# Epic Technical Specification: Working Memory, Evaluation & Production Readiness

Date: 2025-11-18
Author: ethr
Epic ID: 3
Status: Draft

---

## Overview

Epic 3 bringt das Cognitive Memory System v3.1.0-Hybrid in einen production-ready State durch umfassende Monitoring-Infrastruktur, robuste API-Ausfallsicherheit und Budget-Optimierung. Dieser Epic implementiert das Golden Test Set (separate von Ground Truth) für tägliche Model Drift Detection, API Retry-Logic mit Fallbacks für alle externen Services (OpenAI, Anthropic), sowie Staged Dual Judge für Budget-Reduktion von €5-10/mo auf €2-3/mo nach 3 Monaten.

Zusätzlich werden Production-spezifische Features wie PostgreSQL Backup Strategy, systemd Daemonization, Environment-Separation (Development/Production) und 7-Day Stability Testing implementiert, um kontinuierlichen Betrieb mit €5-10/mo Budget und <5s Latency zu gewährleisten.

**Ziel:** Production-Ready System mit automatischer Qualitätssicherung (Precision@5 Monitoring), Budget-Monitoring, Früherkennung von Model Drift und robuster Error Handling für alle kritischen Pfade.

## Objectives and Scope

### In Scope

**Monitoring & Quality Assurance:**
- Golden Test Set Creation (50-100 Queries, separate von Ground Truth)
- Model Drift Detection mit täglich automated Golden Test Execution (Cron)
- Precision@5 Validation auf Ground Truth Set (>0.75 Target)
- Latency Benchmarking (100 Test-Queries, p50/p95/p99 Metriken)

**API Reliability & Fallbacks:**
- API Retry-Logic Enhancement mit Exponential Backoff (4 Retries: 1s, 2s, 4s, 8s)
- Claude Code Fallback für Haiku API Ausfall (Degraded Mode)
- API Retry Logging (api_retry_log table)
- Health Check Mechanismus (15min interval)

**Budget Optimization:**
- Budget Monitoring Dashboard (CLI Tool: mcp-server budget-report)
- API Cost Tracking (api_cost_log table mit daily/monthly aggregation)
- Budget Alerts (>€10/mo projected)
- Staged Dual Judge Implementation (Kappa >0.85 Transition Condition)

**Production Deployment:**
- PostgreSQL Backup Strategy (täglich pg_dump, 7-day retention)
- L2 Insights Git Export (optional, read-only fallback)
- Production Configuration & Environment Setup (Development/Production separation)
- MCP Server Daemonization (systemd service mit auto-restart)
- 7-Day Stability Testing (168h uptime, 70+ queries, >99% success rate)
- Production Handoff Documentation (6 docs: README, Installation, Operations, Troubleshooting, Backup-Recovery, API Reference)

### Out of Scope

- Neo4j Knowledge Graph Integration (v3.2)
- Cloud Deployment (nur lokal)
- Multi-User Support (nur ethr)
- Advanced Agentic Workflows (v2.5)
- Fine-Tuning (System nutzt Verbal RL)
- Automated Re-Calibration bei Domain Shift (manual re-run)

## System Architecture Alignment

Dieser Epic implementiert die **Production Readiness Layer** der Gesamt-Architektur:

```
┌─────────────────────────────────────────────────┐
│ Production Layer [THIS EPIC]                    │
│ ├── Monitoring (Golden Test, Model Drift)      │
│ ├── Budget Tracking (API Cost Log)             │
│ ├── Backup Strategy (pg_dump + Git)            │
│ ├── Daemonization (systemd)                    │
│ └── Environment Management (Dev/Prod)          │
├─────────────────────────────────────────────────┤
│ MCP Server (Epic 1)                             │
│ └── External API Clients                        │
│     ├── Retry Logic [ENHANCED IN THIS EPIC]    │
│     ├── Fallback Logic [NEW IN THIS EPIC]      │
│     └── Health Checks [NEW IN THIS EPIC]       │
├─────────────────────────────────────────────────┤
│ PostgreSQL + pgvector                           │
│ ├── Backup Automation [THIS EPIC]              │
│ └── Production Tables                           │
│     ├── golden_test_set [NEW]                  │
│     ├── model_drift_log [NEW]                  │
│     ├── api_cost_log [NEW]                     │
│     └── api_retry_log [NEW]                    │
└─────────────────────────────────────────────────┘
```

**Architektur-Constraints:**
- **Deployment:** Lokales System (Arch Linux), kein Cloud
- **Service Management:** systemd (Auto-Start, Auto-Restart, Logging)
- **Backup Location:** Lokales NAS oder `/backups/` Mount-Point
- **Monitoring:** Cron-basiert (Golden Test: 2 Uhr nachts, Backup: 3 Uhr nachts)
- **Budget Target:** €5-10/mo (first 3 months), dann €2-3/mo (after Staged Dual Judge)
- **Latency Target:** <5s (p95) für End-to-End Query Response

**Referenced Components:**
- **MCP Server:** Epic 1 Implementation (erweitert mit Retry Logic + Fallbacks)
- **Database Schema:** 4 neue Tabellen (golden_test_set, model_drift_log, api_cost_log, api_retry_log)
- **External APIs:** OpenAI (Embeddings), Anthropic (Haiku Evaluation), mit enhanced reliability measures
- **Claude Code:** Fallback-Provider für Evaluation bei Haiku API Ausfall

## Detailed Design

### Services and Modules

| Module | Responsibility | Inputs | Outputs | Owner/Story |
|--------|----------------|--------|---------|-------------|
| **Golden Test Service** | Creates and manages separate test set for drift detection | L0 Raw Memory, Stratified Sampling Config | Golden Test Set (50-100 queries) | Story 3.1 |
| **Model Drift Detector** | Daily Precision@5 validation on Golden Set | Golden Test Set, Hybrid Search Results | Drift Alert (boolean), Precision@5 Metric | Story 3.2 |
| **API Retry Handler** | Enhanced retry logic with exponential backoff | API Call Function, Retry Config | API Response or Error | Story 3.3 |
| **Haiku Fallback Service** | Claude Code evaluation bei Haiku API Ausfall | Query, Retrieved Context, Generated Answer | Reward Score (-1.0 to +1.0) | Story 3.4 |
| **Latency Benchmarker** | Performance measurement und optimization | Test Query Set (100 queries) | Latency Metrics (p50/p95/p99) | Story 3.5 |
| **Backup Manager** | Automated PostgreSQL backups mit rotation | DB Connection, Backup Config | Backup Files (.dump), Git Export (JSON) | Story 3.6 |
| **Environment Manager** | Dev/Prod configuration separation | .env files, config.yaml | Runtime Environment Config | Story 3.7 |
| **Service Daemon** | systemd integration mit auto-restart | MCP Server Process | systemd Service Status | Story 3.8 |
| **Staged Dual Judge Manager** | Transition von Dual zu Single Judge | Kappa History, Spot Check Config | Judge Mode (dual/single), Spot Check Results | Story 3.9 |
| **Budget Monitor** | API cost tracking und alerts | api_cost_log entries | Monthly Cost Report, Budget Alerts | Story 3.10 |
| **Stability Tester** | 7-day continuous operation validation | Production System | Stability Report (uptime, success rate, cost) | Story 3.11 |
| **Documentation Generator** | Production documentation suite | System Implementation | 6 Markdown Docs (README, Installation, etc.) | Story 3.12 |

### Data Models and Contracts

**Neue PostgreSQL Tabellen (Epic 3):**

```sql
-- Story 3.1: Golden Test Set
CREATE TABLE golden_test_set (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    expected_docs INTEGER[] NOT NULL,  -- L2 Insight IDs marked as relevant
    created_at TIMESTAMPTZ DEFAULT NOW(),
    query_type VARCHAR(20) NOT NULL CHECK (query_type IN ('short', 'medium', 'long'))
);
CREATE INDEX idx_golden_query_type ON golden_test_set(query_type);

-- Story 3.2: Model Drift Log
CREATE TABLE model_drift_log (
    date DATE PRIMARY KEY,
    precision_at_5 FLOAT NOT NULL CHECK (precision_at_5 BETWEEN 0.0 AND 1.0),
    num_queries INTEGER NOT NULL,
    avg_retrieval_time FLOAT,  -- milliseconds
    embedding_model_version VARCHAR(50),
    drift_detected BOOLEAN DEFAULT FALSE,
    baseline_p5 FLOAT  -- 7-day rolling average for comparison
);
CREATE INDEX idx_drift_date ON model_drift_log(date DESC);

-- Story 3.10: API Cost Log
CREATE TABLE api_cost_log (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    api_name VARCHAR(50) NOT NULL,  -- 'openai_embeddings' | 'gpt4o_judge' | 'haiku_eval' | 'haiku_reflection'
    num_calls INTEGER NOT NULL,
    token_count INTEGER,
    estimated_cost FLOAT NOT NULL  -- in EUR
);
CREATE INDEX idx_cost_date_api ON api_cost_log(date DESC, api_name);

-- Story 3.3: API Retry Log
CREATE TABLE api_retry_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    api_name VARCHAR(50) NOT NULL,
    error_type VARCHAR(100),  -- '429_rate_limit' | '503_unavailable' | 'timeout' | 'network_error'
    retry_count INTEGER NOT NULL,
    success BOOLEAN NOT NULL,
    latency_ms FLOAT
);
CREATE INDEX idx_retry_timestamp ON api_retry_log(timestamp DESC);
```

**Configuration Models:**

```yaml
# config.yaml (Story 3.7)
environment: production  # or 'development'

development:
  database:
    host: localhost
    port: 5432
    name: cognitive_memory_dev
    user: mcp_user
  api_budgets:
    openai_monthly_eur: 1.0
    anthropic_monthly_eur: 3.0

production:
  database:
    host: localhost
    port: 5432
    name: cognitive_memory
    user: mcp_user
  api_budgets:
    openai_monthly_eur: 0.10
    anthropic_monthly_eur: 10.0

monitoring:
  golden_test_schedule: "0 2 * * *"  # Daily 2 AM
  backup_schedule: "0 3 * * *"  # Daily 3 AM
  drift_alert_threshold: 0.05  # 5% drop triggers alert

budget:
  monthly_limit_eur: 10.0
  alert_threshold_eur: 8.0

staged_dual_judge:
  transition_kappa_threshold: 0.85
  spot_check_rate: 0.05  # 5% sampling after transition
  min_queries_before_transition: 100
```

**Backup Configuration:**

```bash
# scripts/backup.sh (Story 3.6)
BACKUP_DIR="/backups/postgres"
RETENTION_DAYS=7
DB_NAME="cognitive_memory"
DB_USER="mcp_user"
BACKUP_FILE="${BACKUP_DIR}/cognitive_memory_$(date +%Y-%m-%d).dump"

# L2 Insights Export (optional)
L2_EXPORT_DIR="/home/user/i-o/memory/l2-insights"
L2_EXPORT_FILE="${L2_EXPORT_DIR}/$(date +%Y-%m-%d).json"
```

**systemd Service Definition:**

```ini
# systemd/cognitive-memory-mcp.service (Story 3.8)
[Unit]
Description=Cognitive Memory MCP Server
After=postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=ethr
WorkingDirectory=/home/user/i-o
ExecStart=/home/user/i-o/venv/bin/python /home/user/i-o/mcp_server/main.py
Restart=always
RestartSec=10
Environment="ENVIRONMENT=production"
EnvironmentFile=/home/user/i-o/config/.env.production

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cognitive-memory-mcp

# Health Check / Watchdog
WatchdogSec=60

[Install]
WantedBy=multi-user.target
```

### APIs and Interfaces

**Enhanced API Retry Logic (Story 3.3):**

