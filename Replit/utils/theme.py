"""
Common theme utilities for consistent styling across all pages
"""
import streamlit as st
import textwrap

def apply_theme():
    """
    Apply consistent styling across all pages
    - Sets Montserrat font throughout the application
    - Increases size of insights text
    - Improves general typography and spacing
    """
    st.markdown(textwrap.dedent("""
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
    </style>
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
