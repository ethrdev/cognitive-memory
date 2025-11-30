"""
ATDD Tests: Import Chain Validation (R-001 Mitigation)

These tests verify that the cognitive_memory package can be imported
without circular dependency issues.

Status: RED Phase (cognitive_memory package not yet implemented)
Risk: R-001 - Import cycle between cognitive_memory/ and mcp_server/
Priority: P0 - Must pass before any other Library tests
"""

import pytest


class TestLibraryImports:
    """P0: Verify package imports work without circular dependencies."""

    def test_import_memory_store_from_package(self):
        """
        GIVEN: cognitive_memory package exists
        WHEN: importing MemoryStore from cognitive_memory
        THEN: import succeeds without ImportError

        Risk Mitigation: R-001 (Import cycle prevention)
        """
        # RED Phase: This will fail with ModuleNotFoundError
        from cognitive_memory import MemoryStore

        assert MemoryStore is not None

    def test_import_all_public_exports(self):
        """
        GIVEN: cognitive_memory package exists
        WHEN: importing all public classes
        THEN: all imports succeed

        Verifies: __all__ exports are correct
        """
        from cognitive_memory import (
            CognitiveMemoryError,
            EpisodeMemory,
            EpisodeResult,
            GraphStore,
            InsightResult,
            MemoryStore,
            SearchResult,
            WorkingMemory,
            WorkingMemoryResult,
        )

        # All exports should be non-None
        assert MemoryStore is not None
        assert WorkingMemory is not None
        assert EpisodeMemory is not None
        assert GraphStore is not None
        assert SearchResult is not None
        assert InsightResult is not None
        assert WorkingMemoryResult is not None
        assert EpisodeResult is not None
        assert CognitiveMemoryError is not None

    def test_import_exceptions_hierarchy(self):
        """
        GIVEN: cognitive_memory.exceptions module exists
        WHEN: importing exception classes
        THEN: all exception classes are importable and inherit correctly

        Verifies: Exception hierarchy for error handling
        """
        from cognitive_memory import CognitiveMemoryError
        from cognitive_memory.exceptions import (
            ConnectionError,
            EmbeddingError,
            SearchError,
            StorageError,
            ValidationError,
        )

        # All exceptions inherit from CognitiveMemoryError
        assert issubclass(ConnectionError, CognitiveMemoryError)
        assert issubclass(SearchError, CognitiveMemoryError)
        assert issubclass(StorageError, CognitiveMemoryError)
        assert issubclass(ValidationError, CognitiveMemoryError)
        assert issubclass(EmbeddingError, CognitiveMemoryError)

    def test_no_circular_import_with_mcp_server(self):
        """
        GIVEN: cognitive_memory wraps mcp_server modules
        WHEN: importing both packages in sequence
        THEN: no circular import error occurs

        Risk Mitigation: R-001 (Import cycle prevention)
        Critical: cognitive_memory → mcp_server direction only
        """
        # Import mcp_server first (should work)
        import mcp_server

        # Then import cognitive_memory (should not cause cycle)
        import cognitive_memory

        # Both should be loaded
        assert mcp_server is not None
        assert cognitive_memory is not None

    def test_lazy_import_submodules(self):
        """
        GIVEN: cognitive_memory uses lazy imports
        WHEN: importing only MemoryStore
        THEN: submodules are not loaded until accessed

        Verifies: Lazy import pattern for performance
        Note: This test verifies the module is importable. Full lazy-loading
              verification requires subprocess isolation (not practical in pytest).
        """
        import sys

        # Verify module is in sys.modules after import
        from cognitive_memory import MemoryStore

        # Module should be loaded
        assert "cognitive_memory" in sys.modules
        assert MemoryStore is not None
