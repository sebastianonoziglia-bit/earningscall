# Set page config must be the first Streamlit command
import streamlit as st
st.set_page_config(page_title="Welcome", page_icon="📊", layout="wide")
from utils.theme import apply_theme
apply_theme()

# Handle logo navigation via query params
query_params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()

def _first_param(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value

nav_param = _first_param(query_params.get("nav")) if query_params else None
go_param = _first_param(query_params.get("go")) if query_params else None
page_param = _first_param(query_params.get("page")) if query_params else None
company_param = _first_param(query_params.get("company")) if query_params else None

target_param = nav_param or go_param or page_param
if target_param and str(target_param).lower() in {"earnings", "01_earnings"}:
    if company_param:
        st.session_state["prefill_company"] = company_param
    st.switch_page("pages/01_Earnings.py")

# After page config, import and initialize session state
from utils.state_management import initialize_session_state
initialize_session_state()


# Custom CSS for sidebar navigation items - particularly Financial Genie
st.markdown('''
<style>

/* Apply Montserrat font globally to all elements */
html, body, [class*="css"] {
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 400;
}

/* Main content area */
.main .block-container {
    font-family: 'Montserrat', sans-serif !important;
}

/* Headers and titles - Montserrat Medium */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 500 !important;
}

/* Streamlit specific elements */
.stMarkdown, .stText {
    font-family: 'Montserrat', sans-serif !important;
}

/* Sidebar */
.css-1d391kg {
    font-family: 'Montserrat', sans-serif !important;
}

/* Buttons */
.stButton button {
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 500 !important;
}

/* Selectbox and input elements */
.stSelectbox label, .stTextInput label, .stNumberInput label {
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 500 !important;
}

/* Tab labels */
.stTabs [data-baseweb="tab-list"] button {
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 500 !important;
}

/* Expander headers */
.streamlit-expanderHeader {
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 500 !important;
}

/* All paragraph text */
p {
    font-family: 'Montserrat', sans-serif !important;
}

/* List items */
li {
    font-family: 'Montserrat', sans-serif !important;
}

/* Ensure all divs inherit the font */
div {
    font-family: 'Montserrat', sans-serif !important;
}

/* Override any remaining default fonts */
* {
    font-family: 'Montserrat', sans-serif !important;
}
/* Custom styling for the Financial Genie in the sidebar */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] div.element-container:has(a[href*="Genie"]) {
    background-color: #f3f4f6;
    border-radius: 4px;
    padding: 5px;
    margin-bottom: 5px;
    border-left: 3px solid #0073ff;
}

/* Style for the Genie page in sidebar */
section[data-testid="stSidebar"] a[href*="Genie"]::after {
    content: " (SPECIAL)";
    color: #374151;
    font-weight: bold;
    font-size: 0.8em;
}

/* Direct coloring for the Financial Genie (SPECIAL) text in the expander */
.st-emotion-cache-19rxjzo:has(> .st-emotion-cache-16idsys:contains("Financial Genie")) .st-emotion-cache-16idsys p {
    display: inline;
}
.st-emotion-cache-19rxjzo:has(> .st-emotion-cache-16idsys:contains("Financial Genie")) .st-emotion-cache-16idsys p::after {
    content: " (SPECIAL)";
    color: #374151;
    font-weight: bold;
    font-size: 0.8em;
    margin-left: 4px;
}
</style>
''', unsafe_allow_html=True)


# Import other modules after setting page config
import logging
import os
import base64
import time
import textwrap
from datetime import datetime
from urllib.parse import quote
from utils.time_utils import render_floating_clock
from utils.state_management import get_data_processor
from utils.language import init_language, get_text, get_greeting_translated
from utils.header import display_header
from utils.sql_assistant_sidebar import render_sql_assistant_sidebar
from utils.page_transition import apply_page_transition_fix

# Apply fix for page transitions to prevent background bleed-through
apply_page_transition_fix()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "attached_assets")

def get_greeting():
    """Return time-appropriate greeting"""
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"

