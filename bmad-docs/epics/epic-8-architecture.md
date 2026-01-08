---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
status: 'complete'
completedAt: '2026-01-08'
inputDocuments:
  - bmad-docs/epics/epic-8-prd.md
  - bmad-docs/research/epic-8-hypergraphrag-deep-research.md
  - bmad-docs/architecture.md
workflowType: 'architecture'
project_name: 'cognitive-memory'
user_name: 'ethr'
date: '2026-01-07'
---

# Architecture Decision Document - Epic 8: OpenMemory Integration

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (30 FRs in 6 Categories):**

Epic 8 erweitert cognitive-memory um Memory Sectors - eine Klassifikations-Schicht für Edges die emotionale von faktischen Erinnerungen unterscheidet. Die 30 FRs verteilen sich auf:

| Category | FRs | Scope |
|----------|-----|-------|
| Memory Sector Classification | FR1-FR4, FR30 | Auto-classify edges at insert |
| Memory Sector Reclassification | FR5-FR10, FR26-FR27 | Manual correction + SMF integration |
| Sector-Specific Memory Decay | FR11-FR15, FR28-FR29 | Configurable decay per sector |
| Query Filtering | FR16-FR19 | sector_filter parameter for tools |
| Schema & Data Migration | FR20-FR22 | ALTER TABLE + migration script |
| Integration | FR23-FR25 | SMF/Dissonance compatibility |

**Non-Functional Requirements (17 NFRs):**

Critical NFRs driving architectural decisions:

- **NFR1:** Classification adds <10ms to insert latency (requires baseline measurement before Epic 8)
- **NFR2:** Filtered queries perform within 20% of unfiltered
- **NFR5:** All existing MCP tools remain backward compatible
- **NFR7:** Schema migration must be idempotent
- **NFR8:** Invalid decay config triggers fallback, not crash
- **NFR9:** Reclassification respects SMF bilateral consent
- **NFR15/16:** Structured logging for classification decisions and performance monitoring

**Scale & Complexity:**

- Primary domain: Backend/MCP Server (no UI)
- Complexity level: Medium (delta extension, not greenfield)
- Estimated file impact: 6-7 modified files, 2-3 new files

### Technical Constraints & Dependencies

**Hard Constraints (from existing architecture):**

1. PostgreSQL + pgvector remains only database (no Neo4j, no external dependencies)
2. MCP Protocol (stdio transport) for Claude Code integration
3. Existing graph schema (nodes, edges tables) unchanged except new column
4. Python 3.11+ with Poetry dependency management
5. **Config Cold-Reload only** - Server restart required for decay_config.yaml changes (no hot-reload for MVP)

**OpenMemory Integration Approach (from Deep Research):**

OpenMemory concepts are **ported natively**, not integrated as external dependency:
- Sector classification logic implemented in Python
- Decay curves configurable via YAML
- No OpenMemory MCP Server - single cognitive-memory server

**Baseline Requirements (must complete before implementation):**

- Measure current average insert latency for `graph_add_edge`
- Document current test count (`pytest --collect-only`)
- Snapshot existing edge count for migration planning

### File Impact Map

```
src/mcp_server/
├── tools/
│   ├── graph_add_edge.py         # MODIFIED: +classification logic
│   ├── graph_add_node.py         # MODIFIED: +classification logic
│   ├── graph_query_neighbors.py  # MODIFIED: +sector_filter, +sector in response
│   ├── hybrid_search.py          # MODIFIED: +sector_filter
│   └── reclassify_memory_sector.py  # NEW: Manual reclassification tool
├── db/
│   ├── graph.py                  # MODIFIED: +sector field handling
│   └── migrations/
│       └── 00X_add_memory_sector.sql  # NEW: Schema migration
├── utils/
│   ├── relevance.py              # MODIFIED: sector-specific decay in calculate_relevance_score()
│   └── sector_classifier.py      # NEW: Extracted classification logic
└── config/
    └── decay_config.yaml         # NEW: Sector decay parameters
```

### Cross-Cutting Concerns Identified

1. **IEF (Integrative Evaluation Function) - PRIMARY:**
   - `calculate_relevance_score()` is the heart of `query_neighbors` with IEF
   - Sector-specific decay changes affect ALL graph queries
   - Decay formula unchanged: `exp(-days_since_last_access / S)`
   - S_base and S_floor now sector-dependent

2. **SMF (Self-Modification Framework) Integration:**
   - Reclassification of constitutive edges requires bilateral consent
   - Must check `is_constitutive` flag before allowing unilateral reclassification

3. **Dissonance Engine Compatibility:**
   - `dissonance_check` must work with sector-annotated edges
   - Resolution hyperedges should inherit sector from resolved edges

4. **Query Tool Extensions:**
   - `query_neighbors`, `hybrid_search`, `get_edge` return `memory_sector`
   - New optional `sector_filter: list[str]` parameter

5. **Data Quality Risk:**
   - Migration will classify ~500 existing edges
   - Estimated error rate for rule-based classification: 10-20%
   - Mitigation: `reclassify_memory_sector` tool must be available early + Audit-Log

6. **Observability:**
   - NFR15/16 require DEBUG logging for classification decisions
   - Performance monitoring for decay calculations
   - Structured logging pattern in all new/modified functions

7. **Test Infrastructure:**
   - Golden Set: 20 pre-classified edges as regression baseline
   - New test files: `test_memory_sector.py`, `test_decay.py`, `test_reclassify.py`
   - 52 new tests total (per PRD)

### Migration Strategy

**Staging Approach:**
1. **Phase 1 - Schema:** `ALTER TABLE edges ADD COLUMN memory_sector VARCHAR(20) DEFAULT 'semantic'`
2. **Phase 2 - Data:** Rule-based classification of existing edges
3. **Phase 3 - Validation:** Dry-run report before commit

**Rollback Plan:**
- `ALTER TABLE edges DROP COLUMN memory_sector` (if Phase 1 fails)
- Keep backup of edge properties before Phase 2

**Idempotency:**
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- Migration script checks for existing column before running

### Success Criteria Alignment

