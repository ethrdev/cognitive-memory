# Production Deployment Guide: Story 2.9 - Precision@5 Validation

**Document Version:** 1.0
**Created:** 2025-11-16
**Purpose:** Step-by-step guide for deploying Precision@5 validation to production environment

---

## Executive Summary

This guide provides instructions for deploying and executing the Precision@5 validation script in a production environment with real PostgreSQL access. The development environment validation used mock data and achieved P@5 = 0.0240 (expected baseline for random data). Production validation is required to verify NFR002 compliance (Precision@5 >0.75).

**Critical Success Criteria:**

- Production Precision@5 ≥0.75 → Epic 2 COMPLETE, ready for Epic 3
- Production Precision@5 0.70-0.74 → Deploy with monitoring, re-calibrate in 2 weeks
- Production Precision@5 <0.70 → Architecture review required

---

## Prerequisites

### 1. Database Requirements

**PostgreSQL Database with:**

- ✅ `ground_truth` table populated with 50-100 queries
- ✅ Each query has `expected_docs` array (relevant L2 Insight IDs)
- ✅ `l2_insights` table with embeddings (from Epic 1, Story 1.5)
- ✅ Network access to Neon PostgreSQL instance

**Verification Command:**

```sql
-- Check ground truth count
SELECT COUNT(*) FROM ground_truth;
-- Expected: 50-100 rows

-- Check expected_docs populated
SELECT COUNT(*) FROM ground_truth WHERE expected_docs IS NOT NULL AND array_length(expected_docs, 1) > 0;
-- Expected: Same as total count (all queries have expected docs)

-- Check L2 insights with embeddings
SELECT COUNT(*) FROM l2_insights WHERE embedding IS NOT NULL;
-- Expected: >0 (embeddings exist for hybrid search)
```

### 2. API Access

**OpenAI API:**

- ✅ Valid API key in `.env` file
- ✅ Sufficient credits for embeddings (estimated cost: ~$0.01 for 100 queries)
- ✅ Model: `text-embedding-3-small` (8191 token context)

**Verification Command:**

```bash
# Test OpenAI API access
python -c "
import os
from openai import OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
response = client.embeddings.create(
    model='text-embedding-3-small',
    input='test query'
)
print(f'✅ OpenAI API accessible: {len(response.data[0].embedding)} dimensions')
"
```

### 3. Python Environment

**Required:**

- Python 3.11+
- Dependencies installed: `pip install -r requirements.txt`
- Environment variables configured (`.env` file)

**Verification Command:**

```bash
# Check Python version
python --version
# Expected: Python 3.11.x or higher

# Check dependencies
pip list | grep -E "psycopg2|openai|pyyaml|numpy"
# Expected: All packages installed

# Check environment variables
python -c "import os; print('✅ DB URL:', 'present' if os.getenv('DATABASE_URL') else 'MISSING'); print('✅ OpenAI:', 'present' if os.getenv('OPENAI_API_KEY') else 'MISSING')"
```

---

## Step-by-Step Deployment Instructions

### Step 1: Backup Current Configuration

**Purpose:** Preserve development environment settings before production changes

```bash
# Backup config.yaml
cp config.yaml config.yaml.backup.$(date +%Y%m%d)

# Backup validation script
cp mcp_server/scripts/validate_precision_at_5.py mcp_server/scripts/validate_precision_at_5.py.backup

# Backup previous results (if they exist)
if [ -f mcp_server/scripts/validation_results.json ]; then
    mv mcp_server/scripts/validation_results.json mcp_server/scripts/validation_results.mock.json
fi
if [ -f bmad-docs/evaluation-results.md ]; then
    mv bmad-docs/evaluation-results.md bmad-docs/evaluation-results.mock.md
fi
```

**Expected Output:**

```
✅ Backups created with timestamp suffix
```

---

### Step 2: Configure Production Mode

**Purpose:** Disable mock data and enable real PostgreSQL connection

**File:** `mcp_server/scripts/validate_precision_at_5.py`

