# RLS Migration Runbook

**Story:** 11.8.1 - Migration Scripts und Tooling
**Purpose:** Safe, phased migration of all projects to RLS enforcement

## Overview

This runbook documents the step-by-step procedure for migrating projects through RLS phases:
1. **pending** - Legacy behavior (no RLS enforcement)
2. **shadow** - Audit-only mode (log violations, no blocking)
3. **enforcing** - RLS active (blocks unauthorized access)
4. **complete** - Migration stable

## Prerequisites

- [x] Epic 11.1-11.7 complete (all RLS infrastructure in place)
- [x] Database backups current
- [x] Monitoring configured (check_shadow_violations.py)
- [x] Rollback procedure tested

## Migration Sequence

### Batch 1: Isolated Minimal Projects

**Projects:** `sm`

```bash
# Move to shadow phase
python scripts/migrate_project.py --project sm --phase shadow

# Monitor for 7-14 days
python scripts/check_shadow_violations.py --project sm

# After 0 violations for 7+ days, proceed to enforcing
python scripts/migrate_project.py --project sm --phase enforcing

# Verify isolation test passes (create test suite if needed)
# pytest tests/e2e/test_rls_validation_suite.py -k test_isolation

# Mark complete
python scripts/migrate_project.py --project sm --phase complete
```

### Batch 2: Isolated Projects

**Projects:** `motoko`

Same procedure as Batch 1.

### Batch 3: Shared Projects

**Projects:** `ab`, `aa`, `bap`

```bash
# Batch migrate to shadow
python scripts/migrate_project.py --batch "ab,aa,bap" --phase shadow

# Monitor each project individually
python scripts/check_shadow_violations.py --project ab
python scripts/check_shadow_violations.py --project aa
python scripts/check_shadow_violations.py --project bap

# Proceed to enforcing only when ALL have 0 violations
python scripts/migrate_project.py --batch "ab,aa,bap" --phase enforcing

# Verify shared access tests pass (create test suite if needed)
# pytest tests/e2e/test_rls_validation_suite.py -k test_shared_access
```

### Batch 4: Super Projects

**Projects:** `echo`, `ea`

Super projects can see all data. Verify isolation still works for their data.

### Batch 5: Legacy Owner

**Projects:** `io`

**CRITICAL:** `io` is the legacy owner of all existing data. Exercise extreme caution.

```bash
# Shadow phase (extended monitoring: 14 days)
python scripts/migrate_project.py --project io --phase shadow

# Daily violation checks
python scripts/check_shadow_violations.py --project io

# After 14 days with 0 violations, proceed
python scripts/migrate_project.py --project io --phase enforcing
```

## Exit Criteria

A project can transition from **shadow** to **enforcing** when ALL criteria are met:

| Criterion | Threshold | Measurement |
|-----------|-----------|-------------|
| Minimum Duration | >= 7 days | `updated_at` timestamp in shadow phase |
| Minimum Transactions | >= 1000 tool calls | Count from application logs |
| Violation Count | = 0 | `SELECT COUNT(*) FROM rls_audit_log WHERE would_be_denied = TRUE` |
| False Positive Review | 100% reviewed | All logged items analyzed |

## Rollback Procedure

If issues occur during enforcing phase:

```bash
# Emergency rollback to pending
python scripts/migrate_project.py --project <project_id> --phase pending

# Verify legacy behavior restored
python scripts/migration_status.py

# Investigate issue in logs
# Fix issue in code or permissions

# Retry migration
python scripts/migrate_project.py --project <project_id> --phase shadow
```

## Troubleshooting

### High Violation Count in Shadow Phase

1. Run `check_shadow_violations.py --project <id>` for detailed breakdown
2. Identify root cause: missing permissions, incorrect project_id in queries, etc.
3. Fix root cause (code change or permission update)
4. **RESET shadow timer** - violations must be 0 for 7 consecutive days after fix

### Project Not Found Error

Verify project exists in `project_registry`:
```sql
SELECT * FROM project_registry WHERE project_id = '<id>';
```

### Transaction Rollback in Batch Mode

Batch migrations use transactions. If one project fails, entire batch rolls back.
Re-run with only valid projects or fix invalid project_id first.

## Validation Tests

After each enforcing transition, run validation suite:

```bash
# Create test suite if needed
# pytest tests/e2e/test_rls_validation_suite.py -v
pytest tests/integration/test_migration_scripts.py -v
```

All tests must pass before marking migration complete.
