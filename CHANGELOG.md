# Changelog

All notable changes to **Cognitive Memory** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
