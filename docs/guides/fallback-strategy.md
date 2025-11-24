# Fallback-Strategy: Claude Code Evaluation Fallback

**Story:** 3.4 - Claude Code Fallback für Haiku API Ausfall (Degraded Mode)
**Status:** Implemented
**Datum:** 2025-11-18

## 1. Overview

### Warum Fallback?

Das Cognitive Memory System v3.1.0-Hybrid nutzt Haiku API für kritische Evaluation-Tasks (Reward Score Berechnung). Um 99% Uptime zu garantieren, implementiert Story 3.4 einen **automatischen Fallback-Mechanismus** auf Claude Code Evaluation bei totalem Haiku API Ausfall.

**Key Principle:**
> Verfügbarkeit (99% Uptime) > perfekte Konsistenz (100% Score-Konsistenz)

### Wann wird Fallback getriggert?

Fallback wird **nur bei totalem API Ausfall** aktiviert, nicht bei einzelnen Fehlern:

1. **Haiku API Call fehlschlägt** (HTTP 503, Timeout, Network Error)
2. **Retry-Logic versucht 4x** mit Exponential Backoff (1s, 2s, 4s, 8s) - Story 3.3
3. **Nach allen 4 Retries gescheitert** → `FallbackRequiredException` wird geworfen
4. **Fallback-Handler aktiviert** → Claude Code Evaluation verwendet
5. **Fallback-Status geloggt** in PostgreSQL `fallback_status_log` Table

**Wichtig:** Einzelne API Failures (die nach Retry erfolgreich sind) triggern KEIN Fallback.

### Fallback-Architektur

```
┌─────────────────────────────────────────────────────────────┐
│  evaluate_answer_with_fallback()                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. Check: is_fallback_active('haiku_evaluation')?    │  │
│  │    └─ Ja  → Claude Code Evaluation (skip Haiku API)  │  │
│  │    └─ Nein → Continue to Step 2                      │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 2. Try: client.evaluate_answer() [@retry_with_backoff]│  │
│  │    ├─ Success → Return result (normal operation)      │  │
│  │    └─ FallbackRequiredException → Continue to Step 3  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 3. Activate Fallback:                                 │  │
│  │    ├─ activate_fallback('haiku_evaluation')           │  │
│  │    ├─ log_fallback_activation(...)                    │  │
│  │    └─ _claude_code_fallback_evaluation(...)           │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Background: periodic_health_check() [alle 15 Minuten]     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. Check: is_fallback_active('haiku_evaluation')?    │  │
│  │    └─ Nein → Skip health check (nicht nötig)         │  │
│  │    └─ Ja   → Continue to Step 2                      │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 2. Ping: _lightweight_haiku_ping()                    │  │
│  │    ├─ Success → deactivate_fallback(...)              │  │
│  │    │            log_fallback_recovery(...)             │  │
│  │    │            ✅ Normal operation restored           │  │
│  │    └─ Failure → Log Warning (kein Re-Trigger!)        │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Quality Trade-offs

### Erwartete Konsistenz-Reduktion

**Claude Code Evaluation: ~5-10% weniger konsistent als Haiku API**

| Metrik                  | Haiku API (External) | Claude Code Fallback (Internal) |
|-------------------------|----------------------|----------------------------------|
| **Konsistenz**          | 100% (Baseline)      | 90-95% (5-10% Reduktion)         |
| **Score-Variabilität**  | Minimal (deterministisch) | Leicht erhöht (Session-State)   |
| **Temperature**         | 0.0                  | 0.0 (simuliert)                  |
| **Cost**                | €0.001/eval          | €0.000/eval (intern)             |
| **Latency**             | ~0.5s (API Call)     | ~1-2s (intern, kein Network)     |

### Rationale: Warum ist Claude Code weniger konsistent?

1. **Session-State Variabilität:**
   - Haiku API: Externe API = **stateless**, deterministisch über Sessions
   - Claude Code: Interne Evaluation = **Session-gebunden**, kann zwischen Sessions variieren

2. **Evaluation-Implementierung:**
   - Haiku API: Native Anthropic Evaluation-Engine (optimiert für Konsistenz)
   - Claude Code: Heuristic-basierte Evaluation (Relevance/Accuracy/Completeness)

3. **Trade-off ist akzeptabel:**
   - 5-10% Konsistenz-Reduktion ist **deutlich besser** als 100% Failure (kein Service)
   - Episode Memory Quality kann temporär leicht sinken (akzeptabel für Uptime)

### Wann ist Degraded Mode akzeptabel?

**Acceptable Use Cases:**

- ✅ Haiku API total unavailable (nach 4 Retries)
- ✅ Temporäre API Instabilität (wenige Stunden bis Tage)
- ✅ Evaluation weiterhin erforderlich (Episode Memory muss funktionieren)

**NOT Acceptable (würde Fallback vermeiden):**

- ❌ Einzelne API Failures (werden durch Retry-Logic abgefangen)
- ❌ Perfekte Score-Konsistenz erforderlich (z.B. Production IRR Validation)
- ❌ Kritische Dual Judge Evaluation (Fallback nur für Haiku Evaluation, nicht Dual Judge)

---

## 3. Recovery Strategy

### Automatische Recovery (alle 15 Minuten)

**Background Health Check:**

- **Interval:** 15 Minuten (900 Sekunden)
- **Implementierung:** `periodic_health_check()` Background Task
- **Health Check Methode:** Lightweight Haiku API Ping (minimaler Token-Verbrauch)
- **Cost:** ~€0.0001 pro Ping (negligible, ~€0.01/mo bei continuous fallback)

**Recovery Flow:**

1. Health Check detektiert Haiku API erfolgreich antwortet
2. `deactivate_fallback('haiku_evaluation')` → Fallback-Flag auf False
3. `log_fallback_recovery(...)` → Recovery Event in DB geloggt
4. **Nächster Evaluation-Call nutzt wieder Haiku API** (normale Operation)

### Kein Manual Override erforderlich

**Komplett automatisch:**

- ✅ Activation: Automatisch nach 4 failed Retries
- ✅ Recovery: Automatisch via Health Check (alle 15 min)
- ❌ Kein Manual Intervention nötig

**Manual Recovery (optional, für Testing):**

```python
from mcp_server.health.haiku_health_check import manual_health_check

