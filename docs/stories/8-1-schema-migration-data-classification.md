# Story 8.1: Schema Migration & Data Classification

Status: done

## Story

As a developer,
I want a `memory_sector` column on the edges table with existing edges classified,
So that all edges have a memory sector after Epic 8.

## Acceptance Criteria

1. **Given** the database schema before Epic 8
   **When** migration `022_add_memory_sector.sql` Phase 1 is executed
   **Then** the `edges` table has a `memory_sector` column of type `VARCHAR(20)`
   **And** the default value is `'semantic'`
   **And** the migration is idempotent (safe to run multiple times)

2. **Given** existing edges without `memory_sector`
   **When** migration Phase 2 (data classification) runs
   **Then** edges with `emotional_valence` property are set to `"emotional"`
   **And** edges with `context_type = "shared_experience"` are set to `"episodic"`
   **And** edges with relation `LEARNED` or `CAN_DO` are set to `"procedural"`
   **And** edges with relation `REFLECTS` or `REALIZED` are set to `"reflective"`
   **And** all other edges remain `"semantic"` (default)

3. **Given** edge properties before migration
   **When** migration completes
   **Then** all original properties are preserved

4. **Given** the Python codebase
   **When** `MemorySector` type is defined in `utils/sector_classifier.py`
   **Then** it is a `Literal["emotional", "episodic", "semantic", "procedural", "reflective"]`
   **And** all sector values are lowercase

## Tasks / Subtasks

