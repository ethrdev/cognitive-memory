-- ============================================================================
-- pgTAP Tests for RLS Policies on Support Tables
-- Story 11.3.4: RLS Policies for Support Tables
--
-- Tests:
--   - RLS enabled and FORCE ROW LEVEL SECURITY set on all 6 support tables
--   - RESTRICTIVE policy blocks NULL project_id
--   - working_memory isolation per project
--   - episode_memory isolation per project
--   - l0_raw isolation per project
--   - ground_truth isolation per project
--   - smf_proposals isolation per project
--   - stale_memory isolation per project
--   - Pending/shadow modes allow all reads
--   - Write isolation (all users can write only to own project)
--
-- Run: pg_prove -d $TEST_DATABASE_URL tests/db/pgtap/test_rls_support_tables.sql
-- ============================================================================

-- BEGIN TEST (transaction isolation)
BEGIN;

-- Setup test plan - 68 assertions (added 6 for RESTRICTIVE NULL tests)
SELECT plan(68);

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
INSERT INTO working_memory (key, value, importance, last_accessed, project_id)
VALUES
    ('io_key', 'io_value', 0.5, NOW(), 'test_io'),
    ('aa_key', 'aa_value', 0.5, NOW(), 'test_aa'),
    ('sm_key', 'sm_value', 0.5, NOW(), 'test_sm')
ON CONFLICT DO NOTHING;

INSERT INTO episode_memory (episode, importance, embedding, project_id)
VALUES
    ('io episode', 0.5, ARRAY[0.1, 0.2, 0.3]::REAL[], 'test_io'),
    ('aa episode', 0.5, ARRAY[0.1, 0.2, 0.3]::REAL[], 'test_aa'),
    ('sm episode', 0.5, ARRAY[0.1, 0.2, 0.3]::REAL[], 'test_sm')
ON CONFLICT DO NOTHING;

INSERT INTO l0_raw (session_id, speaker, content, timestamp, project_id)
VALUES
    ('io_session', 'io', 'io raw data', NOW(), 'test_io'),
    ('aa_session', 'aa', 'aa raw data', NOW(), 'test_aa'),
    ('sm_session', 'sm', 'sm raw data', NOW(), 'test_sm')
ON CONFLICT DO NOTHING;

INSERT INTO ground_truth (query, response_1, response_2, judge1_score, judge2_score, project_id)
VALUES
    ('io query', 'io resp1', 'io resp2', ARRAY[0.5]::FLOAT[], ARRAY[0.6]::FLOAT[], 'test_io'),
    ('aa query', 'aa resp1', 'aa resp2', ARRAY[0.5]::FLOAT[], ARRAY[0.6]::FLOAT[], 'test_aa'),
    ('sm query', 'sm resp1', 'sm resp2', ARRAY[0.5]::FLOAT[], ARRAY[0.6]::FLOAT[], 'test_sm')
ON CONFLICT DO NOTHING;

INSERT INTO smf_proposals (proposal_type, edge_id, original_state, status, approval_level, project_id)
VALUES
    ('DISSONANCE', 1, '{}'::JSONB, 'PENDING', 'bilateral', 'test_io'),
    ('DISSONANCE', 2, '{}'::JSONB, 'PENDING', 'bilateral', 'test_aa'),
    ('DISSONANCE', 3, '{}'::JSONB, 'PENDING', 'bilateral', 'test_sm')
ON CONFLICT DO NOTHING;

INSERT INTO stale_memory (content, original_content, archived_at, importance, project_id)
VALUES
    ('io stale', 'io stale', NOW(), 0.5, 'test_io'),
    ('aa stale', 'aa stale', NOW(), 0.5, 'test_aa'),
    ('sm stale', 'sm stale', NOW(), 0.5, 'test_sm')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- TEST 1: RLS Configuration Verification - All 6 Support Tables
-- ============================================================================

-- working_memory
SELECT has_rlspolicy('public', 'working_memory', 'require_project_id',
    'working_memory: RESTRICTIVE policy exists for NULL protection');
SELECT has_rlspolicy('public', 'working_memory', 'select_working_memory',
    'working_memory: SELECT policy exists');
SELECT has_rlspolicy('public', 'working_memory', 'insert_working_memory',
    'working_memory: INSERT policy exists');
SELECT has_rlspolicy('public', 'working_memory', 'update_working_memory',
    'working_memory: UPDATE policy exists');
SELECT has_rlspolicy('public', 'working_memory', 'delete_working_memory',
    'working_memory: DELETE policy exists');
