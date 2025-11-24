# Epic Technical Specification: MCP Server Foundation & Ground Truth Collection

Date: 2025-11-09
Author: ethr
Epic ID: 1
Status: Draft

---

## Overview

Epic 1 etabliert das technische und methodische Fundament für das Cognitive Memory System v3.1.0-Hybrid. Dieser Epic implementiert einen Python MCP Server mit PostgreSQL + pgvector-Persistence, 7 MCP Tools und 5 MCP Resources für die Integration mit Claude Code. Zusätzlich wird ein methodisch valides Ground Truth Set (50-100 gelabelte Queries) mit echten unabhängigen Dual Judges (GPT-4o + Haiku) gesammelt, um robuste Evaluation in Epic 2+3 zu ermöglichen.

**Ziel:** Funktionale MCP-basierte Persistence-Infrastruktur + statistisch robuste Evaluation-Baseline (Cohen's Kappa >0.70) für nachfolgende Hybrid Calibration und Model Drift Detection.

## Objectives and Scope

### In Scope

- PostgreSQL 15+ Installation mit pgvector Extension (lokal)
- Python MCP Server Implementation (7 Tools, 5 Resources)
- Datenbank-Schema für 6 Tabellen (l0_raw, l2_insights, working_memory, episode_memory, stale_memory, ground_truth)
- MCP Tool: `store_raw_dialogue` (L0 Raw Memory Storage)
- MCP Tool: `compress_to_l2_insight` (L2 Insights mit OpenAI Embeddings)
- MCP Tool: `hybrid_search` (Semantic + Keyword Search mit RRF Fusion)
- MCP Tool: `update_working_memory` (Session State mit LRU Eviction)
- MCP Tool: `store_episode` (Episode Memory Storage)
- MCP Tool: `store_dual_judge_scores` (GPT-4o + Haiku API Calls)
- MCP Tool: `get_golden_test_results` (Stub für Epic 3)
- MCP Resources (5x Read-Only URIs: memory://l2-insights, memory://working-memory, memory://episode-memory, memory://l0-raw, memory://stale-memory)
- Streamlit Ground Truth Labeling UI
- Dual Judge Implementation (GPT-4o + Haiku APIs)
- IRR Validation + Contingency Plan (Cohen's Kappa >0.70)
- 50-100 gelabelte Ground Truth Queries (Stratified Sampling)

### Out of Scope

- Claude Code Integration (Epic 2)
- Query Expansion Logik (Epic 2)
- CoT Generation (Epic 2)
- Reflexion-Framework (Epic 2)
- Hybrid Weight Calibration (Epic 2)
- Golden Test Set Creation (Epic 3)
- Model Drift Detection (Epic 3)
- Production Deployment (Epic 3)
- Systemd Daemonization (Epic 3)

## System Architecture Alignment

Dieser Epic implementiert die **MCP Server-Komponente** aus der Gesamt-Architektur (siehe architecture.md):

```
Claude Code (MAX Subscription)
      ↓ MCP Protocol (stdio)
Python MCP Server [THIS EPIC]
  ├── PostgreSQL + pgvector (lokale DB)
  ├── 7 MCP Tools (Actions)
  ├── 5 MCP Resources (Read-Only State)
  └── External API Calls
      ├── OpenAI Embeddings API (text-embedding-3-small)
      ├── GPT-4o API (Dual Judge)
      └── Haiku API (Dual Judge)
```

**Architektur-Constraints:**
- **Transport:** stdio (MCP Standard für lokale Server)
- **Datenbank:** PostgreSQL 15+ mit pgvector Extension (IVFFlat Index, lists=100)
- **Embedding-Dimension:** 1536 (OpenAI text-embedding-3-small)
- **Programming Language:** Python 3.11+ (Type Hints, MCP SDK Support)
- **API Integration:** OpenAI SDK + Anthropic SDK für externe Calls
- **No Multi-Threading:** Sequential Processing (MCP Server single-threaded)

**Referenced Components:**
- **Database Schema:** 6 Tabellen (l0_raw, l2_insights, working_memory, episode_memory, stale_memory, ground_truth) - siehe architecture.md Database Schema Section
- **MCP Tools:** 7 Tools definiert in FR001 des PRD
- **MCP Resources:** 5 Resources definiert in FR001 des PRD
- **External APIs:** OpenAI (Embeddings + GPT-4o), Anthropic (Haiku)

## Detailed Design

### Services and Modules

| Module | Responsibility | Inputs | Outputs | Owner/Story |
|--------|----------------|--------|---------|-------------|
| **MCP Server Core** | MCP Protocol Handshake, Tool/Resource Registration, Request Routing | MCP Protocol Messages (stdio) | MCP Response Messages | Story 1.3 |
| **Database Connection Pool** | PostgreSQL Connection Management | DB Credentials (.env) | psycopg2 Connection Objects | Story 1.2 |
| **L0 Storage Service** | Raw Dialogue Persistence | (session_id, speaker, content, metadata) | L0 Record ID | Story 1.4 |
| **L2 Compression Service** | Semantic Insight Creation + Embedding | (content, source_ids) | L2 Insight ID + Embedding | Story 1.5 |
| **Hybrid Search Service** | Semantic + Keyword Retrieval mit RRF | (query_embedding, query_text, weights) | Top-K L2 Insights | Story 1.6 |
| **Working Memory Service** | LRU Eviction + Importance Management | (content, importance) | Updated Working Memory State | Story 1.7 |
| **Episode Memory Service** | Reflexion Storage + Retrieval | (query, reward, reflection) | Episode ID | Story 1.8 |
| **OpenAI Embeddings Client** | text-embedding-3-small API Calls | Text String | 1536-dim Vector | Story 1.5 |
| **GPT-4o Dual Judge Client** | Dual Judge Evaluation via OpenAI | (query, docs) | Relevance Scores (0.0-1.0) | Story 1.11 |
| **Haiku Dual Judge Client** | Dual Judge Evaluation via Anthropic | (query, docs) | Relevance Scores (0.0-1.0) | Story 1.11 |
| **Cohen's Kappa Calculator** | Inter-Rater Reliability Validation | (judge1_scores, judge2_scores) | Kappa Value | Story 1.11 |
| **Ground Truth UI (Streamlit)** | Manual Query Labeling Interface | L0 Raw Memory (auto-extracted queries) | Labeled Ground Truth Set | Story 1.10 |
| **IRR Contingency Module** | Human Tiebreaker + Wilcoxon Test | Low-Kappa Queries | Recalibrated Ground Truth | Story 1.12 |

### Data Models and Contracts

**PostgreSQL Schema (6 Tabellen):**

```sql
-- Story 1.2: L0 Raw Memory
CREATE TABLE l0_raw (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    speaker VARCHAR(50) NOT NULL,  -- 'user' | 'assistant'
    content TEXT NOT NULL,
    metadata JSONB
);
CREATE INDEX idx_l0_session ON l0_raw(session_id, timestamp);

-- Story 1.2: L2 Insights
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

-- Story 1.2: Working Memory
CREATE TABLE working_memory (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    importance FLOAT NOT NULL CHECK (importance BETWEEN 0.0 AND 1.0),
    last_accessed TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_wm_accessed ON working_memory(last_accessed);

-- Story 1.2: Episode Memory
CREATE TABLE episode_memory (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    reward FLOAT NOT NULL CHECK (reward BETWEEN -1.0 AND 1.0),
    reflection TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    embedding vector(1536) NOT NULL
);
CREATE INDEX idx_episode_embedding ON episode_memory USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Story 1.2: Stale Memory (Enhancement E6)
CREATE TABLE stale_memory (
    id SERIAL PRIMARY KEY,
    original_content TEXT NOT NULL,
    archived_at TIMESTAMPTZ DEFAULT NOW(),
    importance FLOAT,
    reason VARCHAR(100)  -- 'LRU_EVICTION' | 'MANUAL_ARCHIVE'
);

-- Story 1.11: Ground Truth
CREATE TABLE ground_truth (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    expected_docs INTEGER[] NOT NULL,  -- L2 Insight IDs marked as relevant
    judge1_score FLOAT[],               -- GPT-4o scores per doc
    judge2_score FLOAT[],               -- Haiku scores per doc
    judge1_model VARCHAR(100),          -- 'gpt-4o'
    judge2_model VARCHAR(100),          -- 'claude-3-5-haiku-20241022'
    kappa FLOAT,                        -- Cohen's Kappa for this query
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**MCP Tool Contracts:**

```python
# Story 1.4
@mcp_tool
def store_raw_dialogue(session_id: str, speaker: str, content: str, metadata: dict = None) -> dict:
    """Returns: {"id": int, "timestamp": str}"""

# Story 1.5
@mcp_tool
def compress_to_l2_insight(content: str, source_ids: list[int]) -> dict:
    """Returns: {"id": int, "fidelity_score": float, "embedding_status": "success"}"""

# Story 1.6
@mcp_tool
def hybrid_search(query_embedding: list[float], query_text: str, top_k: int = 5,
                  weights: dict = {"semantic": 0.7, "keyword": 0.3}) -> list[dict]:
    """Returns: [{"id": int, "content": str, "score": float, "source_ids": list[int]}]"""

# Story 1.7
@mcp_tool
def update_working_memory(content: str, importance: float) -> dict:
    """Returns: {"added_id": int, "evicted_ids": list[int], "archived_ids": list[int]}"""

# Story 1.8
@mcp_tool
def store_episode(query: str, reward: float, reflection: str) -> dict:
    """Returns: {"id": int, "embedding_status": "success"}"""

# Story 1.11
@mcp_tool
def store_dual_judge_scores(query_id: int, query: str, docs: list[dict]) -> dict:
    """Returns: {"judge1_scores": list[float], "judge2_scores": list[float], "kappa": float}"""

# Story 3.2 (Stub in Epic 1)
@mcp_tool
def get_golden_test_results() -> dict:
    """Returns: {"date": str, "precision_at_5": float, "drift_detected": bool}"""
```

**MCP Resource URIs:**

```python
# Story 1.9
memory://l2-insights?query={q}&top_k={k}
memory://working-memory
memory://episode-memory?query={q}&min_similarity={t}
memory://l0-raw?session_id={id}&date_range={r}
memory://stale-memory?importance_min={t}
```

### APIs and Interfaces

**External API 1: OpenAI Embeddings (Story 1.5)**

```python
# Client: openai Python SDK
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Embedding Call
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=text,
    encoding_format="float"
)
embedding = response.data[0].embedding  # 1536-dim vector

# Cost: €0.02 per 1M tokens (~€0.00002 per query)
# Retry: 3 attempts mit Exponential Backoff (1s, 2s, 4s)
```

**External API 2: GPT-4o Dual Judge (Story 1.11)**

```python
# Client: openai Python SDK
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "Rate relevance of document for query (0.0-1.0)"},
        {"role": "user", "content": f"Query: {query}\nDocument: {doc}"}
    ],
    temperature=0.0  # Deterministisch
)
score = float(response.choices[0].message.content)

