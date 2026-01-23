-- Rollback Migration 032: Remove rls_migration_status Table
--
-- WARNING: Only run if Story 11.2.3 needs to be rolled back
-- This removes the rls_migration_status table and migration_phase_enum
--
-- Dependencies: None
-- Risk: LOW - Drops table and enum type
-- Re-apply: 032_create_rls_migration_status.sql

SET lock_timeout = '5s';

-- ============================================================================
-- DROP TRIGGER
-- ============================================================================

DROP TRIGGER IF EXISTS update_rls_migration_status_updated_at ON rls_migration_status;

-- ============================================================================
-- DROP TABLE
-- ============================================================================

-- Use CASCADE for future-proofing (Epic 11.3 may add RLS policies/views)
DROP TABLE IF EXISTS rls_migration_status CASCADE;

-- ============================================================================
-- DROP ENUM TYPE
-- ============================================================================

DROP TYPE IF EXISTS migration_phase_enum;

RESET lock_timeout;
