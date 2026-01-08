# Story 2.7: Local Testing Setup Guide

**Story**: 2.7 - End-to-End RAG Pipeline Testing
**Environment**: Local (Mac/PC with Internet access)
**Database**: Neon PostgreSQL (eu-central-1)
**Prerequisites**: Neon project created, API keys obtained

---

## Overview

This guide helps you set up and execute Story 2.7 testing in your **local environment**. The container environment lacks internet access, so all testing must be done locally where Neon and API services are accessible.

**Estimated Time:** 45-90 minutes (first time setup)

---

## Prerequisites ✅

Before starting, ensure you have:

1. **Neon Project Created**
   - ✅ Project: cognitive-memory
   - ✅ Region: eu-central-1
   - ✅ Connection String: `postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler...`

2. **API Keys Obtained**
   - ✅ OpenAI API Key (for embeddings)
   - ✅ Anthropic API Key (for Haiku evaluation/reflexion)

3. **Local Environment**
   - Git repository cloned to local machine
   - Python 3.11+ installed
   - psql client installed (PostgreSQL client tools)
   - Claude Code installed (for MCP client testing)

---

## Step 1: Update Local Configuration (5 minutes)

### 1.1: Verify .env.development

The `.env.development` file already exists with Neon connection and API keys (created earlier, gitignored).

**Verify it contains:**

```bash
# Location: /home/user/i-o/.env.development (or your local repo path)

DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require

OPENAI_API_KEY=sk-proj-YOUR_OPENAI_API_KEY

ANTHROPIC_API_KEY=sk-ant-api03-YOUR_ANTHROPIC_API_KEY
```

**If keys are missing or different**, update them with your real values.

### 1.2: Update .mcp.json with Real API Keys

The `.mcp.json` in Git has **placeholders**. You must replace them locally:

```bash
# Open .mcp.json in your editor
# Find this line:
"DATABASE_URL='postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require' ANTHROPIC_API_KEY='sk-ant-api03-YOUR_ANTHROPIC_API_KEY' OPENAI_API_KEY='sk-proj-YOUR_OPENAI_API_KEY' ENVIRONMENT='production' LOG_LEVEL='INFO' /home/ethr/.cache/pypoetry/virtualenvs/cognitive-memory-system-HON7j2ab-py3.13/bin/python -m mcp_server"

# Replace with:
"DATABASE_URL='postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require' ANTHROPIC_API_KEY='sk-ant-api03-YOUR_ANTHROPIC_API_KEY' OPENAI_API_KEY='sk-proj-YOUR_OPENAI_API_KEY' ENVIRONMENT='production' LOG_LEVEL='INFO' python -m mcp_server"
```

**Important:** Also update the Python path to your local virtualenv path (not the container path `/home/ethr/...`).

**Find your local virtualenv:**
```bash
poetry env info --path
# Copy the output path and append /bin/python
# Example: /Users/yourname/.cache/pypoetry/virtualenvs/cognitive-memory-system-abc123-py3.11/bin/python
```

---

## Step 2: Test Neon Connection (5 minutes)

### 2.1: Test with psql

```bash
# Test basic connection
psql 'postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require' -c "SELECT version();"

# Expected output:
# PostgreSQL 17.x on x86_64-pc-linux-gnu, compiled by gcc...
```

**If connection fails:**
- Check internet connection
- Verify Neon project is active (check Neon dashboard)
- Verify password hasn't changed

### 2.2: Test with Python Script

```bash
# Run the test script
python test_neon_connection.py

# Expected output:
# 🔗 Connecting to Neon database...
# ✅ Test 1: PostgreSQL Version
#    Version: PostgreSQL 17.x...
# ✅ Test 2: Enable pgvector Extension
#    pgvector extension enabled
# ✅ Test 3: Verify pgvector Extension
#    pgvector extension active: (...)
# ✅ Test 4: Check Existing Tables
#    No tables found (schema migration needed)
# 🎉 Neon connection successful! Database is ready for schema migration.
```

