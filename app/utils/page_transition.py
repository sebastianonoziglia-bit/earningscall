"""
Utility for handling page transitions in the Streamlit application.
This prevents background elements from one page from showing up during transitions to another page.
"""

import streamlit as st

def apply_page_transition_fix():
    """
    Apply fixes to prevent page transition artifacts.
    This prevents UI elements from the previous page showing through
    while transitioning to the next page.

    IMPORTANT: This function is optimized to prevent unnecessary reruns.
    """
    # Only apply transition fix once per session to avoid reruns
    if 'page_transition_applied' not in st.session_state:
        st.session_state.page_transition_applied = True

        # Add CSS to properly clean up old page content during transitions
        st.markdown("""
        <style>
        /* Clear any lingering components during page transitions */
        .stApp iframe[height="0"] {
            display: none !important;
        }

        /* Prevent old background images from showing during transitions */
        body {
            background-image: none !important;
        }

        /* Ensure clean transition between pages */
        .element-container:empty {
            display: none !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        /* Avoid blanket opacity selectors (they can hide Plotly/SVG layers). */

        /* Force images to be properly removed between Digital Transformation and Executive Summary */
        .main .block-container div[data-testid="stVerticalBlock"] > div:nth-child(n+10):nth-child(-n+20) img {
            opacity: 1 !important;
            transition: opacity 0.2s ease-out;
        }

        /* Hide any ghost elements that might flash during transitions */
        .stApp.streamlit-wide .block-container {
            transition: opacity 0.15s ease-out;
        }

        /* Prevent flicker of old components during page load */
        @keyframes cleanPageTransition {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        .main .block-container {
            animation: cleanPageTransition 0.3s ease-in;
        }

        /* Force cleanup of lingering transparent elements */
        @media screen {
            .element-container:not(:hover) {
                transition: background-color 0.1s;
            }
        }
        </style>
        """, unsafe_allow_html=True)
