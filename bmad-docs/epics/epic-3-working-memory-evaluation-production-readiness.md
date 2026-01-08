# Epic 3: Working Memory, Evaluation & Production Readiness

**Epic Goal:** Bringe das System in Production-Ready State durch robuste Monitoring-Infrastruktur (Golden Test Set, Model Drift Detection), API-Ausfallsicherheit (Retry-Logic + Fallbacks), Budget-Optimierung (Staged Dual Judge) und 7-Tage Stability Testing. Ziel: €5-10/mo Budget, <5s Latency, keine kritischen Data Loss-Szenarien.

**Business Value:** Ermöglicht kontinuierlichen Production-Betrieb mit automatischer Qualitätssicherung, Budget-Monitoring und Früherkennung von Model Drift. Staged Dual Judge reduziert Kosten nach 3 Monaten von €5-10/mo auf €2-3/mo (-40%).

**Timeline:** 60-80 Stunden (Phase 3: 25-35h, Phase 4: 20-25h, Phase 5: 15-20h)
**Budget:** €5-10/mo (Production), dann €2-3/mo (nach Staged Dual Judge)

---

## Story 3.1: Golden Test Set Creation (separate von Ground Truth)

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

## Story 3.2: Model Drift Detection mit Daily Golden Test (MCP Tool: get_golden_test_results)

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

## Story 3.3: API Retry-Logic Enhancement mit Exponential Backoff

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

## Story 3.4: Claude Code Fallback für Haiku API Ausfall (Degraded Mode)

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

## Story 3.5: Latency Benchmarking & Performance Optimization

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

## Story 3.6: PostgreSQL Backup Strategy Implementation

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

## Story 3.7: Production Configuration & Environment Setup

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

## Story 3.8: MCP Server Daemonization & Auto-Start

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

## Story 3.9: Staged Dual Judge Implementation (Enhancement E8)

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

## Story 3.10: Budget Monitoring & Cost Optimization Dashboard

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

## Story 3.11: 7-Day Stability Testing & Validation

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

## Story 3.12: Production Handoff & Documentation

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