**Success Criteria:** All 4 tests pass, pgvector extension is enabled.

---

## Step 3: Run Schema Migrations (10 minutes)

### 3.1: Migration 001 - Initial Schema

```bash
psql 'postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require' \
  -f mcp_server/db/migrations/001_initial_schema.sql

# Expected output:
# CREATE EXTENSION
# CREATE TABLE (x6 - l0_raw, l2_insights, working_memory, episode_memory, stale_memory, ground_truth)
# CREATE INDEX (x3 - idx_l0_session, idx_l2_fts, idx_wm_lru)
```

### 3.2: Migration 002 - Session ID Type Fix

```bash
psql 'postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require' \
  -f mcp_server/db/migrations/002_fix_session_id_type.sql
```

### 3.3: Migration 002-dual-judge (Alternative naming)

**Note:** There are two "002" migrations (naming issue from development). Run both:

```bash
psql 'postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require' \
  -f mcp_server/db/migrations/002_dual_judge_schema.sql
```

### 3.4: Migration 003 - Validation Results

```bash
psql 'postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require' \
  -f mcp_server/db/migrations/003_validation_results.sql
```

### 3.5: Migration 004 - API Tracking Tables

```bash
psql 'postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require' \
  -f mcp_server/db/migrations/004_api_tracking_tables.sql
```

### 3.6: Migration 005 - Evaluation Log

```bash
psql 'postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require' \
  -f mcp_server/db/migrations/005_evaluation_log.sql
```

### 3.7: Verify All Tables Exist

```bash
psql 'postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require' \
  -c "\dt"

# Expected tables (at least):
# l0_raw
# l2_insights
# working_memory
# episode_memory
# stale_memory
# ground_truth
# api_cost_log
# api_retry_log
# evaluation_log
# dual_judge_scores (if migration 002-dual-judge ran)
# validation_results (if migration 003 ran)
```

**Success Criteria:** All core tables exist (l0_raw through ground_truth minimum).

---

## Step 4: Populate Test L2 Insights Data (15-30 minutes)

Story 2.7 requires **minimum 10-20 L2 insights** for test scenarios (High/Medium/Low Confidence).

### 4.1: Create Test Data Script

Create `populate_test_data.py`:

```python
#!/usr/bin/env python3
"""Populate Neon database with test L2 insights for Story 2.7."""

import os
from openai import OpenAI
import psycopg2
from psycopg2.extras import execute_batch

# Load environment
DATABASE_URL = "postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require"
OPENAI_API_KEY = "sk-proj-YOUR_OPENAI_API_KEY"

# Test insights content (philosophische Themen für High Confidence Tests)
test_insights = [
    "Bewusstsein ist eine emergente Eigenschaft komplexer neuronaler Netzwerke. Es entsteht aus der Interaktion von Milliarden Neuronen.",
    "Freier Wille könnte eine Illusion sein, die unser Gehirn erzeugt, um uns das Gefühl von Kontrolle zu geben.",
    "Künstliche Intelligenz ist aktuell nicht bewusst, könnte aber in Zukunft phänomenales Bewusstsein entwickeln.",
    "Ethik sollte auf Konsequenzen basieren (Utilitarismus) und nicht auf starren Regeln.",
    "Menschliches Denken ist stark durch kognitive Biases verzerrt - Confirmation Bias, Dunning-Kruger, etc.",
    "Sprache formt unser Denken (Sapir-Whorf-Hypothese). Verschiedene Sprachen ermöglichen verschiedene Denkweisen.",
    "Zeit ist möglicherweise keine fundamentale Eigenschaft der Realität, sondern eine Konstruktion unseres Bewusstseins.",
    "Realität könnte eine Simulation sein (Simulation Hypothesis). Wir können es nicht definitiv widerlegen.",
    "Moral ist kulturell relativ. Was in einer Kultur gut ist, kann in einer anderen schlecht sein.",
    "Wissen entsteht durch Empirie (Erfahrung) und Rationalismus (Logik). Beides ist notwendig.",

    # Zusätzliche Insights für Medium Confidence Tests (verwandte aber nicht identische Themen)
    "Neuronale Netze in AI sind inspiriert von biologischen Neuronen, aber fundamental verschieden.",
    "Entscheidungen werden oft emotional getroffen und nachträglich rationalisiert.",
    "Philosophische Zombies (P-Zombies) sind ein Gedankenexperiment über Bewusstsein ohne Qualia.",
    "Determinismus impliziert, dass alle Ereignisse durch vorherige Ursachen bestimmt sind.",
    "Wahrnehmung ist konstruktiv - unser Gehirn konstruiert Realität aus sensorischen Inputs.",

    # Low Confidence Test Insights (unrelated topics)
    "Quantencomputer nutzen Superposition und Verschränkung für parallele Berechnungen.",
    "Klimawandel ist primär durch menschliche CO2-Emissionen verursacht.",
    "Evolution durch natürliche Selektion erklärt die Diversität des Lebens.",
    "Dunkle Materie und Dunkle Energie machen 95% des Universums aus.",
    "Demokratie ist die am wenigsten schlechte Regierungsform (Churchill).",
]

def get_embedding(client, text):
    """Get OpenAI embedding for text."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float"
    )
    return response.data[0].embedding

def main():
    print("🚀 Populating Neon database with test L2 insights...")

    # Initialize OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Connect to Neon
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Prepare data
    insights_data = []
    for idx, content in enumerate(test_insights, start=1):
        print(f"📝 Processing insight {idx}/{len(test_insights)}: {content[:50]}...")

        # Get embedding
        embedding = get_embedding(client, content)

        # Source IDs (fake - just for testing)
        source_ids = [idx]

        insights_data.append((content, embedding, source_ids))

    # Insert into database
    print(f"\n💾 Inserting {len(insights_data)} insights into Neon...")
    execute_batch(
        cursor,
        """
        INSERT INTO l2_insights (content, embedding, source_ids)
        VALUES (%s, %s, %s)
        """,
        insights_data
    )

    conn.commit()

    # Verify
    cursor.execute("SELECT COUNT(*) FROM l2_insights;")
    count = cursor.fetchone()[0]
    print(f"✅ Successfully inserted {count} L2 insights into Neon!")

    # Show sample
    cursor.execute("SELECT id, content FROM l2_insights LIMIT 3;")
    print("\n📋 Sample insights:")
    for row in cursor.fetchall():
        print(f"  ID {row[0]}: {row[1][:80]}...")

    cursor.close()
    conn.close()

    print("\n🎉 Test data population complete!")

if __name__ == "__main__":
    main()
```

### 4.2: Run Test Data Population

```bash
# Install openai if needed
pip install openai

# Run script
python populate_test_data.py

# Expected output:
# 🚀 Populating Neon database with test L2 insights...
# 📝 Processing insight 1/20: Bewusstsein ist eine emergente...
# ...
# 💾 Inserting 20 insights into Neon...
# ✅ Successfully inserted 20 L2 insights into Neon!
# 🎉 Test data population complete!
```

**Success Criteria:** At least 20 L2 insights inserted, embeddings generated successfully.

---

## Step 5: Start MCP Server (5 minutes)

### 5.1: Verify Python Environment

```bash
# Ensure you're in the project directory
cd /path/to/your/i-o

# Activate virtualenv (if using poetry)
poetry shell

# Or use poetry run
poetry run python -m mcp_server
```

### 5.2: Expected MCP Server Output

