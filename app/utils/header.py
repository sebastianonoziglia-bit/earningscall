import streamlit as st
from utils.language import init_language
from utils.theme import apply_theme


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

_SUPPORTED_LANGS = {"en", "it", "es"}


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


def _apply_query_language():
    query_params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
    if not query_params:
        return
    lang_param = _first_param(query_params.get("lang"))
    if not lang_param:
        return
    lang_code = str(lang_param).strip().lower()
    if lang_code in _SUPPORTED_LANGS:
        st.session_state.language = lang_code


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


def _render_sticky_top_bar(active_key: str):
    nav_links = []
    for item in _NAV_ITEMS:
        active_class = " active" if item["key"] == active_key else ""
        nav_links.append(
            f"<a href='?nav={item['query']}' class='{active_class}'>{item['icon']} {item['label']}</a>"
        )

    current_lang = str(st.session_state.get("language", "en")).strip().lower()
    lang_en_cls = "active" if current_lang == "en" else ""
    lang_it_cls = "active" if current_lang == "it" else ""
    lang_es_cls = "active" if current_lang == "es" else ""

    st.markdown(
        f"""
        <style>
          .app-top-bar {{
            position: sticky; top: 0; z-index: 9998;
            background: rgba(255,255,255,0.93);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(15,23,42,0.10);
            padding: 7px 18px;
            display: flex; align-items: center; gap: 5px;
            margin: 0 -1.5rem 0.5rem -1.5rem;
          }}
          .app-top-bar a {{
            display: inline-flex; align-items: center; gap: 5px;
            padding: 6px 14px; border-radius: 8px;
            text-decoration: none !important;
            font-size: 0.88rem; font-weight: 700;
            color: #475569 !important;
            border: 1px solid transparent;
            transition: background 0.15s, color 0.15s;
            white-space: nowrap;
          }}
          .app-top-bar a:hover {{ background: #f1f5f9; color: #0f172a !important; }}
          .app-top-bar a.active {{
            background: #1d4ed8; color: #fff !important;
            border-color: #1e40af;
          }}
          .app-top-bar .app-top-bar-spacer {{
            flex: 1;
          }}
          .app-top-bar .lang-link {{
            padding: 6px 10px;
            min-width: 38px;
            justify-content: center;
          }}
        </style>
        <div class="app-top-bar">
          {''.join(nav_links)}
          <span class="app-top-bar-spacer"></span>
          <a href="?lang=en" class="lang-link {lang_en_cls}">🇺🇸</a>
          <a href="?lang=it" class="lang-link {lang_it_cls}">🇮🇹</a>
          <a href="?lang=es" class="lang-link {lang_es_cls}">🇪🇸</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def display_header(enable_dom_patch: bool = True):
    """
    Display the common header across all app pages.
    This includes language selection buttons.
    """
    _route_query_navigation()
    _apply_query_language()

    # Initialize language from URL query params or session state
    init_language()

    # Replace sidebar app navigation with top navigation.
    st.session_state["hide_sidebar_nav"] = True
    active_key = str(
        st.session_state.get("active_nav_page")
        or st.session_state.get("_active_nav_page")
        or ""
    ).strip().lower()
    _render_sticky_top_bar(active_key)
    _render_bottom_nav(active_key)

    # Apply global styles/theme utilities (theme toggle removed).
    apply_theme(enable_dom_patch=enable_dom_patch)
    

def render_header(enable_dom_patch: bool = True):
    """
    Alias for display_header for backward compatibility
    """
    return display_header(enable_dom_patch=enable_dom_patch)
