"""
Custom assertion helpers for cognitive-memory tests.

Provides domain-specific assertions for:
- Database state validation
- JSON response validation
- Cursor result validation
"""

from typing import Any, Dict, List, Optional

import pytest
from psycopg2.extras import DictCursor


def assert_database_state(
    conn,
    table: str,
    expected_count: Optional[int] = None,
    expected_conditions: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Assert database state for a specific table.

    Args:
        conn: Database connection
        table: Table name to check
        expected_count: Expected number of rows (optional)
        expected_conditions: Dict of column=expected_value (optional)

    Returns:
        List of matching rows

    Raises:
        AssertionError: If state doesn't match expectations
    """
    query = f"SELECT * FROM {table}"
    params = []

    if expected_conditions:
        conditions = []
        for key, value in expected_conditions.items():
            conditions.append(f"{key} = %s")
            params.append(value)
        query += " WHERE " + " AND ".join(conditions)

    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute(query, params)
    results = cursor.fetchall()

    if expected_count is not None:
        actual_count = len(results)
        assert (
            actual_count == expected_count
        ), f"Expected {expected_count} rows in {table}, got {actual_count}"

    return results


def assert_json_response(response_data: Dict[str, Any], expected_keys: List[str]) -> None:
    """
    Assert that a JSON response contains expected keys.

    Args:
        response_data: Parsed JSON response
        expected_keys: List of keys that must be present

    Raises:
        AssertionError: If any expected key is missing
    """
    for key in expected_keys:
        assert key in response_data, f"Missing expected key '{key}' in response"

    assert isinstance(
        response_data, dict
    ), f"Expected dict, got {type(response_data).__name__}"


def assert_cursor_result(
    cursor_result: List[Dict[str, Any]], expected_count: Optional[int] = None
) -> None:
    """
    Assert cursor result is valid.

    Args:
        cursor_result: Result from DictCursor
        expected_count: Expected number of rows (optional)

    Raises:
        AssertionError: If result is invalid
    """
    assert isinstance(
        cursor_result, list
    ), f"Expected list, got {type(cursor_result).__name__}"

    for row in cursor_result:
        assert isinstance(
            row, dict
        ), f"Expected dict rows, got {type(row).__name__} in {cursor_result}"

    if expected_count is not None:
        actual_count = len(cursor_result)
        assert (
            actual_count == expected_count
        ), f"Expected {expected_count} rows, got {actual_count}"


def assert_node_data(node: Dict[str, Any], expected_name: str) -> None:
    """
    Assert node data structure is valid.

    Args:
        node: Node data dict
        expected_name: Expected node name

    Raises:
        AssertionError: If node data is invalid
    """
    required_fields = ["id", "label", "name", "properties", "created_at"]

    for field in required_fields:
        assert field in node, f"Missing required field '{field}' in node data"

    assert node["name"] == expected_name, f"Expected name '{expected_name}', got '{node['name']}'"

    assert isinstance(
        node["properties"], dict
    ), f"Expected properties to be dict, got {type(node['properties'])}"


def assert_edge_data(edge: Dict[str, Any], expected_source: str, expected_target: str) -> None:
    """
    Assert edge data structure is valid.

    Args:
        edge: Edge data dict
        expected_source: Expected source node name
        expected_target: Expected target node name

    Raises:
        AssertionError: If edge data is invalid
    """
    required_fields = ["id", "source_id", "target_id", "relation", "weight", "created_at"]

    for field in required_fields:
        assert field in edge, f"Missing required field '{field}' in edge data"

    assert isinstance(
        edge["weight"], (int, float)
    ), f"Expected weight to be number, got {type(edge['weight'])}"

    assert 0 <= edge["weight"] <= 1, f"Weight must be 0-1, got {edge['weight']}"
