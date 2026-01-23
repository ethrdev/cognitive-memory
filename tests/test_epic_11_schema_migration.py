"""
P0 Tests: Schema Migration for Epic 11 Namespace Isolation
ATDD Red Phase - Tests that will pass after implementation

Story 11.1.1: Add project_id Column to All Tables

Risk Mitigation:
- R-001: Schema migration corrupts data
- R-002: Migration causes downtime (> 1s table lock)
- R-003: Migration is not idempotent

Test Count: 33 (28 file structure tests + 5 database integration tests)
"""

import pytest
from pathlib import Path


class TestMigrationFileExists:
    """Verify migration files are created correctly"""

    @pytest.mark.P0
    def test_migration_file_exists(self):
        """AC1, AC2, AC3: Migration file should exist

        Given Story 11.1.1 implementation
        When migration 027_add_project_id.sql is created
        Then the file exists with all required tables
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        assert migration_file.exists(), "Migration file should exist"

    @pytest.mark.P0
    def test_rollback_file_exists(self):
        """DoD requirement: Rollback script must exist

        Given Story 11.1.1 implementation
        When rollback script is created
        Then 027_add_project_id_rollback.sql exists
        """
        rollback_file = Path("mcp_server/db/migrations/027_add_project_id_rollback.sql")
        assert rollback_file.exists(), "Rollback file should exist"


class TestCoreTablesMigration:
    """AC1: Core Tables (High Risk) - Instant Column Addition"""

    @pytest.mark.P0
    def test_l2_insights_column_added(self):
        """AC1: l2_insights table gets project_id column

        Given the l2_insights table exists
        When migration runs
        Then project_id VARCHAR(50) DEFAULT 'io' is added
        And NOT VALID constraint is used
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "l2_insights" in content, "l2_insights table should be in migration"
        assert "ADD COLUMN project_id VARCHAR(50) DEFAULT 'io'" in content, \
            "l2_insights should add project_id with VARCHAR(50) DEFAULT 'io'"
        assert "check_l2_insights_project_id_not_null" in content, \
            "l2_insights should have NOT NULL constraint"

    @pytest.mark.P0
    def test_nodes_column_added(self):
        """AC1: nodes table gets project_id column

        Given the nodes table exists
        When migration runs
        Then project_id VARCHAR(50) DEFAULT 'io' is added
        And NOT VALID constraint is used
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "nodes" in content, "nodes table should be in migration"
        assert "nodes ADD COLUMN project_id VARCHAR(50) DEFAULT 'io'" in content, \
            "nodes should add project_id with correct spec"
        assert "check_nodes_project_id_not_null" in content, \
            "nodes should have NOT NULL constraint"

    @pytest.mark.P0
    def test_edges_column_added(self):
        """AC1: edges table gets project_id column

        Given the edges table exists
        When migration runs
        Then project_id VARCHAR(50) DEFAULT 'io' is added
        And NOT VALID constraint is used
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "edges" in content, "edges table should be in migration"
        assert "edges ADD COLUMN project_id VARCHAR(50) DEFAULT 'io'" in content, \
            "edges should add project_id with correct spec"
        assert "check_edges_project_id_not_null" in content, \
            "edges should have NOT NULL constraint"


