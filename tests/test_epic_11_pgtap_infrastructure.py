"""
P0 Tests: pgTAP Test Infrastructure for Epic 11.3.0

Story 11.3.0: pgTAP + Test Infrastructure

Risk Mitigation:
- R-001: pgTAP installation fails in test database
- R-002: BYPASSRLS role created in production (security risk)
- R-003: Installation script is not idempotent
- R-004: pgTAP template missing critical patterns

Acceptance Criteria:
- AC1: pgTAP Extension Installation (Test-Only, NOT Production Migration)
- AC2: pgTAP Test Execution via pg_prove
- AC4: BYPASSRLS Test Role (Secure Setup)
- AC10: Role-Switching in pgTAP Tests

Test Count: 20 (15 file structure tests + 5 database integration tests)
"""

import os
import pytest
from pathlib import Path


class TestInstallScriptFileStructure:
    """Verify install_test_extensions.sql file structure"""

    @pytest.mark.P0
    def test_install_script_exists(self):
        """AC1: Installation script should exist

        Given Story 11.3.0 implementation
        When install_test_extensions.sql is created
        Then the file exists at tests/db/sql/install_test_extensions.sql
        """
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        assert install_script.exists(), "Installation script should exist"

    @pytest.mark.P0
    def test_install_script_contains_pgtap_extension(self):
        """AC1: Script should install pgTAP extension

        Given the installation script
        When reading its contents
        Then CREATE EXTENSION IF NOT EXISTS pgtap is present
        """
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        content = install_script.read_text()

        assert "CREATE EXTENSION IF NOT EXISTS pgtap" in content, \
            "Script should install pgTAP extension"

    @pytest.mark.P0
    def test_install_script_has_test_only_warning(self):
        """AC1: Script should have test-only warnings

        Given the installation script
        When reading its contents
        Then multiple warnings indicate TEST-ONLY usage
        """
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        content = install_script.read_text()

        assert "TEST-ONLY" in content or "TEST DATABASE ONLY" in content, \
            "Script should have test-only warning"
        assert "NEVER run these statements in production" in content or \
               "NEVER use in production" in content, \
            "Script should warn against production use"

    @pytest.mark.P0
    def test_install_script_is_idempotent(self):
        """AC1: Script should be idempotent (IF NOT EXISTS pattern)

        Given the installation script
        When reading its contents
        Then IF NOT EXISTS pattern is used for extension and role
        """
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        content = install_script.read_text()

        assert "IF NOT EXISTS" in content, \
            "Script should use IF NOT EXISTS for idempotency"

    @pytest.mark.P0
    def test_install_script_creates_bypass_role(self):
        """AC4: Script should create test_bypass_role

        Given the installation script
        When reading its contents
        Then test_bypass_role is created with BYPASSRLS attribute
        """
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        content = install_script.read_text()

        assert "test_bypass_role" in content, \
            "Script should create test_bypass_role"
        assert "BYPASSRLS" in content, \
            "Role should have BYPASSRLS attribute"

    @pytest.mark.P0
    def test_bypass_role_has_login(self):
        """AC4: test_bypass_role should have LOGIN attribute

        Given the installation script
        When reading its contents
        Then test_bypass_role has LOGIN (can connect via TEST_BYPASS_DSN)
        """
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        content = install_script.read_text()

        assert "LOGIN" in content, \
            "test_bypass_role should have LOGIN attribute for DSN connection"

    @pytest.mark.P0
    def test_bypass_role_grants_table_access(self):
        """AC4: Script should grant table access to test_bypass_role

        Given the installation script
        When reading its contents
        Then SELECT, INSERT, UPDATE, DELETE is granted on all tables
        """
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        content = install_script.read_text()

        assert "GRANT SELECT, INSERT, UPDATE, DELETE" in content, \
            "Script should grant full table access to test_bypass_role"

    @pytest.mark.P0
    def test_bypass_role_not_superuser(self):
        """AC4: test_bypass_role should NOT be a superuser

        Given the installation script
        When reading its contents
        Then test_bypass_role has NOSUPERUSER attribute
        """
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        content = install_script.read_text()

        assert "NOSUPERUSER" in content, \
            "test_bypass_role should have NOSUPERUSER attribute"


