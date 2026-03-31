"""
Sankey Revenue Flow + Waterfall Bridge Chart builders.

Usage (Earnings page):
    from utils.sankey_builder import build_sankey_figure, build_waterfall_figure
"""

import numpy as np
import plotly.graph_objects as go


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


# ── Sankey Revenue Flow ───────────────────────────────────────────────────────

def build_sankey_figure(metrics: dict, segments: dict | None = None,
                        company: str = "", year: int = 2024) -> go.Figure | None:
    """Build a Sankey diagram: Revenue → Segments → Gross Profit → OpEx → Op Income → Net Income.

    Args:
        metrics: dict from data_processor.get_metrics(company, year). Must have at minimum
                 revenue, cost_of_revenue, operating_income, net_income.
        segments: dict from data_processor.get_segments(company, year) with labels/values.
        company: company name for title.
        year: year for title.
    Returns:
        go.Figure or None if not enough data.
    """
    if not metrics:
        return None

    rev = metrics.get("revenue") or 0
    cogs = abs(metrics.get("cost_of_revenue") or 0)
    oi = metrics.get("operating_income") or 0
    ni = metrics.get("net_income") or 0
    rd = abs(metrics.get("rd") or 0)

    if rev <= 0:
        return None

    gross_profit = rev - cogs
    # SG&A + other = gross_profit - R&D - operating_income (residual)
    sga_other = max(0, gross_profit - rd - oi)
    # Below-the-line (taxes, interest, etc.)
    below_line = oi - ni

    # ── Build node list ───────────────────────────────────────────────────
    nodes = []
    node_idx = {}

    def _add(name, color):
        idx = len(nodes)
        nodes.append({"label": name, "color": color})
        node_idx[name] = idx
        return idx

    _add("Revenue", "#3b82f6")      # 0

    # Segment nodes (if available)
    seg_indices = []
    has_segs = segments and segments.get("labels") and len(segments["labels"]) > 1
    if has_segs:
        for lbl in segments["labels"]:
            seg_indices.append(_add(lbl, "#60a5fa"))

    _add("COGS", "#ef4444")          # cost
    _add("Gross Profit", "#10b981")
    _add("R&D", "#f59e0b")
    _add("SG&A & Other", "#f97316")
    _add("Operating Income", "#06b6d4")
    _add("Net Income", "#8b5cf6")
    if below_line > 0:
        _add("Tax & Interest", "#ef4444")

    # ── Build links ───────────────────────────────────────────────────────
    sources, targets, values, link_colors = [], [], [], []

    def _link(src, tgt, val, color):
        if val > 0:
            sources.append(node_idx[src])
            targets.append(node_idx[tgt])
            values.append(val)
            link_colors.append(color)

    if has_segs:
        # Revenue → Segments
        seg_total = sum(segments["values"])
        for i, lbl in enumerate(segments["labels"]):
            seg_val = segments["values"][i] if i < len(segments["values"]) else 0
            if seg_val > 0:
                _link("Revenue", lbl, seg_val, "rgba(59,130,246,0.25)")
        # Segments → COGS and Segments → Gross Profit (proportional split)
        for i, lbl in enumerate(segments["labels"]):
            seg_val = segments["values"][i] if i < len(segments["values"]) else 0
            if seg_val > 0 and seg_total > 0:
                ratio = seg_val / seg_total
                _link(lbl, "COGS", cogs * ratio, "rgba(239,68,68,0.2)")
                _link(lbl, "Gross Profit", gross_profit * ratio, "rgba(16,185,129,0.2)")
    else:
        # Direct: Revenue → COGS + Gross Profit
        _link("Revenue", "COGS", cogs, "rgba(239,68,68,0.25)")
        _link("Revenue", "Gross Profit", gross_profit, "rgba(16,185,129,0.25)")

    # Gross Profit → R&D, SG&A, Operating Income
    _link("Gross Profit", "R&D", rd, "rgba(245,158,11,0.25)")
    _link("Gross Profit", "SG&A & Other", sga_other, "rgba(249,115,22,0.25)")
    _link("Gross Profit", "Operating Income", max(0, oi), "rgba(6,182,212,0.25)")

    # Operating Income → Net Income + Tax/Interest
    if below_line > 0:
        _link("Operating Income", "Net Income", max(0, ni), "rgba(139,92,207,0.25)")
        _link("Operating Income", "Tax & Interest", below_line, "rgba(239,68,68,0.2)")
    else:
        _link("Operating Income", "Net Income", max(0, ni), "rgba(139,92,207,0.25)")

    if not values:
        return None

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=18,
            thickness=22,
            line=dict(color="rgba(0,0,0,0.15)", width=0.8),
            label=[n["label"] for n in nodes],
            color=[n["color"] for n in nodes],
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}M<extra></extra>",
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
            hovertemplate="%{source.label} → %{target.label}<br>$%{value:,.0f}M<extra></extra>",
        ),
    ))

    fig.update_layout(
        title=dict(
            text=f"{company} — Revenue Flow ({year})",
            font=dict(size=15, color="#111827"),
        ),
        height=480,
        margin=dict(t=50, r=30, l=20, b=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#374151", size=12),
        hoverlabel=_HOVERLABEL,
    )

    return fig


# ── Waterfall Bridge Chart ────────────────────────────────────────────────────

def build_waterfall_figure(metrics: dict, company: str = "",
                           year: int = 2024) -> go.Figure | None:
    """Build a waterfall: Revenue → -COGS → =Gross → -R&D → -SG&A → =Op Income → =Net Income.

    Returns go.Figure or None.
    """
    if not metrics:
        return None

    rev = metrics.get("revenue") or 0
    cogs = abs(metrics.get("cost_of_revenue") or 0)
    oi = metrics.get("operating_income") or 0
    ni = metrics.get("net_income") or 0
    rd = abs(metrics.get("rd") or 0)

    if rev <= 0:
        return None

    gross = rev - cogs
    sga = max(0, gross - rd - oi)
    below_line = oi - ni

    labels = ["Revenue", "COGS", "Gross Profit", "R&D", "SG&A & Other",
              "Operating Income", "Tax & Interest", "Net Income"]
    measures = ["absolute", "relative", "total", "relative", "relative",
                "total", "relative", "total"]
    vals = [rev, -cogs, None, -rd, -sga, None, -below_line, None]

    # Text on bars
    def _fmt(v):
        if v is None:
            return ""
        av = abs(v)
        if av >= 1000:
            return f"${av / 1000:.1f}B"
        return f"${av:,.0f}M"

    text_vals = []
    running = rev
    for i, (m, v) in enumerate(zip(measures, vals)):
        if m == "absolute":
            text_vals.append(_fmt(v))
        elif m == "total":
            if labels[i] == "Gross Profit":
                text_vals.append(_fmt(gross))
            elif labels[i] == "Operating Income":
                text_vals.append(_fmt(oi))
            elif labels[i] == "Net Income":
                text_vals.append(_fmt(ni))
            else:
                text_vals.append("")
        else:
            text_vals.append(_fmt(v))

    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=measures,
        x=labels,
        y=vals,
        text=text_vals,
        textposition="outside",
        textfont=dict(size=11, color="#374151"),
        connector=dict(line=dict(color="rgba(0,0,0,0.12)", width=1, dash="dot")),
        increasing=dict(marker=dict(color="#10b981")),
        decreasing=dict(marker=dict(color="#ef4444")),
        totals=dict(marker=dict(color="#3b82f6")),
        hovertemplate="<b>%{x}</b><br>$%{y:,.0f}M<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=f"{company} — P&L Bridge ({year})",
            font=dict(size=15, color="#111827"),
        ),
        height=460,
        margin=dict(t=55, r=30, l=20, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#374151"),
        hoverlabel=_HOVERLABEL,
        yaxis=dict(
            tickfont=dict(color="#374151"),
            gridcolor="rgba(0,0,0,0.06)",
            showline=False,
            zeroline=False,
        ),
        xaxis=dict(
            tickfont=dict(color="#374151", size=11),
            showgrid=False,
        ),
        showlegend=False,
    )

    return fig
