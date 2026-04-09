"""
MiroFish Ad-Spend Simulator — Multi-Agent Swarm Prediction Engine.

Clean-room reimplementation of the MiroFish 5-phase architecture
(Graph → Persona → Simulation → Report → Chat), specialized for
global advertising-spend forecasting against GroupM baselines.

Uses DeepSeek (preferred) or OpenAI via the same client as Genie — set
DEEPSEEK_API_KEY in .env or HF secrets. No Anthropic key needed.

Phases:
  1. build_ad_market_graph  — ingest workbook ad-spend data into a networkx graph
  2. seed_ad_agents         — generate N personas with ad-industry biases
  3. run_ad_simulation      — K rounds of agent reactions, crowd aggregation
  4. generate_ad_report     — LLM synthesis: forecast cone, channel deltas, drivers
  5. chat_with_agent        — (stretch) interactive drill-down into an agent

Data sources (all from the workbook, no Supabase):
  - Global_Adv_Aggregates:    18 channels × 31 years (1999–2029, incl. GroupM forecasts)
  - Global Advertising (GroupM): channel split by year
  - Company_advertising_revenue: company-level ad revenue ($B)
  - Macro_KPIs:               macro indicators
  - scored_signals.csv:       3,500+ forward-looking CEO/CFO quotes

Cost control:
  - Each LLM call tracks input/output tokens
  - Hard abort if cumulative spend > $2 per run
  - Button label shows estimated cost before click
"""
from __future__ import annotations

import json
import math
import random
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd


# ════════════════════════════════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════════════════════════════════

CHANNEL_MAP = {
    "Cinema Worldwide": "Cinema",
    "Digital OOH Worldwide": "Digital OOH",
    "Display Desktop Worldwide": "Display Desktop",
    "Display Mobile Worldwide": "Display Mobile",
    "Free TV Worldwide": "Free TV",
    "Magazine Worldwide": "Magazine",
    "Newspaper Worldwide": "Newspaper",
    "Other Desktop Worldwide": "Other Desktop",
    "Other Mobile Worldwide": "Other Mobile",
    "Pay TV Worldwide": "Pay TV",
    "Radio Worldwide": "Radio",
    "Search Desktop Worldwide": "Search Desktop",
    "Search Mobile Worldwide": "Search Mobile",
    "Social Desktop Worldwide": "Social Desktop",
    "Social Mobile Worldwide": "Social Mobile",
    "Traditional OOH Worldwide": "Traditional OOH",
    "Video Desktop Worldwide": "Video Desktop",
    "Video Mobile Worldwide": "Video Mobile",
}

# Collapse to broader categories for simulation
CHANNEL_GROUPS = {
    "Search": ["Search Desktop", "Search Mobile"],
    "Social": ["Social Desktop", "Social Mobile"],
    "Video/CTV": ["Video Desktop", "Video Mobile", "Free TV", "Pay TV"],
    "Display": ["Display Desktop", "Display Mobile"],
    "OOH": ["Traditional OOH", "Digital OOH", "Cinema"],
    "Print": ["Magazine", "Newspaper"],
    "Radio": ["Radio"],
    "Other Digital": ["Other Desktop", "Other Mobile"],
}

# Persona role distribution for seeding
PERSONA_ROLES = {
    "CPG Brand Marketer": 10,
    "Auto CMO": 6,
    "Retail Media Buyer": 8,
    "Agency Investment Director": 8,
    "Platform Sell-Side Exec": 7,
    "CTV Publisher": 5,
    "Institutional Portfolio Manager": 7,
    "Macro Strategist": 4,
    "Privacy Regulator": 3,
    "Ad-Tech Skeptic": 2,
}