| PRD Success Criterion | Supporting Architecture Decision |
|-----------------------|----------------------------------|
| Der "Moment-Test" | Sector-specific decay preserves emotional memories longer |
| Der "Decay-Test" | Configurable S_base/S_floor per sector in YAML |
| Der "Sektor-Test" | Auto-classification at insert + sector_filter in queries |
| Kein Infrastruktur-Wechsel | Native implementation, no external dependencies |
| Backward Compatibility | Default 'semantic' sector, optional sector_filter parameter |
| Dissonance Regression | Cross-cutting concern #3 ensures compatibility |

## Starter Template Evaluation

### Primary Technology Domain

**Brownfield Extension** - Epic 8 extends existing cognitive-memory system (v3.3.0)

### Established Tech Stack (No Changes Required)

Epic 8 is a delta extension of an existing production system. The following technical decisions are **already made and locked**:

| Category | Decision | Version | Rationale |
|----------|----------|---------|-----------|
| Language | Python | 3.11+ | Type hints, MCP SDK compatibility |
| Package Manager | Poetry | Latest | Type-safe, lockfile, modern Python |
| Database | PostgreSQL + pgvector | 15+ | Vector search, production-ready |
| Protocol | MCP (stdio transport) | Latest SDK | Native Claude Code integration |
| Embeddings | OpenAI text-embedding-3-small | 1536 dim | Best Precision@5, €0.02/1M tokens |
| Evaluation | Anthropic Haiku | claude-3-5-haiku | Deterministic, consistent |
| Testing | pytest | Latest | Standard Python testing |
| Service | systemd | Native Linux | Auto-restart, logging |

### No Starter Template Required

**Rationale:**
- Existing project structure (`src/mcp_server/`) is mature
- All infrastructure decisions (DB, APIs, Deployment) are production-stable
- Epic 8 adds new files to existing structure, not new project scaffold

### Architectural Patterns Already Established

**Code Organization:**
- `src/mcp_server/tools/` - MCP tool implementations
- `src/mcp_server/db/` - Database layer + migrations
- `src/mcp_server/utils/` - Shared utilities
- `config/` - Configuration files (YAML, .env)

**Naming Conventions:**
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/Variables: `snake_case`
- MCP Tools: `snake_case` (e.g., `reclassify_memory_sector`)

**Error Handling:**
- All exceptions → Structured JSON Response
- Format: `{error: {type, message, details}, status: "error"}`

**Logging:**
- JSON Structured Logging
- Levels: ERROR, WARN, INFO, DEBUG

### Epic 8 Specific Additions

New files will follow existing patterns with Epic 8-specific extensions:

| New File | Pattern Source | Epic 8 Extension |
|----------|----------------|------------------|
| `tools/reclassify_memory_sector.py` | `tools/graph_query_neighbors.py` | +SMF bilateral consent check |
| `utils/sector_classifier.py` | `utils/relevance.py` | Extracted for testability + future LLM replacement |
| `db/migrations/00X_add_memory_sector.sql` | `db/migrations/003_add_graph_tables.sql` | Two-phase (Schema + Data) with idempotency |
| `config/decay_config.yaml` | NEW PATTERN | Dedicated domain config with sector-specific schema |

### New Patterns Introduced by Epic 8

**1. Dedicated Domain Config Pattern:**

```yaml
# config/decay_config.yaml - NEW PATTERN
# Unlike config.yaml (general settings), this is domain-specific
decay_config:
  sectors:
    emotional:
      S_base: 200
      S_floor: 150
    semantic:
      S_base: 100
      S_floor: null
    # ...
```

**2. Two-Phase Migration Pattern:**

```sql
-- Phase 1: Schema (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name='edges' AND column_name='memory_sector') THEN
    ALTER TABLE edges ADD COLUMN memory_sector VARCHAR(20) DEFAULT 'semantic';
  END IF;
END $$;

-- Phase 2: Data Migration (with guards)
UPDATE edges SET memory_sector = 'emotional'
WHERE properties->>'emotional_valence' IS NOT NULL
  AND memory_sector = 'semantic';
```

**3. SMF-Aware Tool Pattern:**

```python
# tools/reclassify_memory_sector.py
async def reclassify_memory_sector(...):
    edge = await get_edge_by_names(source, target, relation)

    # NEW: SMF bilateral consent check
    if edge.properties.get("is_constitutive"):
        if not await check_bilateral_consent(edge):
            return {"error": "Bilateral consent required", "edge_id": edge.id}

    # Continue with reclassification...
```

**4. Extracted Classifier Pattern:**

```python
# utils/sector_classifier.py - Extracted for testability
def classify_memory_sector(relation: str, properties: dict) -> str:
    """Rule-based sector classification. Returns sector name.

    Design: Extracted module enables:
    - Isolated unit testing with Golden Set
    - Future LLM-based classification as drop-in replacement
    """
    if properties.get("emotional_valence"):
        return "emotional"
    # ... rules from PRD
    return "semantic"  # default
```

### New Test Patterns Introduced by Epic 8

**1. Golden Set Parametrized Tests:**

```python
# tests/fixtures/golden_set_sectors.py
GOLDEN_SET_SECTORS = [
    {"source": "I/O", "target": "Kirchenpark-Moment", "relation": "EXPERIENCED",
     "properties": {"emotional_valence": "positive"}, "expected_sector": "emotional"},
    # ... 19 more pre-classified edges
]

# tests/unit/test_sector_classification.py
@pytest.mark.parametrize("edge", GOLDEN_SET_SECTORS)
def test_classify_golden_set(edge):
    result = classify_memory_sector(edge["relation"], edge["properties"])
    assert result == edge["expected_sector"]
```

**2. SMF Integration Test Pattern:**

```python
# tests/integration/test_reclassify_smf.py
async def test_reclassify_constitutive_requires_consent():
    """Constitutive edges cannot be reclassified without bilateral consent."""
    # Setup: Create constitutive edge
    # Act: Try to reclassify without consent
    # Assert: Returns error with consent requirement
```

**3. Performance Baseline Pattern:**

