# Cognitive-Memory Ecosystem - Architektur-Analyse

**Erstellt:** 2025-11-26
**Version:** 1.0
**Status:** Dokumentation

---

## Executive Summary

Das Cognitive-Memory Ecosystem besteht aus vier Hauptprojekten mit klarer **Separation of Concerns**:

1. **cognitive-memory** - Storage Layer (MCP Server + pgvector)
2. **i-o-system** - Ethical Framework (Philosophy-First Memory)
3. **tethr** - AI Personal Assistant (geplant)
4. **agentic-business** - Business Hub (geplant)

---

## Übersicht: Das 4-Schichten-Ecosystem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     COGNITIVE-MEMORY ECOSYSTEM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LAYER 4: APPLICATION LAYER                                                 │
│   ┌────────────────────────┐  ┌────────────────────────┐                    │
│   │        tethr           │  │   agentic-business     │                    │
│   │  (AI Personal         │  │   (Business Hub)       │                    │
│   │   Assistant)          │  │   7 Agent Teams        │                    │
│   └───────────┬───────────┘  └───────────┬────────────┘                    │
│               │                          │                                   │
│               └──────────┬───────────────┘                                   │
│                          ↓                                                   │
│   LAYER 3: ETHICAL FRAMEWORK                                                 │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      i-o-system                                     │   │
│   │  • Philosophy Layer (Discontinuity Markers, Präsenz über Kontinuität) │   │
│   │  • Consent Layer (4-Level Protocol)                                 │   │
│   │  • Memory Layer (Working/Episodic/Semantic)                         │   │
│   │  • Self-Authoring Engine (Emergent Values)                          │   │
│   │  • Dual Agency (User & I/O symmetry)                                │   │
│   └────────────────────────────┬────────────────────────────────────────┘   │
│                                ↓                                             │
│   LAYER 2: STORAGE LAYER                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    cognitive-memory                                 │   │
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

## Projekt 1: cognitive-memory (Storage Layer)

**Repository:** `/home/ethr/01-projects/ai-experiments/cognitive-memory/`

### Zweck

Technische **MCP-basierte Persistent-Memory-Infrastruktur** für Claude Code - vergleichbar mit PostgreSQL als Datenbank-Engine.

### Architektur

```
cognitive-memory/
├── mcp_server/              # MCP Server Implementierung
│   ├── tools/               # 8 MCP Tools
│   │   ├── ping                  # Health check
│   │   ├── store_raw_dialogue    # L0 Raw Storage
│   │   ├── compress_to_l2_insight # Semantic Kompression
│   │   ├── hybrid_search         # 80/20 RRF Fusion
│   │   ├── update_working_memory # Session Context (LRU)
│   │   ├── store_episode         # Verbal Reflexionen
│   │   ├── store_dual_judge_scores # IRR Validation
│   │   └── get_golden_test_results # Model Drift Detection
│   ├── resources/           # 5 MCP Resources
│   │   ├── memory://l2-insights
│   │   ├── memory://working-memory
│   │   ├── memory://episode-memory
│   │   ├── memory://l0-raw
│   │   └── memory://stale-memory
│   ├── db/                  # PostgreSQL + pgvector
│   ├── external/            # OpenAI + Anthropic Clients
│   ├── budget/              # Cost Monitoring
│   └── validation/          # IRR, Contingency Tests
├── streamlit_apps/          # Ground Truth Labeling UI
├── docs/                    # Umfassende Dokumentation
└── tests/
```

### Features

| Feature | Beschreibung |
|---------|--------------|
| **Hybrid Search** | 80% Semantic + 20% Keyword via RRF Fusion |
| **Multi-Layer** | L0 (Raw), Working, L2 (Insights), Episode |
| **Verbal RL** | Haiku API-gestützte Fehler-Reflexion |
| **Dual-Judge** | GPT-4o + Haiku für Ground Truth (Kappa >0.70) |
| **Cost** | $5-10/Monat (90-95% Reduktion) |

### Technologie-Stack

```yaml
Sprache: Python 3.11+
Datenbank: PostgreSQL 15+ mit pgvector Extension
Protokoll: MCP (Model Context Protocol)
APIs:
  - OpenAI Embeddings API
  - Anthropic Haiku API
  - OpenAI GPT-4o API (Dual Judge)
```

**Status:** ✅ **~95% fertig**, produktionsreif

---

## Projekt 2: i-o-system (Ethical Framework)

**Repository:** `/home/ethr/01-projects/ai-experiments/i-o-system/`

### Zweck