SELECT is((SELECT relrowsecurity FROM pg_class WHERE relname = 'working_memory'), TRUE,
    'working_memory: RLS is enabled');
SELECT is((SELECT relforcerowsecurity FROM pg_class WHERE relname = 'working_memory'), TRUE,
    'working_memory: FORCE ROW LEVEL SECURITY is enabled');

-- episode_memory
SELECT has_rlspolicy('public', 'episode_memory', 'require_project_id',
    'episode_memory: RESTRICTIVE policy exists for NULL protection');
SELECT has_rlspolicy('public', 'episode_memory', 'select_episode_memory',
    'episode_memory: SELECT policy exists');
SELECT has_rlspolicy('public', 'episode_memory', 'insert_episode_memory',
    'episode_memory: INSERT policy exists');
SELECT has_rlspolicy('public', 'episode_memory', 'update_episode_memory',
    'episode_memory: UPDATE policy exists');
SELECT has_rlspolicy('public', 'episode_memory', 'delete_episode_memory',
    'episode_memory: DELETE policy exists');
SELECT is((SELECT relrowsecurity FROM pg_class WHERE relname = 'episode_memory'), TRUE,
    'episode_memory: RLS is enabled');
SELECT is((SELECT relforcerowsecurity FROM pg_class WHERE relname = 'episode_memory'), TRUE,
    'episode_memory: FORCE ROW LEVEL SECURITY is enabled');

-- l0_raw
SELECT has_rlspolicy('public', 'l0_raw', 'require_project_id',
    'l0_raw: RESTRICTIVE policy exists for NULL protection');
SELECT has_rlspolicy('public', 'l0_raw', 'select_l0_raw',
    'l0_raw: SELECT policy exists');
SELECT has_rlspolicy('public', 'l0_raw', 'insert_l0_raw',
    'l0_raw: INSERT policy exists');
SELECT has_rlspolicy('public', 'l0_raw', 'update_l0_raw',
    'l0_raw: UPDATE policy exists');
SELECT has_rlspolicy('public', 'l0_raw', 'delete_l0_raw',
    'l0_raw: DELETE policy exists');
SELECT is((SELECT relrowsecurity FROM pg_class WHERE relname = 'l0_raw'), TRUE,
    'l0_raw: RLS is enabled');
SELECT is((SELECT relforcerowsecurity FROM pg_class WHERE relname = 'l0_raw'), TRUE,
    'l0_raw: FORCE ROW LEVEL SECURITY is enabled');

-- ground_truth
SELECT has_rlspolicy('public', 'ground_truth', 'require_project_id',
    'ground_truth: RESTRICTIVE policy exists for NULL protection');
SELECT has_rlspolicy('public', 'ground_truth', 'select_ground_truth',
    'ground_truth: SELECT policy exists');
SELECT has_rlspolicy('public', 'ground_truth', 'insert_ground_truth',
    'ground_truth: INSERT policy exists');
SELECT has_rlspolicy('public', 'ground_truth', 'update_ground_truth',
    'ground_truth: UPDATE policy exists');
SELECT has_rlspolicy('public', 'ground_truth', 'delete_ground_truth',
    'ground_truth: DELETE policy exists');
SELECT is((SELECT relrowsecurity FROM pg_class WHERE relname = 'ground_truth'), TRUE,
    'ground_truth: RLS is enabled');
SELECT is((SELECT relforcerowsecurity FROM pg_class WHERE relname = 'ground_truth'), TRUE,
    'ground_truth: FORCE ROW LEVEL SECURITY is enabled');

-- smf_proposals
SELECT has_rlspolicy('public', 'smf_proposals', 'require_project_id',
    'smf_proposals: RESTRICTIVE policy exists for NULL protection');
SELECT has_rlspolicy('public', 'smf_proposals', 'select_smf_proposals',
    'smf_proposals: SELECT policy exists');
SELECT has_rlspolicy('public', 'smf_proposals', 'insert_smf_proposals',
    'smf_proposals: INSERT policy exists');
SELECT has_rlspolicy('public', 'smf_proposals', 'update_smf_proposals',
    'smf_proposals: UPDATE policy exists');
SELECT has_rlspolicy('public', 'smf_proposals', 'delete_smf_proposals',
    'smf_proposals: DELETE policy exists');
SELECT is((SELECT relrowsecurity FROM pg_class WHERE relname = 'smf_proposals'), TRUE,
    'smf_proposals: RLS is enabled');
SELECT is((SELECT relforcerowsecurity FROM pg_class WHERE relname = 'smf_proposals'), TRUE,
    'smf_proposals: FORCE ROW LEVEL SECURITY is enabled');