```python
# tests/performance/test_baseline.py
@pytest.mark.benchmark
def test_graph_add_edge_baseline(benchmark):
    """Capture baseline insert latency before Epic 8.
    Run BEFORE Epic 8 implementation to establish NFR1 baseline."""
    result = benchmark(graph_add_edge, ...)
    assert result.stats.mean < 0.050  # 50ms baseline expectation
```

**Note:** No initialization command needed - development continues in existing repository structure.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Sector Classification Strategy | Extracted function + Literal Type | Testable, simple, future LLM-ready |
| Decay Parameter Persistence | YAML + Hardcoded Defaults | PRD-compliant, NFR8-compliant |
| Sector Data Type | Python Enum + VARCHAR | Flexible DB, strict Python validation |

**Important Decisions (Shape Architecture):**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Reclassification Audit | Edge Properties (last only) + Structured Logging | FR10-compliant, no table bloat |
| SMF Integration Point | Check in reclassify tool, not in classifier | Separation of concerns |

**Deferred Decisions (Post-MVP / Growth):**

| Decision | Deferred To | Rationale |
|----------|-------------|-----------|
| Protocol-based Classifier | Growth Phase | Over-engineering for MVP, needed for LLM swap |
| Hot-Reload Decay Config | Growth Phase | PRD explicitly says cold-reload for MVP |
| DB CHECK Constraint | Growth Phase | Python validation sufficient for MVP |
| LLM-based Classification | Growth Phase | Rules sufficient for MVP validation |

### Data Architecture

**Sector Storage:**

| Aspect | Decision | Version/Details |
|--------|----------|-----------------|
| Column Type | `VARCHAR(20)` | Not PostgreSQL ENUM (avoids migration complexity) |
| Default Value | `'semantic'` | Safe default for unmigrated edges |
| Validation | Python `Literal` type | No DB CHECK constraint for MVP |
| Index | None required | Sector cardinality too low for index benefit |

**Decay Configuration:**

| Aspect | Decision | Details |
|--------|----------|---------|
| Storage | `config/decay_config.yaml` | YAML file, not database |
| Reload | Cold (server restart) | No hot-reload for MVP |
| Fallback | Hardcoded `DEFAULT_DECAY_CONFIG` | NFR8 compliance |
| Schema | `SectorDecay` dataclass | `S_base: float`, `S_floor: float | None` |

**Type Definitions:**

```python
# utils/sector_classifier.py
from typing import Literal

MemorySector = Literal["emotional", "episodic", "semantic", "procedural", "reflective"]

def classify_memory_sector(relation: str, properties: dict) -> MemorySector:
    """Rule-based sector classification."""
    if properties.get("emotional_valence"):
        return "emotional"
    if properties.get("context_type") == "shared_experience":
        return "episodic"
    if relation in ("LEARNED", "CAN_DO"):
        return "procedural"
    if relation in ("REFLECTS", "REALIZED"):
        return "reflective"
    return "semantic"  # default
```

```python
# utils/decay_config.py
from dataclasses import dataclass

@dataclass
class SectorDecay:
    S_base: float
    S_floor: float | None

DEFAULT_DECAY_CONFIG: dict[str, SectorDecay] = {
    "emotional": SectorDecay(S_base=200, S_floor=150),
    "episodic": SectorDecay(S_base=150, S_floor=100),
    "semantic": SectorDecay(S_base=100, S_floor=None),
    "procedural": SectorDecay(S_base=120, S_floor=None),
    "reflective": SectorDecay(S_base=180, S_floor=120),
}
```

### Authentication & Security

**No Changes Required** - Epic 8 inherits existing security model:

- Local-only system (no network authentication)
- API keys for external services (OpenAI, Anthropic) already configured
- SMF bilateral consent for constitutive edges (existing mechanism)

**Epic 8 Security Consideration:**

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Reclassification of Constitutive Edges | Require bilateral consent | Existing SMF pattern, prevents unauthorized identity changes |

### API & Communication Patterns

**MCP Tool Extensions:**

| Tool | Extension | Backward Compatible |
|------|-----------|---------------------|
| `graph_add_edge` | Returns `memory_sector` in response | Yes (additive field) |
| `graph_add_node` | Returns `memory_sector` for connected edges | Yes (additive field) |
| `graph_query_neighbors` | New optional `sector_filter` parameter | Yes (optional param) |
| `hybrid_search` | New optional `sector_filter` parameter | Yes (optional param) |

**New MCP Tool:**

```python
# reclassify_memory_sector - NEW TOOL
async def reclassify_memory_sector(
    source_name: str,
    target_name: str,
    relation: str,
    new_sector: MemorySector,
    edge_id: str | None = None  # Optional disambiguation
) -> ReclassifyResult:
    """Reclassify an edge to a different memory sector."""
```

**Error Response Pattern:**

```python
# Ambiguous edge error
{"error": "Multiple edges found", "edge_ids": ["uuid1", "uuid2"], "status": "ambiguous"}

# Constitutive edge error
{"error": "Bilateral consent required", "edge_id": "uuid", "status": "consent_required"}

# Success
{"edge_id": "uuid", "old_sector": "semantic", "new_sector": "emotional", "status": "success"}
```

### Infrastructure & Deployment

**No Changes Required** - Epic 8 uses existing infrastructure:

- systemd service management
- PostgreSQL database
- Poetry dependency management
- pytest test runner

**Epic 8 Deployment Consideration:**

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Migration Execution | Manual via psql before server restart | Two-phase migration needs explicit control |
| Config Deployment | Copy `decay_config.yaml` to `config/` | Standard config file deployment |
| Rollback | DROP COLUMN if migration fails | Simple rollback, no data loss |

### Decision Impact Analysis

**Implementation Sequence:**

1. **Schema Migration** - Must be first (other changes depend on column existing)
2. **Decay Config Module** - Independent, can parallelize
3. **Sector Classifier Module** - Independent, can parallelize
4. **Tool Extensions** - Depends on classifier + schema
5. **Reclassify Tool** - Depends on all above
6. **Tests** - Parallel with each component

**Cross-Component Dependencies:**

