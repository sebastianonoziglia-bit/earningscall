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
    """
    # Create a placeholder and immediately clear it to help reset the page state
    clear_placeholder = st.empty()
    clear_placeholder.empty()
    
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
    
    /* Specifically target transparent elements that may persist */
    img[style*="opacity:0"], img[style*="opacity: 0"],
    div[style*="opacity:0"], div[style*="opacity: 0"] {
        display: none !important;
        height: 0 !important;
        width: 0 !important;
        position: absolute !important;
        top: -9999px !important;
        left: -9999px !important;
    }
    
    /* Force images to be properly removed between Digital Transformation and Executive Summary */
    .main .block-container div[data-testid="stVerticalBlock"] > div:nth-child(n+10):nth-child(-n+20) img {
        opacity: 1 !important; /* Make sure they're visible when they should be */
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
    
    # Add JavaScript to help clean up persisting elements between pages
    st.markdown("""
    <script>
    // This script runs in the Streamlit iframe to help clean up elements
    document.addEventListener('DOMContentLoaded', function() {
        // Function to clean up transparent elements
        function cleanupTransparentElements() {
            // Find all elements with opacity 0
            const transparentElements = document.querySelectorAll('[style*="opacity: 0"], [style*="opacity:0"]');
            transparentElements.forEach(el => {
                // Remove them from the DOM
                if (el.parentNode) {
                    el.parentNode.removeChild(el);
                }
            });
        }
        
        // Run cleanup on page load and periodically
        cleanupTransparentElements();
        setInterval(cleanupTransparentElements, 500);
    });
    </script>
    """, unsafe_allow_html=True)