```python
# mcp_server/utils/retry_logic.py
import time
import random
from typing import Callable, Any, TypeVar
from anthropic import Anthropic
from openai import OpenAI

T = TypeVar('T')

def exponential_backoff_retry(
    func: Callable[..., T],
    max_retries: int = 4,
    base_delay: float = 1.0,
    jitter: bool = True
) -> T:
    """
    Retry function with exponential backoff.

    Delays: 1s, 2s, 4s, 8s (with optional ±20% jitter)
    Total max wait: ~15s
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                # Log to api_retry_log
                log_retry_failure(func.__name__, attempt + 1, str(e))
                raise

            delay = base_delay * (2 ** attempt)
            if jitter:
                delay *= random.uniform(0.8, 1.2)

            # Log retry attempt
            log_retry_attempt(func.__name__, attempt + 1, str(e))
            time.sleep(delay)

    raise RuntimeError(f"Failed after {max_retries} retries")

# Usage for OpenAI Embeddings
def create_embedding_with_retry(text: str) -> list[float]:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def _call():
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    return exponential_backoff_retry(_call, max_retries=4)

# Usage for Haiku API
def haiku_evaluation_with_retry(query: str, answer: str, context: str) -> float:
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def _call():
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=500,
            temperature=0.0,
            messages=[{
                "role": "user",
                "content": f"Query: {query}\nContext: {context}\nAnswer: {answer}\nRate quality (-1.0 to +1.0)"
            }]
        )
        return float(response.content[0].text)

    try:
        return exponential_backoff_retry(_call, max_retries=4)
    except Exception as e:
        # Fallback to Claude Code Evaluation (Story 3.4)
        log_fallback_activation("haiku_eval", str(e))
        return claude_code_fallback_evaluation(query, answer, context)
```

**Fallback Evaluation Service (Story 3.4):**

```python
# mcp_server/services/fallback_evaluation.py
def claude_code_fallback_evaluation(query: str, answer: str, context: str) -> float:
    """
    Fallback evaluation using Claude Code when Haiku API is unavailable.

    Note: This is a degraded mode - Claude Code evaluation may be less
    consistent than Haiku API due to session state variability.
    """
    # Log degraded mode activation
    log_degraded_mode("haiku_api_unavailable", timestamp=datetime.now())

    # Return a conservative reward score
    # In practice, Claude Code would perform evaluation internally
    # This is a simplified stub for the architecture
    return 0.5  # Neutral score, indicates degraded mode

def check_haiku_api_health() -> bool:
    """
    Periodic health check for Haiku API (runs every 15 minutes).

    Returns True if API is available, False otherwise.
    """
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    try:
        # Minimal inference call
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}]
        )
        return True
    except Exception:
        return False

# Periodic health check (runs via cron or background thread)
def health_check_loop():
    while True:
        healthy = check_haiku_api_health()
        if healthy and FALLBACK_MODE_ACTIVE:
            log_api_recovery("haiku_api")
            FALLBACK_MODE_ACTIVE = False
        time.sleep(900)  # 15 minutes
```

**Model Drift Detection API (Story 3.2):**

```python
# MCP Tool Enhancement: get_golden_test_results
@mcp_tool
def get_golden_test_results() -> dict:
    """
    Runs Golden Test Set daily, calculates Precision@5, detects drift.

    Returns:
        {
            "date": "2025-11-18",
            "precision_at_5": 0.78,
            "num_queries": 100,
            "drift_detected": False,
            "baseline_p5": 0.80,
            "current_p5": 0.78,
            "drop_percentage": 0.025
        }
    """
    # Load Golden Test Set
    golden_queries = db.query("SELECT * FROM golden_test_set")

    # Run hybrid_search for each query
    results = []
    for query in golden_queries:
        embedding = create_embedding_with_retry(query.query)
        top5 = hybrid_search(embedding, query.query, top_k=5)

        # Calculate Precision@5
        relevant_count = sum(
            1 for doc in top5 if doc.id in query.expected_docs
        )
        precision = relevant_count / 5.0
        results.append(precision)

    # Aggregate Precision@5
    avg_precision = sum(results) / len(results)

    # Get 7-day baseline
    baseline = db.query("""
        SELECT AVG(precision_at_5)
        FROM model_drift_log
        WHERE date >= CURRENT_DATE - INTERVAL '7 days'
    """).scalar()

    # Detect drift (>5% drop)
    drift_detected = (baseline - avg_precision) > 0.05

    # Store in model_drift_log
    db.execute("""
        INSERT INTO model_drift_log
        (date, precision_at_5, num_queries, drift_detected, baseline_p5)
        VALUES (%s, %s, %s, %s, %s)
    """, (datetime.now().date(), avg_precision, len(golden_queries), drift_detected, baseline))

    return {
        "date": str(datetime.now().date()),
        "precision_at_5": avg_precision,
        "num_queries": len(golden_queries),
        "drift_detected": drift_detected,
        "baseline_p5": baseline,
        "current_p5": avg_precision,
        "drop_percentage": (baseline - avg_precision) / baseline if baseline else 0.0
    }
```

**Budget Monitoring CLI (Story 3.10):**

```python
# scripts/budget_report.py
import argparse
from datetime import datetime, timedelta

def generate_budget_report(days: int = 30):
    """
    CLI Tool: mcp-server budget-report --days 30

    Displays API costs, breakdown per API, projected monthly cost.
    """
    start_date = datetime.now().date() - timedelta(days=days)

    # Query api_cost_log
    costs = db.query("""
        SELECT api_name, SUM(estimated_cost) as total_cost, SUM(num_calls) as total_calls
        FROM api_cost_log
        WHERE date >= %s
        GROUP BY api_name
        ORDER BY total_cost DESC
    """, (start_date,))

    total_cost = sum(row.total_cost for row in costs)
    projected_monthly = (total_cost / days) * 30

    print(f"API Budget Report ({days} days)")
    print("=" * 60)
    print(f"Total Cost: €{total_cost:.2f}")
    print(f"Projected Monthly: €{projected_monthly:.2f}")
    print("\nBreakdown by API:")
    for row in costs:
        print(f"  {row.api_name:30} €{row.total_cost:.2f} ({row.total_calls} calls)")

    # Alert if over budget
    if projected_monthly > 10.0:
        print(f"\n⚠️  ALERT: Projected monthly cost (€{projected_monthly:.2f}) exceeds budget (€10.00)")

    return {
        "total_cost": total_cost,
        "projected_monthly": projected_monthly,
        "breakdown": costs
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    generate_budget_report(args.days)
```

### Workflows and Sequencing

**Workflow 1: Daily Model Drift Detection (Story 3.2)**

```
Cron Job (2 AM daily)
  ↓
MCP Tool: get_golden_test_results()
  ├─ 1. Load Golden Test Set (50-100 queries)
  ├─ 2. For each query:
  │    ├─ Create embedding (OpenAI API)
  │    ├─ Run hybrid_search (MCP Tool)
  │    ├─ Compare Top-5 with expected_docs
  │    └─ Calculate Precision@5
  ├─ 3. Aggregate Macro-Average Precision@5
  ├─ 4. Load 7-Day Baseline from model_drift_log
  ├─ 5. Detect Drift:
  │    ├─ If (baseline - current) > 0.05: drift_detected = True
  │    └─ Else: drift_detected = False
  ├─ 6. Store in model_drift_log table
  └─ 7. Return Results
       └─ If drift_detected: Log Warning (optional Email/Slack alert)
```

**Workflow 2: API Call mit Retry + Fallback (Stories 3.3, 3.4)**

```
Claude Code / MCP Server
  ↓ External API Call (Haiku Evaluation)
Retry Handler
  ├─ Attempt 1
  │    ├─ Call Haiku API
  │    ├─ Success → Return Result
  │    └─ Failure (429/503/timeout) → Log, wait 1s
  ├─ Attempt 2
  │    ├─ Call Haiku API
  │    ├─ Success → Return Result
  │    └─ Failure → Log, wait 2s
  ├─ Attempt 3
  │    ├─ Call Haiku API
  │    ├─ Success → Return Result
  │    └─ Failure → Log, wait 4s
  ├─ Attempt 4
  │    ├─ Call Haiku API
  │    ├─ Success → Return Result
  │    └─ Failure → Log, wait 8s
  └─ All Retries Exhausted
       ↓
  Fallback Logic (Story 3.4)
       ├─ Log: "Entering degraded mode (Haiku API unavailable)"
       ├─ Activate Fallback: Claude Code Evaluation
       ├─ Set FALLBACK_MODE_ACTIVE = True
       └─ Return Conservative Reward Score (0.5)
            ↓
  Background Health Check (15min interval)
       ├─ Ping Haiku API
       ├─ If Success:
       │    ├─ Log: "Haiku API recovered"
       │    └─ Set FALLBACK_MODE_ACTIVE = False
       └─ If Failure: Continue in degraded mode
```

**Workflow 3: Daily Backup + L2 Insights Export (Story 3.6)**

```
Cron Job (3 AM daily)
  ↓ scripts/backup.sh
Backup Manager
  ├─ 1. PostgreSQL Backup
  │    ├─ pg_dump -Fc cognitive_memory > backup_YYYY-MM-DD.dump
  │    ├─ Verify backup size (>1MB expected)
  │    └─ Log success/failure
  ├─ 2. Backup Rotation
  │    ├─ Find backups older than 7 days
  │    ├─ Delete old backups
  │    └─ Log retention policy execution
  ├─ 3. L2 Insights Git Export (optional)
  │    ├─ SELECT id, content, created_at, source_ids FROM l2_insights
  │    ├─ Export to JSON → /memory/l2-insights/YYYY-MM-DD.json
  │    ├─ Git add + commit (optional)
  │    └─ Git push (optional)
  └─ 4. Log Backup Summary
       └─ api_cost_log entry: backup_size, duration, success
```

**Workflow 4: Staged Dual Judge Transition (Story 3.9)**

```
Monthly Evaluation (after 3 months)
  ↓
Staged Dual Judge Manager
  ├─ 1. Check Transition Condition
  │    ├─ Load last 100 Ground Truth queries
  │    ├─ Calculate Macro-Average Kappa
  │    └─ If Kappa >0.85: Proceed to Transition
  ├─ 2. Transition Decision
  │    ├─ Kappa ≥0.85:
  │    │    ├─ Update config: dual_judge_enabled = False
  │    │    ├─ Set primary_judge = "gpt-4o"
  │    │    ├─ Set spot_check_rate = 0.05 (5%)
  │    │    └─ Log: "Transitioned to Single Judge + Spot Checks"
  │    └─ Kappa <0.85:
  │         ├─ Log: "IRR below threshold, continue Dual Judge"
  │         └─ Re-evaluate in 1 month
  ├─ 3. Spot Check Mechanism (after transition)
  │    ├─ For each new Ground Truth query:
  │    │    ├─ Random sampling: if random() < 0.05:
  │    │    │    ├─ Call GPT-4o (primary)
  │    │    │    ├─ Call Haiku (spot check)
  │    │    │    └─ Calculate Kappa for spot check sample
  │    │    └─ Else: Call GPT-4o only
  │    └─ If Spot Check Kappa <0.70:
  │         ├─ Log: "Spot check IRR failure, reverting to Dual Judge"
  │         └─ Revert to full Dual Judge mode
  └─ 4. Budget Impact
       ├─ Before: €5-10/mo (full Dual Judge)
       └─ After: €2-3/mo (Single + 5% Spot Checks)
```

**Workflow 5: 7-Day Stability Test (Story 3.11)**

```
Day 0: Start Production System
  ↓
Stability Tester (runs for 168 hours)
  ├─ 1. Initialize Metrics
  │    ├─ Start timestamp
  │    ├─ Uptime counter
  │    ├─ Query counter
  │    └─ Error counter
  ├─ 2. Daily Operations (Day 1-7)
  │    ├─ Process 10+ queries per day (70+ total)
  │    ├─ Log each query: latency, success/failure, cost
  │    ├─ Monitor systemd status: active/inactive/failed
  │    ├─ Check for crashes (auto-restart count)
  │    └─ Track API costs (daily aggregation)
  ├─ 3. Automated Monitoring
  │    ├─ Cron: Golden Test (daily 2 AM)
  │    ├─ Cron: Backup (daily 3 AM)
  │    └─ Background: Health Check (15min interval)
  ├─ 4. Metrics Collection
  │    ├─ Uptime: systemd uptime calculation
  │    ├─ Query Success Rate: (successful / total) * 100
  │    ├─ Latency: p50, p95, p99 from query logs
  │    ├─ Total Cost: SUM(api_cost_log) over 7 days
  │    └─ Error Rate: failures / total queries
  └─ 5. Final Report (Day 7)
       ├─ Total Uptime: X hours / 168 hours
       ├─ Queries Processed: X queries
       ├─ Success Rate: X% (Target: >99%)
       ├─ Average Latency: X.XXs (p50), X.XXs (p95)
       ├─ Total Cost: €X.XX (Target: <€2 for 7 days)
       ├─ Issues Encountered: [List or "None"]
       └─ Save to /docs/7-day-stability-report.md
```

