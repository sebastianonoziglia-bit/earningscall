"""
This module contains all the custom CSS styles for the application.
These styles can be loaded by any page to ensure consistent styling.
"""
import streamlit as st
import textwrap
import plotly.graph_objects as go
import plotly.io as pio

PLOTLY_TEMPLATE_NAME = "mfe_blue"
PLOTLY_HOVERLABEL_STYLE = dict(
    bgcolor="rgba(255, 255, 255, 0.98)",
    bordercolor="rgba(0, 115, 255, 0.35)",
    font=dict(
        family='"Poppins", system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif',
        size=12,
        color="#0f172a",
    ),
    align="left",
    namelength=-1,
)

def apply_plotly_theme():
    if "plotly_white" in pio.templates:
        base_template = go.layout.Template(pio.templates["plotly_white"])
    else:
        base_template = go.layout.Template()
    base_template.layout.update(
        hoverlabel=PLOTLY_HOVERLABEL_STYLE,
        font=dict(
            family='"Poppins", system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif'
        ),
    )
    pio.templates[PLOTLY_TEMPLATE_NAME] = base_template
    pio.templates.default = PLOTLY_TEMPLATE_NAME

apply_plotly_theme()

def load_common_styles():
    """
    Load common CSS styles for the application.
    This should be called at the top of each page.
    """
    st.markdown(textwrap.dedent("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800&display=swap');
	    :root {
	        --app-font: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            --chart-font: "Poppins", var(--app-font);
	        --brand-blue: #0073ff;
	    }

		    html, body, p, div, h1, h2, h3, h4, h5, h6, li, span, button, input, select,
		    textarea, a, label, option, .stApp {
		        font-family: var(--app-font) !important;
		        letter-spacing: 0 !important;
		    }

		    h1, h2, h3, h4, h5, h6,
		    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6,
		    [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
		    [data-testid="stMarkdownContainer"] h3, [data-testid="stMarkdownContainer"] h4,
		    [data-testid="stMarkdownContainer"] h5, [data-testid="stMarkdownContainer"] h6 {
		        letter-spacing: 0 !important;
		        line-height: 1.12;
		    }

		    [data-testid="stMarkdownContainer"] p,
		    [data-testid="stMarkdownContainer"] li {
		        letter-spacing: 0 !important;
		        line-height: 1.38;
		    }

		    [data-testid="stMarkdownContainer"] p { margin: 0.35rem 0 0.55rem 0; }
		    [data-testid="stMarkdownContainer"] ul,
		    [data-testid="stMarkdownContainer"] ol { margin: 0.35rem 0 0.6rem 1.1rem; }
		    [data-testid="stMarkdownContainer"] li { margin: 0.2rem 0; }
		    [data-testid="stMarkdownContainer"] h2 { margin: 0.75rem 0 0.5rem 0; }
		    [data-testid="stMarkdownContainer"] h3 { margin: 0.7rem 0 0.45rem 0; }
		    [data-testid="stMarkdownContainer"] h4,
		    [data-testid="stMarkdownContainer"] h5,
		    [data-testid="stMarkdownContainer"] h6 { margin: 0.65rem 0 0.4rem 0; }

	    section[data-testid="stSidebar"] *,
	    [data-testid="stSidebarNav"] * {
	        font-family: var(--app-font) !important;
	    }

    section[data-testid="stSidebar"] {
        resize: horizontal;
        overflow: auto;
        min-width: 220px;
        max-width: 420px;
        flex: 0 0 auto;
    }

    h1 {
        color: #0073ff !important;
    }

	    .js-plotly-plot .hoverlayer .hovertext rect {
	        rx: 12px;
	        ry: 12px;
	        filter: drop-shadow(0 10px 22px rgba(15, 23, 42, 0.18));
	    }

	    .js-plotly-plot .hoverlayer .hovertext {
	        filter: drop-shadow(0 12px 24px rgba(15, 23, 42, 0.18));
	    }

        /* Modern Plotly typography */
        .js-plotly-plot, .js-plotly-plot * {
            font-family: var(--chart-font) !important;
        }
		    .js-plotly-plot .gtitle text,
		    .js-plotly-plot .barlayer .text text,
		    .js-plotly-plot .treemaplayer text {
		        font-weight: 800 !important;
		        letter-spacing: 0 !important;
		    }
        .js-plotly-plot .xtick text,
        .js-plotly-plot .ytick text,
        .js-plotly-plot .legend text {
            font-weight: 600 !important;
        }

        /* Rounded-looking bars (simulate corner radius via thick stroke + round joins) */
        .js-plotly-plot .barlayer .bars path {
            stroke-linejoin: round;
            stroke-linecap: round;
        }

    /* Slider styling */
    .stSlider [data-baseweb="slider"] > div {
        background-color: transparent !important;
    }

    .stSlider [data-baseweb="slider"] > div > div {
        background-color: transparent !important;
    }

    .stSlider [data-baseweb="slider"] div[role="slider"] {
        background-color: #ffffff !important;
        border-color: #0073ff !important;
        box-shadow: 0 0 0 2px rgba(17, 24, 39, 0.08) !important;
    }

    /* Select and multiselect styling */
    div[data-baseweb="select"] > div {
        border-color: #d1d5db !important;
    }

    div[data-baseweb="select"] > div:focus-within {
        border-color: #0073ff !important;
        box-shadow: 0 0 0 1px rgba(0, 115, 255, 0.25) !important;
    }

    .stMultiSelect [data-baseweb="tag"] {
        background-color: #f3f4f6 !important;
        color: #111827 !important;
        border: 1px solid rgba(0, 115, 255, 0.45) !important;
    }

    input[type="checkbox"], input[type="radio"] {
        accent-color: #0073ff !important;
    }

    label[data-baseweb="radio"] input:checked + div {
        border-color: #0073ff !important;
        background-color: #ffffff !important;
    }

    /* Main layout styles */
    .main-container {
        padding: 10px;
    }
    
    /* Section styles */
    .section-container {
        background-color: #fff;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    
    .section-title {
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 15px;
        color: #262730;
        border-bottom: 1px solid #f0f0f0;
        padding-bottom: 8px;
    }
    
    /* Insight box styles */
    .insights-content {
        background-color: #f9f9fa;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 15px;
    }
    
    .insights-container {
        max-height: 500px;
        overflow-y: auto;
        border: 1px solid #eee;
        border-radius: 5px;
        padding: 10px;
        background-color: white;
        margin-bottom: 10px;
    }
    
    .insights-container::-webkit-scrollbar {
        width: 5px;
    }
    
    .insights-container::-webkit-scrollbar-track {
        background: #f1f1f1;
    }
    
    .insights-container::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 5px;
    }
    
    .insights-container::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
    
    .insight-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 15px;
    }
    
    .insight-box {
        background-color: white;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #4CAF50;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .insight-box:hover {
        transform: translateY(-3px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    .insight-box h4 {
        margin-top: 0;
        margin-bottom: 10px;
        font-size: 1rem;
        color: #333;
    }
    
    .insight-box p {
        margin: 0;
        font-size: 0.9rem;
        line-height: 1.4;
        color: #555;
    }
    
    .insight-box ul {
        margin-top: 8px;
        margin-bottom: 0;
        padding-left: 20px;
    }
    
    .insight-box li {
        margin-bottom: 5px;
        line-height: 1.4;
    }
    
    /* Category specific insight boxes */
    .insight-box.content {
        border-left-color: #4285F4; /* Google Blue */
    }
    
    .insight-box.dtc {
        border-left-color: #EA4335; /* Google Red */
    }
    
    .insight-box.financials {
        border-left-color: #FBBC05; /* Google Yellow */
    }
    
    .insight-box.segment {
        border-left-color: #34A853; /* Google Green */
    }
    
    .insight-box.other {
        border-left-color: #7B68EE; /* Medium Slate Blue */
    }
    
    /* Growth indicator styles */
    .growth-indicator {
        display: inline-flex;
        align-items: center;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-left: 5px;
        transition: background-color 0.3s ease;
    }
    
    .growth-positive {
        background-color: rgba(52, 168, 83, 0.15);
        color: #34A853;
    }
    
    .growth-negative {
        background-color: rgba(234, 67, 53, 0.15);
        color: #EA4335;
    }
    
    .growth-neutral {
        background-color: rgba(251, 188, 5, 0.15);
        color: #FBBC05;
    }
    
    /* Animation styles */
    .animate-bar {
        transition: width 0.8s ease-in-out;
    }
    
    .animate-number {
        transition: all 0.8s ease-in-out;
    }
    
    /* Company logo styles */
    .company-logo {
        width: 24px;
        height: 24px;
        margin-right: 5px;
        vertical-align: middle;
    }
    
    /* Responsive adjustments */
    @media (max-width: 1200px) {
        .insight-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    
    @media (max-width: 768px) {
        .insight-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """), unsafe_allow_html=True)

def load_genie_specific_styles():
    """
    Load styles specific to the Genie page.
    """
    st.markdown(textwrap.dedent("""
    <style>
    /* Metrics and Segments Visualization Styles */
    .metrics-segments-legend {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
        border-left: 5px solid #4CAF50;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    .legend-title {
        margin-top: 0;
        margin-bottom: 10px;
        color: #333;
        font-size: 1.1rem;
    }
    
    .legend-container {
        display: flex;
        margin-bottom: 10px;
    }
    
    .legend-item {
        flex: 1;
        padding-right: 15px;
    }
    
    .legend-item:not(:first-child) {
        padding-left: 15px;
        border-left: 1px solid #ddd;
    }
    
    .legend-item-title {
        font-size: 0.9rem;
        margin-bottom: 8px;
        font-weight: bold;
    }
    
    .legend-item-icon {
        display: flex;
        align-items: center;
    }
    
    .legend-line-solid {
        width: 30px;
        height: 3px;
        background-color: #1f77b4;
        margin-right: 8px;
    }
    
    .legend-line-dashed {
        width: 30px;
        height: 0px;
        border-top: 2px dashed #ff7f0e;
        margin-right: 8px;
    }
    
    .legend-item-description {
        font-size: 0.85rem;
        margin-top: 5px;
        color: #555;
    }
    
    .legend-footer {
        margin: 0;
        font-size: 0.9rem;
        border-top: 1px solid #eee;
        padding-top: 10px;
    }
    
    /* Enhanced Insight Grid and Boxes */
    .insight-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 15px;
        margin-top: 15px;
    }
    
    .insight-box {
        background-color: #f9f9f9;
        border-left: 3px solid #4CAF50;
        padding: 10px 15px;
        margin-bottom: 10px;
        border-radius: 3px;
        font-size: 14px;
        opacity: 1.0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .insight-box:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    /* Category specific insight boxes */
    .insight-box.content {
        border-left-color: #4285F4; /* Google Blue */
    }
    
    .insight-box.dtc {
        border-left-color: #EA4335; /* Google Red */
    }
    
    .insight-box.financials {
        border-left-color: #FBBC05; /* Google Yellow */
    }
    
    .insight-box.segment {
        border-left-color: #34A853; /* Google Green */
    }
    
    .insight-box.other {
        border-left-color: #7B68EE; /* Medium Slate Blue */
    }
    
    /* Responsive adjustments */
    @media (max-width: 1200px) {
        .insight-grid {
            grid-template-columns: repeat(2, 1fr);
        }
        
        .legend-container {
            flex-direction: column;
        }
        
        .legend-item:not(:first-child) {
            padding-left: 0;
            padding-top: 10px;
            border-left: none;
            border-top: 1px solid #ddd;
        }
    }
    
    @media (max-width: 768px) {
        .insight-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """), unsafe_allow_html=True)

def load_earnings_specific_styles():
    """
    Load styles specific to the Earnings page.
    """
    st.markdown(textwrap.dedent("""
    <style>
    /* Company Selector Styles */
    .company-selector {
        padding: 10px;
        background-color: #f5f7f9;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    
    .company-option {
        cursor: pointer;
        padding: 8px 12px;
        border-radius: 6px;
        transition: background-color 0.2s;
        display: flex;
        align-items: center;
    }
    
    .company-option:hover {
        background-color: #e6e9ed;
    }
    
    .company-option.selected {
        background-color: #f3f4f6;
        border-left: 3px solid #0073ff;
    }
    
    /* Segment Visualization Styles */
    .segment-circle {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }
    
    .segment-row {
        display: flex;
        align-items: center;
        margin-bottom: 6px;
        padding: 5px;
        border-radius: 4px;
        transition: background-color 0.2s;
    }
    
    .segment-row:hover {
        background-color: #f0f0f0;
    }
    
    .segment-value {
        margin-left: auto;
        font-weight: 600;
    }
    
    /* Year Navigation */
    .year-nav {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 15px;
    }
    
    .year-btn {
        background-color: #f0f2f5;
        border: none;
        padding: 5px 15px;
        border-radius: 20px;
        margin: 0 5px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .year-btn:hover {
        background-color: #e1e5eb;
    }
    
    .year-btn.active {
        background-color: #f3f4f6;
        border: 1px solid #0073ff;
        color: #111827;
    }
    
    .year-nav-arrow {
        cursor: pointer;
        padding: 5px 10px;
        color: #555;
        font-size: 1.2rem;
    }
    
    .year-nav-arrow:hover {
        color: #374151;
    }
    </style>
    """), unsafe_allow_html=True)

def load_overview_specific_styles():
    """
    Load styles specific to the Overview page.
    """
    st.markdown(textwrap.dedent("""
    <style>
    /* Bar chart animations */
    .bar-chart-container {
        margin-top: 20px;
    }
    
    .bar-row {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
    }
    
    .bar-label {
        width: 120px;
        font-size: 0.9rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .bar-container {
        flex-grow: 1;
        height: 25px;
        background-color: #f0f0f0;
        border-radius: 4px;
        margin: 0 10px;
        position: relative;
    }
    
    .bar {
        height: 100%;
        background-color: #4285F4;
        border-radius: 4px;
        width: 0;
        transition: width 0.8s cubic-bezier(0.25, 0.1, 0.25, 1);
    }
    
    .bar-value {
        width: 80px;
        text-align: right;
        font-size: 0.9rem;
        font-weight: 600;
    }
    
    /* KPI cards */
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 15px;
        margin-bottom: 20px;
    }
    
    .kpi-card {
        background-color: white;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        text-align: center;
    }
    
    .kpi-title {
        font-size: 0.9rem;
        color: #666;
        margin-bottom: 8px;
    }
    
    .kpi-value {
        font-size: 1.5rem;
        font-weight: 600;
        color: #333;
        margin-bottom: 5px;
    }
    
    .kpi-change {
        font-size: 0.8rem;
        padding: 3px 8px;
        border-radius: 12px;
        display: inline-block;
    }
    
    .positive-change {
        background-color: rgba(52, 168, 83, 0.15);
        color: #34A853;
    }
    
    .negative-change {
        background-color: rgba(234, 67, 53, 0.15);
        color: #EA4335;
    }
    
    /* Year slider */
    .year-slider-container {
        padding: 10px 20px;
        background-color: #f5f7f9;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    
    @media (max-width: 768px) {
        .kpi-container {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    </style>
    """), unsafe_allow_html=True)

def load_global_overview_specific_styles():
    """
    Load styles specific to the Global Overview page.
    """
    st.markdown(textwrap.dedent("""
    <style>
    /* Map visualization styles */
    .map-container {
        margin-bottom: 20px;
    }
    
    .map-filters {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 15px;
    }
    
    .filter-chip {
        background-color: #f0f2f5;
        padding: 5px 12px;
        border-radius: 16px;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .filter-chip:hover {
        background-color: #e1e5eb;
    }
    
    .filter-chip.active {
        background-color: #f3f4f6;
        border: 1px solid #0073ff;
        color: #111827;
    }
    
    /* Heat map styles */
    .heatmap-container {
        background-color: white;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    
    .heatmap-title {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 15px;
        color: #262730;
    }
    
    /* Time series chart styles */
    .time-series-container {
        background-color: white;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    
    .time-series-title {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 15px;
        color: #262730;
    }
    </style>
    """), unsafe_allow_html=True)

def get_floating_clock_style():
    """
    Return the CSS style for the floating clock.
    Used by time_utils.py for rendering the clock.
    """
    return textwrap.dedent("""
    <style>
    .floating-clock {
        position: fixed;
        top: 10px;
        right: 10px;
        background-color: rgba(255, 255, 255, 0.9);
        padding: 6px 10px;
        border-radius: 6px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        font-size: 0.8rem;
        z-index: 1000;
        font-family: 'Montserrat', sans-serif;
        border: 1px solid #eee;
        text-align: right;
    }

    .clock-time {
        font-weight: 600;
        color: #111827;
        line-height: 1.1;
    }

    .clock-date {
        font-size: 0.72rem;
        color: #6b7280;
    }
    </style>
    """)

def get_page_style():
    """
    Return the page CSS style.
    Used by various pages for standard styling.
    """
    return textwrap.dedent("""
    <style>
    :root {
        --app-font: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        --brand-blue: #0073ff;
    }

	    html, body, p, div, h1, h2, h3, h4, h5, h6, li, span, button, input, select,
	    textarea, a, label, option, .stApp {
	        font-family: var(--app-font) !important;
	        letter-spacing: 0 !important;
	    }

	    /* Tighter typography (titles/subtitles + general text) */
	    h1, h2, h3, h4, h5, h6,
	    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6,
	    [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
	    [data-testid="stMarkdownContainer"] h3, [data-testid="stMarkdownContainer"] h4,
	    [data-testid="stMarkdownContainer"] h5, [data-testid="stMarkdownContainer"] h6 {
	        letter-spacing: 0 !important;
	        line-height: 1.12;
	    }

	    [data-testid="stMarkdownContainer"] p,
	    [data-testid="stMarkdownContainer"] li {
	        letter-spacing: 0 !important;
	        line-height: 1.38;
	    }

	    /* Reduce default vertical whitespace in markdown blocks */
	    [data-testid="stMarkdownContainer"] p { margin: 0.35rem 0 0.55rem 0; }
	    [data-testid="stMarkdownContainer"] ul,
	    [data-testid="stMarkdownContainer"] ol { margin: 0.35rem 0 0.6rem 1.1rem; }
	    [data-testid="stMarkdownContainer"] li { margin: 0.2rem 0; }
	    [data-testid="stMarkdownContainer"] h2 { margin: 0.75rem 0 0.5rem 0; }
	    [data-testid="stMarkdownContainer"] h3 { margin: 0.7rem 0 0.45rem 0; }
	    [data-testid="stMarkdownContainer"] h4,
	    [data-testid="stMarkdownContainer"] h5,
	    [data-testid="stMarkdownContainer"] h6 { margin: 0.65rem 0 0.4rem 0; }

    section[data-testid="stSidebar"] *,
    [data-testid="stSidebarNav"] * {
        font-family: var(--app-font) !important;
    }

    section[data-testid="stSidebar"] {
        resize: horizontal;
        overflow: auto;
        min-width: 220px;
        max-width: 420px;
        flex: 0 0 auto;
    }

    h1 {
        color: #0073ff !important;
    }

    .stSlider [data-baseweb="slider"] > div {
        background-color: transparent !important;
    }

    .stSlider [data-baseweb="slider"] > div > div {
        background-color: transparent !important;
    }

    .stSlider [data-baseweb="slider"] div[role="slider"] {
        background-color: #ffffff !important;
        border-color: #0073ff !important;
        box-shadow: 0 0 0 2px rgba(17, 24, 39, 0.08) !important;
    }

    div[data-baseweb="select"] > div {
        border-color: #d1d5db !important;
    }

    div[data-baseweb="select"] > div:focus-within {
        border-color: #0073ff !important;
        box-shadow: 0 0 0 1px rgba(0, 115, 255, 0.25) !important;
    }

    .stMultiSelect [data-baseweb="tag"] {
        background-color: #f3f4f6 !important;
        color: #111827 !important;
        border: 1px solid rgba(0, 115, 255, 0.45) !important;
    }

    input[type="checkbox"], input[type="radio"] {
        accent-color: #0073ff !important;
    }

    label[data-baseweb="radio"] input:checked + div {
        border-color: #0073ff !important;
        background-color: #ffffff !important;
    }

    .main-content {
        padding: 1rem;
        max-width: 1200px;
        margin: 0 auto;
    }
    
    .section-heading {
        margin-top: 2rem;
        margin-bottom: 1rem;
        color: #1e3a8a;
        font-weight: 600;
        font-size: 1.5rem;
        border-bottom: 1px solid #e5e7eb;
        padding-bottom: 0.5rem;
    }
    
    .page-description {
        color: #4b5563;
        margin-bottom: 2rem;
        font-size: 1rem;
        line-height: 1.5;
    }
    
    .card {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    .card-title {
        font-weight: 600;
        font-size: 1.1rem;
        margin-bottom: 0.5rem;
        color: #111827;
    }
    
    .card-subtitle {
        color: #6b7280;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
    </style>
    """)

def get_animation_style():
    """
    Return the CSS style for animations.
    Used by pages that need custom animations.
    """
    return """
    <style>
    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .fade-in {
        animation: fadeIn 0.5s ease forwards;
    }
    
    .delay-100 {
        animation-delay: 0.1s;
    }
    
    .delay-200 {
        animation-delay: 0.2s;
    }
    
    .delay-300 {
        animation-delay: 0.3s;
    }
    
    .delay-400 {
        animation-delay: 0.4s;
    }
    
    .delay-500 {
        animation-delay: 0.5s;
    }
    
    @keyframes pulse {
        0% {
            box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.7);
        }
        70% {
            box-shadow: 0 0 0 10px rgba(37, 99, 235, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(37, 99, 235, 0);
        }
    }
    
    .pulse {
        animation: pulse 2s infinite;
    }
    </style>
    """