# Cost: ~€0.01 per query (100 queries = €1/mo)
# Retry: 4 attempts mit Exponential Backoff
```

**External API 3: Haiku Dual Judge (Story 1.11)**

```python
# Client: anthropic Python SDK
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

response = client.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=100,
    temperature=0.0,  # Deterministisch
    messages=[{"role": "user", "content": f"Query: {query}\nDocument: {doc}\nRate relevance (0.0-1.0)"}]
)
score = float(response.content[0].text)

# Cost: ~€0.01 per query
# Retry: 4 attempts mit Exponential Backoff
```

**MCP Protocol Interface (Story 1.3)**

```python
# Server Declaration
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("cognitive-memory-mcp")

# Tool Registration
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="store_raw_dialogue", ...),
        Tool(name="compress_to_l2_insight", ...),
        # ... alle 7 Tools
    ]

# Resource Registration
@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(uri="memory://l2-insights", ...),
        # ... alle 5 Resources
    ]

# Server Start (stdio transport)
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)
```

**Streamlit Ground Truth UI (Story 1.10)**

```python
import streamlit as st

# Query Extraction from L0
queries = extract_stratified_queries(
    l0_db_connection,
    target_count=100,
    distribution={"short": 0.4, "medium": 0.4, "long": 0.2}
)

