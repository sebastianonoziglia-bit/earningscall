from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict

import pandas as pd


_STOCK_COLUMNS = [
    "date",
    "price",
    "open",
    "high",
    "low",
    "volume",
    "change_pct",
    "market_cap",
    "currency",
    "asset",
    "outstanding_shares",
    "tag",
    "source_sheet",
]

_HOLDERS_COLUMNS = [
    "date_fetched",
    "company",
    "ticker",
    "holder_name",
    "shares",
    "value_usd",
    "pct_out",
    "holder_type",
]

_ALIAS_TO_COMPANY = {
    "alphabet": "Alphabet",
    "google": "Alphabet",
    "googl": "Alphabet",
    "goog": "Alphabet",
    "apple": "Apple",
    "aapl": "Apple",
    "meta platforms": "Meta Platforms",
    "meta": "Meta Platforms",
    "fb": "Meta Platforms",
    "microsoft": "Microsoft",
    "msft": "Microsoft",
    "amazon": "Amazon",
    "amzn": "Amazon",
    "netflix": "Netflix",
    "nflx": "Netflix",
    "disney": "Disney",
    "dis": "Disney",
    "comcast": "Comcast",
    "cmcsa": "Comcast",
    "warner bros": "Warner Bros. Discovery",
    "warner bros. discovery": "Warner Bros. Discovery",
    "wbd": "Warner Bros. Discovery",
    "paramount global": "Paramount Global",
    "paramount": "Paramount Global",
    "para": "Paramount Global",
    "spotify": "Spotify",
    "spot": "Spotify",
    "roku": "Roku",
    "roku inc": "Roku",
    "s&p 500": "S&P 500",
    "sp500": "S&P 500",
    "nasdaq": "Nasdaq",
    "gold": "Gold",
    "bitcoin": "Bitcoin",
}

_SOURCE_PRIORITY = {
    "Daily": 2,
    "Minute": 3,
}


def _empty_stock_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=_STOCK_COLUMNS)


def _empty_holders_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=_HOLDERS_COLUMNS)


def _normalize_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name or "").strip().lower()).strip()


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str:
    alias_set = {_normalize_col(alias) for alias in aliases}
    for col in df.columns:
        if _normalize_col(col) in alias_set:
            return str(col)
    return ""


