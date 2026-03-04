import json
import re
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
    state_json = json.dumps(dashboard_state, indent=2, default=str)
    system_content = (
        GENIE_SYSTEM_PROMPT
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
def _load_transcripts_frame(excel_path: str) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    try:
        df = pd.read_excel(
            excel_path,
            sheet_name="Transcripts",
            usecols=["company", "year", "quarter", "transcript_text"],
        )
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["company"] = df["company"].astype(str).str.strip()
    df["company_lc"] = df["company"].str.lower()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["quarter"] = df["quarter"].astype(str).str.upper().str.strip()
    df["transcript_text"] = df["transcript_text"].astype(str)
    df = df.dropna(subset=["year"])
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["year"].astype(int)
    return df


def build_query_transcript_context(user_message: str, dashboard_state: dict) -> dict:
    """
    Resolve a transcript context block from the user query if company/period can be inferred.
    """
    message = str(user_message or "")
    if not message.strip():
        return {}

    excel_path = str(dashboard_state.get("excel_path", "") or "")
    df = _load_transcripts_frame(excel_path)
    if df.empty:
        return {}

    company_aliases = {
        "meta": "Meta Platforms",
        "google": "Alphabet",
        "warner bros discovery": "Warner Bros Discovery",
        "warner bros. discovery": "Warner Bros Discovery",
        "wbd": "Warner Bros Discovery",
        "paramount": "Paramount Global",
    }
    message_lc = message.lower()
    target_company = None
    for company in sorted(df["company"].unique().tolist(), key=len, reverse=True):
        if company.lower() in message_lc:
            target_company = company
            break
    if not target_company:
        for alias, canonical in company_aliases.items():
            if alias in message_lc:
                matches = df[df["company_lc"].str.contains(canonical.lower(), regex=False)]
                if not matches.empty:
                    target_company = matches.iloc[0]["company"]
                    break
    if not target_company:
        return {}

    year_match = re.search(r"\b(20\d{2})\b", message)
    target_year = int(year_match.group(1)) if year_match else None

    quarter_match = re.search(r"\bQ([1-4])\b", message, flags=re.IGNORECASE)
    if quarter_match:
        target_quarter = f"Q{quarter_match.group(1)}"
    else:
        alt_q_match = re.search(r"\b([1-4])Q\b", message, flags=re.IGNORECASE)
        target_quarter = f"Q{alt_q_match.group(1)}" if alt_q_match else None

    scoped = df[df["company_lc"] == str(target_company).lower()]
    if target_year is not None:
        scoped = scoped[scoped["year"] == int(target_year)]
    if target_quarter is not None:
        scoped = scoped[scoped["quarter"] == target_quarter]

    if scoped.empty:
        scoped = df[df["company_lc"] == str(target_company).lower()]
    if scoped.empty:
        return {}

    record = scoped.sort_values(["year", "quarter"], ascending=[False, False]).iloc[0]
    transcript_text = str(record.get("transcript_text", "") or "").strip()
    excerpt = transcript_text[:6000]
    if len(transcript_text) > 6000:
        excerpt += "\n...[truncated for prompt context]..."

    return {
        "company": str(record.get("company", "")),
        "year": int(record.get("year", 0)),
        "quarter": str(record.get("quarter", "")),
        "transcript_excerpt": excerpt,
    }