# Manual Health Check ausführen
result = await manual_health_check('haiku_evaluation')
print(f"API Healthy: {result['api_healthy']}")
print(f"Action Taken: {result['action_taken']}")
```

### Degraded Mode Duration

**Typische Szenarien:**

- **Kurzer Ausfall (< 1 Stunde):** 1-2 Health Checks → Recovery innerhalb 15-30 Minuten
- **Mittlerer Ausfall (1-6 Stunden):** 4-24 Health Checks → Recovery innerhalb 30-360 Minuten
- **Langer Ausfall (> 24 Stunden):** 96+ Health Checks → System bleibt in Degraded Mode bis API recovered

**Monitoring:**

Query Degraded Mode Duration:

```sql
-- Degraded Mode Duration Berechnung
WITH fallback_pairs AS (
    SELECT service_name,
           timestamp as activation_time,
           LEAD(timestamp) OVER (PARTITION BY service_name ORDER BY timestamp) as recovery_time,
           status,
           LEAD(status) OVER (PARTITION BY service_name ORDER BY timestamp) as next_status
    FROM fallback_status_log
)
SELECT service_name,
       activation_time,
       recovery_time,
       recovery_time - activation_time as degraded_duration,
       EXTRACT(EPOCH FROM (recovery_time - activation_time)) / 60 as degraded_minutes
FROM fallback_pairs
WHERE status = 'active' AND next_status = 'recovered'
ORDER BY activation_time DESC
LIMIT 20;
```

---

## 4. Monitoring

### Wie prüfe ich Fallback-Status?

**Option 1: In-Memory State (Real-Time)**

```python
from mcp_server.state.fallback_state import is_fallback_active, get_all_fallback_status

# Check einzelnen Service
fallback_active = await is_fallback_active('haiku_evaluation')
print(f"Fallback Active: {fallback_active}")

