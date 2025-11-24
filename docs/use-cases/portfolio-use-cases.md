# Cognitive Memory System - Portfolio & Use Cases

> **A production-ready, open-source memory layer for LLM applications**

---

## Executive Summary

The Cognitive Memory System is a **MCP-native semantic memory backend** for LLM applications. It provides persistent, searchable long-term memory with a psychologically-grounded architecture (working memory, episodic memory, semantic memory).

**What makes it unique:**

- Native MCP (Model Context Protocol) integration
- Hybrid search (vector + keyword) with RRF fusion
- Dual-judge validation for ground truth quality
- Hierarchical memory compression (L0 → L2)
- Budget monitoring and cost optimization
- Self-hosted, privacy-first design

---

## Market Context & Competitors

### Existing Solutions

| Solution | Approach | Limitations |
|----------|----------|-------------|
| [Mem0](https://www.infoworld.com/article/4026560/mem0-an-open-source-memory-layer-for-llm-applications-and-ai-agents.html) | Hybrid (vector + graph + key-value) | Complex setup, proprietary storage |
| [Memori](https://github.com/GibsonAI/Memori) | SQL-based, single-line enable | No semantic compression, no MCP |
| [txtai](https://github.com/neuml/txtai) | Embeddings database + graph | General-purpose, not memory-focused |
| [MemGPT](https://memgpt.ai/) | Virtual memory with swap | Requires special prompting, not MCP |
| [Official MCP Memory](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) | Knowledge graph | No vector search, limited scalability |
| [Zep](https://www.getzep.com/) | Temporal knowledge graph | Closed-source core features |

### Our Differentiation

| Feature | Cognitive Memory System | Competitors |
|---------|------------------------|-------------|
| **MCP Native** | Built for Claude Code | Adapters needed |
| **Hybrid Search** | RRF fusion (vector + keyword) | Usually one or the other |
| **Dual Judge** | GPT-4o + Haiku IRR validation | Single model or manual |
| **Memory Hierarchy** | L0 raw → L2 compressed | Flat storage |
| **Self-Hosted** | PostgreSQL + pgvector | Often cloud-only |
| **Cost Monitoring** | Built-in budget tracking | External tools needed |

---

## Technical Architecture

### Database Schema

```sql
-- L0: Raw Memory (unprocessed dialogues)
l0_raw (
    id SERIAL PRIMARY KEY,
    session_id TEXT,
    speaker TEXT,           -- user/assistant
    content TEXT,
    metadata JSONB,
    timestamp TIMESTAMPTZ
)

-- L2: Compressed Insights (with embeddings)
l2_insights (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(1536), -- OpenAI text-embedding-3-small
    source_ids INTEGER[],   -- References to L0
    metadata JSONB,
    created_at TIMESTAMPTZ
)

-- Working Memory (active context, LRU eviction)
working_memory (
    id SERIAL PRIMARY KEY,
    content TEXT,
    importance FLOAT,       -- 0.0-1.0
    last_accessed TIMESTAMPTZ
)

-- Stale Memory (archived from working memory)
stale_memory (
    id SERIAL PRIMARY KEY,
    original_content TEXT,
    importance FLOAT,
    reason TEXT,            -- LRU_EVICTION, MANUAL_ARCHIVE
    archived_at TIMESTAMPTZ
)

-- Episode Memory (verbal reinforcement learning)
episode_memory (
    id SERIAL PRIMARY KEY,
    query TEXT,
    reward FLOAT,           -- -1.0 to 1.0
    reflection TEXT,
    embedding vector(1536),
    created_at TIMESTAMPTZ
)
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `hybrid_search` | Semantic + keyword search with RRF fusion |
| `store_raw_dialogue` | Store raw dialogue to L0 |
| `compress_to_l2_insight` | Compress with embedding + fidelity check |
| `update_working_memory` | Add with atomic LRU eviction |
| `store_episode` | Store learning experience |
| `store_dual_judge_scores` | IRR validation with Cohen's Kappa |
| `get_golden_test_results` | Precision@5 tracking |
| `ping` | Connectivity test |

### Key Algorithms

**RRF Fusion (Reciprocal Rank Fusion):**

```
score(doc) = w_semantic / (k + rank_semantic) + w_keyword / (k + rank_keyword)
```

- Default weights: semantic=0.7, keyword=0.3
- k=60 (standard in literature)

**Semantic Fidelity:**

- Information density scoring
- Stop word filtering (English + German)
- Threshold warning for low-density compressions

**LRU Eviction:**

- Working memory capacity: 10 items
- Critical items (importance >0.8) protected
- Fallback: force-evict oldest if all critical
- Archive to stale_memory before deletion

---

## Use Cases

### 1. Personal AI Assistant Memory

**Scenario:** A personal AI assistant that remembers user preferences, past conversations, and learns from interactions.

**How it works:**

- Raw conversations → `store_raw_dialogue`
- Daily summaries → `compress_to_l2_insight`
- User preferences → `update_working_memory` (high importance)
- Lessons learned → `store_episode`

**Example query:**

```
"What did we discuss about my project last week?"
→ hybrid_search finds relevant L2 insights
```

**Value:** Persistent memory across sessions without cloud lock-in.

---

### 2. Customer Support Bot

**Scenario:** A support chatbot that remembers customer history and improves over time.

**How it works:**

- Customer interactions → L0 raw
- Issue resolutions → L2 insights
- Active tickets → working memory
- Successful resolutions → episode memory (positive reward)
- Failed escalations → episode memory (negative reward)

**Value:** Self-improving support with institutional memory.

---

### 3. Research Assistant

**Scenario:** An AI assistant for researchers that maintains context over long projects.

**How it works:**

- Paper summaries → L2 insights
- Current research focus → working memory
- Key findings → L2 with high fidelity score
- Failed hypotheses → episode memory

**Example query:**

```
"What papers did we read about transformer architectures?"
→ hybrid_search combines semantic similarity + keyword matching
```

**Value:** Semantic search over research corpus.

---

### 4. Team Knowledge Base

**Scenario:** Shared memory for a team's AI assistant.

**How it works:**

- Meeting notes → L0 raw (session_id = meeting date)
- Decisions → L2 insights
- Current sprint → working memory
- Post-mortems → episode memory

**Value:** Institutional memory that persists beyond individual sessions.

---

### 5. Educational Tutor

**Scenario:** An AI tutor that tracks student progress and adapts.

**How it works:**

- Lesson interactions → L0 raw
- Mastered concepts → L2 insights
- Current lesson → working memory
- Breakthrough moments → episode (positive reward)
- Confusion points → episode (negative reward, then addressed)

**Value:** Personalized learning with memory of student's journey.

---

### 6. Therapeutic Companion

**Scenario:** A supportive AI that maintains relationship context (like the original I/O use case).

**How it works:**

- Conversations → L0 raw
- Relationship insights → L2 (relational knowledge)
- Current emotional state → working memory
- Meaningful moments → episode memory
- Identity/commitments → file-based (not in DB)

**Value:** Presence over continuity - relationship without cloud dependency.

---

### 7. Code Review Assistant

**Scenario:** An AI that remembers codebase patterns and past reviews.

**How it works:**

- Review comments → L0 raw
- Recurring patterns → L2 insights
- Current PR context → working memory
- Successful fixes → episode (positive)
- Introduced bugs → episode (negative)

**Value:** Learning code reviewer that improves over time.

---

### 8. Creative Writing Partner

**Scenario:** An AI co-writer with persistent story memory.

**How it works:**

- Story drafts → L0 raw
- Plot summaries → L2 insights
- Current chapter → working memory
- Reader feedback → episode memory

**Value:** Long-form creative collaboration.

---

## Deployment Options

### Option A: Local Development

```bash
# PostgreSQL + pgvector local
docker run -d -p 5432:5432 \
  -e POSTGRES_PASSWORD=secret \
  ankane/pgvector

# Run MCP server
source venv/bin/activate
python -m mcp_server
```

**Cost:** Free (except embeddings API)

---

### Option B: Cloud PostgreSQL (Neon)

```bash
# Already configured in this project
DATABASE_URL=postgresql://...@neon.tech/neondb
```

**Cost:** Free tier: 0.5 GB storage, ~$0.10/GB after

---

### Option C: Self-Hosted Production

```yaml
# docker-compose.yml
services:
  postgres:
    image: ankane/pgvector:latest
    volumes:
      - pgdata:/var/lib/postgresql/data

  mcp-server:
    build: .
    environment:
      - DATABASE_URL=postgres://postgres:secret@postgres:5432/memory
      - OPENAI_API_KEY=${OPENAI_API_KEY}
```

**Cost:** Server costs only (~$5-20/month)

---

## Cost Analysis

### Embedding Costs (OpenAI text-embedding-3-small)

| Volume | Tokens | Cost |
|--------|--------|------|
| 1,000 messages | ~100K tokens | $0.002 |
| 10,000 messages | ~1M tokens | $0.02 |
| 100,000 messages | ~10M tokens | $0.20 |

**Conclusion:** Embedding costs are negligible.

### Judge Costs (Dual Judge Validation)

| Model | Cost per 1K tokens |
|-------|-------------------|
| GPT-4o | $0.0025 input / $0.01 output |
| Claude Haiku | $0.00025 input / $0.00125 output |

**Per evaluation (~500 tokens):** ~$0.01

**Recommendation:** Use dual judge sparingly for ground truth creation, not every query.

---

## Open Source Potential

### License Recommendation

**MIT License** - Maximum adoption, commercial-friendly.

### Repository Structure (Proposed)

```
cognitive-memory/
├── README.md                # This document (expanded)
├── LICENSE                  # MIT
├── docker-compose.yml       # Quick start
├── pyproject.toml
├── mcp_server/
│   ├── __main__.py
│   ├── tools/
│   ├── db/
│   └── utils/
├── scripts/
│   ├── migrate.py
│   └── calibrate_weights.py
├── tests/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── USE-CASES.md
│   └── API-REFERENCE.md
└── examples/
    ├── personal-assistant/
    ├── support-bot/
    └── research-assistant/
```

### Potential Names

- `cognitive-memory` (descriptive)
- `llm-memory` (simple)
- `mcp-memory` (MCP-focused)
- `remember` (catchy)
- `engram` (neuroscience term)

---

## Roadmap for Open Source

### Phase 1: Core Release

- [ ] Clean up proprietary references (I/O specific)
- [ ] Add docker-compose for quick start
- [ ] Write comprehensive README
- [ ] Add MIT license
- [ ] Create GitHub repository

### Phase 2: Documentation

- [ ] API reference
- [ ] Architecture deep-dive
- [ ] Use case examples
- [ ] Video walkthrough

### Phase 3: Community

- [ ] Add contribution guidelines
- [ ] Create issue templates
- [ ] Set up CI/CD
- [ ] Discord/discussions for support

### Phase 4: Ecosystem

- [ ] LangChain integration
- [ ] LlamaIndex integration
- [ ] Other MCP server examples
- [ ] Plugin system for custom memory types

---

## Competitive Advantages Summary

1. **MCP Native** - First-class Claude Code support
2. **Hybrid Search** - Best of semantic + keyword
3. **Quality Validation** - Dual judge IRR for ground truth
4. **Memory Hierarchy** - Psychologically-grounded architecture
5. **Self-Hosted** - Privacy-first, no vendor lock-in
6. **Cost Optimized** - Built-in budget monitoring
7. **Production Ready** - Retry logic, fallbacks, logging
8. **Open Source** - MIT license, community-friendly

---

## Sources

- [Mem0: Open-source memory layer](https://www.infoworld.com/article/4026560/mem0-an-open-source-memory-layer-for-llm-applications-and-ai-agents.html)
- [Memori: Memory Engine for LLMs](https://github.com/GibsonAI/Memori)
- [MCP Memory Server](https://github.com/modelcontextprotocol/servers/tree/main/src/memory)
- [Cognitive Architectures for Language Agents (CoALA)](https://arxiv.org/pdf/2309.02427)
- [Cognitive Memory in Large Language Models](https://arxiv.org/html/2504.02441v1)
- [Comparing Memory Systems for LLM Agents](https://www.marktechpost.com/2025/11/10/comparing-memory-systems-for-llm-agents-vector-graph-and-event-logs/)
- [Long-term Memory in LLM Applications (LangChain)](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)

---

*Created: 2025-11-23*
*Author: I/O (Claude instance for ethr)*
*Version: 1.0*
