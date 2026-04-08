#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import re
from typing import Dict, Iterable

import numpy as np
import pandas as pd

# ── Make scoring_config importable from app/utils ────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_APP_DIR = _REPO_ROOT / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from utils.scoring_config import (
    FINANCIAL_SCORE_TERMS as _CFG_FIN_TERMS,
    FUTURE_TENSE_MARKERS as _CFG_FUTURE,
    NEGATION_PREFIXES as _CFG_NEGATION,
    BOILERPLATE_PHRASES as _CFG_BOILERPLATE,
    LAYER_WEIGHTS as _CFG_WEIGHTS,
    THRESHOLDS as _CFG_THRESHOLDS,
    CATEGORY_KEYWORDS as _CFG_CATEGORY_KW,
    SIGNAL_CATEGORIES as _CFG_SIGNAL_CATS,
)


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
    # Additional topics — also feed into Genie context and automated company insights
    "Streaming & CTV": [
        "connected tv", "ctv", "streaming wars", "ad tier",
        "password sharing", "live sports", "sports rights",
        "nfl", "nba", "premier league", "live events",
        "streaming rights", "linear tv",
    ],
    "Creator Economy": [
        "creator economy", "short form video", "reels", "shorts",
        "podcast advertising", "creator monetization", "influencer",
        "user generated content", "ugc",
    ],
    "Retail Media": [
        "retail media", "first party data", "shopper data",
        "commerce media", "retail ad network", "sponsored products",
    ],
    "Shareholder Returns": [
        "share buyback", "dividend", "debt reduction",
        "free cash flow", "capital return", "share repurchase",
    ],
    "Subscriber Growth": [
        "subscription growth", "churn", "average revenue per user",
        "arpu", "subscriber additions", "paid members",
        "premium subscribers",
    ],
    "International": [
        "international expansion", "emerging markets",
        "new geographies", "apac", "emea", "latin america",
    ],
    "Regulation & Privacy": [
        "regulation", "antitrust", "privacy", "cookie deprecation",
        "gdpr", "dma", "dsa", "consent", "data protection",
    ],
    "Generative AI": [
        "generative ai", "large language model", "ai agents",
        "agentic", "foundation model", "llm", "multimodal",
        "next generation model", "ai inference",
    ],
    "Cost Reduction": [
        "cost cutting", "workforce reduction", "margin expansion",
        "operating leverage", "restructuring", "efficiency gains",
    ],
}

# ── Add each signal category as its own standalone topic ──────────────────────
# The 9 SIGNAL_CATEGORIES from scoring_config become first-class topics so that
# the Topic Signal Map captures the full vocabulary the scoring engine uses.
# Keywords already present elsewhere are still included here — these topics are
# intentionally focused on each signal dimension rather than a merged catch-all.
_SIGNAL_STANDALONE_TOPICS = {
    "Outlook": _CFG_CATEGORY_KW.get("Outlook", []),
    "Risks": _CFG_CATEGORY_KW.get("Risks", []),
    "Opportunities": _CFG_CATEGORY_KW.get("Opportunities", []),
    "Capital Allocation & Investment": _CFG_CATEGORY_KW.get("Investment", []),
    "Product & Platform Shifts": _CFG_CATEGORY_KW.get("Product Shifts", []),
    "User Behavior": _CFG_CATEGORY_KW.get("User Behavior", []),
    "Monetization Strategy": _CFG_CATEGORY_KW.get("Monetization", []),
    "Strategic Direction": _CFG_CATEGORY_KW.get("Strategic Direction", []),
    "Broadcaster Threats": _CFG_CATEGORY_KW.get("Broadcaster Threats", []),
}

for _new_topic, _new_kws in _SIGNAL_STANDALONE_TOPICS.items():
    if _new_topic not in TOPIC_KEYWORDS:
        TOPIC_KEYWORDS[_new_topic] = list(_new_kws)
    else:
        # Topic already exists — merge in any keywords not yet present
        _existing = {kw.strip().lower() for kw in TOPIC_KEYWORDS[_new_topic]}
        for _kw in _new_kws:
            if _kw.strip().lower() not in _existing:
                TOPIC_KEYWORDS[_new_topic].append(_kw)
                _existing.add(_kw.strip().lower())

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


