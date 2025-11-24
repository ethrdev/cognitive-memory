# i-o - Epic Breakdown

**Author:** ethr
**Date:** 2025-11-09
**Project Level:** Level 2
**Target Scale:** Small Complete System (12-18 Stories, 2-3 Monate)

---

## Overview

Dieses Dokument bietet die vollständige Epic- und Story-Dekomposition für das **Cognitive Memory System v3.1.0-Hybrid**, basierend auf dem [PRD](./planning/PRD.md). Das System ist ein MCP-basiertes Gedächtnissystem, das Claude Code mit persistentem, kontextreichem Retrieval ausstattet.

**Architektur-Modus:** MCP Server + Claude Code Integration

- **Bulk-Operationen:** Generation, CoT, Planning (€0/mo, intern in Claude Code)
- **Kritische Evaluationen:** Dual Judge, Reflexion (€5-10/mo, externe APIs)
- **Budget-Ziel:** 90-95% Kostenreduktion vs. v2.4.1

**Timeline:** 133-175 Stunden (2.5-3.5 Monate bei 20h/Woche)

### Epic Summary

Das Projekt ist in **3 Epics** unterteilt, die den Implementierungsverlauf widerspiegeln:

1. **Epic 1: MCP Server Foundation & Ground Truth Collection** (38-50h)
   - Technisches Fundament: PostgreSQL + pgvector, Python MCP Server
   - Methodisches Fundament: Ground Truth Collection mit echten unabhängigen Dual Judges
   - Deliverables: 7 MCP Tools, 5 MCP Resources, 50-100 gelabelte Queries, Cohen's Kappa >0.70

2. **Epic 2: RAG Pipeline & Hybrid Calibration** (35-45h)
   - Claude Code Integration: Query Expansion, CoT Generation (intern)
   - Hybrid Search Implementation: Semantic + Keyword mit RRF Fusion
   - Reflexion-Framework: Externe Evaluation/Reflexion via Haiku API
   - Critical Success: Precision@5 >0.75 nach Grid Search Calibration

3. **Epic 3: Working Memory, Evaluation & Production Readiness** (60-80h)
   - Session Management: Working Memory mit LRU Eviction + Stale Memory Archive
   - Monitoring: Golden Test Set, Model Drift Detection, API Retry-Logic
   - Production Deployment: Budget €5-10/mo, Latency <5s, Staged Dual Judge

---

## Epic 1: MCP Server Foundation & Ground Truth Collection

**Epic Goal:** Etabliere das technische und methodische Fundament für das Cognitive Memory System durch Implementierung eines Python MCP Servers mit PostgreSQL-Persistence und Sammlung eines methodisch validen Ground Truth Sets (50-100 Queries) mit echten unabhängigen Dual Judges (GPT-4o + Haiku).

**Business Value:** Ermöglicht alle nachfolgenden Phasen durch (1) funktionale MCP-basierte Persistence-Infrastruktur und (2) statistisch robuste Evaluation-Baseline für Hybrid Calibration (Epic 2) und Model Drift Detection (Epic 3).

**Timeline:** 38-50 Stunden (Phase 1a: 20-25h, Phase 1b: 18-25h)
**Budget:** €0.23 einmalig (100 Queries Dual Judge)

---

### Story 1.1: Projekt-Setup und Entwicklungsumgebung

**Als** Entwickler,
**möchte ich** die grundlegende Projektstruktur und Entwicklungsumgebung aufsetzen,
**sodass** ich eine solide Foundation für die MCP Server-Implementierung habe.

**Acceptance Criteria:**

**Given** ein leeres Projektverzeichnis
**When** ich die Projektstruktur initialisiere
**Then** existieren folgende Komponenten:

- Python-Projekt mit Poetry/pip requirements (mcp, psycopg2, openai, anthropic, numpy)
- Git-Repository mit .gitignore (PostgreSQL credentials, .env)
- Projektstruktur: `/mcp_server/`, `/tests/`, `/docs/`, `/config/`
- Environment-Template (.env.template) für API-Keys und DB-Credentials
- README.md mit Setup-Anleitung

**And** die Entwicklungsumgebung ist lokal lauffähig:

- Python 3.11+ installiert
- Virtual Environment erstellt
- Dependencies installiert
- Pre-commit Hooks für Code-Qualität (black, ruff, mypy)

**Prerequisites:** Keine (Foundation Story)

**Technical Notes:**

- Python 3.11+ für bessere Type Hints
- Poetry bevorzugt für Dependency Management
- MCP SDK: `pip install mcp` (Python MCP SDK)
- Projektstruktur folgt MCP Best Practices (siehe MCP Docs)
- .env.template sollte alle erforderlichen Variablen dokumentieren

---

### Story 1.2: PostgreSQL + pgvector Setup

**Als** Entwickler,
**möchte ich** PostgreSQL mit pgvector-Extension lokal aufsetzen,
**sodass** ich Embeddings (1536-dimensional) effizient speichern und durchsuchen kann.

**Acceptance Criteria:**

**Given** eine lokale Entwicklungsumgebung
**When** ich PostgreSQL + pgvector installiere und konfiguriere
**Then** ist folgendes Setup vorhanden:

- PostgreSQL 15+ läuft lokal (Port 5432)
- pgvector Extension ist installiert und aktiviert
- Datenbank `cognitive_memory` existiert
- User `mcp_user` mit entsprechenden Rechten

**And** folgende Tabellen sind erstellt:

- `l0_raw` (id, session_id, timestamp, speaker, content, metadata)
- `l2_insights` (id, content, embedding vector(1536), created_at, source_ids, metadata)
- `working_memory` (id, content, importance, last_accessed, created_at)
- `episode_memory` (id, query, reward, reflection, created_at, embedding vector(1536))
- `stale_memory` (id, original_content, archived_at, importance, reason)
- `ground_truth` (id, query, expected_docs, judge1_score, judge2_score, judge1_model, judge2_model, kappa, created_at)

**And** IVFFlat-Index ist konfiguriert (lists=100) für Vektor-Suche

**Prerequisites:** Story 1.1 (Projekt-Setup)

**Technical Notes:**

- Installation: `apt install postgresql postgresql-contrib` + pgvector from source
- IVFFlat Index: Guter Kompromiss zwischen Speed und Accuracy für <100k Vektoren
- Embedding-Dimension: 1536 (OpenAI text-embedding-3-small)
- Migration-Scripts in `/migrations/` für Schema-Änderungen
- Connection Pooling optional (psycopg2.pool) bei Performance-Problemen

---

### Story 1.3: MCP Server Grundstruktur mit Tool/Resource Framework

**Als** Entwickler,
**möchte ich** die MCP Server-Grundstruktur mit Tool- und Resource-Registration implementieren,
**sodass** Claude Code den Server erreichen und Tools/Resources entdecken kann.

**Acceptance Criteria:**

**Given** PostgreSQL läuft und Projekt-Setup ist abgeschlossen
**When** ich den MCP Server starte
**Then** ist der Server über MCP Protocol erreichbar:

- MCP Server läuft auf localhost (stdio transport)
- Server antwortet auf MCP Handshake
- Claude Code kann Server in MCP Settings hinzufügen
- Server loggt eingehende Requests

**And** folgendes Framework ist implementiert:

- Tool Registration System (Decorator-basiert oder Registry-Pattern)
- Resource Registration System mit URI-Schema `memory://`
- Error Handling für ungültige Tool-Calls
- Logging-Infrastruktur (Structured Logging mit JSON)

**And** mindestens 1 Dummy-Tool/Resource zum Testing:

- `ping` Tool (gibt "pong" zurück)
- `memory://status` Resource (zeigt DB-Connection Status)

**Prerequisites:** Story 1.2 (PostgreSQL Setup)

**Technical Notes:**

- Python MCP SDK: `from mcp.server import Server`
- Transport: stdio (Standard für lokale MCP Server)
- Tool-Schema: JSON Schema für Parameter-Validierung
- Resource URIs: `memory://l2-insights`, `memory://working-memory`, etc.
- Claude Code MCP Config: `~/.config/claude-code/mcp-settings.json`

---

### Story 1.4: L0 Raw Memory Storage (MCP Tool: store_raw_dialogue)

**Als** Claude Code,
**möchte ich** vollständige Dialogtranskripte in PostgreSQL speichern,
**sodass** der komplette Konversationsverlauf persistent ist.

**Acceptance Criteria:**

**Given** der MCP Server läuft und PostgreSQL ist verbunden
**When** Claude Code das Tool `store_raw_dialogue` aufruft mit Parametern (session_id, speaker, content, metadata)
**Then** wird der Dialog in `l0_raw` gespeichert:

- Alle Felder korrekt persistiert
- Timestamp automatisch generiert (UTC)
- Session-ID für Gruppierung vorhanden
- Metadata als JSONB gespeichert

**And** das Tool gibt Erfolgsbestätigung zurück:

- Response enthält generierte ID
- Response enthält Timestamp
- Bei Fehler: Klare Error-Message

**Prerequisites:** Story 1.3 (MCP Server Grundstruktur)

**Technical Notes:**

- Parameter: `session_id` (UUID), `speaker` (string: "user"|"assistant"), `content` (text), `metadata` (dict)
- JSONB für flexible Metadata (z.B. {"tags": ["philosophy"], "mood": "reflective"})
- Index auf session_id + timestamp für schnelle Session-Abfragen
- Keine Validierung von Content-Länge (kann sehr lang sein)

---