class TestSupportTablesMigration:
    """AC2: Support Tables (Lower Risk)"""

    @pytest.mark.P0
    def test_working_memory_column_added(self):
        """AC2: working_memory table gets project_id column

        Given the working_memory table exists
        When migration runs
        Then project_id VARCHAR(50) DEFAULT 'io' is added
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "working_memory" in content, "working_memory table should be in migration"
        assert "working_memory ADD COLUMN project_id VARCHAR(50) DEFAULT 'io'" in content, \
            "working_memory should add project_id with correct spec"

    @pytest.mark.P0
    def test_episode_memory_column_added(self):
        """AC2: episode_memory table gets project_id column

        Given the episode_memory table exists (actual table name verified)
        When migration runs
        Then project_id VARCHAR(50) DEFAULT 'io' is added
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "episode_memory" in content, "episode_memory table should be in migration"
        assert "episode_memory ADD COLUMN project_id VARCHAR(50) DEFAULT 'io'" in content, \
            "episode_memory should add project_id with correct spec"

    @pytest.mark.P0
    def test_l0_raw_column_added(self):
        """AC2: l0_raw table gets project_id column

        Given the l0_raw table exists (actual table name verified)
        When migration runs
        Then project_id VARCHAR(50) DEFAULT 'io' is added
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "l0_raw" in content, "l0_raw table should be in migration"
        assert "l0_raw ADD COLUMN project_id VARCHAR(50) DEFAULT 'io'" in content, \
            "l0_raw should add project_id with correct spec"

    @pytest.mark.P0
    def test_ground_truth_column_added(self):
        """AC2: ground_truth table gets project_id column

        Given the ground_truth table exists
        When migration runs
        Then project_id VARCHAR(50) DEFAULT 'io' is added
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "ground_truth" in content, "ground_truth table should be in migration"
        assert "ground_truth ADD COLUMN project_id VARCHAR(50) DEFAULT 'io'" in content, \
            "ground_truth should add project_id with correct spec"


class TestAdditionalTablesMigration:
    """AC3: Additional Tables (discovered in schema analysis)"""

    @pytest.mark.P0
    def test_stale_memory_column_added(self):
        """AC3: stale_memory table gets project_id column

        Given the stale_memory table exists (added in migration 026)
        When migration runs
        Then project_id VARCHAR(50) DEFAULT 'io' is added
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "stale_memory" in content, "stale_memory table should be in migration"
        assert "stale_memory ADD COLUMN project_id VARCHAR(50) DEFAULT 'io'" in content, \
            "stale_memory should add project_id with correct spec"

    @pytest.mark.P0
    def test_smf_proposals_column_added(self):
        """AC3: smf_proposals table gets project_id column

        Given the smf_proposals table exists
        When migration runs
        Then project_id VARCHAR(50) DEFAULT 'io' is added
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "smf_proposals" in content, "smf_proposals table should be in migration"
        assert "smf_proposals ADD COLUMN project_id VARCHAR(50) DEFAULT 'io'" in content, \
            "smf_proposals should add project_id with correct spec"

    @pytest.mark.P0
    def test_ief_feedback_column_added(self):
        """AC3: ief_feedback table gets project_id column

        Given the ief_feedback table exists
        When migration runs
        Then project_id VARCHAR(50) DEFAULT 'io' is added
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "ief_feedback" in content, "ief_feedback table should be in migration"
        assert "ief_feedback ADD COLUMN project_id VARCHAR(50) DEFAULT 'io'" in content, \
            "ief_feedback should add project_id with correct spec"

    @pytest.mark.P0
    def test_l2_insight_history_column_added(self):
        """AC3: l2_insight_history table gets project_id column

        Given the l2_insight_history table exists (added in 024)
        When migration runs
        Then project_id VARCHAR(50) DEFAULT 'io' is added
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "l2_insight_history" in content, "l2_insight_history table should be in migration"
        assert "l2_insight_history ADD COLUMN project_id VARCHAR(50) DEFAULT 'io'" in content, \
            "l2_insight_history should add project_id with correct spec"


class TestZeroDowntimeMigration:
    """AC4: Zero-Downtime Verification"""

    @pytest.mark.P0
    def test_uses_not_valid_constraint(self):
        """AC4: NOT VALID constraint avoids table scan

        Given the migration runs on tables with data
        When adding project_id column
        Then NOT VALID constraint is used for NOT NULL
        And validation is deferred to Story 11.1.2
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        # All 11 tables should use NOT VALID constraint
        not_valid_count = content.count("NOT VALID")
        assert not_valid_count >= 11, \
            f"Expected at least 11 NOT VALID constraints, found {not_valid_count}"

    @pytest.mark.P0
    def test_uses_default_value(self):
        """AC4: ADD COLUMN with DEFAULT is instant (PostgreSQL 11+)

        Given the migration runs
        When adding project_id column
        Then DEFAULT 'io' is used for instant addition
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        # All 11 tables should have DEFAULT 'io'
        default_count = content.count("DEFAULT 'io'")
        assert default_count >= 11, \
            f"Expected at least 11 DEFAULT 'io', found {default_count}"


