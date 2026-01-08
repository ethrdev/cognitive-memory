# Epic 1: MCP Server Foundation & Ground Truth Collection

**Epic Goal:** Etabliere das technische und methodische Fundament für das Cognitive Memory System durch Implementierung eines Python MCP Servers mit PostgreSQL-Persistence und Sammlung eines methodisch validen Ground Truth Sets (50-100 Queries) mit echten unabhängigen Dual Judges (GPT-4o + Haiku).

**Business Value:** Ermöglicht alle nachfolgenden Phasen durch (1) funktionale MCP-basierte Persistence-Infrastruktur und (2) statistisch robuste Evaluation-Baseline für Hybrid Calibration (Epic 2) und Model Drift Detection (Epic 3).

**Timeline:** 38-50 Stunden (Phase 1a: 20-25h, Phase 1b: 18-25h)
**Budget:** €0.23 einmalig (100 Queries Dual Judge)

---

## Story 1.1: Projekt-Setup und Entwicklungsumgebung

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

## Story 1.2: PostgreSQL + pgvector Setup

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

## Story 1.3: MCP Server Grundstruktur mit Tool/Resource Framework

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

## Story 1.4: L0 Raw Memory Storage (MCP Tool: store_raw_dialogue)

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

## Story 1.5: L2 Insights Storage mit Embedding (MCP Tool: compress_to_l2_insight)

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

## Story 1.6: Hybrid Search Implementation (MCP Tool: hybrid_search)

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

## Story 1.7: Working Memory Management (MCP Tool: update_working_memory)

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

## Story 1.8: Episode Memory Storage (MCP Tool: store_episode)

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

## Story 1.9: MCP Resources für Read-Only State Exposure

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

## Story 1.10: Ground Truth Collection UI (Streamlit App)

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

## Story 1.11: Dual Judge Implementation mit GPT-4o + Haiku (MCP Tool: store_dual_judge_scores)

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

## Story 1.12: IRR Validation & Contingency Plan (Enhancement E1)

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
