"""
TGN (Temporal Graph Network) Tests for Stories 7.2 & 7.3

Tests for:
- Auto-update functionality of edge access statistics (Story 7.2)
- Memory Strength and relevance_score calculation (Story 7.3)

Story 7.2: TGN Minimal - Auto-Update bei Lese-Operationen
Story 7.3: TGN Minimal - Decay mit Memory Strength
"""

import pytest
import time
from datetime import datetime, timezone, timedelta

from mcp_server.db.connection import get_connection
from mcp_server.db.graph import (
    _update_edge_access_stats,
    get_edge_by_names,
    query_neighbors,
    find_path,
    add_node,
    add_edge,
    calculate_relevance_score,
    get_edge_by_id
)


class TestTGNAutoUpdate:
    """Test suite for TGN auto-update functionality."""

    def setup_method(self):
        """Setup test data before each test."""
        self.test_nodes = {}
        self.test_edges = {}

        with get_connection() as conn:
            cursor = conn.cursor()

            # Clean up any existing test data
            cursor.execute("DELETE FROM edges WHERE relation LIKE 'TEST_%';")
            cursor.execute("DELETE FROM nodes WHERE name LIKE 'test_node_%';")
            conn.commit()

            # Create test nodes
            test_data = [
                ("test_node_A", "NodeA", '{"description": "Test Node A"}'),
                ("test_node_B", "NodeB", '{"description": "Test Node B"}'),
                ("test_node_C", "NodeC", '{"description": "Test Node C"}'),
                ("test_node_D", "NodeD", '{"description": "Test Node D"}'),
                ("test_node_E", "NodeE", '{"description": "Test Node E"}'),
            ]

            for name, label, properties in test_data:
                result = add_node(label, name, properties)
                self.test_nodes[name] = result["node_id"]

            # Create test edges with initial access_count = 0
            edge_data = [
                ("test_node_A", "test_node_B", "TEST_DIRECTED"),
                ("test_node_A", "test_node_C", "TEST_BIDIRECTIONAL"),
                ("test_node_B", "test_node_C", "TEST_WEIGHTED", 0.8),
                ("test_node_C", "test_node_D", "TEST_DIRECTED"),
                ("test_node_D", "test_node_E", "TEST_FINAL"),
            ]

            for source, target, relation, weight in [(e[0], e[1], e[2], e[3] if len(e) > 3 else 1.0) for e in edge_data]:
                result = add_edge(
                    self.test_nodes[source],
                    self.test_nodes[target],
                    relation,
                    weight
                )
                self.test_edges[f"{source}_{target}_{relation}"] = result["edge_id"]

            # Reset access_count and last_accessed for all test edges
            cursor.execute(
                """
                UPDATE edges
                SET access_count = 0, last_accessed = NOW() - INTERVAL '1 hour'
                WHERE relation LIKE 'TEST_%';
                """
            )
            conn.commit()

    def test_get_edge_by_names_updates_access_count(self):
        """Test 1: get_edge_by_names updates access_count (AC: #1)."""
        # Get initial state
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT access_count, last_accessed
                FROM edges
                WHERE id = %s;
                """,
                (self.test_edges["test_node_A_test_node_B_TEST_DIRECTED"],)
            )
            initial = cursor.fetchone()
            initial_count = initial["access_count"]
            initial_time = initial["last_accessed"]

        # Wait a bit to ensure timestamp difference
        time.sleep(0.01)

        # Call get_edge_by_names
        result = get_edge_by_names("test_node_A", "test_node_B", "TEST_DIRECTED")

        assert result is not None
        assert result["relation"] == "TEST_DIRECTED"

        # Verify access stats were updated
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT access_count, last_accessed
                FROM edges
                WHERE id = %s;
                """,
                (self.test_edges["test_node_A_test_node_B_TEST_DIRECTED"],)
            )
            updated = cursor.fetchone()

            assert updated["access_count"] == initial_count + 1
            assert updated["last_accessed"] > initial_time

    def test_query_neighbors_updates_all_edge_access_counts(self):
        """Test 2: query_neighbors updates all edges in result (AC: #2)."""
        # Get initial access counts for all edges connected to test_node_A
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT e.id, e.access_count, e.last_accessed
                FROM edges e
                JOIN nodes ns ON e.source_id = ns.id
                WHERE ns.name = 'test_node_A'
                AND e.relation LIKE 'TEST_%';
                """
            )
            initial_stats = {str(row["id"]): (row["access_count"], row["last_accessed"])
                           for row in cursor.fetchall()}

        # Wait a bit to ensure timestamp difference
        time.sleep(0.01)

        # Call query_neighbors
        neighbors = query_neighbors(self.test_nodes["test_node_A"])

        # Should find neighbors B and C
        neighbor_names = [n["name"] for n in neighbors]
        assert "test_node_B" in neighbor_names
        assert "test_node_C" in neighbor_names

        # Verify all edges from A were updated
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT e.id, e.access_count, e.last_accessed
                FROM edges e
                JOIN nodes ns ON e.source_id = ns.id
                WHERE ns.name = 'test_node_A'
                AND e.relation LIKE 'TEST_%';
                """
            )
            updated_stats = {str(row["id"]): (row["access_count"], row["last_accessed"])
                           for row in cursor.fetchall()}

            for edge_id, (initial_count, initial_time) in initial_stats.items():
                updated_count, updated_time = updated_stats[edge_id]
                assert updated_count == initial_count + 1
                assert updated_time > initial_time

    def test_find_path_updates_all_edge_access_counts(self):
        """Test 3: find_path updates all edges in path (AC: #3)."""
        # Use the direct path: A -> C (TEST_BIDIRECTIONAL)
        # find_path will find the shortest path, which is the direct edge
        edge_key = "test_node_A_test_node_C_TEST_BIDIRECTIONAL"
        edge_id = self.test_edges[edge_key]

        # Get initial access count for the edge
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT access_count, last_accessed
                FROM edges
                WHERE id = %s;
                """,
                (edge_id,)
            )
            initial = cursor.fetchone()
            initial_count = initial["access_count"]
            initial_time = initial["last_accessed"]

        # Wait a bit to ensure timestamp difference
        time.sleep(0.01)

        # Call find_path - should find A -> C direct path
        result = find_path("test_node_A", "test_node_C", max_depth=2)

        assert result["path_found"] is True
        assert len(result["paths"]) > 0

        # Verify the edge in the path was updated
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT access_count, last_accessed
                FROM edges
                WHERE id = %s;
                """,
                (edge_id,)
            )
            updated = cursor.fetchone()

            assert updated["access_count"] == initial_count + 1
            assert updated["last_accessed"] > initial_time

    def test_update_edge_access_stats_bulk_operation(self):
        """Test 4: Bulk operation efficiency."""
        # Get a list of test edge IDs
        edge_ids = list(self.test_edges.values())

        # Get initial counts
        with get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join(["%s"] * len(edge_ids))
            cursor.execute(
                f"""
                SELECT id, access_count
                FROM edges
                WHERE id IN ({placeholders});
                """,
                edge_ids
            )
            initial_counts = {str(row["id"]): row["access_count"] for row in cursor.fetchall()}

        # Call the helper function with multiple edges
        with get_connection() as conn:
            _update_edge_access_stats(edge_ids, conn)

        # Verify all edges were updated in a single operation
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT id, access_count
                FROM edges
                WHERE id IN ({placeholders});
                """,
                edge_ids
            )
            updated_counts = {str(row["id"]): row["access_count"] for row in cursor.fetchall()}

            for edge_id in edge_ids:
                assert updated_counts[edge_id] == initial_counts[edge_id] + 1

    def test_update_edge_access_stats_silent_fail_on_error(self):
        """Test 5: Silent fail on error (non-existent edge)."""
        # Test with non-existent edge IDs
        fake_edge_ids = [
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        ]

        # Should not raise an exception
        with get_connection() as conn:
            # This should fail silently without raising
            _update_edge_access_stats(fake_edge_ids, conn)

        # Also test with empty list (should do nothing)
        with get_connection() as conn:
            _update_edge_access_stats([], conn)

    def test_multiple_access_count_increments(self):
        """Test 6: Multiple increments accumulate correctly."""
        edge_id = self.test_edges["test_node_A_test_node_B_TEST_DIRECTED"]

        # Call get_edge_by_names multiple times
        for i in range(3):
            get_edge_by_names("test_node_A", "test_node_B", "TEST_DIRECTED")
            time.sleep(0.001)  # Small delay

        # Verify count incremented correctly
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT access_count FROM edges WHERE id = %s;",
                (edge_id,)
            )
            result = cursor.fetchone()
            assert result["access_count"] == 3

    def test_access_count_never_goes_negative(self):
        """Test 7: access_count has CHECK constraint (never negative)."""
        edge_id = self.test_edges["test_node_A_test_node_B_TEST_DIRECTED"]

        # Try to manually set negative count (should fail due to CHECK constraint)
        with get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(Exception):  # Should raise due to CHECK constraint
                cursor.execute(
                    "UPDATE edges SET access_count = -1 WHERE id = %s;",
                    (edge_id,)
                )
                conn.commit()

    def test_direction_filtering_with_auto_update(self):
        """Test 8: query_neighbors with direction filtering still updates edges."""
        # Get initial stats for outgoing edges from A
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT e.id, e.access_count
                FROM edges e
                JOIN nodes ns ON e.source_id = ns.id
                WHERE ns.name = 'test_node_A'
                AND e.relation LIKE 'TEST_%';
                """
            )
            initial_outgoing = {str(row["id"]): row["access_count"] for row in cursor.fetchall()}

        # Query only outgoing neighbors
        neighbors = query_neighbors(
            self.test_nodes["test_node_A"],
            direction="outgoing"
        )

        # Should only find B and C (outgoing from A)
        neighbor_names = [n["name"] for n in neighbors]
        assert "test_node_B" in neighbor_names
        assert "test_node_C" in neighbor_names

        # Verify outgoing edges were updated
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT e.id, e.access_count
                FROM edges e
                JOIN nodes ns ON e.source_id = ns.id
                WHERE ns.name = 'test_node_A'
                AND e.relation LIKE 'TEST_%';
                """
            )
            updated_outgoing = {str(row["id"]): row["access_count"] for row in cursor.fetchall()}

            for edge_id, initial_count in initial_outgoing.items():
                assert updated_outgoing[edge_id] == initial_count + 1


class TestTGNDecayWithMemoryStrength:
    """Test suite for TGN Memory Strength and relevance_score calculation."""

    def setup_method(self):
        """Setup test data before each test."""
        self.test_nodes = {}
        self.test_edges = {}

        with get_connection() as conn:
            cursor = conn.cursor()

            # Clean up any existing test data
            cursor.execute("DELETE FROM edges WHERE relation LIKE 'DECAY_%';")
            cursor.execute("DELETE FROM nodes WHERE name LIKE 'decay_node_%';")
            conn.commit()

            # Create test nodes
            test_data = [
                ("decay_node_A", "NodeA", '{"description": "Test Node A"}'),
                ("decay_node_B", "NodeB", '{"description": "Test Node B"}'),
                ("decay_node_C", "NodeC", '{"description": "Test Node C"}'),
                ("decay_node_D", "NodeD", '{"description": "Test Node D"}'),
            ]

            for name, label, properties in test_data:
                result = add_node(label, name, properties)
                self.test_nodes[name] = result["node_id"]

    def test_relevance_score_new_edge(self):
        """Test: Frische Edge hat hohe Relevanz."""
        # Edge mit aktuellem Timestamp und access_count = 0
        edge_data = {
            "edge_properties": {},
            "last_accessed": datetime.now(timezone.utc) - timedelta(minutes=1),
            "access_count": 0
        }

        score = calculate_relevance_score(edge_data)
        assert 0.99 <= score <= 1.0

    def test_relevance_score_100_days_no_access(self):
        """Test 1: AC #1 - Edge mit 100 Tagen und keinem Zugriff."""
        # Given: Edge mit last_accessed vor 100 Tagen, access_count = 0
        edge_data = {
            "edge_properties": {},
            "last_accessed": datetime.now(timezone.utc) - timedelta(days=100),
            "access_count": 0
        }

        # When: relevance_score berechnet
        score = calculate_relevance_score(edge_data)

        # Then: Score ~0.37 (exp(-100/100) ≈ 0.368)
        assert 0.35 <= score <= 0.40

    def test_relevance_score_100_days_high_access(self):
        """Test 2: AC #2 - Edge mit 100 Tagen und hohem Zugriff."""
        # Given: Edge mit last_accessed vor 100 Tagen, access_count = 10
        edge_data = {
            "edge_properties": {},
            "last_accessed": datetime.now(timezone.utc) - timedelta(days=100),
            "access_count": 10
        }

        # When: relevance_score berechnet
        score = calculate_relevance_score(edge_data)

        # Then: Score ~0.74 (S=340 → exp(-100/340) ≈ 0.745)
        assert 0.70 <= score <= 0.78

    def test_relevance_score_constitutive(self):
        """Test 3: AC #3 - Konstitutive Edge hat immer Score 1.0."""
        # Given: Konstitutive Edge
        edge_data = {
            "edge_properties": {"edge_type": "constitutive"},
            "last_accessed": datetime.now(timezone.utc) - timedelta(days=1000),  # Sehr alt
            "access_count": 0
        }

        # When: relevance_score berechnet
        score = calculate_relevance_score(edge_data)

        # Then: Score ist immer 1.0
        assert score == 1.0

    def test_relevance_score_high_importance(self):
        """Test 5: AC #5 - Edge mit high importance nach 100 Tagen."""
        # Given: Edge mit importance = "high" (S-Floor = 200)
        edge_data = {
            "edge_properties": {"importance": "high"},
            "last_accessed": datetime.now(timezone.utc) - timedelta(days=100),
            "access_count": 0
        }

        # When: relevance_score berechnet
        score = calculate_relevance_score(edge_data)

        # Then: Score ~0.61 (exp(-100/200) ≈ 0.606)
        assert 0.58 <= score <= 0.65

    def test_relevance_score_medium_importance_floor(self):
        """Test: Medium importance S-Floor = 100."""
        # Test mit geringem access_count (würde S < 100 ergeben), aber Medium importance setzt Floor
        edge_data = {
            "edge_properties": {"importance": "medium"},
            "last_accessed": datetime.now(timezone.utc) - timedelta(days=50),
            "access_count": 0  # S = 100, floor = 100
        }

        score = calculate_relevance_score(edge_data)
        # exp(-50/100) = exp(-0.5) ≈ 0.607
        assert 0.60 <= score <= 0.62

    def test_relevance_score_low_importance_no_floor(self):
        """Test: Low importance hat keinen S-Floor."""
        # Low importance sollte kein Floor haben
        edge_data = {
            "edge_properties": {"importance": "low"},
            "last_accessed": datetime.now(timezone.utc) - timedelta(days=100),
            "access_count": 0
        }

        score = calculate_relevance_score(edge_data)
        # exp(-100/100) = exp(-1) ≈ 0.368
        assert 0.35 <= score <= 0.40

    def test_relevance_score_no_timestamp(self):
        """Test: Edge ohne last_accessed hat Score 1.0."""
        edge_data = {
            "edge_properties": {},
            "last_accessed": None,  # Kein Timestamp
            "access_count": 5
        }

        score = calculate_relevance_score(edge_data)
        assert score == 1.0

    def test_query_neighbors_has_relevance_score(self):
        """Test 4a: AC #4 - query_neighbors hat relevance_score."""
        # Setup: Edge mit bekannten Werten erstellen
        result = add_edge(
            self.test_nodes["decay_node_A"],
            self.test_nodes["decay_node_B"],
            "DECAY_TEST",
            1.0,
            '{"importance": "medium"}'
        )
        edge_id = result["edge_id"]

        # Setze last_accessed und access_count manuell
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE edges
                SET last_accessed = %s,
                    access_count = %s
                WHERE id = %s;
                """,
                (datetime.now(timezone.utc) - timedelta(days=50), 3, edge_id)
            )
            conn.commit()

        # Query neighbors
        neighbors = query_neighbors(self.test_nodes["decay_node_A"])

        # Überprüfe relevance_score existiert und ist plausibel
        assert len(neighbors) > 0
        neighbor = neighbors[0]
        assert "relevance_score" in neighbor
        assert isinstance(neighbor["relevance_score"], float)
        assert 0.0 <= neighbor["relevance_score"] <= 1.0

    def test_find_path_has_path_relevance(self):
        """Test 4b: AC #4 - find_path hat path_relevance."""
        # Erstelle direkte Verbindung A -> C für einfacheren Test
        result = add_edge(
            self.test_nodes["decay_node_A"],
            self.test_nodes["decay_node_C"],
            "DECAY_DIRECT",
            1.0,
            '{"importance": "high"}'
        )
        edge_id = result["edge_id"]

        # Setze last_accessed für reproduzierbare Ergebnisse
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE edges
                SET last_accessed = %s,
                    access_count = %s
                WHERE id = %s;
                """,
                (datetime.now(timezone.utc) - timedelta(days=10), 2, edge_id)
            )
            conn.commit()

        # Gebe der Datenbank Zeit, die Edges zu indexieren
        import time
        time.sleep(0.1)

        # Finde direkten Pfad von A nach C
        result = find_path("decay_node_A", "decay_node_C", max_depth=2)

        assert result["path_found"] is True
        assert len(result["paths"]) > 0

        # Überprüfe path_relevance existiert
        path = result["paths"][0]
        assert "path_relevance" in path
        assert isinstance(path["path_relevance"], float)
        assert 0.0 <= path["path_relevance"] <= 1.0

        # Überprüfe jede Edge hat relevance_score
        for edge in path["edges"]:
            assert "relevance_score" in edge
            assert isinstance(edge["relevance_score"], float)
            assert 0.0 <= edge["relevance_score"] <= 1.0

    def test_get_edge_by_id_function(self):
        """Test get_edge_by_id Helper Funktion."""
        # Erstelle Edge mit bekannten Werten
        result = add_edge(
            self.test_nodes["decay_node_A"],
            self.test_nodes["decay_node_B"],
            "DECAY_HELPER",
            1.0,
            '{"importance": "high", "edge_type": "descriptive"}'
        )
        edge_id = result["edge_id"]

        # Setze last_accessed und access_count
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE edges
                SET last_accessed = %s,
                    access_count = %s
                WHERE id = %s;
                """,
                (datetime.now(timezone.utc) - timedelta(days=30), 5, edge_id)
            )
            conn.commit()

        # Teste get_edge_by_id
        edge_data = get_edge_by_id(edge_id)
        assert edge_data is not None
        assert edge_data["id"] == edge_id
        assert edge_data["access_count"] == 5
        assert edge_data["edge_properties"]["importance"] == "high"

        # Teste mit nicht existierender ID
        non_existent = get_edge_by_id("00000000-0000-0000-0000-000000000001")
        assert non_existent is None

    def test_relevance_score_naive_datetime(self):
        """Test: Naive datetime (no timezone) wird korrekt behandelt."""
        # Edge mit naive datetime (könnte von manchen DB-Konfigurationen kommen)
        edge_data = {
            "edge_properties": {},
            "last_accessed": datetime(2025, 1, 1),  # Naive datetime - no timezone!
            "access_count": 0
        }

        # Should not raise TypeError, should return valid score
        score = calculate_relevance_score(edge_data)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_query_neighbors_sorted_by_relevance(self):
        """Test: query_neighbors sortiert nach relevance_score."""
        # Erstelle zwei Edges mit unterschiedlicher Relevanz
        # Edge 1: Hoch relevant (frisch)
        add_edge(
            self.test_nodes["decay_node_A"],
            self.test_nodes["decay_node_B"],
            "DECAY_HIGH_REL",
            1.0,
            '{"importance": "high"}'
        )

        # Edge 2: Niedrig relevant (alt, keine Zugriffe)
        result = add_edge(
            self.test_nodes["decay_node_A"],
            self.test_nodes["decay_node_C"],
            "DECAY_LOW_REL",
            1.0,
            '{"importance": "medium"}'
        )
        edge_id = result["edge_id"]

        # Setze Edge 2 als alt
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE edges
                SET last_accessed = %s,
                    access_count = 0
                WHERE id = %s;
                """,
                (datetime.now(timezone.utc) - timedelta(days=200), edge_id)
            )
            conn.commit()

        # Query neighbors
        neighbors = query_neighbors(self.test_nodes["decay_node_A"])

        assert len(neighbors) >= 2

        # Überprüfe Sortierung: Höchste Relevanz zuerst
        scores = [n["relevance_score"] for n in neighbors]
        assert scores == sorted(scores, reverse=True)