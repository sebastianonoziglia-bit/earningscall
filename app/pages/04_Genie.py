import streamlit as st

# Page config must be the first Streamlit command
st.set_page_config(page_title="Financial Genie (SPECIAL)", page_icon="🧞", layout="wide")

from utils.global_fonts import apply_global_fonts
apply_global_fonts()


from utils.page_transition import apply_page_transition_fix

# Apply fix for page transitions to prevent background bleed-through
apply_page_transition_fix()

# Import other libraries after page config
from utils.insights import get_company_insight, get_cagr_insight
from utils.auth import check_password
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import sqlite3
import re
import math
from datetime import datetime
from pathlib import Path
from data_processor import FinancialDataProcessor
from utils.data_loader import load_advertising_data, get_available_filters, read_excel_data
from utils.components import render_ai_assistant
from utils.styles import load_common_styles, load_genie_specific_styles
from utils.enhanced_chat_interface import render_enhanced_chat_interface
from utils.thought_map import render_thought_map, render_thought_map_controls, match_signal_category, add_queued_node, get_queued_nodes, clear_thought_map
from utils.m2_supply_data import get_m2_monthly_data, get_m2_annual_data, create_m2_visualization
from utils.fed_funds_data import get_fed_funds_annual_data
from utils.bitcoin_analysis import get_bitcoin_monthly_returns, create_bitcoin_monthly_returns_chart, render_bitcoin_analysis_section
from utils.inflation_analysis import render_inflation_methodology_section
from utils.inflation_calculator import create_inflation_analysis_box, add_inflation_selector, load_usd_inflation_table
from subscriber_data_processor import SubscriberDataProcessor
import logging
from functools import lru_cache
from utils.data_granularity import (
    get_available_granularity_options,
    get_day_labels_for_year,
    get_month_labels_for_year,
    get_quarter_labels_for_year,
    update_global_time_context,
)

# Import our Bitcoin integration module (optional; keep Genie functional if missing)
try:
    from integration_bitcoin_charts import integrate_bitcoin_inflation_features
except Exception:  # pragma: no cover
    integrate_bitcoin_inflation_features = None

# Set up logging
logging.basicConfig(level=logging.INFO)

# Apply shared styles
load_common_styles()
load_genie_specific_styles()

# Add header with language selector
from utils.header import render_header
from utils.language import get_text
st.session_state["active_nav_page"] = "genie"
st.session_state["_active_nav_page"] = "genie"
render_header()

def _render_ai_settings_controls(key_prefix: str = "sidebar"):
    ant_key = st.text_input(
        "Anthropic API Key",
        type="password",
        value=st.session_state.get("anthropic_api_key", ""),
        help="Get key at console.anthropic.com — stored in session only.",
        key=f"anthropic_api_key_input_{key_prefix}",
    )
    if ant_key:
        st.session_state["anthropic_api_key"] = ant_key
    try:
        from utils.anthropic_service import is_api_available
        if is_api_available():
            st.success("\u2713 Claude connected", icon="\U0001f916")
        else:
            st.caption(
                "Enter Anthropic key above or set ANTHROPIC_API_KEY as HuggingFace secret"
            )
    except Exception:
        pass
    st.markdown("<div style='margin-top:8px;border-top:1px solid rgba(255,255,255,0.1);padding-top:8px;'><span style='font-size:0.75rem;color:#6b7280;text-transform:uppercase;letter-spacing:.06em;'>OpenAI fallback</span></div>", unsafe_allow_html=True)
    oai_key = st.text_input(
        "OpenAI API Key",
        type="password",
        value=st.session_state.get("openai_api_key", ""),
        key=f"openai_api_key_input_{key_prefix}",
    )
    if oai_key:
        st.session_state["openai_api_key"] = oai_key
    current_model = st.session_state.get("genie_model", "gpt-4o")
    model_options = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
    st.selectbox(
        "Model",
        model_options,
        index=model_options.index(current_model) if current_model in model_options else 0,
        key=f"genie_model_select_{key_prefix}",
    )
    if st.button("\U0001f5d1 Clear Conversation", key=f"clear_genie_chat_{key_prefix}"):
        st.session_state["genie_history"] = []
        st.session_state["thought_map"] = {
            "nodes": {}, "edges": [], "root_ids": [], "version": 1
        }
        st.rerun()


# ── AI Settings hidden from user — keys managed via env/secrets only ──
# (Previously exposed API key inputs here; removed for production UX)

# Add SQL Assistant in the sidebar
from utils.sql_assistant_sidebar import render_sql_assistant_sidebar
if not st.session_state.get("hide_sidebar_nav", False):
    render_sql_assistant_sidebar()

# Company brand color mapping function
def get_company_color(company_name):
    """Return a brand-appropriate color for each company"""
    company_colors = {
        'Netflix': '#E50914',           # Netflix red
        'Spotify': '#1DB954',           # Spotify green
        'Amazon': '#FF9900',            # Amazon orange
        'Apple': '#A2AAAD',             # Apple silver/gray
        'Microsoft': '#00A4EF',         # Microsoft blue
        'Meta Platforms': '#1877F2',    # Meta/Facebook blue
        'Alphabet': '#4285F4',          # Google blue
        'Disney': '#113CCF',            # Disney blue
        'Paramount': '#0064FF',         # Paramount blue
        'Warner Bros. Discovery': '#00A0E5',  # WBD blue
        'Comcast': '#000000',           # Comcast black
        'Roku': '#662D91',              # Roku purple
    }
    
    # Return the mapped color or a default if company not in mapping
    return company_colors.get(company_name, '#808080')  # Default gray


# Check if user is logged in, redirect to Welcome page if not
# Always authenticated - no password check needed
from utils.time_utils import render_floating_clock
render_floating_clock()

# Initialize session state for data caching if not present
if 'data_cache' not in st.session_state:
    st.session_state.data_cache = {}

# Optimize caching for financial data - increased TTL and using hash_funcs
@st.cache_resource(ttl=3600*24, hash_funcs={FinancialDataProcessor: lambda _: None})
def get_data_processor():
    data_processor = FinancialDataProcessor()
    data_processor.load_data()
    return data_processor


@st.cache_resource(ttl=3600 * 24)
def get_subscriber_processor():
    return SubscriberDataProcessor()

# Cache filter options with longer TTL and prevent recomputation
@st.cache_data(ttl=3600*24)
def get_cached_filters():
    return get_available_filters()

# Cache year range computation with specific key
@st.cache_data(ttl=3600*24)
def get_available_years(companies_tuple, data_processor_id):
    all_years = []
    for company in companies_tuple:
        years = data_processor.get_available_years(company)
        all_years.extend(years)
    return sorted(list(set(all_years)))


@st.cache_data(ttl=3600 * 24)
def get_advertising_years():
    try:
        df = read_excel_data()
        if df is None or df.empty or "year" not in df.columns:
            return []
        years = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int).tolist()
        return sorted(set(years))
    except Exception:
        return []


@st.cache_data(ttl=3600 * 24)
def get_inflation_years():
    try:
        df = load_usd_inflation_table()
        if df is None or df.empty or "Year" not in df.columns:
            return []
        years = pd.to_numeric(df["Year"], errors="coerce").dropna().astype(int).tolist()
        return sorted(set(years))
    except Exception:
        return []


@st.cache_data(ttl=3600 * 24)
def get_m2_years():
    try:
        df = get_m2_annual_data(1900, datetime.now().year + 2)
        if df is None or df.empty or "year" not in df.columns:
            return []
        years = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int).tolist()
        return sorted(set(years))
    except Exception:
        return []


@st.cache_data(ttl=3600 * 24)
def get_fed_funds_years():
    try:
        df = get_fed_funds_annual_data(1900, datetime.now().year + 2, method="average")
        if df is None or df.empty or "year" not in df.columns:
            return []
        years = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int).tolist()
        return sorted(set(years))
    except Exception:
        return []


_GENIE_COMPANY_TICKERS = {
    "Alphabet": "GOOGL",
    "Amazon": "AMZN",
    "Apple": "AAPL",
    "Comcast": "CMCSA",
    "Disney": "DIS",
    "Meta Platforms": "META",
    "Meta": "META",
    "Microsoft": "MSFT",
    "Netflix": "NFLX",
    "Paramount": "PARA",
    "Paramount Global": "PARA",
    "Roku": "ROKU",
    "Spotify": "SPOT",
    "Warner Bros. Discovery": "WBD",
    "Warner Bros Discovery": "WBD",
}


COMPANY_BRAND_COLORS = {
    "alphabet": "#4285F4",
    "google": "#4285F4",
    "amazon": "#FF9900",
    "apple": "#555555",
    "meta": "#0866FF",
    "meta platforms": "#0866FF",
    "facebook": "#0866FF",
    "instagram": "#C13584",
    "whatsapp": "#25D366",
    "microsoft": "#00A4EF",
    "netflix": "#E50914",
    "disney": "#113CCF",
    "comcast": "#C01F33",
    "spotify": "#1DB954",
    "roku": "#6C2DC7",
    "warner bros": "#003087",
    "warner bros. discovery": "#003087",
    "paramount": "#0064FF",
    "snap": "#FFFC00",
    "snapchat": "#FFFC00",
    "pinterest": "#E60023",
    "nvidia": "#76B900",
}

TOPIC_NODE_COLORS = {
    "forward_signal": "#F87171",
    "macro": "#FBBF24",
    "comparison": "#A78BFA",
    "data": "#60A5FA",
    "risk": "#EF4444",
    "segment": "#34D399",
    "transcript": "#FB923C",
    "default": "#94A3B8",
}


def _company_to_ticker(company: str) -> str:
    return _GENIE_COMPANY_TICKERS.get(str(company).strip(), "")


def _canon_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _quarter_focus_to_number(label: str):
    if not label or str(label).strip().lower() == "all quarters":
        return None
    match = re.search(r"([1-4])", str(label))
    return int(match.group(1)) if match else None


@st.cache_data(ttl=3600 * 6)
def _load_quarterly_company_metrics_sheet(excel_path: str) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    try:
        q_df = pd.read_excel(excel_path, sheet_name="Company_Quarterly_segments_valu")
    except Exception:
        return pd.DataFrame()

    if q_df is None or q_df.empty:
        return pd.DataFrame()

    q_df = q_df.copy()
    q_df.columns = [str(col).strip() for col in q_df.columns]
    rename_map = {col: re.sub(r"[^a-z0-9]+", "_", str(col).strip().lower()).strip("_") for col in q_df.columns}
    q_df = q_df.rename(columns=rename_map)

    if "ticker" not in q_df.columns or "year" not in q_df.columns:
        return pd.DataFrame()

    q_df["ticker"] = q_df["ticker"].astype(str).str.strip().str.upper()
    q_df["year"] = pd.to_numeric(q_df["year"], errors="coerce")
    q_df = q_df.dropna(subset=["ticker", "year"]).copy()
    if q_df.empty:
        return pd.DataFrame()
    q_df["year"] = q_df["year"].astype(int)

    q_df = q_df.sort_index().copy()
    q_df["quarter"] = q_df.groupby(["ticker", "year"]).cumcount() + 1

    return q_df


@st.cache_data(ttl=3600 * 6)
def _get_quarterly_years_for_companies(excel_path: str, companies: tuple) -> list:
    q_df = _load_quarterly_company_metrics_sheet(excel_path)
    if q_df.empty or not companies:
        return []
    tickers = {t for t in (_company_to_ticker(c) for c in companies) if t}
    if not tickers:
        return []
    years = (
        q_df[q_df["ticker"].isin(tickers)]["year"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )
    return sorted(set(years))


# ── Local transcript file reader ─────────────────────────────────────────────
_TRANSCRIPT_ROOT = Path(__file__).resolve().parents[2] / "earningscall_transcripts"
_COMPANY_NAME_NORMALIZE = {
    "Paramount_Global": "Paramount Global",
    "Warner_Bros_Discovery": "Warner Bros. Discovery",
    "Meta Platforms": "Meta Platforms",
}


def _normalize_company_folder(folder_name: str) -> str:
    return _COMPANY_NAME_NORMALIZE.get(folder_name, folder_name.replace("_", " ").strip())


@st.cache_data(ttl=3600)
def _load_local_transcripts_index() -> dict:
    """Scan earningscall_transcripts/ folder and return {(company, year, quarter): path}."""
    index: dict = {}
    root = _TRANSCRIPT_ROOT
    if not root.exists():
        return index
    for company_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        company = _normalize_company_folder(company_dir.name)
        for year_dir in sorted(p for p in company_dir.iterdir() if p.is_dir() and p.name.isdigit()):
            year = int(year_dir.name)
            for txt in sorted(year_dir.glob("Q[1-4].txt")):
                quarter = txt.stem.upper()
                index[(company, year, quarter)] = str(txt)
    return index


@st.cache_data(ttl=3600)
def _read_local_transcript(company: str, year: int, quarter: str) -> str:
    """Read a single transcript from local files."""
    idx = _load_local_transcripts_index()
    path = idx.get((company, year, quarter))
    if not path:
        for key, p in idx.items():
            if key[0].lower() == company.lower() and key[1] == year and key[2] == quarter.upper():
                path = p
                break
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return ""


@st.cache_data(ttl=3600)
def _get_transcript_index(excel_path: str) -> dict:
    """
    Build a lightweight index of available transcripts.
    Tries Google Sheet first, falls back to local .txt files.
    """
    # Try Google Sheet first
    if excel_path:
        try:
            index_df = pd.read_excel(
                excel_path,
                sheet_name="Transcripts",
                usecols=["company", "year", "quarter"],
            )
            if index_df is not None and not index_df.empty:
                result = {}
                for _, row in index_df.iterrows():
                    company = str(row.get("company", "")).strip()
                    year = pd.to_numeric(row.get("year"), errors="coerce")
                    quarter = str(row.get("quarter", "")).strip()
                    if not company or pd.isna(year) or not quarter:
                        continue
                    key = f"{company} {int(year)} {quarter}"
                    result[key] = True
                if result:
                    return result
        except Exception:
            pass

    # Fallback: local transcript files
    local_idx = _load_local_transcripts_index()
    return {f"{c} {y} {q}": True for (c, y, q) in local_idx.keys()}


@st.cache_data(ttl=3600)
def _search_transcript(excel_path: str, company: str, year: int, quarter: str) -> str:
    """Fetch a specific transcript. Tries Google Sheet, falls back to local files."""
    # Try Google Sheet first
    if excel_path:
        try:
            transcripts_df = pd.read_excel(excel_path, sheet_name="Transcripts")
            if transcripts_df is not None and not transcripts_df.empty:
                required = {"company", "year", "quarter", "transcript_text"}
                if required.issubset(set(transcripts_df.columns)):
                    mask = (
                        transcripts_df["company"].astype(str).str.lower().str.strip() == str(company).lower().strip()
                    ) & (
                        pd.to_numeric(transcripts_df["year"], errors="coerce") == int(year)
                    ) & (
                        transcripts_df["quarter"].astype(str).str.upper().str.strip() == str(quarter).upper().strip()
                    )
                    result = transcripts_df[mask]
                    if not result.empty:
                        return str(result.iloc[0].get("transcript_text", "") or "")
        except Exception:
            pass

    # Fallback: local transcript files
    return _read_local_transcript(company, int(year), str(quarter).upper().strip())


@st.cache_data(ttl=3600)
def _get_active_overview_auto_insights(excel_path: str) -> list[dict]:
    """
    Load active Overview_Auto_Insights rows for Genie system context.
    """
    if not excel_path:
        return []
    try:
        insights_df = pd.read_excel(excel_path, sheet_name="Overview_Auto_Insights")
    except Exception:
        return []
    if insights_df is None or insights_df.empty:
        return []

    insights_df.columns = [str(col).strip().lower() for col in insights_df.columns]
    if "is_active" in insights_df.columns:
        active_series = pd.to_numeric(insights_df["is_active"], errors="coerce").fillna(0).astype(int)
        insights_df = insights_df[active_series == 1]
    if insights_df.empty:
        return []

    if "sort_order" in insights_df.columns:
        insights_df["sort_order"] = pd.to_numeric(insights_df["sort_order"], errors="coerce")
        insights_df = insights_df.sort_values(["sort_order"], na_position="last")

    fields = [
        "insight_id", "category", "title", "text", "comment", "priority",
        "companies", "kpis", "graph_type", "year", "quarter"
    ]
    available_fields = [field for field in fields if field in insights_df.columns]
    if not available_fields:
        return []

    cleaned_rows = []
    for _, row in insights_df[available_fields].iterrows():
        entry = {}
        for field in available_fields:
            value = row.get(field)
            if pd.isna(value):
                value = ""
            entry[field] = value
        cleaned_rows.append(entry)
    return cleaned_rows

@st.cache_data(ttl=3600)
def _extract_forward_signals(excel_path: str, company: str = "", max_signals: int = 200) -> list:
    FORWARD_TRIGGERS = [
        "we expect","we anticipate","we are targeting","we plan to","we intend to",
        "our outlook","looking ahead","heading into","next quarter","full year guidance",
        "we remain confident","we believe","going forward","guidance","we project",
        "we forecast","we see opportunity","we are investing","opportunity ahead",
        "positioned to","we continue to expect","for the year"
    ]
    CATEGORY_KEYWORDS = {
        "AI & Technology": [
            "ai","artificial intelligence","machine learning","cloud","compute","model",
            "llm","gemini","copilot","gpt","neural","language model","automation","robotics",
            "data center","infrastructure","generative","algorithm","inference","training",
        ],
        "Advertising": [
            "advertising","ad revenue","ad market","monetization","arpu","cpm","impressions",
            "sponsored","programmatic","brand","campaign","targeting","measurement",
            "agency","upfront","performance marketing","demand","supply side",
        ],
        "Subscribers & Users": [
            "subscribers","users","dau","mau","engagement","retention","churn","paid members",
            "streaming","audience","reach","active users","monthly active","daily active",
            "signups","premium","conversion",
        ],
        "Revenue & Growth": [
            "revenue","growth","top line","year over year","yoy","outperform","beat",
            "exceeded","record","strong","accelerating","trajectory",
        ],
        "Business Strategy": [
            "strategy","strategic","partnership","acquisition","merger","expand","launch",
            "invest","priority","focus","initiative","roadmap","transformation","pivot",
            "restructur","reorgani","new market","new product",
        ],
        "International Expansion": [
            "international","global","emea","apac","latin america","europe","asia","japan",
            "india","china","emerging market","region","cross-border","fx","currency",
            "foreign exchange","overseas",
        ],
        "Debt & Capital": [
            "debt","leverage","balance sheet","cash flow","free cash flow","fcf","buyback",
            "repurchase","dividend","capital allocation","credit","bond","financing","liquidity",
            "capex","capital expenditure","net debt","interest expense",
        ],
        "Competition": [
            "competition","competitive","market share","rival","competitor","differentiat",
            "moat","advantage","pricing","price war","ecosystem","switching",
            "incumbent","disrupt","win rate",
        ],
        "Product & Innovation": [
            "product","feature","release","update","version","build","develop",
            "innovation","r&d","research","design","user experience",
            "quality","performance","speed","scale",
        ],
        "Cost & Margin": [
            "cost","margin","efficiency","headcount","opex","restructur","expense",
            "savings","profitability","operating leverage","gross margin","ebitda",
            "cash generation","cost control","optimize","lean","scalable",
        ],
        "Macro & Market": [
            "macro","economy","recession","consumer","market condition","interest rate",
            "inflation","gdp","fiscal","monetary","fed","supply chain",
            "geopolit","uncertainty","slowdown","recovery","cycle",
        ],
        "Management Guidance": [
            "full year","next quarter","we project","we forecast","we plan","we intend",
            "looking ahead","we remain","we believe","going forward","positioned",
            "full year guidance","we continue to expect","for the year","target","we guide",
        ],
        "Investment & Acquisitions": [
            "we invested","we will invest","we committed","we are investing","invest in",
            "investment of","investments in","investing heavily","capital investment",
            "acquire","acquired","acquisition","purchase","purchased","purchasing",
            "buy","buying","bought","deal","transaction","takeover","merger",
            "joint venture","strategic investment","committed to","billion investment",
            "million investment","committed capital","deploying capital",
        ],
    }

    # Build list of (company, year, quarter, text) tuples from any available source
    transcript_rows: list[tuple] = []

    # Try Google Sheet first
    if excel_path:
        try:
            df = pd.read_excel(excel_path, sheet_name="Transcripts")
            if df is not None and not df.empty and {"company","year","quarter","transcript_text"}.issubset(set(df.columns)):
                if company:
                    df = df[df["company"].astype(str).str.lower().str.strip() == company.lower().strip()]
                for _, row in df.iterrows():
                    comp = str(row.get("company","")).strip()
                    yr = pd.to_numeric(row.get("year"), errors="coerce")
                    qtr = str(row.get("quarter","")).strip()
                    txt = str(row.get("transcript_text","") or "")
                    if txt and not pd.isna(yr):
                        transcript_rows.append((comp, int(yr), qtr, txt))
        except Exception:
            pass

    # Fallback: local transcript files
    if not transcript_rows:
        local_idx = _load_local_transcripts_index()
        for (comp, yr, qtr), path in local_idx.items():
            if company and comp.lower().strip() != company.lower().strip():
                continue
            try:
                txt = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
                if txt:
                    transcript_rows.append((comp, yr, qtr, txt))
            except Exception:
                continue

    if not transcript_rows:
        return []

    signals = []
    for comp, year, quarter, text in transcript_rows:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20 or len(sentence) > 500:
                continue
            s_lower = sentence.lower()
            if not any(trigger in s_lower for trigger in FORWARD_TRIGGERS):
                continue
            # Score all categories — pick highest match count for richer tagging
            best_cat = "Revenue & Growth"
            best_score = 0
            for cat, keywords in CATEGORY_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw in s_lower)
                if score > best_score:
                    best_score = score
                    best_cat = cat
            signals.append({"company": comp, "year": int(year), "quarter": quarter,
                             "signal": sentence, "category": best_cat})
            if len(signals) >= max_signals * 10:
                break
    seen = set()
    deduped = []
    for s in signals:
        key = s["signal"][:80]
        if key not in seen:
            seen.add(key)
            deduped.append(s)
    return deduped[:max_signals * 3]


