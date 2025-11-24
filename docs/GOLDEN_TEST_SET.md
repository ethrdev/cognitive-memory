# Golden Test Set Documentation

**Story 3.1** | **Status:** Production Ready | **Created:** 2025-11-18

## Overview

The Golden Test Set is a **separate, immutable** test set of 50-100 queries used for daily Precision@5 regression testing and model drift detection. This set is critical for ongoing production monitoring (Epic 3) and must remain completely independent from the Ground Truth Set used for calibration.

## Purpose

- **Model Drift Detection:** Daily Precision@5 validation to catch API changes (e.g., OpenAI embedding model updates)
- **Regression Testing:** Continuous validation that system performance doesn't degrade
- **Immutable Baseline:** Fixed test set enables long-term performance tracking
- **Separation of Concerns:** Prevents "teaching to the test" by using different sessions than Ground Truth

## Key Characteristics

### Size
- **Target:** 50-100 queries
- **Statistical Power:** >0.80 for Precision@5 validation at alpha=0.05

### Stratification
- **40% Short** (≤10 words): Quick factual queries
- **40% Medium** (11-29 words): Balanced queries
- **20% Long** (≥30 words): Complex philosophical questions
- **Tolerance:** ±5% per category

### Independence
- **ZERO overlap** with Ground Truth sessions
- Sessions sampled from L0 Raw Memory excluding any session used in ground_truth table
- Prevents overfitting on calibration data

### Immutability
- **NO updates** after initial labeling
- **NO deletions** permitted
- Only INSERT operations during creation phase
- Documented in schema comments

## Database Schema

```sql
CREATE TABLE golden_test_set (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    query_type VARCHAR(10) NOT NULL CHECK (query_type IN ('short', 'medium', 'long')),
    expected_docs INTEGER[] NOT NULL,
    session_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    word_count INTEGER,
    labeled_by VARCHAR(50) DEFAULT 'ethr',
    notes TEXT
);

-- Indices for query performance
CREATE INDEX idx_golden_query_type ON golden_test_set(query_type);
CREATE INDEX idx_golden_created_at ON golden_test_set(created_at);
CREATE INDEX idx_golden_session_id ON golden_test_set(session_id);
```

## Creation Workflow

### Step 1: Run Database Migration

```bash
psql -U mcp_user -d cognitive_memory -f mcp_server/db/migrations/006_golden_test_set.sql
```

**Verification:**
```sql
\d golden_test_set  -- Inspect schema
SELECT COUNT(*) FROM golden_test_set;  -- Should be 0 initially
```

### Step 2: Generate Golden Test Queries

```bash
python mcp_server/scripts/create_golden_test_set.py --target-count 75
```

**What this does:**
1. Queries l0_raw for all unique session_ids
2. Excludes sessions already in ground_truth table (CRITICAL)
3. Samples queries stratified by length (40%/40%/20%)
4. Inserts queries into golden_test_set (expected_docs empty initially)

**Expected Output:**
```
✅ Golden Test Set Creation Complete!
Queries created: 75
Next step: Run Streamlit UI to label queries
```

**Validation Checks:**
- ✅ 50-100 queries created
- ✅ Stratification within ±5% tolerance
- ✅ ZERO session overlap with ground_truth
- ✅ All queries from valid l0_raw sessions

### Step 3: Manual Labeling via Streamlit UI

```bash
streamlit run mcp_server/ui/golden_test_app.py
```

**Labeling Process:**
1. UI displays each query with hybrid_search Top-5 results
2. User marks relevant documents (binary relevance)
3. Labels saved to golden_test_set.expected_docs (PostgreSQL)
4. Progress tracked: Short/Medium/Long distribution displayed

**Expected Duration:** 2-3 hours for 75 queries (similar to Ground Truth labeling in Story 1.10)

### Step 4: Validate Golden Test Set

```bash
python mcp_server/scripts/validate_golden_test_set.py
```

**Validation Checks:**
1. ✅ Query count: 50-100
2. ✅ Stratification: 40%/40%/20% (±5%)
3. ✅ No session overlap with ground_truth
4. ✅ All queries labeled (no NULL expected_docs)
5. ✅ Immutability documented in schema

## Usage in Production

### Daily Precision@5 Testing (Story 3.2)

The Golden Test Set is executed **daily** via the `get_golden_test_results` MCP Tool:

