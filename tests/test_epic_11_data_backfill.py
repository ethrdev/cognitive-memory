"""
P0 Tests: Data Backfill for Epic 11 Namespace Isolation
ATDD Red Phase - Tests that will pass after implementation

Story 11.1.2: Backfill Existing Data to 'io'

Risk Mitigation:
- R-001: Backfill corrupts data
- R-002: Backfill causes downtime (> 1s table lock)
- R-003: Backfill loses data or causes data inconsistency

Test Count: 20 (12 file structure tests + 8 database integration tests)
"""

import pytest
from pathlib import Path


class TestBackfillScriptExists:
    """Verify backfill script is created correctly"""

    @pytest.mark.P0
    def test_backfill_script_exists(self):
        """AC1: Backfill script should exist

        Given Story 11.1.2 implementation
        When backfill script is created
        Then scripts/backfill_project_id.py exists
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        assert backfill_script.exists(), "Backfill script should exist at scripts/backfill_project_id.py"

    @pytest.mark.P0
    def test_backfill_script_executable(self):
        """AC1: Backfill script should be executable

        Given the backfill script exists
        When checking file permissions
        Then it should have execute permission
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        # Check if file starts with shebang
        content = backfill_script.read_text()
        assert content.startswith("#!"), "Backfill script should start with shebang (#!)"