# Labeling Interface
for query in queries:
    st.write(f"Query: {query}")
    docs = hybrid_search(query, top_k=5)

    for doc in docs:
        relevant = st.radio(f"Doc {doc.id} relevant?", ["Ja", "Nein"], key=doc.id)
        if relevant == "Ja":
            mark_as_relevant(query.id, doc.id)

    if st.button("Save & Next"):
        save_to_ground_truth(query.id)
```

### Workflows and Sequencing

**Workflow 1: L2 Insight Creation mit Embedding (Story 1.5)**

```
Claude Code (Epic 2)
  ↓ compress_to_l2_insight(content, source_ids)
MCP Server
  ├─ 1. Semantic Fidelity Check
  │    ├─ Calculate Information Density (semantic units / tokens)
  │    └─ If density <0.5: Warning (but proceed)
  ├─ 2. OpenAI Embeddings API Call
  │    ├─ text-embedding-3-small
  │    ├─ Retry on failure (3 attempts)
  │    └─ Return 1536-dim vector
  ├─ 3. PostgreSQL Insert
  │    ├─ INSERT INTO l2_insights (content, embedding, source_ids)
  │    └─ Return generated ID
  └─ 4. Response
       └─ {id, fidelity_score, embedding_status}
```

**Workflow 2: Hybrid Search mit RRF Fusion (Story 1.6)**

```
Claude Code (Epic 2)
  ↓ hybrid_search(query_embedding, query_text, top_k=5, weights)
MCP Server
  ├─ 1. Parallel Search Execution
  │    ├─ Semantic Search (pgvector)
  │    │    ├─ SELECT *, embedding <=> query_embedding AS distance
  │    │    ├─ ORDER BY distance LIMIT top_k
  │    │    └─ Apply weight: semantic (default 0.7)
  │    └─ Keyword Search (Full-Text)
  │         ├─ SELECT *, ts_rank(to_tsvector(content), query) AS rank
  │         ├─ ORDER BY rank LIMIT top_k
  │         └─ Apply weight: keyword (default 0.3)
  ├─ 2. RRF Fusion
  │    ├─ For each doc: score = Σ 1/(60 + rank_i)
  │    ├─ Merge beide result sets
  │    ├─ Deduplicate by L2 ID
  │    └─ Sort by final RRF score
  ├─ 3. Top-K Selection
  │    └─ Return top_k results
  └─ 4. Response
       └─ [{id, content, score, source_ids}]
```

**Workflow 3: Ground Truth Collection mit Dual Judge (Stories 1.10-1.11)**

```
ethr (User)
  ↓ Start Streamlit App
Ground Truth UI
  ├─ 1. Query Extraction (Story 1.10)
  │    ├─ SQL: SELECT * FROM l0_raw WHERE LENGTH(content) BETWEEN x AND y
  │    ├─ Stratified Sampling (40% short / 40% medium / 20% long)
  │    ├─ Temporal Diversity (3-5 queries per session)
  │    └─ Target: 50-100 queries
  ├─ 2. Manual Labeling (Story 1.10)
  │    ├─ For each query:
  │    │    ├─ Show query text
  │    │    ├─ Run hybrid_search → Top-5 docs
  │    │    ├─ User marks relevant docs (binary: Ja/Nein)
  │    │    └─ Save expected_docs to ground_truth table
  │    └─ Progress tracking: "68/100 queries labeled"
  ├─ 3. Dual Judge Evaluation (Story 1.11)
  │    ├─ For each labeled query:
  │    │    ├─ Call GPT-4o API → judge1_scores
  │    │    ├─ Call Haiku API → judge2_scores
  │    │    ├─ Parallel execution (asyncio)
  │    │    └─ Store in ground_truth table
  │    └─ Cost: €0.23 for 100 queries
  ├─ 4. Cohen's Kappa Calculation (Story 1.11)
  │    ├─ For each query:
  │    │    ├─ Convert scores to binary (>0.5 = relevant)
  │    │    ├─ Calculate agreement (P_o)
  │    │    └─ Calculate Kappa
  │    ├─ Aggregate: Macro-Average Kappa
  │    └─ Target: Kappa >0.70
  └─ 5. IRR Validation (Story 1.12)
       ├─ If Kappa ≥0.70: Success
       └─ If Kappa <0.70: Contingency Plan
            ├─ Human Tiebreaker (Disagreements >0.4)
            ├─ Wilcoxon Signed-Rank Test (systematic bias?)
            └─ Judge Recalibration (adjust prompts)
```

**Workflow 4: Working Memory Eviction (Story 1.7)**

```
Claude Code (Epic 2)
  ↓ update_working_memory(content, importance)
