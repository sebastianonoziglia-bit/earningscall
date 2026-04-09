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
    """
    CREATE TABLE IF NOT EXISTS forward_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        year INTEGER NOT NULL,
        quarter TEXT NOT NULL,
        quote TEXT NOT NULL,
        speaker TEXT,
        role TEXT,
        score REAL,
        category TEXT,
        has_number INTEGER DEFAULT 0,
        has_year_ref INTEGER DEFAULT 0,
        future_tense_score REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_fs_company_year ON forward_signals(company, year, quarter);",
    "CREATE INDEX IF NOT EXISTS idx_fs_score ON forward_signals(score DESC);",
    # ── Oracle prediction tables ──────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS oracle_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        metric TEXT NOT NULL,
        as_of_date TEXT NOT NULL,
        forecast_horizon TEXT NOT NULL,
        direction TEXT,
        confidence REAL,
        signal_score REAL,
        market_score REAL,
        fundamental_score REAL,
        composite_score REAL,
        latest_actual_value REAL,
        latest_actual_period TEXT,
        forecast_value REAL,
        forecast_delta_pct REAL,
        forecast_unit TEXT,
        summary TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_oracle_pred_company ON oracle_predictions(company);",
    "CREATE INDEX IF NOT EXISTS idx_oracle_pred_date ON oracle_predictions(as_of_date);",
    """
    CREATE TABLE IF NOT EXISTS oracle_prediction_factors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        metric TEXT NOT NULL,
        as_of_date TEXT NOT NULL,
        forecast_horizon TEXT NOT NULL,
        layer TEXT,
        factor_name TEXT,
        contribution REAL,
        factor_value REAL,
        factor_display TEXT,
        detail TEXT,
        sort_order INTEGER
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_oracle_factors_company ON oracle_prediction_factors(company, metric);",
    # ── MiroFish swarm run tables ─────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS mirofish_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT UNIQUE,
        created_at TEXT,
        scope TEXT,
        scope_key TEXT,
        horizon_year INTEGER,
        agents INTEGER,
        rounds INTEGER,
        scenario TEXT,
        preset TEXT,
        graph_json TEXT,
        report_json TEXT,
        baseline_groupm_growth REAL,
        mirofish_growth_mu REAL,
        mirofish_growth_sigma REAL,
        deviation_from_groupm REAL,
        confidence REAL,
        cost_usd REAL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_mirofish_scope ON mirofish_runs(scope, scope_key);",
    "CREATE INDEX IF NOT EXISTS idx_mirofish_horizon ON mirofish_runs(horizon_year);",
    # ── Polymarket snapshots ─────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS polymarket_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_id TEXT NOT NULL,
        snapshot_ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
        question TEXT,
        slug TEXT,
        yes_price REAL,
        no_price REAL,
        volume_total REAL,
        volume_24h REAL,
        liquidity REAL,
        end_date TEXT,
        matched_company TEXT,
        tags TEXT,
        active INTEGER DEFAULT 1
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_poly_market_id ON polymarket_snapshots(market_id);",
    "CREATE INDEX IF NOT EXISTS idx_poly_ts ON polymarket_snapshots(snapshot_ts);",
    "CREATE INDEX IF NOT EXISTS idx_poly_company ON polymarket_snapshots(matched_company);",
    # Dedupe index: only insert when yes/no actually changed
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_poly_dedup ON polymarket_snapshots(market_id, yes_price, no_price);",
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
