# Epic 2: RAG Pipeline & Hybrid Calibration

**Epic Goal:** Implementiere die vollständige RAG-Pipeline mit Claude Code als primärem LLM (Query Expansion, CoT Generation intern) und externen APIs für kritische Evaluationen (Haiku für Reflexion/Evaluation). Kalibriere Hybrid Search Gewichte via Grid Search auf Ground Truth Set für domänenspezifische Optimierung (Precision@5 >0.75).

**Business Value:** Ermöglicht kontextreiche Konversationen mit persistentem Memory (€0/mo für Bulk-Operationen) und konsistenter Qualitätssicherung (€1-2/mo für Evaluationen). Hybrid Calibration liefert +5-10% Precision@5 Uplift gegenüber MEDRAG-Default.

**Timeline:** 35-45 Stunden (Phase 2)
**Budget:** €1-2/mo (Development + Testing)

---

## Story 2.1: Claude Code MCP Client Setup & Integration Testing

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

## Story 2.2: Query Expansion Logik (intern in Claude Code)

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

## Story 2.3: Chain-of-Thought (CoT) Generation Framework

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

## Story 2.4: External API Setup für Haiku (Evaluation + Reflexion)

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

## Story 2.5: Self-Evaluation mit Haiku API

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

## Story 2.6: Reflexion-Framework mit Verbal Reinforcement Learning

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

## Story 2.7: End-to-End RAG Pipeline Testing

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

## Story 2.8: Hybrid Weight Calibration via Grid Search

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

## Story 2.9: Precision@5 Validation auf Ground Truth Set

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
