-- Migration 002: Fix session_id Type from UUID to VARCHAR(255)
-- Created: 2025-11-12 (Schema Consistency Fix between Story 1.2 and 1.4)
--
-- Rationale: VARCHAR(255) provides more flexibility than UUID constraint
-- Allows human-readable session IDs like "session-philosophy-2025-11-12"
-- while still supporting UUIDs if desired
--
-- ⚠️ NOTE: Only run this migration if your database was created with UUID type
-- If you created the database after 2025-11-12, this migration is NOT needed
-- (001_initial_schema.sql already uses VARCHAR(255))

-- Check current data type (informational - doesn't block migration)
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'l0_raw' AND column_name = 'session_id';

-- Convert UUID to VARCHAR(255)
-- This is safe because UUID is a valid substring of VARCHAR
-- Existing UUID values will be converted to their string representation
ALTER TABLE l0_raw
ALTER COLUMN session_id TYPE VARCHAR(255)
USING session_id::text;

-- Verify conversion (informational)
-- SELECT column_name, data_type, character_maximum_length
-- FROM information_schema.columns
-- WHERE table_name = 'l0_raw' AND column_name = 'session_id';