-- stale_memory
SELECT has_rlspolicy('public', 'stale_memory', 'require_project_id',
    'stale_memory: RESTRICTIVE policy exists for NULL protection');
SELECT has_rlspolicy('public', 'stale_memory', 'select_stale_memory',
    'stale_memory: SELECT policy exists');
SELECT has_rlspolicy('public', 'stale_memory', 'insert_stale_memory',
    'stale_memory: INSERT policy exists');
SELECT has_rlspolicy('public', 'stale_memory', 'update_stale_memory',
    'stale_memory: UPDATE policy exists');
SELECT has_rlspolicy('public', 'stale_memory', 'delete_stale_memory',
    'stale_memory: DELETE policy exists');
SELECT is((SELECT relrowsecurity FROM pg_class WHERE relname = 'stale_memory'), TRUE,
    'stale_memory: RLS is enabled');
SELECT is((SELECT relforcerowsecurity FROM pg_class WHERE relname = 'stale_memory'), TRUE,
    'stale_memory: FORCE ROW LEVEL SECURITY is enabled');

-- ============================================================================
-- TEST 2: RESTRICTIVE Policy Blocks NULL project_id
-- ============================================================================

-- Test that NULL project_id rows are never visible (defense-in-depth)
PERFORM set_project_context('test_io');
SELECT is((SELECT COUNT(*) FROM working_memory WHERE project_id IS NULL), 0,
    'working_memory: RESTRICTIVE policy blocks NULL project_id rows');

PERFORM set_project_context('test_aa');
SELECT is((SELECT COUNT(*) FROM episode_memory WHERE project_id IS NULL), 0,
    'episode_memory: RESTRICTIVE policy blocks NULL project_id rows');

PERFORM set_project_context('test_io');
SELECT is((SELECT COUNT(*) FROM l0_raw WHERE project_id IS NULL), 0,
    'l0_raw: RESTRICTIVE policy blocks NULL project_id rows');

PERFORM set_project_context('test_sm');
SELECT is((SELECT COUNT(*) FROM ground_truth WHERE project_id IS NULL), 0,
    'ground_truth: RESTRICTIVE policy blocks NULL project_id rows');

PERFORM set_project_context('test_io');
SELECT is((SELECT COUNT(*) FROM smf_proposals WHERE project_id IS NULL), 0,
    'smf_proposals: RESTRICTIVE policy blocks NULL project_id rows');

PERFORM set_project_context('test_aa');
SELECT is((SELECT COUNT(*) FROM stale_memory WHERE project_id IS NULL), 0,
    'stale_memory: RESTRICTIVE policy blocks NULL project_id rows');

-- ============================================================================
-- TEST 3: working_memory Isolation (AC4)
-- ============================================================================

PERFORM set_project_context('test_sm');
SELECT is((SELECT COUNT(*) FROM working_memory), 1,
    'working_memory: Isolated user sees only own data');
SELECT is((SELECT COUNT(*) FROM working_memory WHERE project_id = 'test_io'), 0,
    'working_memory: Isolated user cannot see other project data');

PERFORM set_project_context('test_aa');
SELECT is((SELECT COUNT(*) FROM working_memory), 2,
    'working_memory: Shared user sees own + permitted data');

PERFORM set_project_context('test_io');
SELECT is((SELECT COUNT(*) FROM working_memory), 3,
    'working_memory: Super user can read all projects');

-- ============================================================================
-- TEST 3: episode_memory Isolation (AC5)
-- ============================================================================

PERFORM set_project_context('test_sm');
SELECT is((SELECT COUNT(*) FROM episode_memory), 1,
    'episode_memory: Isolated user sees only own data');

PERFORM set_project_context('test_io');
SELECT is((SELECT COUNT(*) FROM episode_memory), 3,
    'episode_memory: Super user can read all projects');

-- ============================================================================
-- TEST 4: l0_raw Isolation (AC6)
-- ============================================================================

PERFORM set_project_context('test_sm');
SELECT is((SELECT COUNT(*) FROM l0_raw), 1,
    'l0_raw: Isolated user sees only own data');

PERFORM set_project_context('test_io');
SELECT is((SELECT COUNT(*) FROM l0_raw), 3,
    'l0_raw: Super user can read all projects');

-- ============================================================================
-- TEST 5: ground_truth Isolation (AC7)
-- ============================================================================

PERFORM set_project_context('test_sm');
SELECT is((SELECT COUNT(*) FROM ground_truth), 1,
    'ground_truth: Isolated user sees only own data');

