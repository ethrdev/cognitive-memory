# Troubleshooting Guide - Common Issues

**Version:** 3.1.0-Hybrid
**Ziel:** Systematische Problemlösung für häufige Betriebsprobleme des Cognitive Memory Systems

Dieser Guide folgt einem konsistenten Format: **Symptom → Checks → Solutions**

## Problem/Solution Format

Jedes Problem folgt dieser Struktur:
- **Symptom:** Was der User bemerkt
- **Checks:** Diagnostische Schritte zur Problem-Eingrenzung
- **Solutions:** Konkrete Lösungen von einfach bis fortgeschritten

---

## 1. MCP Server verbindet nicht

### Symptom
- Claude Code zeigt keine MCP Tools unter `/mcp`
- Tools sind nicht verfügbar obwohl Installation abgeschlossen
- Fehlermeldung "MCP server not found" oder "No tools available"

### Checks

```bash
# 1. Service Status prüfen
systemctl status cognitive-memory-mcp
# Expected: active (running)

# 2. Claude Code Konfiguration prüfen
cat .mcp.json
# Expected: Valid JSON with correct paths

# 3. Python Pfad prüfen
poetry run which python
# Expected: /path/to/venv/bin/python

# 4. MCP Server manuell testen
timeout 10s poetry run python -m mcp_server
# Expected: Server startup messages, no errors

# 5. Database Verbindung prüfen
psql -U mcp_user -d cognitive_memory -c "SELECT 1;" 2>/dev/null
# Expected: Returns "1"

# 6. Environment Variablen prüfen
grep -E "(DATABASE_URL|API_KEY)" .env.development
# Expected: All variables set
```

### Solutions

**Solution 1: Service Restart (häufigste Ursache)**
```bash
# MCP Server neustarten
sudo systemctl restart cognitive-memory-mcp

# Status prüfen
systemctl status cognitive-memory-mcp

# Logs auf Fehler prüfen
journalctl -u cognitive-memory-mcp --since "5 minutes ago"
```

**Solution 2: Claude Code Configuration korrigieren**
```bash
# Python Pfad aktualisieren
PYTHON_PATH=$(poetry run which python)

# .mcp.json neu erstellen
cat > .mcp.json << EOF
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "/bin/bash",
      "args": [
        "-c",
        "cd $(pwd) && DATABASE_URL='postgresql://mcp_user:$(grep POSTGRES_PASSWORD .env.development | cut -d'=' -f2)@localhost:5432/cognitive_memory' ANTHROPIC_API_KEY='$(grep ANTHROPIC_API_KEY .env.development | cut -d'=' -f2)' OPENAI_API_KEY='$(grep OPENAI_API_KEY .env.development | cut -d'=' -f2)' ENVIRONMENT='development' $PYTHON_PATH -m mcp_server"
      ]
    }
  }
}
EOF

# Claude Code neustarten damit Konfiguration geladen wird
```

**Solution 3: Database Connection reparieren**
```bash
# PostgreSQL Service prüfen
sudo systemctl status postgresql

# Falls nicht running: starten
sudo systemctl start postgresql

# Database Verbindung testen
psql -U mcp_user -d cognitive_memory -c "SELECT version();"

# Connection String in .env.development prüfen
grep DATABASE_URL .env.development
```

**Solution 4: Environment Variablen reparieren**
```bash
# .env.development auf Korrektheit prüfen
cat .env.development | grep -E "(DATABASE_URL|OPENAI_API_KEY|ANTHROPIC_API_KEY)"

# Fehlende Variablen ergänzen
nano .env.development

# Dateirechte prüfen
chmod 600 .env.development
```

---

## 2. Latency >5s

### Symptom
- Queries dauern deutlich länger als erwartet (>5 Sekunden)
- System fühlt sich langsam an
- Claude Code zeigt timeouts bei MCP tool calls

### Checks

