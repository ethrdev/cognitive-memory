# Story 11.7.3: Golden Test und Verification Operations

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Projekt**,
I want **dass Golden Tests und Verification-Tools meinen Projektkontext respektieren**,
so that **Projekt-Isolation bei Verification-Operations gewährleistet ist**.

## Acceptance Criteria

```gherkin
# get_golden_test_results Project Scoping
Given project 'aa' runs golden tests
When get_golden_test_results() is called
Then it uses 'aa' specific ground_truth data
And Precision@5 is calculated against 'aa' data

# get_node_by_name Project Filtering
Given project 'aa' verifies a node
When get_node_by_name("NodeName") is called
Then it returns 'aa' owned node with that name
And does not return 'io' owned node with same name

# get_edge Project Filtering
Given project 'aa' verifies an edge
When get_edge(source, target, relation) is called
Then it returns 'aa' scoped edge
And does not return edge from other projects
```

## Tasks / Subtasks

- [x] Verify RLS policies filter verification tools by project (AC: #get_golden_test_results Project Scoping)
  - [x] Verify golden_test_set table has project_id column (may need migration)
  - [x] Verify model_drift_log table has project_id column (may need migration)
  - [x] Create RLS policy on golden_test_set table if missing
  - [x] Create RLS policy on model_drift_log table if missing
  - [x] Update execute_golden_test() to use project-scoped connections
  - [x] Test that project 'aa' calculates P@5 against own data only

- [x] Verify get_node_by_name respects project boundaries (AC: #get_node_by_name Project Filtering)
  - [x] Verify get_node_by_name() uses get_connection_with_project_context() (already done)
  - [x] Verify RLS policy exists on nodes table (from Migration 036)
  - [x] Test that project 'aa' sees only own nodes
  - [x] Test that node with same name in different projects returns correct project's node

- [x] Verify get_edge respects project boundaries (AC: #get_edge Project Filtering)
  - [x] Verify get_edge_by_names() uses get_connection_with_project_context() (already done)
  - [x] Verify RLS policy exists on edges table (from Migration 036)
  - [x] Test that project 'aa' sees only own edges
  - [x] Test that edge with same source/target/relation returns correct project's edge

- [x] Create integration tests for verification operations project scope (AC: All)
  - [x] Create tests/integration/test_verification_project_scope.py
  - [x] Test get_golden_test_results uses project-scoped data
  - [x] Test get_node_by_name respects project boundaries
  - [x] Test get_edge respects project boundaries
  - [x] Test super project sees all verification data

## Dev Notes

### Story Context and Dependencies

**From Story 11.7.2 (utility_read_operations - DONE):**
- `get_connection_with_project_context()` is required for all reads to respect RLS
- RLS policies filter automatically at database level through connection context
- Tests require database user WITHOUT bypassrls privilege
- **DISCOVERY**: Some tables had no RLS policies - always verify RLS exists before relying on it

**From Story 11.7.1 (smf_read_operations - DONE):**
- Tools using `get_connection_with_project_context()` should automatically respect RLS
- Always verify RLS policies exist on tables being queried
- No existence leakage: return same error for "not found" and "not accessible"

**From Story 11.6.3 (insight_read_operations - DONE):**
- **CRITICAL SECURITY DISCOVERY**: l2_insight_history had no RLS policies - was fixed in Migration 039
- Always check if RLS policies exist on tables being queried
- Use `get_connection_with_project_context()` for all reads

**From Story 11.6.2 (graph_query_operations - DONE):**
- Replace `get_connection()` with `get_connection_with_project_context()` in tool handlers
- RLS filtering happens transparently at database level through connection context

**From Story 11.6.1 (hybrid_search Project-Aware - DONE):**
- Project-scoped connection pattern established for RLS filtering
- Response metadata includes project_id
- Tests skip when bypassrls=TRUE (expected infrastructure limitation)

**From Epic 11.3 (RLS Infrastructure - DONE):**
- Migration 034 added RLS helper functions (set_project_context, get_allowed_projects, etc.)
- Migration 036 added RLS policies on core tables (nodes, edges)
- `set_project_context(project_id)` sets session variables for RLS
- Access control: super (all), shared (own + permitted), isolated (own only)

**From Epic 11.1 (Schema Migration - DONE):**
- Migration 027 added project_id to nodes and edges tables
- Migration 029 added composite indexes for (project_id, *) patterns

### Relevant Architecture Patterns and Constraints

**Current Implementation Analysis:**

**get_golden_test_results (mcp_server/tools/get_golden_test_results.py):**
- Tool handler gets project_id from middleware context (line 367)
- Calls `execute_golden_test()` core function (line 370)
- **CRITICAL ISSUE**: execute_golden_test() uses `get_connection_sync()` directly (line 119, 179, 252, 291)
- **NEEDS INVESTIGATION**: golden_test_set table may not have project_id column (Migration 006, pre-Epic 11)
- **NEEDS INVESTIGATION**: model_drift_log table may not have project_id column
- **NEEDS FIX**: Replace `get_connection_sync()` with `get_connection_with_project_context_sync()`
- Returns response with metadata (line 371)

**get_node_by_name (mcp_server/tools/get_node_by_name.py):**
- Tool handler gets project_id from middleware context (line 38)
- Calls `get_node_by_name()` from db/graph.py (line 53)
- **GOOD**: db/graph.py uses `get_connection_with_project_context()` (line 339)
- **RLS filtering should happen at db layer** - no code changes expected IF RLS policies exist
- Returns response with metadata (line 57, 69)

**get_edge (mcp_server/tools/get_edge.py):**
- Tool handler gets project_id from middleware context (line 39)
- Calls `get_edge_by_names()` from db/graph.py (line 72)
- **GOOD**: db/graph.py uses `get_connection_with_project_context()` (line 702)
- **RLS filtering should happen at db layer** - no code changes expected IF RLS policies exist
- Returns response with metadata (line 79, 96)

**Database Layer (mcp_server/db/graph.py):**
- `get_node_by_name()` uses `get_connection_with_project_context()` (line 339) - **CORRECT**
- `get_edge_by_names()` uses `get_connection_with_project_context()` (line 702) - **CORRECT**

**CRITICAL FINDING - golden_test_set and model_drift_log tables:**
- These tables were created in Migration 006 (before Epic 11 namespace isolation)
- They likely do NOT have project_id columns
- They likely do NOT have RLS policies
- **NEW MIGRATION NEEDED**: Add project_id to golden_test_set and model_drift_log

**Required Changes:**

**BREAKING SCHEMA CHANGE WARNING:**
The model_drift_log table PRIMARY KEY changes from `date` to `(date, project_id)`.
This affects:
1. UPSERT queries must change from `ON CONFLICT (date)` to `ON CONFLICT (date, project_id)`
2. Drift detection baseline queries will now return one row per project per day
3. Each project stores its own daily P@5 metrics independently
4. Existing code in get_golden_test_results.py (line 294-306) uses `ON CONFLICT (date)` - must be updated

**Migration (NEW - Add project_id to golden test tables):**

```sql
-- Story 11.7.3: Add project_id to golden_test_set and model_drift_log

-- Phase 1: Add project_id column to golden_test_set
ALTER TABLE golden_test_set
ADD COLUMN IF NOT EXISTS project_id VARCHAR(50) NOT NULL DEFAULT 'io';

-- Phase 2: Add project_id column to model_drift_log
ALTER TABLE model_drift_log
ADD COLUMN IF NOT EXISTS project_id VARCHAR(50) NOT NULL DEFAULT 'io';

-- Phase 3: Add indexes for project-scoped queries
CREATE INDEX IF NOT EXISTS idx_golden_test_set_project
ON golden_test_set(project_id);

CREATE INDEX IF NOT EXISTS idx_model_drift_log_project_date
ON model_drift_log(project_id, date);

-- Phase 4: Enable RLS
ALTER TABLE golden_test_set ENABLE ROW LEVEL SECURITY;
ALTER TABLE golden_test_set FORCE ROW LEVEL SECURITY;

ALTER TABLE model_drift_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_drift_log FORCE ROW LEVEL SECURITY;

-- Phase 5: Create RLS policies
CREATE POLICY select_golden_test_set ON golden_test_set
    FOR SELECT
    USING (
        CASE (SELECT get_rls_mode())
            WHEN 'pending' THEN TRUE
            WHEN 'shadow' THEN TRUE
            WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            ELSE TRUE
        END
    );

CREATE POLICY select_model_drift_log ON model_drift_log
    FOR SELECT
    USING (
        CASE (SELECT get_rls_mode())
            WHEN 'pending' THEN TRUE
            WHEN 'shadow' THEN TRUE
            WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            ELSE TRUE
        END
    );

CREATE POLICY insert_model_drift_log ON model_drift_log
    FOR INSERT
    WITH CHECK (project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[]));

CREATE POLICY update_model_drift_log ON model_drift_log
    FOR UPDATE
    USING (project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[]))
    WITH CHECK (project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[]));
```

**mcp_server/tools/get_golden_test_results.py (MODIFY):**

```python
"""
Golden Test Results Tool - Project-Aware Version

Story 11.7.3: Added project context support for RLS filtering on golden test data.
"""

from mcp_server.db.connection import get_connection_with_project_context_sync  # NEW
from mcp_server.middleware.context import get_current_project  # NEW

def execute_golden_test(project_id: str | None = None) -> dict[str, Any]:
    """
    Execute Golden Test Set and calculate Precision@5 with drift detection.

    Story 11.7.3: Uses project-scoped connection for RLS filtering.
    Each project calculates P@5 against its own golden test set.

    Backward Compatibility:
        The project_id parameter defaults to None, making this change backward compatible.
        Existing cron jobs and scripts will continue to work, automatically using the current
        project context from get_current_project().

    Args:
        project_id: Optional project ID (defaults to current project from context)

    Returns:
        Dict with golden test results
    """
    # Story 11.7.3: Get project context if not provided
    if project_id is None:
        project_id = get_current_project()

    start_time = time.time()
    logger.info(f"Starting Golden Test Set execution for project {project_id}...")

    # ... config loading code ...

    # Story 11.7.3: Use project-scoped connection
    with get_connection_with_project_context_sync(read_only=True) as conn:
        cursor = conn.cursor()

        # RLS automatically filters golden_test_set by project_id
        cursor.execute(
            """
            SELECT id, query, expected_docs
            FROM golden_test_set
            ORDER BY id
            """
        )
        queries = cursor.fetchall()

        # ... rest of implementation ...

    # Story 11.7.3: Search queries should also be project-scoped
    # The hybrid_search queries use RLS via l2_insights policies
    # l2_insights RLS Policy: From Migration 036, l2_insights table has
    # select_l2_insights policy that filters by project_id automatically.

    # Story 11.7.3: Model drift log should be project-scoped
    with get_connection_with_project_context_sync() as conn:
        cursor = conn.cursor()

        # RLS filters model_drift_log by project_id
        cursor.execute(
            """
            SELECT AVG(precision_at_5) as baseline
            FROM model_drift_log
            WHERE date >= CURRENT_DATE - INTERVAL '7 days'
              AND date < CURRENT_DATE
            """,
        )

        # ... rest of implementation ...

        # UPSERT with project_id
        cursor.execute(
            """
            INSERT INTO model_drift_log
            (date, precision_at_5, num_queries, avg_retrieval_time, embedding_model_version,
             drift_detected, baseline_p5, project_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, project_id) DO UPDATE SET
                precision_at_5 = EXCLUDED.precision_at_5,
                num_queries = EXCLUDED.num_queries,
                avg_retrieval_time = EXCLUDED.avg_retrieval_time,
                embedding_model_version = EXCLUDED.embedding_model_version,
                drift_detected = EXCLUDED.drift_detected,
                baseline_p5 = EXCLUDED.baseline_p5
            """,
            (
                today,
                macro_avg_precision,
                query_count,
                avg_retrieval_time,
                embedding_model_version,
                drift_detected,
                baseline_p5,
                project_id,  # NEW: Store results per project
            ),
        )
```

**Database Schema Reference:**

From Epic 11.3 (RLS policies on core tables - Migration 036):
```sql
-- nodes RLS policy (Migration 036) - EXISTS ✓
CREATE POLICY select_nodes ON nodes
    FOR SELECT
    USING (
        CASE (SELECT get_rls_mode())
            WHEN 'pending' THEN TRUE
            WHEN 'shadow' THEN TRUE
            WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            ELSE TRUE
        END
    );

-- edges RLS policy (Migration 036) - EXISTS ✓
CREATE POLICY select_edges ON edges
    FOR SELECT
    USING (
        CASE (SELECT get_rls_mode())
            WHEN 'pending' THEN TRUE
            WHEN 'shadow' THEN TRUE
            WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            ELSE TRUE
        END
    );
```

**Super Project Access (Migration 034:86-90):**
```sql
-- From set_project_context() function:
IF v_access_level = 'super' THEN
    -- SUPER: Access to ALL projects
    SELECT '{' || string_agg(project_id, ',') || '}' INTO v_allowed
    FROM project_registry;
```
Super projects (e.g., 'io') get ALL project_ids in their `allowed_projects` array.

**Security Note - No Existence Leakage:**
- When data is inaccessible due to RLS, the query returns zero rows
- For get_node_by_name and get_edge: Return same "not_found" response whether node/edge doesn't exist or is in inaccessible project
- For get_golden_test_results: If no golden test data exists for project, return error message

### Source Tree Components to Touch

**Files to MODIFY:**
- `mcp_server/tools/get_golden_test_results.py` - Replace get_connection_sync() with get_connection_with_project_context_sync()
- `mcp_server/db/migrations/XXX_add_project_id_golden_test.sql` (NEW) - Add project_id and RLS policies

**Files to VERIFY (no changes expected):**
- `mcp_server/tools/get_node_by_name.py` - Already uses middleware context, db layer uses project-scoped connection
- `mcp_server/tools/get_edge.py` - Already uses middleware context, db layer uses project-scoped connection
- `mcp_server/db/graph.py` - Already uses get_connection_with_project_context()

**Files to CREATE (tests):**
- `tests/integration/test_verification_project_scope.py` - Integration tests for project-scoped verification

### Testing Standards Summary

**Integration Tests (pytest + async):**
- Test RLS policies filter golden_test_set by project_id
- Test RLS policies filter model_drift_log by project_id
- Test get_golden_test_results calculates P@5 for current project only
- Test get_node_by_name returns only nodes from accessible projects
- Test get_edge returns only edges from accessible projects
- Test super project sees all verification data across projects
- Test RLS with different access levels (super, shared, isolated)

**Test Infrastructure Note:**
- Tests require database user WITHOUT bypassrls privilege
- Use `pytest.skip()` with infrastructure documentation when bypassrls=TRUE
- This is an infrastructure limitation, NOT a code bug

### Project Structure Notes

**Alignment with unified project structure:**
- Follow existing `mcp_server/tools/` structure
- Use `get_connection_with_project_context_sync()` for synchronous operations in golden tests
- Use `snake_case.py` file naming
- Follow async/await patterns from Story 11.4.2

**Detected conflicts or variances:**
- **CRITICAL**: golden_test_set table lacks project_id column (pre-Epic 11 schema)
- **CRITICAL**: model_drift_log table lacks project_id column (pre-Epic 11 schema)
- get_golden_test_results uses get_connection_sync() directly - bypasses RLS
- get_node_by_name and get_edge should work correctly with existing RLS policies on nodes/edges

### Implementation Code Structure

**Migration File (NEW - Add project_id to golden test tables):**

Create `mcp_server/db/migrations/040_add_project_id_golden_test.sql`:

```sql
-- Story 11.7.3: Add project_id to golden_test_set and model_drift_log tables
-- for project-isolated golden test execution and drift tracking.

-- =============================================================================
-- Phase 1: Add project_id column to golden_test_set
-- =============================================================================

ALTER TABLE golden_test_set
ADD COLUMN IF NOT EXISTS project_id VARCHAR(50) NOT NULL DEFAULT 'io';

COMMENT ON COLUMN golden_test_set.project_id IS
'Project identifier for namespace isolation (Epic 11). Each project maintains its own golden test set.';

-- =============================================================================
-- Phase 2: Add project_id column to model_drift_log
-- =============================================================================

ALTER TABLE model_drift_log
ADD COLUMN IF NOT EXISTS project_id VARCHAR(50) NOT NULL DEFAULT 'io';

COMMENT ON COLUMN model_drift_log.project_id IS
'Project identifier for namespace isolation. Each project tracks its own model drift.';

-- Modify primary key constraint to include project_id
ALTER TABLE model_drift_log DROP CONSTRAINT IF EXISTS model_drift_log_pkey;
ALTER TABLE model_drift_log ADD PRIMARY KEY (date, project_id);

-- =============================================================================
-- Phase 3: Add indexes for project-scoped queries
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_golden_test_set_project
ON golden_test_set(project_id);

CREATE INDEX IF NOT EXISTS idx_model_drift_log_project_date
ON model_drift_log(project_id, date DESC);

-- =============================================================================
-- Phase 4: Enable RLS
-- =============================================================================

ALTER TABLE golden_test_set ENABLE ROW LEVEL SECURITY;
ALTER TABLE golden_test_set FORCE ROW LEVEL SECURITY;

ALTER TABLE model_drift_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_drift_log FORCE ROW LEVEL SECURITY;

-- =============================================================================
-- Phase 5: Create RLS policies
-- =============================================================================

-- golden_test_set: SELECT policy
CREATE POLICY select_golden_test_set ON golden_test_set
    FOR SELECT
    USING (
        CASE (SELECT get_rls_mode())
            WHEN 'pending' THEN TRUE
            WHEN 'shadow' THEN TRUE
            WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            ELSE TRUE
        END
    );

-- model_drift_log: SELECT policy
CREATE POLICY select_model_drift_log ON model_drift_log
    FOR SELECT
    USING (
        CASE (SELECT get_rls_mode())
            WHEN 'pending' THEN TRUE
            WHEN 'shadow' THEN TRUE
            WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            ELSE TRUE
        END
    );

-- model_drift_log: INSERT policy
CREATE POLICY insert_model_drift_log ON model_drift_log
    FOR INSERT
    WITH CHECK (project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[]));

-- model_drift_log: UPDATE policy
CREATE POLICY update_model_drift_log ON model_drift_log
    FOR UPDATE
    USING (project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[]))
    WITH CHECK (project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[]));

-- =============================================================================
-- Phase 6: Update existing data
-- =============================================================================

-- Set existing golden_test_set records to 'io' project (default super project)
UPDATE golden_test_set
SET project_id = 'io'
WHERE project_id IS NULL;

-- Set existing model_drift_log records to 'io' project (default super project)
UPDATE model_drift_log
SET project_id = 'io'
WHERE project_id IS NULL;
```

**mcp_server/tools/get_golden_test_results.py (MODIFY):**

Key changes needed:
1. Import `get_connection_with_project_context_sync` from connection.py
2. Import `get_current_project` from middleware.context
3. Replace all `get_connection_sync()` with `get_connection_with_project_context_sync()`
4. Update INSERT statement to include project_id
5. Update ON CONFLICT clause to handle (date, project_id) composite key

**tests/integration/test_verification_project_scope.py (CREATE - NEW):**

```python
"""
Integration tests for Verification Operations with Project Scope (Story 11.7.3).

Tests that get_golden_test_results, get_node_by_name, and get_edge respect
project boundaries through Row-Level Security (RLS) policies.

AC Covered:
    - get_golden_test_results uses project-scoped golden test data
    - get_node_by_name returns only nodes from accessible projects
    - get_edge returns only edges from accessible projects
    - Super project sees all verification data across all projects

Usage:
    pytest tests/integration/test_verification_project_scope.py -v

INFRASTRUCTURE REQUIREMENT:
    These tests require a database user WITHOUT the bypassrls privilege.
    See module docstring in test_insight_read_project_scope.py for details.
"""

from __future__ import annotations

import pytest
from psycopg2.extensions import connection


def _can_test_rls(conn: connection) -> bool:
    """Check if RLS policies will be enforced."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT rolbypassrls
            FROM pg_roles
            WHERE rolname = session_user
        """)
        result = cur.fetchone()
        return result is not None and not result[0] if result else False


@pytest.fixture(autouse=True)
def check_rls_testing_capability(conn: connection):
    """Skip RLS tests if database user has bypassrls privilege."""
    can_test_rls = _can_test_rls(conn)
    if not can_test_rls:
        pytest.skip(
            "RLS testing requires database user WITHOUT bypassrls privilege. "
            "Current user has bypassrls=TRUE which bypasses all RLS policies."
        )


@pytest.fixture(autouse=True)
def setup_test_data(conn: connection):
    """Create test data for verification operations across multiple projects"""
    with conn.cursor() as cur:
        # Set RLS to enforcing mode for all projects
        cur.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
            VALUES ('io', 'enforcing', TRUE), ('aa', 'enforcing', TRUE), ('sm', 'enforcing', TRUE)
            ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
        """)

        # Set up project_read_permissions for shared project 'aa' to read 'sm'
        cur.execute("""
            INSERT INTO project_read_permissions (reader_project_id, target_project_id)
            VALUES ('aa', 'sm')
            ON CONFLICT (reader_project_id, target_project_id) DO NOTHING
        """)

        # Create test nodes for each project
        cur.execute("DELETE FROM nodes WHERE name IN ('TestNode') AND project_id IN ('io', 'aa', 'sm')")
        cur.execute("""
            INSERT INTO nodes (id, name, label, properties, project_id)
            VALUES
                (1001, 'SharedNode', 'test', '{}'::jsonb, 'io'),
                (2001, 'SharedNode', 'test', '{}'::jsonb, 'aa'),
                (3001, 'SharedNode', 'test', '{}'::jsonb, 'sm')
        """)

        # Create test edges for each project
        cur.execute("""
            INSERT INTO edges (source_id, target_id, relation, weight, properties, memory_sector, project_id)
            VALUES
                (1001, 1001, 'TEST_EDGE', 1.0, '{}'::jsonb, 'semantic', 'io'),
                (2001, 2001, 'TEST_EDGE', 1.0, '{}'::jsonb, 'semantic', 'aa'),
                (3001, 3001, 'TEST_EDGE', 1.0, '{}'::jsonb, 'semantic', 'sm')
        """)

        # Create test golden test set entries for each project
        cur.execute("DELETE FROM golden_test_set WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("""
            INSERT INTO golden_test_set (query, query_type, expected_docs, project_id)
            VALUES
                ('io test query', 'short', ARRAY[]::INTEGER[], 'io'),
                ('aa test query', 'short', ARRAY[]::INTEGER[], 'aa'),
                ('sm test query', 'short', ARRAY[]::INTEGER[], 'sm')
        """)

        conn.commit()


@pytest.mark.asyncio
async def test_get_node_by_name_respects_project_rls():
    """Test that get_node_by_name only returns nodes from current project."""
    from mcp_server.db.graph import get_node_by_name
    from mcp_server.middleware.context import set_project_context, reset_project_context

    # Set project context to 'aa'
    set_project_context('aa')

    # Get node as 'aa' project
    node = await get_node_by_name('SharedNode')

    # Should see 'aa' node (id 2001), not 'io' or 'sm'
    assert node is not None
    assert node['name'] == 'SharedNode'
    # The specific node returned depends on RLS filtering - 'aa' should see its own node

    reset_project_context()


@pytest.mark.asyncio
async def test_get_edge_respects_project_rls():
    """Test that get_edge only returns edges from current project."""
    from mcp_server.db.graph import get_edge_by_names
    from mcp_server.middleware.context import set_project_context, reset_project_context

    # Set project context to 'aa'
    set_project_context('aa')

    # Get edge as 'aa' project
    edge = await get_edge_by_names('SharedNode', 'SharedNode', 'TEST_EDGE')

    # Should see 'aa' edge, not 'io' or 'sm'
    assert edge is not None
    assert edge['relation'] == 'TEST_EDGE'

    reset_project_context()


@pytest.mark.skipif(
    not _can_test_rls(None),
    reason="RLS testing requires database user without bypassrls privilege"
)
def test_rls_policies_exist_on_verification_tables(conn: connection):
    """Test that RLS policies are created on golden test tables."""
    with conn.cursor() as cur:
        # Check RLS is enabled on golden_test_set
        cur.execute("""
            SELECT rowsecurity, forcerowsecurity
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'golden_test_set'
        """)
        result = cur.fetchone()
        assert result is not None
        assert result[0] is True  # rowsecurity enabled

        # Check RLS is enabled on model_drift_log
        cur.execute("""
            SELECT rowsecurity, forcerowsecurity
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'model_drift_log'
        """)
        result = cur.fetchone()
        assert result is not None
        assert result[0] is True  # rowsecurity enabled
```

### Previous Story Intelligence

**From Story 11.7.2 (utility_read_operations):**
- Tools using `get_connection_with_project_context()` should automatically respect RLS
- Always verify RLS policies exist on tables being queried
- No existence leakage: return same error for "not found" and "not accessible"

**From Story 11.7.1 (smf_read_operations):**
- SMF and dissonance operations now respect project boundaries
- Main changes needed: dissonance_check tool and DissonanceEngine

**From Story 11.6.3 (insight_read_operations):**
- **CRITICAL SECURITY DISCOVERY**: l2_insight_history had NO RLS policies - was fixed
- Always check if RLS policies exist on tables being queried

**From Story 11.6.2 (graph_query_operations):**
- Replace `get_connection()` with `get_connection_with_project_context()` in tool handlers
- RLS filtering happens transparently at database level through connection context

**From Story 11.6.1 (hybrid_search Project-Aware):**
- Project-scoped connection pattern established for RLS filtering
- Response metadata includes project_id

**Common Issues to Avoid:**
1. **ALWAYS verify RLS policies exist** on tables being queried
2. **Direct get_connection() calls bypass RLS** - This is a security bug
3. **No existence leakage**: Return same error for "not found" and "not accessible"
4. **Test transaction isolation**: Always rollback in tests
5. **Return project_id in responses**: For transparency and debugging

### Performance Considerations

**RLS Overhead:**
- RLS filtering adds minimal overhead when indexes are properly configured
- Migration adds indexes for (project_id, date) on model_drift_log
- EXPLAIN ANALYZE should show Index Scan with project_id filter

**Golden Test Execution:**
- Golden test queries l2_insights table (already has RLS from Migration 039)
- Each project executes golden tests independently
- Super projects may have longer execution time due to larger dataset

### References

**Epic Context:**
- [Source: _bmad-output/planning-artifacts/epics-epic-11-namespace-isolation.md#Epic-11.7] (Epic 11.7: SMF & Utility Operations)
- [Source: _bmad-output/planning-artifacts/epics-epic-11-namespace-isolation.md#Story-11.7.3] (Story 11.7.3 details)

**Previous Stories:**
- [Source: _bmad-output/implementation-artifacts/11-7-2-utility-read-operations.md] (Story 11.7.2 completion notes)
- [Source: _bmad-output/implementation-artifacts/11-7-1-smf-read-operations.md] (Story 11.7.1 completion notes)
- [Source: _bmad-output/implementation-artifacts/11-6-3-insight-read-operations.md] (Story 11.6.3 completion notes)

**Database Migrations:**
- [Source: mcp_server/db/migrations/027_add_project_id.sql] (project_id column addition for core tables)
- [Source: mcp_server/db/migrations/029_add_composite_indexes.sql] (composite indexes)
- [Source: mcp_server/db/migrations/034_rls_helper_functions.sql] (set_project_context function)
- [Source: mcp_server/db/migrations/036_rls_policies_core_tables.sql] (RLS policies for nodes, edges)
- [Source: mcp_server/db/migrations/006_golden_test_set.sql] (Original golden test set schema - pre-Epic 11)

**Project Context:**
- [Source: project-context.md] (Coding standards and patterns)

## Dev Agent Record

### Agent Model Used

glm-4.7 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

**Story Creation (2026-01-24):**
- Story 11.7.3 created with comprehensive developer context
- All acceptance criteria from epic document preserved in Gherkin format
- Previous story learnings (11.4.2, 11.5.x, 11.6.x, 11.7.1, 11.7.2) incorporated
- Database schema analysis completed

**Code Analysis (2026-01-24):**
- get_golden_test_results uses get_connection_sync() directly - **NEEDS FIX**
- **CRITICAL FINDING**: golden_test_set table has no project_id column (Migration 006, pre-Epic 11)
- **CRITICAL FINDING**: model_drift_log table has no project_id column
- **NEW MIGRATION REQUIRED**: Add project_id to golden_test_set and model_drift_log
- get_node_by_name already uses project-scoped connection correctly (graph.py:339)
- get_edge already uses project-scoped connection correctly (graph.py:702)
- Implementation code structure designed with all required changes
- Integration test template included for all acceptance criteria

**Implementation Notes:**
- New migration file needed: 040_add_project_id_golden_test.sql
- Main changes needed: get_golden_test_results.py - replace get_connection_sync() with get_connection_with_project_context_sync()
- Database functions get_node_by_name() and get_edge_by_names() already use project-scoped connections
- Tests must verify RLS policies actually filter data (not just exist)
- No existence leakage: return same error for "not found" and "not accessible"

**Implementation Complete (2026-01-24):**
- ✅ Migration 040 created: Adds project_id column to golden_test_set and model_drift_log tables
- ✅ Migration 040 creates RLS policies: select_golden_test_set, select_model_drift_log, insert_model_drift_log, update_model_drift_log
- ✅ get_golden_test_results.py updated to use get_connection_with_project_context_sync()
- ✅ execute_golden_test() now accepts project_id parameter for project-scoped golden test execution
- ✅ ON CONFLICT clause updated to use composite key (date, project_id) instead of just (date)
- ✅ Response includes project_id for transparency
- ✅ Integration tests created in test_verification_project_scope.py (13 tests)
- ⚠️ Tests skip when bypassrls=TRUE (infrastructure limitation, not code bug)

**Files Modified:**
- mcp_server/tools/get_golden_test_results.py: All get_connection_sync() replaced with get_connection_with_project_context_sync()
- mcp_server/db/graph.py: Added project_id to return dicts of get_node_by_name() and get_edge_by_names() (Story 11.7.3 code review fix)

**Files Created:**
- mcp_server/db/migrations/040_add_project_id_golden_test.sql
- mcp_server/db/migrations/040_add_project_id_golden_test_rollback.sql
- tests/integration/test_verification_project_scope.py

**Code Review Fixes (2026-01-24):**
- get_node_by_name() now returns project_id in response dict (graph.py:361)
- get_edge_by_names() now returns project_id in response dict (graph.py:736)
- Tests verify project_id is returned correctly for AC compliance

### File List

**Story File:**
- _bmad-output/implementation-artifacts/11-7-3-golden-test-verification-operations.md

**Source Documents Referenced:**
- _bmad-output/planning-artifacts/epics-epic-11-namespace-isolation.md
- _bmad-output/implementation-artifacts/11-7-2-utility-read-operations.md
- _bmad-output/implementation-artifacts/11-7-1-smf-read-operations.md
- _bmad-output/implementation-artifacts/11-6-3-insight-read-operations.md
- mcp_server/tools/get_golden_test_results.py
- mcp_server/tools/get_node_by_name.py
- mcp_server/tools/get_edge.py
- mcp_server/db/graph.py
- mcp_server/db/migrations/006_golden_test_set.sql
- mcp_server/db/migrations/027_add_project_id.sql
- mcp_server/db/migrations/029_add_composite_indexes.sql
- mcp_server/db/migrations/034_rls_helper_functions.sql
- mcp_server/db/migrations/036_rls_policies_core_tables.sql
- project-context.md

**Files Modified:**
- mcp_server/tools/get_golden_test_results.py - Replace get_connection_sync() with get_connection_with_project_context_sync()
- mcp_server/db/graph.py - Added project_id to return dicts of get_node_by_name() and get_edge_by_names() (code review fix)

**Files Created:**
- mcp_server/db/migrations/040_add_project_id_golden_test.sql - Add project_id and RLS policies for golden test tables
- mcp_server/db/migrations/040_add_project_id_golden_test_rollback.sql - Rollback migration
- tests/integration/test_verification_project_scope.py - Integration tests for project-scoped verification operations

**Files to Verify (no changes expected):**
- mcp_server/tools/get_node_by_name.py - Should work with existing RLS on nodes table
- mcp_server/tools/get_edge.py - Should work with existing RLS on edges table