```json
{"timestamp": "2025-11-16T...", "level": "INFO", "message": "Starting Cognitive Memory MCP Server v3.1.0-Hybrid"}
{"timestamp": "2025-11-16T...", "level": "INFO", "message": "Registered 7 tools and 5 resources"}
{"timestamp": "2025-11-16T...", "level": "INFO", "message": "Database connected: PostgreSQL 17.x..."}
{"timestamp": "2025-11-16T...", "level": "INFO", "message": "MCP Server initialized, starting stdio transport"}
```

**If server fails to start:**
- Check DATABASE_URL in environment
- Check API keys are set
- Check database is accessible
- Review error logs

**Success Criteria:** Server starts, registers 7 tools + 5 resources, database connection successful.

---

## Step 6: Configure Claude Code MCP Client (10 minutes)

### 6.1: Locate Claude Code MCP Settings

**On Mac:**
```bash
# MCP settings location
~/.config/claude-code/mcp-settings.json

# Or check project root for .mcp.json
```

### 6.2: Verify .mcp.json Configuration

Your `.mcp.json` should point to your local Python:

```json
{
  "mcpServers": {
    "cognitive-memory": {
      "type": "stdio",
      "command": "/bin/bash",
      "args": [
        "-c",
        "DATABASE_URL='postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require' ANTHROPIC_API_KEY='sk-ant-api03-YOUR_ANTHROPIC_API_KEY...' OPENAI_API_KEY='sk-proj-YOUR_OPENAI_API_KEY...' ENVIRONMENT='production' LOG_LEVEL='INFO' /YOUR/LOCAL/PATH/.cache/pypoetry/virtualenvs/cognitive-memory-system-abc123-py3.11/bin/python -m mcp_server"
      ]
    }
  }
}
```

**Replace:** `/YOUR/LOCAL/PATH/` with your actual home directory path.

### 6.3: Restart Claude Code

After updating `.mcp.json`:
1. Quit Claude Code completely
2. Restart Claude Code
3. Check MCP connection status in settings

**Success Criteria:** Claude Code shows "cognitive-memory" server as connected, 7 tools + 5 resources available.

---

## Step 7: Execute Story 2.7 Testing (30-60 minutes)

Now you can execute the actual Story 2.7 test tasks in Claude Code!

### Task 2: High Confidence Query Test

**In Claude Code, send this query:**

```
Was denke ich über Bewusstsein?
```

**Expected behavior:**
1. Query Expansion generates 4 variants
2. OpenAI Embeddings API called (4 embeddings)
3. Hybrid Search returns Top-5 docs (should match "Bewusstsein ist eine emergente..." with high score >0.85)
4. Episode Memory checked (likely empty on first run)
5. CoT Generation creates Thought + Reasoning + Answer + Confidence >0.8
6. Haiku Evaluation returns Reward >0.5 (good answer)
7. **NO Reflexion triggered** (Reward >0.3)
8. Working Memory updated
9. User sees Answer + Confidence + Sources

**Record:**
- End-to-End Latency (should be <5s for p95 target)
- Retrieval Score (should be >0.85 for Top-1 doc)
- Confidence Score (should be >0.8)

### Task 3: Low Confidence Query Test (Reflexion Trigger)

**In Claude Code, send this query:**

```
Was ist die Hauptstadt von Schweden?
```

**Expected behavior:**
1-6. Same as High Confidence test
7. **Reflexion TRIGGERED** (Reward <0.3 because query is unrelated to cognitive memory)
8. Haiku generates_reflection() called → Problem + Lesson verbalized
9. Episode Memory stored via store_episode tool
10. Working Memory updated
11. User sees Answer + Low Confidence + Sources

**Verify Reflexion Storage:**

```bash
# Check episode_memory table
psql 'postgresql://neondb_owner:YOUR_PASSWORD@...' \
  -c "SELECT query, reward, reflection FROM episode_memory ORDER BY created_at DESC LIMIT 1;"

# Expected: Query about Sweden, Reward <0.3, Reflection with Problem/Lesson format
```

### Task 4: Medium Confidence Query Test

