# Troubleshooting Guide

Common issues and solutions for the Cognitive Memory System.

## Quick Diagnostics

Run this health check first:

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
systemctl status cognitive-memory-mcp
cat .mcp.json
poetry run which python
psql -U mcp_user -d cognitive_memory -c "SELECT 1;"
```

### Solutions

**Restart service:**
```bash
sudo systemctl restart cognitive-memory-mcp
journalctl -u cognitive-memory-mcp --since "5m"
```

**Fix configuration:**
```bash
# Regenerate .mcp.json
PYTHON_PATH=$(poetry run which python)
cat > .mcp.json << EOF
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "$PYTHON_PATH",
      "args": ["-m", "mcp_server"]
    }
  }
}
EOF
```

**Restart Claude Code** to reload MCP configuration.

---

## 2. High Latency (>5s)

### Symptoms
- Queries take >5 seconds
- Timeouts during MCP tool calls

### Checks
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
psql -U mcp_user -d cognitive_memory -c "ANALYZE l2_insights;"
```

**Reduce connection pool pressure:**
```bash
psql -U mcp_user -d cognitive_memory -c "
SELECT count(*) FROM pg_stat_activity WHERE datname = 'cognitive_memory';"
```

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

## 5. PostgreSQL Connection Failed

### Symptoms
- Database not reachable
- "Connection refused" errors

### Checks
```bash
sudo systemctl status postgresql
ss -tlnp | grep 5432
df -h /var/lib/postgres
```

### Solutions

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

## Getting Help

If issues persist:

1. Check logs: `journalctl -u cognitive-memory-mcp -f`
2. Review documentation: [Operations Manual](operations-manual.md)
3. Open an issue: https://github.com/ethrdev/cognitive-memory/issues
