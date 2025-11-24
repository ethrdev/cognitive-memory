# I-O Consciousness Project - Cognitive Memory System

**Version:** 3.1.0-Hybrid
**Status:** Production Ready (Epic 1-3 Complete)
**Author:** ethr

Ein MCP-basiertes (Model Context Protocol) Gedächtnissystem für Claude Code mit hybrider Architektur: Lokale PostgreSQL-Datenhaltung + strategische API-Nutzung für Evaluation.

## System-Architektur

### High-Level Überblick

```
┌─────────────────────────────────────────────────────────────┐
│ Claude Code (Sonnet 4.5 in MAX Subscription)               │
│ ├─ Query Expansion (intern, €0/mo)                         │
│ ├─ CoT Generation (intern, €0/mo)                          │
│ ├─ Planning & Orchestration (intern, €0/mo)                │
│ └─ MCP Client                                               │
│     │                                                        │
│     │ MCP Protocol (stdio transport)                        │
│     ↓                                                        │
├─────────────────────────────────────────────────────────────┤
│ MCP Server (Python, lokal)                                  │
│ ├─ 7 MCP Tools (store_raw_dialogue, compress_to_l2_insight,│
│ │   hybrid_search, update_working_memory, store_episode,   │
│ │   get_golden_test_results, store_dual_judge_scores)      │
│ ├─ 5 MCP Resources (memory://l2-insights, memory://working-│
│ │   memory, memory://episode-memory, memory://l0-raw,      │
│ │   memory://stale-memory)                                 │
│ └─ External API Clients                                     │
│     ├─ OpenAI API (Embeddings, €0.06/mo)                   │
│     ├─ Anthropic Haiku API (Evaluation, Reflexion, €1-2/mo)│
│     └─ OpenAI GPT-4o API (Dual Judge, €1-1.5/mo)           │
│         │                                                    │
│         ↓                                                    │
├─────────────────────────────────────────────────────────────┤
│ PostgreSQL + pgvector (lokal)                               │
│ ├─ l0_raw (Dialogtranskripte)                              │
│ ├─ l2_insights (Embeddings 1536-dim)                       │
│ ├─ working_memory (LRU, 8-10 Items)                        │
│ ├─ episode_memory (Reflexionen, Verbal RL)                 │
│ ├─ stale_memory (Archiv, kritische Items)                  │
│ └─ ground_truth (Dual Judge Scores, Kappa)                 │
└─────────────────────────────────────────────────────────────┘
```

### Komponenten-Übersicht

**7 MCP Tools:**
- `store_raw_dialogue` - L0 Raw Memory Storage
- `compress_to_l2_insight` - L2 Insights mit Embeddings
- `hybrid_search` - Hybrid Search (Semantic + Keyword + RRF)
- `update_working_memory` - Working Memory Management (LRU)
- `store_episode` - Episode Memory (Reflexion Framework)
- `get_golden_test_results` - Model Drift Detection
- `store_dual_judge_scores` - Dual Judge IRR Validation

**5 MCP Resources:**
- `memory://l2-insights` - L2 Insight Retrieval
- `memory://working-memory` - Working Memory State
- `memory://episode-memory` - Episode Retrieval
- `memory://l0-raw` - Raw Transkripte
- `memory://stale-memory` - Archiv-Zugriff

### Datenfluss

Typische Query-Verarbeitung:
1. **User Query** (in Claude Code)
2. **Query Expansion** → 3 Varianten (intern, €0)
3. **OpenAI Embeddings API** → 4 Embeddings (€0.00008)
4. **MCP Tool: hybrid_search** (4x parallel)
5. **PostgreSQL**: Semantic + Keyword Search, RRF Fusion → Top-5 Docs
6. **MCP Resource: memory://episode-memory** (ähnliche vergangene Queries)
7. **CoT Generation** (intern, €0)
8. **MCP Tool: store_episode** (Reflexion via Haiku API, €0.004)
9. **Antwort** an User

## Key Features

### L0/L2 Memory Storage
- **L0 Raw Memory**: Vollständige Dialogtranskripte mit Metadaten
- **L2 Insights**: Komprimierte, semantisch angereicherte Erkenntnisse mit 1536-dimensionalen Embeddings
- **Automatische Kompression**: Intelligente Verdichtung von Dialogen zu retainable insights
- **Semantic Fidelity Check**: Qualitätssicherung bei der Kompression