MCP Server
  ├─ 1. Insert New Item
  │    └─ INSERT INTO working_memory (content, importance, last_accessed)
  ├─ 2. Check Capacity
  │    ├─ SELECT COUNT(*) FROM working_memory
  │    └─ If count >10: Trigger Eviction
  ├─ 3. LRU Eviction with Importance Override
  │    ├─ SELECT * FROM working_memory ORDER BY last_accessed ASC
  │    ├─ Skip items with importance >0.8 (Critical)
  │    ├─ Identify oldest non-critical item
  │    └─ Archive to stale_memory (Enhancement E6)
  ├─ 4. Delete Evicted Item
  │    └─ DELETE FROM working_memory WHERE id = evicted_id
  └─ 5. Response
       └─ {added_id, evicted_ids, archived_ids}
```

## Non-Functional Requirements

### Performance

**Targets (Epic 1 Scope):**

- **PostgreSQL Query Time:** <100ms (p95) für einzelne Retrieval-Operationen
- **Hybrid Search Latency:** <1s (p95) inkl. pgvector + Full-Text Search + RRF Fusion
- **OpenAI Embeddings API:** <500ms (p95) für single embedding call
- **Dual Judge Evaluation:** <2s (p95) für beide API calls parallel (GPT-4o + Haiku)
- **Streamlit UI Response:** <500ms für Query-Anzeige, <2s für hybrid_search Aufruf

**Optimizations:**

- IVFFlat Index für pgvector (lists=100) → schnellere Approximate Nearest Neighbor Search
- Full-Text Search Index (GIN) für keyword search
- Connection Pooling (psycopg2.pool) bei >100 concurrent requests
- Parallel API Calls (asyncio) für Dual Judge (2x Latency Reduction)

**Out of Scope für Epic 1:**
- End-to-End RAG Pipeline Latency (<5s) → Epic 2
- Query Expansion Overhead → Epic 2
- CoT Generation Time → Epic 2

### Security

**Authentication & Authorization:**

- Kein Multi-User Support (Personal Use, nur ethr)
- PostgreSQL User: `mcp_user` mit beschränkten Rechten (kein DROP, kein CREATE USER)
- API Keys in .env File (chmod 600, nicht in Git)
- MCP Server läuft lokal (keine externe Exposition)

**Data Handling:**

- Alle Konversationsdaten bleiben lokal (PostgreSQL)
- Externe APIs erhalten nur Text-Snippets (keine vollständigen Transkripte)
- Keine User-Daten werden für API-Training verwendet (OpenAI/Anthropic Policies)
- Ground Truth enthält nur Queries (keine persönlichen Informationen)

**Threat Model:**

- **In Scope:** Lokaler Datenverlust (mitigiert durch Backups - Epic 3)
- **Out of Scope:** Network-basierte Angriffe (kein externes Network Exposure)
- **Out of Scope:** Multi-User Privilege Escalation (nur 1 User)

**Compliance:**

- GDPR-konform (alle Daten lokal, kein Cloud-Storage)
- Keine PII in Ground Truth Set (nur philosophische Queries)

### Reliability/Availability

**Target Availability:**

- **MCP Server Uptime:** Best-Effort (lokales System, manueller Start)
- **PostgreSQL Uptime:** 99%+ (systemd auto-restart - Epic 3)
- **External API Availability:** 99.9% (OpenAI/Anthropic SLA)

**Error Handling (Epic 1):**

- **OpenAI API Failures:** 3 Retries mit Exponential Backoff (1s, 2s, 4s)
- **PostgreSQL Connection Loss:** Auto-reconnect bei Transient Errors
- **Dual Judge API Failures:** Log Error, continue with available judge (degrade gracefully)
- **Invalid MCP Tool Parameters:** Return error message (nicht crashen)

**Data Integrity:**

- **Critical Items Protection:** Importance >0.8 Items werden archiviert, nicht gelöscht (Enhancement E6)
- **Ground Truth Immutability:** Keine Updates nach Initial Labeling (fixed baseline)
- **JSONB Validation:** Metadata-Felder werden validiert vor Insert

**Degraded Modes:**

- **Partial Dual Judge:** Falls GPT-4o ausfällt → nur Haiku (Kappa nicht berechenbar, aber Labeling möglich)
- **No Embeddings:** Falls OpenAI API ausfällt → nur Keyword Search (degraded retrieval)

**Out of Scope für Epic 1:**
- Fallback zu Claude Code Evaluation → Epic 3
- Automated Health Checks → Epic 3
- Systemd Watchdog → Epic 3

### Observability

**Logging (Epic 1):**

- **MCP Server Logs:** Structured JSON Logging (Python `logging` module)
  - Tool Calls: Tool name, parameters, execution time, success/failure
  - API Calls: Endpoint, latency, response status, retry count
  - Database Operations: Query type, execution time, row count
- **PostgreSQL Logs:** Query logs enabled (log_statement = 'all' during development)
- **Streamlit UI Logs:** User actions (Query viewed, Doc labeled, Progress saved)

**Metrics (Epic 1):**

- **Ground Truth Progress:** Queries labeled count, Stratification balance (short/medium/long %)
- **Cohen's Kappa:** Per-query Kappa, Macro-average Kappa, Judge agreement rate
- **API Usage:** Embeddings API calls count, Dual Judge calls count, Total cost (€)
- **Database Size:** L0 rows, L2 rows, Working Memory size, Episode Memory size

**Tracing:**

- Basic request IDs für MCP Tool Calls (correlation zwischen Claude Code ↔ MCP Server)
- No distributed tracing (single MCP Server, kein Microservices)

**Alerting (Epic 1 Scope):**

- **Cohen's Kappa <0.70:** Manual alert in Streamlit UI (IRR Contingency trigger)
- **API Budget >€1:** Warning in logs (Ground Truth collection exceeded budget)
- **PostgreSQL Connection Failure:** Error log (manual intervention erforderlich)

**Out of Scope für Epic 1:**
- Model Drift Detection Alerts → Epic 3
- Budget Monitoring Dashboard → Epic 3
- Prometheus/Grafana Integration → Out of Scope v3.1

## Dependencies and Integrations

**Python Dependencies (Story 1.1):**

```toml
# pyproject.toml (Poetry) oder requirements.txt
[tool.poetry.dependencies]
python = "^3.11"
mcp = "^1.0.0"                    # Python MCP SDK
psycopg2-binary = "^2.9.9"       # PostgreSQL adapter
pgvector = "^0.2.0"              # pgvector Python client
openai = "^1.0.0"                # OpenAI API client
anthropic = "^0.18.0"            # Anthropic API client
numpy = "^1.26.0"                # Vector operations
streamlit = "^1.28.0"            # Ground Truth UI
scipy = "^1.11.0"                # Cohen's Kappa calculation
python-dotenv = "^1.0.0"         # Environment variables

