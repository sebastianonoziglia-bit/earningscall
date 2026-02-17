"""
Utility functions for loading Federal Funds Rate data from Excel.
"""

from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from typing import Optional

import pandas as pd
import streamlit as st
from utils.workbook_source import resolve_financial_data_xlsx, get_workbook_source_stamp


@lru_cache(maxsize=2)
def _resolve_excel_path() -> Optional[str]:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "attached_assets", "Earnings + stocks  copy.xlsx"),
        os.path.join(base_dir, "..", "Earnings + stocks  copy.xlsx"),
        os.path.join(base_dir, "Earnings + stocks  copy.xlsx"),
    ]
    return resolve_financial_data_xlsx(candidates)


def _pick_column(columns_lower_map: dict[str, str], *candidates: str) -> Optional[str]:
    for candidate in candidates:
        if candidate in columns_lower_map:
            return columns_lower_map[candidate]
    return None


@st.cache_data(ttl=3600 * 24)
def _load_fed_funds_from_excel_cached(path: str, source_stamp: int) -> pd.DataFrame:

    sheet_candidates = [
        "Fed Fund Rates",
        "Fed Funds Rates",
        "Federal Funds Rate",
        "Federal Funds Rates",
    ]

    src = None
    for sheet_name in sheet_candidates:
        try:
            src = pd.read_excel(path, sheet_name=sheet_name).copy()
            break
        except Exception:
            continue
    if src is None or src.empty:
        return pd.DataFrame()

    src.columns = [str(c).strip() for c in src.columns]
    col_lower = {str(c).strip().lower(): c for c in src.columns}

    date_col = _pick_column(
        col_lower,
        "date",
        "observation_date",
        "observation date",
        "usd observation_date",
        "period",
    )
    year_col = _pick_column(col_lower, "year")
    value_col = _pick_column(
        col_lower,
        "fedfunds",
        "fed funds",
        "fed funds rate",
        "federal funds rate",
        "rate",
        "value",
    )

    if not value_col:
        # Last-resort heuristic: any column containing 'rate' or 'fund'.
        for c in src.columns:
            lc = str(c).strip().lower()
            if "rate" in lc or "fund" in lc:
                value_col = c
                break
    if not value_col:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["value"] = (
        src[value_col]
        .astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    out["value"] = pd.to_numeric(out["value"], errors="coerce")

    if date_col:
        out["date"] = pd.to_datetime(src[date_col], errors="coerce")
        out["year"] = out["date"].dt.year.astype("Int64")
        out["month"] = out["date"].dt.month.astype("Int64")
    elif year_col:
        out["year"] = pd.to_numeric(src[year_col], errors="coerce").astype("Int64")
        out["month"] = 12
        out["date"] = pd.to_datetime(
            out["year"].astype("Int64").astype(str) + "-12-31", errors="coerce"
        )
    else:
        return pd.DataFrame()

    out = out.dropna(subset=["year", "value"]).copy()
    if out.empty:
        return pd.DataFrame()

    out["year"] = out["year"].astype(int)
    out = out.sort_values(["year", "date"]).reset_index(drop=True)
    return out


def _load_fed_funds_from_excel() -> pd.DataFrame:
    path = _resolve_excel_path()
    if not path:
        return pd.DataFrame()
    source_stamp = get_workbook_source_stamp(path)
    return _load_fed_funds_from_excel_cached(path, source_stamp)


@st.cache_data(ttl=3600)
def get_fed_funds_monthly_data(start_year: int = 1950, end_year: Optional[int] = None) -> pd.DataFrame:
    if end_year is None:
        end_year = datetime.now().year
    df = _load_fed_funds_from_excel()
    if df.empty:
        return pd.DataFrame()
    sub = df[(df["year"] >= int(start_year)) & (df["year"] <= int(end_year))].copy()
    return sub.reset_index(drop=True)


@st.cache_data(ttl=3600)
def get_fed_funds_annual_data(
    start_year: int = 1950,
    end_year: Optional[int] = None,
    method: str = "average",
) -> pd.DataFrame:
    if end_year is None:
        end_year = datetime.now().year

    monthly = get_fed_funds_monthly_data(start_year=start_year, end_year=end_year)
    if monthly.empty:
        return pd.DataFrame()

    monthly = monthly.sort_values(["year", "date"]).copy()
    agg = monthly.groupby("year", as_index=False)["value"].agg(["mean", "last"]).reset_index()
    agg.columns = ["year", "average_rate", "year_end_rate"]
    agg["year"] = agg["year"].astype(int)
    method_l = str(method or "average").strip().lower()
    if method_l in {"year_end", "year-end", "year end", "end"}:
        agg["value"] = agg["year_end_rate"]
    else:
        agg["value"] = agg["average_rate"]
    agg["annual_change"] = agg["value"].diff()
    return agg.sort_values("year").reset_index(drop=True)
