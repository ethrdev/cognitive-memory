# 7-Day Stability Test - Execution Guide

**Story:** 3.11 - 7-Day Stability Testing & Validation
**Epic:** 3 - Production Readiness & Budget Optimization
**Version:** 1.0
**Erstellt:** 2025-11-20
**Autor:** BMad Dev-Story Workflow

---

## Table of Contents

1. [Übersicht](#1-übersicht)
2. [Prerequisites](#2-prerequisites)
3. [Phase 1: Pre-Test Validation](#3-phase-1-pre-test-validation)
4. [Phase 2: Test Execution (7 Tage)](#4-phase-2-test-execution-7-tage)
5. [Phase 3: End-of-Test Analysis](#5-phase-3-end-of-test-analysis)
6. [Phase 4: Report Generation](#6-phase-4-report-generation)
7. [Failure Scenarios & Recovery](#7-failure-scenarios--recovery)
8. [FAQ](#8-faq)

---

## 1. Übersicht

### 1.1 Was ist der 7-Day Stability Test?

Der 7-Day Stability Test ist ein **Integration Test** für das Cognitive Memory System v3.1.0-Hybrid. Er validiert, dass alle Epic 3 Features (Stories 3.1-3.10) korrekt zusammenarbeiten und das System production-ready ist.

**Ziel:** NFR004 (System Reliability >99% Uptime) validieren

### 1.2 Test Success Criteria (AC-3.11.2)

Der Test gilt als **PASS**, wenn ALLE folgenden Metriken erfüllt sind:

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Uptime** | ≥99% (168h) | systemctl show mcp-server |
| **Success Rate** | >99% | (successful_queries / total_queries) × 100 |
| **Latency p95** | <5s | PostgreSQL percentile calculation |
| **API Reliability** | <10% retry rate | api_retry_log analysis |
| **Budget** | <€2.00 for 7 days | SUM(estimated_cost) from api_cost_log |

### 1.3 Test Timeline

```
Day 0: Pre-Test Validation (30 min)
  ↓
Day 1-7: Daily Monitoring (10 min/day)
  ↓
Day 7: End-of-Test Metrics Collection (60 min)
  ↓
Day 7: Report Generation (60 min)
```

**Total Active Time:** ~4-5 hours over 7 days
**Total Elapsed Time:** 168 hours (7 days)

---

## 2. Prerequisites

### 2.1 System Requirements

Bevor du den Test startest, stelle sicher, dass:

- [ ] **Alle Epic 3 Stories (3.1-3.10) sind "done"** (Check: `bmad-docs/sprint-status.yaml`)
- [ ] **systemd Service läuft** (`systemctl status mcp-server`)
- [ ] **PostgreSQL ist accessible** (`psql -U mcp_user -d cognitive_memory -c "SELECT 1"`)
- [ ] **Cron Jobs sind konfiguriert** (Drift Detection, Backup, Budget Alert)
- [ ] **API Keys sind present** (`.env.production` contains OPENAI_API_KEY, ANTHROPIC_API_KEY)
- [ ] **Production Environment ist configured** (Story 3.7)
- [ ] **Backups sind operational** (Story 3.6 - Check `/backups/postgres/`)

### 2.2 Available Scripts

Der Dev-Agent hat folgende Helper-Scripts erstellt:

| Script | Purpose | Location |
|--------|---------|----------|
| **start_stability_test.sh** | Pre-Test Validation & Initialization | `scripts/start_stability_test.sh` |
| **daily_stability_check.sh** | Daily Monitoring Automation | `scripts/daily_stability_check.sh` |
| **end_stability_test.sh** | End-of-Test Metrics Collection | `scripts/end_stability_test.sh` |
| **generate_stability_report.py** | Automated Report Generation | `scripts/generate_stability_report.py` |

Alle Scripts sind executable (`chmod +x`) und ready to use.

### 2.3 Expected Query Load

Der Test erfordert **mindestens 10 Queries pro Tag (70 total)**:

**Option A: Organic Queries** (Preferred)
- Use the system naturally during your daily work
- Queries count automatically via api_cost_log

**Option B: Synthetic Queries**
- Falls nicht genug organische Queries
- Sample from `golden_test_set` table
- Run test queries via MCP Server

---

## 3. Phase 1: Pre-Test Validation

### 3.1 Run Pre-Test Validation Script

```bash
cd /home/ethr/01-projects/ai-experiments/i-o
./scripts/start_stability_test.sh
```

**Was macht das Script?**

1. **Check 1:** Verify all Epic 3 Stories (3.1-3.10) marked as "done"
2. **Check 2:** Verify systemd service running
3. **Check 3:** Verify PostgreSQL database accessible
4. **Check 4:** Verify all cron jobs configured
5. **Check 5:** Verify API keys configured
6. **Initialize:** Create tracking file `/tmp/stability-test-tracking.json`
7. **Capture:** Baseline metrics (start time, uptime, query count)

### 3.2 Expected Output

**Success:**
```
✓ ALL CHECKS PASSED - System is ready for 7-Day Stability Test

Next Steps:
  1. Review this validation report
  2. Ensure you can commit to 7 days of monitoring
  3. Run daily: ./scripts/daily_stability_check.sh
  4. After 7 days: ./scripts/end_stability_test.sh

Test officially starts: 2025-11-20T10:00:00Z
```

**Failure:**
```
✗ VALIDATION FAILED - System is NOT ready for testing

Required Actions:
  1. Fix all failed checks above
  2. Re-run this script to validate fixes
  3. Only start test when ALL checks pass
```

### 3.3 Was tun bei Failures?

| Failed Check | Action |
|--------------|--------|
| **Stories not done** | Complete missing Epic 3 Stories (run dev-story workflow) |
| **Service not running** | `sudo systemctl start mcp-server` |
| **PostgreSQL not accessible** | Check PostgreSQL service: `sudo systemctl status postgresql` |
| **Cron jobs missing** | Configure cron jobs per Stories 3.2, 3.6, 3.10 |
| **API keys missing** | Add keys to `.env.production` |

**WICHTIG:** Starte den Test NUR, wenn alle Checks PASS sind!

---

## 4. Phase 2: Test Execution (7 Tage)

### 4.1 Day 0: Test Start

Nach erfolgreicher Pre-Test Validation beginnt der Test **automatisch**. Du musst nichts weiteres tun außer:

1. **System laufen lassen** (nicht manuell restarten)
2. **Daily Monitoring** durchführen (siehe 4.2)
3. **Queries generieren** (organic oder synthetic, min. 10/Tag)

### 4.2 Daily Monitoring (Tag 1-7)

**Jeden Tag (oder alle 2 Tage):**

```bash
cd /home/ethr/01-projects/ai-experiments/i-o
./scripts/daily_stability_check.sh
```

**Was macht das Script?**

- ✅ Zeigt Elapsed Time und Remaining Time
- ✅ Checkt systemd Service Status (active/crashed)
- ✅ Checkt Cron Jobs Execution (last 24h)
- ✅ Analyzed API Retry Log (reliability)
- ✅ Checkt Daily Budget (expected €0.20-0.30/Tag)
- ✅ Checkt Query Count (min. 10/Tag)
- ✅ Zeigt Daily Status: OK / WARNING / CRITICAL

### 4.3 Daily Monitoring - Expected Output

```
═══════════════════════════════════════════════════════════════
  7-Day Stability Test - Daily Monitoring Check
  Date: 2025-11-23 10:00:00
═══════════════════════════════════════════════════════════════

Test Start Time: 2025-11-20T10:00:00Z
Elapsed Time: 3d 72h / 168h (Target: 7 days)
Remaining: 96h

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHECK 1: systemd Service Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ PASS: mcp-server service is active (running)
  Restart Count: 0

[... weitere Checks ...]

═══════════════════════════════════════════════════════════════
  Daily Check Summary
═══════════════════════════════════════════════════════════════
✓ Daily Status: OK - All systems operational

Progress: Day 3 of 7 (72h / 168h)

Remaining Time: 96 hours
Next Check: Run this script again tomorrow
═══════════════════════════════════════════════════════════════
```

### 4.4 Was tun bei Daily Warnings?

| Warning | Action |
|---------|--------|
| **Service NOT running** | CRITICAL - Check logs: `journalctl -u mcp-server -n 100` |
| **Cron Jobs not executed** | Check cron logs: `journalctl -u cron --since "24 hours ago"` |
| **High Retry Rate (>10%)** | Monitor API Health - Check api_retry_log for patterns |
| **Budget Spike (>€0.50/day)** | Investigate: `python -m mcp_server.budget.cli breakdown --days 1` |
| **Low Query Count (<10)** | Run test queries or use system more actively |

### 4.5 Query Load Generation

**Option A: Organic (Preferred)**
- Use MCP Server naturally during your work
- Queries are automatically tracked in api_cost_log

**Option B: Synthetic (Falls nötig)**
```bash
# Sample queries from golden_test_set
psql -U mcp_user -d cognitive_memory -c "SELECT query FROM golden_test_set LIMIT 10"

# Run queries via MCP Server
# (Execute queries through your Claude Code or other MCP client)
```

**Target:** 10-15 Queries/Tag = 70-100 Queries über 7 Tage

---

## 5. Phase 3: End-of-Test Analysis

### 5.1 Day 7: End-of-Test Metrics Collection

Nach 7 Tagen (168 hours):

```bash
cd /home/ethr/01-projects/ai-experiments/i-o
./scripts/end_stability_test.sh
```

**Was macht das Script?**

1. **Metric 1:** Calculate Total Uptime (systemctl show mcp-server)
2. **Metric 2:** Calculate Query Success Rate (api_cost_log + api_retry_log)
3. **Metric 3:** Calculate Latency Percentiles (p50, p95, p99 from model_drift_log)
4. **Metric 4:** Calculate API Reliability (retry rate analysis)
5. **Metric 5:** Calculate Total Cost (SUM(estimated_cost) from api_cost_log)
6. **Save:** Metrics to `/tmp/stability-test-metrics.json`

### 5.2 Expected Output

```
═══════════════════════════════════════════════════════════════
  7-Day Stability Test - Final Metrics Collection
  Completion Date: 2025-11-27 10:00:00
═══════════════════════════════════════════════════════════════

Test Start: 2025-11-20T10:00:00Z
Test End: 2025-11-27T10:00:00Z
Total Duration: 168h (Target: 168h)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
METRIC 1: Total Uptime Calculation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Service Start: Wed 2025-11-20 10:00:00 UTC
Uptime: 168h / 168h (100.00%)
✓ PASS: Uptime ≥99% (Target: >99%)
✓ Perfect: No service restarts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
METRIC 2: Query Success Rate
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Queries Processed: 72
Successful Queries: 72
Failed Queries: 0
Success Rate: 100.00%
✓ PASS: Success Rate ≥99% (Target: >99%)
✓ Query Load: 72 queries ≥70 (Target: 70+)

[... weitere Metriken ...]

═══════════════════════════════════════════════════════════════
  7-Day Stability Test - Final Summary
═══════════════════════════════════════════════════════════════
Metric 1 - Uptime: PASS (100.00%)
Metric 2 - Success Rate: PASS (100.00%)
Metric 3 - Latency p95: PASS (2.30s)
Metric 4 - API Reliability: PASS (3.50% retry rate)
Metric 5 - Budget: PASS (€1.85)

✓ OVERALL: PASS - All acceptance criteria met!

Production-Readiness validated successfully (NFR004).

Next Steps:
  1. Review metrics JSON: /tmp/stability-test-metrics.json
  2. Generate stability report: python3 scripts/generate_stability_report.py
  3. Document results in: 7-day-stability-report.md
═══════════════════════════════════════════════════════════════
```

---

## 6. Phase 4: Report Generation

### 6.1 Automated Report Generation (Empfohlen)

```bash
cd /home/ethr/01-projects/ai-experiments/i-o
python3 scripts/generate_stability_report.py
```

**Output:**
- Report saved to: `7-day-stability-report.md`
- Comprehensive Markdown report mit allen 6 Sections
- Basierend auf `/tmp/stability-test-metrics.json`

### 6.2 Manual Report Generation (Alternative)

Falls du das Python-Script nicht verwenden möchtest:

1. Copy Template: `cp 7-day-stability-report-template.md 7-day-stability-report.md`
2. Open: `7-day-stability-report.md`
3. Fill in: Alle Platzhalter `[X]` mit Metrics aus `/tmp/stability-test-metrics.json`
4. Review: Vollständigkeit prüfen

### 6.3 Report Structure

Der Report hat 6 required Sections:

1. **Executive Summary:** Overall Status, Key Metrics
2. **Detailed Metrics:** Alle 5 AC-3.11.2 Metriken detailliert
3. **API Reliability Analysis:** Retry Rate, Fallback Activation
4. **Daily Operations Validation:** Cron Jobs, Health Checks
5. **Issues Encountered:** Alle Probleme während Test
6. **Recommendations:** Performance, Cost, Reliability Optimizations

### 6.4 Add Report to Git

```bash
cd /home/ethr/01-projects/ai-experiments/i-o
git add 7-day-stability-report.md
git commit -m "Story 3.11: 7-Day Stability Report - [PASS/PARTIAL/FAIL]"
git push
```

---

## 7. Failure Scenarios & Recovery

### 7.1 System Crashes (AC-3.11.3)

**Detection:**
- Daily Check Script zeigt: `✗ FAIL: mcp-server service is NOT running`
- OR: systemd auto-restart triggered (Restart Count >0)

**Root Cause Analysis:**
```bash
# Check systemd logs
journalctl -u mcp-server -n 200 --no-pager

# Identify crash reason
# - Exception Stack Trace
# - OOM (Out of Memory)
# - API Timeout
# - DB Connection Loss
```

**Action:**
1. Fix bug in codebase
2. Restart 7-Day Test (max. 3 Iterationen erlaubt)
3. Document crash in final report Section 5 (Issues Encountered)

**Acceptable:**
- 1-2 Restarts mit Auto-Recovery = PASS (Uptime >99%)
- 3+ Restarts = FAIL (Root Cause Analysis erforderlich)

### 7.2 Latency >5s (p95)

**Detection:**
- End-of-Test Script zeigt: `✗ FAIL: p95 Latency ≥5s (NFR001 Violation)`

**Root Cause Analysis:**
```bash
# Profile code - identify bottleneck
# Possible bottlenecks:
# - OpenAI Embeddings (slow API response)
# - PostgreSQL Retrieval (missing index)
# - Anthropic Generation (large context)
# - Evaluation (complex judge prompts)
```

**Action:**
1. Profile code (Python cProfile or log-based analysis)
2. Optimize critical path (connection pooling, caching, batch processing)
3. Re-run latency benchmark (Story 3.5 scripts)
4. Restart 7-Day Test if fix applied

### 7.3 Budget Overage (>€2)

**Detection:**
- Daily Check Script zeigt: `✗ ALERT: Daily cost >€0.50 (investigate cost spike)`
- OR: End-of-Test Script zeigt: `✗ FAIL: Total Cost ≥€3.00`

**Root Cause Analysis:**
```bash
# Run budget dashboard
python -m mcp_server.budget.cli breakdown --days 7

# Identify cost driver
# Possible drivers:
# - High Reflexion Rate (Haiku Eval + Reflexion)
# - Unexpected GPT-4o calls (Dual Judge still active)
# - Large Query Volume (>100 queries)
```

**Action:**
1. Identify cost driver (GPT-4o Judge, Haiku Eval, OpenAI Embeddings)
2. Check Reflexion Rate (high rate = high Haiku costs)
3. Check Dual Judge status (if Kappa >0.85, activate Staged Dual Judge)
4. Continue test with monitoring (budget overage nicht zwingend Failure)

**Note:** Budget >€2 but <€3 = PARTIAL (acceptable with monitoring)

### 7.4 Query Success Rate <99%

**Detection:**
- End-of-Test Script zeigt: `✗ FAIL: Success Rate <99% (Target: >99%)`

**Root Cause Analysis:**
```bash
# Query failed queries
psql -U mcp_user -d cognitive_memory -c "
SELECT * FROM api_retry_log
WHERE retry_count >= 4
AND created_at >= '[test_start]'
"

# Determine failure type
# - API Timeout (OpenAI/Anthropic)
# - DB Error (PostgreSQL connection loss)
# - Evaluation Failure (judge API error)
```

**Action:**
1. Fix error handling (increase retry limit, improve connection pooling)
2. Restart 7-Day Test if critical fix applied
3. Document failures in report Section 5

### 7.5 Cron Job Failures

**Detection:**
- Daily Check Script zeigt: `⚠ WARNING: Some cron jobs may be missing`

**Root Cause Analysis:**
```bash
# Check cron logs
journalctl -u cron --since [test_start] | grep ERROR

# Identify which job failed
# - Drift Detection (2 AM)
# - Backup (3 AM)
# - Budget Alert (4 AM)
```

**Action:**
1. Analyze failure reason (script error, DB connection, API timeout)
2. Fix script error, improve error handling
3. Restart 7-Day Test if critical fix applied

---

## 8. FAQ

### Q1: Was passiert, wenn mein Computer neu startet während des Tests?

**A:** Falls systemd auto-start korrekt konfiguriert ist (Story 3.8), startet der MCP Server automatisch nach Reboot. Der Test wird **fortgesetzt**, aber:
- Restart Count erhöht sich
- Uptime Metric kann <100% sein (aber >99% ist acceptable)
- systemd tracked service uptime weiterhin korrekt

**Action:** Nach Reboot daily check laufen lassen, um Status zu verifizieren.

### Q2: Kann ich den Test pausieren und später fortsetzen?

**A:** **Nein.** Der 7-Day Test erfordert **kontinuierliche 168 Stunden**. Falls du den Test unterbrechen musst:
- Option A: Restart Test von vorne (wenn <3 Tage gelaufen)
- Option B: Continue und documentiere Downtime im Report (kann zu FAIL führen)

### Q3: Was zählt als "Query" für Query Load Metric?

**A:** Jeder MCP Tool Call, der api_cost_log Entry erstellt = 1 Query. Das umfasst:
- Semantic Search Queries
- Memory Insertion Operations
- Working Memory Operations
- Hybrid Search mit Evaluation

### Q4: Muss ich wirklich 10 Queries pro Tag generieren?

**A:** **Ja.** Target ist 10-15 Queries/Tag (70-100 total). Falls organische Queries nicht ausreichen:
- Run synthetic test queries aus golden_test_set
- Use system mehr aktiv während deiner Arbeit
- **Low query load (<70 total) = Test nicht vollständig validiert**

### Q5: Was ist der Unterschied zwischen PASS, PARTIAL und FAIL?

**A:**
- **PASS:** Alle 5 Metriken erfüllt, keine kritischen Issues → Production-Ready ✅
- **PARTIAL:** Core Metriken (Uptime, Success Rate, Latency) erfüllt, aber minor Issues (Budget, API Reliability) → Production mit Monitoring ⚠️
- **FAIL:** Mindestens 1 kritische Metrik nicht erfüllt → NOT Production-Ready, Root Cause Analysis erforderlich ❌

### Q6: Wie viele Test-Iterationen sind erlaubt bei Failures?

**A:** **Maximum 3 Iterationen.** Falls Test 3x FAIL:
- System ist **definitiv NICHT production-ready**
- Umfassende Root Cause Analysis erforderlich
- Epic 3 Stories müssen ggf. re-implementiert werden

### Q7: Muss ich das Python Script für Report Generation verwenden?

**A:** **Nein.** Du hast 2 Optionen:
- **Option A (Empfohlen):** Automated - `python3 scripts/generate_stability_report.py`
- **Option B:** Manual - Use `7-day-stability-report-template.md` und fill in manually

Beide Optionen sind valid und erfüllen AC-3.11.5.

### Q8: Was passiert nach dem Test?

**A:** Based on Result:

**PASS:**
1. Update Story 3.11 status to "done"
2. Proceed to Story 3.12 (Production Handoff Documentation)
3. Deploy System in Production Environment

**PARTIAL:**
1. Address identified issues (Section 5 in Report)
2. Continue to Story 3.12 mit monitoring plan
3. Re-calibrate in 2 weeks

**FAIL:**
1. Conduct Root Cause Analysis
2. Fix bugs/issues
3. Re-run 7-Day Test (max. 3 iterations)

---

## Appendix: Quick Reference

### Scripts Cheat Sheet

```bash
# Pre-Test Validation
./scripts/start_stability_test.sh

# Daily Monitoring (jeden Tag)
./scripts/daily_stability_check.sh

# End-of-Test Metrics (nach 7 Tagen)
./scripts/end_stability_test.sh

# Report Generation
python3 scripts/generate_stability_report.py
```

### Key Files

| File | Purpose |
|------|---------|
| `/tmp/stability-test-tracking.json` | Test Start Time + Baseline Metrics |
| `/tmp/stability-test-metrics.json` | Final Metrics (after end script) |
| `7-day-stability-report.md` | Final Stability Report |
| `7-day-stability-report-template.md` | Template für manual report |
| `bmad-docs/sprint-status.yaml` | Story status tracking |
| `bmad-docs/stories/3-11-*.md` | Story file mit tasks |

### Success Criteria (Quick Check)

✅ **PASS wenn ALLE:**
- Uptime ≥99% (168h)
- Success Rate >99%
- Latency p95 <5s
- API Reliability <10% retry rate
- Budget <€2.00

---

**Guide Version:** 1.0
**Last Updated:** 2025-11-20
**Created by:** BMad Dev-Story Workflow for Story 3.11
