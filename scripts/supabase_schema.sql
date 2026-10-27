-- ==========================================================
-- WelFamily Supabase / PostgreSQL Free Tier Schema
-- Supabase provides 500MB free PostgreSQL database
-- ==========================================================

-- 1. Policies Table
CREATE TABLE IF NOT EXISTS welfare_policies (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    origin TEXT NOT NULL CHECK (origin IN ('CENTRAL', 'LOCAL')),
    region_code TEXT NOT NULL,
    region_name TEXT NOT NULL,
    managing_org TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('CASH', 'VOUCHER', 'DISCOUNT', 'CARE', 'HOUSING')),
    category_name TEXT NOT NULL,
    amount_value BIGINT NOT NULL DEFAULT 0,
    amount_text TEXT NOT NULL,
    target_min_age INT DEFAULT 0,
    target_max_age INT DEFAULT 120,
    income_limit_ratio INT DEFAULT 999,
    required_tags TEXT[] DEFAULT '{}',
    certainty_score INT DEFAULT 90,
    is_budget_limited BOOLEAN DEFAULT FALSE,
    is_urgent BOOLEAN DEFAULT FALSE,
    dday_text TEXT,
    summary_3lines JSONB NOT NULL,
    required_documents JSONB NOT NULL,
    application_url TEXT,
    contact_phone TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Household Profiles Table (Client-sync or Auth-linked)
CREATE TABLE IF NOT EXISTS household_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    region_sido TEXT NOT NULL,
    region_sigungu TEXT NOT NULL,
    income_bracket TEXT NOT NULL,
    housing_type TEXT NOT NULL,
    members JSONB NOT NULL,
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Sync Audit Log
CREATE TABLE IF NOT EXISTS sync_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    total_policies INT NOT NULL,
    central_count INT NOT NULL,
    local_count INT NOT NULL,
    status TEXT NOT NULL
);

-- Index for high-performance spatial & demographic matching
CREATE INDEX IF NOT EXISTS idx_policies_region ON welfare_policies(region_code);
CREATE INDEX IF NOT EXISTS idx_policies_category ON welfare_policies(category);
