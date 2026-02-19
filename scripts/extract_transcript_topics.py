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
        "agentic",
        "multimodal",
        "foundation model",
        "copilot",
        "assistant",
        "ai inference",
        "ai training",
        "machine learning",
        "ml model",
        "automation",
        "autonomous",
        "llm",
        "language model",
        "model training",
        "inference",
    ],
    "Advertising": [
        "advertising",
        "advertiser",
        "ad load",
        "ad spend",
        "ad revenue",
        "ad market",
        "impression",
        "impressions",
        "click-through",
        "ctr",
        "conversion",
        "attribution",
        "targeting",
        "reach",
        "frequency",
        "programmatic",
        "auction",
        "performance marketing",
        "brand advertising",
        "search ads",
        "video ads",
        "retail media",
        "measurement",
        "cpm",
        "cpc",
        "ad tech",
    ],
    "Cost optimization": [
        "cost optimization",
        "cost savings",
        "efficiency",
        "leaner",
        "streamlining",
        "discipline",
        "cost discipline",
        "expense control",
        "rightsizing",
        "optimization",
        "productivity gains",
        "productivity",
        "opex",
        "operating expenses",
        "headcount",
        "layoff",
        "layoffs",
        "reduction in force",
        "restructuring charges",
        "restructuring",
        "margin expansion",
        "profit improvement",
    ],
    "Inflation": [
        "inflation",
        "disinflation",
        "deflation",
        "price pressure",
        "input costs",
        "cost inflation",
        "wage inflation",
        "interest rates",
        "rate cuts",
        "higher for longer",
        "consumer slowdown",
        "rate environment",
        "macro conditions",
        "macroeconomic",
        "consumer pressure",
        "pricing pressure",
    ],
    "Supply chain": [
        "supply chain",
        "component shortages",
        "component supply",
        "factory utilization",
        "fulfillment",
        "freight",
        "port congestion",
        "semiconductor",
        "chips",
        "manufacturing",
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
        "guiding",
        "guidance range",
        "raised guidance",
        "lowered guidance",
        "full-year",
        "next fiscal year",
        "first half",
        "second half",
        "next quarter",
        "full year",
        "fiscal year",
    ],
    "Segment performance": [
        "segment",
        "segment margin",
        "segment profit",
        "mix shift",
        "attach rate",
        "retention",
        "churn",
        "engagement",
        "active users",
        "monthly active users",
        "daily active users",
        "arpu",
        "lifetime value",
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
        "ukraine",
        "russia",
        "taiwan",
        "middle-east",
        "middle east",
        "election",
        "government shutdown",
        "trade restrictions",
        "export controls",
        "sanctions",
        "tariffs",
        "tariff",
        "regulation",
        "china",
    ],
    "Sustainability": [
        "sustainability",
        "carbon",
        "emissions",
        "scope 1",
        "scope 2",
        "scope 3",
        "decarbonization",
        "net zero",
        "energy transition",
        "renewables",
        "power purchase agreement",
        "water usage",
        "renewable",
        "climate",
        "energy efficiency",
        "carbon neutral",
    ],
    "Cloud & infrastructure": [
        "cloud",
        "azure",
        "aws",
        "google cloud",
        "data center",
        "datacenter",
        "infrastructure",
        "compute",
        "storage",
        "network capacity",
        "gpu",
        "server",
        "cluster",
        "latency",
        "throughput",
        "uptime",
    ],
    "Regulation & legal": [
        "regulatory",
        "regulation",
        "antitrust",
        "litigation",
        "lawsuit",
        "settlement",
        "compliance",
        "eu act",
        "dma",
        "dsa",
        "doj",
        "ftc",
        "court ruling",
    ],
    "Consumer demand": [
        "consumer demand",
        "soft demand",
        "demand trends",
        "spending patterns",
        "consumer confidence",
        "traffic",
        "units sold",
        "sell-through",
        "same-store",
        "promotional activity",
        "basket size",
    ],
    "Pricing & monetization": [
        "pricing",
        "price increase",
        "price point",
        "monetization",
        "upsell",
        "cross-sell",
        "yield",
        "take rate",
        "subscription price",
        "bundle",
        "ad tier",
    ],
    "Security & privacy": [
        "security",
        "cybersecurity",
        "privacy",
        "trust and safety",
        "data protection",
        "breach",
        "identity",
        "encryption",
        "threat",
        "fraud",
        "abuse",
    ],
    "Capital allocation": [
        "capital allocation",
        "share repurchase",
        "buyback",
        "dividend",
        "free cash flow",
        "capex",
        "capital expenditures",
        "balance sheet",
        "debt paydown",
        "leverage",
        "acquisition",
        "merger",
        "m&a",
    ],
    "Financial Health": [
        "revenue growth",
        "margin expansion",
        "profitability",
        "cash flow",
        "free cash flow",
        "earnings",
        "operating leverage",
        "gross margin",
    ],
    "Debt & Leverage": [
        "debt",
        "leverage",
        "refinancing",
        "credit facility",
        "interest expense",
        "net debt",
        "deleveraging",
    ],
    "Competition": [
        "competitive",
        "competition",
        "market share",
        "competitors",
        "differentiation",
        "pricing pressure",
    ],
    "Regulatory": [
        "regulation",
        "compliance",
        "policy",
        "antitrust",
        "privacy",
        "legal",
        "regulator",
    ],
    "Innovation": [
        "innovation",
        "new product",
        "r&d",
        "patent",
        "technology",
        "breakthrough",
        "roadmap",
    ],
    "Market Expansion": [
        "expansion",
        "international",
        "new market",
        "geographic",
        "emerging market",
        "global footprint",
    ],
    "Customer Metrics": [
        "subscribers",
        "users",
        "churn",
        "retention",
        "engagement",
        "arpu",
        "mau",
        "dau",
    ],
    "M&A Activity": [
        "acquisition",
        "acquire",
        "merger",
        "divestiture",
        "partnership",
        "joint venture",
    ],
}

