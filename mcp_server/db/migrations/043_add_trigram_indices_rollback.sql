-- Rollback Migration 043: Remove pg_trgm GIN Indices
DROP INDEX IF EXISTS idx_l2_trgm;
DROP INDEX IF EXISTS idx_episode_trgm;
