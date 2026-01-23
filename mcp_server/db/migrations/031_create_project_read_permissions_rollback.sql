-- Rollback Migration 031: Remove project_read_permissions Table
-- Story 11.2.2: Create project_read_permissions Table
--
-- WARNING: Only run if Story 11.2.2 needs to be rolled back
-- This removes the project_read_permissions table
--
-- Dependencies: None
-- Risk: LOW - Drops new table only

SET lock_timeout = '5s';

-- ============================================================================
-- DROP TABLE
-- ============================================================================

DROP TABLE IF EXISTS project_read_permissions;

RESET lock_timeout;
