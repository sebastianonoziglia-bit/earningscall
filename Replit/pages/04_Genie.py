import streamlit as st

# Page config must be the first Streamlit command
st.set_page_config(page_title="Financial Genie (SPECIAL)", page_icon="🧞", layout="wide")

from utils.page_transition import apply_page_transition_fix

# Apply fix for page transitions to prevent background bleed-through
apply_page_transition_fix()

# Import other libraries after page config
from utils.insights import get_company_insight, get_cagr_insight
from utils.auth import check_password
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
from data_processor import FinancialDataProcessor
from utils.data_loader import load_advertising_data, get_available_filters
from utils.components import render_ai_assistant
from utils.styles import load_common_styles, load_genie_specific_styles
from utils.enhanced_chat_interface import render_enhanced_chat_interface
from utils.m2_supply_data import get_m2_monthly_data, get_m2_annual_data, create_m2_visualization
from utils.bitcoin_analysis import get_bitcoin_monthly_returns, create_bitcoin_monthly_returns_chart, render_bitcoin_analysis_section
from utils.inflation_analysis import render_inflation_methodology_section
from utils.inflation_calculator import create_inflation_analysis_box, add_inflation_selector
from subscriber_data_processor import SubscriberDataProcessor
import logging
from functools import lru_cache

# Import our Bitcoin integration module (optional; keep Genie functional if missing)
try:
    from integration_bitcoin_charts import integrate_bitcoin_inflation_features
except Exception:  # pragma: no cover
    integrate_bitcoin_inflation_features = None

# Set up logging
logging.basicConfig(level=logging.INFO)

# Apply shared styles
load_common_styles()
load_genie_specific_styles()

# Add header with language selector
from utils.header import render_header
from utils.language import get_text
render_header()

# Add SQL Assistant in the sidebar
from utils.sql_assistant_sidebar import render_sql_assistant_sidebar
render_sql_assistant_sidebar()

# Company brand color mapping function
def get_company_color(company_name):
    """Return a brand-appropriate color for each company"""
    company_colors = {
        'Netflix': '#E50914',           # Netflix red
        'Spotify': '#1DB954',           # Spotify green
        'Amazon': '#FF9900',            # Amazon orange
        'Apple': '#A2AAAD',             # Apple silver/gray
        'Microsoft': '#00A4EF',         # Microsoft blue
        'Meta Platforms': '#1877F2',    # Meta/Facebook blue
        'Alphabet': '#4285F4',          # Google blue
        'Disney': '#113CCF',            # Disney blue
        'Paramount': '#0064FF',         # Paramount blue
        'Warner Bros. Discovery': '#00A0E5',  # WBD blue
        'Comcast': '#000000',           # Comcast black
        'Roku': '#662D91',              # Roku purple
    }
    
    # Return the mapped color or a default if company not in mapping
    return company_colors.get(company_name, '#808080')  # Default gray

