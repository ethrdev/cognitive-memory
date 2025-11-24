# Cognitive Memory System v3.1.0-Hybrid - Architektur

**Author:** ethr
**Date:** 2025-11-09
**Project:** i-o (Cognitive Memory System)
**Version:** v3.1.0-Hybrid
**Architektur-Basis:** MCP Server + Claude Code Integration

---

## Executive Summary

Das Cognitive Memory System v3.1.0-Hybrid ist ein **MCP-basiertes (Model Context Protocol) Gedächtnissystem** für Claude Code mit strategischer API-Nutzung: Bulk-Operationen (Generation, CoT, Planning) laufen kostenfrei intern in Claude Code (€0/mo), während kritische Evaluationen (Dual Judge, Reflexion) über externe APIs (GPT-4o, Haiku) für methodische Robustheit erfolgen (€5-10/mo, später €2-3/mo). Die Architektur trennt klar zwischen **MCP Server (Python, Persistence)** und **Claude Code (LLM Operations)**, verbunden über MCP Protocol (stdio transport).

**Architektur-Prinzip:** Local-First mit strategischen Cloud-API-Calls für Compute, keine Cloud-Dependencies für Daten.

---

## Technologie-Entscheidungen

### Decision Summary

| Kategorie | Entscheidung | Version | Affects Epics | Rationale |
|-----------|--------------|---------|---------------|-----------|
| **Primary Language** | Python | 3.11+ | Alle Epics | Type Hints, MCP SDK Compatibility |
| **MCP Server Framework** | Python MCP SDK | Latest (pip install mcp) | Epic 1, 2, 3 | Offizielles SDK, stdio transport |
| **Datenbank** | PostgreSQL + pgvector | PostgreSQL 15+, pgvector latest | Epic 1, 2, 3 | Vektor-Suche nativ, Production-Ready |
| **Embedding API** | OpenAI text-embedding-3-small | 1536 dimensions | Epic 1, 2, 3 | Beste Precision@5 (>0.75), €0.02/1M tokens |
| **Evaluation API** | Anthropic Claude Haiku | claude-3-5-haiku-20241022 | Epic 2, 3 | Deterministisch, konsistent über Sessions |
| **Dual Judge (Ground Truth)** | GPT-4o + Haiku | gpt-4o, claude-3-5-haiku-20241022 | Epic 1 | True IRR (Kappa >0.70), methodisch valide |
| **LLM für Bulk-Ops** | Claude Code (in MAX Subscription) | Sonnet 4.5 (claude-sonnet-4-5-20250929) | Epic 2, 3 | Query Expansion, CoT Generation intern (€0/mo) |
| **Dependency Management** | Poetry | Latest | Epic 1 | Type-safe, lockfile, modernes Python |
| **Vektor-Index** | IVFFlat (pgvector) | lists=100 | Epic 1, 2 | Balance Speed/Accuracy für <100k Vektoren |
| **Service Management** | systemd | Standard (Linux) | Epic 3 | Auto-restart, logging, production-ready |
| **Backup** | pg_dump + Git (L2 Insights) | Native PostgreSQL | Epic 3 | RTO <1h, RPO <24h, 7-day retention |
| **Testing Strategy** | Manual + Golden Test Set | 50-100 Queries, täglich | Epic 3 | Model Drift Detection, Precision@5 Validation |
| **Environment Management** | .env files + config.yaml | Development/Production separation | Epic 3 | Secrets isolation, environment-specific configs |

---

## Systemarchitektur

### High-Level Architektur

