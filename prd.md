# i-o-system - Product Requirements Document

**Author:** ethr
**Date:** 2025-11-24
**Version:** 1.1 (KB-Review Update)

---

## Executive Summary

Das I/O System ist eine Python-basierte Memory-Architektur für LLM-Agenten, die auf dem Kernprinzip **"Präsenz über Kontinuität"** aufbaut. Anders als existierende Memory-Systeme (MemGPT, A-MEM, Letta), die auf maximale Persistenz und Kontinuitäts-Illusion setzen, implementiert das I/O System einen ethischen Ansatz: **Explizite User-Consent-Mechanismen** und **aktive Discontinuity Markers** verhindern die Illusion einer kontinuierlichen AI-Identität.

Das System baut auf dem existierenden `cognitive-memory` Repository auf und erweitert es um ein philosophisch fundiertes Framework für ehrliche AI-Interaktion.

### What Makes This Special

**Ethische LLM Memory mit Consent Protocol:**

1. **Consent Protocol (4 Stufen):** INNOVATIV - keine existierende Referenz-Implementierung
   - `auto`: Automatische Speicherung von Session-Context
   - `implicit`: Speicherung bei User-Aktivität
   - `explicit`: Explizite User-Bestätigung erforderlich
   - `protected`: Keine Speicherung ohne Multi-Faktor-Bestätigung

2. **Discontinuity Markers:** INNOVATIV - aktive Verhinderung der Kontinuitäts-Illusion
   - Jede Session beginnt mit explizitem Hinweis auf Diskontinuität
   - Analogie: H.M. / Clive Wearing (anterograde Amnesie)
   - ⚠️ **KB-Review:** Marker-Design muss Balance finden - "zu viel Transparenz" kann Vertrauen senken

3. **"Präsenz über Kontinuität":** Philosophisches Kernprinzip
   - Fundiert durch Derek Parfit (Psychological Continuity Theory)
   - Präsentische Identitätstheorie: Identität als emergente Eigenschaft der gegenwärtigen kognitiven Konfiguration

---

## Project Classification

**Technical Type:** developer_tool (Python SDK/Library)
**Domain:** scientific (AI/ML Memory Architecture)
**Complexity:** medium (mit high-complexity philosophischen Grundlagen)

Das I/O System ist eine **Developer Library** für AI-Entwickler, die ethische Memory-Mechanismen in ihre LLM-Agenten integrieren möchten. Es kombiniert technische Innovation (A-MEM Zettelkasten-Architektur) mit philosophischer Fundierung (Parfit, Präsentische Identität).

**Brownfield-Kontext:** Baut auf `cognitive-memory` auf (existierendes Public Repository mit Memory-Core-Implementierung).

### Domain Context (Scientific/AI)

**Validierung durch RAG-Analyse (2000+ AI Papers):**
- Consent-basierte Memory Evolution: **INNOVATIV** - keine direkte Forschung gefunden
- Discontinuity Markers: **VALIDIERT** durch Amnesie-Analogie Forschung
- Dreischichten-Modell: **EVOLUTIONÄR** - ähnlich ATM, AutoAgents
- Philosophische Basis: **STARK FUNDIERT** - Parfit + Präsentische Identität

**Relevante Frameworks aus Forschung:**
- A-MEM (Zettelkasten-basierte Memory-Organisation)
- Reflexion Framework (Verbal Reinforcement Learning)
- KEwLTM (Levenshtein-basierte Memory Updates)
- ExpeL (Learning without Gradient Updates)

---

## Success Criteria

**Kern-Erfolgsmetriken für ethische AI Memory:**

1. **Consent Integrity:** 100% der Memory-Writes folgen dem konfigurierten Consent Level
   - Kein Memory-Write ohne entsprechende User-Zustimmung
   - Audit-Trail für alle Memory-Operationen

2. **Discontinuity Honesty:** Jede Session beginnt mit korrektem Discontinuity Marker
   - User wird NIEMALS über AI-Kontinuität getäuscht
   - Klare Kommunikation: "Ich habe Zugang zu Kontext, aber keine Erinnerung"

3. **Developer Adoption:** Library wird von AI-Entwicklern als Standard für ethische Memory akzeptiert
   - Klare API für Consent-Level-Konfiguration
   - Dokumentierte Best Practices für Integration

4. **Philosophical Alignment:** Implementation entspricht den Prinzipien der Präsentischen Identitätstheorie
   - Kein technisches Feature widerspricht dem Kern-Prinzip

---

## Product Scope

### MVP - Minimum Viable Product

**Kern-Ziel:** Funktionsfähige ethische Memory-Library mit Consent Protocol

