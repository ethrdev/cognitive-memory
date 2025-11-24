# Production Deployment Checklist

**Cognitive Memory System v3.1.0 - Story 3.7: Production Configuration & Environment Setup**

Dieses Dokument beschreibt alle Schritte für die Production-Deployment des Cognitive Memory Systems. Es basiert auf der Environment-Separation zwischen Development und Production, um sicherzustellen dass Testing keine Production-Daten kontaminiert.

## Überblick

**Production Environment:**
- Database: `cognitive_memory` (PostgreSQL)
- Environment: `ENVIRONMENT=production`
- Config: `config/.env.production` + `config/config.yaml` (production section)
- Log Level: INFO (reduced noise)
- Backups: Daily automated backups (Story 3.6)

**Development Environment:**
- Database: `cognitive_memory_dev` (PostgreSQL)
- Environment: `ENVIRONMENT=development`
- Config: `config/.env.development` + `config/config.yaml` (development section)
- Log Level: DEBUG (verbose for testing)
- Backups: Optional (test data can be recreated)

---

## 1. Pre-Deployment Checklist

Vor dem Production-Deployment müssen folgende Voraussetzungen erfüllt sein:

### 1.1 Infrastructure Requirements

- [ ] **PostgreSQL Server:** Version 15+ installiert und running
- [ ] **pgvector Extension:** Installiert in PostgreSQL
- [ ] **Python:** Version 3.11+ installiert
- [ ] **systemd:** Available für Service Management (Story 3.8)
- [ ] **Disk Space:** Mindestens 10 GB freier Speicherplatz für Database + Backups

### 1.2 Database Setup

- [ ] **Production Database:** `cognitive_memory` existiert
- [ ] **Database User:** `mcp_user` mit Permissions auf `cognitive_memory`
- [ ] **Development Database:** `cognitive_memory_dev` existiert (für Testing)
- [ ] **Migrations:** Alle Migrations auf beiden Databases angewendet
  ```bash
  # Run setup script to create development database
  ./scripts/setup_dev_database.sh

  # Verify both databases have identical schemas
  psql -U mcp_user -d cognitive_memory -c "\dt"
  psql -U mcp_user -d cognitive_memory_dev -c "\dt"
  ```

### 1.3 Environment Configuration

- [ ] **Environment File:** `config/.env.production` erstellt
- [ ] **File Permissions:** `chmod 600 config/.env.production` (owner-only readable)
- [ ] **API Keys:** Real production API keys eingetragen:
  - `OPENAI_API_KEY`: OpenAI API key von https://platform.openai.com/api-keys
  - `ANTHROPIC_API_KEY`: Anthropic API key von https://console.anthropic.com/
- [ ] **Database URL:** PostgreSQL connection string konfiguriert
  ```bash
  DATABASE_URL=postgresql://mcp_user:YOUR_PASSWORD@localhost:5432/cognitive_memory
  ```
- [ ] **PostgreSQL Password:** Secure password gesetzt (nicht das Default-Passwort!)

### 1.4 Backup Strategy (Story 3.6)

- [ ] **Backup Scripts:** `scripts/backup_postgres.sh` und `scripts/export_l2_insights.py` existieren
- [ ] **Backup Directory:** `/home/user/backups/` erstellt mit chmod 700
- [ ] **Cron Jobs:** Configured für automated backups (siehe Section 4.2)
- [ ] **Backup Retention:** Policy definiert (Standard: 7 days für PostgreSQL dumps, 30 days für L2 insights Git exports)

### 1.5 Dependencies

- [ ] **Python Packages:** Alle dependencies installiert via Poetry
  ```bash
  cd /home/user/i-o
  poetry install --no-dev  # Production dependencies only
  ```
- [ ] **Verification:** MCP Server kann importiert werden
  ```bash
  python -c "from mcp_server.config import load_environment; print('OK')"
  ```

---

## 2. Deployment Steps

### 2.1 Environment Setup

1. **Set Production Environment Variable:**
   ```bash
   export ENVIRONMENT=production
   ```