```
┌─────────────────────────────────────────────────────────────┐
│ Claude Code (Sonnet 4.5 in MAX Subscription)               │
│ ├─ Query Expansion (intern, €0/mo)                         │
│ ├─ CoT Generation (intern, €0/mo)                          │
│ ├─ Planning & Orchestration (intern, €0/mo)                │
│ └─ MCP Client                                               │
│     │                                                        │
│     │ MCP Protocol (stdio transport)                        │
│     ↓                                                        │
├─────────────────────────────────────────────────────────────┤
│ MCP Server (Python, lokal)                                  │
│ ├─ 7 MCP Tools (store_raw_dialogue, compress_to_l2_insight,│
│ │   hybrid_search, update_working_memory, store_episode,   │
│ │   get_golden_test_results, store_dual_judge_scores)      │
│ ├─ 5 MCP Resources (memory://l2-insights, memory://working-│
│ │   memory, memory://episode-memory, memory://l0-raw,      │
│ │   memory://stale-memory)                                 │
│ └─ External API Clients                                     │
│     ├─ OpenAI API (Embeddings, €0.06/mo)                   │
│     ├─ Anthropic Haiku API (Evaluation, Reflexion, €1-2/mo)│
│     └─ OpenAI GPT-4o API (Dual Judge, €1-1.5/mo)           │
│         │                                                    │
│         ↓                                                    │
├─────────────────────────────────────────────────────────────┤
│ PostgreSQL + pgvector (lokal)                               │
│ ├─ l0_raw (Dialogtranskripte)                              │
│ ├─ l2_insights (Embeddings 1536-dim)                       │
│ ├─ working_memory (LRU, 8-10 Items)                        │
│ ├─ episode_memory (Reflexionen, Verbal RL)                 │
│ ├─ stale_memory (Archiv, kritische Items)                  │
│ └─ ground_truth (Dual Judge Scores, Kappa)                 │
└─────────────────────────────────────────────────────────────┘

Externes:
  - OpenAI Embeddings API (text-embedding-3-small)
  - Anthropic Haiku API (claude-3-5-haiku-20241022)
  - OpenAI GPT-4o API (gpt-4o)
```

### Daten-Fluss: Typische Query

```
1. User Query (in Claude Code)
   ↓
2. Query Expansion → 3 Varianten (intern in Claude Code, €0)
   ↓
3. OpenAI Embeddings API → 4 Embeddings (4 Queries, €0.00008)
   ↓
4. MCP Tool: hybrid_search (4x parallel)
   ↓
5. PostgreSQL: Semantic + Keyword Search, RRF Fusion → Top-5 Docs
   ↓
6. MCP Resource: memory://episode-memory (ähnliche vergangene Queries)
   ↓
7. CoT Generation (intern in Claude Code, €0)
   ↓
8. MCP Server → Haiku API: Evaluation (€0.001)
   ↓ (falls Reward <0.3)
9. MCP Server → Haiku API: Reflexion (€0.0015)
   ↓
10. MCP Tool: store_episode (speichert verbalisierte Lektion)
    ↓
11. MCP Tool: update_working_memory (LRU Eviction)
    ↓
12. User erhält: Answer + Confidence + Sources + (optional) Lesson Learned
```

**Total Cost per Query:** ~€0.003 (€3/mo bei 1000 Queries)

---

## Projektstruktur

### Source Tree

