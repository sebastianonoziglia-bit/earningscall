import os
import base64
import logging
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
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

    def _run_script(script: str) -> None:
        try:
            result = subprocess.run(
                [sys.executable, script],
                cwd=str(root_dir),
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
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

    _run_script("scripts/generate_insights.py")

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

    if len(cards) > 5:
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
    candidates = []
    if data_path:
        candidates.append(Path(data_path))
    candidates.extend(
        [
            APP_DIR / "attached_assets" / "Earnings + stocks  copy.xlsx",
            ROOT_DIR / "attached_assets" / "Earnings + stocks  copy.xlsx",
            ROOT_DIR / "Earnings + stocks  copy.xlsx",
        ]
    )
    for path in candidates:
        if path and path.exists():
            return path
    return None


def _load_auto_insights(workbook_path: Optional[Path], selected_year: int) -> pd.DataFrame:
    if workbook_path is None:
        return pd.DataFrame()
    try:
        insights_df = pd.read_excel(workbook_path, sheet_name="Overview_Auto_Insights")
    except Exception:
        return pd.DataFrame()

    if insights_df.empty:
        return pd.DataFrame()

    insights_df.columns = [str(col).strip().lower() for col in insights_df.columns]
    if "is_active" in insights_df.columns:
        insights_df["is_active"] = pd.to_numeric(insights_df["is_active"], errors="coerce").fillna(0).astype(int)
        insights_df = insights_df[insights_df["is_active"] == 1]

    if "year" in insights_df.columns:
        insights_df["year"] = pd.to_numeric(insights_df["year"], errors="coerce")
        scoped = insights_df[insights_df["year"].isna() | (insights_df["year"] == int(selected_year))].copy()
        if not scoped.empty:
            insights_df = scoped

    if "sort_order" in insights_df.columns:
        insights_df["sort_order"] = pd.to_numeric(insights_df["sort_order"], errors="coerce")
        insights_df = insights_df.sort_values(["sort_order", "title"], na_position="last")

    return insights_df.head(6).copy()


@st.cache_data(ttl=3600)
def _load_homepage_yearly_comments(excel_path: str, source_stamp: int, selected_year: int) -> dict:
    if not excel_path:
        return {}
    try:
        comments_df = pd.read_excel(excel_path, sheet_name="Homepage_Yearly_Comments")
    except Exception:
        return {}
    if comments_df.empty:
        return {}

    comments_df.columns = [str(c).strip().lower() for c in comments_df.columns]
    if "is_active" in comments_df.columns:
        comments_df["is_active"] = pd.to_numeric(comments_df["is_active"], errors="coerce").fillna(1).astype(int)
        comments_df = comments_df[comments_df["is_active"] == 1]
    if "year" in comments_df.columns:
        comments_df["year"] = pd.to_numeric(comments_df["year"], errors="coerce")
        comments_df = comments_df[comments_df["year"] == int(selected_year)]

    result = {}
    for _, row in comments_df.iterrows():
        slot = str(row.get("slot", "")).strip().lower()
        text = str(row.get("text", "")).strip()
        if slot and text and text.lower() not in {"nan", "none", ""}:
            result[slot] = text
    return result


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
metrics_df = page_data.get("metrics_df", pd.DataFrame())
companies = page_data.get("companies", [])
source_stamp = int(page_data.get("source_stamp", 0) or 0)
data_path = str(page_data.get("data_path", "") or "")

if page_data.get("error"):
    st.warning(f"Data initialization warning: {page_data['error']}")

workbook_path = _resolve_workbook_path(data_path)

if not metrics_df.empty:
    metrics_df.columns = [str(col).strip().lower() for col in metrics_df.columns]

required_columns = ["company", "year", "revenue", "net_income", "operating_income", "market_cap", "rd"]
for column in required_columns:
    if column not in metrics_df.columns:
        metrics_df[column] = pd.NA

if "company" in metrics_df.columns:
    metrics_df["company"] = metrics_df["company"].astype(str).str.strip()
metrics_df["year"] = _to_numeric(metrics_df["year"])
for column in ["revenue", "net_income", "operating_income", "market_cap", "rd"]:
    metrics_df[column] = _to_numeric(metrics_df[column])

metrics_df = metrics_df.dropna(subset=["company", "year"]).copy()
if not metrics_df.empty:
    metrics_df["year"] = metrics_df["year"].astype(int)

available_years = sorted(metrics_df["year"].dropna().unique().tolist()) if not metrics_df.empty else []
latest_year = int(max(available_years)) if available_years else 2024
prev_year = int(max([y for y in available_years if y < latest_year])) if any(y < latest_year for y in available_years) else None

df_latest = metrics_df[metrics_df["year"] == latest_year].copy() if not metrics_df.empty else pd.DataFrame()
df_prev = metrics_df[metrics_df["year"] == prev_year].copy() if prev_year is not None else pd.DataFrame()

total_revenue_latest = float(df_latest["revenue"].sum()) if "revenue" in df_latest.columns else 0.0
total_market_cap_latest = float(df_latest["market_cap"].sum()) if "market_cap" in df_latest.columns else 0.0
total_net_income_latest = float(df_latest["net_income"].sum()) if "net_income" in df_latest.columns else 0.0
total_rd_latest = float(df_latest["rd"].sum()) if "rd" in df_latest.columns else 0.0

total_revenue_prev = float(df_prev["revenue"].sum()) if not df_prev.empty and "revenue" in df_prev.columns else None

revenue_growth_pct = _safe_pct(total_revenue_latest - total_revenue_prev, total_revenue_prev) if total_revenue_prev else None
profit_margin_pct = _safe_pct(total_net_income_latest, total_revenue_latest)
rd_intensity_pct = _safe_pct(total_rd_latest, total_revenue_latest)
margin_pct = profit_margin_pct

total_market_cap_prev = float(df_prev["market_cap"].sum()) if not df_prev.empty and "market_cap" in df_prev.columns else None
market_cap_growth_pct = (
    _safe_pct(total_market_cap_latest - total_market_cap_prev, total_market_cap_prev)
    if total_market_cap_prev not in (None, 0)
    else None
)

total_net_income_prev = float(df_prev["net_income"].sum()) if not df_prev.empty and "net_income" in df_prev.columns else None
margin_prev = (
    (total_net_income_prev / total_revenue_prev * 100)
    if (total_net_income_prev is not None and total_revenue_prev not in (None, 0))
    else None
)
margin_delta_bps = round((margin_pct - margin_prev) * 100) if (margin_pct is not None and margin_prev is not None) else None

total_rd_prev = float(df_prev["rd"].sum()) if not df_prev.empty and "rd" in df_prev.columns else None
rd_growth_pct = _safe_pct(total_rd_latest - total_rd_prev, total_rd_prev) if total_rd_prev not in (None, 0) else None

# Build company KPI leaderboard payloads (horizontal scroll, all companies visible via strip).
leaderboard_sections = []


def _rank_cards_from_block(block: pd.DataFrame, value_col: str, formatter, prev_block: Optional[pd.DataFrame] = None) -> list:
    if block.empty or value_col not in block.columns:
        return []
    scoped = block[["company", value_col]].dropna(subset=[value_col]).copy()
    if scoped.empty:
        return []
    scoped = scoped.sort_values(value_col, ascending=False)
    prev_lookup = {}
    if prev_block is not None and not prev_block.empty and value_col in prev_block.columns:
        prev_scoped = prev_block[["company", value_col]].dropna(subset=[value_col]).copy()
        if not prev_scoped.empty:
            prev_lookup = {str(r["company"]): float(r[value_col]) for _, r in prev_scoped.iterrows()}
    cards = []
    for rank, (_, row) in enumerate(scoped.iterrows(), start=1):
        company_name = str(row["company"])
        curr_val = float(row[value_col])
        yoy_pct = None
        prev_val = prev_lookup.get(company_name)
        if prev_val is not None and prev_val != 0:
            yoy_pct = ((curr_val - prev_val) / abs(prev_val)) * 100.0
        cards.append(
            {
                "rank": rank,
                "company": company_name,
                "value": formatter(curr_val),
                "color": _company_color(company_name),
                "logo": _resolve_logo(company_name, logos),
                "raw": curr_val,
                "yoy_pct": yoy_pct,
            }
        )
    return cards


revenue_cards = _rank_cards_from_block(df_latest, "revenue", lambda v: _format_money_musd(v, 1), prev_block=df_prev)
market_cap_cards = _rank_cards_from_block(df_latest, "market_cap", lambda v: _format_money_musd(v, 1), prev_block=df_prev)
rd_cards = _rank_cards_from_block(df_latest, "rd", lambda v: _format_money_musd(v, 1), prev_block=df_prev)

ad_revenue_cards = []
ad_growth_cards = []
ad_intensity_cards = []

# Advertising revenue, growth, and intensity leaderboard sections.
if workbook_path and workbook_path.exists():
    try:
        ad_df = pd.read_excel(workbook_path, sheet_name="Company_advertising_revenue")
        ad_df.columns = [str(c).strip() for c in ad_df.columns]
        if "Year" in ad_df.columns:
            ad_df["Year"] = pd.to_numeric(ad_df["Year"], errors="coerce")
            latest_rows = ad_df[ad_df["Year"] == int(latest_year)].copy()
            prev_rows = ad_df[ad_df["Year"] == int(prev_year)].copy() if prev_year is not None else pd.DataFrame()
            if not latest_rows.empty:
                ad_row = latest_rows.iloc[0]
                prev_row = prev_rows.iloc[0] if not prev_rows.empty else None
                ad_map = {
                    "Google_Ads": "Alphabet",
                    "Meta_Ads": "Meta Platforms",
                    "Amazon_Ads": "Amazon",
                    "Spotify_Ads": "Spotify",
                    "*WBD_Ads": "Warner Bros. Discovery",
                    "*Microsoft_Ads": "Microsoft",
                    "Paramount": "Paramount Global",
                    "*Apple": "Apple",
                    "*Disney": "Disney",
                    "Comcast": "Comcast",
                    "Netflix": "Netflix",
                    "Twitter/X": "Twitter/X",
                    "TikTok": "TikTok",
                    "Snapchat": "Snapchat",
                }
                revenue_lookup = {}
                prev_revenue_lookup = {}
                if not df_latest.empty and "revenue" in df_latest.columns:
                    for _, r in df_latest[["company", "revenue"]].dropna(subset=["revenue"]).iterrows():
                        revenue_lookup[str(r["company"])] = float(r["revenue"])
                if not df_prev.empty and "revenue" in df_prev.columns:
                    for _, r in df_prev[["company", "revenue"]].dropna(subset=["revenue"]).iterrows():
                        prev_revenue_lookup[str(r["company"])] = float(r["revenue"])

                ad_rows = []
                for col, company_name in ad_map.items():
                    if col not in ad_df.columns:
                        continue
                    value = pd.to_numeric(ad_row.get(col), errors="coerce")
                    if pd.isna(value):
                        continue
                    ad_musd = float(value) * 1000.0
                    prev_val = pd.to_numeric(prev_row.get(col), errors="coerce") if prev_row is not None else np.nan
                    prev_musd = float(prev_val) * 1000.0 if not pd.isna(prev_val) else np.nan
                    growth_pct = _safe_pct(ad_musd - prev_musd, prev_musd) if not pd.isna(prev_musd) else None
                    company_revenue = revenue_lookup.get(company_name)
                    intensity_pct = _safe_pct(ad_musd, company_revenue) if company_revenue else None
                    prev_company_revenue = prev_revenue_lookup.get(company_name)
                    intensity_prev = _safe_pct(prev_musd, prev_company_revenue) if prev_company_revenue and not pd.isna(prev_musd) else None
                    intensity_yoy_pct = (
                        ((float(intensity_pct) - float(intensity_prev)) / abs(float(intensity_prev)) * 100.0)
                        if intensity_pct is not None and intensity_prev not in (None, 0)
                        else None
                    )
                    ad_rows.append(
                        {
                            "company": company_name,
                            "ad_musd": ad_musd,
                            "ad_growth_pct": growth_pct,
                            "ad_intensity_pct": intensity_pct,
                            "ad_intensity_yoy_pct": intensity_yoy_pct,
                        }
                    )

                if ad_rows:
                    ad_ranked = sorted(ad_rows, key=lambda x: x["ad_musd"], reverse=True)
                    for idx, row in enumerate(ad_ranked, start=1):
                        ad_revenue_cards.append(
                            {
                                "rank": idx,
                                "company": row["company"],
                                "value": _format_money_musd(row["ad_musd"], 1),
                                "color": _company_color(row["company"]),
                                "logo": _resolve_logo(row["company"], logos),
                                "raw": row["ad_musd"],
                                "yoy_pct": row["ad_growth_pct"],
                            }
                        )

                    growth_ranked = [r for r in ad_rows if r["ad_growth_pct"] is not None]
                    growth_ranked = sorted(growth_ranked, key=lambda x: x["ad_growth_pct"], reverse=True)
                    for idx, row in enumerate(growth_ranked, start=1):
                        ad_growth_cards.append(
                            {
                                "rank": idx,
                                "company": row["company"],
                                "value": f"{float(row['ad_growth_pct']):+.1f}%",
                                "color": _company_color(row["company"]),
                                "logo": _resolve_logo(row["company"], logos),
                                "raw": float(row["ad_growth_pct"]),
                                "yoy_pct": row["ad_growth_pct"],
                            }
                        )

                    intensity_ranked = [r for r in ad_rows if r["ad_intensity_pct"] is not None]
                    intensity_ranked = sorted(intensity_ranked, key=lambda x: x["ad_intensity_pct"], reverse=True)
                    for idx, row in enumerate(intensity_ranked, start=1):
                        ad_intensity_cards.append(
                            {
                                "rank": idx,
                                "company": row["company"],
                                "value": f"{float(row['ad_intensity_pct']):.1f}%",
                                "color": _company_color(row["company"]),
                                "logo": _resolve_logo(row["company"], logos),
                                "raw": float(row["ad_intensity_pct"]),
                                "yoy_pct": row["ad_intensity_yoy_pct"],
                            }
                        )
    except Exception:
        pass

if revenue_cards:
    leaderboard_sections.append({"title": "Revenue", "subtitle": f"Top annual revenue leaders · sorted highest to lowest · {latest_year}", "cards": revenue_cards})
if ad_revenue_cards:
    leaderboard_sections.append({"title": "Advertising Revenue", "subtitle": f"Top ad monetization leaders · sorted highest to lowest · {latest_year}", "cards": ad_revenue_cards})
if ad_growth_cards:
    leaderboard_sections.append({"title": "Ad Growth", "subtitle": f"Top year-over-year ad growth leaders · sorted highest to lowest · {latest_year}", "cards": ad_growth_cards})
if ad_intensity_cards:
    leaderboard_sections.append({"title": "Ad Intensity", "subtitle": f"Ad revenue as % of total revenue · sorted highest to lowest · {latest_year}", "cards": ad_intensity_cards})
if market_cap_cards:
    leaderboard_sections.append({"title": "Market Cap", "subtitle": f"Top market capitalization leaders · sorted highest to lowest · {latest_year}", "cards": market_cap_cards})
if rd_cards:
    leaderboard_sections.append({"title": "R&D", "subtitle": f"Top innovation spend leaders · sorted highest to lowest · {latest_year}", "cards": rd_cards})

auto_insights_df = _load_auto_insights(workbook_path, latest_year)
yearly_comments = _load_homepage_yearly_comments(
    excel_path=str(workbook_path) if workbook_path else "",
    source_stamp=source_stamp,
    selected_year=latest_year,
)

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
    display: block;
    text-decoration: none !important;
    border-radius: 14px;
    padding: 14px 14px;
    color: #fff !important;
    border: 1px solid transparent;
    transition: transform 0.16s ease, filter 0.16s ease;
}}

