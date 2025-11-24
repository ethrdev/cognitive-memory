# Evaluation Integration Guide (Story 2.5)

## Overview

This document describes how to integrate the Self-Evaluation functionality into the Claude Code RAG pipeline.

**Story**: 2.5 - Self-Evaluation mit Haiku API
**Date**: 2025-11-16
**Status**: Implementation Complete

## Integration Point in RAG Pipeline

The evaluation should occur **after CoT generation** and **before Working Memory update**:

```
1. User Query (in Claude Code)
   ↓
2. Query Expansion → 3 Varianten (Story 2.2)
   ↓
3. Hybrid Search → Top-5 L2 Insights (Story 1.6)
   ↓
4. Episode Memory Load → ähnliche vergangene Queries (Story 1.8)
   ↓
5. CoT Generation → Thought + Reasoning + Answer + Confidence (Story 2.3)
   ↓
6. **Self-Evaluation (Story 2.5) ← INTEGRATION POINT**
   - Input: Query + Top-5 Context + CoT Answer
   - Output: Reward Score (-1.0 bis +1.0) + Reasoning
   ↓
7. Conditional Reflexion (Story 2.6, falls Reward <0.3)
   ↓
8. Working Memory Update (Story 1.7)
   ↓
9. User Response: Answer + Confidence + Sources (+ optional Lesson Learned)
```

## Call Pattern

### Option 1: Direct Python Import (Recommended for MCP Server)

```python
from mcp_server.external.anthropic_client import HaikuClient
from mcp_server.utils.reflexion_utils import should_trigger_reflection

# Initialize client (once per session)
client = HaikuClient()  # Loads from ANTHROPIC_API_KEY env var

# After CoT generation...
query = "Was denke ich über Bewusstsein?"
context = [
    "L2 Insight 1: Bewusstsein als emergentes Phänomen...",
    "L2 Insight 2: Philosophische Perspektiven...",
    "L2 Insight 3: Neurowissenschaftliche Theorien...",
    "L2 Insight 4: Selbstreflexion und Meta-Kognition...",
    "L2 Insight 5: Phenomenale Erfahrung..."
]
answer = "Basierend auf den Insights... [CoT-generierte Antwort]"

# Evaluate answer
evaluation_result = await client.evaluate_answer(
    query=query,
    context=context,
    answer=answer
)

# Extract results
reward_score = evaluation_result["reward_score"]      # float: -1.0 to +1.0
reasoning = evaluation_result["reasoning"]            # str: Haiku's explanation
token_count = evaluation_result["token_count"]        # int: total tokens
cost_eur = evaluation_result["cost_eur"]              # float: cost in EUR

# Check if reflexion should be triggered
if should_trigger_reflection(reward_score):
    # Story 2.6: Call generate_reflection()
    print(f"⚠️ Low quality answer (reward={reward_score:.3f}). Triggering reflexion...")
    # reflection_result = await client.generate_reflection(...)
else:
    print(f"✅ Answer quality acceptable (reward={reward_score:.3f})")
```

### Option 2: MCP Tool Call (Future Enhancement)

If we expose evaluation as an MCP tool:

```python
# MCP Tool: evaluate_answer
{
    "name": "evaluate_answer",
    "description": "Evaluate answer quality using Haiku API",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "context": {"type": "array", "items": {"type": "string"}},
            "answer": {"type": "string"}
        },
        "required": ["query", "context", "answer"]
    }
}
```

## Input Requirements

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `query` | str | Original user query | "Was denke ich über Bewusstsein?" |
| `context` | List[str] | Top-5 L2 Insights from Hybrid Search | ["Context 1...", "Context 2...", ...] |
| `answer` | str | CoT-generated answer | "Basierend auf den Insights..." |

## Output Structure

```python
{
    "reward_score": 0.85,        # float: -1.0 to +1.0
    "reasoning": "Answer is relevant, accurate, and complete...",  # str
    "token_count": 450,          # int: input + output tokens
    "cost_eur": 0.00125         # float: estimated cost
}
```

### Reward Score Interpretation

