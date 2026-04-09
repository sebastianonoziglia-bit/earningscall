import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as _components
from utils.language import init_language
from utils.theme import apply_theme


@st.cache_data(show_spinner=False)
def _load_hero_video_b64() -> str:
    """Read HeroVideo.mp4 and return base64-encoded string (cached in memory)."""
    video_path = Path(__file__).resolve().parent.parent / "attached_assets" / "HeroVideo.mp4"
    if not video_path.exists():
        return ""
    with open(video_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _inject_hero_loader():
    """Inject full-screen video overlay on first visit per browser session.

    Uses sessionStorage so the video only plays once per browser tab session.
    Also skips injection after the first Streamlit page to avoid re-sending 5 MB.
    """
    if st.session_state.get("_hero_shown"):
        return
    st.session_state["_hero_shown"] = True

    video_b64 = _load_hero_video_b64()
    if not video_b64:
        return

    _components.html(
        f"""<script>
(function(){{
  // sessionStorage guard — skip if video already played this browser session
  if(sessionStorage.getItem('_heroPlayed')){{return;}}
  sessionStorage.setItem('_heroPlayed','1');

  var pd=window.parent.document;
  if(!pd){{return;}}

  // Remove any stale overlay from a previous attempt
  var old=pd.getElementById('hero-loader-ov');
  if(old)old.parentNode.removeChild(old);

  // Full-screen overlay
  var ov=pd.createElement('div');
  ov.id='hero-loader-ov';
  ov.style.cssText='position:fixed;top:0;left:0;width:100vw;height:100vh;'
    +'background:#000;z-index:2147483647;overflow:hidden;display:flex;'
    +'align-items:center;justify-content:center;transition:opacity 0.6s ease;';

  var vid=pd.createElement('video');
  vid.src='data:video/mp4;base64,{video_b64}';
  vid.autoplay=true;
  vid.muted=true;
  vid.playsInline=true;
  vid.style.cssText='width:100%;height:100%;object-fit:cover;';

  ov.appendChild(vid);
  pd.body.appendChild(ov);
  pd.body.style.overflow='hidden';

  // Inject dismiss logic as a script in the PARENT document so it
  // survives even if Streamlit destroys this iframe during a rerun.
  var s=pd.createElement('script');
  s.textContent='(function(){{'
    +'var ov=document.getElementById("hero-loader-ov");'
    +'if(!ov)return;'
    +'var vid=ov.querySelector("video");'
    +'function dismiss(){{'
    +'  if(ov._dismissed)return;ov._dismissed=true;'
    +'  ov.style.opacity="0";'
    +'  document.body.style.overflow="";'
    +'  setTimeout(function(){{if(ov.parentNode)ov.parentNode.removeChild(ov);}},650);'
    +'}}'
    +'if(vid)vid.addEventListener("ended",dismiss);'
    +'setTimeout(dismiss,12000);'
    +'ov.addEventListener("click",dismiss);'
    +'if(vid)vid.play().catch(function(){{dismiss();}});'
    +'}})();';
  pd.body.appendChild(s);
}})();
</script>""",
        height=0,
    )


_NAV_ITEMS = [
    {"key": "home",      "target": "Welcome.py",          "label": "Home",      "query": "home"},
    {"key": "overview",  "target": "pages/00_Overview.py", "label": "Overview",  "query": "overview"},
    {"key": "earnings",  "target": "pages/01_Earnings.py", "label": "Earnings",  "query": "earnings"},
    {"key": "stocks",    "target": "pages/02_Stocks.py",   "label": "Stocks",    "query": "stocks"},
    {"key": "editorial", "target": "pages/03_Editorial.py","label": "Editorial", "query": "editorial"},
    {"key": "genie",     "target": "pages/04_Genie.py",    "label": "Genie",     "query": "genie"},
    {"key": "oracle",    "target": "pages/06_Oracle.py",   "label": "Oracle",    "query": "oracle"},
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
    "oracle": "pages/06_Oracle.py",
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
    current_key = str(
        st.session_state.get("active_nav_page")
        or st.session_state.get("_active_nav_page")
        or ""
    ).strip().lower()
    current_page = _QUERY_PAGE_MAP.get(current_key, "")
    if target_key == current_key or (current_page and target_page == current_page):
        # Already on the right page — clear stale nav param to prevent redirect loops
        try:
            if hasattr(st, "query_params"):
                for _k in ("nav", "go", "page"):
                    if _k in st.query_params:
                        del st.query_params[_k]
        except Exception:
            pass
        return
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
        if str(st.session_state.get("language", "")).strip().lower() != lang_code:
            st.session_state.language = lang_code


def _render_nav(active_key: str):
    current_lang = str(st.session_state.get("language", "en")).strip().lower()

    # Streamlit layout fixes (still via markdown — these work fine)
    st.markdown(
        """
        <style>
          header[data-testid="stHeader"] { display:none!important; height:0!important; }
          [data-testid="stToolbar"]       { display:none!important; height:0!important; }
          .stApp > header                 { display:none!important; }
          [data-testid="stAppViewContainer"]                          { padding-top:0!important; margin-top:0!important; }
          [data-testid="stAppViewContainer"] > .main,
          [data-testid="stAppViewContainer"] > section.main          { padding-top:0!important; margin-top:0!important; }
          #root > div:first-child                                     { padding-top:0!important; }
          .block-container,
          [data-testid="stAppViewContainer"] > .main .block-container,
          [data-testid="stAppViewContainer"] > section > div.block-container,
          section.main > div.block-container                          { padding-top:0!important; margin-top:0!important; }
          .main .block-container > div:first-child                    { margin-top:0!important; }
          [data-testid="stMarkdownContainer"]:has(> style:only-child),
          [data-testid="element-container"]:has([data-testid="stMarkdownContainer"] > style:only-child),
          [data-testid="stMarkdownContainer"]:has(> script:only-child),
          [data-testid="element-container"]:has([data-testid="stMarkdownContainer"] > script:only-child) {
            margin:0!important; padding:0!important;
            height:0!important; min-height:0!important;
            line-height:0!important; overflow:hidden!important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Nav pill via st.markdown (proven to work with position:fixed in Streamlit).
    # Uses direct page-slug URLs — NO ?nav= query params.
    _SLUG = {"home": ".", "overview": "Overview", "earnings": "Earnings",
             "stocks": "Stocks", "editorial": "Editorial", "genie": "Genie",
             "oracle": "Oracle"}

    nav_links = ""
    for item in _NAV_ITEMS:
        active_cls = " bnav-active" if item["key"] == active_key else ""
        slug = _SLUG.get(item["key"], ".")
        nav_links += (
            f"<a href='{slug}' target='_self' rel='noopener' "
            f"class='bnav-link{active_cls}'>{item['label']}</a>"
        )

    lang_en_cls = " bnav-lang-active" if current_lang == "en" else ""
    lang_it_cls = " bnav-lang-active" if current_lang == "it" else ""
    lang_es_cls = " bnav-lang-active" if current_lang == "es" else ""

    st.markdown(
        f"""
        <style>
          [data-testid="element-container"]:has(.app-bottom-nav),
          [data-testid="stMarkdownContainer"]:has(.app-bottom-nav) {{
            margin: 0 !important; padding: 0 !important;
            height: 0 !important; min-height: 0 !important;
            overflow: visible !important; line-height: 0 !important;
          }}
          .app-bottom-nav {{
            position: fixed; bottom: 16px; left: 50%;
            transform: translateX(-50%); z-index: 9999;
            background: rgba(15,23,42,0.95); backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.1); border-radius: 50px;
            padding: 6px 12px; display: flex; align-items: center; gap: 2px;
          }}
          .bnav-link {{
            display: inline-flex; align-items: center;
            padding: 5px 13px; border-radius: 20px;
            text-decoration: none !important;
            font-size: 0.82rem; font-weight: 500;
            color: #94a3b8 !important;
            border: 1px solid transparent;
            background: transparent;
            transition: color 0.2s, text-shadow 0.2s, background 0.2s;
            white-space: nowrap;
          }}
          .bnav-link:hover {{
            color: #ffffff !important;
            text-shadow: 0 0 8px rgba(74,174,255,0.5), 0 0 20px rgba(74,174,255,0.25);
            background: rgba(74,174,255,0.08);
          }}
          .bnav-active {{
            color: #fff !important;
            font-weight: 700 !important;
            text-shadow: 0 0 6px rgba(74,174,255,0.4);
            background: rgba(74,174,255,0.12);
          }}
          .bnav-sep {{
            width: 1px; height: 20px;
            background: rgba(148,163,184,0.2);
            margin: 0 6px; flex-shrink: 0;
          }}
          .bnav-lang {{
            display: inline-flex; align-items: center;
            padding: 5px 8px; border-radius: 20px;
            text-decoration: none !important;
            font-size: 0.85rem;
            border: 1px solid transparent;
            transition: border-color 0.15s;
            opacity: 0.5;
          }}
          .bnav-lang:hover {{ opacity: 1; border-color: rgba(148,163,184,0.4) !important; }}
          .bnav-lang-active {{ opacity: 1 !important; border-color: rgba(148,163,184,0.3) !important; }}
        </style>
        <div class="app-bottom-nav">
          {nav_links}
          <span class="bnav-sep"></span>
          <a href="?lang=en" target="_self" rel="noopener" class="bnav-lang{lang_en_cls}">🇺🇸</a>
          <a href="?lang=it" target="_self" rel="noopener" class="bnav-lang{lang_it_cls}">🇮🇹</a>
          <a href="?lang=es" target="_self" rel="noopener" class="bnav-lang{lang_es_cls}">🇪🇸</a>
        </div>
        <div class="app-bottom-nav-spacer" style="height:80px;"></div>
        """,
        unsafe_allow_html=True,
    )


def display_header(enable_dom_patch: bool = True):
    """Display the common header across all app pages."""
    _inject_hero_loader()
    # NOTE: _route_query_navigation() intentionally removed —
    # all navigation now uses direct page URLs, not ?nav= params.
    # Clear any stale ?nav= params so they don't linger in the URL bar.
    try:
        if hasattr(st, "query_params"):
            for _k in ("nav", "go", "page"):
                if _k in st.query_params:
                    del st.query_params[_k]
    except Exception:
        pass
    _apply_query_language()
    init_language()
    st.session_state["hide_sidebar_nav"] = True
    active_key = str(
        st.session_state.get("active_nav_page")
        or st.session_state.get("_active_nav_page")
        or ""
    ).strip().lower()
    _render_nav(active_key)
    apply_theme(enable_dom_patch=enable_dom_patch)


def render_header(enable_dom_patch: bool = True):
    """Alias for display_header for backward compatibility."""
    return display_header(enable_dom_patch=enable_dom_patch)
