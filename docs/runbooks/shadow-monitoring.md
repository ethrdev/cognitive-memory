# Shadow Phase Monitoring Runbook

**Story:** 11.8.2 - Shadow Phase Execution und Monitoring
**Purpose:** Monitor shadow phase and determine eligibility for enforcing phase

## Overview

Shadow phase is a CRITICAL safety mechanism where RLS policies log would-be violations without blocking. This runbook documents the monitoring procedures and exit criteria for transitioning to enforcing phase.

## Exit Criteria

A project can transition from **shadow** to **enforcing** when ALL criteria are met:

| Criterion | Threshold | Measurement |
|-----------|-----------|-------------|
| Minimum Duration | >= 7 days | `updated_at` timestamp in shadow phase |
| Minimum Transactions | >= 1000 tool calls | Count from `rls_audit_log` |
| Violation Count | = 0 | `SELECT COUNT(*) FROM rls_audit_log WHERE would_be_denied = TRUE` |
| False Positive Review | 100% reviewed | All logged items analyzed |

## Daily Monitoring Procedure

### 1. Generate Shadow Phase Report

```bash
python scripts/shadow_phase_report.py
```

**Review:**
- Days in shadow for each project
- Transaction count (should increase daily)
- Violation count (should be 0)
- Eligibility status

### 2. Check Duration Thresholds

```bash
python scripts/check_shadow_duration.py
```

**Alert if:** Any project >14 days in shadow phase

### 3. Check for Violations

```bash
python scripts/check_shadow_violations.py
```

**If violations found:** Investigate immediately (see Violation Analysis below)

## Violation Analysis Workflow

When violations are detected:

### Step 1: Get Detailed Violation Report

```bash
python scripts/check_shadow_violations.py --project <project_id>
```

### Step 2: Categorize Violation Type

**True Positive (real access issue):**
- Application code needs fix
- ACL permissions need adjustment
- Create issue/PR for fix

**False Positive (expected access):**
- Document rationale in `docs/migration_decisions.md`
- Update RLS policy if needed

### Step 3: Resolution

**True Positive:**
1. Create PR for code fix
2. Test fix in development
3. Merge PR
4. **RESET shadow timer** - phase transition must restart

**False Positive:**
1. Document finding with rationale
2. Create issue for policy review
3. May proceed if deemed acceptable

### Step 4: Shadow Timer Reset

After ANY code or permission change:

```bash
# Reset shadow phase to restart timer
python scripts/migrate_project.py --project <id> --phase shadow
```

**IMPORTANT:** The 7-day minimum restarts after any change affecting RLS behavior.

## Migration Sequence

### Batch 1: sm (isolated, minimal)

```bash
# Activate shadow phase
python scripts/migrate_project.py --project sm --phase shadow

# Daily monitoring
python scripts/shadow_phase_report.py --project sm

# After 7+ days with 0 violations and 1000+ transactions
python scripts/migrate_project.py --project sm --phase enforcing
```

### Batch 2: motoko (isolated)

Same procedure as Batch 1.

### Batch 3: ab, aa, bap (shared)

```bash
# Batch activate shadow
python scripts/migrate_project.py --batch "ab,aa,bap" --phase shadow

# Monitor each project individually
python scripts/shadow_phase_report.py
python scripts/check_shadow_violations.py

# ALL projects must be eligible before proceeding
python scripts/migrate_project.py --batch "ab,aa,bap" --phase enforcing
```

### Batch 4: echo, ea (super)

Super projects can see all data. Verify isolation still works.

### Batch 5: io (legacy owner)

**CRITICAL:** Extended monitoring (14 days minimum)

```bash
# Activate shadow phase
python scripts/migrate_project.py --project io --phase shadow

# Extended daily monitoring (14+ days)
python scripts/shadow_phase_report.py --project io

# After 14+ days with 0 violations
python scripts/migrate_project.py --project io --phase enforcing
```

## Escalation Paths

### Shadow Phase >14 Days

**If project exceeds 14 days in shadow:**

1. Run `check_shadow_duration.py` to identify
2. Review `docs/migration_decisions.md` for documentation
3. If no violations - proceed to enforcing within 3 business days
4. If violations - create blocker issue for resolution

### Recurring Violations

**If violations persist >48 hours:**

1. Escalate to engineering lead
2. Consider RLS policy adjustment
3. Document decision in `docs/migration_decisions.md`

## Migration Decisions Document

Track all migration decisions in `docs/migration_decisions.md`:

```markdown
## sm (ISOLATED)

**Shadow Started:** 2026-01-24
**Eligibility Date:** 2026-01-31 (7 days)

**Violations:** None

**Decision:** ELIGIBLE for enforcing phase
**Approved By:** @devops
**Enforcing Date:** 2026-01-31

## aa (SHARED)

**Shadow Started:** 2026-01-26
**Violations Found:** 3 on 2026-01-28

**Root Cause:** Missing ACL permission for aa -> sm
**Resolution:** Migration applied to add permission
**Shadow Reset:** 2026-01-28

**New Eligibility Date:** 2026-02-04 (7 days after reset)
```

## Rollback Procedure

If issues occur during shadow phase:

```bash
# Rollback to pending
python scripts/migrate_project.py --project <id> --phase pending

# Fix issue

# Restart shadow phase
python scripts/migrate_project.py --project <id> --phase shadow
```

## Validation

After transitioning to enforcing:

1. Run isolation tests
2. Verify application functionality
3. Monitor production for 24 hours
4. Mark migration complete if all checks pass
