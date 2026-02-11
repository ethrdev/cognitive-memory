# Tag Taxonomy

## Overview

Tags provide structured metadata for episodes and insights in the Cognitive Memory System. They enable deterministic retrieval through filtering while maintaining semantic flexibility. This taxonomy follows a **hybrid approach**: closed tags for consistency + open tags for extensibility.

Tags are stored as `TEXT[]` arrays with GIN indexing for efficient array-contains queries (`tags @> ARRAY['dark-romance']`).

## Closed Tags (Recommended Values)

Closed tags provide standardized values for common metadata. While not enforced at the database level, agents should use these values consistently.

### source_type (Query Prefix Convention)

**IMPORTANT:** `source_type` is currently implemented as a **query prefix pattern**, NOT as a database tag in the `tags[]` column. When storing episodes, the source is indicated by prefixing the query text.

| Value | Prefix Pattern | Usage | Example |
|-------|---------------|--------|---------|
| `self` | `[self]` | Internal reflections, self-analysis, personal patterns | `store_episode(query="[self] Ich merke...", ...)` |
| `ethr` | `[ethr]` | Direct communication from ethr (user) | `store_episode(query="[ethr] Kannst du mir helfen...", ...)` |
| `shared` | `[shared]` | Collaborative knowledge, external research, best practices | `store_episode(query="[shared] Research: Pre-filtering...", ...)` |
| `relationship` | `[relationship]` | Interpersonal dynamics, social interactions | `store_episode(query="[relationship] Beziehungsmuster...", ...)` |

**When to use:** Apply the appropriate prefix pattern to the `query` parameter when calling `store_episode()`.

**Storage Notes:**
- Currently stored in the `query` TEXT column as a text prefix
- Pattern matching for filtering: `WHERE query LIKE '[ethr]%'`
- Future Epic 9.2 may migrate this to a dedicated `source_type` database column
- This is separate from the `tags[]` array column added in Epic 9.1.1

## Open Tags (Extensible)

Open tags allow domain-specific categorization. These are fully flexible but should follow consistency guidelines below.

### Projects

Tags for organizing work across different projects and contexts.

| Tag | Description | Usage Pattern |
|-----|-------------|---------------|
| `dark-romance` | Creative writing project - "Dark Romance" narrative | Szene analysis, character development, plot points |
| `drift` | Philosophical concept - Drift layers and transcendence | Layer theory, aesthetic drift, from-not-over |
| `cognitive-memory` | This project - MCP memory system architecture | Schema design, MCP tools, hybrid search |
| `i-o-system` | I/O System - Cognitive architecture for agents | Memory guides, consolidation, decay mechanisms |

**Guideline:** Create project tags when a distinct initiative or context generates recurring conversations worth isolating.

### Topics

Cross-cutting themes that span multiple projects.

| Tag | Description | Related Concepts |
|-----|-------------|------------------|
| `stil` | Aesthetic philosophy - "Stil" as anti-pattern avoidance | Anti-patterns, aestheticisierung, from-not-over |
| `pattern` | Reusable behavioral or architectural patterns | Validation patterns, conversation patterns |
| `architektur` | System architecture and design decisions | MCP architecture, database schema, indexing |
| `beziehung` | Interpersonal dynamics and relationship patterns | Confirmation loops, communication patterns |

**Guideline:** Create topic tags for concepts that appear across multiple conversations and benefit from cross-referencing.

## Usage Guidelines

### When to Tag

**Apply tags when:**
- Storing episodes via `store_episode(..., tags=[...])`
- Compressing insights via `compress_to_l2_insight(..., tags=[...])`
- Content belongs to a trackable project or theme
- Future retrieval by category is likely

**Do NOT tag when:**
- Content is ephemeral or throwaway
- Tag value is too generic (e.g., "info", "data")
- Category already captured by existing metadata (date, memory_sector)

### Tag Specificity

**Good tags:** `dark-romance`, `pre-filtering`, `validation-pattern`
**Too generic:** `project`, `work`, `info`
**Too specific:** `dark-romance-chapter-3-scene-2` (use metadata or query content instead)

**Rule:** Tags should group 3-50 related items. If a tag would apply to <3 items, it's too specific. If it applies to >80% of content, it's too generic.

### Consistency Rules

1. **Use lowercase:** `dark-romance` not `Dark-Romance`
2. **Use hyphens for multi-word:** `source-type` not `sourcetype`
3. **Match existing tags:** Check what tags are already in use before creating new ones
4. **Prefer existing over new:** Before creating `ai-concepts`, check if `architektur` suffices

### Tag Combinations

Tags are composable. An insight can have multiple tags:

```python
# Example: Multi-tagged insight about technical implementation
tags=["cognitive-memory", "architektur", "pattern"]
```

When filtering, array-contains requires ALL specified tags:
```sql
-- Finds insights tagged with BOTH cognitive-memory AND architektur
WHERE tags @> ARRAY['cognitive-memory', 'architektur']
```

## Examples

### Example 1: Creative Writing Context

**Episode storage:**
```python
store_episode(
    query="[dark-romance] Kira's internal conflict about the Layer",
    reward=0.7,
    reflection="Character demonstrates transcendence resistance",
    tags=["dark-romance", "drift", "beziehung"]
)
```

**Retrieval:**
```python
# Find all Dark Romance character development
hybrid_search(query="character growth motivation", tags_filter=["dark-romance"])
```

### Example 2: Technical Architecture Decision

**Insight compression:**
```python
compress_to_l2_insight(
    content="Pre-filtering before vector search reduces cost by 90% while maintaining 95% recall",
    source_ids=["ep-123", "ep-124"],
    tags=["cognitive-memory", "architektur", "pattern"]
)
```

**Retrieval:**
```python
# Browse all architecture patterns
list_insights(tags=["cognitive-memory", "architektur"])
```

### Example 3: Cross-Project Pattern Recognition

**Multi-tagged insight:**
```python
compress_to_l2_insight(
    content="Validation loops occur when agents seek confirmation rather than truth - pattern observed across I/O and human interactions",
    source_ids=["ep-045", "ep-089"],
    tags=["pattern", "beziehung", "i-o-system", "cognitive-memory"]
)
```

## References

### Epic 9 Documentation
- **Epic 9 Full Specification:** `bmad-docs/epics/epic-9-structured-retrieval-tags-filters.md`
  - [9.1 Tags Infrastructure](../../bmad-docs/epics/epic-9-structured-retrieval-tags-filters.md#story-91-tags-infrastruktur) - Schema and parameter implementation
  - [9.2 Filter Endpoints](../../bmad-docs/epics/epic-9-structured-retrieval-tags-filters.md#story-92-filter-endpoints) - list_episodes, list_insights
  - [9.3 Pre-Filtering](../../bmad-docs/epics/epic-9-structured-retrieval-tags-filters.md#story-93-pre-filtering-in-hybrid_search) - hybrid_search with tags

### Related Implementation Stories
- **[9-1-1](../../_bmad-output/implementation-artifacts/9-1-1-tags-schema-migration.md):** Schema migration adding tags columns
- **[9-1-2](../../_bmad-output/implementation-artifacts/9-1-2-compress-to-l2-insight-tags-parameter.md):** compress_to_l2_insight tags parameter

### Cross-Epic Consistency
- **Epic 8 (Decay + Sector System):** Tags complement `memory_sector` - no conflicts
- **Epic 11 (Hybrid Search):** Tags work with pre-filtering for efficient retrieval

---

*Document created: 2026-02-11*
*Epic: 9 - Structured Retrieval (Tags & Filter System)*