# Check alle Services
all_status = await get_all_fallback_status()
print(all_status)
# Output: {'haiku_evaluation': False, 'haiku_reflexion': False}
```

**Option 2: Database Logs (Historical)**

```sql
-- Query 1: Aktueller Fallback-Status (latest event pro Service)
WITH latest_events AS (
    SELECT service_name,
           status,
           timestamp,
           reason,
           metadata,
           ROW_NUMBER() OVER (PARTITION BY service_name ORDER BY timestamp DESC) as rn
    FROM fallback_status_log
)
SELECT service_name, status, timestamp, reason, metadata
FROM latest_events
WHERE rn = 1
ORDER BY service_name;
```

```sql
-- Query 2: Fallback-Events letzte 7 Tage
SELECT service_name,
       COUNT(*) as total_events,
       SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as activation_count,
       SUM(CASE WHEN status = 'recovered' THEN 1 ELSE 0 END) as recovery_count,
       MAX(timestamp) FILTER (WHERE status = 'active') as last_activation,
       MAX(timestamp) FILTER (WHERE status = 'recovered') as last_recovery
FROM fallback_status_log
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY service_name
ORDER BY last_activation DESC NULLS LAST;
```

```sql
-- Query 3: Recent Timeline (letzte 50 Events)
SELECT timestamp, service_name, status, reason, metadata
FROM fallback_status_log
ORDER BY timestamp DESC
LIMIT 50;
```

### Warning-Messages

**User-Facing Warning (während Degraded Mode):**

Wenn Fallback aktiv ist, wird folgende Warning-Message im MCP Tool Response angezeigt:

```
⚠️ System running in degraded mode (Haiku API unavailable). Using Claude Code evaluation as fallback.
```

**Log-Level:**

- **INFO:** Fallback activated, Fallback recovered, Health check success
- **WARNING:** Degraded mode active (user-facing), Health check failure
- **ERROR:** Critical failures (Database connection lost, etc.)

---

## 5. Testing

### Simuliere Haiku API Ausfall

**Test 1: Activate Fallback Manually**

```python
from mcp_server.state.fallback_state import activate_fallback
from mcp_server.utils.fallback_logger import log_fallback_activation

# Manually activate fallback (testing only!)
await activate_fallback('haiku_evaluation')
await log_fallback_activation(
    service_name='haiku_evaluation',
    reason='manual_test',
    metadata={'test': True}
)
```

**Test 2: Verify Fallback getriggert**

```python
from mcp_server.external.anthropic_client import HaikuClient, evaluate_answer_with_fallback

client = HaikuClient()

# Evaluation mit Fallback-Support
result = await evaluate_answer_with_fallback(
    client,
    query="What is the capital of France?",
    context=["France is a country in Europe..."],
    answer="The capital of France is Paris."
)

# Check if fallback was used
if result.get("fallback"):
    print("✅ Fallback active - Claude Code evaluation used")
else:
    print("✅ Normal operation - Haiku API used")
```

**Test 3: Verify Database Log**

```sql
-- Check fallback_status_log table
SELECT * FROM fallback_status_log
ORDER BY timestamp DESC
LIMIT 10;

-- Expected: Row mit status='active', service_name='haiku_evaluation'
```

### Simuliere API Recovery

**Test 4: Manual Health Check**

```python
from mcp_server.health.haiku_health_check import manual_health_check

# Run manual health check
result = await manual_health_check('haiku_evaluation')

print(f"API Healthy: {result['api_healthy']}")
print(f"Fallback Active: {result['fallback_active']}")
print(f"Action Taken: {result['action_taken']}")

# Expected: action_taken='fallback_deactivated' if API recovered
```

**Test 5: Verify Recovery Event**

```sql
-- Check recovery event logged
SELECT * FROM fallback_status_log
WHERE status = 'recovered'
ORDER BY timestamp DESC
LIMIT 5;

-- Expected: Row mit status='recovered', reason='api_recovered'
```

### Fallback-Quality Vergleich

**Test 6: Haiku vs. Claude Code Score Comparison**

```python
# Run 10 evaluations mit Haiku (normal mode)
# Run 10 evaluations mit Claude Code (fallback mode)
# Compare reward scores - expect ±5-10% variance

haiku_scores = [...]  # List of 10 scores
claude_code_scores = [...]  # List of 10 scores

variance = calculate_variance(haiku_scores, claude_code_scores)
print(f"Variance: {variance}%")

