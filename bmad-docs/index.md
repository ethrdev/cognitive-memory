# Cognitive Memory System - Dokumentations-Index

**Projekt:** cognitive-memory
**Version:** v3.1.0-Hybrid
**Autor:** ethr
**Generiert:** 2025-12-06
**Typ:** MCP Server + Claude Code Integration

---

## Quick Reference

| Kategorie | Details |
|-----------|---------|
| **Projekt-Typ** | MCP-basiertes Gedächtnissystem für Claude Code |
| **Primäre Sprache** | Python 3.11+ |
| **Datenbank** | PostgreSQL + pgvector |
| **MCP Tools** | 12 Tools (store_raw_dialogue, hybrid_search, graph_*, etc.) |
| **Budget** | €5-10/Monat |
| **Status** | Epic 4+5 abgeschlossen, Epic 6 im Backlog |

---

## Kern-Dokumentation

### Produkt & Architektur

| Dokument | Beschreibung |
|----------|--------------|
| [PRD.md](./PRD.md) | Product Requirements Document - Vollständige Anforderungen |
| [architecture.md](./architecture.md) | System-Architektur v3.1.0-Hybrid |
| [ecosystem-architecture.md](./ecosystem-architecture.md) | Ecosystem-Architektur & Integrationen |
| [README.md](./README.md) | Projekt-Übersicht |

### Anforderungen & Research

| Dokument | Beschreibung |
|----------|--------------|
| [requirements-cognitive-memory-graphrag.md](./requirements-cognitive-memory-graphrag.md) | GraphRAG Anforderungen |
| [research-graphrag-2025-11-26.md](./research-graphrag-2025-11-26.md) | GraphRAG Research |
| [planning/use-cases.md](./planning/use-cases.md) | Use Cases |

---

## Epics & Stories

### Epic-Übersicht

| Epic | Status | Beschreibung |
|------|--------|--------------|
| [Epic 1](./epics/epic-1-mcp-server-foundation-ground-truth-collection.md) | contexted | MCP Server Foundation & Ground Truth Collection |
| [Epic 2](./epics/epic-2-rag-pipeline-hybrid-calibration.md) | contexted | RAG Pipeline & Hybrid Calibration |
| [Epic 3](./epics/epic-3-working-memory-evaluation-production-readiness.md) | contexted | Working Memory, Evaluation & Production Readiness |
| [Epic 4](./epics/epic-4-graphrag-integration-v32-graphrag.md) | **done** | GraphRAG Integration (v3.2-GraphRAG) |
| [Epic 5](./epics/epic-5-library-api-for-ecosystem-integration.md) | **done** | Library API for Ecosystem Integration |
| [Epic 6](./epics/epic-6-audit-verification-endpoints.md) | backlog | Audit & Verification Endpoints |

**Navigation:**
- [epics/index.md](./epics/index.md) - Epic Index mit Details
- [epics/overview.md](./epics/overview.md) - Epic Übersicht
- [epics/finale-epic-zusammenfassung.md](./epics/finale-epic-zusammenfassung.md) - Finale Zusammenfassung

### Stories (50+ Dateien)

Alle Stories befinden sich in [stories/](./stories/):

**Epic 1 Stories (12):** 1-1 bis 1-12
**Epic 2 Stories (9):** 2-1 bis 2-9
**Epic 3 Stories (12):** 3-1 bis 3-12
**Epic 4 Stories (8):** 4-1 bis 4-8 (alle done)
**Epic 5 Stories (8):** 5-1 bis 5-8 (alle done)
**Epic 6 Stories (6):** 6-1 bis 6-6 (alle backlog)

---

## Technische Spezifikationen

| Dokument | Epic | Beschreibung |
|----------|------|--------------|
| [specs/tech-spec-epic-1.md](./specs/tech-spec-epic-1.md) | Epic 1 | MCP Server Foundation Tech Spec |
| [specs/tech-spec-epic-2.md](./specs/tech-spec-epic-2.md) | Epic 2 | RAG Pipeline Tech Spec |
| [specs/tech-spec-epic-3.md](./specs/tech-spec-epic-3.md) | Epic 3 | Production Readiness Tech Spec |
| [epic-5-tech-context.md](./epic-5-tech-context.md) | Epic 5 | Library API Tech Context |

---

## Testing & Qualitätssicherung