SCENARIO_PRESETS = {
    "baseline": "No major shocks. Steady macro conditions. Current trends continue.",
    "recession": "Global recession hits in H2. Consumer confidence drops 25%. Ad budgets cut 10-15% across the board. CPM deflation.",
    "rate_cuts": "US Fed cuts 150bps over 6 months. Risk-on sentiment. Brand budgets expand. M&A activity surges in ad-tech.",
    "tiktok_ban": "TikTok banned in US and EU. $20B+ social ad spend up for grabs. Meta, YouTube, Snapchat compete fiercely.",
    "cookie_deprecation": "Chrome finally kills third-party cookies. Contextual targeting surges. Retail media and first-party data gain share.",
    "genai_creative": "GenAI reduces creative production costs 60%. Long-tail advertisers flood digital channels. Supply increases, CPMs drop initially.",
    "ctv_saturation": "CTV ad load reaches viewer tolerance limits. AVOD churn spikes. Linear TV stabilizes as CTV growth plateaus.",
}

# Cost constants — DeepSeek pricing (primary), falls back to OpenAI/Anthropic
# DeepSeek V3: $0.27/M input, $1.10/M output (cache miss)
DEEPSEEK_INPUT_COST = 0.27 / 1_000_000
DEEPSEEK_OUTPUT_COST = 1.10 / 1_000_000
# Fallback: OpenAI GPT-4o-mini pricing
GPT4O_MINI_INPUT_COST = 0.15 / 1_000_000
GPT4O_MINI_OUTPUT_COST = 0.60 / 1_000_000
MAX_COST_PER_RUN = 2.00  # hard abort


# ════════════════════════════════════════════════════════════════════════
# Phase 1 — Graph Build
# ════════════════════════════════════════════════════════════════════════

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_workbook_path() -> str:
    """Resolve workbook using the standard source helper."""
    try:
        import sys
        if str(_repo_root() / "app") not in sys.path:
            sys.path.insert(0, str(_repo_root() / "app"))
        from utils.workbook_source import resolve_financial_data_xlsx
        return resolve_financial_data_xlsx([])
    except Exception:
        return ""


def _load_global_adv_aggregates(xlsx: str) -> pd.DataFrame:
    """18 channels × 31 years, values in $M."""
    try:
        df = pd.read_excel(xlsx, sheet_name="Global_Adv_Aggregates")
        df.columns = [str(c).strip() for c in df.columns]
        df["channel"] = (
            df["metric_type"]
            .str.replace(" Worldwide", "", regex=False)
            .str.strip()
        )
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df["value_m"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["year", "value_m"]).copy()
    except Exception:
        return pd.DataFrame()


def _load_groupm_channels(xlsx: str) -> pd.DataFrame:
    """GroupM channel split by year ($M)."""
    try:
        df = pd.read_excel(xlsx, sheet_name="Global Advertising (GroupM)")
        df.columns = [str(c).strip() for c in df.columns]
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
        return df.dropna(subset=["Year"]).copy()
    except Exception:
        return pd.DataFrame()


def _load_company_ad_revenue(xlsx: str) -> pd.DataFrame:
    """Company-level advertising revenue by year ($B)."""
    try:
        df = pd.read_excel(xlsx, sheet_name="Company_advertising_revenue")
        df.columns = [str(c).strip() for c in df.columns]
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
        return df.dropna(subset=["Year"]).copy()
    except Exception:
        return pd.DataFrame()


def _load_macro_kpis(xlsx: str) -> list[dict]:
    """Macro indicators: list of {indicator, value, unit}."""
    try:
        df = pd.read_excel(xlsx, sheet_name="Macro_KPIs")
        df.columns = [str(c).strip() for c in df.columns]
        return df.to_dict("records")
    except Exception:
        return []


def _load_scored_signals() -> pd.DataFrame:
    """Load scored_signals.csv (forward-looking CEO/CFO quotes)."""
    path = _repo_root() / "earningscall_transcripts" / "scored_signals.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


