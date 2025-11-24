# Backup & Recovery Guide

Disaster recovery procedures with RTO <1h and RPO <24h.

## Overview

This documentation describes the backup and recovery strategy for the Cognitive Memory PostgreSQL database. The strategy fulfills NFR004 (Disaster Recovery) with RTO <1h and RPO <24h.

### Backup Approach

| Type | Schedule | Format | Retention |
|------|----------|--------|-----------|
| PostgreSQL pg_dump | Daily 03:00 | Custom (-Fc) | 7 days |
| L2 Insights Export | Optional | JSON/Text | Git versioned |

## Backup Strategy

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

## Recovery Procedures

### Full Database Restore

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

### Partial Recovery (Single Table)

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

## Verification Checklist

After recovery, verify:

- [ ] PostgreSQL service running: `systemctl status postgresql`
- [ ] All tables present: `psql -c "\dt"`
- [ ] pgvector extension active: `SELECT extversion FROM pg_extension WHERE extname='vector';`
- [ ] MCP server connects: `systemctl status cognitive-memory-mcp`
- [ ] Ping test passes: Run MCP tool `ping`

## Monitoring

### Backup Health

```bash
# Check last backup
ls -la /backups/postgres/ | tail -3

# Verify backup integrity
pg_restore --list /backups/postgres/latest.dump > /dev/null && echo "OK"
```

### Cron Job Status

```bash
# View backup cron job
crontab -l | grep backup

# Check cron logs
journalctl -u cronie --since "24h" | grep backup
```

## Recovery Metrics

| Metric | Target | Procedure |
|--------|--------|-----------|
| RTO | <1 hour | Full pg_restore |
| RPO | <24 hours | Daily backups |
| Backup Size | ~500MB-2GB | Compressed format |
| Restore Time | 5-30 min | Depends on size |
