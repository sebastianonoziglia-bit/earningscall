"""
Global font styling for the entire Streamlit application
Applies Montserrat font family across all pages and components
"""

import streamlit as st

def apply_oswald_font():
    """Apply Montserrat font styling to the entire application"""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=block');
    
    /* Apply Montserrat to all text elements */
    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 400;
    }
    
    /* Main content area */
    .main .block-container {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    /* Headers and titles - Montserrat Medium */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 500 !important;
    }
    
    /* Streamlit specific elements */
    .stMarkdown, .stText {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    /* Sidebar */
    .css-1d391kg {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    /* Buttons */
    .stButton button {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 500 !important;
    }
    
    /* Selectbox and input elements */
    .stSelectbox label, .stTextInput label, .stNumberInput label {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 500 !important;
    }
    
    /* Metric labels */
    .metric-label {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 500 !important;
    }
    
    /* Tab labels */
    .stTabs [data-baseweb="tab-list"] button {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 500 !important;
    }
    
    /* Expander headers */
    .streamlit-expanderHeader {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 500 !important;
    }
    
    /* DataFrames and tables */
    .dataframe {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    /* Success/warning/error messages */
    .stSuccess, .stWarning, .stError, .stInfo {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    /* All paragraph text */
    p {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    /* List items */
    li {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    /* Code blocks */
    code {
        font-family: 'Montserrat', monospace !important;
    }
    
    /* Chart titles and labels - Medium weight */
    .js-plotly-plot .plotly text {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    /* Ensure all divs inherit the font */
    div {
        font-family: 'Montserrat', sans-serif !important;
    }
    
    /* Override any remaining default fonts */
    * {
        font-family: 'Montserrat', sans-serif !important;
    }
    </style>
    """, unsafe_allow_html=True)
