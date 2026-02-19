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
    finally:
        conn.close()

    print(f"Database: {db_path}")
    print(f"Upserted transcripts: {transcripts_count}")
    print(f"Loaded transcript topics: {topics_count}")
    print(f"Loaded transcript KPIs: {kpis_count}")
    print(f"Loaded transcript highlights: {highlights_count}")


if __name__ == "__main__":
    main()
