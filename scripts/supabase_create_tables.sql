-- Run this ONCE in Supabase Dashboard → SQL Editor → New Query → Run
-- Creates all intelligence tables that are currently SQLite-only

-- Transcripts (352 rows)
CREATE TABLE IF NOT EXISTS transcripts (
    id SERIAL PRIMARY KEY,
    company TEXT NOT NULL,
    year INTEGER NOT NULL,
    quarter TEXT NOT NULL,
    full_text TEXT,
    word_count INTEGER,
    indexed_date TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company, year, quarter)
);

-- Transcript topics (126K rows)
CREATE TABLE IF NOT EXISTS transcript_topics (
    id SERIAL PRIMARY KEY,
    transcript_id INTEGER REFERENCES transcripts(id),
    topic TEXT NOT NULL,
    keyword TEXT,
    mention_count INTEGER,
    context_snippet TEXT,
    speaker TEXT
);
CREATE INDEX IF NOT EXISTS idx_tt_transcript ON transcript_topics(transcript_id);
CREATE INDEX IF NOT EXISTS idx_tt_topic ON transcript_topics(topic);

-- Transcript KPIs (4K rows)
CREATE TABLE IF NOT EXISTS transcript_kpis (
    id SERIAL PRIMARY KEY,
    transcript_id INTEGER,
    kpi_type TEXT NOT NULL,
    value_text TEXT,
    value_numeric REAL,
    unit TEXT,
    context_sentence TEXT,
    confidence REAL
);

-- Transcript highlights (1K rows)
CREATE TABLE IF NOT EXISTS transcript_highlights (
    id SERIAL PRIMARY KEY,
    transcript_id INTEGER,
    highlight_type TEXT,
    speaker TEXT,
    text TEXT,
    relevance_score REAL
);

-- Forward signals (3.5K rows)
CREATE TABLE IF NOT EXISTS forward_signals (
    id SERIAL PRIMARY KEY,
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
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fs_company ON forward_signals(company, year);
CREATE INDEX IF NOT EXISTS idx_fs_score ON forward_signals(score DESC);

-- Polymarket snapshots (20K+ rows, grows over time)
CREATE TABLE IF NOT EXISTS polymarket_snapshots (
    id SERIAL PRIMARY KEY,
    market_id TEXT NOT NULL,
    snapshot_ts TIMESTAMPTZ DEFAULT NOW(),
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
    active BOOLEAN DEFAULT TRUE,
    UNIQUE(market_id, yes_price, no_price)
);
CREATE INDEX IF NOT EXISTS idx_poly_company ON polymarket_snapshots(matched_company);
CREATE INDEX IF NOT EXISTS idx_poly_ts ON polymarket_snapshots(snapshot_ts);

-- Oracle predictions
CREATE TABLE IF NOT EXISTS oracle_predictions (
    id SERIAL PRIMARY KEY,
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

-- Enable read access for anon key (RLS)
ALTER TABLE transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcript_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcript_kpis ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcript_highlights ENABLE ROW LEVEL SECURITY;
ALTER TABLE forward_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE polymarket_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE oracle_predictions ENABLE ROW LEVEL SECURITY;

-- Allow anon read on all (drop first to avoid duplicates)
DO $$ BEGIN
  DROP POLICY IF EXISTS "anon_read" ON transcripts;
  DROP POLICY IF EXISTS "anon_read" ON transcript_topics;
  DROP POLICY IF EXISTS "anon_read" ON transcript_kpis;
  DROP POLICY IF EXISTS "anon_read" ON transcript_highlights;
  DROP POLICY IF EXISTS "anon_read" ON forward_signals;
  DROP POLICY IF EXISTS "anon_read" ON polymarket_snapshots;
  DROP POLICY IF EXISTS "anon_read" ON oracle_predictions;
END $$;

CREATE POLICY "anon_read" ON transcripts FOR SELECT USING (true);
CREATE POLICY "anon_read" ON transcript_topics FOR SELECT USING (true);
CREATE POLICY "anon_read" ON transcript_kpis FOR SELECT USING (true);
CREATE POLICY "anon_read" ON transcript_highlights FOR SELECT USING (true);
CREATE POLICY "anon_read" ON forward_signals FOR SELECT USING (true);
CREATE POLICY "anon_read" ON polymarket_snapshots FOR SELECT USING (true);
CREATE POLICY "anon_read" ON oracle_predictions FOR SELECT USING (true);
