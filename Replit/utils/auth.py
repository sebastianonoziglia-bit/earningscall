import streamlit as st
from utils.time_utils import render_floating_clock

def check_password():
    """
    Temporarily bypassed authentication check
    Simply render the floating clock without checking login status
    """
    # Auto-login for testing
    if not st.session_state.get('logged_in', False):
        st.session_state.logged_in = True
    
    # Render the floating clock on authenticated pages
    render_floating_clock()

def force_refresh():
    """Force a complete page refresh"""
    st.experimental_rerun()