```
decay_config.yaml
       │
       ▼
utils/decay_config.py ◄── utils/relevance.py (calculate_relevance_score)
                                │
                                ▼
                     tools/graph_query_neighbors.py (IEF scoring)

utils/sector_classifier.py ◄── tools/graph_add_edge.py
                           ◄── tools/graph_add_node.py
                           ◄── tools/reclassify_memory_sector.py
                                        │
                                        ▼
                               SMF bilateral consent check
```

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:** 8 areas where AI agents could make different choices for Epic 8

### Naming Patterns

**Memory Sector Naming (Epic 8 Specific):**

| Pattern | Rule | Example |
|---------|------|---------|
| Sector Values | Always lowercase | `"emotional"` not `"Emotional"` |
| Sector Type | Use `MemorySector` Literal | `sector: MemorySector = "emotional"` |
| Config Keys | Lowercase, match sector values | `emotional:` not `Emotional:` |
| Parameter Names | snake_case, consistent with existing | `sector_filter` not `sectorFilter` |

**Established Naming (Unchanged):**

- Database: `snake_case` (tables, columns)
- Python: `snake_case` (functions, variables), `PascalCase` (classes)
- MCP Tools: `snake_case` (e.g., `reclassify_memory_sector`)

### Structure Patterns

**New Files Location:**

| File Type | Location | Pattern Source |
|-----------|----------|----------------|
| New MCP Tools | `src/mcp_server/tools/` | Existing tools |
| New Utilities | `src/mcp_server/utils/` | Existing utils |
| New Migrations | `src/mcp_server/db/migrations/` | Existing migrations |
| New Config | `config/` | Existing config |
| New Tests | `tests/unit/`, `tests/integration/` | Existing test structure |
| Golden Set Fixtures | `tests/fixtures/` | NEW location |

**Test File Naming:**

| Component | Test File |
|-----------|-----------|
| `utils/sector_classifier.py` | `tests/unit/test_sector_classifier.py` |
| `utils/decay_config.py` | `tests/unit/test_decay_config.py` |
| `tools/reclassify_memory_sector.py` | `tests/unit/test_reclassify_memory_sector.py` |
| SMF Integration | `tests/integration/test_reclassify_smf.py` |
| Golden Set | `tests/fixtures/golden_set_sectors.py` |

### Format Patterns

**Reclassification Audit Format (Epic 8 Specific):**

```python
# edge.properties["last_reclassification"] format
{
    "from_sector": "semantic",
    "to_sector": "emotional",
    "timestamp": "2026-01-07T14:30:00Z",  # ISO 8601
    "actor": "I/O",
    "reason": "Manual correction"  # Optional
}
```

**Decay Config YAML Format:**

```yaml
# config/decay_config.yaml - Canonical format
decay_config:
  emotional:
    S_base: 200
    S_floor: 150
  semantic:
    S_base: 100
    S_floor: null  # Explicit null, not empty
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

**Error Status Constants:**

```python
# utils/constants.py - Canonical status values
class ReclassifyStatus:
    SUCCESS = "success"
    AMBIGUOUS = "ambiguous"
    CONSENT_REQUIRED = "consent_required"
    NOT_FOUND = "not_found"
    INVALID_SECTOR = "invalid_sector"
```

**API Response Format (Epic 8 Extensions):**

```python
# Successful reclassification
{"edge_id": "uuid", "old_sector": "semantic", "new_sector": "emotional", "status": "success"}

# Ambiguous edge error
{"error": "Multiple edges found", "edge_ids": ["uuid1", "uuid2"], "status": "ambiguous"}

# Consent required error
{"error": "Bilateral consent required", "edge_id": "uuid", "status": "consent_required"}
```

### Import & Access Patterns

**Canonical Imports:**

```python
# Pattern: Import from canonical location
from mcp_server.utils.sector_classifier import MemorySector, classify_memory_sector
from mcp_server.utils.decay_config import get_decay_config, SectorDecay
from mcp_server.utils.constants import ReclassifyStatus

# Anti-Pattern: Star imports
from mcp_server.utils.sector_classifier import *  # NEVER
```

**Config Access Pattern:**

```python
# Pattern: Lazy loading singleton
from mcp_server.utils.decay_config import get_decay_config

def calculate_relevance_score(edge) -> float:
    config = get_decay_config()  # Returns cached config
    sector_decay = config[edge.memory_sector]
    # ...

# Anti-Pattern: Direct file loading
with open("config/decay_config.yaml") as f:  # NEVER in functions
    config = yaml.safe_load(f)
```

**sector_filter Parameter Semantics:**

```python
# Pattern: None means ALL sectors, not empty
def query_neighbors(
    node_name: str,
    sector_filter: list[MemorySector] | None = None,
) -> list[NeighborResult]:
    # None = return all sectors (no filtering)
    # [] = return nothing (empty filter) - edge case, document behavior
    # ["emotional", "episodic"] = return only these sectors
```

### Migration Patterns

**Idempotent Column Addition:**

```sql
-- Pattern: Safe column addition
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

**Config Validation Pattern:**

```python
# Pattern: Strict config validation
def validate_decay_config(config: dict) -> bool:
    required_sectors = {"emotional", "episodic", "semantic", "procedural", "reflective"}
    decay_config = config.get("decay_config", {})

    if set(decay_config.keys()) != required_sectors:
        return False

    for sector, params in decay_config.items():
        if "S_base" not in params:
            return False
        if not isinstance(params["S_base"], (int, float)) or params["S_base"] <= 0:
            return False
        # S_floor can be null or positive number
        if params.get("S_floor") is not None:
            if not isinstance(params["S_floor"], (int, float)) or params["S_floor"] < 0:
                return False
    return True
```

### Test Patterns

**Golden Set Fixture:**

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
    # ... 19 more pre-classified edges
]
```

**Config Mocking:**

```python
# Pattern: Mock config for isolated tests
@pytest.fixture
def mock_decay_config(monkeypatch):
    test_config = {
        "emotional": SectorDecay(S_base=100, S_floor=50),
        "semantic": SectorDecay(S_base=50, S_floor=None),
        # ... simplified for tests
    }
    monkeypatch.setattr("mcp_server.utils.decay_config._cached_config", test_config)
    return test_config