**Change Line 35:**

```python
# BEFORE (Development):
MOCK_MODE = True  # Set to False for production with real PostgreSQL

# AFTER (Production):
MOCK_MODE = False  # Production mode - use real PostgreSQL
```

**Verification:**

```bash
# Check MOCK_MODE setting
grep "^MOCK_MODE = " mcp_server/scripts/validate_precision_at_5.py
# Expected output: MOCK_MODE = False
```

---

### Step 3: Verify Database Connection

**Purpose:** Ensure PostgreSQL connection works before running validation

**Test Script:**

```bash
python -c "
import os
import sys
sys.path.insert(0, 'mcp_server')

from db.connection import get_connection

try:
    conn = get_connection()
    cursor = conn.cursor()

    # Test ground_truth table access
    cursor.execute('SELECT COUNT(*) FROM ground_truth')
    count = cursor.fetchone()[0]
    print(f'✅ Database connection successful')
    print(f'✅ Ground truth queries found: {count}')

    # Test expected_docs populated
    cursor.execute('SELECT COUNT(*) FROM ground_truth WHERE expected_docs IS NOT NULL AND array_length(expected_docs, 1) > 0')
    populated = cursor.fetchone()[0]
    print(f'✅ Queries with expected_docs: {populated}')

    if count < 50:
        print(f'⚠️  WARNING: Ground truth count ({count}) is below recommended minimum (50)')

    if populated < count:
        print(f'⚠️  WARNING: {count - populated} queries missing expected_docs')

    cursor.close()
    conn.close()

except Exception as e:
    print(f'❌ Database connection FAILED: {e}')
    sys.exit(1)
"
```

**Expected Output:**

```
✅ Database connection successful
✅ Ground truth queries found: 100
✅ Queries with expected_docs: 100
```

**Troubleshooting:**

- If connection fails, check `DATABASE_URL` in `.env`
- If count is 0, verify Epic 1 (Story 1.10-1.12) ground truth collection completed
- If expected_docs missing, run ground truth labeling workflow

---

### Step 4: Load Calibrated Weights

**Purpose:** Verify config.yaml contains calibrated weights from Story 2.8

**Verification:**

```bash
# Check calibrated weights
python -c "
import yaml
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)
    weights = config['hybrid_search_weights']
    print(f'✅ Semantic weight: {weights[\"semantic\"]}')
    print(f'✅ Keyword weight: {weights[\"keyword\"]}')
    print(f'⚠️  Production ready: {weights.get(\"production_ready\", False)}')
"
```

**Expected Output:**

```
✅ Semantic weight: 0.7
✅ Keyword weight: 0.3
⚠️  Production ready: False
```

**Note:** `production_ready: False` is expected (will be updated after successful validation)

---

### Step 5: Execute Production Validation

**Purpose:** Run Precision@5 validation with real data

**Execution Command:**

```bash
# Run validation script
cd /home/user/i-o
python mcp_server/scripts/validate_precision_at_5.py

# Expected runtime: 2-5 minutes for 100 queries (depends on API latency)
```

**Expected Output (Success):**

```
=== Precision@5 Validation auf Ground Truth Set ===

Configuration:
  Semantic weight: 0.7
  Keyword weight: 0.3
  Mock mode: False

Loading Ground Truth Set...
✅ Loaded 100 queries from PostgreSQL

Running validation...
Progress: 100/100 queries processed

Results:
  Macro-Average Precision@5: 0.7680

Breakdown by Query Type:
  Short queries (40): P@5 = 0.7450
  Medium queries (40): P@5 = 0.8200
  Long queries (20): P@5 = 0.7400

Success Criteria Evaluation:
  Status: FULL SUCCESS ✅
  Recommendation: System ready for production. Epic 2 COMPLETE.

Results saved:
  - mcp_server/scripts/validation_results.json
  - bmad-docs/evaluation-results.md
```

**Monitoring During Execution:**

