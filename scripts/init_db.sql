-- DDL Schema Script for Supabase PostgreSQL Database

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. INSTRUMENTS TABLE
CREATE TABLE IF NOT EXISTS public.instruments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) UNIQUE NOT NULL,
    asset_class VARCHAR(20) NOT NULL,
    base_currency VARCHAR(10),
    quote_currency VARCHAR(10),
    pip_size NUMERIC(10,5) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. CANDLES TABLE
CREATE TABLE IF NOT EXISTS public.candles (
    id BIGSERIAL PRIMARY KEY,
    instrument_id UUID REFERENCES public.instruments(id),
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open NUMERIC(12,5) NOT NULL,
    high NUMERIC(12,5) NOT NULL,
    low NUMERIC(12,5) NOT NULL,
    close NUMERIC(12,5) NOT NULL,
    volume NUMERIC(15,2),
    CONSTRAINT unique_candle UNIQUE (instrument_id, timeframe, timestamp)
);

-- 3. OPPORTUNITIES TABLE
CREATE TABLE IF NOT EXISTS public.opportunities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    signal_hash VARCHAR(64) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    entry_price NUMERIC(12,5) NOT NULL,
    stop_loss NUMERIC(12,5) NOT NULL,
    take_profit_1 NUMERIC(12,5) NOT NULL,
    take_profit_2 NUMERIC(12,5) NOT NULL,
    risk_reward NUMERIC(5,2) NOT NULL,
    ml_probability NUMERIC(4,3) NOT NULL,
    opportunity_score NUMERIC(5,2) NOT NULL,
    technical_score NUMERIC(5,2),
    status VARCHAR(20) DEFAULT 'ACTIVE',
    llm_reasoning TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- 4. TRADE OUTCOMES TABLE (Paper-Trading Tracking)
CREATE TABLE IF NOT EXISTS public.trade_outcomes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    opportunity_id UUID REFERENCES public.opportunities(id),
    actual_entry_time TIMESTAMPTZ,
    actual_exit_time TIMESTAMPTZ,
    exit_price NUMERIC(12,5),
    outcome VARCHAR(15),
    realized_r_multiple NUMERIC(5,2),
    max_favorable_excursion NUMERIC(5,2),
    max_adverse_excursion NUMERIC(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. PROVIDER USAGE AUDIT TABLE
CREATE TABLE IF NOT EXISTS public.provider_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider_name VARCHAR(30) NOT NULL,
    model_name VARCHAR(50),
    prompt_tokens INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    estimated_cost_usd NUMERIC(8,6) DEFAULT 0,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
