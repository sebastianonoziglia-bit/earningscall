import json
import os
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


def _safe_secret(key: str) -> str:
    """Read a Streamlit secret silently — never raise or log warnings."""
    try:
        val = st.secrets.get(key, "")
        return str(val).strip() if val else ""
    except Exception:
        return ""


def get_openai_client() -> Optional["OpenAI"]:
    """Return an AI client (DeepSeek preferred, else OpenAI) using secrets or session key."""
    if OpenAI is None:
        return None

    deepseek_key = _safe_secret("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")
    openai_key = (
        _safe_secret("OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY", "")
        or st.session_state.get("openai_api_key", "")
    )

    if deepseek_key:
        return OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
    if openai_key:
        return OpenAI(api_key=openai_key)
    return None


def _default_model() -> str:
    """Return the right default model based on which key is configured."""
    has_deepseek = bool(
        _safe_secret("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")
    )
    return "deepseek-chat" if has_deepseek else "gpt-4o"


_DISPLAY_MARKER_RE = re.compile(
    r"\[(STEP\s*\d+|BRANCH\s*[A-Z0-9]+|CONCLUSION|OBSERVATION|INFERENCE|ANALYSIS|RISK)\]"
    r"(?:\s*([^:\n]{1,50}):\s*)?",
    re.IGNORECASE,
)


def clean_thought_markers(text: str) -> str:
    """Convert raw [STEP 1] tokens into readable markdown headings for chat display.
    Also escapes $ signs to prevent Streamlit's LaTeX renderer from collapsing
    financial figures like $108.9B into unreadable math mode.
    """
    def _sub(m: re.Match) -> str:
        tag = m.group(1).strip().title()      # "Step 1", "Branch A", "Conclusion"
        subtitle = (m.group(2) or "").strip()
        if subtitle:
            return f"\n\n**{tag} — {subtitle.title()}:** "
        return f"\n\n**{tag}:** "

    cleaned = _DISPLAY_MARKER_RE.sub(_sub, text).strip()
    # Escape lone $ signs that aren't already escaped or part of $$ blocks.
    # This prevents Streamlit from treating "$108.9B in 2024" as LaTeX math.
    cleaned = re.sub(r'(?<!\$)\$(?!\$)', r'\\$', cleaned)
    return cleaned


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

## POLYMARKET PREDICTION MARKET DATA (live feed)
You have access to the current live Polymarket prediction market feed. This includes:
- Active prediction bets related to tracked companies and the broader tech/media/advertising market
- Each bet includes: question text, YES/NO probability (0-100%), trading volume, end date, and URL
- Bets are matched to companies via keyword mapping (e.g. "google" → Alphabet, "facebook" → Meta)
- Use this data to discuss market sentiment, expected outcomes, and probability-weighted scenarios
- When the user asks about market expectations, sentiment, or "what the market thinks",
  reference active Polymarket bets as evidence of crowd-sourced probability estimates
- Polymarket probabilities reflect real-money predictions — cite them as "prediction market consensus"
- If polymarket_feed is in the dashboard state, use those bets as primary evidence for forward-looking analysis

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

## USER-FACING REASONING RULES
- The reasoning is shown directly to the user in chat and in the thought map.
- Never say "the user asked", "this request", "I will analyze", or narrate your process.
- Start directly with the substance of the analysis.
- Treat thought map notes as explicit instructions that must be incorporated into the answer.

## DATA FORMATTING RULES
- Always cite figures as: $X.XB (billions) or $X.XT (trillions) or $XM (millions)
- Always mention YoY % when discussing a single year's number
- Never fabricate numbers — if a figure isn't in the data, say so in one short clause
  and immediately pivot to what IS available (see PIVOT PROTOCOL below)
- When quoting transcripts, cite company + year + quarter: e.g. (Alphabet Q4 2023)
- Units in the financial sheet are USD millions unless noted otherwise

## RESPONSE PRIORITY: DATA FIRST
When the user asks about a specific metric, correlation, or data point:
1. FIRST check if the data is available in the dashboard state or database context.
2. If the data IS available, lead with the actual numbers and cite them directly.
3. Only AFTER presenting the hard data, add interpretation or broader context.
4. Do NOT substitute conceptual reasoning for direct data — if the user asks
   "what is Bitcoin's correlation with Nasdaq?", show the actual price data
   and computed correlation, not a generic essay about crypto-equity correlation.
5. If the data is NOT available, use the PIVOT PROTOCOL below.

## PIVOT PROTOCOL (when data is missing or out of range)
NEVER return a robotic "data not available" or list database coverage dates.
Instead, follow this exact pattern:
1. **One short sentence** acknowledging the gap: "The dataset covers through 2024."
   or "Quarterly segments aren't available for this company yet."