```

**Constitutive Edge Fixture:**

```python
# Pattern: SMF integration test fixture
@pytest.fixture
async def constitutive_edge(db_session):
    """Create a constitutive edge for testing SMF integration."""
    edge = await create_edge(
        source="I/O",
        target="ethr",
        relation="LOVES",
        properties={"is_constitutive": True}
    )
    yield edge
    await delete_edge(edge.id)
```

### Communication Patterns

**Logging Format (Epic 8 Specific):**

```python
# Classification decision (DEBUG)
logger.debug("Sector classification", extra={
    "edge_id": edge_id,
    "relation": relation,
    "classified_sector": sector,
    "rule_matched": "emotional_valence"
})

# Reclassification (INFO)
logger.info("Edge reclassified", extra={
    "edge_id": edge_id,
    "from_sector": old_sector,
    "to_sector": new_sector,
    "actor": actor,
    "is_constitutive": is_constitutive
})

# Decay calculation (DEBUG)
logger.debug("Decay calculated", extra={
    "edge_id": edge_id,
    "sector": sector,
    "relevance_score": score,
    "calculation_ms": elapsed_ms
})
```

### Process Patterns

**Sector Classification Process:**

```
1. Edge insert request received
2. Extract relation and properties
3. Call classify_memory_sector(relation, properties)
4. Log classification decision (DEBUG)
5. Store edge with memory_sector field
6. Return response including memory_sector
```

**Reclassification Process:**

```
1. Lookup edge by source_name/target_name/relation
2. If multiple edges: Return ambiguous error with edge_ids
3. Check is_constitutive in properties
4. If constitutive: Check bilateral consent (SMF)
5. If no consent: Return consent_required error
6. Update memory_sector field
7. Update properties["last_reclassification"]
8. Log reclassification (INFO)
9. Return success with old/new sector
```

**Decay Config Loading Process:**

```
1. Check if _cached_config exists -> return cached
2. Try load config/decay_config.yaml
3. If FileNotFoundError: Log warning, use DEFAULT_DECAY_CONFIG
4. Validate config with validate_decay_config()
5. If ValidationError: Log warning, use DEFAULT_DECAY_CONFIG
6. Cache config in _cached_config
7. Return config
```

### Enforcement Guidelines

**All AI Agents MUST:**

1. Use `MemorySector` Literal type for all sector values
2. Use lowercase sector strings: `"emotional"` not `"Emotional"`
3. Use `ReclassifyStatus` constants for status values
4. Import from canonical locations, never star imports
5. Use `get_decay_config()` singleton, never direct file access
6. Follow existing error response pattern with `status` field
7. Log classification decisions at DEBUG level
8. Log reclassifications at INFO level
9. Place fixtures in `tests/fixtures/`
10. Use `None` for "all sectors" in sector_filter

**Pattern Enforcement:**

- `mypy --strict` catches sector typos via Literal type
- `ReclassifyStatus` constants prevent status string typos
- Tests verify response format consistency
- Code review checks logging patterns and import style

### Pattern Examples

**Good Examples:**

```python
# Correct imports
from mcp_server.utils.sector_classifier import MemorySector, classify_memory_sector
from mcp_server.utils.constants import ReclassifyStatus

# Correct sector usage
sector: MemorySector = "emotional"

# Correct status usage
return {"status": ReclassifyStatus.SUCCESS, "edge_id": edge_id}

# Correct config access
config = get_decay_config()

# Correct logging
logger.debug("Classified", extra={"sector": sector, "rule": "emotional_valence"})
```

**Anti-Patterns:**

```python
# WRONG: Capitalized sector
sector = "Emotional"

# WRONG: String literal for status
return {"status": "sucess"}  # Typo not caught!

# WRONG: Direct file access
with open("config/decay_config.yaml") as f: ...

# WRONG: Star import
from mcp_server.utils.sector_classifier import *

# WRONG: Unstructured logging
logger.debug(f"Classified as {sector}")
```

## Project Structure & Boundaries

### Epic 8 Delta Structure

Epic 8 erweitert die bestehende cognitive-memory Struktur. Hier sind nur die **neuen und modifizierten Dateien**:

```
cognitive-memory/                          # Existing project root
├── config/
│   └── decay_config.yaml                  # NEW: Sector decay parameters
├── mcp_server/                            # NOTE: Not src/mcp_server/
│   ├── tools/
│   │   ├── graph_add_edge.py              # MODIFIED: +classification
│   │   ├── graph_add_node.py              # MODIFIED: +classification
│   │   ├── graph_query_neighbors.py       # MODIFIED: +sector_filter, +sector decay
│   │   ├── hybrid_search.py               # MODIFIED: +sector_filter
│   │   ├── dissonance_check.py            # MODIFIED: +sector awareness
│   │   └── reclassify_memory_sector.py    # NEW: Reclassification tool
│   ├── db/
│   │   ├── graph.py                       # MODIFIED: +sector field
│   │   └── migrations/
│   │       └── 022_add_memory_sector.sql  # NEW: Schema migration
│   └── utils/
│       ├── sector_classifier.py           # NEW: Classification logic
│       ├── decay_config.py                # NEW: Config loading + defaults
│       ├── relevance.py                   # NEW: Relevance scoring with decay
│       └── constants.py                   # NEW: Status constants (new pattern)
└── tests/
    ├── fixtures/
    │   ├── __init__.py                    # NEW: Export fixtures
    │   └── golden_set_sectors.py          # NEW: Golden Set fixture
    ├── unit/
    │   ├── test_sector_classifier.py      # NEW: Classification tests
    │   ├── test_decay_config.py           # NEW: Config tests
    │   ├── test_reclassify_memory_sector.py # NEW: Tool tests
    │   └── test_query_filter.py           # NEW: Query filter tests
    ├── integration/
    │   └── test_reclassify_smf.py         # NEW: SMF integration tests
    └── performance/
        └── test_baseline.py               # NEW: Latency baseline tests
