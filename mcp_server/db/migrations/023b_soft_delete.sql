-- Migration 023b: Add soft-delete fields to l2_insights
-- Story 26.3: DELETE Operation

-- UP
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'is_deleted'
    ) THEN
        ALTER TABLE l2_insights ADD COLUMN is_deleted BOOL DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'deleted_at'
    ) THEN
        ALTER TABLE l2_insights ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'deleted_by'
    ) THEN
        ALTER TABLE l2_insights ADD COLUMN deleted_by VARCHAR(10);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'deleted_reason'
    ) THEN
        ALTER TABLE l2_insights ADD COLUMN deleted_reason TEXT;
    END IF;
END $$;

-- Performance Index: Only query non-deleted insights
CREATE INDEX IF NOT EXISTS idx_l2_insights_not_deleted
    ON l2_insights(id) WHERE is_deleted = FALSE;

-- DOWN
DROP INDEX IF EXISTS idx_l2_insights_not_deleted;
ALTER TABLE l2_insights DROP COLUMN IF EXISTS is_deleted;
ALTER TABLE l2_insights DROP COLUMN IF EXISTS deleted_at;
ALTER TABLE l2_insights DROP COLUMN IF EXISTS deleted_by;
ALTER TABLE l2_insights DROP COLUMN IF EXISTS deleted_reason;
