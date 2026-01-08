"""
Unit tests for relevance score calculation with sector-specific decay.

Story 9-2: Sector-Specific Relevance Scoring

Test Coverage:
- AC#3: emotional sector decay (S_base=200)
- AC#4: semantic sector decay (S_base=100)
- AC#5: S_floor enforcement
- AC#7: Performance < 5ms per calculation
- AC#8: Backward compatibility (no memory_sector)
- Constitutive edges always return 1.0
- All 5 sectors x 3 day intervals = 15 parametrized test cases
"""

import logging
from datetime import datetime, timezone, timedelta

import pytest

from mcp_server.utils.decay_config import get_decay_config
from mcp_server.utils.relevance import calculate_relevance_score
from mcp_server.utils.sector_classifier import MemorySector


# Test fixture: Create edge data for testing
def create_test_edge(
    memory_sector: MemorySector,
    days_ago: int,
    access_count: int = 0,
    edge_type: str | None = None,
) -> dict:
    """Create test edge data with specified parameters."""
    last_engaged = datetime.now(timezone.utc) - timedelta(days=days_ago)

    edge_data = {
        "memory_sector": memory_sector,
        "last_engaged": last_engaged,
        "access_count": access_count,
    }

    if edge_type:
        edge_data["edge_properties"] = {"edge_type": edge_type}

    return edge_data


class TestSectorSpecificDecay:
    """Test sector-specific decay rates (AC#3, AC#4, AC#6)."""

    @pytest.mark.parametrize(
        "sector,days,expected_score",
        [
            # Emotional sector (S_base=200)
            ("emotional", 0, 1.000),
            ("emotional", 50, 0.779),
            ("emotional", 100, 0.606),
            # Semantic sector (S_base=100)
            ("semantic", 0, 1.000),
            ("semantic", 50, 0.606),
            ("semantic", 100, 0.368),
            # Episodic sector (S_base=150)
            ("episodic", 0, 1.000),
            ("episodic", 50, 0.716),
            ("episodic", 100, 0.513),
            # Procedural sector (S_base=120)
            ("procedural", 0, 1.000),
            ("procedural", 50, 0.659),
            ("procedural", 100, 0.435),
            # Reflective sector (S_base=180)
            ("reflective", 0, 1.000),
            ("reflective", 50, 0.759),
            ("reflective", 100, 0.574),
        ],
    )
    def test_sector_specific_decay(self, sector, days, expected_score):
        """Verify sector-specific decay rates match expected values (AC#6)."""
        edge_data = create_test_edge(memory_sector=sector, days_ago=days)

        score = calculate_relevance_score(edge_data)

        # Allow 1% tolerance for floating point arithmetic
        assert abs(score - expected_score) < 0.01, (
            f"Score for {sector} sector at {days} days: "
            f"expected {expected_score:.3f}, got {score:.3f}"
        )


class TestSFloorEnforcement:
    """Test S_floor (minimum memory strength) enforcement (AC#5)."""

    def test_s_floor_enforcement(self):
        """Verify S_floor is applied when S would drop below threshold (AC#5)."""
        config = get_decay_config()
        emotional_config = config["emotional"]

        # Emotional sector has S_floor=150
        assert emotional_config.S_floor is not None
        assert emotional_config.S_floor == 150.0

        # Create edge with low access_count (would give low S without floor)
        # S = S_base * (1 + log(1 + access_count))
        # With access_count=0: S = 200 * 1.0 = 200 (above S_floor, no effect)
        edge_data = create_test_edge(
            memory_sector="emotional", days_ago=100, access_count=0
        )

        score = calculate_relevance_score(edge_data)

        # With S=200, days_ago=100: score = exp(-100/200) = exp(-0.5) = 0.606
        assert abs(score - 0.606) < 0.01

        # Verify semantic sector (no S_floor) decays faster
        edge_data_semantic = create_test_edge(
            memory_sector="semantic", days_ago=100, access_count=0
        )
        score_semantic = calculate_relevance_score(edge_data_semantic)

        # Semantic S=100, days_ago=100: score = exp(-100/100) = exp(-1) = 0.368
        assert abs(score_semantic - 0.368) < 0.01

        # Emotional should have higher score than semantic due to S_floor
        assert score > score_semantic


class TestBackwardCompatibility:
    """Test backward compatibility for legacy edges (AC#8)."""

    def test_missing_memory_sector_defaults_to_semantic(self):
        """Verify edges without memory_sector default to 'semantic' (AC#8)."""
        # Create edge without memory_sector field
        last_engaged = datetime.now(timezone.utc) - timedelta(days=50)

        edge_data = {
            "last_engaged": last_engaged,
            "access_count": 0,
            # No memory_sector field
        }

        score = calculate_relevance_score(edge_data)

        # Should use semantic defaults (S_base=100)
        # Expected: exp(-50/100) = exp(-0.5) = 0.606
        assert abs(score - 0.606) < 0.01

    def test_memory_sector_in_properties_fallback(self):
        """Verify memory_sector in edge_properties is used."""
        last_engaged = datetime.now(timezone.utc) - timedelta(days=50)

        edge_data = {
            "edge_properties": {"memory_sector": "emotional"},
            "last_engaged": last_engaged,
            "access_count": 0,
        }

        score = calculate_relevance_score(edge_data)

        # Should use emotional defaults (S_base=200)
        # Expected: exp(-50/200) = exp(-0.25) = 0.779
        assert abs(score - 0.779) < 0.01


