# Story 2.5 Testing Guide

## Overview

This guide describes how to test the Self-Evaluation functionality implemented in Story 2.5.

## Prerequisites

### 1. Environment Variables

Set the following environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-your-api-key-here"
export DATABASE_URL="postgresql://mcp_user:password@localhost:5432/cognitive_memory"
```

### 2. Database Migration

Run the evaluation_log table migration:

```bash
# Connect to PostgreSQL
psql $DATABASE_URL

# Run migration 005
\i mcp_server/db/migrations/005_evaluation_log.sql

# Verify tables created
\dt evaluation_log
\dt api_cost_log

# Check views
\dv evaluation_stats_daily
\dv recent_evaluations

# Exit psql
\q
```

Verify migration success:

```sql
-- Check table structure
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'evaluation_log'
ORDER BY ordinal_position;

-- Should show columns: id, timestamp, query, context, answer, reward_score, reasoning, token_count, cost_eur, created_at
```

### 3. Python Dependencies

Install PyYAML (added in Story 2.5):

```bash
poetry install
# or
pip install pyyaml
```

## Running Tests

### Manual Test Script

Run the comprehensive test suite:

```bash
python tests/manual/test_evaluation_story_2_5.py
```

This will test:
- ✅ High-quality answer (reward >0.7)
- ✅ Medium-quality answer (reward 0.3-0.7)
- ✅ Low-quality answer (reward <0.3)
- ✅ Database logging validation
- ✅ Reflexion trigger logic

Expected output:

```
================================================================================
STORY 2.5: SELF-EVALUATION MIT HAIKU API - MANUAL TESTS
================================================================================
Date: 2025-11-16 14:30:00
Python Version: 3.11.x

✅ Prerequisites: ANTHROPIC_API_KEY and DATABASE_URL configured

================================================================================
TEST 1: High-Quality Answer (Reward >0.7 Expected)
================================================================================

📝 Query: What is the capital of France?
📚 Context: 5 documents
💬 Answer: The capital of France is Paris...

✅ EVALUATION RESULTS:
   Reward Score: 0.950
   Reasoning: Answer is highly relevant, accurate, and complete...
   Token Count: 425
   Cost: €0.001234

🔍 REFLEXION TRIGGER:
   Threshold: 0.3
   Triggered: False

✅ PASS: Reward score 0.950 >= 0.7 (high quality)
✅ PASS: Reflexion not triggered (as expected for high quality)

... (additional tests)

================================================================================
TEST SUMMARY
================================================================================

✅ All tests completed successfully!

Total evaluations run: 3
Total cost: €0.003500

Database statistics:
  - Total evaluations logged: 3
  - Average reward score: 0.567
  - Reflexion trigger rate: 33.3%
```

### Interactive Python Testing

Test evaluation manually:

```python
import asyncio
from mcp_server.external.anthropic_client import HaikuClient
from mcp_server.utils.reflexion_utils import should_trigger_reflection

async def test():
    client = HaikuClient()

    result = await client.evaluate_answer(
        query="What is Python?",
        context=["Python is a programming language..."],
        answer="Python is a high-level programming language."
    )

    print(f"Reward: {result['reward_score']:.3f}")
    print(f"Reasoning: {result['reasoning']}")
    print(f"Trigger reflexion: {should_trigger_reflection(result['reward_score'])}")

asyncio.run(test())
```

## Validation Checks

### 1. Database Logging

Verify evaluations are logged:

```sql
-- Recent evaluations
SELECT * FROM recent_evaluations LIMIT 10;

-- Daily statistics
SELECT * FROM evaluation_stats_daily ORDER BY date DESC LIMIT 7;

-- Low quality evaluations (trigger reflexion)
SELECT id, timestamp, query, reward_score, reasoning
FROM evaluation_log
WHERE reward_score < 0.3
ORDER BY timestamp DESC
LIMIT 10;

