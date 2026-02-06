import streamlit as st

# Page config must be the first Streamlit command
st.set_page_config(page_title="Stocks", page_icon="📈", layout="wide")

from utils.page_transition import apply_page_transition_fix

# Apply fix for page transitions to prevent background bleed-through
apply_page_transition_fix()

from utils.auth import check_password
import plotly.graph_objects as go
import pandas as pd
from stock_processor_fix import StockDataProcessor  # Use the fixed version
from data_processor import FinancialDataProcessor
from utils.helpers import format_number
from utils.ai_chat import render_chat_interface, initialize_chat
from datetime import datetime, timedelta
from PIL import Image
import base64
import os
from io import BytesIO
from utils.styles import get_page_style, get_animation_style

# Apply global styles at page load for better performance
st.markdown(get_page_style(), unsafe_allow_html=True)
st.markdown(get_animation_style(), unsafe_allow_html=True)

# Add header with language selector
from utils.header import render_header
from utils.language import get_text
render_header()

# Add SQL Assistant in the sidebar
from utils.sql_assistant_sidebar import render_sql_assistant_sidebar
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
        df = pd.read_excel(
            data_path,
            sheet_name="Stocks & Crypto",
            usecols=["date", "price", "vol.", "market cap.", "outstanding shares", "asset", "tag"],
        )
    except Exception:
        df = pd.read_excel(data_path, sheet_name="Stocks & Crypto")
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.rename(
        columns={
            "vol.": "volume",
            "vol": "volume",
            "market cap.": "market_cap",
            "market cap": "market_cap",
            "market_cap": "market_cap",
            "outstanding shares": "outstanding_shares",
            "shares outstanding": "outstanding_shares",
            "outstanding_shares": "outstanding_shares",
        }
    )
    if "date" not in df.columns:
        for alt in ("datetime", "timestamp"):
            if alt in df.columns:
                df = df.rename(columns={alt: "date"})
                break
    if "price" not in df.columns:
        for alt in ("close", "close price", "closing price", "adj close", "adj_close"):
            if alt in df.columns:
                df = df.rename(columns={alt: "price"})
                break
    if "asset" not in df.columns:
        for alt in ("name", "company", "symbol", "ticker"):
            if alt in df.columns:
                df = df.rename(columns={alt: "asset"})
                break
    if "tag" not in df.columns:
        df["tag"] = ""
    required = {"date", "price", "asset", "tag"}
    missing = required - set(df.columns)
    if missing:
        return pd.DataFrame()
    for optional in ("volume", "market_cap", "outstanding_shares"):
        if optional not in df.columns:
            df[optional] = None
    df = df[["date", "price", "volume", "market_cap", "outstanding_shares", "asset", "tag"]]
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

# Chat initialization for AI support
initialize_chat()

# Page title
st.title("📈 Stock Performance")

# Get data processor for metrics
_data_processor = st.session_state.data_processor

# Load company logos function (similar to Welcome.py)
def load_company_logos():
    """Load and cache company logos with base64 encoding"""
    logo_paths = {
        'Apple': 'attached_assets/apple.png',
        'Microsoft': 'attached_assets/msft.png',
        'Alphabet': 'attached_assets/Google__G__logo.svg.png',
        'Netflix': 'attached_assets/9.png',
        'Meta': 'attached_assets/12.png',
        'Meta Platforms': 'attached_assets/12.png',
        'Amazon': 'attached_assets/Amazon_icon.png',
        'Disney': 'attached_assets/icons8-logo-disney-240.png',
        'Roku': 'attached_assets/rokudef.png',
        'Spotify': 'attached_assets/11.png',
        'Comcast': 'attached_assets/6.png',
        'Paramount': 'attached_assets/Paramount.png',  # Updated to use the corporate logo
        'Paramount Global': 'attached_assets/Paramount.png',  # Using corporate logo for Paramount Global
        'Warner Bros Discovery': 'attached_assets/adadad.png',
        'Warner Bros. Discovery': 'attached_assets/adadad.png',
    }
    
    # Print all logo files in the directory for debugging
    print("Available logo files:", [f for f in os.listdir('attached_assets')])
    
    logos = {}
    
    for company, path in logo_paths.items():
        try:
            if os.path.exists(path):
                img = Image.open(path)
                img = img.convert('RGBA')
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                logos[company] = img_str
                print(f"Successfully loaded logo for {company}")
            else:
                print(f"Logo file not found: {path}")
        except Exception as e:
            print(f"Error loading logo for {company}: {e}")
    
    return logos


