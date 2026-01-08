# Overview

Dieses Dokument bietet die vollständige Epic- und Story-Dekomposition für das **Cognitive Memory System v3.1.0-Hybrid**, basierend auf dem [PRD](./PRD.md). Das System ist ein MCP-basiertes Gedächtnissystem, das Claude Code mit persistentem, kontextreichem Retrieval ausstattet.

**Architektur-Modus:** MCP Server + Claude Code Integration

- **Bulk-Operationen:** Generation, CoT, Planning (€0/mo, intern in Claude Code)
- **Kritische Evaluationen:** Dual Judge, Reflexion (€5-10/mo, externe APIs)
- **Budget-Ziel:** 90-95% Kostenreduktion vs. v2.4.1

**Timeline:** 133-175 Stunden (2.5-3.5 Monate bei 20h/Woche)

## Epic Summary

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
