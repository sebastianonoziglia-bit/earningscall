"""
Common UI components for the dashboard application.
Includes the AI assistant interface that can be used on all pages.
"""

import streamlit as st
import logging
import os
import subprocess
import time
from utils.state_management import get_data_processor
from PIL import Image
import base64
from io import BytesIO
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@st.cache_data(ttl=3600)
def load_company_logos():
    """Load and cache company logos - reusable across pages"""
    try:
        def _first_existing(*candidates: str):
            for p in candidates:
                if p and Path(p).exists():
                    return p
            return None

        logo_files = {
            'Apple': 'attached_assets/8.png',
            'Microsoft': 'attached_assets/msft.png',
            'Alphabet': 'attached_assets/10.png',
            'Netflix': 'attached_assets/9.png',
            'Meta Platforms': 'attached_assets/12.png',
            # Meta-owned apps: prefer dedicated logos if present, otherwise fall back to Meta.
            'WhatsApp': _first_existing('attached_assets/Whatsapp.png', 'attached_assets/WhatsApp.png', 'attached_assets/12.png'),
            'Instagram': _first_existing('attached_assets/Instagram.png', 'attached_assets/12.png'),
            'Facebook': _first_existing('attached_assets/Facebook.png', 'attached_assets/12.png'),
            'Amazon': 'attached_assets/Amazon_icon.png',
            'Disney': 'attached_assets/icons8-logo-disney-240.png',
            'Roku': 'attached_assets/rokudef.png',
            'Spotify': 'attached_assets/11.png',
            'Comcast': 'attached_assets/6.png',
            'Paramount': 'attached_assets/Paramount.png',
            'Paramount Global': 'attached_assets/Paramount.png', # Add mapping for full name
            'Warner Bros. Discovery': 'attached_assets/adadad.png',
            'Warner Bros Discovery': 'attached_assets/adadad.png', # Keep compatibility without period
        }
        
        # Print which logo files exist for debugging
        for company, logo_path in logo_files.items():
            if os.path.exists(logo_path):
                logger.info(f"Logo file exists for {company}: {logo_path}")
            else:
                logger.warning(f"Logo file MISSING for {company}: {logo_path}")
        
        # Load and convert each logo to base64
        logos_dict = {}
        for company, logo_path in logo_files.items():
            if not logo_path or not os.path.exists(logo_path):
                continue
                
            try:
                # Open the image and convert to base64
                img = Image.open(logo_path)
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                logos_dict[company] = img_str
                logger.info(f"Successfully loaded logo for {company}")
            except Exception as e:
                logger.error(f"Error loading logo for {company}: {str(e)}")
        
        return logos_dict
    except Exception as e:
        logger.error(f"Error loading company logos: {str(e)}")
        return {}

