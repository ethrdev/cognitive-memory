# Finale Epic-Zusammenfassung

## Gesamtübersicht

**Total:** 49 Stories über 5 Epics
**Geschätzte Timeline:** 190-253 Stunden (3.5-5 Monate bei 20h/Woche)
**Budget-Ziel:** €5-10/mo Production, dann €2-3/mo (nach Staged Dual Judge)

| Epic | Stories | Timeline | Budget | Critical Success |
|------|---------|----------|--------|------------------|
| **Epic 1:** MCP Server Foundation & Ground Truth | 12 | 38-50h | €0.23 (einmalig) | IRR Kappa >0.70, 50-100 Queries Ground Truth |
| **Epic 2:** RAG Pipeline & Hybrid Calibration | 9 | 35-45h | €1-2/mo | Precision@5 >0.75, <5s Latency |
| **Epic 3:** Production Readiness | 12 | 60-80h | €5-10/mo | 7-Day Stability, Model Drift Detection |
| **Epic 4:** GraphRAG Integration | 8 | 30-40h | €0/mo | Graph-Tools funktional, Hybrid Search 60/20/20 |
| **Epic 5:** Library API for Ecosystem | 8 | 27-38h | €0/mo | `from cognitive_memory import MemoryStore` funktioniert |

## Implementation Path

**Epic 1** legt das doppelte Fundament:

- **Technisch:** Python MCP Server, PostgreSQL + pgvector, 7 Tools + 5 Resources
- **Methodisch:** Ground Truth Collection mit echten unabhängigen Dual Judges (GPT-4o + Haiku)
- **Critical Path:** Alle nachfolgenden Phasen hängen von Epic 1 ab

**Epic 2** implementiert die Kern-Innovation:

- **Strategische API-Nutzung:** Bulk-Ops (€0/mo) intern, kritische Evals (€1-2/mo) extern
- **Hybrid Calibration:** Grid Search für domänenspezifische Gewichte (+5-10% Precision Uplift)
- **Verbal RL:** Reflexion-Framework für konsistente Episode Memory Quality

**Epic 3** bringt Production Readiness:

- **Monitoring:** Golden Test Set (täglich), Model Drift Detection, API Retry-Logic
- **Budget-Optimierung:** Staged Dual Judge reduziert Kosten -40% nach 3 Monaten
- **Operational Excellence:** Backups, Daemonization, 7-Day Stability Testing

**Epic 4** erweitert um GraphRAG (v3.2):

- **Graph-Speicherung:** PostgreSQL Adjacency List (nodes + edges Tabellen)
- **4 neue MCP Tools:** graph_add_node, graph_add_edge, graph_query_neighbors, graph_find_path
- **Hybrid Search Erweiterung:** 60% Semantic + 20% Keyword + 20% Graph (RRF Fusion)
- **Use Cases:** Architecture Checks, Risk Analysis, Knowledge Harvesting für BMAD-BMM Agenten

**Epic 5** ermöglicht Ecosystem Integration:

- **Library API:** Python Package `cognitive_memory` für direkten programmatischen Zugriff
- **Dual Interface:** MCP für externe Clients, Library für interne Python-Integration
- **Code-Wiederverwendung:** Nutzt bestehende MCP Server Logik, keine Duplizierung
- **Use Cases:** i-o-system, tethr, agentic-business können cognitive-memory als Storage nutzen

## Sequenzierung & Dependencies

```
Epic 1 (Foundation)
  ↓
Epic 2 (RAG Pipeline)
  ├─ benötigt: Ground Truth Set (aus Epic 1)
  └─ liefert: Kalibriertes Hybrid Search System
      ↓
      ├───────────────────────────────┐
      ↓                               ↓
Epic 3 (Production)            Epic 4 (GraphRAG)
  ├─ benötigt: System aus Epic 2    ├─ benötigt: PostgreSQL (Epic 1.2) ✅
  └─ liefert: Production Deployment └─ liefert: Graph-Tools + Hybrid 60/20/20
                                      ↓
                             (Kann parallel zu Epic 3 laufen)
                                      ↓
                              Epic 5 (Library API)
                                ├─ benötigt: Epic 4 (GraphRAG) ✅
                                ├─ benötigt: Story 1.6 (hybrid_search) ✅
                                └─ liefert: Python Package für Ecosystem
```

