#!/usr/bin/env python3
"""
Chart Atlas Generator
=====================
Extracts every advanced visualisation function from each page of the app
and writes one Markdown reference document per page into reports/chart_atlas/.

Usage:
    python3 scripts/generate_chart_atlas.py          # regenerate all
    python3 scripts/generate_chart_atlas.py --page 0  # only Welcome.py

The output is self-contained: each doc shows the full function source with
a short metadata header.  Data payloads are irrelevant — the functions
themselves contain everything needed to recreate the visualisation pattern.

Automatically detects visualisation functions via AST + keyword scanning:
  • go.Figure / go.Scatter / go.Bar / go.Pie  (Plotly)
  • st.plotly_chart                           (Plotly render call)
  • st.components.v1.html                     (raw HTML/Canvas/JS iframes)
  • <canvas / getContext("2d")                (Canvas animations)
  • requestAnimationFrame                     (JS frame loops)
  • @keyframes                                (CSS animations)
  • d3. / topojson                            (D3.js globe / maps)

Re-run any time to regenerate — the script reads live source files.
"""
from __future__ import annotations

import ast
import datetime as dt
import re
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "chart_atlas"

# ── Page manifest ──────────────────────────────────────────────────────────
# (page_key, relative_path, human_label, description)
PAGE_MANIFEST: list[tuple[str, str, str, str]] = [
    ("home",      "app/Welcome.py",            "Home (Welcome)",
     "Hero animation, structural shift donut, concentration bar, M2 money printer, "
     "market bet, wealth machine, human side, scale of attention, ad duopoly, "
     "platform globe, stock ticker strip, transcript pulse."),

    ("overview",  "app/pages/00_Overview.py",   "Overview",
     "Macro KPI panel, context dashboard, expansion sections, company financial "
     "deep dives, device/platform market share, country detail, heatmaps, "
     "transcript topic growth, quarterly intelligence briefing."),

    ("earnings",  "app/pages/01_Earnings.py",   "Earnings",
     "Company metrics explorer, segment composition donut (animated), segment "
     "evolution stacked area, revenue waterfall, performance heatmap, stock charts."),

    ("stocks",    "app/pages/02_Stocks.py",     "Stocks",
     "Stock price multi-line, price history detail, sparkline SVG builder, "
     "company card grid."),

    ("editorial", "app/pages/03_Editorial.py",  "Editorial",
     "Per-service subscriber line charts, multi-service comparison chart, "
     "service color mapping."),

    ("genie",     "app/pages/04_Genie.py",      "Genie (AI Assistant)",
     "Company metrics + segments combined chart, subscriber annualized chart, "
     "topic focus bars, recession band overlay."),

    ("country",   "app/pages/05_Country.py",    "Country Deep Dive",
     "Interactive D3.js country globe, channel distribution bars, ad/GDP trend, "
     "ad spend yearly bars."),

    ("oracle",    "app/pages/06_Oracle.py",     "Oracle",
     "Living constellation visualization, prediction dials (Top Oracle Dials), "
     "layer breakdown chart, prediction table, revenue simulator with quarterly "
     "extrapolation, country ad spend predictor with channel growth models, "
     "intelligence layer metrics (divergence, channel exposure, institutional "
     "conviction, revenue per employee), MiroFish swarm simulator."),
]

# ── Visualisation detection keywords ──────────────────────────────────────
VIZ_KEYWORDS: list[str] = [
    # Plotly
    "go.Figure", "go.Scatter", "go.Bar", "go.Pie", "go.Heatmap",
    "go.Waterfall", "go.Sunburst", "go.Treemap", "go.Choropleth",
    "go.Scattergeo", "go.Indicator", "go.Funnel",
    "st.plotly_chart", "plotly_chart",
    # HTML / Canvas / JS
    "st.components.v1.html", "components.html",
    "<canvas", 'getContext("2d")', "getContext('2d')",
    "requestAnimationFrame", "cancelAnimationFrame",
    "@keyframes", "animation:",
    # D3 / maps
    "d3.select", "d3.geo", "topojson",
    # SVG inline
    "<svg", "</svg>",
]

# Functions to always skip (data-only helpers, not visualisations)
SKIP_PREFIXES = (
    "_load_", "_fetch_", "_cache_", "_parse_", "load_",
    "_git", "_run", "_read",
)
# Skip 'main' only when it's tiny; large main() functions usually contain inline charts
MAIN_MIN_LINES = 40  # include main() only if it's bigger than this


