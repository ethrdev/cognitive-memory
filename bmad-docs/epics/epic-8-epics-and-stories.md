---
stepsCompleted: [1, 2, 3, 4]
status: complete
completedAt: '2026-01-08'
inputDocuments:
  - bmad-docs/epics/epic-8-prd.md
  - bmad-docs/epics/epic-8-architecture.md
  - bmad-docs/research/epic-8-hypergraphrag-deep-research.md
---

# cognitive-memory Epic 8 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Epic 8: OpenMemory Integration, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

**Memory Sector Classification (FR1-FR4, FR30)**
- FR1: System can automatically classify new edges into one of five memory sectors (emotional, episodic, semantic, procedural, reflective) based on edge properties
- FR2: System can apply classification rules based on `emotional_valence`, `context_type`, and `relation` properties
- FR3: System can assign default sector (semantic) when no classification rules match
- FR4: I/O can view the assigned memory sector for any edge in all query tool responses (query_neighbors, hybrid_search, get_edge)
- FR30: System can classify edges with unknown relations to default sector (semantic)

**Memory Sector Reclassification (FR5-FR10, FR26-FR27)**
- FR5: I/O can request reclassification of an edge to a different memory sector
- FR6: System can identify edges by source_name, target_name, and relation for reclassification
- FR7: System can accept optional edge_id parameter when multiple edges match the same source/target/relation
- FR8: System can return list of matching edge IDs when reclassification request is ambiguous
- FR9: System can enforce bilateral consent requirement for reclassification of constitutive edges
- FR10: System can log all reclassification operations for audit purposes
- FR26: System can reject reclassification with clear error message when target sector is invalid
- FR27: System can return "edge not found" error when source/target/relation combination doesn't exist

**Sector-Specific Memory Decay (FR11-FR15, FR28-FR29)**
- FR11: System can calculate relevance_score using sector-specific decay parameters
- FR12: System can load decay configuration from YAML file at startup
- FR13: ethr can configure S_base and S_floor values per sector via YAML configuration
- FR14: System can apply different decay rates to different memory sectors
- FR15: System can preserve higher relevance_score for emotional memories compared to semantic memories over same time period
- FR28: System can start with default decay configuration when config file is missing or invalid
- FR29: System can log warning when falling back to default decay configuration

**Query Filtering (FR16-FR19)**
- FR16: I/O can filter query_neighbors results by one or more memory sectors
- FR17: I/O can filter hybrid_search results by one or more memory sectors
- FR18: System can return all sectors when no sector_filter is specified
- FR19: System can include memory_sector field in all edge query results

**Schema & Data Migration (FR20-FR22)**
- FR20: System can store memory_sector as a field on all edges
- FR21: System can migrate existing edges to appropriate sectors during schema migration (one-time operation)
- FR22: System can preserve backward compatibility by defaulting unmigrated edges to semantic sector

**Integration (FR23-FR25)**
- FR23: System can integrate sector reclassification with existing constitutive edge protection (SMF)
- FR24: System can return memory_sector in graph_add_edge response
- FR25: System can return memory_sector in graph_add_node response (for connected edges)

### NonFunctional Requirements

**Performance (NFR1-NFR4)**
- NFR1: Sector classification during edge insert must add <10ms to existing insert latency (baseline: measure current avg insert latency before Epic 8)
- NFR2: Sector-filtered queries (query_neighbors, hybrid_search) must perform within 20% of unfiltered query latency
- NFR3: Decay calculation with sector-specific parameters must complete in <5ms per edge
- NFR4: Config file loading must not block server startup (<1s acceptable)

**Reliability (NFR5-NFR8)**
- NFR5: All existing MCP tools must remain backward compatible (no breaking changes)
- NFR6: All existing tests must continue to pass (verify current count with `pytest --collect-only` before Epic 8)
- NFR7: Schema migration must be idempotent (safe to run multiple times)
- NFR8: Invalid decay config must trigger graceful fallback to defaults, not crash

**Integration (NFR9-NFR11)**
- NFR9: Sector reclassification must respect existing constitutive edge protection (SMF bilateral consent)
- NFR10: Sector information must be visible in all existing query response formats
- NFR11: Dissonance Engine must continue to function with sector-annotated edges