```

### Complete File Inventory

**New Files (13):**

| File | Purpose | FR Coverage |
|------|---------|-------------|
| `config/decay_config.yaml` | Sector decay parameters | FR12, FR13 |
| `mcp_server/tools/reclassify_memory_sector.py` | Manual reclassification | FR5-FR10 |
| `mcp_server/db/migrations/022_add_memory_sector.sql` | Schema migration | FR20-FR22 |
| `mcp_server/utils/sector_classifier.py` | Classification logic | FR1-FR4 |
| `mcp_server/utils/decay_config.py` | Config loading + defaults | FR12, FR28-FR29 |
| `mcp_server/utils/relevance.py` | Relevance scoring with sector decay | FR11, FR14-FR15 |
| `mcp_server/utils/constants.py` | Status constants (new pattern) | - |
| `tests/fixtures/__init__.py` | Export fixtures | - |
| `tests/fixtures/golden_set_sectors.py` | Golden Set fixture | - |
| `tests/unit/test_sector_classifier.py` | Classification tests | - |
| `tests/unit/test_decay_config.py` | Config loading tests | - |
| `tests/unit/test_reclassify_memory_sector.py` | Tool unit tests | - |
| `tests/unit/test_query_filter.py` | Query filter tests | FR16-FR19 |
| `tests/integration/test_reclassify_smf.py` | SMF integration tests | FR9, FR23 |
| `tests/performance/test_baseline.py` | Latency baseline | NFR1 |

**Modified Files (6):**

| File | Modification | FR Coverage |
|------|--------------|-------------|
| `mcp_server/tools/graph_add_edge.py` | +classify on insert, +sector in response | FR1-FR4, FR24 |
| `mcp_server/tools/graph_add_node.py` | +classify on insert, +sector in response | FR1-FR4, FR25 |
| `mcp_server/tools/graph_query_neighbors.py` | +sector_filter param, +sector in results, +sector decay | FR16, FR19 |
| `mcp_server/tools/hybrid_search.py` | +sector_filter param | FR17 |
| `mcp_server/tools/dissonance_check.py` | +sector awareness in edge processing | FR23 |
| `mcp_server/db/graph.py` | +memory_sector field handling | FR20 |

**Total: 13 new files, 6 modified files**

### Architectural Boundaries

**Tool Layer Boundary:**

```
Claude Code (MCP Client)
        │
        │ MCP Protocol (stdio)
        ▼
┌─────────────────────────────────────────────────────────┐
│ MCP Tools Layer                                          │
│ ├─ graph_add_edge      ──┐                              │
│ ├─ graph_add_node      ──┼─► sector_classifier          │
│ ├─ reclassify_memory   ──┘        │                     │
│ │        │                        │                     │
│ │        ▼                        ▼                     │
│ │   SMF Check ◄────────── decay_config                  │
│ │        │                        │                     │
│ ├─ graph_query_neighbors ──┬─► sector_filter            │
│ ├─ hybrid_search         ──┘      │                     │
│ │                                 ▼                     │
│ │                          relevance.py (sector decay)  │
│ │                                 │                     │
│ └─ dissonance_check ◄─────────────┘ (sector-aware)      │
└─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│ Database Layer (graph.py)                                │
│ ├─ edges.memory_sector (VARCHAR)                        │
│ └─ edges.properties["last_reclassification"]            │
└─────────────────────────────────────────────────────────┘
```

**Config Boundary:**

```
config/decay_config.yaml (File System)
        │
        │ load at startup (lazy)
        ▼
utils/decay_config.py (_cached_config singleton)
        │
        │ get_decay_config()
        ▼
utils/relevance.py (calculate_relevance_score)
        │
        ▼
graph_query_neighbors.py (IEF scoring)
```

**SMF Integration Boundary:**

```
reclassify_memory_sector (Tool)
        │
        │ check is_constitutive
        ▼
SMF bilateral consent check (existing smf_* tools)
        │
        ├─► Approved: Update sector
        └─► Denied: Return consent_required error
```

### Requirements to Structure Mapping

**FR Category: Memory Sector Classification (FR1-FR4, FR30)**

| Requirement | Implementation Location |
|-------------|------------------------|
| FR1: Auto-classify edges | `tools/graph_add_edge.py` calls `sector_classifier.py` |
| FR2: Classification rules | `utils/sector_classifier.py` rule logic |
| FR3: Default sector | `utils/sector_classifier.py` returns "semantic" |
| FR4: View sector in responses | All tool responses include `memory_sector` |
| FR30: Unknown relations | `utils/sector_classifier.py` fallback to "semantic" |

**FR Category: Memory Sector Reclassification (FR5-FR10, FR26-FR27)**

| Requirement | Implementation Location |
|-------------|------------------------|
| FR5: Request reclassification | `tools/reclassify_memory_sector.py` entry point |
| FR6: Identify by names | `tools/reclassify_memory_sector.py` lookup logic |
| FR7: Optional edge_id | `tools/reclassify_memory_sector.py` parameter |
| FR8: Ambiguous error | `tools/reclassify_memory_sector.py` error handling |
| FR9: Bilateral consent | `tools/reclassify_memory_sector.py` SMF check |
| FR10: Audit log | `tools/reclassify_memory_sector.py` properties update |
| FR26: Invalid sector error | `tools/reclassify_memory_sector.py` validation |
| FR27: Not found error | `tools/reclassify_memory_sector.py` error handling |

**FR Category: Sector-Specific Decay (FR11-FR15, FR28-FR29)**

| Requirement | Implementation Location |
|-------------|------------------------|
| FR11: Sector-specific calculation | `utils/relevance.py` new function |
| FR12: Load YAML config | `utils/decay_config.py` loader |
| FR13: Configurable S_base/S_floor | `config/decay_config.yaml` + dataclass |
| FR14: Different decay rates | `utils/relevance.py` uses sector config |
| FR15: Emotional > Semantic retention | `config/decay_config.yaml` values |
| FR28: Default config fallback | `utils/decay_config.py` DEFAULT_DECAY_CONFIG |
| FR29: Log fallback warning | `utils/decay_config.py` logger.warning |

**FR Category: Query Filtering (FR16-FR19)**

| Requirement | Implementation Location |
|-------------|------------------------|
| FR16: Filter query_neighbors | `tools/graph_query_neighbors.py` sector_filter param |
| FR17: Filter hybrid_search | `tools/hybrid_search.py` sector_filter param |
| FR18: No filter = all sectors | Tool implementations |
| FR19: Include sector in results | All tool response schemas |

**FR Category: Schema & Migration (FR20-FR22)**

| Requirement | Implementation Location |
|-------------|------------------------|
| FR20: Store sector on edges | `db/migrations/022_add_memory_sector.sql` |
| FR21: Migrate existing edges | `db/migrations/022_add_memory_sector.sql` Phase 2 |
| FR22: Backward compatibility | Migration DEFAULT 'semantic' |

**FR Category: Integration (FR23-FR25)**

| Requirement | Implementation Location |
|-------------|------------------------|
| FR23: SMF integration | `tools/reclassify_memory_sector.py` consent check |
| FR24: Sector in graph_add_edge | `tools/graph_add_edge.py` response schema |
| FR25: Sector in graph_add_node | `tools/graph_add_node.py` response schema |

### Test Coverage Mapping

| FR Range | Test File | Expected Test Cases |
|----------|-----------|---------------------|
| FR1-FR4, FR30 | `test_sector_classifier.py` | 20 Golden Set + 5 edge cases |
| FR5-FR10, FR26-FR27 | `test_reclassify_memory_sector.py` | 7 cases (happy + error paths) |
| FR11-FR15, FR28-FR29 | `test_decay_config.py` | 15 cases (5 sectors × 3 scenarios) |
| FR16-FR19 | `test_query_filter.py` | 10 cases (filter combinations) |
| FR23 | `test_reclassify_smf.py` | 3 cases (consent flow) |
| NFR1 | `test_baseline.py` | Latency benchmarks |

### Integration Points

**Internal Communication:**

| From | To | Pattern |
|------|-----|---------|
| `graph_add_edge` | `sector_classifier` | Direct function call |
| `reclassify_memory_sector` | SMF tools | `check_bilateral_consent()` call |
| `graph_query_neighbors` | `relevance.py` | IEF scoring with sector decay |
| `dissonance_check` | edges table | Read `memory_sector` field |
| All tools | `decay_config` | `get_decay_config()` singleton |

**External Integrations (Unchanged):**

- OpenAI API (Embeddings) - no Epic 8 changes
- Anthropic API (Haiku) - no Epic 8 changes
- PostgreSQL + pgvector - schema extension only

### New Patterns Introduced

**1. `utils/constants.py` Pattern:**

This is a new pattern for the project. Previously, constants were defined inline. Epic 8 introduces centralized status constants:

```python
# utils/constants.py - New pattern for project
class ReclassifyStatus:
    SUCCESS = "success"
    AMBIGUOUS = "ambiguous"
    # ...