class TestIdempotency:
    """NFR3: Migration must be idempotent (safe to run multiple times)"""

    @pytest.mark.P0
    def test_uses_if_not_exists_pattern(self):
        """NFR3: Idempotent column addition

        Given migration has been executed once
        When it is executed again
        Then no errors occur and column is not duplicated
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        # Should use IF NOT EXISTS check in DO block
        assert "IF NOT EXISTS" in content, \
            "Migration should check if column exists before adding"
        assert "information_schema.columns" in content, \
            "Migration should query information_schema for idempotency"
        assert "DO $$" in content, \
            "Migration should use DO block for idempotent operations"

    @pytest.mark.P0
    def test_all_tables_idempotent(self):
        """NFR3: All 11 tables use idempotent pattern

        Given the migration file
        When checking each table section
        Then all use DO $$ IF NOT EXISTS pattern
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        # Count DO blocks - should have one per table (11 tables)
        do_block_count = content.count("DO $$")
        assert do_block_count >= 11, \
            f"Expected at least 11 DO blocks for idempotency, found {do_block_count}"


class TestRollbackScript:
    """DoD: Rollback script must work correctly"""

    @pytest.mark.P0
    def test_rollback_drops_all_columns(self):
        """DoD: Rollback script removes project_id from all tables

        Given rollback script is executed
        When rollback completes
        Then all 11 project_id columns are removed
        """
        rollback_file = Path("mcp_server/db/migrations/027_add_project_id_rollback.sql")
        content = rollback_file.read_text()

        # All 11 tables should have DROP COLUMN
        drop_count = content.count("DROP COLUMN IF EXISTS project_id")
        assert drop_count >= 11, \
            f"Expected at least 11 DROP COLUMN statements, found {drop_count}"

    @pytest.mark.P0
    def test_rollback_uses_if_exists(self):
        """DoD: Rollback uses IF EXISTS for safety

        Given rollback script is executed
        When columns may not exist
        Then IF EXISTS prevents errors
        """
        rollback_file = Path("mcp_server/db/migrations/027_add_project_id_rollback.sql")
        content = rollback_file.read_text()

        # All DROP statements should use IF EXISTS
        assert "DROP COLUMN IF EXISTS" in content, \
            "Rollback should use IF EXISTS for safe drops"

        # Count occurrences
        if_exists_count = content.count("DROP COLUMN IF EXISTS")
        assert if_exists_count >= 11, \
            f"Expected at least 11 DROP COLUMN IF EXISTS, found {if_exists_count}"


class TestDefaultValues:
    """NFR5: Existing data must be assigned to 'io' (legacy owner)"""

    @pytest.mark.P0
    def test_default_is_io(self):
        """NFR5: All columns use 'io' as default

        Given existing data in tables
        When migration adds project_id column
        Then all existing rows get project_id = 'io'
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        # Should specify DEFAULT 'io' everywhere
        # Count "DEFAULT 'io'" occurrences
        default_io_count = content.count("DEFAULT 'io'")
        assert default_io_count >= 11, \
            f"Expected at least 11 DEFAULT 'io' statements, found {default_io_count}"

    @pytest.mark.P0
    def test_no_other_defaults(self):
        """NFR5: Only 'io' is used as default value

        Given the migration file
        When checking all DEFAULT statements
        Then all use 'io' (no other project IDs)
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        # All DEFAULT 'io' should be consistent
        # Should not have other default values like DEFAULT 'test' or DEFAULT 'project1'
        lines = content.split('\n')
        for line in lines:
            if 'DEFAULT ' in line and 'project_id' in line:
                # Should only have DEFAULT 'io' for project_id columns
                assert "DEFAULT 'io'" in line or "DEFAULT \'io\'" in line, \
                    f"Found unexpected DEFAULT in line: {line}"


