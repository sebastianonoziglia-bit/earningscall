"""
MiroFish-inspired Prediction Probability Cone.

Fan chart: historical prices → expanding cone (50/75/90% confidence intervals)
with optional Polymarket probability overlays.

Usage:
    from utils.probability_cone import render_probability_cone_section
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


_HOVERLABEL = dict(
    bgcolor="rgba(10,14,26,0.97)",
    bordercolor="rgba(99,179,237,0.45)",
    font=dict(family='"DM Sans","Montserrat",system-ui,sans-serif', size=13, color="#e2e8f0"),
)

_PLOTLY_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "showTips": False,
}


# ── Cone computation ──────────────────────────────────────────────────────────

def _compute_cone(prices: pd.Series, n_days: int = 60,
                  confidence_levels: list[float] | None = None) -> dict:
    """Compute expanding confidence cone from historical volatility.

    Returns dict with keys:
        last_price, last_date, future_dates,
        bands: {level: (upper, lower)} for each confidence level
    """
    if confidence_levels is None:
        confidence_levels = [0.50, 0.75, 0.90]

    prices = prices.dropna()
    if len(prices) < 20:
        return {}

    # Log returns
    log_returns = np.log(prices / prices.shift(1)).dropna()
    mu = log_returns.mean()
    sigma = log_returns.std()

    last_price = float(prices.iloc[-1])
    last_idx = prices.index[-1]

    # Generate future dates (trading days)
    if isinstance(last_idx, (pd.Timestamp, datetime)):
        future_dates = pd.bdate_range(start=last_idx, periods=n_days + 1)[1:]
    else:
        future_dates = list(range(1, n_days + 1))

    # Z-scores for each confidence level
    from scipy.stats import norm
    bands = {}
    for level in confidence_levels:
        z = norm.ppf(0.5 + level / 2)
        upper = []
        lower = []
        for t in range(1, n_days + 1):
            drift = mu * t
            vol = sigma * np.sqrt(t)
            upper.append(last_price * np.exp(drift + z * vol))
            lower.append(last_price * np.exp(drift - z * vol))
        bands[level] = (upper, lower)

    return {
        "last_price": last_price,
        "last_date": last_idx,
        "future_dates": future_dates,
        "bands": bands,
    }


def _try_scipy():
    """Check if scipy is available (needed for norm.ppf)."""
    try:
        from scipy.stats import norm
        return True
    except ImportError:
        return False


def _compute_cone_no_scipy(prices: pd.Series, n_days: int = 60,
                           confidence_levels: list[float] | None = None) -> dict:
    """Fallback cone without scipy — uses approximate z-scores."""
    if confidence_levels is None:
        confidence_levels = [0.50, 0.75, 0.90]

    prices = prices.dropna()
    if len(prices) < 20:
        return {}

    log_returns = np.log(prices / prices.shift(1)).dropna()
    mu = log_returns.mean()
    sigma = log_returns.std()

    last_price = float(prices.iloc[-1])
    last_idx = prices.index[-1]

    if isinstance(last_idx, (pd.Timestamp, datetime)):
        future_dates = pd.bdate_range(start=last_idx, periods=n_days + 1)[1:]
    else:
        future_dates = list(range(1, n_days + 1))

    # Approximate z-scores
    _z_approx = {0.50: 0.674, 0.75: 1.150, 0.90: 1.645, 0.95: 1.960, 0.99: 2.576}

    bands = {}
    for level in confidence_levels:
        z = _z_approx.get(level, 1.0)
        upper, lower = [], []
        for t in range(1, n_days + 1):
            drift = mu * t
            vol = sigma * np.sqrt(t)
            upper.append(last_price * np.exp(drift + z * vol))
            lower.append(last_price * np.exp(drift - z * vol))
        bands[level] = (upper, lower)

    return {
        "last_price": last_price,
        "last_date": last_idx,
        "future_dates": future_dates,
        "bands": bands,
    }


# ── Figure builder ────────────────────────────────────────────────────────────

_BAND_COLORS = {
    0.50: ("rgba(59,130,246,0.35)", "50%"),
    0.75: ("rgba(59,130,246,0.20)", "75%"),
    0.90: ("rgba(59,130,246,0.10)", "90%"),
}


def build_cone_figure(prices: pd.Series,
                      company: str = "",
                      n_days: int = 60,
                      polymarket_bets: list | None = None,
                      theme: str = "light") -> go.Figure | None:
    """Build the probability cone chart.

    Args:
        prices: Series with date index and price values (daily close).
        company: company name for title.
        n_days: how many days to project the cone.
        polymarket_bets: list of dicts with keys 'question', 'yes_pct', 'end_date'.
        theme: 'light' or 'dark'.
    Returns:
        go.Figure or None.
    """
    if prices is None or len(prices) < 20:
        return None

    # Compute cone
    if _try_scipy():
        cone = _compute_cone(prices, n_days)
    else:
        cone = _compute_cone_no_scipy(prices, n_days)

    if not cone:
        return None

    fig = go.Figure()

    is_dark = theme == "dark"
    text_color = "#e6edf3" if is_dark else "#374151"
    grid_color = "rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.06)"
    hist_color = "#3b82f6" if not is_dark else "#60a5fa"

    # Historical price line (last 120 days)
    hist = prices.tail(120)
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist.values,
        mode="lines",
        name="Historical",
        line=dict(color=hist_color, width=2),
        hovertemplate="<b>%{x|%b %d}</b><br>$%{y:,.2f}<extra></extra>",
    ))

    # Cone bands (widest first for layering)
    future_dates = cone["future_dates"]
    for level in sorted(cone["bands"].keys(), reverse=True):
        upper, lower = cone["bands"][level]
        color, label = _BAND_COLORS.get(level, (f"rgba(59,130,246,0.15)", f"{int(level*100)}%"))

        # Upper boundary
        fig.add_trace(go.Scatter(
            x=list(future_dates), y=upper,
            mode="lines", line=dict(width=0),
            showlegend=False, hoverinfo="skip",
        ))
        # Lower boundary with fill to upper
        fig.add_trace(go.Scatter(
            x=list(future_dates), y=lower,
            mode="lines", line=dict(width=0),
            fill="tonexty",
            fillcolor=color,
            name=f"{label} CI",
            hovertemplate=f"<b>{label} Confidence</b><br>Range: $%{{y:,.2f}}<extra></extra>",
        ))

    # Center projection (drift line)
    mu = np.log(prices / prices.shift(1)).dropna().mean()
    center = [cone["last_price"] * np.exp(mu * t) for t in range(1, n_days + 1)]
    fig.add_trace(go.Scatter(
        x=list(future_dates), y=center,
        mode="lines",
        line=dict(color="#f59e0b", width=2, dash="dash"),
        name="Expected Path",
        hovertemplate="<b>Expected</b><br>$%{y:,.2f}<extra></extra>",
    ))

    # Polymarket overlays
    if polymarket_bets:
        for bet in polymarket_bets[:5]:
            yes_pct = bet.get("yes_pct") or bet.get("yes_price", 0)
            if isinstance(yes_pct, str):
                try:
                    yes_pct = float(yes_pct.replace("%", ""))
                except ValueError:
                    continue
            if yes_pct <= 0:
                continue

            end_date = bet.get("end_date")
            if end_date and isinstance(end_date, str):
                try:
                    end_date = pd.Timestamp(end_date)
                except Exception:
                    end_date = None

            # Place marker at the expected end date
            if end_date and end_date > cone["last_date"]:
                # Find closest center projection value
                if isinstance(future_dates[0], pd.Timestamp):
                    deltas = [(abs((fd - end_date).days), i) for i, fd in enumerate(future_dates)]
                    closest_idx = min(deltas, key=lambda x: x[0])[1]
                    x_pos = future_dates[closest_idx]
                    y_pos = center[closest_idx]
                else:
                    x_pos = end_date
                    y_pos = center[-1]
            else:
                x_pos = future_dates[len(future_dates) // 2]
                y_pos = center[len(center) // 2]

            question = bet.get("question", "")[:50]
            fig.add_trace(go.Scatter(
                x=[x_pos], y=[y_pos],
                mode="markers+text",
                marker=dict(
                    symbol="diamond",
                    size=14,
                    color="#8b5cf6",
                    line=dict(width=2, color="white"),
                ),
                text=[f"{yes_pct:.0f}%"],
                textposition="top center",
                textfont=dict(size=10, color="#8b5cf6"),
                name=f"Poly: {question}",
                hovertemplate=f"<b>{question}</b><br>YES: {yes_pct:.0f}%<extra></extra>",
                showlegend=False,
            ))

    # Vertical line at today
    fig.add_vline(
        x=cone["last_date"],
        line_dash="dot",
        line_color="rgba(148,163,184,0.6)",
        line_width=1,
        annotation_text="Today",
        annotation_font=dict(size=10, color=text_color),
    )

    fig.update_layout(
        title=dict(
            text=f"{company} — Price Probability Cone ({n_days}-day outlook)",
            font=dict(size=15, color=text_color),
        ),
        height=440,
        margin=dict(t=55, r=30, l=20, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=text_color),
        hoverlabel=_HOVERLABEL,
        legend=dict(
            font=dict(color=text_color, size=11),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            x=0.01, y=0.99, xanchor="left", yanchor="top",
        ),
        xaxis=dict(
            tickfont=dict(color=text_color, size=10),
            showgrid=True, gridcolor=grid_color,
        ),
        yaxis=dict(
            title="Price ($)",
            title_font=dict(color=text_color, size=11),
            tickfont=dict(color=text_color, size=10),
            tickprefix="$",
            showgrid=True, gridcolor=grid_color,
        ),
    )

    return fig


# ── Streamlit section renderer ────────────────────────────────────────────────

def render_probability_cone_section(data_processor, companies: list,
                                    polymarket_feed: list | None = None,
                                    theme: str = "light",
                                    render_fn=None) -> None:
    """Full Streamlit UI for the prediction probability cone."""
    st.markdown("<hr style='margin: 2rem 0 1rem 0;'>", unsafe_allow_html=True)
    st.markdown(
        "<div style='margin:0.4rem 0;'>"
        "<span style='font-weight:800;font-size:1.15rem;color:#111827;'>Prediction Probability Cone</span>"
        "</div>"
        "<div style='font-size:0.85rem;color:#6b7280;margin-bottom:0.8rem;'>"
        "Fan chart based on historical volatility. The cone shows where the price "
        "could land with 50%, 75%, and 90% confidence. Diamond markers = Polymarket bet probabilities."
        "</div>",
        unsafe_allow_html=True,
    )

    _pc1, _pc2 = st.columns([2, 2])
    with _pc1:
        _cone_co = st.selectbox("Company", companies, index=0, key="cone_company")
    with _pc2:
        _cone_days = st.slider("Projection days", 20, 120, 60, step=10, key="cone_days")

    # Load stock prices for the company
    try:
        stock_df = data_processor.df_daily_prices
        if stock_df is None or stock_df.empty:
            from utils.workbook_market_data import load_combined_stock_market_data
            stock_df = load_combined_stock_market_data(
                excel_path=data_processor.data_path,
                source_stamp=int(data_processor.source_stamp or 0),
            )

        if stock_df is not None and not stock_df.empty:
            # Filter for the company
            co_lower = _cone_co.lower()
            mask = (
                stock_df["asset"].astype(str).str.lower().str.contains(co_lower, na=False)
                | stock_df["tag"].astype(str).str.lower().str.contains(co_lower, na=False)
            )
            co_stock = stock_df[mask].copy()
            if not co_stock.empty:
                co_stock["date"] = pd.to_datetime(co_stock["date"], errors="coerce")
                co_stock = co_stock.dropna(subset=["date", "close"])
                co_stock = co_stock.sort_values("date").drop_duplicates("date", keep="last")
                prices = co_stock.set_index("date")["close"].astype(float)

                # Filter Polymarket bets for this company
                co_bets = []
                if polymarket_feed:
                    for bet in polymarket_feed:
                        matched = str(bet.get("matched_company", "")).lower()
                        if co_lower in matched or matched in co_lower:
                            co_bets.append({
                                "question": bet.get("question", ""),
                                "yes_pct": float(bet.get("yes_price", 0) or 0) * 100,
                                "end_date": bet.get("end_date", ""),
                            })

                fig = build_cone_figure(
                    prices, _cone_co, _cone_days,
                    polymarket_bets=co_bets if co_bets else None,
                    theme=theme,
                )
                if fig:
                    if render_fn:
                        render_fn(fig)
                    else:
                        st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_CONFIG)
                else:
                    st.info(f"Not enough price history for {_cone_co} to build the probability cone.")
            else:
                st.info(f"No stock price data found for {_cone_co}.")
        else:
            st.info("Stock price data not available.")
    except Exception as _cone_err:
        st.caption(f"Probability cone unavailable: {_cone_err}")
