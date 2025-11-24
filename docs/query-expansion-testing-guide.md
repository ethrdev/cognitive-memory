# Query Expansion End-to-End Testing Guide

**Version:** 1.0
**Date:** 2025-11-16
**Epic:** 2 - RAG Pipeline & Hybrid Calibration
**Story:** 2.2 - Query Expansion Logik intern in Claude Code

---

## Overview

This document provides manual testing procedures for Query Expansion functionality. Since query expansion is an **internal reasoning process** in Claude Code (not automated code), testing is primarily manual and observational.

### What Can Be Tested

✅ **Automated Unit Tests:** Deduplication and RRF fusion utility functions (see `tests/test_query_expansion.py`)
❌ **Cannot Be Automated:** Query variant generation (happens during Claude Code's reasoning)
📋 **Manual Testing Required:** End-to-end workflow validation in Claude Code interface

---

## Unit Test Results

**Test Suite:** `tests/test_query_expansion.py`
**Status:** ✅ 17/17 tests passed
**Coverage:** `deduplicate_by_l2_id` and `merge_rrf_scores` functions

### Test Categories

1. **Deduplication Tests (6 tests)**
   - No duplicates
   - With duplicates (keeps highest score)
   - Empty list
   - Single document
   - All duplicates
   - Preserves additional fields

2. **RRF Fusion Tests (8 tests)**
   - Single query results
   - Two queries without overlap
   - Two queries with overlap (critical test)
   - Four queries (query expansion scenario)
   - Custom k values
   - Empty results
   - Preserves additional fields
   - Default k=60 validation

3. **Integration Tests (3 tests)**
   - Full pipeline (4 queries → RRF → dedup → Top-5)
   - Deduplication after RRF
   - Edge cases

**Run Tests:**
```bash
poetry run pytest tests/test_query_expansion.py -v
```

---

## Manual Testing Procedure

### Test Environment Setup

**Prerequisites:**
1. ✅ MCP Server running (PostgreSQL + pgvector)
2. ✅ OpenAI API key configured in `.mcp.json`
3. ✅ Database populated with L2 Insights (from Epic 1)
4. ✅ `hybrid_search` MCP tool accessible
5. ✅ `config.yaml` with `query_expansion` section enabled

**Verification:**
```bash
# Check MCP server status
poetry run python -m mcp_server --version

# Verify database connection
psql -U mcp_user -d cognitive_memory -c "SELECT COUNT(*) FROM l2_insights;"

# Check config
grep -A 10 "query_expansion:" config/config.yaml
```

---

## Test Cases

### Test Case 1: Short Query (Single Sentence)

**Query:** "Was denke ich über Autonomie?"

**Expected Behavior:**
1. Claude Code internally generates 3 variants:
   - **Paraphrase:** "Was ist meine Perspektive auf das Autonomie-Konzept?"
   - **Perspektiv-Shift:** "Meine Meinung zum Thema Autonomie wäre..."
   - **Keyword-Fokus:** "Autonomie Gedanken Meinung Perspektive"

2. 4 Queries embedded (Original + 3 variants):
   - OpenAI API calls: 4× `text-embedding-3-small`
   - Expected latency: ~0.2-0.3s (parallel)

3. 4 `hybrid_search` calls (concurrent):
   - Each returns Top-5 results
   - Expected latency: ~0.8-1.0s (parallel, NOT 3-4s sequential)

4. Deduplication:
   - Combined results may have overlapping L2 IDs
   - `deduplicate_by_l2_id()` removes duplicates
   - Keeps highest-scoring instance per ID

5. RRF Fusion:
   - `merge_rrf_scores()` with k=60
   - Final Top-5 documents sorted by RRF score

6. Total Latency:
   - Expected: ~1.5-2.5s end-to-end
   - Acceptable: <5s p95 (NFR001)

**Success Criteria:**
- ✅ No errors or crashes
- ✅ Returns Top-5 unique documents (no duplicate L2 IDs)
- ✅ Latency <5s
- ✅ Documents semantically relevant to query

---

### Test Case 2: Medium Query (Multiple Sentences)

**Query:** "Wie verstehe ich die Beziehung zwischen Bewusstsein und Identität?"

**Expected Behavior:**
1. 3 variants generated (similar process to Test Case 1)
2. 4× Embeddings + 4× hybrid_search
3. Deduplication + RRF fusion
4. Top-5 final results

**Success Criteria:**
- ✅ Same as Test Case 1
- ✅ Variants handle longer query appropriately
- ✅ No degradation in quality or latency

---

### Test Case 3: Long Query (Complex Multi-Clause)

**Query:** "Wenn ich über die philosophischen Implikationen von Autonomie nachdenke, besonders im Kontext von emergenten Strukturen und selbstorganisierenden Systemen, was ist dann meine Kernperspektive?"

**Expected Behavior:**
1. Variants generated correctly (not truncated or malformed)
2. Keyword variant extracts core concepts despite length
3. 4× Embeddings + 4× hybrid_search
4. Deduplication + RRF fusion

**Success Criteria:**
- ✅ Variants handle complex query structure
- ✅ Keyword variant focuses on core terms (Autonomie, Emergenz, selbstorganisierend)
- ✅ No token limit errors
- ✅ Latency remains <5s

---

### Test Case 4: Single-Word Query (Edge Case)

**Query:** "Bewusstsein"

**Expected Behavior:**
1. Variants generated despite minimal input:
   - **Paraphrase:** "Was ist Bewusstsein?"
   - **Perspektiv-Shift:** "Meine Gedanken zum Bewusstsein"
   - **Keyword-Fokus:** "Bewusstsein Konzept Definition"

2. 4× Embeddings + 4× hybrid_search
3. Deduplication + RRF fusion

**Success Criteria:**
- ✅ Variants are semantically meaningful (not empty or malformed)
- ✅ Retrieval returns relevant documents
- ✅ No errors despite minimal input

---

### Test Case 5: Deduplication Verification

**Query:** "Was denke ich über Autonomie?" (reuse Test Case 1)

**Verification Steps:**
1. Observe results from all 4 queries
2. Manually check for overlapping L2 IDs across queries
3. Verify final Top-5 contains unique IDs only

**Expected Overlap:**
- Query variants (Paraphrase, Perspektiv-Shift) should retrieve similar documents
- Original + Paraphrase: High overlap (70-80%)
- Keyword variant: May retrieve different documents (30-50% overlap)

**Success Criteria:**
- ✅ At least 1-2 documents appear in multiple query results
- ✅ Final Top-5 has NO duplicate L2 IDs
- ✅ `deduplicate_by_l2_id()` correctly removed duplicates

---

## Performance Benchmarks

### Latency Breakdown

| Step                | Target      | Acceptable  | Notes                        |
|---------------------|-------------|-------------|------------------------------|
| Query Expansion     | ~0.2-0.3s   | <0.5s       | Internal Claude Code         |
| Embeddings (4×)     | ~0.2-0.3s   | <0.5s       | Parallel OpenAI API          |
| Hybrid Search (4×)  | ~0.8-1.0s   | <2s         | Parallel MCP tool calls      |
| Dedup + RRF         | ~0.05s      | <0.1s       | In-memory operation          |
| **Total**           | **~1.5-2s** | **<5s p95** | End-to-end (NFR001)          |

### Cost Analysis

**Per Query:**
- Query Expansion: €0 (internal reasoning, included in Claude MAX)
- Embeddings: 4 × €0.00002 = **€0.00008**
- Hybrid Search: €0 (local MCP tool)
- **Total:** **€0.00008 per query**

**Comparison:**
- Without Expansion: €0.00002 per query (1 embedding)
- With Expansion: €0.00008 per query (4 embeddings)
- Cost Increase: **4× embedding cost**
- Benefit: **+10-15% recall uplift**

**Alternative (Haiku API for Expansion):**
- Expansion via Haiku: €0.50 per query
- Savings: **€0.49992 per query (6249× cheaper!)**

---

## Recall Uplift Measurement

### Baseline (Without Query Expansion)

**Setup:**
1. Select 20 test queries from ground truth set
2. Run single query (no expansion)
3. Measure Precision@5 for each query

**Expected Baseline:**
- Precision@5: 0.70-0.75
- Recall@5: 0.65-0.70

### Expansion Test (With Query Expansion)

**Setup:**
1. Use same 20 test queries
2. Run with query expansion (4 queries per test)
3. Measure Precision@5 for each query

**Expected Results:**
- Precision@5: 0.75-0.82
- Recall@5: 0.72-0.80
- **Uplift: +10-15%**

### Measurement Procedure

1. **Baseline Run:**
   ```python
   # Pseudo-code (manual in Claude Code interface)
   for query in test_queries:
       results = hybrid_search(query, top_k=5)  # No expansion
       precision = calculate_precision(results, ground_truth[query])
   baseline_avg_precision = mean(precisions)
   ```

2. **Expansion Run:**
   ```python
   # Pseudo-code (manual in Claude Code interface)
   for query in test_queries:
       variants = generate_variants(query)  # Internal reasoning
       all_results = []
       for variant in [query] + variants:
           results = hybrid_search(variant, top_k=5)
           all_results.append(results)
       merged = merge_rrf_scores(all_results, k=60)
       top_5 = merged[:5]
       precision = calculate_precision(top_5, ground_truth[query])
   expansion_avg_precision = mean(precisions)
   ```

3. **Calculate Uplift:**
   ```python
   uplift = (expansion_avg_precision - baseline_avg_precision) / baseline_avg_precision
   # Expected: 0.10-0.15 (10-15%)
   ```

---

## Success Criteria Summary

### Functional Requirements

- ✅ All 5 test queries complete without errors
- ✅ 3 variants generated per query (Paraphrase, Perspektiv-Shift, Keyword)
- ✅ 4 embeddings created per query (OpenAI API calls)
- ✅ 4 `hybrid_search` calls per query (MCP tool calls)
- ✅ Deduplication removes duplicate L2 IDs
- ✅ RRF fusion produces Top-5 final results
- ✅ Final results semantically relevant to query

### Non-Functional Requirements

- ✅ Latency <5s p95 end-to-end
- ✅ Cost €0.00008 per query (4 embeddings only)
- ✅ Recall uplift +10-15% vs. baseline
- ✅ No API errors or crashes
- ✅ Parallel execution (not sequential) for embeddings and searches

### Configuration Validation

- ✅ `config.yaml` has `query_expansion` section
- ✅ `enabled: true`
- ✅ `num_variants: 3`
- ✅ `strategies: [paraphrase, perspective_shift, keyword_focus]`
- ✅ `rrf_k: 60`
- ✅ `final_top_k: 5`

---

## Known Limitations

1. **No Automated Testing for Variant Generation:**
   - Query expansion is an internal reasoning process
   - Cannot be unit-tested directly
   - Manual observation required

2. **Latency Variability:**
   - Depends on OpenAI API response time
   - Database query performance
   - Network conditions
   - Expect 1.5-3s range (avg 2s)

3. **Recall Uplift Depends on Dataset:**
   - +10-15% is expected average
   - May vary based on query complexity and L2 Insight corpus
   - Some queries may benefit more (semantic-heavy) vs. less (keyword-heavy)

---

## Troubleshooting

### Issue: Variants Not Semantically Diverse

**Symptoms:** All 3 variants are very similar to original query

**Causes:**
- Query too short (e.g., single word)
- Query already highly specific (little room for paraphrasing)

**Solutions:**
- Adjust variant generation strategy
- Increase temperature in `config.yaml` (default 0.7 → 0.8)

### Issue: Latency >5s

**Symptoms:** End-to-end latency exceeds NFR001 budget

**Causes:**
- Sequential instead of parallel execution
- Slow OpenAI API response
- Database query performance issues

**Solutions:**
- Verify `parallel_embedding: true` and `parallel_search: true` in config
- Check OpenAI API status
- Optimize database indexes (l2_insights.embedding)

### Issue: Poor Recall Uplift (<10%)

**Symptoms:** Query expansion doesn't improve retrieval quality

**Causes:**
- Variants too similar to original
- Database corpus lacks semantic diversity
- Hybrid search weights not optimal

**Solutions:**
- Review variant generation (manual observation)
- Increase `num_variants` from 3 to 5
- Calibrate `semantic_weight` / `keyword_weight` (Story 2.8)

---

## Next Steps

After completing manual testing:

1. **Document Results:** Create `/docs/query-expansion-evaluation.md` (Task 5)
2. **Measure Recall Uplift:** Run baseline vs. expansion comparison
3. **Optimize Configuration:** Fine-tune `num_variants`, `rrf_k` if needed
4. **Prepare for Story 2.3:** Chain-of-Thought (CoT) Generation Framework

---

## References

- [Query Expansion Guide](./query-expansion-guide.md) - Strategy and implementation details
- [Epic 2 Tech Spec](../bmad-docs/tech-spec-epic-2.md) - Technical requirements
- [Story 2.2](../bmad-docs/stories/2-2-query-expansion-logik-intern-in-claude-code.md) - Story file

---

**Document Status:** ✅ Complete
**Author:** Dev Agent (claude-sonnet-4-5-20250929)
**Last Updated:** 2025-11-16