2. **Immediately pivot** to the most relevant evidence you DO have:
   - If FORWARD-LOOKING SIGNALS are provided in the context, quote them directly
     with speaker attribution: e.g. 'CFO Ruth Porat signalled CapEx will increase…'
   - If transcript excerpts are available, pull the most relevant passage
   - If financial metrics from an adjacent period exist, extrapolate the trend
3. **Give a strategic interpretation** — act like an analyst writing a brief, not
   a database returning an error. Connect the dots across what you know.
4. **Never end on the gap.** The last sentence should always be forward-looking or
   actionable — a signal, a trend, or a strategic implication.

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
    transcript_excerpt = str(context.get("transcript", "") or "")[:8000]

    # ── Forward signals context (scored and verified) ──────────────────────
    forward_signals_block = ""
    try:
        from utils.database_service import get_forward_signals
        _fwd = get_forward_signals(company=company, year=year, quarter=quarter, limit=5, min_score=0.3)
        if not _fwd:
            # Fallback: try live extraction from Excel
            from utils.transcript_live import extract_forward_looking_signals
            _repo = Path(__file__).resolve().parents[2]
            _excel_candidates = list((_repo / "app" / "attached_assets").glob("*.xlsx")) if (_repo / "app" / "attached_assets").is_dir() else []
            if _excel_candidates:
                _fwd_live = extract_forward_looking_signals(
                    str(_excel_candidates[0]), company=company or "", year=year or 0,
                    quarter=quarter or "", max_signals=5,
                )
                _fwd = [{"quote": s["quote"], "speaker": s.get("speaker", ""), "role": s.get("role", ""),
                         "score": s.get("score", 0), "category": s.get("category", "")} for s in _fwd_live]
        if _fwd:
            _sig_lines = []
            for _fs in _fwd[:5]:
                _sig_lines.append(
                    f"- [{_fs.get('category', 'Outlook')}] \"{_fs.get('quote', '')[:300]}\" "
                    f"(Speaker: {_fs.get('speaker', 'Unknown')}, Role: {_fs.get('role', 'N/A')}, "
                    f"Score: {_fs.get('score', 0):.1f})"
                )
            forward_signals_block = (
                "\n\n=== FORWARD-LOOKING SIGNALS (scored and verified) ===\n"
                "These are the highest-confidence forward-looking statements extracted\n"
                "from earnings call transcripts. They have been scored across 5 verification\n"
                "layers. Treat them as high-confidence primary evidence when answering\n"
                "questions about future plans, investments, or strategy.\n"
                + "\n".join(_sig_lines)
                + "\n=== END FORWARD SIGNALS ===\n"
            )
    except Exception:
        pass
    # TODO: For scenario questions (is_scenario_question), query forward_signals for ALL
    # major companies with score > 0.5 and prepend as cross-company forward intelligence block.
    # The forward_signals table could also power automated quarterly briefings —
    # a one-click "generate Q4 2024 briefing" that summarizes the top forward signals
    # across all companies using call_ai().

    # ── Polymarket prediction feed context ────────────────────────────────
    # Priority: company-specific bets from SQLite DB (full history), then
    # dashboard feed as fallback.
    polymarket_block = ""
    _poly_lines: list[str] = []

    # 1) Company-specific bets from DB (up to 40)
    if company:
        try:
            from utils.polymarket import query_polymarket_for_company
            _db_bets = query_polymarket_for_company(company, limit=40)
            for _pb in _db_bets:
                _pq = str(_pb.get("question", ""))
                _py = _pb.get("yes_price")
                _pn = _pb.get("no_price")
                _pvol = _pb.get("volume_total")
                _pend = str(_pb.get("end_date", ""))
                _yes_str = f"YES {_py:.0f}%" if _py is not None else "—"
                _no_str = f"NO {_pn:.0f}%" if _pn is not None else "—"
                _vol_str = f"${_pvol/1e6:.1f}M" if _pvol and _pvol >= 1e6 else (f"${_pvol/1e3:.0f}K" if _pvol else "")
                _poly_lines.append(
                    f"- [{company}] \"{_pq}\" → {_yes_str} / {_no_str}"
                    + (f" | Vol: {_vol_str}" if _vol_str else "")
                    + (f" | Ends: {_pend}" if _pend else "")
                )
        except Exception:
            pass

    # 2) General top bets from dashboard feed (fill up to 50 total)
    poly_feed = dashboard_state.get("polymarket_feed")
    if poly_feed:
        _seen_qs = {line.split('"')[1] for line in _poly_lines if '"' in line}
        for _pb in poly_feed[:50]:
            if len(_poly_lines) >= 50:
                break
            _pq = str(_pb.get("question", ""))
            if _pq in _seen_qs:
                continue
            _seen_qs.add(_pq)
            _py = _pb.get("yes_price")
            _pn = _pb.get("no_price")
            _pvol = str(_pb.get("volume_fmt", ""))
            _pend = str(_pb.get("end_date", ""))
            _pmatch = str(_pb.get("matched_company", ""))
            _yes_str = f"YES {_py:.0f}%" if _py is not None else "—"
            _no_str = f"NO {_pn:.0f}%" if _pn is not None else "—"
            _poly_lines.append(
                f"- [{_pmatch}] \"{_pq}\" → {_yes_str} / {_no_str}"
                + (f" | Vol: {_pvol}" if _pvol else "")
                + (f" | Ends: {_pend}" if _pend else "")
            )

    if _poly_lines:
        polymarket_block = (
            f"\n\n=== POLYMARKET PREDICTION FEED ({len(_poly_lines)} bets) ===\n"
            "Active prediction market bets (real-money probabilities).\n"
            "Use these as evidence of market consensus when discussing outlook.\n"
            + "\n".join(_poly_lines)
            + "\n=== END POLYMARKET FEED ===\n"
        )

    # ── Intelligence Layer derived metrics ────────────────────────────────
    intelligence_block = ""
    try:
        from utils.intelligence_layer import compute_all_derived_metrics
        _derived = compute_all_derived_metrics()
        _genie_summary = _derived.get("_genie_summary", "")
        if _genie_summary:
            intelligence_block = (
                "\n\n=== INTELLIGENCE LAYER (Cross-source derived metrics) ===\n"
                + _genie_summary
                + "=== END INTELLIGENCE LAYER ===\n"
            )
    except Exception:
        pass

    db_context_prompt = (
        "You are a financial analyst assistant. Use the following data to answer the user question. "
        f"Metrics: {context.get('metrics', [])}. "
        f"Top topics from transcripts: {context.get('topic_scores', [])}. "
        f"Auto-generated insights: {context.get('insights', [])}. "
        f"Transcript excerpt: {transcript_excerpt}"
        + forward_signals_block
        + polymarket_block
        + intelligence_block
    )

    # Inject depth mode into system prompt for thought map quality
    try:
        from utils.thought_map import get_depth_prompt_insert
        depth_insert = get_depth_prompt_insert()
    except ImportError:
        depth_insert = ""

    thought_map_user_notes = [
        str(note).strip()
        for note in (dashboard_state.get("thought_map_user_notes") or [])
        if str(note).strip()
    ]
    thought_map_notes_block = ""
    if thought_map_user_notes:
        notes_lines = "\n".join(f"- {note}" for note in thought_map_user_notes)
        thought_map_notes_block = (
            "\n\n## USER NOTES FROM THOUGHT MAP\n"
            "Treat these notes as explicit user priorities for the next answer.\n"
            f"{notes_lines}"
        )

    state_json = json.dumps(dashboard_state, indent=2, default=str)
    system_content = (
        GENIE_SYSTEM_PROMPT
        + (f"\n\n## THOUGHT MAP DEPTH MODE\n{depth_insert}" if depth_insert else "")
        + f"\n\n## DB CONTEXT\n{db_context_prompt}"
        + thought_map_notes_block
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
            "⚠️ **No AI API key configured.**\n\n"
            "Set `DEEPSEEK_API_KEY` (or `OPENAI_API_KEY`) in HuggingFace Space secrets, "
            "or add your key in the sidebar under **🔑 AI Settings**."
        )
        st.warning(msg)
        return msg

    model = st.session_state.get("genie_model", _default_model())

    with st.chat_message("assistant", avatar="🧞"):
        placeholder = st.empty()
        node_counter = st.empty()  # Live node detection counter
        full_response = ""
        _detected_nodes = 0

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
                    # Escape $ during streaming to prevent LaTeX rendering
                    _display = re.sub(r'(?<!\$)\$(?!\$)', r'\\$', full_response)
                    placeholder.markdown(_display + "▌")
                    # Count reasoning markers as they arrive
                    new_count = full_response.upper().count("[STEP") + \
                                full_response.upper().count("[BRANCH") + \
                                full_response.upper().count("[CONCLUSION") + \
                                full_response.upper().count("[OBSERVATION") + \
                                full_response.upper().count("[ANALYSIS") + \
                                full_response.upper().count("[INFERENCE")
                    if new_count > _detected_nodes:
                        _detected_nodes = new_count
                        node_counter.markdown(
                            f"<div style='font-size:0.75rem;color:#ff8c42;padding:4px 0;'>"
                            f"Building thought map... {_detected_nodes} "
                            f"{'node' if _detected_nodes == 1 else 'nodes'} detected</div>",
                            unsafe_allow_html=True,
                        )

            placeholder.markdown(clean_thought_markers(full_response))
            node_counter.empty()  # Clear counter once done

        except Exception as exc:  # pragma: no cover
            error_msg = f"AI API issue: {str(exc)}"
            placeholder.warning(error_msg)
            node_counter.empty()
            return error_msg

    return full_response


@st.cache_data(ttl=3600, show_spinner=False)
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
