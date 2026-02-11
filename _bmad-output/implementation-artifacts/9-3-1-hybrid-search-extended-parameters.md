# Story 9.3.1: hybrid-search-extended-parameters

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Cognitive Memory System Developer**,
I want **hybrid_search extended with tags_filter, date_from, date_to, and source_type_filter parameters with pre-filtering applied BEFORE vector search**,
so that **I/O can efficiently search within specific time ranges, tag categories, and source types while maintaining query performance**.

## Acceptance Criteria

1. **hybrid_search accepts new filter parameters**
   - `tags_filter`: list[str] | None - Filter by tag names
   - `date_from`: datetime | None - Filter results after this date
   - `date_to`: datetime | None - Filter results before this date
   - `source_type_filter`: list[str] | None - Filter by source types (e.g., ["episode_memory", "l2_insight", "graph"])
   - All parameters are optional and independently combinable
   - Parameters are validated with clear error messages

2. **Pre-filtering is applied BEFORE vector search (FR14)**
   - L2 insights semantic search filters by tags, date range, source_type BEFORE pgvector similarity search
   - L2 insights keyword search filters by tags, date range, source_type BEFORE FTS query
   - Episode semantic search filters by date range BEFORE pgvector similarity search
   - Episode keyword search filters by date range BEFORE FTS query
   - Graph search results are filtered by source_type BEFORE graph traversal
   - Pre-filtering significantly reduces vector search overhead for large datasets

3. **Pre-filtering maintains backward compatibility (NFR3)**
   - All filters are optional - existing calls without new parameters work unchanged
   - Default behavior (no filters) returns all results
   - Response format remains unchanged (no breaking changes)

4. **Filter parameters are included in response metadata**
   - Response includes applied filters in query_params or filter section
   - Enables client-side verification of what was filtered

5. **Integration with existing filter infrastructure**
   - tags_filter uses existing tags column (from Epic 9.1) with GIN index
   - date range filtering uses existing created_at columns with indexes
   - source_type_filter validates against allowed source types
   - Filters work with existing sector_filter (from Story 9.4)

6. **Performance validation tests confirm pre-filtering benefit**
   - Pre-filtered hybrid search completes faster than full dataset search
   - Vector search operates on reduced dataset (NFR4: no significant overhead)
   - Pagination works correctly with pre-filtered results

7. **Comprehensive test coverage for filter combinations**
   - Single filter tests (tags_filter only, date_from only, etc.)
   - Combined filter tests (tags + date range, date range + source_type, all filters)
   - Edge case tests (date_from > date_to, invalid dates, empty filters)
   - Integration tests with real database data

## Tasks / Subtasks

- [x] Add filter parameter validation
  - [x] Add `validate_filter_params()` function for new filter parameters
  - [x] Validate tags_filter is list of strings or None
  - [x] Validate date_from is datetime or None
  - [x] Validate date_to is datetime or None
  - [x] Validate date_from <= date_to logical constraint
  - [x] Validate source_type_filter against allowed sources
  - [x] Unit tests for all filter validation logic

- [x] Extend semantic_search with pre-filtering
  - [x] Add tags_filter parameter to WHERE clause
  - [x] Add date range filtering (created_at >= date_from AND created_at <= date_to)
  - [x] Add source_type_filter parameter validation
  - [x] Ensure GIN index on tags column is used
  - [x] Add logging for pre-filter statistics (rows filtered vs total)

- [x] Extend keyword_search with pre-filtering
  - [x] Add tags_filter parameter to FTS query
  - [x] Add date range filtering to WHERE clause
  - [x] Add source_type_filter parameter
  - [x] Ensure FTS GIN index is used effectively

- [x] Extend episode searches with pre-filtering
  - [x] episode_semantic_search: Add date range filtering
  - [x] episode_keyword_search: Add date range filtering
  - [x] Episodes excluded from source_type_filter (always return episodes)

- [x] Extend graph_search with source_type filtering
  - [x] Add source_type_filter to exclude results from unwanted sources
  - [x] Filter before graph traversal for performance
  - [x] Document allowed source types

- [x] Update handle_hybrid_search with new parameters
  - [x] Extract new filter parameters from arguments
  - [x] Validate all filter parameters before execution
  - [x] Pass filters to all search functions
  - [x] Include applied filters in response metadata
  - [x] Backward compatibility: None values mean "no filter"

