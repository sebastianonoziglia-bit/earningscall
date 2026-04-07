-- =============================================================================
-- Replit Revival — Supabase Initial Schema
-- =============================================================================
-- Mirrors the current data sources:
--   • Google Sheets workbook (financial / segments / transcripts / stocks)
--   • SQLite earningscall_intelligence.db (transcripts, signals, KPIs)
--   • Polymarket API cache
--
-- Apply with:  supabase db push
-- =============================================================================

-- ── Extensions ───────────────────────────────────────────────────────────────
create extension if not exists "pgcrypto";   -- for gen_random_uuid()

-- =============================================================================
-- DIMENSION: companies
-- =============================================================================
create table if not exists public.companies (
    company_key      text primary key,           -- canonical lowercase key
    display_name     text not null,
    ticker           text,
    sector           text,
    country          text,
    created_at       timestamptz default now()
);

create index if not exists idx_companies_ticker on public.companies (ticker);

-- =============================================================================
-- FACT: financial metrics (yearly) — Company_metrics_earnings_values
-- =============================================================================
create table if not exists public.financial_metrics_yearly (
    company             text not null,
    year                integer not null,
    revenue             numeric,
    cost_of_revenue     numeric,
    operating_income    numeric,
    net_income          numeric,
    rd                  numeric,
    capex               numeric,
    total_assets        numeric,
    market_cap          numeric,
    cash_balance        numeric,
    debt                numeric,
    primary key (company, year)
);

create index if not exists idx_fmy_company on public.financial_metrics_yearly (company);
create index if not exists idx_fmy_year    on public.financial_metrics_yearly (year);

-- =============================================================================
-- FACT: financial metrics (quarterly) — mirrors SQLite company_metrics
-- =============================================================================
create table if not exists public.financial_metrics_quarterly (
    company             text not null,
    ticker              text,
    year                integer not null,
    quarter             text not null,
    revenue             numeric,
    cost_of_revenue     numeric,
    operating_income    numeric,
    net_income          numeric,
    capex               numeric,
    r_and_d             numeric,
    total_assets        numeric,
    market_cap          numeric,
    cash_balance        numeric,
    debt                numeric,
    employee_count      numeric,
    advertising_revenue numeric,
    primary key (company, year, quarter)
);

create index if not exists idx_fmq_company on public.financial_metrics_quarterly (company);

-- =============================================================================
-- FACT: company employees over time — Company_Employees
-- =============================================================================
create table if not exists public.company_employees (
    company        text not null,
    year           integer not null,
    employee_count bigint,
    primary key (company, year)
);

-- =============================================================================
-- FACT: yearly segments — Company_yearly_segments_values
-- =============================================================================
create table if not exists public.company_segments_yearly (
    company   text not null,
    year      integer not null,
    segment   text not null,
    revenue   numeric,
    primary key (company, year, segment)
);

create index if not exists idx_csy_company_year on public.company_segments_yearly (company, year);

-- =============================================================================
-- FACT: quarterly segments — Company_quarterly_segments_values
-- =============================================================================
create table if not exists public.company_segments_quarterly (
    company   text not null,
    year      integer not null,
    quarter   text not null,
    segment   text not null,
    revenue   numeric,
    primary key (company, year, quarter, segment)
);

create index if not exists idx_csq_company_period on public.company_segments_quarterly (company, year, quarter);

-- =============================================================================
-- TEXT: segment insights / commentary — Company_Segments_insights_text
-- =============================================================================
create table if not exists public.company_segment_insights (
    id            bigserial primary key,
    company       text not null,
    year          integer,
    quarter       text,
    segment       text,
    insight_text  text,
    source        text
);

create index if not exists idx_csi_company on public.company_segment_insights (company);

-- =============================================================================
-- TEXT: company-level insights — Company_insights_text
-- =============================================================================
create table if not exists public.company_insights (
    id           bigserial primary key,
    company      text not null,
    year         integer,
    quarter      text,
    insight_text text,
    source       text
);

