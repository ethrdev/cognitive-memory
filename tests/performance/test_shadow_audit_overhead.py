"""Performance Tests for Story 11.3.2: Shadow Audit Infrastructure

Tests for performance requirements:
- AC7: DML overhead <5ms with shadow triggers
- AC7: SELECT audit overhead <10ms for 100 results

Story 11.3.2: Performance Requirements (AC: #7)
"""

import os
import time
from pathlib import Path

import asyncpg
import pytest


class TestShadowAuditPerformance:
    """Test Shadow Audit Infrastructure performance requirements."""

    @pytest.fixture
    async def test_db(self):
        """Create an asyncpg connection for testing."""
        db_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/test_cognitive_memory"
        )
        try:
            conn = await asyncpg.connect(db_url)
        except Exception as e:
            pytest.skip(f"Could not connect to database: {e}")
            return

        async with conn.transaction():
            yield conn

        await conn.close()

    @pytest.fixture
    async def setup_environment(self, test_db):
        """Set up test environment with migrations and test data."""
        migrations_dir = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations"

        # Run prerequisite migrations
        for migration_name in [
            "030_create_project_registry.sql",
            "031_create_project_read_permissions.sql",
            "032_create_rls_migration_status.sql",
            "033_seed_initial_projects.sql",
            "034_rls_helper_functions.sql",
            "035_shadow_audit_infrastructure.sql",
        ]:
            migration_path = migrations_dir / migration_name
            if migration_path.exists():
                await test_db.execute(migration_path.read_text())

        # Create test tables
        await test_db.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) UNIQUE NOT NULL,
                label VARCHAR(100),
                properties JSONB DEFAULT '{}',
                project_id VARCHAR(50),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

    # =========================================================================
    # AC7: DML Overhead <5ms with Shadow Triggers
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_dml_overhead_with_shadow_triggers(self, test_db, setup_environment) -> None:
        """PERFORMANCE: Verify DML overhead <5ms with shadow triggers (AC7)

        GIVEN project 'aa' is in shadow mode
        WHEN 100 INSERT operations are performed
        THEN average overhead <5ms per operation
        """
        # Set aa to shadow mode
        await test_db.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ($1, 'shadow')
            ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
        """, "aa")

        await test_db.execute("SELECT set_project_context($1)", "aa")

        # Measure DML performance
        times = []
        for i in range(100):
            start = time.perf_counter()
            await test_db.execute("""
                INSERT INTO nodes (name, label, project_id)
                VALUES ($1, $2, $3)
            """, f"test_node_{i}", "Test", "aa")
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to ms

        avg_time = sum(times) / len(times)
        max_time = max(times)

        # Verify performance requirement
        assert avg_time < 5.0, f"Average DML time {avg_time:.2f}ms exceeds 5ms requirement"

    @pytest.mark.P0
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_dml_overhead_comparison_with_without_triggers(self, test_db, setup_environment) -> None:
        """PERFORMANCE: Compare DML overhead with/without shadow triggers (AC7)

        GIVEN shadow triggers may or may not be active
        WHEN comparing DML performance with vs without triggers
        THEN overhead is measurable and acceptable (<5ms)
        """
        # Test without shadow mode (triggers inactive)
        await test_db.execute("SELECT set_project_context($1)", "aa")

        times_without = []
        for i in range(50):
            start = time.perf_counter()
            await test_db.execute("""
                INSERT INTO nodes (name, label, project_id)
                VALUES ($1, $2, $3)
            """, f"test_no_trigger_{i}", "Test", "aa")
            end = time.perf_counter()
            times_without.append((end - start) * 1000)

        # Set shadow mode (triggers active)
        await test_db.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ($1, 'shadow')
            ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
        """, "aa")

        await test_db.execute("SELECT set_project_context($1)", "aa")

        times_with = []
        for i in range(50):
            start = time.perf_counter()
            await test_db.execute("""
                INSERT INTO nodes (name, label, project_id)
                VALUES ($1, $2, $3)
            """, f"test_with_trigger_{i}", "Test", "aa")
            end = time.perf_counter()
            times_with.append((end - start) * 1000)

        avg_without = sum(times_without) / len(times_without)
        avg_with = sum(times_with) / len(times_with)
        overhead = avg_with - avg_without

        # Verify overhead is acceptable
        assert overhead < 5.0, f"Shadow trigger overhead {overhead:.2f}ms exceeds 5ms requirement"

    # =========================================================================
    # AC7: SELECT Audit Overhead <10ms for 100 Results
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_select_audit_overhead_100_results(self, test_db, setup_environment) -> None:
        """PERFORMANCE: Verify SELECT audit overhead <10ms for 100 results (AC7)

        GIVEN ShadowAuditLogger analyzes 100 results
        WHEN log_select_violations is called
        THEN analysis overhead <10ms
        """
        from mcp_server.audit.shadow_logger import ShadowAuditLogger

        # Set shadow mode
        await test_db.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ($1, 'shadow')
            ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
        """, "aa")
        await test_db.execute("SELECT set_project_context($1)", "aa")

        # Create test results (100 rows, mix of same and cross-project)
        results = []
        for i in range(100):
            if i % 3 == 0:  # Every 3rd result is cross-project
                results.append({
                    "id": i,
                    "project_id": "io",
                    "name": f"cross_project_{i}",
                })
            else:
                results.append({
                    "id": i,
                    "project_id": "aa",
                    "name": f"same_project_{i}",
                })

        # Measure detection performance
        logger = ShadowAuditLogger()
        start = time.perf_counter()
        violations = logger._detect_cross_project_violations(results, "aa")
        end = time.perf_counter()

        detection_time_ms = (end - start) * 1000

        # Verify detection worked correctly
        assert len(violations) == 34  # Approximately 1/3 of 100

        # Verify performance requirement
        assert detection_time_ms < 10.0, \
            f"SELECT audit detection time {detection_time_ms:.2f}ms exceeds 10ms requirement"

    @pytest.mark.P0
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_select_audit_overhead_violations_only(self, test_db, setup_environment) -> None:
        """PERFORMANCE: Verify SELECT audit handles all-violations case efficiently (AC7)

        GIVEN ShadowAuditLogger analyzes 100 results (all violations)
        WHEN log_select_violations is called
        THEN overhead <10ms even when all results are violations
        """
        from mcp_server.audit.shadow_logger import ShadowAuditLogger

        # Create test results (all cross-project violations)
        results = [
            {
                "id": i,
                "project_id": "io",
                "name": f"violation_{i}",
            }
            for i in range(100)
        ]

        # Measure detection performance
        logger = ShadowAuditLogger()
        start = time.perf_counter()
        violations = logger._detect_cross_project_violations(results, "aa")
        end = time.perf_counter()

        detection_time_ms = (end - start) * 1000

        # Verify detection worked correctly
        assert len(violations) == 100  # All should be violations

        # Verify performance requirement
        assert detection_time_ms < 10.0, \
            f"SELECT audit detection time {detection_time_ms:.2f}ms exceeds 10ms requirement (all violations)"

    # =========================================================================
    # Additional Performance Tests
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_brin_index_performance_time_range_query(self, test_db, setup_environment) -> None:
        """PERFORMANCE: Verify BRIN index enables fast time-range filtering (AC6)

        GIVEN rls_audit_log has many entries
        WHEN querying with time range filter
        THEN BRIN index provides efficient filtering
        """
        # Set shadow mode and create audit logs
        await test_db.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ($1, 'shadow')
            ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
        """, "aa")
        await test_db.execute("SELECT set_project_context($1)", "aa")

        # Create test table and trigger
        await test_db.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_id UUID NOT NULL,
                target_id UUID NOT NULL,
                relation VARCHAR(100),
                project_id VARCHAR(50),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Create triggers
        await test_db.execute("""
            CREATE TRIGGER tr_edges_shadow_audit
            AFTER INSERT OR UPDATE OR DELETE ON edges
            FOR EACH ROW EXECUTE FUNCTION shadow_audit_trigger();
        """)

        # Generate audit logs (100 cross-project operations)
        for i in range(100):
            await test_db.execute("""
                INSERT INTO edges (source_id, target_id, relation, project_id)
                VALUES (gen_random_uuid(), gen_random_uuid(), $1, $2)
            """, f"rel_{i}", "io")  # Different project

        # Measure query performance with time filter
        start = time.perf_counter()
        result = await test_db.fetch("""
            SELECT COUNT(*) as count
            FROM rls_audit_log
            WHERE logged_at > NOW() - INTERVAL '1 hour'
            AND would_be_denied = TRUE
        """)
        end = time.perf_counter()

        query_time_ms = (end - start) * 1000

        # Verify query returned results
        # fetch() returns a list of Records, so access first element
        assert result[0]['count'] > 0, "Should find audit log entries"

        # Verify efficient query (BRIN index helps)
        # Note: This is a soft check - exact timing depends on hardware
        assert query_time_ms < 100, \
            f"Time-range query took {query_time_ms:.2f}ms - BRIN index should be efficient"