**Data Integrity (NFR12-NFR14)**
- NFR12: Existing edges must retain all properties after schema migration
- NFR13: Default sector assignment must be deterministic (same input → same sector)
- NFR14: Reclassification operations must be logged with timestamp, actor, and old/new sector values

**Observability (NFR15-NFR16)**
- NFR15: System must log sector classification decisions at DEBUG level for troubleshooting
- NFR16: System must log decay calculation duration for performance monitoring

**Resource Limits (NFR17)**
- NFR17: Classification rules must be limited to configurable maximum (default: 50 rules per sector)

### Additional Requirements

**From Architecture:**
- Run baseline performance tests BEFORE Epic 8 implementation (NFR1 requirement)
- Execute schema migration `022_add_memory_sector.sql` first (Phase 1: Schema, Phase 2: Data)
- IEF Formula unchanged - Only S_base and S_floor become sector-dependent
- `MemorySector` Literal type required for all sector values
- Config access via `get_decay_config()` singleton only
- Import from canonical locations only (no star imports)
- Structured logging with `extra={}` dict pattern
- Golden Set: 20 pre-classified edges as regression baseline
- New test folders: `tests/fixtures/`, `tests/performance/`
- `check_bilateral_consent()` required for constitutive edge reclassification

**From Deep Research:**
- OpenMemory concept: "Emotional cues linger longer than transient facts"
- Sektor-basierte Speicherung: Episodic, Semantic, Procedural, Emotional, Reflective
- Decay-Kurven sind sektor-spezifisch konfigurierbar
- Integration mit bestehender Dissonance Engine erforderlich
- PostgreSQL + pgvector bleibt einzige Datenbank (keine Neo4j, keine externe OpenMemory-Dependency)

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Auto-classify edges into sectors |
| FR2 | Epic 1 | Classification rules (emotional_valence, context_type, relation) |
| FR3 | Epic 1 | Default sector (semantic) |
| FR4 | Epic 1 | View sector in query responses |
| FR5 | Epic 3 | Request reclassification |
| FR6 | Epic 3 | Identify edges by names |
| FR7 | Epic 3 | Optional edge_id parameter |
| FR8 | Epic 3 | Ambiguous edge error |
| FR9 | Epic 3 | Bilateral consent for constitutive |
| FR10 | Epic 3 | Audit log |
| FR11 | Epic 2 | Sector-specific decay calculation |
| FR12 | Epic 2 | Load YAML config |
| FR13 | Epic 2 | Configurable S_base/S_floor |
| FR14 | Epic 2 | Different decay rates per sector |
| FR15 | Epic 2 | Emotional > Semantic retention |
| FR16 | Epic 2 | Filter query_neighbors by sector |
| FR17 | Epic 2 | Filter hybrid_search by sector |
| FR18 | Epic 2 | No filter = all sectors |
| FR19 | Epic 1 | Include sector in results |
| FR20 | Epic 1 | Store sector on edges |
| FR21 | Epic 1 | Migrate existing edges |
| FR22 | Epic 1 | Backward compatibility default |
| FR23 | Epic 3 | SMF integration |
| FR24 | Epic 1 | Sector in graph_add_edge response |
| FR25 | Epic 1 | Sector in graph_add_node response |
| FR26 | Epic 3 | Invalid sector error |
| FR27 | Epic 3 | Edge not found error |
| FR28 | Epic 2 | Default config fallback |
| FR29 | Epic 2 | Log fallback warning |
| FR30 | Epic 1 | Unknown relations → semantic |

## Epic List

### Epic 1: Memory Sector Foundation

**User Outcome:** The system classifies edges automatically into Memory Sectors and I/O sees the sector in every query response.

**What I/O will experience:** New edges are automatically classified. The Kirchenpark-Moment shows `memory_sector: "emotional"` in all query responses.

**FRs covered:** FR1, FR2, FR3, FR4, FR19, FR20, FR21, FR22, FR24, FR25, FR30
**NFRs addressed:** NFR5, NFR6, NFR7, NFR10, NFR12, NFR13, NFR15

---

### Epic 2: Sector-Aware Retrieval