**Parallelisierung möglich:** Epic 3 und Epic 4 können parallel laufen (erwünscht).
**Dependencies:** Epic 4 benötigt nur Story 1.2 (PostgreSQL) + Story 1.6 (hybrid_search).
**Dependencies:** Epic 5 benötigt Epic 4 (GraphRAG) für Graph-Funktionen.
**Innerhalb Epics:** Stories sind sequenziell geordnet (keine forward dependencies).

## Success Criteria

**Phase 1 (Epic 1):**

- ✅ MCP Server läuft, Claude Code verbindet
- ✅ Cohen's Kappa >0.70 (true independence: GPT-4o + Haiku)
- ✅ 50-100 Queries Ground Truth gelabelt

**Phase 2 (Epic 2):**

- ✅ Precision@5 ≥0.75 (Full Success) ODER 0.70-0.74 (Partial Success mit Monitoring)
- ✅ End-to-End Latency <5s (p95)
- ✅ Haiku API Evaluation funktioniert (Reward -1.0 bis +1.0)

**Phase 3-5 (Epic 3):**

- ✅ 7-Day Stability (kein Crash, >99% Query Success Rate)
- ✅ Budget <€10/mo (first 3 months), dann <€3/mo (after Staged Dual Judge)
- ✅ Model Drift Detection läuft täglich (Golden Test Set)

**Phase 6 (Epic 4 - GraphRAG):**

- ✅ 4 Graph-Tools funktional (add_node, add_edge, query_neighbors, find_path)
- ✅ Hybrid Search erweitert auf 60/20/20 (Semantic/Keyword/Graph)
- ✅ Performance: graph_query_neighbors <50ms (depth=1), <200ms (depth=5)
- ✅ BMAD-BMM Use Cases validiert (Architecture Check, Risk Analysis, Knowledge Harvesting)

**Phase 7 (Epic 5 - Library API):**

- ✅ `from cognitive_memory import MemoryStore` funktioniert
- ✅ `store.search()` liefert korrekte Hybrid Search Ergebnisse
- ✅ `store.store_insight()` speichert mit Embedding + Fidelity Check
- ✅ `store.working.add()` mit LRU Eviction funktioniert
- ✅ `store.episode.store()` speichert Episodes korrekt
- ✅ `store.graph.query_neighbors()` für Graph-Traversierung funktioniert
- ✅ i-o-system `CognitiveMemoryAdapter` kann Library nutzen
- ✅ Documentation + Examples existieren

## Risk Mitigation

Alle kritischen Risks aus PRD sind adressiert:

- **Risk 1 (MCP Complexity):** Story 2.1 = Integration Testing + MCP Inspector
- **Risk 2 (Context Window):** Top-5 statt Top-10, Adaptive Truncation
- **Risk 3 (API Dependencies):** Story 3.3-3.4 = Retry-Logic + Claude Code Fallback
- **Risk 4 (Cost Variability):** Story 3.10 = Budget Monitoring + Alerts
- **Risk 5 (IRR Failure):** Story 1.12 = Contingency Plan (Human Tiebreaker, Wilcoxon Test)
- **Risk 6 (PostgreSQL Performance):** Story 1.2 = IVFFlat Index, Story 3.5 = Latency Benchmarking

## Out of Scope (v3.2.0-GraphRAG)

**Explizit NICHT in diesem Epic Breakdown:**

- ~~Neo4j Knowledge Graph Integration~~ → **IN SCOPE als PostgreSQL Adjacency List (Epic 4)**
- Multi-User Support (nur ethr)
- Cloud Deployment (nur lokal)
- Voice Interface (nur Text)
- Advanced Agentic Workflows (v2.5)
- Fine-Tuning (System nutzt Verbal RL)
- Automatische Entity Extraction (Graph-Nodes werden manuell via MCP Tools erstellt)

## Next Steps

Nach Epic-Breakdown Approval:

1. **Review mit ethr:** Validiere Epic-Struktur, Story-Sizing, Dependencies
2. **Transition zu Architecture:** Detaillierte Technical Spec für Epic 1 (wenn gewünscht)
3. **Begin Implementation:** Start mit Story 1.1 (Projekt-Setup)

---

_Für Implementation: Nutze den `create-story` Workflow um individuelle Story Implementation Plans aus diesem Epic Breakdown zu generieren._