## Non-Functional Requirements

### Performance

**Latency Targets (Epic 3 Scope):**

| Metric | Target | Measurement Context | Story |
|--------|--------|---------------------|-------|
| **End-to-End Query Response** | <5s (p95) | Full RAG pipeline (Retrieval + Generation + Evaluation) | 3.5 |
| **Golden Test Execution** | <10min | 50-100 queries, sequential processing | 3.2 |
| **Model Drift Detection** | <15min total | Daily cron job (2 AM), includes all queries | 3.2 |
| **PostgreSQL Backup** | <5min | pg_dump for ~10GB database | 3.6 |
| **API Retry Overhead** | +1-15s max | Exponential backoff (4 retries total) | 3.3 |
| **Health Check Latency** | <500ms | Haiku API ping (15min interval) | 3.4 |
| **Budget Report Generation** | <2s | CLI tool, 30-day query window | 3.10 |

**Performance Optimizations:**

- **Parallel API Calls:** Embeddings + Retrieval in parallel (where possible)
- **Connection Pooling:** PostgreSQL connection reuse (psycopg2.pool)
- **Batch Processing:** Golden Test queries processed in batches of 10 (reduce connection overhead)
- **Lazy Loading:** Only load drift detection data when needed
- **Index Optimization:** All monitoring tables have date-based indices (DESC order)

**Performance Monitoring:**

- Latency metrics logged to `model_drift_log.avg_retrieval_time`
- API retry latency tracked in `api_retry_log.latency_ms`
- Daily aggregation for trend analysis (Story 3.11)

**Degraded Performance Scenarios:**

- **API Retry Mode:** +1-15s latency overhead (acceptable for reliability)
- **Fallback Mode:** Claude Code evaluation may be slower than Haiku API
- **Large Database (>100K L2 Insights):** Retrieval may degrade to 2-3s (still within <5s budget)

### Security

**Production Security Measures:**

1. **Environment Isolation (Story 3.7)**
   - Separate `.env.development` and `.env.production` files
   - Production secrets: `chmod 600` (owner-only read)
   - No secrets in Git (`.gitignore` enforced)
   - Environment variable validation on startup

2. **Service User Permissions (Story 3.8)**
   - MCP Server runs as `ethr` user (non-root)
   - PostgreSQL user `mcp_user` has limited privileges (no DROP DATABASE, no CREATE USER)
   - systemd service cannot modify system files outside `/home/user/i-o`

3. **Backup Security (Story 3.6)**
   - Backup files permissions: `chmod 600` (owner-only)
   - Backup location: `/backups/postgres` (not world-readable)
   - Optional encryption: GPG encryption for backups (out of scope v3.1, but documented)

4. **API Key Management**
   - Keys stored in `.env.production` only
   - No hardcoded keys in source code
   - API keys rotated manually (no auto-rotation in v3.1)

5. **Data Privacy**
   - All conversation data remains local (PostgreSQL)
   - External APIs receive only text snippets (no full transcripts)
   - No user data sent for API training (OpenAI/Anthropic policies)
   - Golden Test Set contains no PII (only philosophical queries)

**Threat Model (Epic 3 Additions):**

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| **Backup Theft** | Low | High (full DB exposure) | chmod 600, backup location not publicly exposed |
| **API Key Leak** | Low | Medium (budget overrun, data exposure) | .env files git-ignored, chmod 600 |
| **systemd Service Exploit** | Very Low | Medium (local privilege escalation) | Non-root user, limited permissions |
| **L2 Git Export Exposure** | Low | Low (only L2 text, no raw dialogues) | Optional feature, disabled by default |

**Out of Scope for Epic 3:**

- Network-based attacks (no external exposure)
- Multi-user authentication (single user system)
- Secrets management vault (HashiCorp Vault, AWS Secrets Manager)
- Encryption at rest for PostgreSQL

### Reliability/Availability

**Availability Targets:**

- **MCP Server Uptime:** >99% (7-day stability test, Story 3.11)
- **PostgreSQL Uptime:** >99.9% (systemd auto-restart)
- **External API Availability:** 99%+ (OpenAI/Anthropic SLA, with fallbacks)

**Reliability Enhancements (Epic 3):**

1. **API Retry Logic (Story 3.3)**
   - 4 retries with exponential backoff (1s, 2s, 4s, 8s)
   - Jitter (±20%) to avoid thundering herd
   - Total max wait: ~15s before failure
   - Retry success tracked in `api_retry_log`

2. **Fallback Mechanisms (Story 3.4)**
   - Haiku API failure → Claude Code Evaluation (degraded mode)
   - OpenAI Embeddings failure → No fallback (critical path, hard failure)
   - PostgreSQL connection loss → Auto-reconnect (transient errors)

3. **Health Checks (Story 3.4)**
   - Haiku API: Ping every 15 minutes
   - Automatic recovery from degraded mode when API restored
   - Health status logged (INFO level)

4. **Auto-Restart (Story 3.8)**
   - systemd `Restart=always` policy
   - `RestartSec=10` (wait 10s before restart)
   - `WatchdogSec=60` (health check every 60s)
   - Auto-restart count tracked in systemd journal

5. **Backup & Recovery (Story 3.6)**
   - Daily PostgreSQL backups (3 AM)
   - 7-day retention (RPO: <24h)
   - RTO: <1 hour (restore from latest dump)
   - L2 Insights Git fallback (optional, text-only)

**Error Handling Patterns:**

```python
# All critical operations follow this pattern
try:
    result = critical_operation()
except TransientError as e:
    log_retry_attempt()
    retry_with_backoff()
except PermanentError as e:
    log_failure()
    activate_fallback() or raise
finally:
    cleanup_resources()
```

**Graceful Degradation:**

| Failure Scenario | Degraded Behavior | Impact |
|------------------|-------------------|--------|
| **Haiku API down** | Claude Code Evaluation | Episode Memory quality may vary |
| **OpenAI Embeddings down** | Hard failure (no retrieval possible) | System unusable until recovery |
| **PostgreSQL connection loss** | Auto-reconnect (max 3 attempts) | Temporary query failures |
| **Disk space full** | Backup rotation triggered early | Backup retention <7 days |
| **Cron job failure** | Manual execution required | Model drift detection delayed |

**Data Integrity:**

- **Transactional Backups:** pg_dump uses consistent snapshot
- **Backup Verification:** File size check (>1MB expected)
- **Retention Policy:** Automated deletion of old backups (prevents disk overflow)
- **No Data Loss on Eviction:** Critical items archived to `stale_memory` (Epic 1 feature, validated in Epic 3)

### Observability

**Logging Strategy (Epic 3 Additions):**

1. **Structured JSON Logging**
   ```json
   {
     "timestamp": "2025-11-18T02:15:30Z",
     "level": "INFO",
     "component": "model_drift_detector",
     "message": "Daily drift detection completed",
     "metadata": {
       "precision_at_5": 0.78,
       "num_queries": 100,
       "drift_detected": false,
       "execution_time_seconds": 485
     }
   }
   ```

2. **Log Destinations**
   - systemd Journal: `journalctl -u cognitive-memory-mcp -f`
   - File Log: `/var/log/cognitive-memory/mcp.log` (rotation: 7 days, 100MB max)
   - Console: stderr (development only)

3. **Log Levels**
   - **ERROR:** API failures (all retries exhausted), backup failures, drift alerts
   - **WARN:** Degraded mode activation, retry attempts, backup rotation triggered early
   - **INFO:** Daily drift detection, backup completion, API recovery, service start/stop
   - **DEBUG:** Individual query processing, API call details (development only)

**Metrics Collection (Epic 3):**

| Metric | Source | Storage | Aggregation |
|--------|--------|---------|-------------|
| **Precision@5** | Golden Test | model_drift_log | Daily, 7-day rolling average |
| **API Costs** | API Clients | api_cost_log | Daily sum, monthly projection |
| **Retry Success Rate** | Retry Handler | api_retry_log | Daily, per API |
| **Query Latency** | RAG Pipeline | model_drift_log.avg_retrieval_time | Daily p50/p95/p99 |
| **System Uptime** | systemd | systemd journal | Continuous |
| **Backup Status** | Backup Script | Cron logs + file system | Daily |

**Monitoring Dashboards (Epic 3 Scope):**

1. **Budget Monitoring (Story 3.10)**
   - CLI Tool: `python scripts/budget_report.py --days 30`
   - Output: Total cost, projected monthly, breakdown per API
   - Alert: Red warning if projected >€10/mo

2. **Drift Detection Dashboard (Story 3.2)**
   - SQL Query: `SELECT * FROM model_drift_log ORDER BY date DESC LIMIT 30`
   - Visualization: Precision@5 trend over time (manual plot, not automated)

3. **Retry Statistics (Story 3.3)**
   - SQL Query: `SELECT api_name, COUNT(*), AVG(retry_count) FROM api_retry_log GROUP BY api_name`
   - Metrics: Retry frequency, success rate per API

**Alerting Mechanisms (Epic 3):**

1. **Model Drift Alert (Story 3.2)**
   - Trigger: `drift_detected = True` in daily Golden Test
   - Action: ERROR log entry (optional: email/Slack webhook, out of scope)
   - Message: "Precision@5 dropped by X% (baseline: 0.80, current: 0.75)"

2. **Budget Alert (Story 3.10)**
   - Trigger: Projected monthly cost >€10.00
   - Action: WARN log + CLI output (red warning)
   - Message: "⚠️ ALERT: Projected monthly cost (€12.50) exceeds budget (€10.00)"

3. **API Failure Alert (Story 3.3)**
   - Trigger: All retries exhausted for critical API (OpenAI Embeddings)
   - Action: ERROR log + fallback activation (Haiku only)
   - Message: "OpenAI Embeddings API unavailable after 4 retries"

4. **Backup Failure Alert (Story 3.6)**
   - Trigger: pg_dump exit code != 0
   - Action: ERROR log (manual intervention required)
   - Message: "PostgreSQL backup failed: {error_message}"

**Tracing & Debugging:**

- **Request IDs:** MCP Tool calls have correlation IDs (logged in structured metadata)
- **Query Provenance:** Each query logged with timestamp, user, session_id
- **Error Stack Traces:** Full exception traces in ERROR logs (PII-sanitized)

**Production Monitoring Checklist (Story 3.11):**

- [ ] Daily drift detection runs successfully (check cron logs)
- [ ] Daily backups created (check `/backups/postgres/` directory)
- [ ] Budget within limits (run `budget_report.py` weekly)
- [ ] No ERROR-level logs in systemd journal
- [ ] systemd service status: `active (running)`
- [ ] PostgreSQL connections healthy (`SELECT 1` test)
- [ ] API health checks passing (Haiku API reachable)

**Out of Scope for Epic 3:**

- Real-time monitoring dashboard (Grafana/Prometheus)
- Distributed tracing (OpenTelemetry)
- Anomaly detection (statistical outlier detection)
- Automated incident response (PagerDuty integration)

## Dependencies and Integrations

### Python Dependencies

**Core Libraries (from Epic 1):**

```toml
# pyproject.toml
[project]
name = "cognitive-memory-mcp"
version = "3.1.0-hybrid"
requires-python = ">=3.11"

dependencies = [
    "mcp>=0.9.0",                    # MCP Server framework
    "psycopg2-binary>=2.9.9",        # PostgreSQL driver
    "openai>=1.51.0",                # OpenAI API client
    "anthropic>=0.39.0",             # Anthropic API client
    "numpy>=1.24.0",                 # Vector operations
    "python-dotenv>=1.0.0",          # Environment variable loading
    "pyyaml>=6.0",                   # Config file parsing
    "asyncpg>=0.29.0",               # Async PostgreSQL (optional)
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]
```

**New Dependencies (Epic 3):**

