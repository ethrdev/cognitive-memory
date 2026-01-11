-- Migration 024b: Add version_id to l2_insight_history
-- Purpose: Support Story 26.7 (Revision History) chronological queries
-- Dependencies: Migration 024 (l2_insight_history table)
-- Story: 26.7 - Revision History (Stretch Goal)
-- Date: 2026-01-10
-- Issue: Resolves schema conflict between Story 26.2 (audit trail) and Story 26.7 (version history)
--
-- ============================================================================
-- DEPLOYMENT INSTRUCTIONS (NEON DB)
-- ============================================================================
--
-- This migration runs on **Neon DB** (managed PostgreSQL), not local PostgreSQL.
--
-- Option 1: Neon Console (Recommended for one-off migrations)
--   1. Open Neon Console: https://console.neon.tech/
--   2. Navigate to your cognitive-memory project
--   3. Click "SQL Editor" in left sidebar
--   4. Copy entire contents of this file
--   5. Paste into SQL Editor
--   6. Click "Run" to execute
--
-- Option 2: psql with Neon connection string
--   NEON_DB_URL="postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require"
--   psql "$NEON_DB_URL" -f 024b_add_version_id_to_l2_insight_history.sql
--
-- Option 3: Neon CLI
--   neon db execute --project-id=xxx --file=024b_add_version_id_to_l2_insight_history.sql
--
-- Option 4: Via cognitive-memory application (if migration runner exists)
--   Check if cognitive-memory has a migration runner/deploy script
--
-- Verification after deployment:
--   SELECT column_name, data_type
--   FROM information_schema.columns
--   WHERE table_name = 'l2_insight_history' AND column_name = 'version_id';
--
-- ============================================================================
-- BACKGROUND
-- ============================================================================
--
-- Migration 024 (Story 26.2) created l2_insight_history as an AUDIT TRAIL:
--   - action-based (UPDATE/DELETE)
--   - Field naming: actor, reason, old_content, new_content
--   - Purpose: Compliance, debugging, rollback
--
-- Story 26.7 (Revision History) expects VERSION HISTORY:
--   - version_id-based (chronological)
--   - Field naming: changed_by, change_reason, previous_content
--   - Purpose: User-facing "Archäologie des Selbst"
--
-- This migration extends the existing table to support BOTH use cases:
--   - Preserves audit trail (action, actor, old/new_content)
--   - Adds version_id for chronological queries
--   - Backward compatible with existing data
--
-- ============================================================================

-- UP MIGRATION
-- ============================================================================

-- Step 1: Add version_id column (nullable for existing rows)
ALTER TABLE l2_insight_history
  ADD COLUMN IF NOT EXISTS version_id INT;

-- Step 2: Create unique constraint per insight (version_id is per-insight sequence)
-- Note: Existing rows will have NULL version_id, constraint is validated only for non-NULL
ALTER TABLE l2_insight_history
  ADD CONSTRAINT IF NOT EXISTS unique_insight_version
  UNIQUE (insight_id, version_id);

-- Step 3: Add index for chronological queries (oldest first - FR31)
-- This optimizes: SELECT * FROM l2_insight_history WHERE insight_id = $1 ORDER BY version_id ASC
CREATE INDEX IF NOT EXISTS idx_l2_insight_history_version
  ON l2_insight_history(insight_id, version_id ASC);

-- Step 4: Populate version_id for existing history entries
-- This creates a sequence per insight: 1, 2, 3, ...
WITH numbered_history AS (
  SELECT
    id,
    insight_id,
    ROW_NUMBER() OVER (
      PARTITION BY insight_id
      ORDER BY created_at ASC
    ) as row_num
  FROM l2_insight_history
  WHERE version_id IS NULL
)
UPDATE l2_insight_history h
SET version_id = nh.row_num
FROM numbered_history nh
WHERE h.id = nh.id;

-- Step 5: Make version_id NOT NULL for new entries (after backfill)
-- Note: This uses a CHECK constraint instead of column constraint to avoid table rewrite
ALTER TABLE l2_insight_history
  ADD CONSTRAINT IF NOT EXISTS version_id_not_null
  CHECK (
    version_id IS NOT NULL
    OR created_at < '2026-01-10'::timestamp  -- Grandfather clause for existing data
  );

-- Step 6: Add comment for documentation
COMMENT ON TABLE l2_insight_history IS
'Audit trail and version history for L2 insights. '
'Supports both compliance (action-based) and user-facing (version-based) queries. '
'Created by Migration 024 (Story 26.2), extended by Migration 024b (Story 26.7).';

