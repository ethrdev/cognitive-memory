# Operations Manual

Daily operations and maintenance guide for the Cognitive Memory System.

## Service Management

### MCP Server Service

The MCP Server runs as a systemd service for automatic startup and restart.

```bash
# Check status
systemctl status cognitive-memory-mcp

# Start/stop/restart
sudo systemctl start cognitive-memory-mcp
sudo systemctl stop cognitive-memory-mcp
sudo systemctl restart cognitive-memory-mcp

# Enable auto-start
sudo systemctl enable cognitive-memory-mcp

# View logs
journalctl -u cognitive-memory-mcp -f           # Live logs
journalctl -u cognitive-memory-mcp --since "1h" # Last hour
journalctl -u cognitive-memory-mcp -p err       # Errors only
```

### Health Checks

```bash
# Service status
systemctl is-active cognitive-memory-mcp

# Process check
ps aux | grep "python -m mcp_server"

# Memory usage
systemctl show cognitive-memory-mcp --property=MemoryCurrent
```

## Backup Operations

### Daily Backups

Backups run automatically at 03:00 with 7-day retention.

```bash
# Manual backup
sudo -u postgres pg_dump -Fc cognitive_memory > \
  /backups/postgres/cognitive_memory_$(date +%Y%m%d).dump

# List backups
ls -lah /backups/postgres/

# Verify backup integrity
sudo -u postgres pg_restore --list /backups/postgres/latest.dump | head -20

# Cleanup old backups (>7 days)
find /backups/postgres/ -name "*.dump" -mtime +7 -delete
```

### Restore Procedure

```bash
# Stop MCP server
sudo systemctl stop cognitive-memory-mcp

# Restore database
sudo -u postgres pg_restore -d cognitive_memory --clean /backups/postgres/backup.dump

# Restart server
sudo systemctl start cognitive-memory-mcp
```

## Model Drift Detection

### Daily Golden Test

Run daily to detect model drift (Precision@5 drop >5%).

```bash
# Via Claude Code
# Run MCP tool: get_golden_test_results

# Expected output:
# {
#   "date": "2025-01-15",
#   "precision_at_5": 0.78,
#   "drift_detected": false,
#   "baseline_precision": 0.82
# }
```

### Drift History

```sql
SELECT date, precision_at_5, drift_detected, baseline_precision
FROM model_drift_log
ORDER BY date DESC
LIMIT 10;
```

### Drift Statistics

```sql
SELECT
    COUNT(*) as total_checks,
    COUNT(CASE WHEN drift_detected THEN 1 END) as drift_count,
    AVG(precision_at_5) as avg_precision,
    MIN(precision_at_5) as min_precision
FROM model_drift_log
WHERE date >= CURRENT_DATE - INTERVAL '30 days';
```

## Budget Monitoring

### CLI Dashboard

```bash
# Interactive dashboard
python -m mcp_server.budget dashboard

# Quick status
python -m mcp_server.budget status

# Cost breakdown by API
python -m mcp_server.budget breakdown --days 30

# Monthly projection
python -m mcp_server.budget projection
```

### Cost Analysis

```sql
SELECT
    api_name,
    SUM(num_calls) as total_calls,
    SUM(tokens) as total_tokens,
    SUM(cost_eur) as total_cost
FROM api_cost_log
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY api_name
ORDER BY total_cost DESC;
```

### Budget Thresholds

| Level | Threshold | Action |
|-------|-----------|--------|
| Normal | <$8/mo | No action |
| Warning | $8/mo | Review usage |
| Critical | $10/mo | Reduce API calls |

## Ground Truth Maintenance

### Streamlit UI

```bash
# Start labeling interface
streamlit run streamlit_apps/ground_truth_app.py

# With custom port
streamlit run streamlit_apps/ground_truth_app.py --server.port 8501
```

### Ground Truth Statistics

```sql
SELECT
    COUNT(*) as total_queries,
    COUNT(CASE WHEN judge1_score IS NOT NULL THEN 1 END) as judged,
    AVG(kappa_score) as avg_kappa
FROM ground_truth;
```

### IRR Report

```sql
SELECT
    DATE_TRUNC('week', created_at) as week,
    COUNT(*) as queries,
    AVG(kappa_score) as avg_kappa
FROM ground_truth
WHERE judge1_score IS NOT NULL
GROUP BY week
ORDER BY week DESC
LIMIT 8;
```

## Memory Management

### Working Memory

```sql
-- Current items
SELECT COUNT(*) FROM working_memory;

-- Oldest items
SELECT content, importance, last_accessed
FROM working_memory
ORDER BY last_accessed ASC
LIMIT 5;
```

### Episode Memory

```sql
-- Statistics
SELECT
    COUNT(*) as total,
    AVG(reward) as avg_reward,
    COUNT(CASE WHEN reward > 0.7 THEN 1 END) as positive
FROM episode_memory
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days';

-- Best episodes
SELECT query, reward, reflection
FROM episode_memory
WHERE reward > 0.8
ORDER BY created_at DESC
LIMIT 5;
```

### L2 Insights

```sql
-- Statistics
SELECT
    COUNT(*) as total,
    AVG(fidelity_score) as avg_fidelity,
    COUNT(CASE WHEN fidelity_score > 0.8 THEN 1 END) as high_quality
FROM l2_insights;

-- Low quality (needs review)
SELECT id, LEFT(content, 100), fidelity_score
FROM l2_insights
WHERE fidelity_score < 0.5
ORDER BY fidelity_score ASC
LIMIT 10;
```

## Database Performance

### Table Statistics

```sql
SELECT
    tablename,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes
FROM pg_stat_user_tables
ORDER BY n_tup_ins DESC;
```

### Index Usage

```sql
SELECT
    indexname,
    idx_scan,
    idx_tup_read
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

### Vacuum and Analyze

```bash
# Manual vacuum
vacuumdb -U mcp_user -d cognitive_memory --analyze

# Check last vacuum
psql -U mcp_user -d cognitive_memory -c \
  "SELECT relname, last_vacuum, last_autovacuum FROM pg_stat_user_tables;"
```

## Troubleshooting Quick Reference

| Issue | Check | Fix |
|-------|-------|-----|
| Server not starting | `journalctl -u cognitive-memory-mcp` | Check logs for errors |
| Database connection | `psql -U mcp_user -d cognitive_memory` | Verify PostgreSQL running |
| High latency | `pg_stat_activity` | Check slow queries |
| Disk space | `df -h /backups` | Clean old backups |
| Memory issues | `free -h` | Restart server |

## Maintenance Schedule

| Task | Frequency | Command |
|------|-----------|---------|
| Check service status | Daily | `systemctl status cognitive-memory-mcp` |
| Review drift logs | Daily | `get_golden_test_results` |
| Check budget | Weekly | `python -m mcp_server.budget status` |
| Verify backups | Weekly | `ls -la /backups/postgres/` |
| Database vacuum | Monthly | `vacuumdb --analyze` |
| Review ground truth | Monthly | Streamlit UI |