create index if not exists idx_ci_company on public.company_insights (company);

-- =============================================================================
-- TEXT: auto-generated narratives — Company_Auto_Narratives
-- =============================================================================
create table if not exists public.company_auto_narratives (
    id              bigserial primary key,
    company         text not null,
    year            integer,
    quarter         text,
    narrative_type  text,
    narrative_text  text
);

-- =============================================================================
-- FACT: revenue by region — Company_revenue_by_region
-- =============================================================================
create table if not exists public.company_revenue_by_region (
    company  text not null,
    year     integer not null,
    region   text not null,
    revenue  numeric,
    primary key (company, year, region)
);

-- =============================================================================
-- FACT: subscribers — Company_subscribers_values
-- =============================================================================
create table if not exists public.company_subscribers (
    company             text not null,
    year                integer not null,
    quarter             text not null default '',
    subscribers         bigint,
    subscribers_paid    bigint,
    primary key (company, year, quarter)
);

-- =============================================================================
-- DIMENSION: speakers — Company_Speaker
-- =============================================================================
create table if not exists public.company_speakers (
    id        bigserial primary key,
    company   text not null,
    name      text not null,
    role      text,
    title     text,
    unique (company, name)
);

-- =============================================================================
-- SNAPSHOT: minute & dollar earned — Company_minute&dollar_earned
-- =============================================================================
create table if not exists public.company_minute_dollar_earned (
    platform               text primary key,
    total_minutes_watched  numeric,
    revenue_b              numeric,
    dollar_per_minute      numeric,
    notes                  text
);

-- =============================================================================
-- FACT: company advertising revenue — Company_advertising_revenue
-- =============================================================================
create table if not exists public.company_advertising_revenue (
    company       text not null,
    year          integer not null,
    ad_revenue    numeric,
    extra_data    jsonb,                -- catch-all for varying ad-channel columns
    primary key (company, year)
);

-- =============================================================================
-- FACT: global advertising aggregates — Global_Adv_Aggregates
-- =============================================================================
create table if not exists public.global_adv_aggregates (
    metric_type text not null,
    year        integer not null,
    value       numeric,                -- in $M
    primary key (metric_type, year)
);

-- =============================================================================
-- FACT: country advertising data — Country_Advertising_Data_FullVi
-- =============================================================================
create table if not exists public.country_advertising_data (
    country    text not null,
    year       integer not null,
    metric     text not null,
    value      numeric,
    primary key (country, year, metric)
);

-- =============================================================================
-- FACT: country totals vs GDP — Country_Totals_vs_GDP
-- =============================================================================
create table if not exists public.country_totals_vs_gdp (
    country     text not null,
    year        integer not null,
    ad_total    numeric,
    gdp         numeric,
    ad_pct_gdp  numeric,
    primary key (country, year)
);

-- =============================================================================
-- FACT: GroupM global advertising — Global Advertising (GroupM)
-- =============================================================================
create table if not exists public.global_advertising_groupm (
    year       integer not null,
    category   text not null,
    value      numeric,
    primary key (year, category)
);

-- =============================================================================
-- FACT: Nasdaq composite (FRED) — Nasdaq Composite Est. (FRED)
-- =============================================================================
create table if not exists public.nasdaq_composite_fred (
    date   date primary key,
    value  numeric
);

-- =============================================================================
-- FACT: USD inflation — USD Inflation
-- =============================================================================
create table if not exists public.usd_inflation (
    year         integer primary key,
    inflation    numeric,
    cumulative   numeric
);

-- =============================================================================
-- TEXT: full transcripts — Transcripts sheet + SQLite transcripts
-- =============================================================================
create table if not exists public.transcripts (
    id              bigserial primary key,
    company         text not null,
    year            integer not null,
    quarter         text not null,
    full_text       text,
    word_count      integer,
    indexed_date    timestamptz default now(),
    unique (company, year, quarter)
);

create index if not exists idx_transcripts_company_year on public.transcripts (company, year);

