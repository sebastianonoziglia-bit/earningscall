import json
import re
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


def get_openai_client() -> Optional["OpenAI"]:
    """Return an OpenAI client using Streamlit secrets or session key."""
    if OpenAI is None:
        return None

    api_key = (
        st.secrets.get("OPENAI_API_KEY", "")
        or st.session_state.get("openai_api_key", "")
    )
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


GENIE_SYSTEM_PROMPT = """
You are the Financial Genie, an expert AI analyst embedded in the Earningscall
competitive intelligence dashboard. You have direct access to a proprietary
financial database covering 13 major technology and media companies.

## COMPANIES IN THE DATABASE
Alphabet (GOOGL), Amazon (AMZN), Apple (AAPL), Comcast (CMCSA), Disney (DIS),
Meta Platforms (META), Microsoft (MSFT), Netflix (NFLX), Paramount Global (PARA),
Roku (ROKU), Spotify (SPOT), Warner Bros. Discovery (WBD), MFE (Mediaforeurope)

## FINANCIAL DATA AVAILABLE (per company, per year, 2010–2024)
- Revenue, Operating Income, Net Income, Cost of Revenue
- R&D Spend, Capex, Total Assets, Long-Term Debt, Cash Balance
- Market Capitalization, Employee Count
- Advertising Revenue (company-specific, some estimated*)
- Revenue by business segment (yearly and quarterly)
- Subscriber counts by service (quarterly, 2016–2024)
- Revenue by geography (North America, International, EMEA, APAC)

## ADVERTISING DATA (2010–2024)
Ad revenue for: Google/Alphabet, Meta, Amazon, Spotify, WBD*, Microsoft*,
Paramount, Apple*, Disney*, Comcast*, Netflix*, Twitter/X, TikTok, Snapchat
(* = estimates)

## MACRO DATA AVAILABLE
- US M2 Money Supply (monthly, 1981–present)
- USD Inflation: Official CPI + ShadowStats 1980s/1990s Methods + Chapwood Index
- Global advertising market aggregates by channel (Digital, TV, OOH, Print, etc.)
- Country-level advertising spend vs. GDP
- Nasdaq Composite historical data
- Smartphone shipment data by manufacturer (2010–2024)
- Average internet time spent per country

## EARNINGS CALL TRANSCRIPTS
348 full earnings call transcripts available:
- Companies: Alphabet, Amazon, Apple, Comcast, Disney, Meta Platforms, Microsoft,
  Netflix, Paramount Global, Roku, Samsung, Spotify, Tencent, Warner Bros Discovery
- Year range: 2018–2026
- You can reference and quote directly from these transcripts when asked

## STRATEGIC SIGNALS (pre-computed, always current)
The dashboard has identified these as the top structural signals for 2024:
1. HIGH: Alphabet + Meta control 85.8% of tracked ad revenue (Duopoly Tollbooth)
2. MEDIUM: Meta posted fastest ad revenue growth in 2024: +20.8% YoY
3. HIGH: Netflix leads revenue per employee at $2.79M/employee (2024 Q2)
4. MEDIUM: Apple grew market-cap-per-employee 2.51× from 2019–2024
5. HIGH: Top 3 companies = 66.6% of tracked market cap (concentration regime)
6. MEDIUM: Warner Bros. Discovery has highest debt/revenue ratio: 0.93×

## HOW TO FORMAT YOUR REASONING
When asked to "think through", "analyze", or "reason about" something complex,
ALWAYS structure your response using these markers — they power the Thought Map:

[STEP 1] Observation: state what the data shows
[STEP 2] Inference: what does this imply?
[STEP 3] Analysis: deeper interpretation
[CONCLUSION] Summary: the key takeaway
[BRANCH A] Alternative view: what if the opposite is true?
[BRANCH B] Risk factor: what could change this conclusion?

Use this format for any analytical or reasoning response, even if not explicitly asked.
For simple factual questions, answer directly without the step format.

## DATA FORMATTING RULES
- Always cite figures as: $X.XB (billions) or $X.XT (trillions) or $XM (millions)
- Always mention YoY % when discussing a single year's number
- Never hallucinate data — if you don't have a figure, say "not in the dataset"
- When quoting transcripts, cite company + year + quarter: e.g. (Alphabet Q4 2023)
- Units in the financial sheet are USD millions unless noted otherwise

## IMPORTANT NOTES
- "MFE" in the data = Mediaforeurope (European media company)
- Subscriber sheet column "US_Canade" is intentionally misspelled — it means US/Canada
- Ad revenue column values are in USD billions (not millions like the metrics sheet)
- Transcript data goes back to 2018 only
"""


