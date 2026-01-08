"""
Test Fixtures Package

This package contains test fixtures for unit and integration tests.
Fixtures are reusable test data that support deterministic testing.
"""

import pytest

from tests.fixtures.golden_set_sectors import GOLDEN_SET_SECTORS


@pytest.fixture
def golden_set_edges():
    """
    Fixture providing golden set of pre-classified edges for testing.

    Returns the complete list of 20 pre-classified edges covering all 5 sectors.
    """
    return GOLDEN_SET_SECTORS

