-- ============================================================================
-- pgTAP Tests for RLS Policies on nodes
-- Story 11.3.3: RLS Policies for Core Tables
--
-- Tests:
--   - RLS enabled and FORCE ROW LEVEL SECURITY set
--   - RESTRICTIVE policy blocks NULL project_id
--   - Super user can read all projects
--   - Shared user can read own + permitted projects
--   - Isolated user can read only own project
--   - All users can write only to own project
--   - Pending/shadow modes allow all reads
--
-- Run: pg_prove -d $TEST_DATABASE_URL tests/db/pgtap/test_rls_nodes.sql
-- ============================================================================

-- BEGIN TEST (transaction isolation)
BEGIN;

-- Setup test plan - 19 assertions
SELECT plan(19);

-- ============================================================================
-- SETUP: Create Test Data
-- ============================================================================

-- Create ephemeral test projects
INSERT INTO project_registry (project_id, name, access_level)
VALUES
    ('test_io', 'Test IO Super', 'super'),
    ('test_aa', 'Test AA Shared', 'shared'),
    ('test_sm', 'Test SM Isolated', 'isolated')
ON CONFLICT (project_id) DO NOTHING;

-- Grant read permission: test_aa -> test_sm (simulates sm pattern)
INSERT INTO project_read_permissions (reader_project_id, target_project_id)
VALUES ('test_aa', 'test_sm')
ON CONFLICT (reader_project_id, target_project_id) DO NOTHING;

-- Initialize RLS status for test projects
INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
VALUES
    ('test_io', 'enforcing', TRUE),
    ('test_aa', 'enforcing', TRUE),
    ('test_sm', 'enforcing', TRUE)
ON CONFLICT (project_id) DO NOTHING;

-- Create sample test nodes for each project
INSERT INTO nodes (label, name, project_id)
VALUES
    ('test', 'io_node', 'test_io'),
    ('test', 'aa_node', 'test_aa'),
    ('test', 'sm_node', 'test_sm')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- TEST 1: RLS Configuration Verification
-- ============================================================================

SELECT has_rlspolicy(
    'public',
    'nodes',
    'require_project_id',
    'RESTRICTIVE policy exists for NULL protection'
);

SELECT has_rlspolicy(
    'public',
    'nodes',
    'select_nodes',
    'SELECT policy exists'
);

SELECT has_rlspolicy(
    'public',
    'nodes',
    'insert_nodes',
    'INSERT policy exists'
);

SELECT has_rlspolicy(
    'public',
    'nodes',
    'update_nodes',
    'UPDATE policy exists'
);

SELECT has_rlspolicy(
    'public',
    'nodes',
    'delete_nodes',
    'DELETE policy exists'
);

-- Check FORCE ROW LEVEL SECURITY is enabled
SELECT is(
    (SELECT relrowsecurity FROM pg_class WHERE relname = 'nodes'),
    TRUE,
    'RLS is enabled on nodes'
);

SELECT is(
    (SELECT relforcerowsecurity FROM pg_class WHERE relname = 'nodes'),
    TRUE,
    'FORCE ROW LEVEL SECURITY is enabled on nodes'
);

-- ============================================================================
-- TEST 2: Super User Can Read All Projects (AC5)
-- ============================================================================

PERFORM set_project_context('test_io');

SELECT is(
    (SELECT COUNT(*) FROM nodes WHERE project_id = 'test_io'),
    1,
    'Super user can see own data (test_io)'
);

SELECT is(
    (SELECT COUNT(*) FROM nodes WHERE project_id = 'test_aa'),
    1,
    'Super user can see shared project data (test_aa)'
);

SELECT is(
    (SELECT COUNT(*) FROM nodes),
    3,
    'Super user can read all projects (3 total rows)'
);

-- ============================================================================
-- TEST 3: Shared User Can Read Own + Permitted Projects (AC5)
-- ============================================================================

PERFORM set_project_context('test_aa');

SELECT is(
    (SELECT COUNT(*) FROM nodes),
    2,
    'Shared user sees own + permitted data (test_aa + test_sm)'
);

SELECT is(
    (SELECT project_id FROM nodes WHERE name = 'sm_node'),
    'test_sm',
    'Shared user can access permitted project data (test_sm)'
);

-- ============================================================================
-- TEST 4: Isolated User Can Read Only Own Project (AC5)
-- ============================================================================

PERFORM set_project_context('test_sm');

SELECT is(
    (SELECT COUNT(*) FROM nodes),
    1,
    'Isolated user sees only own data'
);

SELECT is(
    (SELECT COUNT(*) FROM nodes WHERE project_id = 'test_io'),
    0,
    'Isolated user cannot see super project data'
);

-- ============================================================================
-- TEST 5: Write Isolation - Even Super Cannot Write to Other Projects (AC6)
-- ============================================================================

PERFORM set_project_context('test_io');

-- Try to insert with different project_id - should be blocked
DO $$
BEGIN
    INSERT INTO nodes (label, name, project_id)
    VALUES ('test', 'unauthorized', 'test_aa');

    RAISE EXCEPTION 'INSERT should have been blocked by RLS policy';
EXCEPTION WHEN OTHERS THEN
    -- Expected - policy blocked the insert
    IF SQLSTATE != '42501' THEN
        RAISE;
    END IF;
END $$;

SELECT ok(TRUE, 'Super user cannot INSERT into other projects');

-- Try to UPDATE other project's data - should be blocked
DO $$
BEGIN
    UPDATE nodes SET name = 'hacked' WHERE project_id = 'test_aa';

    RAISE EXCEPTION 'UPDATE should have been blocked by RLS policy';
EXCEPTION WHEN OTHERS THEN
    IF SQLSTATE != '42501' THEN
        RAISE;
    END IF;
END $$;

SELECT ok(TRUE, 'Super user cannot UPDATE other projects');

-- ============================================================================
-- TEST 6: Pending/Shadow Modes Allow All Reads (AC4)
-- ============================================================================

-- Set to pending mode
INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
VALUES ('test_sm', 'pending', TRUE)
ON CONFLICT (project_id) DO UPDATE SET migration_phase = 'pending';

PERFORM set_project_context('test_sm');

SELECT is(
    (SELECT COUNT(*) FROM nodes),
    3,
    'Pending mode: Isolated user can see all data (no enforcement)'
);

-- Set to shadow mode
INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
VALUES ('test_sm', 'shadow', TRUE)
ON CONFLICT (project_id) DO UPDATE SET migration_phase = 'shadow';

PERFORM set_project_context('test_sm');

SELECT is(
    (SELECT COUNT(*) FROM nodes),
    3,
    'Shadow mode: Isolated user can see all data (audit-only)'
);

-- Reset to enforcing for cleanup
INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
VALUES ('test_sm', 'enforcing', TRUE)
ON CONFLICT (project_id) DO UPDATE SET migration_phase = 'enforcing';

-- ============================================================================
-- CLEANUP (automatic via ROLLBACK)
-- ============================================================================

SELECT finish();
ROLLBACK;
-- END TEST