**In Claude Code, send this query:**

```
Was denke ich über neuronale Netze?
```

**Expected behavior:**
- Top-1 Score: 0.7-0.85 (partial match to AI insights)
- Confidence: 0.5-0.8
- Reward: 0.3-0.7
- **NO Reflexion trigger**

### Task 5: Episode Memory Retrieval Test

**In Claude Code, send a similar query to the Low Confidence test:**

```
Erkläre mir Schweden.
```

**Expected behavior:**
- Episode Memory resource returns similar episode (Similarity >0.70)
- CoT Reasoning integrates Lesson Learned: "Past experience suggests..."
- User sees transparency about past mistake

### Task 6: Performance Benchmarking

Run 10 queries (mix of High/Medium/Low Confidence) and record latencies:

**Queries:**
1. "Was denke ich über Bewusstsein?" (High)
2. "Was denke ich über freien Willen?" (High)
3. "Was denke ich über künstliche Intelligenz?" (High)
4. "Was denke ich über Ethik?" (High)
5. "Was denke ich über neuronale Netze?" (Medium)
6. "Was denke ich über Entscheidungen?" (Medium)
7. "Was denke ich über Wahrnehmung?" (Medium)
8. "Was denke ich über Demokratie?" (Medium)
9. "Was ist Quantencomputing?" (Low)
10. "Erkläre Klimawandel." (Low)

**Calculate:**
- p50 (Median latency) - expected ~3s
- p95 (95th percentile) - **MUST be <5s per NFR001**

**If p95 >5s:**
- Check Neon response time (network latency EU-Central to your location)
- Check OpenAI API latency
- Check Haiku API latency
- Consider optimization (Story 3.5)

### Task 7: Documentation

Create test results report (can be informal notes):

```markdown
# Story 2.7 Test Results

**Date:** 2025-11-16
**Environment:** Local (Mac/PC) + Neon (eu-central-1)

## High Confidence Test
- Query: "Was denke ich über Bewusstsein?"
- Top-1 Score: 0.92
- Confidence: 0.88
- Latency: 3.2s
- Reflexion: No (Reward 0.65)
- Result: ✅ PASS

## Low Confidence Test
- Query: "Was ist die Hauptstadt von Schweden?"
- Top-1 Score: 0.42
- Confidence: 0.23
- Latency: 4.8s
- Reflexion: Yes (Reward 0.18)
- Episode stored: Yes
- Result: ✅ PASS

## Medium Confidence Test
- Query: "Was denke ich über neuronale Netze?"
- Top-1 Score: 0.78
- Confidence: 0.65
- Latency: 3.5s
- Reflexion: No (Reward 0.48)
- Result: ✅ PASS

## Episode Memory Test
- Similar query to Low Confidence
- Episode retrieved: Yes (Similarity 0.85)
- Lesson integrated: Yes
- Result: ✅ PASS

## Performance Benchmarking (10 queries)
- p50: 3.4s
- p95: 4.7s
- Result: ✅ PASS (p95 <5s per NFR001)

## Overall Result
✅ All acceptance criteria met
- AC-2.7.1: 9-step pipeline executes correctly
- AC-2.7.2: Performance <5s p95
- AC-2.7.3: All 3 scenarios tested successfully
- AC-2.7.4: Pipeline logging verified in Neon
```

---

## Step 8: Verify Logging (5 minutes)

### 8.1: Check API Cost Tracking

```bash
psql 'postgresql://neondb_owner:YOUR_PASSWORD@...' \
  -c "SELECT api_name, COUNT(*), SUM(estimated_cost) FROM api_cost_log GROUP BY api_name;"

# Expected:
# api_name          | count | sum
# openai_embedding  |   40  | 0.0032  (10 queries × 4 embeddings each)
# haiku_eval        |   10  | 0.010   (10 evaluations)
# haiku_reflexion   |    2  | 0.003   (2 low confidence queries)
```

