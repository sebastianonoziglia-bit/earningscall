import streamlit as st

# Page config must be the first Streamlit command
st.set_page_config(page_title="Editorial", page_icon="📝", layout="wide")

from utils.global_fonts import apply_global_fonts
apply_global_fonts()


from utils.auth import check_password
import plotly.graph_objects as go
from subscriber_data_processor import SubscriberDataProcessor
import pandas as pd
from datetime import datetime, timedelta
from utils.styles import get_page_style, get_animation_style
import base64
from PIL import Image
import os
from io import BytesIO
from utils.page_transition import apply_page_transition_fix
from pathlib import Path

# Apply fix for page transitions to prevent background bleed-through
apply_page_transition_fix()

# Apply shared styles
st.markdown(get_page_style(), unsafe_allow_html=True)
st.markdown(get_animation_style(), unsafe_allow_html=True)

# Add header with language selector
from utils.header import render_header
from utils.language import get_text
render_header()

# Add SQL Assistant in the sidebar
from utils.sql_assistant_sidebar import render_sql_assistant_sidebar
render_sql_assistant_sidebar()

# Check if user is logged in, redirect to Welcome page if not
# Always authenticated - no password check needed
from utils.time_utils import render_floating_clock
render_floating_clock()

st.title("Editorial Insights")
st.write("Quarterly subscriber metrics analysis.")

def _metric_label_for_service(service: str) -> str:
    s = (service or "").lower()
    if any(k in s for k in ["whatsapp", "instagram", "facebook"]):
        return "Users"
    if "spotify" in s:
        if any(k in s for k in ["ad supported", "ad-supported", "adsupported", "free", "mau", "monthly active", "total", "totale"]):
            return "Ad Supported"
        if any(k in s for k in ["premium", "paid", "paying"]):
            return "Premium"
    return "Subscribers"

# Initialize subscriber data processor
if 'subscriber_processor' not in st.session_state:
    st.session_state['subscriber_processor'] = SubscriberDataProcessor()

# Get available streaming services and sort them alphabetically
services = sorted(st.session_state['subscriber_processor'].get_service_names())

# Load company logos function (same as in Welcome.py)
def load_company_logos():
    """Load and cache company logos with base64 encoding"""
    def _first_existing(*candidates: str):
        for p in candidates:
            if p and Path(p).exists():
                return p
        return None

    logo_paths = {
        'Disney+': 'attached_assets/icons8-logo-disney-240.png',
        'Netflix': 'attached_assets/9.png',
        'Paramount+': 'attached_assets/Paramount.png',
        'Warner Bros Discovery': 'attached_assets/adadad.png',
        'Warner Bros. Discovery': 'attached_assets/adadad.png',
        'WBD': 'attached_assets/adadad.png',
        'Spotify': 'attached_assets/11.png',
        'Alphabet': 'attached_assets/8.png',  # Reverted to original working logo
        'Apple': 'attached_assets/10.png',
        'Microsoft': 'attached_assets/msft.png',
        'Meta Platforms': 'attached_assets/12.png',
        # Meta-owned apps: prefer dedicated logos if present, otherwise fall back to Meta.
        'WhatsApp': _first_existing('attached_assets/Whatsapp.png', 'attached_assets/WhatsApp.png', 'attached_assets/12.png'),
        'Instagram': _first_existing('attached_assets/Instagram.png', 'attached_assets/12.png'),
        'Facebook': _first_existing('attached_assets/Facebook.png', 'attached_assets/12.png'),
        'Amazon': 'attached_assets/Amazon_icon.png',
        'Roku': 'attached_assets/rokudef.png',
        'Comcast': 'attached_assets/6.png'
    }
    
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
            else:
                print(f"Logo file not found: {path}")
        except Exception as e:
            print(f"Error loading logo for {company}: {e}")
    
    return logos

