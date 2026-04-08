#!/usr/bin/env python3
"""
Sync Google Sheet → Supabase Postgres.

Reads the workbook via the existing resolve_financial_data_xlsx() (which
downloads the Google Sheet once and caches it), then upserts each sheet's
data into the corresponding Supabase table.

Why this script exists (and not Apps Script):
    Apps Script's UrlFetchApp forces a "Mozilla/..." User-Agent on every
    outbound request. Supabase pattern-matches that as "browser" and rejects
    all sb_secret_* keys with HTTP 401 ("Forbidden use of secret API key in
    browser"). Python is a real server environment so the secret key works.

Run all tables:
    python scripts/sync_gsheet_to_supabase.py

Run specific tables only:
    python scripts/sync_gsheet_to_supabase.py --tables stock_daily,holders

Prereqs:
    1. .env file at repo root with SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
    2. Schema applied: paste supabase/migrations/0001_initial_schema.sql
       into the Supabase Studio SQL Editor and click Run.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests


# ── .env loader ────────────────────────────────────────────────────────
def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


REPO_ROOT = Path(__file__).resolve().parents[1]
_load_env(REPO_ROOT / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)


# ── reuse the app's workbook resolver (shared download cache) ──────────
APP_DIR = REPO_ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
from utils.workbook_source import resolve_financial_data_xlsx  # noqa: E402


# ── helpers ────────────────────────────────────────────────────────────
def _norm_col(name: str) -> str:
    return (
        str(name or "")
        .strip()
        .lower()
        .replace("&", " and ")
        .replace("%", " pct ")
        .replace(".", " ")
        .replace("-", " ")
        .replace("/", " ")
    )


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={c: "_".join(p for p in _norm_col(c).split() if p) for c in df.columns})


def _clean(v: Any) -> Any:
    if v is None:
        return None
    # pandas 3.x may yield pd.NA in object columns; catch that explicitly.
    if v is pd.NA:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, (int, float, bool, str)):
        return v
    return str(v)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{k: _clean(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def _str_col(df: pd.DataFrame, name: str, default: str = "") -> pd.Series:
    """Return a cleaned string Series for `name`, aligned to df's index.

    Robust against:
      - missing column  → Series of `default`
      - NaN / None / pd.NA values → `default`
      - pandas 3.x where `.astype(str)` on NaN yields pd.NA that later becomes None
      - literal string residue like "nan" / "None" / "<NA>"
    """
    if name in df.columns:
        s = df[name]
    else:
        return pd.Series([default] * len(df), index=df.index, dtype="object")
    # Replace any NA/NaN/None with default BEFORE astype, so no pd.NA survives.
    s = s.where(s.notna(), default)
    s = s.astype(str).str.strip()
    s = s.replace({"nan": default, "NaN": default, "None": default, "<NA>": default, "": default})
    return s.fillna(default)


# ── Supabase upsert ────────────────────────────────────────────────────
def upsert(
    table: str,
    rows: list[dict[str, Any]],
    batch_size: int = 500,
    on_conflict: str | None = None,
) -> int:
    """Upsert rows into a Supabase table.

    PostgREST's `Prefer: resolution=merge-duplicates` normally resolves
    conflicts on the primary key. For tables that use a surrogate
    `bigserial primary key` with the real dedup key expressed as a
    separate UNIQUE constraint (e.g. `holders`), pass `on_conflict` with
    the comma-separated column list so PostgREST uses that constraint
    instead. Without this the insert raises 23505 on the unique index.
    """
    if not rows:
        print(f"  {table}: no rows")
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if on_conflict:
        url += f"?on_conflict={on_conflict}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
        "Prefer": "return=minimal,resolution=merge-duplicates",
    }
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        resp = requests.post(url, json=batch, headers=headers, timeout=60)
        if resp.status_code >= 300:
            print(f"  {table}: HTTP {resp.status_code} — {resp.text[:400]}")
            raise SystemExit(1)
        total += len(batch)
    print(f"  {table}: {total} rows upserted")
    return total


def _read_sheet(workbook: str, sheet_name: str) -> pd.DataFrame:
    try:
        df = pd.read_excel(workbook, sheet_name=sheet_name)
    except Exception as exc:
        print(f"  WARN: could not read sheet '{sheet_name}': {exc}")
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    return _normalize_columns(df)


# ── per-table transformers ─────────────────────────────────────────────
def _build_stock_frame(df: pd.DataFrame, *, time_col: str, time_format: str) -> pd.DataFrame:
    """Shared stock dataframe builder for daily/minute/yearly syncs.

    Returns a cleaned DataFrame with columns matching the stock_* tables.
    `time_col` is either 'date' or 'ts'; `time_format` is the strftime pattern.
    """
    out = pd.DataFrame(index=df.index)
    out[time_col] = pd.to_datetime(df.get("date"), errors="coerce").dt.strftime(time_format)
    out["asset"] = _str_col(df, "asset")
    # Volume column: sheet uses "vol" / "vol." normalized to "vol"
    vol_col = "volume" if "volume" in df.columns else ("vol" if "vol" in df.columns else None)
    out["price"] = pd.to_numeric(df.get("close", df.get("price")), errors="coerce")
    out["open"] = pd.to_numeric(df.get("open"), errors="coerce")
    out["high"] = pd.to_numeric(df.get("high"), errors="coerce")
    out["low"] = pd.to_numeric(df.get("low"), errors="coerce")
    out["volume"] = pd.to_numeric(df[vol_col], errors="coerce") if vol_col else None
    out["change_pct"] = pd.to_numeric(df.get("change_pct"), errors="coerce")
    out["market_cap"] = pd.to_numeric(df.get("market_cap"), errors="coerce")
    out["currency"] = _str_col(df, "currency", default="USD")
    # tag is NOT NULL in the schema (default ''). Fall back to asset if the
    # sheet row has no tag. If both are missing the row will be dropped next
    # by the asset-length filter below.
    tag = _str_col(df, "tag", default="")
    tag = tag.where(tag.str.len() > 0, out["asset"].fillna(""))
    out["tag"] = tag.fillna("").astype(str)
    out = out.dropna(subset=[time_col])
    # Drop rows whose asset ended up empty after string cleaning
    out = out[out["asset"].astype(str).str.len() > 0]
    out = out.drop_duplicates(subset=[time_col, "asset", "tag"], keep="last")
    return out


def sync_stock_daily(workbook: str) -> int:
    df = _read_sheet(workbook, "Daily")
    if df.empty:
        return 0
    out = _build_stock_frame(df, time_col="date", time_format="%Y-%m-%d")
    return upsert("stock_daily", _records(out))


def sync_stock_minute(workbook: str) -> int:
    df = _read_sheet(workbook, "Minute")
    if df.empty:
        return 0
    out = _build_stock_frame(df, time_col="ts", time_format="%Y-%m-%dT%H:%M:%S")
    return upsert("stock_minute", _records(out))


def sync_stock_yearly(workbook: str) -> int:
    # The workbook does not currently contain a "Stocks & Crypto" tab — the
    # yearly archive was folded into Daily. Try a few name variants; if none
    # exist, return 0 silently instead of logging noisy warnings.
    for name in ("Stocks & Crypto", "Stocks and Crypto", "Stocks_Crypto"):
        try:
            df = pd.read_excel(workbook, sheet_name=name)
        except Exception:
            continue
        if df is not None and not df.empty:
            df = _normalize_columns(df)
            out = _build_stock_frame(df, time_col="date", time_format="%Y-%m-%d")
            return upsert("stock_yearly", _records(out))
    return 0


def sync_holders(workbook: str) -> int:
    df = _read_sheet(workbook, "Holders")
    if df.empty:
        return 0
    out = pd.DataFrame(index=df.index)
    out["date_fetched"] = pd.to_datetime(df.get("date_fetched"), errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
    out["company"] = _str_col(df, "company")
    out["ticker"] = _str_col(df, "ticker")
    out["holder_name"] = _str_col(df, "holder_name")
    out["shares"] = pd.to_numeric(df.get("shares"), errors="coerce")
    out["value_usd"] = pd.to_numeric(df.get("value_usd"), errors="coerce")
    out["pct_out"] = pd.to_numeric(df.get("pct_out"), errors="coerce")
    out["holder_type"] = _str_col(df, "holder_type")
    out = out.dropna(subset=["date_fetched"])
    out = out[(out["company"].str.len() > 0) & (out["holder_name"].str.len() > 0)]
    # Pre-dedup on the UNIQUE key. PostgREST rejects a batch that contains
    # two rows with the same on_conflict tuple even when merge-duplicates
    # is set, so we collapse duplicates here and keep the latest row.
    out = out.drop_duplicates(
        subset=["company", "ticker", "holder_name", "date_fetched"],
        keep="last",
    )
    return upsert(
        "holders",
        _records(out),
        on_conflict="company,ticker,holder_name,date_fetched",
    )


def sync_financial_metrics_yearly(workbook: str) -> int:
    df = _read_sheet(workbook, "Company_metrics_earnings_values")
    if df.empty:
        return 0
    if "company" not in df.columns or "year" not in df.columns:
        print("  financial_metrics_yearly: missing required columns")
        return 0
    out = pd.DataFrame(index=df.index)
    out["company"] = _str_col(df, "company")
    out["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    for src, dst in [
        ("revenue", "revenue"),
        ("cost_of_revenue", "cost_of_revenue"),
        ("operating_income", "operating_income"),
        ("net_income", "net_income"),
        ("r_d", "rd"),
        ("r_and_d", "rd"),
        ("capex", "capex"),
        ("total_assets", "total_assets"),
        ("market_cap", "market_cap"),
        ("market_cap_", "market_cap"),
        ("cash_balance", "cash_balance"),
        ("debt", "debt"),
    ]:
        if src in df.columns and dst not in out.columns:
            out[dst] = pd.to_numeric(df[src], errors="coerce")
    out = out.dropna(subset=["company", "year"])
    out["year"] = out["year"].astype(int)
    return upsert("financial_metrics_yearly", _records(out))


def sync_company_advertising_revenue(workbook: str) -> int:
    df = _read_sheet(workbook, "Company_advertising_revenue")
    if df.empty or "year" not in df.columns:
        return 0
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"]).copy()
    df["year"] = df["year"].astype(int)

    col_to_company = {
        "google_ads": "Alphabet",
        "meta_ads": "Meta Platforms",
        "amazon_ads": "Amazon",
        "spotify_ads": "Spotify",
        "wbd_ads": "Warner Bros. Discovery",
        "microsoft_ads": "Microsoft",
        "paramount": "Paramount Global",
        "apple": "Apple",
        "disney": "Disney",
        "comcast": "Comcast",
        "netflix": "Netflix",
        "twitter_x": "Twitter/X",
        "tiktok": "TikTok",
        "snapchat": "Snapchat",
    }
    rows: list[dict[str, Any]] = []
    for col, company in col_to_company.items():
        if col not in df.columns:
            continue
        for year, value in zip(df["year"].tolist(), pd.to_numeric(df[col], errors="coerce").tolist()):
            if pd.isna(value):
                continue
            rows.append({"company": company, "year": int(year), "ad_revenue": float(value)})
    return upsert("company_advertising_revenue", rows)


def sync_global_adv_aggregates(workbook: str) -> int:
    df = _read_sheet(workbook, "Global_Adv_Aggregates")
    if df.empty:
        return 0
    metric_col = next((c for c in df.columns if c in ("metric_type", "metric")), None)
    year_col = "year" if "year" in df.columns else None
    value_col = next((c for c in df.columns if c in ("value", "value_m", "amount")), None)
    if not metric_col or not year_col or not value_col:
        print("  global_adv_aggregates: missing required columns")
        return 0
    out = pd.DataFrame(index=df.index)
    out["metric_type"] = (
        _str_col(df, metric_col)
        .str.replace(" Worldwide", "", regex=False)
        .str.strip()
    )
    out["year"] = pd.to_numeric(df[year_col], errors="coerce").astype("Int64")
    out["value"] = pd.to_numeric(df[value_col], errors="coerce")
    out = out.dropna(subset=["metric_type", "year"])
    out["year"] = out["year"].astype(int)
    return upsert("global_adv_aggregates", _records(out))


def sync_company_employees(workbook: str) -> int:
    df = _read_sheet(workbook, "Company_Employees")
    if df.empty or "company" not in df.columns or "year" not in df.columns:
        return 0
    out = pd.DataFrame(index=df.index)
    out["company"] = _str_col(df, "company")
    out["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    emp_col = "employee_count" if "employee_count" in df.columns else ("employees" if "employees" in df.columns else None)
    if not emp_col:
        return 0
    out["employee_count"] = pd.to_numeric(df[emp_col], errors="coerce").astype("Int64")
    out = out.dropna(subset=["company", "year"])
    out["year"] = out["year"].astype(int)
    return upsert("company_employees", _records(out))


# ── registry: table → sync function ────────────────────────────────────
SYNCS: dict[str, Callable[[str], int]] = {
    "financial_metrics_yearly": sync_financial_metrics_yearly,
    "company_advertising_revenue": sync_company_advertising_revenue,
    "global_adv_aggregates": sync_global_adv_aggregates,
    "company_employees": sync_company_employees,
    "stock_yearly": sync_stock_yearly,
    "stock_daily": sync_stock_daily,
    "stock_minute": sync_stock_minute,
    "holders": sync_holders,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Google Sheet → Supabase")
    parser.add_argument(
        "--tables",
        default="",
        help="comma-separated table names (default: all). Available: " + ", ".join(SYNCS.keys()),
    )
    args = parser.parse_args()

    selected = [t.strip() for t in args.tables.split(",") if t.strip()] or list(SYNCS.keys())
    unknown = [t for t in selected if t not in SYNCS]
    if unknown:
        print(f"ERROR: unknown table(s): {unknown}")
        print(f"Available: {list(SYNCS.keys())}")
        sys.exit(1)

    print(f"Resolving workbook ...")
    workbook = resolve_financial_data_xlsx()
    if not workbook:
        print("ERROR: could not resolve workbook")
        sys.exit(1)
    print(f"Workbook: {workbook}")
    print(f"Supabase: {SUPABASE_URL}")
    print(f"Syncing {len(selected)} table(s):")

    grand_total = 0
    for table in selected:
        try:
            grand_total += SYNCS[table](workbook)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"  {table}: ERROR — {exc}")

    print(f"\nDone. {grand_total} rows upserted across {len(selected)} table(s).")


if __name__ == "__main__":
    main()