```bash
# 1. System Load prüfen
uptime
# Expected: Load average < 2.0 (für moderne CPUs)

# 2. Memory Usage prüfen
free -h
# Expected: Available memory > 1GB

# 3. Database Performance prüfen
psql -U mcp_user -d cognitive_memory -c "
SELECT
    now() - query_start as duration,
    query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC
LIMIT 5;"

# 4. Index Usage prüfen
psql -U mcp_user -d cognitive_memory -c "
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC
LIMIT 5;"

# 5. Hybrid Search Performance Test
time poetry run python -c "
from mcp_server.tools.hybrid_search import execute_hybrid_search
result = execute_hybrid_search('test query', top_k=5)
print(f'Found {len(result)} results in {time.time()}')
"

# 6. API Latency prüfen
curl -w '@curl-format.txt' -o /dev/null -s "https://api.openai.com/v1/embeddings"
```

### Solutions

**Solution 1: Database Indexe optimieren**
```bash
# IVFFlat Index prüfen/rebauen
psql -U mcp_user -d cognitive_memory -c "
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'l2_insights'
  AND indexname LIKE '%ivfflat%';"

# Index neu bauen (falls zu wenig Vektoren)
psql -U mcp_user -d cognitive_memory -c "
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_l2_insights_embedding_ivfflat
ON l2_insights
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);"

# Index Statistiken aktualisieren
psql -U mcp_user -d cognitive_memory -c "ANALYZE l2_insights;"
```

**Solution 2: Connection Pooling konfigurieren**
```bash
# PostgreSQL Connection Pool prüfen
psql -U mcp_user -d cognitive_memory -c "
SELECT count(*) as active_connections
FROM pg_stat_activity
WHERE datname = 'cognitive_memory';"

# Connection Pool Size erhöhen (in postgresql.conf)
# max_connections = 200
# shared_buffers = 256MB
# effective_cache_size = 1GB
```

**Solution 3: API Retry Logic optimieren**
```bash
# Retry Log prüfen
psql -U mcp_user -d cognitive_memory -c "
SELECT api_name, COUNT(*) as retry_count, AVG(retry_count) as avg_retries
FROM api_retry_log
WHERE timestamp >= CURRENT_DATE - INTERVAL '1 day'
GROUP BY api_name;"

# Retry timeouts reduzieren (in config.yaml)
# poetry run nano config/config.yaml
# api_limits:
#   max_retries: 3 (von 4 reduzieren)
#   timeout_seconds: 10 (von 30 reduzieren)
```

**Solution 4: System Resources optimieren**
```bash
# Memory-Intensive Prozesse identifizieren
ps aux --sort=-%mem | head -10

# PostgreSQL Memory-Konfiguration prüfen
sudo -u postgres psql -c "SHOW shared_buffers;"
sudo -u postgres psql -c "SHOW effective_cache_size;"

# Falls erforderlich: PostgreSQL neu konfigurieren
# sudo nano /var/lib/postgres/data/postgresql.conf
```

---

## 3. API Budget Überschreitung

### Symptom
- Budget Alert wurde getriggert
- System blockiert API-Aufrufe
- Kosten höher als erwartet

### Checks

```bash
# 1. Aktuelle Budget Situation prüfen
poetry run python -m mcp_server.budget dashboard

# 2. Kosten der letzten 7 Tage analysieren
poetry run python -m mcp_server.budget breakdown --days 7

# 3. High-Cost APIs identifizieren
psql -U mcp_user -d cognitive_memory -c "
SELECT
    api_name,
    SUM(cost_eur) as total_cost,
    SUM(num_calls) as total_calls,
    AVG(cost_eur) as avg_cost_per_call
FROM api_cost_log
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY api_name
ORDER BY total_cost DESC;"

# 4. Ungewöhnliche usage patterns finden
psql -U mcp_user -d cognitive_memory -c "
SELECT
    date,
    SUM(cost_eur) as daily_cost
FROM api_cost_log
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date
ORDER BY daily_cost DESC
LIMIT 5;"

# 5. Cost Alerts prüfen
poetry run python -m mcp_server.budget alerts status
```

### Solutions

