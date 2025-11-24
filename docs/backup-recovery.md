# Backup & Recovery Guide

**Version:** 3.1.0-Hybrid
**Ziel:** Disaster Recovery Procedures mit RTO <1h und RPO <24h

---

## Überblick

Diese Dokumentation beschreibt die Backup- und Recovery-Strategie für die Cognitive Memory PostgreSQL-Datenbank. Die Strategie erfüllt NFR004 (Disaster Recovery) mit RTO <1h und RPO <24h.

### Dual Backup Approach

1. **PostgreSQL pg_dump Backups (vollständig):**
   - Tägliche automatisierte Backups mit pg_dump
   - Custom Format (-Fc): komprimiert, parallel restore möglich
   - Enthält ALLE Daten: L2 Insights, Embeddings, Ground Truth, Metadata
   - 7-day Retention (lokales Disk)

2. **L2 Insights Git Export (Text-only Fallback):**
   - Optional: Täglicher Export von L2 Insights (Content + Metadata)
   - OHNE Embeddings (zu groß für Git, können re-generiert werden)
   - Git-basierte Versionierung
   - Niedrige Kosten (~1-2 MB vs. ~2GB pro Backup)

---

## Backup-Strategie Details

### 1. PostgreSQL pg_dump Backups

**Schedule:** Täglich 3 Uhr nachts via Cron
**Tool:** `pg_dump` (native PostgreSQL Backup)
**Format:** Custom Format (`-Fc`)
**Location:** `/backups/postgres/cognitive_memory_YYYY-MM-DD.dump`
**Retention:** 7 Tage (automatische Rotation)
**Geschätzte Größe:** ~1-2 GB pro Backup (10K L2 Insights + Embeddings)

**Cron Job:**
```bash
0 3 * * * /home/user/i-o/scripts/backup_postgres.sh >> /var/log/cognitive-memory/backup.log 2>&1
```

**Script Location:** `/home/user/i-o/scripts/backup_postgres.sh`

**Sicherheitsmerkmale:**
- Backup-Dateien: `chmod 600` (owner-only read/write)
- Backup-Verzeichnis: `chmod 700` (owner-only access)
- DB-Credentials: Geladen aus `.env` (nicht hardcoded)
- Lock-File: Verhindert concurrent execution (flock)

**Logging:**
- Log-Datei: `/var/log/cognitive-memory/backup.log`
- Logged Metrics: timestamp, file size, duration, success/failure
- Consecutive Failures: 2+ Failures → ERROR Level Escalation

### 2. L2 Insights Git Export (Optional)

**Schedule:** Täglich (zusammen mit pg_dump Backup)
**Tool:** `export_l2_insights.py` (Python Script)
**Output:** `/memory/l2-insights/YYYY-MM-DD.json`
**Konfiguration:** `config.yaml` → `backup.git_export_enabled: true/false`

**Was wird exportiert:**
- L2 Insights: `id`, `content`, `metadata`, `created_at`, `source_ids`
- **NICHT exportiert:** `embedding_vector` (1536 dimensions, ~3-6 KB pro Insight)

**Rationale für Embedding-Exclusion:**
- Embeddings können re-generiert werden via OpenAI API
- Kosten für Regeneration: ~10K insights × €0.00002 = €0.20 (einmalig)
- Git-Export bleibt klein: ~1-2 MB vs. ~2GB mit Embeddings

**Aktivierung:**
```yaml
# config.yaml
backup:
  git_export_enabled: true
```

**Manuelle Ausführung:**
```bash
python /home/user/i-o/scripts/export_l2_insights.py
```

---

## Restore-Prozedur

### Szenario 1: Standard Recovery (Vollständiger Restore von pg_dump)

**RTO:** <1 Stunde
**RPO:** <24 Stunden (täglich Backups)
**Use Case:** Disk Failure, Datenverlust, Migration zu neuem Server

#### Schritt 1: Backup-Datei identifizieren

```bash
# Liste alle verfügbaren Backups
ls -lh /backups/postgres/

# Beispiel Output:
# cognitive_memory_2025-11-18.dump
# cognitive_memory_2025-11-17.dump
# ...
```