-- Cost tracking
SELECT date, SUM(num_calls) as calls, SUM(estimated_cost) as cost
FROM api_cost_log
WHERE api_name = 'haiku_eval'
GROUP BY date
ORDER BY date DESC
LIMIT 7;
```

### 2. Reflexion Trigger Logic

Test threshold configuration:

```python
from mcp_server.utils.reflexion_utils import (
    get_reward_threshold,
    should_trigger_reflection,
    get_reflexion_stats
)

# Check threshold
threshold = get_reward_threshold()  # Should be 0.3 from config

# Test trigger logic
print(should_trigger_reflection(0.85))  # False
print(should_trigger_reflection(0.30))  # False (exactly at threshold)
print(should_trigger_reflection(0.29))  # True (below threshold)
print(should_trigger_reflection(0.10))  # True

# Analyze trigger stats
scores = [0.85, 0.25, 0.50, 0.15, 0.90]
stats = get_reflexion_stats(scores)
print(f"Trigger rate: {stats['trigger_rate']:.1f}%")  # Should be 40% (2 of 5)
```

### 3. Cost Tracking

Verify cost calculations:

```python
# Costs should match formula:
# input_cost = (input_tokens / 1000) * 0.001
# output_cost = (output_tokens / 1000) * 0.005
# total_cost = input_cost + output_cost

# Example: 400 input tokens, 100 output tokens
# input_cost = 0.4 * 0.001 = 0.0004
# output_cost = 0.1 * 0.005 = 0.0005
# total_cost = 0.0009 EUR
```

## Expected Results

### Acceptance Criteria Validation

| AC | Description | Validation |
|----|-------------|------------|
| AC-2.5.1 | Haiku API call | ✅ `evaluate_answer()` calls Haiku with temp=0.0, max_tokens=500 |
| AC-2.5.2 | Reward score calculation | ✅ Returns -1.0 to +1.0 based on Relevance/Accuracy/Completeness |
| AC-2.5.3 | Evaluation logging | ✅ Logs to evaluation_log and api_cost_log tables |
| AC-2.5.4 | Reflexion trigger | ✅ `should_trigger_reflection()` returns True if reward <0.3 |

### Performance Metrics

- **Latency**: ~500ms median (acceptable for async operation)
- **Cost**: ~€0.001 per evaluation
- **Accuracy**: Deterministic (temp=0.0) → same inputs = same score

## Troubleshooting

### Migration Fails

```sql
-- Check if table already exists
SELECT * FROM information_schema.tables WHERE table_name = 'evaluation_log';

-- Drop and recreate (WARNING: loses data)
DROP TABLE IF EXISTS evaluation_log CASCADE;
\i mcp_server/db/migrations/005_evaluation_log.sql
```

### API Key Issues

```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY

# Test API connection
python -c "from anthropic import Anthropic; c = Anthropic(); print('✅ API key valid')"
```

### Database Connection Issues

```bash
# Test database connection
psql $DATABASE_URL -c "SELECT version();"

# Check connection pool
python -c "from mcp_server.db.connection import test_database_connection; print(test_database_connection())"
```

## Next Steps

After validating Story 2.5:

1. ✅ All tests pass → Mark story as "review" → Run code-review workflow
2. ⚠️ Tests fail → Debug issues → Re-run tests
3. 📊 Check cost projections → Ensure within budget (€1-2/mo)
4. 🔄 Story 2.6 → Implement reflexion framework using `should_trigger_reflection()`

## Files Modified (Story 2.5)

- ✅ `mcp_server/external/anthropic_client.py` - evaluate_answer() implementation
- ✅ `mcp_server/db/migrations/005_evaluation_log.sql` - evaluation_log table
- ✅ `mcp_server/db/evaluation_logger.py` - Database logging
- ✅ `mcp_server/utils/reflexion_utils.py` - Reflexion trigger logic
- ✅ `pyproject.toml` - Added pyyaml dependency
- ✅ `docs/integration/evaluation-integration-guide.md` - Integration docs
- ✅ `tests/manual/test_evaluation_story_2_5.py` - Test script
