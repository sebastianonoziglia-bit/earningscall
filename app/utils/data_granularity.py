from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st


# Known workbook sheets and their native temporal granularity.
KNOWN_SHEET_GRANULARITY: dict[str, str] = {
    "Stocks & Crypto": "Daily",
    "USD Inflation": "Annual",
    "Nasdaq Composite Est. (FRED)": "Monthly",
    "Country_Totals_vs_GDP": "Annual",
    "Country_Totals_vs_GDP_RAW": "Annual",
    "Country_Advertising_Data_FullVi": "Annual",
    "Country_avg_timespent_intrnt24": "Snapshot",
    "Global_Adv_Aggregates": "Annual",
    "Global Advertising (GroupM)": "Annual",
    "(GroupM) Granular": "Annual",
    "M2_values": "Monthly",
    "Company_metrics_earnings_values": "Annual",
    "Company_Employees": "Annual",
    "Company_Segments_insights_text": "Annual",
    "Company_insights_text": "Annual",
    "Company_advertising_revenue": "Annual",
    "Company_subscribers_values": "Quarterly",
    "Hardware_Smartphone_Shipments": "Annual",
    "Macro_Wealth_by_Generation": "Annual",
    "Company_revenue_by_region": "Annual",
    "Company_minute&dollar_earned": "Snapshot",
    "Company_yearly_segments_values": "Annual",
    "Company_Quarterly_segments_valu": "Quarterly",
    "Overview_Macro": "Quarterly",
    "Overview_Insights": "Quarterly",
    "Overview_Charts": "Quarterly",
    "Transcripts": "Quarterly",
}


def _norm_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _parse_quarter(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().upper()
    if not text:
        return None

    # Q1 / q1 / Quarter 1 / 1Q24 / Q1 2024
    match_q = re.search(r"\bQ\s*([1-4])\b", text)
    if match_q:
        return int(match_q.group(1))
    match_lq = re.search(r"\b([1-4])\s*Q\b", text)
    if match_lq:
        return int(match_lq.group(1))
    match_num = re.fullmatch(r"[1-4]", text)
    if match_num:
        return int(text)

    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.notna(numeric):
        q = int(numeric)
        if 1 <= q <= 4:
            return q
    return None


def _find_col(df: pd.DataFrame, aliases: list[str]) -> str | None:
    normalized = {_norm_text(c): c for c in df.columns}
    for alias in aliases:
        key = _norm_text(alias)
        if key in normalized:
            return normalized[key]
    return None


@st.cache_data(ttl=3600)
def get_workbook_sheet_names(excel_path: str) -> list[str]:
    if not excel_path:
        return []
    try:
        xl = pd.ExcelFile(excel_path)
        return [str(name).strip() for name in xl.sheet_names]
    except Exception:
        return []


@st.cache_data(ttl=3600)
def get_sheet_granularity_library(excel_path: str) -> dict[str, str]:
    names = get_workbook_sheet_names(excel_path)
    if not names:
        return {}

    known_lookup = {_norm_text(k): v for k, v in KNOWN_SHEET_GRANULARITY.items()}
    out: dict[str, str] = {}
    for name in names:
        out[name] = known_lookup.get(_norm_text(name), "Unknown")
    return out


@st.cache_data(ttl=1800)
def get_available_granularity_options(excel_path: str, include_auto: bool = True) -> list[str]:
    library = get_sheet_granularity_library(excel_path)
    available_types = {str(v).strip().title() for v in library.values()}
    options: list[str] = []

    if include_auto:
        options.append("Auto")

    # Always keep annual available as baseline mode.
    options.append("Annual")
    if "Quarterly" in available_types:
        options.append("Quarterly")
    if "Monthly" in available_types:
        options.append("Monthly")
    if "Daily" in available_types:
        options.append("Daily")

    # Keep insertion order while deduplicating.
    return list(dict.fromkeys(options))


@st.cache_data(ttl=1800)
def get_quarter_labels_for_year(
    excel_path: str,
    year: int,
    sheet_preferences: tuple[str, ...] = ("Overview_Insights", "Overview_Macro", "Company_subscribers_values"),
) -> list[str]:
    if not excel_path:
        return []
    names = set(get_workbook_sheet_names(excel_path))
    qset: set[int] = set()

    for sheet in sheet_preferences:
        if sheet not in names:
            continue
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet)
        except Exception:
            continue
        if df is None or df.empty:
            continue

        year_col = _find_col(df, ["year", "fiscal_year"])
        quarter_col = _find_col(df, ["quarter", "quarter_num", "qtr", "q"])
        date_col = _find_col(df, ["date", "observation_date", "period", "he", "usd_observation_date"])
        if not year_col:
            continue

        work = df.copy()
        work[year_col] = pd.to_numeric(work[year_col], errors="coerce")
        work = work[work[year_col] == int(year)].copy()
        if work.empty:
            continue

        if quarter_col:
            quarters = work[quarter_col].apply(_parse_quarter).dropna().astype(int).tolist()
            qset.update({q for q in quarters if 1 <= q <= 4})
            continue

        if date_col:
            dt = pd.to_datetime(work[date_col], errors="coerce")
            qset.update({int(q) for q in dt.dt.quarter.dropna().astype(int).tolist() if 1 <= int(q) <= 4})

    return [f"Q{q}" for q in sorted(qset)]


