import json
import os
import base64
import logging
import re
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from utils.workbook_source import get_live_data_xlsx, get_workbook_source_stamp, resolve_financial_data_xlsx


logger = logging.getLogger(__name__)


@st.cache_data(ttl=300, show_spinner=False)
def ensure_intelligence_pipeline_is_fresh() -> dict:
    app_dir = Path(__file__).resolve().parent
    root_dir = app_dir.parent
    transcripts_dir = root_dir / "earningscall_transcripts"
    db_path = root_dir / "earningscall_intelligence.db"

    ONE_HOUR = 3600
    if db_path.exists() and (time.time() - db_path.stat().st_mtime) < ONE_HOUR:
        return {"ran": False, "reason": "DB built recently, skipping rebuild"}

    newest_txt_mtime = 0.0
    if transcripts_dir.exists():
        txt_files = [p for p in transcripts_dir.rglob("*.txt") if p.is_file()]
        xlsx_files = [p for p in transcripts_dir.rglob("*.xlsx") if p.is_file()]
        # Explicitly exclude Excel files from the mtime check
        txt_files = [p for p in txt_files if p.suffix.lower() != ".xlsx"]
        if txt_files:
            newest_txt_mtime = max(p.stat().st_mtime for p in txt_files)

    db_mtime = db_path.stat().st_mtime if db_path.exists() else 0.0
    should_run = (not db_path.exists()) or (newest_txt_mtime > db_mtime)

    if not should_run:
        return {"ran": False}

    transcript_index_path = transcripts_dir / "transcript_index.csv"
    if not transcript_index_path.exists():
        return {"ran": False, "reason": "No transcripts found — skipping pipeline"}
    try:
        transcript_index_df = pd.read_csv(transcript_index_path)
    except Exception:
        transcript_index_df = pd.DataFrame()
    if transcript_index_df.empty:
        return {"ran": False, "reason": "No transcripts found — skipping pipeline"}

    def _run_script(script: str, timeout_seconds: int = 60) -> None:
        try:
            result = subprocess.run(
                [sys.executable, script],
                cwd=str(root_dir),
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            if result.returncode != 0:
                pass  # silently skip failed scripts, never block startup
        except Exception as exc:
            st.warning(f"Pipeline step failed ({script}): {exc}")

    _run_script("scripts/rebuild_transcript_index.py")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_run_script, "scripts/build_intelligence_db.py"),
            pool.submit(_run_script, "scripts/extract_transcript_topics.py"),
        ]
        for future in futures:
            future.result()

    insights_csv = root_dir / "earningscall_transcripts" / "generated_insights_latest.csv"
    if not (insights_csv.exists() and (time.time() - insights_csv.stat().st_mtime) < 86400):
        _run_script("scripts/generate_insights.py", timeout_seconds=180)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_run_script, "scripts/generate_financial_narratives.py"),
            pool.submit(_run_script, "scripts/generate_diagnostic_report.py"),
        ]
        for future in futures:
            future.result()

    return {"ran": True}


# Must stay first Streamlit command
st.set_page_config(
    page_title="Global Media Intelligence",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)
