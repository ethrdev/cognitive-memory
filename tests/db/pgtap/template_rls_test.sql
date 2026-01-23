-- ============================================================================
-- pgTAP Test Template for RLS Policy Testing
-- ============================================================================
--
-- This template demonstrates the standard pattern for testing RLS policies
-- using pgTAP. Copy this file and modify for specific RLS test scenarios.
--
-- Usage:
--   1. Copy this template to tests/db/pgtap/test_your_feature.sql
--   2. Modify the test plan (number of tests in plan())
--   3. Replace setup data with your test data
--   4. Replace assertions with your specific test cases
--   5. Run: pg_prove -d $TEST_DATABASE_URL tests/db/pgtap/test_your_feature.sql
--
-- Key Patterns:
--   - BEGIN/ROLLBACK: Transaction isolation for test data
--   - SET LOCAL ROLE: Switch roles for multi-user testing
--   - SET LOCAL app.current_project: Set project context for RLS
--   - RESET ROLE: Return to original role after testing
--   - SELECT plan(N): Declare number of tests at start
--   - SELECT finish(): Complete test run
--
-- ============================================================================

-- BEGIN TEST (transaction isolation)
BEGIN;

-- Setup test plan - this template has 9 assertions
SELECT plan(9);

-- ============================================================================
-- SETUP: Create Test Data
-- ============================================================================
-- Create ephemeral test projects within this transaction
-- Note: These will be rolled back, keeping production data clean

INSERT INTO project_registry (project_id, name, access_level)
VALUES
    ('test_super', 'Test Super Project', 'super'),
    ('test_shared', 'Test Shared Project', 'shared'),
    ('test_isolated', 'Test Isolated Project', 'isolated')
ON CONFLICT (project_id) DO NOTHING;

-- Grant read permission: test_shared -> test_isolated (simulates sm pattern)
INSERT INTO project_read_permissions (reader, target)
VALUES ('test_shared', 'test_isolated')
ON CONFLICT (reader, target) DO NOTHING;

-- Initialize RLS status for test projects
INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
VALUES
    ('test_super', 'enforcing', TRUE),
    ('test_shared', 'enforcing', TRUE),
    ('test_isolated', 'enforcing', TRUE)
ON CONFLICT (project_id) DO NOTHING;

-- Create sample test data for each project
INSERT INTO nodes (name, label, project_id)
VALUES
    ('super_node_1', 'test', 'test_super'),
    ('shared_node_1', 'test', 'test_shared'),
    ('isolated_node_1', 'test', 'test_isolated')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- TEST 1: Super user can read all projects
-- ============================================================================

-- Set project context to test_super
SET LOCAL app.current_project = 'test_super';

SELECT is(
    (SELECT COUNT(*) FROM nodes WHERE project_id = 'test_super'),
    1,
    'Super user can see own data (test_super)'
);

SELECT is(
    (SELECT COUNT(*) FROM nodes WHERE project_id = 'test_shared'),
    1,
    'Super user can see shared project data'
);

SELECT is(
    (SELECT COUNT(*) FROM nodes WHERE project_id = 'test_isolated'),
    1,
    'Super user can see isolated project data'
);

-- ============================================================================
-- TEST 2: Isolated user can only read own data
-- ============================================================================

-- Switch to isolated user context
SET LOCAL app.current_project = 'test_isolated';

SELECT is(
    (SELECT COUNT(*) FROM nodes),
    1,
    'Isolated user sees only own data'
);

SELECT is(
    (SELECT COUNT(*) FROM nodes WHERE project_id = 'test_super'),
    0,
    'Isolated user cannot see super project data'
);

-- ============================================================================
-- TEST 3: Shared user can read own + permitted projects
-- ============================================================================

-- Switch to shared user context (has permission to test_isolated)
SET LOCAL app.current_project = 'test_shared';

SELECT is(
    (SELECT COUNT(*) FROM nodes),
    2,
    'Shared user sees own + permitted data (shared + isolated)'
);

SELECT is(
    (SELECT project_id FROM nodes WHERE name = 'isolated_node_1'),
    'test_isolated',
    'Shared user can access permitted project data'
);

-- ============================================================================
-- TEST 4: Role-switching test with SET LOCAL ROLE
-- ============================================================================

-- Reset to super context
SET LOCAL app.current_project = 'test_super';

-- Verify we can see all data
SELECT is(
    (SELECT COUNT(*) FROM nodes),
    3,
    'Super context sees all nodes'
);

-- Switch to app_user role for isolated testing
SET LOCAL ROLE app_user;
SET LOCAL app.current_project = 'test_isolated';

SELECT is(
    (SELECT COUNT(*) FROM nodes),
    1,
    'With app_user role in isolated context, sees only own data'
);

-- Reset role back
RESET ROLE;

-- ============================================================================
-- CLEANUP (automatic via ROLLBACK)
-- ============================================================================

SELECT finish();
ROLLBACK;
-- END TEST

-- ============================================================================
-- Template Usage Examples
-- ============================================================================
--
-- Example 1: Testing write isolation
--   SET LOCAL app.current_project = 'test_isolated';
--   INSERT INTO nodes (name, label, project_id) VALUES ('new_node', 'test', 'test_other');
--   -- Should fail or be blocked by RLS
--
-- Example 2: Testing NULL project_id protection
--   SET LOCAL app.current_project = 'test_isolated';
--   INSERT INTO nodes (name, label, project_id) VALUES ('null_node', 'test', NULL);
--   -- Should be blocked by restrictive policy
--
-- Example 3: Testing multiple role switches in one test
--   SET LOCAL ROLE app_user;
--   SET LOCAL app.current_project = 'test_isolated';
--   -- Test as isolated user
--   RESET ROLE;
--   SET LOCAL app.current_project = 'test_super';
--   -- Test as super user
--
-- ============================================================================