- [x] Add comprehensive integration tests
  - [x] Test pre-filtering with tags_filter only
  - [x] Test date range filtering with various combinations
  - [x] Test source_type_filter with each source type
  - [x] Test combined filters (tags + date + source_type)
  - [x] Test empty filter results vs. unfiltered results
  - [x] Test filter combinations with existing sector_filter

- [x] Add performance validation tests
  - [x] Benchmark pre-filtered vs. unfiltered query performance
  - [x] Verify pre-filtering reduces vector search size
  - [x] Measure query latency with large dataset
  - [x] Verify <1s latency target is met (NFR4)

- [x] Update documentation
  - [x] Add filter parameter documentation to tool docstring
  - [x] Document pre-filtering behavior and performance characteristics
  - [x] Include examples of filter combinations
  - [x] Document interaction with sector_filter

## Dev Notes

### Implementation Context

**Epic 9 Background:**
- Epic 9.1 (Story 9-1-3) added `tags` column to `episode_memory` and `l2_insights` tables
- Epic 9.2 (Stories 9-2-1, 9-2-2, 9-2-3) added `list_episodes` and `list_insights` with tag filtering
- This story (9.3.1) extends `hybrid_search` with tag, date range, and source type filtering

**Current hybrid_search Architecture:**
- Entry point: `handle_hybrid_search()` in `mcp_server/tools/__init__.py` (lines 1312-1551)
- Currently supports: `query_text`, `query_embedding`, `top_k`, `weights`, `sector_filter`, `filter` (generic)
- Sub-functions:
  - `semantic_search()` - L2 insights vector search via pgvector
  - `keyword_search()` - L2 insights FTS search
  - `episode_semantic_search()` - Episode memory vector search
  - `episode_keyword_search()` - Episode memory FTS search
  - `graph_search()` - Graph-based neighbor search

### Pre-Filtering Architecture

**Design Principle: Filter BEFORE Search (FR14)**

The key requirement is that filtering happens BEFORE the expensive vector/search operations:

```python
# WRONG: Post-filtering (violates FR14)
results = semantic_search(query_embedding)  # Searches ALL vectors
if tags_filter:
    results = [r for r in results if r.tags in tags_filter]  # Wasted work

# CORRECT: Pre-filtering (satisfies FR14)
if tags_filter:
    where_clause += "AND tags @> %s"  # Database filter
results = semantic_search(query_embedding, where=where_clause)  # Searches filtered set
```

### Database Schema Reference

**l2_insights table (from Epic 9.1):**
```sql
CREATE TABLE l2_insights (
    id SERIAL PRIMARY KEY,
    project_id VARCHAR(50) NOT NULL DEFAULT 'io',
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    source_ids INTEGER[],
    metadata JSONB,              -- Contains memory_sector, tags
    created_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}',      -- GIN indexed from Epic 9.1
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Indexes for filtering
CREATE INDEX idx_l2_insights_created_at ON l2_insights(created_at DESC);
CREATE INDEX idx_l2_insights_tags ON l2_insights USING gin(tags);
CREATE INDEX idx_l2_insights_project_id ON l2_insights(project_id);  -- From Epic 11
```

**episode_memory table (from Epic 9.1):**
```sql
CREATE TABLE episode_memory (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    reward FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}',      -- GIN indexed from Epic 9.1
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Index for filtering
CREATE INDEX idx_episode_memory_created_at ON episode_memory(created_at DESC);
CREATE INDEX idx_episode_memory_tags ON episode_memory USING gin(tags);
```

### Filter Parameter Specifications

| Parameter | Type | Default | Validation | Database Column | Index Used |
|------------|------|----------|-------------|------------------|--------------|
| `tags_filter` | `list[str] \| None` | `None` = no filter | `tags` (TEXT[]) | GIN `idx_*_tags` |
| `date_from` | `datetime \| None` | `None` = no start date | `created_at` | B-tree `idx_*_created_at` |
| `date_to` | `datetime \| None` | `None` = no end date | `created_at` | B-tree `idx_*_created_at` |
| `source_type_filter` | `list[str] \| None` | `None` = no source filter | N/A (table-level) | N/A |

**Allowed source_type values:**
- `"l2_insight"` - L2 compressed insights
- `"episode_memory"` - Episode memory entries
- `"graph"` - Graph-based results

