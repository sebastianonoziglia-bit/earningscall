import os
from datetime import datetime, timedelta
from functools import lru_cache

import pandas as pd
from utils.workbook_source import resolve_financial_data_xlsx, get_workbook_source_stamp
from utils.workbook_market_data import infer_company_label, load_combined_stock_market_data


def _resolve_data_path():
    return resolve_financial_data_xlsx([])


def _normalize_label(value):
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def _is_excluded_stock_label(value):
    key = _normalize_label(value)
    if not key:
        return False
    if key in {"m2", "mstr", "app"}:
        return True
    return "microstrategy" in key or "applovin" in key


def _is_excluded_stock_row(asset, tag, label=""):
    if _is_excluded_stock_label(label) or _is_excluded_stock_label(asset):
        return True
    ticker = str(tag or "").strip().upper()
    return ticker in {"M2", "MSTR", "APP"}


@lru_cache(maxsize=8)
def _load_stock_sheet(path, source_stamp):
    if not path or not os.path.exists(path):
        return pd.DataFrame()

    merged = load_combined_stock_market_data(
        excel_path=path,
        source_stamp=int(source_stamp or 0),
        include_baseline=True,
        include_daily=True,
        include_minute=True,
    )
    if merged is None or merged.empty:
        return pd.DataFrame()
    out = merged.copy()
    for col in ("volume", "open", "high", "low"):
        if col not in out.columns:
            out[col] = None
    if "tag" not in out.columns:
        out["tag"] = ""
    if "source_sheet" not in out.columns:
        out["source_sheet"] = ""
    keep_cols = ["date", "price", "open", "high", "low", "volume", "asset", "tag", "source_sheet"]
    return out.dropna(subset=["date", "price"])[[c for c in keep_cols if c in out.columns]]


