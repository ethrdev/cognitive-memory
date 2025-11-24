#!/usr/bin/env python3
"""
7-Day Stability Test - Automated Report Generator
Cognitive Memory v1.0.0

Generates comprehensive Markdown stability report from metrics JSON.
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def load_metrics(metrics_file: str = "/tmp/stability-test-metrics.json") -> dict:
    """Load metrics from JSON file."""
    try:
        with open(metrics_file) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Metrics file not found: {metrics_file}")
        print("Have you run ./scripts/end_stability_test.sh yet?")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in metrics file: {e}")
        sys.exit(1)


def format_status_badge(status: str) -> str:
    """Format status as colored badge."""
    badges = {
        "PASS": "✅ PASS",
        "FAIL": "❌ FAIL",
        "WARNING": "⚠️ WARNING",
        "PARTIAL": "⚠️ PARTIAL",
    }
    return badges.get(status, status)


def generate_report(metrics: dict) -> str:
    """Generate comprehensive stability report in Markdown format."""

    # Extract metrics
    start_time = metrics["start_time"]
    end_time = metrics["end_time"]
    elapsed_hours = metrics["elapsed_hours"]

    uptime = metrics["metrics"]["uptime"]
    success_rate = metrics["metrics"]["success_rate"]
    latency = metrics["metrics"]["latency"]
    api_reliability = metrics["metrics"]["api_reliability"]
    budget = metrics["metrics"]["budget"]

    # Determine overall status
    if (
        uptime["status"] == "PASS"
        and success_rate["status"] == "PASS"
        and latency["status"] == "PASS"
    ):
        if budget["status"] in ["PASS", "WARNING"]:
            overall_status = "PASS"
        else:
            overall_status = "PARTIAL"
    else:
        overall_status = "FAIL"

    # Generate report
    report = f"""# 7-Day Stability Test Report

**Test:** 7-Day Stability Validation
**Status:** {format_status_badge(overall_status)}
**Test Period:** {start_time} bis {end_time}
**Total Duration:** {elapsed_hours} Stunden (Target: 168 Stunden)
**Generiert am:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. Executive Summary

Dieser Report dokumentiert die Ergebnisse des 7-tägigen Stability Tests für das Cognitive Memory System v1.0.0. Der Test validiert die Production-Readiness gemäß NFR004 (System Reliability >99% Uptime).

**Test Status:** {format_status_badge(overall_status)}

**Key Metrics:**
- **Uptime:** {uptime['percentage']}% ({format_status_badge(uptime['status'])})
- **Success Rate:** {success_rate['percentage']}% ({format_status_badge(success_rate['status'])})
- **Latency p95:** {latency['p95']}s ({format_status_badge(latency['status'])})
- **API Reliability:** {api_reliability['retry_rate']}% retry rate ({format_status_badge(api_reliability['status'])})
- **Total Cost:** €{budget['total_cost']} ({format_status_badge(budget['status'])})

"""

    # Section 2: Detailed Metrics
    report += """---

## 2. Detailed Metrics

### 2.1 System Uptime (AC-3.11.2 Metric 1)

**Target:** 100% Uptime (>99% acceptable mit Auto-Recovery)

"""
    report += f"""**Ergebnis:** {format_status_badge(uptime['status'])}

- **Total Uptime:** {uptime['hours']} Stunden / 168 Stunden
- **Uptime Percentage:** {uptime['percentage']}%
- **Service Restarts:** {uptime['restart_count']}
"""

    if uptime["restart_count"] == 0:
        report += "- **Stabilität:** ✅ Perfekt - Keine Service-Restarts\n"
    elif uptime["restart_count"] <= 2:
        report += f"- **Stabilität:** ⚠️ Akzeptabel - {uptime['restart_count']} Restart(s) mit Auto-Recovery\n"
    else:
        report += f"- **Stabilität:** ❌ Problematisch - {uptime['restart_count']} Restarts (Root Cause Analysis erforderlich)\n"

    report += "\n"

    # Success Rate
    report += """### 2.2 Query Success Rate (AC-3.11.2 Metric 2)

**Target:** >99% Success Rate (maximal 1 Failed Query von 70 erlaubt)

"""
    report += f"""**Ergebnis:** {format_status_badge(success_rate['status'])}

- **Total Queries:** {success_rate['total_queries']}
- **Successful Queries:** {success_rate['successful_queries']}
- **Failed Queries:** {success_rate['failed_queries']}
- **Success Rate:** {success_rate['percentage']}%

"""

    # Latency
    report += """### 2.3 Latency Percentiles (AC-3.11.2 Metric 3)

**Target:** p95 <5s (NFR001 Performance Compliance)

"""
    report += f"""**Ergebnis:** {format_status_badge(latency['status'])}

- **p50 Latency:** {latency['p50']}s
- **p95 Latency:** {latency['p95']}s (Target: <5s)
- **p99 Latency:** {latency['p99']}s

"""

    # Budget
    report += """### 2.4 Budget Compliance (AC-3.11.2 Metric 5)