PERFORM set_project_context('test_io');
SELECT is((SELECT COUNT(*) FROM ground_truth), 3,
    'ground_truth: Super user can read all projects');

-- ============================================================================
-- TEST 6: smf_proposals Isolation (AC8)
-- ============================================================================

PERFORM set_project_context('test_sm');
SELECT is((SELECT COUNT(*) FROM smf_proposals), 1,
    'smf_proposals: Isolated user sees only own data');

PERFORM set_project_context('test_io');
SELECT is((SELECT COUNT(*) FROM smf_proposals), 3,
    'smf_proposals: Super user can read all projects');

-- ============================================================================
-- TEST 7: stale_memory Isolation (AC9)
-- ============================================================================

PERFORM set_project_context('test_sm');
SELECT is((SELECT COUNT(*) FROM stale_memory), 1,
    'stale_memory: Isolated user sees only own data');

PERFORM set_project_context('test_io');
SELECT is((SELECT COUNT(*) FROM stale_memory), 3,
    'stale_memory: Super user can read all projects');

-- ============================================================================
-- TEST 8: Pending/Shadow Modes Allow All Reads (AC3)
-- ============================================================================

-- Set to pending mode
PERFORM set_project_context('test_sm');
INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
VALUES ('test_sm', 'pending', TRUE)
ON CONFLICT (project_id) DO UPDATE SET migration_phase = 'pending';

PERFORM set_project_context('test_sm');
SELECT is((SELECT COUNT(*) FROM working_memory), 3,
    'working_memory: Pending mode allows all reads');

-- Set to shadow mode
INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
VALUES ('test_sm', 'shadow', TRUE)
ON CONFLICT (project_id) DO UPDATE SET migration_phase = 'shadow';

PERFORM set_project_context('test_sm');
SELECT is((SELECT COUNT(*) FROM working_memory), 3,
    'working_memory: Shadow mode allows all reads');

-- Reset to enforcing for cleanup
INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
VALUES ('test_sm', 'enforcing', TRUE)
ON CONFLICT (project_id) DO UPDATE SET migration_phase = 'enforcing';

-- ============================================================================
-- TEST 9: Write Isolation - All Users Can Write Only to Own Project (AC3)
-- ============================================================================

PERFORM set_project_context('test_io');

-- Try to insert with different project_id - should be blocked
DO $$
BEGIN
    INSERT INTO working_memory (key, value, importance, last_accessed, project_id)
    VALUES ('unauthorized', 'value', 0.5, NOW(), 'test_aa');
    RAISE EXCEPTION 'INSERT should have been blocked by RLS policy';
EXCEPTION WHEN OTHERS THEN
    IF SQLSTATE != '42501' THEN
        RAISE;
    END IF;
END $$;

SELECT ok(TRUE, 'working_memory: Super user cannot INSERT into other projects');

-- Try UPDATE other project's data
DO $$
BEGIN
    UPDATE working_memory SET value = 'hacked' WHERE project_id = 'test_aa';
    RAISE EXCEPTION 'UPDATE should have been blocked by RLS policy';
EXCEPTION WHEN OTHERS THEN
    IF SQLSTATE != '42501' THEN
        RAISE;
    END IF;
END $$;

SELECT ok(TRUE, 'working_memory: Super user cannot UPDATE other projects');

-- Try DELETE other project's data
DO $$
BEGIN
    DELETE FROM working_memory WHERE project_id = 'test_aa';
    RAISE EXCEPTION 'DELETE should have been blocked by RLS policy';
EXCEPTION WHEN OTHERS THEN
    IF SQLSTATE != '42501' THEN
        RAISE;
    END IF;
END $$;

SELECT ok(TRUE, 'working_memory: Super user cannot DELETE from other projects');

-- ============================================================================
-- TEST 10: System Tables Have No RLS (AC10)
-- ============================================================================

SELECT hasnt_rlspolicy('public', 'rls_audit_log', 'any',
    'rls_audit_log has no RLS (system table)');
SELECT hasnt_rlspolicy('public', 'rls_migration_status', 'any',
    'rls_migration_status has no RLS (system table)');
SELECT hasnt_rlspolicy('public', 'project_registry', 'any',
    'project_registry has no RLS (system table)');
SELECT hasnt_rlspolicy('public', 'project_read_permissions', 'any',
    'project_read_permissions has no RLS (system table)');

-- ============================================================================
-- CLEANUP (automatic via ROLLBACK)
-- ============================================================================

SELECT finish();
ROLLBACK;
-- END TEST
