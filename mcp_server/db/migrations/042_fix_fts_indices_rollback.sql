-- Rollback Migration 042: Revert FTS Index fixes
--
-- Restores original 'english' L2 index and drops episode FTS index.

-- Revert L2 index to original 'english' config
DROP INDEX IF EXISTS idx_l2_fts;
CREATE INDEX idx_l2_fts ON l2_insights USING gin(to_tsvector('english', content));

-- Drop episode FTS index (didn't exist before)
DROP INDEX IF EXISTS idx_episode_fts;
