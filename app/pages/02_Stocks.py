import streamlit as st

# Page config must be the first Streamlit command
st.set_page_config(page_title="Stocks", page_icon="📈", layout="wide")

from utils.global_fonts import apply_global_fonts
apply_global_fonts()


from utils.page_transition import apply_page_transition_fix

# Apply fix for page transitions to prevent background bleed-through
apply_page_transition_fix()

from utils.auth import check_password
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from stock_processor_fix import StockDataProcessor  # Use the fixed version
from data_processor import FinancialDataProcessor
from utils.helpers import format_number
from datetime import datetime, timedelta
from PIL import Image
import base64
import os
import re
from io import BytesIO
from pathlib import Path
from utils.styles import get_page_style, get_animation_style
from utils.workbook_market_data import load_combined_stock_market_data
from utils.workbook_source import get_workbook_source_stamp

# Apply global styles at page load for better performance
st.markdown(get_page_style(), unsafe_allow_html=True)
st.markdown(get_animation_style(), unsafe_allow_html=True)

# Add header with language selector
from utils.header import render_header
from utils.language import get_text
st.session_state["active_nav_page"] = "stocks"
st.session_state["_active_nav_page"] = "stocks"
render_header()

# Add SQL Assistant in the sidebar
from utils.sql_assistant_sidebar import render_sql_assistant_sidebar
if not st.session_state.get("hide_sidebar_nav", False):
    render_sql_assistant_sidebar()

# Add the plotly config near the top after other constants
plotly_config = {
    'displayModeBar': True,
    'modeBarButtonsToRemove': [
        'zoom', 'pan', 'select', 'lasso2d', 'zoomIn', 'zoomOut',
        'autoScale', 'resetScale', 'resetViewMapbox', 'zoomInMapbox',
        'zoomOutMapbox', 'resetViewMapbox', 'hoverClosestCartesian',
        'hoverCompareCartesian'
    ],
    'modeBarButtonsToAdd': ['fullscreen'],
    'displaylogo': False
}

# Check if user is logged in, redirect to Welcome page if not
# Always authenticated - no password check needed
from utils.time_utils import render_floating_clock
render_floating_clock()

# Initialize data processor in session state if not already present
if 'data_processor' not in st.session_state:
    data_processor = FinancialDataProcessor()
    data_processor.load_data()
    st.session_state['data_processor'] = data_processor

# Initialize stock processor in session state if not already present
if 'stock_processor' not in st.session_state:
    st.session_state.stock_processor = StockDataProcessor()

# Initialize stock data cache in session state
if 'stock_data_cache' not in st.session_state:
    st.session_state.stock_data_cache = {}

# Define company colors for consistency across visualizations
COMPANY_COLORS = {
    'Apple': ('#000000', 'black'),
    'Microsoft': ('#00A4EF', 'blue'),
    'Alphabet': ('#4285F4', 'blue'),
    'Amazon': ('#FF9900', 'orange'),
    'Meta': ('#0668E1', 'blue'),
    'Meta Platforms': ('#0668E1', 'blue'),
    'Netflix': ('#E50914', 'red'),
    'Disney': ('#113CCF', 'blue'),
    'Spotify': ('#1ED760', 'green'),
    'Roku': ('#6F1AB1', 'purple'),
    'Comcast': ('#FFBA00', 'yellow'),
    'Paramount': ('#000A3B', 'navy'),
    'Paramount Global': ('#000A3B', 'navy'),
    'Warner Bros Discovery': ('#D0A22D', 'gold'),
    'Warner Bros. Discovery': ('#D0A22D', 'gold'),
    'Other US Companies': ('#212121', 'darkgrey')
}

ASSET_DIR = Path(__file__).resolve().parents[1] / "attached_assets"
EXCLUDED_STOCK_KEYS = {"m2", "mstr", "microstrategy", "app", "applovin", "gold", "gld"}
MARKET_INDICATOR_ORDER = ["Nasdaq", "Bitcoin", "S&P 500"]
MARKET_INDICATOR_KEYS = {
    re.sub(r"[^a-z0-9]+", "", label.lower()): index
    for index, label in enumerate(MARKET_INDICATOR_ORDER)
}


def _normalize_company_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _is_excluded_stock(name):
    key = _normalize_company_key(name)
    if not key:
        return False
    if key in EXCLUDED_STOCK_KEYS:
        return True
    return "microstrategy" in key or "applovin" in key


def _is_market_indicator(name):
    return _normalize_company_key(name) in MARKET_INDICATOR_KEYS


def _split_company_groups(names):
    seen = set()
    companies = []
    indicators = []
    for raw_name in names or []:
        name = str(raw_name or "").strip()
        key = _normalize_company_key(name)
        if not key or key in seen or _is_excluded_stock(name):
            continue
        seen.add(key)
        if _is_market_indicator(name):
            indicators.append(name)
        else:
            companies.append(name)
    companies.sort(key=lambda s: s.lower())
    indicators.sort(key=lambda s: MARKET_INDICATOR_KEYS.get(_normalize_company_key(s), 999))
    return companies, indicators


def _first_existing_logo(*names):
    for name in names:
        if not name:
            continue
        candidate = ASSET_DIR / name
        if candidate.exists():
            return candidate
    return None