```bash
# In separate terminal, monitor progress
watch -n 5 'tail -20 mcp_server/scripts/validate_precision_at_5.py.log 2>/dev/null || echo "Log not created yet"'
```

---

### Step 6: Analyze Results

**Purpose:** Review validation results and determine success level

**Review validation_results.json:**

```bash
# Check overall Precision@5
python -c "
import json
with open('mcp_server/scripts/validation_results.json', 'r') as f:
    results = json.load(f)
    p5 = results['macro_avg_precision_at_5']
    print(f'Macro-Average Precision@5: {p5:.4f}')

    if p5 >= 0.75:
        print('✅ FULL SUCCESS - NFR002 met (P@5 ≥0.75)')
        print('   → Epic 2 COMPLETE')
        print('   → Ready for Epic 3 transition')
    elif p5 >= 0.70:
        print('⚠️  PARTIAL SUCCESS - Deploy with monitoring (P@5 0.70-0.74)')
        print('   → Deploy to production with monitoring')
        print('   → Re-calibrate in 2 weeks')
    else:
        print('❌ FAILURE - Architecture review required (P@5 <0.70)')
        print('   → Review query-type breakdown')
        print('   → Evaluate architecture options')

    print(f'\nBreakdown by Query Type:')
    for qtype, stats in results['breakdown_by_type'].items():
        print(f'  {qtype.capitalize()}: P@5 = {stats[\"avg_precision_at_5\"]:.4f} ({stats[\"count\"]} queries)')
"
```

**Review evaluation-results.md:**

```bash
# Open comprehensive evaluation report
cat bmad-docs/evaluation-results.md

# Key sections:
# 1. Executive Summary - Overall status
# 2. Precision@5 Results - Metrics and breakdown
# 3. Success Criteria Evaluation - Full/Partial/Failure determination
# 4. Recommendations - Next steps
```

---

### Step 7: Update Configuration (if Full Success)

**Purpose:** Mark calibrated weights as production-validated

**Condition:** Only if Precision@5 ≥0.75 (FULL SUCCESS)

**File:** `config.yaml`

**Change:**

```yaml
# BEFORE:
hybrid_search_weights:
  semantic: 0.7
  keyword: 0.3
  calibration_precision_at_5: 0.1040
  mock_data: true
  production_ready: false

# AFTER:
hybrid_search_weights:
  semantic: 0.7
  keyword: 0.3
  calibration_precision_at_5: 0.1040  # Mock calibration baseline
  validation_precision_at_5: 0.7680   # Production validation result
  mock_data: false
  production_ready: true
  validated_date: "2025-11-16"
```

**Execution:**

```bash
# Update config.yaml programmatically
python -c "
import yaml
import json

# Load production validation results
with open('mcp_server/scripts/validation_results.json', 'r') as f:
    results = json.load(f)
    prod_p5 = results['macro_avg_precision_at_5']

# Update config.yaml
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

config['hybrid_search_weights']['validation_precision_at_5'] = round(prod_p5, 4)
config['hybrid_search_weights']['mock_data'] = False
config['hybrid_search_weights']['production_ready'] = True
config['hybrid_search_weights']['validated_date'] = '2025-11-16'

with open('config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print(f'✅ config.yaml updated with production validation P@5 = {prod_p5:.4f}')
"
```

---

### Step 8: Update Sprint Status (if Full Success)

**Purpose:** Mark Epic 2 as complete in sprint tracking

**Condition:** Only if Precision@5 ≥0.75 (FULL SUCCESS)

**File:** `bmad-docs/sprint-status.yaml`

**Change:**

```yaml
# Update epic-2 status from "contexted" to "done"
development_status:
  epic-2: done  # Changed from: contexted
```

**Execution:**

```bash
# Update sprint-status.yaml
sed -i 's/epic-2: contexted/epic-2: done/' bmad-docs/sprint-status.yaml

# Verify change
grep "epic-2:" bmad-docs/sprint-status.yaml
# Expected: epic-2: done
```

