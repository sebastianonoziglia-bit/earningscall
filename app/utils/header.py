import streamlit as st
from utils.language import init_language, render_language_selector
from utils.theme import apply_theme, render_theme_toggle


def _render_top_nav():
    """Render page navigation buttons in-header (sidebar is disabled globally)."""
    nav_items = [
        ("Welcome.py", "Home", "🏠"),
        ("pages/00_Overview.py", "Overview", "📊"),
        ("pages/01_Earnings.py", "Earnings", "💰"),
        ("pages/02_Stocks.py", "Stocks", "📈"),
        ("pages/04_Genie.py", "Genie", "🧞"),
    ]
    cols = st.columns(len(nav_items))
    for col, (target, label, icon) in zip(cols, nav_items):
        with col:
            try:
                st.page_link(target, label=label, icon=icon, use_container_width=True)
            except Exception:
                # Fallback for older Streamlit builds.
                st.markdown(f"[{icon} {label}]({target})")


def display_header(enable_dom_patch: bool = True):
    """
    Display the common header across all app pages.
    This includes language selection buttons.
    """
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