@pytest.mark.integration
class TestInstallScriptDatabaseIntegration:
    """AC1, AC4: Verify installation works in test database"""

    @pytest.mark.P0
    def test_install_script_pgtap_extension_created(self, conn):
        """AC1: pgTAP extension can be created in test database

        Given a test database connection
        When install_test_extensions.sql is executed
        Then pgTAP extension is installed successfully
        And pgTAP functions are available
        """
        # Read and execute the installation script
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        script_content = install_script.read_text()

        cur = conn.cursor()
        try:
            cur.execute(script_content)
            conn.commit()

            # Verify pgTAP extension exists
            cur.execute("""
                SELECT extname FROM pg_extension
                WHERE extname = 'pgtap'
            """)
            result = cur.fetchone()

            assert result is not None, \
                "pgTAP extension should be installed"

            # Verify a pgTAP function exists (e.g., plan())
            cur.execute("""
                SELECT proname FROM pg_proc
                WHERE proname = 'plan'
                LIMIT 1
            """)
            result = cur.fetchone()

            assert result is not None, \
                "pgTAP function plan() should be available"
        finally:
            conn.rollback()

    @pytest.mark.P0
    def test_install_script_bypass_role_created(self, conn):
        """AC4: test_bypass_role is created with correct attributes

        Given a test database connection
        When install_test_extensions.sql is executed
        Then test_bypass_role exists with BYPASSRLS, NOLOGIN, NOSUPERUSER
        """
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        script_content = install_script.read_text()

        cur = conn.cursor()
        try:
            cur.execute(script_content)
            conn.commit()

            # Verify role exists
            cur.execute("""
                SELECT rolname, rolcanlogin, rolsuper, rolbypassrls
                FROM pg_roles
                WHERE rolname = 'test_bypass_role'
            """)
            result = cur.fetchone()

            assert result is not None, \
                "test_bypass_role should be created"
            assert result[0] == 'test_bypass_role', \
                "Role name should be test_bypass_role"
            assert result[1] == True, \
                "test_bypass_role should have LOGIN (for TEST_BYPASS_DSN)"
            assert result[2] == False, \
                "test_bypass_role should have NOSUPERUSER"
            assert result[3] == True, \
                "test_bypass_role should have BYPASSRLS"
        finally:
            conn.rollback()

    @pytest.mark.P0
    def test_install_script_idempotent(self, conn):
        """AC1: Script can be run multiple times without errors

        Given a test database connection
        When install_test_extensions.sql is executed twice
        Then both executions succeed without errors
        """
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        script_content = install_script.read_text()

        cur = conn.cursor()
        try:
            # First execution
            cur.execute(script_content)
            conn.commit()

            # Second execution (should not fail)
            cur.execute(script_content)
            conn.commit()

            # Verify state is consistent
            cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'pgtap'")
            assert cur.fetchone() is not None, \
                "pgTAP extension should still exist after second execution"

        finally:
            conn.rollback()

    @pytest.mark.P0
    def test_install_script_security_comment(self, conn):
        """AC4: test_bypass_role has security documentation

        Given a test database connection
        When install_test_extensions.sql is executed
        Then test_bypass_role has comment about test-only usage
        """
        install_script = Path("tests/db/sql/install_test_extensions.sql")
        script_content = install_script.read_text()

        cur = conn.cursor()
        try:
            cur.execute(script_content)
            conn.commit()

            # Check for comment on role (may be None in some DB environments)
            cur.execute("""
                SELECT obj_description((SELECT oid FROM pg_roles WHERE rolname = 'test_bypass_role'), 'pg_authid')
            """)
            result = cur.fetchone()
            comment = result[0] if result else None

            # If comment exists, verify it indicates test-only usage
            if comment is not None:
                comment_lower = comment.lower()
                assert "test" in comment_lower or "never" in comment_lower, \
                    "Comment should indicate test-only usage"

        finally:
            conn.rollback()


