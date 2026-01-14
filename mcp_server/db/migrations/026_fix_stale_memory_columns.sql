-- Migration: Fix stale_memory column names
-- Date: 2026-01-14
-- Issue: REG-TO-DO-002 - stale_memory table schema mismatch
--
-- Problem: Code uses 'content' but schema has 'original_content'.
-- The 'reason' column already exists (same as 'archive_reason').
-- Note: Schema does NOT have 'created_at' - only 'archived_at'.
--
-- Strategy: Add new 'content' column as alias for 'original_content'.

BEGIN;

-- Add new column with code-expected name
ALTER TABLE stale_memory ADD COLUMN IF NOT EXISTS content TEXT;

-- Copy data from old column to new column
UPDATE stale_memory
SET content = original_content
WHERE content IS NULL;

-- Make new column NOT NULL after data is copied
ALTER TABLE stale_memory ALTER COLUMN content SET NOT NULL;

COMMIT;

-- Verification query
-- SELECT id, content, original_content, archived_at, importance, reason FROM stale_memory LIMIT 5;