| Score Range | Quality | Reflexion Trigger | Interpretation |
|-------------|---------|-------------------|----------------|
| +0.7 to +1.0 | Excellent | No | Perfect answer, highly relevant and accurate |
| +0.3 to +0.7 | Good | No | Solid answer, minor gaps |
| 0.0 to +0.3 | Acceptable | **At threshold** | Minimal acceptable quality |
| **<0.3** | Poor | **Yes** | **Triggers reflexion (Story 2.6)** |
| -0.3 to 0.0 | Weak | Yes | Relevance or accuracy issues |
| -0.7 to -0.3 | Bad | Yes | Significant problems |
| -1.0 to -0.7 | Very Bad | Yes | Major errors, hallucinations |

## Configuration

Evaluation parameters are defined in `config/config.yaml`:

```yaml
base:
  memory:
    evaluation:
      model: "claude-3-5-haiku-20241022"
      temperature: 0.0  # Deterministic for consistent scores
      max_tokens: 500
      reward_threshold: 0.3  # Trigger reflexion if reward < 0.3
```

## Database Logging

Evaluation results are automatically logged to PostgreSQL:

1. **evaluation_log**: Detailed results (query, answer, reward, reasoning)
2. **api_cost_log**: Cost tracking (tokens, cost in EUR)

Query recent evaluations:

```sql
-- Last 10 evaluations
SELECT * FROM recent_evaluations LIMIT 10;

-- Daily statistics
SELECT * FROM evaluation_stats_daily ORDER BY date DESC LIMIT 7;

-- Low quality evaluations (triggered reflexion)
SELECT * FROM evaluation_log WHERE reward_score < 0.3 ORDER BY timestamp DESC LIMIT 10;
```

## Performance Considerations

- **Latency**: ~500ms median (p95: ~800ms)
- **Cost**: ~€0.001 per evaluation
- **Not in critical path**: Evaluation can run async (doesn't block user response)
- **Monthly budget**: ~€1-2 for 1000 evaluations

## Error Handling

The `evaluate_answer()` method includes:

- **Retry logic**: 4 retries with exponential backoff [1s, 2s, 4s, 8s]
- **Jitter**: ±20% randomization to prevent Thundering Herd
- **Fallback**: JSON parsing errors result in neutral score (0.0) with explanation
- **Logging**: All failures logged to `api_retry_log` table

## Testing

### Manual Test Example

```python
import asyncio
from mcp_server.external.anthropic_client import HaikuClient

async def test_evaluation():
    client = HaikuClient()

    # High-quality answer test
    result = await client.evaluate_answer(
        query="What is the capital of France?",
        context=["France is a country in Europe with Paris as its capital."],
        answer="The capital of France is Paris."
    )

    print(f"Reward: {result['reward_score']:.3f}")
    print(f"Reasoning: {result['reasoning']}")
    print(f"Cost: €{result['cost_eur']:.6f}")

    # Expected: reward > 0.7 (high quality)

asyncio.run(test_evaluation())
```

## Next Steps (Story 2.6)

When Story 2.6 (Reflexion Framework) is implemented:

1. Check `should_trigger_reflection(reward_score)` after evaluation
2. If `True`, call `client.generate_reflection(query, answer, reasoning)`
3. Store lesson learned in Episode Memory
4. Include reflection in user response (optional)

## Files Created (Story 2.5)

- `mcp_server/external/anthropic_client.py` - evaluate_answer() implementation (lines 76-225)
- `mcp_server/db/migrations/005_evaluation_log.sql` - evaluation_log table
- `mcp_server/db/evaluation_logger.py` - Database logging functions
- `mcp_server/utils/reflexion_utils.py` - Reflexion trigger logic
- `docs/integration/evaluation-integration-guide.md` - This document

## References

- **Architecture**: `bmad-docs/architecture.md` (ADR-002, lines 769-784)
- **Tech Spec**: `bmad-docs/tech-spec-epic-2.md` (Story 2.5, lines 411-416)
- **Epic Breakdown**: `bmad-docs/epics.md` (Story 2.5, lines 671-703)
- **Story File**: `bmad-docs/stories/2-5-self-evaluation-mit-haiku-api.md`