2. **Verify Configuration Loading:**
   ```bash
   python -c "from mcp_server.config import load_environment; config = load_environment(); print(f\"Environment: {config['environment']}, DB: {config['database']['name']}\")"
   ```

   Expected Output:
   ```
   Environment: production, DB: cognitive_memory
   ```

3. **Verify Database Connection:**
   ```bash
   psql -U mcp_user -d cognitive_memory -c "SELECT 1;"
   ```

### 2.2 MCP Server Startup (Manual Test)

1. **Start MCP Server:**
   ```bash
   cd /home/user/i-o
   export ENVIRONMENT=production
   python -m mcp_server
   ```

2. **Verify Startup Logs:**
   - ✓ Environment loaded: production
   - ✓ Database: cognitive_memory
   - ✓ Log Level: INFO
   - ✓ OpenAI API Key: configured
   - ✓ Anthropic API Key: configured

3. **Check for Errors:**
   - ✗ No "FATAL: Configuration error" messages
   - ✗ No "Missing required environment variables" errors
   - ✗ No database connection failures

### 2.3 MCP Server Registration in Claude Code

1. **Update MCP Settings:**
   Edit `~/.config/claude-code/mcp-settings.json`:
   ```json
   {
     "mcpServers": {
       "cognitive-memory": {
         "command": "python",
         "args": ["-m", "mcp_server"],
         "cwd": "/home/user/i-o",
         "env": {
           "ENVIRONMENT": "production"
         }
       }
     }
   }
   ```

2. **Restart Claude Code:** Damit MCP Server neu geladen wird

3. **Verify MCP Server Registration:**
   - Öffne Claude Code
   - Check ob "cognitive-memory" Server in MCP Server Liste erscheint
   - Check ob alle Tools verfügbar sind (7 tools, 5 resources)

### 2.4 Systemd Service Setup (Story 3.8)

**Story 3.8** implementiert MCP Server als systemd Service für Auto-Start beim Boot und Auto-Restart bei Crashes. Dies ist **empfohlen für Production Deployments** zur Maximierung der Service Uptime (NFR004: Reliability).

#### 2.4.1 Service Installation

1. **Automated Installation (Empfohlen):**
   ```bash
   cd /home/user/i-o
   sudo bash scripts/install_service.sh
   ```

   Das Script führt aus:
   - Validiert service file syntax
   - Kopiert service file nach `/etc/systemd/system/`
   - Führt `systemctl daemon-reload` aus
   - Aktiviert service für auto-start

2. **Manual Installation (Alternative):**
   ```bash
   sudo cp systemd/cognitive-memory-mcp.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable cognitive-memory-mcp
   ```

#### 2.4.2 Service Verification

- [ ] **Service File Installed:**
  ```bash
  ls -l /etc/systemd/system/cognitive-memory-mcp.service
  ```

- [ ] **Service Enabled:**
  ```bash
  systemctl is-enabled cognitive-memory-mcp
  # Expected: "enabled"
  ```

- [ ] **Start Service:**
  ```bash
  sudo systemctl start cognitive-memory-mcp
  ```

- [ ] **Verify Running:**
  ```bash
  systemctl status cognitive-memory-mcp
  # Expected: "active (running)"
  ```

- [ ] **Check Logs:**
  ```bash
  journalctl -u cognitive-memory-mcp --since "1 minute ago"
  # Expected: "Production environment loaded"
  ```

#### 2.4.3 Service Management Commands

```bash
# Start/Stop/Restart
sudo systemctl start cognitive-memory-mcp
sudo systemctl stop cognitive-memory-mcp
sudo systemctl restart cognitive-memory-mcp

# Status und Logs
systemctl status cognitive-memory-mcp
journalctl -u cognitive-memory-mcp -f
```

**Detaillierte Dokumentation:** Siehe `systemd-deployment.md` für:
- Troubleshooting
- Health Monitoring (Watchdog)
- Auto-Restart Testing
- Log Management

---

## 3. Post-Deployment Validation

### 3.1 Health Checks

- [ ] **MCP Server Running:** Server startet ohne Errors
- [ ] **Database Connection:** PostgreSQL connection successful
- [ ] **API Keys Valid:** OpenAI und Anthropic API calls funktionieren
- [ ] **Log Output:** Logs zeigen INFO level (nicht DEBUG)

