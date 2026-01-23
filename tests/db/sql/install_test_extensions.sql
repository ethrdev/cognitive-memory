-- ============================================================================
-- TEST-ONLY EXTENSIONS AND ROLES
-- ============================================================================
-- WARNING: This script is for TEST DATABASE ONLY
-- NEVER run these statements in production
--
-- Purpose:
--   1. Install pgTAP extension for database-native testing
--   2. Create test_bypass_role with BYPASSRLS for test data setup/verification
--
-- Usage:
--   psql -d $TEST_DATABASE_URL -f tests/db/sql/install_test_extensions.sql
--
-- Environment Variables Required:
--   - TEST_DATABASE_URL: Test database connection string
--   - TEST_BYPASS_PASSWORD: Password for test_bypass_role (set after creation)
-- ============================================================================

-- pgTAP extension for database-native testing
-- Available on: AWS RDS/Aurora, Google Cloud SQL
-- NOT available on: Azure PostgreSQL (use pytest fallback in that case)
CREATE EXTENSION IF NOT EXISTS pgtap;

-- ============================================================================
-- BYPASSRLS Role for Test Data Setup and Verification
-- ============================================================================
-- This role can bypass RLS policies for:
--   - Setting up test data across multiple projects
--   - Verifying data state during assertions
--   - Cleaning up test data
--
-- SECURITY NOTES:
--   - BYPASSRLS allows this role to ignore ALL RLS policies
--   - Only for test database, NEVER production
--   - Password must be set via environment variable, never hardcoded
--   - Role requires LOGIN to connect via TEST_BYPASS_DSN
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'test_bypass_role') THEN
        CREATE ROLE test_bypass_role WITH
            LOGIN            -- Can login via TEST_BYPASS_DSN connection string
            BYPASSRLS        -- This role ignores RLS policies
            NOINHERIT        -- Does not inherit permissions from other roles
            NOSUPERUSER      -- Not a superuser (least privilege)
            PASSWORD NULL;   -- Password set via environment variable
    END IF;
END $$;

COMMENT ON ROLE test_bypass_role IS
'Test-only role with BYPASSRLS for RLS policy testing. NEVER use in production.';

-- Grant necessary permissions to test_bypass_role
-- Note: These grants are on the public schema in the test database
-- Use DO block to dynamically get current database name
DO $$
DECLARE
    db_name text;
BEGIN
    SELECT current_database() INTO db_name;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO test_bypass_role', db_name);
END $$;

GRANT USAGE ON SCHEMA public TO test_bypass_role;

-- Grant SELECT, INSERT, UPDATE, DELETE on all existing tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO test_bypass_role;

-- Grant SELECT on all sequences (for serial/id columns)
GRANT SELECT, USAGE ON ALL SEQUENCES IN SCHEMA public TO test_bypass_role;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO test_bypass_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, USAGE ON SEQUENCES TO test_bypass_role;

-- ============================================================================
-- Post-Installation Instructions
-- ============================================================================
--
-- After running this script, set the password for test_bypass_role:
--
--   psql -d $TEST_DATABASE_URL -c
--     "ALTER ROLE test_bypass_role PASSWORD '${TEST_BYPASS_PASSWORD}';"
--
-- Or set via environment variable in your test runner:
--
--   export TEST_BYPASS_DSN="postgresql://test_bypass_role:${TEST_BYPASS_PASSWORD}@localhost:5432/cognitive_memory_test"
--
-- ============================================================================