**Solution 1: Query Volume reduzieren**
```bash
# High-frequency Queries identifizieren
psql -U mcp_user -d cognitive_memory -c "
SELECT
    COUNT(*) as query_count,
    DATE_TRUNC('hour', created_at) as hour
FROM l0_raw
WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
GROUP BY hour
ORDER BY query_count DESC
LIMIT 5;"

# Staged Dual Judge aktivieren (Kosten sparen)
poetry run python -c "
from mcp_server.utils.staged_dual_judge import activate_staged_mode
result = activate_staged_mode(cost_threshold=8.0)
print(f'Activated staged mode: {result[\"activated\"]}')
"
```

**Solution 2: Cost Optimization aktivieren**
```bash
# Cost Optimization Recommendations
poetry run python -m mcp_server.budget optimize

# Evaluated vs. Non-evaluated Queries Ratio prüfen
psql -U mcp_user -d cognitive_memory -c "
SELECT
    COUNT(CASE WHEN episode_id IS NOT NULL THEN 1 END) as evaluated_queries,
    COUNT(*) as total_queries,
    ROUND(COUNT(CASE WHEN episode_id IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as evaluation_rate
FROM l0_raw
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days';"

# Embedding Cache prüfen
psql -U mcp_user -d cognitive_memory -c "
SELECT
    COUNT(*) as cached_embeddings,
    AVG(fidelity_score) as avg_quality
FROM l2_insights
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days';"
```

**Solution 3: Budget Thresholds anpassen**
```bash
# Warning/Critical Thresholds anpassen
poetry run python -m mcp_server.budget config --threshold-warning 6
poetry run python -m mcp_server.budget config --threshold-critical 8

# Neue Thresholds prüfen
poetry run python -m mcp_server.budget alerts status
```

**Solution 4: Usage Patterns analysieren und anpassen**
```bash
# Query Pattern Analysis
poetry run python -c "
from mcp_server.utils.usage_analyzer import analyze_query_patterns
patterns = analyze_query_patterns(days=7)
for pattern in patterns['high_cost_patterns']:
    print(f'Pattern: {pattern[\"description\"]}')
    print(f'Cost: €{pattern[\"monthly_cost\"]:.2f}')
    print(f'Recommendation: {pattern[\"recommendation\"]}')
"
```

---

## 4. Model Drift Alert

### Symptom
- Precision@5 drop >5% wurde detektiert
- Golden Test shows poor performance
- Retrieved documents nicht mehr relevant

### Checks

```bash
# 1. Aktuelle Drift Situation prüfen
poetry run python -c "
from mcp_server.tools.get_golden_test_results import execute_golden_test
result = execute_golden_test()
print(f'Current Precision@5: {result[\"precision_at_5\"]:.3f}')
print(f'Baseline Precision@5: {result[\"baseline_precision\"]:.3f}')
print(f'Drift Detected: {result[\"drift_detected\"]}')
"

# 2. Drift History analysieren
psql -U mcp_user -d cognitive_memory -c "
SELECT
    date,
    precision_at_5,
    baseline_precision,
    drift_detected,
    precision_at_5 - baseline_precision as diff_from_baseline
FROM model_drift_log
ORDER BY date DESC
LIMIT 10;"

# 3. Query Type Performance prüfen
psql -U mcp_user -d cognitive_memory -c "
SELECT
    query_type,
    AVG(precision_at_5) as avg_precision,
    COUNT(*) as query_count
FROM golden_test_set gts
JOIN model_drift_log mdl ON DATE(gts.created_at) = mdl.date
WHERE gts.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY query_type;"

# 4. Embedding Model Version prüfen
poetry run python -c "
import openai
print(f'OpenAI Models: {openai.Model.list()}')
"

# 5. L2 Insight Qualität prüfen
psql -U mcp_user -d cognitive_memory -c "
SELECT
    AVG(fidelity_score) as avg_fidelity,
    COUNT(*) as total_insights,
    COUNT(CASE WHEN fidelity_score > 0.8 THEN 1 END) as high_quality_insights
FROM l2_insights
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days';"
```