KPI_PATTERNS: Dict[str, str] = {
    "Revenue": r"(?:revenue|sales).*?(\$?\d+(?:\.\d+)?\s*(?:trillion|billion|million|thousand|B|M|K))",
    "Operating Income": r"(?:operating income|operating profit).*?(\$?\d+(?:\.\d+)?\s*(?:trillion|billion|million|thousand|B|M|K))",
    "Net Income": r"(?:net income|net earnings).*?(\$?\d+(?:\.\d+)?\s*(?:trillion|billion|million|thousand|B|M|K))",
    "EPS": r"(?:earnings per share|EPS)\D{0,25}(\$?\d+(?:\.\d+)?)",
    "Margin": r"(?:operating\s+|gross\s+|net\s+)?margin\D{0,25}(\d+(?:\.\d+)?%)",
    "Debt": r"(?:debt|net debt)\D{0,35}(\$?\d+(?:\.\d+)?\s*(?:trillion|billion|million|thousand|B|M|K))",
    "Cash": r"(?:cash(?:\s+balance)?|cash and equivalents|cash position)\D{0,35}(\$?\d+(?:\.\d+)?\s*(?:trillion|billion|million|thousand|B|M|K))",
    "CapEx": r"(?:capital expenditure|capital expenditures|capex)\D{0,35}(\$?\d+(?:\.\d+)?\s*(?:trillion|billion|million|thousand|B|M|K))",
    "Subscribers": r"subscribers?\D{0,25}(\d+(?:\.\d+)?\s*(?:million|billion|M|B))",
    "Users": r"(?:monthly active users|mau|daily active users|dau|active users?)\D{0,30}(\d+(?:\.\d+)?\s*(?:million|billion|M|B))",
    "ARPU": r"(?:ARPU|average revenue per user)\D{0,25}(\$?\d+(?:\.\d+)?)",
    "YoY Growth": r"(?:year over year|YoY)\D{0,35}(?:grew|growth|increased|up)?\D{0,20}(\d+(?:\.\d+)?%)",
    "QoQ Growth": r"(?:quarter over quarter|QoQ)\D{0,35}(?:grew|growth|increased|up)?\D{0,20}(\d+(?:\.\d+)?%)",
}


