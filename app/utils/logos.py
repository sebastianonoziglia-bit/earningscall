"""
Lightweight logo loader for the Welcome page.
This avoids importing AI/chat/data modules that can trigger heavy initialization.
"""

import base64
import logging
import os
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@st.cache_data(ttl=3600)
def load_company_logos():
    """Load and cache company logos - reusable across pages."""
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
            'WhatsApp': _first_existing('attached_assets/Whatsapp.png', 'attached_assets/WhatsApp.png', 'attached_assets/12.png'),
            'Instagram': _first_existing('attached_assets/Instagram.png', 'attached_assets/12.png'),
            'Facebook': _first_existing('attached_assets/Facebook.png', 'attached_assets/12.png'),
            'Amazon': 'attached_assets/Amazon_icon.png',
            'Disney': 'attached_assets/icons8-logo-disney-240.png',
            'Roku': 'attached_assets/rokudef.png',
            'Spotify': 'attached_assets/11.png',
            'Comcast': 'attached_assets/6.png',
            'Paramount': 'attached_assets/Paramount.png',
            'Paramount Global': 'attached_assets/Paramount.png',
            'Warner Bros. Discovery': 'attached_assets/adadad.png',
            'Warner Bros Discovery': 'attached_assets/adadad.png',
        }

        for company, logo_path in logo_files.items():
            if os.path.exists(logo_path):
                logger.info(f"Logo file exists for {company}: {logo_path}")
            else:
                logger.warning(f"Logo file MISSING for {company}: {logo_path}")

        logos_dict = {}
        for company, logo_path in logo_files.items():
            if not logo_path or not os.path.exists(logo_path):
                continue
            try:
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
