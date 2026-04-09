"""
Country Ad Spend Predictor — forecast advertising spend by country & channel.

Uses historical data (2019-2024) from Country_Advertising_Data_FullVi sheet
to project ad spend forward 1-3 years using channel-level growth models.

Usage:
    from utils.country_ad_predictor import predict_country_ad_spend
    result = predict_country_ad_spend("United States", excel_path)
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


# Macro category groupings (same as data_loader.py)
MACRO_CATEGORIES = {
    "Digital": [
        "Display Desktop", "Display Mobile", "Search Desktop", "Search Mobile",
        "Social Desktop", "Social Mobile", "Video Desktop", "Video Mobile",
        "Other Desktop", "Other Mobile",
    ],
    "OOH": ["Digital OOH", "Traditional OOH"],
    "Press": ["Magazine", "Newspaper"],
    "Television": ["Free TV", "Pay TV"],
    "Cinema": ["Cinema"],
    "Radio": ["Radio"],
}

# Invert: sub-channel → macro category
_SUB_TO_MACRO = {}
for macro, subs in MACRO_CATEGORIES.items():
    for s in subs:
        _SUB_TO_MACRO[s] = macro


def _load_country_data(excel_path: str) -> pd.DataFrame:
    """Load country advertising data from workbook."""
    try:
        df = pd.read_excel(excel_path, sheet_name="Country_Advertising_Data_FullVi")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    # Normalize column names
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "country" in cl:
            col_map[c] = "country"
        elif "year" in cl:
            col_map[c] = "year"
        elif "value" in cl or "spend" in cl or "amount" in cl:
            col_map[c] = "value"
        elif "ad_type" in cl or "metric" in cl or "format" in cl or "type" in cl:
            col_map[c] = "ad_type"
    df = df.rename(columns=col_map)

    if "country" not in df.columns or "year" not in df.columns or "value" not in df.columns:
        return pd.DataFrame()

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["country", "year", "value"])
    df["year"] = df["year"].astype(int)

    # Assign macro category
    if "ad_type" in df.columns:
        df["macro_category"] = df["ad_type"].map(_SUB_TO_MACRO).fillna("Other")
    else:
        df["macro_category"] = "Total"

    return df


def _fit_growth_model(years: np.ndarray, values: np.ndarray) -> dict:
    """Fit a log-linear growth model and return parameters.
    Returns CAGR, trend coefficient, R², and prediction function."""
    if len(years) < 2 or np.all(values <= 0):
        return {"cagr": 0.0, "r2": 0.0, "predict": lambda y: float(values[-1]) if len(values) else 0.0}

    # Filter out zeros for log model
    mask = values > 0
    if mask.sum() < 2:
        return {"cagr": 0.0, "r2": 0.0, "predict": lambda y: float(values[-1])}

    yrs_f = years[mask].astype(float)
    vals_f = values[mask].astype(float)

    # CAGR
    n_years = float(yrs_f[-1] - yrs_f[0])
    if n_years > 0 and vals_f[0] > 0:
        cagr = (vals_f[-1] / vals_f[0]) ** (1.0 / n_years) - 1.0
    else:
        cagr = 0.0

    # Linear regression on log values for R²
    try:
        log_vals = np.log(vals_f)
        coeffs = np.polyfit(yrs_f, log_vals, 1)
        trend = float(coeffs[0])  # annual log growth rate
        intercept = float(coeffs[1])
        predicted = np.exp(np.polyval(coeffs, yrs_f))
        ss_res = np.sum((vals_f - predicted) ** 2)
        ss_tot = np.sum((vals_f - np.mean(vals_f)) ** 2)
        r2 = max(0.0, 1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

        def predict_fn(target_year: int) -> float:
            return float(np.exp(trend * target_year + intercept))
    except Exception:
        r2 = 0.0
        last_val = float(vals_f[-1])

        def predict_fn(target_year: int) -> float:
            return last_val * (1 + cagr) ** (target_year - int(yrs_f[-1]))

    return {"cagr": float(cagr), "r2": float(r2), "predict": predict_fn}


def predict_country_ad_spend(
    country: str,
    excel_path: str,
    forecast_years: int = 3,
) -> dict[str, Any]:
    """
    Predict ad spend for a country by channel.

    Args:
        country: Country name
        excel_path: Path to data workbook
        forecast_years: How many years to project (1-5)

    Returns dict with:
        country, historical {year: {category: value}},
        forecast {year: {category: value}},
        growth_rates {category: cagr},
        total_forecast {year: total},
        confidence, method
    """
    forecast_years = max(1, min(5, forecast_years))

    result: dict[str, Any] = {
        "country": country,
        "historical": {},
        "forecast": {},
        "growth_rates": {},
        "total_forecast": {},
        "confidence": 0,
        "method": "unavailable",
    }

    if not excel_path:
        return result

    df = _load_country_data(excel_path)
    if df.empty:
        return result

    # Filter for country
    country_df = df[df["country"].str.lower() == country.lower()]
    if country_df.empty:
        # Try partial match
        country_df = df[df["country"].str.lower().str.contains(country.lower()[:6])]
    if country_df.empty:
        return result

    actual_country = country_df["country"].iloc[0]
    result["country"] = actual_country

    # Group by year and macro category
    grouped = country_df.groupby(["year", "macro_category"])["value"].sum().reset_index()
    all_years = sorted(grouped["year"].unique())
    all_categories = sorted(grouped["macro_category"].unique())
    latest_year = max(all_years)

    # Build historical data
    for yr in all_years:
        yr_data = grouped[grouped["year"] == yr]
        result["historical"][int(yr)] = {
            row["macro_category"]: round(float(row["value"]), 1)
            for _, row in yr_data.iterrows()
        }
        result["historical"][int(yr)]["Total"] = round(float(yr_data["value"].sum()), 1)

    # Fit growth model per category and forecast
    models: dict[str, dict] = {}
    for cat in all_categories:
        cat_data = grouped[grouped["macro_category"] == cat].sort_values("year")
        if cat_data.empty:
            continue
        years_arr = cat_data["year"].values
        vals_arr = cat_data["value"].values
        model = _fit_growth_model(years_arr, vals_arr)
        models[cat] = model
        result["growth_rates"][cat] = round(model["cagr"] * 100, 1)

    # Generate forecasts
    for offset in range(1, forecast_years + 1):
        target_yr = latest_year + offset
        yr_forecast = {}
        yr_total = 0.0
        for cat in all_categories:
            if cat in models:
                predicted = models[cat]["predict"](target_yr)
                # Dampen growth for longer horizons (mean reversion)
                dampen = 1.0 / (1.0 + 0.1 * offset)
                latest_val = result["historical"].get(latest_year, {}).get(cat, 0)
                cagr = models[cat]["cagr"]
                dampened_val = latest_val * (1 + cagr * dampen) ** offset
                # Blend model prediction with dampened extrapolation
                val = 0.6 * predicted + 0.4 * dampened_val
                val = max(0, val)
                yr_forecast[cat] = round(val, 1)
                yr_total += val
            else:
                yr_forecast[cat] = 0.0
        yr_forecast["Total"] = round(yr_total, 1)
        result["forecast"][int(target_yr)] = yr_forecast
        result["total_forecast"][int(target_yr)] = round(yr_total, 1)

    # Total growth rate
    if len(all_years) >= 2:
        total_first = result["historical"].get(all_years[0], {}).get("Total", 0)
        total_last = result["historical"].get(all_years[-1], {}).get("Total", 0)
        n = all_years[-1] - all_years[0]
        if total_first > 0 and n > 0:
            result["growth_rates"]["Total"] = round(((total_last / total_first) ** (1.0 / n) - 1) * 100, 1)

    # Confidence
    n_years = len(all_years)
    avg_r2 = np.mean([m["r2"] for m in models.values()]) if models else 0
    result["confidence"] = min(90, int(30 + n_years * 8 + avg_r2 * 20))
    result["method"] = "channel_growth_model"

    return result


def get_available_countries(excel_path: str) -> list[str]:
    """Return list of available countries in the dataset."""
    df = _load_country_data(excel_path)
    if df.empty:
        return []
    return sorted(df["country"].unique().tolist())


def predict_all_top_markets(
    excel_path: str,
    n_countries: int = 15,
    forecast_years: int = 2,
) -> list[dict[str, Any]]:
    """Predict ad spend for top N markets by total spend."""
    df = _load_country_data(excel_path)
    if df.empty:
        return []

    # Find top countries by latest year total
    latest_yr = df["year"].max()
    totals = df[df["year"] == latest_yr].groupby("country")["value"].sum()
    top_countries = totals.nlargest(n_countries).index.tolist()

    results = []
    for country in top_countries:
        pred = predict_country_ad_spend(country, excel_path, forecast_years)
        if pred.get("method") != "unavailable":
            results.append(pred)

    return results