@st.cache_data(ttl=1800)
def get_month_labels_for_year(excel_path: str, year: int) -> list[str]:
    if not excel_path:
        return []
    names = set(get_workbook_sheet_names(excel_path))
    if "M2_values" not in names:
        return []

    try:
        df = pd.read_excel(excel_path, sheet_name="M2_values")
    except Exception:
        return []
    if df is None or df.empty:
        return []

    date_col = _find_col(df, ["USD observation_date", "observation_date", "date", "he"])
    if not date_col:
        return []
    dt = pd.to_datetime(df[date_col], errors="coerce")
    scope = dt[dt.dt.year == int(year)].dropna()
    if scope.empty:
        return []
    return sorted(scope.dt.strftime("%Y-%m").unique().tolist())


@st.cache_data(ttl=1800)
def get_day_labels_for_year(excel_path: str, year: int) -> list[str]:
    if not excel_path:
        return []
    names = set(get_workbook_sheet_names(excel_path))
    if "Stocks & Crypto" not in names:
        return []

    try:
        df = pd.read_excel(excel_path, sheet_name="Stocks & Crypto", usecols=["date"])
    except Exception:
        try:
            df = pd.read_excel(excel_path, sheet_name="Stocks & Crypto")
        except Exception:
            return []
    if df is None or df.empty:
        return []

    date_col = _find_col(df, ["date", "datetime", "timestamp"])
    if not date_col:
        return []
    dt = pd.to_datetime(df[date_col], errors="coerce")
    scope = dt[dt.dt.year == int(year)].dropna()
    if scope.empty:
        return []
    return sorted(scope.dt.strftime("%Y-%m-%d").unique().tolist())


def update_global_time_context(
    *,
    page: str,
    granularity: str,
    year: int | None = None,
    quarter: str | None = None,
    month: str | None = None,
    day: str | None = None,
    year_range: tuple[int, int] | None = None,
    excel_path: str | None = None,
) -> dict[str, Any]:
    context = {
        "page": str(page or ""),
        "granularity": str(granularity or "Auto"),
        "year": int(year) if year is not None else None,
        "quarter": str(quarter or "").strip() or None,
        "month": str(month or "").strip() or None,
        "day": str(day or "").strip() or None,
        "year_range": tuple(year_range) if year_range else None,
        "sheet_granularity_library": get_sheet_granularity_library(excel_path or ""),
    }
    st.session_state["global_time_context"] = context
    return context

