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
    # Build the light MFE template (white bg, dark text for non-Welcome pages)
    mfe_blue = go.layout.Template()
    mfe_blue.layout = go.Layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#374151", family="DM Sans, Inter, sans-serif"),
        title=dict(font=dict(color="#111827", size=14)),
        xaxis=dict(
            tickfont=dict(color="#374151", size=11),
            title_font=dict(color="#6b7280"),
            gridcolor="rgba(0,0,0,0.05)",
            showline=False,
            zeroline=False,
        ),
        yaxis=dict(
            tickfont=dict(color="#374151", size=11),
            title_font=dict(color="#6b7280"),
            gridcolor="rgba(0,0,0,0.05)",
            showline=False,
            zeroline=False,
        ),
        legend=dict(
            font=dict(color="#374151", size=11),
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="rgba(0,0,0,0.08)",
            borderwidth=1,
        ),
        colorway=[
            "#4285F4", "#FF5B1F", "#1DB954", "#E50914",
            "#FF9900", "#0082FB", "#9147FF", "#113CCF",
        ],
    )

    pio.templates["mfe_blue"] = mfe_blue
    pio.templates["mfe_dark"] = mfe_blue  # alias so old references still work
    pio.templates.default = "plotly_white+mfe_blue"

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

		    /* Hide default Streamlit sidebar — we use custom bottom nav bar */
		    section[data-testid="stSidebar"] {
		        display: none !important;
		        visibility: hidden !important;
		        width: 0 !important;
		        min-width: 0 !important;
		        max-width: 0 !important;
		        overflow: hidden !important;
		    }
		    [data-testid="stSidebarNav"] {
		        display: none !important;
		    }
		    /* Also hide the collapse button */
		    [data-testid="collapsedControl"] {
		        display: none !important;
		    }

            /* Remove excessive default top whitespace across pages */
            [data-testid="stAppViewContainer"] > section > div.block-container {
                padding-top: 0 !important;
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

        /* Plotly typography handled by Plotly defaults to avoid CSS conflicts */

    /* Fix: hide Material Icons text when font fails to load ("arrow_right" etc.) — GLOBAL
       Strategy: font-size:0 + color:transparent on summary AND all descendants,
       then restore only on [data-testid="stMarkdownContainer"]. This ensures
       even elements with direct Streamlit/emotion font-size get overridden. */
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary * {
        font-size: 0 !important;
        color: transparent !important;
    }
    [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
    [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] * {
        font-size: 0.875rem !important;
        color: #374151 !important;
    }
    [data-testid="stExpander"] summary svg,
    [data-testid="stExpander"] summary svg * {
        color: #94a3b8 !important;
        visibility: visible !important;
    }

    /* Fix multiselect pill text clipping — kill ALL pseudo-element overlays */
    [data-baseweb="select"]::before,
    [data-baseweb="select"]::after,
    [data-baseweb="input"]::before,
    [data-baseweb="input"]::after,
    [data-baseweb="select"] > div::before,
    [data-baseweb="select"] > div::after,
    [data-baseweb="select"] > div > div::before,
    [data-baseweb="select"] > div > div::after,
    .stMultiSelect [data-baseweb="select"]::before,
    .stMultiSelect [data-baseweb="select"]::after,
    .stMultiSelect [data-baseweb="select"] > div::before,
    .stMultiSelect [data-baseweb="select"] > div::after {
        display: none !important;
        content: none !important;
        background: none !important;
        background-image: none !important;
        width: 0 !important;
        height: 0 !important;
        position: absolute !important;
        pointer-events: none !important;
    }
    /* Tag pill — proper padding so first letter is never clipped */
    [data-baseweb="tag"] {
        overflow: visible !important;
        max-width: none !important;
        padding: 2px 8px 2px 10px !important;
        min-width: 0 !important;
        text-overflow: unset !important;
        margin-left: 4px !important;
    }
    [data-baseweb="tag"] > span,
    [data-baseweb="tag"] span[dir="auto"] {
        overflow: visible !important;
        text-overflow: unset !important;
        white-space: nowrap !important;
        max-width: none !important;
        min-width: 0 !important;
    }
    /* Close button inside tag — don't overlap text */
    [data-baseweb="tag"] [role="presentation"] {
        margin-left: 6px !important;
        flex-shrink: 0 !important;
        position: relative !important;
    }
    /* Ensure container doesn't clip tags — kill gradient overlays */
    [data-baseweb="input"],
    [data-baseweb="select"] > div:first-child {
        overflow: visible !important;
        flex-wrap: wrap !important;
        padding-left: 4px !important;
    }
    /* Kill linear-gradient scroll-shadow overlays that Streamlit/BaseWeb adds */
    .stMultiSelect [data-baseweb="select"] > div > div {
        background-image: none !important;
    }

    /* Slider styling */
    .stSlider [data-baseweb="slider"] > div {
        background-color: transparent !important;
    }

    .stSlider [data-baseweb="slider"] > div > div {
        background-color: transparent !important;
    }

    .stSlider [data-baseweb="slider"] div[role="slider"] {
        background-color: var(--app-surface, #ffffff) !important;
        border-color: var(--app-accent, #0073ff) !important;
        box-shadow: 0 0 0 2px rgba(15, 23, 42, 0.12) !important;
    }

    /* Select and multiselect styling */
    div[data-baseweb="select"] > div {
        border-color: var(--app-border, #d1d5db) !important;
        background-color: var(--app-surface, #ffffff) !important;
        color: var(--app-text, #0f172a) !important;
    }

    div[data-baseweb="select"] > div:focus-within {
        border-color: var(--app-accent, #0073ff) !important;
        box-shadow: 0 0 0 1px rgba(0, 115, 255, 0.25) !important;
    }

    .stMultiSelect [data-baseweb="tag"] {
        background-color: var(--app-surface-alt, #f3f4f6) !important;
        color: var(--app-text, #111827) !important;
        border: 1px solid rgba(0, 115, 255, 0.45) !important;
    }

    input[type="checkbox"], input[type="radio"] {
        accent-color: var(--app-accent, #0073ff) !important;
    }

    /* Streamlit radio: input:checked + div is the text block, not the marker. */
    label[data-baseweb="radio"] input:checked + div {
        border-color: transparent !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    label[data-baseweb="radio"]:has(input:checked) > div:first-of-type {
        background: var(--app-accent, #0073ff) !important;
        border-color: var(--app-accent, #0073ff) !important;
        box-shadow: inset 0 0 0 3px var(--app-accent-text, #ffffff) !important;
    }
    label[data-baseweb="radio"] > div:last-of-type,
    label[data-baseweb="radio"] > div:last-of-type * {
        background: transparent !important;
        box-shadow: none !important;
    }
    label[data-baseweb="radio"],
    label[data-baseweb="radio"]:hover,
    label[data-baseweb="radio"][aria-checked="true"] {
        background: transparent !important;
        box-shadow: none !important;
        outline: none !important;
    }
    label[data-baseweb="radio"] span {
        background: transparent !important;
    }

    /* Horizontal radios rendered as button-groups in newer Streamlit */
    div[data-testid="stRadio"] [data-baseweb="button-group"],
    div[data-testid="stRadio"] [data-baseweb="button-group"] > div {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    div[data-testid="stRadio"] [data-baseweb="button-group"] button,
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"],
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"],
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"] {
        background: transparent !important;
        color: var(--app-text, #111827) !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 0 0 26px !important;
        position: relative !important;
        -webkit-tap-highlight-color: transparent !important;
        user-select: none !important;
        -webkit-user-select: none !important;
        -ms-user-select: none !important;
        cursor: pointer !important;
    }
    div[data-testid="stRadio"] [data-baseweb="button-group"] button *,
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"] *,
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"] *,
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"] * {
        color: var(--app-text, #111827) !important;
        background: transparent !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] [aria-checked="true"],
    div[data-testid="stRadio"] [role="radiogroup"] [aria-selected="true"],
    div[data-testid="stRadio"] [role="radiogroup"] [aria-pressed="true"] {
        background: transparent !important;
        color: var(--app-text, #111827) !important;
    }
    .stRadio [data-baseweb="radio"] label[data-baseweb="radio"][aria-checked="true"] span {
        color: var(--app-text, #111827) !important;
    }
    div[data-testid="stRadio"] [data-baseweb="button-group"] button::before {
        content: "";
        position: absolute;
        left: 4px;
        top: 50%;
        transform: translateY(-50%);
        width: 16px;
        height: 16px;
        border: 1.5px solid var(--app-accent, #0073ff) !important;
        border-radius: 4px;
        background: transparent;
        box-shadow: none;
    }
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"]::before,
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"]::before,
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"]::before {
        background: var(--app-accent, #0073ff) !important;
        box-shadow: inset 0 0 0 3px var(--app-accent-text, #ffffff) !important;
    }
    .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button::before {
        border-radius: 999px;
    }
    .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"]::before,
    .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"]::before,
    .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"]::before {
        background: transparent !important;
        box-shadow: inset 0 0 0 4px var(--app-accent, #0073ff) !important;
    }

    /* Catch-all for Streamlit radio button variants (avoid text highlight, force checkbox fill) */
    div[data-testid="stRadio"] [role="radiogroup"] [role="radio"],
    div[data-testid="stRadio"] [role="radiogroup"] [role="button"] {
        background: transparent !important;
        color: var(--app-text, #111827) !important;
        box-shadow: none !important;
        border: none !important;
        position: relative !important;
        padding-left: 26px !important;
        -webkit-tap-highlight-color: transparent !important;
        user-select: none !important;
        -webkit-user-select: none !important;
        -ms-user-select: none !important;
        cursor: pointer !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] [role="radio"]::before,
    div[data-testid="stRadio"] [role="radiogroup"] [role="button"]::before {
        content: "";
        position: absolute;
        left: 4px;
        top: 50%;
        transform: translateY(-50%);
        width: 16px;
        height: 16px;
        border: 1.5px solid var(--app-accent, #0073ff) !important;
        border-radius: 4px;
        background: transparent !important;
        box-shadow: none !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] [role="radio"][aria-checked="true"]::before,
    div[data-testid="stRadio"] [role="radiogroup"] [role="button"][aria-pressed="true"]::before,
    div[data-testid="stRadio"] [role="radiogroup"] [role="button"][aria-selected="true"]::before {
        background: var(--app-accent, #0073ff) !important;
        box-shadow: inset 0 0 0 3px var(--app-accent-text, #ffffff) !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] [role="radio"] *,
    div[data-testid="stRadio"] [role="radiogroup"] [role="button"] * {
        color: var(--app-text, #111827) !important;
        background: transparent !important;
        user-select: none !important;
        -webkit-user-select: none !important;
        -ms-user-select: none !important;
    }
    .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="radio"]::before,
    .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="button"]::before {
        border-radius: 999px !important;
    }
    .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="radio"][aria-checked="true"]::before,
    .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="button"][aria-pressed="true"]::before,
    .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="button"][aria-selected="true"]::before {
        background: transparent !important;
        box-shadow: inset 0 0 0 4px var(--app-accent, #0073ff) !important;
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

    /* Remove wrapper artifacts around overview navigator buttons */
    div[data-testid="column"] > div[data-testid="stVerticalBlock"] > div[data-baseweb="block"] {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }
    div[data-testid="stButtonGroup"],
    div[data-testid="stButtonGroup"] > div {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }
    div[data-testid="stVerticalBlock"] .stButton > button {
        text-align: center !important;
        justify-content: center !important;
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        background: #f8fafc !important;
        border: 1px solid #e2e8f0 !important;
        color: #374151 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        letter-spacing: 0.02em !important;
        transition: background 0.2s ease, border-color 0.2s ease !important;
        padding: 8px 16px !important;
    }
    div[data-testid="stVerticalBlock"] .stButton > button:hover {
        background: #f1f5f9 !important;
        border-color: #94a3b8 !important;
        color: #111827 !important;
    }
    div[data-testid="stVerticalBlock"] .stButton > button:focus,
    div[data-testid="stVerticalBlock"] .stButton > button:active,
    div[data-testid="stVerticalBlock"] .stButton > button:focus-visible {
        outline: none !important;
        background: #f1f5f9 !important;
        box-shadow: 0 0 0 2px rgba(255,91,31,0.25) !important;
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
        background-color: var(--app-surface, #ffffff) !important;
        border-color: var(--app-accent, #0073ff) !important;
        box-shadow: 0 0 0 2px rgba(15, 23, 42, 0.12) !important;
    }

    div[data-baseweb="select"] > div {
        border-color: var(--app-border, #d1d5db) !important;
        background-color: var(--app-surface, #ffffff) !important;
        color: var(--app-text, #0f172a) !important;
    }

    div[data-baseweb="select"] > div:focus-within {
        border-color: var(--app-accent, #0073ff) !important;
        box-shadow: 0 0 0 1px rgba(0, 115, 255, 0.25) !important;
    }

    .stMultiSelect [data-baseweb="tag"] {
        background-color: var(--app-surface-alt, #f3f4f6) !important;
        color: var(--app-text, #111827) !important;
        border: 1px solid rgba(0, 115, 255, 0.45) !important;
    }

    input[type="checkbox"], input[type="radio"] {
        accent-color: var(--app-accent, #0073ff) !important;
    }

    /* Streamlit radio: input:checked + div is the text block, not the marker. */
    label[data-baseweb="radio"] input:checked + div {
        border-color: transparent !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    label[data-baseweb="radio"]:has(input:checked) > div:first-of-type {
        background: var(--app-accent, #0073ff) !important;
        border-color: var(--app-accent, #0073ff) !important;
        box-shadow: inset 0 0 0 3px var(--app-accent-text, #ffffff) !important;
    }
    label[data-baseweb="radio"] > div:last-of-type,
    label[data-baseweb="radio"] > div:last-of-type * {
        background: transparent !important;
        box-shadow: none !important;
    }
    label[data-baseweb="radio"],
    label[data-baseweb="radio"]:hover,
    label[data-baseweb="radio"][aria-checked="true"] {
        background: transparent !important;
        box-shadow: none !important;
        outline: none !important;
    }
    label[data-baseweb="radio"] span {
        background: transparent !important;
    }

    /* Horizontal radios rendered as button-groups in newer Streamlit */
    div[data-testid="stRadio"] [data-baseweb="button-group"],
    div[data-testid="stRadio"] [data-baseweb="button-group"] > div {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    div[data-testid="stRadio"] [data-baseweb="button-group"] button,
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"],
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"],
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"] {
        background: transparent !important;
        color: var(--app-text, #111827) !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 0 0 26px !important;
        position: relative !important;
    }
    div[data-testid="stRadio"] [data-baseweb="button-group"] button::before {
        content: "";
        position: absolute;
        left: 4px;
        top: 50%;
        transform: translateY(-50%);
        width: 16px;
        height: 16px;
        border: 1.5px solid var(--app-accent, #0073ff) !important;
        border-radius: 4px;
        background: transparent;
        box-shadow: none;
    }
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"]::before,
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"]::before,
    div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"]::before {
        background: var(--app-accent, #0073ff) !important;
        box-shadow: inset 0 0 0 3px var(--app-accent-text, #ffffff) !important;
    }
    .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button::before {
        border-radius: 999px;
    }
    .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"]::before,
    .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"]::before,
    .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"]::before {
        background: transparent !important;
        box-shadow: inset 0 0 0 4px var(--app-accent, #0073ff) !important;
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

    div[data-testid="stButton"] > button {
        background-color: #f3f4f6 !important;
        color: #111827 !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 8px !important;
    }
    div[data-testid="stButton"] > button:hover {
        background-color: #e5e7eb !important;
        color: #111827 !important;
        border-color: #d1d5db !important;
    }
    div[data-testid="stButton"] > button *,
    div[data-testid="stButton"] > button p,
    div[data-testid="stButton"] > button span {
        color: #111827 !important;
    }
    /* Search/filter inputs — ensure dark text on white bg */
    div[data-baseweb="input"] input,
    div[data-testid="stTextInput"] input,
    div[data-baseweb="select"] input,
    div[data-testid="stMultiSelect"] input {
        color: #111827 !important;
        background-color: #ffffff !important;
    }
    div[data-baseweb="input"] input::placeholder,
    div[data-testid="stTextInput"] input::placeholder,
    div[data-testid="stMultiSelect"] input::placeholder {
        color: #9ca3af !important;
    }
    /* Caption / Last updated text — readable on white bg */
    div[data-testid="stCaptionContainer"] p,
    div[data-testid="stCaptionContainer"],
    .stCaption p {
        color: #374151 !important;
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
