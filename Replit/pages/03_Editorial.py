import streamlit as st

# Page config must be the first Streamlit command
st.set_page_config(page_title="Editorial", page_icon="📝", layout="wide")

from utils.auth import check_password
from utils.ai_chat import render_chat_interface, initialize_chat
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

# Initialize chat
initialize_chat()

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
tab1, tab2 = st.tabs(["Individual Service Analysis", "Service Comparison"])

with tab1:
    # Add selectors for subscriber type and chart type at the top
    col1, col2 = st.columns(2)
    
    with col1:
        subscriber_type = st.radio(
            "Select Metric",
            options=["Subscribers"],
            horizontal=True,
            key="individual_subscriber_type"
        )
    
    with col2:
        chart_type = st.radio(
            "Chart Type",
            options=["Line Chart", "Bar Chart"],
            horizontal=True,
            key="individual_chart_type",
            help="Select line chart to view trends over time or bar chart to compare values across quarters"
        )

    main_col1, main_col2 = st.columns([3, 1])

    with main_col1:
        # Display all services in alphabetical order
        for service in services:
            with st.container():
                # Header row with logo and name
                col1, col2 = st.columns([0.1, 0.9])

                with col1:
                    if service in service_logos:
                        try:
                            # Display logo with base64 encoding and hover effect
                            st.markdown(f"""
                                <img src='data:image/png;base64,{service_logos[service]}' class='company-logo'>
                            """, unsafe_allow_html=True)
                        except:
                            st.write(service[0])  # Display first letter as fallback
                    else:
                        st.write(service[0])  # Display first letter as fallback

                with col2:
                    st.subheader(service)

                # Get service data based on selected subscriber type
                metric_type = "subscribers"
                service_data = st.session_state['subscriber_processor'].get_service_data(service, metric_type=metric_type)

                if service_data and not service_data['data'].empty:
                    df = service_data['data'].copy()

                    # Convert quarters to datetime for filtering
                    df['date'] = df['Quarter'].apply(parse_quarter_to_date)
                    df = df.dropna(subset=['date'])

                    if not df.empty:
                        # Filter to last 5 years
                        df = df[df['date'] >= five_years_ago]
                        # Sort chronologically (ascending)
                        df = df.sort_values('date')

                        if not df.empty:
                            column_name = service_data['column_name']
                            # Verify the column exists
                            if column_name in df.columns:
                                latest_data = {
                                    'quarter': df.iloc[-1]['Quarter'],
                                    'subscribers': df.iloc[-1][column_name],
                                    'metric': column_name,
                                    'unit': service_data['unit']
                                }

                                # Calculate YoY growth
                                if len(df) >= 5:
                                    yoy_growth = ((df.iloc[-1][service_data['column_name']] - 
                                                df.iloc[-5][service_data['column_name']]) / 
                                                df.iloc[-5][service_data['column_name']]) * 100
                                else:
                                    yoy_growth = None

                                metric_col1, metric_col2 = st.columns([0.2, 0.8])

                                with metric_col1:
                                    metric_label = _metric_label_for_service(service)
                                    st.metric(
                                        label=f"{metric_label} ({latest_data['unit']})",
                                        value=f"{latest_data['subscribers']:,.1f}",
                                        delta=f"{yoy_growth:+.1f}%" if yoy_growth is not None else None,
                                        delta_color="normal"
                                    )
                                    st.caption(f"Quarter: {latest_data['quarter']}")

                                with metric_col2:
                                    # Create either line chart or bar chart based on user selection
                                    fig = go.Figure()
                                    
                                    if chart_type == "Line Chart":
                                        # Create line chart
                                        fig.add_trace(
                                            go.Scatter(
                                                x=df['Quarter'],
                                                y=df[service_data['column_name']],
                                                mode='lines+markers',
                                                name=service,
                                                hovertemplate=(
                                                    "<b>" + service + "</b><br>" +
                                                    "Quarter: %{x}<br>" +
                                                    f"Value: %{{y:.1f}} {service_data['unit']}<br>" +
                                                    "<extra></extra>"
                                                )
                                            )
                                        )
                                    else:  # Bar Chart
                                        # Create bar chart
                                        fig.add_trace(
                                            go.Bar(
                                                x=df['Quarter'],
                                                y=df[service_data['column_name']],
                                                name=service,
                                                hovertemplate=(
                                                    "<b>" + service + "</b><br>" +
                                                    "Quarter: %{x}<br>" +
                                                    f"Value: %{{y:.1f}} {service_data['unit']}<br>" +
                                                    "<extra></extra>"
                                                )
                                            )
                                        )

                                    # Add specific layout options based on chart type
                                    xaxis_config = dict(
                                        showgrid=False,
                                        tickangle=45  # Add 45-degree rotation for all chart types
                                    )
                                    
                                    # For bar charts, adjust x-axis to ensure bars are displayed properly
                                    if chart_type == "Bar Chart":
                                        xaxis_config.update(
                                            type='category',
                                            categoryorder='array',
                                            categoryarray=df['Quarter'].tolist()
                                        )
                                    
                                    fig.update_layout(
                                        margin=dict(l=20, r=20, t=30, b=40),  # Increased bottom margin for rotated labels
                                        height=220,  # Slightly increased height to accommodate labels
                                        showlegend=False,
                                        template='mfe_blue',
                                        xaxis_title=None,
                                        yaxis_title=None,
                                        plot_bgcolor='white',
                                        paper_bgcolor='white',
                                        xaxis=xaxis_config,
                                        yaxis=dict(showgrid=True, gridcolor='#f0f0f0')
                                    )

                                    # Add chart zoom effect if not already added
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
                                    
                                    # Display the plot with zoom effect
                                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                                    st.plotly_chart(fig, use_container_width=True)
                                    st.markdown('</div>', unsafe_allow_html=True)
                            else:
                                st.error(f"Column '{column_name}' not found for {service}. Available columns: {', '.join(df.columns)}")
                                st.info(f"Check subscriber_data_processor.py for correct column mapping for {service}")
                                continue
                        else:
                            st.warning(f"No data available in the last 5 years for {service}")
                    else:
                        st.warning(f"Invalid date format in data for {service}")
                else:
                    st.warning(f"No data available for {service}")

                # Add a separator between services
                st.markdown("---")