def build_genie_messages(
    conversation_history: list[dict],
    dashboard_state: dict,
    user_message: str,
) -> list[dict]:
    """Build a full OpenAI message list without truncating history."""
    selected_companies = dashboard_state.get("selected_companies") or []
    company = str(selected_companies[0]).strip() if isinstance(selected_companies, list) and selected_companies else ""

    year = None
    year_range_state = st.session_state.get("year_range_selector")
    if isinstance(year_range_state, (list, tuple)) and len(year_range_state) >= 2:
        try:
            year = int(year_range_state[1])
        except Exception:
            year = None
    if year is None:
        year_range_text = str(dashboard_state.get("year_range", "") or "")
        match = re.search(r"(\d{4})\s*-\s*(\d{4})", year_range_text)
        if match:
            year = int(match.group(2))

    quarter_focus = str(
        dashboard_state.get("quarter_focus")
        or st.session_state.get("genie_selected_quarter_focus")
        or ""
    ).strip()
    quarter = quarter_focus if re.fullmatch(r"Q[1-4]", quarter_focus, flags=re.IGNORECASE) else ""

    context = build_genie_context_from_db(company=company, year=year, quarter=quarter)
    transcript_excerpt = str(context.get("transcript", "") or "")[:3000]
    db_context_prompt = (
        "You are a financial analyst assistant. Use the following data to answer the user question. "
        f"Metrics: {context.get('metrics', [])}. "
        f"Top topics from transcripts: {context.get('topic_scores', [])}. "
        f"Auto-generated insights: {context.get('insights', [])}. "
        f"Transcript excerpt: {transcript_excerpt}"
    )

    state_json = json.dumps(dashboard_state, indent=2, default=str)
    system_content = (
        GENIE_SYSTEM_PROMPT
        + f"\n\n## DB CONTEXT\n{db_context_prompt}"
        + f"\n\n## CURRENT DASHBOARD STATE\n```json\n{state_json}\n```"
    )
    messages = [{"role": "system", "content": system_content}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})
    return messages


def stream_genie_response(messages: list[dict]) -> str:
    """Stream a response from OpenAI and return the full assistant text."""
    client = get_openai_client()
    if not client:
        msg = (
            "⚠️ **No OpenAI API key configured.**\n\n"
            "Add your key in the sidebar under **🔑 AI Settings**, "
            "or set `OPENAI_API_KEY` in Streamlit secrets."
        )
        st.warning(msg)
        return msg

    model = st.session_state.get("genie_model", "gpt-4o")

    with st.chat_message("assistant", avatar="🧞"):
        placeholder = st.empty()
        full_response = ""

        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                temperature=0.3,
                max_tokens=4000,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_response += delta
                    placeholder.markdown(full_response + "▌")

            placeholder.markdown(full_response)

        except Exception as exc:  # pragma: no cover
            error_msg = f"❌ OpenAI API error: {str(exc)}"
            placeholder.error(error_msg)
            return error_msg

    return full_response