# Set CSS variables and transparent child divs early.
st.markdown(
    """
<style>
:root {
  --bg: #020810;
  --bg2: #030d1a;
  --accent: #4aaeff;
  --accent2: #ff6b6b;
  --text: #e6edf3;
  --muted: #8899aa;
  --alp: #4285f4;
  --meta: #0082fb;
}
html {
    background-color: #020810 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow-x: hidden !important;
}
body {
    background-color: #020810 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow-x: hidden !important;
}
.stApp {
    background-color: #020810 !important;
    background: #020810 !important;
}
section[data-testid="stMain"] {
    background-color: #020810 !important;
    padding: 0 !important;
    margin: 0 !important;
}
div[data-testid="block-container"] {
    background-color: #020810 !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    max-width: 100% !important;
    width: 100% !important;
}
div[data-testid="stVerticalBlock"] {
    background-color: transparent !important;
    gap: 0 !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: transparent !important;
}
div[data-testid="element-container"] {
    background-color: transparent !important;
}
div[data-testid="stHorizontalBlock"] {
    background-color: transparent !important;
}
[data-testid="stDecoration"] {
    display: none !important;
}
[data-testid="stHeader"] {
    background-color: #020810 !important;
}
footer {
    background-color: #020810 !important;
}
iframe {
    display: block !important;
}
.section-label {
    color: #4aaeff;
    font-size: 0.7rem;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    margin-bottom: 10px;
    font-family: 'DM Sans', sans-serif;
}
.section-title {
    color: #ffffff;
    font-size: 1.45rem;
    font-weight: 700;
    line-height: 1.25;
    margin-bottom: 16px;
    font-family: 'Syne', sans-serif;
}
.section-desc {
    color: rgba(255,255,255,0.6);
    font-size: 0.97rem;
    line-height: 1.8;
}
.section-footnote {
    color: rgba(255,255,255,0.35);
    font-size: 0.78rem;
    line-height: 1.6;
    margin-top: 12px;
}
.accent-num {
    color: #4aaeff !important;
    font-weight: 800;
}
.section-desc b {
    color: #4aaeff !important;
    font-weight: 800;
}
.ae-section.ae-visible {
    opacity: 1;
    transform: translateY(0) scale(1);
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<style>iframe{border:none!important;background:#020810!important;}</style>', unsafe_allow_html=True)
_resolved = resolve_financial_data_xlsx([])
logger.info(f"STARTUP: Excel resolved to → {_resolved}")
if "pipeline_refreshed" not in st.session_state:
    st.session_state["pipeline_refreshed"] = False
AUTO_PIPELINE_REFRESH_ENV = "AUTO_REFRESH_INTELLIGENCE_PIPELINE_ON_STARTUP"
if not st.session_state.get("pipeline_refreshed", False):
    auto_refresh_enabled = str(os.getenv(AUTO_PIPELINE_REFRESH_ENV, "")).strip().lower() in {"1", "true", "yes", "on"}
    if auto_refresh_enabled:
        st.session_state["pipeline_refresh_result"] = ensure_intelligence_pipeline_is_fresh()
    else:
        st.session_state["pipeline_refresh_result"] = {
            "ran": False,
            "reason": f"startup intelligence refresh disabled (set {AUTO_PIPELINE_REFRESH_ENV}=1 to enable)",
        }
    st.session_state["pipeline_refreshed"] = True

from utils.global_fonts import apply_global_fonts
from utils.header import display_header
from utils.logos import load_company_logos
from utils.polymarket import fetch_polymarket_top, get_all_company_bets_labelled, COMPANY_LOGO_KEY
from utils.state_management import get_data_processor
from utils.theme import get_theme_mode
from utils.transcript_startup_sync import sync_local_transcripts_to_workbook

# One-time sync per container startup (not per session)
SYNC_FLAG_FILE = "/tmp/transcript_sync_done"
AUTO_SYNC_ENV = "AUTO_SYNC_TRANSCRIPTS_ON_STARTUP"


def _run_startup_transcript_sync() -> None:
    if os.path.exists(SYNC_FLAG_FILE):
        return
    try:
        sync_local_transcripts_to_workbook(timeout_seconds=30)
        with open(SYNC_FLAG_FILE, "w", encoding="utf-8") as handle:
            handle.write(str(datetime.now()))
    except Exception as exc:
        st.warning(f"Transcript sync failed: {exc}")


# Transcript sync runs once per container (flag file prevents repeats).
# Enabled by default so Transcript Intelligence works on HF Spaces.
# Set AUTO_SYNC_TRANSCRIPTS_ON_STARTUP=0 to disable.
# Disabled by default for faster startup — set AUTO_SYNC_TRANSCRIPTS_ON_STARTUP=1 to enable
if str(os.getenv(AUTO_SYNC_ENV, "0")).strip().lower() not in {"0", "false", "no", "off"}:
    _run_startup_transcript_sync()


st.session_state["active_nav_page"] = "home"
st.session_state["_active_nav_page"] = "home"
display_header(enable_dom_patch=False)
# Re-apply Welcome dark animation CSS *after* apply_theme so it wins the cascade.
st.markdown(
    """
<style>
.stApp {
    background-color: #020810 !important;
    background-image:
        radial-gradient(ellipse 90% 70% at 15% 25%, rgba(74,174,255,0.18) 0%, transparent 55%),
        radial-gradient(ellipse 70% 90% at 85% 75%, rgba(0,82,251,0.14) 0%, transparent 55%),
        radial-gradient(ellipse 50% 60% at 55% 55%, rgba(10,40,120,0.22) 0%, transparent 60%) !important;
    background-size: 400% 400% !important;
    animation: wlbSmoke 22s ease-in-out infinite alternate !important;
}
@keyframes wlbSmoke {
    0%   { background-position: 0%   0%;   }
    20%  { background-position: 80%  15%;  }
    40%  { background-position: 30%  90%;  }
    60%  { background-position: 100% 50%;  }
    80%  { background-position: 20%  70%;  }
    100% { background-position: 90%  100%; }
}
</style>
""",
    unsafe_allow_html=True,
)
apply_global_fonts()


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent


def _mount_welcome_liquid_background() -> None:
    """No-op — background handled entirely via CSS (html/body animation in st.markdown)."""
    st.markdown("<div id='welcome-liquid-sentinel' style='display:none'></div>", unsafe_allow_html=True)


_mount_welcome_liquid_background()

# Hero image removed — was loading 1.5MB at startup but never rendered


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _format_money_musd(value, precision: int = 1) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"

    sign = "-" if number < 0 else ""
    amount = abs(number)
    if amount >= 1_000_000:
        return f"{sign}${amount / 1_000_000:.{precision}f}T"
    if amount >= 1_000:
        return f"{sign}${amount / 1_000:.{precision}f}B"
    return f"{sign}${amount:.{precision}f}M"


def _safe_pct(numerator, denominator):
    if denominator in (None, 0) or pd.isna(denominator):
        return None
    if numerator is None or pd.isna(numerator):
        return None
    return float(numerator) / float(denominator) * 100


def _build_hero_narrative(year: int, revenue_fmt: str, growth_pct: Optional[float], company_count: int) -> str:
    n = company_count or "N/A"
    if growth_pct is None:
        return f"In {year}, the tracked universe reported {revenue_fmt} in combined revenue across {n} major media and technology players."
    if growth_pct >= 8:
        return (
            f"In {year}, the tracked universe generated {revenue_fmt} in combined revenue, accelerating "
            f"{growth_pct:.1f}% YoY on the back of sustained monetization strength across {n} major players."
        )
    if growth_pct >= 2:
        return (
            f"In {year}, combined revenue reached {revenue_fmt} — a {growth_pct:.1f}% YoY expansion across {n} "
            "tracked companies, reflecting steady but moderating growth momentum."
        )
    if growth_pct >= 0:
        return (
            f"In {year}, revenue grew modestly to {revenue_fmt} (+{growth_pct:.1f}% YoY), signaling a "
            f"normalization phase across the {n}-company universe."
        )
    return (
        f"In {year}, combined revenue contracted to {revenue_fmt} ({growth_pct:.1f}% YoY), with margin pressure "
        f"visible across the {n}-company universe."
    )


def _company_color(company: str) -> str:
    palette = {
        "Alphabet": "#4285F4",
        "Apple": "#A3A3A3",
        "Meta": "#0866FF",
        "Meta Platforms": "#0866FF",
        "Microsoft": "#00A4EF",
        "Amazon": "#FF9900",
        "Netflix": "#E50914",
        "Disney": "#113CCF",
        "Comcast": "#0088D2",
        "Warner Bros. Discovery": "#4a90d9",
        "Paramount Global": "#7B2FBE",
        "Spotify": "#1DB954",
        "Roku": "#6F1AB1",
        # Platform-specific names
        "YouTube": "#FF0000",
        "Facebook": "#0866FF",
        "Meta – Facebook": "#0866FF",
        "Instagram": "#C13584",
        "Meta – Instagram": "#C13584",
        "WhatsApp": "#25D366",
        "Twitch": "#9147FF",
        "Amazon – Twitch": "#9147FF",
        "Disney+": "#113CCF",
        "Disney+ / Hulu / ESPN+": "#113CCF",
        "WBD": "#4a90d9",
        "WBD Max": "#4a90d9",
        "Max (WBD)": "#4a90d9",
        "WBD Max / HBO": "#4a90d9",
        "Paramount+": "#7B2FBE",
        "Peacock": "#9B2335",
        "Comcast Peacock": "#9B2335",
        "Amazon Prime": "#FF9900",
        "Amazon Prime Video": "#FF9900",
    }
    return palette.get(company, "#4a90d9")


def _resolve_logo(company: str, logos: Dict[str, str]) -> str:
    if company in logos:
        return logos[company]
    aliases = {
        "Meta": "Meta Platforms",
        "Warner Bros Discovery": "Warner Bros. Discovery",
        "Paramount": "Paramount Global",
    }
    alt = aliases.get(company)
    if alt and alt in logos:
        return logos[alt]
    for key in logos:
        if key.lower() == company.lower():
            return logos[key]
    return ""


def _render_company_logos(companies_raw: str, logos: Dict[str, str]) -> str:
    if not companies_raw:
        return ""
    chips = []
    for token in str(companies_raw).replace(",", "|").split("|"):
        name = token.strip()
        if not name:
            continue
        img_b64 = _resolve_logo(name, logos)
        if not img_b64:
            continue
        chips.append(
            "<span class='wm-mini-logo-wrap'>"
            f"<img class='wm-mini-logo' src='data:image/png;base64,{img_b64}' alt='{escape(name)} logo' />"
            "</span>"
        )
    if not chips:
        return ""
    return f"<div class='wm-insight-logos'>{''.join(chips)}</div>"


def _clean_signal_title(raw_title: str) -> str:
    title = str(raw_title or "").strip()
    title = re.sub(r"\s*\(auto\)\s*$", "", title, flags=re.IGNORECASE)
    return title


def _build_hero_company_logo_bar(logos: Dict[str, str]) -> str:
    logo_order = [
        "Alphabet",
        "Meta Platforms",
        "Amazon",
        "Apple",
        "Microsoft",
        "Netflix",
        "Disney",
        "Comcast",
        "Paramount Global",
        "Warner Bros. Discovery",
        "Spotify",
        "Roku",
    ]
    blocks: List[str] = []
    for company in logo_order:
        img_b64 = _resolve_logo(company, logos)
        if not img_b64:
            continue
        company_q = quote_plus(company)
        blocks.append(
            f"<a class='wm-hero-logo-link' href='Earnings?company={company_q}' "
            f"target='_self' rel='noopener' "
            f"aria-label='Open earnings for {escape(company)}'>"
            "<span class='wm-hero-logo-wrap'>"
            f"<img class='wm-hero-logo' src='data:image/png;base64,{img_b64}' alt='{escape(company)} logo' />"
            "</span>"
            "</a>"
        )
    if not blocks:
        return ""
    return f"<div class='wm-hero-logo-bar'>{''.join(blocks)}</div>"


def _render_leaderboard_strip(title: str, subtitle: str, cards: List[dict]) -> None:
    if not cards:
        return
    visible_cards = cards

    header_html = (
        "<div class='wm-strip-header'>"
        f"<div class='wm-strip-title'>{escape(str(title))}</div>"
        f"<div class='wm-strip-subtitle'>{escape(str(subtitle))}</div>"
        "</div>"
    )

    card_blocks = []
    for card in visible_cards:
        company_name = str(card.get("company", "Unknown")).strip()
        company_color = str(card.get("color") or _company_color(company_name))
        rank = card.get("rank")
        rank_badge = f"<span class='wm-rank'>{int(rank)}</span>" if isinstance(rank, (int, float)) else ""
        logo_b64 = str(card.get("logo", "") or "").strip()
        logo_html = (
            f"<img class='wm-company-logo' src='data:image/png;base64,{logo_b64}' alt='{escape(company_name)} logo'/>"
            if logo_b64
            else ""
        )
        value_text = escape(str(card.get("value", "N/A")))
        yoy_pct = card.get("yoy_pct")
        if isinstance(yoy_pct, (int, float)) and not pd.isna(yoy_pct):
            yoy_arrow = "↑" if float(yoy_pct) >= 0 else "↓"
            yoy_color = "#22c55e" if float(yoy_pct) >= 0 else "#ef4444"
            yoy_html = f"<div class='wm-company-yoy' style='color:{yoy_color};'>{yoy_arrow} {abs(float(yoy_pct)):.1f}% YoY</div>"
        else:
            yoy_html = ""
        card_blocks.append(
            f"<div class='wm-company-card wm-strip-card' style='--wm-color:{company_color};'>"
            f"{rank_badge}"
            "<div class='wm-company-head'>"
            f"{logo_html}<span class='wm-company-name'>{escape(company_name)}</span>"
            "</div>"
            f"<div class='wm-company-value'>{value_text}</div>"
            f"{yoy_html}"
            f"<div class='wm-company-caption'>{escape(title)}</div>"
            "</div>"
        )

    # Show the "scroll for more" indicator only when there are hidden cards
    # beyond what we actually render.
    if len(cards) > len(visible_cards):
        card_blocks.append(
            "<div class='wm-strip-card wm-more-indicator'>"
            "<div class='wm-more-arrow'>→</div>"
            f"<div class='wm-more-label'>Scroll for<br/>{len(cards)} companies</div>"
            "</div>"
        )

    st.markdown(
        f"{header_html}<div class='wm-hscroll'>{''.join(card_blocks)}</div>",
        unsafe_allow_html=True,
    )


def _resolve_workbook_path(data_path: Optional[str] = None) -> Optional[Path]:
    if data_path:
        candidate = Path(data_path)
        if candidate.exists():
            return candidate

    resolved = resolve_financial_data_xlsx([])
    if not resolved:
        return None

    path = Path(resolved)
    return path if path.exists() else None


DEFAULT_HOME_NARRATIVE_FALLBACK = (
    "In 2024, the tracked universe generated $2.1T in combined revenue, accelerating 9.6% YoY "
    "on the back of sustained monetization strength across 12 major players."
)

_QUARTER_SORT = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

_COMPANY_ALIASES = {
    "ALPHABET": "Alphabet",
    "GOOGLE": "Alphabet",
    "META": "Meta Platforms",
    "META PLATFORMS": "Meta Platforms",
    "AMAZON": "Amazon",
    "APPLE": "Apple",
    "MICROSOFT": "Microsoft",
    "NETFLIX": "Netflix",
    "DISNEY": "Disney",
    "COMCAST": "Comcast",
    "PARAMOUNT": "Paramount Global",
    "PARAMOUNT GLOBAL": "Paramount Global",
    "WARNER BROS DISCOVERY": "Warner Bros. Discovery",
    "WARNER BROS. DISCOVERY": "Warner Bros. Discovery",
    "WBD": "Warner Bros. Discovery",
    "SPOTIFY": "Spotify",
    "ROKU": "Roku",
}

_AD_COLUMN_TO_COMPANY = {
    "GOOGLE ADS": "Alphabet",
    "META ADS": "Meta Platforms",
    "AMAZON ADS": "Amazon",
    "SPOTIFY ADS": "Spotify",
    "WBD ADS": "Warner Bros. Discovery",
    "MICROSOFT ADS": "Microsoft",
    "PARAMOUNT": "Paramount Global",
    "APPLE": "Apple",
    "DISNEY": "Disney",
    "COMCAST": "Comcast",
    "NETFLIX": "Netflix",
}


def _normalize_quarter_label(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if text in _QUARTER_SORT:
        return text
    number_match = re.search(r"([1-4])", text)
    if number_match:
        return f"Q{number_match.group(1)}"
    return text


def _quarter_sort_value(value: Any) -> int:
    return _QUARTER_SORT.get(_normalize_quarter_label(value), 0)


def _normalize_company_name(value: Any) -> str:
    text = str(value or "").replace("_", " ").strip()
    text = re.sub(r"\s+", " ", text)
    canonical = _COMPANY_ALIASES.get(text.upper())
    return canonical if canonical else text


def _company_variants(company: str) -> list[str]:
    canonical = _normalize_company_name(company)
    variants = {canonical}
    reverse_aliases = {
        "Meta Platforms": {"Meta"},
        "Warner Bros. Discovery": {"Warner Bros Discovery", "WBD"},
        "Paramount Global": {"Paramount"},
        "Alphabet": {"Google"},
    }
    variants.update(reverse_aliases.get(canonical, set()))
    return sorted({v.strip() for v in variants if v and str(v).strip()})


_UNKNOWN_SPEAKER_VALUES = {"", "unknown", "n/a", "none", "nan"}
_ROLE_SPEAKER_LABELS = {
    "CEO": "Chief Executive Officer",
    "CFO": "Chief Financial Officer",
    "COO": "Chief Operating Officer",
}


def _resolve_speaker_label(
    *,
    speaker: Any = "",
    name: Any = "",
    executive: Any = "",
    who: Any = "",
    rolebucket: Any = "",
    role: Any = "",
) -> str:
    for raw in (speaker, name, executive, who):
        value = str(raw or "").strip()
        if value and value.lower() not in _UNKNOWN_SPEAKER_VALUES:
            return value

    role_value = str(rolebucket or "").strip() or str(role or "").strip()
    if role_value:
        return _ROLE_SPEAKER_LABELS.get(role_value.upper(), role_value)
    return "Executive"


def _split_company_tokens(raw: Any) -> list[str]:
    tokens = re.split(r"[|,;/]", str(raw or ""))
    return [token.strip() for token in tokens if token and token.strip()]


def _normalize_text_for_compare(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


@st.cache_resource(ttl=300)
def _get_excel_handle(excel_path: str, source_stamp: int):
    """Open the XLSX file once and cache the ExcelFile handle.

    Avoids reopening the 21 MB zip + re-parsing the shared-strings table
    on every individual sheet read (~1-2 s overhead per open, ×10 sheets).
    """
    _ = source_stamp
    if not excel_path:
        return None
    try:
        return pd.ExcelFile(excel_path)
    except Exception as exc:
        logger.warning("Failed to open workbook handle: %s", exc)
        return None


@st.cache_data(ttl=300, show_spinner=False)
def _read_excel_sheet_cached(excel_path: str, sheet_name: str, source_stamp: int) -> pd.DataFrame:
    _ = source_stamp
    if not excel_path:
        return pd.DataFrame()
    try:
        xls = _get_excel_handle(excel_path, source_stamp)
        if xls is not None:
            df = pd.read_excel(xls, sheet_name=sheet_name)
        else:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
    except Exception as exc:
        logger.warning("Failed to read sheet '%s' from %s: %s", sheet_name, excel_path, exc)
        return pd.DataFrame()
    if df is None or df.empty:
        logger.info("Sheet '%s' is empty in %s", sheet_name, excel_path)
        return pd.DataFrame()
    return df.copy()


def _pick_col(df: pd.DataFrame, aliases: list[str]) -> str:
    normalized = {
        re.sub(r"[^a-z0-9]+", "", str(col).strip().lower()): str(col).strip() for col in df.columns
    }
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return ""


@st.cache_data(ttl=300, show_spinner=False)
def _load_company_metrics_sheet(excel_path: str, source_stamp: int) -> pd.DataFrame:
    raw = _read_excel_sheet_cached(excel_path, "Company_metrics_earnings_values", source_stamp)
    if raw.empty:
        return pd.DataFrame()

    company_col = _pick_col(raw, ["company", "ticker", "name"])
    year_col = _pick_col(raw, ["year", "fiscalyear"])
    revenue_col = _pick_col(raw, ["revenue", "totalrevenue"])
    net_income_col = _pick_col(raw, ["netincome"])
    operating_income_col = _pick_col(raw, ["operatingincome", "operatingprofit"])
    market_cap_col = _pick_col(raw, ["marketcap", "marketcapitalization"])
    rd_col = _pick_col(raw, ["rd", "researchanddevelopment", "researchdevelopment"])

    if not company_col or not year_col:
        return pd.DataFrame()

    df = pd.DataFrame(
        {
            "company": raw[company_col],
            "year": raw[year_col],
            "revenue": raw[revenue_col] if revenue_col else np.nan,
            "net_income": raw[net_income_col] if net_income_col else np.nan,
            "operating_income": raw[operating_income_col] if operating_income_col else np.nan,
            "market_cap": raw[market_cap_col] if market_cap_col else np.nan,
            "rd": raw[rd_col] if rd_col else np.nan,
        }
    )
    df["company"] = df["company"].apply(_normalize_company_name)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    for col in ["revenue", "net_income", "operating_income", "market_cap", "rd"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["company", "year"]).copy()
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["year"].astype(int)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _load_overview_macro_sheet(excel_path: str, source_stamp: int) -> pd.DataFrame:
    raw = _read_excel_sheet_cached(excel_path, "Overview_Macro", source_stamp)
    if raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    if "year" not in df.columns:
        return pd.DataFrame()
    if "quarter" not in df.columns:
        df["quarter"] = ""
    if "macro_comment" not in df.columns:
        df["macro_comment"] = ""
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["quarter"] = df["quarter"].apply(_normalize_quarter_label)
    df["macro_comment"] = df["macro_comment"].astype(str).str.strip()
    df = df.dropna(subset=["year"]).copy()
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["year"].astype(int)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _load_auto_insights(excel_path: str, source_stamp: int, selected_year: int, selected_quarter: str) -> pd.DataFrame:
    raw = _read_excel_sheet_cached(excel_path, "Overview_Auto_Insights", source_stamp)
    if raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]

    for col in ["title", "text", "comment", "priority", "companies", "sort_order", "year", "quarter", "is_active"]:
        if col not in df.columns:
            df[col] = np.nan if col in {"sort_order", "year"} else ""

    df["is_active"] = pd.to_numeric(df["is_active"], errors="coerce").fillna(0).astype(int)
    df = df[df["is_active"] == 1].copy()
    if df.empty:
        return pd.DataFrame()

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["quarter"] = df["quarter"].apply(_normalize_quarter_label)
    df["sort_order"] = pd.to_numeric(df["sort_order"], errors="coerce")
    df["priority"] = df["priority"].astype(str).str.strip().str.lower()

    year_scope = df[df["year"] == int(selected_year)].copy()
    if not year_scope.empty:
        df = year_scope

    rank_map = {"high": 0, "medium": 1, "low": 2}
    df["priority_rank"] = df["priority"].map(rank_map).fillna(3).astype(int)
    df = df.sort_values(["priority_rank", "sort_order", "title"], na_position="last")
    return df.head(6).copy()


@st.cache_data(ttl=300, show_spinner=False)
def _load_company_ad_revenue_sheet(excel_path: str, source_stamp: int) -> pd.DataFrame:
    raw = _read_excel_sheet_cached(excel_path, "Company_advertising_revenue", source_stamp)
    if raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    df.columns = [str(col).strip() for col in df.columns]
    year_col = ""
    for candidate in df.columns:
        if str(candidate).strip().lower() == "year":
            year_col = candidate
            break
    if not year_col:
        return pd.DataFrame()
    df["Year"] = pd.to_numeric(df[year_col], errors="coerce")
    return df.dropna(subset=["Year"]).copy()


@st.cache_data(ttl=300, show_spinner=False)
def _load_company_employees_sheet(excel_path: str, source_stamp: int) -> pd.DataFrame:
    raw = _read_excel_sheet_cached(excel_path, "Company_Employees", source_stamp)
    if raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    company_col = "company" if "company" in df.columns else ""
    year_col = "year" if "year" in df.columns else ""
    employee_col = ""
    for candidate in ["employee count", "employee_count", "employees", "employee"]:
        if candidate in df.columns:
            employee_col = candidate
            break
    if not company_col or not year_col or not employee_col:
        return pd.DataFrame()
    out = pd.DataFrame(
        {
            "company": df[company_col].apply(_normalize_company_name),
            "year": pd.to_numeric(df[year_col], errors="coerce"),
            "employees": pd.to_numeric(df[employee_col], errors="coerce"),
        }
    )
    out = out.dropna(subset=["company", "year"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["year"] = out["year"].astype(int)
    return out


def _select_latest_quarter_for_year(macro_df: pd.DataFrame, year: int) -> str:
    if macro_df.empty:
        return "Q4"
    scoped = macro_df[macro_df["year"] == int(year)].copy()
    if scoped.empty:
        return "Q4"
    scoped["q_sort"] = scoped["quarter"].apply(_quarter_sort_value)
    scoped = scoped.sort_values(["year", "q_sort"], ascending=[False, False])
    quarter = str(scoped.iloc[0].get("quarter", "") or "").strip()
    return quarter if quarter else "Q4"


@st.cache_data(ttl=300, show_spinner=False)
def _load_m2_yearly_series(excel_path: str, source_stamp: int) -> pd.DataFrame:
    raw = _read_excel_sheet_cached(excel_path, "M2", source_stamp)
    if raw.empty:
        raw = _read_excel_sheet_cached(excel_path, "M2_values", source_stamp)
    if raw.empty:
        return pd.DataFrame(columns=["year", "m2_value"])

    df = raw.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    date_col = ""
    for candidate in ["observation_date", "observation date", "date", "period"]:
        if candidate in df.columns:
            date_col = candidate
            break
    if not date_col:
        for col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().mean() >= 0.7:
                date_col = col
                df["_parsed_date"] = parsed
                break
    if "_parsed_date" not in df.columns:
        if not date_col:
            return pd.DataFrame(columns=["year", "m2_value"])
        df["_parsed_date"] = pd.to_datetime(df[date_col], errors="coerce")

    value_col = ""
    preferred = {"wm2ns", "wm2", "m2", "m2sl", "m2value", "value"}
    for col in df.columns:
        normalized = re.sub(r"[^a-z0-9]+", "", col.lower())
        if normalized in preferred:
            value_col = col
            break
    if not value_col:
        excluded = {date_col, "_parsed_date", "year"}
        numeric_candidates = []
        for col in df.columns:
            if col in excluded:
                continue
            numeric = pd.to_numeric(df[col], errors="coerce")
            if numeric.notna().sum() > 0:
                numeric_candidates.append(col)
        if numeric_candidates:
            value_col = numeric_candidates[0]
    if not value_col:
        return pd.DataFrame(columns=["year", "m2_value"])

    out = pd.DataFrame(
        {
            "date": df["_parsed_date"],
            "m2_value": pd.to_numeric(df[value_col], errors="coerce"),
        }
    )
    out = out.dropna(subset=["date", "m2_value"]).copy()
    if out.empty:
        return pd.DataFrame(columns=["year", "m2_value"])
    out["year"] = out["date"].dt.year.astype(int)
    out = out.groupby("year", as_index=False)["m2_value"].mean()
    return out


@st.cache_data(ttl=300, show_spinner=False)
def _load_m2_monthly_series(excel_path: str, source_stamp: int) -> pd.DataFrame:
    """Load M2 at full monthly granularity for the animated chart."""
    raw = _read_excel_sheet_cached(excel_path, "M2", source_stamp)
    if raw.empty:
        raw = _read_excel_sheet_cached(excel_path, "M2_values", source_stamp)
    if raw.empty:
        return pd.DataFrame(columns=["date", "m2_value"])
    df = raw.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    date_col = ""
    for candidate in ["observation_date", "observation date", "date", "period", "he"]:
        if candidate in df.columns:
            date_col = candidate
            break
    if not date_col:
        for col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().mean() >= 0.7:
                date_col = col
                break
    if not date_col:
        return pd.DataFrame(columns=["date", "m2_value"])
    df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    value_col = ""
    preferred = {"m2sl", "wm2ns", "wm2", "m2", "m2value", "value"}
    for col in df.columns:
        normalized = re.sub(r"[^a-z0-9]+", "", col.lower())
        if normalized in preferred:
            value_col = col
            break
    if not value_col:
        excluded = {date_col, "_date"}
        for col in df.columns:
            if col in excluded:
                continue
            numeric = pd.to_numeric(df[col], errors="coerce")
            if numeric.notna().sum() > 0:
                value_col = col
                break
    if not value_col:
        return pd.DataFrame(columns=["date", "m2_value"])
    out = pd.DataFrame({
        "date": df["_date"],
        "m2_value": pd.to_numeric(df[value_col], errors="coerce"),
    })
    out = out.dropna(subset=["date", "m2_value"]).sort_values("date").reset_index(drop=True)
    return out


@st.cache_data(ttl=300, show_spinner=False)
def _build_ss_ad_json_bundle(excel_path: str, source_stamp: int) -> dict:
    """Build structural-shift donut, ad-revenue bubble, and global-adv denominator JSON — all cached.

    Self-contained: loads data from cached sheet readers so this function
    returns instantly from Streamlit cache on every re-run.
    """
    # ── Load global_adv_df ──
    gadf = _read_excel_sheet_cached(excel_path, "Global_Adv_Aggregates", source_stamp) if excel_path else pd.DataFrame()
    if not gadf.empty:
        gadf = gadf.copy()
        gadf.columns = [str(c).strip() for c in gadf.columns]
        gadf["year"] = pd.to_numeric(gadf["year"], errors="coerce")
        gadf["value"] = pd.to_numeric(gadf["value"], errors="coerce")
        gadf = gadf.dropna(subset=["year", "value"])
        gadf["year"] = gadf["year"].astype(int)

    # Global totals $B
    totals = (gadf.groupby("year")["value"].sum() / 1_000.0).round(1) if not gadf.empty else pd.Series(dtype=float)
    if totals.empty:
        totals = pd.Series(
            {2010: 502.0, 2011: 528.0, 2012: 557.0, 2013: 574.0, 2014: 598.0,
             2015: 614.0, 2016: 632.0, 2017: 663.0, 2018: 706.0, 2019: 709.0,
             2020: 633.0, 2021: 745.0, 2022: 781.0, 2023: 849.0, 2024: 942.0},
            dtype=float,
        )

    # Channel-level fallback for structural shift
    if gadf.empty:
        _fb_channels = {
            "Free TV": {2010: 180000, 2012: 175000, 2014: 170000, 2016: 162000, 2018: 155000, 2020: 135000, 2022: 140000, 2024: 138000},
            "Pay TV": {2010: 45000, 2012: 50000, 2014: 52000, 2016: 50000, 2018: 48000, 2020: 42000, 2022: 40000, 2024: 38000},
            "Search Desktop": {2010: 30000, 2012: 45000, 2014: 56000, 2016: 68000, 2018: 85000, 2020: 80000, 2022: 100000, 2024: 115000},
            "Search Mobile": {2010: 2000, 2012: 8000, 2014: 20000, 2016: 42000, 2018: 65000, 2020: 72000, 2022: 95000, 2024: 125000},
            "Social Desktop": {2010: 5000, 2012: 8000, 2014: 12000, 2016: 16000, 2018: 20000, 2020: 18000, 2022: 22000, 2024: 24000},
            "Social Mobile": {2010: 500, 2012: 3000, 2014: 10000, 2016: 25000, 2018: 42000, 2020: 50000, 2022: 72000, 2024: 95000},
            "Video Desktop": {2010: 3000, 2012: 5000, 2014: 8000, 2016: 12000, 2018: 16000, 2020: 18000, 2022: 22000, 2024: 26000},
            "Video Mobile": {2010: 200, 2012: 1000, 2014: 3000, 2016: 8000, 2018: 14000, 2020: 18000, 2022: 28000, 2024: 38000},
            "Display Desktop": {2010: 25000, 2012: 28000, 2014: 30000, 2016: 32000, 2018: 34000, 2020: 30000, 2022: 32000, 2024: 34000},
            "Display Mobile": {2010: 1000, 2012: 4000, 2014: 10000, 2016: 18000, 2018: 25000, 2020: 28000, 2022: 35000, 2024: 42000},
            "Traditional OOH": {2010: 28000, 2012: 29000, 2014: 30000, 2016: 30000, 2018: 31000, 2020: 22000, 2022: 28000, 2024: 30000},
            "Digital OOH": {2010: 1000, 2012: 2000, 2014: 3000, 2016: 5000, 2018: 8000, 2020: 6000, 2022: 12000, 2024: 16000},
            "Magazine": {2010: 42000, 2012: 38000, 2014: 34000, 2016: 28000, 2018: 24000, 2020: 16000, 2022: 14000, 2024: 12000},
            "Newspaper": {2010: 85000, 2012: 72000, 2014: 62000, 2016: 52000, 2018: 42000, 2020: 28000, 2022: 24000, 2024: 20000},
            "Radio": {2010: 32000, 2012: 33000, 2014: 34000, 2016: 33000, 2018: 33000, 2020: 26000, 2022: 30000, 2024: 31000},
            "Cinema": {2010: 2500, 2012: 3000, 2014: 3500, 2016: 4000, 2018: 4500, 2020: 1000, 2022: 3000, 2024: 4000},
            "Other Desktop": {2010: 10000, 2012: 12000, 2014: 14000, 2016: 15000, 2018: 16000, 2020: 14000, 2022: 16000, 2024: 17000},
            "Other Mobile": {2010: 500, 2012: 2000, 2014: 5000, 2016: 10000, 2018: 15000, 2020: 18000, 2022: 24000, 2024: 30000},
        }
        _fb_rows = []
        for _mt, _yr_vals in _fb_channels.items():
            for _yr, _val in _yr_vals.items():
                _fb_rows.append({"year": _yr, "metric_type": _mt, "value": float(_val)})
        gadf = pd.DataFrame(_fb_rows)

    # ── Structural-shift donut ──
    _ss_mt_to_ch = {
        "Free TV": "Free TV", "Pay TV": "Free TV",
        "Magazine": "Print", "Newspaper": "Print",
        "Search Desktop": "Digital Search", "Search Mobile": "Digital Search",
        "Social Desktop": "Digital Social", "Social Mobile": "Digital Social",
        "Video Desktop": "Digital Video", "Video Mobile": "Digital Video",
    }
    _ss_data: dict = {}
    if not gadf.empty:
        _ss_keys = ["Free TV", "Print", "Digital Search", "Digital Social", "Digital Video", "Everything Else"]
        for _ss_yr, _ss_grp in gadf.groupby("year"):
            _yr_dict: dict = {k: 0.0 for k in _ss_keys}
            for _ss_row in _ss_grp.itertuples(index=False):
                _mt = str(getattr(_ss_row, "metric_type", "")).strip().replace(" Worldwide", "").strip()
                _ch = _ss_mt_to_ch.get(_mt, "Everything Else")
                _yr_dict[_ch] += float(_ss_row.value)
            if sum(_yr_dict.values()) > 0:
                _ss_data[int(_ss_yr)] = {k: round(v) for k, v in _yr_dict.items()}
    if not _ss_data:
        _ss_data = {
            2010: {"Free TV": 195000, "Print": 108000, "Digital Search": 43000, "Digital Social": 6000, "Digital Video": 5000, "Everything Else": 145000},
            2012: {"Free TV": 201000, "Print": 96000, "Digital Search": 58000, "Digital Social": 12000, "Digital Video": 8000, "Everything Else": 182000},
            2014: {"Free TV": 205000, "Print": 82000, "Digital Search": 72000, "Digital Social": 22000, "Digital Video": 14000, "Everything Else": 203000},
            2016: {"Free TV": 200000, "Print": 68000, "Digital Search": 89000, "Digital Social": 37000, "Digital Video": 22000, "Everything Else": 216000},
            2018: {"Free TV": 192000, "Print": 54000, "Digital Search": 108000, "Digital Social": 62000, "Digital Video": 36000, "Everything Else": 254000},
            2019: {"Free TV": 185000, "Print": 46000, "Digital Search": 116000, "Digital Social": 74000, "Digital Video": 42000, "Everything Else": 246000},
            2020: {"Free TV": 158000, "Print": 34000, "Digital Search": 118000, "Digital Social": 82000, "Digital Video": 48000, "Everything Else": 193000},
            2021: {"Free TV": 172000, "Print": 30000, "Digital Search": 140000, "Digital Social": 112000, "Digital Video": 62000, "Everything Else": 229000},
            2022: {"Free TV": 168000, "Print": 27000, "Digital Search": 146000, "Digital Social": 118000, "Digital Video": 72000, "Everything Else": 250000},
            2023: {"Free TV": 162000, "Print": 24000, "Digital Search": 164000, "Digital Social": 136000, "Digital Video": 86000, "Everything Else": 277000},
            2024: {"Free TV": 156000, "Print": 21000, "Digital Search": 184000, "Digital Social": 156000, "Digital Video": 102000, "Everything Else": 323000},
        }

    # ── Ad revenue by year ──
    _ad_col_map = {
        "Google_Ads": "Alphabet", "Meta_Ads": "Meta", "Amazon_Ads": "Amazon",
        "Spotify_Ads": "Spotify", "*WBD_Ads": "WBD", "*Microsoft_Ads": "Microsoft",
        "Paramount": "Paramount", "*Apple": "Apple", "*Disney": "Disney",
        "*Comcast": "Comcast", "Netflix*": "Netflix", "Twitter/X": "Twitter/X",
        "TikTok": "TikTok", "Snapchat": "Snapchat",
    }
    asdf = _load_company_ad_revenue_sheet(excel_path, source_stamp) if excel_path else pd.DataFrame()
    _ad_by_year: dict = {}
    if not asdf.empty:
        # Use to_dict to handle column names with special chars (* prefix etc.)
        for _arow_dict in asdf.to_dict(orient="records"):
            try:
                _yr = int(_arow_dict.get("Year", 0))
            except (TypeError, ValueError):
                continue
            _ad_by_year[_yr] = {}
            for _col, _name in _ad_col_map.items():
                _v = _arow_dict.get(_col)
                if _v is not None and pd.notna(_v):
                    try:
                        _vf = float(_v)
                        if _vf > 0:
                            _ad_by_year[_yr][_name] = round(_vf, 2)
                    except (TypeError, ValueError):
                        pass
    if not _ad_by_year:
        _ad_by_year = {
            2018: {"Alphabet": 136.2, "Meta": 55.0, "Amazon": 10.1, "Apple": 2.0, "Microsoft": 7.0, "Netflix": 0.0, "Comcast": 0.0, "Disney": 0.0, "TikTok": 0.3},
            2019: {"Alphabet": 162.0, "Meta": 69.7, "Amazon": 14.1, "Apple": 3.0, "Microsoft": 7.7, "Netflix": 0.0, "Comcast": 0.0, "Disney": 0.0, "TikTok": 1.2},
            2020: {"Alphabet": 147.0, "Meta": 84.2, "Amazon": 19.8, "Apple": 3.5, "Microsoft": 8.0, "Netflix": 0.0, "Comcast": 0.0, "Disney": 0.0, "TikTok": 3.8},
            2021: {"Alphabet": 209.5, "Meta": 115.7, "Amazon": 31.2, "Apple": 5.0, "Microsoft": 10.0, "Netflix": 0.0, "Comcast": 0.0, "Disney": 0.0, "TikTok": 9.4},
            2022: {"Alphabet": 224.5, "Meta": 113.6, "Amazon": 37.7, "Apple": 6.0, "Microsoft": 12.0, "Netflix": 0.8, "Comcast": 0.0, "Disney": 0.0, "TikTok": 14.5},
            2023: {"Alphabet": 223.0, "Meta": 131.9, "Amazon": 46.9, "Apple": 6.5, "Microsoft": 12.2, "Netflix": 1.5, "Comcast": 0.0, "Disney": 0.0, "TikTok": 18.0},
            2024: {"Alphabet": 237.0, "Meta": 160.0, "Amazon": 56.2, "Apple": 7.0, "Microsoft": 13.0, "Netflix": 2.2, "Comcast": 0.0, "Disney": 0.0, "TikTok": 22.0},
        }

    # ── Global adv by year for JS denominator ──
    _global_adv_by_year: dict = {}
    for _gyr, _gval in totals.items():
        if _gval and _gval > 0:
            _global_adv_by_year[int(_gyr)] = round(float(_gval), 1)

    return {
        "ss_data_json": json.dumps(_ss_data),
        "ad_json_str": json.dumps(_ad_by_year),
        "global_adv_json_str": json.dumps(_global_adv_by_year),
    }


@st.cache_data(ttl=300, show_spinner=False)
def _build_revenue_anatomy_json(excel_path: str, source_stamp: int) -> str:
    """Build revenue anatomy year-data JSON — cached."""
    _metrics = _load_company_metrics_sheet(excel_path, source_stamp) if excel_path else pd.DataFrame()
    _adsheet = _load_company_ad_revenue_sheet(excel_path, source_stamp) if excel_path else pd.DataFrame()
    _wr_companies = ["Alphabet", "Amazon", "Apple", "Microsoft", "Meta", "Netflix", "Disney", "Comcast", "Spotify", "Roku"]
    _wr_year_data: dict = {}
    if _metrics.empty or _adsheet.empty:
        return json.dumps(_wr_year_data)
    _wr_ad_lookup: dict = {}
    for _wr_row_dict in _adsheet.to_dict(orient="records"):
        try:
            _wr_yr = int(_wr_row_dict.get("Year", 0))
        except (TypeError, ValueError):
            continue
        for _wr_col in _adsheet.columns:
            if str(_wr_col).strip().lower() == "year":
                continue
            _wr_mapped_co, _ = _map_ad_column_to_company(_wr_col)
            if _wr_mapped_co:
                _wr_val = pd.to_numeric(_wr_row_dict.get(_wr_col), errors="coerce")
                if pd.notna(_wr_val):
                    _wr_ad_lookup[(_wr_yr, _wr_mapped_co)] = float(_wr_val)
    for _wr_yr in sorted(_metrics["year"].unique()):
        _wr_yr_int = int(_wr_yr)
        if _wr_yr_int < 2015:
            continue
        _yr_rows = _metrics[_metrics["year"] == _wr_yr_int]
        _yr_entries = []
        for _mr in _yr_rows.itertuples(index=False):
            _co = str(_mr.company)
            if _co not in _wr_companies:
                continue
            _total_b = float(_mr.revenue) / 1000.0 if pd.notna(_mr.revenue) else 0.0
            _ad_b = _wr_ad_lookup.get((_wr_yr_int, _co), 0.0)
            if _total_b > 0:
                _yr_entries.append({"name": _co, "total": round(_total_b, 1), "ad": round(_ad_b, 1)})
        if _yr_entries:
            _wr_year_data[_wr_yr_int] = sorted(_yr_entries, key=lambda x: x["total"], reverse=True)
    return json.dumps(_wr_year_data)


def _build_home_narrative(
    year: int,
    metrics_df: pd.DataFrame,
    ad_df: pd.DataFrame,
    macro_df: pd.DataFrame,
    m2_df: pd.DataFrame,
) -> str:
    selected_year = int(year)

    total_revenue = None
    revenue_yoy_pct = None
    if isinstance(metrics_df, pd.DataFrame) and not metrics_df.empty and {"year", "revenue"}.issubset(metrics_df.columns):
        current = metrics_df[metrics_df["year"] == selected_year]["revenue"]
        if not current.empty:
            total_revenue = float(pd.to_numeric(current, errors="coerce").sum())
        previous = metrics_df[metrics_df["year"] == (selected_year - 1)]["revenue"]
        if total_revenue is not None and not previous.empty:
            prev_total = float(pd.to_numeric(previous, errors="coerce").sum())
            if prev_total not in (0, None) and not pd.isna(prev_total):
                revenue_yoy_pct = ((total_revenue - prev_total) / abs(prev_total)) * 100.0

    duopoly_share = None
    if isinstance(ad_df, pd.DataFrame) and not ad_df.empty and "Year" in ad_df.columns:
        scoped = ad_df[pd.to_numeric(ad_df["Year"], errors="coerce") == selected_year]
        if not scoped.empty:
            row = scoped.iloc[-1]
            total_ad = 0.0
            google_ad = 0.0
            meta_ad = 0.0
            for col in ad_df.columns:
                if str(col).strip().lower() == "year":
                    continue
                value = pd.to_numeric(row.get(col), errors="coerce")
                if pd.isna(value):
                    continue
                value_musd = float(value) * 1000.0
                total_ad += value_musd
                clean = str(col).strip().lstrip("*")
                norm = re.sub(r"[^a-z0-9]+", " ", clean.lower()).strip()
                if norm == "google ads":
                    google_ad += value_musd
                if norm == "meta ads":
                    meta_ad += value_musd
            if total_ad > 0:
                duopoly_share = ((google_ad + meta_ad) / total_ad) * 100.0

    digital_share = None
    if isinstance(macro_df, pd.DataFrame) and not macro_df.empty and "year" in macro_df.columns:
        scoped = macro_df[macro_df["year"] == selected_year].copy()
        if not scoped.empty:
            row = scoped.sort_values("quarter", key=lambda s: s.map(_quarter_sort_value)).iloc[-1]
            internet = pd.to_numeric(pd.Series([row.get("internet_ad_spend", np.nan)]), errors="coerce").iloc[0]
            total_market = pd.to_numeric(pd.Series([row.get("global_ad_market", np.nan)]), errors="coerce").iloc[0]
            if pd.notna(internet) and pd.notna(total_market) and float(total_market) != 0.0:
                digital_share = (float(internet) / float(total_market)) * 100.0

    m2_growth = None
    if isinstance(m2_df, pd.DataFrame) and not m2_df.empty and {"year", "m2_value"}.issubset(m2_df.columns):
        curr = m2_df[m2_df["year"] == selected_year]["m2_value"]
        prev = m2_df[m2_df["year"] == (selected_year - 1)]["m2_value"]
        if not curr.empty and not prev.empty:
            curr_val = float(pd.to_numeric(curr, errors="coerce").iloc[-1])
            prev_val = float(pd.to_numeric(prev, errors="coerce").iloc[-1])
            if prev_val not in (0, None) and not pd.isna(prev_val):
                m2_growth = ((curr_val - prev_val) / abs(prev_val)) * 100.0

    if total_revenue is None:
        return DEFAULT_HOME_NARRATIVE_FALLBACK.replace("2024", str(selected_year))

    sentence_one = f"In {selected_year}, the tracked universe generated {_format_money_musd(total_revenue, 1)} in combined revenue"
    if revenue_yoy_pct is not None:
        sentence_one += f" ({revenue_yoy_pct:+.1f}% YoY)"
    if digital_share is not None:
        sentence_one += f", with digital advertising at {digital_share:.1f}% of total spend"
    sentence_one += "."

    sentence_two = ""
    if duopoly_share is not None:
        sentence_two = f"The Alphabet/Meta duopoly controlled {duopoly_share:.1f}% of tracked ad revenue"
        if m2_growth is not None:
            sentence_two += f", against a backdrop of {m2_growth:.1f}% M2 growth"
        sentence_two += "."
    elif m2_growth is not None:
        sentence_two = f"M2 grew {m2_growth:.1f}% year over year."

    return f"{sentence_one} {sentence_two}".strip()


def _macro_comment_is_placeholder(comment: str) -> bool:
    text = str(comment or "").strip()
    if not text:
        return False
    return bool(re.search(r"(baseline\s*row|update\s*this)", text, flags=re.IGNORECASE))


def _pick_macro_comment_for_period(macro_df: pd.DataFrame, year: int, quarter: str) -> str:
    if macro_df is None or macro_df.empty:
        return ""
    if "year" not in macro_df.columns or "macro_comment" not in macro_df.columns:
        return ""

    scoped = macro_df[pd.to_numeric(macro_df["year"], errors="coerce") == int(year)].copy()
    if scoped.empty:
        return ""

    scoped["quarter"] = scoped["quarter"].apply(_normalize_quarter_label)
    quarter_norm = _normalize_quarter_label(quarter)
    exact = scoped[scoped["quarter"] == quarter_norm].copy() if quarter_norm else pd.DataFrame()
    if not exact.empty:
        candidate = exact.iloc[-1]
    else:
        scoped["q_sort"] = scoped["quarter"].apply(_quarter_sort_value)
        candidate = scoped.sort_values("q_sort").iloc[-1]

    return str(candidate.get("macro_comment", "") or "").strip()


def _map_ad_column_to_company(raw_col_name: str) -> tuple[str, bool]:
    raw = str(raw_col_name or "").strip()
    is_estimated = raw.startswith("*")
    clean = raw.lstrip("*").strip()
    normalized = re.sub(r"[^a-z0-9]+", " ", clean.lower()).strip().upper()
    company = _AD_COLUMN_TO_COMPANY.get(normalized, "")
    return (company, is_estimated)


@st.cache_data(ttl=300, show_spinner=False)
def _load_ad_revenue_by_company(excel_path: str, source_stamp: int, selected_year: int) -> dict[str, dict[str, Any]]:
    ad_df = _load_company_ad_revenue_sheet(excel_path, source_stamp)
    if ad_df.empty:
        return {}
    scoped = ad_df[ad_df["Year"] == int(selected_year)].copy()
    if scoped.empty:
        return {}
    row = scoped.iloc[-1]
    output: dict[str, dict[str, Any]] = {}
    for col in ad_df.columns:
        if str(col).strip().lower() in {"year"}:
            continue
        company, is_estimated = _map_ad_column_to_company(col)
        if not company:
            continue
        value = pd.to_numeric(row.get(col), errors="coerce")
        if pd.isna(value):
            continue
        ad_musd = float(value) * 1000.0
        bucket = output.setdefault(company, {"ad_revenue_musd": 0.0, "ad_estimated": False})
        bucket["ad_revenue_musd"] = float(bucket.get("ad_revenue_musd", 0.0)) + ad_musd
        bucket["ad_estimated"] = bool(bucket.get("ad_estimated", False) or is_estimated)
    return output


def _format_people(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    number = float(value)
    if number >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"
    if number >= 1_000:
        return f"{number / 1_000:.1f}K"
    return f"{int(number):,}"


@st.cache_data(ttl=900, show_spinner=False)
def _build_bubble_dataset(excel_path: str, source_stamp: int, selected_year: int) -> pd.DataFrame:
    metrics = _load_company_metrics_sheet(excel_path, source_stamp)
    if metrics.empty:
        return pd.DataFrame()
    metrics = metrics[metrics["year"] == int(selected_year)].copy()
    if metrics.empty:
        return pd.DataFrame()

    ad_lookup = _load_ad_revenue_by_company(excel_path, source_stamp, selected_year)
    employees_df = _load_company_employees_sheet(excel_path, source_stamp)

    employee_lookup: dict[str, float] = {}
    if not employees_df.empty:
        for company, group in employees_df.groupby("company"):
            exact = group[group["year"] == int(selected_year)]
            if not exact.empty:
                employee_lookup[company] = float(exact.iloc[-1]["employees"]) if pd.notna(exact.iloc[-1]["employees"]) else np.nan
                continue
            prior = group[group["year"] <= int(selected_year)].sort_values("year")
            if not prior.empty:
                employee_lookup[company] = float(prior.iloc[-1]["employees"]) if pd.notna(prior.iloc[-1]["employees"]) else np.nan
                continue
            latest = group.sort_values("year")
            employee_lookup[company] = float(latest.iloc[-1]["employees"]) if pd.notna(latest.iloc[-1]["employees"]) else np.nan

    rows: list[dict[str, Any]] = []
    for row in metrics.itertuples(index=False):
        company = _normalize_company_name(getattr(row, "company", ""))
        revenue = pd.to_numeric(pd.Series([getattr(row, "revenue", np.nan)]), errors="coerce").iloc[0]
        op_income = pd.to_numeric(pd.Series([getattr(row, "operating_income", np.nan)]), errors="coerce").iloc[0]
        market_cap = pd.to_numeric(pd.Series([getattr(row, "market_cap", np.nan)]), errors="coerce").iloc[0]
        rd_value = pd.to_numeric(pd.Series([getattr(row, "rd", np.nan)]), errors="coerce").iloc[0]
        if pd.isna(revenue) or pd.isna(market_cap):
            continue

        ad_info = ad_lookup.get(company, {})
        ad_revenue = pd.to_numeric(pd.Series([ad_info.get("ad_revenue_musd", np.nan)]), errors="coerce").iloc[0]
        ad_estimated = bool(ad_info.get("ad_estimated", False))

        op_margin = float(op_income) / float(revenue) * 100.0 if pd.notna(op_income) and float(revenue) != 0.0 else np.nan
        ad_dependency = float(ad_revenue) / float(revenue) * 100.0 if pd.notna(ad_revenue) and float(revenue) != 0.0 else np.nan
        employees = employee_lookup.get(company, np.nan)

        rows.append(
            {
                "company": company,
                "revenue": float(revenue),
                "revenue_b": float(revenue) / 1000.0,
                "op_margin": float(op_margin) if pd.notna(op_margin) else np.nan,
                "market_cap": float(market_cap),
                "market_cap_b": float(market_cap) / 1000.0,
                "ad_revenue": float(ad_revenue) if pd.notna(ad_revenue) else np.nan,
                "ad_revenue_b": (float(ad_revenue) / 1000.0) if pd.notna(ad_revenue) else np.nan,
                "ad_dependency": float(ad_dependency) if pd.notna(ad_dependency) else np.nan,
                "rd": float(rd_value) if pd.notna(rd_value) else np.nan,
                "employees": float(employees) if pd.notna(employees) else np.nan,
                "ad_estimated": ad_estimated,
            }
        )

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    out["hover_revenue"] = out["revenue"].apply(lambda v: f"Revenue: {_format_money_musd(v, 1)}")
    out["hover_op_margin"] = out["op_margin"].apply(lambda v: f"Operating Margin: {v:.1f}%" if pd.notna(v) else "Operating Margin: N/A")
    out["hover_market_cap"] = out["market_cap"].apply(lambda v: f"Market Cap: {_format_money_musd(v, 1)}")
    out["hover_ad_revenue"] = out.apply(
        lambda r: (
            f"Ad Revenue: {_format_money_musd(r['ad_revenue'], 1)}{'*' if bool(r.get('ad_estimated', False)) else ''}"
            if pd.notna(r.get("ad_revenue"))
            else "Ad Revenue: N/A"
        ),
        axis=1,
    )
    out["hover_rd"] = out["rd"].apply(lambda v: f"R&D: {_format_money_musd(v, 1)}" if pd.notna(v) else "R&D: N/A")
    out["hover_employees"] = out["employees"].apply(lambda v: f"Employees: {_format_people(v)}")
    return out


def _pick_primary_company_for_insight(row: pd.Series, available_companies: list[str]) -> str:
    known = {c.lower(): c for c in available_companies}

    for token in _split_company_tokens(row.get("companies", "")):
        canonical = _normalize_company_name(token)
        if canonical.lower() in known:
            return known[canonical.lower()]

    title = str(row.get("title", "") or "").strip()
    if ":" in title:
        prefix = title.split(":", 1)[0].strip()
        canonical = _normalize_company_name(prefix)
        if canonical.lower() in known:
            return known[canonical.lower()]

    haystack = f"{row.get('title', '')} {row.get('text', '')} {row.get('comment', '')}".lower()
    for company in available_companies:
        if company.lower() in haystack:
            return company
    return ""


def _sqlite_has_column(conn: sqlite3.Connection, table_name: str, col_name: str) -> bool:
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except Exception:
        return False
    return any(str(row[1]).strip().lower() == str(col_name).strip().lower() for row in rows)


@st.cache_data(ttl=600, show_spinner=False)
def _get_best_quote_for_insight(company: str, year: int, quarter: str, db_path: str) -> Optional[dict]:
    if not company or not db_path:
        return None
    db_file = Path(db_path)
    if not db_file.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
    except Exception:
        return None

    try:
        role_bucket_available = _sqlite_has_column(conn, "transcript_highlights", "role_bucket")
        company_values = [v.lower() for v in _company_variants(company)]
        placeholders = ",".join(["?"] * len(company_values))
        q_norm = _normalize_quarter_label(quarter)
        base_select = """
            SELECT
                h.text AS text,
                h.speaker AS speaker,
                {role_expr} AS role_bucket,
                h.highlight_type AS highlight_type,
                h.relevance_score AS relevance_score,
                t.year AS year,
                t.quarter AS quarter
            FROM transcript_highlights h
            JOIN transcripts t ON t.id = h.transcript_id
            WHERE lower(trim(t.company)) IN ({placeholders})
              AND {role_filter}
        """
        role_expr = "h.role_bucket" if role_bucket_available else "''"
        role_filter = (
            "upper(trim(ifnull(h.role_bucket, ''))) IN ('CEO', 'CFO')"
            if role_bucket_available
            else "(lower(ifnull(h.highlight_type, '')) LIKE '%ceo%' OR lower(ifnull(h.highlight_type, '')) LIKE '%cfo%')"
        )
        base_sql = base_select.format(role_expr=role_expr, placeholders=placeholders, role_filter=role_filter)

        exact_sql = (
            base_sql
            + """
              AND t.year = ?
              AND upper(trim(t.quarter)) = ?
            ORDER BY h.relevance_score DESC
            LIMIT 1
            """
        )
        row = conn.execute(exact_sql, (*company_values, int(year), q_norm)).fetchone()

        if row is None:
            fallback_sql = (
                base_sql
                + """
                ORDER BY h.relevance_score DESC, t.year DESC,
                    CASE upper(trim(t.quarter))
                        WHEN 'Q4' THEN 4
                        WHEN 'Q3' THEN 3
                        WHEN 'Q2' THEN 2
                        WHEN 'Q1' THEN 1
                        ELSE 0
                    END DESC
                LIMIT 1
                """
            )
            row = conn.execute(fallback_sql, tuple(company_values)).fetchone()

        if row is None:
            return None

        role_bucket = str(row["role_bucket"] or "").strip().upper()
        if role_bucket not in {"CEO", "CFO"}:
            highlight_type = str(row["highlight_type"] or "").strip().lower()
            if "ceo" in highlight_type:
                role_bucket = "CEO"
            elif "cfo" in highlight_type:
                role_bucket = "CFO"
            else:
                return None

        text = str(row["text"] or "").strip()
        speaker = str(row["speaker"] or "").strip()
        if not text:
            return None
        return {
            "text": text,
            "speaker": speaker if speaker else "Unknown",
            "role": role_bucket,
            "score": row["relevance_score"],
        }
    except Exception:
        return None
    finally:
        conn.close()


def _normalize_quotes_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    aliases = {
        "company": ["company", "ticker", "service"],
        "year": ["year"],
        "quarter": ["quarter", "qtr"],
        "speaker": ["speaker", "speaker_name"],
        "name": ["name"],
        "executive": ["executive"],
        "who": ["who"],
        "role_bucket": ["role_bucket", "rolebucket", "speaker_role", "role"],
        "rolebucket": ["rolebucket", "role_bucket"],
        "role": ["role", "title", "speaker_role", "position"],
        "highlight_type": ["highlight_type"],
        "quote": ["quote", "text", "highlight", "comment", "insight"],
        "score": ["score", "relevance_score", "importance", "rank_score"],
    }
    out = pd.DataFrame()
    for target, names in aliases.items():
        out[target] = ""
        for name in names:
            if name in df.columns:
                out[target] = df[name]
                break

    out["company"] = out["company"].apply(_normalize_company_name)
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out["quarter"] = out["quarter"].apply(_normalize_quarter_label)
    out["speaker"] = out["speaker"].astype(str).str.strip()
    out["name"] = out["name"].astype(str).str.strip()
    out["executive"] = out["executive"].astype(str).str.strip()
    out["who"] = out["who"].astype(str).str.strip()
    out["quote"] = out["quote"].astype(str).str.strip()
    out["score"] = pd.to_numeric(out["score"], errors="coerce")

    def _role_from_row(r: pd.Series) -> str:
        role_text = str(r.get("role_bucket", "") or "").strip().upper()
        if role_text not in {"CEO", "CFO"}:
            role_text = str(r.get("rolebucket", "") or "").strip().upper()
        if role_text in {"CEO", "CFO"}:
            return role_text
        hl = str(r.get("highlight_type", "") or "").strip().lower()
        if "ceo" in hl:
            return "CEO"
        if "cfo" in hl:
            return "CFO"
        return ""

    out["role_bucket"] = out.apply(_role_from_row, axis=1)
    out["speaker"] = out.apply(
        lambda r: _resolve_speaker_label(
            speaker=r.get("speaker", ""),
            name=r.get("name", ""),
            executive=r.get("executive", ""),
            who=r.get("who", ""),
            rolebucket=r.get("rolebucket", "") or r.get("role_bucket", ""),
            role=r.get("role", ""),
        ),
        axis=1,
    )
    out = out.dropna(subset=["year"]).copy()
    out = out[(out["company"] != "") & (out["quote"] != "")].copy()
    if out.empty:
        return pd.DataFrame()
    out["year"] = out["year"].astype(int)
    return out


@st.cache_data(ttl=600, show_spinner=False)
def _load_pulse_quotes_csv(repo_root_path: str) -> pd.DataFrame:
    repo_root = Path(repo_root_path)
    candidates = [
        repo_root / "earningscall_transcripts" / "overview_iconic_quotes.csv",
        repo_root / "earningscall_transcripts" / "transcript_highlights.csv",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            raw = pd.read_csv(path)
        except Exception:
            continue
        normalized = _normalize_quotes_frame(raw)
        if not normalized.empty:
            return normalized
    return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def _load_pulse_quotes_sqlite(db_path: str) -> pd.DataFrame:
    db_file = Path(db_path)
    if not db_file.exists():
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
    except Exception:
        return pd.DataFrame()
    try:
        role_bucket_available = _sqlite_has_column(conn, "transcript_highlights", "role_bucket")
        role_expr = "h.role_bucket" if role_bucket_available else "''"
        role_filter = (
            "upper(trim(ifnull(h.role_bucket, ''))) = 'CEO'"
            if role_bucket_available
            else "lower(ifnull(h.highlight_type, '')) LIKE '%ceo%'"
        )
        sql = f"""
            SELECT
                t.company AS company,
                t.year AS year,
                t.quarter AS quarter,
                h.speaker AS speaker,
                {role_expr} AS role_bucket,
                h.highlight_type AS highlight_type,
                h.text AS quote,
                h.relevance_score AS score
            FROM transcript_highlights h
            JOIN transcripts t ON t.id = h.transcript_id
            WHERE {role_filter}
            ORDER BY t.year DESC,
                CASE upper(trim(t.quarter))
                    WHEN 'Q4' THEN 4
                    WHEN 'Q3' THEN 3
                    WHEN 'Q2' THEN 2
                    WHEN 'Q1' THEN 1
                    ELSE 0
                END DESC,
                h.relevance_score DESC
            LIMIT 150
        """
        rows = conn.execute(sql).fetchall()
        if not rows:
            return pd.DataFrame()
        raw = pd.DataFrame([dict(row) for row in rows])
        return _normalize_quotes_frame(raw)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600, show_spinner=False)
def _load_transcript_pulse_quotes(repo_root_path: str, db_path: str, selected_year: int, selected_quarter: str, limit: int = 5, data_path: str = "") -> tuple[pd.DataFrame, str]:
    csv_df = _load_pulse_quotes_csv(repo_root_path)
    source_label = ""
    working = csv_df.copy()
    if not working.empty:
        source_label = "earningscall_transcripts/overview_iconic_quotes.csv"
    else:
        working = _load_pulse_quotes_sqlite(db_path)
        if not working.empty:
            source_label = "earningscall_intelligence.db (transcript_highlights)"

    if working.empty:
        # Fallback 3 — live extraction from Transcripts sheet
        try:
            from utils.transcript_live import extract_pulse_quotes as _live_pulse
            _ep = data_path
            _live_results = _live_pulse(str(_ep), max_quotes=25)
            if _live_results:
                _live_df = pd.DataFrame(_live_results)
                _live_df = _live_df.rename(columns={"role": "role_bucket"})
                for col in ["company", "speaker", "role_bucket", "quote", "year", "quarter"]:
                    if col not in _live_df.columns:
                        _live_df[col] = ""
                return (_live_df, "live transcript extraction")
        except Exception:
            pass
        return (pd.DataFrame(), "")

    working = working[working["role_bucket"] == "CEO"].copy()
    if working.empty:
        return (pd.DataFrame(), source_label)

    q_norm = _normalize_quarter_label(selected_quarter)
    period = working[(working["year"] == int(selected_year)) & (working["quarter"] == q_norm)].copy()
    if not period.empty:
        working = period

    working["q_sort"] = working["quarter"].apply(_quarter_sort_value)
    working = working.sort_values(["year", "q_sort", "score"], ascending=[False, False, False])
    return (working.head(int(limit)).copy(), source_label)


@st.cache_data(ttl=300, show_spinner=False)
def _load_page_data():
    try:
        dp = get_data_processor()
        raw_metrics = getattr(dp, "df_metrics", pd.DataFrame())
        metrics_df_cached = raw_metrics.copy() if raw_metrics is not None else pd.DataFrame()
        companies_cached = dp.get_companies() if hasattr(dp, "get_companies") else []
        data_path = str(getattr(dp, "data_path", "") or "")
        source_stamp = int(getattr(dp, "source_stamp", 0) or 0)
        return {
            "metrics_df": metrics_df_cached,
            "companies": companies_cached,
            "data_path": data_path,
            "source_stamp": source_stamp,
            "error": "",
        }
    except Exception as exc:
        return {
            "metrics_df": pd.DataFrame(),
            "companies": [],
            "data_path": "",
            "source_stamp": 0,
            "error": str(exc),
        }


# Load data
logos = load_company_logos()
logos_original = dict(logos)  # preserve originals for globe + bubble chart (no white override)
# Load YouTube logo separately (not a tracked company, so not in logos dict)
try:
    _yt_path = APP_DIR / "attached_assets" / "Youtube_logo.png"
    if _yt_path.exists():
        logos_original["YouTube"] = base64.b64encode(_yt_path.read_bytes()).decode()
except Exception:
    pass
# Override Amazon/Apple with white-on-dark variants — used ONLY for stock strip + revenue anatomy
for _wl_co, _wl_path in {
    "Amazon": "attached_assets/Amazonwhite_logo.png",
    "Apple":  "attached_assets/AppleWhite_logo.png",
}.items():
    try:
        _wl_full = APP_DIR / _wl_path
        if _wl_full.exists():
            logos[_wl_co] = base64.b64encode(_wl_full.read_bytes()).decode()
    except Exception:
        pass
mode = get_theme_mode()
is_dark = mode == "dark"

page_data = _load_page_data()
metrics_df_fallback = page_data.get("metrics_df", pd.DataFrame())
source_stamp = int(page_data.get("source_stamp", 0) or 0)
data_path = str(page_data.get("data_path", "") or "")

if page_data.get("error"):
    st.warning(f"Data initialization warning: {page_data['error']}")

workbook_path = _resolve_workbook_path(data_path)
excel_path = str(workbook_path) if workbook_path else ""

# Live path: always reads Minute / Daily / Holders from Google Sheets (1-hour refresh).
# Falls back to the local file if the download is unavailable.
_live_xlsx = get_live_data_xlsx(refresh_seconds=3600)
live_excel_path: str = _live_xlsx if _live_xlsx else excel_path
live_source_stamp: int = get_workbook_source_stamp(_live_xlsx) if _live_xlsx else source_stamp

metrics_df = _load_company_metrics_sheet(excel_path, source_stamp) if excel_path else pd.DataFrame()
if metrics_df.empty and not metrics_df_fallback.empty:
    fallback = metrics_df_fallback.copy()
    fallback.columns = [str(col).strip().lower() for col in fallback.columns]
    for col in ["company", "year", "revenue", "net_income", "operating_income", "market_cap", "rd"]:
        if col not in fallback.columns:
            fallback[col] = np.nan
    fallback["company"] = fallback["company"].apply(_normalize_company_name)
    fallback["year"] = pd.to_numeric(fallback["year"], errors="coerce")
    for col in ["revenue", "net_income", "operating_income", "market_cap", "rd"]:
        fallback[col] = pd.to_numeric(fallback[col], errors="coerce")
    fallback = fallback.dropna(subset=["company", "year"]).copy()
    if not fallback.empty:
        fallback["year"] = fallback["year"].astype(int)
        metrics_df = fallback[["company", "year", "revenue", "net_income", "operating_income", "market_cap", "rd"]]

# ── Hardcoded fallback if no metrics data loaded at all (values in $M) ──
if metrics_df.empty:
    logger.warning("Company_metrics_earnings_values sheet unavailable — using fallback metrics")
    _fb_rows = []
    _fb_companies = {
        #                          rev_2023, rev_2024, mcap_2023, mcap_2024
        "Alphabet":                (307394, 350018, 1750000, 2100000),
        "Meta Platforms":          (134902, 164500, 900000, 1500000),
        "Amazon":                  (574785, 638000, 1550000, 2100000),
        "Apple":                   (383285, 391035, 2900000, 3700000),
        "Microsoft":               (211915, 245122, 2800000, 3100000),
        "Netflix":                 (33723, 39000, 220000, 330000),
        "Disney":                  (88898, 91000, 165000, 200000),
        "Comcast":                 (121572, 122000, 175000, 170000),
        "Spotify":                 (13247, 16000, 60000, 90000),
        "Warner Bros. Discovery":  (41317, 39900, 28000, 26000),
        "Paramount Global":        (29650, 28600, 9000, 8000),
        "Roku":                    (3484, 4100, 10000, 12000),
    }
    for _co, (_r23, _r24, _m23, _m24) in _fb_companies.items():
        _fb_rows.append({"company": _co, "year": 2023, "revenue": _r23, "net_income": np.nan, "operating_income": np.nan, "market_cap": _m23, "rd": np.nan})
        _fb_rows.append({"company": _co, "year": 2024, "revenue": _r24, "net_income": np.nan, "operating_income": np.nan, "market_cap": _m24, "rd": np.nan})
    metrics_df = pd.DataFrame(_fb_rows)

available_years = sorted(metrics_df["year"].dropna().unique().tolist()) if not metrics_df.empty else []
latest_year = int(max(available_years)) if available_years else 2024
home_year_options = [int(y) for y in available_years if 2015 <= int(y) <= 2024]
if not home_year_options:
    home_year_options = [int(y) for y in available_years] if available_years else [latest_year]
home_year_default = int(home_year_options[-1]) if home_year_options else latest_year

macro_df = _load_overview_macro_sheet(excel_path, source_stamp) if excel_path else pd.DataFrame()
ad_sheet_df = _load_company_ad_revenue_sheet(excel_path, source_stamp) if excel_path else pd.DataFrame()
m2_yearly_df = _load_m2_yearly_series(excel_path, source_stamp) if excel_path else pd.DataFrame()
m2_monthly_df = _load_m2_monthly_series(excel_path, source_stamp) if excel_path else pd.DataFrame()

# ── Fallback: if M2 sheet is missing, use known US M2 money supply by year ($T) ──
if m2_yearly_df.empty:
    logger.warning("M2 sheet unavailable — using fallback M2 money supply data")
    m2_yearly_df = pd.DataFrame({
        "year": [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019,
                 2020, 2021, 2022, 2023, 2024],
        "m2_value": [8.8, 9.6, 10.4, 10.9, 11.6, 12.3, 13.2, 13.8, 14.4, 15.3,
                     19.1, 21.6, 21.4, 20.8, 21.4],
    })

# Load Global_Adv_Aggregates (country-level aggregate, values in $M) for total market denominator
global_adv_df = _read_excel_sheet_cached(excel_path, "Global_Adv_Aggregates", source_stamp) if excel_path else pd.DataFrame()
if not global_adv_df.empty:
    global_adv_df.columns = [str(c).strip() for c in global_adv_df.columns]
    global_adv_df["year"] = pd.to_numeric(global_adv_df["year"], errors="coerce")
    global_adv_df["value"] = pd.to_numeric(global_adv_df["value"], errors="coerce")
    global_adv_df = global_adv_df.dropna(subset=["year", "value"])
    global_adv_df["year"] = global_adv_df["year"].astype(int)
# Per-year totals in $B (values in sheet are $M → ÷1000)
_global_adv_totals: "pd.Series" = (
    global_adv_df.groupby("year")["value"].sum() / 1_000.0
).round(1) if not global_adv_df.empty else pd.Series(dtype=float)

# ── Fallback: if Global_Adv_Aggregates failed to load, use known industry totals ($B) ──
if _global_adv_totals.empty:
    logger.warning("Global_Adv_Aggregates sheet unavailable — using fallback totals")
    _global_adv_totals = pd.Series(
        {2010: 502.0, 2011: 528.0, 2012: 557.0, 2013: 574.0, 2014: 598.0,
         2015: 614.0, 2016: 632.0, 2017: 663.0, 2018: 706.0, 2019: 709.0,
         2020: 633.0, 2021: 745.0, 2022: 781.0, 2023: 849.0, 2024: 942.0},
        dtype=float,
    )

# ── Fallback: if global_adv_df is empty, build channel-level fallback for area chart ──
if global_adv_df.empty:
    logger.warning("Global_Adv_Aggregates sheet unavailable — using channel-level fallback for structural shift")
    _fb_channels = {
        # ($M values) — key metric_types that the area chart maps to channels
        "Free TV":          {2010: 180000, 2012: 175000, 2014: 170000, 2016: 162000, 2018: 155000, 2020: 135000, 2022: 140000, 2024: 138000},
        "Pay TV":           {2010: 45000,  2012: 50000,  2014: 52000,  2016: 50000,  2018: 48000,  2020: 42000,  2022: 40000,  2024: 38000},
        "Search Desktop":   {2010: 30000,  2012: 45000,  2014: 56000,  2016: 68000,  2018: 85000,  2020: 80000,  2022: 100000, 2024: 115000},
        "Search Mobile":    {2010: 2000,   2012: 8000,   2014: 20000,  2016: 42000,  2018: 65000,  2020: 72000,  2022: 95000,  2024: 125000},
        "Social Desktop":   {2010: 5000,   2012: 8000,   2014: 12000,  2016: 16000,  2018: 20000,  2020: 18000,  2022: 22000,  2024: 24000},
        "Social Mobile":    {2010: 500,    2012: 3000,   2014: 10000,  2016: 25000,  2018: 42000,  2020: 50000,  2022: 72000,  2024: 95000},
        "Video Desktop":    {2010: 3000,   2012: 5000,   2014: 8000,   2016: 12000,  2018: 16000,  2020: 18000,  2022: 22000,  2024: 26000},
        "Video Mobile":     {2010: 200,    2012: 1000,   2014: 3000,   2016: 8000,   2018: 14000,  2020: 18000,  2022: 28000,  2024: 38000},
        "Display Desktop":  {2010: 25000,  2012: 28000,  2014: 30000,  2016: 32000,  2018: 34000,  2020: 30000,  2022: 32000,  2024: 34000},
        "Display Mobile":   {2010: 1000,   2012: 4000,   2014: 10000,  2016: 18000,  2018: 25000,  2020: 28000,  2022: 35000,  2024: 42000},
        "Traditional OOH":  {2010: 28000,  2012: 29000,  2014: 30000,  2016: 30000,  2018: 31000,  2020: 22000,  2022: 28000,  2024: 30000},
        "Digital OOH":      {2010: 1000,   2012: 2000,   2014: 3000,   2016: 5000,   2018: 8000,   2020: 6000,   2022: 12000,  2024: 16000},
        "Magazine":         {2010: 42000,  2012: 38000,  2014: 34000,  2016: 28000,  2018: 24000,  2020: 16000,  2022: 14000,  2024: 12000},
        "Newspaper":        {2010: 85000,  2012: 72000,  2014: 62000,  2016: 52000,  2018: 42000,  2020: 28000,  2022: 24000,  2024: 20000},
        "Radio":            {2010: 32000,  2012: 33000,  2014: 34000,  2016: 33000,  2018: 33000,  2020: 26000,  2022: 30000,  2024: 31000},
        "Cinema":           {2010: 2500,   2012: 3000,   2014: 3500,   2016: 4000,   2018: 4500,   2020: 1000,   2022: 3000,   2024: 4000},
        "Other Desktop":    {2010: 10000,  2012: 12000,  2014: 14000,  2016: 15000,  2018: 16000,  2020: 14000,  2022: 16000,  2024: 17000},
        "Other Mobile":     {2010: 500,    2012: 2000,   2014: 5000,   2016: 10000,  2018: 15000,  2020: 18000,  2022: 24000,  2024: 30000},
    }
    _fb_rows = []
    for _mt, _yr_vals in _fb_channels.items():
        for _yr, _val in _yr_vals.items():
            _fb_rows.append({"year": _yr, "metric_type": _mt, "value": float(_val)})
    global_adv_df = pd.DataFrame(_fb_rows)

# All heavy loop processing (structural-shift, ad-revenue, global-adv) is cached
_adv_bundle = _build_ss_ad_json_bundle(excel_path, source_stamp)
_ss_data_json = _adv_bundle["ss_data_json"]
_ad_json_str = _adv_bundle["ad_json_str"]
_global_adv_json_str = _adv_bundle["global_adv_json_str"]
# Keep _ad_by_year as dict — used downstream by concentration chart + revenue ticker
_ad_by_year: dict = {int(k): v for k, v in json.loads(_ad_json_str).items()}

db_path = ROOT_DIR / "earningscall_intelligence.db"


def _build_rank_cards(block: pd.DataFrame, value_col: str, formatter) -> list[dict]:
    if block.empty or value_col not in block.columns:
        return []
    scoped = block[["company", value_col]].dropna(subset=[value_col]).copy()
    if scoped.empty:
        return []
    scoped = scoped.sort_values(value_col, ascending=False).head(6)
    cards: list[dict] = []
    for rank, (_, row) in enumerate(scoped.iterrows(), start=1):
        company_name = str(row["company"])
        cards.append(
            {
                "rank": rank,
                "company": company_name,
                "value": formatter(float(row[value_col])),
                "color": _company_color(company_name),
                "logo": _resolve_logo(company_name, logos),
                "raw": float(row[value_col]),
                "yoy_pct": None,
            }
        )
    return cards

# Styling
st.markdown(
    """
<style>
.stApp > div, .main, .main > div,
section[data-testid="stMain"],
section[data-testid="stMain"] > div,
div[data-testid="stAppViewContainer"],
div[data-testid="stMainBlockContainer"],
div[data-testid="appViewBlockContainer"],
div[data-testid="block-container"] {
    background-color: #020810 !important;
    background: #020810 !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    max-width: 100% !important;
}
.element-container, .stMarkdown, .stPlotlyChart,
.stCaption, div[data-testid="stVerticalBlock"] {
    background: transparent !important;
}
.stApp p, .stApp span, .stApp div,
.stApp label, .stApp h1, .stApp h2, .stApp h3 {
    color: rgba(255,255,255,0.8);
}
.stCaption > p {
    color: rgba(255,255,255,0.38) !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.02em;
}
.stButton > button {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    color: white !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: background 0.2s ease !important;
}
.stButton > button,
.stButton > button *,
.stButton > button p,
.stButton > button span,
.stButton > button div {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    opacity: 1 !important;
}
.stButton > button:hover {
    background: rgba(255,255,255,0.14) !important;
}
@keyframes ae-pulse {
    0%   { box-shadow: 0 0 0 0 rgba(255,255,255,0.3); }
    70%  { box-shadow: 0 0 0 12px rgba(255,255,255,0); }
    100% { box-shadow: 0 0 0 0 rgba(255,255,255,0); }
}
.ae-cta-wrap a:hover {
    background: rgba(255,255,255,0.14) !important;
    border-color: rgba(255,255,255,0.8) !important;
    transform: translateY(-1px);
}
.stPlotlyChart,
.stPlotlyChart > div,
.stPlotlyChart iframe,
div[data-testid="stPlotlyChart"],
div[data-testid="stPlotlyChart"] > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
.js-plotly-plot .plotly,
.js-plotly-plot .plotly .svg-container {
    background: transparent !important;
}
[data-testid="stComponentsIframeWrapper"],
[data-testid="stIframe"] {
    background: transparent !important;
}
.element-container {
    background: transparent !important;
}
.wm-wrap {
    max-width: 1500px;
    margin: 0 auto;
    padding: 0 14px 36px;
}
.wm-pulse-strip,
.wm-stock-strip {
    width: 100%;
    overflow: hidden;
    border-radius: 12px;
    border: 1px solid rgba(74,174,255,0.18);
    background: #020810;
    padding: 10px 0;
}
.wm-stock-strip {
    padding: 7px 0;
}
.wm-pulse-track,
.wm-stock-track {
    display: flex;
    align-items: stretch;
    gap: 12px;
    width: max-content;
    animation: wmPulseScroll 42s linear infinite;
}
.wm-stock-track {
    animation-duration: 36s;
}
.wm-pulse-item {
    width: min(420px, 82vw);
    flex: 0 0 auto;
    border-radius: 10px;
    border: 1px solid rgba(148,163,184,0.22);
    background: rgba(15,23,42,0.72);
    padding: 10px 12px;
    color: #e2e8f0 !important;
    -webkit-text-fill-color: #e2e8f0 !important;
}
.wm-pulse-item * {
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
}
.wm-stock-item {
    width: min(300px, 78vw);
    flex: 0 0 auto;
    border-radius: 10px;
    border: 1px solid rgba(148,163,184,0.22);
    background: rgba(15,23,42,0.72);
    padding: 7px 10px;
    color: #e2e8f0 !important;
    -webkit-text-fill-color: #e2e8f0 !important;
}
.wm-stock-item * {
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
}
.wm-mini-logo {
    width: 42px;
    height: 42px;
    object-fit: contain;
    border-radius: 50%;
    background: rgba(148, 163, 184, 0.12);
    border: 1px solid rgba(148, 163, 184, 0.26);
    padding: 4px;
}
@keyframes wmPulseScroll {
    from { transform: translateX(0); }
    to { transform: translateX(-50%); }
}
@media (max-width: 768px) {
    .wm-wrap { padding: 0 6px 24px; }
}
/* KPI % change arrows — force color against any theme */
.kpi-yoy-pos, .kpi-yoy-pos * {
    color: #22c55e !important;
    -webkit-text-fill-color: #22c55e !important;
    font-size: 0.88rem !important;
    font-weight: 700 !important;
    opacity: 1 !important;
}
.kpi-yoy-neg, .kpi-yoy-neg * {
    color: #ef4444 !important;
    -webkit-text-fill-color: #ef4444 !important;
    font-size: 0.88rem !important;
    font-weight: 700 !important;
    opacity: 1 !important;
}
/* Hero narrative text */
.wm-hero-narrative, .wm-hero-narrative * {
    color: rgba(255,255,255,0.88) !important;
    -webkit-text-fill-color: rgba(255,255,255,0.88) !important;
    opacity: 1 !important;
}
.wm-hero-narrative strong {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-weight: 700 !important;
}
/* Human Voice and stock ticker text */
.wm-pulse-item, .wm-pulse-item * {
    color: #e2e8f0 !important;
    -webkit-text-fill-color: #e2e8f0 !important;
    opacity: 1 !important;
}
.wm-stock-item, .wm-stock-item * {
    color: #e2e8f0 !important;
    -webkit-text-fill-color: #e2e8f0 !important;
    opacity: 1 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# Render
st.markdown("<div class='wm-wrap'>", unsafe_allow_html=True)

selected_year = st.session_state.get("selected_year", None)
if selected_year is None:
    try:
        selected_year = int(metrics_df["year"].max())
    except Exception:
        selected_year = 2024

valid_years = sorted([int(y) for y in available_years]) if available_years else [2024]
if int(selected_year) not in valid_years:
    selected_year = int(valid_years[-1])

# Year selector — top right, lets users rewind to any available year
_yr_col_spacer, _yr_col_select = st.columns([5, 1])
with _yr_col_select:
    selected_year = st.selectbox(
        "Year",
        options=list(reversed(valid_years)),
        index=0,
        key="home_year_select",
        label_visibility="collapsed",
    )

effective_year = int(selected_year)
selected_quarter = _select_latest_quarter_for_year(macro_df, effective_year)

st.markdown("""
<style>
.wm-progress-nav {
    position: fixed;
    right: 20px;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    flex-direction: column;
    gap: 8px;
    z-index: 9999;
}
.wm-progress-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: rgba(255,255,255,0.2);
    transition: all 0.3s ease;
    cursor: pointer;
}
.wm-progress-dot.active {
    background: #4aaeff;
    height: 24px;
    border-radius: 3px;
    width: 6px;
}
.section-label {
    letter-spacing: 0.1em;
    transition: letter-spacing 0.8s ease, opacity 0.6s ease;
}
.sv.sv-visible .section-label {
    letter-spacing: 0.28em;
}
.sv {
  opacity: 0;
  transform: translateY(28px) scale(0.97);
  transition: opacity 0.7s ease, transform 0.75s cubic-bezier(0.16,1,0.3,1);
  will-change: transform, opacity;
}
.sv.sv-visible {
  opacity: 1;
  transform: translateY(0) scale(1);
}
.sv.sv-past {
  opacity: 0.12;
  transform: translateY(-6%) scale(0.90);
  transition: opacity 0.45s ease, transform 0.5s ease;
  pointer-events: none;
}
</style>
<div class="wm-progress-nav" id="wm-progress-nav">
  <div class="wm-progress-dot" data-section="0"></div>
  <div class="wm-progress-dot" data-section="1"></div>
  <div class="wm-progress-dot" data-section="2"></div>
  <div class="wm-progress-dot" data-section="3"></div>
  <div class="wm-progress-dot" data-section="4"></div>
  <div class="wm-progress-dot" data-section="5"></div>
  <div class="wm-progress-dot" data-section="6"></div>
  <div class="wm-progress-dot" data-section="7"></div>
</div>
""", unsafe_allow_html=True)

st.components.v1.html(
    """
<script>
(function() {
  const doc = window.parent.document;

  function init() {
    const dots = doc.querySelectorAll('.wm-progress-dot');
    const observed = new WeakSet();

    const _revealObs = new window.parent.IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('sv-visible');
          e.target.classList.remove('sv-past');
        } else {
          const rect = e.target.getBoundingClientRect();
          if (rect.bottom < 0) {
            e.target.classList.add('sv-past');
            e.target.classList.remove('sv-visible');
          }
        }
      });

      if (dots.length > 0) {
        const scrollY = window.parent.scrollY;
        const pageH = doc.documentElement.scrollHeight;
        const viewH = window.parent.innerHeight;
        const progress = scrollY / Math.max(1, pageH - viewH);
        const activeIdx = Math.round(progress * (dots.length - 1));
        dots.forEach((d, i) => {
          d.classList.toggle('active', i === activeIdx);
        });
      }
    }, { threshold: 0.06, rootMargin: "0px 0px -40px 0px" });

    // Observe all .sv elements, including ones added later by Streamlit
    function observeAll() {
      doc.querySelectorAll('.sv').forEach(el => {
        if (!observed.has(el)) {
          observed.add(el);
          _revealObs.observe(el);
        }
      });
    }
    observeAll();

    // Watch for new .sv elements as Streamlit streams the page
    try {
      const bodyObs = new MutationObserver(() => observeAll());
      bodyObs.observe(doc.body || doc.documentElement, { childList: true, subtree: true });
    } catch(e) {}

    // Fallback poll for environments where MutationObserver can't reach parent
    let _pollCount = 0;
    const _poll = setInterval(() => {
      observeAll();
      _pollCount++;
      if (_pollCount > 60) clearInterval(_poll);
    }, 500);

    // Also update dots on scroll for smooth tracking
    window.parent.addEventListener('scroll', function() {
      if (!dots.length) return;
      const scrollY = window.parent.scrollY;
      const pageH = doc.documentElement.scrollHeight;
      const viewH = window.parent.innerHeight;
      const progress = scrollY / Math.max(1, pageH - viewH);
      const activeIdx = Math.round(progress * (dots.length - 1));
      dots.forEach((d, i) => d.classList.toggle('active', i === activeIdx));
    }, { passive: true });
  }

  if (doc.readyState === 'loading') {
    doc.addEventListener('DOMContentLoaded', init);
  } else {
    // Delay slightly to let Streamlit finish initial DOM setup
    setTimeout(init, 300);
  }

  function _startTicker() {
    const els = doc.querySelectorAll('[data-rps]');
    if (!els.length) { setTimeout(_startTicker, 300); return; }
    const t0 = Date.now();
    setInterval(() => {
      const elapsed = (Date.now() - t0) / 1000;
      doc.querySelectorAll('[data-rps]').forEach(el => {
        const rps = parseFloat(el.getAttribute('data-rps'));
        el.textContent = '$' + (rps * elapsed).toLocaleString('en-US',
          {minimumFractionDigits:0, maximumFractionDigits:0});
      });
    }, 120);
  }
  _startTicker();
})();
</script>
<style>
html,body{margin:0;padding:0;background:#020810;border:none;outline:none;}
.sv {
  opacity: 0;
  transform: translateY(28px) scale(0.97);
  transition: opacity 0.7s ease, transform 0.75s cubic-bezier(0.16,1,0.3,1);
  will-change: transform, opacity;
}
.sv.sv-visible {
  opacity: 1;
  transform: translateY(0) scale(1);
}
.sv.sv-past {
  opacity: 0.12;
  transform: translateY(-6%) scale(0.90);
  transition: opacity 0.45s ease, transform 0.5s ease;
  pointer-events: none;
}
.human-voice-fix {
  margin-top: -1rem;
}
</style>
""",
    height=0,
)


def _section(label: str, headline: str, body: str = "", section_class: str = ""):
    class_attr = "sv ae-section"
    if section_class:
        class_attr = f"{class_attr} {section_class}"
    _, col_mid, _ = st.columns([1, 2.5, 1])
    with col_mid:
        st.markdown(
            f"""
        <div class="{class_attr}" data-ae-section="1" style="padding:56px 0 20px;background:transparent;">
          <div class="section-label">{escape(str(label))}</div>
          <div class="section-title" style="border-left:3px solid rgba(74,174,255,0.4);padding-left:16px;">{escape(str(headline))}</div>
          <div class="section-desc">{body}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )


def _separator():
    st.markdown(
        "<div style='height:120px;'></div>",
        unsafe_allow_html=True,
    )


def _deep_dive(nav: str, label: str):
    """Render a CTA button with pulse animation."""
    _SLUG_MAP = {
        "overview": "Overview",
        "earnings": "Earnings",
        "stocks": "Stocks",
        "editorial": "Editorial",
        "genie": "Genie",
    }
    slug = _SLUG_MAP.get(nav)
    if not slug:
        return
    st.markdown(
        f"""<div class="ae-cta-wrap" style="padding:10px 0;">
        <a href="{slug}" target="_self" rel="noopener"
           style="color:#ffffff;font-size:0.95rem;text-decoration:none;
                  border:1px solid rgba(255,255,255,0.55);border-radius:999px;
                  padding:12px 28px;display:inline-flex;align-items:center;
                  background:rgba(255,255,255,0.07);font-weight:500;
                  transition:all .2s ease;cursor:pointer;
                  animation:ae-pulse 2.5s ease-in-out infinite;">
          {escape(label)} →
        </a></div>""",
        unsafe_allow_html=True,
    )


def _find_col(df: pd.DataFrame, includes: list[str], excludes: Optional[list[str]] = None) -> str:
    if df is None or df.empty:
        return ""
    excludes = excludes or []
    for col in df.columns:
        norm = re.sub(r"[^a-z0-9]+", "", str(col).lower())
        if all(re.sub(r"[^a-z0-9]+", "", x.lower()) in norm for x in includes):
            if any(re.sub(r"[^a-z0-9]+", "", x.lower()) in norm for x in excludes):
                continue
            return str(col)
    return ""


def _yr(df, year, year_col="year"):
    if df is None or df.empty or year_col not in df.columns:
        return pd.DataFrame()
    series = pd.to_numeric(df[year_col], errors="coerce")
    row = df[series == int(year)]
    if row.empty:
        valid = series.dropna()
        if valid.empty:
            return pd.DataFrame()
        row = df[series == int(valid.max())]
    return row


def _yoy(current, previous):
    if previous and previous > 0:
        return (current - previous) / previous * 100
    return None


def _yoy_vec(current_series, prev_series):
    return ((pd.to_numeric(current_series, errors="coerce") - pd.to_numeric(prev_series, errors="coerce")) / pd.to_numeric(prev_series, errors="coerce") * 100).where(pd.to_numeric(prev_series, errors="coerce") > 0, np.nan)


def _apply_dark_chart_layout(fig, *, height=360, margin=None, extra_layout=None):
    base_layout = dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="#ffffff"),
        xaxis=dict(
            color="#aaaaaa",
            gridcolor="#2a2a2a",
            linecolor="#333333",
            tickfont=dict(color="#aaaaaa", size=13),
        ),
        yaxis=dict(
            color="#aaaaaa",
            gridcolor="#2a2a2a",
            linecolor="#333333",
            tickfont=dict(color="#aaaaaa", size=13),
        ),
        legend=dict(font=dict(color="#ffffff", size=13), bgcolor="rgba(0,0,0,0)"),
        margin=margin or dict(l=0, r=0, t=32, b=40),
        height=height,
    )
    if extra_layout:
        base_layout.update(extra_layout)
    fig.update_layout(**base_layout)


def _normalize_market_feed(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    date_col = _find_col(df, ["date"]) or _find_col(df, ["time"])
    price_col = _find_col(df, ["price"]) or _find_col(df, ["close"])
    tag_col = _find_col(df, ["tag"]) or _find_col(df, ["ticker"]) or _find_col(df, ["symbol"])
    asset_col = _find_col(df, ["asset"]) or _find_col(df, ["company"]) or _find_col(df, ["name"])
    change_col = _find_col(df, ["change"]) or _find_col(df, ["chg"])
    if not date_col or not price_col:
        return pd.DataFrame()
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce"),
            "price": pd.to_numeric(df[price_col], errors="coerce"),
            "tag": df[tag_col].astype(str).str.strip().str.upper() if tag_col else "",
            "asset": df[asset_col].astype(str).str.strip() if asset_col else "",
            "change": pd.to_numeric(df[change_col].astype(str).str.replace("%", "", regex=False), errors="coerce") if change_col else np.nan,
        }
    )
    out = out.dropna(subset=["date", "price"]).copy()
    return out.sort_values("date")


@st.cache_data(ttl=300, show_spinner=False)
def _load_market_feed(_excel_path: str, _live_excel_path: str, _source_stamp: int, _live_source_stamp: int) -> pd.DataFrame:
    """Load & merge all market-feed sheets (Stocks, Daily, Minute) — cached."""
    if not _excel_path and not _live_excel_path:
        return pd.DataFrame()
    _src = _live_excel_path or _excel_path
    _stamp = _live_source_stamp if _live_excel_path else _source_stamp
    # Always merge all three sheets: Stocks & Crypto gives long historical data,
    # Daily gives recent daily closes, Minute gives intraday prices.
    _sheet_priority = [("Stocks & Crypto", 1), ("Daily", 2), ("Minute", 3)]
    frames = []
    for sheet_name, prio in _sheet_priority:
        raw = _read_excel_sheet_cached(_src, sheet_name, _stamp)
        norm = _normalize_market_feed(raw)
        if not norm.empty:
            norm = norm.copy()
            norm["_prio"] = prio
            frames.append(norm)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    # Sort by date then priority so higher-priority source wins dedup (keep="last").
    combined = combined.sort_values(["date", "_prio"])
    combined = combined.drop_duplicates(subset=["date", "tag", "asset"], keep="last")
    return combined.drop(columns=["_prio"]).sort_values("date").reset_index(drop=True)


def _render_transcript_pulse_strip(current_year: int, current_quarter: str) -> None:
    pulse_df, pulse_source = _load_transcript_pulse_quotes(
        repo_root_path=str(ROOT_DIR),
        db_path=str(db_path),
        selected_year=int(current_year),
        selected_quarter=current_quarter,
        limit=5,
        data_path=data_path,
    )
    if pulse_df.empty:
        st.info("No transcript data available yet — run the intelligence pipeline first.")
        return
    pulse_items: list[str] = []
    for row in pulse_df.itertuples(index=False):
        company = _normalize_company_name(getattr(row, "company", ""))
        speaker = _resolve_speaker_label(
            speaker=getattr(row, "speaker", ""),
            name=getattr(row, "name", ""),
            executive=getattr(row, "executive", ""),
            who=getattr(row, "who", ""),
            rolebucket=getattr(row, "rolebucket", "") or getattr(row, "role_bucket", ""),
            role=getattr(row, "role", ""),
        )
        role_bucket = str(getattr(row, "rolebucket", "") or getattr(row, "role_bucket", "") or "").strip()
        role_label = str(getattr(row, "role", "") or "").strip()
        title = role_label or role_bucket or ""
        quarter = str(getattr(row, "quarter", "") or "").strip()
        year = str(getattr(row, "year", "") or "").strip()
        period_tag = f"{quarter} {year}".strip() if quarter or year else ""
        quote = str(getattr(row, "quote", "") or "").strip()
        if not quote:
            continue
        logo_b64 = _resolve_logo(company, logos)
        logo_html = (
            f"<img class='logo' src='data:image/png;base64,{logo_b64}' alt='{escape(company)} logo' />"
            if logo_b64
            else "<span class='logo' style='display:inline-flex;align-items:center;justify-content:center;'>&#8226;</span>"
        )
        title_html = f"<span style='opacity:0.5;font-size:0.68rem;'>{escape(title)}</span>" if title else ""
        period_html = f"<span style='opacity:0.4;font-size:0.65rem;margin-left:auto;'>{escape(period_tag)}</span>" if period_tag else ""
        pulse_items.append(
            "<div class='item'>"
            f"<div class='item-quote'>&ldquo;{escape(quote)}&rdquo;</div>"
            f"<div class='item-meta'>"
            f"{logo_html}<div style='display:flex;flex-direction:column;gap:1px;'>"
            f"<span style='font-weight:700;'>{escape(company)}</span>"
            f"<div style='display:flex;align-items:center;gap:6px;'>"
            f"<span style='opacity:0.72;font-size:0.72rem;'>&#8212; {escape(speaker)}</span>"
            f"{title_html}</div></div>"
            f"{period_html}</div>"
            "</div>"
        )
    if not pulse_items:
        st.info("No transcript data available yet — run the intelligence pipeline first.")
        return
    _pulse_track = "".join(pulse_items + pulse_items)
    st.components.v1.html(
        "<style>@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');"
        "html,body{margin:0;padding:0;background:#020810;}*{box-sizing:border-box;}"
        ".strip{width:100%;overflow:hidden;border-radius:12px;border:1px solid rgba(74,174,255,0.18);background:#020810;padding:12px 0;}"
        ".track{display:flex;align-items:flex-start;gap:12px;width:max-content;animation:scroll 200s linear infinite;}"
        ".track:hover{animation-play-state:paused;}"
        ".item{width:380px;height:190px;flex:0 0 auto;border-radius:10px;border:1px solid rgba(148,163,184,0.22);background:rgba(15,23,42,0.72);padding:12px 14px;display:flex;flex-direction:column;justify-content:space-between;overflow:hidden;transition:border-color 0.2s, box-shadow 0.2s;}"
        ".item:hover{border-color:rgba(74,174,255,0.5);box-shadow:0 0 12px rgba(74,174,255,0.15);}"
        ".item-quote{font-style:italic;font-size:0.83rem;line-height:1.5;overflow:hidden;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;}"
        ".item-meta{margin-top:8px;display:flex;align-items:center;gap:8px;font-size:0.74rem;flex-shrink:0;}"
        ".logo{width:32px;height:32px;object-fit:contain;border-radius:50%;background:rgba(148,163,184,0.12);border:1px solid rgba(148,163,184,0.26);padding:3px;flex-shrink:0;}"
        "@keyframes scroll{from{transform:translateX(0);}to{transform:translateX(-50%);}}"
        "</style>"
        f"<div class='strip' style='color:#e2e8f0;font-family:DM Sans,sans-serif;'><div class='track'>{_pulse_track}</div></div>",
        height=230,
    )
    if pulse_source:
        st.caption(f"Source: {pulse_source}")


def _render_stock_price_strip(feed_df: pd.DataFrame) -> None:
    company_ticker_fallback = {
        "Alphabet": ["GOOGL", "GOOG"],
        "Meta Platforms": ["META"],
        "Amazon": ["AMZN"],
        "Apple": ["AAPL"],
        "Microsoft": ["MSFT"],
        "Netflix": ["NFLX"],
        "Disney": ["DIS"],
        "Comcast": ["CMCSA"],
        "Spotify": ["SPOT"],
        "Roku": ["ROKU"],
        "Warner Bros. Discovery": ["WBD"],
        "Paramount Global": ["PARA"],
    }
    if feed_df is None or feed_df.empty:
        st.info("Market ticker unavailable.")
        return

    items = []
    feed = feed_df.copy()
    feed["asset_norm"] = feed["asset"].astype(str).str.lower()
    feed["tag_norm"] = feed["tag"].astype(str).str.upper()
    for company, ticker_aliases in company_ticker_fallback.items():
        company_variants = _company_variants(company)
        pattern = "|".join(re.escape(v.lower()) for v in company_variants if v)
        subset = pd.DataFrame()
        if pattern:
            subset = feed[feed["asset_norm"].str.contains(pattern, na=False, regex=True)]
        if subset.empty:
            subset = feed[feed["tag_norm"].isin(ticker_aliases)]
        if subset.empty:
            # Some sheets store the ticker directly in the asset column.
            subset = feed[feed["asset_norm"].isin([t.lower() for t in ticker_aliases])]
        if subset.empty:
            continue

        subset_sorted = subset.sort_values("date")
        last = subset_sorted.iloc[-1]
        price = float(last.get("price", np.nan))
        if pd.isna(price):
            continue
        # Prefer explicit change column; fall back to calculating 24hr change
        # from the two most recent distinct-day closes (Daily sheet data).
        change = pd.to_numeric(pd.Series([last.get("change", np.nan)]), errors="coerce").iloc[0]
        if pd.isna(change) and len(subset_sorted) >= 2:
            # Get the two most recent rows with different dates for 24hr delta
            _dates = subset_sorted["date"].dt.date
            _unique_dates = _dates.drop_duplicates().tail(2)
            if len(_unique_dates) >= 2:
                _prev_date = _unique_dates.iloc[-2]
                _prev_rows = subset_sorted[_dates == _prev_date]
                if not _prev_rows.empty:
                    _prev_price = float(_prev_rows.iloc[-1]["price"])
                    if _prev_price > 0:
                        change = ((price - _prev_price) / _prev_price) * 100.0
        if pd.notna(change):
            arrow = "&#9650;" if change >= 0 else "&#9660;"
            chg_color = "#22c55e" if change >= 0 else "#ef4444"
            change_html = f"<span style='color:{chg_color};font-weight:700;'>{arrow} {abs(change):.2f}%</span>"
        else:
            change_html = "<span style='opacity:0.4;'>&#8212;</span>"
        ticker_display = ticker_aliases[0]
        logo_b64 = _resolve_logo(company, logos)
        logo_html = (
            f"<img class='logo' src='data:image/png;base64,{logo_b64}' alt='{escape(company)} logo' />"
            if logo_b64
            else "<span class='logo' style='display:inline-flex;align-items:center;justify-content:center;'>&#8226;</span>"
        )
        items.append(
            "<div class='item'>"
            f"<div style='display:flex;align-items:center;gap:8px;width:100%;'>{logo_html}"
            f"<span style='font-weight:700;font-size:0.8rem;'>{escape(ticker_display)}</span>"
            f"<span style='margin-left:auto;font-family:monospace;font-size:0.92rem;font-weight:700;'>${price:,.2f}</span></div>"
            f"<div style='font-size:0.75rem;margin-top:2px;'>{change_html}</div>"
            "</div>"
        )
    if not items:
        st.info("Market ticker unavailable.")
        return
    _stock_track = "".join(items + items)
    st.components.v1.html(
        "<style>@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');"
        "html,body{margin:0;padding:0;background:#020810;}*{box-sizing:border-box;}"
        ".strip{width:100%;overflow:hidden;border-radius:12px;border:1px solid rgba(74,174,255,0.15);background:#020810;padding:7px 0;}"
        ".track{display:flex;align-items:stretch;gap:12px;width:max-content;animation:scroll 120s linear infinite;}"
        ".track:hover{animation-play-state:paused;}"
        ".item{width:220px;flex:0 0 auto;border-radius:10px;border:1px solid rgba(148,163,184,0.22);background:rgba(15,23,42,0.72);padding:7px 10px;}"
        ".logo{width:32px;height:32px;object-fit:contain;border-radius:50%;background:rgba(148,163,184,0.12);border:1px solid rgba(148,163,184,0.26);padding:3px;flex-shrink:0;}"
        "@keyframes scroll{from{transform:translateX(0);}to{transform:translateX(-50%);}}"
        "</style>"
        f"<div class='strip' style='color:#e6edf3;font-family:DM Sans,sans-serif;'><div class='track'>{_stock_track}</div></div>",
        height=110,
    )


def _render_polymarket_strip(logos_dict: dict) -> None:
    """
    Scrolling strip of active Polymarket bets mentioning tracked companies.
    Design mirrors the stock ticker strip — same dark glass card aesthetic.
    """
    try:
        raw_markets = fetch_polymarket_top(1000)
    except Exception:
        raw_markets = []

    bets = get_all_company_bets_labelled(raw_markets)
    if not bets:
        st.caption("⏳ Polymarket data unavailable — API may be blocked by your network.")
        return

    def _yes_color(p: float | None) -> str:
        if p is None:
            return "#6b7280"
        if p >= 65:
            return "#22c55e"
        if p >= 45:
            return "#f59e0b"
        return "#ef4444"

    def _logo_html(company: str) -> str:
        key = COMPANY_LOGO_KEY.get(company, company)
        b64 = _resolve_logo(key, logos_dict)
        if b64:
            return (
                f"<img class='pm-logo' src='data:image/png;base64,{b64}' "
                f"alt='{escape(company)}' />"
            )
        # Fallback: initial letter badge
        letter = (company or "?")[0].upper()
        return (
            f"<span class='pm-logo' style='display:inline-flex;align-items:center;"
            f"justify-content:center;font-weight:800;font-size:0.85rem;color:#4aaeff;'>"
            f"{letter}</span>"
        )

    items = []
    for bet in bets[:60]:  # cap at 60 cards for scroll performance
        q = str(bet.get("question", "")).strip()
        yes_p = bet.get("yes_price")
        vol_fmt = str(bet.get("volume_fmt", ""))
        end_date = str(bet.get("end_date", ""))
        company = str(bet.get("matched_company", ""))
        url = str(bet.get("url", "https://polymarket.com"))

        # Truncate question at 90 chars
        q_display = (q[:87] + "…") if len(q) > 90 else q

        yes_label = f"{yes_p:.0f}% YES" if yes_p is not None else "—"
        yes_col = _yes_color(yes_p)
        logo = _logo_html(company)

        meta_parts = []
        if vol_fmt:
            meta_parts.append(
                f"<span style='color:#94a3b8;font-size:0.7rem;'>{escape(vol_fmt)} vol</span>"
            )
        if end_date:
            meta_parts.append(
                f"<span style='color:#64748b;font-size:0.7rem;'>ends {escape(end_date)}</span>"
            )
        meta_html = "<span style='margin:0 4px;color:#334155;'>·</span>".join(meta_parts)

        items.append(
            f"<a class='pm-item' href='{url}' target='_blank' rel='noopener'>"
            f"<div class='pm-header'>"
            f"{logo}"
            f"<span class='pm-company'>{escape(company)}</span>"
            f"<span class='pm-yes' style='background:{yes_col}22;color:{yes_col};"
            f"border:1px solid {yes_col}44;'>{yes_label}</span>"
            f"</div>"
            f"<div class='pm-question'>{escape(q_display)}</div>"
            f"<div class='pm-meta'>{meta_html}</div>"
            f"</a>"
        )

    if not items:
        return

    track_html = "".join(items + items)  # duplicate for seamless loop

    st.components.v1.html(
        "<style>"
        "@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');"
        "html,body{margin:0;padding:0;background:#020810;}*{box-sizing:border-box;}"
        ".strip{width:100%;overflow:hidden;border-radius:12px;"
        "border:1px solid rgba(124,58,237,0.22);background:#020810;padding:10px 0;}"
        ".track{display:flex;align-items:flex-start;gap:10px;width:max-content;"
        "animation:scroll 120s linear infinite;}"
        ".track:hover{animation-play-state:paused;}"
        ".pm-item{width:300px;flex:0 0 auto;border-radius:10px;"
        "border:1px solid rgba(124,58,237,0.2);background:rgba(15,10,30,0.72);"
        "padding:10px 12px;display:flex;flex-direction:column;gap:6px;"
        "text-decoration:none;transition:border-color 0.2s;}"
        ".pm-item:hover{border-color:rgba(124,58,237,0.5);}"
        ".pm-header{display:flex;align-items:center;gap:7px;}"
        ".pm-logo{width:26px;height:26px;object-fit:contain;border-radius:50%;"
        "background:rgba(148,163,184,0.1);border:1px solid rgba(148,163,184,0.2);"
        "padding:2px;flex-shrink:0;}"
        ".pm-company{font-size:0.72rem;font-weight:700;color:#a78bfa;"
        "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:110px;}"
        ".pm-yes{margin-left:auto;font-size:0.68rem;font-weight:700;"
        "padding:2px 7px;border-radius:999px;white-space:nowrap;}"
        ".pm-question{font-size:0.76rem;line-height:1.45;color:#e2e8f0;"
        "overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;"
        "-webkit-box-orient:vertical;flex:1;}"
        ".pm-meta{display:flex;align-items:center;gap:4px;flex-wrap:wrap;}"
        "@keyframes scroll{from{transform:translateX(0);}to{transform:translateX(-50%);}}"
        "</style>"
        f"<div class='strip' style='font-family:DM Sans,sans-serif;'>"
        f"<div class='track'>{track_html}</div></div>",
        height=168,
    )


metrics = metrics_df.copy() if isinstance(metrics_df, pd.DataFrame) else pd.DataFrame()
if not metrics.empty:
    metrics.columns = [str(c).strip() for c in metrics.columns]
    if "year" in metrics.columns:
        metrics["year"] = pd.to_numeric(metrics["year"], errors="coerce")
    metrics = metrics.dropna(subset=["year", "company"]).copy()
    metrics["year"] = metrics["year"].astype(int)
for col in ["revenue", "operating_income", "market_cap", "rd", "net_income"]:
    if col in metrics.columns:
        metrics[col] = pd.to_numeric(metrics[col], errors="coerce")

mcap_col = next((c for c in metrics.columns if "market" in c.lower() and "cap" in c.lower()), "market_cap")
if mcap_col not in metrics.columns and "market_cap" in metrics.columns:
    mcap_col = "market_cap"

# Derive global ad spend totals from Global_Adv_Aggregates (loaded earlier)
global_adv_b = None
global_adv_yoy = None
effective_year_global_adv = effective_year

if not _global_adv_totals.empty:
    _lookup_yr = effective_year if effective_year in _global_adv_totals.index else int(_global_adv_totals.index.max())
    effective_year_global_adv = _lookup_yr
    global_adv_b = float(_global_adv_totals[_lookup_yr])
    _prev_yr = _lookup_yr - 1
    if _prev_yr in _global_adv_totals.index:
        _prev_val = float(_global_adv_totals[_prev_yr])
        if _prev_val > 0:
            global_adv_yoy = _yoy(global_adv_b, _prev_val)

# Keep legacy aliases so remaining code below continues to work
groupm_b = global_adv_b
groupm_yoy = global_adv_yoy
effective_year_groupm = effective_year_global_adv

rev_b = None
rev_yoy = None
mcap_b = None
mcap_yoy = None
if not metrics.empty and "revenue" in metrics.columns and mcap_col in metrics.columns:
    yr = metrics[metrics["year"] == effective_year].copy()
    py = metrics[metrics["year"] == (effective_year - 1)].copy()
    if not yr.empty:
        rev_m = float(pd.to_numeric(yr["revenue"], errors="coerce").sum())
        mcap_m = float(pd.to_numeric(yr[mcap_col], errors="coerce").sum())
        rev_b = rev_m / 1e3 if rev_m else None
        mcap_b = mcap_m / 1e3 if mcap_m else None
        if not py.empty:
            prev_rev_m = float(pd.to_numeric(py["revenue"], errors="coerce").sum())
            prev_mcap_m = float(pd.to_numeric(py[mcap_col], errors="coerce").sum())
            rev_yoy = _yoy(rev_m, prev_rev_m)
            mcap_yoy = _yoy(mcap_m, prev_mcap_m)

ad_df = _load_company_ad_revenue_sheet(excel_path, source_stamp) if excel_path else pd.DataFrame()
if not ad_df.empty:
    ad_df = ad_df.copy()
    ad_df.columns = [str(c).strip() for c in ad_df.columns]
    if "Year" in ad_df.columns:
        ad_df["Year"] = pd.to_numeric(ad_df["Year"], errors="coerce").astype("Int64")
ad_lookup = _load_ad_revenue_by_company(excel_path, source_stamp, effective_year) if excel_path else {}
total_tracked_musd = float(sum(float(v.get("ad_revenue_musd", 0.0)) for v in ad_lookup.values()))
total_tracked_b = total_tracked_musd / 1e3 if total_tracked_musd else 0.0
big_tech_names = ["Alphabet", "Meta Platforms", "Amazon", "Apple", "Microsoft"]
big_tech_b = sum(float(ad_lookup.get(c, {}).get("ad_revenue_musd", 0.0)) for c in big_tech_names) / 1e3
other_b = max(total_tracked_b - big_tech_b, 0.0)
global_ad_denom_raw = groupm_b if groupm_b else total_tracked_b
global_ad_denom = global_ad_denom_raw
# Safety guard for mixed units ($M vs $B): keep denominator in billions.
if global_ad_denom and global_ad_denom > 5_000 and total_tracked_b < 5_000:
    global_ad_denom = global_ad_denom / 1_000.0
untracked_b = max((global_ad_denom or 0) - total_tracked_b, 0.0)
market_feed_df = _load_market_feed(excel_path, live_excel_path, source_stamp, live_source_stamp)

# Hero + KPIs + Narrative block
# Build hero logo strip — uses white-variant logos (Amazon/Apple)
_HERO_COMPANIES = [
    "Alphabet", "Amazon", "Apple", "Meta Platforms", "Microsoft",
    "Netflix", "Disney", "Comcast", "Spotify", "Roku",
    "Warner Bros. Discovery", "Paramount Global", "Samsung", "Tencent",
]
_hero_logo_count = len(_HERO_COMPANIES)

narrative_parts = []
if groupm_b:
    narrative_parts.append(
        f"In {effective_year_groupm}, the world spent <strong style='color:white;'>${groupm_b:.0f}B</strong> on advertising."
    )
if rev_yoy is not None:
    if rev_yoy >= 10:
        narrative_parts.append(
            f"The {_hero_logo_count} companies we track grew revenues <strong style='color:#22c55e;'>+{rev_yoy:.1f}%</strong> — a year of strong expansion."
        )
    elif rev_yoy >= 0:
        narrative_parts.append(
            f"The {_hero_logo_count} companies we track grew revenues modestly at <strong style='color:#22c55e;'>+{rev_yoy:.1f}%</strong>."
        )
    else:
        narrative_parts.append(
            f"The {_hero_logo_count} companies we track saw revenues contract <strong style='color:#ef4444;'>{rev_yoy:.1f}%</strong> — a difficult macro year."
        )
if mcap_yoy is not None:
    if mcap_yoy >= 15:
        narrative_parts.append(
            f"Markets rewarded them: combined market cap surged <strong style='color:#22c55e;'>+{mcap_yoy:.1f}%</strong>."
        )
    elif mcap_yoy >= 0:
        narrative_parts.append(
            f"Markets moved cautiously: combined market cap rose <strong style='color:#22c55e;'>+{mcap_yoy:.1f}%</strong>."
        )
    else:
        narrative_parts.append(
            f"Markets were skeptical: combined market cap fell <strong style='color:#ef4444;'>{mcap_yoy:.1f}%</strong>."
        )

narrative_html = " ".join(narrative_parts) if narrative_parts else "Narrative unavailable for the selected year."
kpi1_val = f"${groupm_b:.0f}B" if groupm_b else "&#8212;"
kpi1_yoy = ""
if groupm_yoy is not None:
    _c = "#22c55e" if groupm_yoy >= 0 else "#ef4444"
    _a = "&#9650;" if groupm_yoy >= 0 else "&#9660;"
    kpi1_yoy = f"<span style='color:{_c};font-weight:700;font-size:0.88rem;'>{_a} {abs(groupm_yoy):.1f}%</span>"
kpi2_val = f"${rev_b/1e3:.1f}T" if rev_b and rev_b >= 1000 else (f"${rev_b:.0f}B" if rev_b else "&#8212;")
kpi2_yoy = ""
if rev_yoy is not None:
    _c = "#22c55e" if rev_yoy >= 0 else "#ef4444"
    _a = "&#9650;" if rev_yoy >= 0 else "&#9660;"
    kpi2_yoy = f"<span style='color:{_c};font-weight:700;font-size:0.88rem;'>{_a} {abs(rev_yoy):.1f}%</span>"
kpi3_val = f"${mcap_b/1e3:.1f}T" if mcap_b and mcap_b >= 1000 else (f"${mcap_b:.0f}B" if mcap_b else "&#8212;")
kpi3_yoy = ""
if mcap_yoy is not None:
    _c = "#22c55e" if mcap_yoy >= 0 else "#ef4444"
    _a = "&#9650;" if mcap_yoy >= 0 else "&#9660;"
    kpi3_yoy = f"<span style='color:{_c};font-weight:700;font-size:0.88rem;'>{_a} {abs(mcap_yoy):.1f}%</span>"

_hero_logo_items = []
for _hi, _hco in enumerate(_HERO_COMPANIES):
    _hb64 = _resolve_logo(_hco, logos)  # logos has white Amazon/Apple
    _hcolor = _company_color(_hco)
    if _hb64:
        _hero_logo_items.append(
            f"<div class='hl-logo' style='--hl-delay:{_hi * 0.4}s;--hl-brand:{_hcolor};' title='{_hco}'>"
            f"<img src='data:image/png;base64,{_hb64}' alt='{_hco}'/></div>"
        )
    else:
        # Fallback: styled initials with company brand color
        _initials = "".join(w[0] for w in _hco.split() if w[0].isupper())[:2]
        _hero_logo_items.append(
            f"<div class='hl-logo' style='--hl-delay:{_hi * 0.4}s;--hl-brand:{_hcolor};' title='{_hco}'>"
            f"<span style='color:#fff;font-weight:800;font-size:14px;font-family:DM Sans,sans-serif;'>{_initials}</span></div>"
        )
_hero_logo_count = len(_hero_logo_items)
_hero_logos_html = "".join(_hero_logo_items)

st.components.v1.html(
    "<style>@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800;900&family=DM+Sans:wght@400;500;700&display=swap');"
    "html,body{margin:0;padding:0;background:#020810;}*{box-sizing:border-box;}"
    "@keyframes hlPulse{0%,100%{box-shadow:0 0 0 transparent;}50%{box-shadow:0 0 12px color-mix(in srgb,var(--hl-brand) 35%,transparent);}}"
    "@keyframes kpiFadeIn{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:translateY(0);}}"
    ".hl-wrap{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:36px;align-items:center;}"
    ".hl-logo{width:42px;height:42px;border-radius:12px;background:rgba(255,255,255,0.04);"
    "border:1px solid rgba(255,255,255,0.08);display:flex;align-items:center;justify-content:center;"
    "cursor:pointer;transition:all 0.6s cubic-bezier(0.22,1,0.36,1);opacity:1;}"
    ".hl-logo.pulsing{animation:hlPulse 3s ease-in-out infinite;animation-delay:var(--hl-delay);}"
    ".hl-logo:hover{opacity:1!important;transform:scale(1.25)!important;animation:none;"
    "background:rgba(255,255,255,0.08);border-color:var(--hl-brand);box-shadow:0 0 18px color-mix(in srgb,var(--hl-brand) 40%,transparent);}"
    ".hl-logo img{width:28px;height:28px;object-fit:contain;pointer-events:none;}"
    ".kpi-card{opacity:0;animation:kpiFadeIn 0.6s ease forwards;}"
    "</style>"
    "<div style='background:transparent;padding:72px 48px 64px;font-family:DM Sans,sans-serif;'>"
    "<div style='color:#4aaeff;font-size:0.72rem;letter-spacing:0.3em;text-transform:uppercase;margin-bottom:20px;'>The Attention Economy</div>"
    f"<div style='color:#ffffff;font-size:3.2rem;font-weight:900;line-height:1.05;margin-bottom:24px;font-family:Syne,sans-serif;'>"
    f"{_hero_logo_count} companies.<br>"
    + (f"<span style='color:#4aaeff;'>${groupm_b:.0f}B</span> in advertising." if groupm_b else "One dashboard.")
    + "</div>"
    f"<div class='hl-wrap'>{_hero_logos_html}</div>"
    "<div style='display:flex;gap:16px;margin-bottom:40px;flex-wrap:wrap;'>"
    f"<div class='kpi-card' style='animation-delay:0.3s;flex:1;min-width:150px;background:rgba(255,255,255,0.05);border:1px solid rgba(74,174,255,0.15);border-radius:10px;padding:20px 16px;'>"
    f"<div style='color:#a8b3c0;font-size:0.7rem;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Global Ad Spend</div>"
    f"<div style='color:#4aaeff;font-size:2rem;font-weight:900;font-family:monospace;line-height:1.1;'>{kpi1_val}</div>"
    f"<div style='margin-top:4px;'>{kpi1_yoy}</div>"
    f"<div style='color:#8b949e;font-size:0.68rem;margin-top:6px;'>{effective_year_groupm} &middot; Global Aggregates</div></div>"
    f"<div class='kpi-card' style='animation-delay:0.6s;flex:1;min-width:150px;background:rgba(255,255,255,0.05);border:1px solid rgba(74,174,255,0.15);border-radius:10px;padding:20px 16px;'>"
    f"<div style='color:#a8b3c0;font-size:0.7rem;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Tracked Revenue</div>"
    f"<div style='color:#4aaeff;font-size:2rem;font-weight:900;font-family:monospace;line-height:1.1;'>{kpi2_val}</div>"
    f"<div style='margin-top:4px;'>{kpi2_yoy}</div>"
    f"<div style='color:#8b949e;font-size:0.68rem;margin-top:6px;'>{effective_year} &middot; {_hero_logo_count} companies</div></div>"
    f"<div class='kpi-card' style='animation-delay:0.9s;flex:1;min-width:150px;background:rgba(255,255,255,0.05);border:1px solid rgba(74,174,255,0.15);border-radius:10px;padding:20px 16px;'>"
    f"<div style='color:#a8b3c0;font-size:0.7rem;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Combined Market Cap</div>"
    f"<div style='color:#4aaeff;font-size:2rem;font-weight:900;font-family:monospace;line-height:1.1;'>{kpi3_val}</div>"
    f"<div style='margin-top:4px;'>{kpi3_yoy}</div>"
    f"<div style='color:#8b949e;font-size:0.68rem;margin-top:6px;'>{effective_year} &middot; {_hero_logo_count} companies</div></div>"
    "</div>"
    f"<div class='kpi-card' style='animation-delay:1.2s;font-size:1.05rem;line-height:1.85;color:#c9d1d9;max-width:680px;'>{narrative_html}</div>"
    "<div style='color:#8b949e;font-size:0.85rem;margin-top:48px;letter-spacing:0.1em;'>&#8595; Scroll to explore</div>"
    "</div>"
    "<script>setTimeout(function(){document.querySelectorAll('.hl-logo').forEach(function(el){el.classList.add('pulsing');});},5000);</script>",
    height=640,
)

# ── Helper: numeric ISO → alpha-3 mapping for D3 choropleth globe ──
def _build_numeric_iso_map() -> dict:
    """Maps D3/TopoJSON numeric country IDs to ISO 3166-1 alpha-3 codes."""
    return {
        "356": "IND", "360": "IDN", "076": "BRA", "566": "NGA", "050": "BGD",
        "586": "PAK", "231": "ETH", "180": "COD", "834": "TZA", "404": "KEN",
        "288": "GHA", "800": "UGA", "508": "MOZ", "450": "MDG", "120": "CMR",
        "384": "CIV", "024": "AGO", "894": "ZMB", "716": "ZWE", "646": "RWA",
        "608": "PHL", "704": "VNM", "764": "THA", "104": "MMR", "116": "KHM",
        "418": "LAO", "524": "NPL", "144": "LKA", "484": "MEX", "170": "COL",
        "032": "ARG", "604": "PER", "152": "CHL", "862": "VEN", "218": "ECU",
        "068": "BOL", "320": "GTM", "340": "HND", "222": "SLV", "558": "NIC",
        "188": "CRI", "591": "PAN", "214": "DOM", "192": "CUB", "840": "USA",
        "826": "GBR", "276": "DEU", "250": "FRA", "380": "ITA", "724": "ESP",
        "792": "TUR", "364": "IRN", "682": "SAU", "784": "ARE", "818": "EGY",
        "504": "MAR", "012": "DZA", "788": "TUN", "434": "LBY", "729": "SDN",
        "368": "IRQ", "760": "SYR", "400": "JOR", "422": "LBN", "414": "KWT",
        "634": "QAT", "048": "BHR", "512": "OMN", "710": "ZAF", "516": "NAM",
        "072": "BWA", "454": "MWI", "426": "LSO", "748": "SWZ",
        "528": "NLD", "056": "BEL", "756": "CHE", "040": "AUT", "620": "PRT",
        "616": "POL", "203": "CZE", "348": "HUN", "703": "SVK", "191": "HRV",
        "688": "SRB", "100": "BGR", "642": "ROU", "300": "GRC", "752": "SWE",
        "578": "NOR", "208": "DNK", "246": "FIN", "352": "ISL", "233": "EST",
        "428": "LVA", "440": "LTU", "124": "CAN", "036": "AUS", "554": "NZL",
        "372": "IRL", "702": "SGP", "458": "MYS", "344": "HKG", "158": "TWN",
        "392": "JPN", "410": "KOR", "858": "URY", "600": "PRY",
        "084": "BLZ", "398": "KAZ", "860": "UZB", "795": "TKM",
        "762": "TJK", "417": "KGZ", "004": "AFG", "496": "MNG",
        "388": "JAM", "442": "LUX", "705": "SVN", "332": "HTI",
    }


# Beat 1 — Map
map_body = (
    "The map below shows how global advertising spend is distributed across countries — "
    "colored by advertising intensity as a share of each country's GDP."
    if groupm_b
    else "Global advertising data for this year is unavailable."
)
_section("The World", "Every dollar. Every country.", map_body)
try:
    country_df = pd.DataFrame()
    # Try main excel_path first, then live_excel_path as fallback
    for _ep in [excel_path, live_excel_path if "live_excel_path" in dir() else ""]:
        if _ep and country_df.empty:
            country_df = _read_excel_sheet_cached(_ep, "Country_Totals_vs_GDP", source_stamp)
    if country_df.empty:
        logger.warning("Country_Totals_vs_GDP sheet unavailable — using fallback")
        _ctry_fb = [
            ("United States", 2024, 1.42), ("China", 2024, 0.68), ("Japan", 2024, 0.92),
            ("United Kingdom", 2024, 1.28), ("Germany", 2024, 0.85), ("France", 2024, 0.75),
            ("Brazil", 2024, 0.80), ("India", 2024, 0.38), ("Canada", 2024, 1.10),
            ("Australia", 2024, 1.15), ("South Korea", 2024, 1.05), ("Italy", 2024, 0.55),
            ("Spain", 2024, 0.68), ("Netherlands", 2024, 1.00), ("Mexico", 2024, 0.50),
            ("Indonesia", 2024, 0.35), ("Sweden", 2024, 0.90), ("Switzerland", 2024, 0.88),
            ("Turkey", 2024, 0.52), ("Saudi Arabia", 2024, 0.45), ("Norway", 2024, 0.85),
            ("Poland", 2024, 0.62), ("Belgium", 2024, 0.78), ("Denmark", 2024, 0.80),
            ("Argentina", 2024, 0.55), ("Thailand", 2024, 0.55), ("South Africa", 2024, 0.48),
            ("Malaysia", 2024, 0.50), ("Colombia", 2024, 0.42), ("Philippines", 2024, 0.40),
            ("Nigeria", 2024, 0.22), ("Egypt", 2024, 0.30), ("Russia", 2024, 0.45),
            ("Ireland", 2024, 0.65), ("Singapore", 2024, 0.90), ("New Zealand", 2024, 1.05),
            ("Finland", 2024, 0.72), ("Portugal", 2024, 0.58), ("Austria", 2024, 0.72),
            ("Czech Republic", 2024, 0.55), ("Chile", 2024, 0.60), ("Israel", 2024, 0.85),
            ("Vietnam", 2024, 0.32), ("Peru", 2024, 0.38), ("Romania", 2024, 0.42),
            ("Greece", 2024, 0.40), ("Hungary", 2024, 0.48), ("United Arab Emirates", 2024, 0.55),
        ]
        country_df = pd.DataFrame(_ctry_fb, columns=["Country", "Year", "Ad_Spend_pct_GDP"])
    if country_df.empty:
        st.info("Global map unavailable.")
    else:
        country_df.columns = [str(c).strip() for c in country_df.columns]
        country_col = _find_col(country_df, ["country"]) or _find_col(country_df, ["name"])
        year_col = _find_col(country_df, ["year"])
        value_col = _find_col(country_df, ["ad", "gdp"]) or _find_col(country_df, ["value"])
        scoped_map = _yr(country_df, effective_year, year_col) if year_col else country_df.copy()
        if scoped_map.empty or not country_col or not value_col:
            st.info("Global map unavailable.")
        else:
            scoped_map[value_col] = pd.to_numeric(scoped_map[value_col], errors="coerce")
            scoped_map = scoped_map.dropna(subset=[country_col, value_col]).copy()
            if scoped_map.empty:
                st.info("Global map unavailable.")
            else:
                # Build country name → ad spend % GDP dict for D3 globe
                _CHOROPLETH_ISO_TO_NAME = {
                    "USA": "United States", "GBR": "United Kingdom", "DEU": "Germany", "FRA": "France",
                    "JPN": "Japan", "CHN": "China", "IND": "India", "BRA": "Brazil", "CAN": "Canada",
                    "AUS": "Australia", "ITA": "Italy", "ESP": "Spain", "KOR": "South Korea",
                    "RUS": "Russia", "MEX": "Mexico", "IDN": "Indonesia", "TUR": "Turkey",
                    "NLD": "Netherlands", "SAU": "Saudi Arabia", "CHE": "Switzerland", "SWE": "Sweden",
                    "POL": "Poland", "BEL": "Belgium", "NOR": "Norway", "AUT": "Austria",
                    "ARE": "United Arab Emirates", "THA": "Thailand", "SGP": "Singapore",
                    "MYS": "Malaysia", "PHL": "Philippines", "VNM": "Vietnam", "ZAF": "South Africa",
                    "EGY": "Egypt", "NGA": "Nigeria", "ARG": "Argentina", "COL": "Colombia",
                    "CHL": "Chile", "PER": "Peru", "PRT": "Portugal", "DNK": "Denmark",
                    "FIN": "Finland", "IRL": "Ireland", "NZL": "New Zealand", "ISR": "Israel",
                    "CZE": "Czech Republic", "GRC": "Greece", "HUN": "Hungary", "ROU": "Romania",
                    "HKG": "Hong Kong", "TWN": "Taiwan", "PAK": "Pakistan", "BGD": "Bangladesh",
                }
                _NAME_TO_ISO = {v: k for k, v in _CHOROPLETH_ISO_TO_NAME.items()}
                _ad_gdp_data: dict[str, float] = {}
                for _, _row in scoped_map.iterrows():
                    _cname = str(_row[country_col])
                    _val = float(_row[value_col])
                    _iso = _NAME_TO_ISO.get(_cname, "")
                    if _iso:
                        _ad_gdp_data[_iso] = round(_val, 3)
                _ad_gdp_json = json.dumps(_ad_gdp_data)
                _ad_gdp_names_json = json.dumps({v: k for k, v in _NAME_TO_ISO.items() if v in _ad_gdp_data})

                st.components.v1.html(
                    """<!DOCTYPE html><html><head>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Syne:wght@700;800&display=swap">
<style>
html,body{margin:0;padding:0;background:#020810;overflow:hidden;font-family:'DM Sans',sans-serif;}
#adglobe-root{width:100%;height:600px;position:relative;background:#020810;}
#adglobe-tooltip{position:absolute;display:none;background:rgba(10,14,26,0.95);border:1px solid rgba(99,179,237,0.4);color:#e6edf3;padding:10px 14px;border-radius:8px;font-size:13px;pointer-events:none;z-index:100;max-width:220px;}
#adglobe-legend{position:absolute;bottom:16px;left:16px;display:flex;align-items:center;gap:6px;}
.adglobe-grad{width:180px;height:10px;border-radius:5px;background:linear-gradient(90deg,#0d2847,#1a5fb4,#3b82f6,#f97316,#ef4444);}
.adglobe-min,.adglobe-max{font-size:10px;color:#8b949e;}
</style></head><body>
<div id="adglobe-root">
<div id="adglobe-tooltip"></div>
<div id="adglobe-legend">
  <span class="adglobe-min">0%</span>
  <div class="adglobe-grad"></div>
  <span class="adglobe-max">1.5%+</span>
  <span style="font-size:10px;color:#6b7280;margin-left:8px;">Ad Spend % of GDP</span>
</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js"></script>
<script>
var adGdpData="""
                    + _ad_gdp_json
                    + """;
var num2alpha="""
                    + json.dumps(_build_numeric_iso_map())
                    + """;
var isoNames="""
                    + _ad_gdp_names_json
                    + """;
var root=document.getElementById('adglobe-root');
var tooltip=document.getElementById('adglobe-tooltip');
var W=root.clientWidth||900,H=600;
var svg=d3.select('#adglobe-root').append('svg').attr('width',W).attr('height',H).style('position','absolute').style('top','0').style('left','0').style('filter','drop-shadow(0 0 24px rgba(59,130,246,0.12))');
var projection=d3.geoOrthographic().scale(Math.min(W,H)*0.42).translate([W/2,H/2]).clipAngle(90).rotate([0,-20]);
var path=d3.geoPath().projection(projection);
var defs=svg.append('defs');
var radGrad=defs.append('radialGradient').attr('id','globeGlow').attr('cx','38%').attr('cy','32%').attr('r','65%');
radGrad.append('stop').attr('offset','0%').attr('stop-color','#1a3a5c').attr('stop-opacity',1);
radGrad.append('stop').attr('offset','60%').attr('stop-color','#0d1f35').attr('stop-opacity',1);
radGrad.append('stop').attr('offset','100%').attr('stop-color','#060d18').attr('stop-opacity',1);
var shimmerGrad=defs.append('radialGradient').attr('id','globeShimmer').attr('cx','35%').attr('cy','28%').attr('r','50%');
shimmerGrad.append('stop').attr('offset','0%').attr('stop-color','rgba(147,197,253,0.12)');
shimmerGrad.append('stop').attr('offset','100%').attr('stop-color','rgba(147,197,253,0)');
svg.append('circle').attr('cx',W/2).attr('cy',H/2).attr('r',projection.scale()).attr('fill','url(#globeGlow)').attr('stroke','rgba(99,179,237,0.15)').attr('stroke-width',1);
var gCountries=svg.append('g');
var shimmerCircle=svg.append('circle').attr('cx',W/2).attr('cy',H/2).attr('r',projection.scale()).attr('fill','url(#globeShimmer)').attr('pointer-events','none').style('opacity',0.6);
var shimUp=true;function animShimmer(){var cur=parseFloat(shimmerCircle.style('opacity'));var next=shimUp?cur+0.004:cur-0.004;if(next>=0.7)shimUp=false;if(next<=0.3)shimUp=true;shimmerCircle.style('opacity',next);requestAnimationFrame(animShimmer);}requestAnimationFrame(animShimmer);
function adColor(v){
  if(!v&&v!==0)return '#1a2744';
  var t=Math.min(v/1.5,1);
  if(t<0.25)return d3.interpolateRgb('#0d2847','#1a5fb4')(t/0.25);
  if(t<0.5)return d3.interpolateRgb('#1a5fb4','#3b82f6')((t-0.25)/0.25);
  if(t<0.75)return d3.interpolateRgb('#3b82f6','#f97316')((t-0.5)/0.25);
  return d3.interpolateRgb('#f97316','#ef4444')((t-0.75)/0.25);
}
fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json').then(function(r){return r.json();}).then(function(world){
  var countries=topojson.feature(world,world.objects.countries).features;
  gCountries.selectAll('path').data(countries).enter().append('path')
    .attr('d',path)
    .attr('fill',function(d){var a=num2alpha[String(d.id)]||'';var v=adGdpData[a];return adColor(v);})
    .attr('opacity',0.82)
    .attr('stroke','rgba(255,255,255,0.1)').attr('stroke-width',0.4)
    .style('cursor','pointer')
    .on('mousemove',function(event,d){
      var a=num2alpha[String(d.id)]||'';
      var cName=isoNames[a]||'';
      var v=adGdpData[a];
      if(!cName){tooltip.style.display='none';return;}
      tooltip.style.display='block';
      tooltip.style.left=(event.offsetX+12)+'px';
      tooltip.style.top=(event.offsetY-10)+'px';
      var pctHtml=v!==undefined?'<br>Ad Spend: <strong style="color:#f97316">'+v.toFixed(2)+'%</strong> of GDP':'';
      tooltip.innerHTML='<strong>'+cName+'</strong>'+pctHtml+'<br><span style="font-size:11px;color:#93c5fd;opacity:0.8;">Click to explore</span>';
    })
    .on('mouseleave',function(){tooltip.style.display='none';})
    .on('click',function(event,d){
      if(globeDragged)return;
      var a=num2alpha[String(d.id)]||'';
      var cName=isoNames[a]||'';
      if(!cName)return;
      try{window.open('/Overview?country='+encodeURIComponent(cName),'_blank');}catch(e){}
    });
  startRotation();
});
var lon=0,spinning=true,animId=null,lastTime=0;
var isDragging=false,dragStart=null,rotateStart=[0,-20],globeDragged=false;
function rotate(ts){
  if(!spinning)return;
  if(ts-lastTime>16){lon=(lon+0.25)%360;projection.rotate([lon,-20]);gCountries.selectAll('path').attr('d',path);lastTime=ts;}
  animId=requestAnimationFrame(rotate);
}
function startRotation(){spinning=true;animId=requestAnimationFrame(rotate);}
root.addEventListener('mousedown',function(e){
  isDragging=true;spinning=false;globeDragged=false;
  if(animId)cancelAnimationFrame(animId);
  dragStart=[e.clientX,e.clientY];rotateStart=projection.rotate().slice();
  tooltip.style.display='none';
});
root.addEventListener('mousemove',function(e){
  if(!isDragging||!dragStart)return;
  var dx=e.clientX-dragStart[0],dy=e.clientY-dragStart[1];
  if(Math.sqrt(dx*dx+dy*dy)>5)globeDragged=true;
  var newLon=rotateStart[0]+dx*0.4;
  var newLat=Math.max(-60,Math.min(60,rotateStart[1]-dy*0.4));
  lon=newLon%360;projection.rotate([lon,newLat]);
  gCountries.selectAll('path').attr('d',path);
});
root.addEventListener('mouseup',function(){isDragging=false;dragStart=null;setTimeout(function(){if(!isDragging)startRotation();},2000);});
root.addEventListener('mouseleave',function(){if(isDragging){isDragging=false;dragStart=null;setTimeout(function(){startRotation();},2000);}});
</script></body></html>""",
                    height=660,
                    scrolling=False,
                )
except Exception:
    st.info("Global map unavailable.")
st.caption("Globe shows advertising spend by country as a % of GDP. Blue → orange → red = higher ad market intensity.")
_deep_dive("overview", "Explore ad data by country")
_separator()

# Beat 1.5 — Structural Shift donut animation
@st.cache_data(show_spinner=False)
def _build_ss_html(ss_data_json: str) -> str:
    return f"""
<div id="wm-ss-root">
<style>
  html,body{{margin:0;padding:0;background:#020810;border:none;outline:none;}}
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Syne:wght@700;800&display=swap');
  #wm-ss-root{{background:transparent;color:#e6edf3;font-family:'DM Sans',sans-serif;width:100%;padding:32px 24px 24px;}}
#wm-ss-root *{{box-sizing:border-box;}}
.wm-ss-label{{color:#4aaeff;font-family:'Syne',sans-serif;font-size:11px;letter-spacing:.28em;text-transform:uppercase;margin-bottom:10px;font-weight:700;}}
.wm-ss-headline{{color:#e6edf3;font-family:'Syne',sans-serif;font-size:28px;line-height:1.14;margin:0 0 8px;font-weight:800;}}
.wm-ss-body{{color:#8b949e;font-size:14px;line-height:1.55;margin:0 0 20px;}}
.wm-ss-main{{display:flex;gap:24px;align-items:center;min-height:280px;}}
.wm-ss-left{{width:55%;display:flex;justify-content:center;align-items:center;}}
.wm-ss-right{{width:45%;padding:0 8px;}}
.wm-ss-year{{font-family:'Syne',sans-serif;font-size:72px;font-weight:800;color:#e6edf3;line-height:1;}}
.wm-ss-yearlabel{{color:#c9d1d9;font-size:17px;margin-top:10px;line-height:1.45;font-weight:500;}}
.wm-ss-total{{color:#ff5b1f;font-family:'Syne',sans-serif;font-size:23px;font-weight:700;margin-top:14px;}}
.wm-ss-legend{{display:flex;flex-wrap:wrap;gap:12px;margin-top:18px;}}
.wm-ss-leg-item{{display:flex;align-items:center;gap:7px;font-size:13px;color:#8b949e;}}
.wm-ss-leg-dot{{width:10px;height:10px;border-radius:3px;flex-shrink:0;}}
</style>
<div class="wm-ss-main">
  <div class="wm-ss-left"><canvas id="wm-ss-canvas" width="280" height="280"></canvas></div>
  <div class="wm-ss-right">
    <div class="wm-ss-year" id="wm-ss-yr">—</div>
    <div class="wm-ss-yearlabel" id="wm-ss-lbl"></div>
    <div class="wm-ss-total" id="wm-ss-tot"></div>
  </div>
</div>
<div class="wm-ss-legend">
  <div class="wm-ss-leg-item"><div class="wm-ss-leg-dot" style="background:#3a5a8c"></div>Free TV</div>
  <div class="wm-ss-leg-item"><div class="wm-ss-leg-dot" style="background:#6b7280"></div>Print</div>
  <div class="wm-ss-leg-item"><div class="wm-ss-leg-dot" style="background:#ff5b1f"></div>Digital Search</div>
  <div class="wm-ss-leg-item"><div class="wm-ss-leg-dot" style="background:#f59e0b"></div>Digital Social</div>
  <div class="wm-ss-leg-item"><div class="wm-ss-leg-dot" style="background:#10b981"></div>Digital Video</div>
  <div class="wm-ss-leg-item"><div class="wm-ss-leg-dot" style="background:#374151"></div>Everything Else</div>
</div>
<script>
const KEYS=["Free TV","Print","Digital Search","Digital Social","Digital Video","Everything Else"];
const COLORS={{"Free TV":"#3a5a8c","Print":"#6b7280","Digital Search":"#ff5b1f","Digital Social":"#f59e0b","Digital Video":"#10b981","Everything Else":"#374151"}};
const DATA={ss_data_json};
const LABELS={{
  1999:"TV dominates. Internet is a rounding error.",
  2000:"The dot-com bubble. Digital spend is minimal.",
  2001:"Dot-com bust. Traditional media holds firm.",
  2002:"Recovery. Print still leads all digital combined.",
  2003:"Search advertising takes root.",
  2004:"Search starts to matter.",
  2005:"Google goes public. Search accelerates.",
  2006:"YouTube launches. Video is coming.",
  2007:"iPhone arrives. The mobile era begins.",
  2008:"Mobile arrives. Print begins its long decline.",
  2009:"Financial crisis. Ad budgets contract sharply.",
  2010:"Recovery. Digital now rivals radio spend.",
  2011:"Social explodes as Facebook hits 500M users.",
  2012:"Social explodes on mobile.",
  2013:"Mobile search surpasses desktop search.",
  2014:"Programmatic display transforms ad buying.",
  2015:"Digital overtakes TV in the largest markets.",
  2016:"Digital overtakes TV globally for the first time.",
  2017:"Duopoly: Google + Meta capture most digital spend.",
  2018:"GDPR reshapes data and targeting.",
  2019:"Mobile search surpasses all of TV.",
  2020:"Pandemic. Streaming surges. OOH collapses.",
  2021:"Pandemic accelerates everything digital.",
  2022:"Retail media rises. Privacy changes hit targeting.",
  2023:"AI reshapes search. Retail media surpasses $100B.",
  2024:"Search + Social = 60% of all ad spend."
}};
const YEARS=Object.keys(DATA).map(Number).sort((a,b)=>a-b);
const canvas=document.getElementById('wm-ss-canvas');
const ctx=canvas.getContext('2d');
let currentAngles=null,rafId=null,stepIdx=0,pauseTimer=null;
function getAngles(yr){{const d=DATA[yr];const total=KEYS.reduce((s,k)=>s+d[k],0);let a=-Math.PI/2;return KEYS.map(k=>{{const slice=total>0?(d[k]/total)*Math.PI*2:0;const start=a;a+=slice;return{{start,end:a,color:COLORS[k]}};}}); }}
function lerp(a,b,t){{return a+(b-a)*t;}}
function drawDonut(angles){{ctx.clearRect(0,0,280,280);const cx=140,cy=140,r=120,ir=72;angles.forEach(s=>{{ctx.beginPath();ctx.moveTo(cx,cy);ctx.arc(cx,cy,r,s.start,s.end);ctx.closePath();ctx.fillStyle=s.color;ctx.fill();}});ctx.beginPath();ctx.arc(cx,cy,ir,0,Math.PI*2);ctx.fillStyle='#020810';ctx.fill();}}
function animateTo(from,to,onDone){{let t=0;function step(){{t=Math.min(t+0.04,1);const interp=from.map((s,i)=>(({{start:lerp(s.start,to[i].start,t),end:lerp(s.end,to[i].end,t),color:to[i].color}})));drawDonut(interp);if(t<1){{rafId=requestAnimationFrame(step);}}else{{onDone();}}}}rafId=requestAnimationFrame(step);}}
function formatB(yr){{const total=KEYS.reduce((s,k)=>s+DATA[yr][k],0);return'$'+(total/1000).toFixed(0)+'B total';}}
function runStep(){{if(stepIdx>=YEARS.length){{stepIdx=0;}}const yr=YEARS[stepIdx];const to=getAngles(yr);document.getElementById('wm-ss-yr').textContent=yr;document.getElementById('wm-ss-lbl').textContent=LABELS[yr]||'';document.getElementById('wm-ss-tot').textContent=formatB(yr);const lastYr=YEARS[YEARS.length-1];const pause=yr===lastYr?2000:700;animateTo(currentAngles||to,to,()=>{{currentAngles=to;stepIdx++;pauseTimer=setTimeout(runStep,pause);}});}}
if(YEARS.length>0){{currentAngles=getAngles(YEARS[0]);drawDonut(currentAngles);document.getElementById('wm-ss-yr').textContent=YEARS[0];document.getElementById('wm-ss-lbl').textContent=LABELS[YEARS[0]]||'';document.getElementById('wm-ss-tot').textContent=formatB(YEARS[0]);stepIdx=1;pauseTimer=setTimeout(runStep,800);}}
</script>
</div>
"""

_section("THE STRUCTURAL SHIFT", "Television had the world's total attention. Then new players came to compete.", "Global advertising by channel. Watch where the money moved.")
st.markdown("<div data-ae-section='1' style='width:100%;'>", unsafe_allow_html=True)
st.components.v1.html(_build_ss_html(_ss_data_json), height=540)
st.markdown("</div>", unsafe_allow_html=True)
_deep_dive("overview", "Explore the full ad landscape")
_separator()
_wr_logos = {}
_wr_companies = ["Alphabet", "Amazon", "Apple", "Microsoft", "Meta", "Netflix", "Disney", "Comcast", "Spotify", "Roku"]
for _wr_co in _wr_companies:
    _wr_b64 = _resolve_logo(_wr_co, logos)
    if _wr_b64:
        _wr_logos[_wr_co] = _wr_b64
_wr_logos_json = json.dumps(_wr_logos)

# Revenue anatomy — cached loop processing
_wr_year_data_json = _build_revenue_anatomy_json(excel_path, source_stamp)
_wr_year_data_parsed = json.loads(_wr_year_data_json) if _wr_year_data_json != "{}" else {}
_wr_latest_year = max(int(k) for k in _wr_year_data_parsed) if _wr_year_data_parsed else effective_year
_section("REVENUE ANATOMY", "Not all revenue is advertising.",
         f"Total {_wr_latest_year} revenue per company. Orange = ad revenue. Blue = everything else.")
st.markdown("<div data-ae-section='1' style='width:100%;'>", unsafe_allow_html=True)
st.components.v1.html(
    """
<div id="wm-rev-root">
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Syne:wght@700;800&display=swap');
html,body{margin:0;padding:0;background:#020810;border:none;outline:none;}
#wm-rev-root{background:transparent;color:#e6edf3;font-family:'DM Sans',sans-serif;width:100%;padding:32px 24px 24px;}
#wm-rev-root *{box-sizing:border-box;}
.wr-grid{display:flex;gap:0;align-items:flex-end;justify-content:space-between;width:100%;}
.wr-col{display:flex;flex-direction:column;align-items:center;flex:1;min-width:0;}
.wr-bars{display:flex;flex-direction:column;align-items:stretch;width:80%;margin:0 auto 6px;}
.wr-bar{width:100%;position:relative;min-height:2px;}
.wr-bar-other{background:#1e3a5f;transition:height 1.2s cubic-bezier(.34,1.1,.64,1);border-radius:4px 4px 0 0;}
.wr-bar-ad{background:#ff5b1f;transition:height 1.0s cubic-bezier(.34,1.1,.64,1);border-radius:0 0 4px 4px;}
@keyframes wrBreathe{0%,100%{transform:scale(1);opacity:1;}50%{transform:scale(1.08);opacity:0.85;}}
.wr-logo-img{height:34px;width:auto;max-width:68px;object-fit:contain;margin-bottom:6px;display:block;animation:wrBreathe 3s ease-in-out infinite;}
.wr-name{font-size:11px;font-weight:700;color:#e6edf3;text-align:center;margin-bottom:4px;font-family:'Syne',sans-serif;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;width:100%;}
.wr-total{font-size:11px;color:#8b949e;text-align:center;margin-top:3px;}
.wr-legend{display:flex;gap:20px;margin-top:20px;}
.wr-leg{display:flex;align-items:center;gap:6px;font-size:11px;color:#8b949e;}
.wr-leg-dot{width:10px;height:10px;border-radius:2px;}
</style>
<div class="wr-grid" id="wr-grid">
</div>
<div class="wr-legend">
  <div class="wr-leg"><div class="wr-leg-dot" style="background:#ff5b1f;"></div>Ad Revenue</div>
  <div class="wr-leg"><div class="wr-leg-dot" style="background:#1e3a5f;"></div>Other Revenue</div>
</div>
<script>
var WR_LOGOS="""
    + _wr_logos_json
    + """;
/* Year-by-year data — loaded dynamically from Google Sheet */
const yearData="""
    + _wr_year_data_json
    + """;
const years=Object.keys(yearData).map(Number).sort();
/* Use 2024 order for consistent column positions */
const latestYear=years[years.length-1];
const companyOrder=(yearData[latestYear]||[]).sort((a,b)=>b.total-a.total).map(c=>c.name);
const globalMax=Math.max(...Object.values(yearData).flatMap(arr=>arr.map(c=>c.total)));
const maxH=320;
const grid=document.getElementById('wr-grid');

/* Year overlay */
const yrOverlay=document.createElement('div');
yrOverlay.id='wr-year-overlay';
yrOverlay.style.cssText='position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:64px;font-weight:800;color:rgba(255,255,255,0.04);font-family:Syne,sans-serif;pointer-events:none;z-index:0;transition:opacity 0.4s;';
grid.style.position='relative';
grid.appendChild(yrOverlay);

/* Build columns once (2024 order) */
companyOrder.forEach((name,idx)=>{
  const col=document.createElement('div');
  col.className='wr-col';
  col.dataset.company=name;
  const logoHtml=WR_LOGOS[name]
    ?'<img class="wr-logo-img" style="animation-delay:'+idx*0.3+'s" src="data:image/png;base64,'+WR_LOGOS[name]+'" alt="'+name+'">'
    :'<div class="wr-name">'+name+'</div>';
  col.innerHTML=logoHtml+
    '<div class="wr-bars">'+
      '<div class="wr-bar wr-bar-other" style="height:0px"></div>'+
      '<div class="wr-bar wr-bar-ad" style="height:0px"></div>'+
    '</div>'+
    '<div class="wr-total" style="min-height:18px"></div>';
  grid.appendChild(col);
});

function renderYear(yr){
  yrOverlay.textContent=yr;
  const data=yearData[yr]||[];
  const lookup={};
  data.forEach(d=>{lookup[d.name]=d;});
  companyOrder.forEach(name=>{
    const col=grid.querySelector('[data-company="'+name+'"]');
    if(!col)return;
    const d=lookup[name]||{total:0,ad:0};
    const adH=Math.round((d.ad/globalMax)*maxH);
    const otherH=Math.round(((d.total-d.ad)/globalMax)*maxH);
    const adPct=d.total>0?Math.round((d.ad/d.total)*100):0;
    col.querySelector('.wr-bar-other').style.height=otherH+'px';
    col.querySelector('.wr-bar-ad').style.height=adH+'px';
    col.querySelector('.wr-total').textContent='$'+(d.total>=10?Math.round(d.total)+'B':d.total+'B')+' \xb7 '+adPct+'% ad';
  });
}

/* Animate through years when visible */
const io=new IntersectionObserver(entries=>{
  if(!entries[0].isIntersecting)return;
  io.unobserve(entries[0].target);
  let step=0;
  function playNext(){
    if(step>=years.length)return;
    renderYear(years[step]);
    step++;
    if(step<years.length){
      setTimeout(playNext, step===1?1200:900);
    }
  }
  setTimeout(playNext,400);
},{threshold:0.2});
io.observe(grid);
</script>
</div>
""",
    height=540,
)
st.markdown("</div>", unsafe_allow_html=True)
_deep_dive("earnings", "See full earnings breakdown")

# ═══════════════════════════════════════════════════════════════════════════════
# Beat 5.5 — Forward Intelligence CEO Carousel
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from utils.transcript_live import extract_forward_looking_signals_batch

    _FI_COMPANIES = [
        "Alphabet", "Amazon", "Apple", "Comcast", "Disney",
        "Meta Platforms", "Microsoft", "Netflix", "Paramount Global",
        "Roku", "Spotify", "Warner Bros. Discovery", "Samsung", "Tencent",
    ]

    # Single batch call reads the Transcripts sheet ONCE instead of 14 times
    _fi_all = extract_forward_looking_signals_batch(
        excel_path, companies=tuple(_FI_COMPANIES), year=int(selected_year), max_signals_per_company=1
    )

    _fi_cards: list[dict] = []
    for _fi_co in _FI_COMPANIES:
        _fi_sigs = _fi_all.get(_fi_co, [])
        if not _fi_sigs:
            continue
        _fi_sig = _fi_sigs[0]
        _fi_logo_b64 = _resolve_logo(_fi_co, logos)
        _fi_cards.append({
            "company": _fi_co,
            "quote": _fi_sig.get("quote", ""),
            "speaker": _fi_sig.get("speaker", ""),
            "role": _fi_sig.get("role", ""),
            "score": round(_fi_sig.get("score", 0), 2),
            "category": _fi_sig.get("category", "Outlook"),
            "year": _fi_sig.get("year", int(selected_year)),
            "quarter": _fi_sig.get("quarter", ""),
            "logo": _fi_logo_b64,
            "color": _company_color(_fi_co),
        })

    if _fi_cards:
        _section(
            "FORWARD INTELLIGENCE",
            "What management teams are betting on.",
            "The highest-confidence forward-looking statements from the latest earnings calls — scored and verified."
        )

        _fi_json_str = json.dumps(_fi_cards)

        st.components.v1.html(f"""
<div id="fi-root" style="width:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;position:relative;overflow:hidden;padding:24px 0 16px;">
  <style>
    #fi-track {{ display:flex; align-items:center; justify-content:center; gap:20px; transition:transform 0.55s cubic-bezier(0.22,1,0.36,1); position:relative; z-index:1; }}
    .fi-card {{
      flex-shrink:0; width:340px; min-height:480px;
      border-radius:20px; padding:24px 26px; box-sizing:border-box;
      display:flex; flex-direction:column; justify-content:space-between;
      position:relative; overflow:hidden;
      transition: transform 0.55s cubic-bezier(0.22,1,0.36,1), opacity 0.55s ease, filter 0.55s ease;
      transform: scale(0.82); opacity:0.45; filter:blur(3px);
      cursor:pointer;
    }}
    .fi-card.active {{ transform:scale(1); opacity:1; filter:blur(0); z-index:2; }}
    .fi-card.adjacent {{ transform:scale(0.88); opacity:0.55; filter:blur(2px); }}
    .fi-card::before {{
      content:''; position:absolute; inset:0; border-radius:20px;
      border:1px solid rgba(255,255,255,0.12);
      pointer-events:none; z-index:1;
    }}
    .fi-card::after {{
      content:''; position:absolute; inset:0; border-radius:20px;
      background:radial-gradient(ellipse at 30% 20%, var(--brand) 0%, transparent 70%);
      opacity:0.13; pointer-events:none; z-index:0;
    }}
    .fi-card > * {{ position:relative; z-index:2; }}
    .fi-progress {{ position:absolute;top:0;left:0;width:100%;height:3px;background:rgba(255,255,255,0.06);border-radius:20px 20px 0 0;z-index:3; }}
    .fi-progress-bar {{ height:100%;width:0%;background:linear-gradient(90deg,#4aaeff,#f97316);border-radius:20px 20px 0 0;transition:width 0.4s ease; }}
    .fi-top {{ display:flex; align-items:center; justify-content:space-between; }}
    .fi-top-left {{ display:flex; flex-direction:column; gap:6px; }}
    .fi-badge {{ background:linear-gradient(135deg,#4aaeff,#2563eb);color:#fff;font-size:11px;font-weight:700;padding:3px 12px;border-radius:20px;letter-spacing:0.5px;display:inline-block; }}
    .fi-cat {{ color:rgba(255,255,255,0.45);font-size:10px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase; }}
    .fi-label {{ color:rgba(74,174,255,0.6);font-size:10px;font-weight:600;letter-spacing:2px;text-transform:uppercase;margin-top:2px; }}
    .fi-logo-top {{ width:44px;height:44px;border-radius:12px;background:rgba(255,255,255,0.08);display:flex;align-items:center;justify-content:center;overflow:hidden;flex-shrink:0; }}
    .fi-logo-top img {{ width:32px;height:32px;object-fit:contain; }}
    .fi-quote {{ font-size:clamp(15px,2.8vw,20px);font-weight:800;color:#fff;line-height:1.35;letter-spacing:-0.2px;flex:1;display:flex;align-items:center; }}
    .fi-speaker {{ color:#4aaeff;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px; }}
    .fi-role {{ color:rgba(255,255,255,0.3);font-size:10px;font-weight:500; }}
    .fi-bottom {{ display:flex;align-items:center;justify-content:space-between; }}
    .fi-co-name {{ color:#fff;font-size:13px;font-weight:700; }}
    .fi-score-text {{ color:rgba(74,174,255,0.5);font-size:10px;font-weight:600; }}
    .fi-controls {{ display:flex;align-items:center;gap:18px;margin-top:16px;justify-content:center;position:relative;z-index:3; }}
    .fi-btn {{ background:rgba(74,174,255,0.1);border:1px solid rgba(74,174,255,0.2);color:#4aaeff;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;transition:all 0.2s; }}
    .fi-btn:hover {{ background:rgba(74,174,255,0.2); }}
    .fi-btn-play {{ background:linear-gradient(135deg,#4aaeff,#2563eb);border:none;color:#fff;width:46px;height:46px;border-radius:50%;cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;transition:all 0.2s;box-shadow:0 4px 16px rgba(74,174,255,0.25); }}
    .fi-btn-play:hover {{ transform:scale(1.06); }}
    .fi-dots {{ display:flex;gap:6px;margin-top:10px;justify-content:center;z-index:3;position:relative; }}
    .fi-dot {{ width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,0.2);transition:all 0.3s;cursor:pointer; }}
    .fi-dot.on {{ background:#4aaeff;width:18px;border-radius:3px; }}
  </style>

  <!-- Track of cards -->
  <div id="fi-track"></div>

  <!-- Controls -->
  <div class="fi-controls">
    <button class="fi-btn" id="fi-prev">&#9664;</button>
    <button class="fi-btn-play" id="fi-play">&#9654;</button>
    <button class="fi-btn" id="fi-next">&#9654;</button>
  </div>
  <div class="fi-dots" id="fi-dots"></div>
</div>

<script>
(function() {{
  const cards = {_fi_json_str};
  if (!cards.length) return;

  let idx = 0, playing = true, timer = null;
  const track = document.getElementById('fi-track');
  const dotsC = document.getElementById('fi-dots');
  const btnPlay = document.getElementById('fi-play');
  const btnPrev = document.getElementById('fi-prev');
  const btnNext = document.getElementById('fi-next');

  /* — build all card elements once — */
  cards.forEach((c, i) => {{
    const el = document.createElement('div');
    el.className = 'fi-card';
    el.style.setProperty('--brand', c.color || '#4aaeff');
    el.style.background = 'linear-gradient(160deg, rgba(10,22,40,0.92), rgba(10,22,40,0.97))';
    const logoHtml = c.logo
      ? '<div class="fi-logo-top"><img src="data:image/png;base64,' + c.logo + '"/></div>'
      : '';
    const qTxt = c.quote.length > 220 ? c.quote.substring(0, 217) + '...' : c.quote;
    el.innerHTML =
      '<div class="fi-progress"><div class="fi-progress-bar" data-bar></div></div>' +
      '<div class="fi-top">' +
        '<div class="fi-top-left">' +
          '<div><span class="fi-badge">' + (c.quarter ? c.quarter + ' ' : '') + c.year + '</span> <span class="fi-cat">' + (c.category || 'Outlook') + '</span></div>' +
          '<div class="fi-label">Forward Intelligence</div>' +
        '</div>' +
        logoHtml +
      '</div>' +
      '<div class="fi-quote">\\u201C' + qTxt + '\\u201D</div>' +
      '<div><div class="fi-speaker">' + (c.speaker || 'Executive') + '</div><div class="fi-role">' + (c.role || '') + '</div></div>' +
      '<div class="fi-bottom">' +
        '<div><div class="fi-co-name">' + c.company + '</div><div class="fi-score-text">Confidence ' + (c.score * 100).toFixed(0) + '%</div></div>' +
      '</div>';
    el.addEventListener('click', () => {{ stopPlay(); goTo(i); }});
    track.appendChild(el);
    /* dot */
    const dot = document.createElement('div');
    dot.className = 'fi-dot';
    dot.addEventListener('click', () => {{ stopPlay(); goTo(i); }});
    dotsC.appendChild(dot);
  }});

  const cardEls = track.querySelectorAll('.fi-card');
  const dotEls  = dotsC.querySelectorAll('.fi-dot');

  function render() {{
    cardEls.forEach((el, i) => {{
      el.classList.remove('active', 'adjacent');
      if (i === idx) el.classList.add('active');
      else if (Math.abs(i - idx) === 1) el.classList.add('adjacent');
    }});
    dotEls.forEach((d, i) => d.classList.toggle('on', i === idx));
    /* scroll track so active card is centered */
    const activeEl = cardEls[idx];
    const trackRect = track.parentElement.getBoundingClientRect();
    const off = activeEl.offsetLeft + activeEl.offsetWidth / 2 - trackRect.width / 2;
    track.style.transform = 'translateX(' + (-off) + 'px)';
    /* progress bars */
    cardEls.forEach((el, i) => {{
      const bar = el.querySelector('[data-bar]');
      if (bar) bar.style.width = (i <= idx ? '100%' : '0%');
    }});
  }}

  function goTo(i) {{
    idx = ((i % cards.length) + cards.length) % cards.length;
    render();
  }}

  function goNext() {{ goTo(idx + 1); }}
  function goPrev() {{ goTo(idx - 1); }}

  function startPlay() {{
    playing = true; btnPlay.innerHTML = '&#9208;';
    timer = setInterval(goNext, 3500);
  }}
  function stopPlay() {{
    playing = false; btnPlay.innerHTML = '&#9654;';
    if (timer) {{ clearInterval(timer); timer = null; }}
  }}
  function togglePlay() {{
    if (playing) stopPlay(); else startPlay();
  }}

  btnPlay.addEventListener('click', togglePlay);
  btnPrev.addEventListener('click', () => {{ stopPlay(); goPrev(); }});
  btnNext.addEventListener('click', () => {{ stopPlay(); goNext(); }});
  document.addEventListener('keydown', (e) => {{
    if (e.key === 'ArrowLeft')  {{ stopPlay(); goPrev(); }}
    if (e.key === 'ArrowRight') {{ stopPlay(); goNext(); }}
    if (e.key === ' ')          {{ e.preventDefault(); togglePlay(); }}
  }});

  render();
  setTimeout(startPlay, 1200);
}})();
</script>
""", height=600)

except Exception as _fi_err:
    import logging as _fi_log
    _fi_log.getLogger(__name__).warning("Forward Intelligence carousel: %s", _fi_err)

_deep_dive("overview", "Explore signals in Narrative & Sentiment")
_separator()

def _build_attn_html(ad_json_str: str, groupm_json_str: str, human_json_str: str = '[]', logos_json: str = '{}') -> str:
    # Escape </ sequences in JSON to prevent premature </script> closing
    _safe_human = human_json_str.replace("</", "<\\/")
    _safe_logos = logos_json.replace("</", "<\\/")
    return (
        """<!DOCTYPE html><html><head><meta charset='utf-8'>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
html,body{background:#020810;color:#e6edf3;font-family:'DM Sans','Montserrat',sans-serif;height:100%;overflow:hidden;}
#wa-attn-root{position:relative;width:100%;height:520px;background:transparent;overflow:hidden;display:flex;align-items:stretch;}
.glow-yt,.glow-sp{display:none;}
#wa-attn-root::before{content:none;}
#wa-attn-left{position:relative;z-index:2;width:40%;padding:40px 32px;display:flex;flex-direction:column;justify-content:center;flex-shrink:0;}
.attn-label{color:#4aaeff;font-size:10px;letter-spacing:.22em;text-transform:uppercase;font-weight:700;margin-bottom:14px;}
.attn-headline{font-family:'Syne','DM Sans',sans-serif;font-size:clamp(28px,3.5vw,44px);font-weight:900;line-height:1.1;color:#e6edf3;margin-bottom:16px;}
.attn-body{color:#8899aa;font-size:13px;line-height:1.6;margin-bottom:24px;}
.attn-stat-label{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:#8899aa;margin-bottom:4px;}
.attn-stat-val{font-family:'Syne',sans-serif;font-size:clamp(32px,4vw,52px);font-weight:900;color:#ff0033;line-height:1;}
.attn-legend{margin-top:16px;display:grid;grid-template-columns:repeat(3,1fr);gap:4px;}
.attn-leg-row{display:flex;align-items:center;gap:8px;font-size:13px;color:#8899aa;}
.attn-leg-dot{width:12px;height:12px;border-radius:50%;flex-shrink:0;}
#wa-attn-bubbles{position:absolute;right:0;top:0;width:60%;height:100%;z-index:1;}
.wa-bubble{position:absolute;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:default;transform:scale(0);opacity:0;padding:8px;text-align:center;backdrop-filter:blur(8px);transition:transform 0.5s ease, opacity 0.5s ease;}
.wa-bubble.pop{animation-fill-mode:forwards;}
.wa-bubble.visible{transform:scale(1);opacity:1;}
.wa-bubble .bletter{width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.25);font-family:'Syne',sans-serif;font-size:12px;font-weight:800;color:#ffffff;margin-bottom:3px;}
.wa-bubble .blogo-wrap{width:42%;height:42%;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-bottom:3px;}
.wa-bubble .blogo-img{width:72%;height:72%;object-fit:contain;}
.wa-bubble .bname{font-weight:700;text-align:center;line-height:1.2;color:#fff;max-width:88%;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;word-break:break-word;}
.wa-bubble .busers{font-size:.58em;opacity:.7;color:#fff;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:90%;}
.wa-bubble .brevenue{font-size:.54em;opacity:.85;color:#ff9955;margin-top:1px;white-space:nowrap;font-weight:600;}
@keyframes floatA{0%,100%{transform:scale(1) translateY(0);}50%{transform:scale(1) translateY(-10px);}}
@keyframes floatB{0%,100%{transform:scale(1) translateY(0) rotate(0deg);}33%{transform:scale(1) translateY(-7px) rotate(-.4deg);}66%{transform:scale(1) translateY(5px) rotate(.4deg);}}
@keyframes floatC{0%,100%{transform:scale(1) translateY(0);}50%{transform:scale(1) translateY(-14px);}}
@keyframes popIn{0%{transform:scale(0);opacity:0;}70%{transform:scale(1.08);opacity:1;}100%{transform:scale(1);opacity:1;}}
</style></head><body>
<div id='wa-attn-root'>
  <div class='glow-yt'></div><div class='glow-sp'></div>
  <div id='wa-attn-left'>
    <div class='attn-body'>Each bubble = a platform. Size = subscribers or monthly active users.</div>
    <div class='attn-stat-label'>YouTube daily</div>
    <div id='wa-attn-counter' class='attn-stat-val'>0B hours</div>
    <div class='attn-legend' id='wa-attn-legend'></div>
  </div>
  <div id='wa-attn-bubbles'></div>
</div>
<script>
(function _initBubbles(){
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_run);return;}
_run();
function _run(){
try {
var RAW="""
        + _safe_human
        + """;
var LOGOS="""
        + _safe_logos
        + """;

function logoForName(name) {
  var n = String(name || '').toLowerCase();
  for (var k in LOGOS) {
    if (k.toLowerCase() === n) return LOGOS[k];
  }
  for (var k in LOGOS) {
    var kl = k.toLowerCase();
    if (n.indexOf(kl) !== -1 || kl.indexOf(n.split(/[^a-z]/)[0]) !== -1) return LOGOS[k];
  }
  return '';
}
var DATA = [];
if (Array.isArray(RAW) && RAW.length > 0) {
  DATA = RAW.slice().sort(function(a, b) { return (b.val || 0) - (a.val || 0); });
}
if (DATA.length === 0) {
  DATA = [
    {name:'YouTube',color:'#FF0033',val:2500,users:'2.5B MAUs',mins:21.9},
    {name:'Meta \u2013 Facebook',color:'#0866ff',val:2100,users:'2.1B DAUs'},
    {name:'Meta \u2013 Instagram',color:'#e1306c',val:2000,users:'2.0B MAUs'},
    {name:'Twitch',color:'#9147FF',val:240,users:'240M MAUs'},
    {name:'Spotify',color:'#1DB954',val:600,users:'600M MAUs'},
    {name:'Netflix',color:'#E50914',val:301,users:'301M subs'},
    {name:'Amazon Prime Video',color:'#FF9900',val:200,users:'200M actives'},
    {name:'Disney+ / Hulu / ESPN+',color:'#113CCF',val:149,users:'149M subs'},
    {name:'WBD Max / HBO',color:'#0047ab',val:97,users:'97M subs'},
    {name:'Paramount+',color:'#0033a0',val:71,users:'71M subs'},
    {name:'Comcast Peacock',color:'#2563eb',val:35,users:'35M subs'}
  ].sort(function(a,b){ return b.val-a.val; });
}
var maxVal = Math.max.apply(null, DATA.map(function(d){ return d.val || 1; }));
// Shorten long platform names to fit inside bubble (max 2 meaningful words)
function shortName(n) {
  var parts = (n||'').replace(/[/\u2013\u002d]+/g,' ').trim().split(/[ \t\n\r]+/).filter(Boolean);
  if (!parts.length) return n;
  var out = parts[0];
  if (parts.length > 1 && (out+' '+parts[1]).length <= 13) out = out+' '+parts[1];
  return out.length > 15 ? out.slice(0,14)+'\u2026' : out;
}
var ALL_POS = [
  {l:'3%',  t:'5%'},
  {l:'52%', t:'2%'},
  {l:'68%', t:'18%'},
  {l:'25%', t:'8%'},
  {l:'42%', t:'44%'},
  {l:'65%', t:'50%'},
  {l:'10%', t:'50%'},
  {l:'30%', t:'68%'},
  {l:'57%', t:'70%'},
  {l:'80%', t:'4%'},
  {l:'76%', t:'36%'},
  {l:'8%',  t:'28%'},
  {l:'46%', t:'22%'},
  {l:'82%', t:'62%'},
  {l:'18%', t:'80%'},
  {l:'63%', t:'82%'}
];
var FLOATS = ['floatA','floatB','floatC'];
var bfield = document.getElementById('wa-attn-bubbles');
var legend = document.getElementById('wa-attn-legend');
if (!bfield || !legend) {
  throw new Error('DOM elements not found: bfield=' + !!bfield + ' legend=' + !!legend);
}
var ytData = DATA.find(function(d){ return String(d.name||'').toLowerCase().indexOf('youtube') !== -1; });
var ytHoursB = 1.0;
if (ytData && ytData.mins) {
  ytHoursB = ytData.mins * 1e12 / 365 / 60 / 1e9;
  if (ytHoursB < 0.1) ytHoursB = 1.0;
}
var allBubbles = [];
DATA.forEach(function(item, i) {
  var normVal = maxVal > 0 ? (item.val || 1) / maxVal : 0.01;
  /* Reduce inter-bubble gap by 20%: multiplier 112 -> 90 */
  var size = Math.max(70, Math.round(28 + Math.sqrt(normVal) * 90));
  var radius = size / 2;
  var pos = ALL_POS[i] || {l: (5 + (i % 4) * 22) + '%', t: (5 + Math.floor(i / 4) * 30) + '%'};
  var fs = Math.max(7, Math.min(12, Math.round(size / 11)));
  var logoB64 = logoForName(item.name);
  /* Abbreviate name for small bubbles */
  var displayName;
  if (radius < 40) {
    displayName = item.users || shortName(item.name);
  } else if (radius < 55) {
    var parts = (item.name||'').replace(/[/\u2013\u002d]+/g,' ').trim().split(/[ \t\n\r]+/).filter(Boolean);
    displayName = parts[0] || item.name;
  } else {
    displayName = shortName(item.name);
  }
  var revStr = item.revenue ? '$' + (item.revenue >= 10 ? Math.round(item.revenue) + 'B' : item.revenue.toFixed(1) + 'B') + ' rev' : '';
  var rpmStr = item.rpm ? '$' + Number(item.rpm).toFixed(4) + '/min' : '';
  /* Semi-transparent backdrop style for text readability */
  var backdropStyle = 'text-shadow:0 0 6px rgba(0,0,0,0.8),0 1px 3px rgba(0,0,0,0.9);';
  var fs2 = Math.max(fs - 3, 6);
  /* Consistent stack: name -> users (always) -> revenue (if any) -> rpm (if any) */
  var commonLines = ''
    + (item.users && radius >= 40 ? '<div class="busers" style="font-size:' + Math.max(fs - 2, 7) + 'px;' + backdropStyle + '">' + item.users + '</div>' : '')
    + (revStr && radius >= 45 ? '<div class="brevenue" style="font-size:' + fs2 + 'px;' + backdropStyle + '">' + revStr + '</div>' : '')
    + (rpmStr && radius >= 50 ? '<div class="brevenue" style="font-size:' + fs2 + 'px;opacity:0.8;' + backdropStyle + '">' + rpmStr + '</div>' : '');
  var innerHtml;
  if (logoB64) {
    innerHtml = '<div class="blogo-wrap" style="background:rgba(255,255,255,0.88);">'
      + '<img class="blogo-img" src="data:image/png;base64,' + logoB64 + '" alt="' + displayName + '">'
      + '</div>'
      + '<div class="bname" style="font-size:' + fs + 'px;' + backdropStyle + '">' + displayName + '</div>'
      + commonLines;
  } else {
    var badge = (item.name||'?').replace(/[^A-Za-z0-9]+/g,' ').trim().split(' ').slice(0,2)
      .map(function(p){ return p.charAt(0).toUpperCase(); }).join('').slice(0,2) || '?';
    innerHtml = '<div class="bletter">' + badge + '</div>'
      + '<div class="bname" style="font-size:' + fs + 'px;' + backdropStyle + '">' + displayName + '</div>'
      + commonLines;
  }
  var b = document.createElement('div');
  b.className = 'wa-bubble';
  b.style.cssText = 'width:' + size + 'px;height:' + size + 'px;left:' + pos.l + ';top:' + pos.t
    + ';background:radial-gradient(circle at 35% 35%,' + item.color + 'cc,' + item.color + '66)'
    + ';border:1.5px solid ' + item.color + '55;box-shadow:0 0 ' + Math.round(size / 3) + 'px ' + item.color + '44;cursor:pointer;';
  b.innerHTML = innerHtml;
  b.title = 'Explore ' + item.name + ' on Editorial';
  (function(platformName){ b.addEventListener('click', function(){ try{ var bUrl=window.parent.location.pathname.replace(/[/][^/]*$/,'/'); window.parent.location.href = bUrl+'Editorial?company=' + encodeURIComponent(platformName); }catch(e){} }); })(item.name);
  bfield.appendChild(b);
  b._idx = i;
  allBubbles.push({el:b, idx:i, floatAnim:FLOATS[i%3], floatDur:3000+i*220});
  var row = document.createElement('div');
  row.className = 'attn-leg-row';
  row.innerHTML = '<div class="attn-leg-dot" style="background:' + item.color + ';"></div><span>' + item.name + (item.users ? ' \u2014 ' + item.users : '') + '</span>';
  legend.appendChild(row);
});
/* Animate bubbles in — use requestAnimationFrame for reliable timing in iframes */
function animateBubbles() {
  allBubbles.forEach(function(info) {
    var delay = info.idx * 80;
    setTimeout(function() {
      var el = info.el;
      el.style.animation = 'popIn 0.55s cubic-bezier(0.34,1.56,0.64,1) forwards,' + info.floatAnim + ' ' + info.floatDur + 'ms ease-in-out ' + (600 + info.idx * 80) + 'ms infinite';
      el.classList.add('pop');
    }, delay);
  });
  /* Safety net: if animations haven't triggered after 2s, force-show all bubbles */
  setTimeout(function() {
    allBubbles.forEach(function(info) {
      var cs = window.getComputedStyle(info.el);
      if (cs.opacity === '0' || cs.transform.indexOf('matrix(0') === 0) {
        info.el.classList.add('visible');
      }
    });
  }, 2000);
}
requestAnimationFrame(animateBubbles);
function countUp(el, target, dur) {
  var start = performance.now();
  function step(now) {
    var p = Math.min((now - start) / dur, 1);
    var ease = 1 - Math.pow(1 - p, 3);
    var value = ease * target;
    el.textContent = (p < 1 ? value.toFixed(1) : Math.round(value).toString()) + 'B hours';
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
setTimeout(function(){ countUp(document.getElementById('wa-attn-counter'), ytHoursB, 2000); }, 400);
} catch(err) {
  console.error('Bubble chart error:', err);
  var _errEl = document.getElementById('wa-attn-bubbles');
  if (_errEl) _errEl.innerHTML = '<div style="color:#ff5b1f;padding:40px 20px;font-size:14px;font-family:monospace;"><b>Bubble chart error</b><br>' + String(err.message||err) + '<br><br><span style="opacity:0.5;">RAW type: ' + typeof RAW + ', length: ' + (Array.isArray(RAW)?RAW.length:'N/A') + '</span></div>';
  var _ctrEl = document.getElementById('wa-attn-counter');
  if (_ctrEl) _ctrEl.textContent = 'Error';
}
}})();
</script>
</body></html>"""
    )

def _safe_float(v) -> float:
    import math
    try:
        r = float(pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0])
        return 0.0 if math.isnan(r) else r
    except Exception:
        return 0.0


def _parse_human_count_millions(value) -> float:
    if pd.isna(value):
        return float("nan")
    if isinstance(value, (int, float, np.number)):
        return float(value)
    match = re.search(r"([-+]?\d*\.?\d+)\s*([tbmk])?", str(value).replace(",", ""), re.I)
    if not match:
        return float("nan")
    number = float(match.group(1))
    suffix = (match.group(2) or "m").lower()
    scale = {"t": 1_000_000.0, "b": 1_000.0, "m": 1.0, "k": 0.001}.get(suffix, 1.0)
    return number * scale


def _parse_billions(value) -> float:
    if pd.isna(value):
        return float("nan")
    if isinstance(value, (int, float, np.number)):
        number = float(value)
        return number / 1000.0 if abs(number) >= 1000 else number
    match = re.search(r"([-+]?\d*\.?\d+)\s*([tbmk])?", str(value).replace(",", ""), re.I)
    if not match:
        return float("nan")
    number = float(match.group(1))
    suffix = (match.group(2) or "b").lower()
    scale = {"t": 1_000.0, "b": 1.0, "m": 0.001, "k": 0.000001}.get(suffix, 1.0)
    return number * scale


def _parse_trillion_minutes(value) -> float:
    if pd.isna(value):
        return float("nan")
    if isinstance(value, (int, float, np.number)):
        return float(value)
    match = re.search(r"([-+]?\d*\.?\d+)\s*([tbmk])?", str(value).replace(",", ""), re.I)
    if not match:
        return float("nan")
    number = float(match.group(1))
    suffix = (match.group(2) or "t").lower()
    scale = {"t": 1.0, "b": 0.001, "m": 0.000001, "k": 0.000000001}.get(suffix, 1.0)
    return number * scale

# Beat — The Human Side (before Scale of Attention)
_human_df = _read_excel_sheet_cached(excel_path, "Company_minute&dollar_earned", source_stamp) if excel_path else pd.DataFrame()
_human_companies: list[dict] = []
try:
    if not _human_df.empty:
        _human_df.columns = [str(c).strip() for c in _human_df.columns]
        _h_plat = _find_col(_human_df, ["platform"]) or _find_col(_human_df, ["company"]) or _find_col(_human_df, ["name"])
        _h_usr = (_find_col(_human_df, ["user"]) or _find_col(_human_df, ["subscrib"])
                  or _find_col(_human_df, ["mau"]) or _find_col(_human_df, ["active"]))
        _h_mins = (_find_col(_human_df, ["total", "minutes"]) or _find_col(_human_df, ["minutes", "watched"])
                   or _find_col(_human_df, ["minute"]) or _find_col(_human_df, ["avg", "time"]))
        _h_rev = _find_col(_human_df, ["revenue"])
        _h_rpm = (_find_col(_human_df, ["per", "minute"]) or _find_col(_human_df, ["dollar", "minute"])
                  or _find_col(_human_df, ["rpm"]) or _find_col(_human_df, ["min", "earn"]))
        _h_lbl = _find_col(_human_df, ["label"]) or _find_col(_human_df, ["note"])
        if _h_plat and _h_usr:
            _human_df[_h_usr] = _human_df[_h_usr].apply(_parse_human_count_millions)
            if _h_mins:
                _human_df[_h_mins] = _human_df[_h_mins].apply(_parse_trillion_minutes)
            if _h_rev:
                _human_df[_h_rev] = _human_df[_h_rev].apply(_parse_billions)
            if _h_rpm:
                _human_df[_h_rpm] = pd.to_numeric(_human_df[_h_rpm].astype(str).str.replace(r'[^0-9.\-eE]', '', regex=True), errors='coerce')
            _human_df = _human_df.dropna(subset=[_h_plat, _h_usr])
            _human_df = _human_df[_human_df[_h_usr] > 0].sort_values(_h_usr, ascending=False)
            for _, _hr in _human_df.iterrows():
                try:
                    _hname = str(_hr[_h_plat]).strip()
                    _hval = float(_hr[_h_usr])
                    _hmins = _safe_float(_hr.get(_h_mins, np.nan)) if _h_mins else np.nan
                    _hrev = _safe_float(_hr.get(_h_rev, np.nan)) if _h_rev else np.nan
                    _hrpm = _safe_float(_hr.get(_h_rpm, np.nan)) if _h_rpm else np.nan
                    _hlbl = (str(_hr[_h_lbl]).strip() if _h_lbl and not pd.isna(_hr.get(_h_lbl, np.nan)) else
                             (f"{_hval/1000:.1f}B" if _hval >= 1000 else f"{_hval:.0f}M"))
                    _human_companies.append(
                        {
                            "name": _hname,
                            "val": _hval,
                            "mins": _hmins if _hmins != 0.0 and not np.isnan(_hmins) else None,
                            "revenue": _hrev if _hrev != 0.0 and not np.isnan(_hrev) else None,
                            "rpm": _hrpm if _hrpm != 0.0 and not np.isnan(_hrpm) else None,
                            "users": _hlbl,
                            "color": _company_color(_hname),
                            "label": _hlbl,
                        }
                    )
                except Exception:
                    continue  # skip malformed rows rather than crashing the page
except Exception:
    pass  # fall through to hardcoded fallback below
if not _human_companies:
    _human_companies = [
        {"name": "YouTube", "val": 2500, "mins": 1000, "revenue": 36.1, "users": "2.5B users", "color": "#ff0000", "label": "2.5B users"},
        {"name": "Spotify", "val": 675, "mins": 30, "revenue": 15.7, "users": "675M users", "color": "#1db954", "label": "675M users"},
        {"name": "Netflix", "val": 301, "mins": 120, "revenue": 33.7, "users": "301M subs", "color": "#e50914", "label": "301M subs"},
        {"name": "Disney+", "val": 174, "mins": 68, "revenue": 14.5, "users": "174M subs", "color": "#113ccf", "label": "174M subs"},
        {"name": "Amazon", "val": 200, "mins": 55, "revenue": 10.2, "users": "200M Prime", "color": "#ff9900", "label": "200M Prime"},
        {"name": "Max (WBD)", "val": 116, "mins": 42, "revenue": 10.2, "users": "116M subs", "color": "#0047ab", "label": "116M subs"},
        {"name": "Paramount+", "val": 77, "mins": 35, "revenue": 6.8, "users": "77M subs", "color": "#0033a0", "label": "77M subs"},
        {"name": "Roku", "val": 89, "mins": 25, "revenue": 3.9, "users": "89M accounts", "color": "#6f1ab1", "label": "89M accounts"},
    ]
# Supplement _human_companies with data from Company_subscribers_values for
# services that may be missing from Company_minute&dollar_earned sheet
try:
    _subs_df2 = _read_excel_sheet_cached(excel_path, "Company_subscribers_values", source_stamp) if excel_path else pd.DataFrame()
    if _subs_df2 is not None and not _subs_df2.empty:
        _subs_df2.columns = [str(c).strip().lower() for c in _subs_df2.columns]
        if "service" in _subs_df2.columns and "subscribers" in _subs_df2.columns:
            _subs_df2["subscribers"] = pd.to_numeric(_subs_df2["subscribers"], errors="coerce")
            _subs_df2["year"] = pd.to_numeric(_subs_df2.get("year", pd.Series(dtype=float)), errors="coerce")
            _latest_subs2_raw: dict = {}
            for _svc2, _grp2 in _subs_df2.groupby("service"):
                _grp2 = _grp2.dropna(subset=["subscribers"])
                if _grp2.empty:
                    continue
                _sort_cols2 = ["year", "quarter"] if "quarter" in _grp2.columns else ["year"]
                _grp2 = _grp2.sort_values(_sort_cols2, ascending=False)
                _v2 = float(_grp2.iloc[0]["subscribers"])
                if _v2 > 0:
                    _latest_subs2_raw[str(_svc2).strip()] = _v2

            # Auto-group variants → base, track which bases were sums
            _svc2_names = sorted(_latest_subs2_raw.keys(), key=len)
            _latest_subs2: dict = {}
            _summed_into: dict = {}  # base_name → [variant qualifiers summed in]
            for _sn2 in _svc2_names:
                _base2 = _sn2
                for _cand2 in _svc2_names:
                    if _cand2 != _sn2 and _sn2.lower().startswith(_cand2.lower() + " "):
                        _base2 = _cand2
                        break
                if _base2 != _sn2:
                    # store the qualifier (e.g. "Premium" from "Spotify Premium")
                    _qual = _sn2[len(_base2):].strip()
                    _summed_into.setdefault(_base2, []).append(_qual)
                _latest_subs2[_base2] = _latest_subs2.get(_base2, 0.0) + _latest_subs2_raw[_sn2]

            # Name aliases for sheet keys that differ from display names
            _name_aliases = {
                "Amazon Prime": ["Amazon", "Amazon Prime Video"],
                "WBD": ["Max (WBD)", "WBD Max / HBO", "Warner Bros. Discovery"],
            }

            def _subs2_label(base, total_m):
                _lbl = f"{total_m/1000:.1f}B" if total_m >= 1000 else f"{total_m:.0f}M"
                _quals = _summed_into.get(base, [])
                if _quals:
                    _lbl += f" (incl. {', '.join(_quals)})"
                return _lbl

            # Update existing _human_companies entries first
            for _hc in _human_companies:
                _hcname = str(_hc.get("name", "")).strip().lower()
                for _base2, _subs_m2 in _latest_subs2.items():
                    _match_names = [_base2.lower()] + [a.lower() for a in _name_aliases.get(_base2, [])]
                    if any(_hcname == mn or _hcname.startswith(mn) or mn.startswith(_hcname) for mn in _match_names):
                        _slabel2 = _subs2_label(_base2, _subs_m2)
                        # Always update — live aggregated data supersedes sheet/hardcoded
                        _hc["val"] = _subs_m2
                        _hc["users"] = f"{_slabel2} subs"
                        _hc["label"] = f"{_slabel2} subs"
                        break

            # Add platforms from subscribers sheet not yet in _human_companies
            _hc_names_lower = {str(_c.get("name", "")).strip().lower() for _c in _human_companies}
            _subs_meta2 = {
                "Amazon Prime":  {"color": "#FF9900", "display": "Amazon Prime Video"},
                "Peacock":       {"color": "#9B2335", "display": "Comcast Peacock"},
                "WBD":           {"color": "#4a90d9", "display": "WBD Max / HBO"},
                "Disney+":       {"color": "#113CCF", "display": "Disney+ / Hulu / ESPN+"},
                "Paramount+":    {"color": "#7B2FBE", "display": "Paramount+"},
            }
            for _svc2, _subs_m2 in _latest_subs2.items():
                _disp2 = _subs_meta2.get(_svc2, {}).get("display", _svc2)
                _color2 = _subs_meta2.get(_svc2, {}).get("color", _company_color(_svc2))
                _already2 = any(
                    _disp2.lower() in _n or _n in _disp2.lower() or _n == _svc2.lower()
                    for _n in _hc_names_lower
                )
                if not _already2:
                    _slabel2 = _subs2_label(_svc2, _subs_m2)
                    _human_companies.append({
                        "name": _disp2,
                        "val": _subs_m2,
                        "mins": None,
                        "revenue": None,
                        "users": f"{_slabel2} subs",
                        "color": _color2,
                        "label": f"{_slabel2} subs",
                    })
except Exception:
    pass

# Rebadge Twitch as Amazon – Twitch (Amazon-owned)
for _c in _human_companies:
    if "twitch" in str(_c.get("name", _c.get("platform", ""))).lower():
        _c["name"] = "Amazon \u2013 Twitch"
        _c["color"] = "#9146FF"
        _c["logo"] = _resolve_logo("Amazon", logos) if logos else ""

# Sanitise NaN / inf AND convert numpy types before JSON serialisation
# Also strip 'logo' key — it's a large base64 blob not used by the bubble chart JS
import math as _math_mod
for _hc_clean in _human_companies:
    _hc_clean.pop("logo", None)
    for _hk, _hv in list(_hc_clean.items()):
        # Convert numpy types to native Python (json.dumps can't handle np.int64/float64)
        if hasattr(_hv, 'item'):  # numpy scalar -> python scalar
            _hc_clean[_hk] = _hv.item()
            _hv = _hc_clean[_hk]
        if isinstance(_hv, float) and (_math_mod.isnan(_hv) or _math_mod.isinf(_hv)):
            _hc_clean[_hk] = None
        elif _hv is not None and not isinstance(_hv, (str, bool, int, float, list, dict)):
            try:
                _hc_clean[_hk] = float(_hv) if _hv == _hv else None
            except (TypeError, ValueError):
                _hc_clean[_hk] = str(_hv)
try:
    _human_json = json.dumps(_human_companies, allow_nan=False, default=str)
except (ValueError, TypeError):
    _human_json = json.dumps([
        {"name": "YouTube", "val": 2500, "mins": 1000, "revenue": 36.1, "users": "2.5B users", "color": "#ff0000", "label": "2.5B users"},
        {"name": "Spotify", "val": 675, "mins": 30, "revenue": 15.7, "users": "675M users", "color": "#1db954", "label": "675M users"},
        {"name": "Netflix", "val": 301, "mins": 120, "revenue": 33.7, "users": "301M subs", "color": "#e50914", "label": "301M subs"},
    ])

# ── THE HUMAN SIDE — Platform Globe (dynamic from Company_subscribers_values) ─
@st.cache_data(ttl=300)
def _load_platform_subscriber_data(excel_path: str, source_stamp: int = 0) -> list:
    """Load latest subscriber counts from Company_subscribers_values sheet."""
    PLATFORM_META = {
        "YouTube":      {"color": "#FF0000", "logo": "YouTube",               "countries": ["USA","CAN","IND","IDN","BRA","NGA","BGD","PAK","ETH","COD","TZA","KEN","GHA","UGA","MOZ","MDG","CMR","CIV","AGO","ZWE","RWA","SDN","SOM","MLI","BFA","NER","TCD","GIN"], "centroid": (38.0, -97.0)},
        "WhatsApp":     {"color": "#25D366", "logo": "WhatsApp",              "countries": ["ZAF","NAM","BWA","MWI","LSO","SWZ","ZMB","NLD","BEL","CHE","PRT","POL","CZE","HUN","SVK","HRV","SRB","BGR","ROU","GRC","UKR","LTU","LVA","EST"], "centroid": (-26.0, 28.0)},
        "Instagram":    {"color": "#C13584", "logo": "Instagram",             "countries": ["TUR","IRN","SAU","ARE","EGY","MAR","DZA","TUN","IRQ","JOR","LBN","KWT","QAT","OMN","LBY","SYR","YEM","BHR"], "centroid": (26.0, 44.0)},
        "Facebook":     {"color": "#0866FF", "logo": "Facebook",              "countries": ["PHL","VNM","THA","MMR","KHM","LAO","NPL","LKA","MEX","GTM","HND","CUB","HTI","PRY","BOL","NIC"], "centroid": (12.8, 121.7)},
        "Spotify":      {"color": "#1DB954", "logo": "Spotify",               "countries": ["SWE","NOR","DNK","FIN","ISL","SGP","MYS","HKG","TWN","JPN","KOR","AUS","NZL","URY","CHL","IRL"], "centroid": (59.3, 18.1)},
        "Netflix":      {"color": "#E50914", "logo": "Netflix",               "countries": ["CRI","PAN","DOM","JAM","BLZ","SLV","PRY","ECU"], "centroid": (9.9, -84.1)},
        "Amazon Prime": {"color": "#FF9900", "logo": "Amazon",                "countries": ["DEU","AUT","CHE","POL","CZE","SVK","HUN","ROU","BGR","HRV"], "centroid": (51.1, 10.4)},
        "Disney+":      {"color": "#113CCF", "logo": "Disney",                "countries": ["FRA","BEL","LUX","NLD","ESP","ITA"], "centroid": (46.2, 2.2)},
        "WBD":          {"color": "#4a90d9", "logo": "Warner Bros. Discovery","countries": ["GBR","IRL"], "centroid": (54.0, -2.0)},
        "Paramount+":   {"color": "#7B2FBE", "logo": "Paramount",             "countries": ["ARG","COL","PER","VEN"], "centroid": (-38.4, -63.6)},
        "Peacock":      {"color": "#9B2335", "logo": "Comcast",               "countries": ["GTM","HND","BLZ","SLV","NIC","CUB","HTI"], "centroid": (15.5, -90.0)},
        "TikTok":       {"color": "#010101", "logo": "TikTok",               "countries": ["CHN","MNG"], "centroid": (35.8, 104.1)},
    }
    if not excel_path:
        return []
    try:
        df = _read_excel_sheet_cached(excel_path, "Company_subscribers_values", source_stamp)
        if df.empty:
            return []
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]
        if "service" not in df.columns or "subscribers" not in df.columns:
            return []
        df["subscribers"] = pd.to_numeric(df["subscribers"], errors="coerce")
        df = df.dropna(subset=["subscribers"])
        latest = {}
        for service, grp in df.groupby("service"):
            grp = grp.copy()
            if "year" in grp.columns:
                grp["year"] = pd.to_numeric(grp["year"], errors="coerce")
                sort_cols = ["year", "quarter"] if "quarter" in grp.columns else ["year"]
                grp = grp.sort_values(sort_cols, ascending=False)
            latest[str(service).strip()] = float(grp.iloc[0]["subscribers"])

        # Auto-group variants into their base platform:
        # "Spotify Premium" → sums into "Spotify"
        # "YouTube Premium" → sums into "YouTube"
        # Rule: if service name starts with another service name + " ", it's a variant.
        # Sort shortest-first so base names are identified before their variants.
        _all_names = sorted(latest.keys(), key=len)
        aggregated: dict = {}
        for service in _all_names:
            base = service
            for candidate in _all_names:
                if candidate != service and service.lower().startswith(candidate.lower() + " "):
                    base = candidate
                    break
            aggregated[base] = aggregated.get(base, 0.0) + latest[service]
        latest = aggregated

        result = []
        for service, subs_millions in latest.items():
            meta = PLATFORM_META.get(service, {
                "color": "#6b7280",
                "logo": service.split()[0] if service else "Unknown",
                "countries": [],
                "centroid": (0, 0),
            })
            result.append({
                "platform": service,
                "subscribers_m": subs_millions,
                "subscribers_label": (
                    f"{subs_millions/1000:.1f}B" if subs_millions >= 1000
                    else f"{subs_millions:.0f}M"
                ),
                "color": meta["color"],
                "logo_name": meta.get("logo", service),
                "countries": meta.get("countries", []),
                "centroid": meta.get("centroid", (0, 0)),
            })
        result.sort(key=lambda x: -x["subscribers_m"])
        return result
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _build_timeline_data(excel_path: str, source_stamp: int = 0) -> dict:
    """Build per-year subscriber counts for globe timeline animation.

    Returns { "2015": {"YouTube": 800, "Facebook": 1100, ...}, "2016": {...}, ... }
    Values are in millions.
    """
    if not excel_path:
        return {}
    try:
        df = _read_excel_sheet_cached(excel_path, "Company_subscribers_values", source_stamp)
        if df.empty:
            return {}
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]
        if "service" not in df.columns or "subscribers" not in df.columns or "year" not in df.columns:
            return {}
        df["subscribers"] = pd.to_numeric(df["subscribers"], errors="coerce")
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df = df.dropna(subset=["subscribers", "year"])
        df["year"] = df["year"].astype(int)
        if "quarter" in df.columns:
            df["quarter"] = pd.to_numeric(df["quarter"], errors="coerce").fillna(0).astype(int)
        result = {}
        for year in sorted(df["year"].unique()):
            year_df = df[df["year"] == year]
            year_data = {}
            for service, grp in year_df.groupby("service"):
                grp = grp.copy()
                if "quarter" in grp.columns:
                    grp = grp.sort_values("quarter", ascending=False)
                year_data[str(service).strip()] = float(grp.iloc[0]["subscribers"])
            result[str(year)] = year_data
        return result
    except Exception:
        return {}


try:
    _source_stamp_pg = int(getattr(data_processor, "source_stamp", 0) or 0) if "data_processor" in dir() and data_processor else 0
except Exception:
    _source_stamp_pg = 0
try:
    _platform_data = _load_platform_subscriber_data(
        str(excel_path) if "excel_path" in dir() and excel_path else "",
        _source_stamp_pg,
    )
except Exception:
    _platform_data = []
try:
    _timeline_data = _build_timeline_data(
        str(excel_path) if "excel_path" in dir() and excel_path else "",
        _source_stamp_pg,
    )
except Exception:
    _timeline_data = {}

# Fallback to hardcoded data if sheet unavailable
if not _platform_data:
    _platform_data = [
        {"platform": "YouTube",      "subscribers_m": 2500, "subscribers_label": "2.5B", "color": "#FF0000", "logo_name": "YouTube",               "countries": ["USA","CAN","IND","IDN","BRA","NGA","BGD","PAK","ETH","COD","TZA","KEN","GHA","UGA","MOZ","MDG","CMR","CIV","AGO","ZWE","RWA","SDN","SOM","MLI","BFA","NER","TCD","GIN"], "centroid": (38.0,-97.0)},
        {"platform": "WhatsApp",     "subscribers_m": 2000, "subscribers_label": "2.0B", "color": "#25D366", "logo_name": "WhatsApp",              "countries": ["ZAF","NAM","BWA","MWI","LSO","SWZ","ZMB","NLD","BEL","CHE","PRT","POL","CZE","HUN","SVK","HRV","SRB","BGR","ROU","GRC","UKR","LTU","LVA","EST"], "centroid": (-26.0,28.0)},
        {"platform": "Instagram",    "subscribers_m": 2000, "subscribers_label": "2.0B", "color": "#C13584", "logo_name": "Instagram",             "countries": ["TUR","IRN","SAU","ARE","EGY","MAR","DZA","TUN","IRQ","JOR","LBN","KWT","QAT","OMN","LBY","SYR","YEM","BHR"], "centroid": (26.0,44.0)},
        {"platform": "Facebook",     "subscribers_m": 2100, "subscribers_label": "2.1B", "color": "#0866FF", "logo_name": "Facebook",              "countries": ["PHL","VNM","THA","MMR","KHM","LAO","NPL","LKA","MEX","GTM","HND","CUB","HTI","PRY","BOL","NIC"], "centroid": (12.8,121.7)},
        {"platform": "Spotify",      "subscribers_m": 675,  "subscribers_label": "675M", "color": "#1DB954", "logo_name": "Spotify",               "countries": ["SWE","NOR","DNK","FIN","ISL","SGP","MYS","HKG","TWN","JPN","KOR","AUS","NZL","URY","CHL","IRL"], "centroid": (59.3,18.1)},
        {"platform": "Netflix",      "subscribers_m": 301,  "subscribers_label": "301M", "color": "#E50914", "logo_name": "Netflix",               "countries": ["CRI","PAN","DOM","JAM","BLZ","SLV","PRY","ECU"], "centroid": (9.9,-84.1)},
        {"platform": "Amazon Prime", "subscribers_m": 200,  "subscribers_label": "200M", "color": "#FF9900", "logo_name": "Amazon",                "countries": ["DEU","AUT","CHE","POL","CZE","SVK","HUN","ROU","BGR","HRV"], "centroid": (51.1,10.4)},
        {"platform": "Disney+",      "subscribers_m": 174,  "subscribers_label": "174M", "color": "#113CCF", "logo_name": "Disney",                "countries": ["FRA","BEL","LUX","NLD","ESP","ITA"], "centroid": (46.2,2.2)},
        {"platform": "WBD",          "subscribers_m": 116,  "subscribers_label": "116M", "color": "#4a90d9", "logo_name": "Warner Bros. Discovery","countries": ["GBR","IRL"], "centroid": (54.0,-2.0)},
        {"platform": "Paramount+",   "subscribers_m": 77,   "subscribers_label": "77M",  "color": "#7B2FBE", "logo_name": "Paramount",             "countries": ["ARG","COL","PER","VEN"], "centroid": (-38.4,-63.6)},
        {"platform": "Peacock",      "subscribers_m": 36,   "subscribers_label": "36M",  "color": "#9B2335", "logo_name": "Comcast",               "countries": ["GTM","HND","BLZ","SLV","NIC","CUB","HTI"], "centroid": (15.5,-90.0)},
        {"platform": "TikTok",       "subscribers_m": 1500, "subscribers_label": "1.5B", "color": "#010101", "logo_name": "TikTok",               "countries": ["CHN","MNG"], "centroid": (35.8,104.1)},
    ]

# Load logos for all platforms — use original (non-white-overridden) logos for the globe
_platform_logos = {}
for _pd_item in _platform_data:
    try:
        _logo = _resolve_logo(_pd_item["logo_name"], logos_original)
        if _logo:
            _platform_logos[_pd_item["platform"]] = _logo
    except Exception:
        pass

# Build country→platform mapping dynamically
_country_color_map = {}
_country_platform_map = {}
_country_subs_map = {}
for _pd_item in _platform_data:
    for _iso in _pd_item["countries"]:
        if _iso not in _country_color_map:
            _country_color_map[_iso] = _pd_item["color"]
            _country_platform_map[_iso] = _pd_item["platform"]
            _country_subs_map[_iso] = _pd_item["subscribers_label"]

_num_iso_map = _build_numeric_iso_map()

_pg_legend_html = "".join(
    "<div style='display:flex;align-items:center;gap:6px;margin-bottom:4px;'>"
    "<div style='width:10px;height:10px;border-radius:50%;background:" + p["color"] + ";flex-shrink:0;'></div>"
    "<span style='font-size:11px;color:#9ca3af;'>" + p["platform"] + " \u2014 " + p["subscribers_label"] + "</span>"
    "</div>"
    for p in _platform_data if p["countries"]
)

_platform_data_json = json.dumps([{
    "platform": p["platform"],
    "color": p["color"],
    "subscribers_label": p["subscribers_label"],
    "centroid": list(p["centroid"]),
    "logo": _platform_logos.get(p["platform"], ""),
} for p in _platform_data])
_country_color_json = json.dumps(_country_color_map)
_country_platform_json = json.dumps(_country_platform_map)
_country_subs_json = json.dumps(_country_subs_map)
_num2alpha_json = json.dumps(_num_iso_map)
_timeline_json = json.dumps(_timeline_data)

# ISO alpha-3 → English country name (for globe click → Overview drill-down)
_ISO_TO_NAME = {
    "USA": "United States", "GBR": "United Kingdom", "DEU": "Germany", "FRA": "France",
    "JPN": "Japan", "CHN": "China", "IND": "India", "BRA": "Brazil", "CAN": "Canada",
    "AUS": "Australia", "ITA": "Italy", "ESP": "Spain", "KOR": "South Korea",
    "RUS": "Russia", "MEX": "Mexico", "IDN": "Indonesia", "TUR": "Turkey",
    "NLD": "Netherlands", "SAU": "Saudi Arabia", "CHE": "Switzerland", "SWE": "Sweden",
    "POL": "Poland", "BEL": "Belgium", "NOR": "Norway", "AUT": "Austria",
    "ARE": "United Arab Emirates", "THA": "Thailand", "SGP": "Singapore",
    "MYS": "Malaysia", "PHL": "Philippines", "VNM": "Vietnam", "ZAF": "South Africa",
    "EGY": "Egypt", "NGA": "Nigeria", "ARG": "Argentina", "COL": "Colombia",
    "CHL": "Chile", "PER": "Peru", "PRT": "Portugal", "DNK": "Denmark",
    "FIN": "Finland", "IRL": "Ireland", "NZL": "New Zealand", "ISR": "Israel",
    "CZE": "Czech Republic", "ROU": "Romania", "HUN": "Hungary", "GRC": "Greece",
    "PAK": "Pakistan", "BGD": "Bangladesh", "IRN": "Iran", "IRQ": "Iraq",
    "MAR": "Morocco", "DZA": "Algeria", "TUN": "Tunisia", "KEN": "Kenya",
    "GHA": "Ghana", "ETH": "Ethiopia", "TZA": "Tanzania", "UGA": "Uganda",
    "HKG": "Hong Kong", "TWN": "Taiwan", "MMR": "Myanmar", "KHM": "Cambodia",
    "LKA": "Sri Lanka", "NPL": "Nepal", "ECU": "Ecuador", "VEN": "Venezuela",
    "DOM": "Dominican Republic", "GTM": "Guatemala", "CRI": "Costa Rica",
    "PAN": "Panama", "URY": "Uruguay", "PRY": "Paraguay", "BOL": "Bolivia",
    "JAM": "Jamaica", "HND": "Honduras", "SLV": "El Salvador", "NIC": "Nicaragua",
    "BGR": "Bulgaria", "HRV": "Croatia", "SRB": "Serbia", "SVK": "Slovakia",
    "LTU": "Lithuania", "LVA": "Latvia", "EST": "Estonia", "SVN": "Slovenia",
    "UKR": "Ukraine", "BLR": "Belarus", "ISL": "Iceland", "LUX": "Luxembourg",
    "QAT": "Qatar", "KWT": "Kuwait", "OMN": "Oman", "BHR": "Bahrain",
    "JOR": "Jordan", "LBN": "Lebanon", "SYR": "Syria", "YEM": "Yemen",
    "LBY": "Libya", "SDN": "Sudan", "SOM": "Somalia", "CMR": "Cameroon",
    "CIV": "Ivory Coast", "AGO": "Angola", "MOZ": "Mozambique", "MDG": "Madagascar",
    "ZWE": "Zimbabwe", "RWA": "Rwanda", "BWA": "Botswana", "NAM": "Namibia",
    "MWI": "Malawi", "ZMB": "Zambia", "MLI": "Mali", "BFA": "Burkina Faso",
    "NER": "Niger", "TCD": "Chad", "GIN": "Guinea", "SWZ": "Eswatini",
    "LSO": "Lesotho", "BLZ": "Belize", "CUB": "Cuba", "HTI": "Haiti",
    "COD": "Democratic Republic of the Congo", "TEN": "Tencent",
}
_iso_to_name_json = json.dumps(_ISO_TO_NAME)

_platform_globe_html = (
    """<!DOCTYPE html><html><head>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Syne:wght@700;800&display=swap">
<style>
html,body{margin:0;padding:0;background:#020810;overflow:hidden;font-family:'DM Sans',sans-serif;}
#globe-wrap{display:flex;flex-direction:column;width:100%;background:#020810;}
#globe-header{padding:32px 28px 12px;background:#020810;}
.globe-eyebrow{color:#4aaeff;font-family:'DM Sans',sans-serif;font-size:11px;letter-spacing:.28em;text-transform:uppercase;font-weight:700;margin-bottom:10px;}
.globe-title{font-family:'Syne',sans-serif;font-size:clamp(20px,2.4vw,30px);font-weight:800;color:#e6edf3;line-height:1.18;margin:0 0 8px;}
.globe-subtitle{color:#8b949e;font-size:14px;line-height:1.55;margin:0;}
#globe-root{width:100%;height:600px;position:relative;background:#020810;flex-shrink:0;}
#globe-tooltip{position:absolute;display:none;background:rgba(10,14,26,0.95);border:1px solid rgba(99,179,237,0.4);color:#e6edf3;padding:10px 14px;border-radius:8px;font-size:13px;pointer-events:none;z-index:100;max-width:220px;}
#globe-legend{position:absolute;bottom:16px;left:16px;display:flex;flex-direction:column;gap:5px;max-height:220px;overflow:hidden;}
#globe-controls{position:absolute;bottom:16px;right:16px;display:flex;align-items:center;gap:10px;z-index:10;}
#globe-year-label{font-family:'DM Sans',sans-serif;font-size:32px;font-weight:700;color:#e6edf3;line-height:1;letter-spacing:-0.02em;opacity:0.9;}
#globe-play-btn{background:rgba(99,179,237,0.15);border:1px solid rgba(99,179,237,0.35);color:#e6edf3;width:36px;height:36px;border-radius:50%;cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;transition:background 0.2s;}
#globe-play-btn:hover{background:rgba(99,179,237,0.3);}
</style></head><body>
<div id="globe-wrap">
<div id="globe-root">
<div id="globe-tooltip"></div>
<div id="globe-legend">"""
    + _pg_legend_html
    + """</div>
<div id="globe-controls">
  <div id="globe-year-label"></div>
  <button id="globe-play-btn" title="Play timeline">&#9654;</button>
</div>
</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js"></script>
<script>
var countryColors="""
    + _country_color_json
    + """;
var countryPlatform="""
    + _country_platform_json
    + """;
var countrySubs="""
    + _country_subs_json
    + """;
var num2alpha="""
    + _num2alpha_json
    + """;
var isoToName="""
    + _iso_to_name_json
    + """;
var platformData="""
    + _platform_data_json
    + """;
var timelineData="""
    + _timeline_json
    + """;
var root=document.getElementById('globe-root');
var tooltip=document.getElementById('globe-tooltip');
var yearLabel=document.getElementById('globe-year-label');
var playBtn=document.getElementById('globe-play-btn');
var W=root.clientWidth||900;var H=600;
var svg=d3.select('#globe-root').append('svg').attr('width',W).attr('height',H).style('position','absolute').style('top','0').style('left','0');
var projection=d3.geoOrthographic().scale(Math.min(W,H)*0.42).translate([W/2,H/2]).clipAngle(90).rotate([0,-20]);
var path=d3.geoPath().projection(projection);
var defs=svg.append('defs');
var radGrad=defs.append('radialGradient').attr('id','pgGlow').attr('cx','38%').attr('cy','32%').attr('r','65%');
radGrad.append('stop').attr('offset','0%').attr('stop-color','#1a3a5c');
radGrad.append('stop').attr('offset','100%').attr('stop-color','#0d1f35');
var shimGrad=defs.append('radialGradient').attr('id','pgShimmer').attr('cx','35%').attr('cy','28%').attr('r','50%');
shimGrad.append('stop').attr('offset','0%').attr('stop-color','rgba(147,197,253,0.14)');
shimGrad.append('stop').attr('offset','100%').attr('stop-color','rgba(147,197,253,0)');
svg.append('circle').attr('cx',W/2).attr('cy',H/2).attr('r',projection.scale()).attr('fill','url(#pgGlow)').attr('stroke','rgba(99,179,237,0.18)').attr('stroke-width',1.5);
var pgShimmer=svg.append('circle').attr('cx',W/2).attr('cy',H/2).attr('r',projection.scale()).attr('fill','url(#pgShimmer)').attr('pointer-events','none').style('opacity',0.6);
var pgShimUp=true;function animPgShimmer(){var c=parseFloat(pgShimmer.style('opacity'));var n=pgShimUp?c+0.003:c-0.003;if(n>=0.72)pgShimUp=false;if(n<=0.28)pgShimUp=true;pgShimmer.style('opacity',n);requestAnimationFrame(animPgShimmer);}requestAnimationFrame(animPgShimmer);
var gCountries=svg.append('g');
var gLogos=svg.append('g');
defs.append('filter').attr('id','logo-shadow').attr('x','-25%').attr('y','-25%').attr('width','150%').attr('height','150%').append('feDropShadow').attr('dx',0).attr('dy',0).attr('stdDeviation',3).attr('flood-color','rgba(0,0,0,0.25)').attr('flood-opacity',1);
var logoImgs={};
platformData.forEach(function(p){
  if(p.logo){
    var img=new Image();
    img.src='data:image/png;base64,'+p.logo;
    logoImgs[p.platform]=img;
  }
});
function drawLogos(){
  gLogos.selectAll('*').remove();
  platformData.forEach(function(p){
    if(!p.centroid||!p.centroid[0])return;
    var coords=[p.centroid[1],p.centroid[0]];
    var proj=projection(coords);
    if(!proj)return;
    var angle=d3.geoDistance(coords,[-projection.rotate()[0],-projection.rotate()[1]]);
    if(angle>Math.PI/2)return;
    var x=proj[0],y=proj[1],r=18;
    var img=logoImgs[p.platform];
    gLogos.append('circle').attr('cx',x).attr('cy',y).attr('r',r*1.15).attr('fill','rgba(255,255,255,0.92)').attr('filter','url(#logo-shadow)');
    if(img&&img.complete&&img.naturalWidth>0){
      var clipId='clip-'+p.platform.replace(/[^a-z0-9]/gi,'');
      gLogos.append('clipPath').attr('id',clipId).append('circle').attr('cx',x).attr('cy',y).attr('r',r);
      gLogos.append('image').attr('href','data:image/png;base64,'+p.logo).attr('x',x-r).attr('y',y-r).attr('width',r*2).attr('height',r*2).attr('clip-path','url(#'+clipId+')');
    } else {
      gLogos.append('circle').attr('cx',x).attr('cy',y).attr('r',r).attr('fill',p.color).attr('opacity',0.9);
      gLogos.append('text').attr('x',x).attr('y',y).attr('text-anchor','middle').attr('dominant-baseline','central').attr('font-size','13px').attr('font-weight','700').attr('fill','white').text(p.platform[0]);
    }
  });
}
// Timeline state
var timelineYears=Object.keys(timelineData).sort();
var currentYearIdx=timelineYears.length>0?timelineYears.length-1:0;
var timelinePlaying=false;var timelineInterval=null;
function subsLabel(v){return v>=1000?(v/1000).toFixed(1)+'B':Math.round(v)+'M';}
function applyYear(idx){
  if(!timelineYears.length)return;
  var year=timelineYears[idx];
  yearLabel.textContent=year;
  var yd=timelineData[year]||{};
  // Update tooltip subscriber data for this year
  Object.keys(countryPlatform).forEach(function(iso){
    var pl=countryPlatform[iso];
    if(yd[pl]!==undefined){countrySubs[iso]=subsLabel(yd[pl]);}
  });
  // Update legend text
  var items=document.querySelectorAll('#globe-legend span');
  items.forEach(function(el){
    var txt=el.textContent||'';
    var parts=txt.split(' \u2014 ');
    if(parts.length===2){
      var pl=parts[0].trim();
      if(yd[pl]!==undefined){el.textContent=pl+' \u2014 '+subsLabel(yd[pl]);}
    }
  });
}
function stopTimeline(){timelinePlaying=false;if(timelineInterval)clearInterval(timelineInterval);timelineInterval=null;playBtn.innerHTML='&#9654;';}
function startTimeline(){
  if(!timelineYears.length)return;
  timelinePlaying=true;playBtn.innerHTML='&#9646;&#9646;';
  timelineInterval=setInterval(function(){
    currentYearIdx=(currentYearIdx+1)%timelineYears.length;
    applyYear(currentYearIdx);
    if(currentYearIdx===timelineYears.length-1)stopTimeline();
  },900);
}
playBtn.addEventListener('click',function(){
  if(timelinePlaying){stopTimeline();}
  else{
    if(currentYearIdx>=timelineYears.length-1)currentYearIdx=0;
    startTimeline();
  }
});
// Init year label to latest
if(timelineYears.length>0){yearLabel.textContent=timelineYears[timelineYears.length-1];}
fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json').then(function(r){return r.json();}).then(function(world){
  var countries=topojson.feature(world,world.objects.countries).features;
  gCountries.selectAll('path').data(countries).enter().append('path')
    .attr('d',path)
    .attr('fill',function(d){var a=num2alpha[String(d.id)]||'';var c=countryColors[a];return c||'#1a2744';})
    .attr('opacity',function(d){var a=num2alpha[String(d.id)]||'';return countryColors[a]?0.75:1;})
    .attr('stroke','rgba(255,255,255,0.08)').attr('stroke-width',0.4)
    .style('cursor','pointer')
    .on('mousemove',function(event,d){
      var a=num2alpha[String(d.id)]||'';
      var cName=isoToName[a]||'';
      tooltip.style.display='block';
      tooltip.style.left=(event.offsetX+12)+'px';
      tooltip.style.top=(event.offsetY-10)+'px';
      if(countryPlatform[a]){
        tooltip.innerHTML='<strong style="color:'+countryColors[a]+'">'+countryPlatform[a]+'</strong><br>'+countrySubs[a]+' subscribers<br><span style="font-size:11px;color:#93c5fd;opacity:0.8;">Click to explore media data</span>';
      } else if(cName){
        tooltip.innerHTML='<strong>'+cName+'</strong><br><span style="font-size:11px;color:#93c5fd;opacity:0.8;">Click to explore media data</span>';
      } else {
        tooltip.style.display='none';
      }
    })
    .on('mouseleave',function(){tooltip.style.display='none';})
    .on('click',function(event,d){
      if(globeDragged)return;
      var a=num2alpha[String(d.id)]||'';
      var cName=isoToName[a]||'';
      if(!cName)return;
      try{window.open('/Overview?country='+encodeURIComponent(cName),'_blank');}catch(e){}
    });
  drawLogos();
  startRotation();
});
var lon=0;var spinning=true;var animId=null;var lastTime=0;
var isDragging=false;var dragStart=null;var rotateStart=[0,-20];var globeDragged=false;
function rotate(ts){
  if(!spinning)return;
  if(ts-lastTime>16){lon=(lon+0.25)%360;projection.rotate([lon,-20]);gCountries.selectAll('path').attr('d',path);svg.select('path').attr('d',path);drawLogos();lastTime=ts;}
  animId=requestAnimationFrame(rotate);
}
function startRotation(){spinning=true;animId=requestAnimationFrame(rotate);}
root.addEventListener('mousedown',function(e){
  isDragging=true;spinning=false;globeDragged=false;
  if(animId)cancelAnimationFrame(animId);
  dragStart=[e.clientX,e.clientY];
  rotateStart=projection.rotate().slice();
  tooltip.style.display='none';
});
root.addEventListener('mousemove',function(e){
  if(!isDragging||!dragStart)return;
  var dx=e.clientX-dragStart[0];
  var dy=e.clientY-dragStart[1];
  if(Math.sqrt(dx*dx+dy*dy)>5)globeDragged=true;
  var newLon=rotateStart[0]+dx*0.4;
  var newLat=Math.max(-60,Math.min(60,rotateStart[1]-dy*0.4));
  lon=newLon%360;
  projection.rotate([lon,newLat]);
  gCountries.selectAll('path').attr('d',path);
  svg.select('path').attr('d',path);
  drawLogos();
});
root.addEventListener('mouseup',function(){
  isDragging=false;dragStart=null;
  setTimeout(function(){if(!isDragging)startRotation();},2000);
});
root.addEventListener('mouseleave',function(){
  isDragging=false;dragStart=null;
  startRotation();
});
</script></body></html>"""
)
_section("IF PLATFORMS WERE COUNTRIES", "If the world were divided by platform, this is how it would look.", "A billion people. One platform. One color.")
st.markdown("<div data-ae-section='1' style='width:100%;'>", unsafe_allow_html=True)
st.markdown("<div style='display:flex;justify-content:center;width:100%;'>", unsafe_allow_html=True)
st.components.v1.html(_platform_globe_html, height=760, scrolling=False)
st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
_deep_dive("editorial", "Explore platform deep dives")
_separator()

_bubble_logo_aliases = {
    "YouTube": "YouTube",  # uses Youtube_logo.png loaded into logos_original
    "Netflix": "Netflix",
    "Twitch": None,
    "Spotify": "Spotify",
    "Meta \u2013 Facebook": "Facebook",
    "Meta \u2013 Instagram": "Instagram",
    "Disney+ / Hulu / ESPN+": "Disney",
    "Paramount+": "Paramount Global",
    "WBD Max / HBO": "Warner Bros. Discovery",
    "Comcast Peacock": "Comcast",
    "Amazon Prime Video": "Amazon",
}
_bubble_logo_map = {}
for _hc in _human_companies:
    _hname = _hc.get("name", "")
    _logo_key = _bubble_logo_aliases.get(_hname, _hname)
    if _logo_key:
        _b64 = _resolve_logo(_logo_key, logos_original)
        if _b64:
            _bubble_logo_map[_hname] = _b64
try:
    _logos_json_str = json.dumps(_bubble_logo_map, default=str)
except Exception:
    _logos_json_str = "{}"
try:
    _attn_html = _build_attn_html(_ad_json_str, _global_adv_json_str, _human_json, logos_json=_logos_json_str)
except Exception as _attn_err:
    _attn_html = f"<html><body style='background:#0d1117;color:#ff5b1f;padding:40px;font-family:monospace;'><b>Bubble chart build error</b><br>{_attn_err}</body></html>"
_section("ATTENTION ECONOMY", "Who Owns Your Time", "Each bubble = a platform. Size = subscribers or monthly active users.")
st.markdown("<div data-ae-section='1' style='width:100%;'>", unsafe_allow_html=True)
st.components.v1.html(_attn_html, height=580)
st.markdown("</div>", unsafe_allow_html=True)
_deep_dive("editorial", "Deep dive into platforms")
_separator()
# --- Concentration: animated stacked bar 2010→latest ---
_CONC_SEG_ORDER = ["Alphabet", "Meta", "Amazon", "Apple + MSFT",
                   "Search (other)", "Social (other)", "Display (other)", "Video (other)", "Other Digital",
                   "TV (Free + Pay)", "Print", "Radio", "OOH", "Cinema"]
_CONC_SEG_COLORS = {
    # Companies — distinct, vivid
    "Alphabet": "#4285f4", "Meta": "#e040fb", "Amazon": "#ff9900",
    "Apple + MSFT": "#34d399",
    # Digital channels — grey gradient (lightest = biggest)
    "Search (other)": "#6b7280", "Social (other)": "#5b616b",
    "Display (other)": "#4b5058", "Video (other)": "#3b3f46",
    "Other Digital": "#2d3138",
    # Traditional media — darker greys
    "TV (Free + Pay)": "#252830", "Print": "#1e2028",
    "Radio": "#181a20", "OOH": "#131518", "Cinema": "#0e1012",
}
_CONC_DIG_PATTERNS = ["Search", "Social", "Display", "Video", "Digital OOH", "Other Desktop", "Other Mobile"]

_conc_all_years: dict = {}
_conc_anim_start = 2010
for _ay in range(_conc_anim_start, (effective_year or 2024) + 1):
    if _ay not in _global_adv_totals.index:
        continue
    _ay_total = float(_global_adv_totals[_ay])
    if _ay_total <= 0:
        continue
    _ay_ar = _ad_by_year.get(_ay, {})
    _ay_alpha = _safe_float(_ay_ar.get("Alphabet", 0))
    _ay_meta  = _safe_float(_ay_ar.get("Meta", 0))
    _ay_amzn  = _safe_float(_ay_ar.get("Amazon", 0))
    _ay_apple = _safe_float(_ay_ar.get("Apple", 0))
    _ay_msft  = _safe_float(_ay_ar.get("Microsoft", 0))
    _ay_named = _ay_alpha + _ay_meta + _ay_amzn + _ay_apple + _ay_msft
    _ay_df = global_adv_df[global_adv_df["year"] == _ay] if not global_adv_df.empty else pd.DataFrame()
    _ay_by_type = (_ay_df.groupby("metric_type")["value"].sum() / 1_000.0).to_dict() if not _ay_df.empty else {}
    # Granular digital breakdown
    _ay_search_total = sum(_ay_by_type.get(k, 0) for k in ["Search Desktop Worldwide", "Search Mobile Worldwide"])
    _ay_social_total = sum(_ay_by_type.get(k, 0) for k in ["Social Desktop Worldwide", "Social Mobile Worldwide"])
    _ay_display_total = sum(_ay_by_type.get(k, 0) for k in ["Display Desktop Worldwide", "Display Mobile Worldwide"])
    _ay_video_total = sum(_ay_by_type.get(k, 0) for k in ["Video Desktop Worldwide", "Video Mobile Worldwide"])
    _ay_dig_other_raw = sum(_ay_by_type.get(k, 0) for k in ["Other Desktop Worldwide", "Other Mobile Worldwide", "Digital OOH Worldwide"])
    # Subtract named company ad revenue from the appropriate digital categories
    # Alphabet is mostly search, Meta is mostly social, Amazon is mostly display/other
    _ay_search_other = max(0.0, _ay_search_total - _ay_alpha)
    _ay_social_other = max(0.0, _ay_social_total - _ay_meta)
    _ay_display_other = max(0.0, _ay_display_total - _ay_amzn)
    _ay_video_other = _ay_video_total
    _ay_remaining_dig = max(0.0, _ay_dig_other_raw - (_ay_apple + _ay_msft))
    _ay_vals: dict = {
        "Alphabet": _ay_alpha, "Meta": _ay_meta, "Amazon": _ay_amzn,
        "Apple + MSFT": _ay_apple + _ay_msft,
        "Search (other)": _ay_search_other if _ay_search_other > 0.3 else 0.0,
        "Social (other)": _ay_social_other if _ay_social_other > 0.3 else 0.0,
        "Display (other)": _ay_display_other if _ay_display_other > 0.3 else 0.0,
        "Video (other)": _ay_video_other if _ay_video_other > 0.3 else 0.0,
        "Other Digital": _ay_remaining_dig if _ay_remaining_dig > 0.3 else 0.0,
        "TV (Free + Pay)": sum(_ay_by_type.get(k, 0) for k in ["Free TV Worldwide", "Pay TV Worldwide"]),
        "Print":  sum(_ay_by_type.get(k, 0) for k in ["Newspaper Worldwide", "Magazine Worldwide"]),
        "Radio":  _ay_by_type.get("Radio Worldwide", 0.0),
        "OOH":    _ay_by_type.get("Traditional OOH Worldwide", 0.0),
        "Cinema": _ay_by_type.get("Cinema Worldwide", 0.0),
    }
    _conc_all_years[_ay] = {
        "total": round(_ay_total, 1),
        "vals": {c: round(_ay_vals[c], 1) for c in _CONC_SEG_ORDER},
    }

_conc_yr = effective_year
_conc_ad = _ad_by_year.get(_conc_yr, {})
_conc_alpha    = _safe_float(_conc_ad.get("Alphabet", 0))
_conc_meta     = _safe_float(_conc_ad.get("Meta", 0))
_conc_amzn     = _safe_float(_conc_ad.get("Amazon", 0))
_conc_apple    = _safe_float(_conc_ad.get("Apple", 0))
_conc_msft     = _safe_float(_conc_ad.get("Microsoft", 0))
_conc_apple_msft = _conc_apple + _conc_msft
_conc_named    = _conc_alpha + _conc_meta + _conc_amzn + _conc_apple_msft
# Total from Global_Adv_Aggregates (best available whole-market figure)
_conc_total = groupm_b if groupm_b and groupm_b > 0 else (_conc_named * 2.0)

# Metric-type breakdown for _conc_yr from global_adv_df (already loaded)
_conc_by_type: dict = {}
if not global_adv_df.empty:
    _cyr_df = global_adv_df[global_adv_df["year"] == _conc_yr]
    _conc_by_type = (_cyr_df.groupby("metric_type")["value"].sum() / 1_000.0).to_dict()

# Digital residual = all digital metric-types minus named-company revenues
_digital_keys = [k for k in _conc_by_type if any(
    x in k for x in ["Search", "Social", "Display", "Video", "Digital OOH", "Other Desktop", "Other Mobile"]
)]
_digital_total = sum(_conc_by_type[k] for k in _digital_keys)
_digital_other = max(0.0, _digital_total - _conc_named)

# Non-digital categories
_trad_cats = [
    ("TV (Free + Pay)", ["Free TV Worldwide", "Pay TV Worldwide"],        "#444444"),
    ("Print",           ["Newspaper Worldwide", "Magazine Worldwide"],    "#333333"),
    ("Radio",           ["Radio Worldwide"],                              "#282828"),
    ("OOH",             ["Traditional OOH Worldwide"],                    "#1e1e1e"),
    ("Cinema",          ["Cinema Worldwide"],                             "#161616"),
]

_conc_top_share = (_conc_named / _conc_total * 100) if _conc_total > 0 else 0
_conc_all_years_json = json.dumps(_conc_all_years)
_conc_seg_colors_json = json.dumps(_CONC_SEG_COLORS)
_conc_seg_order_json = json.dumps(_CONC_SEG_ORDER)

_section("THE CONCENTRATION", "Most of it went to very few hands.", f"Of ${_conc_total:.0f}B spent globally on advertising in {_conc_yr}, 4 companies captured {_conc_top_share:.0f}% of the market.")
st.markdown("<div data-ae-section='1' style='width:100%;'>", unsafe_allow_html=True)
st.components.v1.html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500;700&display=swap');
html,body{{margin:0;padding:0;background:#020810;}}
*{{box-sizing:border-box;}}
#conc-root{{background:transparent;padding:32px 24px 40px;font-family:'DM Sans',sans-serif;color:#e6edf3;}}
.wc-label{{color:#4aaeff;font-family:'Syne',sans-serif;font-size:11px;letter-spacing:.28em;text-transform:uppercase;font-weight:700;margin-bottom:10px;}}
.wc-headline{{font-family:'Syne',sans-serif;font-size:28px;font-weight:800;color:#e6edf3;margin:0 0 6px;}}
.wc-sub{{color:#8b949e;font-size:14px;margin:0 0 20px;}}
/* controls */
.conc-controls{{display:flex;align-items:center;gap:14px;margin-bottom:14px;}}
.conc-year{{font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:#e6edf3;min-width:52px;}}
.conc-total{{font-size:13px;color:#8b949e;}}
.conc-total span{{color:#c9d1d9;font-weight:600;}}
#conc-play{{background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.18);color:#e6edf3;
  border-radius:6px;padding:5px 16px;font-size:12px;font-weight:600;cursor:pointer;letter-spacing:.05em;}}
#conc-play:hover{{background:rgba(255,255,255,0.14);}}
#conc-slider{{flex:1;accent-color:#4aaeff;cursor:pointer;height:3px;}}
/* above-bar callout area */
#conc-above{{position:relative;width:100%;height:0;overflow:visible;}}
.cab{{position:absolute;border-radius:6px;padding:6px 10px;white-space:nowrap;pointer-events:none;
  box-shadow:0 2px 8px rgba(0,0,0,.5);transform:translateX(-50%);transition:left 0.5s ease,opacity 0.3s;}}
.cab-cat{{font-size:9px;font-weight:700;color:rgba(255,255,255,.82);text-transform:uppercase;letter-spacing:.04em;}}
.cab-amt{{font-size:13px;font-weight:800;color:#fff;margin-top:1px;}}
.cab-pct{{font-size:10px;color:rgba(255,255,255,.68);margin-top:1px;}}
.cab-line{{position:absolute;bottom:0;width:1px;opacity:0.5;transform:translateX(-50%);}}
/* bar */
.bar-container{{width:100%;height:130px;display:flex;position:relative;z-index:2;
  border-radius:8px;overflow:hidden;border:1px solid #2a2a2a;}}
.bar-segment{{height:100%;position:relative;border-right:1px solid rgba(255,255,255,0.12);opacity:0.88;
  flex-shrink:0;overflow:hidden;transition:width 0.7s cubic-bezier(.4,0,.2,1);}}
.bar-segment:first-child{{border-radius:8px 0 0 8px;}}
.bar-segment:last-child{{border-right:none;border-radius:0 8px 8px 0;}}
.bar-segment:hover{{filter:brightness(1.12);}}
.seg-label{{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;
  padding:0 11px;pointer-events:none;overflow:hidden;}}
.seg-label-cat{{font-size:9px;font-weight:700;color:rgba(255,255,255,.82);text-transform:uppercase;
  letter-spacing:.05em;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.seg-label-amt{{font-size:14px;font-weight:800;color:#fff;line-height:1.25;margin-top:2px;white-space:nowrap;}}
.seg-label-pct{{font-size:10px;color:rgba(255,255,255,.68);line-height:1.2;margin-top:1px;white-space:nowrap;}}
/* mini label for tight segments (2-5.5%) */
.seg-label-mini{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  padding:0 4px;pointer-events:none;overflow:hidden;}}
.seg-label-mini-amt{{font-size:10px;font-weight:800;color:#fff;white-space:nowrap;
  writing-mode:vertical-rl;transform:rotate(180deg);}}
</style>
<div id="conc-root">
  <div class="wc-sub">Of <span id="conc-sub-total">${_conc_total:.0f}B</span> spent globally on advertising in <span id="conc-sub-yr">{_conc_yr}</span>, 4 companies captured <span id="conc-sub-pct">{_conc_top_share:.0f}%</span> of the market.</div>
  <div class="conc-controls">
    <button id="conc-play">&#9654; Play</button>
    <span class="conc-year" id="conc-yr-label">{_conc_yr}</span>
    <input type="range" id="conc-slider" min="0" value="0" />
    <span class="conc-total">Total: <span id="conc-total-label">${_conc_total:.0f}B</span></span>
  </div>
  <div id="conc-above"></div>
  <div class="bar-container" id="conc-bar"></div>
</div>
<script>
const ALL_YEARS = {_conc_all_years_json};
const SEG_COLORS = {_conc_seg_colors_json};
const SEG_ORDER = {_conc_seg_order_json};
const START_YR = {_conc_yr};
const years = Object.keys(ALL_YEARS).map(Number).sort((a,b)=>a-b);

const slider = document.getElementById('conc-slider');
const playBtn = document.getElementById('conc-play');
const yrLabel = document.getElementById('conc-yr-label');
const totalLabel = document.getElementById('conc-total-label');
const subTotal = document.getElementById('conc-sub-total');
const subYr = document.getElementById('conc-sub-yr');
const subPct = document.getElementById('conc-sub-pct');
const barEl = document.getElementById('conc-bar');
const aboveEl = document.getElementById('conc-above');

slider.max = years.length - 1;
let currentIdx = Math.max(0, years.indexOf(START_YR));
slider.value = currentIdx;

function fmtAmt(b) {{ return '$' + (b >= 1000 ? (b/1000).toFixed(1)+'T' : Math.round(b)+'B'); }}
function fmtPct(p) {{ return p.toFixed(1)+'%'; }}

/* Create one segment div per category (fixed order) */
const segEls = {{}};
SEG_ORDER.forEach(cat => {{
  const s = document.createElement('div');
  s.className = 'bar-segment';
  s.style.background = SEG_COLORS[cat] || '#333';
  s.style.width = '0%';
  s.dataset.cat = cat;
  barEl.appendChild(s);
  segEls[cat] = s;
}});

function updateYear(idx) {{
  currentIdx = Math.max(0, Math.min(years.length - 1, idx));
  slider.value = currentIdx;
  const yr = years[currentIdx];
  const data = ALL_YEARS[yr];
  if (!data) return;
  yrLabel.textContent = yr;
  totalLabel.textContent = fmtAmt(data.total);
  subTotal.textContent = fmtAmt(data.total);
  subYr.textContent = yr;

  const total = data.total;
  const vals = data.vals || {{}};
  const named4 = ['Alphabet','Meta','Amazon','Apple + MSFT'];
  const namedSum = named4.reduce((s,c) => s + (vals[c]||0), 0);
  subPct.textContent = total > 0 ? (namedSum/total*100).toFixed(0)+'%' : '—';

  /* Update bar widths */
  SEG_ORDER.forEach(cat => {{
    const v = vals[cat] || 0;
    const pct = total > 0 ? v / total * 100 : 0;
    const seg = segEls[cat];
    seg.style.width = pct + '%';
    /* Clear previous label */
    seg.innerHTML = '';
    if (pct <= 0) return;
    if (pct >= 8.0) {{
      const lbl = document.createElement('div'); lbl.className = 'seg-label';
      const c = document.createElement('div'); c.className = 'seg-label-cat'; c.textContent = cat;
      const a = document.createElement('div'); a.className = 'seg-label-amt'; a.textContent = fmtAmt(v);
      const p = document.createElement('div'); p.className = 'seg-label-pct'; p.textContent = fmtPct(pct);
      lbl.appendChild(c); lbl.appendChild(a); lbl.appendChild(p);
      seg.appendChild(lbl);
    }}
    /* Segments < 8% get above-bar callouts below */
  }});

  /* Above-bar callouts for narrow segments (< 8% of total) to avoid clipping */
  aboveEl.innerHTML = '';
  let aboveH = 0;
  const smallSegs = SEG_ORDER.map(cat => {{
    const v = vals[cat] || 0;
    const pct = total > 0 ? v / total * 100 : 0;
    return {{cat, v, pct}};
  }}).filter(x => x.pct > 0 && x.pct < 8.0);

  if (smallSegs.length > 0) {{
    aboveH = 90;
    aboveEl.style.height = aboveH + 'px';
    /* compute cumulative positions */
    let cum = 0;
    const positions = {{}};
    SEG_ORDER.forEach(cat => {{
      const v = vals[cat] || 0;
      const pct = total > 0 ? v / total * 100 : 0;
      positions[cat] = cum + pct / 2;
      cum += pct;
    }});
    smallSegs.forEach(item => {{
      const cx = positions[item.cat] / 100;
      const line = document.createElement('div'); line.className = 'cab-line';
      line.style.left = (cx*100)+'%'; line.style.height = aboveH+'px';
      line.style.background = SEG_COLORS[item.cat];
      aboveEl.appendChild(line);
      const card = document.createElement('div'); card.className = 'cab';
      card.style.background = SEG_COLORS[item.cat];
      card.style.bottom = '8px'; card.style.left = (cx*100)+'%';
      const cc = document.createElement('div'); cc.className = 'cab-cat'; cc.textContent = item.cat;
      const ca = document.createElement('div'); ca.className = 'cab-amt'; ca.textContent = fmtAmt(item.v);
      const cp = document.createElement('div'); cp.className = 'cab-pct'; cp.textContent = fmtPct(item.pct);
      card.appendChild(cc); card.appendChild(ca); card.appendChild(cp);
      aboveEl.appendChild(card);
    }});
  }} else {{
    aboveEl.style.height = '0px';
  }}
}}

/* Animation */
let timer = null;
let playing = false;
function tick() {{
  if (currentIdx >= years.length - 1) {{ stopPlay(); return; }}
  updateYear(currentIdx + 1);
}}
function startPlay() {{
  playing = true; playBtn.textContent = '⏸ Pause';
  if (currentIdx >= years.length - 1) updateYear(0);
  timer = setInterval(tick, 1100);
}}
function stopPlay() {{
  playing = false; playBtn.textContent = '▶ Play';
  clearInterval(timer); timer = null;
}}
playBtn.addEventListener('click', () => playing ? stopPlay() : startPlay());
slider.addEventListener('input', () => {{ stopPlay(); updateYear(Number(slider.value)); }});

updateYear(currentIdx);
</script>
""", height=560)
st.markdown("</div>", unsafe_allow_html=True)
_deep_dive("earnings", "Explore company financials")
_separator()

# Beat 6 — M2 vs ad spend (animated)
try:
    _m2_desc_base = int(_global_adv_totals.index.min()) if not _global_adv_totals.empty else 1999
    _m2_desc_end = int(_global_adv_totals.index.max()) if not _global_adv_totals.empty else effective_year
    _m2_desc_years = _m2_desc_end - _m2_desc_base
    # Compute correlation between M2 annual and ad spend over common years
    if not m2_monthly_df.empty and not _global_adv_totals.empty:
        _m2_annual = m2_monthly_df.copy()
        _m2_annual["year"] = pd.to_datetime(_m2_annual["date"]).dt.year
        _m2_annual = _m2_annual.groupby("year")["m2_value"].mean()
        _common = _m2_annual.index.intersection(_global_adv_totals.index)
        if len(_common) >= 5:
            import numpy as _np
            _corr = _np.corrcoef(_m2_annual[_common].values, _global_adv_totals[_common].values)[0, 1]
            _m2_body = (
                f"Both lines indexed to {_m2_desc_base} = 100. "
                f"M2 monthly granularity over {_m2_desc_years} years. "
                f"Pearson correlation with ad spend: {_corr:.2f} — "
                + ("structurally tight." if _corr > 0.9 else "moderately correlated." if _corr > 0.7 else "evolving relationship.")
            )
        else:
            _m2_body = f"Both lines indexed to {_m2_desc_base} = 100. M2 monthly granularity over {_m2_desc_years} years."
    else:
        _m2_body = "Both lines indexed to first common year = 100. M2 shown at monthly granularity."
except Exception:
    _m2_body = "Both lines indexed to first common year = 100. M2 shown at monthly granularity."

_section(
    "The Money Printer",
    "When liquidity expands, ad markets follow.",
    _m2_body
)
try:
    # Determine first year with ad data
    _m2_anim_first_ad_year = int(_global_adv_totals.index.min()) if not _global_adv_totals.empty else 1999
    # Prepare M2 monthly, scoped from first ad year
    _m2_monthly_scoped = pd.DataFrame()
    if not m2_monthly_df.empty:
        _m2_ms = m2_monthly_df.copy()
        _m2_ms["year"] = _m2_ms["date"].dt.year
        _m2_ms = _m2_ms[_m2_ms["year"] >= _m2_anim_first_ad_year].sort_values("date")
        if not _m2_ms.empty:
            _m2_monthly_scoped = _m2_ms
    # Prepare ad spend yearly, scoped
    _ad_yearly_scoped = pd.DataFrame()
    if not _global_adv_totals.empty:
        _gm = _global_adv_totals.reset_index()
        _gm.columns = ["year", "ad_total"]
        _gm = _gm[_gm["year"] >= _m2_anim_first_ad_year].sort_values("year")
        if not _gm.empty:
            _ad_yearly_scoped = _gm

    if _m2_monthly_scoped.empty or _ad_yearly_scoped.empty:
        st.info("M2 vs Ad Spend chart unavailable.")
    else:
        # Index both to the first common year = 100
        _base_yr = max(_m2_anim_first_ad_year, int(_ad_yearly_scoped["year"].min()))
        _base_m2_rows = _m2_monthly_scoped[_m2_monthly_scoped["year"] == _base_yr]
        _base_m2_val = float(_base_m2_rows["m2_value"].mean()) if not _base_m2_rows.empty else 1.0
        _base_ad_val = float(_ad_yearly_scoped[_ad_yearly_scoped["year"] == _base_yr]["ad_total"].iloc[0]) if (_ad_yearly_scoped["year"] == _base_yr).any() else 1.0

        if _base_m2_val <= 0 or _base_ad_val <= 0:
            st.info("M2 vs Ad Spend chart unavailable.")
        else:
            # Build JSON arrays for JS
            _m2_points = []
            for _, row in _m2_monthly_scoped.iterrows():
                _m2_points.append({
                    "d": row["date"].strftime("%Y-%m"),
                    "v": round(float(row["m2_value"]) / _base_m2_val * 100, 1),
                    "y": int(row["year"]),
                })
            _ad_points = []
            for _, row in _ad_yearly_scoped.iterrows():
                _ad_points.append({
                    "y": int(row["year"]),
                    "v": round(float(row["ad_total"]) / _base_ad_val * 100, 1),
                })
            import json as _json
            _m2_json = _json.dumps(_m2_points)
            _ad_json = _json.dumps(_ad_points)

            _m2_anim_html = """
<div id="m2-chart-wrap" style="position:relative;width:100%;height:420px;background:transparent;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
  <canvas id="m2Canvas" style="width:100%;height:100%;"></canvas>
  <div id="m2Tooltip" style="position:absolute;display:none;background:rgba(13,17,23,0.92);color:#e6edf3;padding:8px 12px;border-radius:8px;font-size:12px;pointer-events:none;border:1px solid rgba(255,255,255,0.1);backdrop-filter:blur(8px);z-index:10;"></div>
  <div id="m2Year" style="position:absolute;top:12px;right:16px;font-size:40px;font-weight:800;color:rgba(255,255,255,0.08);pointer-events:none;"></div>
  <div id="m2Legend" style="position:absolute;bottom:8px;left:50%;transform:translateX(-50%);display:flex;gap:24px;font-size:12px;color:#aaa;">
    <span><span style="display:inline-block;width:12px;height:3px;background:#3b82f6;border-radius:2px;margin-right:6px;vertical-align:middle;"></span>M2 Money Supply (monthly)</span>
    <span><span style="display:inline-block;width:10px;height:10px;background:#ff9900;border-radius:50%;margin-right:6px;vertical-align:middle;"></span>Global Ad Spend (yearly)</span>
  </div>
</div>
<script>
(function(){
var m2Data = """ + _m2_json + """;
var adData = """ + _ad_json + """;
var canvas = document.getElementById('m2Canvas');
var wrap = document.getElementById('m2-chart-wrap');
var tooltip = document.getElementById('m2Tooltip');
var yearLabel = document.getElementById('m2Year');
var dpr = window.devicePixelRatio || 1;
function resize(){
  var r = wrap.getBoundingClientRect();
  canvas.width = r.width * dpr;
  canvas.height = r.height * dpr;
  canvas.style.width = r.width + 'px';
  canvas.style.height = r.height + 'px';
}
resize();
var ctx = canvas.getContext('2d');
ctx.scale(dpr, dpr);

var PAD = {l:56, r:56, t:24, b:48};
var W, H;
function dims(){ var r=wrap.getBoundingClientRect(); W=r.width; H=r.height; }
dims();

// Compute ranges
var allVals = m2Data.map(function(p){return p.v;}).concat(adData.map(function(p){return p.v;}));
var minV = Math.min.apply(null, allVals) * 0.95;
var maxV = Math.max.apply(null, allVals) * 1.05;
var minYear = m2Data[0].y;
var maxYear = m2Data[m2Data.length-1].y;
// Total months for x-axis
var totalPts = m2Data.length;

function xPos(i){ return PAD.l + (i / (totalPts-1)) * (W - PAD.l - PAD.r); }
function yPos(v){ return PAD.t + (1 - (v - minV) / (maxV - minV)) * (H - PAD.t - PAD.b); }

// Map ad yearly data to m2 index positions
var adMapped = [];
adData.forEach(function(ad){
  // Find the m2 index closest to Jan of that year
  for(var i=0;i<m2Data.length;i++){
    if(m2Data[i].y === ad.y){ adMapped.push({i:i, y:ad.y, v:ad.v}); break; }
  }
});

// Animation state
var frame = 0;
var speed = 3; // points per frame
var animDone = false;

function drawGrid(){
  ctx.clearRect(0,0,W,H);
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 1;
  // Horizontal grid + labels
  var nGrid = 5;
  ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
  ctx.textAlign = 'right';
  for(var g=0;g<=nGrid;g++){
    var gv = minV + (maxV - minV) * g / nGrid;
    var gy = yPos(gv);
    ctx.beginPath(); ctx.moveTo(PAD.l, gy); ctx.lineTo(W-PAD.r, gy); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.3)';
    ctx.fillText(Math.round(gv), PAD.l - 8, gy + 4);
  }
  // Year labels on x-axis
  ctx.textAlign = 'center';
  ctx.fillStyle = 'rgba(255,255,255,0.3)';
  var prevLabel = -1;
  for(var i=0;i<m2Data.length;i++){
    var yr = m2Data[i].y;
    if(yr !== prevLabel && yr % 5 === 0){
      ctx.fillText(yr, xPos(i), H - PAD.b + 18);
      prevLabel = yr;
    }
  }
  // Axis labels
  ctx.save();
  ctx.fillStyle = 'rgba(255,255,255,0.25)';
  ctx.font = '10px -apple-system,BlinkMacSystemFont,sans-serif';
  ctx.translate(14, H/2);
  ctx.rotate(-Math.PI/2);
  ctx.textAlign = 'center';
  ctx.fillText('Indexed (""" + str(_base_yr) + """ = 100)', 0, 0);
  ctx.restore();
}

// 2020 stimulus highlight
var stimStart = -1, stimEnd = -1;
for(var i=0;i<m2Data.length;i++){
  if(m2Data[i].y === 2020 && stimStart < 0) stimStart = i;
  if(m2Data[i].y === 2021) stimEnd = i;
}

function drawFrame(){
  dims();
  resize();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  drawGrid();

  var show = Math.min(frame, totalPts);

  // 2020 stimulus band
  if(stimStart >= 0 && stimEnd >= 0 && show > stimStart){
    var sx0 = xPos(stimStart), sx1 = xPos(Math.min(stimEnd, show));
    ctx.fillStyle = 'rgba(239,68,68,0.06)';
    ctx.fillRect(sx0, PAD.t, sx1-sx0, H-PAD.t-PAD.b);
    if(show > stimEnd){
      ctx.fillStyle = 'rgba(255,255,255,0.15)';
      ctx.font = '10px -apple-system,BlinkMacSystemFont,sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('2020 stimulus', (sx0+sx1)/2, PAD.t + 16);
    }
  }

  // M2 monthly line (blue)
  if(show > 1){
    ctx.beginPath();
    ctx.moveTo(xPos(0), yPos(m2Data[0].v));
    for(var i=1;i<show;i++){
      ctx.lineTo(xPos(i), yPos(m2Data[i].v));
    }
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.stroke();
    // Glow
    ctx.strokeStyle = 'rgba(59,130,246,0.15)';
    ctx.lineWidth = 8;
    ctx.stroke();
  }

  // Ad spend dots (orange) — appear when animation reaches that year
  for(var a=0;a<adMapped.length;a++){
    if(adMapped[a].i >= show) break;
    var ax = xPos(adMapped[a].i);
    var ay = yPos(adMapped[a].v);
    // Connecting stem
    ctx.beginPath();
    ctx.moveTo(ax, ay - 6);
    ctx.lineTo(ax, ay + 6);
    ctx.strokeStyle = 'rgba(255,153,0,0.3)';
    ctx.lineWidth = 1;
    ctx.stroke();
    // Dot
    ctx.beginPath();
    ctx.arc(ax, ay, 5, 0, Math.PI*2);
    ctx.fillStyle = '#ff9900';
    ctx.fill();
    // Glow
    ctx.beginPath();
    ctx.arc(ax, ay, 8, 0, Math.PI*2);
    ctx.fillStyle = 'rgba(255,153,0,0.15)';
    ctx.fill();
  }

  // Year counter overlay
  if(show > 0 && show <= totalPts){
    yearLabel.textContent = m2Data[Math.min(show-1, totalPts-1)].y;
  }

  if(!animDone){
    frame += speed;
    if(frame >= totalPts){
      frame = totalPts;
      animDone = true;
      // Draw ad spend connecting line when done
      if(adMapped.length > 1){
        ctx.beginPath();
        ctx.moveTo(xPos(adMapped[0].i), yPos(adMapped[0].v));
        for(var a=1;a<adMapped.length;a++){
          ctx.lineTo(xPos(adMapped[a].i), yPos(adMapped[a].v));
        }
        ctx.strokeStyle = 'rgba(255,153,0,0.4)';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4,4]);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
    requestAnimationFrame(drawFrame);
  } else {
    // Final: draw ad connecting line
    if(adMapped.length > 1){
      ctx.beginPath();
      ctx.moveTo(xPos(adMapped[0].i), yPos(adMapped[0].v));
      for(var a=1;a<adMapped.length;a++){
        ctx.lineTo(xPos(adMapped[a].i), yPos(adMapped[a].v));
      }
      ctx.strokeStyle = 'rgba(255,153,0,0.4)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4,4]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }
}

// Tooltip on hover
wrap.addEventListener('mousemove', function(e){
  if(!animDone) return;
  var rect = canvas.getBoundingClientRect();
  var mx = e.clientX - rect.left;
  // Find closest m2 point
  var closest = -1, minDist = Infinity;
  for(var i=0;i<totalPts;i++){
    var d = Math.abs(xPos(i) - mx);
    if(d < minDist){ minDist = d; closest = i; }
  }
  if(closest >= 0 && minDist < 20){
    var pt = m2Data[closest];
    var html = '<b>' + pt.d + '</b><br>M2: ' + pt.v.toFixed(1);
    // Check if there's an ad point at this year
    for(var a=0;a<adMapped.length;a++){
      if(adMapped[a].y === pt.y){
        html += '<br>Ad Spend: ' + adMapped[a].v.toFixed(1);
        break;
      }
    }
    tooltip.innerHTML = html;
    tooltip.style.display = 'block';
    tooltip.style.left = Math.min(mx + 12, W - 140) + 'px';
    tooltip.style.top = (yPos(pt.v) - 40) + 'px';
    // Crosshair
    drawFrame();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.beginPath();
    ctx.moveTo(xPos(closest), PAD.t);
    ctx.lineTo(xPos(closest), H - PAD.b);
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3,3]);
    ctx.stroke();
    ctx.setLineDash([]);
  } else {
    tooltip.style.display = 'none';
  }
});
wrap.addEventListener('mouseleave', function(){ tooltip.style.display = 'none'; });

// Replay on click
wrap.addEventListener('click', function(){
  if(animDone){ frame = 0; animDone = false; requestAnimationFrame(drawFrame); }
});

// Start animation
requestAnimationFrame(drawFrame);
})();
</script>
"""
            st.markdown("<div data-ae-section='1' style='width:100%;'>", unsafe_allow_html=True)
            st.components.v1.html(_m2_anim_html, height=440, scrolling=False)
            st.caption("Both M2 money supply and global ad spend indexed to " + str(_base_yr) + " = 100. M2 at monthly granularity. Click to replay animation.")
            st.markdown("</div>", unsafe_allow_html=True)
except Exception as _m2_exc:
    logger.warning("M2 animated chart error: %s", _m2_exc)
    st.info("M2 vs Ad Spend chart unavailable.")
_deep_dive("overview", "Explore macro economics data")
_separator()

# Beat 7 — Structural shift
try:
    if global_adv_df.empty:
        _section("The Structural Shift", "The ad market didn't just grow. It transformed.",
                 "Traditional channels fade while search and retail media take share.")
        st.info("Structural shift chart unavailable.")
    else:
        _channel_map = {
            "TV": ["Free TV", "Pay TV"],
            "Streaming / Video": ["Video Desktop", "Video Mobile"],
            "Search": ["Search Desktop", "Search Mobile"],
            "Social": ["Social Desktop", "Social Mobile"],
            "Display": ["Display Desktop", "Display Mobile"],
            "OOH": ["Traditional OOH", "Digital OOH"],
            "Print": ["Magazine", "Newspaper"],
            "Radio": ["Radio"],
            "Cinema / Other": ["Cinema", "Other Desktop", "Other Mobile"],
        }
        _channel_colors = {
            "TV": "#4472c4",
            "Streaming / Video": "#00bcd4",
            "Search": "#ff9900",
            "Social": "#ffd600",
            "Display": "#e57373",
            "OOH": "#888888",
            "Print": "#a5a5a5",
            "Radio": "#9c27b0",
            "Cinema / Other": "#607d8b",
        }
        gdf_agg = global_adv_df[global_adv_df["year"] >= 2010].copy()
        _mt_to_ch = {mt: ch for ch, mts in _channel_map.items() for mt in mts}
        gdf_agg["channel"] = (
            gdf_agg["metric_type"]
            .str.replace(" Worldwide", "", regex=False)
            .str.strip()
            .map(_mt_to_ch)
        )
        gdf_agg = gdf_agg.dropna(subset=["channel"])
        gdf_pivot = (
            gdf_agg.groupby(["year", "channel"])["value"].sum().unstack(fill_value=0) / 1_000.0
        )
        if gdf_pivot.empty:
            _section("The Structural Shift", "The ad market didn't just grow. It transformed.",
                     "Traditional channels fade while search and retail media take share.")
            st.info("Structural shift chart unavailable.")
        else:
            # Auto-compute description from real data
            _ss_latest = max(y for y in gdf_pivot.index if y <= effective_year) if any(y <= effective_year for y in gdf_pivot.index) else int(gdf_pivot.index.max())
            _ss_earliest = int(gdf_pivot.index.min())
            _ss_yr_row = gdf_pivot.loc[_ss_latest] if _ss_latest in gdf_pivot.index else gdf_pivot.iloc[-1]
            _ss_top_ch = _ss_yr_row.idxmax() if not _ss_yr_row.empty else "Search"
            _ss_top_val = float(_ss_yr_row.max())
            _ss_total = float(_ss_yr_row.sum())
            _ss_top_pct = int(_ss_top_val / _ss_total * 100) if _ss_total > 0 else 0
            # TV share then vs now
            _ss_tv_now = float(_ss_yr_row.get("TV", 0)) / _ss_total * 100 if _ss_total > 0 else 0
            _ss_earliest_row = gdf_pivot.loc[_ss_earliest] if _ss_earliest in gdf_pivot.index else gdf_pivot.iloc[0]
            _ss_total_early = float(_ss_earliest_row.sum())
            _ss_tv_then = float(_ss_earliest_row.get("TV", 0)) / _ss_total_early * 100 if _ss_total_early > 0 else 0
            _ss_body = (
                f"{_ss_top_ch} is the largest channel at {_ss_top_pct}% of global ad spend in {_ss_latest}. "
                f"TV's share fell from {_ss_tv_then:.0f}% in {_ss_earliest} to {_ss_tv_now:.0f}% in {_ss_latest}. "
                f"Click to replay animation."
            )
            _section("The Structural Shift", "The ad market didn't just grow. It transformed.", _ss_body)
            import json as _json_ss
            _ss_channels = [ch for ch in _channel_map if ch in gdf_pivot.columns]
            _ss_years = sorted([int(y) for y in gdf_pivot.index.tolist()])
            _ss_series = {}
            for _ch in _ss_channels:
                _ss_series[_ch] = [round(float(gdf_pivot.loc[y, _ch]), 2) if y in gdf_pivot.index else 0 for y in _ss_years]
            _ss_chart_json = _json_ss.dumps({"years": _ss_years, "channels": _ss_channels, "series": _ss_series})
            _ss_colors_json = _json_ss.dumps({ch: _channel_colors[ch] for ch in _ss_channels})

            _ss_anim_html = (
                "<div id='ss-wrap' style='position:relative;width:100%;height:390px;background:rgba(0,0,0,0);cursor:pointer;'>"
                "<canvas id='ss-canvas' style='width:100%;height:100%;display:block;'></canvas>"
                "<div id='ss-year' style='position:absolute;top:16px;right:24px;font:bold 36px Arial;color:rgba(255,255,255,0.13);pointer-events:none;'></div>"
                "<div id='ss-tip' style='display:none;position:absolute;background:rgba(13,17,23,0.93);color:#e6edf3;padding:8px 12px;border-radius:6px;font:12px Arial;pointer-events:none;z-index:9;border:1px solid rgba(255,255,255,0.1);white-space:nowrap;'></div>"
                "<div id='ss-legend' style='position:absolute;bottom:2px;left:50%;transform:translateX(-50%);display:flex;gap:12px;flex-wrap:wrap;justify-content:center;pointer-events:none;'></div>"
                "</div>"
                "<script>(function(){"
                "var data=" + _ss_chart_json + ";"
                "var colors=" + _ss_colors_json + ";"
                "var wrap=document.getElementById('ss-wrap');"
                "var canvas=document.getElementById('ss-canvas');"
                "var yearLabel=document.getElementById('ss-year');"
                "var tooltip=document.getElementById('ss-tip');"
                "var legend=document.getElementById('ss-legend');"
                "var dpr=window.devicePixelRatio||1;"
                "var W,H;"
                "function resize(){"
                "  var r=wrap.getBoundingClientRect();"
                "  W=r.width;H=r.height;"
                "  canvas.width=W*dpr;canvas.height=H*dpr;"
                "  canvas.style.width=W+'px';canvas.style.height=H+'px';"
                "}"
                "resize();"
                "var ctx=canvas.getContext('2d');"
                "var PAD={t:24,r:20,b:50,l:58};"
                "var years=data.years,channels=data.channels,nY=years.length;"
                "var stacked=[];"
                "for(var y=0;y<nY;y++){"
                "  var row=[],cum=0;"
                "  for(var c=0;c<channels.length;c++){"
                "    var v=data.series[channels[c]][y];"
                "    row.push({lo:cum,hi:cum+v,val:v});cum+=v;"
                "  }"
                "  row._total=cum;stacked.push(row);"
                "}"
                "var maxT=0;"
                "for(var y=0;y<nY;y++)maxT=Math.max(maxT,stacked[y]._total);"
                "maxT=Math.ceil(maxT/50)*50;"
                "function xP(i){return PAD.l+i/(nY-1)*(W-PAD.l-PAD.r);}"
                "function yP(v){return PAD.t+(1-v/maxT)*(H-PAD.t-PAD.b);}"
                "var lh='';"
                "for(var c=0;c<channels.length;c++){lh+='<span style=\"display:inline-flex;align-items:center;gap:4px;font:11px Arial;color:#aaa;\"><span style=\"width:10px;height:10px;border-radius:2px;background:'+colors[channels[c]]+'\"></span>'+channels[c]+'</span>';}"
                "legend.innerHTML=lh;"
                "var frame=0,speed=0.07,animDone=false,hoverIdx=-1;"
                "function draw(){"
                "  ctx.setTransform(dpr,0,0,dpr,0,0);"
                "  ctx.clearRect(0,0,W,H);"
                "  var gridStep=maxT<=300?50:100;"
                "  for(var g=0;g<=maxT;g+=gridStep){"
                "    var gy=yP(g);"
                "    ctx.strokeStyle='rgba(255,255,255,0.06)';ctx.lineWidth=0.5;"
                "    ctx.beginPath();ctx.moveTo(PAD.l,gy);ctx.lineTo(W-PAD.r,gy);ctx.stroke();"
                "    ctx.fillStyle='#888';ctx.font='10px Arial';ctx.textAlign='right';"
                "    ctx.fillText('$'+g+'B',PAD.l-6,gy+3);"
                "  }"
                "  ctx.textAlign='center';"
                "  for(var y=0;y<nY;y++){"
                "    if(y%2===0||y===nY-1){ctx.fillStyle='#888';ctx.font='10px Arial';ctx.fillText(years[y],xP(y),H-PAD.b+16);}"
                "  }"
                "  var show=Math.min(Math.floor(frame)+1,nY);"
                "  var t=frame-Math.floor(frame);"
                "  if(show>=nY){show=nY;t=1;}"
                "  for(var c=channels.length-1;c>=0;c--){"
                "    ctx.beginPath();"
                "    for(var y=0;y<show;y++){var x=xP(y),lo=stacked[y][c].lo;if(y===0)ctx.moveTo(x,yP(lo));else ctx.lineTo(x,yP(lo));}"
                "    if(show<nY&&t>0){var p=show-1;ctx.lineTo(xP(p)+t*(xP(show)-xP(p)),yP(stacked[p][c].lo+t*(stacked[show][c].lo-stacked[p][c].lo)));}"
                "    var tpts=[];"
                "    for(var y=0;y<show;y++)tpts.push({x:xP(y),y:yP(stacked[y][c].hi)});"
                "    if(show<nY&&t>0){var p=show-1;tpts.push({x:xP(p)+t*(xP(show)-xP(p)),y:yP(stacked[p][c].hi+t*(stacked[show][c].hi-stacked[p][c].hi))});}"
                "    for(var p=tpts.length-1;p>=0;p--)ctx.lineTo(tpts[p].x,tpts[p].y);"
                "    ctx.closePath();ctx.fillStyle=colors[channels[c]];ctx.globalAlpha=0.85;ctx.fill();ctx.globalAlpha=1;"
                "  }"
                "  if(show>0)yearLabel.textContent=years[Math.min(show-1,nY-1)];"
                "  if(hoverIdx>=0&&animDone){"
                "    ctx.beginPath();ctx.moveTo(xP(hoverIdx),PAD.t);ctx.lineTo(xP(hoverIdx),H-PAD.b);"
                "    ctx.strokeStyle='rgba(255,255,255,0.2)';ctx.lineWidth=1;ctx.setLineDash([3,3]);ctx.stroke();ctx.setLineDash([]);"
                "  }"
                "}"
                "function loop(){"
                "  draw();"
                "  if(!animDone){frame+=speed;if(frame>=nY-1){frame=nY-1;animDone=true;}else requestAnimationFrame(loop);}"
                "}"
                "wrap.addEventListener('mousemove',function(e){"
                "  if(!animDone)return;"
                "  var rect=canvas.getBoundingClientRect(),mx=e.clientX-rect.left;"
                "  var best=-1,bd=Infinity;"
                "  for(var y=0;y<nY;y++){var d=Math.abs(xP(y)-mx);if(d<bd){bd=d;best=y;}}"
                "  if(best>=0&&bd<30){"
                "    hoverIdx=best;draw();"
                "    var html='<b>'+years[best]+'</b><br>';"
                "    for(var c=0;c<channels.length;c++){var v=stacked[best][c].val;if(v>0)html+='<span style=\"color:'+colors[channels[c]]+'\">&#9632;</span> '+channels[c]+': $'+v.toFixed(1)+'B<br>';}"
                "    html+='<b>Total: $'+stacked[best]._total.toFixed(1)+'B</b>';"
                "    tooltip.innerHTML=html;tooltip.style.display='block';"
                "    tooltip.style.left=Math.min(mx+14,W-170)+'px';tooltip.style.top='30px';"
                "  }else{hoverIdx=-1;tooltip.style.display='none';}"
                "});"
                "wrap.addEventListener('mouseleave',function(){hoverIdx=-1;tooltip.style.display='none';draw();});"
                "wrap.addEventListener('click',function(){if(animDone){frame=0;animDone=false;requestAnimationFrame(loop);}});"
                "window.addEventListener('resize',function(){resize();draw();});"
                "requestAnimationFrame(loop);"
                "})();</script>"
            )
            st.markdown("<div data-ae-section='1' style='width:100%;'>", unsafe_allow_html=True)
            st.components.v1.html(_ss_anim_html, height=420, scrolling=False)
            st.caption("Global ad spend by channel category. Hover to inspect by year. Click to replay. Values in $B.")
            st.markdown("</div>", unsafe_allow_html=True)
except Exception:
    st.info("Structural shift chart unavailable.")
_separator()

# Beat 10 — Performance chart
try:
    import plotly.graph_objects as go
    company_ticker_fallback = {
        "Alphabet": "GOOGL",
        "Meta Platforms": "META",
        "Amazon": "AMZN",
        "Apple": "AAPL",
        "Microsoft": "MSFT",
        "Netflix": "NFLX",
        "Disney": "DIS",
        "Comcast": "CMCSA",
        "Spotify": "SPOT",
        "Roku": "ROKU",
        "Warner Bros. Discovery": "WBD",
        "Paramount Global": "PARA",
    }
    if metrics.empty or mcap_col not in metrics.columns:
        st.info("Performance chart unavailable.")
    else:
        min_year = int(metrics["year"].min())
        y_start = max(effective_year - 3, min_year)
        # Filter market feed to start from 1999 so chart is readable
        _mbet_start = pd.Timestamp("1999-01-01")
        _mbet_feed = market_feed_df[market_feed_df["date"] >= _mbet_start].copy() if not market_feed_df.empty else market_feed_df
        start_df = metrics[metrics["year"] == y_start][["company", mcap_col]].rename(columns={mcap_col: "mcap_start"})
        end_df = metrics[metrics["year"] == effective_year][["company", mcap_col]].rename(columns={mcap_col: "mcap_end"})
        perf = start_df.merge(end_df, on="company", how="inner")
        perf["tsr"] = _yoy_vec(perf["mcap_end"], perf["mcap_start"])
        perf = perf.dropna(subset=["tsr"])
        if perf.empty:
            st.info("Performance chart unavailable.")
        else:
            top3 = perf.nlargest(3, "tsr")["company"].tolist()
            if _mbet_feed.empty:
                st.info("Performance chart unavailable.")
            else:
                p_fig = go.Figure()
                # Collect all series for % change calculation
                _mbet_traces = []
                for idx_tag, idx_label, color, dash in [("^GSPC", "S&P 500", "rgba(255,255,255,0.7)", "dash"), ("^IXIC", "Nasdaq", "#ff9900", "dot")]:
                    _tag_col = _mbet_feed["tag"].astype(str).str.upper()
                    _asset_col = _mbet_feed["asset"].astype(str).str.lower()
                    idx_feed = _mbet_feed[_tag_col.isin([idx_tag, idx_tag.lstrip("^")])]
                    if idx_feed.empty:
                        idx_feed = _mbet_feed[_asset_col.str.contains(idx_label.lower(), na=False)]
                    if idx_feed.empty:
                        idx_feed = _mbet_feed[_asset_col.isin([idx_tag.lower(), idx_tag.lstrip("^").lower()])]
                    if idx_feed.empty:
                        continue
                    idx_feed = idx_feed.sort_values("date")
                    base = float(idx_feed.iloc[0]["price"])
                    if base <= 0:
                        continue
                    pct_change = ((idx_feed["price"] - base) / base) * 100.0
                    latest_pct = float(pct_change.iloc[-1])
                    p_fig.add_trace(go.Scatter(
                        x=idx_feed["date"], y=pct_change,
                        name=f"{idx_label} {latest_pct:+,.0f}%",
                        line=dict(color=color, dash=dash, width=1.5, shape="spline"),
                        hovertemplate=f"<b>{idx_label}</b><br>%{{y:+,.1f}}%<extra></extra>",
                    ))
                for company in top3:
                    ticker = company_ticker_fallback.get(company)
                    if not ticker:
                        continue
                    co_feed = _mbet_feed[_mbet_feed["tag"].astype(str).str.upper() == ticker]
                    if co_feed.empty:
                        co_feed = _mbet_feed[_mbet_feed["asset"].astype(str).str.lower().str.contains(company.lower(), na=False)]
                    if co_feed.empty:
                        co_feed = _mbet_feed[_mbet_feed["asset"].astype(str).str.upper() == ticker]
                    if co_feed.empty:
                        continue
                    co_feed = co_feed.sort_values("date")
                    base = float(co_feed.iloc[0]["price"])
                    if base <= 0:
                        continue
                    pct_change = ((co_feed["price"] - base) / base) * 100.0
                    latest_pct = float(pct_change.iloc[-1])
                    p_fig.add_trace(go.Scatter(
                        x=co_feed["date"], y=pct_change,
                        name=f"{company} {latest_pct:+,.0f}%",
                        line=dict(color=_company_color(company), width=2.5, shape="spline"),
                        hovertemplate=f"<b>{company}</b><br>%{{y:+,.1f}}%<extra></extra>",
                    ))
                if not p_fig.data:
                    st.info("Performance chart unavailable.")
                else:
                    best = perf.nlargest(1, "tsr").iloc[0]
                    _mbet_body = (
                        f"{best['company']} was the top compounder: +{best['tsr']:.0f}% market-cap growth "
                        f"from {y_start} to {effective_year}. All lines show % change from 1999 base. "
                        f"S&P 500 and Nasdaq shown as benchmarks."
                    )
                    _section(
                        "The Market Bet",
                        "Starting from the same base, who compounded fastest?",
                        _mbet_body
                    )
                    # Polymarket-style layout
                    p_fig.update_layout(
                        height=400,
                        hovermode="x",
                        margin=dict(l=0, r=0, t=32, b=40),
                        font=dict(color="#ffffff"),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(13,17,23,0.5)",
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                                    bgcolor="rgba(0,0,0,0)",
                                    font=dict(color="#e6edf3", size=11)),
                        hoverlabel=dict(
                            bgcolor="rgba(17,24,39,0.92)",
                            bordercolor="rgba(99,179,237,0.4)",
                            font=dict(color="#ffffff", size=12),
                        ),
                        xaxis=dict(
                            showgrid=False, zeroline=False, showline=False,
                            tickfont=dict(color="#aaaaaa"),
                            showspikes=True, spikemode="across",
                            spikecolor="rgba(148,163,184,0.4)", spikethickness=1,
                            spikedash="solid",
                        ),
                        yaxis=dict(
                            showgrid=True, gridcolor="rgba(48,54,61,0.3)",
                            zeroline=True, zerolinecolor="rgba(148,163,184,0.3)",
                            zerolinewidth=1, showline=False,
                            tickfont=dict(color="#aaaaaa"),
                            ticksuffix="%",
                        ),
                    )
                    st.markdown("<div data-ae-section='1' style='width:100%;'>", unsafe_allow_html=True)
                    st.plotly_chart(p_fig, use_container_width=True, config={"displayModeBar": False})
                    st.markdown("</div>", unsafe_allow_html=True)
except Exception:
    _section("The Market Bet", "Starting from the same base of 100, who compounded fastest?",
             "Top market-cap compounders benchmarked against major indices from 1999.")
    st.info("Performance chart unavailable.")
_deep_dive("stocks", "Explore stock performance")
_separator()

# Beat 11 — Wealth Machine treemap (animated by year)
_section(
    "The Wealth Machine",
    "Market cap, year by year.",
    "Each square = one company. Size = market cap. Watch how dominance shifted over time."
)
try:
    import plotly.graph_objects as go
    _CO_COLORS = {
        "Alphabet": "#4285f4", "Meta Platforms": "#0082fb", "Amazon": "#ff9900",
        "Apple": "#555555", "Microsoft": "#00a4ef", "Netflix": "#e50914",
        "Disney": "#113ccf", "Comcast": "#e11900", "Spotify": "#1db954",
        "Roku": "#6c1f7d", "Warner Bros. Discovery": "#4a90d9",
        "Paramount Global": "#7b2fbe",
    }
    if metrics.empty or mcap_col not in metrics.columns:
        st.info("Market cap history unavailable.")
    else:
        _tm_years = sorted(metrics["year"].dropna().astype(int).unique().tolist())
        _tm_companies = sorted(metrics["company"].dropna().unique().tolist())
        # Build frames for each year
        _tm_frames = []
        # Pre-compute previous year mcap for YoY
        _prev_mcap = {}
        for _yr in _tm_years:
            _yr_df = metrics[metrics["year"] == _yr][["company", mcap_col]].copy()
            _yr_df[mcap_col] = pd.to_numeric(_yr_df[mcap_col], errors="coerce").fillna(0)
            _yr_df = _yr_df[_yr_df[mcap_col] > 0].copy()
            if _yr_df.empty:
                _prev_mcap = {}
                continue
            _yr_df["color"] = _yr_df["company"].map(lambda c: _CO_COLORS.get(c, "#666666"))
            # Build label with YoY change
            def _tm_label(r):
                mcap_b = r[mcap_col] / 1e3
                prev = _prev_mcap.get(r["company"])
                if prev and prev > 0:
                    chg = (r[mcap_col] - prev) / prev * 100
                    chg_str = f"+{chg:.0f}%" if chg >= 0 else f"{chg:.0f}%"
                    return f"<b>{r['company']}</b><br>${mcap_b:.0f}B<br><span style='font-size:10px'>{chg_str} YoY</span>"
                return f"<b>{r['company']}</b><br>${mcap_b:.0f}B"
            _yr_df["label"] = _yr_df.apply(_tm_label, axis=1)
            # Build hover with clean formatting
            def _tm_hover(r):
                mcap_b = r[mcap_col] / 1e3
                prev = _prev_mcap.get(r["company"])
                if prev and prev > 0:
                    chg = (r[mcap_col] - prev) / prev * 100
                    chg_str = f"+{chg:.1f}%" if chg >= 0 else f"{chg:.1f}%"
                    return f"{r['company']}<br>${mcap_b:.1f}B market cap<br>{chg_str} vs prior year"
                return f"{r['company']}<br>${mcap_b:.1f}B market cap"
            _yr_df["hover"] = _yr_df.apply(_tm_hover, axis=1)
            _prev_mcap = dict(zip(_yr_df["company"], _yr_df[mcap_col]))
            _tm_frames.append(go.Frame(
                data=[go.Treemap(
                    ids=_yr_df["company"],
                    labels=_yr_df["label"],
                    parents=[""] * len(_yr_df),
                    values=_yr_df[mcap_col],
                    customdata=_yr_df["hover"],
                    marker=dict(colors=_yr_df["color"].tolist(), line=dict(width=2, color="#020810")),
                    textinfo="label",
                    hovertemplate="%{customdata}<extra></extra>",
                    textfont=dict(family="DM Sans, Inter, sans-serif", size=13, color="white"),
                )],
                name=str(_yr),
                layout=go.Layout(
                    title_text=f"{_yr}",
                    title_font=dict(size=52, color="rgba(255,255,255,0.12)", family="DM Sans, sans-serif"),
                ),
            ))

        if _tm_frames:
            # Initial frame = latest year
            _init_data = _tm_frames[-1].data
            _tm_fig = go.Figure(
                data=list(_init_data),
                frames=_tm_frames,
                layout=go.Layout(
                    height=520,
                    margin=dict(l=0, r=0, t=60, b=80),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="DM Sans, Inter, sans-serif", color="#e6edf3"),
                    title=dict(
                        text=f"{_tm_years[-1]}",
                        font=dict(size=52, color="rgba(255,255,255,0.12)", family="DM Sans, sans-serif"),
                        x=0.98, xanchor="right", y=0.98, yanchor="top",
                    ),
                    updatemenus=[dict(
                        type="buttons", showactive=False,
                        x=0.0, y=-0.05, xanchor="left", yanchor="top",
                        buttons=[
                            dict(label="▶ Play", method="animate",
                                 args=[None, dict(frame=dict(duration=800, redraw=True),
                                                  fromcurrent=True, transition=dict(duration=400, easing="cubic-in-out"))]),
                            dict(label="⏸ Pause", method="animate",
                                 args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                        ],
                        font=dict(color="#e6edf3", size=11),
                        bgcolor="rgba(30,41,59,0.9)", bordercolor="rgba(255,255,255,0.15)",
                    )],
                    sliders=[dict(
                        active=len(_tm_years) - 1,
                        steps=[dict(method="animate", args=[[str(y)],
                               dict(frame=dict(duration=400, redraw=True), mode="immediate",
                                    transition=dict(duration=200))],
                               label=str(y)) for y in _tm_years],
                        x=0.0, y=-0.02, len=1.0, xanchor="left", yanchor="top",
                        currentvalue=dict(prefix="Year: ", font=dict(color="#e6edf3", size=13)),
                        font=dict(color="#8b949e", size=10),
                        bgcolor="rgba(30,41,59,0.5)", bordercolor="rgba(255,255,255,0.1)",
                        activebgcolor="#ff5b1f",
                        tickcolor="rgba(255,255,255,0.2)",
                    )],
                )
            )
            st.markdown("<div data-ae-section='1' style='width:100%;'>", unsafe_allow_html=True)
            st.plotly_chart(_tm_fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)
            _total_latest = metrics[metrics["year"] == _tm_years[-1]][mcap_col].apply(pd.to_numeric, errors="coerce").sum()
            st.caption(f"Combined tracked market cap: ${_total_latest/1e6:.1f}T as of {_tm_years[-1]}. Press Play to animate from {_tm_years[0]}.")
except Exception:
    st.info("Market cap treemap unavailable.")
_deep_dive("earnings", "Explore company financials in depth")
_separator()

# Beat 13 — Live ticker
# ── THE CLOCK — session timer header (in iframe so JS executes) ─────────
st.components.v1.html("""
<style>
html,body{margin:0;padding:0;background:transparent;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}
</style>
<div style="display:flex;align-items:center;justify-content:space-between;">
  <div>
    <div style="font-size:0.7rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px;">THE CLOCK</div>
    <div style="font-size:1.6rem;font-weight:700;color:#f1f5f9;border-left:3px solid #f97316;padding-left:12px;">
      Every second you stay on this page, revenue keeps running.
    </div>
  </div>
  <div style="text-align:right;">
    <div style="font-size:0.65rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:2px;">Time on dashboard</div>
    <div id="ae-session-timer" style="font-size:2rem;font-weight:800;color:#f97316;font-variant-numeric:tabular-nums;letter-spacing:0.05em;">00:00</div>
  </div>
</div>
<script>
(function() {
  var KEY = 'ae_session_start';
  var stored = null;
  try { stored = localStorage.getItem(KEY); } catch(e) {}
  if (!stored) {
    stored = Date.now().toString();
    try { localStorage.setItem(KEY, stored); } catch(e) {}
  }
  var startTime = parseInt(stored, 10);
  // Reset if older than 4 hours
  if (Date.now() - startTime > 4*60*60*1000) {
    startTime = Date.now();
    try { localStorage.setItem(KEY, startTime.toString()); } catch(e) {}
  }
  function tick() {
    var el = document.getElementById('ae-session-timer');
    if (!el) return;
    var s = Math.floor((Date.now() - startTime) / 1000);
    el.textContent = Math.floor(s/60).toString().padStart(2,'0') + ':' + (s%60).toString().padStart(2,'0');
  }
  tick(); setInterval(tick, 1000);
})();
</script>
""", height=90)

try:
    company_ticker_map = {
        "Alphabet": "GOOGL",
        "Meta Platforms": "META",
        "Amazon": "AMZN",
        "Apple": "AAPL",
        "Microsoft": "MSFT",
        "Netflix": "NFLX",
        "Disney": "DIS",
        "Comcast": "CMCSA",
        "Spotify": "SPOT",
        "Roku": "ROKU",
        "Warner Bros. Discovery": "WBD",
        "Paramount Global": "PARA",
    }

    # ── Ad revenue per company (for dual-column clock) ──
    _ad_rev_fallback_b = {
        "Alphabet": 237.0, "Meta Platforms": 160.0, "Amazon": 56.2,
        "Apple": 7.0, "Microsoft": 13.0, "Netflix": 2.2,
        "Disney": 0.0, "Comcast": 0.0, "Spotify": 0.0,
        "Roku": 0.0, "Warner Bros. Discovery": 0.0, "Paramount Global": 0.0,
    }
    # Try live ad_lookup first; fall back to _ad_by_year then hard-coded.
    _clock_ad_annual: dict[str, float] = {}  # company → annual ad revenue USD
    for _ck_co in company_ticker_map:
        ad_info = ad_lookup.get(_ck_co) if 'ad_lookup' in dir() else None
        if ad_info and float(ad_info.get("ad_revenue_musd", 0)) > 0:
            _clock_ad_annual[_ck_co] = float(ad_info["ad_revenue_musd"]) * 1e6
        elif '_ad_by_year' in dir() and _ad_by_year:
            yr_data = _ad_by_year.get(effective_year, _ad_by_year.get(max(_ad_by_year.keys()), {}))
            # _ad_by_year uses short names like "Meta" not "Meta Platforms"
            _short_map = {"Meta Platforms": "Meta", "Warner Bros. Discovery": "Warner Bros Discovery",
                          "Paramount Global": "Paramount"}
            _short = _short_map.get(_ck_co, _ck_co)
            ad_b = yr_data.get(_ck_co, yr_data.get(_short, 0.0))
            _clock_ad_annual[_ck_co] = float(ad_b) * 1e9 if ad_b else 0.0
        else:
            _fb = _ad_rev_fallback_b.get(_ck_co, 0.0)
            _clock_ad_annual[_ck_co] = float(_fb) * 1e9

    ticker_data: list[tuple[str, str, float, float]] = []  # (company, ticker, total_rps, ad_rps)
    total_rps = 0.0
    total_ad_rps = 0.0
    seconds_per_year = 365 * 24 * 3600

    metrics_scope = pd.DataFrame()
    if not metrics.empty and {"company", "year", "revenue"}.issubset(metrics.columns):
        metrics_scope = metrics[metrics["year"] == effective_year].copy()
        if metrics_scope.empty:
            latest_year = int(metrics["year"].max())
            metrics_scope = metrics[metrics["year"] == latest_year].copy()
        if not metrics_scope.empty:
            metrics_scope["company"] = metrics_scope["company"].apply(_normalize_company_name)
            metrics_scope["revenue"] = pd.to_numeric(metrics_scope["revenue"], errors="coerce")
            metrics_scope = metrics_scope.dropna(subset=["company", "revenue"])
            metrics_scope = metrics_scope[metrics_scope["revenue"] > 0].copy()
            revenue_scale = 1_000_000 if metrics_scope["revenue"].median() > 1000 else 1_000_000_000
            metrics_scope = metrics_scope.sort_values("revenue", ascending=False)

            seen_companies: set[str] = set()
            for row in metrics_scope.itertuples(index=False):
                company = _normalize_company_name(getattr(row, "company", ""))
                if not company or company in seen_companies:
                    continue
                seen_companies.add(company)
                annual_revenue_usd = float(getattr(row, "revenue", 0.0) or 0.0) * revenue_scale
                if annual_revenue_usd <= 0:
                    continue
                rps = annual_revenue_usd / seconds_per_year
                ad_annual = _clock_ad_annual.get(company, 0.0)
                ad_rps = ad_annual / seconds_per_year if ad_annual > 0 else 0.0
                total_rps += rps
                total_ad_rps += ad_rps
                ticker_data.append((company, company_ticker_map.get(company, ""), rps, ad_rps))

    # Fallback: use known company-level annual revenue ($B) when metrics sheet unavailable.
    if not ticker_data:
        _clock_fallback = [
            ("Alphabet", "GOOGL", 350.0),
            ("Meta Platforms", "META", 164.0),
            ("Amazon", "AMZN", 638.0),
            ("Apple", "AAPL", 391.0),
            ("Microsoft", "MSFT", 245.0),
            ("Netflix", "NFLX", 39.0),
            ("Disney", "DIS", 91.0),
            ("Comcast", "CMCSA", 122.0),
            ("Spotify", "SPOT", 16.0),
            ("Warner Bros. Discovery", "WBD", 40.0),
            ("Paramount Global", "PARA", 30.0),
        ]
        for _co, _tk, _rev_b in _clock_fallback:
            annual_revenue_usd = _rev_b * 1_000_000_000
            rps = annual_revenue_usd / seconds_per_year
            ad_annual = _clock_ad_annual.get(_co, 0.0)
            ad_rps = ad_annual / seconds_per_year if ad_annual > 0 else 0.0
            total_rps += rps
            total_ad_rps += ad_rps
            ticker_data.append((_co, _tk, rps, ad_rps))

    if not ticker_data:
        st.info("Revenue ticker unavailable.")
    else:
        rows_html = ""
        for company, ticker, rps, ad_rps in ticker_data:
            logo_b64 = _resolve_logo(company, logos)
            logo_html = (
                f"<img src='data:image/png;base64,{logo_b64}' alt='{escape(company)} logo' "
                "style='width:30px;height:30px;object-fit:contain;border-radius:50%;"
                "background:rgba(148,163,184,0.12);border:1px solid rgba(148,163,184,0.26);padding:3px;' />"
                if logo_b64
                else "<span style='width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center;"
                "border-radius:50%;background:rgba(148,163,184,0.16);color:#ffffff;'>•</span>"
            )
            ticker_label = f" · {ticker}" if ticker else ""
            # Ad revenue column: show counter or dash
            if ad_rps > 0:
                ad_col_html = (
                    f"<div style='text-align:right;min-width:180px;'>"
                    f"<div style='font-size:0.6rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.04em;'>Ad Rev</div>"
                    f"<span data-rps='{ad_rps:.6f}' style='color:#f1f5f9;font-family:monospace;font-size:1.1rem;font-weight:800;'>$0</span>"
                    f"</div>"
                )
            else:
                ad_col_html = (
                    f"<div style='text-align:right;min-width:180px;'>"
                    f"<div style='font-size:0.6rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.04em;'>Ad Rev</div>"
                    f"<span style='color:rgba(255,255,255,0.2);font-family:monospace;font-size:1.1rem;font-weight:800;'>—</span>"
                    f"</div>"
                )
            rows_html += (
                "<div style='display:flex;justify-content:space-between;align-items:center;padding:12px 0;"
                "border-bottom:1px solid rgba(255,255,255,0.07);'>"
                "<div style='display:inline-flex;align-items:center;gap:8px;min-width:200px;'>"
                f"{logo_html}<span style='color:#ffffff;font-weight:600;font-size:0.92rem;'>{escape(company)}</span>"
                f"<span style='color:rgba(255,255,255,0.55);font-size:0.75rem;'>{escape(ticker_label)}</span>"
                "</div>"
                "<div style='display:flex;gap:24px;align-items:flex-start;'>"
                f"<div style='text-align:right;min-width:180px;'>"
                f"<div style='font-size:0.6rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.04em;'>Total</div>"
                f"<span data-rps='{rps:.6f}' style='color:#ff5b1f;font-family:monospace;font-size:1.1rem;font-weight:800;'>$0</span>"
                f"</div>"
                f"{ad_col_html}"
                "</div>"
                "</div>"
            )

        # Combined row
        if total_ad_rps > 0:
            combined_ad_html = (
                f"<div style='text-align:right;min-width:180px;'>"
                f"<div style='font-size:0.6rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.04em;'>Ad Rev</div>"
                f"<span data-rps='{total_ad_rps:.6f}' style='color:#f1f5f9;font-family:monospace;font-size:1.2rem;font-weight:800;'>$0</span>"
                f"</div>"
            )
        else:
            combined_ad_html = "<div style='min-width:180px;'></div>"

        rows_html += (
            "<div style='display:flex;justify-content:space-between;align-items:center;padding:14px 0 0;'>"
            "<span style='color:rgba(255,255,255,0.45);font-size:0.88rem;'>Combined</span>"
            "<div style='display:flex;gap:24px;align-items:flex-start;'>"
            f"<div style='text-align:right;min-width:180px;'>"
            f"<div style='font-size:0.6rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.04em;'>Total</div>"
            f"<span data-rps='{total_rps:.6f}' style='color:white;font-family:monospace;font-size:1.2rem;font-weight:800;'>$0</span>"
            f"</div>"
            f"{combined_ad_html}"
            "</div>"
            "</div>"
        )

        component_height = int(min(960, max(280, 130 + len(ticker_data) * 58)))
        st.components.v1.html(
            f"""
            <style>
              html, body {{
                margin: 0; padding: 0; background: #020810;
                color: #e6edf3; overflow: hidden; border: none; outline: none;
              }}
            </style>
            <div style="background:#020810;padding:20px 18px;border-radius:12px;font-family:sans-serif;">
              {rows_html}
              <div style="color:rgba(255,255,255,0.3);font-size:0.72rem;margin-top:14px;">
                Based on {effective_year} annual revenue ÷ seconds per year. Updates every 120ms since you opened this page.
              </div>
            </div>
            <script>
              (function() {{
                var SESSION_KEY = 'ae_clock_start_ts';
                var SESSION_MAX_AGE_MS = 4 * 60 * 60 * 1000;
                var _startTs;
                try {{
                    var stored = localStorage.getItem(SESSION_KEY);
                    if (stored) {{
                        var storedTs = parseInt(stored, 10);
                        if (Date.now() - storedTs < SESSION_MAX_AGE_MS) {{ _startTs = storedTs; }}
                    }}
                }} catch(e) {{}}
                if (!_startTs) {{
                    _startTs = Date.now();
                    try {{ localStorage.setItem(SESSION_KEY, String(_startTs)); }} catch(e) {{}}
                }}
                function _getElapsedSeconds() {{ return Math.floor((Date.now() - _startTs) / 1000); }}
                var els = document.querySelectorAll('[data-rps]');
                setInterval(function() {{
                  var elapsed = _getElapsedSeconds();
                  els.forEach(function(el) {{
                    var rps = parseFloat(el.getAttribute('data-rps'));
                    el.textContent = '$' + (rps * elapsed).toLocaleString('en-US', {{
                      minimumFractionDigits: 0,
                      maximumFractionDigits: 0
                    }});
                  }});
                }}, 120);
              }})();
            </script>
            """,
            height=component_height,
        )
except Exception as exc:
    st.info(f"Revenue ticker unavailable: {exc}")
_separator()

# Beat 14 — Transcript pulse
_section(
    "The Human Voice",
    "Here\'s what management teams are saying.",
    "Quotes are pulled from the transcript intelligence layer and filtered to the most relevant executive statements.",
    section_class="human-voice-fix",
)
_render_transcript_pulse_strip(effective_year, selected_quarter)
_separator()

# Beat 15 — Stock tape (no section header, just the tape)
_render_stock_price_strip(market_feed_df)
_separator()

# Beat 16 — Polymarket prediction strip
_section(
    "What the Market is Saying",
    "Live prediction market bets on companies you track.",
    "Real-time odds, volume, and closing dates — powered by <b>Polymarket</b>.",
)
_render_polymarket_strip(logos_original)
_separator()

# Gateway section
st.markdown(
    """
    <div style="padding:64px 0 32px;text-align:center;">
      <div style="color:#4aaeff;font-size:0.7rem;letter-spacing:0.28em;
                  text-transform:uppercase;margin-bottom:12px;">Your Turn</div>
      <div style="color:white;font-size:2.2rem;font-weight:800;
                  margin-bottom:8px;">Go deeper.</div>
      <div style="color:rgba(255,255,255,0.35);font-size:1rem;
                  margin-bottom:36px;">Pick your path.</div>
    </div>
    """,
    unsafe_allow_html=True,
)
# ── CTA navigation — st.page_link (Streamlit native, guaranteed to work) ──
st.markdown("""<style>
/* Glass CTA card styling for st.page_link */
div[data-testid="stPageLink"] a {
  display:block!important;padding:22px 20px!important;border-radius:16px!important;
  background:rgba(74,174,255,0.06)!important;border:1px solid rgba(74,174,255,0.18)!important;
  text-decoration:none!important;cursor:pointer!important;
  transition:all .4s cubic-bezier(.22,1,.36,1)!important;
}
div[data-testid="stPageLink"] a:hover {
  background:rgba(74,174,255,0.12)!important;border-color:rgba(74,174,255,0.4)!important;
  transform:translateY(-4px) scale(1.02)!important;
  box-shadow:0 8px 32px rgba(74,174,255,0.2),0 0 60px rgba(74,174,255,0.08)!important;
}
div[data-testid="stPageLink"] a span {
  color:#4aaeff!important;font-size:1.05rem!important;font-weight:700!important;
  font-family:'DM Sans',sans-serif!important;letter-spacing:.02em!important;
}
</style>""", unsafe_allow_html=True)
_cta_c1, _cta_c2, _cta_c3 = st.columns(3, gap="medium")
with _cta_c1:
    st.page_link("pages/00_Overview.py", label="Overview  →  Macro trends & market signals", icon="🔭")
with _cta_c2:
    st.page_link("pages/01_Earnings.py", label="Earnings  →  Company deep dives & intelligence", icon="📊")
with _cta_c3:
    st.page_link("pages/04_Genie.py", label="Genie  →  Ask the data anything", icon="🧞")

source_label = str(workbook_path) if workbook_path else "not found"
st.markdown(
    f"<div style='margin-top:32px;padding-top:14px;border-top:1px solid rgba(255,255,255,0.12);color:rgba(255,255,255,0.45);font-size:0.84rem;text-align:center;'>Source: {escape(source_label)} • Period baseline: {effective_year} {selected_quarter}</div>",
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)

st.components.v1.html("""
<script>
(function() {
    function initScrollAnimations() {
        var doc = window.parent.document;
        var sections = doc.querySelectorAll('[data-ae-section]');
        if (!sections.length) {
            setTimeout(initScrollAnimations, 1000);
            return;
        }

        var observer = new window.parent.IntersectionObserver(
            function(entries) {
                entries.forEach(function(entry) {
                    var el = entry.target;
                    if (entry.isIntersecting) {
                        el.style.opacity = '1';
                        el.style.transform = 'translateY(0) scale(1)';
                        el._ae_seen = true;
                    } else if (el._ae_seen) {
                        var rect = entry.boundingClientRect;
                        if (rect.top < 0) {
                            el.style.opacity = '0.3';
                            el.style.transform = 'translateY(-20px) scale(0.98)';
                        }
                    }
                });
            },
            { rootMargin: '-5% 0px -10% 0px', threshold: 0.1 }
        );

        sections.forEach(function(el) {
            el.style.transition = [
                'opacity 0.6s cubic-bezier(0.16,1,0.3,1)',
                'transform 0.6s cubic-bezier(0.16,1,0.3,1)',
            ].join(', ');
            observer.observe(el);
        });
    }
    setTimeout(initScrollAnimations, 3000);
})();
</script>
""", height=0)