class TestVerificationQueries:
    """AC5: Verification queries included"""

    @pytest.mark.P0
    def test_verification_queries_exist(self):
        """AC5: Migration includes verification queries

        Given the migration file
        When checking comments section
        Then verification queries are provided
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "VERIFICATION QUERIES" in content or "VERIFICATION" in content, \
            "Migration should include verification queries section"

    @pytest.mark.P0
    def test_checks_column_existence(self):
        """AC5: Verification checks all columns exist

        Given the migration file
        When verification queries run
        Then they check information_schema.columns
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "information_schema.columns" in content, \
            "Verification should check information_schema for column existence"

    @pytest.mark.P0
    def test_checks_null_values(self):
        """AC5: Verification ensures no NULL values

        Given the migration file
        When verification queries run
        Then they verify no NULL project_id values exist
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "IS NULL" in content or "null_count" in content.lower(), \
            "Verification should check for NULL values"


class TestDatabaseIntegration:
    """INTEGRATION TESTS: Verify actual migration execution against database"""

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_actually_adds_columns(self, conn):
        """INTEGRATION: Verify migration actually adds project_id columns to database

        Given database with pre-migration schema
        When migration 027_add_project_id.sql is executed
        Then all 11 tables have project_id column with correct type and default
        """
        # Load and execute migration
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        migration_sql = migration_file.read_text()

        # Execute migration
        conn.autocommit = True
        try:
            cursor = conn.cursor()
            cursor.execute(migration_sql)
        finally:
            conn.autocommit = False

        # Verify all 11 tables have project_id column
        tables = [
            'l2_insights', 'nodes', 'edges', 'working_memory',
            'episode_memory', 'l0_raw', 'ground_truth', 'stale_memory',
            'smf_proposals', 'ief_feedback', 'l2_insight_history'
        ]

        for table in tables:
            cursor.execute("""
                SELECT column_name, data_type, column_default, is_nullable
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'project_id'
            """, (table,))

            result = cursor.fetchone()
            assert result is not None, f"{table} missing project_id column"
            assert result[1] == 'character varying', f"{table} project_id should be VARCHAR"
            assert result[2] == "'io'::character varying", f"{table} project_id default should be 'io'"
            assert result[3] == 'YES', f"{table} project_id should allow NULL initially (NOT VALID constraint)"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_default_value_works(self, conn):
        """INTEGRATION: Verify DEFAULT 'io' is applied to existing rows

        Given database with data in a table
        When migration adds project_id column
        Then existing rows get project_id = 'io' automatically
        """
        # Load and execute migration
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        migration_sql = migration_file.read_text()

        conn.autocommit = True
        try:
            cursor = conn.cursor()
            cursor.execute(migration_sql)
        finally:
            conn.autocommit = False

        # Test with working_memory table (smaller, safer for testing)
        cursor.execute("""
            SELECT project_id
            FROM working_memory
            LIMIT 1
        """)

        # If table has data, verify project_id is 'io'
        result = cursor.fetchone()
        if result:
            assert result[0] == 'io', "Existing rows should have project_id = 'io'"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_idempotent_execution(self, conn):
        """INTEGRATION: Verify migration can run multiple times safely

        Given migration has been executed once
        When it is executed again
        Then no errors occur and no duplicate columns created
        """
        # Load migration
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        migration_sql = migration_file.read_text()

        # Execute twice
        conn.autocommit = True
        try:
            cursor = conn.cursor()
            cursor.execute(migration_sql)
            cursor.execute(migration_sql)  # Should not error
        finally:
            conn.autocommit = False

        # Verify still only one project_id column per table
        cursor.execute("""
            SELECT table_name, COUNT(*)
            FROM information_schema.columns
            WHERE column_name = 'project_id'
            GROUP BY table_name
            HAVING COUNT(*) > 1
        """)

        # Should return empty result (no duplicates)
        results = cursor.fetchall()
        assert len(results) == 0, "No table should have duplicate project_id columns"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_not_valid_constraints_created(self, conn):
        """INTEGRATION: Verify NOT VALID constraints avoid table scans

        Given migration executes successfully
        When checking constraints
        Then NOT VALID constraints are created (not yet validated)
        """
        # Load and execute migration
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        migration_sql = migration_file.read_text()

        conn.autocommit = True
        try:
            cursor = conn.cursor()
            cursor.execute(migration_sql)
        finally:
            conn.autocommit = False

        # Check NOT VALID constraints exist
        cursor.execute("""
            SELECT conname, convalidated
            FROM pg_constraint
            WHERE conname LIKE '%project_id_not_null%'
        """)

        constraints = cursor.fetchall()
        assert len(constraints) >= 11, "Should have at least 11 NOT VALID constraints"

        for conname, validated in constraints:
            assert validated == 'f', f"Constraint {conname} should be NOT VALID"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_script_actually_removes_columns(self, conn):
        """INTEGRATION: Verify rollback script removes project_id columns

        Given migration has been applied
        When rollback script is executed
        Then all project_id columns are removed
        """
        # Load and execute migration first
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        migration_sql = migration_file.read_text()

        conn.autocommit = True
        try:
            cursor = conn.cursor()
            cursor.execute(migration_sql)
        finally:
            conn.autocommit = False

        # Execute rollback
        rollback_file = Path("mcp_server/db/migrations/027_add_project_id_rollback.sql")
        rollback_sql = rollback_file.read_text()

        conn.autocommit = True
        try:
            cursor = conn.cursor()
            cursor.execute(rollback_sql)
        finally:
            conn.autocommit = False

        # Verify no project_id columns exist
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE column_name = 'project_id'
        """)

        count = cursor.fetchone()[0]
        assert count == 0, "Rollback should remove all project_id columns"


