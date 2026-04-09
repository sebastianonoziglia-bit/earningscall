from __future__ import annotations

from datetime import date
from functools import lru_cache
import json
import math
from pathlib import Path
import sqlite3
import sys
from typing import Any

import numpy as np
import pandas as pd

from utils.workbook_market_data import infer_company_label, load_combined_stock_market_data


ORACLE_LAYER_WEIGHTS = {
    "signal": 0.40,
    "market": 0.30,
    "fundamental": 0.30,
}

FORECAST_HORIZON = "next_12m"
NEUTRAL_HHI = 0.55

CANONICAL_COMPANY_ALIASES = {
    "alphabet": "Alphabet",
    "alphabetgoogle": "Alphabet",
    "google": "Alphabet",
    "amazon": "Amazon",
    "apple": "Apple",
    "comcast": "Comcast",
    "disney": "Disney",
    "meta": "Meta Platforms",
    "metaplatforms": "Meta Platforms",
    "facebook": "Meta Platforms",
    "microsoft": "Microsoft",
    "netflix": "Netflix",
    "paramount": "Paramount Global",
    "paramountglobal": "Paramount Global",
    "roku": "Roku",
    "spotify": "Spotify",
    "warnerbrosdiscovery": "Warner Bros. Discovery",
    "warnerbros.discovery": "Warner Bros. Discovery",
    "warnerbrosdiscoveryinc": "Warner Bros. Discovery",
    "warnerbrosdiscoveryclassa": "Warner Bros. Discovery",
    "warnerbrosdiscoveryclassb": "Warner Bros. Discovery",
    "samsung": "Samsung",
    "tencent": "Tencent",
}

SIGNAL_BASE_POLARITY = {
    "Investment": 0.85,
    "Monetization": 0.85,
    "Opportunities": 0.75,
    "Strategic Direction": 0.65,
    "Product Shifts": 0.55,
    "User Behavior": 0.35,
    "Outlook": 0.20,
    "Risks": -0.95,
    "Broadcaster Threats": -1.00,
}

POSITIVE_SIGNAL_TOKENS = (
    "accelerat",
    "ahead",
    "benefit",
    "confident",
    "demand",
    "expand",
    "gain",
    "growing",
    "growth",
    "improv",
    "invest",
    "launch",
    "momentum",
    "opportun",
    "optimist",
    "outperform",
    "ramp",
    "rebound",
    "scale",
    "strong",
    "tailwind",
    "upside",
)

NEGATIVE_SIGNAL_TOKENS = (
    "antitrust",
    "challenge",
    "churn",
    "compress",
    "declin",
    "delay",
    "downturn",
    "headwind",
    "lawsuit",
    "lower",
    "macro",
    "pressure",
    "regulator",
    "risk",
    "slow",
    "soft",
    "uncertain",
    "weak",
)

POSITIVE_BET_TOKENS = (
    "above",
    "beat",
    "bull",
    "growth",
    "higher",
    "improves",
    "increase",
    "launches",
    "profit",
    "record",
    "wins",
)