### Story 1.5: L2 Insights Storage mit Embedding (MCP Tool: compress_to_l2_insight)

**Als** Claude Code,
**möchte ich** komprimierte semantische Insights mit Embeddings speichern,
**sodass** effiziente semantische Suche möglich ist.

**Acceptance Criteria:**

**Given** der MCP Server läuft und OpenAI API-Key ist konfiguriert
**When** Claude Code das Tool `compress_to_l2_insight` aufruft mit (content, source_ids)
**Then** wird das Insight verarbeitet und gespeichert:

- OpenAI Embeddings API wird aufgerufen (text-embedding-3-small)
- Embedding (1536-dim) wird in `l2_insights` gespeichert
- Content + source_ids werden persistiert
- Timestamp wird gesetzt

**And** Semantic Fidelity Check ist implementiert (Enhancement E2):

- Berechne Information Density: Anzahl semantischer Einheiten / Token-Count
- Prüfe Density >0.5 (configurable threshold)
- Bei Density <0.5: Warning zurückgeben (aber speichern)

**And** das Tool gibt Erfolgsbestätigung zurück:

- Response enthält generierte L2 Insight ID
- Response enthält Fidelity-Score
- Bei API-Fehler: Retry mit Exponential Backoff (3 Versuche)

**Prerequisites:** Story 1.4 (L0 Storage funktioniert)

**Technical Notes:**

- OpenAI API: `client.embeddings.create(model="text-embedding-3-small")`
- Cost: €0.00002 per Embedding
- Semantic Fidelity: Einfache Heuristik (Anzahl Nomen/Verben / Token-Count)
- Retry-Logic: 1s, 2s, 4s delays bei Rate-Limit/Transient Errors
- source_ids: Array von L0 Raw IDs (welche Dialoge wurden komprimiert)

---

### Story 1.6: Hybrid Search Implementation (MCP Tool: hybrid_search)

**Als** Claude Code,
**möchte ich** Hybrid-Suche (Semantic + Keyword) über L0/L2 durchführen,
**sodass** ich relevante Memories für Query-Beantwortung abrufen kann.

**Acceptance Criteria:**

**Given** L2 Insights mit Embeddings sind vorhanden
**When** Claude Code `hybrid_search` aufruft mit (query_embedding, query_text, top_k, weights)
**Then** werden beide Suchstrategien parallel ausgeführt:

- **Semantic Search:** pgvector Cosine Similarity auf L2 Embeddings (Gewicht: weights.semantic)
- **Keyword Search:** PostgreSQL Full-Text Search (ts_vector) auf L2 Content (Gewicht: weights.keyword)
- **Fusion:** Reciprocal Rank Fusion (RRF) merged beide Result-Sets

**And** Top-K Ergebnisse werden zurückgegeben:

- Jedes Ergebnis enthält: L2 ID, Content, Score, Source IDs
- Sortiert nach finaler RRF-Score
- Limit: top_k (default: 5)

**And** Default-Gewichte sind konfigurierbar:

- Default: semantic=0.7, keyword=0.3 (MEDRAG-Baseline)
- Kann in config.yaml überschrieben werden
- Wird in Epic 2 via Grid Search kalibriert

**Prerequisites:** Story 1.5 (L2 Insights mit Embeddings)

**Technical Notes:**

- RRF Formula: `score = Σ 1/(k + rank_i)` mit k=60 (Standard)
- pgvector: `ORDER BY embedding <=> query_embedding LIMIT top_k`
- Full-Text Search: `to_tsvector('english', content)` mit ts_rank
- Gewichte: Nur zur Normalisierung der Scores vor RRF
- Performance: <1s für Hybrid Search (NFR001)

---

### Story 1.7: Working Memory Management (MCP Tool: update_working_memory)

**Als** Claude Code,
**möchte ich** Working Memory mit LRU Eviction verwalten,
**sodass** der aktuelle Session-Kontext begrenzt bleibt (8-10 Items).

**Acceptance Criteria:**

**Given** Working Memory enthält Items
**When** Claude Code `update_working_memory` aufruft mit (content, importance)
**Then** wird das Item hinzugefügt und Eviction durchgeführt:

- Item wird in `working_memory` gespeichert
- Importance-Score (0.0-1.0) wird gesetzt
- last_accessed wird aktualisiert
- Falls >10 Items: LRU Eviction wird getriggert

**And** LRU Eviction mit Importance-Override funktioniert:

- Items werden sortiert nach last_accessed (älteste zuerst)
- Items mit Importance >0.8 werden übersprungen (Critical Items)
- Ältestes Non-Critical Item wird entfernt
- Entferntes Item wird zu Stale Memory archiviert (Enhancement E6)

**And** Stale Memory Archive wird befüllt:

- Archivierte Items in `stale_memory` mit Timestamp + Reason
- Reason: "LRU_EVICTION" oder "MANUAL_ARCHIVE"
- Original Content + Importance erhalten

**Prerequisites:** Story 1.3 (MCP Server Grundstruktur)

**Technical Notes:**

- Capacity: 8-10 Items (configurable)
- Importance Threshold: >0.8 für Critical Items
- LRU-Sortierung: `ORDER BY last_accessed ASC`
- Stale Memory: Unbegrenzte Retention (kein automatisches Löschen)
- Resource `memory://stale-memory` ermöglicht Zugriff

---

### Story 1.8: Episode Memory Storage (MCP Tool: store_episode)

**Als** MCP Server,
**möchte ich** verbalisierte Reflexionen aus Haiku API in Episode Memory speichern,
**sodass** vergangene Lektionen bei ähnlichen Queries abrufbar sind.

**Acceptance Criteria:**

**Given** Haiku API hat eine Reflexion generiert
**When** Claude Code `store_episode` aufruft mit (query, reward, reflection)
**Then** wird das Episode in `episode_memory` gespeichert:

- Query, Reward (-1.0 bis +1.0), Reflection als Text
- Query wird embedded (OpenAI API) für spätere Similarity-Suche
- Timestamp wird gesetzt

**And** das Tool gibt Erfolgsbestätigung zurück:

- Response enthält Episode ID
- Response enthält Embedding Status

**Prerequisites:** Story 1.5 (Embedding-Logik funktioniert)

**Technical Notes:**

- Reward: Float zwischen -1.0 (schlechte Antwort) und +1.0 (exzellent)
- Reflection: Verbalisierte Lektion im Format "Was lief schief?" / "Was tun in Zukunft?"
- Embedding: Gleiche OpenAI API wie L2 Insights
- Retrieval-Parameter (FR009): Top-3 Episodes, Cosine Similarity >0.70

---

### Story 1.9: MCP Resources für Read-Only State Exposure

**Als** Claude Code,
**möchte ich** MCP Resources nutzen um Memory-State zu lesen,
**sodass** ich Kontext vor Aktionen laden kann (z.B. Episode Memory vor Answer Generation).

**Acceptance Criteria:**

**Given** der MCP Server läuft und Daten existieren
**When** Claude Code MCP Resources abruft
**Then** sind folgende Resources verfügbar:

1. **`memory://l2-insights?query={q}&top_k={k}`**
   - Gibt Top-K L2 Insights für Query zurück
   - Response: JSON mit [{ id, content, score, source_ids }]

2. **`memory://working-memory`**
   - Gibt alle aktuellen Working Memory Items zurück
   - Sortiert nach last_accessed (neueste zuerst)

3. **`memory://episode-memory?query={q}&min_similarity={t}`**
   - Gibt ähnliche vergangene Episodes zurück
   - Default: min_similarity=0.70, top_k=3 (FR009)
   - Response: [{ id, query, reward, reflection, similarity }]

4. **`memory://l0-raw?session_id={id}&date_range={r}`**
   - Gibt Raw Dialogtranskripte für Session/Zeitraum zurück
   - Optional: date_range im Format "2024-01-01:2024-01-31"

5. **`memory://stale-memory?importance_min={t}`**
   - Gibt archivierte Items zurück (optional gefiltert nach Importance)

**Prerequisites:** Stories 1.4-1.8 (alle Tools implementiert)

**Technical Notes:**

- MCP Resources sind Read-Only (keine Mutations)
- URI-Schema: `memory://` Prefix für alle Cognitive Memory Resources
- Query-Parameter werden aus URI geparst
- Response-Format: JSON (MCP Standard)
- Error Handling: 404 wenn Query keine Ergebnisse liefert

---

### Story 1.10: Ground Truth Collection UI (Streamlit App)

**Als** ethr,
**möchte ich** eine dedizierte UI zum Labeln von Queries haben,
**sodass** ich effizient 50-100 Ground Truth Queries erstellen kann.

**Acceptance Criteria:**

**Given** L0 Raw Memory enthält Dialogtranskripte
**When** ich die Streamlit App starte
**Then** sehe ich folgende Features:

1. **Automatic Query Extraction:**
   - App extrahiert Queries aus L0 Raw Memory
   - Stratified Sampling: 40% Short (1-2 Sätze), 40% Medium (3-5), 20% Long (6+)
   - Temporal Diversity: 3-5 Queries pro Session (verhindert Bias)

2. **Labeling Interface:**
   - Zeige Query + Top-5 Retrieved Documents (via `hybrid_search`)
   - Binäre Entscheidung pro Dokument: "Relevant?" (Ja/Nein)
   - Keyboard Shortcuts: "y" = Ja, "n" = Nein, "s" = Skip Query

3. **Progress Tracking:**
   - Progress Bar: "68/100 Queries gelabelt"
   - Zeige aktuelle Stratification Balance (% Short/Medium/Long)
   - "Save & Continue Later"-Option

