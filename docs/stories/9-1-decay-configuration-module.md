# Story 9.1: Decay Configuration Module

Status: done

## Story

As a developer (ethr),
I want to configure decay parameters per memory sector via YAML,
So that I can tune how long different memory types persist.

## Acceptance Criteria

1. **Given** a valid `config/decay_config.yaml` file
   **When** `get_decay_config()` is called
   **Then** it returns a dict mapping sector names to `SectorDecay` dataclasses
   **And** each `SectorDecay` has `S_base: float` and `S_floor: float | None`

2. **Given** `config/decay_config.yaml` with default values (see YAML Structure below)
   **When** `get_decay_config()` is called
   **Then** all 5 sectors are loaded with correct values
   **And** config validates that all required sectors exist

3. **Given** `config/decay_config.yaml` is missing or invalid
   **When** `get_decay_config()` is called
   **Then** it returns `DEFAULT_DECAY_CONFIG` with the same 5 sector values as above
   **And** a warning is logged with `logger.warning("Falling back to default decay config")`

4. **Given** config loading
   **When** server starts
   **Then** config loading completes in less than 1 second (NFR4)

5. **Given** `get_decay_config()` is called multiple times
   **When** the config is already loaded
   **Then** it returns the cached config (singleton pattern)

## Tasks / Subtasks