@st.cache_data(show_spinner=False)
def load_company_logos():
    """Load and cache company logos"""
    try:
        logo_files = {
            'Apple': os.path.join(ASSETS_DIR, "8.png"),
            'Microsoft': os.path.join(ASSETS_DIR, "msft.png"),
            'Alphabet': os.path.join(ASSETS_DIR, "10.png"),
            'Netflix': os.path.join(ASSETS_DIR, "9.png"),
            'Meta Platforms': os.path.join(ASSETS_DIR, "12.png"),
            'Amazon': os.path.join(ASSETS_DIR, "Amazon_icon.png"),
            'Disney': os.path.join(ASSETS_DIR, "icons8-logo-disney-240.png"),
            'Roku': os.path.join(ASSETS_DIR, "rokudef.png"),
            'Spotify': os.path.join(ASSETS_DIR, "11.png"),
            'Comcast': os.path.join(ASSETS_DIR, "6.png"),
            'Paramount': os.path.join(ASSETS_DIR, "Paramount.png"),
            'Paramount Global': os.path.join(ASSETS_DIR, "Paramount.png"),
            'Warner Bros Discovery': os.path.join(ASSETS_DIR, "adadad.png"),
            'Warner Bros. Discovery': os.path.join(ASSETS_DIR, "adadad.png"),
            'More': os.path.join(ASSETS_DIR, "Coming soon.png"),
        }

        logos = {}
        for company, path in logo_files.items():
            if os.path.exists(path):
                try:
                    with open(path, "rb") as img_file:
                        logos[company] = base64.b64encode(img_file.read()).decode()
                except Exception as e:
                    logger.error(f"Error loading logo for {company}: {str(e)}")
                    continue
        return logos
    except Exception as e:
        logger.error(f"Error in load_company_logos: {str(e)}")
        return {}

# Initialize session state - no password authentication
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.logged_in = True  # Always logged in, no password required
    st.session_state.show_login = False
    st.session_state.first_time_user = False  # Skip first-time tutorial

# Define company_logos variable at the global scope
company_logos = {}

# Hero image with loading state
background_path = os.path.join(ASSETS_DIR, "FAQ MFE.png")
background_b64 = ""
if os.path.exists(background_path):
    try:
        with open(background_path, "rb") as img_file:
            background_b64 = base64.b64encode(img_file.read()).decode()
    except Exception as e:
        logger.error(f"Error loading hero background: {str(e)}")

hero_placeholder = st.empty()