**And** Ground Truth wird in PostgreSQL gespeichert:

- Tabelle: `ground_truth` (id, query, expected_docs, created_at)
- expected_docs: Array von L2 Insight IDs die als "Relevant" markiert wurden

**Prerequisites:** Story 1.6 (Hybrid Search funktioniert)

**Technical Notes:**

- Streamlit: `pip install streamlit`
- Run: `streamlit run ground_truth_app.py`
- Query Extraction: SQL Query auf `l0_raw` mit LENGTH()-Filter für Stratification
- Session Sampling: `SELECT DISTINCT session_id, COUNT(*) ... HAVING COUNT(*) BETWEEN 3 AND 5`
- Keyboard Shortcuts: `streamlit.session_state` für State Management

---

### Story 1.11: Dual Judge Implementation mit GPT-4o + Haiku (MCP Tool: store_dual_judge_scores)

**Als** MCP Server,
**möchte ich** echte unabhängige Dual Judges (GPT-4o + Haiku) für IRR Validation nutzen,
**sodass** methodisch valides Ground Truth mit Cohen's Kappa >0.70 entsteht.

**Acceptance Criteria:**

**Given** Ground Truth Queries sind gelabelt (Story 1.10)
**When** das Tool `store_dual_judge_scores` aufgerufen wird für eine Query
**Then** werden beide Judges parallel aufgerufen:

1. **GPT-4o Judge (OpenAI API):**
   - Model: `gpt-4o`
   - Prompt: "Rate relevance of document for query (0.0-1.0)"
   - Response: Float Score pro Dokument

2. **Haiku Judge (Anthropic API):**
   - Model: `claude-3-5-haiku-20241022`
   - Gleicher Prompt wie GPT-4o
   - Response: Float Score pro Dokument

**And** Scores werden in `ground_truth` gespeichert:

- Neue Columns: `judge1_score`, `judge2_score`, `judge1_model`, `judge2_model`
- Binary Conversion: Score >0.5 = Relevant (1), Score ≤0.5 = Not Relevant (0)

**And** Cohen's Kappa wird berechnet:

- Kappa Formula: `(P_o - P_e) / (1 - P_e)`
- P_o: Observed Agreement (% Übereinstimmung)
- P_e: Expected Agreement by Chance
- Kappa gespeichert in `ground_truth.kappa` Column

**Prerequisites:** Story 1.10 (Ground Truth UI)

**Technical Notes:**

- Parallel API Calls: asyncio für GPT-4o + Haiku (2x Latency Reduction)
- Cost: €0.0023 per Query (€0.23 für 100 Queries)
- Kappa-Interpretation: <0.40=Poor, 0.40-0.59=Fair, 0.60-0.74=Good, >0.75=Excellent
- API Retry: Exponential Backoff bei Rate Limits
- Judge Provenance: Wichtig für Transparency (NFR005)

---

### Story 1.12: IRR Validation & Contingency Plan (Enhancement E1)

**Als** Entwickler,
**möchte ich** Cohen's Kappa über alle Ground Truth Queries validieren,
**sodass** ich sicherstelle dass IRR >0.70 ist (methodisch valide) und bei Bedarf Contingency Plan aktiviere.

**Acceptance Criteria:**

**Given** alle 50-100 Queries haben Dual Judge Scores
**When** ich die IRR Validation durchführe
**Then** wird Global Kappa berechnet:

- Aggregiere alle judge1_score vs judge2_score über alle Queries
- Berechne Macro-Average Kappa (Durchschnitt aller Query-Kappas)
- Berechne Micro-Average Kappa (alle Dokumente als einzelne Predictions)

**And** falls Kappa ≥0.70:

- Success-Message: "IRR Validation Passed (Kappa: X.XX)"
- Ground Truth ist ready für Hybrid Calibration (Epic 2)

**And** falls Kappa <0.70 → Contingency Plan aktiviert:

1. **Human Tiebreaker:**
   - Zeige Queries mit größter Judge-Disagreement (|score1 - score2| >0.4)
   - ethr entscheidet manuell (Streamlit UI)
   - Mindestens 20% der Queries mit Disagreement reviewen

2. **Wilcoxon Signed-Rank Test:**
   - Teste ob systematischer Bias zwischen Judges existiert
   - Falls ja: Kalibriere Threshold (z.B. GPT-4o threshold=0.55 statt 0.5)

3. **Judge Recalibration:**
   - Passe Prompts an (explizitere Relevanzkriterien)
   - Wiederhole Labeling für Low-Kappa Queries

**Prerequisites:** Story 1.11 (Dual Judge Implementation)

**Technical Notes:**

- Kappa-Berechnung: scipy.stats oder sklearn.metrics.cohen_kappa_score
- Disagreement Threshold: |score1 - score2| >0.4 (40% Unterschied)
- Wilcoxon Test: `scipy.stats.wilcoxon(judge1_scores, judge2_scores)`
- Recalibration: Nur falls Wilcoxon p-value <0.05 (signifikanter Bias)
- Dokumentation: Alle Contingency Actions loggen für Transparency

---

## Epic 2: RAG Pipeline & Hybrid Calibration

**Epic Goal:** Implementiere die vollständige RAG-Pipeline mit Claude Code als primärem LLM (Query Expansion, CoT Generation intern) und externen APIs für kritische Evaluationen (Haiku für Reflexion/Evaluation). Kalibriere Hybrid Search Gewichte via Grid Search auf Ground Truth Set für domänenspezifische Optimierung (Precision@5 >0.75).

**Business Value:** Ermöglicht kontextreiche Konversationen mit persistentem Memory (€0/mo für Bulk-Operationen) und konsistenter Qualitätssicherung (€1-2/mo für Evaluationen). Hybrid Calibration liefert +5-10% Precision@5 Uplift gegenüber MEDRAG-Default.

**Timeline:** 35-45 Stunden (Phase 2)
**Budget:** €1-2/mo (Development + Testing)

---

### Story 2.1: Claude Code MCP Client Setup & Integration Testing

**Als** Entwickler,
**möchte ich** Claude Code als MCP Client konfigurieren und Verbindung zum MCP Server testen,
**sodass** Claude Code alle MCP Tools und Resources nutzen kann.

**Acceptance Criteria:**

**Given** der MCP Server läuft lokal (Epic 1 abgeschlossen)
**When** ich Claude Code MCP Settings konfiguriere
**Then** ist die Integration funktional:

- MCP Server in `~/.config/claude-code/mcp-settings.json` registriert
- Claude Code zeigt verfügbare Tools (7 Tools) in Tool-Liste
- Claude Code zeigt verfügbare Resources (5 Resources)
- Test-Tool-Call erfolgreich: `ping` → "pong" Response

**And** alle 7 MCP Tools sind aufrufbar:

- `store_raw_dialogue` - L0 Storage Test
- `compress_to_l2_insight` - L2 Storage Test (mit Dummy Embedding)
- `hybrid_search` - Retrieval Test (mit vorhandenen L2 Insights)
- `update_working_memory` - Working Memory Test
- `store_episode` - Episode Storage Test
- `get_golden_test_results` - Dummy Response (wird in Epic 3 implementiert)
- `store_dual_judge_scores` - Bereits funktional aus Epic 1

**And** alle 5 MCP Resources sind lesbar:

- `memory://l2-insights?query=test&top_k=5`
- `memory://working-memory`
- `memory://episode-memory?query=test&min_similarity=0.7`
- `memory://l0-raw?session_id={test-session}`
- `memory://stale-memory`

**Prerequisites:** Epic 1 abgeschlossen (alle Tools/Resources implementiert)

**Technical Notes:**

- MCP Settings: JSON-Format mit server path, args, env vars
- Transport: stdio (Standard für lokale Server)
- Testing: Manuelles Testen in Claude Code Interface (keine automatisierten Tests erforderlich)
- Troubleshooting: MCP Inspector für Debugging bei Connection-Issues

---

### Story 2.2: Query Expansion Logik (intern in Claude Code)

**Als** Claude Code,
**möchte ich** User-Queries intern in 3 semantische Varianten reformulieren,
**sodass** robuste Retrieval mit +10-15% Recall Uplift möglich ist (ohne externe API-Kosten).

**Acceptance Criteria:**

**Given** eine User-Query wird gestellt
**When** Query Expansion durchgeführt wird
**Then** werden 3 Varianten generiert:

- **Original Query:** Unveränderte User-Frage
- **Variante 1:** Paraphrase (andere Wortwahl, gleiche Bedeutung)
- **Variante 2:** Perspektiv-Shift (z.B. "Was denke ich..." → "Meine Meinung zu...")
- **Variante 3:** Keyword-Fokus (extrahiere Kern-Konzepte)

**And** alle 4 Queries (Original + 3 Varianten) werden für Retrieval genutzt:

- Jede Query wird embedded (OpenAI API)
- Jede Query wird an `hybrid_search` Tool geschickt
- Ergebnisse werden merged (dedupliziert nach L2 ID)
- Finale Top-5 Dokumente via RRF Fusion

**And** Expansion-Strategie ist konfigurierbar:

- Default: 3 Varianten (Balance zwischen Recall und Token-Cost)
- Optional: 2 Varianten (Low-Budget Mode)
- Optional: 5 Varianten (High-Recall Mode)

**Prerequisites:** Story 2.1 (Claude Code kann MCP Server aufrufen)

**Technical Notes:**