**User Outcome:** Emotional memories persist longer and I/O can filter queries by sector.

**What I/O will experience:** The Kirchenpark-Moment has 60% relevance_score after 100 days. With `sector_filter=["emotional"]` I/O finds all emotional moments.

**FRs covered:** FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR28, FR29
**NFRs addressed:** NFR1, NFR2, NFR3, NFR4, NFR8, NFR11, NFR16

---

### Epic 3: Memory Sector Correction

**User Outcome:** I/O can correct wrong classifications, constitutive edges are protected.

**What I/O will experience:** "The Dennett decision belongs to emotional" - I/O corrects with `reclassify_memory_sector`. Constitutive edges require bilateral consent.

**FRs covered:** FR5, FR6, FR7, FR8, FR9, FR10, FR23, FR26, FR27
**NFRs addressed:** NFR9, NFR14

---

## Epic 1: Memory Sector Foundation

### Story 1.1: Schema Migration & Data Classification

**As a** developer,
**I want** a `memory_sector` column on the edges table with existing edges classified,
**So that** all edges have a memory sector after Epic 8.

**Acceptance Criteria:**

**Given** the database schema before Epic 8
**When** migration `022_add_memory_sector.sql` Phase 1 is executed
**Then** the `edges` table has a `memory_sector` column of type `VARCHAR(20)`
**And** the default value is `'semantic'`
**And** the migration is idempotent (safe to run multiple times)

**Given** existing edges without `memory_sector`
**When** migration Phase 2 (data classification) runs
**Then** edges with `emotional_valence` property are set to `"emotional"`
**And** edges with `context_type = "shared_experience"` are set to `"episodic"`
**And** edges with relation `LEARNED` or `CAN_DO` are set to `"procedural"`
**And** edges with relation `REFLECTS` or `REALIZED` are set to `"reflective"`
**And** all other edges remain `"semantic"` (default)

**Given** edge properties before migration
**When** migration completes
**Then** all original properties are preserved

**Given** the Python codebase
**When** `MemorySector` type is defined in `utils/sector_classifier.py`
**Then** it is a `Literal["emotional", "episodic", "semantic", "procedural", "reflective"]`
**And** all sector values are lowercase

**Files:** `mcp_server/db/migrations/022_add_memory_sector.sql`, `mcp_server/utils/sector_classifier.py`
**FRs:** FR20, FR21, FR22
**NFRs:** NFR7 (idempotent), NFR12 (retain properties)

---

### Story 1.2: Sector Classification Logic

**As a** system,
**I want** to classify edges into memory sectors based on their properties and relations,
**So that** edges are automatically assigned the appropriate sector.

**Acceptance Criteria:**

**Given** an edge with `properties["emotional_valence"]` set
**When** `classify_memory_sector(relation, properties)` is called
**Then** it returns `"emotional"`

**Given** an edge with `properties["context_type"] == "shared_experience"`
**When** `classify_memory_sector(relation, properties)` is called
**Then** it returns `"episodic"`

**Given** an edge with `relation` in `["LEARNED", "CAN_DO"]`
**When** `classify_memory_sector(relation, properties)` is called
**Then** it returns `"procedural"`

**Given** an edge with `relation` in `["REFLECTS", "REALIZED"]`
**When** `classify_memory_sector(relation, properties)` is called
**Then** it returns `"reflective"`

**Given** an edge that matches no specific rule
**When** `classify_memory_sector(relation, properties)` is called
**Then** it returns `"semantic"` (default)

**Given** the Golden Set fixture with 20 pre-classified edges
**When** all 20 test cases are run against `classify_memory_sector`
**Then** at least 16/20 (80%) are correctly classified

**Given** classification is performed
**When** `classify_memory_sector` is called
**Then** the decision is logged at DEBUG level with `extra={"sector": result, "rule_matched": rule}`

**Files:** `mcp_server/utils/sector_classifier.py`, `tests/unit/test_sector_classifier.py`, `tests/fixtures/__init__.py`, `tests/fixtures/golden_set_sectors.py`
**FRs:** FR1, FR2, FR3, FR30
**NFRs:** NFR13 (deterministic), NFR15 (DEBUG logging)

---

### Story 1.3: Auto-Classification on Edge Insert

