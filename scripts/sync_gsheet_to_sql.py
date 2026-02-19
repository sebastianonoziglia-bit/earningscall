#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys
import warnings

import pandas as pd


TICKER_TO_COMPANY = {
    "AAPL": "Apple",
    "AMZN": "Amazon",
    "CMCSA": "Comcast",
    "DIS": "Disney",
    "GOOGL": "Alphabet",
    "META": "Meta Platforms",
    "MSFT": "Microsoft",
    "NFLX": "Netflix",
    "PARA": "Paramount Global",
    "ROKU": "Roku",
    "WBD": "Warner Bros. Discovery",
    "SPOT": "Spotify",
    "MFE": "MFE",
}

COMPANY_ALIASES = {
    "google": "Alphabet",
    "alphabetgoogle": "Alphabet",
    "alphabet": "Alphabet",
    "meta": "Meta Platforms",
    "metaplatforms": "Meta Platforms",
    "facebook": "Meta Platforms",
    "warnerbrosdiscovery": "Warner Bros. Discovery",
    "warnerbrosdiscoveryinc": "Warner Bros. Discovery",
    "wbd": "Warner Bros. Discovery",
    "paramount": "Paramount Global",
    "paramountglobal": "Paramount Global",
}


def _norm_col(name: str) -> str:
    return (
        str(name or "")
        .strip()
        .lower()
        .replace("&", " and ")
        .replace("%", " pct ")
        .replace(".", " ")
        .replace("-", " ")
        .replace("/", " ")
    )


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    for col in df.columns:
        norm = "_".join(part for part in _norm_col(col).split() if part)
        col_map[col] = norm
    return df.rename(columns=col_map)


def _resolve_workbook_path(repo_root: Path) -> str:
    app_dir = repo_root / "app"
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    from utils.workbook_source import resolve_financial_data_xlsx  # noqa: WPS433

    workbook = resolve_financial_data_xlsx(
        [
            str(app_dir / "attached_assets" / "Earnings + stocks  copy.xlsx"),
            str(repo_root / "Earnings + stocks  copy.xlsx"),
        ]
    )
    if not workbook:
        raise RuntimeError("Workbook path could not be resolved")
    return workbook


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _norm_company(value: str) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _canonical_company(value: str) -> str:
    text = str(value or "").strip()
    norm = _norm_company(text)
    if norm in COMPANY_ALIASES:
        return COMPANY_ALIASES[norm]
    return text


def _load_quarterly_company_metrics(workbook_path: str) -> pd.DataFrame:
    df = pd.read_excel(workbook_path, sheet_name="Company_Quarterly_segments_valu")
    if df is None or df.empty:
        return pd.DataFrame()
    df = _normalize_columns(df)

    required = ["ticker", "year"]
    for col in required:
        if col not in df.columns:
            raise RuntimeError(f"Company_Quarterly_segments_valu missing required column: {col}")

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["year"] = _coerce_numeric(df["year"])
    df = df.dropna(subset=["ticker", "year"]).copy()
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["year"].astype(int)

    # Assign quarter by row order inside each ticker/year group.
    df = df.reset_index(drop=True)
    df["quarter_num"] = df.groupby(["ticker", "year"]).cumcount() + 1
    counts = df.groupby(["ticker", "year"])["quarter_num"].count().reset_index(name="q_count")
    complete = counts[counts["q_count"] >= 4][["ticker", "year"]]
    df = df.merge(complete, on=["ticker", "year"], how="inner")
    df = df[df["quarter_num"].between(1, 4)].copy()
    df["quarter"] = "Q" + df["quarter_num"].astype(int).astype(str)

    df["company"] = df["ticker"].map(TICKER_TO_COMPANY).fillna(df["ticker"]).apply(_canonical_company)

    metric_cols = {
        "revenue": "revenue",
        "cost_of_revenue": "cost_of_revenue",
        "operating_income": "operating_income",
        "net_income": "net_income",
        "capex": "capex",
        "r_d": "r_and_d",
        "r_and_d": "r_and_d",
        "total_assets": "total_assets",
        "market_cap": "market_cap",
        "market_cap_": "market_cap",
        "cash_balance": "cash_balance",
        "debt": "debt",
    }

    out = pd.DataFrame()
    out["company"] = df["company"].astype(str).str.strip().apply(_canonical_company)
    out["ticker"] = df["ticker"].astype(str).str.strip()
    out["year"] = df["year"].astype(int)
    out["quarter"] = df["quarter"].astype(str)

    for source_col, target_col in metric_cols.items():
        if source_col in df.columns:
            out[target_col] = _coerce_numeric(df[source_col])
        elif target_col not in out.columns:
            out[target_col] = pd.NA

    expected = [
        "company",
        "ticker",
        "year",
        "quarter",
        "revenue",
        "cost_of_revenue",
        "operating_income",
        "net_income",
        "capex",
        "r_and_d",
        "total_assets",
        "market_cap",
        "cash_balance",
        "debt",
    ]
    for col in expected:
        if col not in out.columns:
            out[col] = pd.NA

    return out[expected]