---

### Step 9: Commit and Document

**Purpose:** Preserve production validation results in version control

**Git Workflow:**

```bash
# Stage all production validation changes
git add config.yaml
git add mcp_server/scripts/validate_precision_at_5.py
git add mcp_server/scripts/validation_results.json
git add bmad-docs/evaluation-results.md
git add bmad-docs/sprint-status.yaml

# Commit with detailed message
git commit -m "$(cat <<'EOF'
Story 2.9 production validation: FULL SUCCESS

Production Precision@5 validation completed with real data:
- Macro-Average P@5: 0.7680 (exceeds NFR002 target of 0.75)
- Query breakdown: Short (0.7450), Medium (0.8200), Long (0.7400)
- Success level: FULL SUCCESS - Epic 2 COMPLETE

Changes:
- Set MOCK_MODE=False for production deployment
- Validated with real PostgreSQL ground_truth table (100 queries)
- Updated config.yaml: production_ready=true, validation_precision_at_5=0.7680
- Updated sprint-status.yaml: epic-2 status → done

Epic 2 completion verified. Ready for Epic 3 transition.
EOF
)"

# Push to remote
git push -u origin claude/create-story-workflow-01FR741Nae3yTaJJHwW531CH
```

**Expected Output:**

```
✅ 5 files changed, X insertions(+), Y deletions(-)
✅ Pushed to remote branch
```

---

## Success Criteria Decision Tree

### Full Success (P@5 ≥0.75)

**Status:** ✅ NFR002 MET - Epic 2 COMPLETE

**Actions:**

1. ✅ Update config.yaml: `production_ready: true`
2. ✅ Update sprint-status.yaml: `epic-2: done`
3. ✅ Commit and push changes
4. ✅ Proceed to Epic 3 (Story 3.1: Golden Test Set Creation)

**Documentation:**

- evaluation-results.md contains FULL SUCCESS status
- validation_results.json confirms P@5 ≥0.75
- config.yaml marked as production-ready

---

### Partial Success (P@5 0.70-0.74)

**Status:** ⚠️ DEPLOY WITH MONITORING - Re-calibration in 2 weeks

**Actions:**

1. ⚠️ Deploy system to production (functional but sub-optimal)
2. 📋 Create monitoring plan (daily P@5 checks)
3. 📋 Schedule re-calibration in 2 weeks
4. 📋 Continue data collection (target: 100+ additional L2 insights)
5. ⏸️ Do NOT mark epic-2 as "done" yet (pending re-calibration)

**Monitoring Plan Template:**

```yaml
# monitoring-plan-story-2.9.yaml
monitoring:
  metric: precision_at_5
  frequency: daily
  threshold_warning: 0.70
  threshold_critical: 0.65

  schedule:
    - week_1: Daily P@5 checks on 10-query sample
    - week_2: Collect 50+ additional L2 insights
    - week_2_end: Re-run calibration (Story 2.8) with extended dataset
    - week_3: Re-run validation (Story 2.9) with new weights

  success_criteria:
    - Re-calibration P@5 ≥0.75 → Mark Epic 2 complete
    - Re-calibration P@5 still 0.70-0.74 → Continue monitoring, collect more data
```

**Documentation Updates:**

```bash
# Create monitoring plan
cat > bmad-docs/monitoring-plan-epic-2.md << 'EOF'
# Epic 2 Monitoring Plan - Partial Success Path

**Validation Result:** P@5 = 0.72 (Partial Success)

## Monitoring Schedule
- **Week 1-2:** Daily P@5 checks, data collection
- **Week 2 End:** Re-calibration with extended dataset
- **Week 3:** Re-validation with new weights

## Target
- Re-validation P@5 ≥0.75 → Epic 2 complete
EOF

# Do NOT update sprint-status.yaml epic-2 status yet
```

---

### Failure (P@5 <0.70)

**Status:** ❌ ARCHITECTURE REVIEW REQUIRED

**Actions:**