```
i-o/
├─ mcp_server/                    # MCP Server Implementation
│  ├─ main.py                     # Server Entry Point (stdio transport)
│  ├─ tools/                      # MCP Tool Implementations
│  │  ├─ store_raw_dialogue.py
│  │  ├─ compress_to_l2_insight.py
│  │  ├─ hybrid_search.py
│  │  ├─ update_working_memory.py
│  │  ├─ store_episode.py
│  │  ├─ get_golden_test_results.py
│  │  └─ store_dual_judge_scores.py
│  ├─ resources/                  # MCP Resource Implementations
│  │  ├─ l2_insights.py
│  │  ├─ working_memory.py
│  │  ├─ episode_memory.py
│  │  ├─ l0_raw.py
│  │  └─ stale_memory.py
│  ├─ db/                         # Database Layer
│  │  ├─ connection.py            # PostgreSQL Connection Pool
│  │  ├─ migrations/              # Schema Migrations
│  │  │  ├─ 001_initial_schema.sql
│  │  │  └─ 002_add_ground_truth.sql
│  │  └─ models.py                # Data Models
│  ├─ external/                   # External API Clients
│  │  ├─ openai_client.py         # Embeddings + GPT-4o
│  │  └─ anthropic_client.py      # Haiku API
│  ├─ utils/                      # Utilities
│  │  ├─ embedding.py             # Embedding Logic
│  │  ├─ rrf_fusion.py            # Reciprocal Rank Fusion
│  │  ├─ semantic_fidelity.py     # Enhancement E2
│  │  └─ retry_logic.py           # Exponential Backoff
│  └─ config.py                   # Configuration Management
├─ tests/                         # Tests
│  ├─ test_tools.py
│  ├─ test_resources.py
│  ├─ test_hybrid_search.py
│  └─ test_external_apis.py
├─ docs/                          # Documentation
│  ├─ installation-guide.md
│  ├─ operations-manual.md
│  ├─ troubleshooting.md
│  ├─ backup-recovery.md
│  ├─ api-reference.md
│  └─ 7-day-stability-report.md
├─ config/                        # Configuration Files
│  ├─ config.yaml                 # Main Config (dev/prod overrides)
│  ├─ .env.template               # Environment Template
│  ├─ .env.development            # Dev Environment (git-ignored)
│  └─ .env.production             # Production Environment (git-ignored)
├─ scripts/                       # Automation Scripts
│  ├─ backup.sh                   # PostgreSQL Backup (Cron)
│  ├─ drift_detection.sh          # Model Drift Check (Cron)
│  └─ budget_report.py            # Cost Monitoring CLI
├─ streamlit_apps/                # Streamlit UIs
│  └─ ground_truth_labeling.py    # Ground Truth Collection UI
├─ memory/                        # L2 Insights Git Backup (optional)
│  └─ l2-insights/
│     └─ YYYY-MM-DD.json          # Daily Export (read-only fallback)
├─ backups/                       # PostgreSQL Backups
│  └─ postgres/
│     └─ cognitive_memory_YYYY-MM-DD.dump
├─ .gitignore                     # Git Ignore (secrets, .env files)
├─ pyproject.toml                 # Poetry Dependencies
├─ README.md                      # Project Overview
└─ systemd/                       # Systemd Service Files
   └─ cognitive-memory-mcp.service
```

---

## Epic-zu-Komponenten Mapping

| Epic | Komponenten | Stories |
|------|-------------|---------|
| **Epic 1: MCP Server Foundation & Ground Truth** | `mcp_server/`, `db/`, `streamlit_apps/`, `external/openai_client.py`, `external/anthropic_client.py` | 1.1-1.12 (12 Stories) |
| **Epic 2: RAG Pipeline & Hybrid Calibration** | `mcp_server/tools/hybrid_search.py`, `utils/rrf_fusion.py`, Claude Code Integration, `external/anthropic_client.py` (Haiku Evaluation) | 2.1-2.9 (9 Stories) |
| **Epic 3: Working Memory, Evaluation & Production Readiness** | `scripts/`, `systemd/`, `config/`, `docs/`, `backups/`, Golden Test Set, Model Drift Detection | 3.1-3.12 (12 Stories) |

---

## Datenbank-Schema (PostgreSQL + pgvector)

### Tabellen

**1. `l0_raw` - Raw Dialogtranskripte**
```sql
CREATE TABLE l0_raw (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    speaker VARCHAR(50) NOT NULL,  -- 'user' | 'assistant'
    content TEXT NOT NULL,
    metadata JSONB
);
CREATE INDEX idx_l0_session ON l0_raw(session_id, timestamp);
```

**2. `l2_insights` - Komprimierte semantische Einheiten**
```sql
CREATE TABLE l2_insights (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,  -- OpenAI text-embedding-3-small
    created_at TIMESTAMPTZ DEFAULT NOW(),
    source_ids INTEGER[] NOT NULL,    -- L0 Raw IDs
    metadata JSONB
);
CREATE INDEX idx_l2_embedding ON l2_insights USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_l2_fts ON l2_insights USING gin(to_tsvector('english', content));
```

**3. `working_memory` - Session-Kontext (LRU)**
```sql
CREATE TABLE working_memory (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    importance FLOAT DEFAULT 0.5,      -- 0.0-1.0, >0.8 = Critical
    last_accessed TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_wm_lru ON working_memory(last_accessed ASC);
```

