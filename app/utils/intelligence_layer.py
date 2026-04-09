"""
Intelligence Layer — Cross-source derived metrics engine.

Reads from Supabase (primary) and local scored_signals.csv to compute
derived metrics that NO single data source provides:

  1. Signal-to-Price Divergence   — transcript signals vs stock momentum
  2. Ad Channel Exposure Forecast — company ad rev × GroupM channel forecasts
  3. Institutional Conviction     — holder flows × signals × price direction
  4. Revenue per Employee         — operational efficiency trajectory
  5. Ad Dependency Ratio          — ad revenue / total revenue
  6. Market Concentration Delta   — duopoly share trend over time

All functions are company-agnostic: they work for any company present in the
data. When new companies are added to Supabase, metrics compute automatically.

Usage:
    from utils.intelligence_layer import compute_all_derived_metrics
    metrics = compute_all_derived_metrics()
    # metrics is a dict of DataFrames, one per metric type
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NORM_RE = None  # lazy-compiled


def _norm_company_key(text: str) -> str:
    """Lower, strip, remove punctuation for alias matching."""
    global _NORM_RE
    if _NORM_RE is None:
        import re
        _NORM_RE = re.compile(r"[^a-z0-9]")
    return _NORM_RE.sub("", text.lower())


# Import canonical aliases from oracle_engine if available, else inline a copy.
try:
    from utils.oracle_engine import (
        CANONICAL_COMPANY_ALIASES,
        canonical_company,
    )
except ImportError:
    CANONICAL_COMPANY_ALIASES = {
        "alphabet": "Alphabet", "alphabetgoogle": "Alphabet", "google": "Alphabet",
        "amazon": "Amazon", "apple": "Apple", "comcast": "Comcast",
        "disney": "Disney", "meta": "Meta Platforms", "metaplatforms": "Meta Platforms",
        "facebook": "Meta Platforms", "microsoft": "Microsoft", "netflix": "Netflix",
        "paramount": "Paramount Global", "paramountglobal": "Paramount Global",
        "roku": "Roku", "spotify": "Spotify",
        "warnerbrosdiscovery": "Warner Bros. Discovery",
        "warnerbros.discovery": "Warner Bros. Discovery",
        "samsung": "Samsung", "tencent": "Tencent",
    }

    def canonical_company(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return CANONICAL_COMPANY_ALIASES.get(_norm_company_key(text), text)


# ---------------------------------------------------------------------------
# Channel exposure mapping (manual, one-time — update when adding companies)
# Maps company → estimated % of ad revenue per channel.
# Channels must match Global_Adv_Aggregates metric_type values (after
# stripping " Worldwide" suffix).
# ---------------------------------------------------------------------------
CHANNEL_EXPOSURE: dict[str, dict[str, float]] = {
    "Alphabet": {
        "Search": 0.57, "Video": 0.16, "Display": 0.14,
        "Other Digital": 0.08, "Social": 0.05,
    },
    "Meta Platforms": {
        "Social": 0.70, "Video": 0.18, "Display": 0.12,
    },
    "Amazon": {
        "Search": 0.50, "Display": 0.30, "Video": 0.15,
        "Other Digital": 0.05,
    },
    "Apple": {
        "Search": 0.60, "Display": 0.25, "Other Digital": 0.15,
    },
    "Microsoft": {
        "Search": 0.65, "Display": 0.20, "Other Digital": 0.15,
    },
    "Disney": {
        "Video": 0.70, "Display": 0.20, "Other Digital": 0.10,
    },
    "Netflix": {
        "Video": 0.85, "Display": 0.15,
    },
    "Spotify": {
        "Radio": 0.70, "Display": 0.20, "Other Digital": 0.10,
    },
    "Roku": {
        "Video": 0.80, "Display": 0.20,
    },
    "Comcast": {
        "Video": 0.50, "TV": 0.30, "Display": 0.20,
    },
    "Warner Bros. Discovery": {
        "TV": 0.50, "Video": 0.30, "Display": 0.20,
    },
    "Paramount Global": {
        "TV": 0.55, "Video": 0.30, "Display": 0.15,
    },
}

# Mapping from aggregated channel groups in Global_Adv_Aggregates to our
# simplified channel keys.  The raw metric_type values have " Worldwide"
# stripped already (done by the loader), and include desktop/mobile splits
# we want to merge.
_CHANNEL_GROUP_MAP = {
    "Search Desktop": "Search",
    "Search Mobile": "Search",
    "Social Desktop": "Social",
    "Social Mobile": "Social",
    "Video Desktop": "Video",
    "Video Mobile": "Video",
    "Display Desktop": "Display",
    "Display Mobile": "Display",
    "Free TV": "TV",
    "Pay TV": "TV",
    "Radio": "Radio",
    "Traditional OOH": "OOH",
    "Digital OOH": "OOH",
    "Cinema": "Cinema",
    "Newspaper": "Print",
    "Magazine": "Print",
    "Other Desktop": "Other Digital",
    "Other Mobile": "Other Digital",
}


# ---------------------------------------------------------------------------
# Data loaders — Supabase primary, SQLite + Workbook fallback
# ---------------------------------------------------------------------------

def _sqlite_db_path() -> Path | None:
    """Return path to earningscall_intelligence.db if it exists."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "earningscall_intelligence.db",
        Path("/tmp/replit_revival_data/earningscall_intelligence.db"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _read_sqlite_table(query: str, params: tuple = ()) -> pd.DataFrame:
    """Read from SQLite intelligence DB. Returns empty DataFrame on failure."""
    import sqlite3
    db = _sqlite_db_path()
    if not db:
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(str(db))
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def _load_workbook():
    """Load workbook via resolve_financial_data_xlsx (returns path or None)."""
    try:
        from utils.workbook_source import resolve_financial_data_xlsx
        return resolve_financial_data_xlsx()
    except Exception:
        return None


def _load_financial_metrics() -> pd.DataFrame:
    """Load annual financial metrics — Supabase first, then SQLite, then Workbook."""
    # Try Supabase
    try:
        from utils.supabase_client import is_configured, fetch_table_paginated
        if is_configured():
            df = fetch_table_paginated("financial_metrics_yearly", order="year.asc")
            if not df.empty:
                df.columns = [str(c).strip().lower() for c in df.columns]
                df["company"] = df["company"].apply(canonical_company)
                for col in ["year", "revenue", "operating_income", "net_income",
                             "cost_of_revenue", "rd", "capex", "total_assets",
                             "market_cap", "cash_balance", "debt"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                return df
    except Exception:
        pass

    # Fallback: SQLite company_metrics table
    df = _read_sqlite_table("SELECT * FROM company_metrics ORDER BY year ASC")
    if not df.empty:
        df.columns = [str(c).strip().lower() for c in df.columns]
        if "company" in df.columns:
            df["company"] = df["company"].apply(canonical_company)
        for col in ["year", "revenue", "operating_income", "net_income",
                     "cost_of_revenue", "r_and_d", "capex", "total_assets",
                     "market_cap", "cash_balance", "debt"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # Alias r_and_d → rd for downstream compatibility
        if "r_and_d" in df.columns and "rd" not in df.columns:
            df["rd"] = df["r_and_d"]
        return df

    return pd.DataFrame()


def _load_employees() -> pd.DataFrame:
    """Load employee data — Supabase first, then SQLite."""
    # Try Supabase
    try:
        from utils.supabase_client import is_configured, fetch_table_paginated
        if is_configured():
            df = fetch_table_paginated("company_employees", order="year.asc")
            if not df.empty:
                df.columns = [str(c).strip().lower() for c in df.columns]
                df["company"] = df["company"].apply(canonical_company)
                df["year"] = pd.to_numeric(df["year"], errors="coerce")
                df["employee_count"] = pd.to_numeric(
                    df.get("employee_count", df.get("employees")), errors="coerce"
                )
                return df
    except Exception:
        pass

    # Fallback: SQLite (company_metrics has employee_count)
    df = _read_sqlite_table(
        "SELECT company, year, employee_count FROM company_metrics "
        "WHERE employee_count IS NOT NULL ORDER BY year ASC"
    )
    if not df.empty:
        df["company"] = df["company"].apply(canonical_company)
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df["employee_count"] = pd.to_numeric(df["employee_count"], errors="coerce")
        return df

    return pd.DataFrame()


def _load_ad_revenue() -> pd.DataFrame:
    """Load company advertising revenue — Supabase first, then SQLite."""
    # Try Supabase
    try:
        from utils.supabase_client import is_configured, fetch_table_paginated
        if is_configured():
            df = fetch_table_paginated("company_advertising_revenue", order="year.asc")
            if not df.empty:
                df.columns = [str(c).strip().lower() for c in df.columns]
                if "advertising_revenue_b" in df.columns and "company" in df.columns:
                    df["company"] = df["company"].apply(canonical_company)
                    df["year"] = pd.to_numeric(df["year"], errors="coerce")
                    df["ad_revenue_b"] = pd.to_numeric(df["advertising_revenue_b"], errors="coerce")
                elif "year" in df.columns:
                    id_col = "year"
                    value_cols = [c for c in df.columns if c != id_col]
                    df = df.melt(id_vars=[id_col], value_vars=value_cols,
                                 var_name="company", value_name="ad_revenue_b")
                    df["company"] = df["company"].apply(canonical_company)
                    df["year"] = pd.to_numeric(df["year"], errors="coerce")
                    df["ad_revenue_b"] = pd.to_numeric(df["ad_revenue_b"], errors="coerce")
                return df
    except Exception:
        pass

    # Fallback: SQLite (company_metrics has advertising_revenue in $M)
    df = _read_sqlite_table(
        "SELECT company, year, advertising_revenue FROM company_metrics "
        "WHERE advertising_revenue IS NOT NULL ORDER BY year ASC"
    )
    if not df.empty:
        df["company"] = df["company"].apply(canonical_company)
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        # advertising_revenue in SQLite is $M, convert to $B
        df["ad_revenue_b"] = pd.to_numeric(df["advertising_revenue"], errors="coerce") / 1000.0
        return df

    return pd.DataFrame()


def _load_stock_daily() -> pd.DataFrame:
    """Load daily stock prices from Supabase."""
    try:
        from utils.supabase_client import is_configured, fetch_table_paginated
        if not is_configured():
            return pd.DataFrame()
        df = fetch_table_paginated(
            "stock_daily",
            select="date,asset,tag,price,market_cap,change_pct",
            order="date.asc",
            max_rows=80_000,
        )
        if df.empty:
            return df
        try:
            from utils.workbook_market_data import infer_company_label
            df["company"] = [
                canonical_company(infer_company_label(str(a), str(t)))
                for a, t in zip(df.get("asset", []), df.get("tag", []))
            ]
        except ImportError:
            df["company"] = df.get("asset", df.get("tag", "")).apply(canonical_company)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["market_cap"] = pd.to_numeric(df.get("market_cap"), errors="coerce")
        df = df.dropna(subset=["date", "price"]).copy()
        df = df[df["company"].astype(str).str.strip() != ""].copy()
        return df.sort_values(["company", "date"]).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _load_holders() -> pd.DataFrame:
    """Load institutional holder data from Supabase."""
    try:
        from utils.supabase_client import is_configured, fetch_table_paginated
        if not is_configured():
            return pd.DataFrame()
        df = fetch_table_paginated("holders", order="date_fetched.desc")
        if df.empty:
            return df
        df.columns = [str(c).strip().lower() for c in df.columns]
        df["company"] = df.get("company", df.get("ticker", "")).apply(canonical_company)
        df["date_fetched"] = pd.to_datetime(df.get("date_fetched"), errors="coerce")
        for col in ["shares", "value_usd", "pct_out"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def _load_global_adv_aggregates() -> pd.DataFrame:
    """Load global advertising aggregates (GroupM channel data) — Supabase first, then Workbook."""
    # Try Supabase
    try:
        from utils.supabase_client import is_configured, fetch_table_paginated
        if is_configured():
            df = fetch_table_paginated("global_adv_aggregates", order="year.asc")
            if not df.empty:
                df.columns = [str(c).strip().lower() for c in df.columns]
                df["year"] = pd.to_numeric(df["year"], errors="coerce")
                df["value"] = pd.to_numeric(df["value"], errors="coerce")
                if "metric_type" in df.columns:
                    df["metric_type"] = (
                        df["metric_type"]
                        .astype(str)
                        .str.replace(" Worldwide", "", regex=False)
                        .str.strip()
                    )
                return df
    except Exception:
        pass

    # Fallback: read from Workbook
    wb = _load_workbook()
    if wb:
        try:
            df = pd.read_excel(wb, sheet_name="Global_Adv_Aggregates")
            df.columns = [str(c).strip().lower() for c in df.columns]
            df["year"] = pd.to_numeric(df["year"], errors="coerce")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            if "metric_type" in df.columns:
                df["metric_type"] = (
                    df["metric_type"]
                    .astype(str)
                    .str.replace(" Worldwide", "", regex=False)
                    .str.strip()
                )
            return df
        except Exception:
            pass

    return pd.DataFrame()


def _load_scored_signals() -> pd.DataFrame:
    """Load scored transcript signals from local CSV."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent
        / "earningscall_transcripts" / "scored_signals.csv",
        Path("/tmp/replit_revival_data/scored_signals.csv"),
    ]
    for path in candidates:
        if path.exists():
            try:
                df = pd.read_csv(path)
                df["company"] = df["company"].apply(canonical_company)
                df["year"] = pd.to_numeric(df["year"], errors="coerce")
                df["score"] = pd.to_numeric(df["score"], errors="coerce")
                return df
            except Exception:
                continue
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Derived metric computations
# ---------------------------------------------------------------------------

def compute_signal_velocity(signals: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-company signal velocity from scored_signals.csv.

    Returns DataFrame: company | signal_velocity | signal_direction | signal_strength | n_signals
    """
    if signals.empty:
        return pd.DataFrame(columns=["company", "signal_velocity", "signal_direction",
                                      "signal_strength", "n_signals"])

    # Polarity by category
    polarity_map = {
        "Investment": 0.85, "Monetization": 0.85, "Opportunities": 0.75,
        "Strategic Direction": 0.65, "Product Shifts": 0.55, "User Behavior": 0.35,
        "Outlook": 0.20, "Risks": -0.95, "Broadcaster Threats": -1.00,
    }
    signals = signals.copy()
    signals["polarity"] = signals["category"].map(polarity_map).fillna(0.0)
    signals["signed_score"] = signals["score"] * signals["polarity"]

    rows = []
    for company, group in signals.groupby("company"):
        if group.empty or len(group) < 3:
            continue
        # Yearly aggregated signal strength
        yearly = group.groupby("year")["signed_score"].mean().sort_index()
        if len(yearly) < 2:
            strength = float(yearly.iloc[-1]) if len(yearly) else 0.0
            velocity = 0.0
        else:
            strength = float(yearly.iloc[-1])
            velocity = float(yearly.iloc[-1] - yearly.iloc[-2])

        # Normalize to -1..+1
        velocity_norm = float(np.tanh(velocity / 3.0))
        strength_norm = float(np.tanh(strength / 5.0))

        direction = "bullish" if velocity_norm > 0.1 else ("bearish" if velocity_norm < -0.1 else "neutral")
        rows.append({
            "company": company,
            "signal_velocity": round(velocity_norm, 3),
            "signal_direction": direction,
            "signal_strength": round(strength_norm, 3),
            "n_signals": int(len(group)),
        })

    return pd.DataFrame(rows)


def compute_price_momentum(daily: pd.DataFrame, lookback_days: int = 60) -> pd.DataFrame:
    """
    Compute per-company stock price momentum over lookback_days.

    Returns DataFrame: company | price_momentum | price_direction | latest_price | latest_date
    """
    if daily.empty:
        return pd.DataFrame(columns=["company", "price_momentum", "price_direction",
                                      "latest_price", "latest_date"])

    rows = []
    for company, group in daily.groupby("company"):
        group = group.sort_values("date").drop_duplicates(subset=["date"], keep="last")
        if len(group) < 10:
            continue
        latest = group.iloc[-1]
        lookback_date = latest["date"] - pd.Timedelta(days=lookback_days)
        past = group[group["date"] <= lookback_date]
        if past.empty:
            past_price = group.iloc[0]["price"]
        else:
            past_price = past.iloc[-1]["price"]

        if past_price and past_price > 0:
            momentum = (latest["price"] - past_price) / past_price
        else:
            momentum = 0.0

        # Normalize to -1..+1 using tanh
        momentum_norm = float(np.tanh(momentum * 5.0))  # 20% return → ~0.76
        direction = "up" if momentum_norm > 0.05 else ("down" if momentum_norm < -0.05 else "flat")

        rows.append({
            "company": company,
            "price_momentum": round(momentum_norm, 3),
            "price_direction": direction,
            "latest_price": round(float(latest["price"]), 2),
            "latest_date": latest["date"].strftime("%Y-%m-%d") if pd.notna(latest["date"]) else "",
        })

    return pd.DataFrame(rows)


def compute_signal_price_divergence(
    signal_vel: pd.DataFrame,
    price_mom: pd.DataFrame,
) -> pd.DataFrame:
    """
    Metric 1: Signal-to-Price Divergence.

    divergence = signal_velocity - price_momentum
    Positive → signals ahead of market (potential upside)
    Negative → market pricing more than signals suggest (potential overvaluation)

    Returns DataFrame: company | signal_velocity | price_momentum | divergence | interpretation
    """
    if signal_vel.empty or price_mom.empty:
        return pd.DataFrame()

    merged = signal_vel.merge(price_mom, on="company", how="inner")
    merged["divergence"] = (merged["signal_velocity"] - merged["price_momentum"]).round(3)

    def interpret(row):
        d = row["divergence"]
        if d > 0.4:
            return "Strong: signals well ahead of market price — potential underpricing"
        if d > 0.15:
            return "Moderate: signals slightly ahead of market"
        if d < -0.4:
            return "Strong: market pricing ahead of signals — potential overvaluation"
        if d < -0.15:
            return "Moderate: market slightly ahead of signals"
        return "Aligned: signals and price momentum in agreement"

    merged["interpretation"] = merged.apply(interpret, axis=1)
    return merged[["company", "signal_velocity", "signal_direction",
                    "price_momentum", "price_direction", "divergence",
                    "interpretation", "latest_price", "latest_date"]].sort_values(
        "divergence", ascending=False
    ).reset_index(drop=True)


def compute_channel_exposure_forecast(
    ad_revenue: pd.DataFrame,
    global_agg: pd.DataFrame,
    forecast_year: int = 2026,
) -> pd.DataFrame:
    """
    Metric 2: Ad Channel Exposure Forecast.

    For each company with a known channel exposure map, compute:
    - channel_mix_growth: weighted average of GroupM channel growth forecasts
    - company_ad_cagr: actual historical ad revenue CAGR
    - alpha: company_ad_cagr - channel_mix_growth (company-specific outperformance)

    Returns DataFrame: company | channel_mix_growth | company_ad_cagr | alpha | channel_detail | interpretation
    """
    if global_agg.empty:
        return pd.DataFrame()

    # Compute channel growth rates from GroupM data
    # Use last available year as base and forecast_year as target
    agg = global_agg.copy()
    agg["channel"] = agg["metric_type"].map(_CHANNEL_GROUP_MAP)
    agg = agg.dropna(subset=["channel", "year", "value"])
    agg = agg[agg["value"] > 0]

    # Aggregate desktop + mobile into unified channels
    channel_yearly = agg.groupby(["channel", "year"])["value"].sum().reset_index()

    # Get base year (latest available before forecast) and forecast year
    available_years = sorted(channel_yearly["year"].dropna().unique())
    base_year = max(y for y in available_years if y < forecast_year) if any(y < forecast_year for y in available_years) else None
    if base_year is None or forecast_year not in available_years:
        # Can't compute forecast — need both years in data
        return pd.DataFrame()

    base = channel_yearly[channel_yearly["year"] == base_year].set_index("channel")["value"]
    target = channel_yearly[channel_yearly["year"] == forecast_year].set_index("channel")["value"]

    channel_growth = {}
    for ch in base.index:
        if ch in target.index and base[ch] > 0:
            years_diff = forecast_year - base_year
            if years_diff > 0:
                cagr = (target[ch] / base[ch]) ** (1.0 / years_diff) - 1.0
            else:
                cagr = 0.0
            channel_growth[ch] = round(cagr * 100, 2)

    if not channel_growth:
        return pd.DataFrame()

    # Compute company-level ad revenue CAGR
    company_cagr: dict[str, float] = {}
    if not ad_revenue.empty:
        for company, group in ad_revenue.groupby("company"):
            group = group.dropna(subset=["ad_revenue_b"]).sort_values("year")
            if len(group) < 2:
                continue
            first = group.iloc[0]
            last = group.iloc[-1]
            years = last["year"] - first["year"]
            if years > 0 and first["ad_revenue_b"] > 0:
                cagr = (last["ad_revenue_b"] / first["ad_revenue_b"]) ** (1.0 / years) - 1.0
                company_cagr[company] = round(cagr * 100, 2)

    # Compute channel-mix weighted growth per company
    rows = []
    for company, exposure in CHANNEL_EXPOSURE.items():
        mix_growth = 0.0
        channel_detail = {}
        for ch, weight in exposure.items():
            ch_growth = channel_growth.get(ch, 0.0)
            contribution = weight * ch_growth
            mix_growth += contribution
            channel_detail[ch] = {
                "exposure_pct": round(weight * 100, 1),
                "channel_growth_pct": ch_growth,
                "contribution_pp": round(contribution, 2),
            }

        actual_cagr = company_cagr.get(company)
        alpha = round(actual_cagr - mix_growth, 2) if actual_cagr is not None else None

        interpretation = ""
        if alpha is not None:
            if alpha > 2.0:
                interpretation = f"Outperforming channel mix by {alpha:+.1f}pp — gaining market share"
            elif alpha > 0:
                interpretation = f"Slightly above channel mix ({alpha:+.1f}pp) — holding share"
            elif alpha > -2.0:
                interpretation = f"Slightly below channel mix ({alpha:+.1f}pp) — losing some share"
            else:
                interpretation = f"Underperforming channel mix by {alpha:.1f}pp — losing market share"
        else:
            interpretation = "No historical ad revenue CAGR available for comparison"

        rows.append({
            "company": company,
            "channel_mix_growth_pct": round(mix_growth, 2),
            "company_ad_cagr_pct": actual_cagr,
            "alpha_pp": alpha,
            "channel_detail": channel_detail,
            "interpretation": interpretation,
        })

    return pd.DataFrame(rows).sort_values("alpha_pp", ascending=False, na_position="last").reset_index(drop=True)


def compute_institutional_conviction(
    holders: pd.DataFrame,
    signal_vel: pd.DataFrame,
    price_mom: pd.DataFrame,
) -> pd.DataFrame:
    """
    Metric 3: Institutional Conviction Alignment.

    Compares institutional ownership signals with transcript signals and price direction.

    Returns DataFrame: company | top_holders | holder_concentration | holder_signal_alignment | interpretation
    """
    if holders.empty:
        return pd.DataFrame()

    rows = []
    for company, group in holders.groupby("company"):
        if group.empty:
            continue

        # Get latest snapshot
        latest_date = group["date_fetched"].max()
        latest = group[group["date_fetched"] == latest_date].copy()

        # Top 5 holders by value
        latest_sorted = latest.sort_values("value_usd", ascending=False).head(5)
        top_holders = [
            {
                "name": str(row.get("holder_name", "Unknown")),
                "pct": round(float(row.get("pct_out", 0) or 0), 2),
                "value_usd": float(row.get("value_usd", 0) or 0),
            }
            for _, row in latest_sorted.iterrows()
        ]

        total_top5_pct = sum(h["pct"] for h in top_holders)

        # Check for multi-date data (weekly snapshots)
        unique_dates = group["date_fetched"].dropna().nunique()
        holder_trend = "unknown"
        if unique_dates >= 2:
            # Compare latest vs earliest snapshot
            earliest_date = group["date_fetched"].min()
            earliest = group[group["date_fetched"] == earliest_date]
            earliest_total = earliest["value_usd"].sum()
            latest_total = latest["value_usd"].sum()
            if earliest_total > 0:
                change = (latest_total - earliest_total) / earliest_total
                if change > 0.02:
                    holder_trend = "accumulating"
                elif change < -0.02:
                    holder_trend = "reducing"
                else:
                    holder_trend = "stable"

        # Cross-reference with signal and price direction
        sig_row = signal_vel[signal_vel["company"] == company]
        price_row = price_mom[price_mom["company"] == company]

        sig_dir = sig_row.iloc[0]["signal_direction"] if not sig_row.empty else "unknown"
        price_dir = price_row.iloc[0]["price_direction"] if not price_row.empty else "unknown"

        # Determine alignment
        directions = [holder_trend, sig_dir, price_dir]
        positive = sum(1 for d in directions if d in ("accumulating", "bullish", "up"))
        negative = sum(1 for d in directions if d in ("reducing", "bearish", "down"))

        if positive >= 2 and negative == 0:
            alignment = "strong_aligned_bullish"
            interpretation = "Institutions, signals, and price all pointing positive — high conviction"
        elif negative >= 2 and positive == 0:
            alignment = "strong_aligned_bearish"
            interpretation = "Institutions, signals, and price all pointing negative — bearish conviction"
        elif holder_trend == "accumulating" and sig_dir == "bullish" and price_dir in ("down", "flat"):
            alignment = "smart_money_divergent"
            interpretation = "Institutions accumulating despite flat/down price while signals bullish — contrarian opportunity"
        elif holder_trend == "reducing" and sig_dir == "bullish":
            alignment = "institutions_divergent"
            interpretation = "Institutions reducing despite bullish signals — watch for risk they see that signals miss"
        else:
            alignment = "mixed"
            interpretation = f"Mixed signals: holders {holder_trend}, signals {sig_dir}, price {price_dir}"

        rows.append({
            "company": company,
            "top_holders": top_holders,
            "top5_ownership_pct": round(total_top5_pct, 2),
            "holder_trend": holder_trend,
            "holder_snapshots": unique_dates,
            "signal_direction": sig_dir,
            "price_direction": price_dir,
            "alignment": alignment,
            "interpretation": interpretation,
        })

    return pd.DataFrame(rows).sort_values("top5_ownership_pct", ascending=False).reset_index(drop=True)


def compute_revenue_per_employee(
    metrics: pd.DataFrame,
    employees: pd.DataFrame,
) -> pd.DataFrame:
    """
    Revenue per Employee trajectory.

    Returns DataFrame: company | year | revenue_m | employees | rev_per_employee | yoy_change_pct
    """
    if metrics.empty or employees.empty:
        return pd.DataFrame()

    merged = metrics[["company", "year", "revenue"]].merge(
        employees[["company", "year", "employee_count"]],
        on=["company", "year"],
        how="inner",
    )
    merged = merged.dropna(subset=["revenue", "employee_count"])
    merged = merged[merged["employee_count"] > 0].copy()
    merged["rev_per_employee"] = (merged["revenue"] / merged["employee_count"]).round(2)
    merged = merged.sort_values(["company", "year"])

    # Compute YoY change
    merged["yoy_change_pct"] = merged.groupby("company")["rev_per_employee"].pct_change() * 100
    merged["yoy_change_pct"] = merged["yoy_change_pct"].round(1)

    return merged.reset_index(drop=True)


def compute_ad_dependency(
    metrics: pd.DataFrame,
    ad_revenue: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ad Dependency Ratio: ad_revenue / total_revenue.

    Returns DataFrame: company | year | revenue_m | ad_revenue_b | ad_dependency_pct
    """
    if metrics.empty or ad_revenue.empty:
        return pd.DataFrame()

    # Ensure ad revenue is in millions to match
    ad = ad_revenue.copy()
    ad["ad_revenue_m"] = ad["ad_revenue_b"] * 1000  # Convert $B to $M

    merged = metrics[["company", "year", "revenue"]].merge(
        ad[["company", "year", "ad_revenue_m"]],
        on=["company", "year"],
        how="inner",
    )
    merged = merged.dropna(subset=["revenue", "ad_revenue_m"])
    merged = merged[merged["revenue"] > 0].copy()
    merged["ad_dependency_pct"] = ((merged["ad_revenue_m"] / merged["revenue"]) * 100).round(1)

    return merged.sort_values(["company", "year"]).reset_index(drop=True)


def compute_market_concentration(
    ad_revenue: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ad Market Concentration Delta: duopoly (Alphabet+Meta) share over time.

    Returns DataFrame: year | total_market_b | duopoly_share_pct | top5_share_pct | hhi
    """
    if ad_revenue.empty:
        return pd.DataFrame()

    yearly = ad_revenue.groupby("year").agg(
        total=("ad_revenue_b", "sum"),
    ).reset_index()

    duopoly = ad_revenue[ad_revenue["company"].isin(["Alphabet", "Meta Platforms"])].groupby("year")["ad_revenue_b"].sum().reset_index()
    duopoly.columns = ["year", "duopoly_b"]

    merged = yearly.merge(duopoly, on="year", how="left")
    merged["duopoly_share_pct"] = ((merged["duopoly_b"] / merged["total"]) * 100).round(1)

    # HHI per year
    hhi_rows = []
    for year, group in ad_revenue.groupby("year"):
        total = group["ad_revenue_b"].sum()
        if total > 0:
            shares = (group["ad_revenue_b"] / total)
            hhi = (shares ** 2).sum()
            hhi_rows.append({"year": year, "hhi": round(hhi, 4)})

    hhi_df = pd.DataFrame(hhi_rows)
    if not hhi_df.empty:
        merged = merged.merge(hhi_df, on="year", how="left")

    return merged.sort_values("year").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Text summary generator (for Genie injection)
# ---------------------------------------------------------------------------

def generate_genie_summary(metrics: dict[str, pd.DataFrame]) -> str:
    """
    Generate a compact text summary of all derived metrics for injection
    into Genie's system prompt.

    Returns a string block suitable for appending to the AI context.
    """
    lines = ["INTELLIGENCE LAYER — Cross-source derived metrics (auto-computed):\n"]

    # 1. Signal-to-Price Divergence
    spd = metrics.get("signal_price_divergence")
    if spd is not None and not spd.empty:
        lines.append("SIGNAL-TO-PRICE DIVERGENCE (transcript signals vs stock momentum):")
        for _, row in spd.iterrows():
            lines.append(
                f"  {row['company']}: signal {row['signal_velocity']:+.2f} ({row['signal_direction']}), "
                f"price {row['price_momentum']:+.2f} ({row['price_direction']}), "
                f"divergence {row['divergence']:+.2f} → {row['interpretation']}"
            )
        lines.append("")

    # 2. Channel Exposure Forecast
    cef = metrics.get("channel_exposure_forecast")
    if cef is not None and not cef.empty:
        lines.append("AD CHANNEL EXPOSURE FORECAST (company ad revenue weighted by GroupM channel growth):")
        for _, row in cef.iterrows():
            cagr_str = f"{row['company_ad_cagr_pct']:.1f}%" if row['company_ad_cagr_pct'] is not None else "N/A"
            alpha_str = f"{row['alpha_pp']:+.1f}pp" if row['alpha_pp'] is not None else "N/A"
            lines.append(
                f"  {row['company']}: channel-mix growth {row['channel_mix_growth_pct']:.1f}%, "
                f"actual CAGR {cagr_str}, alpha {alpha_str}"
            )
        lines.append("")

    # 3. Institutional Conviction
    ic = metrics.get("institutional_conviction")
    if ic is not None and not ic.empty:
        lines.append("INSTITUTIONAL CONVICTION ALIGNMENT:")
        for _, row in ic.iterrows():
            top_name = row["top_holders"][0]["name"] if row["top_holders"] else "Unknown"
            lines.append(
                f"  {row['company']}: top holder {top_name} ({row['top5_ownership_pct']:.1f}% top-5), "
                f"trend {row['holder_trend']}, alignment: {row['alignment']}"
            )
        lines.append("")

    # 4. Revenue per Employee (latest year only)
    rpe = metrics.get("revenue_per_employee")
    if rpe is not None and not rpe.empty:
        latest_year = rpe["year"].max()
        latest = rpe[rpe["year"] == latest_year].sort_values("rev_per_employee", ascending=False)
        lines.append(f"REVENUE PER EMPLOYEE ({int(latest_year)}):")
        for _, row in latest.head(14).iterrows():
            yoy = f" ({row['yoy_change_pct']:+.1f}% YoY)" if pd.notna(row['yoy_change_pct']) else ""
            # rev_per_employee is already in $M/employee (revenue is in $M)
            lines.append(
                f"  {row['company']}: ${row['rev_per_employee']:.2f}M/employee{yoy}"
            )
        lines.append("")

    # 5. Ad Dependency (latest year)
    ad_dep = metrics.get("ad_dependency")
    if ad_dep is not None and not ad_dep.empty:
        latest_year = ad_dep["year"].max()
        latest = ad_dep[ad_dep["year"] == latest_year].sort_values("ad_dependency_pct", ascending=False)
        lines.append(f"AD DEPENDENCY RATIO ({int(latest_year)}):")
        for _, row in latest.iterrows():
            lines.append(
                f"  {row['company']}: {row['ad_dependency_pct']:.1f}% of revenue from advertising"
            )
        lines.append("")

    # 6. Market Concentration
    mc = metrics.get("market_concentration")
    if mc is not None and not mc.empty:
        recent = mc.tail(3)
        lines.append("AD MARKET CONCENTRATION (Alphabet + Meta duopoly share):")
        for _, row in recent.iterrows():
            hhi_str = f", HHI {row['hhi']:.3f}" if pd.notna(row.get('hhi')) else ""
            lines.append(
                f"  {int(row['year'])}: duopoly {row['duopoly_share_pct']:.1f}%{hhi_str}"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def compute_all_derived_metrics(forecast_year: int = 2026) -> dict[str, pd.DataFrame]:
    """
    Compute all cross-source derived metrics.

    Returns dict of:
      signal_price_divergence   — per company
      channel_exposure_forecast — per company with channel mapping
      institutional_conviction  — per company
      revenue_per_employee      — per company per year
      ad_dependency             — per company per year
      market_concentration      — per year
      _genie_summary            — text string for Genie injection
    """
    # Load all data sources
    fin_metrics = _load_financial_metrics()
    employees = _load_employees()
    ad_revenue = _load_ad_revenue()
    daily = _load_stock_daily()
    holders = _load_holders()
    global_agg = _load_global_adv_aggregates()
    signals = _load_scored_signals()

    # Intermediate computations
    signal_vel = compute_signal_velocity(signals)
    price_mom = compute_price_momentum(daily)

    # Derived metrics
    result: dict[str, Any] = {}

    result["signal_price_divergence"] = compute_signal_price_divergence(signal_vel, price_mom)
    result["channel_exposure_forecast"] = compute_channel_exposure_forecast(ad_revenue, global_agg, forecast_year)
    result["institutional_conviction"] = compute_institutional_conviction(holders, signal_vel, price_mom)
    result["revenue_per_employee"] = compute_revenue_per_employee(fin_metrics, employees)
    result["ad_dependency"] = compute_ad_dependency(fin_metrics, ad_revenue)
    result["market_concentration"] = compute_market_concentration(ad_revenue)

    # Generate text summary for Genie
    result["_genie_summary"] = generate_genie_summary(result)

    return result