def render_hero(logos_html="", show_spinner=False):
    if not background_b64:
        return

    spinner_html = "<div class='hero-spinner'></div>" if show_spinner else ""
    if logos_html:
        overlay_html = textwrap.dedent(f"""
        <div class="hero-title">Big tech and Media</div>
        <div class="hero-overlay">
            <div class="hero-logo-row">
                {logos_html}
            </div>
        </div>
        """).strip()
    else:
        overlay_html = textwrap.dedent(f"""
        <div class="hero-title">Big tech and Media</div>
        {spinner_html}
        """).strip()

    css = textwrap.dedent(f"""
    <style>
    .hero-shell {{
        border-radius: 18px;
        overflow: hidden;
        margin-bottom: 2.5rem;
        transform: translateZ(0);
    }}

    .hero-section {{
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 9;
        min-height: 320px;
        border-radius: 18px;
        background-image: url("data:image/png;base64,{background_b64}");
        background-repeat: no-repeat;
        background-size: cover;
        background-position: center center;
        overflow: hidden;
    }}

	    .hero-overlay-wrap {{
	        position: absolute;
	        top: 54%;
	        left: 50%;
	        transform: translate(-50%, -50%);
	        width: min(88vw, 1250px);
	        display: flex;
	        flex-direction: column;
	        align-items: center;
	        gap: 10px;
	    }}

	    .hero-overlay {{
	        width: 100%;
	        padding: 26px 30px;
	        border-radius: 22px;
	        background: rgba(255, 255, 255, 0.22);
	        border: 1px solid rgba(255, 255, 255, 0.35);
	        backdrop-filter: blur(14px);
	        -webkit-backdrop-filter: blur(14px);
	        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
	        display: flex;
	        align-items: center;
	        justify-content: center;
	    }}

	    .hero-logo-row {{
	        display: flex;
	        align-items: center;
	        justify-content: space-between;
	        gap: 20px;
	    }}

    .hero-logo-link {{
        flex: 1 1 0;
        display: flex;
        align-items: center;
        justify-content: center;
    }}

	    .hero-logo {{
	        height: 72px;
	        max-width: 160px;
	        width: auto;
	        object-fit: contain;
	        transition: transform 0.18s ease, filter 0.18s ease;
	        filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.12));
	    }}

    .hero-logo-apple {{
        margin-top: -2px;
    }}

    .hero-logo-amazon {{
        margin-top: 4px;
    }}

	    .hero-logo-roku {{
	        height: 80px;
	    }}

    .hero-logo-link:hover .hero-logo {{
        transform: scale(1.12);
        filter: drop-shadow(0 6px 14px rgba(0, 0, 0, 0.18));
    }}

    .hero-title {{
        font-size: 0.95rem;
        font-weight: 700;
        color: #FFFFFF !important;
        text-transform: uppercase;
        letter-spacing: 0.28em;
        text-shadow: 0 3px 10px rgba(0, 0, 0, 0.45);
    }}

    .hero-spinner {{
        width: 52px;
        height: 52px;
        border-radius: 50%;
        border: 4px solid rgba(0, 115, 255, 0.2);
        border-top-color: #0073ff;
        border-right-color: #0073ff;
        animation: hero-spin 0.9s linear infinite;
    }}

    @keyframes hero-spin {{
        to {{
            transform: rotate(360deg);
        }}
    }}

	    @media (max-width: 1200px) {{
        .hero-overlay-wrap {{
            width: min(92vw, 1080px);
        }}

	        .hero-logo {{
	            height: 62px;
	            max-width: 138px;
	        }}
	    }}

	    @media (max-width: 800px) {{
	        .hero-overlay-wrap {{
	            width: 92vw;
	            top: 58%;
	        }}

        .hero-logo-row {{
            gap: 14px;
            overflow-x: auto;
        }}

	        .hero-logo {{
	            height: 52px;
	            max-width: 112px;
	        }}
	    }}
	    </style>
	    """).strip()

    hero_html = "\n".join(
        [
            css,
            '<div class="hero-shell">',
            '<div class="hero-section">',
            '<div class="hero-overlay-wrap">',
            overlay_html,
            "</div>",
            "</div>",
            "</div>",
        ]
    )
    hero_placeholder.markdown(hero_html, unsafe_allow_html=True)


render_hero(show_spinner=True)

# Initialize data processing with optimized loading
try:
    # Initialize the data processor using optimized loader
    data_processor = get_data_processor()

    # For better performance, preload frequently accessed data
    if not st.session_state.get('data_preloaded', False):
        st.session_state.data_preloaded = True

    # Load company logos
    company_logos = load_company_logos()
    st.session_state.initialized = True
except Exception as e:
    logger.error(f"Error initializing application: {str(e)}")
    st.error("Error loading application data. Please try refreshing the page.")

logo_order = [
    "Alphabet",
    "Meta Platforms",
    "Amazon",
    "Apple",
    "Microsoft",
    "Netflix",
    "Disney",
    "Comcast",
    "Paramount Global",
    "Warner Bros. Discovery",
    "Spotify",
    "Roku",
]

logo_links = []
for company in logo_order:
    logo_b64 = company_logos.get(company)
    if not logo_b64:
        continue
    company_param = quote(company)
    href = f"?nav=earnings&company={company_param}"
    logo_class = "hero-logo"
    if company == "Apple":
        logo_class += " hero-logo-apple"
    if company == "Amazon":
        logo_class += " hero-logo-amazon"
    if company == "Roku":
        logo_class += " hero-logo-roku"
    logo_links.append(
        (
            "<a class='hero-logo-link' href='{href}' target='_self' rel='noreferrer'>"
            "<img class='{logo_class}' src='data:image/png;base64,{logo_b64}' alt='{company} logo'>"
            "</a>"
        ).format(href=href, logo_b64=logo_b64, company=company, logo_class=logo_class)
    )

logos_html = "".join(logo_links)
render_hero(logos_html=logos_html, show_spinner=False)

