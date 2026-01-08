---
project_name: 'cognitive-memory'
user_name: 'ethr'
date: '2026-01-08'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality', 'workflow_rules', 'critical_rules']
status: 'complete'
rule_count: 45
optimized_for_llm: true
---

# Project Context for AI Agents

_Critical rules and patterns for implementing code in cognitive-memory. Focus on unobvious details._

---

## Reference Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Full Architecture | `bmad-docs/epics/epic-8-architecture.md` | Decisions & rationale |
| PRD | `bmad-docs/epics/epic-8-prd.md` | Requirements (30 FRs, 17 NFRs) |
| Research | `bmad-docs/research/epic-8-hypergraphrag-deep-research.md` | Background |

**This context file contains RULES. For full decisions and rationale, see architecture.**

---

## Technology Stack & Versions

| Technology | Version | Notes |
|------------|---------|-------|
| Python | ^3.11 | Type hints required |
| MCP | ^1.23.0 | stdio transport only |
| PostgreSQL | 15+ | With pgvector extension |
| pgvector | ^0.2.0 | 1536-dim embeddings |
| OpenAI | ^1.0.0 | text-embedding-3-small |
| Anthropic | ^0.25.0 | claude-3-5-haiku for evaluation |
| pytest | ^7.4.0 | asyncio_mode = "auto" |
| black | ^24.3.0 | line-length = 88 |
| ruff | ^0.1.0 | See pyproject.toml for rules |

---

## Canonical Import Block

```python
# Standard imports for Epic 8 tools
from mcp_server.utils.sector_classifier import MemorySector, classify_memory_sector
from mcp_server.utils.decay_config import get_decay_config, SectorDecay
from mcp_server.utils.constants import ReclassifyStatus
```

---

## Critical Implementation Rules

### Python Language Rules

- **Use `Literal` types** for constrained string values (e.g., `MemorySector`)
- **Import from canonical locations only** - never star imports
- **Use dataclasses** for config/data structures
- **Async functions** must use `async def`, not `asyncio.run()` wrappers
- **Type hints required** for all function signatures

### MCP Framework Rules

- **All MCP tools return JSON** with `status` field
- **Tool names**: `snake_case` (e.g., `reclassify_memory_sector`)
- **Optional parameters**: Use `| None = None` pattern

**Standard Response Patterns:**

```python
# Success
return {"data": {...}, "status": "success"}

# Error
return {"error": "Description", "status": ReclassifyStatus.NOT_FOUND}
```

### Database Rules

- **All DB operations in `mcp_server/db/`** - never inline SQL in tools
- **Migrations are idempotent** - use `IF NOT EXISTS` patterns
- **Properties column is JSONB** - use `->>'key'` for access
- **Always rollback in tests** - see `conftest.py` pattern

### Dependency Flow

```
Tools → Utils → DB
       ↓
     Config

Tools dürfen NICHT direkt auf DB zugreifen ohne Utils.
```

### SMF (Self-Modification Framework) Rules

- **Constitutive edges require bilateral consent** - check `is_constitutive` flag
- **Never modify constitutive edges without SMF approval**
- **Resolution hyperedges use node properties** (not separate edges)

### IEF (Integrative Evaluation Function) Rules

- **Formula MUST NOT change**: `S = S_base * (1 + log(1 + access_count))`
- **Relevance**: `exp(-days_since_last_access / S)`
- **Epic 8**: Only `S_base` and `S_floor` become sector-dependent
- **IEF integration point**: `graph_query_neighbors.py`

---

## Testing Rules

### Test Organization

| Type | Location |
|------|----------|
| Unit tests | `tests/unit/test_*.py` |
| Integration tests | `tests/integration/test_*.py` |
| Performance tests | `tests/performance/test_*.py` |
| Fixtures | `tests/fixtures/*.py` |

### Test Patterns

