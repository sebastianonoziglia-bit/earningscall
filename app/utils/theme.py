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
    st.markdown("<div class=\"theme-toggle\">", unsafe_allow_html=True)
    st.radio(
        "Theme",
        options,
        index=index,
        horizontal=True,
        label_visibility="collapsed",
        key="theme_mode",
    )
    st.markdown("</div>", unsafe_allow_html=True)

def apply_theme(enable_dom_patch: bool = True):
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
        card_bg = "#FFFFFF"
        card_text = "#0F172A"
        card_muted = "#475569"
        plot_bg = bg
    else:
        bg = "#FFFFFF"
        text = "#0F172A"
        muted = "#475569"
        border = "rgba(15, 23, 42, 0.12)"
        surface = "#F8FAFC"
        surface_alt = "#F1F5F9"
        accent = "#2563EB"
        accent_text = "#FFFFFF"
        card_bg = "#FFFFFF"
        card_text = "#0F172A"
        card_muted = "#64748B"
        plot_bg = bg

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
            --card-bg: __CARD_BG__;
            --card-text: __CARD_TEXT__;
            --card-muted: __CARD_MUTED__;
            --plot-bg: __PLOT_BG__;
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

        /* Ensure colored segment insight cards always use white text */
        .segment-insight-card,
        .segment-insight-card * {
            color: #ffffff !important;
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

        /* Plotly styling is handled by Plotly itself to avoid hiding traces. */

        /* Theme toggle styling */
        .theme-toggle-label {
            font-size: 0.75rem;
            color: var(--app-muted);
            margin-bottom: 2px;
        }

        /* App background + text */
        body,
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

        label {
            background: transparent !important;
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
        section[data-testid="stSidebar"] *,
        [data-testid="stSidebarNav"] * {
            color: var(--app-text) !important;
        }

        /* Full-screen mode: hide Streamlit sidebar/page-nav for all pages. */
        section[data-testid="stSidebar"] {
            display: none !important;
            width: 0 !important;
            min-width: 0 !important;
            max-width: 0 !important;
        }
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        [data-testid="stAppViewContainer"] > .main {
            margin-left: 0 !important;
        }
        [data-testid="stAppViewContainer"] > .main .block-container {
            max-width: none !important;
            padding-top: 0 !important;
            margin-top: 0 !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
        }
        [data-testid="stAppViewContainer"] > section > div.block-container,
        section.main > div.block-container {
            padding-top: 0 !important;
            margin-top: 0 !important;
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
        div[data-baseweb="select"] * {
            color: var(--app-text) !important;
        }

        .stMultiSelect [data-baseweb="tag"] {
            background: var(--app-surface-alt) !important;
            color: var(--app-text) !important;
        }

        /* Radio + checkbox */
        .stRadio label, .stCheckbox label {
            color: var(--app-text) !important;
        }
        .stRadio label,
        .stRadio label > div,
        .stRadio label > div > div,
        .stCheckbox label,
        .stCheckbox label > div,
        .stCheckbox label > div > div {
            background: transparent !important;
        }
        .stRadio label * {
            background: transparent !important;
            box-shadow: none !important;
        }
        .stCheckbox label,
        .stCheckbox label * {
            background: transparent !important;
            box-shadow: none !important;
        }
        .stRadio div[role="radiogroup"] label {
            background: transparent !important;
        }
        .stRadio div[role="radiogroup"] > div {
            background: transparent !important;
        }
        .stRadio [data-baseweb="radio"] > div {
            background: transparent !important;
        }
        .stRadio [data-baseweb="radio"] > div * {
            background: transparent !important;
        }
        div[data-testid="stRadio"] label,
        div[data-testid="stRadio"] div,
        div[data-testid="stRadio"] span {
            background: transparent !important;
        }
        .stRadio [data-baseweb="radio"],
        .stCheckbox [data-baseweb="checkbox"] {
            background: transparent !important;
        }
        .stRadio [data-baseweb="radio"] label,
        .stCheckbox [data-baseweb="checkbox"] label {
            background: transparent !important;
        }
        .stRadio [data-baseweb="radio"] label[data-baseweb="radio"],
        .stRadio [data-baseweb="radio"] label[data-baseweb="radio"]:hover,
        .stRadio [data-baseweb="radio"] label[data-baseweb="radio"][aria-checked="true"],
        .stCheckbox [data-baseweb="checkbox"] label[data-baseweb="checkbox"],
        .stCheckbox [data-baseweb="checkbox"] label[data-baseweb="checkbox"]:hover {
            background: transparent !important;
            box-shadow: none !important;
            outline: none !important;
        }
        .stRadio [data-baseweb="radio"] label[data-baseweb="radio"] * {
            background: transparent !important;
            box-shadow: none !important;
        }
        .stRadio [data-baseweb="radio"] span,
        .stRadio [data-baseweb="radio"] div:last-child {
            background: transparent !important;
        }
        .stRadio [data-baseweb="radio"] label > div:last-child,
        .stCheckbox [data-baseweb="checkbox"] label > div:last-child {
            background: transparent !important;
        }
        /* Force visible checkbox-style indicators for radios */
        .stRadio label[data-baseweb="radio"] > div:first-of-type {
            width: 18px !important;
            height: 18px !important;
            border: 1.5px solid var(--app-accent) !important;
            border-radius: 4px !important;
            background: transparent !important;
            box-shadow: none !important;
            margin-right: 8px !important;
        }
        .stCheckbox label[data-baseweb="checkbox"] > div:first-of-type {
            width: 18px !important;
            height: 18px !important;
            border: 1.5px solid var(--app-accent) !important;
            border-radius: 4px !important;
            background: transparent !important;
            box-shadow: none !important;
            margin-right: 8px !important;
        }
        /* Important: input:checked + div targets the label text block in Streamlit radios.
           Keep that text block transparent and style only the first marker box. */
        div[data-testid="stRadio"] label[data-baseweb="radio"] input:checked + div {
            background: transparent !important;
            border-color: transparent !important;
            box-shadow: none !important;
        }
        div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div:first-of-type {
            background: var(--app-accent) !important;
            border-color: var(--app-accent) !important;
            box-shadow: inset 0 0 0 3px var(--app-accent-text) !important;
        }
        div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div:last-of-type,
        div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div:last-of-type *,
        div[data-testid="stRadio"] label[data-baseweb="radio"] > div:last-of-type,
        div[data-testid="stRadio"] label[data-baseweb="radio"] > div:last-of-type * {
            background: transparent !important;
            color: var(--app-text) !important;
            box-shadow: none !important;
        }
        div[data-testid="stCheckbox"] label[data-baseweb="checkbox"] input:checked + div {
            background: var(--app-accent) !important;
            border-color: var(--app-accent) !important;
            box-shadow: inset 0 0 0 3px var(--app-accent-text) !important;
        }
        div[data-testid="stCheckbox"] label[data-baseweb="checkbox"] input:checked + div svg {
            fill: var(--app-accent-text) !important;
            stroke: var(--app-accent-text) !important;
        }
        /* Keep the theme toggle as a round radio with a dot */
        .theme-toggle .stRadio label[data-baseweb="radio"] > div:first-of-type {
            border-radius: 999px !important;
        }
        .theme-toggle .stRadio label[data-baseweb="radio"] input:checked + div {
            background: transparent !important;
            box-shadow: none !important;
            border-color: transparent !important;
        }
        .theme-toggle .stRadio label[data-baseweb="radio"]:has(input:checked) > div:first-of-type {
            background: transparent !important;
            box-shadow: inset 0 0 0 4px var(--app-accent) !important;
            border-color: var(--app-accent) !important;
        }
        /* Theme toggle: remove label highlight, keep only control fill */
        .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button,
        .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"],
        .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"],
        .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"],
        .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="radio"],
        .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="button"] {
            background: transparent !important;
            color: var(--app-text) !important;
            box-shadow: none !important;
            border: none !important;
        }
        .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button *,
        .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="radio"] *,
        .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="button"] * {
            background: transparent !important;
            box-shadow: none !important;
            color: var(--app-text) !important;
        }
        .stCheckbox [data-baseweb="checkbox"] > div {
            border-color: var(--app-border) !important;
            background: var(--app-surface) !important;
        }
        .stRadio [data-baseweb="radio"] div[role="radio"] + div,
        .stCheckbox [data-baseweb="checkbox"] div[role="checkbox"] + div {
            color: var(--app-text) !important;
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
            color: var(--app-text) !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 0 0 26px !important;
            position: relative !important;
        }
        div[data-testid="stRadio"] [data-baseweb="button-group"] button *,
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"] *,
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"] *,
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"] * {
            color: var(--app-text) !important;
            background: transparent !important;
        }
        div[data-testid="stRadio"] [role="radiogroup"] [aria-checked="true"],
        div[data-testid="stRadio"] [role="radiogroup"] [aria-selected="true"],
        div[data-testid="stRadio"] [role="radiogroup"] [aria-pressed="true"] {
            background: transparent !important;
            color: var(--app-text) !important;
        }
        .stRadio [data-baseweb="radio"] label[data-baseweb="radio"][aria-checked="true"] span {
            color: var(--app-text) !important;
        }
        div[data-testid="stRadio"] [data-baseweb="button-group"] button::before {
            content: "";
            position: absolute;
            left: 4px;
            top: 50%;
            transform: translateY(-50%);
            width: 16px;
            height: 16px;
            border: 1.5px solid var(--app-accent) !important;
            border-radius: 4px;
            background: transparent;
            box-shadow: none;
        }
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"]::before,
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"]::before,
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"]::before {
            background: var(--app-accent) !important;
            box-shadow: inset 0 0 0 3px var(--app-accent-text) !important;
        }
        /* Keep the theme toggle as a round radio with a dot */
        .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button::before {
            border-radius: 999px;
        }
        .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"]::before,
        .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"]::before,
        .theme-toggle div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"]::before {
            background: transparent !important;
            box-shadow: inset 0 0 0 4px var(--app-accent) !important;
        }

        /* Catch-all for Streamlit radio button variants (avoid text highlight, force checkbox fill) */
        div[data-testid="stRadio"] [role="radiogroup"] [role="radio"],
        div[data-testid="stRadio"] [role="radiogroup"] [role="button"] {
            background: transparent !important;
            color: var(--app-text) !important;
            box-shadow: none !important;
            border: none !important;
            position: relative !important;
            padding-left: 26px !important;
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
            border: 1.5px solid var(--app-accent) !important;
            border-radius: 4px;
            background: transparent !important;
            box-shadow: none !important;
        }
        div[data-testid="stRadio"] [role="radiogroup"] [role="radio"][aria-checked="true"]::before,
        div[data-testid="stRadio"] [role="radiogroup"] [role="button"][aria-pressed="true"]::before,
        div[data-testid="stRadio"] [role="radiogroup"] [role="button"][aria-selected="true"]::before {
            background: var(--app-accent) !important;
            box-shadow: inset 0 0 0 3px var(--app-accent-text) !important;
        }
        div[data-testid="stRadio"] [role="radiogroup"] [role="radio"] *,
        div[data-testid="stRadio"] [role="radiogroup"] [role="button"] * {
            color: var(--app-text) !important;
            background: transparent !important;
        }
        .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="radio"]::before,
        .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="button"]::before {
            border-radius: 999px !important;
        }
        .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="radio"][aria-checked="true"]::before,
        .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="button"][aria-pressed="true"]::before,
        .theme-toggle div[data-testid="stRadio"] [role="radiogroup"] [role="button"][aria-selected="true"]::before {
            background: transparent !important;
            box-shadow: inset 0 0 0 4px var(--app-accent) !important;
        }

        /* Hard override: remove selected label highlight, keep only checkbox/radio fill */
        div[data-testid="stRadio"] button,
        div[data-testid="stRadio"] [role="radio"],
        div[data-testid="stRadio"] [role="button"],
        div[data-testid="stRadio"] label {
            background-color: transparent !important;
            background-image: none !important;
            box-shadow: none !important;
            -webkit-tap-highlight-color: transparent !important;
            user-select: none !important;
            -webkit-user-select: none !important;
            -ms-user-select: none !important;
            cursor: pointer !important;
        }
        div[data-testid="stRadio"] * {
            background-color: transparent !important;
            background-image: none !important;
            box-shadow: none !important;
            -webkit-tap-highlight-color: transparent !important;
            user-select: none !important;
            -webkit-user-select: none !important;
            -ms-user-select: none !important;
        }
        div[data-testid="stRadio"] button::after,
        div[data-testid="stRadio"] [role="radio"]::after,
        div[data-testid="stRadio"] [role="button"]::after {
            background-color: transparent !important;
            box-shadow: none !important;
        }
        div[data-testid="stRadio"] [data-baseweb="button-group"] button > div,
        div[data-testid="stRadio"] [data-baseweb="button-group"] button > div > span,
        div[data-testid="stRadio"] [data-baseweb="button-group"] button span,
        div[data-testid="stRadio"] [data-baseweb="button-group"] button p {
            background-color: transparent !important;
            background-image: none !important;
            box-shadow: none !important;
            color: var(--app-text) !important;
        }
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"],
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"],
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"] {
            background-color: transparent !important;
            background-image: none !important;
            box-shadow: none !important;
            color: var(--app-text) !important;
        }
        div[data-testid="stRadio"] ::selection,
        div[data-testid="stRadio"] *::selection,
        div[data-testid="stCheckbox"] ::selection,
        div[data-testid="stCheckbox"] *::selection {
            background: transparent !important;
            color: inherit !important;
        }
        div[data-testid="stRadio"] ::-moz-selection,
        div[data-testid="stRadio"] *::-moz-selection,
        div[data-testid="stCheckbox"] ::-moz-selection,
        div[data-testid="stCheckbox"] *::-moz-selection {
            background: transparent !important;
            color: inherit !important;
        }
        div[data-testid="stRadio"] button:focus,
        div[data-testid="stRadio"] button:focus-visible,
        div[data-testid="stRadio"] button:active,
        div[data-testid="stRadio"] [role="radio"]:focus,
        div[data-testid="stRadio"] [role="radio"]:focus-visible,
        div[data-testid="stRadio"] [role="radio"]:active,
        div[data-testid="stRadio"] [role="button"]:focus,
        div[data-testid="stRadio"] [role="button"]:focus-visible,
        div[data-testid="stRadio"] [role="button"]:active {
            background-color: transparent !important;
            box-shadow: none !important;
            outline: none !important;
        }
        div[data-testid="stRadio"] button[aria-pressed="true"],
        div[data-testid="stRadio"] button[aria-selected="true"],
        div[data-testid="stRadio"] button[aria-checked="true"],
        div[data-testid="stRadio"] [role="radio"][aria-checked="true"],
        div[data-testid="stRadio"] [role="button"][aria-pressed="true"],
        div[data-testid="stRadio"] [role="button"][aria-selected="true"],
        div[data-testid="stRadio"] [aria-checked="true"] {
            background-color: transparent !important;
            background-image: none !important;
            box-shadow: none !important;
        }
        div[data-testid="stRadio"] button * ,
        div[data-testid="stRadio"] [role="radio"] *,
        div[data-testid="stRadio"] [role="button"] * {
            background-color: transparent !important;
            background-image: none !important;
            box-shadow: none !important;
        }
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-pressed="true"]::before,
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-checked="true"]::before,
        div[data-testid="stRadio"] [data-baseweb="button-group"] button[aria-selected="true"]::before,
        div[data-testid="stRadio"] [role="radiogroup"] [aria-checked="true"]::before,
        div[data-testid="stRadio"] [role="radiogroup"] [aria-pressed="true"]::before,
        div[data-testid="stRadio"] [role="radiogroup"] [aria-selected="true"]::before {
            background: var(--app-accent) !important;
            box-shadow: inset 0 0 0 3px var(--app-accent-text) !important;
        }

        div[data-testid="stCheckbox"] label,
        div[data-testid="stCheckbox"] [role="checkbox"],
        div[data-testid="stCheckbox"] [role="checkbox"] * {
            background-color: transparent !important;
            background-image: none !important;
            box-shadow: none !important;
        }
        div[data-testid="stCheckbox"] [role="checkbox"][aria-checked="true"] {
            background-color: transparent !important;
            box-shadow: none !important;
        }

        /* Final deterministic filter styling: no text highlight, only indicator fill */
        div[data-testid="stRadio"] [data-baseweb="button-group"] button.mfe-filter-radio,
        div[data-testid="stRadio"] [role="radiogroup"] [role="radio"].mfe-filter-radio,
        div[data-testid="stRadio"] [role="radiogroup"] [role="button"].mfe-filter-radio {
            background: transparent !important;
            background-color: transparent !important;
            background-image: none !important;
            box-shadow: none !important;
            border: none !important;
            color: var(--app-text) !important;
            display: inline-flex !important;
            align-items: center !important;
            gap: 0.5rem !important;
            min-height: 28px !important;
            padding: 0 !important;
            margin: 0 0.8rem 0 0 !important;
            position: relative !important;
            user-select: none !important;
            -webkit-user-select: none !important;
        }
        div[data-testid="stRadio"] .mfe-filter-radio * {
            background: transparent !important;
            background-color: transparent !important;
            background-image: none !important;
            box-shadow: none !important;
            color: var(--app-text) !important;
            text-shadow: none !important;
        }
        div[data-testid="stRadio"] .mfe-filter-radio-indicator {
            width: 16px !important;
            height: 16px !important;
            flex: 0 0 16px !important;
            border: 1.5px solid var(--app-accent) !important;
            border-radius: 4px !important;
            background: transparent !important;
            box-shadow: none !important;
            display: inline-block !important;
        }
        div[data-testid="stRadio"] .mfe-filter-radio.mfe-filter-radio-selected > .mfe-filter-radio-indicator {
            background: var(--app-accent) !important;
            box-shadow: inset 0 0 0 3px var(--app-accent-text) !important;
        }
        .theme-toggle div[data-testid="stRadio"] .mfe-filter-radio-indicator {
            border-radius: 999px !important;
        }
        .theme-toggle div[data-testid="stRadio"] .mfe-filter-radio.mfe-filter-radio-selected > .mfe-filter-radio-indicator {
            background: transparent !important;
            box-shadow: inset 0 0 0 4px var(--app-accent) !important;
        }
        div[data-testid="stRadio"] .mfe-filter-radio::selection,
        div[data-testid="stRadio"] .mfe-filter-radio *::selection {
            background: transparent !important;
            color: inherit !important;
        }

        /* Buttons */
        .stButton button,
        .stDownloadButton button {
            background: var(--app-surface) !important;
            color: var(--app-text) !important;
            border: 1px solid var(--app-border) !important;
        }

        /* Plotly text styling is left to Plotly to avoid conflicts. */

        /* Stock cards in dark mode: keep readable text on light cards */
        .company-card,
        .stock-metric-card {
            background: var(--card-bg) !important;
            color: var(--card-text) !important;
            border-color: var(--app-border) !important;
        }
        .company-card-name,
        .company-card-price,
        .stock-metric-value {
            color: var(--card-text) !important;
        }
        .stock-metric-label {
            color: var(--card-muted) !important;
        }

        /* Remove heading anchor icons */
        a.anchor-link {
            display: none !important;
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
        .replace("__CARD_BG__", card_bg)
        .replace("__CARD_TEXT__", card_text)
        .replace("__CARD_MUTED__", card_muted)
        .replace("__PLOT_BG__", plot_bg)
    )
    st.markdown(css, unsafe_allow_html=True)
    if not enable_dom_patch:
        return

    st.markdown(
        f"""
        <script>
        (function() {{
          const mode = "{mode}";
          document.body.classList.remove("theme-dark", "overview-dark");
          if (mode === "dark") {{
            document.body.classList.add("theme-dark");
          }}

          const isSelected = (el) => {{
            const attrs = ["aria-checked", "aria-pressed", "aria-selected", "data-selected", "data-active"];
            return attrs.some((attr) => (el.getAttribute(attr) || "").toLowerCase() === "true");
          }};

          const clearHighlight = (el) => {{
            el.style.setProperty("background", "transparent", "important");
            el.style.setProperty("background-color", "transparent", "important");
            el.style.setProperty("background-image", "none", "important");
            el.style.setProperty("box-shadow", "none", "important");
            el.style.setProperty("color", "var(--app-text)", "important");
          }};

          const ensureIndicator = (el) => {{
            let indicator = null;
            const first = el.firstElementChild;
            if (first && first.classList && first.classList.contains("mfe-filter-radio-indicator")) {{
              indicator = first;
            }} else {{
              indicator = document.createElement("span");
              indicator.className = "mfe-filter-radio-indicator";
              el.insertBefore(indicator, el.firstChild);
            }}
            return indicator;
          }};

          const patchRadio = (el) => {{
            if (!(el instanceof HTMLElement)) return;
            el.classList.add("mfe-filter-radio");
            clearHighlight(el);
            el.querySelectorAll("*").forEach((child) => {{
              if (child.classList && child.classList.contains("mfe-filter-radio-indicator")) return;
              clearHighlight(child);
            }});
            ensureIndicator(el);
            el.classList.toggle("mfe-filter-radio-selected", isSelected(el));
          }};

          const applyRadioFixes = () => {{
            document.querySelectorAll('div[data-testid="stRadio"] [data-baseweb="button-group"] button').forEach(patchRadio);
            document.querySelectorAll('div[data-testid="stRadio"] [role="radiogroup"] [role="radio"], div[data-testid="stRadio"] [role="radiogroup"] [role="button"]').forEach(patchRadio);
          }};

          if (window.__mfeRadioFixObserver) {{
            window.__mfeRadioFixObserver.disconnect();
            window.__mfeRadioFixObserver = null;
          }}

          let _animRunning = false;
          const scheduleFix = () => {{
            if (_animRunning) return;
            _animRunning = true;
            window.setTimeout(() => {{
              applyRadioFixes();
              _animRunning = false;
            }}, 0);
          }};

          scheduleFix();
          const observer = new MutationObserver((mutations) => {{
            for (const mutation of mutations) {{
              if (mutation.type === "childList") {{
                scheduleFix();
                return;
              }}
              if (
                mutation.type === "attributes" &&
                ["aria-checked", "aria-pressed", "aria-selected"].includes(mutation.attributeName || "")
              ) {{
                scheduleFix();
                return;
              }}
            }}
          }});
          const radioRoots = document.querySelectorAll('div[data-testid="stRadio"]');
          radioRoots.forEach((root) => {{
            observer.observe(root, {{
              subtree: true,
              childList: true,
              attributes: true,
              attributeFilter: ["aria-checked", "aria-pressed", "aria-selected"],
            }});
          }});
          window.__mfeRadioFixObserver = observer;
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )

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