def build_ad_market_graph(
    scope: str = "global",
    horizon_year: int = 2026,
    xlsx_path: str = "",
) -> dict[str, Any]:
    """Phase 1 — Build the ad-market knowledge graph.

    Returns a context dict with:
      graph:          networkx.DiGraph
      channel_ts:     {channel: {year: value_m}}
      groupm_ts:      GroupM baseline time series
      company_ad:     company ad revenue
      macro:          macro indicators
      signals:        scored_signals DataFrame
      horizon_year:   target forecast year
      scope:          'global' | 'channel' | 'company'
      baseline_growth: GroupM baseline growth % for horizon_year vs prior year
    """
    xlsx = xlsx_path or _load_workbook_path()

    # ── Load data ────────────────────────────────────────────────────
    agg = _load_global_adv_aggregates(xlsx)
    groupm = _load_groupm_channels(xlsx)
    company_ad = _load_company_ad_revenue(xlsx)
    macro = _load_macro_kpis(xlsx)
    signals = _load_scored_signals()

    # ── Build channel time series ────────────────────────────────────
    channel_ts: dict[str, dict[int, float]] = {}
    if not agg.empty:
        for ch in agg["channel"].unique():
            sub = agg[agg["channel"] == ch].sort_values("year")
            channel_ts[ch] = dict(zip(sub["year"].astype(int), sub["value_m"]))

    # ── Compute GroupM baseline growth for horizon_year ──────────────
    total_by_year: dict[int, float] = {}
    if not agg.empty:
        for yr, grp in agg.groupby("year"):
            total_by_year[int(yr)] = grp["value_m"].sum()

    baseline_growth = 0.0
    prior_year = horizon_year - 1
    if horizon_year in total_by_year and prior_year in total_by_year:
        prev = total_by_year[prior_year]
        if prev > 0:
            baseline_growth = ((total_by_year[horizon_year] / prev) - 1) * 100

    # ── Build networkx graph ─────────────────────────────────────────
    G = nx.DiGraph()

    # Channel nodes
    for ch, ts in channel_ts.items():
        recent = ts.get(2024) or ts.get(max(ts.keys(), default=2024))
        G.add_node(ch, type="channel", spend_2024_m=recent or 0)

    # Channel group edges (aggregation)
    for group_name, members in CHANNEL_GROUPS.items():
        G.add_node(group_name, type="channel_group")
        for member in members:
            if member in G:
                G.add_edge(member, group_name, relation="AGGREGATES_INTO")

    # Macro factor nodes
    for kpi in macro:
        name = str(kpi.get("indicator", "")).strip()
        if name:
            G.add_node(name, type="macro", value=kpi.get("value"), unit=kpi.get("unit"))
            # Macro factors DRIVE total ad spend
            G.add_edge(name, "Global Ad Spend", relation="DRIVES")

    G.add_node("Global Ad Spend", type="aggregate",
               value_2024_b=total_by_year.get(2024, 0) / 1000,
               baseline_growth_pct=baseline_growth)

    # Company nodes
    if not company_ad.empty:
        company_cols = [c for c in company_ad.columns if c != "Year"]
        for col in company_cols:
            company_name = col.replace("_Ads", "").replace("*", "").strip()
            latest_row = company_ad.dropna(subset=[col]).sort_values("Year", ascending=False)
            if not latest_row.empty:
                val = float(latest_row.iloc[0][col])
                G.add_node(company_name, type="company", ad_revenue_2024_b=val)
                G.add_edge(company_name, "Global Ad Spend", relation="CONTRIBUTES_TO")

    return {
        "graph": G,
        "channel_ts": channel_ts,
        "groupm_ts": groupm.to_dict("records") if not groupm.empty else [],
        "company_ad": company_ad.to_dict("records") if not company_ad.empty else [],
        "macro": macro,
        "signals": signals,
        "horizon_year": horizon_year,
        "scope": scope,
        "total_by_year": total_by_year,
        "baseline_growth": baseline_growth,
    }


# ════════════════════════════════════════════════════════════════════════
# Phase 2 — Persona Seeding
# ════════════════════════════════════════════════════════════════════════

