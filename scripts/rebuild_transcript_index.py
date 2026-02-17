#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Tuple

import pandas as pd


TRANSCRIPT_FILE_RE = re.compile(r"^Q([1-4])\.txt$", re.IGNORECASE)


@dataclass(frozen=True)
class TranscriptKey:
    company: str
    year: int
    quarter: int


def normalize_company_name(folder_name: str) -> str:
    return folder_name.replace("_", " ").strip()


def parse_existing_index(index_path: Path) -> tuple[Dict[TranscriptKey, dict], Dict[str, tuple[str, str]]]:
    if not index_path.exists():
        return {}, {}

    df = pd.read_csv(index_path)
    records: Dict[TranscriptKey, dict] = {}
    defaults: Dict[str, tuple[str, str]] = {}
    if df.empty:
        return records, defaults

    for _, row in df.iterrows():
        company = str(row.get("company", "")).strip()
        year = pd.to_numeric(row.get("year"), errors="coerce")
        quarter = pd.to_numeric(row.get("quarter"), errors="coerce")
        if not company or pd.isna(year) or pd.isna(quarter):
            continue
        key = TranscriptKey(company=company, year=int(year), quarter=int(quarter))
        records[key] = row.to_dict()

        symbol = str(row.get("symbol", "")).strip()
        exchange = str(row.get("exchange", "")).strip()
        if company not in defaults and (symbol or exchange):
            defaults[company] = (symbol, exchange)

    return records, defaults


def count_text_metrics(file_path: Path) -> tuple[int, int]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    words = len(text.split())
    chars = len(text)
    return words, chars


def build_index(transcript_root: Path, repo_root: Path) -> pd.DataFrame:
    existing_index_path = transcript_root / "transcript_index.csv"
    existing_rows, company_defaults = parse_existing_index(existing_index_path)
    rows = []

    for company_dir in sorted([p for p in transcript_root.iterdir() if p.is_dir()]):
        company_display = normalize_company_name(company_dir.name)
        symbol, exchange = company_defaults.get(company_display, ("", ""))

        for year_dir in sorted([p for p in company_dir.iterdir() if p.is_dir()]):
            if not year_dir.name.isdigit():
                continue
            year = int(year_dir.name)

            for transcript_file in sorted([p for p in year_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt"]):
                match = TRANSCRIPT_FILE_RE.match(transcript_file.name)
                if not match:
                    continue
                quarter = int(match.group(1))
                word_count, char_count = count_text_metrics(transcript_file)
                rel_path = transcript_file.relative_to(repo_root).as_posix()

                key = TranscriptKey(company=company_display, year=year, quarter=quarter)
                existing = existing_rows.get(key, {})
                source_url = str(existing.get("source_url", "") or "").strip()
                status = "ok" if char_count > 0 else "empty"

                rows.append(
                    {
                        "company": company_display,
                        "symbol": symbol,
                        "exchange": exchange,
                        "year": year,
                        "quarter": quarter,
                        "source_url": source_url,
                        "file_path": rel_path,
                        "word_count": word_count,
                        "char_count": char_count,
                        "status": status,
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=[
                "company",
                "symbol",
                "exchange",
                "year",
                "quarter",
                "source_url",
                "file_path",
                "word_count",
                "char_count",
                "status",
            ]
        )

    df = pd.DataFrame(rows)
    return df.sort_values(["company", "year", "quarter"]).reset_index(drop=True)


def build_company_summary(index_df: pd.DataFrame) -> pd.DataFrame:
    if index_df.empty:
        return pd.DataFrame(
            columns=["company", "symbol", "exchange", "calls_found", "calls_extracted", "first_year", "last_year"]
        )

    grouped = (
        index_df.groupby(["company", "symbol", "exchange"], dropna=False)
        .agg(
            calls_found=("quarter", "count"),
            calls_extracted=("status", lambda s: int((s == "ok").sum())),
            first_year=("year", "min"),
            last_year=("year", "max"),
        )
        .reset_index()
        .sort_values("company")
    )
    return grouped


def build_coverage_gaps(index_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if index_df.empty:
        return pd.DataFrame(columns=["company", "year", "missing_quarters"])

    for company, g in index_df.groupby("company"):
        year_map = g.groupby("year")["quarter"].apply(lambda s: sorted(set(int(x) for x in s))).to_dict()
        if not year_map:
            continue
        for year in range(min(year_map), max(year_map) + 1):
            existing = set(year_map.get(year, []))
            missing = [q for q in [1, 2, 3, 4] if q not in existing]
            if missing:
                rows.append(
                    {
                        "company": company,
                        "year": year,
                        "missing_quarters": ",".join(f"Q{q}" for q in missing),
                    }
                )
    return pd.DataFrame(rows).sort_values(["company", "year"]).reset_index(drop=True) if rows else pd.DataFrame(
        columns=["company", "year", "missing_quarters"]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild transcript index from earningscall_transcripts folder")
    parser.add_argument(
        "--root",
        default="earningscall_transcripts",
        help="Transcript root folder (default: earningscall_transcripts)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    transcript_root = (repo_root / args.root).resolve()
    if not transcript_root.exists():
        raise SystemExit(f"Transcript folder not found: {transcript_root}")

    index_df = build_index(transcript_root=transcript_root, repo_root=repo_root)
    summary_df = build_company_summary(index_df)
    gaps_df = build_coverage_gaps(index_df)

    (transcript_root / "transcript_index.csv").write_text("", encoding="utf-8")
    index_df.to_csv(transcript_root / "transcript_index.csv", index=False)
    summary_df.to_csv(transcript_root / "company_summary.csv", index=False)
    gaps_df.to_csv(transcript_root / "coverage_gaps.csv", index=False)

    print(f"Indexed transcripts: {len(index_df)}")
    print(f"Companies: {index_df['company'].nunique() if not index_df.empty else 0}")
    print(f"Wrote: {transcript_root / 'transcript_index.csv'}")
    print(f"Wrote: {transcript_root / 'company_summary.csv'}")
    print(f"Wrote: {transcript_root / 'coverage_gaps.csv'}")


if __name__ == "__main__":
    main()