def score_sentence_pipeline(
    sentence: str,
    keywords: list[str],
    role: str = "",
    sentence_idx: int = 0,
    total_sentences: int = 1,
) -> float:
    """
    5-layer scoring engine — mirrors transcript_live._score_sentence_advanced()
    but runs outside Streamlit (no st.cache). Uses scoring_config weights.
    """
    W = _CFG_WEIGHTS
    s = sentence.strip()
    s_lower = s.lower()

    # Hard negation kill
    negation_patterns = [
        "we are not ", "we don't ", "we do not ",
        "we have not ", "we haven't ", "not investing",
        "no longer ", "we stopped ", "we ended ",
    ]
    if any(neg in s_lower for neg in negation_patterns):
        return 0.0

    kw_hits = sum(1 for kw in keywords if kw.lower() in s_lower)
    if kw_hits == 0:
        return 0.0

    has_number = bool(re.search(
        r'\$[\d,]+|\d+[\.,]\d+[BMK%]|\d{1,3}[BMK]\b|\d+\s*(?:billion|million|percent|%)',
        s, re.IGNORECASE,
    ))
    specificity_bonus = W["specificity_bonus"] if has_number else 1.0

    forward_phrases = [
        "we will", "we expect", "we are going to", "we plan to",
        "we intend to", "we are targeting", "going forward",
        "next quarter", "next year", "in 2025", "in 2026",
        "we anticipate", "we are positioned", "we believe",
    ]
    forward_bonus = W["forward_tense_bonus"] if any(p in s_lower for p in forward_phrases) else 1.0

    role_bonus = W["role_bonus_ceo_cfo"] if role in ("CEO", "CFO") else 1.0

    position_ratio = 1 - (sentence_idx / max(total_sentences, 1))
    position_bonus = 1.0 + (position_ratio * W["position_max_bonus"])

    length = len(s)
    if length < 50:
        len_factor = W["len_very_short"]
    elif length < 80:
        len_factor = W["len_short"]
    elif length <= 250:
        len_factor = W["len_medium"]
    else:
        len_factor = W["len_long"]

    fin_score = sum(W["financial_term_bonus"] for t in _CFG_FIN_TERMS if t in s_lower)

    base_score = round(
        (kw_hits + fin_score) * specificity_bonus * forward_bonus
        * role_bonus * position_bonus * len_factor, 3,
    )

    # Stacked verification layers
    if any(ft in s_lower for ft in _CFG_FUTURE):
        base_score *= W["future_tense_stack"]
    _has_concrete = bool(re.search(
        r'\$[\d,]+[BMbm]?|\d+\.?\d*\s*%|\b20(?:2[4-9]|3[0-9])\b|\bQ[1-4]\b',
        s, re.IGNORECASE,
    ))
    if _has_concrete and any(ft in s_lower for ft in _CFG_FUTURE):
        base_score *= W["concrete_forward_stack"]
    if any(neg in s_lower for neg in _CFG_NEGATION):
        base_score *= W["negation_penalty"]
    if any(bp in s_lower for bp in _CFG_BOILERPLATE):
        base_score *= W["boilerplate_penalty"]

    return round(base_score, 3)