def _parse_numeric(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None

    # Percent strings are normalized to plain percentage values.
    is_percent = "%" in text
    text = text.replace("%", "").replace("$", "").replace(",", "")
    text = text.replace("−", "-")

    multiplier = 1.0
    upper = text.upper()
    if upper.endswith("K"):
        multiplier = 1_000.0
        text = text[:-1]
    elif upper.endswith("M"):
        multiplier = 1_000_000.0
        text = text[:-1]
    elif upper.endswith("B"):
        multiplier = 1_000_000_000.0
        text = text[:-1]
    elif upper.endswith("T"):
        multiplier = 1_000_000_000_000.0
        text = text[:-1]

    try:
        parsed = float(text) * multiplier
    except ValueError:
        return None
    return parsed


def _clean_ticker(text: str) -> str:
    value = re.sub(r"[^A-Z0-9.-]+", "", str(text or "").strip().upper())
    if value in {"", "NONE", "NAN", "NULL"}:
        return ""
    if len(value) > 10:
        return ""
    if not any(ch.isalpha() for ch in value):
        return ""
    return value


@lru_cache(maxsize=64)
def _read_sheet_cached(excel_path: str, source_stamp: int, sheet_name: str) -> pd.DataFrame:
    del source_stamp
    try:
        return pd.read_excel(excel_path, sheet_name=sheet_name)
    except Exception:
        return pd.DataFrame()


def _normalize_stock_sheet(raw_df: pd.DataFrame, source_sheet: str) -> pd.DataFrame:
    if raw_df is None or raw_df.empty:
        return _empty_stock_frame()

    df = raw_df.copy()
    df.columns = [str(col).strip() for col in df.columns]

    date_col = _find_column(df, ["date", "datetime", "timestamp", "time"])
    price_col = _find_column(df, ["price", "close", "last", "close price", "closing price", "adj close", "adj_close"])
    open_col = _find_column(df, ["open"])
    high_col = _find_column(df, ["high"])
    low_col = _find_column(df, ["low"])
    volume_col = _find_column(df, ["volume", "vol", "vol."])
    change_col = _find_column(df, ["change %", "change", "change pct", "change_percent"])
    market_cap_col = _find_column(df, ["market cap.", "market cap", "market_cap", "market capitalization"])
    currency_col = _find_column(df, ["currency"])
    asset_col = _find_column(df, ["asset", "name", "company", "symbol", "ticker"])
    shares_col = _find_column(df, ["outstanding shares", "shares outstanding", "outstanding_shares"])
    tag_col = _find_column(df, ["tag", "ticker", "symbol"])

    if not date_col or not price_col or not asset_col:
        return _empty_stock_frame()

    out = pd.DataFrame(
        {
            "date": df[date_col],
            "price": df[price_col],
            "open": df[open_col] if open_col else None,
            "high": df[high_col] if high_col else None,
            "low": df[low_col] if low_col else None,
            "volume": df[volume_col] if volume_col else None,
            "change_pct": df[change_col] if change_col else None,
            "market_cap": df[market_cap_col] if market_cap_col else None,
            "currency": df[currency_col] if currency_col else "",
            "asset": df[asset_col],
            "outstanding_shares": df[shares_col] if shares_col else None,
            "tag": df[tag_col] if tag_col else "",
            "source_sheet": source_sheet,
        }
    )

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for col in ["price", "open", "high", "low", "volume", "change_pct", "market_cap", "outstanding_shares"]:
        out[col] = out[col].apply(_parse_numeric)
    out["asset"] = out["asset"].fillna("").astype(str).str.strip()
    out["currency"] = out["currency"].fillna("").astype(str).str.strip().str.upper()
    out["tag"] = out["tag"].fillna("").astype(str).str.strip().str.upper().apply(_clean_ticker)

    # If tag is empty, derive a ticker-like key from asset for dedup/ticker mapping.
    empty_tag = out["tag"] == ""
    out.loc[empty_tag, "tag"] = out.loc[empty_tag, "asset"].apply(_clean_ticker)

    out = out.dropna(subset=["date", "price"])
    out = out[out["asset"] != ""].copy()
    if out.empty:
        return _empty_stock_frame()
    return out[_STOCK_COLUMNS]


def load_combined_stock_market_data(
    excel_path: str,
    source_stamp: int = 0,
    include_baseline: bool = False,  # kept for signature stability; no baseline sheet exists anymore
    include_daily: bool = True,
    include_minute: bool = True,
) -> pd.DataFrame:
    # `include_baseline` used to select a "Stocks & Crypto" tab that has
    # since been removed from the workbook. The parameter is kept so
    # callers don't need to change, but it is now a no-op.
    del include_baseline
    if not excel_path:
        return _empty_stock_frame()

    sheets: list[str] = []
    if include_daily:
        sheets.append("Daily")
    if include_minute:
        sheets.append("Minute")

    frames: list[pd.DataFrame] = []
    for sheet_name in sheets:
        raw = _read_sheet_cached(excel_path, int(source_stamp or 0), sheet_name).copy()
        normalized = _normalize_stock_sheet(raw, sheet_name)
        if normalized is not None and not normalized.empty:
            frames.append(normalized)

    if not frames:
        return _empty_stock_frame()

    merged = pd.concat(frames, ignore_index=True)
    merged["asset_key"] = merged["asset"].astype(str).str.upper().str.strip()
    merged["tag_key"] = merged["tag"].fillna("").astype(str)
    merged["source_rank"] = merged["source_sheet"].map(_SOURCE_PRIORITY).fillna(0).astype(int)
    merged = merged.sort_values(["date", "asset_key", "tag_key", "source_rank"])
    merged = merged.drop_duplicates(subset=["date", "asset_key", "tag_key"], keep="last")
    merged = merged.drop(columns=["asset_key", "tag_key", "source_rank"])
    return merged.sort_values("date").reset_index(drop=True)


def infer_company_label(asset: str, tag: str) -> str:
    asset_text = str(asset or "").strip()
    tag_text = str(tag or "").strip()
    combined = f"{asset_text} {tag_text}".strip().lower()
    for alias, company in _ALIAS_TO_COMPANY.items():
        if alias in combined:
            return company
    if asset_text and asset_text.upper() not in {"NAN", "NONE", "NULL"}:
        return asset_text
    ticker = _clean_ticker(tag_text)
    if ticker:
        return ticker
    return ""


def build_company_ticker_map_from_market_data(excel_path: str, source_stamp: int = 0) -> Dict[str, str]:
    df = load_combined_stock_market_data(
        excel_path=excel_path,
        source_stamp=source_stamp,
        include_daily=True,
        include_minute=True,
    )
    if df.empty:
        return {}

    out: Dict[str, str] = {}
    latest = df.sort_values("date")
    for _, row in latest.iterrows():
        label = infer_company_label(row.get("asset", ""), row.get("tag", ""))
        ticker = _clean_ticker(row.get("tag", "")) or _clean_ticker(row.get("asset", ""))
        if label and ticker and any(ch.isalpha() for ch in ticker):
            out[label] = ticker
    return out


def load_holders_sheet(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return _empty_holders_frame()

    raw = _read_sheet_cached(excel_path, int(source_stamp or 0), "Holders").copy()
    if raw is None or raw.empty:
        return _empty_holders_frame()

    df = raw.copy()
    df.columns = [str(col).strip() for col in df.columns]

    mapping = {
        "date_fetched": _find_column(df, ["date_fetched", "date fetched", "fetched_at", "timestamp"]),
        "company": _find_column(df, ["company", "asset", "name"]),
        "ticker": _find_column(df, ["ticker", "tag", "symbol"]),
        "holder_name": _find_column(df, ["holder_name", "holder name", "holder"]),
        "shares": _find_column(df, ["shares", "shares_owned", "share_count"]),
        "value_usd": _find_column(df, ["value_usd", "value usd", "value", "market_value"]),
        "pct_out": _find_column(df, ["pct_out", "pct out", "% out", "ownership_pct"]),
        "holder_type": _find_column(df, ["holder_type", "holder type", "type"]),
    }

    out = pd.DataFrame()
    for target in _HOLDERS_COLUMNS:
        source_col = mapping.get(target, "")
        out[target] = df[source_col] if source_col else None

    out["date_fetched"] = pd.to_datetime(out["date_fetched"], errors="coerce")
    for col in ["shares", "value_usd", "pct_out"]:
        out[col] = out[col].apply(_parse_numeric)
    for col in ["company", "ticker", "holder_name", "holder_type"]:
        out[col] = out[col].fillna("").astype(str).str.strip()
    out["ticker"] = out["ticker"].str.upper().apply(_clean_ticker)

    out = out[(out["company"] != "") & (out["holder_name"] != "")].copy()
    if out.empty:
        return _empty_holders_frame()

    # Keep the latest row when duplicate keys exist in the export.
    out = out.sort_values("date_fetched")
    out = out.drop_duplicates(subset=["company", "ticker", "holder_name"], keep="last")
    return out[_HOLDERS_COLUMNS].reset_index(drop=True)
