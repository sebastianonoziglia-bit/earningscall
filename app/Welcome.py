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
st.markdown(
    """
<style>
section[data-testid="stMain"] > div {
    background-color: #0d1117 !important;
}
section[data-testid="stMain"] {
    background-color: #0d1117 !important;
}
section[data-testid="stMain"] p,
section[data-testid="stMain"] span,
section[data-testid="stMain"] div,
section[data-testid="stMain"] label {
    color: rgba(255,255,255,0.85);
}
section[data-testid="stMain"] .stCaption p {
    color: rgba(255,255,255,0.45) !important;
    font-size: 0.82rem;
}
.wm-wrap {
    max-width: 1500px;
    margin: 0 auto;
    padding: 0 14px 36px;
}
.sv {
    opacity: 0;
    transform: translateY(22px);
    transition: opacity .6s ease, transform .6s ease;
}
.sv.sv-visible {
    opacity: 1;
    transform: translateY(0);
}
.beat-divider {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.07);
    margin: 48px 0;
}
.beat-label {
    color: #ff5b1f;
    font-size: 0.72rem;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    margin-bottom: 6px;
    display: block;
}
.beat-headline {
    color: white;
    font-size: 1.55rem;
    font-weight: 700;
    line-height: 1.25;
    margin-bottom: 20px;
    display: block;
}
.beat-body {
    color: rgba(255,255,255,0.6);
    font-size: 1rem;
    line-height: 1.8;
    margin-bottom: 20px;
}
.kpi-card {
    background: rgba(30, 60, 100, 0.35);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 28px 20px;
    text-align: center;
    margin-bottom: 8px;
}
.ticker-val {
    color: #ff5b1f;
    font-family: monospace;
    font-size: 1.6rem;
    font-weight: 800;
}
.sub-row {
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 10px;
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
.wm-pulse-strip,
.wm-stock-strip {
    width: 100%;
    overflow: hidden;
    border-radius: 12px;
    border: 1px solid rgba(148,163,184,0.24);
    background: rgba(6,11,20,0.92);
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
}
.wm-stock-item {
    width: min(300px, 78vw);
    flex: 0 0 auto;
    border-radius: 10px;
    border: 1px solid rgba(148,163,184,0.22);
    background: rgba(15,23,42,0.72);
    padding: 7px 10px;
}
.wm-pulse-quote {
    color: #e2e8f0;
    font-style: italic;
    font-size: 0.85rem;
    line-height: 1.45;
}
.wm-pulse-meta,
.wm-stock-meta {
    margin-top: 8px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 0.75rem;
}
.wm-stock-meta {
    margin-top: 0;
}
.wm-pulse-company {
    color: #FFFFFF !important;
    font-weight: 700;
}
.wm-pulse-speaker {
    color: rgba(255,255,255,0.75) !important;
}
.wm-stock-price {
    margin-left: auto;
    color: #ffffff !important;
    font-family: monospace;
    font-size: 0.92rem;
    font-weight: 700;
}
.wm-stock-change {
    color: rgba(255,255,255,0.64) !important;
    font-size: 0.72rem;
}
.wm-foot {
    margin-top: 32px;
    padding-top: 14px;
    border-top: 1px solid rgba(148,163,184,0.25);
    color: rgba(255,255,255,0.45);
    font-size: 0.84rem;
    text-align: center;
}
.gateway-btn-row {
    display: flex;
    gap: 16px;
    justify-content: center;
    margin-top: 24px;
}
@keyframes wmPulseScroll {
    from { transform: translateX(0); }
    to { transform: translateX(-50%); }
}
@media (max-width: 768px) {
    .wm-wrap { padding: 0 6px 24px; }
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
const _revealObs = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) e.target.classList.add('sv-visible');
  });
}, { threshold: 0.08 });
document.querySelectorAll('.sv').forEach(el => _revealObs.observe(el));

function _startTicker() {
  const els = document.querySelectorAll('[data-rps]');
  if (!els.length) { setTimeout(_startTicker, 300); return; }
  const t0 = Date.now();
  setInterval(() => {
    const elapsed = (Date.now() - t0) / 1000;
    document.querySelectorAll('[data-rps]').forEach(el => {
      const rps = parseFloat(el.getAttribute('data-rps'));
      el.textContent = '$' + (rps * elapsed).toLocaleString('en-US',
        {minimumFractionDigits:0, maximumFractionDigits:0});
    });
  }, 120);
}
_startTicker();
</script>
""",
    height=0,
)


def _yr(df, year, year_col="year"):
    row = df[df[year_col] == year] if (df is not None and not df.empty and year_col in df.columns) else pd.DataFrame()
    if row.empty and isinstance(df, pd.DataFrame) and not df.empty and year_col in df.columns:
        max_year = pd.to_numeric(df[year_col], errors="coerce").max()
        if pd.notna(max_year):
            row = df[pd.to_numeric(df[year_col], errors="coerce") == int(max_year)]
    return row


def _yoy(current, previous):
    if previous and previous > 0:
        return (current - previous) / previous * 100
    return None


def _yoy_vec(current_series, prev_series):
    return ((pd.to_numeric(current_series, errors="coerce") - pd.to_numeric(prev_series, errors="coerce"))
            / pd.to_numeric(prev_series, errors="coerce") * 100).where(pd.to_numeric(prev_series, errors="coerce") > 0, np.nan)


def _yoy_html(yoy):
    if yoy is None or pd.isna(yoy):
        return ""
    arrow = "▲" if yoy >= 0 else "▼"
    color = "#22c55e" if yoy >= 0 else "#ef4444"
    return f'<span style="color:{color};font-size:0.85rem;">{arrow} {abs(float(yoy)):.1f}% YoY</span>'


def _comment_growth(metric_name, yoy):
    if yoy is None or pd.isna(yoy):
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


def _beat_header(label, headline):
    st.markdown(
        f"<div class='sv'>"
        f"<span class='beat-label' style='color:#ff5b1f;'>{escape(str(label))}</span>"
        f"<span class='beat-headline' style='color:#ffffff;'>{escape(str(headline))}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _beat_body(text):
    st.markdown(
        f"<div class='beat-body' style='color:rgba(255,255,255,0.6);'>{text}</div>",
        unsafe_allow_html=True,
    )


def _beat_divider():
    st.markdown("<hr class='beat-divider'>", unsafe_allow_html=True)


def _kpi_card(title, value_str, yoy_html, subtitle):
    return f"""
    <div class="kpi-card">
      <div style="color:rgba(255,255,255,0.4);font-size:0.72rem;
                  letter-spacing:0.12em;text-transform:uppercase;
                  margin-bottom:10px;">{escape(str(title))}</div>
      <div style="color:#ff5b1f;font-size:2.2rem;font-weight:900;
                  font-family:monospace;margin-bottom:8px;">{escape(str(value_str))}</div>
      <div style="min-height:20px;">{yoy_html}</div>
      <div style="color:rgba(255,255,255,0.25);font-size:0.7rem;
                  margin-top:10px;">{escape(str(subtitle))}</div>
    </div>
    """


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


def _chart_layout(height: int, extra: Optional[dict] = None) -> dict:
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(10,20,40,0.5)",
        font=dict(color="white"),
        height=height,
    )
    if extra:
        base.update(extra)
    return base


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