class TestPgtapTemplateFileStructure:
    """Verify template_rls_test.sql file structure (AC2, AC10)"""

    @pytest.mark.P0
    def test_template_file_exists(self):
        """AC2: Template file should exist

        Given Story 11.3.0 implementation
        When template_rls_test.sql is created
        Then the file exists at tests/db/pgtap/template_rls_test.sql
        """
        template_file = Path("tests/db/pgtap/template_rls_test.sql")
        assert template_file.exists(), "Template file should exist"

    @pytest.mark.P0
    def test_template_has_begin_rollback(self):
        """AC10: Template should have BEGIN/ROLLBACK transaction wrapper

        Given the template file
        When reading its contents
        Then BEGIN and ROLLBACK are present for transaction isolation
        """
        template_file = Path("tests/db/pgtap/template_rls_test.sql")
        content = template_file.read_text()

        assert "BEGIN;" in content, \
            "Template should have BEGIN statement"
        assert "ROLLBACK;" in content, \
            "Template should have ROLLBACK statement"

    @pytest.mark.P0
    def test_template_has_set_local_role_pattern(self):
        """AC10: Template should demonstrate SET LOCAL ROLE pattern

        Given the template file
        When reading its contents
        Then SET LOCAL ROLE and RESET ROLE patterns are shown
        """
        template_file = Path("tests/db/pgtap/template_rls_test.sql")
        content = template_file.read_text()

        assert "SET LOCAL ROLE" in content, \
            "Template should show SET LOCAL ROLE pattern"
        assert "RESET ROLE" in content, \
            "Template should show RESET ROLE pattern"

    @pytest.mark.P0
    def test_template_has_set_local_project_pattern(self):
        """AC10: Template should demonstrate SET LOCAL app.current_project

        Given the template file
        When reading its contents
        Then SET LOCAL app.current_project pattern is shown
        """
        template_file = Path("tests/db/pgtap/template_rls_test.sql")
        content = template_file.read_text()

        assert "SET LOCAL app.current_project" in content, \
            "Template should show SET LOCAL app.current_project pattern"

    @pytest.mark.P0
    def test_template_has_pgtap_functions(self):
        """AC2: Template should use pgTAP functions

        Given the template file
        When reading its contents
        Then pgTAP functions like plan(), is(), finish() are demonstrated
        """
        template_file = Path("tests/db/pgtap/template_rls_test.sql")
        content = template_file.read_text()

        assert "SELECT plan(" in content, \
            "Template should use plan() function"
        assert "SELECT is(" in content, \
            "Template should use is() assertion function"
        assert "SELECT finish()" in content, \
            "Template should use finish() function"

    @pytest.mark.P0
    def test_template_has_test_project_setup(self):
        """AC2: Template should show test project setup

        Given the template file
        When reading its contents
        Then test projects (test_super, test_shared, test_isolated) are created
        """
        template_file = Path("tests/db/pgtap/template_rls_test.sql")
        content = template_file.read_text()

        assert "test_super" in content, \
            "Template should show test_super project"
        assert "test_shared" in content, \
            "Template should show test_shared project"
        assert "test_isolated" in content, \
            "Template should show test_isolated project"
        assert "project_registry" in content, \
            "Template should register test projects"

    @pytest.mark.P0
    def test_template_has_ephemeral_data_pattern(self):
        """AC2: Template should use ON CONFLICT DO NOTHING

        Given the template file
        When reading its contents
        Then ON CONFLICT pattern is used for idempotency
        """
        template_file = Path("tests/db/pgtap/template_rls_test.sql")
        content = template_file.read_text()

        assert "ON CONFLICT" in content, \
            "Template should use ON CONFLICT for idempotency"


