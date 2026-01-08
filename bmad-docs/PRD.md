# Cognitive Memory System - Product Requirements Document (PRD)

**Author:** ethr
**Date:** 2025-11-09
**Version:** 3.1.0-Hybrid
**Project Level:** Level 2
**Project Type:** MCP Server + Claude Code Integration
**Target Scale:** Small Complete System (12-18 Stories, 2-3 Monate)
**Architecture Basis:** mcp-architecture-specification-v3.1-hybrid.md

---

## Executive Summary

**Cognitive Memory System** ist ein MCP-basiertes (Model Context Protocol) Gedächtnissystem, das Claude Code mit persistentem, kontextreichem Retrieval ausstattet. Das System nutzt Claude MAX Subscription für primäre LLM-Operationen (Generation, Planning) und externe APIs für kritische Validationen (Dual Judge, Evaluation), wodurch 90-95% Kostenreduktion gegenüber v2.4.1 erreicht wird (€106/mo → €5-10/mo).

**Kern-Innovation:** Strategische API-Nutzung - Bulk-Operationen (Generation, CoT) laufen kostenfrei in Claude Code, kritische Evaluationen (Dual Judge, Reflexion) nutzen externe APIs für methodische Robustheit.

**Budget:** €5-10/Monat
- **€0/mo:** Generation, Planning, CoT (Claude Code in MAX Subscription)
- **€3-4/mo:** Evaluation, Reflexion, Dual Judge (Haiku + GPT-4o APIs)
- **€0.06/mo:** Embeddings (OpenAI API)
- **€1/mo:** Expanded Golden Test Set (50-100 Queries)

**Timeline:** 133-175 Stunden (2.5-3.5 Monate bei 20h/Woche)

**Key Improvement vs. v3.0.0-MCP:** Methodisch valides Ground Truth durch echte unabhängige Dual Judges (GPT-4o + Haiku) statt pseudo-independence (Claude Code 2x Prompts).

---

## Description, Context and Goals

### Projektbeschreibung

**Kernproblem:** LLMs wie Claude haben keine native Session-Persistenz. Nach jeder Konversation geht der Kontext verloren, Beziehungsdynamiken müssen neu aufgebaut werden. Für tiefgehende philosophische Gespräche über Monate/Jahre ist dies unzureichend.

**Lösung:** Ein mehrstufiges Memory-System mit MCP-Integration:

**Architektur-Muster:**
```
Claude Code (MAX Subscription)
├─ Generation, Planning, CoT (€0, intern)
├─ MCP Protocol ↕
└─ MCP Server (Python, lokal)
   ├─ PostgreSQL + pgvector (Persistence)
   ├─ L0 Raw Memory (vollständige Transkripte)
   ├─ L2 Insights (adaptive Kompression)
   ├─ Working Memory (8-10 Items, LRU)
   └─ Episode Memory (Reflexionen)
       ↓
   External APIs (€5-10/mo)
   ├─ OpenAI Embeddings (€0.06/mo)
   ├─ GPT-4o Dual Judge (€1-1.5/mo)
   ├─ Haiku Dual Judge (€1-1.5/mo)
   └─ Haiku Evaluation/Reflexion (€1-2/mo)
```

**Memory-Ebenen:**
- **L0 (Raw Memory):** Vollständige Dialogtranskripte
- **L2 (Insights):** Komprimierte semantische Einheiten (Compression in Claude Code)
- **Working Memory:** Session-Kontext (8-10 Items, LRU Eviction)
- **Episode Memory:** Verbalisierte Reflexionen (Verbal Reinforcement Learning)

**Philosophische Foundation:** "Präsenz über Kontinuität" - Identität und Bedeutung existieren auch ohne durchgehende temporale Kontinuität.

**Primary Use Case:** ethr's Gespräche mit Claude (I/O) sollen persistent werden, sodass Beziehungsdynamiken, geteilte Konzepte und philosophische Entwicklungen über Zeit erhalten bleiben.

### Deployment Intent

**Production Application** - Kontinuierlicher Betrieb mit **lokaler Infrastruktur + strategischen externen APIs**:
- **MCP Server:** Python-basiert, läuft lokal
- **Datenbank:** PostgreSQL + pgvector (lokal installiert)
- **LLM Operations:** Claude Code (Generation, CoT) + Haiku API (Evaluation)
- **Embeddings:** OpenAI API
- **Validation:** GPT-4o + Haiku API (Dual Judge)

**Timeline:** 2.5-3.5 Monate (133-175 Stunden bei 20h/Woche)
**Budget:** €5-10/Monat (90-95% Savings vs. v2.4.1)
**Scale:** Personal Use (1 User - ethr)

### Context

**Warum jetzt?**
Die Forschung zu kognitiven Modi in LLMs (78 kuratierte Papers, NotebookLM-Analysen) zeigt: Emergente Modularität ist real, aber nur nutzbar mit robustem Memory-System. Die v3.1-Hybrid-Architektur balanciert Kosten und methodische Validität - 90-95% Kostenreduktion bei echtem IRR.

