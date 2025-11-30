# Troubleshooting Guide

Common issues and solutions for the Cognitive Memory System.

## Quick Diagnostics

Run this health check first:

**For Neon Cloud:**
```bash
# Full system check
psql "$DATABASE_URL" -c "SELECT 1;"
python -c "import mcp_server; print('OK')"
```

**For Local PostgreSQL:**
```bash
# Full system check
systemctl status cognitive-memory-mcp postgresql --no-pager
psql -U mcp_user -d cognitive_memory -c "SELECT 1;"
python -c "import mcp_server; print('OK')"
```

---

## 1. MCP Server Not Connecting

### Symptoms
- Claude Code shows no MCP tools under `/mcp`
- "MCP server not found" errors

### Checks
```bash
# Check .mcp.json exists
cat .mcp.json  # Should exist (copy from .mcp.json.template if missing)

# Test database connection
psql "$DATABASE_URL" -c "SELECT 1;"

# For local: check systemd service
systemctl status cognitive-memory-mcp
```

### Solutions

**Restart service (Local):**
```bash
sudo systemctl restart cognitive-memory-mcp
journalctl -u cognitive-memory-mcp --since "5m"
```

**Fix configuration:**
```bash
# Create .mcp.json from template
cp .mcp.json.template .mcp.json

# Edit .mcp.json and replace ${PROJECT_ROOT} with your actual path
# Example: /home/user/cognitive-memory/start_mcp_server.sh

# Verify JSON syntax
python -m json.tool .mcp.json
```

**Restart Claude Code** to reload MCP configuration.

---

## 2. High Latency (>5s)

### Symptoms
- Queries take >5 seconds
- Timeouts during MCP tool calls

### Checks

**For Neon Cloud:**
```bash
# Check if project is suspended (free tier)
psql "$DATABASE_URL" -c "SELECT 1;"  # First query may take ~1s

# Database performance
psql "$DATABASE_URL" -c "
SELECT now() - query_start as duration, query
FROM pg_stat_activity WHERE state = 'active';"
```

**For Local PostgreSQL:**
```bash
# System load
uptime
free -h

# Database performance
psql -U mcp_user -d cognitive_memory -c "
SELECT now() - query_start as duration, query
FROM pg_stat_activity WHERE state = 'active';"
```

### Solutions

**Optimize indexes:**
```bash
psql "$DATABASE_URL" -c "ANALYZE l2_insights;"
```

**Reduce connection pool pressure:**
```bash
psql "$DATABASE_URL" -c "
SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();"
```

**Neon-specific:** Upgrade to paid tier to avoid auto-suspend wake-up latency.

---

## 3. Budget Exceeded

### Symptoms
- Budget alerts triggered
- API calls blocked

### Checks
```bash
python -m mcp_server.budget status
python -m mcp_server.budget breakdown --days 7
```

### Solutions

**Analyze costs:**
```sql
SELECT api_name, SUM(cost_eur) as total_cost
FROM api_cost_log
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY api_name ORDER BY total_cost DESC;
```

**Reduce API usage:**
- Enable staged dual judge mode
- Increase caching
- Reduce evaluation frequency

---

## 4. Model Drift Detected

### Symptoms
- Precision@5 drop >5%
- Poor retrieval quality

### Checks
```bash
# Current drift status
python -c "
from mcp_server.tools.get_golden_test_results import execute_golden_test
result = execute_golden_test()
print(f'Precision@5: {result[\"precision_at_5\"]:.3f}')
print(f'Drift: {result[\"drift_detected\"]}')"
```

### Solutions

**Check drift history:**
```sql
SELECT date, precision_at_5, drift_detected
FROM model_drift_log ORDER BY date DESC LIMIT 10;
```

**Recalibrate hybrid search weights:**
```bash
python -c "
from mcp_server.utils.hybrid_search_calibrator import recalibrate_weights
result = recalibrate_weights()
print(f'New weights: {result}')"
```

---

## 5. Database Connection Failed

### Symptoms
- Database not reachable
- "Connection refused" errors

### Checks (Neon Cloud)
```bash
# Verify connection string format
echo $DATABASE_URL
# Should include: ?sslmode=require

# Test connection
psql "$DATABASE_URL" -c "SELECT 1;"

# Check if project is suspended (first query may take ~1s)
```

### Checks (Local PostgreSQL)
```bash
sudo systemctl status postgresql
ss -tlnp | grep 5432
df -h /var/lib/postgres
```

### Solutions (Neon Cloud)

**Verify connection string:**
```bash
# Must include ?sslmode=require
# Format: postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
```

