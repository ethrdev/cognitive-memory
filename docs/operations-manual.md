# Operations Manual - Daily Operations

**Version:** 3.1.0-Hybrid
**Ziel:** Komplette Anleitung für daily operations und maintenance des Cognitive Memory Systems

Dieser Manual beschreibt alle Routine-Aufgaben für den laufenden Betrieb des Systems in Production.

## 1. Service Management

### MCP Server systemd Service

**Service Name:** `cognitive-memory-mcp`
**Purpose:** MCP Server für Claude Code Integration
**Auto-Restart:** Aktiv (Restart=always)

#### Service Status prüfen

```bash
# Aktuellen Service-Status anzeigen
systemctl status cognitive-memory-mcp

# Kurzform: Nur Active-Status
systemctl is-active cognitive-memory-mcp
# Expected: active

# Auto-Start Status prüfen
systemctl is-enabled cognitive-memory-mcp
# Expected: enabled

# Service-Aktivität der letzten 24h
journalctl -u cognitive-memory-mcp --since "24 hours ago" --no-pager
```

#### Service Management Commands

```bash
# Service starten
sudo systemctl start cognitive-memory-mcp

# Service stoppen
sudo systemctl stop cognitive-memory-mcp

# Service neu starten (nach Config-Änderungen)
sudo systemctl restart cognitive-memory-mcp

# Service Konfiguration neu laden (ohne Restart)
sudo systemctl reload cognitive-memory-mcp

# Service deaktivieren (wenn Wartung erforderlich)
sudo systemctl disable cognitive-memory-mcp
```

#### Log-Zugriff und Monitoring

```bash
# Live-Logs verfolgen (wie tail -f)
journalctl -u cognitive-memory-mcp -f

# Logs der letzten Stunde
journalctl -u cognitive-memory-mcp --since "1 hour ago"

# Fehler-Logs der letzten 24h
journalctl -u cognitive-memory-mcp --since "24 hours ago" -p err

# Logs mit Pattern Filter
journalctl -u cognitive-memory-mcp | grep -i "error\|exception\|failed"

# Service Performance Stats
systemctl show cognitive-memory-mcp --property=MemoryCurrent,CPUUsageNSec
```

#### Health Checks

```bash
# Basic Health Check (expected: 0 = active)
systemctl is-active cognitive-memory-mcp; echo $?

# Detaillierte Service-Informationen
systemctl show cognitive-memory-mcp | grep -E "(State|Result|Status)"

# Prozess prüfen
ps aux | grep -v grep | grep "python -m mcp_server"

# Port prüfen (falls HTTP transport verwendet)
ss -tlnp | grep :8000
```

## 2. Backup Operations

### PostgreSQL Database Backups

**Schedule:** Täglich um 03:00 Uhr (Cron Job)
**Retention:** 7 Tage
**Location:** `/backups/postgres/`

#### Manuelle Backups erstellen

```bash
# Full Database Backup (komprimiert)
sudo -u postgres pg_dump -Fc cognitive_memory > /backups/postgres/cognitive_memory_$(date +%Y%m%d_%H%M%S).dump

# SQL-Format Backup (lesbar)
sudo -u postgres pg_dump cognitive_memory > /backups/postgres/cognitive_memory_$(date +%Y%m%d_%H%M%S).sql

# Backup mit Datum im Format YYYY-MM-DD
BACKUP_FILE="/backups/postgres/cognitive_memory_$(date +%F).dump"
sudo -u postgres pg_dump -Fc cognitive_memory > "$BACKUP_FILE"
echo "Backup created: $BACKUP_FILE"
```

#### Backup Verification

```bash
# Backup-Dateien auflisten
ls -lah /backups/postgres/

# Backup-Integrität prüfen (ohne Restore)
sudo -u postgres pg_restore --list /backups/postgres/cognitive_memory_latest.dump | head -20

# Backup-Größe prüfen (sollte konsistent sein)
du -sh /backups/postgres/*.dump | tail -5

# Prüfen ob letztes Backup erfolgreich war
find /backups/postgres/ -name "*.dump" -mtime -1 -exec ls -la {} \;
```

#### Backup Rotation und Cleanup

```bash
# Ältere Backups löschen (>7 Tage)
find /backups/postgres/ -name "*.dump" -mtime +7 -delete
find /backups/postgres/ -name "*.sql" -mtime +7 -delete

# Backup-Statistik anzeigen
echo "Backup Statistics:"
echo "Total backups: $(ls /backups/postgres/*.dump | wc -l)"
echo "Latest backup: $(ls -t /backups/postgres/*.dump | head -1)"
echo "Total size: $(du -sh /backups/postgres/ | cut -f1)"
```

