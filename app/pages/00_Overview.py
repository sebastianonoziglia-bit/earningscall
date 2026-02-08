import streamlit as st
# Set page config - Must be the first Streamlit command
st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime
import numpy as np
import textwrap
import json
import requests
import streamlit.components.v1 as components
from pathlib import Path
from data_processor import FinancialDataProcessor
from subscriber_data_processor import SubscriberDataProcessor
from utils.state_management import get_data_processor, initialize_session_state
from utils.animation_helper import update_chart_layout, create_consistent_frame, get_dynamic_tick_values, create_animation_buttons
from utils.styles import get_page_style
from utils.components import load_company_logos
from utils.data_loader import CONTINENT_MAPPINGS, AD_MACRO_CATEGORIES

st.markdown(get_page_style(), unsafe_allow_html=True)

# Streamlit markdown can treat indented HTML as a code block. Normalize HTML blocks to avoid that.
def _html_block(html: str) -> str:
    dedented = textwrap.dedent(html)
    return "\n".join(line.lstrip() for line in dedented.splitlines()).strip()

st.markdown(
    _html_block(
        """
        <style>
        body.overview-dark .stApp,
        body.overview-dark [data-testid="stAppViewContainer"],
        body.overview-dark section.main,
        body.overview-dark .block-container {
            background: #0B1220 !important;
            color: #F8FAFC !important;
        }

        body.overview-dark [data-testid="stMarkdownContainer"],
        body.overview-dark [data-testid="stMarkdownContainer"] p,
        body.overview-dark [data-testid="stMarkdownContainer"] li,
        body.overview-dark [data-testid="stMarkdownContainer"] span,
        body.overview-dark [data-testid="stMarkdownContainer"] strong {
            color: #E2E8F0 !important;
        }

        body.overview-dark h1,
        body.overview-dark h2,
        body.overview-dark h3,
        body.overview-dark h4,
        body.overview-dark h5,
        body.overview-dark h6,
        body.overview-dark .stMarkdown h1,
        body.overview-dark .stMarkdown h2,
        body.overview-dark .stMarkdown h3,
        body.overview-dark .stMarkdown h4,
        body.overview-dark .stMarkdown h5,
        body.overview-dark .stMarkdown h6 {
            color: #F8FAFC !important;
        }

        body.overview-dark .overview-summary-card {
            background: #111827 !important;
            color: #F8FAFC !important;
            box-shadow: 0 14px 28px rgba(2, 6, 23, 0.35) !important;
        }

        body.overview-dark .overview-summary-card * {
            color: inherit !important;
        }

        body.overview-dark .ov-map-summary {
            position: absolute;
            top: 228px;
            left: 18px;
            z-index: 6;
            max-width: min(340px, 40vw);
            height: clamp(300px, 48vh, 460px);
            background: rgba(11, 18, 32, 0.6);
            border-radius: 12px;
            padding: 10px 12px;
            box-shadow: none;
            overflow-y: auto;
            pointer-events: auto;
        }

        body.overview-dark .ov-map-summary-title {
            font-size: 0.95rem;
            color: #94A3B8;
            margin-bottom: 6px;
        }

        body.overview-dark .ov-map-summary-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: #F8FAFC;
            margin-bottom: 12px;
        }

        body.overview-dark .ov-map-summary-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        body.overview-dark .ov-map-summary-row {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            font-size: 0.9rem;
            font-weight: 600;
            color: #E2E8F0;
        }

        body.overview-dark .ov-map-summary-sub {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            font-size: 0.78rem;
            color: #94A3B8;
            padding-left: 10px;
        }

        body.overview-dark .ov-macro-label {
            margin: 4px 0 8px;
            font-size: 0.8rem;
            color: #94A3B8;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        body.overview-dark .ov-map-wrap {
            position: relative;
            min-height: 700px;
        }

        body.overview-dark .ov-macro-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 10px 0 14px 0;
        }

        body.overview-dark .ov-macro-pill {
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

        body.overview-dark .ov-macro-pill.positive {
            border-color: rgba(34, 197, 94, 0.45);
            color: #BBF7D0;
        }

        body.overview-dark .ov-macro-pill.negative {
            border-color: rgba(248, 113, 113, 0.5);
            color: #FECACA;
        }

        body.overview-dark div[data-baseweb="select"] > div,
        body.overview-dark div[data-baseweb="select"] > div > div,
        body.overview-dark input,
        body.overview-dark textarea {
            background: #0F172A !important;
            color: #F8FAFC !important;
            border-color: rgba(148, 163, 184, 0.35) !important;
        }

        body.overview-dark .stMultiSelect [data-baseweb="tag"] {
            background: #0F172A !important;
            color: #F8FAFC !important;
            border: 1px solid rgba(59, 130, 246, 0.45) !important;
        }

        body.overview-dark label,
        body.overview-dark .stRadio label,
        body.overview-dark .stCheckbox label {
            color: #E2E8F0 !important;
        }

        body.overview-dark .js-plotly-plot .xtick text,
        body.overview-dark .js-plotly-plot .ytick text,
        body.overview-dark .js-plotly-plot .gtitle text,
        body.overview-dark .js-plotly-plot .legend text,
        body.overview-dark .js-plotly-plot .colorbar text {
            fill: #E2E8F0 !important;
        }

        body.overview-dark .js-plotly-plot .bglayer .bg {
            fill: rgba(0, 0, 0, 0) !important;
        }

        body.overview-dark .js-plotly-plot .gridlayer path {
            stroke: rgba(148, 163, 184, 0.12) !important;
        }

        </style>
        """
    ),
    unsafe_allow_html=True,
)
components.html(
    "<script>window.parent.document.body.classList.add('overview-dark');</script>",
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
    st.markdown(
        f"<section class='ov-snap-section' data-ov-section='{section_id}'>",
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
        return sorted([int(y) for y in years])

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
def _load_country_advertising_df() -> pd.DataFrame:
    path = Path(__file__).resolve().parents[1] / "attached_assets" / "Country_Advertising_Data_FullVi.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["Country"] = df["Country"].astype(str).str.strip()
    df["Metric_type"] = df["Metric_type"].astype(str).str.strip()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["Country", "Year", "Metric_type", "Value"])
    df["Year"] = df["Year"].astype(int)
    return df

# Configure Plotly
plotly_config = {
    'displayModeBar': True,
    'modeBarButtonsToRemove': [
        'zoom', 'pan', 'select', 'lasso2d', 'zoomIn', 'zoomOut',
        'autoScale', 'resetScale'
    ],
    'modeBarButtonsToAdd': ['fullscreen'],
    'displaylogo': False
}

begin_snap_section("overview_summary")

# Main app content
st.title("Overview - Financial Market Intelligence")

# Initialize data processor
data_processor = get_data_processor()

# Get companies and available years
companies = get_available_companies(data_processor)
available_years = get_available_years(data_processor)

# Year selector
selected_year = st.selectbox(
    "Select Year", 
    available_years, 
    index=len(available_years)-1  # Default to most recent year
)

st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

# SECTION 1 — GLOBAL CONTEXT (WORLD MAP)
st.subheader("The Global Media Economy")
st.markdown(
    "Global advertising is geographically distributed across regions and markets. "
    "Hover countries to view values.",
)

country_ad_df = _load_country_advertising_df()
if not country_ad_df.empty:
    show_by_country = st.checkbox(
        "By country",
        value=False,
        help="Toggle to show country-level detail; unchecked uses region view.",
    )
    view_mode = "By country" if show_by_country else "By region"

    region_options = ["Europe", "North America", "Asia Pacific", "South America", "Middle East & Africa"]
    region_col, _ = st.columns([0.3, 0.7])
    with region_col:
        region_choice = st.selectbox(
            "Region",
            ["Global"] + region_options,
            index=0,
            help="Global shows everything. By region colors countries uniformly by their region total.",
        )

    metric_types = sorted(country_ad_df["Metric_type"].dropna().unique().tolist())
    metric_col, _ = st.columns([0.34, 0.66])
    with metric_col:
        metric_choice = st.selectbox(
            "Advertising metric",
            ["All channels"] + metric_types,
            index=0,
            help="All channels aggregates all available advertising channels for each country.",
        )

    available_ad_years = sorted(country_ad_df["Year"].dropna().unique().tolist())
    # Use the app's selected year when available; otherwise pick the closest available <= selected year.
    year_for_map = selected_year
    if year_for_map not in available_ad_years:
        prior_years = [y for y in available_ad_years if y <= selected_year]
        year_for_map = max(prior_years) if prior_years else max(available_ad_years)

    macro_prev_years = [y for y in available_ad_years if y < year_for_map]
    macro_prev_year = max(macro_prev_years) if macro_prev_years else None
    macro_rows = []
    for macro, types in AD_MACRO_CATEGORIES.items():
        current_sum = country_ad_df[
            (country_ad_df["Year"] == int(year_for_map)) & (country_ad_df["Metric_type"].isin(types))
        ]["Value"].sum()
        prev_sum = 0.0
        if macro_prev_year is not None:
            prev_sum = country_ad_df[
                (country_ad_df["Year"] == int(macro_prev_year))
                & (country_ad_df["Metric_type"].isin(types))
            ]["Value"].sum()
        yoy = None
        if prev_sum:
            yoy = ((current_sum - prev_sum) / prev_sum) * 100.0
        macro_rows.append((macro, yoy))

    if macro_rows:
        if macro_prev_year is not None:
            macro_label = f"Macro YoY ({year_for_map} vs {macro_prev_year})"
        else:
            macro_label = f"Macro YoY ({year_for_map})"
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
                rows_html += (
                    f"<div class='ov-map-summary-row'><span>{idx}. {row.Country}</span>"
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
                        rows_html += (
                            f"<div class='ov-map-summary-sub'><span>{channel.Metric_type}</span>"
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
                rows_html += (
                    f"<div class='ov-map-summary-row'><span>{idx}. {row.Country}</span>"
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
                        rows_html += (
                            f"<div class='ov-map-summary-sub'><span>{channel.Metric_type}</span>"
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
                    textfont=dict(size=default_sizes, color="rgba(15, 23, 42, 0.9)", family="Poppins, system-ui, sans-serif"),
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
                        textfont=dict(size=override_sizes, color="rgba(15, 23, 42, 0.9)", family="Poppins, system-ui, sans-serif"),
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
                            color="#F8FAFC",
                            family="Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
                        ),
                        bgcolor="rgba(15, 23, 42, 0.92)",
                        bordercolor="#FFFFFF",
                        borderwidth=1,
                        borderpad=6,
                    )
                )
            if annotations:
                map_fig.update_layout(annotations=annotations)
        map_fig.update_geos(
            projection_type="natural earth",
            projection_scale=1.1,
            center=dict(lon=0, lat=0),
            showcoastlines=False,
            showcountries=True,
            countrycolor="rgba(15,23,42,0.12)",
            showframe=False,
            showland=True,
            landcolor="#111827",
            oceancolor="#0B1220",
            lakecolor="#0B1220",
            bgcolor="rgba(0,0,0,0)",
        )
        map_fig.update_layout(
            height=680,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="#0B1220",
            plot_bgcolor="#0B1220",
            coloraxis_colorbar=dict(
                tickfont=dict(color="rgba(226, 232, 240, 0.8)"),
                title=dict(text="", font=dict(color="rgba(226, 232, 240, 0.8)")),
            ),
            font=dict(family="Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"),
            dragmode=False,
            hoverlabel=dict(
                bgcolor="rgba(15, 23, 42, 0.92)",
                bordercolor="rgba(255,255,255,0.12)",
                font=dict(
                    color="#FFFFFF",
                    size=12,
                    family="Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
                ),
                align="left",
            ),
        )
        hover_value = [f"{float(v):,.0f}" for v in df_map["Value"].tolist()]
        hover_region_total = [f"{float(v):,.0f}" for v in df_map["RegionTotal"].tolist()]
        map_fig.update_traces(
            hovertemplate=(
                "<b>%{customdata[0]}</b>"
                "<br>Year: %{customdata[1]}"
                "<br>Advertising: %{customdata[2]}"
                + ("<br>Region total: %{customdata[3]}" if view_mode == "By region" else "")
                + "<extra></extra>"
            ),
            customdata=np.stack(
                [
                    (df_map["Region"].astype(str) if view_mode == "By region" else df_map["Country"].astype(str)).to_numpy(),
                    np.full(len(df_map), int(year_for_map)),
                    np.array(hover_value, dtype=object),
                    np.array(hover_region_total, dtype=object),
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
            "displayModeBar": False,
            "scrollZoom": False,
            "doubleClick": False,
            "modeBarButtonsToRemove": ["zoomInGeo", "zoomOutGeo", "resetGeo"],
        }
        map_html = pio.to_html(
            map_fig,
            include_plotlyjs="cdn",
            full_html=False,
            config=map_config,
            default_height=680,
        )
        overlay_html = summary_html if summary_html else ""
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
                    height: 680px;
                    background: #0B1220;
                  }}
                  .ov-map-wrap .js-plotly-plot {{
                    width: 100%;
                    height: 100%;
                  }}
                  .ov-map-summary {{
                    position: absolute;
                    top: 228px;
                    left: 18px;
                    z-index: 6;
                    max-width: min(340px, 40vw);
                    height: clamp(300px, 48vh, 460px);
                    background: rgba(11, 18, 32, 0.6);
                    border-radius: 12px;
                    padding: 10px 12px;
                    border: 1px solid rgba(148, 163, 184, 0.22);
                    overflow-y: auto;
                    pointer-events: auto;
                    color: #E2E8F0;
                  }}
                  .ov-map-summary-title {{
                    position: sticky;
                    top: 0;
                    z-index: 2;
                    padding: 6px 0 8px 0;
                    background: rgba(11, 18, 32, 0.9);
                    backdrop-filter: blur(6px);
                  }}
                  .ov-map-summary-value {{
                    position: sticky;
                    top: 32px;
                    z-index: 2;
                    padding-bottom: 10px;
                    background: rgba(11, 18, 32, 0.9);
                    backdrop-filter: blur(6px);
                  }}
                  .ov-map-summary-title {{
                    font-size: 0.95rem;
                    color: #94A3B8;
                    margin-bottom: 6px;
                  }}
                  .ov-map-summary-value {{
                    font-size: 1.75rem;
                    font-weight: 700;
                    color: #F8FAFC;
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
                    color: #E2E8F0;
                  }}
                  .ov-map-summary-sub {{
                    display: flex;
                    justify-content: space-between;
                    gap: 8px;
                    font-size: 0.78rem;
                    color: #94A3B8;
                    padding-left: 10px;
                  }}
                </style>
                <div class="ov-map-wrap">
                  {map_html}
                  {overlay_html}
                </div>
                """
            ),
            height=700,
        )
        if year_for_map != selected_year:
            st.caption(f"Country advertising data is not available for {selected_year}; showing {year_for_map} instead.")
    else:
        st.info("No country advertising values available for the selected metric/year.")
else:
    st.info("Country advertising dataset not found. Expected `Country_Advertising_Data_FullVi.csv` in `attached_assets/`.")



end_snap_section()

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
    growth_data = [d for d in data_list if d.get(yoy_key) is not None]
    if not growth_data:
        return None
    return max(growth_data, key=lambda x: x[yoy_key])


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
            if not top_row or not growth_row:
                continue
            st.markdown(
                render_split_summary_card(
                    left_title,
                    top_row["Company"],
                    format_large_number(top_row[left_key]),
                    right_title,
                    growth_row["Company"],
                    f"{growth_row[yoy_key]:+.1f}%",
                    company_logos,
                    left_icon_key=icon_key,
                    right_icon_key=icon_key,
                ),
                unsafe_allow_html=True,
            )

        if operating_income_data and top_growth_operating_income:
            top_operating_income = max(
                operating_income_data,
                key=lambda x: x.get("Operating Income", float("-inf")),
            )
            st.markdown(
                render_split_summary_card(
                    "Highest Operating Income",
                    top_operating_income["Company"],
                    format_large_number(top_operating_income["Operating Income"]),
                    "Operating Income Growth",
                    top_growth_operating_income["Company"],
                    f"{top_growth_operating_income['Operating Income YoY']:+.1f}%",
                    company_logos,
                    left_icon_key="operating_income",
                    right_icon_key="operating_income",
                ),
                unsafe_allow_html=True,
            )

        if cash_balance_data and top_growth_cash:
            top_cash_balance = max(
                cash_balance_data, key=lambda x: x.get("Cash Balance", float("-inf"))
            )
            st.markdown(
                render_split_summary_card(
                    "Highest Cash Balance",
                    top_cash_balance["Company"],
                    format_large_number(top_cash_balance["Cash Balance"]),
                    "Cash Balance Growth",
                    top_growth_cash["Company"],
                    f"{top_growth_cash['Cash Balance YoY']:+.1f}%",
                    company_logos,
                    left_icon_key="cash_balance",
                    right_icon_key="cash_balance",
                ),
                unsafe_allow_html=True,
            )

        if top_rd and top_growth_rd:
            st.markdown(
                render_split_summary_card(
                    "Highest R&D Spending",
                    top_rd["Company"],
                    format_large_number(top_rd["R&D"]),
                    "R&D Spending Growth",
                    top_growth_rd["Company"],
                    f"{top_growth_rd['R&D YoY']:+.1f}%",
                    company_logos,
                    left_icon_key="rd",
                    right_icon_key="rd",
                ),
                unsafe_allow_html=True,
            )

        if top_debt and top_growth_debt:
            st.markdown(
                render_split_summary_card(
                    "Highest Debt",
                    top_debt["Company"],
                    format_large_number(top_debt["Debt"]),
                    "Debt Growth",
                    top_growth_debt["Company"],
                    f"{top_growth_debt['Debt YoY']:+.1f}%",
                    company_logos,
                    left_icon_key="debt",
                    right_icon_key="debt",
                ),
                unsafe_allow_html=True,
            )

        if top_capex and top_growth_capex:
            st.markdown(
                render_split_summary_card(
                    "Highest Capital Expenditure",
                    top_capex["Company"],
                    format_large_number(top_capex["Capex"]),
                    "Capital Expenditure Growth",
                    top_growth_capex["Company"],
                    f"{top_growth_capex['Capex YoY']:+.1f}%",
                    company_logos,
                    left_icon_key="capex",
                    right_icon_key="capex",
                ),
                unsafe_allow_html=True,
            )

        if top_cost_of_revenue and top_growth_cost:
            st.markdown(
                render_split_summary_card(
                    "Highest Cost of Revenue",
                    top_cost_of_revenue["Company"],
                    format_large_number(top_cost_of_revenue["Cost of Revenue"]),
                    "Cost of Revenue Growth",
                    top_growth_cost["Company"],
                    f"{top_growth_cost['Cost of Revenue YoY']:+.1f}%",
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
            growth_data = [d for d in ad_revenue_data if d.get("Ad Revenue YoY") is not None]
            if growth_data:
                top_growth = max(growth_data, key=lambda x: x["Ad Revenue YoY"])
                yoy_text = f"{top_growth['Ad Revenue YoY']:+.1f}%"
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
            growth_data = [d for d in subscribers_data if d.get("Subscribers YoY") is not None]
            if growth_data:
                top_growth = max(growth_data, key=lambda x: x["Subscribers YoY"])
                yoy_text = f"{top_growth['Subscribers YoY']:+.1f}%"
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
            growth_data = [d for d in employee_data if d.get("Employees YoY") is not None]
            if growth_data:
                top_growth = max(growth_data, key=lambda x: x["Employees YoY"])
                yoy_text = f"{top_growth['Employees YoY']:+.1f}%"
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
                btn["args"][1]["frame"]["redraw"] = False
                btn["args"][1]["transition"]["duration"] = 600
        pie_fig.update_layout(updatemenus=pie_buttons, transition=dict(duration=500, easing="cubic-in-out"))
    pie_fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        uniformtext=dict(minsize=8, mode="hide"),
    )
    st.plotly_chart(pie_fig, use_container_width=True, config=plotly_config)
else:
    st.info("Nasdaq market cap data is not available for the selected year.")

end_snap_section()

# Add a touch of breathing room before the treemap.
st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

# Market Cap Treemap (one rectangle split into company boxes)
begin_snap_section("market_cap_treemap")
st.subheader("Market Cap Treemap")
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
                btn["args"][1]["frame"]["redraw"] = False
                btn["args"][1]["transition"]["duration"] = 600
        treemap_fig.update_layout(updatemenus=treemap_buttons, transition=dict(duration=500, easing="cubic-in-out"))
    treemap_fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        uniformtext=dict(minsize=10, mode="hide"),
    )
    st.plotly_chart(treemap_fig, use_container_width=True, config=plotly_config)
else:
    st.info("Market cap data is not available for the selected year.")

end_snap_section()

# Advertising Revenue vs Total Revenue (Stacked)
begin_snap_section("ad_vs_total")
st.subheader("Advertising Revenue vs Total Revenue")
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
    if total_revenue <= 0:
        continue
    # Metrics revenue is stored as USD millions; advertising revenue sheet is USD billions.
    total_revenue_b = total_revenue / 1000.0
    if total_revenue_b <= 0:
        continue
    ad_pct = (ad_value / total_revenue_b) * 100.0 if total_revenue_b else 0.0
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
    ad_bar_fig.add_trace(
        go.Scatter(
            x=x_companies,
            y=[r["Total"] for r in ad_stack_rows],
            text=ad_pct_labels,
            mode="text",
            textposition="top center",
            textfont=dict(
                size=12,
                color="#E2E8F0",
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
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="",
        yaxis_title="Revenue (USD, Billions)",
        legend=dict(
            orientation="h",
            y=-0.14,
            x=0,
            xanchor="left",
            font=dict(size=12, color="#E2E8F0"),
        ),
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
    ad_bar_fig.update_xaxes(showgrid=False, zeroline=False, showline=False, tickangle=-15)
    ad_bar_fig.update_yaxes(showgrid=False, zeroline=False, showline=False, ticksuffix="B")
    st.plotly_chart(ad_bar_fig, use_container_width=True, config=plotly_config)
else:
    st.info("Advertising revenue data is not available for the selected year.")

end_snap_section()

# Market Cap Visualization
begin_snap_section("market_cap_animation")

st.subheader("Market Capitalization")

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
else:
    st.info(f"No market cap data available for {selected_year}")

end_snap_section()

# Add spacing
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# Revenue Visualization
begin_snap_section("revenue_animation")
st.subheader("Revenue")

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
else:
    st.info(f"No revenue data available for {selected_year}")

end_snap_section()

# Add spacing
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# Net Income Visualization
begin_snap_section("net_income_animation")
st.subheader("Net Income")

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
else:
    st.info(f"No net income data available for {selected_year}")

end_snap_section()

# Add spacing
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# Total Assets Visualization
begin_snap_section("assets_animation")
st.subheader("Total Assets")

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
else:
    st.info(f"No total assets data available for {selected_year}")

end_snap_section()

# Add additional metrics
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("cash_animation")
st.subheader("Cash Balance")

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
else:
    st.info(f"No cash balance data available for {selected_year}")

end_snap_section()

# Add R&D Spending Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("rd_animation")
st.subheader("R&D Spending")

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
else:
    st.info(f"No R&D spending data available for {selected_year}")

end_snap_section()

# Add Employee Count Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("employees_animation")
st.subheader("Employee Count")

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
            texttemplate='%{x:,.0f}',  # Format as integer with commas
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
else:
    st.info(f"No employee count data available for {selected_year}")

end_snap_section()
    
# Add Long-Term Debt Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("debt_animation")
st.subheader("Long-Term Debt")

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
else:
    st.info(f"No debt data available for {selected_year}")

end_snap_section()

# Add Operating Income Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("operating_income_animation")
st.subheader("Operating Income")

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
else:
    st.info(f"No operating income data available for {selected_year}")

end_snap_section()

# Add Cost of Revenue Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("cost_of_revenue_animation")
st.subheader("Cost of Revenue")

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
else:
    st.info(f"No cost of revenue data available for {selected_year}")

end_snap_section()

# Add Capital Expenditure Visualization
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("capex_animation")
st.subheader("Capital Expenditure (Capex)")

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
else:
    st.info(f"No capex data available for {selected_year}")

end_snap_section()

# Executive Summary (moved to bottom for now)
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
begin_snap_section("executive_summary")
render_executive_summary_section()
end_snap_section()

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