**Check Neon Console:**
- Verify project is not paused
- Check connection limits (free tier: 5 concurrent)
- Verify region availability at [status.neon.tech](https://status.neon.tech)

### Solutions (Local PostgreSQL)

**Restart PostgreSQL:**
```bash
sudo systemctl restart postgresql
```

**Check authentication:**
```bash
sudo cat /var/lib/postgres/data/pg_hba.conf
# Ensure: local all all md5
```

**Recover from backup:**
```bash
sudo systemctl stop postgresql
sudo -u postgres pg_restore -d cognitive_memory --clean /backups/postgres/latest.dump
sudo systemctl start postgresql
```

---

## 6. Haiku API Unavailable

### Symptoms
- Evaluation failures
- Fallback mode active

### Checks
```bash
# Test API connectivity
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-3-5-haiku-20241022","max_tokens":10,"messages":[{"role":"user","content":"test"}]}' \
  https://api.anthropic.com/v1/messages
```

### Solutions

**Check API key:**
```bash
grep ANTHROPIC_API_KEY .env.development
```

**Enable fallback:**
```bash
python -c "
from mcp_server.fallback.manager import activate_fallback
activate_fallback(reason='Haiku unavailable', duration_hours=24)"
```

---

## 7. Low Precision@5

### Symptoms
- Retrieved documents not relevant
- Precision@5 < 0.6

### Checks
```sql
SELECT query_type, AVG(precision_at_5) as avg_precision
FROM golden_test_set
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY query_type;
```

### Solutions

**Optimize hybrid weights:**
```bash
python -c "
from mcp_server.utils.hybrid_search_optimizer import optimize_weights
result = optimize_weights(target_precision=0.75)
print(f'Best weights: {result}')"
```

**Improve L2 insight quality:**
```sql
SELECT id, LEFT(content, 50), fidelity_score
FROM l2_insights WHERE fidelity_score < 0.6
ORDER BY fidelity_score LIMIT 10;
```

---

## Emergency Reset

Use only when all else fails:

**For Neon Cloud:**
```bash
# 1. Backup current state
pg_dump "$DATABASE_URL" -Fc > /tmp/emergency_backup_$(date +%Y%m%d).dump

# 2. Restart MCP server
pkill -f "python -m mcp_server"
python -m mcp_server

# 3. Verify
psql "$DATABASE_URL" -c "SELECT count(*) FROM l2_insights;"
```

**For Local PostgreSQL:**
```bash
# 1. Stop services
sudo systemctl stop cognitive-memory-mcp

# 2. Backup current state
BACKUP_DIR="/tmp/emergency_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
sudo -u postgres pg_dump -Fc cognitive_memory > "$BACKUP_DIR/backup.dump"

# 3. Restart services
sudo systemctl start postgresql
sleep 5
sudo systemctl start cognitive-memory-mcp

# 4. Verify
systemctl status cognitive-memory-mcp
```

---

## 8. Graph Duplicate Nodes (RESOLVED v2025-11-30)

### Symptom (Historical)
- `graph_add_edge` created duplicate nodes with same name but different labels
- `graph_query_neighbors` returned empty results for nodes created via `graph_add_node`

### Resolution
This bug was fixed in commit `9f6634e`. The UNIQUE constraint is now on `name` only (not `label` + `name`).

**Migration required:**
```sql
DROP INDEX IF EXISTS idx_nodes_unique;
CREATE UNIQUE INDEX idx_nodes_unique ON nodes(name);
```

**Cleanup duplicate nodes:**
```sql
-- Check for duplicates
SELECT name, COUNT(*) FROM nodes GROUP BY name HAVING COUNT(*) > 1;

-- Remove duplicates (keep oldest)
DELETE FROM nodes a USING nodes b
WHERE a.name = b.name AND a.created_at > b.created_at;
```

---

## 9. SSL Connection Closed Unexpectedly (Known Issue)

### Symptoms
- First MCP call after idle period (>30s) fails with:
  ```
  SSL connection has been closed unexpectedly
  ```
- Retry immediately succeeds

### Workaround
Simply retry the operation. The second call succeeds.

### Future Fix
Connection pooling with keep-alive is planned. See `TECH-DEBT-SSL-CONNECTION.md`.

---

## 10. hybrid_search Ignores Custom Weights (RESOLVED v2025-11-30)

### Symptom (Historical)
- Custom weights like `{"semantic": 0.5, "keyword": 0.5}` were ignored
- Response showed default weights `{"semantic": 0.6, "keyword": 0.2, "graph": 0.2}`

### Resolution
Fixed in commit `9f6634e`. Legacy 2-source weights are now proportionally scaled:
- Input: `{"semantic": 0.5, "keyword": 0.5}`
- Output: `{"semantic": 0.4, "keyword": 0.4, "graph": 0.2}`

For full control, use 3-source format: `{"semantic": 0.6, "keyword": 0.2, "graph": 0.2}`

---

## Getting Help

If issues persist:

1. Check logs: `journalctl -u cognitive-memory-mcp -f` (local) or Python stderr (Neon)
2. Review documentation: [Operations Manual](operations/operations-manual.md)
3. Open an issue: https://github.com/ethrdev/cognitive-memory/issues
