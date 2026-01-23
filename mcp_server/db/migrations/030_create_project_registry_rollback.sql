-- Rollback Migration 030: Remove project_registry Table
--
-- WARNING: Only run if Story 11.2.1 needs to be rolled back
-- This removes the project registry table and access level enum
--
-- Risk: MEDIUM - Drops table and enum type
-- Dependencies: Must run before Story 11.2.2 creates dependent tables

SET lock_timeout = '5s';

-- Drop table first (no CASCADE needed if run before 11.2.2)
DROP TABLE IF EXISTS project_registry;

-- Drop enum type
DROP TYPE IF EXISTS access_level_enum;

RESET lock_timeout;
