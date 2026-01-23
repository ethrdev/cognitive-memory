"""
Tests for Baseline Capture and Comparison Scripts (Story 11.1.0, Tasks 2-3)

Tests the capture_baseline.py and compare_rls_overhead.py scripts
for structure validation and basic functionality.

Run with: pytest tests/performance/test_baseline_scripts.py -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Integration tests require real database
pytestmark = pytest.mark.integration


class TestCaptureBaselineScript:
    """Test the baseline capture script structure and CLI."""

    @pytest.fixture
    def script_path(self) -> Path:
        """Path to the capture baseline script."""
        return Path("scripts/capture_baseline.py")

    def test_script_exists(self, script_path: Path):
        """Test that the script file exists."""
        assert script_path.exists(), f"Script not found: {script_path}"

    def test_script_has_required_imports(self, script_path: Path):
        """Verify script has required imports."""
        content = script_path.read_text()

        required_imports = [
            "from mcp_server.db.connection import initialize_pool",
            "from mcp_server.tools import handle_hybrid_search",
            "from mcp_server.tools.graph_query_neighbors import handle_graph_query_neighbors",
        ]

        for import_stmt in required_imports:
            assert import_stmt in content, f"Missing import: {import_stmt}"

    def test_script_has_required_functions(self, script_path: Path):
        """Verify script has all required functions from Task 2."""
        content = script_path.read_text()

        required_functions = [
            "get_postgres_version",
            "get_hardware_info",
            "get_row_counts",
            "get_metadata",
            "measure_hybrid_search",
            "measure_graph_query_neighbors_1hop",
            "measure_graph_query_neighbors_3hop",
            "measure_compress_to_l2_insight",
            "validate_baseline_json",
            "main_async",
            "main",
        ]

        for func in required_functions:
            assert f"def {func}" in content or f"async def {func}" in content, (
                f"Missing function: {func}"
            )

    def test_script_has_correct_measurement_protocol(self, script_path: Path):
        """Verify script uses correct measurement protocol (AC2)."""
        content = script_path.read_text()

        # Check for warmup and measured iterations
        assert "WARMUP_ITERATIONS = 5" in content, "Should have 5 warmup iterations"
        assert "MEASURED_ITERATIONS = 100" in content, "Should have 100 measured iterations"

    def test_script_has_json_schema_validation(self, script_path: Path):
        """Verify script has JSON schema validation (Task 4.4)."""
        content = script_path.read_text()

        assert "BASELINE_SCHEMA" in content, "Should define BASELINE_SCHEMA"
        assert "validate_baseline_json" in content, "Should have validation function"

    def test_script_outputs_to_correct_path(self, script_path: Path):
        """Verify script outputs to correct path (AC2)."""
        content = script_path.read_text()

        assert 'OUTPUT_FILE = OUTPUT_DIR / "baseline_pre_rls.json"' in content, (
            "Should output to tests/performance/baseline_pre_rls.json"
        )

    def test_performance_measurement_class_exists(self, script_path: Path):
        """Verify PerformanceMeasurement class exists."""
        content = script_path.read_text()

        assert "class PerformanceMeasurement:" in content, (
            "Should have PerformanceMeasurement class"
        )


class TestCompareRlsOverheadScript:
    """Test the RLS overhead comparison script structure and CLI."""

    @pytest.fixture
    def script_path(self) -> Path:
        """Path to the comparison script."""
        return Path("scripts/compare_rls_overhead.py")

    def test_script_exists(self, script_path: Path):
        """Test that the script file exists."""
        assert script_path.exists(), f"Script not found: {script_path}"

    def test_script_has_required_imports(self, script_path: Path):
        """Verify script has required imports."""
        content = script_path.read_text()

        required_imports = [
            "from mcp_server.db.connection import initialize_pool",
            "from mcp_server.tools import handle_hybrid_search",
            "from mcp_server.tools.graph_query_neighbors import handle_graph_query_neighbors",
            "from mcp_server.tools import handle_compress_to_l2_insight",
        ]

        for import_stmt in required_imports:
            assert import_stmt in content, f"Missing import: {import_stmt}"

    def test_script_has_required_functions(self, script_path: Path):
        """Verify script has all required functions from Task 3."""
        content = script_path.read_text()

        required_functions = [
            "measure_query_performance",
            "measure_post_rls_hybrid_search",
            "measure_post_rls_graph_query_1hop",
            "measure_post_rls_graph_query_3hop",
            "measure_post_rls_compress_to_l2_insight",
            "calculate_delta",
            "compare_against_baseline",
            "main_async",
            "main",
        ]

        for func in required_functions:
            assert f"def {func}" in content or f"async def {func}" in content, (
                f"Missing function: {func}"
            )

    def test_script_has_correct_nfr2_threshold(self, script_path: Path):
        """Verify script uses correct NFR2 threshold (AC3)."""
        content = script_path.read_text()

        assert "NFR2_THRESHOLD_MS = 10.0" in content, (
            "Should have NFR2 threshold of 10ms"
        )

    def test_script_loads_correct_baseline_path(self, script_path: Path):
        """Verify script loads from correct baseline path."""
        content = script_path.read_text()

        assert 'BASELINE_FILE = Path("tests/performance/baseline_pre_rls.json")' in content, (
            "Should load baseline from tests/performance/baseline_pre_rls.json"
        )

    def test_calculate_delta_logic(self):
        """Test AC3: delta calculation is correct."""
        # Import the function
        import sys
        sys.path.insert(0, str(Path("scripts").parent))

        from scripts.compare_rls_overhead import calculate_delta

        # Test delta calculation
        assert calculate_delta(100.0, 105.0) == 5.0, "Delta should be 5.0"
        assert calculate_delta(100.0, 100.0) == 0.0, "Delta should be 0.0"
        assert calculate_delta(100.0, 95.0) == -5.0, "Negative delta allowed (improvement)"

    def test_script_measures_all_four_queries(self, script_path: Path):
        """Verify script measures all 4 queries like baseline does."""
        content = script_path.read_text()

        required_measurements = [
            "hybrid_search_semantic_top10",
            "graph_query_neighbors_1hop",
            "graph_query_neighbors_3hop",
            "compress_to_l2_insight",
        ]

        for measurement in required_measurements:
            assert f'"{measurement}"' in content, (
                f"Missing measurement for: {measurement}"
            )


class TestBaselineScriptsSyntax:
    """Test that scripts have valid Python syntax."""

    def test_capture_baseline_syntax(self):
        """Verify capture_baseline.py has valid syntax."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", "scripts/capture_baseline.py"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_compare_rls_overhead_syntax(self):
        """Verify compare_rls_overhead.py has valid syntax."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", "scripts/compare_rls_overhead.py"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"