```bash
# No new external dependencies required
# Epic 3 uses existing libraries with enhanced patterns:
# - psycopg2: Backup/restore operations
# - anthropic/openai: Enhanced retry logic
# - yaml: Configuration management (config.yaml)
```

**Dependency Version Constraints:**

| Package | Min Version | Max Version | Reason |
|---------|-------------|-------------|--------|
| `mcp` | 0.9.0 | <1.0 | Breaking changes expected in v1.0 |
| `psycopg2-binary` | 2.9.9 | <3.0 | PostgreSQL 15+ compatibility |
| `openai` | 1.51.0 | <2.0 | text-embedding-3-small model support |
| `anthropic` | 0.39.0 | <1.0 | claude-3-5-haiku-20241022 support |
| `python` | 3.11 | <4.0 | Type hints, async/await features |

### System Dependencies

**PostgreSQL 15+ mit pgvector:**

```bash
# Arch Linux Installation
sudo pacman -S postgresql postgresql-libs
yay -S pgvector

# Database Initialization
sudo -u postgres initdb -D /var/lib/postgres/data
sudo systemctl enable postgresql.service
sudo systemctl start postgresql.service

# Create Database User
sudo -u postgres createuser -P mcp_user
sudo -u postgres createdb -O mcp_user cognitive_memory

# Enable pgvector Extension
sudo -u postgres psql -d cognitive_memory -c "CREATE EXTENSION vector;"
```

**systemd (Service Management):**

```bash
# Version Check
systemctl --version
# Expected: systemd 253 or higher (Arch Linux default)

# Service File Location
/etc/systemd/system/cognitive-memory-mcp.service

# Service Management Commands
sudo systemctl daemon-reload
sudo systemctl enable cognitive-memory-mcp.service
sudo systemctl start cognitive-memory-mcp.service
sudo systemctl status cognitive-memory-mcp.service
```

**cron (Scheduled Tasks):**

```bash
# Version Check
cronie --version

# Crontab Entry (Story 3.2, 3.6)
# Edit: crontab -e
0 2 * * * /home/user/i-o/venv/bin/python /home/user/i-o/scripts/golden_test.py >> /var/log/cognitive-memory/golden-test.log 2>&1
0 3 * * * /home/user/i-o/scripts/backup.sh >> /var/log/cognitive-memory/backup.log 2>&1
```

**File System Requirements:**

| Path | Size | Purpose | Story |
|------|------|---------|-------|
| `/home/user/i-o` | ~500MB | Application directory | - |
| `/var/lib/postgres/data` | ~10GB | PostgreSQL data | - |
| `/backups/postgres` | ~70GB | Backup storage (7 days × 10GB) | 3.6 |
| `/var/log/cognitive-memory` | ~1GB | Logs (7-day retention) | 3.8 |
| `/home/user/i-o/memory/l2-insights` | ~500MB | Optional Git export | 3.6 |

### External Service Integrations

**OpenAI API (Embeddings):**

```python
# Configuration
OPENAI_API_KEY: str  # from .env.production
OPENAI_MODEL: "text-embedding-3-small"
OPENAI_EMBEDDING_DIM: 1536

# Endpoints Used
POST https://api.openai.com/v1/embeddings

# Pricing (as of 2025-11)
$0.020 per 1M tokens (~$0.00002 per embedding)

# Rate Limits
Tier 1: 3,000 RPM (Requests Per Minute)
Tier 1: 1,000,000 TPM (Tokens Per Minute)

# Error Handling (Story 3.3)
- 429 Rate Limit: Exponential backoff retry (4 attempts)
- 503 Service Unavailable: Retry
- Network Timeout: Retry (10s timeout)
- Hard Failure: No fallback (critical path)
```

**Anthropic API (Haiku Evaluation):**

```python
# Configuration
ANTHROPIC_API_KEY: str  # from .env.production
ANTHROPIC_MODEL: "claude-3-5-haiku-20241022"
ANTHROPIC_MAX_TOKENS: 500

# Endpoints Used
POST https://api.anthropic.com/v1/messages

# Pricing (as of 2025-11)
$1.00 per 1M input tokens
$5.00 per 1M output tokens
~$0.0025 per evaluation call (average)

# Rate Limits
Tier 1: 50 RPM
Tier 2: 1000 RPM (after verification)

# Error Handling (Story 3.3, 3.4)
- 429 Rate Limit: Exponential backoff retry (4 attempts)
- 503 Service Unavailable: Retry → Fallback to Claude Code
- Network Timeout: Retry → Fallback to Claude Code
- Hard Failure: Activate degraded mode (Claude Code Evaluation)
```

**Claude Code (Fallback Evaluation):**

```python
# Configuration
CLAUDE_CODE_FALLBACK_ENABLED: bool = True

# Integration Method
# Claude Code is invoked implicitly when running in the IDE
# No explicit API calls required

# Fallback Trigger
When Haiku API exhausts all retries (Story 3.4)

# Limitations
- Not available in headless mode (production concern)
- Evaluation quality may vary (no consistent temperature/prompting)
- Return value: Conservative reward score (0.5)
```

**GPT-4o (Judge - Epic 1 Dependency):**

```python
# Configuration
OPENAI_JUDGE_MODEL: "gpt-4o-2024-08-06"

# Endpoints Used
POST https://api.openai.com/v1/chat/completions

# Pricing
$2.50 per 1M input tokens
$10.00 per 1M output tokens

# Budget Impact (Epic 3)
Primary cost driver (~€4-6/mo for dual judge)
Reduced to €1-2/mo after Staged Dual Judge transition (Story 3.9)
```

### Configuration Dependencies

**Environment Variables (.env.production):**

```bash
# PostgreSQL Connection
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=cognitive_memory
DATABASE_USER=mcp_user
DATABASE_PASSWORD=<secret>

# OpenAI API
OPENAI_API_KEY=<secret>
OPENAI_MODEL=text-embedding-3-small

# Anthropic API
ANTHROPIC_API_KEY=<secret>
ANTHROPIC_MODEL=claude-3-5-haiku-20241022

# Environment
ENVIRONMENT=production

# Budget Limits
MONTHLY_BUDGET_LIMIT_EUR=10.0
BUDGET_ALERT_THRESHOLD_EUR=8.0

# Monitoring
GOLDEN_TEST_SCHEDULE="0 2 * * *"
BACKUP_SCHEDULE="0 3 * * *"
DRIFT_ALERT_THRESHOLD=0.05

# Fallback Configuration
CLAUDE_CODE_FALLBACK_ENABLED=true
HAIKU_HEALTH_CHECK_INTERVAL_SEC=900  # 15 minutes
```

**Configuration File (config.yaml):**

```yaml
# Referenced in Story 3.7
environment: production

development:
  database:
    host: localhost
    port: 5432
    name: cognitive_memory_dev
    user: mcp_user
  api_budgets:
    openai_monthly_eur: 1.0
    anthropic_monthly_eur: 3.0

production:
  database:
    host: localhost
    port: 5432
    name: cognitive_memory
    user: mcp_user
  api_budgets:
    openai_monthly_eur: 0.10
    anthropic_monthly_eur: 10.0

monitoring:
  golden_test_schedule: "0 2 * * *"
  backup_schedule: "0 3 * * *"
  drift_alert_threshold: 0.05

budget:
  monthly_limit_eur: 10.0
  alert_threshold_eur: 8.0

staged_dual_judge:
  transition_kappa_threshold: 0.85
  spot_check_rate: 0.05
  min_queries_before_transition: 100

retry:
  max_retries: 4
  base_delay_seconds: 1.0
  jitter_enabled: true

backup:
  retention_days: 7
  backup_dir: /backups/postgres
  l2_git_export_enabled: false
```

### Version Compatibility Matrix

**Tested Configurations:**

| Component | Version | Status | Notes |
|-----------|---------|--------|-------|
| **Python** | 3.11.6 | ✅ Tested | Arch Linux default |
| **PostgreSQL** | 15.8 | ✅ Tested | With pgvector 0.5.1 |
| **pgvector** | 0.5.1 | ✅ Tested | Latest stable |
| **systemd** | 253 | ✅ Tested | Arch Linux default |
| **OpenAI API** | v1 (2024-11) | ✅ Tested | text-embedding-3-small |
| **Anthropic API** | v1 (2024-11) | ✅ Tested | claude-3-5-haiku-20241022 |
| **mcp** | 0.9.0 | ✅ Tested | Latest stable |

**Incompatible Versions:**

| Component | Version | Issue |
|-----------|---------|-------|
| **Python** | <3.11 | Missing type hints (PEP 655) |
| **PostgreSQL** | <15 | pgvector compatibility issues |
| **pgvector** | <0.5.0 | Missing HNSW index support |
| **OpenAI API** | <1.0 | Legacy SDK, different error handling |

### Integration Points

**Epic 1 → Epic 3 Dependencies:**

```
Epic 1: MCP Server Implementation
  ├─ PostgreSQL Schema (all tables)
  ├─ OpenAI Embeddings Client
  ├─ Anthropic Haiku Client
  ├─ GPT-4o Judge Client
  └─ MCP Tool Interface

Epic 3: Production Readiness (THIS EPIC)
  ├─ ENHANCES: API Clients (retry logic)
  ├─ ADDS: Fallback mechanisms (Haiku → Claude Code)
  ├─ ADDS: 4 new tables (golden_test_set, model_drift_log, etc.)
  ├─ ADDS: Backup/restore scripts
  ├─ ADDS: systemd service
  └─ ADDS: Budget monitoring CLI
```

**Epic 2 → Epic 3 Dependencies:**

```
Epic 2: Working Memory Enhancements
  ├─ Hybrid Search (implemented in Epic 1, refined in Epic 2)
  ├─ Episode Memory (evaluates with Haiku API)
  └─ Dual Judge (GPT-4o + Haiku)

Epic 3: Production Readiness
  ├─ VALIDATES: Hybrid Search quality (Golden Test)
  ├─ MONITORS: Episode Memory quality (Model Drift Detection)
  └─ OPTIMIZES: Dual Judge cost (Staged Dual Judge)
```

**External Integration Workflows:**

1. **MCP Server → OpenAI API (Embeddings)**
   ```
   User Query
     ↓
   MCP Tool: hybrid_search()
     ↓
   create_embedding_with_retry()  [Epic 3 Enhancement]
     ├─ Retry Logic (4 attempts)
     ├─ api_retry_log tracking
     └─ Hard failure if exhausted (no fallback)
   ```

2. **MCP Server → Anthropic API (Haiku Evaluation)**
   ```
   Episode Memory Creation
     ↓
   haiku_evaluation_with_retry()  [Epic 3 Enhancement]
     ├─ Retry Logic (4 attempts)
     ├─ api_retry_log tracking
     └─ Fallback: Claude Code Evaluation  [Epic 3 New]
   ```

3. **MCP Server → PostgreSQL (Hybrid Search)**
   ```
   MCP Tool: hybrid_search()
     ↓
   pgvector Query
     ├─ HNSW Index (vector_cosine_ops)
     ├─ BM25 Full-Text Search
     └─ RRF Fusion (weights: 0.5/0.5)
   ```

4. **Cron → PostgreSQL (Daily Drift Detection)**
   ```
   Daily Cron (2 AM)
     ↓
   golden_test.py
     ├─ Load golden_test_set
     ├─ Run hybrid_search for each query
     ├─ Calculate Precision@5
     └─ Store in model_drift_log
   ```

5. **Cron → File System (Daily Backup)**
   ```
   Daily Cron (3 AM)
     ↓
   backup.sh
     ├─ pg_dump → /backups/postgres/YYYY-MM-DD.dump
     ├─ Optional: L2 Insights → JSON export
     └─ Delete backups >7 days old
   ```

### Deployment Dependencies

**Minimum System Requirements:**

- **OS:** Arch Linux (or compatible systemd-based distro)
- **CPU:** 2 cores (4 recommended for parallel processing)
- **RAM:** 4GB (8GB recommended for large databases)
- **Disk:** 100GB free (50GB for backups, 30GB for PostgreSQL, 20GB for logs/other)
- **Network:** Stable internet connection (for OpenAI/Anthropic API calls)

**Pre-Deployment Checklist (Story 3.12):**

