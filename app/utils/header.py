import streamlit as st
from utils.language import init_language, render_language_selector
from utils.theme import apply_theme, render_theme_toggle

def display_header():
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

    # Apply theme after toggles are rendered
    apply_theme()
    
def render_header():
    """
    Alias for display_header for backward compatibility
    """
    return display_header()
