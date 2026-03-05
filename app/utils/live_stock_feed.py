import os
import re
import time
from functools import lru_cache
from typing import Dict

import pandas as pd


DEFAULT_LIVE_STOCK_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1LVQpPmkKua9GxecehY7g--q1bIKRCrtj__0iv6Msj8U/export?format=csv"
)


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
}


def live_feed_cache_bucket(seconds: int = 300) -> int:
    seconds = max(int(seconds or 300), 60)
    return int(time.time() // seconds)


def _empty_feed_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "price", "volume", "asset", "tag"])


def _normalize_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name or "").strip().lower()).strip()


def _find_column(df: pd.DataFrame, aliases) -> str:
    alias_set = {_normalize_col(a) for a in aliases}
    for col in df.columns:
        if _normalize_col(col) in alias_set:
            return col
    return ""


def _parse_numeric(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
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
        return float(text) * multiplier
    except ValueError:
        return None


def _clean_ticker(text: str) -> str:
    value = re.sub(r"[^A-Z0-9.-]+", "", str(text or "").strip().upper())
    if value in {"", "NONE", "NAN", "NULL"}:
        return ""
    if len(value) > 10:
        return ""
    if not any(ch.isalpha() for ch in value):
        return ""
    return value


@lru_cache(maxsize=8)
def load_live_stock_feed(cache_bucket: int = 0, url: str = "") -> pd.DataFrame:
    del cache_bucket  # cache key only
    source_url = (url or os.getenv("LIVE_STOCK_SHEET_URL", DEFAULT_LIVE_STOCK_SHEET_URL)).strip()
    if not source_url:
        return _empty_feed_frame()

    try:
        raw = pd.read_csv(source_url)
    except Exception:
        return _empty_feed_frame()

    if raw is None or raw.empty:
        return _empty_feed_frame()

    date_col = _find_column(raw, ["date", "datetime", "timestamp", "time"])
    price_col = _find_column(raw, ["price", "close", "last", "close price", "closing price", "adj close", "adj_close"])
    asset_col = _find_column(raw, ["asset", "name", "company", "symbol", "ticker"])
    volume_col = _find_column(raw, ["volume", "vol", "vol."])
    tag_col = _find_column(raw, ["tag", "ticker", "symbol"])

    if not date_col or not price_col or not asset_col:
        return _empty_feed_frame()

    out = pd.DataFrame(
        {
            "date": raw[date_col],
            "price": raw[price_col],
            "volume": raw[volume_col] if volume_col else None,
            "asset": raw[asset_col],
            "tag": raw[tag_col] if tag_col else "",
        }
    )

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["price"] = out["price"].apply(_parse_numeric)
    out["volume"] = out["volume"].apply(_parse_numeric)
    out["asset"] = out["asset"].fillna("").astype(str).str.strip()
    out["tag"] = out["tag"].fillna("").astype(str).str.strip().str.upper()
    out["tag"] = out["tag"].apply(_clean_ticker)
    out = out.dropna(subset=["date", "price"])
    out = out[out["asset"] != ""].copy()

    if out.empty:
        return _empty_feed_frame()
    return out[["date", "price", "volume", "asset", "tag"]]


def merge_with_live_stock_feed(base_df: pd.DataFrame, cache_bucket: int = 0) -> pd.DataFrame:
    live_df = load_live_stock_feed(cache_bucket=cache_bucket)

    if base_df is None or base_df.empty:
        return live_df.copy()

    out = base_df.copy()
    if "date" not in out.columns:
        return live_df.copy() if not live_df.empty else _empty_feed_frame()
    if "price" not in out.columns:
        return live_df.copy() if not live_df.empty else _empty_feed_frame()
    if "asset" not in out.columns:
        out["asset"] = ""
    if "volume" not in out.columns:
        out["volume"] = None
    if "tag" not in out.columns:
        out["tag"] = ""

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["price"] = out["price"].apply(_parse_numeric)
    out["volume"] = out["volume"].apply(_parse_numeric)
    out["asset"] = out["asset"].fillna("").astype(str).str.strip()
    out["tag"] = out["tag"].fillna("").astype(str).str.strip().str.upper().apply(_clean_ticker)
    out = out.dropna(subset=["date", "price"])
    out = out[out["asset"] != ""].copy()

    if live_df.empty:
        return out.sort_values("date").reset_index(drop=True)

    merged = pd.concat([out[["date", "price", "volume", "asset", "tag"]], live_df], ignore_index=True)
    merged["asset_upper"] = merged["asset"].str.upper()
    merged["tag_key"] = merged["tag"].fillna("")
    merged = merged.sort_values(["date", "asset_upper", "tag_key"])
    merged = merged.drop_duplicates(subset=["date", "asset_upper", "tag_key"], keep="last")
    merged = merged.drop(columns=["asset_upper", "tag_key"])
    return merged.sort_values("date").reset_index(drop=True)


def infer_company_label(asset: str, tag: str) -> str:
    combined = f"{asset or ''} {tag or ''}".strip().lower()
    for alias, company in _ALIAS_TO_COMPANY.items():
        if alias in combined:
            return company
    ticker = _clean_ticker(tag) or _clean_ticker(asset)
    if ticker:
        return ticker
    label = str(asset or "").strip()
    return label if label else ""


def build_live_company_ticker_map(cache_bucket: int = 0) -> Dict[str, str]:
    df = load_live_stock_feed(cache_bucket=cache_bucket)
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