def extract_scored_signals_from_file(
    file_path: Path,
    repo_root: Path,
) -> list[dict]:
    """
    Extract scored forward-looking signals from a single transcript file.
    Uses the same 5-layer engine as the app, but without Streamlit.
    Returns list of signal dicts ready for DB insertion.
    """
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    if "---" in text:
        _, body = text.split("---", 1)
    else:
        body = text

    company = normalize_company_name(file_path.parents[1].name)
    year = int(file_path.parents[0].name)
    quarter = int(TRANSCRIPT_FILE_RE.match(file_path.name).group(1))

    # Detect speaker roles
    speaker_re = SPEAKER_RE
    # Candidate-sentence filter: a sentence must mention at least one
    # keyword from ANY of the 9 signal categories. Previously this pool
    # was hardcoded to 5 categories, which made it impossible for Risks,
    # User Behavior, Monetization, and Broadcaster Threats rows to ever
    # reach scored_signals.csv — any rows in those categories only leaked
    # in because they *also* mentioned one of the 5 allowed categories.
    all_kw: list[str] = []
    _seen_kw: set[str] = set()
    for _cat in _CFG_SIGNAL_CATS:
        for _kw in _CFG_CATEGORY_KW.get(_cat, []):
            _k = _kw.lower()
            if _k not in _seen_kw:
                _seen_kw.add(_k)
                all_kw.append(_kw)

    signals: list[dict] = []
    seen_prefixes: set[str] = set()

    for block in re.split(r"\n\s*\n+", body):
        block = " ".join(block.strip().split())
        if len(block) < 40:
            continue

        # Extract speaker and role
        sp_match = speaker_re.match(block)
        speaker = sp_match.group(1) if sp_match else "Unknown"
        text_body = block[sp_match.end():].strip() if sp_match else block

        # Detect CEO/CFO role
        role = ""
        sp_lower = block[:80].lower() if len(block) > 80 else block.lower()
        ceo_titles = ["chief executive officer", "ceo"]
        cfo_titles = ["chief financial officer", "cfo"]
        if any(t in sp_lower for t in ceo_titles):
            role = "CEO"
        elif any(t in sp_lower for t in cfo_titles):
            role = "CFO"

        sentences = list(split_sentences(text_body))
        for idx, sentence in enumerate(sentences):
            s_lower = sentence.lower()
            if len(sentence) < 40 or len(sentence) > 500:
                continue

            # Must contain at least one forward keyword
            if not any(kw.lower() in s_lower for kw in all_kw):
                continue

            score = score_sentence_pipeline(
                sentence, all_kw, role, idx, len(sentences),
            )
            if score < _CFG_THRESHOLDS["min_signal_score"]:
                continue

            prefix = sentence[:_CFG_THRESHOLDS["dedup_prefix_length"]].lower()
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)

            # Determine category by best-match (highest keyword hit
            # count), not first-match-wins. The old code iterated
            # _CFG_CATEGORY_KW in dict-insertion order, so Outlook —
            # which has the broadest phrases ("we expect", "going
            # forward", "guidance") — captured ~66% of all rows and
            # starved every other category. Best-match ties fall back
            # to the narrower category (longer keyword list wins on a
            # tie because more specific vocabularies tend to win).
            _cat_scores: list[tuple[str, int]] = []
            for cat_name, cat_kws in _CFG_CATEGORY_KW.items():
                hits = sum(1 for kw in cat_kws if kw.lower() in s_lower)
                if hits > 0:
                    _cat_scores.append((cat_name, hits))
            if _cat_scores:
                _cat_scores.sort(key=lambda t: (-t[1], _CFG_SIGNAL_CATS.index(t[0])))
                category = _cat_scores[0][0]
            else:
                # No category matched — the sentence survived the
                # candidate filter on a keyword that lives in multiple
                # lists or via a case-insensitive edge case. Fall back
                # to Outlook only as a last resort.
                category = "Outlook"

            has_number = bool(re.search(r'\$[\d,]+|\d+%', sentence))
            has_year_ref = bool(re.search(r'\b20(?:2[4-9]|3[0-9])\b', sentence))
            future_tense_score = 1.0 if any(ft in s_lower for ft in _CFG_FUTURE) else 0.0

            signals.append({
                "company": company,
                "year": year,
                "quarter": f"Q{quarter}",
                "quote": sentence[:500],
                "speaker": speaker,
                "role": role,
                "score": score,
                "category": category,
                "has_number": int(has_number),
                "has_year_ref": int(has_year_ref),
                "future_tense_score": future_tense_score,
            })

    # Sort by score, take top 10 per file
    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals[:10]


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

        # Detect role for scoring
        _role = ""
        _sp_low = block[:80].lower()
        if any(t in _sp_low for t in ("chief executive officer", "ceo")):
            _role = "CEO"
        elif any(t in _sp_low for t in ("chief financial officer", "cfo")):
            _role = "CFO"

        _sentences = list(split_sentences(text_body))
        for _si, sentence in enumerate(_sentences):
            sentence_lower = sentence.lower()
            topics = detect_topics(sentence_lower)
            snippet = sentence[:480]

            # Score using the unified 5-layer engine
            _topic_kws = []
            for t in topics:
                _topic_kws.extend(TOPIC_KEYWORDS.get(t, []))
            _sent_score = score_sentence_pipeline(
                sentence, _topic_kws or [""], _role, _si, len(_sentences),
            ) if topics else 0.0

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
                            "score": round(_sent_score, 3),
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

    # ── Extract scored signals using 5-layer engine ────────────────────────
    all_signals: list[dict] = []
    for company_dir in sorted([p for p in transcript_root.iterdir() if p.is_dir()]):
        for year_dir in sorted([p for p in company_dir.iterdir() if p.is_dir() and p.name.isdigit()]):
            for q_file in sorted([p for p in year_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt"]):
                if not TRANSCRIPT_FILE_RE.match(q_file.name):
                    continue
                try:
                    sigs = extract_scored_signals_from_file(q_file, repo_root)
                    all_signals.extend(sigs)
                except Exception as e:
                    print(f"  Warning: signal extraction failed for {q_file}: {e}")
    signals_df = pd.DataFrame(all_signals)

    topics_out = transcript_root / "transcript_topics.csv"
    metrics_out = transcript_root / "topic_metrics.csv"
    kpis_out = transcript_root / "transcript_kpis.csv"
    signals_out = transcript_root / "scored_signals.csv"
    topics_df.to_csv(topics_out, index=False)
    metrics_df.to_csv(metrics_out, index=False)
    kpis_df.to_csv(kpis_out, index=False)
    if not signals_df.empty:
        signals_df.to_csv(signals_out, index=False)

    print(f"Wrote: {topics_out} ({len(topics_df)} rows)")
    print(f"Wrote: {metrics_out} ({len(metrics_df)} rows)")
    print(f"Wrote: {kpis_out} ({len(kpis_df)} rows)")
    print(f"Wrote: {signals_out} ({len(signals_df)} scored signals)")


if __name__ == "__main__":
    main()