def _pick_signal_quotes(signals: pd.DataFrame, role: str, n: int = 2) -> list[str]:
    """Pick relevant signal quotes for a persona role."""
    if signals.empty:
        return []
    # Match role to category bias
    role_to_cats = {
        "CPG Brand Marketer": ["Monetization", "User Behavior"],
        "Auto CMO": ["Investment", "Strategic Direction"],
        "Retail Media Buyer": ["Monetization", "Product Shifts"],
        "Agency Investment Director": ["Outlook", "Opportunities"],
        "Platform Sell-Side Exec": ["Monetization", "Product Shifts"],
        "CTV Publisher": ["Broadcaster Threats", "Opportunities"],
        "Institutional Portfolio Manager": ["Outlook", "Risks"],
        "Macro Strategist": ["Outlook", "Risks"],
        "Privacy Regulator": ["Risks", "Strategic Direction"],
        "Ad-Tech Skeptic": ["Risks", "Broadcaster Threats"],
    }
    cats = role_to_cats.get(role, ["Outlook"])
    if "category" in signals.columns:
        subset = signals[signals["category"].isin(cats)]
        if subset.empty:
            subset = signals
    else:
        subset = signals
    if "score" in subset.columns:
        subset = subset.sort_values("score", ascending=False)
    quotes = subset["quote"].dropna().head(n * 3).tolist()
    if len(quotes) > n:
        quotes = random.sample(quotes, n)
    return [str(q)[:300] for q in quotes]


def seed_ad_agents(
    context: dict[str, Any],
    n: int = 60,
) -> list[dict[str, Any]]:
    """Phase 2 — Generate N agent personas with ad-industry biases.

    Each agent: {id, role, geo_bias, channel_bias, macro_sensitivity, seed_quotes, memory}
    """
    agents: list[dict[str, Any]] = []
    signals = context.get("signals", pd.DataFrame())

    # Build a pool of (role, count) scaled to n
    total_weight = sum(PERSONA_ROLES.values())
    role_pool: list[str] = []
    for role, weight in PERSONA_ROLES.items():
        count = max(1, round(n * weight / total_weight))
        role_pool.extend([role] * count)
    random.shuffle(role_pool)
    role_pool = role_pool[:n]  # trim to exactly n

    geo_options = ["US-centric", "EU-centric", "APAC-centric", "Global", "LatAm-centric"]
    channel_options = list(CHANNEL_GROUPS.keys())

    for i in range(n):
        role = role_pool[i] if i < len(role_pool) else random.choice(list(PERSONA_ROLES.keys()))
        agent = {
            "id": i,
            "role": role,
            "geo_bias": random.choice(geo_options),
            "channel_bias": random.choice(channel_options),
            "macro_sensitivity": round(random.uniform(0.3, 1.0), 2),
            "seed_quotes": _pick_signal_quotes(signals, role, n=2),
            "memory": [],
        }
        agents.append(agent)

    return agents


# ════════════════════════════════════════════════════════════════════════
# Phase 3 — Simulation Loop
# ════════════════════════════════════════════════════════════════════════

def _build_agent_prompt(
    agent: dict,
    context: dict,
    social_feed: list[str],
    scenario: str,
    round_num: int,
) -> str:
    """Build the prompt for one agent's reaction in one round."""
    horizon = context["horizon_year"]
    baseline = context["baseline_growth"]
    total_2024 = context["total_by_year"].get(2024, 942_500)

    # Channel snapshot
    channel_snapshot = ""
    for group, members in CHANNEL_GROUPS.items():
        total = sum(
            context["channel_ts"].get(m, {}).get(2024, 0) for m in members
        )
        if total > 0:
            channel_snapshot += f"  {group}: ${total/1000:.1f}B\n"

    # Social feed (last round's agent statements)
    feed_text = ""
    if social_feed:
        feed_text = "\n".join(f"  - {s}" for s in social_feed[:8])

    seed_context = ""
    if agent["seed_quotes"]:
        seed_context = "Relevant CEO/CFO quotes you've read:\n" + "\n".join(
            f'  "{q}"' for q in agent["seed_quotes"]
        )

    return f"""You are a {agent['role']} with a {agent['geo_bias']} geographic bias and particular focus on {agent['channel_bias']}.
Your macro sensitivity is {agent['macro_sensitivity']:.0%} (1.0 = very sensitive to macro shifts).

CONTEXT — Global Ad Market {horizon} Forecast:
GroupM baseline: +{baseline:.1f}% growth vs {horizon-1} (total 2024: ${total_2024/1000:.0f}B)
Channel breakdown (2024):
{channel_snapshot}
Scenario: {scenario}

{seed_context}

{"Other market participants are saying:" + chr(10) + feed_text if feed_text else "This is the opening round — no prior statements from others."}

Round {round_num}: Give your forecast reaction for {horizon}.

FORMAT — respond with EXACTLY this structure:
GROWTH: +X.X%
CHANNELS: Search=+X, Social=+X, Video/CTV=+X, Display=+X, OOH=+X, Print=+X, Radio=+X, Other Digital=+X
COMMENT: 2-3 sentences with your biggest risk or tailwind and reasoning.

Rules for CHANNELS line: rate each from -5 (very bearish) to +5 (very bullish). Use 0 for neutral.
Respond ONLY in this format, no preamble."""


