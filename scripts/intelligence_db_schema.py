from __future__ import annotations

import sqlite3


DDL = [
    """
    CREATE TABLE IF NOT EXISTS transcripts (
        id INTEGER PRIMARY KEY,
        company TEXT NOT NULL,
        year INTEGER NOT NULL,
        quarter TEXT NOT NULL,
        full_text TEXT,
        word_count INTEGER,
        indexed_date TIMESTAMP,
        UNIQUE(company, year, quarter)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transcript_topics (
        id INTEGER PRIMARY KEY,
        transcript_id INTEGER,
        topic TEXT NOT NULL,
        keyword TEXT,
        mention_count INTEGER,
        context_snippet TEXT,
        speaker TEXT,
        FOREIGN KEY (transcript_id) REFERENCES transcripts(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transcript_kpis (
        id INTEGER PRIMARY KEY,
        transcript_id INTEGER,
        kpi_type TEXT NOT NULL,
        value_text TEXT,
        value_numeric REAL,
        unit TEXT,
        context_sentence TEXT,
        confidence REAL,
        FOREIGN KEY (transcript_id) REFERENCES transcripts(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transcript_highlights (
        id INTEGER PRIMARY KEY,
        transcript_id INTEGER,
        highlight_type TEXT,
        speaker TEXT,
        text TEXT,
        relevance_score REAL,
        FOREIGN KEY (transcript_id) REFERENCES transcripts(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS company_metrics (
        id INTEGER PRIMARY KEY,
        company TEXT NOT NULL,
        ticker TEXT,
        year INTEGER,
        quarter TEXT,
        revenue REAL,
        cost_of_revenue REAL,
        operating_income REAL,
        net_income REAL,
        capex REAL,
        r_and_d REAL,
        total_assets REAL,
        market_cap REAL,
        cash_balance REAL,
        debt REAL,
        employee_count REAL,
        advertising_revenue REAL,
        UNIQUE(company, year, quarter)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_topics_company ON transcript_topics(topic);",
    "CREATE INDEX IF NOT EXISTS idx_kpis_type ON transcript_kpis(kpi_type);",
    "CREATE INDEX IF NOT EXISTS idx_transcripts_company_year ON transcripts(company, year);",
]


TABLE_COLUMN_MIGRATIONS = {
    "company_metrics": {
        "employee_count": "REAL",
        "advertising_revenue": "REAL",
    }
}


def _ensure_columns(conn: sqlite3.Connection, table_name: str, columns: dict[str, str]) -> None:
    current = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_cols = {str(row[1]).strip().lower() for row in current}
    for col_name, col_type in columns.items():
        if str(col_name).lower() in existing_cols:
            continue
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")


def ensure_schema(conn: sqlite3.Connection) -> None:
    for statement in DDL:
        conn.execute(statement)
    for table_name, columns in TABLE_COLUMN_MIGRATIONS.items():
        _ensure_columns(conn, table_name, columns)
    conn.commit()
