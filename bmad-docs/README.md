# cognitive-memory - BMAD Project Documentation

Diese Dokumentation enthält alle **Planungs- und Projektmanagement-Dokumente** für das Cognitive Memory System. Für Betriebs- und Entwickler-Dokumentation siehe `/docs/`.

## Zweck

`bmad-docs/` enthält:
- **PRD & Requirements** - Was soll gebaut werden
- **Architecture & Specs** - Wie soll es gebaut werden
- **Epics & Stories** - Wann und in welcher Reihenfolge
- **Results & Testing** - Evaluations- und Kalibrierungsergebnisse

## Dokumenten-Hierarchie

```
bmad-docs/
├── PRD.md                           # Product Requirements Document
├── architecture.md                  # Technische Architektur
├── ecosystem-architecture.md        # Position im Ecosystem
├── epics.md                         # Epic-Breakdown (33 Stories)
├── requirements-cognitive-memory-graphrag.md  # GraphRAG Erweiterung
├── research-graphrag-2025-11-26.md  # GraphRAG Research
│
├── specs/                           # Technische Spezifikationen
│   ├── tech-spec-epic-1.md
│   ├── tech-spec-epic-2.md
│   └── tech-spec-epic-3.md
│
├── stories/                         # 33 Story-Dokumente
│   └── {epic}-{story}-{titel}.md
│
├── planning/                        # Planung
│   └── use-cases.md
│
├── results/                         # Evaluations-Ergebnisse
│   ├── calibration-results.md
│   ├── evaluation-results.md
│   └── evaluation-results.mock.md
│
├── guides/                          # Implementation Guides
│   ├── production-deployment-story-2.9.md
│   └── story-3.1-golden-test-set.md
│
└── testing/                         # Testing-Dokumentation
    ├── testing-story-2.7-infrastructure-blocker.md
    └── testing-story-2.7-local-testing-guide.md
```

## Kern-Dokumente

| Dokument | Beschreibung |
|----------|--------------|
| [PRD.md](./PRD.md) | Product Requirements - Ziele, FRs/NFRs, Budget |
| [architecture.md](./architecture.md) | Technische Architektur, DB-Schema, API-Integration |
| [ecosystem-architecture.md](./ecosystem-architecture.md) | Position im 4-Schichten-Ecosystem |
| [epics.md](./epics.md) | Alle 33 Stories mit Dependencies |

## Ecosystem-Position

cognitive-memory ist **Layer 2 (Storage Layer)** im Ecosystem:

```
Layer 4: Applications (tethr, agentic-business)
Layer 3: Ethical Framework (i-o-system)
Layer 2: Storage Layer (cognitive-memory) ← Dieses Projekt
```

Für Details siehe [ecosystem-architecture.md](./ecosystem-architecture.md).

## Verbindung zum i-o-system (Python-Repo)

Das i-o-system nutzt cognitive-memory als Storage-Backend über einen Adapter:

```python
# Geplante Struktur in i-o-system
from io_system.adapters.cognitive import CognitiveMemoryAdapter

adapter = CognitiveMemoryAdapter()
await adapter.store(content, consent_level=ConsentLevel.EXPLICIT)
await adapter.search(query, filters={"consent_level": "explicit"})
```

**Repository:** `https://github.com/ethrdev/i-o-system` (in Entwicklung)

## Projekt-Status

| Epic | Stories | Status |
|------|---------|--------|
| Epic 1: MCP Server Foundation | 12 | ✅ Abgeschlossen |
| Epic 2: RAG Pipeline | 9 | ✅ Abgeschlossen |
| Epic 3: Production Readiness | 12 | ✅ Abgeschlossen |

**Gesamt:** ~95% fertig, produktionsreif

## Verwandte Dokumentation

| Ordner | Inhalt |
|--------|--------|
| `/docs/` | Betriebs- und Entwickler-Docs (Installation, Guides, Troubleshooting) |
| `/bmad-docs/` | Projekt-Planung (PRD, Architecture, Epics) ← Hier |

---

**Version:** 3.1.0-Hybrid  
**Letzte Aktualisierung:** 2025-11-26
