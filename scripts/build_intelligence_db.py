#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys

import pandas as pd


def _normalize_company(value: str) -> str:
    return str(value or "").replace("_", " ").strip()


def _normalize_quarter(value) -> str:
    text = str(value or "").strip().upper()
    if text.startswith("Q") and len(text) > 1 and text[1].isdigit():
        return f"Q{int(text[1])}"
    n = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.notna(n):
        q = int(n)
        if 1 <= q <= 4:
            return f"Q{q}"
    return text


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    return df if df is not None else pd.DataFrame()


def _collect_transcript_rows(repo_root: Path, transcript_root: Path) -> pd.DataFrame:
    index_path = transcript_root / "transcript_index.csv"
    index_df = _load_csv(index_path)
    rows: list[dict] = []

    if index_df.empty:
        for company_dir in sorted([p for p in transcript_root.iterdir() if p.is_dir()]):
            company = _normalize_company(company_dir.name)
            for year_dir in sorted([p for p in company_dir.iterdir() if p.is_dir() and p.name.isdigit()]):
                year = int(year_dir.name)
                for q_file in sorted([p for p in year_dir.iterdir() if p.is_file() and p.suffix.lower() == ".txt"]):
                    q = _normalize_quarter(q_file.stem)
                    if q not in {"Q1", "Q2", "Q3", "Q4"}:
                        continue
                    text = q_file.read_text(encoding="utf-8", errors="ignore")
                    rows.append(
                        {
                            "company": company,
                            "year": year,
                            "quarter": q,
                            "full_text": text,
                            "word_count": len(text.split()),
                        }
                    )
        return pd.DataFrame(rows)

    idx = index_df.copy()
    idx.columns = [str(c).strip().lower() for c in idx.columns]
    for col in ["company", "year", "quarter", "file_path", "word_count"]:
        if col not in idx.columns:
            idx[col] = ""

    for row in idx.itertuples(index=False):
        company = _normalize_company(getattr(row, "company", ""))
        year = pd.to_numeric(pd.Series([getattr(row, "year", None)]), errors="coerce").iloc[0]
        quarter = _normalize_quarter(getattr(row, "quarter", ""))
        if not company or pd.isna(year) or quarter not in {"Q1", "Q2", "Q3", "Q4"}:
            continue

        rel_path = str(getattr(row, "file_path", "") or "").strip()
        file_path = (repo_root / rel_path).resolve() if rel_path else None
        if not file_path or not file_path.exists():
            fallback = transcript_root / company.replace(" ", "_") / str(int(year)) / f"{quarter}.txt"
            file_path = fallback if fallback.exists() else None
        if not file_path or not file_path.exists():
            continue

        text = file_path.read_text(encoding="utf-8", errors="ignore")
        word_count = pd.to_numeric(pd.Series([getattr(row, "word_count", None)]), errors="coerce").iloc[0]
        rows.append(
            {
                "company": company,
                "year": int(year),
                "quarter": quarter,
                "full_text": text,
                "word_count": int(word_count) if pd.notna(word_count) else len(text.split()),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["company", "year", "quarter", "full_text", "word_count"])
    return pd.DataFrame(rows)


def _transcript_id_map(conn: sqlite3.Connection) -> dict[tuple[str, int, str], int]:
    rows = conn.execute("SELECT id, company, year, quarter FROM transcripts").fetchall()
    mapping: dict[tuple[str, int, str], int] = {}
    for transcript_id, company, year, quarter in rows:
        mapping[(str(company).strip().lower(), int(year), _normalize_quarter(quarter))] = int(transcript_id)
    return mapping


def _key(company: str, year, quarter) -> tuple[str, int, str] | None:
    y = pd.to_numeric(pd.Series([year]), errors="coerce").iloc[0]
    if pd.isna(y):
        return None
    c = _normalize_company(company)
    q = _normalize_quarter(quarter)
    if not c or q not in {"Q1", "Q2", "Q3", "Q4"}:
        return None
    return (c.lower(), int(y), q)


def ingest_transcripts(conn: sqlite3.Connection, repo_root: Path, transcript_root: Path) -> int:
    rows_df = _collect_transcript_rows(repo_root, transcript_root)
    if rows_df.empty:
        return 0

    indexed_date = datetime.now(timezone.utc).isoformat()
    payload = []
    for row in rows_df.itertuples(index=False):
        payload.append(
            (
                _normalize_company(getattr(row, "company", "")),
                int(getattr(row, "year")),
                _normalize_quarter(getattr(row, "quarter", "")),
                str(getattr(row, "full_text", "") or ""),
                int(getattr(row, "word_count", 0) or 0),
                indexed_date,
            )
        )

    conn.executemany(
        """
        INSERT INTO transcripts (company, year, quarter, full_text, word_count, indexed_date)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(company, year, quarter) DO UPDATE SET
            full_text=excluded.full_text,
            word_count=excluded.word_count,
            indexed_date=excluded.indexed_date
        """,
        payload,
    )
    conn.commit()
    return len(payload)


def ingest_topics(conn: sqlite3.Connection, topics_csv: Path) -> int:
    df = _load_csv(topics_csv)
    if df.empty:
        conn.execute("DELETE FROM transcript_topics")
        conn.commit()
        return 0

    df.columns = [str(c).strip().lower() for c in df.columns]
    for col in ["company", "year", "quarter", "topic", "text", "speaker"]:
        if col not in df.columns:
            df[col] = ""

    transcript_map = _transcript_id_map(conn)
    payload = []
    for row in df.itertuples(index=False):
        row_key = _key(getattr(row, "company", ""), getattr(row, "year", None), getattr(row, "quarter", None))
        if row_key is None:
            continue
        transcript_id = transcript_map.get(row_key)
        if transcript_id is None:
            continue
        payload.append(
            (
                transcript_id,
                str(getattr(row, "topic", "") or "").strip(),
                "",
                1,
                str(getattr(row, "text", "") or "").strip(),
                str(getattr(row, "speaker", "") or "").strip(),
            )
        )

    conn.execute("DELETE FROM transcript_topics")
    if payload:
        conn.executemany(
            """
            INSERT INTO transcript_topics (transcript_id, topic, keyword, mention_count, context_snippet, speaker)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    conn.commit()
    return len(payload)


def ingest_kpis(conn: sqlite3.Connection, kpis_csv: Path) -> int:
    df = _load_csv(kpis_csv)
    if df.empty:
        conn.execute("DELETE FROM transcript_kpis")
        conn.commit()
        return 0

    df.columns = [str(c).strip().lower() for c in df.columns]
    for col in ["company", "year", "quarter", "kpi_type", "value_text", "value_numeric", "unit", "context_sentence", "confidence"]:
        if col not in df.columns:
            df[col] = ""

    transcript_map = _transcript_id_map(conn)
    payload = []
    for row in df.itertuples(index=False):
        row_key = _key(getattr(row, "company", ""), getattr(row, "year", None), getattr(row, "quarter", None))
        if row_key is None:
            continue
        transcript_id = transcript_map.get(row_key)
        if transcript_id is None:
            continue
        value_numeric = pd.to_numeric(pd.Series([getattr(row, "value_numeric", None)]), errors="coerce").iloc[0]
        confidence = pd.to_numeric(pd.Series([getattr(row, "confidence", None)]), errors="coerce").iloc[0]
        payload.append(
            (
                transcript_id,
                str(getattr(row, "kpi_type", "") or "").strip(),
                str(getattr(row, "value_text", "") or "").strip(),
                float(value_numeric) if pd.notna(value_numeric) else None,
                str(getattr(row, "unit", "") or "").strip(),
                str(getattr(row, "context_sentence", "") or "").strip(),
                float(confidence) if pd.notna(confidence) else None,
            )
        )

    conn.execute("DELETE FROM transcript_kpis")
    if payload:
        conn.executemany(
            """
            INSERT INTO transcript_kpis (
                transcript_id, kpi_type, value_text, value_numeric, unit, context_sentence, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    conn.commit()
    return len(payload)


def ingest_highlights(conn: sqlite3.Connection, highlights_csv: Path) -> int:
    df = _load_csv(highlights_csv)
    if df.empty:
        conn.execute("DELETE FROM transcript_highlights")
        conn.commit()
        return 0

    df.columns = [str(c).strip().lower() for c in df.columns]
    for col in ["company", "year", "quarter", "highlight_type", "speaker", "text", "relevance_score", "quote", "score", "role_bucket"]:
        if col not in df.columns:
            df[col] = ""

    transcript_map = _transcript_id_map(conn)
    payload = []
    for row in df.itertuples(index=False):
        row_key = _key(getattr(row, "company", ""), getattr(row, "year", None), getattr(row, "quarter", None))
        if row_key is None:
            continue
        transcript_id = transcript_map.get(row_key)
        if transcript_id is None:
            continue

        highlight_type = str(getattr(row, "highlight_type", "") or "").strip()
        if not highlight_type:
            role_bucket = str(getattr(row, "role_bucket", "") or "").strip().upper()
            if role_bucket == "CEO":
                highlight_type = "CEO_Quote"
            elif role_bucket == "CFO":
                highlight_type = "CFO_Financial_Detail"
            else:
                highlight_type = "Strategic_Announcement"

        text = str(getattr(row, "text", "") or "").strip() or str(getattr(row, "quote", "") or "").strip()
        score_value = pd.to_numeric(pd.Series([getattr(row, "relevance_score", None)]), errors="coerce").iloc[0]
        if pd.isna(score_value):
            score_value = pd.to_numeric(pd.Series([getattr(row, "score", None)]), errors="coerce").iloc[0]

        if not text:
            continue

        payload.append(
            (
                transcript_id,
                highlight_type,
                str(getattr(row, "speaker", "") or "").strip(),
                text,
                float(score_value) if pd.notna(score_value) else None,
            )
        )

    conn.execute("DELETE FROM transcript_highlights")
    if payload:
        conn.executemany(
            """
            INSERT INTO transcript_highlights (transcript_id, highlight_type, speaker, text, relevance_score)
            VALUES (?, ?, ?, ?, ?)
            """,
            payload,
        )
    conn.commit()
    return len(payload)


def ingest_forward_signals(conn: sqlite3.Connection, repo_root: Path) -> int:
    """
    Populate forward_signals table.
    Prefers scored_signals.csv (pre-computed by extract_transcript_topics.py
    using the unified 5-layer engine from scoring_config.py).
    Falls back to live extraction from Excel if CSV not found.
    """
    # Try pre-scored CSV first (produced by pipeline step 2)
    csv_path = repo_root / "earningscall_transcripts" / "scored_signals.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        if not df.empty:
            conn.execute("DELETE FROM forward_signals")
            total = 0
            for _, row in df.iterrows():
                conn.execute(
                    """INSERT INTO forward_signals
                       (company, year, quarter, quote, speaker, role, score, category,
                        has_number, has_year_ref, future_tense_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(row.get("company", "")),
                        int(row.get("year", 0)),
                        str(row.get("quarter", "")),
                        str(row.get("quote", ""))[:500],
                        str(row.get("speaker", "")),
                        str(row.get("role", "")),
                        float(row.get("score", 0)),
                        str(row.get("category", "")),
                        int(row.get("has_number", 0)),
                        int(row.get("has_year_ref", 0)),
                        float(row.get("future_tense_score", 0)),
                    ),
                )
                total += 1
            conn.commit()
            print(f"  Ingested {total} pre-scored signals from {csv_path.name}")
            return total

    # Fallback: live extraction from Excel (slower)
    app_dir = repo_root / "app"
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    try:
        from utils.transcript_live import extract_forward_looking_signals
    except ImportError:
        print("Warning: could not import extract_forward_looking_signals — skipping forward signals")
        return 0

    excel_candidates = [
        repo_root / "app" / "attached_assets" / "Financial_Data.xlsx",
        repo_root / "attached_assets" / "Financial_Data.xlsx",
    ]
    for d in [repo_root / "app" / "attached_assets", repo_root / "attached_assets"]:
        if d.is_dir():
            for f in d.iterdir():
                if f.suffix.lower() == ".xlsx" and f not in excel_candidates:
                    excel_candidates.append(f)

    excel_path = None
    for p in excel_candidates:
        if p.exists():
            excel_path = str(p)
            break
    if not excel_path:
        print("Warning: no Excel workbook found for forward signals extraction")
        return 0

    rows = conn.execute(
        "SELECT DISTINCT company, year, quarter FROM transcripts ORDER BY company, year, quarter"
    ).fetchall()

    conn.execute("DELETE FROM forward_signals")
    total = 0
    for company, year, quarter in rows:
        signals = extract_forward_looking_signals(
            excel_path, company=company, year=int(year),
            quarter=str(quarter), max_signals=10,
        )
        for sig in signals:
            conn.execute(
                """INSERT INTO forward_signals
                   (company, year, quarter, quote, speaker, role, score, category,
                    has_number, has_year_ref, future_tense_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sig["company"], sig["year"], sig["quarter"],
                    sig["quote"], sig.get("speaker", ""), sig.get("role", ""),
                    sig.get("score", 0), sig.get("category", ""),
                    int(sig.get("has_number", False)),
                    int(sig.get("has_year_ref", False)),
                    sig.get("score", 0),
                ),
            )
            total += 1
    conn.commit()
    return total


def _ad_column_to_company() -> dict[str, str]:
    """Map Company_advertising_revenue column names to canonical company names."""
    return {
        "Google_Ads": "Alphabet",
        "Meta_Ads": "Meta Platforms",
        "Amazon_Ads": "Amazon",
        "Spotify_Ads": "Spotify",
        "*WBD_Ads": "Warner Bros Discovery",
        "*Microsoft_Ads": "Microsoft",
        "Paramount": "Paramount Global",
        "*Apple": "Apple",
        "*Disney": "Disney",
        "*Comcast": "Comcast",
        "Netflix*": "Netflix",
        "Twitter/X": "Twitter",
        "TikTok": "TikTok",
        "Snapchat": "Snapchat",
    }


_COMPANY_TICKER_MAP = {
    "Alphabet": "GOOGL",
    "Amazon": "AMZN",
    "Apple": "AAPL",
    "Comcast": "CMCSA",
    "Disney": "DIS",
    "Meta Platforms": "META",
    "Microsoft": "MSFT",
    "Netflix": "NFLX",
    "Paramount Global": "PARA",
    "Roku": "ROKU",
    "Spotify": "SPOT",
    "Warner Bros Discovery": "WBD",
    "Samsung": "005930.KS",
    "Tencent": "TCEHY",
    "MFE": "MFEA.MI",
}


def ingest_company_metrics(conn: sqlite3.Connection, repo_root: Path) -> int:
    """Populate company_metrics from Google Sheets workbook.

    Merges three sheets:
      - Company_metrics_earnings_values → revenue, operating_income, net_income, etc.
      - Company_Employees → employee_count
      - Company_advertising_revenue → advertising_revenue
    """
    app_dir = repo_root / "app"
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    try:
        from utils.workbook_source import resolve_financial_data_xlsx
    except ImportError:
        print("Warning: could not import workbook_source — skipping company_metrics")
        return 0

    wb_path = resolve_financial_data_xlsx()
    if not wb_path:
        print("Warning: no workbook available — skipping company_metrics")
        return 0

    # ── Load financial metrics ───────────────────────────────────────
    try:
        metrics_df = pd.read_excel(wb_path, sheet_name="Company_metrics_earnings_values")
    except Exception as exc:
        print(f"Warning: failed to read Company_metrics_earnings_values: {exc}")
        return 0

    metrics_df.columns = [str(c).strip() for c in metrics_df.columns]
    col_map = {
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
    metrics_df = metrics_df.rename(columns=col_map)
    for col in col_map.values():
        if col not in metrics_df.columns:
            metrics_df[col] = None
    metrics_df["company"] = metrics_df["company"].apply(_normalize_company)
    metrics_df["year"] = pd.to_numeric(metrics_df["year"], errors="coerce")
    metrics_df = metrics_df.dropna(subset=["company", "year"])
    metrics_df["year"] = metrics_df["year"].astype(int)

    # ── Load employees ───────────────────────────────────────────────
    try:
        emp_df = pd.read_excel(wb_path, sheet_name="Company_Employees")
        emp_df.columns = [str(c).strip() for c in emp_df.columns]
        emp_df = emp_df.rename(columns={"Company": "company", "Year": "year", "Employee Count": "employee_count"})
        emp_df["company"] = emp_df["company"].apply(_normalize_company)
        emp_df["year"] = pd.to_numeric(emp_df["year"], errors="coerce")
        emp_df = emp_df.dropna(subset=["company", "year"])
        emp_df["year"] = emp_df["year"].astype(int)
    except Exception as exc:
        print(f"Warning: failed to read Company_Employees: {exc}")
        emp_df = pd.DataFrame(columns=["company", "year", "employee_count"])

    # ── Load ad revenue (wide format → melt) ─────────────────────────
    try:
        ad_df = pd.read_excel(wb_path, sheet_name="Company_advertising_revenue")
        ad_df.columns = [str(c).strip() for c in ad_df.columns]
        ad_col_map = _ad_column_to_company()
        ad_rows: list[dict] = []
        for _, row in ad_df.iterrows():
            year_val = pd.to_numeric(pd.Series([row.get("Year")]), errors="coerce").iloc[0]
            if pd.isna(year_val):
                continue
            for col_name, comp_name in ad_col_map.items():
                val = row.get(col_name)
                if pd.notna(val):
                    ad_rows.append({
                        "company": _normalize_company(comp_name),
                        "year": int(year_val),
                        "advertising_revenue": float(val) * 1000,  # $B → $M to match metrics sheet
                    })
        ad_melted = pd.DataFrame(ad_rows) if ad_rows else pd.DataFrame(columns=["company", "year", "advertising_revenue"])
    except Exception as exc:
        print(f"Warning: failed to read Company_advertising_revenue: {exc}")
        ad_melted = pd.DataFrame(columns=["company", "year", "advertising_revenue"])

    # ── Merge all three sources ──────────────────────────────────────
    merged = metrics_df.copy()
    if not emp_df.empty:
        merged = merged.merge(emp_df[["company", "year", "employee_count"]], on=["company", "year"], how="left")
    else:
        merged["employee_count"] = None
    if not ad_melted.empty:
        merged = merged.merge(ad_melted[["company", "year", "advertising_revenue"]], on=["company", "year"], how="left")
    else:
        merged["advertising_revenue"] = None

    # Add ticker
    merged["ticker"] = merged["company"].map(_COMPANY_TICKER_MAP)

    # ── Upsert into SQLite ───────────────────────────────────────────
    conn.execute("DELETE FROM company_metrics")
    total = 0
    for _, row in merged.iterrows():
        conn.execute(
            """INSERT INTO company_metrics
               (company, ticker, year, quarter, revenue, cost_of_revenue,
                operating_income, net_income, capex, r_and_d, total_assets,
                market_cap, cash_balance, debt, employee_count, advertising_revenue)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(company, year, quarter) DO UPDATE SET
                 ticker=excluded.ticker, revenue=excluded.revenue,
                 cost_of_revenue=excluded.cost_of_revenue,
                 operating_income=excluded.operating_income,
                 net_income=excluded.net_income, capex=excluded.capex,
                 r_and_d=excluded.r_and_d, total_assets=excluded.total_assets,
                 market_cap=excluded.market_cap, cash_balance=excluded.cash_balance,
                 debt=excluded.debt, employee_count=excluded.employee_count,
                 advertising_revenue=excluded.advertising_revenue""",
            (
                str(row["company"]),
                str(row.get("ticker") or ""),
                int(row["year"]),
                "",  # quarter — annual data, no quarter
                float(row["revenue"]) if pd.notna(row.get("revenue")) else None,
                float(row["cost_of_revenue"]) if pd.notna(row.get("cost_of_revenue")) else None,
                float(row["operating_income"]) if pd.notna(row.get("operating_income")) else None,
                float(row["net_income"]) if pd.notna(row.get("net_income")) else None,
                float(row["capex"]) if pd.notna(row.get("capex")) else None,
                float(row["r_and_d"]) if pd.notna(row.get("r_and_d")) else None,
                float(row["total_assets"]) if pd.notna(row.get("total_assets")) else None,
                float(row["market_cap"]) if pd.notna(row.get("market_cap")) else None,
                float(row["cash_balance"]) if pd.notna(row.get("cash_balance")) else None,
                float(row["debt"]) if pd.notna(row.get("debt")) else None,
                float(row["employee_count"]) if pd.notna(row.get("employee_count")) else None,
                float(row["advertising_revenue"]) if pd.notna(row.get("advertising_revenue")) else None,
            ),
        )
        total += 1
    conn.commit()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SQLite earningscall intelligence database from extracted CSV files")
    parser.add_argument("--db", default="earningscall_intelligence.db", help="Output SQLite database path")
    parser.add_argument("--root", default="earningscall_transcripts", help="Transcript folder")
    parser.add_argument("--topics-csv", default="earningscall_transcripts/transcript_topics.csv", help="Transcript topics CSV")
    parser.add_argument("--kpis-csv", default="earningscall_transcripts/transcript_kpis.csv", help="Transcript KPI CSV")
    parser.add_argument("--highlights-csv", default="earningscall_transcripts/transcript_highlights.csv", help="Transcript highlights CSV")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))

    from intelligence_db_schema import ensure_schema  # noqa: WPS433

    db_path = (repo_root / args.db).resolve()
    transcript_root = (repo_root / args.root).resolve()

    conn = sqlite3.connect(str(db_path))
    try:
        ensure_schema(conn)
        transcripts_count = ingest_transcripts(conn, repo_root, transcript_root)
        topics_count = ingest_topics(conn, (repo_root / args.topics_csv).resolve())
        kpis_count = ingest_kpis(conn, (repo_root / args.kpis_csv).resolve())
        highlights_count = ingest_highlights(conn, (repo_root / args.highlights_csv).resolve())
        forward_count = ingest_forward_signals(conn, repo_root)
        metrics_count = ingest_company_metrics(conn, repo_root)
    finally:
        conn.close()

    print(f"Database: {db_path}")
    print(f"Upserted transcripts: {transcripts_count}")
    print(f"Loaded transcript topics: {topics_count}")
    print(f"Loaded transcript KPIs: {kpis_count}")
    print(f"Loaded transcript highlights: {highlights_count}")
    print(f"Loaded forward signals: {forward_count}")
    print(f"Loaded company metrics: {metrics_count}")


if __name__ == "__main__":
    main()
