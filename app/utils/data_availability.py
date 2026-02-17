from __future__ import annotations

import re
from typing import Iterable

import pandas as pd


def _normalize_colname(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name or "").strip().lower()).strip("_")


def _find_column(df: pd.DataFrame, aliases: Iterable[str]) -> str | None:
    if df is None or df.empty:
        return None
    normalized = {_normalize_colname(c): c for c in df.columns}
    for alias in aliases:
        key = _normalize_colname(alias)
        if key in normalized:
            return normalized[key]
    return None


def _parse_quarter(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    if text.startswith("Q") and len(text) > 1 and text[1].isdigit():
        quarter = int(text[1])
        return quarter if 1 <= quarter <= 4 else None
    match = re.search(r"\b([1-4])\b", text)
    if match:
        return int(match.group(1))
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    quarter = int(numeric)
    return quarter if 1 <= quarter <= 4 else None


def _subset_for_scope(
    df: pd.DataFrame,
    year: int,
    company: str | None = None,
    ticker: str | None = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    work = df.copy()
    year_col = _find_column(work, ["year"])
    quarter_col = _find_column(work, ["quarter", "quarter_num", "qtr"])
    company_col = _find_column(work, ["company", "player"])
    ticker_col = _find_column(work, ["ticker", "symbol"])

    if not year_col:
        return pd.DataFrame()

    work[year_col] = pd.to_numeric(work[year_col], errors="coerce")
    work = work[work[year_col] == int(year)].copy()
    if work.empty:
        return pd.DataFrame()

    if company and company_col:
        cval = str(company).strip().lower()
        work = work[
            work[company_col]
            .astype(str)
            .str.strip()
            .str.lower()
            == cval
        ].copy()
    if ticker and ticker_col:
        tval = str(ticker).strip().upper()
        work = work[
            work[ticker_col]
            .astype(str)
            .str.strip()
            .str.upper()
            == tval
        ].copy()
    if work.empty:
        return pd.DataFrame()

    if quarter_col:
        work["_quarter_num"] = work[quarter_col].apply(_parse_quarter)
    else:
        work["_quarter_num"] = pd.NA
    return work


def is_quarter_complete(
    df: pd.DataFrame,
    year: int,
    quarter: int,
    company: str | None = None,
    ticker: str | None = None,
) -> bool:
    scoped = _subset_for_scope(df, year=year, company=company, ticker=ticker)
    if scoped.empty:
        return False
    q = int(quarter)
    return bool((scoped["_quarter_num"] == q).any())


def get_available_quarters(
    df: pd.DataFrame,
    year: int,
    company: str | None = None,
    ticker: str | None = None,
) -> list[int]:
    scoped = _subset_for_scope(df, year=year, company=company, ticker=ticker)
    if scoped.empty:
        return []
    quarters = (
        pd.to_numeric(scoped["_quarter_num"], errors="coerce")
        .dropna()
        .astype(int)
        .tolist()
    )
    unique = sorted({q for q in quarters if 1 <= int(q) <= 4})
    return unique


def is_year_complete(
    df: pd.DataFrame,
    year: int,
    company: str | None = None,
    ticker: str | None = None,
) -> bool:
    scoped = _subset_for_scope(df, year=year, company=company, ticker=ticker)
    if scoped.empty:
        return False

    available = set(get_available_quarters(scoped, year=year))
    if {1, 2, 3, 4}.issubset(available):
        return True

    # Annual fallback: rows with no quarter value are treated as year-level entries.
    annual_like = scoped["_quarter_num"].isna().any()
    return bool(annual_like)