- [ ] PostgreSQL 15+ installed and running
- [ ] pgvector extension enabled
- [ ] Python 3.11+ installed
- [ ] All dependencies installed (`pip install -e .`)
- [ ] `.env.production` configured with valid API keys
- [ ] `config.yaml` reviewed and customized
- [ ] Database schema initialized (Epic 1 migrations + Epic 3 tables)
- [ ] systemd service file installed
- [ ] Cron jobs configured (Golden Test, Backup)
- [ ] Backup directory created (`/backups/postgres`)
- [ ] Log directory created (`/var/log/cognitive-memory`)
- [ ] Permissions verified (chmod 600 for secrets, backups)

**Dependency Installation Script:**

```bash
#!/bin/bash
# scripts/install_dependencies.sh (Story 3.12)

set -e

echo "Installing system dependencies..."
sudo pacman -S --needed postgresql python python-pip
yay -S --needed pgvector

echo "Setting up Python environment..."
python -m venv venv
source venv/bin/activate
pip install -e .

echo "Initializing PostgreSQL..."
sudo systemctl enable postgresql.service
sudo systemctl start postgresql.service

echo "Creating database..."
sudo -u postgres createuser -P mcp_user
sudo -u postgres createdb -O mcp_user cognitive_memory
sudo -u postgres psql -d cognitive_memory -c "CREATE EXTENSION vector;"

echo "Running database migrations..."
python scripts/migrate_database.py

echo "Installing systemd service..."
sudo cp systemd/cognitive-memory-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "Setting up cron jobs..."
crontab -l > /tmp/crontab.bak || true
echo "0 2 * * * /home/user/i-o/venv/bin/python /home/user/i-o/scripts/golden_test.py >> /var/log/cognitive-memory/golden-test.log 2>&1" >> /tmp/crontab.bak
echo "0 3 * * * /home/user/i-o/scripts/backup.sh >> /var/log/cognitive-memory/backup.log 2>&1" >> /tmp/crontab.bak
crontab /tmp/crontab.bak

echo "Creating directories..."
sudo mkdir -p /backups/postgres /var/log/cognitive-memory
sudo chown ethr:ethr /backups/postgres /var/log/cognitive-memory

echo "Installation complete!"
echo "Next steps:"
echo "1. Configure .env.production with API keys"
echo "2. Review config.yaml"
echo "3. Start service: sudo systemctl start cognitive-memory-mcp.service"
echo "4. Check status: sudo systemctl status cognitive-memory-mcp.service"
```

## Acceptance Criteria and Traceability

### Story-Level Acceptance Criteria

#### Story 3.1: Golden Test Set Creation

**Given** L0 Raw Memory und L2 Insights existieren
**When** ich Golden Test Set erstelle
**Then** werden 50-100 Queries extrahiert:
- Source: Automatisch aus L0 Raw Memory (unterschiedliche Sessions als Ground Truth)
- Stratification: 40% Short, 40% Medium, 20% Long
- Temporal Diversity: Keine Überlappung mit Ground Truth Sessions
- Labeling: Manuelle Relevanz-Labels via Streamlit UI

**And** Golden Test Set wird in separater Tabelle gespeichert:
- Tabelle: `golden_test_set` (id, query, expected_docs, created_at, query_type)
- query_type: "short" | "medium" | "long" für Stratification-Tracking

**And** Golden Set ist immutable nach Erstellung:
- Keine Updates nach Initial Labeling
- Separates Set verhindert Overfitting auf Ground Truth
- Expected Size: 50-100 Queries (statistical power >0.80)

**Prerequisites:** Epic 2 abgeschlossen
**Validation:**
- ✅ Golden set table exists with 50-100 queries
- ✅ Stratification verified: 40% short, 40% medium, 20% long
- ✅ No session overlap with ground truth
- ✅ All queries have expected_docs labels

---

#### Story 3.2: Model Drift Detection

**Given** Golden Test Set existiert
**When** das Tool `get_golden_test_results` aufgerufen wird (täglich via Cron)
**Then** werden alle Golden Queries getestet:
- Führe `hybrid_search` für alle 50-100 Queries aus
- Vergleiche Top-5 Ergebnisse mit expected_docs
- Berechne Precision@5 für jede Query
- Aggregiere zu Daily Precision@5 Metric

**And** Metrics werden in `model_drift_log` Tabelle gespeichert:
- Columns: date, precision_at_5, num_queries, avg_retrieval_time, embedding_model_version
- Neue Zeile pro Tag (historische Tracking)

**And** Drift Detection Alert wird getriggert:
- Condition: Precision@5 drop >5% gegenüber Rolling 7-Day Average
- Action: Log Warning + optional Email/Slack Alert
- Example: Baseline P@5=0.78, Current P@5=0.73 → Alert

**And** das Tool gibt tägliche Metriken zurück:
- Response: {date, precision_at_5, drift_detected, baseline_p5, current_p5}

**Prerequisites:** Story 3.1
**Validation:**
- ✅ Cron job runs daily at 2 AM
- ✅ model_drift_log table populated daily
- ✅ Drift alert triggers when P@5 drops >5%
- ✅ 7-day rolling average calculated correctly

---

#### Story 3.3: API Retry-Logic Enhancement

**Given** ein External API Call schlägt fehl
**When** Retry-Logic getriggert wird
**Then** wird Exponential Backoff ausgeführt:
- Delays: 1s, 2s, 4s, 8s (4 Retries total)
- Jitter: ±20% Random Delay
- Total Max Time: ~15s

**And** Retry-Logic ist für alle API-Typen implementiert:
1. OpenAI Embeddings API: Retry bei 429, 503, Timeout → Error nach 4 failures
2. Anthropic Haiku API (Evaluation): Retry → Fallback to Claude Code
3. Anthropic Haiku API (Reflexion): Retry → Skip if failed
4. GPT-4o + Haiku Dual Judge: Retry → Log Error

**And** Retry-Statistiken werden geloggt:
- Tabelle: `api_retry_log` (timestamp, api_name, error_type, retry_count, success)

**Prerequisites:** Story 2.4
**Validation:**
- ✅ All API clients implement exponential backoff
- ✅ Jitter prevents thundering herd
- ✅ api_retry_log tracks all retry attempts
- ✅ Max retry time ≤15s verified

---

#### Story 3.4: Claude Code Fallback

**Given** Haiku API ist nach 4 Retries nicht erreichbar
**When** Fallback zu Claude Code getriggert wird
**Then** wird alternative Evaluation durchgeführt:
- Fallback-Modus: Claude Code führt Self-Evaluation intern durch
- Prompt: Gleiche Evaluation-Kriterien wie Haiku
- Output: Reward Score -1.0 bis +1.0

**And** Fallback-Status wird geloggt:
- Log Entry: `fallback_mode_active: true`, `reason: "haiku_api_unavailable"`
- Warning-Message an User: "System running in degraded mode"
- Timestamp: Wann aktiviert, wann deaktiviert

**And** automatische Recovery nach API-Wiederherstellung:
- Periodic Health Check: Alle 15 Minuten Haiku API Ping
- Falls Ping erfolgreich: Deaktiviere Fallback, log Recovery
- Keine manuelle Intervention erforderlich

**And** Fallback-Quality wird dokumentiert:
- Erwartung: Claude Code ~5-10% weniger konsistent als Haiku
- Trade-off: Verfügbarkeit > perfekte Konsistenz

**Prerequisites:** Story 3.3
**Validation:**
- ✅ Fallback activates after retry exhaustion
- ✅ Health check pings every 15 minutes
- ✅ Auto-recovery when API restored
- ✅ Degraded mode logged and reported

---

#### Story 3.5: Latency Benchmarking

**Given** das System läuft mit realistischen Daten
**When** Latency Benchmarking durchgeführt wird
**Then** werden 100 Test-Queries gemessen:
- Query Mix: 40 Short, 40 Medium, 20 Long
- Measured Metrics: End-to-End, Breakdown (Embedding, Search, CoT, Evaluation)
- Percentiles: p50, p95, p99

**And** Performance-Ziele werden validiert:
- p95 End-to-End Latency: <5s (NFR001)
- p95 Retrieval Time: <1s (Hybrid Search)
- p50 End-to-End Latency: <3s

**And** bei Performance-Problemen → Optimierung:
- Falls Hybrid Search >1s p95: Prüfe pgvector Index (HNSW?)
- Falls CoT Generation >3s p95: Kürze Context, optimize Prompt
- Falls Evaluation >1s p95: Prüfe Haiku API Latency, erwäge Batch

**And** Latency-Metriken werden dokumentiert:
- Dokumentation: `/docs/performance-benchmarks.md`
- Baseline für zukünftige Regression Tests

**Prerequisites:** Epic 2 abgeschlossen
**Validation:**
- ✅ 100 test queries executed
- ✅ p95 end-to-end <5s verified
- ✅ Performance benchmarks documented
- ✅ Optimization applied if needed

---

#### Story 3.6: PostgreSQL Backup Strategy

**Given** PostgreSQL läuft mit Production-Daten
**When** Backup-Strategie implementiert wird
**Then** werden tägliche Backups erstellt:
- Tool: `pg_dump` (Custom Format `-Fc`)
- Schedule: Täglich 3 Uhr nachts via Cron
- Target: `/backups/postgres/cognitive_memory_YYYY-MM-DD.dump`

**And** Backup-Rotation mit 7-day Retention:
- Script löscht Backups älter als 7 Tage
- Disk Space: ~1-2 GB pro Backup

**And** L2 Insights in Git als Read-Only Fallback:
- Täglicher Export: L2 Insights → JSON
- Git Commit + Push (optional, konfigurierbar)
- Rationale: Text ist klein, Embeddings re-generated

**And** Recovery-Prozedur ist dokumentiert:
- RTO: <1 hour
- RPO: <24 hours
- Dokumentation: `/docs/backup-recovery.md`

**And** Backup-Success wird geloggt:
- Log Entry: timestamp, backup_size, success/failure
- Alert bei 2 aufeinanderfolgenden Failures

**Prerequisites:** Story 1.2
**Validation:**
- ✅ Cron job runs daily at 3 AM
- ✅ Backups created in correct format
- ✅ Rotation deletes old backups
- ✅ Recovery procedure tested and documented

---

#### Story 3.7: Production Configuration

**Given** Development-Environment funktioniert
**When** Production-Environment erstellt wird
**Then** existieren separate Konfigurationen:

1. Environment Files: `.env.development`, `.env.production`, `.env.template`
2. Database Separation: `cognitive_memory_dev` vs. `cognitive_memory`
3. Configuration Management: `config.yaml` mit environment-specific Overrides

**And** Secrets Management:
- API Keys: Nur in .env Files (NICHT in Git)
- DB Credentials: Nur in .env Files
- `.gitignore` enthält: `.env.production`, `.env.development`

**And** Production Checklist ist dokumentiert:
- `/docs/production-checklist.md` mit allen Setup-Schritten

**Prerequisites:** Epic 2 abgeschlossen
**Validation:**
- ✅ .env.production configured with real API keys
- ✅ Separate dev/prod databases verified
- ✅ Secrets not in git (gitignore working)
- ✅ Production checklist complete

---

#### Story 3.8: MCP Server Daemonization

**Given** Production-Environment ist konfiguriert
**When** MCP Server als Daemon konfiguriert wird
**Then** läuft der Server persistent:

1. Systemd Service: `/etc/systemd/system/cognitive-memory-mcp.service`
2. Auto-Start bei Boot: `systemctl enable`
3. Logging: systemd Journal + `/var/log/cognitive-memory/mcp.log`

**And** Service Management Commands:
- Start: `systemctl start cognitive-memory-mcp`
- Stop: `systemctl stop cognitive-memory-mcp`
- Status: `systemctl status cognitive-memory-mcp`

**And** Health Monitoring:
- Systemd Watchdog: Timeout 60s
- Falls kein Heartbeat: Auto-Restart
- Health Check Endpoint: `/health`

**Prerequisites:** Story 3.7
**Validation:**
- ✅ Service starts on boot
- ✅ Auto-restart after crashes
- ✅ Watchdog monitoring active
- ✅ Logs written to journal and file

---

#### Story 3.9: Staged Dual Judge Implementation

