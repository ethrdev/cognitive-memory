-- Migration 044: Cleanup Audit Test Data (Epic 8, Story A4)
--
-- Removes test artifacts created during the 2026-02-12 system audit.
-- These are NOT production data — they were created to verify bug fixes.
--
-- Test artifacts:
-- 1. TEST-NODE-AUDIT graph node (Fix 1 verification, vector_id test)
-- 2. Edges referencing TEST-NODE-AUDIT
-- 3. Episode #10934 (test episode "[self] TEST-EPISODE: System-Audit 2026-02-12")
-- 4. Edges from A1 sector verification (2 test edges)
-- 5. 'arbeitet_an' edge (inconsistent German naming, should be WORKS_ON)

-- Step 1: Delete edges referencing TEST-NODE-AUDIT
DELETE FROM edges
WHERE source_id IN (SELECT id FROM nodes WHERE name = 'TEST-NODE-AUDIT')
   OR target_id IN (SELECT id FROM nodes WHERE name = 'TEST-NODE-AUDIT');

-- Step 2: Delete the TEST-NODE-AUDIT node itself
DELETE FROM nodes WHERE name = 'TEST-NODE-AUDIT';

-- Step 3: Delete test episode
DELETE FROM episode_memory WHERE id = 10934;

-- Step 4: Delete 'arbeitet_an' edges (inconsistent German relation name)
-- These should have been WORKS_ON per RELATION_SECTOR_MAP convention
DELETE FROM edges WHERE relation = 'arbeitet_an';

-- Step 5: Delete backup column from A2 (no longer needed after verification)
ALTER TABLE edges DROP COLUMN IF EXISTS memory_sector_backup;