[tool.poetry.dev-dependencies]
black = "^23.0.0"                # Code formatter
ruff = "^0.1.0"                  # Linter
mypy = "^1.7.0"                  # Type checker
pytest = "^7.4.0"                # Testing framework
```

**System Dependencies (Story 1.2):**

```bash
# Ubuntu/Debian
apt-get install postgresql-15 postgresql-contrib-15
apt-get install build-essential git

# pgvector Extension (from source)
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
make install  # Requires PostgreSQL dev headers
```

**External Services:**

| Service | Version/Model | Purpose | Cost | Story |
|---------|---------------|---------|------|-------|
| **OpenAI Embeddings** | text-embedding-3-small | L2 Insight Embeddings | €0.02/1M tokens | 1.5 |
| **OpenAI GPT-4o** | gpt-4o | Dual Judge Evaluation | €0.01/query | 1.11 |
| **Anthropic Haiku** | claude-3-5-haiku-20241022 | Dual Judge Evaluation | €0.01/query | 1.11 |
| **PostgreSQL** | 15+ | Persistence Layer | €0 (lokal) | 1.2 |

**Integration Points:**

```
MCP Server (Python)
  ├─ PostgreSQL (psycopg2)
  │    └─ Connection String: postgresql://mcp_user:***@localhost:5432/cognitive_memory
  ├─ OpenAI API (openai SDK)
  │    ├─ Embeddings Endpoint: https://api.openai.com/v1/embeddings
  │    └─ Chat Endpoint: https://api.openai.com/v1/chat/completions
  ├─ Anthropic API (anthropic SDK)
  │    └─ Messages Endpoint: https://api.anthropic.com/v1/messages
  └─ Claude Code (MCP Protocol)
       └─ Transport: stdio (Standard Input/Output)