1. 🔍 Analyze query-type breakdown (identify which types are failing)
2. 🔍 Review evaluation-results.md failure analysis section
3. 🔍 Evaluate architecture options (see below)
4. 🛑 Do NOT deploy to production yet
5. 🛑 Do NOT mark epic-2 as "done"

**Root Cause Analysis:**

**Option A: Short Queries Failing (P@5 <0.60 for short queries)**

```
Hypothesis: Keyword search too weak, semantic search lacks context for short queries
Solution: Re-calibrate with higher keyword weight (e.g., semantic=0.6, keyword=0.4)
Timeline: 1-2 days for re-calibration
```

**Option B: Long Queries Failing (P@5 <0.60 for long queries)**

```
Hypothesis: Semantic search truncates long queries (>8191 tokens?)
Solution: Upgrade embedding model to text-embedding-3-large (8192 tokens → 8192 tokens, higher quality)
Timeline: 1-2 days for migration + re-embedding
```

**Option C: All Query Types Failing (P@5 <0.60 across all types)**

```
Hypothesis: Systematic issue (L2 quality low, ground truth mislabeled, or embedding model inadequate)
Solutions:
  1. Re-label ground truth with higher IRR (target Kappa >0.80)
  2. Improve L2 compression quality (more detailed insights)
  3. Consider different embedding model (e.g., OpenAI text-embedding-3-large or ada-002)
Timeline: 1-2 weeks for architecture review + remediation
```

**Architecture Review Meeting Agenda:**

```markdown
# Epic 2 Architecture Review - P@5 Failure Analysis

**Meeting Date:** [Schedule within 48 hours]
**Attendees:** Product Manager, Architect, Developer

## Agenda
1. Review validation results (breakdown by query type)
2. Identify failure patterns
3. Evaluate remediation options
4. Select path forward
5. Create revised Epic 2 timeline

## Decision Framework
- Option 1: Re-calibration with different weight ranges
- Option 2: Embedding model upgrade
- Option 3: Ground truth quality improvement
- Option 4: L2 insight quality improvement
- Option 5: Hybrid approach (multiple changes)

## Success Criteria
- Revised approach should target P@5 ≥0.75
- Timeline should not exceed 2 weeks
- Budget impact should be minimal (<$100 additional API costs)
```

---

## Rollback Procedure

**If production validation fails or needs to be reverted:**

```bash
# Step 1: Restore mock mode
sed -i 's/MOCK_MODE = False/MOCK_MODE = True/' mcp_server/scripts/validate_precision_at_5.py

# Step 2: Restore previous config.yaml
cp config.yaml.backup.* config.yaml

# Step 3: Restore mock results
if [ -f mcp_server/scripts/validation_results.mock.json ]; then
    mv mcp_server/scripts/validation_results.mock.json mcp_server/scripts/validation_results.json
fi
if [ -f bmad-docs/evaluation-results.mock.md ]; then
    mv bmad-docs/evaluation-results.mock.md bmad-docs/evaluation-results.md
fi

# Step 4: Verify rollback
grep "^MOCK_MODE = " mcp_server/scripts/validate_precision_at_5.py
# Expected: MOCK_MODE = True

echo "✅ Rollback complete - system restored to development mode"
```

---

## Troubleshooting

### Issue 1: Database Connection Timeout

**Symptom:**

```
psycopg2.OperationalError: timeout expired
```

**Solution:**

```bash
# Check database connection
psql $DATABASE_URL -c "SELECT 1"

# If connection works but validation times out, increase timeout in connection.py:
# Change: connect_timeout=10 → connect_timeout=30
```

---

### Issue 2: OpenAI API Rate Limit

**Symptom:**

```
openai.RateLimitError: Rate limit exceeded
```

**Solution:**

```python
# Add exponential backoff in validate_precision_at_5.py
# (Already implemented in lines 107-123 mock_hybrid_search function)

# Reduce batch size:
# Process 10 queries at a time with 5-second pause between batches
```

---

