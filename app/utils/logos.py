"""
Lightweight logo loader for the Welcome page.
This avoids importing AI/chat/data modules that can trigger heavy initialization.
"""

import base64
import logging
import os
from pathlib import Path

import streamlit as st

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@st.cache_data(ttl=3600, show_spinner=False)
def load_company_logos():
    """Load and cache company logos - reusable across pages."""
    try:
        # Use absolute path so it works regardless of cwd (HF vs local)
        _ASSETS = Path(__file__).resolve().parent.parent / "attached_assets"

        def _first_existing(*candidates: str):
            for p in candidates:
                full = _ASSETS / p if not Path(p).is_absolute() else Path(p)
                if full.exists():
                    return str(full)
            return None

        def _a(name: str) -> str:
            """Resolve asset path to absolute."""
            return str(_ASSETS / name)

        logo_files = {
            'Apple': _a('apple_logo.png'),
            'Microsoft': _a('msft.png'),
            'Alphabet': _a('Google_logo.png'),
            'Netflix': _a('Netflix_logo.png'),
            'Meta Platforms': _a('Meta_logo.png'),
            'WhatsApp': _first_existing('Whatsapp_logo.png', 'Meta_logo.png'),
            'Instagram': _first_existing('Instagram_logo.png', 'Meta_logo.png'),
            'Facebook': _first_existing('Facebook.png', 'Meta_logo.png'),
            'Amazon': _a('Amazon_icon.png'),
            'Disney': _a('icons8-logo-disney-240.png'),
            'Roku': _a('roku_logo.png'),
            'Spotify': _a('Spotify_logo.png'),
            'Comcast': _a('Comcast_logo.png'),
            'Paramount': _a('Paramount_logo.png'),
            'Paramount Global': _a('Paramount_logo.png'),
            'Warner Bros. Discovery': _a('WarnerBrosDiscovery_log.png'),
            'Warner Bros Discovery': _a('WarnerBrosDiscovery_log.png'),
            'YouTube': _first_existing('Youtube_logo.png', 'Google_logo.png'),
            'Samsung': _a('samsung_logo.png'),
            'Tencent': _a('Tencent_logo.png'),
            'Nvidia': _a('Nvidia_logo.png'),
        }

        for company, logo_path in logo_files.items():
            if logo_path and os.path.exists(logo_path):
                logger.info(f"Logo file exists for {company}: {logo_path}")
            else:
                logger.warning(f"Logo file MISSING for {company}: {logo_path}")

        logos_dict = {}
        for company, logo_path in logo_files.items():
            if not logo_path or not os.path.exists(logo_path):
                continue
            try:
                with open(logo_path, "rb") as f:
                    img_str = base64.b64encode(f.read()).decode()
                logos_dict[company] = img_str
                logger.info(f"Successfully loaded logo for {company}")
            except Exception as e:
                logger.error(f"Error loading logo for {company}: {str(e)}")

        return logos_dict
    except Exception as e:
        logger.error(f"Error loading company logos: {str(e)}")
        return {}