def _load_annual_company_metrics(workbook_path: str) -> pd.DataFrame:
    try:
        df = pd.read_excel(workbook_path, sheet_name="Company_metrics_earnings_values")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    df = _normalize_columns(df)
    if "company" not in df.columns or "year" not in df.columns:
        return pd.DataFrame()

    df["company"] = df["company"].astype(str).str.strip().apply(_canonical_company)
    df["year"] = _coerce_numeric(df["year"])
    df = df.dropna(subset=["company", "year"]).copy()
    if df.empty:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["company"] = df["company"].apply(_canonical_company)
    out["ticker"] = pd.NA
    out["year"] = df["year"].astype(int)
    out["quarter"] = "Annual"

    mapping = {
        "revenue": "revenue",
        "cost_of_revenue": "cost_of_revenue",
        "operating_income": "operating_income",
        "net_income": "net_income",
        "capex": "capex",
        "r_d": "r_and_d",
        "r_and_d": "r_and_d",
        "total_assets": "total_assets",
        "market_cap": "market_cap",
        "market_cap_": "market_cap",
        "cash_balance": "cash_balance",
        "debt": "debt",
    }
    for source_col, target_col in mapping.items():
        if source_col in df.columns:
            out[target_col] = _coerce_numeric(df[source_col])

    expected = [
        "company",
        "ticker",
        "year",
        "quarter",
        "revenue",
        "cost_of_revenue",
        "operating_income",
        "net_income",
        "capex",
        "r_and_d",
        "total_assets",
        "market_cap",
        "cash_balance",
        "debt",
    ]
    for col in expected:
        if col not in out.columns:
            out[col] = pd.NA

    return out[expected]


def _load_employee_count_map(workbook_path: str) -> dict[tuple[str, int], float]:
    try:
        df = pd.read_excel(workbook_path, sheet_name="Company_Employees")
    except Exception:
        return {}
    if df is None or df.empty:
        return {}
    df = _normalize_columns(df)
    company_col = "company" if "company" in df.columns else None
    year_col = "year" if "year" in df.columns else None
    employee_col = "employee_count" if "employee_count" in df.columns else ("employees" if "employees" in df.columns else None)
    if not company_col or not year_col or not employee_col:
        return {}
    work = pd.DataFrame()
    work["company"] = df[company_col].astype(str).str.strip().apply(_canonical_company)
    work["year"] = _coerce_numeric(df[year_col])
    work["employee_count"] = _coerce_numeric(df[employee_col])
    work = work.dropna(subset=["company", "year", "employee_count"])
    if work.empty:
        return {}
    work["year"] = work["year"].astype(int)
    return {
        (_norm_company(row.company), int(row.year)): float(row.employee_count)
        for row in work.itertuples(index=False)
    }


def _load_ad_revenue_map(workbook_path: str) -> dict[tuple[str, int], float]:
    try:
        df = pd.read_excel(workbook_path, sheet_name="Company_advertising_revenue")
    except Exception:
        return {}
    if df is None or df.empty:
        return {}
    df = _normalize_columns(df)
    if "year" not in df.columns:
        return {}
    df["year"] = _coerce_numeric(df["year"])
    df = df.dropna(subset=["year"]).copy()
    if df.empty:
        return {}
    df["year"] = df["year"].astype(int)

    col_to_company = {
        "google_ads": "Alphabet",
        "meta_ads": "Meta Platforms",
        "amazon_ads": "Amazon",
        "spotify_ads": "Spotify",
        "wbd_ads": "Warner Bros. Discovery",
        "microsoft_ads": "Microsoft",
        "paramount": "Paramount Global",
        "apple": "Apple",
        "disney": "Disney",
        "comcast": "Comcast",
        "netflix": "Netflix",
        "twitter_x": "Twitter/X",
        "tiktok": "TikTok",
        "snapchat": "Snapchat",
    }

    mapping: dict[tuple[str, int], float] = {}
    for col, company in col_to_company.items():
        if col not in df.columns:
            continue
        vals = _coerce_numeric(df[col])
        for year, value in zip(df["year"].tolist(), vals.tolist()):
            if pd.isna(value):
                continue
            mapping[(_norm_company(company), int(year))] = float(value)
    return mapping