**Target:** Total Cost <€2.00 für 7 Tage (€8/mo projected)

"""
    report += f"""**Ergebnis:** {format_status_badge(budget['status'])}

- **Total Cost (7 Tage):** €{budget['total_cost']}
- **Projected Monthly Cost:** €{budget['monthly_projection']}
- **NFR003 Target:** €5-10/mo
- **Compliance:** {'✅ Innerhalb Budget' if float(budget['monthly_projection']) <= 10 else '❌ Über Budget'}

"""

    # Section 3: API Reliability
    report += """---

## 3. API Reliability Analysis (AC-3.11.2 Metric 4)

**Target:** Retry-Logic erfolgreich bei transient Failures (<10% retry rate)

"""
    report += f"""**Ergebnis:** {format_status_badge(api_reliability['status'])}

- **Total API Calls:** {api_reliability['total_calls']}
- **Retry Count:** {api_reliability['retry_count']}
- **Retry Rate:** {api_reliability['retry_rate']}%
- **First-Attempt Success Rate:** {100 - float(api_reliability['retry_rate']):.2f}%

**Analysis:**
"""

    retry_rate_float = float(api_reliability["retry_rate"])
    if retry_rate_float < 10:
        report += "✅ Retry-Logic funktioniert einwandfrei. API Reliability ist ausgezeichnet.\n"
    elif retry_rate_float < 20:
        report += "⚠️ Retry-Logic funktioniert, aber höhere Rate als erwartet. Monitoring empfohlen.\n"
    else:
        report += "❌ Hohe Retry-Rate deutet auf API Reliability Issues. Root Cause Analysis erforderlich.\n"

    report += "\n"

    # Section 4: Daily Operations
    report += """---

## 4. Daily Operations Validation (AC-3.11.4)

### 4.1 Automated Cron Jobs

**Daily Cron Jobs (must execute without errors):**

1. **Model Drift Detection** (2 AM)
   - Target: 7 successful runs
   - Status: (Manual verification erforderlich - Check: `journalctl -u cron | grep drift`)

2. **PostgreSQL Backup** (3 AM)
   - Target: 7 backups created
   - Status: (Manual verification erforderlich - Check: `ls -lh /backups/postgres/`)

3. **Budget Alert Check** (4 AM)
   - Target: 7 checks executed
   - Status: (Manual verification erforderlich - Check: `journalctl -u cron | grep budget`)

### 4.2 Continuous Background Tasks

1. **Health Check** (every 15 minutes)
   - Target: >95% success rate
   - Status: (Integrated in API Reliability metrics above)

2. **systemd Auto-Restart**
   - Target: Functional if crash occurs
   - Restart Count: {uptime['restart_count']}
   - Status: {'✅ Functional (Auto-Recovery verified)' if uptime['restart_count'] > 0 else '✅ Not needed (No crashes)'}

"""

    # Section 5: Issues Encountered
    report += """---

## 5. Issues Encountered

"""

    if overall_status == "PASS" and uptime["restart_count"] == 0:
        report += "**Keine kritischen Issues während des Tests.**\n\n"
        report += "Das System lief 7 Tage kontinuierlich ohne Crashes, Timeouts oder Budget Overage.\n"
    else:
        report += "**Folgende Issues wurden während des Tests identifiziert:**\n\n"

        if uptime["status"] != "PASS":
            report += f"1. **Uptime Issue:** System erreichte nur {uptime['percentage']}% Uptime (Target: >99%)\n"
            report += f"   - Service Restarts: {uptime['restart_count']}\n"
            report += "   - Action: Root Cause Analysis erforderlich\n\n"

        if success_rate["status"] != "PASS":
            report += f"2. **Query Failures:** {success_rate['failed_queries']} Failed Queries\n"
            report += "   - Action: Analyze api_retry_log for exhausted retries\n\n"

        if latency["status"] != "PASS":
            report += (
                f"3. **Latency Issue:** p95 Latency {latency['p95']}s (Target: <5s)\n"
            )
            report += "   - Action: Profile code, optimize critical path\n\n"

        if budget["status"] == "FAIL":
            report += f"4. **Budget Overage:** Total Cost €{budget['total_cost']} (Target: <€2.00)\n"
            report += "   - Action: Cost breakdown analysis, optimize API usage\n\n"

    # Section 6: Recommendations
    report += """---

## 6. Recommendations