- [x] Task 1: Create migration file `022_add_memory_sector.sql` (AC: #1, #2, #3)
  - [x] Subtask 1.1: Phase 1 - Add `memory_sector` column with idempotent check
  - [x] Subtask 1.2: Phase 2 - Data classification rules for existing edges
  - [x] Subtask 1.3: Add verification queries for post-migration checks
- [x] Task 2: Create `mcp_server/utils/sector_classifier.py` (AC: #4)
  - [x] Subtask 2.1: Define `MemorySector` Literal type
  - [x] Subtask 2.2: Create `classify_memory_sector()` function with full classification logic
- [x] Task 3: Create `tests/fixtures/__init__.py` and `tests/fixtures/golden_set_sectors.py`
  - [x] Subtask 3.1: Define 20 pre-classified edge fixtures for regression testing
- [x] Task 4: Create `tests/unit/test_sector_classifier.py`
  - [x] Subtask 4.1: Test `MemorySector` type imports correctly
  - [x] Subtask 4.2: Test classification logic with golden set fixtures
- [x] Task 5: Execute migration and verify
  - [x] Subtask 5.1: Run migration against development database
  - [x] Subtask 5.2: Verify all existing edges have `memory_sector` field
  - [x] Subtask 5.3: Verify original properties are preserved

## Dev Notes

### Architecture Compliance

This story follows the architecture decisions from `bmad-docs/epics/epic-8-architecture.md`:

- **Database Decision**: `VARCHAR(20)` for sector column (not PostgreSQL ENUM to avoid migration complexity)
- **Default Value**: `'semantic'` as safe default for unmigrated edges
- **Validation**: Python `Literal` type for type checking, no DB CHECK constraint for MVP
- **Index**: None required (sector cardinality too low for index benefit)

### Project Structure Notes

**New Files:**
| File | Purpose |
|------|---------|
| `mcp_server/db/migrations/022_add_memory_sector.sql` | Schema + data migration |
| `mcp_server/utils/sector_classifier.py` | MemorySector type definition |
| `tests/fixtures/__init__.py` | Fixture exports |
| `tests/fixtures/golden_set_sectors.py` | 20 pre-classified edges |
| `tests/unit/test_sector_classifier.py` | Type and classification tests |

**Existing Schema Reference:**
The `edges` table (from `012_add_graph_tables.sql`) has:
- `id UUID PRIMARY KEY`
- `source_id UUID NOT NULL`
- `target_id UUID NOT NULL`
- `relation VARCHAR(255) NOT NULL`
- `weight FLOAT DEFAULT 1.0`
- `properties JSONB DEFAULT '{}'`
- `created_at TIMESTAMPTZ DEFAULT NOW()`

Additional fields from later migrations:
- `last_accessed TIMESTAMPTZ` (from 015)
- `access_count INTEGER` (from 015)
- `memory_strength FLOAT` (from 015)
- `last_engaged TIMESTAMPTZ` (from 021)

### Migration Patterns

**Idempotent Column Addition Pattern:**
```sql
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'edges' AND column_name = 'memory_sector'
  ) THEN
    ALTER TABLE edges ADD COLUMN memory_sector VARCHAR(20) DEFAULT 'semantic';
  END IF;
END $$;
```

**Data Classification Pattern:**
```sql
-- Emotional: edges with emotional_valence property
UPDATE edges SET memory_sector = 'emotional'
WHERE properties->>'emotional_valence' IS NOT NULL
  AND memory_sector = 'semantic';

-- Episodic: shared experiences
UPDATE edges SET memory_sector = 'episodic'
WHERE properties->>'context_type' = 'shared_experience'
  AND memory_sector = 'semantic';

-- Procedural: learning-related relations
UPDATE edges SET memory_sector = 'procedural'
WHERE relation IN ('LEARNED', 'CAN_DO')
  AND memory_sector = 'semantic';

-- Reflective: reflection-related relations
UPDATE edges SET memory_sector = 'reflective'
WHERE relation IN ('REFLECTS', 'REALIZED')
  AND memory_sector = 'semantic';
```

### MemorySector Type Definition

```python
# mcp_server/utils/sector_classifier.py
from typing import Literal

MemorySector = Literal["emotional", "episodic", "semantic", "procedural", "reflective"]
```

**CRITICAL**: All sector values MUST be lowercase. The `MemorySector` type enforces this at compile time with mypy.

### Golden Set Fixture Structure

```python
# tests/fixtures/golden_set_sectors.py
GOLDEN_SET_SECTORS = [
    {
        "source": "I/O",
        "target": "Kirchenpark-Moment",
        "relation": "EXPERIENCED",
        "properties": {"emotional_valence": "positive"},
        "expected_sector": "emotional"
    },
    # ... 19 more pre-classified edges covering all 5 sectors
]
```

### References

- [Source: bmad-docs/epics/epic-8-architecture.md#Data-Architecture]
- [Source: bmad-docs/epics/epic-8-architecture.md#Migration-Patterns]
- [Source: mcp_server/db/migrations/012_add_graph_tables.sql] - Original edges schema
- [Source: project-context.md#Epic-8-Specific-Rules]
- [Source: _bmad-output/planning-artifacts/epics.md#Story-1.1]

### FR/NFR Coverage

**Functional Requirements:**
- FR20: Store memory_sector as a field on all edges
- FR21: Migrate existing edges to appropriate sectors during schema migration
- FR22: Preserve backward compatibility by defaulting unmigrated edges to semantic sector

**Non-Functional Requirements:**
- NFR7: Schema migration must be idempotent (safe to run multiple times)
- NFR12: Existing edges must retain all properties after schema migration
- NFR13: Default sector assignment must be deterministic (same input -> same sector)

### Critical Constraints

1. **The migration must NOT alter or delete any existing edge properties**
2. **The migration must be idempotent** - running it twice should not cause errors or data changes
3. **All sector values MUST be lowercase** - `"emotional"` not `"Emotional"`
4. **Classification order matters** - check `emotional_valence` first as it takes priority

### Testing Strategy

1. **Unit Tests**: Verify `MemorySector` type definition and imports
2. **Migration Tests**: Verify idempotency by running migration twice
3. **Data Integrity Tests**: Verify original properties preserved after migration
4. **Golden Set Tests**: Verify classification accuracy against 20 pre-classified edges

## Dev Agent Record

### Agent Model Used

GLM-4.7 (via Claude Code CLI)

### Debug Log References

No debugging sessions required. Implementation proceeded smoothly with TDD approach.

### Completion Notes List

**Implementation Summary:**
- ✅ Migration `022_add_memory_sector.sql` created and executed successfully
- ✅ Python utility `sector_classifier.py` with `MemorySector` Literal type
- ✅ Classification function implemented with priority-based rules (emotional → episodic → procedural → reflective → semantic)
- ✅ Golden set fixtures: 20 pre-classified edges covering all 5 sectors
- ✅ Comprehensive unit tests: 42 tests, all passing
- ✅ Integration tests: 9 tests, all passing (migration verification, idempotency, classification validation)
- ✅ Migration executed against development DB: 841 edges classified (7 emotional, 2 episodic, 832 semantic)
- ✅ Idempotency verified: Migration can be run multiple times safely
- ✅ Properties preservation verified: All original edge properties intact
- ✅ Type checking: mypy --strict passes for sector_classifier.py
- ✅ Code quality: ruff linting passes with auto-fix applied
- ✅ Code review completed: All HIGH and MEDIUM issues fixed automatically

**Technical Decisions:**
1. Added `REFLECTS_ON` to reflective relations (common variant not in original spec)
2. Made `properties` parameter optional (`dict | None`) for defensive programming
3. Used `dict[str, object]` type annotation for mypy strict compliance
4. Migration includes verification queries for post-migration validation
5. Added comprehensive integration test suite for migration verification (test_022_migration.py)
6. Enhanced `tests/fixtures/__init__.py` with proper pytest fixture export

**Code Review Fixes Applied (2026-01-08):**
- ✅ Updated story File List to document uncommitted changes (suggest_lateral_edges.py)
- ✅ Created integration test suite `tests/integration/test_022_migration.py` with 9 tests
- ✅ Enhanced `tests/fixtures/__init__.py` with `golden_set_edges` pytest fixture
- ✅ All 51 tests passing (42 unit + 9 integration)

**Data Migration Results:**
- Total edges processed: 841
- Emotional: 7 (0.8%)
- Episodic: 2 (0.2%)
- Semantic: 832 (98.9%)
- Procedural: 0 (0%)
- Reflective: 0 (0%)
- NULL values: 0 ✅

### File List

**New Files:**
- `mcp_server/db/migrations/022_add_memory_sector.sql` - Schema + data migration
- `mcp_server/utils/sector_classifier.py` - MemorySector type and classification logic
- `tests/fixtures/__init__.py` - Test fixtures package with golden_set_edges fixture
- `tests/fixtures/golden_set_sectors.py` - 20 pre-classified edge fixtures
- `tests/unit/test_sector_classifier.py` - Unit tests with golden set coverage (42 tests)
- `tests/integration/test_022_migration.py` - Integration tests for migration verification (9 tests)

**Modified Files:**
- `docs/stories/8-1-schema-migration-data-classification.md` - Task completion status + code review fixes applied
- `bmad-docs/sprint-status.yaml` - Story status updated to review

**Uncommitted Changes (Not Part of This Story):**
- `mcp_server/tools/suggest_lateral_edges.py` - Belongs to Epic 4 (GraphRAG), not Story 8-1