.wm-nav-btn:hover {{
    transform: translateY(-2px);
    filter: brightness(1.05);
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

.wm-nav-overview {{ background: #1d4ed8; border-color: #1e40af; }}
.wm-nav-earnings {{ background: #0891b2; border-color: #0e7490; }}
.wm-nav-stocks {{ background: #15803d; border-color: #166534; }}
.wm-nav-genie {{ background: #4338ca; border-color: #3730a3; }}

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

@media (max-width: 768px) {{
    .wm-wrap {{ padding: 0 6px 24px; }}
    .wm-hero {{ padding: 28px 20px; }}
    .wm-title {{ font-size: 2rem; }}
}}
</style>
""",
    unsafe_allow_html=True,
)

# Hero image band between header and page body
if hero_home_b64:
    hero_logo_bar_html = _build_hero_company_logo_bar(logos)
    st.markdown(
        f"""
        <style>
          .wm-page-hero {{
            display: block;
            width: calc(100% + 3rem);
            margin-left: -1.5rem;
            margin-right: -1.5rem;
            margin-top: -1px;
            min-height: clamp(300px, 40vh, 520px);
            background-image: url('data:{hero_home_mime};base64,{hero_home_b64}');
            background-size: cover;
            background-position: top center;
            background-repeat: no-repeat;
            position: relative;
            overflow: hidden;
          }}
          .wm-hero-logo-bar {{
            position: absolute;
            left: 20px;
            right: 20px;
            bottom: 14px;
            z-index: 3;
            display: flex;
            align-items: center;
            gap: 12px;
            min-height: 82px;
            border-radius: 16px;
            padding: 14px 16px;
            overflow-x: auto;
            background: rgba(255,255,255,0.14);
            border: 1px solid rgba(255,255,255,0.34);
            backdrop-filter: blur(10px);
          }}
          .wm-hero-logo-link {{
            display: inline-flex;
            text-decoration: none !important;
            border-radius: 999px;
            transition: transform 120ms ease, filter 120ms ease;
          }}
          .wm-hero-logo-link:hover {{
            transform: translateY(-1px) scale(1.04);
            filter: drop-shadow(0 4px 10px rgba(15,23,42,0.34));
          }}
          .wm-hero-logo-wrap {{
            width: 56px;
            height: 56px;
            min-width: 56px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.38);
          }}
          .wm-hero-logo {{
            width: 34px;
            height: 34px;
            object-fit: contain;
          }}
          .wm-page-hero::after {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(to bottom, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.0) 100%);
            pointer-events: none;
          }}
        </style>
        <div class="wm-page-hero">{hero_logo_bar_html}</div>
        """,
        unsafe_allow_html=True,
    )

# Render
st.markdown("<div class='wm-wrap'>", unsafe_allow_html=True)

kpi_change_label = "No prior-year baseline"
if revenue_growth_pct is not None:
    arrow = "↑" if revenue_growth_pct >= 0 else "↓"
    kpi_change_label = f"{arrow} {abs(revenue_growth_pct):.1f}% YoY"

company_count = len(df_latest["company"].dropna().unique()) if not df_latest.empty else len(companies)
hero_sentence = _build_hero_narrative(
    latest_year,
    _format_money_musd(total_revenue_latest, 1),
    revenue_growth_pct,
    company_count,
)

if market_cap_growth_pct is not None:
    sign = "↑" if market_cap_growth_pct >= 0 else "↓"
    market_cap_label = f"{sign} {abs(market_cap_growth_pct):.1f}% YoY"
else:
    market_cap_label = "Aggregated valuation"

if margin_delta_bps is not None:
    if margin_delta_bps > 0:
        margin_label = f"↑ expanding +{margin_delta_bps}bps YoY"
    elif margin_delta_bps < 0:
        margin_label = f"↓ compressing {margin_delta_bps}bps YoY"
    else:
        margin_label = "Margin held flat YoY"
else:
    margin_label = "Net income / Revenue"

if rd_growth_pct is not None:
    sign = "↑" if rd_growth_pct >= 0 else "↓"
    rd_label = f"{sign} {abs(rd_growth_pct):.1f}% more invested YoY" if rd_growth_pct >= 0 else f"↓ {abs(rd_growth_pct):.1f}% less invested YoY"
else:
    rd_label = f"${total_rd_latest / 1000:.1f}B invested" if total_rd_latest else "R&D spend"

st.markdown(
    f"""
<div class="wm-hero">
  <div class="wm-status"><span class="wm-status-dot"></span>Live Data • {latest_year}</div>
  <h1 class="wm-title">Competitive Monetization Intelligence</h1>
  <div class="wm-subtitle">
    Strategic signal layer across technology and media leaders.<br>{escape(hero_sentence)}
  </div>
  <div class="wm-kpi-grid">
    <div class="wm-kpi-card">
      <div class="wm-kpi-label">Total Revenue</div>
      <div class="wm-kpi-value">{_format_money_musd(total_revenue_latest, 1)}</div>
      <div class="wm-kpi-change">{kpi_change_label}</div>
    </div>
    <div class="wm-kpi-card">
      <div class="wm-kpi-label">Combined Market Cap</div>
      <div class="wm-kpi-value">{_format_money_musd(total_market_cap_latest, 1)}</div>
      <div class="wm-kpi-change">{market_cap_label}</div>
    </div>
    <div class="wm-kpi-card">
      <div class="wm-kpi-label">Industry Profit Margin</div>
      <div class="wm-kpi-value">{f'{profit_margin_pct:.1f}%' if profit_margin_pct is not None else 'N/A'}</div>
      <div class="wm-kpi-change">{margin_label}</div>
    </div>
    <div class="wm-kpi-card">
      <div class="wm-kpi-label">R&D Intensity</div>
      <div class="wm-kpi-value">{f'{rd_intensity_pct:.1f}%' if rd_intensity_pct is not None else 'N/A'}</div>
      <div class="wm-kpi-change">{rd_label}</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

narrative_text = yearly_comments.get("narrative", "")
if narrative_text:
    narrative_text = narrative_text.replace("{year}", str(latest_year))
    narrative_text = narrative_text.replace("{revenue}", _format_money_musd(total_revenue_latest, 1))
    if revenue_growth_pct is not None:
        narrative_text = narrative_text.replace("{pct}", f"{abs(revenue_growth_pct):.1f}")
    st.markdown(
        f"""
        <div class='wm-narrative-block'>
            <div class='wm-narrative-label'>📋 Annual Snapshot — {latest_year}</div>
            <p class='wm-narrative-text'>{escape(narrative_text)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div class='wm-section-title'>🎯 Strategic Signals</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='wm-priority-legend'>"
    "<strong>Priority legend</strong>: "
    "<strong>High</strong> = strongest magnitude + cross-market structural impact for the selected period; "
    "<strong>Medium</strong> = meaningful trend with moderate breadth; "
    "<strong>Low</strong> = early signal or narrower/single-cohort movement."
    "</div>",
    unsafe_allow_html=True,
)

if auto_insights_df.empty:
    fallback_signals = [
        {
            "priority": "high",
            "title": "Duopoly Dominance Persists",
            "text": "Alphabet and Meta continue to command the largest share of tracked advertising pools, preserving concentration power.",
            "companies": "Alphabet|Meta Platforms",
        },
        {
            "priority": "medium",
            "title": "Efficiency and Margin Discipline",
            "text": f"Industry profit margin currently sits at {profit_margin_pct:.1f}% with ongoing cost controls and selective growth bets."
            if profit_margin_pct is not None
            else "Profitability remains central, with companies balancing growth against cost discipline.",
            "companies": "Microsoft|Meta Platforms|Netflix",
        },
        {
            "priority": "medium",
            "title": "R&D Investment Cycle",
            "text": f"R&D intensity is {rd_intensity_pct:.1f}% of revenue, reinforcing strategic focus on AI and platform differentiation."
            if rd_intensity_pct is not None
            else "R&D investment remains elevated as the platform cycle shifts toward AI-era infrastructure.",
            "companies": "Alphabet|Microsoft|Amazon",
        },
    ]
    cards = []
    for insight in fallback_signals:
        priority = str(insight["priority"]).strip().lower()
        if priority not in {"high", "medium", "low"}:
            priority = "medium"
        cards.append(
            "<div class='wm-insight-card'>"
            f"<div class='wm-priority wm-priority-{priority}'>{escape(priority.upper())}</div>"
            f"{_render_company_logos(insight.get('companies', ''), logos)}"
            f"<div class='wm-insight-title'>{escape(_clean_signal_title(insight.get('title', 'Untitled')))}</div>"
            f"<p class='wm-insight-text'>{escape(str(insight.get('text', '')))}</p>"
            "<div style=\"margin-top:12px; padding-top:10px; border-top:1px solid rgba(15,23,42,0.07);\">"
            "<a href=\"/Overview\" target=\"_self\" "
            "style=\"font-size:0.8rem; font-weight:700; color:#0073FF; text-decoration:none; display:inline-flex; align-items:center; gap:4px; letter-spacing:0.01em;\">"
            "Explore in Overview&nbsp;→"
            "</a>"
            "</div>"
            "</div>"
        )
    st.markdown(f"<div class='wm-insight-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)
else:
    cards = []
    for _, row in auto_insights_df.iterrows():
        priority = str(row.get("priority", "medium")).strip().lower()
        if priority not in {"high", "medium", "low"}:
            priority = "medium"
        title = _clean_signal_title(row.get("title", "Untitled"))
        text = str(row.get("text", row.get("comment", ""))).strip()
        companies_raw = str(row.get("companies", "")).strip()
        cards.append(
            "<div class='wm-insight-card'>"
            f"<div class='wm-priority wm-priority-{priority}'>{escape(priority.upper())}</div>"
            f"{_render_company_logos(companies_raw, logos)}"
            f"<div class='wm-insight-title'>{escape(title)}</div>"
            f"<p class='wm-insight-text'>{escape(text)}</p>"
            "<div style=\"margin-top:12px; padding-top:10px; border-top:1px solid rgba(15,23,42,0.07);\">"
            "<a href=\"/Overview\" target=\"_self\" "
            "style=\"font-size:0.8rem; font-weight:700; color:#0073FF; text-decoration:none; display:inline-flex; align-items:center; gap:4px; letter-spacing:0.01em;\">"
            "Explore in Overview&nbsp;→"
            "</a>"
            "</div>"
            "</div>"
        )
    st.markdown(f"<div class='wm-insight-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)

st.markdown(f"<div class='wm-section-title'>🏆 Company KPI Leaderboards — {latest_year}</div>", unsafe_allow_html=True)
if not leaderboard_sections:
    st.info("KPI leaderboards will appear once yearly metrics are available.")
else:
    st.caption("Scroll horizontally to explore all companies in each KPI strip.")
    for section in leaderboard_sections:
        _render_leaderboard_strip(
            title=section.get("title", "KPI"),
            subtitle=section.get("subtitle", ""),
            cards=section.get("cards", []),
        )

source_label = str(workbook_path) if workbook_path else "not found"
st.markdown(
    f"<div class='wm-foot'>Source: {escape(source_label)} • Period baseline: {latest_year}</div>",
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)