```python
# Daily cron job (2 AM)
results = get_golden_test_results()

# Returns:
{
    "date": "2025-11-18",
    "precision_at_5": 0.78,
    "num_queries": 75,
    "drift_detected": False,
    "baseline_p5": 0.80,
    "current_p5": 0.78,
    "drop_percentage": -2.5%
}
```

**Drift Detection Trigger:**
- Precision@5 drops >5% vs. 7-day rolling average
- Example: Baseline P@5=0.80, Current P@5=0.75 → ALERT

### SQL Queries

**Count queries:**
```sql
SELECT COUNT(*) FROM golden_test_set;
```

**Check stratification:**
```sql
SELECT query_type, COUNT(*) as count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM golden_test_set
GROUP BY query_type
ORDER BY query_type;
```

**Verify no overlap (CRITICAL):**
```sql
SELECT COUNT(*)
FROM golden_test_set gts
INNER JOIN (
    SELECT DISTINCT l0.session_id
    FROM ground_truth gt
    CROSS JOIN LATERAL unnest(gt.expected_docs) AS l2_id
    JOIN l2_insights l2 ON l2.id = l2_id
    CROSS JOIN LATERAL unnest(l2.source_ids) AS l0_id
    JOIN l0_raw l0 ON l0.id = l0_id
) gt_sessions ON gts.session_id = gt_sessions.session_id;
-- Expected: 0 (ZERO overlap)
```

**Check labeling progress:**
```sql
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN expected_docs IS NULL OR expected_docs = '{}' THEN 1 ELSE 0 END) as unlabeled,
    SUM(CASE WHEN expected_docs IS NOT NULL AND expected_docs != '{}' THEN 1 ELSE 0 END) as labeled
FROM golden_test_set;
```

## Comparison: Ground Truth vs. Golden Test

| Aspect | Ground Truth Set | Golden Test Set |
|--------|-----------------|----------------|
| **Purpose** | Calibration (Grid Search) | Ongoing Validation (Drift Detection) |
| **Size** | 50-100 queries | 50-100 queries |
| **Labeling** | Dual Judge (GPT-4o + Haiku) + User | User only (no Dual Judge) |
| **Usage** | One-time (Story 2.8) | Daily (Story 3.2) |
| **Mutability** | Can be extended for re-calibration | IMMUTABLE after creation |
| **Table** | `ground_truth` (with judge_scores) | `golden_test_set` (no judge scores) |
| **Sessions** | Any L0 sessions | MUST NOT overlap with Ground Truth |

## Files Created (Story 3.1)

- **Migration:** `mcp_server/db/migrations/006_golden_test_set.sql`
- **Sampling Script:** `mcp_server/scripts/create_golden_test_set.py`
- **Streamlit UI:** `mcp_server/ui/golden_test_app.py` (adapted from Story 1.10)
- **Validation Script:** `mcp_server/scripts/validate_golden_test_set.py`
- **Documentation:** `docs/GOLDEN_TEST_SET.md` (this file)

## Dependencies

- **From Story 2.9:** `classify_query_type()` function for query classification
- **From Story 1.10:** Streamlit UI pattern for manual labeling
- **From Epic 1:** L0 Raw Memory, L2 Insights, database connection pool

## Acceptance Criteria Met

- ✅ **AC-3.1.1:** Query extraction with 40%/40%/20% stratification, NO ground_truth overlap
- ✅ **AC-3.1.2:** Manual labeling via Streamlit UI (reused from Story 1.10)
- ✅ **AC-3.1.3:** golden_test_set table with query_type column and indices
- ✅ **AC-3.1.4:** Immutability enforced and documented

## Next Steps (Epic 3 Continuation)

1. **Story 3.2:** Implement `get_golden_test_results` MCP Tool for daily drift detection
2. **Story 3.11:** 7-Day Stability Testing using Golden Test Set for continuous validation
3. **Story 3.12:** Production handoff documentation referencing Golden Test Set usage

## References

- **Tech Spec:** `bmad-docs/tech-spec-epic-3.md` (Story 3.1 Acceptance Criteria)
- **Epics:** `bmad-docs/epics.md` (lines 887-921)
- **Architecture:** `bmad-docs/architecture.md` (Database Schema section)
- **Story File:** `bmad-docs/stories/3-1-golden-test-set-creation-separate-von-ground-truth.md`