# Expected: variance <= 10%
```

---

## 6. Integration mit Epic 3 (Production Readiness)

### Story Dependencies

**Upstream (Dependency für Story 3.4):**

- ✅ **Story 3.3:** API Retry-Logic Enhancement mit Exponential Backoff
  - Provides `FallbackRequiredException` exception class
  - Implements 4-retry logic mit delays [1s, 2s, 4s, 8s]
  - Story 3.4 catches this exception → triggers fallback

**Downstream (Story 3.4 enhances future stories):**

- 🔄 **Story 3.5:** Latency Benchmarking & Performance Optimization
  - Will measure Fallback-Latency (Claude Code evaluation)
  - Benchmark: Haiku API (0.5s) vs. Claude Code (1-2s)

- 🔄 **Story 3.10:** Budget Monitoring & Cost Optimization Dashboard
  - Tracks Fallback-Aktivierungen (cost-savings während degraded mode)
  - Alert wenn Fallback-Frequency zu hoch (API Instabilität)

- 🔄 **Story 3.11:** 7-Day Stability Testing & Validation
  - Tests Fallback-Robustheit (simulierte API Ausfälle)
  - Validates Auto-Recovery funktioniert zuverlässig

### NFR Alignment

**NFR001: Query Response Time <5s (p95)**

- Haiku Evaluation: ~0.5s (normal operation)
- Claude Code Fallback: ~1-2s (degraded mode, **immer noch <5s**)
- ✅ NFR001 erfüllt auch während Fallback

**NFR003: Cost Target €5-10/mo**

- Normal Operation: €0.001/eval × 1000 evals = €1/mo
- Degraded Mode: €0.000/eval × 1000 evals = €0/mo (**Cost-Savings!**)
- ✅ NFR003 erfüllt, Fallback reduziert sogar Costs

**NFR004: Reliability & Robustness**

- 99% Uptime Ziel: Fallback ermöglicht weiterhin Evaluation bei API Ausfall
- Auto-Recovery: Kein Manual Intervention (15-min Health Check)
- ✅ NFR004 ist der **Hauptgrund** für Story 3.4

---

## 7. Known Limitations

### Was Fallback NICHT kann

1. **Perfekte Konsistenz:** 5-10% Varianz akzeptabel (nicht 100% deterministisch)
2. **Dual Judge Replacement:** Fallback nur für Haiku Evaluation, **nicht** für Dual Judge (GPT-4o + Haiku)
3. **Sofortige Recovery:** Health Check alle 15 Minuten (nicht instant)
4. **Fallback für OpenAI Embeddings:** Kein Fallback für Embeddings (kritisch, kein Alternative)

### Fallback-Cascade Vermeidung

**Important:** Health Check Failures triggern **KEIN neues Fallback**.

Ohne diese Constraint würde Infinite Loop entstehen:

```
API Failure → Activate Fallback → Health Check Fails → WOULD Re-Trigger Fallback → ∞
```

**Lösung:** Health Check on Failure nur loggt Warning, triggert NICHT neuen Fallback.

---

## 8. Maintenance

### Fallback-State Reset (Emergency)

```python
from mcp_server.state.fallback_state import reset_all_fallback_state

# ONLY for emergency recovery (not normal operation!)
await reset_all_fallback_state()
```

### Database Table Maintenance

**Retention Policy:**

- Fallback-Events werden **permanent** gespeichert (kein Auto-Delete)
- Optional: Cleanup-Script für Events > 90 Tage

```sql
-- Optional: Delete old fallback events (> 90 days)
DELETE FROM fallback_status_log
WHERE timestamp < NOW() - INTERVAL '90 days';
```

### Monitoring Alerts (future Story 3.10)

**Recommended Alerts:**

- 🚨 **High Fallback Frequency:** > 5 Activations pro Tag (API Instabilität)
- 🚨 **Long Degraded Mode:** Fallback active > 24 Stunden (persistent API failure)
- ℹ️ **Recovery Event:** Info-Notification wenn Fallback deactivated (normal operation restored)

---

## References

- **Story 3.4 File:** `bmad-docs/stories/3-4-claude-code-fallback-fuer-haiku-api-ausfall-degraded-mode.md`
- **Epic 3:** `bmad-docs/epics.md` (lines 1098-1142)
- **Architecture:** `bmad-docs/architecture.md` (Error Handling Strategy, lines 378-388)
- **Story 3.3:** API Retry-Logic Enhancement (Dependency)