def _git_short() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_functions(source: str) -> list[tuple[str, int, int]]:
    """Return (name, start_line, end_line) for every top-level + nested function."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    funcs: list[tuple[str, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            funcs.append((node.name, node.lineno, end))
    funcs.sort(key=lambda x: x[1])
    return funcs


def _is_viz_function(source_lines: list[str], start: int, end: int) -> bool:
    """Check if the function body contains visualisation keywords."""
    body = "\n".join(source_lines[start - 1 : end])
    return any(kw in body for kw in VIZ_KEYWORDS)


def _classify_viz(body: str) -> list[str]:
    """Return tags describing the visualisation type."""
    tags: list[str] = []
    if any(k in body for k in ("go.Figure", "go.Scatter", "go.Bar", "go.Pie", "go.Heatmap", "go.Waterfall")):
        tags.append("Plotly")
    if any(k in body for k in ("st.components.v1.html", "components.html")):
        tags.append("HTML/iframe")
    if any(k in body for k in ("<canvas", 'getContext("2d")', "getContext('2d')")):
        tags.append("Canvas")
    if "requestAnimationFrame" in body:
        tags.append("JS Animation")
    if "@keyframes" in body:
        tags.append("CSS Animation")
    if any(k in body for k in ("d3.select", "d3.geo", "topojson")):
        tags.append("D3.js")
    if any(k in body for k in ("<svg", "</svg>")):
        tags.append("SVG")
    if "st.plotly_chart" in body or "plotly_chart" in body:
        tags.append("Plotly render")
    return tags or ["Visualisation"]


def _find_inline_viz_blocks(source: str, lines: list[str], func_ranges: list[tuple[int, int]]) -> list[tuple[str, int, int, str]]:
    """Find visualisation calls (HTML components + Plotly) NOT inside any function."""
    blocks: list[tuple[str, int, int, str]] = []
    in_func = set()
    for start, end in func_ranges:
        for i in range(start, end + 1):
            in_func.add(i)

    # Patterns to detect inline visualisation blocks
    inline_patterns = [
        (re.compile(r"st\.components\.v1\.html\("), "html"),
        (re.compile(r"go\.Figure\("), "plotly"),
        (re.compile(r"st\.plotly_chart\("), "plotly_render"),
    ]

    seen_lines: set[int] = set()  # avoid duplicate captures

    for pattern, kind in inline_patterns:
        for i, line in enumerate(lines, 1):
            if pattern.search(line) and i not in in_func and i not in seen_lines:
                # Grab context: scan backwards for the start of the block
                ctx_start = max(1, i - 5)
                ctx_end = min(len(lines), i + 3)

                if kind == "html":
                    # Try to find the closing of the html() call
                    paren_depth = 0
                    for j in range(i - 1, min(len(lines), i + 50)):
                        for ch in lines[j]:
                            if ch == "(":
                                paren_depth += 1
                            elif ch == ")":
                                paren_depth -= 1
                        if paren_depth <= 0 and j > i - 1:
                            ctx_end = j + 1
                            break
                    # Also grab the variable being passed
                    html_var = None
                    m = re.search(r"html\(\s*(\w+)", line)
                    if m:
                        html_var = m.group(1)
                        for k in range(i - 2, max(0, i - 200), -1):
                            if re.match(rf"\s*{re.escape(html_var)}\s*=", lines[k]):
                                ctx_start = k + 1
                                break
                    label = f"inline_{html_var or 'html'}_L{i}"

                elif kind == "plotly":
                    # Scan backwards for fig = go.Figure or fig.add_trace etc.
                    fig_var = None
                    m = re.match(r"\s*(\w+)\s*=\s*go\.Figure", line)
                    if m:
                        fig_var = m.group(1)
                        ctx_start = i
                    # Scan forward to find st.plotly_chart or render_plotly call
                    for j in range(i, min(len(lines), i + 80)):
                        fwd_line = lines[j]
                        if fig_var and ("plotly_chart" in fwd_line or "render_plotly" in fwd_line):
                            ctx_end = j + 1
                            break
                        if fig_var and f"{fig_var}.update_layout" in fwd_line:
                            ctx_end = j + 1  # keep scanning
                    label = f"inline_{fig_var or 'figure'}_L{i}"

                elif kind == "plotly_render":
                    # Just the render call — grab a few lines of context
                    ctx_start = max(1, i - 2)
                    ctx_end = i + 1
                    label = f"inline_plotly_render_L{i}"

                # Mark all lines in this block as seen
                for k in range(ctx_start, ctx_end + 1):
                    seen_lines.add(k)

                snippet = "\n".join(lines[ctx_start - 1 : ctx_end])
                blocks.append((label, ctx_start, ctx_end, snippet))

    blocks.sort(key=lambda x: x[1])
    return blocks


def _generate_page_doc(
    page_key: str,
    rel_path: str,
    label: str,
    description: str,
) -> str | None:
    """Generate markdown for one page. Returns None if file missing."""
    path = ROOT / rel_path
    if not path.exists():
        return None

    source = _read_source(path)
    lines = source.splitlines()
    total_lines = len(lines)
    funcs = _extract_functions(source)

    # Filter to viz functions (skip data loaders)
    viz_funcs: list[tuple[str, int, int, list[str]]] = []
    for name, start, end in funcs:
        if any(name.startswith(p) for p in SKIP_PREFIXES):
            continue
        # Include main() only if it's large enough to contain real chart code
        if name == "main" and (end - start + 1) < MAIN_MIN_LINES:
            continue
        if _is_viz_function(lines, start, end):
            body = "\n".join(lines[start - 1 : end])
            tags = _classify_viz(body)
            viz_funcs.append((name, start, end, tags))

    # Find inline viz blocks (HTML + Plotly) not inside functions
    func_ranges = [(s, e) for _, s, e in funcs]
    inline_blocks = _find_inline_viz_blocks(source, lines, func_ranges)

    if not viz_funcs and not inline_blocks:
        return None

    # Build markdown
    md: list[str] = []
    md.append(f"# Chart Atlas — {label}")
    md.append(f"**Source:** `{rel_path}` ({total_lines:,} lines)")
    md.append(f"**Generated:** {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} — commit `{_git_short()}`")
    md.append(f"**Visualisation functions found:** {len(viz_funcs)} | **Inline HTML blocks:** {len(inline_blocks)}")
    md.append("")
    md.append(f"> {description}")
    md.append("")
    md.append("---")
    md.append("")

    # Table of contents
    md.append("## Index")
    md.append("")
    for i, (name, start, end, tags) in enumerate(viz_funcs, 1):
        tag_str = ", ".join(tags)
        md.append(f"{i}. [`{name}()`](#fn-{name}) — L{start}–L{end} — {tag_str}")
    for i, (label_b, start, end, _snippet) in enumerate(inline_blocks, len(viz_funcs) + 1):
        md.append(f"{i}. [`{label_b}`](#inline-{label_b}) — L{start}–L{end} — HTML/iframe")
    md.append("")
    md.append("---")
    md.append("")

    # Function snippets
    for name, start, end, tags in viz_funcs:
        tag_str = " · ".join(tags)
        body = "\n".join(lines[start - 1 : end])
        md.append(f'<a id="fn-{name}"></a>')
        md.append(f"## `{name}()` — {tag_str}")
        md.append(f"Lines {start}–{end} ({end - start + 1} lines)")
        md.append("")
        md.append("```python")
        md.append(body)
        md.append("```")
        md.append("")
        md.append("---")
        md.append("")

    # Inline HTML blocks
    for label_b, start, end, snippet in inline_blocks:
        md.append(f'<a id="inline-{label_b}"></a>')
        md.append(f"## `{label_b}` — HTML/iframe")
        md.append(f"Lines {start}–{end}")
        md.append("")
        md.append("```python")
        md.append(snippet)
        md.append("```")
        md.append("")
        md.append("---")
        md.append("")

    return "\n".join(md)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate Chart Atlas — per-page visualisation reference docs.")
    parser.add_argument("--page", type=int, default=None, help="Generate only for page N (0=Home, 1=Overview, ...)")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pages = PAGE_MANIFEST
    if args.page is not None:
        pages = [PAGE_MANIFEST[args.page]]

    generated: list[str] = []
    for page_key, rel_path, label, description in pages:
        print(f"[atlas] Processing {label} ({rel_path}) ...")
        md = _generate_page_doc(page_key, rel_path, label, description)
        if md is None:
            print(f"  ⚠ skipped (no file or no viz functions)")
            continue
        out_file = OUT_DIR / f"chart_atlas_{page_key}.md"
        out_file.write_text(md, encoding="utf-8")
        n_funcs = md.count("```python") // 2  # each snippet has open+close
        print(f"  ✓ {out_file.name} — {n_funcs} snippets")
        generated.append(out_file.name)

    # Write a combined index
    idx: list[str] = []
    idx.append("# Chart Atlas — Master Index")
    idx.append(f"**Generated:** {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} — commit `{_git_short()}`")
    idx.append("")
    idx.append("Per-page visualisation reference docs for **The Attention Economy** dashboard.")
    idx.append("Each doc contains the full source code of every chart, animation, and HTML component.")
    idx.append("")
    idx.append("| # | Page | Doc | Description |")
    idx.append("|---|------|-----|-------------|")
    for i, (page_key, rel_path, label, description) in enumerate(PAGE_MANIFEST):
        doc_name = f"chart_atlas_{page_key}.md"
        exists = (OUT_DIR / doc_name).exists()
        status = f"[{doc_name}](./{doc_name})" if exists else "*(not generated)*"
        short_desc = description[:80] + "..." if len(description) > 80 else description
        idx.append(f"| {i} | **{label}** | {status} | {short_desc} |")
    idx.append("")
    idx.append("---")
    idx.append("")
    idx.append("**Regenerate:** `python3 scripts/generate_chart_atlas.py`")
    idx.append("")

    idx_file = OUT_DIR / "INDEX.md"
    idx_file.write_text("\n".join(idx), encoding="utf-8")
    print(f"\n[atlas] Index → {idx_file}")
    print(f"[atlas] Done — {len(generated)} docs in {OUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