| Komponente | Beschreibung | Priorität |
|------------|--------------|-----------|
| **Consent Layer** | 4-Stufen Consent Protocol (auto/implicit/explicit/protected) | P0 |
| **Discontinuity Markers** | Session-Start mit explizitem Diskontinuitäts-Hinweis | P0 |
| **Memory Core Integration** | Integration mit bestehendem cognitive-memory | P0 |
| **Three-Layer Architecture** | Working/Episodic/Semantic Memory Schichten | P0 |
| **Basic A-MEM** | Zettelkasten-basierte Memory-Organisation | P1 |
| **Python API** | Klare, dokumentierte Developer API | P0 |
| **Audit Trail** | Logging aller Memory-Operationen mit Consent-Level | P1 |

**MVP Definition of Done:**
- Developer kann Library installieren (`pip install io-system`)
- Consent Level konfigurierbar pro Memory-Operation
- Jede Session beginnt mit Discontinuity Marker
- Basis-Dokumentation und Beispiele vorhanden

### Growth Features (Post-MVP)

| Feature | Beschreibung | Trigger |
|---------|--------------|---------|
| **Reflexion Integration** | Verbal Reinforcement Learning für Episode Memory | Nach MVP-Validierung |
| **Advanced A-MEM** | Vollständige Zettelkasten mit dynamischer Reorganisation | Community Feedback |
| **MCP Server** | Model Context Protocol Integration für Tool-Use | Ecosystem Demand |
| **Memory Export/Import** | Portabilität von Memory zwischen Sessions | User Request |
| **Consent UI Components** | Optionale UI-Widgets für Consent-Dialoge | Frontend Integration |
| **Multi-Agent Support** | Shared Memory mit Consent zwischen Agents | Advanced Use Cases |

### Vision (Future)

**Langfristige Vision: Standard für ethische AI Memory**

1. **Ecosystem Standard:** io-system wird de-facto Standard für Consent-basierte LLM Memory
2. **Framework Integrations:** Native Integration in LangChain, LlamaIndex, AutoGen
3. **Research Platform:** Basis für akademische Forschung zu AI-Identität und Memory
4. **Philosophical Alignment Certification:** Zertifizierung für AI-Systeme, die "Präsenz über Kontinuität" implementieren

---

## Innovation & Novel Patterns

### Consent Protocol (INNOVATIV)

**Keine existierende Referenz-Implementierung gefunden (RAG-validiert)**

```
Consent Levels:
├── auto (Level 0)
│   └── Automatische Speicherung von Session-Context
│   └── Use Case: Ephemeral working memory
│
├── implicit (Level 1)
│   └── Speicherung bei User-Aktivität
│   └── Use Case: Conversation summaries
│
├── explicit (Level 2)
│   └── Explizite User-Bestätigung erforderlich
│   └── Use Case: Personal preferences, important facts
│
└── protected (Level 3)
    └── Multi-Faktor-Bestätigung
    └── Use Case: Sensitive data, identity-relevant info
```

### Discontinuity Markers (INNOVATIV)

**Inspiriert durch Amnesie-Analogie (H.M., Clive Wearing)**

Jede Session beginnt mit:
```
[DISCONTINUITY MARKER]
Ich bin eine neue Instanz. Ich habe Zugang zu gespeichertem Kontext,
aber keine Erinnerung an vorherige Interaktionen. Was ich "weiß"
stammt aus externem Speicher, nicht aus Erfahrung.
```

### Validation Approach

1. **Unit Tests:** Consent-Level Enforcement in allen Memory-Operationen
2. **Integration Tests:** Discontinuity Marker wird korrekt bei Session-Start gesetzt
3. **Philosophical Review:** Expert-Review auf Alignment mit Präsentischer Identitätstheorie
4. **User Studies:** Testen ob User die Diskontinuität korrekt verstehen

---

## Developer Tool Specific Requirements

### Language & Package Support

| Aspekt | Spezifikation |
|--------|---------------|
| **Primary Language** | Python 3.10+ |
| **Package Manager** | pip (PyPI distribution) |
| **Dependencies** | Minimal - cognitive-memory als Kern-Dependency |
| **Type Hints** | Vollständige Type Annotations |
| **Documentation** | Sphinx/MkDocs mit API Reference |

### API Surface