### 3.2 Functional Testing

- [ ] **Test Query via Claude Code:**
  ```
  User: Test the cognitive memory system - store this conversation
  Claude Code: [Should successfully call MCP tools and store data]
  ```

- [ ] **Verify Database Writes:**
  ```bash
  psql -U mcp_user -d cognitive_memory -c "SELECT COUNT(*) FROM l0_raw;"
  psql -U mcp_user -d cognitive_memory -c "SELECT COUNT(*) FROM l2_insights;"
  ```

  Expected: Row counts should increase after test query

- [ ] **Check Logs:**
  ```bash
  # If using systemd (Story 3.8):
  journalctl -u cognitive-memory-mcp -n 50

  # If running manually:
  # Check stderr output for structured JSON logs
  ```

### 3.3 Environment Separation Validation

- [ ] **Production DB Isolation:**
  ```bash
  # Run development environment
  export ENVIRONMENT=development
  python -m mcp_server

  # Verify it connects to cognitive_memory_dev (not cognitive_memory)
  psql -U mcp_user -d cognitive_memory_dev -c "SELECT COUNT(*) FROM l0_raw;"
  ```

- [ ] **No Cross-Contamination:**
  - Development tests schreiben NICHT in Production DB
  - Production queries schreiben NICHT in Development DB

---

## 4. Operational Readiness

### 4.1 Monitoring & Alerting

- [ ] **Log Monitoring:** Logs werden überwacht (manuel oder via systemd journal)
- [ ] **Error Alerting:** Critical errors werden gemeldet
- [ ] **Performance Monitoring:** Slow queries werden geloggt (threshold: 500ms production, 1000ms development)

### 4.2 Backup Automation (Story 3.6)

- [ ] **PostgreSQL Backup Cron Job:**
  ```bash
  # Add to crontab:
  # Daily backup at 2 AM
  0 2 * * * ENVIRONMENT=production /home/user/i-o/scripts/backup_postgres.sh
  ```

- [ ] **L2 Insights Git Export Cron Job:**
  ```bash
  # Add to crontab:
  # Daily export at 3 AM (after DB backup)
  0 3 * * * ENVIRONMENT=production /home/user/i-o/scripts/export_l2_insights.py
  ```

- [ ] **Backup Verification:**
  ```bash
  # Check latest backup exists
  ls -lh /home/user/backups/postgresql/ | tail -5
  ls -lh /home/user/backups/l2_insights_export/ | tail -5
  ```

### 4.3 Model Drift Detection (Story 3.2)

- [ ] **Golden Test Set:** Exists and configured
- [ ] **Drift Detection Cron Job:**
  ```bash
  # Add to crontab:
  # Daily drift detection at 4 AM
  0 4 * * * ENVIRONMENT=production python -m mcp_server.monitoring.drift_check
  ```

### 4.4 Budget Monitoring (Story 3.10)

- [ ] **API Cost Tracking:** Enabled in production
- [ ] **Monthly Budget Alert:** Set to €10/mo
- [ ] **Cost Dashboard:** Accessible for monitoring

#### 4.4.2 Budget Monitoring Setup (Story 3.10)

**Database Setup:**

- [ ] **api_cost_log Table Created:**
  ```bash
  psql -U mcp_user -d cognitive_memory -c "\dt api_cost_log"
  ```
  - Expected: Table exists with schema: id, date, api_name, num_calls, token_count, estimated_cost, created_at
  - Migration 004: Initial table creation
  - Migration 010: Composite index (date DESC, api_name)

- [ ] **API Cost Logging Integrated:**
  - Verify cost logging in all API client functions:
    - `mcp_server/external/openai_client.py` (embeddings): Line ~104
    - `mcp_server/external/anthropic_client.py` (evaluation): Line ~233
    - `mcp_server/external/anthropic_client.py` (reflexion): Line ~429
    - `mcp_server/tools/dual_judge.py` (GPT-4o judge): Line ~162
    - `mcp_server/tools/dual_judge.py` (Haiku judge): Line ~226
  - Test with sample API call:
    ```bash
    python -c "from mcp_server.db.cost_logger import insert_cost_log; insert_cost_log('test_api', 1, 1000, 0.001); print('OK')"
    ```