### Solutions

**Solution 1: Golden Test Set erweitern**
```bash
# Low-performing Queries identifizieren
psql -U mcp_user -d cognitive_memory -c "
SELECT
    query_id,
    query_text,
    precision_at_5
FROM golden_test_set
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
  AND precision_at_5 < 0.6
ORDER BY precision_at_5 ASC
LIMIT 10;"

# Additional Ground Truth hinzufügen
poetry run python -c "
from mcp_server.utils.ground_truth_expander import expand_golden_test_set
result = expand_golden_test_set(target_increase=20)
print(f'Added {result[\"added_queries\"]} new queries')
"
```

**Solution 2: Re-Kalibration durchführen**
```bash
# Hybrid Search Weights re-kalibrieren
poetry run python -c "
from mcp_server.utils.hybrid_search_calibrator import recalibrate_weights
result = recalibrate_weights()
print(f'New weights: {result[\"new_weights\"]}')
print(f'Expected improvement: {result[\"expected_improvement\"]:.1%}')
"

# Calibrated Performance testen
poetry run python -c "
from mcp_server.tools.get_golden_test_results import execute_golden_test
result = execute_golden_test()
print(f'Post-calibration Precision@5: {result[\"precision_at_5\"]:.3f}')
"
```

**Solution 3: OpenAI API Changes prüfen**
```bash
# API Model Version prüfen
curl -H "Authorization: Bearer $(grep OPENAI_API_KEY .env.development | cut -d'=' -f2)" \
     https://api.openai.com/v1/models

# Embedding Qualität testen
poetry run python -c "
import openai
client = openai.OpenAI()
test_text = 'This is a test for embedding quality check'
response = client.embeddings.create(
    model='text-embedding-3-small',
    input=test_text
)
print(f'Embedding dimensions: {len(response.data[0].embedding)}')
"
```

**Solution 4: L2 Insights neu generieren**
```bash
# Low-Quality Insights identifizieren
psql -U mcp_user -d cognitive_memory -c "
SELECT id, content_preview, fidelity_score
FROM l2_insights
WHERE fidelity_score < 0.6
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY fidelity_score ASC
LIMIT 10;"

# Insights neu komprimieren
poetry run python -c "
from mcp_server.utils.insight_refresher import refresh_low_quality_insights
result = refresh_low_quality_insights(min_fidelity=0.6)
print(f'Refreshed {result[\"refreshed_count\"]} insights')
"
```

---

## 5. PostgreSQL Connection Failure

### Symptom
- Database nicht erreichbar
- Connection refused errors
- MCP Server startet nicht wegen DB Probleme

### Checks

```bash
# 1. PostgreSQL Service Status
sudo systemctl status postgresql

# 2. PostgreSQL Prozess prüfen
ps aux | grep postgres

# 3. Port prüfen
ss -tlnp | grep :5432

# 4. Connection Test
psql -U mcp_user -d cognitive_memory -c "SELECT 1;" 2>&1

# 5. Disk Space prüfen
df -h /var/lib/postgres

# 6. PostgreSQL Logs prüfen
sudo tail -20 /var/log/postgresql.log

# 7. Connection Limits prüfen
psql -U postgres -c "SHOW max_connections;"
psql -U postgres -c "
SELECT count(*) as active_connections
FROM pg_stat_activity;"
```

### Solutions

**Solution 1: PostgreSQL Service restarten**
```bash
# PostgreSQL neustarten
sudo systemctl restart postgresql

# Status prüfen
systemctl status postgresql

# Logs prüfen
journalctl -u postgresql --since "5 minutes ago"
```

**Solution 2: Connection Issues beheben**
```bash
# pg_hba.conf prüfen
sudo cat /var/lib/postgres/data/pg_hba.conf

# Authentication Method anpassen (falls erforderlich)
sudo nano /var/lib/postgres/data/pg_hba.conf
# Ändern: local   all   all   peer  →  md5

# PostgreSQL neu starten
sudo systemctl restart postgresql

# Connection Test wiederholen
psql -U mcp_user -d cognitive_memory -c "SELECT version();"
```