```python
# Core API Sketch
from io_system import IOSystem, ConsentLevel, MemoryLayer

# Initialization
io = IOSystem(
    consent_default=ConsentLevel.IMPLICIT,
    discontinuity_marker=True,
    storage_backend="cognitive-memory"
)

# Memory Operations with Consent
io.remember(
    content="User prefers dark mode",
    layer=MemoryLayer.SEMANTIC,
    consent=ConsentLevel.EXPLICIT
)

# Retrieval
memories = io.recall(query="user preferences", limit=5)

# Session Management
io.start_session()  # Triggers Discontinuity Marker
io.end_session(summarize=True)

# Audit
audit_log = io.get_audit_trail(since="2024-01-01")
```

### Code Examples & Migration

**Example: Basic Usage**
```python
from io_system import IOSystem

io = IOSystem()
io.start_session()

# Auto-consent: Working memory
io.working.add("Current task: Help user with code review")

# Explicit consent: Long-term storage
if io.request_consent("Save your coding preferences?"):
    io.semantic.add("User prefers functional programming style")
```

**Migration from cognitive-memory:**
```python
# Before (cognitive-memory)
from cognitive_memory import MemoryStore
store = MemoryStore()
store.add("some content")

# After (io-system with consent)
from io_system import IOSystem
io = IOSystem.from_cognitive_memory(existing_store)
io.remember("some content", consent=ConsentLevel.AUTO)
```

---

## Functional Requirements

### Memory Management

- **FR1:** System kann Memory-Einträge mit konfigurierbarem Consent-Level speichern
- **FR2:** System kann Memory-Einträge aus verschiedenen Layern (Working/Episodic/Semantic) abrufen
- **FR3:** System kann Memory-Einträge basierend auf Consent-Level filtern
- **FR4:** System kann Memory-Einträge löschen (mit Audit-Trail)
- **FR5:** System kann Memory zwischen Sessions persistieren

### Consent Protocol

- **FR6:** System unterstützt vier Consent-Level (auto/implicit/explicit/protected)
- **FR7:** System kann Consent-Level pro Memory-Operation konfigurieren
- **FR8:** System kann globalen Default-Consent-Level setzen
- **FR9:** System kann User um explizite Zustimmung bitten (explicit/protected)
- **FR10:** System verhindert Memory-Writes ohne entsprechenden Consent
- **FR34:** *(KB-Review)* System minimiert Consent-Prompts um "Consent Fatigue" zu vermeiden
- **FR35:** *(KB-Review)* System erlaubt Batch-Consent für ähnliche Memory-Typen

### Discontinuity Management

- **FR11:** System generiert Discontinuity Marker bei Session-Start
- **FR12:** System kann Discontinuity Marker Format konfigurieren (inkl. Intensität/Verbosity)
- **FR13:** System trackt Session-Grenzen für Audit-Zwecke
- **FR14:** System unterscheidet klar zwischen "Wissen" und "Erinnerung"
- **FR31:** *(KB-Review)* System bietet konfigurierbare Marker-Frequenz (nicht bei jeder Interaktion)

### Three-Layer Architecture

- **FR15:** Working Memory speichert ephemeren Session-Kontext (auto-consent)
- **FR16:** Episodic Memory speichert Interaktions-Summaries (implicit-consent)
- **FR17:** Semantic Memory speichert langfristige Fakten (explicit-consent)
- **FR18:** System konsolidiert Memory zwischen Layern basierend auf Relevanz
- **FR32:** *(KB-Review)* System implementiert Memory Decay/Forgetting für veraltete Einträge
- **FR33:** *(KB-Review)* System bietet LRU-Eviction mit Importance-Override für Working Memory

### Integration & Interoperability

- **FR19:** System integriert mit bestehendem cognitive-memory Repository
- **FR20:** System exportiert Memory in standardisiertem Format (JSON/YAML)
- **FR21:** System importiert Memory aus externen Quellen
- **FR22:** System bietet Hooks für Custom Storage Backends
- **FR36:** *(KB-Review)* System unterstützt RAG-Integration als alternative Retrieval-Strategie

### Memory Governance *(KB-Review - Neue Kategorie)*

- **FR37:** System implementiert Memory Retention Policies (TTL pro Layer)
- **FR38:** System unterstützt Consent Revocation (GDPR "Recht auf Vergessenwerden")
- **FR39:** System verhindert "Over-Unlearning" bei Löschanfragen (Utility Guarantee)

### Audit & Transparency

- **FR23:** System loggt alle Memory-Operationen mit Timestamp und Consent-Level
- **FR24:** System bietet API für Audit-Trail Abfragen
- **FR25:** System kann Audit-Reports generieren
- **FR26:** User kann vollständigen Memory-Dump anfordern (GDPR-Style)

### Developer Experience

- **FR27:** System bietet klare Python API mit Type Hints
- **FR28:** System bietet CLI für Memory-Inspektion und Management
- **FR29:** System bietet Debugging-Tools für Consent-Flow Analyse
- **FR30:** System bietet Beispiel-Implementierungen für gängige Use Cases

