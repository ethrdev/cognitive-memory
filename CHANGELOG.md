# Changelog

All notable changes to **Cognitive Memory** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.1.1] - 2026-02-11

### Added
- Tag taxonomy documentation (`docs/tag-taxonomy.md`)
- Complete tag usage guidelines with closed tags (source_type) and open tags (Projects, Topics)
- Real usage examples for tag-based retrieval
- Cross-epic consistency notes (Epic 8 memory_sector, Epic 11 hybrid_search)

### Changed
- README.md: Added reference to tag-taxonomy documentation

---

## [1.1.0] - 2026-01-27

### Multi-Project Architecture

Major update to support shared Neon DB infrastructure across all ai-experiments projects with namespace isolation.

### Added

- **PROJECT_ID column** to all core tables (nodes, edges, l2_insights, chunks, episode_memory) for namespace isolation
- **Multi-Project Configuration** support for shared Neon DB instance
- **Integration Test Suite** (test_neon_connection.py) with 12 comprehensive tests
- **Project-specific environments**: `cognitive`, `agentic-business`, `semantic`, `io`

### Changed

- **Database Configuration** updated to use shared Neon DB:
  - `ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb`
  - All projects now share single Neon DB instance for cost efficiency
- **MCP Server configuration** updated with PROJECT_ID environment variable
- **Schema enhancements**:
  - `project_id` VARCHAR(100) DEFAULT 'cognitive' added to all tables
  - Enhanced indexes for project_id filtering
  - Updated foreign key constraints with CASCADE deletes

### Fixed

- **Connection pooling** for Neon DB with TCP keep-alive settings
- **UUID type handling** in psycopg2 compatibility layer
- **Transaction management** with explicit commits for data visibility

### Test Results

| Test Category | Tests | Passed | Status |
|--------------|-------|--------|--------|
| Database Connection | 1 | 1 | ✅ |
| Schema Validation | 1 | 1 | ✅ |
| Graph Operations | 4 | 4 | ✅ |
| Vector Search | 1 | 1 | ✅ |
| Project Isolation | 1 | 1 | ✅ |
| pgvector Extension | 1 | 1 | ✅ |
| **Total** | **12** | **12** | **✅ 100%** |

### Database Statistics

- **165 chunks** with embeddings indexed
- **91 episodes** stored in episode_memory
- **15 columns** in l2_insights with io_category and memory_strength
- **pgvector extension** installed and operational

### Migration Notes

For existing installations:

```bash
# Add project_id column to existing tables
psql "$DATABASE_URL" -c "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS project_id VARCHAR(100) DEFAULT 'cognitive';"
psql "$DATABASE_URL" -c "ALTER TABLE edges ADD COLUMN IF NOT EXISTS project_id VARCHAR(100) DEFAULT 'cognitive';"
psql "$DATABASE_URL" -c "ALTER TABLE l2_insights ADD COLUMN IF NOT EXISTS project_id VARCHAR(100) DEFAULT 'cognitive';"
psql "$DATABASE_URL" -c "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS project_id VARCHAR(100) DEFAULT 'cognitive';"
psql "$DATABASE_URL" -c "ALTER TABLE episode_memory ADD COLUMN IF NOT EXISTS project_id VARCHAR(100) DEFAULT 'cognitive';"

# Update .env with PROJECT_ID
echo "PROJECT_ID=cognitive" >> .env
```

---

## [1.0.0] - 2024-11-24

### Initial Release

First stable release of the Cognitive Memory System - an MCP-based persistent memory for Claude Code.

### Added

#### Core MCP Infrastructure
- MCP Server with stdio transport for Claude Code integration
- PostgreSQL + pgvector database backend with IVFFlat indexing
- 7 MCP Tools for memory operations
- 5 MCP Resources for read-only state access

#### Memory Layers
- **L0 Raw Memory**: Complete dialogue transcript storage
- **L2 Insights**: Semantic compression with 1536-dim embeddings
- **Working Memory**: Session context with LRU eviction (8-10 items)
- **Episode Memory**: Verbal reinforcement learning reflections
- **Stale Memory**: Archive for critical evicted items

#### RAG Pipeline
- Hybrid Search with RRF fusion (semantic 80%, keyword 20%)
- Query Expansion with semantic variants
- Chain-of-Thought generation framework
- Haiku API integration for evaluation and reflexion

#### Evaluation System
- Dual-Judge implementation (GPT-4o + Haiku)
- Cohen's Kappa calculation for IRR validation
- Golden Test Set for model drift detection
- Ground Truth collection with stratified sampling

#### Production Features
- API retry logic with exponential backoff
- Claude Code fallback for API outages
- Latency benchmarking (p50/p95/p99)
- PostgreSQL backup strategy (daily, 7-day retention)
- systemd service for daemonization
- Budget monitoring with cost alerts

### Performance

| Metric | Target | Achieved |
|--------|--------|----------|
| Precision@5 | ≥0.75 | 0.72 |
| Cohen's Kappa | >0.70 | ✓ |
| End-to-End Latency | <5s (p95) | ✓ |
| Uptime | >99% | ✓ |
| Monthly Budget | $5-10 | ✓ |

### MCP Tools

1. `store_raw_dialogue` - L0 dialogue storage
2. `compress_to_l2_insight` - L2 creation with embedding
3. `hybrid_search` - Semantic + keyword retrieval
4. `update_working_memory` - Session state management
5. `store_episode` - Reflexion storage
6. `store_dual_judge_scores` - IRR validation
7. `get_golden_test_results` - Drift detection

### MCP Resources

1. `memory://l2-insights` - Semantic search over insights
2. `memory://working-memory` - Current session context
3. `memory://episode-memory` - Past experience retrieval
4. `memory://l0-raw` - Raw dialogue access
5. `memory://stale-memory` - Archived items

---

## Architecture

```
Claude Code (MAX Subscription)
├── Generation, Planning, CoT ($0/mo)
└── MCP Server (Python, local)
    ├── PostgreSQL + pgvector
    ├── Memory Layers (L0, L2, Working, Episode)
    └── External APIs ($5-10/mo)
        ├── OpenAI Embeddings
        ├── GPT-4o Dual Judge
        └── Haiku Evaluation/Reflexion
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.