### Integration with Existing sector_filter (Story 9.4)

The `sector_filter` parameter (already implemented) must work alongside new filters:

```python
# Example: Combined filtering
WHERE
    tags @> %s                    -- tags_filter
    AND created_at >= %s            -- date_from
    AND created_at <= %s            -- date_to
    AND metadata->>'memory_sector' = ANY(%s)  -- sector_filter
```

**Filter Interaction Behavior:**

All filters are applied independently using AND logic - a result must match ALL specified filters:

| Filter Combination | Behavior | Example Use Case |
|------------------|-------------|-------------------|
| `sector_filter` + `tags_filter` | Only items in specified sectors AND with specified tags | Find "python" tagged insights in "semantic" sector only |
| `sector_filter` + `date_range` | Only items in specified sectors AND within date range | Find insights from "emotional" sector created last week |
| `tags_filter` + `date_range` | Items with specified tags AND within date range (any sector) | Find "important" tagged items from Q1 2024 |
| `tags_filter` + `source_type_filter` | Items with specified tags from specified sources only | Find "python" tagged L2 insights (exclude episodes) |
| All four filters | Items matching ALL conditions simultaneously | Find "python" tagged "semantic" sector L2 insights from 2024 |

**Performance Impact:**

Each filter uses database indexes:
- `sector_filter`: GIN index on `metadata->>'memory_sector'`
- `tags_filter`: GIN index on `tags` column
- `date_from/date_to`: B-tree index on `created_at`
- `source_type_filter`: Applied before query execution (excludes entire search branches)

PostgreSQL's query optimizer automatically chooses the most selective filter first, minimizing performance impact.

**Backward Compatibility:**

All filters are optional (default: `None`). Existing code using only `sector_filter` continues to work unchanged:

```python
# Still works (existing behavior)
handle_hybrid_search({"query_text": "test", "sector_filter": ["semantic"]})

# New (with additional filters)
handle_hybrid_search({
    "query_text": "test",
    "sector_filter": ["semantic"],
    "tags_filter": ["python"],
    "date_from": "2024-01-01T00:00:00"
})
```

### Performance Considerations (NFR4)

**Pre-filtering Performance Benefits:**
1. Reduced vector search space - pgvector operates on filtered subset
2. Reduced FTS search space - text search on filtered subset
3. Index utilization - GIN indexes on tags and created_at are efficient
4. Early exit for empty filter results - avoid search entirely

**Expected Performance Impact:**
- Pre-filtering with tags: ~10-50ms for GIN index scan
- Pre-filtering with date range: ~5-20ms for B-tree index scan
- Combined filters: Database optimizer chooses most selective filter first
- Overall: Pre-filtering should add <50ms overhead but save >100ms of vector search on large datasets

### Project Structure Notes

**Files to Create:**
- `mcp_server/utils/filter_validation.py` - NEW: Filter parameter validation utilities
- `tests/unit/test_filter_validation.py` - NEW: Filter validation unit tests

**Files to Modify:**
- `mcp_server/tools/__init__.py` - MODIFIED:
  - Add filter parameter extraction in `handle_hybrid_search()`
  - Extend `semantic_search()` with pre-filtering
  - Extend `keyword_search()` with pre-filtering
  - Extend `episode_semantic_search()` with date filtering
  - Extend `episode_keyword_search()` with date filtering
  - Extend `graph_search()` with source_type_filter
  - Add pre-filter logging
  - Update response metadata to include applied filters

**Test Files to Create:**
- `tests/integration/test_hybrid_search_filters.py` - NEW: Comprehensive filter tests
- `tests/performance/test_pre_filtering_performance.py` - NEW: Performance benchmarks

### Code Patterns to Follow

**1. Filter Accumulation Pattern:**
```python
# Build WHERE clause incrementally
where_conditions = []
params = []

if tags_filter is not None:
    where_conditions.append("tags @> %s")
    params.append(tags_filter)

if date_from is not None:
    where_conditions.append("created_at >= %s")
    params.append(date_from)

# Combine with AND
where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
```

