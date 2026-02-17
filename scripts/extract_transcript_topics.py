#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import Dict, Iterable

import numpy as np
import pandas as pd


TRANSCRIPT_FILE_RE = re.compile(r"^Q([1-4])\.txt$", re.IGNORECASE)

TOPIC_KEYWORDS: Dict[str, list[str]] = {
    "AI": [
        " ai ",
        "artificial intelligence",
        "generative ai",
        "gen ai",
        "llm",
        "language model",
        "model training",
        "inference",
        "automation",
    ],
    "Advertising": [
        "advertising",
        "advertiser",
        "ad spend",
        "ad revenue",
        "ad market",
        "impression",
        "cpm",
        "cpc",
        "ad tech",
    ],
    "Cost optimization": [
        "cost optimization",
        "cost savings",
        "efficiency",
        "productivity",
        "opex",
        "operating expenses",
        "headcount",
        "restructuring",
        "margin expansion",
    ],
    "Inflation": [
        "inflation",
        "interest rates",
        "rate environment",
        "macro conditions",
        "macroeconomic",
        "consumer pressure",
        "pricing pressure",
    ],
    "Supply chain": [
        "supply chain",
        "inventory",
        "logistics",
        "shipping",
        "lead time",
        "procurement",
        "component",
    ],
    "Guidance": [
        "guidance",
        "outlook",
        "we expect",
        "we project",
        "forecast",
        "next quarter",
        "full year",
        "fiscal year",
    ],
    "Segment performance": [
        "segment",
        "services",
        "streaming",
        "subscription",
        "market share",
        "operating income",
        "gross margin",
        "revenue growth",
    ],
    "Geopolitical uncertainty": [
        "geopolitical",
        "war",
        "middle east",
        "election",
        "government shutdown",
        "tariff",
        "regulation",
        "china",
    ],
    "Sustainability": [
        "sustainability",
        "carbon",
        "emissions",
        "renewable",
        "climate",
        "energy efficiency",
        "carbon neutral",
    ],
}

SPEAKER_RE = re.compile(r"^([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){0,4})\s+")


def normalize_company_name(folder_name: str) -> str:
    return folder_name.replace("_", " ").strip()


def split_sentences(text: str) -> Iterable[str]:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        cleaned = sentence.strip()
        if len(cleaned) >= 25:
            yield cleaned


def detect_topics(sentence_lower: str) -> list[str]:
    padded = f" {sentence_lower} "
    hits = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in padded for keyword in keywords):
            hits.append(topic)
    return hits


def extract_rows_from_file(file_path: Path, repo_root: Path) -> list[dict]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    if "---" in text:
        _, body = text.split("---", 1)
    else:
        body = text

    company = normalize_company_name(file_path.parents[1].name)
    year = int(file_path.parents[0].name)
    quarter = int(TRANSCRIPT_FILE_RE.match(file_path.name).group(1))
    rel_path = file_path.relative_to(repo_root).as_posix()

    rows = []
    for block in re.split(r"\n\s*\n+", body):
        block = " ".join(block.strip().split())
        if len(block) < 25:
            continue

        speaker_match = SPEAKER_RE.match(block)
        speaker = speaker_match.group(1) if speaker_match else "Unknown"
        text_body = block[speaker_match.end() :].strip() if speaker_match else block
        if len(text_body) < 20:
            continue

        for sentence in split_sentences(text_body):
            sentence_lower = sentence.lower()
            topics = detect_topics(sentence_lower)
            if not topics:
                continue
            snippet = sentence[:480]
            for topic in topics:
                rows.append(
                    {
                        "company": company,
                        "year": year,
                        "quarter": quarter,
                        "topic": topic,
                        "text": snippet,
                        "speaker": speaker,
                        "file_path": rel_path,
                    }
                )
    return rows


