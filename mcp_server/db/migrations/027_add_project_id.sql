-- Migration 027: Add project_id Column for Epic 11 Namespace Isolation
-- Story 11.1.1: Add project_id Column to All Tables
--
-- Purpose: Add project_id column to all tenant-relevant tables for multi-project isolation
-- Dependencies: Migration 026 (stale_memory fix must exist)
-- Breaking Changes: KEINE - Felder haben Defaults, Migration ist idempotent
--
-- Epic 11 Context: Namespace-Isolation fur Multi-Project Support
--   Phase 1 (this story): Schema addition with instant metadata operations
--   Phase 2 (Story 11.1.2): Data backfill with batched UPDATE statements
--   Phase 3 (Story 11.1.3): Constraint validation with VALIDATE CONSTRAINT
--
-- Default Value Rationale: All existing data assigned project_id = 'io'
--   - cognitive-memory originally built for I/O's personal memory system
--   - 'io' is registered project_id for "i-o-system" (super user level)
--   - Decision documented in knowledge/DECISION-namespace-isolation-strategy.md
--
-- Zero-Downtime Pattern (PostgreSQL 11+):
--   - ADD COLUMN with DEFAULT is instant (metadata-only operation)
--   - CHECK (...) NOT VALID creates constraint without table scan
--   - Lock duration: milliseconds per table

-- ============================================================================
-- PHASE 1: SCHEMA MIGRATION - Add project_id Columns
-- ============================================================================