**Given** System läuft 3 Monate in Production mit Dual Judge
**When** Staged Dual Judge Transition evaluiert wird
**Then** wird IRR-Stabilität geprüft:
- Condition für Transition: Kappa >0.85 über letzten 100 Ground Truth Queries
- Rationale: Kappa >0.85 = "Almost Perfect Agreement"

**And** falls Kappa >0.85 → aktiviere Single Judge Mode:
- Phase 2 Config: `dual_judge_enabled: false`
- Primary Judge: GPT-4o
- Spot Checks: 5% Random Sampling mit Haiku
- Cost Reduction: €2-3/mo statt €5-10/mo

**And** falls Kappa <0.85 → bleibe in Dual Judge Mode:
- Log Warning: "IRR below threshold"
- Continue Dual Judge für weitere 1 Monat
- Re-evaluate nach 4 Monaten

**And** Spot Check Mechanismus:
- Random Sampling: 5% aller neuen Ground Truth Queries
- Beide Judges aufrufen (GPT-4o + Haiku)
- Falls Kappa <0.70 auf Spot Checks → Revert zu Full Dual Judge

**Prerequisites:** Stories 1.11-1.12
**Validation:**
- ✅ Kappa calculation over 100 queries
- ✅ Transition threshold (>0.85) verified
- ✅ Spot check sampling (5%) implemented
- ✅ Cost reduction achieved

---

#### Story 3.10: Budget Monitoring Dashboard

**Given** System läuft in Production mit externen APIs
**When** Budget-Monitoring abgefragt wird
**Then** sind folgende Metriken verfügbar:

1. Daily Cost Tracking: `api_cost_log` (date, api_name, num_calls, token_count, estimated_cost)
2. Monthly Aggregation: `SUM(estimated_cost)` über 30 Tage, Breakdown per API
3. Budget Alert: Threshold €10/mo, Alert bei projected overage

**And** Cost Optimization Insights:
- Highest Cost API: Identifiziere teuerste API
- Query Volume: Correlate Cost mit Query Volume
- Reflexion Rate: Hohe Rate (>30%) = hohe Kosten

**And** Simple CLI Dashboard:
- Command: `mcp-server budget-report --days 30`
- Output: Daily/Monthly Costs, Breakdown per API, Projected Monthly Cost

**Prerequisites:** Story 2.4
**Validation:**
- ✅ api_cost_log tracks all API calls
- ✅ Monthly aggregation accurate
- ✅ Budget alert triggers at threshold
- ✅ CLI dashboard functional

---

#### Story 3.11: 7-Day Stability Testing

**Given** alle Epic 3 Stories sind implementiert
**When** 7-Day Stability Test durchgeführt wird
**Then** läuft das System kontinuierlich:
- Duration: 7 Tage (168 Stunden) ohne manuellen Restart
- Query Load: Mindestens 10 Queries/Tag (70 Queries total)
- No Critical Crashes: MCP Server Auto-Recovery bei minor Errors

**And** folgende Metriken werden gemessen:
1. Uptime: 100% (Server läuft durchgehend)
2. Query Success Rate: >99% (max. 1 Failed Query)
3. Latency: p95 <5s über alle 70 Queries
4. API Reliability: Retry-Logic erfolgreich
5. Budget: Total Cost <€2 für 7 Tage

**And** bei Problemen → Root Cause Analysis:
- Falls Crashes: Analyze logs, fix bug, restart test
- Falls Latency >5s: Profile code, optimize
- Falls Budget Overage: Identify cost driver, optimize API usage

**And** Success-Dokumentation:
- `/docs/7-day-stability-report.md` mit allen Metriken

**Prerequisites:** Stories 3.1-3.10
**Validation:**
- ✅ 168 hours uptime achieved
- ✅ >99% query success rate
- ✅ p95 latency <5s verified
- ✅ Budget <€2 for 7 days
- ✅ Stability report documented

---

#### Story 3.12: Production Handoff & Documentation

**Given** alle Features sind implementiert und getestet
**When** Dokumentation finalisiert wird
**Then** existieren folgende Dokumente:

1. `/docs/README.md` - Projekt-Overview
2. `/docs/installation-guide.md` - Setup von Scratch
3. `/docs/operations-manual.md` - Daily Operations
4. `/docs/troubleshooting.md` - Common Issues
5. `/docs/backup-recovery.md` - Disaster Recovery
6. `/docs/api-reference.md` - MCP Tools & Resources

**And** Code-Kommentierung:
- Alle wichtigen Funktionen haben Docstrings
- Komplexe Logik hat Inline-Comments
- Config-Dateien haben Kommentare

**And** Knowledge Transfer:
- Optional: 1-2 Sessions mit ethr zum Walkthrough
- Dokumentation ist self-service-tauglich

**Prerequisites:** Stories 3.1-3.11
**Validation:**
- ✅ All 6 documentation files complete
- ✅ Code docstrings present
- ✅ Self-service documentation tested
- ✅ Troubleshooting guide covers common issues

---

### Traceability Matrix

**PRD Functional Requirements → Epic 3 Stories:**

| PRD Requirement | Epic 3 Story | Implementation | Validation |
|-----------------|--------------|----------------|------------|
| **NFR001: Latency** | Story 3.5 | Latency Benchmarking (p95 <5s) | 100 test queries, performance doc |
| **NFR003: Budget** | Story 3.10 | Budget Monitoring Dashboard | api_cost_log, monthly aggregation |
| **NFR004: Reliability** | Story 3.3, 3.4, 3.6, 3.8 | Retry Logic, Fallback, Backup, Daemonization | 7-day stability test |
| **Enhancement E7** | Story 3.2 | Model Drift Detection | Daily Golden Test, drift alerts |
| **Enhancement E8** | Story 3.9 | Staged Dual Judge | Kappa >0.85 transition, cost reduction |
| **Production Readiness** | Story 3.7, 3.8, 3.11, 3.12 | Config, Daemon, Testing, Docs | Production checklist, stability report |

**PRD Non-Functional Requirements → Epic 3 Features:**

| NFR | Target | Epic 3 Implementation | Measured By |
|-----|--------|----------------------|-------------|
| **NFR001: Performance** | <5s p95 | Story 3.5: Latency Benchmarking | `/docs/performance-benchmarks.md` |
| **NFR002: Data Loss** | No critical loss | Story 3.6: Backup Strategy (RPO <24h, RTO <1h) | Backup logs, recovery test |
| **NFR003: Budget** | €5-10/mo → €2-3/mo | Story 3.10: Budget Monitoring, Story 3.9: Staged Dual Judge | api_cost_log, monthly report |
| **NFR004: Reliability** | >99% Uptime | Story 3.3: Retry Logic, Story 3.4: Fallback, Story 3.8: Auto-Restart | 7-day stability test (Story 3.11) |
| **NFR005: Observability** | Logs + Metrics | Story 3.2: Drift Tracking, Story 3.3: Retry Logs, Story 3.10: Cost Logs | PostgreSQL tables, systemd journal |

**PRD Enhancements → Epic 3 Stories:**

| Enhancement | Description | Epic 3 Story | Success Metric |
|-------------|-------------|--------------|----------------|
| **E7: Model Drift Detection** | Daily Precision@5 validation | Story 3.2 | Drift alerts when P@5 drops >5% |
| **E8: Staged Dual Judge** | Cost reduction after 3 months | Story 3.9 | €5-10/mo → €2-3/mo (-40%) |

**Epic 3 Story Dependencies:**

```
Story 3.1: Golden Test Set Creation
  └─ Story 3.2: Model Drift Detection
       └─ Story 3.11: 7-Day Stability Testing

Story 3.3: API Retry Logic
  └─ Story 3.4: Claude Code Fallback
       └─ Story 3.11: 7-Day Stability Testing

Story 3.5: Latency Benchmarking
  └─ Story 3.11: 7-Day Stability Testing

Story 3.6: PostgreSQL Backup
  └─ Story 3.11: 7-Day Stability Testing

Story 3.7: Production Configuration
  └─ Story 3.8: MCP Server Daemonization
       └─ Story 3.11: 7-Day Stability Testing

Story 3.10: Budget Monitoring
  └─ Story 3.9: Staged Dual Judge (after 3 months)
       └─ Story 3.11: 7-Day Stability Testing

Stories 3.1-3.11: All Production Features
  └─ Story 3.12: Production Handoff & Documentation
```

### Definition of Done (DoD)

**Epic 3 Story-Level DoD:**

For each story to be considered "DONE", the following criteria must be met:

1. **Code Implementation:**
   - ✅ All acceptance criteria implemented
   - ✅ Code reviewed and merged to main branch
   - ✅ No critical bugs or security vulnerabilities
   - ✅ Docstrings added for all new functions

2. **Testing:**
   - ✅ Unit tests written and passing (where applicable)
   - ✅ Integration tests passing
   - ✅ Manual testing completed
   - ✅ Performance tested (if latency-critical)

3. **Database:**
   - ✅ Schema changes migrated (new tables/columns)
   - ✅ Indexes created for performance
   - ✅ Data validated (no corruption)

4. **Configuration:**
   - ✅ Config files updated (.env, config.yaml)
   - ✅ Secrets management verified
   - ✅ Environment separation (dev/prod) working

5. **Documentation:**
   - ✅ Inline code comments added
   - ✅ User-facing documentation updated
   - ✅ API reference updated (if new tools/resources)
   - ✅ Troubleshooting guide updated (if needed)

6. **Deployment:**
   - ✅ Changes deployed to production
   - ✅ Service restarted successfully (if needed)
   - ✅ Monitoring/logging verified
   - ✅ No regressions detected

7. **Validation:**
   - ✅ All validation checkpoints passed
   - ✅ Success metrics measured
   - ✅ User acceptance (ethr) confirmed

**Epic-Level DoD (Epic 3 Complete):**

For Epic 3 to be considered "DONE":

1. **All Stories Complete:**
   - ✅ All 12 stories meet Story-Level DoD
   - ✅ No open bugs or blockers
   - ✅ No technical debt documented

2. **Integration Testing:**
   - ✅ 7-Day Stability Test passed (Story 3.11)
   - ✅ All monitoring systems operational
   - ✅ Backup/restore tested successfully

3. **Performance Validation:**
   - ✅ p95 Latency <5s verified
   - ✅ Budget <€10/mo verified
   - ✅ Uptime >99% verified

4. **Documentation Complete:**
   - ✅ All 6 documentation files finalized
   - ✅ Production checklist validated
   - ✅ Operations manual reviewed by ethr

5. **Production Readiness:**
   - ✅ Production environment configured
   - ✅ systemd service running
   - ✅ Cron jobs scheduled
   - ✅ Backups created and verified

6. **Knowledge Transfer:**
   - ✅ ethr can operate system independently
   - ✅ Troubleshooting guide tested
   - ✅ Emergency procedures documented

### Epic-Level Success Criteria

**Epic 3: Production Readiness Success Criteria:**

| Criterion | Target | Measurement | Status |
|-----------|--------|-------------|--------|
| **7-Day Stability** | 168h uptime, >99% success rate | Story 3.11 stability report | Pending |
| **Query Performance** | p95 <5s end-to-end latency | 100 test queries (Story 3.5) | Pending |
| **Budget Compliance** | €5-10/mo (first 3 months) | api_cost_log monthly aggregation | Pending |
| **Model Drift Detection** | Daily Golden Test operational | Cron job + model_drift_log | Pending |
| **API Reliability** | Retry logic + fallback working | api_retry_log, fallback logs | Pending |
| **Backup Recovery** | RTO <1h, RPO <24h | Recovery test documentation | Pending |
| **Documentation Complete** | All 6 docs finalized | Documentation review | Pending |
| **Production Deployment** | systemd service active | systemctl status check | Pending |

**Critical Path to Success:**

1. **Phase 1: Foundation (Stories 3.1-3.6)** - ~30h
   - Golden Test Set Creation
   - Model Drift Detection
   - API Retry Logic + Fallback
   - Latency Benchmarking
   - Backup Strategy

2. **Phase 2: Production Setup (Stories 3.7-3.8)** - ~10h
   - Production Configuration
   - systemd Daemonization

3. **Phase 3: Optimization (Stories 3.9-3.10)** - ~15h
   - Staged Dual Judge (after 3 months)
   - Budget Monitoring