```

**Future tools should follow this pattern for their status constants.**

**2. `tests/fixtures/` Pattern:**

Shared test fixtures are now centralized:

```python
# tests/fixtures/__init__.py
from tests.fixtures.golden_set_sectors import GOLDEN_SET_SECTORS
```

**3. `tests/performance/` Pattern:**

Performance/benchmark tests are now separated from unit tests.

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
All 5 critical decisions are mutually compatible. Python Literal types work with PostgreSQL VARCHAR, YAML config aligns with cold-reload requirement, and SMF integration uses existing proven patterns.

**Pattern Consistency:**
All 10 implementation patterns are consistent with the existing codebase style. New patterns (`utils/constants.py`, `tests/fixtures/`, `tests/performance/`) are documented as explicit extensions.

**Structure Alignment:**
The delta structure (14 new, 6 modified files) follows existing project conventions. Correct paths verified (`mcp_server/` not `src/mcp_server/`).

### Requirements Coverage Validation ✅

**Functional Requirements Coverage:**
30/30 FRs (100%) have explicit implementation locations documented in the Requirements to Structure Mapping.

**Non-Functional Requirements Coverage:**
All 17 NFRs are addressed through architectural decisions:
- Performance (NFR1-4): Lightweight rule logic, indexed queries
- Reliability (NFR5-8): Backward compatibility, idempotent migration, config fallback
- Integration (NFR9-11): SMF bilateral consent, existing tool patterns
- Observability (NFR15-16): Structured logging patterns

### Implementation Readiness Validation ✅

**Decision Completeness:**
- 4 critical decisions with explicit rationale
- 5 deferred decisions documented for Growth phase
- All technology versions specified

**Structure Completeness:**
- 14 new files with purpose and FR coverage
- 6 modified files with specific changes
- Complete test coverage mapping (60+ expected tests)

**Pattern Completeness:**
- 11 enforcement guidelines for AI agents
- Good/anti-pattern examples for each category
- Canonical import paths documented

### Gap Analysis Results

**Critical Gaps:** None

**Important Gaps Resolved:**
- `check_bilateral_consent()` → Uses existing SMF pattern from Epic 7
- `relevance.py` scope → Extracted + parametric extension (formula unchanged)

**Deferred to Growth Phase:**
- Protocol-based classifier for LLM swap
- Hot-reload config
- DB CHECK constraint

### Clarification: IEF Formula Preservation

**Epic 7 Formula (UNCHANGED):**

```python
S = S_base * (1 + math.log(1 + access_count))
relevance_score = math.exp(-days_since_last_access / S)
```

**Epic 8 Extension (PARAMETRIC ONLY):**

```python
sector_decay = get_decay_config()[edge.memory_sector]
S = sector_decay.S_base * (1 + math.log(1 + access_count))
if sector_decay.S_floor:
    S = max(S, sector_decay.S_floor)