-- Core Tables (High Risk) - using NOT VALID for zero-downtime
-- l2_insights: Vector embeddings, critical for search (~1,000 rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE l2_insights ADD COLUMN project_id VARCHAR(50) DEFAULT 'io';
        ALTER TABLE l2_insights ADD CONSTRAINT check_l2_insights_project_id_not_null
            CHECK (project_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- nodes: Graph entities (~500 rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'nodes' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE nodes ADD COLUMN project_id VARCHAR(50) DEFAULT 'io';
        ALTER TABLE nodes ADD CONSTRAINT check_nodes_project_id_not_null
            CHECK (project_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- edges: Graph relationships (~1,500 rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'edges' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE edges ADD COLUMN project_id VARCHAR(50) DEFAULT 'io';
        ALTER TABLE edges ADD CONSTRAINT check_edges_project_id_not_null
            CHECK (project_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- Support Tables (Lower Risk)
-- working_memory: Per-project capacity (<100 rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'working_memory' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE working_memory ADD COLUMN project_id VARCHAR(50) DEFAULT 'io';
        ALTER TABLE working_memory ADD CONSTRAINT check_working_memory_project_id_not_null
            CHECK (project_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- episode_memory: Actual table name verified (~100 rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'episode_memory' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE episode_memory ADD COLUMN project_id VARCHAR(50) DEFAULT 'io';
        ALTER TABLE episode_memory ADD CONSTRAINT check_episode_memory_project_id_not_null
            CHECK (project_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- l0_raw: Actual table name verified (~500 rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'l0_raw' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE l0_raw ADD COLUMN project_id VARCHAR(50) DEFAULT 'io';
        ALTER TABLE l0_raw ADD CONSTRAINT check_l0_raw_project_id_not_null
            CHECK (project_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- ground_truth: Test data (<50 rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ground_truth' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE ground_truth ADD COLUMN project_id VARCHAR(50) DEFAULT 'io';
        ALTER TABLE ground_truth ADD CONSTRAINT check_ground_truth_project_id_not_null
            CHECK (project_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- Additional Tables (discovered in schema analysis)
-- stale_memory: Added in migration 026 (~50 rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'stale_memory' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE stale_memory ADD COLUMN project_id VARCHAR(50) DEFAULT 'io';
        ALTER TABLE stale_memory ADD CONSTRAINT check_stale_memory_project_id_not_null
            CHECK (project_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- smf_proposals: SMF framework (<20 rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'smf_proposals' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE smf_proposals ADD COLUMN project_id VARCHAR(50) DEFAULT 'io';
        ALTER TABLE smf_proposals ADD CONSTRAINT check_smf_proposals_project_id_not_null
            CHECK (project_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- ief_feedback: IEF evaluation feedback (<50 rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ief_feedback' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE ief_feedback ADD COLUMN project_id VARCHAR(50) DEFAULT 'io';
        ALTER TABLE ief_feedback ADD CONSTRAINT check_ief_feedback_project_id_not_null
            CHECK (project_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- l2_insight_history: Version history (added in 024) (<100 rows)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'l2_insight_history' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE l2_insight_history ADD COLUMN project_id VARCHAR(50) DEFAULT 'io';
        ALTER TABLE l2_insight_history ADD CONSTRAINT check_l2_insight_history_project_id_not_null
            CHECK (project_id IS NOT NULL) NOT VALID;
    END IF;
END $$;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify all columns exist with correct defaults:
-- SELECT table_name, column_name, column_default, is_nullable
-- FROM information_schema.columns
-- WHERE column_name = 'project_id'
-- ORDER BY table_name;

-- Verify no NULL values (DEFAULT ensures this):
-- SELECT table_name, COUNT(*) as null_count
-- FROM (
--     SELECT 'l2_insights' as table_name FROM l2_insights WHERE project_id IS NULL
--     UNION ALL
--     SELECT 'nodes' FROM nodes WHERE project_id IS NULL
--     UNION ALL
--     SELECT 'edges' FROM edges WHERE project_id IS NULL
--     UNION ALL
--     SELECT 'working_memory' FROM working_memory WHERE project_id IS NULL
--     UNION ALL
--     SELECT 'episode_memory' FROM episode_memory WHERE project_id IS NULL
--     UNION ALL
--     SELECT 'l0_raw' FROM l0_raw WHERE project_id IS NULL
--     UNION ALL
--     SELECT 'ground_truth' FROM ground_truth WHERE project_id IS NULL
--     UNION ALL
--     SELECT 'stale_memory' FROM stale_memory WHERE project_id IS NULL
--     UNION ALL
--     SELECT 'smf_proposals' FROM smf_proposals WHERE project_id IS NULL
--     UNION ALL
--     SELECT 'ief_feedback' FROM ief_feedback WHERE project_id IS NULL
--     UNION ALL
--     SELECT 'l2_insight_history' FROM l2_insight_history WHERE project_id IS NULL
-- ) null_checks
-- GROUP BY table_name;

-- Verify project_id distribution (should be all 'io' after this migration):
-- SELECT table_name, project_id, COUNT(*) as row_count
-- FROM (
--     SELECT 'l2_insights' as table_name, project_id FROM l2_insights
--     UNION ALL
--     SELECT 'nodes', project_id FROM nodes
--     UNION ALL
--     SELECT 'edges', project_id FROM edges
--     UNION ALL
--     SELECT 'working_memory', project_id FROM working_memory
--     UNION ALL
--     SELECT 'episode_memory', project_id FROM episode_memory
--     UNION ALL
--     SELECT 'l0_raw', project_id FROM l0_raw
--     UNION ALL
--     SELECT 'ground_truth', project_id FROM ground_truth
--     UNION ALL
--     SELECT 'stale_memory', project_id FROM stale_memory
--     UNION ALL
--     SELECT 'smf_proposals', project_id FROM smf_proposals
--     UNION ALL
--     SELECT 'ief_feedback', project_id FROM ief_feedback
--     UNION ALL
--     SELECT 'l2_insight_history', project_id FROM l2_insight_history
-- ) project_distribution
-- GROUP BY table_name, project_id
-- ORDER BY table_name;

-- Check NOT VALID constraints (should be NOT VALID for zero-downtime):
-- SELECT conname, contype, convalidated
-- FROM pg_constraint
-- WHERE conname LIKE '%project_id_not_null'
-- ORDER BY conname;

-- ============================================================================
-- VERIFICATION BLOCK - Execute these queries to verify migration success
-- ============================================================================

-- Verification 1: Check all columns exist
DO $$
DECLARE
    verification_error TEXT := '';
    expected_tables TEXT[] := ARRAY[
        'l2_insights', 'nodes', 'edges', 'working_memory',
        'episode_memory', 'l0_raw', 'ground_truth', 'stale_memory',
        'smf_proposals', 'ief_feedback', 'l2_insight_history'
    ];
    table_name TEXT;
    column_count INT;
BEGIN
    FOREACH table_name IN ARRAY expected_tables
    LOOP
        SELECT COUNT(*) INTO column_count
        FROM information_schema.columns
        WHERE table_name = table_name AND column_name = 'project_id';

        IF column_count = 0 THEN
            verification_error := verification_error || 'ERROR: ' || table_name || ' missing project_id column;';
        END IF;
    END LOOP;

    IF verification_error != '' THEN
        RAISE EXCEPTION 'Migration verification failed: %', verification_error;
    ELSE
        RAISE NOTICE 'SUCCESS: All 11 tables have project_id column';
    END IF;
END $$;

-- Verification 2: Check all NOT VALID constraints exist
DO $$
DECLARE
    constraint_count INT;
BEGIN
    SELECT COUNT(*) INTO constraint_count
    FROM pg_constraint
    WHERE conname LIKE '%project_id_not_null' AND convalidated = 'f';

    IF constraint_count < 11 THEN
        RAISE EXCEPTION 'Migration verification failed: Expected 11 NOT VALID constraints, found %', constraint_count;
    ELSE
        RAISE NOTICE 'SUCCESS: All 11 NOT VALID constraints created';
    END IF;
END $$;

-- Verification 3: Check no NULL values exist (safeguard)
DO $$
DECLARE
    null_count INT;
    table_name TEXT;
BEGIN
    SELECT COUNT(*) INTO null_count
    FROM (
        SELECT 'l2_insights' as table_name FROM l2_insights WHERE project_id IS NULL
        UNION ALL
        SELECT 'nodes' FROM nodes WHERE project_id IS NULL
        UNION ALL
        SELECT 'edges' FROM edges WHERE project_id IS NULL
        UNION ALL
        SELECT 'working_memory' FROM working_memory WHERE project_id IS NULL
        UNION ALL
        SELECT 'episode_memory' FROM episode_memory WHERE project_id IS NULL
        UNION ALL
        SELECT 'l0_raw' FROM l0_raw WHERE project_id IS NULL
        UNION ALL
        SELECT 'ground_truth' FROM ground_truth WHERE project_id IS NULL
        UNION ALL
        SELECT 'stale_memory' FROM stale_memory WHERE project_id IS NULL
        UNION ALL
        SELECT 'smf_proposals' FROM smf_proposals WHERE project_id IS NULL
        UNION ALL
        SELECT 'ief_feedback' FROM ief_feedback WHERE project_id IS NULL
        UNION ALL
        SELECT 'l2_insight_history' FROM l2_insight_history WHERE project_id IS NULL
    ) null_checks;

    IF null_count > 0 THEN
        RAISE EXCEPTION 'Migration verification failed: Found % NULL project_id values', null_count;
    ELSE
        RAISE NOTICE 'SUCCESS: No NULL project_id values found';
    END IF;
END $$;

-- Verification 4: Log completion with timestamp
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Migration 027 completed successfully at %', now();
    RAISE NOTICE 'All 11 tables have project_id with DEFAULT ''io''';
    RAISE NOTICE 'All constraints are NOT VALID (zero-downtime)';
    RAISE NOTICE '========================================';
END $$;