**Solution 3: Resource Constraints beheben**
```bash
# Disk Space prüfen und freigeben
df -h
sudo du -sh /var/lib/postgres/data/base/* | sort -hr | head -10

# Falls volle Disk: Logs aufräumen
sudo find /var/log -name "*.log" -mtime +30 -delete
sudo journalctl --vacuum-time=30d

# Connection Limit erhöhen (falls erforderlich)
sudo -u postgres psql -c "ALTER SYSTEM SET max_connections = 200;"
sudo systemctl reload postgresql
```

**Solution 4: Database Recovery**
```bash
# Database Consistency prüfen
sudo -u postgres pg_dump -Fc cognitive_memory > /tmp/test_backup.dump

# Falls Corruption: Restore vom letzten Backup
sudo systemctl stop postgresql
sudo -u postgres dropdb cognitive_memory
sudo -u postgres createdb cognitive_memory
sudo -u postgres pg_restore -d cognitive_memory /backups/postgres/cognitive_memory_latest.dump
sudo systemctl start postgresql
```

---

## 6. Haiku API Unavailable

### Symptom
- Evaluation failures
- Fallback mode aktiv
- Anthropic API timeouts oder errors

### Checks

```bash
# 1. API Key prüfen
grep ANTHROPIC_API_KEY .env.development

# 2. API Connectivity testen
curl -H "Authorization: Bearer $(grep ANTHROPIC_API_KEY .env.development | cut -d'=' -f2)" \
     -H "Content-Type: application/json" \
     -d '{"model": "claude-3-5-haiku-20241022", "max_tokens": 10, "messages": [{"role": "user", "content": "test"}]}' \
     https://api.anthropic.com/v1/messages

# 3. Retry Log prüfen
psql -U mcp_user -d cognitive_memory -c "
SELECT
    timestamp,
    api_name,
    retry_count,
    error_message
FROM api_retry_log
WHERE api_name = 'haiku_evaluation'
  AND timestamp >= CURRENT_DATE - INTERVAL '1 day'
ORDER BY timestamp DESC
LIMIT 10;"

# 4. Fallback Status prüfen
poetry run python -c "
from mcp_server.external.anthropic_client import get_fallback_status
status = get_fallback_status()
print(f'Fallback Active: {status[\"fallback_active\"]}')
print(f'Reason: {status[\"reason\"]}')
"

# 5. Anthropic Status Page prüfen
curl -s "https://status.anthropic.com/" | grep -i "operational\|degraded\|down"
```

### Solutions

**Solution 1: API Key prüfen und erneuern**
```bash
# API Key validieren
poetry run python -c "
from mcp_server.external.anthropic_client import validate_api_key
key_valid = validate_api_key()
print(f'API Key Valid: {key_valid}')
"

# Falls ungültig: neuen Key besorgen und updaten
nano .env.development
# ANTHROPIC_API_KEY=sk-ant-NEU-KEY-HIER
```

**Solution 2: Retry Logic optimieren**
```bash
# Retry timeouts anpassen (temporär erhöhen)
poetry run python -c "
from mcp_server.utils.retry_config import update_retry_config
update_retry_config({
    'haiku_evaluation': {
        'max_retries': 5,
        'timeout_seconds': 30,
        'backoff_factor': 2.0
    }
})
"

# Retry Logs überwachen
tail -f /var/log/cognitive-memory/retry.log &
```

**Solution 3: Fallback Modus aktivieren**
```bash
# Manuelles Fallback aktivieren
poetry run python -c "
from mcp_server.fallback.manager import activate_fallback
result = activate_fallback(reason='Haiku API unavailable', duration_hours=24)
print(f'Fallback activated: {result[\"activated\"]}')
"

# Fallback Status prüfen
poetry run python -c "
from mcp_server.fallback.manager import get_fallback_config
config = get_fallback_config()
print(f'Fallback APIs: {config[\"fallback_apis\"]}')
"
```