def _attach_enrichment_columns(df: pd.DataFrame, workbook_path: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df
    out = df.copy()
    employee_map = _load_employee_count_map(workbook_path)
    ad_rev_map = _load_ad_revenue_map(workbook_path)

    def _lookup(company: str, year: int, source: dict[tuple[str, int], float]):
        return source.get((_norm_company(company), int(year)), pd.NA)

    out["employee_count"] = [
        _lookup(company, year, employee_map)
        for company, year in zip(out["company"], out["year"])
    ]
    out["advertising_revenue"] = [
        _lookup(company, year, ad_rev_map)
        for company, year in zip(out["company"], out["year"])
    ]
    return out


def _upsert_company_metrics(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    rows = []
    for row in df.itertuples(index=False):
        rows.append(
            (
                str(getattr(row, "company", "") or "").strip(),
                str(getattr(row, "ticker", "") or "").strip() or None,
                int(getattr(row, "year")),
                str(getattr(row, "quarter", "") or "").strip(),
                pd.to_numeric(pd.Series([getattr(row, "revenue", None)]), errors="coerce").iloc[0],
                pd.to_numeric(pd.Series([getattr(row, "cost_of_revenue", None)]), errors="coerce").iloc[0],
                pd.to_numeric(pd.Series([getattr(row, "operating_income", None)]), errors="coerce").iloc[0],
                pd.to_numeric(pd.Series([getattr(row, "net_income", None)]), errors="coerce").iloc[0],
                pd.to_numeric(pd.Series([getattr(row, "capex", None)]), errors="coerce").iloc[0],
                pd.to_numeric(pd.Series([getattr(row, "r_and_d", None)]), errors="coerce").iloc[0],
                pd.to_numeric(pd.Series([getattr(row, "total_assets", None)]), errors="coerce").iloc[0],
                pd.to_numeric(pd.Series([getattr(row, "market_cap", None)]), errors="coerce").iloc[0],
                pd.to_numeric(pd.Series([getattr(row, "cash_balance", None)]), errors="coerce").iloc[0],
                pd.to_numeric(pd.Series([getattr(row, "debt", None)]), errors="coerce").iloc[0],
                pd.to_numeric(pd.Series([getattr(row, "employee_count", None)]), errors="coerce").iloc[0],
                pd.to_numeric(pd.Series([getattr(row, "advertising_revenue", None)]), errors="coerce").iloc[0],
            )
        )

    conn.executemany(
        """
        INSERT INTO company_metrics (
            company, ticker, year, quarter, revenue, cost_of_revenue, operating_income,
            net_income, capex, r_and_d, total_assets, market_cap, cash_balance, debt,
            employee_count, advertising_revenue
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(company, year, quarter) DO UPDATE SET
            ticker=excluded.ticker,
            revenue=excluded.revenue,
            cost_of_revenue=excluded.cost_of_revenue,
            operating_income=excluded.operating_income,
            net_income=excluded.net_income,
            capex=excluded.capex,
            r_and_d=excluded.r_and_d,
            total_assets=excluded.total_assets,
            market_cap=excluded.market_cap,
            cash_balance=excluded.cash_balance,
            debt=excluded.debt,
            employee_count=excluded.employee_count,
            advertising_revenue=excluded.advertising_revenue
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync quarterly/annual company metrics from workbook into SQLite")
    parser.add_argument("--db", default="earningscall_intelligence.db", help="SQLite DB path")
    parser.add_argument("--workbook", default="", help="Optional workbook path override")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    from intelligence_db_schema import ensure_schema  # noqa: WPS433

    workbook_path = args.workbook.strip() or _resolve_workbook_path(repo_root)
    db_path = (repo_root / args.db).resolve()

    quarterly = _load_quarterly_company_metrics(workbook_path)
    annual = _load_annual_company_metrics(workbook_path)
    frames = [df for df in [quarterly, annual] if df is not None and not df.empty]
    if frames:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=FutureWarning,
                message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.*",
            )
            merged = pd.concat(frames, ignore_index=True)
    else:
        merged = pd.DataFrame()
    if not merged.empty:
        merged = _attach_enrichment_columns(merged, workbook_path)

    conn = sqlite3.connect(str(db_path))
    try:
        ensure_schema(conn)
        inserted = _upsert_company_metrics(conn, merged)
    finally:
        conn.close()

    print(f"Workbook: {workbook_path}")
    print(f"Database: {db_path}")
    print(f"Upserted company_metrics rows: {inserted}")


if __name__ == "__main__":
    main()
