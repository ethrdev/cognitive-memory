# Enforcing Phase Activation Runbook

**Story:** 11.8.3 - Enforcing Phase Activation und Validation
**Purpose:** Activate enforcing phase for all projects and validate namespace isolation

## Overview

Enforcing phase is the FINAL stage of RLS migration where Row-Level Security policies actively block unauthorized access. This runbook documents the activation procedure, validation steps, and rollback process.

## Prerequisites

Before activating enforcing for ANY project, verify:

1. **Zero Violations:** `SELECT COUNT(*) FROM rls_audit_log WHERE would_be_denied = TRUE` = 0
2. **Minimum Duration:** >= 7 days in shadow phase
3. **Minimum Transactions:** >= 1000 tool calls processed
4. **Exit Criteria Validated:** All shadow phase exit criteria met

## Activation Procedure

### Step 1: Verify Eligibility

```bash
# Check eligibility for a single project
python scripts/activate_enforcing.py --project <project_id> --dry-run

# Check eligibility for multiple projects
python scripts/activate_enforcing.py --batch "sm,motoko" --dry-run
```

**Expected Output:**
- Shadow duration: >= 7 days
- Transactions: >= 1000
- Violations: 0
- Status: ✓ ELIGIBLE

### Step 2: Activate Enforcing Phase

**Single Project:**
```bash
python scripts/activate_enforcing.py --project <project_id>
```

**Batch Activation (recommended for low-risk projects):**
```bash
python scripts/activate_enforcing.py --batch "sm,motoko"
```

### Step 3: Validate Isolation

After activation, run the validation test suite:

```bash
# Run E2E validation tests
uv run pytest tests/e2e/test_rls_validation_suite.py -v
```

**Critical Tests:**
1. Isolation Test: Projects see only their own data
2. Super-User Test: Super can read all, not write others
3. Collision Test: Same-name nodes work across projects
4. Write-Protection Test: Cross-project writes blocked
5. Gradual-Rollout Test: Phase transitions work

## Migration Sequence (Risk-Based)

### Batch 1: sm (LOW risk - isolated, minimal)

```bash
# Step 1: Check eligibility
python scripts/activate_enforcing.py --project sm --dry-run

# Step 2: Activate enforcing
python scripts/activate_enforcing.py --project sm

# Step 3: Run validation
uv run pytest tests/e2e/test_rls_validation_suite.py -k "test_isolation_by_project" -v

# Step 4: Monitor for 24 hours before proceeding
```

### Batch 2: motoko (LOW risk - isolated)

Same procedure as Batch 1.

### Batch 3: ab, aa, bap (MEDIUM risk - shared)

```bash
# Step 1: Check eligibility for all
for proj in ab aa bap; do
    python scripts/activate_enforcing.py --project $proj --dry-run
done

# Step 2: Batch activate
python scripts/activate_enforcing.py --batch "ab,aa,bap"

# Step 3: Validate cross-project isolation
uv run pytest tests/e2e/test_rls_validation_suite.py -k "test_write_protection" -v
```

### Batch 4: echo, ea (MEDIUM risk - super)

```bash
# Step 1: Check eligibility
python scripts/activate_enforcing.py --batch "echo,ea" --dry-run

# Step 2: Activate
python scripts/activate_enforcing.py --batch "echo,ea"

# Step 3: Validate super-user behavior
uv run pytest tests/e2e/test_rls_validation_suite.py -k "test_super_user" -v
```

### Batch 5: io (HIGH risk - super, legacy)

```bash
# Step 1: Check eligibility (EXTENDED validation)
python scripts/activate_enforcing.py --project io --dry-run

# Step 2: Activate with extra monitoring
python scripts/activate_enforcing.py --project io

# Step 3: Extended validation
uv run pytest tests/e2e/test_rls_validation_suite.py -v

# Step 4: Monitor production for 48 hours
```

## Rollback Procedure

### Emergency Rollback

If issues are detected in enforcing phase:

```bash
# Immediate rollback to pending (stops blocking within 1 minute)
python scripts/activate_enforcing.py --project <project_id> --rollback

# Batch rollback
python scripts/activate_enforcing.py --batch "sm,motoko" --rollback
```

### Rollback Scenarios

**Scenario 1: Application Error**
- Symptom: 5xx errors, timeout increases
- Action: Rollback to pending immediately
- Investigation: Check logs for RLS policy violations

**Scenario 2: Data Not Visible**
- Symptom: Users report missing data
- Action: Rollback to pending, check ACL permissions
- Resolution: Fix ACL, restart shadow phase

**Scenario 3: Performance Degradation**
- Symptom: Latency increases >20ms
- Action: Run performance comparison
- Resolution: If overhead >10ms, rollback and investigate

## BYPASSRLS Role Usage