#### Automatische Backup-Cron Job

```bash
# Cron Job anzeigen
crontab -l | grep backup

# Beispielscript für tägliche Backups
cat > /usr/local/bin/backup_cognitive_memory.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/cognitive_memory_$DATE.dump"

# Backup erstellen
sudo -u postgres pg_dump -Fc cognitive_memory > "$BACKUP_FILE"

# Alte Backups löschen (>7 Tage)
find $BACKUP_DIR -name "*.dump" -mtime +7 -delete

# Logging
echo "Backup completed: $BACKUP_FILE" | logger -t cognitive-memory-backup
EOF

chmod +x /usr/local/bin/backup_cognitive_memory.sh
```

## 3. Model Drift Detection

### Golden Test Set Monitoring

**Tool:** `get_golden_test_results` MCP Tool
**Schedule:** Tägliche Ausführung empfohlen
**Threshold:** Drift bei Precision@5 drop >5%

#### Manueller Drift Check

```bash
# Golden Test ausführen (über Claude Code)
# Führe MCP Tool "get_golden_test_results" aus

# Expected Output Format:
# {
#   "date": "2025-01-15",
#   "precision_at_5": 0.78,
#   "drift_detected": false,
#   "baseline_precision": 0.82,
#   "queries_tested": 75,
#   "details": "All metrics within normal range"
# }
```

#### Drift Check Commands

```bash
# Manueller Test über Python (für Skripte)
cd /path/to/i-o
poetry run python -c "
from mcp_server.tools.get_golden_test_results import execute_golden_test
result = execute_golden_test()
print(f'Date: {result[\"date\"]}')
print(f'Precision@5: {result[\"precision_at_5\"]:.3f}')
print(f'Drift Detected: {result[\"drift_detected\"]}')
print(f'Baseline: {result[\"baseline_precision\"]:.3f}')
"
```

#### Cron Job Status prüfen

```bash
# Cron Jobs anzeigen
crontab -l

# System-weite Cron Jobs für Golden Tests
sudo crontab -l | grep golden

# Cron Service Status
systemctl status cronie  # oder systemd-cron je nach Distribution

# Letzte Ausführung prüfen
grep "golden.*test" /var/log/cron.log 2>/dev/null || echo "No cron logs found"
```

#### Drift Alert Interpretation

```bash
# Drift Log prüfen (falls gespeichert)
tail -20 /var/log/cognitive-memory/drift.log

# Model Drift Tabelle abfragen
psql -U mcp_user -d cognitive_memory -c "
SELECT date, precision_at_5, drift_detected, baseline_precision
FROM model_drift_log
ORDER BY date DESC
LIMIT 10;"

# Drift Statistics
psql -U mcp_user -d cognitive_memory -c "
SELECT
    COUNT(*) as total_checks,
    COUNT(CASE WHEN drift_detected THEN 1 END) as drift_count,
    AVG(precision_at_5) as avg_precision,
    MAX(precision_at_5) as max_precision,
    MIN(precision_at_5) as min_precision
FROM model_drift_log
WHERE date >= CURRENT_DATE - INTERVAL '30 days';
"
```

## 4. Budget Monitoring

### CLI Dashboard Commands

**Module:** `mcp_server.budget.cli`
**Purpose:** Real-time Budget monitoring und cost tracking

#### Budget Status Dashboard

```bash
# Interactive Dashboard starten
poetry run python -m mcp_server.budget dashboard

# Quick Status (non-interactive)
poetry run python -m mcp_server.budget status

# Kosten der letzten 30 Tage
poetry run python -m mcp_server.budget breakdown --days 30

# Monats-Projektion anzeigen
poetry run python -m mcp_server.budget projection
```

#### Cost Analysis Commands

```bash
# Detaillierte Cost Breakdown nach API
poetry run python -m mcp_server.budget breakdown --api openai_embeddings
poetry run python -m mcp_server.budget breakdown --api haiku_evaluation
poetry run python -m mcp_server.budget breakdown --api gpt4o_judge

# Kosten nach Zeitraum
poetry run python -m mcp_server.budget breakdown --days 7    # Letzte Woche
poetry run python -m mcp_server.budget breakdown --days 30   # Letzter Monat
poetry run python -m mcp_server.budget breakdown --days 90   # Letzte 3 Monate

# Cost Trends anzeigen
poetry run python -m mcp_server.budget trends --days 30
```

