import base64
import html
import io
import logging
import os
import re
import uuid
from datetime import datetime

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

# Page config must be the first Streamlit command
st.set_page_config(page_title="Earnings", page_icon="E", layout="wide")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

check_password()
st.markdown(get_page_style(), unsafe_allow_html=True)
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

    h1 {
        margin-top: 0.2rem;
        margin-bottom: 0.75rem;
    }

    hr {
        margin: 0.75rem 0;
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
        filter: blur(18px);
        transform: scale(1.08);
        opacity: 0.85;
        z-index: 0;
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
	        --stock-safe-right: 280px;
	        --stock-safe-bottom: 150px;
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

    .earnings-hero-panel .kpi-card {
        background: rgba(15, 23, 42, 0.55);
        border: 1px solid rgba(248, 250, 252, 0.25);
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.18);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        opacity: 0;
        transform: translateY(6px);
        transition: opacity 0.6s ease, transform 0.6s ease;
    }

    .earnings-hero-panel .kpi-card.kpi-show {
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
        color: #ffffff;
        box-shadow: 0 10px 22px rgba(15, 23, 42, 0.18);
        min-height: 120px;
        position: relative;
        overflow: hidden;
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
            grid-template-columns: 1fr;
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
            right: 0.9rem;
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
    bgcolor="rgba(255, 255, 255, 0.98)",
    bordercolor="rgba(0, 115, 255, 0.35)",
    font=dict(family="Montserrat, sans-serif", size=12, color="#0f172a"),
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

def render_plotly(fig, xaxis_is_year=False):
    fig.update_layout(
        font=dict(family="Montserrat, sans-serif", color="#111827"),
        dragmode=False,
    )
    if xaxis_is_year:
        fig.update_xaxes(dtick=1, tickformat="d")
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

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
    "Alphabet": "attached_assets/10.png",
    "Google": "attached_assets/10.png",
    "Netflix": "attached_assets/9.png",
    "Meta": "attached_assets/12.png",
    "Meta Platforms": "attached_assets/12.png",
    "Amazon": "attached_assets/Amazon_icon.png",
    "Disney": "attached_assets/icons8-logo-disney-240.png",
    "Roku": "attached_assets/rokudef.png",
    "Spotify": "attached_assets/11.png",
    "Comcast": "attached_assets/6.png",
    "Paramount": "attached_assets/Paramount.png",
    "Paramount Global": "attached_assets/Paramount.png",
    "Warner Bros Discovery": "attached_assets/adadad.png",
    "Warner Bros. Discovery": "attached_assets/adadad.png",
}

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
def load_stock_data(excel_path):
    """Load stock data only when needed."""
    if not excel_path:
        return pd.DataFrame()
    try:
        def _read_stock_sheet(sheet_name, usecols=None):
            df = pd.read_excel(excel_path, sheet_name=sheet_name, usecols=usecols)
            df.columns = [str(c).strip().lower() for c in df.columns]
            return df

        try:
            df = _read_stock_sheet("Stocks & Crypto", usecols=["date", "price", "asset", "tag"])
        except Exception:
            sheet = None
            try:
                xl = pd.ExcelFile(excel_path)
                for name in xl.sheet_names:
                    lowered = name.lower()
                    if "stock" in lowered or "crypto" in lowered:
                        sheet = name
                        break
            except Exception:
                sheet = None
            if not sheet:
                raise
            df = _read_stock_sheet(sheet, usecols=None)

        if "date" not in df.columns:
            for alt in ("datetime", "timestamp"):
                if alt in df.columns:
                    df = df.rename(columns={alt: "date"})
                    break
        if "price" not in df.columns:
            for alt in ("close", "close price", "closing price", "adj close", "adj_close"):
                if alt in df.columns:
                    df = df.rename(columns={alt: "price"})
                    break
        if "asset" not in df.columns:
            for alt in ("name", "company", "symbol", "ticker"):
                if alt in df.columns:
                    df = df.rename(columns={alt: "asset"})
                    break
        if "tag" not in df.columns:
            df["tag"] = ""
        required = {"date", "price", "asset", "tag"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in stock sheet: {sorted(missing)}")
        df = df[["date", "price", "asset", "tag"]]
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        return df.dropna(subset=["date", "price"])
    except Exception as exc:
        logger.warning("Stock data load failed: %s", exc)
        return pd.DataFrame()


@st.cache_data
def load_m2_data(excel_path):
    """Load M2 macro data from the Excel source."""
    if not excel_path:
        return pd.DataFrame()
    try:
        df = pd.read_excel(excel_path, sheet_name="M2_values", usecols=["USD observation_date", "WM2NS"])
        df = df.rename(columns={"USD observation_date": "date", "WM2NS": "value"})
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
        return df
    except Exception as exc:
        logger.warning("Company insights load failed: %s", exc)
        return pd.DataFrame()


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
        if "Gran" in sheet:
            continue
        try:
            df = pd.read_excel(xls, sheet_name=sheet)
        except Exception as exc:
            logger.warning("Quarterly segments read failed for %s: %s", sheet, exc)
            continue
        if df is None or df.empty:
            continue
        company_name = sheet.replace("Quarterly Segments", "").strip()
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
        frames.append(df[["company", "quarter", "year", "quarter_num", "segment", "revenue"]])
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@st.cache_data(show_spinner=False)
def load_quarterly_company_metrics(excel_path, file_mtime=0):
    if not excel_path:
        return pd.DataFrame()
    candidate_sheets = [
        # Canonical sheet name (may be truncated by Excel's 31-char sheet limit).
        "Company_Quarterly_segments_",
        # Legacy name used in earlier versions (if present).
        "Quarterly_Company_metrics_earnings_values",
    ]
    try:
        xls = pd.ExcelFile(excel_path)
    except Exception as exc:
        logger.warning("Quarterly company metrics load failed: %s", exc)
        return pd.DataFrame()
    sheet_name = None
    for s in xls.sheet_names:
        if s == "Quarterly_Company_metrics_earnings_values":
            sheet_name = s
            break
        if s.startswith("Company_Quarterly_segments_"):
            sheet_name = s
            break
    if not sheet_name:
        return pd.DataFrame()
    try:
        df = pd.read_excel(xls, sheet_name=sheet_name)
    except Exception as exc:
        logger.warning("Quarterly company metrics read failed: %s", exc)
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    df.columns = [str(c).strip() for c in df.columns]
    lowered = {str(c).strip().lower(): c for c in df.columns}
    # The quarterly KPI sheet is stored per ticker+year with repeated rows (Q1..Q4)
    # but without an explicit quarter column. Infer quarters by row order within (ticker, year).
    ticker_col = lowered.get("ticker") or lowered.get("symbol")
    year_col = lowered.get("year")
    if not ticker_col or not year_col:
        return pd.DataFrame()

    df = df.rename(columns={ticker_col: "ticker", year_col: "year"})
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["ticker", "year"])
    df["year"] = df["year"].astype(int)

    # Map tickers to canonical company names used throughout the app.
    ticker_to_company = {}
    for company_name, tickers in COMPANY_TICKERS.items():
        for t in tickers:
            ticker_to_company[str(t).upper()] = normalize_company(company_name)
    df["company"] = df["ticker"].map(ticker_to_company).fillna(df["ticker"])

    # Preserve original order to infer quarters.
    df["_row"] = np.arange(len(df))
    df = df.sort_values(["ticker", "year", "_row"])

    def _select_quarter_rows(group: pd.DataFrame) -> pd.DataFrame:
        g = group.sort_values("_row").copy()
        if len(g) <= 4:
            return g
        # Heuristic: if the sheet includes an annual total row, it typically has the max revenue
        # and is much larger than the other rows. Drop that row before selecting quarters.
        rev_col = next((c for c in g.columns if str(c).strip().lower() == "revenue"), None)
        if rev_col:
            rev = pd.to_numeric(g[rev_col], errors="coerce")
            g["_rev_num"] = rev
            if rev.notna().any():
                max_rev = float(rev.max())
                unique_vals = sorted(set(rev.dropna().astype(float).tolist()))
                second_max = unique_vals[-2] if len(unique_vals) >= 2 else None
                # Only drop max rows when they look like annual totals (significantly larger).
                if second_max and second_max > 0 and max_rev >= 1.5 * second_max:
                    cutoff = 1.5 * second_max
                    g = g[g["_rev_num"] < cutoff].copy()
        if len(g) > 4:
            g = g.tail(4).copy()
        return g.drop(columns=[c for c in ["_rev_num"] if c in g.columns], errors="ignore")

    df = df.groupby(["ticker", "year"], group_keys=False).apply(_select_quarter_rows)
    df = df.sort_values(["ticker", "year", "_row"])
    df["quarter_num"] = df.groupby(["ticker", "year"]).cumcount() + 1

    metric_cols = {}
    # Explicit mapping for the quarterly sheet headers.
    preferred = {
        "revenue": lowered.get("revenue"),
        "cost_of_revenue": lowered.get("cost of revenue") or lowered.get("cost_of_revenue"),
        "operating_income": lowered.get("operating income") or lowered.get("operating_income"),
        "net_income": lowered.get("net income") or lowered.get("net_income"),
        "capex": lowered.get("capex"),
        "rd": lowered.get("r&d") or lowered.get("rd") or lowered.get("r_d"),
        "total_assets": lowered.get("total assets") or lowered.get("total_assets"),
        "cash_balance": lowered.get("cash balance") or lowered.get("cash_balance"),
        "debt": lowered.get("debt"),
        # market_cap is not present in the quarterly KPI sheet.
    }
    for key, col in preferred.items():
        if col and col in df.columns:
            metric_cols[key] = col

    if not metric_cols:
        return pd.DataFrame()

    records = []
    for metric_key, col in metric_cols.items():
        values = pd.to_numeric(df[col], errors="coerce")
        temp = df[["company", "year", "quarter_num"]].copy()
        temp["metric_key"] = metric_key
        temp["value"] = values
        records.append(temp)
    result = pd.concat(records, ignore_index=True)
    result = result.dropna(subset=["value"])
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