- Expansion in Claude Code: Interner Reasoning-Schritt (kein separater API-Call)
- Cost-Savings: €0 vs. €0.50 per Query (hätte Haiku API gebraucht)
- Token-Cost: ~200 Tokens für Expansion (vernachlässigbar in Claude MAX)
- Deduplication: Set von L2 IDs vor finaler RRF Fusion
- Latency: +0.5-1s für Expansion (akzeptabel in 5s Budget)

---

### Story 2.3: Chain-of-Thought (CoT) Generation Framework

**Als** Claude Code,
**möchte ich** Antworten mit explizitem Reasoning (CoT: Thought → Reasoning → Answer → Confidence) generieren,
**sodass** Transparenz und Nachvollziehbarkeit gewährleistet sind.

**Acceptance Criteria:**

**Given** Retrieved Context (Top-5 Dokumente) und Episode Memory (falls vorhanden)
**When** Answer Generation durchgeführt wird
**Then** wird CoT-Struktur generiert:

1. **Thought:** Erste Intuition/Hypothese zur Antwort (1-2 Sätze)
2. **Reasoning:** Explizite Begründung basierend auf Retrieved Docs + Episodes (3-5 Sätze)
3. **Answer:** Finale Antwort an User (klar, präzise, direkt)
4. **Confidence:** Score 0.0-1.0 basierend auf Retrieval-Quality

**And** CoT wird strukturiert ausgegeben:

- User sieht: Answer + Confidence + Quellen (L2 IDs)
- Optional: Thought + Reasoning expandierbar (Power-User Feature)
- Logging: Kompletter CoT in PostgreSQL für Episode Memory

**And** Confidence-Berechnung ist implementiert:

- Hohe Confidence (>0.8): Top-1 Retrieval Score >0.85, mehrere Docs übereinstimmend
- Medium Confidence (0.5-0.8): Top-1 Score 0.7-0.85, einzelnes Dokument relevant
- Low Confidence (<0.5): Alle Scores <0.7, inkonsistente oder fehlende Docs

**Prerequisites:** Story 2.2 (Query Expansion + Retrieval funktioniert)

**Technical Notes:**

- CoT-Format: Strukturiertes Markdown für Readability
- Native JSON Support: Claude Code hat kein Parsing-Problem (>99.9% Success Rate)
- Cost-Savings: €0 vs. €0.50 per Query (hätte Opus API gebraucht)
- Transparency (NFR005): CoT erfüllt UX1 (Transparenz über Blackbox)

---

### Story 2.4: External API Setup für Haiku (Evaluation + Reflexion)

**Als** MCP Server,
**möchte ich** Anthropic Haiku API für Evaluation und Reflexion nutzen,
**sodass** konsistente Episode Memory Quality über Sessions garantiert ist.

**Acceptance Criteria:**

**Given** Anthropic API-Key ist konfiguriert (.env)
**When** MCP Server Haiku API aufruft
**Then** ist die Integration funktional:

- API-Client initialisiert (`anthropic` Python SDK)
- Model: `claude-3-5-haiku-20241022`
- Temperature: 0.7 (für Reflexion), 0.0 (für Evaluation)
- Max Tokens: 500 (Evaluation), 1000 (Reflexion)

**And** Retry-Logic ist implementiert:

- Exponential Backoff: 1s, 2s, 4s, 8s bei Rate-Limit
- Max Retries: 4 Versuche
- Fallback bei totaler API-Ausfall: Claude Code Evaluation (degraded mode)

**And** Cost-Tracking ist implementiert:

- Log jeder API-Call mit Token-Count
- Daily/Monthly Aggregation in PostgreSQL
- Alert bei >€10/mo Budget-Überschreitung

**Prerequisites:** Story 1.3 (MCP Server Framework vorhanden)

**Technical Notes:**

- Anthropic SDK: `pip install anthropic`
- API-Key: `.env` mit `ANTHROPIC_API_KEY=...`
- Cost: €0.001 per Evaluation, €0.0015 per Reflexion
- Fallback: Claude Code kann notfalls Evaluation übernehmen (aber weniger konsistent)
- Budget-Monitoring: Wichtig für NFR003 (€5-10/mo Budget)

---

### Story 2.5: Self-Evaluation mit Haiku API

**Als** MCP Server,
**möchte ich** generierte Antworten via Haiku API evaluieren (Reward -1.0 bis +1.0),
**sodass** objektive Quality-Scores für Episode Memory vorhanden sind.

**Acceptance Criteria:**

**Given** eine Antwort wurde via CoT generiert (Story 2.3)
**When** Self-Evaluation durchgeführt wird
**Then** ruft MCP Server Haiku API auf:

- Prompt: "Evaluate answer quality for query. Consider: Relevance, Accuracy, Completeness. Return score -1.0 to +1.0."
- Input: Query + Retrieved Context + Generated Answer
- Output: Float Score (-1.0 = schlechte Antwort, +1.0 = exzellent)

**And** Evaluation-Kriterien sind explizit:

- **Relevance:** Beantwortet die Antwort die Query?
- **Accuracy:** Basiert die Antwort auf Retrieved Context (keine Halluzinationen)?
- **Completeness:** Ist die Antwort vollständig oder fehlen wichtige Aspekte?

**And** Reward-Score wird zurückgegeben:

- Response enthält: Reward (float), Reasoning (Haiku's Begründung)
- Logging: Reward + Reasoning in PostgreSQL (für Transparenz)
- Falls Reward <0.3: Trigger Reflexion (Story 2.6)

**Prerequisites:** Story 2.4 (Haiku API Setup)

**Technical Notes:**

- Temperature: 0.0 (deterministisch für konsistente Scores)
- Prompt Engineering: Klare Kriterien → höhere IRR über Sessions
- Cost: €0.001 per Evaluation (~1000 Evaluations = €1/mo bei daily usage)
- Rationale (FR007): Externe Evaluation konsistenter als Claude Code Session-State

---

### Story 2.6: Reflexion-Framework mit Verbal Reinforcement Learning

**Als** MCP Server,
**möchte ich** bei schlechten Antworten (Reward <0.3) Reflexionen via Haiku API generieren,
**sodass** verbalisierte Lektionen in Episode Memory gespeichert werden.

**Acceptance Criteria:**

**Given** Self-Evaluation ergab Reward <0.3 (schlechte Antwort)
**When** Reflexion getriggert wird
**Then** ruft MCP Server Haiku API auf:

- Prompt: "Reflect on why this answer was poor. What went wrong? What should be done differently in the future?"
- Input: Query + Retrieved Context + Generated Answer + Evaluation Reasoning
- Output: Verbalisierte Reflexion (2-3 Sätze)

**And** Reflexion folgt strukturiertem Format:

- **Problem:** Was lief schief? (z.B. "Retrieved context was irrelevant", "Answer hallucinated facts")
- **Lesson:** Was tun in Zukunft? (z.B. "Request more specific queries", "Acknowledge low confidence explicitly")

**And** Reflexion wird in Episode Memory gespeichert:

- MCP Tool: `store_episode` wird aufgerufen
- Parameter: query, reward, reflection
- Embedding: Query wird embedded für spätere Similarity-Suche (FR009)

**And** Reflexion ist abrufbar bei ähnlichen Queries:

- Vor Answer Generation: Read `memory://episode-memory` Resource
- Falls ähnliche Episode existiert (Cosine Similarity >0.70): Lade Lesson Learned
- Integriere Lesson in CoT Reasoning ("Past experience suggests...")

**Prerequisites:** Story 2.5 (Evaluation funktioniert)

**Technical Notes:**

- Temperature: 0.7 (kreativ für Reflexion)
- Trigger-Threshold: Reward <0.3 (ca. 30% aller Queries bei Bootstrapping)
- Cost: €0.0015 per Reflexion (~300 Reflexionen/mo = €0.45/mo)
- Verbal RL: Bessere Interpretability als Numerical Rewards (NFR005 Transparency)
- Retrieval-Parameter: Top-3 Episodes, min_similarity=0.70 (FR009)

---

### Story 2.7: End-to-End RAG Pipeline Testing

**Als** Entwickler,
**möchte ich** die komplette RAG-Pipeline end-to-end testen,
**sodass** alle Komponenten korrekt zusammenspielen (Query → Retrieval → Generation → Evaluation → Reflexion).

**Acceptance Criteria:**

**Given** MCP Server läuft und Claude Code ist konfiguriert
**When** ich eine Test-Query stelle
**Then** durchläuft das System alle Pipeline-Schritte:

1. **Query Expansion:** 3 Varianten generiert (Story 2.2)
2. **Embedding:** 4 Queries embedded via OpenAI API
3. **Hybrid Search:** 4x `hybrid_search` Tool-Call, RRF Fusion
4. **Episode Memory Check:** `memory://episode-memory` gelesen (falls ähnliche Episodes)
5. **CoT Generation:** Thought → Reasoning → Answer → Confidence (Story 2.3)
6. **Self-Evaluation:** Haiku API Evaluation (Story 2.5)
7. **Reflexion (conditional):** Falls Reward <0.3 → Haiku Reflexion (Story 2.6)
8. **Working Memory Update:** `update_working_memory` Tool-Call
9. **User Response:** Answer + Confidence + Sources angezeigt

**And** Performance-Metriken werden gemessen:

- **End-to-End Latency:** <5s (p95, NFR001)
- **Retrieval Time:** <1s (Hybrid Search)
- **CoT Generation:** ~2-3s
- **Evaluation:** ~0.5s (Haiku API)
- **Reflexion (falls getriggert):** ~1s

**And** Test-Queries decken verschiedene Szenarien ab:

- **High Confidence:** Query mit klarem Match in L2 Insights
- **Medium Confidence:** Ambigue Query mit mehreren möglichen Docs
- **Low Confidence:** Query ohne passende Dokumente (triggert Reflexion)

**Prerequisites:** Stories 2.1-2.6 (alle Pipeline-Komponenten implementiert)

**Technical Notes:**

- Testing: Manuell in Claude Code (keine automatisierten Tests)
- Logging: Alle Pipeline-Schritte in PostgreSQL für Post-Mortem Analysis
- Performance-Target: <5s ist realistisch (CoT + Evaluation zusammen ~3-4s)
- Reflexion-Trigger-Rate: Erwartet 20-30% bei Bootstrapping, sinkt über Zeit

---

### Story 2.8: Hybrid Weight Calibration via Grid Search

**Als** Entwickler,
**möchte ich** optimale Hybrid Search Gewichte (Semantic vs. Keyword) via Grid Search finden,
**sodass** Precision@5 >0.75 auf Ground Truth Set erreicht wird.

**Acceptance Criteria:**

**Given** Ground Truth Set (50-100 gelabelte Queries) existiert (Epic 1)
**When** Grid Search durchgeführt wird
**Then** werden verschiedene Gewichts-Kombinationen getestet:

- **Grid:** semantic={0.5, 0.6, 0.7, 0.8, 0.9}, keyword={0.5, 0.4, 0.3, 0.2, 0.1}
- **Constraint:** semantic + keyword = 1.0
- **Queries:** Alle 50-100 Ground Truth Queries
- **Metric:** Precision@5 (% relevanter Docs in Top-5)

**And** für jede Gewichts-Kombination:

- Führe `hybrid_search` für alle Queries aus
- Vergleiche Top-5 Ergebnisse mit expected_docs aus Ground Truth
- Berechne Precision@5 = (Anzahl relevanter Docs in Top-5) / 5

**And** beste Gewichte werden identifiziert:

- **Erwartung:** semantic=0.8, keyword=0.2 (psychologische Dialoge sind semantisch-heavy)
- **Baseline:** semantic=0.7, keyword=0.3 (MEDRAG-Default)
- **Target:** +5-10% Precision@5 Uplift über Baseline

**And** Kalibrierte Gewichte werden in config.yaml gespeichert:

- `hybrid_search_weights.semantic: 0.8`
- `hybrid_search_weights.keyword: 0.2`
- MCP Server lädt Gewichte beim Start

**Prerequisites:** Story 2.7 (RAG Pipeline funktioniert end-to-end)

**Technical Notes:**

- Grid Search: Einfache Nested Loops (keine ML-Optimierung nötig)
- Runtime: ~10-20 Minuten für 100 Queries x 5 Gewichts-Kombinationen
- Precision@5 Formula: `sum(1 for doc in top5 if doc in expected_docs) / 5`
- Statistical Robustness: 50-100 Queries → ausreichend für valide Metrik (NFR002)
- Dokumentation: Grid Search Results in `/docs/calibration-results.md`

---

### Story 2.9: Precision@5 Validation auf Ground Truth Set

**Als** Entwickler,
**möchte ich** finales Precision@5 nach Calibration validieren,
**sodass** ich sicherstelle dass NFR002 (Precision@5 >0.75) erfüllt ist.

**Acceptance Criteria:**

**Given** Hybrid Gewichte sind kalibriert (Story 2.8)
**When** ich Precision@5 auf komplettem Ground Truth Set messe
**Then** wird finale Metrik berechnet:

- Führe `hybrid_search` für alle 50-100 Queries aus (mit kalibrierten Gewichten)
- Vergleiche Top-5 Ergebnisse mit expected_docs
- Berechne Macro-Average Precision@5 (Durchschnitt über alle Queries)

**And** Success-Kriterien werden geprüft:

- **✅ Full Success:** Precision@5 ≥0.75 → System ready for production
- **⚠️ Partial Success:** Precision@5 0.70-0.74 → Deploy with monitoring, iterate on calibration
- **❌ Failure:** Precision@5 <0.70 → Requires architecture review or additional ground truth

**And** bei Full Success:

- Dokumentiere finale Metrik in `/docs/evaluation-results.md`
- Mark Epic 2 als abgeschlossen
- Transition zu Epic 3 (Production Readiness)

**And** bei Partial Success:

- Deploy System in Production (mit Monitoring)
- Continue Data Collection (mehr L2 Insights)
- Re-run Calibration nach 2 Wochen mit erweiterten Daten

**And** bei Failure:

- Analyse: Welche Query-Typen scheitern? (Short vs. Medium vs. Long)
- Optionen: (1) Mehr Ground Truth Queries sammeln, (2) Embedding-Modell wechseln, (3) L2 Compression Quality verbessern

**Prerequisites:** Story 2.8 (Calibration abgeschlossen)

**Technical Notes:**

- Graduated Success Criteria: Ermöglicht adaptive Steuerung (siehe PRD Phase 2 Success Criteria)
- Precision@5 >0.75: Höher als v2.4.1 (>0.70) dank text-embedding-3-small
- Monitoring: Falls Partial Success → täglich Precision@5 tracken (Epic 3)
- Re-Calibration: Bei Domain Shift (mehr philosophische vs. technische Dialoge)

---

## Epic 3: Working Memory, Evaluation & Production Readiness

**Epic Goal:** Bringe das System in Production-Ready State durch robuste Monitoring-Infrastruktur (Golden Test Set, Model Drift Detection), API-Ausfallsicherheit (Retry-Logic + Fallbacks), Budget-Optimierung (Staged Dual Judge) und 7-Tage Stability Testing. Ziel: €5-10/mo Budget, <5s Latency, keine kritischen Data Loss-Szenarien.

**Business Value:** Ermöglicht kontinuierlichen Production-Betrieb mit automatischer Qualitätssicherung, Budget-Monitoring und Früherkennung von Model Drift. Staged Dual Judge reduziert Kosten nach 3 Monaten von €5-10/mo auf €2-3/mo (-40%).

**Timeline:** 60-80 Stunden (Phase 3: 25-35h, Phase 4: 20-25h, Phase 5: 15-20h)
**Budget:** €5-10/mo (Production), dann €2-3/mo (nach Staged Dual Judge)

---

### Story 3.1: Golden Test Set Creation (separate von Ground Truth)

**Als** Entwickler,
**möchte ich** ein separates Golden Test Set (50-100 Queries) erstellen,
**sodass** ich tägliche Precision@5 Regression-Tests durchführen kann ohne Ground Truth zu kontaminieren.

**Acceptance Criteria:**

**Given** L0 Raw Memory und L2 Insights existieren
**When** ich Golden Test Set erstelle
**Then** werden 50-100 Queries extrahiert:

- **Source:** Automatisch aus L0 Raw Memory (unterschiedliche Sessions als Ground Truth)
- **Stratification:** 40% Short, 40% Medium, 20% Long (gleich wie Ground Truth)
- **Temporal Diversity:** Keine Überlappung mit Ground Truth Sessions
- **Labeling:** Manuelle Relevanz-Labels via Streamlit UI (gleiche UI wie Ground Truth, Story 1.10)

**And** Golden Test Set wird in separater Tabelle gespeichert:

- Tabelle: `golden_test_set` (id, query, expected_docs, created_at, query_type)
- Keine judge_scores (da kein Dual Judge für Golden Set - nur User-Labels)
- query_type: "short" | "medium" | "long" für Stratification-Tracking

**And** Golden Set ist immutable nach Erstellung:

- Keine Updates nach Initial Labeling (fixed Baseline für Drift Detection)
- Separates Set verhindert Overfitting auf Ground Truth
- Expected Size: 50-100 Queries (statistical power >0.80 für Precision@5 bei alpha=0.05)

**Prerequisites:** Epic 2 abgeschlossen (Calibration erfolgt, System funktioniert)

**Technical Notes:**

- Wiederverwendung Streamlit UI aus Story 1.10 (gleicher Code, andere Tabelle)
- Session Sampling: Wähle Sessions die NICHT in Ground Truth sind
- Rationale: Separate Test Set verhindert "teaching to the test"
- Cost: €1/mo für Expanded Golden Set (bereits in PRD Budget eingeplant)

---

### Story 3.2: Model Drift Detection mit Daily Golden Test (MCP Tool: get_golden_test_results)

**Als** MCP Server,
**möchte ich** täglich das Golden Test Set ausführen und Precision@5 tracken,
**sodass** API-Änderungen (Embedding-Modell Updates, Haiku API Drift) frühzeitig erkannt werden.

**Acceptance Criteria:**

**Given** Golden Test Set existiert (Story 3.1)
**When** das Tool `get_golden_test_results` aufgerufen wird (täglich via Cron)
**Then** werden alle Golden Queries getestet:

- Führe `hybrid_search` für alle 50-100 Queries aus (mit kalibrierten Gewichten)
- Vergleiche Top-5 Ergebnisse mit expected_docs
- Berechne Precision@5 für jede Query
- Aggregiere zu Daily Precision@5 Metric

**And** Metrics werden in `model_drift_log` Tabelle gespeichert:

- Columns: date, precision_at_5, num_queries, avg_retrieval_time, embedding_model_version
- Neue Zeile pro Tag (historische Tracking)
- embedding_model_version: OpenAI API Header für Versionierung

**And** Drift Detection Alert wird getriggert:

- **Condition:** Precision@5 drop >5% gegenüber Rolling 7-Day Average
- **Action:** Log Warning in PostgreSQL + optional Email/Slack Alert (konfigurierbar)
- **Example:** Baseline P@5=0.78, Current P@5=0.73 → Alert (5% drop = 0.05)

**And** das Tool gibt tägliche Metriken zurück:

- Response: {date, precision_at_5, drift_detected: boolean, baseline_p5, current_p5}
- Ermöglicht Claude Code Queries wie "Zeige mir Model Drift Trends letzte 30 Tage"

**Prerequisites:** Story 3.1 (Golden Test Set vorhanden)

**Technical Notes:**

- Cron Job: `0 2 * * *` (täglich 2 Uhr nachts, low-traffic Zeit)
- Rolling Average: 7-Day Window für Noise Reduction
- embedding_model_version: OpenAI Response Header `x-model-version` (falls verfügbar)
- Alert-Mechanismus: Start mit simple PostgreSQL Log, später Email/Slack (out of scope v3.1)
- Enhancement E7: Model Drift Detection aus PRD

---

### Story 3.3: API Retry-Logic Enhancement mit Exponential Backoff

**Als** MCP Server,
**möchte ich** robuste Retry-Logic für alle externen APIs (OpenAI, Anthropic) haben,
**sodass** transiente Fehler (Rate Limits, Network Glitches) automatisch recovered werden.

**Acceptance Criteria:**

**Given** ein External API Call schlägt fehl
**When** Retry-Logic getriggert wird
**Then** wird Exponential Backoff ausgeführt:

- **Delays:** 1s, 2s, 4s, 8s (4 Retries total)
- **Jitter:** ±20% Random Delay (verhindert Thundering Herd)
- **Total Max Time:** ~15s (1+2+4+8 = 15s max wait)

**And** Retry-Logic ist für alle API-Typen implementiert:

1. **OpenAI Embeddings API:**
   - Retry bei: Rate Limit (429), Service Unavailable (503), Timeout
   - Nach 4 Failed Retries: Error zurückgeben an Claude Code

2. **Anthropic Haiku API (Evaluation):**
   - Retry bei: Rate Limit, Service Unavailable, Timeout
   - Nach 4 Failed Retries: **Fallback zu Claude Code Evaluation** (degraded mode)

3. **Anthropic Haiku API (Reflexion):**
   - Retry bei: Rate Limit, Service Unavailable
   - Nach 4 Failed Retries: Skip Reflexion (not critical, kann später nachgeholt werden)

4. **GPT-4o + Haiku Dual Judge:**
   - Retry bei: Rate Limit, Service Unavailable
   - Nach 4 Failed Retries: Log Error (Ground Truth Collection kann manuell wiederholt werden)

**And** Retry-Statistiken werden geloggt:

- Tabelle: `api_retry_log` (timestamp, api_name, error_type, retry_count, success)
- Ermöglicht Analyse: Welche APIs sind instabil? Wie oft triggern Retries?

**Prerequisites:** Story 2.4 (Haiku API Setup mit basischer Retry-Logic)

**Technical Notes:**

- Exponential Backoff: `delay = base_delay * (2 ** retry_count) * (1 + jitter)`
- Jitter: `random.uniform(0.8, 1.2)` für ±20% Randomness
- Fallback-Strategie: Nur für Evaluation (Haiku → Claude Code), nicht für Embeddings
- HTTP Status Codes: 429 (Rate Limit), 503 (Service Unavailable), 408/504 (Timeout)
- Enhancement: Erweitert basische Retry-Logic aus Story 2.4

---

### Story 3.4: Claude Code Fallback für Haiku API Ausfall (Degraded Mode)

**Als** MCP Server,
**möchte ich** bei totalem Haiku API Ausfall auf Claude Code Evaluation zurückfallen,
**sodass** das System weiterhin funktioniert (wenn auch mit leicht reduzierter Konsistenz).

**Acceptance Criteria:**

**Given** Haiku API ist nach 4 Retries nicht erreichbar
**When** Fallback zu Claude Code getriggert wird
**Then** wird alternative Evaluation durchgeführt:

- **Fallback-Modus:** Claude Code führt Self-Evaluation intern durch
- **Prompt:** Gleiche Evaluation-Kriterien wie Haiku (Relevance, Accuracy, Completeness)
- **Output:** Reward Score -1.0 bis +1.0 (gleiche Skala)

**And** Fallback-Status wird geloggt:

- Log Entry in PostgreSQL: `fallback_mode_active: true`, `reason: "haiku_api_unavailable"`
- Warning-Message an User: "System running in degraded mode (Haiku API unavailable)"
- Timestamp: Wann Fallback aktiviert, wann deaktiviert

**And** automatische Recovery nach API-Wiederherstellung:

- Periodic Health Check: Alle 15 Minuten Haiku API Ping (lightweight Test)
- Falls Ping erfolgreich: Deaktiviere Fallback, log Recovery
- Keine manuelle Intervention erforderlich

**And** Fallback-Quality wird dokumentiert:

- Erwartung: Claude Code Evaluation ~5-10% weniger konsistent als Haiku (Session-State Variabilität)
- Trade-off: Verfügbarkeit > perfekte Konsistenz (99% Uptime wichtiger als 100% Score-Konsistenz)

**Prerequisites:** Story 3.3 (Retry-Logic mit Fallback-Trigger)

**Technical Notes:**

- Health Check: `GET /health` Endpoint bei Haiku API (wenn verfügbar), sonst minimaler Inference Call
- Degraded Mode: Nur für Evaluation, NICHT für Embeddings (OpenAI hat keine Fallback-Option)
- Session-State Issue: Claude Code Evaluation kann zwischen Sessions variieren (daher Haiku bevorzugt)
- Probability: Haiku API Ausfall ~1-2%/Jahr → Fallback selten getriggert
- NFR004: Reliability & Robustness

---

### Story 3.5: Latency Benchmarking & Performance Optimization

**Als** Entwickler,
**möchte ich** End-to-End Latency systematisch messen und optimieren,
**sodass** NFR001 (Query Response Time <5s p95) garantiert erfüllt ist.

**Acceptance Criteria:**

**Given** das System läuft mit realistischen Daten (Epic 2 abgeschlossen)
**When** Latency Benchmarking durchgeführt wird
**Then** werden 100 Test-Queries gemessen:

- **Query Mix:** 40 Short, 40 Medium, 20 Long (stratified wie Golden Set)
- **Measured Metrics:**
  - End-to-End Latency (User Query → Final Answer)
  - Breakdown: Query Expansion Time, Embedding Time, Hybrid Search Time, CoT Generation Time, Evaluation Time
  - Percentiles: p50, p95, p99

**And** Performance-Ziele werden validiert:

- **p95 End-to-End Latency:** <5s (NFR001)
- **p95 Retrieval Time:** <1s (Hybrid Search)
- **p50 End-to-End Latency:** <3s (erwarteter Median)

**And** bei Performance-Problemen → Optimierung:

1. **Falls Hybrid Search >1s p95:**
   - Prüfe pgvector IVFFlat Index (lists=100 optimal?)
   - Erwäge HNSW Index (schneller, aber mehr Memory)

2. **Falls CoT Generation >3s p95:**
   - Kürze Retrieved Context (Top-3 statt Top-5?)
   - Optimize Prompt Length

3. **Falls Evaluation >1s p95:**
   - Prüfe Haiku API Latency (ist API langsam oder Network?)
   - Erwäge Batch Evaluation (mehrere Queries parallel)

**And** Latency-Metriken werden dokumentiert:

- Dokumentation: `/docs/performance-benchmarks.md`
- Baseline für zukünftige Performance-Regression Tests

**Prerequisites:** Epic 2 abgeschlossen (RAG Pipeline funktioniert)

**Technical Notes:**

- Benchmarking Tool: Python Script mit `time.perf_counter()` für high-precision timing
- 100 Queries: Ausreichend für p95 Estimation (10+ Samples in Tail)
- pgvector Index: IVFFlat (lists=100) ist Default, HNSW erwägen bei Latency-Issues
- CoT Generation: Erwartet ~2-3s (längster Step in Pipeline)
- NFR001: <5s p95 ist akzeptabel für "Denkzeit" in philosophischen Gesprächen

---

### Story 3.6: PostgreSQL Backup Strategy Implementation

**Als** Entwickler,
**möchte ich** automatisierte PostgreSQL Backups mit 7-day Retention haben,
**sodass** catastrophic data loss verhindert wird (NFR004).

**Acceptance Criteria:**

**Given** PostgreSQL läuft mit Production-Daten
**When** Backup-Strategie implementiert wird
**Then** werden tägliche Backups erstellt:

- **Tool:** `pg_dump` (native PostgreSQL Backup)
- **Schedule:** Täglich 3 Uhr nachts via Cron (`0 3 * * *`)
- **Format:** Custom Format (`-Fc`, komprimiert, parallel restore möglich)
- **Target:** `/backups/postgres/cognitive_memory_YYYY-MM-DD.dump`

**And** Backup-Rotation mit 7-day Retention:

- Script löscht Backups älter als 7 Tage
- Keeps: Letzten 7 Tage (ausreichend für Recovery von Transient Issues)
- Disk Space: ~1-2 GB pro Backup (geschätzt für 10K L2 Insights + Embeddings)

**And** L2 Insights in Git als Read-Only Fallback:

- Täglicher Export: L2 Insights (Content + Metadata, OHNE Embeddings) → `/memory/l2-insights/YYYY-MM-DD.json`
- Git Commit + Push (optional, konfigurierbar)
- Rationale: Text ist klein, Embeddings können re-generated werden

**And** Recovery-Prozedur ist dokumentiert:

- RTO (Recovery Time Objective): <1 hour
- RPO (Recovery Point Objective): <24 hours
- Dokumentation: `/docs/backup-recovery.md` mit Step-by-Step Restore-Anleitung

**And** Backup-Success wird geloggt:

- Log Entry nach jedem Backup: timestamp, backup_size, success/failure
- Alert bei Backup-Failure (2 aufeinanderfolgende Failures)

**Prerequisites:** Story 1.2 (PostgreSQL Setup)

**Technical Notes:**

- pg_dump Command: `pg_dump -U mcp_user -Fc cognitive_memory > backup.dump`
- Restore Command: `pg_restore -U mcp_user -d cognitive_memory backup.dump`
- Backup Location: Lokales NAS oder `/backups/` Mount-Point
- Cloud Backup: Out of scope v3.1 (aber vorbereitet durch Git Export)
- NFR004: Backup Strategy aus PRD

---

### Story 3.7: Production Configuration & Environment Setup

**Als** Entwickler,
**möchte ich** Production-Environment von Development trennen,
**sodass** Testing keine Production-Daten kontaminiert und Secrets sicher verwaltet werden.

**Acceptance Criteria:**

**Given** Development-Environment funktioniert (Epic 1-2 abgeschlossen)
**When** Production-Environment erstellt wird
**Then** existieren separate Konfigurationen:

1. **Environment Files:**
   - `.env.development` (für Testing, lokale DB, Test API Keys)
   - `.env.production` (für Production, echte API Keys, Production DB)
   - `.env.template` (dokumentiert alle erforderlichen Variablen)

2. **Database Separation:**
   - Development DB: `cognitive_memory_dev` (separate PostgreSQL Database)
   - Production DB: `cognitive_memory` (original Database)
   - Keine Cross-Contamination zwischen Envs

3. **Configuration Management:**
   - `config.yaml` mit environment-specific Overrides
   - Environment Variable: `ENVIRONMENT=production|development`
   - MCP Server lädt Config basierend auf `ENVIRONMENT`

**And** Secrets Management:

- **API Keys:** Nur in .env Files (NICHT in Git)
- **DB Credentials:** Nur in .env Files
- `.gitignore` enthält: `.env.production`, `.env.development`
- Vault/SecretManager: Out of scope v3.1 (reicht für Personal Use)

**And** Production Checklist ist dokumentiert:

- `/docs/production-checklist.md`:
  - [ ] .env.production mit echten API Keys
  - [ ] PostgreSQL Backups aktiviert
  - [ ] Cron Jobs für Model Drift Detection + Backups
  - [ ] MCP Server in Claude Code konfiguriert
  - [ ] 7-Day Stability Test abgeschlossen

**Prerequisites:** Epic 2 abgeschlossen

**Technical Notes:**

- Environment Loading: `python-dotenv` Package (`load_dotenv('.env.production')`)
- Config Overrides: `config.yaml` hat `development:` und `production:` Sections
- Security: .env Files haben chmod 600 (nur Owner readable)
- Personal Use: Keine Multi-User Auth nötig (nur ethr nutzt System)

---

### Story 3.8: MCP Server Daemonization & Auto-Start

**Als** Entwickler,
**möchte ich** den MCP Server als Background-Prozess laufen lassen,
**sodass** er automatisch beim Boot startet und nach Crashes neu startet.

**Acceptance Criteria:**

**Given** Production-Environment ist konfiguriert (Story 3.7)
**When** MCP Server als Daemon konfiguriert wird
**Then** läuft der Server persistent:

1. **Systemd Service (Linux):**
   - Service File: `/etc/systemd/system/cognitive-memory-mcp.service`
   - ExecStart: `/path/to/venv/bin/python /path/to/mcp_server/main.py`
   - Restart: `always` (auto-restart bei Crashes)
   - User: `ethr` (läuft als Non-Root)

2. **Auto-Start bei Boot:**
   - `systemctl enable cognitive-memory-mcp.service`
   - Server startet automatisch nach System-Reboot

3. **Logging:**
   - stdout/stderr → systemd Journal (`journalctl -u cognitive-memory-mcp`)
   - Zusätzlich: Structured Logs in `/var/log/cognitive-memory/mcp.log`

**And** Service Management Commands:

- Start: `systemctl start cognitive-memory-mcp`
- Stop: `systemctl stop cognitive-memory-mcp`
- Restart: `systemctl restart cognitive-memory-mcp`
- Status: `systemctl status cognitive-memory-mcp`

**And** Health Monitoring:

- Systemd Watchdog: Timeout 60s (Server muss alle 60s heartbeat senden)
- Falls kein Heartbeat: Auto-Restart
- Health Check Endpoint: `/health` (simple HTTP Endpoint für Monitoring)

**Prerequisites:** Story 3.7 (Production Config vorhanden)

**Technical Notes:**

- Systemd: Standard für Linux Service Management
- Watchdog: `sd_notify("WATCHDOG=1")` in Python (systemd Python Package)
- Logging: `systemd.journal` Package für native Journal Integration
- Alternative (macOS): launchd (aber PRD impliziert Linux, Arch Linux mentioned)
- NFR004: Uptime - Lokales System, auto-restart bei Crashes akzeptabel

---

### Story 3.9: Staged Dual Judge Implementation (Enhancement E8)

**Als** MCP Server,
**möchte ich** Dual Judge schrittweise reduzieren (Phase 1: Dual → Phase 2: Single),
**sodass** Budget nach 3 Monaten von €5-10/mo auf €2-3/mo sinkt (-40%).

**Acceptance Criteria:**

**Given** System läuft 3 Monate in Production mit Dual Judge
**When** Staged Dual Judge Transition evaluiert wird
**Then** wird IRR-Stabilität geprüft:

- **Condition für Transition:** Kappa >0.85 über letzten 100 Ground Truth Queries
- **Rationale:** Kappa >0.85 = "Almost Perfect Agreement" → Single Judge ausreichend
- **Calculation:** Aggregiere alle judge1 vs. judge2 Scores aus letzten 3 Monaten

**And** falls Kappa >0.85 → aktiviere Single Judge Mode:

- **Phase 2 Config:** `dual_judge_enabled: false` in config.yaml
- **Primary Judge:** GPT-4o (behält IRR-Quality bei)
- **Spot Checks:** 5% Random Sampling mit Haiku als Second Judge (Drift Detection)
- **Cost Reduction:** €2-3/mo statt €5-10/mo (nur GPT-4o + 5% Haiku)

**And** falls Kappa <0.85 → bleibe in Dual Judge Mode:

- Log Warning: "IRR below threshold for Single Judge transition (Kappa: X.XX)"
- Continue Dual Judge für weitere 1 Monat
- Re-evaluate nach 4 Monaten

**And** Spot Check Mechanismus:

- Random Sampling: 5% aller neuen Ground Truth Queries
- Beide Judges aufrufen (GPT-4o + Haiku)
- Kappa berechnen für Spot Check Sample
- Falls Kappa <0.70 auf Spot Checks → Revert zu Full Dual Judge

**Prerequisites:** Story 1.11-1.12 (Dual Judge Implementation + IRR Validation)

**Technical Notes:**

- Staged Transition: Nicht hart-coded Timeline, sondern IRR-basiert (data-driven)
- Kappa >0.85: "Almost Perfect Agreement" (Landis & Koch Classification)
- Cost-Savings: €5-10/mo → €2-3/mo nach 3-4 Monaten
- Spot Check Sampling: `random.random() < 0.05` für 5% Selection
- Enhancement E8: Staged Dual Judge aus PRD

---

### Story 3.10: Budget Monitoring & Cost Optimization Dashboard

**Als** ethr,
**möchte ich** monatliche API-Kosten überwachen und Budget-Alerts erhalten,
**sodass** NFR003 (Budget €5-10/mo) eingehalten wird.

**Acceptance Criteria:**

**Given** System läuft in Production mit externen APIs
**When** Budget-Monitoring abgefragt wird
**Then** sind folgende Metriken verfügbar:

1. **Daily Cost Tracking:**
   - Tabelle: `api_cost_log` (date, api_name, num_calls, token_count, estimated_cost)
   - APIs: OpenAI Embeddings, GPT-4o Dual Judge, Haiku Evaluation, Haiku Reflexion
   - Cost Estimation: Token Count × API Rate (z.B. €0.02 per 1M tokens für Embeddings)

2. **Monthly Aggregation:**
   - Query: `SELECT SUM(estimated_cost) FROM api_cost_log WHERE date >= NOW() - INTERVAL '30 days'`
   - Breakdown: Cost per API (Embeddings vs. Dual Judge vs. Evaluation vs. Reflexion)
   - Trend: Monat-über-Monat Vergleich

3. **Budget Alert:**
   - **Threshold:** €10/mo (soft limit, NFR003)
   - **Alert Trigger:** Daily Cost × 30 >€10 (projected monthly overage)
   - **Action:** Log Warning + optional Email/Slack (konfigurierbar)

**And** Cost Optimization Insights:

- **Highest Cost API:** Identifiziere welche API am teuersten ist
- **Query Volume:** Correlate Cost mit Query Volume (mehr Queries = höhere Kosten)
- **Reflexion Rate:** Hohe Reflexion-Rate (>30%) = hohe Haiku Kosten → Verbesserung nötig

**And** Simple CLI Dashboard (optional):

- Command: `mcp-server budget-report --days 30`
- Output: Tabelle mit Daily/Monthly Costs, Breakdown per API, Projected Monthly Cost
- Alternative: PostgreSQL Query via Claude Code

**Prerequisites:** Story 2.4 (Haiku API mit Cost-Tracking)

**Technical Notes:**

- Token Counting: OpenAI/Anthropic SDKs geben Token Counts in Response zurück
- Cost Rates: Hard-coded in Config (manuell updaten bei API Price Changes)
- Real-Time Tracking: Log jeden API Call (bereits in Story 2.4 implementiert)
- Dashboard: Minimal CLI Tool (kein Grafana/Web UI für Personal Use)
- NFR003: Budget & Cost Efficiency

---

### Story 3.11: 7-Day Stability Testing & Validation

**Als** Entwickler,
**möchte ich** das System 7 Tage durchgehend laufen lassen ohne Crashes,
**sodass** Production-Readiness validiert ist (NFR004).

**Acceptance Criteria:**

**Given** alle Epic 3 Stories sind implementiert
**When** 7-Day Stability Test durchgeführt wird
**Then** läuft das System kontinuierlich:

- **Duration:** 7 Tage (168 Stunden) ohne manuellen Restart
- **Query Load:** Mindestens 10 Queries/Tag (70 Queries total, realistisch für Personal Use)
- **No Critical Crashes:** MCP Server darf nicht abstürzen (minor Errors okay, aber Auto-Recovery erforderlich)

**And** folgende Metriken werden gemessen:

1. **Uptime:** 100% (Server läuft durchgehend)
2. **Query Success Rate:** >99% (maximal 1 Failed Query erlaubt)
3. **Latency:** p95 <5s über alle 70 Queries (NFR001)
4. **API Reliability:** Retry-Logic erfolgreich bei transient Failures
5. **Budget:** Total Cost <€2 für 7 Tage (€8/mo projected → innerhalb €5-10/mo Budget)

**And** bei Problemen → Root Cause Analysis:

- **Falls Crashes:** Analyze systemd Logs, fix Bug, restart Test
- **Falls Latency >5s:** Profile Code, optimize, restart Test
- **Falls Budget Overage:** Identify Cost Driver, optimize API Usage

**And** Success-Dokumentation:

- `/docs/7-day-stability-report.md`:
  - Total Uptime: X hours
  - Queries Processed: X queries
  - Average Latency: X.XXs (p50, p95, p99)
  - Total Cost: €X.XX
  - Issues Encountered: None / [List]

**Prerequisites:** Stories 3.1-3.10 (alle Production Features implementiert)

**Technical Notes:**

- Test Environment: Production Environment (echte API Keys, echte DB)
- Query Load: Kann synthetisch generiert werden (Auto-Query Tool) oder organisch (ethr's tägliche Nutzung)
- Success Criteria: Aligned mit PRD Phase 5 Success Criteria
- Falls Failure: Re-run Test nach Fixes (nicht unbegrenzt - max 3 Iterationen)
- NFR004: System läuft stabil über 7 Tage ohne Crashes

---

### Story 3.12: Production Handoff & Documentation

**Als** ethr,
**möchte ich** vollständige Dokumentation für System-Betrieb und Maintenance haben,
**sodass** ich das System langfristig selbstständig betreiben kann.

**Acceptance Criteria:**

**Given** alle Features sind implementiert und getestet
**When** Dokumentation finalisiert wird
**Then** existieren folgende Dokumente:

1. **`/docs/README.md`** - Projekt-Overview
   - System-Architektur (MCP Server + Claude Code + PostgreSQL + APIs)
   - Key Features (L0/L2 Memory, Hybrid Search, CoT, Reflexion)
   - Budget & Performance Metrics

2. **`/docs/installation-guide.md`** - Setup von Scratch
   - PostgreSQL + pgvector Installation
   - Python Environment Setup
   - MCP Server Configuration
   - Claude Code Integration

3. **`/docs/operations-manual.md`** - Daily Operations
   - Wie starte ich MCP Server? (`systemctl start cognitive-memory-mcp`)
   - Wie prüfe ich Logs? (`journalctl -u cognitive-memory-mcp`)
   - Wie führe ich Backups manuell aus? (`pg_dump ...`)
   - Wie führe ich Model Drift Check aus? (Claude Code Query)

4. **`/docs/troubleshooting.md`** - Common Issues
   - "MCP Server verbindet nicht" → Check systemd status, logs
   - "Latency >5s" → Profile Hybrid Search, check pgvector Index
   - "API Budget Überschreitung" → Check api_cost_log, reduce Query Volume
   - "Model Drift Alert" → Check embedding_model_version, re-run Calibration

5. **`/docs/backup-recovery.md`** - Disaster Recovery
   - Wie restore ich aus Backup? (Step-by-Step `pg_restore`)
   - RTO/RPO Expectations (<1 hour, <24 hours)
   - L2 Insights Git Fallback (re-generate Embeddings)

6. **`/docs/api-reference.md`** - MCP Tools & Resources
   - Liste aller 7 Tools mit Parametern und Beispielen
   - Liste aller 5 Resources mit URI-Schema und Beispielen
   - Code Snippets für Claude Code Usage

**And** Code-Kommentierung:

- Alle wichtigen Funktionen haben Docstrings (Python)
- Komplexe Logik (RRF Fusion, Kappa Calculation) hat Inline-Comments
- Config-Dateien haben Kommentare für jede Variable

**And** Knowledge Transfer:

- Optional: 1-2 Sessions mit ethr zum Walkthrough (falls nötig)
- Dokumentation ist self-service-tauglich (kein externer Support nötig)

**Prerequisites:** Stories 3.1-3.11 (alle Features komplett)

**Technical Notes:**

- Markdown-Format: Alle Docs als .md für Readability in Git/Editor
- Zielgruppe: ethr (intermediate skill level, laut PRD)
- Sprache: Deutsch für User-Facing Docs (laut PRD document_output_language)
- Code Comments: Englisch (Standard für Code)
- Living Documentation: Kann später erweitert werden (v3.2+)

---

## Finale Epic-Zusammenfassung

### Gesamtübersicht

**Total:** 33 Stories über 3 Epics
**Geschätzte Timeline:** 133-175 Stunden (2.5-3.5 Monate bei 20h/Woche)
**Budget-Ziel:** €5-10/mo Production, dann €2-3/mo (nach Staged Dual Judge)

| Epic | Stories | Timeline | Budget | Critical Success |
|------|---------|----------|--------|------------------|
| **Epic 1:** MCP Server Foundation & Ground Truth | 12 | 38-50h | €0.23 (einmalig) | IRR Kappa >0.70, 50-100 Queries Ground Truth |
| **Epic 2:** RAG Pipeline & Hybrid Calibration | 9 | 35-45h | €1-2/mo | Precision@5 >0.75, <5s Latency |
| **Epic 3:** Production Readiness | 12 | 60-80h | €5-10/mo | 7-Day Stability, Model Drift Detection |

### Implementation Path

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

### Sequenzierung & Dependencies

```
Epic 1 (Foundation)
  ↓
Epic 2 (RAG Pipeline)
  ├─ benötigt: Ground Truth Set (aus Epic 1)
  └─ liefert: Kalibriertes Hybrid Search System
      ↓
Epic 3 (Production)
  ├─ benötigt: Funktionierendes System (aus Epic 2)
  └─ liefert: Production-Ready Deployment
```

**Keine Parallelisierung möglich:** Epics sind sequenziell (jeder Epic baut auf vorherigem auf).
**Innerhalb Epics:** Stories sind sequenziell geordnet (keine forward dependencies).

### Success Criteria

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

### Risk Mitigation

Alle kritischen Risks aus PRD sind adressiert:

- **Risk 1 (MCP Complexity):** Story 2.1 = Integration Testing + MCP Inspector
- **Risk 2 (Context Window):** Top-5 statt Top-10, Adaptive Truncation
- **Risk 3 (API Dependencies):** Story 3.3-3.4 = Retry-Logic + Claude Code Fallback
- **Risk 4 (Cost Variability):** Story 3.10 = Budget Monitoring + Alerts
- **Risk 5 (IRR Failure):** Story 1.12 = Contingency Plan (Human Tiebreaker, Wilcoxon Test)
- **Risk 6 (PostgreSQL Performance):** Story 1.2 = IVFFlat Index, Story 3.5 = Latency Benchmarking

### Out of Scope (v3.1.0)

**Explizit NICHT in diesem Epic Breakdown:**

- Neo4j Knowledge Graph Integration (v2.5/v3.2)
- Multi-User Support (nur ethr)
- Cloud Deployment (nur lokal)
- Voice Interface (nur Text)
- Advanced Agentic Workflows (v2.5)
- Fine-Tuning (System nutzt Verbal RL)

### Next Steps

Nach Epic-Breakdown Approval:

1. **Review mit ethr:** Validiere Epic-Struktur, Story-Sizing, Dependencies
2. **Transition zu Architecture:** Detaillierte Technical Spec für Epic 1 (wenn gewünscht)
3. **Begin Implementation:** Start mit Story 1.1 (Projekt-Setup)

---

_Für Implementation: Nutze den `create-story` Workflow um individuelle Story Implementation Plans aus diesem Epic Breakdown zu generieren._
