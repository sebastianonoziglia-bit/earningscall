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
from utils.workbook_source import resolve_financial_data_xlsx


logger = logging.getLogger(__name__)


@st.cache_data(ttl=3600, show_spinner=False)
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
_resolved = resolve_financial_data_xlsx([])
logger.info(f"STARTUP: Excel resolved to → {_resolved}")
if "pipeline_refreshed" not in st.session_state:
    st.session_state["pipeline_refreshed"] = False
if not st.session_state.get("pipeline_refreshed", False):
    st.session_state["pipeline_refresh_result"] = ensure_intelligence_pipeline_is_fresh()
    st.session_state["pipeline_refreshed"] = True

from utils.global_fonts import apply_global_fonts
from utils.header import display_header
from utils.logos import load_company_logos
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
        sync_local_transcripts_to_workbook()
        with open(SYNC_FLAG_FILE, "w", encoding="utf-8") as handle:
            handle.write(str(datetime.now()))
    except Exception as exc:
        st.warning(f"Transcript sync failed: {exc}")


# Keep startup fast/stable on hosted runtimes (HF).
# Enable only when explicitly requested via env var.
if str(os.getenv(AUTO_SYNC_ENV, "")).strip().lower() in {"1", "true", "yes", "on"}:
    _run_startup_transcript_sync()


st.session_state["active_nav_page"] = "home"
st.session_state["_active_nav_page"] = "home"
display_header(enable_dom_patch=False)
apply_global_fonts()


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent

hero_home_path = APP_DIR / "attached_assets" / "hero_home.jpg"
hero_home_b64 = ""
hero_home_mime = "image/jpeg"
if hero_home_path.exists():
    hero_home_b64 = base64.b64encode(hero_home_path.read_bytes()).decode()
elif (APP_DIR / "attached_assets" / "FAQ MFE.png").exists():
    fallback_path = APP_DIR / "attached_assets" / "FAQ MFE.png"
    hero_home_b64 = base64.b64encode(fallback_path.read_bytes()).decode()
    hero_home_mime = "image/png"


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
        "Meta": "#0668E1",
        "Meta Platforms": "#0668E1",
        "Microsoft": "#00A4EF",
        "Amazon": "#FF9900",
        "Netflix": "#E50914",
        "Disney": "#113CCF",
        "Comcast": "#0088D2",
        "Warner Bros. Discovery": "#1E40AF",
        "Paramount Global": "#0060FF",
        "Spotify": "#1ED760",
        "Roku": "#6F1AB1",
    }
    return palette.get(company, "#0073FF")


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
            f"<a class='wm-hero-logo-link' href='?nav=earnings&company={company_q}' "
            f"target='_self' rel='noopener' onclick=\"window.location.assign('?nav=earnings&company={company_q}'); return false;\" "
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


@st.cache_data(ttl=3600, show_spinner=False)
def _read_excel_sheet_cached(excel_path: str, sheet_name: str, source_stamp: int) -> pd.DataFrame:
    _ = source_stamp
    if not excel_path:
        return pd.DataFrame()
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
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


@st.cache_data(ttl=3600, show_spinner=False)
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


@st.cache_data(ttl=3600, show_spinner=False)
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


@st.cache_data(ttl=3600, show_spinner=False)
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


@st.cache_data(ttl=3600, show_spinner=False)
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


@st.cache_data(ttl=3600, show_spinner=False)
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


@st.cache_data(ttl=3600, show_spinner=False)
def _load_m2_yearly_series(excel_path: str, source_stamp: int) -> pd.DataFrame:
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
    preferred = {"wm2ns", "wm2", "m2", "m2value", "value"}
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


@st.cache_data(ttl=3600, show_spinner=False)
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
def _load_transcript_pulse_quotes(repo_root_path: str, db_path: str, selected_year: int, selected_quarter: str, limit: int = 5) -> tuple[pd.DataFrame, str]:
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


@st.cache_data(ttl=3600, show_spinner=False)
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

available_years = sorted(metrics_df["year"].dropna().unique().tolist()) if not metrics_df.empty else []
latest_year = int(max(available_years)) if available_years else 2024
home_year_options = [int(y) for y in available_years if 2015 <= int(y) <= 2024]
if not home_year_options:
    home_year_options = [int(y) for y in available_years] if available_years else [latest_year]
home_year_default = int(home_year_options[-1]) if home_year_options else latest_year

macro_df = _load_overview_macro_sheet(excel_path, source_stamp) if excel_path else pd.DataFrame()
ad_sheet_df = _load_company_ad_revenue_sheet(excel_path, source_stamp) if excel_path else pd.DataFrame()
m2_yearly_df = _load_m2_yearly_series(excel_path, source_stamp) if excel_path else pd.DataFrame()
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
bg_color = "#0B1220" if is_dark else "#F5F8FF"
text_color = "#E2E8F0" if is_dark else "#0F172A"
muted_color = "#94A3B8" if is_dark else "#475569"
surface_color = "#111827" if is_dark else "#FFFFFF"
border_color = "rgba(148,163,184,0.28)" if is_dark else "rgba(15,23,42,0.10)"

