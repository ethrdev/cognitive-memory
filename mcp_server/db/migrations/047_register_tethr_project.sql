-- Migration 047: Register tethr Project
--
-- Purpose: Add tethr as isolated project in project_registry
--          tethr is a personal AI analyst system for Stefan.
--          Highly sensitive personal data requires isolated access.
-- Access: isolated — tethr reads/writes only own data
--         io (super) can read tethr data for cross-system context
-- Dependencies: Migration 030 (project_registry), 032 (rls_migration_status)
-- Risk: LOW - Data insertion with idempotency protection

SET lock_timeout = '5s';

-- Register tethr as isolated project
INSERT INTO project_registry (project_id, name, access_level)
VALUES ('tethr', 'tethr', 'isolated')
ON CONFLICT (project_id) DO NOTHING;

-- Add RLS migration status
INSERT INTO rls_migration_status (project_id, migration_phase)
VALUES ('tethr', 'pending')
ON CONFLICT (project_id) DO NOTHING;

-- Verification:
-- SELECT * FROM project_registry WHERE project_id = 'tethr';
-- SELECT * FROM rls_migration_status WHERE project_id = 'tethr';

RESET lock_timeout;