**Solution 4: Alternative Evaluation Method**
```bash
# Staged Dual Judge ohne Haiku aktivieren
poetry run python -c "
from mcp_server.utils.staged_evaluation import activate_gpt4_only_mode
result = activate_gpt4_only_mode()
print(f'GPT-4 only mode: {result[\"activated\"]}')
"

# Evaluation mit Claude Code intern (kostenlos)
poetry run python -c "
from mcp_server.evaluation.claude_code_evaluator import configure_claude_code_evaluator
result = configure_claude_code_evaluator(enable=True)
print(f'Claude Code evaluator: {result[\"enabled\"]}')
"
```

---

## 7. Low Precision@5

### Symptom
- Retrieved documents nicht relevant
- User不满意 mit Suchergebnissen
- Precision@5 < 0.6 statt >0.75 target

### Checks

```bash
# 1. Aktuelle Precision@5 messen
poetry run python -c "
from mcp_server.tools.get_golden_test_results import execute_golden_test
result = execute_golden_test()
print(f'Current Precision@5: {result[\"precision_at_5\"]:.3f}')
print(f'Target Precision@5: 0.750')
print(f'Gap: {0.750 - result[\"precision_at_5\"]:.3f}')
"

# 2. Query Type Performance analysieren
psql -U mcp_user -d cognitive_memory -c "
SELECT
    query_type,
    AVG(precision_at_5) as avg_precision,
    COUNT(*) as query_count,
    STDDEV(precision_at_5) as precision_std
FROM golden_test_set
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY query_type
ORDER BY avg_precision DESC;"

# 3. L2 Insight Qualität prüfen
psql -U mcp_user -d cognitive_memory -c "
SELECT
    AVG(fidelity_score) as avg_fidelity,
    COUNT(*) as total_insights,
    COUNT(CASE WHEN fidelity_score > 0.8 THEN 1 END) as high_quality_count,
    ROUND(COUNT(CASE WHEN fidelity_score > 0.8 THEN 1 END) * 100.0 / COUNT(*), 2) as high_quality_pct
FROM l2_insights
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days';"

# 4. Hybrid Search Weights prüfen
poetry run python -c "
from mcp_server.config import get_config
config = get_config()
weights = config['search']['hybrid_weights']
print(f'Semantic Weight: {weights[\"semantic\"]}')
print(f'Keyword Weight: {weights[\"keyword\"]}')
print(f'RRF Weight: {weights[\"rrf\"]}')
"

# 5. Index Performance prüfen
psql -U mcp_user -d cognitive_memory -c "
SELECT
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename = 'l2_insights'
ORDER BY idx_scan DESC;"
```

### Solutions

**Solution 1: Hybrid Search Weights optimieren**
```bash
# Grid Search für optimale Weights
poetry run python -c "
from mcp_server.utils.hybrid_search_optimizer import optimize_weights
result = optimize_weights(target_precision=0.75)
print(f'Optimal weights: {result[\"best_weights\"]}')
print(f'Expected precision: {result[\"expected_precision\"]:.3f}')
print(f'Improvement: {result[\"improvement\"]:.1%}')
"

# Neue Weights in Konfiguration übernehmen
poetry run python -c "
from mcp_server.config import update_config
update_config({
    'search': {
        'hybrid_weights': {
            'semantic': 0.4,    # Angepasst
            'keyword': 0.3,     # Angepasst
            'rrf': 0.3          # Angepasst
        }
    }
})
"
```

**Solution 2: Ground Truth erweitern und verbessern**
```bash
# Low-performing Queries identifizieren
psql -U mcp_user -d cognitive_memory -c "
SELECT
    query_text,
    precision_at_5,
    query_type
FROM golden_test_set
WHERE precision_at_5 < 0.5
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY precision_at_5 ASC
LIMIT 10;"

# Ground Truth Quality verbessern
poetry run python -c "
from mcp_server.utils.ground_truth_improver import improve_low_precision_queries
result = improve_low_precision_queries(min_precision=0.5)
print(f'Improved {result[\"improved_queries\"]} queries')
print(f'Expected precision gain: {result[\"expected_gain\"]:.1%}')
"
```