def format_metric_value(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    return format_number(value)


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
def build_quarterly_metric_heatmap_data(quarterly_df, companies, metric_key, year_start, year_end):
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


st.title("Earnings")
data_processor = get_data_processor()

companies = data_processor.get_companies()
if not companies:
    st.error("No company data available.")
    st.stop()

query_params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
query_company = None
if query_params:
    query_company = query_params.get("company")
    if isinstance(query_company, list):
        query_company = query_company[0] if query_company else None
if not query_company:
    query_company = st.session_state.get("prefill_company")

default_index = 0
if query_company:
    for idx, name in enumerate(companies):
        if name.lower() == str(query_company).lower():
            default_index = idx
            break

company = st.selectbox("Select Company", companies, index=default_index)
years = data_processor.get_available_years(company)
if not years:
    st.error("No years available for this company.")
    st.stop()

years = sorted(years)
year = st.selectbox("Select Year", years, index=len(years) - 1)
metrics = data_processor.get_metrics(company, year)
if not metrics:
    st.error("No data available for the selected company/year.")
    st.stop()

prev_company = st.session_state.get("kpi_anim_company")
prev_year = st.session_state.get("kpi_anim_year")
if prev_company != company or prev_year != year or "kpi_anim_key" not in st.session_state:
    st.session_state["kpi_anim_key"] = uuid.uuid4().hex[:8]
    st.session_state["kpi_anim_company"] = company
    st.session_state["kpi_anim_year"] = year
kpi_anim_key = st.session_state["kpi_anim_key"]
kpi_anim_start_delay = 1.0
kpi_anim_step = 0.2

logo_path = COMPANY_LOGOS.get(company, COMPANY_LOGOS.get(normalize_company(company)))
logo_base64 = get_logo_base64(logo_path, get_file_mtime(logo_path))
logo_html = ""
if logo_base64:
    logo_html = f"<img src='data:image/png;base64,{logo_base64}' class='company-logo' alt='{company} logo'>"

stock_df = load_stock_data(data_processor.data_path)
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
        if not ticker_display:
            for candidate in (latest_row.get("tag"), latest_row.get("asset")):
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
            <span class="company-year">{year}</span>
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
hero_image_html = (
    (
        "<img "
        f"src='data:{hero_mime};base64,{hero_base64}' "
        f"alt='{company} hero image' "
        ">"
    )
    if hero_base64
    else ""
)
hero_classes = "earnings-hero"
if hero_stock_html:
    hero_classes += " has-stock"
st.markdown(company_header_html, unsafe_allow_html=True)
st.markdown(
    (
        f"<div class='{hero_classes}' id='earnings-hero-{kpi_anim_key}' "
        f"style=\"{hero_style}\">"
        f"{hero_image_html}"
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
	        const hero = doc.getElementById("earnings-hero-{kpi_anim_key}");
	        const panel = doc.getElementById("kpi-panel-{kpi_anim_key}");
	        if (!hero || !panel) return;

        hero.classList.remove("is-collapsed");
        const cards = panel.querySelectorAll(".kpi-card");
        cards.forEach((card) => card.classList.remove("kpi-show"));
        const img = hero.querySelector("img");
	        const delayMs = {int(kpi_anim_start_delay * 1000)};
	        const stepMs = {int(kpi_anim_step * 1000)};
	        const minH = 460;
	        const maxH = 760;
	        const ratio = 0.45;

        if (window.parent.__kpiAnimTimers) {{
            window.parent.__kpiAnimTimers.forEach((t) => window.parent.clearTimeout(t));
        }}
        window.parent.__kpiAnimTimers = [];

	        const computeHeights = function() {{
	            const width = hero.getBoundingClientRect().width || hero.clientWidth || 1;
	            const finalHeight = Math.min(maxH, Math.max(minH, width * ratio));
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

	            // Prevent runaway heights on smaller/zoomed viewports (e.g. laptop screens),
	            // but keep the large-display behavior by capping to a % of viewport height.
	            const vhCap = Math.min(window.innerHeight * 0.92, 980);
	            introHeight = Math.max(finalHeight, Math.min(introHeight, vhCap));
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
    }})();
    </script>
    """,
    height=0,
)

st.markdown("<hr class='thin-section-divider' />", unsafe_allow_html=True)

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
        lambda s: normalize_segment_label(company, s)
    )
    segment_insights_filtered["segment"] = segment_insights_filtered["segment"].astype(str).str.strip()
    segment_insights_filtered = segment_insights_filtered[
        (segment_insights_filtered["company"] == canonical_company)
        & (segment_insights_filtered["segment"].notna())
        & (segment_insights_filtered["segment"] != "")
        & (segment_insights_filtered["insight"].notna())
    ]

segment_insight_map = {}
if not segment_insights_filtered.empty:
    desired_insight_year = int(segment_end)
    segment_to_group = {k: v for k, v in segment_insights_filtered.groupby("segment")}
    if segment_labels:
        ordered_segments = [s for s in segment_labels if s in segment_to_group]
    else:
        ordered_segments = sorted(segment_to_group.keys())

    for segment_name in ordered_segments:
        segment_name = str(segment_name).strip()
        group = segment_to_group.get(segment_name)
        if group is None or group.empty:
            continue
        group = group.copy()
        group["year"] = pd.to_numeric(group["year"], errors="coerce")
        group_in_range = group[
            group["year"].notna()
            & (group["year"] >= int(segment_start))
            & (group["year"] <= int(segment_end))
        ]

        group_year = group_in_range[group_in_range["year"] == desired_insight_year]
        if group_year.empty:
            if not group_in_range.empty:
                best_year = int(group_in_range["year"].max())
                group_year = group_in_range[group_in_range["year"] == best_year]
            else:
                group_le = group[group["year"].notna() & (group["year"] <= desired_insight_year)]
                if not group_le.empty:
                    best_year = int(group_le["year"].max())
                    group_year = group_le[group_le["year"] == best_year]
                else:
                    year_values = group["year"].dropna()
                    if not year_values.empty:
                        best_year = int(year_values.max())
                        group_year = group[group["year"] == best_year]
                    else:
                        group_year = group

        insights = []
        for item in group_year["insight"].tolist():
            for part in split_insight_text(item):
                if part and str(part).strip():
                    insights.append(html.escape(str(part).strip()))
        if not insights:
            continue
        insight_items = "".join(f"<li>{item}</li>" for item in insights)
        segment_color = segment_colors.get(segment_name)
        if not segment_color:
            segment_color = match_segment_color(canonical_company, segment_name)
        if not segment_color:
            segment_color = COMPANY_COLORS.get(canonical_company, "#111827")
        segment_insight_map[segment_name] = (
            f"<div class=\"segment-insight-card\" style=\"background: {segment_color}; width: 100%;\">"
            f"<div class=\"segment-insight-title\">{html.escape(segment_name)}</div>"
            f"<ul class=\"segment-insight-list\">{insight_items}</ul>"
            "</div>"
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
                        `<div class="segment-insight-card" style="background: ${{bg}}; width: 100%; opacity: 0.92;">` +
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
    if segment_labels and segment_values and sum(v for v in segment_values if v > 0) > 0:
        pie_colors = [segment_colors.get(label, "#999999") for label in segment_labels]
        hover_font_colors = [pick_contrast_color(color) for color in pie_colors]
        pie_fig = go.Figure(
            data=[
                go.Pie(
                    labels=segment_labels,
                    values=[max(v, 0) for v in segment_values],
                    hole=0.55,
                    sort=False,
                    marker=dict(colors=pie_colors),
                    textinfo="percent",
                    customdata=segment_yoy_labels,
                    hoverlabel=dict(
                        bgcolor=pie_colors,
                        bordercolor=pie_colors,
                        font=dict(
                            family="Montserrat, sans-serif",
                            size=12,
                            color=hover_font_colors,
                        ),
                        align="left",
                        namelength=-1,
                    ),
                    hovertemplate=(
                        "<b>%{label}</b><br>Value: $%{value:,.0f}M<br>"
                        "Share: %{percent}<br>YoY: %{customdata}<extra></extra>"
                    ),
                )
            ]
        )
        employee_count = data_processor.get_employee_count(company, year)
        if employee_count is None or pd.isna(employee_count):
            employee_label = "Employees: —"
        else:
            employee_label = f"Employees: {employee_count:,.0f}"
        center_text = f"{year}<br>{employee_label}"
        logo_src = ""
        if logo_base64:
            logo_src = f"data:image/png;base64,{logo_base64}"
        center_annotations = [
            dict(
                text=center_text,
                x=0.5,
                y=0.32,
                font=dict(size=14, family="Montserrat, sans-serif", color="#111827"),
                showarrow=False,
            )
        ]
        layout_images = []
        if logo_src:
            layout_images.append(
                dict(
                    source=logo_src,
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    sizex=0.22,
                    sizey=0.22,
                    xanchor="center",
                    yanchor="middle",
                    layer="above",
                )
            )
        pie_fig.update_layout(
            height=520,
            legend_title_text="Segments",
            legend=dict(orientation="v", x=1.02, y=0.5, yanchor="middle"),
            annotations=center_annotations,
            images=layout_images,
            margin=dict(l=20, r=120, t=20, b=20),
            uniformtext_minsize=10,
            uniformtext_mode="hide",
        )
        render_plotly(pie_fig)
    else:
        st.info("Segment composition is not available for this year.")

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

st.divider()

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
    if has_quarterly_segments and "segment_evolution_freq" not in st.session_state:
        st.session_state["segment_evolution_freq"] = "Quarterly"
    segment_freq = st.radio(
        "Frequency",
        ["Yearly", "Quarterly"],
        horizontal=True,
        key="segment_evolution_freq",
        index=1 if has_quarterly_segments else 0,
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
        f"<b>%{{fullData.name}}</b><br>{time_label}: %{{x}}<br>Value: {hover_value}"
        f"<br>{change_label}: %{{customdata}}<extra></extra>"
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

st.subheader("Insights")
company_insights_df = load_company_insights_text(data_processor.data_path)

company_insights_filtered = pd.DataFrame()
if company_insights_df is not None and not company_insights_df.empty:
    company_insights_filtered = company_insights_df.copy()
    company_insights_filtered["company"] = (
        company_insights_filtered["company"].astype(str).str.strip().apply(normalize_company)
    )
    company_insights_filtered["year"] = pd.to_numeric(
        company_insights_filtered["year"], errors="coerce"
    )
    company_insights_filtered = company_insights_filtered[
        (company_insights_filtered["company"] == canonical_company)
        & (company_insights_filtered["year"] == int(year))
        & (company_insights_filtered["insight"].notna())
    ]
    if "category" in company_insights_filtered.columns:
        company_insights_filtered["category"] = company_insights_filtered["category"].fillna("")

if company_insights_filtered.empty:
    st.info("Company insights are not available for the selected company and year.")
else:
    st.markdown("#### Company insights")
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

st.divider()

# Default to the last 5 years where possible.
default_start = max(int(min_year), int(max_year) - 4)

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
    min_value=int(min_year),
    max_value=int(max_year),
    value=(int(default_start), int(max_year)),
    key="metrics_year_range",
)

metric_toggle_row = st.columns([0.55, 0.25, 0.2])
with metric_toggle_row[1]:
    metrics_freq = st.radio(
        "Frequency",
        ["Yearly", "Quarterly"],
        horizontal=True,
        key="metrics_frequency",
    )
with metric_toggle_row[2]:
    show_metric_yoy = st.checkbox("Show YoY%", value=True, key="metrics_show_yoy")

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
                height=520,
                margin=dict(t=60, r=30, l=20, b=40),
            )
            if show_metric_yoy:
                hovertemplate = (
                    f"<b>%{{fullData.name}}</b><br>{metric_label}: $%{{y:,.0f}}M"
                    f"<br>{'Quarter' if metrics_freq == 'Quarterly' else 'Year'}: %{{x}}"
                    f"<br>{change_label}: %{{customdata[0]}}<extra></extra>"
                )
            else:
                hovertemplate = (
                    f"<b>%{{fullData.name}}</b><br>{metric_label}: $%{{y:,.0f}}M"
                    f"<br>{'Quarter' if metrics_freq == 'Quarterly' else 'Year'}: %{{x}}<extra></extra>"
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

st.markdown("<div class='metrics-section-spacer'></div>", unsafe_allow_html=True)
st.divider()

# Heatmap comparison layer
st.subheader("Heatmap Comparison")
st.markdown(
    "A fast visual scan across companies, segments, and prices over time. "
    "Darker cells indicate higher values within the selected view."
)

heatmap_row = st.columns([2.2, 2.2, 1.6, 1.6, 2.4])
with heatmap_row[0]:
    heatmap_mode = st.selectbox(
        "Heatmap data",
        ["Company Metrics", "Segments", "Stock Price"],
        index=0,
        key="heatmap_mode",
    )
with heatmap_row[1]:
    if heatmap_mode == "Company Metrics":
        heatmap_metrics = st.multiselect(
            "Metrics",
            list(AVAILABLE_METRICS.keys()),
            default=["Revenue"],
            key="heatmap_metrics",
        )
    elif heatmap_mode == "Segments":
        heatmap_metric = "Segment revenue"
        st.selectbox("Metric", ["Segment revenue"], index=0, key="heatmap_segment_metric")
    else:
        heatmap_metric = "Stock Price"
        st.selectbox("Metric", ["Stock price (close)"], index=0, key="heatmap_stock_metric")
with heatmap_row[2]:
    heatmap_basis = st.radio(
        "Heat basis",
        ["Value", "Change (%)"],
        horizontal=True,
        key="heatmap_basis",
    )
with heatmap_row[3]:
    if heatmap_mode == "Stock Price":
        freq_options = ["Yearly", "Quarterly", "Monthly", "Weekly", "Daily"]
    elif heatmap_mode == "Segments":
        freq_options = ["Quarterly"]
    else:
        freq_options = ["Yearly", "Quarterly"]
    heatmap_freq = st.radio(
        "Frequency",
        freq_options,
        horizontal=True,
        key=f"heatmap_freq_{heatmap_mode.replace(' ', '_').lower()}",
    )
with heatmap_row[4]:
    if heatmap_mode == "Segments":
        heatmap_company = st.selectbox(
            "Company",
            companies,
            index=companies.index(company) if company in companies else 0,
            key="heatmap_segment_company",
        )
    else:
        heatmap_company = None
        st.markdown("&nbsp;", unsafe_allow_html=True)

heatmap_company_list = companies
segment_filter = []
year_range = None
week_window = None

if heatmap_mode == "Company Metrics":
    metrics_df = data_processor.df_metrics
    quarterly_metrics_df = load_quarterly_company_metrics(
        data_processor.data_path, get_file_mtime(data_processor.data_path)
    )
    if heatmap_freq == "Quarterly" and quarterly_metrics_df is not None and not quarterly_metrics_df.empty:
        available_companies = sorted(quarterly_metrics_df["company"].dropna().unique().tolist())
    else:
        available_companies = sorted(metrics_df["company"].dropna().unique().tolist()) if metrics_df is not None else []
    if available_companies:
        default_companies = get_default_company_selection(available_companies, company)
        heatmap_company_list = st.multiselect(
            "Companies",
            options=available_companies,
            default=default_companies,
            key="heatmap_companies",
        )
    else:
        heatmap_company_list = companies

    metric_years = []
    if heatmap_freq == "Quarterly" and quarterly_metrics_df is not None and not quarterly_metrics_df.empty:
        metric_years = sorted(
            pd.to_numeric(quarterly_metrics_df["year"], errors="coerce")
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )
    elif metrics_df is not None and not metrics_df.empty:
        metric_years = sorted(
            pd.to_numeric(metrics_df["year"], errors="coerce")
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )
    if metric_years:
        span = 7 if len(metric_years) >= 7 else len(metric_years)
        if len(metric_years) == 1:
            only_year = int(metric_years[0])
            st.selectbox(
                "Year",
                [only_year],
                index=0,
                key="heatmap_metric_year_single",
            )
            year_range = (only_year, only_year)
        else:
            default_range = (metric_years[-span], metric_years[-1])
            year_range = st.slider(
                "Year range",
                min_value=int(metric_years[0]),
                max_value=int(metric_years[-1]),
                value=default_range,
                key="heatmap_metric_year_range",
            )

elif heatmap_mode == "Segments":
    segments_df = load_quarterly_segments(data_processor.data_path, get_file_mtime(data_processor.data_path))
    canonical_heatmap_company = normalize_company(heatmap_company)
    segment_options = get_company_segments(segments_df, canonical_heatmap_company)
    if segment_options:
        segment_filter = st.multiselect(
            "Segments",
            options=segment_options,
            default=segment_options,
            key="heatmap_segment_filter",
        )
    segment_years = []
    if segments_df is not None and not segments_df.empty:
        segment_years = sorted(
            pd.to_numeric(
                segments_df[segments_df["company"] == canonical_heatmap_company]["year"],
                errors="coerce",
            )
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )
    if segment_years:
        span = 7 if len(segment_years) >= 7 else len(segment_years)
        if len(segment_years) == 1:
            only_year = int(segment_years[0])
            st.selectbox(
                "Year",
                [only_year],
                index=0,
                key="heatmap_segment_year_single",
            )
            year_range = (only_year, only_year)
        else:
            default_range = (segment_years[-span], segment_years[-1])
            year_range = st.slider(
                "Year range",
                min_value=int(segment_years[0]),
                max_value=int(segment_years[-1]),
                value=default_range,
                key="heatmap_segment_year_range",
            )

else:
    stock_df = load_stock_data(data_processor.data_path)
    available_companies = companies
    default_companies = get_default_company_selection(available_companies, company)
    heatmap_company_list = st.multiselect(
        "Companies",
        options=available_companies,
        default=default_companies,
        key="heatmap_stock_companies",
    )
    if heatmap_freq == "Yearly":
        stock_years = []
        if stock_df is not None and not stock_df.empty:
            stock_years = sorted(stock_df["date"].dt.year.dropna().unique().tolist())
        if stock_years:
            span = 7 if len(stock_years) >= 7 else len(stock_years)
            default_range = (stock_years[-span], stock_years[-1])
            year_range = st.slider(
                "Year range",
                min_value=int(stock_years[0]),
                max_value=int(stock_years[-1]),
                value=default_range,
                key="heatmap_stock_year_range",
            )
    else:
        if heatmap_freq == "Daily":
            window_options = [60, 120, 252]
            window_label = "Day window"
        elif heatmap_freq == "Weekly":
            window_options = [26, 52, 104]
            window_label = "Week window"
        elif heatmap_freq == "Monthly":
            window_options = [24, 60, 120]
            window_label = "Month window"
        else:
            window_options = [12, 20, 40]
            window_label = "Quarter window"
        week_window = st.selectbox(
            window_label,
            window_options,
            index=1 if len(window_options) > 1 else 0,
            key="heatmap_stock_window",
        )

heatmap_df = pd.DataFrame()
heatmap_value_kind = "metric"
heatmap_metric_list = []

def render_heatmap_figure(heatmap_df, heatmap_value_kind, heatmap_freq, y_title):
    if heatmap_df is None or heatmap_df.empty:
        st.info("Heatmap data is not available for the current selection.")
        return
    heatmap_change_df = compute_heatmap_change(heatmap_df)
    if heatmap_basis == "Change (%)":
        heatmap_numeric = heatmap_change_df
    else:
        heatmap_numeric = heatmap_df
    normalized = normalize_heatmap(heatmap_numeric)

    if heatmap_value_kind == "stock":
        value_display = heatmap_df.applymap(format_stock_value)
    else:
        value_display = heatmap_df.applymap(format_metric_value)

    x_labels = [str(col) for col in heatmap_df.columns.tolist()]
    y_labels = heatmap_df.index.tolist()
    if heatmap_freq == "Weekly":
        x_title = "Week"
    elif heatmap_freq == "Daily":
        x_title = "Date"
    elif heatmap_freq == "Monthly":
        x_title = "Month"
    elif heatmap_freq == "Quarterly":
        x_title = "Quarter"
    else:
        x_title = "Year"
    if heatmap_freq == "Yearly":
        change_label = "YoY change"
    elif heatmap_freq == "Quarterly":
        change_label = "QoQ change"
    elif heatmap_freq == "Monthly":
        change_label = "MoM change"
    elif heatmap_freq == "Weekly":
        change_label = "WoW change"
    elif heatmap_freq == "Daily":
        change_label = "DoD change"
    else:
        change_label = "Change (%)"
    change_display = heatmap_change_df.applymap(format_change_value)
    value_text = value_display.to_numpy().tolist()
    change_text = change_display.to_numpy().tolist()
    hover_text = []
    for row_idx, row_label in enumerate(y_labels):
        row = []
        for col_idx, col_label in enumerate(x_labels):
            value_str = value_text[row_idx][col_idx]
            change_str = change_text[row_idx][col_idx]
            row.append(
                f"{y_title}: {row_label}<br>"
                f"{x_title}: {col_label}<br>"
                f"Value: {value_str}<br>"
                f"{change_label}: {change_str}"
            )
        hover_text.append(row)
    row_count = len(y_labels)
    heatmap_height = min(640, max(320, 36 * row_count + 120))

    heatmap_fig = go.Figure(
        data=go.Heatmap(
            z=normalized.to_numpy(),
            x=x_labels,
            y=y_labels,
            hoverinfo="text",
            hovertext=hover_text,
            colorscale=HEATMAP_COLORSCALE,
            zmin=0,
            zmax=1,
            xgap=1,
            ygap=1,
            showscale=False,
            hoverlabel=HOVERLABEL_STYLE,
        )
    )
    heatmap_fig.update_layout(
        height=heatmap_height,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis_title=x_title,
        yaxis_title=y_title,
        font=dict(family="Montserrat, sans-serif", size=12, color="#111827"),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
    )
    heatmap_fig.update_xaxes(showgrid=False, tickangle=0)
    heatmap_fig.update_yaxes(showgrid=False)
    render_plotly(heatmap_fig)

if heatmap_mode == "Company Metrics":
    heatmap_metric_list = heatmap_metrics or []
    if not heatmap_metric_list:
        st.info("Select at least one metric to display the heatmap.")
    elif year_range and heatmap_company_list:
        for metric_label in heatmap_metric_list:
            metric_key = AVAILABLE_METRICS.get(metric_label)
            if heatmap_freq == "Quarterly":
                metric_df = build_quarterly_metric_heatmap_data(
                    quarterly_metrics_df,
                    tuple(heatmap_company_list),
                    metric_key,
                    year_range[0],
                    year_range[1],
                )
                if metric_df is None or metric_df.empty:
                    st.info(f"Quarterly {metric_label} metrics are not available in the Excel yet.")
                    continue
            else:
                metric_df = build_metric_heatmap_data(
                    data_processor.df_metrics,
                    tuple(heatmap_company_list),
                    metric_key,
                    year_range[0],
                    year_range[1],
                )
            st.markdown(f"#### {metric_label}")
            render_heatmap_figure(metric_df, "metric", heatmap_freq, "Company")
elif heatmap_mode == "Segments":
    if year_range:
        heatmap_df = build_quarterly_segment_heatmap_data(
            segments_df,
            canonical_heatmap_company,
            year_range[0],
            year_range[1],
            tuple(segment_filter),
        )
    render_heatmap_figure(heatmap_df, "metric", heatmap_freq, "Segment")
else:
    heatmap_value_kind = "stock"
    if heatmap_freq == "Yearly" and year_range:
        heatmap_df = build_stock_heatmap_data(
            stock_df,
            tuple(heatmap_company_list),
            "Yearly",
            year_start=year_range[0],
            year_end=year_range[1],
        )
    elif heatmap_freq in {"Quarterly", "Monthly", "Weekly", "Daily"}:
        heatmap_df = build_stock_heatmap_data(
            stock_df,
            tuple(heatmap_company_list),
            heatmap_freq,
            period_limit=week_window,
        )
    render_heatmap_figure(heatmap_df, "stock", heatmap_freq, "Company")
