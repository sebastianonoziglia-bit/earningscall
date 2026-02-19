#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def run_step(label: str, cmd: list[str], cwd: Path) -> None:
    print(f"\n[{label}] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Master pipeline: rebuild transcript index, extract topics/KPIs/highlights, "
            "build SQLite intelligence DB, sync company metrics, and generate insights"
        )
    )
    parser.add_argument("--db", default="earningscall_intelligence.db", help="SQLite DB path")
    parser.add_argument("--root", default="earningscall_transcripts", help="Transcript folder root")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    py = sys.executable

    print("🚀 Starting Earningscall Intelligence Pipeline...")
    run_step("1/7 Rebuild transcript index", [py, "scripts/rebuild_transcript_index.py", "--root", args.root], repo_root)
    run_step("2/7 Extract topics + metrics", [py, "scripts/extract_transcript_topics.py", "--root", args.root], repo_root)
    run_step("3/7 Extract KPI values", [py, "scripts/extract_kpi_values.py", "--root", args.root], repo_root)
    run_step("4/7 Extract transcript highlights", [py, "scripts/extract_transcript_highlights_from_sheet.py", "--out-dir", args.root], repo_root)
    run_step("5/7 Build intelligence DB", [py, "scripts/build_intelligence_db.py", "--db", args.db, "--root", args.root], repo_root)
    run_step("6/7 Sync workbook metrics to SQL", [py, "scripts/sync_gsheet_to_sql.py", "--db", args.db], repo_root)
    run_step("7/7 Generate summary insights", [py, "scripts/generate_insights.py", "--db", args.db], repo_root)

    print("\n✅ Pipeline complete!")


if __name__ == "__main__":
    main()