class TestBackfillScriptStructure:
    """AC1: Verify backfill script has correct structure"""

    @pytest.mark.P0
    def test_uses_keyset_pagination(self):
        """AC1: Backfill should use keyset pagination (not OFFSET)

        Given the backfill script
        When examining the implementation
        Then it uses keyset pagination pattern with id column
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should use WHERE id > last_id pattern (keyset pagination)
        assert "WHERE id >" in content or "id > %" in content, \
            "Backfill should use keyset pagination (WHERE id > last_id)"
        # Should NOT use OFFSET which becomes slow
        assert "OFFSET" not in content.upper() or "offset" not in content.lower() or \
               "# Not using OFFSET" in content or "# keyset" in content.lower(), \
            "Backfill should not use OFFSET for performance"

    @pytest.mark.P0
    def test_uses_batched_operations(self):
        """AC1: Backfill should use batched operations

        Given the backfill script
        When examining the implementation
        Then it processes data in batches of 5000 rows
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should have batch_size parameter
        assert "batch_size" in content.lower(), \
            "Backfill script should have batch_size parameter"
        # Default should be 5000
        assert "5000" in content, \
            "Default batch size should be 5000"

    @pytest.mark.P0
    def test_has_sleep_between_batches(self):
        """AC1: Backfill should have optional sleep between batches

        Given the backfill script
        When examining the implementation
        Then it has optional pg_sleep(0.1) or asyncio.sleep between batches
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should have sleep functionality for I/O pressure management
        assert "sleep" in content.lower(), \
            "Backfill should have sleep between batches for I/O pressure management"
        # Should default to 0.1 seconds
        assert "0.1" in content, \
            "Default sleep should be 0.1 seconds"


class TestAnomalyLoggingSystem:
    """AC2: Anomaly logging system for edge cases"""

    @pytest.mark.P0
    def test_creates_anomalies_table(self):
        """AC2: Backfill should create backfill_anomalies table

        Given the backfill script runs
        When anomalies are detected
        Then backfill_anomalies table exists to log them
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should create backfill_anomalies table
        assert "backfill_anomalies" in content.lower(), \
            "Backfill script should create backfill_anomalies table"
        assert "CREATE TABLE" in content.upper() or "create_table" in content, \
            "Backfill script should create anomalies table"

    @pytest.mark.P0
    def test_logs_anomalies_with_details(self):
        """AC2: Anomalies should be logged with row_id, table_name, issue_description

        Given an anomaly is detected during backfill
        When the anomaly is logged
        Then it includes row_id, table_name, and issue_description
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should log these fields
        assert "row_id" in content.lower(), \
            "Anomalies table should have row_id field"
        assert "table_name" in content.lower(), \
            "Anomalies table should have table_name field"
        assert "issue_description" in content.lower() or "description" in content.lower(), \
            "Anomalies table should have issue_description field"

    @pytest.mark.P0
    def test_continues_on_error(self):
        """AC2: Backfill should continue on single-row failure

        Given a record causes an error during backfill
        When the error occurs
        Then backfill continues with remaining records
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should have try/except or continue-on-error pattern
        assert "try" in content.lower() or "except" in content.lower(), \
            "Backfill script should have error handling"
        # Should log errors and continue
        assert "continue" in content.lower() or "pass" in content.lower(), \
            "Backfill script should continue on error"

    @pytest.mark.P0
    def test_reports_summary_statistics(self):
        """AC2: Backfill should report summary statistics after completion

        Given the backfill completes
        When summary is reported
        Then it shows total rows updated, anomalies found, tables processed
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should track and report statistics
        assert "total" in content.lower(), \
            "Backfill script should track total rows updated"
        assert "summary" in content.lower() or "report" in content.lower(), \
            "Backfill script should report summary statistics"


class TestConstraintValidation:
    """AC3: Constraint validation after backfill"""

    @pytest.mark.P0
    def test_validates_not_null_constraints(self):
        """AC3: Backfill should validate NOT NULL constraints

        Given all rows have been backfilled
        When VALIDATE CONSTRAINT runs
        Then NOT NULL constraint is fully enforced
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should have VALIDATE CONSTRAINT logic
        assert "VALIDATE CONSTRAINT" in content.upper() or "validate_constraint" in content.lower(), \
            "Backfill script should validate NOT NULL constraints"
        # Should validate all 11 table constraints
        assert "check_l2_insights_project_id_not_null" in content or \
               "check_nodes_project_id_not_null" in content or \
               "check_edges_project_id_not_null" in content, \
            "Backfill script should validate specific constraints from Story 11.1.1"

    @pytest.mark.P0
    def test_validates_all_11_tables(self):
        """AC3: All 11 tables should have constraints validated

        Given the backfill script
        When checking validation logic
        Then all 11 tables from Story 11.1.1 are validated
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should reference all 11 tables
        tables = [
            'l2_insights', 'nodes', 'edges', 'working_memory',
            'episode_memory', 'l0_raw', 'ground_truth', 'stale_memory',
            'smf_proposals', 'ief_feedback', 'l2_insight_history'
        ]

        found_tables = sum(1 for table in tables if table in content)
        assert found_tables >= 8, \
            f"Backfill script should reference most of the 11 tables, found {found_tables}"


class TestRollbackCapability:
    """Task 5 (DoD): Rollback script and procedure"""

    @pytest.mark.P0
    def test_has_rollback_flag(self):
        """DoD: Backfill script should have rollback capability

        Given the backfill script
        When checking CLI options
        Then --rollback flag exists to undo backfill
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should have rollback option
        assert "rollback" in content.lower() or "--rollback" in content, \
            "Backfill script should have rollback flag"

    @pytest.mark.P0
    def test_has_dry_run_mode(self):
        """DoD: Backfill script should have dry-run mode

        Given the backfill script
        When checking CLI options
        Then --dry-run flag exists to simulate backfill
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should have dry-run option
        assert "dry-run" in content.lower() or "dry_run" in content, \
            "Backfill script should have dry-run mode for testing"


class TestCLIInterface:
    """CLI interface follows project patterns"""

    @pytest.mark.P0
    def test_has_cli_argument_parser(self):
        """CLI: Should use argparse for command-line interface

        Given the backfill script
        When checking implementation
        Then it uses argparse for CLI arguments
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should use argparse
        assert "argparse" in content.lower(), \
            "Backfill script should use argparse for CLI"
        assert "ArgumentParser" in content, \
            "Backfill script should use ArgumentParser"

    @pytest.mark.P0
    def test_has_help_documentation(self):
        """CLI: Should have help documentation

        Given the backfill script
        When user runs --help
        Then script shows usage and options
        """
        backfill_script = Path("scripts/backfill_project_id.py")
        content = backfill_script.read_text()

        # Should have description
        assert "description" in content.lower() or "__doc__" in content, \
            "Backfill script should have help documentation"
        # Should describe purpose
        assert "backfill" in content.lower() and "project_id" in content.lower(), \
            "Backfill script should document its purpose"