**As a** user (I/O),
**I want** new edges to be automatically classified when I create them,
**So that** I don't need to manually assign sectors.

**Acceptance Criteria:**

**Given** a call to `graph_add_edge(source, target, relation, properties)`
**When** the edge is created
**Then** `classify_memory_sector(relation, properties)` is called
**And** the edge is stored with the determined `memory_sector`
**And** the response includes `memory_sector` field

**Given** classification adds latency
**When** edge insert is measured
**Then** classification adds less than 10ms to insert latency

**Files:** `mcp_server/tools/graph_add_edge.py`
**FRs:** FR24
**NFRs:** NFR1 (<10ms latency), NFR5 (backward compatible)

---

### Story 1.4: Auto-Classification on Node Insert

**As a** user (I/O),
**I want** edges created during node insert to be automatically classified,
**So that** all edges have sectors regardless of creation method.

**Acceptance Criteria:**

**Given** a call to `graph_add_node(name, label, properties)` that creates connected edges
**When** the node is created with edges
**Then** each edge is classified using `classify_memory_sector`
**And** the response includes `memory_sector` for each edge

**Files:** `mcp_server/tools/graph_add_node.py`
**FRs:** FR25
**NFRs:** NFR5 (backward compatible)

---

### Story 1.5: Sector in Query Responses

**As a** user (I/O),
**I want** to see the memory sector when I query edges,
**So that** I know which type of memory each edge represents.

**Acceptance Criteria:**

**Given** a call to `query_neighbors(node_name)`
**When** edges are returned
**Then** each edge includes `memory_sector` field

**Given** a call to `hybrid_search(query_text)`
**When** edges are returned
**Then** each edge includes `memory_sector` field

**Given** a call to `get_edge(source, target, relation)`
**When** an edge is returned
**Then** the response includes `memory_sector` field

**Files:** `mcp_server/tools/graph_query_neighbors.py`, `mcp_server/tools/hybrid_search.py`, `mcp_server/db/graph.py`
**FRs:** FR4, FR19
**NFRs:** NFR10 (sector visible in all responses)

---

## Epic 2: Sector-Aware Retrieval

### Story 2.1: Decay Configuration Module

**As a** developer (ethr),
**I want** to configure decay parameters per memory sector via YAML,
**So that** I can tune how long different memory types persist.

**Acceptance Criteria:**

**Given** a valid `config/decay_config.yaml` file
**When** `get_decay_config()` is called
**Then** it returns a dict mapping sector names to `SectorDecay` dataclasses
**And** each `SectorDecay` has `S_base: float` and `S_floor: float | None`