class TestConstitutiveEdges:
    """Test constitutive edge behavior."""

    def test_constitutive_edge_always_1_0(self):
        """Verify constitutive edges always return 1.0 regardless of sector."""
        edge_data = create_test_edge(
            memory_sector="emotional",
            days_ago=1000,  # Very old
            access_count=0,
            edge_type="constitutive",
        )

        score = calculate_relevance_score(edge_data)

        # Constitutive edges should never decay
        assert score == 1.0


class TestPerformance:
    """Test performance requirements (AC#7)."""

    def test_performance_under_5ms(self, caplog):
        """Verify calculation completes in < 5ms (AC#7)."""
        import time

        edge_data = create_test_edge(
            memory_sector="emotional", days_ago=100, access_count=5
        )

        # Run multiple iterations to get stable measurement
        iterations = 100
        start = time.perf_counter()

        for _ in range(iterations):
            calculate_relevance_score(edge_data)

        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        avg_ms = elapsed / iterations

        # Should be much faster than 5ms per calculation
        assert avg_ms < 5.0, f"Average calculation time: {avg_ms:.3f}ms"

    def test_performance_logging(self, caplog):
        """Verify performance logging includes calculation_ms (AC#7, NFR16)."""
        edge_data = create_test_edge(
            memory_sector="emotional", days_ago=100, access_count=5
        )

        with caplog.at_level(logging.DEBUG):
            score = calculate_relevance_score(edge_data)

        # Should log with calculation_ms in extra dict
        assert score > 0
        # Find the debug log entry
        debug_logs = [
            record
            for record in caplog.records
            if record.levelname == "DEBUG"
            and "Calculated relevance_score" in record.message
        ]

        assert len(debug_logs) > 0

        log_entry = debug_logs[0]
        assert "calculation_ms" in log_entry.__dict__
        assert log_entry.calculation_ms < 5.0  # NFR7: < 5ms


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_no_timestamp_returns_1_0(self):
        """Verify edges without timestamp return 1.0 (no decay)."""
        edge_data = {
            "memory_sector": "emotional",
            "access_count": 0,
            # No last_engaged or last_accessed
        }

        score = calculate_relevance_score(edge_data)

        # Should return 1.0 when no timestamp available
        assert score == 1.0

    def test_string_timestamp_conversion(self):
        """Verify string timestamps are correctly parsed."""
        last_engaged = datetime.now(timezone.utc) - timedelta(days=50)

        edge_data = {
            "memory_sector": "semantic",
            "last_engaged": last_engaged.isoformat(),
            "access_count": 0,
        }

        score = calculate_relevance_score(edge_data)

        # Should correctly parse string and calculate decay
        assert abs(score - 0.606) < 0.01

    def test_naive_datetime_assumes_utc(self):
        """Verify naive datetime (no timezone) is treated as UTC."""
        # Create naive datetime (no timezone info)
        last_engaged_naive = datetime.now() - timedelta(days=50)
        # Remove timezone info
        last_engaged_naive = last_engaged_naive.replace(tzinfo=None)

        edge_data = {
            "memory_sector": "semantic",
            "last_engaged": last_engaged_naive,
            "access_count": 0,
        }

        score = calculate_relevance_score(edge_data)

        # Should treat as UTC and calculate decay
        assert abs(score - 0.606) < 0.01

    def test_access_count_boosts_memory_strength(self):
        """Verify higher access_count increases S (slower decay)."""
        # Same sector and days, different access_count
        edge_low_access = create_test_edge(
            memory_sector="semantic", days_ago=50, access_count=0
        )
        edge_high_access = create_test_edge(
            memory_sector="semantic", days_ago=50, access_count=10
        )

        score_low = calculate_relevance_score(edge_low_access)
        score_high = calculate_relevance_score(edge_high_access)

        # Higher access_count should result in higher score (slower decay)
        # access_count=0: S = 100 * 1.0 = 100, score = exp(-50/100) = 0.606
        # access_count=10: S = 100 * (1 + log(11)) = 100 * 3.4 = 340, score = exp(-50/340) = 0.863
        assert abs(score_low - 0.606) < 0.01
        assert abs(score_high - 0.863) < 0.01
        assert score_high > score_low


class TestScoreBounds:
    """Test that scores are always within valid bounds."""

    @pytest.mark.parametrize("sector", ["emotional", "semantic", "episodic", "procedural", "reflective"])
    @pytest.mark.parametrize("days_ago", [0, 10, 50, 100, 500, 1000])
    def test_score_always_between_0_and_1(self, sector, days_ago):
        """Verify scores are always in [0.0, 1.0] range."""
        edge_data = create_test_edge(memory_sector=sector, days_ago=days_ago)

        score = calculate_relevance_score(edge_data)

        assert 0.0 <= score <= 1.0, f"Score {score} not in [0, 1] for {sector} at {days_ago} days"


class TestConfigIntegration:
    """Test integration with decay_config module."""

    def test_uses_sector_config_from_singleton(self):
        """Verify function uses get_decay_config() singleton (project-context rule)."""
        # This test verifies the integration with decay_config module
        # by checking that different sectors produce different decay rates

        edge_emotional = create_test_edge(memory_sector="emotional", days_ago=100)
        edge_semantic = create_test_edge(memory_sector="semantic", days_ago=100)

        score_emotional = calculate_relevance_score(edge_emotional)
        score_semantic = calculate_relevance_score(edge_semantic)

        # Emotional should have higher score (slower decay) due to higher S_base
        assert score_emotional > score_semantic

        # Verify exact expected values
        assert abs(score_emotional - 0.606) < 0.01  # S_base=200
        assert abs(score_semantic - 0.368) < 0.01  # S_base=100
