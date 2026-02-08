"""
Utilities to improve Streamlit page loading performance
"""

import streamlit as st
import time
from functools import lru_cache
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache the function
@lru_cache(maxsize=16)
def get_cached_processors(page_name):
    """Get cached processors for a specific page"""
    return {}

def load_company_data_in_background(companies, target_year, data_processor):
    """Pre-warm cache for improved page loading speed"""
    start_time = time.time()
    progress = 0
    total_ops = len(companies)
    
    # Create placeholder for progress
    progress_placeholder = st.empty()
    
    # Preload data for target year
    for i, company in enumerate(companies):
        # Update progress (ensure progress is between 0.0 and 1.0)
        progress = (i + 1) / total_ops
        progress_placeholder.progress(progress, text=f"Optimizing data for {company}...")
        
        # Pre-load data
        try:
            data_processor.get_metrics(company, target_year)
            if hasattr(data_processor, 'get_segments'):
                data_processor.get_segments(company, target_year)
        except Exception as e:
            logger.error(f"Error preloading data for {company}: {e}")
        
    # Clear progress
    progress_placeholder.empty()
    
    # Log timing
    load_time = time.time() - start_time
    logger.info(f"Preloaded data for {len(companies)} companies in {load_time:.2f} seconds")
    
def create_loading_animation():
    """Create a nicer loading animation for improved UX during long operations"""
    return st.markdown("""
        <style>
        @keyframes loading {
            0% { width: 0%; }
            50% { width: 100%; }
            100% { width: 0%; }
        }
        .loading-bar {
            height: 4px;
            background: linear-gradient(to right, #0068c9, #83c9ff);
            border-radius: 2px;
            animation: loading 2s ease-in-out infinite;
            margin: 10px 0;
        }
        </style>
        
        <div class="loading-bar"></div>
    """, unsafe_allow_html=True)