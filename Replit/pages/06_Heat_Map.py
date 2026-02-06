import streamlit as st

# Page config must be the first Streamlit command
st.set_page_config(
    page_title="Heat Map",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

from utils.page_transition import apply_page_transition_fix

# Apply fix for page transitions to prevent background bleed-through
apply_page_transition_fix()

from utils.styles import apply_plotly_theme, load_common_styles
load_common_styles()
apply_plotly_theme()

from utils.auth import check_password
import pandas as pd
import plotly.graph_objects as go
from utils.data_loader import load_advertising_data, get_available_filters
from utils.state_management import get_data_processor
from data_processor import FinancialDataProcessor
from utils.components import render_ai_assistant
import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add authentication check
# Always authenticated - no password check needed
from utils.time_utils import render_floating_clock
render_floating_clock()

# Add custom CSS and branding
st.markdown("""
    <style>
        :root {
            --app-font: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        .stApp {
            font-family: var(--app-font) !important;
        }

        .main-header {
            padding: 1rem 0;
            margin-bottom: 2rem;
        }

        .main-title {
            color: #0073ff;
            font-size: 2rem;
            font-weight: 600;
            margin: 0;
            font-family: var(--app-font);
        }

        .subtitle {
            color: #333;
            font-size: 1.2rem;
            font-weight: 400;
            margin-top: 0.5rem;
            font-family: var(--app-font);
        }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="main-header">
        <h1 class="main-title">🔥 Heat Map</h1>
        <p class="subtitle">Growth Analysis Dashboard</p>
    </div>
""", unsafe_allow_html=True)

# Initialize data processor with caching
@st.cache_resource(ttl=3600*24)
def get_data_processor():
    data_processor = FinancialDataProcessor()
    data_processor.load_data()
    return data_processor

data_processor = get_data_processor()
companies = data_processor.get_companies()

# Define available metrics
COMPANY_METRICS = {
    'Revenue': 'revenue',
    'Operating Income': 'operating_income',
    'Net Income': 'net_income',
    'R&D': 'rd',
    'Total Assets': 'total_assets',
    'Debt': 'debt',
    'Market Cap': 'market_cap',
    'Cost of Revenue': 'cost_of_revenue',
    'Capex': 'capex',
    'Cash Balance': 'cash_balance'
}

# Get filters for ad spend metrics
filter_options = get_available_filters()
available_countries = [c for c in filter_options.get('countries', []) if c != 'Global']

# Sidebar filters
with st.sidebar:
    st.header("Data Filters")

    metric_type = st.radio(
        "Select Metric Type",
        ["Company Metrics", "Ad Spend Metrics"],
        help="Choose between company financial metrics or advertising spend metrics"
    )

    if metric_type == "Company Metrics":
        selected_metric = st.selectbox(
            "Select Company Metric",
            options=list(COMPANY_METRICS.keys()),
            help="Select a company metric to analyze"
        )
        selected_entities = companies
        metric_key = COMPANY_METRICS[selected_metric]
    else:
        # Add view mode selector for ad spend metrics
        metric_selection_mode = st.radio(
            "Ad Spend Metric Type",
            options=["Macro Categories", "Detailed Metrics"],
            horizontal=True,
            key="metric_type_selector"
        )

        if metric_selection_mode == "Macro Categories":
            selected_metric = st.selectbox(
                "Select Ad Spend Categories",
                options=filter_options['macro_categories'],
                help="Select an advertising category to analyze"
            )
            selected_entities = available_countries
            # Use the selected macro category directly
            metric_key = selected_metric
        else:
            selected_metric = st.selectbox(
                "Select Ad Spend Metrics",
                options=filter_options['ad_types'],
                help="Select a detailed advertising metric to analyze"
            )
            selected_entities = available_countries
            metric_key = selected_metric

    # Different year ranges based on the selected metric type
    if metric_type == "Company Metrics":
        year_range = st.slider(
            "Select Year Range",
            min_value=2010,
            max_value=2024,
            value=(2022, 2023),
            help="Select start and end years for growth calculation (company data available from 2010 to 2024)"
        )
    else:  # Ad Spend Metrics
        year_range = st.slider(
            "Select Year Range",
            min_value=1999,
            max_value=2029,
            value=(2023, 2024),
            help="Select start and end years for growth calculation (advertising data available from 1999 to 2029)"
        )

def calculate_growth(start_value, end_value):
    """Calculate percentage growth between two values"""
    if not (start_value and end_value) or start_value == 0:
        return None
    return ((end_value - start_value) / abs(start_value)) * 100

def process_metric_data(entity, metric_type, metric_key, year_range):
    """Process metric data for an entity"""
    if metric_type == "Company Metrics":
        try:
            start_metrics = data_processor.get_metrics(entity, year_range[0])
            end_metrics = data_processor.get_metrics(entity, year_range[1])

            if start_metrics and end_metrics:
                start_value = start_metrics.get(metric_key)
                end_value = end_metrics.get(metric_key)
                
                
                growth = calculate_growth(start_value, end_value)
                
                
                return growth if growth is not None else None
        except Exception as e:
            logger.error(f"Error processing company metrics for {entity}: {str(e)}")
            return None
    else:
        filters = {
            'years': list(range(year_range[0], year_range[1] + 1)),
            'countries': [entity],
            'metrics': [metric_key],
            'view_mode': 'macro_categories' if metric_selection_mode == "Macro Categories" else 'detailed_metrics'
        }
        df = load_advertising_data(filters)

        if df.empty:
            logger.warning(f"No data found for {entity} with metric {metric_key}")
            return None

        # Group by year and sum values
        df_grouped = df.groupby('year')['value'].sum().reset_index()

        if len(df_grouped) >= 2:
            start_value = df_grouped[df_grouped['year'] == year_range[0]]['value'].iloc[0]
            end_value = df_grouped[df_grouped['year'] == year_range[1]]['value'].iloc[0]
            return calculate_growth(start_value, end_value)

        logger.warning(f"Insufficient data points for {entity}")
        return None

# Process data
growth_data = []
for entity in selected_entities:
    growth = process_metric_data(entity, metric_type, metric_key, year_range)
    if growth is not None:
        growth_data.append({
            'entity': entity,
            'growth': growth
        })

# Debug before sorting

# Sort data by growth (ascending order - from most negative to highest positive)
# This puts the most negative growth at the top (red) and the highest positive at the bottom (green)
growth_data = sorted(growth_data, key=lambda x: x['growth'], reverse=False)

# Debug after sorting

if growth_data:
    # Create heatmap data
    entities = [d['entity'] for d in growth_data]
    growth_values = [d['growth'] for d in growth_data]

    # Calculate color scale range
    max_abs_growth = max(abs(min(growth_values)), abs(max(growth_values)))

    # Create vertical heatmap
    fig = go.Figure(data=go.Heatmap(
        z=[[val] for val in growth_values],
        x=[selected_metric],
        y=entities,
        colorscale=[
            [0, '#67000d'],
            [0.125, '#a50f15'],
            [0.25, '#cb181d'],
            [0.375, '#ef3b2c'],
            [0.5, '#ffffff'],
            [0.625, '#a1d99b'],
            [0.75, '#74c476'],
            [0.875, '#31a354'],
            [1, '#006d2c']
        ],
        zmid=0,
        zmin=-max_abs_growth,
        zmax=max_abs_growth,
        text=[[f"{val:.1f}%" for val in [growth]] for growth in growth_values],
        texttemplate="%{text}",
        textfont={"family": "Montserrat", "size": 12},
        hovertemplate="<b>%{y}</b><br>" +
                      f"{selected_metric} Growth: %{{text}}<br>" +
                      "<extra></extra>"
    ))

    # Update layout for vertical orientation
    fig.update_layout(
        title=dict(
            text=f'{metric_type} Growth Analysis ({year_range[0]}-{year_range[1]})',
            font=dict(family="Montserrat", size=24)
        ),
        height=max(400, len(entities) * 30),
        margin=dict(t=100, b=50, l=150, r=100),
        xaxis=dict(
            title=None,
            tickangle=0,
            tickfont=dict(family="Montserrat", size=12)
        ),
        yaxis=dict(
            title="Companies" if metric_type == "Company Metrics" else "Countries",
            tickfont=dict(family="Montserrat", size=12),
            automargin=True
        ),
        coloraxis=dict(
            colorbar=dict(
                title=dict(
                    text="Growth Rate (%)",
                    font=dict(family="Montserrat", size=12)
                ),
                tickfont=dict(family="Montserrat", size=10),
                len=0.9,
                x=1.1
            )
        )
    )

    # Add chart zoom effect if not already added
    if not hasattr(st.session_state, 'heatmap_chart_css_added'):
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
        st.session_state.heatmap_chart_css_added = True
    
    # Display the plot with zoom effect
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Summary statistics
    st.markdown("### Summary Statistics")
    col1, col2, col3 = st.columns(3)

    with col1:
        positive_growth = len([d for d in growth_data if d['growth'] > 0])
        st.metric("Positive Growth", positive_growth)

    with col2:
        negative_growth = len([d for d in growth_data if d['growth'] < 0])
        st.metric("Negative Growth", negative_growth)

    with col3:
        avg_growth = sum(d['growth'] for d in growth_data) / len(growth_data) if growth_data else 0
        st.metric("Average Growth", f"{avg_growth:.1f}%")

else:
    st.info("No data available for the selected parameters.")

# Add AI Assistant to the sidebar
render_ai_assistant(location="sidebar", current_page="Heat Map")