def _load_market_feed() -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    minute_raw = _read_excel_sheet_cached(excel_path, "Minute", source_stamp)
    daily_raw = _read_excel_sheet_cached(excel_path, "Daily", source_stamp)
    minute_df = _normalize_market_feed(minute_raw)
    daily_df = _normalize_market_feed(daily_raw)
    combined = pd.concat([minute_df, daily_df], ignore_index=True)
    if combined.empty:
        return pd.DataFrame()
    combined = combined.sort_values("date")
    dedup_keys = ["date"]
    if "tag" in combined.columns:
        dedup_keys.append("tag")
    if "asset" in combined.columns:
        dedup_keys.append("asset")
    combined = combined.drop_duplicates(subset=dedup_keys, keep="last")
    return combined


def _render_transcript_pulse_strip(current_year: int, current_quarter: str) -> None:
    pulse_df, pulse_source = _load_transcript_pulse_quotes(
        repo_root_path=str(ROOT_DIR),
        db_path=str(db_path),
        selected_year=int(current_year),
        selected_quarter=current_quarter,
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
            else "<span class='wm-mini-logo' style='display:inline-flex;align-items:center;justify-content:center;color:#fff;'>•</span>"
        )
        pulse_items.append(
            "<div class='wm-pulse-item'>"
            f"<div class='wm-pulse-quote' style='color:#e2e8f0;'>“{escape(quote)}”</div>"
            f"<div class='wm-pulse-meta'>{logo_html}<span class='wm-pulse-company' style='color:#fff;'>{escape(company)}</span>"
            f"<span class='wm-pulse-speaker' style='color:rgba(255,255,255,0.75);'>— {escape(speaker)}</span></div>"
            "</div>"
        )
    if not pulse_items:
        st.info("No transcript data available yet — run the intelligence pipeline first.")
        return
    st.markdown(
        f"<div class='wm-pulse-strip'><div class='wm-pulse-track'>{''.join(pulse_items + pulse_items)}</div></div>",
        unsafe_allow_html=True,
    )
    if pulse_source:
        st.caption(f"Source: {pulse_source}")


