#!/usr/bin/env python3
"""
Sync SQLite intelligence DB → Supabase.

Usage:
    python scripts/sync_sqlite_to_supabase.py          # sync all tables
    python scripts/sync_sqlite_to_supabase.py --table polymarket_snapshots  # sync one table

Requires .env with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import requests

# Load .env
_env_path = Path(__file__).resolve().parents[1] / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
DB_PATH = Path(__file__).resolve().parents[1] / "earningscall_intelligence.db"

BATCH_SIZE = 500  # PostgREST max rows per insert


def _headers() -> dict:
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",  # upsert
    }


def _clean_row(row: dict) -> dict:
    """Replace NaN/inf with None, strip null bytes from strings."""
    out = {}
    for k, v in row.items():
        if k == "id":
            continue  # let Supabase auto-generate
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            out[k] = None
        elif isinstance(v, str):
            out[k] = v.replace("\x00", "")  # strip null bytes
        else:
            out[k] = v
    return out


def _upsert_batch(table: str, rows: list[dict]) -> int:
    """POST rows to Supabase PostgREST. Returns rows inserted."""
    if not rows:
        return 0
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=_headers(),
        json=rows,
        timeout=60,
    )
    if resp.status_code in (200, 201):
        return len(rows)
    # 409 = conflict (already exists with merge-duplicates)
    if resp.status_code == 409:
        return 0
    print(f"  ERROR {resp.status_code}: {resp.text[:300]}")
    return 0


def sync_table(table: str, conn: sqlite3.Connection) -> int:
    """Read table from SQLite and upsert to Supabase in batches."""
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    except Exception as e:
        print(f"  Skip {table}: {e}")
        return 0

    if df.empty:
        print(f"  {table}: 0 rows (empty)")
        return 0

    rows = [_clean_row(r) for r in df.to_dict("records")]
    total = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        n = _upsert_batch(table, batch)
        total += n
        if n:
            print(f"  {table}: batch {i // BATCH_SIZE + 1} → {n} rows")

    print(f"  {table}: {total}/{len(rows)} synced")
    return total


# Tables to sync (order matters — transcripts before topics/kpis)
SYNC_ORDER = [
    "transcripts",
    "transcript_topics",
    "transcript_kpis",
    "transcript_highlights",
    "forward_signals",
    "polymarket_snapshots",
    "oracle_predictions",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", help="Sync only this table")
    args = parser.parse_args()

    if not SUPABASE_URL or not SERVICE_KEY:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)

    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found. Run scripts/build_intelligence_db.py first.")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    tables = [args.table] if args.table else SYNC_ORDER
    grand_total = 0
    for t in tables:
        n = sync_table(t, conn)
        grand_total += n

    conn.close()
    print(f"\nDone. Total rows synced: {grand_total}")


if __name__ == "__main__":
    main()