**Budget Alert Configuration:**

- [ ] **Budget Threshold Configured:**
  ```bash
  # Verify config.yaml settings
  grep -A 5 "^  budget:" config/config.yaml
  ```
  - Expected: monthly_limit_eur: 10.0, alert_threshold_pct: 80
  - Email/Slack configuration (optional): alert_email, alert_slack_webhook
  - SMTP environment variables (if email enabled): SMTP_HOST, SMTP_USER, SMTP_PASSWORD

- [ ] **Budget Alert Cron Job Configured:**
  ```bash
  # Add to crontab for daily budget checks
  crontab -e
  # Add line: 0 9 * * * cd /home/user/i-o && source venv/bin/activate && python -m mcp_server.budget.cli alerts --send >> /var/log/budget-alerts.log 2>&1

  # Verify cron job
  crontab -l | grep budget
  ```
  - Schedule: Daily at 9 AM (adjust as needed)
  - Log output to `/var/log/budget-alerts.log`

**CLI Tool Verification:**

- [ ] **CLI Tool Tested:**
  ```bash
  # Test all CLI commands
  python -m mcp_server.budget.cli dashboard
  python -m mcp_server.budget.cli breakdown --days 7
  python -m mcp_server.budget.cli optimize
  python -m mcp_server.budget.cli alerts
  python -m mcp_server.budget.cli daily --days 7
  ```
  - Expected: All commands execute without errors
  - Budget status displayed correctly
  - Cost breakdown shows API data

#### 4.4.3 Staged Dual Judge Budget Optimization (Story 3.9)

**Monatliche Tasks (Phase 1: Full Dual Judge - Erste 3 Monate):**

- [ ] **Evaluate Transition Eligibility:**
  ```bash
  python scripts/staged_dual_judge_cli.py --evaluate
  ```
  - Check Kappa progress towards ≥0.85 threshold
  - Review transition recommendation
  - Execute transition wenn "READY" status erreicht

**Monatliche Tasks (Phase 2: Single Judge + Spot Checks - Nach Transition):**

- [ ] **Monitor Spot Check Kappa:**
  ```bash
  python scripts/staged_dual_judge_cli.py --status
  ```
  - Verify spot check Kappa ≥0.70 (healthy threshold)
  - Check health status (HEALTHY or LOW)
  - Investigate if LOW status (siehe Troubleshooting)

- [ ] **Verify Cost Reduction:**
  ```bash
  # Compare Month N (Dual) vs Month N+1 (Single Judge)
  psql -U mcp_user -d cognitive_memory -c "
    SELECT DATE_TRUNC('month', date) AS month, SUM(estimated_cost) AS total_cost
    FROM api_cost_log
    WHERE date >= NOW() - INTERVAL '2 months'
    GROUP BY month
    ORDER BY month;
  "
  ```
  - Expected: ~40% cost reduction
  - Month N: €5-10/mo → Month N+1: €2-3/mo

- [ ] **Cron Job Verification:**
  ```bash
  # Check validation logs
  tail -f /var/log/mcp-server/spot-check-validation.log
  ```
  - Verify monthly spot check validation ran (1st of month)
  - No revert events (unless justified)

**Referenz:** Siehe `../guides/staged-dual-judge.md` für detailed guide

### 4.5 7-Day Stability Testing (Story 3.11)

- [ ] **Stability Test:** 7-day production run without crashes
- [ ] **Performance Baseline:** Established for query latency, API costs
- [ ] **Production Handoff:** Documentation complete (Story 3.12)

---

## 5. Troubleshooting

### 5.1 Common Environment Issues

#### Problem: "Missing required environment variables"

**Symptom:**
```
FATAL: Configuration error: Missing required environment variables in .env.production:
  - OPENAI_API_KEY
  - ANTHROPIC_API_KEY
```

**Solution:**
1. Edit `config/.env.production`
2. Replace placeholder values with real API keys
3. Ensure no "your-" prefixes or "-here" suffixes
4. Restart MCP Server