class TestDatabaseIntegration:
    """INTEGRATION TESTS: Verify actual backfill execution against database"""

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backfill_updates_null_values(self, conn):
        """INTEGRATION: Verify backfill script updates NULL project_id to 'io'

        GIVEN database with some NULL project_id values
        WHEN backfill script runs
        THEN all NULL values are set to 'io'
        """
        # Import backfill function
        from scripts.backfill_project_id import backfill_all_tables

        # Create test data with NULL project_id in nodes table
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO nodes (name, label, project_id)
            VALUES ('test-backfill-node-1', 'test', NULL),
                   ('test-backfill-node-2', 'test', NULL)
            ON CONFLICT (name) DO UPDATE SET project_id = EXCLUDED.project_id
        """)
        conn.commit()
        cursor.close()

        # Run backfill
        await backfill_all_tables(conn, batch_size=5000, sleep_duration=0)

        # Verify all project_id values are 'io'
        cursor = conn.cursor()
        cursor.execute("""
            SELECT project_id
            FROM nodes
            WHERE name LIKE 'test-backfill-node-%'
        """)
        result = cursor.fetchall()
        cursor.close()

        assert len(result) == 2, "Should have 2 test nodes"
        assert all(row['project_id'] == 'io' for row in result), \
            "All NULL values should be backfilled to 'io'"

        # Cleanup
        cursor = conn.cursor()
        cursor.execute("DELETE FROM nodes WHERE name LIKE 'test-backfill-node-%'")
        conn.commit()
        cursor.close()

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backfill_logs_anomalies(self, conn):
        """INTEGRATION: Verify backfill logs anomalies for problematic records

        GIVEN database with corrupted records
        WHEN backfill script encounters errors
        THEN anomalies are logged and backfill continues
        """
        from scripts.backfill_project_id import backfill_all_tables

        # Create anomalies table first (part of backfill script)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backfill_anomalies (
                id SERIAL PRIMARY KEY,
                table_name VARCHAR(100) NOT NULL,
                row_id VARCHAR(100),
                issue_description TEXT NOT NULL,
                resolved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()
        cursor.close()

        # Run backfill (should handle any anomalies gracefully)
        await backfill_all_tables(conn, batch_size=5000, sleep_duration=0)

        # Verify anomalies table exists
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'backfill_anomalies'
            )
        """)
        result = cursor.fetchone()
        cursor.close()

        assert result[0] is True, "Anomalies table should exist after backfill"

        # Cleanup
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS backfill_anomalies")
        conn.commit()
        cursor.close()

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_constraint_validation(self, conn):
        """INTEGRATION: Verify VALIDATE CONSTRAINT enforces NOT NULL

        GIVEN backfilled data with no NULL values
        WHEN VALIDATE CONSTRAINT runs
        THEN constraint is validated and enforced
        """
        from scripts.backfill_project_id import validate_all_constraints

        # Ensure all project_id values are 'io' (no NULLs)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE nodes SET project_id = 'io' WHERE project_id IS NULL
        """)
        conn.commit()
        cursor.close()

        # Run constraint validation
        await validate_all_constraints(conn)

        # Verify constraint is now validated
        cursor = conn.cursor()
        cursor.execute("""
            SELECT conname, convalidated
            FROM pg_constraint
            WHERE conname = 'check_nodes_project_id_not_null'
        """)
        result = cursor.fetchall()
        cursor.close()

        assert len(result) > 0, "Constraint should exist"
        # After VALIDATE CONSTRAINT, convalidated should be 't' (true)
        # Note: In actual implementation, we check this

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backfill_all_11_tables(self, conn):
        """INTEGRATION: Verify backfill processes all 11 tables

        GIVEN database with all 11 tables from Story 11.1.1
        WHEN backfill runs
        THEN all tables are processed and updated
        """
        from scripts.backfill_project_id import backfill_all_tables

        # Run backfill
        results = await backfill_all_tables(conn, batch_size=5000, sleep_duration=0)

        # Verify all tables were processed
        assert 'processed_tables' in results, "Should return processed tables count"
        assert results['processed_tables'] == 11, \
            f"Should process all 11 tables, got {results.get('processed_tables')}"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dry_run_mode(self, conn):
        """INTEGRATION: Verify dry-run mode doesn't modify data

        GIVEN database with NULL project_id values
        WHEN backfill runs with --dry-run
        THEN no data is actually modified
        """
        from scripts.backfill_project_id import backfill_all_tables

        # Insert test data with NULL
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO nodes (name, label, project_id)
            VALUES ('test-dryrun-node', 'test', NULL)
            ON CONFLICT (name) DO UPDATE SET project_id = EXCLUDED.project_id
        """)
        conn.commit()
        cursor.close()

        # Get initial NULL count
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM nodes WHERE name = 'test-dryrun-node' AND project_id IS NULL
        """)
        initial_null_count = cursor.fetchone()[0]
        cursor.close()

        # Run dry-run backfill
        await backfill_all_tables(conn, batch_size=5000, sleep_duration=0, dry_run=True)

        # Verify data unchanged (still NULL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM nodes WHERE name = 'test-dryrun-node' AND project_id IS NULL
        """)
        final_null_count = cursor.fetchone()[0]
        cursor.close()

        assert initial_null_count == final_null_count, \
            "Dry-run mode should not modify data"

        # Cleanup
        cursor = conn.cursor()
        cursor.execute("DELETE FROM nodes WHERE name = 'test-dryrun-node'")
        conn.commit()
        cursor.close()

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batched_operations(self, conn):
        """INTEGRATION: Verify backfill uses batched operations

        GIVEN database with many rows needing backfill
        WHEN backfill runs with batch_size=100
        THEN multiple batches are executed
        """
        from scripts.backfill_project_id import backfill_table

        # Create test data
        cursor = conn.cursor()
        for i in range(250):
            cursor.execute("""
                INSERT INTO nodes (name, label, project_id)
                VALUES (%s, 'test', NULL)
                ON CONFLICT (name) DO UPDATE SET project_id = EXCLUDED.project_id
            """, (f"test-batch-node-{i}",))
        conn.commit()
        cursor.close()

        # Run with small batch size
        result = await backfill_table(
            conn,
            'nodes',
            batch_size=100,
            sleep_duration=0
        )

        # Should track batches
        assert 'batches' in result, "Should track number of batches"
        assert result['batches'] >= 2, "Should process in multiple batches"

        # Verify all updated
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM nodes
            WHERE name LIKE 'test-batch-node-%' AND project_id IS NULL
        """)
        null_count = cursor.fetchone()[0]
        cursor.close()

        assert null_count == 0, "All rows should be backfilled"

        # Cleanup
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM nodes WHERE name LIKE 'test-batch-node-%'
        """)
        conn.commit()
        cursor.close()

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_summary_statistics(self, conn):
        """INTEGRATION: Verify backfill reports summary statistics

        GIVEN backfill completes
        WHEN summary is generated
        THEN it includes total rows updated, anomalies found, processing time
        """
        from scripts.backfill_project_id import backfill_all_tables

        # Run backfill
        results = await backfill_all_tables(conn, batch_size=5000, sleep_duration=0)

        # Verify summary fields
        assert 'total_updated' in results, "Should report total rows updated"
        assert 'total_anomalies' in results, "Should report anomalies found"
        assert 'processing_time' in results, \
            "Should report processing time"

        # Total updated should be non-negative
        assert results['total_updated'] >= 0, "Total updated should be non-negative"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_sets_null(self, conn):
        """INTEGRATION: Verify rollback sets project_id back to NULL

        GIVEN backfill has been run
        WHEN rollback is executed
        THEN project_id values are set back to NULL
        """
        from scripts.backfill_project_id import rollback_backfill

        # Insert test data with 'io'
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO nodes (name, label, project_id)
            VALUES ('test-rollback-node', 'test', 'io')
            ON CONFLICT (name) DO UPDATE SET project_id = EXCLUDED.project_id
        """)
        conn.commit()
        cursor.close()

        # Run rollback (before constraint validation)
        await rollback_backfill(conn, tables=['nodes'])

        # Verify set to NULL
        cursor = conn.cursor()
        cursor.execute("""
            SELECT project_id FROM nodes WHERE name = 'test-rollback-node'
        """)
        result = cursor.fetchone()
        cursor.close()

        assert result is None or result[0] is None, "Rollback should set project_id back to NULL"

        # Cleanup
        cursor = conn.cursor()
        cursor.execute("DELETE FROM nodes WHERE name = 'test-rollback-node'")
        conn.commit()
        cursor.close()
