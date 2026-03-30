import base64
import html
import io
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from utils import format_number
from utils.auth import check_password
from utils.state_management import get_data_processor
from utils.styles import get_page_style
from utils.header import display_header
from utils.data_availability import get_available_quarters
from utils.components import render_ai_assistant
from utils.workbook_market_data import (
    build_company_ticker_map_from_market_data,
    load_combined_stock_market_data,
)

# Ensure transcript data is synced (flag file prevents repeat work)
_SYNC_FLAG_FILE = "/tmp/transcript_sync_done"
_AUTO_SYNC_ENV = "AUTO_SYNC_TRANSCRIPTS_ON_STARTUP"
if (
    str(os.getenv(_AUTO_SYNC_ENV, "1")).strip().lower() not in {"0", "false", "no", "off"}
    and not os.path.exists(_SYNC_FLAG_FILE)
):
    try:
        from utils.transcript_startup_sync import sync_local_transcripts_to_workbook
        _sync_result = sync_local_transcripts_to_workbook(timeout_seconds=30)
        if not _sync_result.error:
            with open(_SYNC_FLAG_FILE, "w", encoding="utf-8") as _fh:
                _fh.write(str(datetime.now()))
    except Exception:
        pass  # best-effort, don't block page load

def main():
    # Page config must be the first Streamlit command
    st.set_page_config(page_title="Earnings", page_icon="E", layout="wide")

    from utils.global_fonts import apply_global_fonts
    apply_global_fonts()


    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    check_password()
    st.markdown(get_page_style(), unsafe_allow_html=True)
    st.session_state["active_nav_page"] = "earnings"
    st.session_state["_active_nav_page"] = "earnings"
    display_header()
    st.markdown(
        """
        <style>
        .stApp .block-container {
            max-width: 1600px;
            padding-left: 2rem;
            padding-right: 2rem;
            padding-top: 0.5rem;
        }

        .main-content {
            max-width: 1600px;
            margin: 0 auto;
        }

        /* Fix: hide Material Icons text when font fails to load (shows "arrow_right" etc.)
           Target summary AND all descendants to override Streamlit emotion styles. */
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary * {
            font-size: 0 !important;
            color: transparent !important;
        }
        [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"],
        [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] * {
            font-size: 0.875rem !important;
            color: #374151 !important;
        }
        [data-testid="stExpander"] summary svg,
        [data-testid="stExpander"] summary svg * {
            color: #94a3b8 !important;
            visibility: visible !important;
        }

        h1 {
            margin-top: 0.2rem;
            margin-bottom: 0.75rem;
        }

        hr {
            margin: 0.75rem 0;
        }

        /* ── Fix multiselect pill first-letter clipping ── */
        [data-baseweb="select"] *,
        .stMultiSelect * {
            background-image: none !important;
        }
        div[data-testid="stMultiSelect"] div[style*="linear-gradient"],
        [data-baseweb="select"] > div > div[style*="gradient"] {
            display: none !important;
            opacity: 0 !important;
            width: 0 !important;
            pointer-events: none !important;
        }
        [data-baseweb="tag"] {
            overflow: visible !important;
            max-width: none !important;
            padding: 2px 8px 2px 10px !important;
            margin-left: 4px !important;
        }
        [data-baseweb="tag"] > span,
        [data-baseweb="tag"] span[dir="auto"] {
            overflow: visible !important;
            text-overflow: unset !important;
            white-space: nowrap !important;
            max-width: none !important;
            padding-left: 2px !important;
        }
        [data-baseweb="input"],
        [data-baseweb="select"] > div:first-child {
            overflow: visible !important;
            flex-wrap: wrap !important;
            padding-left: 6px !important;
        }

        .earnings-hero {
            width: 100%;
            margin: 0.5rem 0 1rem;
            border-radius: 18px;
            overflow: hidden;
            position: relative;
            background: #0f172a;
            background-image: var(--hero-image);
            background-size: cover;
            background-position: center;
            height: auto;
            transition: height 0.9s ease;
            border: 1px solid #eef0f4;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12);
        }

        .earnings-hero.is-collapsed {
            height: var(--hero-final-height);
        }

        .earnings-hero::before {
            content: "";
            position: absolute;
            inset: 0;
            background-image: var(--hero-image);
            background-size: cover;
            background-position: center;
            filter: blur(0px);
            transform: scale(1.08);
            opacity: 0;
            z-index: 0;
            transition: filter 0.8s ease, opacity 0.8s ease;
        }
        .earnings-hero.is-loaded::before {
            filter: blur(0px);
            opacity: 0.85;
        }

    	    .earnings-hero img {
    	        width: 100%;
    	        height: 100%;
    	        object-fit: cover;
    	        display: block;
    	        position: relative;
    	        z-index: 1;
    	        transform: scale(1);
    	        transform-origin: center;
    	        transition: transform 0.9s ease;
    	    }

        .earnings-hero.is-collapsed img {
            transform: scale(1.06);
        }

    	    .earnings-hero-overlay {
    	        position: absolute;
    	        inset: 0;
    	        display: flex;
    	        align-items: center;
    	        justify-content: center;
    	        padding: 1.25rem 1.5rem;
    	        z-index: 2;
    	    }

    	    .earnings-hero.has-stock {
    	        --stock-safe-right: clamp(180px, 20vw, 280px);
    	        --stock-safe-bottom: clamp(128px, 14vw, 150px);
    	    }

    	    .earnings-hero.has-stock .earnings-hero-overlay {
    	        align-items: flex-start;
    	        padding-right: calc(1.5rem + var(--stock-safe-right));
    	        padding-bottom: calc(1.25rem + var(--stock-safe-bottom));
    	    }

        .earnings-hero-panel {
            width: 100%;
            background: transparent;
            border: none;
            border-radius: 0;
            padding: 0.35rem 0.1rem;
            box-shadow: none;
            max-width: 1500px;
        }

        @keyframes kpiCardFadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to   { opacity: 1; transform: translateY(0); }
        }

        .earnings-hero-panel .kpi-card {
            background: rgba(15, 23, 42, 0.55);
            border: 1px solid rgba(248, 250, 252, 0.25);
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.18);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            opacity: 0;
            transform: translateY(6px);
            transition: opacity 0.6s ease, transform 0.6s ease;
            /* CSS-only fallback: cards appear even if JS animation fails */
            animation: kpiCardFadeIn 0.6s ease forwards;
            animation-delay: 1.8s;
        }
        .earnings-hero-panel .kpi-card:nth-child(2) { animation-delay: 1.92s; }
        .earnings-hero-panel .kpi-card:nth-child(3) { animation-delay: 2.04s; }
        .earnings-hero-panel .kpi-card:nth-child(4) { animation-delay: 2.16s; }
        .earnings-hero-panel .kpi-card:nth-child(5) { animation-delay: 2.28s; }
        .earnings-hero-panel .kpi-card:nth-child(6) { animation-delay: 2.40s; }
        .earnings-hero-panel .kpi-card:nth-child(7) { animation-delay: 2.52s; }
        .earnings-hero-panel .kpi-card:nth-child(8) { animation-delay: 2.64s; }
        .earnings-hero-panel .kpi-card:nth-child(9) { animation-delay: 2.76s; }
        .earnings-hero-panel .kpi-card:nth-child(10) { animation-delay: 2.88s; }

        .earnings-hero-panel .kpi-card.kpi-show {
            animation: none;
            opacity: 1;
            transform: translateY(0);
        }

        .company-header {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 0.9rem;
            margin-top: 0.4rem;
            margin-bottom: 0.75rem;
        }

        .company-header-left {
            display: flex;
            align-items: center;
            gap: 0.9rem;
        }

        .company-logo {
            width: 54px;
            height: 54px;
            object-fit: contain;
            flex-shrink: 0;
            align-self: center;
        }

        .company-header-text {
            display: flex;
            align-items: baseline;
            gap: 0.45rem;
        }

        .company-name {
            font-size: 2.2rem;
            font-weight: 600;
            line-height: 1;
            color: #111827;
        }

        .company-year {
            font-size: 2.2rem;
            font-weight: 500;
            color: #6b7280;
            line-height: 1;
        }

    	    .earnings-hero-stock {
    	        position: absolute;
    	        bottom: 1.1rem;
    	        right: 1.6rem;
    	        z-index: 5;
    	        text-align: right;
    	        font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    	        background: rgba(15, 23, 42, 0.55);
    	        border: 1px solid rgba(248, 250, 252, 0.22);
    	        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.18);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-radius: 14px;
            padding: 0.8rem 1rem;
            min-width: 200px;
        }

        .earnings-hero-stock .hero-stock-ticker {
            font-size: 2.8rem;
            font-weight: 700;
            color: #f8fafc;
            letter-spacing: 0.08em;
            line-height: 1;
        }

        .earnings-hero-stock .hero-stock-price {
            font-size: 1.25rem;
            font-weight: 600;
            color: #f8fafc;
            margin-top: 0.2rem;
        }

        .earnings-hero-stock .hero-stock-change {
            font-size: 0.95rem;
            font-weight: 600;
            margin-top: 0.25rem;
        }

        .earnings-hero-stock .hero-stock-change-positive {
            color: #16A34A;
        }

        .earnings-hero-stock .hero-stock-change-negative {
            color: #EF4444;
        }

        .earnings-hero-stock .hero-stock-change-neutral {
            color: #E2E8F0;
        }

        .earnings-hero-stock .hero-stock-sparkline {
            width: 180px;
            height: 44px;
            margin-top: 0.35rem;
            opacity: 0.95;
        }

        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 1.25rem;
            margin-bottom: 0.75rem;
        }

        .kpi-card {
            background: #ffffff;
            border-radius: 10px;
            border: 1px solid #eef0f4;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
            padding: 0.85rem 1rem;
            transform-style: preserve-3d;
            transition: transform 0.15s ease, box-shadow 0.2s ease;
            will-change: transform;
        }

        .kpi-card:hover {
            box-shadow: 0 12px 26px rgba(15, 23, 42, 0.18);
        }

        .kpi-icon-wrap {
            width: 46px;
            height: 46px;
            border-radius: 12px;
            background: rgba(0, 115, 255, 0.14);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 0.55rem;
        }

        .kpi-icon-wrap.is-negative {
            background: rgba(239, 68, 68, 0.14);
        }

        .kpi-icon {
            width: 28px;
            height: 28px;
            display: block;
        }

        .kpi-icon .growth-bar {
            transform-origin: bottom;
            animation: kpiBarPulse1 3s ease-in-out infinite;
        }
        .kpi-icon .growth-bar:nth-child(2) { animation-name: kpiBarPulse2; animation-duration: 3.5s; }
        .kpi-icon .growth-bar:nth-child(3) { animation-name: kpiBarPulse3; animation-duration: 2.8s; }
        .kpi-icon .growth-bar:nth-child(4) { animation-name: kpiBarPulse4; animation-duration: 3.2s; }
        .kpi-icon .growth-bar:nth-child(5) { animation-name: kpiBarPulse5; animation-duration: 2.5s; }

        @keyframes kpiBarPulse1 {
            0%, 100% { transform: scaleY(1); }
            30% { transform: scaleY(0.7); }
            60% { transform: scaleY(1.1); }
        }
        @keyframes kpiBarPulse2 {
            0%, 100% { transform: scaleY(1); }
            25% { transform: scaleY(1.15); }
            70% { transform: scaleY(0.8); }
        }
        @keyframes kpiBarPulse3 {
            0%, 100% { transform: scaleY(1); }
            35% { transform: scaleY(0.75); }
            65% { transform: scaleY(1.05); }
        }
        @keyframes kpiBarPulse4 {
            0%, 100% { transform: scaleY(1); }
            40% { transform: scaleY(1.2); }
            75% { transform: scaleY(0.85); }
        }
        @keyframes kpiBarPulse5 {
            0%, 100% { transform: scaleY(1); }
            20% { transform: scaleY(1.1); }
            55% { transform: scaleY(0.9); }
        }

        .dollar-pulse {
            animation: kpiDollarBounce 2s ease-in-out infinite;
            transform-origin: center;
        }
        @keyframes kpiDollarBounce {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.12); }
        }

    	    .kpi-icon .gear-rotate {
    	        animation: kpiGearSpin 6s linear infinite;
    	        transform-origin: center;
    	    }
        @keyframes kpiGearSpin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .kpi-icon .coin-stack {
            animation: kpiCoinFloat 3s ease-in-out infinite;
        }
        .kpi-icon .coin-stack:nth-child(2) { animation-delay: 0.3s; }
        .kpi-icon .coin-stack:nth-child(3) { animation-delay: 0.6s; }
        @keyframes kpiCoinFloat {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-3px); }
        }

        .kpi-icon .bulb-glow {
            animation: kpiBulbFlicker 2s ease-in-out infinite;
        }
        .kpi-icon .bulb-glow-ghost {
            animation: kpiBulbGhost 2.4s ease-in-out infinite;
            opacity: 0;
        }
        @keyframes kpiBulbFlicker {
            0%, 100% { filter: drop-shadow(0 0 4px rgba(0, 115, 255, 0.35)); }
            50% { filter: drop-shadow(0 0 10px rgba(0, 115, 255, 0.7)); }
        }
        @keyframes kpiBulbGhost {
            0%, 100% { opacity: 0; }
            35% { opacity: 0.18; }
            55% { opacity: 0.35; }
            70% { opacity: 0.12; }
        }

        .kpi-icon .block-build {
            animation: kpiBlockGrow 3s ease-in-out infinite;
            transform-origin: bottom;
        }
        .kpi-icon .block-build:nth-child(2) { animation-delay: 0.3s; }
        .kpi-icon .block-build:nth-child(3) { animation-delay: 0.6s; }
        @keyframes kpiBlockGrow {
            0%, 100% { transform: scaleY(1); opacity: 1; }
            50% { transform: scaleY(0.8); opacity: 0.7; }
        }

        .kpi-icon .pie-segment {
            animation: kpiPieExpand 3s ease-in-out infinite;
            transform-origin: center;
        }
        .kpi-icon .pie-slice {
            animation: kpiPieSlice 3.2s ease-in-out infinite;
            transform-origin: center;
        }
        .kpi-icon .pie-slice.slice-2 { animation-delay: 0.3s; }
        .kpi-icon .pie-slice.slice-3 { animation-delay: 0.6s; }
        @keyframes kpiPieExpand {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.08); }
        }
        @keyframes kpiPieSlice {
            0%, 100% { transform: scale(1); opacity: 0.9; }
            50% { transform: scale(1.12); opacity: 1; }
        }

        .kpi-icon .trend-line {
            stroke-dasharray: 80;
            stroke-dashoffset: 80;
            animation: kpiDrawTrend 3s ease-in-out infinite;
        }
        @keyframes kpiDrawTrend {
            0%, 100% { stroke-dashoffset: 80; }
            50% { stroke-dashoffset: 0; }
        }

        .kpi-icon .money-float {
            animation: kpiMoneyWave 2.5s ease-in-out infinite;
        }
        .kpi-icon .money-float:nth-child(2) { animation-delay: 0.2s; }
        .kpi-icon .money-float:nth-child(3) { animation-delay: 0.4s; }
        @keyframes kpiMoneyWave {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-3px); }
        }

        .kpi-icon .arrow-up {
            animation: kpiArrowLift 2.6s ease-in-out infinite;
            transform-origin: center;
        }
        @keyframes kpiArrowLift {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-3px); }
        }

        .kpi-label {
            font-size: 0.75rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #f8fafc;
            font-weight: 600;
        }

        .kpi-value {
            font-size: 1.4rem;
            font-weight: 700;
            color: #f8fafc;
            margin-top: 0.35rem;
        }

        .kpi-yoy {
            font-size: 0.8rem;
            font-weight: 600;
            margin-top: 0.35rem;
        }

        .kpi-yoy-positive {
            color: #16A34A;
        }

        .kpi-yoy-negative {
            color: #EF4444;
        }

        .kpi-yoy-neutral {
            color: #6B7280;
        }

        .kpi-mini {
            display: flex;
            align-items: flex-end;
            justify-content: center;
            gap: 8px;
            height: 62px;
            margin-top: 0.65rem;
        }

        .kpi-mini-item {
            flex: 1;
            min-width: 18px;
            max-width: 32px;
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
        }

        .kpi-mini-bar-wrap {
            flex: 1;
            width: 100%;
            display: flex;
            align-items: flex-end;
            justify-content: center;
        }

        .kpi-mini-bar {
            width: 100%;
            border-radius: 6px 6px 3px 3px;
            box-shadow: inset 0 -1px 0 rgba(15, 23, 42, 0.15);
        }

        .kpi-mini-label {
            font-size: 0.65rem;
            color: #f8fafc;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .kpi-mini-empty {
            font-size: 0.75rem;
            color: #9CA3AF;
            justify-content: center;
        }

        .segment-range-label {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9rem;
            font-weight: 600;
            color: #1f2937;
            margin-top: 0.5rem;
            margin-bottom: 0.25rem;
        }

        .segment-range-info {
            position: relative;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 18px;
            height: 18px;
            border-radius: 999px;
            background: #f3f4f6;
            border: 1px solid #0073ff;
            color: #111827;
            font-size: 12px;
            font-weight: 700;
            cursor: help;
        }

        .segment-range-info::after {
            content: attr(data-tooltip);
            position: absolute;
            right: 0;
            top: 28px;
            width: 240px;
            padding: 8px 10px;
            background: #111827;
            color: #ffffff;
            font-size: 12px;
            font-weight: 500;
            line-height: 1.4;
            border-radius: 8px;
            opacity: 0;
            pointer-events: none;
            transform: translateY(-4px);
            transition: opacity 0.15s ease, transform 0.15s ease;
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.18);
            z-index: 20;
        }

        .segment-range-info::before {
            content: "";
            position: absolute;
            right: 8px;
            top: 22px;
            border-width: 0 6px 6px 6px;
            border-style: solid;
            border-color: transparent transparent #111827 transparent;
            opacity: 0;
            transition: opacity 0.15s ease;
        }

        .segment-range-info:hover::after,
        .segment-range-info:hover::before {
            opacity: 1;
            transform: translateY(0);
        }

        .thin-section-divider {
            border: none;
            border-top: 1px solid #e5e7eb;
            margin: 0.55rem 0 0.7rem;
            opacity: 0.65;
        }

        .insights-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 0.75rem;
            margin: 0.4rem 0 0.9rem;
        }

        .insights-carousel-wrap {
            position: relative;
            margin: 0.35rem 0 1.1rem;
        }

        .insights-carousel {
            display: flex;
            gap: 0.9rem;
            overflow-x: auto;
            scroll-behavior: smooth;
            padding: 0.25rem 0.25rem 0.6rem;
            scroll-snap-type: x mandatory;
        }

        .insights-carousel::-webkit-scrollbar {
            height: 8px;
        }

        .insights-carousel::-webkit-scrollbar-track {
            background: rgba(15, 23, 42, 0.06);
            border-radius: 999px;
        }

        .insights-carousel::-webkit-scrollbar-thumb {
            background: rgba(0, 115, 255, 0.45);
            border-radius: 999px;
        }

        .insights-carousel::-webkit-scrollbar-thumb:hover {
            background: rgba(0, 115, 255, 0.7);
        }

        .insight-card {
            flex: 0 0 320px;
            scroll-snap-align: start;
        }

        .segment-insight-card {
            border-radius: 14px;
            padding: 0.9rem 1rem;
            color: #ffffff !important;
            box-shadow: 0 10px 22px rgba(15, 23, 42, 0.18);
            min-height: 120px;
            position: relative;
            overflow: hidden;
        }

        .segment-insight-card,
        .segment-insight-card * {
            color: #ffffff !important;
        }

        .segment-insight-title {
            font-size: 0.9rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.65rem;
            color: #ffffff;
            line-height: 1.2;
        }

        .segment-insight-list {
            margin: 0;
            padding-left: 1rem;
            color: #ffffff;
            font-size: 0.84rem;
            line-height: 1.45;
            margin-top: 0.1rem;
        }

        .segment-insight-list li {
            margin-bottom: 0.4rem;
        }

        .segment-insight-list li:last-child {
            margin-bottom: 0;
        }

        .segment-insight-list li::marker {
            color: #ffffff !important;
        }

        .company-insight-card {
            background: #ffffff;
            border-radius: 14px;
            border: 1px solid #eef0f4;
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
            padding: 0.9rem 1rem;
            min-height: 120px;
        }

        .company-insight-title {
            font-size: 0.9rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.65rem;
            color: #111827;
            line-height: 1.2;
        }

        .company-insight-list {
            margin: 0;
            padding-left: 1rem;
            color: #1f2937;
            font-size: 0.84rem;
            line-height: 1.45;
            margin-top: 0.1rem;
        }

        .company-insight-list li {
            margin-bottom: 0.4rem;
        }

        .company-insight-list li:last-child {
            margin-bottom: 0;
        }

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

        .insights-nav {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            width: 36px;
            height: 36px;
            border-radius: 999px;
            border: none;
            background: rgba(0, 115, 255, 0.92);
            color: #ffffff;
            font-size: 18px;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 8px 16px rgba(15, 23, 42, 0.18);
            cursor: pointer;
            z-index: 5;
        }

        .insights-nav:disabled {
            opacity: 0.4;
            cursor: default;
        }

        .insights-nav.left {
            left: -14px;
        }

        .insights-nav.right {
            right: -14px;
        }

        @media (max-width: 900px) {
            .insight-card {
                flex-basis: 300px;
            }
            .insights-nav.left {
                left: -6px;
            }
            .insights-nav.right {
                right: -6px;
            }
        }

        .metrics-section-spacer {
            height: 12px;
        }

        @media (max-width: 1400px) {
            .kpi-grid {
                grid-template-columns: repeat(4, minmax(0, 1fr));
            }
        }

        @media (max-width: 1100px) {
            .kpi-grid {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
        }

    	    @media (max-width: 800px) {
            .stApp .block-container {
                padding-left: 1.25rem;
                padding-right: 1.25rem;
            }

            .kpi-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .company-name {
                font-size: 1.85rem;
            }

            .company-year {
                font-size: 1.85rem;
            }

            .company-logo {
                width: 52px;
                height: 52px;
            }
            .earnings-hero-stock {
                bottom: 0.9rem;
                right: 1.1rem;
            }

            .earnings-hero-stock .hero-stock-ticker {
                font-size: 2.1rem;
            }

    	        .earnings-hero-stock .hero-stock-price {
    	            font-size: 1.05rem;
    	        }

    	        .earnings-hero.has-stock {
    	            --stock-safe-right: 0px;
    	            --stock-safe-bottom: 170px;
    	        }

    	        .earnings-hero.has-stock .earnings-hero-overlay {
    	            padding-right: 1.25rem;
    	            padding-bottom: calc(1.25rem + var(--stock-safe-bottom));
    	        }
    	    }

        @media (max-width: 600px) {
            .stApp .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .kpi-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .company-logo {
                width: 48px;
                height: 48px;
            }

            .company-name {
                font-size: 1.65rem;
            }

            .company-year {
                font-size: 1.65rem;
            }

            .earnings-hero-stock {
                bottom: 0.8rem;
                left: 0.9rem;
                right: 0.9rem;
                min-width: 0;
                text-align: left;
            }

            .earnings-hero-stock .hero-stock-ticker {
                font-size: 1.85rem;
            }

            .earnings-hero-stock .hero-stock-price {
                font-size: 0.95rem;
            }

            .earnings-hero-stock .hero-stock-change {
                font-size: 0.85rem;
            }

            .earnings-hero-stock .hero-stock-sparkline {
                width: min(100%, 260px);
            }

            .earnings-hero.has-stock {
                --stock-safe-right: 0px;
                --stock-safe-bottom: 190px;
            }

            .earnings-hero.has-stock .earnings-hero-overlay {
                padding-right: 1rem;
                padding-bottom: calc(1rem + var(--stock-safe-bottom));
            }
        }

        @media (max-width: 430px) {
            .kpi-grid {
                grid-template-columns: 1fr;
            }

            .earnings-hero.has-stock {
                --stock-safe-bottom: 230px;
            }
        }

        /* Force all Plotly SVG text dark-theme */
        .js-plotly-plot .plotly .xtick text,
        .js-plotly-plot .plotly .ytick text,
        .js-plotly-plot .plotly .gtitle,
        .js-plotly-plot .plotly .g-xtitle text,
        .js-plotly-plot .plotly .g-ytitle text,
        .js-plotly-plot .plotly .legendtext,
        .js-plotly-plot .plotly .colorbar-title text,
        .js-plotly-plot .plotly .colorbar .tick text {
            fill: #8b949e !important;
        }
        .js-plotly-plot .plotly .gtitle {
            fill: #ffffff !important;
        }
        .js-plotly-plot .plotly .bg {
            fill: rgba(0,0,0,0) !important;
        }
        .modebar, .modebar-container {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
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
                plot.on('plotly_hover', (data) => {
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
                    } else {
                        const traces = plot.querySelectorAll(".barlayer .trace, .scatterlayer .trace, .boxlayer .trace");
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
                });
                plot.on('plotly_unhover', () => {
                    clearPop();
                });
            };

            const scan = () => {
                doc.querySelectorAll(".js-plotly-plot").forEach(bindPop);
            };

            scan();
            const observer = new MutationObserver(scan);
            observer.observe(doc.body, { childList: true, subtree: true });
        })();
        </script>
        """,
        height=0,
    )

    # Company colors for comparison charts
    COMPANY_COLORS = {
        "Alphabet": "#4285F4",
        "Google": "#4285F4",
        "Apple": "#000000",
        "Meta": "#0668E1",
        "Meta Platforms": "#0668E1",
        "Microsoft": "#00A4EF",
        "Amazon": "#FF9900",
        "Netflix": "#E50914",
        "Disney": "#113CCF",
        "Comcast": "#FFBA00",
        "Warner Bros. Discovery": "#D0A22D",
        "Warner Bros Discovery": "#D0A22D",
        "Paramount": "#000A3B",
        "Paramount Global": "#000A3B",
        "Spotify": "#1ED760",
        "Roku": "#6F1AB1",
    }

    BRAND_BLUE = "#0073ff"
    HOVERLABEL_STYLE = dict(
        bgcolor="rgba(10, 14, 26, 0.97)",
        bordercolor="rgba(99, 179, 237, 0.45)",
        font=dict(family='"DM Sans","Montserrat",system-ui,sans-serif', size=13, color="#e2e8f0"),
        align="left",
        namelength=-1,
    )

    PLOTLY_CONFIG = {
        "displayModeBar": False,
        "scrollZoom": False,
        "doubleClick": False,
        "showTips": False,
        "showAxisDragHandles": False,
        "modeBarButtonsToRemove": [
            "zoom2d",
            "pan2d",
            "select2d",
            "lasso2d",
            "zoomIn2d",
            "zoomOut2d",
            "autoScale2d",
            "resetScale2d",
        ],
    }

    def render_plotly(fig, xaxis_is_year=False, light_theme=False, key=None, **kwargs):
        # Always apply dark theme — ignore light_theme param entirely
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#374151"),
            hoverlabel=HOVERLABEL_STYLE,
        )
        fig.update_xaxes(
            tickfont=dict(color="#374151"),
            title_font=dict(color="#374151"),
            gridcolor="rgba(0,0,0,0.06)",
            gridwidth=0.5,
            showline=False,
            zeroline=False,
        )
        fig.update_yaxes(
            tickfont=dict(color="#374151"),
            title_font=dict(color="#374151"),
            gridcolor="rgba(0,0,0,0.06)",
            gridwidth=0.5,
            showline=False,
            zeroline=False,
        )
        fig.update_layout(legend=dict(
            font=dict(color="#374151"),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
        ))
        if xaxis_is_year:
            fig.update_xaxes(dtick=1, tickformat="d")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=key, **kwargs)

    def _auto_insight(data_dict: dict, company: str) -> str:
        """Generate a concise narrative insight from chart data.
        data_dict: {metric_name: {period: value}}. Returns HTML string.
        """
        if not data_dict:
            return ""
        all_vals = []
        for metric, periods in data_dict.items():
            for period, val in periods.items():
                if val is not None and not (isinstance(val, float) and val != val):
                    all_vals.append((metric, period, float(val)))
        if not all_vals:
            return ""
        all_vals.sort(key=lambda x: x[2])
        worst = all_vals[0]
        best = all_vals[-1]
        yoy_notes = []
        for metric, periods in data_dict.items():
            sorted_periods = sorted(periods.keys())
            if len(sorted_periods) >= 2:
                prev_val = periods[sorted_periods[-2]]
                curr_val = periods[sorted_periods[-1]]
                if prev_val and prev_val != 0 and curr_val is not None:
                    yoy = (float(curr_val) - float(prev_val)) / abs(float(prev_val)) * 100
                    if abs(yoy) >= 15:
                        direction = "▲" if yoy > 0 else "▼"
                        color = "#3fb950" if yoy > 0 else "#f85149"
                        yoy_notes.append(
                            f"<span style='color:{color};'>{direction} {metric}: "
                            f"{yoy:+.1f}% vs prior period</span>"
                        )
        insight_parts = []
        if yoy_notes:
            insight_parts.append("Notable moves: " + " &nbsp;·&nbsp; ".join(yoy_notes[:3]))
        insight_parts.append(
            f"<span style='color:#8b949e;'>Period high: "
            f"<b style='color:#e6edf3;'>{best[0]}</b> at "
            f"<b style='color:#3fb950;'>{best[2]:,.1f}</b> ({best[1]})</span>"
        )
        insight_parts.append(
            f"<span style='color:#8b949e;'>Period low: "
            f"<b style='color:#e6edf3;'>{worst[0]}</b> at "
            f"<b style='color:#f85149;'>{worst[2]:,.1f}</b> ({worst[1]})</span>"
        )
        return (
            "<div style='margin-top:10px; padding:10px 16px; "
            "background:#0d1117; border-left:3px solid #ff5b1f; "
            "border-radius:0 6px 6px 0; font-size:12px; "
            "font-family:\"DM Mono\",monospace; line-height:1.8;'>"
            + "<br>".join(insight_parts)
            + "</div>"
        )

    HEATMAP_COLORSCALE = [
        [0.0, "#EAF2FF"],
        [0.5, "#8BB6FF"],
        [1.0, "#1B73FF"],
    ]

    COMPANY_PALETTES = {
        "Alphabet": ["#4285F4", "#34A853", "#F59E0B", "#F6BF26", "#8B9094", "#A3AAAE"],
        "Amazon": ["#FFA826", "#262626", "#C98826", "#FF9900", "#C47500", "#4D4D4D", "#FFD89D"],
        "Apple": ["#111111", "#007AFF", "#34C759", "#5AC8FA", "#AF52DE", "#353535"],
        "Meta": ["#0668E1", "#2693FC", "#1C2B33"],
        "Meta Platforms": ["#0668E1", "#2693FC", "#1C2B33"],
        "Microsoft": ["#0073A7", "#F46A43", "#00A4EF", "#268BC0", "#FFB900", "#737373"],
        "Netflix": ["#E92E37", "#B20710", "#BE2C34", "#E50914"],
        "Disney": ["#00C2FF", "#081E66", "#A2D0D7", "#FF9500", "#3559D6", "#6F878B"],
        "Comcast": ["#FFBA00", "#F56F02", "#CB1F47", "#645DAC", "#0088D2", "#00B345"],
        "Warner Bros. Discovery": ["#4D71D4", "#2652CA", "#B18A26", "#D0A22D", "#DDBC67", "#0034C1"],
        "Warner Bros Discovery": ["#4D71D4", "#2652CA", "#B18A26", "#D0A22D", "#DDBC67", "#0034C1"],
        "Paramount": ["#00C2FF", "#1B73FF", "#000A3B", "#262F58", "#4D5476", "#737890", "#A3AAAE"],
        "Paramount Global": ["#00C2FF", "#1B73FF", "#000A3B", "#262F58", "#4D5476", "#737890", "#A3AAAE"],
        "Spotify": ["#1ED760", "#40DD78", "#79E7A0"],
        "Roku": ["#853CBD", "#6F1AB1"],
    }

    FALLBACK_SEGMENT_PALETTE = [
        "#1B73FF",
        "#00C2FF",
        "#34C759",
        "#FF9500",
        "#AF52DE",
        "#FF3B30",
        "#FFD60A",
        "#0F9D58",
        "#FF6D00",
    ]

    COMPANY_LOGOS = {
        "Apple": "attached_assets/8.png",
        "Microsoft": "attached_assets/msft.png",
        "Alphabet": "attached_assets/Google_logo.png",
        "Google": "attached_assets/Google_logo.png",
        "Netflix": "attached_assets/Netflix_logo.png",
        "Meta": "attached_assets/Meta_logo.png",
        "Meta Platforms": "attached_assets/Meta_logo.png",
        "Amazon": "attached_assets/Amazon_icon.png",
        "Disney": "attached_assets/icons8-logo-disney-240.png",
        "Roku": "attached_assets/roku_logo.png",
        "Spotify": "attached_assets/Spotify_logo.png",
        "Comcast": "attached_assets/Comcast_logo.png",
        "Paramount": "attached_assets/Paramount_logo.png",
        "Paramount Global": "attached_assets/Paramount_logo.png",
        "Warner Bros Discovery": "attached_assets/WarnerBrosDiscovery_log.png",
        "Warner Bros. Discovery": "attached_assets/WarnerBrosDiscovery_log.png",
    }

    SEGMENT_TRANSCRIPT_KEYWORDS = {
        "google search": ["search", "search revenue", "search advertising", "query", "search queries"],
        "google search & other": ["search", "search revenue", "search advertising", "query", "search queries"],
        "youtube ads": ["youtube", "youtube ads", "video advertising", "reels", "shorts"],
        "google network": ["network", "google network", "adsense", "admob", "programmatic"],
        "google cloud": ["cloud", "google cloud", "gcp", "cloud revenue", "cloud growth"],
        "google other": ["devices", "hardware", "pixel", "nest", "play store", "app store"],
        "other bets": ["other bets", "waymo", "deepmind", "moonshot"],
        "aws": ["aws", "amazon web services", "cloud", "cloud revenue"],
        "online stores": ["online stores", "first party", "retail", "e-commerce", "online retail"],
        "third-party seller services": ["third party", "3p", "marketplace", "seller services", "fulfillment"],
        "advertising services": ["advertising", "ads", "sponsored", "ad revenue", "advertising revenue"],
        "subscription services": ["prime", "subscription", "prime membership"],
        "physical stores": ["whole foods", "physical stores", "retail stores"],
        "iphone": ["iphone", "iphone revenue", "iphone units", "smartphone"],
        "mac": ["mac", "macbook", "macos", "personal computer"],
        "ipad": ["ipad", "tablet"],
        "wearables": ["wearables", "apple watch", "airpods", "accessories"],
        "services": ["services", "app store", "apple music", "icloud", "apple tv", "services revenue"],
        "family of apps": ["family of apps", "facebook", "instagram", "whatsapp", "messenger", "reels", "threads"],
        "reality labs": ["reality labs", "quest", "vr", "virtual reality", "metaverse", "ar glasses"],
        "intelligent cloud": ["azure", "cloud", "server products", "intelligent cloud"],
        "productivity and business processes": ["office", "microsoft 365", "linkedin", "dynamics", "productivity"],
        "more personal computing": ["windows", "gaming", "xbox", "bing", "surface", "personal computing"],
        "ucan": ["ucan", "united states", "canada", "north america", "us revenue"],
        "emea": ["emea", "europe", "middle east", "africa", "european"],
        "latam": ["latam", "latin america", "brazil", "mexico"],
        "apac": ["apac", "asia pacific", "japan", "korea", "india"],
        "entertainment": ["disney+", "hulu", "streaming", "disney entertainment", "content"],
        "sports": ["espn", "sports", "live sports", "nfl", "nba"],
        "experiences": ["parks", "theme parks", "experiences", "cruise", "disney parks"],
        "linear networks": ["abc", "linear", "cable", "broadcast", "fx", "national geographic"],
        "connectivity and platforms": ["broadband", "internet", "connectivity", "xfinity", "wireless"],
        "content and experiences": ["nbcuniversal", "nbc", "peacock", "universal", "content"],
        "sky": ["sky", "sky uk", "sky germany", "european pay"],
        "premium": ["premium", "paid subscribers", "premium revenue", "subscription"],
        "ad-supported": ["ad supported", "free tier", "ad revenue", "advertising", "mau"],
        "platform": ["platform", "the roku channel", "streaming", "active accounts", "arpu"],
        "devices": ["devices", "player", "hardware", "streaming player"],
        "distribution": ["distribution", "max", "hbo max", "streaming", "subscribers"],
        "advertising": ["advertising", "ad revenue", "upfront", "linear ad"],
        "content": ["content", "film", "theatrical", "warner bros", "studio"],
        "dtc": ["paramount+", "direct to consumer", "streaming", "dtc", "pluto"],
        "tv media": ["cbs", "linear", "tv media", "broadcast", "cable"],
        "filmed entertainment": ["film", "theatrical", "box office", "paramount pictures"],
        "north america": ["north america", "us", "united states"],
        "europe": ["europe", "european"],
        "rest of world": ["rest of world", "international", "global"],
        "us": ["united states", "us revenue", "domestic"],
        "international": ["international", "global", "europe", "rest of world"],
    }

    def _normalize_seg_key(s: str) -> str:
        return str(s).lower().strip().replace("-", " ").replace("_", " ")

    COMPANY_TICKERS = {
        "Alphabet": ["GOOGL", "GOOG"],
        "Google": ["GOOGL", "GOOG"],
        "Apple": ["AAPL"],
        "Meta": ["META", "FB"],
        "Meta Platforms": ["META", "FB"],
        "Microsoft": ["MSFT"],
        "Amazon": ["AMZN"],
        "Netflix": ["NFLX"],
        "Disney": ["DIS"],
        "Comcast": ["CMCSA"],
        "Warner Bros. Discovery": ["WBD"],
        "Warner Bros Discovery": ["WBD"],
        "Paramount": ["PARA"],
        "Paramount Global": ["PARA"],
        "Spotify": ["SPOT"],
        "Roku": ["ROKU"],
    }

    COMPANY_HERO_IMAGES = {
        "Alphabet": "attached_assets/AlphabetGoogleHero.png",
        "Meta": "attached_assets/MetaHero.png",
        "Apple": "attached_assets/AppleHEro.png",
        "Microsoft": "attached_assets/MicrosoftHero.png",
        "Amazon": "attached_assets/AmazonHero.png",
        "Netflix": "attached_assets/NetflixHero.png",
        "Disney": "attached_assets/DisneyHero.png",
        "Comcast": "attached_assets/ComcastHero.png",
        "Paramount": "attached_assets/ParamountHero.png",
        "Warner Bros Discovery": "attached_assets/WarnerBrosDiscovery.png",
        "Spotify": "attached_assets/SpotifyHero.png",
        "Roku": "attached_assets/RokuHero.png",
    }

    QUARTERLY_COMPANY_MAP = {
        "Meta": "Meta Platforms",
        "Paramount": "Paramount Global",
        "Warner Bros": "Warner Bros. Discovery",
        "Warner Bros.": "Warner Bros. Discovery",
    }

    COMPANY_ALIASES = {
        "Google": "Alphabet",
        "Meta Platforms": "Meta",
        "Amazon.com": "Amazon",
        "Amazon.com, Inc.": "Amazon",
        "Warner Bros. Discovery": "Warner Bros Discovery",
        "Warner Bros": "Warner Bros Discovery",
        "Paramount Global": "Paramount",
    }

    GLOBAL_SEGMENT_RULES = []

    SEGMENT_RULES = {
        "Alphabet": [
            (["youtube"], "#FF0000"),
            (["search", "ads"], "#4285F4"),
            (["cloud"], "#34A853"),
            (["network"], "#F59E0B"),
            (["subs", "subscription", "platforms", "devices"], "#F6BF26"),
            (["other bets"], "#8B9094"),
            (["hedging", "other"], "#A3AAAE"),
        ],
        "Amazon": [
            (["aws"], "#FFA826"),
            (["online", "north america"], "#262626"),
            (["third-party", "third party", "reseller", "seller services"], "#C98826"),
            (["adv", "advertising", "ads"], "#FF9900"),
            (["subscription"], "#C47500"),
            (["physical"], "#4D4D4D"),
            (["international", "other"], "#FFD89D"),
        ],
        "Apple": [
            (["iphone"], "#111111"),
            (["mac"], "#007AFF"),
            (["ipad"], "#34C759"),
            (["services"], "#5AC8FA"),
            (["wearables", "wearable", "home", "accessories", "accessory"], "#AF52DE"),
            (["ipod", "legacy"], "#353535"),
        ],
        "Meta": [
            (["family"], "#0668E1"),
            (["reality"], "#2693FC"),
            (["other"], "#1C2B33"),
        ],
        "Microsoft": [
            (["linkedin"], "#268BC0"),
            (["search", "news", "online services"], "#FFB900"),
            (["productivity", "business processes", "office", "commercial licensing", "microsoft business division", "dynamics", "company services"], "#F46A43"),
            (["intelligent cloud", "server and cloud", "server and tools", "server", "cloud"], "#0073A7"),
            (["gaming", "xbox"], "#34C759"),
            (["devices", "device", "hardware", "surface"], "#737373"),
            (["windows"], "#00A4EF"),
            (["more personal computing", "phone", "entertainment", "computing"], "#00A4EF"),
            (["commercial other", "corporate", "unallocated", "other"], "#737373"),
        ],
        "Netflix": [
            (["ucan"], "#E92E37"),
            (["emea"], "#B20710"),
            (["latam"], "#BE2C34"),
            (["apac"], "#E50914"),
        ],
        "Disney": [
            (["parks", "experiences", "resorts", "domestic parks", "international parks", "consumer products", "interactive media"], "#00C2FF"),
            (["media networks", "linear", "espn"], "#081E66"),
            (["direct-to", "dtc"], "#A2D0D7"),
            (["studio"], "#FF9500"),
            (["licensing", "content sales"], "#3559D6"),
            (["elimination", "eliminations", "intrasegment"], "#6F878B"),
        ],
        "Comcast": [
            (["nbc", "media"], "#0088D2"),
            (["theme park", "theme parks"], "#00B345"),
            (["corporate", "elimination", "eliminations"], "#A3AAAE"),
        ],
        "Warner Bros Discovery": [
            (["networks"], "#4D71D4"),
            (["dtc"], "#2652CA"),
            (["studios"], "#B18A26"),
            (["advertising"], "#D0A22D"),
            (["distribution"], "#DDBC67"),
            (["corporate", "elimination", "eliminations", "other"], "#0034C1"),
        ],
        "Paramount": [
            (["tv media", "tv"], "#00C2FF"),
            (["filmed"], "#1B73FF"),
            (["advertising"], "#000A3B"),
            (["affiliate"], "#262F58"),
            (["licensing", "content"], "#4D5476"),
            (["dtc"], "#737890"),
            (["elimination", "eliminations"], "#A3AAAE"),
        ],
        "Spotify": [
            (["premium"], "#1ED760"),
            (["ad-supported", "ad supported", "ad"], "#111111"),
            (["total", "totale"], "#79E7A0"),
        ],
        "Roku": [
            (["platform"], "#853CBD"),
            (["device"], "#6F1AB1"),
        ],
    }

    AVAILABLE_METRICS = {
        "Revenue": "revenue",
        "Net Income": "net_income",
        "Operating Income": "operating_income",
        "Cost of Revenue": "cost_of_revenue",
        "R&D": "rd",
        "CapEx": "capex",
        "Total Assets": "total_assets",
        "Debt": "debt",
        "Cash Balance": "cash_balance",
        "Market Cap": "market_cap",
    }


    @st.cache_data
    def load_stock_data(excel_path, source_stamp=0):
        """Load stock data only when needed."""
        if not excel_path:
            return pd.DataFrame()
        try:
            merged = load_combined_stock_market_data(
                excel_path=excel_path,
                source_stamp=int(source_stamp or 0),
                include_baseline=True,
                include_daily=True,
                include_minute=True,
            )
            if merged is None or merged.empty:
                return pd.DataFrame()
            df = merged.copy()
            if "tag" not in df.columns:
                df["tag"] = ""
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["price"] = pd.to_numeric(df["price"], errors="coerce")
            df["asset"] = df["asset"].fillna("").astype(str).str.strip()
            df["tag"] = df["tag"].fillna("").astype(str).str.strip().str.upper()
            df = df.dropna(subset=["date", "price"])
            df = df[df["asset"] != ""]
            if df.empty:
                return pd.DataFrame()
            merged = df[[c for c in ["date", "price", "volume", "asset", "tag", "source_sheet"] if c in df.columns]].copy()
            return merged
        except Exception as exc:
            logger.warning("Stock data load failed: %s", exc)
            return pd.DataFrame()


    @st.cache_data
    def load_m2_data(excel_path):
        """Load M2 macro data from the Excel source."""
        if not excel_path:
            return pd.DataFrame()
        try:
            _df = None
            for _sn in ("M2", "M2_values"):
                try:
                    _df = pd.read_excel(excel_path, sheet_name=_sn)
                    if _df is not None and not _df.empty:
                        break
                except Exception:
                    _df = None
            if _df is None or _df.empty:
                return pd.DataFrame()
            _df.columns = [str(c).strip() for c in _df.columns]
            _lowered = {c.lower(): c for c in _df.columns}
            _date_col = (_lowered.get("usd observation_date") or _lowered.get("observation_date")
                         or _lowered.get("date"))
            _val_col = (_lowered.get("wm2ns") or _lowered.get("m2sl") or _lowered.get("m2")
                        or _lowered.get("value"))
            if not _date_col or not _val_col:
                return pd.DataFrame()
            df = _df[[_date_col, _val_col]].rename(columns={_date_col: "date", _val_col: "value"})
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            return df.dropna(subset=["date", "value"])
        except Exception as exc:
            logger.warning("M2 data load failed: %s", exc)
            return pd.DataFrame()


    @st.cache_data(show_spinner=False)
    def load_company_segment_insights(excel_path):
        if not excel_path:
            return pd.DataFrame()
        try:
            df = pd.read_excel(excel_path, sheet_name="Company_Segments_insights_text")
            df.columns = [str(c).strip().lower() for c in df.columns]
            required = {"company", "year", "segment", "insight"}
            if not required.issubset(df.columns):
                raise ValueError(f"Missing columns in segment insights: {sorted(required - set(df.columns))}")
            if "category" not in df.columns:
                df["category"] = ""
            if "quarter" not in df.columns:
                df["quarter"] = ""
            return df
        except Exception as exc:
            logger.warning("Segment insights load failed: %s", exc)
            return pd.DataFrame()


    @st.cache_data(show_spinner=False)
    def load_company_insights_text(excel_path):
        if not excel_path:
            return pd.DataFrame()
        try:
            df = pd.read_excel(excel_path, sheet_name="Company_insights_text")
            df.columns = [str(c).strip().lower() for c in df.columns]
            required = {"company", "year", "insight"}
            if not required.issubset(df.columns):
                raise ValueError(f"Missing columns in company insights: {sorted(required - set(df.columns))}")
            if "category" not in df.columns:
                df["category"] = ""
            if "quarter" not in df.columns:
                df["quarter"] = ""
            return df
        except Exception as exc:
            logger.warning("Company insights load failed: %s", exc)
            return pd.DataFrame()


    @st.cache_data(show_spinner=False)
    def load_company_auto_narratives(excel_path):
        try:
            df = pd.read_excel(excel_path, sheet_name="Company_Auto_Narratives")
            df.columns = [str(c).strip().lower() for c in df.columns]
            return df
        except Exception:
            return pd.DataFrame()


    @st.cache_data(show_spinner=False)
    def _load_transcript_for_company(excel_path: str, company: str, year: int, quarter: str = "") -> str:
        """Load transcript text for a company/year/quarter from the Transcripts sheet."""
        if not excel_path:
            return ""
        try:
            df = pd.read_excel(excel_path, sheet_name="Transcripts")
            df.columns = [str(c).strip().lower() for c in df.columns]
            if not {"company", "year", "transcript_text"}.issubset(set(df.columns)):
                return ""
            df["_comp_norm"] = df["company"].astype(str).str.strip().str.lower()
            df["_year"] = pd.to_numeric(df["year"], errors="coerce")
            comp_norm = str(company).strip().lower()
            matches = df[(df["_comp_norm"] == comp_norm) & (df["_year"] == int(year))]
            if matches.empty:
                matches = df[
                    (df["_comp_norm"] == comp_norm)
                    & (df["_year"] >= int(year) - 1)
                    & (df["_year"] <= int(year) + 1)
                ]
            if matches.empty:
                return ""
            if quarter and "quarter" in df.columns:
                q_matches = matches[
                    matches["quarter"].astype(str).str.upper().str.strip() == str(quarter).upper().strip()
                ]
                if not q_matches.empty:
                    matches = q_matches
            text = str(matches.iloc[0].get("transcript_text", "") or "")
            return text[:15000]
        except Exception:
            return ""

    def _find_best_transcript_sentence(transcript_text: str, segment_name: str, max_len: int = 220) -> str:
        """Find the most relevant sentence in a transcript for a given segment."""
        if not transcript_text or not segment_name:
            return ""
        seg_key = _normalize_seg_key(segment_name)
        keywords = SEGMENT_TRANSCRIPT_KEYWORDS.get(seg_key, [])
        if not keywords:
            words = [w for w in seg_key.split() if len(w) > 3]
            keywords = words if words else [seg_key]
        sentences = re.split(r'(?<=[.!?])\s+', transcript_text)
        best_sentence = ""
        best_score = 0
        for sentence in sentences:
            s = sentence.strip()
            if len(s) < 30 or len(s) > 350:
                continue
            s_lower = s.lower()
            score = sum(1 for kw in keywords if kw in s_lower)
            if score == 0:
                continue
            financial_bonus = sum(1 for term in [
                "revenue", "growth", "billion", "million", "margin", "profit",
                "expect", "guidance", "quarter", "year", "increase", "grew"
            ] if term in s_lower)
            score += financial_bonus * 0.3
            if len(s) < 60:
                score *= 0.5
            if score > best_score:
                best_score = score
                best_sentence = s
        if not best_sentence or best_score < 0.8:
            return ""
        if len(best_sentence) > max_len:
            best_sentence = best_sentence[:max_len].rsplit(" ", 1)[0] + "\u2026"
        return best_sentence

    def _build_auto_segment_insight(
        segment_name: str,
        segment_revenue,
        segment_yoy,
        transcript_sentence: str,
        year: int,
        quarter: str = "",
    ) -> str:
        """Build a compact auto-generated insight when no manual Excel insight exists."""
        parts = []
        period = f"{year} {quarter}".strip() if quarter else str(year)
        if segment_revenue is not None and not pd.isna(segment_revenue):
            rev_b = segment_revenue / 1000
            rev_str = f"${rev_b:.1f}B" if rev_b >= 1 else f"${segment_revenue:.0f}M"
            if segment_yoy is not None and not pd.isna(segment_yoy):
                sign = "+" if segment_yoy >= 0 else ""
                parts.append(f"{segment_name} generated {rev_str} in {period} ({sign}{segment_yoy:.1f}% YoY).")
            else:
                parts.append(f"{segment_name} generated {rev_str} in {period}.")
        if transcript_sentence:
            parts.append(f'On the earnings call: "{transcript_sentence}"')
        if not parts:
            return ""
        return " ".join(parts)

    def _parse_quarter_int(value) -> int | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        text = str(value).strip().upper()
        if not text:
            return None
        if text in {"ANNUAL", "FY", "YEARLY", "YEAR"}:
            return None
        if text.startswith("Q") and len(text) > 1 and text[1].isdigit():
            q = int(text[1])
            return q if 1 <= q <= 4 else None
        match = re.search(r"\b([1-4])\b", text)
        if match:
            return int(match.group(1))
        num = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.isna(num):
            return None
        q = int(num)
        return q if 1 <= q <= 4 else None


    @st.cache_data(show_spinner=False)
    def _load_quarterly_kpis(excel_path: str, file_mtime=0) -> pd.DataFrame:
        if not excel_path:
            return pd.DataFrame()
        try:
            df = pd.read_excel(excel_path, sheet_name="Company_Quarterly_segments_valu")
        except Exception as exc:
            logger.warning("Quarterly KPI sheet load failed: %s", exc)
            return pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()

        out = df.copy().sort_index()
        out.columns = [str(c).strip() for c in out.columns]
        if "Ticker" not in out.columns or "Year" not in out.columns:
            return pd.DataFrame()

        out["Ticker"] = out["Ticker"].astype(str).str.strip().str.upper()
        out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
        out = out.dropna(subset=["Ticker", "Year"]).copy()
        if out.empty:
            return pd.DataFrame()
        out["Year"] = out["Year"].astype(int)
        out["Quarter"] = out.groupby(["Ticker", "Year"]).cumcount() + 1

        counts = out.groupby(["Ticker", "Year"])["Quarter"].count().reset_index(name="quarter_count")
        complete = counts[counts["quarter_count"] == 4][["Ticker", "Year"]]
        out = out.merge(complete, on=["Ticker", "Year"], how="inner")
        if out.empty:
            return pd.DataFrame()

        rename_map = {
            "Revenue": "revenue",
            "Cost Of Revenue": "cost_of_revenue",
            "Operating Income": "operating_income",
            "Net Income": "net_income",
            "Capex": "capex",
            "R&D": "rd",
            "Total Assets": "total_assets",
            "Cash Balance": "cash_balance",
            "Debt": "debt",
            "Quarter": "quarter_num",
        }
        out = out.rename(columns=rename_map)

        numeric_cols = [
            "revenue",
            "cost_of_revenue",
            "operating_income",
            "net_income",
            "capex",
            "rd",
            "total_assets",
            "cash_balance",
            "debt",
        ]
        for col in numeric_cols:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce")
            else:
                out[col] = np.nan

        ticker_to_company = {}
        for company_name, tickers in COMPANY_TICKERS.items():
            for t in tickers:
                ticker_to_company[str(t).strip().upper()] = normalize_company(company_name)

        out["company"] = out["Ticker"].map(ticker_to_company).fillna(out["Ticker"]).apply(normalize_company)
        out["period_label"] = out["Year"].astype(str) + " Q" + out["quarter_num"].astype(int).astype(str)
        keep_cols = [
            "company",
            "Ticker",
            "Year",
            "quarter_num",
            "period_label",
            *numeric_cols,
        ]
        return out[keep_cols].sort_values(["company", "Year", "quarter_num"]).reset_index(drop=True)


    def _get_available_quarters_for_earnings(
        selected_year: int,
        company_name: str,
        quarterly_kpis_df: pd.DataFrame,
    ) -> list[int]:
        canonical = normalize_company(company_name)
        all_quarters: set[int] = set()
        # Source 1: quarterly KPIs sheet
        if quarterly_kpis_df is not None and not quarterly_kpis_df.empty:
            kpi_q = get_available_quarters(quarterly_kpis_df, year=int(selected_year), company=canonical)
            all_quarters.update(kpi_q)
        # Source 2: quarterly segments sheet (may have quarters KPIs sheet lacks)
        try:
            _seg_df = getattr(data_processor, "df_quarterly_segments", None)
            if _seg_df is None:
                from utils.workbook_source import resolve_financial_data_xlsx
                _ep = resolve_financial_data_xlsx()
                if _ep:
                    _seg_df = pd.read_excel(_ep, sheet_name="Company_Quarterly_segments_valu")
            if _seg_df is not None and not _seg_df.empty:
                _seg_df.columns = [str(c).strip() for c in _seg_df.columns]
                _co_col = next((c for c in _seg_df.columns if c.lower().strip() == "company"), None)
                _yr_col = next((c for c in _seg_df.columns if c.lower().strip() == "year"), None)
                _q_col = next((c for c in _seg_df.columns if "quarter" in c.lower()), None)
                if _co_col and _yr_col and _q_col:
                    _mask = (_seg_df[_co_col].astype(str).str.strip() == canonical) & (pd.to_numeric(_seg_df[_yr_col], errors="coerce") == int(selected_year))
                    for qv in _seg_df.loc[_mask, _q_col].dropna().unique():
                        qs = str(qv).strip().upper()
                        if qs.startswith("Q") and len(qs) > 1 and qs[1].isdigit():
                            q_int = int(qs[1])
                            if 1 <= q_int <= 4:
                                all_quarters.add(q_int)
                        elif str(qv).strip().isdigit():
                            q_int = int(str(qv).strip())
                            if 1 <= q_int <= 4:
                                all_quarters.add(q_int)
        except Exception:
            pass
        return sorted(all_quarters)


    def _get_quarterly_metrics_snapshot(
        company_name: str,
        selected_year: int,
        selected_quarter: str,
        quarterly_kpis_df: pd.DataFrame,
        annual_metrics: dict,
    ) -> tuple[dict | None, str]:
        qnum = _parse_quarter_int(selected_quarter)
        if qnum is None or quarterly_kpis_df is None or quarterly_kpis_df.empty:
            return None, f"Annual {selected_year}"

        canonical = normalize_company(company_name)
        current = quarterly_kpis_df[
            (quarterly_kpis_df["company"] == canonical)
            & (quarterly_kpis_df["Year"] == int(selected_year))
            & (quarterly_kpis_df["quarter_num"] == int(qnum))
        ].copy()
        if current.empty:
            return None, f"Annual {selected_year}"

        row = current.iloc[0]
        output = {}
        metric_keys = [
            "revenue",
            "cost_of_revenue",
            "operating_income",
            "net_income",
            "capex",
            "rd",
            "total_assets",
            "cash_balance",
            "debt",
        ]
        for key in metric_keys:
            output[key] = row.get(key)
            output[f"{key}_yoy"] = np.nan

        # Keep market cap from annual sheet when quarterly source does not provide it.
        output["market_cap"] = annual_metrics.get("market_cap") if isinstance(annual_metrics, dict) else None
        output["market_cap_yoy"] = annual_metrics.get("market_cap_yoy") if isinstance(annual_metrics, dict) else np.nan

        prev = quarterly_kpis_df[
            (quarterly_kpis_df["company"] == canonical)
            & (quarterly_kpis_df["Year"] == int(selected_year) - 1)
            & (quarterly_kpis_df["quarter_num"] == int(qnum))
        ]
        if not prev.empty:
            prev_row = prev.iloc[0]
            for key in metric_keys:
                cur = pd.to_numeric(pd.Series([output.get(key)]), errors="coerce").iloc[0]
                prv = pd.to_numeric(pd.Series([prev_row.get(key)]), errors="coerce").iloc[0]
                if pd.notna(cur) and pd.notna(prv) and float(prv) != 0:
                    output[f"{key}_yoy"] = ((float(cur) - float(prv)) / float(prv)) * 100.0

        return output, f"Q{qnum} {selected_year}"


    def render_company_kpi_auto_block(metrics: dict, source_label: str) -> None:
        if not metrics:
            return
        st.markdown("#### KPI Auto Summary")
        st.caption(f"Source: {source_label}")
        row1 = (
            f"Revenue: {format_metric_value(metrics.get('revenue'))} ({format_yoy_value(metrics.get('revenue_yoy'))})  |  "
            f"Net Income: {format_metric_value(metrics.get('net_income'))} ({format_yoy_value(metrics.get('net_income_yoy'))})"
        )
        row2 = (
            f"Operating Income: {format_metric_value(metrics.get('operating_income'))} ({format_yoy_value(metrics.get('operating_income_yoy'))})  |  "
            f"Market Cap: {format_metric_value(metrics.get('market_cap'))}"
        )
        row3 = (
            f"R&D: {format_metric_value(metrics.get('rd'))}  |  "
            f"Capex: {format_metric_value(metrics.get('capex'))}  |  "
            f"Cash: {format_metric_value(metrics.get('cash_balance'))}  |  "
            f"Debt: {format_metric_value(metrics.get('debt'))}"
        )
        st.markdown(row1)
        st.markdown(row2)
        st.markdown(row3)


    def render_segment_breakdown_auto_block(
        canonical_company: str,
        selected_year: int,
        selected_quarter: str,
        yearly_segments_df: pd.DataFrame,
        quarterly_segments_df: pd.DataFrame,
    ) -> None:
        qnum = _parse_quarter_int(selected_quarter)
        segment_df = pd.DataFrame()
        period_label = f"Annual {selected_year}"

        if qnum is not None and quarterly_segments_df is not None and not quarterly_segments_df.empty:
            segment_df = quarterly_segments_df[
                (quarterly_segments_df["company"] == canonical_company)
                & (quarterly_segments_df["year"] == int(selected_year))
                & (quarterly_segments_df["quarter_num"] == int(qnum))
            ][["segment", "revenue"]].copy()
            period_label = f"Q{qnum} {selected_year}"

        if segment_df.empty and yearly_segments_df is not None and not yearly_segments_df.empty:
            segment_df = yearly_segments_df[
                (yearly_segments_df["company"] == canonical_company)
                & (pd.to_numeric(yearly_segments_df["year"], errors="coerce") == int(selected_year))
            ][["segment", "revenue"]].copy()

        if segment_df.empty:
            return

        segment_df["revenue"] = pd.to_numeric(segment_df["revenue"], errors="coerce")
        segment_df = segment_df.dropna(subset=["segment", "revenue"])
        segment_df = segment_df.groupby("segment", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        if segment_df.empty:
            return

        total = float(segment_df["revenue"].sum())
        if total <= 0:
            return

        top = segment_df.head(4).copy()
        top["share"] = (top["revenue"] / total) * 100.0
        summary = "  |  ".join(
            [f"{row.segment}: {format_metric_value(row.revenue)} ({row.share:.1f}%)" for row in top.itertuples(index=False)]
        )
        st.markdown("#### Segment Auto Breakdown")
        st.caption(f"Source: {period_label}")
        st.markdown(summary)


    def render_transcript_highlights(company_name: str, selected_year: int, selected_quarter: str) -> None:
        try:
            from utils.transcript_live import extract_ceo_cfo_quotes
            quotes = extract_ceo_cfo_quotes(
                str(data_processor.data_path),
                canonical_company,
                int(selected_year),
                selected_quarter if selected_quarter and selected_quarter != "Annual" else "",
            )
        except Exception:
            quotes = {"CEO": [], "CFO": []}

        if not quotes["CEO"] and not quotes["CFO"]:
            return

        period = f"Q{_parse_quarter_int(selected_quarter)} {selected_year}" if _parse_quarter_int(selected_quarter) else str(selected_year)
        st.markdown("#### Management commentary")

        for role, label, limit in [("CEO", "Chief Executive Officer", 3), ("CFO", "Chief Financial Officer", 2)]:
            role_quotes = quotes.get(role, [])[:limit]
            if not role_quotes:
                continue
            speaker_name = role_quotes[0]["speaker"]
            st.markdown(
                f"<div style='margin:12px 0 6px 0;'>"
                f"<span style='font-weight:700;color:#111827;font-size:0.9rem;'>{html.escape(speaker_name)}</span>"
                f"<span style='color:#6b7280;font-size:0.8rem;margin-left:8px;'>{label} · {period}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
            for q in role_quotes:
                st.markdown(
                    f"<div style='border-left:3px solid #e2e8f0;padding:8px 14px;margin-bottom:8px;"
                    f"background:#f9fafb;border-radius:0 6px 6px 0;'>"
                    f"<p style='margin:0;font-size:0.88rem;color:#374151;line-height:1.6;"
                    f"font-style:italic;'>\"{html.escape(q['quote'])}\"</p>"
                    f"</div>",
                    unsafe_allow_html=True
                )


    def parse_quarter_label(value):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        label = str(value).strip()
        if not label:
            return None
        patterns = [
            re.compile(r"^([1-4])Q(\d{2,4})$", re.IGNORECASE),
            re.compile(r"^Q([1-4])\s*(\d{2,4})$", re.IGNORECASE),
            re.compile(r"^(\d{2,4})\s*Q([1-4])$", re.IGNORECASE),
        ]
        for pattern in patterns:
            match = pattern.match(label)
            if match:
                first = match.group(1)
                second = match.group(2)
                if len(first) >= 3 or int(first) > 4:
                    year = int(first)
                    quarter = int(second)
                else:
                    quarter = int(first)
                    year = int(second)
                if year < 100:
                    year += 2000
                return year, quarter
        return None


    def extract_year_from_label(label):
        if label is None:
            return None
        match = re.search(r"(\\d{4})", str(label))
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None


    def build_quarter_axis(labels):
        category_order = []
        tickvals = []
        ticktext = []
        last_year = None
        gap_index = 0
        for label in labels:
            year = extract_year_from_label(label)
            if last_year is not None and year is not None and year != last_year:
                gap_label = f"gap-{last_year}-{gap_index}"
                category_order.append(gap_label)
                tickvals.append(gap_label)
                ticktext.append("")
                gap_index += 1
            category_order.append(label)
            tickvals.append(label)
            ticktext.append(label)
            last_year = year
        return category_order, tickvals, ticktext


    @st.cache_data(show_spinner=False)
    def load_quarterly_segments(excel_path, file_mtime=0):
        if not excel_path:
            return pd.DataFrame()
        try:
            xls = pd.ExcelFile(excel_path)
        except Exception as exc:
            logger.warning("Quarterly segments load failed: %s", exc)
            return pd.DataFrame()

        frames = []
        for sheet in xls.sheet_names:
            if "Quarterly Segments" not in sheet:
                continue
            try:
                df = pd.read_excel(xls, sheet_name=sheet)
            except Exception as exc:
                logger.warning("Quarterly segments read failed for %s: %s", sheet, exc)
                continue
            if df is None or df.empty:
                continue
            company_name = sheet.replace("Quarterly Segments", "").strip()
            # Strip trailing granularity suffixes (e.g. "Comcast Quarterly Segments Gran")
            for _sfx in ("Granular", "Gran"):
                if company_name.endswith(_sfx):
                    company_name = company_name[:-len(_sfx)].strip()
            company_name = QUARTERLY_COMPANY_MAP.get(company_name, company_name)
            # Align quarterly company names with the rest of the app (e.g., "Warner Bros." vs "Warner Bros").
            company_name = normalize_company(company_name)
            df = df.rename(columns={df.columns[0]: "Quarter"})
            df = df.melt(id_vars=["Quarter"], var_name="segment", value_name="revenue")
            df["segment"] = df["segment"].astype(str).str.strip()
            df = df[~df["segment"].str.contains("total", case=False, na=False)]
            df["quarter"] = df["Quarter"].astype(str).str.strip()
            parsed = df["quarter"].apply(parse_quarter_label)
            df["year"] = parsed.apply(lambda item: item[0] if item else None)
            df["quarter_num"] = parsed.apply(lambda item: item[1] if item else None)
            df = df.dropna(subset=["year", "quarter_num"])
            df["year"] = df["year"].astype(int)
            df["quarter_num"] = df["quarter_num"].astype(int)
            df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
            df = df.dropna(subset=["revenue"])
            df["company"] = company_name
            df["segment"] = df["segment"].apply(
                lambda value: normalize_segment_label(company_name, value)
            )
            df = df[df["segment"].notna() & (df["segment"].astype(str).str.strip() != "")]
            # Some quarterly sheets contain duplicate segment labels for the same quarter.
            # Collapse duplicates to avoid double-counting in hover/tooltips.
            df = (
                df.groupby(["company", "segment", "year", "quarter_num"], as_index=False)
                .agg(
                    revenue=("revenue", "max"),
                    quarter=("quarter", "first"),
                )
            )
            df["quarter"] = df["quarter"].fillna(
                df["year"].astype(int).astype(str) + " Q" + df["quarter_num"].astype(int).astype(str)
            )
            frames.append(df[["company", "quarter", "year", "quarter_num", "segment", "revenue"]])
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)


    @st.cache_data(show_spinner=False)
    def load_quarterly_company_metrics(excel_path, file_mtime=0):
        if not excel_path:
            return pd.DataFrame()
        # Build quarterly metrics from the per-company quarterly segment sheets.
        # This avoids the corrupted consolidated quarterly sheet where Q1 can contain annual totals.
        segments_df = load_quarterly_segments(excel_path, file_mtime)
        if segments_df is None or segments_df.empty:
            return pd.DataFrame()

        revenue_quarterly = (
            segments_df.groupby(["company", "year", "quarter_num"], as_index=False)["revenue"]
            .sum()
            .rename(columns={"revenue": "value"})
        )
        revenue_quarterly["metric_key"] = "revenue"
        records = [revenue_quarterly[["company", "year", "quarter_num", "metric_key", "value"]]]

        # Use annual company metrics for non-revenue KPIs and allocate to quarters based on
        # revenue seasonality shares (quarter revenue / annual revenue).
        try:
            xls = pd.ExcelFile(excel_path)
        except Exception as exc:
            logger.warning("Quarterly company metrics annual cross-reference failed: %s", exc)
            xls = None

        if xls is not None:
            annual_sheet = None
            for s in xls.sheet_names:
                if s == "Company_metrics_earnings_values":
                    annual_sheet = s
                    break
                if s.startswith("Company_metrics_earnings"):
                    annual_sheet = s
                    break

            if annual_sheet:
                try:
                    annual_df = pd.read_excel(xls, sheet_name=annual_sheet)
                except Exception as exc:
                    logger.warning("Annual metrics read failed for quarterly allocation: %s", exc)
                    annual_df = pd.DataFrame()

                if annual_df is not None and not annual_df.empty:
                    annual_df.columns = [str(c).strip() for c in annual_df.columns]
                    lowered = {str(c).strip().lower(): c for c in annual_df.columns}

                    year_col = lowered.get("year")
                    company_col = lowered.get("company") or lowered.get("player")
                    ticker_col = lowered.get("ticker") or lowered.get("symbol")

                    if year_col and (company_col or ticker_col):
                        annual_df = annual_df.rename(columns={year_col: "year"})
                        annual_df["year"] = pd.to_numeric(annual_df["year"], errors="coerce")
                        annual_df = annual_df.dropna(subset=["year"])
                        annual_df["year"] = annual_df["year"].astype(int)

                        if company_col:
                            annual_df["company"] = annual_df[company_col].astype(str).str.strip().apply(normalize_company)
                        else:
                            ticker_to_company = {}
                            for company_name, tickers in COMPANY_TICKERS.items():
                                for t in tickers:
                                    ticker_to_company[str(t).upper()] = normalize_company(company_name)
                            annual_df["ticker"] = annual_df[ticker_col].astype(str).str.strip().str.upper()
                            annual_df["company"] = annual_df["ticker"].map(ticker_to_company).fillna(annual_df["ticker"])

                        metric_cols = {}
                        preferred = {
                            "cost_of_revenue": lowered.get("cost of revenue") or lowered.get("cost_of_revenue"),
                            "operating_income": lowered.get("operating income") or lowered.get("operating_income"),
                            "net_income": lowered.get("net income") or lowered.get("net_income"),
                            "capex": lowered.get("capex"),
                            "rd": lowered.get("r&d") or lowered.get("rd") or lowered.get("r_d"),
                            "total_assets": lowered.get("total assets") or lowered.get("total_assets"),
                            "cash_balance": lowered.get("cash balance") or lowered.get("cash_balance"),
                            "debt": lowered.get("debt"),
                            "market_cap": lowered.get("market cap") or lowered.get("market_cap"),
                        }
                        for key, col in preferred.items():
                            if col and col in annual_df.columns:
                                metric_cols[key] = col

                        if metric_cols:
                            annual_keep = annual_df[["company", "year"] + list(metric_cols.values())].copy()
                            for col in metric_cols.values():
                                annual_keep[col] = pd.to_numeric(annual_keep[col], errors="coerce")
                            annual_keep = annual_keep.groupby(["company", "year"], as_index=False).sum(min_count=1)

                            shares = revenue_quarterly[["company", "year", "quarter_num", "value"]].copy()
                            shares = shares.rename(columns={"value": "revenue_value"})
                            annual_revenue = shares.groupby(["company", "year"], as_index=False)["revenue_value"].sum()
                            annual_revenue = annual_revenue.rename(columns={"revenue_value": "annual_revenue"})
                            shares = shares.merge(annual_revenue, on=["company", "year"], how="left")
                            shares["quarter_count"] = shares.groupby(["company", "year"])["quarter_num"].transform("count")
                            shares["share"] = np.where(
                                shares["annual_revenue"].fillna(0) > 0,
                                shares["revenue_value"] / shares["annual_revenue"],
                                1.0 / shares["quarter_count"].clip(lower=1),
                            )
                            shares = shares.drop(columns=["quarter_count"])

                            for metric_key, col in metric_cols.items():
                                metric_base = annual_keep[["company", "year", col]].copy()
                                metric_base = metric_base.rename(columns={col: "annual_value"})
                                metric_base = metric_base[metric_base["annual_value"].notna()]
                                if metric_base.empty:
                                    continue
                                merged = shares.merge(metric_base, on=["company", "year"], how="inner")
                                if merged.empty:
                                    continue
                                if metric_key in {"total_assets", "cash_balance", "debt", "market_cap"}:
                                    # Stock-style metrics are point-in-time levels; keep the annual level per quarter.
                                    metric_values = merged["annual_value"]
                                else:
                                    # Flow metrics are split by observed quarterly revenue seasonality.
                                    metric_values = merged["annual_value"] * merged["share"]
                                temp = merged[["company", "year", "quarter_num"]].copy()
                                temp["metric_key"] = metric_key
                                temp["value"] = metric_values
                                records.append(temp)

        if not records:
            return pd.DataFrame()

        result = pd.concat(records, ignore_index=True)
        result["value"] = pd.to_numeric(result["value"], errors="coerce")
        result = result.dropna(subset=["value"])
        result["year"] = pd.to_numeric(result["year"], errors="coerce").astype(int)
        result["quarter_num"] = pd.to_numeric(result["quarter_num"], errors="coerce").astype(int)
        result = result.sort_values(["company", "year", "quarter_num", "metric_key"])
        result["period_label"] = (
            result["year"].astype(int).astype(str)
            + " Q"
            + result["quarter_num"].astype(int).astype(str)
        )
        return result


    @st.cache_data
    def get_logo_base64(path, file_mtime=0):
        if not path or not os.path.exists(path):
            return ""
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()


    @st.cache_data
    def get_hero_base64(path, file_mtime=0, max_width=2200, quality=86):
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
        except Exception:
            return get_logo_base64(path, file_mtime), "image/png"


    def get_file_mtime(path):
        if not path:
            return 0
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0


    def normalize_company(company):
        return COMPANY_ALIASES.get(company, company)

    def get_default_company_selection(available_companies, selected_company):
        if not available_companies:
            return []
        if selected_company in available_companies:
            return [selected_company]
        return [available_companies[0]]


    DISNEY_PARKS_LABEL = "Parks, Experiences & Products"


    def normalize_segment(segment):
        return str(segment).strip().lower()


    def normalize_segment_label(company, segment):
        if segment is None or (isinstance(segment, float) and pd.isna(segment)):
            return ""
        label = str(segment).strip()
        key = normalize_segment(label)
        normalized_company = normalize_company(company)

        # Drop totals (they're not real segments for composition/insights views).
        if key in {"total", "totale", "total revenue", "total revenues", "revenue total"}:
            return ""
        if key.startswith("total ") or key.endswith(" total"):
            return ""

        if normalized_company == "Alphabet":
            if "youtube" in key:
                if "ad" in key or "ads" in key or "advertis" in key:
                    return "YouTube ads"
                return "YouTube ads"
            if "search" in key:
                return "Google Search & other"
            if "cloud" in key:
                return "Google Cloud"
            if "network" in key:
                return "Google Network"
            if any(k in key for k in ("subs", "subscription", "platform", "device")):
                return "Google subs, platforms and devices"
            if "other bets" in key:
                return "Other bets"
            if "hedging" in key:
                return "Hedging gains"

        if normalized_company == "Spotify":
            if "premium" in key:
                return "Premium"
            if "ad" in key:
                return "Ad Supported"

        if normalized_company == "Roku":
            if "platform" in key:
                return "Platform"
            if "player" in key or "device" in key:
                # Excel uses "Player" for insights; quarterly sheets often label it as "Devices/Player".
                return "Player"

        if normalized_company == "Amazon":
            if "aws" in key or "web service" in key:
                return "AWS"
            if "online" in key and "store" in key:
                return "Online Stores"
            if "physical" in key and "store" in key:
                return "Physical Stores"
            if "subscription" in key or "prime" in key:
                return "Subscription Services"
            if (
                "advert" in key
                or "adv service" in key
                or "ad service" in key
                or key in {"adv", "ads", "ad"}
            ):
                return "Advertising"
            if (
                ("third" in key and ("party" in key or "seller" in key or "reseller" in key))
                or "3p" in key
                or "third-party seller services" in key
            ):
                return "Third-Party Seller Services"
            if "other" in key:
                return "Other"

        if normalized_company == "Warner Bros Discovery":
            # Quarterly sheets use broad buckets (Distribution / Advertising / Content / Other),
            # while insights may contain more granular labels (e.g., Studios). Normalize to the
            # quarterly buckets so hover insights can match consistently.
            if "distrib" in key:
                return "Distribution"
            if "advert" in key:
                return "Advertising"
            if "content" in key or "studio" in key:
                return "Content"
            if "other" in key or "corporate" in key or "elimination" in key:
                return "Other"

        if normalized_company == "Disney":
            parks_keywords = [
                "parks",
                "experiences",
                "resorts",
                "domestic parks",
                "international parks",
                "consumer products",
                "interactive media",
            ]
            if any(keyword in key for keyword in parks_keywords):
                return DISNEY_PARKS_LABEL
        return label


    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


    def rgb_to_hex(rgb):
        return "#{:02X}{:02X}{:02X}".format(*rgb)


    def color_distance(hex_a, hex_b):
        a_r, a_g, a_b = hex_to_rgb(hex_a)
        b_r, b_g, b_b = hex_to_rgb(hex_b)
        return ((a_r - b_r) ** 2 + (a_g - b_g) ** 2 + (a_b - b_b) ** 2) ** 0.5


    def is_color_too_close(color, used_colors, threshold=38):
        if not color:
            return True
        return any(color_distance(color, used) < threshold for used in used_colors)


    def hex_to_rgba(hex_color, alpha):
        r, g, b = hex_to_rgb(hex_color)
        return f"rgba({r}, {g}, {b}, {alpha:.2f})"


    def pick_contrast_color(hex_color):
        r, g, b = hex_to_rgb(hex_color)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#111827" if luminance > 0.6 else "#FFFFFF"


    def blend_with_target(hex_color, target_hex, ratio):
        base = hex_to_rgb(hex_color)
        target = hex_to_rgb(target_hex)
        blended = tuple(int(round(b * ratio + t * (1 - ratio))) for b, t in zip(base, target))
        return rgb_to_hex(blended)


    def expand_palette(base_palette, needed):
        """Create deterministic tints for brands with fewer colors than segments."""
        if not base_palette:
            base_palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
        ratios = [1.0, 0.85, 0.7]
        palette = []
        for ratio in ratios:
            for color in base_palette:
                palette.append(blend_with_target(color, "#FFFFFF", ratio))
        if len(palette) < needed:
            for ratio in [0.9, 0.75]:
                for color in base_palette:
                    palette.append(blend_with_target(color, "#000000", ratio))
        deduped = []
        for color in palette:
            if color not in deduped:
                deduped.append(color)
        return deduped[:needed]


    def make_unique_color(base_color, used_colors, fallback_palette=None):
        if base_color and not is_color_too_close(base_color, used_colors):
            return base_color
        if fallback_palette:
            for candidate in fallback_palette:
                if not is_color_too_close(candidate, used_colors):
                    return candidate
        return base_color or "#9CA3AF"


    def next_palette_color(palette_iter, used_colors):
        for candidate in palette_iter:
            if not is_color_too_close(candidate, used_colors):
                return candidate
        return "#9CA3AF"


    def match_segment_color(company, segment):
        segment_key = normalize_segment(segment)
        rules = SEGMENT_RULES.get(company, [])
        for keywords, color in rules:
            if any(keyword in segment_key for keyword in keywords):
                return color
        for keywords, color in GLOBAL_SEGMENT_RULES:
            if any(keyword in segment_key for keyword in keywords):
                return color
        return None


    def get_segment_color_map(df_segments, company):
        """Assign deterministic, brand-aware colors per segment across years."""
        if df_segments is None or df_segments.empty:
            return {}
        canonical = normalize_company(company)
        raw_segments = df_segments[df_segments["company"] == company]["segment"].dropna().tolist()
        normalized = []
        for segment in raw_segments:
            label = normalize_segment_label(canonical, segment)
            if not label:
                continue
            if normalize_segment(label) == "total revenue":
                continue
            normalized.append(label)
        segments = sorted(set(normalized), key=str.lower)
        color_map = {}
        used_colors = set()
        palette = []
        for color in COMPANY_PALETTES.get(canonical, []):
            if color not in palette:
                palette.append(color)
        for color in FALLBACK_SEGMENT_PALETTE:
            if color not in palette:
                palette.append(color)
        palette_iter = iter(palette)

        for segment in segments:
            color = match_segment_color(canonical, segment)
            if color:
                color_map[segment] = color
                used_colors.add(color)
                continue
            color = next_palette_color(palette_iter, used_colors)
            color_map[segment] = color
            used_colors.add(color)

        return color_map


    def format_compact_value(value):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "N/A"
        try:
            value = float(value)
        except (TypeError, ValueError):
            return "N/A"
        abs_val = abs(value)
        if abs_val >= 1_000_000_000_000:
            scaled = value / 1_000_000_000_000
            suffix = "T"
        elif abs_val >= 1_000_000_000:
            scaled = value / 1_000_000_000
            suffix = "B"
        elif abs_val >= 1_000_000:
            scaled = value / 1_000_000
            suffix = "M"
        elif abs_val >= 1_000:
            scaled = value / 1_000
            suffix = "K"
        else:
            scaled = value
            suffix = ""

        if abs(scaled) >= 100:
            formatted = f"{scaled:.0f}"
        elif abs(scaled) >= 10:
            formatted = f"{scaled:.1f}"
        else:
            formatted = f"{scaled:.2f}"
        formatted = formatted.replace(".00", "").replace(".0", "")
        return f"{formatted}{suffix}"


    def format_metric_value(value, scale="millions"):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "N/A"
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return "N/A"
        if scale == "raw":
            return format_compact_value(numeric_value)
        # Guard against values already in raw dollars to avoid huge "B" outputs.
        if abs(numeric_value) >= 1e9:
            return format_compact_value(numeric_value)
        return format_number(numeric_value)


    def infer_metric_scale(df):
        if df is None or df.empty:
            return "millions"
        try:
            values = pd.to_numeric(pd.Series(df.to_numpy().ravel()), errors="coerce").dropna()
        except Exception:
            return "millions"
        if values.empty:
            return "millions"
        max_abs = values.abs().max()
        return "raw" if max_abs >= 1e7 else "millions"


    def get_metric_history(metrics_df, company, metric_key, available_years, window=5):
        if metrics_df is None or metrics_df.empty or not available_years:
            return []
        if metric_key not in metrics_df.columns:
            return []
        history_years = [int(y) for y in available_years][-window:]
        df_hist = metrics_df[
            (metrics_df["company"] == company) & (metrics_df["year"].isin(history_years))
        ][["year", metric_key]]
        if df_hist.empty:
            return []
        df_hist = df_hist.groupby("year", as_index=False)[metric_key].sum()
        values_by_year = {
            int(row["year"]): row[metric_key] for _, row in df_hist.iterrows()
        }
        history = []
        for year in history_years:
            history.append((int(year), values_by_year.get(int(year))))
        return history


    def build_kpi_history_bars(history, bar_color):
        if not history:
            return "<div class='kpi-mini kpi-mini-empty'>No history</div>"
        values = [
            value
            for _, value in history
            if value is not None and not (isinstance(value, float) and pd.isna(value))
        ]
        max_value = max(values) if values else 0
        if max_value <= 0:
            max_value = 1
        bars = []
        for year, value in history:
            if value is None or (isinstance(value, float) and pd.isna(value)):
                ratio = 0
                label_value = "N/A"
            else:
                ratio = max(float(value), 0) / max_value if max_value else 0
                label_value = format_metric_value(value)
            height_pct = 12 + (ratio * 88)
            alpha = 0.35 + (ratio * 0.55)
            bar_style = f"height: {height_pct:.0f}%; background: {hex_to_rgba(bar_color, alpha)};"
            label = str(year)[-2:]
            bars.append(
                "<div class='kpi-mini-item'>"
                "<div class='kpi-mini-bar-wrap'>"
                f"<div class='kpi-mini-bar' style='{bar_style}' title='{year}: {label_value}'></div>"
                "</div>"
                f"<div class='kpi-mini-label'>{label}</div>"
                "</div>"
            )
        return "<div class='kpi-mini'>" + "".join(bars) + "</div>"


    def format_stock_value(value):
        if value is None or pd.isna(value):
            return "N/A"
        return f"${value:,.2f}"


    def normalize_heatmap(pivot_df):
        if pivot_df is None or pivot_df.empty:
            return pivot_df
        values = [
            value
            for value in pivot_df.to_numpy().flatten().tolist()
            if value is not None and not pd.isna(value)
        ]
        if not values:
            return pivot_df
        min_val = min(values)
        max_val = max(values)
        if max_val == min_val:
            normalized = pivot_df.copy().astype(float)
            normalized = normalized.applymap(
                lambda v: 0.5 if not pd.isna(v) else None
            )
            return normalized
        normalized = (pivot_df - min_val) / (max_val - min_val)
        return normalized


    def compute_heatmap_change(pivot_df):
        if pivot_df is None or pivot_df.empty:
            return pivot_df
        ordered = pivot_df.copy()
        ordered = ordered.reindex(columns=list(ordered.columns))
        change = ordered.pct_change(axis=1) * 100
        change = change.replace([np.inf, -np.inf], np.nan)
        return change


    def get_company_segments(segments_df, company):
        if segments_df is None or segments_df.empty:
            return []
        df = segments_df[segments_df["company"] == company]
        if df.empty:
            return []
        labels = []
        for segment in df["segment"].dropna().tolist():
            label = normalize_segment_label(company, segment)
            if not label or label == "Total Revenue":
                continue
            labels.append(label)
        return sorted(set(labels), key=str.lower)


    @st.cache_data(show_spinner=False)
    def build_metric_heatmap_data(metrics_df, companies, metric_key, year_start, year_end):
        if metrics_df is None or metrics_df.empty or not companies:
            return pd.DataFrame()
        if metric_key not in metrics_df.columns:
            return pd.DataFrame()
        df = metrics_df[
            (metrics_df["company"].isin(companies))
            & (metrics_df["year"] >= year_start)
            & (metrics_df["year"] <= year_end)
        ][["company", "year", metric_key]].dropna()
        if df.empty:
            return pd.DataFrame()
        df = df.groupby(["company", "year"], as_index=False)[metric_key].sum()
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
        years = list(range(int(year_start), int(year_end) + 1))
        pivot = df.pivot(index="company", columns="year", values=metric_key)
        return pivot.reindex(index=companies, columns=years)


    @st.cache_data(show_spinner=False)
    def build_segment_heatmap_data(segments_df, company, year_start, year_end, segment_filter):
        if segments_df is None or segments_df.empty or not company:
            return pd.DataFrame()
        df = segments_df[
            (segments_df["company"] == company)
            & (segments_df["year"] >= year_start)
            & (segments_df["year"] <= year_end)
        ].copy()
        if df.empty:
            return pd.DataFrame()
        df["segment"] = df["segment"].apply(lambda s: normalize_segment_label(company, s))
        df = df[
            df["segment"].notna()
            & (df["segment"] != "")
            & (df["segment"] != "Total Revenue")
        ]
        if segment_filter:
            df = df[df["segment"].isin(segment_filter)]
        if df.empty:
            return pd.DataFrame()
        df = df.groupby(["segment", "year"], as_index=False)["revenue"].sum()
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
        years = list(range(int(year_start), int(year_end) + 1))
        pivot = df.pivot(index="segment", columns="year", values="revenue")
        if segment_filter:
            pivot = pivot.reindex(index=list(segment_filter))
        else:
            pivot = pivot.reindex(index=sorted(pivot.index.tolist(), key=str.lower))
        return pivot.reindex(columns=years)


    @st.cache_data(show_spinner=False)
    def build_quarterly_segment_heatmap_data(segments_df, company, year_start, year_end, segment_filter):
        if segments_df is None or segments_df.empty or not company:
            return pd.DataFrame()
        df = segments_df[
            (segments_df["company"] == company)
            & (segments_df["year"] >= year_start)
            & (segments_df["year"] <= year_end)
        ].copy()
        df["segment"] = df["segment"].apply(lambda s: normalize_segment_label(company, s))
        if segment_filter:
            df = df[df["segment"].isin(segment_filter)]
        if df.empty:
            return pd.DataFrame()
        quarter_order = (
            df[["quarter", "year", "quarter_num"]]
            .dropna()
            .drop_duplicates()
            .sort_values(["year", "quarter_num"])
        )
        quarter_labels = quarter_order["quarter"].tolist()
        pivot = df.pivot_table(index="segment", columns="quarter", values="revenue", aggfunc="sum")
        if segment_filter:
            pivot = pivot.reindex(index=list(segment_filter))
        else:
            pivot = pivot.reindex(index=sorted(pivot.index.tolist(), key=str.lower))
        return pivot.reindex(columns=quarter_labels)


    @st.cache_data(show_spinner=False)
    def build_quarterly_metric_heatmap_data(quarterly_df, companies, metric_key, year_start, year_end, annual_df=None):
        if quarterly_df is None or quarterly_df.empty or not companies:
            return pd.DataFrame()
        df = quarterly_df[
            (quarterly_df["company"].isin(companies))
            & (quarterly_df["year"] >= year_start)
            & (quarterly_df["year"] <= year_end)
            & (quarterly_df["metric_key"] == metric_key)
        ].copy()
        if df.empty:
            return pd.DataFrame()
        df = df.groupby(["company", "year", "quarter_num", "period_label"], as_index=False)["value"].sum()
        # Guard against mixed scaling in the quarterly sheet (raw dollars vs millions).
        cleaned = (
            df["value"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.replace("(", "-", regex=False)
            .str.replace(")", "", regex=False)
        )
        values = pd.to_numeric(cleaned, errors="coerce")
        if values.notna().any():
            df["value"] = values
            scale_factor = None
            if annual_df is not None and not annual_df.empty and metric_key in annual_df.columns:
                annual = annual_df[
                    (annual_df["company"].isin(companies))
                    & (annual_df["year"] >= year_start)
                    & (annual_df["year"] <= year_end)
                ][["company", "year", metric_key]].copy()
                if not annual.empty:
                    annual = annual.groupby(["company", "year"], as_index=False)[metric_key].sum()
                    annual_vals = pd.to_numeric(annual[metric_key], errors="coerce")
                    annual["annual_value"] = annual_vals
                    quarterly_sum = df.groupby(["company", "year"], as_index=False)["value"].sum()
                    merged = quarterly_sum.merge(annual[["company", "year", "annual_value"]], on=["company", "year"], how="inner")
                    merged = merged[merged["annual_value"].notna() & merged["value"].notna()]
                    if not merged.empty:
                        ratios = merged["value"] / merged["annual_value"]
                        ratios = ratios.replace([np.inf, -np.inf], np.nan).dropna()
                        if not ratios.empty:
                            median_ratio = float(ratios.median())
                            if median_ratio >= 1000:
                                scale_factor = 1e6
            if scale_factor:
                df["value"] = df["value"] / scale_factor
            else:
                max_abs = float(values.abs().max())
                if max_abs >= 1e12:
                    df["value"] = df["value"] / 1e6
        df = df.sort_values(["year", "quarter_num"])
        period_order = df["period_label"].drop_duplicates().tolist()
        pivot = df.pivot(index="company", columns="period_label", values="value")
        return pivot.reindex(index=companies, columns=period_order)


    @st.cache_data(show_spinner=False)
    def build_stock_heatmap_data(
        stock_df,
        companies,
        frequency,
        year_start=None,
        year_end=None,
        period_limit=None,
    ):
        if stock_df is None or stock_df.empty or not companies:
            return pd.DataFrame()
        rows = {}
        period_labels = {}
        for company in companies:
            company_df = filter_stock_for_company(stock_df, company)
            if company_df.empty:
                continue
            series = company_df.sort_values("date").set_index("date")["price"]
            if frequency == "Yearly":
                agg = series.resample("Y").last()
                agg.index = agg.index.year
                if year_start is not None and year_end is not None:
                    agg = agg[(agg.index >= int(year_start)) & (agg.index <= int(year_end))]
                labels = agg.index.astype(int).tolist()
            elif frequency == "Quarterly":
                agg = series.resample("Q").last()
                if period_limit:
                    agg = agg.tail(int(period_limit))
                labels = []
                for dt in agg.index:
                    label = f"Q{((dt.month - 1) // 3) + 1} {dt.year}"
                    labels.append(label)
                    period_labels[label] = dt
            elif frequency == "Monthly":
                agg = series.resample("M").last()
                if period_limit:
                    agg = agg.tail(int(period_limit))
                labels = []
                for dt in agg.index:
                    label = dt.strftime("%Y-%m")
                    labels.append(label)
                    period_labels[label] = dt
            elif frequency == "Weekly":
                agg = series.resample("W").last()
                if period_limit:
                    agg = agg.tail(int(period_limit))
                labels = []
                for dt in agg.index:
                    label = dt.strftime("%Y-%m-%d")
                    labels.append(label)
                    period_labels[label] = dt
            else:
                agg = series
                if period_limit:
                    agg = agg.tail(int(period_limit))
                labels = []
                for dt in agg.index:
                    label = dt.strftime("%Y-%m-%d")
                    labels.append(label)
                    period_labels[label] = dt
            if agg.empty:
                continue
            rows[company] = pd.Series(agg.values, index=labels)

        if not rows:
            return pd.DataFrame()

        if frequency == "Yearly":
            columns = sorted({col for series in rows.values() for col in series.index}, key=int)
        else:
            columns = sorted(period_labels.keys(), key=lambda key: period_labels[key])
        pivot = pd.DataFrame(rows).T
        return pivot.reindex(index=companies, columns=columns)


    def filter_stock_for_company(stock_df, company):
        """Filter stock rows using ticker or company name."""
        if stock_df.empty:
            return stock_df
        keys = COMPANY_TICKERS.get(company, [])
        asset = stock_df["asset"].fillna("").str.upper()
        tag = stock_df["tag"].fillna("").str.upper()
        name_match = stock_df["asset"].fillna("").str.contains(company, case=False, regex=False)
        ticker_match = asset.isin(keys) | tag.isin(keys)
        return stock_df[name_match | ticker_match]


    def format_yoy_value(value):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.1f}%"


    def format_yoy_label(value, suffix="%"):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "—"
        try:
            value = float(value)
        except (TypeError, ValueError):
            return "—"
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.1f}{suffix}"


    def format_change_value(value):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "—"
        try:
            value = float(value)
        except (TypeError, ValueError):
            return "—"
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.1f}%"


    def get_yoy_class(value):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "kpi-yoy-neutral"
        try:
            value = float(value)
        except (TypeError, ValueError):
            return "kpi-yoy-neutral"
        if value > 0:
            return "kpi-yoy-positive"
        if value < 0:
            return "kpi-yoy-negative"
        return "kpi-yoy-neutral"


    def get_yoy_class_for_metric(metric_key, value):
        if metric_key == "debt":
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return "kpi-yoy-neutral"
            try:
                value = float(value)
            except (TypeError, ValueError):
                return "kpi-yoy-neutral"
            if value < 0:
                return "kpi-yoy-positive"
            if value > 0:
                return "kpi-yoy-negative"
            return "kpi-yoy-neutral"
        return get_yoy_class(value)


    def get_kpi_icon_html(metric_key, is_negative=False):
        icon_color = "#EF4444" if is_negative else "#0073ff"
        wrap_class = "kpi-icon-wrap is-negative" if is_negative else "kpi-icon-wrap"
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
        return f"<div class='{wrap_class}'>{svg}</div>"


    def split_insight_text(raw_text):
        if raw_text is None:
            return []
        text = str(raw_text).strip()
        if not text:
            return []
        if "•" in text:
            parts = [p.strip() for p in text.split("•")]
        else:
            parts = [p.strip() for p in text.split(";")]
        cleaned = []
        for part in parts:
            if not part:
                continue
            cleaned.append(part)
        return cleaned if cleaned else [text]


    def _resolve_company_years(data_processor, company_name):
        """Return robust year options for selector, prioritizing annual metrics coverage."""
        years = []
        try:
            years = data_processor.get_available_years(company_name) or []
        except Exception:
            years = []
        years = sorted({int(y) for y in years if pd.notna(y)})

        df_metrics = getattr(data_processor, "df_metrics", None)
        if df_metrics is not None and not df_metrics.empty:
            scoped = df_metrics[df_metrics["company"].astype(str).str.strip() == str(company_name).strip()].copy()
            if not scoped.empty and "year" in scoped.columns:
                metric_years = pd.to_numeric(scoped["year"], errors="coerce").dropna().astype(int).tolist()
                metric_years = sorted(set(metric_years))
                if metric_years:
                    return metric_years

        if years:
            return years

        excel_path = getattr(data_processor, "data_path", "")
        if excel_path and Path(excel_path).exists():
            try:
                raw = pd.read_excel(
                    excel_path,
                    sheet_name="Company_metrics_earnings_values",
                    usecols=["Company", "Year"],
                )
                raw.columns = [str(c).strip() for c in raw.columns]
                if {"Company", "Year"}.issubset(set(raw.columns)):
                    raw = raw[raw["Company"].astype(str).str.strip() == str(company_name).strip()]
                    fallback_years = pd.to_numeric(raw["Year"], errors="coerce").dropna().astype(int).tolist()
                    fallback_years = sorted(set(fallback_years))
                    if fallback_years:
                        return fallback_years
            except Exception:
                pass

        return []


    st.title("Earnings")
    data_processor = get_data_processor()
    workbook_ticker_map = build_company_ticker_map_from_market_data(
        excel_path=str(getattr(data_processor, "data_path", "") or ""),
        source_stamp=int(getattr(data_processor, "source_stamp", 0) or 0),
    )
    for company_name, ticker in workbook_ticker_map.items():
        if not ticker:
            continue
        current = COMPANY_TICKERS.setdefault(company_name, [])
        if ticker not in current:
            COMPANY_TICKERS[company_name] = [ticker] + current

    metrics_df_guard = getattr(data_processor, "df_metrics", None)
    if metrics_df_guard is None or metrics_df_guard.empty:
        # Cache may have captured a failed init — try a live reload before giving up.
        try:
            data_processor.load_data()
            metrics_df_guard = getattr(data_processor, "df_metrics", None)
        except Exception:
            pass
    if metrics_df_guard is None or metrics_df_guard.empty:
        from utils.workbook_source import resolve_financial_data_xlsx, DEFAULT_GOOGLE_SHEET_ID
        _resolved_path = resolve_financial_data_xlsx([])
        _path_info = f"Path: `{_resolved_path}`" if _resolved_path else "No file downloaded."
        _sheet_id = DEFAULT_GOOGLE_SHEET_ID
        st.warning(
            f"Financial data unavailable — could not load `Company_metrics_earnings_values` sheet.\n\n"
            f"**Sheet ID:** `{_sheet_id}`\n\n"
            f"**{_path_info}**\n\n"
            "Check that the Google Sheet is **shared publicly** (Anyone with link → Viewer). "
            "Then click Reload below."
        )
        if st.button("🔄 Reload data", key="reload_data_btn"):
            st.cache_resource.clear()
            st.rerun()
        st.stop()

    try:
        companies = data_processor.get_companies()
    except Exception:
        companies = []
    if not companies:
        st.error("No company data available.")
        st.stop()

    # Pre-filter from Genie thought map navigation
    if st.session_state.get("genie_nav_target") == "earnings":
        _nav_co = st.session_state.pop("genie_nav_company", "")
        _nav_yr = st.session_state.pop("genie_nav_year", None)
        _nav_q = st.session_state.pop("genie_nav_quarter", "")
        st.session_state.pop("genie_nav_target", None)
        if _nav_co:
            st.session_state["earnings_preselect_company"] = _nav_co
        if _nav_yr:
            st.session_state["earnings_preselect_year"] = int(_nav_yr)
        if _nav_q:
            st.session_state["earnings_preselect_quarter"] = _nav_q

    query_params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
    query_company = None
    if query_params:
        query_company = query_params.get("company")
        if isinstance(query_company, list):
            query_company = query_company[0] if query_company else None
    if not query_company:
        query_company = st.session_state.get("prefill_company")

    _preselect_co = st.session_state.pop("earnings_preselect_company", None)
    _default_co_idx = 0
    if _preselect_co and _preselect_co in companies:
        _default_co_idx = companies.index(_preselect_co)
    elif query_company:
        for idx, name in enumerate(companies):
            if name.lower() == str(query_company).lower():
                _default_co_idx = idx
                break

    year_col, quarter_col, company_col = st.columns([1, 1, 2])
    with company_col:
        company = st.selectbox("Select Company", companies, index=_default_co_idx)

    years = _resolve_company_years(data_processor, company)
    if not years:
        st.error("No years available for this company.")
        st.stop()
    years = sorted(years)

    _preselect_yr = st.session_state.pop("earnings_preselect_year", None)
    _default_yr_idx = len(years) - 1
    if _preselect_yr and int(_preselect_yr) in years:
        _default_yr_idx = years.index(int(_preselect_yr))

    with year_col:
        year = st.selectbox("Select Year", years, index=_default_yr_idx)

    quarterly_kpis_df = _load_quarterly_kpis(data_processor.data_path, get_file_mtime(data_processor.data_path))
    available_q = _get_available_quarters_for_earnings(year, company, quarterly_kpis_df)
    quarter_options = ["Annual"]  # Quarterly selector removed — all sections use annual data
    _preselect_q = st.session_state.pop("earnings_preselect_quarter", None)
    _default_q_idx = 0
    if _preselect_q and _preselect_q in quarter_options:
        _default_q_idx = quarter_options.index(_preselect_q)
    with quarter_col:
        selected_quarter = st.selectbox(
            "Quarter",
            quarter_options,
            index=_default_q_idx,
            key="earnings_selected_quarter",
        )

    st.session_state["earnings_selected_year"] = int(year)
    st.session_state["selected_year"] = int(year)
    st.session_state["selected_quarter"] = str(selected_quarter)
    render_ai_assistant(location="sidebar", current_page="Earnings")

    annual_metrics = data_processor.get_metrics(company, year) or {}
    quarterly_metrics, _ = _get_quarterly_metrics_snapshot(
        company_name=company,
        selected_year=year,
        selected_quarter=selected_quarter,
        quarterly_kpis_df=quarterly_kpis_df,
        annual_metrics=annual_metrics,
    )
    metrics = quarterly_metrics if quarterly_metrics is not None else annual_metrics
    if not metrics:
        st.error("No data available for the selected company/year.")
        st.stop()

    prev_company = st.session_state.get("kpi_anim_company")
    prev_year = st.session_state.get("kpi_anim_year")
    prev_quarter = st.session_state.get("kpi_anim_quarter")
    if (
        prev_company != company
        or prev_year != year
        or prev_quarter != selected_quarter
        or "kpi_anim_key" not in st.session_state
    ):
        st.session_state["kpi_anim_key"] = uuid.uuid4().hex[:8]
        st.session_state["kpi_anim_company"] = company
        st.session_state["kpi_anim_year"] = year
        st.session_state["kpi_anim_quarter"] = selected_quarter
    kpi_anim_key = st.session_state["kpi_anim_key"]
    kpi_anim_start_delay = 1.0
    kpi_anim_step = 0.2

    logo_path = COMPANY_LOGOS.get(company, COMPANY_LOGOS.get(normalize_company(company)))
    logo_base64 = get_logo_base64(logo_path, get_file_mtime(logo_path))
    logo_html = ""
    if logo_base64:
        logo_html = f"<img src='data:image/png;base64,{logo_base64}' class='company-logo' alt='{company} logo'>"

    stock_df = load_stock_data(
        data_processor.data_path,
        int(getattr(data_processor, "source_stamp", 0) or 0),
    )
    stock_company_df = filter_stock_for_company(stock_df, company)
    ticker_options = COMPANY_TICKERS.get(company, [])
    ticker_display = ticker_options[0] if ticker_options else ""
    stock_price_display = "—"
    stock_change_display = "Last 3 Months —"
    stock_change_class = "hero-stock-change-neutral"
    sparkline_svg = ""
    if stock_company_df is not None and not stock_company_df.empty:
        series_df = stock_company_df.dropna(subset=["date", "price"]).sort_values("date")
        if not series_df.empty:
            latest_row = series_df.iloc[-1]
            latest_price = latest_row.get("price")
            latest_date = latest_row.get("date")
            # Prefer hardcoded COMPANY_TICKERS — live data tags can be stale/wrong
            if not ticker_display:
                live_ticker = str(latest_row.get("tag", "")).strip().upper()
                if live_ticker and live_ticker not in {"NAN", "NONE", "NULL", ""}:
                    ticker_display = live_ticker
                else:
                    for candidate in (latest_row.get("asset"),):
                        if isinstance(candidate, str) and candidate.strip():
                            ticker_display = candidate.strip().upper()
                            break
            if latest_price is not None and not pd.isna(latest_price):
                stock_price_display = format_stock_value(latest_price)
            if latest_date is not None and not pd.isna(latest_date):
                cutoff = latest_date - pd.DateOffset(months=3)
                prior_df = series_df[series_df["date"] <= cutoff]
                if not prior_df.empty:
                    prior_price = prior_df.iloc[-1].get("price")
                    if prior_price is not None and not pd.isna(prior_price) and float(prior_price) != 0:
                        change_pct = (float(latest_price) - float(prior_price)) / float(prior_price) * 100
                        stock_change_display = f"Last 3 Months {change_pct:+.1f}%"
                        if change_pct > 0:
                            stock_change_class = "hero-stock-change-positive"
                        elif change_pct < 0:
                            stock_change_class = "hero-stock-change-negative"
            if latest_date is not None and not pd.isna(latest_date):
                spark_df = series_df[series_df["date"] >= (latest_date - pd.DateOffset(months=3))]
                if spark_df.empty:
                    spark_df = series_df.tail(60)
                if len(spark_df) > 60:
                    sample_idx = np.linspace(0, len(spark_df) - 1, 60).round().astype(int)
                    spark_df = spark_df.iloc[sample_idx]
                spark_values = spark_df["price"].astype(float).tolist()
                if len(spark_values) >= 2:
                    min_val = min(spark_values)
                    max_val = max(spark_values)
                    span = max(max_val - min_val, 1e-9)
                    width = 180
                    height = 44
                    points = []
                    for idx, value in enumerate(spark_values):
                        x = 1 + (idx / (len(spark_values) - 1)) * (width - 2)
                        y = 1 + (1 - (value - min_val) / span) * (height - 2)
                        points.append(f"{x:.1f},{y:.1f}")
                    if stock_change_class == "hero-stock-change-positive":
                        line_color = "#16A34A"
                    elif stock_change_class == "hero-stock-change-negative":
                        line_color = "#EF4444"
                    else:
                        line_color = "#E2E8F0"
                    sparkline_svg = (
                        f"<svg class='hero-stock-sparkline' viewBox='0 0 {width} {height}' "
                        "preserveAspectRatio='none'>"
                        f"<polyline fill='none' stroke='{line_color}' stroke-width='2' "
                        "stroke-linecap='round' stroke-linejoin='round' "
                        f"points='{ ' '.join(points) }'/>"
                        "</svg>"
                    )

    if not ticker_display:
        ticker_display = "—"

    company_header_html = f"""
    <div class="company-header">
        <div class="company-header-left">
            {logo_html}
            <div class="company-header-text">
                <span class="company-name">{company}</span>
                <span class="company-year">{year if selected_quarter == "Annual" else f"{year} · {selected_quarter}"}</span>
            </div>
        </div>
    </div>
    """

    hero_stock_html = f"""
    <div class="earnings-hero-stock">
        <div class="hero-stock-ticker">{ticker_display}</div>
        <div class="hero-stock-price">{stock_price_display}</div>
        <div class="hero-stock-change {stock_change_class}">{stock_change_display}</div>
        {sparkline_svg}
    </div>
    """

    snapshot_items = [
        ("Revenue", "revenue"),
        ("Net Income", "net_income"),
        ("Operating Income", "operating_income"),
        ("Cost of Revenue", "cost_of_revenue"),
        ("R&D", "rd"),
        ("CapEx", "capex"),
        ("Total Assets", "total_assets"),
        ("Debt", "debt"),
        ("Cash Balance", "cash_balance"),
        ("Market Cap", "market_cap"),
    ]

    metrics_df = data_processor.df_metrics
    base_kpi_color = COMPANY_COLORS.get(company, BRAND_BLUE)
    kpi_bar_color = blend_with_target(base_kpi_color, "#FFFFFF", 0.45)

    kpi_cards = []
    for idx, (label, metric_key) in enumerate(snapshot_items):
        raw_value = metrics.get(metric_key)
        value = format_metric_value(raw_value)
        yoy_value = metrics.get(f"{metric_key}_yoy")
        yoy_text = format_yoy_value(yoy_value)
        yoy_class = get_yoy_class_for_metric(metric_key, yoy_value)
        yoy_display = f"{yoy_text} YoY" if yoy_text else "YoY: —"
        history = get_metric_history(metrics_df, company, metric_key, years, window=5)
        history_html = build_kpi_history_bars(history, kpi_bar_color)
        card_style = ""
        is_negative = False
        try:
            is_negative = yoy_value is not None and float(yoy_value) < 0
        except (TypeError, ValueError):
            is_negative = False
        if metric_key == "debt":
            is_negative = False
        icon_html = get_kpi_icon_html(metric_key, is_negative=is_negative)
        kpi_cards.append(
            (
                f"<div class='kpi-card kpi-tilt' style='{card_style}'>"
                f"{icon_html}"
                f"<div class='kpi-label'>{label}</div>"
                f"<div class='kpi-value'>{value}</div>"
                f"<div class='kpi-yoy {yoy_class}'>{yoy_display}</div>"
                f"{history_html}"
                "</div>"
            )
        )
    kpi_cards_html = "".join(kpi_cards)
    hero_key = normalize_company(company)
    hero_path = COMPANY_HERO_IMAGES.get(company) or COMPANY_HERO_IMAGES.get(hero_key)
    hero_base64, hero_mime = get_hero_base64(hero_path, get_file_mtime(hero_path))
    hero_style = "--hero-image: none;"
    if hero_base64:
        hero_style = f"--hero-image: url('data:{hero_mime};base64,{hero_base64}')"
    hero_classes = "earnings-hero"
    if hero_stock_html:
        hero_classes += " has-stock"
    st.markdown(company_header_html, unsafe_allow_html=True)
    # NOTE: hero image is rendered via CSS background-image (--hero-image var)
    # rather than an <img> tag — this keeps the HTML well under Streamlit's
    # rehype-raw size limit and prevents raw-HTML rendering bugs.
    st.markdown(
        (
            f"<div class='{hero_classes}' id='earnings-hero-{kpi_anim_key}' "
            f"style=\"{hero_style}\">"
            f"{hero_stock_html}"
            "<div class='earnings-hero-overlay'>"
            f"<div class='earnings-hero-panel' id='kpi-panel-{kpi_anim_key}'>"
            f"<div class='kpi-grid'>{kpi_cards_html}</div>"
            "</div>"
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    components.html(
        f"""
        <script>
    	    (function() {{
    	        const doc = window.parent.document;
    	        function tryInit(attempt) {{
    	            const hero = doc.getElementById("earnings-hero-{kpi_anim_key}");
    	            const panel = doc.getElementById("kpi-panel-{kpi_anim_key}");
    	            if (!hero || !panel) {{
    	                if (attempt < 10) window.parent.setTimeout(() => tryInit(attempt + 1), 200);
    	                return;
    	            }}
    	            runAnimation(hero, panel);
    	        }}
    	        tryInit(0);
    	        function runAnimation(hero, panel) {{

            hero.classList.remove("is-collapsed");
            const cards = panel.querySelectorAll(".kpi-card");
            cards.forEach((card) => card.classList.remove("kpi-show"));
            const img = hero.querySelector("img");
    	        const delayMs = {int(kpi_anim_start_delay * 1000)};
    	        const stepMs = {int(kpi_anim_step * 1000)};
    	        const minH = 420;
    	        const ratio = 0.45;
    	        const toPx = (value) => {{
    	            const parsed = parseFloat(value || "0");
    	            return Number.isFinite(parsed) ? parsed : 0;
    	        }};

            if (window.parent.__kpiAnimTimers) {{
                window.parent.__kpiAnimTimers.forEach((t) => window.parent.clearTimeout(t));
            }}
            window.parent.__kpiAnimTimers = [];

    	        const getRequiredFinalHeight = function() {{
    	            const overlay = hero.querySelector(".earnings-hero-overlay");
    	            const stock = hero.querySelector(".earnings-hero-stock");
    	            const panelHeight = panel.scrollHeight || panel.getBoundingClientRect().height || 0;
    	            let overlayPadding = 0;
    	            let extraStock = 0;

    	            if (overlay) {{
    	                const overlayStyle = window.getComputedStyle(overlay);
    	                overlayPadding = toPx(overlayStyle.paddingTop) + toPx(overlayStyle.paddingBottom);
    	                if (stock && hero.classList.contains("has-stock")) {{
    	                    const stockHeight = stock.getBoundingClientRect().height || stock.scrollHeight || 0;
    	                    const safeBottom = toPx(overlayStyle.paddingBottom);
    	                    extraStock = Math.max(0, stockHeight + 18 - safeBottom);
    	                }}
    	            }}

    	            return Math.ceil(panelHeight + overlayPadding + extraStock + 12);
    	        }};

    	        const computeHeights = function() {{
    	            const width = hero.getBoundingClientRect().width || hero.clientWidth || 1;
    	            const viewportFinalCap = Math.min(1400, Math.max(760, window.innerHeight * 1.4));
    	            const baseFinalHeight = Math.max(minH, width * ratio);
    	            const contentFinalHeight = getRequiredFinalHeight();
    	            const finalHeight = Math.min(viewportFinalCap, Math.max(baseFinalHeight, contentFinalHeight));
    	            let introHeight = finalHeight;

    	            const imgHeight =
    	                (img && img.naturalWidth && img.naturalHeight)
    	                    ? (img.naturalHeight / img.naturalWidth) * width
    	                    : null;

    	            if (imgHeight && Number.isFinite(imgHeight)) {{
    	                introHeight = Math.max(finalHeight, imgHeight);
    	            }} else {{
    	                introHeight = Math.max(finalHeight, hero.scrollHeight || hero.clientHeight || finalHeight);
    	            }}

    	            // Let intro be larger than collapsed height, but keep it bounded.
    	            const introCap = Math.min(1550, Math.max(finalHeight, window.innerHeight * 1.55));
    	            introHeight = Math.max(finalHeight, Math.min(introHeight, introCap));
    	            return {{ finalHeight, introHeight }};
    	        }};

    	        const applyHeights = function() {{
    	            const {{ finalHeight, introHeight }} = computeHeights();
    	            hero.style.setProperty("--hero-final-height", finalHeight.toFixed(1) + "px");
    	            hero.style.height = (hero.classList.contains("is-collapsed") ? finalHeight : introHeight).toFixed(1) + "px";
    	        }};

    	        const start = function() {{
    	            applyHeights();

    	            window.parent.__kpiAnimTimers.push(
    	                window.parent.setTimeout(function() {{
    	                    hero.classList.add("is-collapsed");
    	                    applyHeights();
    	                }}, delayMs)
    	            );
    	            cards.forEach((card, idx) => {{
    	                window.parent.__kpiAnimTimers.push(
    	                    window.parent.setTimeout(function() {{
    	                        card.classList.add("kpi-show");
    	                    }}, delayMs + (idx * stepMs))
    	                );
    	            }});
    	            // Enable blur backdrop after KPIs finish animating
    	            window.parent.__kpiAnimTimers.push(
    	                window.parent.setTimeout(function() {{
    	                    hero.classList.add("is-loaded");
    	                }}, delayMs + (cards.length * stepMs) + 200)
    	            );
    	        }};

    	        if (img && !img.complete) {{
    	            img.addEventListener("load", start, {{ once: true }});
    	        }} else {{
    	            start();
    	        }}

    	        // Keep hero sizing stable when the viewport changes (external monitor vs laptop, zoom, etc.).
    	        if (!hero.__kpiResizeBound) {{
    	            hero.__kpiResizeBound = true;
    	            window.addEventListener("resize", () => {{
    	                window.requestAnimationFrame(applyHeights);
    	            }});
    	        }}

            const tiltCards = panel.querySelectorAll(".kpi-tilt");
            tiltCards.forEach((card) => {{
                card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg)";
                card.addEventListener("mousemove", (e) => {{
                    const r = card.getBoundingClientRect();
                    const x = (e.clientX - r.left) / r.width - 0.5;
                    const y = (e.clientY - r.top) / r.height - 0.5;
                    card.style.transform = `perspective(1000px) rotateX(${{-y * 6}}deg) rotateY(${{x * 6}}deg) scale(1.05)`;
                }});
                card.addEventListener("mouseleave", () => {{
                    card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg)";
                }});
            }});
        }}
        }})();
        </script>
        """,
        height=0,
    )

    st.markdown("<hr class='thin-section-divider' />", unsafe_allow_html=True)

    # ── Institutional Ownership ───────────────────────────────────────────
    canonical_company = normalize_company(company)
    st.subheader("Institutional Ownership")

    _h_tickers = COMPANY_TICKERS.get(company, COMPANY_TICKERS.get(canonical_company, []))
    _h_ticker = _h_tickers[0] if _h_tickers else ""
    _holders_df = pd.DataFrame()
    if _h_ticker:
        _holders_df = data_processor.get_holders(ticker=_h_ticker)
    if _holders_df.empty:
        _all_h = data_processor.get_holders()
        if not _all_h.empty and _h_ticker:
            _holders_df = _all_h[
                _all_h["company"].str.upper() == _h_ticker.upper()
            ].copy()

    if _holders_df.empty:
        st.info("Ownership data is not available for this company.")
    else:
        def _clean_hname(name: str) -> str:
            """Shorten 'FUND FAMILY-Specific Fund Name' → 'Specific Fund Name'."""
            if "-" in name:
                parts = name.split("-", 1)
                tail = parts[1].strip()
                if len(tail) >= 6:
                    return tail
            return name.strip()

        _holders_df = _holders_df.copy()
        _holders_df["name_short"] = _holders_df["holder_name"].apply(_clean_hname)
        _holders_df["pct_display"] = (_holders_df["pct_out"] * 100).round(2)
        _holders_df["value_b"] = (_holders_df["value_usd"].fillna(0) / 1e9).round(1)
        _holders_df["shares_m"] = (_holders_df["shares"].fillna(0) / 1e6).round(1)
        _holders_df = _holders_df.sort_values("pct_out", ascending=False).reset_index(drop=True)

        _top_h = _holders_df.iloc[0]
        _BIG3 = ["vanguard", "blackrock", "state street"]
        _big3_pct = (
            _holders_df[
                _holders_df["name_short"].str.lower().apply(
                    lambda n: any(b in n for b in _BIG3)
                )
            ]["pct_out"].sum()
            * 100
        )
        _n_inst = int((_holders_df["holder_type"] == "institutional").sum())
        _n_fund = int((_holders_df["holder_type"] == "fund").sum())
        _h_date = ""
        try:
            _dt = pd.to_datetime(_holders_df["date_fetched"]).max()
            _h_date = _dt.strftime("%b %Y") if pd.notna(_dt) else ""
        except Exception:
            pass

        # KPI strip
        _hkpi = st.columns(3)
        _kpi_style = (
            "background:#f8fafc;border:1px solid #e2e8f0;"
            "border-radius:12px;padding:1rem 1.1rem;box-shadow:0 1px 3px rgba(0,0,0,0.06);"
        )
        with _hkpi[0]:
            st.markdown(
                f"<div style='{_kpi_style}'>"
                f"<div style='font-size:0.7rem;color:#6b7280;text-transform:uppercase;"
                f"letter-spacing:0.08em;margin-bottom:0.25rem;'>Top Holder</div>"
                f"<div style='font-size:0.95rem;font-weight:700;color:#111827;"
                f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>"
                f"{html.escape(_top_h['name_short'][:30])}</div>"
                f"<div style='font-size:1.6rem;font-weight:800;color:#2563eb;line-height:1.1;'>"
                f"{_top_h['pct_display']:.2f}%</div>"
                f"<div style='font-size:0.78rem;color:#6b7280;margin-top:0.15rem;'>"
                f"${_top_h['value_b']:.1f}B position</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with _hkpi[1]:
            st.markdown(
                f"<div style='{_kpi_style}'>"
                f"<div style='font-size:0.7rem;color:#6b7280;text-transform:uppercase;"
                f"letter-spacing:0.08em;margin-bottom:0.25rem;'>Big Three</div>"
                f"<div style='font-size:0.8rem;color:#6b7280;'>Vanguard · BlackRock · State Street</div>"
                f"<div style='font-size:1.6rem;font-weight:800;color:#2563eb;line-height:1.1;'>"
                f"{_big3_pct:.1f}%</div>"
                f"<div style='font-size:0.78rem;color:#6b7280;margin-top:0.15rem;'>"
                f"Passive mega-managers combined</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with _hkpi[2]:
            st.markdown(
                f"<div style='{_kpi_style}'>"
                f"<div style='font-size:0.7rem;color:#6b7280;text-transform:uppercase;"
                f"letter-spacing:0.08em;margin-bottom:0.25rem;'>Holders tracked</div>"
                f"<div style='font-size:1.6rem;font-weight:800;color:#111827;line-height:1.1;'>"
                f"{len(_holders_df)}</div>"
                f"<div style='font-size:0.78rem;color:#6b7280;margin-top:0.15rem;'>"
                f"{_n_inst} institutional · {_n_fund} funds"
                f"{(' · snapshot ' + _h_date) if _h_date else ''}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)

        _INST_PALETTE = [
            "#1a73e8", "#00c9a7", "#f59e0b", "#ef4444", "#8b5cf6",
            "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16",
        ]

        def _render_ownership_tab(df_tab: pd.DataFrame, tab_label: str) -> None:
            """Render donut + compact table for one holder type."""
            if df_tab.empty:
                st.info(f"No {tab_label.lower()} holders found.")
                return

            _top8 = df_tab.head(8).copy()
            _top8_labels = _top8["name_short"].tolist()
            _top8_vals = _top8["pct_display"].tolist()
            _top8_colors = _INST_PALETTE[: len(_top8)]

            _donut_fig = go.Figure(go.Pie(
                labels=_top8_labels,
                values=_top8_vals,
                hole=0.50,
                sort=False,
                marker=dict(colors=_top8_colors, line=dict(color="rgba(0,0,0,0.15)", width=1)),
                textinfo="none",
                hovertemplate="<b>%{label}</b><br>%{value:.2f}%<extra></extra>",
                customdata=_top8[["value_b", "shares_m"]].values,
            ))
            _donut_fig.update_layout(
                height=340,
                margin=dict(l=0, r=0, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#111827"),
                showlegend=True,
                legend=dict(
                    orientation="v", x=1.01, y=0.5, yanchor="middle",
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#111827", size=10),
                ),
                hoverlabel=HOVERLABEL_STYLE,
            )
            # Compact styled HTML table
            _tbl_rows = ""
            for _ri, (_idx, _row) in enumerate(df_tab.iterrows()):
                _bg = "#f8fafc" if _ri % 2 == 0 else "#f1f5f9"
                _tbl_rows += (
                    f"<tr style='background:{_bg};'>"
                    f"<td style='padding:6px 8px;color:#6b7280;font-size:11px;width:30px;'>{_ri+1}</td>"
                    f"<td style='padding:6px 8px;color:#111827;font-size:12px;font-weight:600;'>{html.escape(_row['name_short'][:36])}</td>"
                    f"<td style='padding:6px 8px;color:#374151;font-size:11px;text-align:right;'>{_row['shares_m']:.1f}</td>"
                    f"<td style='padding:6px 8px;color:#374151;font-size:11px;text-align:right;'>${_row['value_b']:.1f}B</td>"
                    f"<td style='padding:6px 8px;color:#2563eb;font-size:11px;text-align:right;font-weight:700;'>{_row['pct_display']:.2f}%</td>"
                    f"</tr>"
                )
            _tbl_html = (
                "<div style='overflow-x:auto;'>"
                "<table style='width:100%;border-collapse:collapse;font-family:Montserrat,sans-serif;'>"
                "<thead><tr style='background:#e2e8f0;'>"
                "<th style='padding:6px 8px;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.06em;text-align:left;width:30px;'>#</th>"
                "<th style='padding:6px 8px;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.06em;text-align:left;'>Holder</th>"
                "<th style='padding:6px 8px;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.06em;text-align:right;'>Shares (M)</th>"
                "<th style='padding:6px 8px;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.06em;text-align:right;'>Value</th>"
                "<th style='padding:6px 8px;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.06em;text-align:right;'>% Stake</th>"
                "</tr></thead>"
                f"<tbody>{_tbl_rows}</tbody>"
                "</table></div>"
            )

            _dcol, _tcol = st.columns([1, 1.4])
            with _dcol:
                st.plotly_chart(_donut_fig, use_container_width=True, config=PLOTLY_CONFIG)
            with _tcol:
                st.markdown(_tbl_html, unsafe_allow_html=True)

        # Tabs: Institutional | Funds
        _tab_inst, _tab_fund = st.tabs(["📋 Institutional", "📊 Funds"])
        with _tab_inst:
            _render_ownership_tab(
                _holders_df[_holders_df["holder_type"] == "institutional"].reset_index(drop=True),
                "Institutional",
            )
        with _tab_fund:
            _render_ownership_tab(
                _holders_df[_holders_df["holder_type"] == "fund"].reset_index(drop=True),
                "Fund",
            )

    st.divider()


    st.divider()

    # Default to the last 5 years where possible, but keep explorer floor at 2010.
    metrics_floor_year = 2010
    max_year = int(max(years))
    min_year = int(min(years))
    metrics_ceiling_year = max(int(max_year), int(max(years)))
    if metrics_ceiling_year < metrics_floor_year:
        metrics_floor_year = metrics_ceiling_year
    default_start = max(int(metrics_floor_year), int(metrics_ceiling_year) - 4)

    # Company metrics explorer
    st.markdown("<div class='metrics-section-spacer'></div>", unsafe_allow_html=True)
    st.subheader("Company Metrics Explorer")

    metric_cols = st.columns([3, 1, 1])
    with metric_cols[0]:
        selected_metrics = st.multiselect(
            "Select metrics",
            options=list(AVAILABLE_METRICS.keys()),
            default=["Revenue"],
        )
    with metric_cols[1]:
        metric_chart = st.radio("Chart", ["Bar", "Line"], horizontal=True)
    with metric_cols[2]:
        compare_companies = st.multiselect(
            "Compare with",
            options=[c for c in companies if c != company],
            default=[],
        )

    metric_year_range = st.slider(
        "Metrics year range",
        min_value=int(metrics_floor_year),
        max_value=int(metrics_ceiling_year),
        value=(int(default_start), int(metrics_ceiling_year)),
        key="metrics_year_range",
    )

    metric_toggle_row = st.columns([0.45, 0.30, 0.25])
    with metric_toggle_row[0]:
        metrics_freq = st.radio(
            "Frequency",
            ["Yearly", "Quarterly"],
            horizontal=True,
            key="metrics_frequency",
        )
    with metric_toggle_row[1]:
        show_metric_yoy = st.checkbox("Show YoY %", value=True, key="metrics_show_yoy")

    metrics_df = data_processor.df_metrics
    metrics_quarter_col = None
    metrics_ready = True
    quarterly_metrics_df = None
    if metrics_freq == "Quarterly":
        quarterly_metrics_df = load_quarterly_company_metrics(
            data_processor.data_path, get_file_mtime(data_processor.data_path)
        )
        metrics_ready = quarterly_metrics_df is not None and not quarterly_metrics_df.empty

    has_metrics_source = (
        (metrics_df is not None and not metrics_df.empty) or (quarterly_metrics_df is not None)
    )
    if selected_metrics and has_metrics_source:
        selected_companies = [company] + compare_companies
        df_filtered = pd.DataFrame()
        if metrics_df is not None and not metrics_df.empty:
            df_filtered = metrics_df[
                (metrics_df["company"].isin(selected_companies))
                & (metrics_df["year"] >= metric_year_range[0])
                & (metrics_df["year"] <= metric_year_range[1])
            ]

        if metrics_freq == "Quarterly" and not metrics_ready:
            st.info("Quarterly company metrics are not available in the Excel yet.")
        else:
            for metric_label in selected_metrics:
                metric_col = AVAILABLE_METRICS[metric_label]
                if metrics_freq == "Quarterly":
                    if quarterly_metrics_df is None or quarterly_metrics_df.empty:
                        st.info("Quarterly company metrics are not available in the Excel yet.")
                        break
                    df_metric = quarterly_metrics_df[
                        (quarterly_metrics_df["company"].isin(selected_companies))
                        & (quarterly_metrics_df["year"] >= metric_year_range[0])
                        & (quarterly_metrics_df["year"] <= metric_year_range[1])
                        & (quarterly_metrics_df["metric_key"] == metric_col)
                    ].copy()
                    if df_metric.empty:
                        st.info(f"No quarterly data available for {metric_label}.")
                        continue
                    df_metric = (
                        df_metric.groupby(["company", "year", "quarter_num", "period_label"], as_index=False)[
                            "value"
                        ].sum()
                    )
                else:
                    df_metric = df_filtered[["company", "year", metric_col]].dropna().rename(
                        columns={metric_col: "value"}
                    )
                    if df_metric.empty:
                        st.info(f"No data available for {metric_label}.")
                        continue
                df_metric["year"] = pd.to_numeric(df_metric["year"], errors="coerce")
                df_metric = df_metric.dropna(subset=["year"])
                df_metric["year"] = df_metric["year"].astype(int)
                if metrics_freq == "Quarterly":
                    df_metric["quarter_num"] = pd.to_numeric(df_metric["quarter_num"], errors="coerce")
                    df_metric = df_metric.dropna(subset=["year", "quarter_num"])
                    df_metric["year"] = df_metric["year"].astype(int)
                    df_metric["quarter_num"] = df_metric["quarter_num"].astype(int)
                    df_metric = df_metric.sort_values(["company", "year", "quarter_num"])
                    df_metric["period_label"] = (
                        df_metric["year"].astype(int).astype(str)
                        + " Q"
                        + df_metric["quarter_num"].astype(int).astype(str)
                    )
                    df_metric["yoy"] = df_metric.groupby("company")["value"].pct_change() * 100
                    df_metric["yoy_label"] = df_metric["yoy"].apply(lambda v: format_yoy_label(v, "%"))
                    x_col = "period_label"
                    change_label = "QoQ"
                else:
                    df_metric = df_metric.sort_values(["company", "year"])
                    df_metric["yoy"] = df_metric.groupby("company")["value"].pct_change() * 100
                    df_metric["yoy_label"] = df_metric["yoy"].apply(lambda v: format_yoy_label(v, "%"))
                    x_col = "year"
                    change_label = "YoY"
                custom_data = ["yoy_label"] if show_metric_yoy else None
                if metric_chart == "Bar":
                    fig = px.bar(
                        df_metric,
                        x=x_col,
                        y="value",
                        color="company",
                        barmode="group",
                        title=f"{metric_label} Over Time",
                        color_discrete_map=COMPANY_COLORS,
                        custom_data=custom_data,
                    )
                else:
                    fig = px.line(
                        df_metric,
                        x=x_col,
                        y="value",
                        color="company",
                        markers=True,
                        title=f"{metric_label} Over Time",
                        color_discrete_map=COMPANY_COLORS,
                        custom_data=custom_data,
                    )
                fig.update_layout(
                    yaxis_title=f"{metric_label} (M)",
                    xaxis_title="Quarterly" if metrics_freq == "Quarterly" else "Year",
                    height=520,
                    margin=dict(t=60, r=30, l=20, b=40),
                )
                _period_word = "Quarter" if metrics_freq == "Quarterly" else "Year"
                if show_metric_yoy:
                    hovertemplate = (
                        f"<b>%{{fullData.name}}</b>"
                        f"<br><span style='color:#94a3b8'>{_period_word}</span>  <b>%{{x}}</b>"
                        f"<br><span style='color:#94a3b8'>{metric_label}</span>  <b>$%{{y:,.0f}}M</b>"
                        f"<br><span style='color:#94a3b8'>{change_label}</span>  <b>%{{customdata[0]}}</b>"
                        f"<extra></extra>"
                    )
                else:
                    hovertemplate = (
                        f"<b>%{{fullData.name}}</b>"
                        f"<br><span style='color:#94a3b8'>{_period_word}</span>  <b>%{{x}}</b>"
                        f"<br><span style='color:#94a3b8'>{metric_label}</span>  <b>$%{{y:,.0f}}M</b>"
                        f"<extra></extra>"
                    )
                fig.update_traces(
                    hovertemplate=hovertemplate
                )
                fig.update_layout(hoverlabel=HOVERLABEL_STYLE)
                if metrics_freq == "Quarterly":
                    period_order = (
                        df_metric[["year", "quarter_num"]]
                        .drop_duplicates()
                        .sort_values(["year", "quarter_num"])
                    )
                    quarter_labels = (
                        period_order["year"].astype(int).astype(str)
                        + " Q"
                        + period_order["quarter_num"].astype(int).astype(str)
                    ).tolist()
                    category_order, tickvals, ticktext = build_quarter_axis(quarter_labels)
                    fig.update_xaxes(
                        type="category",
                        categoryorder="array",
                        categoryarray=category_order,
                        tickmode="array",
                        tickvals=tickvals,
                        ticktext=ticktext,
                    )
                    render_plotly(fig, xaxis_is_year=False)
                else:
                    render_plotly(fig, xaxis_is_year=True)


    # ── Insights — independent year/quarter filter ─────────────────────────
    st.markdown(
        "<div style='margin:2rem 0 0.6rem 0;'>"
        "<span style='font-weight:800;font-size:1.15rem;color:#111827;'>Insights</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    _ins_col_yr, _ins_col_qtr, _ins_col_pad = st.columns([1, 1, 4])
    _ins_years_opts = sorted([int(y) for y in years], reverse=True)
    with _ins_col_yr:
        _ins_year = st.selectbox("Year", _ins_years_opts, index=0,
                                  key=f"ins_yr_{company}")
    with _ins_col_qtr:
        _ins_qtr = st.selectbox("Quarter", ["Annual", "Q1", "Q2", "Q3", "Q4"],
                                 index=0, key=f"ins_qtr_{company}")
    _ins_q_str = "" if _ins_qtr == "Annual" else _ins_qtr
    _period = f"Q{_ins_qtr.lstrip('Q')} {_ins_year}" if _ins_q_str else str(_ins_year)

    render_transcript_highlights(company, int(_ins_year), _ins_qtr)

    # Extract signals
    try:
        from utils.transcript_live import (
            extract_outlook_risks_opportunities,
            SIGNAL_ICONS,
            SIGNAL_COLORS,
        )
        _oro = extract_outlook_risks_opportunities(
            str(data_processor.data_path),
            canonical_company,
            int(_ins_year),
            _ins_q_str,
        )
        _has_oro = any(bool(v) for v in _oro.values())
    except Exception:
        _oro = {}
        _has_oro = False
        SIGNAL_COLORS = {
            "Outlook":             {"bg": "#f8faff", "border": "#3b82f6", "tag": "#1d4ed8"},
            "Risks":               {"bg": "#fffaf7", "border": "#f97316", "tag": "#c2410c"},
            "Opportunities":       {"bg": "#f6fdf7", "border": "#22c55e", "tag": "#15803d"},
            "Investment":          {"bg": "#fefce8", "border": "#eab308", "tag": "#a16207"},
            "Product Shifts":      {"bg": "#fdf4ff", "border": "#a855f7", "tag": "#7e22ce"},
            "User Behavior":       {"bg": "#f0f9ff", "border": "#0ea5e9", "tag": "#0369a1"},
            "Monetization":        {"bg": "#fef9f0", "border": "#f59e0b", "tag": "#b45309"},
            "Strategic Direction": {"bg": "#f1f5f9", "border": "#64748b", "tag": "#334155"},
            "Broadcaster Threats": {"bg": "#fff1f2", "border": "#f43f5e", "tag": "#be123c"},
        }

    def _render_signal_col(cat_name, oro_dict, sig_colors, co, yr, qtr=""):
        _sigs = sorted(oro_dict.get(cat_name, []), key=lambda x: -x.get("score", 0))
        _c = sig_colors.get(cat_name, {"bg": "#f9fafb", "border": "#e5e7eb", "tag": "#374151"})
        # Category header
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;"
            f"margin-bottom:10px;padding-bottom:8px;"
            f"border-bottom:2px solid {_c['border']};'>"
            f"<span style='font-weight:700;font-size:0.88rem;color:#111827;'>{cat_name}</span>"
            f"<span style='margin-left:auto;background:{_c['tag']};color:#fff;"
            f"font-size:0.62rem;padding:1px 7px;border-radius:10px;"
            f"font-weight:700;'>{len(_sigs)}</span></div>",
            unsafe_allow_html=True,
        )
        if not _sigs:
            st.markdown(
                "<p style='color:#9ca3af;font-size:0.8rem;'>No signals found.</p>",
                unsafe_allow_html=True,
            )
            return
        _sn_key = f"sn_{co}_{yr}_{qtr}_{cat_name}"
        if _sn_key not in st.session_state:
            st.session_state[_sn_key] = 3
        _show_n = st.session_state[_sn_key]
        for _sig in _sigs[:_show_n]:
            _q = str(_sig.get("quote", "")).strip()
            _sp = str(_sig.get("speaker", "")).strip()
            _rl = str(_sig.get("role", "")).strip()
            _sq = str(_sig.get("quarter", "")).strip()
            _sc = float(_sig.get("score", 0))
            _filled = max(1, int(min(_sc / 15.0, 1.0) * 5))
            _dot_color = _c["tag"]
            _dots = (
                f"<span style='color:{_dot_color};'>{'●' * _filled}</span>"
                f"<span style='color:#d1d5db;'>{'●' * (5 - _filled)}</span>"
            )
            # Quarter badge
            _qtr_badge = (
                f"<span style='background:#dbeafe;color:#1d4ed8;font-size:0.6rem;"
                f"padding:1px 5px;border-radius:8px;font-weight:700;margin-left:4px;'>"
                f"{html.escape(_sq)}</span>"
                if _sq else ""
            )
            # Role badge (boxed)
            _role_badge = (
                f"<span style='background:{_c['tag']}18;color:{_c['tag']};font-size:0.62rem;"
                f"padding:1px 6px;border-radius:4px;font-weight:600;border:1px solid {_c['tag']}30;"
                f"margin-left:4px;'>{html.escape(_rl)}</span>"
                if _rl else ""
            )
            _meta = ""
            if _sp and _sp.lower() not in ("", "unknown", "nan"):
                _meta = (
                    f"<div style='margin-top:6px;display:flex;justify-content:space-between;"
                    f"align-items:center;flex-wrap:wrap;gap:3px;'>"
                    f"<span style='font-size:0.71rem;color:#6b7280;display:flex;align-items:center;"
                    f"flex-wrap:wrap;gap:3px;'>{html.escape(_sp)}"
                    f"{_role_badge}{_qtr_badge}"
                    f"</span><span style='font-size:0.68rem;letter-spacing:1px;'>{_dots}</span></div>"
                )
            st.markdown(
                f"<div style='border-left:3px solid {_c['border']};"
                f"padding:9px 12px;margin-bottom:8px;background:{_c['bg']};"
                f"border-radius:0 6px 6px 0;'>"
                f"<p style='margin:0;font-size:0.82rem;color:#1f2937;line-height:1.55;'>"
                f"\"{html.escape(_q)}\"</p>{_meta}</div>",
                unsafe_allow_html=True,
            )
        _rem = len(_sigs) - _show_n
        # Use on_click callbacks — avoids explicit st.rerun() which collapses expanders
        if _rem > 0:
            def _show_more_cb(_key=_sn_key):
                st.session_state[_key] = st.session_state.get(_key, 3) + 3
            st.button(
                f"Show {min(3, _rem)} more ›",
                key=f"more_{_sn_key}",
                on_click=_show_more_cb,
                use_container_width=True,
            )
        elif _show_n > 3:
            def _show_less_cb(_key=_sn_key):
                st.session_state[_key] = 3
            st.button(
                "Show less ‹",
                key=f"less_{_sn_key}",
                on_click=_show_less_cb,
                use_container_width=True,
            )

    if _has_oro:
        # ── Quarter selector inline with the "Signals from" header ──────────
        _sig_hdr_col, _sig_qtr_col = st.columns([3, 2])
        with _sig_hdr_col:
            st.markdown(
                f"<div style='margin:1.5rem 0 0.3rem 0;'>"
                f"<span style='font-weight:700;font-size:0.95rem;color:#111827;'>"
                f"Signals from the earnings call</span>"
                f"<span style='color:#9ca3af;font-size:0.8rem;margin-left:8px;'>"
                f"{canonical_company}</span></div>",
                unsafe_allow_html=True,
            )
        with _sig_qtr_col:
            # Compact radio for quarter — synced with _ins_qtr but independent key
            # so changing it here doesn't reload the management commentary above
            _sig_qtr_key = f"sig_qtr_{company}_{_ins_year}"
            if _sig_qtr_key not in st.session_state:
                st.session_state[_sig_qtr_key] = _ins_qtr
            _sig_qtr_opts = ["Annual", "Q1", "Q2", "Q3", "Q4"]
            _sig_qtr_sel = st.radio(
                "Quarter",
                _sig_qtr_opts,
                index=_sig_qtr_opts.index(st.session_state[_sig_qtr_key])
                      if st.session_state[_sig_qtr_key] in _sig_qtr_opts else 0,
                key=_sig_qtr_key,
                horizontal=True,
                label_visibility="collapsed",
            )
        _sig_q_str = "" if _sig_qtr_sel == "Annual" else _sig_qtr_sel
        _sig_period = f"Q{_sig_qtr_sel.lstrip('Q')} {_ins_year}" if _sig_q_str else str(_ins_year)

        # Re-fetch signals if quarter selection differs from ins_qtr
        if _sig_q_str != _ins_q_str:
            try:
                from utils.transcript_live import extract_outlook_risks_opportunities as _ero2
                _oro = _ero2(
                    str(data_processor.data_path),
                    canonical_company,
                    int(_ins_year),
                    _sig_q_str,
                )
                _has_oro = any(bool(v) for v in _oro.values())
            except Exception:
                pass

        # ── Always visible: Outlook · Risks · Opportunities ─────────────────
        _core_cols = st.columns(3, gap="medium")
        for _ci, _cat in enumerate(["Outlook", "Risks", "Opportunities"]):
            with _core_cols[_ci]:
                _render_signal_col(_cat, _oro, SIGNAL_COLORS, company, _ins_year, _sig_qtr_sel)

        # ── Collapsible: 6 additional categories — no inner filter UI ───────
        _ext_cats = ["Investment", "Product Shifts", "User Behavior",
                     "Monetization", "Strategic Direction", "Broadcaster Threats"]
        _ext_with_data = [c for c in _ext_cats if _oro.get(c)]
        if _ext_with_data:
            _exp_key = f"ext_exp_{company}_{_ins_year}_{_sig_qtr_sel}"
            with st.expander(
                f"More signal categories — {len(_ext_with_data)} with data",
                expanded=st.session_state.get(f"exp_open_{_exp_key}", False),
                key=_exp_key,
            ):
                _ext_n = min(3, len(_ext_with_data))
                _ext_cols = st.columns(_ext_n, gap="medium")
                for _ei, _ecat in enumerate(_ext_with_data):
                    with _ext_cols[_ei % _ext_n]:
                        _render_signal_col(_ecat, _oro, SIGNAL_COLORS, company, _ins_year, _sig_qtr_sel)

    # ── Forward Intelligence Panel ─────────────────────────────────────────
    try:
        from utils.transcript_live import extract_forward_looking_signals, SIGNAL_COLORS
        _fwd_signals = extract_forward_looking_signals(
            excel_path=str(data_processor.data_path),
            company=canonical_company,
            year=int(_ins_year),
            quarter=_ins_q_str,
        )
        # Also try DB merge if available
        try:
            from utils.database_service import get_forward_signals as _db_fwd
            _db_signals = _db_fwd(company=canonical_company, year=int(_ins_year), limit=6)
            if _db_signals:
                _existing_keys = {s["quote"][:60].lower() for s in _fwd_signals}
                for ds in _db_signals:
                    if ds.get("quote", "")[:60].lower() not in _existing_keys:
                        _fwd_signals.append(ds)
                _fwd_signals.sort(key=lambda x: -x.get("score", 0))
        except Exception:
            pass

        if _fwd_signals:
            _period = (
                f"Q{_parse_quarter_int(selected_quarter)} {year}"
                if _parse_quarter_int(selected_quarter) else str(year)
            )
            st.markdown(
                f"<div style='margin:1.5rem 0 0.5rem 0;'>"
                f"<span style='font-weight:700;font-size:1rem;color:#111827;'>Forward Intelligence</span>"
                f"<span style='color:#6b7280;font-size:0.82rem;margin-left:10px;'>"
                f"{canonical_company} · {_period} · Scored across 5 verification layers</span></div>",
                unsafe_allow_html=True,
            )
            _fwd_sn_key = f"fwd_show_n_{company}_{year}"
            if _fwd_sn_key not in st.session_state:
                st.session_state[_fwd_sn_key] = 3
            _fwd_show_n = st.session_state[_fwd_sn_key]
            _fwd_cols = st.columns(2, gap="medium")
            for _fi, _sig in enumerate(_fwd_signals[:_fwd_show_n]):
                with _fwd_cols[_fi % 2]:
                    _q = str(_sig.get("quote", "")).strip()
                    _sp = str(_sig.get("speaker", "")).strip()
                    _rl = str(_sig.get("role", "")).strip()
                    _sc = float(_sig.get("score", 0))
                    # Confidence squares
                    _filled = max(1, int(min(_sc / 15.0, 1.0) * 5))
                    _conf = "■" * _filled + "□" * (5 - _filled)
                    _fwd_qtr = str(_sig.get("quarter", "")).strip()
                    _fwd_qtr_badge = (
                        f"<span style='background:#dbeafe;color:#1d4ed8;font-size:0.62rem;"
                        f"padding:1px 6px;border-radius:8px;font-weight:700;margin-left:6px;'>"
                        f"{html.escape(_fwd_qtr)}</span>"
                        if _fwd_qtr else ""
                    )
                    _sp_html = ""
                    if _sp and _sp.lower() not in ("", "unknown", "nan"):
                        _sp_html = (
                            f"<div style='font-size:0.72rem;color:#6b7280;margin-top:5px;"
                            f"display:flex;justify-content:space-between;align-items:center;'>"
                            f"<span>{html.escape(_sp)}"
                            + (f" · <span style='color:#1d4ed8'>{html.escape(_rl)}</span>" if _rl else "")
                            + f"{_fwd_qtr_badge}</span>"
                            f"<span style='color:#3b82f6;font-family:monospace;letter-spacing:1px;"
                            f"font-size:0.7rem;'>{_conf}</span></div>"
                        )
                    st.markdown(
                        f"<div style='background:#eff6ff;border:1px solid #3b82f6;"
                        f"border-left:3px solid #1d4ed8;border-radius:6px;padding:10px 12px;margin-bottom:8px;'>"
                        f"<p style='margin:0;font-size:0.83rem;color:#374151;"
                        f"line-height:1.6;font-style:italic;'>"
                        f"\"{html.escape(_q)}\"</p>"
                        f"{_sp_html}</div>",
                        unsafe_allow_html=True,
                    )
            # Show more / show less — on_click avoids explicit rerun
            _fwd_remaining = len(_fwd_signals) - _fwd_show_n
            _btn_row = st.columns(2)
            if _fwd_remaining > 0:
                with _btn_row[0]:
                    def _fwd_more_cb(_k=_fwd_sn_key):
                        st.session_state[_k] = st.session_state.get(_k, 3) + 3
                    st.button(
                        f"Show {min(3, _fwd_remaining)} more  ›",
                        key=f"fwd_more_{company}_{year}",
                        on_click=_fwd_more_cb,
                        use_container_width=True,
                    )
            if _fwd_show_n > 3:
                with _btn_row[1]:
                    def _fwd_less_cb(_k=_fwd_sn_key):
                        st.session_state[_k] = 3
                    st.button(
                        "Show less  ‹",
                        key=f"fwd_less_{company}_{year}",
                        on_click=_fwd_less_cb,
                        use_container_width=True,
                    )
    except Exception:
        pass
    # TODO: This section could also auto-generate a 3-bullet company outlook summary
    # using call_ai() from ai_service.py with the top 3 forward signals as input.

    # ── Market Intelligence — Polymarket prediction bets ──────────────────
    try:
        from utils.polymarket import fetch_company_bets, COMPANY_KEYWORDS

        # Resolve company name for Polymarket (handle normalization differences)
        _poly_company = canonical_company
        # Also check common aliases used in Polymarket module
        if canonical_company not in COMPANY_KEYWORDS:
            _alias_map = {
                "Meta": "Meta Platforms",
                "Meta Platforms Inc": "Meta Platforms",
                "Alphabet Inc": "Alphabet",
                "Warner Bros Discovery": "Warner Bros. Discovery",
                "Paramount": "Paramount Global",
            }
            _poly_company = _alias_map.get(canonical_company, canonical_company)

        _poly_bets = fetch_company_bets(_poly_company)
        if _poly_bets:
            st.markdown(
                f"<div style='margin:1.5rem 0 0.5rem 0;display:flex;align-items:baseline;gap:10px;'>"
                f"<span style='font-weight:700;font-size:1rem;color:#111827;'>Market Intelligence</span>"
                f"<span style='color:#7c3aed;font-size:0.78rem;font-weight:600;'>"
                f"Polymarket · {len(_poly_bets)} active bet{'s' if len(_poly_bets) != 1 else ''}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            def _yes_badge(p):
                if p is None:
                    return "<span style='color:#9ca3af;font-size:0.72rem;'>—</span>"
                col = "#16a34a" if p >= 65 else ("#d97706" if p >= 45 else "#dc2626")
                bg = "#dcfce7" if p >= 65 else ("#fef3c7" if p >= 45 else "#fee2e2")
                return (
                    f"<span style='background:{bg};color:{col};font-weight:700;"
                    f"font-size:0.72rem;padding:2px 8px;border-radius:999px;"
                    f"white-space:nowrap;'>{p:.0f}% YES</span>"
                )

            st.markdown("""<style>
            @keyframes polyPulse { 0%,100%{box-shadow:0 0 0 0 rgba(124,58,237,0);border-left-color:#7c3aed;} 50%{box-shadow:-2px 0 8px 0 rgba(124,58,237,0.15);border-left-color:#a78bfa;} }
            @keyframes liveDot { 0%,100%{opacity:1;} 50%{opacity:0.35;} }
            @keyframes barPulse { 0%,100%{opacity:1;} 50%{opacity:0.75;} }
            .poly-bet-card { animation: polyPulse 3s ease-in-out infinite; transition: transform 0.2s, box-shadow 0.2s; }
            .poly-bet-card:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(124,58,237,0.12) !important; }
            .poly-live-dot { display:inline-block;width:6px;height:6px;border-radius:50%;background:#16a34a;margin-right:4px;animation:liveDot 2s ease-in-out infinite; }
            .poly-bar-fill { animation: barPulse 4s ease-in-out infinite; }
            </style>""", unsafe_allow_html=True)

            _poly_cols = st.columns(2, gap="medium")
            for _pi, _bet in enumerate(_poly_bets[:6]):
                with _poly_cols[_pi % 2]:
                    _bq = str(_bet.get("question", ""))
                    _yes = _bet.get("yes_price")
                    _no = _bet.get("no_price")
                    _vol = str(_bet.get("volume_fmt", ""))
                    _end = str(_bet.get("end_date", ""))
                    _url = str(_bet.get("url", "https://polymarket.com"))
                    _yes_html = _yes_badge(_yes)
                    _no_val = f"NO {_no:.0f}%" if _no is not None else ""
                    _meta_parts = []
                    if _vol:
                        _meta_parts.append(f"<span style='color:#6b7280;'>{html.escape(_vol)} vol</span>")
                    if _end:
                        _meta_parts.append(f"<span style='color:#9ca3af;'>ends {html.escape(_end)}</span>")
                    _meta_html = "<span style='color:#d1d5db;margin:0 3px;'>·</span>".join(_meta_parts)
                    # Probability bar
                    _bar_pct = int(_yes or 50)
                    _bar_col = "#16a34a" if _bar_pct >= 65 else ("#d97706" if _bar_pct >= 45 else "#dc2626")
                    st.markdown(
                        f"<a href='{_url}' target='_blank' rel='noopener' style='text-decoration:none;'>"
                        f"<div class='poly-bet-card' style='background:#f9fafb;border:1px solid #e5e7eb;"
                        f"border-left:3px solid #7c3aed;border-radius:6px;"
                        f"padding:10px 12px;margin-bottom:8px;'>"
                        f"<div style='display:flex;align-items:flex-start;justify-content:space-between;"
                        f"gap:8px;margin-bottom:7px;'>"
                        f"<p style='margin:0;font-size:0.83rem;color:#111827;"
                        f"line-height:1.5;font-weight:500;flex:1;'><span class='poly-live-dot'></span>{html.escape(_bq)}</p>"
                        f"{_yes_html}"
                        f"</div>"
                        f"<div style='background:#e5e7eb;border-radius:999px;height:4px;margin-bottom:6px;'>"
                        f"<div class='poly-bar-fill' style='background:{_bar_col};width:{_bar_pct}%;height:4px;border-radius:999px;'></div>"
                        f"</div>"
                        f"<div style='display:flex;align-items:center;gap:4px;font-size:0.7rem;'>"
                        f"{_meta_html}</div>"
                        f"</div></a>",
                        unsafe_allow_html=True,
                    )

            if len(_poly_bets) > 6:
                st.caption(
                    f"Showing 6 of {len(_poly_bets)} bets — "
                    f"[view all on Polymarket](https://polymarket.com)"
                )
    except Exception:
        pass

    company_insights_df = load_company_insights_text(data_processor.data_path)

    company_insights_filtered = pd.DataFrame()
    insight_source_label = f"Annual {year}"
    if company_insights_df is not None and not company_insights_df.empty:
        all_insights = company_insights_df.copy()
        all_insights["company"] = all_insights["company"].astype(str).str.strip().apply(normalize_company)
        all_insights["year"] = pd.to_numeric(all_insights["year"], errors="coerce")
        all_insights = all_insights[
            (all_insights["company"] == canonical_company)
            & (all_insights["year"] == int(year))
            & (all_insights["insight"].notna())
        ].copy()

        qnum = _parse_quarter_int(selected_quarter)
        if "quarter" in all_insights.columns and qnum is not None:
            all_insights["_quarter_num"] = all_insights["quarter"].apply(_parse_quarter_int)
            quarter_match = all_insights[all_insights["_quarter_num"] == int(qnum)].copy()
            if not quarter_match.empty:
                company_insights_filtered = quarter_match
                insight_source_label = f"Q{qnum} {year}"
            else:
                annual_fallback = all_insights[
                    all_insights["quarter"].isna()
                    | (all_insights["quarter"].astype(str).str.strip() == "")
                ].copy()
                company_insights_filtered = annual_fallback
                insight_source_label = f"Annual {year}"
        else:
            if "quarter" in all_insights.columns:
                all_insights["quarter"] = all_insights["quarter"].fillna("")
                all_insights = all_insights[
                    all_insights["quarter"].astype(str).str.strip().str.upper().isin(
                        ["", "ANNUAL", "FY", "YEARLY", "YEAR"]
                    )
                ].copy()
            company_insights_filtered = all_insights
            insight_source_label = f"Annual {year}"

        if "category" in company_insights_filtered.columns:
            company_insights_filtered["category"] = company_insights_filtered["category"].fillna("")

    if company_insights_filtered.empty:
        _co_insight_generated = False
        _ant_available_ci = False
        try:
            from utils.anthropic_service import is_api_available as _ci_ant_check, call_claude as _ci_call
            _ant_available_ci = _ci_ant_check()
        except Exception:
            pass
        if _ant_available_ci:
            try:
                _ci_transcript = _load_transcript_for_company(
                    str(data_processor.data_path), canonical_company, int(year),
                    selected_quarter if selected_quarter and selected_quarter != "Annual" else "",
                )
                if _ci_transcript:
                    _ci_system = (
                        "You are a senior media & technology financial analyst. "
                        "Write exactly 3 insight bullets about this company's performance. "
                        "Format: one sentence per bullet, separated by | character. "
                        "Cover: revenue performance, key business development, forward outlook. "
                        "Be specific with numbers. No bullet symbols, no headers, no markdown."
                    )
                    _ci_period = f"Q{_parse_quarter_int(selected_quarter)} {year}" if _parse_quarter_int(selected_quarter) else str(year)
                    _ci_result = _ci_call(
                        _ci_system,
                        f"Company: {canonical_company}\nPeriod: {_ci_period}\n"
                        f"Transcript (first 3000 chars):\n{_ci_transcript[:3000]}\n\nWrite 3 insight bullets separated by |",
                        max_tokens=350,
                    )
                    if _ci_result:
                        _ci_parts = [p.strip().lstrip("•-·").strip() for p in _ci_result.split("|") if p.strip()]
                        if _ci_parts:
                            company_color = (
                                COMPANY_COLORS.get(company)
                                or COMPANY_COLORS.get(canonical_company)
                                or "#111827"
                            )
                            _items_html = "".join(f"<li>{html.escape(p)}</li>" for p in _ci_parts[:3])
                            _card = (
                                f"<div class='company-insight-card insight-card' style='border-left:4px solid {company_color};'>"
                                f"<div class='company-insight-title'>✨ AI Analysis</div>"
                                f"<ul class='company-insight-list'>{_items_html}</ul>"
                                f"</div>"
                            )
                            st.markdown("#### Company insights")
                            st.markdown(
                                f"<div class='insights-carousel-wrap' data-carousel='company'>"
                                f"<div class='insights-carousel' id='insights-carousel-company'>{_card}</div>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )
                            _co_insight_generated = True
            except Exception:
                pass
    else:
        st.markdown("#### Company insights")
        st.caption(f"Source: {insight_source_label}")
        company_cards = []
        company_color = (
            COMPANY_COLORS.get(company)
            or COMPANY_COLORS.get(canonical_company)
            or COMPANY_COLORS.get(normalize_company(company))
            or "#111827"
        )
        for category, group in company_insights_filtered.groupby("category"):
            title = str(category).strip() if category and str(category).strip() else "Company Insight"
            insights = []
            for item in group["insight"].tolist():
                for part in split_insight_text(item):
                    if part and str(part).strip():
                        insights.append(html.escape(str(part).strip()))
            if not insights:
                continue
            insight_items = "".join(f"<li>{item}</li>" for item in insights)
            company_cards.append(
                f"<div class=\"company-insight-card insight-card\" style=\"border-left: 4px solid {company_color};\">"
                f"<div class=\"company-insight-title\">{html.escape(title)}</div>"
                f"<ul class=\"company-insight-list\">{insight_items}</ul>"
                "</div>"
            )
        if company_cards:
            st.markdown(
                f"<div class='insights-carousel-wrap' data-carousel='company'>"
                f"<button class='insights-nav left' data-dir='left' data-target='company' aria-label='Scroll left'>&lsaquo;</button>"
                f"<div class='insights-carousel' id='insights-carousel-company'>{''.join(company_cards)}</div>"
                f"<button class='insights-nav right' data-dir='right' data-target='company' aria-label='Scroll right'>&rsaquo;</button>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("Company insights are not available for this company/year.")

    company_auto_narratives_df = load_company_auto_narratives(data_processor.data_path)
    if company_auto_narratives_df is not None and not company_auto_narratives_df.empty:
        auto_rows = company_auto_narratives_df.copy()
        if "company" not in auto_rows.columns and "companies" in auto_rows.columns:
            auto_rows["company"] = auto_rows["companies"].astype(str).str.split("|").str[0]
        if {"company", "year"}.issubset(auto_rows.columns):
            auto_rows["company"] = auto_rows["company"].astype(str).str.strip().apply(normalize_company)
            auto_rows["year"] = pd.to_numeric(auto_rows["year"], errors="coerce")
            auto_rows = auto_rows[
                (auto_rows["company"] == canonical_company)
                & (auto_rows["year"] == int(year))
            ].copy()
            if not auto_rows.empty:
                st.markdown(
                    """
                    <style>
                    .wm-priority {
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        border-radius: 999px;
                        padding: 0.18rem 0.5rem;
                        font-size: 0.68rem;
                        font-weight: 700;
                        letter-spacing: 0.03em;
                        text-transform: uppercase;
                        line-height: 1;
                    }
                    .wm-priority-high { background: rgba(239,68,68,0.15); color: #ef4444; }
                    .wm-priority-medium { background: rgba(249,115,22,0.15); color: #f97316; }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
                company_color = (
                    COMPANY_COLORS.get(company)
                    or COMPANY_COLORS.get(canonical_company)
                    or COMPANY_COLORS.get(normalize_company(company))
                    or "#111827"
                )
                narrative_cards = []
                for _, row in auto_rows.sort_values(["priority", "insight_id"]).iterrows():
                    raw_text = str(row.get("text", "") or row.get("comment", "") or "").strip()
                    if not raw_text:
                        continue
                    priority = str(row.get("priority", "medium")).strip().lower()
                    priority = priority if priority in {"high", "medium"} else "medium"
                    category = str(row.get("category", "")).strip() or "Narrative"
                    narrative_cards.append(
                        f"<div class=\"company-insight-card insight-card\" style=\"border-left: 4px solid {company_color};\">"
                        f"<div style=\"display:flex; align-items:center; justify-content:space-between; gap:8px;\">"
                        f"<div style=\"font-size:0.68rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:#64748B;\">{html.escape(category)}</div>"
                        f"<span class=\"wm-priority wm-priority-{priority}\">{html.escape(priority.upper())}</span>"
                        "</div>"
                        f"<div style=\"margin-top:8px; font-size:0.95rem; line-height:1.55;\">{html.escape(raw_text)}</div>"
                        "<div style=\"margin-top:10px; color:#6b7280; font-size:0.78rem; font-style:italic;\">⚡ Auto-generated from financial metrics</div>"
                        "</div>"
                    )
                if narrative_cards:
                    st.markdown("#### Auto narratives")
                    st.markdown("".join(narrative_cards), unsafe_allow_html=True)

    components.html(
        """
        <script>
        (function() {
            const root = window.parent.document;
            const bindCarousel = (key) => {
                const carousel = root.getElementById(`insights-carousel-${key}`);
                if (!carousel) return;
                const leftBtn = root.querySelector(`.insights-nav.left[data-target="${key}"]`);
                const rightBtn = root.querySelector(`.insights-nav.right[data-target="${key}"]`);
                const updateButtons = () => {
                    const maxScroll = carousel.scrollWidth - carousel.clientWidth - 2;
                    if (leftBtn) leftBtn.disabled = carousel.scrollLeft <= 2;
                    if (rightBtn) rightBtn.disabled = carousel.scrollLeft >= maxScroll;
                };
                const scrollByAmount = (dir) => {
                    const card = carousel.querySelector(".insight-card");
                    const step = card ? card.getBoundingClientRect().width + 14 : 320;
                    carousel.scrollBy({ left: dir * step, behavior: "smooth" });
                };
                if (leftBtn) {
                    leftBtn.addEventListener("click", () => scrollByAmount(-1));
                }
                if (rightBtn) {
                    rightBtn.addEventListener("click", () => scrollByAmount(1));
                }
                carousel.addEventListener("scroll", () => {
                    window.requestAnimationFrame(updateButtons);
                });
                updateButtons();
                window.addEventListener("resize", updateButtons);
            };
            bindCarousel("segment");
            bindCarousel("company");
        })();
        </script>
        """,
        height=0,
    )


    # Segment composition
    st.subheader("Segment Composition")
    canonical_company = normalize_company(company)
    segments_quarterly_all = load_quarterly_segments(
        data_processor.data_path, get_file_mtime(data_processor.data_path)
    )
    has_quarterly_segments = (
        segments_quarterly_all is not None
        and not segments_quarterly_all.empty
        and canonical_company in segments_quarterly_all["company"].dropna().unique().tolist()
    )
    segment_source_df = segments_quarterly_all if has_quarterly_segments else data_processor.df_segments
    segment_colors = get_segment_color_map(segment_source_df, canonical_company)
    segment_insights_df = load_company_segment_insights(data_processor.data_path)

    segment_years = []
    if segment_source_df is not None and not segment_source_df.empty:
        try:
            segment_years = (
                segment_source_df[segment_source_df["company"] == canonical_company]["year"]
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            )
        except Exception:
            segment_years = []
    min_year = int(min(segment_years)) if segment_years else int(min(years))
    max_year = int(max(segment_years)) if segment_years else int(max(years))
    segment_range_key = "segment_year_range"
    default_segment_range = (int(year), int(year))
    segment_year_range = st.session_state.get(segment_range_key, default_segment_range)
    if isinstance(segment_year_range, int):
        segment_year_range = (segment_year_range, segment_year_range)
    segment_start, segment_end = segment_year_range
    segment_start = max(int(min_year), min(int(max_year), int(segment_start)))
    segment_end = max(int(min_year), min(int(max_year), int(segment_end)))
    if segment_start > segment_end:
        segment_start, segment_end = segment_end, segment_start

    segment_labels = []
    segment_values = []
    segment_yoy_labels = []
    segments_df = segment_source_df
    if segments_df is not None and not segments_df.empty:
        composition_df = segments_df[
            (segments_df["company"] == canonical_company)
            & (segments_df["year"] >= segment_start)
            & (segments_df["year"] <= segment_end)
        ]
        if not composition_df.empty:
            composition_df = composition_df[composition_df["segment"].notna()]
            composition_df["segment"] = composition_df["segment"].apply(
                lambda s: normalize_segment_label(canonical_company, s)
            )
            composition_df["segment"] = composition_df["segment"].astype(str).str.strip()
            composition_df = composition_df[
                composition_df["segment"].notna()
                & (composition_df["segment"] != "")
                & (composition_df["segment"] != "Total Revenue")
            ]
            composition_df = composition_df.groupby("segment", as_index=False)["revenue"].sum()
            composition_df = composition_df.sort_values("revenue", ascending=False)
            segment_labels = composition_df["segment"].tolist()
            segment_values = composition_df["revenue"].fillna(0).tolist()
            segment_yoy_labels = ["—"] * len(segment_labels)

            if segment_start == segment_end:
                prev_year = segment_start - 1
                prev_df = segments_df[
                    (segments_df["company"] == canonical_company)
                    & (segments_df["year"] == prev_year)
                    & (segments_df["segment"].notna())
                    & (segments_df["segment"] != "Total Revenue")
                ]
                if not prev_df.empty:
                    prev_df = prev_df.copy()
                    prev_df["segment"] = prev_df["segment"].apply(
                        lambda s: normalize_segment_label(canonical_company, s)
                    )
                    prev_df["segment"] = prev_df["segment"].astype(str).str.strip()
                    prev_df = prev_df[
                        prev_df["segment"].notna()
                        & (prev_df["segment"] != "")
                        & (prev_df["segment"] != "Total Revenue")
                    ]
                    prev_df = prev_df.groupby("segment", as_index=False)["revenue"].sum()
                    prev_map = dict(zip(prev_df["segment"], prev_df["revenue"]))
                    for idx, segment in enumerate(segment_labels):
                        prev_value = prev_map.get(segment)
                        current_value = segment_values[idx]
                        if prev_value is None or pd.isna(prev_value) or prev_value == 0:
                            segment_yoy_labels[idx] = "—"
                        else:
                            yoy = ((current_value - prev_value) / prev_value) * 100
                            segment_yoy_labels[idx] = format_yoy_label(yoy, "%")

    segment_insights_filtered = pd.DataFrame()
    if segment_insights_df is not None and not segment_insights_df.empty:
        segment_insights_filtered = segment_insights_df.copy()
        segment_insights_filtered["company"] = (
            segment_insights_filtered["company"].astype(str).str.strip().apply(normalize_company)
        )
        segment_insights_filtered["year"] = pd.to_numeric(
            segment_insights_filtered["year"], errors="coerce"
        )
        segment_insights_filtered["segment"] = segment_insights_filtered["segment"].apply(
            lambda s: normalize_segment_label(canonical_company, s)
        )
        segment_insights_filtered["segment"] = segment_insights_filtered["segment"].astype(str).str.strip()
        if "quarter" not in segment_insights_filtered.columns:
            segment_insights_filtered["quarter"] = ""
        segment_insights_filtered["_quarter_text"] = (
            segment_insights_filtered["quarter"].fillna("").astype(str).str.strip().str.upper()
        )
        segment_insights_filtered["_quarter_num"] = segment_insights_filtered["quarter"].apply(_parse_quarter_int)
        segment_insights_filtered = segment_insights_filtered[
            (segment_insights_filtered["company"] == canonical_company)
            & (segment_insights_filtered["segment"].notna())
            & (segment_insights_filtered["segment"] != "")
            & (segment_insights_filtered["insight"].notna())
        ]

    segment_insight_map = {}
    # ── FULLY AUTOMATIC SEGMENT INSIGHTS ─────────────────────────────────────
    selected_insight_qnum = _parse_quarter_int(selected_quarter)
    desired_insight_year = int(year) if selected_insight_qnum is not None else int(segment_end)

    # Build manual insight lookup (Excel overrides)
    _manual_lookup = {}
    if not segment_insights_filtered.empty:
        _stg = {k: v for k, v in segment_insights_filtered.groupby("segment")}
        _stg_norm = {normalize_segment(k): v for k, v in _stg.items() if str(k).strip()}
        for _seg_k, _seg_v in _stg_norm.items():
            _seg_v = _seg_v.copy()
            _seg_v["year"] = pd.to_numeric(_seg_v["year"], errors="coerce")
            _yr_rows = _seg_v[_seg_v["year"] == desired_insight_year]
            if _yr_rows.empty:
                _yr_rows = _seg_v[_seg_v["year"] == _seg_v["year"].max()] if not _seg_v.empty else pd.DataFrame()
            if not _yr_rows.empty:
                _texts = []
                for _item in _yr_rows["insight"].tolist():
                    for _part in split_insight_text(_item):
                        if _part and str(_part).strip():
                            _texts.append(str(_part).strip())
                if _texts:
                    _manual_lookup[_seg_k] = _texts

    # Use ALL segment labels from donut (not just ones with manual rows)
    _all_ordered = segment_labels if segment_labels else sorted(_manual_lookup.keys())

    # Load transcript once for this company/year
    _seg_transcript = ""
    try:
        _seg_transcript = _load_transcript_for_company(
            str(data_processor.data_path),
            canonical_company,
            int(desired_insight_year),
            selected_quarter if selected_quarter and selected_quarter != "Annual" else "",
        )
    except Exception:
        pass

    # Check if Anthropic API is available
    _ant_available = False
    try:
        from utils.anthropic_service import is_api_available as _ant_check
        _ant_available = _ant_check()
    except Exception:
        pass

    for raw_segment_name in _all_ordered:
        segment_name = str(raw_segment_name).strip()
        if not segment_name:
            continue

        segment_color = segment_colors.get(segment_name)
        if not segment_color:
            segment_color = match_segment_color(canonical_company, segment_name)
        if not segment_color:
            segment_color = COMPANY_COLORS.get(canonical_company, "#111827")

        # PRIORITY 0 — Manual Excel row (override)
        _manual_key = normalize_segment(segment_name)
        if _manual_key in _manual_lookup:
            _items = _manual_lookup[_manual_key]
            _items_html = "".join(
                f"<li style='color:#FFFFFF !important;'>{html.escape(t)}</li>"
                for t in _items
            )
            segment_insight_map[segment_name] = (
                f"<div class='segment-insight-card' style='background:{segment_color};color:#ffffff;width:100%;'>"
                f"<div class='segment-insight-title' style='color:#FFFFFF !important;'>{html.escape(segment_name)}</div>"
                f"<ul class='segment-insight-list' style='color:#FFFFFF !important;'>{_items_html}</ul>"
                f"</div>"
            )
            continue

        # Get segment revenue and YoY for context
        _seg_rev = None
        _seg_rev_prev = None
        _seg_yoy = None
        try:
            _rev_range = list(range(int(desired_insight_year) - 1, int(desired_insight_year) + 1))
            _sd = get_segment_data(canonical_company, segment_name, _rev_range)
            if _sd and desired_insight_year in _sd:
                _seg_rev = _sd[desired_insight_year]
                _prev = desired_insight_year - 1
                if _prev in _sd and _sd[_prev] and float(_sd[_prev]) != 0:
                    _seg_rev_prev = _sd[_prev]
                    _seg_yoy = (_seg_rev - _seg_rev_prev) / abs(_seg_rev_prev) * 100
        except Exception:
            pass

        # Fallback: pull revenue + YoY from composition_df / segment_yoy_labels
        if _seg_rev is None:
            try:
                if "composition_df" in dir() and composition_df is not None and not composition_df.empty:
                    _row = composition_df[composition_df["segment"] == segment_name]
                    if not _row.empty:
                        _seg_rev = float(_row["revenue"].iloc[0])
                if _seg_yoy is None and segment_labels and segment_name in segment_labels and "segment_yoy_labels" in dir():
                    _idx = segment_labels.index(segment_name)
                    if _idx < len(segment_yoy_labels):
                        _yoy_str = str(segment_yoy_labels[_idx])
                        _m = re.search(r"([+-]?\d+\.?\d*)%", _yoy_str)
                        if _m:
                            _seg_yoy = float(_m.group(1))
            except Exception:
                pass

        # Get best transcript sentence for this segment
        _seg_sentence = ""
        try:
            _seg_sentence = _find_best_transcript_sentence(_seg_transcript, segment_name)
        except Exception:
            pass

        # PRIORITY 1 — Claude API insight (if available)
        _insight_text = ""
        _source_badge = ""

        if _ant_available:
            try:
                from utils.anthropic_service import generate_segment_insight
                _insight_text = generate_segment_insight(
                    company=canonical_company,
                    segment=segment_name,
                    revenue_m=_seg_rev,
                    yoy_pct=_seg_yoy,
                    year=int(desired_insight_year),
                    quarter=selected_quarter if selected_quarter and selected_quarter != "Annual" else "",
                    transcript_sentence=_seg_sentence,
                )
                if _insight_text:
                    _source_badge = (
                        "<div style='font-size:0.65rem;opacity:0.7;margin-bottom:4px;"
                        "letter-spacing:0.06em;text-transform:uppercase;'>✨ AI generated</div>"
                    )
            except Exception:
                _insight_text = ""

        # PRIORITY 2 — Tier 1 template (revenue + transcript sentence)
        if not _insight_text:
            try:
                _insight_text = _build_auto_segment_insight(
                    segment_name=segment_name,
                    segment_revenue=_seg_rev,
                    segment_yoy=_seg_yoy,
                    transcript_sentence=_seg_sentence,
                    year=int(desired_insight_year),
                    quarter=selected_quarter if selected_quarter and selected_quarter != "Annual" else "",
                )
                if _insight_text:
                    _source_badge = (
                        "<div style='font-size:0.65rem;opacity:0.7;margin-bottom:4px;"
                        "letter-spacing:0.06em;text-transform:uppercase;'>📋 from transcript</div>"
                    )
            except Exception:
                _insight_text = ""

        # PRIORITY 3 — Generic fallback (always show something)
        if not _insight_text:
            _period = f"{desired_insight_year} {selected_quarter}".strip() if selected_quarter and selected_quarter != "Annual" else str(desired_insight_year)
            _insight_text = f"{segment_name} data for {canonical_company} in {_period}. Revenue data not yet available for this segment."
            _source_badge = ""

        _insight_escaped = html.escape(_insight_text)
        segment_insight_map[segment_name] = (
            f"<div class='segment-insight-card' style='background:{segment_color};color:#ffffff;width:100%;'>"
            f"<div class='segment-insight-title' style='color:#FFFFFF !important;'>{html.escape(segment_name)}</div>"
            f"{_source_badge}"
            f"<ul class='segment-insight-list' style='color:#FFFFFF !important;'>"
            f"<li style='color:#FFFFFF !important;'>{_insight_escaped}</li>"
            f"</ul>"
            f"</div>"
        )

    composition_cols = st.columns([0.95, 1.55], gap="large")
    with composition_cols[0]:
        st.markdown("#### Segment insights")
        if not segment_insight_map:
            st.info("Segment insights are not available for this company/year.")
        else:
            import json

            default_segment = next(iter(segment_insight_map.keys()))
            st.markdown(
                f"<div id='segment-insight-hover-card'>{segment_insight_map.get(default_segment, '')}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<div style='text-align:center; font-weight:600; color:#64748b; margin-top: 0.55rem;'>"
                "Note: segment values may vary due to inter-segment eliminations and consolidated reporting.</div>",
                unsafe_allow_html=True,
            )

            segment_colors_js = {
                label: (segment_colors.get(label) or match_segment_color(canonical_company, label) or "#111827")
                for label in (segment_labels or list(segment_insight_map.keys()))
            }
            insight_map_json = json.dumps(segment_insight_map)
            color_map_json = json.dumps(segment_colors_js)
            target_label = (segment_labels[0] if segment_labels else default_segment)

            components.html(
                f"""
                <script>
                (function() {{
                    const root = window.parent.document;
                    const insightMap = {insight_map_json};
                    const colorMap = {color_map_json};
                    const insightMapLower = Object.create(null);
                    const colorMapLower = Object.create(null);
                    Object.keys(insightMap || {{}}).forEach((k) => {{
                        insightMapLower[String(k).trim().toLowerCase()] = insightMap[k];
                    }});
                    Object.keys(colorMap || {{}}).forEach((k) => {{
                        colorMapLower[String(k).trim().toLowerCase()] = colorMap[k];
                    }});
                    const defaultSegment = {json.dumps(default_segment)};
                    const matchLabel = {json.dumps(target_label)};

                    const escapeHtml = (s) => String(s)
                        .replace(/&/g, "&amp;")
                        .replace(/</g, "&lt;")
                        .replace(/>/g, "&gt;")
                        .replace(/"/g, "&quot;")
                        .replace(/'/g, "&#39;");

                    const cardEl = root.getElementById("segment-insight-hover-card");
                    if (!cardEl) return;

                    const renderMissing = (label) => {{
                        const trimmed = String(label || "").trim();
                        const bg =
                            colorMap[trimmed] ||
                            colorMapLower[trimmed.toLowerCase()] ||
                            "#111827";
                        return (
                            `<div class="segment-insight-card" style="background: ${{bg}}; color: #ffffff; width: 100%; opacity: 0.92;">` +
                            `<div class="segment-insight-title">${{escapeHtml(trimmed)}}</div>` +
                            `<div style="font-size:0.84rem; line-height:1.45; color:#ffffff;">No insights available for this segment.</div>` +
                            `</div>`
                        );
                    }};

                    const setCard = (label) => {{
                        const trimmed = String(label || "").trim();
                        if (!trimmed) {{
                            cardEl.innerHTML = insightMap[defaultSegment] || "";
                            return;
                        }}
                        const direct = insightMap[trimmed];
                        const lowered = insightMapLower[trimmed.toLowerCase()];
                        cardEl.innerHTML = direct || lowered || renderMissing(trimmed);
                    }};

                    // Expose a stable callback so other Plotly hover handlers (e.g. the pop effect)
                    // aren't removed/replaced, and to avoid stale closures across reruns.
                    window.parent.__segmentInsightSetCard = (label) => {{
                        try {{
                            if (label) window.parent.__segmentInsightLastLabel = String(label);
                            setCard(label || window.parent.__segmentInsightLastLabel || defaultSegment);
                        }} catch (e) {{}}
                    }};

                    // Keep last hovered segment on screen.
                    window.parent.__segmentInsightSetCard(defaultSegment);

                    const findPieGraph = () => {{
                        const graphs = Array.from(root.querySelectorAll(".js-plotly-plot"));
                        for (const g of graphs) {{
                            try {{
                                const data = g.data || g._fullData;
                                if (!data) continue;
                                const hasMatch = data.some((tr) => {{
                                    if (!tr) return false;
                                    const t = tr.type || tr._type;
                                    if (t !== "pie") return false;
                                    const labels = tr.labels;
                                    if (!Array.isArray(labels)) return false;
                                    return labels.includes(matchLabel);
                                }});
                                if (hasMatch) return g;
                            }} catch (e) {{}}
                        }}
                        return null;
                    }};

                    let attempts = 0;
                    const timer = window.parent.setInterval(() => {{
                        attempts += 1;
                        const pie = findPieGraph();
                        if (!pie) {{
                            if (attempts > 40) window.parent.clearInterval(timer);
                            return;
                        }}
                        if (!pie.__segmentInsightBinderAdded) {{
                            pie.__segmentInsightBinderAdded = true;
                            pie.on("plotly_hover", (ev) => {{
                                try {{
                                    const label = ev && ev.points && ev.points[0] && ev.points[0].label;
                                    if (label && window.parent.__segmentInsightSetCard) {{
                                        window.parent.__segmentInsightSetCard(label);
                                    }}
                                }} catch (e) {{}}
                            }});
                            pie.on("plotly_click", (ev) => {{
                                try {{
                                    const label = ev && ev.points && ev.points[0] && ev.points[0].label;
                                    if (label && window.parent.__segmentInsightSetCard) {{
                                        window.parent.__segmentInsightSetCard(label);
                                    }}
                                }} catch (e) {{}}
                            }});
                        }}
                        if (window.parent.__segmentInsightSetCard) {{
                            window.parent.__segmentInsightSetCard(window.parent.__segmentInsightLastLabel || defaultSegment);
                        }}
                        window.parent.clearInterval(timer);
                    }}, 200);
                }})(); 
                </script>
                """,
                height=0,
            )

    with composition_cols[1]:
        import math as _math

        # Helper: compute outer-label annotations with connector lines for donut
        def _donut_annotations(labels, values, colors, yoy_pcts, period_text):
            total = sum(max(v, 0) for v in values)
            if total <= 0:
                return []

            cx, cy = 0.36, 0.5
            MIN_FRAC = 0.025

            items = []
            angle = _math.pi / 2
            for lbl, val, col, yoy in zip(labels, values, colors, yoy_pcts):
                frac = max(val, 0) / total
                span = frac * 2 * _math.pi
                if frac >= MIN_FRAC:
                    mid_angle = angle - span / 2
                    rim_rx, rim_ry = 0.30, 0.42
                    dot_x = cx + rim_rx * _math.cos(mid_angle)
                    dot_y = cy + rim_ry * _math.sin(mid_angle)
                    items.append({
                        "lbl": lbl, "val": val, "col": col, "yoy": yoy,
                        "frac": frac, "mid_angle": mid_angle,
                        "dot_x": dot_x, "dot_y": dot_y,
                    })
                angle -= span

            if not items:
                return []

            left  = sorted([d for d in items if _math.cos(d["mid_angle"]) < 0],  key=lambda d: -_math.sin(d["mid_angle"]))
            right = sorted([d for d in items if _math.cos(d["mid_angle"]) >= 0], key=lambda d: -_math.sin(d["mid_angle"]))

            anns = []

            def _place_group(group, is_left):
                if not group:
                    return
                n = len(group)
                y_top, y_bot = 0.88, 0.12
                step = (y_top - y_bot) / max(n - 1, 1)
                label_x = -0.04 if is_left else 0.76
                elbow_x =  0.03 if is_left else 0.69
                run_end_x = label_x + (0.07 if is_left else -0.07)
                for i, d in enumerate(group):
                    label_y = y_top - i * step
                    val_b   = d["val"] / 1000
                    val_str = f"${val_b:.0f}B" if val_b >= 10 else f"${val_b:.1f}B"
                    yoy_str = f" ({d['yoy']:+.0f}%)" if d["yoy"] is not None else ""
                    text = (
                        f"<b style='color:{d['col']};font-size:12px;'>{val_str}{yoy_str}</b>"
                        f"<br><span style='color:#c9d1d9;font-size:10px;'>{d['lbl']}</span>"
                    )
                    anns.append(dict(
                        x=label_x, y=label_y, xref="paper", yref="paper",
                        text=text, showarrow=False,
                        font=dict(color=d["col"], size=11, family="Montserrat, sans-serif"),
                        align="right" if is_left else "left",
                        bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)", borderpad=2,
                    ))

            _place_group(left,  is_left=True)
            _place_group(right, is_left=False)

            anns.append(dict(
                x=cx, y=cy - 0.10, xref="paper", yref="paper",
                text=f"<b>{period_text}</b>",
                showarrow=False,
                font=dict(size=11, color="#8b949e", family="Montserrat, sans-serif"),
                align="center", bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)",
            ))
            return anns

        # Helper: normalize + aggregate segments for one period
        def _agg_period_df(src_df):
            df = src_df.copy()
            df["segment"] = df["segment"].apply(
                lambda s: normalize_segment_label(canonical_company, s)
            )
            df = df[df["segment"].notna() & (df["segment"] != "") & (df["segment"] != "Total Revenue")]
            df = df.groupby("segment", as_index=False)["revenue"].sum()
            return df.sort_values("revenue", ascending=False)

        # Helper: compute YoY per segment given current and previous dicts
        def _compute_yoy(labels, values, prev_map):
            result = []
            for lbl, val in zip(labels, values):
                prev = prev_map.get(lbl)
                if prev is not None and prev != 0:
                    result.append((val - prev) / abs(prev) * 100)
                else:
                    result.append(None)
            return result

        # Build animation periods
        _is_annual = (selected_quarter == "Annual")

        # Animation granularity toggle — only show if quarterly data exists
        if has_quarterly_segments:
            _anim_mode = st.radio(
                "Animation mode",
                options=["Quarterly", "Annual"],
                index=0 if not _is_annual else 1,
                horizontal=True,
                key=f"seg_anim_mode_{canonical_company}_{year}",
                label_visibility="collapsed",
            )
            _use_quarterly_anim = (_anim_mode == "Quarterly")
        else:
            _use_quarterly_anim = False

        if has_quarterly_segments and _use_quarterly_anim:
            _qdf = segments_quarterly_all[
                segments_quarterly_all["company"] == canonical_company
            ].copy()
            _qdf = _qdf[_qdf["segment"].notna() & (_qdf["segment"] != "Total Revenue")]
            _qperiods = (
                _qdf[["year", "quarter_num"]]
                .dropna()
                .drop_duplicates()
                .sort_values(["year", "quarter_num"])
            )
            _anim_periods = [
                (f"{int(r.year)} Q{int(r.quarter_num)}", int(r.year), int(r.quarter_num))
                for _, r in _qperiods.iterrows()
            ]
        else:
            # Annual mode: one frame per year
            _annual_years = (
                sorted(
                    segments_quarterly_all[
                        segments_quarterly_all["company"] == canonical_company
                    ]["year"].dropna().astype(int).unique().tolist()
                )
                if has_quarterly_segments
                else sorted(segment_years)
            )
            _anim_periods = [(f"FY {yr}", yr, None) for yr in _annual_years]

        _pie_frames = []
        for _plabel, _pyr, _pqn in _anim_periods:
            if _pqn is not None:
                _dfp_raw = segments_quarterly_all[
                    (segments_quarterly_all["company"] == canonical_company)
                    & (segments_quarterly_all["year"] == _pyr)
                    & (segments_quarterly_all["quarter_num"] == _pqn)
                ]
                _prev_raw = segments_quarterly_all[
                    (segments_quarterly_all["company"] == canonical_company)
                    & (segments_quarterly_all["year"] == _pyr - 1)
                    & (segments_quarterly_all["quarter_num"] == _pqn)
                ]
            else:
                # Annual — aggregate all quarters if quarterly data exists
                if has_quarterly_segments:
                    _dfp_raw = segments_quarterly_all[
                        (segments_quarterly_all["company"] == canonical_company)
                        & (segments_quarterly_all["year"] == _pyr)
                    ]
                    _prev_raw = segments_quarterly_all[
                        (segments_quarterly_all["company"] == canonical_company)
                        & (segments_quarterly_all["year"] == _pyr - 1)
                    ]
                else:
                    _dfp_raw = segment_source_df[
                        (segment_source_df["company"] == canonical_company)
                        & (segment_source_df["year"] == _pyr)
                    ]
                    _prev_raw = segment_source_df[
                        (segment_source_df["company"] == canonical_company)
                        & (segment_source_df["year"] == _pyr - 1)
                    ]

            if _dfp_raw.empty:
                continue

            _dfp = _agg_period_df(_dfp_raw)
            _fl = _dfp["segment"].tolist()
            _fv = _dfp["revenue"].fillna(0).tolist()
            _fc = [segment_colors.get(l, "#999999") for l in _fl]

            _prev_df = _agg_period_df(_prev_raw) if not _prev_raw.empty else pd.DataFrame()
            _prev_map = dict(zip(_prev_df["segment"], _prev_df["revenue"])) if not _prev_df.empty else {}
            _fyoy = _compute_yoy(_fl, _fv, _prev_map)

            _frame_anns = _donut_annotations(_fl, _fv, _fc, _fyoy, _plabel)

            _pie_frames.append(
                go.Frame(
                    data=[
                        go.Pie(
                            labels=_fl,
                            values=[max(v, 0) for v in _fv],
                            hole=0.55,
                            sort=False,
                            direction="clockwise",
                            rotation=90,
                            marker=dict(
                                colors=_fc,
                                line=dict(color="rgba(0,0,0,0.18)", width=1),
                            ),
                            textinfo="percent",
                            textfont=dict(color="#374151", size=10),
                            hovertemplate=(
                                "<b>%{label}</b><br>$%{value:,.0f}M &nbsp;%{percent}"
                                "<extra></extra>"
                            ),
                        )
                    ],
                    name=_plabel,
                    layout=go.Layout(annotations=_frame_anns),
                )
            )

        if not _pie_frames:
            st.info("Segment composition is not available for this company.")
        else:
            # Find frame closest to the selected `year`
            _init_idx = len(_pie_frames) - 1
            # Find frame closest to the selected year (for Annual, pick first Q of that year)
            _init_idx = len(_pie_frames) - 1
            for _i, (_lbl, _yr, _qn) in enumerate(_anim_periods):
                if _yr == int(year):
                    _init_idx = _i
                    break

            # ── Annual mode: compute FY aggregate as the static initial view ──
            # Rebuild initial trace with domain (frames omit domain intentionally)
            _f0 = _pie_frames[_init_idx].data[0]
            _init_data = [go.Pie(
                labels=_f0.labels, values=_f0.values,
                hole=0.55, sort=False, direction="clockwise", rotation=90,
                domain=dict(x=[0, 0.72], y=[0, 1]),
                marker=_f0.marker,
                textinfo="percent", textfont=dict(color="#374151", size=10),
                hovertemplate="<b>%{label}</b><br>$%{value:,.0f}M &nbsp;%{percent}<extra></extra>",
            )]
            _init_anns = list(_pie_frames[_init_idx].layout.annotations or [])
            _cx, _cy = 0.36, 0.5
            if _is_annual:
                if has_quarterly_segments:
                    _fy_raw = segments_quarterly_all[
                        (segments_quarterly_all["company"] == canonical_company)
                        & (segments_quarterly_all["year"] == int(year))
                    ]
                    _prev_fy_raw = segments_quarterly_all[
                        (segments_quarterly_all["company"] == canonical_company)
                        & (segments_quarterly_all["year"] == int(year) - 1)
                    ]
                    if not _fy_raw.empty:
                        _fy_df = _agg_period_df(_fy_raw)
                        _fy_fl = _fy_df["segment"].tolist()
                        _fy_fv = _fy_df["revenue"].fillna(0).tolist()
                        _fy_fc = [segment_colors.get(l, "#999999") for l in _fy_fl]
                        _prev_fy = _agg_period_df(_prev_fy_raw) if not _prev_fy_raw.empty else pd.DataFrame()
                        _prev_fy_map = dict(zip(_prev_fy["segment"], _prev_fy["revenue"])) if not _prev_fy.empty else {}
                        _fy_yoy = _compute_yoy(_fy_fl, _fy_fv, _prev_fy_map)
                        _fy_period_label = f"FY {int(year)}"
                        _init_anns = _donut_annotations(_fy_fl, _fy_fv, _fy_fc, _fy_yoy, _fy_period_label)
                        _init_data = [go.Pie(
                            labels=_fy_fl,
                            values=[max(v, 0) for v in _fy_fv],
                            hole=0.55, sort=False, direction="clockwise", rotation=90,
                            domain=dict(x=[0, 0.72], y=[0, 1]),
                            marker=dict(colors=_fy_fc, line=dict(color="rgba(0,0,0,0.18)", width=1)),
                            textinfo="percent",
                            textfont=dict(color="#374151", size=10),
                            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}M &nbsp;%{percent}<extra></extra>",
                        )]
                else:
                    # Annual-only company: relabel center annotation to FY format
                    _fy_period_label = f"FY {int(year)}"
                    if _init_anns:
                        _init_anns[-1] = dict(
                            x=_cx, y=_cy - 0.07, xref="paper", yref="paper",
                            text=f"<b>{_fy_period_label}</b>",
                            showarrow=False,
                            font=dict(size=11, color="#8b949e", family="Montserrat, sans-serif"),
                            align="center", bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)",
                        )

            _logo_src = f"data:image/png;base64,{logo_base64}" if logo_base64 else ""
            _layout_images = []
            if _logo_src:
                _layout_images.append(dict(
                    source=_logo_src, xref="paper", yref="paper",
                    x=0.36, y=0.5, sizex=0.22, sizey=0.22,
                    xanchor="center", yanchor="middle", layer="above",
                ))

            _slider_steps = [
                {
                    "args": [
                        [f.name],
                        {
                            "frame": {"duration": 400, "redraw": True},
                            "mode": "immediate",
                            "transition": {"duration": 300, "easing": "cubic-in-out"},
                        },
                    ],
                    "label": f.name,
                    "method": "animate",
                }
                for f in _pie_frames
            ]

            _pie_anim_fig = go.Figure(
                data=_init_data,
                frames=_pie_frames,
                layout=go.Layout(
                    height=640,
                    annotations=_init_anns,
                    images=_layout_images,
                    legend=dict(
                        orientation="v",
                        x=1.02, y=0.5, yanchor="middle",
                        bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#374151", size=11),
                        title=dict(text="Segments", font=dict(color="#374151", size=11)),
                    ),
                    margin=dict(l=140, r=200, t=80, b=120),
                    updatemenus=[{
                        "type": "buttons", "showactive": False, "direction": "left",
                        "x": 0.0, "y": -0.06, "xanchor": "left", "yanchor": "top",
                        "buttons": [
                            {
                                "label": "▶",
                                "method": "animate",
                                "args": [None, {"frame": {"duration": 900, "redraw": True},
                                                "fromcurrent": True,
                                                "transition": {"duration": 600, "easing": "cubic-in-out"}}],
                            },
                            {
                                "label": "⏸",
                                "method": "animate",
                                "args": [[None], {"frame": {"duration": 0, "redraw": False},
                                                  "mode": "immediate", "transition": {"duration": 0}}],
                            },
                        ],
                        "font": {"size": 18, "color": "#e6edf3"},
                        "bgcolor": "rgba(255,255,255,0.08)",
                        "bordercolor": "rgba(255,255,255,0.18)",
                        "borderwidth": 1,
                        "pad": {"l": 10, "r": 10, "t": 5, "b": 5},
                    }],
                    sliders=[{
                        "active": _init_idx,
                        "transition": {"duration": 0},
                        "currentvalue": {
                            "prefix": "Period: ", "visible": True, "xanchor": "left",
                            "font": {"size": 13, "color": "#e6edf3", "family": "Montserrat, sans-serif"},
                        },
                        "pad": {"b": 10, "t": 50},
                        "len": 0.82, "x": 0.18, "y": 0,
                        "steps": _slider_steps,
                        "font": {"color": "#cccccc", "size": 9},
                        "bgcolor": "rgba(255,255,255,0.08)",
                        "bordercolor": "rgba(255,255,255,0.15)",
                        "activebgcolor": "#2563eb",
                        "tickcolor": "rgba(255,255,255,0.25)",
                        "ticklen": 5, "minorticklen": 3,
                    }],
                ),
            )
            render_plotly(_pie_anim_fig)

            # Employee count footnote below donut
            try:
                _emp_val = data_processor.get_employee_count(canonical_company, int(year))
                _emp_yr_disp = int(year)
                if _emp_val is None:
                    # Try most recent available year for this company
                    _emp_df_fb = data_processor.df_employees
                    if _emp_df_fb is not None and not _emp_df_fb.empty:
                        _emp_co_fb = _emp_df_fb[_emp_df_fb["company"] == canonical_company]
                        if not _emp_co_fb.empty:
                            _emp_yr_disp = int(_emp_co_fb.sort_values("year")["year"].iloc[-1])
                            _emp_val = data_processor.get_employee_count(canonical_company, _emp_yr_disp)
                if _emp_val is not None:
                    _emp_val_n = pd.to_numeric(_emp_val, errors="coerce")
                    if pd.notna(_emp_val_n) and _emp_val_n > 0:
                        _emp_fmt = (
                            f"{_emp_val_n/1000:.0f}K" if _emp_val_n >= 1000 else str(int(_emp_val_n))
                        )
                        st.markdown(
                            f"<div style='text-align:center;color:#8b949e;font-size:0.82rem;"
                            f"margin-top:-8px;padding-bottom:8px;'>"
                            f"\U0001f465 <b style='color:#c9d1d9;'>{_emp_fmt}</b> employees ({_emp_yr_disp})</div>",
                            unsafe_allow_html=True,
                        )
            except Exception:
                pass

    # ── Segment year range (placed near Segment Composition) ──────────────
    segment_controls = st.columns([7, 3])
    with segment_controls[1]:
        st.markdown(
            """
            <div class="segment-range-label">
                <span>Segment year range</span>
                <span class="segment-range-info" data-tooltip="Select one year or a range to sum segment revenue across years. Use this to compare how the mix changes over time.">i</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.slider(
            "",
            min_value=int(min_year),
            max_value=int(max_year),
            value=(int(segment_start), int(segment_end)),
            key=segment_range_key,
            label_visibility="collapsed",
        )


    # Segment evolution
    st.subheader("Segment Evolution")
    min_year = min(years)
    max_year = max(years)
    segment_range_options = ["All", "10", "5", "3", "1"]
    segment_controls_row = st.columns([2.2, 2.2, 2.2, 1.6])
    with segment_controls_row[0]:
        evolution_type = st.radio("Chart type", ["Bars", "Lines"], horizontal=True)
    with segment_controls_row[1]:
        value_mode = st.radio("View mode", ["Absolute", "% of total"], horizontal=True)
    with segment_controls_row[3]:
        # Prefer quarterly sheets (per-company) when available.
        if "segment_evolution_freq" not in st.session_state:
            st.session_state["segment_evolution_freq"] = "Quarterly" if has_quarterly_segments else "Yearly"
        segment_freq = st.radio(
            "Frequency",
            ["Yearly", "Quarterly"],
            horizontal=True,
            key="segment_evolution_freq",
        )

    df_segments = data_processor.df_segments
    segment_data_source = segments_quarterly_all if segment_freq == "Quarterly" else df_segments

    evolution_years = []
    if segment_data_source is not None and not segment_data_source.empty:
        try:
            evolution_years = (
                segment_data_source[segment_data_source["company"] == canonical_company]["year"]
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            )
        except Exception:
            evolution_years = []
    min_year = int(min(evolution_years)) if evolution_years else int(min(years))
    max_year = int(max(evolution_years)) if evolution_years else int(max(years))

    with segment_controls_row[2]:
        range_key = f"segment_evolution_range_{segment_freq.lower()}"
        selected_range = st.radio(
            "Years",
            options=segment_range_options,
            horizontal=True,
            index=0 if segment_freq == "Quarterly" else 2,
            key=range_key,
            label_visibility="visible",
        )
    if selected_range == "All":
        year_range = (int(min_year), int(max_year))
    else:
        span = int(selected_range)
        start_year = max(int(min_year), int(max_year) - (span - 1))
        year_range = (int(start_year), int(max_year))

    evolution_df = pd.DataFrame()
    if segment_data_source is not None and not segment_data_source.empty:
        evolution_df = segment_data_source[
            (segment_data_source["company"] == canonical_company)
            & (segment_data_source["year"] >= year_range[0])
            & (segment_data_source["year"] <= year_range[1])
        ]

    if evolution_df.empty:
        st.info("Segment evolution data is not available for the selected range.")
    else:
        evolution_df = evolution_df.copy()
        evolution_df["segment"] = evolution_df["segment"].apply(
            lambda s: normalize_segment_label(canonical_company, s)
        )
        evolution_df = evolution_df[
            evolution_df["segment"].notna()
            & (evolution_df["segment"] != "")
            & (evolution_df["segment"] != "Total Revenue")
        ]
        if segment_freq == "Quarterly":
            evolution_df = evolution_df.groupby(
                ["year", "quarter_num", "segment"], as_index=False
            )["revenue"].sum()
            evolution_df = evolution_df.sort_values(["year", "quarter_num"])
            evolution_df["period_label"] = (
                evolution_df["year"].astype(int).astype(str)
                + " Q"
                + evolution_df["quarter_num"].astype(int).astype(str)
            )
            period_order = evolution_df["period_label"].drop_duplicates().tolist()
            pivot = evolution_df.pivot(
                index="period_label", columns="segment", values="revenue"
            ).fillna(0)
            pivot = pivot.reindex(period_order)
        else:
            evolution_df = evolution_df.groupby(["year", "segment"], as_index=False)["revenue"].sum()
            pivot = evolution_df.pivot(index="year", columns="segment", values="revenue").fillna(0)
            pivot = pivot.sort_index()
            try:
                pivot.index = pivot.index.astype(int)
            except (TypeError, ValueError):
                pass

        if value_mode == "% of total":
            totals = pivot.sum(axis=1).replace(0, pd.NA)
            pivot = (pivot.div(totals, axis=0) * 100).fillna(0)

        time_label = "Year" if segment_freq == "Yearly" else "Quarter"
        change_label = "YoY" if segment_freq == "Yearly" else "QoQ"
        xaxis_is_year = segment_freq == "Yearly"
        evolution_colors = get_segment_color_map(segment_data_source, canonical_company)
        fig = go.Figure()
        hover_value = "%{y:.1f}%" if value_mode == "% of total" else "$%{y:,.0f}M"
        hover_template = (
            f"<b>%{{fullData.name}}</b>"
            f"<br><span style='color:#94a3b8'>{time_label}</span>  <b>%{{x}}</b>"
            f"<br><span style='color:#94a3b8'>Value</span>  <b>{hover_value}</b>"
            f"<br><span style='color:#94a3b8'>{change_label}</span>  <b>%{{customdata}}</b>"
            f"<extra></extra>"
        )
        for segment in pivot.columns:
            color = evolution_colors.get(segment, "#999999")
            if value_mode == "% of total":
                yoy_series = pivot[segment].diff()
                yoy_labels = [format_yoy_label(v, "pp") for v in yoy_series.tolist()]
            else:
                yoy_series = pivot[segment].pct_change() * 100
                yoy_labels = [format_yoy_label(v, "%") for v in yoy_series.tolist()]
            if evolution_type == "Bars":
                fig.add_bar(
                    x=pivot.index,
                    y=pivot[segment],
                    name=segment,
                    marker_color=color,
                    customdata=yoy_labels,
                    hovertemplate=hover_template,
                )
            else:
                fig.add_scatter(
                    x=pivot.index,
                    y=pivot[segment],
                    name=segment,
                    mode="lines+markers",
                    line=dict(color=color),
                    customdata=yoy_labels,
                    hovertemplate=hover_template,
                )

        if evolution_type == "Bars":
            fig.update_layout(barmode="stack")
        fig.update_layout(
            height=480,
            xaxis_title="Quarter" if segment_freq == "Quarterly" else "Year",
            yaxis_title="% of total" if value_mode == "% of total" else "Revenue (M)",
            legend_title_text="Segments",
            hovermode="closest",
            hoverlabel=HOVERLABEL_STYLE,
        )
        if segment_freq == "Quarterly":
            category_order, tickvals, ticktext = build_quarter_axis(pivot.index.tolist())
            fig.update_xaxes(
                type="category",
                categoryorder="array",
                categoryarray=category_order,
                tickmode="array",
                tickvals=tickvals,
                ticktext=ticktext,
            )
        render_plotly(fig, xaxis_is_year=xaxis_is_year)


    # ── Coinglass-style single-company performance heatmap ──────────────────
    st.markdown("<div class='metrics-section-spacer'></div>", unsafe_allow_html=True)
    st.divider()
    st.subheader(f"Performance Heatmap — {company}")
    _hm_period_label = (
        f"Q{selected_quarter.strip('Q')} {year}"
        if str(selected_quarter).upper().startswith("Q")
        else f"FY {year}"
    )
    st.markdown(
        f"<p style='color:#6b7280;font-size:13px;margin-top:-6px;'>"
        f"<b style='color:#374151;'>{_hm_period_label}</b> &nbsp;·&nbsp; "
        f"Value shown · Color = YoY change · 9 metrics · Stock tabs show price return %</p>",
        unsafe_allow_html=True,
    )

    _HM_METRICS = {
        "Revenue": "revenue",
        "Net Income": "net_income",
        "Operating Income": "operating_income",
        "Cost of Revenue": "cost_of_revenue",
        "R&D": "rd",
        "CapEx": "capex",
        "Total Assets": "total_assets",
        "Debt": "debt",
        "Cash Balance": "cash_balance",
    }
    _MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # ── Quarterly: absolute values per quarter, colored by YoY (same Q vs prior year Q) ──
    # {metric_label: {year: {qnum(1-4): float_or_None}}}
    _cg_q_vals = {}
    # {metric_label: {year: {qnum(1-4): yoy_pct_or_None}}}
    _cg_q_yoy = {}
    try:
        # Use load_quarterly_company_metrics — same source as the existing heatmap,
        # which has proper unit calibration against annual data (avoids raw-dollar scale bugs)
        _cg_qm_df = load_quarterly_company_metrics(
            data_processor.data_path, get_file_mtime(data_processor.data_path)
        )
        if _cg_qm_df is not None and not _cg_qm_df.empty:
            _cg_co_qm = _cg_qm_df[_cg_qm_df["company"] == canonical_company]
            for _ml, _mk in _HM_METRICS.items():
                _rows = _cg_co_qm[_cg_co_qm["metric_key"] == _mk]
                if _rows.empty:
                    continue
                _raw = {}
                for _, _r in _rows.iterrows():
                    _v = pd.to_numeric(_r.get("value"), errors="coerce")
                    if not pd.isna(_v):
                        _raw[(int(_r["year"]), int(_r["quarter_num"]))] = float(_v)
                _cg_q_vals[_ml] = {}
                _cg_q_yoy[_ml] = {}
                for (_yr, _qn), _v in _raw.items():
                    _cg_q_vals[_ml].setdefault(_yr, {})[_qn] = _v
                    _pv = _raw.get((_yr - 1, _qn))
                    _cg_q_yoy[_ml].setdefault(_yr, {})[_qn] = (
                        round((_v - _pv) / abs(_pv) * 100, 2) if _pv and abs(_pv) > 0 else None
                    )
    except Exception:
        pass

    # ── Annual: YoY % changes ──
    _cg_a = {}
    try:
        _amdf = data_processor.df_metrics
        if _amdf is not None and not _amdf.empty:
            _cg_co_a = _amdf[_amdf["company"] == canonical_company].copy()
            _cg_co_a["year"] = pd.to_numeric(_cg_co_a["year"], errors="coerce")
            _cg_co_a = _cg_co_a.dropna(subset=["year"]).sort_values("year")
            _ap = {}
            for _, _r in _cg_co_a.iterrows():
                _yr = int(_r["year"])
                for _ml, _mk in _HM_METRICS.items():
                    if _mk not in _cg_co_a.columns:
                        continue
                    _v = pd.to_numeric(_r.get(_mk), errors="coerce")
                    _cg_a.setdefault(_ml, {})
                    _pv = _ap.get(_ml)
                    if pd.isna(_v):
                        _cg_a[_ml][_yr] = None
                    elif _pv and abs(_pv) > 0:
                        _cg_a[_ml][_yr] = round((float(_v) - _pv) / abs(_pv) * 100, 2)
                    else:
                        _cg_a[_ml][_yr] = None
                    if not pd.isna(_v):
                        _ap[_ml] = float(_v)
    except Exception:
        pass

    # ── Segments quarterly: absolute $M values, colored by YoY ──
    # {segment_name: {year: {qnum: val_or_None}}}
    _cg_seg_vals = {}
    _cg_seg_yoy = {}
    _cg_seg_names = []
    try:
        if segments_quarterly_all is not None and not segments_quarterly_all.empty:
            _sq = segments_quarterly_all[
                segments_quarterly_all["company"] == canonical_company
            ].copy()
            _sq["segment"] = _sq["segment"].apply(
                lambda s: normalize_segment_label(canonical_company, s)
            )
            _sq = _sq[
                _sq["segment"].notna()
                & (_sq["segment"] != "")
                & (_sq["segment"] != "Total Revenue")
            ]
            if not _sq.empty:
                _sq["year"] = pd.to_numeric(_sq["year"], errors="coerce")
                _sq["quarter_num"] = pd.to_numeric(_sq["quarter_num"], errors="coerce")
                _sq["revenue"] = pd.to_numeric(_sq["revenue"], errors="coerce")
                _sq = _sq.dropna(subset=["year", "quarter_num", "revenue"])
                _cg_seg_names = sorted(_sq["segment"].dropna().unique().tolist())
                for _seg in _cg_seg_names:
                    _sd = _sq[_sq["segment"] == _seg]
                    _raw_s = {}
                    for _, _r in _sd.iterrows():
                        _raw_s[(int(_r["year"]), int(_r["quarter_num"]))] = float(_r["revenue"])
                    _cg_seg_vals[_seg] = {}
                    _cg_seg_yoy[_seg] = {}
                    for (_yr, _qn), _v in _raw_s.items():
                        _cg_seg_vals[_seg].setdefault(_yr, {})[_qn] = _v
                        _pv = _raw_s.get((_yr - 1, _qn))
                        _cg_seg_yoy[_seg].setdefault(_yr, {})[_qn] = (
                            round((_v - _pv) / abs(_pv) * 100, 2) if _pv and abs(_pv) > 0 else None
                        )
    except Exception:
        pass

    # ── Stock period returns ──
    _cg_mon = {}
    _cg_wk = {}
    _cg_day = {}
    try:
        _cg_st = filter_stock_for_company(stock_df, canonical_company)
        if not _cg_st.empty:
            _ps = _cg_st.sort_values("date").set_index("date")["price"]
            _ps.index = pd.to_datetime(_ps.index, errors="coerce")
            _ps = _ps[_ps.index.notna()].sort_index()
            _ps = _ps[~_ps.index.duplicated(keep="last")]
            for _dt, _pct in (_ps.resample("ME").last().pct_change() * 100).items():
                _cg_mon.setdefault(_dt.year, {})[_MONTHS[_dt.month - 1]] = (
                    None if pd.isna(_pct) else round(float(_pct), 2)
                )
            _wk_cut = _ps.index.max() - pd.Timedelta(days=3 * 365)
            for _dt, _pct in (_ps[_ps.index >= _wk_cut].resample("W").last().pct_change() * 100).items():
                _cg_wk.setdefault(_dt.year, {})[f"W{_dt.isocalendar()[1]:02d}"] = (
                    None if pd.isna(_pct) else round(float(_pct), 2)
                )
            _dy_cut = _ps.index.max() - pd.Timedelta(days=365)
            for _dt, _pct in (_ps[_ps.index >= _dy_cut].pct_change() * 100).items():
                _cg_day.setdefault(_dt.strftime("%Y-%m"), {})[_dt.day] = (
                    None if pd.isna(_pct) else round(float(_pct), 2)
                )
    except Exception:
        pass

    # ── HTML cell builder helpers ──
    _TD = "padding:7px 6px;font-size:11px;border:none;border-bottom:1px solid #e5e7eb;"

    def _cg_hdr(text):
        return (
            f"<th style='background:#f3f4f6;color:#6b7280;text-align:center;"
            f"padding:9px 6px;font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;"
            f"border:none;border-bottom:1px solid #e5e7eb;white-space:nowrap;'>{text}</th>"
        )

    def _cg_time(text):
        return (
            f"<td style='background:transparent;color:#374151;text-align:center;"
            f"padding:7px 10px;font-size:12px;font-weight:600;border:none;"
            f"border-bottom:1px solid #e5e7eb;white-space:nowrap;'>{text}</td>"
        )

    def _cg_foot(text):
        return (
            f"<td style='background:#f3f4f6;color:#6b7280;text-align:center;"
            f"padding:7px 10px;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;"
            f"border:none;border-top:1px solid #e2e8f0;'>{text}</td>"
        )

    def _heatmap_text_color(normalized_val):
        """Return dark or white text based on colorscale position (0=min, 1=max).
        Yellow zone (near neutral 0.5) gets dark text for readability on pastel bg.
        """
        if 0.30 <= normalized_val <= 0.70:
            return "#0d1117"
        return "#ffffff"

    def _cg_val_cell(val, yoy, scale=1000.0):
        """Cell showing absolute $B value, background colored by YoY change."""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return (
                f"<td style='background:transparent;color:#9ca3af;text-align:center;{_TD}'>—</td>"
            )
        v_b = val / scale
        if abs(v_b) >= 100:
            fmt = f"${v_b:.0f}B"
        elif abs(v_b) >= 10:
            fmt = f"${v_b:.1f}B"
        elif abs(v_b) >= 1:
            fmt = f"${v_b:.2f}B"
        else:
            fmt = f"${v_b * 1000:.0f}M"
        if yoy is None:
            bg = "#f3f4f6"
            col = "#374151"
        elif yoy >= 0:
            alpha = min(0.85, yoy / 25)
            bg = f"rgba(22,199,132,{alpha:.2f})"
            col = _heatmap_text_color(0.5 + (alpha / 0.85) * 0.5)
        else:
            alpha = min(0.85, abs(yoy) / 25)
            bg = f"rgba(234,57,67,{alpha:.2f})"
            col = _heatmap_text_color(0.5 - (alpha / 0.85) * 0.5)
        yoy_str = f"<br><span style='font-size:9px;opacity:.75;'>{'+'if yoy and yoy>0 else ''}{yoy:.1f}%</span>" if yoy is not None else ""
        return (
            f"<td style='background:{bg};color:{col};text-align:center;{_TD}'>{fmt}{yoy_str}</td>"
        )

    def _cg_pct_cell(pct):
        """Cell for stock % return."""
        if pct is None:
            return f"<td style='background:transparent;color:#9ca3af;text-align:center;{_TD}'>—</td>"
        alpha = min(0.92, abs(pct) / 30)
        if pct >= 0:
            bg = f"rgba(22,199,132,{alpha:.2f})"
            col = _heatmap_text_color(0.5 + (alpha / 0.92) * 0.5)
        else:
            bg = f"rgba(234,57,67,{alpha:.2f})"
            col = _heatmap_text_color(0.5 - (alpha / 0.92) * 0.5)
        sign = "+" if pct > 0 else ""
        return f"<td style='background:{bg};color:{col};text-align:center;{_TD}'>{sign}{pct:.2f}%</td>"

    def _cg_stat_val(val_list, stat="avg", scale=1000.0):
        valid = [v for v in val_list if v is not None]
        if not valid:
            return f"<td style='background:#f3f4f6;color:#9ca3af;text-align:center;{_TD}'>—</td>"
        if stat == "avg":
            v = sum(valid) / len(valid)
        else:
            sv = sorted(valid); n = len(sv)
            v = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2
        v_b = v / scale
        if abs(v_b) >= 100:
            fmt = f"${v_b:.0f}B"
        elif abs(v_b) >= 10:
            fmt = f"${v_b:.1f}B"
        else:
            fmt = f"${v_b:.2f}B"
        return f"<td style='background:#f3f4f6;color:#6b7280;text-align:center;{_TD}'>{fmt}</td>"

    def _cg_stat_pct(pct_list, stat="avg"):
        valid = [v for v in pct_list if v is not None]
        if not valid:
            return f"<td style='background:#f3f4f6;color:#9ca3af;text-align:center;{_TD}'>—</td>"
        if stat == "avg":
            v = sum(valid) / len(valid)
        else:
            sv = sorted(valid); n = len(sv)
            v = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2
        sign = "+" if v > 0 else ""
        return f"<td style='background:#f3f4f6;color:#6b7280;text-align:center;{_TD}'>{sign}{v:.2f}%</td>"

    def _detect_scale(vals_dict):
        """Return divisor to convert raw value → $B. Handles raw $, $M, and $B sources."""
        all_vals = [
            v for yr_d in vals_dict.values()
            for v in (yr_d.values() if isinstance(yr_d, dict) else [yr_d])
            if v is not None
        ]
        if not all_vals:
            return 1000.0
        med = sorted([abs(v) for v in all_vals])[len(all_vals) // 2]
        if med >= 1e9:
            return 1e9    # raw dollars → $B
        if med >= 1e6:
            return 1e6    # raw millions → $B (unlikely but guard)
        if med > 500:
            return 1000.0  # $M → $B
        return 1.0         # already $B

    def _build_q_table(metric_label):
        vals = _cg_q_vals.get(metric_label, {})
        yoys = _cg_q_yoy.get(metric_label, {})
        if not vals:
            return "<p style='color:#6b7280;padding:20px;text-align:center;'>No quarterly data available for this metric.</p>"
        scale = _detect_scale(vals)
        years = sorted(vals.keys(), reverse=True)
        rows = [
            "<table style='width:100%;border-collapse:collapse;'>",
            "<thead><tr>" + _cg_hdr("Time") + "".join(_cg_hdr(f"Q{q}") for q in [1,2,3,4]) + "</tr></thead><tbody>",
        ]
        col_vals = {q: [] for q in [1, 2, 3, 4]}
        for yr in years:
            yd = vals.get(yr, {})
            yd_yoy = yoys.get(yr, {})
            rows.append("<tr>" + _cg_time(str(yr)))
            for q in [1, 2, 3, 4]:
                v = yd.get(q)
                if v is not None:
                    col_vals[q].append(v)
                rows.append(_cg_val_cell(v, yd_yoy.get(q), scale))
            rows.append("</tr>")
        rows.append("<tr>" + _cg_foot("Avg") + "".join(_cg_stat_val(col_vals[q], "avg", scale) for q in [1,2,3,4]) + "</tr>")
        rows.append("<tr>" + _cg_foot("Med") + "".join(_cg_stat_val(col_vals[q], "med", scale) for q in [1,2,3,4]) + "</tr>")
        rows.append("</tbody></table>")
        return "".join(rows)

    def _build_a_table(metric_label):
        data = _cg_a.get(metric_label, {})
        if not data:
            return "<p style='color:#6b7280;padding:20px;text-align:center;'>No annual data available.</p>"
        years = sorted(data.keys(), reverse=True)
        rows = [
            "<table style='width:260px;border-collapse:collapse;'>",
            "<thead><tr>" + _cg_hdr("Year") + _cg_hdr("YoY %") + "</tr></thead><tbody>",
        ]
        all_vals = []
        for yr in years:
            pct = data.get(yr)
            if pct is not None:
                all_vals.append(pct)
            rows.append("<tr>" + _cg_time(str(yr)) + _cg_pct_cell(pct) + "</tr>")
        rows.append("<tr>" + _cg_foot("Avg") + _cg_stat_pct(all_vals, "avg") + "</tr>")
        rows.append("<tr>" + _cg_foot("Med") + _cg_stat_pct(all_vals, "med") + "</tr>")
        rows.append("</tbody></table>")
        return "".join(rows)

    def _build_seg_table(seg_name):
        vals = _cg_seg_vals.get(seg_name, {})
        yoys = _cg_seg_yoy.get(seg_name, {})
        if not vals:
            return "<p style='color:#6b7280;padding:20px;text-align:center;'>No segment data available.</p>"
        scale = _detect_scale(vals)
        years = sorted(vals.keys(), reverse=True)
        rows = [
            "<table style='width:100%;border-collapse:collapse;'>",
            "<thead><tr>" + _cg_hdr("Time") + "".join(_cg_hdr(f"Q{q}") for q in [1,2,3,4]) + "</tr></thead><tbody>",
        ]
        col_vals = {q: [] for q in [1, 2, 3, 4]}
        for yr in years:
            yd = vals.get(yr, {})
            yd_yoy = yoys.get(yr, {})
            rows.append("<tr>" + _cg_time(str(yr)))
            for q in [1, 2, 3, 4]:
                v = yd.get(q)
                if v is not None:
                    col_vals[q].append(v)
                rows.append(_cg_val_cell(v, yd_yoy.get(q), scale))
            rows.append("</tr>")
        rows.append("<tr>" + _cg_foot("Avg") + "".join(_cg_stat_val(col_vals[q], "avg", scale) for q in [1,2,3,4]) + "</tr>")
        rows.append("<tr>" + _cg_foot("Med") + "".join(_cg_stat_val(col_vals[q], "med", scale) for q in [1,2,3,4]) + "</tr>")
        rows.append("</tbody></table>")
        return "".join(rows)

    def _build_stock_table(data_dict, col_keys, empty_msg):
        if not data_dict:
            return f"<p style='color:#6b7280;padding:20px;text-align:center;'>{empty_msg}</p>"
        rows_keys = sorted(data_dict.keys(), reverse=True)
        col_vals = {k: [] for k in col_keys}
        rows = [
            "<div style='overflow-x:auto;'>",
            "<table style='border-collapse:collapse;min-width:400px;width:100%;'>",
            "<thead><tr>" + _cg_hdr("Time") + "".join(_cg_hdr(str(k)) for k in col_keys) + "</tr></thead><tbody>",
        ]
        for rk in rows_keys:
            rd = data_dict.get(rk, {})
            rows.append("<tr>" + _cg_time(str(rk)))
            for ck in col_keys:
                pct = rd.get(ck)
                if pct is not None:
                    col_vals[ck].append(pct)
                rows.append(_cg_pct_cell(pct))
            rows.append("</tr>")
        rows.append("<tr>" + _cg_foot("Avg") + "".join(_cg_stat_pct(col_vals[k], "avg") for k in col_keys) + "</tr>")
        rows.append("<tr>" + _cg_foot("Med") + "".join(_cg_stat_pct(col_vals[k], "med") for k in col_keys) + "</tr>")
        rows.append("</tbody></table></div>")
        return "".join(rows)

    # Build all table HTML
    _metric_ids = [ml.lower().replace(" ", "_").replace("/", "_").replace("&", "") for ml in _HM_METRICS]

    _q_panes = ""
    _a_panes = ""
    _q_pills = ""
    _a_pills = ""
    for i, (ml, _) in enumerate(_HM_METRICS.items()):
        mid = _metric_ids[i]
        disp = "block" if i == 0 else "none"
        _q_panes += f"<div id='cg-q-{mid}' class='cg-mpane' style='display:{disp};'>{_build_q_table(ml)}</div>"
        _a_panes += f"<div id='cg-a-{mid}' class='cg-mpane' style='display:{disp};'>{_build_a_table(ml)}</div>"
        ac = " active" if i == 0 else ""
        _q_pills += f"<button class='cg-pill{ac}' onclick=\"cgMetric('q','{mid}',this)\">{ml}</button>"
        _a_pills += f"<button class='cg-pill{ac}' onclick=\"cgMetric('a','{mid}',this)\">{ml}</button>"

    _seg_panes = ""
    _seg_pills = ""
    if _cg_seg_names:
        for i, seg in enumerate(_cg_seg_names):
            sid = seg.lower().replace(" ", "_").replace("/", "_").replace("&", "").replace(".", "")[:30]
            disp = "block" if i == 0 else "none"
            _seg_panes += f"<div id='cg-s-{sid}' class='cg-mpane' style='display:{disp};'>{_build_seg_table(seg)}</div>"
            ac = " active" if i == 0 else ""
            _seg_pills += f"<button class='cg-pill{ac}' onclick=\"cgMetric('s','{sid}',this)\">{seg}</button>"
    else:
        _seg_panes = "<p style='color:#6b7280;padding:24px;text-align:center;'>No segment data available for this company.</p>"

    _all_wk_keys = sorted({wk for yd in _cg_wk.values() for wk in yd})
    _all_day_keys = list(range(1, 32))
    _mon_html = _build_stock_table({str(k): v for k, v in _cg_mon.items()}, _MONTHS, "No monthly stock data available.")
    _wk_html = _build_stock_table({str(k): v for k, v in _cg_wk.items()}, _all_wk_keys, "No weekly stock data available.")
    _day_html = _build_stock_table(_cg_day, _all_day_keys, "No daily stock data available.")

    _cg_q_years = max((len(_cg_q_vals.get(ml, {})) for ml in _HM_METRICS), default=0)
    _cg_height = max(540, 260 + _cg_q_years * 38)

    _cg_html = (
        """<!DOCTYPE html><html><head><meta charset='utf-8'>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
html,body{background:rgba(0,0,0,0);color:#374151;font-family:'DM Sans','Montserrat',sans-serif;}
.cg-wrap{background:rgba(0,0,0,0);border:none;overflow:hidden;}
.cg-tabs{display:flex;overflow-x:auto;border-bottom:1px solid #e2e8f0;background:transparent;}
.cg-tab{background:transparent;border:none;border-bottom:2px solid transparent;color:#6b7280;padding:10px 16px;font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap;letter-spacing:.04em;transition:all .2s;}
.cg-tab.active,.cg-tab:hover{color:#374151;border-bottom-color:#ff5b1f;}
.cg-pills{display:flex;flex-wrap:wrap;gap:6px;padding:10px 0 8px;}
.cg-pill{background:#f3f4f6;border:1px solid #e5e7eb;color:#6b7280;padding:5px 12px;border-radius:20px;font-size:11px;cursor:pointer;transition:all .2s;font-family:inherit;white-space:nowrap;}
.cg-pill.active,.cg-pill:hover{background:#ff5b1f;border-color:#ff5b1f;color:#fff;}
.cg-note{padding:6px 0 2px;font-size:10px;color:#6b7280;letter-spacing:.05em;}
.cg-panel{display:none;}.cg-panel.active{display:block;}
.cg-body{padding:10px 0;}
</style></head><body><div class="cg-wrap">
<div class="cg-tabs">
  <button class="cg-tab active" onclick="cgTab('q',this)">Quarterly</button>
  <button class="cg-tab" onclick="cgTab('a',this)">Annual YoY%</button>
  <button class="cg-tab" onclick="cgTab('s',this)">Segments</button>
  <button class="cg-tab" onclick="cgTab('mon',this)">Monthly stock%</button>
  <button class="cg-tab" onclick="cgTab('wk',this)">Weekly stock%</button>
  <button class="cg-tab" onclick="cgTab('day',this)">Daily stock%</button>
</div>
<div id="cg-pq" class="cg-panel active">
  <div class="cg-pills">"""
        + _q_pills
        + """</div>
  <div class="cg-note">Value in $B &nbsp;|&nbsp; Cell color = YoY change (same quarter, prior year)</div>
  <div class="cg-body">"""
        + _q_panes
        + """</div></div>
<div id="cg-pa" class="cg-panel">
  <div class="cg-pills">"""
        + _a_pills
        + """</div>
  <div class="cg-note">Annual YoY % change</div>
  <div class="cg-body">"""
        + _a_panes
        + """</div></div>
<div id="cg-ps" class="cg-panel">
  <div class="cg-pills">"""
        + _seg_pills
        + """</div>
  <div class="cg-note">Segment revenue in $B &nbsp;|&nbsp; Cell color = YoY change</div>
  <div class="cg-body">"""
        + _seg_panes
        + """</div></div>
<div id="cg-pmon" class="cg-panel">
  <div class="cg-note">Stock price — month-over-month % return</div>
  <div class="cg-body">"""
        + _mon_html
        + """</div></div>
<div id="cg-pwk" class="cg-panel">
  <div class="cg-note">Stock price — week-over-week % return (last 3 years)</div>
  <div class="cg-body">"""
        + _wk_html
        + """</div></div>
<div id="cg-pday" class="cg-panel">
  <div class="cg-note">Stock price — day-over-day % return (last 12 months)</div>
  <div class="cg-body">"""
        + _day_html
        + """</div></div>
</div>
<script>
var TABS={q:'cg-pq',a:'cg-pa',s:'cg-ps',mon:'cg-pmon',wk:'cg-pwk',day:'cg-pday'};
function cgTab(id,btn){
  document.querySelectorAll('.cg-tab').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  Object.keys(TABS).forEach(function(k){
    var p=document.getElementById(TABS[k]);
    if(p)p.classList.toggle('active',k===id);
  });
}
function cgMetric(tab,mid,btn){
  var panel=document.getElementById(TABS[tab]);
  if(!panel)return;
  panel.querySelectorAll('.cg-pill').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  panel.querySelectorAll('.cg-mpane').forEach(function(p){p.style.display='none';});
  var pane=document.getElementById('cg-'+tab+'-'+mid);
  if(pane)pane.style.display='block';
}
</script>
</body></html>"""
    )
    components.html(_cg_html, height=_cg_height, scrolling=False)


    # Transcript Intelligence removed — now in Overview Narrative & Sentiment


if __name__ == '__main__' or True:
    main()
