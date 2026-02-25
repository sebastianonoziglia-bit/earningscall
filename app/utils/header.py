import streamlit as st
from utils.language import init_language, render_language_selector
from utils.theme import apply_theme, render_theme_toggle


_NAV_ITEMS = [
    {"key": "home", "target": "Welcome.py", "label": "Home", "icon": "🏠", "query": "home"},
    {"key": "overview", "target": "pages/00_Overview.py", "label": "Overview", "icon": "📊", "query": "overview"},
    {"key": "earnings", "target": "pages/01_Earnings.py", "label": "Earnings", "icon": "💰", "query": "earnings"},
    {"key": "stocks", "target": "pages/02_Stocks.py", "label": "Stocks", "icon": "📈", "query": "stocks"},
    {"key": "editorial", "target": "pages/03_Editorial.py", "label": "Editorial", "icon": "📝", "query": "editorial"},
    {"key": "genie", "target": "pages/04_Genie.py", "label": "Genie", "icon": "🧞", "query": "genie"},
]

_QUERY_PAGE_MAP = {
    "home": "Welcome.py",
    "welcome": "Welcome.py",
    "overview": "pages/00_Overview.py",
    "earnings": "pages/01_Earnings.py",
    "01_earnings": "pages/01_Earnings.py",
    "stocks": "pages/02_Stocks.py",
    "editorial": "pages/03_Editorial.py",
    "genie": "pages/04_Genie.py",
    "financial_genie": "pages/04_Genie.py",
    "financial-genie": "pages/04_Genie.py",
}


def _first_param(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _route_query_navigation():
    query_params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
    if not query_params:
        return
    nav_param = _first_param(query_params.get("nav"))
    go_param = _first_param(query_params.get("go"))
    page_param = _first_param(query_params.get("page"))
    target_param = nav_param or go_param or page_param
    if not target_param:
        return
    target_key = str(target_param).strip().lower()
    target_page = _QUERY_PAGE_MAP.get(target_key)
    if not target_page:
        return
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.switch_page(target_page)


def _render_bottom_nav(active_key: str):
    chips = []
    for item in _NAV_ITEMS:
        active_class = " app-bottom-nav-item-active" if item["key"] == active_key else ""
        chips.append(
            f"<a class='app-bottom-nav-item{active_class}' href='?nav={item['query']}'>"
            f"{item['icon']} {item['label']}"
            "</a>"
        )
    st.markdown(
        """
        <style>
        .app-bottom-nav-wrap {
            position: fixed;
            left: 12px;
            right: 12px;
            bottom: 10px;
            z-index: 9999;
            display: flex;
            justify-content: center;
            pointer-events: none;
        }
        .app-bottom-nav {
            pointer-events: auto;
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding: 8px;
            border-radius: 14px;
            background: rgba(15,23,42,0.84);
            border: 1px solid rgba(148,163,184,0.34);
            backdrop-filter: blur(10px);
            box-shadow: 0 10px 28px rgba(2,6,23,0.26);
        }
        .app-bottom-nav-item {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 120px;
            padding: 8px 10px;
            border-radius: 10px;
            text-decoration: none !important;
            color: #E2E8F0 !important;
            font-size: 0.9rem;
            font-weight: 700;
            border: 1px solid rgba(148,163,184,0.25);
            background: rgba(30,41,59,0.65);
            white-space: nowrap;
        }
        .app-bottom-nav-item:hover {
            border-color: rgba(59,130,246,0.6);
            background: rgba(30,64,175,0.36);
            color: #FFFFFF !important;
        }
        .app-bottom-nav-item-active {
            border-color: rgba(59,130,246,0.95) !important;
            background: linear-gradient(135deg,#1D4ED8 0%, #2563EB 100%) !important;
            color: #FFFFFF !important;
        }
        .app-bottom-nav-spacer {
            height: 74px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='app-bottom-nav-wrap'><div class='app-bottom-nav'>{''.join(chips)}</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='app-bottom-nav-spacer'></div>", unsafe_allow_html=True)


def _render_top_nav():
    """Render visible top nav with active-page highlighting."""
    active_key = str(st.session_state.get("_active_nav_page", "")).strip().lower()
    st.markdown(
        """
        <style>
        .app-top-nav-note {
            margin: 0 0 6px 2px;
            font-size: 0.74rem;
            color: var(--app-muted, #64748B);
            letter-spacing: 0.06em;
            text-transform: uppercase;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='app-top-nav-note'>Navigation</div>", unsafe_allow_html=True)

    cols = st.columns(len(_NAV_ITEMS))
    for col, item in zip(cols, _NAV_ITEMS):
        with col:
            if st.button(
                f"{item['icon']} {item['label']}",
                key=f"global_top_nav_{item['key']}",
                use_container_width=True,
                type="primary" if item["key"] == active_key else "secondary",
            ):
                if item["key"] != active_key:
                    st.switch_page(item["target"])

    _render_bottom_nav(active_key)


def display_header(enable_dom_patch: bool = True):
    """
    Display the common header across all app pages.
    This includes language selection buttons.
    """
    _route_query_navigation()

    # Initialize language from URL query params or session state
    init_language()
    
    # Create three columns for the header layout
    left_col, center_col, right_col = st.columns([1, 4, 1])
    
    # Left column: Language selection
    with left_col:
        render_language_selector()

    # Right column: Theme toggle
    with right_col:
        st.markdown("<div class='theme-toggle-label'>Theme</div>", unsafe_allow_html=True)
        render_theme_toggle()
    
    # Space between panels
    st.markdown("<br>", unsafe_allow_html=True)

    # Replace sidebar app navigation with top navigation.
    st.session_state["hide_sidebar_nav"] = True
    _render_top_nav()

    # Apply theme after toggles are rendered
    apply_theme(enable_dom_patch=enable_dom_patch)
    

def render_header(enable_dom_patch: bool = True):
    """
    Alias for display_header for backward compatibility
    """
    return display_header(enable_dom_patch=enable_dom_patch)