st.markdown(
    f"""
<style>
[data-testid="stSidebarNav"] {{
    display: none !important;
}}

.wm-wrap {{
    max-width: 1500px;
    margin: 0 auto;
    margin-top: 0;
    padding-top: 0;
    padding: 0 14px 36px;
}}

.wm-hero {{
    position: relative;
    overflow: hidden;
    border-radius: 22px;
    padding: 38px 40px;
    margin: 8px 0 26px;
    background: linear-gradient(135deg, #0073FF 0%, #00A3FF 55%, #00C2FF 100%);
    box-shadow: 0 20px 48px rgba(0, 115, 255, 0.30);
}}

.wm-hero::before {{
    content: "";
    position: absolute;
    inset: -40% -30%;
    background: radial-gradient(circle at 28% 38%, rgba(255,255,255,0.22) 0%, rgba(255,255,255,0.0) 54%);
    animation: wmPulse 7.5s ease-in-out infinite;
    pointer-events: none;
}}

@keyframes wmPulse {{
    0%, 100% {{ transform: translate(0, 0) scale(1); opacity: 0.62; }}
    50% {{ transform: translate(8%, 8%) scale(1.08); opacity: 0.38; }}
}}

.wm-status {{
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 9px;
    padding: 6px 14px;
    border-radius: 999px;
    background: rgba(2, 6, 23, 0.20);
    color: #D1FAE5;
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}

.wm-status-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #22C55E;
    animation: wmDotPulse 1.9s ease-in-out infinite;
}}

@keyframes wmDotPulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50% {{ opacity: 0.45; transform: scale(1.25); }}
}}

.wm-title {{
    position: relative;
    margin: 12px 0 10px;
    color: #FFFFFF;
    font-size: clamp(2rem, 3.2vw, 3.1rem);
    line-height: 1.08;
    font-weight: 900;
}}

.wm-subtitle {{
    position: relative;
    margin: 0 0 26px;
    color: rgba(255, 255, 255, 0.94);
    font-size: 1.06rem;
    line-height: 1.55;
    max-width: 1100px;
}}

.wm-kpi-grid {{
    position: relative;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 15px;
}}

.wm-kpi-card {{
    border-radius: 15px;
    padding: 16px 18px;
    border: 1px solid rgba(255,255,255,0.28);
    background: rgba(255,255,255,0.16);
    backdrop-filter: blur(9px);
    transition: transform 0.22s ease, background 0.22s ease;
}}

.wm-kpi-card:hover {{
    transform: translateY(-3px);
    background: rgba(255,255,255,0.22);
}}

.wm-kpi-label {{
    color: rgba(255,255,255,0.84);
    font-size: 0.76rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}

.wm-kpi-value {{
    color: #FFFFFF;
    margin-top: 6px;
    font-size: clamp(1.35rem, 2.5vw, 1.85rem);
    font-weight: 900;
    line-height: 1.1;
}}

.wm-kpi-change {{
    color: rgba(255,255,255,0.94);
    font-size: 0.83rem;
    font-weight: 600;
    margin-top: 7px;
}}

.wm-nav-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
    margin: 0 0 28px;
}}

.wm-nav-btn {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    text-decoration: none !important;
    border-radius: 14px;
    padding: 14px 14px;
    color: #fff !important;
    background: rgba(37, 99, 235, 0.12);
    border: 1px solid rgba(37, 99, 235, 0.28);
    transition: background 0.2s ease, border-color 0.2s ease, transform 0.16s ease;
}}

.wm-nav-btn:hover {{
    background: rgba(37, 99, 235, 0.22);
    border-color: rgba(37, 99, 235, 0.5);
    transform: translateY(-2px);
}}

.wm-nav-btn:active {{
    background: rgba(37, 99, 235, 0.32);
}}

.wm-nav-title {{
    font-size: 0.98rem;
    font-weight: 800;
    line-height: 1.2;
}}

.wm-nav-desc {{
    margin-top: 4px;
    font-size: 0.79rem;
    font-weight: 500;
    opacity: 0.94;
}}

.wm-nav-overview {{ background: rgba(37, 99, 235, 0.12); border-color: rgba(37, 99, 235, 0.28); }}
.wm-nav-earnings {{ background: rgba(37, 99, 235, 0.12); border-color: rgba(37, 99, 235, 0.28); }}
.wm-nav-stocks {{ background: rgba(37, 99, 235, 0.12); border-color: rgba(37, 99, 235, 0.28); }}
.wm-nav-genie {{ background: rgba(37, 99, 235, 0.12); border-color: rgba(37, 99, 235, 0.28); }}

.wm-section-title {{
    margin: 28px 0 14px;
    color: {muted_color};
    font-size: 0.76rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 800;
    display: flex;
    align-items: center;
    gap: 10px;
}}

.wm-section-title::before {{
    content: "";
    width: 4px;
    height: 18px;
    border-radius: 2px;
    background: linear-gradient(180deg, #0073ff 0%, #00c2ff 100%);
}}

.wm-insight-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
    gap: 14px;
}}

.wm-insight-card {{
    background: {surface_color};
    border: 1px solid {border_color};
    border-radius: 16px;
    padding: 18px 18px 17px;
    color: {text_color};
    box-shadow: 0 8px 24px rgba(2, 6, 23, 0.06);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}}

.wm-insight-card:hover {{
    transform: translateY(-4px);
    box-shadow: 0 14px 36px rgba(0, 115, 255, 0.16);
}}

.wm-priority {{
    display: inline-block;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 0.69rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 10px;
}}

.wm-priority-high {{ background: rgba(239,68,68,0.15); color: #ef4444; }}
.wm-priority-medium {{ background: rgba(249,115,22,0.15); color: #f97316; }}
.wm-priority-low {{ background: rgba(59,130,246,0.15); color: #3b82f6; }}

.wm-priority-legend {{
    margin: 4px 0 14px;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid {border_color};
    background: {'rgba(15,23,42,0.04)' if is_dark else 'rgba(15,23,42,0.03)'};
    color: {muted_color};
    font-size: 0.8rem;
    line-height: 1.5;
}}

.wm-insight-title {{
    color: {text_color};
    font-size: 1.05rem;
    line-height: 1.35;
    font-weight: 750;
    margin: 0 0 8px;
}}

.wm-insight-text {{
    color: {muted_color};
    font-size: 0.9rem;
    line-height: 1.6;
    margin: 0;
}}

.quote-pill {{
    background: rgba(255,255,255,0.04);
    border-left: 3px solid #3b82f6;
    padding: 10px 14px;
    margin-top: 12px;
    border-radius: 0 8px 8px 0;
    font-size: 0.82rem;
}}

.quote-text {{
    font-style: italic;
    color: {'#cbd5e1' if is_dark else '#334155'};
}}

.quote-meta {{
    display: block;
    margin-top: 6px;
    color: {'#64748b' if is_dark else '#475569'};
    font-size: 0.75rem;
}}

body.theme-dark .wm-insight-card a {{
    color: #93C5FD !important;
}}

.wm-narrative-block {{
    margin: 0 0 28px;
    padding: 20px 24px;
    border-radius: 14px;
    border-left: 4px solid #0073FF;
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(15, 23, 42, 0.1);
    border-left: 4px solid #0073FF;
}}

body.theme-dark .wm-narrative-block {{
    background: rgba(15, 23, 42, 0.55);
    border-color: rgba(148, 163, 184, 0.18);
    border-left-color: #0073FF;
}}

.wm-narrative-label {{
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #0073FF;
    margin-bottom: 8px;
}}

.wm-narrative-text {{
    font-size: 0.97rem;
    line-height: 1.7;
    color: #1E293B;
    margin: 0;
}}

body.theme-dark .wm-narrative-text {{
    color: #CBD5E1;
}}

.wm-insight-logos {{
    display: flex;
    gap: 6px;
    margin-bottom: 10px;
    align-items: center;
    flex-wrap: wrap;
}}

.wm-mini-logo-wrap {{
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: rgba(148, 163, 184, 0.15);
    border: 1px solid {border_color};
}}

.wm-mini-logo {{
    width: 16px;
    height: 16px;
    object-fit: contain;
}}

.wm-company-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 14px;
}}

.wm-strip-header {{
    margin: 14px 0 8px;
}}

.wm-strip-title {{
    color: {text_color};
    font-size: 0.97rem;
    font-weight: 780;
    line-height: 1.2;
}}

.wm-strip-subtitle {{
    color: {muted_color};
    font-size: 0.78rem;
    line-height: 1.35;
    margin-top: 3px;
}}

.wm-hscroll {{
    display: flex;
    gap: 12px;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 4px 2px 12px 2px;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
    scrollbar-color: rgba(148,163,184,0.55) transparent;
}}

.wm-hscroll::-webkit-scrollbar {{
    height: 8px;
}}

.wm-hscroll::-webkit-scrollbar-thumb {{
    border-radius: 8px;
    background: rgba(148,163,184,0.45);
}}

.wm-company-card {{
    background: {surface_color};
    border: 1px solid {border_color};
    border-left: 4px solid var(--wm-color, #0073ff);
    border-radius: 14px;
    padding: 16px;
    position: relative;
    box-shadow: 0 8px 20px rgba(2, 6, 23, 0.06);
    transition: transform 0.18s ease;
}}

.wm-company-card:hover {{ transform: translateY(-3px); }}

.wm-strip-card {{
    flex: 0 0 248px;
    min-width: 248px;
    max-width: 248px;
    scroll-snap-align: start;
}}

.wm-rank {{
    position: absolute;
    right: 12px;
    top: 10px;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
    font-weight: 900;
    color: #fff;
    background: linear-gradient(135deg, #0073ff 0%, #00c2ff 100%);
}}

.wm-company-head {{
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 8px;
    min-height: 26px;
}}

.wm-company-logo {{
    width: 22px;
    height: 22px;
    object-fit: contain;
}}

.wm-company-name {{
    font-size: 1rem;
    font-weight: 760;
    color: {text_color};
}}

.wm-company-value {{
    font-size: 1.6rem;
    font-weight: 900;
    line-height: 1.1;
    color: var(--wm-color, #0073ff);
    margin-top: 5px;
}}

.wm-company-yoy {{
    font-size: 0.8rem;
    font-weight: 700;
    margin-top: 3px;
}}

.wm-more-indicator {{
    flex: 0 0 120px;
    min-width: 120px;
    max-width: 120px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(0,115,255,0.08);
    border: 2px dashed rgba(0,115,255,0.35);
    border-radius: 14px;
    cursor: default;
}}

.wm-more-arrow {{
    font-size: 2rem;
    color: #0073ff;
    font-weight: 900;
}}

.wm-more-label {{
    font-size: 0.75rem;
    color: #0073ff;
    text-align: center;
    margin-top: 6px;
    font-weight: 700;
    line-height: 1.35;
}}

.wm-company-caption {{
    margin-top: 5px;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: {muted_color};
    font-weight: 650;
}}

.wm-cta {{
    margin-top: 34px;
    border-radius: 18px;
    border: 1px solid {border_color};
    padding: 28px 26px;
    background: linear-gradient(140deg, {'#182235' if is_dark else '#f8fbff'} 0%, {'#0f172a' if is_dark else '#e8f0ff'} 100%);
}}

.wm-cta-title {{
    font-size: 1.55rem;
    font-weight: 820;
    color: {'#F8FAFC' if is_dark else '#0f172a'};
    margin: 0 0 8px;
}}

.wm-cta-text {{
    font-size: 0.98rem;
    line-height: 1.55;
    color: {'#cbd5e1' if is_dark else '#475569'};
    margin: 0 0 16px;
}}

.wm-cta-actions {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}}

.wm-cta-btn {{
    display: inline-block;
    text-decoration: none !important;
    border-radius: 10px;
    padding: 11px 16px;
    color: #fff !important;
    font-weight: 700;
    font-size: 0.92rem;
    background: linear-gradient(135deg, #0073ff 0%, #00c2ff 100%);
}}

.wm-cta-btn.wm-ghost {{
    color: {'#f8fafc' if is_dark else '#0f172a'} !important;
    background: {'rgba(255,255,255,0.12)' if is_dark else 'rgba(0,115,255,0.12)'};
    border: 1px solid {border_color};
}}

.wm-foot {{
    margin-top: 32px;
    padding-top: 14px;
    border-top: 1px solid {border_color};
    color: {muted_color};
    font-size: 0.84rem;
    text-align: center;
}}

.wm-pulse-strip {{
    width: 100%;
    overflow: hidden;
    border-radius: 12px;
    border: 1px solid rgba(148,163,184,0.25);
    background: #060b14;
    padding: 12px 0;
}}

.wm-pulse-track {{
    display: flex;
    align-items: stretch;
    gap: 12px;
    width: max-content;
    animation: wmPulseScroll 42s linear infinite;
}}

.wm-pulse-item {{
    width: min(420px, 82vw);
    flex: 0 0 auto;
    border-radius: 10px;
    border: 1px solid rgba(148,163,184,0.22);
    background: rgba(15,23,42,0.72);
    padding: 10px 12px;
}}

.wm-pulse-quote {{
    color: #e2e8f0;
    font-style: italic;
    font-size: 0.85rem;
    line-height: 1.45;
}}

.wm-pulse-meta {{
    margin-top: 8px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 0.75rem;
}}

.wm-pulse-meta .wm-mini-logo {{
    width: 96px;
    height: 96px;
    max-width: 100%;
    border-radius: 50%;
    object-fit: contain;
    background: rgba(148, 163, 184, 0.16);
    border: 1px solid rgba(148, 163, 184, 0.3);
    padding: 6px;
    flex-shrink: 0;
}}

.wm-pulse-company {{
    color: #FFFFFF !important;
    font-weight: 700;
}}

.wm-pulse-speaker {{
    color: rgba(255,255,255,0.75) !important;
}}

@keyframes wmPulseScroll {{
    from {{ transform: translateX(0); }}
    to {{ transform: translateX(-50%); }}
}}

@media (max-width: 768px) {{
    .wm-wrap {{ padding: 0 6px 24px; }}
    .wm-hero {{ padding: 28px 20px; }}
    .wm-title {{ font-size: 2rem; }}
    .wm-insight-grid {{ grid-template-columns: 1fr; }}
    .wm-kpi-grid {{ grid-template-columns: 1fr; }}
}}
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
year_index = valid_years.index(int(selected_year))
selected_year = int(
    st.selectbox(
        "Story Year",
        options=valid_years,
        index=year_index,
        key="selected_year",
    )
)
effective_year = int(selected_year)
selected_quarter = _select_latest_quarter_for_year(macro_df, effective_year)

st.components.v1.html(
    """
<script>
document.addEventListener('DOMContentLoaded', function() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
      }
    });
  }, { threshold: 0.12 });
  document.querySelectorAll('.scroll-reveal').forEach(el => observer.observe(el));

  window._tickerStart = Date.now();
  function updateTickers() {
    const elapsed = (Date.now() - window._tickerStart) / 1000;
    document.querySelectorAll('[data-rps]').forEach(el => {
      const rps = parseFloat(el.getAttribute('data-rps'));
      const val = rps * elapsed;
      el.textContent = '$' + val.toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
      });
    });
  }
  setInterval(updateTickers, 100);
});
</script>
<style>
.scroll-reveal {
  opacity: 0;
  transform: translateY(28px);
  transition: opacity 0.75s cubic-bezier(.4,0,.2,1),
              transform 0.75s cubic-bezier(.4,0,.2,1);
}
.scroll-reveal.is-visible { opacity: 1; transform: translateY(0); }
.story-beat {
  background: rgba(37, 99, 235, 0.14);
  border: 1px solid rgba(37, 99, 235, 0.25);
  border-radius: 12px;
  padding: 48px 40px;
  margin-bottom: 32px;
}
.kpi-card {
  background: rgba(37, 99, 235, 0.18);
  border: 1px solid rgba(37, 99, 235, 0.3);
  border-radius: 12px;
  padding: 28px 20px;
  text-align: center;
}
.beat-label {
  color: #ff5b1f;
  font-size: 0.75rem;
  letter-spacing: 0.25em;
  text-transform: uppercase;
  margin-bottom: 12px;
}
.beat-headline {
  color: white;
  font-size: 1.6rem;
  font-weight: 700;
  line-height: 1.3;
  margin-bottom: 16px;
}
.beat-body {
  color: rgba(255,255,255,0.6);
  font-size: 1rem;
  line-height: 1.8;
}
.ticker-val {
  color: #ff5b1f;
  font-family: monospace;
  font-size: 1.8rem;
  font-weight: 800;
}
</style>
""",
    height=0,
)


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
    current = pd.to_numeric(current_series, errors="coerce")
    previous = pd.to_numeric(prev_series, errors="coerce")
    return ((current - previous) / previous * 100).where(previous > 0, np.nan)


def _yoy_html(yoy):
    if yoy is None:
        return ""
    arrow = "▲" if yoy >= 0 else "▼"
    color = "#22c55e" if yoy >= 0 else "#ef4444"
    return (
        f'<span style="color:{color};font-size:0.85rem;">'
        f"{arrow} {abs(yoy):.1f}% YoY</span>"
    )


def _comment_growth(metric_name, yoy):
    if yoy is None:
        return ""
    if yoy >= 15:
        return f"{metric_name} surged <strong style='color:#22c55e;'>+{yoy:.1f}%</strong> — an exceptional year."
    if yoy >= 5:
        return f"{metric_name} grew solidly <strong style='color:#22c55e;'>+{yoy:.1f}%</strong>."
    if yoy >= 0:
        return f"{metric_name} edged up <strong style='color:#22c55e;'>+{yoy:.1f}%</strong> — a year of modest expansion."
    if yoy >= -5:
        return f"{metric_name} dipped <strong style='color:#ef4444;'>{yoy:.1f}%</strong> — a year of consolidation."
    return f"{metric_name} contracted sharply <strong style='color:#ef4444;'>{yoy:.1f}%</strong> — a difficult macro year."


def _beat(content_fn, label=None, headline=None):
    parts = ["<div class='scroll-reveal story-beat'>"]
    if label:
        parts.append(f"<div class='beat-label'>{escape(str(label))}</div>")
    if headline:
        parts.append(f"<div class='beat-headline'>{escape(str(headline))}</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)
    content_fn()
    st.markdown("</div>", unsafe_allow_html=True)


def _find_groupm_col(df: pd.DataFrame, include_terms: list[str], exclude_terms: Optional[list[str]] = None) -> str:
    if df is None or df.empty:
        return ""
    excludes = [str(x).lower() for x in (exclude_terms or [])]
    for col in df.columns:
        norm = re.sub(r"[^a-z0-9]+", "", str(col).lower())
        if all(term.lower().replace(" ", "") in norm for term in include_terms):
            if any(ex.lower().replace(" ", "") in norm for ex in excludes):
                continue
            return str(col)
    return ""


def _render_transcript_pulse_strip() -> None:
    pulse_df, pulse_source = _load_transcript_pulse_quotes(
        repo_root_path=str(ROOT_DIR),
        db_path=str(db_path),
        selected_year=int(effective_year),
        selected_quarter=selected_quarter,
        limit=5,
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
        quote = str(getattr(row, "quote", "") or "").strip()
        if not quote:
            continue
        logo_b64 = _resolve_logo(company, logos)
        logo_html = (
            f"<img class='wm-mini-logo' src='data:image/png;base64,{logo_b64}' alt='{escape(company)} logo' />"
            if logo_b64
            else "<span class='wm-mini-logo' style='display:inline-flex;align-items:center;justify-content:center;'>•</span>"
        )
        pulse_items.append(
            "<div class='wm-pulse-item'>"
            f"<div class='wm-pulse-quote'>“{escape(quote)}”</div>"
            f"<div class='wm-pulse-meta'>{logo_html}<span class='wm-pulse-company'>{escape(company)}</span>"
            f"<span class='wm-pulse-speaker'>— {escape(speaker)}</span></div>"
            "</div>"
        )
    if not pulse_items:
        st.info("No transcript data available yet — run the intelligence pipeline first.")
        return
    track = "".join(pulse_items + pulse_items)
    st.markdown(
        f"<div class='wm-pulse-strip'><div class='wm-pulse-track'>{track}</div></div>",
        unsafe_allow_html=True,
    )
    if pulse_source:
        st.caption(f"Source: {pulse_source}")


metrics = metrics_df.copy() if isinstance(metrics_df, pd.DataFrame) else pd.DataFrame()
if not metrics.empty:
    metrics["year"] = pd.to_numeric(metrics["year"], errors="coerce").astype("Int64")
    for col in ["revenue", "operating_income", "market_cap", "rd", "net_income"]:
        if col in metrics.columns:
            metrics[col] = pd.to_numeric(metrics[col], errors="coerce")
    metrics = metrics.dropna(subset=["year", "company"]).copy()
    metrics["year"] = metrics["year"].astype(int)

groupm_df = _read_excel_sheet_cached(excel_path, "Global Advertising (GroupM)", source_stamp) if excel_path else pd.DataFrame()
if not groupm_df.empty:
    groupm_df = groupm_df.copy()
    groupm_df.columns = [str(c).strip() for c in groupm_df.columns]
groupm_year_col = _find_groupm_col(groupm_df, ["year"]) if not groupm_df.empty else ""
groupm_total_col = _find_groupm_col(groupm_df, ["total"]) if not groupm_df.empty else ""
if not groupm_df.empty and groupm_year_col and not groupm_total_col:
    numeric_cols = []
    for c in groupm_df.columns:
        if c == groupm_year_col:
            continue
        numeric = pd.to_numeric(groupm_df[c], errors="coerce")
        if numeric.notna().sum() > 0:
            numeric_cols.append(c)
            groupm_df[c] = numeric
    if numeric_cols:
        groupm_df["_computed_total"] = groupm_df[numeric_cols].sum(axis=1, min_count=1)
        groupm_total_col = "_computed_total"

groupm_b = None
groupm_yoy = None
if not groupm_df.empty and groupm_year_col and groupm_total_col:
    g_row = _yr(groupm_df, effective_year, groupm_year_col)
    g_prev = _yr(groupm_df, effective_year - 1, groupm_year_col)
    if not g_row.empty:
        groupm_b = float(pd.to_numeric(g_row[groupm_total_col], errors="coerce").iloc[0])
        if not g_prev.empty:
            prev_val = float(pd.to_numeric(g_prev[groupm_total_col], errors="coerce").iloc[0])
            groupm_yoy = _yoy(groupm_b, prev_val)

rev_b = None
rev_yoy = None
mcap_b = None
mcap_yoy = None
if not metrics.empty:
    yr = metrics[metrics["year"] == effective_year].copy()
    py = metrics[metrics["year"] == (effective_year - 1)].copy()
    if not yr.empty:
        rev_m = float(pd.to_numeric(yr.get("revenue", pd.Series(dtype=float)), errors="coerce").sum())
        mcap_m = float(pd.to_numeric(yr.get("market_cap", pd.Series(dtype=float)), errors="coerce").sum())
        rev_b = rev_m / 1e3 if rev_m else None
        mcap_b = mcap_m / 1e3 if mcap_m else None
        if not py.empty:
            prev_rev_m = float(pd.to_numeric(py.get("revenue", pd.Series(dtype=float)), errors="coerce").sum())
            prev_mcap_m = float(pd.to_numeric(py.get("market_cap", pd.Series(dtype=float)), errors="coerce").sum())
            rev_yoy = _yoy(rev_m, prev_rev_m)
            mcap_yoy = _yoy(mcap_m, prev_mcap_m)

ad_lookup = _load_ad_revenue_by_company(excel_path, source_stamp, effective_year) if excel_path else {}
total_tracked_musd = float(sum(float(v.get("ad_revenue_musd", 0.0)) for v in ad_lookup.values()))
total_tracked_b = total_tracked_musd / 1e3 if total_tracked_musd else 0.0
big_tech = ["Alphabet", "Meta Platforms", "Amazon", "Apple", "Microsoft"]
big_tech_musd = float(sum(float(ad_lookup.get(c, {}).get("ad_revenue_musd", 0.0)) for c in big_tech))
big_tech_b = big_tech_musd / 1e3 if big_tech_musd else 0.0
other_b = max(total_tracked_b - big_tech_b, 0.0)
global_ad_denom = groupm_b if groupm_b else total_tracked_b
untracked_b = max((global_ad_denom or 0) - total_tracked_b, 0.0)

# Screen 1
st.markdown(
    """