**Solution 3: L2 Insight Qualität verbessern**
```bash
# Low-Fidelity Insights identifizieren und erneuern
psql -U mcp_user -d cognitive_memory -c "
SELECT id, content_preview, fidelity_score
FROM l2_insights
WHERE fidelity_score < 0.7
  AND created_at >= CURRENT_DATE - INTERVAL '60 days'
ORDER BY fidelity_score ASC
LIMIT 20;"

# Fidelity Threshold erhöhen
poetry run python -c "
from mcp_server.utils.insight_quality import update_fidelity_threshold
result = update_fidelity_threshold(min_fidelity=0.7)
print(f'Updated {result[\"updated_insights\"]} insights')
"

# Batch Re-Compression für alte Insights
poetry run python -c "
from mcp_server.utils.insight_refresher import batch_recompress_old_insights
result = batch_recompress_old_insights(days_old=60, min_fidelity=0.7)
print(f'Recompressed {result[\"recompressed_count\"]} insights')
"
```

**Solution 4: Query Expansion optimieren**
```bash
# Query Expansion Performance analysieren
poetry run python -c "
from mcp_server.utils.query_analyzer import analyze_query_expansion_effectiveness
result = analyze_query_expansion_effectiveness()
print(f'Average improvement: {result[\"avg_precision_improvement\"]:.1%}')
print(f'Best expansion strategy: {result[\"best_strategy\"]}')
"

# Expansion Strategy anpassen
poetry run python -c "
from mcp_server.utils.query_expander import update_expansion_strategy
result = update_expansion_strategy(strategy='semantic_focused')
print(f'Updated expansion strategy: {result[\"new_strategy\"]}')
"
```

---

## General Troubleshooting Workflow

### Systematic Approach

```bash
# 1. Full System Health Check
echo "=== System Health Check ==="
systemctl status cognitive-memory-mcp postgresql --no-pager

echo -e "\n=== Database Health ==="
psql -U mcp_user -d cognitive_memory -c "SELECT 1 as db_connection_test;" 2>/dev/null && echo "✅ DB OK" || echo "❌ DB Failed"

echo -e "\n=== API Keys Test ==="
poetry run python -c "
try:
    from mcp_server.utils.api_validator import validate_all_keys
    result = validate_all_keys()
    print('✅ APIs OK' if result['all_valid'] else f'❌ API Issues: {result[\"invalid_keys\"]}')
except Exception as e:
    print(f'❌ API Test Failed: {e}')
"

echo -e "\n=== Recent Errors ==="
journalctl -u cognitive-memory-mcp --since "1 hour ago" -p err --no-pager | tail -10

echo -e "\n=== Performance Metrics ==="
poetry run python -m mcp_server.budget status 2>/dev/null || echo "❌ Budget monitoring unavailable"
```

### Emergency Procedures

```bash
# Full System Reset (nur im Notfall)
echo "=== EMERGENCY SYSTEM RESET ==="

# 1. Services stoppen
sudo systemctl stop cognitive-memory-mcp

# 2. Backup aktueller State
BACKUP_DIR="/tmp/emergency_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
sudo -u postgres pg_dump -Fc cognitive_memory > "$BACKUP_DIR/emergency_backup.dump"

# 3. Logs sichern
journalctl -u cognitive-memory-mcp > "$BACKUP_DIR/service_logs.txt"
cp .env.development "$BACKUP_DIR/env_backup"

# 4. Services neu starten
sudo systemctl start postgresql
sleep 5
sudo systemctl start cognitive-memory-mcp

# 5. Verification
sleep 10
systemctl status cognitive-memory-mcp --no-pager

echo "Emergency backup created at: $BACKUP_DIR"
```

---

*Troubleshooting Guide erstellt am 2025-11-24*
*Projekt: Cognitive Memory System v3.1.0-Hybrid*