#### Budget Alert Thresholds

**Standard Alerts:**
- 80% Warning: €8 projected monthly cost
- 100% Critical: €10 projected monthly cost

```bash
# Alert konfigurieren
poetry run python -m mcp_server.budget config --threshold-warning 8
poetry run python -m mcp_server.budget config --threshold-critical 10

# Alert Status prüfen
poetry run python -m mcp_server.budget alerts status

# Manual Alert Test
poetry run python -m mcp_server.budget alerts test
```

#### Cost Interpretation

```bash
# API Cost Log abfragen
psql -U mcp_user -d cognitive_memory -c "
SELECT
    api_name,
    SUM(num_calls) as total_calls,
    SUM(tokens) as total_tokens,
    SUM(cost_eur) as total_cost,
    AVG(cost_eur) as avg_cost_per_call
FROM api_cost_log
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY api_name
ORDER BY total_cost DESC;"

# Tagesbasierte Kostenentwicklung
psql -U mcp_user -d cognitive_memory -c "
SELECT
    date,
    SUM(cost_eur) as daily_cost,
    SUM(SUM(cost_eur)) OVER (ORDER BY date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) as rolling_30day_cost
FROM api_cost_log
WHERE date >= CURRENT_DATE - INTERVAL '60 days'
GROUP BY date
ORDER BY date DESC
LIMIT 30;"
```

## 5. Ground Truth Maintenance

### Streamlit UI Management

**UI:** Ground Truth Collection Interface
**Purpose:** Label neue Queries und manage Golden Test Set

#### Streamlit UI starten

```bash
# UI starten (im Projektverzeichnis)
cd /path/to/i-o
poetry run streamlit run mcp_server/ui/ground_truth_app.py

# UI mit custom Port starten
poetry run streamlit run mcp_server/ui/ground_truth_app.py --server.port 8501

# UI im Background starten
nohup poetry run streamlit run mcp_server/ui/ground_truth_app.py --server.headless true > /var/log/streamlit.log 2>&1 &

# UI Prozess beenden
pkill -f "streamlit.*ground_truth_app.py"
```

#### Ground Truth Datenbank-Management

```bash
# Aktuelle Ground Truth Statistik
psql -U mcp_user -d cognitive_memory -c "
SELECT
    COUNT(*) as total_queries,
    COUNT(CASE WHEN judge1_score IS NOT NULL AND judge2_score IS NOT NULL THEN 1 END) as dual_judged,
    COUNT(CASE WHEN query_type = 'short' THEN 1 END) as short_queries,
    COUNT(CASE WHEN query_type = 'medium' THEN 1 END) as medium_queries,
    COUNT(CASE WHEN query_type = 'long' THEN 1 END) as long_queries
FROM ground_truth;"

# Quality Score Verteilung
psql -U mcp_user -d cognitive_memory -c "
SELECT
    AVG(judge1_score) as avg_judge1,
    AVG(judge2_score) as avg_judge2,
    AVG(kappa_score) as avg_kappa,
    STDDEV(kappa_score) as kappa_std
FROM ground_truth
WHERE judge1_score IS NOT NULL AND judge2_score IS NOT NULL;"

# Neue Queries ohne Dual Judge Scores
psql -U mcp_user -d cognitive_memory -c "
SELECT query_id, query_text, created_at
FROM ground_truth
WHERE judge1_score IS NULL OR judge2_score IS NULL
ORDER BY created_at ASC
LIMIT 10;"
```

#### Dual Judge Review Workflow

```bash
# Batch Dual Judge Evaluation (für ungelabelte Queries)
poetry run python -c "
from mcp_server.tools.store_dual_judge_scores import batch_evaluate_queries
result = batch_evaluate_queries(limit=10)
print(f'Evaluated {result[\"evaluated_count\"]} queries')
print(f'Average Kappa: {result[\"avg_kappa\"]:.3f}')
"

# IRR (Inter-Rater Reliability) Report
psql -U mcp_user -d cognitive_memory -c "
SELECT
    DATE_TRUNC('week', created_at) as week,
    COUNT(*) as queries_evaluated,
    AVG(kappa_score) as avg_kappa,
    COUNT(CASE WHEN kappa_score > 0.70 THEN 1 END) as acceptable_kappa_count
FROM ground_truth
WHERE judge1_score IS NOT NULL AND judge2_score IS NOT NULL
GROUP BY DATE_TRUNC('week', created_at)
ORDER BY week DESC
LIMIT 8;"
```