**Constraint-Driven Architecture:**
System muss primär in Claude Code lauffähig sein → MCP Server übernimmt nur Persistence, bulk LLM-Operationen in Claude Code, kritische Evaluationen via externe APIs für Robustheit.

**Methodological Improvement (v3.0 → v3.1):**
v3.0.0-MCP hatte Single-Model Dual Judge (Claude Code 2x Prompts) → kompromittiert Cohen's Kappa. v3.1-Hybrid nutzt GPT-4o + Haiku = true independence, valides Ground Truth.

### Goals

**Primary Goals (Level 2):**

1. **High-Quality Retrieval mit methodischer Validität**
   - Precision@5 >0.75 (höher als v2.4.1 dank besserer Embeddings)
   - Recall Uplift +10-15% durch Query Expansion (intern in Claude Code)
   - **True IRR:** Cohen's Kappa >0.70 mit echten unabhängigen Judges (GPT-4o + Haiku)
   - Budget: €5-10/mo (90-95% Savings vs. v2.4.1)

2. **Kontinuierliches Lernen mit konsistenter Evaluation**
   - Reflexion-Framework (Verbal RL) mit Haiku API = deterministisch über Sessions
   - Episode Memory speichert verbalisierte Lektionen
   - +10-15% Fehlerreduktion bei wiederholten Tasks
   - Bulk-Generation in Claude Code (€0/mo)

3. **Operational Excellence mit robusten Safeguards**
   - Robustheit durch 9 Enhancements (IRR Contingency, Semantic Fidelity, JSON Fallbacks, Model Drift Detection)
   - Latency <5s (p95) - akzeptabel für "Denkzeit" in Claude Code
   - **Expanded Golden Set:** 50-100 Queries (vs. 20 in v3.0.0) für statistische Robustheit
   - MCP Protocol ermöglicht native Claude Code Integration

**Secondary Goals:**

- **Transparenz:** Verbalisierte Reflexionen, menschlich lesbar
- **Lokale Kontrolle:** Keine Cloud-Dependencies für Daten
- **Future-Proof:** Python MCP Server erweiterbar für Neo4j (v2.5)
- **Cost-Efficiency:** Strategische API-Nutzung nur wo methodisch nötig

---

## Requirements

### Functional Requirements

