import os
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

# Must stay first Streamlit command
st.set_page_config(
    page_title="Global Media Intelligence",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.global_fonts import apply_global_fonts
from utils.header import display_header
from utils.logos import load_company_logos
from utils.state_management import get_data_processor
from utils.theme import get_theme_mode
from utils.transcript_startup_sync import sync_local_transcripts_to_workbook

apply_global_fonts()

# One-time sync per container startup (not per session)
SYNC_FLAG_FILE = "/tmp/transcript_sync_done"


def _run_startup_transcript_sync() -> None:
    if os.path.exists(SYNC_FLAG_FILE):
        return
    try:
        sync_local_transcripts_to_workbook()
        with open(SYNC_FLAG_FILE, "w", encoding="utf-8") as handle:
            handle.write(str(datetime.now()))
    except Exception as exc:
        st.warning(f"Transcript sync failed: {exc}")


_run_startup_transcript_sync()


# Query-param navigation support (same behavior as before)
query_params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()


def _first_param(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


nav_param = _first_param(query_params.get("nav")) if query_params else None
go_param = _first_param(query_params.get("go")) if query_params else None
page_param = _first_param(query_params.get("page")) if query_params else None
company_param = _first_param(query_params.get("company")) if query_params else None

target_param = nav_param or go_param or page_param
if target_param:
    target_key = str(target_param).strip().lower()
    page_map = {
        "overview": "pages/00_Overview.py",
        "earnings": "pages/01_Earnings.py",
        "01_earnings": "pages/01_Earnings.py",
        "stocks": "pages/02_Stocks.py",
        "editorial": "pages/03_Editorial.py",
        "genie": "pages/04_Genie.py",
        "financial_genie": "pages/04_Genie.py",
        "financial-genie": "pages/04_Genie.py",
    }
    if target_key in page_map:
        if target_key in {"earnings", "01_earnings"} and company_param:
            st.session_state["prefill_company"] = company_param
        try:
            st.query_params.clear()
        except Exception:
            pass
        st.switch_page(page_map[target_key])


display_header(enable_dom_patch=False)

sync_col_left, sync_col_right = st.columns([6, 2])
with sync_col_right:
    if st.button("🔄 Sync Transcripts", help="Manually sync transcript data", use_container_width=True):
        if os.path.exists(SYNC_FLAG_FILE):
            os.remove(SYNC_FLAG_FILE)
        with st.spinner("Syncing transcripts..."):
            try:
                sync_local_transcripts_to_workbook()
                with open(SYNC_FLAG_FILE, "w", encoding="utf-8") as handle:
                    handle.write(str(datetime.now()))
                st.success("Sync complete!")
            except Exception as exc:
                st.error(f"Sync failed: {exc}")


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent


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


def _render_leaderboard_strip(title: str, subtitle: str, cards: List[dict]) -> None:
    if not cards:
        return
    header_html = (
        "<div class='wm-strip-header'>"
        f"<div class='wm-strip-title'>{escape(str(title))}</div>"
        f"<div class='wm-strip-subtitle'>{escape(str(subtitle))}</div>"
        "</div>"
    )

    card_blocks = []
    for card in cards:
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
        card_blocks.append(
            f"<div class='wm-company-card wm-strip-card' style='--wm-color:{company_color};'>"
            f"{rank_badge}"
            "<div class='wm-company-head'>"
            f"{logo_html}<span class='wm-company-name'>{escape(company_name)}</span>"
            "</div>"
            f"<div class='wm-company-value'>{value_text}</div>"
            f"<div class='wm-company-caption'>{escape(title)}</div>"
            "</div>"
        )

    st.markdown(
        f"{header_html}<div class='wm-hscroll'>{''.join(card_blocks)}</div>",
        unsafe_allow_html=True,
    )


def _resolve_workbook_path(data_processor) -> Optional[Path]:
    candidates = []
    if data_processor is not None and getattr(data_processor, "data_path", None):
        candidates.append(Path(data_processor.data_path))
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


# Load data
logos = load_company_logos()
mode = get_theme_mode()
is_dark = mode == "dark"

data_processor = None
metrics_df = pd.DataFrame()
companies: List[str] = []

try:
    data_processor = get_data_processor()
    raw_metrics = getattr(data_processor, "df_metrics", pd.DataFrame())
    if raw_metrics is not None:
        metrics_df = raw_metrics.copy()
    companies = data_processor.get_companies() if hasattr(data_processor, "get_companies") else []
except Exception as exc:
    st.warning(f"Data initialization warning: {exc}")

workbook_path = _resolve_workbook_path(data_processor)

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

if not df_latest.empty:
    top_by_revenue = df_latest[["company", "revenue"]].dropna(subset=["revenue"]).nlargest(5, "revenue")
else:
    top_by_revenue = pd.DataFrame(columns=["company", "revenue"])

growth_df = pd.DataFrame()
if not df_latest.empty and not df_prev.empty:
    prev_rev = df_prev[["company", "revenue"]].rename(columns={"revenue": "revenue_prev"})
    growth_df = df_latest[["company", "revenue"]].merge(prev_rev, on="company", how="left")
    growth_df["growth_pct"] = growth_df.apply(
        lambda row: _safe_pct(row["revenue"] - row["revenue_prev"], row["revenue_prev"]),
        axis=1,
    )
    growth_df = growth_df.dropna(subset=["growth_pct"]).nlargest(3, "growth_pct")

# Build per-company KPI leaderboard payloads (all companies, horizontal scroll rows).
leaderboard_sections = []
growth_sections = []

if not df_latest.empty:
    metric_sections = [
        ("Revenue", "revenue", "Annual revenue leaders"),
        ("Net Income", "net_income", "Bottom-line leaders"),
        ("Operating Income", "operating_income", "Core profitability leaders"),
        ("Market Cap", "market_cap", "Market value concentration"),
        ("Debt", "debt", "Highest leverage by absolute debt"),
        ("Cash Balance", "cash_balance", "Liquidity leaders"),
        ("R&D", "rd", "Innovation spend leaders"),
        ("Capex", "capex", "Infrastructure investment leaders"),
    ]
    for title, key, subtitle in metric_sections:
        if key not in df_latest.columns:
            continue
        block = df_latest[["company", key]].dropna(subset=[key]).copy()
        if block.empty:
            continue
        block = block.sort_values(key, ascending=False)
        cards = []
        for rank, (_, row) in enumerate(block.iterrows(), start=1):
            company_name = str(row["company"])
            value = row[key]
            cards.append(
                {
                    "rank": rank,
                    "company": company_name,
                    "value": _format_money_musd(value, 1),
                    "color": _company_color(company_name),
                    "logo": _resolve_logo(company_name, logos),
                }
            )
        leaderboard_sections.append({"title": title, "subtitle": subtitle, "cards": cards})

        yoy_col = f"{key}_yoy"
        if yoy_col in df_latest.columns:
            growth_block = (
                df_latest[["company", yoy_col]]
                .rename(columns={yoy_col: "growth"})
                .dropna(subset=["growth"])
                .sort_values("growth", ascending=False)
            )
        else:
            growth_block = pd.DataFrame()
            if not df_prev.empty and key in df_prev.columns:
                prev_block = (
                    df_prev[["company", key]]
                    .dropna(subset=[key])
                    .rename(columns={key: "prev_value"})
                )
                growth_block = (
                    df_latest[["company", key]]
                    .dropna(subset=[key])
                    .merge(prev_block, on="company", how="left")
                )
                growth_block["growth"] = growth_block.apply(
                    lambda r: _safe_pct(r[key] - r["prev_value"], r["prev_value"]),
                    axis=1,
                )
                growth_block = growth_block.dropna(subset=["growth"]).sort_values("growth", ascending=False)

        if not growth_block.empty:
            g_cards = []
            for rank, (_, row) in enumerate(growth_block.iterrows(), start=1):
                company_name = str(row["company"])
                g_cards.append(
                    {
                        "rank": rank,
                        "company": company_name,
                        "value": f"{float(row['growth']):+.1f}%",
                        "color": _company_color(company_name),
                        "logo": _resolve_logo(company_name, logos),
                    }
                )
            growth_sections.append(
                {
                    "title": f"{title} Growth",
                    "subtitle": "YoY leaderboard",
                    "cards": g_cards,
                }
            )

# Advertising revenue leaderboard from annual ad sheet (if available).
if workbook_path and workbook_path.exists():
    try:
        ad_df = pd.read_excel(workbook_path, sheet_name="Company_advertising_revenue")
        ad_df.columns = [str(c).strip() for c in ad_df.columns]
        if "Year" in ad_df.columns:
            ad_df["Year"] = pd.to_numeric(ad_df["Year"], errors="coerce")
            ad_row = ad_df[ad_df["Year"] == int(latest_year)].copy()
            if not ad_row.empty:
                ad_row = ad_row.iloc[0]
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
                cards = []
                for col, company_name in ad_map.items():
                    if col not in ad_df.columns:
                        continue
                    value = pd.to_numeric(ad_row.get(col), errors="coerce")
                    if pd.isna(value):
                        continue
                    # Sheet values are USD billions.
                    value_musd = float(value) * 1000.0
                    cards.append(
                        {
                            "company": company_name,
                            "raw": value_musd,
                            "value": _format_money_musd(value_musd, 1),
                            "color": _company_color(company_name),
                            "logo": _resolve_logo(company_name, logos),
                        }
                    )
                cards = sorted(cards, key=lambda x: x["raw"], reverse=True)
                for idx, card in enumerate(cards, start=1):
                    card["rank"] = idx
                if cards:
                    leaderboard_sections.insert(
                        3,
                        {
                            "title": "Advertising Revenue",
                            "subtitle": "Ad monetization leaders",
                            "cards": cards,
                        },
                    )
    except Exception:
        pass

auto_insights_df = _load_auto_insights(workbook_path, latest_year)

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

# Render
st.markdown("<div class='wm-wrap'>", unsafe_allow_html=True)

kpi_change_label = "No prior-year baseline"
if revenue_growth_pct is not None:
    arrow = "↑" if revenue_growth_pct >= 0 else "↓"
    kpi_change_label = f"{arrow} {abs(revenue_growth_pct):.1f}% YoY"

company_count = len(df_latest["company"].dropna().unique()) if not df_latest.empty else len(companies)

st.markdown(
    f"""
<div class="wm-hero">
  <div class="wm-status"><span class="wm-status-dot"></span>Live Data • {latest_year}</div>
  <h1 class="wm-title">Global Media Economy Intelligence</h1>
  <div class="wm-subtitle">
    Strategic signal layer across technology and media leaders. Tracking <strong>{company_count}</strong> companies,
    <strong>{_format_money_musd(total_revenue_latest, 1)}</strong> in annual revenue, and cross-market structure changes in one view.
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
      <div class="wm-kpi-change">Aggregated valuation</div>
    </div>
    <div class="wm-kpi-card">
      <div class="wm-kpi-label">Industry Profit Margin</div>
      <div class="wm-kpi-value">{f'{profit_margin_pct:.1f}%' if profit_margin_pct is not None else 'N/A'}</div>
      <div class="wm-kpi-change">Net income / Revenue</div>
    </div>
    <div class="wm-kpi-card">
      <div class="wm-kpi-label">R&D Intensity</div>
      <div class="wm-kpi-value">{f'{rd_intensity_pct:.1f}%' if rd_intensity_pct is not None else 'N/A'}</div>
      <div class="wm-kpi-change">{_format_money_musd(total_rd_latest, 1)} invested</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="wm-nav-grid">
  <a class="wm-nav-btn wm-nav-overview" href="?nav=overview" target="_self">
    <div class="wm-nav-title">Executive Overview</div>
    <div class="wm-nav-desc">Macro regime, concentration, and strategic narratives</div>
  </a>
  <a class="wm-nav-btn wm-nav-earnings" href="?nav=earnings" target="_self">
    <div class="wm-nav-title">Earnings Analysis</div>
    <div class="wm-nav-desc">Company metrics, segments, and commentary drilldowns</div>
  </a>
  <a class="wm-nav-btn wm-nav-stocks" href="?nav=stocks" target="_self">
    <div class="wm-nav-title">Market Performance</div>
    <div class="wm-nav-desc">Price action, index context, and valuation movement</div>
  </a>
  <a class="wm-nav-btn wm-nav-genie" href="?nav=genie" target="_self">
    <div class="wm-nav-title">AI Assistant</div>
    <div class="wm-nav-desc">Context-aware Q&A over metrics and transcript intelligence</div>
  </a>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown("<div class='wm-section-title'>🎯 Strategic Signals</div>", unsafe_allow_html=True)

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
            f"<div class='wm-insight-title'>{escape(str(insight.get('title', 'Untitled')))}</div>"
            f"<p class='wm-insight-text'>{escape(str(insight.get('text', '')))}</p>"
            "</div>"
        )
    st.markdown(f"<div class='wm-insight-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)
else:
    cards = []
    for _, row in auto_insights_df.iterrows():
        priority = str(row.get("priority", "medium")).strip().lower()
        if priority not in {"high", "medium", "low"}:
            priority = "medium"
        title = str(row.get("title", "Untitled")).strip()
        text = str(row.get("text", row.get("comment", ""))).strip()
        companies_raw = str(row.get("companies", "")).strip()
        cards.append(
            "<div class='wm-insight-card'>"
            f"<div class='wm-priority wm-priority-{priority}'>{escape(priority.upper())}</div>"
            f"{_render_company_logos(companies_raw, logos)}"
            f"<div class='wm-insight-title'>{escape(title)}</div>"
            f"<p class='wm-insight-text'>{escape(text)}</p>"
            "</div>"
        )
    st.markdown(f"<div class='wm-insight-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)

st.markdown(f"<div class='wm-section-title'>🏆 Company KPI Leaderboards — {latest_year}</div>", unsafe_allow_html=True)
if not leaderboard_sections:
    st.info("KPI leaderboards will appear once yearly metrics are available.")
else:
    st.caption("Horizontal strips: drag or scroll to browse all companies in each KPI.")
    for section in leaderboard_sections:
        _render_leaderboard_strip(
            title=section.get("title", "KPI"),
            subtitle=section.get("subtitle", ""),
            cards=section.get("cards", []),
        )

if growth_sections:
    st.markdown("<div class='wm-section-title'>🚀 Fastest Growing by KPI</div>", unsafe_allow_html=True)
    st.caption("YoY growth strips from the same KPI library.")
    for section in growth_sections:
        _render_leaderboard_strip(
            title=section.get("title", "Growth"),
            subtitle=section.get("subtitle", ""),
            cards=section.get("cards", []),
        )

st.markdown(
    """
<div class="wm-cta">
  <div class="wm-cta-title">Strategic Next Steps</div>
  <div class="wm-cta-text">
    Use the overview for regime context, move to earnings for company-level operating detail,
    and use Genie for rapid hypothesis checks against transcripts and financial metrics.
  </div>
  <div class="wm-cta-actions">
    <a class="wm-cta-btn" href="?nav=overview" target="_self">📊 Open Executive Overview</a>
    <a class="wm-cta-btn" href="?nav=earnings" target="_self">💰 Open Earnings Analysis</a>
    <a class="wm-cta-btn wm-ghost" href="?nav=stocks" target="_self">📈 Open Market Performance</a>
    <a class="wm-cta-btn wm-ghost" href="?nav=genie" target="_self">🤖 Open AI Assistant</a>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

source_label = str(workbook_path) if workbook_path else "not found"
st.markdown(
    f"<div class='wm-foot'>Source: {escape(source_label)} • Period baseline: {latest_year}</div>",
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)