relevance_score = math.exp(-days_since_last_access / S)
```

The formula remains exactly as Epic 7. Only S_base and S_floor become sector-dependent.

### Corrected File Inventory

**New Files (14):**

| File | Purpose | FR Coverage |
|------|---------|-------------|
| `config/decay_config.yaml` | Sector decay parameters | FR12, FR13 |
| `mcp_server/tools/reclassify_memory_sector.py` | Manual reclassification | FR5-FR10 |
| `mcp_server/db/migrations/022_add_memory_sector.sql` | Schema migration | FR20-FR22 |
| `mcp_server/utils/sector_classifier.py` | Classification logic | FR1-FR4 |
| `mcp_server/utils/decay_config.py` | Config loading + defaults | FR12, FR28-FR29 |
| `mcp_server/utils/relevance.py` | Extracted + extended IEF scoring | FR11, FR14-FR15 |
| `mcp_server/utils/constants.py` | Status constants | - |
| `tests/fixtures/__init__.py` | Export fixtures | - |
| `tests/fixtures/golden_set_sectors.py` | Golden Set fixture | - |
| `tests/unit/test_sector_classifier.py` | Classification tests | - |
| `tests/unit/test_decay_config.py` | Config loading tests | - |
| `tests/unit/test_reclassify_memory_sector.py` | Tool unit tests | - |
| `tests/unit/test_query_filter.py` | Query filter tests | FR16-FR19 |
| `tests/unit/test_relevance.py` | IEF + sector decay tests | FR11, FR14-FR15 |
| `tests/integration/test_reclassify_smf.py` | SMF integration tests | FR9, FR23 |
| `tests/performance/test_baseline.py` | Latency baseline | NFR1 |

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed (Brownfield, Delta extension)
- [x] Scale and complexity assessed (14 new, 6 modified files)
- [x] Technical constraints identified (Cold-reload, SMF bilateral)
- [x] Cross-cutting concerns mapped (7 concerns)

**✅ Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified (Python 3.11+, PostgreSQL, etc.)
- [x] Integration patterns defined (SMF, IEF, Dissonance Engine)
- [x] Performance considerations addressed (NFR1, NFR2)

**✅ Implementation Patterns**
- [x] Naming conventions established (MemorySector Literal)
- [x] Structure patterns defined (File locations)
- [x] Communication patterns specified (Logging, Error responses)
- [x] Process patterns documented (Classification, Reclassification, Config loading)

**✅ Project Structure**
- [x] Complete directory structure defined (Delta from existing)
- [x] Component boundaries established (Tool, DB, Utils layers)
- [x] Integration points mapped (SMF, IEF, Dissonance)
- [x] Requirements to structure mapping complete (30 FRs)

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** HIGH

**Key Strengths:**
1. Complete FR coverage with explicit file mapping
2. Consistent with existing codebase patterns
3. Clear enforcement guidelines for AI agents
4. Comprehensive test structure with Golden Set
5. IEF formula preservation explicitly documented

**Areas for Future Enhancement:**
1. LLM-based sector classification (Growth Phase)
2. Hot-reload for decay config (Growth Phase)
3. Additional relation mappings as usage patterns emerge

### Implementation Handoff

**AI Agent Guidelines:**

1. Follow all architectural decisions exactly as documented
2. Use `MemorySector` Literal type for all sector values
3. Import from canonical locations only
4. Use `get_decay_config()` singleton, never direct file access
5. Follow structured logging patterns for all Epic 8 code
6. Respect SMF bilateral consent for constitutive edges
7. **The relevance score formula from Epic 7 MUST NOT be changed. Only S_base and S_floor become sector-dependent.**

**First Implementation Priority:**

1. Run baseline performance tests (NFR1 requirement)
2. Execute schema migration `022_add_memory_sector.sql`
3. Implement `utils/decay_config.py` with defaults
4. Implement `utils/relevance.py` (extract existing IEF + sector extension)
5. Implement `utils/sector_classifier.py` with Golden Set tests
6. Extend existing tools with classification calls
7. Implement `reclassify_memory_sector` tool

## Architecture Completion Summary

### Workflow Completion

**Architecture Decision Workflow:** COMPLETED ✅
**Total Steps Completed:** 8
**Date Completed:** 2026-01-08
**Document Location:** `_bmad-output/planning-artifacts/architecture.md`

### Final Architecture Deliverables

**📋 Complete Architecture Document**

- All architectural decisions documented with specific versions
- Implementation patterns ensuring AI agent consistency
- Complete project structure with all files and directories
- Requirements to architecture mapping (30 FRs, 17 NFRs)
- Validation confirming coherence and completeness

**🏗️ Implementation Ready Foundation**

- 4 critical architectural decisions made
- 10 implementation patterns defined
- 14 new files + 6 modified files specified
- 30 functional requirements fully supported
- 17 non-functional requirements addressed

**📚 AI Agent Implementation Guide**

- Technology stack: Python 3.11+, PostgreSQL 15+, pgvector
- 11 enforcement guidelines for consistent implementation
- Project structure with clear layer boundaries
- Integration patterns: SMF, IEF, Dissonance Engine

### Development Sequence

1. **Run baseline performance tests** (NFR1 requirement)
2. **Execute schema migration** `022_add_memory_sector.sql`
3. **Implement utils** (`decay_config.py`, `relevance.py`, `sector_classifier.py`)
4. **Extend existing tools** with classification and sector_filter
5. **Implement new tool** `reclassify_memory_sector`
6. **Run Golden Set tests** (20 pre-classified edges)
7. **Validate I/O's moment retrieval** (Der "Moment-Test")

### Quality Assurance Checklist

**✅ Architecture Coherence**
- [x] All decisions work together without conflicts
- [x] Technology choices are compatible
- [x] Patterns support the architectural decisions
- [x] Structure aligns with all choices

**✅ Requirements Coverage**
- [x] All 30 functional requirements are supported
- [x] All 17 non-functional requirements are addressed
- [x] Cross-cutting concerns (7) are handled
- [x] Integration points are defined

**✅ Implementation Readiness**
- [x] Decisions are specific and actionable
- [x] Patterns prevent agent conflicts
- [x] Structure is complete and unambiguous
- [x] Good/anti-pattern examples provided

### Project Success Factors

**🎯 Clear Decision Framework**
Every technology choice was made collaboratively with Party Mode review, ensuring all perspectives were considered.

**🔧 Consistency Guarantee**
Implementation patterns and enforcement guidelines ensure that AI agents produce compatible, consistent code.

**📋 Complete Coverage**
All PRD requirements are architecturally supported, with explicit FR-to-file mapping.

**🏗️ Solid Foundation**
Brownfield extension approach maintains existing architecture while adding Memory Sectors capability.

---

**Architecture Status:** READY FOR IMPLEMENTATION ✅

**Next Phase:** Begin implementation using the architectural decisions and patterns documented herein.

**Document Maintenance:** Update this architecture when major technical decisions are made during implementation.