# Load logos with base64 encoding
service_logos = load_company_logos()

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
</style>
""", unsafe_allow_html=True)

def parse_quarter_to_date(quarter_str):
    """Convert quarter string to datetime object"""
    try:
        if quarter_str.startswith('Q'):
            # Format: "Q1 2020"
            q = int(quarter_str[1])
            year = int(quarter_str.split()[1])
        elif 'Q' in quarter_str:
            # Format: "20Q1"
            parts = quarter_str.split('Q')
            year = int(f"20{parts[0]}")
            q = int(parts[1])
        else:
            # Format: "1 2020"
            parts = quarter_str.split()
            q = int(parts[0])
            year = int(parts[1])

        month = (q - 1) * 3 + 1
        return pd.to_datetime(f"{year}-{month:02d}-01")
    except Exception as e:
        print(f"Failed to parse quarter '{quarter_str}': {str(e)}")
        return None

# Calculate current date and 5 years ago date for filtering
current_date = datetime.now()
five_years_ago = current_date - timedelta(days=5*365)

# Add tabs for single service view and comparison view
processor = st.session_state['subscriber_processor']
companies = processor.get_company_names() if hasattr(processor, "get_company_names") else []
selected_services = []

# Add chart zoom effect once
if not hasattr(st.session_state, 'editorial_chart_css_added'):
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
    st.session_state.editorial_chart_css_added = True

# Add tabs for single service view and comparison view
tab1, tab2 = st.tabs(["Individual Service Analysis", "Service Comparison"])

with tab1:
    filter_cols = st.columns(3)

    with filter_cols[0]:
        individual_company_filter = st.selectbox(
            "Company filter",
            ["All"] + companies,
            key="editorial_individual_company_filter",
        )

    individual_service_options = (
        processor.get_service_names(None if individual_company_filter == "All" else individual_company_filter)
        if hasattr(processor, "get_service_names")
        else services
    )

    with filter_cols[1]:
        selected_service = st.selectbox(
            "Service",
            individual_service_options,
            key="editorial_individual_service_filter",
        ) if individual_service_options else None

    service_series_keys = (
        processor.get_series_columns([selected_service]) if selected_service and hasattr(processor, "get_series_columns") else ["subscribers"]
    )
    default_series_key = "subscribers" if "subscribers" in service_series_keys else (service_series_keys[0] if service_series_keys else None)
    default_series_index = service_series_keys.index(default_series_key) if default_series_key in service_series_keys else 0

    with filter_cols[2]:
        selected_series_key = st.selectbox(
            "Series / Split",
            service_series_keys,
            index=default_series_index,
            format_func=lambda key: processor.get_series_label(key) if hasattr(processor, "get_series_label") else str(key),
            key="editorial_individual_series_filter",
        ) if service_series_keys else None

    control_cols = st.columns(2)
    with control_cols[0]:
        individual_chart_type = st.radio(
            "Chart Type",
            options=["Line Chart", "Bar Chart"],
            horizontal=True,
            key="editorial_individual_chart_type",
        )

    service_data = (
        processor.get_service_data(selected_service, series_key=selected_series_key)
        if selected_service else {"data": pd.DataFrame(), "column_name": "Subscribers", "unit": "millions"}
    )
    df_individual = service_data.get("data", pd.DataFrame()).copy()
    if not df_individual.empty:
        df_individual["date"] = df_individual["Quarter"].apply(parse_quarter_to_date)
        df_individual = df_individual.dropna(subset=["date"])
        df_individual = df_individual.sort_values("date")

    with control_cols[1]:
        if not df_individual.empty:
            years = sorted(df_individual["date"].dt.year.unique().tolist())
            min_year = int(min(years))
            max_year = int(max(years))
            default_start = max(min_year, max_year - 4)
            individual_year_range = st.slider(
                "Select Year Range",
                min_value=min_year,
                max_value=max_year,
                value=(default_start, max_year),
                step=1,
                key="editorial_individual_year_range",
            )
            df_individual = df_individual[
                df_individual["date"].dt.year.between(individual_year_range[0], individual_year_range[1])
            ]
        else:
            individual_year_range = None

    if selected_service and not df_individual.empty:
        logo_col, title_col = st.columns([0.08, 0.92])
        with logo_col:
            logo_key_candidates = [
                selected_service,
                processor.df_subscribers[processor.df_subscribers["service"] == selected_service]["company"].iloc[0]
                if "company" in processor.df_subscribers.columns and (processor.df_subscribers["service"] == selected_service).any()
                else "",
            ]
            logo_b64 = None
            for candidate in logo_key_candidates:
                if candidate in service_logos:
                    logo_b64 = service_logos[candidate]
                    break
            if logo_b64:
                st.markdown(
                    f"<img src='data:image/png;base64,{logo_b64}' class='company-logo'>",
                    unsafe_allow_html=True,
                )
            else:
                st.write(selected_service[0])
        with title_col:
            series_label = (
                processor.get_series_label(selected_series_key)
                if hasattr(processor, "get_series_label") and selected_series_key
                else "Subscribers"
            )
            st.subheader(f"{selected_service} — {series_label}")

        column_name = service_data.get("column_name", "Subscribers")
        if column_name in df_individual.columns:
            latest_value = df_individual.iloc[-1][column_name]
            latest_quarter = df_individual.iloc[-1]["Quarter"]
            yoy_growth = None
            if len(df_individual) >= 5:
                previous_value = df_individual.iloc[-5][column_name]
                if previous_value not in (None, 0):
                    yoy_growth = ((latest_value - previous_value) / previous_value) * 100

            metric_col, chart_col = st.columns([0.22, 0.78])
            with metric_col:
                label_key = selected_series_key or "subscribers"
                if label_key == "subscribers":
                    metric_label = _metric_label_for_service(selected_service)
                else:
                    metric_label = processor.get_series_label(label_key)
                st.metric(
                    label=f"{metric_label} ({service_data.get('unit', 'millions')})",
                    value=f"{latest_value:,.1f}",
                    delta=f"{yoy_growth:+.1f}%" if yoy_growth is not None else None,
                    delta_color="normal",
                )
                st.caption(f"Quarter: {latest_quarter}")

            with chart_col:
                fig = go.Figure()
                if individual_chart_type == "Line Chart":
                    fig.add_trace(
                        go.Scatter(
                            x=df_individual["Quarter"],
                            y=df_individual[column_name],
                            mode="lines+markers",
                            name=selected_service,
                            hovertemplate=(
                                f"<b>{selected_service}</b><br>"
                                "Quarter: %{x}<br>"
                                f"Value: %{{y:.1f}} {service_data.get('unit', 'millions')}<br>"
                                "<extra></extra>"
                            ),
                        )
                    )
                else:
                    fig.add_trace(
                        go.Bar(
                            x=df_individual["Quarter"],
                            y=df_individual[column_name],
                            name=selected_service,
                            hovertemplate=(
                                f"<b>{selected_service}</b><br>"
                                "Quarter: %{x}<br>"
                                f"Value: %{{y:.1f}} {service_data.get('unit', 'millions')}<br>"
                                "<extra></extra>"
                            ),
                        )
                    )

                fig.update_layout(
                    margin=dict(l=20, r=20, t=25, b=50),
                    height=280,
                    showlegend=False,
                    template='mfe_blue',
                    xaxis_title=None,
                    yaxis_title=None,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    xaxis=dict(
                        type='category',
                        categoryorder='array',
                        categoryarray=df_individual["Quarter"].tolist(),
                        tickangle=45,
                        showgrid=False,
                    ),
                    yaxis=dict(showgrid=True, gridcolor='#f0f0f0'),
                )

                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.plotly_chart(fig, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No data available for the selected filters.")

with tab2:
    comparison_filter_cols = st.columns(3)

    with comparison_filter_cols[0]:
        comparison_company_filter = st.selectbox(
            "Company filter",
            ["All"] + companies,
            key="editorial_comparison_company_filter",
        )

    comparison_service_pool = (
        processor.get_service_names(None if comparison_company_filter == "All" else comparison_company_filter)
        if hasattr(processor, "get_service_names")
        else services
    )
    default_comparison_services = comparison_service_pool[:2] if len(comparison_service_pool) >= 2 else comparison_service_pool

    with comparison_filter_cols[1]:
        selected_services = st.multiselect(
            "Services",
            options=comparison_service_pool,
            default=default_comparison_services,
            key="editorial_comparison_services_filter",
            help="Select services to compare.",
        )

    comparison_series_options = (
        processor.get_series_columns(selected_services if selected_services else comparison_service_pool)
        if hasattr(processor, "get_series_columns")
        else ["subscribers"]
    )
    comparison_default_series = (
        "subscribers"
        if "subscribers" in comparison_series_options
        else (comparison_series_options[0] if comparison_series_options else None)
    )
    comparison_default_series_idx = (
        comparison_series_options.index(comparison_default_series)
        if comparison_default_series in comparison_series_options
        else 0
    )

    with comparison_filter_cols[2]:
        comparison_series_key = st.selectbox(
            "Series / Split",
            comparison_series_options,
            index=comparison_default_series_idx,
            format_func=lambda key: processor.get_series_label(key) if hasattr(processor, "get_series_label") else str(key),
            key="editorial_comparison_series_filter",
        ) if comparison_series_options else None

    comparison_control_cols = st.columns(2)
    with comparison_control_cols[0]:
        comparison_chart_type = st.radio(
            "Chart Type",
            options=["Line", "Bar"],
            horizontal=True,
            key="editorial_comparison_chart_type",
        )

    comparison_long = (
        processor.get_long_series_data(services=selected_services, series_keys=[comparison_series_key])
        if selected_services and comparison_series_key and hasattr(processor, "get_long_series_data")
        else pd.DataFrame()
    )
    if not comparison_long.empty:
        comparison_long["date"] = comparison_long["Quarter"].apply(parse_quarter_to_date)
        comparison_long = comparison_long.dropna(subset=["date"])
        comparison_long = comparison_long.sort_values(["service", "date"])

    with comparison_control_cols[1]:
        if not comparison_long.empty:
            years = sorted(comparison_long["date"].dt.year.unique().tolist())
            min_year = int(min(years))
            max_year = int(max(years))
            default_start = max(min_year, max_year - 4)
            comparison_year_range = st.slider(
                "Select Year Range",
                min_value=min_year,
                max_value=max_year,
                value=(default_start, max_year),
                step=1,
                key="editorial_comparison_year_range",
            )
            comparison_long = comparison_long[
                comparison_long["date"].dt.year.between(comparison_year_range[0], comparison_year_range[1])
            ]
        else:
            comparison_year_range = None

    if selected_services and not comparison_long.empty:
        available_service_set = set(comparison_long["service"].unique().tolist())
        missing_services = [s for s in selected_services if s not in available_service_set]
        if missing_services:
            st.warning(
                "No data for selected split in: " + ", ".join(missing_services)
            )

        quarter_order = (
            comparison_long[["Quarter", "date"]]
            .drop_duplicates()
            .sort_values("date")["Quarter"]
            .tolist()
        )

        fig = go.Figure()
        for service_name in selected_services:
            df_service = comparison_long[comparison_long["service"] == service_name]
            if df_service.empty:
                continue
            df_service = df_service.sort_values("date")
            hover_template = (
                f"<b>{service_name}</b><br>"
                "Quarter: %{x}<br>"
                "Value: %{y:.1f}<br>"
                "<extra></extra>"
            )
            if comparison_chart_type == "Line":
                fig.add_trace(
                    go.Scatter(
                        x=df_service["Quarter"],
                        y=df_service["value"],
                        mode="lines+markers",
                        connectgaps=False,
                        name=service_name,
                        hovertemplate=hover_template,
                    )
                )
            else:
                fig.add_trace(
                    go.Bar(
                        x=df_service["Quarter"],
                        y=df_service["value"],
                        name=service_name,
                        hovertemplate=hover_template,
                    )
                )

        series_title = (
            processor.get_series_label(comparison_series_key)
            if hasattr(processor, "get_series_label") and comparison_series_key
            else "Subscribers"
        )
        units = sorted(
            comparison_long["unit"].dropna().astype(str).str.strip().replace("", "millions").unique().tolist()
        )
        y_title = series_title if len(units) != 1 else f"{series_title} ({units[0]})"

        fig.update_layout(
            title=f"Service Comparison — {series_title}",
            xaxis_title="Quarter",
            yaxis_title=y_title,
            showlegend=True,
            height=500,
            template='mfe_blue',
            xaxis=dict(
                type='category',
                categoryorder='array',
                categoryarray=quarter_order,
                tickangle=45,
                showgrid=True,
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
            barmode='group' if comparison_chart_type == "Bar" else None,
        )

        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    elif selected_services:
        st.info("No data available for the selected filters.")
    else:
        st.info("Select services to compare.")

# Update AI context
dashboard_state = {
    'page': 'Editorial',
    'comparison_services': selected_services if 'selected_services' in locals() else []
}
if 'ai_chat' in st.session_state:
    ai_chat = st.session_state.get("ai_chat")
    if ai_chat is not None and hasattr(ai_chat, "update_context"):
        ai_chat.update_context(dashboard_state)