def _get_llm_client():
    """Get the shared OpenAI-compatible client (DeepSeek preferred, else OpenAI).

    Reuses the exact same resolution logic as Genie — no extra keys needed.
    """
    try:
        from utils.genie_ai import get_openai_client, _default_model
        return get_openai_client(), _default_model()
    except ImportError:
        pass
    # Fallback: try direct env vars
    import os
    try:
        from openai import OpenAI
    except ImportError:
        return None, ""
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if ds_key:
        return OpenAI(api_key=ds_key, base_url="https://api.deepseek.com"), "deepseek-chat"
    oai_key = os.environ.get("OPENAI_API_KEY", "")
    if oai_key:
        return OpenAI(api_key=oai_key), "gpt-4o-mini"
    return None, ""


def _call_llm_short(prompt: str, system: str = "") -> tuple[str, float]:
    """Call LLM for agent reactions (short output). Returns (text, cost_usd)."""
    client, model = _get_llm_client()
    if client is None:
        return "[No API key configured — set DEEPSEEK_API_KEY in .env or HF secrets]", 0.0
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=200,
            temperature=0.8,
        )
        text = response.choices[0].message.content or ""
        inp = getattr(response.usage, "prompt_tokens", 0) or 0
        out = getattr(response.usage, "completion_tokens", 0) or 0
        cost = (inp * DEEPSEEK_INPUT_COST) + (out * DEEPSEEK_OUTPUT_COST)
        return text.strip(), cost
    except Exception as e:
        return f"[Agent error: {e}]", 0.0


def _call_llm_long(prompt: str, system: str = "") -> tuple[str, float]:
    """Call LLM for report generation (longer output). Returns (text, cost_usd)."""
    client, model = _get_llm_client()
    if client is None:
        return "[No API key configured — set DEEPSEEK_API_KEY in .env or HF secrets]", 0.0
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000,
            temperature=0.4,
        )
        text = response.choices[0].message.content or ""
        inp = getattr(response.usage, "prompt_tokens", 0) or 0
        out = getattr(response.usage, "completion_tokens", 0) or 0
        cost = (inp * DEEPSEEK_INPUT_COST) + (out * DEEPSEEK_OUTPUT_COST)
        return text.strip(), cost
    except Exception as e:
        return f"[Report error: {e}]", 0.0


