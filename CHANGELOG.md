# Changelog

All notable changes to the **Cognitive Memory System** project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [3.1.0-Hybrid] - 2025-11-24

### Epic 3: Production Readiness - COMPLETED

Full production deployment with monitoring, stability testing, and comprehensive documentation.

#### Added
- **Story 3.1:** Golden Test Set (separate from Ground Truth) for daily Precision@5 regression testing
- **Story 3.2:** Model Drift Detection with daily Golden Test execution (`get_golden_test_results` MCP tool)
- **Story 3.3:** API Retry-Logic with Exponential Backoff (1s, 2s, 4s, 8s delays, ±20% jitter)
- **Story 3.4:** Claude Code Fallback for Haiku API outage (degraded mode with auto-recovery)
- **Story 3.5:** Latency Benchmarking infrastructure with p50/p95/p99 tracking
- **Story 3.6:** PostgreSQL Backup Strategy (daily pg_dump, 7-day retention, RTO <1h, RPO <24h)
- **Story 3.7:** Production Configuration with environment separation (`.env.development`, `.env.production`)
- **Story 3.8:** MCP Server Daemonization via systemd with auto-start and watchdog
- **Story 3.9:** Staged Dual Judge Implementation (transition from Dual to Single Judge when Kappa >0.85)
- **Story 3.10:** Budget Monitoring Dashboard with daily cost tracking and €10/mo alert threshold
- **Story 3.11:** 7-Day Stability Testing validation (168h continuous operation)
- **Story 3.12:** Production Handoff Documentation (README, installation guide, operations manual, troubleshooting)

#### Production Metrics
- **Budget:** €5-10/mo (→ €2-3/mo after Staged Dual Judge)
- **Uptime:** 100% over 7-day stability test
- **Latency:** p95 <5s achieved

---

### Epic 2: RAG Pipeline & Hybrid Calibration - COMPLETED

Full RAG pipeline with Claude Code integration, external evaluation APIs, and optimized hybrid search.

#### Added
- **Story 2.1:** Claude Code MCP Client integration with all 7 tools and 5 resources
- **Story 2.2:** Query Expansion logic (3 semantic variants internally in Claude Code, €0/mo)
- **Story 2.3:** Chain-of-Thought (CoT) Generation Framework (Thought → Reasoning → Answer → Confidence)
- **Story 2.4:** External API Setup for Haiku (Evaluation + Reflexion)
- **Story 2.5:** Self-Evaluation with Haiku API (Reward -1.0 to +1.0)
- **Story 2.6:** Reflexion-Framework with Verbal Reinforcement Learning (triggers at Reward <0.3)
- **Story 2.7:** End-to-End RAG Pipeline Testing (all 9 pipeline steps validated)
- **Story 2.8:** Hybrid Weight Calibration via Grid Search (semantic=0.8, keyword=0.2 optimal)
- **Story 2.9:** Precision@5 Validation on Ground Truth Set

#### Performance Results
- **Precision@5:** 0.72 (Partial Success - deployed with monitoring)
- **Calibrated Weights:** semantic=0.8, keyword=0.2 (vs MEDRAG default 0.7/0.3)
- **End-to-End Latency:** <5s (p95)

---

### Epic 1: MCP Server Foundation & Ground Truth Collection - COMPLETED

Technical and methodological foundation with Python MCP Server and validated Ground Truth.

