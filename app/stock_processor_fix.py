import os
from datetime import datetime, timedelta
from functools import lru_cache

import pandas as pd


def _resolve_data_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "attached_assets", "Earnings + stocks  copy.xlsx"),
        os.path.join(base_dir, "..", "Earnings + stocks  copy.xlsx"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None


def _parse_numeric(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    multiplier = 1.0
    if text.endswith("K"):
        multiplier = 1_000.0
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1_000_000.0
        text = text[:-1]
    elif text.endswith("B"):
        multiplier = 1_000_000_000.0
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _load_stock_sheet(path):
    if not path or not os.path.exists(path):
        return pd.DataFrame()

    df = pd.read_excel(
        path,
        sheet_name="Stocks & Crypto",
        usecols=["date", "price", "vol.", "asset", "tag"],
    )
    df = df.rename(columns={"vol.": "volume"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["price"] = df["price"].apply(_parse_numeric)
    df["volume"] = df["volume"].apply(_parse_numeric)
    return df.dropna(subset=["date", "price"])


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
        }

    def _increment_calls(self):
        key = "local_excel"
        self.calls_today[key] = self.calls_today.get(key, 0) + 1

    def _filter_company(self, df, company):
        if df.empty:
            return df
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
        df = _load_stock_sheet(self.data_path)
        if df.empty:
            return None
        df_company = self._filter_company(df, company)
        if df_company.empty:
            return None
        df_company = df_company.sort_values("date")
        df_company = self._apply_timeframe(df_company, timeframe)
        if df_company.empty:
            return None

        history = df_company[["date", "price", "volume"]].rename(
            columns={"price": "Close", "volume": "Volume"}
        )
        history = history.set_index("date")

        last_price = history["Close"].iloc[-1]
        prev_price = history["Close"].iloc[-2] if len(history) > 1 else last_price
        change = last_price - prev_price
        change_percent = (change / prev_price * 100) if prev_price else 0
        volume = history["Volume"].iloc[-1] if "Volume" in history else 0

        symbol = (self._ticker_map.get(company) or [company])[0]
        quote = {
            "price": float(last_price),
            "change": float(change),
            "change_percent": float(change_percent),
            "symbol": symbol,
            "volume": int(volume) if volume is not None else 0,
        }

        return {
            "quote": quote,
            "history": history,
            "source": "excel",
        }

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
