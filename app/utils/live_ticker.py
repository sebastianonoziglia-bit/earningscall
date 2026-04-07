"""
Live ticker prices for the Welcome.py stock strip.

Hits Yahoo Finance directly via yfinance and returns a small DataFrame in the
same shape that _render_stock_price_strip already consumes (asset, tag, date,
price, change). 60-second cache means the strip is at most 60s out of date,
which is what "minute level" means in practice.

This bypasses the Google Sheet → Supabase pipeline entirely for the live tail
because that pipeline can't realistically push fresh data faster than every
few minutes. Yahoo is the source of truth, hit it directly.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pandas as pd
import streamlit as st


# (display_name, primary_ticker, list_of_aliases_for_strip_matching)
STRIP_TICKERS: list[tuple[str, str]] = [
    ("Alphabet",                "GOOGL"),
    ("Meta Platforms",          "META"),
    ("Amazon",                  "AMZN"),
    ("Apple",                   "AAPL"),
    ("Microsoft",               "MSFT"),
    ("Netflix",                 "NFLX"),
    ("Disney",                  "DIS"),
    ("Comcast",                 "CMCSA"),
    ("Spotify",                 "SPOT"),
    ("Roku",                    "ROKU"),
    ("Warner Bros. Discovery",  "WBD"),
    ("Paramount Global",        "PARA"),
]


def _fetch_one(name: str, symbol: str) -> dict | None:
    """Fetch one symbol. Tries fast_info first, falls back to history()
    if Yahoo's response shape has drifted (yfinance versions vary)."""
    import yfinance as yf
    price = 0.0
    prev = 0.0
    # Path 1: fast_info — quick (1 HTTP call) but breaks across yfinance versions
    try:
        info = yf.Ticker(symbol).fast_info
        price = float(info.get("lastPrice") or info.get("regularMarketPrice") or 0)
        prev = float(info.get("previousClose") or 0)
    except Exception:
        price, prev = 0.0, 0.0
    # Path 2: history() fallback — slower but extremely reliable
    if price <= 0:
        try:
            hist = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=False)
            if hist is not None and not hist.empty:
                closes = hist["Close"].dropna()
                if len(closes) >= 1:
                    price = float(closes.iloc[-1])
                if len(closes) >= 2:
                    prev = float(closes.iloc[-2])
        except Exception:
            pass
    if price <= 0:
        return None
    change_pct = ((price - prev) / abs(prev) * 100.0) if prev else 0.0
    return {
        "asset": name,
        "tag": symbol,
        "date": pd.Timestamp(datetime.now(timezone.utc)),
        "price": round(price, 4),
        "change": round(change_pct, 2),
    }


@st.cache_data(ttl=60, show_spinner=False)
def get_live_strip_feed() -> pd.DataFrame:
    """Fetch the 12 strip tickers in parallel from Yahoo. 60s cache."""
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(_fetch_one, n, s): (n, s) for n, s in STRIP_TICKERS}
        for fut in as_completed(futures):
            row = fut.result()
            if row:
                rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["asset", "tag", "date", "price", "change"])
    return pd.DataFrame(rows)