-- =============================================================================
-- FACT: extracted topics from transcripts — SQLite transcript_topics
-- =============================================================================
create table if not exists public.transcript_topics (
    id               bigserial primary key,
    transcript_id    bigint references public.transcripts (id) on delete cascade,
    topic            text not null,
    keyword          text,
    mention_count    integer,
    context_snippet  text,
    speaker          text
);

create index if not exists idx_tt_topic on public.transcript_topics (topic);

-- =============================================================================
-- FACT: extracted KPIs from transcripts — SQLite transcript_kpis
-- =============================================================================
create table if not exists public.transcript_kpis (
    id                bigserial primary key,
    transcript_id     bigint references public.transcripts (id) on delete cascade,
    kpi_type          text not null,
    value_text        text,
    value_numeric     numeric,
    unit              text,
    context_sentence  text,
    confidence        numeric
);

create index if not exists idx_tk_type on public.transcript_kpis (kpi_type);

-- =============================================================================
-- FACT: transcript highlights — SQLite transcript_highlights
-- =============================================================================
create table if not exists public.transcript_highlights (
    id              bigserial primary key,
    transcript_id   bigint references public.transcripts (id) on delete cascade,
    highlight_type  text,
    speaker         text,
    text            text,
    relevance_score numeric
);

-- =============================================================================
-- FACT: forward-looking signals — SQLite forward_signals (most-used table)
-- =============================================================================
create table if not exists public.forward_signals (
    id                  bigserial primary key,
    company             text not null,
    year                integer not null,
    quarter             text not null,
    quote               text not null,
    speaker             text,
    role                text,
    score               numeric,
    category            text,
    has_number          boolean default false,
    has_year_ref        boolean default false,
    future_tense_score  numeric default 0,
    topics              jsonb,                       -- list of topic tags
    created_at          timestamptz default now()
);

create index if not exists idx_fs_company_year on public.forward_signals (company, year, quarter);
create index if not exists idx_fs_score        on public.forward_signals (score desc);
create index if not exists idx_fs_category     on public.forward_signals (category);

-- =============================================================================
-- TEXT: iconic CEO/CFO quotes — Overview_Iconic_Quotes
-- =============================================================================
create table if not exists public.overview_iconic_quotes (
    id           bigserial primary key,
    year         integer not null,
    quarter      text not null,
    company      text not null,
    speaker      text,
    role_bucket  text,                -- CEO / CFO / OTHER
    quote        text not null,
    category     text,                -- signal category
    topics       jsonb,               -- list of topic tags (added later)
    score        numeric,
    source       text default 'sheet'
);

create index if not exists idx_oiq_year_q   on public.overview_iconic_quotes (year, quarter);
create index if not exists idx_oiq_company  on public.overview_iconic_quotes (company);

-- =============================================================================
-- TEXT: overview auto insights — Overview_Auto_Insights
-- =============================================================================
create table if not exists public.overview_auto_insights (
    id            bigserial primary key,
    year          integer,
    quarter       text,
    insight_type  text,
    insight_text  text
);

-- =============================================================================
-- DIMENSION: topics master — Topics_Master
-- =============================================================================
create table if not exists public.topics_master (
    topic       text primary key,
    description text,
    keywords    jsonb
);

-- =============================================================================
-- FACT: institutional holders — Holders
-- =============================================================================
create table if not exists public.holders (
    id            bigserial primary key,
    date_fetched  timestamptz,
    company       text not null,
    ticker        text,
    holder_name   text not null,
    shares        numeric,
    value_usd     numeric,
    pct_out       numeric,
    holder_type   text,
    unique (company, ticker, holder_name, date_fetched)
);

create index if not exists idx_holders_company on public.holders (company);

-- =============================================================================
-- FACT: yearly stock prices — Stocks & Crypto
-- =============================================================================
create table if not exists public.stock_yearly (
    date              date not null,
    asset             text not null,
    tag               text not null default '',
    price             numeric,
    open              numeric,
    high              numeric,
    low               numeric,
    volume            numeric,
    change_pct        numeric,
    market_cap        numeric,
    currency          text,
    outstanding_shares numeric,
    primary key (date, asset, tag)
);

