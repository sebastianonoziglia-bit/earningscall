import streamlit as st
from utils.language import init_language, render_language_selector

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
    
    # Space between panels
    st.markdown("<br>", unsafe_allow_html=True)
    
def render_header():
    """
    Alias for display_header for backward compatibility
    """
    return display_header()