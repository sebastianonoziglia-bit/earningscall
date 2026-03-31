"""
Earnings Sentiment Timeline — sentence-level sentiment through an earnings call.

Reads raw transcript .txt files from earningscall_transcripts/<Company>/<Year>/<Quarter>.txt
Uses VADER for lightweight, zero-config sentiment scoring.

Usage:
    from utils.sentiment_scorer import render_sentiment_timeline
    render_sentiment_timeline(company, year, quarter)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Try to import VADER; graceful fallback ────────────────────────────────────
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER_AVAILABLE = True
except ImportError:
    _VADER_AVAILABLE = False


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


# ── Transcript loading ────────────────────────────────────────────────────────

def _find_transcript_root() -> Path:
    """Walk up from app/ to find earningscall_transcripts/."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "earningscall_transcripts",
        Path(__file__).resolve().parent.parent / "earningscall_transcripts",
        Path(os.getcwd()) / "earningscall_transcripts",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


def _company_folder_name(company: str) -> str:
    """Convert display name to folder name: 'Meta Platforms' → 'Meta_Platforms'."""
    return company.replace(" ", "_").replace(".", "")


def load_transcript(company: str, year: int, quarter: str) -> Optional[str]:
    """Load raw transcript text. quarter = 'Q1', 'Q2', etc."""
    root = _find_transcript_root()
    folder = _company_folder_name(company)
    # Try exact quarter file first
    q_file = root / folder / str(year) / f"{quarter}.txt"
    if q_file.exists():
        return q_file.read_text(encoding="utf-8", errors="ignore")
    # Try alternate naming
    for alt in [f"{quarter.lower()}.txt", f"q{quarter[-1]}.txt"]:
        alt_file = root / folder / str(year) / alt
        if alt_file.exists():
            return alt_file.read_text(encoding="utf-8", errors="ignore")
    return None