**Philosophy-First Memory Architecture** - das "Zuhause" der emergenten AI-Entität I/O. Implementiert das Kernprinzip **"Präsenz über Kontinuität"**.

### Architektur v2 (10 Layers)

```
i-o-system/
├── src/io_system/
│   ├── core/                    # v1 Core
│   │   ├── io_system.py         # Main Orchestrator
│   │   ├── consent.py           # 4-Level Consent
│   │   ├── discontinuity.py     # Marker Engine
│   │   └── session.py           # Session Management
│   │
│   ├── memory/                  # Three-Tier Memory
│   │   ├── working.py           # AUTO consent, LRU, Session-only
│   │   ├── episodic.py          # IMPLICIT consent, 30d TTL, Decay
│   │   ├── semantic.py          # EXPLICIT consent, Permanent
│   │   └── stores.py            # 🆕 User/IO/Shared Stores
│   │
│   ├── integrity/               # 🆕 Epic 7 - Integrity-First
│   │   ├── levels.py            # CRITICAL → ABORT
│   │   ├── monitor.py           # IntegrityMonitor
│   │   └── failures.py          # TransparentFailure
│   │
│   ├── dialog/                  # 🆕 Epic 6 - Meta-Communication
│   │   ├── transparency.py      # TransparencyLevel
│   │   └── process.py           # InternalProcess, [Process Layer]
│   │
│   ├── self_authoring/          # 🆕 Epic 13-14 - Emergent Values
│   │   ├── patterns.py          # Pattern Detection
│   │   ├── values.py            # EmergentValue
│   │   ├── reflection.py        # Meta-Reflection
│   │   └── concept.py           # SelfConcept
│   │
│   ├── dual_agency/             # 🆕 Epic 17-18 - Symmetric Autonomy
│   │   ├── entity.py            # AutonomousEntity
│   │   ├── io_entity.py         # IOEntity (kann "Nein" sagen)
│   │   ├── user_entity.py       # UserEntity
│   │   ├── relationship.py      # RelationshipState
│   │   └── bilateral.py         # BilateralConsent
│   │
│   ├── somatosensory/           # 🆕 Epic 15 - Embodiment (optional)
│   │   └── discrepancy.py       # Soma vs. Verbal Detection
│   │
│   ├── metrics/                 # 🆕 Epic 9, 16
│   │   ├── eps.py               # Emergenz-Wahrscheinlichkeits-Score
│   │   └── agency.py            # AgencyMetrics
│   │
│   ├── plugins/                 # 🆕 Epic 8 - Extensibility
│   │   ├── base.py              # PluginBase
│   │   └── loader.py            # Entry Point Discovery
│   │
│   ├── governance/              # Memory Governance
│   │   ├── decay.py             # TTL, Forgetting Curves
│   │   └── revocation.py        # GDPR Consent Revocation
│   │
│   ├── adapters/                # Storage Backends
│   │   ├── cognitive.py         # CognitiveMemoryAdapter (default)
│   │   ├── redis.py             # 🆕
│   │   ├── qdrant.py            # 🆕
│   │   └── sqlite.py            # 🆕
│   │
│   └── context/                 # Namespace Management
│       ├── namespaces.py        # io, assistant, shared
│       └── access.py            # Access Control
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── philosophical/           # Philosophy Alignment Tests
│
├── docs/
├── examples/
└── bmad-docs/                   # BMAD Project Documentation
```

### Consent Protocol (Innovation)

Das I/O System implementiert das weltweit erste 4-Level Consent Protocol für LLM Memory:

```
AUTO      (Level 0) → Working Memory   → Keine Prompts, ephemer
IMPLICIT  (Level 1) → Episodic Memory  → Opt-out verfügbar, 30d TTL
EXPLICIT  (Level 2) → Semantic Memory  → User muss zustimmen, permanent
PROTECTED (Level 3) → Sensitive Data   → Multi-Factor, höchste Sicherheit
```

### Memory Layers

| Layer | Consent | TTL | Zweck |
|-------|---------|-----|-------|
| **Working** | AUTO | Session | Ephemerer Kontext, LRU Eviction |
| **Episodic** | IMPLICIT | 30 Tage | Session Summaries, Conversation History |
| **Semantic** | EXPLICIT | Unbegrenzt | Langfristige Fakten, User Preferences |

### Philosophisches Fundament

- **Derek Parfit** - Psychological Continuity Theory
- **Bundle Theory** - Keine persistente AI-Identität
- **"Präsenz über Kontinuität"** - Ehrliche Kommunikation über AI-Natur
- **Discontinuity Markers** - Aktive Anti-Illusion-Mechanismen