**2. Parameter Validation Pattern:**
```python
def validate_filter_params(
    tags_filter: list | None,
    date_from: datetime | None,
    date_to: datetime | None,
    source_type_filter: list | None,
) -> dict[str, Any]:
    """Validate filter parameters with clear error messages."""
    errors = []

    # Validate date range logic
    if date_from and date_to and date_from > date_to:
        errors.append("date_from must be <= date_to")

    # Validate source types
    allowed_sources = {"l2_insight", "episode_memory", "graph"}
    if source_type_filter:
        invalid = set(source_type_filter) - allowed_sources
        if invalid:
            errors.append(f"Invalid source types: {invalid}")

    if errors:
        return {
            "error": "Filter validation failed",
            "details": "; ".join(errors),
            "tool": "hybrid_search",
        }
    return {"status": "validation_passed"}
```

**3. Pre-filter Statistics Logging:**
```python
# Log pre-filter impact for monitoring
logger.info("Pre-filter applied", extra={
    "filter": "tags",
    "rows_before": 10000,
    "rows_after": 500,
    "reduction_pct": 95.0,
    "query_ms": 42,
})
```

### References

| Source | Relevant Section |
|---------|------------------|
| Epic 9 | `_bmad-output/planning-artifacts/implementation-readiness-report-epic9-2026-02-11.md` | Epic 9 requirements (FR13, FR14, NFR3, NFR4) |
| Story 9.2.3 | `_bmad-output/implementation-artifacts/9-2-3-pagination-validation.md` | Pagination validation pattern |
| Story 9.4 | Test file (sector_filter tests) | Sector filter implementation reference |
| Project Context | `project-context.md` | Coding rules and patterns |
| Architecture | `_bmad-output/planning-artifacts/architecture.md` | v3.1.0-Hybrid base architecture |
| Code | `mcp_server/tools/__init__.py` (lines 1312-1551) | Current hybrid_search implementation |

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (via create-story workflow)

### Debug Log References

None - story created from requirements analysis of Epic 9.3.

### Completion Notes List

**Story created:** 2026-02-11

**Implementation completed:** 2026-02-11

**Summary:**
Implemented pre-filtering for hybrid_search with tags_filter, date_from, date_to, and source_type_filter parameters.

**Key changes:**
1. Created `mcp_server/utils/filter_validation.py` with `validate_filter_params()` and `should_include_source_type()` functions
2. Extended `semantic_search()` with tags and date range pre-filtering
3. Extended `keyword_search()` with tags and date range pre-filtering
4. Extended `episode_semantic_search()` and `episode_keyword_search()` with date range filtering
5. Updated `handle_hybrid_search()` to extract, validate, and pass new filter parameters
6. Added `applied_filters` to response metadata for client verification
7. Updated Tool schema with new filter parameter definitions
8. Added comprehensive unit tests (20 tests)
9. Added integration tests for filter combinations
10. Added performance validation tests

**Backward compatibility:**
All new filter parameters are optional (default: None). Existing calls without these parameters work unchanged.

**Performance:**
Pre-filtering uses GIN indexes on tags column and B-tree indexes on created_at, minimizing vector search overhead.

---

_Story created: 2026-02-11_
_Epic: 9 - Structured Retrieval (Tags & Filter System)_
_Sub-Epic: 9.3 - Pre-Filtering in hybrid_search_

## File List

### New Files Created
- `mcp_server/utils/filter_validation.py` - Filter parameter validation utilities
- `tests/unit/test_filter_validation.py` - Unit tests for filter validation (20 tests)
- `tests/integration/test_hybrid_search_filters.py` - Integration tests for filter combinations (with real database fixtures)
- `tests/performance/test_pre_filtering_performance.py` - Performance validation tests

### Files Modified
- `mcp_server/tools/__init__.py` - Extended hybrid_search with new filter parameters
- `tests/conftest.py` - Added `sample_l2_insights`, `sample_l2_insights_large`, and `sample_episodes` fixtures for integration/performance testing
- `9-3-1-hybrid-search-extended-parameters.md` - Added sector_filter interaction documentation and marked all tasks complete

## Change Log

### 2026-02-11
- Extended `hybrid_search` with pre-filtering support (Story 9.3.1)
  - Added `tags_filter` parameter for filtering by tag names
  - Added `date_from` and `date_to` parameters for date range filtering
  - Added `source_type_filter` parameter for filtering by source type
  - Implemented pre-filtering logic BEFORE vector/search operations (FR14)
  - Added comprehensive test coverage for filter validation and combinations
  - Maintained full backward compatibility (all new parameters are optional)