#### Golden Test Set Management

```bash
# Golden Test Set Größe und Qualität
psql -U mcp_user -d cognitive_memory -c "
SELECT
    COUNT(*) as total_queries,
    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_queries,
    COUNT(CASE WHEN status = 'review' THEN 1 END) as review_queries,
    AVG(difficulty_score) as avg_difficulty
FROM golden_test_set;"

# Golden Test Update aus Ground Truth
poetry run python -c "
from mcp_server.db.golden_test_manager import update_golden_test_from_ground_truth
result = update_golden_test_from_ground_truth()
print(f'Updated {result[\"updated_count\"]} queries in golden test set')
"
```

## 6. Common Operational Tasks

### Working Memory Management

```bash
# Working Memory Status prüfen
poetry run python -c "
from mcp_server.db.connection import get_connection
conn = get_connection()
cur = conn.cursor()
cur.execute('SELECT COUNT(*) as items FROM working_memory')
count = cur.fetchone()[0]
print(f'Working Memory Items: {count}')
cur.close()
conn.close()
"

# Working Memory clearen (falls erforderlich)
poetry run python -c "
from mcp_server.tools.update_working_memory import clear_working_memory
result = clear_working_memory()
print(f'Cleared {result[\"cleared_count\"]} items')
"

# Working Memory Capacity prüfen (LRU limit)
psql -U mcp_user -d cognitive_memory -c "
SELECT
    COUNT(*) as current_items,
    MAX(created_at) as oldest_item,
    importance_avg
FROM working_memory;"
```

### Episode Memory Review

```bash
# Episode Memory Statistics
psql -U mcp_user -d cognitive_memory -c "
SELECT
    COUNT(*) as total_episodes,
    AVG(reward_score) as avg_reward,
    COUNT(CASE WHEN reward_score > 0.7 THEN 1 END) as positive_episodes,
    COUNT(CASE WHEN embedding_status = 'completed' THEN 1 END) as embedded_episodes
FROM episode_memory
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days';"

# Hoch-Performante Episodes finden
psql -U mcp_user -d cognitive_memory -c "
SELECT query, reward_score, reflection_summary
FROM episode_memory
WHERE reward_score > 0.8
  AND created_at >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY reward_score DESC
LIMIT 5;"

# Episode Memory Cleanup (sehr alte, irrelevante Episodes)
psql -U mcp_user -d cognitive_memory -c "
DELETE FROM episode_memory
WHERE reward_score < 0.3
  AND created_at < CURRENT_DATE - INTERVAL '90 days'
RETURNING COUNT(*) as deleted_episodes;"
```

### L2 Insights Exploration

```bash
# L2 Insights Statistics
psql -U mcp_user -d cognitive_memory -c "
SELECT
    COUNT(*) as total_insights,
    AVG(fidelity_score) as avg_fidelity,
    COUNT(CASE WHEN fidelity_score > 0.8 THEN 1 END) as high_fidelity,
    COUNT(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) as recent_insights
FROM l2_insights;"

# Low-Quality L2 Insights finden (für Review)
psql -U mcp_user -d cognitive_memory -c "
SELECT id, content_preview, fidelity_score, created_at
FROM l2_insights
WHERE fidelity_score < 0.5
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY fidelity_score ASC
LIMIT 10;"

# Insights nach Topics/Clusters
poetry run python -c "
from mcp_server.utils.insight_analyzer import cluster_insights_by_similarity
clusters = cluster_insights_by_similarity(top_k=50)
for i, cluster in enumerate(clusters[:5]):
    print(f'Cluster {i+1}: {len(cluster[\"insights\"])} insights')
    print(f'  Sample: {cluster[\"sample_insight\"][:100]}...')
"
```

### System Performance Monitoring

```bash
# Database Performance
psql -U mcp_user -d cognitive_memory -c "
SELECT
    schemaname,
    tablename,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes
FROM pg_stat_user_tables
ORDER BY n_tup_ins + n_tup_upd + n_tup_del DESC;"

# Index Performance
psql -U mcp_user -d cognitive_memory -c "
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;"

# Memory Usage
psql -U mcp_user -d cognitive_memory -c "
SELECT
    datname,
    numbackends,
    xact_commit,
    xact_rollback,
    blks_read,
    blks_hit,
    tup_returned,
    tup_fetched
FROM pg_stat_database
WHERE datname = 'cognitive_memory';"
```

---

*Operations Manual erstellt am 2025-11-24*
*Projekt: Cognitive Memory System v3.1.0-Hybrid*
