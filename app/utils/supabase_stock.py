"""
Supabase-backed stock data loader.

This module provides narrow, fast reads over the `stock_daily` and
`stock_minute` tables that the GitHub Actions sync writes from the
Google Sheet. It exists so the Streamlit app doesn't have to parse
~240k rows from the xlsx workbook on every cold start.

Three entry points:

    fetch_latest_prices(tickers)
        One row per ticker with the newest minute-level price. Used by
        the Welcome ticker strip. Tiny payload (≤ len(tickers) rows).

    fetch_recent_daily(tickers, lookback_days=7)
        Recent daily closes for the supplied tickers — used to compute
        24h / 3-month change on the Welcome strip and Earnings hero.

    fetch_company_history(ticker_aliases, start_date=None)
        Full historical daily + minute price series for a single
        company, merged with the same source-priority logic as the
        legacy workbook loader. Used by per-company charts on Earnings.

All functions return the same column shape as the existing xlsx path
(see `app/utils/workbook_market_data._STOCK_COLUMNS`) so callers can
drop in without restructuring downstream logic.

If Supabase is not configured (missing env vars) every function returns
an empty DataFrame and the caller should fall back to the xlsx path.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from utils.supabase_client import fetch_table, fetch_table_paginated, is_configured


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


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=_STOCK_COLUMNS)


def _normalize_tickers(tickers: Iterable[str]) -> list[str]:
    """Return a clean de-duplicated list of ticker strings."""
    seen: dict[str, None] = {}
    for t in tickers or []:
        s = str(t or "").strip()
        if not s:
            continue
        seen.setdefault(s, None)
    return list(seen.keys())


def _in_filter(column: str, values: list[str]) -> dict[str, str]:
    """Build a PostgREST `in.(v1,v2,...)` filter dict."""
    if not values:
        return {}
    # PostgREST quotes values with double quotes if they contain commas
    # or spaces. Our tickers are clean alnum strings so no escaping needed.
    return {column: "in.(" + ",".join(values) + ")"}


def _normalize_rows(df: pd.DataFrame, *, source_sheet: str, time_col: str) -> pd.DataFrame:
    """Coerce a Supabase stock_* result into the _STOCK_COLUMNS shape."""
    if df is None or df.empty:
        return _empty()
    out = pd.DataFrame()
    # stock_minute.ts is timestamptz (tz-aware) while stock_daily.date is
    # date (tz-naive). The xlsx path returns tz-naive datetimes, so strip
    # tz info to keep everything comparable downstream.
    _dt = pd.to_datetime(df.get(time_col), errors="coerce", utc=True)
    try:
        _dt = _dt.dt.tz_convert("UTC").dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    out["date"] = _dt
    for col in ["price", "open", "high", "low", "volume", "change_pct", "market_cap", "outstanding_shares"]:
        out[col] = pd.to_numeric(df.get(col), errors="coerce")
    out["currency"] = df.get("currency", "").fillna("").astype(str).str.upper()
    out["asset"] = df.get("asset", "").fillna("").astype(str).str.strip()
    out["tag"] = df.get("tag", "").fillna("").astype(str).str.strip().str.upper()
    out["source_sheet"] = source_sheet
    out = out.dropna(subset=["date", "price"])
    out = out[out["asset"] != ""]
    return out[_STOCK_COLUMNS].copy()


def fetch_latest_prices(tickers: Iterable[str]) -> pd.DataFrame:
    """Return the single most-recent minute row per ticker.

    Falls back to daily if no minute row exists. Returns an empty frame
    when Supabase is not configured or the query turns up nothing.
    """
    if not is_configured():
        return _empty()
    clean = _normalize_tickers(tickers)
    if not clean:
        return _empty()

    # One batched query: get recent minute rows for all requested assets,
    # then pick the latest per ticker client-side. Limit keeps payload
    # bounded even if one ticker is very active.
    filters = _in_filter("asset", clean)
    minute = fetch_table(
        "stock_minute",
        select="ts,asset,tag,price,open,high,low,volume,change_pct,market_cap,currency",
        order="ts.desc",
        limit=max(500, 50 * len(clean)),
        filters=filters,
    )
    minute_norm = _normalize_rows(minute, source_sheet="Minute", time_col="ts")
    if not minute_norm.empty:
        minute_norm = (
            minute_norm.sort_values("date")
            .drop_duplicates(subset=["asset"], keep="last")
        )

    # Always also pull latest daily for each ticker — we need a prior
    # close for 24h change math and Minute doesn't always carry it.
    daily = fetch_table(
        "stock_daily",
        select="date,asset,tag,price,open,high,low,volume,change_pct,market_cap,currency",
        order="date.desc",
        limit=max(500, 30 * len(clean)),
        filters=filters,
    )
    daily_norm = _normalize_rows(daily, source_sheet="Daily", time_col="date")

    if minute_norm.empty and daily_norm.empty:
        return _empty()
    return pd.concat([daily_norm, minute_norm], ignore_index=True)


def fetch_company_history(
    ticker_aliases: Iterable[str],
    *,
    include_daily: bool = True,
    include_minute: bool = True,
    start_date: str | None = None,
    max_rows: int = 20000,
) -> pd.DataFrame:
    """Full historical stock data for one company (all its ticker aliases).

    Uses a single `asset=in.(...)` filter so a company like Alphabet with
    multiple tickers (GOOGL, GOOG) comes back in one request. The xlsx
    path historically also matched on company name in the asset column,
    which we replicate by letting the caller pass any known aliases.

    `start_date` is an ISO date string (e.g. "2015-01-01"). If supplied,
    we only fetch rows with `date >= start_date` / `ts >= start_date`,
    which is the main way to keep the payload small for per-company
    Earnings charts.
    """
    if not is_configured():
        return _empty()
    clean = _normalize_tickers(ticker_aliases)
    if not clean:
        return _empty()
    base_filters = _in_filter("asset", clean)

    frames: list[pd.DataFrame] = []
    if include_daily:
        daily_filters = dict(base_filters)
        if start_date:
            daily_filters["date"] = f"gte.{start_date}"
        daily = fetch_table_paginated(
            "stock_daily",
            select="date,asset,tag,price,open,high,low,volume,change_pct,market_cap,currency",
            order="date.asc",
            max_rows=max_rows,
            filters=daily_filters,
        )
        df = _normalize_rows(daily, source_sheet="Daily", time_col="date")
        if not df.empty:
            frames.append(df)
    if include_minute:
        minute_filters = dict(base_filters)
        if start_date:
            minute_filters["ts"] = f"gte.{start_date}"
        minute = fetch_table_paginated(
            "stock_minute",
            select="ts,asset,tag,price,open,high,low,volume,change_pct,market_cap,currency",
            order="ts.asc",
            max_rows=max_rows,
            filters=minute_filters,
        )
        df = _normalize_rows(minute, source_sheet="Minute", time_col="ts")
        if not df.empty:
            frames.append(df)
    if not frames:
        return _empty()

    merged = pd.concat(frames, ignore_index=True)
    # Match the legacy dedup: prefer Minute (3) > Daily (2) on identical
    # (date, asset, tag) tuples.
    priority = {"Minute": 3, "Daily": 2}
    merged["_prio"] = merged["source_sheet"].map(priority).fillna(0).astype(int)
    merged = merged.sort_values(["date", "asset", "tag", "_prio"])
    merged = merged.drop_duplicates(subset=["date", "asset", "tag"], keep="last")
    merged = merged.drop(columns=["_prio"]).sort_values("date").reset_index(drop=True)
    return merged