class TestMigrationFileStructure:
    """Migration file follows Epic 8 pattern"""

    @pytest.mark.P0
    def test_has_purpose_header(self):
        """Migration file should have proper documentation

        Given the migration file
        When reading the header
        Then it has Purpose, Dependencies, Breaking Changes
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "Purpose:" in content or "PURPOSE" in content.upper(), \
            "Migration should document purpose"
        assert "Dependencies:" in content or "DEPENDENCIES" in content.upper(), \
            "Migration should document dependencies"
        assert "Breaking Changes:" in content or "BREAKING" in content.upper(), \
            "Migration should document breaking changes"

    @pytest.mark.P0
    def test_phase_structure(self):
        """Migration follows two-phase pattern from Epic 8

        Given the migration file
        When checking structure
        Then it has PHASE 1: SCHEMA MIGRATION section
        """
        migration_file = Path("mcp_server/db/migrations/027_add_project_id.sql")
        content = migration_file.read_text()

        assert "PHASE 1" in content or "PHASE1" in content, \
            "Migration should have PHASE 1 section"
        assert "SCHEMA MIGRATION" in content or "SCHEMA" in content, \
            "Migration should document schema migration phase"


class TestRollbackDocumentation:
    """Rollback script is properly documented"""

    @pytest.mark.P0
    def test_rollback_has_warning(self):
        """Rollback script should warn about dependent migrations

        Given the rollback file
        When reading header
        Then it warns about Story 11.1.2+ dependencies
        """
        rollback_file = Path("mcp_server/db/migrations/027_add_project_id_rollback.sql")
        content = rollback_file.read_text()

        assert "WARNING" in content or "Warning" in content, \
            "Rollback should have warning header"
        assert "11.1.2" in content or "11.1.3" in content, \
            "Rollback should warn about subsequent migrations"

    @pytest.mark.P0
    def test_rollback_has_procedure(self):
        """Rollback script should document procedure

        Given the rollback file
        When reading documentation
        Then it lists rollback procedure steps
        """
        rollback_file = Path("mcp_server/db/migrations/027_add_project_id_rollback.sql")
        content = rollback_file.read_text()

        assert "Procedure" in content or "procedure" in content, \
            "Rollback should document procedure"
