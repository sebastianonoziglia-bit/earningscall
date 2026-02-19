#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd



def main() -> None:
    parser = argparse.ArgumentParser(description="Extract KPI mentions from transcript text into transcript_kpis.csv")
    parser.add_argument("--root", default="earningscall_transcripts", help="Transcript folder (default: earningscall_transcripts)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    from extract_transcript_topics import build_topics_and_kpis_df  # noqa: WPS433

    transcript_root = (repo_root / args.root).resolve()
    if not transcript_root.exists():
        raise SystemExit(f"Transcript folder not found: {transcript_root}")

    _topics_df, kpis_df = build_topics_and_kpis_df(transcript_root=transcript_root, repo_root=repo_root)
    if kpis_df is None:
        kpis_df = pd.DataFrame()

    out_path = transcript_root / "transcript_kpis.csv"
    kpis_df.to_csv(out_path, index=False)
    print(f"Wrote: {out_path} ({len(kpis_df)} rows)")


if __name__ == "__main__":
    main()
