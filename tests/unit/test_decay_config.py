"""
Unit tests for decay configuration module.

Tests cover:
- Valid YAML loading (AC #1, #2)
- Fallback on missing file (AC #3)
- Fallback on invalid YAML (AC #3)
- Singleton caching (AC #5)
- Config load time < 1s (AC #4)
- Sector validation (enhancement)
"""

from pathlib import Path
import pytest
from mcp_server.utils.decay_config import (
    get_decay_config,
    SectorDecay,
    DEFAULT_DECAY_CONFIG,
    _config_cache,
)
from mcp_server.utils.sector_classifier import MemorySector


class TestSectorDecayDataclass:
    """Test SectorDecay dataclass (AC #1)."""

    def test_sector_decay_creation(self):
        """SectorDecay can be created with S_base and optional S_floor."""
        decay = SectorDecay(S_base=200.0, S_floor=150.0)
        assert decay.S_base == 200.0
        assert decay.S_floor == 150.0

    def test_sector_decay_without_floor(self):
        """SectorDecay S_floor can be None (AC #1)."""
        decay = SectorDecay(S_base=100.0, S_floor=None)
        assert decay.S_base == 100.0
        assert decay.S_floor is None

    def test_sector_decay_immutability(self):
        """SectorDecay is frozen=True - immutable after creation."""
        decay = SectorDecay(S_base=200.0, S_floor=150.0)
        with pytest.raises(Exception):  # FrozenInstanceError
            decay.S_base = 250.0


class TestDefaultDecayConfig:
    """Test DEFAULT_DECAY_CONFIG constant (AC #3)."""

    def test_default_config_exists(self):
        """DEFAULT_DECAY_CONFIG is defined and contains all 5 sectors."""
        assert DEFAULT_DECAY_CONFIG is not None
        assert len(DEFAULT_DECAY_CONFIG) == 5

    def test_default_config_all_sectors_present(self):
        """DEFAULT_DECAY_CONFIG contains all required sectors."""
        required_sectors = {"emotional", "episodic", "semantic", "procedural", "reflective"}
        actual_sectors = set(DEFAULT_DECAY_CONFIG.keys())
        assert actual_sectors == required_sectors

    def test_default_config_values(self):
        """DEFAULT_DECAY_CONFIG has expected values from AC #2."""
        emotional = DEFAULT_DECAY_CONFIG["emotional"]
        assert emotional.S_base == 200.0
        assert emotional.S_floor == 150.0

        semantic = DEFAULT_DECAY_CONFIG["semantic"]
        assert semantic.S_base == 100.0
        assert semantic.S_floor is None


class TestValidYAMLLoading:
    """Test valid YAML loading (AC #1, #2)."""

    def test_get_decay_config_returns_dict(self):
        """get_decay_config() returns dict mapping sectors to SectorDecay (AC #1)."""
        config = get_decay_config()
        assert isinstance(config, dict)
        assert len(config) == 5

    def test_get_decay_config_all_sectors_loaded(self):
        """All 5 sectors are loaded with correct values (AC #2)."""
        config = get_decay_config()

        # Check emotional sector
        emotional = config["emotional"]
        assert isinstance(emotional, SectorDecay)
        assert emotional.S_base == 200.0
        assert emotional.S_floor == 150.0

        # Check semantic sector
        semantic = config["semantic"]
        assert semantic.S_base == 100.0
        assert semantic.S_floor is None

        # Check episodic sector
        episodic = config["episodic"]
        assert episodic.S_base == 150.0
        assert episodic.S_floor == 100.0

        # Check procedural sector
        procedural = config["procedural"]
        assert procedural.S_base == 120.0
        assert procedural.S_floor is None

        # Check reflective sector
        reflective = config["reflective"]
        assert reflective.S_base == 180.0
        assert reflective.S_floor == 120.0


class TestFallbackOnMissingFile:
    """Test fallback on missing file (AC #3)."""

    def test_fallback_on_missing_file(self, caplog, monkeypatch, tmp_path):
        """get_decay_config() falls back to defaults when file missing (AC #3)."""
        # Mock config path to non-existent file
        fake_config_path = tmp_path / "nonexistent" / "decay_config.yaml"

        import mcp_server.utils.decay_config as decay_module
        monkeypatch.setattr(
            decay_module,
            "_get_config_path",
            lambda: fake_config_path,
        )

        # Reset cache to force reload
        monkeypatch.setattr(decay_module, "_config_cache", None)

        config = get_decay_config()

        assert config == DEFAULT_DECAY_CONFIG
        assert "Falling back to default decay config" in caplog.text


