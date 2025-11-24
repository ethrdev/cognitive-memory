-- Migration 001: Initial Schema for Cognitive Memory System v1.0.0
-- 
--
-- Tables: l0_raw, l2_insights, working_memory, episode_memory, stale_memory, ground_truth
-- Indizes: IVFFlat (commented - needs training data), GIN Full-Text, Session, LRU

-- Enable pgvector extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- TABLE 1: l0_raw - Raw Dialogtranskripte
-- ============================================================================
-- Note: session_id is VARCHAR(255) for flexibility (user-defined session IDs)
-- Examples: "session-philosophy-2025-11-12", "conv-abc-123", or UUIDs if desired
CREATE TABLE l0_raw (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    speaker VARCHAR(50) NOT NULL,  -- 'user' | 'assistant'
    content TEXT NOT NULL,
    metadata JSONB
);

-- Index für Session-Queries (schnelle Abfrage nach Session + Zeitbereich)
CREATE INDEX idx_l0_session ON l0_raw(session_id, timestamp);

-- ============================================================================
-- TABLE 2: l2_insights - Komprimierte semantische Einheiten
-- ============================================================================
CREATE TABLE l2_insights (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,  -- OpenAI text-embedding-3-small
    created_at TIMESTAMPTZ DEFAULT NOW(),
    source_ids INTEGER[] NOT NULL,    -- L0 Raw IDs
    metadata JSONB
);

-- ⚠️ IVFFlat Index - NICHT sofort bauen (benötigt ≥100 Vektoren für Training)
-- Wird gebaut in 
-- CREATE INDEX CONCURRENTLY idx_l2_embedding
--   ON l2_insights USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Full-Text Search Index (kann sofort gebaut werden)
CREATE INDEX idx_l2_fts ON l2_insights USING gin(to_tsvector('english', content));

-- ============================================================================
-- TABLE 3: working_memory - Session-Kontext (LRU Eviction)
-- ============================================================================
CREATE TABLE working_memory (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    importance FLOAT DEFAULT 0.5,      -- 0.0-1.0, >0.8 = Critical Items
    last_accessed TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- LRU Index (schnelle Identifikation ältester Items bei Eviction)
CREATE INDEX idx_wm_lru ON working_memory(last_accessed ASC);

-- ============================================================================
-- TABLE 4: episode_memory - Verbalisierte Reflexionen (Verbal RL)
-- ============================================================================
CREATE TABLE episode_memory (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    reward FLOAT NOT NULL,             -- -1.0 bis +1.0 (Haiku Evaluation)
    reflection TEXT NOT NULL,          -- Verbalisierte Lektion
    created_at TIMESTAMPTZ DEFAULT NOW(),
    embedding vector(1536) NOT NULL   -- Query Embedding
);

-- ⚠️ IVFFlat Index - NICHT sofort bauen (benötigt ≥100 Vektoren für Training)
-- Wird gebaut in 
-- CREATE INDEX CONCURRENTLY idx_episode_embedding
--   ON episode_memory USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- TABLE 5: stale_memory - Archiv kritischer Items
-- ============================================================================
CREATE TABLE stale_memory (
    id SERIAL PRIMARY KEY,
    original_content TEXT NOT NULL,
    archived_at TIMESTAMPTZ DEFAULT NOW(),
    importance FLOAT NOT NULL,
    reason VARCHAR(100) NOT NULL       -- 'LRU_EVICTION' | 'MANUAL_ARCHIVE'
);

-- ============================================================================
-- TABLE 6: ground_truth - Dual Judge Scores für IRR Validation
-- ============================================================================
CREATE TABLE ground_truth (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    expected_docs INTEGER[] NOT NULL,  -- L2 Insight IDs
    judge1_score FLOAT,                -- GPT-4o Score
    judge2_score FLOAT,                -- Haiku Score
    judge1_model VARCHAR(100),         -- 'gpt-4o'
    judge2_model VARCHAR(100),         -- 'claude-3-5-haiku-20241022'
    kappa FLOAT,                       -- Cohen's Kappa
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================

-- Verify all tables exist (should return 6 rows)
-- SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN
--   ('l0_raw', 'l2_insights', 'working_memory', 'episode_memory', 'stale_memory', 'ground_truth');

-- Verify all indizes exist (should return 3 rows - IVFFlat not built yet)
-- SELECT indexname FROM pg_indexes WHERE schemaname='public' AND
--   indexname IN ('idx_l0_session', 'idx_l2_fts', 'idx_wm_lru');

-- Verify pgvector extension (should return 1 row)
-- SELECT * FROM pg_extension WHERE extname='vector';