### 8.2: Check Episode Memory Storage

```bash
psql 'postgresql://neondb_owner:YOUR_PASSWORD@...' \
  -c "SELECT COUNT(*) FROM episode_memory;"

# Expected: 2 episodes (from Low Confidence tests)
```

**Success Criteria:** All API calls logged, costs tracked, episode memory populated.

---

## Troubleshooting

### Issue: Neon Connection Timeout

**Symptoms:** `psql: connection timeout` or `could not connect to server`

**Solutions:**
1. Check internet connection
2. Verify Neon project is active (Neon dashboard)
3. Check firewall settings (allow outbound HTTPS/PostgreSQL)
4. Try non-pooled connection (remove `-pooler` from hostname)

### Issue: pgvector Extension Missing

**Symptoms:** `ERROR: type "vector" does not exist`

**Solution:**
```bash
psql 'postgresql://...' -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Issue: MCP Server Won't Start

**Symptoms:** `ModuleNotFoundError` or `ImportError`

**Solutions:**
1. Verify virtualenv is activated
2. Run `poetry install` to install dependencies
3. Check Python version (must be 3.11+)
4. Check DATABASE_URL environment variable is set

### Issue: Claude Code Can't Connect to MCP Server

**Symptoms:** "MCP server disconnected" or "cognitive-memory not available"

**Solutions:**
1. Check `.mcp.json` Python path is correct (local path, not container path)
2. Restart Claude Code
3. Check MCP server logs for errors
4. Verify API keys in `.mcp.json` are correct

### Issue: High Latency (p95 >5s)

**Symptoms:** Queries take >5 seconds consistently

**Solutions:**
1. Check Neon region (EU-Central may be slow from US/Asia)
2. Check OpenAI API rate limits (429 errors)
3. Check Haiku API rate limits
4. Consider using non-pooled Neon connection for lower latency
5. Profile individual pipeline steps (add timing logs)

---

## Success Criteria Checklist

Before marking Story 2.7 as complete, verify:

- [ ] Neon database connected successfully
- [ ] pgvector extension enabled
- [ ] All 6 schema migrations executed
- [ ] 20+ L2 insights populated
- [ ] MCP Server starts and registers 7 tools + 5 resources
- [ ] Claude Code connects to MCP server
- [ ] High Confidence test passes (Top-1 Score >0.85, NO reflexion)
- [ ] Low Confidence test passes (Reflexion triggered, Episode stored)
- [ ] Medium Confidence test passes (Score 0.7-0.85, NO reflexion)
- [ ] Episode Memory retrieval works (Similar query retrieves lesson)
- [ ] Performance p95 <5s (NFR001 met)
- [ ] API costs tracked in database
- [ ] Episode memory populated
- [ ] All 9 pipeline steps execute correctly

**If all checkboxes are ticked:** Story 2.7 is COMPLETE! Mark as "done" in sprint-status.yaml.

---

## Next Steps After Story 2.7

Once Story 2.7 is complete:

1. **Story 2.8:** Hybrid Weight Calibration via Grid Search
   - Use same test infrastructure
   - Grid search semantic/keyword weights (0.5-0.9 for semantic)
   - Find optimal weights for Precision@5

2. **Story 2.9:** Precision@5 Validation on Ground Truth Set
   - Use ground truth queries from Story 1.10
   - Validate Precision@5 ≥0.75 (Full Success criterion)

3. **Epic 3:** Production Readiness
   - Performance optimization (if p95 not meeting targets)
   - Golden Test Set automation
   - IVFFlat index building (once >100 vectors)

---

**Good luck with Story 2.7 testing!** 🚀

**Questions or issues?** Check the troubleshooting section above or refer to:
- `bmad-docs/testing/story-2-7-infrastructure-blocker.md` (infrastructure details)
- `docs/mcp-configuration.md` (MCP client setup)
- `docs/reflexion-integration-guide.md` (reflexion workflow)
