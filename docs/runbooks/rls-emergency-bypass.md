# RLS Emergency Bypass Runbook

## Purpose

This runbook documents the procedure for using the `rls_emergency_bypass` role to debug Row-Level Security (RLS) issues in the Cognitive Memory System.

**IMPORTANT**: This is an emergency debugging tool. NEVER use this role in production code.

---

## When to Use

**Use ONLY for:**
- Debugging RLS policy issues in development/staging environments
- Investigating data access problems during incidents
- Verifying data integrity across project boundaries
- Emergency troubleshooting when RLS is blocking legitimate access

**NEVER use for:**
- Production application code
- Routine data access operations
- Bypassing security for convenience
- Any automated processes

---

## How to Activate

### Prerequisites

1. **Superuser access required** - Only superusers can `SET ROLE` to `rls_emergency_bypass`
2. **Database connection** - Connect to the database as a superuser
3. **Incident ticket** - Have an incident ticket number ready for audit purposes

### Activation Steps

```sql
-- Step 1: Start a transaction (recommended for safety)
BEGIN;

-- Step 2: Activate the emergency bypass role
SET ROLE rls_emergency_bypass;

-- Step 3: Verify activation
SELECT current_role;  -- Should return: rls_emergency_bypass

-- Step 4: Run your debugging queries
-- Example: View all data across all projects
SELECT project_id, COUNT(*) FROM l2_insights GROUP BY project_id;
SELECT * FROM nodes WHERE project_id = 'some_other_project';

-- Step 5: Deactivate (see below)
RESET ROLE;

-- Step 6: Commit the transaction
COMMIT;
```

### What Happens When Active

- **All RLS policies are bypassed** - You can see data from ALL projects
- **Table permissions still apply** - You still need SELECT, INSERT, UPDATE, DELETE permissions
- **Activity is logged** - All queries are captured if `log_statement = 'all'` is configured
- **Session-scoped** - The bypass is only active for your current session

---

## How to Deactivate

### Deactivation Steps

```sql
-- Step 1: Deactivate the bypass role
RESET ROLE;

-- Step 2: Verify deactivation
SELECT current_role;  -- Should return your original username

-- Step 3: Confirm RLS is enforced again
-- Example: Set project context and verify limited visibility
SET LOCAL app.current_project = 'test_isolated';
SELECT * FROM l2_insights;  -- Should only show test_isolated data
```

### Automatic Deactivation

The bypass role is automatically deactivated when:
- You execute `RESET ROLE`
- Your session ends
- Your transaction completes (if using `SET LOCAL` patterns)

---

## Lock Timeout Procedure

For extreme cases where you need to disable RLS system-wide (LAST RESORT):

### WARNING

**Prefer `SET ROLE rls_emergency_bypass` over disabling RLS system-wide.**
Disabling RLS has blocking risks and affects ALL users.

### Procedure (LAST RESORT ONLY)

```sql
-- Step 1: Set 5-second lock timeout to prevent cascade blocking
SET lock_timeout = '5s';

-- Step 2: Attempt to disable RLS (fails if locks cannot be acquired)
ALTER TABLE l2_insights DISABLE ROW LEVEL SECURITY;

-- Step 3: Do your debugging...

-- Step 4: Re-enable RLS immediately
ALTER TABLE l2_insights ENABLE ROW LEVEL SECURITY;

-- Step 5: Reset lock timeout to default
RESET lock_timeout;
```

### Why Lock Timeout?

- **Prevents cascade blocking** - If the operation cannot acquire locks within 5 seconds, it fails
- **Protects production** - Prevents long-running blocking scenarios
- **NFR19 compliance** - Per Story 11.3.5 requirements, 5s timeout is mandatory

---

## Audit Requirements

### Incident Log Template

Every use of the emergency bypass role must be documented with the following information:

```markdown
## RLS Emergency Bypass Incident Log

### Incident Details
- **Ticket**: INC-XXXX
- **Date/Time**: YYYY-MM-DD HH:MM to YYYY-MM-DD HH:MM
- **Operator**: [Your name]
- **Reason**: [Description of the issue being debugged]

### Usage Log
1. `SET ROLE rls_emergency_bypass` at HH:MM:SS
2. [List queries executed]
   ```sql
   SELECT ...;
   ```
3. `RESET ROLE` at HH:MM:SS

### Resolution
[Describe the issue found and the resolution applied]
```

### PostgreSQL Audit Logging

Ensure the following PostgreSQL settings are configured for audit:

```postgresql
# postgresql.conf
log_statement = 'all'          # Logs all queries
log_duration = on              # Logs query duration
log_line_prefix = '%t [%p] '   # Timestamp and PID
```

### What Gets Logged

When `log_statement = 'all'` is enabled:
- All queries executed during the bypass session
- Timestamp of each query
- Session user and current role
- Query duration

---

## Security Considerations

### Role Attributes

The `rls_emergency_bypass` role has the following security attributes:

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `NOLOGIN` | ✅ Enabled | Cannot be used for direct connections |
| `BYPASSRLS` | ✅ Enabled | Bypasses all RLS policies when active |
| `PASSWORD` | ❌ None | Prevents password-based authentication |
| `GRANT` | ❌ None | Only superusers can activate by default |

### Activation Security

- **Only superusers** can `SET ROLE` to `rls_emergency_bypass` by default
- **Non-superusers** get "permission denied" if they try to activate
- **Explicit grant required** for non-superusers (emergency only):
  ```sql
  -- ONLY do this in an emergency for a specific user
  GRANT rls_emergency_bypass TO specific_user;
  -- Remember to revoke after:
  REVOKE rls_emergency_bypass FROM specific_user;
  ```

### Audit Trail

All bypass activations are logged in PostgreSQL logs when `log_statement = 'all'` is configured. This provides:
- Complete query history during bypass
- Timestamp of activation/deactivation
- Operator identification

---

## Troubleshooting

### "permission denied" when trying to SET ROLE

**Problem**: You get a permission denied error when trying to activate the bypass.

**Solution**: You must be a superuser to activate this role. Contact your database administrator.

### Role does not exist

**Problem**: `rls_emergency_bypass` role does not exist.

**Solution**: Run Migration 038 to create the role:
```bash
psql -f mcp_server/db/migrations/038_bypassrls_emergency_role.sql
```

### Cannot see all data after activation

**Problem**: You activated the bypass role but still can't see all data.

**Possible causes**:
1. **Table permissions** - You still need SELECT/INSERT/UPDATE/DELETE permissions on tables
2. **Wrong role** - Verify `SELECT current_role` returns `rls_emergency_bypass`
3. **System catalogs** - Some system tables have their own access controls

---

## Testing

After using the bypass role, verify normal RLS behavior is restored:

```sql
-- Step 1: Deactivate bypass
RESET ROLE;

-- Step 2: Set project context
SET LOCAL app.current_project = 'test_isolated';

-- Step 3: Verify limited visibility
SELECT project_id, COUNT(*) FROM l2_insights;
-- Should only show data for test_isolated project
```

---

## Related Documentation

- **Story 11.3.5**: BYPASSRLS Emergency Role implementation
- **Story 11.3.1**: RLS Helper Functions (set_project_context, get_rls_mode)
- **Story 11.3.3**: RLS Policies for Core Tables
- **Story 11.3.4**: RLS Policies for Support Tables
- **Migration 038**: `mcp_server/db/migrations/038_bypassrls_emergency_role.sql`

---

## Contact

For questions or issues related to the RLS emergency bypass:
- **Database Team**: [Contact information]
- **On-Call Engineer**: [Contact information]
- **Incident Response**: [Contact information]

---

*Last Updated: 2026-01-23*
*Story: 11.3.5 - BYPASSRLS Emergency Role*