def render_all_company_stocks_section():
    st.header("All Company Stocks")

    stock_processor = st.session_state.stock_processor
    companies_all = (
        stock_processor.get_companies()
        if hasattr(stock_processor, "get_companies")
        else st.session_state["data_processor"].get_companies()
    )
    companies_all = [c for c in companies_all if isinstance(c, str) and c.strip()]
    companies_all = sorted(dict.fromkeys(companies_all), key=lambda s: s.lower())

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
            ["Indexed (base=100)", "Price (USD)", "Price (USD, log scale)"],
            index=0,
            key="all_stocks_view_mode",
        )
    with controls[2]:
        default_selection = st.session_state.get("all_stocks_companies")
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

    with st.spinner("Loading price histories..."):
        fig = go.Figure()
        added = 0
        for company in selected_companies:
            try:
                stock_data = stock_processor.get_company_data(company, multi_timeframe)
                history = stock_data.get("history") if isinstance(stock_data, dict) else None
                if history is None or getattr(history, "empty", True):
                    continue
                series = pd.to_numeric(history.get("Close"), errors="coerce").dropna()
                if series.empty:
                    continue

                if view_mode == "Indexed (base=100)":
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
                added += 1
            except Exception:
                continue

    if added == 0:
        st.info("No price history available for the selected companies/timeframe.")
        return

    yaxis_type = "log" if view_mode == "Price (USD, log scale)" else "linear"
    fig.update_layout(
        height=560,
        hovermode="x unified",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        font=dict(
            family="system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
            color="#0f172a",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False, zeroline=False, showline=False)
    fig.update_yaxes(
        title=y_title,
        type=yaxis_type,
        showgrid=False,
        zeroline=False,
        showline=False,
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
        border: 1px solid #f0f0f0;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        background-color: white;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
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
    }
    .company-card-price {
        font-size: 20px;
        font-weight: 600;
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
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    .price-up {
        color: green;
    }
    .price-down {
        color: red;
    }
    .stock-metric-card {
        background: #ffffff;
        border-radius: 10px;
        border: 1px solid #eef0f4;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
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
        color: #6b7280;
    }
    .stock-metric-value {
        font-size: 1.1rem;
        font-weight: 700;
        color: #111827;
        margin-top: 0.35rem;
    }
</style>
""", unsafe_allow_html=True)

#############################
# TAB 1: COMPANY DETAILS
#############################
with tab1:
    # Get available companies
    companies = _data_processor.get_companies()
    stock_processor = st.session_state.stock_processor
    company_logos = load_company_logos()
    
    # Company selector
    if 'selected_company' not in st.session_state:
        # Show all companies in a grid layout
        st.subheader("Select a Company to View Details")
        
        # Default timeframe for overview cards
        timeframe = "3M"
        
        # Create a grid of company cards
        cols = st.columns(3)
        
        for i, company in enumerate(companies):
            # Load stock data for each company
            with cols[i % 3]:
                try:
                    # Get stock data
                    stock_data = stock_processor.get_company_data(company, timeframe)
                    
                    if stock_data and 'quote' in stock_data:
                        quote = stock_data['quote']
                        history = stock_data.get('history')
                        price = quote.get('price', 0)
                        change = quote.get('change', 0)
                        change_percent = quote.get('change_percent', 0)
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
                            sparkline_svg = _build_sparkline_svg(
                                history["Close"], color=spark_color
                            )
                        sparkline_html = (
                            f"<div class='company-sparkline'>{sparkline_svg}</div>"
                            if sparkline_svg
                            else ""
                        )
                        
                        # Create clickable card
                        with st.container():
                            st.markdown(f"""
                            <div class="company-card" onclick="handleCompanyClick('{company}')">
                                <div class="company-card-content">
                                    <div class="company-card-left">
                                        <img src="data:image/png;base64,{company_logos.get(company, '')}" class="company-logo">
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
                            """, unsafe_allow_html=True)
                            
                            # Hidden button to handle the click
                            if st.button(f"View {company}", key=f"btn_{company}", help=f"View detailed data for {company}"):
                                st.session_state.selected_company = company
                                st.session_state.selected_timeframe = timeframe
                                st.rerun()
                except Exception as e:
                    st.error(f"Error loading data for {company}: {str(e)}")
        
        # Add JavaScript for handling card clicks
        st.markdown("""
        <script>
        function handleCompanyClick(company) {
            // Find and click the corresponding button
            const btnId = 'btn_' + company;
            const buttons = document.querySelectorAll('button');
            for (const button of buttons) {
                if (button.innerText.includes(company)) {
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
                            <div style="font-size: 1.05rem; font-weight: 600; color: #111827;">{selected_company}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.subheader(f"{selected_company}")

                price = quote.get('price', 0)
                change = quote.get('change', 0)
                change_percent = quote.get('change_percent', 0)

                change_color = "green" if change >= 0 else "red"
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
                        legend=dict(orientation="h", y=1.02),
                        margin=dict(l=0, r=10, t=40, b=0),
                        font=dict(
                            family="system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
                            color="#0f172a",
                        ),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        yaxis=dict(
                            title="Price ($)",
                            tickprefix="$",
                            showgrid=False,
                            zeroline=False,
                            showline=False,
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
                            rangebreaks=[dict(bounds=["sat", "mon"])],
                        ),
                    )
                    fig.update_xaxes(showgrid=False, zeroline=False, showline=False)
                    fig.update_yaxes(showgrid=False, zeroline=False, showline=False)
                    
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
        - Local Excel (`Earnings + stocks  copy.xlsx` → `Stocks & Crypto`)
        - Updated when the Excel file is refreshed

        Click on any company card to see detailed performance.
        """)

#############################
# Sidebar Components
#############################

# Update AI context
dashboard_state = {
    'page': 'Stocks',
    'selected_company': st.session_state.get('selected_company', None),
}