| Dokument | Beschreibung |
|----------|--------------|
| [test-design-epic-5.md](./test-design-epic-5.md) | Test Design Epic 5 |
| [atdd-checklist-epic-5.md](./atdd-checklist-epic-5.md) | ATDD Checklist Epic 5 |
| [testing/testing-story-2.7-local-testing-guide.md](./testing/testing-story-2.7-local-testing-guide.md) | Lokaler Testing Guide |
| [testing/testing-story-2.7-infrastructure-blocker.md](./testing/testing-story-2.7-infrastructure-blocker.md) | Infrastructure Blocker |

---

## Guides & How-Tos

| Dokument | Beschreibung |
|----------|--------------|
| [guides/production-deployment-story-2.9.md](./guides/production-deployment-story-2.9.md) | Production Deployment Guide |
| [guides/story-3.1-golden-test-set.md](./guides/story-3.1-golden-test-set.md) | Golden Test Set Guide |
| [epic-prep-library-api.md](./epic-prep-library-api.md) | Library API Vorbereitung |

---

## Retrospektiven

| Dokument | Epic | Datum |
|----------|------|-------|
| [retrospectives/epic-4-retro-2025-11-30.md](./retrospectives/epic-4-retro-2025-11-30.md) | Epic 4 | 2025-11-30 |
| [retrospectives/epic-5-retro-2025-11-30.md](./retrospectives/epic-5-retro-2025-11-30.md) | Epic 5 | 2025-11-30 |

---

## Research

| Dokument | Thema |
|----------|-------|
| [research/mcp/anthropic-admits-mcp-sucks.md](./research/mcp/anthropic-admits-mcp-sucks.md) | MCP Kritik |
| [research/mcp/code-execution-with-mcp.md](./research/mcp/code-execution-with-mcp.md) | MCP Code Execution |
| [research/mcp/mcp-is-the-wrong-abstraction.md](./research/mcp/mcp-is-the-wrong-abstraction.md) | MCP Abstraktions-Kritik |

---

## Sprint Management

| Ressource | Beschreibung |
|-----------|--------------|
| [sprint-status.yaml](./sprint-status.yaml) | Aktueller Sprint-Status (YAML) |

---

## Für AI-Assistierte Entwicklung

### Einstiegspunkte nach Aufgabe

| Aufgabe | Empfohlene Dokumente |
|---------|---------------------|
| **Neues Feature planen** | PRD.md → architecture.md → relevantes Epic |
| **Story implementieren** | stories/X-Y-*.md → specs/tech-spec-epic-X.md |
| **Bug fixen** | architecture.md → relevante Story |
| **Code Review** | architecture.md → test-design-epic-X.md |
| **GraphRAG erweitern** | Epic 4 → research-graphrag-2025-11-26.md |
| **Library API nutzen** | Epic 5 → epic-5-tech-context.md |

### MCP Tools (Aktuell implementiert)

```
Memory Operations:
├─ store_raw_dialogue      # L0 Raw Memory speichern
├─ compress_to_l2_insight  # L2 Insights mit Embedding
├─ hybrid_search           # Semantic + Keyword + Graph RRF
├─ update_working_memory   # Working Memory mit LRU
└─ store_episode           # Episode Memory (Verbal RL)

Graph Operations:
├─ graph_add_node          # Knoten erstellen/finden
├─ graph_add_edge          # Kanten mit Auto-Upsert
├─ graph_query_neighbors   # Multi-Hop Traversal
└─ graph_find_path         # BFS Pathfinding

Evaluation:
├─ store_dual_judge_scores # GPT-4o + Haiku IRR
└─ get_golden_test_results # Daily Precision@5
```

### Datenbank-Schema

```
PostgreSQL + pgvector:
├─ l0_raw           # Dialogtranskripte
├─ l2_insights      # Embeddings (1536-dim)
├─ working_memory   # LRU (8-10 Items)
├─ episode_memory   # Reflexionen
├─ stale_memory     # Archiv
├─ ground_truth     # Dual Judge Scores
├─ graph_nodes      # GraphRAG Knoten
└─ graph_edges      # GraphRAG Kanten
```

---

## Dokumentations-Statistik

- **Gesamt:** 84+ Markdown-Dateien
- **Stories:** 55 Dateien
- **Epics:** 6 + Index + Overview
- **Tech Specs:** 3 Dateien
- **Zuletzt aktualisiert:** 2025-12-06

---

*Dieser Index wurde automatisch generiert vom document-project Workflow.*