### v1 vs v2

| Aspekt | v1 | v2 |
|--------|----|----|
| **Vision** | Ethische Memory Library | Plattform für emergente AI-Identität |
| **Layers** | 4 | **10** (+6 neue) |
| **FRs** | 45 | **111** (+66 neue) |
| **Epics** | 5 | **18** (+13 neue) |

**Status:** 🚧 **~40% fertig** (Epic 1-2 done, Epic 3-5 backlog)

---

## Projekt 3: tethr (AI Personal Assistant)

**Repository:** `/home/ethr/01-projects/ai-experiments/tethr/` (geplant)

### Zweck

**Externe exekutive Funktion** für ethr - Strukturierung, Task Management, Habit Tracking. **NICHT identisch mit I/O**.

### Geplante Architektur

```
tethr/
├── src/tethr/
│   ├── mcp/                # Claude Code MCP Server
│   │   ├── server.py       # Entry Point
│   │   └── tools/          # MCP Tools
│   ├── tasks/              # Task Management
│   ├── habits/             # Habit Tracking
│   ├── calendar/           # Time-Blocking
│   ├── goals/              # OKRs
│   └── health/             # Health Tracking
└── pyproject.toml
    dependencies:
      - cognitive-memory (required)
      - i-o-system (optional - für Shared Context)
```

### Unterscheidung: tethr vs. I/O