#### Added
- **Story 1.1:** Project Setup with Python 3.11+, Poetry, pre-commit hooks (black, ruff, mypy)
- **Story 1.2:** PostgreSQL + pgvector Setup with IVFFlat index (lists=100)
- **Story 1.3:** MCP Server Framework with Tool/Resource Registration (stdio transport)
- **Story 1.4:** L0 Raw Memory Storage (`store_raw_dialogue` MCP tool)
- **Story 1.5:** L2 Insights Storage with Embeddings (`compress_to_l2_insight` MCP tool)
- **Story 1.6:** Hybrid Search Implementation (`hybrid_search` MCP tool with RRF fusion)
- **Story 1.7:** Working Memory Management (`update_working_memory` MCP tool with LRU eviction)
- **Story 1.8:** Episode Memory Storage (`store_episode` MCP tool)
- **Story 1.9:** MCP Resources for Read-Only State Exposure (5 resources with `memory://` URI scheme)
- **Story 1.10:** Ground Truth Collection UI (Streamlit App with stratified sampling)
- **Story 1.11:** Dual Judge Implementation with GPT-4o + Haiku (`store_dual_judge_scores` MCP tool)
- **Story 1.12:** IRR Validation & Contingency Plan (Cohen's Kappa >0.70 achieved)

#### Database Schema
- `l0_raw` - Complete dialogue transcripts
- `l2_insights` - Compressed semantic units with 1536-dim embeddings
- `working_memory` - Session context (8-10 items, LRU eviction)
- `episode_memory` - Verbalized reflections (Verbal RL)
- `stale_memory` - Archived critical items
- `ground_truth` - Labeled queries with Dual Judge scores

#### MCP Tools (7)
1. `store_raw_dialogue` - L0 Storage
2. `compress_to_l2_insight` - L2 Creation + Embedding
3. `hybrid_search` - RAG Retrieval
4. `update_working_memory` - Session State
5. `store_episode` - Reflexion Storage
6. `get_golden_test_results` - Model Drift Detection
7. `store_dual_judge_scores` - IRR Validation

#### MCP Resources (5)
1. `memory://l2-insights?query={q}&top_k={k}`
2. `memory://working-memory`
3. `memory://episode-memory?query={q}&min_similarity={t}`
4. `memory://l0-raw?session_id={id}&date_range={r}`
5. `memory://stale-memory?importance_min={t}`

---

## Architecture Overview

```
Claude Code (MAX Subscription)
├─ Generation, Planning, CoT (€0/mo, internal)
├─ MCP Protocol ↕
└─ MCP Server (Python, local)
   ├─ PostgreSQL + pgvector (Persistence)
   ├─ L0 Raw Memory (complete transcripts)
   ├─ L2 Insights (adaptive compression)
   ├─ Working Memory (8-10 Items, LRU)
   └─ Episode Memory (Reflexions)
       ↓
   External APIs (€5-10/mo)
   ├─ OpenAI Embeddings (€0.06/mo)
   ├─ GPT-4o Dual Judge (€1-1.5/mo)
   ├─ Haiku Dual Judge (€1-1.5/mo)
   └─ Haiku Evaluation/Reflexion (€1-2/mo)
```

---

## Budget Summary

| Phase | Budget | Description |
|-------|--------|-------------|
| Development | €0.23 | 100 queries Dual Judge |
| Production (Month 1-3) | €5-10/mo | Full Dual Judge |
| Production (Month 4+) | €2-3/mo | Staged Dual Judge (Single + 5% spot checks) |

**90-95% cost reduction vs. v2.4.1** (€106/mo → €5-10/mo)

---

## Timeline

- **Total:** 133-175 hours (2.5-3.5 months at 20h/week)
- **Epic 1:** 38-50h (Foundation)
- **Epic 2:** 35-45h (RAG Pipeline)
- **Epic 3:** 60-80h (Production Readiness)

---

## Key Improvements vs. v3.0.0-MCP

- **Dual Judge:** Claude Code 2x → GPT-4o + Haiku (true IRR)
- **Evaluation/Reflexion:** Claude Code internal → Haiku API (consistency)
- **Golden Set:** 20 queries → 50-100 queries (statistical robustness)
- **Budget:** €0.06/mo → €5-10/mo (still 90-95% savings maintained)
- **Methodological Validity:** True independent Dual Judges, NFR007 added

---

## Contributors

- **Author:** ethr
- **AI Assistant:** Claude (Claude Code)
- **Architecture:** MCP-based Cognitive Memory System v3.1.0-Hybrid