#### Schritt 2: Database vorbereiten

**Option A: Drop und re-create (Clean Install):**
```bash
# PostgreSQL Connection mit Superuser
psql -U postgres

# Drop existing database (WARNING: Alle Daten verloren!)
DROP DATABASE IF EXISTS cognitive_memory;

# Re-create database
CREATE DATABASE cognitive_memory OWNER mcp_user;

# Enable pgvector extension
\c cognitive_memory
CREATE EXTENSION IF NOT EXISTS vector;

# Exit psql
\q
```

**Option B: Restore über existierende Database (pg_restore -c):**
```bash
# pg_restore mit --clean flag
# Löscht existierende Objects vor Restore (weniger destruktiv als DROP DATABASE)
pg_restore -U mcp_user -d cognitive_memory -c -v /backups/postgres/cognitive_memory_2025-11-18.dump
```

#### Schritt 3: Restore ausführen

```bash
# Full Restore mit Verbose Output
pg_restore \
  -U mcp_user \
  -d cognitive_memory \
  -v \
  /backups/postgres/cognitive_memory_2025-11-18.dump

# Mit Passwort-Prompt (falls PGPASSWORD nicht gesetzt):
PGPASSWORD=your_password pg_restore -U mcp_user -d cognitive_memory -v /backups/postgres/cognitive_memory_2025-11-18.dump
```

**Restore-Optionen erklärt:**
- `-U mcp_user`: PostgreSQL User
- `-d cognitive_memory`: Target Database
- `-v`: Verbose (zeigt Fortschritt)
- `-c`: Clean (drop objects before restore) - **optional**
- `-j 4`: Parallel Restore mit 4 Workers - **optional, für große Backups**

#### Schritt 4: Verify Restore

```bash
# Connect zu restored database
psql -U mcp_user -d cognitive_memory

# Check row counts
SELECT COUNT(*) FROM l2_insights;
SELECT COUNT(*) FROM ground_truth;
SELECT COUNT(*) FROM l0_raw;

# Check latest timestamp (verify recent data)
SELECT MAX(created_at) FROM l2_insights;

# Exit psql
\q
```

**Erwartete Ergebnisse:**
- Row counts sollten mit Production übereinstimmen (vor Datenverlust)
- Timestamps zeigen Daten bis zu 24h vor Restore

#### Schritt 5: Restart MCP Server

```bash
# Restart MCP Server um connection pool zu refreshen
# (Methode abhängig von Deployment - systemd, docker, etc.)
systemctl restart mcp-server  # Beispiel für systemd
```

---

### Szenario 2: L2 Insights Fallback Recovery (Git Export)

**RTO:** <2 Stunden
**RPO:** <24 Stunden
**Use Case:** pg_dump Backup korrupt oder nicht verfügbar, aber Git-Export vorhanden

#### Schritt 1: L2 Insights JSON laden

```bash
# Neueste JSON Export finden
ls -lh /memory/l2-insights/

# JSON laden
cat /memory/l2-insights/2025-11-18.json > l2_backup.json
```

#### Schritt 2: Database vorbereiten (wie Szenario 1)

```bash
psql -U postgres
DROP DATABASE IF EXISTS cognitive_memory;
CREATE DATABASE cognitive_memory OWNER mcp_user;
\c cognitive_memory
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

#### Schritt 3: L2 Insights importieren (Python Script)

**Import-Script erstellen:** `restore_l2_from_json.py`

```python
#!/usr/bin/env python3
import json
import psycopg2
from datetime import datetime

# Load JSON export
with open('l2_backup.json', 'r') as f:
    data = json.load(f)

# Connect to database
conn = psycopg2.connect("postgresql://mcp_user:password@localhost/cognitive_memory")
cursor = conn.cursor()