class StockDataProcessor:
    """Local Excel-backed stock data processor (no external API)."""

    def __init__(self, data_path=None):
        self.data_path = data_path or _resolve_data_path()
        self.calls_today = {}
        self.last_reset = datetime.now().isoformat()
        self.max_calls_per_key = 500
        self._ticker_map = {
            "Alphabet": ["GOOGL", "GOOG", "ALPHABET", "GOOGLE"],
            "Apple": ["AAPL", "APPLE"],
            "Meta Platforms": ["META", "FB", "META PLATFORMS"],
            "Meta": ["META", "FB", "META PLATFORMS"],
            "Microsoft": ["MSFT", "MICROSOFT"],
            "Amazon": ["AMZN", "AMAZON"],
            "Netflix": ["NFLX", "NETFLIX"],
            "Disney": ["DIS", "DISNEY"],
            "Comcast": ["CMCSA", "COMCAST"],
            "Warner Bros. Discovery": ["WBD", "WARNER BROS", "WARNER BROS. DISCOVERY"],
            "Warner Bros Discovery": ["WBD", "WARNER BROS", "WARNER BROS. DISCOVERY"],
            "Paramount Global": ["PARA", "PARAMOUNT"],
            "Paramount": ["PARA", "PARAMOUNT"],
            "Spotify": ["SPOT", "SPOTIFY"],
            "Roku": ["ROKU", "ROKU INC"],
            "Bitcoin": ["BTC-USD", "BTC", "BITCOIN"],
            "S&P 500": ["^GSPC", "S&P500", "S&P 500", "SP500"],
            "Nasdaq": ["^IXIC", "NASDAQ"],
            "Nvidia": ["NVDA", "NVIDIA"],
            "NVIDIA": ["NVDA", "NVIDIA"],
            "TTD": ["TTD", "THE TRADE DESK"],
            "The Trade Desk": ["TTD", "THE TRADE DESK"],
            "CRTO": ["CRTO", "CRITEO"],
            "Criteo": ["CRTO", "CRITEO"],
            "DSP": ["DSP", "VIANT", "VIANT TECHNOLOGY"],
            "Viant Technology": ["DSP", "VIANT", "VIANT TECHNOLOGY"],
            "U": ["U", "UTIQ"],
            "Utiq": ["U", "UTIQ"],
            "MGNI": ["MGNI", "MAGNITE"],
            "Magnite": ["MGNI", "MAGNITE"],
            "PUBM": ["PUBM", "PUBMATIC"],
            "PubMatic": ["PUBM", "PUBMATIC"],
            "DV": ["DV", "DOUBLEVERIFY"],
            "DoubleVerify": ["DV", "DOUBLEVERIFY"],
            "IAS": ["IAS", "INTEGRAL AD SCIENCE"],
            "Integral Ad Science": ["IAS", "INTEGRAL AD SCIENCE"],
            "SNAP": ["SNAP", "SNAPCHAT"],
            "PINS": ["PINS", "PINTEREST"],
            "NEXN": ["NEXN", "NEXXEN"],
        }

    def _increment_calls(self):
        key = "local_excel"
        self.calls_today[key] = self.calls_today.get(key, 0) + 1

    def _filter_company(self, df, company):
        if df.empty:
            return df
        if _is_excluded_stock_label(company):
            return df.iloc[0:0]
        asset = df["asset"].fillna("").astype(str)
        tag = df["tag"].fillna("").astype(str)
        mask = asset.str.contains(company, case=False, regex=False)
        tickers = self._ticker_map.get(company, [])
        if tickers:
            tickers_upper = [t.upper() for t in tickers]
            mask |= asset.str.upper().isin(tickers_upper)
            mask |= tag.str.upper().isin(tickers_upper)
        if company == "Alphabet":
            mask |= asset.str.contains("Google", case=False, regex=False)
        return df[mask]

    def _apply_timeframe(self, df, timeframe):
        if df.empty or timeframe == "MAX":
            return df
        delta_map = {
            "1M": 30,
            "3M": 90,
            "6M": 180,
            "1Y": 365,
            "2Y": 730,
            "5Y": 1825,
        }
        days = delta_map.get(timeframe, 30)
        end_date = df["date"].max()
        start_date = end_date - timedelta(days=days)
        return df[df["date"] >= start_date]

    def get_company_data(self, company, timeframe="1M", expanded=False):
        self._increment_calls()
        if _is_excluded_stock_label(company):
            return None
        source_stamp = get_workbook_source_stamp(self.data_path)
        df = _load_stock_sheet(self.data_path, source_stamp)
        if df.empty:
            return None
        df_company = self._filter_company(df, company)
        if df_company.empty:
            return None
        df_company = df_company.sort_values("date")
        df_company = self._apply_timeframe(df_company, timeframe)
        if df_company.empty:
            return None

        hist_cols = {"price": "Close", "volume": "Volume"}
        avail = ["date", "price", "volume"]
        if "open" in df_company.columns:
            avail.append("open")
            hist_cols["open"] = "Open"
        if "high" in df_company.columns:
            avail.append("high")
            hist_cols["high"] = "High"
        if "low" in df_company.columns:
            avail.append("low")
            hist_cols["low"] = "Low"
        history = df_company[[c for c in avail if c in df_company.columns]].rename(columns=hist_cols)
        history = history.set_index("date")

        last_price = history["Close"].iloc[-1]
        prev_price = history["Close"].iloc[-2] if len(history) > 1 else last_price
        change = last_price - prev_price
        change_percent = (change / prev_price * 100) if prev_price else 0
        volume = history["Volume"].iloc[-1] if "Volume" in history else 0
        volume_int = 0
        if volume is not None and not pd.isna(volume):
            try:
                volume_int = int(float(volume))
            except (TypeError, ValueError):
                volume_int = 0

        symbol = (self._ticker_map.get(company) or [company])[0]
        quote = {
            "price": float(last_price),
            "change": float(change),
            "change_percent": float(change_percent),
            "symbol": symbol,
            "volume": volume_int,
        }

        return {
            "quote": quote,
            "history": history,
            "source": "excel+live",
        }

    def get_companies(self):
        source_stamp = get_workbook_source_stamp(self.data_path)
        df = _load_stock_sheet(self.data_path, source_stamp)

        discovered = []
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                label = infer_company_label(row.get("asset", ""), row.get("tag", ""))
                if _is_excluded_stock_row(row.get("asset", ""), row.get("tag", ""), label):
                    continue
                if label:
                    discovered.append(label)

        seed = [
            "Alphabet",
            "Apple",
            "Meta Platforms",
            "Microsoft",
            "Amazon",
            "Netflix",
            "Disney",
            "Comcast",
            "Warner Bros. Discovery",
            "Paramount Global",
            "Spotify",
            "Roku",
            "Bitcoin",
            "S&P 500",
            "Nasdaq",
            "TTD",
            "CRTO",
            "DSP",
            "U",
            "MGNI",
            "PUBM",
            "NEXN",
            "DV",
            "IAS",
            "SNAP",
            "PINS",
        ]
        merged = seed + discovered
        return sorted(
            {
                str(name).strip()
                for name in merged
                if str(name).strip() and not _is_excluded_stock_label(name)
            },
            key=lambda s: s.lower(),
        )

    def get_call_stats(self):
        return {
            "last_reset": self.last_reset,
            "calls_today": self.calls_today,
            "max_calls_per_key": self.max_calls_per_key,
        }

    def reset_daily_calls(self):
        self.calls_today = {}
        self.last_reset = datetime.now().isoformat()

    def force_reset_counters(self):
        self.reset_daily_calls()
