from __future__ import annotations

from html import escape
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Oracle", page_icon="🔮", layout="wide")

from utils.global_fonts import apply_global_fonts

apply_global_fonts()

from utils.page_transition import apply_page_transition_fix

apply_page_transition_fix()

from utils.header import render_header
from utils.styles import load_common_styles

# Lazy-import oracle_engine — if it fails (missing dep, path issue on HF),
# the page still renders and shows a clear error instead of crashing to Home.
_oracle_import_error = ""
try:
    from utils.oracle_engine import build_oracle_snapshot, persist_oracle_snapshot
except Exception as _exc:
    _oracle_import_error = f"{type(_exc).__name__}: {_exc}"
    build_oracle_snapshot = None  # type: ignore
    persist_oracle_snapshot = None  # type: ignore

load_common_styles()
st.session_state["active_nav_page"] = "oracle"
st.session_state["_active_nav_page"] = "oracle"
render_header()


@st.cache_data(ttl=1800, show_spinner=False)
def get_oracle_snapshot(use_polymarket: bool) -> dict:
    if build_oracle_snapshot is None:
        return {}
    return build_oracle_snapshot(use_polymarket=use_polymarket)


def _format_value(value: float | None, unit: str) -> str:
    if value is None or pd.isna(value):
        return "Not found"
    amount = float(value)
    if unit == "USDm":
        if abs(amount) >= 1_000_000:
            return f"${amount / 1_000_000:.2f}T"
        if abs(amount) >= 1_000:
            return f"${amount / 1_000:.1f}B"
        return f"${amount:,.0f}M"
    if unit == "USDb":
        if abs(amount) >= 1_000:
            return f"${amount / 1_000:.2f}T"
        return f"${amount:.1f}B"
    if unit == "pct":
        return f"{amount:.1f}%"
    return f"{amount:,.2f}"


def _format_delta(value: float | None, unit: str) -> str:
    if value is None or pd.isna(value):
        return "Not found"
    sign = "+" if float(value) > 0 else ""
    if unit == "pct":
        return f"{sign}{float(value):.1f} pts"
    return f"{sign}{float(value):.1f}%"


def _direction_color(direction: str) -> str:
    mapping = {
        "Bullish": "#22c55e",
        "Bearish": "#ef4444",
        "Neutral": "#38bdf8",
    }
    return mapping.get(str(direction), "#38bdf8")