# Add custom CSS and branding
st.markdown("""
    <style>
        :root {
            --app-font: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        /* Base styles */
        .stApp, p, div {
            font-family: var(--app-font) !important;
            font-weight: 400;
        }

        /* Loading placeholder animation */
        @keyframes shimmer {
            0% { background-position: -1000px 0; }
            100% { background-position: 1000px 0; }
        }

        .loading-placeholder {
            animation: shimmer 2s infinite linear;
            background: linear-gradient(to right, #f6f7f8 0%, #edeef1 20%, #f6f7f8 40%, #f6f7f8 100%);
            background-size: 1000px 100%;
            border-radius: 4px;
        }

        /* Headings */
        h1, h2, h3 {
            font-family: var(--app-font) !important;
            font-weight: 600;
            color: #333333;
        }

        /* Main title */
        h1 {
            color: #0073ff;
            font-size: 2.5rem;
            margin-bottom: 0.5rem !important;
            font-family: var(--app-font) !important;
            font-weight: 600;
        }

        /* Subtitle styling */
        .subtitle {
            font-family: var(--app-font) !important;
            font-size: 1.2rem;
            color: #666666;
            margin-bottom: 2rem;
            font-weight: 400;
        }

        /* Company logos grid */
        .company-logo-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 1rem;
            margin-bottom: 1rem;
            height: 140px;
            opacity: 0;
            animation: fadeIn 0.5s ease-in forwards;
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        .company-logo {
            width: 80px;
            height: 80px;
            object-fit: contain;
            margin-bottom: 0.5rem;
            transition: all 0.3s ease;
        }
        
        /* Special styling for the Coming Soon logo */
        .coming-soon-logo {
            width: 80px;
            height: 80px;
            object-fit: contain;
            margin-bottom: 0.5rem;
            transition: all 0.3s ease;
            opacity: 0.4; /* Further reduced opacity to minimize visual impact */
        }
        
        .company-logo-container:hover .company-logo,
        .company-logo-container:hover .coming-soon-logo {
            transform: scale(1.2);
            filter: drop-shadow(0 0 5px rgba(0,0,0,0.3));
        }

        .company-name {
            margin-top: 0.5rem;
            font-size: 0.9rem;
            text-align: center;
            line-height: 1.2;
        }

        /* Login section */
        #login-section {
            margin-top: 2rem;
            padding: 2rem;
            border-radius: 8px;
            background: #f8f9fa;
        }
        /* Tutorial tooltips */
        .tutorial-box {
            background-color: #f8f9fa;
            border-left: 4px solid #ff4202;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        .tutorial-box:hover {
            transform: translateX(5px);
            box-shadow: 2px 4px 8px rgba(0,0,0,0.15);
        }
        .welcome-message {
            color: #ff4202;
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 1rem;
            animation: fadeIn 1s ease-in;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
""", unsafe_allow_html=True)

# Initialize language and render the common header with language selector
init_language()

# Render the floating clock
current_year = render_floating_clock()

# Render the common header with language selector
display_header()

# Don't show SQL Assistant on the Welcome page

# Dynamic welcome message with translation
greeting = get_greeting_translated()
st.markdown(f"<div class='welcome-message'>{greeting}! 👋</div>", unsafe_allow_html=True)
st.markdown(f"<h1>{get_text('welcome')}</h1>", unsafe_allow_html=True)
st.markdown(f"<p class='subtitle'>{get_text('subtitle')}</p>", unsafe_allow_html=True)