NEGATIVE_BET_TOKENS = (
    "antitrust",
    "ban",
    "below",
    "bear",
    "breakup",
    "cuts",
    "decline",
    "fall",
    "investigation",
    "lawsuit",
    "lower",
    "miss",
    "recession",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _oracle_db_path() -> Path:
    return _repo_root() / "earningscall_intelligence.db"


def _signals_path() -> Path:
    return _repo_root() / "earningscall_transcripts" / "scored_signals.csv"


def _norm_company_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def canonical_company(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return CANONICAL_COMPANY_ALIASES.get(_norm_company_key(text), text)


def _quarter_number(value: Any) -> int:
    text = str(value or "").strip().upper()
    if text.startswith("Q") and len(text) >= 2 and text[1].isdigit():
        return int(text[1])
    try:
        number = int(float(text))
    except (TypeError, ValueError):
        return 0
    return number if 1 <= number <= 4 else 0


def _quarter_label(value: Any) -> str:
    quarter_num = _quarter_number(value)
    return f"Q{quarter_num}" if quarter_num else ""


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return float(max(low, min(high, value)))


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _display_score(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}"


def _format_money_millions(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Not found"
    amount = float(value)
    if abs(amount) >= 1_000_000:
        return f"${amount / 1_000_000:.2f}T"
    if abs(amount) >= 1_000:
        return f"${amount / 1_000:.1f}B"
    return f"${amount:,.0f}M"


def _format_money_billions(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Not found"
    amount = float(value)
    if abs(amount) >= 1_000:
        return f"${amount / 1_000:.2f}T"
    return f"${amount:.1f}B"


def _format_percent(value: float | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "Not found"
    return f"{float(value):.{digits}f}%"


def _latest_local_workbook() -> Path:
    repo_root = _repo_root()
    candidates = [
        repo_root / "app" / "attached_assets" / "Earnings + stocks  copy.xlsx",
        repo_root / "app" / "attached_assets" / "Financial_Data.xlsx",
        repo_root / "attached_assets" / "Financial_Data.xlsx",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    try:
        from utils.workbook_source import resolve_financial_data_xlsx

        resolved = resolve_financial_data_xlsx([])
    except Exception:
        resolved = ""
    if resolved:
        return Path(resolved)
    raise FileNotFoundError("No workbook found for Oracle engine")


def _sheet_mtime(path: Path) -> int:
    try:
        return int(path.stat().st_mtime_ns)
    except OSError:
        return 0


def _signal_tone_score(text: str) -> float:
    lowered = str(text or "").lower()
    positive_hits = sum(token in lowered for token in POSITIVE_SIGNAL_TOKENS)
    negative_hits = sum(token in lowered for token in NEGATIVE_SIGNAL_TOKENS)
    if positive_hits == negative_hits:
        return 0.0
    return _clip((positive_hits - negative_hits) / 3.0)


def infer_signal_polarity(category: str, quote: str) -> float:
    base = SIGNAL_BASE_POLARITY.get(str(category or "").strip(), 0.0)
    tone = _signal_tone_score(quote)
    if abs(tone) < 1e-9:
        return _clip(base)
    return _clip((0.65 * base) + (0.35 * tone))


def infer_bet_polarity(question: str) -> float:
    lowered = str(question or "").lower()
    positive_hits = sum(token in lowered for token in POSITIVE_BET_TOKENS)
    negative_hits = sum(token in lowered for token in NEGATIVE_BET_TOKENS)
    if positive_hits == negative_hits:
        return 0.0
    return 1.0 if positive_hits > negative_hits else -1.0


@lru_cache(maxsize=8)
def _read_signals_cached(path_str: str, mtime_ns: int) -> pd.DataFrame:
    del mtime_ns
    df = pd.read_csv(path_str)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    for column in ["company", "year", "quarter", "quote", "category", "score", "speaker", "role"]:
        if column not in df.columns:
            df[column] = ""
    df["company"] = df["company"].apply(canonical_company)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["quarter"] = df["quarter"].apply(_quarter_label)
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["signal_polarity"] = [
        infer_signal_polarity(category, quote)
        for category, quote in zip(df["category"], df["quote"])
    ]
    df["signed_score"] = df["score"] * df["signal_polarity"]
    df = df.dropna(subset=["year", "score"]).copy()
    df = df[df["company"].astype(str).str.strip() != ""]
    df = df[df["quarter"].isin(["Q1", "Q2", "Q3", "Q4"])].copy()
    df["year"] = df["year"].astype(int)
    df["quarter_num"] = df["quarter"].map(_quarter_number).astype(int)
    df["quarter_index"] = (df["year"] * 4) + df["quarter_num"]
    return df.reset_index(drop=True)


def load_signals_frame() -> pd.DataFrame:
    path = _signals_path()
    if not path.exists():
        return pd.DataFrame()
    return _read_signals_cached(str(path), _sheet_mtime(path)).copy()


@lru_cache(maxsize=4)
def _read_annual_metrics_cached(path_str: str, mtime_ns: int) -> pd.DataFrame:
    del mtime_ns
    workbook_path = Path(path_str)
    metrics = pd.read_excel(workbook_path, sheet_name="Company_metrics_earnings_values")
    metrics = metrics.rename(
        columns={
            "Company": "company",
            "Year": "year",
            "Revenue": "revenue",
            "Operating Income": "operating_income",
            "Net Income": "net_income",
            "Cost Of Revenue": "cost_of_revenue",
            "R&D": "r_and_d",
            "Capex": "capex",
            "Total Assets": "total_assets",
            "Market Cap.": "market_cap",
            "Cash Balance": "cash_balance",
            "Debt": "debt",
        }
    )
    metrics = metrics.copy()
    metrics["company"] = metrics["company"].apply(canonical_company)
    metrics = metrics[metrics["company"] != "MFE"].copy()
    for column in [
        "year",
        "revenue",
        "operating_income",
        "net_income",
        "cost_of_revenue",
        "r_and_d",
        "capex",
        "total_assets",
        "market_cap",
        "cash_balance",
        "debt",
    ]:
        metrics[column] = pd.to_numeric(metrics[column], errors="coerce")
    metrics = metrics.dropna(subset=["company", "year", "revenue"]).copy()
    metrics["year"] = metrics["year"].astype(int)
    metrics["operating_margin"] = np.where(
        metrics["revenue"].replace(0, np.nan).notna(),
        metrics["operating_income"] / metrics["revenue"],
        np.nan,
    )

    try:
        employees = pd.read_excel(workbook_path, sheet_name="Company_Employees")
        employees = employees.rename(
            columns={
                "Company": "company",
                "Year": "year",
                "Employee Count": "employee_count",
            }
        )
        employees["company"] = employees["company"].apply(canonical_company)
        employees["year"] = pd.to_numeric(employees["year"], errors="coerce")
        employees["employee_count"] = pd.to_numeric(employees["employee_count"], errors="coerce")
        employees = employees.dropna(subset=["company", "year", "employee_count"]).copy()
        employees["year"] = employees["year"].astype(int)
        metrics = metrics.merge(employees, on=["company", "year"], how="left")
    except Exception:
        metrics["employee_count"] = np.nan

    try:
        ad_revenue = pd.read_excel(workbook_path, sheet_name="Company_advertising_revenue")
        ad_revenue = ad_revenue.copy()
        ad_revenue.columns = [str(col).strip() for col in ad_revenue.columns]
        ad_revenue["Year"] = pd.to_numeric(ad_revenue["Year"], errors="coerce")
        ad_revenue = ad_revenue.dropna(subset=["Year"]).copy()
        ad_revenue["year"] = ad_revenue["Year"].astype(int)
        ad_column_map = {
            "Google_Ads": "Alphabet",
            "Meta_Ads": "Meta Platforms",
            "Amazon_Ads": "Amazon",
            "Spotify_Ads": "Spotify",
            "*WBD_Ads": "Warner Bros. Discovery",
            "*Microsoft_Ads": "Microsoft",
            "Paramount": "Paramount Global",
            "*Apple": "Apple",
            "*Disney": "Disney",
            "*Comcast": "Comcast",
            "Netflix*": "Netflix",
        }
        ad_rows: list[dict[str, Any]] = []
        for column, company in ad_column_map.items():
            if column not in ad_revenue.columns:
                continue
            for year_value, raw_value in zip(ad_revenue["year"].tolist(), ad_revenue[column].tolist()):
                value = _safe_float(raw_value)
                if value is None:
                    continue
                ad_rows.append(
                    {
                        "company": company,
                        "year": int(year_value),
                        "advertising_revenue_b": value,
                    }
                )
        ad_df = pd.DataFrame(ad_rows)
        if not ad_df.empty:
            metrics = metrics.merge(ad_df, on=["company", "year"], how="left")
        else:
            metrics["advertising_revenue_b"] = np.nan
    except Exception:
        metrics["advertising_revenue_b"] = np.nan

    metrics = metrics.sort_values(["company", "year"]).reset_index(drop=True)
    return metrics


def load_annual_metrics_frame() -> pd.DataFrame:
    workbook_path = _latest_local_workbook()
    return _read_annual_metrics_cached(str(workbook_path), _sheet_mtime(workbook_path)).copy()


@lru_cache(maxsize=4)
def _read_region_mix_cached(path_str: str, mtime_ns: int) -> pd.DataFrame:
    del mtime_ns
    workbook_path = Path(path_str)
    region_df = pd.read_excel(workbook_path, sheet_name="Company_revenue_by_region")
    if region_df is None or region_df.empty:
        return pd.DataFrame()
    region_df = region_df.rename(
        columns={
            "company": "company",
            "year": "year",
            "segment_name": "segment_name",
            "revenue_millions": "revenue_millions",
        }
    )
    region_df = region_df.copy()
    region_df["company"] = region_df["company"].apply(canonical_company)
    region_df["year"] = pd.to_numeric(region_df["year"], errors="coerce")
    region_df["revenue_millions"] = pd.to_numeric(region_df["revenue_millions"], errors="coerce")
    region_df = region_df.dropna(subset=["company", "year", "revenue_millions"]).copy()
    region_df["year"] = region_df["year"].astype(int)
    return region_df.reset_index(drop=True)


def load_region_mix_frame() -> pd.DataFrame:
    workbook_path = _latest_local_workbook()
    return _read_region_mix_cached(str(workbook_path), _sheet_mtime(workbook_path)).copy()


@lru_cache(maxsize=4)
def _read_daily_prices_cached(path_str: str, mtime_ns: int) -> pd.DataFrame:
    workbook_path = Path(path_str)
    daily_prices = load_combined_stock_market_data(
        excel_path=str(workbook_path),
        source_stamp=int(mtime_ns or 0),
        include_baseline=False,
        include_daily=True,
        include_minute=False,
    )
    if daily_prices is None or daily_prices.empty:
        return pd.DataFrame()
    daily_prices = daily_prices.copy()
    daily_prices["company"] = [
        canonical_company(infer_company_label(asset, tag))
        for asset, tag in zip(daily_prices.get("asset", []), daily_prices.get("tag", []))
    ]
    daily_prices["date"] = pd.to_datetime(daily_prices["date"], errors="coerce")
    daily_prices["price"] = pd.to_numeric(daily_prices["price"], errors="coerce")
    daily_prices["market_cap"] = pd.to_numeric(daily_prices.get("market_cap"), errors="coerce")
    daily_prices = daily_prices.dropna(subset=["date", "price"]).copy()
    daily_prices = daily_prices[daily_prices["company"].astype(str).str.strip() != ""].copy()
    return daily_prices.sort_values(["company", "date"]).reset_index(drop=True)


def load_daily_prices_frame() -> pd.DataFrame:
    workbook_path = _latest_local_workbook()
    return _read_daily_prices_cached(str(workbook_path), _sheet_mtime(workbook_path)).copy()


def load_polymarket_markets(use_polymarket: bool = True) -> pd.DataFrame:
    if not use_polymarket:
        return pd.DataFrame()
    try:
        from utils.polymarket import get_all_company_bets_labelled

        markets = get_all_company_bets_labelled(limit=250)
    except Exception:
        markets = []
    if not markets:
        return pd.DataFrame()
    poly_df = pd.DataFrame(markets)
    if poly_df.empty:
        return poly_df
    if "matched_company" not in poly_df.columns:
        poly_df["matched_company"] = ""
    if "question" not in poly_df.columns:
        poly_df["question"] = ""
    for column in ["yes_price", "volume_total", "liquidity"]:
        poly_df[column] = pd.to_numeric(poly_df.get(column), errors="coerce")
    poly_df["matched_company"] = poly_df["matched_company"].apply(canonical_company)
    poly_df["bet_polarity"] = poly_df["question"].apply(infer_bet_polarity)
    poly_df["bet_score"] = (
        ((poly_df["yes_price"].fillna(50.0) - 50.0) / 50.0) * poly_df["bet_polarity"].fillna(0.0)
    )
    return poly_df


def compute_signal_velocity(signals_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if signals_df is None or signals_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    ordered = signals_df.sort_values(
        ["company", "year", "quarter_num", "category", "score"],
        ascending=[True, True, True, True, False],
    )
    grouped = (
        ordered.groupby(
            ["company", "year", "quarter", "quarter_num", "quarter_index", "category"],
            dropna=False,
        )
        .agg(
            signal_count=("quote", "size"),
            avg_score=("score", "mean"),
            raw_score=("score", "sum"),
            signed_score=("signed_score", "sum"),
            avg_polarity=("signal_polarity", "mean"),
            top_quote=("quote", "first"),
            top_speaker=("speaker", "first"),
        )
        .reset_index()
        .sort_values(["company", "category", "quarter_index"])
    )
    grouped["prior_signal_count"] = grouped.groupby(["company", "category"])["signal_count"].shift(1)
    grouped["prior_signed_score"] = grouped.groupby(["company", "category"])["signed_score"].shift(1)
    grouped["delta_score"] = grouped["signed_score"] - grouped["prior_signed_score"].fillna(0.0)
    grouped["prior_delta_score"] = grouped.groupby(["company", "category"])["delta_score"].shift(1)
    grouped["acceleration_score"] = grouped["delta_score"] - grouped["prior_delta_score"].fillna(0.0)
    grouped["strength_component"] = np.tanh(grouped["signed_score"].fillna(0.0) / 30.0)
    grouped["velocity_component"] = np.tanh(grouped["delta_score"].fillna(0.0) / 18.0)
    grouped["acceleration_component"] = np.tanh(grouped["acceleration_score"].fillna(0.0) / 18.0)
    grouped["category_score"] = (
        (0.45 * grouped["strength_component"])
        + (0.35 * grouped["velocity_component"])
        + (0.20 * grouped["acceleration_component"])
    )
    grouped["weight"] = grouped["signal_count"].clip(lower=1) + (grouped["avg_score"].fillna(0.0) / 10.0)

    latest_quarters = grouped.groupby("company")["quarter_index"].transform("max")
    latest = grouped[grouped["quarter_index"] == latest_quarters].copy()
    if latest.empty:
        return pd.DataFrame(), grouped

    company_rows: list[dict[str, Any]] = []
    for company, company_df in latest.groupby("company", sort=False):
        weights = company_df["weight"].fillna(1.0)
        category_scores = company_df["category_score"].fillna(0.0)
        signal_score = float(np.average(category_scores, weights=weights))
        total_signals = int(company_df["signal_count"].fillna(0).sum())
        diversity = int(company_df["category"].nunique())
        mean_magnitude = float(company_df["category_score"].abs().mean())
        confidence = 100.0 * _clip(
            (0.45 * min(total_signals / 16.0, 1.0))
            + (0.25 * min(diversity / 4.0, 1.0))
            + (0.30 * min(mean_magnitude / 0.55, 1.0)),
            0.0,
            1.0,
        )
        first_row = company_df.iloc[0]
        company_rows.append(
            {
                "company": company,
                "signal_score": signal_score,
                "signal_confidence": confidence,
                "latest_signal_year": int(first_row["year"]),
                "latest_signal_quarter": str(first_row["quarter"]),
                "latest_signal_period": f"{int(first_row['year'])} {first_row['quarter']}",
                "signal_total": total_signals,
                "signal_diversity": diversity,
            }
        )
    summary = pd.DataFrame(company_rows)
    return summary.sort_values("signal_score", ascending=False).reset_index(drop=True), latest.reset_index(drop=True)


def _rolling_return(series: pd.Series, periods: int) -> float | None:
    if series is None or len(series) <= periods:
        return None
    latest = _safe_float(series.iloc[-1])
    prior = _safe_float(series.iloc[-(periods + 1)])
    if latest is None or prior in {None, 0.0}:
        return None
    return (latest / prior) - 1.0


def compute_market_consensus(
    daily_prices_df: pd.DataFrame,
    polymarket_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if daily_prices_df is None or daily_prices_df.empty:
        daily_summary = pd.DataFrame(columns=["company", "market_score"])
    else:
        rows: list[dict[str, Any]] = []
        for company, company_df in daily_prices_df.groupby("company", sort=False):
            company_df = company_df.sort_values("date")
            price_series = company_df["price"].astype(float).reset_index(drop=True)
            return_20 = _rolling_return(price_series, 20)
            return_60 = _rolling_return(price_series, 60)
            return_120 = _rolling_return(price_series, 120)
            momentum_parts = [
                np.tanh((return_20 or 0.0) / 0.12) if return_20 is not None else np.nan,
                np.tanh((return_60 or 0.0) / 0.18) if return_60 is not None else np.nan,
                np.tanh((return_120 or 0.0) / 0.25) if return_120 is not None else np.nan,
            ]
            valid_momentum = [part for part in momentum_parts if not pd.isna(part)]
            momentum_score = float(np.mean(valid_momentum)) if valid_momentum else 0.0
            momentum_confidence = 100.0 * _clip(
                (0.55 * (len(valid_momentum) / 3.0))
                + (0.45 * min(np.mean(np.abs(valid_momentum)) / 0.7, 1.0) if valid_momentum else 0.0),
                0.0,
                1.0,
            )
            last_row = company_df.iloc[-1]
            rows.append(
                {
                    "company": company,
                    "price_score": momentum_score,
                    "price_confidence": momentum_confidence,
                    "price_20d_return": return_20,
                    "price_60d_return": return_60,
                    "price_120d_return": return_120,
                    "latest_price": _safe_float(last_row["price"]),
                    "latest_price_date": pd.to_datetime(last_row["date"]).date().isoformat(),
                    "latest_market_cap": _safe_float(last_row.get("market_cap")),
                }
            )
        daily_summary = pd.DataFrame(rows)

    poly_summary_rows: list[dict[str, Any]] = []
    if polymarket_df is not None and not polymarket_df.empty:
        relevant = polymarket_df[polymarket_df["matched_company"].astype(str).str.strip() != ""].copy()
        relevant = relevant[relevant["matched_company"] != "Entertainment"].copy()
        relevant = relevant[relevant["bet_polarity"].fillna(0.0) != 0.0].copy()
        for company, company_df in relevant.groupby("matched_company", sort=False):
            weights = np.log1p(company_df["volume_total"].fillna(0.0) + company_df["liquidity"].fillna(0.0) + 1.0)
            if not np.isfinite(weights).any() or float(weights.sum()) <= 0:
                weights = pd.Series(1.0, index=company_df.index)
            market_score = float(np.average(company_df["bet_score"].fillna(0.0), weights=weights))
            conviction = company_df["bet_score"].fillna(0.0).abs()
            liquidity_factor = min(math.log1p(float(company_df["volume_total"].fillna(0.0).sum()) + 1.0) / math.log1p(5_000_000.0), 1.0)
            confidence = 100.0 * _clip(
                (0.60 * min(conviction.mean() / 0.7, 1.0))
                + (0.40 * liquidity_factor),
                0.0,
                1.0,
            )
            top_bet = company_df.sort_values("volume_total", ascending=False).iloc[0]
            poly_summary_rows.append(
                {
                    "company": canonical_company(company),
                    "polymarket_score": market_score,
                    "polymarket_confidence": confidence,
                    "polymarket_bet_count": int(company_df.shape[0]),
                    "top_bet_question": str(top_bet.get("question", "") or ""),
                    "top_bet_yes_price": _safe_float(top_bet.get("yes_price")),
                    "top_bet_volume": _safe_float(top_bet.get("volume_total")),
                }
            )
    poly_summary = pd.DataFrame(poly_summary_rows)

    if daily_summary.empty and poly_summary.empty:
        return pd.DataFrame()

    merged = (
        daily_summary.merge(poly_summary, on="company", how="outer")
        if not daily_summary.empty and not poly_summary.empty
        else daily_summary.copy() if poly_summary.empty else poly_summary.copy()
    )
    for column in ["price_score", "price_confidence", "polymarket_score", "polymarket_confidence"]:
        if column not in merged.columns:
            merged[column] = 0.0
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    has_poly = merged["polymarket_confidence"] > 0
    merged["market_score"] = np.where(
        has_poly,
        (0.60 * merged["polymarket_score"]) + (0.40 * merged["price_score"]),
        merged["price_score"],
    )
    merged["market_confidence"] = np.where(
        has_poly,
        (0.55 * merged["polymarket_confidence"]) + (0.45 * merged["price_confidence"]),
        merged["price_confidence"],
    )
    return merged.sort_values("market_score", ascending=False).reset_index(drop=True)


def _latest_region_hhi(region_df: pd.DataFrame, company: str, year: int) -> float | None:
    if region_df is None or region_df.empty:
        return None
    scoped = region_df[(region_df["company"] == company) & (region_df["year"] == int(year))].copy()
    if scoped.empty:
        return None
    total = scoped["revenue_millions"].sum()
    if not total or pd.isna(total):
        return None
    shares = scoped["revenue_millions"] / total
    return float((shares**2).sum())


def _compute_cagr(series: pd.Series, years: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty or len(values) < 2:
        return None
    first = _safe_float(values.iloc[0])
    last = _safe_float(values.iloc[-1])
    if first in {None, 0.0} or last is None or first <= 0 or last <= 0:
        return None
    year_span = max(int(years.iloc[-1] - years.iloc[0]), 1)
    return (last / first) ** (1.0 / year_span) - 1.0


def _compute_slope(years: pd.Series, values: pd.Series) -> float | None:
    y = pd.to_numeric(years, errors="coerce")
    v = pd.to_numeric(values, errors="coerce")
    mask = y.notna() & v.notna()
    if mask.sum() < 2:
        return None
    slope = np.polyfit(y[mask], v[mask], 1)[0]
    return float(slope)


def compute_fundamental_trajectory(
    annual_metrics_df: pd.DataFrame,
    region_mix_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[tuple[str, str], dict[str, Any]]]:
    if annual_metrics_df is None or annual_metrics_df.empty:
        return pd.DataFrame(), {}

    company_rows: list[dict[str, Any]] = []
    metric_factors: dict[tuple[str, str], dict[str, Any]] = {}

    for company, company_df in annual_metrics_df.groupby("company", sort=False):
        company_df = company_df.sort_values("year").tail(8).copy()
        if company_df.empty:
            continue

        latest = company_df.iloc[-1]
        revenue_cagr = _compute_cagr(company_df["revenue"], company_df["year"])
        ad_cagr = _compute_cagr(
            company_df["advertising_revenue_b"].dropna(),
            company_df.loc[company_df["advertising_revenue_b"].notna(), "year"],
        ) if company_df["advertising_revenue_b"].notna().sum() >= 2 else None
        margin_slope = _compute_slope(company_df["year"], company_df["operating_margin"])
        latest_margin = _safe_float(latest.get("operating_margin"))
        latest_cash = _safe_float(latest.get("cash_balance"))
        latest_debt = _safe_float(latest.get("debt"))
        if latest_cash is None and latest_debt is None:
            cash_debt_ratio = None
        elif latest_debt in {None, 0.0}:
            cash_debt_ratio = 3.0 if (latest_cash or 0.0) > 0 else 1.0
        else:
            cash_debt_ratio = (latest_cash or 0.0) / latest_debt

        latest_year = int(latest["year"])
        latest_region_hhi = _latest_region_hhi(region_mix_df, company, latest_year) if region_mix_df is not None else None
        concentration_score = _clip((NEUTRAL_HHI - (latest_region_hhi or NEUTRAL_HHI)) / 0.20)
        growth_score = _clip(math.tanh((revenue_cagr or 0.0) / 0.14))
        margin_score = _clip(math.tanh((margin_slope or 0.0) * 18.0))
        balance_score = _clip(math.tanh((((cash_debt_ratio or 1.0) - 1.0) / 1.5)))
        ad_growth_score = _clip(math.tanh((ad_cagr or 0.0) / 0.16))

        latest_revenue = _safe_float(latest.get("revenue"))
        latest_ad_revenue_b = _safe_float(latest.get("advertising_revenue_b"))
        ad_mix = None
        if latest_ad_revenue_b is not None and latest_revenue not in {None, 0.0}:
            ad_mix = (latest_ad_revenue_b * 1_000.0) / latest_revenue

        revenue_score = _clip(
            (0.40 * growth_score)
            + (0.25 * margin_score)
            + (0.20 * balance_score)
            + (0.15 * concentration_score)
        )
        margin_metric_score = _clip(
            (0.55 * margin_score)
            + (0.25 * balance_score)
            + (0.20 * concentration_score)
        )
        ad_metric_score = _clip(
            (0.50 * ad_growth_score)
            + (0.30 * growth_score)
            + (0.20 * balance_score)
        )

        company_rows.append(
            {
                "company": company,
                "fundamental_score_revenue": revenue_score,
                "fundamental_score_operating_margin": margin_metric_score,
                "fundamental_score_advertising_revenue": ad_metric_score,
                "fundamental_confidence": 100.0 * _clip(
                    (0.35 * (1.0 if revenue_cagr is not None else 0.0))
                    + (0.25 * (1.0 if margin_slope is not None else 0.0))
                    + (0.20 * (1.0 if cash_debt_ratio is not None else 0.0))
                    + (0.20 * (1.0 if latest_region_hhi is not None else 0.0)),
                    0.0,
                    1.0,
                ),
                "latest_fundamental_year": latest_year,
                "latest_revenue": latest_revenue,
                "latest_operating_margin": latest_margin,
                "latest_advertising_revenue_b": latest_ad_revenue_b,
                "revenue_cagr": revenue_cagr,
                "ad_revenue_cagr": ad_cagr,
                "margin_slope": margin_slope,
                "cash_debt_ratio": cash_debt_ratio,
                "region_hhi": latest_region_hhi,
                "ad_mix": ad_mix,
                "latest_market_cap": _safe_float(latest.get("market_cap")),
            }
        )

        metric_factors[(company, "Revenue")] = {
            "revenue_cagr": revenue_cagr,
            "margin_slope": margin_slope,
            "cash_debt_ratio": cash_debt_ratio,
            "region_hhi": latest_region_hhi,
            "score": revenue_score,
        }
        metric_factors[(company, "Operating Margin")] = {
            "revenue_cagr": revenue_cagr,
            "margin_slope": margin_slope,
            "cash_debt_ratio": cash_debt_ratio,
            "region_hhi": latest_region_hhi,
            "score": margin_metric_score,
        }
        if latest_ad_revenue_b is not None:
            metric_factors[(company, "Advertising Revenue")] = {
                "ad_revenue_cagr": ad_cagr,
                "ad_mix": ad_mix,
                "cash_debt_ratio": cash_debt_ratio,
                "score": ad_metric_score,
            }

    fundamentals = pd.DataFrame(company_rows)
    return fundamentals.sort_values("company").reset_index(drop=True), metric_factors


def _direction_label(score: float) -> str:
    if score >= 0.18:
        return "Bullish"
    if score <= -0.18:
        return "Bearish"
    return "Neutral"


def _build_prediction_summary(
    company: str,
    metric: str,
    direction: str,
    confidence: float,
    signal_score: float | None,
    market_score: float | None,
    fundamental_score: float | None,
) -> str:
    pieces = [
        f"{company} {metric.lower()} outlook is {direction.lower()}",
        f"confidence {confidence:.0f}%",
    ]
    if signal_score is not None:
        pieces.append(f"signals {_display_score(signal_score)}")
    if market_score is not None:
        pieces.append(f"market {_display_score(market_score)}")
    if fundamental_score is not None:
        pieces.append(f"fundamentals {_display_score(fundamental_score)}")
    return " | ".join(pieces)


def _forecast_revenue(row: pd.Series, composite_score: float) -> tuple[float | None, float | None, str]:
    latest_revenue = _safe_float(row.get("latest_revenue"))
    if latest_revenue is None:
        return None, None, "USDm"
    base_growth = row.get("revenue_cagr")
    base_growth = float(base_growth) if base_growth is not None and not pd.isna(base_growth) else 0.04
    forecast_growth = _clip(base_growth + (0.05 * composite_score), -0.18, 0.30)
    return latest_revenue * (1.0 + forecast_growth), forecast_growth * 100.0, "USDm"


def _forecast_operating_margin(row: pd.Series, composite_score: float) -> tuple[float | None, float | None, str]:
    latest_margin = _safe_float(row.get("latest_operating_margin"))
    if latest_margin is None:
        return None, None, "pct"
    slope = row.get("margin_slope")
    slope = float(slope) if slope is not None and not pd.isna(slope) else 0.0
    delta_points = max(-8.0, min(8.0, (slope * 250.0) + (4.0 * composite_score)))
    return (latest_margin * 100.0) + delta_points, delta_points, "pct"


def _forecast_ad_revenue(row: pd.Series, composite_score: float) -> tuple[float | None, float | None, str]:
    latest_ad = _safe_float(row.get("latest_advertising_revenue_b"))
    if latest_ad is None:
        return None, None, "USDb"
    base_growth = row.get("ad_revenue_cagr")
    if base_growth is None or pd.isna(base_growth):
        base_growth = row.get("revenue_cagr")
    base_growth = float(base_growth) if base_growth is not None and not pd.isna(base_growth) else 0.05
    forecast_growth = _clip(base_growth + (0.06 * composite_score), -0.20, 0.35)
    return latest_ad * (1.0 + forecast_growth), forecast_growth * 100.0, "USDb"


def compute_oracle_predictions(
    signal_summary: pd.DataFrame,
    signal_categories: pd.DataFrame,
    market_summary: pd.DataFrame,
    fundamentals: pd.DataFrame,
    metric_factors: dict[tuple[str, str], dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = [frame for frame in [signal_summary, market_summary, fundamentals] if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(), pd.DataFrame()

    company_base = fundamentals[["company"]].drop_duplicates().copy() if not fundamentals.empty else pd.DataFrame()
    if company_base.empty:
        company_base = signal_summary[["company"]].drop_duplicates().copy() if not signal_summary.empty else market_summary[["company"]].drop_duplicates().copy()

    if not signal_summary.empty:
        company_base = company_base.merge(signal_summary, on="company", how="left")
    if not market_summary.empty:
        company_base = company_base.merge(market_summary, on="company", how="left")
    if not fundamentals.empty:
        company_base = company_base.merge(fundamentals, on="company", how="left")

    as_of_date = date.today().isoformat()
    prediction_rows: list[dict[str, Any]] = []
    factor_rows: list[dict[str, Any]] = []

    latest_signal_lookup = {}
    if signal_categories is not None and not signal_categories.empty:
        grouped_categories = signal_categories.sort_values("category_score", key=lambda s: s.abs(), ascending=False)
        for company, company_df in grouped_categories.groupby("company", sort=False):
            latest_signal_lookup[company] = company_df.head(3).copy()

    for row in company_base.to_dict("records"):
        company = canonical_company(row.get("company"))
        metric_names = ["Revenue", "Operating Margin"]
        if _safe_float(row.get("latest_advertising_revenue_b")) is not None:
            metric_names.append("Advertising Revenue")

        signal_score = _safe_float(row.get("signal_score"))
        signal_confidence = _safe_float(row.get("signal_confidence"))
        market_score = _safe_float(row.get("market_score"))
        market_confidence = _safe_float(row.get("market_confidence"))

        for metric in metric_names:
            fundamental_key = {
                "Revenue": "fundamental_score_revenue",
                "Operating Margin": "fundamental_score_operating_margin",
                "Advertising Revenue": "fundamental_score_advertising_revenue",
            }[metric]
            fundamental_score = _safe_float(row.get(fundamental_key))
            fundamental_confidence = _safe_float(row.get("fundamental_confidence"))

            weighted_components: list[tuple[str, float, float, float]] = []
            if signal_score is not None:
                weighted_components.append(("signal", signal_score, ORACLE_LAYER_WEIGHTS["signal"], signal_confidence or 0.0))
            if market_score is not None:
                weighted_components.append(("market", market_score, ORACLE_LAYER_WEIGHTS["market"], market_confidence or 0.0))
            if fundamental_score is not None:
                weighted_components.append(("fundamental", fundamental_score, ORACLE_LAYER_WEIGHTS["fundamental"], fundamental_confidence or 0.0))
            if not weighted_components:
                continue

            weight_total = sum(weight for _, _, weight, _ in weighted_components) or 1.0
            composite_score = float(
                sum(score * weight for _, score, weight, _ in weighted_components) / weight_total
            )
            agreement = abs(sum(np.sign(score) for _, score, _, _ in weighted_components)) / len(weighted_components)
            magnitude = float(np.mean([abs(score) for _, score, _, _ in weighted_components]))
            layer_confidence = float(np.mean([confidence for _, _, _, confidence in weighted_components]) / 100.0)
            confidence = 100.0 * _clip(
                (0.40 * agreement)
                + (0.25 * min(magnitude / 0.75, 1.0))
                + (0.20 * (len(weighted_components) / 3.0))
                + (0.15 * layer_confidence),
                0.0,
                1.0,
            )
            direction = _direction_label(composite_score)

            row_series = pd.Series(row)
            if metric == "Revenue":
                forecast_value, forecast_delta_pct, forecast_unit = _forecast_revenue(row_series, composite_score)
                latest_actual_value = _safe_float(row.get("latest_revenue"))
            elif metric == "Operating Margin":
                forecast_value, forecast_delta_pct, forecast_unit = _forecast_operating_margin(row_series, composite_score)
                latest_actual_value = (_safe_float(row.get("latest_operating_margin")) or 0.0) * 100.0 if _safe_float(row.get("latest_operating_margin")) is not None else None
            else:
                forecast_value, forecast_delta_pct, forecast_unit = _forecast_ad_revenue(row_series, composite_score)
                latest_actual_value = _safe_float(row.get("latest_advertising_revenue_b"))

            latest_actual_period = str(int(row.get("latest_fundamental_year"))) if row.get("latest_fundamental_year") is not None and not pd.isna(row.get("latest_fundamental_year")) else ""
            summary = _build_prediction_summary(
                company=company,
                metric=metric,
                direction=direction,
                confidence=confidence,
                signal_score=signal_score,
                market_score=market_score,
                fundamental_score=fundamental_score,
            )
            prediction_rows.append(
                {
                    "company": company,
                    "metric": metric,
                    "as_of_date": as_of_date,
                    "forecast_horizon": FORECAST_HORIZON,
                    "direction": direction,
                    "confidence": confidence,
                    "signal_score": signal_score,
                    "market_score": market_score,
                    "fundamental_score": fundamental_score,
                    "composite_score": composite_score,
                    "latest_actual_value": latest_actual_value,
                    "latest_actual_period": latest_actual_period,
                    "forecast_value": forecast_value,
                    "forecast_delta_pct": forecast_delta_pct,
                    "forecast_unit": forecast_unit,
                    "summary": summary,
                    "latest_market_cap": _safe_float(row.get("latest_market_cap")),
                    "latest_price": _safe_float(row.get("latest_price")),
                    "latest_price_date": row.get("latest_price_date"),
                    "latest_signal_period": f"{row.get('latest_signal_year', '')} {row.get('latest_signal_quarter', '')}".strip(),
                }
            )

            layer_records = [
                ("Signal Velocity", signal_score, signal_confidence, row.get("latest_signal_period", "")),
                ("Market Consensus", market_score, market_confidence, row.get("latest_price_date", "")),
                ("Fundamental Trajectory", fundamental_score, fundamental_confidence, row.get("latest_fundamental_year", "")),
            ]
            for sort_order, (layer, value, layer_conf, detail_anchor) in enumerate(layer_records, start=1):
                if value is None:
                    continue
                factor_rows.append(
                    {
                        "company": company,
                        "metric": metric,
                        "as_of_date": as_of_date,
                        "forecast_horizon": FORECAST_HORIZON,
                        "layer": layer,
                        "factor_name": layer,
                        "contribution": value,
                        "factor_value": layer_conf,
                        "factor_display": f"{_display_score(value)} | conf {layer_conf or 0:.0f}%",
                        "detail": str(detail_anchor or ""),
                        "sort_order": sort_order,
                    }
                )

            top_signal_categories = latest_signal_lookup.get(company)
            if top_signal_categories is not None and not top_signal_categories.empty:
                for offset, signal_row in enumerate(top_signal_categories.itertuples(index=False), start=10):
                    trend_word = "accelerated" if float(signal_row.delta_score or 0.0) > 0 else "softened"
                    factor_rows.append(
                        {
                            "company": company,
                            "metric": metric,
                            "as_of_date": as_of_date,
                            "forecast_horizon": FORECAST_HORIZON,
                            "layer": "Signal Drivers",
                            "factor_name": str(signal_row.category),
                            "contribution": _safe_float(signal_row.category_score),
                            "factor_value": _safe_float(signal_row.signal_count),
                            "factor_display": f"{int(signal_row.signal_count)} quotes | avg {signal_row.avg_score:.1f}",
                            "detail": f"{signal_row.category} {trend_word} into {signal_row.quarter} {signal_row.year}. Top quote: {str(signal_row.top_quote)[:180]}",
                            "sort_order": offset,
                        }
                    )

            metric_factor = metric_factors.get((company, metric), {})
            if metric == "Revenue":
                factor_rows.extend(
                    [
                        {
                            "company": company,
                            "metric": metric,
                            "as_of_date": as_of_date,
                            "forecast_horizon": FORECAST_HORIZON,
                            "layer": "Fundamental Drivers",
                            "factor_name": "Revenue CAGR",
                            "contribution": _safe_float(metric_factor.get("score")),
                            "factor_value": _safe_float(metric_factor.get("revenue_cagr")),
                            "factor_display": _format_percent((_safe_float(metric_factor.get("revenue_cagr")) or 0.0) * 100.0),
                            "detail": f"Latest reported base year: {latest_actual_period}",
                            "sort_order": 20,
                        },
                        {
                            "company": company,
                            "metric": metric,
                            "as_of_date": as_of_date,
                            "forecast_horizon": FORECAST_HORIZON,
                            "layer": "Fundamental Drivers",
                            "factor_name": "Revenue Mix HHI",
                            "contribution": _safe_float(metric_factor.get("score")),
                            "factor_value": _safe_float(metric_factor.get("region_hhi")),
                            "factor_display": f"{(_safe_float(metric_factor.get('region_hhi')) or NEUTRAL_HHI):.2f}",
                            "detail": "Computed from Company_revenue_by_region latest revenue mix.",
                            "sort_order": 21,
                        },
                    ]
                )
            elif metric == "Operating Margin":
                factor_rows.append(
                    {
                        "company": company,
                        "metric": metric,
                        "as_of_date": as_of_date,
                        "forecast_horizon": FORECAST_HORIZON,
                        "layer": "Fundamental Drivers",
                        "factor_name": "Margin Slope",
                        "contribution": _safe_float(metric_factor.get("score")),
                        "factor_value": _safe_float(metric_factor.get("margin_slope")),
                        "factor_display": f"{(_safe_float(metric_factor.get('margin_slope')) or 0.0) * 100:.2f} pts / year",
                        "detail": f"Latest operating margin: {_format_percent((_safe_float(row.get('latest_operating_margin')) or 0.0) * 100.0)}",
                        "sort_order": 20,
                    }
                )
            else:
                factor_rows.append(
                    {
                        "company": company,
                        "metric": metric,
                        "as_of_date": as_of_date,
                        "forecast_horizon": FORECAST_HORIZON,
                        "layer": "Fundamental Drivers",
                        "factor_name": "Ad Revenue CAGR",
                        "contribution": _safe_float(metric_factor.get("score")),
                        "factor_value": _safe_float(metric_factor.get("ad_revenue_cagr")),
                        "factor_display": _format_percent((_safe_float(metric_factor.get("ad_revenue_cagr")) or 0.0) * 100.0),
                        "detail": f"Latest ad mix: {_format_percent((_safe_float(metric_factor.get('ad_mix')) or 0.0) * 100.0)} of revenue",
                        "sort_order": 20,
                    }
                )

            if metric == "Revenue":
                if row.get("price_20d_return") is not None:
                    factor_rows.append(
                        {
                            "company": company,
                            "metric": metric,
                            "as_of_date": as_of_date,
                            "forecast_horizon": FORECAST_HORIZON,
                            "layer": "Market Drivers",
                            "factor_name": "20D Price Momentum",
                            "contribution": market_score,
                            "factor_value": _safe_float(row.get("price_20d_return")),
                            "factor_display": _format_percent((_safe_float(row.get("price_20d_return")) or 0.0) * 100.0),
                            "detail": f"As of {row.get('latest_price_date', 'Not found')}",
                            "sort_order": 30,
                        }
                    )
                if row.get("top_bet_question"):
                    factor_rows.append(
                        {
                            "company": company,
                            "metric": metric,
                            "as_of_date": as_of_date,
                            "forecast_horizon": FORECAST_HORIZON,
                            "layer": "Market Drivers",
                            "factor_name": "Top Polymarket Signal",
                            "contribution": _safe_float(row.get("polymarket_score")),
                            "factor_value": _safe_float(row.get("top_bet_yes_price")),
                            "factor_display": f"YES {(_safe_float(row.get('top_bet_yes_price')) or 0.0):.0f}%",
                            "detail": str(row.get("top_bet_question"))[:180],
                            "sort_order": 31,
                        }
                    )

    predictions = pd.DataFrame(prediction_rows)
    factors = pd.DataFrame(factor_rows)
    if predictions.empty:
        return predictions, factors
    predictions = predictions.sort_values(["confidence", "composite_score"], ascending=[False, False]).reset_index(drop=True)
    return predictions, factors


def compute_company_correlations(daily_prices_df: pd.DataFrame, companies: list[str]) -> pd.DataFrame:
    if daily_prices_df is None or daily_prices_df.empty or not companies:
        return pd.DataFrame()
    scoped = daily_prices_df[daily_prices_df["company"].isin(companies)].copy()
    if scoped.empty:
        return pd.DataFrame()
    scoped = scoped.sort_values(["company", "date"])
    scoped["return"] = scoped.groupby("company")["price"].pct_change()
    pivot = scoped.pivot_table(index="date", columns="company", values="return")
    if pivot.empty:
        return pd.DataFrame()
    recent = pivot.tail(120)
    corr_matrix = recent.corr()
    corr_matrix.index.name = "source"
    corr_matrix.columns.name = "target"
    corr = corr_matrix.stack().reset_index(name="correlation")
    corr = corr[corr["source"] < corr["target"]].copy()
    corr["abs_corr"] = corr["correlation"].abs()
    corr = corr[corr["abs_corr"] >= 0.35].copy()
    return corr.sort_values("abs_corr", ascending=False).reset_index(drop=True)


def build_oracle_snapshot(use_polymarket: bool = True) -> dict[str, Any]:
    signals_df = load_signals_frame()
    annual_metrics_df = load_annual_metrics_frame()
    region_mix_df = load_region_mix_frame()
    daily_prices_df = load_daily_prices_frame()
    polymarket_df = load_polymarket_markets(use_polymarket=use_polymarket)

    signal_summary, signal_categories = compute_signal_velocity(signals_df)
    market_summary = compute_market_consensus(daily_prices_df, polymarket_df)
    fundamentals, metric_factors = compute_fundamental_trajectory(annual_metrics_df, region_mix_df)
    predictions, factors = compute_oracle_predictions(
        signal_summary=signal_summary,
        signal_categories=signal_categories,
        market_summary=market_summary,
        fundamentals=fundamentals,
        metric_factors=metric_factors,
    )
    correlations = compute_company_correlations(daily_prices_df, predictions["company"].drop_duplicates().tolist() if not predictions.empty else [])

    metadata = {
        "as_of_date": date.today().isoformat(),
        "forecast_horizon": FORECAST_HORIZON,
        "workbook_path": str(_latest_local_workbook()),
        "signals_path": str(_signals_path()) if _signals_path().exists() else "",
        "signal_rows": int(signals_df.shape[0]) if signals_df is not None else 0,
        "prediction_rows": int(predictions.shape[0]) if predictions is not None else 0,
        "use_polymarket": bool(use_polymarket),
        "polymarket_rows": int(polymarket_df.shape[0]) if polymarket_df is not None else 0,
    }
    return {
        "metadata": metadata,
        "signals": signal_summary,
        "signal_categories": signal_categories,
        "market": market_summary,
        "fundamentals": fundamentals,
        "predictions": predictions,
        "factors": factors,
        "correlations": correlations,
    }


def _ensure_intelligence_schema(conn: sqlite3.Connection) -> None:
    script_dir = _repo_root() / "scripts"
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    from intelligence_db_schema import ensure_schema  # noqa: WPS433

    ensure_schema(conn)


def persist_oracle_snapshot(snapshot: dict[str, Any], db_path: Path | None = None) -> Path:
    predictions = snapshot.get("predictions")
    factors = snapshot.get("factors")
    if predictions is None or predictions.empty:
        return db_path or _oracle_db_path()

    target_db = db_path or _oracle_db_path()
    target_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_db))
    try:
        _ensure_intelligence_schema(conn)
        as_of_date = str(snapshot.get("metadata", {}).get("as_of_date") or date.today().isoformat())
        horizon = str(snapshot.get("metadata", {}).get("forecast_horizon") or FORECAST_HORIZON)
        conn.execute(
            "DELETE FROM oracle_prediction_factors WHERE as_of_date=? AND forecast_horizon=?",
            (as_of_date, horizon),
        )
        conn.execute(
            "DELETE FROM oracle_predictions WHERE as_of_date=? AND forecast_horizon=?",
            (as_of_date, horizon),
        )
        conn.executemany(
            """
            INSERT INTO oracle_predictions (
                company, metric, as_of_date, forecast_horizon, direction, confidence,
                signal_score, market_score, fundamental_score, composite_score,
                latest_actual_value, latest_actual_period, forecast_value,
                forecast_delta_pct, forecast_unit, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.company,
                    row.metric,
                    row.as_of_date,
                    row.forecast_horizon,
                    row.direction,
                    row.confidence,
                    row.signal_score,
                    row.market_score,
                    row.fundamental_score,
                    row.composite_score,
                    row.latest_actual_value,
                    row.latest_actual_period,
                    row.forecast_value,
                    row.forecast_delta_pct,
                    row.forecast_unit,
                    row.summary,
                )
                for row in predictions.itertuples(index=False)
            ],
        )
        if factors is not None and not factors.empty:
            conn.executemany(
                """
                INSERT INTO oracle_prediction_factors (
                    company, metric, as_of_date, forecast_horizon, layer, factor_name,
                    contribution, factor_value, factor_display, detail, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.company,
                        row.metric,
                        row.as_of_date,
                        row.forecast_horizon,
                        row.layer,
                        row.factor_name,
                        row.contribution,
                        row.factor_value,
                        row.factor_display,
                        row.detail,
                        row.sort_order,
                    )
                    for row in factors.itertuples(index=False)
                ],
            )
        conn.commit()
    finally:
        conn.close()
    return target_db


def load_oracle_predictions_from_db(limit: int = 50, company: str = "") -> pd.DataFrame:
    db_path = _oracle_db_path()
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "oracle_predictions" not in tables:
            return pd.DataFrame()
        latest = conn.execute("SELECT MAX(as_of_date) FROM oracle_predictions").fetchone()
        latest_date = latest[0] if latest else None
        if not latest_date:
            return pd.DataFrame()
        query = """
            SELECT *
            FROM oracle_predictions
            WHERE as_of_date = ?
        """
        params: list[Any] = [latest_date]
        if company:
            query += " AND LOWER(company) = LOWER(?)"
            params.append(company.strip())
        query += " ORDER BY confidence DESC, composite_score DESC LIMIT ?"
        params.append(int(limit))
        return pd.read_sql_query(query, conn, params=params)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def get_oracle_snapshot(use_polymarket: bool = True, persist: bool = True) -> dict[str, Any]:
    snapshot = build_oracle_snapshot(use_polymarket=use_polymarket)
    if persist:
        persist_oracle_snapshot(snapshot)
    return snapshot


def get_oracle_context_text(company: str = "", top_n: int = 6, auto_build: bool = True) -> str:
    predictions = load_oracle_predictions_from_db(limit=max(top_n * 3, 12), company=company)
    if predictions.empty and auto_build:
        try:
            snapshot = build_oracle_snapshot(use_polymarket=False)
            predictions = snapshot.get("predictions", pd.DataFrame()).copy()
        except Exception:
            predictions = pd.DataFrame()
    if predictions is None or predictions.empty:
        return ""

    if company:
        predictions = predictions[predictions["company"].astype(str).str.lower() == company.strip().lower()].copy()
    if predictions.empty:
        return ""

    priority = pd.CategoricalDtype(
        categories=["Revenue", "Advertising Revenue", "Operating Margin"],
        ordered=True,
    )
    if "metric" in predictions.columns:
        predictions["metric"] = predictions["metric"].astype(priority)
    predictions = predictions.sort_values(["confidence", "metric"], ascending=[False, True]).head(top_n)

    lines = []
    for row in predictions.itertuples(index=False):
        if row.forecast_unit == "USDm":
            forecast_display = _format_money_millions(row.forecast_value)
        elif row.forecast_unit == "USDb":
            forecast_display = _format_money_billions(row.forecast_value)
        else:
            forecast_display = _format_percent(row.forecast_value)
        delta_display = _format_percent(row.forecast_delta_pct)
        lines.append(
            f"- {row.company} | {row.metric} | {row.direction} | "
            f"Confidence {row.confidence:.0f}% | Forecast {forecast_display}"
            + (f" ({delta_display})" if delta_display != "Not found" else "")
        )
    return "\n".join(lines)


def serialize_snapshot_metadata(snapshot: dict[str, Any]) -> str:
    metadata = snapshot.get("metadata", {})
    return json.dumps(metadata, default=str)
