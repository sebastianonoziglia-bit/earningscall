"""
Supabase REST client (read-only, anon key).

This is the *runtime* read path used by the Streamlit app. Writes happen
out-of-band via scripts/sync_gsheet_to_supabase.py (run by GitHub Actions).

We use the publishable / anon key here because:
  1. The app reads tables that have permissive read RLS policies.
  2. The anon key is safe to ship to the browser (Streamlit reveals env vars
     to the page anyway via st.secrets / os.environ).
  3. The secret key would be wasted privilege and a leak risk.

Reads use the PostgREST endpoint with simple ?select=*&order=... filters.
For anything more complex, write a SQL view in Supabase and select that.
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
import streamlit as st


SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_ANON_KEY = (
    os.environ.get("SUPABASE_ANON_KEY")
    or os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    or ""
)


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY)


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Accept": "application/json",
    }


@st.cache_data(ttl=600, show_spinner=False)
def fetch_table(
    table: str,
    select: str = "*",
    order: str | None = None,
    limit: int | None = None,
    filters: dict[str, str] | None = None,
) -> pd.DataFrame:
    """
    Read rows from a Supabase table via PostgREST.

    Args:
        table: table name (e.g. "stock_daily")
        select: columns to select, default "*"
        order: e.g. "date.desc"
        limit: max rows
        filters: dict of {column: "op.value"}, e.g. {"asset": "eq.AAPL"}

    Returns: DataFrame (empty on any failure — caller falls back to sheet).
    """
    if not is_configured():
        return pd.DataFrame()
    params: dict[str, Any] = {"select": select}
    if order:
        params["order"] = order
    if limit:
        params["limit"] = str(limit)
    if filters:
        params.update(filters)
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=20)
        if resp.status_code >= 300:
            return pd.DataFrame()
        data = resp.json()
        if not isinstance(data, list) or not data:
            return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def fetch_table_paginated(
    table: str,
    select: str = "*",
    order: str | None = None,
    page_size: int = 1000,
    max_rows: int = 200_000,
) -> pd.DataFrame:
    """Page through a large table in 1000-row chunks (PostgREST default cap)."""
    if not is_configured():
        return pd.DataFrame()
    out: list[pd.DataFrame] = []
    offset = 0
    while offset < max_rows:
        params: dict[str, Any] = {
            "select": select,
            "limit": str(page_size),
            "offset": str(offset),
        }
        if order:
            params["order"] = order
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        try:
            resp = requests.get(url, headers=_headers(), params=params, timeout=30)
            if resp.status_code >= 300:
                break
            chunk = resp.json()
            if not isinstance(chunk, list) or not chunk:
                break
            out.append(pd.DataFrame(chunk))
            if len(chunk) < page_size:
                break
            offset += page_size
        except Exception:
            break
    if not out:
        return pd.DataFrame()
    return pd.concat(out, ignore_index=True)
