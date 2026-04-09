#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Oracle prediction snapshot from local workbook + transcript assets")
    parser.add_argument("--db", default="earningscall_intelligence.db", help="SQLite DB path")
    parser.add_argument(
        "--no-polymarket",
        action="store_true",
        help="Skip live Polymarket enrichment and use workbook price momentum only",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    app_dir = repo_root / "app"
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    from utils.oracle_engine import get_oracle_snapshot, persist_oracle_snapshot  # noqa: WPS433

    snapshot = get_oracle_snapshot(use_polymarket=not args.no_polymarket, persist=False)
    db_path = persist_oracle_snapshot(snapshot, db_path=(repo_root / args.db).resolve())

    metadata = snapshot.get("metadata", {})
    predictions = snapshot.get("predictions")
    factors = snapshot.get("factors")

    print(f"Database: {db_path}")
    print(f"As of date: {metadata.get('as_of_date', '')}")
    print(f"Workbook: {metadata.get('workbook_path', '')}")
    print(f"Signals source: {metadata.get('signals_path', '')}")
    print(f"Signal rows: {metadata.get('signal_rows', 0)}")
    print(f"Polymarket enabled: {metadata.get('use_polymarket', False)}")
    print(f"Polymarket rows: {metadata.get('polymarket_rows', 0)}")
    print(f"Prediction rows: {int(predictions.shape[0]) if predictions is not None else 0}")
    print(f"Factor rows: {int(factors.shape[0]) if factors is not None else 0}")


if __name__ == "__main__":
    main()
