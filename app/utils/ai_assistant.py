from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
from typing import Dict, List, Optional

import pandas as pd


SECTION_QUESTIONS: Dict[str, List[str]] = {
    "Macro KPI Panel": [
        "What drove M2 growth this quarter?",
        "How does Big Tech/M2 ratio compare to last year?",
        "Which companies increased market cap most?",
    ],
    "Global Media Economy": [
        "Which region had highest ad growth?",
        "What's driving digital advertising in APAC?",
        "Compare US vs China advertising spend",
    ],
    "Smartphone Shipments": [
        "How is Apple's market share trending?",
        "What did executives say about mobile strategy?",
        "Show me quotes about iPhone from latest calls",
    ],
    "Company Metrics": [
        "Which company has best debt-to-revenue ratio?",
        "Show me CFO quotes about margins",
        "Compare Netflix vs Disney subscriber growth",
    ],
}

COMPANY_ALIASES: Dict[str, str] = {
    "alphabet": "Alphabet",
    "google": "Alphabet",
    "apple": "Apple",
    "amazon": "Amazon",
    "meta": "Meta Platforms",
    "facebook": "Meta Platforms",
    "microsoft": "Microsoft",
    "netflix": "Netflix",
    "disney": "Disney",
    "comcast": "Comcast",
    "paramount": "Paramount Global",
    "wbd": "Warner Bros. Discovery",
    "warner": "Warner Bros. Discovery",
    "roku": "Roku",
    "spotify": "Spotify",
}

METRIC_ALIASES: Dict[str, str] = {
    "revenue": "revenue",
    "net income": "net_income",
    "operating income": "operating_income",
    "debt": "debt",
    "cash": "cash_balance",
    "capex": "capex",
    "r&d": "r_and_d",
    "market cap": "market_cap",
    "assets": "total_assets",
}


@dataclass
class QueryContext:
    section: str
    year: int
    quarter: str