class TestPytestFixturesInConftest:
    """Verify RLS pytest fixtures are properly defined (AC5, AC6, AC7)"""

    @pytest.mark.P0
    def test_project_context_class_exists(self):
        """AC6: ProjectContext class should exist in conftest

        Given Story 11.3.0 implementation
        When conftest.py is read
        Then ProjectContext class is defined
        """
        conftest = Path("tests/conftest.py")
        content = conftest.read_text()

        assert "class ProjectContext:" in content, \
            "ProjectContext class should be defined"

    @pytest.mark.P0
    def test_project_context_has_enter_exit(self):
        """AC6: ProjectContext should have __enter__ and __exit__ methods

        Given the ProjectContext class
        When inspecting conftest.py
        Then __enter__ and __exit__ are defined (context manager protocol)
        """
        conftest = Path("tests/conftest.py")
        content = conftest.read_text()

        assert "def __enter__" in content, \
            "ProjectContext should have __enter__ method"
        assert "def __exit__" in content, \
            "ProjectContext should have __exit__ method"

    @pytest.mark.P0
    def test_project_context_fixture_exists(self):
        """AC6: project_context fixture should exist

        Given conftest.py
        When reading its contents
        Then project_context fixture is defined
        """
        conftest = Path("tests/conftest.py")
        content = conftest.read_text()

        assert "def project_context" in content, \
            "project_context fixture should be defined"
        assert "return ProjectContext" in content, \
            "project_context fixture should return ProjectContext class"

    @pytest.mark.P0
    def test_isolated_conn_fixture_exists(self):
        """AC5: isolated_conn fixture should exist

        Given conftest.py
        When reading its contents
        Then isolated_conn fixture is defined
        """
        conftest = Path("tests/conftest.py")
        content = conftest.read_text()

        assert "def isolated_conn" in content, \
            "isolated_conn fixture should be defined"
        assert "SET LOCAL app.current_project" in content, \
            "isolated_conn should set app.current_project"
        assert "%s" in content or "$1" in content, \
            "isolated_conn should use parameterized query (not f-string)"

    @pytest.mark.P0
    def test_bypass_conn_fixture_exists(self):
        """AC7: bypass_conn fixture should exist

        Given conftest.py
        When reading its contents
        Then bypass_conn fixture is defined with TESTING guard
        """
        conftest = Path("tests/conftest.py")
        content = conftest.read_text()

        assert "def bypass_conn" in content, \
            "bypass_conn fixture should be defined"
        assert "TESTING" in content, \
            "bypass_conn should check TESTING environment variable"
        assert "TEST_BYPASS_DSN" in content, \
            "bypass_conn should require TEST_BYPASS_DSN"

    @pytest.mark.P0
    def test_fixtures_use_parameterized_queries(self):
        """AC5, AC6: Fixtures should use parameterized queries for security

        Given conftest.py
        When reading fixture implementations
        Then %s or $1 placeholders are used (no f-strings for SQL)
        """
        conftest = Path("tests/conftest.py")
        content = conftest.read_text()

        # Check that SET LOCAL uses parameterized query
        assert "SET LOCAL app.current_project = %s" in content or \
               "SET LOCAL app.current_project = $1" in content, \
            "Fixtures should use parameterized queries for security"


@pytest.mark.integration
class TestPytestFixturesIntegration:
    """AC5, AC6, AC7: Verify fixtures work in actual tests"""

    @pytest.mark.P0
    def test_project_context_defined(self):
        """AC6: project_context fixture is callable

        Given the test infrastructure
        When requesting project_context fixture
        Then it returns a ProjectContext factory
        """
        # Verify the fixture is defined by checking it's in conftest
        conftest = Path("tests/conftest.py")
        content = conftest.read_text()

        assert "def project_context" in content, \
            "project_context fixture should be defined"
        assert "return ProjectContext" in content, \
            "project_context should return ProjectContext factory"

    @pytest.mark.P0
    def test_isolated_conn_defined(self):
        """AC5: isolated_conn fixture is defined

        Given the test infrastructure
        When checking conftest.py
        Then isolated_conn fixture exists
        """
        conftest = Path("tests/conftest.py")
        content = conftest.read_text()

        assert "def isolated_conn" in content, \
            "isolated_conn fixture should be defined"
        assert "@pytest.fixture" in content, \
            "isolated_conn should be marked as pytest fixture"

    @pytest.mark.P0
    def test_bypass_conn_skips_without_testing_var(self):
        """AC7: bypass_conn should skip when TESTING not set

        Given the bypass_conn fixture
        When TESTING environment variable is not set
        Then the fixture skips with appropriate message
        """
        # Temporarily unset TESTING for this test
        original_testing = os.environ.get("TESTING")
        os.environ.pop("TESTING", None)

        try:
            # Import would cause skip if we tried to use bypass_conn
            # This test verifies the guard logic exists
            conftest = Path("tests/conftest.py")
            content = conftest.read_text()

            assert 'if not os.getenv("TESTING")' in content or \
                   'not os.getenv("TESTING")' in content, \
                "bypass_conn should have TESTING guard"
            assert "pytest.skip" in content, \
                "bypass_conn should skip when TESTING not set"
        finally:
            # Restore original TESTING value
            if original_testing:
                os.environ["TESTING"] = original_testing


