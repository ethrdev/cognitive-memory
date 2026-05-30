-- Migration 049: Register njord Project + Enforce RLS
--
-- Purpose: Add njord as isolated project, advance directly to enforcing.
--          njord is Stefan's personal business agent (pipeline, proposals, finance).
-- Access: isolated — njord reads/writes only own data.
-- Dependencies: Migration 030 (project_registry), 032 (rls_migration_status)
-- Risk: LOW — idempotent inserts, new project, no existing data.

SET lock_timeout = '5s';

-- Register njord
INSERT INTO project_registry (project_id, name, access_level)
VALUES ('njord', 'njord', 'isolated')
ON CONFLICT (project_id) DO NOTHING;

-- Set RLS directly to enforcing (no pending phase needed)
INSERT INTO rls_migration_status (project_id, migration_phase)
VALUES ('njord', 'enforcing')
ON CONFLICT (project_id) DO UPDATE SET migration_phase = 'enforcing', updated_at = NOW();

RESET lock_timeout;