# Update the mapping of macro categories to their detailed metrics
MACRO_CATEGORY_MAPPING = {
    'Television': ['Free TV', 'Pay TV'],  # Main category matching AD_MACRO_CATEGORIES
    'TELEVISION': ['Free TV', 'Pay TV'],  # Uppercase version for case-insensitive matching
    'TV': ['Free TV', 'Pay TV'],  # Keep TV for backward compatibility
    'Digital': ['Other Desktop', 'Other Mobile', 'Search Desktop', 'Search Mobile', 
                'Social Mobile', 'Video Mobile', 'Display Desktop', 'Display Mobile', 
                'Social Desktop', 'Video Desktop'],
    'OOH': ['Digital OOH', 'Traditional OOH'],
    'Press': ['Magazine', 'Newspaper'],
    'Radio': ['Radio'],  # Single metric categories
    'Cinema': ['Cinema']  # Single metric categories
}

# Optimize advertising data loading with specific key
@st.cache_data(ttl=3600)
def load_cached_advertising_data(countries_tuple, metrics_tuple, year_start, year_end):
    # Determine if we need to fetch detailed metrics based on macro categories
    detailed_metrics = []
    for metric in metrics_tuple:
        if metric in MACRO_CATEGORY_MAPPING:
            detailed_metrics.extend(MACRO_CATEGORY_MAPPING[metric])
        else:
            detailed_metrics.append(metric)

    filters = {
        'years': list(range(year_start, year_end + 1)),
        'countries': list(countries_tuple),
        'metrics': detailed_metrics
    }
    return load_advertising_data(filters)

# Update the data processing section to handle None values
@st.cache_data(ttl=3600)
def process_metrics_data(df, country, metric, _year_range):
    if df.empty:
        return None

    country_data = df[df['country'] == country]

    # Handle macro categories by summing their constituent metrics
    if metric in MACRO_CATEGORY_MAPPING:
        detailed_metrics = MACRO_CATEGORY_MAPPING[metric]
        metric_data = country_data[country_data['metric_type'].isin(detailed_metrics)]

        if not metric_data.empty:
            # Group by year and sum the values for all constituent metrics
            metric_data = metric_data.groupby('year', as_index=False)['value'].sum()
    else:
        metric_data = country_data[country_data['metric_type'] == metric]

    if metric_data.empty or len(metric_data) < 2:
        return None

    metric_data = metric_data.sort_values('year')
    values = metric_data['value'].tolist()

    # Calculate YoY changes
    yoy_changes = []
    for i in range(len(values)):
        if i > 0:
            current_val = values[i]
            prev_val = values[i-1]
            yoy_change = ((current_val - prev_val) / prev_val * 100) if prev_val != 0 else 0
        else:
            yoy_change = 0
        yoy_changes.append(yoy_change)

    return {
        'years': metric_data['year'].tolist(),
        'values': values,
        'yoy_changes': yoy_changes
    }


# Initialize data processor with caching
if 'data_processor' not in st.session_state:
    st.session_state['data_processor'] = get_data_processor()

data_processor = st.session_state['data_processor']
filter_options = get_cached_filters()

# Add custom styling for select chips to the Genie page styles
st.markdown("""
<style>
/* Fix suggestion chip buttons — light background, dark text */
div[data-testid="stButton"] button {
    background-color: #f3f4f6 !important;
    color: #111827 !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 20px !important;
    font-size: 0.82rem !important;
    padding: 6px 14px !important;
    font-weight: 500 !important;
}
div[data-testid="stButton"] button:hover {
    background-color: #e5e7eb !important;
    color: #111827 !important;
    border-color: #d1d5db !important;
}
    /* Company Analysis section chips */
    [data-testid="stMultiSelect"]:has([aria-label*="Select Companies"]) .st-emotion-cache-12w0qpk,
    [data-testid="stMultiSelect"]:has([aria-label*="Company Metrics"]) .st-emotion-cache-12w0qpk,
    [data-testid="stMultiSelect"]:has([aria-label*="Company Segments"]) .st-emotion-cache-12w0qpk {
        background-color: #f3e5f5;
        border-color: #9c27b0;
    }

    [data-testid="stMultiSelect"]:has([aria-label*="Select Companies"]) .st-emotion-cache-12w0qpk:hover,
    [data-testid="stMultiSelect"]:has([aria-label*="Company Metrics"]) .st-emotion-cache-12w0qpk:hover,
    [data-testid="stMultiSelect"]:has([aria-label*="Company Segments"]) .st-emotion-cache-12w0qpk:hover {
        background-color: #e1bee7;
        border-color: #7b1fa2;
    }

    /* Ad Spend Analysis section chips */
    [data-testid="stMultiSelect"]:has([aria-label*="Select Countries"]) .st-emotion-cache-12w0qpk,
    [data-testid="stMultiSelect"]:has([aria-label*="Ad Spend Categories"]) .st-emotion-cache-12w0qpk,
    [data-testid="stMultiSelect"]:has([aria-label*="Ad Spend Metrics"]) .st-emotion-cache-12w0qpk {
        background-color: #e8f0fe;
        border-color: #4285f4;
    }

    /* ── Fix: hide Material Icons text when font fails to load ("arrow_right" etc.) ── */
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary * {
        font-size: 0 !important;
        color: transparent !important;
    }
    [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
    [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] * {
        font-size: 0.875rem !important;
        color: #e6edf3 !important;
    }
    [data-testid="stExpander"] summary svg,
    [data-testid="stExpander"] summary svg * {
        color: #94a3b8 !important;
        visibility: visible !important;
    }

    /* ── Fix multiselect pill text clipping ── */
    [data-testid="stMultiSelect"] [data-baseweb="tag"] {
        overflow: visible !important;
        max-width: none !important;
        padding-left: 10px !important;
    }
    [data-testid="stMultiSelect"] [data-baseweb="tag"] > span:first-child {
        overflow: visible !important;
        text-overflow: unset !important;
        white-space: nowrap !important;
        padding-left: 2px !important;
    }
    [data-testid="stMultiSelect"] [data-baseweb="input"] {
        overflow: visible !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&display=swap');
.genie-hdr{padding:20px 0 16px 0;border-bottom:1px solid #f1f5f9;margin-bottom:20px;}
.genie-hdr-label{font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:#ff5b1f;font-weight:700;margin-bottom:6px;}
.genie-hdr-title{font-family:'Syne',sans-serif;font-size:2rem;font-weight:800;color:#0f172a;line-height:1.1;margin:0 0 6px 0;}
.genie-hdr-title .acc{color:#ff5b1f;}
.genie-hdr-sub{font-size:0.88rem;color:#6b7280;margin:0 0 10px 0;}
.genie-hdr-tags{display:flex;gap:8px;flex-wrap:wrap;}
.genie-hdr-tag{background:#fff7f4;border:1px solid #fed7aa;color:#c2410c;padding:2px 10px;border-radius:999px;font-size:11px;font-weight:600;}
</style>
<div class="genie-hdr">
  <div class="genie-hdr-label">AI FINANCIAL ANALYST</div>
  <div class="genie-hdr-title">Financial Genie <span class="acc">↗</span></div>
  <p class="genie-hdr-sub">Company KPIs · Advertising spend · Macro overlays · Earnings transcript AI</p>
  <div class="genie-hdr-tags">
    <span class="genie-hdr-tag">Company Analysis</span>
    <span class="genie-hdr-tag">Ad Spend</span>
    <span class="genie-hdr-tag">Macro Indicators</span>
    <span class="genie-hdr-tag">Earnings Intelligence</span>
  </div>
</div>
""", unsafe_allow_html=True)

def load_recession_periods():
    """
    Deprecated: recession shading previously used a hard-coded list.
    Keep for backward compatibility but return an empty frame (no hard-coded data).
    """
    return pd.DataFrame(columns=["period", "start_year", "end_year", "description"])


@st.cache_data(ttl=3600 * 24)
def _get_usd_inflation_series(source: str = "Official") -> dict:
    """
    Return a {year: inflation_rate_pct} dict from the 'USD Inflation' sheet.
    """
    from utils.inflation_calculator import load_usd_inflation_table

    df = load_usd_inflation_table()
    if df is None or df.empty:
        return {}

    col_map = {
        "Official": "Official Headline CPI",
        # Keep the existing UI label "Alternative" but source it from the sheet.
        "Alternative": "ShadowStats 1980s Method*",
    }
    col = col_map.get(source, col_map["Official"])
    if "Year" not in df.columns or col not in df.columns:
        return {}

    sub = df[["Year", col]].dropna().copy()
    sub["Year"] = pd.to_numeric(sub["Year"], errors="coerce").astype("Int64")
    sub[col] = pd.to_numeric(sub[col], errors="coerce")
    sub = sub.dropna(subset=["Year", col])
    return {int(y): float(v) for y, v in zip(sub["Year"].astype(int), sub[col].astype(float))}

def adjust_for_purchasing_power(value, year):
    """
    Adjust value based on USD purchasing power for given year.
    E.g., if a value was $100 in 2020 (purchasing power 0.64),
    it would be adjusted to $64 to show the real purchasing power decline.
    """
    # Use the USD Inflation sheet to compute a purchasing-power adjustment factor
    # (convert nominal values into "base-year dollars").
    from utils.inflation_calculator import get_price_index

    try:
        year_int = int(year)
    except Exception:
        return value

    base_year = st.session_state.get("purchasing_power_base_year", 2000)
    try:
        base_year = int(base_year)
    except Exception:
        base_year = 2000

    idx = get_price_index("Official Headline CPI")
    if idx is None or idx.empty or year_int not in idx.index or base_year not in idx.index:
        return value

    factor = float(idx.loc[base_year]) / float(idx.loc[year_int])
    return value * factor

def format_large_number(value):
    """Format large numbers to billions/millions/thousands for readability"""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if abs(value) >= 1e12:  # Trillions
        return f"${value/1e12:.2f}T"
    elif abs(value) >= 1e9:  # Billions
        return f"${value/1e9:.2f}B"
    elif abs(value) >= 1e6:  # Millions
        return f"${value/1e6:.2f}M"
    elif abs(value) >= 1e3:  # Thousands
        return f"${value/1e3:.1f}K"
    else:
        return f"${value:,.2f}"

# Initialize session state for search
if 'search_country' not in st.session_state:
    st.session_state.search_country = ""

# Create main columns for the layout
col1, col2 = st.columns(2)