def _compile_topic_patterns(topic_keywords: Dict[str, list[str]]) -> Dict[str, list[re.Pattern[str]]]:
    compiled: Dict[str, list[re.Pattern[str]]] = {}
    for topic, keywords in topic_keywords.items():
        patterns: list[re.Pattern[str]] = []
        for keyword in keywords:
            term = str(keyword or "").strip().lower()
            if not term:
                continue
            pattern = re.escape(term).replace(r"\ ", r"\s+")
            if term[0].isalnum():
                pattern = r"(?<![a-z0-9])" + pattern
            if term[-1].isalnum():
                pattern = pattern + r"(?![a-z0-9])"
            patterns.append(re.compile(pattern, flags=re.IGNORECASE))
        compiled[topic] = patterns
    return compiled


def _compile_kpi_patterns(patterns: Dict[str, str]) -> Dict[str, re.Pattern[str]]:
    return {kpi: re.compile(pattern, flags=re.IGNORECASE) for kpi, pattern in patterns.items()}


TOPIC_PATTERNS = _compile_topic_patterns(TOPIC_KEYWORDS)
KPI_REGEX = _compile_kpi_patterns(KPI_PATTERNS)

SPEAKER_RE = re.compile(r"^([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){0,4})\s+")
VALUE_RE = re.compile(r"(\$)?\s*(\d+(?:\.\d+)?)\s*(trillion|billion|million|thousand|bn|mn|b|m|k|%)?", re.IGNORECASE)


def normalize_company_name(folder_name: str) -> str:
    return folder_name.replace("_", " ").strip()


def split_sentences(text: str) -> Iterable[str]:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        cleaned = sentence.strip()
        if len(cleaned) >= 25:
            yield cleaned


def detect_topics(sentence_lower: str) -> list[str]:
    hits = []
    for topic, patterns in TOPIC_PATTERNS.items():
        if any(pattern.search(sentence_lower) for pattern in patterns):
            hits.append(topic)
    return hits


def _parse_value_numeric(value_text: str) -> tuple[float | None, str]:
    text = str(value_text or "").strip()
    if not text:
        return None, ""
    match = VALUE_RE.search(text)
    if not match:
        return None, ""

    number = float(match.group(2))
    raw_unit = str(match.group(3) or "").strip().lower()
    if raw_unit == "%":
        return number, "%"

    multipliers = {
        "trillion": 1_000_000_000_000.0,
        "billion": 1_000_000_000.0,
        "million": 1_000_000.0,
        "thousand": 1_000.0,
        "bn": 1_000_000_000.0,
        "mn": 1_000_000.0,
        "b": 1_000_000_000.0,
        "m": 1_000_000.0,
        "k": 1_000.0,
    }
    if raw_unit in multipliers:
        return number * multipliers[raw_unit], raw_unit
    return number, raw_unit


def _estimate_confidence(sentence: str, value_text: str) -> float:
    score = 0.55
    if "$" in str(value_text):
        score += 0.1
    if any(unit in str(value_text).lower() for unit in ["billion", "million", "trillion", "%", " b", " m"]):
        score += 0.12
    if len(sentence) > 80:
        score += 0.08
    if any(token in sentence.lower() for token in ["guidance", "reported", "reached", "was", "were"]):
        score += 0.06
    return float(max(0.0, min(score, 0.98)))