class TestFallbackOnInvalidYAML:
    """Test fallback on invalid YAML (AC #3)."""

    def test_fallback_on_invalid_yaml(self, caplog, monkeypatch, tmp_path):
        """get_decay_config() falls back to defaults when YAML is invalid (AC #3)."""
        # Create invalid YAML file
        invalid_config = tmp_path / "decay_config.yaml"
        invalid_config.write_text("invalid: yaml: content: [")

        import mcp_server.utils.decay_config as decay_module
        monkeypatch.setattr(
            decay_module,
            "_get_config_path",
            lambda: invalid_config,
        )

        # Reset cache to force reload
        monkeypatch.setattr(decay_module, "_config_cache", None)

        config = get_decay_config()

        assert config == DEFAULT_DECAY_CONFIG
        assert "Falling back to default decay config" in caplog.text


class TestFallbackOnMissingDecayConfigKey:
    """Test fallback on missing 'decay_config' key."""

    def test_fallback_on_missing_key(self, caplog, monkeypatch, tmp_path):
        """get_decay_config() falls back to defaults when 'decay_config' key missing."""
        # Create YAML without decay_config key
        invalid_config = tmp_path / "decay_config.yaml"
        invalid_config.write_text("wrong_key:\n  emotional:\n    S_base: 200")

        import mcp_server.utils.decay_config as decay_module
        monkeypatch.setattr(
            decay_module,
            "_get_config_path",
            lambda: invalid_config,
        )

        # Reset cache to force reload
        monkeypatch.setattr(decay_module, "_config_cache", None)

        config = get_decay_config()

        assert config == DEFAULT_DECAY_CONFIG
        assert "Falling back to default decay config" in caplog.text


class TestFallbackOnMissingSectors:
    """Test fallback on missing required sectors (enhancement)."""

    def test_fallback_on_missing_sectors(self, caplog, monkeypatch, tmp_path):
        """get_decay_config() falls back to defaults when sectors are missing."""
        # Create YAML with only 3 sectors
        incomplete_config = tmp_path / "decay_config.yaml"
        incomplete_config.write_text(
            "decay_config:\n"
            "  emotional:\n"
            "    S_base: 200\n"
            "    S_floor: 150\n"
            "  semantic:\n"
            "    S_base: 100\n"
            "    S_floor: null\n"
            "  episodic:\n"
            "    S_base: 150\n"
            "    S_floor: 100\n"
        )

        import mcp_server.utils.decay_config as decay_module
        monkeypatch.setattr(
            decay_module,
            "_get_config_path",
            lambda: incomplete_config,
        )

        # Reset cache to force reload
        monkeypatch.setattr(decay_module, "_config_cache", None)

        config = get_decay_config()

        assert config == DEFAULT_DECAY_CONFIG
        assert "Falling back to default decay config" in caplog.text


class TestSingletonCaching:
    """Test singleton caching (AC #5)."""

    def test_singleton_caching(self, monkeypatch):
        """get_decay_config() returns cached config on subsequent calls (AC #5)."""
        import mcp_server.utils.decay_config as decay_module

        # Reset cache
        monkeypatch.setattr(decay_module, "_config_cache", None)

        # First call
        config1 = get_decay_config()
        assert decay_module._config_cache is not None

        # Second call should return cached version
        config2 = get_decay_config()

        assert config1 is config2  # Same object reference

    def test_cache_persists_across_calls(self):
        """Cached config persists across multiple get_decay_config() calls."""
        config1 = get_decay_config()
        config2 = get_decay_config()
        config3 = get_decay_config()

        assert config1 is config2 is config3


class TestConfigLoadTime:
    """Test config load time < 1s (AC #4)."""

    def test_config_load_time_nfr4(self):
        """Config loading must complete in <1s (AC #4, NFR4)."""
        import time

        # Reset cache to ensure actual load
        import mcp_server.utils.decay_config as decay_module
        decay_module._config_cache = None

        start_time = time.time()
        config = get_decay_config()
        elapsed = time.time() - start_time

        assert config is not None
        assert len(config) == 5  # All sectors loaded
        assert elapsed < 1.0, f"Config load took {elapsed:.3f}s, exceeds 1s limit (NFR4)"