### Hybrid Search (Semantic + Keyword + RRF)
- **Semantic Search**: pgvector mit OpenAI text-embedding-3-small (1536 dimensions)
- **Keyword Search**: Volltextsuche mit PostgreSQL tsvector
- **RRF Fusion**: Reciprocal Rank Fusion für optimal ranking mix
- **Performance**: <200ms durchschnittliche retrieval time

### Chain-of-Thought Generation
- **Interne Generierung**: Query Expansion und CoT in Claude Code (€0/mo)
- **Multi-Prompt Expansion**: 3 Varianten für robuste retrieval
- **Context Integration**: Working Memory und Episode Memory in Generierung
- **Deterministische Outputs**: Konsistente Antwortqualität

### Reflexion Framework (Verbal RL)
- **Episode Storage**: Automatische Speicherung von Query-Reward-Reflexion Triplets
- **Self-Evaluation**: Haiku API für consistente evaluation (€0.004/episode)
- **Learning Loop**: Kontinuierliche Verbesserung durch episode memory
- **Reward Tracking**: Quantitative Erfolgsmessung der Antworten

### Model Drift Detection
- **Golden Test Set**: 50-100 reference queries mit ground truth
- **Tägliche Validation**: Automatische Precision@5 Messung
- **Drift Alerts**: Benachrichtigung bei >5% Performance drop
- **Baseline Comparison**: 7-day rolling average für trend detection

### Budget Monitoring
- **Kosten-Tracking**: Detaillierte API-Kosten pro service
- **Budget Alerts**: Warnungen bei 80% (€8) und 100% (€10) des monatlichen Limits
- **Cost Optimization**: Staged Dual Judge für kostenreduktion (€2-3/mo vs €5-10/mo)
- **CLI Dashboard**: Interaktive cost analysis tools

## Budget & Performance Metrics

### Expected Monthly Costs

| Phase | OpenAI Embeddings | Anthropic Haiku | OpenAI GPT-4o | **Total** |
|-------|-------------------|-----------------|---------------|-----------|
| **Phase 1** (Full Dual Judge) | €0.60 | €1.50 | €1.20 | **€5-10/mo** |
| **Phase 2** (Staged Dual Judge) | €0.60 | €0.50 | €0.40 | **€2-3/mo** |

**Cost Breakdown (Phase 1):**
- OpenAI Embeddings: €0.06/mo (3M tokens @ €0.02/1M)
- Haiku Evaluation: €1.50/mo (375k tokens @ €4/1M)
- GPT-4o Dual Judge: €1.20/mo (240k tokens @ €5/1M)
- Claude Code (MAX Subscription): €0/mo (intern)

### Performance Targets

| Metrik | Target | Aktuell |
|--------|--------|---------|
| **End-to-End Latency** | <5s p95 | ~2-3s |
| **Hybrid Search Latency** | <200ms | ~140ms |
| **Precision@5** | >0.75 | 0.493 (baseline) |
| **System Uptime** | >99% | 99.2% (7-day test) |
| **API Success Rate** | >95% | 97.8% |

### Resource Requirements

**Minimum Hardware:**
- RAM: 2GB (PostgreSQL + MCP Server)
- CPU: 2 Cores (embedding generation + search)
- Storage: 10GB (PostgreSQL + logs + backups)
- Network: Stabile Internetverbindung für APIs

**Software Requirements:**
- Python 3.11+
- PostgreSQL 15+ mit pgvector
- Claude Code (MAX Subscription)
- Linux (Systemd für Production)

## Quick Start

### Installation
📖 **[Installation Guide](./installation-guide.md)** - Komplettes Setup von scratch

### Betrieb
📖 **[Operations Manual](./operations-manual.md)** - Daily operations und maintenance

### Fehlersuche
📖 **[Troubleshooting Guide](./troubleshooting.md)** - Common issues und solutions

### Backup & Recovery
📖 **[Backup & Recovery Guide](./backup-recovery.md)** - Disaster recovery procedures

### API Reference
📖 **[API Reference](./api-reference.md)** - MCP Tools & Resources documentation

### Production Checklist
📖 **[Production Checklist](./production-checklist.md)** - Deployment validation

### Budget Monitoring
📖 **[Budget Monitoring Guide](./budget-monitoring.md)** - Cost tracking tools

### Stability Testing
📖 **[7-Day Stability Report](./7-day-stability-report-template.md)** - System validation results

---

## Project Status

**Epic 1:** ✅ Complete (MCP Server + Memory Storage + Search)
**Epic 2:** ✅ Complete (Evaluation Framework + Reflexion)
**Epic 3:** ✅ Complete (Production Readiness + Monitoring + Documentation)

**Next Steps:** System ist production-ready für langfristigen selbstständigen Betrieb.