def extract_rows_from_file(file_path: Path, repo_root: Path) -> tuple[list[dict], list[dict]]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    if "---" in text:
        _, body = text.split("---", 1)
    else:
        body = text

    company = normalize_company_name(file_path.parents[1].name)
    year = int(file_path.parents[0].name)
    quarter = int(TRANSCRIPT_FILE_RE.match(file_path.name).group(1))
    rel_path = file_path.relative_to(repo_root).as_posix()

    topic_rows: list[dict] = []
    kpi_rows: list[dict] = []

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
            snippet = sentence[:480]

            if topics:
                for topic in topics:
                    topic_rows.append(
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

            seen_kpis: set[tuple[str, str]] = set()
            for kpi_type, regex in KPI_REGEX.items():
                for match in regex.finditer(sentence):
                    value_text = str(match.group(1) or "").strip()
                    if not value_text:
                        continue
                    dedupe_key = (kpi_type, value_text.lower())
                    if dedupe_key in seen_kpis:
                        continue
                    seen_kpis.add(dedupe_key)

                    value_numeric, unit = _parse_value_numeric(value_text)
                    kpi_rows.append(
                        {
                            "company": company,
                            "year": year,
                            "quarter": quarter,
                            "kpi_type": kpi_type,
                            "value_text": value_text,
                            "value_numeric": value_numeric,
                            "unit": unit,
                            "context_sentence": snippet,
                            "speaker": speaker,
                            "file_path": rel_path,
                            "confidence": _estimate_confidence(sentence, value_text),
                        }
                    )

    return topic_rows, kpi_rows


def build_topics_and_kpis_df(transcript_root: Path, repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    topic_rows: list[dict] = []
    kpi_rows: list[dict] = []

    for company_dir in sorted([p for p in transcript_root.iterdir() if p.is_dir()]):
        for year_dir in sorted([p for p in company_dir.iterdir() if p.is_dir() and p.name.isdigit()]):
            for q_file in sorted([p for p in year_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt"]):
                if not TRANSCRIPT_FILE_RE.match(q_file.name):
                    continue
                file_topics, file_kpis = extract_rows_from_file(q_file, repo_root)
                topic_rows.extend(file_topics)
                kpi_rows.extend(file_kpis)

    topics_df = pd.DataFrame(topic_rows)
    if topics_df.empty:
        topics_df = pd.DataFrame(columns=["company", "year", "quarter", "topic", "text", "speaker", "file_path"])
    else:
        topics_df = topics_df.sort_values(["company", "year", "quarter", "topic"]).reset_index(drop=True)

    kpis_df = pd.DataFrame(kpi_rows)
    if kpis_df.empty:
        kpis_df = pd.DataFrame(
            columns=[
                "company",
                "year",
                "quarter",
                "kpi_type",
                "value_text",
                "value_numeric",
                "unit",
                "context_sentence",
                "speaker",
                "file_path",
                "confidence",
            ]
        )
    else:
        kpis_df["value_numeric"] = pd.to_numeric(kpis_df["value_numeric"], errors="coerce")
        kpis_df["confidence"] = pd.to_numeric(kpis_df["confidence"], errors="coerce")
        kpis_df = kpis_df.sort_values(["company", "year", "quarter", "kpi_type", "confidence"], ascending=[True, True, True, True, False]).reset_index(drop=True)

    return topics_df, kpis_df


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

    for _topic, group_df in metrics.groupby("topic"):
        prev_count = None
        for idx in group_df.index:
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
    parser = argparse.ArgumentParser(
        description="Extract topic rows, KPI mentions, and quarterly topic metrics from raw transcripts"
    )
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

    topics_df, kpis_df = build_topics_and_kpis_df(transcript_root=transcript_root, repo_root=repo_root)
    metrics_df = build_metrics_df(topics_df=topics_df, transcript_index_df=transcript_index_df)

    topics_out = transcript_root / "transcript_topics.csv"
    metrics_out = transcript_root / "topic_metrics.csv"
    kpis_out = transcript_root / "transcript_kpis.csv"
    topics_df.to_csv(topics_out, index=False)
    metrics_df.to_csv(metrics_out, index=False)
    kpis_df.to_csv(kpis_out, index=False)

    print(f"Wrote: {topics_out} ({len(topics_df)} rows)")
    print(f"Wrote: {metrics_out} ({len(metrics_df)} rows)")
    print(f"Wrote: {kpis_out} ({len(kpis_df)} rows)")


if __name__ == "__main__":
    main()