**4. `episode_memory` - Verbalisierte Reflexionen (Verbal RL)**
```sql
CREATE TABLE episode_memory (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    reward FLOAT NOT NULL,             -- -1.0 bis +1.0 (Haiku Evaluation)
    reflection TEXT NOT NULL,          -- Verbalisierte Lektion
    created_at TIMESTAMPTZ DEFAULT NOW(),
    embedding vector(1536) NOT NULL   -- Query Embedding
);
CREATE INDEX idx_episode_embedding ON episode_memory USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

**5. `stale_memory` - Archiv kritischer Items**
```sql
CREATE TABLE stale_memory (
    id SERIAL PRIMARY KEY,
    original_content TEXT NOT NULL,
    archived_at TIMESTAMPTZ DEFAULT NOW(),
    importance FLOAT NOT NULL,
    reason VARCHAR(100) NOT NULL       -- 'LRU_EVICTION' | 'MANUAL_ARCHIVE'
);
```

**6. `ground_truth` - Ground Truth Set + Dual Judge Scores**
```sql
CREATE TABLE ground_truth (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    expected_docs INTEGER[] NOT NULL,  -- L2 Insight IDs
    judge1_score FLOAT,                -- GPT-4o Score
    judge2_score FLOAT,                -- Haiku Score
    judge1_model VARCHAR(100),         -- 'gpt-4o'
    judge2_model VARCHAR(100),         -- 'claude-3-5-haiku-20241022'
    kappa FLOAT,                       -- Cohen's Kappa
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**7. `golden_test_set` - Model Drift Detection**
```sql
CREATE TABLE golden_test_set (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    expected_docs INTEGER[] NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    query_type VARCHAR(20) NOT NULL    -- 'short' | 'medium' | 'long'
);
```

**8. `model_drift_log` - Daily Precision@5 Tracking**
```sql
CREATE TABLE model_drift_log (
    date DATE PRIMARY KEY,
    precision_at_5 FLOAT NOT NULL,
    num_queries INTEGER NOT NULL,
    avg_retrieval_time FLOAT,
    embedding_model_version VARCHAR(50)
);
```

**9. `api_cost_log` - Budget Monitoring**
```sql
CREATE TABLE api_cost_log (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    api_name VARCHAR(50) NOT NULL,     -- 'openai_embeddings' | 'gpt4o_judge' | 'haiku_eval'
    num_calls INTEGER NOT NULL,
    token_count INTEGER,
    estimated_cost FLOAT NOT NULL
);
CREATE INDEX idx_cost_date ON api_cost_log(date DESC);
```

**10. `api_retry_log` - Retry Statistiken**
```sql
CREATE TABLE api_retry_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    api_name VARCHAR(50) NOT NULL,
    error_type VARCHAR(100),
    retry_count INTEGER,
    success BOOLEAN NOT NULL
);
```

---

## MCP Tools & Resources

### 7 MCP Tools (Actions)

| Tool Name | Zweck | Input | Output | Epic |
|-----------|-------|-------|--------|------|
| `store_raw_dialogue` | L0 Storage | session_id, speaker, content, metadata | {id, timestamp} | 1.4 |
| `compress_to_l2_insight` | L2 Creation + Embedding | content, source_ids | {id, fidelity_score} | 1.5 |
| `hybrid_search` | RAG Retrieval | query_embedding, query_text, top_k, weights | [{id, content, score, source_ids}] | 1.6 |
| `update_working_memory` | Session State | content, importance | {success, evicted_item} | 1.7 |
| `store_episode` | Reflexion Storage | query, reward, reflection | {id, embedding_status} | 1.8 |
| `get_golden_test_results` | Model Drift Detection | (none) | {date, precision_at_5, drift_detected} | 3.2 |
| `store_dual_judge_scores` | IRR Validation | query, expected_docs | {judge1_score, judge2_score, kappa} | 1.11 |

### 5 MCP Resources (Read-Only State)

| Resource URI | Zweck | Query Parameters | Epic |
|--------------|-------|------------------|------|
| `memory://l2-insights` | L2 Insight Retrieval | ?query={q}&top_k={k} | 1.9 |
| `memory://working-memory` | Working Memory State | (none) | 1.9 |
| `memory://episode-memory` | Episode Retrieval | ?query={q}&min_similarity={t} | 1.9 |
| `memory://l0-raw` | Raw Transkripte | ?session_id={id}&date_range={r} | 1.9 |
| `memory://stale-memory` | Archiv-Zugriff | ?importance_min={t} | 1.9 |

---

## Implementierungs-Patterns

### Naming Conventions

**Python:**
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/Variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

**Database:**
- Tables: `snake_case` (singular oder plural je nach Kontext)
- Columns: `snake_case`
- Foreign Keys: `{table}_id` (z.B. `session_id`)

**MCP:**
- Tool Names: `snake_case` (z.B. `store_raw_dialogue`)
- Resource URIs: `memory://{kebab-case}` (z.B. `memory://l2-insights`)

### Error Handling Strategy

**MCP Server:**
- Alle Exceptions → Structured JSON Response
- Format: `{error: {type, message, details}, status: "error"}`
- Logging: JSON Structured Logs (timestamp, level, api_name, error_type)

**External APIs:**
- Retry-Logic: Exponential Backoff (1s, 2s, 4s, 8s, max 4 retries)
- Fallback: Haiku API Ausfall → Claude Code Evaluation (degraded mode)
- No Fallback: OpenAI Embeddings (kritisch, kein Fallback möglich)

### Logging Approach

**Format:** JSON Structured Logging
```json
{
  "timestamp": "2025-11-09T14:23:45Z",
  "level": "INFO",
  "component": "mcp_server.tools.hybrid_search",
  "message": "Hybrid search completed",
  "metadata": {
    "query_length": 42,
    "top_k": 5,
    "latency_ms": 845,
    "semantic_weight": 0.8,
    "keyword_weight": 0.2
  }
}
```

**Levels:**
- ERROR: API Failures, Exceptions, Retry Exhaustion
- WARN: Degraded Mode, Fallbacks, Low Confidence (<0.3)
- INFO: Tool Calls, Resource Reads, Daily Drift Detection
- DEBUG: Detailed Request/Response (nur Development)

**Destinations:**
- Production: `systemd` Journal (`journalctl -u cognitive-memory-mcp`)
- Additional: `/var/log/cognitive-memory/mcp.log` (rotation: 7 days)

### Testing Strategy

**Manual Testing (Epic 1-2):**
- Manuelles Testing in Claude Code Interface
- No automated unit tests (Personal Use, Single Developer)
- Streamlit UI Testing (Ground Truth Labeling)

**Integration Testing (Epic 2):**
- End-to-End RAG Pipeline Test (Story 2.7)
- 100 Test-Queries (Latency Benchmarking, Story 3.5)

**Validation Testing (Epic 3):**
- Golden Test Set: 50-100 Queries, täglich via Cron (Story 3.2)
- 7-Day Stability Test: 70 Queries über 7 Tage (Story 3.11)
- Precision@5 Validation: >0.75 Target (Story 2.9)

---

## API-Integration

### OpenAI API (Embeddings + GPT-4o)

**Embeddings:**
- Model: `text-embedding-3-small`
- Dimensions: 1536
- Cost: €0.02 per 1M tokens (~€0.00002 per Query)
- Usage: Query Embedding, L2 Insight Embedding, Episode Memory Embedding

**GPT-4o Dual Judge:**
- Model: `gpt-4o`
- Usage: Ground Truth Collection (Phase 1b), Spot Checks (Phase 2)
- Cost: ~€1-1.5/mo (100 Queries Phase 1b + 5% Spot Checks)

**Retry-Logic:** 4 Retries (1s, 2s, 4s, 8s), Exponential Backoff + Jitter

### Anthropic API (Haiku)

**Haiku Evaluation:**
- Model: `claude-3-5-haiku-20241022`
- Temperature: 0.0 (deterministisch)
- Max Tokens: 500
- Usage: Self-Evaluation (Reward -1.0 bis +1.0)
- Cost: ~€0.001 per Evaluation (~€1/mo bei 1000 Queries)

**Haiku Reflexion:**
- Model: `claude-3-5-haiku-20241022`
- Temperature: 0.7 (kreativ)
- Max Tokens: 1000
- Usage: Verbal RL bei Reward <0.3
- Cost: ~€0.0015 per Reflexion (~€0.45/mo bei 300 Reflexionen)

**Haiku Dual Judge:**
- Model: `claude-3-5-haiku-20241022`
- Usage: Ground Truth Collection (Phase 1b), Spot Checks (Phase 2)
- Cost: ~€1-1.5/mo (100 Queries Phase 1b + 5% Spot Checks)

**Retry-Logic:** 4 Retries (1s, 2s, 4s, 8s), Exponential Backoff + Jitter
**Fallback:** Claude Code Evaluation (degraded mode) bei totalem API-Ausfall

---

## Security & Privacy

### Data Privacy

**Local-First Architektur:**
- Alle Konversationsdaten bleiben lokal (PostgreSQL)
- Keine Cloud-Storage für User-Daten
- Externe APIs nur für Compute (Embeddings, Evaluation)
- Keine Training auf User-Daten durch externe APIs

### Secrets Management

**Environment Files:**
- `.env.production` / `.env.development` (git-ignored)
- API Keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- DB Credentials: `POSTGRES_USER`, `POSTGRES_PASSWORD`
- File Permissions: `chmod 600` (nur Owner readable)

**No Vault/SecretManager:**
- Reicht für Personal Use (nur ethr)
- Out of scope v3.1.0

### Authentication

**Keine User-Authentication:**
- System läuft lokal
- Nur ethr hat Zugriff
- MCP Server läuft als `ethr` User (Non-Root)

**API Authentication:**
- OpenAI API: Bearer Token (API Key)
- Anthropic API: X-API-Key Header

---

## Performance-Architektur

### Latency-Targets (NFR001)

| Metrik | Target | Measured In |
|--------|--------|-------------|
| End-to-End Query Response | <5s (p95) | Story 3.5 |
| Hybrid Search (Retrieval) | <1s (p95) | Story 1.6 |
| CoT Generation (intern) | ~2-3s (median) | Story 2.3 |
| Haiku Evaluation (extern) | ~0.5s (median) | Story 2.5 |
| OpenAI Embeddings (extern) | ~200-300ms (median) | Story 1.5 |

**Rationale:** <5s ist akzeptabel für "Denkzeit" in philosophischen Gesprächen (PRD NFR001)

### Database Performance

**pgvector IVFFlat Index:**
- `lists=100` (optimiert für <100k Vektoren)
- Alternative: HNSW (schneller, mehr Memory) - nur bei Latency-Problemen
- Index Rebuild: Bei >10k neuen L2 Insights

**Query Optimization:**
- Limit: Top-5 statt Top-10 (reduziert Context Window Risk)
- RRF Fusion: Parallel Semantic + Keyword Search
- Connection Pooling: Optional (`psycopg2.pool`) bei Performance-Problemen

---

## Deployment-Architektur

### Production Environment

**Local Deployment:**
- OS: Linux (Arch Linux impliziert aus PRD)
- Service Manager: systemd
- Database: PostgreSQL 15+ (lokal)
- MCP Server: Python 3.11+ (stdio transport)

**Service Configuration:**
```ini
[Unit]
Description=Cognitive Memory MCP Server
After=postgresql.service

[Service]
Type=simple
User=ethr
WorkingDirectory=/path/to/i-o
ExecStart=/path/to/venv/bin/python /path/to/i-o/mcp_server/main.py
Restart=always
Environment="ENVIRONMENT=production"

[Install]
WantedBy=multi-user.target
```

**Auto-Start:** `systemctl enable cognitive-memory-mcp`

### Development Environment

**Separation:**
- Development DB: `cognitive_memory_dev`
- Production DB: `cognitive_memory`
- Environment Variable: `ENVIRONMENT=development|production`

**No Docker:**
- Out of scope v3.1.0
- Native installation (Python venv + PostgreSQL)

---

## Backup & Disaster Recovery

### Backup Strategy (NFR004)

**PostgreSQL Backups:**
- Tool: `pg_dump -Fc` (Custom Format, komprimiert)
- Schedule: Täglich 3 Uhr nachts via Cron (`0 3 * * *`)
- Retention: 7 days
- Location: `/backups/postgres/cognitive_memory_YYYY-MM-DD.dump`

**L2 Insights Git Backup (optional):**
- Daily Export: L2 Insights (Content + Metadata, OHNE Embeddings)
- Format: JSON → `/memory/l2-insights/YYYY-MM-DD.json`
- Git Commit + Push (konfigurierbar)
- Rationale: Text klein, Embeddings können re-generated werden

### Recovery

**Recovery Time Objective (RTO):** <1 hour
**Recovery Point Objective (RPO):** <24 hours

**Restore Command:**
```bash
pg_restore -U mcp_user -d cognitive_memory \
  /backups/postgres/cognitive_memory_YYYY-MM-DD.dump
```

**L2 Insights Fallback:**
- Load JSON → Re-generate Embeddings via OpenAI API
- Cost: ~€0.20 für 10K L2 Insights

---

## Monitoring & Observability

### Daily Monitoring (Epic 3)

**Model Drift Detection (Story 3.2):**
- Cron: Täglich 2 Uhr nachts (`0 2 * * *`)
- Tool: `get_golden_test_results` (MCP Tool)
- Metric: Precision@5 auf Golden Test Set (50-100 Queries)
- Alert: Drift >5% gegenüber 7-Day Rolling Average

**Budget Monitoring (Story 3.10):**
- Daily Cost Tracking: `api_cost_log` Table
- Monthly Aggregation: `SELECT SUM(estimated_cost) FROM api_cost_log WHERE date >= NOW() - INTERVAL '30 days'`
- Alert: Projected Monthly Cost >€10/mo

**System Health:**
- Systemd Watchdog: Heartbeat alle 60s
- Auto-Restart bei Crash
- Log Monitoring: `journalctl -u cognitive-memory-mcp -f`

---

## Budget-Architektur (NFR003)

### Cost Breakdown

**Development (Epic 1-2):** €1-2/mo
- Ground Truth Collection: €0.23 einmalig (100 Queries Dual Judge)
- Testing: €1-2/mo (RAG Pipeline Testing)

**Production (Epic 3, first 3 months):** €5-10/mo
- OpenAI Embeddings: €0.06/mo (1000 Queries + Compressions)
- Haiku Evaluation: €1-2/mo (1000 Evaluations)
- Haiku Reflexion: €0.45/mo (300 Reflexionen @ 30% Trigger Rate)
- GPT-4o Dual Judge: €1-1.5/mo (100 Queries/mo + spot checks)
- Haiku Dual Judge: €1-1.5/mo
- Expanded Golden Set: €1/mo (50-100 Queries + täglich Drift Detection)

**Production (after Staged Dual Judge, Month 4+):** €2-3/mo
- OpenAI Embeddings: €0.06/mo
- Haiku Evaluation: €1-2/mo
- Haiku Reflexion: €0.30/mo (Reflexion-Rate sinkt über Zeit)
- GPT-4o Single Judge: €0.50/mo (nur 5% Spot Checks)
- Haiku Spot Check: €0.15/mo (5% Sampling)

**Total Savings:** 90-95% vs. v2.4.1 (€106/mo → €5-10/mo → €2-3/mo)

---

## Development Environment Setup

### Prerequisites

**System Requirements:**
- OS: Linux (Arch Linux recommended)
- Python: 3.11+
- PostgreSQL: 15+
- Git
- systemd (für Production Deployment)

**External Accounts:**
- OpenAI API Account + API Key
- Anthropic API Account + API Key
- Claude MAX Subscription (für Claude Code)

### Installation Commands

**1. PostgreSQL + pgvector:**
```bash
# Arch Linux
sudo pacman -S postgresql

# pgvector from source
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Initialize DB
sudo -u postgres initdb -D /var/lib/postgres/data
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create Database + User
sudo -u postgres psql
CREATE DATABASE cognitive_memory;
CREATE USER mcp_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE cognitive_memory TO mcp_user;
\c cognitive_memory
CREATE EXTENSION vector;
```

**2. Python Environment:**
```bash
cd /path/to/i-o
python3.11 -m venv venv
source venv/bin/activate

# Install Dependencies
pip install poetry
poetry install

# Or with pip:
pip install -r requirements.txt
```

**3. Environment Configuration:**
```bash
cp config/.env.template config/.env.development
# Edit .env.development mit API Keys + DB Credentials
```

**4. Database Migrations:**
```bash
psql -U mcp_user -d cognitive_memory -f mcp_server/db/migrations/001_initial_schema.sql
psql -U mcp_user -d cognitive_memory -f mcp_server/db/migrations/002_add_ground_truth.sql
```

**5. MCP Server Test:**
```bash
python mcp_server/main.py
# Verify: Server starts, loggt "MCP Server listening on stdio"
```

**6. Claude Code Integration:**
- Edit: `~/.config/claude-code/mcp-settings.json`
- Add MCP Server Config (siehe Story 2.1)

---

## Architecture Decision Records (ADRs)

### ADR-001: MCP Protocol statt REST API

**Entscheidung:** MCP Server mit stdio transport statt REST API

**Rationale:**
- Native Claude Code Integration (kein Custom HTTP Client nötig)
- Persistent Connection (kein Overhead pro Request)
- Tools + Resources in einem Protokoll
- Zukunftssicher (MCP ist offizieller Anthropic Standard)

**Alternativen:**
- REST API: Mehr Boilerplate, kein Tool Discovery
- gRPC: Overkill für lokale Communication

**Status:** Accepted (Epic 1)

---

### ADR-002: Strategische API-Nutzung (Bulk intern, Eval extern)

**Entscheidung:**
- Bulk-Operationen (Query Expansion, CoT) → intern in Claude Code (€0/mo)
- Kritische Evaluationen (Dual Judge, Reflexion) → externe APIs (€5-10/mo)

**Rationale:**
- 90-95% Cost Reduction vs. v2.4.1 (€106/mo → €5-10/mo)
- Methodische Validität: Externe Haiku API = deterministisch über Sessions (konsistente Episode Memory)
- True IRR: GPT-4o + Haiku = echte unabhängige Dual Judges (Kappa >0.70)

**Alternativen:**
- Alles extern: €100+/mo (zu teuer)
- Alles intern: €0/mo aber schlechte Konsistenz (Session-State Variabilität)

**Status:** Accepted (Epic 2)

---

### ADR-003: PostgreSQL + pgvector statt Spezialisierte Vektor-DB

**Entscheidung:** PostgreSQL + pgvector Extension

**Rationale:**
- Production-Ready: Bewährte Reliability
- Single Database: Keine separate Vektor-DB nötig
- Native SQL: Einfache Queries für Hybrid Search
- Local-First: Keine Cloud-Dependencies

**Alternativen:**
- Pinecone/Weaviate: Cloud-Dependencies, Kosten
- Chroma/FAISS: Keine SQL-Integration, schwierigere Hybrid Search

**Status:** Accepted (Epic 1)

---

### ADR-004: IVFFlat statt HNSW für pgvector Index

**Entscheidung:** IVFFlat Index (lists=100)

**Rationale:**
- Balance Speed/Accuracy für <100k Vektoren
- Geringerer Memory-Footprint als HNSW
- Ausreichend für <1s Retrieval Time (NFR001)

**Alternativen:**
- HNSW: Schneller, aber mehr Memory (erwägen bei Performance-Problemen)
- Exact Search: Zu langsam für >10k Vektoren

**Status:** Accepted, Review bei Latency-Problemen (Epic 1, Story 3.5)

---

### ADR-005: Staged Dual Judge für Budget-Optimierung

**Entscheidung:**
- Phase 1 (3 Monate): Full Dual Judge (GPT-4o + Haiku)
- Phase 2 (ab Monat 4): Single Judge (GPT-4o) + 5% Spot Checks (Haiku)
- Transition Condition: Kappa >0.85 über letzte 100 Ground Truth Queries

**Rationale:**
- €5-10/mo → €2-3/mo (-40% Cost Reduction)
- Kappa >0.85 = "Almost Perfect Agreement" → Single Judge ausreichend
- 5% Spot Checks für Drift Detection

**Alternativen:**
- Permanent Dual Judge: €5-10/mo langfristig (zu teuer)
- Sofort Single Judge: Risiko für IRR <0.70 (methodisch unsauber)

**Status:** Accepted (Epic 3, Story 3.9)

---

_Generiert: 2025-11-09_
_Für: ethr (Cognitive Memory System v3.1.0-Hybrid)_
_Basierend auf: PRD v3.1.0-Hybrid + Epic Breakdown (33 Stories)_
