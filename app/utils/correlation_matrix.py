"""
Correlation Heatmap Matrix — cross-company metric & return correlations.

Usage (Overview page):
    from utils.correlation_matrix import render_correlation_section
    render_correlation_section(data_processor)
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ── Colour scales ─────────────────────────────────────────────────────────────

_DIVERGING = [
    [0.0, "#d73027"],   # strong negative  (red)
    [0.25, "#f46d43"],
    [0.5, "#ffffff"],   # zero  (white)
    [0.75, "#74add1"],
    [1.0, "#4575b4"],   # strong positive  (blue)
]

_HOVERLABEL = dict(
    bgcolor="rgba(10,14,26,0.97)",
    bordercolor="rgba(99,179,237,0.45)",
    font=dict(family='"DM Sans","Montserrat",system-ui,sans-serif', size=13, color="#e2e8f0"),
)


# ── Correlation computation ───────────────────────────────────────────────────

def compute_metric_correlation(df_metrics: pd.DataFrame, metric: str,
                               companies: list | None = None,
                               year_min: int = 2010,
                               year_max: int = 2025) -> pd.DataFrame:
    """Pivot *metric* by (company, year) then return NxN Pearson correlation matrix."""
    if df_metrics is None or df_metrics.empty:
        return pd.DataFrame()

    df = df_metrics.copy()
    if "company" not in df.columns or "year" not in df.columns or metric not in df.columns:
        return pd.DataFrame()

    df = df[(df["year"] >= year_min) & (df["year"] <= year_max)]
    if companies:
        df = df[df["company"].isin(companies)]

    pivot = df.pivot_table(index="year", columns="company", values=metric, aggfunc="first")
    if pivot.shape[1] < 2:
        return pd.DataFrame()

    corr = pivot.corr()
    return corr


def compute_return_correlation(df_metrics: pd.DataFrame, metric: str,
                               companies: list | None = None,
                               year_min: int = 2010,
                               year_max: int = 2025) -> pd.DataFrame:
    """Correlate YoY *changes* instead of raw levels (removes trend bias)."""
    if df_metrics is None or df_metrics.empty:
        return pd.DataFrame()

    df = df_metrics.copy()
    if "company" not in df.columns or "year" not in df.columns or metric not in df.columns:
        return pd.DataFrame()

    df = df[(df["year"] >= year_min) & (df["year"] <= year_max)].sort_values(["company", "year"])
    if companies:
        df = df[df["company"].isin(companies)]

    pivot = df.pivot_table(index="year", columns="company", values=metric, aggfunc="first")
    if pivot.shape[1] < 2:
        return pd.DataFrame()

    returns = pivot.pct_change().dropna(how="all")
    if returns.shape[0] < 3:
        return pd.DataFrame()

    corr = returns.corr()
    return corr


def compute_cross_metric_correlation(df_metrics: pd.DataFrame,
                                     company: str,
                                     metrics: list | None = None,
                                     year_min: int = 2010,
                                     year_max: int = 2025) -> pd.DataFrame:
    """Cross-metric correlation for a *single* company across years."""
    if df_metrics is None or df_metrics.empty:
        return pd.DataFrame()

    _default_metrics = ["revenue", "net_income", "operating_income", "rd",
                        "capex", "market_cap", "cash_balance", "debt"]
    if not metrics:
        metrics = _default_metrics

    df = df_metrics[df_metrics["company"] == company].copy()
    df = df[(df["year"] >= year_min) & (df["year"] <= year_max)]
    present = [m for m in metrics if m in df.columns]
    if len(present) < 2:
        return pd.DataFrame()

    corr = df[present].corr()

    # Pretty-print column names
    _nice = {
        "revenue": "Revenue", "net_income": "Net Income",
        "operating_income": "Op Income", "rd": "R&D", "capex": "CapEx",
        "market_cap": "Market Cap", "cash_balance": "Cash",
        "debt": "Debt", "total_assets": "Total Assets",
        "cost_of_revenue": "COGS",
    }
    corr.index = [_nice.get(c, c) for c in corr.index]
    corr.columns = [_nice.get(c, c) for c in corr.columns]
    return corr


# ── Figure builder ────────────────────────────────────────────────────────────

def build_correlation_figure(corr: pd.DataFrame, title: str = "Correlation Matrix") -> go.Figure:
    """Build a Plotly heatmap figure from a square correlation DataFrame."""
    if corr.empty:
        fig = go.Figure()
        fig.add_annotation(text="Not enough data", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False,
                           font=dict(size=16, color="#94a3b8"))
        return fig

    z = corr.values
    labels = corr.columns.tolist()

    # Annotation text: correlation coefficients
    text = [[f"{z[i][j]:.2f}" for j in range(len(labels))] for i in range(len(labels))]

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=labels,
        y=labels,
        text=text,
        texttemplate="%{text}",
        textfont=dict(size=11, color="#111827"),
        colorscale=_DIVERGING,
        zmin=-1,
        zmax=1,
        colorbar=dict(
            title="ρ",
            titlefont=dict(color="#374151"),
            tickfont=dict(color="#374151"),
            thickness=14,
            len=0.65,
        ),
        hovertemplate=(
            "<b>%{x}</b> vs <b>%{y}</b><br>"
            "Correlation: <b>%{z:.3f}</b><extra></extra>"
        ),
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#111827")),
        height=max(380, 50 * len(labels) + 80),
        margin=dict(t=50, r=30, l=20, b=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#374151"),
        hoverlabel=_HOVERLABEL,
        xaxis=dict(tickfont=dict(color="#374151", size=11), showgrid=False),
        yaxis=dict(tickfont=dict(color="#374151", size=11), showgrid=False, autorange="reversed"),
    )

    return fig


# ── Streamlit section renderer ────────────────────────────────────────────────

_PLOTLY_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "showTips": False,
}

_METRIC_OPTIONS = {
    "Revenue": "revenue",
    "Net Income": "net_income",
    "Operating Income": "operating_income",
    "R&D": "rd",
    "CapEx": "capex",
    "Market Cap": "market_cap",
    "Cash Balance": "cash_balance",
    "Debt": "debt",
}


def render_correlation_section(data_processor) -> None:
    """Full UI section: tabs for Stock Returns / Revenue / Cross-Metric correlation."""
    st.divider()
    st.subheader("Correlation Matrix")
    st.markdown(
        "How similarly do these companies move? "
        "Darker blue = strong positive correlation, darker red = strong negative."
    )

    corr_tab_names = ["Revenue Correlation", "Growth Correlation", "Cross-Metric"]
    corr_tabs = st.tabs(corr_tab_names)

    df = data_processor.df_metrics
    all_companies = sorted(df["company"].dropna().unique().tolist()) if df is not None and not df.empty else []
    max_year = int(df["year"].max()) if df is not None and not df.empty else 2024
    min_year = int(df["year"].min()) if df is not None and not df.empty else 2010

    # ── Tab 1: Revenue correlation (levels) ───────────────────────────────
    with corr_tabs[0]:
        c1, c2 = st.columns([2, 3])
        with c1:
            metric_label_rev = st.selectbox(
                "Metric", list(_METRIC_OPTIONS.keys()), index=0, key="corr_metric_rev"
            )
        with c2:
            yr_range_rev = st.slider(
                "Year range", min_value=min_year, max_value=max_year,
                value=(max(min_year, max_year - 9), max_year), key="corr_yr_rev"
            )

        corr_df = compute_metric_correlation(
            df, _METRIC_OPTIONS[metric_label_rev],
            companies=all_companies,
            year_min=yr_range_rev[0], year_max=yr_range_rev[1],
        )
        fig = build_correlation_figure(corr_df, f"{metric_label_rev} Correlation")
        st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_CONFIG, key="corr_fig_rev")

    # ── Tab 2: Growth correlation (YoY changes) ──────────────────────────
    with corr_tabs[1]:
        c1, c2 = st.columns([2, 3])
        with c1:
            metric_label_gro = st.selectbox(
                "Metric", list(_METRIC_OPTIONS.keys()), index=0, key="corr_metric_gro"
            )
        with c2:
            yr_range_gro = st.slider(
                "Year range", min_value=min_year, max_value=max_year,
                value=(max(min_year, max_year - 9), max_year), key="corr_yr_gro"
            )

        corr_df = compute_return_correlation(
            df, _METRIC_OPTIONS[metric_label_gro],
            companies=all_companies,
            year_min=yr_range_gro[0], year_max=yr_range_gro[1],
        )
        fig = build_correlation_figure(corr_df, f"{metric_label_gro} Growth Correlation")
        st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_CONFIG, key="corr_fig_gro")

    # ── Tab 3: Cross-metric (single company) ─────────────────────────────
    with corr_tabs[2]:
        c1, c2 = st.columns([2, 3])
        with c1:
            cross_company = st.selectbox("Company", all_companies, index=0, key="corr_cross_co")
        with c2:
            yr_range_cross = st.slider(
                "Year range", min_value=min_year, max_value=max_year,
                value=(max(min_year, max_year - 9), max_year), key="corr_yr_cross"
            )

        corr_df = compute_cross_metric_correlation(
            df, cross_company,
            year_min=yr_range_cross[0], year_max=yr_range_cross[1],
        )
        fig = build_correlation_figure(corr_df, f"{cross_company} — Cross-Metric Correlation")
        st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_CONFIG, key="corr_fig_cross")
