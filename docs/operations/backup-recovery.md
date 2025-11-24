# Backup & Recovery Guide

Disaster recovery procedures with RTO <1h and RPO <24h.

## Overview

This documentation describes the backup and recovery strategy for the Cognitive Memory PostgreSQL database. The strategy fulfills NFR004 (Disaster Recovery) with RTO <1h and RPO <24h.

### Backup Approach

| Type | Provider | Schedule | Retention |
|------|----------|----------|-----------|
| Neon Automatic | Neon Cloud | Continuous (PITR) | 7-30 days |
| Manual pg_dump | Both | On-demand | User-managed |
| L2 Insights Export | Both | Optional | Git versioned |

---

## Neon Cloud Backup (Recommended)

Neon provides automatic, continuous backups with Point-in-Time Recovery (PITR).

### Built-in Features

- **Automatic backups**: No configuration required
- **PITR**: Restore to any point within retention window
- **Branching**: Create instant database copies for testing
- **Retention**: 7 days (free tier), 30 days (paid tiers)

### Point-in-Time Recovery

1. Go to [console.neon.tech](https://console.neon.tech)
2. Select your project
3. Click **"Branches"** → **"Create branch"**
4. Choose **"From a point in time"**
5. Select the timestamp to restore to

### Manual Backup (Neon)

For additional safety or migration purposes:

```bash
# Export database dump
pg_dump "$DATABASE_URL" -Fc > backup_$(date +%Y%m%d).dump

# Verify backup
pg_restore --list backup_$(date +%Y%m%d).dump | head -20

# Export as SQL (for version control)
pg_dump "$DATABASE_URL" --schema-only > schema_backup.sql
```

### Restore from Manual Backup (Neon)

```bash
# Create new branch in Neon Console, then restore
pg_restore -d "$NEW_DATABASE_URL" backup_YYYYMMDD.dump

# Or restore specific tables
pg_restore -t l2_insights -d "$DATABASE_URL" backup.dump
```

---

## Local PostgreSQL Backup (Alternative)

For local PostgreSQL installations.

### Daily PostgreSQL Backups

```bash
# Automated backup script location
/usr/local/bin/backup_cognitive_memory.sh

# Manual backup
sudo -u postgres pg_dump -Fc cognitive_memory > \
  /backups/postgres/cognitive_memory_$(date +%Y%m%d).dump

# Verify backup
pg_restore --list /backups/postgres/cognitive_memory_latest.dump | head -20
```

### Backup Rotation

```bash
# List backups
ls -lah /backups/postgres/

# Cleanup old backups (>7 days)
find /backups/postgres/ -name "*.dump" -mtime +7 -delete
```

### Full Database Restore (Local)

**RTO: <1 hour**

```bash
# 1. Stop MCP server
sudo systemctl stop cognitive-memory-mcp

# 2. Drop and recreate database
sudo -u postgres dropdb cognitive_memory
sudo -u postgres createdb cognitive_memory
sudo -u postgres psql -d cognitive_memory -c "CREATE EXTENSION vector;"

# 3. Restore from backup
sudo -u postgres pg_restore -d cognitive_memory \
  /backups/postgres/cognitive_memory_YYYYMMDD.dump

# 4. Verify restore
psql -U mcp_user -d cognitive_memory -c "\dt"

# 5. Restart MCP server
sudo systemctl start cognitive-memory-mcp
```

---

## Recovery Procedures

### Partial Recovery (Single Table)

**For Neon Cloud:**
```bash
# Extract specific table from backup
pg_restore -t l2_insights backup.dump > l2_insights.sql

# Restore single table
psql "$DATABASE_URL" -f l2_insights.sql
```

**For Local PostgreSQL:**
```bash
# Extract specific table
pg_restore -t l2_insights /backups/postgres/backup.dump > l2_insights.sql

# Restore single table
psql -U mcp_user -d cognitive_memory -f l2_insights.sql
```

### Embedding Re-generation

If only L2 content is available (without embeddings):

```bash
# Re-generate embeddings for all L2 insights
python -c "
from mcp_server.utils.embedding_regenerator import regenerate_all_embeddings
result = regenerate_all_embeddings()
print(f'Regenerated {result[\"count\"]} embeddings')
"
```

---

## Verification Checklist

After recovery, verify:

**For Neon Cloud:**
- [ ] Database accessible: `psql "$DATABASE_URL" -c "SELECT 1;"`
- [ ] All tables present: `psql "$DATABASE_URL" -c "\dt"`
- [ ] pgvector extension active: `SELECT extversion FROM pg_extension WHERE extname='vector';`
- [ ] MCP server connects: `python -m mcp_server` (test startup)
- [ ] Ping test passes: Run MCP tool `ping`

**For Local PostgreSQL:**
- [ ] PostgreSQL service running: `systemctl status postgresql`
- [ ] All tables present: `psql -c "\dt"`
- [ ] pgvector extension active: `SELECT extversion FROM pg_extension WHERE extname='vector';`
- [ ] MCP server connects: `systemctl status cognitive-memory-mcp`
- [ ] Ping test passes: Run MCP tool `ping`

---

## Monitoring

### Backup Health (Neon Cloud)

```bash
# Check connection
psql "$DATABASE_URL" -c "SELECT NOW();"

# View recent data
psql "$DATABASE_URL" -c "SELECT MAX(created_at) FROM l2_insights;"

# Neon Console: Check "Usage" tab for storage metrics
```

### Backup Health (Local)

```bash
# Check last backup
ls -la /backups/postgres/ | tail -3

# Verify backup integrity
pg_restore --list /backups/postgres/latest.dump > /dev/null && echo "OK"
```

### Cron Job Status (Local)

```bash
# View backup cron job
crontab -l | grep backup

# Check cron logs
journalctl -u cronie --since "24h" | grep backup
```

---

## Recovery Metrics

| Metric | Neon Cloud | Local PostgreSQL |
|--------|------------|------------------|
| RTO | <15 min (PITR) | <1 hour |
| RPO | Near-zero (continuous) | <24 hours |
| Backup Size | Managed by Neon | ~500MB-2GB |
| Restore Time | <5 min (branch) | 5-30 min |

---

## Migration Between Providers

### From Local to Neon

```bash
# 1. Export from local
sudo -u postgres pg_dump -Fc cognitive_memory > migration.dump

# 2. Create Neon project and get connection string

# 3. Restore to Neon
pg_restore -d "$NEON_DATABASE_URL" migration.dump

# 4. Update .env.development with new DATABASE_URL
```

### From Neon to Local

```bash
# 1. Export from Neon
pg_dump "$NEON_DATABASE_URL" -Fc > migration.dump

# 2. Restore to local
sudo -u postgres pg_restore -d cognitive_memory migration.dump

# 3. Update .env.development with local DATABASE_URL
```
