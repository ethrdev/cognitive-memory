-- Migration 042: Fix FTS Index Language Mismatch + Add Episode FTS Index
--
-- Fix N3 (2026-02-11): Migration 001 created L2 FTS index with 'english',
--   but runtime code (keyword_search, episode_keyword_search) uses 'simple'.
--   PostgreSQL requires exact tsvector config match to use a GIN index.
--   Result: idx_l2_fts was NEVER used — sequential scan on every keyword query.
--
-- Fix N4 (2026-02-11): No FTS index existed on episode_memory at all.
--   episode_keyword_search() computes to_tsvector('simple', query || ' ' || reflection)
--   per row on every query — sequential scan with expression evaluation.
--
-- Source: BMAD Party Mode Architecture Analysis (Winston, Murat, Mary, I/O)
-- See: bmad-docs/hybrid-search-fix-plan.md

-- Fix N3: Drop mismatched L2 index, recreate with 'simple'
DROP INDEX IF EXISTS idx_l2_fts;
CREATE INDEX idx_l2_fts ON l2_insights USING gin(to_tsvector('simple', content));

-- Fix N4: Create episode FTS index (query + reflection combined, matching runtime)
CREATE INDEX idx_episode_fts ON episode_memory
  USING gin(to_tsvector('simple', query || ' ' || reflection));
