# Migration Tests Guide - Cognitive Memory

## Overview

This guide explains how to run migration tests for cognitive-memory database migrations.

## Problem

Integration tests that depend on database migrations will **FAIL** if the migrations haven't been applied to the test database. The error will look like:

```
psycopg2.errors.UndefinedColumn: column "memory_strength" does not exist
```

## Solution

### Option 1: Run Tests Against Production Database (Not Recommended)

```bash
# Set DATABASE_URL to production database
export DATABASE_URL="postgresql://..."

# Run tests
pytest tests/integration/test_023_migration.py -v
```

⚠️ **WARNING**: This modifies your production database! Only use this if you know what you're doing.

### Option 2: Create Test Database (Recommended)

#### Step 1: Create a Test Database

```bash
# Using PostgreSQL
createdb cognitive_memory_test

# Or using Neon Console
# Create a new project named "cognitive-memory-test"
```

#### Step 2: Set Environment Variables

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/cognitive_memory_test"
# Or for Neon:
export DATABASE_URL="postgresql://user:pass@ep-xxx.aws.neon.tech/cognitive_memory_test?sslmode=require"
```

#### Step 3: Run All Migrations

```bash
# Option A: Run migrations manually
psql $DATABASE_URL -f mcp_server/db/migrations/001_initial_schema.sql
psql $DATABASE_URL -f mcp_server/db/migrations/023_memory_strength.sql

# Option B: Use a migration runner (if you have one)
python -m mcp_server.db.run_migrations
```

#### Step 4: Run Tests

```bash
# Run specific migration test
pytest tests/integration/test_023_migration.py -v

# Run all integration tests
pytest tests/integration/ -v
```

### Option 3: Docker Test Database (Best for CI/CD)

Create `docker-compose.test.yml`:

```yaml
version: '3.8'
services:
  postgres-test:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass
      POSTGRES_DB: cognitive_memory_test
    ports:
      - "5433:5432"
```

Run tests:

```bash
# Start test database
docker-compose -f docker-compose.test.yml up -d

# Export DATABASE_URL
export DATABASE_URL="postgresql://test_user:test_pass@localhost:5433/cognitive_memory_test"

# Run migrations and tests
psql $DATABASE_URL -f mcp_server/db/migrations/001_initial_schema.sql
psql $DATABASE_URL -f mcp_server/db/migrations/023_memory_strength.sql

pytest tests/integration/test_023_migration.py -v

# Cleanup
docker-compose -f docker-compose.test.yml down
```

## Current Migration Tests Status

### Migration 023 (memory_strength)

**Status**: ⚠️ **BLOCKED** - Needs test database setup

**Test Files**:
- `tests/integration/test_023_migration.py` - Migration Up/Down/Up cycle tests
- `tests/integration/test_compress_memory_strength.py` - Integration tests with real DB
- `tests/integration/test_regression_26_1.py` - Backward compatibility tests

**To Run**:

```bash
# 1. Set up test database
createdb cognitive_memory_test
export DATABASE_URL="postgresql://user:pass@localhost:5432/cognitive_memory_test"

# 2. Run migrations
psql $DATABASE_URL -f mcp_server/db/migrations/001_initial_schema.sql
psql $DATABASE_URL -f mcp_server/db/migrations/023_memory_strength.sql

# 3. Run tests
pytest tests/integration/test_023_migration.py -v
pytest tests/integration/test_compress_memory_strength.py -v
pytest tests/integration/test_regression_26_1.py -v
```

## Troubleshooting

### Error: "column does not exist"

**Cause**: Migration not applied to test database

**Fix**: Run the migration SQL file against your test database

```bash
psql $DATABASE_URL -f mcp_server/db/migrations/023_memory_strength.sql
```

### Error: "connection refused"

**Cause**: Database not running or wrong port

**Fix**: Check database is running and DATABASE_URL is correct

```bash
# Check PostgreSQL is running
pg_isready

# For Docker
docker ps | grep postgres
```

### Error: "FATAL: database \"cognitive_memory_test\" does not exist"

**Cause**: Test database not created

**Fix**: Create the database

```bash
createdb cognitive_memory_test
```

## CI/CD Integration

For GitHub Actions, add to `.github/workflows/test.yml`:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    env:
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass
      POSTGRES_DB: cognitive_memory_test
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5

env:
  DATABASE_URL: postgresql://test_user:test_pass@localhost:5432/cognitive_memory_test

steps:
  - name: Run migrations
    run: |
      psql $DATABASE_URL -f mcp_server/db/migrations/001_initial_schema.sql
      psql $DATABASE_URL -f mcp_server/db/migrations/023_memory_strength.sql

  - name: Run integration tests
    run: pytest tests/integration/ -v
```

## Migration Testing Best Practices

1. **Always use a separate test database** - Never run migration tests against production
2. **Clean up after tests** - Drop test database or use transactions that roll back
3. **Test both Up and Down migrations** - Ensure rollbacks work
4. **Test idempotency** - Migration should work if run multiple times
5. **Verify data migration** - Check that existing data is correctly migrated
6. **Test edge cases** - Empty tables, NULL values, existing data

## Quick Reference

```bash
# Full test workflow
export DATABASE_URL="postgresql://user:pass@localhost:5432/cognitive_memory_test"
psql $DATABASE_URL -f mcp_server/db/migrations/001_initial_schema.sql
psql $DATABASE_URL -f mcp_server/db/migrations/023_memory_strength.sql
pytest tests/integration/test_023_migration.py -v

# Unit tests (no database required)
pytest tests/unit/test_memory_strength.py -v

# All tests (requires database setup)
pytest tests/ -v
```

## Related Documentation

- [Migration Pattern Reference](../../mcp_server/db/migrations/022_add_memory_sector.sql)
- [Story 26.1](../../../bmad-docs/sprint-artifacts/26-1-memory-strength.md)
- [Architecture Decisions](../../../bmad-docs/architecture.md#AD-3-Test-Strategy)