For debugging when RLS blocks legitimate access:

```sql
-- Set bypass role (requires TEST_BYPASS_DSN or admin access)
SET ROLE bypassrls;

-- Perform investigation
SELECT * FROM nodes WHERE project_id = 'other-project';

-- Reset role
RESET ROLE;
```

**Use Cases:**
- Investigating data visibility issues
- Verifying data exists during troubleshooting
- Emergency data access while fixing permissions

## Validation Checklist

After each batch activation:

- [ ] Eligibility verified (0 violations, >=7 days, >=1000 tx)
- [ ] Enforcing activated successfully
- [ ] Isolation Test: hybrid_search returns only accessible data
- [ ] Super-User Test: super can read all, not write others
- [ ] Collision Test: same-name nodes work across projects
- [ ] Write-Protection Test: cross-project writes blocked
- [ ] Performance validated: <10ms overhead
- [ ] Application monitoring: no errors for 24 hours

## Performance Validation

### Run Performance Comparison

```bash
# Compare enforcing performance against Story 11.1.0 baseline
python scripts/performance_comparison.py --output tests/performance/enforcing_comparison_report.json
```

**NFR2 Threshold:** RLS overhead must be <10ms

### Acceptable Overhead

| Query | Baseline p99 | Enforcing p99 | Overhead | Status |
|-------|-------------|---------------|----------|--------|
| hybrid_search | ~X ms | ~Y ms | <10ms | ✅ PASS |
| graph_query_neighbors | ~X ms | ~Y ms | <10ms | ✅ PASS |

## Troubleshooting

### Issue: Activation Fails with "Not Eligible"

**Diagnosis:**
```bash
python scripts/activate_enforcing.py --project <id> --dry-run
```

**Common Causes:**
1. Insufficient shadow duration (<7 days) → Wait and retry
2. Insufficient transactions (<1000) → Wait and retry
3. Violations detected → Investigate with check_shadow_violations.py

### Issue: Validation Tests Fail

**Isolation Test Fails:**
```bash
# Check project context is set correctly
# Check RLS policies are active
SELECT project_id, migration_phase FROM rls_migration_status;

# Verify ACL entries
SELECT * FROM project_read_permissions WHERE project_id = '<id>';
```

**Write-Protection Test Fails:**
```sql
-- Verify RLS policies are enforcing
SELECT tablename, policyname, permissive
FROM pg_policies
WHERE tablename IN ('nodes', 'edges', 'l2_insights');
```

### Issue: Performance Exceeds Threshold

```bash
# Run detailed performance analysis
python scripts/performance_comparison.py

# Check PostgreSQL query plans
EXPLAIN ANALYZE SELECT * FROM nodes WHERE project_id = 'test';
```

### Issue: Performance Comparison Fails

**Baseline File Not Found:**
```bash
# Error: Baseline file not found
# Solution: Run Story 11.1.0 baseline capture first
python tests/performance/capture_baseline.py
```

**Query Name Mismatch:**
```bash
# Error: No baseline found for graph_query_neighbors
# Solution: Ensure baseline uses correct query names:
# - graph_query_neighbors_1hop (for 1-hop queries)
# - graph_query_neighbors_3hop (for 3-hop queries)
# - hybrid_search_semantic_top10 (for hybrid search)
```

**Hybrid Search Skipped:**
```bash
# Error: hybrid_search skipped due to missing OPENAI_API_KEY
# Solution: Configure OpenAI API key for baseline capture
export OPENAI_API_KEY="your-api-key-here"
python tests/performance/capture_baseline.py
```

## Migration Completion

After ALL batches are activated and validated:

```bash
# Step 1: Run final validation suite
uv run pytest tests/e2e/test_rls_validation_suite.py -v

# Step 2: Run performance comparison
python scripts/performance_comparison.py

# Step 3: Mark all projects as complete
python scripts/migrate_project.py --batch "sm,motoko,ab,aa,bap,echo,ea,io" --phase complete

# Step 4: Update Epic 11 status
# Update sprint-status.yaml: epic-11-8 -> done
```

## Success Criteria

Epic 11 is COMPLETE when:

- [ ] All projects in enforcing phase
- [ ] All E2E validation tests pass
- [ ] Performance overhead <10ms (NFR2)
- [ ] Zero production RLS violations for 7 days
- [ ] Rollback procedure tested and documented
- [ ] Epic 11 retrospective completed

## References

- **Story 11.8.2:** Shadow Phase Monitoring Runbook
- **Story 11.1.0:** Performance Baseline Capture
- **Epic 11:** Namespace-Isolation für Multi-Project Support
- **Migration Script:** scripts/activate_enforcing.py
- **Validation Suite:** tests/e2e/test_rls_validation_suite.py
