"""
Revenue Simulator — YTD and quarterly revenue estimation.

Estimates current-year revenue per company by extrapolating the latest
quarterly run-rate, adjusted by earnings-call signal momentum.

Usage:
    from utils.revenue_simulator import estimate_revenue
    result = estimate_revenue("Alphabet", excel_path, source_stamp)
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


# Ticker → canonical company name
_TICKER_TO_COMPANY = {
    "GOOGL": "Alphabet", "GOOG": "Alphabet",
    "AMZN": "Amazon", "AAPL": "Apple",
    "CMCSA": "Comcast", "DIS": "Disney",
    "META": "Meta Platforms", "MSFT": "Microsoft",
    "NFLX": "Netflix", "PARA": "Paramount Global",
    "ROKU": "Roku", "SPOT": "Spotify",
    "WBD": "Warner Bros. Discovery",
    "005930.KS": "Samsung", "TCEHY": "Tencent",
}
_COMPANY_TO_TICKER = {v: k for k, v in _TICKER_TO_COMPANY.items()}
# Prefer primary tickers
_COMPANY_TO_TICKER.update({
    "Alphabet": "GOOGL", "Meta Platforms": "META",
})


def _safe_float(v) -> float | None:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _load_quarterly_data(excel_path: str) -> pd.DataFrame:
    """Load quarterly revenue from Company_Quarterly_KPI sheet."""
    import re
    try:
        df = pd.read_excel(excel_path, sheet_name="Company_Quarterly_KPI")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {c: re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in df.columns}
    df = df.rename(columns=rename)
    if "ticker" not in df.columns or "year" not in df.columns:
        return pd.DataFrame()

    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["ticker", "year"]).copy()
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["year"].astype(int)
    df = df.sort_index().copy()
    df["quarter"] = df.groupby(["ticker", "year"]).cumcount() + 1

    # Find revenue column
    rev_candidates = [c for c in df.columns if "revenue" in c and "segment" not in c]
    if not rev_candidates:
        rev_candidates = [c for c in df.columns if "revenue" in c]
    if rev_candidates:
        df["_revenue"] = pd.to_numeric(df[rev_candidates[0]], errors="coerce")
        # Revenue is in raw USD — convert to $M for consistency
        df["_revenue"] = df["_revenue"] / 1_000_000
        # Drop anomalous rows (> $500B/quarter = $500,000M is unrealistic)
        df.loc[df["_revenue"] > 500_000, "_revenue"] = np.nan
    else:
        df["_revenue"] = np.nan
    return df


def _load_signal_momentum(company: str) -> float:
    """Load signal momentum from scored_signals.csv for growth adjustment.
    Returns a value between -0.05 and +0.05 (max ±5pp growth adjustment)."""
    from pathlib import Path
    try:
        csv_path = Path(__file__).resolve().parents[1] / "earningscall_transcripts" / "scored_signals.csv"
        if not csv_path.exists():
            csv_path = Path(__file__).resolve().parents[2] / "earningscall_transcripts" / "scored_signals.csv"
        if not csv_path.exists():
            return 0.0
        signals = pd.read_csv(csv_path)
        if signals.empty:
            return 0.0

        # Normalize company name
        comp_lower = company.lower().replace(" ", "").replace(".", "")
        signals["_norm"] = signals["company"].str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
        co_signals = signals[signals["_norm"].str.contains(comp_lower[:6])]
        if co_signals.empty:
            return 0.0

        # Get latest quarter signals
        co_signals = co_signals.sort_values(["year", "quarter"], ascending=False)
        latest_yr = co_signals.iloc[0]["year"]
        latest_q = co_signals.iloc[0]["quarter"]
        latest = co_signals[(co_signals["year"] == latest_yr) & (co_signals["quarter"] == latest_q)]

        avg_score = float(latest["score"].mean())
        # Normalize: scores range ~5-25; map to -0.05..+0.05
        momentum = max(-0.05, min(0.05, (avg_score - 12) / 200))
        return momentum
    except Exception:
        return 0.0


def estimate_revenue(
    company: str,
    excel_path: str,
    source_stamp: int = 0,
    as_of_date: date | None = None,
    through_quarter: int | None = None,
) -> dict[str, Any]:
    """
    Estimate current-year revenue for a company.

    Args:
        company: Company name (e.g. "Alphabet")
        excel_path: Path to data workbook
        source_stamp: Cache buster
        as_of_date: Date to estimate through (default: today)
        through_quarter: If set (1-4), estimate through that quarter only

    Returns dict with:
        company, ticker, estimate_year, ytd_revenue, full_year_estimate,
        quarterly_breakdown [{q, revenue, is_actual, is_estimate}],
        growth_rate, signal_adjustment, method, confidence
    """
    if as_of_date is None:
        as_of_date = date.today()

    estimate_year = as_of_date.year
    ticker = _COMPANY_TO_TICKER.get(company, "")

    result = {
        "company": company,
        "ticker": ticker,
        "estimate_year": estimate_year,
        "as_of_date": as_of_date.isoformat(),
        "ytd_revenue": None,
        "full_year_estimate": None,
        "quarterly_breakdown": [],
        "growth_rate": None,
        "signal_adjustment": 0.0,
        "method": "unavailable",
        "confidence": 0,
        "prior_year_revenue": None,
    }

    if not excel_path:
        return result

    df = _load_quarterly_data(excel_path)
    if df.empty or not ticker:
        return result

    co_df = df[df["ticker"] == ticker].copy()
    if co_df.empty:
        return result

    # Get latest complete year for baseline
    yr_counts = co_df.groupby("year").size()
    complete_years = yr_counts[yr_counts >= 4].index.tolist()

    # Quarterly breakdown for prior years
    latest_complete_yr = max(complete_years) if complete_years else co_df["year"].max()
    prior_q = co_df[co_df["year"] == latest_complete_yr].sort_values("quarter")
    prior_year_rev = prior_q["_revenue"].sum()

    if prior_year_rev <= 0 or prior_q.empty:
        return result

    result["prior_year_revenue"] = float(prior_year_rev)

    # Calculate YoY growth from last 2 complete years
    if len(complete_years) >= 2:
        sorted_yrs = sorted(complete_years)
        prev_yr_rev = co_df[co_df["year"] == sorted_yrs[-2]]["_revenue"].sum()
        if prev_yr_rev > 0:
            base_growth = (prior_year_rev / prev_yr_rev) - 1.0
        else:
            base_growth = 0.05
    else:
        base_growth = 0.05  # default 5% if only 1 year

    # Signal momentum adjustment
    signal_adj = _load_signal_momentum(company)
    growth_rate = base_growth + signal_adj

    result["growth_rate"] = float(growth_rate)
    result["signal_adjustment"] = float(signal_adj)

    # Build quarterly estimates for current year
    prior_quarters = {}
    for _, row in prior_q.iterrows():
        q = int(row["quarter"])
        rev = _safe_float(row["_revenue"])
        if rev is not None:
            prior_quarters[q] = rev

    # Check if we have any actual data for the estimate year
    current_yr_df = co_df[co_df["year"] == estimate_year].sort_values("quarter")
    actual_quarters: dict[int, float] = {}
    for _, row in current_yr_df.iterrows():
        q = int(row["quarter"])
        rev = _safe_float(row["_revenue"])
        if rev is not None and rev > 0:
            actual_quarters[q] = rev

    quarterly_breakdown = []
    ytd_total = 0.0
    max_q = through_quarter if through_quarter else 4

    for q in range(1, max_q + 1):
        if q in actual_quarters:
            # We have actual data
            quarterly_breakdown.append({
                "q": q,
                "revenue": actual_quarters[q],
                "is_actual": True,
                "is_estimate": False,
            })
            ytd_total += actual_quarters[q]
        elif q in prior_quarters:
            # Estimate = prior year same quarter × (1 + growth)
            est = prior_quarters[q] * (1.0 + growth_rate)
            quarterly_breakdown.append({
                "q": q,
                "revenue": round(est, 1),
                "is_actual": False,
                "is_estimate": True,
            })
            ytd_total += est
        else:
            # No prior quarter data — use average
            avg_q = prior_year_rev / 4.0 * (1.0 + growth_rate)
            quarterly_breakdown.append({
                "q": q,
                "revenue": round(avg_q, 1),
                "is_actual": False,
                "is_estimate": True,
            })
            ytd_total += avg_q

    # Full year estimate (always all 4 quarters)
    full_year = 0.0
    for q in range(1, 5):
        if q in actual_quarters:
            full_year += actual_quarters[q]
        elif q in prior_quarters:
            full_year += prior_quarters[q] * (1.0 + growth_rate)
        else:
            full_year += prior_year_rev / 4.0 * (1.0 + growth_rate)

    # Confidence based on data availability
    n_actual = len(actual_quarters)
    n_prior = len(prior_quarters)
    confidence = min(95, 40 + n_actual * 15 + min(n_prior, 4) * 5 + (10 if len(complete_years) >= 2 else 0))

    result["ytd_revenue"] = round(ytd_total, 1)
    result["full_year_estimate"] = round(full_year, 1)
    result["quarterly_breakdown"] = quarterly_breakdown
    result["confidence"] = confidence
    result["method"] = "quarterly_extrapolation"

    return result


def estimate_all_companies(
    excel_path: str,
    source_stamp: int = 0,
    as_of_date: date | None = None,
    through_quarter: int | None = None,
) -> list[dict[str, Any]]:
    """Run revenue estimation for all tracked companies."""
    companies = [
        "Alphabet", "Amazon", "Apple", "Comcast", "Disney",
        "Meta Platforms", "Microsoft", "Netflix", "Paramount Global",
        "Roku", "Spotify", "Warner Bros. Discovery",
    ]
    results = []
    for co in companies:
        r = estimate_revenue(co, excel_path, source_stamp, as_of_date, through_quarter)
        if r.get("full_year_estimate"):
            results.append(r)
    return sorted(results, key=lambda x: x.get("full_year_estimate", 0), reverse=True)