with col1:
    # Company Analysis Section
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader("📊 Company Analysis")

    # Company selection
    companies = data_processor.get_companies()
    selected_companies = st.multiselect(
        "Select Companies",
        options=companies,
        default=[companies[0]] if companies else None,
        key="company_selector"
    )

    # Company metrics selection
    if selected_companies:
        # Available company metrics
        available_metrics = {
            'Revenue': 'revenue',
            'Operating Income': 'operating_income',
            'Net Income': 'net_income',
            'R&D': 'rd',
            'Total Assets': 'total_assets',
            'Debt': 'debt',
            'Market Cap': 'market_cap',
            'Cost of Revenue': 'cost_of_revenue',
            'Capex': 'capex',
            'Cash Balance': 'cash_balance'  # Added Cash Balance metric
        }
        
        # Allow selecting both financial metrics and segments

        st.markdown("##### Company Data Options")
        st.markdown("""
        <div style="color: #666; font-size: 0.85rem; margin-bottom: 8px;">
        You can select both financial metrics and segments to display simultaneously
        </div>
        """, unsafe_allow_html=True)

        # Financial metrics section
        selected_company_metrics = st.multiselect(
            "Select Company Financial Metrics",
            options=list(available_metrics.keys()),
            default=['Revenue'],
            help="Select financial metrics to compare across companies",
            key="company_metrics_selector"
        )
        
        # Segment selection section
        # Helper function to get segments for a company/year
        @st.cache_data(ttl=3600, show_spinner=False)
        def get_company_segments_for_selection(company, excel_path):
            """Get actual segment names for a company from the workbook."""
            try:
                # Try the yearly segments sheet first
                try:
                    df = pd.read_excel(excel_path, sheet_name="Company_yearly_segments_values")
                except Exception:
                    df = pd.DataFrame()

                if df.empty:
                    # Fallback: read from quarterly segment sheets (e.g. "Alphabet Quarterly Segments")
                    try:
                        xl = pd.ExcelFile(excel_path)
                        comp_norm = str(company).strip().lower()
                        matching_sheet = None
                        for sheet in xl.sheet_names:
                            if "quarterly segments" in sheet.lower():
                                sheet_comp = sheet.replace("Quarterly Segments", "").strip()
                                for _sfx in ("Granular", "Gran"):
                                    if sheet_comp.endswith(_sfx):
                                        sheet_comp = sheet_comp[:-len(_sfx)].strip()
                                if sheet_comp.lower() == comp_norm or comp_norm.startswith(sheet_comp.lower()[:6]):
                                    matching_sheet = sheet
                                    break
                        if matching_sheet:
                            df_q = pd.read_excel(excel_path, sheet_name=matching_sheet)
                            df_q.columns = [str(c).strip() for c in df_q.columns]
                            # Find the segment column — prefer column named "segment",
                            # then fall back to first non-numeric/non-quarter column
                            seg_col = None
                            for c in df_q.columns:
                                if "segment" in c.lower():
                                    seg_col = c
                                    break
                            if not seg_col:
                                # Fallback: first column that isn't year/quarter/numeric
                                for c in df_q.columns:
                                    cl = c.lower()
                                    if cl not in ("year", "quarter", "q", "date", "period") and not cl.replace(".", "", 1).isdigit():
                                        seg_col = c
                                        break
                            if seg_col:
                                segments = df_q[seg_col].dropna().unique().tolist()
                                segments = [str(s).strip() for s in segments if str(s).strip() and not str(s).strip().replace('.','',1).replace('-','',1).isdigit()]
                                return [(company, seg) for seg in sorted(segments)]
                        return []
                    except Exception:
                        return []

                df.columns = [str(c).strip().lower() for c in df.columns]
                comp_col = "company" if "company" in df.columns else df.columns[0]
                seg_col = next((c for c in df.columns if "segment" in c), None)
                if not seg_col:
                    return []
                df["_comp"] = df[comp_col].astype(str).str.strip().str.lower()
                comp_norm = str(company).strip().lower()
                comp_df = df[df["_comp"] == comp_norm]
                if comp_df.empty:
                    comp_df = df[df["_comp"].str.contains(comp_norm[:6], na=False)]
                if comp_df.empty:
                    return []
                segments = comp_df[seg_col].dropna().unique().tolist()
                segments = [str(s).strip() for s in segments if str(s).strip()]
                return [(company, seg) for seg in sorted(segments)]
            except Exception:
                return []

        # Get segments for all selected companies
        segment_options = []
        excel_path = str(data_processor.data_path) if hasattr(data_processor, 'data_path') else ""
        for company in selected_companies:
            company_segments = get_company_segments_for_selection(company, excel_path)
            segment_options.extend(company_segments)
        
        # Format segment options for display
        formatted_segment_options = [f"{company}: {segment}" for company, segment in segment_options]
        
        # Add a divider with stronger visual distinction
        st.markdown("""
        <div style="margin: 15px 0 10px 0; border-top: 2px solid #4CAF50; position: relative;">
            <div style="position: absolute; top: -12px; left: 10px; background-color: white; padding: 0 10px; color: #4CAF50; font-weight: bold; font-size: 0.9rem;">
                SEGMENTS
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Segment selection without redundant explanation
        
        selected_segment_options = st.multiselect(
            "Select Company Segments",
            options=formatted_segment_options,
            default=[],
            help="Select segments to compare their revenue performance across years. Segments from different companies can be compared directly."
        )
        
        # Add a note about simultaneous viewing if both types selected
        if selected_company_metrics and selected_segment_options:
            st.success("✓ You're viewing both financial metrics and segments on the same chart for direct comparison! Segments have their own Y-axis labeled 'Segment Values'.")
        elif selected_segment_options:
            st.info("💡 Segment data will be displayed with distinctive dotted lines and diamond markers on a dedicated Y-axis.")
        elif selected_company_metrics and formatted_segment_options:
            st.info("💡 You can select both financial metrics and segments to view them on the same chart with separate Y-axes!")
        
        # Parse the selected segments back to (company, segment) tuples
        selected_segments = []
        for selected in selected_segment_options:
            company, segment = selected.split(": ", 1)
            selected_segments.append((company, segment))
        
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    # Ad Spend Analysis Section
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader("📈 Country Ad Spend Analysis")
    # Country search and selection
    country_search = st.text_input(
        "Search Countries",
        value=st.session_state.search_country,
        placeholder="Type to search countries...",
        key="country_search"
    )
    country_query = (country_search or "").strip().lower()
    st.session_state.search_country = country_search

    # Filter countries based on search (excluding Global) with normalized values.
    available_countries = sorted(
        {
            str(c).strip()
            for c in filter_options.get("countries", [])
            if str(c).strip() and str(c).strip().lower() != "global"
        }
    )
    filtered_countries = (
        [country for country in available_countries if country_query in country.lower()]
        if country_query
        else available_countries
    )

    if "country_selector" not in st.session_state:
        default_country = "Italy" if "Italy" in available_countries else (available_countries[0] if available_countries else None)
        st.session_state["country_selector"] = [default_country] if default_country else []
    else:
        # Keep only still-valid countries in the current workbook.
        st.session_state["country_selector"] = [
            c for c in st.session_state.get("country_selector", []) if c in available_countries
        ]

    # Keep selected countries visible even when search query narrows options.
    options_for_multiselect = list(filtered_countries)
    for c in st.session_state.get("country_selector", []):
        if c not in options_for_multiselect:
            options_for_multiselect.insert(0, c)

    selected_countries = st.multiselect(
        "Select Countries",
        options=options_for_multiselect,
        help="Select one or more countries to analyze",
        key="country_selector"
    )
    selected_countries = [c for c in selected_countries if c in available_countries]

    if country_query and not filtered_countries:
        st.caption("No countries match that search.")

    # Ad spend metric selection
    metric_selection_mode = st.radio(
        "Ad Spend Metric Type",
        options=["Macro Categories", "Detailed Metrics"],
        horizontal=True,
        key="metric_type_selector"
    )

    if metric_selection_mode == "Macro Categories":
        selected_ad_metrics = st.multiselect(
            "Select Ad Spend Categories",
            options=filter_options['macro_categories'],
            default=['Digital'] if 'Digital' in filter_options['macro_categories'] else filter_options['macro_categories'][:1],
            key="macro_categories_selector"
        )
        selected_metrics = selected_ad_metrics
        selected_detailed_metrics = []
        for category in selected_ad_metrics:
            selected_detailed_metrics.extend(filter_options['ad_type_mappings'].get(category, []))
    else:
        selected_detailed_metrics = st.multiselect(
            "Select Ad Spend Metrics",
            options=filter_options['ad_types'],
            default=['Free TV'] if 'Free TV' in filter_options['ad_types'] else filter_options['ad_types'][:1],
            key="detailed_metrics_selector"
        )
        selected_metrics = selected_detailed_metrics
    st.markdown("</div>", unsafe_allow_html=True)

# Add CSS for layout improvements including tight spacing and consistent headers
st.markdown("""
<style>
    /* Flex layout for section headers */
    .section-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        padding-bottom: 0;
        border-bottom: 1px solid #eee;
    }
    .section-title {
        font-size: 1.3rem;
        font-weight: 600;
        margin: 0;
        padding: 0;
        padding-bottom: 0.5rem;
    }
    
    /* Flex layout for content columns */
    .options-content, .insights-content {
        width: 100%;
    }
    
    /* Override Streamlit's default column styling */
    [data-testid="column"] {
        padding: 0 10px !important;
    }
    .option-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        grid-gap: 8px;
        margin-bottom: 10px;
    }
    .option-item {
        padding: 4px;
        margin-bottom: 0;
    }
    .option-item h4 {
        margin-top: 0;
        margin-bottom: 4px;
        font-size: 0.95rem;
    }
    .option-item .stCheckbox {
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .option-item .stRadio {
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .option-item .stSelectbox {
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .insights-container {
        margin-top: 15px;
        padding-top: 10px;
    }
    
    .insights-content {
        margin-top: 15px;
        padding: 10px;
        background-color: #f9f9f9;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# Small spacer before the macro expander
st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

# Polished macro-indicator expander: dark panel, clear checkboxes, orange accents.
st.markdown(
    """
    <style>
    /* ── Macro Indicators Expander Panel ─────────────────────── */
    div[data-testid="stExpander"]:has(summary:first-child) {
        background: rgba(15, 23, 42, 0.55) !important;
        border: 1px solid rgba(255, 91, 31, 0.25) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }
    /* Expander header (toggle bar) — color set on label only, not summary (avoids showing icon text) */
    div[data-testid="stExpander"] summary {
        background: rgba(15, 23, 42, 0.7) !important;
        padding: 12px 16px !important;
        border-radius: 12px !important;
    }
    div[data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
    div[data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] * {
        color: #e6edf3 !important;
        font-weight: 600 !important;
    }
    div[data-testid="stExpander"] summary:hover {
        background: rgba(255, 91, 31, 0.12) !important;
    }
    /* Expander body */
    div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] {
        padding: 12px 16px 16px !important;
    }

    /* ── Checkbox rows ───────────────────────────────────────── */
    div[data-testid="stExpander"] div[data-testid="stCheckbox"] label {
        display: flex !important;
        align-items: center !important;
        gap: 0.55rem !important;
        width: auto !important;
        padding: 6px 10px !important;
        border-radius: 8px !important;
        cursor: pointer !important;
        transition: background 0.15s ease !important;
    }
    div[data-testid="stExpander"] div[data-testid="stCheckbox"] label:hover {
        background: rgba(255, 255, 255, 0.06) !important;
    }

    /* Checkbox box — unchecked state */
    div[data-testid="stExpander"] div[data-testid="stCheckbox"] label > div:first-child {
        flex: 0 0 20px !important;
        width: 20px !important;
        height: 20px !important;
    }
    div[data-testid="stExpander"] div[data-testid="stCheckbox"] label > div:first-child > div {
        width: 20px !important;
        height: 20px !important;
        border: 2px solid rgba(255, 255, 255, 0.35) !important;
        border-radius: 4px !important;
        background: transparent !important;
        transition: all 0.15s ease !important;
    }
    /* Checkbox box — checked state (Streamlit adds aria-checked="true") */
    div[data-testid="stExpander"] div[data-testid="stCheckbox"] label[data-checked="true"] > div:first-child > div,
    div[data-testid="stExpander"] div[data-testid="stCheckbox"] input:checked ~ div > div {
        background: #ff5b1f !important;
        border-color: #ff5b1f !important;
    }
    /* The SVG checkmark icon inside */
    div[data-testid="stExpander"] div[data-testid="stCheckbox"] svg {
        color: #ffffff !important;
        stroke: #ffffff !important;
    }

    /* Label text */
    div[data-testid="stExpander"] div[data-testid="stCheckbox"] label > div:last-child,
    div[data-testid="stExpander"] div[data-testid="stCheckbox"] label > div:last-child * {
        writing-mode: horizontal-tb !important;
        text-orientation: mixed !important;
        white-space: normal !important;
        width: auto !important;
        max-width: 100% !important;
        display: inline !important;
        line-height: 1.3 !important;
        letter-spacing: normal !important;
        word-break: normal !important;
        overflow-wrap: normal !important;
        color: #e6edf3 !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
    }

    /* ── Radio / selectbox inside expander ────────────────────── */
    div[data-testid="stExpander"] div[data-testid="stRadio"] [data-baseweb="button-group"] {
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 0.5rem !important;
    }
    div[data-testid="stExpander"] div[data-testid="stRadio"] [data-baseweb="button-group"] button {
        white-space: nowrap !important;
        min-width: 120px !important;
    }

    /* Help tooltips — remove extra border box, integrate into parent */
    div[data-testid="stExpander"] [data-testid="stTooltipIcon"] {
        color: rgba(255, 255, 255, 0.4) !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
        display: inline-flex !important;
        align-items: center !important;
        vertical-align: middle !important;
        padding: 0 !important;
        margin-left: 4px !important;
    }
    [data-testid="stTooltipIcon"] {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
        display: inline-flex !important;
        padding: 0 !important;
    }
    [data-testid="stTooltipIcon"] svg {
        color: rgba(255,255,255,0.35) !important;
        width: 14px !important;
        height: 14px !important;
    }

    /* Checkbox label text — ensure high contrast in all states */
    div[data-testid="stExpander"] div[data-testid="stCheckbox"] label p,
    div[data-testid="stExpander"] div[data-testid="stCheckbox"] label span {
        color: #e6edf3 !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
    }

    /* Selectbox / multiselect inside expander */
    div[data-testid="stExpander"] div[data-baseweb="select"] {
        background: rgba(255, 255, 255, 0.07) !important;
        border-color: rgba(255, 255, 255, 0.15) !important;
        border-radius: 8px !important;
    }
    div[data-testid="stExpander"] div[data-baseweb="select"] * {
        color: #e6edf3 !important;
    }

    /* ── Global checkbox readability on dark pages ─────────── */
    div[data-testid="stCheckbox"] label p,
    div[data-testid="stCheckbox"] label span,
    div[data-testid="stCheckbox"] label > div:last-child,
    div[data-testid="stCheckbox"] label > div:last-child * {
        color: #e6edf3 !important;
    }

    /* ── Button borders — unified component look ─────────── */
    div[data-testid="stCheckbox"] label {
        border: none !important;
    }
    div[data-testid="stCheckbox"] label > div:first-child {
        border: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Organize options into expanders to reduce clutter
show_fed_funds = False
fed_funds_aggregation = "Annual Average"
with st.expander("⚡ Macro Overlays — M2 · Inflation · Fed Rate · Recession · Subscribers", expanded=False):
    # Row 1 - Basic Options
    basic_cols = st.columns([1, 1])
    
    with basic_cols[0]:
        show_global = st.checkbox(
            "Show Global Data",
            value=False,
            help="Show global data on secondary axis",
            key="show_global"
        )
        
        show_growth_rates = st.checkbox(
            "Show Growth Rates",
            value=False,
            help="Display Year-over-Year percentage growth rates instead of absolute values",
            key="show_growth_rates"
        )
    
    with basic_cols[1]:
        show_recessions = st.checkbox(
            "Show Recession Periods",
            value=False,
            help="(Disabled) Recession shading requires a dedicated sheet; hard-coded periods were removed.",
            key="recession_checkbox"
        )
        
        show_m2_supply = st.checkbox(
            "M2 Money Supply",
            value=False,
            help="Display M2 Money Supply data with monthly growth rates",
            key="m2_supply_checkbox"
        )

        show_subscribers = st.checkbox(
            "Subscribers / Users",
            value=False,
            help="Plot subscriber/user counts from the 'Company_subscribers_values' sheet (annualized).",
            key="subscribers_checkbox",
        )
        if show_subscribers:
            sub_proc = get_subscriber_processor()
            services = sub_proc.get_service_names() if sub_proc else []
            st.session_state["selected_services"] = st.multiselect(
                "Select Services",
                options=services,
                default=[],
                key="selected_services_multiselect",
            )
    
    # Without additional header inside
    advanced_cols = st.columns([1, 1])
    
    with advanced_cols[0]:
        show_inflation = st.checkbox(
            "Show USD Inflation Rates",
            value=False,
            help="Display USD inflation rates alongside financial data",
            key="show_inflation_checkbox"
        )
        
        if show_inflation:
            inflation_type = st.selectbox(
                "Inflation Source",
                ["Official", "Alternative"],
                key="inflation_type"
            )
    
    with advanced_cols[1]:
        adjust_purchasing_power = st.checkbox(
            "Adjust for USD Purchasing Power",
            value=False,
            help="Convert values to real terms using historical USD purchasing power",
            key="purchasing_power_checkbox"
        )
        show_fed_funds = st.checkbox(
            "Fed Funds Rate",
            value=False,
            help="Overlay Federal Funds Rate from the 'Fed Fund Rates' sheet.",
            key="fed_funds_checkbox",
        )
        if show_fed_funds:
            fed_funds_aggregation = st.selectbox(
                "Fed Funds Aggregation",
                ["Annual Average", "Year-End"],
                key="fed_funds_aggregation",
            )
        if adjust_purchasing_power:
            from utils.inflation_calculator import load_usd_inflation_table

            _tbl = load_usd_inflation_table()
            _years = []
            if _tbl is not None and not _tbl.empty and "Year" in _tbl.columns:
                _years = sorted(set(_tbl["Year"].dropna().astype(int).tolist()))
            if _years:
                st.session_state["purchasing_power_base_year"] = st.selectbox(
                    "Purchasing Power Base Year",
                    options=_years,
                    index=0,
                    key="purchasing_power_base_year_select",
                    help="Values will be adjusted into base-year dollars using the USD Inflation sheet.",
                )

# Year range selector positioned right below the options row
excel_path = getattr(data_processor, "data_path", "")
year_candidates = set()

# Company years
if selected_companies:
    year_candidates.update(get_available_years(tuple(selected_companies), id(data_processor)))
    year_candidates.update(_get_quarterly_years_for_companies(excel_path, tuple(selected_companies)))

# Country advertising years
if selected_metrics or show_global:
    year_candidates.update(get_advertising_years())

# Inflation years (needed both for chart overlay and purchasing power adjustment)
if show_inflation or adjust_purchasing_power:
    year_candidates.update(get_inflation_years())

# M2 years
if show_m2_supply:
    year_candidates.update(get_m2_years())

# Fed funds years
if show_fed_funds:
    year_candidates.update(get_fed_funds_years())

# Always include baseline range so slider is never too narrow
year_candidates.update(range(2010, datetime.now().year + 1))

all_years = sorted(int(y) for y in year_candidates if y is not None)
if not all_years:
    all_years = list(range(2010, datetime.now().year + 1))

# Ensure min < max to prevent RangeError on slider
if len(all_years) < 2 or min(all_years) >= max(all_years):
    all_years = list(range(2010, datetime.now().year + 1))

year_range = st.slider(
    "Select Year Range",
    min_value=min(all_years),
    max_value=max(all_years),
    value=(min(all_years), max(all_years)),
    key="year_range_selector"
)

# Cross-page temporal context (shared with Overview and future SQL assistant/widget).
granularity_options = get_available_granularity_options(excel_path, include_auto=True)
current_granularity = st.session_state.get("genie_selected_granularity", "Auto")
if current_granularity not in granularity_options:
    current_granularity = granularity_options[0] if granularity_options else "Auto"

time_col1, time_col2, time_col3 = st.columns([1.0, 1.0, 1.0])
with time_col1:
    selected_granularity = st.radio(
        "Granularity",
        options=granularity_options,
        index=granularity_options.index(current_granularity),
        key="genie_selected_granularity",
        horizontal=True,
    )

selected_quarter_focus = "All Quarters"
selected_month_focus = None
selected_day_focus = None
focus_year = int(year_range[1])

with time_col2:
    quarter_labels = get_quarter_labels_for_year(
        excel_path,
        focus_year,
        sheet_preferences=("Company_subscribers_values", "Overview_Insights", "Overview_Macro"),
    )
    if not quarter_labels:
        quarter_labels = ["Q1", "Q2", "Q3", "Q4"]
    quarter_focus_options = ["All Quarters"] + quarter_labels
    current_q_focus = st.session_state.get("genie_selected_quarter_focus", "All Quarters")
    if current_q_focus not in quarter_focus_options:
        current_q_focus = "All Quarters"
    selected_quarter_focus = st.radio(
        f"Quarter ({focus_year})",
        options=quarter_focus_options,
        index=quarter_focus_options.index(current_q_focus),
        key="genie_selected_quarter_focus",
        horizontal=True,
        disabled=selected_granularity not in {"Auto", "Quarterly"},
    )

with time_col3:
    if selected_granularity == "Monthly":
        month_labels = get_month_labels_for_year(excel_path, focus_year)
        if month_labels:
            current_month_focus = st.session_state.get("genie_selected_month_focus", month_labels[-1])
            if current_month_focus not in month_labels:
                current_month_focus = month_labels[-1]
            selected_month_focus = st.selectbox(
                f"Month Focus ({focus_year})",
                options=month_labels,
                index=month_labels.index(current_month_focus),
                key="genie_selected_month_focus",
                help="Context filter for monthly-aware analysis.",
            )
        else:
            st.caption(f"No monthly rows for {focus_year}.")
    elif selected_granularity == "Daily":
        day_labels = get_day_labels_for_year(excel_path, focus_year)
        if day_labels:
            current_day_focus = st.session_state.get("genie_selected_day_focus", day_labels[-1])
            if current_day_focus not in day_labels:
                current_day_focus = day_labels[-1]
            selected_day_focus = st.selectbox(
                f"Day Focus ({focus_year})",
                options=day_labels,
                index=day_labels.index(current_day_focus),
                key="genie_selected_day_focus",
                help="Context filter for daily-aware analysis.",
            )
        else:
            st.caption(f"No daily rows for {focus_year}.")
    else:
        st.caption("Month/Day focus activates in Monthly or Daily mode.")

st.session_state["genie_time_context"] = update_global_time_context(
    page="Genie",
    granularity=selected_granularity,
    year=focus_year,
    quarter=selected_quarter_focus if selected_quarter_focus != "All Quarters" else None,
    month=selected_month_focus,
    day=selected_day_focus,
    year_range=(int(year_range[0]), int(year_range[1])),
    excel_path=excel_path,
)

# Initialize inflation_type in session_state if not already present
if 'inflation_type' not in st.session_state:
    st.session_state.inflation_type = "Official"

# Add Global to selected countries if enabled
all_selected_countries = selected_countries.copy()
if show_global:
    all_selected_countries.append('Global')


# Initialize selected_segments variable so it's always defined
if 'selected_segment_options' in locals() and selected_segment_options:
    selected_segments = []
    for selected in selected_segment_options:
        company, segment = selected.split(": ", 1)
        selected_segments.append((company, segment))
else:
    selected_segments = []
    
# Create visualizations when any data selection is made 
if (
    selected_metrics
    or ("selected_company_metrics" in locals() and selected_company_metrics)
    or ("selected_segment_options" in locals() and selected_segment_options)
    or show_global
    or show_m2_supply
    or show_inflation
    or show_fed_funds
):
    # We can display both company metrics AND segments simultaneously on the same chart
    # Create visualization
    fig = go.Figure()

    # Load recession data if needed
    recession_df = load_recession_periods() if show_recessions else None

    # Create color mapping for consistent colors
    color_sequence = [
        '#4285F4', '#ff5b1f', '#1DB954', '#E50914', '#7C3AED',
        '#0866FF', '#FF9900', '#C13584', '#25D366', '#113CCF'
    ]
                     
    # Store color mapping in session state to reference in detailed insights
    if 'color_mapping' not in st.session_state:
        st.session_state.color_mapping = {}

    # Track max values for each axis
    country_max_values = []
    global_max_values = []
    company_max_values = []

    # Process advertising data if metrics are selected or show_global is True
    # Note: We process advertising data even if company metrics are selected (removed the dependency)
    if selected_metrics and all_selected_countries or show_global:
        df = load_cached_advertising_data(
            tuple(all_selected_countries),
            tuple(selected_metrics),
            year_range[0],
            year_range[1]
        )

        logging.info(f"Loaded data frame with shape: {df.shape if df is not None else 'None'}")

        if df is not None and not df.empty:
            for country in all_selected_countries:
                for metric in selected_metrics:
                    processed_data = process_metrics_data(df, country, metric, year_range)

                    if processed_data:
                        is_global = country == 'Global'
                        yaxis = 'y2' if is_global else 'y'

                        color_index = len(fig.data) % len(color_sequence)
                        base_color = color_sequence[color_index]

                        if is_global:
                            color = base_color.replace('rgb', 'rgba').replace(')', ', 0.3)')
                        else:
                            color = base_color
                            
                        # Store the color in session state for reference in insights
                        trace_name = f"{country} - {metric}"
                        st.session_state.color_mapping[trace_name] = base_color

                        values = processed_data['values']
                        if adjust_purchasing_power:
                            values = [adjust_for_purchasing_power(val, year) for val, year in zip(values, processed_data['years'])]
                        
                        # If show_growth_rates is checked, use YoY changes instead of actual values
                        display_values = processed_data['yoy_changes'] if show_growth_rates else values
                        
                        # Format for hover display depends on what we're showing
                        if show_growth_rates:
                            # When showing growth rates, the main value is the YoY change percentage
                            hover_values = [f"{change:.1f}%" for change in processed_data['yoy_changes']]
                            value_label = "YoY Growth"
                            # The customdata will contain the actual value for reference
                            custom_values = [format_large_number(val) for val in values]
                            hover_template = (
                                f"<b>{country} - {metric}</b><br>" +
                                "Year: %{x}<br>" +
                                f"{value_label}: %{{customdata[0]}}<br>" +
                                "Actual Value: %{customdata[1]}<br>" +
                                "<extra></extra>"
                            )
                            # Zip the growth percentage and actual value for hover data
                            custom_values = list(zip(hover_values, custom_values))
                        else:
                            # When showing actual values, the customdata contains YoY change
                            hover_values = [format_large_number(val) for val in values]
                            value_label = "Value"
                            # Format YoY changes with percentage sign
                            formatted_yoy = [f"{yoy:.1f}%" for yoy in processed_data['yoy_changes']]
                            custom_values = formatted_yoy
                            hover_template = (
                                f"<b>{country} - {metric}</b><br>" +
                                "Year: %{x}<br>" +
                                f"{value_label}: {hover_values}<br>" +
                                "YoY Change: %{customdata}<br>" +
                                "<extra></extra>"
                            )

                        fig.add_trace(go.Scatter(
                            x=processed_data['years'],
                            y=display_values,
                            name=f"{country} - {metric}",
                            mode='lines+markers',
                            marker=dict(size=5),
                            line=dict(
                                color=color,
                                width=1.5,
                                dash='dot' if is_global else None
                            ),
                            customdata=custom_values,
                            hovertemplate=hover_template,
                            yaxis=yaxis
                        ))

                        for i in range(len(processed_data['values'])):
                            if is_global:
                                global_max_values.append(processed_data['values'][i])
                            else:
                                country_max_values.append(processed_data['values'][i])


    quarterly_company_metrics_df = _load_quarterly_company_metrics_sheet(excel_path)
    prefer_quarterly_metrics = (
        selected_granularity in {"Auto", "Quarterly"} and not quarterly_company_metrics_df.empty
    )
    quarter_focus_num = _quarter_focus_to_number(selected_quarter_focus)

    def _resolve_quarterly_metric_column(metric_key: str):
        if quarterly_company_metrics_df.empty:
            return None
        canonical = {_canon_col(col): col for col in quarterly_company_metrics_df.columns}
        candidate_tokens = [
            metric_key,
            metric_key.replace("_", ""),
            metric_key.replace("_", " "),
        ]
        if metric_key == "rd":
            candidate_tokens.extend(["r&d", "r_and_d"])
        if metric_key == "cash_balance":
            candidate_tokens.extend(["cash", "cash balance"])
        for token in candidate_tokens:
            match = canonical.get(_canon_col(token))
            if match:
                return match
        return None

    def _get_quarterly_metric_point(company: str, year: int, metric_key: str):
        if not prefer_quarterly_metrics:
            return None
        ticker = _company_to_ticker(company)
        if not ticker:
            return None
        metric_col = _resolve_quarterly_metric_column(metric_key)
        if not metric_col:
            return None

        scoped = quarterly_company_metrics_df[
            (quarterly_company_metrics_df["ticker"] == ticker) &
            (quarterly_company_metrics_df["year"] == int(year))
        ].copy()
        if scoped.empty:
            return None
        if quarter_focus_num is not None:
            scoped = scoped[scoped["quarter"] == quarter_focus_num].copy()
            if scoped.empty:
                return None

        scoped = scoped.sort_values("quarter")
        row = scoped.iloc[-1]
        value = pd.to_numeric(row.get(metric_col), errors="coerce")
        if pd.isna(value):
            return None
        quarter_value = pd.to_numeric(row.get("quarter"), errors="coerce")
        period_label = f"{int(year)} Q{int(quarter_value)}" if not pd.isna(quarter_value) else f"{int(year)}"
        return {"value": float(value), "period_label": period_label}

    # Helper function to get and log company metric data
    @lru_cache(maxsize=32)
    def get_cached_company_years(company):
        annual_years = set(data_processor.get_available_years(company))
        if prefer_quarterly_metrics:
            ticker = _company_to_ticker(company)
            if ticker:
                q_years = (
                    quarterly_company_metrics_df[quarterly_company_metrics_df["ticker"] == ticker]["year"]
                    .dropna()
                    .astype(int)
                    .unique()
                    .tolist()
                )
                annual_years.update(q_years)
        return sorted(int(y) for y in annual_years)

    @lru_cache(maxsize=32)
    def get_cached_metrics(company, year):
        return data_processor.get_metrics(company, year)
        
    @lru_cache(maxsize=32)
    def get_cached_segments(company, year):
        return data_processor.get_segments(company, year)

    def get_company_metric_data(company, metric_name, metric_key, filtered_years, data_processor):
        metric_data = []
        try:
            for year in filtered_years:
                quarterly_point = _get_quarterly_metric_point(company, int(year), metric_key)
                if quarterly_point:
                    value = quarterly_point["value"]
                    metric_data.append({
                        'year': int(year),
                        'value': value,
                        'period_label': quarterly_point["period_label"],
                    })
                    company_max_values.append(value)
                    logging.info(
                        "Loaded %s for %s in %s from quarterly sheet: %s",
                        metric_name,
                        company,
                        quarterly_point["period_label"],
                        value,
                    )
                    continue

                metrics = get_cached_metrics(company, year)
                if metrics and metric_key in metrics:
                    value = metrics[metric_key]
                    if value is not None:
                        metric_data.append({
                            'year': int(year),
                            'value': value,
                            'period_label': f"{int(year)} FY",
                        })
                        company_max_values.append(value)
                        logging.info(f"Loaded {metric_name} for {company} in {year}: {value}")
                else:
                    logging.warning(f"No {metric_name} data for {company} in {year}")
        except Exception as e:
            logging.error(f"Error loading {metric_name} for {company}: {str(e)}")
        return metric_data
        
    def get_segment_data(company, segment_name, filtered_years):
        """Get data for a specific segment across multiple years"""
        segment_data = []
        try:
            for year in filtered_years:
                segments = get_cached_segments(company, year)
                if segments and 'labels' in segments and 'values' in segments:
                    # Find index of segment name in labels list
                    if segment_name in segments['labels']:
                        idx = segments['labels'].index(segment_name)
                        value = segments['values'][idx]
                        if value is not None:
                            segment_data.append({
                                'year': year,
                                'value': value
                            })
                            company_max_values.append(value)
                            logging.info(f"Loaded segment {segment_name} for {company} in {year}: {value}")
                else:
                    logging.warning(f"No segment data for {company} in {year}")
        except Exception as e:
            logging.error(f"Error loading segment {segment_name} for {company}: {str(e)}")
        return segment_data

    # Process company data
    if selected_companies and selected_company_metrics:
        for company in selected_companies:
            company_years = get_cached_company_years(company)
            filtered_years = [y for y in company_years if year_range[0] <= y <= year_range[1]]

            for metric_name in selected_company_metrics:
                metric_key = available_metrics[metric_name]
                metric_data = get_company_metric_data(company, metric_name, metric_key, filtered_years, data_processor)

                if metric_data:
                    df_metric = pd.DataFrame(metric_data)
                    df_metric = df_metric.sort_values('year')

                    if adjust_purchasing_power:
                        df_metric['value'] = df_metric.apply(lambda row: adjust_for_purchasing_power(row['value'], row['year']), axis=1)

                    # Calculate YoY changes
                    yoy_changes = []
                    for i in range(len(df_metric)):
                        if i > 0:
                            current_val = df_metric.iloc[i]['value']
                            prev_val = df_metric.iloc[i-1]['value']
                            yoy_change = ((current_val - prev_val) / prev_val * 100) if prev_val != 0 else 0
                        else:
                            yoy_change = 0
                        yoy_changes.append(yoy_change)

                    hover_values = [format_large_number(val) for val in df_metric['value']]
                    period_labels = (
                        df_metric["period_label"].astype(str).tolist()
                        if "period_label" in df_metric.columns
                        else [str(int(y)) for y in df_metric["year"].tolist()]
                    )

                    # Determine a color index for this metric
                    color_index = len(fig.data) % len(color_sequence)
                    base_color = color_sequence[color_index]
                    
                    # Store the color in session state for reference in insights
                    trace_name = f"{company} - {metric_name} (Metric)"
                    st.session_state.color_mapping[trace_name] = base_color
                    
                    # Use distinctive styling for financial metrics - solid lines and circle markers
                    # If show_growth_rates is checked, use YoY changes instead of actual values
                    display_values = yoy_changes if show_growth_rates else df_metric['value']
                    
                    # Format hover information based on what we're displaying
                    if show_growth_rates:
                        # When showing growth rates, the main value is the YoY change percentage
                        formatted_growth = [f"{yoy:.1f}%" for yoy in yoy_changes]
                        hover_template = (
                            f"<b>{company} - {metric_name}</b><br>" +
                            "Year: %{x}<br>" +
                            "Period Source: %{customdata[2]}<br>" +
                            "YoY Growth: %{customdata[0]}<br>" +
                            "Actual Value: %{customdata[1]}<br>" +
                            "<b>Type: Financial Metric</b><br>" +
                            "<extra></extra>"
                        )
                        custom_data = list(zip(formatted_growth, hover_values, period_labels))
                    else:
                        # When showing actual values, customdata contains the YoY changes with % formatting
                        formatted_yoy = [f"{yoy:.1f}%" for yoy in yoy_changes]
                        hover_template = (
                            f"<b>{company} - {metric_name}</b><br>" +
                            "Year: %{x}<br>" +
                            "Period Source: %{customdata[2]}<br>" +
                            "Value: %{customdata[1]}<br>" +
                            "YoY Change: %{customdata[0]}<br>" +
                            "<b>Type: Financial Metric</b><br>" +
                            "<extra></extra>"
                        )
                        custom_data = list(zip(formatted_yoy, hover_values, period_labels))
                        
                    fig.add_trace(go.Scatter(
                        x=df_metric['year'],
                        y=display_values,
                        name=f"{company} - {metric_name} (Metric)",
                        mode='lines+markers',
                        marker=dict(
                            size=6,
                            symbol='circle',
                            color=get_company_color(company),
                            line=dict(width=1, color='rgba(255,255,255,0.6)')
                        ),
                        line=dict(
                            width=2,
                            color=get_company_color(company),
                            shape='linear'
                        ),
                        customdata=custom_data,
                        hovertemplate=hover_template,
                        yaxis='y4'  # Use a separate y-axis for company metrics
                    ))
    
    # Process segment data if selected
    if selected_segments:
        for company, segment_name in selected_segments:
            company_years = get_cached_company_years(company)
            filtered_years = [y for y in company_years if year_range[0] <= y <= year_range[1]]
            
            segment_data = get_segment_data(company, segment_name, filtered_years)
            
            if segment_data:
                df_segment = pd.DataFrame(segment_data)
                df_segment = df_segment.sort_values('year')
                
                if adjust_purchasing_power:
                    df_segment['value'] = df_segment.apply(lambda row: adjust_for_purchasing_power(row['value'], row['year']), axis=1)
                
                # Calculate YoY changes
                yoy_changes = []
                for i in range(len(df_segment)):
                    if i > 0:
                        current_val = df_segment.iloc[i]['value']
                        prev_val = df_segment.iloc[i-1]['value']
                        yoy_change = ((current_val - prev_val) / prev_val * 100) if prev_val != 0 else 0
                    else:
                        yoy_change = 0
                    yoy_changes.append(yoy_change)
                
                hover_values = [format_large_number(val) for val in df_segment['value']]
                
                # Use distinctive styling for segment traces so they're easy to distinguish from metrics
                # Determine a color index, then get a base color and create semi-transparent version
                color_index = len(fig.data) % len(color_sequence)
                base_color = color_sequence[color_index]
                
                # Store the color in session state for reference in insights
                trace_name = f"{company} - {segment_name} (Segment)"
                st.session_state.color_mapping[trace_name] = base_color
                
                # If show_growth_rates is checked, use YoY changes instead of actual values
                display_values = yoy_changes if show_growth_rates else df_segment['value']
                
                # Format hover information based on what we're displaying
                if show_growth_rates:
                    # When showing growth rates, the main value is the YoY change percentage
                    formatted_growth = [f"{yoy:.1f}%" for yoy in yoy_changes]
                    hover_template = (
                        f"<b>{company} - {segment_name}</b><br>" +
                        "Year: %{x}<br>" +
                        "YoY Growth: %{customdata[0]}<br>" +
                        "Actual Value: %{customdata[1]}<br>" +
                        "<b>Type: Business Segment</b><br>" +
                        "<extra></extra>"
                    )
                    custom_data = list(zip(formatted_growth, hover_values))  # Both growth and values
                else:
                    # When showing actual values, customdata contains the YoY changes with % formatting
                    formatted_yoy = [f"{yoy:.1f}%" for yoy in yoy_changes]
                    hover_template = (
                        f"<b>{company} - {segment_name}</b><br>" +
                        "Year: %{x}<br>" +
                        "Value: %{customdata[1]}<br>" +
                        "YoY Change: %{customdata[0]}<br>" +
                        "<b>Type: Business Segment</b><br>" +
                        "<extra></extra>"
                    )
                    custom_data = list(zip(formatted_yoy, hover_values))
                
                # Create a segment trace with enhanced styling
                fig.add_trace(go.Scatter(
                    x=df_segment['year'],
                    y=display_values,
                    name=f"{company} - {segment_name} (Segment)",
                    mode='lines+markers',
                    marker=dict(
                        size=7,
                        symbol='diamond',
                        color=base_color,
                        line=dict(width=1, color='rgba(0,0,0,0.3)'),
                        opacity=0.9
                    ),
                    line=dict(
                        dash='dash',
                        width=1.5,
                        color=base_color,
                        shape='spline'
                    ),
                    opacity=0.9,
                    customdata=custom_data,
                    hovertemplate=hover_template,
                    yaxis='y5'  # Use a dedicated y-axis for segments
                ))

    # Add recession periods if enabled
    if show_recessions and recession_df is not None:
        filtered_recessions = recession_df[
            (recession_df['start_year'] >= year_range[0]) &
            (recession_df['end_year'] <= year_range[1])
        ]

        for _, period in filtered_recessions.iterrows():
            fig.add_vrect(
                x0=str(period['start_year']),
                x1=str(period['end_year']),
                fillcolor="lightgray",
                opacity=0.2,
                layer="below",
                line_width=0,
                annotation=dict(
                    text=period['period'],
                    textangle=-90,
                    font=dict(size=10),
                    x=(period['start_year'] + period['end_year']) / 2,
                    y=1.02,
                    showarrow=False
                )
            )

    fed_rate_min_value = None
    fed_rate_max_value = None

    # Add inflation rate if enabled
    if show_inflation:
        # Use the value from session state to ensure consistency
        inflation_type_value = st.session_state.inflation_type
        series = _get_usd_inflation_series(inflation_type_value)
        inflation_years = sorted(y for y in series.keys() if year_range[0] <= y <= year_range[1])
        inflation_values = [series[y] for y in inflation_years]

        # Use proper label that includes the source information
        source_label = "USD Inflation (sheet)" if inflation_type_value == "Official" else "Alternative Inflation (sheet)"
        
        fig.add_trace(go.Scatter(
            x=inflation_years,
            y=inflation_values,
            name=f'USD Inflation Rate ({source_label})',
            mode='lines+markers',
            line=dict(width=2, dash='dot', color='rgba(255, 0, 0, 0.3)'),
            marker=dict(size=6, color='rgba(255, 0, 0, 0.3)'),
            yaxis='y3',
            hovertemplate="<b>%{data.name}</b><br>" +
                          "Year: %{x}<br>" +
                          "Rate: %{y:.1f}%<br>" +
                          "<extra></extra>"
        ))

    # Add Fed Funds rate if enabled
    if show_fed_funds:
        fed_method = "average" if fed_funds_aggregation == "Annual Average" else "year_end"
        fed_df = get_fed_funds_annual_data(
            start_year=year_range[0],
            end_year=year_range[1],
            method=fed_method,
        )
        if fed_df is None or fed_df.empty:
            st.info(
                "Fed Funds Rate sheet not found or empty. "
                "Expected sheet name like 'Fed Fund Rates' with date/year and rate columns."
            )
        else:
            fed_values = pd.to_numeric(fed_df["value"], errors="coerce").dropna()
            if not fed_values.empty:
                fed_rate_min_value = float(fed_values.min())
                fed_rate_max_value = float(fed_values.max())
            fig.add_trace(
                go.Scatter(
                    x=fed_df["year"].astype(int),
                    y=fed_df["value"].astype(float),
                    name=f"Fed Funds Rate ({fed_funds_aggregation})",
                    mode="lines+markers",
                    line=dict(width=2, dash="solid", color="rgba(245, 158, 11, 0.9)"),
                    marker=dict(size=6, color="rgba(245, 158, 11, 0.9)"),
                    yaxis="y8",
                    hovertemplate="<b>%{data.name}</b><br>"
                    + "Year: %{x}<br>"
                    + "Rate: %{y:.2f}%<br>"
                    + "<extra></extra>",
                )
            )

    # Calculate axis ranges and steps
    country_max = max(country_max_values) if country_max_values else 0
    global_max = max(global_max_values) if global_max_values else 0
    company_max = max(company_max_values) if company_max_values else 0

    def get_axis_range_and_step(max_val):
        """Calculate appropriate axis range and step size based on data"""
        if max_val <= 100:  # For values up to 100M
            step = 10
            upper_limit = min(100, max_val * 1.2)  # 20% padding
        elif max_val <= 500:  # For values up to 500M
            step = 50
            upper_limit = min(500, max_val * 1.1)
        elif max_val <= 1000:  # For values up to 1B
            step = 100
            upper_limit = min(1000, max_val * 1.1)
        else:
            step = round(max_val / 5, -2)  # Round to nearest hundred
            upper_limit = max_val * 1.1

        return [0, upper_limit], step

    # Get range and step for country axis
    country_range, country_step = get_axis_range_and_step(country_max)

    # Initialize layout dictionary with default settings
    layout_dict = {
        'title': dict(text="Financial Analysis", font=dict(family="'DM Sans', Inter, sans-serif", size=13, color="#111827"), x=0, pad=dict(b=8)),
        'height': 520,
        'xaxis_title': "Year",
        'yaxis': dict(
            title=dict(
                text="Country Values" + (" (YoY % Change)" if show_growth_rates else " (In millions of USD)"),
                font=dict(size=11, color="#111827"),
            ),
            side="left",
            showgrid=True,
            gridcolor="rgba(0,0,0,0.06)",
            range=country_range if not show_growth_rates else [-50, 50],
            tickformat=',',
            dtick=country_step if not show_growth_rates else 10,
            tickfont=dict(color="#111827"),
        ),
        'showlegend': True,
        'legend': dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#111827"),
        ),
        'margin': dict(t=50, l=50, r=120, b=50),
        'plot_bgcolor': 'white',
        'paper_bgcolor': 'white',
        'font': dict(family="'DM Sans', Inter, sans-serif", size=12, color="#111827"),
    }

    # Initialize M2 growth variable before using it
    show_m2_growth = False
    if 'show_m2_growth' in st.session_state:
        show_m2_growth = st.session_state.show_m2_growth
        
    # Calculate how many right-side axes we need to display
    right_axes_count = sum([
        show_global,
        show_inflation,
        show_fed_funds,
        bool(selected_companies and selected_company_metrics),
        bool('selected_segments' in locals() and selected_segments),
        show_m2_supply and not show_m2_growth  # Only when showing absolute M2 values
    ])
    
    # Adjust axis positions based on the number of right-side axes
    # The more axes we have, the more we need to distribute them
    right_side_spacing = 0.05 if right_axes_count <= 3 else 0.04
    
    # Set the starting position from right edge
    current_position = 1.0
    
    # Add Global axis if needed
    if show_global:
        current_position -= right_side_spacing
        layout_dict['yaxis2'] = dict(
            title=dict(text="Global Values" + (" (YoY % Change)" if show_growth_rates else " (In millions of USD)"), font=dict(size=11, color='#111827')),
            overlaying="y",
            side="right",
            anchor="free",
            position=current_position,
            showgrid=False,
            range=[-50, 50] if show_growth_rates else ([0, global_max * 1.1] if global_max > 0 else None),
            tickformat=',',
            tickfont=dict(size=10, color='#111827'),
            tickmode='auto',
            nticks=6
        )

    # Add inflation axis if needed
    if show_inflation:
        current_position -= right_side_spacing
        layout_dict['yaxis3'] = dict(
            title=dict(text="USD Inflation Rate (%)", font=dict(size=11, color='#111827')),
            overlaying="y",
            side="right",
            anchor="free",
            position=current_position,
            showgrid=False,
            range=[0, 15],
            tickformat='.1f',
            tickfont=dict(size=10, color='#111827')
        )

    # Add Fed Funds axis if needed
    if show_fed_funds:
        current_position -= right_side_spacing
        fed_range = None
        if fed_rate_min_value is not None and fed_rate_max_value is not None:
            fed_pad = max(0.5, (fed_rate_max_value - fed_rate_min_value) * 0.2)
            fed_low = min(0.0, fed_rate_min_value - fed_pad)
            fed_high = fed_rate_max_value + fed_pad
            if fed_high <= fed_low:
                fed_high = fed_low + 1.0
            fed_range = [fed_low, fed_high]
        layout_dict['yaxis8'] = dict(
            title=dict(text=f"Fed Funds Rate (%) [{fed_funds_aggregation}]", font=dict(size=11, color='#111827')),
            overlaying="y",
            side="right",
            anchor="free",
            position=current_position,
            showgrid=False,
            range=fed_range,
            tickformat='.2f',
            tickfont=dict(size=10, color='#111827'),
            tickmode='auto',
            nticks=6
        )
    
    # Add Company metrics axis if needed
    if selected_companies and selected_company_metrics:
        current_position -= right_side_spacing
        layout_dict['yaxis4'] = dict(
            title=dict(text="Company Values" + (" (YoY % Change)" if show_growth_rates else " (In millions of USD)"), font=dict(size=11, color='#111827')),
            overlaying="y",
            side="right",
            anchor="free",
            position=current_position,
            showgrid=False,
            range=[-50, 50] if show_growth_rates else ([0, company_max * 1.1] if company_max > 0 else None),
            tickformat=',',
            tickfont=dict(size=10, color='#111827'),
            tickmode='auto',
            nticks=6
        )
        
    # Add dedicated segment axis if needed
    if 'selected_segments' in locals() and selected_segments:
        current_position -= right_side_spacing
        layout_dict['yaxis5'] = dict(
            title=dict(text="Segment Values" + (" (YoY % Change)" if show_growth_rates else " (In millions of USD)"), font=dict(size=11, color='#111827')),
            overlaying="y",
            side="right",
            anchor="free",
            position=current_position,
            showgrid=False,
            range=[-50, 50] if show_growth_rates else ([0, company_max * 1.1] if company_max > 0 else None),
            tickformat=',',
            tickfont=dict(size=10, color='#111827'),
            tickmode='auto',
            nticks=6
        )

    # Add M2 money supply data if enabled
    if show_m2_supply:
        m2_axis_title = "M2 Supply (Billions USD, Real)" if adjust_purchasing_power else "M2 Supply (Billions USD)"
        # Add additional UI controls for M2 supply visualization in a sidebar section
        with st.sidebar.expander("M2 Money Supply Options", expanded=True):
            # Use checkboxes to allow selecting both annual and monthly views simultaneously
            show_annual_m2 = st.checkbox(
                "Show Annual Data",
                value=True,
                key="show_annual_m2",
                help="Display annual M2 supply data as a line"
            )
            
            show_monthly_m2 = st.checkbox(
                "Show Monthly Data",
                value=False,
                key="show_monthly_m2",
                help="Display monthly M2 supply data as bars"
            )
            
            # Independent toggle for M2 growth rates (separate from main metrics growth rate toggle)
            show_m2_growth = st.checkbox(
                "Show M2 Growth Rates",
                value=False,
                help="Display growth rates for M2 data (adds a growth rate line while keeping the M2 supply values visible)",
                key="show_m2_growth"
            )
        
        # Get M2 data directly
        from utils.m2_supply_data import get_m2_annual_data, get_m2_monthly_data
        
        # Flag to track if we need to add M2 axes
        m2_axis_added = False
        max_m2_value = 0
        
        # Get annual data if selected
        if show_annual_m2:
            # Get the annual M2 data and make sure it includes the current year (2025)
            annual_m2_df = get_m2_annual_data(year_range[0], year_range[1])
            if not annual_m2_df.empty:
                annual_m2_df = annual_m2_df.sort_values("year").copy()
                if adjust_purchasing_power:
                    annual_m2_df["value"] = annual_m2_df.apply(
                        lambda row: adjust_for_purchasing_power(row["value"], row["year"]),
                        axis=1,
                    )
                    annual_m2_df["annual_growth"] = annual_m2_df["value"].pct_change() * 100.0
                # Log the data we have for debugging
                current_year = datetime.now().year
                logging.info(f"M2 annual data years: {annual_m2_df['year'].unique()}")
                if current_year in annual_m2_df['year'].values:
                    logging.info(f"Current year ({current_year}) M2 value: {annual_m2_df[annual_m2_df['year'] == current_year]['value'].iloc[0]}")
                
                if not annual_m2_df.empty:
                    # Add annual line chart
                    fig.add_trace(go.Scatter(
                        x=annual_m2_df['year'],
                        y=annual_m2_df['value'],
                        name=f"M2 Supply Annual ({'Real' if adjust_purchasing_power else 'Nominal'})",
                        line=dict(color='#1f77b4', width=3),
                        mode='lines',
                        yaxis='y6',  # Use yaxis6 to match the layout definition
                        hovertemplate='Year: %{x}<br>M2 Supply: $%{y:,.0f} Billion<br><extra></extra>'
                    ))
                    max_m2_value = max(max_m2_value, max(annual_m2_df['value']))
                    m2_axis_added = True
                    
                    # Store annual growth data for later if needed
                    annual_growth_field = 'annual_growth'
                    annual_x_field = 'year'
        
        # Get monthly data if selected
        if show_monthly_m2:
            monthly_m2_df = get_m2_monthly_data()
            if not monthly_m2_df.empty:
                monthly_m2_df = monthly_m2_df.sort_values("date").copy()
                if adjust_purchasing_power:
                    monthly_m2_df["value"] = monthly_m2_df.apply(
                        lambda row: adjust_for_purchasing_power(
                            row["value"],
                            row["date"].year if hasattr(row["date"], "year") else row["year"],
                        ),
                        axis=1,
                    )
                    monthly_m2_df["monthly_growth"] = monthly_m2_df["value"].pct_change() * 100.0
                # For monthly data, we need to filter by year component
                # Handle datetime.date objects which are the most common case
                if hasattr(monthly_m2_df['date'].iloc[0], 'year'):
                    # Filter by year attribute of date objects
                    monthly_m2_df = monthly_m2_df[(monthly_m2_df['date'].apply(lambda x: x.year) >= year_range[0]) & 
                                               (monthly_m2_df['date'].apply(lambda x: x.year) <= year_range[1])]
                    
                    if not monthly_m2_df.empty:
                        # Create a separate bar chart below the main chart for monthly data
                        # We'll keep the original data granularity (monthly)
                        
                        # First, ensure we have proper date objects
                        if not hasattr(monthly_m2_df['date'].iloc[0], 'year'):
                            st.warning("Monthly data dates are not in a proper format")
                        else:
                            # Filter to the selected year range
                            filtered_monthly = monthly_m2_df[(monthly_m2_df['date'].apply(lambda x: x.year) >= year_range[0]) & 
                                                         (monthly_m2_df['date'].apply(lambda x: x.year) <= year_range[1])]
                            
                            # Create custom x-values that are evenly spaced
                            years = range(year_range[0], year_range[1] + 1)
                            
                            # For each year, create background bars to represent the monthly data
                            for year in years:
                                # Get the data for this year
                                year_data = filtered_monthly[filtered_monthly['date'].apply(lambda x: x.year) == year]
                                
                                if not year_data.empty:
                                    # Add bars for each month in this year
                                    for _, row in year_data.iterrows():
                                        # Calculate position - each year gets divided into 12 parts
                                        # Position the bar at year + (month-1)/12 to create evenly spaced monthly bars
                                        month = row['date'].month
                                        x_pos = year + (month - 1) / 12
                                        
                                        # Add a thin bar for this month's value
                                        fig.add_trace(go.Bar(
                                            x=[x_pos],  # Single position for this month
                                            y=[row['value']],
                                            name=f"M2 Supply Monthly",  # Use a single name for all
                                            marker=dict(
                                                color='rgba(31, 119, 180, 0.3)',  # More transparent blue (50%)
                                                line=dict(color='rgba(31, 119, 180, 0.5)', width=0.5)  # Add border for better visibility
                                            ),
                                            width=1/14,  # Make bars thin (less than 1/12 to have gaps)
                                            opacity=0.4,  # Make bars even more transparent (60%)
                                            yaxis='y6',  # Use yaxis6 to match the layout definition
                                            hovertemplate='%{x}<br>M2 Supply: $%{y:,.0f} Billion<br><extra></extra>',
                                            showlegend=False,  # Don't show in legend at all
                                            legendgroup='monthly'  # Group all monthly bars together
                                        ))
                                        
                            # Ensure tick labels show full years without the monthly detail
                            fig.update_xaxes(
                                tickmode='array',
                                tickvals=list(years),
                                ticktext=[str(y) for y in years]
                            )
                        max_m2_value = max(max_m2_value, max(monthly_m2_df['value']))
                        m2_axis_added = True
                        
                        # Store monthly growth data for later if needed
                        monthly_growth_field = 'monthly_growth'
                        monthly_x_field = 'date'
                else:
                    st.warning("Monthly M2 data format is unexpected. Please check the data source.")
        
        # Add M2 y-axis if we added any M2 data
        if m2_axis_added:
            # Add a new y-axis for M2 Supply
            current_position -= right_side_spacing
            layout_dict['yaxis6'] = dict(
                title=dict(text=m2_axis_title, font=dict(color='#111827', size=11)),
                overlaying='y',
                side='right',
                anchor='free',
                position=current_position,
                showgrid=False,
                range=[0, max_m2_value * 1.1],
                tickformat=',',
                tickfont=dict(color='#111827', size=10),
                nticks=6
            )
            
            # Optionally add M2 growth rate line when toggle is checked
            if show_m2_growth:
                # Add annual growth rate if we have annual data
                if show_annual_m2 and annual_m2_df is not None and not annual_m2_df.empty:
                    fig.add_trace(go.Scatter(
                        x=annual_m2_df['year'],
                        y=annual_m2_df['annual_growth'],
                        name='M2 Annual Growth Rate (%)',
                        line=dict(color='#9C27B0', width=3),  # Purple color for growth rate
                        mode='lines',
                        yaxis='y7'  # Use a dedicated axis (y7) for M2 growth rate
                    ))
                
                # Add monthly growth rate if we have monthly data (keeping monthly granularity)
                if show_monthly_m2 and monthly_m2_df is not None and not monthly_m2_df.empty:
                    # Filter to the selected year range
                    filtered_monthly = monthly_m2_df[(monthly_m2_df['date'].apply(lambda x: x.year) >= year_range[0]) & 
                                                 (monthly_m2_df['date'].apply(lambda x: x.year) <= year_range[1])]
                    
                    # For each year, add the monthly growth rates
                    for year in range(year_range[0], year_range[1] + 1):
                        # Get data for this year
                        year_data = filtered_monthly[filtered_monthly['date'].apply(lambda x: x.year) == year]
                        
                        if not year_data.empty:
                            # Create arrays to store points for connecting lines
                            x_positions = []
                            growth_values = []
                            
                            # Process each month
                            for _, row in year_data.iterrows():
                                month = row['date'].month
                                x_pos = year + (month - 1) / 12
                                x_positions.append(x_pos)
                                growth_values.append(row['monthly_growth'])
                            
                            # Add a line for this year's monthly growth rates
                            fig.add_trace(go.Scatter(
                                x=x_positions,
                                y=growth_values,
                                name=f"M2 Monthly Growth Rate",  # Use a single name for all years
                                line=dict(color='rgba(224, 64, 251, 0.5)', width=1),  # More transparent purple
                                mode='lines',  # Remove markers to reduce clutter
                                marker=dict(size=2, opacity=0.4),  # Smaller, more transparent markers
                                yaxis='y7',  # Use same dedicated axis for growth rates
                                legendgroup='monthly_growth',  # Group all monthly growth lines together
                                showlegend=year==year_range[0]  # Only show in legend for first year
                            ))
                
                # Add the dedicated y7 axis for M2 growth rate
                current_position -= right_side_spacing
                layout_dict['yaxis7'] = dict(
                    title=dict(text="M2 Growth Rate (%)", font=dict(size=11, color='#111827')),
                    overlaying='y',
                    side='right',
                    anchor='free',
                    position=current_position,
                    showgrid=False,
                    range=[-5, 25],
                    tickformat='.1f',
                    tickfont=dict(size=10, color='#111827'),
                    nticks=6
                )
            
            # Add explanatory text as separate elements for better rendering
            st.markdown("""
            <div style="background-color: #f0f7fc; padding: 15px; border-radius: 5px; margin-top: 20px; border-left: 4px solid #0366d6;">
                <h4 style="margin-top: 0; color: #0366d6;">About M2 Money Supply</h4>
                <p style="margin-bottom: 0; font-size: 0.9rem;">M2 is a measure of the U.S. money supply that includes cash, checking deposits, 
                savings deposits, money market securities, and other time deposits. It is an important economic indicator that reflects the amount of money in circulation 
                and can impact inflation, interest rates, and overall economic growth.</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Add key events as a separate markdown element
            st.markdown("<h5 style='color: #0366d6;'>Key Events Affecting M2 Money Supply</h5>", unsafe_allow_html=True)
            
            # Add events as bullet points
            st.markdown("""
            • **2008-2009:** Financial crisis and QE1 (Quantitative Easing)
            • **2010-2011:** QE2 - Fed purchased Treasury securities
            • **2012-2014:** QE3 - Further expansion
            • **2020-2021:** COVID-19 pandemic stimulus - Major expansion
            • **2022-Present:** Quantitative tightening
            """)
        else:
            st.warning("M2 supply data is not available. Please ensure the data has been imported into the database.")



    fig.update_layout(**layout_dict)
    fig.update_layout(
        hovermode="x",  # Per-trace hover labels (Polymarket-style)
        font=dict(family="DM Sans, Inter, sans-serif", size=12, color="#111827"),
        xaxis=dict(
            showgrid=True, gridcolor='rgba(0,0,0,0.06)', showline=False,
            zeroline=False, tickfont=dict(size=11, color="#111827"),
            showspikes=True, spikemode="across",
            spikecolor="rgba(107,114,128,0.3)", spikethickness=1,
            spikedash="solid",
        ),
        legend=dict(font=dict(color="#111827")),
        hoverlabel=dict(bgcolor="rgba(17,24,39,0.92)", bordercolor="rgba(99,179,237,0.4)",
                        font=dict(size=12, color="#f9fafb")),
    )

    # Update hover templates for country traces
    for trace in fig.data:
        if trace.yaxis == 'y':  # Only update country traces
            # Add YoY growth data to hover template
            # Get the country/region name from trace
            country_name = trace.name
            
            # Get data for this country to calculate YoY growth
            # Use the loaded advertising data if available
            try:
                if 'df' in locals() and df is not None and not df.empty:
                    country_data = df[df['country'] == country_name]
                else:
                    continue  # Skip if no data available
            except NameError:
                continue  # Skip if df is not defined
            
            if not country_data.empty:
                # Sort data by year
                country_data = country_data.sort_values('year')
                
                # Calculate YoY growth percentages
                values = country_data['value'].tolist()
                years = country_data['year'].tolist()
                
                # Initialize growth list
                yoy_growth = ['N/A']  # First year has no YoY growth
                
                # Calculate for subsequent years
                for i in range(1, len(values)):
                    if values[i-1] != 0:
                        growth_pct = ((values[i] - values[i-1]) / values[i-1]) * 100
                        yoy_growth.append(f"{growth_pct:.1f}%")
                    else:
                        yoy_growth.append('N/A')
                
                # Assign years and growth values as custom data
                trace.customdata = list(zip(years, yoy_growth))
                
                # Update hover template to include YoY growth
                trace.hovertemplate = (
                    "<b>%{data.name}</b><br>" +
                    "Year: %{x}<br>" +
                    "Value: %{y:.1f} Million USD<br>" +
                    "YoY Growth: %{customdata[1]}<br>" +
                    "<extra></extra>"
                )
            else:
                # Default hover template without YoY growth
                trace.hovertemplate = (
                    "<b>%{data.name}</b><br>" +
                    "Year: %{x}<br>" +
                    "Value: %{y:.1f} Million USD<br>" +
                    "<extra></extra>"
                )

    # Add chart zoom effect if not already added
    if not hasattr(st.session_state, 'genie_chart_css_added'):
        st.markdown("""
        <style>
        .chart-container {
            transition: transform 0.3s ease;
            transform-origin: center center;
        }
        .chart-container:hover {
            transform: scale(1.02);
        }
        </style>
        """, unsafe_allow_html=True)
        st.session_state.genie_chart_css_added = True
    
    # Display the plot with zoom effect
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

    # Generate data-driven insight for displayed chart
    _chart_insights = []
    try:
        _co_metrics = selected_company_metrics if 'selected_company_metrics' in dir() else []
        # Fallback: always show Revenue insight for selected companies even when no metric is picked
        _insight_metrics = _co_metrics[:2] if _co_metrics else ["Revenue"]
        for _co in selected_companies:
            for _metric in _insight_metrics:
                _yrs = sorted(data_processor.get_available_years(_co))
                if len(_yrs) >= 2:
                    _latest_yr = _yrs[-1]
                    _prev_yr = _yrs[-2]
                    _metrics_latest = data_processor.get_metrics(_co, _latest_yr)
                    _metrics_prev = data_processor.get_metrics(_co, _prev_yr)
                    _metric_key = available_metrics.get(_metric, _metric.lower()) if 'available_metrics' in dir() else _metric.lower()
                    _latest_val = _metrics_latest.get(_metric_key) if _metrics_latest else None
                    _prev_val = _metrics_prev.get(_metric_key) if _metrics_prev else None
                    if _latest_val and _prev_val and float(_prev_val) != 0:
                        _yoy = (float(_latest_val) - float(_prev_val)) / abs(float(_prev_val)) * 100
                        _direction = "grew" if _yoy > 0 else "declined"
                        _color = "#22c55e" if _yoy > 0 else "#ef4444"
                        if float(_latest_val) > 1000:
                            _insight = (f"<b>{_co}</b> {_metric} {_direction} "
                                f"<span style='color:{_color}'>{'+'if _yoy>0 else ''}{_yoy:.1f}%</span> "
                                f"in {_latest_yr} vs {_prev_yr} "
                                f"(${float(_latest_val)/1000:.1f}B → ${float(_prev_val)/1000:.1f}B)")
                        else:
                            _insight = (f"<b>{_co}</b> {_metric} {_direction} "
                                f"<span style='color:{_color}'>{'+'if _yoy>0 else ''}{_yoy:.1f}%</span> "
                                f"in {_latest_yr}")
                        _chart_insights.append(_insight)
    except Exception:
        pass

    # Also build country ad-spend insights
    try:
        if selected_metrics and all_selected_countries:
            _ad_df = load_cached_advertising_data(
                tuple(all_selected_countries), tuple(selected_metrics),
                int(year_range[0]), int(year_range[1])
            )
            if _ad_df is not None and not _ad_df.empty:
                for _ctry in [c for c in all_selected_countries if c != "Global"]:
                    _found_insight = False
                    for _met in selected_metrics[:2]:  # limit to first 2 metrics
                        _pdata = process_metrics_data(_ad_df, _ctry, _met, year_range)
                        if _pdata and len(_pdata["years"]) >= 2:
                            _lval = _pdata["values"][-1]
                            _pval = _pdata["values"][-2]
                            _lyr = _pdata["years"][-1]
                            _pyr = _pdata["years"][-2]
                            if _pval and float(_pval) != 0:
                                _yoy = (float(_lval) - float(_pval)) / abs(float(_pval)) * 100
                                _dir = "grew" if _yoy > 0 else "declined"
                                _clr = "#22c55e" if _yoy > 0 else "#ef4444"
                                _chart_insights.append(
                                    f"<b>{_ctry}</b> {_met} ad spend {_dir} "
                                    f"<span style='color:{_clr}'>{'+'if _yoy>0 else ''}{_yoy:.1f}%</span> "
                                    f"in {_lyr} vs {_pyr} "
                                    f"(${float(_lval):,.0f}M)"
                                )
                                _found_insight = True
                    # Fallback: aggregate total for this country if individual metrics failed
                    if not _found_insight:
                        _ctry_df = _ad_df[_ad_df["country"] == _ctry]
                        if not _ctry_df.empty and "year" in _ctry_df.columns and "value" in _ctry_df.columns:
                            _ctry_totals = _ctry_df.groupby("year", as_index=False)["value"].sum()
                            _ctry_totals = _ctry_totals.sort_values("year")
                            if len(_ctry_totals) >= 2:
                                _lval = float(_ctry_totals.iloc[-1]["value"])
                                _pval = float(_ctry_totals.iloc[-2]["value"])
                                _lyr = int(_ctry_totals.iloc[-1]["year"])
                                _pyr = int(_ctry_totals.iloc[-2]["year"])
                                if _pval != 0:
                                    _yoy = (_lval - _pval) / abs(_pval) * 100
                                    _dir = "grew" if _yoy > 0 else "declined"
                                    _clr = "#22c55e" if _yoy > 0 else "#ef4444"
                                    _chart_insights.append(
                                        f"<b>{_ctry}</b> total ad spend {_dir} "
                                        f"<span style='color:{_clr}'>{'+'if _yoy>0 else ''}{_yoy:.1f}%</span> "
                                        f"in {_lyr} vs {_pyr} "
                                        f"(${_lval:,.0f}M)"
                                    )
    except Exception:
        pass

    if _chart_insights:
        st.markdown(
            "<div style='background:rgba(15,23,42,0.5);border-left:3px solid #6366f1;"
            "padding:10px 14px;border-radius:0 8px 8px 0;margin-top:8px;'>"
            + "".join(f"<p style='margin:2px 0;font-size:0.83rem;color:#e6edf3;'>{i}</p>"
                      for i in _chart_insights)
            + "</div>",
            unsafe_allow_html=True
        )

    # Optional: subscribers/users chart (sheet-backed, no hard-coded data)
    if 'show_subscribers' in locals() and show_subscribers and st.session_state.get("selected_services"):
        st.subheader("👥 Subscribers / Users (Annualized)")
        sub_proc = get_subscriber_processor()
        sub_fig = go.Figure()

        for service in st.session_state.get("selected_services", []):
            svc_data = sub_proc.get_service_data(service, metric_type="subscribers")
            df_svc = (svc_data.get("data") if svc_data else None)
            if df_svc is None or df_svc.empty:
                continue

            df_svc = df_svc.copy()
            # Quarter is stored as a string like "Q1 2020"
            q = df_svc["Quarter"].astype(str).str.strip()
            year = pd.to_numeric(q.str.extract(r"(\\d{4})")[0], errors="coerce")
            qn = pd.to_numeric(q.str.extract(r"Q(\\d)")[0], errors="coerce")
            df_svc["year"] = year.astype("Int64")
            df_svc["quarter_num"] = qn.astype("Int64")
            df_svc = df_svc.dropna(subset=["year", "quarter_num", "Subscribers"])

            # Last reported quarter in each year (year-end proxy)
            annual = (
                df_svc.sort_values(["year", "quarter_num"])
                .groupby("year", as_index=False)
                .tail(1)
                .sort_values("year")
            )

            annual = annual[(annual["year"] >= year_range[0]) & (annual["year"] <= year_range[1])]
            if annual.empty:
                continue

            sub_fig.add_trace(
                go.Scatter(
                    x=annual["year"].astype(int),
                    y=annual["Subscribers"].astype(float),
                    mode="lines+markers",
                    name=service,
                    hovertemplate="<b>%{data.name}</b><br>Year: %{x}<br>Value: %{y:,.1f}<extra></extra>",
                )
            )

        if sub_fig.data:
            sub_fig.update_layout(
                height=360,
                margin=dict(t=30, l=40, r=20, b=40),
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color="#374151"),
                xaxis=dict(title="Year", tickfont=dict(color="#374151"), title_font=dict(color="#6b7280")),
                yaxis=dict(title="Subscribers / Users", tickfont=dict(color="#374151"), title_font=dict(color="#6b7280")),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color="#374151")),
            )
            st.plotly_chart(sub_fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No subscriber/user data found in the selected year range.")
    
# Insights section has been removed from the top and will only appear below the chart

# No need to close any flex container here as we're not using one

# Detailed Insights section removed — dynamic insights appear inline with charts above

try:
    dashboard_state = {
        "page": "Genie",
        "excel_path": str(excel_path),
        "selected_companies": selected_companies,
        "selected_countries": all_selected_countries,
        "metric_selection_mode": metric_selection_mode,
        "selected_metrics": selected_detailed_metrics,
        "selected_company_metrics": selected_company_metrics if "selected_company_metrics" in locals() else [],
        "year_range": f"{year_range[0]}-{year_range[1]}" if "year_range" in locals() else "unknown",
        "data_granularity": selected_granularity if "selected_granularity" in locals() else "Auto",
        "quarter_focus": selected_quarter_focus if "selected_quarter_focus" in locals() else "All Quarters",
        "month_focus": selected_month_focus if "selected_month_focus" in locals() else None,
        "day_focus": selected_day_focus if "selected_day_focus" in locals() else None,
        "sheet_granularity_library": st.session_state.get("global_time_context", {}).get("sheet_granularity_library", {}),
        "show_m2_supply": bool(show_m2_supply) if "show_m2_supply" in locals() else False,
        "show_inflation": bool(show_inflation) if "show_inflation" in locals() else False,
        "show_fed_funds": bool(show_fed_funds) if "show_fed_funds" in locals() else False,
        "adjust_purchasing_power": bool(adjust_purchasing_power) if "adjust_purchasing_power" in locals() else False,
    }
    dashboard_state["available_transcripts"] = list(_get_transcript_index(str(excel_path)).keys())
    dashboard_state["active_overview_auto_insights"] = _get_active_overview_auto_insights(str(excel_path))
    _primary_co_ds = selected_companies[0] if "selected_companies" in dir() and selected_companies else ""
    dashboard_state["forward_signals"] = _extract_forward_signals(
        str(excel_path) if "excel_path" in dir() and excel_path else "",
        company=_primary_co_ds,
        max_signals=20
    )
    dashboard_state["all_tracked_companies"] = [
        "Alphabet","Amazon","Apple","Meta Platforms","Microsoft","Netflix","Disney",
        "Comcast","Spotify","Roku","Warner Bros. Discovery","Paramount","Snap","Pinterest","Nvidia"
    ]
    dashboard_state["company_asset_map"] = {
        "Alphabet":["Google Search","YouTube","Google Cloud","Google Network","Waymo","DeepMind"],
        "Amazon":["Amazon Ads","AWS","Amazon Prime Video","Twitch","Alexa"],
        "Apple":["iPhone","Mac","iPad","Wearables","Apple TV+","App Store","iCloud","Apple Music"],
        "Meta Platforms":["Facebook","Instagram","WhatsApp","Threads","Reels","Meta AI","Reality Labs / Quest VR"],
        "Microsoft":["Azure Cloud","Microsoft 365","LinkedIn","Bing Ads","Xbox","GitHub","Copilot AI"],
        "Netflix":["Netflix Streaming","Ad-Supported Tier","Netflix Games","Live Events"],
        "Disney":["Disney+","Hulu","ESPN / ESPN+","Linear TV (ABC/FX/NatGeo)","Disney Parks","Pixar/Marvel/Lucasfilm"],
        "Comcast":["NBCUniversal / NBC","Peacock","Sky (Europe)","Universal Studios","Xfinity Broadband"],
        "Spotify":["Spotify Premium","Spotify Ad-Supported / Free Tier","Podcasts","Audiobooks"],
        "Roku":["Roku Platform / The Roku Channel","Roku Devices","Roku OS"],
        "Warner Bros. Discovery":["Max (HBO Max)","HBO","CNN","Warner Bros Film","Discovery+","TNT/TBS"],
        "Paramount":["Paramount+","CBS","MTV/Nickelodeon/Comedy Central","BET","Pluto TV"],
        "Snap":["Snapchat","Snap Ads","Snap AR / Spectacles"],
        "Pinterest":["Pinterest Ads","Pinterest Shopping"],
        "Nvidia":["Data Center GPUs (H100/B200)","Gaming GPUs","NVIDIA DRIVE","Omniverse","CUDA"],
    }
except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    st.stop()

# Persist current Genie filter state for downstream in-chat drilldowns.
st.session_state["genie_context_company"] = selected_companies[0] if selected_companies else ""
st.session_state["genie_context_year"] = int(year_range[1]) if "year_range" in locals() else None
quarter_focus_for_context = str(selected_quarter_focus if "selected_quarter_focus" in locals() else "").strip().upper()
st.session_state["genie_context_quarter"] = quarter_focus_for_context if re.fullmatch(r"Q[1-4]", quarter_focus_for_context) else ""


def _store_last_genie_response(response_text: str, message_index: int) -> None:
    st.session_state["last_genie_response"] = str(response_text or "")
    st.session_state["last_genie_response_index"] = int(message_index)
    st.session_state["last_genie_response_at"] = datetime.utcnow().isoformat()
    st.session_state["last_genie_context_company"] = st.session_state.get("genie_context_company", "")
    st.session_state["last_genie_context_year"] = st.session_state.get("genie_context_year")
    st.session_state["last_genie_context_quarter"] = st.session_state.get("genie_context_quarter", "")


def _extract_node_intent(response_text: str, user_question: str = "") -> dict:
    """
    Parse a Genie response to extract intent metadata for thought map nodes.
    Returns dict with: companies, years, quarters, metrics, node_type, topic_color
    """
    ALL_COMPANIES = [
        "alphabet", "google", "amazon", "apple", "meta", "meta platforms",
        "microsoft", "netflix", "disney", "comcast", "spotify", "roku",
        "warner bros", "paramount", "snap", "snapchat", "pinterest", "nvidia",
        "instagram", "whatsapp", "facebook",
    ]
    combined = (response_text + " " + user_question).lower()

    found_companies = []
    for co in ALL_COMPANIES:
        if co in combined:
            canonical = {
                "google": "Alphabet", "alphabet": "Alphabet",
                "meta platforms": "Meta Platforms", "meta": "Meta Platforms",
                "facebook": "Meta Platforms", "instagram": "Meta Platforms",
                "whatsapp": "Meta Platforms",
                "warner bros": "Warner Bros. Discovery",
                "snapchat": "Snap",
            }.get(co, co.title())
            if canonical not in found_companies:
                found_companies.append(canonical)

    years = list(set(int(m) for m in re.findall(r'\b(20[1-2][0-9])\b', combined)))
    quarters = list(set(m.upper() for m in re.findall(r'\b(q[1-4])\b', combined)))

    metric_keywords = {
        "revenue": "Revenue", "ad revenue": "Ad Revenue",
        "margin": "Margin", "subscribers": "Subscribers",
        "operating income": "Operating Income", "cloud": "Cloud",
        "eps": "EPS", "market cap": "Market Cap",
    }
    found_metrics = [v for k, v in metric_keywords.items() if k in combined]

    forward_triggers = ["expect", "anticipate", "guidance", "outlook", "heading into",
                        "next quarter", "going forward", "we believe", "positioned"]
    macro_triggers = ["m2", "inflation", "fed", "interest rate", "recession",
                      "liquidity", "money supply", "macro"]
    comparison_triggers = ["vs", "versus", "compare", "compared", "relative to",
                           "outperform", "underperform", "better than", "worse than"]
    risk_triggers = ["risk", "concern", "headwind", "decline", "miss", "disappoint",
                     "challenge", "warning", "caution"]
    transcript_triggers = ["said", "stated", "noted", "mentioned", "transcript",
                           "earnings call", "management", "ceo", "cfo"]

    if any(t in combined for t in forward_triggers):
        node_type = "forward_signal"
    elif any(t in combined for t in macro_triggers):
        node_type = "macro"
    elif any(t in combined for t in comparison_triggers):
        node_type = "comparison"
    elif any(t in combined for t in risk_triggers):
        node_type = "risk"
    elif any(t in combined for t in transcript_triggers):
        node_type = "transcript"
    elif found_metrics:
        node_type = "data"
    else:
        node_type = "default"

    return {
        "companies": found_companies[:3],
        "years": sorted(years, reverse=True)[:2],
        "quarters": quarters[:2],
        "metrics": found_metrics[:3],
        "node_type": node_type,
        "primary_company": found_companies[0] if found_companies else "",
    }


# ── GENIE CHAT + THOUGHT MAP SECTION ────────────────────────────────────────
st.markdown("<hr style='margin: 2.5rem 0 1.5rem 0;'>", unsafe_allow_html=True)

# ── Suggestion chips with category filter + shuffle ──────────────────────
import random as _rng

_primary = (selected_companies[0] if selected_companies else "Meta Platforms") if "selected_companies" in dir() else "Meta Platforms"
_yr = (year_range[1] if "year_range" in dir() else 2024)

# Question bank organised by category
_QUESTION_BANK = {
    "All": [],  # filled below from all categories
    "AI & Technology": [
        f"What did {_primary} management say about AI investment plans in {_yr}?",
        f"How much is {_primary} spending on data centres and AI infrastructure?",
        f"Compare AI mentions across Alphabet, Meta, and Microsoft transcripts in {_yr}",
        "Which company is investing the most in generative AI based on their earnings calls?",
        f"What AI products or features did {_primary} launch or announce recently?",
    ],
    "Advertising": [
        f"Compare {_primary} advertising revenue growth vs the overall market trend",
        f"How is {_primary} ad revenue split between search, display, and video?",
        "Which company is gaining the most ad market share \u2014 and who is losing?",
        "How did the ad market perform this quarter vs macro forecasts from GroupM/Magna?",
        f"What did {_primary} say about advertiser demand and CPM trends?",
    ],
    "Revenue & Growth": [
        f"Which company had the most surprising segment performance in {_yr}?",
        f"Break down {_primary} revenue by segment \u2014 what is driving growth?",
        "Which company has the fastest revenue growth among the tracked 13?",
        f"What was {_primary} revenue guidance for the coming quarter?",
        f"Compare {_primary} revenue trajectory vs its 5-year CAGR",
    ],
    "Subscribers & Users": [
        "How is the streaming wars playing out \u2014 who is winning on subscribers and margins?",
        f"What did {_primary} say about user growth and engagement trends?",
        "Compare Netflix, Disney+, and Paramount+ subscriber trajectories",
        "Which platform has the best revenue per subscriber?",
        f"What retention or churn signals did {_primary} management highlight?",
    ],
    "Investment & Acquisitions": [
        f"What acquisitions or investments did {_primary} announce in {_yr}?",
        "Which company committed the most capital to acquisitions this year?",
        f"What strategic investments is {_primary} making outside its core business?",
        "Compare CapEx trajectories across Alphabet, Meta, Amazon, and Microsoft",
        f"Did {_primary} mention any joint ventures or partnership deals?",
    ],
    "Cost & Margin": [
        f"How are {_primary} operating margins trending \u2014 improving or declining?",
        "Which company has the best cost discipline based on recent earnings calls?",
        f"What did {_primary} say about headcount changes and efficiency programs?",
        "Compare gross margins across the Big Tech companies",
        f"What restructuring or cost-cutting measures did {_primary} announce?",
    ],
    "Macro & Market": [
        "What macro signals (M2, Fed rate) correlate most with ad market growth?",
        "How are companies talking about inflation and consumer spending?",
        "What did management teams say about the economic outlook?",
        "How does M2 money supply growth map to digital ad revenue growth?",
        "Which companies flagged geopolitical risks in their latest calls?",
    ],
    "Competition": [
        f"What are the key risks {_primary} flagged for the next 12 months?",
        f"How does {_primary} compare to its closest competitor on key metrics?",
        "Which company is winning the cloud market based on earnings commentary?",
        f"What competitive advantages did {_primary} management highlight?",
        "Who is disrupting whom in the current media landscape?",
    ],
    "Strategy Brief": [
        f"Generate a 1-paragraph strategic brief on {_primary} for a European broadcaster",
        f"What should Mediaset know about {_primary} as a potential partner or rival?",
        f"Summarise {_primary} quarterly performance in 3 bullet points",
        f"What is the single most important thing {_primary} said in their latest call?",
        "Write a competitive landscape summary for the European ad market",
    ],
}
# Fill "All" from every other category
for _cat_key, _cat_qs in _QUESTION_BANK.items():
    if _cat_key != "All" and _cat_qs:
        _QUESTION_BANK["All"].extend(_cat_qs)

# Shuffle seed in session state
if "suggestion_seed" not in st.session_state:
    st.session_state["suggestion_seed"] = _rng.randint(0, 999999)
if "suggestion_category" not in st.session_state:
    st.session_state["suggestion_category"] = "All"

st.markdown("""<style>
/* ── GLOBAL: kill Streamlit's dark overlay on button active/focus ── */
div[data-testid="stButton"] > button:active,
div[data-testid="stButton"] > button:focus,
div[data-testid="stButton"] > button:focus-visible,
div[data-testid="stButton"] > button:focus:not(:focus-visible) {
    background-image: none !important;
    box-shadow: none !important;
    outline: none !important;
}
/* ── Suggestion area (clean minimal dark cards) ── */
.genie-suggest-area { margin-bottom: 1rem; }
.genie-suggest-area div[data-testid="stButton"] > button {
    background: rgba(255,255,255,0.04) !important;
    color: #c9d1d9 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 14px !important;
    font-size: 0.84rem !important;
    padding: 0.75rem 1rem !important;
    white-space: normal !important;
    text-align: left !important;
    height: auto !important;
    min-height: 3.2rem !important;
    font-weight: 400 !important;
    line-height: 1.4 !important;
    backdrop-filter: blur(8px) !important;
    transition: all 0.2s cubic-bezier(.4,0,.2,1) !important;
    background-image: none !important;
}
.genie-suggest-area div[data-testid="stButton"] > button:hover {
    background: rgba(255,91,31,0.08) !important;
    border-color: rgba(255,91,31,0.35) !important;
    color: #ff8c42 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.25) !important;
    background-image: none !important;
}
.genie-suggest-area div[data-testid="stButton"] > button:active,
.genie-suggest-area div[data-testid="stButton"] > button:focus {
    background: rgba(255,91,31,0.12) !important;
    background-image: none !important;
    box-shadow: none !important;
}
/* Category pills */
.genie-cat-pills { margin: 0.4rem 0 0.7rem 0; }
.genie-cat-pills div[data-testid="stButton"] > button {
    background: transparent !important;
    color: #6e7681 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 999px !important;
    font-size: 0.68rem !important;
    padding: 0.18rem 0.6rem !important;
    font-weight: 500 !important;
    min-height: 0 !important;
    height: auto !important;
    letter-spacing: 0.02em !important;
    transition: all 0.15s ease !important;
    background-image: none !important;
}
.genie-cat-pills div[data-testid="stButton"] > button:hover {
    background: rgba(255,255,255,0.06) !important;
    border-color: rgba(255,91,31,0.4) !important;
    color: #ff8c42 !important;
    background-image: none !important;
}
.genie-cat-pills div[data-testid="stButton"] > button:active,
.genie-cat-pills div[data-testid="stButton"] > button:focus {
    background: rgba(255,255,255,0.08) !important;
    background-image: none !important;
    box-shadow: none !important;
}
/* Shuffle button */
.genie-shuffle div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #ff5b1f 0%, #ff8c42 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 999px !important;
    font-size: 0.76rem !important;
    padding: 0.28rem 0.9rem !important;
    font-weight: 600 !important;
    min-height: 0 !important;
    height: auto !important;
    transition: all 0.15s ease !important;
    box-shadow: 0 2px 8px rgba(255,91,31,0.2) !important;
    background-image: none !important;
}
.genie-shuffle div[data-testid="stButton"] > button:hover {
    transform: scale(1.05) !important;
    box-shadow: 0 4px 16px rgba(255,91,31,0.35) !important;
    background-image: none !important;
}
.genie-shuffle div[data-testid="stButton"] > button:active,
.genie-shuffle div[data-testid="stButton"] > button:focus {
    background: linear-gradient(135deg, #ff5b1f 0%, #ff8c42 100%) !important;
    background-image: none !important;
}
/* Guidance signal buttons — kill dark overlay */
.guidance-signals-wrap div[data-testid="stButton"] > button:active,
.guidance-signals-wrap div[data-testid="stButton"] > button:focus {
    background: #fff7f4 !important;
    background-image: none !important;
    box-shadow: none !important;
}
</style>""", unsafe_allow_html=True)

# Header row: title + shuffle
_hdr_left, _hdr_right = st.columns([4, 1])
with _hdr_left:
    st.markdown(
        "<p style='font-size:0.9rem;font-weight:600;color:#e6edf3;margin:0 0 0.2rem 0;'>"
        "\U0001f4a1 Suggested questions</p>",
        unsafe_allow_html=True,
    )
with _hdr_right:
    st.markdown('<div class="genie-shuffle">', unsafe_allow_html=True)
    if st.button("\U0001f500 Shuffle", key="shuffle_suggestions", use_container_width=True):
        st.session_state["suggestion_seed"] = _rng.randint(0, 999999)
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# Category filter pills
_cat_names = [c for c in _QUESTION_BANK if _QUESTION_BANK[c]]
st.markdown('<div class="genie-cat-pills">', unsafe_allow_html=True)
_cat_cols = st.columns(min(len(_cat_names), 5))
for _ci, _cname in enumerate(_cat_names):
    with _cat_cols[_ci % len(_cat_cols)]:
        _is_active = (st.session_state["suggestion_category"] == _cname)
        _cat_label = f"\u25cf {_cname}" if _is_active else _cname
        if st.button(_cat_label, key=f"cat_pill_{_ci}", use_container_width=True):
            st.session_state["suggestion_category"] = _cname
            st.session_state["suggestion_seed"] = _rng.randint(0, 999999)
            st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# Pick 3 questions from the active category using the shuffle seed
_active_cat = st.session_state["suggestion_category"]
_pool = list(_QUESTION_BANK.get(_active_cat, _QUESTION_BANK["All"]))
_seed_rng = _rng.Random(st.session_state["suggestion_seed"])
_seed_rng.shuffle(_pool)
_visible_suggestions = _pool[:3]

# Display the 3 clickable question cards
st.markdown('<div class="genie-suggest-area">', unsafe_allow_html=True)
_sugg_cols = st.columns(3)
for _si, _sq in enumerate(_visible_suggestions):
    with _sugg_cols[_si]:
        if st.button(
            _sq[:140] + ("\u2026" if len(_sq) > 140 else ""),
            key=f"suggest_q_{st.session_state['suggestion_seed']}_{_si}",
            use_container_width=True,
        ):
            add_queued_node(_sq, source_type="suggestion")
            # No st.rerun() — queued node appears on next natural interaction
            # to avoid jarring full-page reload
st.markdown('</div>', unsafe_allow_html=True)

# ── Forward Signals Panel ─────────────────────────────────────────────────
st.markdown("<hr style='margin: 2rem 0 1rem 0;'>", unsafe_allow_html=True)
st.markdown("### Management Outlook & Guidance Signals")
st.markdown(
    "<p style='color:#6b7280;font-size:0.9rem;margin-bottom:0.5rem;'>"
    "Forward-looking statements extracted from earnings call transcripts. "
    "Click any signal to ask Genie about it.</p>",
    unsafe_allow_html=True
)

# Separate company selector for signals / suggestions — decoupled from top Company Analysis
_all_tracked = [
    "Alphabet", "Amazon", "Apple", "Meta Platforms", "Microsoft", "Netflix",
    "Disney", "Comcast", "Spotify", "Roku", "Warner Bros. Discovery", "Paramount",
]
_signal_default = selected_companies[:3] if ("selected_companies" in dir() and selected_companies) else (_all_tracked[:1])
_signal_companies = st.multiselect(
    "Companies for signals & suggestions",
    options=_all_tracked,
    default=_signal_default,
    key="signal_company_selector",
    help="Choose which companies drive suggested questions, management outlook, and guidance signals below. Independent from Company Analysis above.",
)

st.markdown("""<style>
/* Guidance signal buttons — readable text, light card */
.guidance-signals-wrap div[data-testid="stButton"] > button {
    background: #f8fafc !important;
    color: #1e293b !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 6px !important;
    font-size: 0.82rem !important;
    text-align: left !important;
    white-space: normal !important;
    height: auto !important;
    min-height: 2rem !important;
    padding: 0.4rem 0.7rem !important;
    font-weight: 400 !important;
    line-height: 1.4 !important;
    background-image: none !important;
}
.guidance-signals-wrap div[data-testid="stButton"] > button:hover {
    background: #fff7f4 !important;
    border-color: #ff5b1f !important;
    color: #0f172a !important;
    background-image: none !important;
}
.guidance-signals-wrap div[data-testid="stButton"] > button:active,
.guidance-signals-wrap div[data-testid="stButton"] > button:focus {
    background: #fff7f4 !important;
    background-image: none !important;
    box-shadow: none !important;
}
/* Category expander bars — high contrast readable labels */
.guidance-signals-wrap div[data-testid="stExpander"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    margin-bottom: 0.5rem !important;
}
.guidance-signals-wrap div[data-testid="stExpander"] summary {
    background: rgba(255,91,31,0.06) !important;
    padding: 10px 14px !important;
    border-radius: 10px !important;
}
.guidance-signals-wrap div[data-testid="stExpander"] summary:hover {
    background: rgba(255,91,31,0.12) !important;
}
.guidance-signals-wrap div[data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
.guidance-signals-wrap div[data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] * {
    color: #e6edf3 !important;
    font-size: 0.9rem !important;
}
.guidance-signals-wrap div[data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] strong {
    color: #ff8c42 !important;
}
.guidance-signals-wrap div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] {
    padding: 8px 12px 12px !important;
}
/* Quarter radio pills — readable on dark */
.guidance-signals-wrap div[data-testid="stRadio"] label {
    color: #e6edf3 !important;
}
.guidance-signals-wrap div[data-testid="stRadio"] label p,
.guidance-signals-wrap div[data-testid="stRadio"] label span {
    color: #e6edf3 !important;
    font-size: 0.82rem !important;
}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="guidance-signals-wrap">', unsafe_allow_html=True)
_fs_companies = _signal_companies if _signal_companies else []
_fs_excel = str(excel_path) if "excel_path" in dir() and excel_path else ""
_all_signals = []
for _fs_co in _fs_companies:
    _co_signals = _extract_forward_signals(_fs_excel, company=_fs_co, max_signals=200)
    _all_signals.extend(_co_signals)
if _all_signals:
    # Build sorted period list (year + quarter, chronological)
    _all_periods = sorted(
        set(f"{s['year']} {s['quarter']}".strip() for s in _all_signals if s.get("year")),
        key=lambda p: (
            int(p.split()[0]) if p.split()[0].isdigit() else 0,
            int(p.split()[1].replace("Q", "")) if len(p.split()) > 1 and "Q" in p.split()[1].upper() else 0,
        ),
        reverse=True,
    )
    if _all_periods:
        _sel_period_fs = st.radio(
            "Period",
            options=_all_periods,
            index=0,
            key="guidance_period_radio",
            label_visibility="collapsed",
            horizontal=True,
        )
    else:
        _sel_period_fs = None

    if _sel_period_fs:
        _yr_str_fs, *_q_parts_fs = _sel_period_fs.split()
        _q_str_fs = _q_parts_fs[0] if _q_parts_fs else ""
        _period_signals = [
            s for s in _all_signals
            if str(s.get("year", "")) == _yr_str_fs
            and str(s.get("quarter", "")).upper() == _q_str_fs.upper()
        ]
        _cats: dict = {}
        for sig in _period_signals:
            _cats.setdefault(sig["category"], []).append(sig)

        _cat_order = ["AI & Technology", "Advertising", "Subscribers & Users", "Revenue & Growth",
                      "Business Strategy", "International Expansion", "Debt & Capital", "Competition",
                      "Product & Innovation", "Cost & Margin", "Macro & Market", "Management Guidance",
                      "Investment & Acquisitions"]
        _cats_present = [c for c in _cat_order if c in _cats] + [c for c in _cats if c not in _cat_order]
        for _cat in _cats_present:
            with st.expander(
                f"**{_cat}** \u2014 {len(_cats[_cat])} signal{'s' if len(_cats[_cat])>1 else ''}",
                expanded=(_cat == _cats_present[0])
            ):
                for sig in _cats[_cat]:
                    col_chip, col_text = st.columns([0.22, 0.78])
                    with col_chip:
                        _brand = COMPANY_BRAND_COLORS.get(sig['company'].lower(), "")
                        if not _brand:
                            # Try partial match (e.g. "Meta Platforms" → "meta platforms")
                            _co_lower = sig['company'].lower()
                            for _bk, _bv in COMPANY_BRAND_COLORS.items():
                                if _bk in _co_lower or _co_lower in _bk:
                                    _brand = _bv
                                    break
                        _brand = _brand or "#c2410c"
                        # Compute a lighter background from the brand color
                        _chip_bg = _brand + "18"  # ~10% alpha hex
                        _chip_border = _brand + "55"
                        st.markdown(
                            f"<span style='background:{_chip_bg};color:{_brand};padding:3px 10px;"
                            f"border-radius:12px;font-size:0.75rem;font-weight:600;white-space:nowrap;"
                            f"border:1px solid {_chip_border};'>"
                            f"{sig['company']} · {sig['year']} {sig['quarter']}</span>",
                            unsafe_allow_html=True
                        )
                    with col_text:
                        _prompt = (
                            f'Regarding this statement from {sig["company"]} '
                            f'({sig["year"]} {sig["quarter"]}): "{sig["signal"][:200]}" '
                            f'\u2014 what does this signal about their strategy and how should Mediaset think about it?'
                        )
                        if st.button(
                            sig["signal"][:160] + ("\u2026" if len(sig["signal"]) > 160 else ""),
                            key=f"sig_{hash(sig['signal'][:60])}_{_sel_period_fs}",
                            use_container_width=True
                        ):
                            add_queued_node(
                                _prompt,
                                source_type="signal",
                                meta={"company": sig["company"], "year": sig["year"], "quarter": sig["quarter"]},
                            )
                            # No st.rerun() — avoid full page reload
else:
    if not _fs_companies:
        st.info("Select companies above to see guidance signals extracted from earnings call transcripts.")
    else:
        st.info(
            f"No forward-looking signals found for {', '.join(_fs_companies[:3])}. "
            "This requires a **Transcripts** sheet in the data source with columns: "
            "`company`, `year`, `quarter`, `transcript_text`."
        )

st.markdown("</div>", unsafe_allow_html=True)

# ── Depth selector for thought map ──
from utils.thought_map import render_depth_selector
st.markdown(
    "<div style='margin:1.5rem 0 0.5rem;'>"
    "<span style='font-size:0.75rem;color:#6b7280;text-transform:uppercase;"
    "letter-spacing:0.08em;font-weight:600;'>Thought map depth</span></div>",
    unsafe_allow_html=True,
)
render_depth_selector()

# ── Thought map layout controls ──
if "genie_thought_map_view" not in st.session_state:
    st.session_state["genie_thought_map_view"] = "studio"
if "genie_thought_map_fullscreen" not in st.session_state:
    st.session_state["genie_thought_map_fullscreen"] = True

# ── Minimal layout toggle (view buttons now live inside the map) ──
_tm_is_fullscreen = bool(st.session_state.get("genie_thought_map_fullscreen", False))
st.markdown("""<style>
.tm-fs-toggle div[data-testid="stButton"] > button {
    border-radius: 999px !important;
    border: 1px solid rgba(0,115,255,0.24) !important;
    background: rgba(15,23,42,0.52) !important;
    background-image: none !important;
    color: #cbd5e1 !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    height: 36px !important;
    padding: 0 18px !important;
    transition: all 180ms ease !important;
}
.tm-fs-toggle div[data-testid="stButton"] > button:hover {
    border-color: rgba(56,189,248,0.7) !important;
    color: #ffffff !important;
    background: rgba(0,115,255,0.18) !important;
    background-image: none !important;
}
.tm-fs-toggle div[data-testid="stButton"] > button[kind="primary"] {
    border-color: #38bdf8 !important;
    color: #ffffff !important;
    background: linear-gradient(135deg, rgba(14,165,233,0.92), rgba(2,132,199,0.92)) !important;
    box-shadow: 0 0 12px rgba(14,165,233,0.18) !important;
    background-image: none !important;
}
</style>""", unsafe_allow_html=True)
_fs_spacer, _fs_col = st.columns([4, 1])
with _fs_col:
    st.markdown('<div class="tm-fs-toggle">', unsafe_allow_html=True)
    _fs_label = "Exit Full Screen" if _tm_is_fullscreen else "Full Screen"
    if st.button(_fs_label, key="tm_toggle_fullscreen", type="primary" if _tm_is_fullscreen else "secondary", use_container_width=True):
        st.session_state["genie_thought_map_fullscreen"] = not _tm_is_fullscreen
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

_tm_current_view = st.session_state.get("genie_thought_map_view", "classic")
_tm_is_fullscreen = bool(st.session_state.get("genie_thought_map_fullscreen", False))
_tm_height = 920 if _tm_is_fullscreen else (760 if _tm_current_view == "studio" else 700 if _tm_current_view == "focus" else 650)

# ── Side-by-side: Chat (right) + Thought Map (left) ──
if _tm_is_fullscreen:
    _tm_col = st.container()
    _chat_col = st.container()
else:
    _tm_ratio = 2.0 if _tm_current_view == "studio" else 1.85 if _tm_current_view == "focus" else 1.8
    _tm_col, _chat_col = st.columns([_tm_ratio, 1], gap="medium")

with _chat_col:
    render_enhanced_chat_interface(dashboard_state=dashboard_state, on_new_response=_store_last_genie_response)

# Fallback for pre-existing chat sessions where callback has not fired yet in this run.
if not st.session_state.get("last_genie_response"):
    _history = st.session_state.get("genie_history", [])
    if _history and isinstance(_history, list):
        for idx in range(len(_history) - 1, -1, -1):
            item = _history[idx]
            if str(item.get("role", "")).lower() == "assistant":
                st.session_state["last_genie_response"] = str(item.get("content", "") or "")
                st.session_state["last_genie_response_index"] = max(idx - 1, 0)
                st.session_state["last_genie_context_company"] = st.session_state.get("genie_context_company", "")
                st.session_state["last_genie_context_year"] = st.session_state.get("genie_context_year")
                st.session_state["last_genie_context_quarter"] = st.session_state.get("genie_context_quarter", "")
                break

# In-chat drilldown panels: shown only after at least one Genie response.
if st.session_state.get("last_genie_response"):
    try:
        repo_root = Path(__file__).resolve().parents[2]
        db_path = repo_root / "earningscall_intelligence.db"
        transcript_topics_csv = repo_root / "earningscall_transcripts" / "transcript_topics.csv"

        context_company = str(st.session_state.get("last_genie_context_company", "") or "").strip()
        context_year = st.session_state.get("last_genie_context_year")
        context_quarter = str(st.session_state.get("last_genie_context_quarter", "") or "").strip().upper()
        if not context_quarter or not re.fullmatch(r"Q[1-4]", context_quarter):
            context_quarter = ""
        is_dark_mode = str(get_theme_mode()).strip().lower() == "dark"
        local_plotly_template = "plotly_dark" if is_dark_mode else "plotly_white"

        with st.expander("💭 Thought map", expanded=True):
            response_text = str(st.session_state.get("last_genie_response", "") or "")
            last_user_q = ""
            _hist = st.session_state.get("genie_history", [])
            if _hist:
                for _msg in reversed(_hist):
                    if _msg.get("role") == "user":
                        last_user_q = str(_msg.get("content", ""))
                        break

            intent = _extract_node_intent(response_text, last_user_q)
            primary_co = intent.get("primary_company", "")
            primary_co_lower = primary_co.lower()
            node_type = intent.get("node_type", "default")

            company_color = COMPANY_BRAND_COLORS.get(primary_co_lower, "")
            topic_color = TOPIC_NODE_COLORS.get(node_type, TOPIC_NODE_COLORS["default"])
            node_color = company_color if company_color else topic_color

            # Get logo - use the logos dict if available, else empty
            node_logo_b64 = ""
            try:
                _logos_dict = st.session_state.get("_cached_logos") or {}
                if not _logos_dict:
                    from utils.logos import load_company_logos
                    _logos_dict = load_company_logos()
                    st.session_state["_cached_logos"] = _logos_dict
                # Try multiple name variants
                for _try_name in [primary_co, primary_co_lower, primary_co.split()[0] if primary_co else ""]:
                    if _try_name in _logos_dict:
                        node_logo_b64 = _logos_dict[_try_name]
                        break
                    for k in _logos_dict:
                        if _try_name and k.lower() == _try_name.lower():
                            node_logo_b64 = _logos_dict[k]
                            break
                    if node_logo_b64:
                        break
            except Exception:
                node_logo_b64 = ""

            if node_logo_b64:
                _logo_html = (
                    f"<img src='data:image/png;base64,{node_logo_b64}' "
                    f"style='width:28px;height:28px;border-radius:50%;object-fit:contain;"
                    f"background:white;padding:2px;margin-right:8px;vertical-align:middle;flex-shrink:0;'/>"
                )
            else:
                _initial = primary_co[0].upper() if primary_co else "?"
                _logo_html = (
                    f"<span style='width:28px;height:28px;border-radius:50%;"
                    f"background:{node_color};color:white;display:inline-flex;"
                    f"align-items:center;justify-content:center;font-weight:700;"
                    f"font-size:13px;margin-right:8px;vertical-align:middle;"
                    f"flex-shrink:0;'>{_initial}</span>"
                )

            _type_labels = {
                "forward_signal": "📈 Outlook", "macro": "🌐 Macro",
                "comparison": "⚖️ Comparison", "data": "📊 Data",
                "risk": "⚠️ Risk", "segment": "🔍 Segment",
                "transcript": "🎙️ Transcript", "default": "💬 Analysis",
            }
            _type_badge = _type_labels.get(node_type, "💬 Analysis")

            _cos = intent.get("companies", [])
            _years = intent.get("years", [])
            _quarters = intent.get("quarters", [])
            _metrics = intent.get("metrics", [])

            _period_str = " · ".join([str(y) for y in _years] + _quarters)

            st.markdown(
                f"""<div style='border:1.5px solid {node_color}40;border-radius:12px;
padding:14px 16px;background:{node_color}0d;margin-bottom:12px;'>
<div style='display:flex;align-items:center;margin-bottom:8px;'>
{_logo_html}
<div><span style='font-weight:700;color:{node_color};font-size:14px;'>
{primary_co if primary_co else "General Analysis"}</span>
<span style='margin-left:8px;background:{node_color}20;color:{node_color};
padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600;'>
{_type_badge}</span></div></div>
{f'<div style="font-size:12px;color:#6b7280;margin-bottom:4px;">Companies: <strong>{", ".join(_cos)}</strong></div>' if _cos else ''}
{f'<div style="font-size:12px;color:#6b7280;margin-bottom:4px;">Period: <strong>{_period_str}</strong></div>' if _period_str else ''}
{f'<div style="font-size:12px;color:#6b7280;">Metrics: <strong>{", ".join(_metrics)}</strong></div>' if _metrics else ''}
</div>""",
                unsafe_allow_html=True
            )

            st.markdown(
                "<div style='font-size:11px;color:#9ca3af;text-transform:uppercase;"
                "letter-spacing:.06em;margin-bottom:6px;'>Actions</div>",
                unsafe_allow_html=True
            )

            _primary_year = _years[0] if _years else (
                st.session_state.get("genie_context_year") or 2024
            )
            _primary_quarter = _quarters[0] if _quarters else (
                st.session_state.get("genie_context_quarter") or ""
            )
            _primary_co_for_nav = _cos[0] if _cos else primary_co
            _resp_key = str(hash(response_text[:40]))

            _action_cols = st.columns(2)

            with _action_cols[0]:
                if _primary_co_for_nav and st.button(
                    f"📊 Open {_primary_co_for_nav[:18]} in Earnings",
                    key=f"tm_action_earnings_{_resp_key}",
                    use_container_width=True,
                    help=f"Open Earnings page pre-filtered to {_primary_co_for_nav} · {_primary_year}"
                ):
                    st.session_state["genie_nav_company"] = _primary_co_for_nav
                    st.session_state["genie_nav_year"] = int(_primary_year)
                    st.session_state["genie_nav_quarter"] = _primary_quarter
                    st.session_state["genie_nav_target"] = "earnings"
                    try:
                        st.switch_page("pages/01_Earnings.py")
                    except Exception:
                        st.session_state["_redirect"] = "pages/01_Earnings.py"

            with _action_cols[1]:
                if len(_cos) >= 2 and st.button(
                    f"⚖️ Compare {_cos[0][:10]} vs {_cos[1][:10]}",
                    key=f"tm_action_compare_{_resp_key}",
                    use_container_width=True,
                ):
                    st.session_state["genie_nav_companies"] = _cos[:2]
                    st.session_state["genie_nav_year"] = int(_primary_year)
                    st.session_state["genie_nav_target"] = "overview"
                    try:
                        st.switch_page("pages/00_Overview.py")
                    except Exception:
                        st.session_state["_redirect"] = "pages/00_Overview.py"
                elif len(_cos) < 2 and _primary_co_for_nav and st.button(
                    "🌐 Open in Overview",
                    key=f"tm_action_overview_{_resp_key}",
                    use_container_width=True,
                ):
                    st.session_state["genie_nav_company"] = _primary_co_for_nav
                    st.session_state["genie_nav_target"] = "overview"
                    try:
                        st.switch_page("pages/00_Overview.py")
                    except Exception:
                        st.session_state["_redirect"] = "pages/00_Overview.py"

            _action_cols2 = st.columns(2)

            with _action_cols2[0]:
                _follow_up = ""
                if node_type == "forward_signal" and _primary_co_for_nav:
                    _follow_up = f"What specific guidance did {_primary_co_for_nav} give for next quarter and what are the risks to that outlook?"
                elif node_type == "comparison" and len(_cos) >= 2:
                    _follow_up = f"Which of {_cos[0]} or {_cos[1]} has better margin expansion potential over the next 2 years?"
                elif node_type == "macro":
                    _follow_up = "How do current M2 and Fed rate conditions historically correlate with ad market performance?"
                elif node_type == "transcript" and _primary_co_for_nav:
                    _follow_up = f"What were the 3 most important things {_primary_co_for_nav} management said on the earnings call?"
                elif _primary_co_for_nav:
                    _follow_up = f"What is the biggest strategic risk for {_primary_co_for_nav} in the next 12 months?"

                if _follow_up and st.button(
                    "🔍 Dig deeper",
                    key=f"tm_action_followup_{_resp_key}",
                    use_container_width=True,
                    help=_follow_up[:100]
                ):
                    st.session_state.setdefault("genie_history", []).append(
                        {"role": "user", "content": _follow_up}
                    )
                    st.rerun()

            with _action_cols2[1]:
                if _primary_co_for_nav and st.button(
                    "📺 Mediaset angle",
                    key=f"tm_action_mediaset_{_resp_key}",
                    use_container_width=True,
                    help=f"How should Mediaset think about {_primary_co_for_nav}?"
                ):
                    _mediaset_q = (
                        f"As a European free-to-air broadcaster, how should Mediaset "
                        f"strategically respond to {_primary_co_for_nav}'s recent performance "
                        f"and stated direction? What's the threat and the opportunity?"
                    )
                    st.session_state.setdefault("genie_history", []).append(
                        {"role": "user", "content": _mediaset_q}
                    )
                    st.rerun()

            # Pattern detection
            _hist_companies = []
            for _msg in st.session_state.get("genie_history", []):
                if _msg.get("role") == "user":
                    _msg_intent = _extract_node_intent(_msg.get("content", ""))
                    _hist_companies.extend(_msg_intent.get("companies", []))

            _co_counts = {}
            for _c in _hist_companies:
                _co_counts[_c] = _co_counts.get(_c, 0) + 1

            _streaming_cos = {"Netflix", "Disney", "Paramount", "Warner Bros. Discovery",
                              "Comcast", "Roku", "Spotify"}
            _adtech_cos = {"Alphabet", "Meta Platforms", "Amazon", "Snap", "Pinterest"}
            _session_cos = set(_co_counts.keys())
            _streaming_overlap = _session_cos & _streaming_cos
            _adtech_overlap = _session_cos & _adtech_cos

            if len(_streaming_overlap) >= 2:
                st.markdown(
                    f"<div style='margin-top:10px;padding:10px 14px;background:#f0fdf4;"
                    f"border:1px solid #86efac;border-radius:8px;font-size:12px;color:#15803d;'>"
                    f"🎯 <strong>Pattern detected:</strong> You've been exploring streaming companies "
                    f"({', '.join(list(_streaming_overlap)[:3])})</div>",
                    unsafe_allow_html=True
                )
                if st.button(
                    "⚖️ Compare streaming margins side by side",
                    key=f"tm_pattern_streaming_{hash(str(sorted(_streaming_overlap)))}",
                    use_container_width=True
                ):
                    _q = (
                        f"Compare the streaming segment operating margins and subscriber growth "
                        f"for {', '.join(list(_streaming_overlap)[:4])} — who is closest to "
                        f"sustainable profitability and why?"
                    )
                    st.session_state.setdefault("genie_history", []).append(
                        {"role": "user", "content": _q}
                    )
                    st.rerun()

            if len(_adtech_overlap) >= 2:
                st.markdown(
                    f"<div style='margin-top:10px;padding:10px 14px;background:#eff6ff;"
                    f"border:1px solid #93c5fd;border-radius:8px;font-size:12px;color:#1d4ed8;'>"
                    f"🎯 <strong>Pattern detected:</strong> You've been exploring ad platforms "
                    f"({', '.join(list(_adtech_overlap)[:3])})</div>",
                    unsafe_allow_html=True
                )
                if st.button(
                    "📊 Compare ad revenue growth rates",
                    key=f"tm_pattern_adtech_{hash(str(sorted(_adtech_overlap)))}",
                    use_container_width=True
                ):
                    _q = (
                        f"Compare advertising revenue growth rates for "
                        f"{', '.join(list(_adtech_overlap)[:4])} — which platform "
                        f"is gaining share and which is losing it?"
                    )
                    st.session_state.setdefault("genie_history", []).append(
                        {"role": "user", "content": _q}
                    )
                    st.rerun()

            # Thought map → chart: pre-populate selectors from Genie intent
            _chart_cos = [c for c in intent.get("companies", []) if c in companies]
            _metric_name_map = {v: k for k, v in {"Revenue":"Revenue","Operating Income":"Operating Income","Net Income":"Net Income","R&D":"R&D","Market Cap":"Market Cap","Capex":"Capex","Cash Balance":"Cash Balance"}.items()}
            _chart_metrics = [m for m in intent.get("metrics", []) if m in available_metrics]
            if _chart_cos or _chart_metrics:
                st.markdown("<div style='margin-top:10px;padding:10px 14px;background:#fff7f4;border:1px solid #fed7aa;border-radius:8px;'>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:12px;color:#c2410c;font-weight:600;margin-bottom:6px;'>📊 Chart this analysis</div>", unsafe_allow_html=True)
                if _chart_cos:
                    st.markdown(f"<div style='font-size:11px;color:#6b7280;margin-bottom:4px;'>Companies: <strong style='color:#0f172a'>{', '.join(_chart_cos[:3])}</strong></div>", unsafe_allow_html=True)
                if _chart_metrics:
                    st.markdown(f"<div style='font-size:11px;color:#6b7280;margin-bottom:6px;'>Metrics: <strong style='color:#0f172a'>{', '.join(_chart_metrics[:3])}</strong></div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                if st.button("📊 Plot these in the chart", key=f"tm_chart_{_resp_key}_plot", use_container_width=True):
                    if _chart_cos:
                        st.session_state["company_selector"] = _chart_cos[:3]
                    if _chart_metrics:
                        st.session_state["company_metrics_selector"] = _chart_metrics[:3]
                    st.rerun()

        topic_breakdown_df = pd.DataFrame(columns=["topic", "total"])
        with st.expander("Topic breakdown", expanded=False):
            if not db_path.exists() or not context_company or context_year is None or not context_quarter:
                st.info("No topic data available for this period.")
            else:
                with sqlite3.connect(str(db_path)) as conn:
                    topic_query = """
                        SELECT tt.topic, SUM(tt.mention_count) as total
                        FROM transcript_topics tt
                        JOIN transcripts t ON tt.transcript_id = t.id
                        WHERE t.company=? AND t.year=? AND t.quarter=?
                        GROUP BY tt.topic
                        ORDER BY total DESC
                    """
                    topic_breakdown_df = pd.read_sql_query(
                        topic_query,
                        conn,
                        params=[context_company, int(context_year), context_quarter],
                    )

                if topic_breakdown_df.empty:
                    st.info("No topic data available for this period.")
                else:
                    topic_breakdown_df["total"] = pd.to_numeric(topic_breakdown_df["total"], errors="coerce").fillna(0.0)
                    topic_breakdown_df = topic_breakdown_df.sort_values("total", ascending=False).reset_index(drop=True)

                    topic_color_map = {}
                    try:
                        if excel_path and Path(excel_path).exists():
                            topics_master_df = pd.read_excel(excel_path, sheet_name="Topics_Master")
                            if topics_master_df is not None and not topics_master_df.empty:
                                topics_master_df = topics_master_df.copy()
                                topics_master_df.columns = [str(col).strip().lower() for col in topics_master_df.columns]
                                if "topic_id" in topics_master_df.columns and "color" in topics_master_df.columns:
                                    if "is_active" in topics_master_df.columns:
                                        active_mask = pd.to_numeric(topics_master_df["is_active"], errors="coerce").fillna(1).astype(int) == 1
                                        topics_master_df = topics_master_df[active_mask]
                                    for _, row in topics_master_df.iterrows():
                                        tid = str(row.get("topic_id", "")).strip()
                                        color = str(row.get("color", "")).strip()
                                        if tid and color and color.lower() not in {"nan", "none"}:
                                            topic_color_map[tid] = color
                    except Exception:
                        topic_color_map = {}

                    default_colors = px.colors.qualitative.Plotly
                    bar_colors = []
                    for idx, topic_name in enumerate(topic_breakdown_df["topic"].astype(str).tolist()):
                        bar_colors.append(topic_color_map.get(topic_name, default_colors[idx % len(default_colors)]))

                    topic_fig = go.Figure(
                        data=[
                            go.Bar(
                                x=topic_breakdown_df["total"].tolist(),
                                y=topic_breakdown_df["topic"].astype(str).tolist(),
                                orientation="h",
                                marker=dict(color=bar_colors),
                                hovertemplate="%{y}<br>Mentions: %{x}<extra></extra>",
                            )
                        ]
                    )
                    topic_fig.update_layout(
                        template="plotly_white",
                        title=f"Topic Mentions — {context_company} {int(context_year)} {context_quarter}",
                        title_font=dict(color="#111827", size=13),
                        xaxis_title="Mentions",
                        yaxis_title="Topic",
                        margin=dict(l=20, r=20, t=60, b=20),
                        height=380,
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        font=dict(family="DM Sans, Inter, sans-serif", size=12, color="#374151"),
                        xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)',
                                   showline=False, zeroline=False,
                                   tickfont=dict(size=11, color="#374151")),
                        yaxis=dict(showgrid=False, showline=False, zeroline=False,
                                   tickfont=dict(size=11, color="#374151")),
                        hoverlabel=dict(bgcolor="rgba(17,24,39,0.95)",
                                        bordercolor="rgba(99,179,237,0.4)",
                                        font=dict(size=12, color="#f9fafb")),
                    )
                    topic_fig.update_yaxes(autorange="reversed")
                    st.plotly_chart(topic_fig, use_container_width=True, config={"displayModeBar": False})

        with st.expander("Transcript quotes", expanded=False):
            if topic_breakdown_df.empty or not transcript_topics_csv.exists() or not context_company or context_year is None or not context_quarter:
                st.info("No transcript quotes available.")
            else:
                top_topic = str(topic_breakdown_df.iloc[0]["topic"]).strip()
                quotes_df = pd.read_csv(transcript_topics_csv)
                quotes_df.columns = [str(c).strip() for c in quotes_df.columns]
                if "year" in quotes_df.columns:
                    quotes_df["year"] = pd.to_numeric(quotes_df["year"], errors="coerce")
                if "quarter" in quotes_df.columns:
                    quotes_df["quarter"] = quotes_df["quarter"].astype(str).str.upper().str.strip()
                if "company" in quotes_df.columns:
                    quotes_df["company"] = quotes_df["company"].astype(str).str.strip()
                if "topic" in quotes_df.columns:
                    quotes_df["topic"] = quotes_df["topic"].astype(str).str.strip()

                quotes_df = quotes_df[
                    (quotes_df.get("company", pd.Series(dtype=str)) == context_company)
                    & (quotes_df.get("year", pd.Series(dtype=float)) == float(context_year))
                    & (quotes_df.get("quarter", pd.Series(dtype=str)) == context_quarter)
                    & (quotes_df.get("topic", pd.Series(dtype=str)) == top_topic)
                ].copy()

                if quotes_df.empty:
                    st.info("No transcript quotes available.")
                else:
                    quotes_df["sentence"] = quotes_df["text"] if "text" in quotes_df.columns else ""
                    display_cols = ["sentence", "topic"]
                    if "speaker" in quotes_df.columns:
                        display_cols = ["speaker"] + display_cols
                    st.dataframe(quotes_df[display_cols].head(5), use_container_width=True, hide_index=True)

        with st.expander("Connected companies", expanded=False):
            if topic_breakdown_df.empty or not db_path.exists() or not context_company or context_year is None or not context_quarter:
                st.info("No connected companies found for this period.")
            else:
                top_topics = topic_breakdown_df["topic"].astype(str).head(3).tolist()
                if not top_topics:
                    st.info("No connected companies found for this period.")
                else:
                    placeholders = ",".join(["?"] * len(top_topics))
                    connected_query = f"""
                        SELECT t.company AS company, tt.topic AS topic, SUM(tt.mention_count) as mentions
                        FROM transcript_topics tt
                        JOIN transcripts t ON tt.transcript_id = t.id
                        WHERE tt.topic IN ({placeholders})
                          AND t.year=?
                          AND t.quarter=?
                          AND t.company != ?
                        GROUP BY t.company, tt.topic
                        ORDER BY mentions DESC
                        LIMIT 15
                    """
                    params = top_topics + [int(context_year), context_quarter, context_company]
                    with sqlite3.connect(str(db_path)) as conn:
                        connected_df = pd.read_sql_query(connected_query, conn, params=params)

                    if connected_df.empty:
                        st.info("No connected companies found for this period.")
                    else:
                        st.markdown("**Other companies discussing the same topics**")
                        connected_df["mentions"] = pd.to_numeric(connected_df["mentions"], errors="coerce").fillna(0).astype(int)
                        st.dataframe(
                            connected_df[["company", "topic", "mentions"]],
                            use_container_width=True,
                            hide_index=True,
                        )
    except Exception:
        pass

# ── THOUGHT MAP (rendered inside left column from the side-by-side layout) ──
with _tm_col:
    st.markdown(
        """
    <div style='display:flex; align-items:center; gap:12px; margin-bottom:6px;'>
      <span style='font-size:1.15rem; font-weight:900; color:#e6edf3;'>💭 Thought Map</span>
      <span style='background:rgba(0,115,255,0.1); border:1px solid rgba(0,115,255,0.25);
        border-radius:999px; padding:2px 10px; font-size:0.7rem; font-weight:700;
        color:#0073FF; letter-spacing:0.06em; text-transform:uppercase;'>Beta</span>
    </div>
    <p style='color:#8b949e; font-size:0.85rem; margin-bottom:1rem;'>
      Visual map of Genie's reasoning — grows with every response. Persists across questions.
    </p>
    """,
        unsafe_allow_html=True,
    )
    # Render persistent Cytoscape thought map (session-state backed, survives reruns)
    render_thought_map(height=_tm_height, view_mode=_tm_current_view)
    render_thought_map_controls()

st.markdown("<hr style='margin: 2.5rem 0 1.5rem 0;'>", unsafe_allow_html=True)

# Show helper message if no data is selected
if not selected_companies and not selected_metrics:
    st.info("Select metrics, companies, or enable global data to view the analysis.")