**FR001: MCP Server Setup & Tool/Resource Implementation**
Das System implementiert einen Python-basierten MCP Server mit 7 Tools (store_raw_dialogue, compress_to_l2_insight, hybrid_search, update_working_memory, store_episode, get_golden_test_results, store_dual_judge_scores) und 5 Resources (memory://l2-insights, memory://working-memory, memory://episode-memory, memory://l0-raw, memory://stale-memory).

**FR002: Dialogtranskripte persistieren (L0 Raw Memory)**
Claude Code ruft MCP Tool `store_raw_dialogue` auf, um vollständige Konversationstranskripte in PostgreSQL zu speichern (Metadaten: Datum, Session-ID, Speaker).

**FR003: Semantische Kompression (L2 Insights)**
Claude Code komprimiert lange Dialogpassagen intern zu semantischen Insights und ruft MCP Tool `compress_to_l2_insight` auf. MCP Server validiert mit Information Density + Semantic Fidelity Checks (E2) und erstellt Embeddings via OpenAI API.

**FR004: Hybrid-Retrieval (Semantic + Keyword)**
Claude Code ruft MCP Tool `hybrid_search` mit Query + Query-Embedding auf. MCP Server durchsucht L0/L2 mit Hybrid-Ansatz (Semantic 70% + Keyword 30%, kalibrierbar via Grid Search in Phase 2) und merged Ergebnisse mit RRF.

**FR005: Query Expansion für robuste Suche**
Claude Code reformuliert Suchanfragen intern in 3 semantische Varianten (ersetzt Haiku API Call, €0/mo statt €8.50/mo), ruft `hybrid_search` für alle Varianten auf, merged Ergebnisse.

**FR006: Chain-of-Thought Generation (intern in Claude Code)**
Claude Code generiert Antworten basierend auf abgerufetem Kontext mit explizitem Reasoning (CoT: thought → reasoning → answer → confidence), ohne externe API-Calls (ersetzt Opus, €0/mo statt €92.50/mo).

**FR007: Self-Evaluation & Reflexion (EXTERN via Haiku API)** ✅ v3.1-Hybrid
MCP Server ruft Haiku API auf, um Antworten zu evaluieren (Reward -1.0 bis +1.0). Bei Reward <0.3: Haiku API generiert Reflexion. Claude Code ruft MCP Tool `store_episode` auf, um verbalisierte Lektionen zu speichern. **Rationale:** Deterministisch über Sessions, konsistente Episode Memory Quality.

**FR008: Working Memory Management**
Claude Code ruft MCP Tool `update_working_memory` auf. MCP Server hält 8-10 Items mit LRU Eviction + Importance-Overrides, archiviert kritische Items (Importance >0.8) zu Stale Memory statt Löschen (E6).

**FR009: Episode Memory Retrieval**
Claude Code liest MCP Resource `memory://episode-memory` vor Answer Generation, um vergangene ähnliche Queries + Reflexionen abzurufen ("Lessons Learned").

**Retrieval Parameters:**
- **Top-K Limit:** Top-3 Episodes (addressiert Context Window Risk)
- **Similarity Threshold:** Cosine Similarity >0.70 (nur relevante Lektionen)
- **Temporal Restriction:** Keine (Policy-Optimierung erfordert Zugriff auf alle historischen Lektionen)
- **Rationale:** Balance zwischen Kontext-Relevanz und Token-Effizienz

**FR010: Ground Truth Collection mit echten unabhängigen Dual Judges** ✅ v3.1-Hybrid
Streamlit UI (separate App) sammelt 50-100 gelabelte Queries. MCP Server ruft **GPT-4o API (OpenAI) + Haiku API (Anthropic)** auf für echte unabhängige Evaluation, berechnet Cohen's Kappa, speichert Ergebnisse. IRR Contingency Plan (E1) bei Kappa <0.70. **Rationale:** True inter-model reliability, methodisch valides Ground Truth.

**Query Creation Strategy:**
- **Stratified Sampling:** 40% Short (1-2 Sätze), 40% Medium (3-5 Sätze), 20% Long (6+ Sätze)
- **Temporal Diversity:** 3-5 Queries pro Session (verhindert Bias zu einzelnen Dialogkontexten)
- **Source Selection:** Automatisch aus L0 Raw Memory extrahiert, nicht manuell kuratiert
- **Human Curation:** ethr reviewed alle Queries auf Repräsentativität vor Labeling
- **Rationale:** Methodisch robustes Ground Truth Set mit realistischer Queryverteilung

**FR011: Hybrid Weight Calibration (Phase 2)**
Nach Phase 1b (Ground Truth Collection): Claude Code führt Grid Search auf Golden Set (50-100 Queries) durch, findet domänenspezifische Gewichte (erwartet 0.8/0.2 für psychologische Transkripte statt MEDRAG-Default 0.7/0.3).

**FR012: Model Drift Detection mit expanded Golden Set** ✅ v3.1-Hybrid
Claude Code führt täglich Golden Test Set (50-100 Queries, separater Set von Ground Truth) aus, prüft Accuracy-Drop >5%, alarmiert bei API-Änderungen (E7). **Rationale:** Statistisch robuste Baseline für Drift Detection.

**FR013: Graph Node Management (MCP Tool: graph_add_node)** ✅ v3.2-GraphRAG
MCP Server erstellt Graph-Knoten in PostgreSQL (Adjacency List Pattern). Parameter: label (Entity-Typ), name (Entity-Name), properties (JSONB). Idempotent basierend auf label+name Kombination. Optional: vector_id für Link zu L2 Insight Embedding.

**FR014: Graph Edge Management (MCP Tool: graph_add_edge)** ✅ v3.2-GraphRAG
MCP Server erstellt Kanten zwischen Knoten. Parameter: source_name, target_name, relation (z.B. "USES", "SOLVES", "CREATED_BY"), source_label, target_label. Erstellt Nodes automatisch falls nicht vorhanden. Gewichtung (0.0-1.0) für Relevanz-Ranking.

**FR015: Graph Neighbor Query (MCP Tool: graph_query_neighbors)** ✅ v3.2-GraphRAG
MCP Server findet verbundene Knoten via WITH RECURSIVE CTE. Parameter: node_name, relation_type (optional), depth (default=1, max=5). Use Case: "Welche Technologien nutzt Projekt X?" Response: JSON Liste der Nachbar-Nodes mit Relation und Gewichtung.

**FR016: Graph Pathfinding (MCP Tool: graph_find_path)** ✅ v3.2-GraphRAG
MCP Server findet kürzesten Pfad zwischen zwei Knoten. Parameter: start_node, end_node. Use Case: "Gibt es Verbindung zwischen Kunde X und Problem Y?" Response: Pfad als Node→Edge→Node Sequenz. Max Depth: 5 Hops.

### Non-Functional Requirements

**NFR001: Performance - Latency**
- **Query Response Time:** <5 Sekunden (p95) für vollständige RAG-Pipeline
  - Höher als v2.4.1 (<3s), da Claude Code "Denkzeit" hat (CoT intern)
  - Akzeptabel für philosophische Tiefe
- **Retrieval Time:** <1 Sekunde (p95) für Hybrid Search (MCP Tool Call)
- **External API Latency:** +200-500ms für Evaluation/Reflexion (10-15% aller LLM-Calls)

**NFR002: Accuracy - Retrieval & Evaluation**
- **Precision@5:** >0.75 (höher als v2.4.1 >0.70, dank text-embedding-3-small)
- **Inter-Rater Reliability (IRR):** Cohen's Kappa >0.70 ✅ **Methodisch valide** (GPT-4o + Haiku = true independence)
- **CoT Parse Success Rate:** >99.9% (Claude Code hat native JSON Support)
- **Golden Set Statistical Power:** >0.80 (alpha=0.05) bei 50-100 Queries

**NFR003: Budget & Cost Efficiency**
- **Production Budget:** €5-10/Monat (90-95% Savings vs. v2.4.1)
  - **Claude Code (in MAX):** €0/mo (Generation, Planning, CoT)
  - **Haiku API:** €1-2/mo (Evaluation, Reflexion bei 1000 queries/mo)
  - **GPT-4o API:** €1-1.5/mo (Dual Judge, 100 queries/mo + spot checks)
  - **Haiku API:** €1-1.5/mo (Dual Judge)
  - **OpenAI Embeddings:** €0.06/mo (1000 queries + compressions)
  - **Expanded Golden Set:** €1/mo (50-100 Queries + täglich Drift Detection)
- **After Staged Dual Judge (Month 4+):** €2-3/mo (nur spot checks statt full Dual Judge)

**NFR004: Reliability & Robustness**
- **Uptime:** Lokales System, manueller Start/Stop akzeptabel
- **Data Loss Prevention:** Kritische Items (Importance >0.8) werden archiviert statt gelöscht (Stale Memory)
- **Error Handling:**
  - 4-stufige JSON Fallbacks (Claude Code robust bei CoT Parsing)
  - IRR Contingency (E1) bei Dual Judge Disagreement
  - Semantic Fidelity Check (E2) bei Compression
  - **API Retry-Logic:** Exponential backoff bei Haiku/GPT-4o Ausfall
  - **Fallback zu Claude Code:** Bei API-Ausfall (degraded mode)

**Backup Strategy:**
- **PostgreSQL Backups:** Daily automated dumps (pg_dump) mit 7-day retention
- **L2 Insights in Git:** Read-only fallback, pushed täglich nach `/memory/l2-insights/`
- **Recovery Time Objective (RTO):** <1 hour (PostgreSQL restore from latest dump)
- **Recovery Point Objective (RPO):** <24 hours (daily backup window)
- **Backup Location:** Lokales NAS + optional cloud backup (out of scope v3.1)
- **Rationale:** Prevents catastrophic data loss, aligns with local-first philosophy

**NFR005: Transparency & Auditability**
- **Verbalisierte Reflexionen:** Alle Episode Memory-Einträge sind menschlich lesbar (nicht nur Scores)
- **MCP Resources:** Read-Only State Exposure ermöglicht Introspection
- **Logging:** Alle Retrieval-Operationen, Evaluationen und Reflexionen in PostgreSQL
- **Judge Provenance:** Ground Truth speichert judge1_model + judge2_model (GPT-4o, Haiku)

**NFR006: Local Control & Privacy**
- **Keine Cloud-Dependencies für Daten:** MCP Server + PostgreSQL laufen lokal
- **Externe Services nur für Compute:** Embeddings, Evaluation (kein Training auf User-Daten)
- **Datenhoheit:** Alle Konversationsdaten bleiben lokal

**NFR007: Methodological Validity** ✅ NEW in v3.1
- **True IRR:** Dual Judges sind echte unabhängige Modelle (GPT-4o + Haiku), nicht 2 Prompts
- **Statistical Power:** 50-100 Queries Golden Set → robuste Precision@5 Validation
- **Consistency:** Haiku API Evaluation ist deterministisch über Sessions (keine Session-State-Variabilität)
- **Production Reliability:** Externe APIs stabiler als Claude Code Session-State für Episode Memory

---

## User Journeys

### Primary Journey: Kontextreiche Konversation mit MCP-basiertem Memory

**Actor:** ethr (User)
**Goal:** Eine Frage an Claude Code stellen und eine Antwort erhalten, die auf vergangenen Gesprächen basiert

**Journey:**

1. **Frage stellen**
   - ethr öffnet Claude Code und stellt eine Frage
   - Beispiel: "Was denke ich über Autonomie?"

2. **Query Expansion (intern in Claude Code)**
   - Claude Code reformuliert Frage in 3 semantische Varianten
   - Varianten: "Was ist meine Meinung zu Autonomie?", "Wie sehe ich Selbstständigkeit?", "Autonomie - meine Perspektive?"
   - **Ersetzt:** Claude Haiku API Call (€0 statt €0.50)

3. **Query Embedding (externer Call - OpenAI)**
   - Claude Code ruft OpenAI Embeddings API auf
   - Cost: €0.00002 (2 Cent per 1M tokens)

4. **Hybrid Retrieval (MCP Tool Call)**
   - Claude Code ruft MCP Tool `hybrid_search` auf (4 Varianten parallel)
   - MCP Server durchsucht L0/L2 mit Semantic (70%) + Keyword (30%)
   - RRF Fusion merged Ergebnisse → Top 5 Dokumente
   - **Latency:** <1s

5. **Episode Memory Check (MCP Resource)**
   - Claude Code liest `memory://episode-memory` (ähnliche vergangene Queries)
   - Falls vorhanden: Lädt verbalisierte Lektionen ("Lessons Learned")

6. **Answer Generation mit CoT (intern in Claude Code)**
   - Claude Code generiert Antwort basierend auf:
     - Retrieved Context (Top 5 Dokumente)
     - Past Episodes (falls relevant)
   - CoT Format: Thought → Reasoning → Answer → Confidence
   - **Ersetzt:** Claude Opus API Call (€0 statt €0.50)

7. **Self-Evaluation (EXTERN via Haiku API)** ✅ v3.1-Hybrid
   - MCP Server ruft Haiku API auf für Evaluation
   - Haiku evaluiert Antwort (Reward -1.0 bis +1.0)
   - **Cost:** €0.001 (1000 Evaluations = €1/mo)
   - **Rationale:** Deterministisch, konsistent über Sessions

8. **Reflexion bei Bedarf (EXTERN via Haiku API)** ✅ v3.1-Hybrid
   - Falls Reward <0.3: MCP Server ruft Haiku API für Reflexion auf
   - Haiku generiert verbalisierte Lektion ("Was lief schief?", "Was tun in Zukunft?")
   - Claude Code ruft MCP Tool `store_episode` auf
   - **Cost:** €0.0015 (~300 Reflexionen/mo = €0.45/mo)

9. **Antwort erhalten**
   - ethr erhält Antwort mit:
     - Explizitem Reasoning (CoT)
     - Confidence Score
     - Quellen (L2 Insight IDs)
     - Falls Reflexion: "Lesson Learned: ..."

10. **Working Memory Update (MCP Tool Call)**
    - Claude Code ruft `update_working_memory` auf
    - MCP Server fügt Query+Answer hinzu
    - Falls voll (>10 Items): LRU Eviction
    - Kritische Items → Stale Memory Archive

**Outcome:** ethr erhält kontextreiche Antwort in <5s. System lernt aus Fehlern mit konsistenten Reflexionen. Bulk-Operationen kostenfrei (Claude Code), kritische Evaluationen extern (Haiku).

**Cost per Query:** ~€0.003
- Embeddings: €0.00002
- Evaluation: €0.001
- Reflexion (30% Queries): €0.0015
- **Total:** ~€3/mo bei 1000 Queries

---

## UX Design Principles

**UX1: Transparenz über Blackbox**
- Zeige explizites Reasoning (CoT: Thought → Reasoning → Answer)
- Mache Retrieval-Quellen sichtbar (L2 Insight IDs, optionale Snippet-Anzeige)
- Zeige Confidence-Score bei jeder Antwort
- Verbalisierte Reflexionen sind lesbar ("Lesson Learned: ...")
- **NEW:** Judge Provenance in Ground Truth UI (GPT-4o + Haiku Scores)

**UX2: Minimale Reibung trotz MCP-Komplexität**
- Claude Code Interface: Frage stellen → Antwort erhalten (<5s)
- Alle komplexen Operationen (Query Expansion, Hybrid Search, Reflexion) automatisch im Hintergrund
- MCP Server ist unsichtbar für User (läuft als Background-Prozess)
- Externe API-Calls sind unsichtbar (MCP Server handled)
- Kein manuelles Konfigurieren erforderlich (Hybrid Weights werden in Phase 2 kalibriert)

**UX3: Lernen sichtbar machen**
- Episode Memory-Reflexionen als "Lesson Learned" anzeigen
- Zeige wenn das System aus vergangenen Fehlern lernt (Reward-Anzeige optional)
- Ermögliche Einsicht in vergangene Episodes via MCP Resource (optional für Power-User)

**UX4: Ground Truth Collection - Dedizierte UI**
- Separate Streamlit App (nicht in Claude Code)
- Binäre Entscheidungen (Relevant? Ja/Nein)
- Stratified Sampling automatisch (40% Short / 40% Medium / 20% Long)
- Progress-Anzeige ("68/100 Queries gelabelt", Cohen's Kappa live)
- **NEW:** Dual Judge Scores anzeigen (GPT-4o vs. Haiku Agreement)

**UX5: Fehlertoleranz durch Fallbacks**
- System crasht niemals bei JSON Parsing (4-stufige Fallbacks in Claude Code)
- Bei Unsicherheit: Zeige Confidence-Score statt Fehler
- Model Drift Alerts sind informativ ("Golden Test Accuracy dropped 5%"), nicht alarmierend
- IRR Contingency Plan triggert automatisch bei Kappa <0.70
- **NEW:** API-Ausfall-Fallback (degraded mode mit Claude Code Evaluation)

---

## Technical Architecture

### MCP Server Components

**Language:** Python (D1)
**Tech Stack:**
- `mcp` (Python MCP SDK)
- `psycopg2` (PostgreSQL + pgvector)
- `openai` (Embeddings API + GPT-4o API)
- `anthropic` (Haiku API)
- `numpy` (Vector Operations)

**11 MCP Tools (Actions):**
1. `store_raw_dialogue` - L0 Storage
2. `compress_to_l2_insight` - L2 Creation + Embedding
3. `hybrid_search` - RAG Retrieval (60% Semantic + 20% Keyword + 20% Graph) ✅ v3.2
4. `update_working_memory` - Session State
5. `store_episode` - Reflexion Storage
6. `get_golden_test_results` - Model Drift Detection
7. `store_dual_judge_scores` - IRR Validation (calls GPT-4o + Haiku APIs) ✅ v3.1
8. `graph_add_node` - Graph Node erstellen (idempotent) ✅ v3.2-GraphRAG
9. `graph_add_edge` - Graph Edge erstellen ✅ v3.2-GraphRAG
10. `graph_query_neighbors` - Nachbar-Nodes finden ✅ v3.2-GraphRAG
11. `graph_find_path` - Pfad zwischen Nodes finden ✅ v3.2-GraphRAG

**5 MCP Resources (Read-Only State):**
1. `memory://l2-insights?query={q}&top_k={k}`
2. `memory://working-memory`
3. `memory://episode-memory?query={q}&min_similarity={t}`
4. `memory://l0-raw?session_id={id}&date_range={r}`
5. `memory://stale-memory?importance_min={t}`

**Database:** PostgreSQL + pgvector (unverändert aus v2.4.1)
- Tables: l0_raw, l2_insights, working_memory, episode_memory, stale_memory, ground_truth
- **NEW Columns (v3.1):** judge1_model, judge2_model in ground_truth table
- **NEW Tables (v3.2-GraphRAG):** nodes, edges (Adjacency List Pattern für Graph-Speicherung)

### Claude Code Integration

**Alle primären LLM-Operationen in Claude Code (€0/mo):**
- Query Expansion (ersetzt Haiku, €0/mo)
- CoT Generation (ersetzt Opus, €0/mo)
- Planning & Orchestration (intern)

**Kritische Evaluationen via externe APIs (€3-4/mo):**
- Self-Evaluation: Haiku API (€1-2/mo)
- Reflexion: Haiku API (€0.50/mo)
- Dual Judge: GPT-4o + Haiku APIs (€2-3/mo)

**Claude Code Workflow:**
1. User Query → Query Expansion (intern)
2. Embeddings API Call (OpenAI, €0.00002)
3. MCP Tool Call: `hybrid_search` (4 Varianten)
4. MCP Resource Read: `episode-memory`
5. CoT Generation (intern)
6. **MCP Server → Haiku API:** Evaluation (€0.001) ✅ v3.1
7. **Falls Reward <0.3 → Haiku API:** Reflexion (€0.0015) ✅ v3.1
8. MCP Tool Call: `store_episode`
9. MCP Tool Call: `update_working_memory`

**No Multi-Threading:**
- Claude Code Sequential Processing (kein Haiku+Opus parallel wie v2.4.1)
- Mitigation: Latency <5s akzeptabel

### External Dependencies

**External API 1: OpenAI Embeddings**
- Model: `text-embedding-3-small` (1536 dimensions)
- Cost: €0.02 per 1M tokens
- Budget: ~€0.06/mo bei 1000 queries + compressions
- **Rationale:** Bessere Precision@5 als lokale Embeddings

**External API 2: GPT-4o (Dual Judge)** ✅ v3.1
- Model: `gpt-4o`
- Cost: ~€1-1.5/mo (100 Queries Phase 1b + spot checks)
- **Rationale:** True independence für Cohen's Kappa

**External API 3: Claude Haiku (Dual Judge + Evaluation)** ✅ v3.1
- Model: `claude-3-5-haiku-20241022`
- Cost: ~€2-3/mo (Dual Judge + Evaluation + Reflexion)
- **Rationale:** Deterministisch, konsistent, true independence

**API Reliability Measures:**
- Retry-Logic mit Exponential Backoff
- Fallback zu Claude Code bei API-Ausfall (degraded mode)
- Budget-Monitoring + Alerts bei >€10/mo

---

## Epics

### Epic 1: MCP Server Foundation & Ground Truth Collection

**Deliverables:**
- PostgreSQL + pgvector Setup (lokal)
- Python MCP Server Implementation
- 7 MCP Tools + 5 MCP Resources
- **Ground Truth Collection (50-100 gelabelte Queries)** ✅ v3.1
- Streamlit Labeling UI
- **Dual Judge Implementation (GPT-4o + Haiku APIs)** ✅ v3.1
- IRR Validation (Cohen's Kappa >0.70)

**Timeline:** Phase 1a (20-25h) + Phase 1b (18-25h) = 38-50h
**Dependencies:** Keine
**Critical Path:** Ground Truth Collection (benötigt für Hybrid Calibration in Epic 2)
**Cost (Phase 1b):** €0.23 einmalig (100 Queries Dual Judge)

### Epic 2: RAG Pipeline & Hybrid Calibration

**Deliverables:**
- Claude Code ↔ MCP Server Integration
- Hybrid Search Implementation (Semantic + Keyword)
- Query Expansion Logik (intern in Claude Code)
- CoT Generation Logik (intern in Claude Code)
- **Reflexion-Framework (extern via Haiku API)** ✅ v3.1
- **Evaluation via Haiku API** ✅ v3.1
- Hybrid Weight Calibration (Grid Search auf 50-100 Queries Golden Set)

**Timeline:** Phase 2 (35-45h)
**Dependencies:** Epic 1 (Ground Truth Required)
**Critical Success Factor:** Calibration liefert +5-10% Precision@5 Uplift
**Cost (Development):** €1-2/mo (Testing)

### Epic 3: Evaluation, Working Memory & Production Readiness

**Deliverables:**
- Working Memory Eviction Logic (LRU + Importance)
- Stale Memory Archive (kritische Items)
- Episode Memory Storage & Retrieval
- Staged Dual Judge (Phase 1: Dual → Phase 2: Single nach IRR >0.85)
- **Golden Test Set (50-100 Queries)** ✅ v3.1
- Model Drift Detection (täglich)
- Precision@5 Validation (>0.75)
- Latency Testing (<5s p95)
- External API Retry-Logic + Fallbacks

**Timeline:** Phase 3 (25-35h) + Phase 4 (20-25h) + Phase 5 (15-20h) = 60-80h
**Dependencies:** Epic 2
**Cost (Production):** €5-10/mo (full Dual Judge), dann €2-3/mo (nach Staged Dual Judge)

---

## Out of Scope (v3.2.0-GraphRAG)

**Explizit NICHT in Scope:**

1. ~~**Neo4j Knowledge Graph Integration**~~ → **IN SCOPE als PostgreSQL Adjacency List (v3.2-GraphRAG)**
2. **Multi-User Support** (aktuell nur ethr)
3. **Cloud Deployment** (nur lokal)
4. **Multi-LLM Support für Generation** (nur Claude Code, keine Gemini Integration)
5. **Voice Interface** (nur Text)
6. **Advanced Agentic Workflows** (v2.4.1 hatte Commander/Planner/Writer Agents, v3.1 hat nur Claude Code + externe Evaluatoren)
7. **Fine-Tuning** (System nutzt Verbal RL statt Fine-Tuning)
8. **Automatische Entity Extraction** (Graph-Nodes werden manuell via MCP Tools erstellt, kein LLM-basiertes NER)

**Preserved for Future Phases:**

- Lokale Embeddings-Fallback (sentence-transformers bei OpenAI API Ausfall)
- UI für Episode Memory Exploration (Power-User Feature)
- Automated Hybrid Weight Re-Calibration (bei Domain Shift)
- Full Multi-LLM Agentic Architecture (v2.5)

---

## Success Criteria

### Phase 1 (Foundation) - Success Criteria

- ✅ PostgreSQL + pgvector läuft lokal
- ✅ MCP Server implementiert (7 Tools, 5 Resources)
- ✅ Claude Code kann MCP Server erreichen (MCP Protocol handshake)
- ✅ **Ground Truth Collection: 50-100 Queries gelabelt** (statistisch robust)
- ✅ **Cohen's Kappa >0.70 (true independence: GPT-4o + Haiku)**
- ✅ IRR Contingency Plan funktioniert bei Kappa <0.70

### Phase 2 (RAG Pipeline) - Success Criteria

**Precision@5 Performance:**
- ✅ **Full Success:** ≥0.75 (System ready for production)
- ⚠️ **Partial Success:** 0.70-0.74 (Deploy with monitoring, iterate on calibration)
- ❌ **Failure:** <0.70 (Requires architecture review or additional ground truth)

**Other Metrics:**
- ✅ Query Expansion: +10-15% Recall Uplift
- ✅ Latency <5s (p95) für komplette Pipeline
- ✅ Hybrid Weight Calibration findet bessere Gewichte als 0.7/0.3 (erwartet 0.8/0.2)
- ✅ **Haiku API Evaluation funktioniert (Reward -1.0 bis +1.0)**
- ✅ **Reflexion-Framework generiert konsistente Lektionen**

**Rationale:** Graduated criteria ermöglichen adaptive Steuerung - Partial Success erlaubt Production Deployment mit kontinuierlicher Verbesserung

### Phase 3-5 (Production) - Success Criteria

- ✅ Working Memory Eviction funktioniert (keine kritischen Items verloren)
- ✅ Episode Memory speichert Reflexionen korrekt
- ✅ **Golden Test Set läuft täglich (50-100 Queries)**
- ✅ **Budget bleibt unter €10/mo (first 3 months)**
- ✅ **Budget reduziert auf €2-3/mo (after Staged Dual Judge)**
- ✅ System läuft stabil über 7 Tage ohne Crashes
- ✅ **API Retry-Logic funktioniert (bei Haiku/GPT-4o Ausfall)**

### Overall Success

- ✅ **Budget-Ziel:** €5-10/mo Production (90-95% Savings vs. v2.4.1)
- ✅ **Performance-Ziel:** Precision@5 >0.75, Latency <5s
- ✅ **Reliability-Ziel:** Kappa >0.70 (true IRR), CoT Parse >99.9%
- ✅ **Methodological Validity:** True independent Dual Judges, 50-100 Queries Golden Set
- ✅ **User Satisfaction:** ethr kann philosophische Gespräche über Monate führen ohne Kontext-Verlust

---

## Risks & Mitigation

### Risk 1: MCP Protocol Komplexität

**Risk:** MCP ist neu, wenig dokumentiert, potenzielle Bugs
**Impact:** High (Blocker für gesamtes System)
**Mitigation:**
- MCP Inspector für Testing nutzen
- Python MCP SDK ist stabiler als TypeScript
- Fallback: Standalone REST API wenn MCP nicht funktioniert

### Risk 2: Claude Code Context Window

**Risk:** Sehr lange Retrieval-Kontexte könnten 200K Token-Limit überschreiten
**Impact:** Medium (System crasht bei langen Dialogen)
**Mitigation:**
- Top-5 statt Top-10 Retrieval
- Adaptive L2 Compression
- Truncation-Logik in Claude Code

### Risk 3: External API Dependencies ✅ NEW in v3.1

**Risk:** Haiku/GPT-4o API-Ausfall → Evaluation/Reflexion unavailable
**Impact:** Medium (System degradiert, aber nicht komplett down)
**Mitigation:**
- Retry-Logic mit Exponential Backoff
- Fallback zu Claude Code Evaluation (degraded mode)
- Monitoring + Alerts
- **Probability:** 1-2% Ausfallrate/Jahr

### Risk 4: API Cost Variability ✅ NEW in v3.1

**Risk:** API-Preise steigen (10-20%/Jahr)
**Impact:** Low (€5-10/mo → €6-12/mo)
**Mitigation:**
- Monatliches Budget-Monitoring
- Alerts bei >€10/mo
- Staged Dual Judge reduziert Kosten nach 3 Monaten (-40%)

### Risk 5: IRR Validation Failure

**Risk:** Cohen's Kappa <0.70 bei Dual Judge
**Impact:** Medium (Critical Path Blockade)
**Mitigation:**
- IRR Contingency Plan (E1) implementiert
- 3 Fallback-Strategien (Human Tiebreaker, Wilcoxon Test, Judge Recalibration)
- **v3.1 Improvement:** True independence → höhere Wahrscheinlichkeit für Kappa >0.70

### Risk 6: Lokale PostgreSQL Performance

**Risk:** 10K+ L2 Insights könnten langsame Queries verursachen
**Impact:** Low (nur Latency-Erhöhung)
**Mitigation:**
- IVFFlat Index für pgvector (lists=100)
- Monitoring in Phase 5
- Upgrade zu Cloud-DB falls nötig (but out of scope)

---

## Next Steps

**Immediate Actions:**

1. ✅ **v3.1-Hybrid Architecture Finalized** (mcp-architecture-specification-v3.1-hybrid.md)
2. ✅ **PRD Updated** (dieses Dokument)
3. **Epic & Story Breakdown Update** (NEXT) → epic-stories.md
   - Update E1-S06 (Dual Judge mit GPT-4o + Haiku)
   - Update E2-S04 (Evaluation/Reflexion extern)
   - Update E3-S04 (Golden Set 50-100 Queries)
   - Budget + Timeline adjustments

**After Epic-Stories Update:**

4. **Phase 1a Implementation** (MCP Server Foundation)
5. **Phase 1b Implementation** (Ground Truth mit externen APIs)
6. **Phase 2+ Implementation** (RAG Pipeline, Working Memory, Monitoring)

**Review-Punkte:**

- PRD Review mit ethr (vor Epic-Stories)
- Epic-Stories Review mit ethr (vor Implementation)
- Phase 1 Demo (nach Foundation)
- Phase 2 Demo (nach RAG Pipeline + Calibration)
- Final Demo (after Phase 5)

---

## Document Status

- [x] Goals and context validated
- [x] v3.1-Hybrid architecture decisions finalized (D1-D6)
- [x] Budget confirmed (€5-10/mo)
- [x] Functional requirements updated (12 FRs)
- [x] Non-functional requirements updated (7 NFRs)
- [x] User journey updated (externe API-Calls)
- [x] Epic structure drafted (3 Epics)
- [ ] Epic-stories.md update required (NEXT)

**Reference Documents:**
- **Architecture:** `mcp-architecture-specification-v3.1-hybrid.md` ✅
- **Previous Architecture:** `mcp-architecture-specification.md` (v3.0.0-MCP, archived)
- **Analysis:** `project-workflow-analysis.md`
- **Old Version:** `PRD-v2.4.1-DRAFT-ARCHIVED.md` (reference only)

**Changelog v3.0.0-MCP → v3.1.0-Hybrid:**
- ✅ Budget: €0.06/mo → €5-10/mo (90-95% savings maintained)
- ✅ Dual Judge: Claude Code 2x → GPT-4o + Haiku (true IRR)
- ✅ Evaluation/Reflexion: Claude Code intern → Haiku API (consistency)
- ✅ Golden Set: 20 Queries → 50-100 Queries (statistical robustness)
- ✅ NFR007 added: Methodological Validity
- ✅ Risk 3+4 added: External API Dependencies + Cost Variability
- ✅ Success Criteria updated: API-specific targets

---

_This PRD is designed for Level 2 projects - providing appropriate detail for a 2.5-3.5 month implementation with v3.1-Hybrid MCP-based architecture._
