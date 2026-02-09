"""
Common theme utilities for consistent styling across all pages
"""
import streamlit as st
import textwrap

def get_theme_mode():
    """
    Return the current theme mode ('light' or 'dark').
    Defaults to light if unset.
    """
    mode = st.session_state.get("theme_mode", "Light")
    if isinstance(mode, str) and mode.lower() in {"light", "dark"}:
        return mode.lower()
    st.session_state["theme_mode"] = "Light"
    return "light"

def render_theme_toggle():
    """
    Render a compact Light/Dark toggle in the header.
    """
    current = get_theme_mode()
    options = ["Light", "Dark"]
    index = 0 if current == "light" else 1
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = "Light"
    st.radio(
        "Theme",
        options,
        index=index,
        horizontal=True,
        label_visibility="collapsed",
        key="theme_mode",
    )

def apply_theme():
    """
    Apply consistent styling across all pages
    - Sets Montserrat font throughout the application
    - Increases size of insights text
    - Improves general typography and spacing
    """
    mode = get_theme_mode()
    if mode == "dark":
        bg = "#0B1220"
        text = "#F8FAFC"
        muted = "#E2E8F0"
        border = "rgba(148, 163, 184, 0.35)"
        surface = "rgba(15, 23, 42, 0.85)"
        surface_alt = "rgba(15, 23, 42, 0.65)"
        accent = "#3B82F6"
        accent_text = "#F8FAFC"
    else:
        bg = "#FFFFFF"
        text = "#0F172A"
        muted = "#475569"
        border = "rgba(15, 23, 42, 0.12)"
        surface = "#F8FAFC"
        surface_alt = "#F1F5F9"
        accent = "#2563EB"
        accent_text = "#FFFFFF"

    css = textwrap.dedent("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=block');

        :root {
            --app-bg: __BG__;
            --app-text: __TEXT__;
            --app-muted: __MUTED__;
            --app-border: __BORDER__;
            --app-surface: __SURFACE__;
            --app-surface-alt: __SURFACE_ALT__;
            --app-accent: __ACCENT__;
            --app-accent-text: __ACCENT_TEXT__;
        }

        /* Base styles - apply to everything */
        html, body, p, div, h1, h2, h3, h4, h5, h6, li, span, button, input, select, textarea, .stApp {
            font-family: 'Montserrat', sans-serif !important;
        }

        h1 { color: var(--app-accent) !important; }
        
        /* Streamlit elements */
        .css-1kyxreq, .st-ae, .st-af, .st-ag, .st-ah, .st-ai, .st-aj, .st-ak, .st-al, 
        .st-am, .st-an, .st-ao, .st-ap, .st-aq, .st-ar, .st-as, .st-at, 
        .css-10trblm, .css-16idsys, .css-183lzff, .css-1aehpvj, .css-1v3fvcr {
            font-family: 'Montserrat', sans-serif !important;
        }
        
        /* Page selector in sidebar */
        section[data-testid="stSidebar"] *,
        [data-testid="stSidebarNav"] *,
        .css-1oe6o96, .css-uc1cuc, .css-erpbzb {
            font-family: 'Montserrat', sans-serif !important;
        }
        
        /* Company and segment insights - larger font */
        .insight-text, .company-insight, .segment-insight {
            font-family: 'Montserrat', sans-serif !important;
            font-size: 1.05rem !important;
            line-height: 1.6 !important;
        }
        
        /* Bullet points in insights */
        .insight-bullet {
            margin: 8px 0;
            line-height: 1.6;
        }
        
        /* Metrics and cards */
        .metric-card, .value-box {
            font-family: 'Montserrat', sans-serif !important;
        }
        
        /* Chart labels and titles */
        .js-plotly-plot .plotly .gtitle, .js-plotly-plot .plotly .xtitle, 
        .js-plotly-plot .plotly .ytitle, .js-plotly-plot .plotly .legendtext {
            font-family: 'Montserrat', sans-serif !important;
        }
        
        /* Buttons */
        .stButton button {
            font-family: 'Montserrat', sans-serif !important;
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab"] {
            font-family: 'Montserrat', sans-serif !important;
        }
        
        /* Tooltips */
        .tooltip, [data-tooltip] {
            font-family: 'Montserrat', sans-serif !important;
        }

        /* Theme toggle styling */
        .theme-toggle-label {
            font-size: 0.75rem;
            color: var(--app-muted);
            margin-bottom: 2px;
        }

        /* App background + text */
        .stApp,
        [data-testid="stAppViewContainer"],
        section.main,
        .block-container {
            background: var(--app-bg) !important;
            color: var(--app-text) !important;
        }

        [data-testid="stMarkdownContainer"],
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] span,
        [data-testid="stMarkdownContainer"] strong {
            color: var(--app-text) !important;
        }

        h1, h2, h3, h4, h5, h6 {
            color: var(--app-text) !important;
        }

        section[data-testid="stSidebar"] {
            background: var(--app-bg) !important;
            color: var(--app-text) !important;
            border-right: 1px solid var(--app-border);
        }

        /* Inputs / selects */
        div[data-baseweb="select"] > div,
        div[data-baseweb="select"] > div > div,
        input,
        textarea,
        .stNumberInput input {
            background: var(--app-surface) !important;
            color: var(--app-text) !important;
            border-color: var(--app-border) !important;
        }

        .stMultiSelect [data-baseweb="tag"] {
            background: var(--app-surface-alt) !important;
            color: var(--app-text) !important;
        }

        /* Radio + checkbox */
        .stRadio label, .stCheckbox label {
            color: var(--app-text) !important;
        }
        .stRadio [data-baseweb="radio"] {
            background: transparent !important;
        }
        .stRadio [data-baseweb="radio"] div[role="radio"] {
            border-color: var(--app-border) !important;
            background: transparent !important;
        }
        .stRadio [data-baseweb="radio"] div[role="radio"][aria-checked="true"] {
            border-color: var(--app-accent) !important;
        }
        .stCheckbox [data-baseweb="checkbox"] > div {
            border-color: var(--app-border) !important;
            background: var(--app-surface) !important;
        }

        /* Buttons */
        .stButton button,
        .stDownloadButton button {
            background: var(--app-surface) !important;
            color: var(--app-text) !important;
            border: 1px solid var(--app-border) !important;
        }

        /* Plotly text */
        .js-plotly-plot text {
            fill: var(--app-text) !important;
        }
    </style>
    """)
    css = (
        css.replace("__BG__", bg)
        .replace("__TEXT__", text)
        .replace("__MUTED__", muted)
        .replace("__BORDER__", border)
        .replace("__SURFACE__", surface)
        .replace("__SURFACE_ALT__", surface_alt)
        .replace("__ACCENT__", accent)
        .replace("__ACCENT_TEXT__", accent_text)
    )
    st.markdown(css, unsafe_allow_html=True)

def format_company_insights(insights_text):
    """
    Format company insights text for better display
    - Adds proper bullet point formatting
    - Uses Montserrat font with increased size
    - Ensures consistent spacing between points
    - Fixes "withrecord" spacing issue in Apple Financial Growth text
    
    Args:
        insights_text: Raw insights text, with bullet points
        
    Returns:
        HTML-formatted insights for display
    """
    if not insights_text:
        return ""
    
    # Fix the specific issue with "annual revenue totaled" text that appears without proper spacing
    if "Annual revenue totaled" in insights_text:
        # Fix the spacing issue with "withrecord" 
        insights_text = insights_text.replace("Bwithrecord", "B with record ")
        
        # Also check for other variations
        insights_text = insights_text.replace("Bwith record", "B with record ")
        insights_text = insights_text.replace("B withrecord", "B with record ")
    
    formatted_html = '<div class="company-insight">'
    
    # Split by bullet points and format each point
    if "•" in insights_text:
        points = insights_text.split("•")
        for point in points:
            if point.strip():
                # Apply additional fixing for specific revenue text patterns inside each bullet point
                point_text = point.strip()
                if "Annual revenue totaled" in point_text and "withrecord" in point_text:
                    point_text = point_text.replace("Bwithrecord", "B with record ")
                
                formatted_html += f'<div class="insight-bullet">• {point_text}</div>'
    else:
        # If no bullet points, just format the text
        formatted_html += f'<p>{insights_text}</p>'
    
    formatted_html += '</div>'
    return formatted_html

def format_segment_insights(insights_text):
    """
    Format segment insights text for better display
    - Uses larger font size with Montserrat
    - Adds specific styling for segment insights
    
    Args:
        insights_text: Raw segment insights text
        
    Returns:
        HTML-formatted segment insights for display
    """
    if not insights_text:
        return ""
    
    formatted_html = '<div class="segment-insight">'
    
    # Split by bullet points and format each point if present
    if "•" in insights_text:
        points = insights_text.split("•")
        for point in points:
            if point.strip():
                formatted_html += f'<div class="insight-bullet">• {point.strip()}</div>'
    else:
        # If no bullet points, just format the text
        formatted_html += f'<p>{insights_text}</p>'
    
    formatted_html += '</div>'
    return formatted_html