### Issue 3: Low Precision@5 (<0.70)

**Symptom:**

```
Macro-Average Precision@5: 0.52 (FAILURE)
```

**Solution:**

```bash
# Step 1: Review breakdown by query type
python -c "
import json
with open('mcp_server/scripts/validation_results.json', 'r') as f:
    results = json.load(f)
    for qtype, stats in results['breakdown_by_type'].items():
        print(f'{qtype}: P@5 = {stats[\"avg_precision_at_5\"]:.4f}')
"

# Step 2: Identify which query type is failing
# Step 3: Follow "Failure (P@5 <0.70)" section above for remediation options
```

---

### Issue 4: Ground Truth Missing expected_docs

**Symptom:**

```
ERROR: Query ID 42 has no expected_docs (expected_docs is NULL or empty)
```

**Solution:**

```sql
-- Check which queries are missing expected_docs
SELECT id, query FROM ground_truth
WHERE expected_docs IS NULL OR array_length(expected_docs, 1) = 0;

-- Solution: Re-run ground truth labeling for these queries (Story 1.10-1.12)
```

---

## Post-Deployment Verification Checklist

After successful production deployment, verify:

- [ ] Precision@5 ≥0.75 (FULL SUCCESS) or ≥0.70 (PARTIAL SUCCESS)
- [ ] validation_results.json contains real data (not mock data)
- [ ] evaluation-results.md documents success level correctly
- [ ] config.yaml updated with `production_ready: true` (if FULL SUCCESS)
- [ ] sprint-status.yaml updated with `epic-2: done` (if FULL SUCCESS)
- [ ] All changes committed and pushed to remote branch
- [ ] Backup files preserved (config.yaml.backup, etc.)
- [ ] MOCK_MODE = False in validate_precision_at_5.py

---

## Estimated Timeline

| Phase | Duration | Notes |
|---|---|---|
| Prerequisites verification | 30 minutes | Database access, API keys, dependencies |
| Configuration changes | 15 minutes | Set MOCK_MODE=False, verify settings |
| Production validation execution | 2-5 minutes | 100 queries with API calls |
| Results analysis | 15 minutes | Review metrics, breakdown, success level |
| Configuration updates | 10 minutes | Update config.yaml, sprint-status.yaml |
| Commit and push | 10 minutes | Git workflow |
| **Total (FULL SUCCESS path)** | **1-2 hours** | Including verification steps |

**Partial Success:** +2 weeks for monitoring and re-calibration
**Failure:** +1-2 weeks for architecture review and remediation

---

## Cost Estimate

**OpenAI API Costs (Embeddings):**

- 100 queries × avg 50 tokens/query = 5,000 tokens
- text-embedding-3-small: $0.00002 per 1K tokens
- Total cost: ~$0.0001 × 100 = **$0.01**

**Database Costs:**

- Neon PostgreSQL: Included in existing plan (no additional cost)

**Total Deployment Cost:** ~$0.01

---

## Support and Escalation

**Questions or Issues:**

1. Review this deployment guide thoroughly
2. Check troubleshooting section for common issues
3. Review evaluation-results.md for detailed analysis
4. Consult Story 2.9 file for implementation details

**Escalation Path:**

- P@5 ≥0.70: Continue per success criteria (no escalation needed)
- P@5 <0.70: Schedule architecture review meeting within 48 hours

---

## References

- **Story 2.9 File:** `bmad-docs/stories/2-9-precision-5-validation-auf-ground-truth-set.md`
- **Validation Script:** `mcp_server/scripts/validate_precision_at_5.py`
- **Configuration:** `config.yaml` (hybrid_search_weights section)
- **Tech Spec:** `bmad-docs/tech-spec-epic-2.md` (AC-2.9.1 to AC-2.9.4)
- **NFR002:** `bmad-docs/architecture.md` (Precision@5 >0.75 requirement)

---

**Document Maintained By:** Development Team
**Last Updated:** 2025-11-16
**Next Review:** After production validation execution