```python
# Golden Set test pattern
@pytest.mark.parametrize("edge", GOLDEN_SET_SECTORS)
def test_classify(edge):
    result = classify_memory_sector(edge["relation"], edge["properties"])
    assert result == edge["expected_sector"]

# Async DB test pattern
@pytest.mark.asyncio
async def test_with_db(conn):
    # conn auto-rollbacks after test
    pass
```

### Critical Test Rule

**All tests must be green before marking a story complete.**

---

## Code Quality & Style Rules

### Formatting

- **black**: line-length = 88
- **ruff**: See `[tool.ruff]` in pyproject.toml
- **isort**: Handled by ruff `I` rules

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Files | `snake_case.py` | `sector_classifier.py` |
| Classes | `PascalCase` | `SectorDecay` |
| Functions | `snake_case` | `classify_memory_sector` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_DECAY_CONFIG` |
| MCP Tools | `snake_case` | `reclassify_memory_sector` |

### Logging

- **Use structured logging**: `logger.debug("message", extra={...})`
- **Never use f-strings in log messages** - use extra dict
- **Levels**: ERROR (failures), WARN (fallbacks), INFO (operations), DEBUG (details)

---

## Epic 8 Specific Rules

### Memory Sector Rules

- **Sector values always lowercase**: `"emotional"` not `"Emotional"`
- **Use `MemorySector` Literal type** for all sector values
- **Default sector is `"semantic"`** if classification fails
- **`sector_filter: None`** means ALL sectors, not empty

### Config Rules

- **Use `get_decay_config()` singleton** - never load YAML directly
- **`DEFAULT_DECAY_CONFIG` is fallback** if YAML invalid
- **Cold-reload only** - server restart for config changes

### Reclassification Rules

- **Check `is_constitutive` before reclassifying**
- **Store `last_reclassification` in edge properties** (not history)
- **Use `ReclassifyStatus` constants** for status values

### Migration Sequence

```
1. Schema first (022_add_memory_sector.sql)
2. Data migration second (same file, Phase 2)
3. Code deployment third
```

---

## Anti-Patterns (NEVER DO)

| Wrong | Right | Why |
|-------|-------|-----|
| `"Emotional"` | `"emotional"` | Literal type mismatch |
| `with open("config/...")` | `get_decay_config()` | Singleton pattern |
| `from x import *` | `from x import a, b` | Explicit imports |
| `f"Classified as {x}"` | `extra={"sector": x}` | Structured logging |
| `{"status": "sucess"}` | `ReclassifyStatus.SUCCESS` | Typo prevention |

---

## Edge Cases

| Case | Behavior |
|------|----------|
| `sector_filter=[]` | Returns nothing (not all sectors) |
| `sector_filter=None` | Returns all sectors |
| Multiple edges same source/target/relation | Return ambiguous error with edge_ids |
| Missing `S_floor` in config | Treated as None (no minimum) |
| Invalid YAML config | Use `DEFAULT_DECAY_CONFIG`, log warning |

---

## Security Rules

- **Never log sensitive properties** (emotional_valence content)
- **SMF consent is mandatory** for identity-related edges
- **Validate sector values** before database operations

---

## File Locations Quick Reference

| Purpose | Location |
|---------|----------|
| MCP Tools | `mcp_server/tools/` |
| Utilities | `mcp_server/utils/` |
| DB Layer | `mcp_server/db/` |
| Migrations | `mcp_server/db/migrations/` |
| Config Files | `config/` |
| Unit Tests | `tests/unit/` |
| Integration Tests | `tests/integration/` |
| Test Fixtures | `tests/fixtures/` |

---

## Usage Guidelines

**For AI Agents:**

- Read this file before implementing any code
- Follow ALL rules exactly as documented
- When in doubt, prefer the more restrictive option
- Reference architecture doc for full decisions/rationale

**For Humans:**

- Keep this file lean and focused on agent needs
- Update when technology stack changes
- Review quarterly for outdated rules
- Remove rules that become obvious over time

---

_Last Updated: 2026-01-08_