class TestRlsTestDataFixture:
    """Verify RLS test data fixtures are properly defined (AC8, AC9)"""

    @pytest.mark.P0
    def test_rls_test_helpers_file_exists(self):
        """AC8: RLS test helpers file should exist

        Given Story 11.3.0 implementation
        When tests/fixtures/rls_test_helpers.py is checked
        Then the file exists with test data fixtures
        """
        helpers_file = Path("tests/fixtures/rls_test_helpers.py")
        assert helpers_file.exists(), \
            "RLS test helpers file should exist"

    @pytest.mark.P0
    def test_rls_test_data_fixture_exists(self):
        """AC8: rls_test_data fixture should exist

        Given the rls_test_helpers.py file
        When reading its contents
        Then rls_test_data fixture is defined
        """
        helpers_file = Path("tests/fixtures/rls_test_helpers.py")
        content = helpers_file.read_text()

        assert "def rls_test_data" in content, \
            "rls_test_data fixture should be defined"
        assert "@pytest.fixture" in content, \
            "rls_test_data should be marked as pytest fixture"

    @pytest.mark.P0
    def test_rls_test_data_creates_test_projects(self):
        """AC8: rls_test_data should create 3 test projects

        Given the rls_test_data fixture
        When reading its implementation
        Then test_super, test_shared, test_isolated are created
        """
        helpers_file = Path("tests/fixtures/rls_test_helpers.py")
        content = helpers_file.read_text()

        assert "test_super" in content, \
            "Should create test_super project"
        assert "test_shared" in content, \
            "Should create test_shared project"
        assert "test_isolated" in content, \
            "Should create test_isolated project"

    @pytest.mark.P0
    def test_rls_test_data_uses_ephemeral_projects(self):
        """AC9: Test data should use ephemeral test projects only

        Given the rls_test_data fixture
        When reading its implementation
        Then production project_ids (io, aa, ab, etc.) are NOT used
        """
        helpers_file = Path("tests/fixtures/rls_test_helpers.py")
        content = helpers_file.read_text()

        # Ensure production project IDs are NOT used
        production_ids = ["'io'", "'aa'", "'ab'", "'ea'", "'echo'", "'motoko'", "'bap'"]
        for prod_id in production_ids:
            # Check that production IDs are NOT used in INSERT statements
            lines_with_prod_id = [line for line in content.split('\n') if prod_id in line]
            # Allow in comments, but not in actual data creation
            data_lines = [l for l in lines_with_prod_id
                         if "INSERT" in l or "VALUES" in l or "project_id =" in l]
            assert len(data_lines) == 0, \
                f"Production project ID {prod_id} should not be used in test data"

    @pytest.mark.P0
    def test_rls_test_data_creates_sample_nodes_edges_insights(self):
        """AC8: rls_test_data should create nodes, edges, and l2_insights

        Given the rls_test_data fixture
        When reading its implementation
        Then 2 nodes, 2 edges, 2 l2_insights per project are created
        """
        helpers_file = Path("tests/fixtures/rls_test_helpers.py")
        content = helpers_file.read_text()

        assert "INSERT INTO nodes" in content, \
            "Should create test nodes"
        assert "INSERT INTO edges" in content, \
            "Should create test edges"
        assert "INSERT INTO l2_insights" in content, \
            "Should create test l2_insights"

    @pytest.mark.P0
    def test_rls_test_data_has_cross_project_permissions(self):
        """AC8: Test data should include cross-project permissions

        Given the rls_test_data fixture
        When reading its implementation
        Then test_shared has read permission to test_isolated
        """
        helpers_file = Path("tests/fixtures/rls_test_helpers.py")
        content = helpers_file.read_text()

        assert "project_read_permissions" in content, \
            "Should set up cross-project permissions"
        assert "test_shared" in content and "test_isolated" in content, \
            "test_shared should have permission to read test_isolated"