def _render_stock_price_strip(feed_df: pd.DataFrame) -> None:
    if feed_df is None or feed_df.empty:
        st.info("Market ticker unavailable.")
        return
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
    items = []
    for company, ticker in company_ticker_fallback.items():
        subset = feed_df[feed_df["tag"].astype(str).str.upper() == ticker]
        if subset.empty:
            subset = feed_df[feed_df["asset"].astype(str).str.lower().str.contains(company.lower(), na=False)]
        if subset.empty:
            continue
        last = subset.sort_values("date").iloc[-1]
        price = float(last.get("price", np.nan))
        if pd.isna(price):
            continue
        change = pd.to_numeric(pd.Series([last.get("change", np.nan)]), errors="coerce").iloc[0]
        change_txt = f"{change:+.2f}%" if pd.notna(change) else "n/a"
        logo_b64 = _resolve_logo(company, logos)
        logo_html = (
            f"<img class='wm-mini-logo' src='data:image/png;base64,{logo_b64}' alt='{escape(company)} logo' />"
            if logo_b64
            else "<span class='wm-mini-logo' style='display:inline-flex;align-items:center;justify-content:center;color:#fff;'>•</span>"
        )
        items.append(
            "<div class='wm-stock-item'>"
            f"<div class='wm-stock-meta'>{logo_html}"
            f"<span style='color:#fff;font-weight:700;font-size:0.8rem;'>{escape(company)}</span>"
            f"<span class='wm-stock-price' style='color:#fff;'>${price:,.2f}</span></div>"
            f"<div class='wm-stock-change' style='color:rgba(255,255,255,0.64);'>{escape(change_txt)} · {escape(ticker)}</div>"
            "</div>"
        )
    if not items:
        st.info("Market ticker unavailable.")
        return
    st.markdown(
        f"<div class='wm-stock-strip'><div class='wm-stock-track'>{''.join(items + items)}</div></div>",
        unsafe_allow_html=True,
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

groupm_df = _read_excel_sheet_cached(excel_path, "Global Advertising (GroupM)", source_stamp) if excel_path else pd.DataFrame()
if not groupm_df.empty:
    groupm_df.columns = [str(c).strip() for c in groupm_df.columns]
groupm_year_col = _find_col(groupm_df, ["year"]) if not groupm_df.empty else ""
groupm_total_col = _find_col(groupm_df, ["total"]) if not groupm_df.empty else ""
if not groupm_df.empty and groupm_year_col and not groupm_total_col:
    numeric_candidates = []
    for c in groupm_df.columns:
        if c == groupm_year_col:
            continue
        vals = pd.to_numeric(groupm_df[c], errors="coerce")
        if vals.notna().sum() > 0:
            groupm_df[c] = vals
            numeric_candidates.append(c)
    if numeric_candidates:
        groupm_df["_computed_total"] = groupm_df[numeric_candidates].sum(axis=1, min_count=1)
        groupm_total_col = "_computed_total"

groupm_b = None
groupm_yoy = None
effective_year_groupm = effective_year
if not groupm_df.empty and groupm_year_col and groupm_total_col:
    g_row = _yr(groupm_df, effective_year, groupm_year_col)
    if not g_row.empty:
        effective_year_groupm = int(pd.to_numeric(g_row[groupm_year_col], errors="coerce").iloc[0])
        groupm_b = float(pd.to_numeric(g_row[groupm_total_col], errors="coerce").iloc[0])
    g_prev = _yr(groupm_df, effective_year_groupm - 1, groupm_year_col)
    if not g_prev.empty and groupm_b is not None:
        groupm_prev_b = float(pd.to_numeric(g_prev[groupm_total_col], errors="coerce").iloc[0])
        groupm_yoy = _yoy(groupm_b, groupm_prev_b)

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
    ad_df.columns = [str(c).replace("*", "").strip() for c in ad_df.columns]
    if "Year" in ad_df.columns:
        ad_df["Year"] = pd.to_numeric(ad_df["Year"], errors="coerce").astype("Int64")
ad_lookup = _load_ad_revenue_by_company(excel_path, source_stamp, effective_year) if excel_path else {}
total_tracked_musd = float(sum(float(v.get("ad_revenue_musd", 0.0)) for v in ad_lookup.values()))
total_tracked_b = total_tracked_musd / 1e3 if total_tracked_musd else 0.0
big_tech_names = ["Alphabet", "Meta Platforms", "Amazon", "Apple", "Microsoft"]
big_tech_b = sum(float(ad_lookup.get(c, {}).get("ad_revenue_musd", 0.0)) for c in big_tech_names) / 1e3
other_b = max(total_tracked_b - big_tech_b, 0.0)
global_ad_denom = groupm_b if groupm_b else total_tracked_b
untracked_b = max((global_ad_denom or 0) - total_tracked_b, 0.0)
market_feed_df = _load_market_feed()

# Screen 1 — Hero
st.markdown(
    """
<div style="
  background: linear-gradient(160deg, #0d1117 0%, #0f1f35 60%, #0d1117 100%);
  color: white;
  padding: 100px 48px 80px;
  text-align: center;
  border-radius: 16px;
  margin: -16px -16px 0 -16px;
">
  <div style="color:#ff5b1f;font-size:0.72rem;letter-spacing:0.3em;
              text-transform:uppercase;margin-bottom:16px;">
    The Attention Economy
  </div>
  <div style="font-size:clamp(2rem,5vw,3.8rem);font-weight:900;
              line-height:1.1;margin-bottom:20px;color:white;">
    14 companies.<br>One dashboard.
  </div>
  <div style="color:rgba(255,255,255,0.3);font-size:0.95rem;
              letter-spacing:0.1em;">
    ↓ Scroll to explore
  </div>
</div>
""",
    unsafe_allow_html=True,
)
_beat_divider()

# Screen 2 — KPI strip + comment
_beat_header("The Scale", f"The world's attention, in numbers — {effective_year}")
k1, k2, k3 = st.columns(3)
with k1:
    st.markdown(_kpi_card("Global Ad Spend", f"${groupm_b:.0f}B" if groupm_b else "—", _yoy_html(groupm_yoy), f"{effective_year_groupm} · GroupM"), unsafe_allow_html=True)
with k2:
    rev_display = f"${(rev_b/1e3):.1f}T" if rev_b and rev_b >= 1000 else (f"${rev_b:.0f}B" if rev_b else "—")
    st.markdown(_kpi_card("Tracked Revenue", rev_display, _yoy_html(rev_yoy), f"{effective_year} · 14 companies"), unsafe_allow_html=True)
with k3:
    mcap_display = f"${(mcap_b/1e3):.1f}T" if mcap_b and mcap_b >= 1000 else (f"${mcap_b:.0f}B" if mcap_b else "—")
    st.markdown(_kpi_card("Combined Market Cap", mcap_display, _yoy_html(mcap_yoy), f"{effective_year} · 14 companies"), unsafe_allow_html=True)
parts = []
if groupm_b:
    parts.append(f"In {effective_year_groupm}, the world spent <strong style='color:white;'>${groupm_b:.0f}B</strong> on advertising.")
if rev_yoy is not None:
    parts.append(_comment_growth("Tracked company revenues", rev_yoy))
if mcap_yoy is not None:
    if mcap_yoy >= 15:
        parts.append(f"Markets rewarded them: combined market cap surged <strong style='color:#22c55e;'>+{mcap_yoy:.1f}%</strong>.")
    elif mcap_yoy >= 0:
        parts.append(f"Markets were measured: combined market cap rose <strong style='color:#22c55e;'>+{mcap_yoy:.1f}%</strong>.")
    else:
        parts.append(f"Markets were skeptical: combined market cap fell <strong style='color:#ef4444;'>{mcap_yoy:.1f}%</strong>.")
if parts:
    _beat_body(" ".join(parts))
_beat_divider()

# Screen 3 — Global map
_beat_header("The World", "Every dollar. Every country. One map.")
if groupm_b:
    st.markdown(
        f"""
        <div style="
          background: linear-gradient(90deg,rgba(255,91,31,0.12),transparent);
          border-left: 3px solid #ff5b1f;
          padding: 16px 20px;
          border-radius: 0 8px 8px 0;
          margin-bottom: 20px;
        ">
          <span style="color:white;font-size:1.4rem;font-weight:700;">
            ${groupm_b:.0f}B
          </span>
          <span style="color:rgba(255,255,255,0.5);font-size:0.9rem;margin-left:10px;">
            total global ad spend in {effective_year_groupm} — Source: GroupM
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
try:
    country_df = _read_excel_sheet_cached(excel_path, "Country_Totals_vs_GDP", source_stamp) if excel_path else pd.DataFrame()
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
                map_fig = px.choropleth(
                    scoped_map,
                    locations=country_col,
                    locationmode="country names",
                    color=value_col,
                    color_continuous_scale="Blues",
                )
                map_fig.update_layout(
                    **_chart_layout(
                        470,
                        dict(
                            geo=dict(showframe=False, showcoastlines=False, projection_type="natural earth"),
                            margin=dict(l=0, r=0, t=8, b=0),
                        ),
                    )
                )
                st.plotly_chart(map_fig, use_container_width=True)
except Exception:
    st.info("Global map unavailable.")
st.caption("Map shows advertising spend by country as a % of GDP. Darker = higher ad market intensity.")
_beat_divider()

# Screen 4 — Big Tech vs world
_beat_header("The Concentration", "Most of it went to very few hands.")
if total_tracked_b <= 0 and (groupm_b is None or groupm_b <= 0):
    st.info("Ad revenue data not available.")
else:
    import plotly.graph_objects as go
    denom = global_ad_denom if global_ad_denom else total_tracked_b
    bar_fig = go.Figure()
    for name, val, color in [
        ("Big Tech (Alphabet, Meta, Amazon, Apple, Microsoft)", big_tech_b, "#ff5b1f"),
        ("Other Tracked Companies", other_b, "#3b82f6"),
        ("Rest of World (untracked)", untracked_b, "#1f2937"),
    ]:
        pct = (val / denom * 100) if denom else 0
        bar_fig.add_trace(
            go.Bar(
                x=[val], y=[""], name=name, orientation="h",
                marker=dict(color=color),
                customdata=[[pct]],
                text=f"${val:.0f}B  {pct:.1f}%" if pct > 7 else "",
                textposition="inside",
                hovertemplate=f"{name}: $%{{x:.0f}}B — %{{customdata[0]:.1f}}% of global<extra></extra>",
            )
        )
    bar_fig.update_layout(
        **_chart_layout(
            170,
            dict(
                barmode="stack",
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                showlegend=True,
                legend=dict(orientation="h", yanchor="top", y=-0.32, font=dict(color="white", size=11)),
                margin=dict(l=0, r=0, t=8, b=100),
            ),
        )
    )
    st.plotly_chart(bar_fig, use_container_width=True)
    big_pct = (big_tech_b / denom * 100) if denom else 0
    tracked_pct = (total_tracked_b / denom * 100) if denom else 0
    st.caption(
        f"Of the ${denom:.0f}B spent globally on advertising in {effective_year_groupm}, "
        f"just 5 Big Tech companies captured ${big_tech_b:.0f}B ({big_pct:.1f}%). "
        f"Our full tracked universe held ${total_tracked_b:.0f}B ({tracked_pct:.1f}% of global). "
        f"The remaining ${untracked_b:.0f}B went to thousands of other publishers worldwide."
    )
_beat_divider()

# Screen 5 — Revenue treemap
_beat_header("The Revenue Map", "Not all revenue is equal. See who grew.")
try:
    if metrics.empty or "revenue" not in metrics.columns:
        st.info("Revenue treemap unavailable.")
    else:
        treemap_df = metrics[metrics["year"] == effective_year].copy()
        prev_df = metrics[metrics["year"] == (effective_year - 1)][["company", "revenue"]].rename(columns={"revenue": "prev_rev"})
        treemap_df = treemap_df.merge(prev_df, on="company", how="left")
        treemap_df["revenue_b"] = pd.to_numeric(treemap_df["revenue"], errors="coerce") / 1e3
        treemap_df["rev_yoy"] = _yoy_vec(treemap_df["revenue"], treemap_df["prev_rev"])
        treemap_df = treemap_df.dropna(subset=["company", "revenue_b"])
        if treemap_df.empty:
            st.info("Revenue treemap unavailable.")
        else:
            t_fig = px.treemap(
                treemap_df,
                path=["company"],
                values="revenue_b",
                color="rev_yoy",
                color_continuous_scale=["#ef4444", "#1f2937", "#22c55e"],
                color_continuous_midpoint=0,
                custom_data=["rev_yoy", "revenue_b"],
                title=f"Revenue by Company — {effective_year}",
            )
            t_fig.update_traces(
                hovertemplate="<b>%{label}</b><br>Revenue: $%{customdata[1]:.0f}B<br>YoY: %{customdata[0]:+.1f}%<extra></extra>",
                textfont=dict(color="white"),
            )
            t_fig.update_layout(**_chart_layout(420, dict(margin=dict(l=0, r=0, t=46, b=0))))
            st.plotly_chart(t_fig, use_container_width=True)
            st.caption("Rectangle size = total revenue. Color = YoY growth (green = growth, red = decline). Hover for details.")
except Exception:
    st.info("Revenue treemap unavailable.")
_beat_divider()

# Screen 6 — Ad dependency
_beat_header("The Dependency", "Some live and die by advertising. Others barely care.")
try:
    import plotly.graph_objects as go
    if metrics.empty or "revenue" not in metrics.columns:
        st.info("Ad dependency chart unavailable.")
    else:
        dep_rows = []
        for _, row in metrics[metrics["year"] == effective_year].iterrows():
            company = str(row.get("company", ""))
            total_rev = float(pd.to_numeric(pd.Series([row.get("revenue", np.nan)]), errors="coerce").iloc[0] or 0.0)
            ad_rev = float(ad_lookup.get(company, {}).get("ad_revenue_musd", 0.0))
            ad_pct = min((ad_rev / total_rev * 100) if total_rev > 0 else 0.0, 100.0)
            dep_rows.append(
                {
                    "company": company,
                    "ad_pct": ad_pct,
                    "non_ad_pct": max(100 - ad_pct, 0),
                    "ad_rev_b": ad_rev / 1e3,
                    "total_rev_b": total_rev / 1e3,
                }
            )
        dep_rows = [r for r in dep_rows if r["company"]]
        if not dep_rows:
            st.info("Ad dependency chart unavailable.")
        else:
            dep_rows.sort(key=lambda x: x["ad_pct"], reverse=True)
            dep_fig = go.Figure()
            dep_fig.add_trace(
                go.Bar(
                    y=[r["company"] for r in dep_rows],
                    x=[r["ad_pct"] for r in dep_rows],
                    name="Ad Revenue %",
                    orientation="h",
                    marker=dict(color="#ff5b1f"),
                    customdata=[[r["ad_rev_b"], r["total_rev_b"]] for r in dep_rows],
                    hovertemplate="<b>%{y}</b><br>Ad Revenue: $%{customdata[0]:.1f}B (%{x:.1f}%)<br>Total Revenue: $%{customdata[1]:.1f}B<extra></extra>",
                )
            )
            dep_fig.add_trace(
                go.Bar(
                    y=[r["company"] for r in dep_rows],
                    x=[r["non_ad_pct"] for r in dep_rows],
                    name="Non-Ad Revenue %",
                    orientation="h",
                    marker=dict(color="rgba(255,255,255,0.08)"),
                    hoverinfo="skip",
                )
            )
            dep_fig.update_layout(
                **_chart_layout(
                    430,
                    dict(
                        barmode="stack",
                        xaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="rgba(255,255,255,0.05)", color="rgba(255,255,255,0.4)"),
                        yaxis=dict(color="white"),
                        margin=dict(l=120, r=0, t=8, b=40),
                        legend=dict(font=dict(color="white")),
                    ),
                )
            )
            st.plotly_chart(dep_fig, use_container_width=True)
            most_dep = dep_rows[0]
            least_dep = dep_rows[-1]
            st.caption(
                f"{most_dep['company']} derives {most_dep['ad_pct']:.0f}% of its revenue from advertising — it is, functionally, an advertising company. "
                f"{least_dep['company']} sits at {least_dep['ad_pct']:.1f}% — barely reliant on ads despite its scale."
            )
except Exception:
    st.info("Ad dependency chart unavailable.")
_beat_divider()

# Screen 7 — Duopoly donut
_beat_header("The Duopoly", "Two companies. One grip.")
try:
    import plotly.graph_objects as go
    if total_tracked_b <= 0:
        st.info("Duopoly chart unavailable.")
    else:
        duo_b = (
            float(ad_lookup.get("Alphabet", {}).get("ad_revenue_musd", 0.0))
            + float(ad_lookup.get("Meta Platforms", {}).get("ad_revenue_musd", 0.0))
        ) / 1e3
        rest_b = max(total_tracked_b - duo_b, 0.0)
        duo_pct = duo_b / total_tracked_b * 100 if total_tracked_b else 0.0
        d_fig = go.Figure(
            go.Pie(
                values=[duo_b, rest_b],
                labels=["Alphabet + Meta", "Everyone Else"],
                hole=0.65,
                marker=dict(colors=["#ff5b1f", "rgba(255,255,255,0.08)"]),
                textfont=dict(color="white"),
                hovertemplate="%{label}: $%{value:.0f}B (%{percent})<extra></extra>",
            )
        )
        d_fig.update_layout(
            **_chart_layout(
                350,
                dict(
                    annotations=[dict(text=f"<b>{duo_pct:.1f}%</b><br><span style='font-size:10px'>Duopoly</span>", x=0.5, y=0.5, showarrow=False, font_size=22, font_color="white")],
                    margin=dict(l=0, r=0, t=8, b=0),
                    legend=dict(font=dict(color="white")),
                ),
            )
        )
        st.plotly_chart(d_fig, use_container_width=True)
        st.caption(
            f"Alphabet and Meta together controlled {duo_pct:.1f}% of all tracked digital ad revenue in {effective_year}. "
            f"Combined: ${duo_b:.0f}B. The rest of the tracked universe: ${rest_b:.0f}B."
        )
except Exception:
    st.info("Duopoly chart unavailable.")
_beat_divider()

# Screen 8 — M2 vs Ad spend
_beat_header("The Money Printer", "When central banks print, ad markets follow.")
try:
    import plotly.graph_objects as go
    if m2_yearly_df.empty or groupm_df.empty or not groupm_year_col or not groupm_total_col:
        st.info("M2 vs Ad Spend chart unavailable.")
    else:
        m2_scoped = m2_yearly_df.copy()
        m2_scoped["year"] = pd.to_numeric(m2_scoped["year"], errors="coerce")
        m2_scoped["m2_value"] = pd.to_numeric(m2_scoped["m2_value"], errors="coerce")
        m2_scoped = m2_scoped.dropna(subset=["year", "m2_value"])
        gm = groupm_df[[groupm_year_col, groupm_total_col]].copy()
        gm.columns = ["year", "ad_total"]
        gm["year"] = pd.to_numeric(gm["year"], errors="coerce")
        gm["ad_total"] = pd.to_numeric(gm["ad_total"], errors="coerce")
        gm = gm.dropna(subset=["year", "ad_total"])
        merged = m2_scoped.merge(gm, on="year", how="inner")
        merged = merged[merged["year"] >= 2010].sort_values("year")
        if merged.empty:
            st.info("M2 vs Ad Spend chart unavailable.")
        else:
            base_year = 2010 if (merged["year"] == 2010).any() else int(merged["year"].min())
            base_m2 = float(merged[merged["year"] == base_year]["m2_value"].iloc[0])
            base_ad = float(merged[merged["year"] == base_year]["ad_total"].iloc[0])
            if base_m2 <= 0 or base_ad <= 0:
                st.info("M2 vs Ad Spend chart unavailable.")
            else:
                merged["m2_idx"] = merged["m2_value"] / base_m2 * 100
                merged["ad_idx"] = merged["ad_total"] / base_ad * 100
                m2_fig = go.Figure()
                m2_fig.add_trace(go.Scatter(x=merged["year"], y=merged["m2_idx"], name="M2 Money Supply (indexed)", line=dict(color="#3b82f6", width=2.5)))
                m2_fig.add_trace(go.Scatter(x=merged["year"], y=merged["ad_idx"], name="Global Ad Spend (indexed)", line=dict(color="#ff9900", width=2.5), yaxis="y2"))
                m2_fig.add_vrect(x0=2020, x1=2021, fillcolor="rgba(255,255,255,0.05)", line_width=0, annotation_text="2020 stimulus", annotation_font_color="rgba(255,255,255,0.4)")
                m2_fig.update_layout(
                    **_chart_layout(
                        370,
                        dict(
                            yaxis=dict(title="M2 (indexed, 2010=100)", color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
                            yaxis2=dict(title="Ad Spend (indexed)", overlaying="y", side="right", color="rgba(255,255,255,0.4)"),
                            xaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
                            margin=dict(l=0, r=60, t=8, b=40),
                            legend=dict(font=dict(color="white")),
                        ),
                    )
                )
                st.plotly_chart(m2_fig, use_container_width=True)
                st.caption("Both M2 money supply and global ad spend indexed to 2010 = 100. The near-perfect correlation shows macro liquidity as a leading indicator for ad market growth.")
except Exception:
    st.info("M2 vs Ad Spend chart unavailable.")
_beat_divider()

# Screen 9 — Structural shift
_beat_header("The Structural Shift", "The ad market didn't just grow. It transformed.")
try:
    import plotly.graph_objects as go
    if groupm_df.empty or not groupm_year_col:
        st.info("Structural shift chart unavailable.")
    else:
        gdf = groupm_df.copy()
        gdf[groupm_year_col] = pd.to_numeric(gdf[groupm_year_col], errors="coerce")
        gdf = gdf.dropna(subset=[groupm_year_col])
        gdf[groupm_year_col] = gdf[groupm_year_col].astype(int)
        gdf = gdf[gdf[groupm_year_col] >= 2010].sort_values(groupm_year_col)
        if gdf.empty:
            st.info("Structural shift chart unavailable.")
        else:
            channels = {
                "Traditional TV": ("#4472c4", _find_col(gdf, ["traditional", "tv"])),
                "Connected TV": ("#00bcd4", _find_col(gdf, ["connected", "tv"])),
                "Search": ("#ff9900", _find_col(gdf, ["search"], ["non"])),
                "Non-Search": ("#ffd600", _find_col(gdf, ["non", "search"])),
                "Retail Media": ("#22c55e", _find_col(gdf, ["retail"])),
                "Traditional OOH": ("#888888", _find_col(gdf, ["traditional", "ooh"])),
                "Digital OOH": ("#26a69a", _find_col(gdf, ["digital", "ooh"])),
            }
            s_fig = go.Figure()
            for channel, (color, col) in channels.items():
                if not col:
                    continue
                vals = pd.to_numeric(gdf[col], errors="coerce")
                if vals.notna().sum() == 0:
                    continue
                s_fig.add_trace(go.Scatter(x=gdf[groupm_year_col], y=vals, name=channel, stackgroup="one", line=dict(width=0), fillcolor=color, hovertemplate=f"{channel}: $%{{y:.0f}}B<extra></extra>"))
            if not s_fig.data:
                st.info("Structural shift chart unavailable.")
            else:
                retail_col = channels.get("Retail Media", ("", ""))[1]
                if retail_col:
                    r_2022 = gdf[gdf[groupm_year_col] == 2022][retail_col]
                    if not r_2022.empty and pd.notna(r_2022.iloc[0]):
                        s_fig.add_annotation(x=2022, y=float(r_2022.iloc[0]), text="Retail Media emerges", showarrow=True, arrowcolor="white", font=dict(color="white", size=11), arrowhead=2)
                s_fig.update_layout(
                    **_chart_layout(
                        390,
                        dict(
                            xaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
                            yaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)", ticksuffix="B"),
                            margin=dict(l=0, r=0, t=8, b=40),
                            legend=dict(font=dict(color="white")),
                        ),
                    )
                )
                st.plotly_chart(s_fig, use_container_width=True)
                st.caption("Linear TV declining while Search and Retail Media accelerate. CTV growing but from a small base. Retail Media as a category barely existed before 2018.")
except Exception:
    st.info("Structural shift chart unavailable.")
_beat_divider()

# Screen 10 — Search vs traditional
_beat_header("Search Dominance", "Search alone beats all traditional media combined.")
try:
    import plotly.graph_objects as go
    if groupm_df.empty or not groupm_year_col:
        st.info("Search vs Traditional chart unavailable.")
    else:
        g_row = _yr(groupm_df, effective_year, groupm_year_col)
        search_col = _find_col(groupm_df, ["search"], ["non"])
        trad_cols = []
        for c in groupm_df.columns:
            norm = re.sub(r"[^a-z0-9]+", "", c.lower())
            if c in {groupm_year_col, search_col}:
                continue
            if any(x in norm for x in ["traditionaltv", "radio", "print", "newspaper"]):
                trad_cols.append(c)
        if g_row.empty or not search_col or not trad_cols:
            st.info("Search vs Traditional chart unavailable.")
        else:
            search_b = float(pd.to_numeric(g_row[search_col], errors="coerce").iloc[0] or 0.0)
            trad_b = float(sum(float(pd.to_numeric(g_row[c], errors="coerce").iloc[0] or 0.0) for c in trad_cols))
            if search_b <= 0 and trad_b <= 0:
                st.info("Search vs Traditional chart unavailable.")
            else:
                ratio = search_b / trad_b if trad_b > 0 else None
                st_fig = go.Figure(go.Bar(x=[search_b, trad_b], y=["Search", "Traditional (TV+Radio+Print)"], orientation="h", marker=dict(color=["#ff9900", "#4472c4"]), text=[f"${search_b:.0f}B", f"${trad_b:.0f}B"], textposition="outside", textfont=dict(color="white"), hovertemplate="%{y}: $%{x:.0f}B<extra></extra>"))
                st_fig.update_layout(**_chart_layout(210, dict(xaxis=dict(visible=False), yaxis=dict(color="white"), margin=dict(l=0, r=60, t=8, b=8), showlegend=False)))
                st.plotly_chart(st_fig, use_container_width=True)
                caption = f"Search advertising alone accounts for ${search_b:.0f}B in {effective_year}."
                if ratio:
                    caption += f" That is {ratio:.1f}× larger than all traditional TV, radio, and print combined."
                st.caption(caption)
except Exception:
    st.info("Search vs Traditional chart unavailable.")
_beat_divider()

# Screen 11 — Gapminder bubble
_beat_header("The Landscape", "Not all Big Tech is equal. Who won?")
try:
    if metrics.empty or "revenue" not in metrics.columns or mcap_col not in metrics.columns:
        st.info("Bubble chart unavailable.")
    else:
        all_rows = []
        for yr_val in sorted(metrics["year"].dropna().astype(int).unique().tolist()):
            m = metrics[metrics["year"] == yr_val]
            p = metrics[metrics["year"] == (yr_val - 1)]
            ad_lookup_year = _load_ad_revenue_by_company(excel_path, source_stamp, yr_val) if excel_path else {}
            for _, row in m.iterrows():
                company = str(row.get("company", ""))
                rev = float(pd.to_numeric(pd.Series([row.get("revenue", np.nan)]), errors="coerce").iloc[0] or 0.0)
                prev_rows = p[p["company"] == company]
                prev_rev = None
                if not prev_rows.empty:
                    prev_rev = float(pd.to_numeric(pd.Series([prev_rows.iloc[0].get("revenue", np.nan)]), errors="coerce").iloc[0] or 0.0)
                rev_yoy = _yoy(rev, prev_rev) or 0.0
                if rev_yoy is not None and abs(rev_yoy) < 5:
                    rev_yoy = rev_yoy * 100
                mcap = float(pd.to_numeric(pd.Series([row.get(mcap_col, np.nan)]), errors="coerce").iloc[0] or 0.0)
                ad_rev = float(ad_lookup_year.get(company, {}).get("ad_revenue_musd", 0.0))
                ad_pct = min((ad_rev / rev * 100) if rev > 0 else 0.0, 100.0)
                all_rows.append(
                    {
                        "year": str(yr_val),
                        "company": company,
                        "rev_yoy": rev_yoy,
                        "market_cap_b": mcap / 1e3,
                        "ad_pct": max(ad_pct, 1.0),
                        "revenue_b": rev / 1e3,
                        "ad_rev_b": ad_rev / 1e3,
                    }
                )
        bubble_df = pd.DataFrame(all_rows).dropna(subset=["company", "year", "rev_yoy", "market_cap_b"])
        if bubble_df.empty:
            st.info("Bubble chart unavailable.")
        else:
            company_colors = {c: _company_color(c) for c in bubble_df["company"].unique()}
            b_fig = px.scatter(
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
            b_fig.update_traces(
                hovertemplate="<b>%{hovertext}</b><br>Market Cap: $%{y:.0f}B<br>Rev YoY: %{x:+.1f}%<br>Ad Dependency: %{customdata[1]:.1f}%<br>Ad Revenue: $%{customdata[2]:.1f}B<extra></extra>"
            )
            b_fig.update_layout(
                **_chart_layout(
                    590,
                    dict(
                        margin=dict(l=0, r=0, t=8, b=40),
                        legend=dict(font=dict(color="white")),
                        xaxis=dict(ticksuffix="%", color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)", zeroline=True, zerolinecolor="rgba(255,255,255,0.15)"),
                        yaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
                    ),
                )
            )
            st.plotly_chart(b_fig, use_container_width=True)
            latest = bubble_df[bubble_df["year"] == str(effective_year)]
            if not latest.empty:
                top_mcap = latest.nlargest(1, "market_cap_b").iloc[0]
                most_ad = latest.nlargest(1, "ad_pct").iloc[0]
                st.caption(
                    f"Bubble size = ad revenue dependency. {top_mcap['company']} leads on market cap at ${top_mcap['market_cap_b']:.0f}B. "
                    f"{most_ad['company']} is most ad-dependent at {most_ad['ad_pct']:.1f}% of total revenue."
                )
except Exception:
    st.info("Bubble chart unavailable.")
_beat_divider()

# Screen 12 — Index beaters
_beat_header("The Market Bet", "The ad-driven giants didn't just grow. They beat the market.")
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
        start_df = metrics[metrics["year"] == y_start][["company", mcap_col]].rename(columns={mcap_col: "mcap_start"})
        end_df = metrics[metrics["year"] == effective_year][["company", mcap_col]].rename(columns={mcap_col: "mcap_end"})
        perf = start_df.merge(end_df, on="company", how="inner")
        perf["tsr"] = _yoy_vec(perf["mcap_end"], perf["mcap_start"])
        perf = perf.dropna(subset=["tsr"])
        if perf.empty:
            st.info("Performance chart unavailable.")
        else:
            top3 = perf.nlargest(3, "tsr")["company"].tolist()
            if market_feed_df.empty:
                st.info("Performance chart unavailable.")
            else:
                p_fig = go.Figure()
                for idx_tag, idx_label, color, dash in [("^GSPC", "S&P 500", "white", "dash"), ("^IXIC", "Nasdaq", "#ff9900", "dot")]:
                    idx_feed = market_feed_df[market_feed_df["tag"].astype(str).str.upper() == idx_tag]
                    if idx_feed.empty:
                        idx_feed = market_feed_df[market_feed_df["asset"].astype(str).str.lower().str.contains(idx_label.lower(), na=False)]
                    if idx_feed.empty:
                        continue
                    idx_feed = idx_feed.sort_values("date")
                    base = float(idx_feed.iloc[0]["price"])
                    if base <= 0:
                        continue
                    norm = idx_feed["price"] / base * 100
                    p_fig.add_trace(go.Scatter(x=idx_feed["date"], y=norm, name=idx_label, line=dict(color=color, dash=dash, width=1.5), hovertemplate=f"{idx_label}: %{{y:.0f}}<extra></extra>"))
                for company in top3:
                    ticker = company_ticker_fallback.get(company)
                    if not ticker:
                        continue
                    co_feed = market_feed_df[market_feed_df["tag"].astype(str).str.upper() == ticker]
                    if co_feed.empty:
                        co_feed = market_feed_df[market_feed_df["asset"].astype(str).str.lower().str.contains(company.lower(), na=False)]
                    if co_feed.empty:
                        continue
                    co_feed = co_feed.sort_values("date")
                    base = float(co_feed.iloc[0]["price"])
                    if base <= 0:
                        continue
                    norm = co_feed["price"] / base * 100
                    p_fig.add_trace(go.Scatter(x=co_feed["date"], y=norm, name=company, line=dict(color=_company_color(company), width=2.5), hovertemplate=f"{company}: %{{y:.0f}}<extra></extra>"))
                if not p_fig.data:
                    st.info("Performance chart unavailable.")
                else:
                    p_fig.update_layout(
                        **_chart_layout(
                            370,
                            dict(
                                margin=dict(l=0, r=0, t=8, b=40),
                                legend=dict(font=dict(color="white")),
                                yaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
                                xaxis=dict(color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
                            ),
                        )
                    )
                    st.plotly_chart(p_fig, use_container_width=True)
                    best = perf.nlargest(1, "tsr").iloc[0]
                    st.caption(
                        f"Normalized to 100 at start. Top 3 market cap growers vs S&P500 and Nasdaq. "
                        f"{best['company']} led with +{best['tsr']:.0f}% market cap growth over {y_start}→{effective_year}."
                    )
except Exception:
    st.info("Performance chart unavailable.")
_beat_divider()

# Screen 13 — Market cap then vs now
_beat_header("The Wealth Machine", "The market cap story, then vs now.")
try:
    import plotly.graph_objects as go
    if metrics.empty or mcap_col not in metrics.columns:
        st.info("Market cap history unavailable.")
    else:
        year_pool = sorted(metrics["year"].dropna().astype(int).unique().tolist())
        earlier = [y for y in year_pool if y < effective_year]
        y_then = year_pool[0] if year_pool and year_pool[0] < effective_year else (earlier[-1] if earlier else effective_year - 1)
        y_now = effective_year
        then_df = metrics[metrics["year"] == y_then][["company", mcap_col]].copy().rename(columns={mcap_col: "mcap_then"})
        now_df = metrics[metrics["year"] == y_now][["company", mcap_col]].copy().rename(columns={mcap_col: "mcap_now"})
        if then_df.empty or now_df.empty:
            st.info("Market cap history unavailable.")
        else:
            comp = then_df.merge(now_df, on="company", how="inner")
            if comp.empty:
                st.info("Market cap history unavailable.")
            else:
                comp = comp.sort_values("mcap_now", ascending=True)
                mc_fig = go.Figure()
                mc_fig.add_trace(go.Bar(y=comp["company"], x=comp["mcap_then"] / 1e3, name=str(y_then), orientation="h", marker=dict(color="rgba(255,255,255,0.24)"), hovertemplate=f"%{{y}} {y_then}: $%{{x:.0f}}B<extra></extra>"))
                mc_fig.add_trace(go.Bar(y=comp["company"], x=comp["mcap_now"] / 1e3, name=str(y_now), orientation="h", marker=dict(color="#ff5b1f"), hovertemplate=f"%{{y}} {y_now}: $%{{x:.0f}}B<extra></extra>"))
                mc_fig.update_layout(
                    **_chart_layout(
                        410,
                        dict(
                            barmode="group",
                            xaxis=dict(tickprefix="$", ticksuffix="B", color="rgba(255,255,255,0.4)", gridcolor="rgba(255,255,255,0.05)"),
                            yaxis=dict(color="white"),
                            margin=dict(l=120, r=0, t=8, b=40),
                            legend=dict(font=dict(color="white")),
                        ),
                    )
                )
                st.plotly_chart(mc_fig, use_container_width=True)
                total_then = comp["mcap_then"].sum() / 1e6
                total_now = comp["mcap_now"].sum() / 1e6
                growth = _yoy(total_now, total_then)
                cap = f"Combined market cap grew from ${total_then:.1f}T to ${total_now:.1f}T between {y_then} and {y_now}."
                if growth is not None:
                    cap += f" That's a +{growth:.0f}% increase over the period."
                st.caption(cap)
except Exception:
    st.info("Market cap history unavailable.")
_beat_divider()

# Screen 14 — Subscribers pictogram
_beat_header("The Human Side", "Behind every dollar: a human being.")
try:
    sub_df = _read_excel_sheet_cached(excel_path, "Company_subscribers_values", source_stamp) if excel_path else pd.DataFrame()
    if sub_df.empty:
        st.info("Subscriber data unavailable.")
    else:
        sub_df.columns = [str(c).strip() for c in sub_df.columns]
        year_col = _find_col(sub_df, ["year"])
        scope = _yr(sub_df, effective_year, year_col) if year_col else sub_df.copy()
        if scope.empty:
            scope = sub_df.copy()
        streaming = ["Netflix", "Spotify", "Disney", "Paramount"]
        rows_html = []
        total_subs = 0.0
        company_col = _find_col(scope, ["company"]) or _find_col(scope, ["service"]) or _find_col(scope, ["platform"])
        subs_col = _find_col(scope, ["subscriber"])
        if company_col and subs_col:
            scope[subs_col] = pd.to_numeric(scope[subs_col], errors="coerce")
            scope = scope.dropna(subset=[company_col, subs_col])
            for company in streaming:
                rows = scope[scope[company_col].astype(str).str.lower().str.contains(company.lower(), na=False)]
                if rows.empty:
                    continue
                subs_raw = float(rows[subs_col].sum())
                subs_m = subs_raw / 1000 if subs_raw > 10000 else subs_raw
                total_subs += subs_m
                icons = "●" * min(int(subs_m / 10), 30)
                rows_html.append(
                    f"<div class='sub-row'>"
                    f"<span style='color:#ffffff;font-weight:600;display:inline-block;width:120px;'>{escape(company)}</span>"
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
                subs_raw = pd.to_numeric(pd.Series([row[matches[0]]]), errors="coerce").iloc[0]
                if pd.isna(subs_raw):
                    continue
                subs_raw = float(subs_raw)
                subs_m = subs_raw / 1000 if subs_raw > 10000 else subs_raw
                total_subs += subs_m
                icons = "●" * min(int(subs_m / 10), 30)
                rows_html.append(
                    f"<div class='sub-row'>"
                    f"<span style='color:#ffffff;font-weight:600;display:inline-block;width:120px;'>{escape(company)}</span>"
                    f"<span style='color:#ff5b1f;letter-spacing:2px;'>{icons}</span>"
                    f"<span style='color:rgba(255,255,255,0.5);font-size:0.85rem;margin-left:8px;'>{subs_m:.0f}M</span>"
                    f"</div>"
                )
        if not rows_html:
            st.info("Subscriber data unavailable.")
        else:
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
                f"{'more than' if total_subs > china_pop else 'approaching'} "
                f"the population of China ({china_pop}M)."
            )
except Exception:
    st.info("Subscriber data unavailable.")
_beat_divider()

# Screen 15 — Live revenue ticker (self-contained component)
_beat_header("The Clock", "Every second you've been reading this...")
try:
    min_df = _read_excel_sheet_cached(excel_path, "Company_minute&dollar_earned", source_stamp) if excel_path else pd.DataFrame()
    if min_df.empty:
        st.info("Revenue ticker unavailable.")
    else:
        min_df.columns = [str(c).strip() for c in min_df.columns]
        yr_col_m = _find_col(min_df, ["year"])
        min_row = _yr(min_df, effective_year, yr_col_m) if yr_col_m else min_df.copy()
        if min_row.empty:
            min_row = min_df.copy()
        ticker_companies = ["Alphabet", "Meta", "Amazon", "Apple", "Microsoft"]
        ticker_data = []
        total_rps = 0.0
        platform_col = _find_col(min_row, ["platform"]) or _find_col(min_row, ["company"])
        revenue_col = _find_col(min_row, ["revenue"])
        if platform_col and revenue_col:
            min_row[revenue_col] = pd.to_numeric(min_row[revenue_col], errors="coerce")
            for company in ticker_companies:
                rows = min_row[min_row[platform_col].astype(str).str.lower().str.contains(company.lower(), na=False)]
                if rows.empty:
                    continue
                rev_b = float(rows[revenue_col].iloc[0] or 0.0)
                if rev_b <= 0:
                    continue
                rps = (rev_b * 1e9) / (365 * 24 * 3600)
                total_rps += rps
                ticker_data.append((company, rps))
        else:
            row = min_row.iloc[-1]
            for company in ticker_companies:
                matches = [c for c in min_row.columns if company.lower() in c.lower() and c != yr_col_m]
                if not matches:
                    continue
                rpm = pd.to_numeric(pd.Series([row[matches[0]]]), errors="coerce").iloc[0]
                if pd.isna(rpm):
                    continue
                rps = float(rpm) / 60.0
                total_rps += rps
                ticker_data.append((company, rps))
        if not ticker_data:
            st.info("Revenue ticker unavailable.")
        else:
            rows_html = ""
            for company, rps in ticker_data:
                rows_html += f"""
                <div style="display:flex;justify-content:space-between;
                            align-items:center;padding:14px 0;
                            border-bottom:1px solid rgba(255,255,255,0.07);">
                  <span style="color:white;font-weight:600;font-size:1rem;">{escape(company)}</span>
                  <span id="tick_{escape(company).replace(' ','_')}"
                        data-rps="{rps:.6f}"
                        style="color:#ff5b1f;font-family:monospace;
                               font-size:1.5rem;font-weight:800;">$0</span>
                </div>
                """
            rows_html += f"""
            <div style="display:flex;justify-content:space-between;
                        align-items:center;padding:16px 0 0;">
              <span style="color:rgba(255,255,255,0.4);font-size:0.9rem;">
                Combined
              </span>
              <span id="tick_combined"
                    data-rps="{total_rps:.6f}"
                    style="color:white;font-family:monospace;
                           font-size:1.5rem;font-weight:800;">$0</span>
            </div>
            """
            st.components.v1.html(
                f"""
                <div style="background:#0d1117;padding:24px 20px;border-radius:12px;font-family:sans-serif;">
                  {rows_html}
                  <div style="color:rgba(255,255,255,0.3);font-size:0.72rem;margin-top:16px;">
                    Based on {effective_year} annual revenue ÷ seconds per year.
                    Updates every 120ms since you opened this page.
                  </div>
                </div>
                <script>
                  (function() {{
                    var t0 = Date.now();
                    var els = document.querySelectorAll('[data-rps]');
                    setInterval(function() {{
                      var elapsed = (Date.now() - t0) / 1000;
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
                height=340,
            )
except Exception as exc:
    st.info(f"Revenue ticker unavailable: {exc}")
_beat_divider()

# Screen 16 — Transcript pulse + market tape
_beat_header("The Human Voice", "Here's what the people running these companies actually said.")
_render_transcript_pulse_strip(effective_year, selected_quarter)
st.markdown(
    "<div style='color:#ff5b1f;font-size:0.68rem;letter-spacing:0.22em;text-transform:uppercase;margin:16px 0 8px;'>"
    "Market Tape"
    "</div>",
    unsafe_allow_html=True,
)
_render_stock_price_strip(market_feed_df)
_beat_divider()

# Screen 17 — Gateway
st.markdown(
    """
<div style="text-align:center;padding:48px 0 24px;">
  <div style="color:#ff5b1f;font-size:0.72rem;letter-spacing:0.28em;
              text-transform:uppercase;margin-bottom:12px;">Your Turn</div>
  <div style="color:white;font-size:2.2rem;font-weight:800;
              margin-bottom:8px;">Go deeper.</div>
  <div style="color:rgba(255,255,255,0.4);font-size:1rem;
              margin-bottom:32px;">Pick your path.</div>
</div>
""",
    unsafe_allow_html=True,
)
g1, g2, g3 = st.columns(3)
with g1:
    if st.button("Overview — Macro and Market", use_container_width=True, key="home_gateway_overview"):
        st.switch_page("pages/00_Overview.py")
with g2:
    if st.button("Earnings — Company Deep Dives", use_container_width=True, key="home_gateway_earnings"):
        st.switch_page("pages/01_Earnings.py")
with g3:
    if st.button("Genie — Ask the Data", use_container_width=True, key="home_gateway_genie"):
        st.switch_page("pages/04_Genie.py")

source_label = str(workbook_path) if workbook_path else "not found"
st.markdown(
    f"<div class='wm-foot' style='color:rgba(255,255,255,0.45);'>Source: {escape(source_label)} • Period baseline: {effective_year} {selected_quarter}</div>",
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)