- [x] Task 1: Create `config/decay_config.yaml` (AC: #2)
  - [x] Subtask 1.1: Create `config/` directory if not exists
  - [x] Subtask 1.2: Create YAML file with 5 sector configurations
  - [x] Subtask 1.3: Validate YAML structure against AC #2 format

- [x] Task 2: Create `SectorDecay` dataclass (AC: #1)
  - [x] Subtask 2.1: Create `mcp_server/utils/decay_config.py`
  - [x] Subtask 2.2: Define `SectorDecay` dataclass with `S_base: float` and `S_floor: float | None`
  - [x] Subtask 2.3: Add type hints and docstring

- [x] Task 3: Create `DEFAULT_DECAY_CONFIG` constant (AC: #3)
  - [x] Subtask 3.1: Define dict mapping `MemorySector` to `SectorDecay`
  - [x] Subtask 3.2: Use values from AC #2 YAML example
  - [x] Subtask 3.3: Export from module for use in fallback

- [x] Task 4: Implement `get_decay_config()` function (AC: #1, #3, #5)
  - [x] Subtask 4.1: Implement YAML loading with `yaml.safe_load()`
  - [x] Subtask 4.2: Implement singleton pattern with module-level `_config_cache`
  - [x] Subtask 4.3: Implement fallback to `DEFAULT_DECAY_CONFIG` on error
  - [x] Subtask 4.4: Add `logger.warning()` for fallback case (AC: #3)
  - [x] Subtask 4.5: Return `dict[MemorySector, SectorDecay]` type

- [x] Task 5: Add unit tests (AC: #1-5)
  - [x] Subtask 5.1: Create `tests/unit/test_decay_config.py`
  - [x] Subtask 5.2: Test valid YAML loading (AC: #1, #2)
  - [x] Subtask 5.3: Test fallback on missing file (AC: #3)
  - [x] Subtask 5.4: Test fallback on invalid YAML (AC: #3)
  - [x] Subtask 5.5: Test singleton caching (AC: #5)
  - [x] Subtask 5.6: Test config load time < 1s (AC: #4)

- [x] Task 6: Validate mypy strict compliance
  - [x] Subtask 6.1: Run `mypy --strict mcp_server/utils/decay_config.py`
  - [x] Subtask 6.2: Fix any type annotation issues

- [x] Task 7: Run full test suite
  - [x] Subtask 7.1: Run `pytest tests/unit/test_decay_config.py -v`
  - [x] Subtask 7.2: Verify no regressions in existing tests

## Dev Notes

### Architecture Compliance

From `project-context.md`:

- **Use `get_decay_config()` singleton** - never load YAML directly
- **`DEFAULT_DECAY_CONFIG` is fallback** if YAML invalid
- **Cold-reload only** - server restart for config changes
- **Use dataclasses** for config/data structures
- **Structured logging**: `logger.warning("message", extra={...})`

### Canonical Import Block

```python
from mcp_server.utils.decay_config import get_decay_config, SectorDecay
from mcp_server.utils.sector_classifier import MemorySector
```

### IEF Formula Integration

**Current (Story 9-1):** Create config module only
**Next (Story 9-2):** Integrate into `utils/relevance.py`:

```python
# In calculate_relevance_score() - Story 9-2 will implement:
# Before: S = 100 (hardcoded)
# After: sector_config = get_decay_config()[edge.memory_sector]
#        S = sector_config.S_base * (1 + log(1 + access_count))

relevance_score = exp(-days_since_last_access / S)
```

**IEF Formula unchanged** - only S_base becomes sector-dependent.

### SectorDecay Dataclass Pattern

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SectorDecay:
    """Decay parameters for a memory sector."""
    S_base: float
    S_floor: float | None = None
```

Using `frozen=True` ensures immutability of config values.

### Singleton Pattern

```python
_config_cache: dict[MemorySector, SectorDecay] | None = None

def get_decay_config() -> dict[MemorySector, SectorDecay]:
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    try:
        # Load from YAML
        _config_cache = _load_yaml_config()
    except Exception:
        logger.warning("Falling back to default decay config")
        _config_cache = DEFAULT_DECAY_CONFIG

    return _config_cache
```

### YAML Structure

**Location:** `config/decay_config.yaml`
**Load via:** `get_decay_config()` from `mcp_server/utils/decay_config.py`

```yaml
# config/decay_config.yaml
decay_config:
  emotional:
    S_base: 200      # Higher = slower decay
    S_floor: 150     # Minimum memory strength (never forgets completely)
  semantic:
    S_base: 100
    S_floor: null    # Can decay to zero
  episodic:
    S_base: 150
    S_floor: 100
  procedural:
    S_base: 120
    S_floor: null
  reflective:
    S_base: 180
    S_floor: 120
```

**Interpretation:**
- `S_base: 200` = emotional memories decay ~2x slower than semantic (S_base: 100)
- `S_floor: 150` = emotional memories never go below 60.6% relevance (at 100 days)
- `S_floor: null` = memory can decay completely over time

### Project Structure Notes

**New Files:**
| File | Purpose |
|------|---------|
| `config/decay_config.yaml` | YAML configuration file |
| `mcp_server/utils/decay_config.py` | Config loader module |
| `tests/unit/test_decay_config.py` | Unit tests |

**Existing Files (no modifications):**
- This story is self-contained - no existing files need modification
- Story 9-2 will integrate this into `graph_query_neighbors.py`

### Dependency Requirements

The `PyYAML` library should already be in dependencies. Verify with:
```bash
pip show pyyaml
```

If not installed, add to `pyproject.toml`:
```toml
dependencies = [
    "pyyaml>=6.0.0",
]
```

### Error Handling & Validation

```python
def _load_yaml_config() -> dict[MemorySector, SectorDecay]:
    config_path = Path(__file__).parent.parent.parent / "config" / "decay_config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    if "decay_config" not in raw:
        raise ValueError("Invalid config: missing 'decay_config' key")

    # Parse each sector
    result: dict[MemorySector, SectorDecay] = {}
    for sector, values in raw["decay_config"].items():
        result[sector] = SectorDecay(
            S_base=float(values["S_base"]),
            S_floor=values.get("S_floor")  # None if missing
        )

    # CRITICAL: Validate all required sectors present
    required_sectors = {"emotional", "episodic", "semantic", "procedural", "reflective"}
    missing = required_sectors - set(result.keys())
    if missing:
        raise ValueError(f"Config missing sectors: {missing}")

    return result
```

### Testing Strategy

1. **Unit Tests**: Config loading, fallback, singleton, validation
2. **Performance Test**: Verify < 1s load time (NFR4)
3. **Edge Cases**: Missing file, invalid YAML, missing sectors

```python
# Performance test for NFR4 compliance
def test_config_load_time_nfr4(benchmark):
    """Config loading must complete in <1s (NFR4)."""
    config = benchmark(get_decay_config)
    assert config is not None
    assert len(config) == 5  # All sectors loaded

# Test validation of required sectors
def test_config_missing_sector_validation():
    """Config must contain all 5 required sectors."""
    # Mock YAML with only 3 sectors
    with pytest.raises(ValueError, match="Config missing sectors"):
        get_decay_config()  # Should raise on incomplete config

# Test fallback on missing file
def test_fallback_on_missing_file(caplog, monkeypatch):
    """get_decay_config() falls back to defaults when file missing."""
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)

    config = get_decay_config()

    assert config == DEFAULT_DECAY_CONFIG
    assert "Falling back to default decay config" in caplog.text
```

### Previous Epic Learnings (Epic 8)

1. **Use Golden Set pattern** for config validation tests
2. **mypy strict** compliance from start
3. **Structured logging** with `extra={}` dict
4. **Singleton pattern** for config loading (like `MemorySector` type)

### References

- [Source: project-context.md#Config-Rules] - Singleton pattern, fallback behavior
- [Source: project-context.md#IEF-Rules] - Formula unchanged, only S_base/S_floor are sector-dependent
- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.1] - Full acceptance criteria
- [Source: bmad-docs/epics/epic-8-architecture.md] - Architecture decisions
- [Source: docs/stories/8-1-schema-migration-data-classification.md] - TDD pattern reference

### FR/NFR Coverage

**Functional Requirements:**
- FR12: System can load decay configuration from YAML file
- FR13: System can fall back to default config when file invalid/missing
- FR28: System can provide `SectorDecay` dataclass with `S_base` and `S_floor`
- FR29: System can cache config using singleton pattern

**Non-Functional Requirements:**
- NFR4: Config loading must complete in < 1 second
- NFR8: Graceful fallback to defaults on config errors

### Critical Constraints

1. **Never load YAML directly** - always use `get_decay_config()`
2. **Config is cold-reload only** - requires server restart for changes
3. **`S_floor: null`** means no minimum (can decay to 0)
4. **All sector values must be lowercase** - per `MemorySector` Literal type
5. **Use `yaml.safe_load()`** - never `yaml.load()` (security)
6. **Validate all 5 sectors present** - raise ValueError if any sector missing

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

**Implementation Summary:**
- ✅ Created `config/decay_config.yaml` with all 5 sector configurations (emotional, semantic, episodic, procedural, reflective)
- ✅ Implemented `SectorDecay` frozen dataclass with `S_base` and `S_floor` fields
- ✅ Implemented `DEFAULT_DECAY_CONFIG` constant as fallback
- ✅ Implemented `get_decay_config()` singleton function with YAML loading
- ✅ Added comprehensive error handling: FileNotFoundError, ValueError, YAMLError
- ✅ Added sector validation: all 5 required sectors must be present
- ✅ Added **structured logging** with `logger.warning(..., extra={...})` for fallback cases (project-context compliant)
- ✅ Created comprehensive unit tests: 15 tests covering all ACs
- ✅ Validated mypy --strict compliance (types-PyYAML stubs installed)
- ✅ Verified no regressions in existing tests (sector_classifier tests: 51 passed)

**Code Review Fixes Applied (2025-01-08):**
- ✅ Fixed M1: Updated File List to document all git-modified files (5 files)
- ✅ Fixed M2: Converted to structured logging per project-context.md:167 (added extra={})
- ✅ Fixed M3: Added error context to exception handler (fallback_reason, error, config_path)

**Test Results:**
- All 15 new unit tests passing
- Config load time: < 1ms (well under NFR4 < 1s limit)
- All existing tests remain passing (no regressions)

**Technical Decisions:**
1. Used `frozen=True` for SectorDecay dataclass (immutability)
2. Implemented sector validation (enhancement from story validation)
3. Added `_get_config_path()` helper for better testability
4. Used module-level `_config_cache` for singleton pattern
5. Installed `types-PyYAML` stubs for mypy strict compliance
6. Performance test uses `time.time()` instead of pytest-benchmark (no additional dependency)

### File List

**New Files:**
- `config/decay_config.yaml`
- `mcp_server/utils/decay_config.py`
- `tests/unit/test_decay_config.py`

**Modified Files:**
- `bmad-docs/sprint-status.yaml` - Updated story 9-1 status to "review"
- `mcp_server/db/graph.py` - Minor formatting (13 line changes)
- `mcp_server/tools/get_edge.py` - Minor update (1 line added)
- `tests/test_get_edge.py` - Test enhancement (5 lines added)
- `tests/test_graph_query_neighbors.py` - Test updates (24 lines modified)