# Insert L2 insights (ohne embeddings)
for insight in data['insights']:
    cursor.execute("""
        INSERT INTO l2_insights (id, content, metadata, created_at, source_ids)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        insight['id'],
        insight['content'],
        insight['metadata'],
        datetime.fromisoformat(insight['created_at']),
        insight['source_ids']
    ))

conn.commit()
print(f"Imported {len(data['insights'])} L2 insights")
```

#### Schritt 4: Embeddings regenerieren

**WICHTIG:** Embeddings fehlen nach JSON Import → müssen regeneriert werden

```python
# Regenerate embeddings via OpenAI API
import openai

cursor.execute("SELECT id, content FROM l2_insights WHERE embedding IS NULL")
insights = cursor.fetchall()

for insight_id, content in insights:
    # Generate embedding via OpenAI API
    response = openai.Embedding.create(
        input=content,
        model="text-embedding-3-small"
    )
    embedding = response['data'][0]['embedding']

    # Update l2_insights table
    cursor.execute("""
        UPDATE l2_insights
        SET embedding = %s::vector
        WHERE id = %s
    """, (embedding, insight_id))

conn.commit()
```

**Kosten:**
- ~10K insights × €0.00002 pro Embedding = **€0.20**
- Dauer: ~20-30min (API Rate Limits)

#### Schritt 5: Verify und Test

```bash
psql -U mcp_user -d cognitive_memory

# Check L2 insights count
SELECT COUNT(*) FROM l2_insights;

# Check embeddings restored
SELECT COUNT(*) FROM l2_insights WHERE embedding IS NOT NULL;

# Exit
\q
```

---

## Backup Integrity Testing

### Test-Database Restore (Empfohlen: monatlich)

```bash
# Step 1: Create test database
createdb -U mcp_user cognitive_memory_test

# Step 2: Restore latest backup to test DB
pg_restore -U mcp_user -d cognitive_memory_test -v /backups/postgres/cognitive_memory_$(date +%Y-%m-%d).dump

# Step 3: Verify data integrity
psql -U mcp_user -d cognitive_memory_test -c "SELECT COUNT(*) FROM l2_insights;"

# Step 4: Compare with production
psql -U mcp_user -d cognitive_memory -c "SELECT COUNT(*) FROM l2_insights;"

# Step 5: Cleanup test database
dropdb -U mcp_user cognitive_memory_test
```

**Erfolg:** Row counts stimmen überein zwischen Test und Production

---

## Troubleshooting

### Problem 1: Backup Script fehlschlägt

**Symptome:**
- `/var/log/cognitive-memory/backup.log` zeigt ERROR
- Keine neuen Backup-Dateien in `/backups/postgres/`

**Diagnose:**
```bash
# Check backup logs
tail -50 /var/log/cognitive-memory/backup.log

# Check disk space
df -h /backups/postgres/

# Check PostgreSQL connection
psql -U mcp_user -d cognitive_memory -c "SELECT 1;"
```

**Häufige Ursachen:**
1. **Disk Space Full:**
   - Lösung: Alte Backups manuell löschen, Disk erweitern
   - Command: `find /backups/postgres/ -type f -mtime +7 -delete`

2. **PostgreSQL Connection Error:**
   - Check: `.env` Datei mit DATABASE_URL vorhanden?
   - Check: PostgreSQL läuft? `systemctl status postgresql`
   - Check: Credentials korrekt? `psql -U mcp_user -d cognitive_memory`

3. **Permission Denied:**
   - Check: Backup-Verzeichnis existiert? `ls -ld /backups/postgres/`
   - Check: User hat Schreibrechte? `touch /backups/postgres/test && rm /backups/postgres/test`
   - Fix: `sudo chown -R $USER:$USER /backups/postgres/ && chmod 700 /backups/postgres/`

### Problem 2: Restore schlägt fehl

**Symptome:**
- `pg_restore` gibt Fehler aus
- Restore incomplete (fehlende Tabellen oder Rows)

**Diagnose:**
```bash
# Check backup file integrity
file /backups/postgres/cognitive_memory_2025-11-18.dump
# Expected: "PostgreSQL custom database dump"

# Check backup file size
ls -lh /backups/postgres/cognitive_memory_2025-11-18.dump
# Expected: >1 MB (besser: 100MB-2GB)
```

**Häufige Ursachen:**
1. **Corrupted Backup File (<1 MB):**
   - Backup wurde unterbrochen (Kill signal, Disk voll)
   - Lösung: Verwende älteren Backup (gestern)
   - Prevention: Backup script validiert File Size >1MB

2. **Permission Errors:**
   - Restore User hat keine CREATE Rechte auf Database
   - Lösung: Use database owner (mcp_user) oder superuser

3. **Database existiert nicht:**
   - `pg_restore` benötigt existierende Database
   - Lösung: `createdb -U mcp_user cognitive_memory` vor Restore

### Problem 3: Embeddings fehlen nach Git-Restore

**Symptome:**
- `SELECT COUNT(*) FROM l2_insights WHERE embedding IS NULL` zeigt >0 Rows
- Hybrid Search gibt keine Ergebnisse

**Diagnose:**
```bash
psql -U mcp_user -d cognitive_memory <<EOF
SELECT
  COUNT(*) AS total_insights,
  COUNT(embedding) AS with_embeddings,
  COUNT(*) - COUNT(embedding) AS missing_embeddings
FROM l2_insights;
EOF
```

**Lösung:**
- Embeddings regenerieren via OpenAI API (siehe Szenario 2, Schritt 4)
- Kosten: ~€0.20 für 10K insights
- Dauer: ~20-30min

---

## RTO/RPO Spezifikationen

### Recovery Time Objective (RTO): <1 Stunde

**Zeitplan:**
1. Backup-Datei identifizieren: **~2 min**
2. Database vorbereiten (drop/create): **~3 min**
3. pg_restore ausführen (~10GB): **~5-10 min**
4. Verify Restore (row counts, timestamps): **~5 min**
5. Restart MCP Server: **~2 min**
6. **Total: ~17-22 min** (erfüllt <1h target)

**Worst-Case mit L2 Git Fallback:**
- L2 JSON Import: ~5 min
- Embedding Regeneration: ~20-30 min
- **Total: ~30-40 min** (erfüllt <1h target)

### Recovery Point Objective (RPO): <24 Stunden

**Datenverlust:**
- Tägliche Backups um 3 AM
- Worst-Case Datenverlust: Queries zwischen letztem Backup und Ausfall
- Maximum: **24 Stunden** (akzeptabel für Personal Use)

**Beispiel:**
- Backup: 2025-11-18 3:00 AM
- Disk Failure: 2025-11-18 18:00 PM
- Datenverlust: 15 Stunden (3 AM → 6 PM queries verloren)

---

## Monitoring & Alerts

### Backup Success Tracking

**Logs prüfen:**
```bash
# Zeige letzte 20 Backup-Logs
tail -20 /var/log/cognitive-memory/backup.log

# Suche nach ERROR
grep ERROR /var/log/cognitive-memory/backup.log

# Check consecutive failures
cat /var/log/cognitive-memory/.backup_failures
```

**Success Criteria:**
- Backup file erstellt: `/backups/postgres/cognitive_memory_$(date +%Y-%m-%d).dump`
- File size >1 MB (besser: 100MB-2GB)
- Backup duration <5min (NFR Performance Target)
- Exit code 0 (success)

### Consecutive Failure Alerts

**Mechanismus:**
- Backup script trackt Failures in `/var/log/cognitive-memory/.backup_failures`
- 2+ consecutive Failures → ERROR Level log
- Manual intervention erforderlich

**Alert Check:**
```bash
# Check failure counter
if [ -f /var/log/cognitive-memory/.backup_failures ]; then
  failures=$(cat /var/log/cognitive-memory/.backup_failures)
  if [ $failures -ge 2 ]; then
    echo "ALERT: $failures consecutive backup failures!"
  fi
fi
```

---

## Best Practices

### 1. Test Restore Regularly (monatlich)

- Verify Backups sind nicht korrupt
- Practice Restore-Prozedur (Reduce RTO bei echtem Ausfall)
- Use Test-Database (nicht Production)

### 2. Monitor Disk Space

```bash
# Check backup directory disk usage
df -h /backups/postgres/

# Check total backup size
du -sh /backups/postgres/

# Expected: ~14GB (7 days × ~2GB)
```

### 3. Secure Backups

- Backup-Dateien: `chmod 600` (owner-only)
- Backup-Verzeichnis: `chmod 700` (owner-only)
- Credentials: `.env` Datei (nicht hardcoded)
- Log-Dateien: Keine Passwörter im Log

### 4. L2 Git Export aktivieren (Optional, empfohlen)

```yaml
# config.yaml
backup:
  git_export_enabled: true
```

**Vorteile:**
- Zusätzlicher Fallback (Git-basiert)
- Niedrige Kosten (~1-2 MB)
- Embeddings re-generierbar (~€0.20)

---

## 6. Disaster Recovery Checklist

### Vollständige System-Wiederherstellung

**Verwende diese Checkliste bei complete system failure oder data corruption.**

#### Phase 1: Vorbereitung (2-5 Minuten)

- [ ] **Stop MCP Server**
  ```bash
  sudo systemctl stop cognitive-memory-mcp
  ```

- [ ] **aktuellen (korrupten) Zustand sichern**
  ```bash
  # Backup-Verzeichnis für corrupted data erstellen
  CORRUPTED_DIR="/tmp/corrupted_state_$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$CORRUPTED_DIR"

  # Database dump (falls noch möglich)
  sudo -u postgres pg_dump -Fc cognitive_memory > "$CORRUPTED_DIR/corrupted_backup.dump" 2>/dev/null || echo "Could not create corrupted backup"

  # Wichtige Konfigurationsdateien sichern
  cp .env.development "$CORRUPTED_DIR/"
  cp .mcp.json "$CORRUPTED_DIR/" 2>/dev/null || true
  ```

#### Phase 2: Restore von neuestem Backup (5-15 Minuten)

- [ ] **neuestes Backup identifizieren**
  ```bash
  # Liste verfügbare Backups
  ls -lah /backups/postgres/

  # Neuestes valides Backup auswählen (nicht <1MB)
  LATEST_BACKUP=$(ls -t /backups/postgres/*.dump | head -1)
  BACKUP_SIZE=$(stat -c%s "$LATEST_BACKUP")

  if [ $BACKUP_SIZE -lt 1048576 ]; then  # <1MB
    echo "WARNING: Backup file seems too small ($(stat -c%s "$LATEST_BACKUP") bytes)"
    echo "Consider using previous backup:"
    ls -lah /backups/postgres/*.dump | head -5
  fi
  ```

- [ ] **Database neu erstellen**
  ```bash
  # Alte Database löschen (mit Bestätigung)
  sudo -u postgres dropdb cognitive_memory
  echo "Dropped corrupted database"

  # Neue Database erstellen
  sudo -u postgres createdb -O mcp_user cognitive_memory
  echo "Created new database"

  # Extensions aktivieren
  sudo -u postgres psql -d cognitive_memory -c "CREATE EXTENSION IF NOT EXISTS vector;"
  echo "Enabled pgvector extension"
  ```

- [ ] **Restore ausführen**
  ```bash
  # Restore mit verbose output für Fortschrittsanzeige
  echo "Starting restore from: $LATEST_BACKUP"
  time sudo -u postgres pg_restore \
    -U mcp_user \
    -d cognitive_memory \
    -v \
    -j 4 \
    "$LATEST_BACKUP"

  if [ $? -eq 0 ]; then
    echo "✅ Restore completed successfully"
  else
    echo "❌ Restore failed - check logs above"
    exit 1
  fi
  ```

#### Phase 3: Verification (5-10 Minuten)

- [ ] **Data Integrity prüfen**
  ```bash
  # Row counts für wichtige Tabellen
  sudo -u postgres psql -d cognitive_memory -c "
  SELECT
    'l2_insights' as table_name, COUNT(*) as row_count
  FROM l2_insights
  UNION ALL
  SELECT
    'l0_raw' as table_name, COUNT(*) as row_count
  FROM l0_raw
  UNION ALL
  SELECT
    'ground_truth' as table_name, COUNT(*) as row_count
  FROM ground_truth
  UNION ALL
  SELECT
    'working_memory' as table_name, COUNT(*) as row_count
  FROM working_memory
  UNION ALL
  SELECT
    'episode_memory' as table_name, COUNT(*) as row_count
  FROM episode_memory
  ORDER BY row_count DESC;"

  # Latest timestamps prüfen
  echo -e "\nLatest timestamps:"
  sudo -u postgres psql -d cognitive_memory -c "
  SELECT
    'l2_insights' as table_name, MAX(created_at) as latest_timestamp
  FROM l2_insights
  UNION ALL
  SELECT
    'l0_raw' as table_name, MAX(created_at) as latest_timestamp
  FROM l0_raw
  ORDER BY latest_timestamp DESC;"
  ```

- [ ] **Indexe prüfen**
  ```bash
  # Wichtige Indexe vorhanden?
  sudo -u postgres psql -d cognitive_memory -c "
  SELECT indexname, tablename
  FROM pg_indexes
  WHERE tablename IN ('l2_insights', 'l0_raw', 'working_memory')
  ORDER BY tablename, indexname;"
  ```

- [ ] **Embedding Vektor prüfen**
  ```bash
  # Sample der Embeddings prüfen (sollte nicht NULL sein)
  sudo -u postgres psql -d cognitive_memory -c "
  SELECT
    COUNT(*) as total_insights,
    COUNT(embedding) as with_embeddings,
    COUNT(*) - COUNT(embedding) as missing_embeddings,
    ROUND(COUNT(embedding) * 100.0 / COUNT(*), 2) as embedding_pct
  FROM l2_insights;"

  # Falls Embeddings fehlen: Regeneration Plan anzeigen
  MISSING_EMBEDDINGS=$(sudo -u postgres psql -d cognitive_memory -t -c "
  SELECT COUNT(*) - COUNT(embedding) FROM l2_insights;")

  if [ "$MISSING_EMBEDDINGS" -gt 0 ]; then
    echo "⚠️  WARNING: $MISSING_EMBEDDINGS insights missing embeddings"
    echo "Run embedding regeneration:"
    echo "poetry run python -c \"
from mcp_server.utils.embedding_regenerator import regenerate_missing_embeddings \\
result = regenerate_missing_embeddings() \\
print(f'Regenerated {result[\"count\"]} embeddings, cost: €{result[\"cost\"]:.2f}')\""
  fi
  ```

#### Phase 4: Service Recovery (2-5 Minuten)

- [ ] **MCP Server neustarten**
  ```bash
  # Service starten
  sudo systemctl start cognitive-memory-mcp

  # Status prüfen
  sleep 5
  systemctl status cognitive-memory-mcp --no-pager

  # Auf erfolgreichen Start warten
  timeout 30s bash -c 'while ! systemctl is-active cognitive-memory-mcp; do sleep 1; done'

  if systemctl is-active cognitive-memory-mcp; then
    echo "✅ MCP Server started successfully"
  else
    echo "❌ MCP Server failed to start - check logs:"
    journalctl -u cognitive-memory-mcp --since "5 minutes ago"
  fi
  ```

- [ ] **Logs prüfen**
  ```bash
  # Startup Logs auf Fehler prüfen
  journalctl -u cognitive-memory-mcp --since "5 minutes ago" -p err
  ```

#### Phase 5: Health Checks (5-10 Minuten)

- [ ] **MCP Tools prüfen**
  ```bash
  # Manuelles Health Check über Python
  cd /path/to/i-o
  poetry run python -c "
  from mcp_server.tools.ping import execute_ping
  try:
      result = execute_ping()
      print('✅ MCP Tools accessible')
  except Exception as e:
      print(f'❌ MCP Tools not accessible: {e}')
  "
  ```

- [ ] **Database Connection aus Anwendung prüfen**
  ```bash
  # Connection Test
  poetry run python -c "
  from mcp_server.db.connection import get_connection
  try:
      conn = get_connection()
      cursor = conn.cursor()
      cursor.execute('SELECT COUNT(*) FROM l2_insights')
      count = cursor.fetchone()[0]
      print(f'✅ Database connection successful, {count} L2 insights found')
      conn.close()
  except Exception as e:
      print(f'❌ Database connection failed: {e}')
  "
  ```

- [ ] **Functionality Test (optional)**
  ```bash
  # Einfache Search Query Test
  poetry run python -c "
  from mcp_server.tools.hybrid_search import execute_hybrid_search
  try:
      result = execute_hybrid_search('test query', top_k=3)
      print(f'✅ Search functionality working, found {len(result)} results')
  except Exception as e:
      print(f'❌ Search functionality failed: {e}')
  "
  ```

#### Abschluss

- [ ] **Recovery dokumentieren**
  ```bash
  echo "=== DISASTER RECOVERY COMPLETED ===" >> /var/log/cognitive-memory/recovery.log
  echo "Timestamp: $(date)" >> /var/log/cognitive-memory/recovery.log
  echo "Backup used: $LATEST_BACKUP" >> /var/log/cognitive-memory/recovery.log
  echo "Database rows restored: $(sudo -u postgres psql -d cognitive_memory -t -c 'SELECT COUNT(*) FROM l2_insights;')" >> /var/log/cognitive-memory/recovery.log
  echo "MCP Server status: $(systemctl is-active cognitive-memory-mcp)" >> /var/log/cognitive-memory/recovery.log
  ```

### Recovery Zeit-Messung

**Erwartete Zeiten:**
- Phase 1 (Vorbereitung): 2-5 min
- Phase 2 (Restore): 5-15 min
- Phase 3 (Verification): 5-10 min
- Phase 4 (Service Recovery): 2-5 min
- Phase 5 (Health Checks): 5-10 min

**Total: 19-45 min (im RTO <1h Target)**

### Recovery Script (Automatisiert)

Für wiederkehrende Recoverys kann das folgende Script verwendet werden:

```bash
#!/bin/bash
# disaster_recovery.sh
set -e  # Bei Fehlern abbrechen

echo "=== DISASTER RECOVERY STARTED ==="
echo "Timestamp: $(date)"

# Phase 1: Preparation
echo "Phase 1: Preparation..."
sudo systemctl stop cognitive-memory-mcp

CORRUPTED_DIR="/tmp/corrupted_state_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$CORRUPTED_DIR"
sudo -u postgres pg_dump -Fc cognitive_memory > "$CORRUPTED_DIR/corrupted_backup.dump" 2>/dev/null || true
cp .env.development "$CORRUPTED_DIR/"

# Phase 2: Restore
echo "Phase 2: Restore..."
LATEST_BACKUP=$(ls -t /backups/postgres/*.dump | head -1)

sudo -u postgres dropdb cognitive_memory || true
sudo -u postgres createdb -O mcp_user cognitive_memory
sudo -u postgres psql -d cognitive_memory -c "CREATE EXTENSION IF NOT EXISTS vector;"

sudo -u postgres pg_restore -U mcp_user -d cognitive_memory -v -j 4 "$LATEST_BACKUP"

# Phase 3: Verification
echo "Phase 3: Verification..."
ROW_COUNT=$(sudo -u postgres psql -d cognitive_memory -t -c 'SELECT COUNT(*) FROM l2_insights;')
echo "Restored $ROW_COUNT L2 insights"

# Phase 4: Service Recovery
echo "Phase 4: Service Recovery..."
sudo systemctl start cognitive-memory-mcp
sleep 10

# Phase 5: Health Checks
echo "Phase 5: Health Checks..."
if systemctl is-active cognitive-memory-mcp >/dev/null; then
    echo "✅ MCP Server running"
else
    echo "❌ MCP Server failed to start"
    exit 1
fi

echo "=== DISASTER RECOVERY COMPLETED ==="
echo "Total time: $SECONDS seconds"
```

---

## Referenzen

- [Source: bmad-docs/tech-spec-epic-3.md#Backup-Manager] - Technical Specification
- [Source: bmad-docs/architecture.md#NFR004-Backup-Strategy] - Architecture Decisions
- [Source: bmad-docs/PRD.md#Backup-Strategy] - Business Requirements
- [PostgreSQL pg_dump Documentation](https://www.postgresql.org/docs/current/app-pgdump.html)
- [PostgreSQL pg_restore Documentation](https://www.postgresql.org/docs/current/app-pgrestore.html)

---

**Letzte Aktualisierung:** 2025-11-18
**Version:** 1.0
**Author:** BMad dev-story workflow