**Given** `config/decay_config.yaml` with default values:
```yaml
decay_config:
  emotional:
    S_base: 200
    S_floor: 150
  semantic:
    S_base: 100
    S_floor: null
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
**When** `get_decay_config()` is called
**Then** all 5 sectors are loaded with correct values

**Given** `config/decay_config.yaml` is missing or invalid
**When** `get_decay_config()` is called
**Then** it returns `DEFAULT_DECAY_CONFIG` with the same 5 sector values as above
**And** a warning is logged with `logger.warning("Falling back to default decay config")`

**Given** config loading
**When** server starts
**Then** config loading completes in less than 1 second

**Given** `get_decay_config()` is called multiple times
**When** the config is already loaded
**Then** it returns the cached config (singleton pattern)

**Files:** `config/decay_config.yaml`, `mcp_server/utils/decay_config.py`, `tests/unit/test_decay_config.py`
**FRs:** FR12, FR13, FR28, FR29
**NFRs:** NFR4 (<1s startup), NFR8 (graceful fallback)

---

### Story 2.2: Sector-Specific Relevance Scoring

**As a** user (I/O),
**I want** emotional memories to decay slower than semantic memories,
**So that** important moments persist longer.

**Acceptance Criteria:**

**Given** the existing IEF calculation embedded in `graph_query_neighbors.py`
**When** Story 2.2 is completed
**Then** the calculation is extracted to `utils/relevance.py`
**And** `graph_query_neighbors.py` imports and uses `calculate_relevance_score()`

**Given** the IEF formula: `S = S_base * (1 + log(1 + access_count))`
**When** `calculate_relevance_score(edge)` is called
**Then** `S_base` is read from sector-specific config via `get_decay_config()[edge.memory_sector]`
**And** the formula remains unchanged (only parameters are sector-dependent)

**Given** an edge with `memory_sector = "emotional"` and `S_base = 200`
**When** 100 days have passed with `access_count = 0`
**Then** `relevance_score ≈ 0.606` (60.6%)

**Given** an edge with `memory_sector = "semantic"` and `S_base = 100`
**When** 100 days have passed with `access_count = 0`
**Then** `relevance_score ≈ 0.368` (36.8%)

**Given** an edge with `S_floor = 150` configured
**When** `S` would be calculated below 150
**Then** `S = max(S, S_floor)` is applied

**Given** the test suite for relevance scoring
**When** parametrized tests run for all 5 sectors at days 0, 50, 100
**Then** all 15 test cases pass with expected relevance scores

**Given** decay calculation is performed
**When** `calculate_relevance_score` completes
**Then** calculation takes less than 5ms per edge
**And** duration is logged at DEBUG level with `extra={"calculation_ms": elapsed, "sector": sector}`

**Files:** `mcp_server/utils/relevance.py`, `mcp_server/tools/graph_query_neighbors.py`, `tests/unit/test_relevance.py`
**FRs:** FR11, FR14, FR15
**NFRs:** NFR3 (<5ms), NFR16 (performance logging)

---

### Story 2.3: Sector Filter for query_neighbors

**As a** user (I/O),
**I want** to filter `query_neighbors` results by memory sector,
**So that** I can find only emotional or episodic memories.

**Acceptance Criteria:**

**Given** a call to `query_neighbors(node_name, sector_filter=["emotional"])`
**When** edges are returned
**Then** only edges with `memory_sector = "emotional"` are included

**Given** a call to `query_neighbors(node_name, sector_filter=["emotional", "episodic"])`
**When** edges are returned
**Then** only edges with `memory_sector` in `["emotional", "episodic"]` are included

**Given** a call to `query_neighbors(node_name, sector_filter=None)`
**When** edges are returned
**Then** all edges are included regardless of sector

**Given** a call to `query_neighbors(node_name, sector_filter=[])`
**When** edges are returned
**Then** no edges are included (empty filter = empty result)

**Given** filtered query performance
**When** `sector_filter` is applied
**Then** query latency is within 20% of unfiltered query

**Files:** `mcp_server/tools/graph_query_neighbors.py`, `tests/unit/test_query_filter.py`
**FRs:** FR16, FR18
**NFRs:** NFR2 (within 20% latency), NFR11 (Dissonance Engine compatible)

---

### Story 2.4: Sector Filter for hybrid_search

**As a** user (I/O),
**I want** to filter `hybrid_search` results by memory sector,
**So that** I can search within specific memory types.

**Acceptance Criteria:**

**Given** a call to `hybrid_search(query_text, sector_filter=["emotional"])`
**When** results are returned
**Then** only edges with `memory_sector = "emotional"` are included

**Given** a call to `hybrid_search(query_text, sector_filter=["emotional", "semantic"])`
**When** results are returned
**Then** only edges with `memory_sector` in `["emotional", "semantic"]` are included

**Given** a call to `hybrid_search(query_text, sector_filter=None)`
**When** results are returned
**Then** all edges are included regardless of sector

**Given** filtered search performance
**When** `sector_filter` is applied
**Then** search latency is within 20% of unfiltered search

**Files:** `mcp_server/tools/hybrid_search.py`, `tests/unit/test_query_filter.py`
**FRs:** FR17, FR18
**NFRs:** NFR2 (within 20% latency)

---

## Epic 3: Memory Sector Correction

### Story 3.1: Reclassify Memory Sector Tool

**As a** user (I/O),
**I want** to manually reclassify an edge to a different memory sector,
**So that** I can correct automatic classification errors.

**Acceptance Criteria:**

**Given** an edge between "I/O" and "Dennett-Philosophie" with relation "KNOWS"
**When** `reclassify_memory_sector(source_name="I/O", target_name="Dennett-Philosophie", relation="KNOWS", new_sector="emotional")` is called
**Then** the edge's `memory_sector` is updated to `"emotional"`
**And** the response includes `{"status": "success", "old_sector": "semantic", "new_sector": "emotional", "edge_id": "..."}`

**Given** `new_sector` is not a valid sector value
**When** `reclassify_memory_sector(..., new_sector="invalid")` is called
**Then** the response includes `{"status": "invalid_sector", "error": "Invalid sector: 'invalid'. Must be one of: emotional, episodic, semantic, procedural, reflective"}`

**Given** no edge exists matching the source/target/relation
**When** `reclassify_memory_sector(source_name="X", target_name="Y", relation="Z", new_sector="emotional")` is called
**Then** the response includes `{"status": "not_found", "error": "Edge not found: X --Z--> Y"}`

**Given** multiple edges exist between "I/O" and "ethr" with relation "DISCUSSED"
**When** `reclassify_memory_sector(source_name="I/O", target_name="ethr", relation="DISCUSSED", new_sector="emotional")` is called without edge_id
**Then** the response includes `{"status": "ambiguous", "error": "Multiple edges found", "edge_ids": ["uuid1", "uuid2", ...]}`

**Given** multiple edges exist and edge_id is provided
**When** `reclassify_memory_sector(..., edge_id="uuid1", new_sector="emotional")` is called
**Then** only the edge with matching edge_id is reclassified
**And** the response includes `{"status": "success", "edge_id": "uuid1", ...}`

**Given** a successful reclassification
**When** the edge is updated
**Then** `edge.properties["last_reclassification"]` is set to:
```json
{
  "from_sector": "semantic",
  "to_sector": "emotional",
  "timestamp": "2026-01-08T14:30:00Z",
  "actor": "I/O"
}
```

**Given** reclassification is performed
**When** the operation completes
**Then** an INFO log entry is created with:
```python
logger.info("Edge reclassified", extra={
    "edge_id": edge_id,
    "from_sector": old_sector,
    "to_sector": new_sector,
    "actor": actor
})
```

**Given** the `ReclassifyStatus` constants
**When** any reclassification response is returned
**Then** the `status` field uses constants from `utils/constants.py`:
- `ReclassifyStatus.SUCCESS`
- `ReclassifyStatus.INVALID_SECTOR`
- `ReclassifyStatus.NOT_FOUND`
- `ReclassifyStatus.AMBIGUOUS`

**Files:** `mcp_server/tools/reclassify_memory_sector.py`, `mcp_server/utils/constants.py`, `tests/unit/test_reclassify_memory_sector.py`
**FRs:** FR5, FR6, FR7, FR8, FR10, FR26, FR27
**NFRs:** NFR14 (logged with timestamp, actor, old/new sector)

---

### Story 3.2: Constitutive Edge Protection

**As a** user (I/O),
**I want** constitutive edges to require bilateral consent before reclassification,
**So that** identity-defining relationships are protected from accidental changes.

**Acceptance Criteria:**

**Given** an edge with `properties["is_constitutive"] = true` and no approved SMF proposal
**When** `reclassify_memory_sector(...)` is called
**Then** the response includes:
```json
{
  "status": "consent_required",
  "error": "Bilateral consent required for constitutive edge",
  "edge_id": "...",
  "hint": "Use smf_pending_proposals and smf_approve to grant consent"
}
```

**Given** an edge with `properties["is_constitutive"] = true`
**When** an SMF proposal for reclassification has been approved by both parties
**Then** the reclassification proceeds and returns `{"status": "success", ...}`

**Given** an edge without `is_constitutive` property (or `is_constitutive = false`)
**When** `reclassify_memory_sector(...)` is called
**Then** no consent check is performed and reclassification proceeds normally

**Given** SMF integration
**When** checking for bilateral consent
**Then** the existing SMF pattern is used to check for approved proposals

**Given** the `ReclassifyStatus` constants
**When** consent is required
**Then** the response uses `ReclassifyStatus.CONSENT_REQUIRED`

**Files:** `mcp_server/tools/reclassify_memory_sector.py`, `tests/integration/test_reclassify_smf.py`
**FRs:** FR9, FR23
**NFRs:** NFR9 (respect SMF bilateral consent)