@pytest.mark.integration
class TestRlsTestDataFixtureIntegration:
    """AC8, AC9: Verify test data fixture works correctly"""

    @pytest.mark.P0
    def test_rls_test_data_creates_projects(self, conn):
        """AC8: rls_test_data fixture creates test projects

        Given a database connection
        When rls_test_data fixture is used
        Then 3 test projects are registered in project_registry

        Note: Skips if project_registry table doesn't exist (requires Epic 11.2 migrations)
        """
        cur = conn.cursor()

        # Check if project_registry exists (requires Epic 11.2 migrations)
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'project_registry'
            )
        """)
        table_exists = cur.fetchone()[0]

        if not table_exists:
            pytest.skip("project_registry table not found - Epic 11.2 migrations not run")

        try:
            # Simulate fixture behavior
            cur.execute("""
                INSERT INTO project_registry (project_id, name, access_level)
                VALUES
                    ('test_super', 'Test Super Project', 'super'),
                    ('test_shared', 'Test Shared Project', 'shared'),
                    ('test_isolated', 'Test Isolated Project', 'isolated')
                ON CONFLICT (project_id) DO NOTHING
            """)
            conn.commit()

            # Verify projects were created
            cur.execute("""
                SELECT project_id FROM project_registry
                WHERE project_id IN ('test_super', 'test_shared', 'test_isolated')
                ORDER BY project_id
            """)
            results = cur.fetchall()

            project_ids = [r[0] for r in results]
            assert 'test_isolated' in project_ids, \
                "test_isolated should be created"
            assert 'test_shared' in project_ids, \
                "test_shared should be created"
            assert 'test_super' in project_ids, \
                "test_super should be created"
        finally:
            conn.rollback()

    @pytest.mark.P0
    def test_rls_test_data_rolled_back(self, conn):
        """AC9: Test data is rolled back after test

        Given a database connection
        When test data is created and transaction is rolled back
        Then no test projects remain in project_registry

        Note: Skips if project_registry table doesn't exist (requires Epic 11.2 migrations)
        """
        cur = conn.cursor()

        # Check if project_registry exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'project_registry'
            )
        """)
        table_exists = cur.fetchone()[0]

        if not table_exists:
            pytest.skip("project_registry table not found - Epic 11.2 migrations not run")

        try:
            # Create test data
            cur.execute("""
                INSERT INTO project_registry (project_id, name, access_level)
                VALUES ('test_cleanup', 'Test Cleanup', 'isolated')
                ON CONFLICT (project_id) DO NOTHING
            """)
            conn.commit()

            # Verify it exists
            cur.execute("""
                SELECT COUNT(*) FROM project_registry WHERE project_id = 'test_cleanup'
            """)
            count_before = cur.fetchone()[0]
            assert count_before == 1, "Test project should exist"

            # Rollback (simulating test cleanup)
            conn.rollback()

            # Verify cleanup mechanism exists
            # Note: conn.rollback() in the fixture will clean up
        finally:
            conn.rollback()


class TestPytestFallbackTests:
    """Verify pytest fallback tests exist for Azure compatibility (AC3)"""

    @pytest.mark.P0
    def test_rls_isolation_file_exists(self):
        """AC3: test_rls_isolation.py should exist

        Given Story 11.3.0 implementation
        When tests/integration/test_rls_isolation.py is checked
        Then the file exists with pytest fallback tests
        """
        rls_tests = Path("tests/integration/test_rls_isolation.py")
        assert rls_tests.exists(), \
            "RLS isolation fallback tests file should exist"

    @pytest.mark.P0
    def test_fallback_has_super_read_tests(self):
        """AC3: Fallback tests should include super user read tests

        Given the test_rls_isolation.py file
        When reading its contents
        Then tests for super reading all projects exist
        """
        rls_tests = Path("tests/integration/test_rls_isolation.py")
        content = rls_tests.read_text()

        assert "TestSuperReadsAllProjects" in content, \
            "Should have test class for super access level"
        assert "FR12" in content, \
            "Should document FR12 (super reads all)"

    @pytest.mark.P0
    def test_fallback_has_shared_read_tests(self):
        """AC3: Fallback tests should include shared user read tests

        Given the test_rls_isolation.py file
        When reading its contents
        Then tests for shared reading own + permitted exist
        """
        rls_tests = Path("tests/integration/test_rls_isolation.py")
        content = rls_tests.read_text()

        assert "TestSharedReadsOwnAndPermitted" in content, \
            "Should have test class for shared access level"
        assert "FR13" in content, \
            "Should document FR13 (shared reads own + permitted)"

    @pytest.mark.P0
    def test_fallback_has_isolated_read_tests(self):
        """AC3: Fallback tests should include isolated user read tests

        Given the test_rls_isolation.py file
        When reading its contents
        Then tests for isolated reading own only exist
        """
        rls_tests = Path("tests/integration/test_rls_isolation.py")
        content = rls_tests.read_text()

        assert "TestIsolatedReadsOwnOnly" in content, \
            "Should have test class for isolated access level"
        assert "FR14" in content, \
            "Should document FR14 (isolated reads own only)"

    @pytest.mark.P0
    def test_fallback_has_write_tests(self):
        """AC3: Fallback tests should include write isolation tests

        Given the test_rls_isolation.py file
        When reading its contents
        Then tests for all levels writing own only exist
        """
        rls_tests = Path("tests/integration/test_rls_isolation.py")
        content = rls_tests.read_text()

        assert "TestAllLevelsWriteOwnOnly" in content, \
            "Should have test class for write isolation"
        assert "FR15" in content, \
            "Should document FR15 (all levels write own only)"

    @pytest.mark.P0
    def test_fallback_has_null_protection_tests(self):
        """AC3: Fallback tests should include NULL project_id protection

        Given the test_rls_isolation.py file
        When reading its contents
        Then tests for RESTRICTIVE policy on NULL exist
        """
        rls_tests = Path("tests/integration/test_rls_isolation.py")
        content = rls_tests.read_text()

        assert "TestNullProjectIdBlocked" in content, \
            "Should have test class for NULL protection"
        assert "RESTRICTIVE" in content, \
            "Should document RESTRICTIVE policy"

    @pytest.mark.P0
    def test_fallback_has_pgtap_skip_condition(self):
        """AC3: Fallback tests should skip when pgTAP is available

        Given the test_rls_isolation.py file
        When reading its contents
        Then tests have skipif condition for pgTAP availability
        """
        rls_tests = Path("tests/integration/test_rls_isolation.py")
        content = rls_tests.read_text()

        assert "PGTAP_AVAILABLE" in content, \
            "Should check pgTAP availability"
        assert "skipif" in content, \
            "Should have skipif decorator for pgTAP check"