def build_topics_df(transcript_root: Path, repo_root: Path) -> pd.DataFrame:
    rows = []
    for company_dir in sorted([p for p in transcript_root.iterdir() if p.is_dir()]):
        for year_dir in sorted([p for p in company_dir.iterdir() if p.is_dir() and p.name.isdigit()]):
            for q_file in sorted([p for p in year_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt"]):
                if not TRANSCRIPT_FILE_RE.match(q_file.name):
                    continue
                rows.extend(extract_rows_from_file(q_file, repo_root))

    if not rows:
        return pd.DataFrame(columns=["company", "year", "quarter", "topic", "text", "speaker", "file_path"])
    df = pd.DataFrame(rows)
    return df.sort_values(["company", "year", "quarter", "topic"]).reset_index(drop=True)


def build_metrics_df(topics_df: pd.DataFrame, transcript_index_df: pd.DataFrame) -> pd.DataFrame:
    if topics_df.empty:
        return pd.DataFrame(
            columns=[
                "year",
                "quarter",
                "topic",
                "mention_count",
                "companies_mentioned",
                "total_companies",
                "importance_pct",
                "growth_pct",
            ]
        )

    totals = (
        transcript_index_df.groupby(["year", "quarter"])["company"]
        .nunique()
        .reset_index(name="total_companies")
    )
    grouped = (
        topics_df.groupby(["year", "quarter", "topic"], as_index=False)
        .agg(
            mention_count=("text", "count"),
            companies_mentioned=("company", "nunique"),
        )
    )
    metrics = grouped.merge(totals, on=["year", "quarter"], how="left")
    metrics["total_companies"] = metrics["total_companies"].replace(0, np.nan)
    metrics["importance_pct"] = (metrics["companies_mentioned"] / metrics["total_companies"]) * 100.0
    metrics["importance_pct"] = metrics["importance_pct"].fillna(0.0)

    metrics = metrics.sort_values(["topic", "year", "quarter"]).reset_index(drop=True)
    metrics["period_idx"] = metrics["year"] * 4 + metrics["quarter"]
    metrics["growth_pct"] = np.nan

    for topic, g in metrics.groupby("topic"):
        prev_count = None
        for idx in g.index:
            current_count = float(metrics.at[idx, "mention_count"])
            if prev_count is None:
                growth = np.nan
            elif prev_count <= 0 and current_count > 0:
                growth = 200.0
            elif prev_count <= 0 and current_count <= 0:
                growth = 0.0
            else:
                growth = ((current_count - prev_count) / prev_count) * 100.0
            metrics.at[idx, "growth_pct"] = growth
            prev_count = current_count

    metrics["growth_pct"] = metrics["growth_pct"].fillna(0.0).clip(lower=-100.0, upper=200.0)
    return metrics.drop(columns=["period_idx"]).sort_values(["year", "quarter", "topic"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract topic rows and quarterly topic metrics from raw transcripts")
    parser.add_argument("--root", default="earningscall_transcripts", help="Transcript folder (default: earningscall_transcripts)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    transcript_root = (repo_root / args.root).resolve()
    if not transcript_root.exists():
        raise SystemExit(f"Transcript folder not found: {transcript_root}")

    index_path = transcript_root / "transcript_index.csv"
    if not index_path.exists():
        raise SystemExit("transcript_index.csv not found. Run scripts/rebuild_transcript_index.py first.")
    transcript_index_df = pd.read_csv(index_path)
    transcript_index_df["company"] = transcript_index_df["company"].astype(str).str.strip()
    transcript_index_df["year"] = pd.to_numeric(transcript_index_df["year"], errors="coerce").astype("Int64")
    transcript_index_df["quarter"] = pd.to_numeric(transcript_index_df["quarter"], errors="coerce").astype("Int64")
    transcript_index_df = transcript_index_df.dropna(subset=["year", "quarter"]).copy()
    transcript_index_df["year"] = transcript_index_df["year"].astype(int)
    transcript_index_df["quarter"] = transcript_index_df["quarter"].astype(int)

    topics_df = build_topics_df(transcript_root=transcript_root, repo_root=repo_root)
    metrics_df = build_metrics_df(topics_df=topics_df, transcript_index_df=transcript_index_df)

    topics_out = transcript_root / "transcript_topics.csv"
    metrics_out = transcript_root / "topic_metrics.csv"
    topics_df.to_csv(topics_out, index=False)
    metrics_df.to_csv(metrics_out, index=False)

    print(f"Wrote: {topics_out} ({len(topics_df)} rows)")
    print(f"Wrote: {metrics_out} ({len(metrics_df)} rows)")


if __name__ == "__main__":
    main()