# Add additional styling for the Genie page
st.markdown("""
<style>
    /* Main container styling */
    .insights-content {
        margin-top: 2rem;
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 0.5rem;
        border-left: 4px solid #4285f4;
    }
    
    /* Scrollable container */
    .insights-container {
        max-height: 400px;
        overflow-y: auto;
        padding-right: 10px;
    }
    
    /* Better spacing for options */
    .stCheckbox {
        margin-bottom: 0.5rem;
    }
    
    /* Title alignment */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        margin-top: 1.5rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Check if user is logged in, redirect to Welcome page if not
# Always authenticated - no password check needed
from utils.time_utils import render_floating_clock
render_floating_clock()

# Initialize session state for data caching if not present
if 'data_cache' not in st.session_state:
    st.session_state.data_cache = {}

# Optimize caching for financial data - increased TTL and using hash_funcs
@st.cache_resource(ttl=3600*24, hash_funcs={FinancialDataProcessor: lambda _: None})
def get_data_processor():
    data_processor = FinancialDataProcessor()
    data_processor.load_data()
    return data_processor


@st.cache_resource(ttl=3600 * 24)
def get_subscriber_processor():
    return SubscriberDataProcessor()

# Cache filter options with longer TTL and prevent recomputation
@st.cache_data(ttl=3600*24)
def get_cached_filters():
    return get_available_filters()

# Cache year range computation with specific key
@st.cache_data(ttl=3600*24)
def get_available_years(companies_tuple, data_processor_id):
    all_years = []
    for company in companies_tuple:
        years = data_processor.get_available_years(company)
        all_years.extend(years)
    return sorted(list(set(all_years)))

# Update the mapping of macro categories to their detailed metrics
MACRO_CATEGORY_MAPPING = {
    'Television': ['Free TV', 'Pay TV'],  # Main category matching AD_MACRO_CATEGORIES
    'TELEVISION': ['Free TV', 'Pay TV'],  # Uppercase version for case-insensitive matching
    'TV': ['Free TV', 'Pay TV'],  # Keep TV for backward compatibility
    'Digital': ['Other Desktop', 'Other Mobile', 'Search Desktop', 'Search Mobile', 
                'Social Mobile', 'Video Mobile', 'Display Desktop', 'Display Mobile', 
                'Social Desktop', 'Video Desktop'],
    'OOH': ['Digital OOH', 'Traditional OOH'],
    'Press': ['Magazine', 'Newspaper'],
    'Radio': ['Radio'],  # Single metric categories
    'Cinema': ['Cinema']  # Single metric categories
}

# Optimize advertising data loading with specific key
@st.cache_data(ttl=3600)
def load_cached_advertising_data(countries_tuple, metrics_tuple, year_start, year_end):
    # Determine if we need to fetch detailed metrics based on macro categories
    detailed_metrics = []
    for metric in metrics_tuple:
        if metric in MACRO_CATEGORY_MAPPING:
            detailed_metrics.extend(MACRO_CATEGORY_MAPPING[metric])
        else:
            detailed_metrics.append(metric)

    filters = {
        'years': list(range(year_start, year_end + 1)),
        'countries': list(countries_tuple),
        'metrics': detailed_metrics
    }
    return load_advertising_data(filters)

# Update the data processing section to handle None values
@st.cache_data(ttl=3600)
def process_metrics_data(df, country, metric, _year_range):
    if df.empty:
        return None

    country_data = df[df['country'] == country]

    # Handle macro categories by summing their constituent metrics
    if metric in MACRO_CATEGORY_MAPPING:
        detailed_metrics = MACRO_CATEGORY_MAPPING[metric]
        metric_data = country_data[country_data['metric_type'].isin(detailed_metrics)]

        if not metric_data.empty:
            # Group by year and sum the values for all constituent metrics
            metric_data = metric_data.groupby('year', as_index=False)['value'].sum()
    else:
        metric_data = country_data[country_data['metric_type'] == metric]

    if metric_data.empty or len(metric_data) < 2:
        return None

    metric_data = metric_data.sort_values('year')
    values = metric_data['value'].tolist()

    # Calculate YoY changes
    yoy_changes = []
    for i in range(len(values)):
        if i > 0:
            current_val = values[i]
            prev_val = values[i-1]
            yoy_change = ((current_val - prev_val) / prev_val * 100) if prev_val != 0 else 0
        else:
            yoy_change = 0
        yoy_changes.append(yoy_change)

    return {
        'years': metric_data['year'].tolist(),
        'values': values,
        'yoy_changes': yoy_changes
    }


# Initialize data processor with caching
if 'data_processor' not in st.session_state:
    st.session_state['data_processor'] = get_data_processor()

data_processor = st.session_state['data_processor']
filter_options = get_cached_filters()

# Add custom styling for select chips to the Genie page styles
st.markdown("""
<style>
    /* Company Analysis section chips */
    [data-testid="stMultiSelect"]:has([aria-label*="Select Companies"]) .st-emotion-cache-12w0qpk,
    [data-testid="stMultiSelect"]:has([aria-label*="Company Metrics"]) .st-emotion-cache-12w0qpk,
    [data-testid="stMultiSelect"]:has([aria-label*="Company Segments"]) .st-emotion-cache-12w0qpk {
        background-color: #f3e5f5;
        border-color: #9c27b0;
    }

    [data-testid="stMultiSelect"]:has([aria-label*="Select Companies"]) .st-emotion-cache-12w0qpk:hover,
    [data-testid="stMultiSelect"]:has([aria-label*="Company Metrics"]) .st-emotion-cache-12w0qpk:hover,
    [data-testid="stMultiSelect"]:has([aria-label*="Company Segments"]) .st-emotion-cache-12w0qpk:hover {
        background-color: #e1bee7;
        border-color: #7b1fa2;
    }

    /* Ad Spend Analysis section chips */
    [data-testid="stMultiSelect"]:has([aria-label*="Select Countries"]) .st-emotion-cache-12w0qpk,
    [data-testid="stMultiSelect"]:has([aria-label*="Ad Spend Categories"]) .st-emotion-cache-12w0qpk,
    [data-testid="stMultiSelect"]:has([aria-label*="Ad Spend Metrics"]) .st-emotion-cache-12w0qpk {
        background-color: #e8f0fe;
        border-color: #4285f4;
    }
</style>
""", unsafe_allow_html=True)

# Create a title layout with columns
col1, col2, col3 = st.columns([0.75, 0.15, 0.10])
with col1:
    st.markdown("""
    <h1 style="margin-bottom: 0.2rem;">Financial Genie <span style="color: #FF4204; font-size: 0.65em; font-weight: bold;">(SPECIAL)</span></h1>
    """, unsafe_allow_html=True)
with col2:
    st.image("attached_assets/Copy - Cover Layout.gif", use_column_width=True)
with col3:
    st.markdown("""
    <a href="#genie-chat-section" class="go-to-genie-btn">
        Go to Genie
    </a>
    """, unsafe_allow_html=True)
    
st.write("Advanced comparative analysis with inflation adjustments and advertising spend")

# Add CSS for the Go to Genie button
st.markdown("""
<style>
.go-to-genie-btn {
    display: inline-block;
    background-color: #4285F4;
    color: white !important;
    padding: 8px 12px;
    font-size: 0.9rem;
    font-weight: 500;
    border-radius: 4px;
    text-decoration: none !important;
    transition: all 0.3s ease;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    margin-top: 10px;
    text-align: center;
}
.go-to-genie-btn:hover {
    background-color: #3367D6;
    box-shadow: 0 3px 8px rgba(0,0,0,0.3);
    transform: translateY(-1px);
}
</style>
""", unsafe_allow_html=True)

# Add some spacing
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

def load_recession_periods():
    """
    Deprecated: recession shading previously used a hard-coded list.
    Keep for backward compatibility but return an empty frame (no hard-coded data).
    """
    return pd.DataFrame(columns=["period", "start_year", "end_year", "description"])


@st.cache_data(ttl=3600 * 24)
def _get_usd_inflation_series(source: str = "Official") -> dict:
    """
    Return a {year: inflation_rate_pct} dict from the 'USD Inflation' sheet.
    """
    from utils.inflation_calculator import load_usd_inflation_table

    df = load_usd_inflation_table()
    if df is None or df.empty:
        return {}

    col_map = {
        "Official": "Official Headline CPI",
        # Keep the existing UI label "Alternative" but source it from the sheet.
        "Alternative": "ShadowStats 1980s Method*",
    }
    col = col_map.get(source, col_map["Official"])
    if "Year" not in df.columns or col not in df.columns:
        return {}

    sub = df[["Year", col]].dropna().copy()
    sub["Year"] = pd.to_numeric(sub["Year"], errors="coerce").astype("Int64")
    sub[col] = pd.to_numeric(sub[col], errors="coerce")
    sub = sub.dropna(subset=["Year", col])
    return {int(y): float(v) for y, v in zip(sub["Year"].astype(int), sub[col].astype(float))}

def adjust_for_purchasing_power(value, year):
    """
    Adjust value based on USD purchasing power for given year.
    E.g., if a value was $100 in 2020 (purchasing power 0.64),
    it would be adjusted to $64 to show the real purchasing power decline.
    """
    # Use the USD Inflation sheet to compute a purchasing-power adjustment factor
    # (convert nominal values into "base-year dollars").
    from utils.inflation_calculator import get_price_index

    try:
        year_int = int(year)
    except Exception:
        return value

    base_year = st.session_state.get("purchasing_power_base_year", 2000)
    try:
        base_year = int(base_year)
    except Exception:
        base_year = 2000

    idx = get_price_index("Official Headline CPI")
    if idx is None or idx.empty or year_int not in idx.index or base_year not in idx.index:
        return value

    factor = float(idx.loc[base_year]) / float(idx.loc[year_int])
    return value * factor

def format_large_number(value):
    """Format large numbers to billions/millions/thousands for readability"""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if abs(value) >= 1e12:  # Trillions
        return f"${value/1e12:.2f}T"
    elif abs(value) >= 1e9:  # Billions
        return f"${value/1e9:.2f}B"
    elif abs(value) >= 1e6:  # Millions
        return f"${value/1e6:.2f}M"
    elif abs(value) >= 1e3:  # Thousands
        return f"${value/1e3:.1f}K"
    else:
        return f"${value:,.2f}"

# Initialize session state for search
if 'search_country' not in st.session_state:
    st.session_state.search_country = ""

# Create main columns for the layout
col1, col2 = st.columns(2)

with col1:
    # Company Analysis Section
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader("📊 Company Analysis")

    # Company selection (up to 3)
    companies = data_processor.get_companies()
    selected_companies = st.multiselect(
        "Select Companies (up to 3)",
        options=companies,
        default=[companies[0]] if companies else None,
        max_selections=3,
        key="company_selector"
    )

    # Company metrics selection
    if selected_companies:
        # Available company metrics
        available_metrics = {
            'Revenue': 'revenue',
            'Operating Income': 'operating_income',
            'Net Income': 'net_income',
            'R&D': 'rd',
            'Total Assets': 'total_assets',
            'Debt': 'debt',
            'Market Cap': 'market_cap',
            'Cost of Revenue': 'cost_of_revenue',
            'Capex': 'capex',
            'Cash Balance': 'cash_balance'  # Added Cash Balance metric
        }
        
        # Allow selecting both financial metrics and segments

        st.markdown("##### Company Data Options")
        st.markdown("""
        <div style="color: #666; font-size: 0.85rem; margin-bottom: 8px;">
        You can select both financial metrics and segments to display simultaneously
        </div>
        """, unsafe_allow_html=True)

        # Financial metrics section
        selected_company_metrics = st.multiselect(
            "Select Company Financial Metrics",
            options=list(available_metrics.keys()),
            default=['Revenue'],
            help="Select financial metrics to compare across companies"
        )
        
        # Segment selection section
        # Helper function to get segments for a company/year
        @st.cache_data(ttl=3600)
        def get_company_segments_for_selection(company):
            latest_year = max(data_processor.get_available_years(company))
            segments_data = data_processor.get_segments(company, latest_year)
            if segments_data and 'labels' in segments_data:
                return [(company, segment) for segment in segments_data['labels']]
            return []
        
        # Get segments for all selected companies
        segment_options = []
        for company in selected_companies:
            company_segments = get_company_segments_for_selection(company)
            segment_options.extend(company_segments)
        
        # Format segment options for display
        formatted_segment_options = [f"{company}: {segment}" for company, segment in segment_options]
        
        # Add a divider with stronger visual distinction
        st.markdown("""
        <div style="margin: 15px 0 10px 0; border-top: 2px solid #4CAF50; position: relative;">
            <div style="position: absolute; top: -12px; left: 10px; background-color: white; padding: 0 10px; color: #4CAF50; font-weight: bold; font-size: 0.9rem;">
                SEGMENTS
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Segment selection without redundant explanation
        
        selected_segment_options = st.multiselect(
            "Select Company Segments",
            options=formatted_segment_options,
            default=[] if not formatted_segment_options else None,
            help="Select segments to compare their revenue performance across years. Segments from different companies can be compared directly."
        )
        
        # Add a note about simultaneous viewing if both types selected
        if selected_company_metrics and selected_segment_options:
            st.success("✓ You're viewing both financial metrics and segments on the same chart for direct comparison! Segments have their own Y-axis labeled 'Segment Values'.")
        elif selected_segment_options:
            st.info("💡 Segment data will be displayed with distinctive dotted lines and diamond markers on a dedicated Y-axis.")
        elif selected_company_metrics and formatted_segment_options:
            st.info("💡 You can select both financial metrics and segments to view them on the same chart with separate Y-axes!")
        
        # Parse the selected segments back to (company, segment) tuples
        selected_segments = []
        for selected in selected_segment_options:
            company, segment = selected.split(": ", 1)
            selected_segments.append((company, segment))
        
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    # Ad Spend Analysis Section
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader("📈 Country Ad Spend Analysis")
    # Country search and selection
    country_search = st.text_input(
        "Search Countries",
        value=st.session_state.search_country,
        placeholder="Type to search countries...",
        key="country_search"
    )
    st.session_state.search_country = country_search

    # Filter countries based on search (excluding Global)
    available_countries = [c for c in filter_options.get('countries', []) if c != 'Global']
    filtered_countries = [
        country for country in available_countries
        if country_search.lower() in country.lower()
    ] if country_search else available_countries

    # Country selection with Italy as default
    selected_countries = st.multiselect(
        "Select Countries",
        options=filtered_countries,
        default=['Italy'] if 'Italy' in filtered_countries else [filtered_countries[0]] if filtered_countries else None,
        help="Select one or more countries to analyze",
        key="country_selector"
    )

    # Ad spend metric selection
    metric_selection_mode = st.radio(
        "Ad Spend Metric Type",
        options=["Macro Categories", "Detailed Metrics"],
        horizontal=True,
        key="metric_type_selector"
    )

    if metric_selection_mode == "Macro Categories":
        selected_ad_metrics = st.multiselect(
            "Select Ad Spend Categories",
            options=filter_options['macro_categories'],
            default=['Digital'] if 'Digital' in filter_options['macro_categories'] else filter_options['macro_categories'][:1],
            key="macro_categories_selector"
        )
        selected_metrics = selected_ad_metrics
        selected_detailed_metrics = []
        for category in selected_ad_metrics:
            selected_detailed_metrics.extend(filter_options['ad_type_mappings'].get(category, []))
    else:
        selected_detailed_metrics = st.multiselect(
            "Select Ad Spend Metrics",
            options=filter_options['ad_types'],
            default=['Free TV'] if 'Free TV' in filter_options['ad_types'] else filter_options['ad_types'][:1],
            key="detailed_metrics_selector"
        )
        selected_metrics = selected_detailed_metrics
    st.markdown("</div>", unsafe_allow_html=True)

# Add CSS for layout improvements including tight spacing and consistent headers
st.markdown("""
<style>
    /* Flex layout for section headers */
    .section-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        padding-bottom: 0;
        border-bottom: 1px solid #eee;
    }
    .section-title {
        font-size: 1.3rem;
        font-weight: 600;
        margin: 0;
        padding: 0;
        padding-bottom: 0.5rem;
    }
    
    /* Flex layout for content columns */
    .options-content, .insights-content {
        width: 100%;
    }
    
    /* Override Streamlit's default column styling */
    [data-testid="column"] {
        padding: 0 10px !important;
    }
    .option-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        grid-gap: 8px;
        margin-bottom: 10px;
    }
    .option-item {
        padding: 4px;
        margin-bottom: 0;
    }
    .option-item h4 {
        margin-top: 0;
        margin-bottom: 4px;
        font-size: 0.95rem;
    }
    .option-item .stCheckbox {
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .option-item .stRadio {
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .option-item .stSelectbox {
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .insights-container {
        margin-top: 15px;
        padding-top: 10px;
    }
    
    .insights-content {
        margin-top: 15px;
        padding: 10px;
        background-color: #f9f9f9;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# Create a title for Macro Economics Indicators with proper positioning
st.markdown("""
<div style="margin-top: 20px; margin-bottom: 10px;">
    <div style="font-size: 18px; font-weight: bold;">🔧 Activate Macro Economics Indicators</div>
</div>
""", unsafe_allow_html=True)

# Organize options into expanders to reduce clutter
with st.expander("Activate Macro Economics Indicators", expanded=False):
    # Row 1 - Basic Options
    basic_cols = st.columns([1, 1])
    
    with basic_cols[0]:
        show_global = st.checkbox(
            "Show Global Data",
            value=False,
            help="Show global data on secondary axis",
            key="show_global"
        )
        
        show_growth_rates = st.checkbox(
            "Show Growth Rates",
            value=False,
            help="Display Year-over-Year percentage growth rates instead of absolute values",
            key="show_growth_rates"
        )
    
    with basic_cols[1]:
        show_recessions = st.checkbox(
            "Show Recession Periods",
            value=False,
            help="(Disabled) Recession shading requires a dedicated sheet; hard-coded periods were removed.",
            key="recession_checkbox"
        )
        
        show_m2_supply = st.checkbox(
            "M2 Money Supply",
            value=False,
            help="Display M2 Money Supply data with monthly growth rates",
            key="m2_supply_checkbox"
        )

        show_subscribers = st.checkbox(
            "Subscribers / Users",
            value=False,
            help="Plot subscriber/user counts from the 'Company_subscribers_values' sheet (annualized).",
            key="subscribers_checkbox",
        )
        if show_subscribers:
            sub_proc = get_subscriber_processor()
            services = sub_proc.get_service_names() if sub_proc else []
            st.session_state["selected_services"] = st.multiselect(
                "Select Services",
                options=services,
                default=[],
                key="selected_services_multiselect",
            )
    
    # Without additional header inside
    advanced_cols = st.columns([1, 1])
    
    with advanced_cols[0]:
        show_inflation = st.checkbox(
            "Show USD Inflation Rates",
            value=False,
            help="Display USD inflation rates alongside financial data",
            key="show_inflation_checkbox"
        )
        
        if show_inflation:
            inflation_type = st.radio(
                "Inflation Source",
                ["Official", "Alternative"],
                horizontal=True,
                key="inflation_type"
            )
    
    with advanced_cols[1]:
        adjust_purchasing_power = st.checkbox(
            "Adjust for USD Purchasing Power",
            value=False,
            help="Convert values to real terms using historical USD purchasing power",
            key="purchasing_power_checkbox"
        )
        if adjust_purchasing_power:
            from utils.inflation_calculator import load_usd_inflation_table

            _tbl = load_usd_inflation_table()
            _years = []
            if _tbl is not None and not _tbl.empty and "Year" in _tbl.columns:
                _years = sorted(set(_tbl["Year"].dropna().astype(int).tolist()))
            if _years:
                st.session_state["purchasing_power_base_year"] = st.selectbox(
                    "Purchasing Power Base Year",
                    options=_years,
                    index=0,
                    key="purchasing_power_base_year_select",
                    help="Values will be adjusted into base-year dollars using the USD Inflation sheet.",
                )

# Year range selector positioned right below the options row
if selected_companies:
    all_years = get_available_years(tuple(selected_companies), id(data_processor))
else:
    # Default year range when no companies selected
    all_years = list(range(2010, 2025))

year_range = st.slider(
    "Select Year Range",
    min_value=min(all_years),
    max_value=max(all_years),
    value=(min(all_years), max(all_years)),
    key="year_range_selector"
)

# Initialize inflation_type in session_state if not already present
if 'inflation_type' not in st.session_state:
    st.session_state.inflation_type = "Official"

# Add Global to selected countries if enabled
all_selected_countries = selected_countries.copy()
if show_global:
    all_selected_countries.append('Global')


# Initialize selected_segments variable so it's always defined
if 'selected_segment_options' in locals() and selected_segment_options:
    selected_segments = []
    for selected in selected_segment_options:
        company, segment = selected.split(": ", 1)
        selected_segments.append((company, segment))
else:
    selected_segments = []
    
# Create visualizations when any data selection is made 
if selected_metrics or selected_company_metrics or selected_segment_options or show_global or show_m2_supply:
    # We can display both company metrics AND segments simultaneously on the same chart
    # Create visualization
    fig = go.Figure()

    # Load recession data if needed
    recession_df = load_recession_periods() if show_recessions else None

    # Create color mapping for consistent colors
    color_sequence = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                     '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
                     
    # Store color mapping in session state to reference in detailed insights
    if 'color_mapping' not in st.session_state:
        st.session_state.color_mapping = {}

    # Track max values for each axis
    country_max_values = []
    global_max_values = []
    company_max_values = []

    # Process advertising data if metrics are selected or show_global is True
    # Note: We process advertising data even if company metrics are selected (removed the dependency)
    if selected_metrics and all_selected_countries or show_global:
        df = load_cached_advertising_data(
            tuple(all_selected_countries),
            tuple(selected_metrics),
            year_range[0],
            year_range[1]
        )

        logging.info(f"Loaded data frame with shape: {df.shape if df is not None else 'None'}")

        if df is not None and not df.empty:
            for country in all_selected_countries:
                for metric in selected_metrics:
                    processed_data = process_metrics_data(df, country, metric, year_range)

                    if processed_data:
                        is_global = country == 'Global'
                        yaxis = 'y2' if is_global else 'y'

                        color_index = len(fig.data) % len(color_sequence)
                        base_color = color_sequence[color_index]

                        if is_global:
                            color = base_color.replace('rgb', 'rgba').replace(')', ', 0.3)')
                        else:
                            color = base_color
                            
                        # Store the color in session state for reference in insights
                        trace_name = f"{country} - {metric}"
                        st.session_state.color_mapping[trace_name] = base_color

                        values = processed_data['values']
                        if adjust_purchasing_power:
                            values = [adjust_for_purchasing_power(val, year) for val, year in zip(values, processed_data['years'])]
                        
                        # If show_growth_rates is checked, use YoY changes instead of actual values
                        display_values = processed_data['yoy_changes'] if show_growth_rates else values
                        
                        # Format for hover display depends on what we're showing
                        if show_growth_rates:
                            # When showing growth rates, the main value is the YoY change percentage
                            hover_values = [f"{change:.1f}%" for change in processed_data['yoy_changes']]
                            value_label = "YoY Growth"
                            # The customdata will contain the actual value for reference
                            custom_values = [format_large_number(val) for val in values]
                            hover_template = (
                                f"<b>{country} - {metric}</b><br>" +
                                "Year: %{x}<br>" +
                                f"{value_label}: %{{customdata[0]}}<br>" +
                                "Actual Value: %{customdata[1]}<br>" +
                                "<extra></extra>"
                            )
                            # Zip the growth percentage and actual value for hover data
                            custom_values = list(zip(hover_values, custom_values))
                        else:
                            # When showing actual values, the customdata contains YoY change
                            hover_values = [format_large_number(val) for val in values]
                            value_label = "Value"
                            # Format YoY changes with percentage sign
                            formatted_yoy = [f"{yoy:.1f}%" for yoy in processed_data['yoy_changes']]
                            custom_values = formatted_yoy
                            hover_template = (
                                f"<b>{country} - {metric}</b><br>" +
                                "Year: %{x}<br>" +
                                f"{value_label}: {hover_values}<br>" +
                                "YoY Change: %{customdata}<br>" +
                                "<extra></extra>"
                            )

                        fig.add_trace(go.Scatter(
                            x=processed_data['years'],
                            y=display_values,
                            name=f"{country} - {metric}",
                            mode='lines+markers',
                            marker=dict(size=8),
                            line=dict(
                                color=color,
                                dash='dot' if is_global else None
                            ),
                            customdata=custom_values,
                            hovertemplate=hover_template,
                            yaxis=yaxis
                        ))

                        for i in range(len(processed_data['values'])):
                            if is_global:
                                global_max_values.append(processed_data['values'][i])
                            else:
                                country_max_values.append(processed_data['values'][i])


    # Helper function to get and log company metric data
    @lru_cache(maxsize=32)
    def get_cached_company_years(company):
        return data_processor.get_available_years(company)

    @lru_cache(maxsize=32)
    def get_cached_metrics(company, year):
        return data_processor.get_metrics(company, year)
        
    @lru_cache(maxsize=32)
    def get_cached_segments(company, year):
        return data_processor.get_segments(company, year)

    def get_company_metric_data(company, metric_name, metric_key, filtered_years, data_processor):
        metric_data = []
        try:
            for year in filtered_years:
                metrics = get_cached_metrics(company, year)
                if metrics and metric_key in metrics:
                    value = metrics[metric_key]
                    if value is not None:
                        metric_data.append({
                            'year': year,
                            'value': value
                        })
                        company_max_values.append(value)
                        logging.info(f"Loaded {metric_name} for {company} in {year}: {value}")
                else:
                    logging.warning(f"No {metric_name} data for {company} in {year}")
        except Exception as e:
            logging.error(f"Error loading {metric_name} for {company}: {str(e)}")
        return metric_data
        
    def get_segment_data(company, segment_name, filtered_years):
        """Get data for a specific segment across multiple years"""
        segment_data = []
        try:
            for year in filtered_years:
                segments = get_cached_segments(company, year)
                if segments and 'labels' in segments and 'values' in segments:
                    # Find index of segment name in labels list
                    if segment_name in segments['labels']:
                        idx = segments['labels'].index(segment_name)
                        value = segments['values'][idx]
                        if value is not None:
                            segment_data.append({
                                'year': year,
                                'value': value
                            })
                            company_max_values.append(value)
                            logging.info(f"Loaded segment {segment_name} for {company} in {year}: {value}")
                else:
                    logging.warning(f"No segment data for {company} in {year}")
        except Exception as e:
            logging.error(f"Error loading segment {segment_name} for {company}: {str(e)}")
        return segment_data

    # Process company data
    if selected_companies and selected_company_metrics:
        for company in selected_companies:
            company_years = get_cached_company_years(company)
            filtered_years = [y for y in company_years if year_range[0] <= y <= year_range[1]]

            for metric_name in selected_company_metrics:
                metric_key = available_metrics[metric_name]
                metric_data = get_company_metric_data(company, metric_name, metric_key, filtered_years, data_processor)

                if metric_data:
                    df_metric = pd.DataFrame(metric_data)
                    df_metric = df_metric.sort_values('year')

                    if adjust_purchasing_power:
                        df_metric['value'] = df_metric.apply(lambda row: adjust_for_purchasing_power(row['value'], row['year']), axis=1)

                    # Calculate YoY changes
                    yoy_changes = []
                    for i in range(len(df_metric)):
                        if i > 0:
                            current_val = df_metric.iloc[i]['value']
                            prev_val = df_metric.iloc[i-1]['value']
                            yoy_change = ((current_val - prev_val) / prev_val * 100) if prev_val != 0 else 0
                        else:
                            yoy_change = 0
                        yoy_changes.append(yoy_change)

                    hover_values = [format_large_number(val) for val in df_metric['value']]

                    # Determine a color index for this metric
                    color_index = len(fig.data) % len(color_sequence)
                    base_color = color_sequence[color_index]
                    
                    # Store the color in session state for reference in insights
                    trace_name = f"{company} - {metric_name} (Metric)"
                    st.session_state.color_mapping[trace_name] = base_color
                    
                    # Use distinctive styling for financial metrics - solid lines and circle markers
                    # If show_growth_rates is checked, use YoY changes instead of actual values
                    display_values = yoy_changes if show_growth_rates else df_metric['value']
                    
                    # Format hover information based on what we're displaying
                    if show_growth_rates:
                        # When showing growth rates, the main value is the YoY change percentage
                        formatted_growth = [f"{yoy:.1f}%" for yoy in yoy_changes]
                        hover_template = (
                            f"<b>{company} - {metric_name}</b><br>" +
                            "Year: %{x}<br>" +
                            "YoY Growth: %{customdata[0]}<br>" +
                            "Actual Value: %{customdata[1]}<br>" +
                            "<b>Type: Financial Metric</b><br>" +
                            "<extra></extra>"
                        )
                        custom_data = list(zip(formatted_growth, hover_values))  # Both formatted growth and values
                    else:
                        # When showing actual values, customdata contains the YoY changes with % formatting
                        formatted_yoy = [f"{yoy:.1f}%" for yoy in yoy_changes]
                        hover_template = (
                            f"<b>{company} - {metric_name}</b><br>" +
                            "Year: %{x}<br>" +
                            "Value: %{customdata[1]}<br>" +
                            "YoY Change: %{customdata[0]}<br>" +
                            "<b>Type: Financial Metric</b><br>" +
                            "<extra></extra>"
                        )
                        custom_data = list(zip(formatted_yoy, hover_values))
                        
                    fig.add_trace(go.Scatter(
                        x=df_metric['year'],
                        y=display_values,
                        name=f"{company} - {metric_name} (Metric)",
                        mode='lines+markers',
                        marker=dict(
                            size=9,
                            symbol='circle',
                            color=get_company_color(company),  # Use brand color
                            line=dict(width=1.5, color='rgba(255,255,255,0.8)')
                        ),
                        line=dict(
                            width=3,
                            color=get_company_color(company),  # Use brand color
                            shape='linear'  # Straight lines for metrics
                        ),
                        customdata=custom_data,
                        hovertemplate=hover_template,
                        yaxis='y4'  # Use a separate y-axis for company metrics
                    ))
    
    # Process segment data if selected
    if selected_segments:
        for company, segment_name in selected_segments:
            company_years = get_cached_company_years(company)
            filtered_years = [y for y in company_years if year_range[0] <= y <= year_range[1]]
            
            segment_data = get_segment_data(company, segment_name, filtered_years)
            
            if segment_data:
                df_segment = pd.DataFrame(segment_data)
                df_segment = df_segment.sort_values('year')
                
                if adjust_purchasing_power:
                    df_segment['value'] = df_segment.apply(lambda row: adjust_for_purchasing_power(row['value'], row['year']), axis=1)
                
                # Calculate YoY changes
                yoy_changes = []
                for i in range(len(df_segment)):
                    if i > 0:
                        current_val = df_segment.iloc[i]['value']
                        prev_val = df_segment.iloc[i-1]['value']
                        yoy_change = ((current_val - prev_val) / prev_val * 100) if prev_val != 0 else 0
                    else:
                        yoy_change = 0
                    yoy_changes.append(yoy_change)
                
                hover_values = [format_large_number(val) for val in df_segment['value']]
                
                # Use distinctive styling for segment traces so they're easy to distinguish from metrics
                # Determine a color index, then get a base color and create semi-transparent version
                color_index = len(fig.data) % len(color_sequence)
                base_color = color_sequence[color_index]
                
                # Store the color in session state for reference in insights
                trace_name = f"{company} - {segment_name} (Segment)"
                st.session_state.color_mapping[trace_name] = base_color
                
                # If show_growth_rates is checked, use YoY changes instead of actual values
                display_values = yoy_changes if show_growth_rates else df_segment['value']
                
                # Format hover information based on what we're displaying
                if show_growth_rates:
                    # When showing growth rates, the main value is the YoY change percentage
                    formatted_growth = [f"{yoy:.1f}%" for yoy in yoy_changes]
                    hover_template = (
                        f"<b>{company} - {segment_name}</b><br>" +
                        "Year: %{x}<br>" +
                        "YoY Growth: %{customdata[0]}<br>" +
                        "Actual Value: %{customdata[1]}<br>" +
                        "<b>Type: Business Segment</b><br>" +
                        "<extra></extra>"
                    )
                    custom_data = list(zip(formatted_growth, hover_values))  # Both growth and values
                else:
                    # When showing actual values, customdata contains the YoY changes with % formatting
                    formatted_yoy = [f"{yoy:.1f}%" for yoy in yoy_changes]
                    hover_template = (
                        f"<b>{company} - {segment_name}</b><br>" +
                        "Year: %{x}<br>" +
                        "Value: %{customdata[1]}<br>" +
                        "YoY Change: %{customdata[0]}<br>" +
                        "<b>Type: Business Segment</b><br>" +
                        "<extra></extra>"
                    )
                    custom_data = list(zip(formatted_yoy, hover_values))
                
                # Create a segment trace with enhanced styling
                fig.add_trace(go.Scatter(
                    x=df_segment['year'],
                    y=display_values,
                    name=f"{company} - {segment_name} (Segment)",
                    mode='lines+markers',
                    marker=dict(
                        size=12, 
                        symbol='diamond',
                        color=base_color,
                        line=dict(width=2, color='rgba(0,0,0,0.5)'),
                        opacity=0.9
                    ),
                    line=dict(
                        dash='dash', 
                        width=3,
                        color=base_color,
                        shape='spline'  # Smooth curved lines
                    ),
                    opacity=0.85,  # Slight transparency for the whole trace
                    customdata=custom_data,
                    hovertemplate=hover_template,
                    yaxis='y5'  # Use a dedicated y-axis for segments
                ))

    # Add recession periods if enabled
    if show_recessions and recession_df is not None:
        filtered_recessions = recession_df[
            (recession_df['start_year'] >= year_range[0]) &
            (recession_df['end_year'] <= year_range[1])
        ]

        for _, period in filtered_recessions.iterrows():
            fig.add_vrect(
                x0=str(period['start_year']),
                x1=str(period['end_year']),
                fillcolor="lightgray",
                opacity=0.2,
                layer="below",
                line_width=0,
                annotation=dict(
                    text=period['period'],
                    textangle=-90,
                    font=dict(size=10),
                    x=(period['start_year'] + period['end_year']) / 2,
                    y=1.02,
                    showarrow=False
                )
            )

    # Add inflation rate if enabled
    if show_inflation:
        # Use the value from session state to ensure consistency
        inflation_type_value = st.session_state.inflation_type
        series = _get_usd_inflation_series(inflation_type_value)
        inflation_years = sorted(y for y in series.keys() if year_range[0] <= y <= year_range[1])
        inflation_values = [series[y] for y in inflation_years]

        # Use proper label that includes the source information
        source_label = "USD Inflation (sheet)" if inflation_type_value == "Official" else "Alternative Inflation (sheet)"
        
        fig.add_trace(go.Scatter(
            x=inflation_years,
            y=inflation_values,
            name=f'USD Inflation Rate ({source_label})',
            mode='lines+markers',
            line=dict(width=2, dash='dot', color='rgba(255, 0, 0, 0.3)'),
            marker=dict(size=6, color='rgba(255, 0, 0, 0.3)'),
            yaxis='y3',
            hovertemplate="<b>%{data.name}</b><br>" +
                          "Year: %{x}<br>" +
                          "Rate: %{y:.1f}%<br>" +
                          "<extra></extra>"
        ))

    # Calculate axis ranges and steps
    country_max = max(country_max_values) if country_max_values else 0
    global_max = max(global_max_values) if global_max_values else 0
    company_max = max(company_max_values) if company_max_values else 0

    def get_axis_range_and_step(max_val):
        """Calculate appropriate axis range and step size based on data"""
        if max_val <= 100:  # For values up to 100M
            step = 10
            upper_limit = min(100, max_val * 1.2)  # 20% padding
        elif max_val <= 500:  # For values up to 500M
            step = 50
            upper_limit = min(500, max_val * 1.1)
        elif max_val <= 1000:  # For values up to 1B
            step = 100
            upper_limit = min(1000, max_val * 1.1)
        else:
            step = round(max_val / 5, -2)  # Round to nearest hundred
            upper_limit = max_val * 1.1

        return [0, upper_limit], step

    # Get range and step for country axis
    country_range, country_step = get_axis_range_and_step(country_max)

    # Initialize layout dictionary with default settings
    layout_dict = {
        'title': "Financial Analysis",
        'height': 600,
        'xaxis_title': "Year",
        'yaxis': dict(
            title="Country Values" + (" (YoY % Change)" if show_growth_rates else " (In millions of USD)"),
            side="left",
            showgrid=True,
            range=country_range if not show_growth_rates else [-50, 50],  # Use appropriate range for growth rates
            tickformat=',',  # Use comma separator
            dtick=country_step if not show_growth_rates else 10  # Adjust tick spacing for growth rates
        ),
        'showlegend': True,
        'legend': dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        'margin': dict(t=50, l=50, r=120, b=50),  # Increased right margin from 100 to 120 for better label visibility
        'plot_bgcolor': 'white',
        'paper_bgcolor': 'white'
    }

    # Initialize M2 growth variable before using it
    show_m2_growth = False
    if 'show_m2_growth' in st.session_state:
        show_m2_growth = st.session_state.show_m2_growth
        
    # Calculate how many right-side axes we need to display
    right_axes_count = sum([
        show_global,
        show_inflation,
        bool(selected_companies and selected_company_metrics),
        bool('selected_segments' in locals() and selected_segments),
        show_m2_supply and not show_m2_growth  # Only when showing absolute M2 values
    ])
    
    # Adjust axis positions based on the number of right-side axes
    # The more axes we have, the more we need to distribute them
    right_side_spacing = 0.05 if right_axes_count <= 3 else 0.04
    
    # Set the starting position from right edge
    current_position = 1.0
    
    # Add Global axis if needed
    if show_global:
        current_position -= right_side_spacing
        layout_dict['yaxis2'] = dict(
            title="Global Values" + (" (YoY % Change)" if show_growth_rates else " (In millions of USD)"),
            overlaying="y",
            side="right",
            anchor="free",
            position=current_position,
            showgrid=False,
            range=[-50, 50] if show_growth_rates else ([0, global_max * 1.1] if global_max > 0 else None),
            tickformat=',',  # Use comma separator
            titlefont=dict(size=11, color='#2ca02c'),  # Slightly smaller font with color
            tickfont=dict(size=10, color='#2ca02c'),  # Smaller tick font with matching color
            tickmode='auto',
            nticks=6  # Fewer ticks to reduce overlap
        )

    # Add inflation axis if needed
    if show_inflation:
        current_position -= right_side_spacing
        layout_dict['yaxis3'] = dict(
            title="USD Inflation Rate (%)",
            overlaying="y",
            side="right",
            anchor="free",
            position=current_position,
            showgrid=False,
            range=[0, 15],  # Fixed range for inflation percentage
            tickformat='.1f',  # One decimal place
            titlefont=dict(size=11, color='rgba(255, 0, 0, 0.6)'),  # Red-themed for inflation
            tickfont=dict(size=10, color='rgba(255, 0, 0, 0.6)')   # Matching tick color
        )
    
    # Add Company metrics axis if needed
    if selected_companies and selected_company_metrics:
        current_position -= right_side_spacing
        layout_dict['yaxis4'] = dict(
            title="Company Values" + (" (YoY % Change)" if show_growth_rates else " (In millions of USD)"),
            overlaying="y",
            side="right",
            anchor="free",
            position=current_position,
            showgrid=False,
            range=[-50, 50] if show_growth_rates else ([0, company_max * 1.1] if company_max > 0 else None),
            tickformat=',',  # Use comma separator
            titlefont=dict(size=11, color='#1f77b4'),  # Blue color for company metrics
            tickfont=dict(size=10, color='#1f77b4'),  # Matching tick color
            tickmode='auto',
            nticks=6  # Fewer ticks to reduce overlap
        )
        
    # Add dedicated segment axis if needed
    if 'selected_segments' in locals() and selected_segments:
        current_position -= right_side_spacing
        layout_dict['yaxis5'] = dict(
            title="Segment Values" + (" (YoY % Change)" if show_growth_rates else " (In millions of USD)"),
            overlaying="y",
            side="right",
            anchor="free",
            position=current_position,
            showgrid=False,
            range=[-50, 50] if show_growth_rates else ([0, company_max * 1.1] if company_max > 0 else None),
            tickformat=',',  # Use comma separator
            titlefont=dict(size=11, color='#ff7f0e'),  # Orange color for segments
            tickfont=dict(size=10, color='#ff7f0e'),  # Matching tick color
            tickmode='auto',
            nticks=6  # Fewer ticks to reduce overlap
        )

    # Add M2 money supply data if enabled
    if show_m2_supply:
        # Add additional UI controls for M2 supply visualization in a sidebar section
        with st.sidebar.expander("M2 Money Supply Options", expanded=True):
            # Use checkboxes to allow selecting both annual and monthly views simultaneously
            show_annual_m2 = st.checkbox(
                "Show Annual Data",
                value=True,
                key="show_annual_m2",
                help="Display annual M2 supply data as a line"
            )
            
            show_monthly_m2 = st.checkbox(
                "Show Monthly Data",
                value=False,
                key="show_monthly_m2",
                help="Display monthly M2 supply data as bars"
            )
            
            # Independent toggle for M2 growth rates (separate from main metrics growth rate toggle)
            show_m2_growth = st.checkbox(
                "Show M2 Growth Rates",
                value=False,
                help="Display growth rates for M2 data (adds a growth rate line while keeping the M2 supply values visible)",
                key="show_m2_growth"
            )
        
        # Get M2 data directly
        from utils.m2_supply_data import get_m2_annual_data, get_m2_monthly_data
        
        # Flag to track if we need to add M2 axes
        m2_axis_added = False
        max_m2_value = 0
        
        # Get annual data if selected
        if show_annual_m2:
            # Get the annual M2 data and make sure it includes the current year (2025)
            annual_m2_df = get_m2_annual_data(year_range[0], year_range[1])
            if not annual_m2_df.empty:
                # Log the data we have for debugging
                current_year = datetime.now().year
                logging.info(f"M2 annual data years: {annual_m2_df['year'].unique()}")
                if current_year in annual_m2_df['year'].values:
                    logging.info(f"Current year ({current_year}) M2 value: {annual_m2_df[annual_m2_df['year'] == current_year]['value'].iloc[0]}")
                
                if not annual_m2_df.empty:
                    # Add annual line chart
                    fig.add_trace(go.Scatter(
                        x=annual_m2_df['year'],
                        y=annual_m2_df['value'],
                        name='M2 Supply Annual (Billions USD)',
                        line=dict(color='#1f77b4', width=3),
                        mode='lines',
                        yaxis='y6',  # Use yaxis6 to match the layout definition
                        hovertemplate='Year: %{x}<br>M2 Supply: $%{y:,.0f} Billion<br><extra></extra>'
                    ))
                    max_m2_value = max(max_m2_value, max(annual_m2_df['value']))
                    m2_axis_added = True
                    
                    # Store annual growth data for later if needed
                    annual_growth_field = 'annual_growth'
                    annual_x_field = 'year'
        
        # Get monthly data if selected
        if show_monthly_m2:
            monthly_m2_df = get_m2_monthly_data()
            if not monthly_m2_df.empty:
                # For monthly data, we need to filter by year component
                # Handle datetime.date objects which are the most common case
                if hasattr(monthly_m2_df['date'].iloc[0], 'year'):
                    # Filter by year attribute of date objects
                    monthly_m2_df = monthly_m2_df[(monthly_m2_df['date'].apply(lambda x: x.year) >= year_range[0]) & 
                                               (monthly_m2_df['date'].apply(lambda x: x.year) <= year_range[1])]
                    
                    if not monthly_m2_df.empty:
                        # Create a separate bar chart below the main chart for monthly data
                        # We'll keep the original data granularity (monthly)
                        
                        # First, ensure we have proper date objects
                        if not hasattr(monthly_m2_df['date'].iloc[0], 'year'):
                            st.warning("Monthly data dates are not in a proper format")
                        else:
                            # Filter to the selected year range
                            filtered_monthly = monthly_m2_df[(monthly_m2_df['date'].apply(lambda x: x.year) >= year_range[0]) & 
                                                         (monthly_m2_df['date'].apply(lambda x: x.year) <= year_range[1])]
                            
                            # Create custom x-values that are evenly spaced
                            years = range(year_range[0], year_range[1] + 1)
                            
                            # For each year, create background bars to represent the monthly data
                            for year in years:
                                # Get the data for this year
                                year_data = filtered_monthly[filtered_monthly['date'].apply(lambda x: x.year) == year]
                                
                                if not year_data.empty:
                                    # Add bars for each month in this year
                                    for _, row in year_data.iterrows():
                                        # Calculate position - each year gets divided into 12 parts
                                        # Position the bar at year + (month-1)/12 to create evenly spaced monthly bars
                                        month = row['date'].month
                                        x_pos = year + (month - 1) / 12
                                        
                                        # Add a thin bar for this month's value
                                        fig.add_trace(go.Bar(
                                            x=[x_pos],  # Single position for this month
                                            y=[row['value']],
                                            name=f"M2 Supply Monthly",  # Use a single name for all
                                            marker=dict(
                                                color='rgba(31, 119, 180, 0.3)',  # More transparent blue (50%)
                                                line=dict(color='rgba(31, 119, 180, 0.5)', width=0.5)  # Add border for better visibility
                                            ),
                                            width=1/14,  # Make bars thin (less than 1/12 to have gaps)
                                            opacity=0.4,  # Make bars even more transparent (60%)
                                            yaxis='y6',  # Use yaxis6 to match the layout definition
                                            hovertemplate='%{x}<br>M2 Supply: $%{y:,.0f} Billion<br><extra></extra>',
                                            showlegend=False,  # Don't show in legend at all
                                            legendgroup='monthly'  # Group all monthly bars together
                                        ))
                                        
                            # Ensure tick labels show full years without the monthly detail
                            fig.update_xaxes(
                                tickmode='array',
                                tickvals=list(years),
                                ticktext=[str(y) for y in years]
                            )
                        max_m2_value = max(max_m2_value, max(monthly_m2_df['value']))
                        m2_axis_added = True
                        
                        # Store monthly growth data for later if needed
                        monthly_growth_field = 'monthly_growth'
                        monthly_x_field = 'date'
                else:
                    st.warning("Monthly M2 data format is unexpected. Please check the data source.")
        
        # Add M2 y-axis if we added any M2 data
        if m2_axis_added:
            # Add a new y-axis for M2 Supply
            current_position -= right_side_spacing
            layout_dict['yaxis6'] = dict(
                title="M2 Supply (Billions USD)",
                overlaying='y',
                side='right',
                anchor='free',
                position=current_position,
                showgrid=False,
                range=[0, max_m2_value * 1.1],  # Scale based on max value from either dataset
                tickformat=',',
                titlefont=dict(color='#1f77b4', size=11),
                tickfont=dict(color='#1f77b4', size=10),
                nticks=6  # Fewer ticks to reduce overlap
            )
            
            # Optionally add M2 growth rate line when toggle is checked
            if show_m2_growth:
                # Add annual growth rate if we have annual data
                if show_annual_m2 and annual_m2_df is not None and not annual_m2_df.empty:
                    fig.add_trace(go.Scatter(
                        x=annual_m2_df['year'],
                        y=annual_m2_df['annual_growth'],
                        name='M2 Annual Growth Rate (%)',
                        line=dict(color='#9C27B0', width=3),  # Purple color for growth rate
                        mode='lines',
                        yaxis='y7'  # Use a dedicated axis (y7) for M2 growth rate
                    ))
                
                # Add monthly growth rate if we have monthly data (keeping monthly granularity)
                if show_monthly_m2 and monthly_m2_df is not None and not monthly_m2_df.empty:
                    # Filter to the selected year range
                    filtered_monthly = monthly_m2_df[(monthly_m2_df['date'].apply(lambda x: x.year) >= year_range[0]) & 
                                                 (monthly_m2_df['date'].apply(lambda x: x.year) <= year_range[1])]
                    
                    # For each year, add the monthly growth rates
                    for year in range(year_range[0], year_range[1] + 1):
                        # Get data for this year
                        year_data = filtered_monthly[filtered_monthly['date'].apply(lambda x: x.year) == year]
                        
                        if not year_data.empty:
                            # Create arrays to store points for connecting lines
                            x_positions = []
                            growth_values = []
                            
                            # Process each month
                            for _, row in year_data.iterrows():
                                month = row['date'].month
                                x_pos = year + (month - 1) / 12
                                x_positions.append(x_pos)
                                growth_values.append(row['monthly_growth'])
                            
                            # Add a line for this year's monthly growth rates
                            fig.add_trace(go.Scatter(
                                x=x_positions,
                                y=growth_values,
                                name=f"M2 Monthly Growth Rate",  # Use a single name for all years
                                line=dict(color='rgba(224, 64, 251, 0.5)', width=1),  # More transparent purple
                                mode='lines',  # Remove markers to reduce clutter
                                marker=dict(size=2, opacity=0.4),  # Smaller, more transparent markers
                                yaxis='y7',  # Use same dedicated axis for growth rates
                                legendgroup='monthly_growth',  # Group all monthly growth lines together
                                showlegend=year==year_range[0]  # Only show in legend for first year
                            ))
                
                # Add the dedicated y7 axis for M2 growth rate
                current_position -= right_side_spacing
                layout_dict['yaxis7'] = dict(
                    title="M2 Growth Rate (%)",
                    overlaying='y',
                    side='right',
                    anchor='free',
                    position=current_position,
                    showgrid=False,
                    range=[-5, 25],  # Fixed range for growth percentage
                    tickformat='.1f',  # One decimal place
                    titlefont=dict(size=11, color='#9C27B0'),  # Match color to the purple M2 growth line
                    tickfont=dict(size=10, color='#9C27B0'),
                    nticks=6  # Fewer ticks to reduce overlap
                )
            
            # Add explanatory text as separate elements for better rendering
            st.markdown("""
            <div style="background-color: #f0f7fc; padding: 15px; border-radius: 5px; margin-top: 20px; border-left: 4px solid #0366d6;">
                <h4 style="margin-top: 0; color: #0366d6;">About M2 Money Supply</h4>
                <p style="margin-bottom: 0; font-size: 0.9rem;">M2 is a measure of the U.S. money supply that includes cash, checking deposits, 
                savings deposits, money market securities, and other time deposits. It is an important economic indicator that reflects the amount of money in circulation 
                and can impact inflation, interest rates, and overall economic growth.</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Add key events as a separate markdown element
            st.markdown("<h5 style='color: #0366d6;'>Key Events Affecting M2 Money Supply</h5>", unsafe_allow_html=True)
            
            # Add events as bullet points
            st.markdown("""
            • **2008-2009:** Financial crisis and QE1 (Quantitative Easing)
            • **2010-2011:** QE2 - Fed purchased Treasury securities
            • **2012-2014:** QE3 - Further expansion
            • **2020-2021:** COVID-19 pandemic stimulus - Major expansion
            • **2022-Present:** Quantitative tightening
            """)
        else:
            st.warning("M2 supply data is not available. Please ensure the data has been imported into the database.")



    fig.update_layout(**layout_dict)

    # Update hover templates for country traces
    for trace in fig.data:
        if trace.yaxis == 'y':  # Only update country traces
            # Add YoY growth data to hover template
            # Get the country/region name from trace
            country_name = trace.name
            
            # Get data for this country to calculate YoY growth
            # Use the loaded advertising data if available
            try:
                if 'df' in locals() and df is not None and not df.empty:
                    country_data = df[df['country'] == country_name]
                else:
                    continue  # Skip if no data available
            except NameError:
                continue  # Skip if df is not defined
            
            if not country_data.empty:
                # Sort data by year
                country_data = country_data.sort_values('year')
                
                # Calculate YoY growth percentages
                values = country_data['value'].tolist()
                years = country_data['year'].tolist()
                
                # Initialize growth list
                yoy_growth = ['N/A']  # First year has no YoY growth
                
                # Calculate for subsequent years
                for i in range(1, len(values)):
                    if values[i-1] != 0:
                        growth_pct = ((values[i] - values[i-1]) / values[i-1]) * 100
                        yoy_growth.append(f"{growth_pct:.1f}%")
                    else:
                        yoy_growth.append('N/A')
                
                # Assign years and growth values as custom data
                trace.customdata = list(zip(years, yoy_growth))
                
                # Update hover template to include YoY growth
                trace.hovertemplate = (
                    "<b>%{data.name}</b><br>" +
                    "Year: %{x}<br>" +
                    "Value: %{y:.1f} Million USD<br>" +
                    "YoY Growth: %{customdata[1]}<br>" +
                    "<extra></extra>"
                )
            else:
                # Default hover template without YoY growth
                trace.hovertemplate = (
                    "<b>%{data.name}</b><br>" +
                    "Year: %{x}<br>" +
                    "Value: %{y:.1f} Million USD<br>" +
                    "<extra></extra>"
                )

    # Add chart zoom effect if not already added
    if not hasattr(st.session_state, 'genie_chart_css_added'):
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
        st.session_state.genie_chart_css_added = True
    
    # Display the plot with zoom effect
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Optional: subscribers/users chart (sheet-backed, no hard-coded data)
    if 'show_subscribers' in locals() and show_subscribers and st.session_state.get("selected_services"):
        st.subheader("👥 Subscribers / Users (Annualized)")
        sub_proc = get_subscriber_processor()
        sub_fig = go.Figure()

        for service in st.session_state.get("selected_services", []):
            svc_data = sub_proc.get_service_data(service, metric_type="subscribers")
            df_svc = (svc_data.get("data") if svc_data else None)
            if df_svc is None or df_svc.empty:
                continue

            df_svc = df_svc.copy()
            # Quarter is stored as a string like "Q1 2020"
            q = df_svc["Quarter"].astype(str).str.strip()
            year = pd.to_numeric(q.str.extract(r"(\\d{4})")[0], errors="coerce")
            qn = pd.to_numeric(q.str.extract(r"Q(\\d)")[0], errors="coerce")
            df_svc["year"] = year.astype("Int64")
            df_svc["quarter_num"] = qn.astype("Int64")
            df_svc = df_svc.dropna(subset=["year", "quarter_num", "Subscribers"])

            # Last reported quarter in each year (year-end proxy)
            annual = (
                df_svc.sort_values(["year", "quarter_num"])
                .groupby("year", as_index=False)
                .tail(1)
                .sort_values("year")
            )

            annual = annual[(annual["year"] >= year_range[0]) & (annual["year"] <= year_range[1])]
            if annual.empty:
                continue

            sub_fig.add_trace(
                go.Scatter(
                    x=annual["year"].astype(int),
                    y=annual["Subscribers"].astype(float),
                    mode="lines+markers",
                    name=service,
                    hovertemplate="<b>%{data.name}</b><br>Year: %{x}<br>Value: %{y:,.1f}<extra></extra>",
                )
            )

        if sub_fig.data:
            sub_fig.update_layout(
                height=360,
                margin=dict(t=30, l=40, r=20, b=40),
                xaxis=dict(title="Year"),
                yaxis=dict(title="Subscribers / Users"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            st.plotly_chart(sub_fig, use_container_width=True)
        else:
            st.info("No subscriber/user data found in the selected year range.")
    
# Insights section has been removed from the top and will only appear below the chart

# No need to close any flex container here as we're not using one

# Original Key Insights Section below the chart
st.subheader("🔍 Detailed Insights")
st.markdown("""
<style>
.insight-box {
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    border-left: 4px solid #ccc;
    background-color: white;
    border-radius: 6px;
    padding: 15px;
    margin-bottom: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.insight-box:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}
.insight-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
    margin-top: 12px;
}
.macro-insight-box {
    border-left: 4px solid #4b8bfe;
    background-color: #f7f9ff;
    border-radius: 6px;
    padding: 15px;
    margin-bottom: 16px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.pp-adjusted-box {
    border-left: 4px solid #35a853;
    background-color: #f0f9f0;
    border-radius: 6px;
    padding: 15px;
    margin-bottom: 16px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.cagr-value {
    font-weight: bold;
    color: #1a73e8;
}
.macro-title {
    font-size: 1.1rem;
    font-weight: bold;
    margin-bottom: 8px;
    color: #555;
}
</style>
<div style="margin-bottom: 8px; font-size: 0.85rem; color: #666;">
<i>Note: Insight boxes are color-coded to match their corresponding chart elements</i>
</div>
""", unsafe_allow_html=True)
insights_placeholder = st.empty()

# Initialize insights list
insights = []
macro_insights = []

# Get the latest year from the year range for insights
latest_year = year_range[1] if 'year_range' in locals() else 2024
earliest_year = year_range[0] if 'year_range' in locals() else 2010

# Calculate the year span for CAGR calculations
year_span = latest_year - earliest_year

# Generate detailed insights (combine all selections into a single insights list)
if selected_companies:
    # Generate insights for company metrics if available
    if selected_company_metrics:
        for company in selected_companies:
            for metric_name in selected_company_metrics:
                metric_key = available_metrics[metric_name]
                try:
                    # Get current year value
                    current_metrics = get_cached_metrics(company, latest_year)
                    if current_metrics and metric_key in current_metrics:
                        current_value = current_metrics[metric_key]
                        
                        # Get previous year value for calculating percentage change
                        prev_metrics = get_cached_metrics(company, latest_year - 1)
                        prev_value = prev_metrics.get(metric_key) if prev_metrics else None
                        
                        percentage_change = None
                        if prev_value and current_value:
                            percentage_change = ((current_value - prev_value) / prev_value * 100)
                        
                        # Generate insight
                        insight = get_company_insight(company, latest_year, metric_name, current_value, percentage_change)
                        if insight:
                            insights.append(insight)
                except Exception as e:
                    logging.error(f"Error generating insight for {company} {metric_name}: {str(e)}")

    # Generate insights for segments if available
    # Use the selected_segments variable defined above
    if 'selected_segments' in locals() and selected_segments:
        for company, segment_name in selected_segments:
            try:
                # Get current year segment value
                current_segments = get_cached_segments(company, latest_year)
                if current_segments and 'labels' in current_segments and segment_name in current_segments['labels']:
                    idx = current_segments['labels'].index(segment_name)
                    current_value = current_segments['values'][idx]
                    
                    # Get previous year segment value
                    prev_segments = get_cached_segments(company, latest_year - 1)
                    prev_value = None
                    if prev_segments and 'labels' in prev_segments and segment_name in prev_segments['labels']:
                        prev_idx = prev_segments['labels'].index(segment_name)
                        prev_value = prev_segments['values'][prev_idx]
                    
                    percentage_change = None
                    if prev_value is not None and current_value is not None and prev_value != 0:
                        percentage_change = ((current_value - prev_value) / prev_value * 100)
                    
                    # Generate segment insight
                    segment_insight = f"**{company}'s {segment_name} segment** generated "
                    segment_insight += f"{format_large_number(current_value)} in revenue for {latest_year}"
                    
                    if percentage_change is not None:
                        direction = "up" if percentage_change > 0 else "down"
                        segment_insight += f", {direction} {abs(percentage_change):.1f}% from {latest_year-1}"
                    
                    insights.append(segment_insight)
            except Exception as e:
                logging.error(f"Error generating segment insight for {company} {segment_name}: {str(e)}")

# Add CAGR insight if we have data for the full range
if 'selected_companies' in locals() and selected_companies:
    for company in selected_companies:
        if 'selected_company_metrics' in locals() and selected_company_metrics:
            for metric_name in selected_company_metrics:
                metric_key = available_metrics[metric_name]
                try:
                    # Get current year value
                    current_metrics = get_cached_metrics(company, latest_year)
                    if current_metrics and metric_key in current_metrics:
                        current_value = current_metrics[metric_key]
                        start_year = year_range[0]
                        if start_year < latest_year:
                            start_metrics = get_cached_metrics(company, start_year)
                            if start_metrics and metric_key in start_metrics:
                                start_value = start_metrics[metric_key]
                                if start_value and start_value > 0:
                                    num_years = latest_year - start_year
                                    cagr_insight = get_cagr_insight(
                                        f"{company}'s {metric_name}",
                                        start_year,
                                        latest_year,
                                        start_value,
                                        current_value
                                    )
                                    insights.append(cagr_insight)
                except Exception as e:
                    logging.error(f"Error generating insight for {company} {metric_name}: {e}")

# Generate insights for ad spend metrics if available
if 'selected_metrics' in locals() and selected_metrics and 'all_selected_countries' in locals() and all_selected_countries:
    try:
        # Include data from start_year for CAGR calculation
        start_year = year_range[0]
        df = load_cached_advertising_data(
            tuple(all_selected_countries),
            tuple(selected_metrics),
            start_year,  # Include start year for CAGR calculation
            latest_year
        )
        
        if df is not None and not df.empty:
            for country in selected_countries:  # Use regular countries, not global
                # Process all selected metrics
                for metric in selected_metrics:
                    # Get current year data
                    current_data = df[(df['country'] == country) & 
                                     (df['metric_type'] == metric) &
                                     (df['year'] == latest_year)]
                    
                    if not current_data.empty:
                        current_value = current_data['value'].iloc[0]
                        
                        # Get previous year data
                        prev_data = df[(df['country'] == country) & 
                                      (df['metric_type'] == metric) &
                                      (df['year'] == latest_year - 1)]
                        
                        prev_value = prev_data['value'].iloc[0] if not prev_data.empty else None
                        percentage_change = ((current_value - prev_value) / prev_value * 100) if prev_value and prev_value != 0 else None
                        
                        from utils.insights import get_ad_spend_insight
                        insight = get_ad_spend_insight(country, metric, latest_year, current_value, percentage_change)
                        if insight:
                            insights.append(insight)
                        
                        # Add CAGR insight for ad spend metrics
                        if start_year < latest_year:
                            # Get start year data directly from our already loaded dataframe
                            start_data = df[(df['country'] == country) & 
                                          (df['metric_type'] == metric) &
                                          (df['year'] == start_year)]
                            
                            if not start_data.empty:
                                start_value = start_data['value'].iloc[0]
                                if start_value and start_value > 0:
                                    num_years = latest_year - start_year
                                    cagr_insight = get_cagr_insight(
                                        f"{country}'s {metric} ad spend",
                                        start_year,
                                        latest_year,
                                        start_value,
                                        current_value
                                    )
                                    insights.append(cagr_insight)
    except Exception as e:
        logging.error(f"Error generating ad spend insights: {e}")

# Generate combined insights if we have both company and ad spend data
if ('selected_companies' in locals() and selected_companies and 
    'selected_company_metrics' in locals() and selected_company_metrics and 
    'selected_metrics' in locals() and selected_metrics and 
    'all_selected_countries' in locals() and all_selected_countries):
    try:
        from utils.insights import get_combined_insight
        
        # Loop through all selected companies
        for company in selected_companies:
            # Use the first metric for simplicity (can be expanded to use multiple)
            metric_name = selected_company_metrics[0]
            metric_key = available_metrics[metric_name]
            company_metrics = get_cached_metrics(company, latest_year)
            
            if company_metrics and metric_key in company_metrics:
                company_value = company_metrics[metric_key]
                
                # Get an ad spend metric
                country = selected_countries[0]
                ad_metric = selected_metrics[0]
                
                df = load_cached_advertising_data(
                    tuple([country]),
                    tuple([ad_metric]),
                    latest_year,
                    latest_year
                )
                
                if df is not None and not df.empty:
                    ad_data = df[(df['country'] == country) & 
                                (df['metric_type'] == ad_metric) &
                                (df['year'] == latest_year)]
                    
                    if not ad_data.empty:
                        ad_value = ad_data['value'].iloc[0]
                        
                        # Create data dictionaries for combined insight
                        company_data = {
                            "company": company,
                            "metric": metric_name,
                            "value": company_value,
                            "year": latest_year
                        }
                        
                        ad_spend_data = {
                            "country": country,
                            "metric": ad_metric,
                            "value": ad_value,
                            "year": latest_year
                        }
                        
                        combined_insight = get_combined_insight(company_data, ad_spend_data)
                        if combined_insight:
                            insights.append(combined_insight)
    except Exception as e:
        logging.error(f"Error generating combined insights: {e}")

# Generate M2 Supply and purchasing power macroeconomic insights
if 'show_m2_supply' in locals() and show_m2_supply:
    try:
        # Get M2 Supply data for the full time range
        from utils.m2_supply_data import get_m2_annual_data
        m2_data = get_m2_annual_data(earliest_year, latest_year)
        
        if not m2_data.empty:
            # Get start and end values
            start_m2 = m2_data[m2_data['year'] == earliest_year]['value'].iloc[0] if not m2_data[m2_data['year'] == earliest_year].empty else None
            end_m2 = m2_data[m2_data['year'] == latest_year]['value'].iloc[0] if not m2_data[m2_data['year'] == latest_year].empty else None
            
            if start_m2 is not None and end_m2 is not None:
                # Calculate CAGR for M2 Supply
                from utils.insights import calculate_cagr
                m2_cagr = calculate_cagr(start_m2, end_m2, year_span)
                
                # Format values for display
                start_m2_formatted = f"${start_m2/1000:.1f}T" if start_m2 >= 1_000_000 else f"${start_m2:.0f}B"
                end_m2_formatted = f"${end_m2/1000:.1f}T" if end_m2 >= 1_000_000 else f"${end_m2:.0f}B"
                
                # Create M2 Supply insight
                m2_insight = f"""
                <div class='macro-title'>M2 Money Supply Analysis ({earliest_year}-{latest_year})</div>
                <p>The M2 money supply grew from {start_m2_formatted} in {earliest_year} to {end_m2_formatted} in {latest_year}, 
                representing a <span class='cagr-value'>{m2_cagr:.1f}%</span> compound annual growth rate (CAGR).</p>
                <p>This expansion in the money supply provides important macroeconomic context for understanding the financial performance 
                of companies during this period, as it impacts inflation, purchasing power, and overall economic activity.</p>
                """
                macro_insights.append(m2_insight)
    except Exception as e:
        logging.error(f"Error generating M2 Supply insights: {e}")

# We've removed the redundant purchasing power adjustment analysis box
# as it's been replaced by the more comprehensive inflation analysis below

# Generate detailed inflation analysis insights using the new inflation_calculator
if 'adjust_purchasing_power' in locals() and adjust_purchasing_power and selected_companies and selected_company_metrics:
    try:
        # Create a dropdown for selecting the base year for inflation analysis
        with st.expander("🔎 **Detailed Inflation Analysis Settings**", expanded=False):
            base_year = add_inflation_selector(key_prefix="genie")
            st.info("Adjusts all selected company metrics to account for inflation using CPI data, with detailed breakdowns of purchasing power loss and real growth/decline values.")
            
        # Create the data structure needed for the inflation calculator
        company_metrics_data = []
        
        for company in selected_companies:
            for metric_name in selected_company_metrics:
                metric_key = available_metrics[metric_name]
                for year in year_range:
                    metrics = get_cached_metrics(company, year)
                    if metrics and metric_key in metrics:
                        company_metrics_data.append({
                            'company': company,
                            'metric': metric_name,
                            'year': year,
                            'value': metrics[metric_key]
                        })
        
        # Convert to DataFrame
        if company_metrics_data:
            df = pd.DataFrame(company_metrics_data)
            
            # Generate the inflation analysis box using the utility function
            inflation_analysis_html = create_inflation_analysis_box(
                df, 
                selected_metrics=selected_company_metrics,
                selected_companies=selected_companies,
                is_global_view=False,
                base_year=base_year
            )
            
            # Add to macro insights
            macro_insights.append(inflation_analysis_html)
    except Exception as e:
        logging.error(f"Error generating detailed inflation analysis: {e}")
        st.error(f"Could not generate inflation analysis: {e}")

# Display insights (up to 10 - increased to accommodate multiple companies)
if insights:
    max_insights = min(10, len(insights))
    insights_html = "<div class='insight-grid'>"
    for i in range(max_insights):
        # Determine which category this insight belongs to
        category_class = "other"  # Default category
        insight_text = insights[i].lower()
        
        if "content" in insight_text or "streaming" in insight_text or "subscriber" in insight_text:
            category_class = "content"
        elif "dtc" in insight_text or "direct-to-consumer" in insight_text:
            category_class = "dtc"
        elif "revenue" in insight_text or "income" in insight_text or "financial" in insight_text:
            category_class = "financials"
        elif "segment" in insight_text:
            category_class = "segment"
        elif "ad spend" in insight_text or "advertising" in insight_text:
            category_class = "adspend"
        
        # Determine if there's a specific color for this insight
        custom_style = ""
        if 'color_mapping' in st.session_state:
            for key, color in st.session_state.color_mapping.items():
                # Check if this trace name appears in the insight
                if key in insights[i]:
                    custom_style = f"border-left-color: {color}; border-left-width: 4px; box-shadow: 0 3px 6px rgba({color.replace('rgb(', '').replace(')', '')}, 0.2);"
                    break
                
                # Also check for company name and metric/segment name matches
                if " - " in key:
                    parts = key.split(" - ")
                    company_name = parts[0]
                    metric_segment_name = parts[1].split(" ")[0]  # Get just the name part before "(Metric)" or "(Segment)"
                    
                    if company_name in insights[i] and metric_segment_name in insights[i]:
                        custom_style = f"border-left-color: {color}; border-left-width: 4px; box-shadow: 0 3px 6px rgba({color.replace('rgb(', '').replace(')', '')}, 0.2);"
                        break
                    
                # Try to match Global data insights
                if "Global" in key and "Global" in insights[i]:
                    metric_name = key.split(" - ")[1]
                    if metric_name in insights[i]:
                        custom_style = f"border-left-color: {color}; border-left-width: 4px; box-shadow: 0 3px 6px rgba({color.replace('rgb(', '').replace(')', '')}, 0.2);"
                        break
        
        # Add custom color styling if found            
        if custom_style:
            insights_html += f"<div class='insight-box {category_class}' style='{custom_style}'>{insights[i]}</div>"
        else:
            insights_html += f"<div class='insight-box {category_class}'>{insights[i]}</div>"
    
    insights_html += "</div>"
    
    # Add macroeconomic insights if available
    if macro_insights:
        insights_html += "<div style='margin-top: 30px;'>"
        for macro_insight in macro_insights:
            insights_html += f"<div class='macro-insight-box'>{macro_insight}</div>"
        insights_html += "</div>"
    
    insights_placeholder.markdown(insights_html, unsafe_allow_html=True)
else:
    insights_placeholder.info("Select companies and metrics to generate insights.")

    # Add recession periods explanation if shown
    if show_recessions and recession_df is not None:
        with st.expander("📉 About Recession Periods"):
            st.info("Recession shading is currently disabled because the app no longer ships hard-coded recession periods. Add a dedicated recession/events sheet to enable this feature.")

# Add the new Enhanced Chat Interface section
st.markdown("<hr style='margin: 2.5rem 0 1.5rem 0;'>", unsafe_allow_html=True)
render_enhanced_chat_interface()
st.markdown("<hr style='margin: 2.5rem 0 1.5rem 0;'>", unsafe_allow_html=True)

# Show helper message if no data is selected
if not selected_companies and not selected_metrics:
    st.info("Select metrics, companies, or enable global data to view the analysis.")


try:
    # Update AI context
    dashboard_state = {
        'page': 'Genie',
        'selected_companies': selected_companies,
        'selected_countries': all_selected_countries,
        'metric_selection_mode': metric_selection_mode,
        'selected_metrics': selected_detailed_metrics,
        'selected_company_metrics': selected_company_metrics if 'selected_company_metrics' in locals() else [],
        'year_range': f"{year_range[0]}-{year_range[1]}" if 'year_range' in locals() else "unknown"
    }

    # AI Assistant disabled for now

except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    st.stop()