"""

    recommendations = []

    # Performance recommendations
    if latency["status"] != "PASS":
        recommendations.append(
            "**Performance:** Profile und optimize RAG Pipeline - p95 Latency >5s (NFR001 Violation)"
        )
    elif float(latency["p95"]) > 3.0:
        recommendations.append(
            f"**Performance:** p95 Latency {latency['p95']}s ist okay (<5s), aber Optimization möglich für bessere UX"
        )

    # Cost recommendations
    if budget["status"] == "FAIL":
        recommendations.append(
            f"**Cost:** Budget Overage €{budget['total_cost']} - Identify cost driver via Budget Dashboard"
        )
    elif float(budget["monthly_projection"]) > 7.0:
        recommendations.append(
            f"**Cost:** Projected Monthly Cost €{budget['monthly_projection']} - Consider activating Staged Dual Judge für -40% Cost Reduction"
        )
    else:
        recommendations.append(
            "**Cost:** Budget ist optimal - Staged Dual Judge kann langfristig weitere Einsparungen bringen"
        )

    # Reliability recommendations
    if uptime["restart_count"] > 0:
        recommendations.append(
            f"**Reliability:** {uptime['restart_count']} Service Restart(s) - Analyze journalctl logs für Root Cause"
        )

    if retry_rate_float > 10:
        recommendations.append(
            f"**Reliability:** Retry Rate {api_reliability['retry_rate']}% - Monitor API Health Check logs für transient failures"
        )

    # Success recommendations
    if overall_status == "PASS":
        recommendations.append(
            "**Production Deployment:** System ist production-ready - Proceed to next phase (Production Handoff Documentation)"
        )

    if not recommendations:
        recommendations.append(
            "**System Performance:** Ausgezeichnet - Keine Optimierungen erforderlich"
        )

    for i, rec in enumerate(recommendations, 1):
        report += f"{i}. {rec}\n"

    report += "\n"

    # Footer
    report += """---

## Fazit

"""

    if overall_status == "PASS":
        report += f"""**7-Day Stability Test: ERFOLGREICH BESTANDEN ✅**

Das Cognitive Memory System v1.0.0 hat den 7-tägigen Stability Test erfolgreich bestanden:
- ✅ Uptime: {uptime['percentage']}% (Target: >99%)
- ✅ Success Rate: {success_rate['percentage']}% (Target: >99%)
- ✅ Latency p95: {latency['p95']}s (Target: <5s)
- ✅ Budget: €{budget['total_cost']} (Target: <€2.00)

**NFR004 (System Reliability) validiert:** Production-Readiness bestätigt.

**Next Steps:**
1. Proceed to next phase (Production Handoff & Documentation)
2. Deploy System in Production Environment
3. Continue daily monitoring (Health Checks, Budget Alerts, Drift Detection)
"""
    elif overall_status == "PARTIAL":
        report += f"""**7-Day Stability Test: TEILWEISE BESTANDEN ⚠️**

Core Metrics sind erfüllt, aber minor Issues wurden identifiziert:
- Uptime: {uptime['percentage']}% ({uptime['status']})
- Success Rate: {success_rate['percentage']}% ({success_rate['status']})
- Latency p95: {latency['p95']}s ({latency['status']})
- Budget: €{budget['total_cost']} ({budget['status']})

**NFR004 (System Reliability) teilweise validiert:** Production Deployment mit Monitoring empfohlen.

**Next Steps:**
1. Address identified issues (siehe Section 5)
2. Re-calibrate in 2 weeks mit extended dataset
3. Continue to next phase mit monitoring plan
"""
    else:
        report += f"""**7-Day Stability Test: NICHT BESTANDEN ❌**

Kritische Acceptance Criteria nicht erfüllt:
- Uptime: {uptime['percentage']}% ({uptime['status']})
- Success Rate: {success_rate['percentage']}% ({success_rate['status']})
- Latency p95: {latency['p95']}s ({latency['status']})
- Budget: €{budget['total_cost']} ({budget['status']})

**NFR004 (System Reliability) NICHT validiert:** System ist NICHT production-ready.

**Next Steps:**
1. Root Cause Analysis für alle Failed Metrics
2. Fix identified bugs/issues
3. Re-run 7-Day Stability Test (max. 3 Iterationen erlaubt)
"""

    report += "\n---\n\n"
    report += (
        f"**Report Generiert:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
    )
    report += (
        "**Automatisch generiert durch:** `scripts/generate_stability_report.py`  \n"
    )
    report += "**Source Metrics:** `/tmp/stability-test-metrics.json`\n"

    return report


def main():
    """Main entry point."""
    print("═══════════════════════════════════════════════════════════════")
    print("  7-Day Stability Test - Report Generator")
    print("═══════════════════════════════════════════════════════════════")
    print()

    # Load metrics
    print("Loading metrics from /tmp/stability-test-metrics.json...")
    metrics = load_metrics()
    print("✓ Metrics loaded successfully")
    print()

    # Generate report
    print("Generating stability report...")
    report = generate_report(metrics)
    print("✓ Report generated")
    print()

    # Save report
    output_file = Path(
        "/home/ethr/01-projects/ai-experiments/i-o/docs/testing/7-day-stability-report.md"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        f.write(report)

    print(f"✓ Report saved to: {output_file}")
    print()
    print("═══════════════════════════════════════════════════════════════")
    print()
    print("Next Steps:")
    print(f"  1. Review report: {output_file}")
    print("  2. Add report to Git: git add docs/testing/7-day-stability-report.md")
    print("  3. Update 3.11 status based on results")
    print("  4. Proceed to next phase (Production Handoff) if test passed")
    print()


if __name__ == "__main__":
    main()
