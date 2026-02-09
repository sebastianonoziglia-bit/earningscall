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
    mode = st.session_state.get("theme_mode")
    if mode not in {"light", "dark"}:
        mode = "light"
        st.session_state["theme_mode"] = mode
    return mode

def render_theme_toggle():
    """
    Render a compact Light/Dark toggle in the header.
    """
    current = get_theme_mode()
    options = ["Light", "Dark"]
    index = 0 if current == "light" else 1
    selection = st.radio(
        "Theme",
        options,
        index=index,
        horizontal=True,
        label_visibility="collapsed",
        key="theme_mode_toggle",
    )
    st.session_state["theme_mode"] = selection.lower()

def apply_theme():
    """
    Apply consistent styling across all pages
    - Sets Montserrat font throughout the application
    - Increases size of insights text
    - Improves general typography and spacing
    """
    mode = get_theme_mode()
    st.markdown(textwrap.dedent(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=block');

        /* Base styles - apply to everything */
        html, body, p, div, h1, h2, h3, h4, h5, h6, li, span, button, input, select, textarea, .stApp {
            font-family: 'Montserrat', sans-serif !important;
        }

        h1 {
            color: #0073ff !important;
        }
        
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
            color: #94A3B8;
            margin-bottom: 2px;
        }

        /* Dark theme */
        body.theme-dark .stApp,
        body.theme-dark [data-testid="stAppViewContainer"],
        body.theme-dark section.main,
        body.theme-dark .block-container {
            background: #0B1220 !important;
            color: #F8FAFC !important;
        }

        body.theme-dark [data-testid="stMarkdownContainer"],
        body.theme-dark [data-testid="stMarkdownContainer"] p,
        body.theme-dark [data-testid="stMarkdownContainer"] li,
        body.theme-dark [data-testid="stMarkdownContainer"] span,
        body.theme-dark [data-testid="stMarkdownContainer"] strong {
            color: #E2E8F0 !important;
        }

        body.theme-dark h1, body.theme-dark h2, body.theme-dark h3,
        body.theme-dark h4, body.theme-dark h5, body.theme-dark h6 {
            color: #F8FAFC !important;
        }

        body.theme-dark section[data-testid="stSidebar"] {
            background: #0F172A !important;
            color: #E2E8F0 !important;
        }

        body.theme-dark div[data-baseweb="select"] > div,
        body.theme-dark div[data-baseweb="select"] > div > div,
        body.theme-dark input,
        body.theme-dark textarea {
            background: rgba(15, 23, 42, 0.85) !important;
            color: #F8FAFC !important;
            border-color: rgba(148, 163, 184, 0.35) !important;
        }

        body.theme-dark .stMultiSelect [data-baseweb="tag"] {
            background: rgba(148, 163, 184, 0.2) !important;
            color: #E2E8F0 !important;
        }

        body.theme-dark .stButton button,
        body.theme-dark .stDownloadButton button {
            background: rgba(15, 23, 42, 0.8) !important;
            color: #F8FAFC !important;
            border: 1px solid rgba(148, 163, 184, 0.4) !important;
        }

        body.theme-dark .js-plotly-plot text {
            fill: #E2E8F0 !important;
        }

        /* Light theme (explicit resets for clarity) */
        body.theme-light .stApp,
        body.theme-light [data-testid="stAppViewContainer"],
        body.theme-light section.main,
        body.theme-light .block-container {
            background: #FFFFFF !important;
            color: #0F172A !important;
        }
    </style>
    <script>
        const body = window.parent.document.body;
        body.classList.remove('theme-dark', 'theme-light', 'overview-dark');
        body.classList.add('theme-{mode}');
    </script>
    """), unsafe_allow_html=True)

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
