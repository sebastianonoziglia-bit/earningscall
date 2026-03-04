import streamlit as st
# Set page config - Must be the first Streamlit command
st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")

from utils.global_fonts import apply_global_fonts


import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime
import numpy as np
import textwrap
import html
import json
import re
import base64
import requests
from urllib.parse import quote_plus
import streamlit.components.v1 as components
from pathlib import Path
from data_processor import FinancialDataProcessor
from subscriber_data_processor import SubscriberDataProcessor
from utils.state_management import get_data_processor, initialize_session_state
from utils.animation_helper import update_chart_layout, create_consistent_frame, get_dynamic_tick_values, create_animation_buttons
from utils.styles import get_page_style, load_overview_specific_styles
from utils.components import load_company_logos, render_ai_assistant
from utils.header import display_header
from utils.data_loader import CONTINENT_MAPPINGS, AD_MACRO_CATEGORIES
from utils.theme import get_theme_mode
from utils.data_granularity import (
    get_available_granularity_options,
    get_day_labels_for_year,
    get_month_labels_for_year,
    get_quarter_labels_for_year,
    update_global_time_context,
)

st.session_state["active_nav_page"] = "overview"
st.session_state["_active_nav_page"] = "overview"
display_header()
apply_global_fonts()
st.markdown(get_page_style(), unsafe_allow_html=True)
load_overview_specific_styles()

# Streamlit markdown can treat indented HTML as a code block. Normalize HTML blocks to avoid that.
def _html_block(html: str) -> str:
    dedented = textwrap.dedent(html)
    return "\n".join(line.lstrip() for line in dedented.splitlines()).strip()

st.markdown(
    _html_block(
        """
        <style>
        body.theme-dark .stApp,
        body.theme-dark [data-testid="stAppViewContainer"],
        body.theme-dark section.main,
        body.theme-dark .block-container {
            background: #0B1220 !important;
            color: #F8FAFC !important;
        }

        body.theme-dark [data-testid="stMarkdownContainer"],
        body.theme-dark [data-testid="stMarkdownContainer"] p,
        body.theme-dark [data-testid="stMarkdownContainer"] li,
        body.theme-dark [data-testid="stMarkdownContainer"] span,
        body.theme-dark [data-testid="stMarkdownContainer"] strong {
            color: #E2E8F0 !important;
        }

        div[data-testid="stCaptionContainer"],
        div[data-testid="stCaptionContainer"] p,
        .stCaption {
            color: #475569 !important;
            opacity: 1 !important;
        }

        body.theme-dark div[data-testid="stCaptionContainer"],
        body.theme-dark div[data-testid="stCaptionContainer"] p,
        body.theme-dark .stCaption {
            color: #CBD5E1 !important;
            opacity: 1 !important;
        }

        body.theme-dark h1,
        body.theme-dark h2,
        body.theme-dark h3,
        body.theme-dark h4,
        body.theme-dark h5,
        body.theme-dark h6,
        body.theme-dark .stMarkdown h1,
        body.theme-dark .stMarkdown h2,
        body.theme-dark .stMarkdown h3,
        body.theme-dark .stMarkdown h4,
        body.theme-dark .stMarkdown h5,
        body.theme-dark .stMarkdown h6 {
            color: #F8FAFC !important;
        }

        body.theme-dark .overview-summary-card {
            background: #111827 !important;
            color: #F8FAFC !important;
            box-shadow: 0 14px 28px rgba(2, 6, 23, 0.35) !important;
        }

        body.theme-dark .overview-summary-card * {
            color: inherit !important;
        }

        body.theme-dark .ov-map-summary {
            position: absolute;
            top: clamp(90px, calc(35% + 90px), 380px);
            left: 18px;
            z-index: 6;
            max-width: min(340px, 40vw);
            height: clamp(180px, 35vh, 420px);
            background: rgba(11, 18, 32, 0.6);
            border-radius: 12px;
            padding: 10px 12px;
            box-shadow: none;
            overflow-y: auto;
            pointer-events: auto;
        }

        body.theme-dark .ov-map-summary-title {
            font-size: 0.95rem;
            color: #94A3B8;
            margin-bottom: 6px;
        }

        body.theme-dark .ov-map-summary-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: #F8FAFC;
            margin-bottom: 12px;
        }

        body.theme-dark .ov-map-summary-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        body.theme-dark .ov-map-summary-row {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            font-size: 0.9rem;
            font-weight: 600;
            color: #E2E8F0;
        }

        body.theme-dark .ov-map-summary-sub {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            font-size: 0.78rem;
            color: #94A3B8;
            padding-left: 10px;
        }

        .ov-macro-label {
            margin: 4px 0 8px;
            font-size: 0.8rem;
            color: #64748B;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .ov-macro-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 10px 0 14px 0;
        }

        .ov-macro-pill {
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(15, 23, 42, 0.12);
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85rem;
            color: #0F172A;
            font-weight: 600;
        }

        .ov-macro-pill.positive {
            border-color: rgba(34, 197, 94, 0.4);
            color: #166534;
        }

        .ov-macro-pill.negative {
            border-color: rgba(248, 113, 113, 0.45);
            color: #991B1B;
        }

        body.theme-dark .ov-macro-label {
            margin: 4px 0 8px;
            font-size: 0.8rem;
            color: #94A3B8;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        body.theme-dark .ov-map-wrap {
            position: relative;
            min-height: clamp(420px, 58vh, 680px);
        }

        body.theme-dark .ov-macro-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 10px 0 14px 0;
        }

        body.theme-dark .ov-macro-pill {
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(148, 163, 184, 0.2);
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85rem;
            color: #E2E8F0;
            font-weight: 600;
        }

        body.theme-dark .ov-macro-pill.positive {
            border-color: rgba(34, 197, 94, 0.45);
            color: #BBF7D0;
        }

        body.theme-dark .ov-macro-pill.negative {
            border-color: rgba(248, 113, 113, 0.5);
            color: #FECACA;
        }

        body.theme-dark div[data-baseweb="select"] > div,
        body.theme-dark div[data-baseweb="select"] > div > div,
        body.theme-dark input,
        body.theme-dark textarea {
            background: #0F172A !important;
            color: #F8FAFC !important;
            border-color: rgba(148, 163, 184, 0.35) !important;
        }

        body.theme-dark .stMultiSelect [data-baseweb="tag"] {
            background: #0F172A !important;
            color: #F8FAFC !important;
            border: 1px solid rgba(59, 130, 246, 0.45) !important;
        }

        body.theme-dark label,
        body.theme-dark .stRadio label,
        body.theme-dark .stCheckbox label {
            color: #E2E8F0 !important;
        }

        body.theme-dark .js-plotly-plot .xtick text,
        body.theme-dark .js-plotly-plot .ytick text,
        body.theme-dark .js-plotly-plot .gtitle text,
        body.theme-dark .js-plotly-plot .legend text,
        body.theme-dark .js-plotly-plot .colorbar text {
            fill: #E2E8F0 !important;
        }

        body.theme-dark .js-plotly-plot .bglayer .bg {
            fill: rgba(0, 0, 0, 0) !important;
        }

        body.theme-dark .js-plotly-plot .gridlayer path {
            stroke: rgba(148, 163, 184, 0.12) !important;
        }

        .ov-insight-category-card {
            border: 1px solid rgba(37, 99, 235, 0.28);
            border-radius: 16px;
            background: linear-gradient(180deg, rgba(239, 246, 255, 0.92), rgba(248, 250, 252, 0.96));
            padding: 10px 12px 12px 12px;
            margin: 12px 0 18px 0;
            box-shadow: 0 10px 24px rgba(37, 99, 235, 0.12);
        }

        .ov-insight-category-title {
            display: block;
            width: 100%;
            background: linear-gradient(135deg, #1D4ED8 0%, #2563EB 52%, #3B82F6 100%);
            border-radius: 10px;
            color: #FFFFFF;
            padding: 9px 12px;
            margin-bottom: 10px;
            font-size: 1.02rem;
            font-weight: 800;
            letter-spacing: 0.01em;
            box-shadow: 0 8px 18px rgba(37, 99, 235, 0.26);
        }

        .ov-insight-item {
            border-top: 1px solid rgba(15, 23, 42, 0.08);
            padding-top: 18px;
            margin-top: 22px;
        }

        .ov-insight-item:first-child {
            border-top: none;
            padding-top: 0;
            margin-top: 0;
        }

        .ov-insight-head {
            font-size: 1.04rem;
            line-height: 1.45;
            color: #0F172A;
            margin-bottom: 8px;
            font-weight: 700;
        }

        .ov-insight-head-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }

        .ov-insight-local-index {
            font-weight: 700;
            color: #1E293B;
            margin-right: 6px;
        }

        .ov-insight-logos {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            margin-left: auto;
            flex-wrap: wrap;
        }

        .ov-insight-logo {
            width: 72px;
            height: 72px;
            border-radius: 999px;
            object-fit: contain;
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(15, 23, 42, 0.12);
            padding: 4px;
        }

        .ov-insight-meta {
            font-size: 0.84rem;
            color: #475569;
            margin-bottom: 4px;
        }

        .ov-insight-chart-link {
            color: #1D4ED8;
            font-weight: 600;
            text-decoration: none;
        }

        .ov-insight-chart-link:hover {
            text-decoration: underline;
        }

        .ov-chart-anchor {
            position: relative;
            top: -80px;
        }

        .ov-insight-body {
            font-size: 0.98rem;
            line-height: 1.72;
            color: #1E293B;
            margin: 0 0 6px 0;
        }

        .ov-insight-stat {
            font-size: 0.8rem;
            font-weight: 700;
            color: #1D4ED8;
            background: rgba(59, 130, 246, 0.12);
            padding: 2px 8px;
            border-radius: 6px;
            margin-left: 8px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .ov-chart-comment {
            margin: 0 0 10px 0;
            font-size: 0.95rem;
            line-height: 1.62;
            color: #334155;
        }

        .ov-chart-comment-post {
            margin: 10px 0 0 0;
            font-size: 0.92rem;
            line-height: 1.58;
            color: #475569;
        }

        .ov-quote-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 10px;
            margin-top: 8px;
        }

        .ov-quote-card {
            border: 1px solid rgba(15, 23, 42, 0.12);
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.9);
            padding: 10px 12px;
            box-shadow: 0 8px 16px rgba(15, 23, 42, 0.08);
        }

        .ov-quote-meta {
            font-size: 0.82rem;
            color: #334155;
            margin-bottom: 6px;
            font-weight: 700;
        }

        .ov-quote-body {
            margin: 0;
            font-size: 0.9rem;
            line-height: 1.5;
            color: #0F172A;
        }

        body.theme-dark .ov-insight-category-card {
            border-color: rgba(148, 163, 184, 0.22);
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.58), rgba(15, 23, 42, 0.42));
        }

        body.theme-dark .ov-insight-category-title {
            color: #E2E8F0;
            box-shadow: 0 8px 18px rgba(37, 99, 235, 0.34);
        }

        body.theme-dark .ov-insight-item {
            border-top-color: rgba(148, 163, 184, 0.2);
        }

        body.theme-dark .ov-insight-head {
            color: #F8FAFC;
        }

        body.theme-dark .ov-insight-local-index {
            color: #CBD5E1;
        }

        body.theme-dark .ov-insight-logo {
            background: rgba(15, 23, 42, 0.72);
            border-color: rgba(148, 163, 184, 0.3);
        }

        body.theme-dark .ov-insight-meta {
            color: #94A3B8;
        }

        body.theme-dark .ov-insight-chart-link {
            color: #93C5FD;
        }

        body.theme-dark .ov-insight-body {
            color: #CBD5E1;
        }

        body.theme-dark .ov-insight-stat {
            color: #BFDBFE;
            background: rgba(59, 130, 246, 0.24);
        }

        body.theme-dark .ov-chart-comment {
            color: #CBD5E1;
        }

        body.theme-dark .ov-chart-comment-post {
            color: #94A3B8;
        }

        body.theme-dark .ov-quote-card {
            border-color: rgba(148, 163, 184, 0.24);
            background: rgba(15, 23, 42, 0.52);
            box-shadow: 0 8px 16px rgba(2, 6, 23, 0.3);
        }

        body.theme-dark .ov-quote-meta {
            color: #93C5FD;
        }

        body.theme-dark .ov-quote-body {
            color: #E2E8F0;
        }

        </style>
        """
    ),
    unsafe_allow_html=True,
)
components.html(
    "",
    height=0,
)

@st.cache_data(ttl=3600)
def _load_continent_geojson():
    candidates = [
        Path("attached_assets/continents.geojson"),
        Path("attached_assets/continents.json"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
    remote_sources = [
        "https://opengeos.org/data/world/continents.geojson",
        "https://gist.githubusercontent.com/hrbrmstr/91ea5cc9474286c72838/raw/59421ff9b268ff0929b051ddafafbeb94a4c1910/continents.json",
    ]
    for url in remote_sources:
        try:
            resp = requests.get(url, timeout=12)
            resp.raise_for_status()
            data = resp.json()
            try:
                Path("attached_assets").mkdir(parents=True, exist_ok=True)
                Path("attached_assets/continents.geojson").write_text(
                    json.dumps(data), encoding="utf-8"
                )
            except OSError:
                pass
            return data
        except (requests.RequestException, ValueError, json.JSONDecodeError):
            continue
    return None

def _pick_geojson_region_key(geojson_data, region_names):
    if not geojson_data:
        return None
    features = geojson_data.get("features", [])
    if not features:
        return None
    candidates = ["region", "Region", "CONTINENT", "continent", "name", "NAME", "NAME_EN", "NAME_LONG"]
    region_set = {str(r) for r in region_names}
    for key in candidates:
        values = set()
        for feature in features:
            props = feature.get("properties", {})
            if key in props:
                values.add(str(props.get(key)))
        if values & region_set:
            return key
    return None

def _geojson_region_names(geojson_data, key):
    if not geojson_data or not key:
        return []
    names = []
    for feature in geojson_data.get("features", []):
        props = feature.get("properties", {})
        if key in props:
            names.append(str(props.get(key)))
    return sorted({n for n in names if n})

def _geojson_centroids(geojson_data, key):
    if not geojson_data or not key:
        return {}
    centroids = {}
    for feature in geojson_data.get("features", []):
        props = feature.get("properties", {})
        name = props.get(key)
        geometry = feature.get("geometry", {})
        gtype = geometry.get("type")
        coords = geometry.get("coordinates", [])
        if not name:
            continue

        def _poly_centroid(ring):
            if not ring:
                return 0.0, None
            area = 0.0
            cx = 0.0
            cy = 0.0
            n = len(ring)
            for i in range(n):
                x1, y1 = ring[i]
                x2, y2 = ring[(i + 1) % n]
                cross = x1 * y2 - x2 * y1
                area += cross
                cx += (x1 + x2) * cross
                cy += (y1 + y2) * cross
            area *= 0.5
            if abs(area) < 1e-9:
                return 0.0, None
            cx /= 6.0 * area
            cy /= 6.0 * area
            return area, (cx, cy)

        def _point_in_ring(pt, ring):
            x, y = pt
            inside = False
            n = len(ring)
            for i in range(n):
                x1, y1 = ring[i]
                x2, y2 = ring[(i + 1) % n]
                if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1):
                    inside = not inside
            return inside

        def _best_centroid(polys):
            best = None
            best_area = 0.0
            best_ring = None
            for ring in polys:
                area, centroid = _poly_centroid(ring)
                if centroid and abs(area) > abs(best_area):
                    best_area = area
                    best = centroid
                    best_ring = ring
            if best and best_ring and not _point_in_ring(best, best_ring):
                xs = [p[0] for p in best_ring]
                ys = [p[1] for p in best_ring]
                bbox_center = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
                if _point_in_ring(bbox_center, best_ring):
                    return bbox_center
            return best

        centroid = None
        if gtype == "Polygon":
            outer = coords[0] if coords else []
            centroid = _best_centroid([outer])
        elif gtype == "MultiPolygon":
            outers = []
            for poly in coords:
                if poly:
                    outers.append(poly[0])
            centroid = _best_centroid(outers)
        if centroid:
            centroids[str(name)] = centroid
    return centroids

def _lonlat_to_paper(lon, lat, center_lon=0.0, center_lat=10.0, scale=1.05):
    x = 0.5 + ((lon - center_lon) / 360.0) * scale
    y = 0.5 + ((lat - center_lat) / 180.0) * scale
    return max(0.02, min(0.98, x)), max(0.02, min(0.98, y))

def _fmt_compact(value: float) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    av = abs(v)
    if av >= 1_000_000_000:
        return f"{v/1_000_000_000:.1f}B"
    if av >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if av >= 1_000:
        return f"{v/1_000:.0f}k"
    return f"{v:.0f}"

def begin_snap_section(section_id: str) -> None:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(section_id or "").strip()).strip("-") or "section"
    st.markdown(
        f"<section id='ov-{safe_id}' class='ov-snap-section' data-ov-section='{safe_id}'>",
        unsafe_allow_html=True,
    )

def end_snap_section() -> None:
    st.markdown("</section>", unsafe_allow_html=True)

# Match Earnings hover + pop interaction styling.
st.markdown(
    """
    <style>
    .js-plotly-plot .barlayer .bars path,
    .js-plotly-plot .boxlayer .boxes path {
        transition: transform 0.12s ease, filter 0.12s ease;
        transform-origin: center;
    }

    .js-plotly-plot .barlayer .bars path:hover,
    .js-plotly-plot .boxlayer .boxes path:hover {
        transform: scale(1.04);
        filter: drop-shadow(0 8px 14px rgba(15, 23, 42, 0.18));
    }

    .js-plotly-plot .scatterlayer .trace path:hover,
    .js-plotly-plot .scatterlayer .trace circle:hover {
        transform: scale(1.08);
        filter: drop-shadow(0 6px 10px rgba(15, 23, 42, 0.2));
    }

    .js-plotly-plot .plotly-pop {
        transform: scale(1.06);
        transform-box: fill-box;
        transform-origin: center;
        filter: drop-shadow(0 8px 14px rgba(15, 23, 42, 0.18));
    }

    .js-plotly-plot .pielayer .slice.plotly-pop {
        transform: scale(1.06);
        transform-origin: center;
        filter: drop-shadow(0 10px 16px rgba(15, 23, 42, 0.2));
    }

    /* Choropleth countries (world map) hover pop */
    .js-plotly-plot .choroplethlayer path,
    .js-plotly-plot .geolayer path {
        transition: transform 0.12s ease, filter 0.12s ease, stroke-width 0.12s ease;
        transform-origin: center;
    }
    .js-plotly-plot .choroplethlayer path:hover,
    .js-plotly-plot .geolayer path:hover,
    .js-plotly-plot .choroplethlayer path.plotly-pop,
    .js-plotly-plot .geolayer path.plotly-pop {
        transform: scale(1.03);
        stroke-width: 2px !important;
        filter: drop-shadow(0 10px 16px rgba(15, 23, 42, 0.22));
    }

    /* KPI icons (reused from Earnings hero KPIs) */
    .overview-summary-card .kpi-icon-wrap {
        width: 46px;
        height: 46px;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.22);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-top: 8px;
    }

    .overview-summary-card .kpi-icon {
        width: 28px;
        height: 28px;
        display: block;
    }

    .overview-summary-card .kpi-icon .growth-bar {
        transform-origin: bottom;
        animation: kpiBarPulse1 3s ease-in-out infinite;
    }
    .overview-summary-card .kpi-icon .growth-bar:nth-child(2) { animation-name: kpiBarPulse2; animation-duration: 3.5s; }
    .overview-summary-card .kpi-icon .growth-bar:nth-child(3) { animation-name: kpiBarPulse3; animation-duration: 2.8s; }
    .overview-summary-card .kpi-icon .growth-bar:nth-child(4) { animation-name: kpiBarPulse4; animation-duration: 3.2s; }
    .overview-summary-card .kpi-icon .growth-bar:nth-child(5) { animation-name: kpiBarPulse5; animation-duration: 2.5s; }

    @keyframes kpiBarPulse1 { 0%, 100% { transform: scaleY(1); } 30% { transform: scaleY(0.7); } 60% { transform: scaleY(1.1); } }
    @keyframes kpiBarPulse2 { 0%, 100% { transform: scaleY(1); } 25% { transform: scaleY(1.15); } 70% { transform: scaleY(0.8); } }
    @keyframes kpiBarPulse3 { 0%, 100% { transform: scaleY(1); } 35% { transform: scaleY(0.75); } 65% { transform: scaleY(1.05); } }
    @keyframes kpiBarPulse4 { 0%, 100% { transform: scaleY(1); } 40% { transform: scaleY(1.2); } 75% { transform: scaleY(0.85); } }
    @keyframes kpiBarPulse5 { 0%, 100% { transform: scaleY(1); } 20% { transform: scaleY(1.1); } 55% { transform: scaleY(0.9); } }

    .overview-summary-card .dollar-pulse {
        animation: kpiDollarBounce 2s ease-in-out infinite;
        transform-origin: center;
    }
    @keyframes kpiDollarBounce { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.12); } }

    .overview-summary-card .kpi-icon .gear-rotate {
        animation: kpiGearSpin 6s linear infinite;
        transform-origin: center;
    }
    @keyframes kpiGearSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

    .overview-summary-card .kpi-icon .coin-stack {
        animation: kpiCoinFloat 3s ease-in-out infinite;
    }
    .overview-summary-card .kpi-icon .coin-stack:nth-child(2) { animation-delay: 0.3s; }
    .overview-summary-card .kpi-icon .coin-stack:nth-child(3) { animation-delay: 0.6s; }
    @keyframes kpiCoinFloat { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }

    .overview-summary-card .kpi-icon .bulb-glow { animation: kpiBulbFlicker 2s ease-in-out infinite; }
    .overview-summary-card .kpi-icon .bulb-glow-ghost { animation: kpiBulbGhost 2.4s ease-in-out infinite; opacity: 0; }
    @keyframes kpiBulbFlicker { 0%, 100% { filter: drop-shadow(0 0 4px rgba(0, 115, 255, 0.35)); } 50% { filter: drop-shadow(0 0 10px rgba(0, 115, 255, 0.7)); } }
    @keyframes kpiBulbGhost { 0%, 100% { opacity: 0; } 35% { opacity: 0.18; } 55% { opacity: 0.35; } 70% { opacity: 0.12; } }

    .overview-summary-card .kpi-icon .block-build { animation: kpiBlockGrow 3s ease-in-out infinite; transform-origin: bottom; }
    .overview-summary-card .kpi-icon .block-build:nth-child(2) { animation-delay: 0.3s; }
    .overview-summary-card .kpi-icon .block-build:nth-child(3) { animation-delay: 0.6s; }
    @keyframes kpiBlockGrow { 0%, 100% { transform: scaleY(1); opacity: 1; } 50% { transform: scaleY(0.8); opacity: 0.7; } }

    .overview-summary-card .kpi-icon .pie-slice { animation: kpiPieSlice 3.2s ease-in-out infinite; transform-origin: center; }
    .overview-summary-card .kpi-icon .pie-slice.slice-2 { animation-delay: 0.3s; }
    .overview-summary-card .kpi-icon .pie-slice.slice-3 { animation-delay: 0.6s; }
    @keyframes kpiPieSlice { 0%, 100% { transform: scale(1); opacity: 0.9; } 50% { transform: scale(1.12); opacity: 1; } }

    .overview-summary-card .kpi-icon .trend-line { stroke-dasharray: 80; stroke-dashoffset: 80; animation: kpiDrawTrend 3s ease-in-out infinite; }
    @keyframes kpiDrawTrend { 0%, 100% { stroke-dashoffset: 80; } 50% { stroke-dashoffset: 0; } }

    .overview-summary-card .kpi-icon .money-float { animation: kpiMoneyWave 2.5s ease-in-out infinite; }
    .overview-summary-card .kpi-icon .money-float:nth-child(2) { animation-delay: 0.2s; }
    .overview-summary-card .kpi-icon .money-float:nth-child(3) { animation-delay: 0.4s; }
    @keyframes kpiMoneyWave { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }

    .overview-summary-card .kpi-icon .arrow-up { animation: kpiArrowLift 2.6s ease-in-out infinite; transform-origin: center; }
    @keyframes kpiArrowLift { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
    </style>
    """,
    unsafe_allow_html=True,
)

# Overview fade-on-scroll (scoped to this page only; no scroll-snapping).
st.markdown("<div id='ov-fade-marker' style='display:none'></div>", unsafe_allow_html=True)
components.html(
    _html_block(
        """
        <style>
          body.ov-fade-page .ov-snap-section { will-change: opacity, transform; }
        </style>
        <script>
        (function () {
          const doc = window.parent.document;
          const marker = doc.getElementById("ov-fade-marker");
          if (!marker) return;

          doc.body.classList.add("ov-fade-page");

          const cleanupIfMissing = () => {
            if (!doc.getElementById("ov-fade-marker")) {
              doc.body.classList.remove("ov-fade-page");
              try { doc.defaultView.removeEventListener("scroll", onScroll, { passive: true }); } catch (e) {}
              try { doc.defaultView.removeEventListener("resize", onScroll); } catch (e) {}
            }
          };
          const mo = new MutationObserver(cleanupIfMissing);
          mo.observe(doc.body, { childList: true, subtree: true });

          const getSections = () => Array.from(doc.querySelectorAll(".ov-snap-section"));

          let raf = 0;
          function applyFade() {
            raf = 0;
            const sections = getSections();
            if (!sections.length) return;
            const vh = doc.defaultView.innerHeight || 800;
            const focusY = vh * 0.28;     // where the "active" section feels centered
            const spread = vh * 0.65;     // fade distance
            for (const sec of sections) {
              const r = sec.getBoundingClientRect();
              const secY = r.top + Math.min(r.height * 0.35, 180);
              const dist = Math.abs(secY - focusY);
              const t = Math.max(0, Math.min(1, 1 - dist / spread)); // 0..1
              const opacity = 0.22 + t * 0.78;
              const translate = (1 - t) * 18;
              sec.style.opacity = String(opacity);
              sec.style.transform = `translateY(${translate}px)`;
            }
          }

          function onScroll() {
            if (raf) return;
            raf = doc.defaultView.requestAnimationFrame(applyFade);
          }

          doc.defaultView.addEventListener("scroll", onScroll, { passive: true });
          doc.defaultView.addEventListener("resize", onScroll);
          setTimeout(applyFade, 250);
        })();
        </script>
        """
    ),
    height=0,
)

components.html(
    """
    <script>
    (function() {
        const doc = window.parent.document;
        const bindPop = (plot) => {
            if (!plot || plot.__hoverPopBound) return;
            plot.__hoverPopBound = true;
            const clearPop = () => {
                const popped = plot.querySelectorAll(".plotly-pop");
                popped.forEach((el) => el.classList.remove("plotly-pop"));
            };
            try { clearPop(); } catch (e) {}
            if (typeof plot.on !== "function") return;
            plot.on('plotly_hover', (data) => {
                try {
                    clearPop();
                    if (!data || !data.points || !data.points.length) return;
                    const pt = data.points[0];
                    const pointNumber = pt.pointNumber;
                    const curveNumber = pt.curveNumber;
                    if (pt && pt.data && pt.data.type === "pie") {
                        let target = null;
                        const evTarget = data && data.event && data.event.target ? data.event.target : null;
                        if (evTarget && evTarget.closest) {
                            target = evTarget.closest(".slice");
                        }
                        if (!target) {
                            const pieTraces = plot.querySelectorAll(".pielayer .trace");
                            const pieTrace = pieTraces[curveNumber];
                            if (!pieTrace) return;
                            const slices = pieTrace.querySelectorAll(".slice");
                            target = slices[pointNumber] || null;
                        }
                        if (target) target.classList.add("plotly-pop");
                    } else if (pt && pt.data && pt.data.type === "choropleth") {
                        // Pop the hovered country path in choropleth maps.
                        let target = null;
                        const evTarget = data && data.event && data.event.target ? data.event.target : null;
                        if (evTarget && evTarget.closest) {
                            target = evTarget.closest("path");
                        }
                        if (target) target.classList.add("plotly-pop");
                    } else if (pt && pt.data && pt.data.type === "treemap") {
                        // Treemap DOM ordering doesn't reliably match pointNumber indexing.
                        // Use the actual event target to pop the hovered tile.
                        let target = null;
                        const evTarget = data && data.event && data.event.target ? data.event.target : null;
                        if (evTarget && evTarget.closest) {
                            target =
                                evTarget.closest("g.slice") ||
                                evTarget.closest(".slice") ||
                                evTarget.closest("path") ||
                                null;
                        }
                        if (target) target.classList.add("plotly-pop");
                    } else {
                        const traces = plot.querySelectorAll(
                            ".barlayer .trace, .scatterlayer .trace, .boxlayer .trace, .treemaplayer .trace"
                        );
                        const trace = traces[curveNumber];
                        if (!trace) return;
                        let target = trace.querySelector(`[data-point-number='${pointNumber}']`);
                        if (!target) {
                            const points = trace.querySelectorAll("path, circle, rect");
                            target = points[pointNumber] || null;
                        }
                        if (target) {
                            target.classList.add("plotly-pop");
                        }
                    }
                } catch (e) {}
            });
            plot.on('plotly_unhover', () => {
                try { clearPop(); } catch (e) {}
            });
        };

        const scan = () => {
            doc.querySelectorAll(".js-plotly-plot").forEach(bindPop);
        };
        scan();
        const observer = new MutationObserver(() => scan());
        observer.observe(doc.body, { childList: true, subtree: true });
    })();
    </script>
    """,
    height=0,
)

# Now that page config is set, we can initialize session state
initialize_session_state()

# Define company colors
COMPANY_COLORS = {
    "Alphabet": ["#4285F4", "#DB4437", "#F4B400", "#0F9D58"],
    "Apple": ["#000000", "#A3AAAE"],
    "Meta": ["#0668E1", "#0080FB", "#1C2B33"],
    "Meta Platforms": ["#0668E1", "#0080FB", "#1C2B33"],
    "Microsoft": ["#F25022", "#7FBA00", "#00A4EF", "#FFB900", "#737373"],
    "Amazon": ["#FF9900", "#000000"],
    "Netflix": ["#E50914", "#B20710"],
    "Disney": ["#113CCF", "#FFFFFF", "#BFF5FD"],
    "Comcast": ["#FFBA00", "#F56F02", "#CB1F47", "#645DAC", "#0088D2", "#00B345"],
    "Warner Bros. Discovery": ["#D0A22D", "#0034C1"],
    "Warner Bros Discovery": ["#D0A22D", "#0034C1"],
    "Paramount": ["#000A3B"],
    "Paramount Global": ["#000A3B"],
    "Spotify": ["#1ED760"],
    "Roku": ["#6F1AB1"],
    "Pinterest": ["#E60023", "#E60045", "#E50068", "#E5008A"],
}

# Tickers used for compact labels inside charts.
COMPANY_TICKERS = {
    "Alphabet": "GOOGL",
    "Apple": "AAPL",
    "Amazon": "AMZN",
    "Meta Platforms": "META",
    "Meta": "META",
    "Microsoft": "MSFT",
    "Netflix": "NFLX",
    "Disney": "DIS",
    "Comcast": "CMCSA",
    "Paramount Global": "PARA",
    "Paramount": "PARA",
    "Warner Bros. Discovery": "WBD",
    "Warner Bros Discovery": "WBD",
    "Spotify": "SPOT",
    "Roku": "ROKU",
}


def company_ticker(company: str) -> str:
    name = str(company or "").strip()
    return COMPANY_TICKERS.get(name, name[:5].upper() if name else "")


def _clean_overview_text(value) -> str:
    text = str(value if value is not None else "").strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def _clean_insight_comment_text(value) -> str:
    text = _clean_overview_text(value)
    if not text:
        return ""
    # Remove worksheet artifacts like "Chart: c1", "[Chart: nan]" and "(Chart note: ...)".
    text = re.sub(r"\[?\s*chart\s*:\s*[^\]\n\r]+?\]?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bchart\s*c\d+\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(?\s*chart\s*note\s*:\s*[^)\n\r]+?\)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


_COUNTRY_LABEL_OVERRIDES = {
    "United States": "USA",
    "United Kingdom": "UK",
    "United Arab Emirates": "UAE",
    "South Korea": "KOR",
    "Saudi Arabia": "SAU",
    "New Zealand": "NZ",
    "Czech Republic": "CZE",
    "Hong Kong": "HK",
    "Italy": "ITA",
}


def _country_short_label(country: str) -> str:
    name = str(country or "").strip()
    if not name:
        return ""
    if name in _COUNTRY_LABEL_OVERRIDES:
        return _COUNTRY_LABEL_OVERRIDES[name]
    parts = re.findall(r"[A-Za-z]+", name)
    if not parts:
        return name[:3].upper()
    if len(parts) == 1:
        return parts[0][:3].upper()
    initials = "".join(p[0] for p in parts[:3]).upper()
    if len(initials) >= 2:
        return initials
    return name[:3].upper()


def _normalize_quarter_label(value) -> str:
    q = _parse_quarter_number(value)
    return f"Q{q}" if q else ""


def _chart_anchor_id(chart_key: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", str(chart_key or "").strip().lower()).strip("-")
    return f"ov-chart-{token or 'unknown'}"


def _lookup_chart_row_from_overview_sheet(
    section_title: str,
    selected_year: int | None,
    selected_quarter: str | None,
    selected_chart_key: str | None = None,
) -> tuple[pd.Series | None, str]:
    data_processor = get_data_processor()
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    if not excel_path:
        return None, ""
    df = _load_overview_charts_sheet(excel_path, source_stamp)
    if df.empty:
        return None, ""

    title_norm = _normalize_overview_colname(section_title)
    chart_key_norm = _normalize_overview_colname(selected_chart_key or "")
    if chart_key_norm:
        chart_rows = df[df["_chart_key_norm"] == chart_key_norm].copy()
    elif title_norm:
        chart_rows = df[df["_title_norm"] == title_norm].copy()
    else:
        chart_rows = pd.DataFrame()
    if chart_rows.empty:
        return None, ""

    scoped, period_label = _pick_rows_for_period(chart_rows, selected_year, selected_quarter)
    if scoped.empty:
        return None, ""
    row = scoped.sort_values(["year", "_quarter_num", "chart_key"], ascending=[False, False, True]).iloc[0]
    return row, period_label


def _lookup_chart_comments_from_overview_sheet(
    section_title: str,
    selected_year: int | None,
    selected_quarter: str | None,
    selected_chart_key: str | None = None,
) -> tuple[str, str, str]:
    row, period_label = _lookup_chart_row_from_overview_sheet(
        section_title=section_title,
        selected_year=selected_year,
        selected_quarter=selected_quarter,
        selected_chart_key=selected_chart_key,
    )
    if row is None:
        return "", "", ""
    pre_comment = _clean_overview_text(row.get("pre_comment"))
    post_comment = _clean_overview_text(row.get("post_comment"))
    return pre_comment, post_comment, period_label


def _lookup_chart_key_for_title(
    section_title: str,
    selected_year: int | None,
    selected_quarter: str | None,
) -> str:
    row, _ = _lookup_chart_row_from_overview_sheet(
        section_title=section_title,
        selected_year=selected_year,
        selected_quarter=selected_quarter,
        selected_chart_key=None,
    )
    if row is None:
        return ""
    return _clean_overview_text(row.get("chart_key"))


def _lookup_chart_title_for_key(
    chart_key: str,
    selected_year: int | None,
    selected_quarter: str | None,
) -> str:
    key = _clean_overview_text(chart_key)
    if not key:
        return ""
    row, _ = _lookup_chart_row_from_overview_sheet(
        section_title="",
        selected_year=selected_year,
        selected_quarter=selected_quarter,
        selected_chart_key=key,
    )
    if row is None:
        return ""
    return _clean_overview_text(row.get("title"))


def render_standard_overview_comment(
    section_title: str,
    selected_period=None,
    period_label: str = "Year",
    chart_key: str | None = None,
) -> None:
    selected_quarter = st.session_state.get("overview_selected_quarter", "Q4")
    effective_chart_key = _clean_overview_text(chart_key)
    if not effective_chart_key:
        effective_chart_key = _lookup_chart_key_for_title(
            section_title=section_title,
            selected_year=selected_period if selected_period is not None else None,
            selected_quarter=selected_quarter,
        )
    if effective_chart_key:
        st.markdown(
            f"<div id=\"{_chart_anchor_id(effective_chart_key)}\" class=\"ov-chart-anchor\"></div>",
            unsafe_allow_html=True,
        )
    pre_comment, _, _ = _lookup_chart_comments_from_overview_sheet(
        section_title=section_title,
        selected_year=selected_period if selected_period is not None else None,
        selected_quarter=selected_quarter,
        selected_chart_key=effective_chart_key or None,
    )
    if pre_comment:
        pre_html = html.escape(pre_comment).replace("\n", "<br>")
        st.markdown(f"<p class='ov-chart-comment'>{pre_html}</p>", unsafe_allow_html=True)


def render_standard_overview_post_comment(
    section_title: str,
    selected_period=None,
    chart_key: str | None = None,
) -> None:
    selected_quarter = st.session_state.get("overview_selected_quarter", "Q4")
    effective_chart_key = _clean_overview_text(chart_key)
    if not effective_chart_key:
        effective_chart_key = _lookup_chart_key_for_title(
            section_title=section_title,
            selected_year=selected_period if selected_period is not None else None,
            selected_quarter=selected_quarter,
        )
    _, post_comment, _ = _lookup_chart_comments_from_overview_sheet(
        section_title=section_title,
        selected_year=selected_period if selected_period is not None else None,
        selected_quarter=selected_quarter,
        selected_chart_key=effective_chart_key or None,
    )
    if post_comment:
        post_html = html.escape(post_comment).replace("\n", "<br>")
        st.markdown(f"<p class='ov-chart-comment-post'>{post_html}</p>", unsafe_allow_html=True)


# Helper functions
def format_large_number(value):
    """Format large numbers to billions/trillions with proper rounding"""
    if value is None:
        return "N/A"
    
    abs_value = abs(value)
    
    if abs_value >= 1_000_000:  # >= 1 trillion (numbers in millions)
        formatted = f"${value / 1_000_000:.1f}T"
    elif abs_value >= 1_000:    # >= 1 billion (numbers in millions)
        formatted = f"${value / 1_000:.1f}B"
    else:                       # < 1 billion
        formatted = f"${value:.1f}M"
        
    return formatted


def format_large_number_precise(value):
    """More precise formatting for treemaps (avoid ties like 2.4T vs 2.4T)."""
    if value is None:
        return "N/A"
    abs_value = abs(value)
    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.2f}T"
    if abs_value >= 1_000:
        return f"${value / 1_000:.2f}B"
    return f"${value:.1f}M"

def _format_employee_count(value):
    if value is None:
        return "N/A"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if value >= 1_000_000:
        return f"{value/1_000_000:.2f}M"
    return f"{value:,.0f}"

def _format_subscribers(value, unit="millions"):
    if value is None:
        return "N/A"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"
    unit_str = str(unit or "").lower()
    if "million" in unit_str or unit_str in {"m", "mm"}:
        return f"{value:,.1f}M"
    if "thousand" in unit_str or unit_str in {"k"}:
        return f"{value:,.0f}K"
    return f"{value:,.0f}"

def _parse_quarter_number(quarter_value):
    s = str(quarter_value or "").strip().upper()
    if not s or s == "NAN":
        return None
    if s.startswith("Q") and len(s) >= 2 and s[1].isdigit():
        q = int(s[1])
        return q if 1 <= q <= 4 else None
    if "Q" in s:
        parts = s.split("Q", 1)
        if len(parts) == 2 and parts[1] and parts[1][0].isdigit():
            q = int(parts[1][0])
            return q if 1 <= q <= 4 else None
    if s.isdigit():
        q = int(s)
        return q if 1 <= q <= 4 else None
    return None

def _format_ad_revenue_billions(value):
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"
    # The advertising revenue sheet is treated as USD billions.
    return f"${v:.1f}B"


def _hex_to_rgb(hex_color: str):
    hex_color = (hex_color or "").strip().lstrip("#")
    if len(hex_color) != 6:
        return (17, 24, 39)
    try:
        return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))
    except ValueError:
        return (17, 24, 39)


def _pick_contrast_text(hex_color: str) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#111827" if luminance > 0.64 else "#FFFFFF"


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    a = max(0.0, min(1.0, float(alpha)))
    return f"rgba({r}, {g}, {b}, {a:.3f})"


def get_company_primary_color(company: str) -> str:
    company_str = str(company).strip()
    base_company = company_str.split("—", 1)[0].strip()
    base_company = base_company.replace("+", "").strip()
    palette = (
        COMPANY_COLORS.get(company_str)
        or COMPANY_COLORS.get(base_company)
        or COMPANY_COLORS.get(company_str.replace("+", "").strip())
        or ["#E5E7EB"]
    )
    return palette[0] if palette else "#E5E7EB"


def company_logo_html(company: str, logos: dict, size_px: int = 44) -> str:
    company_str = str(company).strip()
    base_company = company_str.split("—", 1)[0].strip()
    # Meta properties are tracked as separate "services" but should use the Meta logo.
    if company_str.lower() in {"whatsapp", "instagram", "facebook"}:
        base_company = "Meta Platforms"
    logo_candidates = [
        company_str,
        base_company,
        company_str.replace("+", "").strip(),
        base_company.replace("+", "").strip(),
    ]
    b64 = None
    for key in logo_candidates:
        b64 = logos.get(key) or logos.get(str(key).strip())
        if b64:
            break
    if not b64:
        return f"<div style='font-weight:700; font-size: 1rem; text-align:right;'>{company_str}</div>"
    return (
        "<img "
        f"src='data:image/png;base64,{b64}' "
        f"alt='{company_str} logo' "
        f"style='height:{size_px}px; width:{size_px}px; object-fit:contain; display:block;'"
        "/>"
    )


_INSIGHT_COMPANY_PATTERNS: list[tuple[str, list[str]]] = [
    ("Alphabet", [r"\balphabet\b", r"\bgoogle\b", r"\byoutube\b"]),
    ("Amazon", [r"\bamazon\b"]),
    ("Apple", [r"\bapple\b", r"\biphone\b"]),
    ("Meta Platforms", [r"\bmeta\b", r"\bfacebook\b", r"\binstagram\b", r"\bwhatsapp\b"]),
    ("Microsoft", [r"\bmicrosoft\b", r"\bazure\b"]),
    ("Netflix", [r"\bnetflix\b"]),
    ("Disney", [r"\bdisney\b", r"\bdisney\+\b"]),
    ("Comcast", [r"\bcomcast\b"]),
    ("Paramount Global", [r"\bparamount\b"]),
    ("Warner Bros. Discovery", [r"\bwbd\b", r"\bwarner\s+bro(?:s|\.)?\b"]),
    ("Spotify", [r"\bspotify\b"]),
    ("Roku", [r"\broku\b"]),
    ("TikTok", [r"\btiktok\b"]),
]


def _company_logo_base64_for_insight(company: str, logos: dict) -> str:
    company_str = str(company).strip()
    candidates = [
        company_str,
        company_str.replace("Meta Platforms", "Meta"),
        company_str.replace("Warner Bros. Discovery", "Warner Bros Discovery"),
        company_str.replace("Warner Bros Discovery", "Warner Bros. Discovery"),
    ]
    for key in candidates:
        b64 = logos.get(key) or logos.get(str(key).strip())
        if b64:
            return b64
    return ""


def _extract_insight_companies(title: str, comment: str) -> list[str]:
    text = f"{str(title or '')} {str(comment or '')}"
    found: list[str] = []
    lowered = text.lower()
    for company, patterns in _INSIGHT_COMPANY_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                if company not in found:
                    found.append(company)
                break
    return found


def _inline_insight_company_logos_html(companies: list[str], logos: dict, size_px: int = 22) -> str:
    chips: list[str] = []
    for company in companies:
        b64 = _company_logo_base64_for_insight(company, logos)
        if not b64:
            continue
        chips.append(
            "<img "
            f"src='data:image/png;base64,{b64}' "
            f"alt='{html.escape(company)} logo' "
            f"title='{html.escape(company)}' "
            f"class='ov-insight-logo' "
            "onerror='this.style.display=\"none\";' "
            f"style='width:{int(size_px)}px; height:{int(size_px)}px;'"
            "/>"
        )
    if not chips:
        return ""
    return "<span class='ov-insight-logos'>" + "".join(chips) + "</span>"


def get_kpi_icon_html(metric_key: str) -> str:
    icon_color = "#0073ff"
    icons = {
        "revenue": (
            "<svg class='kpi-icon' viewBox='0 0 48 48' fill='none'>"
            f"<rect class='growth-bar' x='6' y='30' width='5' height='12' rx='2' fill='{icon_color}' />"
            f"<rect class='growth-bar' x='13' y='22' width='5' height='20' rx='2' fill='{icon_color}' />"
            f"<rect class='growth-bar' x='20' y='26' width='5' height='16' rx='2' fill='{icon_color}' />"
            f"<rect class='growth-bar' x='27' y='16' width='5' height='26' rx='2' fill='{icon_color}' />"
            f"<rect class='growth-bar' x='34' y='10' width='5' height='32' rx='2' fill='{icon_color}' />"
            "</svg>"
        ),
        "net_income": (
            "<svg class='kpi-icon dollar-pulse' viewBox='0 0 48 48' fill='none'>"
            f"<circle cx='24' cy='24' r='18' fill='{icon_color}' />"
            "<text x='24' y='32' font-size='24' font-weight='bold' fill='white' text-anchor='middle'>$</text>"
            "</svg>"
        ),
        "operating_income": (
            "<svg class='kpi-icon' viewBox='0 0 48 48' fill='none'>"
            "<g class='gear-rotate'>"
            f"<circle cx='24' cy='24' r='12' fill='{icon_color}' />"
            f"<rect x='22' y='5' width='4' height='7' rx='2' fill='{icon_color}' />"
            f"<rect x='22' y='36' width='4' height='7' rx='2' fill='{icon_color}' />"
            f"<rect x='36' y='22' width='7' height='4' rx='2' fill='{icon_color}' />"
            f"<rect x='5' y='22' width='7' height='4' rx='2' fill='{icon_color}' />"
            f"<rect x='32.5' y='9' width='4' height='7' rx='2' fill='{icon_color}' transform='rotate(45 34.5 12.5)' />"
            f"<rect x='10.5' y='31' width='4' height='7' rx='2' fill='{icon_color}' transform='rotate(45 12.5 34.5)' />"
            f"<rect x='10.5' y='10' width='4' height='7' rx='2' fill='{icon_color}' transform='rotate(-45 12.5 13.5)' />"
            f"<rect x='32.5' y='31' width='4' height='7' rx='2' fill='{icon_color}' transform='rotate(-45 34.5 34.5)' />"
            "</g>"
            "<circle cx='24' cy='24' r='6' fill='white' opacity='0.7' />"
            "</svg>"
        ),
        "cost_of_revenue": (
            "<svg class='kpi-icon' viewBox='0 0 48 48' fill='none'>"
            f"<ellipse class='coin-stack' cx='24' cy='32' rx='10' ry='4' fill='{icon_color}' />"
            f"<ellipse class='coin-stack' cx='24' cy='24' rx='10' ry='4' fill='{icon_color}' />"
            f"<ellipse class='coin-stack' cx='24' cy='16' rx='10' ry='4' fill='{icon_color}' />"
            "</svg>"
        ),
        "rd": (
            "<svg class='kpi-icon' viewBox='0 0 48 48' fill='none'>"
            f"<path class='bulb-glow' d='M24 8C19.58 8 16 11.58 16 16C16 19.5 18.14 22.54 21.18 23.8V28H26.82V23.8C29.86 22.54 32 19.5 32 16C32 11.58 28.42 8 24 8Z' fill='{icon_color}' />"
            "<path class='bulb-glow-ghost' d='M24 8C19.58 8 16 11.58 16 16C16 19.5 18.14 22.54 21.18 23.8V28H26.82V23.8C29.86 22.54 32 19.5 32 16C32 11.58 28.42 8 24 8Z' fill='white' />"
            f"<rect x='20' y='30' width='8' height='6' rx='1' fill='{icon_color}' />"
            f"<rect x='20' y='38' width='8' height='3' rx='1.5' fill='{icon_color}' />"
            "</svg>"
        ),
        "capex": (
            "<svg class='kpi-icon' viewBox='0 0 48 48' fill='none'>"
            f"<rect class='block-build' x='6' y='28' width='10' height='12' rx='2' fill='{icon_color}' />"
            f"<rect class='block-build' x='19' y='20' width='10' height='20' rx='2' fill='{icon_color}' />"
            f"<rect class='block-build' x='32' y='12' width='10' height='28' rx='2' fill='{icon_color}' />"
            "</svg>"
        ),
        "total_assets": (
            "<svg class='kpi-icon' viewBox='0 0 48 48' fill='none'>"
            f"<circle cx='24' cy='24' r='16' fill='{icon_color}' opacity='0.2' />"
            f"<path class='pie-slice slice-1' d='M24 8A16 16 0 0 1 38 18L24 24Z' fill='{icon_color}' />"
            f"<path class='pie-slice slice-2' d='M38 18A16 16 0 0 1 30 38L24 24Z' fill='{icon_color}' opacity='0.85' />"
            f"<path class='pie-slice slice-3' d='M30 38A16 16 0 0 1 10 30L24 24Z' fill='{icon_color}' opacity='0.7' />"
            "</svg>"
        ),
        "debt": (
            "<svg class='kpi-icon' viewBox='0 0 48 48' fill='none'>"
            f"<path class='trend-line' d='M24 10 L24 32' stroke='{icon_color}' stroke-width='4' stroke-linecap='round' />"
            f"<path class='trend-line' d='M24 32 L16 24' stroke='{icon_color}' stroke-width='4' stroke-linecap='round' />"
            f"<path class='trend-line' d='M24 32 L32 24' stroke='{icon_color}' stroke-width='4' stroke-linecap='round' />"
            "</svg>"
        ),
        "cash_balance": (
            "<svg class='kpi-icon' viewBox='0 0 48 48' fill='none'>"
            f"<rect class='money-float' x='8' y='14' width='32' height='6' rx='2' fill='{icon_color}' />"
            f"<rect class='money-float' x='8' y='22' width='32' height='6' rx='2' fill='{icon_color}' />"
            f"<rect class='money-float' x='8' y='30' width='32' height='6' rx='2' fill='{icon_color}' />"
            "</svg>"
        ),
        "market_cap": (
            "<svg class='kpi-icon' viewBox='0 0 48 48' fill='none'>"
            f"<path class='arrow-up' d='M24 8 L34 18 L29.5 18 L29.5 26 L18.5 26 L18.5 18 L14 18 Z' fill='{icon_color}' />"
            f"<rect x='14' y='32' width='20' height='4' rx='2' fill='{icon_color}' />"
            f"<rect x='12' y='37' width='24' height='5' rx='2.5' fill='{icon_color}' />"
            "</svg>"
        ),
    }
    svg = icons.get(metric_key)
    if not svg:
        return ""
    return f"<div class='kpi-icon-wrap'>{svg}</div>"


def render_summary_card(title: str, company: str, value_text: str, logos: dict, icon_key: str = "") -> str:
    bg = get_company_primary_color(company)
    bg_rgba = _hex_to_rgba(bg, 0.60)
    fg = _pick_contrast_text(bg)
    border = "rgba(255,255,255,0.25)" if fg == "#FFFFFF" else "rgba(15,23,42,0.12)"
    icon_html = get_kpi_icon_html(icon_key) if icon_key else ""
    style = (
        f"background:{bg_rgba};"
        f"color:{fg};"
        "padding:14px 14px;"
        "border-radius:12px;"
        "margin-bottom:10px;"
        "box-shadow:0 8px 18px rgba(15, 23, 42, 0.12);"
        f"border:1px solid {border};"
    )
    return _html_block(
        f"""
        <div class="overview-summary-card" style="{style}">
          <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px;">
            <div style="display:flex; flex-direction:column; align-items:flex-start;">
              <div style="font-size:0.98rem; font-weight:800; margin:0; line-height:1.15;">{title}</div>
              {icon_html}
            </div>
            <div style="flex:0 0 auto; display:flex; align-items:center; justify-content:flex-end;">
              {company_logo_html(company, logos, size_px=72)}
            </div>
          </div>
          <div style="font-size:1.35rem; font-weight:800; margin-top:10px; line-height:1.1;">{value_text}</div>
        </div>
        """
    )

def render_split_summary_card(
    left_title: str,
    left_company: str,
    left_value_text: str,
    right_title: str,
    right_company: str,
    right_value_text: str,
    logos: dict,
    left_icon_key: str = "",
    right_icon_key: str = "",
) -> str:
    left_bg = get_company_primary_color(left_company)
    right_bg = get_company_primary_color(right_company)
    left_bg_rgba = _hex_to_rgba(left_bg, 0.60)
    right_bg_rgba = _hex_to_rgba(right_bg, 0.60)
    left_fg = _pick_contrast_text(left_bg)
    right_fg = _pick_contrast_text(right_bg)

    left_icon_html = get_kpi_icon_html(left_icon_key) if left_icon_key else ""
    right_icon_html = get_kpi_icon_html(right_icon_key) if right_icon_key else ""

    # Streamlit markdown can treat indented lines as code blocks; normalize indentation.
    return _html_block(
        f"""
        <div style="display:flex; overflow:hidden; border-radius:12px; margin-bottom:10px; box-shadow:0 8px 18px rgba(15,23,42,0.12); border:1px solid rgba(15,23,42,0.12);">
          <div class="overview-summary-card" style="flex:1 1 0; background:{left_bg_rgba}; color:{left_fg}; padding:14px 14px;">
            <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px;">
              <div style="display:flex; flex-direction:column; align-items:flex-start;">
                <div style="font-size:0.98rem; font-weight:800; margin:0; line-height:1.15;">{left_title}</div>
                {left_icon_html}
              </div>
              <div style="flex:0 0 auto; display:flex; align-items:center; justify-content:flex-end;">
                {company_logo_html(left_company, logos, size_px=64)}
              </div>
            </div>
            <div style="font-size:1.35rem; font-weight:800; margin-top:10px; line-height:1.1;">{left_value_text}</div>
          </div>
          <div style="width:1px; background:rgba(255,255,255,0.28);"></div>
          <div class="overview-summary-card" style="flex:1 1 0; background:{right_bg_rgba}; color:{right_fg}; padding:14px 14px;">
            <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px;">
              <div style="display:flex; flex-direction:column; align-items:flex-start;">
                <div style="font-size:0.98rem; font-weight:800; margin:0; line-height:1.15;">{right_title}</div>
                {right_icon_html}
              </div>
              <div style="flex:0 0 auto; display:flex; align-items:center; justify-content:flex-end;">
                {company_logo_html(right_company, logos, size_px=64)}
              </div>
            </div>
            <div style="font-size:1.35rem; font-weight:800; margin-top:10px; line-height:1.1;">{right_value_text}</div>
          </div>
        </div>
        """
    )

def compute_yoy(metrics, metrics_prev, key):
    """Safely compute YoY percentage change for a metric."""
    if not metrics:
        return None
    fallback = metrics.get(f"{key}_yoy")
    if not metrics_prev:
        return fallback
    current = metrics.get(key)
    previous = metrics_prev.get(key)
    if current is None or previous is None:
        return fallback
    try:
        if previous == 0:
            return fallback
        return ((current - previous) / previous) * 100
    except ZeroDivisionError:
        return fallback

def get_available_companies(data_processor):
    """Get list of available companies from data processor"""
    return data_processor.get_companies()

def get_available_years(data_processor):
    """Get list of available years for all companies"""
    df_metrics = getattr(data_processor, "df_metrics", None)
    if df_metrics is not None and not df_metrics.empty:
        years = df_metrics["year"].dropna().unique().tolist()
        normalized = sorted({int(y) for y in years if pd.notna(y)})
        if normalized:
            return normalized

    # Fallback: read metrics years directly from workbook when processor index is empty.
    excel_path = getattr(data_processor, "data_path", "")
    if excel_path and Path(excel_path).exists():
        try:
            workbook_years = pd.read_excel(
                excel_path,
                sheet_name="Company_metrics_earnings_values",
                usecols=["Year"],
            )
            if workbook_years is not None and not workbook_years.empty:
                vals = pd.to_numeric(workbook_years["Year"], errors="coerce").dropna().astype(int).tolist()
                vals = sorted(set(vals))
                if vals:
                    return vals
        except Exception:
            pass

    common_years = list(range(2010, 2025))
    available_years = []
    companies = get_available_companies(data_processor)

    for year in common_years:
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and any(metrics.values()):
                available_years.append(year)
                break

    return sorted(available_years)

@st.cache_data(ttl=3600)
def _load_country_advertising_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Country_Advertising_Data_FullVi")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    required = {"Country", "Year", "Metric_type", "Value"}
    if not required.issubset(set(df.columns)):
        return pd.DataFrame()
    df["Country"] = df["Country"].astype(str).str.strip()
    df["Metric_type"] = df["Metric_type"].astype(str).str.strip()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["Country", "Year", "Metric_type", "Value"])
    df["Year"] = df["Year"].astype(int)
    return df


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


@st.cache_data(ttl=3600)
def _load_groupm_channels_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Global Advertising (GroupM)")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    if "year" in df.columns and "Year" not in df.columns:
        df = df.rename(columns={"year": "Year"})
    known = [
        "Traditional_TV",
        "Connected_TV",
        "Traditional_OOH",
        "Digital_OOH",
        "Search",
        "NonSearch",
        "Retail_Media",
    ]
    if "Year" not in df.columns:
        return pd.DataFrame()

    present = [col for col in known if col in df.columns]
    out = df[["Year"] + present].copy()
    for col in known:
        if col not in out.columns:
            out[col] = np.nan
    out = out[["Year"] + known]
    out["Year"] = _coerce_numeric(out["Year"])
    for col in known:
        out[col] = _coerce_numeric(out[col])
    out = out.dropna(subset=["Year"]).copy()
    out["Year"] = out["Year"].astype(int)
    out = out.sort_values("Year")
    return out


@st.cache_data(ttl=3600)
def _load_groupm_granular_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name=" (GroupM) Granular ")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    if "year" in df.columns and "Year" not in df.columns:
        df = df.rename(columns={"year": "Year"})
    required = ["Year", "TV / Pro Video", "Internet"]
    if not set(required).issubset(df.columns):
        return pd.DataFrame()

    optional = ["Audio", "Newspapers", "Magazines", "OOH", "Cinema", "Total Advertising"]
    present_optional = [col for col in optional if col in df.columns]
    out = df[required + present_optional].copy()
    for col in optional:
        if col not in out.columns:
            out[col] = np.nan
    out = out[required + optional]

    for col in required + optional:
        out[col] = _coerce_numeric(out[col])
    if out["Total Advertising"].isna().all():
        component_cols = [col for col in ["TV / Pro Video", "Internet", "Audio", "Newspapers", "Magazines", "OOH", "Cinema"] if col in out.columns]
        if component_cols:
            out["Total Advertising"] = out[component_cols].sum(axis=1, min_count=1)
    out = out.dropna(subset=["Year"]).copy()
    out["Year"] = out["Year"].astype(int)
    out = out.sort_values("Year")
    return out


@st.cache_data(ttl=3600)
def _load_groupm_total_ad_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name=" (GroupM) Granular ")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    if "year" in df.columns and "Year" not in df.columns:
        df = df.rename(columns={"year": "Year"})
    required = ["Year", "Total Advertising"]
    if not set(required).issubset(df.columns):
        return pd.DataFrame()

    out = df[required].copy()
    out["Year"] = _coerce_numeric(out["Year"])
    out["Total Advertising"] = _coerce_numeric(out["Total Advertising"])
    out = out.dropna(subset=["Year", "Total Advertising"]).copy()
    out["Year"] = out["Year"].astype(int)
    out = out.sort_values("Year")
    return out


def _coerce_percent_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace("$", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


@st.cache_data(ttl=3600)
def _load_stocks_crypto_timeseries_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Stocks & Crypto", usecols=["date", "price", "asset"])
    except Exception:
        try:
            df = pd.read_excel(path, sheet_name="Stocks & Crypto")
        except Exception:
            return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    date_col = _find_column_by_alias(out, ["date", "datetime", "timestamp"])
    price_col = _find_column_by_alias(out, ["price", "close", "close price", "closing price", "adj close", "adj_close"])
    asset_col = _find_column_by_alias(out, ["asset", "name", "symbol", "ticker"])
    if not date_col or not price_col or not asset_col:
        return pd.DataFrame()
    out = out.rename(columns={date_col: "date", price_col: "price", asset_col: "asset"})
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out["asset"] = out["asset"].astype(str).str.strip()
    out = out.dropna(subset=["date", "price", "asset"])
    if out.empty:
        return pd.DataFrame()
    return out.sort_values("date")


@st.cache_data(ttl=3600)
def _load_m2_yearly_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="M2_values")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    value_col = _find_column_by_alias(out, ["WM2NS", "WM2", "M2", "M2 Value", "M2_values"])
    if not value_col:
        return pd.DataFrame()

    date_col = _find_column_by_alias(
        out,
        [
            "USD observation_date",
            "observation_date",
            "observation",
            "date",
            "period",
        ],
    )
    year_col = _find_column_by_alias(out, ["Year", "year"])
    quarter_col = _find_column_by_alias(out, ["Quarter", "quarter", "Qtr", "qtr"])

    # Google-sheet XLSX exports can occasionally mutate header text;
    # detect a date-like column from values when the header lookup fails.
    if not date_col:
        min_valid = max(3, int(len(out) * 0.4))
        for col in out.columns:
            if col == value_col:
                continue
            series = out[col]
            if pd.api.types.is_datetime64_any_dtype(series):
                date_col = col
                break
            parsed = pd.to_datetime(series, errors="coerce")
            if parsed.notna().sum() >= min_valid:
                out[col] = parsed
                date_col = col
                break

    out["M2"] = pd.to_numeric(out[value_col], errors="coerce")

    if date_col:
        out["_date"] = pd.to_datetime(out[date_col], errors="coerce")
        out["Year"] = out["_date"].dt.year
        out["QuarterNum"] = out["_date"].dt.quarter
    elif year_col:
        out["Year"] = pd.to_numeric(out[year_col], errors="coerce")
        out["QuarterNum"] = out[quarter_col].apply(_parse_quarter_number) if quarter_col else 4
    else:
        return pd.DataFrame()

    out["QuarterNum"] = pd.to_numeric(out["QuarterNum"], errors="coerce").fillna(4).clip(lower=1, upper=4)
    out = out.dropna(subset=["Year", "M2"]).copy()
    if out.empty:
        return pd.DataFrame()

    out["Year"] = out["Year"].astype(int)
    out["QuarterNum"] = out["QuarterNum"].astype(int)
    sort_cols = ["Year", "QuarterNum"]
    if "_date" in out.columns:
        sort_cols.append("_date")

    quarterly = (
        out.sort_values(sort_cols)
        .groupby(["Year", "QuarterNum"], as_index=False)
        .tail(1)
        .copy()
    )
    yearly = (
        quarterly.sort_values(["Year", "QuarterNum"])
        .groupby("Year", as_index=False)
        .tail(1)
        .copy()
    )
    yearly["M2_B"] = yearly["M2"]
    return yearly[["Year", "M2_B"]].sort_values("Year").reset_index(drop=True)


@st.cache_data(ttl=3600)
def _load_m2_quarterly(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="M2_values")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    value_col = _find_column_by_alias(out, ["WM2NS", "WM2", "M2", "M2 Value", "M2_values"])
    date_col = _find_column_by_alias(
        out,
        ["USD observation_date", "observation_date", "observation", "date", "period"],
    )
    if not value_col:
        return pd.DataFrame()

    if not date_col:
        min_valid = max(3, int(len(out) * 0.4))
        for col in out.columns:
            if col == value_col:
                continue
            parsed = pd.to_datetime(out[col], errors="coerce")
            if parsed.notna().sum() >= min_valid:
                out[col] = parsed
                date_col = col
                break
    if not date_col:
        return pd.DataFrame()

    out["date"] = pd.to_datetime(out[date_col], errors="coerce")
    out["m2_usd_bn"] = pd.to_numeric(out[value_col], errors="coerce")
    out = out.dropna(subset=["date", "m2_usd_bn"]).copy()
    if out.empty:
        return pd.DataFrame()

    out["year"] = out["date"].dt.year.astype(int)
    out["quarter"] = out["date"].dt.quarter.astype(int)
    out["month"] = out["date"].dt.month.astype(int)

    quarterly = (
        out.groupby(["year", "quarter"], as_index=False)
        .agg(
            m2_usd_bn=("m2_usd_bn", "mean"),
            month_count=("month", "nunique"),
        )
        .sort_values(["year", "quarter"])
    )
    quarterly = quarterly[quarterly["month_count"] >= 3].copy()
    if quarterly.empty:
        return pd.DataFrame(columns=["year", "quarter", "m2_usd_bn"])
    return quarterly[["year", "quarter", "m2_usd_bn"]].reset_index(drop=True)


@st.cache_data(ttl=3600)
def _load_inflation_yearly_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="USD Inflation")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    year_col = _find_column_by_alias(out, ["Year", "year"])
    date_col = _find_column_by_alias(out, ["date", "period", "observation_date", "observation"])
    infl_col = _find_column_by_alias(
        out,
        [
            "Official Headline CPI",
            "official_headline_cpi",
            "Inflation",
            "Inflation YoY",
            "CPI YoY",
        ],
    )

    if not infl_col:
        return pd.DataFrame()

    if year_col:
        out["Year"] = pd.to_numeric(out[year_col], errors="coerce")
    elif date_col:
        out["Year"] = pd.to_datetime(out[date_col], errors="coerce").dt.year
    else:
        return pd.DataFrame()

    out["Inflation_YoY"] = _coerce_percent_series(out[infl_col])
    out = out.dropna(subset=["Year", "Inflation_YoY"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["Year"] = out["Year"].astype(int)

    # If monthly/quarterly rows are present, aggregate to annual for bridge charts.
    out = out.groupby("Year", as_index=False)["Inflation_YoY"].mean()
    return out[["Year", "Inflation_YoY"]].sort_values("Year").reset_index(drop=True)


@st.cache_data(ttl=3600)
def _load_company_metrics_yearly_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Company_metrics_earnings_values")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    col_map = {
        "Company": "Company",
        "Year": "Year",
        "Revenue": "Revenue",
        "Debt": "Debt",
        "Market Cap.": "MarketCap",
        "Operating Income": "OperatingIncome",
        "Net Income": "NetIncome",
        "Cost Of Revenue": "CostOfRevenue",
        "Total Assets": "TotalAssets",
        "R&D": "RD",
        "Capex": "Capex",
        "Cash Balance": "CashBalance",
    }
    for src, dst in col_map.items():
        if src not in out.columns:
            out[src] = np.nan if src != "Company" else ""
        out = out.rename(columns={src: dst})

    out["Company"] = out["Company"].astype(str).str.strip()
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    for col in [
        "Revenue",
        "Debt",
        "MarketCap",
        "OperatingIncome",
        "NetIncome",
        "CostOfRevenue",
        "TotalAssets",
        "RD",
        "Capex",
        "CashBalance",
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["Company", "Year"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["Year"] = out["Year"].astype(int)
    return out


@st.cache_data(ttl=3600)
def _load_employee_yearly_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Company_Employees")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    company_col = "Company" if "Company" in out.columns else None
    year_col = "Year" if "Year" in out.columns else None
    emp_col = "Employee Count" if "Employee Count" in out.columns else ("employees" if "employees" in out.columns else None)
    if not company_col or not year_col or not emp_col:
        return pd.DataFrame()

    out = out.rename(columns={company_col: "Company", year_col: "Year", emp_col: "Employees"})
    out["Company"] = out["Company"].astype(str).str.strip()
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    out["Employees"] = pd.to_numeric(out["Employees"], errors="coerce")
    out = out.dropna(subset=["Company", "Year", "Employees"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["Year"] = out["Year"].astype(int)
    return out[["Company", "Year", "Employees"]]


@st.cache_data(ttl=3600)
def _load_global_ad_vs_gdp_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Country_Totals_vs_GDP")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    required = ["Year", "AdSpending_USD", "GDP_USD"]
    if not set(required).issubset(out.columns):
        return pd.DataFrame()
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    out["AdSpending_USD"] = pd.to_numeric(out["AdSpending_USD"], errors="coerce")
    out["GDP_USD"] = pd.to_numeric(out["GDP_USD"], errors="coerce")
    out = out.dropna(subset=["Year", "AdSpending_USD", "GDP_USD"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["Year"] = out["Year"].astype(int)
    agg = out.groupby("Year", as_index=False)[["AdSpending_USD", "GDP_USD"]].sum(min_count=1)
    agg = agg[agg["GDP_USD"] > 0].copy()
    if agg.empty:
        return pd.DataFrame()
    agg["Ad_vs_GDP_pct"] = (agg["AdSpending_USD"] / agg["GDP_USD"]) * 100.0
    return agg.sort_values("Year").reset_index(drop=True)


_COUNTRY_TV_METRICS = {"Free TV", "Pay TV"}
_COUNTRY_INTERNET_METRICS = {
    "Display Desktop",
    "Display Mobile",
    "Search Desktop",
    "Search Mobile",
    "Social Desktop",
    "Social Mobile",
    "Video Desktop",
    "Video Mobile",
    "Other Desktop",
    "Other Mobile",
}
_COUNTRY_OOH_METRICS = {"Digital OOH", "Traditional OOH"}


@st.cache_data(ttl=3600)
def _load_country_ad_channel_yearly_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    src = _load_country_advertising_df(excel_path, source_stamp)
    if src.empty:
        return pd.DataFrame()

    df = src.copy()
    df["Country"] = df["Country"].astype(str).str.strip()
    df["Metric_type"] = df["Metric_type"].astype(str).str.strip()
    df = df[~df["Country"].str.lower().isin({"global", "world"})].copy()
    if df.empty:
        return pd.DataFrame()

    def _channel(metric: str) -> str:
        if metric in _COUNTRY_TV_METRICS:
            return "TV"
        if metric in _COUNTRY_INTERNET_METRICS:
            return "Internet"
        if metric in _COUNTRY_OOH_METRICS:
            return "OOH"
        return "Other"

    df["Channel"] = df["Metric_type"].apply(_channel)
    yearly_channel = (
        df.groupby(["Year", "Channel"], as_index=False)["Value"]
        .sum(min_count=1)
        .rename(columns={"Value": "AdSpend_MUSD"})
    )
    yearly_total = (
        df.groupby("Year", as_index=False)["Value"]
        .sum(min_count=1)
        .rename(columns={"Value": "TotalAdvertising_MUSD"})
    )
    out = yearly_channel.merge(yearly_total, on="Year", how="left")
    out["AdSpend_BUSD"] = out["AdSpend_MUSD"] / 1000.0
    out["TotalAdvertising_BUSD"] = out["TotalAdvertising_MUSD"] / 1000.0
    out = out.sort_values(["Year", "Channel"]).reset_index(drop=True)
    return out


@st.cache_data(ttl=3600)
def _load_country_totals_vs_gdp_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Country_Totals_vs_GDP")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    required = ["Country", "Year", "AdSpending_USD", "GDP_USD"]
    if not set(required).issubset(set(out.columns)):
        return pd.DataFrame()

    out["Country"] = out["Country"].astype(str).str.strip()
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    out["AdSpending_USD"] = pd.to_numeric(out["AdSpending_USD"], errors="coerce")
    out["GDP_USD"] = pd.to_numeric(out["GDP_USD"], errors="coerce")
    out = out.dropna(subset=required).copy()
    if out.empty:
        return pd.DataFrame()

    out["Year"] = out["Year"].astype(int)
    out = out[out["GDP_USD"] > 0].copy()
    if out.empty:
        return pd.DataFrame()
    out["Ad_vs_GDP_pct"] = (out["AdSpending_USD"] / out["GDP_USD"]) * 100.0
    out["AdSpending_BUSD"] = out["AdSpending_USD"] / 1_000_000_000.0
    out["GDP_BUSD"] = out["GDP_USD"] / 1_000_000_000.0
    return out.sort_values(["Year", "Country"]).reset_index(drop=True)


def _norm_sheet_col(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _find_column_by_alias(df: pd.DataFrame, aliases: list[str]) -> str | None:
    lookup = {_norm_sheet_col(c): c for c in df.columns}
    for alias in aliases:
        key = _norm_sheet_col(alias)
        if key in lookup:
            return lookup[key]
    return None


def _attach_year_quarter(
    df: pd.DataFrame,
    year_aliases: list[str],
    quarter_aliases: list[str],
    date_aliases: list[str],
) -> pd.DataFrame:
    out = df.copy()
    out["_year"] = np.nan
    out["_quarter_num"] = np.nan

    year_col = _find_column_by_alias(out, year_aliases)
    quarter_col = _find_column_by_alias(out, quarter_aliases)
    date_col = _find_column_by_alias(out, date_aliases)

    if year_col:
        out["_year"] = pd.to_numeric(out[year_col], errors="coerce")
    if quarter_col:
        out["_quarter_num"] = out[quarter_col].apply(_parse_quarter_number)

    if date_col:
        text = out[date_col].astype(str).str.strip()
        dt = pd.to_datetime(text, errors="coerce")
        year_from_text = pd.to_numeric(text.str.extract(r"((?:19|20)\d{2})", expand=False), errors="coerce")
        quarter_from_text = pd.to_numeric(text.str.extract(r"[Qq]\s*([1-4])", expand=False), errors="coerce")

        out["_year"] = out["_year"].fillna(dt.dt.year)
        out["_year"] = out["_year"].fillna(year_from_text)
        out["_quarter_num"] = out["_quarter_num"].fillna(dt.dt.quarter)
        out["_quarter_num"] = out["_quarter_num"].fillna(quarter_from_text)

    out["_year"] = pd.to_numeric(out["_year"], errors="coerce")
    out["_quarter_num"] = pd.to_numeric(out["_quarter_num"], errors="coerce").fillna(4)
    out["_quarter_num"] = out["_quarter_num"].clip(lower=1, upper=4)
    out = out.dropna(subset=["_year"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["Year"] = out["_year"].astype(int)
    out["QuarterNum"] = out["_quarter_num"].astype(int)
    out["Quarter"] = out["QuarterNum"].astype(int).apply(lambda q: f"Q{q}")
    return out


def _pick_macro_row_for_period(df: pd.DataFrame, selected_year: int, selected_quarter: str) -> pd.Series | None:
    if df is None or df.empty:
        return None
    scoped = df.copy()
    scoped["Year"] = pd.to_numeric(scoped["Year"], errors="coerce")
    scoped["QuarterNum"] = pd.to_numeric(scoped.get("QuarterNum", 4), errors="coerce").fillna(4)
    scoped = scoped.dropna(subset=["Year"]).copy()
    if scoped.empty:
        return None
    scoped["Year"] = scoped["Year"].astype(int)
    scoped["QuarterNum"] = scoped["QuarterNum"].astype(int).clip(lower=1, upper=4)

    qnum = _parse_quarter_number(selected_quarter) or 4
    eligible = scoped[
        (scoped["Year"] < int(selected_year))
        | ((scoped["Year"] == int(selected_year)) & (scoped["QuarterNum"] <= int(qnum)))
    ].copy()
    if eligible.empty:
        eligible = scoped.copy()
    if eligible.empty:
        return None
    return eligible.sort_values(["Year", "QuarterNum"]).iloc[-1]


def _get_overview_granularity_options(data_processor: FinancialDataProcessor) -> list[str]:
    excel_path = getattr(data_processor, "data_path", "")
    return get_available_granularity_options(excel_path, include_auto=True)


@st.cache_data(ttl=3600)
def _load_macro_interest_rates_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    raw, _sheet_used = _read_excel_sheet_flexible(
        excel_path=excel_path,
        source_stamp=source_stamp,
        preferred="Macro_Interest_Rates",
        aliases=["Interest_Rates", "Macro Interest Rates", "Rates"],
        contains_all=["rate"],
        contains_any=["interest", "fed", "treasury", "yield", "funds"],
    )
    if raw.empty:
        return pd.DataFrame()
    out = _attach_year_quarter(
        raw,
        year_aliases=["year"],
        quarter_aliases=["quarter", "qtr"],
        date_aliases=["date", "period"],
    )
    if out.empty:
        return pd.DataFrame()
    fed_col = _find_column_by_alias(out, ["fed_funds_rate", "fed funds rate", "fed_rate"])
    ten_col = _find_column_by_alias(out, ["10y_treasury", "10y", "ten_year_treasury", "treasury_10y"])
    two_col = _find_column_by_alias(out, ["2y_treasury", "2y", "two_year_treasury", "treasury_2y"])
    spread_col = _find_column_by_alias(out, ["yield_curve_spread", "yield_curve", "10y_2y_spread", "spread"])
    ecb_col = _find_column_by_alias(out, ["ecb_rate", "ecb"])
    regime_col = _find_column_by_alias(out, ["rate_regime", "regime"])
    comment_col = _find_column_by_alias(out, ["comment", "note", "macro_comment"])

    out["FedFundsRate"] = pd.to_numeric(out[fed_col], errors="coerce") if fed_col else np.nan
    out["TenYearTreasury"] = pd.to_numeric(out[ten_col], errors="coerce") if ten_col else np.nan
    out["TwoYearTreasury"] = pd.to_numeric(out[two_col], errors="coerce") if two_col else np.nan
    out["YieldCurveSpread"] = pd.to_numeric(out[spread_col], errors="coerce") if spread_col else np.nan
    out["ECBRate"] = pd.to_numeric(out[ecb_col], errors="coerce") if ecb_col else np.nan
    if out["YieldCurveSpread"].isna().all() and out["TenYearTreasury"].notna().any() and out["TwoYearTreasury"].notna().any():
        out["YieldCurveSpread"] = out["TenYearTreasury"] - out["TwoYearTreasury"]
    out["RateRegime"] = out[regime_col].astype(str).str.strip() if regime_col else ""
    out["Comment"] = out[comment_col].astype(str).str.strip() if comment_col else ""
    cols = [
        "Year",
        "QuarterNum",
        "Quarter",
        "FedFundsRate",
        "TenYearTreasury",
        "TwoYearTreasury",
        "YieldCurveSpread",
        "ECBRate",
        "RateRegime",
        "Comment",
    ]
    return out[cols].sort_values(["Year", "QuarterNum"]).reset_index(drop=True)


@st.cache_data(ttl=3600)
def _load_macro_gdp_growth_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    raw, _sheet_used = _read_excel_sheet_flexible(
        excel_path=excel_path,
        source_stamp=source_stamp,
        preferred="Macro_GDP_Growth",
        aliases=["GDP_Growth", "Macro GDP Growth", "GDP"],
        contains_all=["gdp"],
        contains_any=["growth", "macro"],
    )
    if raw.empty:
        # Fallback: derive global GDP YoY from Country_Totals_vs_GDP.
        country_totals = _load_country_totals_vs_gdp_df(excel_path, source_stamp)
        if country_totals.empty:
            return pd.DataFrame()
        gdp = (
            country_totals.groupby("Year", as_index=False)["GDP_USD"]
            .sum(min_count=1)
            .sort_values("Year")
        )
        gdp["Global_GDP_YoY"] = gdp["GDP_USD"].pct_change() * 100.0
        gdp = gdp.dropna(subset=["Global_GDP_YoY"]).copy()
        if gdp.empty:
            return pd.DataFrame()
        gdp["QuarterNum"] = 4
        gdp["Quarter"] = "Q4"
        gdp["US_GDP_YoY"] = np.nan
        gdp["Comment"] = "Derived from Country_Totals_vs_GDP"
        return gdp[["Year", "QuarterNum", "Quarter", "US_GDP_YoY", "Global_GDP_YoY", "Comment"]]
    out = _attach_year_quarter(
        raw,
        year_aliases=["year"],
        quarter_aliases=["quarter", "qtr"],
        date_aliases=["date", "period"],
    )
    if out.empty:
        return pd.DataFrame()
    us_yoy_col = _find_column_by_alias(out, ["us_gdp_yoy", "us_gdp_growth", "us_gdp_growth_yoy"])
    global_yoy_col = _find_column_by_alias(out, ["global_gdp_yoy", "global_gdp_growth", "world_gdp_yoy"])
    comment_col = _find_column_by_alias(out, ["comment", "note"])

    out["US_GDP_YoY"] = pd.to_numeric(out[us_yoy_col], errors="coerce") if us_yoy_col else np.nan
    out["Global_GDP_YoY"] = pd.to_numeric(out[global_yoy_col], errors="coerce") if global_yoy_col else np.nan
    out["Comment"] = out[comment_col].astype(str).str.strip() if comment_col else ""
    cols = ["Year", "QuarterNum", "Quarter", "US_GDP_YoY", "Global_GDP_YoY", "Comment"]
    out = out[cols].dropna(subset=["US_GDP_YoY", "Global_GDP_YoY"], how="all")
    return out.sort_values(["Year", "QuarterNum"]).reset_index(drop=True)


@st.cache_data(ttl=3600)
def _load_macro_labor_market_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    raw, _sheet_used = _read_excel_sheet_flexible(
        excel_path=excel_path,
        source_stamp=source_stamp,
        preferred="Macro_Labor_Market",
        aliases=["Labor_Market", "Macro Labor Market", "Labour Market"],
        contains_all=["labor"],
        contains_any=["market", "unemployment", "wage", "participation"],
    )
    if raw.empty:
        return pd.DataFrame()
    out = _attach_year_quarter(
        raw,
        year_aliases=["year"],
        quarter_aliases=["quarter", "qtr"],
        date_aliases=["date", "period"],
    )
    if out.empty:
        return pd.DataFrame()
    unemployment_col = _find_column_by_alias(out, ["us_unemployment_rate", "unemployment_rate", "unemployment"])
    participation_col = _find_column_by_alias(out, ["labor_force_participation", "participation"])
    real_wages_col = _find_column_by_alias(out, ["real_wages_yoy", "real_wage_yoy"])
    comment_col = _find_column_by_alias(out, ["comment", "note"])

    out["US_Unemployment_Rate"] = pd.to_numeric(out[unemployment_col], errors="coerce") if unemployment_col else np.nan
    out["Labor_Force_Participation"] = pd.to_numeric(out[participation_col], errors="coerce") if participation_col else np.nan
    out["Real_Wages_YoY"] = pd.to_numeric(out[real_wages_col], errors="coerce") if real_wages_col else np.nan
    out["Comment"] = out[comment_col].astype(str).str.strip() if comment_col else ""
    cols = ["Year", "QuarterNum", "Quarter", "US_Unemployment_Rate", "Labor_Force_Participation", "Real_Wages_YoY", "Comment"]
    out = out[cols].dropna(subset=["US_Unemployment_Rate", "Labor_Force_Participation", "Real_Wages_YoY"], how="all")
    return out.sort_values(["Year", "QuarterNum"]).reset_index(drop=True)


@st.cache_data(ttl=3600)
def _load_macro_currency_index_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    raw, _sheet_used = _read_excel_sheet_flexible(
        excel_path=excel_path,
        source_stamp=source_stamp,
        preferred="Macro_Currency_Index",
        aliases=["Currency_Index", "FX", "Macro FX"],
        contains_all=["currency"],
        contains_any=["dxy", "usd", "fx", "index"],
    )
    if raw.empty:
        stocks = _load_stocks_crypto_timeseries_df(excel_path, source_stamp)
        if stocks.empty:
            return pd.DataFrame()
        mask = stocks["asset"].str.lower().str.contains("dxy|dollar index|usd index", regex=True, na=False)
        dxy = stocks[mask].copy()
        if dxy.empty:
            return pd.DataFrame()
        dxy["Year"] = dxy["date"].dt.year.astype(int)
        dxy["QuarterNum"] = dxy["date"].dt.quarter.astype(int)
        dxy = (
            dxy.sort_values(["Year", "QuarterNum", "date"])
            .groupby(["Year", "QuarterNum"], as_index=False)
            .tail(1)
        )
        dxy["Quarter"] = dxy["QuarterNum"].apply(lambda q: f"Q{int(q)}")
        dxy["USD_Index_DXY"] = dxy["price"]
        dxy["Comment"] = "Derived from Stocks & Crypto"
        return dxy[["Year", "QuarterNum", "Quarter", "USD_Index_DXY", "Comment"]].sort_values(["Year", "QuarterNum"])
    out = _attach_year_quarter(
        raw,
        year_aliases=["year"],
        quarter_aliases=["quarter", "qtr"],
        date_aliases=["date", "period"],
    )
    if out.empty:
        return pd.DataFrame()
    dxy_col = _find_column_by_alias(out, ["usd_index_dxy", "dxy", "usd_index"])
    comment_col = _find_column_by_alias(out, ["comment", "note"])
    out["USD_Index_DXY"] = pd.to_numeric(out[dxy_col], errors="coerce") if dxy_col else np.nan
    out["Comment"] = out[comment_col].astype(str).str.strip() if comment_col else ""
    cols = ["Year", "QuarterNum", "Quarter", "USD_Index_DXY", "Comment"]
    out = out[cols].dropna(subset=["USD_Index_DXY"], how="all")
    return out.sort_values(["Year", "QuarterNum"]).reset_index(drop=True)


@st.cache_data(ttl=3600)
def _load_macro_tech_valuations_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    raw, _sheet_used = _read_excel_sheet_flexible(
        excel_path=excel_path,
        source_stamp=source_stamp,
        preferred="Macro_Tech_Valuations",
        aliases=["Tech_Valuations", "Valuations", "Macro Tech Valuations"],
        contains_any=["vix", "pe", "valuation", "nasdaq"],
    )
    if raw.empty:
        stocks = _load_stocks_crypto_timeseries_df(excel_path, source_stamp)
        if stocks.empty:
            return pd.DataFrame()
        vix = stocks[stocks["asset"].str.lower().str.contains("vix", regex=False, na=False)].copy()
        if vix.empty:
            return pd.DataFrame()
        vix["Year"] = vix["date"].dt.year.astype(int)
        vix["QuarterNum"] = vix["date"].dt.quarter.astype(int)
        vix = (
            vix.sort_values(["Year", "QuarterNum", "date"])
            .groupby(["Year", "QuarterNum"], as_index=False)
            .tail(1)
        )
        vix["Quarter"] = vix["QuarterNum"].apply(lambda q: f"Q{int(q)}")
        vix["Tech_Aggregate_PE"] = np.nan
        vix["VIX_Volatility"] = vix["price"]
        vix["Comment"] = "Derived from Stocks & Crypto"
        return vix[["Year", "QuarterNum", "Quarter", "Tech_Aggregate_PE", "VIX_Volatility", "Comment"]].sort_values(["Year", "QuarterNum"])
    out = _attach_year_quarter(
        raw,
        year_aliases=["year"],
        quarter_aliases=["quarter", "qtr"],
        date_aliases=["date", "period"],
    )
    if out.empty:
        return pd.DataFrame()
    tech_pe_col = _find_column_by_alias(out, ["tech_aggregate_pe", "big_tech_pe", "tech_pe"])
    vix_col = _find_column_by_alias(out, ["vix_volatility", "vix"])
    comment_col = _find_column_by_alias(out, ["comment", "note"])

    out["Tech_Aggregate_PE"] = pd.to_numeric(out[tech_pe_col], errors="coerce") if tech_pe_col else np.nan
    out["VIX_Volatility"] = pd.to_numeric(out[vix_col], errors="coerce") if vix_col else np.nan
    out["Comment"] = out[comment_col].astype(str).str.strip() if comment_col else ""
    cols = ["Year", "QuarterNum", "Quarter", "Tech_Aggregate_PE", "VIX_Volatility", "Comment"]
    out = out[cols].dropna(subset=["Tech_Aggregate_PE", "VIX_Volatility"], how="all")
    return out.sort_values(["Year", "QuarterNum"]).reset_index(drop=True)


@st.cache_data(ttl=3600)
def _load_company_revenue_by_region_yearly_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Company_revenue_by_region")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    required = ["company", "year", "segment_name", "revenue_millions"]
    if not set(required).issubset(set(out.columns)):
        return pd.DataFrame()
    out["company"] = out["company"].astype(str).str.strip()
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out["segment_name"] = out["segment_name"].astype(str).str.strip()
    out["revenue_millions"] = pd.to_numeric(out["revenue_millions"], errors="coerce")
    out = out.dropna(subset=["company", "year", "segment_name", "revenue_millions"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["year"] = out["year"].astype(int)
    return out.sort_values(["company", "year", "segment_name"]).reset_index(drop=True)


@st.cache_data(ttl=3600)
def _load_macro_wealth_by_generation_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    raw, _sheet_used = _read_excel_sheet_flexible(
        excel_path=excel_path,
        source_stamp=source_stamp,
        preferred="Macro_Wealth_by_Generation",
        aliases=["Wealth_by_Generation", "Macro Wealth by Generation"],
        contains_all=["wealth", "generation"],
    )
    if raw.empty:
        return pd.DataFrame()
    out = raw.copy()
    out.columns = [str(c).strip() for c in out.columns]
    country_col = _find_column_by_alias(out, ["country"])
    year_col = _find_column_by_alias(out, ["year"])
    generation_col = _find_column_by_alias(out, ["generation_label", "generation", "age_group"])
    share_col = _find_column_by_alias(out, ["wealth_share_pct", "wealth_share", "share_pct"])
    total_col = _find_column_by_alias(out, ["total_wealth_billion_usd", "total_wealth", "wealth_billion"])
    people_col = _find_column_by_alias(out, ["number_of_people_m", "people_m", "population_m", "population"])
    if not country_col or not year_col or not generation_col:
        return pd.DataFrame()
    out = out.rename(
        columns={
            country_col: "Country",
            year_col: "Year",
            generation_col: "Generation",
        }
    )
    out["Country"] = out["Country"].astype(str).str.strip()
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    out["Generation"] = out["Generation"].astype(str).str.strip()
    if share_col:
        out["WealthSharePct"] = pd.to_numeric(out[share_col], errors="coerce")
    else:
        out["WealthSharePct"] = np.nan
    if total_col:
        out["TotalWealthBUSD"] = pd.to_numeric(out[total_col], errors="coerce")
    else:
        out["TotalWealthBUSD"] = np.nan
    if people_col:
        out["PeopleM"] = pd.to_numeric(out[people_col], errors="coerce")
    else:
        out["PeopleM"] = np.nan
    out = out.dropna(subset=["Country", "Year", "Generation"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["Year"] = out["Year"].astype(int)
    return out[
        ["Country", "Year", "Generation", "WealthSharePct", "TotalWealthBUSD", "PeopleM"]
    ].sort_values(["Year", "Country", "Generation"])


@st.cache_data(ttl=3600)
def _load_hardware_smartphone_shipments_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    raw, _sheet_used = _read_excel_sheet_flexible(
        excel_path=excel_path,
        source_stamp=source_stamp,
        preferred="Hardware_Smartphone_Shipments",
        aliases=["Smartphone_Shipments", "Hardware Smartphone Shipments"],
        contains_all=["smartphone", "ship"],
    )
    if raw.empty:
        return pd.DataFrame()
    out = raw.copy()
    out.columns = [str(c).strip() for c in out.columns]
    year_col = _find_column_by_alias(out, ["year"])
    total_col = _find_column_by_alias(out, ["total_global_units_m", "total_global_units", "total_units"])
    if not year_col or not total_col:
        return pd.DataFrame()
    out = out.rename(columns={year_col: "Year", total_col: "Total_Global_Units_M"})
    # Keep all manufacturer unit columns to build market-share and comparison charts.
    unit_cols = [
        col for col in out.columns
        if col != "Total_Global_Units_M"
        and col.lower().endswith("_units_m")
        and "total_global" not in col.lower()
    ]
    apple_col = _find_column_by_alias(
        out,
        ["apple_iphone_units_m", "apple_iphone_units", "iphone_units"],
    )
    if apple_col and apple_col not in unit_cols:
        unit_cols.append(apple_col)
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    out["Total_Global_Units_M"] = pd.to_numeric(out["Total_Global_Units_M"], errors="coerce")
    for col in unit_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["Year", "Total_Global_Units_M"]).copy()
    if out.empty:
        return pd.DataFrame()
    out = out[out["Total_Global_Units_M"] > 0].copy()
    if out.empty:
        return pd.DataFrame()
    out["Year"] = out["Year"].astype(int)
    if apple_col:
        out["Apple_iPhone_Units_M"] = pd.to_numeric(out[apple_col], errors="coerce")
        out["AppleSharePct"] = np.where(
            out["Total_Global_Units_M"] > 0,
            (out["Apple_iPhone_Units_M"] / out["Total_Global_Units_M"]) * 100.0,
            np.nan,
        )
    else:
        out["Apple_iPhone_Units_M"] = np.nan
        out["AppleSharePct"] = np.nan

    keep_cols = ["Year", "Total_Global_Units_M", "Apple_iPhone_Units_M", "AppleSharePct"] + unit_cols
    keep_cols = list(dict.fromkeys([col for col in keep_cols if col in out.columns]))
    return out[keep_cols].sort_values("Year").reset_index(drop=True)


def _parse_hours_minutes(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return np.nan
    text = str(value).strip()
    if not text:
        return np.nan
    if ":" in text:
        try:
            hh, mm = text.split(":", 1)
            return float(hh) + (float(mm) / 60.0)
        except Exception:
            return np.nan
    try:
        raw = float(text)
    except Exception:
        return np.nan
    hours = int(raw)
    minutes = int(round((raw - hours) * 100))
    minutes = max(0, min(minutes, 59))
    return float(hours) + (minutes / 60.0)


@st.cache_data(ttl=3600)
def _load_country_avg_internet_time_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    raw, _sheet_used = _read_excel_sheet_flexible(
        excel_path=excel_path,
        source_stamp=source_stamp,
        preferred="Country_avg_timespent_intrnt24",
        aliases=["Country_avg_timespent_internet24", "Country Avg Time Spent Internet"],
        contains_all=["time", "internet"],
        contains_any=["country", "avg"],
    )
    if raw.empty:
        return pd.DataFrame()
    out = raw.copy()
    out.columns = [str(c).strip() for c in out.columns]
    country_col = _find_column_by_alias(out, ["country"])
    time_col = _find_column_by_alias(out, ["daily_time_spent_internet_hours_minutes", "daily_time_spent_internet", "time_spent_internet"])
    if not country_col or not time_col:
        return pd.DataFrame()
    out = out.rename(columns={country_col: "Country", time_col: "DailyInternetTimeRaw"})
    out["Country"] = out["Country"].astype(str).str.strip()
    out["DailyInternetHours"] = out["DailyInternetTimeRaw"].apply(_parse_hours_minutes)
    out = out.dropna(subset=["Country", "DailyInternetHours"]).copy()
    if out.empty:
        return pd.DataFrame()
    return out[["Country", "DailyInternetHours"]].sort_values("DailyInternetHours", ascending=False)


_COMPANY_TO_TICKER = {
    "Alphabet": "GOOGL",
    "Amazon": "AMZN",
    "Apple": "AAPL",
    "Comcast": "CMCSA",
    "Disney": "DIS",
    "Meta Platforms": "META",
    "Meta": "META",
    "Microsoft": "MSFT",
    "Netflix": "NFLX",
    "Paramount Global": "PARA",
    "Paramount": "PARA",
    "Roku": "ROKU",
    "Spotify": "SPOT",
    "Warner Bros. Discovery": "WBD",
    "Warner Bros Discovery": "WBD",
}

_TICKER_TO_COMPANY = {
    value: key for key, value in _COMPANY_TO_TICKER.items()
    if key in {
        "Alphabet",
        "Amazon",
        "Apple",
        "Comcast",
        "Disney",
        "Meta Platforms",
        "Microsoft",
        "Netflix",
        "Paramount Global",
        "Roku",
        "Spotify",
        "Warner Bros. Discovery",
    }
}

_STREAMING_SERVICE_TO_COMPANY = {
    "netflix": "Netflix",
    "disney+": "Disney",
    "hulu": "Disney",
    "espn+": "Disney",
    "max": "Warner Bros. Discovery",
    "hbo max": "Warner Bros. Discovery",
    "paramount+": "Paramount Global",
    "spotify": "Spotify",
}


@st.cache_data(ttl=3600)
def _load_company_quarterly_kpis_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Company_Quarterly_segments_valu")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    required_base = {"Ticker", "Year", "Revenue", "Net Income", "Operating Income", "Debt", "Capex", "R&D", "Cash Balance"}
    for col in required_base:
        if col not in out.columns:
            out[col] = np.nan if col != "Ticker" else ""
    out["Ticker"] = out["Ticker"].astype(str).str.strip().str.upper()
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    out = out.dropna(subset=["Ticker", "Year"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["Year"] = out["Year"].astype(int)

    for col in ["Revenue", "Net Income", "Operating Income", "Debt", "Capex", "R&D", "Cash Balance"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.sort_index().copy()
    out["QuarterNum"] = out.groupby(["Ticker", "Year"]).cumcount() + 1
    out = out[out["QuarterNum"].between(1, 4)].copy()
    out["Quarter"] = "Q" + out["QuarterNum"].astype(int).astype(str)
    out["Company"] = out["Ticker"].map(_TICKER_TO_COMPANY).fillna(out["Ticker"])
    return out.sort_values(["Company", "Year", "QuarterNum"]).reset_index(drop=True)


@st.cache_data(ttl=3600)
def _load_company_minute_dollar_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Company_minute&dollar_earned")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    platform_col = _find_column_by_alias(out, ["platform", "service", "company"])
    minutes_col = _find_column_by_alias(out, ["total_minutes_watched_t", "total_minutes_watched", "minutes"])
    rev_col = _find_column_by_alias(out, ["revenue_b", "revenue", "revenue_usd_b", "revenue_$b"])
    rate_col = _find_column_by_alias(out, ["$_per_minute_watched", "dollar_per_minute_watched", "revenue_per_minute"])
    if not platform_col:
        return pd.DataFrame()
    out = out.rename(columns={platform_col: "Platform"})
    out["Platform"] = out["Platform"].astype(str).str.strip()
    out["TotalMinutesT"] = pd.to_numeric(out[minutes_col], errors="coerce") if minutes_col else np.nan
    out["RevenueB"] = pd.to_numeric(out[rev_col], errors="coerce") if rev_col else np.nan
    out["DollarPerMinute"] = pd.to_numeric(out[rate_col], errors="coerce") if rate_col else np.nan
    out = out[out["Platform"] != ""].copy()
    if out.empty:
        return pd.DataFrame()
    return out[["Platform", "TotalMinutesT", "RevenueB", "DollarPerMinute"]].sort_values("Platform")


@st.cache_data(ttl=3600)
def _load_company_subscribers_quarterly_df(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name="Company_subscribers_values")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    required = {"service", "year", "quarter", "subscribers"}
    if not required.issubset(set(out.columns)):
        return pd.DataFrame()
    out["service"] = out["service"].astype(str).str.strip()
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out["subscribers"] = pd.to_numeric(out["subscribers"], errors="coerce")
    out["quarter_num"] = out["quarter"].apply(_parse_quarter_number)
    out = out.dropna(subset=["service", "year", "quarter_num", "subscribers"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["year"] = out["year"].astype(int)
    out["quarter_num"] = out["quarter_num"].astype(int)
    out["company"] = out["service"].str.lower().map(_STREAMING_SERVICE_TO_COMPANY)
    out = out.dropna(subset=["company"]).copy()
    if out.empty:
        return pd.DataFrame()
    return out.sort_values(["company", "year", "quarter_num", "service"]).reset_index(drop=True)


def _is_international_region_label(name: str) -> bool:
    text = str(name or "").strip().lower()
    return any(
        token in text
        for token in (
            "international",
            "outside",
            "emea",
            "apac",
            "asia",
            "europe",
            "latam",
            "latin",
            "rest of world",
            "worldwide",
        )
    )


def _latest_subscriber_history(subscriber_df: pd.DataFrame, services: list[str]) -> pd.DataFrame:
    if subscriber_df is None or subscriber_df.empty:
        return pd.DataFrame()
    if not services:
        return pd.DataFrame()

    df = subscriber_df.copy()
    if "year" not in df.columns or "quarter" not in df.columns or "subscribers" not in df.columns:
        return pd.DataFrame()
    df = df[df["service"].isin(services)].copy()
    if df.empty:
        return pd.DataFrame()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["subscribers"] = pd.to_numeric(df["subscribers"], errors="coerce")
    df["_q"] = df["quarter"].apply(_parse_quarter_number).fillna(0).astype(int)
    df = df.dropna(subset=["year", "subscribers"])
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["year"].astype(int)
    latest = (
        df.sort_values(["service", "year", "_q", "subscribers"])
        .groupby(["service", "year"], as_index=False)
        .tail(1)
        .copy()
    )
    latest = latest.sort_values(["year", "service"])
    return latest


_OVERVIEW_MACRO_COLUMN_ALIASES = {
    "year": ["year"],
    "quarter": ["quarter", "qtr"],
    "m2_value": ["m2_value", "m2", "m2_usd_b"],
    "global_ad_market": ["global_ad_market", "global_ad_market_size", "total_ad_market"],
    "duopoly_share": ["duopoly_share", "duopoly_share_pct", "google_meta_share"],
    "tv_ad_spend": ["tv_ad_spend", "tv_spend"],
    "internet_ad_spend": ["internet_ad_spend", "internet_spend"],
    "retail_media": ["retail_media", "retail_media_spend"],
    "macro_comment": ["macro_comment", "comment", "macro_overview"],
}

_OVERVIEW_INSIGHTS_COLUMN_ALIASES = {
    "insight_id": ["insight_id", "id", "insight_code"],
    "sort_order": ["sort_order", "order", "rank"],
    "category": ["category", "cat", "section"],
    "title": ["title", "insight_title"],
    "year": ["year"],
    "quarter": ["quarter", "qtr"],
    "frequency": ["frequency", "granularity", "period_type"],
    "comment": ["comment", "overview_comment", "insight", "body", "text"],
    "chart_key": ["chart_key", "chart", "chart_id"],
    "is_active": ["is_active", "active", "enabled"],
}

_OVERVIEW_AUTO_INSIGHTS_COLUMN_ALIASES = {
    "insight_id": ["insight_id", "id", "insight_code"],
    "sort_order": ["sort_order", "order", "rank"],
    "category": ["category", "cat", "section"],
    "title": ["title", "insight_title"],
    "year": ["year"],
    "quarter": ["quarter", "qtr"],
    "frequency": ["frequency", "granularity", "period_type"],
    "comment": ["comment", "overview_comment", "insight", "body", "text"],
    "text": ["text", "comment", "insight", "body"],
    "priority": ["priority", "importance"],
    "companies": ["companies", "company_list", "company"],
    "kpis": ["kpis", "metrics", "kpi_list"],
    "graph_type": ["graph_type", "chart_type", "graph", "chart_key"],
    "is_active": ["is_active", "active", "enabled"],
}

_OVERVIEW_CHARTS_COLUMN_ALIASES = {
    "chart_key": ["chart_key", "chart", "chart_id"],
    "year": ["year"],
    "quarter": ["quarter", "qtr"],
    "frequency": ["frequency", "granularity", "period_type"],
    "title": ["title", "section_title", "chart_title"],
    "pre_comment": ["pre_comment", "comment_before", "comment_above", "overview_comment"],
    "post_comment": ["post_comment", "comment_after", "comment_below", "chart_comment"],
}

_OVERVIEW_INSIGHT_CATEGORY_ORDER = [
    "Advertising",
    "Efficiency",
    "Macro",
    "Attention",
    "Streaming",
    "Business Model",
    "Demographics",
]


def _normalize_overview_colname(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", str(name or "").strip().lower().replace(" ", "_"))


def _normalize_overview_period(year_value, quarter_value, period_value=None) -> str:
    period_str = str(period_value or "").strip().upper()
    if period_str:
        m = re.search(r"(\d{4}).*Q([1-4])", period_str)
        if m:
            return f"{m.group(1)}-Q{m.group(2)}"
        y = re.search(r"(\d{4})", period_str)
        if y:
            return y.group(1)
        return period_str
    year_num = pd.to_numeric(year_value, errors="coerce")
    year_int = int(year_num) if pd.notna(year_num) else None
    quarter_num = _parse_quarter_number(quarter_value)
    if year_int and quarter_num:
        return f"{year_int}-Q{quarter_num}"
    if year_int:
        return str(year_int)
    return ""


def _period_sort_key(period_label: str) -> tuple[int, str]:
    p = str(period_label or "").strip().upper()
    m = re.search(r"(\d{4})-?Q([1-4])", p)
    if m:
        return int(m.group(1)) * 10 + int(m.group(2)), p
    y = re.search(r"(\d{4})", p)
    if y:
        return int(y.group(1)) * 10, p
    return -1, p


def _parse_is_active_flag(value) -> bool:
    s = str(value if value is not None else "").strip().lower()
    if not s:
        return True
    return s not in {"0", "false", "no", "n", "off"}


def _row_period_rank(year_value, quarter_value, period_value=None) -> int:
    period = _normalize_overview_period(year_value, quarter_value, period_value)
    return _period_sort_key(period)[0]


def _pick_rows_for_period(df: pd.DataFrame, selected_year: int | None, selected_quarter: str | None) -> tuple[pd.DataFrame, str]:
    if df is None or df.empty:
        return pd.DataFrame(), "No data"

    scoped = df.copy()
    scoped["_year_int"] = pd.to_numeric(scoped.get("year"), errors="coerce")
    scoped["_quarter_norm"] = scoped.get("quarter", pd.Series(dtype=str)).apply(_normalize_quarter_label)
    scoped["_quarter_num"] = scoped["_quarter_norm"].apply(_parse_quarter_number).fillna(0).astype(int)
    scoped["_frequency_norm"] = scoped.get("frequency", pd.Series(dtype=str)).astype(str).str.strip().str.lower()
    quarter_norm = _normalize_quarter_label(selected_quarter)
    quarter_num = _parse_quarter_number(quarter_norm) or 0

    if selected_year is not None:
        year_exact = scoped[scoped["_year_int"] == int(selected_year)].copy()
        if quarter_norm:
            exact = year_exact[year_exact["_quarter_norm"] == quarter_norm].copy()
            if not exact.empty:
                return exact, f"{int(selected_year)}-{quarter_norm}"

            # Year-level fallback for rows that leave quarter blank/NaN.
            year_no_quarter = year_exact[year_exact["_quarter_norm"] == ""].copy()
            if not year_no_quarter.empty:
                return year_no_quarter, f"{int(selected_year)} (annual)"

            # Keep frequency-based annual fallback for compatibility.
            year_fallback = year_exact[
                year_exact["_frequency_norm"].isin({"yearly", "annual", "year"})
            ].copy()
            if not year_fallback.empty:
                return year_fallback, f"{int(selected_year)} (annual)"

            # Quarter fallback: use the latest available quarter in the selected year up to selected quarter.
            quarter_le = year_exact[
                (year_exact["_quarter_num"] > 0) & (year_exact["_quarter_num"] <= int(quarter_num))
            ].copy()
            if not quarter_le.empty:
                best_q = int(quarter_le["_quarter_num"].max())
                return quarter_le[quarter_le["_quarter_num"] == best_q].copy(), f"{int(selected_year)}-Q{best_q} (fallback)"

            # Final fallback for the year: latest quarter available.
            any_quarter = year_exact[year_exact["_quarter_num"] > 0].copy()
            if not any_quarter.empty:
                best_q = int(any_quarter["_quarter_num"].max())
                return any_quarter[any_quarter["_quarter_num"] == best_q].copy(), f"{int(selected_year)}-Q{best_q} (latest)"
        else:
            if not year_exact.empty:
                yearly = year_exact[
                    (year_exact["_quarter_norm"] == "")
                    | (year_exact["_frequency_norm"].isin({"yearly", "annual", "year"}))
                ].copy()
                if not yearly.empty:
                    return yearly, str(int(selected_year))
                return year_exact, str(int(selected_year))

    if quarter_norm:
        quarter_only = scoped[(scoped["_year_int"].isna()) & (scoped["_quarter_norm"] == quarter_norm)].copy()
        if not quarter_only.empty:
            return quarter_only, quarter_norm

    defaults = scoped[(scoped["_year_int"].isna()) & (scoped["_quarter_norm"] == "")].copy()
    if not defaults.empty:
        return defaults, "Default"

    scoped["_period_rank"] = scoped.apply(
        lambda row: _row_period_rank(row.get("year"), row.get("quarter"), row.get("period")),
        axis=1,
    )
    top_rank = scoped["_period_rank"].max()
    latest = scoped[scoped["_period_rank"] == top_rank].copy()
    if latest.empty:
        return pd.DataFrame(), "No data"
    first = latest.iloc[0]
    latest_label = _normalize_overview_period(first.get("year"), first.get("quarter"), first.get("period")) or "Latest"
    return latest, latest_label


def _read_excel_overview_sheet(excel_path: str, sheet_name: str, source_stamp: int = 0) -> pd.DataFrame:
    try:
        raw = pd.read_excel(excel_path, sheet_name=sheet_name)
    except Exception:
        return pd.DataFrame()
    if raw is None or raw.empty:
        return pd.DataFrame()
    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    return raw


@st.cache_data(ttl=3600)
def _list_workbook_sheet_names(excel_path: str, source_stamp: int = 0) -> list[str]:
    if not excel_path:
        return []
    path = Path(excel_path)
    if not path.exists():
        return []
    try:
        xl = pd.ExcelFile(path)
    except Exception:
        return []
    return [str(s).strip() for s in xl.sheet_names]


def _find_sheet_name(
    excel_path: str,
    source_stamp: int = 0,
    preferred: str | None = None,
    aliases: list[str] | None = None,
    contains_all: list[str] | None = None,
    contains_any: list[str] | None = None,
) -> str:
    sheet_names = _list_workbook_sheet_names(excel_path, source_stamp)
    if not sheet_names:
        return ""

    if preferred:
        preferred_str = str(preferred).strip()
        if preferred_str in sheet_names:
            return preferred_str

    normalized_map = {_norm_sheet_col(s): s for s in sheet_names}
    for alias in aliases or []:
        alias_norm = _norm_sheet_col(alias)
        if alias_norm in normalized_map:
            return normalized_map[alias_norm]

    all_tokens = [_norm_sheet_col(t) for t in (contains_all or []) if str(t).strip()]
    any_tokens = [_norm_sheet_col(t) for t in (contains_any or []) if str(t).strip()]
    if not all_tokens and not any_tokens:
        return ""

    candidates: list[tuple[int, int, str]] = []
    for sheet in sheet_names:
        norm = _norm_sheet_col(sheet)
        if all_tokens and not all(tok in norm for tok in all_tokens):
            continue
        if any_tokens and not any(tok in norm for tok in any_tokens):
            continue
        score = 0
        score += sum(tok in norm for tok in all_tokens) * 3
        score += sum(tok in norm for tok in any_tokens)
        candidates.append((score, -len(norm), sheet))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][2]


def _read_excel_sheet_flexible(
    excel_path: str,
    source_stamp: int = 0,
    preferred: str | None = None,
    aliases: list[str] | None = None,
    contains_all: list[str] | None = None,
    contains_any: list[str] | None = None,
) -> tuple[pd.DataFrame, str]:
    sheet_name = _find_sheet_name(
        excel_path=excel_path,
        source_stamp=source_stamp,
        preferred=preferred,
        aliases=aliases,
        contains_all=contains_all,
        contains_any=contains_any,
    )
    if not sheet_name:
        return pd.DataFrame(), ""
    return _read_excel_overview_sheet(excel_path, sheet_name, source_stamp), sheet_name


def _rename_overview_columns(raw: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    normalized_lookup = {_normalize_overview_colname(c): c for c in raw.columns}
    rename_map = {}
    for canonical, names in aliases.items():
        for alias in names:
            key = _normalize_overview_colname(alias)
            if key in normalized_lookup:
                rename_map[normalized_lookup[key]] = canonical
                break
    return raw.rename(columns=rename_map).copy()


@st.cache_data(show_spinner=False)
def _load_overview_macro_sheet(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    raw = _read_excel_overview_sheet(excel_path, "Overview_Macro", source_stamp)
    if raw.empty:
        return pd.DataFrame()
    df = _rename_overview_columns(raw, _OVERVIEW_MACRO_COLUMN_ALIASES)

    required = ["year", "quarter", "m2_value", "global_ad_market", "duopoly_share", "tv_ad_spend", "internet_ad_spend", "retail_media", "macro_comment"]
    for col in required:
        if col not in df.columns:
            df[col] = np.nan if col not in {"quarter", "macro_comment"} else ""

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"]).copy()
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["year"].astype(int)
    df["quarter"] = df["quarter"].apply(_normalize_quarter_label).replace("", "Q4")
    for col in ["m2_value", "global_ad_market", "duopoly_share", "tv_ad_spend", "internet_ad_spend", "retail_media"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["macro_comment"] = df["macro_comment"].apply(_clean_overview_text)
    return df


@st.cache_data(show_spinner=False)
def _load_overview_insights_sheet(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    raw = _read_excel_overview_sheet(excel_path, "Overview_Insights", source_stamp)
    if raw.empty:
        return pd.DataFrame()
    df = _rename_overview_columns(raw, _OVERVIEW_INSIGHTS_COLUMN_ALIASES)

    required = ["insight_id", "sort_order", "category", "title", "year", "quarter", "frequency", "comment", "chart_key", "is_active"]
    for col in required:
        if col not in df.columns:
            df[col] = ""

    df["insight_id"] = df["insight_id"].astype(str).str.strip()
    df["sort_order"] = pd.to_numeric(df["sort_order"], errors="coerce")
    missing_sort = df["sort_order"].isna()
    if missing_sort.any():
        df.loc[missing_sort, "sort_order"] = pd.to_numeric(
            df.loc[missing_sort, "insight_id"].str.extract(r"(\d+)", expand=False),
            errors="coerce",
        )
    df["sort_order"] = df["sort_order"].fillna(9_999).astype(int)
    df["category"] = df["category"].apply(_clean_overview_text).replace("", "General")
    df["title"] = df["title"].apply(_clean_overview_text)
    df["comment"] = df["comment"].apply(_clean_overview_text)
    df["chart_key"] = df["chart_key"].apply(_clean_overview_text)
    df["frequency"] = df["frequency"].astype(str).str.strip().str.lower()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["quarter"] = df["quarter"].apply(_normalize_quarter_label)
    df = df[df["is_active"].apply(_parse_is_active_flag)].copy()
    df = df.dropna(subset=["year"]).copy()
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["year"].astype(int)
    df = df[(df["title"] != "") & (df["comment"] != "")].copy()
    return df.sort_values(["year", "quarter", "sort_order", "insight_id"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def _load_overview_charts_sheet(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    raw = _read_excel_overview_sheet(excel_path, "Overview_Charts", source_stamp)
    if raw.empty:
        return pd.DataFrame()
    df = _rename_overview_columns(raw, _OVERVIEW_CHARTS_COLUMN_ALIASES)

    required = ["chart_key", "year", "quarter", "frequency", "title", "pre_comment", "post_comment"]
    for col in required:
        if col not in df.columns:
            df[col] = ""

    df["chart_key"] = df["chart_key"].apply(_clean_overview_text)
    df["title"] = df["title"].apply(_clean_overview_text)
    df["pre_comment"] = df["pre_comment"].apply(_clean_overview_text)
    df["post_comment"] = df["post_comment"].apply(_clean_overview_text)
    df["frequency"] = df["frequency"].astype(str).str.strip().str.lower()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"]).copy()
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["year"].astype(int)
    df["quarter"] = df["quarter"].apply(_normalize_quarter_label)
    df["_quarter_num"] = df["quarter"].apply(_parse_quarter_number).fillna(0).astype(int)
    df["_title_norm"] = df["title"].apply(_normalize_overview_colname)
    df["_chart_key_norm"] = df["chart_key"].apply(_normalize_overview_colname)
    return df


def _format_macro_metric(value, suffix: str = "") -> str:
    try:
        if value is None or pd.isna(value):
            return "N/A"
        number = float(value)
        if suffix == "%":
            return f"{number:,.1f}%"
        if suffix == "B":
            return f"${number:,.1f}B"
        return f"{number:,.1f}"
    except Exception:
        return "N/A"


def _format_compact_metric(value, suffix: str = "", decimals: int = 1) -> str:
    try:
        if value is None or pd.isna(value):
            return "N/A"
        number = float(value)
        if suffix:
            return f"{number:,.{decimals}f}{suffix}"
        return f"{number:,.{decimals}f}"
    except Exception:
        return "N/A"


def _compute_duopoly_share_series(
    data_processor: FinancialDataProcessor,
    excel_path: str,
    source_stamp: int = 0,
) -> pd.DataFrame:
    try:
        if getattr(data_processor, "df_ad_revenue", None) is None or data_processor.df_ad_revenue.empty:
            data_processor._load_ad_revenue()
    except Exception:
        pass
    ad_df = getattr(data_processor, "df_ad_revenue", None)
    if ad_df is None or ad_df.empty:
        return pd.DataFrame()

    ad = ad_df.copy()
    ad.columns = [str(c).strip() for c in ad.columns]
    if "year" in ad.columns and "Year" not in ad.columns:
        ad = ad.rename(columns={"year": "Year"})
    required_cols = {"Year", "Google_Ads", "Meta_Ads"}
    if not required_cols.issubset(ad.columns):
        return pd.DataFrame()

    ad["Year"] = _coerce_numeric(ad["Year"])
    ad["Google_Ads"] = _coerce_numeric(ad["Google_Ads"])
    ad["Meta_Ads"] = _coerce_numeric(ad["Meta_Ads"])
    ad = ad.dropna(subset=["Year", "Google_Ads", "Meta_Ads"]).copy()
    if ad.empty:
        return pd.DataFrame()
    ad["Year"] = ad["Year"].astype(int)

    groupm = _load_groupm_granular_df(excel_path, source_stamp)
    if groupm.empty:
        return pd.DataFrame()
    totals = groupm[["Year", "Total Advertising"]].copy()
    totals["Year"] = _coerce_numeric(totals["Year"]).astype("Int64")
    totals["Global_Ad_B"] = _coerce_numeric(totals["Total Advertising"]) / 1000.0
    totals = totals.dropna(subset=["Year", "Global_Ad_B"])
    if totals.empty:
        return pd.DataFrame()
    totals["Year"] = totals["Year"].astype(int)

    merged = ad.merge(totals[["Year", "Global_Ad_B"]], on="Year", how="inner")
    merged = merged[merged["Global_Ad_B"] > 0].copy()
    if merged.empty:
        return pd.DataFrame()
    merged["Duopoly_Share_Pct"] = ((merged["Google_Ads"] + merged["Meta_Ads"]) / merged["Global_Ad_B"]) * 100.0
    return merged[["Year", "Duopoly_Share_Pct"]].sort_values("Year").reset_index(drop=True)


def _compute_duopoly_triopoly_share_series(
    data_processor: FinancialDataProcessor,
    excel_path: str,
    source_stamp: int = 0,
) -> pd.DataFrame:
    try:
        if getattr(data_processor, "df_ad_revenue", None) is None or data_processor.df_ad_revenue.empty:
            data_processor._load_ad_revenue()
    except Exception:
        pass
    ad_df = getattr(data_processor, "df_ad_revenue", None)
    if ad_df is None or ad_df.empty:
        return pd.DataFrame()

    ad = ad_df.copy()
    ad.columns = [str(c).strip() for c in ad.columns]
    if "year" in ad.columns and "Year" not in ad.columns:
        ad = ad.rename(columns={"year": "Year"})
    required_cols = {"Year", "Google_Ads", "Meta_Ads", "Amazon_Ads"}
    if not required_cols.issubset(ad.columns):
        return pd.DataFrame()

    for col in ["Year", "Google_Ads", "Meta_Ads", "Amazon_Ads"]:
        ad[col] = _coerce_numeric(ad[col])
    ad = ad.dropna(subset=["Year", "Google_Ads", "Meta_Ads", "Amazon_Ads"]).copy()
    if ad.empty:
        return pd.DataFrame()
    ad["Year"] = ad["Year"].astype(int)

    groupm = _load_groupm_granular_df(excel_path, source_stamp)
    if groupm.empty:
        return pd.DataFrame()
    totals = groupm[["Year", "Total Advertising"]].copy()
    totals["Year"] = _coerce_numeric(totals["Year"]).astype("Int64")
    totals["Global_Ad_B"] = _coerce_numeric(totals["Total Advertising"]) / 1000.0
    totals = totals.dropna(subset=["Year", "Global_Ad_B"])
    if totals.empty:
        return pd.DataFrame()
    totals["Year"] = totals["Year"].astype(int)

    merged = ad.merge(totals[["Year", "Global_Ad_B"]], on="Year", how="inner")
    merged = merged[merged["Global_Ad_B"] > 0].copy()
    if merged.empty:
        return pd.DataFrame()
    merged["Duopoly_Share_Pct"] = ((merged["Google_Ads"] + merged["Meta_Ads"]) / merged["Global_Ad_B"]) * 100.0
    merged["Triopoly_Share_Pct"] = (
        (merged["Google_Ads"] + merged["Meta_Ads"] + merged["Amazon_Ads"]) / merged["Global_Ad_B"]
    ) * 100.0
    return merged[["Year", "Google_Ads", "Meta_Ads", "Amazon_Ads", "Duopoly_Share_Pct", "Triopoly_Share_Pct"]].sort_values("Year").reset_index(drop=True)


def render_macro_kpi_panel(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
    plotly_config: dict,
) -> bool:
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    if not excel_path:
        return False

    m2_quarterly = _load_m2_quarterly(excel_path, source_stamp)
    groupm_channels = _load_groupm_channels_df(excel_path, source_stamp)
    duopoly_series = _compute_duopoly_share_series(data_processor, excel_path, source_stamp)
    inflation_df = _load_inflation_yearly_df(excel_path, source_stamp)
    rates_df = _load_macro_interest_rates_df(excel_path, source_stamp)
    currency_df = _load_macro_currency_index_df(excel_path, source_stamp)
    labor_df = _load_macro_labor_market_df(excel_path, source_stamp)
    metrics_df = getattr(data_processor, "df_metrics", None)

    if (
        m2_quarterly.empty
        and groupm_channels.empty
        and duopoly_series.empty
        and rates_df.empty
        and inflation_df.empty
        and (metrics_df is None or metrics_df.empty)
    ):
        return False

    rate_row = _pick_macro_row_for_period(rates_df, int(selected_year), selected_quarter) if not rates_df.empty else None
    currency_row = (
        _pick_macro_row_for_period(currency_df, int(selected_year), selected_quarter)
        if not currency_df.empty
        else None
    )
    labor_row = _pick_macro_row_for_period(labor_df, int(selected_year), selected_quarter) if not labor_df.empty else None

    qnum = _parse_quarter_number(selected_quarter) or 4
    m2_current_value = np.nan
    m2_yoy = np.nan
    m2_tail = pd.DataFrame()
    if not m2_quarterly.empty:
        m2_scope = m2_quarterly[
            (m2_quarterly["year"] < int(selected_year))
            | ((m2_quarterly["year"] == int(selected_year)) & (m2_quarterly["quarter"] <= int(qnum)))
        ].copy()
        if m2_scope.empty:
            m2_scope = m2_quarterly.copy()
        if not m2_scope.empty:
            m2_scope = m2_scope.sort_values(["year", "quarter"])
            m2_current = m2_scope.iloc[-1]
            m2_current_value = float(m2_current["m2_usd_bn"])
            prev = m2_quarterly[
                (m2_quarterly["year"] == int(m2_current["year"]) - 1)
                & (m2_quarterly["quarter"] == int(m2_current["quarter"]))
            ]
            if not prev.empty and float(prev.iloc[0]["m2_usd_bn"]) != 0:
                m2_yoy = (
                    (float(m2_current["m2_usd_bn"]) - float(prev.iloc[0]["m2_usd_bn"]))
                    / float(prev.iloc[0]["m2_usd_bn"])
                ) * 100.0
            m2_tail = m2_scope.tail(8).copy()
            m2_tail["period"] = m2_tail["year"].astype(str) + " Q" + m2_tail["quarter"].astype(str)

    groupm_current = groupm_channels[groupm_channels["Year"] == int(selected_year)].copy()
    if groupm_current.empty and not groupm_channels.empty:
        prior = groupm_channels[groupm_channels["Year"] <= int(selected_year)]
        groupm_current = groupm_channels[groupm_channels["Year"] == int(prior["Year"].max())] if not prior.empty else groupm_channels.tail(1)

    internet_share = np.nan
    retail_yoy = np.nan
    internet_share_delta = np.nan
    if not groupm_current.empty:
        row = groupm_current.iloc[0]
        channels = [
            "Traditional_TV",
            "Connected_TV",
            "Search",
            "NonSearch",
            "Retail_Media",
            "Traditional_OOH",
            "Digital_OOH",
        ]
        total = float(sum([float(row.get(c) or 0.0) for c in channels]))
        if total > 0:
            internet_value = float(row.get("Search", 0.0) or 0.0) + float(row.get("NonSearch", 0.0) or 0.0)
            internet_share = (internet_value / total) * 100.0

        current_year = int(row["Year"])
        prev_row = groupm_channels[groupm_channels["Year"] == current_year - 1]
        if not prev_row.empty:
            prev_retail = float(prev_row.iloc[0].get("Retail_Media") or 0.0)
            cur_retail = float(row.get("Retail_Media") or 0.0)
            if prev_retail > 0:
                retail_yoy = ((cur_retail - prev_retail) / prev_retail) * 100.0
            prev_total = float(sum([float(prev_row.iloc[0].get(c) or 0.0) for c in channels]))
            if prev_total > 0 and pd.notna(internet_share):
                prev_internet_value = float(prev_row.iloc[0].get("Search", 0.0) or 0.0) + float(prev_row.iloc[0].get("NonSearch", 0.0) or 0.0)
                prev_internet_share = (prev_internet_value / prev_total) * 100.0
                internet_share_delta = internet_share - prev_internet_share

    duopoly_value = np.nan
    duopoly_delta = np.nan
    if not duopoly_series.empty:
        d_scope = duopoly_series[duopoly_series["Year"] <= int(selected_year)]
        if d_scope.empty:
            d_scope = duopoly_series.copy()
        d_scope = d_scope.sort_values("Year")
        if not d_scope.empty:
            duopoly_value = float(d_scope.iloc[-1]["Duopoly_Share_Pct"])
            if len(d_scope) > 1:
                duopoly_delta = duopoly_value - float(d_scope.iloc[-2]["Duopoly_Share_Pct"])

    ratio_value = np.nan
    ratio_delta = np.nan
    if metrics_df is not None and not metrics_df.empty and not m2_quarterly.empty:
        mcap = metrics_df.copy()
        mcap["year"] = pd.to_numeric(mcap.get("year"), errors="coerce")
        mcap["market_cap"] = pd.to_numeric(mcap.get("market_cap"), errors="coerce")
        mcap = mcap.dropna(subset=["year", "market_cap"]).copy()
        if not mcap.empty:
            mcap["year"] = mcap["year"].astype(int)
            mcap_year = (
                mcap.groupby("year", as_index=False)["market_cap"]
                .sum(min_count=1)
                .rename(columns={"market_cap": "market_cap_million"})
            )
            mcap_year["market_cap_billion"] = mcap_year["market_cap_million"] / 1000.0

            m2_year = (
                m2_quarterly.sort_values(["year", "quarter"])
                .groupby("year", as_index=False)
                .tail(1)
                .rename(columns={"year": "Year", "m2_usd_bn": "M2_B"})
            )
            merged = mcap_year.merge(m2_year, left_on="year", right_on="Year", how="inner")
            merged = merged[(merged["M2_B"] > 0)].sort_values("year")
            if not merged.empty:
                merged["ratio"] = merged["market_cap_billion"] / merged["M2_B"]
                r_scope = merged[merged["year"] <= int(selected_year)]
                if r_scope.empty:
                    r_scope = merged.copy()
                if not r_scope.empty:
                    ratio_value = float(r_scope.iloc[-1]["ratio"])
                    if len(r_scope) > 1:
                        ratio_delta = ratio_value - float(r_scope.iloc[-2]["ratio"])

    inflation_trend = np.nan
    if inflation_df is not None and not inflation_df.empty:
        infl_scope = inflation_df[inflation_df["Year"] <= int(selected_year)].sort_values("Year")
        if infl_scope.empty:
            infl_scope = inflation_df.sort_values("Year")
        if len(infl_scope) >= 2:
            inflation_trend = float(infl_scope.iloc[-1]["Inflation_YoY"]) - float(infl_scope.iloc[-2]["Inflation_YoY"])

    liquidity_score = 0
    if pd.notna(m2_yoy):
        if float(m2_yoy) > 3.0:
            liquidity_score = 1
        elif float(m2_yoy) < 0.0:
            liquidity_score = -1

    inflation_score = 0
    if pd.notna(inflation_trend):
        if float(inflation_trend) < -0.10:
            inflation_score = 1
        elif float(inflation_trend) > 0.10:
            inflation_score = -1

    digital_score = 0
    if pd.notna(internet_share_delta):
        if float(internet_share_delta) > 0.20:
            digital_score = 1
        elif float(internet_share_delta) < -0.20:
            digital_score = -1

    concentration_delta = np.nan
    concentration_high = False
    if pd.notna(duopoly_delta):
        concentration_delta = float(duopoly_delta)
    elif pd.notna(ratio_delta):
        concentration_delta = float(ratio_delta)
    if pd.notna(duopoly_value) and float(duopoly_value) >= 44.0:
        concentration_high = True
    if pd.notna(ratio_value) and float(ratio_value) >= 0.60:
        concentration_high = True

    concentration_score = 0
    if pd.notna(concentration_delta):
        if pd.notna(duopoly_delta):
            if concentration_delta > 1.0:
                concentration_score = -1
            elif concentration_delta < -1.0:
                concentration_score = 1
        else:
            if concentration_delta > 0.03:
                concentration_score = -1
            elif concentration_delta < -0.03:
                concentration_score = 1

    regime_score = liquidity_score + inflation_score + digital_score + concentration_score
    if regime_score >= 2:
        regime_icon = "🟢"
        regime_title = "Current Advertising Demand Regime: Expansion"
        regime_description = (
            "Liquidity supportive, inflation contained, advertising allocation expanding across digital and video channels."
        )
        regime_style = "background:rgba(34,197,94,0.14); border:1px solid rgba(34,197,94,0.36); color:#166534;"
    elif regime_score <= -2:
        regime_icon = "🔴"
        regime_title = "Current Advertising Demand Regime: Tightening"
        regime_description = (
            "Liquidity contracting, inflation compressing advertiser margins, performance bias accelerating allocation shifts."
        )
        regime_style = "background:rgba(239,68,68,0.14); border:1px solid rgba(239,68,68,0.35); color:#991B1B;"
    else:
        regime_icon = "🟡"
        if concentration_high:
            regime_title = "Current Advertising Demand Regime: Neutral with Competitive Pressure"
        else:
            regime_title = "Current Advertising Demand Regime: Neutral"
        regime_description = (
            "Liquidity stabilizing, inflation moderating, platform concentration reinforcing pricing competition."
        )
        regime_style = "background:rgba(245,158,11,0.14); border:1px solid rgba(245,158,11,0.35); color:#92400E;"

    st.markdown("### Macro Snapshot")
    st.markdown(
        _html_block(
            f"""
            <div style="border-radius:12px; padding:10px 12px; margin:6px 0 14px 0; {regime_style}">
              <div style="font-size:0.95rem; font-weight:800; line-height:1.35;">{regime_icon} {regime_title}</div>
              <div style="font-size:0.88rem; margin-top:4px; line-height:1.45;">{html.escape(regime_description)}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )
    groupm_row = None
    prev_groupm_row = None
    if not groupm_current.empty:
        groupm_row = groupm_current.iloc[0]
        current_groupm_year = int(groupm_row["Year"])
        prev_groupm = groupm_channels[groupm_channels["Year"] == current_groupm_year - 1]
        if not prev_groupm.empty:
            prev_groupm_row = prev_groupm.iloc[0]

    digital_total = np.nan
    tv_total = np.nan
    total_ad_market = np.nan
    ctv_revenue = np.nan
    ctv_revenue_yoy = np.nan
    digital_share = np.nan
    ad_market_yoy = np.nan
    tv_digital_label = "TV: 22% | Digital: 78%"
    groupm_year_label = 2024
    if groupm_row is not None:
        groupm_year_label = int(groupm_row.get("Year") or 2024)
        row_digital = (
            float(groupm_row.get("Search", 0.0) or 0.0)
            + float(groupm_row.get("NonSearch", 0.0) or 0.0)
            + float(groupm_row.get("Retail_Media", 0.0) or 0.0)
            + float(groupm_row.get("Connected_TV", 0.0) or 0.0)
            + float(groupm_row.get("Digital_OOH", 0.0) or 0.0)
        )
        row_ctv = float(groupm_row.get("Connected_TV", 0.0) or 0.0)
        row_tv = float(groupm_row.get("Traditional_TV", 0.0) or 0.0)
        row_total = float(groupm_row.get("Total Advertising", np.nan))
        if not np.isfinite(row_total) or row_total <= 0:
            row_total = row_digital + row_tv + float(groupm_row.get("Traditional_OOH", 0.0) or 0.0)

        if row_total > 0:
            digital_total = row_digital
            tv_total = row_tv
            total_ad_market = row_total
            ctv_revenue = row_ctv
            digital_share = (row_digital / row_total) * 100.0
            tv_share = (row_tv / row_total) * 100.0
            tv_digital_label = f"TV: {tv_share:.0f}% | Digital: {digital_share:.0f}%"

        if prev_groupm_row is not None:
            prev_total = float(prev_groupm_row.get("Total Advertising", np.nan))
            prev_ctv = float(prev_groupm_row.get("Connected_TV", 0.0) or 0.0)
            if not np.isfinite(prev_total) or prev_total <= 0:
                prev_total = (
                    float(prev_groupm_row.get("Search", 0.0) or 0.0)
                    + float(prev_groupm_row.get("NonSearch", 0.0) or 0.0)
                    + float(prev_groupm_row.get("Retail_Media", 0.0) or 0.0)
                    + float(prev_groupm_row.get("Connected_TV", 0.0) or 0.0)
                    + float(prev_groupm_row.get("Digital_OOH", 0.0) or 0.0)
                    + float(prev_groupm_row.get("Traditional_TV", 0.0) or 0.0)
                    + float(prev_groupm_row.get("Traditional_OOH", 0.0) or 0.0)
                )
            if prev_total > 0 and row_total > 0:
                ad_market_yoy = ((row_total - prev_total) / prev_total) * 100.0
            if prev_ctv > 0 and row_ctv > 0:
                ctv_revenue_yoy = ((row_ctv - prev_ctv) / prev_ctv) * 100.0

    inflation_level = np.nan
    if inflation_df is not None and not inflation_df.empty:
        infl_level_scope = inflation_df[inflation_df["Year"] <= int(selected_year)].sort_values("Year")
        if not infl_level_scope.empty:
            inflation_level = float(infl_level_scope.iloc[-1]["Inflation_YoY"])

    fed_rate = float(rate_row.get("FedFundsRate")) if rate_row is not None and pd.notna(rate_row.get("FedFundsRate")) else np.nan
    ten_year_treasury = (
        float(rate_row.get("TenYearTreasury"))
        if rate_row is not None and pd.notna(rate_row.get("TenYearTreasury"))
        else np.nan
    )
    eur_usd_value = (
        float(currency_row.get("EUR_USD"))
        if currency_row is not None and "EUR_USD" in currency_row.index and pd.notna(currency_row.get("EUR_USD"))
        else np.nan
    )
    if not np.isfinite(eur_usd_value):
        eur_usd_value = 1.08

    consumer_confidence = (
        float(labor_row.get("ConsumerConfidence"))
        if labor_row is not None and "ConsumerConfidence" in labor_row.index and pd.notna(labor_row.get("ConsumerConfidence"))
        else np.nan
    )

    macro_kpis_by_indicator = {}
    try:
        macro_kpis_df = pd.read_excel(excel_path, sheet_name="Macro_KPIs")
        macro_kpis_df.columns = [str(col).strip().lower() for col in macro_kpis_df.columns]
        if {"indicator", "value", "unit"}.issubset(macro_kpis_df.columns):
            for _, kpi_row in macro_kpis_df.iterrows():
                indicator_key = str(kpi_row.get("indicator", "")).strip().lower()
                if not indicator_key:
                    continue
                macro_kpis_by_indicator[indicator_key] = {
                    "value": pd.to_numeric(kpi_row.get("value"), errors="coerce"),
                    "unit": str(kpi_row.get("unit", "")).strip(),
                }
    except Exception:
        macro_kpis_by_indicator = {}

    def _macro_kpi_text(indicator_name: str):
        row = macro_kpis_by_indicator.get(str(indicator_name).strip().lower())
        if not row:
            return None
        value = row.get("value")
        unit = str(row.get("unit", "")).strip().lower()
        if pd.isna(value):
            return None
        value = float(value)
        if "usd billion" in unit:
            return f"${value:,.0f}B" if float(value).is_integer() else f"${value:,.1f}B"
        if unit == "%":
            return f"{value:.1f}%".replace(".0%", "%")
        if unit == "% yoy":
            return f"{value:.1f}% YoY".replace(".0% YoY", "% YoY")
        if unit == "rate":
            return f"{value:.2f}".rstrip("0").rstrip(".")
        if unit == "index":
            return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.1f}"
        return f"{value:g} {row.get('unit', '')}".strip()

    def _pill_class(value: float | int | None) -> str:
        if value is None or pd.isna(value):
            return ""
        return "positive" if float(value) >= 0 else "negative"

    def _pill(label: str, value_text: str, cls: str = "") -> str:
        return (
            f"<div class='ov-macro-pill {cls}' style='display:flex; flex-direction:column; align-items:flex-start; gap:4px; border-radius:12px;'>"
            f"<span style='font-size:0.78rem; font-weight:700; line-height:1.2;'>{html.escape(label)}</span>"
            f"<strong style='font-size:0.95rem; line-height:1.2;'>{html.escape(value_text)}</strong>"
            "</div>"
        )

    st.markdown("<div class='ov-macro-label'>MONETARY & MACRO</div>", unsafe_allow_html=True)
    fed_funds_text = _macro_kpi_text("Fed Funds Rate")
    cpi_inflation_text = _macro_kpi_text("CPI Inflation")
    ten_year_sheet_text = _macro_kpi_text("10Y Treasury Yield")
    monetary_pills = [
        _pill(
            "🌊 M2 Money Supply",
            f"${m2_current_value / 1000.0:,.1f}T" if pd.notna(m2_current_value) else "N/A",
            _pill_class(m2_yoy),
        ),
        _pill(
            "🏦 Fed Funds Rate",
            fed_funds_text or (f"{fed_rate:.2f}%" if np.isfinite(fed_rate) else "N/A"),
            _pill_class(fed_rate),
        ),
        _pill(
            "📈 10Y Treasury Yield",
            ten_year_sheet_text
            or (
                f"{ten_year_treasury:.2f}%"
                if np.isfinite(ten_year_treasury)
                else "~4.3% (Mar 2026)"
            ),
            _pill_class(ten_year_treasury if np.isfinite(ten_year_treasury) else None),
        ),
        _pill(
            "🧯 CPI Inflation",
            cpi_inflation_text or (f"{inflation_level:.1f}%" if pd.notna(inflation_level) else "N/A"),
            _pill_class(inflation_trend),
        ),
        _pill(
            "🧲 Google + Meta Share",
            f"{duopoly_value:,.1f}%" if pd.notna(duopoly_value) else "N/A",
            _pill_class(-(duopoly_delta) if pd.notna(duopoly_delta) else None),
        ),
        _pill(
            "⚖️ Big Tech / M2",
            f"{ratio_value:,.2f}x" if pd.notna(ratio_value) else "N/A",
            _pill_class(ratio_delta),
        ),
    ]
    st.markdown(
        "<div class='ov-macro-row' style='display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:10px;'>"
        + "".join(monetary_pills)
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='ov-macro-label'>ADVERTISING & MEDIA MARKET</div>", unsafe_allow_html=True)
    tv_market_value = _macro_kpi_text("Global TV Ad Market") or "~$155B (2024)"
    digital_market_value = _macro_kpi_text("Global Digital Ad Market") or "~$740B (2024)"
    ctv_value = _macro_kpi_text("CTV Ad Revenue") or "~$30B (2024, +18% YoY)"
    digital_share_value = _macro_kpi_text("Digital Share of Total Ad") or "~78% (2024)"
    consumer_confidence_value = _macro_kpi_text("Consumer Confidence Index") or "~98 (Feb 2026)"
    eurusd_value = _macro_kpi_text("EUR/USD Rate") or "~1.08 (Mar 2026)"
    ten_year_value = ten_year_sheet_text or "~4.3% (Mar 2026)"
    advertising_pills = [
        _pill("📺 Global TV Ad Market", tv_market_value, _pill_class(ad_market_yoy)),
        _pill("💻 Global Digital Ad Market", digital_market_value, _pill_class(ad_market_yoy)),
        _pill("📡 CTV Ad Revenue", ctv_value, _pill_class(ctv_revenue_yoy)),
        _pill("📊 Digital Share of Total Ad", digital_share_value, _pill_class(ad_market_yoy)),
        _pill("🎯 Consumer Confidence", consumer_confidence_value),
        _pill("💱 EUR/USD", eurusd_value),
        _pill("📈 10Y Treasury Yield", ten_year_value),
    ]
    st.markdown(
        "<div class='ov-macro-row' style='display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:10px;'>"
        + "".join(advertising_pills)
        + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='margin-top:8px; color:#64748B; font-size:0.78rem; font-style:italic;'>"
        "Source: Macro_KPIs sheet — edit directly in Excel to update values."
        "</div>",
        unsafe_allow_html=True,
    )

    trend_cols = st.columns(3)
    with trend_cols[0]:
        st.caption("M2 Trend")
        if m2_tail.empty:
            st.info("Chart data not available — pipeline not yet run.")
        else:
            m2_fig = go.Figure(
                go.Scatter(
                    x=m2_tail["period"],
                    y=m2_tail["m2_usd_bn"] / 1000.0,
                    mode="lines+markers",
                    line=dict(color="#2563EB", width=2),
                    marker=dict(size=4),
                    hovertemplate="%{x}<br>$%{y:.2f}T<extra></extra>",
                    showlegend=False,
                )
            )
            m2_fig.update_layout(
                height=180,
                margin=dict(l=8, r=8, t=8, b=8),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
            )
            st.plotly_chart(m2_fig, use_container_width=True, config=plotly_config)

    with trend_cols[1]:
        st.caption("Fed Funds Trend")
        rate_trend = rates_df[rates_df["Year"] <= int(selected_year)].sort_values(["Year", "QuarterNum"]) if not rates_df.empty else pd.DataFrame()
        rate_trend = rate_trend.dropna(subset=["FedFundsRate"]) if not rate_trend.empty else rate_trend
        if rate_trend.empty:
            st.info("Chart data not available — pipeline not yet run.")
        else:
            rate_trend = rate_trend.tail(8).copy()
            rate_trend["period"] = rate_trend["Year"].astype(str) + " " + rate_trend["Quarter"].astype(str)
            rate_fig = go.Figure(
                go.Scatter(
                    x=rate_trend["period"],
                    y=rate_trend["FedFundsRate"],
                    mode="lines+markers",
                    line=dict(color="#1D4ED8", width=2),
                    marker=dict(size=4),
                    hovertemplate="%{x}<br>%{y:.2f}%<extra></extra>",
                    showlegend=False,
                )
            )
            rate_fig.update_layout(
                height=180,
                margin=dict(l=8, r=8, t=8, b=8),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
            )
            st.plotly_chart(rate_fig, use_container_width=True, config=plotly_config)

    with trend_cols[2]:
        st.caption("Inflation Trend")
        infl_trend = inflation_df[inflation_df["Year"] <= int(selected_year)].sort_values("Year") if inflation_df is not None and not inflation_df.empty else pd.DataFrame()
        infl_trend = infl_trend.dropna(subset=["Inflation_YoY"]) if not infl_trend.empty else infl_trend
        if infl_trend.empty:
            st.info("Chart data not available — pipeline not yet run.")
        else:
            infl_trend = infl_trend.tail(8).copy()
            infl_fig = go.Figure(
                go.Scatter(
                    x=infl_trend["Year"],
                    y=infl_trend["Inflation_YoY"],
                    mode="lines+markers",
                    line=dict(color="#F97316", width=2),
                    marker=dict(size=4),
                    hovertemplate="%{x}<br>%{y:.2f}%<extra></extra>",
                    showlegend=False,
                )
            )
            infl_fig.update_layout(
                height=180,
                margin=dict(l=8, r=8, t=8, b=8),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
            )
            st.plotly_chart(infl_fig, use_container_width=True, config=plotly_config)

    return True


def _render_macro_context_dashboard(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
) -> bool:
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    if not excel_path:
        return False

    rates_df = _load_macro_interest_rates_df(excel_path, source_stamp)
    labor_df = _load_macro_labor_market_df(excel_path, source_stamp)
    currency_df = _load_macro_currency_index_df(excel_path, source_stamp)
    tech_val_df = _load_macro_tech_valuations_df(excel_path, source_stamp)
    m2_df = _load_m2_yearly_df(excel_path, source_stamp)
    inflation_df = _load_inflation_yearly_df(excel_path, source_stamp)

    rate_row = _pick_macro_row_for_period(rates_df, selected_year, selected_quarter)
    labor_row = _pick_macro_row_for_period(labor_df, selected_year, selected_quarter)
    currency_row = _pick_macro_row_for_period(currency_df, selected_year, selected_quarter)
    tech_row = _pick_macro_row_for_period(tech_val_df, selected_year, selected_quarter)

    m2_yoy = np.nan
    if m2_df is not None and not m2_df.empty:
        m2 = m2_df.copy().sort_values("Year")
        m2["M2_YoY"] = m2["M2_B"].pct_change() * 100.0
        m2_scope = m2[m2["Year"] <= int(selected_year)]
        if not m2_scope.empty:
            m2_yoy = m2_scope.iloc[-1]["M2_YoY"]

    inflation_yoy = np.nan
    if inflation_df is not None and not inflation_df.empty:
        infl_scope = inflation_df[inflation_df["Year"] <= int(selected_year)]
        if not infl_scope.empty:
            inflation_yoy = infl_scope.iloc[-1]["Inflation_YoY"]

    if all(
        row is None
        for row in [rate_row, labor_row, currency_row, tech_row]
    ) and (pd.isna(m2_yoy) and pd.isna(inflation_yoy)):
        return False

    st.markdown("### Macro Context Dashboard")
    st.caption("Auto-read from available Google Sheet tabs (flexible name matching) plus existing M2/Inflation sheets.")

    card_data = [
        ("Fed Rate", _format_compact_metric(rate_row.get("FedFundsRate") if rate_row is not None else np.nan, "%", 2)),
        ("M2 YoY", _format_compact_metric(m2_yoy, "%", 1)),
        ("Inflation", _format_compact_metric(inflation_yoy, "%", 1)),
        ("USD Index (DXY)", _format_compact_metric(currency_row.get("USD_Index_DXY") if currency_row is not None else np.nan, "", 1)),
        ("Unemployment", _format_compact_metric(labor_row.get("US_Unemployment_Rate") if labor_row is not None else np.nan, "%", 1)),
        ("VIX", _format_compact_metric(tech_row.get("VIX_Volatility") if tech_row is not None else np.nan, "", 1)),
        ("10Y-2Y Spread", _format_compact_metric(rate_row.get("YieldCurveSpread") if rate_row is not None else np.nan, "%", 2)),
        ("Tech P/E", _format_compact_metric(tech_row.get("Tech_Aggregate_PE") if tech_row is not None else np.nan, "x", 1)),
    ]
    visible_cards = [(label, value) for (label, value) in card_data if str(value).strip().upper() != "N/A"]
    if not visible_cards:
        return False

    cols_per_row = 4
    for start in range(0, len(visible_cards), cols_per_row):
        row = visible_cards[start: start + cols_per_row]
        row_cols = st.columns(len(row))
        for col, (label, value) in zip(row_cols, row):
            with col:
                st.metric(label, value)

    notes = []
    if rate_row is not None:
        regime = _clean_overview_text(rate_row.get("RateRegime"))
        rate_comment = _clean_overview_text(rate_row.get("Comment"))
        if regime:
            notes.append(f"Rate regime: {regime}")
        if rate_comment:
            notes.append(rate_comment)
    if labor_row is not None:
        labor_comment = _clean_overview_text(labor_row.get("Comment"))
        if labor_comment:
            notes.append(labor_comment)
    if notes:
        st.caption(" | ".join(notes[:3]))
    return True


def _render_overview_hero_banner() -> None:
    """Top hero with MFE image, logo blur-bar, and quick page links."""
    hero_image_path = Path("attached_assets/FAQ MFE.png")
    logos = load_company_logos()
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
    logo_html = ""
    for company in logo_order:
        img = logos.get(company)
        if not img:
            continue
        company_q = quote_plus(company)
        logo_html += (
            f"<a class='ov-hero-logo-link' href='?nav=earnings&company={company_q}' "
            f"target='_self' rel='noopener' onclick=\"window.location.assign('?nav=earnings&company={company_q}'); return false;\" "
            f"aria-label='Open earnings for {html.escape(company)}'>"
            "<span class='ov-hero-logo-wrap'>"
            f"<img class='ov-hero-logo' src='data:image/png;base64,{img}' alt='{html.escape(company)} logo'/>"
            "</span>"
            "</a>"
        )

    hero_background = "background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);"
    if hero_image_path.exists():
        hero_b64 = base64.b64encode(hero_image_path.read_bytes()).decode()
        hero_background = f"background-image:url('data:image/png;base64,{hero_b64}');"

    st.markdown(
        _html_block(
            f"""
            <style>
            .ov-hero {{
                position: relative;
                border-radius: 20px;
                overflow: hidden;
                min-height: clamp(320px, 42vh, 520px);
                margin: 0 0 26px 0;
                {hero_background}
                background-size: cover;
                background-position: top center;
                box-shadow: 0 20px 48px rgba(2, 6, 23, 0.28);
            }}
            .ov-hero::before {{
                content: '';
                position: absolute;
                inset: 0;
                background: linear-gradient(180deg, rgba(2,6,23,0.35) 0%, rgba(2,6,23,0.6) 100%);
                pointer-events: none;
            }}
            .ov-hero-copy {{
                position: relative;
                z-index: 2;
                padding: 28px 30px 98px;
                color: #F8FAFC;
            }}
            .ov-hero-title {{
                font-size: clamp(1.6rem, 2.8vw, 2.5rem);
                font-weight: 900;
                line-height: 1.1;
                margin: 0 0 10px 0;
                color: #F8FAFC;
            }}
            .ov-hero-sub {{
                font-size: 0.98rem;
                line-height: 1.55;
                max-width: 900px;
                color: rgba(248,250,252,0.92);
            }}
            .ov-hero-logo-bar {{
                position: absolute;
                left: 22px;
                right: 22px;
                bottom: 16px;
                z-index: 3;
                border-radius: 16px;
                padding: 14px 16px;
                min-height: 82px;
                display: flex;
                gap: 12px;
                align-items: center;
                overflow-x: auto;
                background: rgba(255,255,255,0.14);
                border: 1px solid rgba(255,255,255,0.30);
                backdrop-filter: blur(10px);
            }}
            .ov-hero-logo-link {{
                display: inline-flex;
                text-decoration: none !important;
                border-radius: 999px;
                transition: transform 120ms ease, filter 120ms ease;
            }}
            .ov-hero-logo-link:hover {{
                transform: translateY(-1px) scale(1.04);
                filter: drop-shadow(0 4px 10px rgba(15,23,42,0.32));
            }}
            .ov-hero-logo-wrap {{
                width: 56px;
                height: 56px;
                min-width: 56px;
                border-radius: 50%;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                background: rgba(255,255,255,0.12);
                border: 1px solid rgba(255,255,255,0.35);
            }}
            .ov-hero-logo {{
                width: 34px;
                height: 34px;
                object-fit: contain;
            }}
            </style>
            <div class='ov-hero'>
                <div class='ov-hero-copy'>
                    <div class='ov-hero-title'>Overview Intelligence Hub</div>
                    <div class='ov-hero-sub'>
                        Macro regime, concentration, and company signal layers in one control surface.
                        Use the section selector to focus one analysis block at a time.
                    </div>
                </div>
                <div class='ov-hero-logo-bar'>{logo_html}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def _add_rate_regime_bands(fig: go.Figure, rates_df: pd.DataFrame) -> None:
    if rates_df is None or rates_df.empty or "Year" not in rates_df.columns or "RateRegime" not in rates_df.columns:
        return
    regime_df = rates_df[["Year", "RateRegime"]].dropna(subset=["Year"]).copy()
    if regime_df.empty:
        return
    regime_df["Year"] = pd.to_numeric(regime_df["Year"], errors="coerce")
    regime_df["RateRegime"] = regime_df["RateRegime"].astype(str).str.strip()
    regime_df = regime_df.dropna(subset=["Year"])
    regime_df = regime_df[regime_df["RateRegime"] != ""].copy()
    if regime_df.empty:
        return
    regime_df["Year"] = regime_df["Year"].astype(int)
    yearly_regime = (
        regime_df.sort_values(["Year"])
        .groupby("Year", as_index=False)
        .tail(1)
        .sort_values("Year")
    )
    if yearly_regime.empty:
        return
    colors = {
        "zirp era": "rgba(16,185,129,0.10)",
        "rate shock": "rgba(245,158,11,0.12)",
        "normalization": "rgba(37,99,235,0.10)",
    }

    current_regime = None
    start_year = None
    prev_year = None
    for _, row in yearly_regime.iterrows():
        year = int(row["Year"])
        regime = str(row["RateRegime"]).strip()
        if current_regime is None:
            current_regime = regime
            start_year = year
            prev_year = year
            continue
        if regime == current_regime and year == (prev_year + 1):
            prev_year = year
            continue
        color = colors.get(current_regime.lower(), "rgba(148,163,184,0.08)")
        fig.add_vrect(
            x0=start_year - 0.5,
            x1=prev_year + 0.5,
            fillcolor=color,
            opacity=1.0,
            layer="below",
            line_width=0,
        )
        current_regime = regime
        start_year = year
        prev_year = year

    if current_regime is not None and start_year is not None and prev_year is not None:
        color = colors.get(current_regime.lower(), "rgba(148,163,184,0.08)")
        fig.add_vrect(
            x0=start_year - 0.5,
            x1=prev_year + 0.5,
            fillcolor=color,
            opacity=1.0,
            layer="below",
            line_width=0,
        )


def _render_macro_expansion_sections(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
    plotly_config: dict,
) -> bool:
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    if not excel_path:
        return False

    rates_df = _load_macro_interest_rates_df(excel_path, source_stamp)
    gdp_df = _load_macro_gdp_growth_df(excel_path, source_stamp)
    labor_df = _load_macro_labor_market_df(excel_path, source_stamp)
    currency_df = _load_macro_currency_index_df(excel_path, source_stamp)
    metrics_df = _load_company_metrics_yearly_df(excel_path, source_stamp)
    employees_df = _load_employee_yearly_df(excel_path, source_stamp)
    country_channel_df = _load_country_ad_channel_yearly_df(excel_path, source_stamp)
    revenue_region_df = _load_company_revenue_by_region_yearly_df(excel_path, source_stamp)
    wealth_df = _load_macro_wealth_by_generation_df(excel_path, source_stamp)
    internet_time_df = _load_country_avg_internet_time_df(excel_path, source_stamp)

    rendered_any = False
    tech_companies = {"Alphabet", "Amazon", "Apple", "Meta Platforms", "Microsoft", "Netflix", "Roku", "Spotify"}
    tech_companies_with_aliases = tech_companies | {"Meta", "Paramount", "Warner Bros Discovery", "Warner Bros. Discovery"}

    # Monetary Policy Impact
    if not rates_df.empty and metrics_df is not None and not metrics_df.empty:
        metrics = metrics_df.copy()
        metrics = metrics[metrics["Company"].isin(tech_companies_with_aliases)].copy()
        if not metrics.empty:
            capex_df = metrics.groupby("Year", as_index=False)[["Capex", "Revenue"]].sum(min_count=1)
            capex_df = capex_df[capex_df["Revenue"] > 0].copy()
            capex_df["Capex_Intensity"] = (capex_df["Capex"] / capex_df["Revenue"]) * 100.0

            rates_year = rates_df.groupby("Year", as_index=False).agg(
                FedFundsRate=("FedFundsRate", "mean"),
                RateRegime=("RateRegime", "last"),
            )
            plot_df = rates_year.merge(capex_df[["Year", "Capex_Intensity"]], on="Year", how="inner").sort_values("Year")
            if not plot_df.empty:
                st.markdown("### Monetary Policy Impact")
                title = "Interest Rates vs Big Tech Capex Intensity"
                st.markdown(f"#### {title}")
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=plot_df["Year"],
                        y=plot_df["FedFundsRate"],
                        mode="lines+markers",
                        name="Fed Funds Rate (%)",
                        line=dict(color="#DC2626", width=3),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=plot_df["Year"],
                        y=plot_df["Capex_Intensity"],
                        mode="lines+markers",
                        name="Big Tech Capex / Revenue (%)",
                        line=dict(color="#2563EB", width=3),
                        yaxis="y2",
                    )
                )
                _add_rate_regime_bands(fig, rates_df)
                fig.update_layout(
                    height=450,
                    margin=_overview_chart_margin(left=30, right=34, top=104),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(title="Fed funds rate (%)"),
                    yaxis2=dict(title="Capex intensity (%)", overlaying="y", side="right", showgrid=False),
                    legend=_overview_legend_style(),
                )
                fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
                st.plotly_chart(fig, use_container_width=True, config=plotly_config)
                rendered_any = True

    # Economic Cycle Indicators
    section_started = False
    ad_totals_df = (
        country_channel_df[["Year", "TotalAdvertising_BUSD"]]
        .dropna()
        .drop_duplicates(subset=["Year"])
        .sort_values("Year")
        if not country_channel_df.empty
        else pd.DataFrame()
    )

    if not gdp_df.empty and not ad_totals_df.empty:
        gdp_year = gdp_df.groupby("Year", as_index=False)["Global_GDP_YoY"].mean()
        ad_year = ad_totals_df.copy()
        ad_year["Ad_YoY"] = ad_year["TotalAdvertising_BUSD"].pct_change() * 100.0
        merge = gdp_year.merge(ad_year[["Year", "Ad_YoY"]], on="Year", how="inner").dropna()
        if not merge.empty:
            if not section_started:
                st.markdown("### Economic Cycle Indicators")
                section_started = True
            title = "GDP Growth vs Ad Spend Growth"
            st.markdown(f"#### {title}")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=merge["Year"], y=merge["Global_GDP_YoY"], name="Global GDP YoY %", marker_color="#94A3B8"))
            fig.add_trace(go.Bar(x=merge["Year"], y=merge["Ad_YoY"], name="Global Ad Spend YoY %", marker_color="#2563EB"))
            fig.update_layout(
                barmode="group",
                height=420,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis_title="YoY %",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            rendered_any = True

    if not labor_df.empty and employees_df is not None and not employees_df.empty:
        labor_year = labor_df.groupby("Year", as_index=False)["US_Unemployment_Rate"].mean()
        emp = employees_df.copy()
        emp = emp[emp["Company"].isin(tech_companies_with_aliases)].copy()
        if not emp.empty:
            emp_year = emp.groupby("Year", as_index=False)["Employees"].sum(min_count=1)
            emp_year["Employees_M"] = emp_year["Employees"] / 1_000_000.0
            merge = labor_year.merge(emp_year[["Year", "Employees_M"]], on="Year", how="inner").sort_values("Year")
            if not merge.empty:
                if not section_started:
                    st.markdown("### Economic Cycle Indicators")
                    section_started = True
                title = "Unemployment vs Tech Headcount"
                st.markdown(f"#### {title}")
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=merge["Year"],
                        y=merge["US_Unemployment_Rate"],
                        mode="lines+markers",
                        name="US Unemployment Rate (%)",
                        line=dict(color="#DC2626", width=3),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=merge["Year"],
                        y=merge["Employees_M"],
                        mode="lines+markers",
                        name="Big Tech Headcount (Millions)",
                        line=dict(color="#2563EB", width=3),
                        yaxis="y2",
                    )
                )
                fig.update_layout(
                    height=440,
                    margin=_overview_chart_margin(left=30, right=34, top=104),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(title="Unemployment (%)"),
                    yaxis2=dict(title="Headcount (M)", overlaying="y", side="right", showgrid=False),
                    legend=_overview_legend_style(),
                )
                fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
                st.plotly_chart(fig, use_container_width=True, config=plotly_config)
                rendered_any = True

    # Currency & International Revenue
    if not currency_df.empty and not revenue_region_df.empty:
        currency_year = currency_df.groupby("Year", as_index=False)["USD_Index_DXY"].mean()
        rev = revenue_region_df.copy()
        rev["company"] = rev["company"].astype(str).str.strip()
        rev["company_norm"] = rev["company"].replace({"Google": "Alphabet", "Meta": "Meta Platforms"})
        rev = rev[rev["company_norm"].isin(tech_companies)].copy()
        rev["is_international"] = rev["segment_name"].apply(_is_international_region_label)
        rev_group = rev.groupby(["year", "is_international"], as_index=False)["revenue_millions"].sum(min_count=1)
        intl = rev_group[rev_group["is_international"]].rename(columns={"year": "Year", "revenue_millions": "IntlRevenueM"})
        if not intl.empty:
            intl = intl.sort_values("Year")
            intl["IntlRevenue_YoY"] = intl["IntlRevenueM"].pct_change() * 100.0
            merge = currency_year.merge(intl[["Year", "IntlRevenue_YoY"]], on="Year", how="inner").dropna().sort_values("Year")
            if not merge.empty:
                st.markdown("### Currency & International Revenue")
                title = "USD Strength vs International Revenue Growth"
                st.markdown(f"#### {title}")
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=merge["Year"],
                        y=merge["USD_Index_DXY"],
                        mode="lines+markers",
                        name="USD Index (DXY)",
                        line=dict(color="#0EA5E9", width=3),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=merge["Year"],
                        y=merge["IntlRevenue_YoY"],
                        mode="lines+markers",
                        name="Big Tech Intl Revenue YoY (%)",
                        line=dict(color="#2563EB", width=3),
                        yaxis="y2",
                    )
                )
                fig.update_layout(
                    height=440,
                    margin=_overview_chart_margin(left=30, right=34, top=104),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(title="DXY"),
                    yaxis2=dict(title="International revenue YoY (%)", overlaying="y", side="right", showgrid=False),
                    legend=_overview_legend_style(),
                )
                fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
                st.plotly_chart(fig, use_container_width=True, config=plotly_config)
                rendered_any = True

    # Demographics & Attention Shift
    structural_started = False
    if not wealth_df.empty:
        year_df = wealth_df[wealth_df["Year"] == int(selected_year)].copy()
        if year_df.empty:
            year_df = wealth_df[wealth_df["Year"] <= int(selected_year)].copy()
            target_year = int(year_df["Year"].max()) if not year_df.empty else None
            if target_year is not None:
                year_df = wealth_df[wealth_df["Year"] == target_year].copy()
        else:
            target_year = int(selected_year)
        if not year_df.empty:
            if not structural_started:
                st.markdown("### Demographics & Attention Shift")
                structural_started = True
            gen_df = year_df.copy()
            gen_df["Generation"] = gen_df["Generation"].astype(str).str.strip()
            gen_df = gen_df[gen_df["Generation"] != ""].copy()

            def _canon_generation(label: str) -> str:
                low = str(label or "").strip().lower()
                if "gen z" in low:
                    return "Gen Z"
                if "millennial" in low or "gen y" in low:
                    return "Millennials"
                if "gen x" in low:
                    return "Gen X"
                if "boomer" in low:
                    return "Boomers"
                if "silent" in low:
                    return "Silent"
                if "greatest" in low:
                    return "Greatest"
                return str(label).strip()

            gen_df["Generation"] = gen_df["Generation"].apply(_canon_generation)
            if gen_df["WealthSharePct"].notna().any():
                share = (
                    gen_df.groupby(["Country", "Generation"], as_index=False)["WealthSharePct"]
                    .sum(min_count=1)
                    .dropna(subset=["WealthSharePct"])
                )
            elif gen_df["TotalWealthBUSD"].notna().any():
                wealth_raw = (
                    gen_df.groupby(["Country", "Generation"], as_index=False)["TotalWealthBUSD"]
                    .sum(min_count=1)
                    .dropna(subset=["TotalWealthBUSD"])
                )
                country_totals = wealth_raw.groupby("Country", as_index=False)["TotalWealthBUSD"].sum(min_count=1)
                share = wealth_raw.merge(country_totals, on="Country", how="left", suffixes=("", "_Country"))
                share["WealthSharePct"] = np.where(
                    share["TotalWealthBUSD_Country"] > 0,
                    (share["TotalWealthBUSD"] / share["TotalWealthBUSD_Country"]) * 100.0,
                    np.nan,
                )
                share = share[["Country", "Generation", "WealthSharePct"]].dropna(subset=["WealthSharePct"])
            else:
                share = pd.DataFrame(columns=["Country", "Generation", "WealthSharePct"])

            if not share.empty:
                preferred_generation_order = ["Gen Z", "Millennials", "Gen X", "Boomers", "Silent", "Greatest"]
                generations_present = share["Generation"].dropna().astype(str).unique().tolist()
                generation_order = [
                    *[g for g in preferred_generation_order if g in generations_present],
                    *sorted([g for g in generations_present if g not in preferred_generation_order]),
                ]

                boomer_rank = share[share["Generation"] == "Boomers"][["Country", "WealthSharePct"]].rename(
                    columns={"WealthSharePct": "BoomerShare"}
                )
                countries_rank = share.groupby("Country", as_index=False)["WealthSharePct"].sum(min_count=1)
                countries_rank = countries_rank.merge(boomer_rank, on="Country", how="left")
                countries_rank["BoomerShare"] = countries_rank["BoomerShare"].fillna(0.0)
                countries_rank = countries_rank.sort_values(["BoomerShare", "Country"], ascending=[True, True])
                country_order = countries_rank["Country"].astype(str).tolist()

                generation_colors = {
                    "Gen Z": "#22C55E",
                    "Millennials": "#0EA5E9",
                    "Gen X": "#6366F1",
                    "Boomers": "#2563EB",
                    "Silent": "#64748B",
                    "Greatest": "#334155",
                }
                color_map = {g: generation_colors.get(g, "#94A3B8") for g in generation_order}

                title = "Wealth Concentration by Generation"
                st.markdown(f"#### {title}")
                fig = px.bar(
                    share,
                    x="WealthSharePct",
                    y="Country",
                    color="Generation",
                    orientation="h",
                    color_discrete_map=color_map,
                    category_orders={"Country": country_order, "Generation": generation_order},
                    labels={"WealthSharePct": "Wealth share (%)", "Country": "", "Generation": "Generation"},
                )
                fig.update_layout(
                    barmode="stack",
                    height=max(380, min(860, 36 * len(country_order))),
                    margin=_overview_chart_margin(left=30, right=20, top=104),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis_title="Wealth share (%)",
                    yaxis_title="",
                    legend=_overview_legend_style(),
                )
                fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
                st.plotly_chart(fig, use_container_width=True, config=plotly_config)
                if target_year is not None:
                    st.caption(f"Year shown: {target_year}")
                rendered_any = True

    if not internet_time_df.empty:
        if not structural_started:
            st.markdown("### Demographics & Attention Shift")
            structural_started = True
        title = "Daily Internet Time Spent by Country on Internet"
        st.markdown(f"#### {title}")
        top = internet_time_df.copy().sort_values("DailyInternetHours", ascending=True)
        fig = px.bar(
            top,
            x="DailyInternetHours",
            y="Country",
            orientation="h",
            labels={"DailyInternetHours": "Hours per day", "Country": ""},
            color="DailyInternetHours",
            color_continuous_scale="Blues",
        )
        fig.update_layout(
            height=max(420, min(2600, 24 * len(top))),
            margin=_overview_chart_margin(left=30, right=20, top=24),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
        )
        fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
        rendered_any = True

    return rendered_any


def _render_company_financial_deep_dives(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
    plotly_config: dict,
) -> bool:
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    if not excel_path:
        return False

    metrics_df = _load_company_metrics_yearly_df(excel_path, source_stamp)
    if metrics_df.empty:
        return False

    quarterly_df = _load_company_quarterly_kpis_df(excel_path, source_stamp)
    subs_df = _load_company_subscribers_quarterly_df(excel_path, source_stamp)
    minute_df = _load_company_minute_dollar_df(excel_path, source_stamp)
    market_structure_df = _compute_duopoly_triopoly_share_series(data_processor, excel_path, source_stamp)

    year_min = int(metrics_df["Year"].min())
    year_max = int(metrics_df["Year"].max())
    metrics = _apply_year_window(metrics_df, year_min, year_max)
    if metrics.empty:
        return False

    old_media = {"Comcast", "Disney", "Warner Bros. Discovery", "Paramount Global"}
    tech_media = {"Alphabet", "Amazon", "Apple", "Meta Platforms", "Microsoft", "Netflix", "Roku", "Spotify"}

    st.markdown("<div id='section-company-deep-dives'></div>", unsafe_allow_html=True)
    st.markdown("### Company Financial Deep Dives")
    st.caption("P/E, leverage, profitability, investment intensity, and market-structure signals from workbook company sheets.")

    ctrl1, ctrl2, ctrl3 = st.columns([1.0, 2.1, 1.0])
    with ctrl1:
        sector_mode = st.radio(
            "Sector View",
            ["All", "Tech", "Old Media"],
            horizontal=False,
            key="overview_deepdive_sector_mode",
        )
    all_companies = sorted(metrics["Company"].dropna().astype(str).str.strip().unique().tolist())
    if sector_mode == "Tech":
        company_scope = [c for c in all_companies if c in tech_media]
    elif sector_mode == "Old Media":
        company_scope = [c for c in all_companies if c in old_media]
    else:
        company_scope = all_companies

    latest_scope = metrics[metrics["Year"] <= int(selected_year)].copy()
    default_companies = (
        latest_scope[latest_scope["Company"].isin(company_scope)]
        .sort_values(["Year", "MarketCap"], ascending=[False, False])
        .drop_duplicates(subset=["Company"])
        .head(3)["Company"]
        .tolist()
    )
    if not default_companies:
        default_companies = company_scope[:3]
    with ctrl2:
        chosen_companies = st.multiselect(
            "Comparison Mode (overlay up to 3 companies)",
            options=company_scope,
            default=default_companies,
            key="overview_deepdive_companies",
            help="Select 2-3 companies to overlay in all deep-dive charts.",
        )
    if len(chosen_companies) > 3:
        chosen_companies = chosen_companies[:3]
        st.caption("Comparison mode supports up to 3 companies at once; using the first three selected.")
    if not chosen_companies:
        chosen_companies = default_companies[:3]

    with ctrl3:
        focus_company = st.selectbox(
            "Focus Company",
            ["All"] + chosen_companies,
            index=0,
            key="overview_deepdive_focus_company",
            help="Use a single-company focus while keeping the comparison selection for quick toggling.",
        )
    chart_companies = chosen_companies if focus_company == "All" else [focus_company]
    plot_df = metrics[metrics["Company"].isin(chart_companies)].copy()
    if plot_df.empty:
        return False

    # Revenue-quality and unit economics features.
    plot_df["PE_Ratio"] = np.where(plot_df["NetIncome"] > 0, plot_df["MarketCap"] / plot_df["NetIncome"], np.nan)
    plot_df["Debt_to_Revenue"] = np.where(plot_df["Revenue"] > 0, plot_df["Debt"] / plot_df["Revenue"], np.nan)
    plot_df["Operating_Margin_Pct"] = np.where(plot_df["Revenue"] > 0, (plot_df["OperatingIncome"] / plot_df["Revenue"]) * 100.0, np.nan)
    plot_df["RD_Intensity_Pct"] = np.where(plot_df["Revenue"] > 0, (plot_df["RD"] / plot_df["Revenue"]) * 100.0, np.nan)
    plot_df["Gross_Margin_Pct"] = np.where(plot_df["Revenue"] > 0, ((plot_df["Revenue"] - plot_df["CostOfRevenue"]) / plot_df["Revenue"]) * 100.0, np.nan)
    plot_df["Capex_Intensity_Pct"] = np.where(plot_df["Revenue"] > 0, (plot_df["Capex"] / plot_df["Revenue"]) * 100.0, np.nan)

    tabs = st.tabs(
        [
            "P/E Ratios",
            "Debt Metrics",
            "Operating Margins",
            "R&D Intensity",
            "Employees & Productivity",
            "Market Structure",
        ]
    )

    with tabs[0]:
        pe_df = plot_df.dropna(subset=["PE_Ratio"]).copy()
        pe_df = pe_df[(pe_df["PE_Ratio"] > 0) & (pe_df["PE_Ratio"] < 250)].copy()
        if pe_df.empty:
            st.info("P/E ratio trend is unavailable for these selections (requires positive net income history).")
        else:
            fig = px.line(
                pe_df,
                x="Year",
                y="PE_Ratio",
                color="Company",
                markers=True,
                labels={"PE_Ratio": "P/E ratio (Market Cap / Net Income)", "Year": ""},
            )
            fig.update_layout(
                height=440,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)

        # Quarterly sparkline row: Revenue QoQ + YoY + TTM for selected companies.
        if quarterly_df is None or quarterly_df.empty:
            st.caption("Quarterly sparkline cards are unavailable until `Company_Quarterly_segments_valu` is populated.")
        else:
            st.markdown("#### Quarterly Momentum (QoQ, YoY, TTM)")
            qnum = _parse_quarter_number(selected_quarter) or 4
            card_cols = st.columns(min(len(chart_companies), 3)) if chart_companies else []
            for col, company in zip(card_cols, chart_companies):
                with col:
                    ticker = _COMPANY_TO_TICKER.get(company, "")
                    q_scope = quarterly_df[
                        (quarterly_df["Ticker"] == ticker)
                        & (
                            (quarterly_df["Year"] < int(selected_year))
                            | (
                                (quarterly_df["Year"] == int(selected_year))
                                & (quarterly_df["QuarterNum"] <= int(qnum))
                            )
                        )
                    ].copy()
                    if q_scope.empty:
                        st.caption(f"{company}: no quarterly rows yet.")
                        continue
                    q_scope = q_scope.sort_values(["Year", "QuarterNum"])
                    latest = q_scope.iloc[-1]
                    prev = q_scope.iloc[-2] if len(q_scope) > 1 else None
                    prev_y = q_scope[
                        (q_scope["Year"] == int(latest["Year"]) - 1)
                        & (q_scope["QuarterNum"] == int(latest["QuarterNum"]))
                    ]
                    prev_y_row = prev_y.iloc[-1] if not prev_y.empty else None
                    curr_rev = float(latest["Revenue"]) if pd.notna(latest["Revenue"]) else np.nan
                    qoq = (
                        ((curr_rev - float(prev["Revenue"])) / float(prev["Revenue"])) * 100.0
                        if prev is not None and pd.notna(prev["Revenue"]) and float(prev["Revenue"]) != 0
                        else np.nan
                    )
                    yoy = (
                        ((curr_rev - float(prev_y_row["Revenue"])) / float(prev_y_row["Revenue"])) * 100.0
                        if prev_y_row is not None and pd.notna(prev_y_row["Revenue"]) and float(prev_y_row["Revenue"]) != 0
                        else np.nan
                    )
                    ttm = (
                        q_scope.tail(4)["Revenue"].sum(min_count=1)
                        if len(q_scope) >= 4
                        else np.nan
                    )
                    # Company_Quarterly_segments_valu stores raw USD amounts.
                    curr_rev_b = curr_rev / 1_000_000_000.0 if pd.notna(curr_rev) else np.nan
                    ttm_b = ttm / 1_000_000_000.0 if pd.notna(ttm) else np.nan
                    st.metric(
                        f"{company} Revenue",
                        _format_macro_metric(curr_rev_b, "B"),
                        f"{qoq:+.1f}% QoQ" if pd.notna(qoq) else "QoQ N/A",
                    )
                    st.caption(
                        f"{yoy:+.1f}% YoY · TTM {_format_macro_metric(ttm_b, 'B')}"
                    )
                    spark = q_scope.tail(8).copy()
                    spark["Label"] = spark["Year"].astype(str) + "Q" + spark["QuarterNum"].astype(str)
                    spark_fig = go.Figure(
                        go.Scatter(
                            x=spark["Label"],
                            y=spark["Revenue"] / 1_000_000_000.0,
                            mode="lines+markers",
                            line=dict(color="#2563EB", width=2),
                            marker=dict(size=4),
                            hovertemplate="%{x}<br>$%{y:.2f}B<extra></extra>",
                            showlegend=False,
                        )
                    )
                    spark_fig.update_layout(
                        height=120,
                        margin=dict(l=4, r=4, t=6, b=6),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(visible=False),
                        yaxis=dict(visible=False),
                    )
                    st.plotly_chart(spark_fig, use_container_width=True, config=plotly_config)

    with tabs[1]:
        debt_df = plot_df.dropna(subset=["Debt_to_Revenue"]).copy()
        if debt_df.empty:
            st.info("Debt-to-revenue ratio is unavailable for the selected companies.")
        else:
            fig = px.line(
                debt_df,
                x="Year",
                y="Debt_to_Revenue",
                color="Company",
                markers=True,
                labels={"Debt_to_Revenue": "Debt / Revenue", "Year": ""},
            )
            fig.update_layout(
                height=420,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)

            heat_df = debt_df.pivot_table(index="Company", columns="Year", values="Debt_to_Revenue", aggfunc="mean")
            if not heat_df.empty:
                fig_h = px.imshow(
                    heat_df,
                    aspect="auto",
                    color_continuous_scale="Blues",
                    labels=dict(x="Year", y="Company", color="Debt / Revenue"),
                )
                fig_h.update_layout(
                    height=320,
                    margin=dict(l=20, r=20, t=10, b=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_h, use_container_width=True, config=plotly_config)

    with tabs[2]:
        margin_df = plot_df.dropna(subset=["Operating_Margin_Pct", "Gross_Margin_Pct"], how="all").copy()
        if margin_df.empty:
            st.info("Operating/Gross margin trends are unavailable for selected companies.")
        else:
            op_long = margin_df[["Company", "Year", "Operating_Margin_Pct"]].rename(
                columns={"Operating_Margin_Pct": "MarginPct"}
            )
            op_long["Metric"] = "Operating Margin %"
            gm_long = margin_df[["Company", "Year", "Gross_Margin_Pct"]].rename(
                columns={"Gross_Margin_Pct": "MarginPct"}
            )
            gm_long["Metric"] = "Gross Margin %"
            long_df = pd.concat([op_long, gm_long], ignore_index=True).dropna(subset=["MarginPct"])
            fig = px.line(
                long_df,
                x="Year",
                y="MarginPct",
                color="Company",
                line_dash="Metric",
                markers=True,
                labels={"MarginPct": "Margin (%)", "Year": ""},
            )
            fig.update_layout(
                height=440,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)

            cap_cash = margin_df.groupby("Year", as_index=False)[["CashBalance", "Capex"]].sum(min_count=1)
            if not cap_cash.empty:
                fig2 = go.Figure()
                fig2.add_trace(
                    go.Bar(
                        x=cap_cash["Year"],
                        y=cap_cash["Capex"] / 1000.0,
                        name="CapEx (B USD)",
                        marker_color="#2563EB",
                        opacity=0.65,
                    )
                )
                fig2.add_trace(
                    go.Scatter(
                        x=cap_cash["Year"],
                        y=cap_cash["CashBalance"] / 1000.0,
                        mode="lines+markers",
                        name="Cash Balance (B USD)",
                        line=dict(color="#0EA5E9", width=3),
                    )
                )
                fig2.update_layout(
                    height=360,
                    margin=_overview_chart_margin(),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis_title="USD billions",
                    legend=_overview_legend_style(),
                )
                fig2.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
                st.plotly_chart(fig2, use_container_width=True, config=plotly_config)
                st.caption("Cash flow is not available in the workbook; cash balance is used as an investment-capacity proxy vs CapEx.")

    with tabs[3]:
        rd_df = plot_df.dropna(subset=["RD_Intensity_Pct"]).copy()
        if rd_df.empty:
            st.info("R&D intensity is unavailable for selected companies.")
        else:
            fig = px.line(
                rd_df,
                x="Year",
                y="RD_Intensity_Pct",
                color="Company",
                markers=True,
                labels={"RD_Intensity_Pct": "R&D / Revenue (%)", "Year": ""},
            )
            fig.update_layout(
                height=420,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)

    with tabs[4]:
        emp_df = _apply_year_window(employees_df, year_min, year_max)
        merged_emp = plot_df.merge(emp_df, on=["Company", "Year"], how="left") if not emp_df.empty else pd.DataFrame()
        if merged_emp.empty or "Employees" not in merged_emp.columns:
            st.info("Employee comparison is unavailable because `Company_Employees` rows are missing for the selected companies.")
        else:
            merged_emp["Employees"] = pd.to_numeric(merged_emp["Employees"], errors="coerce")
            merged_emp = merged_emp.dropna(subset=["Employees"]).copy()
            if merged_emp.empty:
                st.info("No employee-count overlap found for these companies.")
            else:
                merged_emp["Revenue_per_Employee_MUSD"] = np.where(
                    (merged_emp["Employees"] > 0) & merged_emp["Revenue"].notna(),
                    merged_emp["Revenue"] / merged_emp["Employees"],
                    np.nan,
                )

                st.markdown("#### Employee Count Trend")
                fig_emp = px.line(
                    merged_emp,
                    x="Year",
                    y="Employees",
                    color="Company",
                    markers=True,
                    labels={"Employees": "Employees", "Year": ""},
                )
                fig_emp.update_layout(
                    height=400,
                    margin=_overview_chart_margin(),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend=_overview_legend_style(),
                )
                fig_emp.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
                st.plotly_chart(fig_emp, use_container_width=True, config=plotly_config)

                st.markdown("#### Revenue per Employee")
                rpe = merged_emp.dropna(subset=["Revenue_per_Employee_MUSD"]).copy()
                if rpe.empty:
                    st.info("Revenue-per-employee requires both revenue and employee rows for the selected companies.")
                else:
                    fig_rpe = px.line(
                        rpe,
                        x="Year",
                        y="Revenue_per_Employee_MUSD",
                        color="Company",
                        markers=True,
                        labels={"Revenue_per_Employee_MUSD": "Revenue per Employee (M USD)", "Year": ""},
                    )
                    fig_rpe.update_layout(
                        height=400,
                        margin=_overview_chart_margin(),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        legend=_overview_legend_style(),
                    )
                    fig_rpe.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
                    st.plotly_chart(fig_rpe, use_container_width=True, config=plotly_config)

                    rank = rpe[rpe["Year"] == int(selected_year)].copy()
                    if rank.empty:
                        rank = rpe[rpe["Year"] <= int(selected_year)].copy()
                        if not rank.empty:
                            rank = rank[rank["Year"] == int(rank["Year"].max())].copy()
                    if not rank.empty:
                        rank = rank.sort_values("Revenue_per_Employee_MUSD", ascending=True)
                        fig_rank = px.bar(
                            rank,
                            x="Revenue_per_Employee_MUSD",
                            y="Company",
                            orientation="h",
                            color="Company",
                            labels={"Revenue_per_Employee_MUSD": "Revenue per Employee (M USD)", "Company": ""},
                        )
                        fig_rank.update_layout(
                            height=360,
                            margin=_overview_chart_margin(left=20, right=20, top=84, bottom=96),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            showlegend=False,
                        )
                        fig_rank.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
                        st.plotly_chart(fig_rank, use_container_width=True, config=plotly_config)

    with tabs[5]:
        if market_structure_df.empty:
            st.info("Duopoly/Triopoly concentration history is not available in current ad sheets.")
        else:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=market_structure_df["Year"],
                    y=market_structure_df["Duopoly_Share_Pct"],
                    mode="lines+markers",
                    name="Google + Meta share (%)",
                    line=dict(color="#1D4ED8", width=3),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=market_structure_df["Year"],
                    y=market_structure_df["Triopoly_Share_Pct"],
                    mode="lines+markers",
                    name="Google + Meta + Amazon share (%)",
                    line=dict(color="#0EA5E9", width=3),
                )
            )
            fig.update_layout(
                height=420,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis_title="Share of global ad market (%)",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)

        if not subs_df.empty:
            subs_annual = (
                subs_df[subs_df["company"].isin(chart_companies)]
                .groupby(["company", "year"], as_index=False)["subscribers"]
                .mean()
                .rename(columns={"company": "Company", "year": "Year", "subscribers": "SubscribersMAvg"})
            )
            arpu_df = plot_df.merge(subs_annual, on=["Company", "Year"], how="inner")
            arpu_df = arpu_df[arpu_df["SubscribersMAvg"] > 0].copy()
            arpu_df["ARPU_USD_Proxy"] = arpu_df["Revenue"] / arpu_df["SubscribersMAvg"]
            if not arpu_df.empty:
                fig_arpu = px.line(
                    arpu_df,
                    x="Year",
                    y="ARPU_USD_Proxy",
                    color="Company",
                    markers=True,
                    labels={"ARPU_USD_Proxy": "Annual ARPU proxy (USD per subscriber)", "Year": ""},
                )
                fig_arpu.update_layout(
                    height=360,
                    margin=_overview_chart_margin(),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend=_overview_legend_style(),
                )
                fig_arpu.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
                st.plotly_chart(fig_arpu, use_container_width=True, config=plotly_config)
                st.caption("ARPU proxy = annual revenue (USD millions) / average reported subscribers (millions).")

        if minute_df is not None and not minute_df.empty:
            md = minute_df.dropna(subset=["RevenueB", "TotalMinutesT", "DollarPerMinute"]).copy()
            if not md.empty:
                fig_md = px.scatter(
                    md,
                    x="TotalMinutesT",
                    y="RevenueB",
                    size="DollarPerMinute",
                    color="Platform",
                    text="Platform",
                    labels={
                        "TotalMinutesT": "Total internet hours proxy (trillion minutes watched)",
                        "RevenueB": "Revenue (USD billions)",
                        "DollarPerMinute": "$ per minute watched",
                    },
                    size_max=45,
                )
                fig_md.update_traces(textposition="top center")
                fig_md.update_layout(
                    height=400,
                    margin=_overview_chart_margin(),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend=_overview_legend_style(),
                )
                fig_md.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
                fig_md.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
                st.plotly_chart(fig_md, use_container_width=True, config=plotly_config)

        st.caption("Customer acquisition cost trends are not available in current workbook sheets.")

    return True


def _render_device_platform_market_share(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    plotly_config: dict,
) -> bool:
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    if not excel_path:
        return False

    smartphone_df = _load_hardware_smartphone_shipments_df(excel_path, source_stamp)
    country_ad_df = _load_country_advertising_df(excel_path, source_stamp)
    if smartphone_df.empty and country_ad_df.empty:
        return False

    st.markdown("<div id='section-device-platform'></div>", unsafe_allow_html=True)
    st.markdown("### Device & Platform Market Share")
    st.caption("Device shipment concentration and device-category ad allocation after macro regime validation.")
    rendered = False

    if not smartphone_df.empty:
        unit_cols = [
            c for c in smartphone_df.columns
            if c not in {"Year", "Total_Global_Units_M", "Apple_iPhone_Units_M", "AppleSharePct"}
            and c.lower().endswith("_units_m")
        ]
        if unit_cols:
            pretty_map = {
                "Apple_iPhone_Units_M": "Apple iPhone",
                "Samsung_Units_M": "Samsung",
                "Xiaomi_Units_M": "Xiaomi",
                "Huawei_Units_M": "Huawei",
                "Oppo_Units_M": "Oppo",
                "Vivo_Units_M": "Vivo",
                "Motorola_Units_M": "Motorola",
                "Google_Pixel_Units_M": "Google Pixel",
                "OnePlus_Units_M": "OnePlus",
                "Other_Brands_Units_M": "Other Brands",
            }
            major_cols = [c for c in ["Apple_iPhone_Units_M", "Samsung_Units_M", "Xiaomi_Units_M", "Huawei_Units_M"] if c in smartphone_df.columns]
            other_known = [c for c in unit_cols if c not in major_cols and c != "Other_Brands_Units_M"]
            sp = smartphone_df.copy()
            if "Other_Brands_Units_M" in sp.columns:
                sp["Other_Manufacturers_M"] = pd.to_numeric(sp["Other_Brands_Units_M"], errors="coerce").fillna(0.0)
            else:
                known_sum = sp[major_cols + other_known].sum(axis=1, min_count=1)
                sp["Other_Manufacturers_M"] = (sp["Total_Global_Units_M"] - known_sum).clip(lower=0.0)

            stacked_cols = major_cols + ["Other_Manufacturers_M"]
            long_units = sp.melt(
                id_vars=["Year"],
                value_vars=stacked_cols,
                var_name="ManufacturerRaw",
                value_name="Units_M",
            ).dropna(subset=["Units_M"])
            long_units["Manufacturer"] = long_units["ManufacturerRaw"].map(pretty_map).fillna(
                long_units["ManufacturerRaw"].str.replace("_Units_M", "", regex=False).str.replace("_", " ", regex=False)
            )
            long_units["SharePct"] = np.where(
                long_units["Units_M"] > 0,
                (long_units["Units_M"] / long_units.groupby("Year")["Units_M"].transform("sum")) * 100.0,
                np.nan,
            )

            st.markdown("#### Apple iPhone vs Other Mobile Manufacturers")
            fig = px.area(
                long_units,
                x="Year",
                y="Units_M",
                color="Manufacturer",
                labels={"Units_M": "Units shipped (millions)", "Year": ""},
            )
            fig.update_layout(
                height=430,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)

            st.markdown("#### Device Market Share Evolution by Manufacturer")
            fig_share = px.line(
                long_units,
                x="Year",
                y="SharePct",
                color="Manufacturer",
                markers=True,
                labels={"SharePct": "Market share (%)", "Year": ""},
            )
            fig_share.update_layout(
                height=410,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=_overview_legend_style(),
            )
            fig_share.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig_share, use_container_width=True, config=plotly_config)
            rendered = True

    if not country_ad_df.empty:
        cad = country_ad_df.copy()
        cad["MetricLower"] = cad["Metric_type"].astype(str).str.strip().str.lower()
        cad["DeviceCategory"] = np.select(
            [
                cad["MetricLower"].str.contains("mobile", na=False),
                cad["MetricLower"].str.contains("desktop", na=False),
                cad["MetricLower"].str.contains("tv", na=False),
            ],
            ["Mobile", "Desktop", "TV"],
            default="Other",
        )
        cad = cad[cad["DeviceCategory"].isin(["Mobile", "Desktop", "TV"])].copy()
        if not cad.empty:
            country_to_region = {}
            for region, names in CONTINENT_MAPPINGS.items():
                for name in names:
                    country_to_region[str(name)] = str(region)
            cad["Region"] = cad["Country"].map(country_to_region).fillna("Other")

            year_focus = int(selected_year)
            cad_year = cad[cad["Year"] == year_focus].copy()
            if cad_year.empty:
                fallback = cad[cad["Year"] <= year_focus]
                if not fallback.empty:
                    year_focus = int(fallback["Year"].max())
                    cad_year = cad[cad["Year"] == year_focus].copy()

            if not cad_year.empty:
                reg = cad_year.groupby(["Region", "DeviceCategory"], as_index=False)["Value"].sum(min_count=1)
                reg["SharePct"] = np.where(
                    reg.groupby("Region")["Value"].transform("sum") > 0,
                    (reg["Value"] / reg.groupby("Region")["Value"].transform("sum")) * 100.0,
                    np.nan,
                )
                st.markdown("#### Advertising Split by Device Category and Region")
                fig_reg = px.bar(
                    reg,
                    x="Region",
                    y="SharePct",
                    color="DeviceCategory",
                    barmode="stack",
                    labels={"SharePct": "Share of regional ad spend (%)", "Region": ""},
                    color_discrete_map={"Mobile": "#2563EB", "Desktop": "#0EA5E9", "TV": "#F59E0B"},
                )
                fig_reg.update_layout(
                    height=430,
                    margin=_overview_chart_margin(),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend=_overview_legend_style(),
                )
                fig_reg.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
                st.plotly_chart(fig_reg, use_container_width=True, config=plotly_config)
                st.caption(f"Year shown: {year_focus}")
                rendered = True

    return rendered


def _render_global_media_economy_extras(
    country_ad_df: pd.DataFrame,
    data_processor: FinancialDataProcessor,
    map_year: int,
    plotly_config: dict,
) -> bool:
    if country_ad_df is None or country_ad_df.empty:
        return False
    rendered = False

    # Time trajectories for top countries by selected map year.
    country_totals = country_ad_df.groupby(["Country", "Year"], as_index=False)["Value"].sum(min_count=1)
    top_countries = (
        country_totals[country_totals["Year"] == int(map_year)]
        .sort_values("Value", ascending=False)
        .head(8)["Country"]
        .tolist()
    )
    if top_countries:
        trend_df = country_totals[country_totals["Country"].isin(top_countries)].copy()
        st.markdown("#### Country Advertising Growth Trajectories")
        fig_trend = px.line(
            trend_df,
            x="Year",
            y="Value",
            color="Country",
            markers=True,
            labels={"Value": "Advertising spend (USD millions)", "Year": ""},
        )
        fig_trend.update_layout(
            height=410,
            margin=_overview_chart_margin(),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=_overview_legend_style(),
        )
        fig_trend.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
        st.plotly_chart(fig_trend, use_container_width=True, config=plotly_config)
        rendered = True

    # Per-capita advertising spend (when population proxies are available in Macro_Wealth_by_Generation).
    wealth_df = _load_macro_wealth_by_generation_df(
        getattr(data_processor, "data_path", ""),
        int(getattr(data_processor, "source_stamp", 0) or 0),
    )
    if wealth_df is not None and not wealth_df.empty and "PeopleM" in wealth_df.columns:
        population = (
            wealth_df.groupby(["Country", "Year"], as_index=False)["PeopleM"]
            .sum(min_count=1)
            .dropna(subset=["PeopleM"])
        )
        population = population[population["PeopleM"] > 0].copy()
        year_country = country_totals[country_totals["Year"] == int(map_year)].copy()
        per_capita = year_country.merge(population, on=["Country", "Year"], how="inner")
        if not per_capita.empty:
            per_capita["AdPerCapitaUSD"] = per_capita["Value"] / per_capita["PeopleM"]
            rank = per_capita.sort_values("AdPerCapitaUSD", ascending=False).head(20).sort_values("AdPerCapitaUSD")
            if not rank.empty:
                st.markdown("#### Per-Capita Advertising Spend by Country")
                fig_pc = px.bar(
                    rank,
                    x="AdPerCapitaUSD",
                    y="Country",
                    orientation="h",
                    color="AdPerCapitaUSD",
                    color_continuous_scale="Blues",
                    labels={"AdPerCapitaUSD": "Ad spend per capita (USD)", "Country": ""},
                )
                fig_pc.update_layout(
                    height=560,
                    margin=_overview_chart_margin(),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    coloraxis_showscale=False,
                )
                fig_pc.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
                st.plotly_chart(fig_pc, use_container_width=True, config=plotly_config)
                rendered = True

    # Mobile vs Desktop split by region.
    cad = country_ad_df.copy()
    cad["MetricLower"] = cad["Metric_type"].astype(str).str.strip().str.lower()
    cad["DeviceClass"] = np.select(
        [
            cad["MetricLower"].str.contains("mobile", na=False),
            cad["MetricLower"].str.contains("desktop", na=False),
        ],
        ["Mobile", "Desktop"],
        default="Other",
    )
    cad = cad[cad["DeviceClass"].isin(["Mobile", "Desktop"])].copy()
    if not cad.empty:
        country_to_region = {}
        for region, names in CONTINENT_MAPPINGS.items():
            for name in names:
                country_to_region[str(name)] = str(region)
        cad["Region"] = cad["Country"].map(country_to_region).fillna("Other")
        cad = cad[cad["Year"] == int(map_year)].copy()
        if not cad.empty:
            reg = cad.groupby(["Region", "DeviceClass"], as_index=False)["Value"].sum(min_count=1)
            reg["SharePct"] = np.where(
                reg.groupby("Region")["Value"].transform("sum") > 0,
                (reg["Value"] / reg.groupby("Region")["Value"].transform("sum")) * 100.0,
                np.nan,
            )
            st.markdown("#### Mobile vs Desktop Split by Region")
            fig_split = px.bar(
                reg,
                x="Region",
                y="SharePct",
                color="DeviceClass",
                barmode="group",
                labels={"SharePct": "Share of device-class ad spend (%)", "Region": ""},
                color_discrete_map={"Mobile": "#2563EB", "Desktop": "#0EA5E9"},
            )
            fig_split.update_layout(
                height=420,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=_overview_legend_style(),
            )
            fig_split.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig_split, use_container_width=True, config=plotly_config)
            rendered = True

    return rendered


def _render_excel_macro_section(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
) -> bool:
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    if not excel_path:
        return False
    macro_df = _load_overview_macro_sheet(excel_path, source_stamp)
    if macro_df.empty:
        return False

    scoped_df, selected_period = _pick_rows_for_period(macro_df, selected_year, selected_quarter)
    if scoped_df.empty:
        return False
    row = scoped_df.sort_values(["year", "quarter"], ascending=[False, False]).iloc[0]

    st.markdown("### Macro KPI Bar")
    st.caption(f"Source: Overview_Macro · Period: {selected_period}")
    metric_items = [
        ("M2", row.get("m2_value"), "B"),
        ("Global Ad Market", row.get("global_ad_market"), "B"),
        ("Duopoly Share", row.get("duopoly_share"), "%"),
        ("TV Ad Spend", row.get("tv_ad_spend"), "B"),
        ("Internet Ad Spend", row.get("internet_ad_spend"), "B"),
    ]
    retail_value = row.get("retail_media")
    if pd.notna(retail_value):
        metric_items.append(("Retail Media", retail_value, "B"))
    columns = st.columns(len(metric_items))
    for col, (label, value, suffix) in zip(columns, metric_items):
        with col:
            st.metric(label, _format_macro_metric(value, suffix))

    macro_comment = _clean_overview_text(row.get("macro_comment"))
    if macro_comment:
        st.markdown(macro_comment)
    return True


def _render_excel_overview_insights(
    data_processor: FinancialDataProcessor,
    selected_year: int | None,
    selected_quarter: str | None,
) -> bool:
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    if not excel_path:
        return False
    insights_df = _load_overview_insights_sheet(excel_path, source_stamp)
    if insights_df.empty:
        return False

    scoped_df, selected_period = _pick_rows_for_period(insights_df, selected_year, selected_quarter)
    if scoped_df.empty:
        return False
    scoped_df = scoped_df.sort_values(["sort_order", "insight_id", "title"]).copy()

    st.markdown("<div id='section-overview-insights'></div>", unsafe_allow_html=True)
    st.markdown("### Insights by Category")
    st.caption(f"Source: Overview_Insights · Period: {selected_period} · {len(scoped_df)} insights")
    company_logos = load_company_logos()

    categories_present = scoped_df["category"].dropna().astype(str).str.strip().unique().tolist()
    ordered_categories = [
        *[c for c in _OVERVIEW_INSIGHT_CATEGORY_ORDER if c in categories_present],
        *[c for c in categories_present if c not in _OVERVIEW_INSIGHT_CATEGORY_ORDER],
    ]
    html_parts: list[str] = []
    for category in ordered_categories:
        cat_df = scoped_df[scoped_df["category"] == category].copy()
        if cat_df.empty:
            continue

        bullets_html = ""
        for local_idx, (_, row) in enumerate(cat_df.iterrows(), start=1):
            code = _clean_overview_text(row.get("insight_code")) or _clean_overview_text(row.get("insight_id")) or str(local_idx)
            title = _clean_overview_text(row.get("title"))
            stat = _clean_overview_text(row.get("stat"))
            stat_label = _clean_overview_text(row.get("stat_label"))
            comment = _clean_insight_comment_text(row.get("overview_comment") or row.get("comment"))
            companies = _extract_insight_companies(title, comment)
            logos_html = _inline_insight_company_logos_html(companies, company_logos, size_px=72)

            stat_badge = ""
            if stat:
                label_text = f" · {html.escape(stat_label)}" if stat_label else ""
                stat_badge = f"<span class='ov-insight-stat'>{html.escape(stat)}{label_text}</span>"
            comment_html = html.escape(comment).replace("\n", "<br>")

            bullets_html += (
                "<div class='ov-insight-item'>"
                "<div class='ov-insight-head-row'>"
                "<div class='ov-insight-head'>"
                f"{html.escape(code)} — {html.escape(title)}{stat_badge}"
                "</div>"
                f"{logos_html}"
                "</div>"
                "<p class='ov-insight-body'>"
                f"{comment_html}"
                "</p>"
                "</div>"
            )

        html_parts.append(
            "<div class='ov-insight-category-card'>"
            f"<div class='ov-insight-category-title'>{html.escape(category)}</div>"
            f"{bullets_html}"
            "</div>"
        )

    if html_parts:
        st.markdown("".join(html_parts), unsafe_allow_html=True)
    return True


@st.cache_data(show_spinner=False)
def _normalize_generated_auto_insights_df(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()

    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = _rename_overview_columns(df, _OVERVIEW_AUTO_INSIGHTS_COLUMN_ALIASES)

    required = [
        "insight_id",
        "sort_order",
        "category",
        "title",
        "year",
        "quarter",
        "frequency",
        "comment",
        "text",
        "priority",
        "companies",
        "kpis",
        "graph_type",
        "is_active",
    ]
    for col in required:
        if col not in df.columns:
            df[col] = ""

    if "text" in df.columns and "comment" in df.columns:
        df["comment"] = df["comment"].where(df["comment"].astype(str).str.strip() != "", df["text"])
    if "comment" in df.columns and "text" in df.columns:
        df["text"] = df["text"].where(df["text"].astype(str).str.strip() != "", df["comment"])

    out = df.copy()
    out["insight_id"] = out["insight_id"].astype(str).str.strip()
    out["sort_order"] = pd.to_numeric(out["sort_order"], errors="coerce")
    missing_sort = out["sort_order"].isna()
    if missing_sort.any():
        out.loc[missing_sort, "sort_order"] = pd.to_numeric(
            out.loc[missing_sort, "insight_id"].str.extract(r"(\d+)", expand=False),
            errors="coerce",
        )
    out["sort_order"] = out["sort_order"].fillna(9_999).astype(int)
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out["quarter"] = out["quarter"].apply(_normalize_quarter_label)
    out["category"] = out["category"].astype(str).str.strip().replace("", "Auto")
    out["title"] = out["title"].astype(str).str.strip()
    out["comment"] = out["comment"].astype(str).str.strip()
    out["text"] = out["text"].astype(str).str.strip()
    out["graph_type"] = out.get("graph_type", "").astype(str).str.strip()
    out["companies"] = out.get("companies", "").astype(str).str.strip()
    out["priority"] = out.get("priority", "").astype(str).str.strip()
    out["kpis"] = out.get("kpis", "").astype(str).str.strip()
    out["is_active"] = out.get("is_active", 1).apply(_parse_is_active_flag).astype(int)
    out = out[out["title"] != ""].copy()
    if out.empty:
        return pd.DataFrame()

    return out.sort_values(["sort_order", "insight_id", "title"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def _load_generated_auto_insights_sheet(excel_path: str, source_stamp: int = 0) -> tuple[pd.DataFrame, str]:
    if not excel_path:
        return pd.DataFrame(), ""

    raw, sheet_name = _read_excel_sheet_flexible(
        excel_path=excel_path,
        source_stamp=source_stamp,
        preferred="Overview_Auto_Insights",
        aliases=[
            "Overview Auto Insights",
            "Auto_Insights",
            "Generated_Insights",
            "Auto Insights",
        ],
        contains_all=["insight"],
        contains_any=["auto", "generated"],
    )
    if raw.empty:
        return pd.DataFrame(), ""

    out = _normalize_generated_auto_insights_df(raw)
    if out.empty:
        return pd.DataFrame(), ""
    return out, sheet_name


@st.cache_data(show_spinner=False)
def _load_generated_auto_insights_csv() -> pd.DataFrame:
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "earningscall_transcripts" / "generated_insights_latest.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    return _normalize_generated_auto_insights_df(df)


def _parse_pipe_list(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    items = re.split(r"[|,;/]+", text)
    return [it.strip() for it in items if str(it).strip()]


@st.cache_data(show_spinner=False)
def _load_transcript_kpis_csv() -> pd.DataFrame:
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "earningscall_transcripts" / "transcript_kpis.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    for col in ["company", "year", "quarter", "kpi_type", "value_text"]:
        if col not in out.columns:
            out[col] = ""
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out["quarter"] = out["quarter"].apply(_normalize_quarter_label)
    out["company"] = out["company"].astype(str).str.strip()
    out["kpi_type"] = out["kpi_type"].astype(str).str.strip()
    out = out.dropna(subset=["year"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["year"] = out["year"].astype(int)
    return out


def _render_auto_insight_graph(
    graph_type: str,
    companies: list[str],
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
    plotly_config: dict,
) -> None:
    graph = str(graph_type or "").strip().lower()
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    if not excel_path:
        st.caption("Workbook source not available.")
        return

    metrics_df = _load_company_metrics_yearly_df(excel_path, source_stamp)
    employees_df = _load_employee_yearly_df(excel_path, source_stamp)

    if graph == "duopoly_share_trend":
        series = _compute_duopoly_triopoly_share_series(data_processor, excel_path, source_stamp)
        if series.empty:
            st.info("Duopoly/Triopoly series is unavailable.")
            return
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=series["Year"], y=series["Duopoly_Share_Pct"], mode="lines+markers", name="Duopoly share (%)", line=dict(color="#1D4ED8", width=3)))
        fig.add_trace(go.Scatter(x=series["Year"], y=series["Triopoly_Share_Pct"], mode="lines+markers", name="Triopoly share (%)", line=dict(color="#0EA5E9", width=3)))
        fig.update_layout(
            height=360,
            margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="Share (%)",
            legend=_overview_legend_style(),
        )
        fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
        return

    if graph == "ad_revenue_growth_comparison":
        try:
            if getattr(data_processor, "df_ad_revenue", None) is None or data_processor.df_ad_revenue.empty:
                data_processor._load_ad_revenue()
        except Exception:
            pass
        ad_df = getattr(data_processor, "df_ad_revenue", None)
        if ad_df is None or ad_df.empty:
            st.info("Ad revenue sheet is unavailable.")
            return
        ad = ad_df.copy()
        ad.columns = [str(c).strip() for c in ad.columns]
        if "year" in ad.columns and "Year" not in ad.columns:
            ad = ad.rename(columns={"year": "Year"})
        if "Year" not in ad.columns:
            st.info("Ad revenue sheet has no year column.")
            return
        ad["Year"] = pd.to_numeric(ad["Year"], errors="coerce")
        ad = ad.dropna(subset=["Year"]).copy()
        ad["Year"] = ad["Year"].astype(int)
        map_cols = {
            "Google_Ads": "Alphabet",
            "Meta_Ads": "Meta Platforms",
            "Amazon_Ads": "Amazon",
            "Spotify_Ads": "Spotify",
            "Comcast": "Comcast",
            "Netflix": "Netflix",
            "Disney": "Disney",
            "Paramount": "Paramount Global",
            "WBD_Ads": "Warner Bros. Discovery",
            "Microsoft_Ads": "Microsoft",
        }
        rows = []
        for col, cname in map_cols.items():
            for c in [col, f"*{col}"]:
                if c in ad.columns:
                    tmp = ad[["Year", c]].copy().rename(columns={c: "AdRevenue"})
                    tmp["Company"] = cname
                    rows.append(tmp)
                    break
        if not rows:
            st.info("No ad-revenue company columns available.")
            return
        long = pd.concat(rows, ignore_index=True)
        long["AdRevenue"] = pd.to_numeric(long["AdRevenue"], errors="coerce")
        long = long.dropna(subset=["AdRevenue"]).copy()
        long = long.sort_values(["Company", "Year"])
        long["YoY"] = long.groupby("Company")["AdRevenue"].pct_change() * 100.0
        scope = long[long["Year"] == int(selected_year)].dropna(subset=["YoY"]).copy()
        if scope.empty:
            st.info("No YoY ad-growth values for the selected year.")
            return
        if companies:
            scope = scope[scope["Company"].isin(companies)].copy() if not scope.empty else scope
        scope = scope.sort_values("YoY", ascending=True)
        fig = px.bar(
            scope,
            x="YoY",
            y="Company",
            orientation="h",
            color="Company",
            labels={"YoY": "Ad Revenue YoY (%)", "Company": ""},
        )
        fig.update_layout(
            height=360,
            margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
        return

    if graph in {"revenue_per_employee_comparison", "employee_count_comparison", "market_cap_vs_headcount_growth"}:
        if metrics_df.empty or employees_df.empty:
            st.info("Employee/productivity charts need both Company_metrics_earnings_values and Company_Employees.")
            return
        merged = metrics_df.merge(employees_df, on=["Company", "Year"], how="inner")
        if merged.empty:
            st.info("No overlap between employee and metric rows.")
            return
        if companies:
            merged = merged[merged["Company"].isin(companies)].copy()
        if merged.empty:
            st.info("No matching company rows for this insight graph.")
            return

        if graph == "employee_count_comparison":
            scope = merged[merged["Year"] == int(selected_year)].copy()
            if scope.empty:
                scope = merged[merged["Year"] <= int(selected_year)]
                if not scope.empty:
                    scope = scope[scope["Year"] == int(scope["Year"].max())].copy()
            scope = scope.sort_values("Employees", ascending=True)
            fig = px.bar(
                scope,
                x="Employees",
                y="Company",
                orientation="h",
                color="Company",
                labels={"Employees": "Employees", "Company": ""},
            )
            fig.update_layout(
                height=360,
                margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            return

        if graph == "revenue_per_employee_comparison":
            merged["RevPerEmpM"] = np.where(merged["Employees"] > 0, merged["Revenue"] / merged["Employees"], np.nan)
            scope = merged[merged["Year"] == int(selected_year)].dropna(subset=["RevPerEmpM"]).copy()
            if scope.empty:
                scope = merged[merged["Year"] <= int(selected_year)].dropna(subset=["RevPerEmpM"]).copy()
                if not scope.empty:
                    scope = scope[scope["Year"] == int(scope["Year"].max())].copy()
            scope = scope.sort_values("RevPerEmpM", ascending=True)
            fig = px.bar(
                scope,
                x="RevPerEmpM",
                y="Company",
                orientation="h",
                color="Company",
                labels={"RevPerEmpM": "Revenue per Employee (M USD)", "Company": ""},
            )
            fig.update_layout(
                height=360,
                margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            return

        base_year = int(selected_year) - 5
        merged["CapPerEmp"] = np.where(merged["Employees"] > 0, merged["MarketCap"] / merged["Employees"], np.nan)
        curr = merged[merged["Year"] == int(selected_year)][["Company", "CapPerEmp"]]
        base = merged[merged["Year"] == int(base_year)][["Company", "CapPerEmp"]].rename(columns={"CapPerEmp": "BaseCapPerEmp"})
        growth = curr.merge(base, on="Company", how="inner")
        growth = growth[(growth["BaseCapPerEmp"] > 0) & growth["CapPerEmp"].notna()].copy()
        if growth.empty:
            st.info("Insufficient 5-year overlap for cap-per-employee growth chart.")
            return
        growth["GrowthMultiple"] = growth["CapPerEmp"] / growth["BaseCapPerEmp"]
        growth = growth.sort_values("GrowthMultiple", ascending=True)
        fig = px.bar(
            growth,
            x="GrowthMultiple",
            y="Company",
            orientation="h",
            color="Company",
            labels={"GrowthMultiple": f"Market Cap per Employee Growth ({base_year}→{selected_year})", "Company": ""},
        )
        fig.update_layout(
            height=360,
            margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
        return

    if graph in {"debt_to_revenue_trend", "rd_intensity_comparison", "operating_margin_comparison", "market_cap_concentration_trend", "streaming_capex_intensity"}:
        if metrics_df.empty:
            st.info("Company metrics are unavailable for this chart.")
            return

        data = metrics_df.copy()
        if companies:
            filtered = data[data["Company"].isin(companies)].copy()
            if not filtered.empty:
                data = filtered

        if graph == "debt_to_revenue_trend":
            data = data[(data["Revenue"] > 0) & data["Debt"].notna()].copy()
            data["DebtToRevenue"] = data["Debt"] / data["Revenue"]
            if data.empty:
                st.info("No debt/revenue overlap available.")
                return
            fig = px.line(
                data,
                x="Year",
                y="DebtToRevenue",
                color="Company",
                markers=True,
                labels={"DebtToRevenue": "Debt / Revenue", "Year": ""},
            )
            fig.update_layout(
                height=360,
                margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            return

        if graph == "rd_intensity_comparison":
            data = data[(data["Revenue"] > 0) & data["RD"].notna()].copy()
            data["RDIntensity"] = (data["RD"] / data["Revenue"]) * 100.0
            scope = data[data["Year"] == int(selected_year)].copy()
            if scope.empty:
                scope = data[data["Year"] <= int(selected_year)]
                if not scope.empty:
                    scope = scope[scope["Year"] == int(scope["Year"].max())].copy()
            scope = scope.sort_values("RDIntensity", ascending=True)
            fig = px.bar(
                scope,
                x="RDIntensity",
                y="Company",
                orientation="h",
                color="Company",
                labels={"RDIntensity": "R&D Intensity (% of Revenue)", "Company": ""},
            )
            fig.update_layout(
                height=360,
                margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            return

        if graph == "operating_margin_comparison":
            data = data[(data["Revenue"] > 0) & data["OperatingIncome"].notna()].copy()
            data["OpMargin"] = (data["OperatingIncome"] / data["Revenue"]) * 100.0
            scope = data[data["Year"] == int(selected_year)].copy()
            if scope.empty:
                scope = data[data["Year"] <= int(selected_year)]
                if not scope.empty:
                    scope = scope[scope["Year"] == int(scope["Year"].max())].copy()
            scope = scope.sort_values("OpMargin", ascending=True)
            fig = px.bar(
                scope,
                x="OpMargin",
                y="Company",
                orientation="h",
                color="Company",
                labels={"OpMargin": "Operating Margin (%)", "Company": ""},
            )
            fig.update_layout(
                height=360,
                margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            return

        if graph == "market_cap_concentration_trend":
            mc = data.dropna(subset=["MarketCap"]).copy()
            if mc.empty:
                st.info("Market-cap series unavailable.")
                return
            yearly = (
                mc.groupby(["Year", "Company"], as_index=False)["MarketCap"].sum(min_count=1)
                .sort_values(["Year", "MarketCap"], ascending=[True, False])
            )
            top3 = yearly.groupby("Year", as_index=False).head(3).groupby("Year", as_index=False)["MarketCap"].sum()
            total = yearly.groupby("Year", as_index=False)["MarketCap"].sum().rename(columns={"MarketCap": "TotalMC"})
            trend = top3.merge(total, on="Year", how="inner")
            trend["Top3Share"] = np.where(trend["TotalMC"] > 0, (trend["MarketCap"] / trend["TotalMC"]) * 100.0, np.nan)
            fig = px.line(
                trend,
                x="Year",
                y="Top3Share",
                markers=True,
                labels={"Top3Share": "Top-3 Market Cap Share (%)", "Year": ""},
            )
            fig.update_layout(
                height=360,
                margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            return

        if graph == "streaming_capex_intensity":
            streamers = {"Netflix", "Disney", "Warner Bros. Discovery", "Paramount Global", "Roku"}
            scope = data[
                (data["Company"].isin(streamers))
                & (data["Year"] == int(selected_year))
                & (data["Revenue"] > 0)
                & data["Capex"].notna()
            ].copy()
            if scope.empty:
                st.info("No streamer capex-intensity rows for this year.")
                return
            scope["CapexIntensity"] = (scope["Capex"] / scope["Revenue"]) * 100.0
            scope = scope.sort_values("CapexIntensity", ascending=True)
            fig = px.bar(
                scope,
                x="CapexIntensity",
                y="Company",
                orientation="h",
                color="Company",
                labels={"CapexIntensity": "CapEx Intensity (% of Revenue)", "Company": ""},
            )
            fig.update_layout(
                height=360,
                margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            return

    if graph in {"topic_mentions_bar", "transcript_kpi_mix", "subscriber_signal_company"}:
        if graph == "topic_mentions_bar":
            topic_df = _load_transcript_topic_metrics()
            if topic_df.empty:
                st.info("Topic metrics are unavailable. Run transcript topic extraction first.")
                return
            scoped, _ = _pick_rows_for_period(topic_df, int(selected_year), selected_quarter)
            if scoped.empty:
                st.info("No topic rows for selected period.")
                return
            scope = scoped.sort_values("mention_count", ascending=False).head(12).copy()
            fig = px.bar(
                scope.sort_values("mention_count", ascending=True),
                x="mention_count",
                y="topic",
                orientation="h",
                color="mention_count",
                color_continuous_scale="Blues",
                labels={"mention_count": "Mentions", "topic": ""},
            )
            fig.update_layout(
                height=360,
                margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            return

        kpi_df = _load_transcript_kpis_csv()
        if kpi_df.empty:
            st.info("Transcript KPI rows are unavailable.")
            return
        scoped, _ = _pick_rows_for_period(kpi_df, int(selected_year), selected_quarter)
        if scoped.empty:
            st.info("No transcript KPI rows for selected period.")
            return

        if graph == "subscriber_signal_company":
            scope = scoped[scoped["kpi_type"].astype(str).str.lower() == "subscribers"].copy()
            if scope.empty:
                st.info("No subscriber KPI mentions for this period.")
                return
            agg = scope.groupby("company", as_index=False).size().rename(columns={"size": "mentions"})
            agg = agg.sort_values("mentions", ascending=True).tail(12)
            fig = px.bar(
                agg,
                x="mentions",
                y="company",
                orientation="h",
                color="mentions",
                color_continuous_scale="Tealgrn",
                labels={"mentions": "Subscriber KPI Mentions", "company": ""},
            )
            fig.update_layout(
                height=360,
                margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            return

        agg = scoped.groupby("kpi_type", as_index=False).size().rename(columns={"size": "mentions"})
        agg = agg.sort_values("mentions", ascending=True).tail(12)
        fig = px.bar(
            agg,
            x="mentions",
            y="kpi_type",
            orientation="h",
            color="mentions",
            color_continuous_scale="Purp",
            labels={"mentions": "Mentions", "kpi_type": ""},
        )
        fig.update_layout(
            height=360,
            margin=_overview_chart_margin(left=24, right=24, top=84, bottom=96),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
        return

    st.caption("No graph renderer mapped for this insight type yet.")


def _render_generated_auto_insights(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
    plotly_config: dict,
) -> bool:
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    auto_df, sheet_name = _load_generated_auto_insights_sheet(excel_path, source_stamp) if excel_path else (pd.DataFrame(), "")
    source_label = f"Workbook/{sheet_name}" if sheet_name else ""
    if auto_df.empty:
        auto_df = _load_generated_auto_insights_csv()
        source_label = "earningscall_transcripts/generated_insights_latest.csv"
    if auto_df.empty:
        return False

    auto_df = auto_df[auto_df["is_active"].apply(_parse_is_active_flag)].copy()
    if auto_df.empty:
        return False
    scoped_df, selected_period = _pick_rows_for_period(auto_df, selected_year, selected_quarter)
    if scoped_df.empty:
        return False

    company_logos = load_company_logos()
    st.markdown("### Auto-Generated Insights")
    st.caption(f"Source: {source_label} · Period: {selected_period}")

    categories_present = scoped_df["category"].dropna().astype(str).str.strip().unique().tolist()
    ordered_categories = [
        *[c for c in _OVERVIEW_INSIGHT_CATEGORY_ORDER if c in categories_present],
        *[c for c in categories_present if c not in _OVERVIEW_INSIGHT_CATEGORY_ORDER],
    ]

    for category in ordered_categories:
        cat_df = scoped_df[scoped_df["category"] == category].copy()
        if cat_df.empty:
            continue
        st.markdown(f"#### {category}")
        cat_df = cat_df.sort_values(["sort_order", "insight_id", "title"])
        for _, row in cat_df.iterrows():
            title = _clean_overview_text(row.get("title"))
            text = _clean_overview_text(row.get("comment") or row.get("text"))
            companies = _parse_pipe_list(row.get("companies"))
            logos_html = _inline_insight_company_logos_html(companies, company_logos, size_px=96)
            if logos_html:
                st.markdown(logos_html, unsafe_allow_html=True)
            st.markdown(f"**{title}**")
            st.markdown(text)
            with st.expander("Show Graph"):
                _render_auto_insight_graph(
                    graph_type=row.get("graph_type"),
                    companies=companies,
                    data_processor=data_processor,
                    selected_year=selected_year,
                    selected_quarter=selected_quarter,
                    plotly_config=plotly_config,
                )
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    return True


@st.cache_data(show_spinner=False)
def _load_transcript_topic_metrics() -> pd.DataFrame:
    repo_root = Path(__file__).resolve().parents[2]
    metrics_path = repo_root / "earningscall_transcripts" / "topic_metrics.csv"
    if not metrics_path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(metrics_path)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    required = [
        "year",
        "quarter",
        "topic",
        "mention_count",
        "companies_mentioned",
        "total_companies",
        "importance_pct",
        "growth_pct",
    ]
    for col in required:
        if col not in df.columns:
            df[col] = np.nan if col not in {"topic"} else ""

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["quarter"] = pd.to_numeric(df["quarter"], errors="coerce")
    df = df.dropna(subset=["year", "quarter"]).copy()
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["year"].astype(int)
    df["quarter"] = df["quarter"].apply(_normalize_quarter_label)
    df["topic"] = df["topic"].astype(str).str.strip()
    for col in ["mention_count", "companies_mentioned", "total_companies", "importance_pct", "growth_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df["topic"] != ""].copy()
    return df


_OVERVIEW_ICONIC_QUOTES_COLUMN_ALIASES = {
    "year": ["year"],
    "quarter": ["quarter", "qtr"],
    "company": ["company", "ticker", "service"],
    "speaker": ["speaker", "speaker_name", "executive", "name"],
    "role_bucket": ["role_bucket", "role", "speaker_role"],
    "quote": ["quote", "highlight", "comment", "text", "insight"],
    "score": ["score", "importance", "rank_score"],
}


def _normalize_role_bucket(value: str) -> str:
    text = str(value or "").strip()
    low = text.lower()
    if "ceo" in low or "chief executive" in low:
        return "CEO"
    if "cfo" in low or "chief financial" in low:
        return "CFO"
    return text.upper() if text else ""


def _normalize_iconic_quotes_df(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = _rename_overview_columns(df, _OVERVIEW_ICONIC_QUOTES_COLUMN_ALIASES)
    required = ["year", "quarter", "company", "speaker", "role_bucket", "quote", "score"]
    for col in required:
        if col not in df.columns:
            df[col] = "" if col in {"quarter", "company", "speaker", "role_bucket", "quote"} else np.nan

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["quarter"] = df["quarter"].apply(_normalize_quarter_label)
    df["company"] = df["company"].apply(_clean_overview_text)
    df["speaker"] = df["speaker"].apply(_clean_overview_text)
    df["role_bucket"] = df["role_bucket"].apply(_normalize_role_bucket)
    df["quote"] = df["quote"].apply(_clean_overview_text)
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df = df.dropna(subset=["year"]).copy()
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["year"].astype(int)
    df = df[(df["company"] != "") & (df["quote"] != "")].copy()
    if df.empty:
        return pd.DataFrame()
    return df.sort_values(["year", "quarter", "score"], ascending=[False, False, False]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def _load_overview_iconic_quotes_sheet(excel_path: str, source_stamp: int = 0) -> pd.DataFrame:
    if not excel_path:
        return pd.DataFrame()
    raw, _sheet_used = _read_excel_sheet_flexible(
        excel_path=excel_path,
        source_stamp=source_stamp,
        preferred="Overview_Iconic_Quotes",
        aliases=[
            "Overview Iconic Quotes",
            "Earnings_Call_Highlights",
            "Overview_CEO_Highlights",
            "CEO_CFO_Highlights",
        ],
        contains_any=["iconic", "highlight", "ceo", "cfo", "quote"],
    )
    if raw.empty:
        return pd.DataFrame()
    return _normalize_iconic_quotes_df(raw)


@st.cache_data(show_spinner=False)
def _load_overview_iconic_quotes_csv() -> pd.DataFrame:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / "earningscall_transcripts" / "overview_iconic_quotes.csv",
        repo_root / "earningscall_transcripts" / "transcript_highlights.csv",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            raw = pd.read_csv(path)
        except Exception:
            continue
        df = _normalize_iconic_quotes_df(raw)
        if not df.empty:
            return df
    return pd.DataFrame()


def _render_iconic_quote_section(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
) -> bool:
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    sheet_df = _load_overview_iconic_quotes_sheet(excel_path, source_stamp) if excel_path else pd.DataFrame()
    csv_df = _load_overview_iconic_quotes_csv()
    quotes_df = sheet_df if not sheet_df.empty else csv_df
    if quotes_df.empty:
        return False

    scoped_df, selected_period = _pick_rows_for_period(quotes_df, selected_year, selected_quarter)
    if scoped_df.empty:
        return False
    scoped_df = scoped_df.sort_values(["score", "company", "speaker"], ascending=[False, True, True]).head(12)
    if scoped_df.empty:
        return False

    st.markdown("#### Iconic CEO/CFO Commentary")
    source_label = "Overview_Iconic_Quotes (sheet)" if not sheet_df.empty else "earningscall_transcripts/overview_iconic_quotes.csv"
    st.caption(f"Source: {source_label} · Period: {selected_period}")

    cards = []
    for row in scoped_df.itertuples(index=False):
        company = html.escape(str(getattr(row, "company", "") or "").strip())
        speaker = html.escape(str(getattr(row, "speaker", "") or "").strip() or "Unknown")
        role = html.escape(str(getattr(row, "role_bucket", "") or "").strip())
        quote = html.escape(str(getattr(row, "quote", "") or "").strip())
        score = getattr(row, "score", None)
        score_text = ""
        try:
            if score is not None and pd.notna(score):
                score_text = f" · Score {float(score):.2f}"
        except Exception:
            score_text = ""
        meta = f"{company} · {role} · {speaker}{score_text}" if role else f"{company} · {speaker}{score_text}"
        cards.append(
            f"""
            <div class="ov-quote-card">
                <div class="ov-quote-meta">{meta}</div>
                <p class="ov-quote-body">"{quote}"</p>
            </div>
            """
        )
    st.markdown(_html_block(f"<div class='ov-quote-grid'>{''.join(cards)}</div>"), unsafe_allow_html=True)
    return True


def _apply_year_window(df: pd.DataFrame, start_year: int, end_year: int, year_col: str = "Year") -> pd.DataFrame:
    if df is None:
        return pd.DataFrame(columns=[year_col])
    if df.empty:
        cols = list(df.columns)
        if year_col not in cols:
            cols.append(year_col)
        return pd.DataFrame(columns=cols)
    if year_col not in df.columns:
        cols = list(df.columns)
        cols.append(year_col)
        return pd.DataFrame(columns=cols)
    out = df.copy()
    out[year_col] = pd.to_numeric(out[year_col], errors="coerce")
    out = out.dropna(subset=[year_col]).copy()
    if out.empty:
        cols = list(out.columns)
        if year_col not in cols:
            cols.append(year_col)
        return pd.DataFrame(columns=cols)
    out[year_col] = out[year_col].astype(int)
    return out[(out[year_col] >= int(start_year)) & (out[year_col] <= int(end_year))].copy()


def _overview_legend_style() -> dict:
    return dict(
        orientation="h",
        yanchor="top",
        y=-0.16,
        x=0.0,
        xanchor="left",
        bgcolor="rgba(0,0,0,0)",
        borderwidth=0,
        font=dict(size=11),
    )


def _overview_chart_margin(left: int = 30, right: int = 20, bottom: int = 88, top: int = 94) -> dict:
    return dict(l=int(left), r=max(int(right), 34), t=max(int(top), 62), b=max(int(bottom), 108))


def _df_has_cols(df: pd.DataFrame | None, cols: list[str]) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and all(col in df.columns for col in cols)


def _render_macro_bridge_charts(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
    plotly_config: dict,
) -> bool:
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    st.markdown("<div id='section-macro-bridge'></div>", unsafe_allow_html=True)
    st.markdown("### Macro Regime Bridge Charts")
    if not excel_path:
        st.info("Workbook source is not available, so macro regime charts cannot load yet.")
        return False

    m2_df = _load_m2_yearly_df(excel_path, source_stamp)
    inflation_df = _load_inflation_yearly_df(excel_path, source_stamp)
    country_channel_df = _load_country_ad_channel_yearly_df(excel_path, source_stamp)
    metrics_df = _load_company_metrics_yearly_df(excel_path, source_stamp)
    employees_df = _load_employee_yearly_df(excel_path, source_stamp)
    ad_gdp_df = _load_global_ad_vs_gdp_df(excel_path, source_stamp)
    country_gdp_df = _load_country_totals_vs_gdp_df(excel_path, source_stamp)

    year_candidates = []
    for df in [m2_df, inflation_df, country_channel_df, metrics_df, employees_df, ad_gdp_df, country_gdp_df]:
        if df is not None and not df.empty:
            col = "Year" if "Year" in df.columns else ("year" if "year" in df.columns else None)
            if col:
                vals = pd.to_numeric(df[col], errors="coerce").dropna().astype(int).tolist()
                year_candidates.extend(vals)
    if not year_candidates:
        st.caption("Auto-rendered from workbook sheets.")
        st.info("No compatible yearly data was detected for Macro Regime Bridge Charts.")
        return False

    min_year = int(min(year_candidates))
    max_year = int(max(year_candidates))
    start_year, end_year = min_year, max_year

    old_media = {"Comcast", "Disney", "Warner Bros. Discovery", "Paramount Global", "MFE"}
    tech_media = {"Alphabet", "Amazon", "Apple", "Meta Platforms", "Microsoft", "Netflix", "Roku", "Spotify"}
    ad_totals_df = (
        country_channel_df[["Year", "TotalAdvertising_BUSD"]]
        .dropna()
        .drop_duplicates(subset=["Year"])
        .sort_values("Year")
        if not country_channel_df.empty
        else pd.DataFrame()
    )

    st.caption(f"Auto-rendered from workbook sheets ({start_year}-{end_year}).")

    # 1) M2 vs Big Tech Aggregate Market Cap
    title = "M2 vs Big Tech Aggregate Market Cap"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    m2 = _apply_year_window(m2_df, start_year, end_year)
    if _df_has_cols(m2, ["Year", "M2_B"]) and _df_has_cols(metrics_df, ["Year", "Company", "MarketCap"]):
        mcap = _apply_year_window(metrics_df, start_year, end_year)
        if not _df_has_cols(mcap, ["Year", "Company", "MarketCap"]):
            mcap = pd.DataFrame(columns=["Year", "Company", "MarketCap"])
        mcap = mcap[mcap["Company"].isin(tech_media)].copy()
        mcap = mcap.groupby("Year", as_index=False)["MarketCap"].sum(min_count=1)
        mcap["Tech_MarketCap_B"] = mcap["MarketCap"] / 1000.0
        merged = m2.merge(mcap[["Year", "Tech_MarketCap_B"]], on="Year", how="inner").sort_values("Year")
    else:
        merged = pd.DataFrame()
    if merged.empty:
        st.info("Not enough M2/market-cap series to build this chart.")
    else:
        merged["M2_YoY"] = merged["M2_B"].pct_change() * 100.0
        merged["TechCap_YoY"] = merged["Tech_MarketCap_B"].pct_change() * 100.0
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=merged["Year"], y=merged["M2_B"], mode="lines+markers", name="US M2 (B USD)", line=dict(color="#0EA5E9", width=3)))
        fig.add_trace(go.Scatter(x=merged["Year"], y=merged["Tech_MarketCap_B"], mode="lines+markers", name="Big Tech Market Cap (B USD)", line=dict(color="#1D4ED8", width=3)))
        fig.add_trace(go.Scatter(x=merged["Year"], y=merged["M2_YoY"], mode="lines", name="M2 YoY %", line=dict(color="#0EA5E9", width=1.8, dash="dot"), yaxis="y2"))
        fig.add_trace(go.Scatter(x=merged["Year"], y=merged["TechCap_YoY"], mode="lines", name="Tech Cap YoY %", line=dict(color="#F97316", width=1.8, dash="dot"), yaxis="y2"))
        fig.update_layout(
            height=460,
            margin=_overview_chart_margin(left=30, right=34, top=104),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="USD billions"),
            yaxis2=dict(title="YoY %", overlaying="y", side="right", showgrid=False),
            legend=_overview_legend_style(),
        )
        fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment(title, selected_year)

    # 2) Inflation vs Advertising Spend Growth
    title = "Inflation vs Advertising Spend Growth"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    infl = _apply_year_window(inflation_df, start_year, end_year)
    ad = _apply_year_window(ad_totals_df, start_year, end_year)
    if not ad.empty:
        ad = ad.sort_values("Year").copy()
        ad["Ad_YoY"] = ad["TotalAdvertising_BUSD"].pct_change() * 100.0
        ad = ad[["Year", "Ad_YoY"]]
    merged = infl.merge(ad, on="Year", how="inner") if (not infl.empty and not ad.empty) else pd.DataFrame()
    if merged.empty:
        st.info("Not enough inflation/ad-spend data to build this chart.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=merged["Year"], y=merged["Inflation_YoY"], mode="lines+markers", name="Inflation YoY %", line=dict(color="#DC2626", width=3)))
        fig.add_trace(go.Scatter(x=merged["Year"], y=merged["Ad_YoY"], mode="lines+markers", name="Global Ad Spend YoY %", line=dict(color="#2563EB", width=3)))
        fig.update_layout(
            height=430,
            margin=_overview_chart_margin(),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="YoY %",
            legend=_overview_legend_style(),
        )
        fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
        fig.add_hline(y=0, line_dash="dot", line_color="rgba(15,23,42,0.5)")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment(title, selected_year)

    # 3) TV vs Internet vs OOH Migration
    title = "TV vs Internet vs Digital Migration"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    tvi = _apply_year_window(country_channel_df, start_year, end_year)
    if (not _df_has_cols(tvi, ["Year", "Channel", "AdSpend_BUSD"])) or tvi.empty:
        st.info("No country advertising channel time series available for this chart.")
    else:
        channels = tvi[tvi["Channel"].isin(["TV", "Internet", "OOH"])].copy()
        if channels.empty:
            st.info("TV/Internet/OOH channel coverage is missing in `Country_Advertising_Data_FullVi`.")
        else:
            channels["ChannelLabel"] = channels["Channel"].map(
                {"TV": "TV", "Internet": "Internet", "OOH": "OOH"}
            )
            fig = px.area(
                channels,
                x="Year",
                y="AdSpend_BUSD",
                color="ChannelLabel",
                color_discrete_map={"TV": "#F59E0B", "Internet": "#2563EB", "OOH": "#14B8A6"},
                labels={"AdSpend_BUSD": "USD billions", "ChannelLabel": "Channel"},
            )
            fig.update_layout(
                height=460,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis_title="USD billions",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment(title, selected_year)

    # 4) Industry Debt vs Industry Market Cap
    title = "Industry Debt vs Industry Market Cap"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    metrics = _apply_year_window(metrics_df, start_year, end_year)
    if not _df_has_cols(metrics, ["Year", "Company", "Debt", "MarketCap"]):
        st.info("No company metrics available for this chart.")
    else:
        old = metrics[metrics["Company"].isin(old_media)].groupby("Year", as_index=False)[["Debt", "MarketCap"]].sum(min_count=1)
        tech = metrics[metrics["Company"].isin(tech_media)].groupby("Year", as_index=False)[["Debt", "MarketCap"]].sum(min_count=1)
        comp = old.merge(tech, on="Year", how="outer", suffixes=("_old", "_tech")).sort_values("Year")
        comp["OldMedia_Debt_to_MCap"] = np.where(comp["MarketCap_old"] > 0, comp["Debt_old"] / comp["MarketCap_old"], np.nan)
        comp["Tech_Debt_to_MCap"] = np.where(comp["MarketCap_tech"] > 0, comp["Debt_tech"] / comp["MarketCap_tech"], np.nan)
        comp = comp.dropna(subset=["OldMedia_Debt_to_MCap", "Tech_Debt_to_MCap"], how="all")
        if comp.empty:
            st.info("Not enough debt/market-cap overlap for this chart.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=comp["Year"], y=comp["OldMedia_Debt_to_MCap"], mode="lines+markers", name="Old media debt / market cap", line=dict(color="#F97316", width=3)))
            fig.add_trace(go.Scatter(x=comp["Year"], y=comp["Tech_Debt_to_MCap"], mode="lines+markers", name="Tech debt / market cap", line=dict(color="#2563EB", width=3)))
            fig.update_layout(
                height=430,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis_title="Debt / Market Cap",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment(title, selected_year)

    # 5) Real M2 (Inflation-Adjusted)
    title = "Real M2 (Inflation-Adjusted)"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    m2 = _apply_year_window(m2_df, start_year, end_year)
    infl = _apply_year_window(inflation_df, start_year, end_year)
    merged = (
        m2.merge(infl, on="Year", how="inner").sort_values("Year")
        if _df_has_cols(m2, ["Year", "M2_B"]) and _df_has_cols(infl, ["Year", "Inflation_YoY"])
        else pd.DataFrame()
    )
    if merged.empty:
        st.info("Not enough M2 + inflation overlap for this chart.")
    else:
        merged["InflationFactor"] = 1.0 + (merged["Inflation_YoY"] / 100.0)
        merged["CPI_Index"] = merged["InflationFactor"].cumprod()
        base_index = merged["CPI_Index"].iloc[0] if merged["CPI_Index"].iloc[0] else 1.0
        merged["Real_M2_B"] = merged["M2_B"] / (merged["CPI_Index"] / base_index)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=merged["Year"], y=merged["M2_B"], mode="lines+markers", name="Nominal M2", line=dict(color="#0EA5E9", width=3)))
        fig.add_trace(go.Scatter(x=merged["Year"], y=merged["Real_M2_B"], mode="lines+markers", name="Real M2", line=dict(color="#1D4ED8", width=3)))
        fig.update_layout(
            height=430,
            margin=_overview_chart_margin(),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="USD billions",
            legend=_overview_legend_style(),
        )
        fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment(title, selected_year)

    # 6) Ad Spend as % of GDP
    title = "Ad Spend as % of GDP"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    adgdp = _apply_year_window(ad_gdp_df, start_year, end_year)
    if not _df_has_cols(adgdp, ["Year", "Ad_vs_GDP_pct"]):
        st.info("No global ad-vs-GDP data available for this chart.")
    else:
        fig = px.line(adgdp, x="Year", y="Ad_vs_GDP_pct", markers=True)
        fig.update_traces(line=dict(color="#2563EB", width=3))
        fig.update_layout(
            height=420,
            margin=dict(l=30, r=20, t=10, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="Ad spend / GDP (%)",
            showlegend=False,
        )
        fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment(title, selected_year)

    # 7) Revenue per Employee: Old Media vs Tech
    title = "Revenue per Employee: Old Media vs Tech"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    metrics = _apply_year_window(metrics_df, start_year, end_year)
    emps = _apply_year_window(employees_df, start_year, end_year)
    merged = (
        metrics.merge(emps, on=["Company", "Year"], how="inner")
        if _df_has_cols(metrics, ["Company", "Year", "Revenue"]) and _df_has_cols(emps, ["Company", "Year", "Employees"])
        else pd.DataFrame()
    )
    merged = merged[(merged["Employees"] > 0) & merged["Revenue"].notna()].copy() if not merged.empty else merged
    if merged is None or merged.empty:
        st.info("No revenue-per-employee overlap found.")
    else:
        merged["RevPerEmployee_MUSD"] = merged["Revenue"] / merged["Employees"]
        old = merged[merged["Company"].isin(old_media)].groupby("Year", as_index=False)["RevPerEmployee_MUSD"].median().rename(columns={"RevPerEmployee_MUSD": "Old Media"})
        tech = merged[merged["Company"].isin(tech_media)].groupby("Year", as_index=False)["RevPerEmployee_MUSD"].median().rename(columns={"RevPerEmployee_MUSD": "Tech"})
        plot_df = old.merge(tech, on="Year", how="outer").sort_values("Year")
        plot_long = plot_df.melt(id_vars="Year", value_vars=["Old Media", "Tech"], var_name="Cohort", value_name="Revenue per Employee (M USD)")
        plot_long = plot_long.dropna(subset=["Revenue per Employee (M USD)"])
        if plot_long.empty:
            st.info("Insufficient cohort coverage for this chart.")
        else:
            fig = px.line(
                plot_long,
                x="Year",
                y="Revenue per Employee (M USD)",
                color="Cohort",
                markers=True,
                color_discrete_map={"Old Media": "#F97316", "Tech": "#2563EB"},
            )
            fig.update_layout(
                height=430,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment(title, selected_year)

    # 8) Debt vs Inflation Regime
    title = "Debt vs Inflation Regime"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    metrics = _apply_year_window(metrics_df, start_year, end_year)
    infl = _apply_year_window(inflation_df, start_year, end_year)
    if (not _df_has_cols(metrics, ["Year", "Company", "Debt"])) or (not _df_has_cols(infl, ["Year", "Inflation_YoY"])):
        st.info("Need debt and inflation series for this chart.")
    else:
        old_debt = metrics[metrics["Company"].isin(old_media)].groupby("Year", as_index=False)["Debt"].sum(min_count=1)
        tech_debt = metrics[metrics["Company"].isin(tech_media)].groupby("Year", as_index=False)["Debt"].sum(min_count=1)
        plot_df = old_debt.merge(tech_debt, on="Year", how="outer", suffixes=("_old", "_tech"))
        plot_df = plot_df.merge(infl, on="Year", how="left").sort_values("Year")
        plot_df["Debt_old_B"] = plot_df["Debt_old"] / 1000.0
        plot_df["Debt_tech_B"] = plot_df["Debt_tech"] / 1000.0

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=plot_df["Year"], y=plot_df["Debt_old_B"], mode="lines+markers", name="Old media debt (B USD)", line=dict(color="#F97316", width=3)))
        fig.add_trace(go.Scatter(x=plot_df["Year"], y=plot_df["Debt_tech_B"], mode="lines+markers", name="Tech debt (B USD)", line=dict(color="#2563EB", width=3)))
        fig.add_trace(go.Scatter(x=plot_df["Year"], y=plot_df["Inflation_YoY"], mode="lines", name="Inflation YoY %", line=dict(color="#DC2626", width=1.8, dash="dot"), yaxis="y2"))
        fig.update_layout(
            height=450,
            margin=_overview_chart_margin(left=30, right=34, top=104),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="Debt (USD billions)"),
            yaxis2=dict(title="Inflation YoY %", overlaying="y", side="right", showgrid=False),
            legend=_overview_legend_style(),
        )
        fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment(title, selected_year)

    # 9) Market Cap Share Concentration
    title = "Market Cap Share Concentration"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    metrics = _apply_year_window(metrics_df, start_year, end_year)
    if not _df_has_cols(metrics, ["Year", "Company", "MarketCap"]):
        st.info("No market cap data available for concentration chart.")
    else:
        m = metrics.dropna(subset=["MarketCap"]).copy()
        if m.empty:
            st.info("No market cap observations available.")
        else:
            top_companies = (
                m.groupby("Company", as_index=False)["MarketCap"]
                .mean()
                .sort_values("MarketCap", ascending=False)
                .head(8)["Company"]
                .tolist()
            )
            yearly = m.groupby("Year", as_index=False)["MarketCap"].sum(min_count=1).rename(columns={"MarketCap": "TotalCap"})
            m = m.merge(yearly, on="Year", how="left")
            m["SharePct"] = np.where(m["TotalCap"] > 0, (m["MarketCap"] / m["TotalCap"]) * 100.0, np.nan)
            m["CompanyGroup"] = np.where(m["Company"].isin(top_companies), m["Company"], "Other")
            share = m.groupby(["Year", "CompanyGroup"], as_index=False)["SharePct"].sum(min_count=1)
            share = share.sort_values(["Year", "SharePct"], ascending=[True, False])
            fig = px.area(
                share,
                x="Year",
                y="SharePct",
                color="CompanyGroup",
                groupnorm=None,
            )
            fig.update_layout(
                height=480,
                margin=_overview_chart_margin(),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis_title="Share of total market cap (%)",
                legend=_overview_legend_style(),
            )
            fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment(title, selected_year)

    # 10) M2 vs Global Advertising Spend (Indexed)
    title = "M2 vs Global Advertising Spend (Indexed)"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    m2 = _apply_year_window(m2_df, start_year, end_year)
    ad = _apply_year_window(ad_totals_df, start_year, end_year)
    merged = (
        m2.merge(ad[["Year", "TotalAdvertising_BUSD"]], on="Year", how="inner")
        if _df_has_cols(m2, ["Year", "M2_B"]) and _df_has_cols(ad, ["Year", "TotalAdvertising_BUSD"])
        else pd.DataFrame()
    )
    if merged.empty:
        st.info("Not enough M2/ad-spend overlap for indexed chart.")
    else:
        first_m2 = merged["M2_B"].iloc[0] if merged["M2_B"].iloc[0] else np.nan
        first_ad = merged["TotalAdvertising_BUSD"].iloc[0] if merged["TotalAdvertising_BUSD"].iloc[0] else np.nan
        merged["M2_Index100"] = (merged["M2_B"] / first_m2) * 100.0
        merged["Ad_Index100"] = (merged["TotalAdvertising_BUSD"] / first_ad) * 100.0
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=merged["Year"], y=merged["M2_Index100"], mode="lines+markers", name="M2 indexed (base=100)", line=dict(color="#0EA5E9", width=3)))
        fig.add_trace(go.Scatter(x=merged["Year"], y=merged["Ad_Index100"], mode="lines+markers", name="Global ad spend indexed (base=100)", line=dict(color="#2563EB", width=3)))
        fig.update_layout(
            height=430,
            margin=_overview_chart_margin(),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="Index (base year = 100)",
            legend=_overview_legend_style(),
        )
        fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment(title, selected_year)

    # 11) Country Ad Spend vs GDP (bubble chart)
    title = "Country Ad Spend vs GDP (Bubble)"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    country_window = _apply_year_window(country_gdp_df, start_year, end_year)
    if not _df_has_cols(country_window, ["Year", "Country", "GDP_BUSD", "AdSpending_BUSD", "Ad_vs_GDP_pct"]):
        st.info("No country-level ad spend/GDP data found.")
    else:
        year_df = country_window[country_window["Year"] == int(selected_year)].copy()
        if year_df.empty:
            eligible = country_window[country_window["Year"] <= int(selected_year)]
            target_year = int(eligible["Year"].max()) if not eligible.empty else int(country_window["Year"].max())
            year_df = country_window[country_window["Year"] == target_year].copy()
        else:
            target_year = int(selected_year)
        year_df = year_df[(year_df["GDP_BUSD"] > 0) & (year_df["AdSpending_BUSD"] > 0)].copy()
        year_df = year_df.sort_values("AdSpending_BUSD", ascending=False).head(75)
        year_df["CountryCode"] = year_df["Country"].apply(_country_short_label)
        # Compress outliers and keep small countries visible.
        year_df["BubbleSize"] = np.log10((year_df["AdSpending_BUSD"] * 1_000.0).clip(lower=1.0))
        year_df["BubbleSize"] = year_df["BubbleSize"].clip(lower=0.7)
        label_color = "#F8FAFC" if get_theme_mode() == "dark" else "#0F172A"
        fig = px.scatter(
            year_df,
            x="GDP_BUSD",
            y="AdSpending_BUSD",
            size="BubbleSize",
            color="Ad_vs_GDP_pct",
            color_continuous_scale="Turbo",
            hover_name="Country",
            text="CountryCode",
            labels={
                "GDP_BUSD": "GDP (USD billions)",
                "AdSpending_BUSD": "Ad spend (USD billions)",
                "Ad_vs_GDP_pct": "Ad/GDP %",
            },
            log_x=True,
            log_y=True,
            size_max=74,
        )
        fig.update_traces(
            textposition="middle center",
            textfont=dict(size=10, color=label_color),
            marker=dict(opacity=0.92, line=dict(width=1, color="rgba(15,23,42,0.55)")),
            hovertemplate=(
                "<b>%{hovertext}</b>"
                "<br>GDP: %{x:,.0f}B USD"
                "<br>Ad Spend: %{y:,.2f}B USD"
                "<br>Ad/GDP: %{marker.color:.2f}%"
                "<extra></extra>"
            ),
        )
        fig.update_layout(
            height=500,
            margin=dict(l=30, r=20, t=10, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            coloraxis_colorbar=dict(title="Ad/GDP %"),
        )
        fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
        fig.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
        st.caption(f"Year shown: {target_year}")
    render_standard_overview_post_comment(title, selected_year)

    # 12) Country Ad Intensity Ranking
    title = "Country Ad Intensity Ranking (Ad Spend / GDP)"
    st.markdown(f"#### {title}")
    render_standard_overview_comment(title, selected_year)
    country_window = _apply_year_window(country_gdp_df, start_year, end_year)
    if not _df_has_cols(country_window, ["Year", "Country", "Ad_vs_GDP_pct"]):
        st.info("No country-level ad spend/GDP data found.")
    else:
        year_df = country_window[country_window["Year"] == int(selected_year)].copy()
        if year_df.empty:
            eligible = country_window[country_window["Year"] <= int(selected_year)]
            target_year = int(eligible["Year"].max()) if not eligible.empty else int(country_window["Year"].max())
            year_df = country_window[country_window["Year"] == target_year].copy()
        else:
            target_year = int(selected_year)
        rank_df = year_df.sort_values("Ad_vs_GDP_pct", ascending=False).head(20).sort_values("Ad_vs_GDP_pct", ascending=True)
        if rank_df.empty:
            st.info("No valid country ad-intensity rows for this year.")
        else:
            fig = px.bar(
                rank_df,
                x="Ad_vs_GDP_pct",
                y="Country",
                orientation="h",
                color="Ad_vs_GDP_pct",
                color_continuous_scale="Tealgrn",
                labels={"Ad_vs_GDP_pct": "Ad spend / GDP (%)", "Country": ""},
            )
            fig.update_layout(
                height=560,
                margin=dict(l=30, r=20, t=10, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
            )
            fig.update_xaxes(gridcolor="rgba(148,163,184,0.22)")
            st.plotly_chart(fig, use_container_width=True, config=plotly_config)
            st.caption(f"Year shown: {target_year}")
    render_standard_overview_post_comment(title, selected_year)

    return True


def _render_transcript_topic_growth_chart(
    selected_year: int,
    selected_quarter: str,
    plotly_config: dict,
) -> bool:
    metrics_df = _load_transcript_topic_metrics()
    if metrics_df.empty:
        return False

    scoped_df, selected_period = _pick_rows_for_period(metrics_df, selected_year, selected_quarter)
    if scoped_df.empty:
        return False
    scoped_df = scoped_df.sort_values("topic").copy()
    if scoped_df.empty:
        return False

    scoped_df["importance_pct"] = scoped_df["importance_pct"].fillna(0.0).clip(lower=0.0, upper=100.0)
    scoped_df["importance_plot"] = scoped_df["importance_pct"].clip(lower=0.1)
    scoped_df["growth_pct"] = scoped_df["growth_pct"].fillna(0.0).clip(lower=-100.0, upper=200.0)
    scoped_df["mention_count"] = scoped_df["mention_count"].fillna(0.0).clip(lower=0.0)
    scoped_df["companies_mentioned"] = scoped_df["companies_mentioned"].fillna(0.0)
    scoped_df["total_companies"] = scoped_df["total_companies"].fillna(0.0)
    label_cutoff = float(scoped_df["mention_count"].quantile(0.55)) if not scoped_df.empty else 0.0
    scoped_df["topic_label"] = np.where(scoped_df["mention_count"] >= max(label_cutoff, 1.0), scoped_df["topic"], "")

    mid_x = max(float(scoped_df["importance_plot"].median()), 1.0)
    mid_y = 0.0

    def classify_quadrant(row):
        high_x = row["importance_plot"] >= mid_x
        high_y = row["growth_pct"] >= mid_y
        if high_x and high_y:
            return "Big and growing"
        if (not high_x) and high_y:
            return "Small and growing"
        if high_x and (not high_y):
            return "Big and fading"
        return "Small and fading"

    scoped_df["quadrant"] = scoped_df.apply(classify_quadrant, axis=1)
    quadrant_colors = {
        "Big and growing": "#1D4ED8",
        "Small and growing": "#0EA5E9",
        "Big and fading": "#F97316",
        "Small and fading": "#94A3B8",
    }

    st.markdown("<div id='section-topic-signal'></div>", unsafe_allow_html=True)
    st.markdown("### Topic Signal Map")
    st.caption(
        f"Source: earningscall_transcripts/topic_metrics.csv · Period: {selected_period} · "
        f"{int(scoped_df['total_companies'].max()) if not scoped_df['total_companies'].isna().all() else 0} companies"
    )
    render_standard_overview_comment("Transcript Topic Growth vs Importance", selected_year)

    fig = px.scatter(
        scoped_df,
        x="importance_plot",
        y="growth_pct",
        size="mention_count",
        color="quadrant",
        color_discrete_map=quadrant_colors,
        text="topic_label",
        custom_data=["topic", "importance_pct", "growth_pct", "mention_count", "companies_mentioned", "total_companies"],
    )
    fig.update_traces(
        marker=dict(line=dict(color="rgba(15,23,42,0.18)", width=1)),
        textposition="top center",
        textfont=dict(size=12),
        hovertemplate=(
            "<b>%{customdata[0]}</b>"
            "<br>Importance: %{customdata[1]:.1f}% of companies"
            "<br>Growth vs prior quarter: %{customdata[2]:.1f}%"
            "<br>Mentions: %{customdata[3]:,.0f}"
            "<br>Companies mentioning: %{customdata[4]:,.0f} / %{customdata[5]:,.0f}"
            "<extra></extra>"
        ),
    )
    fig.update_layout(
        height=560,
        margin=_overview_chart_margin(left=20, right=20, top=106),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=_overview_legend_style(),
    )
    fig.update_xaxes(
        type="log",
        title="Keyword importance (% of tracked companies mentioning topic)",
        tickvals=[0.1, 0.5, 1, 2, 5, 10, 20, 50, 100],
        ticktext=["0.1%", "0.5%", "1%", "2%", "5%", "10%", "20%", "50%", "100%"],
        gridcolor="rgba(148,163,184,0.22)",
    )
    fig.update_yaxes(
        title="Keyword growth vs prior quarter (%)",
        range=[-100, 200],
        gridcolor="rgba(148,163,184,0.22)",
    )
    fig.add_hline(y=0, line_dash="dot", line_color="rgba(15,23,42,0.55)")
    fig.add_vline(x=mid_x, line_dash="dot", line_color="rgba(15,23,42,0.55)")

    st.plotly_chart(fig, use_container_width=True, config=plotly_config)
    ranked = scoped_df.sort_values(["mention_count", "importance_pct"], ascending=[False, False]).copy()
    ranked = ranked[["topic", "mention_count", "importance_pct", "growth_pct", "companies_mentioned", "total_companies"]]
    ranked = ranked.rename(
        columns={
            "topic": "Topic",
            "mention_count": "Mentions",
            "importance_pct": "Importance (%)",
            "growth_pct": "QoQ Growth (%)",
            "companies_mentioned": "Companies Mentioning",
            "total_companies": "Total Companies",
        }
    )
    st.caption("Top topic signals for this selected period")
    st.dataframe(
        ranked,
        use_container_width=True,
        hide_index=True,
    )
    render_standard_overview_post_comment("Transcript Topic Growth vs Importance", selected_year)
    return True


def _render_excel_overview_layers(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
    plotly_config: dict,
) -> None:
    st.markdown("---")
    macro_rendered = _render_excel_macro_section(data_processor, selected_year, selected_quarter)
    if not macro_rendered:
        st.info("No `Overview_Macro` row found for the selected period.")
    insights_rendered = _render_excel_overview_insights(data_processor, selected_year, selected_quarter)
    if not insights_rendered:
        st.info("No active `Overview_Insights` rows found for the selected period.")
    auto_insights_rendered = _render_generated_auto_insights(
        data_processor,
        selected_year,
        selected_quarter,
        plotly_config,
    )
    if not auto_insights_rendered:
        st.caption(
            "Auto-generated insights are unavailable. Run "
            "`python3 scripts/generate_insights.py --db earningscall_intelligence.db` "
            "after syncing transcript intelligence."
        )

    with st.expander("Expanded Macro Cross-Sheet Charts", expanded=True):
        macro_expansion_rendered = _render_macro_expansion_sections(
            data_processor,
            selected_year,
            selected_quarter,
            plotly_config,
        )
        if not macro_expansion_rendered:
            st.caption(
                "Expanded macro cross-sheet charts will auto-populate when matching rate/GDP/labor/currency fields "
                "exist in your Google Sheets tabs (name does not need to follow `Macro_*`)."
            )

    with st.expander("Company Financial Deep Dives", expanded=True):
        deep_dive_rendered = _render_company_financial_deep_dives(
            data_processor,
            selected_year,
            selected_quarter,
            plotly_config,
        )
        if not deep_dive_rendered:
            st.caption("Company deep-dive charts need annual company metrics (Revenue, Net Income, Debt, CapEx, R&D).")

    with st.expander("Macro Regime Bridge Charts", expanded=True):
        _render_macro_bridge_charts(data_processor, selected_year, selected_quarter, plotly_config)

    with st.expander("Device & Platform Market Share", expanded=True):
        device_rendered = _render_device_platform_market_share(data_processor, selected_year, plotly_config)
        if not device_rendered:
            st.caption(
                "Device/platform section auto-loads when `Hardware_Smartphone_Shipments` or "
                "`Country_Advertising_Data_FullVi` contains device-class fields."
            )

    topic_chart_rendered = _render_transcript_topic_growth_chart(selected_year, selected_quarter, plotly_config)
    if not topic_chart_rendered:
        st.info(
            "No transcript topic metrics found. Run `python3 scripts/extract_transcript_topics.py` "
            "after adding new quarter transcript files."
        )
    iconic_quotes_rendered = _render_iconic_quote_section(data_processor, selected_year, selected_quarter)
    if not iconic_quotes_rendered:
        st.caption(
            "No iconic CEO/CFO quote rows found for this period. Run "
            "`python3 scripts/sync_iconic_quotes_to_gsheet.py --upload-transcripts-first --extract-first` "
            "or populate `Overview_Iconic_Quotes` in the workbook."
        )


def _build_overview_export_payload(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
) -> dict:
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    payload: dict = {
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "selected_year": int(selected_year),
        "selected_quarter": str(selected_quarter),
        "source_path": str(excel_path or ""),
    }
    if not excel_path:
        return payload

    macro_df = _load_overview_macro_sheet(excel_path, source_stamp)
    insights_df = _load_overview_insights_sheet(excel_path, source_stamp)
    charts_df = _load_overview_charts_sheet(excel_path, source_stamp)

    macro_scoped, macro_period = _pick_rows_for_period(macro_df, selected_year, selected_quarter)
    insights_scoped, insights_period = _pick_rows_for_period(insights_df, selected_year, selected_quarter)
    charts_scoped, charts_period = _pick_rows_for_period(charts_df, selected_year, selected_quarter)

    if not insights_scoped.empty and "is_active" in insights_scoped.columns:
        insights_scoped = insights_scoped[insights_scoped["is_active"].fillna(0).astype(int) == 1].copy()

    payload["overview_macro_period"] = macro_period
    payload["overview_macro_rows"] = macro_scoped.fillna("").to_dict(orient="records") if not macro_scoped.empty else []
    payload["overview_insights_period"] = insights_period
    payload["overview_insights_rows"] = (
        insights_scoped.fillna("").to_dict(orient="records") if not insights_scoped.empty else []
    )
    payload["overview_charts_period"] = charts_period
    payload["overview_chart_comment_rows"] = (
        charts_scoped.fillna("").to_dict(orient="records") if not charts_scoped.empty else []
    )
    return payload


def _render_overview_download_section(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
) -> None:
    st.markdown("### Export Overview")
    st.caption("Download the currently filtered overview as a full-page HTML snapshot or as structured JSON data.")

    payload = _build_overview_export_payload(data_processor, selected_year, selected_quarter)
    payload_bytes = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    st.download_button(
        "Download Current View Data (JSON)",
        data=payload_bytes,
        file_name=f"overview_snapshot_{int(selected_year)}_{str(selected_quarter).lower()}.json",
        mime="application/json",
        key=f"overview_export_json_{int(selected_year)}_{str(selected_quarter)}",
    )

    button_id = f"ov-download-html-{int(selected_year)}-{str(selected_quarter).lower()}".replace(" ", "-")
    components.html(
        _html_block(
            f"""
            <div style="display:flex;align-items:center;gap:8px;">
              <button id="{button_id}" style="
                background:#1D4ED8;color:#fff;border:none;border-radius:8px;
                padding:8px 12px;font-size:13px;font-weight:600;cursor:pointer;">
                Download Current Page (HTML Snapshot)
              </button>
              <span style="font-size:12px;color:#64748B;">
                Includes all content currently rendered for Year {int(selected_year)} · {html.escape(str(selected_quarter))}
              </span>
            </div>
            <script>
            (function() {{
              const btn = document.getElementById("{button_id}");
              if (!btn || btn.dataset.bound === "1") return;
              btn.dataset.bound = "1";
              btn.addEventListener("click", function() {{
                try {{
                  const parentDoc = window.parent.document;
                  const htmlText = "<!doctype html>\\n" + parentDoc.documentElement.outerHTML;
                  const blob = new Blob([htmlText], {{ type: "text/html;charset=utf-8" }});
                  const url = URL.createObjectURL(blob);
                  const a = parentDoc.createElement("a");
                  a.href = url;
                  a.download = "overview_snapshot_{int(selected_year)}_{str(selected_quarter).lower()}.html";
                  parentDoc.body.appendChild(a);
                  a.click();
                  parentDoc.body.removeChild(a);
                  URL.revokeObjectURL(url);
                }} catch (err) {{
                  console.error("Overview HTML export failed", err);
                }}
              }});
            }})();
            </script>
            """
        ),
        height=64,
    )


def _render_quarterly_intelligence_briefing(
    data_processor: FinancialDataProcessor,
    selected_year: int,
    selected_quarter: str,
    plotly_config: dict,
) -> None:
    st.markdown("---")
    st.subheader("Global Media & Tech Intelligence Briefing")
    st.caption("24 Quarterly Overview Bullet Points + Validation Charts + Dashboard Architecture")
    st.caption("2010-2024 | 12 Companies | 33 Data Sheets")
    st.markdown(
        "This section mirrors your briefing structure and is wired to Excel-backed updates. "
        "It sits directly after the global map so users move from geography to narrative and then to validation charts."
    )

    st.markdown("### Quarterly Overview Insights (24 Bullet Points)")
    insights_rendered = _render_excel_overview_insights(data_processor, selected_year, selected_quarter)
    if not insights_rendered:
        st.info(
            "No `Overview insights` sheet was detected yet. Add that sheet in the workbook to drive these comments "
            "by company and quarter directly from Excel."
        )

    st.markdown("#### Correlation Validation Charts (Part 1)")
    rendered_part1_charts = 0
    try:
        if getattr(data_processor, "df_ad_revenue", None) is None or data_processor.df_ad_revenue.empty:
            data_processor._load_ad_revenue()
    except Exception:
        pass
    ad_df = getattr(data_processor, "df_ad_revenue", None)
    excel_path = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    groupm_granular = _load_groupm_granular_df(excel_path, source_stamp)

    if ad_df is not None and not ad_df.empty and not groupm_granular.empty:
        ad_frame = ad_df.copy()
        ad_frame.columns = [str(c).strip() for c in ad_frame.columns]
        if "year" in ad_frame.columns and "Year" not in ad_frame.columns:
            ad_frame = ad_frame.rename(columns={"year": "Year"})
        required_cols = {"Year", "Google_Ads", "Meta_Ads", "Amazon_Ads"}
        if required_cols.issubset(ad_frame.columns):
            share_df = ad_frame[["Year", "Google_Ads", "Meta_Ads", "Amazon_Ads"]].copy()
            share_df["Year"] = _coerce_numeric(share_df["Year"])
            share_df["Google_Ads"] = _coerce_numeric(share_df["Google_Ads"])
            share_df["Meta_Ads"] = _coerce_numeric(share_df["Meta_Ads"])
            share_df["Amazon_Ads"] = _coerce_numeric(share_df["Amazon_Ads"])
            share_df = share_df.dropna(subset=["Year"]).copy()
            share_df["Year"] = share_df["Year"].astype(int)
            share_df = share_df[(share_df["Year"] >= 2010) & (share_df["Year"] <= 2024)]
            global_totals = groupm_granular[["Year", "Total Advertising"]].copy()
            global_totals["Global_Ad_B"] = global_totals["Total Advertising"] / 1000.0
            duopoly_df = share_df.merge(global_totals[["Year", "Global_Ad_B"]], on="Year", how="inner")
            duopoly_df = duopoly_df[duopoly_df["Global_Ad_B"] > 0]
            duopoly_df["Duopoly_Share"] = (
                (duopoly_df["Google_Ads"] + duopoly_df["Meta_Ads"]) / duopoly_df["Global_Ad_B"] * 100.0
            )
            duopoly_df["Amazon_Share"] = duopoly_df["Amazon_Ads"] / duopoly_df["Global_Ad_B"] * 100.0
            if not duopoly_df.empty:
                fig_duopoly = go.Figure()
                fig_duopoly.add_trace(
                    go.Scatter(
                        x=duopoly_df["Year"],
                        y=duopoly_df["Duopoly_Share"],
                        mode="lines+markers",
                        name="Google + Meta share",
                        line=dict(color="#2563EB", width=3),
                    )
                )
                fig_duopoly.add_trace(
                    go.Scatter(
                        x=duopoly_df["Year"],
                        y=duopoly_df["Amazon_Share"],
                        mode="lines+markers",
                        name="Amazon share",
                        line=dict(color="#F59E0B", width=2.5),
                    )
                )
                fig_duopoly.update_layout(
                    height=340,
                    margin=_overview_chart_margin(left=40, right=20, top=92, bottom=96),
                    yaxis_title="% of global advertising spend",
                    xaxis_title="Year",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=_overview_legend_style(),
                )
                fig_duopoly.update_yaxes(gridcolor="rgba(148,163,184,0.25)")
                st.plotly_chart(fig_duopoly, use_container_width=True, config=plotly_config)
                rendered_part1_charts += 1

    if not groupm_granular.empty:
        tv_net_df = groupm_granular.copy()
        tv_net_df = tv_net_df[(tv_net_df["Year"] >= 2010) & (tv_net_df["Year"] <= 2024)].copy()
        tv_net_df["TV_B"] = tv_net_df["TV / Pro Video"] / 1000.0
        tv_net_df["Internet_B"] = tv_net_df["Internet"] / 1000.0
        tv_net_long = tv_net_df.melt(
            id_vars="Year",
            value_vars=["TV_B", "Internet_B"],
            var_name="Channel",
            value_name="USD Billions",
        )
        tv_net_long["Channel"] = tv_net_long["Channel"].map(
            {"TV_B": "TV / Pro Video", "Internet_B": "Internet"}
        )
        fig_tv = px.line(
            tv_net_long,
            x="Year",
            y="USD Billions",
            color="Channel",
            markers=True,
            color_discrete_map={"TV / Pro Video": "#F59E0B", "Internet": "#2563EB"},
        )
        fig_tv.update_layout(
            height=360,
            margin=_overview_chart_margin(left=40, right=20, top=92, bottom=96),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=_overview_legend_style(),
            yaxis_title="Ad spend (USD billions)",
        )
        fig_tv.update_yaxes(gridcolor="rgba(148,163,184,0.25)")
        st.plotly_chart(fig_tv, use_container_width=True, config=plotly_config)
        rendered_part1_charts += 1

    metrics_df = getattr(data_processor, "df_metrics", None)
    employees_df = getattr(data_processor, "df_employees", None)
    if metrics_df is not None and not metrics_df.empty and employees_df is not None and not employees_df.empty:
        ratio_df = metrics_df[["company", "year", "market_cap", "debt"]].merge(
            employees_df[["company", "year", "employees"]],
            on=["company", "year"],
            how="inner",
        )
        ratio_df["market_cap"] = pd.to_numeric(ratio_df["market_cap"], errors="coerce")
        ratio_df["employees"] = pd.to_numeric(ratio_df["employees"], errors="coerce")
        ratio_df["debt"] = pd.to_numeric(ratio_df["debt"], errors="coerce")
        ratio_df = ratio_df.dropna(subset=["year", "market_cap", "employees"])
        ratio_df = ratio_df[ratio_df["employees"] > 0]
        ratio_df["mcap_per_employee_m"] = ratio_df["market_cap"] / ratio_df["employees"]

        focus_eff = ["Microsoft", "Netflix", "Apple", "Alphabet", "Meta Platforms"]
        eff = ratio_df[ratio_df["company"].isin(focus_eff)].copy()
        if not eff.empty:
            pre = (
                eff[(eff["year"] >= 2010) & (eff["year"] <= 2014)]
                .groupby("company", as_index=False)["mcap_per_employee_m"]
                .mean()
                .rename(columns={"mcap_per_employee_m": "pre_period"})
            )
            post = (
                eff[(eff["year"] >= 2020) & (eff["year"] <= 2024)]
                .groupby("company", as_index=False)["mcap_per_employee_m"]
                .mean()
                .rename(columns={"mcap_per_employee_m": "post_period"})
            )
            mult = pre.merge(post, on="company", how="inner")
            mult["Multiplier"] = np.where(mult["pre_period"] > 0, mult["post_period"] / mult["pre_period"], np.nan)
            mult = mult.dropna(subset=["Multiplier"]).sort_values("Multiplier", ascending=True)
            if not mult.empty:
                fig_mult = px.bar(
                    mult,
                    x="Multiplier",
                    y="company",
                    orientation="h",
                    text="Multiplier",
                    color="Multiplier",
                    color_continuous_scale="Blues",
                )
                fig_mult.update_traces(texttemplate="%{text:.2f}x", textposition="outside")
                fig_mult.update_layout(
                    height=330,
                    margin=dict(l=40, r=20, t=20, b=40),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    coloraxis_showscale=False,
                    xaxis_title="Market-cap-per-employee multiplier (2020-2024 vs 2010-2014)",
                    yaxis_title="",
                )
                st.plotly_chart(fig_mult, use_container_width=True, config=plotly_config)
                rendered_part1_charts += 1

        focus_leverage = ["Comcast", "Disney", "Alphabet", "Meta Platforms"]
        lev_rows = []
        for comp in focus_leverage:
            comp_df = ratio_df[(ratio_df["company"] == comp) & (ratio_df["year"] <= int(selected_year))].copy()
            if comp_df.empty:
                continue
            latest = comp_df.sort_values("year").iloc[-1]
            if pd.notna(latest["market_cap"]) and latest["market_cap"] and pd.notna(latest["debt"]):
                lev_rows.append(
                    {
                        "Company": comp,
                        "Debt / Market Cap": float(latest["debt"]) / float(latest["market_cap"]),
                    }
                )
        lev_df = pd.DataFrame(lev_rows).sort_values("Debt / Market Cap", ascending=True) if lev_rows else pd.DataFrame()
        if not lev_df.empty:
            fig_lev = px.bar(
                lev_df,
                x="Debt / Market Cap",
                y="Company",
                orientation="h",
                text="Debt / Market Cap",
                color="Debt / Market Cap",
                color_continuous_scale="Oranges",
            )
            fig_lev.update_traces(texttemplate="%{text:.3f}", textposition="outside")
            fig_lev.update_layout(
                height=300,
                margin=dict(l=40, r=20, t=20, b=40),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
                xaxis_title=f"Debt-to-market-cap ratio (latest <= {selected_year})",
                yaxis_title="",
            )
            st.plotly_chart(fig_lev, use_container_width=True, config=plotly_config)
            rendered_part1_charts += 1

    if rendered_part1_charts == 0:
        st.info(
            "No Part 1 chart inputs were found with the current workbook fields. "
            "Showing fallback validation from core company metrics."
        )
        if metrics_df is not None and not metrics_df.empty:
            fallback = metrics_df[["year", "market_cap", "revenue"]].copy()
            fallback["year"] = _coerce_numeric(fallback["year"])
            fallback["market_cap"] = _coerce_numeric(fallback["market_cap"])
            fallback["revenue"] = _coerce_numeric(fallback["revenue"])
            fallback = fallback.dropna(subset=["year"]).copy()
            fallback["year"] = fallback["year"].astype(int)
            fallback = fallback[(fallback["year"] >= 2010) & (fallback["year"] <= 2024)]
            if not fallback.empty:
                fallback_year = (
                    fallback.groupby("year", as_index=False)[["market_cap", "revenue"]]
                    .sum(min_count=1)
                    .dropna(subset=["market_cap", "revenue"], how="all")
                )
                if not fallback_year.empty:
                    fallback_year["market_cap_t"] = fallback_year["market_cap"] / 1_000_000.0
                    fallback_year["revenue_t"] = fallback_year["revenue"] / 1_000_000.0
                    fig_fallback = go.Figure()
                    fig_fallback.add_trace(
                        go.Scatter(
                            x=fallback_year["year"],
                            y=fallback_year["market_cap_t"],
                            mode="lines+markers",
                            name="Aggregate market cap (T USD)",
                            line=dict(color="#2563EB", width=3),
                        )
                    )
                    fig_fallback.add_trace(
                        go.Scatter(
                            x=fallback_year["year"],
                            y=fallback_year["revenue_t"],
                            mode="lines+markers",
                            name="Aggregate revenue (T USD)",
                            line=dict(color="#F59E0B", width=3),
                        )
                    )
                    fig_fallback.update_layout(
                        height=360,
                        margin=_overview_chart_margin(left=40, right=20, top=92, bottom=96),
                        xaxis_title="Year",
                        yaxis_title="USD trillions",
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        legend=_overview_legend_style(),
                    )
                    fig_fallback.update_yaxes(gridcolor="rgba(148,163,184,0.25)")
                    st.plotly_chart(fig_fallback, use_container_width=True, config=plotly_config)
                    rendered_part1_charts += 1
        if rendered_part1_charts == 0:
            st.warning(
                "Charts could not be rendered because required numeric series were not detected in the workbook."
            )

    return


_OVERVIEW_AREA_CONFIG = [
    {
        "key": "macro_snapshot",
        "title": "Macro Snapshot",
        "description": "Top macro KPIs, liquidity, and regime context.",
    },
    {
        "key": "global_media_map",
        "title": "Global Media Economy",
        "description": "Interactive world map and country-level ad structure.",
    },
    {
        "key": "insights",
        "title": "Insights by Category",
        "description": "Quarterly overview commentary from workbook + auto insights.",
    },
    {
        "key": "macro_regime",
        "title": "Macro Regime Charts",
        "description": "Cross-sheet macro bridge and regime diagnostics.",
    },
    {
        "key": "deep_dives",
        "title": "Company Deep Dives",
        "description": "P/E, debt, margins, R&D, efficiency and concentration.",
    },
    {
        "key": "device_platform",
        "title": "Device & Platform",
        "description": "Smartphone share and device-linked ad migration.",
    },
    {
        "key": "topic_signal",
        "title": "Topic Signal & Quotes",
        "description": "Transcript topic map plus iconic CEO/CFO commentary.",
    },
    {
        "key": "export",
        "title": "Export",
        "description": "Download current filtered overview payload and HTML snapshot.",
    },
]


def _render_overview_area_selector() -> str:
    st.markdown(
        _html_block(
            """
            <style>
            .ov-nav-card {
              border: 1px solid rgba(15,23,42,0.10);
              border-radius: 14px;
              padding: 16px 14px 14px 14px;
              background: rgba(255,255,255,0.96);
              box-shadow: 0 4px 12px rgba(15,23,42,0.07);
              cursor: pointer;
              transition: box-shadow 0.15s ease, transform 0.15s ease;
              text-align: left;
              margin-bottom: 4px;
            }
            .ov-nav-card:hover {
              box-shadow: 0 8px 24px rgba(37,99,235,0.14);
              transform: translateY(-2px);
            }
            .ov-nav-card.active {
              border-left: 4px solid #2563EB;
              background: rgba(239,246,255,0.98);
            }
            .ov-nav-icon { font-size: 1.4rem; margin-bottom: 6px; }
            .ov-nav-label { font-size: 1.0rem; font-weight: 700; color: #0F172A; }
            .ov-nav-sub { font-size: 0.82rem; color: #64748B; margin-top: 4px; line-height: 1.45; }
            body.theme-dark .ov-nav-card { background: #1E293B; border-color: rgba(255,255,255,0.08); }
            body.theme-dark .ov-nav-label { color: #E2E8F0; }
            body.theme-dark .ov-nav-sub { color: #94A3B8; }
            body.theme-dark .ov-nav-card.active { background: rgba(37,99,235,0.15); border-left-color: #60A5FA; }
            .ov-nav-link {
              text-decoration: none !important;
              color: inherit !important;
              display: block;
            }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )
    st.markdown("### Overview Navigator")
    st.caption("Choose one of the 8 sections below. Only that section is rendered to keep focus and reduce lag.")

    valid_keys = {item["key"] for item in _OVERVIEW_AREA_CONFIG}
    active_key = st.session_state.get("overview_active_area", "macro_snapshot")
    if active_key not in valid_keys:
        active_key = "macro_snapshot"
    query_params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
    query_area = query_params.get("ov_area") if query_params else None
    if isinstance(query_area, list):
        query_area = query_area[0] if query_area else None
    query_area = str(query_area or "").strip()
    if query_area in valid_keys:
        active_key = query_area

    icon_map = {
        "global_media_map": "🌍",
        "macro_snapshot": "📉",
        "insights": "🧠",
        "macro_regime": "🧭",
        "deep_dives": "🏢",
        "device_platform": "📱",
        "topic_signal": "🗣️",
        "export": "📦",
    }
    per_row = 4
    for row_start in range(0, len(_OVERVIEW_AREA_CONFIG), per_row):
        row_items = _OVERVIEW_AREA_CONFIG[row_start: row_start + per_row]
        row_cols = st.columns(len(row_items))
        for col, item in zip(row_cols, row_items):
            with col:
                is_active = active_key == item["key"]
                active_class = "active" if is_active else ""
                section_id = str(item["key"])
                section_href = f"?nav=overview&ov_area={quote_plus(section_id)}"
                st.markdown(
                    _html_block(
                        f"""
                        <a class='ov-nav-link' href='{section_href}' target='_self' rel='noopener'>
                          <div class='ov-nav-card {active_class}' id='nav-{html.escape(section_id)}'>
                            <div class='ov-nav-icon'>{icon_map.get(item['key'], '•')}</div>
                            <div class='ov-nav-label'>{html.escape(item['title'])}</div>
                            <div class='ov-nav-sub'>{html.escape(item['description'])}</div>
                          </div>
                        </a>
                        """
                    ),
                    unsafe_allow_html=True,
                )

    st.session_state["overview_active_area"] = active_key
    return active_key


# Configure Plotly
plotly_config = {
    'displayModeBar': 'hover',
    'modeBarButtonsToRemove': [
        'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d',
        'autoScale2d', 'resetScale2d', 'hoverClosestCartesian', 'hoverCompareCartesian',
        'toggleSpikelines', 'resetGeo', 'zoomInGeo', 'zoomOutGeo'
    ],
    'displaylogo': False,
    'toImageButtonOptions': {
        'format': 'png',
        'filename': 'overview_chart',
        'scale': 4
    }
}

begin_snap_section("overview_summary")

# Main app content
st.title("Advertising Demand & Competitive Context")
_render_overview_hero_banner()

# Initialize data processor
data_processor = get_data_processor()

# Get companies and available years
companies = get_available_companies(data_processor)
available_years = get_available_years(data_processor)
if not available_years:
    # Avoid showing an empty/future-only selector when data source fails to hydrate.
    available_years = [max(2010, int(datetime.now().year) - 1)]
excel_path = getattr(data_processor, "data_path", "")

# Year + quarter + granularity selectors
year_col, quarter_col, gran_col = st.columns([1.0, 1.0, 1.0])
with year_col:
    selected_year = st.selectbox(
        "Select Year",
        available_years,
        index=len(available_years)-1  # Default to most recent year
    )
with quarter_col:
    quarter_options = get_quarter_labels_for_year(excel_path, int(selected_year))
    if not quarter_options:
        quarter_options = ["Q1", "Q2", "Q3", "Q4"]
    current_q = st.session_state.get("overview_selected_quarter", quarter_options[-1])
    if current_q not in quarter_options:
        current_q = quarter_options[-1]
    selected_quarter = st.selectbox(
        "Select Quarter",
        quarter_options,
        index=quarter_options.index(current_q),
        key="overview_selected_quarter",
        help="Used by Excel-backed overview comments (quarterly/yearly).",
    )
st.session_state["selected_year"] = int(selected_year)
st.session_state["selected_quarter"] = str(selected_quarter)
with gran_col:
    granularity_options = _get_overview_granularity_options(data_processor)
    current_granularity = st.session_state.get("overview_selected_granularity", "Auto")
    if current_granularity not in granularity_options:
        current_granularity = granularity_options[0] if granularity_options else "Auto"
    selected_granularity = st.selectbox(
        "Data Granularity",
        granularity_options,
        index=granularity_options.index(current_granularity),
        key="overview_selected_granularity",
        help="Auto uses each chart's native frequency. Annual/Quarterly/Monthly/Daily enables extra period controls when data exists.",
    )

ux_col1, ux_col2 = st.columns([1.0, 2.0])
with ux_col1:
    chart_export_format = st.selectbox(
        "Chart Export Format",
        ["png", "svg"],
        index=0,
        key="overview_chart_export_format",
        help="Controls Plotly per-chart download format from the modebar.",
    )
with ux_col2:
    st.markdown("Use the navigator buttons below to open one overview section at a time.")

selected_overview_area = _render_overview_area_selector()

selected_month = None
selected_day = None
if selected_granularity == "Monthly":
    month_labels = get_month_labels_for_year(excel_path, int(selected_year))
    if month_labels:
        current_month = st.session_state.get("overview_selected_month", month_labels[-1])
        if current_month not in month_labels:
            current_month = month_labels[-1]
        selected_month = st.selectbox(
            "Select Month",
            month_labels,
            index=month_labels.index(current_month),
            key="overview_selected_month",
            help="Monthly controls are available for datasets that provide monthly time series.",
        )
    else:
        st.caption("No monthly rows available for this selected year.")
elif selected_granularity == "Daily":
    day_labels = get_day_labels_for_year(excel_path, int(selected_year))
    if day_labels:
        current_day = st.session_state.get("overview_selected_day", day_labels[-1])
        if current_day not in day_labels:
            current_day = day_labels[-1]
        selected_day = st.selectbox(
            "Select Day",
            day_labels,
            index=day_labels.index(current_day),
            key="overview_selected_day",
            help="Daily controls are available for datasets with daily observations.",
        )
    else:
        st.caption("No daily rows available for this selected year.")

st.session_state["overview_time_context"] = update_global_time_context(
    page="Overview",
    granularity=selected_granularity,
    year=int(selected_year),
    quarter=selected_quarter,
    month=selected_month,
    day=selected_day,
    year_range=(int(selected_year), int(selected_year)),
    excel_path=excel_path,
)

plotly_config["toImageButtonOptions"]["format"] = chart_export_format

# Sticky summary (period-aware, updates with filters).
with st.expander("Key Insights Summary", expanded=False):
    st.caption(f"Period: {int(selected_year)} · {selected_quarter}")
    excel_source = getattr(data_processor, "data_path", "")
    source_stamp = int(getattr(data_processor, "source_stamp", 0) or 0)
    if excel_source:
        macro_sidebar_df = _load_overview_macro_sheet(excel_source, source_stamp)
        insights_sidebar_df = _load_overview_insights_sheet(excel_source, source_stamp)
        macro_scope, _ = _pick_rows_for_period(macro_sidebar_df, int(selected_year), selected_quarter)
        insights_scope, _ = _pick_rows_for_period(insights_sidebar_df, int(selected_year), selected_quarter)
        if not insights_scope.empty and "is_active" in insights_scope.columns:
            insights_scope = insights_scope[insights_scope["is_active"].fillna(0).astype(int) == 1]

        if not macro_scope.empty:
            row = macro_scope.sort_values(["year", "_quarter_num"], ascending=[False, False]).iloc[0]
            st.metric("Global Ad Market", _format_macro_metric(row.get("global_ad_market"), "B"))
            st.metric("Duopoly Share", _format_macro_metric(row.get("duopoly_share"), "%"))
        if not insights_scope.empty:
            st.metric("Active Insights", f"{len(insights_scope)}")
            top_cats = (
                insights_scope["category"].astype(str).str.strip().value_counts().head(3).to_dict()
                if "category" in insights_scope.columns
                else {}
            )
            if top_cats:
                st.caption(
                    "Top categories: "
                    + " · ".join([f"{k}: {v}" for k, v in top_cats.items()])
                )
        else:
            st.caption("No active Overview insights found for this period.")

render_ai_assistant(location="sidebar", current_page="Overview")

st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

if selected_overview_area == "macro_snapshot":
    macro_kpi_rendered = render_macro_kpi_panel(data_processor, selected_year, selected_quarter, plotly_config)
    if not macro_kpi_rendered:
        st.caption(
            "Macro KPI panel is ready and will auto-populate when M2, GroupM, ad-revenue, and company-metrics inputs are available."
        )

    macro_context_rendered = _render_macro_context_dashboard(data_processor, selected_year, selected_quarter)
    if not macro_context_rendered:
        st.caption(
            "Macro context dashboard is ready and connected. It auto-reads whichever tabs contain "
            "matching rate/labor/currency/valuation fields (no strict sheet naming required)."
        )
    # Avoid duplicating KPI blocks: macro baseline table remains available under Export.
    _render_overview_download_section(data_processor, selected_year, selected_quarter)
    end_snap_section()
    st.stop()

if selected_overview_area == "insights":
    insights_rendered = _render_excel_overview_insights(data_processor, selected_year, selected_quarter)
    auto_rendered = _render_generated_auto_insights(
        data_processor,
        selected_year,
        selected_quarter,
        plotly_config,
    )
    if not insights_rendered:
        st.info("No active `Overview_Insights` rows found for the selected period.")
    if not auto_rendered:
        st.caption(
            "Auto-generated insights are unavailable. Run "
            "`python3 scripts/generate_insights.py --db earningscall_intelligence.db`."
        )
    _render_overview_download_section(data_processor, selected_year, selected_quarter)
    end_snap_section()
    st.stop()

if selected_overview_area == "macro_regime":
    macro_expansion_rendered = _render_macro_expansion_sections(
        data_processor,
        selected_year,
        selected_quarter,
        plotly_config,
    )
    if not macro_expansion_rendered:
        st.caption(
            "Expanded macro cross-sheet charts will auto-populate when matching macro fields exist in your workbook."
        )
    macro_bridge_rendered = _render_macro_bridge_charts(data_processor, selected_year, selected_quarter, plotly_config)
    if not macro_bridge_rendered:
        st.info("Macro bridge charts are unavailable because required source sheets are missing.")
    _render_overview_download_section(data_processor, selected_year, selected_quarter)
    end_snap_section()
    st.stop()

if selected_overview_area == "deep_dives":
    deep_dive_rendered = _render_company_financial_deep_dives(
        data_processor,
        selected_year,
        selected_quarter,
        plotly_config,
    )
    if not deep_dive_rendered:
        st.info("Company deep-dive charts need annual company metrics (Revenue, Net Income, Debt, CapEx, R&D).")
    _render_overview_download_section(data_processor, selected_year, selected_quarter)
    end_snap_section()
    st.stop()

if selected_overview_area == "device_platform":
    device_rendered = _render_device_platform_market_share(data_processor, selected_year, plotly_config)
    if not device_rendered:
        st.info(
            "Device/platform section auto-loads when `Hardware_Smartphone_Shipments` or "
            "`Country_Advertising_Data_FullVi` contains device-class fields."
        )
    _render_overview_download_section(data_processor, selected_year, selected_quarter)
    end_snap_section()
    st.stop()

if selected_overview_area == "topic_signal":
    topic_chart_rendered = _render_transcript_topic_growth_chart(selected_year, selected_quarter, plotly_config)
    if not topic_chart_rendered:
        st.info(
            "No transcript topic metrics found. Run `python3 scripts/extract_transcript_topics.py` "
            "after adding new quarter transcript files."
        )
    iconic_quotes_rendered = _render_iconic_quote_section(data_processor, selected_year, selected_quarter)
    if not iconic_quotes_rendered:
        st.caption("No iconic CEO/CFO quote rows found for this period.")
    _render_overview_download_section(data_processor, selected_year, selected_quarter)
    end_snap_section()
    st.stop()

if selected_overview_area == "export":
    _render_overview_download_section(data_processor, selected_year, selected_quarter)
    end_snap_section()
    st.stop()


def _is_digital_metric_type(metric_name: str) -> bool:
    text = str(metric_name or "").strip().lower()
    if not text:
        return False
    digital_tokens = (
        "digital",
        "search",
        "social",
        "display",
        "internet",
        "online",
        "nonsearch",
        "retail",
        "ecommerce",
        "programmatic",
        "video",
        "connected tv",
        "ctv",
    )
    return any(token in text for token in digital_tokens)


def _calc_scope_growth_pct(
    country_df: pd.DataFrame,
    year: int,
    allowed_countries: set[str] | None = None,
) -> float:
    if country_df is None or country_df.empty:
        return np.nan
    scope = country_df[country_df["Year"].isin([int(year) - 1, int(year)])].copy()
    if allowed_countries:
        scope = scope[scope["Country"].isin(allowed_countries)].copy()
    if scope.empty:
        return np.nan
    annual = scope.groupby("Year", as_index=False)["Value"].sum(min_count=1)
    curr = annual.loc[annual["Year"] == int(year), "Value"]
    prev = annual.loc[annual["Year"] == int(year) - 1, "Value"]
    if curr.empty or prev.empty:
        return np.nan
    curr_val = float(curr.iloc[0])
    prev_val = float(prev.iloc[0])
    if prev_val == 0 or pd.isna(prev_val):
        return np.nan
    return ((curr_val - prev_val) / prev_val) * 100.0


def _calc_digital_share_growth_pp(
    country_df: pd.DataFrame,
    year: int,
    allowed_countries: set[str] | None = None,
) -> float:
    if country_df is None or country_df.empty:
        return np.nan
    scope = country_df[country_df["Year"].isin([int(year) - 1, int(year)])].copy()
    if allowed_countries:
        scope = scope[scope["Country"].isin(allowed_countries)].copy()
    if scope.empty:
        return np.nan
    scope["IsDigital"] = scope["Metric_type"].apply(_is_digital_metric_type)
    total = scope.groupby("Year", as_index=False)["Value"].sum(min_count=1).rename(columns={"Value": "TotalValue"})
    digital = (
        scope[scope["IsDigital"]]
        .groupby("Year", as_index=False)["Value"]
        .sum(min_count=1)
        .rename(columns={"Value": "DigitalValue"})
    )
    merged = total.merge(digital, on="Year", how="left")
    merged["DigitalValue"] = merged["DigitalValue"].fillna(0.0)
    merged = merged[merged["TotalValue"] > 0].copy()
    if merged.empty:
        return np.nan
    merged["DigitalSharePct"] = (merged["DigitalValue"] / merged["TotalValue"]) * 100.0
    curr = merged.loc[merged["Year"] == int(year), "DigitalSharePct"]
    prev = merged.loc[merged["Year"] == int(year) - 1, "DigitalSharePct"]
    if curr.empty or prev.empty:
        return np.nan
    return float(curr.iloc[0]) - float(prev.iloc[0])


def _render_region_vs_global_position_badge(
    country_df: pd.DataFrame,
    map_year: int,
    scope_label: str = "Global",
    allowed_countries: set[str] | None = None,
) -> None:
    scope_label = str(scope_label or "Global").strip() or "Global"
    is_global_scope = scope_label.lower() == "global" or not allowed_countries

    if is_global_scope:
        st.markdown("#### Global Advertising Position")
    else:
        st.markdown(f"#### {html.escape(scope_label)} Advertising Position vs Global")
    st.markdown(
        "Classification Types: 🟢 In Line / Resilient · 🟡 Below Global Average · 🔴 Structurally Lagging"
    )

    apac_countries = set(CONTINENT_MAPPINGS.get("Asia Pacific", []))
    north_america_countries = set(CONTINENT_MAPPINGS.get("North America", []))

    global_growth = _calc_scope_growth_pct(country_df, int(map_year))
    scope_growth = (
        _calc_scope_growth_pct(country_df, int(map_year), allowed_countries)
        if not is_global_scope
        else global_growth
    )
    us_growth = _calc_scope_growth_pct(country_df, int(map_year), {"United States"})
    if pd.isna(us_growth):
        us_growth = _calc_scope_growth_pct(country_df, int(map_year), north_america_countries)
    apac_growth = _calc_scope_growth_pct(country_df, int(map_year), apac_countries)

    high_growth_candidates = [v for v in [us_growth, apac_growth] if pd.notna(v)]
    high_growth_reference = max(high_growth_candidates) if high_growth_candidates else np.nan

    if is_global_scope:
        gd = np.nan
        hg = global_growth - high_growth_reference if pd.notna(global_growth) and pd.notna(high_growth_reference) else np.nan
        dad = np.nan

        if pd.notna(hg) and hg <= -5.0:
            regime_icon = "🔴"
            regime_label = "Global Structurally Lagging High-Growth Regions"
            regime_style = "background:rgba(239,68,68,0.16); border:1px solid rgba(239,68,68,0.4); color:#FCA5A5;"
            base_desc = (
                f"Global ad growth materially trails high-growth regions by {abs(hg):.1f}pp, "
                "signaling concentrated momentum in selective markets and elevated allocation pressure."
            )
        elif pd.notna(hg) and hg < -2.0:
            regime_icon = "🟡"
            regime_label = "Global Growing Below High-Growth Regions"
            regime_style = "background:rgba(245,158,11,0.14); border:1px solid rgba(245,158,11,0.42); color:#FDE68A;"
            base_desc = (
                f"Global ad growth trails high-growth regions by {abs(hg):.1f}pp, "
                "reflecting uneven expansion across geographies."
            )
        else:
            regime_icon = "🟢"
            regime_label = "Global In Line with High-Growth Regions"
            regime_style = "background:rgba(34,197,94,0.14); border:1px solid rgba(34,197,94,0.45); color:#86EFAC;"
            base_desc = (
                "Global ad growth is broadly aligned with high-growth regions, "
                "indicating resilient aggregate demand across major markets."
            )
    else:
        gd = scope_growth - global_growth if pd.notna(scope_growth) and pd.notna(global_growth) else np.nan
        hg = scope_growth - high_growth_reference if pd.notna(scope_growth) and pd.notna(high_growth_reference) else np.nan

        scope_digital_growth = _calc_digital_share_growth_pp(country_df, int(map_year), allowed_countries)
        global_digital_growth = _calc_digital_share_growth_pp(country_df, int(map_year))
        dad = (
            scope_digital_growth - global_digital_growth
            if pd.notna(scope_digital_growth) and pd.notna(global_digital_growth)
            else np.nan
        )

        if pd.notna(gd) and pd.notna(hg) and gd <= -3.0 and hg <= -5.0:
            regime_icon = "🔴"
            regime_label = f"{scope_label} Structurally Lagging High-Growth Regions"
            regime_style = "background:rgba(239,68,68,0.16); border:1px solid rgba(239,68,68,0.4); color:#FCA5A5;"
            base_desc = (
                f"{scope_label} materially underperforms global and high-growth regions by over {abs(gd):.1f}pp, "
                "reflecting structural digital acceleration gaps and rising competitive pressure from global platforms."
            )
        elif pd.notna(gd) and pd.notna(hg) and gd >= -0.5 and hg >= -3.0:
            regime_icon = "🟢"
            regime_label = f"{scope_label} In Line with Global Advertising Momentum"
            regime_style = "background:rgba(34,197,94,0.14); border:1px solid rgba(34,197,94,0.45); color:#86EFAC;"
            base_desc = (
                f"{scope_label} ad growth is broadly aligned with global trends ({gd:+.1f}pp differential), "
                "supported by balanced digital expansion and resilient premium inventory dynamics."
            )
        else:
            regime_icon = "🟡"
            regime_label = f"{scope_label} Growing Below Global Average"
            regime_style = "background:rgba(245,158,11,0.14); border:1px solid rgba(245,158,11,0.42); color:#FDE68A;"
            gd_abs_text = f"{abs(gd):.1f}" if pd.notna(gd) else "N/A"
            hg_abs_text = f"{abs(hg):.1f}" if pd.notna(hg) else "N/A"
            base_desc = (
                f"{scope_label} ad growth trails global by {gd_abs_text}pp and high-growth regions by {hg_abs_text}pp, "
                "reflecting slower digital acceleration while maintaining relative premium inventory stability."
            )

        dad_modifier = ""
        if pd.notna(dad) and dad <= -1.0:
            dad_modifier = " Digital acceleration gap versus global markets remains significant."
        elif pd.notna(dad) and dad >= 0:
            dad_modifier = " Digital expansion remains broadly aligned with global trends."
        base_desc = base_desc + dad_modifier

    st.markdown(
        _html_block(
            f"""
            <div style="border-radius:14px; padding:12px 14px; margin:8px 0 10px 0; {regime_style}">
              <div style="font-size:0.78rem; letter-spacing:0.08em; text-transform:uppercase; font-weight:700; opacity:0.9;">
                {html.escape(scope_label)} Demand Classification · {int(map_year)}
              </div>
              <div style="font-size:1.0rem; font-weight:800; margin-top:5px;">
                {regime_icon} {regime_label}
              </div>
              <div style="font-size:0.92rem; line-height:1.5; margin-top:6px;">
                {html.escape(base_desc)}
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("Growth Differential (GD)", f"{gd:+.1f}pp" if pd.notna(gd) else "N/A")
    with metric_cols[1]:
        st.metric("High-Growth Gap (HG)", f"{hg:+.1f}pp" if pd.notna(hg) else "N/A")
    with metric_cols[2]:
        st.metric("Digital Accel Differential (DAD)", f"{dad:+.1f}pp" if pd.notna(dad) else "N/A")

# SECTION 1 — GLOBAL CONTEXT (WORLD MAP)
st.markdown("<div id='section-global-media-economy'></div>", unsafe_allow_html=True)
st.subheader("Global Media Economy")
st.markdown(
    "Global advertising is geographically distributed across regions and markets. "
    "Hover countries to view values.",
)

theme_mode = get_theme_mode()
dark_mode = theme_mode == "dark"
map_bg = "#0B1220" if dark_mode else "#F8FAFC"
land_color = "#1E293B" if dark_mode else "#E2E8F0"
ocean_color = "#0B1220" if dark_mode else "#FFFFFF"
border_color = "rgba(15,23,42,0.12)" if dark_mode else "rgba(15,23,42,0.18)"
label_text_color = "#F8FAFC" if dark_mode else "#0F172A"
annotation_bg = "rgba(15, 23, 42, 0.92)" if dark_mode else "rgba(255,255,255,0.96)"
annotation_border = "#FFFFFF" if dark_mode else "rgba(15,23,42,0.18)"
hover_bg = "rgba(15, 23, 42, 0.92)" if dark_mode else "rgba(255,255,255,0.98)"
hover_border = "rgba(255,255,255,0.12)" if dark_mode else "rgba(15,23,42,0.15)"
hover_font_color = "#FFFFFF" if dark_mode else "#0F172A"
colorbar_font = "rgba(226, 232, 240, 0.8)" if dark_mode else "rgba(15, 23, 42, 0.6)"

country_ad_df = _load_country_advertising_df(
    getattr(data_processor, "data_path", ""),
    int(getattr(data_processor, "source_stamp", 0) or 0),
)
if not country_ad_df.empty:
    view_mode = st.radio(
        "Map view",
        ["By region", "By country"],
        index=0,
        horizontal=True,
        key="overview_map_view",
        help="Choose region view or country-level detail.",
    )

    region_options = [
        str(region)
        for region in CONTINENT_MAPPINGS.keys()
        if str(region).strip() and str(region).strip().lower() != "global"
    ]
    region_col, _ = st.columns([0.22, 0.78])
    with region_col:
        region_choice = st.selectbox(
            "Region",
            ["Global"] + region_options,
            index=0,
            help="Global shows everything. By region colors countries uniformly by their region total.",
        )

    metric_types = sorted(country_ad_df["Metric_type"].dropna().unique().tolist())
    metric_col, _ = st.columns([0.22, 0.78])
    with metric_col:
        metric_choice = st.selectbox(
            "Advertising metric",
            ["All channels"] + metric_types,
            index=0,
            help="All channels aggregates all available advertising channels for each country.",
        )

    available_ad_years = sorted(country_ad_df["Year"].dropna().unique().tolist())
    # Time slider for country ad map animation context.
    map_year_default = selected_year
    if map_year_default not in available_ad_years:
        prior_years = [y for y in available_ad_years if y <= selected_year]
        map_year_default = max(prior_years) if prior_years else max(available_ad_years)
    if len(available_ad_years) > 1:
        map_year_index = available_ad_years.index(map_year_default) if map_year_default in available_ad_years else 0
        map_year_selected = st.selectbox(
            "Map Year (country advertising)",
            options=available_ad_years,
            index=map_year_index,
            key="overview_map_year_select",
            help="Select the year to view country-level ad market structure.",
        )
    else:
        map_year_selected = map_year_default

    # Use the map year when available; otherwise pick closest available <= map selection.
    year_for_map = int(map_year_selected)
    if year_for_map not in available_ad_years:
        prior_years = [y for y in available_ad_years if y <= int(map_year_selected)]
        year_for_map = max(prior_years) if prior_years else max(available_ad_years)

    macro_prev_years = [y for y in available_ad_years if y < year_for_map]
    macro_prev_year = max(macro_prev_years) if macro_prev_years else None

    df_year = country_ad_df[country_ad_df["Year"] == int(year_for_map)].copy()
    if metric_choice != "All channels":
        df_year = df_year[df_year["Metric_type"] == metric_choice]

    # Optional country filtering (only in country mode).
    if view_mode == "By country":
        if region_choice != "Global":
            allowed = set(CONTINENT_MAPPINGS.get(region_choice, []))
            if allowed:
                df_year = df_year[df_year["Country"].isin(allowed)]

        available_countries = sorted(df_year["Country"].dropna().unique().tolist()) if not df_year.empty else []
        picked_countries = st.multiselect(
            "Countries (optional)",
            available_countries,
            default=[],
            help="Select countries to focus the map. Leave empty to show all countries in the selected region.",
        )
        if picked_countries:
            df_year = df_year[df_year["Country"].isin(set(picked_countries))]
    else:
        picked_countries = []

    scope_countries: set[str] | None = None
    scope_label = "Global"
    if view_mode == "By country" and picked_countries:
        scope_label = "Selected Countries"
        scope_countries = set(picked_countries)
    elif region_choice != "Global":
        scope_label = str(region_choice)
        mapped = set(CONTINENT_MAPPINGS.get(region_choice, []))
        scope_countries = mapped if mapped else None

    _render_region_vs_global_position_badge(
        country_ad_df,
        int(year_for_map),
        scope_label=scope_label,
        allowed_countries=scope_countries,
    )

    macro_base_df = country_ad_df.copy()
    macro_years = [int(year_for_map)]
    if macro_prev_year is not None:
        macro_years.append(int(macro_prev_year))
    macro_base_df = macro_base_df[macro_base_df["Year"].isin(macro_years)]

    if region_choice != "Global":
        allowed = set(CONTINENT_MAPPINGS.get(region_choice, []))
        if allowed:
            macro_base_df = macro_base_df[macro_base_df["Country"].isin(allowed)]
    if view_mode == "By country" and picked_countries:
        macro_base_df = macro_base_df[macro_base_df["Country"].isin(set(picked_countries))]

    macro_rows = []
    if metric_choice == "All channels":
        for macro, types in AD_MACRO_CATEGORIES.items():
            current_sum = macro_base_df[
                (macro_base_df["Year"] == int(year_for_map))
                & (macro_base_df["Metric_type"].isin(types))
            ]["Value"].sum()
            prev_sum = 0.0
            if macro_prev_year is not None:
                prev_sum = macro_base_df[
                    (macro_base_df["Year"] == int(macro_prev_year))
                    & (macro_base_df["Metric_type"].isin(types))
                ]["Value"].sum()
            yoy = None
            if prev_sum:
                yoy = ((current_sum - prev_sum) / prev_sum) * 100.0
            macro_rows.append((macro, yoy))
    else:
        macro_base_df = macro_base_df[macro_base_df["Metric_type"] == metric_choice]
        current_sum = macro_base_df[macro_base_df["Year"] == int(year_for_map)]["Value"].sum()
        prev_sum = 0.0
        if macro_prev_year is not None:
            prev_sum = macro_base_df[macro_base_df["Year"] == int(macro_prev_year)]["Value"].sum()
        yoy = None
        if prev_sum:
            yoy = ((current_sum - prev_sum) / prev_sum) * 100.0
        macro_rows.append((metric_choice, yoy))

    if macro_rows:
        if metric_choice == "All channels":
            label_prefix = "Macro YoY"
        else:
            label_prefix = f"{metric_choice} YoY"
        if macro_prev_year is not None:
            macro_label = f"{label_prefix} ({year_for_map} vs {macro_prev_year})"
        else:
            macro_label = f"{label_prefix} ({year_for_map})"
        st.markdown(f"<div class='ov-macro-label'>{macro_label}</div>", unsafe_allow_html=True)
        macro_html = "<div class='ov-macro-row'>"
        for macro, yoy in macro_rows:
            if yoy is None:
                cls = ""
                value = "—"
            else:
                cls = "positive" if yoy >= 0 else "negative"
                value = f"{yoy:+.1f}%"
            macro_html += f"<div class='ov-macro-pill {cls}'><span>{macro}</span><span>{value}</span></div>"
        macro_html += "</div>"
        st.markdown(macro_html, unsafe_allow_html=True)

    df_map = (
        df_year.groupby("Country", as_index=False)["Value"].sum()
        if not df_year.empty
        else pd.DataFrame(columns=["Country", "Value"])
    )

    if not df_map.empty:
        map_title_suffix = (
            f"{metric_choice} ({year_for_map})" if metric_choice != "All channels" else f"All channels ({year_for_map})"
        )
        # Region mode: aggregate by region and color countries uniformly by their region total.
        if view_mode == "By region":
            country_to_region = {}
            for region, names in CONTINENT_MAPPINGS.items():
                for name in names:
                    country_to_region[str(name)] = str(region)
            df_map["Region"] = df_map["Country"].map(country_to_region).fillna("Other")

            df_region = df_map.groupby("Region", as_index=False)["Value"].sum()
            if region_choice != "Global":
                selected_region_mask = df_map["Region"] == region_choice
            else:
                selected_region_mask = None

            region_total_map = {r["Region"]: float(r["Value"]) for _, r in df_region.iterrows()}
            df_map["RegionTotal"] = df_map["Region"].map(region_total_map).fillna(0.0)
            if selected_region_mask is not None:
                df_map["ValueForColor"] = np.where(selected_region_mask, df_map["RegionTotal"], 0.0)
            else:
                df_map["ValueForColor"] = df_map["RegionTotal"]
        else:
            df_map["Region"] = ""
            df_map["RegionTotal"] = 0.0
            df_map["ValueForColor"] = df_map["Value"]

        # Improve gradient separation: use a log-scaled color value (hover shows true value).
        df_map["ColorValue"] = np.log10(df_map["ValueForColor"].clip(lower=0) + 1.0)
        cmin = float(df_map["ColorValue"].min())
        cmax = float(df_map["ColorValue"].quantile(0.98)) if len(df_map) > 5 else float(df_map["ColorValue"].max())
        if cmax <= cmin:
            cmax = cmin + 1.0

        map_fig = px.choropleth(
            df_map,
            locations="Country",
            locationmode="country names",
            color="ColorValue",
            hover_name="Country" if view_mode == "By country" else "Region",
            color_continuous_scale=[
                [0.0, "#DBEAFE"],
                [0.55, "#60A5FA"],
                [1.0, "#0073FF"],
            ],
            labels={"ColorValue": "Advertising"},
            range_color=(cmin, cmax),
        )
        if map_fig.data:
            map_fig.data[0].name = "country-layer"
            map_fig.data[0].showlegend = False
        continent_geojson = _load_continent_geojson() if view_mode == "By region" else None

        region_allowed = None
        if region_choice != "Global":
            region_allowed = set(CONTINENT_MAPPINGS.get(region_choice, []))
        region_filtered = df_year if region_allowed is None else df_year[df_year["Country"].isin(region_allowed)]

        summary_html = ""
        if view_mode == "By region":
            if region_choice == "Global":
                total_value = float(df_region["Value"].sum()) if not df_region.empty else 0.0
                total_label = f"Global total — {map_title_suffix}"
            else:
                total_value = float(
                    df_region.loc[df_region["Region"] == region_choice, "Value"].sum()
                )
                total_label = f"{region_choice} total — {map_title_suffix}"
            top_n = 8 if region_choice == "Global" else 6
            country_totals = (
                region_filtered.groupby("Country", as_index=False)["Value"]
                .sum()
                .sort_values("Value", ascending=False)
                .head(top_n)
            )
            rows_html = ""
            for idx, row in enumerate(country_totals.itertuples(index=False), start=1):
                country_text = html.escape(str(row.Country))
                country_attr = html.escape(str(row.Country), quote=True)
                rows_html += (
                    f"<div class='ov-map-summary-row' data-country=\"{country_attr}\"><span>{idx}. {country_text}</span>"
                    f"<span>{_fmt_compact(row.Value)}</span></div>"
                )
                if metric_choice == "All channels":
                    channel_df = (
                        region_filtered[region_filtered["Country"] == row.Country]
                        .groupby("Metric_type", as_index=False)["Value"]
                        .sum()
                        .sort_values("Value", ascending=False)
                        .head(3)
                    )
                    for channel in channel_df.itertuples(index=False):
                        metric_text = html.escape(str(channel.Metric_type))
                        rows_html += (
                            f"<div class='ov-map-summary-sub'><span>{metric_text}</span>"
                            f"<span>{_fmt_compact(channel.Value)}</span></div>"
                        )
        else:
            total_value = float(df_map["Value"].sum()) if not df_map.empty else 0.0
            total_label = (
                f"{region_choice} total — {map_title_suffix}"
                if region_choice != "Global"
                else f"Global total — {map_title_suffix}"
            )
            top_n = 10 if region_choice == "Global" else 6
            country_totals = df_map.sort_values("Value", ascending=False).head(top_n)
            rows_html = ""
            for idx, row in enumerate(country_totals.itertuples(index=False), start=1):
                country_text = html.escape(str(row.Country))
                country_attr = html.escape(str(row.Country), quote=True)
                rows_html += (
                    f"<div class='ov-map-summary-row' data-country=\"{country_attr}\"><span>{idx}. {country_text}</span>"
                    f"<span>{_fmt_compact(row.Value)}</span></div>"
                )
                if metric_choice == "All channels":
                    channel_df = (
                        region_filtered[region_filtered["Country"] == row.Country]
                        .groupby("Metric_type", as_index=False)["Value"]
                        .sum()
                        .sort_values("Value", ascending=False)
                        .head(3)
                    )
                    for channel in channel_df.itertuples(index=False):
                        metric_text = html.escape(str(channel.Metric_type))
                        rows_html += (
                            f"<div class='ov-map-summary-sub'><span>{metric_text}</span>"
                            f"<span>{_fmt_compact(channel.Value)}</span></div>"
                        )

        if rows_html:
            summary_html = (
                "<div class='ov-map-summary'>"
                f"<div class='ov-map-summary-title'>{total_label}</div>"
                f"<div class='ov-map-summary-value'>{total_value:,.0f}</div>"
                f"<div class='ov-map-summary-list'>{rows_html}</div>"
                "</div>"
            )

        st.markdown(f"**{map_title_suffix}**")

        if view_mode == "By country":
            country_label_overrides = {
                "Peru": (-74.5, -10.2),
                "Indonesia": (116.0, -2.5),
                "Greece": (22.0, 39.0),
                "Canada": (-106.0, 60.5),
            }
            label_values = df_map["Value"].tolist()
            label_texts = [_fmt_compact(v) for v in label_values]
            label_sizes = [10 if float(v) >= 1_000_000 else 8 for v in label_values]
            default_locations = []
            default_texts = []
            default_sizes = []
            override_lons = []
            override_lats = []
            override_texts = []
            override_sizes = []
            for country, text, size in zip(df_map["Country"].tolist(), label_texts, label_sizes):
                if country in country_label_overrides:
                    lon, lat = country_label_overrides[country]
                    override_lons.append(lon)
                    override_lats.append(lat)
                    override_texts.append(text)
                    override_sizes.append(size)
                else:
                    default_locations.append(country)
                    default_texts.append(text)
                    default_sizes.append(size)
            map_fig.add_trace(
                go.Scattergeo(
                    locations=default_locations,
                    locationmode="country names",
                    text=default_texts,
                    mode="text",
                    textfont=dict(size=default_sizes, color=label_text_color, family="Poppins, system-ui, sans-serif"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
            if override_lons:
                map_fig.add_trace(
                    go.Scattergeo(
                        lon=override_lons,
                        lat=override_lats,
                        text=override_texts,
                        mode="text",
                        textfont=dict(size=override_sizes, color=label_text_color, family="Poppins, system-ui, sans-serif"),
                        hoverinfo="skip",
                        showlegend=False,
                        name="country-label-overrides",
                    )
                )
        if view_mode == "By region":
            label_regions = (
                [region_choice] if region_choice != "Global" else sorted(df_region["Region"].unique())
            )
            geo_key = None
            centroid_map = {}
            region_aliases = {
                "Asia Pacific": ["Asia", "Oceania", "Australia"],
                "Middle East & Africa": ["Africa"],
            }
            if continent_geojson:
                geo_key = _pick_geojson_region_key(
                    continent_geojson,
                    label_regions or CONTINENT_MAPPINGS.keys(),
                )
                centroid_map = _geojson_centroids(continent_geojson, geo_key) if geo_key else {}
            annotations = []
            for region in label_regions:
                total_value = float(region_total_map.get(region, 0.0))
                if total_value <= 0:
                    continue
                pos = None
                if centroid_map:
                    centroid = centroid_map.get(region)
                    if not centroid:
                        alias_names = region_aliases.get(region, [])
                        alias_points = [centroid_map.get(a) for a in alias_names if centroid_map.get(a)]
                        if alias_points:
                            lon_sum = sum(p[0] for p in alias_points)
                            lat_sum = sum(p[1] for p in alias_points)
                            centroid = (lon_sum / len(alias_points), lat_sum / len(alias_points))
                    if centroid:
                        pos = _lonlat_to_paper(centroid[0], centroid[1])
                if not pos:
                    continue
                value_text = _fmt_compact(total_value)
                annotations.append(
                    dict(
                        x=pos[0],
                        y=pos[1],
                        xref="paper",
                        yref="paper",
                        text=f"<b>{region}</b><br><b>{value_text}</b>",
                        showarrow=False,
                        align="center",
                        xanchor="center",
                        yanchor="middle",
                        font=dict(
                            size=11,
                            color=label_text_color,
                            family="Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
                        ),
                        bgcolor=annotation_bg,
                        bordercolor=annotation_border,
                        borderwidth=1,
                        borderpad=6,
                    )
                )
            if annotations:
                map_fig.update_layout(annotations=annotations)
        map_fig.update_geos(
            projection_type="natural earth",
            projection_scale=1.0,
            center=dict(lon=0, lat=0),
            showcoastlines=False,
            showcountries=True,
            countrycolor=border_color,
            showframe=False,
            showland=True,
            landcolor=land_color,
            oceancolor=ocean_color,
            lakecolor=ocean_color,
            bgcolor="rgba(0,0,0,0)",
        )
        map_fig.update_layout(
            height=680,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor=map_bg,
            plot_bgcolor=map_bg,
            coloraxis_colorbar=dict(
                tickfont=dict(color=colorbar_font),
                title=dict(text="", font=dict(color=colorbar_font)),
            ),
            font=dict(family="Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"),
            dragmode=False,
            hoverlabel=dict(
                bgcolor=hover_bg,
                bordercolor=hover_border,
                font=dict(
                    color=hover_font_color,
                    size=12,
                    family="Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
                ),
                align="left",
            ),
        )
        map_total_value = float(df_map["Value"].sum()) if not df_map.empty else 0.0
        rank_df = (
            df_map[["Country", "Value"]]
            .sort_values("Value", ascending=False)
            .reset_index(drop=True)
        )
        rank_lookup = {
            str(row.Country): (idx + 1)
            for idx, row in enumerate(rank_df.itertuples(index=False))
        }
        hover_value = [f"{float(v):,.0f}" for v in df_map["Value"].tolist()]
        hover_region_total = [f"{float(v):,.0f}" for v in df_map["RegionTotal"].tolist()]
        hover_share = [
            f"{(float(v) / map_total_value) * 100:.1f}%"
            if map_total_value > 0
            else "—"
            for v in df_map["Value"].tolist()
        ]
        hover_rank = [
            f"#{rank_lookup[str(country)]}" if str(country) in rank_lookup else "—"
            for country in df_map["Country"].tolist()
        ]
        hover_template = (
            "<b>%{customdata[0]}</b>"
            "<br>Year: %{customdata[2]}"
            + ("<br>Region: %{customdata[1]}" if view_mode == "By region" else "")
            + ("<br>Country value: %{customdata[3]}" if view_mode == "By region" else "<br>Advertising: %{customdata[3]}")
            + ("<br>Region total: %{customdata[4]}" if view_mode == "By region" else "")
            + "<br>Share of shown total: %{customdata[5]}"
            + "<br>Rank: %{customdata[6]}"
            + "<extra></extra>"
        )
        map_fig.update_traces(
            hovertemplate=hover_template,
            customdata=np.stack(
                [
                    df_map["Country"].astype(str).to_numpy(),
                    df_map["Region"].astype(str).to_numpy(),
                    np.full(len(df_map), int(year_for_map)),
                    np.array(hover_value, dtype=object),
                    np.array(hover_region_total, dtype=object),
                    np.array(hover_share, dtype=object),
                    np.array(hover_rank, dtype=object),
                ],
                axis=1,
            ),
            selector=dict(name="country-layer"),
        )

        # By region: hide internal country borders for a unified region look.
        if view_mode == "By region":
            map_fig.update_traces(marker_line_width=0, selector=dict(name="country-layer"))
            map_fig.update_geos(showcountries=False)
            continent_geojson = _load_continent_geojson()
            if continent_geojson:
                region_outline_aliases = {
                    "Asia Pacific": ["Asia", "Oceania", "Australia"],
                    "Middle East & Africa": ["Africa"],
                }
                outline_regions = (
                    region_outline_aliases.get(region_choice, [region_choice])
                    if region_choice != "Global"
                    else None
                )
                geo_key = _pick_geojson_region_key(
                    continent_geojson,
                    outline_regions or CONTINENT_MAPPINGS.keys(),
                )
                if geo_key and outline_regions is None:
                    outline_regions = _geojson_region_names(continent_geojson, geo_key)
                    allowed_outlines = {
                        "Africa",
                        "Asia",
                        "Europe",
                        "North America",
                        "South America",
                        "Oceania",
                        "Australia",
                    }
                    outline_regions = [r for r in outline_regions if r in allowed_outlines]
                if geo_key and outline_regions:
                    outline_df = pd.DataFrame({"Region": outline_regions, "OutlineValue": 1})
                    map_fig.add_trace(
                        go.Choropleth(
                            geojson=continent_geojson,
                            locations=outline_df["Region"],
                            z=outline_df["OutlineValue"],
                            featureidkey=f"properties.{geo_key}",
                            colorscale=[[0.0, "rgba(0,0,0,0)"], [1.0, "rgba(0,0,0,0)"]],
                            showscale=False,
                            hoverinfo="skip",
                            marker_line_width=1.2,
                            marker_line_color="rgba(15, 23, 42, 0.35)",
                            name="region-outline",
                        )
                    )
        map_config = {
            **plotly_config,
            "displayModeBar": "hover",
            "scrollZoom": False,
            "doubleClick": False,
            "modeBarButtonsToRemove": [
                "zoomInGeo",
                "zoomOutGeo",
                "resetGeo",
                "select2d",
                "lasso2d",
                "pan2d",
            ],
            "toImageButtonOptions": {
                "format": "png",
                "filename": "overview_map",
                "scale": 4,
            },
        }
        map_html = pio.to_html(
            map_fig,
            include_plotlyjs="cdn",
            full_html=False,
            config=map_config,
            default_height="100%",
        )
        overlay_html = summary_html if summary_html else ""
        summary_bg = "rgba(11, 18, 32, 0.74)" if dark_mode else "rgba(255, 255, 255, 0.92)"
        summary_border = "rgba(255, 255, 255, 0.55)" if dark_mode else "rgba(15, 23, 42, 0.18)"
        summary_title_color = "#94A3B8" if dark_mode else "#475569"
        summary_value_color = "#F8FAFC" if dark_mode else "#0F172A"
        summary_text_color = "#E2E8F0" if dark_mode else "#0F172A"
        summary_sub_color = "#94A3B8" if dark_mode else "#64748B"
        summary_sticky_bg = "rgba(11, 18, 32, 0.94)" if dark_mode else "rgba(255, 255, 255, 0.95)"
        summary_row_hover_bg = "rgba(148, 163, 184, 0.20)" if dark_mode else "rgba(148, 163, 184, 0.18)"
        summary_row_active_bg = "rgba(34, 211, 238, 0.24)" if dark_mode else "rgba(14, 116, 144, 0.14)"
        components.html(
            _html_block(
                f"""
                <style>
                  @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&display=swap');
                  html, body {{
                    margin: 0;
                    padding: 0;
                    background: transparent;
                    font-family: "Poppins", system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
                  }}
                  .ov-map-wrap {{
                    position: relative;
                    width: 100%;
                    height: clamp(420px, 58vh, 680px);
                    background: {map_bg};
                  }}
                  .ov-map-wrap .js-plotly-plot {{
                    width: 100%;
                    height: 100%;
                  }}
                  .ov-map-wrap .js-plotly-plot > div,
                  .ov-map-wrap .js-plotly-plot .plot-container,
                  .ov-map-wrap .js-plotly-plot .svg-container,
                  .ov-map-wrap .js-plotly-plot .main-svg {{
                    width: 100% !important;
                    height: 100% !important;
                  }}
                  .ov-map-wrap .choroplethlayer .trace path {{
                    transition: transform 160ms ease, stroke-width 160ms ease, filter 180ms ease, opacity 140ms ease;
                    transform-origin: center center;
                    transform-box: fill-box;
                    cursor: pointer;
                  }}
                  .ov-map-wrap .choroplethlayer .trace path.ov-map-country-pop {{
                    transform: scale(1.045);
                    stroke: rgba(255, 255, 255, 0.98) !important;
                    stroke-width: 1.6px !important;
                    filter: drop-shadow(0 2px 8px rgba(15, 23, 42, 0.45));
                  }}
                  .ov-map-wrap .choroplethlayer .trace path.ov-map-country-selected {{
                    transform: scale(1.075);
                    stroke: #22D3EE !important;
                    stroke-width: 2.2px !important;
                    filter: drop-shadow(0 3px 11px rgba(34, 211, 238, 0.55));
                  }}
                  .ov-map-summary {{
                    position: absolute;
                    top: clamp(90px, calc(35% + 90px), 380px);
                    left: 18px;
                    z-index: 6;
                    max-width: min(340px, 40vw);
                    height: clamp(260px, 45vh, 520px);
                    background: {summary_bg};
                    border-radius: 12px;
                    padding: 10px 12px;
                    border: 1px solid {summary_border};
                    overflow-y: auto;
                    pointer-events: auto;
                    color: {summary_text_color};
                  }}
                  .ov-map-summary-title {{
                    position: sticky;
                    top: 0;
                    z-index: 2;
                    padding: 6px 0 8px 0;
                    background: {summary_sticky_bg};
                    backdrop-filter: blur(6px);
                  }}
                  .ov-map-summary-value {{
                    position: sticky;
                    top: 32px;
                    z-index: 2;
                    padding-bottom: 10px;
                    background: {summary_sticky_bg};
                    backdrop-filter: blur(6px);
                  }}
                  .ov-map-summary-title {{
                    font-size: 0.95rem;
                    color: {summary_title_color};
                    margin-bottom: 6px;
                  }}
                  .ov-map-summary-value {{
                    font-size: 1.75rem;
                    font-weight: 700;
                    color: {summary_value_color};
                    margin-bottom: 12px;
                  }}
                  .ov-map-summary-list {{
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                  }}
                  .ov-map-summary-row {{
                    display: flex;
                    justify-content: space-between;
                    gap: 8px;
                    font-size: 0.9rem;
                    font-weight: 600;
                    color: {summary_text_color};
                  }}
                  .ov-map-summary-row[data-country] {{
                    margin: 0 -6px;
                    padding: 4px 6px;
                    border-radius: 8px;
                    cursor: pointer;
                    transition: background 120ms ease, transform 120ms ease;
                  }}
                  .ov-map-summary-row[data-country]:hover {{
                    background: {summary_row_hover_bg};
                    transform: translateX(1px);
                  }}
                  .ov-map-summary-row.ov-map-summary-row-active {{
                    background: {summary_row_active_bg};
                  }}
                  .ov-map-summary-sub {{
                    display: flex;
                    justify-content: space-between;
                    gap: 8px;
                    font-size: 0.78rem;
                    color: {summary_sub_color};
                    padding-left: 10px;
                  }}
                </style>
                <div class="ov-map-wrap">
                  {map_html}
                  {overlay_html}
                </div>
                <script>
                  (function () {{
                    const wrap = document.querySelector(".ov-map-wrap");
                    if (!wrap) return;

                    const getPlot = () => wrap.querySelector(".js-plotly-plot");
                    let hoveredPath = null;
                    let selectedPath = null;
                    let selectedCountry = "";

                    const relayout = () => {{
                      const plot = getPlot();
                      if (!plot || !window.Plotly) return;
                      try {{
                        window.Plotly.Plots.resize(plot);
                        window.Plotly.relayout(plot, {{ autosize: true }});
                      }} catch (e) {{}}
                    }};

                    const getCountryPaths = () => {{
                      const plot = getPlot();
                      if (!plot) return [];
                      const firstTrace = plot.querySelector(".choroplethlayer .trace");
                      if (firstTrace) return Array.from(firstTrace.querySelectorAll("path"));
                      return Array.from(plot.querySelectorAll(".choroplethlayer path"));
                    }};

                    const clearHover = () => {{
                      if (hoveredPath && hoveredPath !== selectedPath) {{
                        hoveredPath.classList.remove("ov-map-country-pop");
                      }}
                      hoveredPath = null;
                    }};

                    const setHover = (path) => {{
                      if (!path || path === selectedPath) return;
                      if (hoveredPath && hoveredPath !== selectedPath && hoveredPath !== path) {{
                        hoveredPath.classList.remove("ov-map-country-pop");
                      }}
                      hoveredPath = path;
                      hoveredPath.classList.add("ov-map-country-pop");
                    }};

                    const syncSummarySelection = () => {{
                      wrap.querySelectorAll(".ov-map-summary-row[data-country]").forEach((row) => {{
                        const isActive = !!selectedCountry && row.dataset.country === selectedCountry;
                        row.classList.toggle("ov-map-summary-row-active", isActive);
                      }});
                    }};

                    const clearSelected = () => {{
                      if (selectedPath) {{
                        selectedPath.classList.remove("ov-map-country-selected");
                        selectedPath.classList.remove("ov-map-country-pop");
                      }}
                      if (hoveredPath && hoveredPath === selectedPath) {{
                        hoveredPath = null;
                      }}
                      selectedPath = null;
                      selectedCountry = "";
                      syncSummarySelection();
                    }};

                    const getPointIndex = (pt) => {{
                      if (!pt) return -1;
                      if (Number.isInteger(pt.pointNumber)) return pt.pointNumber;
                      if (Number.isInteger(pt.pointIndex)) return pt.pointIndex;
                      return -1;
                    }};

                    const getCountryFromPoint = (pt) => {{
                      if (!pt) return "";
                      const cd = Array.isArray(pt.customdata) ? pt.customdata : null;
                      if (cd && cd.length) return String(cd[0] || "").trim();
                      if (pt.location) return String(pt.location).trim();
                      return "";
                    }};

                    const getCountryToIndexMap = () => {{
                      const plot = getPlot();
                      const trace = plot && plot.data && plot.data[0] ? plot.data[0] : null;
                      const cd = trace && Array.isArray(trace.customdata) ? trace.customdata : [];
                      const map = new Map();
                      cd.forEach((row, idx) => {{
                        const country = Array.isArray(row) ? String(row[0] || "").trim() : "";
                        if (country && !map.has(country)) {{
                          map.set(country, idx);
                        }}
                      }});
                      return map;
                    }};

                    const findPathForPoint = (data) => {{
                      const evTarget = data && data.event && data.event.target && data.event.target.closest
                        ? data.event.target.closest("path")
                        : null;
                      if (evTarget && evTarget.closest(".choroplethlayer")) {{
                        return evTarget;
                      }}
                      const pt = data && data.points && data.points[0] ? data.points[0] : null;
                      const idx = getPointIndex(pt);
                      const paths = getCountryPaths();
                      if (idx < 0 || idx >= paths.length) return null;
                      return paths[idx];
                    }};

                    const setSelected = (path, country) => {{
                      if (!path || !country) return;
                      if (selectedPath && selectedPath !== path) {{
                        selectedPath.classList.remove("ov-map-country-selected");
                      }}
                      selectedPath = path;
                      selectedCountry = country;
                      selectedPath.classList.add("ov-map-country-selected");
                      syncSummarySelection();
                    }};

                    const bindSummaryRows = () => {{
                      wrap.querySelectorAll(".ov-map-summary-row[data-country]").forEach((row) => {{
                        if (row.dataset.ovBound === "1") return;
                        row.dataset.ovBound = "1";

                        row.addEventListener("mouseenter", () => {{
                          const country = row.dataset.country || "";
                          const indexMap = getCountryToIndexMap();
                          const idx = indexMap.has(country) ? indexMap.get(country) : -1;
                          const paths = getCountryPaths();
                          if (idx >= 0 && idx < paths.length) {{
                            setHover(paths[idx]);
                          }}
                        }});

                        row.addEventListener("mouseleave", () => {{
                          clearHover();
                        }});

                        row.addEventListener("click", () => {{
                          const country = row.dataset.country || "";
                          const indexMap = getCountryToIndexMap();
                          const idx = indexMap.has(country) ? indexMap.get(country) : -1;
                          const paths = getCountryPaths();
                          if (idx < 0 || idx >= paths.length) return;
                          if (selectedCountry && selectedCountry === country) {{
                            clearSelected();
                            return;
                          }}
                          setSelected(paths[idx], country);
                        }});
                      }});
                    }};

                    const bindMapEvents = () => {{
                      const plot = getPlot();
                      if (!plot || typeof plot.on !== "function" || plot.__ovMapBound) return;
                      plot.__ovMapBound = true;

                      plot.on("plotly_hover", (data) => {{
                        const path = findPathForPoint(data);
                        setHover(path);
                      }});

                      plot.on("plotly_unhover", () => {{
                        clearHover();
                      }});

                      plot.on("plotly_click", (data) => {{
                        const pt = data && data.points && data.points[0] ? data.points[0] : null;
                        const path = findPathForPoint(data);
                        const country = getCountryFromPoint(pt);
                        if (!path || !country) return;
                        if (selectedCountry && selectedCountry === country) {{
                          clearSelected();
                        }} else {{
                          setSelected(path, country);
                        }}
                      }});
                    }};

                    let tries = 0;
                    const settle = () => {{
                      relayout();
                      bindMapEvents();
                      bindSummaryRows();
                      tries += 1;
                      if (tries < 20) {{
                        window.setTimeout(settle, 80);
                      }}
                    }};
                    settle();
                    window.addEventListener("resize", relayout);
                    if (typeof ResizeObserver !== "undefined") {{
                      const observer = new ResizeObserver(relayout);
                      observer.observe(wrap);
                    }}
                  }})();
                </script>
                """
            ),
            height=700,
        )
        if year_for_map != selected_year:
            st.caption(f"Country advertising data is not available for {selected_year}; showing {year_for_map} instead.")

        extras_rendered = _render_global_media_economy_extras(
            country_ad_df=country_ad_df,
            data_processor=data_processor,
            map_year=int(year_for_map),
            plotly_config=plotly_config,
        )
        if not extras_rendered:
            st.caption("Additional country/per-capita/device context will appear when matching rows are available.")
    else:
        st.info("No country advertising values available for the selected metric/year.")
else:
    st.info("Country advertising dataset not found. Expected `Country_Advertising_Data_FullVi` sheet in the workbook source.")


if selected_overview_area == "global_media_map":
    _render_overview_download_section(data_processor, selected_year, selected_quarter)
    end_snap_section()
    st.stop()


end_snap_section()
_render_excel_overview_layers(data_processor, selected_year, selected_quarter, plotly_config)

# Calculate summary metrics
market_cap_data = []
revenue_data = []
net_income_data = []

# Create additional data structures for new metrics
cash_balance_data = []
employee_data = []
rd_data = []
debt_data = []
assets_data = []
cost_of_revenue_data = []
capex_data = []
operating_income_data = []
ad_revenue_data = []

# Process metrics for each company
for company in companies:
    metrics = data_processor.get_metrics(company, selected_year)
    if not metrics:
        continue
    
    # Get previous year metrics for YoY calculation
    metrics_prev = data_processor.get_metrics(company, selected_year-1) if selected_year > 2010 else None
    
    # Calculate YoY metrics safely
    market_cap_yoy = compute_yoy(metrics, metrics_prev, 'market_cap')
    revenue_yoy = compute_yoy(metrics, metrics_prev, 'revenue')
    net_income_yoy = compute_yoy(metrics, metrics_prev, 'net_income')
    cash_balance_yoy = compute_yoy(metrics, metrics_prev, 'cash_balance')
    rd_yoy = compute_yoy(metrics, metrics_prev, 'rd')
    debt_yoy = compute_yoy(metrics, metrics_prev, 'debt')
    assets_yoy = compute_yoy(metrics, metrics_prev, 'total_assets')
    cost_of_revenue_yoy = compute_yoy(metrics, metrics_prev, 'cost_of_revenue')
    capex_yoy = compute_yoy(metrics, metrics_prev, 'capex')
    operating_income_yoy = compute_yoy(metrics, metrics_prev, 'operating_income')
    employees_yoy = compute_yoy(metrics, metrics_prev, 'employees')
    
    # Add to market cap data
    if metrics.get('market_cap') is not None:
        market_cap_data.append({
            'Company': company,
            'Market Cap': metrics.get('market_cap'),
            'Market Cap YoY': market_cap_yoy
        })
    
    # Add to revenue data
    if metrics.get('revenue') is not None:
        revenue_data.append({
            'Company': company,
            'Revenue': metrics.get('revenue'),
            'Revenue YoY': revenue_yoy
        })
    
    # Add to net income data
    if metrics.get('net_income') is not None:
        net_income_data.append({
            'Company': company,
            'Net Income': metrics.get('net_income'),
            'Net Income YoY': net_income_yoy
        })
        
    # Add to cash balance data
    if metrics.get('cash_balance') is not None:
        cash_balance_data.append({
            'Company': company,
            'Cash Balance': metrics.get('cash_balance'),
            'Cash Balance YoY': cash_balance_yoy
        })
    
    # Add to employee data
    if metrics.get('employees') is not None:
        employee_data.append({
            'Company': company,
            'Employees': metrics.get('employees'),
            'Employees YoY': employees_yoy,
        })
        
    # Add to R&D data
    if metrics.get('rd') is not None:
        rd_data.append({
            'Company': company,
            'R&D': metrics.get('rd'),
            'R&D YoY': rd_yoy
        })
        
    # Add to debt data
    if metrics.get('debt') is not None:
        debt_data.append({
            'Company': company,
            'Debt': metrics.get('debt'),
            'Debt YoY': debt_yoy
        })
        
    # Add to total assets data
    if metrics.get('total_assets') is not None:
        assets_data.append({
            'Company': company,
            'Assets': metrics.get('total_assets'),
            'Assets YoY': assets_yoy
        })
        
    # Add to cost of revenue data
    if metrics.get('cost_of_revenue') is not None:
        cost_of_revenue_data.append({
            'Company': company,
            'Cost of Revenue': metrics.get('cost_of_revenue'),
            'Cost of Revenue YoY': cost_of_revenue_yoy
        })
        
    # Add to capex data
    if metrics.get('capex') is not None:
        capex_data.append({
            'Company': company,
            'Capex': metrics.get('capex'),
            'Capex YoY': capex_yoy
        })
        
    # Add to operating income data
    if metrics.get('operating_income') is not None:
        operating_income_data.append({
            'Company': company,
            'Operating Income': metrics.get('operating_income'),
            'Operating Income YoY': operating_income_yoy
        })

    try:
        ad = data_processor.get_advertising_revenue(company, selected_year)
    except KeyError:
        ad = None
    if ad and ad.get("value") is not None:
        prev_ad = (
            data_processor.get_advertising_revenue(company, selected_year - 1)
            if selected_year > 2010
            else None
        )
        prev_val = prev_ad.get("value") if isinstance(prev_ad, dict) else None
        curr_val = ad.get("value")
        ad_yoy = None
        try:
            if prev_val not in (None, 0):
                ad_yoy = ((float(curr_val) - float(prev_val)) / float(prev_val)) * 100
        except Exception:
            ad_yoy = None
        ad_revenue_data.append(
            {
                "Company": company,
                "Ad Revenue": curr_val,
                "Ad Revenue YoY": ad_yoy,
            }
        )

# Sort the data
market_cap_data = sorted(market_cap_data, key=lambda x: x['Market Cap'], reverse=True)
revenue_data = sorted(revenue_data, key=lambda x: x['Revenue'], reverse=True)
net_income_data = sorted(net_income_data, key=lambda x: x['Net Income'], reverse=True)
debt_data = sorted(debt_data, key=lambda x: x['Debt'], reverse=True) if debt_data else []
rd_data = sorted(rd_data, key=lambda x: x['R&D'], reverse=True) if rd_data else []
capex_data = sorted(capex_data, key=lambda x: x['Capex'], reverse=True) if capex_data else []
cost_of_revenue_data = sorted(cost_of_revenue_data, key=lambda x: x['Cost of Revenue'], reverse=True) if cost_of_revenue_data else []
employee_data = sorted(employee_data, key=lambda x: x["Employees"], reverse=True) if employee_data else []
ad_revenue_data = (
    sorted(ad_revenue_data, key=lambda x: float(x["Ad Revenue"]) if x.get("Ad Revenue") is not None else -1, reverse=True)
    if ad_revenue_data
    else []
)

# Load logos once for summary cards
company_logos = load_company_logos()

# Subscribers data (from Company_subscribers_values)
if "subscriber_processor" not in st.session_state:
    st.session_state["subscriber_processor"] = SubscriberDataProcessor()
else:
    existing_processor = st.session_state.get("subscriber_processor")
    if existing_processor is None or not hasattr(existing_processor, "is_source_updated"):
        st.session_state["subscriber_processor"] = SubscriberDataProcessor()
    else:
        try:
            if existing_processor.is_source_updated():
                st.session_state["subscriber_processor"] = SubscriberDataProcessor()
        except Exception:
            st.session_state["subscriber_processor"] = SubscriberDataProcessor()

subscribers_data = []
subscriber_df = getattr(st.session_state["subscriber_processor"], "df_subscribers", None)
if subscriber_df is not None and not subscriber_df.empty:
    df_year = subscriber_df[subscriber_df["year"] == selected_year].copy()
    if not df_year.empty:
        df_year["_q"] = df_year["quarter"].apply(_parse_quarter_number).fillna(0).astype(int)
        df_year = df_year.sort_values(["service", "_q", "subscribers"])
        latest_rows = df_year.groupby("service", as_index=False).tail(1)

        prev_lookup = {}
        if selected_year > 2010:
            df_prev = subscriber_df[subscriber_df["year"] == (selected_year - 1)].copy()
            if not df_prev.empty:
                df_prev["_q"] = df_prev["quarter"].apply(_parse_quarter_number).fillna(0).astype(int)
                df_prev = df_prev.sort_values(["service", "_q", "subscribers"])
                prev_rows = df_prev.groupby("service", as_index=False).tail(1)
                prev_lookup = {
                    str(r["service"]): (r.get("subscribers"), r.get("unit"))
                    for _, r in prev_rows.iterrows()
                }

        for _, row in latest_rows.iterrows():
            service = str(row.get("service") or "").strip()
            if not service:
                continue
            current_val = row.get("subscribers")
            unit = row.get("unit", "millions")
            prev_val, _prev_unit = prev_lookup.get(service, (None, None))
            yoy = None
            try:
                if prev_val not in (None, 0) and current_val is not None:
                    yoy = ((float(current_val) - float(prev_val)) / float(prev_val)) * 100
            except Exception:
                yoy = None
            subscribers_data.append(
                {
                    "Company": service,
                    "Subscribers": current_val,
                    "Subscribers YoY": yoy,
                    "Unit": unit,
                }
            )

subscribers_data = (
    sorted(subscribers_data, key=lambda x: float(x["Subscribers"]) if x.get("Subscribers") is not None else -1, reverse=True)
    if subscribers_data
    else []
)

# Get top companies for each metric
top_market_cap = market_cap_data[0] if market_cap_data else None
top_revenue = revenue_data[0] if revenue_data else None
top_net_income = net_income_data[0] if net_income_data else None
top_debt = debt_data[0] if debt_data else None
top_rd = rd_data[0] if rd_data else None
top_capex = capex_data[0] if capex_data else None 
top_cost_of_revenue = cost_of_revenue_data[0] if cost_of_revenue_data else None
top_employees = employee_data[0] if employee_data else None
top_ad_revenue = ad_revenue_data[0] if ad_revenue_data else None
top_subscribers = subscribers_data[0] if subscribers_data else None

def _top_growth(data_list, yoy_key):
    if not data_list:
        return None
    growth_data = []
    for d in data_list:
        value = d.get(yoy_key)
        try:
            num = float(value)
        except (TypeError, ValueError):
            continue
        if np.isfinite(num):
            growth_data.append(d)
    if not growth_data:
        return None
    return max(growth_data, key=lambda x: x[yoy_key])


def _format_growth_pct(value) -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if not np.isfinite(num):
        return "N/A"
    return f"{num:+.1f}%"


top_growth_market_cap = _top_growth(market_cap_data, "Market Cap YoY")
top_growth_revenue = _top_growth(revenue_data, "Revenue YoY")
top_growth_net_income = _top_growth(net_income_data, "Net Income YoY")
top_growth_operating_income = _top_growth(operating_income_data, "Operating Income YoY")
top_growth_cash = _top_growth(cash_balance_data, "Cash Balance YoY")
top_growth_rd = _top_growth(rd_data, "R&D YoY")
top_growth_debt = _top_growth(debt_data, "Debt YoY")
top_growth_capex = _top_growth(capex_data, "Capex YoY")
top_growth_cost = _top_growth(cost_of_revenue_data, "Cost of Revenue YoY")

def render_executive_summary_section() -> None:
    st.subheader("📈 Executive Summary")
    left_col, right_col = st.columns([2.25, 1])

    with left_col:
        header_left, header_right = st.columns(2)
        with header_left:
            st.markdown(f"### 🏆 {selected_year} Highest Values")
        with header_right:
            st.markdown("### 📊 YoY Growth Leaders")

        pairs = [
            (
                "Highest Market Cap",
                top_market_cap,
                "Market Cap",
                "market_cap",
                "Market Cap Growth",
                top_growth_market_cap,
                "Market Cap YoY",
            ),
            (
                "Highest Revenue",
                top_revenue,
                "Revenue",
                "revenue",
                "Revenue Growth",
                top_growth_revenue,
                "Revenue YoY",
            ),
            (
                "Highest Net Income",
                top_net_income,
                "Net Income",
                "net_income",
                "Net Income Growth",
                top_growth_net_income,
                "Net Income YoY",
            ),
        ]
        for left_title, top_row, left_key, icon_key, right_title, growth_row, yoy_key in pairs:
            if not top_row:
                continue
            growth_company = growth_row["Company"] if growth_row else top_row["Company"]
            growth_value = growth_row.get(yoy_key) if growth_row else None
            st.markdown(
                render_split_summary_card(
                    left_title,
                    top_row["Company"],
                    format_large_number(top_row[left_key]),
                    right_title,
                    growth_company,
                    _format_growth_pct(growth_value),
                    company_logos,
                    left_icon_key=icon_key,
                    right_icon_key=icon_key,
                ),
                unsafe_allow_html=True,
            )

        if operating_income_data:
            top_operating_income = max(
                operating_income_data,
                key=lambda x: x.get("Operating Income", float("-inf")),
            )
            operating_growth_company = (
                top_growth_operating_income["Company"]
                if top_growth_operating_income
                else top_operating_income["Company"]
            )
            operating_growth_value = (
                top_growth_operating_income.get("Operating Income YoY")
                if top_growth_operating_income
                else None
            )
            st.markdown(
                render_split_summary_card(
                    "Highest Operating Income",
                    top_operating_income["Company"],
                    format_large_number(top_operating_income["Operating Income"]),
                    "Operating Income Growth",
                    operating_growth_company,
                    _format_growth_pct(operating_growth_value),
                    company_logos,
                    left_icon_key="operating_income",
                    right_icon_key="operating_income",
                ),
                unsafe_allow_html=True,
            )

        if cash_balance_data:
            top_cash_balance = max(
                cash_balance_data, key=lambda x: x.get("Cash Balance", float("-inf"))
            )
            cash_growth_company = top_growth_cash["Company"] if top_growth_cash else top_cash_balance["Company"]
            cash_growth_value = top_growth_cash.get("Cash Balance YoY") if top_growth_cash else None
            st.markdown(
                render_split_summary_card(
                    "Highest Cash Balance",
                    top_cash_balance["Company"],
                    format_large_number(top_cash_balance["Cash Balance"]),
                    "Cash Balance Growth",
                    cash_growth_company,
                    _format_growth_pct(cash_growth_value),
                    company_logos,
                    left_icon_key="cash_balance",
                    right_icon_key="cash_balance",
                ),
                unsafe_allow_html=True,
            )

        if top_rd:
            rd_growth_company = top_growth_rd["Company"] if top_growth_rd else top_rd["Company"]
            rd_growth_value = top_growth_rd.get("R&D YoY") if top_growth_rd else None
            st.markdown(
                render_split_summary_card(
                    "Highest R&D Spending",
                    top_rd["Company"],
                    format_large_number(top_rd["R&D"]),
                    "R&D Spending Growth",
                    rd_growth_company,
                    _format_growth_pct(rd_growth_value),
                    company_logos,
                    left_icon_key="rd",
                    right_icon_key="rd",
                ),
                unsafe_allow_html=True,
            )

        if top_debt:
            debt_growth_company = top_growth_debt["Company"] if top_growth_debt else top_debt["Company"]
            debt_growth_value = top_growth_debt.get("Debt YoY") if top_growth_debt else None
            st.markdown(
                render_split_summary_card(
                    "Highest Debt",
                    top_debt["Company"],
                    format_large_number(top_debt["Debt"]),
                    "Debt Growth",
                    debt_growth_company,
                    _format_growth_pct(debt_growth_value),
                    company_logos,
                    left_icon_key="debt",
                    right_icon_key="debt",
                ),
                unsafe_allow_html=True,
            )

        if top_capex:
            capex_growth_company = top_growth_capex["Company"] if top_growth_capex else top_capex["Company"]
            capex_growth_value = top_growth_capex.get("Capex YoY") if top_growth_capex else None
            st.markdown(
                render_split_summary_card(
                    "Highest Capital Expenditure",
                    top_capex["Company"],
                    format_large_number(top_capex["Capex"]),
                    "Capital Expenditure Growth",
                    capex_growth_company,
                    _format_growth_pct(capex_growth_value),
                    company_logos,
                    left_icon_key="capex",
                    right_icon_key="capex",
                ),
                unsafe_allow_html=True,
            )

        if top_cost_of_revenue:
            cost_growth_company = top_growth_cost["Company"] if top_growth_cost else top_cost_of_revenue["Company"]
            cost_growth_value = top_growth_cost.get("Cost of Revenue YoY") if top_growth_cost else None
            st.markdown(
                render_split_summary_card(
                    "Highest Cost of Revenue",
                    top_cost_of_revenue["Company"],
                    format_large_number(top_cost_of_revenue["Cost of Revenue"]),
                    "Cost of Revenue Growth",
                    cost_growth_company,
                    _format_growth_pct(cost_growth_value),
                    company_logos,
                    left_icon_key="cost_of_revenue",
                    right_icon_key="cost_of_revenue",
                ),
                unsafe_allow_html=True,
            )

    with right_col:
        st.markdown("### 📣 Ads, Subscribers & Workforce")

        if top_ad_revenue:
            st.markdown(
                render_summary_card(
                    "Highest Advertising Revenue",
                    top_ad_revenue["Company"],
                    _format_ad_revenue_billions(top_ad_revenue.get("Ad Revenue")),
                    company_logos,
                    icon_key="revenue",
                ),
                unsafe_allow_html=True,
            )

        if ad_revenue_data:
            growth_data = []
            for d in ad_revenue_data:
                v = d.get("Ad Revenue YoY")
                try:
                    num = float(v)
                except (TypeError, ValueError):
                    continue
                if np.isfinite(num):
                    growth_data.append(d)
            if growth_data:
                top_growth = max(growth_data, key=lambda x: x["Ad Revenue YoY"])
                yoy_text = _format_growth_pct(top_growth.get("Ad Revenue YoY"))
                st.markdown(
                    render_summary_card(
                        "Advertising Revenue Growth",
                        top_growth["Company"],
                        yoy_text,
                        company_logos,
                        icon_key="revenue",
                    ),
                    unsafe_allow_html=True,
                )

        if top_subscribers:
            st.markdown(
                render_summary_card(
                    "Highest Subscribers",
                    top_subscribers["Company"],
                    _format_subscribers(
                        top_subscribers.get("Subscribers"),
                        top_subscribers.get("Unit"),
                    ),
                    company_logos,
                    icon_key="total_assets",
                ),
                unsafe_allow_html=True,
            )

        if subscribers_data:
            growth_data = []
            for d in subscribers_data:
                v = d.get("Subscribers YoY")
                try:
                    num = float(v)
                except (TypeError, ValueError):
                    continue
                if np.isfinite(num):
                    growth_data.append(d)
            if growth_data:
                top_growth = max(growth_data, key=lambda x: x["Subscribers YoY"])
                yoy_text = _format_growth_pct(top_growth.get("Subscribers YoY"))
                st.markdown(
                    render_summary_card(
                        "Subscribers Growth",
                        top_growth["Company"],
                        yoy_text,
                        company_logos,
                        icon_key="total_assets",
                    ),
                    unsafe_allow_html=True,
                )

        if top_employees:
            st.markdown(
                render_summary_card(
                    "Highest Employees",
                    top_employees["Company"],
                    _format_employee_count(top_employees.get("Employees")),
                    company_logos,
                    icon_key="capex",
                ),
                unsafe_allow_html=True,
            )

        if employee_data:
            growth_data = []
            for d in employee_data:
                v = d.get("Employees YoY")
                try:
                    num = float(v)
                except (TypeError, ValueError):
                    continue
                if np.isfinite(num):
                    growth_data.append(d)
            if growth_data:
                top_growth = max(growth_data, key=lambda x: x["Employees YoY"])
                yoy_text = _format_growth_pct(top_growth.get("Employees YoY"))
                st.markdown(
                    render_summary_card(
                        "Employee Count Growth",
                        top_growth["Company"],
                        yoy_text,
                        company_logos,
                        icon_key="capex",
                    ),
                    unsafe_allow_html=True,
                )

# Add spacing
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# Market Cap vs Nasdaq (Pie)
begin_snap_section("nasdaq_pie")
st.subheader("Market Cap Share vs Nasdaq")
render_standard_overview_comment("Market Cap Share vs Nasdaq", selected_year)
nasdaq_market_cap = None
try:
    nasdaq_market_cap = data_processor.get_nasdaq_market_cap(selected_year, method="year_end")
except Exception:
    nasdaq_market_cap = None

if market_cap_data and nasdaq_market_cap:
    def _fmt_yoy(yoy_value):
        try:
            if yoy_value is None:
                return "N/A"
            return f"{float(yoy_value):+.1f}%"
        except (TypeError, ValueError):
            return "N/A"

    pie_companies = [d["Company"] for d in market_cap_data]
    pie_labels = [company_ticker(c) for c in pie_companies]
    pie_colors = [COMPANY_COLORS.get(c, ["#94a3b8"])[0] for c in pie_companies]

    def _market_cap_for_year(year):
        values = []
        yoy_values = []
        for company in pie_companies:
            metrics = data_processor.get_metrics(company, year) or {}
            cap = metrics.get("market_cap")
            cap_value = float(cap) if cap is not None else 0.0
            values.append(cap_value)
            prev_metrics = data_processor.get_metrics(company, year - 1) or {}
            yoy_values.append(compute_yoy(metrics, prev_metrics, "market_cap"))
        return values, yoy_values

    # Company market caps in our metrics sheet are in USD millions; Nasdaq is in raw USD.
    nasdaq_market_cap_m = float(nasdaq_market_cap) / 1_000_000.0
    values_pie, yoy_pie_raw = _market_cap_for_year(selected_year)
    yoy_pie = [_fmt_yoy(y) for y in yoy_pie_raw]
    sum_companies = float(sum(values_pie))
    remainder = max(nasdaq_market_cap_m - sum_companies, 0.0)

    # Compute YoY for the Nasdaq "Other" remainder (based on remainder, not the raw Nasdaq total).
    nasdaq_other_yoy = "N/A"
    try:
        prev_nasdaq = data_processor.get_nasdaq_market_cap(selected_year - 1, method="year_end")
        if prev_nasdaq:
            prev_nasdaq_m = float(prev_nasdaq) / 1_000_000.0
            prev_company_sum = 0.0
            for company in companies_pie:
                prev_metrics = data_processor.get_metrics(company, selected_year - 1)
                if prev_metrics and prev_metrics.get("market_cap") is not None:
                    prev_company_sum += float(prev_metrics.get("market_cap"))
            prev_remainder = max(prev_nasdaq_m - prev_company_sum, 0.0)
            if prev_remainder > 0 and remainder > 0:
                nasdaq_other_yoy = _fmt_yoy(((remainder - prev_remainder) / prev_remainder) * 100.0)
    except Exception:
        nasdaq_other_yoy = "N/A"

    labels = list(pie_labels) + ["NASDAQ"]
    values = list(values_pie) + [remainder]
    colors = list(pie_colors) + ["#94a3b8"]
    hovertext = [
        f"<b>{c}</b> ({company_ticker(c)})<br>Year: {selected_year}<br>Market Cap: {format_large_number_precise(v)}<br>YoY: {y}"
        for c, v, y in zip(pie_companies, values_pie, yoy_pie)
    ] + [
        f"<b>Nasdaq (Other)</b> (NASDAQ)<br>Year: {selected_year}<br>Market Cap: {format_large_number_precise(remainder)}<br>YoY: {nasdaq_other_yoy}"
    ]

    hover = "%{hovertext}<br>Share of Nasdaq: %{percent}<extra></extra>"

    pie_fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                sort=False,
                direction="clockwise",
                marker=dict(colors=colors, line=dict(color="rgba(255,255,255,0.55)", width=1)),
                hovertext=hovertext,
                hovertemplate=hover,
                textinfo="label",
                textposition="inside",
                insidetextorientation="radial",
                textfont=dict(size=12, color="#F8FAFC"),
            )
        ]
    )
    anim_years = [y for y in available_years if y <= selected_year]
    frames = []
    for year in anim_years:
        year_nasdaq = data_processor.get_nasdaq_market_cap(year, method="year_end")
        if not year_nasdaq:
            continue
        year_nasdaq_m = float(year_nasdaq) / 1_000_000.0
        year_values, year_yoy_raw = _market_cap_for_year(year)
        year_sum = float(sum(year_values))
        year_remainder = max(year_nasdaq_m - year_sum, 0.0)
        year_hover = [
            f"<b>{c}</b> ({company_ticker(c)})<br>Year: {year}<br>Market Cap: {format_large_number_precise(v)}<br>YoY: {_fmt_yoy(y)}"
            for c, v, y in zip(pie_companies, year_values, year_yoy_raw)
        ] + [
            f"<b>Nasdaq (Other)</b> (NASDAQ)<br>Year: {year}<br>Market Cap: {format_large_number_precise(year_remainder)}<br>YoY: N/A"
        ]
        frames.append(
            go.Frame(
                name=str(year),
                data=[
                    go.Pie(
                        labels=labels,
                        values=list(year_values) + [year_remainder],
                        sort=False,
                        direction="clockwise",
                        marker=dict(colors=colors, line=dict(color="rgba(255,255,255,0.55)", width=1)),
                        hovertext=year_hover,
                        hovertemplate=hover,
                        textinfo="label",
                        textposition="inside",
                        insidetextorientation="radial",
                        textfont=dict(size=12, color="#F8FAFC"),
                    )
                ],
            )
        )
    if frames:
        pie_fig.frames = frames
        pie_buttons = create_animation_buttons(x_position=0.01, y_position=1.05)
        for btn in pie_buttons[0]["buttons"]:
            if "frame" in btn["args"][1]:
                btn["args"][1]["frame"]["redraw"] = True
                btn["args"][1]["transition"]["duration"] = 600
        pie_steps = [
            {
                "label": str(year),
                "method": "animate",
                "args": [[str(year)], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}}],
            }
            for year in anim_years
        ]
        pie_fig.update_layout(
            updatemenus=pie_buttons,
            sliders=[{"active": max(len(pie_steps) - 1, 0), "steps": pie_steps, "visible": False}],
            transition=dict(duration=500, easing="cubic-in-out"),
        )
    pie_fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        uniformtext=dict(minsize=8, mode="hide"),
    )
    st.plotly_chart(pie_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Market Cap Share vs Nasdaq", selected_year)
else:
    st.info("Nasdaq market cap data is not available for the selected year.")

end_snap_section()

# Add a touch of breathing room before the treemap.
st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

# Market Cap Treemap (one rectangle split into company boxes)
begin_snap_section("market_cap_treemap")
st.subheader("Market Cap Treemap")
render_standard_overview_comment("Market Cap Treemap", selected_year)
if market_cap_data:
    treemap_companies = [d["Company"] for d in market_cap_data]
    treemap_labels = [company_ticker(c) for c in treemap_companies]
    treemap_values = [float(d["Market Cap"]) for d in market_cap_data]
    treemap_text = [format_large_number_precise(v) for v in treemap_values]
    treemap_colors = [
        COMPANY_COLORS.get(company, ["#94a3b8"])[0] for company in treemap_companies
    ]

    treemap_custom = [
        [company, company_ticker(company), format_large_number_precise(value)]
        for company, value in zip(treemap_companies, treemap_values)
    ]
    treemap_fig = go.Figure(
        go.Treemap(
            labels=treemap_labels,
            parents=[""] * len(treemap_companies),
            values=treemap_values,
            text=treemap_text,
            textinfo="label+text",
            customdata=treemap_custom,
            marker=dict(
                colors=treemap_colors,
                cornerradius=20,
                line=dict(color="rgba(255, 255, 255, 0.35)", width=1),
            ),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Market Cap: %{customdata[2]}<extra></extra>",
            tiling=dict(packing="squarify", pad=6),
            pathbar=dict(visible=False),
        )
    )
    treemap_frames = []
    treemap_years = [y for y in available_years if y <= selected_year]
    for year in treemap_years:
        year_values = []
        year_text = []
        for company in treemap_companies:
            metrics = data_processor.get_metrics(company, year) or {}
            cap_value = metrics.get("market_cap")
            cap_value = float(cap_value) if cap_value is not None else 0.0
            year_values.append(cap_value)
            year_text.append(format_large_number_precise(cap_value))
        treemap_frames.append(
            go.Frame(
                name=str(year),
                data=[
                    go.Treemap(
                        labels=treemap_labels,
                        parents=[""] * len(treemap_companies),
                        values=year_values,
                        text=year_text,
                        textinfo="label+text",
                        customdata=treemap_custom,
                        marker=dict(
                            colors=treemap_colors,
                            cornerradius=20,
                            line=dict(color="rgba(255, 255, 255, 0.35)", width=1),
                        ),
                        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Market Cap: %{customdata[2]}<extra></extra>",
                        tiling=dict(packing="squarify", pad=6),
                        pathbar=dict(visible=False),
                    )
                ],
            )
        )
    if treemap_frames:
        treemap_fig.frames = treemap_frames
        treemap_buttons = create_animation_buttons(x_position=0.01, y_position=1.05)
        for btn in treemap_buttons[0]["buttons"]:
            if "frame" in btn["args"][1]:
                btn["args"][1]["frame"]["redraw"] = True
                btn["args"][1]["transition"]["duration"] = 600
        treemap_steps = [
            {
                "label": frame.name,
                "method": "animate",
                "args": [[frame.name], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}}],
            }
            for frame in treemap_frames
        ]
        treemap_fig.update_layout(
            updatemenus=treemap_buttons,
            sliders=[{"active": max(len(treemap_steps) - 1, 0), "steps": treemap_steps, "visible": False}],
            transition=dict(duration=500, easing="cubic-in-out"),
        )
    treemap_fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        uniformtext=dict(minsize=10, mode="hide"),
    )
    st.plotly_chart(treemap_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Market Cap Treemap", selected_year)
else:
    st.info("Market cap data is not available for the selected year.")

end_snap_section()

# Advertising Revenue vs Total Revenue (Stacked)
begin_snap_section("ad_vs_total")
st.subheader("Advertising Revenue vs Total Revenue")
render_standard_overview_comment("Advertising Revenue vs Total Revenue", selected_year)
ad_stack_rows = []
for company in companies:
    metrics = data_processor.get_metrics(company, selected_year)
    total_revenue = metrics.get("revenue") if metrics else None
    if total_revenue is None:
        continue
    ad = data_processor.get_advertising_revenue(company, selected_year)
    ad_value = ad.get("value") if isinstance(ad, dict) else None
    if ad_value is None:
        continue
    try:
        total_revenue = float(total_revenue)
        ad_value = float(ad_value)
    except (TypeError, ValueError):
        continue
    if not np.isfinite(total_revenue) or not np.isfinite(ad_value):
        continue
    if total_revenue <= 0:
        continue
    # Metrics revenue is stored as USD millions; advertising revenue sheet is USD billions.
    total_revenue_b = total_revenue / 1000.0
    if total_revenue_b <= 0:
        continue
    ad_value = max(ad_value, 0.0)
    ad_pct = (ad_value / total_revenue_b) * 100.0 if total_revenue_b else 0.0
    if not np.isfinite(ad_pct):
        continue
    ad_stack_rows.append(
        {
            "Company": company,
            "Total": total_revenue_b,
            "Ad": ad_value,
            "NonAd": max(total_revenue_b - ad_value, 0.0),
            "AdPct": ad_pct,
        }
    )

if ad_stack_rows:
    ad_stack_rows = sorted(ad_stack_rows, key=lambda x: x["Total"], reverse=True)
    x_companies = [r["Company"] for r in ad_stack_rows]
    y_nonad = [r["NonAd"] for r in ad_stack_rows]
    y_ad = [r["Ad"] for r in ad_stack_rows]
    custom = [
        [
            _format_ad_revenue_billions(r["Ad"]),
            _format_ad_revenue_billions(r["NonAd"]),
            _format_ad_revenue_billions(r["Total"]),
            float(r["AdPct"]),
        ]
        for r in ad_stack_rows
    ]

    base_hex = [COMPANY_COLORS.get(c, ["#94a3b8"])[0] for c in x_companies]
    nonad_colors = [_hex_to_rgba(h, 0.40) for h in base_hex]

    hover_ad = (
        "<b>%{x}</b>"
        f"<br>Year: {selected_year}"
        "<br>Advertising revenue: %{customdata[0]}"
        "<br>Ad % of total: %{customdata[3]:.1f}%"
        "<extra></extra>"
    )
    hover_nonad = (
        "<b>%{x}</b>"
        f"<br>Year: {selected_year}"
        "<br>Total revenue: %{customdata[2]}"
        "<br>Other revenue: %{customdata[1]}"
        "<extra></extra>"
    )

    ad_bar_fig = go.Figure(
        data=[
            go.Bar(
                x=x_companies,
                y=y_nonad,
                name="Other revenue",
                marker=dict(color=nonad_colors, line=dict(color=nonad_colors, width=1)),
                customdata=custom,
                hovertemplate=hover_nonad,
            ),
            go.Bar(
                x=x_companies,
                y=y_ad,
                name="Advertising revenue",
                marker=dict(color=base_hex, line=dict(color=base_hex, width=1)),
                customdata=custom,
                hovertemplate=hover_ad,
            ),
        ]
    )
    ad_pct_labels = [f"{r['AdPct']:.1f}%" for r in ad_stack_rows]
    mode = get_theme_mode()
    label_color = "#F8FAFC" if mode == "dark" else "#0F172A"

    ad_bar_fig.add_trace(
        go.Scatter(
            x=x_companies,
            y=[r["Total"] for r in ad_stack_rows],
            text=ad_pct_labels,
            mode="text",
            textposition="top center",
            textfont=dict(
                size=12,
                color=label_color,
                family="Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
            ),
            hoverinfo="skip",
            showlegend=False,
            name="Ad % labels",
        )
    )
    ad_bar_fig.update_layout(
        barmode="stack",
        height=460,
        margin=_overview_chart_margin(left=10, right=10, top=92, bottom=96),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="",
        yaxis_title="Revenue (USD, Billions)",
        legend=_overview_legend_style(),
        bargap=0.35,
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.92)",
            bordercolor="rgba(255, 255, 255, 0.18)",
            font=dict(
                family='"Poppins", system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif',
                size=12,
                color="#F8FAFC",
            ),
            align="left",
        ),
    )
    ad_bar_fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        showline=False,
        tickangle=-15,
        tickfont=dict(color=label_color),
        title_font=dict(color=label_color),
    )
    ad_bar_fig.update_yaxes(
        showgrid=False,
        zeroline=False,
        showline=False,
        ticksuffix="B",
        tickfont=dict(color=label_color),
        title_font=dict(color=label_color),
    )
    st.plotly_chart(ad_bar_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Advertising Revenue vs Total Revenue", selected_year)
else:
    st.info("Advertising revenue data is not available for the selected year.")

end_snap_section()

# Market Cap Visualization
begin_snap_section("market_cap_animation")

st.subheader("Market Capitalization")
render_standard_overview_comment("Market Capitalization", selected_year)

# Create Market Cap visualization
if market_cap_data:
    # Create animated visualization with frames for different years
    years = [y for y in range(2010, selected_year + 1) if y in available_years]
    max_market_cap = 0
    frames = []
    
    # Create data for each year to enable animation
    for year in years:
        year_data = []
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and metrics.get('market_cap') is not None:
                year_data.append({
                    'Company': company,
                    'Market Cap': metrics.get('market_cap')
                })
                max_market_cap = max(max_market_cap, metrics.get('market_cap'))
        
        if year_data:
            # Sort by market cap descending
            year_data = sorted(year_data, key=lambda x: x['Market Cap'], reverse=True)
            
            # Create frame for this year
            company_list = [d['Company'] for d in year_data]
            values = [d['Market Cap'] for d in year_data]
            colors = [COMPANY_COLORS.get(company, ['#808080'])[0] for company in company_list]
            
            frame = create_consistent_frame(
                companies=company_list,
                values=values,
                year=year,
                max_overall_value=max_market_cap * 1.1,  # Add 10% margin
                title='Market Cap',
                tick_vals=None,  # Will be set by the dynamic function
                tick_text=None,  # Will be set by the dynamic function
                format_func=format_large_number,
                hover_template="<b>%{customdata[0]}</b><br>Market Cap: %{customdata[1]}<extra></extra>",
                colors=colors
            )
            frames.append(frame)
    
    # Create initial visualization
    market_cap_fig = go.Figure(
        data=[go.Bar(
            y=[data['Company'] for data in market_cap_data],
            x=[data['Market Cap'] for data in market_cap_data],
            orientation='h',
            name="Market Cap",
            textposition='outside',
            texttemplate='%{text}',
            text=[format_large_number(data['Market Cap']) for data in market_cap_data],
            hovertemplate="<b>%{y}</b><br>Market Cap: %{text}<br>YoY Change: %{customdata:.1f}%<extra></extra>",
            customdata=[data['Market Cap YoY'] if data['Market Cap YoY'] is not None else float('nan') for data in market_cap_data],
            marker=dict(
                color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [data['Company'] for data in market_cap_data]],
                line=dict(
                    color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [data['Company'] for data in market_cap_data]],
                    width=14,
                ),
            ),
        )]
    )
    
    # Add frames for animation
    market_cap_fig.frames = frames
    
    # Generate tick values based on data
    tick_vals, tick_text = get_dynamic_tick_values(max_market_cap * 1.1, is_trillion=True)
    
    # Update layout with animation controls
    update_chart_layout(
        fig=market_cap_fig,
        title=f"Market Capitalization ({selected_year})",
        x_title="Market Capitalization (USD)",
        max_value=max_market_cap * 1.1,
        tick_vals=tick_vals,
        tick_text=tick_text,
        year=selected_year,
        height=500,
        use_default_annotation=True,
        show_animation_buttons=True,
    )
    
    # Display the chart
    st.plotly_chart(market_cap_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Market Capitalization", selected_year)
else:
    st.info(f"No market cap data available for {selected_year}")

end_snap_section()

# Add spacing
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# Revenue Visualization
begin_snap_section("revenue_animation")
st.subheader("Revenue")
render_standard_overview_comment("Revenue", selected_year)

# Create Revenue visualization
if revenue_data:
    # Create animated visualization with frames for different years
    years = [y for y in range(2010, selected_year + 1) if y in available_years]
    max_revenue = 0
    frames = []
    
    # Create data for each year to enable animation
    for year in years:
        year_data = []
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and metrics.get('revenue') is not None:
                year_data.append({
                    'Company': company,
                    'Revenue': metrics.get('revenue')
                })
                max_revenue = max(max_revenue, metrics.get('revenue'))
        
        if year_data:
            # Sort by revenue descending
            year_data = sorted(year_data, key=lambda x: x['Revenue'], reverse=True)
            
            # Create frame for this year
            company_list = [d['Company'] for d in year_data]
            values = [d['Revenue'] for d in year_data]
            colors = [COMPANY_COLORS.get(company, ['#808080'])[0] for company in company_list]
            
            frame = create_consistent_frame(
                companies=company_list,
                values=values,
                year=year,
                max_overall_value=max_revenue * 1.1,  # Add 10% margin
                title='Revenue',
                tick_vals=None,  # Will be set by the dynamic function
                tick_text=None,  # Will be set by the dynamic function
                format_func=format_large_number,
                hover_template="<b>%{customdata[0]}</b><br>Revenue: %{customdata[1]}<extra></extra>",
                colors=colors
            )
            frames.append(frame)
    
    # Create initial visualization
    revenue_fig = go.Figure(
        data=[go.Bar(
            y=[data['Company'] for data in revenue_data],
            x=[data['Revenue'] for data in revenue_data],
            orientation='h',
            name="Revenue",
            textposition='outside',
            texttemplate='%{text}',
            text=[format_large_number(data['Revenue']) for data in revenue_data],
            hovertemplate="<b>%{y}</b><br>Revenue: %{text}<br>YoY Change: %{customdata:.1f}%<extra></extra>",
            customdata=[data['Revenue YoY'] if data['Revenue YoY'] is not None else float('nan') for data in revenue_data],
            marker=dict(
                color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [data['Company'] for data in revenue_data]],
                line=dict(
                    color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [data['Company'] for data in revenue_data]],
                    width=14,
                ),
            ),
        )]
    )
    
    # Add frames for animation
    revenue_fig.frames = frames
    
    # Generate tick values based on data
    tick_vals, tick_text = get_dynamic_tick_values(max_revenue * 1.1)
    
    # Update layout with animation controls
    update_chart_layout(
        fig=revenue_fig,
        title=f"Revenue ({selected_year})",
        x_title="Revenue (USD)",
        max_value=max_revenue * 1.1,
        tick_vals=tick_vals,
        tick_text=tick_text,
        year=selected_year,
        height=500,
        use_default_annotation=True,
        show_animation_buttons=True,
    )
    
    # Display the chart
    st.plotly_chart(revenue_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Revenue", selected_year)
else:
    st.info(f"No revenue data available for {selected_year}")

end_snap_section()

# Add spacing
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# Net Income Visualization
begin_snap_section("net_income_animation")
st.subheader("Net Income")
render_standard_overview_comment("Net Income", selected_year)

# Create Net Income visualization
if net_income_data:
    # Create animated visualization with frames for different years
    years = [y for y in range(2010, selected_year + 1) if y in available_years]
    max_net_income = 0
    frames = []
    
    # Create data for each year to enable animation
    for year in years:
        year_data = []
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and metrics.get('net_income') is not None:
                year_data.append({
                    'Company': company,
                    'Net Income': metrics.get('net_income')
                })
                max_net_income = max(max_net_income, metrics.get('net_income'))
        
        if year_data:
            # Sort by net income descending
            year_data = sorted(year_data, key=lambda x: x['Net Income'], reverse=True)
            
            # Create frame for this year
            company_list = [d['Company'] for d in year_data]
            values = [d['Net Income'] for d in year_data]
            colors = [COMPANY_COLORS.get(company, ['#808080'])[0] for company in company_list]
            
            frame = create_consistent_frame(
                companies=company_list,
                values=values,
                year=year,
                max_overall_value=max_net_income * 1.1,  # Add 10% margin
                title='Net Income',
                tick_vals=None,  # Will be set by the dynamic function
                tick_text=None,  # Will be set by the dynamic function
                format_func=format_large_number,
                hover_template="<b>%{customdata[0]}</b><br>Net Income: %{customdata[1]}<extra></extra>",
                colors=colors
            )
            frames.append(frame)
    
    # Create initial visualization
    net_income_fig = go.Figure(
        data=[go.Bar(
            y=[data['Company'] for data in net_income_data],
            x=[data['Net Income'] for data in net_income_data],
            orientation='h',
            name="Net Income",
            textposition='outside',
            texttemplate='%{text}',
            text=[format_large_number(data['Net Income']) for data in net_income_data],
            hovertemplate="<b>%{y}</b><br>Net Income: %{text}<br>YoY Change: %{customdata:.1f}%<extra></extra>",
            customdata=[data['Net Income YoY'] if data['Net Income YoY'] is not None else float('nan') for data in net_income_data],
            marker=dict(
                color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [data['Company'] for data in net_income_data]],
                line=dict(
                    color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [data['Company'] for data in net_income_data]],
                    width=14,
                ),
            ),
        )]
    )
    
    # Add frames for animation
    net_income_fig.frames = frames
    
    # Generate tick values based on data
    tick_vals, tick_text = get_dynamic_tick_values(max_net_income * 1.1)
    
    # Update layout with animation controls
    update_chart_layout(
        fig=net_income_fig,
        title=f"Net Income ({selected_year})",
        x_title="Net Income (USD)",
        max_value=max_net_income * 1.1,
        tick_vals=tick_vals,
        tick_text=tick_text,
        year=selected_year,
        height=500,
        use_default_annotation=True,
        show_animation_buttons=True,
    )
    
    # Display the chart
    st.plotly_chart(net_income_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Net Income", selected_year)
else:
    st.info(f"No net income data available for {selected_year}")

end_snap_section()

# Add spacing
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# Total Assets Visualization
begin_snap_section("assets_animation")
st.subheader("Total Assets")
render_standard_overview_comment("Total Assets", selected_year)

# Sort assets data
if assets_data:
    assets_data = sorted(assets_data, key=lambda x: x['Assets'], reverse=True)
    
    # Create animated visualization with frames for different years
    years = [y for y in range(2010, selected_year + 1) if y in available_years]
    max_assets = 0
    frames = []
    
    # Create data for each year to enable animation
    for year in years:
        year_data = []
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and metrics.get('total_assets') is not None:
                year_data.append({
                    'Company': company,
                    'Assets': metrics.get('total_assets')
                })
                max_assets = max(max_assets, metrics.get('total_assets'))
        
        if year_data:
            # Sort by assets descending
            year_data = sorted(year_data, key=lambda x: x['Assets'], reverse=True)
            
            # Create frame for this year
            company_list = [d['Company'] for d in year_data]
            values = [d['Assets'] for d in year_data]
            colors = [COMPANY_COLORS.get(company, ['#808080'])[0] for company in company_list]
            
            frame = create_consistent_frame(
                companies=company_list,
                values=values,
                year=year,
                max_overall_value=max_assets * 1.1,  # Add 10% margin
                title='Total Assets',
                tick_vals=None,  # Will be set by the dynamic function
                tick_text=None,  # Will be set by the dynamic function
                format_func=format_large_number,
                hover_template="<b>%{customdata[0]}</b><br>Total Assets: %{customdata[1]}<extra></extra>",
                colors=colors
            )
            frames.append(frame)
    
    # Create initial visualization
    assets_fig = go.Figure(
        data=[go.Bar(
            y=[d['Company'] for d in assets_data],
            x=[d['Assets'] for d in assets_data],
            orientation='h',
            name="Total Assets",
            textposition='outside',
            texttemplate='%{text}',
            text=[format_large_number(d['Assets']) for d in assets_data],
            hovertemplate="<b>%{y}</b><br>Total Assets: %{text}<br>YoY Change: %{customdata:.1f}%<extra></extra>",
            customdata=[d['Assets YoY'] if d.get('Assets YoY') is not None else float('nan') for d in assets_data],
            marker=dict(
                color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in assets_data]],
                line=dict(
                    color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in assets_data]],
                    width=14,
                ),
            ),
        )]
    )
    
    # Add frames for animation
    assets_fig.frames = frames
    
    # Generate tick values based on data
    tick_vals, tick_text = get_dynamic_tick_values(max_assets * 1.1)
    
    # Update layout with animation controls
    update_chart_layout(
        fig=assets_fig,
        title=f"Total Assets ({selected_year})",
        x_title="Total Assets (USD)",
        max_value=max_assets * 1.1,
        tick_vals=tick_vals,
        tick_text=tick_text,
        year=selected_year,
        height=500,
        use_default_annotation=True,
        show_animation_buttons=True,
    )
    
    # Display the chart
    st.plotly_chart(assets_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Total Assets", selected_year)
else:
    st.info(f"No total assets data available for {selected_year}")

end_snap_section()

# Add additional metrics
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("cash_animation")
st.subheader("Cash Balance")
render_standard_overview_comment("Cash Balance", selected_year)

# Sort cash balance data
if cash_balance_data:
    cash_balance_data = sorted(cash_balance_data, key=lambda x: x['Cash Balance'], reverse=True)
    
    # Create animated visualization with frames for different years
    years = [y for y in range(2010, selected_year + 1) if y in available_years]
    max_cash = 0
    frames = []
    
    # Create data for each year to enable animation
    for year in years:
        year_data = []
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and metrics.get('cash_balance') is not None:
                year_data.append({
                    'Company': company,
                    'Cash Balance': metrics.get('cash_balance')
                })
                max_cash = max(max_cash, metrics.get('cash_balance'))
        
        if year_data:
            # Sort by cash balance descending
            year_data = sorted(year_data, key=lambda x: x['Cash Balance'], reverse=True)
            
            # Create frame for this year
            company_list = [d['Company'] for d in year_data]
            values = [d['Cash Balance'] for d in year_data]
            colors = [COMPANY_COLORS.get(company, ['#808080'])[0] for company in company_list]
            
            frame = create_consistent_frame(
                companies=company_list,
                values=values,
                year=year,
                max_overall_value=max_cash * 1.1,  # Add 10% margin
                title='Cash Balance',
                tick_vals=None,  # Will be set by the dynamic function
                tick_text=None,  # Will be set by the dynamic function
                format_func=format_large_number,
                hover_template="<b>%{customdata[0]}</b><br>Cash Balance: %{customdata[1]}<extra></extra>",
                colors=colors
            )
            frames.append(frame)
    
    # Create initial visualization
    cash_fig = go.Figure(
        data=[go.Bar(
            y=[d['Company'] for d in cash_balance_data],
            x=[d['Cash Balance'] for d in cash_balance_data],
            orientation='h',
            name="Cash Balance",
            textposition='outside',
            texttemplate='%{text}',
            text=[format_large_number(d['Cash Balance']) for d in cash_balance_data],
            hovertemplate="<b>%{y}</b><br>Cash Balance: %{text}<br>YoY Change: %{customdata:.1f}%<extra></extra>",
            customdata=[d['Cash Balance YoY'] if d.get('Cash Balance YoY') is not None else float('nan') for d in cash_balance_data],
            marker=dict(
                color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in cash_balance_data]],
                line=dict(
                    color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in cash_balance_data]],
                    width=14,
                ),
            ),
        )]
    )
    
    # Add frames for animation
    cash_fig.frames = frames
    
    # Generate tick values based on data
    tick_vals, tick_text = get_dynamic_tick_values(max_cash * 1.1)
    
    # Update layout with animation controls
    update_chart_layout(
        fig=cash_fig,
        title=f"Cash Balance ({selected_year})",
        x_title="Cash Balance (USD)",
        max_value=max_cash * 1.1,
        tick_vals=tick_vals,
        tick_text=tick_text,
        year=selected_year,
        height=500,
        use_default_annotation=True,
        show_animation_buttons=True,
    )
    
    # Display the chart
    st.plotly_chart(cash_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Cash Balance", selected_year)
else:
    st.info(f"No cash balance data available for {selected_year}")

end_snap_section()

# Add R&D Spending Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("rd_animation")
st.subheader("R&D Spending")
render_standard_overview_comment("R&D Spending", selected_year)

# Sort R&D data
if rd_data:
    rd_data = sorted(rd_data, key=lambda x: x['R&D'], reverse=True)
    
    # Create animated visualization with frames for different years
    years = [y for y in range(2010, selected_year + 1) if y in available_years]
    max_rd = 0
    frames = []
    
    # Create data for each year to enable animation
    for year in years:
        year_data = []
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and metrics.get('rd') is not None:
                year_data.append({
                    'Company': company,
                    'R&D': metrics.get('rd')
                })
                max_rd = max(max_rd, metrics.get('rd'))
        
        if year_data:
            # Sort by R&D spending descending
            year_data = sorted(year_data, key=lambda x: x['R&D'], reverse=True)
            
            # Create frame for this year
            company_list = [d['Company'] for d in year_data]
            values = [d['R&D'] for d in year_data]
            colors = [COMPANY_COLORS.get(company, ['#808080'])[0] for company in company_list]
            
            frame = create_consistent_frame(
                companies=company_list,
                values=values,
                year=year,
                max_overall_value=max_rd * 1.1,  # Add 10% margin
                title='R&D Spending',
                tick_vals=None,
                tick_text=None,
                format_func=format_large_number,
                hover_template="<b>%{customdata[0]}</b><br>R&D Spending: %{customdata[1]}<extra></extra>",
                colors=colors
            )
            frames.append(frame)
    
    # Create initial visualization
    rd_fig = go.Figure(
        data=[go.Bar(
            y=[d['Company'] for d in rd_data],
            x=[d['R&D'] for d in rd_data],
            orientation='h',
            name="R&D",
            textposition='outside',
            texttemplate='%{text}',
            text=[format_large_number(d['R&D']) for d in rd_data],
            hovertemplate="<b>%{y}</b><br>R&D Spending: %{text}<br>YoY Change: %{customdata:.1f}%<extra></extra>",
            customdata=[d['R&D YoY'] if d.get('R&D YoY') is not None else float('nan') for d in rd_data],
            marker=dict(
                color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in rd_data]],
                line=dict(
                    color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in rd_data]],
                    width=14,
                ),
            ),
        )]
    )
    
    # Add frames for animation
    rd_fig.frames = frames
    
    # Generate tick values based on data
    tick_vals, tick_text = get_dynamic_tick_values(max_rd * 1.1)
    
    # Update layout with animation controls
    update_chart_layout(
        fig=rd_fig,
        title=f"R&D Spending ({selected_year})",
        x_title="R&D Spending (USD)",
        max_value=max_rd * 1.1,
        tick_vals=tick_vals,
        tick_text=tick_text,
        year=selected_year,
        height=500,
        use_default_annotation=True,
        show_animation_buttons=True,
    )
    
    # Display the chart
    st.plotly_chart(rd_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("R&D Spending", selected_year)
else:
    st.info(f"No R&D spending data available for {selected_year}")

end_snap_section()

# Add Employee Count Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("employees_animation")
st.subheader("Employee Count")
render_standard_overview_comment("Employee Count", selected_year)

# Sort employee data
if employee_data:
    employee_data = sorted(employee_data, key=lambda x: x['Employees'], reverse=True)
    
    # Create animated visualization with frames for different years
    years = [y for y in range(2010, selected_year + 1) if y in available_years]
    max_employees = 0
    frames = []
    
    # Create data for each year to enable animation
    for year in years:
        year_data = []
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and metrics.get('employees') is not None:
                year_data.append({
                    'Company': company,
                    'Employees': metrics.get('employees')
                })
                max_employees = max(max_employees, metrics.get('employees'))
        
        if year_data:
            # Sort by employee count descending
            year_data = sorted(year_data, key=lambda x: x['Employees'], reverse=True)
            
            # Create frame for this year
            company_list = [d['Company'] for d in year_data]
            values = [d['Employees'] for d in year_data]
            colors = [COMPANY_COLORS.get(company, ['#808080'])[0] for company in company_list]
            
            # Custom formatter for employee count (integers with commas)
            def format_employee_count(val):
                return f"{int(val):,}"
            
            frame = create_consistent_frame(
                companies=company_list,
                values=values,
                year=year,
                max_overall_value=float(max_employees) * 1.1,  # Add 10% margin
                title='Employee Count',
                tick_vals=None,
                tick_text=None,
                format_func=format_employee_count,
                hover_template="<b>%{customdata[0]}</b><br>Employees: %{customdata[1]}<extra></extra>",
                colors=colors
            )
            frames.append(frame)
    
    # Create initial visualization
    employee_fig = go.Figure(
        data=[go.Bar(
            y=[d['Company'] for d in employee_data],
            x=[d['Employees'] for d in employee_data],
            orientation='h',
            name="Employees",
            textposition='outside',
            texttemplate='%{text}',  # Keep consistent with animation helper
            text=[f"{int(d['Employees']):,}" for d in employee_data],
            hovertemplate="<b>%{y}</b><br>Employees: %{x:,.0f}<extra></extra>",
            marker=dict(
                color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in employee_data]],
                line=dict(
                    color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in employee_data]],
                    width=14,
                ),
            ),
        )]
    )
    
    # Add frames for animation
    employee_fig.frames = frames
    
    # Generate tick values based on data (custom for employees to use integers)
    tick_interval = 50000  # 50k intervals
    # Make sure we have at least 5 ticks
    while (float(max_employees) / tick_interval) < 5:
        tick_interval = tick_interval // 2
    tick_vals = list(range(0, int(float(max_employees) * 1.1) + tick_interval, tick_interval))
    tick_text = [f"{val:,}" for val in tick_vals]
    
    # Update layout with animation controls
    update_chart_layout(
        fig=employee_fig,
        title=f"Employee Count ({selected_year})",
        x_title="Number of Employees",
        max_value=float(max_employees) * 1.1,
        tick_vals=tick_vals,
        tick_text=tick_text,
        year=selected_year,
        height=500,
        use_default_annotation=True,
        show_animation_buttons=True,
    )
    
    # Display the chart
    st.plotly_chart(employee_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Employee Count", selected_year)
else:
    st.info(f"No employee count data available for {selected_year}")

end_snap_section()
    
# Add Long-Term Debt Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("debt_animation")
st.subheader("Long-Term Debt")
render_standard_overview_comment("Long-Term Debt", selected_year)

# Sort debt data
if debt_data:
    debt_data = sorted(debt_data, key=lambda x: x['Debt'], reverse=True)
    
    # Create animated visualization with frames for different years
    years = [y for y in range(2010, selected_year + 1) if y in available_years]
    max_debt = 0
    frames = []
    
    # Create data for each year to enable animation
    for year in years:
        year_data = []
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and metrics.get('debt') is not None:
                year_data.append({
                    'Company': company,
                    'Debt': metrics.get('debt')
                })
                max_debt = max(max_debt, metrics.get('debt'))
        
        if year_data:
            # Sort by debt descending
            year_data = sorted(year_data, key=lambda x: x['Debt'], reverse=True)
            
            # Create frame for this year
            company_list = [d['Company'] for d in year_data]
            values = [d['Debt'] for d in year_data]
            colors = [COMPANY_COLORS.get(company, ['#808080'])[0] for company in company_list]
            
            frame = create_consistent_frame(
                companies=company_list,
                values=values,
                year=year,
                max_overall_value=max_debt * 1.1,  # Add 10% margin
                title='Long-Term Debt',
                tick_vals=None,
                tick_text=None,
                format_func=format_large_number,
                hover_template="<b>%{customdata[0]}</b><br>Debt: %{customdata[1]}<extra></extra>",
                colors=colors
            )
            frames.append(frame)
    
    # Create initial visualization
    debt_fig = go.Figure(
        data=[go.Bar(
            y=[d['Company'] for d in debt_data],
            x=[d['Debt'] for d in debt_data],
            orientation='h',
            name="Debt",
            textposition='outside',
            texttemplate='%{text}',
            text=[format_large_number(d['Debt']) for d in debt_data],
            hovertemplate="<b>%{y}</b><br>Debt: %{text}<br>YoY Change: %{customdata:.1f}%<extra></extra>",
            customdata=[d['Debt YoY'] if d.get('Debt YoY') is not None else float('nan') for d in debt_data],
            marker=dict(
                color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in debt_data]],
                line=dict(
                    color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in debt_data]],
                    width=14,
                ),
            ),
        )]
    )
    
    # Add frames for animation
    debt_fig.frames = frames
    
    # Generate tick values based on data
    tick_vals, tick_text = get_dynamic_tick_values(max_debt * 1.1)
    
    # Update layout with animation controls
    update_chart_layout(
        fig=debt_fig,
        title=f"Long-Term Debt ({selected_year})",
        x_title="Long-Term Debt (USD)",
        max_value=max_debt * 1.1,
        tick_vals=tick_vals,
        tick_text=tick_text,
        year=selected_year,
        height=500,
        use_default_annotation=True,
        show_animation_buttons=True,
    )
    
    # Display the chart
    st.plotly_chart(debt_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Long-Term Debt", selected_year)
else:
    st.info(f"No debt data available for {selected_year}")

end_snap_section()

# Add Operating Income Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("operating_income_animation")
st.subheader("Operating Income")
render_standard_overview_comment("Operating Income", selected_year)

# Sort operating income data
if operating_income_data:
    operating_income_data = sorted(operating_income_data, key=lambda x: x['Operating Income'], reverse=True)
    
    # Create animated visualization with frames for different years
    years = [y for y in range(2010, selected_year + 1) if y in available_years]
    max_operating_income = 0
    frames = []
    
    # Create data for each year to enable animation
    for year in years:
        year_data = []
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and metrics.get('operating_income') is not None:
                year_data.append({
                    'Company': company,
                    'Operating Income': metrics.get('operating_income')
                })
                max_operating_income = max(max_operating_income, metrics.get('operating_income'))
        
        if year_data:
            # Sort by operating income descending
            year_data = sorted(year_data, key=lambda x: x['Operating Income'], reverse=True)
            
            # Create frame for this year
            company_list = [d['Company'] for d in year_data]
            values = [d['Operating Income'] for d in year_data]
            colors = [COMPANY_COLORS.get(company, ['#808080'])[0] for company in company_list]
            
            frame = create_consistent_frame(
                companies=company_list,
                values=values,
                year=year,
                max_overall_value=max_operating_income * 1.1,  # Add 10% margin
                title='Operating Income',
                tick_vals=None,  # Will be set by the dynamic function
                tick_text=None,  # Will be set by the dynamic function
                format_func=format_large_number,
                hover_template="<b>%{customdata[0]}</b><br>Operating Income: %{customdata[1]}<extra></extra>",
                colors=colors
            )
            frames.append(frame)
    
    # Create initial visualization
    operating_income_fig = go.Figure(
        data=[go.Bar(
            y=[d['Company'] for d in operating_income_data],
            x=[d['Operating Income'] for d in operating_income_data],
            orientation='h',
            name="Operating Income",
            textposition='outside',
            texttemplate='%{text}',
            text=[format_large_number(d['Operating Income']) for d in operating_income_data],
            hovertemplate="<b>%{y}</b><br>Operating Income: %{text}<br>YoY Change: %{customdata:.1f}%<extra></extra>",
            customdata=[d['Operating Income YoY'] if d.get('Operating Income YoY') is not None else float('nan') for d in operating_income_data],
            marker=dict(
                color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in operating_income_data]],
                line=dict(
                    color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in operating_income_data]],
                    width=14,
                ),
            ),
        )]
    )
    
    # Add frames for animation
    operating_income_fig.frames = frames
    
    # Generate tick values based on data
    tick_vals, tick_text = get_dynamic_tick_values(max_operating_income * 1.1)
    
    # Update layout with animation controls
    update_chart_layout(
        fig=operating_income_fig,
        title=f"Operating Income ({selected_year})",
        x_title="Operating Income (USD)",
        max_value=max_operating_income * 1.1,
        tick_vals=tick_vals,
        tick_text=tick_text,
        year=selected_year,
        height=500,
        use_default_annotation=True,
        show_animation_buttons=True,
    )
    
    # Display the chart
    st.plotly_chart(operating_income_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Operating Income", selected_year)
else:
    st.info(f"No operating income data available for {selected_year}")

end_snap_section()

# Add Cost of Revenue Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("cost_of_revenue_animation")
st.subheader("Cost of Revenue")
render_standard_overview_comment("Cost of Revenue", selected_year)

# Sort cost of revenue data
if cost_of_revenue_data:
    cost_of_revenue_data = sorted(cost_of_revenue_data, key=lambda x: x['Cost of Revenue'], reverse=True)
    
    # Create animated visualization with frames for different years
    years = [y for y in range(2010, selected_year + 1) if y in available_years]
    max_cost_of_revenue = 0
    frames = []
    
    # Create data for each year to enable animation
    for year in years:
        year_data = []
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and metrics.get('cost_of_revenue') is not None:
                year_data.append({
                    'Company': company,
                    'Cost of Revenue': metrics.get('cost_of_revenue')
                })
                max_cost_of_revenue = max(max_cost_of_revenue, metrics.get('cost_of_revenue'))
        
        if year_data:
            # Sort by cost of revenue descending
            year_data = sorted(year_data, key=lambda x: x['Cost of Revenue'], reverse=True)
            
            # Create frame for this year
            company_list = [d['Company'] for d in year_data]
            values = [d['Cost of Revenue'] for d in year_data]
            colors = [COMPANY_COLORS.get(company, ['#808080'])[0] for company in company_list]
            
            frame = create_consistent_frame(
                companies=company_list,
                values=values,
                year=year,
                max_overall_value=max_cost_of_revenue * 1.1,  # Add 10% margin
                title='Cost of Revenue',
                tick_vals=None,  # Will be set by the dynamic function
                tick_text=None,  # Will be set by the dynamic function
                format_func=format_large_number,
                hover_template="<b>%{customdata[0]}</b><br>Cost of Revenue: %{customdata[1]}<extra></extra>",
                colors=colors
            )
            frames.append(frame)
    
    # Create initial visualization
    cost_of_revenue_fig = go.Figure(
        data=[go.Bar(
            y=[d['Company'] for d in cost_of_revenue_data],
            x=[d['Cost of Revenue'] for d in cost_of_revenue_data],
            orientation='h',
            name="Cost of Revenue",
            textposition='outside',
            texttemplate='%{text}',
            text=[format_large_number(d['Cost of Revenue']) for d in cost_of_revenue_data],
            hovertemplate="<b>%{y}</b><br>Cost of Revenue: %{text}<br>YoY Change: %{customdata:.1f}%<extra></extra>",
            customdata=[d['Cost of Revenue YoY'] if d.get('Cost of Revenue YoY') is not None else float('nan') for d in cost_of_revenue_data],
            marker=dict(
                color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in cost_of_revenue_data]],
                line=dict(
                    color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in cost_of_revenue_data]],
                    width=14,
                ),
            ),
        )]
    )
    
    # Add frames for animation
    cost_of_revenue_fig.frames = frames
    
    # Generate tick values based on data
    tick_vals, tick_text = get_dynamic_tick_values(max_cost_of_revenue * 1.1)
    
    # Update layout with animation controls
    update_chart_layout(
        fig=cost_of_revenue_fig,
        title=f"Cost of Revenue ({selected_year})",
        x_title="Cost of Revenue (USD)",
        max_value=max_cost_of_revenue * 1.1,
        tick_vals=tick_vals,
        tick_text=tick_text,
        year=selected_year,
        height=500,
        use_default_annotation=True,
        show_animation_buttons=True,
    )
    
    # Display the chart
    st.plotly_chart(cost_of_revenue_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Cost of Revenue", selected_year)
else:
    st.info(f"No cost of revenue data available for {selected_year}")

end_snap_section()

# Add Capital Expenditure Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("capex_animation")
st.subheader("Capital Expenditure (Capex)")
render_standard_overview_comment("Capital Expenditure (Capex)", selected_year)

# Sort capex data
if capex_data:
    capex_data = sorted(capex_data, key=lambda x: x['Capex'], reverse=True)
    
    # Create animated visualization with frames for different years
    years = [y for y in range(2010, selected_year + 1) if y in available_years]
    max_capex = 0
    frames = []
    
    # Create data for each year to enable animation
    for year in years:
        year_data = []
        for company in companies:
            metrics = data_processor.get_metrics(company, year)
            if metrics and metrics.get('capex') is not None:
                year_data.append({
                    'Company': company,
                    'Capex': metrics.get('capex')
                })
                max_capex = max(max_capex, metrics.get('capex'))
        
        if year_data:
            # Sort by capex descending
            year_data = sorted(year_data, key=lambda x: x['Capex'], reverse=True)
            
            # Create frame for this year
            company_list = [d['Company'] for d in year_data]
            values = [d['Capex'] for d in year_data]
            colors = [COMPANY_COLORS.get(company, ['#808080'])[0] for company in company_list]
            
            frame = create_consistent_frame(
                companies=company_list,
                values=values,
                year=year,
                max_overall_value=max_capex * 1.1,  # Add 10% margin
                title='Capital Expenditure',
                tick_vals=None,  # Will be set by the dynamic function
                tick_text=None,  # Will be set by the dynamic function
                format_func=format_large_number,
                hover_template="<b>%{customdata[0]}</b><br>Capex: %{customdata[1]}<extra></extra>",
                colors=colors
            )
            frames.append(frame)
    
    # Create initial visualization
    capex_fig = go.Figure(
        data=[go.Bar(
            y=[d['Company'] for d in capex_data],
            x=[d['Capex'] for d in capex_data],
            orientation='h',
            name="Capex",
            textposition='outside',
            texttemplate='%{text}',
            text=[format_large_number(d['Capex']) for d in capex_data],
            hovertemplate="<b>%{y}</b><br>Capital Expenditure: %{text}<br>YoY Change: %{customdata:.1f}%<extra></extra>",
            customdata=[d['Capex YoY'] if d.get('Capex YoY') is not None else float('nan') for d in capex_data],
            marker=dict(
                color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in capex_data]],
                line=dict(
                    color=[COMPANY_COLORS.get(company, ['#808080'])[0] for company in [d['Company'] for d in capex_data]],
                    width=14,
                ),
            ),
        )]
    )
    
    # Add frames for animation
    capex_fig.frames = frames
    
    # Generate tick values based on data
    tick_vals, tick_text = get_dynamic_tick_values(max_capex * 1.1)
    
    # Update layout with animation controls
    update_chart_layout(
        fig=capex_fig,
        title=f"Capital Expenditure ({selected_year})",
        x_title="Capital Expenditure (USD)",
        max_value=max_capex * 1.1,
        tick_vals=tick_vals,
        tick_text=tick_text,
        year=selected_year,
        height=500,
        use_default_annotation=True,
        show_animation_buttons=True,
    )
    
    # Display the chart
    st.plotly_chart(capex_fig, use_container_width=True, config=plotly_config)
    render_standard_overview_post_comment("Capital Expenditure (Capex)", selected_year)
else:
    st.info(f"No capex data available for {selected_year}")

end_snap_section()

# Executive Summary (moved to bottom for now)
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("executive_summary")
render_executive_summary_section()
end_snap_section()

st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
_render_overview_download_section(data_processor, selected_year, selected_quarter)

# Add spacing before footer
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# Add footer note
st.markdown(
    """
    <div style="margin-top: 50px; padding: 10px; background-color: #f8f9fa; border-radius: 8px; text-align: center;">
      <small>Tip: Use the ▶ / ❚❚ controls next to each chart title to animate across years.</small>
    </div>
    """,
    unsafe_allow_html=True,
)