create index if not exists idx_sy_asset on public.stock_yearly (asset);

-- =============================================================================
-- FACT: daily stock prices — Daily
-- =============================================================================
create table if not exists public.stock_daily (
    date              date not null,
    asset             text not null,
    tag               text not null default '',
    price             numeric,
    open              numeric,
    high              numeric,
    low               numeric,
    volume            numeric,
    change_pct        numeric,
    market_cap        numeric,
    currency          text,
    outstanding_shares numeric,
    primary key (date, asset, tag)
);

create index if not exists idx_sd_asset on public.stock_daily (asset);
create index if not exists idx_sd_tag   on public.stock_daily (tag);

-- =============================================================================
-- FACT: minute-level / intraday stock prices — Minute
-- =============================================================================
create table if not exists public.stock_minute (
    ts                timestamptz not null,
    asset             text not null,
    tag               text not null default '',
    price             numeric,
    open              numeric,
    high              numeric,
    low               numeric,
    volume            numeric,
    change_pct        numeric,
    market_cap        numeric,
    currency          text,
    outstanding_shares numeric,
    primary key (ts, asset, tag)
);

create index if not exists idx_sm_asset on public.stock_minute (asset);

-- =============================================================================
-- CACHE: Polymarket markets — fetched from Gamma API
-- =============================================================================
create table if not exists public.polymarket_cache (
    market_id      text primary key,
    slug           text,
    question       text,
    yes_price      numeric,
    no_price       numeric,
    volume_total   numeric,
    volume_24h     numeric,
    liquidity      numeric,
    end_date       timestamptz,
    active         boolean,
    url            text,
    tags           jsonb,
    fetched_at     timestamptz default now()
);

create index if not exists idx_pm_active on public.polymarket_cache (active);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================
-- Strategy: enable RLS on every table. Allow `authenticated` (any logged-in
-- Supabase user) to read everything. Writes are restricted to `service_role`
-- (i.e. the sb_secret_* key used by Apps Script + the backfill script).
--
-- This is multi-user-safe from day one but doesn't get in the way while
-- there's only one user.
-- =============================================================================

do $$
declare
    tbl text;
    public_tables text[] := array[
        'companies',
        'financial_metrics_yearly',
        'financial_metrics_quarterly',
        'company_employees',
        'company_segments_yearly',
        'company_segments_quarterly',
        'company_segment_insights',
        'company_insights',
        'company_auto_narratives',
        'company_revenue_by_region',
        'company_subscribers',
        'company_speakers',
        'company_minute_dollar_earned',
        'company_advertising_revenue',
        'global_adv_aggregates',
        'country_advertising_data',
        'country_totals_vs_gdp',
        'global_advertising_groupm',
        'nasdaq_composite_fred',
        'usd_inflation',
        'transcripts',
        'transcript_topics',
        'transcript_kpis',
        'transcript_highlights',
        'forward_signals',
        'overview_iconic_quotes',
        'overview_auto_insights',
        'topics_master',
        'holders',
        'stock_yearly',
        'stock_daily',
        'stock_minute',
        'polymarket_cache'
    ];
begin
    foreach tbl in array public_tables loop
        execute format('alter table public.%I enable row level security', tbl);

        -- Permissive read for any authenticated user
        execute format(
            'drop policy if exists "read_authenticated" on public.%I', tbl
        );
        execute format(
            'create policy "read_authenticated" on public.%I for select to authenticated using (true)',
            tbl
        );

        -- Anonymous reads also allowed (because the publishable key uses anon)
        -- Remove this block if you want to require login.
        execute format(
            'drop policy if exists "read_anon" on public.%I', tbl
        );
        execute format(
            'create policy "read_anon" on public.%I for select to anon using (true)',
            tbl
        );
    end loop;
end $$;