# Interactive Tutorial for First-time Users
if st.session_state.first_time_user and st.session_state.logged_in:
    with st.expander("🎯 Quick Start Guide", expanded=True):
        st.markdown("""
        <div class='tutorial-box'>
            <h4>📊 Dashboard Navigation</h4>
            <p>Use the sidebar to navigate between different sections of the dashboard. Each page offers unique insights:</p>
            <ul>
                <li><strong>Overview:</strong> Get a bird's-eye view of market performance</li>
                <li><strong>Earnings:</strong> Deep dive into company financials</li>
                <li><strong>Stocks:</strong> Track real-time market data</li>
                <li><strong>Editorial:</strong> Expert analysis and insights</li>
                <li><strong>Financial Genie:</strong> AI-powered comparative analysis</li>
            </ul>
        </div>
        <div class='tutorial-box'>
            <h4>💡 Pro Tips</h4>
            <ul>
                <li>Use the year selector to view historical data</li>
                <li>Hover over charts for detailed information</li>
                <li>Click legends to filter data</li>
                <li>Use the AI chat for instant insights</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Got it! Don't show again"):
            st.session_state.first_time_user = False
            st.rerun()

# Stats Dashboard 
st.markdown(f"""
<div style="display: flex; flex-wrap: wrap; justify-content: space-between; margin: 20px 0;">
    <div style="background-color: #f8f9fa; border-left: 4px solid #ff4202; padding: 15px; margin: 10px 0; border-radius: 5px; flex: 1; min-width: 200px; margin-right: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <h3 style="margin: 0; color: #333; font-size: 16px;">{get_text('companies_tracked')}</h3>
        <p style="font-size: 24px; font-weight: 600; margin: 5px 0; color: #ff4202;">12+</p>
        <p style="margin: 0; font-size: 12px; color: #666;">Media-tech & Entertainment</p>
    </div>
    <div style="background-color: #f8f9fa; border-left: 4px solid #34A853; padding: 15px; margin: 10px 0; border-radius: 5px; flex: 1; min-width: 200px; margin-right: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <h3 style="margin: 0; color: #333; font-size: 16px;">{get_text('global_ad_spend')}</h3>
        <p style="font-size: 24px; font-weight: 600; margin: 5px 0; color: #34A853;">180+</p>
        <p style="margin: 0; font-size: 12px; color: #666;">Countries Covered</p>
    </div>
    <div style="background-color: #f8f9fa; border-left: 4px solid #4285F4; padding: 15px; margin: 10px 0; border-radius: 5px; flex: 1; min-width: 200px; margin-right: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <h3 style="margin: 0; color: #333; font-size: 16px;">{get_text('music_giants')}</h3>
        <p style="font-size: 24px; font-weight: 600; margin: 5px 0; color: #4285F4;">5+</p>
        <p style="margin: 0; font-size: 12px; color: #666;">Platforms & Labels</p>
    </div>
    <div style="background-color: #f8f9fa; border-left: 4px solid #FBBC05; padding: 15px; margin: 10px 0; border-radius: 5px; flex: 1; min-width: 200px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <h3 style="margin: 0; color: #333; font-size: 16px;">{get_text('streaming_services')}</h3>
        <p style="font-size: 24px; font-weight: 600; margin: 5px 0; color: #FBBC05;">11+</p>
        <p style="margin: 0; font-size: 12px; color: #666;">OTT Platforms</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Main introduction
st.markdown(f"""
## {get_text('about_platform')}

{get_text('about_description')}
""")

# Add unauthorized access message
if not st.session_state.get('logged_in', False):
    st.warning("👋 Please log in using the button in the top right to access all dashboard features.")
else:
    # Executive Summary moved to Overview page
    pass
    
    # No Executive Summary content here - moved to Overview page

# Dashboard Pages Section
st.subheader(get_text('dashboard_pages'))

# Overview Page
with st.expander(get_text('overview'), expanded=False):
    st.markdown(f"""
    {get_text('overview_desc')}
    - Company market capitalizations comparison
    - Visual performance indicators
    - Key market trends
    """)
    if st.session_state.get('logged_in', False):
        st.page_link("pages/00_Overview.py", label=f"{get_text('go_to')} {get_text('overview').replace('📊 ', '')} →")
    else:
        st.markdown('<a href="#" onclick="scrollToLogin(); return false;">Go to Overview →</a>', unsafe_allow_html=True)

# Earnings Page
with st.expander(get_text('earnings'), expanded=False):
    st.markdown(f"""
    {get_text('earnings_desc')}
    - Revenue segment analysis
    - Historical segment comparisons
    - Interactive pie charts and trend analysis
    """)
    if st.session_state.get('logged_in', False):
        st.page_link("pages/01_Earnings.py", label=f"{get_text('go_to')} {get_text('earnings').replace('💰 ', '')} →")
    else:
        st.markdown('<a href="#" onclick="scrollToLogin(); return false;">Go to Earnings →</a>', unsafe_allow_html=True)

# Stocks Page
with st.expander(get_text('stocks'), expanded=False):
    st.markdown(f"""
    {get_text('stocks_desc')}
    - Real-time stock tracking
    - Historical price trends
    - Volume analysis
    """)
    if st.session_state.get('logged_in', False):
        st.page_link("pages/02_Stocks.py", label=f"{get_text('go_to')} {get_text('stocks').replace('📈 ', '')} →")
    else:
        st.markdown('<a href="#" onclick="scrollToLogin(); return false;">Go to Stocks →</a>', unsafe_allow_html=True)


# Editorial Page
with st.expander(get_text('editorial'), expanded=False):
    st.markdown(f"""
    {get_text('editorial_desc')}
    - Professional insights
    - Market commentary
    - Performance analysis
    """)
    if st.session_state.get('logged_in', False):
        st.page_link("pages/03_Editorial.py", label=f"{get_text('go_to')} {get_text('editorial').replace('📝 ', '')} →")
    else:
        st.markdown('<a href="#" onclick="scrollToLogin(); return false;">Go to Editorial →</a>', unsafe_allow_html=True)

# Genie Page with SPECIAL badge
with st.expander("🧞 Financial Genie", expanded=False):
    # Add orange (SPECIAL) text right after the title
    st.markdown("<div style='margin-top: -15px; margin-bottom: 10px;'><span style='color: #FF4204; font-weight: bold; font-size: 0.9em;'>(SPECIAL)</span></div>", unsafe_allow_html=True)

    # Add JavaScript to color the SPECIAL text
    st.markdown("""
    <script>
    // Find all expander headers containing "Financial Genie"
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(function() {
            const headers = document.querySelectorAll('.streamlit-expanderHeader');
            headers.forEach(header => {
                if (header.textContent.includes('Financial Genie')) {
                    // Modify the text to include the orange SPECIAL text
                    header.innerHTML = header.innerHTML.replace('Financial Genie', 'Financial Genie <span style="color:#FF4204;">(SPECIAL)</span>');
                }
            });
        }, 1000); // Delay to ensure elements are loaded
    });
    </script>
    """, unsafe_allow_html=True)
    # Add a div with the special class to enable styling
    st.markdown('<div class="dashboard-financial-genie-special" style="display:none;"></div>', unsafe_allow_html=True)
    st.markdown(f"""
    {get_text('genie_desc')}
    - Multi-company comparisons
    - Inflation-adjusted metrics
    - Interactive visualization tools
    """)
    if st.session_state.get('logged_in', False):
        st.page_link("pages/04_Genie.py", label=f"{get_text('go_to')} {get_text('genie').replace('🧞 ', '')} →")
    else:
        st.markdown('<a href="#" onclick="scrollToLogin(); return false;">Go to Financial Genie →</a>', unsafe_allow_html=True)

# Add Glossary section
with st.expander(get_text('glossary')):
    st.markdown("""
    - **Adjust by USD Purchasing Power**: Modifies values based on the U.S. dollar's purchasing power to account for inflation effects over time (Bureau of Labor Statistics data).
    - **ATH**: The highest market price an asset has ever achieved.
    - **CAPEX**: Expenditures on acquiring or upgrading physical assets like buildings, machinery, and technology.
    - **Cost of Revenue**: Total expenses directly associated with producing and selling goods or services, including costs like materials and labor.
    - **Headcount**: The number of individuals employed by a company.
    - **Inflation Rates**: Measure of how much prices are rising for goods and services over time, reducing purchasing power.
      - **Official (Federal Reserve)**: Uses government-reported CPI data.
      - **Alternative (Shadow Stats)**: Uses pre-1980/1990 methodologies for arguably more realistic inflation levels.
    - **IPO**: A company's first issuance of stock to the public market.
    - **Long-Term Debt**: Debt obligations that are due in more than one year's time.
    - **M2 Money Supply**: Total amount of money in circulation including cash, checking deposits, and savings deposits—an indicator of potential inflation.
    - **Net Income**: Earnings after all expenses, including operational costs, interest, taxes, and other charges, have been subtracted from total revenue.
    - **Outstanding Shares**: The total of all shares currently held by shareholders, both common and preferred.
    - **Property & Equipment**: Assets like land, buildings, machinery, and vehicles that a company owns and uses for its operations.
    - **R&D**: Funds allocated for Research & Development of new products or technology.
    - **Recession Periods**: Timeframes when the economy was contracting, typically identified as two consecutive quarters of GDP decline.
    - **Revenue**: The total money received from selling goods or services, excluding deductions like returns and discounts, before accounting for any costs or expenses.
    - **Share Repurchases**: A company's act of buying back its own shares from the stock market.
    - **Stock Classes (A, B, C)**: Different types of stock that a company may issue, often with varying voting rights and dividend policies.
    - **Tech Service Launches**: Key launch dates of major technology platforms or services that may correlate with economic and market shifts.
    - **Total Assets**: The sum of all company assets, both current and fixed.
    """)

# Add Sources section
with st.expander(get_text('sources')):
    st.markdown("""
    Our financial data is sourced from:
    - Company Earnings Reports
    - SEC 10-K Filings
    - S&P 500 Index Data
    """)

# Add SQL Assistant description
with st.expander("🔍 SQL Assistant"):
    st.markdown("""
    <div style="padding: 10px 0;">
        <p>Access our database using natural language through the SQL Assistant in the side menu.</p>
        <p>Simply ask questions in English, Italian, or Spanish to get insights about companies, markets, and financial metrics.</p>
    </div>
    """, unsafe_allow_html=True)

# Add JavaScript for scrolling to login section when clicking protected links
st.markdown("""
<script>
    function scrollToLogin() {
        document.getElementById('login-section').scrollIntoView({ behavior: 'smooth' });
    }
</script>
""", unsafe_allow_html=True)

# Add company logos section
st.markdown("---")
st.subheader(get_text('featured_companies'))

# Add some spacing above the logos section
st.markdown("<div style='margin: 2rem 0;'></div>", unsafe_allow_html=True)

# Create rows of logos (3 rows with the new companies)
row1_cols = st.columns(5)
row2_cols = st.columns(5)
row3_cols = st.columns(5)


# Display first row of logos with centered alignment
for i, company in enumerate(['Alphabet', 'Microsoft', 'Apple', 'Netflix', 'Meta Platforms']):
    with row1_cols[i]:
        if company in company_logos and company_logos[company]:
            st.markdown(f"""
                <div class='company-logo-container'>
                    <img src='data:image/png;base64,{company_logos[company]}' class='company-logo'>
                    <div class='company-name'>{company}</div>
                </div>
            """,
                unsafe_allow_html=True)

# Display second row of logos with centered alignment
for i, company in enumerate(['Amazon', 'Disney', 'Roku', 'Spotify', 'Comcast']):
    with row2_cols[i]:
        if company in company_logos and company_logos[company]:
            st.markdown(f"""
                <div class='company-logo-container'>
                    <img src='data:image/png;base64,{company_logos[company]}' class='company-logo'>
                    <div class='company-name'>{company}</div>
                </div>
            """,
                unsafe_allow_html=True)

# Display third row of logos with centered alignment (new companies)
for i, company in enumerate(['Paramount', 'Warner Bros Discovery', 'More']):
    with row3_cols[i]:
        if company in company_logos and company_logos[company]:
            # Use special class for the "More" company with Coming Soon logo
            logo_class = 'coming-soon-logo' if company == 'More' else 'company-logo'
            st.markdown(f"""
                <div class='company-logo-container'>
                    <img src='data:image/png;base64,{company_logos[company]}' class='{logo_class}'>
                    <div class='company-name' style="{('color: #888; font-style: italic;' if company == 'More' else '')}">{company}</div>
                </div>
            """,
                unsafe_allow_html=True)


# Add spacing for visual separation
st.markdown("<div style='margin: 2rem 0;'></div>", unsafe_allow_html=True)

# Add footer section instead of login
st.markdown("---")
st.markdown('<div id="footer-section">', unsafe_allow_html=True)

# Create columns for footer
col1, col2, col3 = st.columns([1, 1, 1])

with col2:
    st.markdown("""
        <div style='text-align: center; padding: 10px;'>
            <p style="margin-bottom: 0;"><strong>© 2025 Insight</strong><strong>360</strong></p>
            <p style="white-space: nowrap; margin-top: 5px;">by Sebastiano Noziglia</p>
            <p><strong>Version: Beta</strong></p>
        </div>
    """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