4. **Phase 4: Validation (Stories 3.11-3.12)** - ~25h
   - 7-Day Stability Testing
   - Production Handoff & Documentation

**Total Estimated Timeline:** 60-80 hours (3-4 weeks at 20h/week)

**Budget Success Metrics:**

- **Month 1-3:** €5-10/mo (Dual Judge + Full Evaluation)
- **Month 4+:** €2-3/mo (Single Judge + 5% Spot Checks)
- **Cost Reduction:** -40% after Staged Dual Judge transition

**Quality Success Metrics:**

- **Precision@5:** >0.75 maintained (verified via Golden Test)
- **Model Drift Detection:** <5% drop triggers alert
- **Query Success Rate:** >99% over 7-day test
- **Uptime:** >99% (auto-restart on failures)

**Operational Success Metrics:**

- **Recovery Time:** <1 hour (backup restore)
- **Deployment Time:** <30 minutes (service restart)
- **Troubleshooting Time:** <1 hour for common issues (via docs)
- **Maintenance Time:** <2 hours/month (monitoring, updates)

## Risks and Test Strategy

### Risk Assessment

**Epic 3: Production Readiness Risk Register:**

| Risk ID | Risk Description | Likelihood | Impact | Severity | Mitigation Strategy |
|---------|------------------|------------|--------|----------|---------------------|
| **R3.1** | Model Drift goes undetected for >7 days | Low | High | **Medium** | Daily Golden Test (Story 3.2), drift alerts at >5% drop |
| **R3.2** | API Budget Overage (>€10/mo) | Medium | Medium | **Medium** | Budget monitoring dashboard (Story 3.10), monthly alerts |
| **R3.3** | OpenAI Embeddings API failure (no fallback) | Low | Critical | **High** | Retry logic (Story 3.3), no fallback available (hard failure acceptable) |
| **R3.4** | Haiku API prolonged outage (>24h) | Very Low | Medium | **Low** | Claude Code fallback (Story 3.4), auto-recovery health checks |
| **R3.5** | PostgreSQL data corruption | Very Low | Critical | **High** | Daily backups (Story 3.6), 7-day retention, tested recovery procedure |
| **R3.6** | Latency degradation (p95 >5s) | Medium | Medium | **Medium** | Latency benchmarking (Story 3.5), pgvector index optimization |
| **R3.7** | systemd service crash loop | Low | High | **Medium** | Auto-restart policy (Story 3.8), watchdog monitoring |
| **R3.8** | Backup failure (2+ consecutive days) | Low | High | **Medium** | Backup success logging, alert on 2 failures, manual intervention |
| **R3.9** | Golden Test Set becomes stale | Medium | Low | **Low** | Immutable set design, re-create if domain shift detected (manual) |
| **R3.10** | Staged Dual Judge transition premature | Low | Medium | **Low** | Kappa >0.85 threshold enforced, spot checks with revert mechanism |
| **R3.11** | 7-Day Stability Test failure | Medium | High | **High** | Iterative testing (max 3 attempts), root cause analysis, bug fixes |
| **R3.12** | Production secrets leak (API keys in Git) | Low | Critical | **High** | .gitignore enforcement, chmod 600 on .env files, pre-commit hooks |

**Risk Severity Calculation:**

- **Critical Impact + Medium Likelihood** = **High Severity** (R3.3, R3.5)
- **High Impact + Medium Likelihood** = **High Severity** (R3.11)
- **Medium Impact + Medium Likelihood** = **Medium Severity** (R3.1, R3.2, R3.6)
- **Critical Impact + Low Likelihood** = **High Severity** (R3.12)

### Risk Mitigation Strategies

#### R3.1: Model Drift Undetected

**Scenario:** OpenAI updates text-embedding-3-small model, causing Precision@5 to degrade slowly over weeks.

**Mitigation:**
1. **Daily Golden Test (Story 3.2):** Automated detection within 24h
2. **7-Day Rolling Average:** Reduces false positives from daily noise
3. **Drift Alert Threshold:** >5% drop triggers immediate warning
4. **Manual Re-Calibration:** If drift confirmed, re-run Grid Search (Epic 2) with new embeddings

**Residual Risk:** Low (alert system ensures detection within 1 day)

---

#### R3.2: API Budget Overage

**Scenario:** Query volume increases unexpectedly, pushing monthly cost to €15/mo.

**Mitigation:**
1. **Budget Dashboard (Story 3.10):** CLI tool shows projected monthly cost
2. **Budget Alert:** Warning at €8/mo projected (before €10/mo limit)
3. **Cost Analysis:** Identify high-cost API (e.g., excessive Reflexion calls)
4. **Optimization Levers:**
   - Reduce Reflexion frequency (if >30% of queries)
   - Transition to Staged Dual Judge early (Story 3.9)
   - Reduce Golden Test frequency (daily → weekly)

**Residual Risk:** Low (early warning allows proactive optimization)

---

#### R3.3: OpenAI Embeddings API Failure

**Scenario:** OpenAI API down for >1 hour, making Hybrid Search impossible.

**Mitigation:**
1. **Retry Logic (Story 3.3):** 4 retries with exponential backoff (15s max)
2. **No Fallback:** Embeddings are critical path (no alternative provider)
3. **Acceptable Downtime:** OpenAI SLA ~99.9% uptime (4.3h/month downtime expected)
4. **User Communication:** "Retrieval temporarily unavailable, try again shortly"

**Residual Risk:** Medium (no mitigation beyond retry logic, hard failure accepted)

**Trade-off:** Switching to alternative embeddings provider (e.g., Voyage AI) would require re-embedding all L2 Insights (costly, out of scope v3.1)

---

#### R3.4: Haiku API Prolonged Outage

**Scenario:** Anthropic Haiku API unavailable for 24+ hours.

**Mitigation:**
1. **Claude Code Fallback (Story 3.4):** Degraded mode evaluation
2. **Health Check (15min interval):** Auto-recovery when API restored
3. **Quality Trade-off:** Claude Code evaluation ~5-10% less consistent
4. **Acceptable Degradation:** Availability > perfect consistency

**Residual Risk:** Very Low (fallback ensures system continues operating)

---

#### R3.5: PostgreSQL Data Corruption

**Scenario:** Disk failure or software bug corrupts database.

**Mitigation:**
1. **Daily Backups (Story 3.6):** pg_dump every night (3 AM)
2. **7-Day Retention:** Multiple recovery points available
3. **L2 Insights Git Export:** Text-only fallback (embeddings can be re-generated)
4. **Tested Recovery Procedure:** RTO <1h, RPO <24h documented

**Residual Risk:** Very Low (worst case: lose <24h of data, recover from backup)

**Additional Protection:**
- PostgreSQL transaction logs (WAL) for point-in-time recovery
- RAID storage (if available) for disk redundancy

---

#### R3.6: Latency Degradation

**Scenario:** Database grows to 100K L2 Insights, Hybrid Search slows to p95 >5s.

**Mitigation:**
1. **Latency Benchmarking (Story 3.5):** Baseline established at 10K insights
2. **pgvector Index Optimization:** Switch IVFFlat → HNSW if needed
3. **Query Optimization:** Analyze slow queries, add indexes
4. **Capacity Planning:** Monitor DB size, estimate latency growth

**Residual Risk:** Low (multiple optimization levers available)

**Trigger for Action:** When p95 latency exceeds 4s (before 5s threshold), run optimization

---

#### R3.7: systemd Service Crash Loop

**Scenario:** Bug causes MCP Server to crash every 10 minutes.

**Mitigation:**
1. **Auto-Restart Policy (Story 3.8):** systemd restarts service automatically
2. **Watchdog Monitoring:** Detects crash loop (timeout 60s)
3. **Error Logging:** systemd journal captures stack traces
4. **Manual Intervention:** If crash loop persists >5 times, systemd stops auto-restart (safety)

**Residual Risk:** Low (auto-restart handles transient errors, persistent errors require manual fix)

**Prevention:**
- Comprehensive testing (Story 3.11: 7-Day Stability Test)
- Error handling in critical paths (try/except blocks)

---

#### R3.8: Backup Failure

**Scenario:** Backup script fails due to disk space full or permission error.

**Mitigation:**
1. **Backup Success Logging:** Each backup logged with timestamp + status
2. **Alert on 2 Consecutive Failures:** Indicates persistent issue (not transient)
3. **Manual Intervention:** ethr checks logs, fixes issue (disk cleanup, permissions)
4. **Backup Rotation:** Prevents disk overflow (7-day retention)

**Residual Risk:** Low (early detection allows quick fix before critical data loss)

---

#### R3.9: Golden Test Set Becomes Stale

**Scenario:** Domain shift (ethr starts asking different types of questions), Golden Set no longer representative.

**Mitigation:**
1. **Immutable Design:** Golden Set fixed after creation (no updates)
2. **Drift Detection Still Valid:** Measures relative performance change (not absolute quality)
3. **Manual Re-Creation:** If major domain shift detected, create new Golden Set
4. **Version Tracking:** Golden Set v1, v2, etc. with creation date

**Residual Risk:** Low (Golden Set purpose is regression detection, not absolute quality validation)

**Note:** Ground Truth Set (Epic 1) is separate and can be expanded for new domains

---

#### R3.10: Staged Dual Judge Transition Premature

**Scenario:** Kappa >0.85 achieved but Single Judge quality degrades in production.

**Mitigation:**
1. **Strict Transition Condition:** Kappa >0.85 over 100 queries (high confidence)
2. **Spot Check Mechanism (5%):** Continuous monitoring after transition
3. **Revert Trigger:** If spot check Kappa <0.70, revert to Dual Judge automatically
4. **Grace Period:** Wait 3 months minimum before considering transition

**Residual Risk:** Very Low (spot checks ensure ongoing quality validation)

---

#### R3.11: 7-Day Stability Test Failure

**Scenario:** System crashes on Day 3, test fails.

**Mitigation:**
1. **Root Cause Analysis:** Analyze systemd logs, identify crash cause
2. **Bug Fix:** Fix identified issue
3. **Restart Test:** Max 3 iterations allowed (prevents infinite loop)
4. **Success Criteria Adjustment:** If persistent issues, adjust criteria (e.g., allow 1-2 minor crashes)

**Residual Risk:** Medium (test is strict, may require multiple iterations)

**Contingency:** If 3 iterations fail, escalate to deeper architecture review

---

#### R3.12: Production Secrets Leak

**Scenario:** .env.production accidentally committed to Git, API keys exposed.

**Mitigation:**
1. **.gitignore Enforcement:** .env.production excluded from Git
2. **chmod 600:** Only owner can read .env files
3. **Pre-Commit Hooks:** (Optional) Scan for secrets before commit
4. **API Key Rotation:** If leak detected, immediately rotate keys

**Residual Risk:** Low (multiple layers of protection)

**Recovery Plan:**
1. Immediately revoke leaked API keys (OpenAI/Anthropic dashboards)
2. Generate new keys, update .env.production
3. Restart MCP Server with new keys

---

### Test Strategy

**Epic 3 Test Pyramid:**

```
                  /\
                 /  \
                /    \
               /  E2E \        7-Day Stability Test (Story 3.11)
              /--------\       70+ queries, full system validation
             /          \
            / Integration\     Daily Golden Test, Backup/Restore
           /--------------\    Model Drift Detection, API Retry
          /                \
         /   Unit Tests      \  Golden Test logic, Retry logic
        /____________________\ Budget calculations, Config parsing
```

#### Unit Tests

**Scope:** Individual functions and modules in isolation.

**Test Coverage (Story-Level):**