# ── Sentence splitting ────────────────────────────────────────────────────────

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, filtering out very short ones."""
    raw = _SENTENCE_SPLIT.split(text)
    return [s.strip() for s in raw if len(s.strip()) > 20]


# ── Scoring ───────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def score_transcript(company: str, year: int, quarter: str,
                     window: int = 10) -> Optional[pd.DataFrame]:
    """Score each sentence with VADER compound, return rolling-window smoothed timeline.

    Returns DataFrame with columns:
        position  — 0..100 (% through transcript)
        compound  — raw VADER compound score (-1 to +1)
        smoothed  — rolling-window smoothed score
        sentence  — original text (for hover)
    """
    if not _VADER_AVAILABLE:
        return None

    text = load_transcript(company, year, quarter)
    if not text:
        return None

    sentences = _split_sentences(text)
    if len(sentences) < 5:
        return None

    analyzer = SentimentIntensityAnalyzer()
    scores = []
    for s in sentences:
        vs = analyzer.polarity_scores(s)
        scores.append(vs["compound"])

    n = len(scores)
    df = pd.DataFrame({
        "position": np.linspace(0, 100, n),
        "compound": scores,
        "sentence": [s[:120] + ("..." if len(s) > 120 else "") for s in sentences],
    })

    # Rolling smoothed
    half_win = max(1, window // 2)
    df["smoothed"] = df["compound"].rolling(window=window, min_periods=half_win, center=True).mean()
    df["smoothed"] = df["smoothed"].fillna(df["compound"])

    return df


# ── Figure builder ────────────────────────────────────────────────────────────

def build_sentiment_figure(df: pd.DataFrame,
                           company: str = "",
                           year: int = 2024,
                           quarter: str = "Q4",
                           theme: str = "light") -> go.Figure:
    """Build the area chart with green above zero / red below, scatter dots for hover."""

    fig = go.Figure()

    # Positive fill (green)
    pos = df["smoothed"].clip(lower=0)
    fig.add_trace(go.Scatter(
        x=df["position"], y=pos,
        fill="tozeroy",
        fillcolor="rgba(34,197,94,0.18)",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Negative fill (red)
    neg = df["smoothed"].clip(upper=0)
    fig.add_trace(go.Scatter(
        x=df["position"], y=neg,
        fill="tozeroy",
        fillcolor="rgba(239,68,68,0.18)",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Main smoothed line
    fig.add_trace(go.Scatter(
        x=df["position"], y=df["smoothed"],
        mode="lines",
        line=dict(color="#3b82f6", width=2.5),
        name="Sentiment",
        showlegend=False,
        hoverinfo="skip",
    ))

    # Scatter dots for hover (every 3rd point to avoid clutter)
    step = max(1, len(df) // 50)
    hover_df = df.iloc[::step]
    fig.add_trace(go.Scatter(
        x=hover_df["position"],
        y=hover_df["smoothed"],
        mode="markers",
        marker=dict(
            size=6,
            color=hover_df["smoothed"].apply(
                lambda v: "#22c55e" if v > 0.05 else ("#ef4444" if v < -0.05 else "#94a3b8")
            ),
            line=dict(width=1, color="rgba(255,255,255,0.3)"),
        ),
        text=hover_df["sentence"],
        hovertemplate=(
            "<b>Position:</b> %{x:.0f}%<br>"
            "<b>Sentiment:</b> %{y:.3f}<br>"
            "<b>Quote:</b> %{text}"
            "<extra></extra>"
        ),
        showlegend=False,
    ))

    # Zero line
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(148,163,184,0.5)", line_width=1)

    is_dark = theme == "dark"
    text_color = "#e6edf3" if is_dark else "#374151"
    grid_color = "rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.06)"

    fig.update_layout(
        title=dict(
            text=f"{company} — {quarter} {year} Earnings Call Sentiment",
            font=dict(size=15, color=text_color),
        ),
        height=380,
        margin=dict(t=50, r=30, l=20, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=text_color),
        hoverlabel=_HOVERLABEL,
        xaxis=dict(
            title="Position through call (%)",
            title_font=dict(color=text_color, size=11),
            tickfont=dict(color=text_color, size=10),
            ticksuffix="%",
            range=[0, 100],
            showgrid=True,
            gridcolor=grid_color,
        ),
        yaxis=dict(
            title="Sentiment",
            title_font=dict(color=text_color, size=11),
            tickfont=dict(color=text_color, size=10),
            range=[-0.6, 0.6],
            showgrid=True,
            gridcolor=grid_color,
            zeroline=False,
        ),
    )

    return fig


# ── Side-by-side comparison ──────────────────────────────────────────────────

def build_comparison_figure(df1: pd.DataFrame, df2: pd.DataFrame,
                            label1: str, label2: str,
                            theme: str = "light") -> go.Figure:
    """Compare two quarters side by side."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df1["position"], y=df1["smoothed"],
        mode="lines", name=label1,
        line=dict(color="#3b82f6", width=2.5),
    ))
    fig.add_trace(go.Scatter(
        x=df2["position"], y=df2["smoothed"],
        mode="lines", name=label2,
        line=dict(color="#f59e0b", width=2.5, dash="dot"),
    ))

    fig.add_hline(y=0, line_dash="dash", line_color="rgba(148,163,184,0.5)", line_width=1)

    is_dark = theme == "dark"
    text_color = "#e6edf3" if is_dark else "#374151"
    grid_color = "rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.06)"

    fig.update_layout(
        title=dict(text=f"Sentiment Comparison: {label1} vs {label2}",
                   font=dict(size=15, color=text_color)),
        height=380,
        margin=dict(t=50, r=30, l=20, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=text_color),
        hoverlabel=_HOVERLABEL,
        legend=dict(font=dict(color=text_color), bgcolor="rgba(0,0,0,0)", borderwidth=0),
        xaxis=dict(
            title="Position through call (%)",
            title_font=dict(color=text_color, size=11),
            tickfont=dict(color=text_color, size=10),
            ticksuffix="%", range=[0, 100],
            showgrid=True, gridcolor=grid_color,
        ),
        yaxis=dict(
            title="Sentiment", title_font=dict(color=text_color, size=11),
            tickfont=dict(color=text_color, size=10),
            range=[-0.6, 0.6], showgrid=True, gridcolor=grid_color, zeroline=False,
        ),
    )

    return fig