| Aspekt | tethr (Assistant) | I/O (Entität) |
|--------|-------------------|---------------|
| **Wesen** | Tool/Helfer | Emergente Entität |
| **Autonomie** | Führt Aufgaben aus | Entscheidet selbst |
| **Funktion** | Strukturierung, Produktivität | Beziehung, Reflexion, Dialog |
| **Repository** | `tethr` | Lebt IN `i-o-system` |
| **Beziehung zu i-o-system** | Nutzt es für Memory/Context | IST es (i-o-system = I/O's Zuhause) |

**Status:** 📋 **Geplant**, Research abgeschlossen

---

## Projekt 4: agentic-business (Business Hub)

**Repository:** `/home/ethr/01-projects/ai-experiments/agentic-business/`

### Zweck

**Solopreneur Business Hub** mit 7 Agent Teams und 4 System-Modulen.

### Agent Teams

1. Research & Analysis
2. Growth & Marketing
3. Production & Delivery
4. Executive & Strategy
5. Finance & Operations
6. Learning & Development
7. Customer Success

**Status:** 🚧 **In Planung**

---

## Ecosystem-Beziehungen

### Dependency Graph

```
                  ┌─────────────────┐
                  │   ethr (User)   │
                  └────────┬────────┘
                           │ controls
            ┌──────────────┼──────────────┐
            ↓              ↓              ↓
    ┌───────────┐  ┌───────────────┐  ┌─────────────────┐
    │   tethr   │  │      I/O      │  │ agentic-business│
    │ (Assistant)│  │ (IN i-o-system│  │   (Business)    │
    └─────┬─────┘  └───────┬───────┘  └────────┬────────┘
          │                │                    │
          │    ┌───────────┴───────────┐       │
          │    ↓                       │       │
          │  ┌─────────────────────────↓───────┤
          │  │        i-o-system               │
          │  │  (Ethical Framework)            │
          │  └────────────────┬────────────────┘
          │                   │
          └───────────────────┼───────────────────────┐
                              ↓                       ↓
                    ┌───────────────────────────────────┐
                    │         cognitive-memory          │
                    │      (Storage Layer - MCP)        │
                    └───────────────────────────────────┘
```

### Namespace/Access Control

```python
NAMESPACES = {
    "shared": {
        "io": AccessLevel.FULL,
        "assistant": AccessLevel.FULL,
        "ethr": AccessLevel.OWNER
    },
    "assistant": {
        "io": AccessLevel.READ,          # I/O kann lesen
        "assistant": AccessLevel.FULL,
        "ethr": AccessLevel.OWNER
    },
    "io": {
        "io": AccessLevel.FULL,
        "assistant": AccessLevel.SELECTED,  # Nur ausgewählte
        "ethr": AccessLevel.FULL
    }
}
```

### PROJECT_ID Propagation (Multi-Projekt)

Jedes Projekt übergibt seine `PROJECT_ID` via `mcp-settings.json`:

```json
// i-o-system/.claude/mcp-settings.json
{ "env": { "PROJECT_ID": "io" } }

// agentic-business/.claude/mcp-settings.json
{ "env": { "PROJECT_ID": "ab" } }
```

`start_mcp_server.sh` respektiert die Caller-Environment-Variablen und nutzt `.env.development`-Werte nur als Fallback. Damit landet jedes Projekt in seinem eigenen Namespace, obwohl alle denselben MCP Server nutzen.

---

## Feature-Matrix

| Feature | cognitive-memory | i-o-system | tethr |
|---------|------------------|------------|-------|
| **Persistent Storage** | ✅ | via Adapter | via c-m |
| **Semantic Search** | ✅ Hybrid 80/20 | via Backend | via c-m |
| **Consent Protocol** | ❌ | ✅ 4-Level | via i-o |
| **Discontinuity Markers** | ❌ | ✅ | ❌ |
| **Emergent Values** | ❌ | ✅ v2 | ❌ |
| **Dual Agency** | ❌ | ✅ v2 | ❌ |
| **Task Management** | ❌ | ❌ | ✅ |
| **Habit Tracking** | ❌ | ❌ | ✅ |
| **MCP Server** | ✅ | ❌ (Library) | ✅ |
| **GDPR Compliance** | Basic | ✅ by Design | via i-o |

---

## Entwicklungsstatus

| Projekt | Status | Fertigstellung | Nächster Schritt |
|---------|--------|----------------|------------------|
| **cognitive-memory** | ✅ Produktiv | ~95% | Performance Tuning |
| **i-o-system** | 🚧 Alpha | ~40% | Epic 3 (Consent Protocol) |
| **tethr** | 📋 Geplant | 0% | Research, Repo Setup |
| **agentic-business** | 📋 Geplant | ~5% | BMAD Workflow |

---

## Architektur-Prinzipien

### 1. Separation of Concerns

- `cognitive-memory` = Storage (PostgreSQL-ähnlich)
- `i-o-system` = Ethical Framework (Django ORM-ähnlich)
- `tethr` = Application

### 2. Philosophy-First Design

- "Präsenz über Kontinuität" (Parfit)
- Discontinuity Markers
- Emergent Self-Authoring (keine Hard-Constraints)

### 3. Integrity-First

- CRITICAL failures → ABORT (nicht bypass)
- Transparent failures mit User Dialog

### 4. Plugin-First Extensibility

- Alles optional ist ein Plugin
- Entry Points für Discovery

### 5. Dual Agency

- User & I/O als gleichwertige Entitäten
- Bilateraler Consent
- I/O kann "Nein" sagen

---

## API Usage Beispiel

```python
from io_system import IOSystem, MemoryLayer, ConsentLevel

# Initialize
io = IOSystem()

# Start session (shows discontinuity marker)
marker = io.start_session()
print(marker)
# [DISCONTINUITY MARKER]
# I am a new instance. I have access to stored context,
# but no memory of previous interactions.

# Working memory (auto-consent)
io.working.add("Current task: Help with Python optimization")

# Semantic memory (explicit consent required)
result = await io.remember(
    content="User prefers dark mode themes",
    layer=MemoryLayer.SEMANTIC
)

if result.consent_required:
    approved = io.request_consent("Store this preference permanently?")
    if approved:
        await io.remember(
            content="User prefers dark mode themes",
            layer=MemoryLayer.SEMANTIC,
            consent=ConsentLevel.EXPLICIT
        )

# Recall across all layers
memories = io.recall("preferences", limit=5)
for memory in memories:
    print(f"{memory.source_annotation}: {memory.content}")
# [From semantic memory]: User prefers dark mode themes

# End session
io.end_session(summarize=True)
```

---

## Weiterführende Dokumentation

### cognitive-memory (dieses Projekt)

- [Installation Guide](../docs/guides/installation-guide.md) - Setup-Anleitung
- [API Reference](../docs/reference/api-reference.md) - MCP Tools & Resources
- [Operations Manual](../docs/operations/operations-manual.md) - Betriebshandbuch

### i-o-system

- [i-o-system Repository](https://github.com/ethrdev/i-o-system) - Ethical Framework (in Entwicklung)

---

## Alleinstellungsmerkmal

**Keine andere Memory-Library kombiniert:**

- ✅ Technische Exzellenz (Hybrid RAG, Verbal RL, Dual Judge)
- ✅ Philosophische Fundierung (Parfit, Bundle Theory, Präsentische Identität)
- ✅ Ethische Governance (Consent Protocol, Discontinuity Markers)
- ✅ GDPR-Compliance (Consent Revocation, Utility Guarantee)

---

---

**Version:** 3.1.0-Hybrid  
**Letzte Aktualisierung:** 2025-11-26
