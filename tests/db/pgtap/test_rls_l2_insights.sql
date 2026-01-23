-- ============================================================================
-- pgTAP Tests for RLS Policies on l2_insights
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
-- Run: pg_prove -d $TEST_DATABASE_URL tests/db/pgtap/test_rls_l2_insights.sql
-- ============================================================================

-- BEGIN TEST (transaction isolation)
BEGIN;

-- Setup test plan - 22 assertions
SELECT plan(22);

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

-- Create sample test data for each project
INSERT INTO l2_insights (content, source_ids, project_id)
VALUES
    ('io insight data', ARRAY[1], 'test_io'),
    ('aa insight data', ARRAY[2], 'test_aa'),
    ('sm insight data', ARRAY[3], 'test_sm')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- TEST 1: RLS Configuration Verification
-- ============================================================================

SELECT has_rlspolicy(
    'public',
    'l2_insights',
    'require_project_id',
    'RESTRICTIVE policy exists for NULL protection'
);

SELECT isnt_rlspolicy_permissive(
    'public',
    'l2_insights',
    'require_project_id',
    'require_project_id is RESTRICTIVE (not permissive)'
);

SELECT has_rlspolicy(
    'public',
    'l2_insights',
    'select_l2_insights',
    'SELECT policy exists'
);

SELECT has_rlspolicy(
    'public',
    'l2_insights',
    'insert_l2_insights',
    'INSERT policy exists'
);

SELECT has_rlspolicy(
    'public',
    'l2_insights',
    'update_l2_insights',
    'UPDATE policy exists'
);

SELECT has_rlspolicy(
    'public',
    'l2_insights',
    'delete_l2_insights',
    'DELETE policy exists'
);

-- Check FORCE ROW LEVEL SECURITY is enabled
SELECT is(
    (SELECT relrowsecurity FROM pg_class WHERE relname = 'l2_insights'),
    TRUE,
    'RLS is enabled on l2_insights'
);

SELECT is(
    (SELECT relforcerowsecurity FROM pg_class WHERE relname = 'l2_insights'),
    TRUE,
    'FORCE ROW LEVEL SECURITY is enabled on l2_insights'
);

-- ============================================================================
-- TEST 2: Super User Can Read All Projects (AC5)
-- ============================================================================

PERFORM set_project_context('test_io');

SELECT is(
    (SELECT COUNT(*) FROM l2_insights WHERE project_id = 'test_io'),
    1,
    'Super user can see own data (test_io)'
);

SELECT is(
    (SELECT COUNT(*) FROM l2_insights WHERE project_id = 'test_aa'),
    1,
    'Super user can see shared project data (test_aa)'
);

SELECT is(
    (SELECT COUNT(*) FROM l2_insights WHERE project_id = 'test_sm'),
    1,
    'Super user can see isolated project data (test_sm)'
);

SELECT is(
    (SELECT COUNT(*) FROM l2_insights),
    3,
    'Super user can read all projects (3 total rows)'
);

-- ============================================================================
-- TEST 3: Shared User Can Read Own + Permitted Projects (AC5)
-- ============================================================================

PERFORM set_project_context('test_aa');

SELECT is(
    (SELECT COUNT(*) FROM l2_insights),
    2,
    'Shared user sees own + permitted data (test_aa + test_sm)'
);

SELECT is(
    (SELECT project_id FROM l2_insights WHERE content = 'sm insight data'),
    'test_sm',
    'Shared user can access permitted project data (test_sm)'
);

SELECT is(
    (SELECT COUNT(*) FROM l2_insights WHERE project_id = 'test_io'),
    0,
    'Shared user cannot see non-permitted project (test_io)'
);

-- ============================================================================
-- TEST 4: Isolated User Can Read Only Own Project (AC5)
-- ============================================================================

PERFORM set_project_context('test_sm');

SELECT is(
    (SELECT COUNT(*) FROM l2_insights),
    1,
    'Isolated user sees only own data'
);

SELECT is(
    (SELECT COUNT(*) FROM l2_insights WHERE project_id = 'test_aa'),
    0,
    'Isolated user cannot see shared project data'
);

SELECT is(
    (SELECT COUNT(*) FROM l2_insights WHERE project_id = 'test_io'),
    0,
    'Isolated user cannot see super project data'
);

-- ============================================================================
-- TEST 5: Write Isolation - Even Super Cannot Write to Other Projects (AC6)
-- ============================================================================

PERFORM set_project_context('test_io');

-- Try to insert with different project_id - should be blocked
-- Note: This will raise an error, so we test via a function that catches it
DO $$
BEGIN
    -- This INSERT should fail due to RLS policy
    INSERT INTO l2_insights (content, source_ids, project_id)
    VALUES ('unauthorized insert', ARRAY[99], 'test_aa');

    RAISE EXCEPTION 'INSERT should have been blocked by RLS policy';
EXCEPTION WHEN OTHERS THEN
    -- Expected - policy blocked the insert
    IF SQLSTATE != '42501' THEN  -- insufficient_privilege
        RAISE;
    END IF;
END $$;

SELECT ok(TRUE, 'Super user cannot INSERT into other projects');

-- Try to UPDATE other project's data - should be blocked
DO $$
BEGIN
    UPDATE l2_insights SET content = 'hacked' WHERE project_id = 'test_aa';

    RAISE EXCEPTION 'UPDATE should have been blocked by RLS policy';
EXCEPTION WHEN OTHERS THEN
    -- Expected - policy blocked the update
    IF SQLSTATE != '42501' THEN
        RAISE;
    END IF;
END $$;

SELECT ok(TRUE, 'Super user cannot UPDATE other projects');

-- Try to DELETE other project's data - should be blocked
DO $$
BEGIN
    DELETE FROM l2_insights WHERE project_id = 'test_aa';

    RAISE EXCEPTION 'DELETE should have been blocked by RLS policy';
EXCEPTION WHEN OTHERS THEN
    -- Expected - policy blocked the delete
    IF SQLSTATE != '42501' THEN
        RAISE;
    END IF;
END $$;

SELECT ok(TRUE, 'Super user cannot DELETE from other projects');

-- ============================================================================
-- TEST 6: Pending/Shadow Modes Allow All Reads (AC4)
-- ============================================================================

-- Set to pending mode
PERFORM set_project_context('test_sm');
INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
VALUES ('test_sm', 'pending', TRUE)
ON CONFLICT (project_id) DO UPDATE SET migration_phase = 'pending';

PERFORM set_project_context('test_sm');

SELECT is(
    (SELECT COUNT(*) FROM l2_insights),
    3,
    'Pending mode: Isolated user can see all data (no enforcement)'
);

-- Set to shadow mode
INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
VALUES ('test_sm', 'shadow', TRUE)
ON CONFLICT (project_id) DO UPDATE SET migration_phase = 'shadow';

PERFORM set_project_context('test_sm');

SELECT is(
    (SELECT COUNT(*) FROM l2_insights),
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