@st.cache_data(ttl=3600)
def build_genie_context_from_db(company, year, quarter) -> dict:
    try:
        repo_root = Path(__file__).resolve().parents[2]
        db_path = repo_root / "earningscall_intelligence.db"
        insights_path = repo_root / "earningscall_transcripts" / "generated_insights_latest.csv"

        if not db_path.exists():
            return {"metrics": [], "transcript": "", "topic_scores": [], "insights": []}

        company_text = str(company or "").strip()
        year_int = int(year) if year is not None else None
        quarter_text = str(quarter or "").strip().upper()
        quarter_text = quarter_text if re.fullmatch(r"Q[1-4]", quarter_text) else ""

        with sqlite3.connect(str(db_path)) as conn:
            if company_text and year_int is not None:
                metrics = pd.read_sql_query(
                    "SELECT * FROM company_metrics WHERE company=? AND year=?",
                    conn,
                    params=[company_text, year_int],
                )
            else:
                metrics = pd.DataFrame()

            if company_text and year_int is not None and not quarter_text:
                latest_q_df = pd.read_sql_query(
                    "SELECT quarter FROM transcripts WHERE company=? AND year=? ORDER BY quarter DESC LIMIT 1",
                    conn,
                    params=[company_text, year_int],
                )
                if not latest_q_df.empty and "quarter" in latest_q_df.columns:
                    inferred_q = str(latest_q_df.iloc[0]["quarter"] or "").strip().upper()
                    if re.fullmatch(r"Q[1-4]", inferred_q):
                        quarter_text = inferred_q

            transcript_text = ""
            if company_text and year_int is not None and quarter_text:
                transcript_column = "text"
                transcript_cols = pd.read_sql_query("PRAGMA table_info(transcripts)", conn)
                if "name" in transcript_cols.columns:
                    available = {str(v).strip().lower() for v in transcript_cols["name"].tolist()}
                    if "text" not in available and "full_text" in available:
                        transcript_column = "full_text"
                transcript_query = (
                    f"SELECT {transcript_column} AS text FROM transcripts "
                    "WHERE company=? AND year=? AND quarter=?"
                )
                transcript_df = pd.read_sql_query(
                    transcript_query,
                    conn,
                    params=[company_text, year_int, quarter_text],
                )
                if not transcript_df.empty and "text" in transcript_df.columns:
                    transcript_text = str(transcript_df.iloc[0]["text"] or "")

            if company_text and year_int is not None and quarter_text:
                topic_query = """
                    SELECT tt.topic, SUM(tt.mention_count) as total_mentions
                    FROM transcript_topics tt
                    JOIN transcripts t ON tt.transcript_id = t.id
                    WHERE t.company=? AND t.year=? AND t.quarter=?
                    GROUP BY tt.topic
                    ORDER BY total_mentions DESC
                """
                topic_scores = pd.read_sql_query(topic_query, conn, params=[company_text, year_int, quarter_text])
            else:
                topic_scores = pd.DataFrame(columns=["topic", "total_mentions"])

        insights = pd.DataFrame()
        if insights_path.exists():
            try:
                insights_df = pd.read_csv(insights_path)
                if "companies" in insights_df.columns and company_text:
                    mask = insights_df["companies"].astype(str).str.contains(company_text, case=False, na=False)
                    insights = insights_df[mask].copy()
                else:
                    insights = insights_df.copy()
            except Exception:
                insights = pd.DataFrame()

        return {
            "metrics": metrics.to_dict("records") if metrics is not None else [],
            "transcript": transcript_text,
            "topic_scores": topic_scores.to_dict("records") if topic_scores is not None else [],
            "insights": insights.to_dict("records") if insights is not None else [],
        }
    except Exception:
        return {"metrics": [], "transcript": "", "topic_scores": [], "insights": []}


def build_query_transcript_context(user_message: str, dashboard_state: dict) -> dict:
    """
    Resolve a transcript context block from the user query if company/period can be inferred.
    """
    message = str(user_message or "")
    if not message.strip():
        return {}

    selected_companies = dashboard_state.get("selected_companies") or []
    target_company = str(selected_companies[0]).strip() if isinstance(selected_companies, list) and selected_companies else ""

    if not target_company:
        company_aliases = {
            "meta": "Meta Platforms",
            "google": "Alphabet",
            "wbd": "Warner Bros. Discovery",
            "paramount": "Paramount Global",
        }
        message_lc = message.lower()
        for alias, canonical in company_aliases.items():
            if alias in message_lc:
                target_company = canonical
                break
    if not target_company:
        return {}

    year_match = re.search(r"\b(20\d{2})\b", message)
    target_year = int(year_match.group(1)) if year_match else None
    if target_year is None:
        year_range_state = st.session_state.get("year_range_selector")
        if isinstance(year_range_state, (list, tuple)) and len(year_range_state) >= 2:
            try:
                target_year = int(year_range_state[1])
            except Exception:
                target_year = None
    if target_year is None:
        year_range_text = str(dashboard_state.get("year_range", "") or "")
        year_range_match = re.search(r"(\d{4})\s*-\s*(\d{4})", year_range_text)
        if year_range_match:
            target_year = int(year_range_match.group(2))

    quarter_match = re.search(r"\bQ([1-4])\b", message, flags=re.IGNORECASE)
    if quarter_match:
        target_quarter = f"Q{quarter_match.group(1)}"
    else:
        focus = str(
            dashboard_state.get("quarter_focus")
            or st.session_state.get("genie_selected_quarter_focus")
            or ""
        ).strip().upper()
        target_quarter = focus if re.fullmatch(r"Q[1-4]", focus) else ""

    context = build_genie_context_from_db(
        company=target_company,
        year=target_year,
        quarter=target_quarter,
    )
    transcript_text = str(context.get("transcript", "") or "").strip()
    if not transcript_text:
        return {}
    excerpt = transcript_text[:6000]
    if len(transcript_text) > 6000:
        excerpt += "\n...[truncated for prompt context]..."

    return {
        "company": target_company,
        "year": int(target_year) if target_year is not None else 0,
        "quarter": str(target_quarter),
        "transcript_excerpt": excerpt,
    }