with tab2:
    # Add subscriber type selector for comparison view
    comparison_subscriber_type = st.radio(
        "Select View Type",
        options=["Subscribers"],
        horizontal=True,
        key="comparison_subscriber_type"
    )

    # Multi-select for services to compare
    selected_services = st.multiselect(
        "Select Services to Compare",
        options=services,
        default=[services[0]] if services else None,
        help="Select services to compare"
    )

    # Add controls in two columns
    col1, col2 = st.columns(2)

    with col1:
        # Chart type selector
        chart_type = st.radio(
            "Select Chart Type",
            options=["Line", "Bar"],
            horizontal=True
        )

    with col2:
        # Get all available years across all services
        all_years = set()
        metric_type = "subscribers"

        for service in selected_services:
            service_data = st.session_state['subscriber_processor'].get_service_data(
                service, 
                metric_type=metric_type
            )
            if service_data and not service_data['data'].empty:
                df = service_data['data'].copy()
                df['date'] = df['Quarter'].apply(parse_quarter_to_date)
                df = df.dropna(subset=['date'])
                if not df.empty:
                    years = df['date'].dt.year.unique()
                    all_years.update(years)

        # Create year range selector if we have years
        if all_years:
            min_year, max_year = min(all_years), max(all_years)
            year_range = st.slider(
                "Select Year Range",
                min_value=min_year,
                max_value=max_year,
                value=(max_year-4, max_year),  # Default to last 5 years
                step=1
            )
        else:
            year_range = None

    if selected_services:
        # Dictionary to store all service data
        all_data = {}
        all_quarters_set = set()

        # First pass: collect all data and standardize quarters
        for service in selected_services:
            service_data = st.session_state['subscriber_processor'].get_service_data(
                service,
                metric_type=metric_type
            )
            if service_data and not service_data['data'].empty:
                df = service_data['data'].copy()

                # Convert quarters to datetime
                df['date'] = df['Quarter'].apply(parse_quarter_to_date)
                df = df.dropna(subset=['date'])

                # Filter by selected year range
                if year_range and not df.empty:
                    df = df[df['date'].dt.year.between(year_range[0], year_range[1])]

                if not df.empty:
                    # Sort chronologically
                    df = df.sort_values('date')
                    all_quarters_set.update(df['date'])
                    all_data[service] = {
                        'data': df,
                        'metric_col': service_data['column_name'],
                        'unit': service_data['unit']
                    }

        if all_data:
            # Sort quarters chronologically
            all_quarters = sorted(list(all_quarters_set))
            quarter_labels = [f"Q{(d.month-1)//3 + 1} {d.year}" for d in all_quarters]

            # Create figure
            fig = go.Figure()

            # Plot each service
            for service in selected_services:
                if service in all_data:
                    service_info = all_data[service]
                    df = service_info['data']

                    # Create trace based on chart type
                    if chart_type == "Line":
                        fig.add_trace(
                            go.Scatter(
                                x=df['Quarter'],
                                y=df[service_info['metric_col']],
                                name=service,
                                mode='lines+markers',
                                connectgaps=False,
                                hovertemplate=(
                                    f"<b>{service}</b><br>" +
                                    "Quarter: %{x}<br>" +
                                    f"Value: %{{y:.1f}} {service_info['unit']}<br>" +
                                    "<extra></extra>"
                                )
                            )
                        )
                    else:  # Bar chart
                        fig.add_trace(
                            go.Bar(
                                x=df['Quarter'],
                                y=df[service_info['metric_col']],
                                name=service,
                                hovertemplate=(
                                    f"<b>{service}</b><br>" +
                                    "Quarter: %{x}<br>" +
                                    f"Value: %{{y:.1f}} {service_info['unit']}<br>" +
                                    "<extra></extra>"
                                )
                            )
                        )

            # Update layout
            fig.update_layout(
                title=f"Streaming Services Comparison ({comparison_subscriber_type})",
                xaxis_title="Quarter",
                yaxis_title="Subscribers (millions)",
                showlegend=True,
                height=500,
                template='mfe_blue',
                xaxis=dict(
                    type='category',
                    categoryorder='array',
                    categoryarray=quarter_labels,
                    tickangle=45,
                    showgrid=True
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                barmode='group' if chart_type == "Bar" else None
            )

            # Display the plot with zoom effect
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No data available for the selected services and time range")
    else:
        st.info("Select multiple services to compare their performance")

# Update AI context
dashboard_state = {
    'page': 'Editorial',
    'comparison_services': selected_services if 'selected_services' in locals() else []
}
if 'ai_chat' in st.session_state:
    ai_chat = st.session_state.get("ai_chat")
    if ai_chat is not None and hasattr(ai_chat, "update_context"):
        ai_chat.update_context(dashboard_state)
