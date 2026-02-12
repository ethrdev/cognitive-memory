-- Migration 043: Add pg_trgm GIN Indices for German Compound Word Search
--
-- Epic 8, Story B2: Trigram-based fuzzy matching as FTS fallback.
-- Prerequisite: pg_trgm extension (B1, applied 2026-02-12 via Neon Console).
--
-- Problem: PostgreSQL FTS with 'simple' tokenizer cannot split German
-- compound words like "Kontexttrennung" into "Kontext" + "Trennung".
-- FTS keyword search returns 0 results for these terms.
--
-- Solution: GIN indices using gin_trgm_ops enable pg_trgm similarity()
-- queries. keyword_search falls back to trigram when FTS yields 0 results.
--
-- Source: System Audit 2026-02-12, BMAD Party Mode Development Plan

-- L2 Insights: Trigram index on content column
CREATE INDEX IF NOT EXISTS idx_l2_trgm
    ON l2_insights USING gin(content gin_trgm_ops);

-- Episode Memory: Trigram index on combined query + reflection
-- Matches the expression used in episode_keyword_search()
CREATE INDEX IF NOT EXISTS idx_episode_trgm
    ON episode_memory USING gin((query || ' ' || reflection) gin_trgm_ops);