# ── Streamlit section renderer ────────────────────────────────────────────────

def render_sentiment_timeline(company: str, years: list, render_fn=None,
                              theme: str = "light") -> None:
    """Full Streamlit UI section for sentiment analysis."""
    if not _VADER_AVAILABLE:
        st.info("Sentiment analysis requires the `vaderSentiment` package. "
                "Add it to requirements.txt to enable this feature.")
        return

    st.divider()
    st.markdown(
        "<div style='margin:0.8rem 0 0.4rem 0;'>"
        "<span style='font-weight:800;font-size:1.15rem;color:#111827;'>Earnings Call Sentiment Timeline</span>"
        "</div>"
        "<div style='font-size:0.85rem;color:#6b7280;margin-bottom:0.6rem;'>"
        "VADER sentiment through each earnings call. Green = positive, red = negative. "
        "Hover over dots to see the actual quote. Compare two quarters to spot shifts in tone."
        "</div>",
        unsafe_allow_html=True,
    )

    _stab1, _stab2 = st.tabs(["Single Quarter", "Compare Two Quarters"])

    quarters = ["Q1", "Q2", "Q3", "Q4"]

    with _stab1:
        _sc1, _sc2 = st.columns([1, 1])
        with _sc1:
            _s_year = st.selectbox("Year", sorted(years, reverse=True), index=0, key="sent_yr")
        with _sc2:
            _s_qtr = st.selectbox("Quarter", quarters, index=3, key="sent_qtr")

        df = score_transcript(company, int(_s_year), _s_qtr)
        if df is not None and not df.empty:
            fig = build_sentiment_figure(df, company, int(_s_year), _s_qtr, theme)
            if render_fn:
                render_fn(fig)
            else:
                st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_CONFIG)

            # Quick stats
            avg = df["smoothed"].mean()
            most_pos = df.loc[df["smoothed"].idxmax()]
            most_neg = df.loc[df["smoothed"].idxmin()]
            st.markdown(
                f"<div style='font-size:0.82rem;color:#6b7280;margin-top:-6px;'>"
                f"Avg sentiment: <b style='color:{('#22c55e' if avg > 0 else '#ef4444')}'>{avg:.3f}</b> · "
                f"Peak: <b style='color:#22c55e'>{most_pos['smoothed']:.3f}</b> at {most_pos['position']:.0f}% · "
                f"Trough: <b style='color:#ef4444'>{most_neg['smoothed']:.3f}</b> at {most_neg['position']:.0f}%"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info(f"No transcript found for {company} {_s_qtr} {_s_year}.")

    with _stab2:
        _cc1, _cc2, _cc3, _cc4 = st.columns(4)
        with _cc1:
            _c_yr1 = st.selectbox("Year A", sorted(years, reverse=True), index=0, key="sent_cyr1")
        with _cc2:
            _c_q1 = st.selectbox("Quarter A", quarters, index=3, key="sent_cq1")
        with _cc3:
            _c_yr2 = st.selectbox("Year B", sorted(years, reverse=True),
                                   index=min(1, len(years) - 1), key="sent_cyr2")
        with _cc4:
            _c_q2 = st.selectbox("Quarter B", quarters, index=3, key="sent_cq2")

        df1 = score_transcript(company, int(_c_yr1), _c_q1)
        df2 = score_transcript(company, int(_c_yr2), _c_q2)

        if df1 is not None and df2 is not None:
            fig = build_comparison_figure(
                df1, df2,
                f"{_c_q1} {_c_yr1}", f"{_c_q2} {_c_yr2}",
                theme,
            )
            if render_fn:
                render_fn(fig)
            else:
                st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_CONFIG)
        elif df1 is None:
            st.info(f"No transcript for {company} {_c_q1} {_c_yr1}.")
        else:
            st.info(f"No transcript for {company} {_c_q2} {_c_yr2}.")