def _parse_numeric(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    multiplier = 1.0
    if text.endswith("K"):
        multiplier = 1_000.0
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1_000_000.0
        text = text[:-1]
    elif text.endswith("B"):
        multiplier = 1_000_000_000.0
        text = text[:-1]
    elif text.endswith("T"):
        multiplier = 1_000_000_000_000.0
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _format_currency(value, decimals=2):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    return f"${value:,.{decimals}f}"


def _format_percent(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def _format_ratio(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    return f"{value:.1f}x"


def _format_volume(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    value = float(value)
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"


def _format_money_millions(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    return f"${format_number(value)}"


def _format_shares_millions(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    return format_number(value)


def _build_sparkline_svg(series, color="#16A34A", width=140, height=40):
    if series is None:
        return ""
    try:
        if isinstance(series, pd.Series):
            values = series.dropna().astype(float).tolist()
        else:
            values = [
                float(v)
                for v in series
                if v is not None and not (isinstance(v, float) and pd.isna(v))
            ]
    except Exception:
        return ""
    if len(values) < 2:
        return ""
    if len(values) > 60:
        step = max(1, len(values) // 60)
        values = values[::step][:60]
    min_val = min(values)
    max_val = max(values)
    span = max(max_val - min_val, 1e-9)
    points = []
    for idx, value in enumerate(values):
        x = 1 + (idx / (len(values) - 1)) * (width - 2)
        y = 1 + (1 - (value - min_val) / span) * (height - 2)
        points.append(f"{x:.1f},{y:.1f}")
    return (
        f"<svg class='stock-sparkline' viewBox='0 0 {width} {height}' "
        "preserveAspectRatio='none'>"
        f"<polyline fill='none' stroke='{color}' stroke-width='2' "
        "stroke-linecap='round' stroke-linejoin='round' "
        f"points='{ ' '.join(points) }'/>"
        "</svg>"
    )


@st.cache_data(show_spinner=False)
def load_stock_fundamentals(data_path):
    if not data_path or not os.path.exists(data_path):
        return pd.DataFrame()
    try:
        merged = load_combined_stock_market_data(
            excel_path=data_path,
            source_stamp=int(get_workbook_source_stamp(data_path) or 0),
            include_baseline=True,
            include_daily=True,
            include_minute=True,
        )
    except Exception:
        return pd.DataFrame()

    if merged is None or merged.empty:
        return pd.DataFrame()

    df = merged.copy()
    if "market_cap" not in df.columns:
        df["market_cap"] = None
    if "outstanding_shares" not in df.columns:
        df["outstanding_shares"] = None
    if "tag" not in df.columns:
        df["tag"] = ""
    if "volume" not in df.columns:
        df["volume"] = None

    required = {"date", "price", "asset", "tag"}
    if not required.issubset(set(df.columns)):
        return pd.DataFrame()
    df = df[["date", "price", "volume", "market_cap", "outstanding_shares", "asset", "tag"]].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ("price", "volume", "market_cap", "outstanding_shares"):
        df[col] = df[col].apply(_parse_numeric)
    return df.dropna(subset=["date", "price"])


def _latest_available_year(years, end_date):
    if not years:
        return None
    end_year = end_date.year if end_date else max(years)
    eligible = [year for year in years if year <= end_year]
    return max(eligible) if eligible else max(years)


def _get_last_nonzero(series):
    if series is None or series.empty:
        return None
    series = series.dropna()
    if series.empty:
        return None
    series = series[series != 0]
    return series.iloc[-1] if not series.empty else None

#############################
# Start of Stocks Page Content
#############################

# Page title
st.title("📈 Stock Performance")

# Get data processor for metrics
_data_processor = st.session_state.data_processor

@st.cache_data(ttl=3600, show_spinner=False)
def load_company_logos():
    """Load and cache company logos with base64 encoding."""
    logo_paths = {
        "Apple": _first_existing_logo("apple_logo.png"),
        "Microsoft": _first_existing_logo("msft.png"),
        "Alphabet": _first_existing_logo("Google_logo.png"),
        "Netflix": _first_existing_logo("Netflix_logo.png"),
        "Meta": _first_existing_logo("Meta_logo.png"),
        "Meta Platforms": _first_existing_logo("Meta_logo.png"),
        "Amazon": _first_existing_logo("Amazon_icon.png"),
        "Disney": _first_existing_logo("icons8-logo-disney-240.png"),
        "Roku": _first_existing_logo("roku_logo.png"),
        "Spotify": _first_existing_logo("Spotify_logo.png"),
        "Comcast": _first_existing_logo("Comcast_logo.png"),
        "Paramount": _first_existing_logo("Paramount_logo.png"),
        "Paramount Global": _first_existing_logo("Paramount_logo.png"),
        "Warner Bros Discovery": _first_existing_logo("WarnerBrosDiscovery_log.png"),
        "Warner Bros. Discovery": _first_existing_logo("WarnerBrosDiscovery_log.png"),
        "Bitcoin": _first_existing_logo("Bitcoin_logo.png"),
        "Nasdaq": _first_existing_logo("Nasdaq_logo.png"),
        "S&P 500": _first_existing_logo("S&P500_logo.png"),
        "S&P500": _first_existing_logo("S&P500_logo.png"),
        "Gold": _first_existing_logo("Gold_logo.png"),
        "GLD": _first_existing_logo("Gold_logo.png"),
        "Nvidia": _first_existing_logo("Nvidia_logo.png"),
        "NVIDIA": _first_existing_logo("Nvidia_logo.png"),
        "NVDA": _first_existing_logo("Nvidia_logo.png"),
        "TTD": _first_existing_logo("TheTradeDesk_logo.png"),
        "The Trade Desk": _first_existing_logo("TheTradeDesk_logo.png"),
        "CRTO": _first_existing_logo("Criteo_logo.png"),
        "Criteo": _first_existing_logo("Criteo_logo.png"),
        "DSP": _first_existing_logo("ViantTechnology_logo.png"),
        "Viant Technology": _first_existing_logo("ViantTechnology_logo.png"),
        "U": _first_existing_logo("Utiq_logo.png"),
        "Utiq": _first_existing_logo("Utiq_logo.png"),
        "MGNI": _first_existing_logo("Magnite_logo.png"),
        "Magnite": _first_existing_logo("Magnite_logo.png"),
        "PUBM": _first_existing_logo("Pubmatic_logo.png"),
        "PubMatic": _first_existing_logo("Pubmatic_logo.png"),
        "DV": _first_existing_logo("DoubleVerify_logo.png"),
        "DoubleVerify": _first_existing_logo("DoubleVerify_logo.png"),
        "IAS": _first_existing_logo("IAS.png"),
        "Integral Ad Science": _first_existing_logo("IAS.png"),
    }

    logos = {}
    for company, path in logo_paths.items():
        if not path:
            continue
        try:
            with Image.open(path) as img:
                img = img.convert("RGBA")
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                logos[company] = base64.b64encode(buffered.getvalue()).decode()
        except Exception:
            continue
    return logos


def _render_company_card(company, company_logos, stock_processor, timeframe, button_prefix="company"):
    try:
        stock_data = stock_processor.get_company_data(company, timeframe)
        if not stock_data or "quote" not in stock_data:
            return False

        quote = stock_data["quote"]
        history = stock_data.get("history")
        price = quote.get("price", 0)
        change = quote.get("change", 0)
        change_percent = quote.get("change_percent", 0)
        if history is not None and not history.empty:
            history_close = history["Close"].dropna()
            if not history_close.empty:
                price = float(history_close.iloc[-1])
                first_price = float(history_close.iloc[0])
                change = price - first_price
                change_percent = (change / first_price * 100) if first_price else 0

        sparkline_svg = ""
        if history is not None and not history.empty:
            spark_color = "#16A34A" if change >= 0 else "#EF4444"
            sparkline_svg = _build_sparkline_svg(history["Close"], color=spark_color)
        sparkline_html = (
            f"<div class='company-sparkline'>{sparkline_svg}</div>"
            if sparkline_svg
            else ""
        )
        card_classes = "company-card indicator-card" if _is_market_indicator(company) else "company-card"
        logo_b64 = company_logos.get(company, "")
        logo_html = (
            f"<img src='data:image/png;base64,{logo_b64}' class='company-logo'>"
            if logo_b64
            else "<div class='company-logo'></div>"
        )

        with st.container():
            st.markdown(
                f"""
                <div class="{card_classes}" onclick="handleCompanyClick('{company}')">
                    <div class="company-card-content">
                        <div class="company-card-left">
                            {logo_html}
                            <div class="company-card-details">
                                <div class="company-card-name">{company}</div>
                                <div class="company-card-price">${price:.2f}</div>
                                <div class="company-card-change {'price-up' if change >= 0 else 'price-down'}">
                                    Last 3 Months {'+' if change_percent >= 0 else ''}{change_percent:.2f}%
                                </div>
                            </div>
                        </div>
                        {sparkline_html}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                f"View {company}",
                key=f"{button_prefix}_{_normalize_company_key(company)}",
            ):
                st.session_state.selected_company = company
                st.session_state.selected_timeframe = timeframe
                st.rerun()
        return True
    except Exception:
        return False


def _render_company_grid(companies, company_logos, stock_processor, timeframe, button_prefix, center_last_single=False):
    # Pre-filter: verify each company actually has renderable data
    # so that failed cards don't leave empty column slots in the grid.
    renderable = []
    for c in companies:
        try:
            _d = stock_processor.get_company_data(c, timeframe)
            if _d and "quote" in _d:
                renderable.append(c)
        except Exception:
            pass

    for start in range(0, len(renderable), 3):
        row = renderable[start:start + 3]
        if len(row) == 1 and center_last_single:
            _, middle, _ = st.columns([0.35, 1, 0.35])
            row_cols = [middle]
        elif len(row) == 2 and center_last_single:
            _, left, right, _ = st.columns([0.15, 1, 1, 0.15])
            row_cols = [left, right]
        else:
            row_cols = st.columns(3)
        for col, company in zip(row_cols, row):
            with col:
                _render_company_card(
                    company,
                    company_logos,
                    stock_processor,
                    timeframe,
                    button_prefix=button_prefix,
                )


def render_all_company_stocks_section():
    st.header("All Company Stocks")

    stock_processor = st.session_state.stock_processor
    companies_all_raw = (
        stock_processor.get_companies()
        if hasattr(stock_processor, "get_companies")
        else st.session_state["data_processor"].get_companies()
    )
    companies_main, companies_indicators = _split_company_groups(companies_all_raw)
    companies_all = companies_main + companies_indicators

    controls = st.columns([1.2, 1.2, 2.6])
    with controls[0]:
        multi_timeframe = st.selectbox(
            "Timeframe",
            ["1M", "3M", "6M", "1Y", "2Y", "5Y", "MAX"],
            index=1,
            key="all_stocks_timeframe",
        )
    with controls[1]:
        view_mode = st.selectbox(
            "View",
            ["Individual Charts", "Overlay (Indexed)", "Overlay (Price)"],
            index=0,
            key="all_stocks_view_mode",
        )
    with controls[2]:
        default_selection = st.session_state.get("all_stocks_companies")
        if default_selection:
            default_selection = [name for name in default_selection if name in companies_all]
        if not default_selection:
            default_selection = companies_all
        selected_companies = st.multiselect(
            "Companies",
            options=companies_all,
            default=default_selection,
            key="all_stocks_companies",
        )

    if not selected_companies:
        st.info("Select at least one company to show the chart.")
        return

    # ── Collect price data for all selected companies ──
    company_series = {}
    with st.spinner("Loading price histories..."):
        for company in selected_companies:
            try:
                stock_data = stock_processor.get_company_data(company, multi_timeframe)
                history = stock_data.get("history") if isinstance(stock_data, dict) else None
                if history is None or getattr(history, "empty", True):
                    continue
                series = pd.to_numeric(history.get("Close"), errors="coerce").dropna()
                if series.empty:
                    continue
                company_series[company] = series
            except Exception:
                continue

    if not company_series:
        st.info("No price history available for the selected companies/timeframe.")
        return

    if view_mode == "Individual Charts":
        # ── Trading-terminal style: one mini-chart per company ──
        n = len(company_series)
        cols_per_row = 3
        rows = (n + cols_per_row - 1) // cols_per_row
        names = list(company_series.keys())

        fig = make_subplots(
            rows=rows,
            cols=cols_per_row,
            subplot_titles=names + [""] * (rows * cols_per_row - n),
            vertical_spacing=0.08,
            horizontal_spacing=0.05,
        )

        for idx, (company, series) in enumerate(company_series.items()):
            row = idx // cols_per_row + 1
            col = idx % cols_per_row + 1
            color = (COMPANY_COLORS.get(company) or COMPANY_COLORS.get(company.strip()) or ("#64748b", ""))[0]
            # Compute period return for color
            start_price = float(series.iloc[0])
            end_price = float(series.iloc[-1])
            pct_change = ((end_price - start_price) / start_price * 100) if start_price else 0
            line_color = "#16A34A" if pct_change >= 0 else "#EF4444"
            # Fill area under the line
            fig.add_trace(
                go.Scatter(
                    x=series.index,
                    y=series,
                    mode="lines",
                    name=company,
                    showlegend=False,
                    line=dict(color=line_color, width=2),
                    fill="tozeroy",
                    fillcolor=f"rgba({int(line_color[1:3],16)},{int(line_color[3:5],16)},{int(line_color[5:7],16)},0.08)",
                    hovertemplate="%{x|%b %d, %Y}<br>$%{y:.2f}<extra></extra>",
                ),
                row=row,
                col=col,
            )

        chart_height = max(320, rows * 240)
        fig.update_layout(
            height=chart_height,
            margin=dict(l=40, r=20, t=40, b=20),
            font=dict(
                family="system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
                size=11,
                color="#e6edf3",
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        # Style each subplot axis
        for idx in range(len(company_series)):
            ax_suffix = "" if idx == 0 else str(idx + 1)
            fig.update_xaxes(
                showgrid=False, zeroline=False, showline=False,
                showticklabels=(idx // cols_per_row == rows - 1),  # only bottom row
                tickfont=dict(size=9, color="#8b949e"),
                row=idx // cols_per_row + 1,
                col=idx % cols_per_row + 1,
            )
            fig.update_yaxes(
                showgrid=True,
                gridcolor="rgba(48,54,61,0.4)",
                zeroline=False,
                showline=False,
                tickprefix="$",
                tickfont=dict(size=9, color="#8b949e"),
                row=idx // cols_per_row + 1,
                col=idx % cols_per_row + 1,
            )
        # Style subplot titles (company names)
        fig.update_annotations(font=dict(size=12, color="#e6edf3"))
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)

        # Summary strip: show current price + period return for each
        strip_cols = st.columns(min(len(company_series), 6))
        for i, (company, series) in enumerate(company_series.items()):
            col_idx = i % min(len(company_series), 6)
            start_p = float(series.iloc[0])
            end_p = float(series.iloc[-1])
            pct = ((end_p - start_p) / start_p * 100) if start_p else 0
            sign = "+" if pct >= 0 else ""
            clr = "#16A34A" if pct >= 0 else "#EF4444"
            with strip_cols[col_idx]:
                st.markdown(
                    f"<div style='text-align:center;padding:6px 0;'>"
                    f"<div style='font-weight:700;font-size:0.85rem;color:#e6edf3;'>{company}</div>"
                    f"<div style='font-size:1.05rem;font-weight:600;color:#e6edf3;'>${end_p:.2f}</div>"
                    f"<div style='font-size:0.82rem;color:{clr};font-weight:600;'>{sign}{pct:.1f}%</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
    else:
        # ── Overlay mode: all companies on same chart ──
        is_indexed = view_mode == "Overlay (Indexed)"
        fig = go.Figure()
        for company, series in company_series.items():
            if is_indexed:
                base = float(series.iloc[0]) if float(series.iloc[0]) != 0 else None
                if not base:
                    continue
                y = (series / base) * 100.0
                hover_y = series
                hover_extra = "Price: $%{customdata:.2f}"
                y_title = "Index (base=100)"
            else:
                y = series
                hover_y = series
                hover_extra = "Price: $%{y:.2f}"
                y_title = "Price (USD)"

            color = (COMPANY_COLORS.get(company) or COMPANY_COLORS.get(company.strip()) or ("#64748b", ""))[0]
            fig.add_trace(
                go.Scatter(
                    x=series.index,
                    y=y,
                    mode="lines",
                    name=company,
                    line=dict(color=color, width=2.6),
                    customdata=hover_y,
                    hovertemplate="%{x|%b %d, %Y}<br><b>%{fullData.name}</b><br>"
                    + hover_extra
                    + "<extra></extra>",
                )
            )

        fig.update_layout(
            height=560,
            hovermode="x unified",
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color="#e6edf3")),
            font=dict(
                family="system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
                color="#e6edf3",
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_xaxes(showgrid=False, zeroline=False, showline=False, tickfont=dict(color="#8b949e"))
        fig.update_yaxes(
            title=y_title,
            showgrid=True,
            gridcolor="rgba(48,54,61,0.4)",
            zeroline=False,
            showline=False,
            tickfont=dict(color="#8b949e"),
            title_font=dict(color="#8b949e"),
        )
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)

# Create tabs for different views (only Company Details for now)
tab1, = st.tabs(["Company Details"])

# Add hover effect CSS for company logos
st.markdown("""
<style>
    .company-logo {
        width: 50px;
        height: 50px;
        object-fit: contain;
        transition: all 0.3s ease;
    }
    .company-logo:hover {
        transform: scale(1.2);
        filter: drop-shadow(0 0 5px rgba(0,0,0,0.3));
        cursor: pointer;
    }
    .company-card {
        border: 1px solid rgba(48,54,61,0.6);
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        background-color: rgba(22,27,34,0.85);
        box-shadow: 0 2px 8px rgba(0,0,0,0.25);
        transition: all 0.3s ease;
        cursor: pointer;
    }
    .company-card-content {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
    }
    .company-card-left {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .company-card-details {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
    }
    .company-card-name {
        font-weight: 700;
        font-size: 16px;
        color: #e6edf3;
    }
    .company-card-price {
        font-size: 20px;
        font-weight: 600;
        color: #e6edf3;
    }
    .company-card-change {
        font-size: 0.9rem;
    }
    .company-sparkline {
        display: flex;
        align-items: center;
    }
    .stock-sparkline {
        width: 120px;
        height: 40px;
    }
    .company-card:hover {
        box-shadow: 0 5px 20px rgba(0,0,0,0.4);
        transform: translateY(-2px);
        border-color: rgba(88,100,120,0.7);
    }
    .indicator-card {
        border-color: rgba(37,99,235,0.35);
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.12);
    }
    /* Hide Streamlit element toolbar overlay that creates dark bar on hover */
    [data-testid="stElementToolbar"],
    [data-testid="stElementToolbarBorderless"] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }
    /* Blue button styling — CSS fallback alongside JS inline styles.
       .stApp prefix raises specificity above Streamlit emotion classes.
       -webkit-text-fill-color needed because emotion CSS overrides color. */
    .stApp div[data-testid="stButton"] > button,
    .stApp [data-testid="stBaseButton-secondary"],
    .stApp [data-testid="stBaseButton-primary"] {
        background: #1e40af !important;
        background-color: #1e40af !important;
        background-image: none !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: 1px solid #1e3a8a !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 8px 18px !important;
        box-shadow: 0 2px 6px rgba(30,64,175,0.18) !important;
        cursor: pointer !important;
    }
    .stApp div[data-testid="stButton"] > button:hover,
    .stApp [data-testid="stBaseButton-secondary"]:hover,
    .stApp [data-testid="stBaseButton-primary"]:hover {
        background: #2563eb !important;
        background-color: #2563eb !important;
        background-image: none !important;
    }
    .stApp div[data-testid="stButton"] > button p,
    .stApp div[data-testid="stButton"] > button span,
    .stApp [data-testid="stBaseButton-secondary"] p,
    .stApp [data-testid="stBaseButton-secondary"] span {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    .price-up {
        color: #16A34A;
    }
    .price-down {
        color: #EF4444;
    }
    .stock-metric-card {
        background: rgba(22,27,34,0.85);
        border-radius: 10px;
        border: 1px solid rgba(48,54,61,0.6);
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
        padding: 12px 14px;
        min-height: 76px;
    }
    .stock-metrics-section {
        margin-bottom: 1.4rem;
    }
    .stock-metric-label {
        font-size: 0.72rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8b949e;
    }
    .stock-metric-value {
        font-size: 1.1rem;
        font-weight: 700;
        color: #e6edf3;
        margin-top: 0.35rem;
    }
</style>
""", unsafe_allow_html=True)

#############################
# TAB 1: COMPANY DETAILS
#############################
with tab1:
    stock_processor = st.session_state.stock_processor
    # Get available companies (financial universe + live stock feed additions)
    base_companies = _data_processor.get_companies()
    live_companies = (
        stock_processor.get_companies()
        if hasattr(stock_processor, "get_companies")
        else []
    )
    companies_main, companies_indicators = _split_company_groups(
        list(base_companies or []) + list(live_companies or [])
    )
    company_logos = load_company_logos()
    if _is_excluded_stock(st.session_state.get("selected_company", "")):
        del st.session_state.selected_company

    # Filter out companies with no stock data — use fast set lookup, not per-company API call
    try:
        _known = set(stock_processor.get_companies()) if hasattr(stock_processor, "get_companies") else set()
    except Exception:
        _known = set()
    _known_lower = {c.lower() for c in _known}

    def _has_stock_data(name):
        return name in _known or name.lower() in _known_lower

    companies_main = [c for c in companies_main if _has_stock_data(c)]
    companies_indicators = [c for c in companies_indicators if _has_stock_data(c)]

    # Company selector
    if 'selected_company' not in st.session_state:
        # Show all companies in a grid layout
        st.subheader("Select a Company to View Details")

        # Default timeframe for overview cards
        timeframe = "3M"

        # Single continuous grid — companies + indicators packed left-to-right.
        # Indicator cards keep their visual distinction via .indicator-card CSS.
        all_display = companies_main + companies_indicators
        _render_company_grid(
            all_display,
            company_logos,
            stock_processor,
            timeframe,
            button_prefix="company",
            center_last_single=False,
        )
        
        # Add JavaScript for handling card clicks
        st.markdown("""
        <script>
        function handleCompanyClick(company) {
            // Find and click the corresponding button
            const buttons = document.querySelectorAll('button');
            for (const button of buttons) {
                if (button.innerText.trim() === `View ${company}`) {
                    button.click();
                    break;
                }
            }
        }
        </script>
        """, unsafe_allow_html=True)
    else:
        # Display detailed view for selected company
        selected_company = st.session_state.selected_company
        timeframe = st.session_state.get('selected_timeframe', '1M')
        
        # Get stock data for the company with expanded details
        stock_data = stock_processor.get_company_data(selected_company, timeframe, expanded=True)
        
        # Display stock data
        if stock_data:
            # Extract data components
            quote = stock_data['quote']
            history = stock_data['history']

            fundamentals_df = load_stock_fundamentals(stock_processor.data_path)
            fundamentals_company_df = (
                stock_processor._filter_company(fundamentals_df, selected_company)
                if fundamentals_df is not None and not fundamentals_df.empty
                else pd.DataFrame()
            )
            if not fundamentals_company_df.empty:
                fundamentals_company_df = fundamentals_company_df.sort_values("date")
                fundamentals_company_df = stock_processor._apply_timeframe(
                    fundamentals_company_df, timeframe
                )

            col1, col2 = st.columns([1, 2.4])

            # Stock price and change
            with col1:
                logo_b64 = company_logos.get(selected_company, "")
                if logo_b64:
                    st.markdown(
                        f"""
                        <div style="display:flex; align-items:center; gap: 0.75rem; margin-bottom: 0.35rem;">
                            <img src="data:image/png;base64,{logo_b64}" alt="{selected_company} logo"
                                 style="height: 54px; width: 54px; object-fit: contain;">
                            <div style="font-size: 1.05rem; font-weight: 600; color: #e6edf3;">{selected_company}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.subheader(f"{selected_company}")

                price = quote.get('price', 0)
                change = quote.get('change', 0)
                change_percent = quote.get('change_percent', 0)

                change_color = "#16A34A" if change >= 0 else "#EF4444"
                change_prefix = "+" if change >= 0 else "−"

                st.markdown(f"<h3 style='margin-bottom: 0;'>${price:.2f}</h3>", unsafe_allow_html=True)
                st.markdown(
                    f"<span style='color: {change_color}; font-size: 1.1em; font-weight: 600;'>"
                    f"{change_prefix}${abs(change):.2f} ({abs(change_percent):.2f}%)</span>",
                    unsafe_allow_html=True,
                )

                st.markdown(f"**Symbol**: {quote.get('symbol', 'N/A')}")
                st.markdown(f"**Volume**: {format(quote.get('volume', 0), ',')}")
                st.caption(f"Source: {stock_data.get('source', 'Unknown').capitalize()}")

                new_timeframe = st.selectbox(
                    "Change Timeframe",
                    ["1M", "3M", "6M", "1Y", "2Y", "5Y", "MAX"],
                    index=["1M", "3M", "6M", "1Y", "2Y", "5Y", "MAX"].index(timeframe),
                )

                show_volume = st.checkbox(
                    "Show volume",
                    value=False,
                    key=f"show_volume_{selected_company}",
                )

                if new_timeframe != timeframe:
                    st.session_state.selected_timeframe = new_timeframe
                    st.rerun()

            # Stock price history chart
            with col2:
                if not history.empty:
                    fig = go.Figure()

                    fig.add_trace(
                        go.Scatter(
                            x=history.index,
                            y=history['Close'],
                            mode='lines',
                            name='Price',
                            line=dict(color='#0073ff', width=3),
                            hovertemplate='%{x|%b %d, %Y}<br>$%{y:.2f}<extra></extra>',
                        )
                    )

                    if show_volume:
                        fig.add_trace(
                            go.Bar(
                                x=history.index,
                                y=history['Volume'],
                                name='Volume',
                                marker=dict(color='rgba(22, 163, 74, 0.35)'),
                                hovertemplate='%{x|%b %d, %Y}<br>Vol: %{y:,}<extra></extra>',
                                yaxis='y2',
                            )
                        )

                    fig.update_layout(
                        height=420,
                        title=None,
                        hovermode="x unified",
                        legend=dict(orientation="h", y=1.02, font=dict(color="#e6edf3")),
                        margin=dict(l=0, r=10, t=40, b=0),
                        font=dict(
                            family="system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
                            color="#e6edf3",
                        ),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        yaxis=dict(
                            title="Price ($)",
                            tickprefix="$",
                            showgrid=True,
                            gridcolor="rgba(48,54,61,0.4)",
                            zeroline=False,
                            showline=False,
                            tickfont=dict(color="#8b949e"),
                        ),
                        yaxis2=(
                            dict(
                                title="Volume",
                                overlaying="y",
                                side="right",
                                showgrid=False,
                                zeroline=False,
                                showline=False,
                            )
                            if show_volume
                            else None
                        ),
                        xaxis=dict(
                            showgrid=False,
                            zeroline=False,
                            showline=False,
                            tickfont=dict(color="#8b949e"),
                            rangebreaks=[dict(bounds=["sat", "mon"])],
                        ),
                    )
                    fig.update_xaxes(showgrid=False, zeroline=False, showline=False, tickfont=dict(color="#8b949e"))
                    fig.update_yaxes(showgrid=True, gridcolor="rgba(48,54,61,0.4)", zeroline=False, showline=False, tickfont=dict(color="#8b949e"))
                    
                    # Add chart zoom effect at the top of the file if not already added
                    if not hasattr(st.session_state, 'chart_css_added'):
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
                        st.session_state.chart_css_added = True
                    
                    # Show plot with zoom effect
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True, config=plotly_config)
                    st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown("<div class='stock-metrics-section'>", unsafe_allow_html=True)
                    st.markdown("#### Key Metrics")
                    period_end = history.index.max()
                    start_price = history["Close"].iloc[0]
                    end_price = history["Close"].iloc[-1]
                    period_return = (
                        (end_price - start_price) / start_price * 100 if start_price else None
                    )
                    period_high = history["Close"].max()
                    period_low = history["Close"].min()
                    avg_volume = (
                        history["Volume"].mean() if "Volume" in history.columns else None
                    )

                    market_cap = (
                        _get_last_nonzero(fundamentals_company_df["market_cap"])
                        if "market_cap" in fundamentals_company_df
                        else None
                    )
                    shares_outstanding = (
                        _get_last_nonzero(fundamentals_company_df["outstanding_shares"])
                        if "outstanding_shares" in fundamentals_company_df
                        else None
                    )

                    available_years = _data_processor.get_available_years(selected_company)
                    metric_year = _latest_available_year(available_years, period_end)
                    metrics = (
                        _data_processor.get_metrics(selected_company, metric_year)
                        if metric_year
                        else None
                    )

                    market_cap_value = (
                        market_cap if market_cap and market_cap > 0 else None
                    )
                    if market_cap_value is None and metrics:
                        metric_market_cap = metrics.get("market_cap")
                        market_cap_value = metric_market_cap if metric_market_cap else None

                    pe_ratio = None
                    ps_ratio = None
                    net_assets_to_debt = None
                    if metrics:
                        net_income = metrics.get("net_income")
                        revenue = metrics.get("revenue")
                        debt = metrics.get("debt")
                        total_assets = metrics.get("total_assets")
                        if market_cap_value and net_income and net_income > 0:
                            pe_ratio = market_cap_value / net_income
                        if market_cap_value and revenue and revenue > 0:
                            ps_ratio = market_cap_value / revenue
                        if debt and debt > 0 and total_assets:
                            net_assets = total_assets - debt
                            if net_assets is not None:
                                net_assets_to_debt = net_assets / debt

                    metric_cards = [
                        {
                            "label": f"Period Return ({timeframe})",
                            "value": _format_percent(period_return),
                        },
                        {
                            "label": f"Range ({timeframe})",
                            "value": f"{_format_currency(period_low)} - {_format_currency(period_high)}",
                        },
                        {
                            "label": f"Avg Volume ({timeframe})",
                            "value": _format_volume(avg_volume),
                        },
                        {
                            "label": "Market Cap",
                            "value": _format_money_millions(market_cap_value),
                        },
                        {
                            "label": "P/E",
                            "value": _format_ratio(pe_ratio),
                        },
                        {
                            "label": "P/S",
                            "value": _format_ratio(ps_ratio),
                        },
                        {
                            "label": "Net Assets / Debt",
                            "value": _format_ratio(net_assets_to_debt),
                        },
                        {
                            "label": "Shares Outstanding",
                            "value": _format_shares_millions(shares_outstanding),
                        },
                    ]

                    for start in range(0, len(metric_cards), 4):
                        cols = st.columns(4)
                        for col, metric in zip(cols, metric_cards[start:start + 4]):
                            with col:
                                st.markdown(
                                    "<div class='stock-metric-card'>"
                                    f"<div class='stock-metric-label'>{metric['label']}</div>"
                                    f"<div class='stock-metric-value'>{metric['value']}</div>"
                                    "</div>",
                                    unsafe_allow_html=True,
                                )
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.error("No historical data available for this timeframe.")
            
            # Display additional info about the chart
            with st.expander("📊 About the Chart"):
                st.markdown(f"""
                This chart shows the stock price history for {st.session_state.selected_company} over the selected timeframe:
                - The blue line represents the closing price
                - The gray bars show daily trading volume
                - Hover over the chart to see detailed values
                """)
            
            # Clear selection button
            if st.button("← Back to Overview"):
                del st.session_state.selected_company
                st.rerun()
        else:
            st.error("Unable to fetch detailed data. This might be due to missing rows in the Excel stock sheet.")
            
    st.divider()
    render_all_company_stocks_section()

    st.divider()
    with st.expander("ℹ️ About Stock Data"):
        st.markdown("""
        This section shows detailed stock information for major technology and media companies.

        **Key Metrics**:
        - **Current Price**: Latest stock price in USD
        - **Change**: Last 3 months price movement
        - **Volume**: Trading volume

        **Data Sources**:
        - Historical + live rows from workbook tabs: `Stocks & Crypto`, `Daily`, `Minute`
        - Latest price cards/hero values use the merged feed automatically
        - Market Terminal: live data via yfinance, CoinGecko, CoinMarketCap

        Click on any company card to see detailed performance.
        """)

    # ── Market Terminal Panel ──────────────────────────────────────────────
    st.divider()
    st.header("Market Terminal")
    st.caption("Live prices across indices, commodities, forex, crypto, sectors & ad-tech")

    try:
        from utils.market_terminal import (
            fetch_bulk_market_data,
            fetch_fear_greed,
            fetch_crypto_top,
            build_terminal_html,
        )

        with st.spinner("Loading live market data..."):
            _mt_data = fetch_bulk_market_data()
            _mt_fg = fetch_fear_greed()
            _mt_crypto = fetch_crypto_top(limit=30)

        if _mt_data:
            _mt_html = build_terminal_html(
                market_data=_mt_data,
                fear_greed=_mt_fg,
                crypto_top=_mt_crypto,
            )
            # Estimate height: base 200 + rows
            _n_rows = len(_mt_data) + (30 if _mt_crypto else 0)
            _mt_height = max(600, 200 + _n_rows * 22 + (80 if _mt_fg else 0))
            st.components.v1.html(_mt_html, height=_mt_height, scrolling=True)
        else:
            st.info("Market terminal data unavailable — yfinance may be blocked by your network.")
    except ImportError:
        st.info("Market terminal requires `yfinance`. Add it to requirements.txt.")
    except Exception as _mt_exc:
        st.warning(f"Market terminal error: {_mt_exc}")

#############################
# Sidebar Components
#############################

# Update AI context
dashboard_state = {
    'page': 'Stocks',
    'selected_company': st.session_state.get('selected_company', None),
}

# ── Button style override — MutationObserver applies INLINE styles ──
# CSS specificity wars with Streamlit are unwinnable. Inline styles always
# beat any stylesheet rule, so we apply them directly via JS on every DOM
# mutation. A throttle prevents performance issues.
import streamlit.components.v1 as _comp
_comp.html("""
<script>
(function() {
  var doc = window.parent ? window.parent.document : document;
  var BLUE = '#1e40af';
  var BLUE_HOVER = '#2563eb';
  var _timer = null;

  function styleAllButtons() {
    var btns = doc.querySelectorAll(
      '[data-testid="stButton"] button, ' +
      '[data-testid="stBaseButton-secondary"], ' +
      '[data-testid="stBaseButton-primary"]'
    );
    btns.forEach(function(btn) {
      btn.style.setProperty('background', BLUE, 'important');
      btn.style.setProperty('background-color', BLUE, 'important');
      btn.style.setProperty('background-image', 'none', 'important');
      btn.style.setProperty('color', '#ffffff', 'important');
      btn.style.setProperty('border', '1px solid #1e3a8a', 'important');
      btn.style.setProperty('border-radius', '8px', 'important');
      btn.style.setProperty('font-weight', '600', 'important');
      btn.style.setProperty('font-size', '0.85rem', 'important');
      btn.style.setProperty('padding', '8px 18px', 'important');
      btn.style.setProperty('box-shadow', '0 2px 6px rgba(30,64,175,0.2)', 'important');
      btn.style.setProperty('cursor', 'pointer', 'important');
      // Force white text on all children
      var kids = btn.querySelectorAll('p, span, div');
      kids.forEach(function(k) { k.style.setProperty('color', '#ffffff', 'important'); });
      // Add hover listeners (only once)
      if (!btn._stocksHover) {
        btn._stocksHover = true;
        btn.addEventListener('mouseenter', function() {
          this.style.setProperty('background', BLUE_HOVER, 'important');
          this.style.setProperty('background-color', BLUE_HOVER, 'important');
          this.style.setProperty('box-shadow', '0 4px 12px rgba(37,99,235,0.35)', 'important');
          this.style.setProperty('transform', 'translateY(-1px)', 'important');
        });
        btn.addEventListener('mouseleave', function() {
          this.style.setProperty('background', BLUE, 'important');
          this.style.setProperty('background-color', BLUE, 'important');
          this.style.setProperty('box-shadow', '0 2px 6px rgba(30,64,175,0.2)', 'important');
          this.style.setProperty('transform', 'none', 'important');
        });
      }
    });
  }

  // Initial pass
  styleAllButtons();
  // Re-apply on DOM changes (throttled to 150ms)
  var obs = new MutationObserver(function() {
    if (_timer) clearTimeout(_timer);
    _timer = setTimeout(styleAllButtons, 150);
  });
  obs.observe(doc.body, { childList: true, subtree: true });
  // Safety: also re-apply after short delay for Streamlit hydration
  setTimeout(styleAllButtons, 300);
  setTimeout(styleAllButtons, 800);
  setTimeout(styleAllButtons, 1500);
})();
</script>
""", height=0)