| Story | Unit Test Coverage | Test Cases |
|-------|-------------------|------------|
| **Story 3.1** | Golden Test Set creation logic | - Stratification (40/40/20 verification)<br>- Query deduplication<br>- Session exclusion (no GT overlap) |
| **Story 3.2** | Precision@5 calculation | - Macro-average calculation<br>- Drift detection threshold (>5%)<br>- Rolling average (7-day window) |
| **Story 3.3** | Exponential backoff retry logic | - Delay calculation (1s, 2s, 4s, 8s)<br>- Jitter application (±20%)<br>- Max retries enforcement (4 attempts) |
| **Story 3.4** | Fallback activation logic | - Trigger condition (4 retries exhausted)<br>- Health check ping (15min interval)<br>- Auto-recovery when API restored |
| **Story 3.5** | Latency measurement | - Percentile calculation (p50, p95, p99)<br>- Timer accuracy (perf_counter)<br>- Breakdown tracking (embedding, search, CoT) |
| **Story 3.6** | Backup rotation logic | - Date-based deletion (>7 days old)<br>- Backup file existence check<br>- pg_dump command construction |
| **Story 3.7** | Config loading | - Environment variable parsing<br>- config.yaml validation<br>- Dev/prod separation |
| **Story 3.8** | Service health check | - Watchdog heartbeat (60s interval)<br>- Health endpoint response (200 OK)<br>- Service status parsing |
| **Story 3.9** | Kappa calculation | - Agreement calculation (100 queries)<br>- Spot check sampling (5% selection)<br>- Revert trigger (<0.70 threshold) |
| **Story 3.10** | Budget aggregation | - Monthly cost summation<br>- API breakdown (group by api_name)<br>- Projected cost calculation |
| **Story 3.11** | Stability metrics | - Uptime calculation (168h tracking)<br>- Success rate (% calculation)<br>- Latency aggregation (p95 over 7 days) |
| **Story 3.12** | Documentation generation | - (No unit tests, manual review) |

**Unit Test Framework:** pytest (Python)

**Example Unit Test (Story 3.3):**

```python
# tests/test_retry_logic.py
import pytest
from mcp_server.utils.retry_logic import exponential_backoff_retry

def test_exponential_backoff_delays():
    """Test that retry delays follow exponential pattern."""
    delays = []

    def failing_func():
        delays.append(time.time())
        raise Exception("Simulated failure")

    with pytest.raises(Exception):
        exponential_backoff_retry(failing_func, max_retries=4, jitter=False)

    # Calculate actual delays
    actual_delays = [delays[i+1] - delays[i] for i in range(len(delays)-1)]

    # Expected: 1s, 2s, 4s, 8s (±0.1s tolerance)
    assert abs(actual_delays[0] - 1.0) < 0.1
    assert abs(actual_delays[1] - 2.0) < 0.1
    assert abs(actual_delays[2] - 4.0) < 0.1
    assert abs(actual_delays[3] - 8.0) < 0.1

def test_max_retries_enforced():
    """Test that retry logic stops after max_retries."""
    attempt_count = 0

    def failing_func():
        nonlocal attempt_count
        attempt_count += 1
        raise Exception("Simulated failure")

    with pytest.raises(Exception):
        exponential_backoff_retry(failing_func, max_retries=4)

    assert attempt_count == 4  # 4 retries total

def test_jitter_applied():
    """Test that jitter introduces randomness."""
    delays_run1 = []
    delays_run2 = []

    def failing_func(delays_list):
        delays_list.append(time.time())
        raise Exception("Simulated failure")

    # Run 1
    with pytest.raises(Exception):
        exponential_backoff_retry(lambda: failing_func(delays_run1), max_retries=2, jitter=True)

    # Run 2
    with pytest.raises(Exception):
        exponential_backoff_retry(lambda: failing_func(delays_run2), max_retries=2, jitter=True)

    # Calculate delays
    actual_delays_run1 = [delays_run1[i+1] - delays_run1[i] for i in range(len(delays_run1)-1)]
    actual_delays_run2 = [delays_run2[i+1] - delays_run2[i] for i in range(len(delays_run2)-1)]

    # Delays should differ due to jitter (±20%)
    assert actual_delays_run1[0] != actual_delays_run2[0]
```

---

#### Integration Tests

**Scope:** Interaction between multiple components (MCP Server + PostgreSQL, API clients).

**Test Coverage:**

1. **Golden Test Set Creation (Story 3.1 + Story 3.2):**
   - Create Golden Test Set from L0 Raw Memory
   - Insert into `golden_test_set` table
   - Run `get_golden_test_results` MCP Tool
   - Verify Precision@5 calculation and storage in `model_drift_log`

2. **API Retry + Fallback (Story 3.3 + Story 3.4):**
   - Simulate Haiku API failure (503 error)
   - Verify retry logic triggers (4 attempts)
   - Verify fallback to Claude Code activates
   - Verify api_retry_log entry created

3. **Backup + Restore (Story 3.6):**
   - Create test database with sample L2 Insights
   - Run backup script (pg_dump)
   - Drop test database
   - Restore from backup (pg_restore)
   - Verify all data restored correctly

4. **systemd Service (Story 3.8):**
   - Start MCP Server via systemd
   - Send test query (MCP Tool call)
   - Kill MCP Server process (simulate crash)
   - Verify auto-restart occurs (within 10s)
   - Verify service returns to `active` state

5. **Budget Monitoring (Story 3.10):**
   - Insert sample API cost log entries
   - Run budget dashboard CLI tool
   - Verify monthly aggregation correct
   - Verify budget alert triggers at threshold

**Integration Test Framework:** pytest + Docker (for PostgreSQL isolation)

**Example Integration Test (Story 3.6):**

```python
# tests/integration/test_backup_restore.py
import pytest
import subprocess
import psycopg2

@pytest.fixture
def test_database():
    """Create isolated test database."""
    conn = psycopg2.connect("dbname=postgres user=mcp_user")
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE cognitive_memory_test")
    cursor.close()
    conn.close()

    yield "cognitive_memory_test"

    # Cleanup
    conn = psycopg2.connect("dbname=postgres user=mcp_user")
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute("DROP DATABASE cognitive_memory_test")
    cursor.close()
    conn.close()

def test_backup_restore_workflow(test_database):
    """Test full backup and restore workflow."""
    # 1. Insert sample data
    conn = psycopg2.connect(f"dbname={test_database} user=mcp_user")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE l2_insights (
            id SERIAL PRIMARY KEY,
            content TEXT NOT NULL
        )
    """)
    cursor.execute("INSERT INTO l2_insights (content) VALUES ('Test insight 1')")
    cursor.execute("INSERT INTO l2_insights (content) VALUES ('Test insight 2')")
    conn.commit()
    cursor.close()
    conn.close()

    # 2. Run backup
    backup_file = "/tmp/test_backup.dump"
    subprocess.run([
        "pg_dump", "-U", "mcp_user", "-Fc", test_database, "-f", backup_file
    ], check=True)

    # 3. Drop database
    conn = psycopg2.connect("dbname=postgres user=mcp_user")
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute(f"DROP DATABASE {test_database}")
    cursor.execute(f"CREATE DATABASE {test_database}")
    cursor.close()
    conn.close()

    # 4. Restore from backup
    subprocess.run([
        "pg_restore", "-U", "mcp_user", "-d", test_database, backup_file
    ], check=True)

    # 5. Verify data restored
    conn = psycopg2.connect(f"dbname={test_database} user=mcp_user")
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM l2_insights ORDER BY id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    assert len(rows) == 2
    assert rows[0][0] == "Test insight 1"
    assert rows[1][0] == "Test insight 2"
```

---

#### End-to-End Tests

**Scope:** Full system validation (7-Day Stability Test, Story 3.11).

**Test Scenarios:**

1. **Full RAG Pipeline with Monitoring:**
   - User query → Hybrid Search → CoT Generation → Haiku Evaluation
   - Model Drift Detection runs daily (cron)
   - Budget tracking logs all API calls
   - Backup runs nightly (cron)

2. **Error Recovery Scenarios:**
   - Haiku API failure → Fallback to Claude Code
   - MCP Server crash → Auto-restart via systemd
   - API rate limit → Retry with exponential backoff

3. **Performance Validation:**
   - 100 test queries (Story 3.5)
   - p95 latency <5s verified
   - Latency breakdown measured

4. **7-Day Stability Test (Story 3.11):**
   - 168 hours continuous operation
   - 70+ queries processed
   - >99% success rate
   - Budget <€2 for 7 days

**E2E Test Environment:** Production environment (real APIs, real database)

**Success Criteria:**
- All 70+ queries succeed (max 1 failure allowed)
- No critical errors in systemd journal
- p95 latency <5s over entire test period
- Total cost <€2 (projected €8/mo)

---

### Test Coverage Goals

**Epic 3 Test Coverage Targets:**

| Test Type | Coverage Target | Rationale |
|-----------|----------------|-----------|
| **Unit Tests** | >80% code coverage | Critical functions (retry, calculation, parsing) fully tested |
| **Integration Tests** | >60% integration paths | Key workflows (backup/restore, API retry+fallback) validated |
| **End-to-End Tests** | 100% user scenarios | 7-Day Stability Test covers all production use cases |

**Coverage Measurement:** pytest-cov (Python code coverage tool)

**Exemptions from Unit Testing:**
- Documentation generation (Story 3.12) - manual review
- systemd service file - integration test only
- Cron job scripts - integration test only

---

### Quality Assurance

**QA Activities for Epic 3:**

1. **Code Review:**
   - All PRs reviewed by ethr (self-review for solo project)
   - Focus: Error handling, security (no secrets in code), performance

2. **Manual Testing:**
   - Each story manually tested before marking "DONE"
   - Test both happy path and error scenarios

3. **Performance Profiling:**
   - Story 3.5: Run latency benchmarking with 100 queries
   - Identify bottlenecks (embedding, search, CoT, evaluation)
   - Optimize if p95 >5s

4. **Security Audit:**
   - Story 3.7: Verify .env files not in Git
   - Story 3.8: Verify service runs as non-root user
   - Story 3.6: Verify backup files have chmod 600

5. **Stability Validation:**
   - Story 3.11: 7-Day Stability Test (168h continuous operation)
   - Monitor systemd journal for errors
   - Track query success rate, latency, budget

6. **Documentation Review:**
   - Story 3.12: All 6 docs reviewed for completeness
   - Troubleshooting guide tested against common issues
   - Operations manual validated by attempting operations

**QA Sign-Off Criteria:**
- All unit tests passing
- All integration tests passing
- 7-Day Stability Test passed
- Code review complete
- Documentation reviewed and validated

---

### Test Execution Plan

**Epic 3 Test Execution Timeline:**

| Phase | Stories | Test Activities | Duration | Validation |
|-------|---------|-----------------|----------|------------|
| **Phase 1: Foundation** | 3.1-3.6 | Unit tests, integration tests | ~30h | Unit test pass, integration test pass |
| **Phase 2: Production Setup** | 3.7-3.8 | Config tests, systemd integration test | ~10h | Service starts on boot, auto-restart works |
| **Phase 3: Optimization** | 3.9-3.10 | Kappa calculation tests, budget tests | ~15h | Budget dashboard functional, Kappa correct |
| **Phase 4: Validation** | 3.11-3.12 | 7-Day Stability Test, doc review | ~25h | 168h uptime, >99% success, docs complete |

**Total Test Execution Time:** ~80 hours (included in 60-80h epic timeline)

**Test Environment Setup:**
- Development: Isolated test database, test API keys
- Staging: Production-like environment (separate .env.staging)
- Production: Real environment (7-Day Stability Test only)

**Continuous Integration (Optional):**
- GitHub Actions: Run unit tests on every commit
- Pre-commit hooks: Prevent secrets from being committed
- (Out of scope for v3.1, but recommended for v3.2+)

---

### Acceptance Testing

**User Acceptance Testing (UAT) - ethr:**

Before marking Epic 3 "DONE", ethr performs UAT:

1. **Production Checklist Walkthrough:**
   - Follow `/docs/production-checklist.md` step-by-step
   - Verify all items checked off

2. **Operations Manual Validation:**
   - Perform daily operations (start/stop service, check logs, run backups)
   - Verify operations manual instructions are accurate

3. **Troubleshooting Guide Testing:**
   - Simulate common issues (API failure, latency spike, budget overage)
   - Verify troubleshooting guide resolves issues

4. **7-Day Stability Test Review:**
   - Review `/docs/7-day-stability-report.md`
   - Verify all metrics meet success criteria

5. **Final Sign-Off:**
   - ethr confirms system meets all requirements
   - Epic 3 marked "DONE" and transitioned to "Production"

**UAT Success Criteria:**
- ethr can operate system independently (no external support needed)
- All documentation is clear and actionable
- System meets performance, budget, and reliability targets