COMMENT ON COLUMN l2_insight_history.version_id IS
'Chronological version number per insight (1-based). '
'Monotonically increasing per insight. '
'Used by Story 26.7 (get_insight_history) for "Archäologie des Selbst".';

COMMENT ON COLUMN l2_insight_history.action IS
'Audit trail action type: UPDATE or DELETE. '
'Used by Stories 26.2 (update_insight) and 26.3 (delete_insight). '
'Distinct from version_id - same action can have multiple versions.';

COMMENT ON INDEX idx_l2_insight_history_version IS
'Optimizes chronological queries (FR31): ORDER BY version_id ASC. '
'Composite index on (insight_id, version_id) for efficient history retrieval.';

-- Step 7: Create trigger to auto-increment version_id for new entries
-- This ensures version_id is always populated for new history entries
CREATE OR REPLACE FUNCTION l2_insight_history_increment_version()
RETURNS TRIGGER AS $$
DECLARE
  next_version INT;
BEGIN
  -- Only set version_id if not already provided (for backfill compatibility)
  IF NEW.version_id IS NULL THEN
    SELECT COALESCE(MAX(version_id), 0) + 1
    INTO next_version
    FROM l2_insight_history
    WHERE insight_id = NEW.insight_id;

    NEW.version_id := next_version;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_l2_insight_history_version
  BEFORE INSERT ON l2_insight_history
  FOR EACH ROW
  EXECUTE FUNCTION l2_insight_history_increment_version();

-- ============================================================================
-- VALIDATION QUERIES (NEON DB SQL Editor)
-- ============================================================================
-- Run these after migration in Neon SQL Editor to verify correctness:

-- 1. Check version_id column exists
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'l2_insight_history' AND column_name = 'version_id';

-- 2. Verify version_id sequence is correct (no gaps per insight)
-- SELECT insight_id, version_id, created_at
-- FROM l2_insight_history
-- WHERE insight_id = 42  -- Replace with actual insight_id
-- ORDER BY version_id ASC;

-- 3. Verify trigger exists
-- SELECT trigger_name, event_manipulation, action_statement
-- FROM information_schema.triggers
-- WHERE trigger_name = 'trigger_l2_insight_history_version';

-- 4. Verify no NULL version_id for new entries (after migration date)
-- SELECT COUNT(*)
-- FROM l2_insight_history
-- WHERE version_id IS NULL AND created_at >= '2026-01-10';

-- 5. Verify unique constraint works
-- SELECT COUNT(*) as duplicate_count
-- FROM (
--   SELECT insight_id, version_id, COUNT(*)
--   FROM l2_insight_history
--   GROUP BY insight_id, version_id
--   HAVING COUNT(*) > 1
-- ) duplicates;

-- 6. Test index usage (should use Index Scan)
-- EXPLAIN ANALYZE
-- SELECT * FROM l2_insight_history
-- WHERE insight_id = 42
-- ORDER BY version_id ASC;

-- ============================================================================

-- DOWN MIGRATION
-- ============================================================================

-- Drop trigger first
DROP TRIGGER IF EXISTS trigger_l2_insight_history_version ON l2_insight_history;

-- Drop function
DROP FUNCTION IF EXISTS l2_insight_history_increment_version();

-- Drop check constraint
ALTER TABLE l2_insight_history
  DROP CONSTRAINT IF EXISTS version_id_not_null;

-- Drop unique constraint
ALTER TABLE l2_insight_history
  DROP CONSTRAINT IF EXISTS unique_insight_version;

-- Drop index
DROP INDEX IF EXISTS idx_l2_insight_history_version;

-- Drop column (this will lose version information!)
ALTER TABLE l2_insight_history
  DROP COLUMN IF EXISTS version_id;

-- ============================================================================
-- ROLLBACK STRATEGY
-- ============================================================================
-- If rollback is needed after data has been written:
--
-- 1. Data is preserved (version_id column is dropped, but base data remains)
-- 2. Audit trail functionality (Stories 26.2, 26.3) continues to work
-- 3. Story 26.7 (get_insight_history) will need to use created_at instead
--
-- Alternative: Keep column but drop trigger/constraints if re-migrating:
--   - Keep version_id column for existing data
--   - Re-run UP migration steps 1-7 to fix constraints
-- ============================================================================
