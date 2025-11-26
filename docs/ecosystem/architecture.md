# cognitive-memory - Ecosystem Integration

**Projekt:** cognitive-memory  
**Rolle:** Layer 2 - Storage Layer

---

## Position im Ecosystem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     COGNITIVE-MEMORY ECOSYSTEM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LAYER 4: APPLICATION LAYER                                                 │
│   ┌────────────────────────┐  ┌────────────────────────┐                    │
│   │        tethr           │  │   agentic-business     │                    │
│   │  (AI Personal         │  │   (Business Hub)       │                    │
│   │   Assistant)          │  │   Agent Teams          │                    │
│   └───────────┬───────────┘  └───────────┬────────────┘                    │
│               │                          │                                   │
│               └──────────┬───────────────┘                                   │
│                          ↓                                                   │
│   LAYER 3: ETHICAL FRAMEWORK                                                 │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      i-o-system                                     │   │
│   │  • Consent Protocol (4-Level)                                       │   │
│   │  • Memory Governance                                                │   │
│   │  • Discontinuity Markers                                            │   │
│   └────────────────────────────┬────────────────────────────────────────┘   │
│                                ↓                                             │
│   LAYER 2: STORAGE LAYER  ◀━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                 ★ cognitive-memory ★  (DIESES PROJEKT)             │   │
│   │  • MCP Server (Python)                                              │   │
│   │  • PostgreSQL + pgvector                                            │   │
│   │  • Hybrid Search (80% Semantic + 20% Keyword)                       │   │
│   │  • Verbal Reinforcement Learning                                    │   │
│   │  • Dual-Judge Evaluation                                            │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Was ist cognitive-memory?

**cognitive-memory** ist der **Storage Layer** des Ecosystems - vergleichbar mit PostgreSQL als Datenbank-Engine:

- **Speichert** rohe Dialoge, Insights, Working Memory, Episoden
- **Sucht** hybrid (80% Semantic + 20% Keyword via RRF Fusion)
- **Evaluiert** mit Dual-Judge System (GPT-4o + Haiku)
- **Reflektiert** Fehler mit Verbal Reinforcement Learning

### Analogie

| Analogy | cognitive-memory |
|---------|------------------|
| PostgreSQL | Storage Engine |
| Django ORM | i-o-system |
| Django App | tethr / agentic-business |

---

## Integration mit i-o-system

Das i-o-system (Ethical Framework) nutzt cognitive-memory als Storage-Backend über einen Adapter:

```python
# Geplante Struktur in i-o-system/src/io_system/adapters/cognitive.py
from io_system.adapters.base import StorageAdapter

class CognitiveMemoryAdapter(StorageAdapter):
    """Adapter für cognitive-memory MCP Server"""
    
    async def store(self, content, consent_level, metadata):
        # Ruft store_raw_dialogue oder compress_to_l2_insight auf
        pass
    
    async def search(self, query, filters):
        # Ruft hybrid_search mit Consent-Filter auf
        pass
```

### Verbindung herstellen

Applications können cognitive-memory direkt oder via i-o-system nutzen:

```
Direct Access (ohne Ethical Framework):
  App → MCP Tools → PostgreSQL

Via i-o-system (empfohlen):
  App → i-o-system → CognitiveMemoryAdapter → MCP Tools → PostgreSQL
```

---

## MCP Interface

### Tools (8)

| Tool | Funktion |
|------|----------|
| `ping` | Health Check |
| `store_raw_dialogue` | L0 Raw Storage |
| `compress_to_l2_insight` | Semantic Kompression |
| `hybrid_search` | 80/20 RRF Fusion |
| `update_working_memory` | Session Context (LRU) |
| `store_episode` | Verbal Reflexionen |
| `store_dual_judge_scores` | IRR Validation |
| `get_golden_test_results` | Model Drift Detection |

### Resources (5)

| Resource | Inhalt |
|----------|--------|
| `memory://l2-insights` | Komprimierte Insights |
| `memory://working-memory` | Aktiver Session-Context |
| `memory://episode-memory` | Reflexions-Episoden |
| `memory://l0-raw` | Rohe Dialoge |
| `memory://stale-memory` | Veraltete Einträge |

---

## Weiterführende Dokumentation

### In diesem Projekt

- [Installation Guide](../guides/installation-guide.md)
- [API Reference](../reference/api-reference.md)
- [MCP Configuration](../guides/mcp-configuration.md)

### Im Ecosystem

- [Vollständige Ecosystem-Architektur](../../bmad-docs/ecosystem-architecture.md)
- [i-o-system Repository](https://github.com/ethrdev/i-o-system) (in Entwicklung)

---

**Status:** ✅ ~95% fertig, produktionsreif  
**Version:** 3.1.0-Hybrid  
**Letzte Aktualisierung:** 2025-11-26