def _build_constellation_html(nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> str:
    if nodes_df is None or nodes_df.empty:
        return "<div style='padding:24px;color:#64748b;'>Oracle has no nodes to render yet.</div>"

    nodes = nodes_df.copy().sort_values("latest_market_cap", ascending=False, na_position="last").reset_index(drop=True)
    width = 1160
    height = 440
    center_x = width / 2
    center_y = height / 2
    ellipse_x = 370
    ellipse_y = 145
    max_market_cap = max(nodes["latest_market_cap"].fillna(1).max(), 1.0)

    positioned_rows = []
    for idx, row in enumerate(nodes.itertuples(index=False)):
        angle = ((2 * math.pi * idx) / max(len(nodes), 1)) - (math.pi / 2)
        radius_x = ellipse_x + (18 * math.sin(idx * 1.3))
        radius_y = ellipse_y + (10 * math.cos(idx * 1.7))
        x = center_x + (math.cos(angle) * radius_x) + (row.composite_score * 42)
        y = center_y + (math.sin(angle) * radius_y) - (row.composite_score * 26)
        market_cap = row.latest_market_cap if row.latest_market_cap and row.latest_market_cap > 0 else max_market_cap * 0.08
        size = 18 + (24 * math.sqrt(max(market_cap, 1.0) / max_market_cap))
        confidence = max(float(row.confidence or 0.0), 1.0)
        positioned_rows.append(
            {
                "company": row.company,
                "x": round(x, 1),
                "y": round(y, 1),
                "size": round(size, 1),
                "direction": row.direction,
                "color": _direction_color(row.direction),
                "confidence": confidence,
                "score": round(float(row.composite_score or 0.0), 3),
                "forecast": escape(_format_value(row.forecast_value, row.forecast_unit)),
                "delta": escape(_format_delta(row.forecast_delta_pct, row.forecast_unit)),
                "summary": escape(str(row.summary or "")[:220]),
            }
        )

    node_lookup = {row["company"]: row for row in positioned_rows}
    edges = []
    if edges_df is not None and not edges_df.empty:
        for edge in edges_df.itertuples(index=False):
            source = node_lookup.get(edge.source)
            target = node_lookup.get(edge.target)
            if not source or not target:
                continue
            edges.append(
                {
                    "source": edge.source,
                    "target": edge.target,
                    "x1": source["x"],
                    "y1": source["y"],
                    "x2": target["x"],
                    "y2": target["y"],
                    "corr": round(float(edge.correlation or 0.0), 3),
                    "stroke_width": max(1.0, abs(float(edge.correlation or 0.0)) * 4.0),
                }
            )

    edges_markup = "".join(
        (
            f"<line class='oracle-edge' x1='{edge['x1']}' y1='{edge['y1']}' "
            f"x2='{edge['x2']}' y2='{edge['y2']}' stroke-width='{edge['stroke_width']:.2f}' />"
        )
        for edge in edges
    )

    nodes_markup = ""
    for node in positioned_rows:
        pulse_radius = node["size"] + 8 + (node["confidence"] / 18.0)
        pulse_speed = max(1.8, 3.7 - (node["confidence"] / 34.0))
        nodes_markup += f"""
        <g class="oracle-node"
           data-company="{escape(node['company'])}"
           data-direction="{escape(node['direction'])}"
           data-confidence="{node['confidence']:.0f}"
           data-forecast="{node['forecast']}"
           data-delta="{node['delta']}"
           data-summary="{node['summary']}"
           style="--node-color:{node['color']}; --pulse-speed:{pulse_speed:.2f}s;">
          <circle class="oracle-pulse" cx="{node['x']}" cy="{node['y']}" r="{pulse_radius:.1f}" fill="{node['color']}" opacity="0.22"></circle>
          <circle class="oracle-core" cx="{node['x']}" cy="{node['y']}" r="{node['size'] + 4:.1f}" fill="{node['color']}" opacity="0.10"></circle>
          <circle cx="{node['x']}" cy="{node['y']}" r="{node['size']:.1f}" fill="{node['color']}" opacity="0.92"></circle>
          <circle cx="{node['x']}" cy="{node['y']}" r="{max(4.2, node['size'] * 0.34):.1f}" fill="#f8fafc" opacity="0.95"></circle>
          <text class="oracle-label" x="{node['x']}" y="{node['y'] + node['size'] + 18:.1f}" text-anchor="middle">{escape(node['company'])}</text>
          <text class="oracle-score" x="{node['x']}" y="{node['y'] + node['size'] + 34:.1f}" text-anchor="middle">{node['direction']} · {node['confidence']:.0f}%</text>
        </g>
        """

    html = """
    <style>
      .oracle-space {
        position: relative;
        width: 100%;
        height: __HEIGHT__px;
        border-radius: 26px;
        overflow: hidden;
        background:
          radial-gradient(circle at 20% 15%, rgba(56, 189, 248, 0.16), transparent 32%),
          radial-gradient(circle at 78% 22%, rgba(34, 197, 94, 0.12), transparent 24%),
          radial-gradient(circle at 50% 50%, rgba(15, 23, 42, 0.12), transparent 44%),
          linear-gradient(135deg, #020617 0%, #0f172a 42%, #111827 100%);
        border: 1px solid rgba(148, 163, 184, 0.18);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 22px 55px rgba(15, 23, 42, 0.18);
      }
      .oracle-space svg {
        width: 100%;
        height: 100%;
        display: block;
      }
      .oracle-space .backdrop-ring {
        stroke: rgba(148, 163, 184, 0.18);
        stroke-width: 1;
        fill: none;
      }
      .oracle-space .backdrop-grid {
        stroke: rgba(148, 163, 184, 0.10);
        stroke-width: 0.8;
        fill: none;
        stroke-dasharray: 4 8;
      }
      .oracle-edge {
        stroke: rgba(125, 211, 252, 0.28);
        fill: none;
        stroke-dasharray: 10 12;
        animation: oracleFlow 14s linear infinite;
      }
      .oracle-node {
        cursor: pointer;
      }
      .oracle-pulse {
        transform-origin: center;
        animation: oraclePulse var(--pulse-speed) ease-out infinite;
      }
      .oracle-core {
        filter: drop-shadow(0 0 18px var(--node-color));
      }
      .oracle-label {
        font: 600 12px "Poppins", "DM Sans", sans-serif;
        fill: rgba(226, 232, 240, 0.94);
        letter-spacing: 0.03em;
      }
      .oracle-score {
        font: 500 11px "DM Sans", sans-serif;
        fill: rgba(148, 163, 184, 0.95);
      }
      .oracle-legend {
        position: absolute;
        top: 18px;
        left: 18px;
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(2, 6, 23, 0.62);
        border: 1px solid rgba(148, 163, 184, 0.14);
        backdrop-filter: blur(12px);
        color: #e2e8f0;
        max-width: 260px;
      }
      .oracle-legend h4 {
        margin: 0 0 6px 0;
        font: 700 0.92rem "Poppins", sans-serif;
        color: #f8fafc;
      }
      .oracle-legend p {
        margin: 0;
        font: 0.82rem/1.45 "DM Sans", sans-serif;
        color: rgba(226, 232, 240, 0.84);
      }
      .oracle-tooltip {
        position: absolute;
        min-width: 220px;
        max-width: 280px;
        pointer-events: none;
        transform: translate(-50%, -112%);
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(2, 6, 23, 0.94);
        color: #f8fafc;
        border: 1px solid rgba(56, 189, 248, 0.28);
        box-shadow: 0 18px 44px rgba(2, 6, 23, 0.45);
        opacity: 0;
        transition: opacity 0.18s ease;
        backdrop-filter: blur(12px);
      }
      .oracle-tooltip h5 {
        margin: 0 0 6px 0;
        font: 700 0.92rem "Poppins", sans-serif;
      }
      .oracle-tooltip .sub {
        color: #93c5fd;
        font: 500 0.78rem "DM Sans", sans-serif;
        margin-bottom: 8px;
      }
      .oracle-tooltip .meta {
        font: 0.78rem/1.35 "DM Sans", sans-serif;
        color: rgba(226, 232, 240, 0.82);
      }
      @keyframes oraclePulse {
        0%   { transform: scale(0.82); opacity: 0.68; }
        70%  { transform: scale(1.45); opacity: 0; }
        100% { transform: scale(1.45); opacity: 0; }
      }
      @keyframes oracleFlow {
        from { stroke-dashoffset: 0; }
        to   { stroke-dashoffset: -140; }
      }
    </style>
    <div class="oracle-space">
      <div class="oracle-legend">
        <h4>Living Constellation</h4>
        <p>Node size tracks market cap. Color tracks Oracle direction. Pulse intensity tracks confidence. Correlation links are built from recent daily return co-movement in the workbook price data.</p>
      </div>
      <svg viewBox="0 0 __WIDTH__ __HEIGHT__" preserveAspectRatio="xMidYMid meet">
        <ellipse class="backdrop-ring" cx="__CENTER_X__" cy="__CENTER_Y__" rx="__RING_X__" ry="__RING_Y__" />
        <ellipse class="backdrop-grid" cx="__CENTER_X__" cy="__CENTER_Y__" rx="__GRID1_X__" ry="__GRID1_Y__" />
        <ellipse class="backdrop-grid" cx="__CENTER_X__" cy="__CENTER_Y__" rx="__GRID2_X__" ry="__GRID2_Y__" />
        <line class="backdrop-grid" x1="__CENTER_X__" y1="58" x2="__CENTER_X__" y2="__VERTICAL_END__" />
        <line class="backdrop-grid" x1="140" y1="__CENTER_Y__" x2="__HORIZONTAL_END__" y2="__CENTER_Y__" />
        __EDGES__
        __NODES__
      </svg>
      <div class="oracle-tooltip" id="oracle-tooltip">
        <h5 id="oracle-tooltip-company"></h5>
        <div class="sub" id="oracle-tooltip-sub"></div>
        <div class="meta" id="oracle-tooltip-body"></div>
      </div>
    </div>
    <script>
      const root = document.currentScript.previousElementSibling;
      const tooltip = root.querySelector('#oracle-tooltip');
      const title = root.querySelector('#oracle-tooltip-company');
      const sub = root.querySelector('#oracle-tooltip-sub');
      const body = root.querySelector('#oracle-tooltip-body');
      root.querySelectorAll('.oracle-node').forEach((node) => {
        node.addEventListener('mousemove', (event) => {
          const rect = root.getBoundingClientRect();
          tooltip.style.left = `${event.clientX - rect.left}px`;
          tooltip.style.top = `${event.clientY - rect.top}px`;
          title.textContent = node.dataset.company || '';
          sub.textContent = `${node.dataset.direction || ''} · Confidence ${node.dataset.confidence || ''}%`;
          body.innerHTML = `<strong>Forecast:</strong> ${node.dataset.forecast || 'Not found'}`
            + ` <span style="color:#93c5fd;">(${node.dataset.delta || 'Not found'})</span><br>`
            + `${node.dataset.summary || ''}`;
          tooltip.style.opacity = '1';
        });
        node.addEventListener('mouseleave', () => {
          tooltip.style.opacity = '0';
        });
      });
    </script>
    """
    return (
        html.replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__CENTER_X__", f"{center_x}")
        .replace("__CENTER_Y__", f"{center_y}")
        .replace("__RING_X__", f"{ellipse_x + 48}")
        .replace("__RING_Y__", f"{ellipse_y + 48}")
        .replace("__GRID1_X__", f"{ellipse_x - 18}")
        .replace("__GRID1_Y__", f"{ellipse_y - 16}")
        .replace("__GRID2_X__", f"{ellipse_x - 108}")
        .replace("__GRID2_Y__", f"{ellipse_y - 72}")
        .replace("__VERTICAL_END__", str(height - 58))
        .replace("__HORIZONTAL_END__", str(width - 140))
        .replace("__EDGES__", edges_markup)
        .replace("__NODES__", nodes_markup)
    )


def _inject_page_css() -> None:
    st.markdown(
        """
        <style>
          .oracle-hero-copy {
            display: grid;
            grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.75fr);
            gap: 20px;
            margin-top: 14px;
            margin-bottom: 18px;
          }
          .oracle-hero-panel,
          .oracle-aside-panel,
          .oracle-card,
          .oracle-table-shell {
            border-radius: 22px;
            border: 1px solid rgba(148, 163, 184, 0.16);
            background: linear-gradient(160deg, rgba(255,255,255,0.98), rgba(248,250,252,0.94));
            box-shadow: 0 20px 48px rgba(15, 23, 42, 0.08);
          }
          .oracle-hero-panel {
            padding: 26px 28px 24px 28px;
          }
          .oracle-hero-title {
            margin: 0 0 10px 0;
            font: 800 2.2rem/1 "Poppins", sans-serif;
            color: #020617;
            letter-spacing: -0.04em;
          }
          .oracle-hero-subtitle {
            margin: 0;
            font: 1rem/1.6 "DM Sans", sans-serif;
            color: #475569;
            max-width: 780px;
          }
          .oracle-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 16px;
          }
          .oracle-pill {
            display: inline-flex;
            align-items: center;
            padding: 8px 12px;
            border-radius: 999px;
            background: rgba(15, 23, 42, 0.05);
            color: #0f172a;
            font: 700 0.78rem/1 "Poppins", sans-serif;
            text-transform: uppercase;
            letter-spacing: 0.06em;
          }
          .oracle-aside-panel {
            padding: 22px 22px 20px 22px;
            background: linear-gradient(160deg, rgba(2, 6, 23, 0.98), rgba(15, 23, 42, 0.95));
            color: #f8fafc;
          }
          .oracle-aside-panel h4 {
            margin: 0 0 10px 0;
            font: 700 1.08rem "Poppins", sans-serif;
          }
          .oracle-aside-panel p {
            margin: 0 0 12px 0;
            color: rgba(226, 232, 240, 0.82);
            font: 0.92rem/1.55 "DM Sans", sans-serif;
          }
          .oracle-aside-list {
            margin: 0;
            padding-left: 18px;
            color: rgba(226, 232, 240, 0.82);
            font: 0.9rem/1.5 "DM Sans", sans-serif;
          }
          .oracle-card {
            padding: 20px 18px 18px 18px;
            height: 100%;
          }
          .oracle-card-top {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: baseline;
          }
          .oracle-card-top h4 {
            margin: 0;
            font: 700 1.02rem "Poppins", sans-serif;
            color: #0f172a;
          }
          .oracle-card-top span {
            font: 700 0.78rem "Poppins", sans-serif;
            letter-spacing: 0.05em;
            text-transform: uppercase;
          }
          .oracle-card-forecast {
            margin-top: 12px;
            color: #0f172a;
            font: 700 1.7rem/1 "Poppins", sans-serif;
          }
          .oracle-card-detail {
            margin-top: 4px;
            color: #475569;
            font: 0.88rem/1.5 "DM Sans", sans-serif;
          }
          .oracle-card-summary {
            margin-top: 12px;
            color: #334155;
            font: 0.9rem/1.55 "DM Sans", sans-serif;
            min-height: 88px;
          }
          .oracle-dial {
            position: relative;
            width: 160px;
            height: 84px;
            margin: 18px auto 10px;
            overflow: hidden;
          }
          .oracle-dial-track,
          .oracle-dial-fill {
            position: absolute;
            inset: 0;
            border-top-left-radius: 160px;
            border-top-right-radius: 160px;
            border: 14px solid rgba(148, 163, 184, 0.18);
            border-bottom: none;
          }
          .oracle-dial-fill {
            border-color: var(--dial-color);
            opacity: 0.35;
            clip-path: inset(0 calc(50% - var(--dial-fill)) 0 0);
          }
          .oracle-dial-needle {
            position: absolute;
            left: 50%;
            bottom: 4px;
            width: 3px;
            height: 74px;
            background: #0f172a;
            transform-origin: bottom center;
            transform: translateX(-50%) rotate(var(--needle-rotation));
            border-radius: 999px;
            box-shadow: 0 0 0 4px rgba(255,255,255,0.88);
          }
          .oracle-dial-center {
            position: absolute;
            left: 50%;
            bottom: -2px;
            width: 18px;
            height: 18px;
            border-radius: 999px;
            background: #0f172a;
            transform: translateX(-50%);
          }
          .oracle-dial-labels {
            display: flex;
            justify-content: space-between;
            font: 700 0.72rem "Poppins", sans-serif;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-top: 2px;
          }
          .oracle-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
          }
          .oracle-chip {
            padding: 7px 10px;
            border-radius: 999px;
            font: 700 0.72rem/1 "Poppins", sans-serif;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            background: rgba(15, 23, 42, 0.06);
            color: #0f172a;
          }
          .oracle-table-shell {
            padding: 12px;
          }
          .oracle-section-label {
            margin: 0 0 10px 0;
            font: 700 0.78rem/1 "Poppins", sans-serif;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #64748b;
          }

          /* ── Command Center ─────────────────────────────── */
          .oracle-cmd-header {
            margin: 24px 0 14px 0;
            font: 800 1.1rem/1 "Poppins", sans-serif;
            letter-spacing: -0.02em;
            color: #e2e8f0;
          }
          .oracle-cmd-subtext {
            font: 0.78rem/1.5 "DM Sans", sans-serif;
            color: #64748b;
            margin: 0 0 18px 0;
          }
          .oracle-cmd-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 12px;
            margin-bottom: 6px;
          }
          .oracle-cmd-card {
            position: relative;
            padding: 18px 16px 16px 16px;
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.12);
            background: linear-gradient(160deg, rgba(30,41,59,0.7), rgba(15,23,42,0.85));
            cursor: pointer;
            transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
            overflow: hidden;
          }
          .oracle-cmd-card:hover {
            border-color: rgba(59, 130, 246, 0.45);
            background: linear-gradient(160deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95));
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
          }
          .oracle-cmd-card.active {
            border-color: #3b82f6;
            background: linear-gradient(160deg, rgba(30,41,59,0.95), rgba(15,23,42,1));
            box-shadow: 0 0 0 1px rgba(59,130,246,0.3), 0 12px 32px rgba(0,0,0,0.3);
          }
          .oracle-cmd-card.active::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, #3b82f6, #8b5cf6);
          }
          .oracle-cmd-icon {
            font-size: 1.6rem;
            line-height: 1;
            margin-bottom: 10px;
          }
          .oracle-cmd-title {
            margin: 0 0 4px 0;
            font: 700 0.88rem/1.2 "Poppins", sans-serif;
            color: #f1f5f9;
          }
          .oracle-cmd-desc {
            margin: 0;
            font: 0.72rem/1.45 "DM Sans", sans-serif;
            color: #94a3b8;
          }
          .oracle-cmd-badge {
            position: absolute;
            top: 12px;
            right: 12px;
            padding: 2px 8px;
            border-radius: 999px;
            font: 600 0.6rem/1.4 "Poppins", sans-serif;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
          }
          .oracle-tool-active-header {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 14px 0 10px 0;
            border-bottom: 1px solid rgba(148,163,184,0.1);
            margin-bottom: 16px;
          }
          .oracle-tool-active-header .tool-icon {
            font-size: 1.4rem;
          }
          .oracle-tool-active-header .tool-name {
            font: 700 1rem/1 "Poppins", sans-serif;
            color: #f1f5f9;
          }
          .oracle-tool-active-header .tool-tag {
            font: 600 0.62rem/1 "Poppins", sans-serif;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            padding: 3px 8px;
            border-radius: 999px;
            background: rgba(59,130,246,0.12);
            color: #60a5fa;
          }
          @media (max-width: 1080px) {
            .oracle-hero-copy {
              grid-template-columns: 1fr;
            }
            .oracle-cmd-grid {
              grid-template-columns: 1fr 1fr;
            }
          }
          @media (max-width: 640px) {
            .oracle-cmd-grid {
              grid-template-columns: 1fr;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_prediction_cards(predictions: pd.DataFrame) -> None:
    top_cards = predictions.sort_values(["confidence", "composite_score"], ascending=[False, False])
    cols = st.columns(3, gap="medium")
    for idx, row in enumerate(top_cards.itertuples(index=False)):
        col = cols[idx % 3]
        color = _direction_color(row.direction)
        rotation = max(-88.0, min(88.0, float(row.composite_score or 0.0) * 85.0))
        fill = max(8.0, min(100.0, (float(row.confidence or 0.0) / 100.0) * 100.0))
        with col:
            st.markdown(
                f"""
                <div class="oracle-card">
                  <div class="oracle-card-top">
                    <h4>{escape(row.company)}</h4>
                    <span style="color:{color};">{escape(row.direction)}</span>
                  </div>
                  <div class="oracle-card-forecast">{escape(_format_value(row.forecast_value, row.forecast_unit))}</div>
                  <div class="oracle-card-detail">{escape(row.metric)} · {escape(_format_delta(row.forecast_delta_pct, row.forecast_unit))} · confidence {row.confidence:.0f}%</div>
                  <div class="oracle-dial" style="--dial-color:{color}; --needle-rotation:{rotation:.1f}deg; --dial-fill:{fill:.1f}%;">
                    <div class="oracle-dial-track"></div>
                    <div class="oracle-dial-fill"></div>
                    <div class="oracle-dial-needle"></div>
                    <div class="oracle-dial-center"></div>
                  </div>
                  <div class="oracle-dial-labels"><span>Bearish</span><span>Neutral</span><span>Bullish</span></div>
                  <div class="oracle-card-summary">{escape(str(row.summary or '')[:190])}</div>
                  <div class="oracle-chip-row">
                    <span class="oracle-chip">Signal {row.signal_score if row.signal_score is not None else 0:+.2f}</span>
                    <span class="oracle-chip">Market {row.market_score if row.market_score is not None else 0:+.2f}</span>
                    <span class="oracle-chip">Fund {row.fundamental_score if row.fundamental_score is not None else 0:+.2f}</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _build_layer_chart(predictions: pd.DataFrame, metric: str) -> go.Figure:
    scoped = predictions[predictions["metric"] == metric].copy()
    scoped = scoped.sort_values("confidence", ascending=True)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=scoped["company"],
            x=scoped["signal_score"],
            name="Signal Velocity",
            orientation="h",
            marker=dict(color="#1d4ed8"),
        )
    )
    fig.add_trace(
        go.Bar(
            y=scoped["company"],
            x=scoped["market_score"],
            name="Market Consensus",
            orientation="h",
            marker=dict(color="#0f766e"),
        )
    )
    fig.add_trace(
        go.Bar(
            y=scoped["company"],
            x=scoped["fundamental_score"],
            name="Fundamental Trajectory",
            orientation="h",
            marker=dict(color="#f97316"),
        )
    )
    fig.add_trace(
        go.Scatter(
            y=scoped["company"],
            x=scoped["composite_score"],
            mode="markers",
            name="Composite",
            marker=dict(color="#fbbf24", size=10, symbol="diamond", line=dict(color="#0f172a", width=1)),
            hovertemplate="<b>%{y}</b><br>Composite %{x:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        height=max(430, len(scoped) * 36),
        margin=dict(l=160, r=20, t=40, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#1e293b"),
        title=dict(
            text=f"Layer Breakdown \u00b7 {metric}",
            font=dict(size=16, color="#0f172a"),
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(color="#334155", size=11),
        ),
        xaxis=dict(
            range=[-1.15, 1.15],
            gridcolor="rgba(148,163,184,0.18)",
            zerolinecolor="rgba(148,163,184,0.3)",
            tickfont=dict(color="#334155"),
            title=dict(text="Bearish \u2190 Score \u2192 Bullish", font=dict(color="#64748b", size=11)),
        ),
        yaxis=dict(
            gridcolor="rgba(0,0,0,0)",
            tickfont=dict(color="#0f172a", size=12),
            automargin=True,
        ),
    )
    return fig


def _build_table_frame(predictions: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    driver_strings = {}
    if factors is not None and not factors.empty:
        driver_df = factors[factors["layer"].isin(["Signal Drivers", "Market Drivers", "Fundamental Drivers"])].copy()
        driver_df = driver_df.sort_values(["company", "metric", "sort_order"])
        grouped = driver_df.groupby(["company", "metric"])["factor_name"].apply(lambda values: ", ".join(list(values)[:4]))
        driver_strings = grouped.to_dict()

    table = predictions.copy()
    table["Forecast"] = [
        _format_value(value, unit)
        for value, unit in zip(table["forecast_value"], table["forecast_unit"])
    ]
    table["Change"] = [
        _format_delta(value, unit)
        for value, unit in zip(table["forecast_delta_pct"], table["forecast_unit"])
    ]
    table["Layers"] = [
        f"S {signal:+.2f} | M {market:+.2f} | F {fund:+.2f}"
        for signal, market, fund in zip(
            table["signal_score"].fillna(0.0),
            table["market_score"].fillna(0.0),
            table["fundamental_score"].fillna(0.0),
        )
    ]
    table["Top Drivers"] = [
        driver_strings.get((company, metric), "")
        for company, metric in zip(table["company"], table["metric"])
    ]
    table["Confidence"] = table["confidence"].map(lambda value: f"{value:.0f}%")
    table["Composite"] = table["composite_score"].map(lambda value: f"{value:+.2f}")
    return table[["company", "metric", "direction", "Confidence", "Composite", "Forecast", "Change", "Layers", "Top Drivers"]].rename(
        columns={
            "company": "Company",
            "metric": "Metric",
            "direction": "Direction",
        }
    )


def main() -> None:
    _inject_page_css()

    if _oracle_import_error:
        st.error(
            f"**Oracle engine failed to import.**\n\n"
            f"`{_oracle_import_error}`\n\n"
            "Check Space logs for details."
        )
        return

    st.markdown(
        """
        <div class="oracle-hero-copy">
          <div class="oracle-hero-panel">
            <div class="oracle-section-label">Predictive Intelligence</div>
            <h1 class="oracle-hero-title">Oracle</h1>
            <p class="oracle-hero-subtitle">
              Oracle is the quantitative forward layer for the dashboard. It fuses transcript signal velocity,
              market consensus, and fundamental trajectory into a company-level prediction surface that Genie can cite.
            </p>
            <div class="oracle-pill-row">
              <span class="oracle-pill">Signal Velocity 40%</span>
              <span class="oracle-pill">Market Consensus 30%</span>
              <span class="oracle-pill">Fundamentals 30%</span>
            </div>
          </div>
          <div class="oracle-aside-panel">
            <h4>What This Uses</h4>
            <p>Only repo-backed sources are used here: the local workbook, the transcript signal CSVs, and the local SQLite intelligence DB for materialized Oracle output.</p>
            <ul class="oracle-aside-list">
              <li>`earningscall_transcripts/scored_signals.csv` for forward-looking transcript velocity</li>
              <li>Google Sheets workbook (auto-downloaded) for fundamentals and daily prices</li>
              <li>`earningscall_intelligence.db` for Oracle snapshot storage</li>
            </ul>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    controls_left, controls_right = st.columns([0.72, 0.28], gap="large")
    with controls_left:
        st.caption("Oracle will attempt to enrich the market layer with Polymarket if live data is available. If not, the market score falls back to workbook price momentum.")
    with controls_right:
        use_polymarket = st.toggle("Use live Polymarket overlay", value=True, key="oracle_use_polymarket")

    try:
        with st.spinner("Materializing Oracle prediction layer..."):
            snapshot = get_oracle_snapshot(use_polymarket=use_polymarket)
    except Exception as exc:
        st.error(
            f"Oracle engine failed to build predictions.\n\n"
            f"**Error:** `{type(exc).__name__}: {exc}`\n\n"
            "This usually means the Google Sheets workbook couldn't be downloaded, "
            "or `scored_signals.csv` is missing. Check the Space logs for details."
        )
        return

    try:
        persist_oracle_snapshot(snapshot)
    except Exception:
        pass  # SQLite write failure is non-fatal — predictions still render

    predictions = snapshot.get("predictions", pd.DataFrame()).copy()
    factors = snapshot.get("factors", pd.DataFrame()).copy()
    correlations = snapshot.get("correlations", pd.DataFrame()).copy()
    metadata = snapshot.get("metadata", {})

    if predictions.empty:
        st.error("Oracle could not build predictions from the current local assets.")
        return

    revenue_predictions = predictions[predictions["metric"] == "Revenue"].copy()
    bull_count = int((predictions["direction"] == "Bullish").sum())
    bear_count = int((predictions["direction"] == "Bearish").sum())
    avg_confidence = float(predictions["confidence"].mean())
    live_market_count = int((predictions["market_score"].fillna(0.0).abs() > 0).sum())

    metric_cols = st.columns(4, gap="medium")
    metric_cols[0].metric("Bullish Calls", bull_count)
    metric_cols[1].metric("Bearish Calls", bear_count)
    metric_cols[2].metric("Average Confidence", f"{avg_confidence:.0f}%")
    metric_cols[3].metric("Market-Linked Rows", live_market_count)

    components.html(
        _build_constellation_html(revenue_predictions.head(10), correlations.head(14)),
        height=452,
        scrolling=False,
    )

    filter_col1, filter_col2 = st.columns([0.36, 0.64], gap="large")
    with filter_col1:
        metric_filter = st.selectbox(
            "Metric",
            options=["Revenue", "Advertising Revenue", "Operating Margin"],
            index=0,
        )
        available_companies = sorted(predictions["company"].dropna().unique().tolist())
        company_filter = st.multiselect(
            "Companies",
            options=available_companies,
            default=available_companies,
        )

    filtered = predictions[predictions["metric"] == metric_filter].copy()
    if company_filter:
        filtered = filtered[filtered["company"].isin(company_filter)].copy()
    if filtered.empty:
        filtered = predictions[predictions["metric"] == metric_filter].copy()

    with filter_col2:
        st.plotly_chart(_build_layer_chart(filtered, metric_filter), use_container_width=True, config={"displayModeBar": False})
        st.caption("Signal = transcript momentum · Market = price consensus/Polymarket · Fundamental = financial trajectory · ◆ = weighted composite")

    # ══════════════════════════════════════════════════════════════════
    # Oracle Prediction Dials + Table (always visible — core page content)
    # ══════════════════════════════════════════════════════════════════
    st.markdown("<div class='oracle-section-label' style='margin-top:12px;'>Oracle Dials</div>", unsafe_allow_html=True)
    _render_prediction_cards(filtered)

    st.markdown("<div class='oracle-section-label' style='margin-top:14px;'>Prediction Table</div>", unsafe_allow_html=True)
    table_frame = _build_table_frame(filtered.sort_values(["confidence", "composite_score"], ascending=[False, False]), factors)
    st.markdown("<div class='oracle-table-shell'>", unsafe_allow_html=True)
    st.dataframe(table_frame, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════
    # Command Center — Apple-style tool selector
    # ══════════════════════════════════════════════════════════════════
    st.markdown("---")

    _TOOL_REGISTRY = [
        {
            "key": "revenue_sim",
            "icon": "📊",
            "title": "Revenue Simulator",
            "desc": "Estimate current-year revenue by company from quarterly run rates + signal momentum",
            "badge": "Live",
        },
        {
            "key": "country_ad",
            "icon": "🌍",
            "title": "Country Ad Spend",
            "desc": "Forecast advertising spend by country and channel using historical growth models",
            "badge": "Forecast",
        },
        {
            "key": "intelligence",
            "icon": "🧠",
            "title": "Intelligence Layer",
            "desc": "Cross-source derived metrics \u2014 signal divergence, channel exposure, institutional conviction",
            "badge": "Derived",
        },
        {
            "key": "mirofish",
            "icon": "🐟",
            "title": "MiroFish Simulator",
            "desc": "Multi-agent swarm forecasting \u2014 AI agents debate ad spend scenarios vs GroupM baseline",
            "badge": "AI",
        },
    ]

    active_tool = st.session_state.get("oracle_active_tool", None)

    # Build command card grid as HTML
    cards_html_parts = []
    for t in _TOOL_REGISTRY:
        active_cls = " active" if t["key"] == active_tool else ""
        cards_html_parts.append(
            f'<div class="oracle-cmd-card{active_cls}" data-tool="{t["key"]}">'
            f'<div class="oracle-cmd-badge">{t["badge"]}</div>'
            f'<div class="oracle-cmd-icon">{t["icon"]}</div>'
            f'<div class="oracle-cmd-title">{t["title"]}</div>'
            f'<p class="oracle-cmd-desc">{t["desc"]}</p>'
            f'</div>'
        )

    st.markdown(
        '<div class="oracle-cmd-header">Analysis Tools</div>'
        '<p class="oracle-cmd-subtext">Select a tool to open it inline. Each tool combines multiple data sources for deeper analysis.</p>'
        '<div class="oracle-cmd-grid">' + "".join(cards_html_parts) + '</div>',
        unsafe_allow_html=True,
    )

    # Streamlit buttons (hidden-ish, laid out as columns) to capture clicks
    btn_cols = st.columns(len(_TOOL_REGISTRY), gap="small")
    for i, t in enumerate(_TOOL_REGISTRY):
        with btn_cols[i]:
            is_active = (t["key"] == active_tool)
            label = f"\u2715 Close {t['title']}" if is_active else f"{t['icon']} {t['title']}"
            if st.button(label, key=f"cmd_{t['key']}", use_container_width=True):
                if is_active:
                    st.session_state["oracle_active_tool"] = None
                else:
                    st.session_state["oracle_active_tool"] = t["key"]
                st.rerun()

    # ── Render active tool ────────────────────────────────────────────
    if active_tool:
        tool_meta = next((t for t in _TOOL_REGISTRY if t["key"] == active_tool), None)
        if tool_meta:
            st.markdown(
                f'<div class="oracle-tool-active-header">'
                f'<span class="tool-icon">{tool_meta["icon"]}</span>'
                f'<span class="tool-name">{tool_meta["title"]}</span>'
                f'<span class="tool-tag">{tool_meta["badge"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if active_tool == "revenue_sim":
            _render_revenue_simulator()
        elif active_tool == "country_ad":
            _render_country_predictor()
        elif active_tool == "intelligence":
            _render_intelligence_section()
        elif active_tool == "mirofish":
            _render_mirofish_panel()

    # Metadata at the very bottom
    with st.expander("Oracle Snapshot Metadata", expanded=False):
        st.json(metadata)


# ═══════════════════════════════════════════════════════════════════════
# Revenue Simulator Section
# ═══════════════════════════════════════════════════════════════════════

def _render_revenue_simulator() -> None:
    """YTD revenue estimation — extrapolates quarterly run rate + signal momentum."""
    try:
        from utils.revenue_simulator import estimate_all_companies
        from utils.workbook_source import resolve_financial_data_xlsx, get_workbook_source_stamp
    except ImportError:
        return

    st.markdown(
        '<p style="font-size:0.82rem;color:#94a3b8;margin-top:0;margin-bottom:14px;">'
        'Estimates current year revenue from last reported quarters, adjusted by '
        'earnings call signal momentum. Select quarters to see partial-year estimates.</p>',
        unsafe_allow_html=True,
    )

    ctrl_col1, ctrl_col2 = st.columns([0.3, 0.7])
    with ctrl_col1:
        q_choice = st.radio(
            "Estimate through",
            options=["Full Year", "Q1", "Q2", "Q3"],
            horizontal=True,
            key="rev_sim_quarter",
        )

    through_q = {"Full Year": None, "Q1": 1, "Q2": 2, "Q3": 3}.get(q_choice)

    try:
        excel_path = resolve_financial_data_xlsx()
        source_stamp = get_workbook_source_stamp(excel_path)
        results = estimate_all_companies(excel_path, source_stamp, through_quarter=through_q)
    except Exception as e:
        st.warning(f"Revenue simulator error: {e}")
        return

    if not results:
        st.info("No quarterly data available for revenue estimation.")
        return

    # Build comparison table
    rows = []
    for r in results:
        est_val = r.get("ytd_revenue") if through_q else r.get("full_year_estimate")
        prior = r.get("prior_year_revenue")
        growth = r.get("growth_rate")
        sig_adj = r.get("signal_adjustment", 0)
        conf = r.get("confidence", 0)

        if est_val and est_val > 0:
            # Show values in $B if over 1000 ($M)
            if est_val > 1000:
                est_str = f"${est_val/1000:.1f}B"
            else:
                est_str = f"${est_val:.0f}M"
            prior_str = f"${prior/1000:.1f}B" if prior and prior > 1000 else (f"${prior:.0f}M" if prior else "—")
            growth_str = f"{growth*100:+.1f}%" if growth is not None else "—"
            sig_str = f"{sig_adj*100:+.1f}pp" if sig_adj else "—"

            rows.append({
                "Company": r["company"],
                "Estimate": est_str,
                "Prior Year": prior_str,
                "Growth Rate": growth_str,
                "Signal Adj.": sig_str,
                "Confidence": f"{conf}%",
            })

    if rows:
        label = f"through {q_choice}" if through_q else "Full Year"
        with ctrl_col2:
            st.markdown(f"<div style='font-size:0.8rem;color:#64748b;margin-bottom:4px;'>Estimated revenue {label}</div>", unsafe_allow_html=True)

        df_display = pd.DataFrame(rows)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Quarterly breakdown for top companies
    with st.expander("Quarterly Breakdown", expanded=False):
        for r in results[:6]:
            qb = r.get("quarterly_breakdown", [])
            if not qb:
                continue
            q_parts = []
            for q in qb:
                tag = "✓" if q["is_actual"] else "est."
                rev = q["revenue"]
                rev_str = f"${rev/1000:.1f}B" if rev > 1000 else f"${rev:.0f}M"
                q_parts.append(f"Q{q['q']}: {rev_str} ({tag})")
            st.markdown(f"**{r['company']}** — {' · '.join(q_parts)}")


# ═══════════════════════════════════════════════════════════════════════
# Country Ad Spend Predictor Section
# ═══════════════════════════════════════════════════════════════════════

def _render_country_predictor() -> None:
    """Country-level ad spend forecasting with channel breakdown."""
    try:
        from utils.country_ad_predictor import predict_country_ad_spend, get_available_countries
        from utils.workbook_source import resolve_financial_data_xlsx
    except ImportError:
        return

    st.markdown(
        '<p style="font-size:0.82rem;color:#94a3b8;margin-top:0;margin-bottom:14px;">'
        'Forecasts advertising spend by country and channel using historical growth patterns (2019-2024). '
        'Blends log-linear regression with dampened extrapolation for robust multi-year projections.</p>',
        unsafe_allow_html=True,
    )

    try:
        excel_path = resolve_financial_data_xlsx()
    except Exception:
        st.info("Workbook not available for country predictions.")
        return

    countries = get_available_countries(excel_path)
    if not countries:
        st.info("No country advertising data available.")
        return

    ctrl1, ctrl2 = st.columns([0.4, 0.6])
    with ctrl1:
        default_countries = ["United States", "United Kingdom", "China", "Japan", "Germany"]
        defaults = [c for c in default_countries if c in countries]
        selected = st.multiselect(
            "Select countries",
            options=countries,
            default=defaults[:3],
            key="country_pred_select",
        )
    with ctrl2:
        forecast_yrs = st.slider("Forecast years", min_value=1, max_value=5, value=2, key="country_pred_yrs")

    if not selected:
        return

    for country in selected:
        try:
            pred = predict_country_ad_spend(country, excel_path, forecast_yrs)
        except Exception:
            continue

        if pred.get("method") == "unavailable":
            continue

        st.markdown(f"### {pred['country']}")

        # Growth rates by channel
        growth = pred.get("growth_rates", {})
        total_growth = growth.get("Total", 0)
        conf = pred.get("confidence", 0)
        st.markdown(
            f"<div style='font-size:0.8rem;color:#94a3b8;'>"
            f"Overall CAGR: <strong style='color:#e6edf3;'>{total_growth:+.1f}%</strong> · "
            f"Confidence: {conf}%</div>",
            unsafe_allow_html=True,
        )

        # Build chart: historical + forecast
        historical = pred.get("historical", {})
        forecast = pred.get("forecast", {})
        all_years = sorted(list(historical.keys()) + list(forecast.keys()))
        categories = [c for c in growth.keys() if c != "Total"]

        if all_years and categories:
            fig = go.Figure()
            cat_colors = {
                "Digital": "#3b82f6", "Television": "#ef4444",
                "OOH": "#f59e0b", "Press": "#6b7280",
                "Radio": "#8b5cf6", "Cinema": "#ec4899",
            }
            for cat in categories:
                hist_vals = [historical.get(y, {}).get(cat, 0) for y in all_years if y in historical]
                fore_vals = [forecast.get(y, {}).get(cat, 0) for y in all_years if y in forecast]
                hist_years = [y for y in all_years if y in historical]
                fore_years = [y for y in all_years if y in forecast]

                color = cat_colors.get(cat, "#64748b")
                # Historical (solid)
                if hist_vals:
                    fig.add_trace(go.Bar(
                        name=cat,
                        x=hist_years,
                        y=hist_vals,
                        marker_color=color,
                        legendgroup=cat,
                        showlegend=True,
                    ))
                # Forecast (hatched/lighter)
                if fore_vals:
                    fig.add_trace(go.Bar(
                        name=f"{cat} (forecast)",
                        x=fore_years,
                        y=fore_vals,
                        marker_color=color,
                        marker_opacity=0.5,
                        marker_line=dict(color=color, width=1),
                        legendgroup=cat,
                        showlegend=False,
                    ))

            fig.update_layout(
                barmode="stack",
                height=320,
                margin=dict(l=60, r=20, t=10, b=40),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8"),
                xaxis=dict(tickfont=dict(color="#e6edf3")),
                yaxis=dict(title="$M", gridcolor="#1e293b", tickfont=dict(color="#94a3b8")),
                legend=dict(
                    orientation="h", y=-0.15,
                    font=dict(color="#94a3b8", size=10),
                ),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Channel growth table
        with st.expander(f"Channel growth rates — {pred['country']}", expanded=False):
            gr_rows = [{"Channel": k, "CAGR %": f"{v:+.1f}%"} for k, v in growth.items() if k != "Total"]
            if gr_rows:
                st.dataframe(pd.DataFrame(gr_rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════
# Intelligence Layer Section
# ═══════════════════════════════════════════════════════════════════════

def _render_intelligence_section() -> None:
    """Render cross-source derived metrics from the intelligence layer."""
    try:
        from utils.intelligence_layer import compute_all_derived_metrics
    except ImportError:
        return

    try:
        derived = compute_all_derived_metrics()
    except Exception:
        return

    if not derived:
        return

    st.markdown(
        '<p style="font-size:0.82rem;color:#94a3b8;margin-top:0;margin-bottom:14px;">'
        'Combines transcript signals, stock prices, institutional holdings, ad revenue, and GroupM '
        'channel forecasts to produce metrics no single source provides.</p>',
        unsafe_allow_html=True,
    )

    # ── Signal-to-Price Divergence ──────────────────────────────────
    spd = derived.get("signal_price_divergence")
    if spd is not None and not spd.empty:
        st.markdown(
            "<div style='font-size:0.85rem;font-weight:700;color:#e6edf3;margin-bottom:4px;'>"
            "Signal-to-Price Divergence</div>"
            "<div style='font-size:0.72rem;color:#64748b;margin-bottom:8px;'>"
            "When transcript signals diverge from stock momentum → market may be mispricing</div>",
            unsafe_allow_html=True,
        )

        # Build a horizontal bar chart
        fig = go.Figure()
        spd_sorted = spd.sort_values("divergence", ascending=True)
        colors = ["#22c55e" if d > 0.1 else ("#ef4444" if d < -0.1 else "#64748b") for d in spd_sorted["divergence"]]
        fig.add_trace(go.Bar(
            y=spd_sorted["company"],
            x=spd_sorted["divergence"],
            orientation="h",
            marker_color=colors,
            text=[f"{d:+.2f}" for d in spd_sorted["divergence"]],
            textposition="auto",
            textfont=dict(color="#e6edf3", size=11),
            hovertemplate="<b>%{y}</b><br>Signal: %{customdata[0]:+.2f}<br>Price: %{customdata[1]:+.2f}<br>Divergence: %{x:+.2f}<extra></extra>",
            customdata=list(zip(spd_sorted["signal_velocity"], spd_sorted["price_momentum"])),
        ))
        fig.update_layout(
            height=max(200, len(spd_sorted) * 32),
            margin=dict(l=120, r=20, t=10, b=30),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8"),
            xaxis=dict(
                title="← Market ahead | Signals ahead →",
                gridcolor="#1e293b",
                tickfont=dict(color="#94a3b8"),
                zeroline=True,
                zerolinecolor="#475569",
            ),
            yaxis=dict(tickfont=dict(color="#e6edf3")),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Channel Exposure Forecast ──────────────────────────────────
    cef = derived.get("channel_exposure_forecast")
    if cef is not None and not cef.empty:
        st.markdown(
            "<div style='font-size:0.85rem;font-weight:700;color:#e6edf3;margin-top:14px;margin-bottom:4px;'>"
            "Ad Channel Exposure Forecast</div>"
            "<div style='font-size:0.72rem;color:#64748b;margin-bottom:8px;'>"
            "Company ad revenue weighted by GroupM channel growth forecasts → expected growth from channel mix</div>",
            unsafe_allow_html=True,
        )
        cef_display = cef[["company", "channel_mix_growth_pct", "company_ad_cagr_pct", "alpha_pp"]].copy()
        cef_display.columns = ["Company", "Channel Mix Growth %", "Actual CAGR %", "Alpha (pp)"]
        st.dataframe(cef_display, use_container_width=True, hide_index=True)

    # ── Revenue per Employee (latest year) ──────────────────────────
    rpe = derived.get("revenue_per_employee")
    if rpe is not None and not rpe.empty:
        latest_year = rpe["year"].max()
        latest = rpe[rpe["year"] == latest_year].sort_values("rev_per_employee", ascending=False).head(14)
        if not latest.empty:
            st.markdown(
                f"<div style='font-size:0.85rem;font-weight:700;color:#e6edf3;margin-top:14px;margin-bottom:4px;'>"
                f"Revenue per Employee ({int(latest_year)})</div>",
                unsafe_allow_html=True,
            )
            fig = go.Figure(go.Bar(
                x=latest["company"],
                y=latest["rev_per_employee"] / 1_000_000,
                marker_color="#3b82f6",
                text=[f"${v/1_000_000:.2f}M" for v in latest["rev_per_employee"]],
                textposition="auto",
                textfont=dict(color="#e6edf3", size=10),
            ))
            fig.update_layout(
                height=280,
                margin=dict(l=40, r=20, t=10, b=60),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8"),
                xaxis=dict(tickfont=dict(color="#e6edf3", size=10), tickangle=-45),
                yaxis=dict(title="$M / employee", gridcolor="#1e293b", tickfont=dict(color="#94a3b8")),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Institutional Conviction (compact) ──────────────────────────
    ic = derived.get("institutional_conviction")
    if ic is not None and not ic.empty:
        st.markdown(
            "<div style='font-size:0.85rem;font-weight:700;color:#e6edf3;margin-top:14px;margin-bottom:4px;'>"
            "Institutional Conviction Alignment</div>"
            "<div style='font-size:0.72rem;color:#64748b;margin-bottom:8px;'>"
            "Cross-referencing holder trends × transcript signals × price direction</div>",
            unsafe_allow_html=True,
        )
        ic_display = ic[["company", "top5_ownership_pct", "holder_trend",
                         "signal_direction", "price_direction", "alignment"]].copy()
        ic_display.columns = ["Company", "Top-5 Own %", "Holder Trend",
                              "Signal Dir.", "Price Dir.", "Alignment"]
        st.dataframe(ic_display, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════
# MiroFish Panel
# ═══════════════════════════════════════════════════════════════════════

def _render_mirofish_panel() -> None:
    """Render the MiroFish Ad-Spend Simulator panel below Oracle."""
    try:
        from utils.mirofish_engine import (
            SCENARIO_PRESETS,
            build_ad_market_graph,
            estimate_run_cost,
            run_full_mirofish,
        )
    except ImportError:
        st.warning("MiroFish engine not available. Check that `app/utils/mirofish_engine.py` exists.")
        return

    st.markdown(
        '<p style="font-size:0.82rem;color:#94a3b8;margin-top:0;margin-bottom:14px;">'
        'Spawns AI agents with ad-industry personas that react to your workbook data, '
        'debate across rounds, and produce a crowd-consensus forecast vs GroupM baseline.</p>',
        unsafe_allow_html=True,
    )

    # ── Controls ─────────────────────────────────────────────────────
    ctrl1, ctrl2, ctrl3 = st.columns([0.34, 0.33, 0.33], gap="medium")

    with ctrl1:
        horizon_year = st.selectbox(
            "Forecast Year",
            options=[2025, 2026, 2027, 2028, 2029],
            index=1,
            key="mf_horizon",
        )

    with ctrl2:
        n_agents = st.select_slider(
            "Agents",
            options=[10, 20, 40, 60, 80, 100],
            value=20,
            key="mf_agents",
        )

    with ctrl3:
        n_rounds = st.select_slider(
            "Rounds",
            options=[1, 2, 3, 5, 7],
            value=2,
            key="mf_rounds",
        )

    # Scenario selection
    st.markdown("<div style='font-size:0.78rem;font-weight:600;color:#94a3b8;margin-bottom:4px;'>Scenario Presets</div>", unsafe_allow_html=True)
    preset_labels = {
        "baseline": "📊 Baseline",
        "recession": "🧊 Recession",
        "rate_cuts": "📈 Rate Cuts",
        "tiktok_ban": "📵 TikTok Ban",
        "cookie_deprecation": "🔒 Cookie Death",
        "genai_creative": "🤖 GenAI Creative",
        "ctv_saturation": "🛑 CTV Saturation",
    }

    pcols = st.columns(len(preset_labels), gap="small")
    for i, (key, label) in enumerate(preset_labels.items()):
        with pcols[i]:
            if st.button(label, key=f"mf_preset_{key}", use_container_width=True):
                st.session_state["mf_scenario_text"] = SCENARIO_PRESETS[key]
                st.session_state["mf_scenario_key"] = key

    scenario_text = st.text_area(
        "Scenario (editable)",
        value=st.session_state.get("mf_scenario_text", SCENARIO_PRESETS["baseline"]),
        height=68,
        key="mf_scenario_input",
    )

    # ── Advanced Configuration ─────────────────────────────────────
    with st.expander("⚙ Advanced Configuration", expanded=False):
        adv_c1, adv_c2, adv_c3 = st.columns(3, gap="medium")
        with adv_c1:
            agent_temp = st.slider(
                "Agent creativity",
                min_value=0.1, max_value=1.5, value=0.8, step=0.1,
                help="Higher = more diverse agent opinions. Lower = more conservative consensus.",
                key="mf_agent_temp",
            )
        with adv_c2:
            geo_weight = st.select_slider(
                "Geographic diversity",
                options=["Low", "Medium", "High"],
                value="Medium",
                help="Low = US-heavy agent pool. High = global distribution.",
                key="mf_geo_weight",
            )
        with adv_c3:
            include_tools = st.multiselect(
                "Feed into simulation",
                options=["Revenue Simulator", "Country Forecasts", "Intelligence Layer"],
                default=[],
                help="Inject pre-computed metrics from other tools into agent context.",
                key="mf_include_tools",
            )

        st.markdown(
            '<div style="font-size:0.72rem;color:#475569;margin-top:4px;">'
            'Agent creativity controls LLM temperature. Geographic diversity adjusts the regional '
            'bias distribution of spawned agents. Tool injection feeds derived metrics into agent prompts for richer analysis.</div>',
            unsafe_allow_html=True,
        )

    # Cost estimate
    est_cost = estimate_run_cost(n_agents, n_rounds)
    st.caption(f"Estimated cost: **${est_cost:.2f}** · {n_agents} agents × {n_rounds} rounds · Uses same DeepSeek/OpenAI key as Genie")

    # ── Run button ───────────────────────────────────────────────────
    run_clicked = st.button(
        f"🌀 Run Swarm  (~${est_cost:.2f})",
        key="mf_run_btn",
        type="primary",
        use_container_width=True,
    )

    # ── Results ──────────────────────────────────────────────────────
    if run_clicked:
        progress_bar = st.progress(0, text="Initializing swarm...")
        live_feed_container = st.container()
        live_feed_placeholder = live_feed_container.empty()
        _live_statements: list[dict] = []

        # Role → emoji mapping for visual identity
        _role_emoji = {
            "CPG Brand Marketer": "🛒", "Auto CMO": "🚗", "Retail Media Buyer": "🏪",
            "Agency Investment Director": "💼", "Platform Sell-Side Exec": "📡",
            "CTV Publisher": "📺", "Institutional Portfolio Manager": "📊",
            "Macro Strategist": "🌐", "Privacy Regulator": "🔒", "Ad-Tech Skeptic": "🤔",
        }

        def _progress_callback(round_num, total_rounds, metrics, cost):
            pct = round_num / total_rounds
            progress_bar.progress(
                pct,
                text=f"Round {round_num}/{total_rounds} · consensus: +{metrics['growth_mean']:.1f}% · cost: ${cost:.3f}",
            )

        def _statement_callback(stmt, current, total):
            _live_statements.append(stmt)
            # Build live feed HTML — show last 6 statements
            recent = _live_statements[-6:]
            html_lines = []
            for s in recent:
                emoji = _role_emoji.get(s["role"], "🔮")
                growth_str = f"+{s['growth_estimate']:.1f}%" if s["growth_estimate"] is not None else "—"
                # Truncate statement for display
                display_text = s["statement"][:200].split("COMMENT:")[-1].strip() if "COMMENT:" in s["statement"] else s["statement"][:200]
                html_lines.append(
                    f"<div style='padding:6px 10px;margin:3px 0;border-radius:8px;"
                    f"background:rgba(30,41,59,0.8);border-left:3px solid #3b82f6;'>"
                    f"<span style='font-size:0.72rem;color:#94a3b8;'>"
                    f"{emoji} {s['role']} · {s['geo_bias']} · R{s['round']}</span>"
                    f"<span style='float:right;font-size:0.78rem;color:#22c55e;font-weight:700;'>{growth_str}</span>"
                    f"<div style='font-size:0.78rem;color:#e2e8f0;margin-top:2px;line-height:1.4;'>"
                    f"{escape(display_text)}</div></div>"
                )
            counter_text = (
                f"<div style='font-size:0.72rem;color:#64748b;margin-bottom:4px;'>"
                f"Agent {current}/{total} responding...</div>"
            )
            live_feed_placeholder.markdown(
                counter_text + "".join(html_lines),
                unsafe_allow_html=True,
            )

        try:
            report = run_full_mirofish(
                horizon_year=horizon_year,
                n_agents=n_agents,
                n_rounds=n_rounds,
                scenario=scenario_text,
                progress_callback=_progress_callback,
                statement_callback=_statement_callback,
            )
            st.session_state["mf_last_report"] = report
            st.session_state["mf_last_statements"] = _live_statements
        except Exception as e:
            st.error(f"MiroFish run failed: {e}")
            return

        progress_bar.empty()
        live_feed_placeholder.empty()

    # Display report if available
    report = st.session_state.get("mf_last_report")
    if report:
        _render_mirofish_report(report)

    # ── Post-run simulation transcript expander ─────────────────────
    saved_statements = st.session_state.get("mf_last_statements", [])
    if saved_statements:
        _render_simulation_transcript(saved_statements)


def _render_simulation_transcript(statements: list[dict]) -> None:
    """Expandable transcript of all agent statements from the last MiroFish run."""
    _role_emoji = {
        "CPG Brand Marketer": "🛒", "Auto CMO": "🚗", "Retail Media Buyer": "🏪",
        "Agency Investment Director": "💼", "Platform Sell-Side Exec": "📡",
        "CTV Publisher": "📺", "Institutional Portfolio Manager": "📊",
        "Macro Strategist": "🌐", "Privacy Regulator": "🔒", "Ad-Tech Skeptic": "🤔",
    }

    # Group by round
    rounds: dict[int, list[dict]] = {}
    for s in statements:
        r = s.get("round", 0)
        rounds.setdefault(r, []).append(s)

    total_agents = len(statements)
    n_rounds = max(rounds.keys()) if rounds else 0

    with st.expander(f"📜 View Simulation Transcript ({total_agents} statements · {n_rounds} rounds)", expanded=False):
        for round_num in sorted(rounds.keys()):
            st.markdown(
                f"<div style='font-size:0.78rem;color:#3b82f6;font-weight:700;"
                f"margin:12px 0 6px 0;padding:4px 8px;background:rgba(59,130,246,0.08);"
                f"border-radius:4px;'>ROUND {round_num}</div>",
                unsafe_allow_html=True,
            )
            for s in rounds[round_num]:
                emoji = _role_emoji.get(s.get("role", ""), "🔮")
                growth_str = f"+{s['growth_estimate']:.1f}%" if s.get("growth_estimate") is not None else "—"
                geo = s.get("geo_bias", "")
                role = s.get("role", "Unknown")

                # Extract comment from structured output
                raw_text = s.get("statement", "")
                if "COMMENT:" in raw_text:
                    comment = raw_text.split("COMMENT:")[-1].strip()
                else:
                    comment = raw_text[:500]

                st.markdown(
                    f"<div style='padding:8px 12px;margin:3px 0;border-radius:6px;"
                    f"background:rgba(30,41,59,0.6);border-left:3px solid #334155;'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                    f"<span style='font-size:0.72rem;color:#94a3b8;'>"
                    f"{emoji} <b>{escape(role)}</b> · {escape(geo)}</span>"
                    f"<span style='font-size:0.78rem;color:#22c55e;font-weight:700;'>{growth_str}</span>"
                    f"</div>"
                    f"<div style='font-size:0.78rem;color:#cbd5e1;margin-top:3px;line-height:1.5;'>"
                    f"{escape(comment)}</div></div>",
                    unsafe_allow_html=True,
                )


def _render_mirofish_report(report: dict) -> None:
    """Render MiroFish results: forecast cone, channel deltas, drivers."""
    baseline = report.get("baseline_groupm_growth", 0)
    mu = report.get("mirofish_growth_mu", 0)
    sigma = report.get("mirofish_growth_sigma", 0)
    deviation = report.get("deviation_from_groupm", 0)
    confidence = report.get("confidence", 0)
    horizon = report.get("horizon", 2026)
    cost = report.get("cost_usd", 0)

    # ── Headline metrics ─────────────────────────────────────────────
    dev_color = "#22c55e" if deviation >= 0 else "#ef4444"

    m1, m2, m3, m4 = st.columns(4, gap="medium")
    m1.metric("GroupM Baseline", f"+{baseline:.1f}%")
    m2.metric("MiroFish Consensus", f"+{mu:.1f}%")
    m3.metric("Δ vs GroupM", f"{deviation:+.1f}pp")
    m4.metric("Swarm Confidence", f"{confidence:.0%}")

    # ── Narrative ────────────────────────────────────────────────────
    narrative = report.get("narrative", "")
    if narrative:
        st.markdown(
            f"<div style='background:#1e293b;border-radius:8px;padding:14px 18px;margin:8px 0 14px 0;"
            f"border-left:3px solid {dev_color};'>"
            f"<div style='font-size:0.72rem;color:#64748b;text-transform:uppercase;letter-spacing:0.06em;"
            f"margin-bottom:4px;'>MiroFish Narrative</div>"
            f"<div style='font-size:0.88rem;color:#e2e8f0;line-height:1.6;'>{escape(narrative)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Forecast Cone + Channel Deltas side by side ──────────────────
    chart_left, chart_right = st.columns(2, gap="medium")

    with chart_left:
        _render_forecast_cone_chart(report)

    with chart_right:
        _render_channel_delta_chart(report)

    # ── Tailwinds / Headwinds ────────────────────────────────────────
    tw_col, hw_col = st.columns(2, gap="medium")
    with tw_col:
        st.markdown("##### 🟢 Top Tailwinds")
        for tw in report.get("top_tailwinds", [])[:5]:
            st.markdown(f"- {tw}")
    with hw_col:
        st.markdown("##### 🔴 Top Headwinds")
        for hw in report.get("top_headwinds", [])[:5]:
            st.markdown(f"- {hw}")

    # ── Channel Outlook ──────────────────────────────────────────────
    channel_outlook = report.get("channel_outlook", {})
    if channel_outlook:
        with st.expander("Channel Outlook Detail", expanded=False):
            for ch, outlook in channel_outlook.items():
                st.markdown(f"**{ch}:** {outlook}")

    # ── Round-by-round convergence ───────────────────────────────────
    round_metrics = report.get("round_metrics", [])
    if len(round_metrics) > 1:
        _render_convergence_chart(round_metrics, baseline)

    st.caption(f"Run cost: ${cost:.3f} · {report.get('n_agents', 0)} agents × {report.get('n_rounds', 0)} rounds")


def _render_forecast_cone_chart(report: dict) -> None:
    """Forecast cone: GroupM baseline as dashed line, MiroFish as gradient cone."""
    mu = report.get("mirofish_growth_mu", 0)
    sigma = report.get("mirofish_growth_sigma", 0)
    baseline = report.get("baseline_groupm_growth", 0)
    horizon = report.get("horizon", 2026)

    years = list(range(2024, horizon + 1))
    n = len(years)

    # Build cone (widening sigma from 2024 → horizon)
    baseline_vals = [0.0] + [baseline * i / (n - 1) for i in range(1, n)]
    mirofish_vals = [0.0] + [mu * i / (n - 1) for i in range(1, n)]
    upper = [0.0] + [(mu + sigma * 1.5) * i / (n - 1) for i in range(1, n)]
    lower = [0.0] + [(mu - sigma * 1.5) * i / (n - 1) for i in range(1, n)]

    fig = go.Figure()

    # Cone fill
    fig.add_trace(go.Scatter(
        x=years + years[::-1],
        y=upper + lower[::-1],
        fill="toself",
        fillcolor="rgba(59,130,246,0.15)",
        line=dict(color="rgba(0,0,0,0)"),
        name="Confidence Cone",
        showlegend=True,
    ))

    # GroupM baseline dashed
    fig.add_trace(go.Scatter(
        x=years, y=baseline_vals,
        mode="lines",
        line=dict(color="#94a3b8", dash="dash", width=2),
        name=f"GroupM +{baseline:.1f}%",
    ))

    # MiroFish consensus
    fig.add_trace(go.Scatter(
        x=years, y=mirofish_vals,
        mode="lines+markers",
        line=dict(color="#3b82f6", width=3),
        marker=dict(size=8),
        name=f"MiroFish +{mu:.1f}%",
    ))

    fig.update_layout(
        title=dict(text=f"Cumulative Growth vs 2024 → {horizon}", font=dict(size=13, color="#e2e8f0")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94a3b8"),
        xaxis=dict(gridcolor="#1e293b", tickfont=dict(color="#94a3b8")),
        yaxis=dict(title="Cumulative Growth %", gridcolor="#1e293b", tickfont=dict(color="#94a3b8"), ticksuffix="%"),
        legend=dict(font=dict(color="#94a3b8", size=10), bgcolor="rgba(0,0,0,0)"),
        height=320,
        margin=dict(l=40, r=20, t=40, b=30),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_channel_delta_chart(report: dict) -> None:
    """Horizontal bar chart of channel sentiment from the swarm."""
    deltas = report.get("channel_deltas", {})
    if not deltas:
        st.info("No channel sentiment data from this run.")
        return

    sorted_channels = sorted(deltas.items(), key=lambda x: x[1], reverse=True)
    channels = [c for c, _ in sorted_channels]
    values = [v for _, v in sorted_channels]
    colors = ["#22c55e" if v >= 0 else "#ef4444" for v in values]

    fig = go.Figure(go.Bar(
        y=channels,
        x=values,
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.0%}" for v in values],
        textposition="auto",
        textfont=dict(color="#e2e8f0", size=11),
    ))
    fig.update_layout(
        title=dict(text="Channel Share Momentum", font=dict(size=13, color="#e2e8f0")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94a3b8"),
        xaxis=dict(gridcolor="#1e293b", tickfont=dict(color="#94a3b8"), range=[-1, 1], title="Bearish ← → Bullish"),
        yaxis=dict(tickfont=dict(color="#94a3b8")),
        height=320,
        margin=dict(l=100, r=20, t=40, b=30),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_convergence_chart(round_metrics: list, baseline: float) -> None:
    """Sparkline showing how swarm consensus converges across rounds."""
    rounds = [r["round"] for r in round_metrics]
    means = [r["growth_mean"] for r in round_metrics]
    stds = [r["growth_std"] for r in round_metrics]

    upper = [m + s for m, s in zip(means, stds)]
    lower = [m - s for m, s in zip(means, stds)]

    fig = go.Figure()

    # Std envelope
    fig.add_trace(go.Scatter(
        x=rounds + rounds[::-1],
        y=upper + lower[::-1],
        fill="toself",
        fillcolor="rgba(59,130,246,0.15)",
        line=dict(color="rgba(0,0,0,0)"),
        showlegend=False,
    ))

    # GroupM baseline
    fig.add_trace(go.Scatter(
        x=rounds, y=[baseline] * len(rounds),
        mode="lines",
        line=dict(color="#94a3b8", dash="dash", width=1),
        name="GroupM",
    ))

    # Consensus
    fig.add_trace(go.Scatter(
        x=rounds, y=means,
        mode="lines+markers",
        line=dict(color="#3b82f6", width=2),
        marker=dict(size=6),
        name="Consensus",
    ))

    fig.update_layout(
        title=dict(text="Swarm Convergence by Round", font=dict(size=12, color="#94a3b8")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94a3b8"),
        xaxis=dict(title="Round", gridcolor="#1e293b", tickfont=dict(color="#94a3b8"), dtick=1),
        yaxis=dict(title="Growth %", gridcolor="#1e293b", tickfont=dict(color="#94a3b8"), ticksuffix="%"),
        legend=dict(font=dict(color="#94a3b8", size=10), bgcolor="rgba(0,0,0,0)"),
        height=200,
        margin=dict(l=40, r=20, t=30, b=30),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


if __name__ == "__main__":
    main()