```

**Configuration Management (Story 1.1):**

```bash
# .env.template
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=cognitive_memory
POSTGRES_USER=mcp_user
POSTGRES_PASSWORD=***
```

**Version Constraints:**

- Python 3.11+ (Type Hints, better async support)
- PostgreSQL 15+ (pgvector compatibility)
- pgvector 0.5.0+ (IVFFlat index support)
- MCP SDK 1.0+ (stable MCP Protocol)
- OpenAI SDK 1.0+ (new API structure)
- Anthropic SDK 0.18+ (Haiku model support)

## Acceptance Criteria (Authoritative)

**AC-1.1: Projekt-Setup (Story 1.1)**
- Python-Projekt mit Poetry/pip requirements existiert (mcp, psycopg2, openai, anthropic, numpy)
- Git-Repository mit .gitignore (PostgreSQL credentials, .env)
- Projektstruktur: `/mcp_server/`, `/tests/`, `/docs/`, `/config/`
- Environment-Template (.env.template) für API-Keys und DB-Credentials
- README.md mit Setup-Anleitung vorhanden
- Virtual Environment erstellt, Dependencies installiert
- Pre-commit Hooks für Code-Qualität (black, ruff, mypy)

**AC-1.2: PostgreSQL + pgvector Setup (Story 1.2)**
- PostgreSQL 15+ läuft lokal (systemctl status postgresql)
- pgvector Extension installiert (CREATE EXTENSION vector erfolgt)
- Datenbank `cognitive_memory` erstellt
- User `mcp_user` mit Passwort existiert
- Alle 6 Tabellen existieren (l0_raw, l2_insights, working_memory, episode_memory, stale_memory, ground_truth)
- IVFFlat Indizes existieren für l2_insights.embedding und episode_memory.embedding
- Full-Text Search Index existiert für l2_insights (GIN)
- Connection von Python erfolgreich (psycopg2.connect())

**AC-1.3: MCP Server Grundstruktur (Story 1.3)**
- MCP Server startet via stdio transport
- 7 Tools registriert (list_tools() response)
- 5 Resources registriert (list_resources() response)
- MCP Inspector kann Server erreichen (handshake erfolgreich)
- Tool-Stubs implementiert (return Placeholder-Responses)

**AC-1.4: L0 Raw Memory Storage (Story 1.4)**
- MCP Tool `store_raw_dialogue` implementiert
- Parameter-Validierung: session_id (UUID), speaker (user|assistant), content (non-empty)
- PostgreSQL INSERT in l0_raw Tabelle
- Return: {id, timestamp}
- Test: 10 Dialogzeilen speichern → 10 rows in l0_raw

**AC-1.5: L2 Insights Storage mit Embedding (Story 1.5)**
- MCP Tool `compress_to_l2_insight` implementiert
- OpenAI Embeddings API Call (text-embedding-3-small)
- Semantic Fidelity Check: Information Density berechnet, Warning bei <0.5
- PostgreSQL INSERT in l2_insights (content, embedding, source_ids)
- Return: {id, fidelity_score, embedding_status}
- Test: 5 Insights erstellen → 5 rows mit 1536-dim embeddings

**AC-1.6: Hybrid Search Implementation (Story 1.6)**
- MCP Tool `hybrid_search` implementiert
- Semantic Search via pgvector (cosine similarity)
- Keyword Search via Full-Text Search (ts_rank)
- RRF Fusion: score = Σ 1/(60 + rank_i)
- Configurable weights (default: semantic 0.7, keyword 0.3)
- Return: Top-K L2 Insights mit scores
- Test: Query "Autonomie" findet relevante Insights (Top-5)

**AC-1.7: Working Memory Management (Story 1.7)**
- MCP Tool `update_working_memory` implementiert
- LRU Eviction bei >10 Items
- Importance Override: Items mit importance >0.8 werden nicht evicted
- Kritische Items werden zu stale_memory archiviert (Enhancement E6)
- Return: {added_id, evicted_ids, archived_ids}
- Test: 15 Items hinzufügen → 5 evicted, 2 davon archiviert

**AC-1.8: Episode Memory Storage (Story 1.8)**
- MCP Tool `store_episode` implementiert
- Parameter: query, reward (-1.0 bis +1.0), reflection (non-empty)
- OpenAI Embeddings API Call für query
- PostgreSQL INSERT in episode_memory
- Return: {id, embedding_status}
- Test: 3 Episodes speichern → 3 rows mit embeddings

**AC-1.9: MCP Resources Implementation (Story 1.9)**
- 5 MCP Resources implementiert mit URIs:
  - memory://l2-insights?query={q}&top_k={k}
  - memory://working-memory
  - memory://episode-memory?query={q}&min_similarity={t}
  - memory://l0-raw?session_id={id}&date_range={r}
  - memory://stale-memory?importance_min={t}
- Read-Only State Exposure (keine Mutations)
- Test: Alle 5 Resources abrufbar via MCP Inspector

**AC-1.10: Ground Truth Collection UI (Story 1.10)**
- Streamlit App läuft (streamlit run app.py)
- Query Extraction: Stratified Sampling (40% short / 40% medium / 20% long)
- 50-100 Queries aus l0_raw extrahiert
- Labeling Interface: User kann Docs als relevant/nicht-relevant markieren
- Progress Tracking: "68/100 Queries gelabelt" angezeigt
- Save to ground_truth table (expected_docs als INTEGER[])

**AC-1.11: Dual Judge Implementation (Story 1.11)**
- MCP Tool `store_dual_judge_scores` implementiert
- GPT-4o API Call: Rate relevance (0.0-1.0) für jeden Doc
- Haiku API Call: Rate relevance (0.0-1.0) für jeden Doc
- Parallel Execution (asyncio) → <2s für beide calls
- Cohen's Kappa Berechnung (scipy.stats.cohen_kappa_score)
- Store in ground_truth: judge1_scores, judge2_scores, judge1_model, judge2_model, kappa
- Test: 10 Queries evaluieren → Macro-Average Kappa >0.70

**AC-1.12: IRR Validation & Contingency (Story 1.12)**
- Kappa >0.70: Success Message, kein Contingency Plan nötig
- Kappa <0.70: Contingency Plan aktiviert:
  - Human Tiebreaker für Disagreements >0.4
  - Wilcoxon Signed-Rank Test (systematischer Bias?)
  - Judge Recalibration (Prompt-Adjustments)
- Re-evaluation nach Contingency → neuer Kappa berechnet
- Documentation: Contingency-Schritte in README.md
- Test: Simuliere Low-Kappa Scenario (mocked API responses)

## Traceability Mapping

| AC | PRD Requirement | Spec Section | Component/API | Test Strategy |
|----|----------------|--------------|---------------|---------------|
| **AC-1.1** | FR001 (MCP Server Setup) | Dependencies and Integrations | Project Structure, Poetry, .env | Integration Test: `pytest tests/test_setup.py` (check dependencies installed) |
| **AC-1.2** | FR002 (L0 Raw), FR003 (L2 Insights) | Data Models and Contracts (PostgreSQL Schema) | PostgreSQL, pgvector, 6 Tables | Integration Test: `pytest tests/test_database.py` (check all tables + indices exist) |
| **AC-1.3** | FR001 (7 Tools, 5 Resources) | APIs and Interfaces (MCP Protocol) | MCP Server Core | Integration Test: MCP Inspector handshake, `list_tools()`, `list_resources()` |
| **AC-1.4** | FR002 (L0 Raw Memory) | Data Models (l0_raw table), Workflows (L0 Storage) | L0 Storage Service | Unit Test: Mock DB insert, Integration Test: Store 10 dialogues, verify DB rows |
| **AC-1.5** | FR003 (L2 Insights + Embeddings) | Data Models (l2_insights table), APIs (OpenAI Embeddings), Workflows (L2 Creation) | L2 Compression Service, OpenAI Embeddings Client | Unit Test: Mock OpenAI API, Integration Test: Create 5 insights, verify embeddings (1536-dim) |
| **AC-1.6** | FR004 (Hybrid Retrieval) | Workflows (Hybrid Search mit RRF) | Hybrid Search Service | Unit Test: RRF Fusion Logic, Integration Test: Query "Autonomie", verify Top-5 results |
| **AC-1.7** | FR008 (Working Memory + LRU) | Workflows (Working Memory Eviction) | Working Memory Service | Unit Test: LRU Logic + Importance Override, Integration Test: Add 15 items, verify 5 evicted + 2 archived |
| **AC-1.8** | FR009 (Episode Memory) | Data Models (episode_memory table) | Episode Memory Service | Integration Test: Store 3 episodes, verify embeddings + retrieval |
| **AC-1.9** | FR001 (5 Resources) | APIs and Interfaces (MCP Resources) | MCP Server Core | Integration Test: Read all 5 resources via MCP Inspector, verify responses |
| **AC-1.10** | FR010 (Ground Truth Collection) | Workflows (Ground Truth Collection), APIs (Streamlit UI) | Ground Truth UI (Streamlit) | Manual Test: Run Streamlit app, label 10 queries, verify progress tracking |
| **AC-1.11** | FR010 (Dual Judge + IRR) | APIs (GPT-4o, Haiku), Workflows (Dual Judge Evaluation) | GPT-4o Client, Haiku Client, Cohen's Kappa Calculator | Unit Test: Mock API responses, Integration Test: Evaluate 10 queries, verify Kappa >0.70 |
| **AC-1.12** | FR010 (IRR Contingency, Enhancement E1) | Workflows (IRR Validation) | IRR Contingency Module | Unit Test: Simulate Low-Kappa scenario, Integration Test: Trigger contingency, verify re-evaluation |

**PRD → Epic 1 Coverage:**

- **FR001:** MCP Server Setup → AC-1.1, AC-1.3, AC-1.9
- **FR002:** L0 Raw Memory → AC-1.2, AC-1.4
- **FR003:** L2 Insights + Embeddings → AC-1.2, AC-1.5
- **FR004:** Hybrid Retrieval → AC-1.6
- **FR008:** Working Memory → AC-1.7
- **FR009:** Episode Memory → AC-1.8
- **FR010:** Ground Truth + Dual Judge → AC-1.2, AC-1.10, AC-1.11, AC-1.12
- **NFR002:** Accuracy (IRR Kappa >0.70) → AC-1.11, AC-1.12
- **NFR007:** Methodological Validity → AC-1.11 (true independent judges)

## Risks, Assumptions, Open Questions

### Risks

**Risk-1.1: MCP Protocol Komplexität (High Impact)**
- **Description:** MCP SDK ist neu, wenig dokumentiert, potenzielle Bugs im stdio transport
- **Impact:** Blocker für gesamtes System (MCP Server nicht nutzbar)
- **Probability:** Medium (20%)
- **Mitigation:**
  - MCP Inspector für Testing nutzen (Story 1.3)
  - Python MCP SDK ist stabiler als TypeScript SDK
  - Fallback: Standalone REST API wenn MCP nicht funktioniert (out of scope v3.1, aber dokumentiert)
- **Owner:** Story 1.3

**Risk-1.2: Cohen's Kappa <0.70 (Medium Impact)**
- **Description:** Dual Judges (GPT-4o + Haiku) disagreen systematisch → Ground Truth nicht robust
- **Impact:** Critical Path Blockade (Epic 2 Calibration benötigt valides Ground Truth)
- **Probability:** Low (10% dank true independence)
- **Mitigation:**
  - IRR Contingency Plan implementiert (Enhancement E1, Story 1.12)
  - 3 Fallback-Strategien: Human Tiebreaker, Wilcoxon Test, Judge Recalibration
  - v3.1 Improvement: True independence → höhere Wahrscheinlichkeit für Kappa >0.70
- **Owner:** Story 1.12

**Risk-1.3: PostgreSQL Performance bei 10K+ L2 Insights (Low Impact)**
- **Description:** IVFFlat Index könnte bei großen Datensätzen langsame Queries verursachen
- **Impact:** Latency-Erhöhung (1s → 2-3s), aber kein Systemausfall
- **Probability:** Low (10%)
- **Mitigation:**
  - IVFFlat Index mit lists=100 (optimiert für 10K-100K vectors)
  - Monitoring in Epic 3
  - Upgrade zu Cloud-DB falls nötig (out of scope)
- **Owner:** Story 1.2

**Risk-1.4: External API Availability (Low Impact)**
- **Description:** OpenAI/Anthropic API Ausfall während Ground Truth Collection
- **Impact:** Temporary blockage (kann später wiederholt werden)
- **Probability:** Low (1-2% Ausfallrate/Jahr)
- **Mitigation:**
  - Retry-Logic mit Exponential Backoff (3-4 attempts)
  - Ground Truth Collection ist einmalig (nicht production-critical)
  - Manual re-run bei Failure
- **Owner:** Story 1.5, 1.11

### Assumptions

**Assumption-1.1: Ground Truth Quality**
- ethr kann 50-100 Queries manuell labeln mit konsistenten Entscheidungen
- Stratified Sampling liefert repräsentative Query-Verteilung
- Binäre Entscheidungen (Relevant/Nicht-Relevant) sind ausreichend (keine Graded Relevance)

**Assumption-1.2: PostgreSQL Capacity**
- Lokales System (ethr's Machine) hat ausreichend Disk Space für PostgreSQL (min. 10GB)
- PostgreSQL 15+ ist verfügbar via apt/brew
- pgvector Extension kann erfolgreich kompiliert werden (build-essential installiert)

**Assumption-1.3: API Budget**
- €0.23 für Ground Truth Collection (100 Queries) ist akzeptabel
- OpenAI/Anthropic API Keys sind verfügbar (ethr hat Accounts)
- API-Preise bleiben stabil während Epic 1 (2-3 Wochen)

**Assumption-1.4: MCP Protocol Stability**
- Python MCP SDK 1.0+ ist production-ready
- stdio transport funktioniert zuverlässig auf ethr's System (Linux)
- Claude Code kann MCP Server erreichen (kein Firewall-Blocking)

### Open Questions

**Question-1.1: Ground Truth Set Size**
- **Q:** 50 oder 100 Queries für Ground Truth?
- **Context:** Mehr Queries → bessere statistische Robustheit, aber höhere Labeling-Kosten
- **Decision Needed By:** Start of Story 1.10
- **Default:** 50 Queries (Budget €0.12), extend zu 100 falls Kappa <0.70

**Question-1.2: Hybrid Weight Defaults**
- **Q:** Semantic 0.7 / Keyword 0.3 als Default-Weights in Epic 1?
- **Context:** MEDRAG-Paper empfiehlt 0.7/0.3, aber psychologische Transkripte könnten 0.8/0.2 bevorzugen
- **Decision Needed By:** Story 1.6
- **Default:** 0.7/0.3 (wird in Epic 2 kalibriert)

**Question-1.3: Working Memory Capacity**
- **Q:** 8 oder 10 Items als Working Memory Limit?
- **Context:** PRD spezifiziert "8-10 Items", Architecture.md spezifiziert "10 Items"
- **Decision Needed By:** Story 1.7
- **Default:** 10 Items (Architecture.md wins)

## Test Strategy Summary

### Test Levels

**Unit Tests (pytest):**
- **Scope:** Einzelne Funktionen/Methoden isoliert testen
- **Coverage Target:** >80% für business logic
- **Examples:**
  - RRF Fusion Logic (Story 1.6): Mock beide result sets, verify merged scores
  - LRU Eviction Logic (Story 1.7): Mock DB, verify eviction order + importance override
  - Cohen's Kappa Calculation (Story 1.11): Test-Daten mit bekannten Kappa-Werten
  - Information Density Check (Story 1.5): Test edge cases (density 0.0, 0.5, 1.0)
- **Mocking:** API calls (OpenAI, Anthropic), DB connections (psycopg2)

**Integration Tests (pytest):**
- **Scope:** End-to-End Tests mit echten Dependencies (PostgreSQL, ggf. mocked APIs)
- **Coverage Target:** Alle 12 Acceptance Criteria
- **Examples:**
  - Database Setup (AC-1.2): Check all 6 tables + indices exist
  - MCP Server Handshake (AC-1.3): Start server, verify MCP Inspector connection
  - L2 Insight Creation (AC-1.5): Call tool, verify embedding in DB (1536-dim)
  - Hybrid Search (AC-1.6): Insert test data, query, verify Top-5 results
  - Working Memory Eviction (AC-1.7): Add 15 items, verify eviction + archival
- **Test Database:** Separate `cognitive_memory_test` DB (teardown nach jedem Test)

**API Integration Tests (pytest + VCR.py):**
- **Scope:** Test API calls mit recorded responses (VCR cassettes)
- **Coverage:** OpenAI Embeddings, GPT-4o, Haiku API calls
- **Examples:**
  - OpenAI Embeddings (Story 1.5): Record response, replay in tests
  - Dual Judge (Story 1.11): Mock both API calls, verify Kappa calculation
- **Rationale:** Avoid API costs während Testing, deterministic results

**Manual Tests:**
- **Scope:** UI/UX Tests, End-to-End Workflows
- **Examples:**
  - Streamlit Ground Truth UI (AC-1.10): Run app, label 10 queries, verify progress
  - MCP Inspector (AC-1.3): Handshake, list tools/resources, call tool
  - IRR Contingency (AC-1.12): Manually trigger low-Kappa scenario
- **Documentation:** Test cases in `tests/manual/README.md`

### Test Frameworks

- **pytest:** Unit + Integration Tests
- **pytest-mock:** Mocking framework
- **VCR.py:** API response recording
- **pytest-cov:** Coverage reporting
- **MCP Inspector:** MCP Protocol testing (separate tool)

### Coverage Strategy

**Critical Paths (Must be tested):**
1. MCP Server Handshake + Tool Registration (AC-1.3)
2. L2 Insight Creation + Embedding (AC-1.5)
3. Hybrid Search RRF Fusion (AC-1.6)
4. Dual Judge + Kappa Calculation (AC-1.11)
5. IRR Contingency Plan (AC-1.12)

**Edge Cases:**
- Empty query → hybrid_search returns []
- Invalid UUID → store_raw_dialogue returns error
- API timeout → retry logic triggers
- Kappa <0.70 → contingency plan activates
- Working Memory full + all items importance >0.8 → evict oldest anyway (override limit)

**Performance Tests (Out of Scope for Epic 1):**
- Load testing (1000+ concurrent queries) → Epic 3
- Latency benchmarking (<5s p95) → Epic 2+3
- Database performance (10K+ vectors) → Epic 3

### Test Data

**Fixtures (pytest):**
- `test_dialogues.json`: 50 sample L0 dialogue lines
- `test_insights.json`: 20 pre-embedded L2 insights (with embeddings)
- `test_queries.json`: 10 test queries (short, medium, long)
- `test_ground_truth.json`: 5 labeled queries mit expected_docs

**Database Seeding:**
- `tests/fixtures/seed_db.py`: Populate test DB with realistic data
- Stratified Sampling: 40% short / 40% medium / 20% long queries

### Success Criteria

**Epic 1 Passed wenn:**
- ✅ Alle 12 Acceptance Criteria erfüllt
- ✅ Unit Test Coverage >80%
- ✅ Alle Integration Tests grün
- ✅ MCP Inspector Handshake erfolgreich
- ✅ Cohen's Kappa >0.70 (oder Contingency Plan dokumentiert)
- ✅ Ground Truth Set: 50-100 Queries gelabelt
- ✅ No blocking bugs in MCP Server

**Definition of Done:**
- Code reviewed (selbst oder pair programming)
- Tests geschrieben + passing
- Documentation updated (README.md, docstrings)
- Epic-1 Status → "contexted" in sprint-status.yaml