class EarningscallAI:
    """
    Lightweight SQL-backed assistant for Overview/Earnings context.
    Uses deterministic query routing (no external LLM required).
    """

    def __init__(self, db_path: str, current_section: str, current_year: int, current_quarter: str):
        self.db_path = str(db_path)
        self.context = QueryContext(
            section=str(current_section or "").strip() or "Overview",
            year=int(current_year),
            quarter=str(current_quarter or "Q4").strip().upper(),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_suggested_questions(self, section: Optional[str] = None) -> List[str]:
        key = str(section or self.context.section or "").strip()
        if key in SECTION_QUESTIONS:
            return SECTION_QUESTIONS[key]
        return SECTION_QUESTIONS.get("Company Metrics", [])

    def answer(self, question: str) -> str:
        q = str(question or "").strip()
        if not q:
            return "Please enter a question."

        q_type = self._classify_question(q)
        if q_type == "quote":
            return self._answer_quote_question(q)
        if q_type == "comparison":
            return self._answer_comparison_question(q)
        if q_type == "trend":
            return self._answer_trend_question(q)
        return self._answer_metric_question(q)

    def _classify_question(self, question: str) -> str:
        q = question.lower()
        if any(k in q for k in ["say", "quote", "comment", "mentioned", "what did"]):
            return "quote"
        if any(k in q for k in ["compare", "vs", "versus", "difference", "between"]):
            return "comparison"
        if any(k in q for k in ["trend", "over time", "history", "evolution", "change"]):
            return "trend"
        return "metric"

    def _extract_company(self, question: str) -> Optional[str]:
        q = question.lower()
        for alias, canonical in COMPANY_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", q):
                return canonical
        return None

    def _extract_companies(self, question: str) -> List[str]:
        q = question.lower()
        found = []
        for alias, canonical in COMPANY_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", q) and canonical not in found:
                found.append(canonical)
        return found

    def _extract_metric(self, question: str) -> Optional[str]:
        q = question.lower()
        for alias, metric in METRIC_ALIASES.items():
            if alias in q:
                return metric
        return None

    def _extract_topic(self, question: str) -> Optional[str]:
        q = question.lower()
        # Common topic cues
        for topic in [
            "ai",
            "advertising",
            "guidance",
            "margin",
            "cost",
            "debt",
            "subscribers",
            "competition",
            "regulation",
            "innovation",
        ]:
            if topic in q:
                return topic
        m = re.search(r"about\s+([a-zA-Z\-\s]+)$", q)
        if m:
            return m.group(1).strip()
        return None

    def _db_exists(self) -> bool:
        return Path(self.db_path).exists()

    def _answer_quote_question(self, question: str) -> str:
        if not self._db_exists():
            return f"Intelligence DB not found at `{self.db_path}`. Run `python3 scripts/sync_all_intelligence.py`."

        company = self._extract_company(question)
        topic = self._extract_topic(question) or ""

        with self._connect() as conn:
            if company:
                query = """
                    SELECT h.speaker, h.text, t.company, t.year, t.quarter, h.relevance_score
                    FROM transcript_highlights h
                    JOIN transcripts t ON h.transcript_id = t.id
                    WHERE t.company = ?
                      AND LOWER(h.text) LIKE ?
                    ORDER BY t.year DESC,
                             CASE t.quarter WHEN 'Q4' THEN 4 WHEN 'Q3' THEN 3 WHEN 'Q2' THEN 2 WHEN 'Q1' THEN 1 ELSE 0 END DESC,
                             h.relevance_score DESC
                    LIMIT 4
                """
                rows = conn.execute(query, (company, f"%{topic.lower()}%")).fetchall()
            else:
                query = """
                    SELECT h.speaker, h.text, t.company, t.year, t.quarter, h.relevance_score
                    FROM transcript_highlights h
                    JOIN transcripts t ON h.transcript_id = t.id
                    WHERE LOWER(h.text) LIKE ?
                    ORDER BY h.relevance_score DESC
                    LIMIT 4
                """
                rows = conn.execute(query, (f"%{topic.lower()}%",)).fetchall()

        if not rows:
            return "No matching transcript quotes found for that query."

        heading = f"**Transcript quotes on {topic}**" if topic else "**Transcript quotes**"
        lines = [heading]
        for row in rows:
            lines.append(
                f"- **{row['speaker'] or 'Unknown'}** ({row['company']} {row['year']} {row['quarter']}): "
                f"\"{str(row['text']).strip()}\""
            )
        return "\n".join(lines)

    def _answer_metric_question(self, question: str) -> str:
        if not self._db_exists():
            return f"Intelligence DB not found at `{self.db_path}`. Run `python3 scripts/sync_all_intelligence.py`."

        company = self._extract_company(question)
        metric = self._extract_metric(question)
        if not metric:
            metric = "revenue"

        with self._connect() as conn:
            if company:
                row = conn.execute(
                    f"""
                    SELECT company, year, quarter, {metric} AS value
                    FROM company_metrics
                    WHERE company = ?
                    ORDER BY year DESC,
                             CASE quarter WHEN 'Q4' THEN 4 WHEN 'Q3' THEN 3 WHEN 'Q2' THEN 2 WHEN 'Q1' THEN 1 ELSE 0 END DESC
                    LIMIT 1
                    """,
                    (company,),
                ).fetchone()
            else:
                row = conn.execute(
                    f"""
                    SELECT company, year, quarter, {metric} AS value
                    FROM company_metrics
                    WHERE year = ?
                    ORDER BY value DESC
                    LIMIT 1
                    """,
                    (int(self.context.year),),
                ).fetchone()

        if not row or row["value"] is None:
            return f"No `{metric}` value found for that scope."

        value = float(row["value"])
        if abs(value) >= 1_000:
            value_txt = f"{value:,.1f}M"
        else:
            value_txt = f"{value:,.2f}"

        return (
            f"**{row['company']} {metric.replace('_', ' ').title()}**\n\n"
            f"{value_txt} (source period: {row['year']} {row['quarter']})"
        )

    def _answer_comparison_question(self, question: str) -> str:
        if not self._db_exists():
            return f"Intelligence DB not found at `{self.db_path}`. Run `python3 scripts/sync_all_intelligence.py`."

        companies = self._extract_companies(question)
        metric = self._extract_metric(question) or "revenue"
        if len(companies) < 2:
            return "Please mention at least two companies to compare (for example: 'Compare Meta vs Google revenue')."

        placeholders = ",".join(["?"] * len(companies))
        params = list(companies)

        with self._connect() as conn:
            df = pd.read_sql_query(
                f"""
                SELECT company, year, quarter, {metric} AS value
                FROM company_metrics
                WHERE company IN ({placeholders})
                ORDER BY year DESC,
                         CASE quarter WHEN 'Q4' THEN 4 WHEN 'Q3' THEN 3 WHEN 'Q2' THEN 2 WHEN 'Q1' THEN 1 ELSE 0 END DESC
                """,
                conn,
                params=params,
            )

        if df.empty:
            return f"No rows found to compare `{metric}` for those companies."

        latest = df.sort_values(["company", "year", "quarter"]).groupby("company", as_index=False).tail(1)
        latest = latest.sort_values("value", ascending=False)

        lines = [f"**Comparison: {metric.replace('_', ' ').title()}**"]
        for row in latest.itertuples(index=False):
            val = pd.to_numeric(pd.Series([row.value]), errors="coerce").iloc[0]
            if pd.isna(val):
                continue
            lines.append(f"- {row.company}: {float(val):,.1f}M ({row.year} {row.quarter})")
        return "\n".join(lines)

    def _answer_trend_question(self, question: str) -> str:
        if not self._db_exists():
            return f"Intelligence DB not found at `{self.db_path}`. Run `python3 scripts/sync_all_intelligence.py`."

        company = self._extract_company(question)
        metric = self._extract_metric(question) or "revenue"
        if not company:
            return "Please include a company for trend questions (for example: 'Trend of Apple revenue')."

        with self._connect() as conn:
            df = pd.read_sql_query(
                f"""
                SELECT year, quarter, {metric} AS value
                FROM company_metrics
                WHERE company = ?
                ORDER BY year,
                         CASE quarter WHEN 'Q1' THEN 1 WHEN 'Q2' THEN 2 WHEN 'Q3' THEN 3 WHEN 'Q4' THEN 4 ELSE 0 END
                """,
                conn,
                params=[company],
            )

        if df.empty:
            return f"No trend rows found for {company} {metric}."

        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        if df.empty:
            return f"No numeric trend values found for {company} {metric}."

        first = df.iloc[0]
        last = df.iloc[-1]
        delta_pct = ((last["value"] - first["value"]) / first["value"] * 100.0) if first["value"] else None

        delta_txt = f"{delta_pct:+.1f}%" if delta_pct is not None else "n/a"
        return (
            f"**{company} {metric.replace('_', ' ').title()} trend**\n\n"
            f"Start: {first['value']:,.1f} ({int(first['year'])} {first['quarter']})\n"
            f"Latest: {last['value']:,.1f} ({int(last['year'])} {last['quarter']})\n"
            f"Change: {delta_txt}"
        )