def render_company_logos(size="small"):
    """Render company logos with hover effect - reusable across pages"""
    # Get the cached logos
    company_logos = load_company_logos()
    
    # Debug the loaded logos
    logger.info(f"Loaded {len(company_logos)} company logos")
    
    # Add CSS for company logos
    st.markdown("""
    <style>
        .header-logo-container {
            display: inline-block;
            margin: 0.5rem;
            padding: 0.5rem;
            text-align: center;
            transition: all 0.3s ease;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .header-logo {
            width: 50px;
            height: 50px;
            object-fit: contain;
            transition: all 0.3s ease;
        }
        .paramount-logo {
            width: 60px;  /* Larger than standard logo size */
            height: 60px;
            object-fit: contain;
            transition: all 0.3s ease;
        }
        .header-logo-container:hover .header-logo, 
        .header-logo-container:hover .paramount-logo {
            transform: scale(1.2);
            filter: drop-shadow(0 0 5px rgba(0,0,0,0.3));
        }
        .header-logos-flex {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            align-items: center;
            gap: 0.8rem;
            margin-bottom: 1.5rem;
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Simple check to ensure we have logos loaded
    if not company_logos:
        st.warning("No company logos could be loaded")
        return
    
    # Create a container with all logos
    logo_html = '<div class="header-logos-flex">'
    
    # Combine all company names into a single array
    all_companies = [
        'Alphabet', 'Microsoft', 'Apple', 'Netflix', 'Meta Platforms',
        'Amazon', 'Disney', 'Roku', 'Spotify', 'Comcast',
        'Paramount Global', 'Warner Bros. Discovery'
    ]
    
    # Add all logos in a single row with flexible wrapping
    for company in all_companies:
        if company in company_logos and company_logos[company]:
            # Use special class for Paramount logo to make it larger
            logo_class = 'paramount-logo' if company == 'Paramount Global' or company == 'Paramount' else 'header-logo'
            logo_html += f"""
            <div class='header-logo-container'>
                <img src='data:image/png;base64,{company_logos[company]}' class='{logo_class}' title="{company}">
            </div>
            """
            
    logo_html += '</div>'
    
    # Display the logos
    st.markdown(logo_html, unsafe_allow_html=True)

def render_ai_assistant(location="sidebar", width=None, height=None, current_page=None):
    """
    Render the AI Assistant component that can be used on any page
    
    Args:
        location: Where to place the assistant - "sidebar" or "main" (in the main content area)
        width: Width of the assistant component (for main area)
        height: Height of the assistant component (for main area)
        current_page: Current page name for context
    """
    try:
        hide_sidebar = bool(st.session_state.get("hide_sidebar_nav", False))
        if location == "sidebar" and hide_sidebar:
            container = st
        else:
            container = st.sidebar if location == "sidebar" else st
        page_name = str(current_page or st.session_state.get("current_page", "Overview")).strip() or "Overview"
        section_name = str(
            st.session_state.get("overview_current_section")
            or st.session_state.get("global_time_context", {}).get("page")
            or page_name
        ).strip()
        year_value = int(st.session_state.get("selected_year", st.session_state.get("earnings_selected_year", 2024)))
        quarter_value = str(
            st.session_state.get("selected_quarter", st.session_state.get("earnings_selected_quarter", "Q4"))
        ).strip()

        repo_root = Path(__file__).resolve().parents[2]
        db_path = repo_root / "earningscall_intelligence.db"

        container.markdown("---")
        with container.expander("🤖 Earningscall Intelligence Assistant", expanded=False):
            container.caption(f"Context: {section_name} · {year_value} {quarter_value}")
            if not db_path.exists():
                container.info(
                    "Intelligence DB not found. Run `python3 scripts/sync_all_intelligence.py` "
                    "to build the transcript/topic/KPI SQL layer."
                )
                return

            from utils.ai_assistant import EarningscallAI  # noqa: WPS433

            assistant = EarningscallAI(
                db_path=str(db_path),
                current_section=section_name,
                current_year=year_value,
                current_quarter=quarter_value,
            )

            state_key = f"ai_assistant_answer_{location}_{page_name}".replace(" ", "_").lower()
            question_key = f"ai_assistant_question_{location}_{page_name}".replace(" ", "_").lower()
            ask_key = f"ai_assistant_ask_{location}_{page_name}".replace(" ", "_").lower()

            container.markdown("**Suggested questions**")
            for idx, suggestion in enumerate(assistant.get_suggested_questions(section_name)[:4]):
                if container.button(suggestion, key=f"{state_key}_suggested_{idx}"):
                    st.session_state[state_key] = assistant.answer(suggestion)

            user_question = container.text_input("Ask your own question", key=question_key)
            if container.button("Ask", key=ask_key):
                if user_question.strip():
                    st.session_state[state_key] = assistant.answer(user_question.strip())
                else:
                    st.session_state[state_key] = "Please enter a question first."

            answer = st.session_state.get(state_key, "")
            if answer:
                container.markdown(answer)

    except Exception as e:
        logger.error(f"Error rendering AI Assistant: {str(e)}")
        hide_sidebar = bool(st.session_state.get("hide_sidebar_nav", False))
        if location == "sidebar" and not hide_sidebar:
            st.sidebar.error("Error displaying AI Assistant.")
        else:
            st.error("Error displaying AI Assistant.")
