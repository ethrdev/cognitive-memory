-- Migration 023: Add memory_strength Column for Memory Evolution (Epic 26)
-- Story 26.1: Memory Strength Field für I/O's Bedeutungszuweisung
--
-- Purpose: Persistiert I/O's memory_strength Werte für L2 Insights
-- Dependencies: Migration 001 (l2_insights table must exist)
-- Breaking Changes: KEINE - Feld hat Default 0.5, Migration ist idempotent
--
-- Memory Strength Values:
--   - 0.0: Schwache Bedeutung, vergesslich
--   - 0.5: Neutraler Default (Backward Compat)
--   - 1.0: Starke Bedeutung, zentral für I/O's Identität
--
-- ============================================================================
-- PHASE 1: SCHEMA MIGRATION - Add memory_strength Column
-- ============================================================================

-- Column: memory_strength - I/O's Bedeutungszuweisung für Insights
-- Type: FLOAT (PostgreSQL DOUBLE PRECISION)
-- Default: 0.5 (neutral - backward compatible mit bestehenden Insights)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'memory_strength'
    ) THEN
        ALTER TABLE l2_insights ADD COLUMN memory_strength FLOAT DEFAULT 0.5;
    END IF;
END $$;

-- ============================================================================
-- PHASE 2: DATA MIGRATION - Set Default für Existing Insights
-- ============================================================================

-- Alle bestehenden Insights bekommen den neutralen Default 0.5
UPDATE l2_insights
SET memory_strength = 0.5
WHERE memory_strength IS NULL;

-- ============================================================================
-- PHASE 3: ROLLBACK - DOWN Migration (für Rollback Szenario)
-- ============================================================================

-- Für Rollback: Column entfernen (IF EXISTS für Safety)
-- ALTER TABLE l2_insights DROP COLUMN IF EXISTS memory_strength;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify column exists:
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'l2_insights' AND column_name = 'memory_strength';

-- Verify data migration - keine NULL Werte:
-- SELECT COUNT(*) as null_count FROM l2_insights WHERE memory_strength IS NULL;

-- Verify memory_strength distribution:
-- SELECT
--     COUNT(*) as total_insights,
--     AVG(memory_strength) as avg_strength,
--     MIN(memory_strength) as min_strength,
--     MAX(memory_strength) as max_strength
-- FROM l2_insights;

-- Verify sample insights mit memory_strength:
-- SELECT id, LEFT(content, 50) as content_preview, memory_strength
-- FROM l2_insights
-- ORDER BY created_at DESC
-- LIMIT 10;

-- ============================================================================
-- UP-DOWN-UP CYCLE TEST (für Migration 023 Test Suite)
-- ============================================================================
-- Test Sequence:
--   1. UP: Migration ausführen (späterer Test)
--   2. VERIFY: Column existiert, alle haben 0.5
--   3. DOWN: Rollback ausführen
--   4. VERIFY: Column entfernt
--   5. UP: Migration erneut ausführen
--   6. VERIFY: Column wieder da, idempotent