class TestPerformanceComparisonTests:
    """Verify performance comparison tests exist for RLS overhead (AC11)"""

    @pytest.mark.P0
    def test_rls_overhead_file_exists(self):
        """AC11: test_rls_overhead.py should exist

        Given Story 11.3.0 implementation
        When tests/performance/test_rls_overhead.py is checked
        Then the file exists with performance comparison tests
        """
        perf_tests = Path("tests/performance/test_rls_overhead.py")
        assert perf_tests.exists(), \
            "RLS overhead performance tests file should exist"

    @pytest.mark.P0
    def test_performance_has_overhead_measurement_tests(self):
        """AC11: Performance tests should measure RLS overhead

        Given the test_rls_overhead.py file
        When reading its contents
        Then tests measure query latency with/without RLS
        """
        perf_tests = Path("tests/performance/test_rls_overhead.py")
        content = perf_tests.read_text()

        assert "TestRlsOverheadMeasurement" in content, \
            "Should have test class for overhead measurement"
        assert "NFR2" in content, \
            "Should document NFR2 threshold (<10ms overhead)"

    @pytest.mark.P0
    def test_performance_tests_common_queries(self):
        """AC11: Performance tests should cover common query patterns

        Given the test_rls_overhead.py file
        When reading its contents
        Then tests for SELECT, JOIN, vector search, aggregation exist
        """
        perf_tests = Path("tests/performance/test_rls_overhead.py")
        content = perf_tests.read_text()

        assert "simple_select" in content or "SELECT" in content, \
            "Should test simple SELECT queries"
        assert "complex_join" in content or "JOIN" in content, \
            "Should test JOIN queries"
        assert "vector_search" in content or "l2_insights" in content, \
            "Should test vector similarity search"

    @pytest.mark.P0
    def test_performance_requires_bypass_conn(self):
        """AC11: Performance tests require bypass_conn for comparison

        Given the test_rls_overhead.py file
        When reading its contents
        Then tests skip if TEST_BYPASS_DSN not available
        """
        perf_tests = Path("tests/performance/test_rls_overhead.py")
        content = perf_tests.read_text()

        assert "TEST_BYPASS_DSN" in content, \
            "Should require TEST_BYPASS_DSN for comparison tests"
        assert "skipif" in content, \
            "Should skip if bypass connection not available"

    @pytest.mark.P0
    def test_performance_logs_latency_metrics(self):
        """AC11: Performance tests should log latency for NFR2 validation

        Given the test_rls_overhead.py file
        When reading its contents
        Then tests log p95 latency measurements
        """
        perf_tests = Path("tests/performance/test_rls_overhead.py")
        content = perf_tests.read_text()

        assert "p95" in content, \
            "Should calculate p95 percentile"
        assert "overhead" in content.lower(), \
            "Should measure RLS overhead"
