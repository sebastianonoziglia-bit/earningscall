# Set page config must be the first Streamlit command
import streamlit as st
st.set_page_config(page_title="Welcome", page_icon="📊", layout="wide")

from utils.global_fonts import apply_global_fonts
apply_global_fonts()

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
if target_param:
    target_key = str(target_param).strip().lower()
    page_map = {
        "overview": "pages/00_Overview.py",
        "earnings": "pages/01_Earnings.py",
        "01_earnings": "pages/01_Earnings.py",
        "stocks": "pages/02_Stocks.py",
        "editorial": "pages/03_Editorial.py",
        "genie": "pages/04_Genie.py",
        "financial_genie": "pages/04_Genie.py",
        "financial-genie": "pages/04_Genie.py",
    }
    if target_key in page_map:
        if target_key.startswith("earnings") or target_key == "01_earnings":
            if company_param:
                st.session_state["prefill_company"] = company_param
        try:
            st.query_params.clear()
        except Exception:
            pass
        st.switch_page(page_map[target_key])

# Note: removed the full-page overlay to avoid client-side flicker loops.


# Custom CSS for sidebar navigation items - particularly Financial Genie
st.markdown('''
<style>
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
import textwrap
import io
import mimetypes
from datetime import datetime
from urllib.parse import quote
from PIL import Image
from utils.language import get_text, get_greeting_translated
from utils.header import display_header
from utils.logos import load_company_logos
# Note: avoid transition animation on Welcome to reduce visual flicker.

# Global header (language + theme toggle)
display_header(enable_dom_patch=False)

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

# Initialize session state - no password authentication
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.logged_in = True  # Always logged in, no password required
    st.session_state.show_login = False
    st.session_state.first_time_user = False  # Skip first-time tutorial

# Define company_logos variable at the global scope
company_logos = {}

@st.cache_data(show_spinner=False)
def get_hero_background_b64(path, max_width=2000, quality=85):
    if not path or not os.path.exists(path):
        return "", "image/png"
    try:
        with Image.open(path) as img:
            has_alpha = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            )
            target = img
            if max_width and img.width > max_width:
                ratio = max_width / float(img.width)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                target = img.resize(new_size, Image.LANCZOS)
            buffer = io.BytesIO()
            if has_alpha:
                if target.mode != "RGBA":
                    target = target.convert("RGBA")
                target.save(buffer, format="PNG", optimize=True)
                mime = "image/png"
            else:
                if target.mode != "RGB":
                    target = target.convert("RGB")
                target.save(buffer, format="JPEG", quality=quality, optimize=True)
                mime = "image/jpeg"
            return base64.b64encode(buffer.getvalue()).decode(), mime
    except Exception as e:
        logger.error(f"Error loading hero background: {str(e)}")
        try:
            with open(path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode(), "image/png"
        except Exception:
            return "", "image/png"


def find_hero_video_path(assets_dir):
    if not assets_dir or not os.path.isdir(assets_dir):
        return ""

    preferred_names = [
        "HeroVideo.mp4",
        "HeroVideo.webm",
        "HeroVideo.mov",
        "HeroVideo.m4v",
    ]
    for filename in preferred_names:
        candidate = os.path.join(assets_dir, filename)
        if os.path.exists(candidate):
            return candidate

    for filename in os.listdir(assets_dir):
        lower = filename.lower()
        if lower.startswith("herovideo."):
            return os.path.join(assets_dir, filename)

    return ""


@st.cache_data(show_spinner=False)
def get_hero_video_b64(path, cache_buster=0):
    if not path or not os.path.exists(path):
        return "", ""
    try:
        mime = mimetypes.guess_type(path)[0] or "video/mp4"
        with open(path, "rb") as video_file:
            return base64.b64encode(video_file.read()).decode(), mime
    except Exception as e:
        logger.error(f"Error loading hero video: {str(e)}")
        return "", ""


# Hero image with loading state
background_path = os.path.join(ASSETS_DIR, "FAQ MFE.png")
background_b64, background_mime = get_hero_background_b64(background_path)
hero_video_path = find_hero_video_path(ASSETS_DIR)
hero_video_cache_buster = os.path.getmtime(hero_video_path) if hero_video_path else 0
hero_video_b64, hero_video_mime = get_hero_video_b64(hero_video_path, hero_video_cache_buster)
HERO_VIDEO_REMOTE_URL = (
    "https://raw.githubusercontent.com/sebastianonoziglia-bit/earningscall/"
    "40b8b4c/app/attached_assets/HeroVideo.mp4"
)

hero_placeholder = st.empty()


def render_hero(logos_html="", show_spinner=False):
    hero_video_src = ""
    video_source_mime = hero_video_mime or "video/mp4"
    if hero_video_b64 and hero_video_mime:
        hero_video_src = f"data:{hero_video_mime};base64,{hero_video_b64}"
        video_source_mime = hero_video_mime
    elif HERO_VIDEO_REMOTE_URL:
        hero_video_src = HERO_VIDEO_REMOTE_URL
        video_source_mime = "video/mp4"

    has_video = bool(hero_video_src)
    if not background_b64 and not has_video:
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

    hero_background_css = (
        f'background-image: url("data:{background_mime};base64,{background_b64}");'
        if background_b64
        else "background: #0f172a;"
    )

    hero_video_html = ""
    if has_video:
        poster_attr = (
            f'poster="data:{background_mime};base64,{background_b64}"'
            if background_b64
            else ""
        )
        hero_video_html = textwrap.dedent(f"""
        <video class="hero-video" muted playsinline preload="metadata" {poster_attr}>
            <source src="{hero_video_src}" type="{video_source_mime}">
        </video>
        <div class="hero-video-mask"></div>
        <script>
        (function() {{
            const section = document.querySelector(".hero-section");
            if (!section || section.dataset.videoBound === "1") return;
            const video = section.querySelector(".hero-video");
            if (!video) return;
            section.dataset.videoBound = "1";

            const safePlay = () => {{
                const p = video.play();
                if (p && typeof p.catch === "function") p.catch(() => {{}});
            }};

            const playIntro = () => {{
                video.loop = false;
                video.currentTime = 0;
                safePlay();
            }};

            if (video.readyState >= 2) {{
                playIntro();
            }} else {{
                video.addEventListener("loadeddata", playIntro, {{ once: true }});
            }}

            section.addEventListener("mouseenter", () => {{
                video.loop = true;
                safePlay();
            }});

            section.addEventListener("mouseleave", () => {{
                video.loop = false;
                video.pause();
                video.currentTime = 0;
            }});

            video.addEventListener("ended", () => {{
                if (!section.matches(":hover")) {{
                    video.pause();
                    video.currentTime = 0;
                }}
            }});
        }})();
        </script>
        """).strip()

    css = textwrap.dedent(f"""
    <style>
    .hero-shell {{
        border-radius: 18px;
        overflow: hidden;
        margin-bottom: 0.2rem;
        transform: translateZ(0);
    }}

    .hero-section {{
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 9;
        min-height: 320px;
        border-radius: 18px;
        {hero_background_css}
        background-repeat: no-repeat;
        background-size: cover;
        background-position: center center;
        overflow: hidden;
    }}

    .hero-video {{
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
        z-index: 0;
        pointer-events: none;
    }}

    .hero-video-mask {{
        position: absolute;
        inset: 0;
        background: linear-gradient(180deg, rgba(0, 0, 0, 0.08) 0%, rgba(0, 0, 0, 0.12) 100%);
        z-index: 1;
        pointer-events: none;
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
            z-index: 2;
	    }}

	    .hero-overlay {{
	        width: 100%;
	        padding: 26px 30px;
	        border-radius: 22px;
	        background: rgba(255, 255, 255, 0.22);
	        border: 1px solid rgba(255, 255, 255, 0.35);
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
            hero_video_html,
            '<div class="hero-overlay-wrap">',
            overlay_html,
            "</div>",
            "</div>",
            "</div>",
        ]
    )
    hero_placeholder.markdown(hero_html, unsafe_allow_html=True)


# Load company logos (avoid heavy data processor on Welcome)
try:
    company_logos = load_company_logos()
    st.session_state.initialized = True
except Exception as e:
    logger.error(f"Error loading application data: {str(e)}")
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

# Dashboard Pages Section (directly under hero)
st.markdown("""
<style>
/* Hide sidebar nav on Welcome */
section[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}

.welcome-nav-wrap {
    margin-top: -12px;
}
.welcome-nav {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(255px, 1fr));
    gap: 14px;
    margin: 0 0 18px;
}
.welcome-nav .nav-btn {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 12px;
    height: 98px;
    text-align: left;
    padding: 14px 16px;
    color: #ffffff !important;
    border-radius: 14px;
    text-decoration: none !important;
    font-weight: 700;
    font-size: 1.06rem;
    border: 1px solid transparent;
    transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
}
.welcome-nav .nav-btn:hover {
    transform: translateY(-2px) scale(1.01);
    filter: brightness(1.05);
}
.welcome-nav .nav-btn:visited,
.welcome-nav .nav-btn:active,
.welcome-nav .nav-btn:focus {
    color: #ffffff !important;
    text-decoration: none !important;
}
.welcome-nav .nav-icon {
    width: 30px;
    height: 30px;
    background-repeat: no-repeat;
    background-position: center;
    background-size: contain;
    flex: 0 0 30px;
}
.welcome-nav .nav-label {
    color: #ffffff !important;
    line-height: 1.2;
    font-size: 1.08rem;
    font-weight: 700;
}
.welcome-nav .nav-copy {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
}
.welcome-nav .nav-desc {
    color: rgba(255, 255, 255, 0.96) !important;
    font-size: 0.78rem;
    line-height: 1.28;
    font-weight: 500;
}
.welcome-nav .nav-overview { background: #1d4ed8; border-color: #1e40af; box-shadow: 0 10px 18px rgba(30, 64, 175, 0.30); }
.welcome-nav .nav-earnings { background: #0891b2; border-color: #0e7490; box-shadow: 0 10px 18px rgba(14, 116, 144, 0.30); }
.welcome-nav .nav-stocks { background: #15803d; border-color: #166534; box-shadow: 0 10px 18px rgba(22, 101, 52, 0.30); }
.welcome-nav .nav-editorial { background: #c2410c; border-color: #9a3412; box-shadow: 0 10px 18px rgba(154, 52, 18, 0.30); }
.welcome-nav .nav-genie { background: #7c3aed; border-color: #6d28d9; box-shadow: 0 10px 18px rgba(109, 40, 217, 0.30); }

@media (max-width: 768px) {
    .welcome-nav {
        grid-template-columns: 1fr;
    }
    .welcome-nav .nav-btn {
        height: 92px;
        font-size: 1.01rem;
    }
    .welcome-nav-wrap {
        margin-top: -8px;
    }
}

.nav-icon-search { background-image: url('data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22white%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Ccircle%20cx%3D%2211%22%20cy%3D%2211%22%20r%3D%227%22/%3E%3Cline%20x1%3D%2216.5%22%20y1%3D%2216.5%22%20x2%3D%2222%22%20y2%3D%2222%22/%3E%3C/svg%3E'); }
.nav-icon-bar { background-image: url('data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22white%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cline%20x1%3D%224%22%20y1%3D%2220%22%20x2%3D%2220%22%20y2%3D%2220%22/%3E%3Crect%20x%3D%226%22%20y%3D%2211%22%20width%3D%223%22%20height%3D%229%22/%3E%3Crect%20x%3D%2211%22%20y%3D%227%22%20width%3D%223%22%20height%3D%2213%22/%3E%3Crect%20x%3D%2216%22%20y%3D%223%22%20width%3D%223%22%20height%3D%2217%22/%3E%3C/svg%3E'); }
.nav-icon-line { background-image: url('data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22white%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpolyline%20points%3D%223%2017%209%2011%2013%2015%2021%207%22/%3E%3Cpolyline%20points%3D%223%2021%203%2017%2021%2017%22/%3E%3C/svg%3E'); }
.nav-icon-coin { background-image: url('data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22white%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cellipse%20cx%3D%2212%22%20cy%3D%226%22%20rx%3D%227%22%20ry%3D%223%22/%3E%3Cpath%20d%3D%22M5%206v6c0%201.7%203.1%203%207%203s7-1.3%207-3V6%22/%3E%3Cpath%20d%3D%22M5%2012v6c0%201.7%203.1%203%207%203s7-1.3%207-3v-6%22/%3E%3C/svg%3E'); }
.nav-icon-book { background-image: url('data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22white%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M2%203h7a4%204%200%200%201%204%204v14a3%203%200%200%200-3-3H2z%22/%3E%3Cpath%20d%3D%22M22%203h-7a4%204%200%200%200-4%204%22/%3E%3Cpath%20d%3D%22M22%2020h-7a3%203%200%200%201-3-3%22/%3E%3Cline%20x1%3D%2212%22%20y1%3D%227%22%20x2%3D%2212%22%20y2%3D%2221%22/%3E%3C/svg%3E'); }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="welcome-nav-wrap">
  <div class="welcome-nav">
    <a class="nav-btn nav-overview" href="?nav=overview"><span class="nav-icon nav-icon-search"></span><span class="nav-copy"><span class="nav-label">Overview</span><span class="nav-desc">Global media map and KPI snapshot</span></span></a>
    <a class="nav-btn nav-earnings" href="?nav=earnings"><span class="nav-icon nav-icon-coin"></span><span class="nav-copy"><span class="nav-label">Earnings</span><span class="nav-desc">Revenue segments and quarterly drilldowns</span></span></a>
    <a class="nav-btn nav-stocks" href="?nav=stocks"><span class="nav-icon nav-icon-line"></span><span class="nav-copy"><span class="nav-label">Stocks</span><span class="nav-desc">Live performance and market trend tracking</span></span></a>
    <a class="nav-btn nav-editorial" href="?nav=editorial"><span class="nav-icon nav-icon-book"></span><span class="nav-copy"><span class="nav-label">Editorial</span><span class="nav-desc">Service-level stories and subscriber context</span></span></a>
    <a class="nav-btn nav-genie" href="?nav=genie"><span class="nav-icon nav-icon-bar"></span><span class="nav-copy"><span class="nav-label">Financial Genie (SPECIAL)</span><span class="nav-desc">Macro overlays with multi-metric comparisons</span></span></a>
  </div>
</div>
""", unsafe_allow_html=True)

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

# Add Glossary section
with st.expander("Glossary"):
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
with st.expander("Sources"):
    st.markdown("""
    Our financial data is sourced from:
    - Company Earnings Reports
    - SEC 10-K Filings
    - S&P 500 Index Data
    """)

# Add JavaScript for scrolling to login section when clicking protected links
# Removed scrollToLogin script to avoid client-side DOM manipulation.

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