#### Problem: "Environment file not found"

**Symptom:**
```
FileNotFoundError: Environment file not found: /home/user/i-o/config/.env.production
```

**Solution:**
1. Create file from template:
   ```bash
   cp config/.env.template config/.env.production
   ```
2. Edit with real values
3. Set permissions: `chmod 600 config/.env.production`

#### Problem: "Invalid ENVIRONMENT value"

**Symptom:**
```
ConfigurationError: Invalid ENVIRONMENT value: 'prod'. Must be one of: development, production
```

**Solution:**
1. Use exact values: `development` or `production` (not "prod", "dev", etc.)
2. Set correctly:
   ```bash
   export ENVIRONMENT=production  # Correct
   export ENVIRONMENT=prod        # Incorrect
   ```

### 5.2 Database Connection Issues

#### Problem: Database connection refused

**Symptom:**
```
psycopg2.OperationalError: could not connect to server: Connection refused
```

**Solution:**
1. Verify PostgreSQL running:
   ```bash
   sudo systemctl status postgresql
   ```
2. Check DATABASE_URL in `.env.production`
3. Verify `mcp_user` has permissions:
   ```bash
   psql -U postgres -c "SELECT * FROM pg_user WHERE usename='mcp_user';"
   ```

#### Problem: Wrong database connected

**Symptom:** MCP Server connects to wrong database (dev instead of prod)

**Solution:**
1. Check ENVIRONMENT variable:
   ```bash
   echo $ENVIRONMENT
   ```
2. Verify config.yaml database name:
   ```bash
   grep -A 5 "^production:" config/config.yaml
   ```
3. Check .env.production DATABASE_URL

### 5.3 API Key Issues

#### Problem: OpenAI API rate limit exceeded

**Symptom:**
```
openai.error.RateLimitError: You exceeded your current quota
```

**Solution:**
1. Check API usage: https://platform.openai.com/usage
2. Verify billing: https://platform.openai.com/account/billing
3. Consider rate limiting in application
4. Use budget monitoring (Story 3.10)

---

## 6. Recovery & Disaster Management

### 6.1 RTO/RPO Specifications (Story 3.6)

**Recovery Time Objective (RTO):**
- **Target:** < 1 hour
- **Process:** Restore from latest PostgreSQL backup + replay L2 insights Git export

**Recovery Point Objective (RPO):**
- **Target:** < 24 hours
- **Rationale:** Daily backups at 2 AM → max data loss = 1 day
- **Acceptable for Personal Use:** Yes (Requirement: R2.5 RPO Target < 1 Week)

### 6.2 Backup Restore Procedure

Siehe `backup-recovery.md` (Story 3.6) für vollständige Restore-Anleitung.

**Quick Restore:**
```bash
# 1. Stop MCP Server
sudo systemctl stop cognitive-memory-mcp

# 2. Restore PostgreSQL Database
./scripts/restore_postgres.sh /home/user/backups/postgresql/cognitive_memory_YYYYMMDD_HHMMSS.sql

# 3. Verify Restore
psql -U mcp_user -d cognitive_memory -c "SELECT COUNT(*) FROM l0_raw;"

# 4. Start MCP Server
sudo systemctl start cognitive-memory-mcp
```

---

## 7. References

- **Story 3.7:** Production Configuration & Environment Setup (this story)
- **Story 3.6:** PostgreSQL Backup Strategy Implementation
- **Story 3.2:** Model Drift Detection mit Daily Golden Test
- **Story 3.8:** MCP Server Daemonization & Auto-Start (systemd service)
- **Story 3.10:** Budget Monitoring & Cost Optimization Dashboard
- **Story 3.11:** 7-Day Stability Testing & Validation
- **Story 3.12:** Production Handoff Documentation

**Architecture Documents:**
- `bmad-docs/architecture.md` - Section: Environment Management, Secrets Management
- `bmad-docs/specs/tech-spec-epic-3.md` - Environment Manager Component
- `bmad-docs/PRD.md` - NFR006: Local Control & Privacy

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-18 | Initial production checklist created | Story 3.7 Implementation |