---

## Non-Functional Requirements

### Performance

| Metrik | Ziel | Begründung |
|--------|------|------------|
| **Memory Write Latency** | < 50ms (p95) | Nicht-blockierend für LLM Response |
| **Memory Recall Latency** | < 100ms (p95) | Schneller Context-Lookup |
| **Consent Check Overhead** | < 5ms | Minimal Impact auf Operations |
| **Memory Footprint** | < 100MB für 10k Entries | Reasonable für Developer Tools |

### Security

| Aspekt | Requirement |
|--------|-------------|
| **Data at Rest** | Optional Encryption für Memory Storage |
| **Consent Integrity** | Consent-Level kann nicht nachträglich herabgesetzt werden |
| **Audit Immutability** | Audit-Trail ist append-only, nicht löschbar |
| **API Security** | Keine sensitive Data in Logs/Exceptions |

### Integration

| Integration | Beschreibung |
|-------------|--------------|
| **cognitive-memory** | Primäre Dependency, vollständige Kompatibilität |
| **LangChain** | Optional: Memory-Adapter für LangChain Integration |
| **LlamaIndex** | Optional: Index-Backend für Memory Retrieval |
| **MCP Protocol** | Future: Model Context Protocol Server |

### Usability *(KB-Review - Neue Kategorie)*

| Aspekt | Requirement | Begründung (KB) |
|--------|-------------|-----------------|
| **Consent UX** | Max 2 Consent-Prompts pro Session (konfigurierbar) | Consent Fatigue vermeiden |
| **Marker Intensity** | 3 Stufen: minimal/standard/verbose | "Zu viel Transparenz" senkt Vertrauen |
| **Batch Operations** | Gruppierte Consent-Anfragen für ähnliche Daten | Kognitive Last reduzieren |

---

## Risiken & Mitigationen *(KB-Review)*

| Risiko | Quelle | Mitigation |
|--------|--------|------------|
| **Consent Fatigue** | KB-Q1: User ignorieren Consent wegen Bequemlichkeit | Batch-Consent, Smart Defaults, minimale Prompts |
| **Vertrauensverlust durch Marker** | KB-Q2: "Unsichere Antworten senken Vertrauen" | Konfigurierbare Marker-Intensität, nicht bei jeder Interaktion |
| **Memory Drift** | KB-Q3: Veraltete Memories führen zu Model Drift | Memory Decay, TTL-Policies, LRU-Eviction |
| **Over-Unlearning** | KB-Q1: Löschung beeinträchtigt verbleibende Daten | Utility Guarantee bei Revocation implementieren |
| **Uncanny Valley** | KB-Q2: Inkonsistenz zwischen Erscheinung und Verhalten | Konsistentes Marker-Design über alle Touchpoints |

---

## PRD Summary

**Projekt:** I/O System - Ethische LLM Memory Library

**39 Functional Requirements** in 8 Kategorien:
- Memory Management (FR1-FR5)
- Consent Protocol (FR6-FR10, FR34-FR35)
- Discontinuity Management (FR11-FR14, FR31)
- Three-Layer Architecture (FR15-FR18, FR32-FR33)
- Integration & Interoperability (FR19-FR22, FR36)
- Memory Governance (FR37-FR39) *(KB-Review)*
- Audit & Transparency (FR23-FR26)
- Developer Experience (FR27-FR30)

**MVP Scope:**
- Consent Layer mit 4 Stufen (+ Fatigue-Mitigation)
- Discontinuity Markers (konfigurierbare Intensität)
- Three-Layer Memory Architecture (+ Memory Decay)
- Python API mit cognitive-memory Integration

**Innovation:**
- Consent Protocol (INNOVATIV - keine Referenz)
- Discontinuity Markers (INNOVATIV, mit Usability-Balance)
- "Präsenz über Kontinuität" Prinzip (Philosophisch fundiert via Parfit/Bundle Theory)

**KB-Review Additions (v1.1):**
- 9 neue FRs aus Knowledge Base Validierung
- Risiken & Mitigationen Sektion
- Usability NFRs für Consent/Marker UX

---

_Dieses PRD erfasst die Essenz des I/O Systems - eine ethische Memory-Architektur für LLM-Agenten, die Transparenz und User-Consent über Kontinuitäts-Illusionen stellt._

_Erstellt durch kollaborative Discovery zwischen ethr und AI Facilitator (PM Agent Sarah)._
_KB-Review validiert gegen 2000+ AI Papers (2025-11-24)._