def _extract_growth_estimate(text: str) -> float | None:
    """Pull a growth % from agent text like '+4.8%' or '-1.2%'."""
    import re
    patterns = [
        r'([+-]?\d+\.?\d*)\s*%',
        r'growth.*?([+-]?\d+\.?\d*)',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                val = float(m.group(1))
                if -30 < val < 50:  # sanity bound
                    return val
            except ValueError:
                continue
    return None


def estimate_run_cost(n_agents: int, n_rounds: int) -> float:
    """Estimate cost before running. Returns USD (DeepSeek pricing)."""
    # Each agent produces ~150 output tokens per round, reads ~600 input tokens
    agent_calls = n_agents * n_rounds
    agent_cost = agent_calls * (600 * DEEPSEEK_INPUT_COST + 150 * DEEPSEEK_OUTPUT_COST)
    # One report call (longer)
    report_cost = 3000 * DEEPSEEK_INPUT_COST + 1500 * DEEPSEEK_OUTPUT_COST
    return agent_cost + report_cost


def run_ad_simulation(
    context: dict[str, Any],
    agents: list[dict[str, Any]],
    rounds: int = 5,
    scenario: str = "baseline",
    progress_callback: Any = None,
    statement_callback: Any = None,
) -> dict[str, Any]:
    """Phase 3 — Run K rounds of agent reactions.

    Returns:
      round_metrics: list of per-round {growth_estimates, mean, std, channel_mentions}
      total_cost:    cumulative Claude API cost
      all_statements: list of all agent statements
      aborted:       True if cost cap hit
    """
    # Resolve scenario text
    if scenario in SCENARIO_PRESETS:
        scenario_text = SCENARIO_PRESETS[scenario]
    else:
        scenario_text = scenario or SCENARIO_PRESETS["baseline"]

    round_metrics: list[dict[str, Any]] = []
    all_statements: list[dict[str, Any]] = []
    total_cost = 0.0
    social_feed: list[str] = []
    aborted = False

    for r in range(1, rounds + 1):
        round_estimates: list[float] = []
        round_statements: list[str] = []

        for agent in agents:
            # Cost guard
            if total_cost >= MAX_COST_PER_RUN:
                aborted = True
                break

            prompt = _build_agent_prompt(agent, context, social_feed, scenario_text, r)
            response, cost = _call_llm_short(prompt)
            total_cost += cost

            # Extract growth estimate
            growth = _extract_growth_estimate(response)
            if growth is not None:
                round_estimates.append(growth)

            # Store
            statement = f"[{agent['role']}|{agent['geo_bias']}] {response.strip()}"
            round_statements.append(statement)
            agent["memory"].append({"round": r, "statement": response.strip()})
            stmt_record = {
                "round": r,
                "agent_id": agent["id"],
                "role": agent["role"],
                "geo_bias": agent["geo_bias"],
                "channel_bias": agent["channel_bias"],
                "statement": response.strip(),
                "growth_estimate": growth,
                "cost": cost,
            }
            all_statements.append(stmt_record)

            # Fire per-statement callback for live feed
            if statement_callback:
                try:
                    statement_callback(stmt_record, len(all_statements), len(agents) * rounds)
                except Exception:
                    pass

        if aborted:
            break

        # Round aggregation
        mean_growth = np.mean(round_estimates) if round_estimates else 0.0
        std_growth = np.std(round_estimates) if len(round_estimates) > 1 else 0.0

        round_metrics.append({
            "round": r,
            "n_estimates": len(round_estimates),
            "growth_mean": float(mean_growth),
            "growth_std": float(std_growth),
            "growth_min": float(min(round_estimates)) if round_estimates else 0.0,
            "growth_max": float(max(round_estimates)) if round_estimates else 0.0,
        })

        # Social feed for next round — random sample of this round's statements
        social_feed = random.sample(
            round_statements, min(10, len(round_statements))
        )

        if progress_callback:
            try:
                progress_callback(r, rounds, round_metrics[-1], total_cost)
            except Exception:
                pass

    return {
        "round_metrics": round_metrics,
        "total_cost": total_cost,
        "all_statements": all_statements,
        "aborted": aborted,
    }


# ════════════════════════════════════════════════════════════════════════
# Phase 4 — Report Generation
# ════════════════════════════════════════════════════════════════════════

def generate_ad_report(
    context: dict[str, Any],
    agents: list[dict[str, Any]],
    sim_results: dict[str, Any],
    scope: str = "global",
    horizon_year: int = 2026,
) -> dict[str, Any]:
    """Phase 4 — Synthesize swarm output into a structured forecast report.

    Returns dict with:
      horizon, baseline_groupm_growth, mirofish_growth_mu, mirofish_growth_sigma,
      channel_deltas, top_tailwinds, top_headwinds, deviation_from_groupm,
      narrative, confidence, scenario_label, cost_usd
    """
    round_metrics = sim_results.get("round_metrics", [])
    all_statements = sim_results.get("all_statements", [])
    baseline = context.get("baseline_growth", 0.0)

    # ── Compute final crowd consensus ────────────────────────────────
    if round_metrics:
        # Weight later rounds more (convergence)
        weights = [0.5 + 0.5 * (i / (len(round_metrics) - 1)) if len(round_metrics) > 1 else 1.0
                   for i in range(len(round_metrics))]
        total_w = sum(weights)
        growth_mu = sum(r["growth_mean"] * w for r, w in zip(round_metrics, weights)) / total_w
        growth_sigma = round_metrics[-1]["growth_std"] if round_metrics else 0.0
    else:
        growth_mu = baseline
        growth_sigma = 0.0

    # ── Aggregate agent channel ratings (structured parsing) ────────
    # Parse the CHANNELS: line from each agent's structured response.
    # Format: "CHANNELS: Search=+3, Social=-1, Video/CTV=+2, ..."
    # Each rating is -5..+5; we normalize to -1..+1 by dividing by 5.
    import re as _re
    channel_ratings: dict[str, list[float]] = {g: [] for g in CHANNEL_GROUPS}
    for stmt in all_statements:
        text = str(stmt.get("statement", ""))
        # Find CHANNELS: line
        channels_match = _re.search(r"CHANNELS:\s*(.+?)(?:\n|$)", text, _re.IGNORECASE)
        if channels_match:
            pairs_text = channels_match.group(1)
            # Parse key=value pairs like "Search=+3"
            for pair in _re.finditer(r"(\w[\w/]*)\s*=\s*([+-]?\d+(?:\.\d+)?)", pairs_text):
                ch_name = pair.group(1).strip()
                rating = float(pair.group(2))
                # Match to closest channel group
                for group in CHANNEL_GROUPS:
                    if ch_name.lower().replace("/", "").replace(" ", "") in group.lower().replace("/", "").replace(" ", "") or \
                       group.lower().replace("/", "").replace(" ", "") in ch_name.lower().replace("/", "").replace(" ", ""):
                        channel_ratings[group].append(max(-5.0, min(5.0, rating)))
                        break

    channel_deltas: dict[str, float] = {}
    for group, ratings in channel_ratings.items():
        if ratings:
            # Average of all agent ratings for this channel, normalized to -1..+1
            channel_deltas[group] = round(sum(ratings) / (len(ratings) * 5.0), 3)
        else:
            channel_deltas[group] = 0.0

    # ── Build the LLM report prompt ──────────────────────────────────
    # Sample diverse agent statements for the report
    top_statements = []
    if all_statements:
        # Get last-round statements (most converged)
        last_round = max(s["round"] for s in all_statements)
        last_stmts = [s for s in all_statements if s["round"] == last_round]
        # Sample up to 15 diverse ones
        if len(last_stmts) > 15:
            last_stmts = random.sample(last_stmts, 15)
        top_statements = [f"[{s['role']}]: {s['statement']}" for s in last_stmts]

    report_prompt = f"""You are synthesizing a multi-agent advertising market forecast.

DATA:
- Target year: {horizon_year}
- GroupM baseline growth: +{baseline:.1f}%
- MiroFish crowd consensus growth: +{growth_mu:.1f}% (σ={growth_sigma:.1f}%)
- Deviation from GroupM: {growth_mu - baseline:+.1f}pp
- Total 2024 ad spend: ${context.get('total_by_year', {}).get(2024, 942500)/1000:.0f}B

CHANNEL SENTIMENT from {len(all_statements)} agent statements:
{json.dumps(channel_deltas, indent=2)}

SAMPLE AGENT STATEMENTS (final round):
{chr(10).join(top_statements[:12])}

TASK: Return a JSON object with exactly these keys:
{{
  "narrative": "3-4 sentence executive summary of the forecast",
  "top_tailwinds": ["tailwind 1", "tailwind 2", "tailwind 3", "tailwind 4", "tailwind 5"],
  "top_headwinds": ["headwind 1", "headwind 2", "headwind 3", "headwind 4", "headwind 5"],
  "channel_outlook": {{
    "Search": "1 sentence outlook",
    "Social": "1 sentence outlook",
    "Video/CTV": "1 sentence outlook",
    "Display": "1 sentence outlook",
    "Retail Media": "1 sentence outlook"
  }},
  "confidence_pct": 65
}}

Return ONLY valid JSON, no markdown fences, no extra text."""

    report_text, report_cost = _call_llm_long(report_prompt)
    total_cost = sim_results.get("total_cost", 0.0) + report_cost

    # ── Parse report JSON ────────────────────────────────────────────
    report_data: dict[str, Any] = {}
    try:
        # Strip markdown fences if present
        clean = report_text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        if clean.startswith("json"):
            clean = clean[4:].strip()
        report_data = json.loads(clean)
    except (json.JSONDecodeError, Exception):
        report_data = {
            "narrative": report_text[:500],
            "top_tailwinds": [],
            "top_headwinds": [],
            "channel_outlook": {},
            "confidence_pct": 50,
        }

    confidence = float(report_data.get("confidence_pct", 50)) / 100.0

    return {
        "horizon": horizon_year,
        "baseline_groupm_growth": float(baseline),
        "mirofish_growth_mu": float(growth_mu),
        "mirofish_growth_sigma": float(growth_sigma),
        "channel_deltas": channel_deltas,
        "top_tailwinds": report_data.get("top_tailwinds", []),
        "top_headwinds": report_data.get("top_headwinds", []),
        "channel_outlook": report_data.get("channel_outlook", {}),
        "deviation_from_groupm": float(growth_mu - baseline),
        "narrative": str(report_data.get("narrative", "")),
        "confidence": confidence,
        "scenario_label": sim_results.get("scenario_label", "custom"),
        "cost_usd": total_cost,
        "n_agents": len(agents),
        "n_rounds": len(round_metrics),
        "round_metrics": round_metrics,
    }


# ════════════════════════════════════════════════════════════════════════
# Phase 5 — Persistence
# ════════════════════════════════════════════════════════════════════════

def persist_mirofish_run(report: dict[str, Any], db_path: Path | None = None) -> Path:
    """Save a MiroFish run to the intelligence SQLite DB."""
    target = db_path or (_repo_root() / "earningscall_intelligence.db")
    target.parent.mkdir(parents=True, exist_ok=True)

    # Ensure schema
    conn = sqlite3.connect(str(target))
    try:
        import sys
        script_dir = _repo_root() / "scripts"
        if str(script_dir) not in sys.path:
            sys.path.insert(0, str(script_dir))
        from intelligence_db_schema import ensure_schema
        ensure_schema(conn)

        run_id = str(uuid.uuid4())[:12]
        conn.execute(
            """
            INSERT INTO mirofish_runs (
                run_id, created_at, scope, scope_key, horizon_year,
                agents, rounds, scenario, preset,
                graph_json, report_json,
                baseline_groupm_growth, mirofish_growth_mu, mirofish_growth_sigma,
                deviation_from_groupm, confidence, cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                datetime.utcnow().isoformat(),
                "global",
                "",
                report.get("horizon", 2026),
                report.get("n_agents", 0),
                report.get("n_rounds", 0),
                report.get("scenario_label", ""),
                report.get("scenario_label", ""),
                "",  # graph_json — omit for now, too large
                json.dumps(report, default=str),
                report.get("baseline_groupm_growth", 0),
                report.get("mirofish_growth_mu", 0),
                report.get("mirofish_growth_sigma", 0),
                report.get("deviation_from_groupm", 0),
                report.get("confidence", 0),
                report.get("cost_usd", 0),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return target


# ════════════════════════════════════════════════════════════════════════
# Convenience — Full pipeline
# ════════════════════════════════════════════════════════════════════════

def run_full_mirofish(
    horizon_year: int = 2026,
    n_agents: int = 60,
    n_rounds: int = 5,
    scenario: str = "baseline",
    xlsx_path: str = "",
    progress_callback: Any = None,
    statement_callback: Any = None,
) -> dict[str, Any]:
    """Run the full MiroFish pipeline: graph → agents → simulation → report.

    Returns the Phase 4 report dict, augmented with run metadata.
    """
    context = build_ad_market_graph(
        scope="global",
        horizon_year=horizon_year,
        xlsx_path=xlsx_path,
    )
    agents = seed_ad_agents(context, n=n_agents)
    sim = run_ad_simulation(
        context, agents,
        rounds=n_rounds,
        scenario=scenario,
        progress_callback=progress_callback,
        statement_callback=statement_callback,
    )
    sim["scenario_label"] = scenario
    report = generate_ad_report(
        context, agents, sim,
        scope="global",
        horizon_year=horizon_year,
    )

    # Persist
    try:
        persist_mirofish_run(report)
    except Exception:
        pass

    return report