<div style="
  background: linear-gradient(135deg, rgba(37,99,235,0.2) 0%, #0a0a0a 100%);
  color:white; padding:120px 60px; text-align:center;
  border-radius:16px; margin-bottom:32px;
">
  <div class="beat-label">The Attention Economy</div>
  <div style="font-size:3.8rem;font-weight:900;line-height:1.1;margin-bottom:24px;">
    14 companies.<br>One dashboard.
  </div>
  <div style="color:rgba(255,255,255,0.35);font-size:1rem;letter-spacing:0.08em;">
    ↓ Scroll to explore
  </div>
</div>
""",
    unsafe_allow_html=True,
)


# Screen 2
def _screen2():
    col1, col2, col3 = st.columns(3)
    rev_display = "—"
    if rev_b is not None:
        rev_display = f"${(rev_b / 1e3):.1f}T" if rev_b >= 1000 else f"${rev_b:.0f}B"
    mcap_display = "—"
    if mcap_b is not None:
        mcap_display = f"${(mcap_b / 1e3):.1f}T" if mcap_b >= 1000 else f"${mcap_b:.0f}B"
    cards = [
        ("Global Ad Spend", f"${groupm_b:.0f}B" if groupm_b is not None else "—", _yoy_html(groupm_yoy), f"{effective_year} · GroupM"),
        ("Tracked Revenue", rev_display, _yoy_html(rev_yoy), f"{effective_year} · 14 companies"),
        ("Combined Market Cap", mcap_display, _yoy_html(mcap_yoy), f"{effective_year} · 14 companies"),
    ]
    for col, (title, val, yoy_html, sub) in zip([col1, col2, col3], cards):
        with col:
            st.markdown(
                f"""
                <div class="kpi-card">
                  <div style="color:rgba(255,255,255,0.45);font-size:0.75rem;
                              letter-spacing:0.1em;text-transform:uppercase;
                              margin-bottom:8px;">{escape(title)}</div>
                  <div style="color:white;font-size:2.2rem;font-weight:900;
                              font-family:monospace;margin-bottom:6px;">{escape(val)}</div>
                  {yoy_html}
                  <div style="color:rgba(255,255,255,0.3);font-size:0.7rem;
                              margin-top:8px;">{escape(sub)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    parts = []
    if groupm_b is not None:
        parts.append(
            f"In {effective_year}, the world spent <strong style='color:white;'>${groupm_b:.0f}B</strong> on advertising."
        )
    if rev_yoy is not None:
        parts.append(_comment_growth("Tracked company revenues", rev_yoy))
    if mcap_yoy is not None:
        if mcap_yoy >= 15:
            parts.append(
                f"Markets rewarded them: combined market cap surged <strong style='color:#22c55e;'>+{mcap_yoy:.1f}%</strong>."
            )
        elif mcap_yoy >= 0:
            parts.append(
                f"Markets were measured: combined market cap rose <strong style='color:#22c55e;'>+{mcap_yoy:.1f}%</strong>."
            )
        else:
            parts.append(
                f"Markets were skeptical: combined market cap fell <strong style='color:#ef4444;'>{mcap_yoy:.1f}%</strong>."
            )
    if parts:
        st.markdown(
            f"<div class='beat-body' style='margin-top:24px;'>{' '.join(parts)}</div>",
            unsafe_allow_html=True,
        )


_beat(_screen2, label="The Scale", headline=f"The world's attention, in numbers — {effective_year}")


# Screen 3
def _screen3():
    try:
        country_df = _read_excel_sheet_cached(excel_path, "Country_Totals_vs_GDP", source_stamp) if excel_path else pd.DataFrame()
        if country_df.empty:
            st.info("Global map unavailable — open Overview to see the full map.")
            return
        country_df = country_df.copy()
        country_df.columns = [str(c).strip() for c in country_df.columns]
        country_col = ""
        for candidate in country_df.columns:
            if re.sub(r"[^a-z0-9]+", "", candidate.lower()) in {"country", "countryname"}:
                country_col = candidate
                break
        year_col = ""
        for candidate in country_df.columns:
            if "year" in candidate.lower():
                year_col = candidate
                break
        value_col = ""
        preferred = ["ad_vs_gdp_%", "ad_vs_gdp", "adspendpctgdp", "ad_share_gdp"]
        norm_map = {re.sub(r"[^a-z0-9]+", "", c.lower()): c for c in country_df.columns}
        for key in preferred:
            if key in norm_map:
                value_col = norm_map[key]
                break
        if not value_col:
            numeric_candidates = []
            for c in country_df.columns:
                if c in {country_col, year_col}:
                    continue
                numeric = pd.to_numeric(country_df[c], errors="coerce")
                if numeric.notna().sum() > 0:
                    numeric_candidates.append(c)
            value_col = numeric_candidates[0] if numeric_candidates else ""

        if not country_col or not value_col:
            st.info("Global map unavailable — open Overview to see the full map.")
            return

        scoped = country_df.copy()
        if year_col:
            scoped = _yr(country_df, effective_year, year_col)
        if scoped.empty:
            st.info("Global map unavailable — open Overview to see the full map.")
            return
        scoped[value_col] = pd.to_numeric(scoped[value_col], errors="coerce")
        scoped = scoped.dropna(subset=[country_col, value_col]).copy()
        if scoped.empty:
            st.info("Global map unavailable — open Overview to see the full map.")
            return

        fig = px.choropleth(
            scoped,
            locations=country_col,
            locationmode="country names",
            color=value_col,
            color_continuous_scale="Blues",
            labels={value_col: "Ad vs GDP %"},
        )
        fig.update_layout(
            geo=dict(showframe=False, showcoastlines=False, projection_type="natural earth"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            margin=dict(l=0, r=0, t=8, b=0),
            height=460,
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.info("Global map unavailable — open Overview to see the full map.")


_beat(_screen3, label="The World", headline="Every country. Every dollar. One map.")


# Screen 4
def _screen4():
    if total_tracked_b <= 0 and (groupm_b is None or groupm_b <= 0):
        st.info("Ad revenue data not available.")
        return
    import plotly.graph_objects as go

    denom = global_ad_denom if global_ad_denom else total_tracked_b
    segments = [
        ("Big Tech (Alphabet, Meta, Amazon, Apple, Microsoft)", big_tech_b, "#ff5b1f"),
        ("Other Tracked Companies", other_b, "#3b82f6"),
        ("Rest of World (untracked)", untracked_b, "#1f2937"),
    ]
    fig = go.Figure()
    for name, val, color in segments:
        pct = (val / denom * 100) if denom else 0
        fig.add_trace(
            go.Bar(
                x=[val],
                y=[""],
                name=name,
                orientation="h",
                marker=dict(color=color),
                customdata=[[pct]],
                text=f"${val:.0f}B  {pct:.1f}%" if pct > 7 else "",
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color="white", size=11),
                hovertemplate=f"{name}: $%{{x:.0f}}B — %{{customdata[0]:.1f}}% of global<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.3, font=dict(color="white", size=11)),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=8, b=100),
        height=160,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
    )
    st.plotly_chart(fig, use_container_width=True)
    big_pct = (big_tech_b / denom * 100) if denom else 0
    tracked_pct = (total_tracked_b / denom * 100) if denom else 0
    st.caption(
        f"Of the ${denom:.0f}B spent globally on advertising in {effective_year}, "
        f"just 5 Big Tech companies captured ${big_tech_b:.0f}B ({big_pct:.1f}%). "
        f"Our full tracked universe held ${total_tracked_b:.0f}B ({tracked_pct:.1f}% of global). "
        f"The remaining ${untracked_b:.0f}B went to thousands of other publishers worldwide."
    )


_beat(_screen4, label="The Concentration", headline="Most of it went to very few hands.")


# Screen 5
def _screen5():
    try:
        if metrics.empty:
            st.info("Revenue treemap unavailable.")
            return
        yr_df = metrics[metrics["year"] == effective_year].copy()
        if yr_df.empty:
            st.info("Revenue treemap unavailable.")
            return
        prev_df = metrics[metrics["year"] == (effective_year - 1)][["company", "revenue"]].rename(columns={"revenue": "prev_rev"})
        yr_df = yr_df.merge(prev_df, on="company", how="left")
        yr_df["rev_yoy"] = _yoy_vec(yr_df["revenue"], yr_df["prev_rev"])
        yr_df["revenue_b"] = pd.to_numeric(yr_df["revenue"], errors="coerce") / 1e3
        yr_df = yr_df.dropna(subset=["company", "revenue_b"]).copy()
        if yr_df.empty:
            st.info("Revenue treemap unavailable.")
            return
        fig = px.treemap(
            yr_df,
            path=["company"],
            values="revenue_b",
            color="rev_yoy",
            color_continuous_scale=["#ef4444", "#1f2937", "#22c55e"],
            color_continuous_midpoint=0,
            custom_data=["rev_yoy", "revenue_b"],
            title=f"Revenue by Company — {effective_year}",
        )
        fig.update_traces(
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Revenue: $%{customdata[1]:.0f}B<br>"
                "YoY: %{customdata[0]:+.1f}%<extra></extra>"
            ),
            textfont=dict(color="white"),
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            height=400,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Rectangle size = total revenue. Color = YoY growth (green = growth, red = decline). Hover for details.")
    except Exception:
        st.info("Revenue treemap unavailable.")


_beat(_screen5, label="The Revenue Map", headline="Not all revenue is equal. See who grew.")


# Screen 6
def _screen6():
    try:
        import plotly.graph_objects as go

        if metrics.empty:
            st.info("Ad dependency chart unavailable.")
            return
        yr_metrics = metrics[metrics["year"] == effective_year].copy()
        if yr_metrics.empty:
            st.info("Ad dependency chart unavailable.")
            return
        rows = []
        for _, m_row in yr_metrics.iterrows():
            company = str(m_row.get("company", ""))
            total_rev = float(pd.to_numeric(pd.Series([m_row.get("revenue", np.nan)]), errors="coerce").iloc[0] or 0.0)
            ad_rev_musd = float(ad_lookup.get(company, {}).get("ad_revenue_musd", 0.0))
            ad_pct = (ad_rev_musd / total_rev * 100) if total_rev > 0 else 0.0
            rows.append(
                {
                    "company": company,
                    "ad_pct": min(max(ad_pct, 0.0), 100.0),
                    "non_ad_pct": max(100.0 - min(max(ad_pct, 0.0), 100.0), 0.0),
                    "ad_rev_b": ad_rev_musd / 1e3,
                    "total_rev_b": total_rev / 1e3,
                }
            )
        if not rows:
            st.info("Ad dependency chart unavailable.")
            return
        rows.sort(key=lambda r: r["ad_pct"], reverse=True)
        companies = [r["company"] for r in rows]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                y=companies,
                x=[r["ad_pct"] for r in rows],
                name="Ad Revenue %",
                orientation="h",
                marker=dict(color="#ff5b1f"),
                customdata=[[r["ad_rev_b"], r["total_rev_b"]] for r in rows],
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Ad Revenue: $%{customdata[0]:.1f}B (%{x:.1f}%)<br>"
                    "Total Revenue: $%{customdata[1]:.1f}B<extra></extra>"
                ),
            )
        )
        fig.add_trace(
            go.Bar(
                y=companies,
                x=[r["non_ad_pct"] for r in rows],
                name="Non-Ad Revenue %",
                orientation="h",
                marker=dict(color="rgba(255,255,255,0.08)"),
                hoverinfo="skip",
            )
        )
        fig.update_layout(
            barmode="stack",
            xaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="rgba(255,255,255,0.05)", color="rgba(255,255,255,0.4)"),
            yaxis=dict(color="white"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            legend=dict(font=dict(color="white")),
            height=420,
            margin=dict(l=120, r=0, t=8, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
        most_dep = rows[0]
        least_dep = rows[-1]
        st.caption(
            f"{most_dep['company']} derives {most_dep['ad_pct']:.0f}% of its revenue from advertising — "
            f"it is, functionally, an advertising company. {least_dep['company']} sits at "
            f"{least_dep['ad_pct']:.1f}% — barely reliant on ads despite its scale."
        )
    except Exception:
        st.info("Ad dependency chart unavailable.")


_beat(_screen6, label="The Dependency", headline="Some live and die by advertising. Others barely care.")


# Screen 7
def _screen7():
    try:
        import plotly.graph_objects as go

        if total_tracked_b <= 0:
            st.info("Duopoly chart unavailable.")
            return
        duo_musd = float(ad_lookup.get("Alphabet", {}).get("ad_revenue_musd", 0.0))
        duo_musd += float(ad_lookup.get("Meta Platforms", {}).get("ad_revenue_musd", 0.0))
        duo_b = duo_musd / 1e3
        rest_b = max(total_tracked_b - duo_b, 0.0)
        duo_pct = duo_b / total_tracked_b * 100 if total_tracked_b else 0
        fig = go.Figure(
            go.Pie(
                values=[duo_b, rest_b],
                labels=["Alphabet + Meta", "Everyone Else"],
                hole=0.65,
                marker=dict(colors=["#ff5b1f", "rgba(255,255,255,0.08)"]),
                textfont=dict(color="white"),
                hovertemplate="%{label}: $%{value:.0f}B (%{percent})<extra></extra>",
            )
        )
        fig.update_layout(
            annotations=[
                dict(
                    text=f"<b>{duo_pct:.1f}%</b><br><span style='font-size:10px'>Duopoly</span>",
                    x=0.5,
                    y=0.5,
                    font_size=22,
                    font_color="white",
                    showarrow=False,
                )
            ],
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            legend=dict(font=dict(color="white")),
            height=340,
            margin=dict(l=0, r=0, t=8, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Alphabet and Meta together controlled {duo_pct:.1f}% of all tracked digital ad revenue in {effective_year}. "
            f"Combined: ${duo_b:.0f}B. The rest of the tracked universe: ${rest_b:.0f}B."
        )
    except Exception:
        st.info("Duopoly chart unavailable.")


_beat(_screen7, label="The Duopoly", headline="Two companies. One grip.")


# Screen 8
def _screen8():
    try:
        import plotly.graph_objects as go

        if m2_yearly_df.empty or groupm_df.empty or not groupm_year_col or not groupm_total_col:
            st.info("M2 vs Ad Spend chart unavailable.")
            return
        m2_df = m2_yearly_df.copy()
        m2_df["year"] = pd.to_numeric(m2_df["year"], errors="coerce").astype("Int64")
        m2_df["m2_value"] = pd.to_numeric(m2_df["m2_value"], errors="coerce")
        m2_df = m2_df.dropna(subset=["year", "m2_value"]).copy()
        if m2_df.empty:
            st.info("M2 vs Ad Spend chart unavailable.")
            return
        m2_df["year"] = m2_df["year"].astype(int)

        g_years = groupm_df[[groupm_year_col, groupm_total_col]].copy()
        g_years.columns = ["year", "ad_total"]
        g_years["year"] = pd.to_numeric(g_years["year"], errors="coerce").astype("Int64")
        g_years["ad_total"] = pd.to_numeric(g_years["ad_total"], errors="coerce")
        g_years = g_years.dropna(subset=["year", "ad_total"]).copy()
        if g_years.empty:
            st.info("M2 vs Ad Spend chart unavailable.")
            return
        g_years["year"] = g_years["year"].astype(int)

        merged = m2_df.merge(g_years, on="year", how="inner")
        merged = merged[merged["year"] >= 2010].sort_values("year")
        if merged.empty:
            st.info("M2 vs Ad Spend chart unavailable.")
            return
        base_year = 2010 if (merged["year"] == 2010).any() else int(merged["year"].min())
        base_m2 = float(merged[merged["year"] == base_year]["m2_value"].iloc[0])
        base_ad = float(merged[merged["year"] == base_year]["ad_total"].iloc[0])
        if base_m2 <= 0 or base_ad <= 0:
            st.info("M2 vs Ad Spend chart unavailable.")
            return
        merged["m2_idx"] = merged["m2_value"] / base_m2 * 100
        merged["ad_idx"] = merged["ad_total"] / base_ad * 100

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=merged["year"],
                y=merged["m2_idx"],
                name="M2 Money Supply (indexed)",
                line=dict(color="#3b82f6", width=2.5),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=merged["year"],
                y=merged["ad_idx"],
                name="Global Ad Spend (indexed)",
                line=dict(color="#ff9900", width=2.5),
                yaxis="y2",
            )
        )
        fig.add_vrect(
            x0=2020,
            x1=2021,
            fillcolor="rgba(255,255,255,0.05)",
            line_width=0,
            annotation_text="2020 stimulus",
            annotation_font_color="rgba(255,255,255,0.4)",
        )
        fig.update_layout(
            yaxis=dict(title="M2 (indexed, 2010=100)", color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
            yaxis2=dict(title="Ad Spend (indexed)", overlaying="y", side="right", color="rgba(255,255,255,0.4)"),
            xaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            legend=dict(font=dict(color="white")),
            height=360,
            margin=dict(l=0, r=60, t=8, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Both M2 money supply and global ad spend indexed to 2010 = 100. "
            "The near-perfect correlation shows macro liquidity as a leading indicator for ad market growth."
        )
    except Exception:
        st.info("M2 vs Ad Spend chart unavailable.")


_beat(_screen8, label="The Money Printer", headline="When central banks print, ad markets follow.")


# Screen 9
def _screen9():
    try:
        import plotly.graph_objects as go

        if groupm_df.empty or not groupm_year_col:
            st.info("Structural shift chart unavailable.")
            return
        g_df = groupm_df.copy()
        g_df[groupm_year_col] = pd.to_numeric(g_df[groupm_year_col], errors="coerce")
        g_df = g_df.dropna(subset=[groupm_year_col]).copy()
        g_df[groupm_year_col] = g_df[groupm_year_col].astype(int)
        g_df = g_df[g_df[groupm_year_col] >= 2010].sort_values(groupm_year_col)
        if g_df.empty:
            st.info("Structural shift chart unavailable.")
            return

        channels = {
            "Traditional TV": ("#4472c4", _find_groupm_col(g_df, ["traditional", "tv"])),
            "Connected TV": ("#00bcd4", _find_groupm_col(g_df, ["connected", "tv"])),
            "Search": ("#ff9900", _find_groupm_col(g_df, ["search"], ["non"])),
            "Non-Search": ("#ffd600", _find_groupm_col(g_df, ["non", "search"])),
            "Retail Media": ("#22c55e", _find_groupm_col(g_df, ["retail"])),
            "Traditional OOH": ("#888888", _find_groupm_col(g_df, ["traditional", "ooh"])),
            "Digital OOH": ("#26a69a", _find_groupm_col(g_df, ["digital", "ooh"])),
        }
        fig = go.Figure()
        for channel, (color, col_match) in channels.items():
            if not col_match:
                continue
            values = pd.to_numeric(g_df[col_match], errors="coerce")
            if values.notna().sum() == 0:
                continue
            fig.add_trace(
                go.Scatter(
                    x=g_df[groupm_year_col],
                    y=values,
                    name=channel,
                    stackgroup="one",
                    line=dict(width=0),
                    fillcolor=color,
                    hovertemplate=f"{channel}: $%{{y:.0f}}B<extra></extra>",
                )
            )
        if not fig.data:
            st.info("Structural shift chart unavailable.")
            return
        retail_col = channels.get("Retail Media", ("", ""))[1]
        if retail_col:
            retail_2022 = g_df[g_df[groupm_year_col] == 2022][retail_col]
            if not retail_2022.empty and pd.notna(retail_2022.iloc[0]):
                fig.add_annotation(
                    x=2022,
                    y=float(retail_2022.iloc[0]),
                    text="Retail Media emerges",
                    showarrow=True,
                    arrowcolor="white",
                    font=dict(color="white", size=11),
                    arrowhead=2,
                )
        fig.update_layout(
            xaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)", ticksuffix="B"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            legend=dict(font=dict(color="white")),
            height=380,
            margin=dict(l=0, r=0, t=8, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Linear TV declining while Search and Retail Media accelerate. "
            "CTV growing but from a small base. Retail Media as a category barely existed before 2018."
        )
    except Exception:
        st.info("Structural shift chart unavailable.")


_beat(_screen9, label="The Structural Shift", headline="The ad market didn't just grow. It transformed.")


# Screen 10
def _screen10():
    try:
        import plotly.graph_objects as go

        if groupm_df.empty or not groupm_year_col:
            st.info("Search vs Traditional chart unavailable.")
            return
        g_row_val = _yr(groupm_df, effective_year, groupm_year_col)
        if g_row_val.empty:
            st.info("Search vs Traditional chart unavailable.")
            return
        search_col = _find_groupm_col(groupm_df, ["search"], ["non"])
        if not search_col:
            st.info("Search vs Traditional chart unavailable.")
            return

        trad_cols = []
        for c in groupm_df.columns:
            norm = re.sub(r"[^a-z0-9]+", "", str(c).lower())
            if c == groupm_year_col or c == search_col:
                continue
            if ("traditionaltv" in norm) or ("radio" in norm) or ("print" in norm) or ("newspaper" in norm):
                trad_cols.append(c)
        if not trad_cols:
            st.info("Search vs Traditional chart unavailable.")
            return
        search_b = float(pd.to_numeric(g_row_val[search_col], errors="coerce").iloc[0] or 0.0)
        trad_b = 0.0
        for c in trad_cols:
            value = pd.to_numeric(g_row_val[c], errors="coerce").iloc[0]
            if pd.notna(value):
                trad_b += float(value)
        if search_b <= 0 and trad_b <= 0:
            st.info("Search vs Traditional chart unavailable.")
            return
        ratio = search_b / trad_b if trad_b > 0 else None
        fig = go.Figure(
            go.Bar(
                x=[search_b, trad_b],
                y=["Search", "Traditional (TV+Radio+Print)"],
                orientation="h",
                marker=dict(color=["#ff9900", "#4472c4"]),
                text=[f"${search_b:.0f}B", f"${trad_b:.0f}B"],
                textposition="outside",
                textfont=dict(color="white"),
                hovertemplate="%{y}: $%{x:.0f}B<extra></extra>",
            )
        )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(color="white"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            height=200,
            margin=dict(l=0, r=60, t=8, b=8),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
        caption = f"Search advertising alone accounts for ${search_b:.0f}B in {effective_year}."
        if ratio:
            caption += f" That is {ratio:.1f}× larger than all traditional TV, radio, and print combined."
        st.caption(caption)
    except Exception:
        st.info("Search vs Traditional chart unavailable.")


_beat(_screen10, label="Search Dominance", headline="Search alone beats all traditional media combined.")


# Screen 11
def _screen11():
    try:
        if metrics.empty:
            st.info("Bubble chart unavailable.")
            return
        metric_years = sorted(metrics["year"].dropna().astype(int).unique().tolist())
        if not metric_years:
            st.info("Bubble chart unavailable.")
            return
        all_rows = []
        for yr_val in metric_years:
            m = metrics[metrics["year"] == yr_val].copy()
            p_m = metrics[metrics["year"] == (yr_val - 1)].copy()
            ad_lookup_year = _load_ad_revenue_by_company(excel_path, source_stamp, int(yr_val)) if excel_path else {}
            for _, row in m.iterrows():
                company = str(row.get("company", ""))
                rev = float(pd.to_numeric(pd.Series([row.get("revenue", np.nan)]), errors="coerce").iloc[0] or 0.0)
                prev_block = p_m[p_m["company"] == company]
                prev_rev = None
                if not prev_block.empty:
                    prev_val = pd.to_numeric(pd.Series([prev_block.iloc[0].get("revenue", np.nan)]), errors="coerce").iloc[0]
                    prev_rev = float(prev_val) if pd.notna(prev_val) else None
                rev_yoy = _yoy(rev, prev_rev) or 0.0
                mcap = float(pd.to_numeric(pd.Series([row.get("market_cap", np.nan)]), errors="coerce").iloc[0] or 0.0)
                ad_rev_musd = float(ad_lookup_year.get(company, {}).get("ad_revenue_musd", 0.0))
                ad_pct = min((ad_rev_musd / rev * 100) if rev > 0 else 0.0, 100.0)
                all_rows.append(
                    {
                        "year": str(int(yr_val)),
                        "company": company,
                        "rev_yoy": rev_yoy,
                        "market_cap_b": mcap / 1e3,
                        "ad_pct": max(ad_pct, 1.0),
                        "revenue_b": rev / 1e3,
                        "ad_rev_b": ad_rev_musd / 1e3,
                    }
                )
        bubble_df = pd.DataFrame(all_rows).dropna(subset=["company", "year", "market_cap_b", "rev_yoy"])
        if bubble_df.empty:
            st.info("Bubble chart unavailable.")
            return
        company_colors = {company: _company_color(company) for company in bubble_df["company"].unique()}
        fig = px.scatter(
            bubble_df,
            x="rev_yoy",
            y="market_cap_b",
            size="ad_pct",
            color="company",
            color_discrete_map=company_colors,
            animation_frame="year",
            animation_group="company",
            hover_name="company",
            custom_data=["revenue_b", "ad_pct", "ad_rev_b"],
            size_max=65,
            labels={"rev_yoy": "Revenue YoY Growth (%)", "market_cap_b": "Market Cap ($B)"},
        )
        fig.update_traces(
            hovertemplate=(
                "<b>%{hovertext}</b><br>"
                "Market Cap: $%{y:.0f}B<br>"
                "Rev YoY: %{x:+.1f}%<br>"
                "Ad Dependency: %{customdata[1]:.1f}%<br>"
                "Ad Revenue: $%{customdata[2]:.1f}B<extra></extra>"
            )
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            legend=dict(font=dict(color="white")),
            height=580,
            margin=dict(l=0, r=0, t=8, b=40),
            xaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)", zeroline=True, zerolinecolor="rgba(255,255,255,0.15)"),
            yaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
        )
        st.plotly_chart(fig, use_container_width=True)
        latest_b = bubble_df[bubble_df["year"] == str(effective_year)]
        if not latest_b.empty:
            top_mcap = latest_b.nlargest(1, "market_cap_b").iloc[0]
            most_ad = latest_b.nlargest(1, "ad_pct").iloc[0]
            st.caption(
                f"Bubble size = ad revenue dependency. {top_mcap['company']} leads on market cap at "
                f"${top_mcap['market_cap_b']:.0f}B. {most_ad['company']} is most ad-dependent at "
                f"{most_ad['ad_pct']:.1f}% of total revenue."
            )
    except Exception:
        st.info("Bubble chart unavailable.")


_beat(_screen11, label="The Landscape", headline="Not all Big Tech is equal. Who won?")


# Screen 12
def _screen12():
    try:
        import plotly.graph_objects as go
        from utils.live_stock_feed import build_live_company_ticker_map, infer_company_label, load_live_stock_feed

        if metrics.empty:
            st.info("Performance chart unavailable.")
            return
        min_year = int(metrics["year"].min())
        y_start = max(effective_year - 3, min_year)
        start_df = metrics[metrics["year"] == y_start][["company", "market_cap"]]
        end_df = metrics[metrics["year"] == effective_year][["company", "market_cap"]]
        perf = start_df.merge(end_df, on="company", suffixes=("_start", "_end"))
        if perf.empty:
            st.info("Performance chart unavailable.")
            return
        perf["tsr"] = _yoy_vec(perf["market_cap_end"], perf["market_cap_start"])
        perf = perf.dropna(subset=["tsr"]).copy()
        if perf.empty:
            st.info("Performance chart unavailable.")
            return
        top3 = perf.nlargest(3, "tsr")["company"].tolist()
        if not top3:
            st.info("Performance chart unavailable.")
            return

        feed = load_live_stock_feed()
        if feed.empty:
            st.info("Performance chart unavailable.")
            return
        feed = feed.copy()
        feed["date"] = pd.to_datetime(feed["date"], errors="coerce")
        feed["price"] = pd.to_numeric(feed["price"], errors="coerce")
        feed["tag"] = feed["tag"].astype(str).str.strip()
        feed = feed.dropna(subset=["date", "price"])
        if feed.empty:
            st.info("Performance chart unavailable.")
            return

        company_ticker_map = {v: k for k, v in build_live_company_ticker_map().items()}
        if not company_ticker_map:
            for tag, grp in feed.groupby("tag"):
                if grp.empty:
                    continue
                label = infer_company_label(grp.iloc[-1].get("asset", ""), tag)
                if label and label not in company_ticker_map:
                    company_ticker_map[label] = tag

        fig = go.Figure()
        idx_styles = [("^GSPC", "S&P 500", "white", "dash"), ("^IXIC", "Nasdaq", "#ff9900", "dot")]
        for ticker, label, color, dash in idx_styles:
            idx_feed = feed[feed["tag"] == ticker].sort_values("date")
            if idx_feed.empty:
                continue
            base = float(idx_feed.iloc[0]["price"])
            idx_feed = idx_feed.copy()
            idx_feed["norm"] = idx_feed["price"] / base * 100
            fig.add_trace(
                go.Scatter(
                    x=idx_feed["date"],
                    y=idx_feed["norm"],
                    name=label,
                    line=dict(color=color, dash=dash, width=1.5),
                    hovertemplate=f"{label}: %{{y:.0f}}<extra></extra>",
                )
            )
        for company in top3:
            ticker = company_ticker_map.get(company)
            if not ticker:
                continue
            co_feed = feed[feed["tag"] == ticker].sort_values("date")
            if co_feed.empty:
                continue
            base = float(co_feed.iloc[0]["price"])
            co_feed = co_feed.copy()
            co_feed["norm"] = co_feed["price"] / base * 100
            fig.add_trace(
                go.Scatter(
                    x=co_feed["date"],
                    y=co_feed["norm"],
                    name=company,
                    line=dict(color=_company_color(company), width=2.5),
                    hovertemplate=f"{company}: %{{y:.0f}}<extra></extra>",
                )
            )
        if not fig.data:
            st.info("Performance chart unavailable.")
            return
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            legend=dict(font=dict(color="white")),
            height=360,
            yaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
            xaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
            margin=dict(l=0, r=0, t=8, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
        best = perf.nlargest(1, "tsr").iloc[0]
        st.caption(
            f"Normalized to 100 at start. Top 3 market cap growers vs S&P500 and Nasdaq. "
            f"{best['company']} led with +{best['tsr']:.0f}% market cap growth over {y_start}→{effective_year}."
        )
    except Exception:
        st.info("Performance chart unavailable.")


_beat(_screen12, label="The Market Bet", headline="The ad-driven giants didn't just grow. They beat the market.")


# Screen 13
def _screen13():
    try:
        import plotly.graph_objects as go

        if metrics.empty:
            st.info("Market cap chart unavailable.")
            return
        y_then = effective_year - 5
        then_df = metrics[metrics["year"] == y_then][["company", "market_cap"]]
        now_df = metrics[metrics["year"] == effective_year][["company", "market_cap"]]
        comp = then_df.merge(now_df, on="company", suffixes=("_then", "_now"))
        if comp.empty:
            st.info("Market cap chart unavailable.")
            return
        comp = comp.sort_values("market_cap_now", ascending=True)
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                y=comp["company"],
                x=comp["market_cap_then"] / 1e3,
                name=str(y_then),
                orientation="h",
                marker=dict(color="rgba(255,255,255,0.2)"),
                hovertemplate="%{y} " + str(y_then) + ": $%{x:.0f}B<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                y=comp["company"],
                x=comp["market_cap_now"] / 1e3,
                name=str(effective_year),
                orientation="h",
                marker=dict(color="#ff5b1f"),
                hovertemplate="%{y} " + str(effective_year) + ": $%{x:.0f}B<extra></extra>",
            )
        )
        fig.update_layout(
            barmode="overlay",
            xaxis=dict(tickprefix="$", ticksuffix="B", color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(color="white"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            legend=dict(font=dict(color="white")),
            height=400,
            margin=dict(l=120, r=0, t=8, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
        total_then = comp["market_cap_then"].sum() / 1e6
        total_now = comp["market_cap_now"].sum() / 1e6
        growth = _yoy(total_now, total_then)
        caption = (
            f"Combined market cap grew from ${total_then:.1f}T to ${total_now:.1f}T "
            f"between {y_then} and {effective_year}."
        )
        if growth:
            caption += f" That's a +{growth:.0f}% increase over 5 years."
        st.caption(caption)
    except Exception:
        st.info("Market cap chart unavailable.")


_beat(_screen13, label="The Wealth Machine", headline="The market cap story, then vs now.")


# Screen 14
def _screen14():
    try:
        sub_df = _read_excel_sheet_cached(excel_path, "Company_subscribers_values", source_stamp) if excel_path else pd.DataFrame()
        if sub_df.empty:
            st.info("Subscriber data unavailable.")
            return
        sub_df = sub_df.copy()
        sub_df.columns = [str(c).strip() for c in sub_df.columns]
        year_col = ""
        for c in sub_df.columns:
            if "year" in c.lower():
                year_col = c
                break
        scope = sub_df.copy()
        if year_col:
            scope = _yr(sub_df, effective_year, year_col)
            if scope.empty:
                scope = sub_df.copy()

        streaming = ["Netflix", "Spotify", "Disney", "Paramount"]
        rows_html = []
        total_subs = 0.0
        company_col = ""
        for c in scope.columns:
            if c.lower() in {"company", "service", "platform"}:
                company_col = c
                break
        subs_col = ""
        for c in scope.columns:
            if "subscriber" in c.lower():
                subs_col = c
                break

        if company_col and subs_col:
            scope[subs_col] = pd.to_numeric(scope[subs_col], errors="coerce")
            scope = scope.dropna(subset=[company_col, subs_col]).copy()
            for company in streaming:
                rows = scope[scope[company_col].astype(str).str.lower().str.contains(company.lower(), na=False)]
                if rows.empty:
                    continue
                subs_m = float(rows[subs_col].sum())
                total_subs += subs_m
                icons = "●" * min(max(int(subs_m / 10), 1), 30)
                rows_html.append(
                    f"<div style='margin-bottom:12px;'>"
                    f"<span style='color:white;font-weight:600;display:inline-block;width:120px;'>{escape(company)}</span>"
                    f"<span style='color:#ff5b1f;letter-spacing:2px;'>{icons}</span>"
                    f"<span style='color:rgba(255,255,255,0.5);font-size:0.85rem;margin-left:8px;'>{subs_m:.0f}M</span>"
                    f"</div>"
                )
        else:
            row = scope.iloc[-1]
            for company in streaming:
                matches = [c for c in scope.columns if company.lower() in c.lower()]
                if not matches:
                    continue
                subs_val = pd.to_numeric(pd.Series([row[matches[0]]]), errors="coerce").iloc[0]
                if pd.isna(subs_val):
                    continue
                subs_m = float(subs_val)
                total_subs += subs_m
                icons = "●" * min(max(int(subs_m / 10), 1), 30)
                rows_html.append(
                    f"<div style='margin-bottom:12px;'>"
                    f"<span style='color:white;font-weight:600;display:inline-block;width:120px;'>{escape(company)}</span>"
                    f"<span style='color:#ff5b1f;letter-spacing:2px;'>{icons}</span>"
                    f"<span style='color:rgba(255,255,255,0.5);font-size:0.85rem;margin-left:8px;'>{subs_m:.0f}M</span>"
                    f"</div>"
                )
        if not rows_html:
            st.info("Subscriber data unavailable.")
            return
        st.markdown(
            "<div style='padding:8px 0;'>"
            + "".join(rows_html)
            + "<div style='color:rgba(255,255,255,0.3);font-size:0.75rem;margin-top:8px;'>● = 10M subscribers</div>"
            + "</div>",
            unsafe_allow_html=True,
        )
        china_pop = 1400
        st.caption(
            f"Combined paid subscribers: {total_subs:.0f}M — "
            f"{'more than' if total_subs > china_pop else 'approaching'} the population of China ({china_pop}M)."
        )
    except Exception:
        st.info("Subscriber data unavailable.")


_beat(_screen14, label="The Human Side", headline="Behind every dollar: a human being.")


# Screen 15
def _screen15():
    try:
        min_df = _read_excel_sheet_cached(excel_path, "Company_minute&dollar_earned", source_stamp) if excel_path else pd.DataFrame()
        if min_df.empty:
            st.info("Revenue ticker unavailable.")
            return
        min_df = min_df.copy()
        min_df.columns = [str(c).strip() for c in min_df.columns]
        year_col = ""
        for c in min_df.columns:
            if "year" in c.lower():
                year_col = c
                break
        scoped = min_df.copy()
        if year_col:
            scoped = _yr(min_df, effective_year, year_col)
            if scoped.empty:
                scoped = min_df.copy()
        platform_col = ""
        for c in scoped.columns:
            if c.lower() in {"platform", "company", "service", "asset"}:
                platform_col = c
                break
        revenue_col = ""
        for c in scoped.columns:
            norm = c.lower()
            if "revenue" in norm and ("$b" in norm or "usd" in norm or "$" in norm):
                revenue_col = c
                break
        if not revenue_col:
            for c in scoped.columns:
                if "revenue" in c.lower():
                    revenue_col = c
                    break
        if not platform_col or not revenue_col:
            st.info("Revenue ticker unavailable.")
            return

        ticker_companies = ["Alphabet", "Meta", "Amazon", "Apple", "Microsoft"]
        rows_html = []
        total_rps = 0.0
        scoped[revenue_col] = pd.to_numeric(scoped[revenue_col], errors="coerce")
        for company in ticker_companies:
            rows = scoped[scoped[platform_col].astype(str).str.lower().str.contains(company.lower(), na=False)]
            if rows.empty:
                continue
            revenue_b = float(rows[revenue_col].iloc[0])
            if revenue_b <= 0:
                continue
            rps = (revenue_b * 1e9) / (365 * 24 * 3600)
            total_rps += rps
            rows_html.append(
                f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;"
                f"border-bottom:1px solid rgba(255,255,255,0.06);padding-bottom:12px;'>"
                f"<span style='color:white;font-weight:600;'>{escape(company)}</span>"
                f"<span class='ticker-val' data-rps='{rps:.4f}'>$0</span>"
                f"</div>"
            )
        if not rows_html:
            st.info("Revenue ticker unavailable.")
            return
        rows_html.append(
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-top:8px;'>"
            f"<span style='color:rgba(255,255,255,0.5);font-size:0.9rem;'>Combined</span>"
            f"<span class='ticker-val' style='color:white;' data-rps='{total_rps:.4f}'>$0</span>"
            f"</div>"
        )
        st.markdown("<div style='padding:8px 0;'>" + "".join(rows_html) + "</div>", unsafe_allow_html=True)
        st.caption(
            f"Based on {effective_year} annual revenue ÷ seconds per year. Numbers update every 100ms since you opened this page."
        )
    except Exception:
        st.info("Revenue ticker unavailable.")


_beat(_screen15, label="The Clock", headline="Every second you've been reading this...")


# Screen 16
def _screen16():
    _render_transcript_pulse_strip()


_beat(
    _screen16,
    label="The Human Voice",
    headline="Here's what the people running these companies actually said.",
)


# Screen 17
st.markdown(
    "<div class='scroll-reveal story-beat' style='text-align:center;'>"
    "<div class='beat-label'>Your Turn</div>"
    "<div class='beat-headline'>Go deeper.</div>"
    "<div class='beat-body'>Pick your path.</div>"
    "</div>",
    unsafe_allow_html=True,
)
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Overview — Macro and Market", key="home_gateway_overview"):
        st.switch_page("pages/00_Overview.py")
with col2:
    if st.button("Earnings — Company Deep Dives", key="home_gateway_earnings"):
        st.switch_page("pages/01_Earnings.py")
with col3:
    if st.button("Genie — Ask the Data", key="home_gateway_genie"):
        st.switch_page("pages/04_Genie.py")

source_label = str(workbook_path) if workbook_path else "not found"
st.markdown(
    f"<div class='wm-foot'>Source: {escape(source_label)} • Period baseline: {effective_year} {selected_quarter}</div>",
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)
