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


# ── Supabase upsert ────────────────────────────────────────────────────
def upsert(table: str, rows: list[dict[str, Any]], batch_size: int = 500) -> int:
    if not rows:
        print(f"  {table}: no rows")
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
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
def sync_stock_daily(workbook: str) -> int:
    df = _read_sheet(workbook, "Daily")
    if df.empty:
        return 0
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df.get("date"), errors="coerce").dt.strftime("%Y-%m-%d")
    out["asset"] = df.get("asset").astype(str).str.strip() if "asset" in df.columns else None
    out["tag"] = df.get("tag", "").astype(str).str.strip() if "tag" in df.columns else ""
    out["price"] = pd.to_numeric(df.get("close", df.get("price")), errors="coerce")
    out["open"] = pd.to_numeric(df.get("open"), errors="coerce")
    out["high"] = pd.to_numeric(df.get("high"), errors="coerce")
    out["low"] = pd.to_numeric(df.get("low"), errors="coerce")
    out["volume"] = pd.to_numeric(df.get("volume"), errors="coerce")
    out["change_pct"] = pd.to_numeric(df.get("change_pct"), errors="coerce")
    out["market_cap"] = pd.to_numeric(df.get("market_cap"), errors="coerce")
    out["currency"] = df.get("currency", "USD").astype(str) if "currency" in df.columns else "USD"
    out = out.dropna(subset=["date", "asset"])
    out = out.drop_duplicates(subset=["date", "asset", "tag"], keep="last")
    return upsert("stock_daily", _records(out))


def sync_stock_minute(workbook: str) -> int:
    df = _read_sheet(workbook, "Minute")
    if df.empty:
        return 0
    out = pd.DataFrame()
    out["ts"] = pd.to_datetime(df.get("date"), errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
    out["asset"] = df.get("asset").astype(str).str.strip() if "asset" in df.columns else None
    out["tag"] = df.get("tag", "").astype(str).str.strip() if "tag" in df.columns else ""
    out["price"] = pd.to_numeric(df.get("close", df.get("price")), errors="coerce")
    out["open"] = pd.to_numeric(df.get("open"), errors="coerce")
    out["high"] = pd.to_numeric(df.get("high"), errors="coerce")
    out["low"] = pd.to_numeric(df.get("low"), errors="coerce")
    out["volume"] = pd.to_numeric(df.get("volume"), errors="coerce")
    out["change_pct"] = pd.to_numeric(df.get("change_pct"), errors="coerce")
    out["market_cap"] = pd.to_numeric(df.get("market_cap"), errors="coerce")
    out["currency"] = df.get("currency", "USD").astype(str) if "currency" in df.columns else "USD"
    out = out.dropna(subset=["ts", "asset"])
    out = out.drop_duplicates(subset=["ts", "asset", "tag"], keep="last")
    return upsert("stock_minute", _records(out))


def sync_stock_yearly(workbook: str) -> int:
    df = _read_sheet(workbook, "Stocks & Crypto")
    if df.empty:
        df = _read_sheet(workbook, "Stocks and Crypto")
    if df.empty:
        return 0
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df.get("date"), errors="coerce").dt.strftime("%Y-%m-%d")
    out["asset"] = df.get("asset").astype(str).str.strip() if "asset" in df.columns else None
    out["tag"] = df.get("tag", "").astype(str).str.strip() if "tag" in df.columns else ""
    out["price"] = pd.to_numeric(df.get("close", df.get("price")), errors="coerce")
    out["open"] = pd.to_numeric(df.get("open"), errors="coerce")
    out["high"] = pd.to_numeric(df.get("high"), errors="coerce")
    out["low"] = pd.to_numeric(df.get("low"), errors="coerce")
    out["volume"] = pd.to_numeric(df.get("volume"), errors="coerce")
    out["change_pct"] = pd.to_numeric(df.get("change_pct"), errors="coerce")
    out["market_cap"] = pd.to_numeric(df.get("market_cap"), errors="coerce")
    out["currency"] = df.get("currency", "USD").astype(str) if "currency" in df.columns else "USD"
    out = out.dropna(subset=["date", "asset"])
    out = out.drop_duplicates(subset=["date", "asset", "tag"], keep="last")
    return upsert("stock_yearly", _records(out))


def sync_holders(workbook: str) -> int:
    df = _read_sheet(workbook, "Holders")
    if df.empty:
        return 0
    out = pd.DataFrame()
    out["date_fetched"] = pd.to_datetime(df.get("date_fetched"), errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
    out["company"] = df.get("company").astype(str).str.strip() if "company" in df.columns else None
    out["ticker"] = df.get("ticker").astype(str).str.strip() if "ticker" in df.columns else None
    out["holder_name"] = df.get("holder_name").astype(str).str.strip() if "holder_name" in df.columns else None
    out["shares"] = pd.to_numeric(df.get("shares"), errors="coerce")
    out["value_usd"] = pd.to_numeric(df.get("value_usd"), errors="coerce")
    out["pct_out"] = pd.to_numeric(df.get("pct_out"), errors="coerce")
    out["holder_type"] = df.get("holder_type").astype(str) if "holder_type" in df.columns else None
    out = out.dropna(subset=["company", "holder_name", "date_fetched"])
    return upsert("holders", _records(out))


def sync_financial_metrics_yearly(workbook: str) -> int:
    df = _read_sheet(workbook, "Company_metrics_earnings_values")
    if df.empty:
        return 0
    if "company" not in df.columns or "year" not in df.columns:
        print("  financial_metrics_yearly: missing required columns")
        return 0
    out = pd.DataFrame()
    out["company"] = df["company"].astype(str).str.strip()
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
    out = pd.DataFrame()
    out["metric_type"] = df[metric_col].astype(str).str.replace(" Worldwide", "", regex=False).str.strip()
    out["year"] = pd.to_numeric(df[year_col], errors="coerce").astype("Int64")
    out["value"] = pd.to_numeric(df[value_col], errors="coerce")
    out = out.dropna(subset=["metric_type", "year"])
    out["year"] = out["year"].astype(int)
    return upsert("global_adv_aggregates", _records(out))


def sync_company_employees(workbook: str) -> int:
    df = _read_sheet(workbook, "Company_Employees")
    if df.empty or "company" not in df.columns or "year" not in df.columns:
        return 0
    out = pd.DataFrame()
    out["company"] = df["company"].astype(str).str.strip()
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
