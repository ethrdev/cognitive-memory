# Budget Monitoring & Cost Optimization

Comprehensive guide for the Budget Monitoring system (Story 3.10), implementing NFR003 budget compliance (€5-10/mo target).

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [CLI Dashboard](#cli-dashboard)
4. [Configuration](#configuration)
5. [Cost Tracking](#cost-tracking)
6. [Budget Alerts](#budget-alerts)
7. [Cost Optimization](#cost-optimization)
8. [Integration Guide](#integration-guide)
9. [Troubleshooting](#troubleshooting)

## Overview

The Budget Monitoring system provides:

- **Automatic Cost Tracking**: All API calls (OpenAI, Anthropic) are logged with actual token counts
- **Monthly Aggregation**: Real-time cost aggregation and monthly projections
- **Budget Alerts**: Email and Slack notifications when budget thresholds are exceeded
- **Cost Optimization**: AI-powered recommendations for reducing costs
- **CLI Dashboard**: Interactive command-line interface for budget monitoring

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     API Clients Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ OpenAI       │  │ GPT-4o       │  │ Haiku        │      │
│  │ Embeddings   │  │ Judge        │  │ Eval/Refl    │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                            ↓                                 │
│              ┌─────────────────────────────┐                │
│              │  Cost Logger (cost_logger.py)│                │
│              │  insert_cost_log()           │                │
│              └─────────────┬───────────────┘                │
└────────────────────────────┼────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                    Database Layer (PostgreSQL)               │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  api_cost_log table                                     │ │
│  │  ┌──────┬──────────┬───────────┬─────────┬──────────┐ │ │
│  │  │ date │ api_name │ num_calls │ tokens  │ cost_eur │ │ │
│  │  ├──────┼──────────┼───────────┼─────────┼──────────┤ │ │
│  │  │ ...  │ ...      │ ...       │ ...     │ ...      │ │ │
│  │  └──────┴──────────┴───────────┴─────────┴──────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                 Budget Monitoring Layer                      │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Budget Monitor   │  │ Cost Optimization│                │
│  │ - Aggregation    │  │ - Insights       │                │
│  │ - Projection     │  │ - Recommendations│                │
│  │ - Thresholds     │  │ - Savings        │                │
│  └────────┬─────────┘  └────────┬─────────┘                │
│           │                      │                          │
│           └──────────┬───────────┘                          │
│                      ↓                                       │
│           ┌──────────────────────┐                          │
│           │  Budget Alerts       │                          │
│           │  - Email             │                          │
│           │  - Slack             │                          │
│           │  - Deduplication     │                          │
│           └──────────┬───────────┘                          │
└──────────────────────┼──────────────────────────────────────┘
                       ↓
           ┌────────────────────────┐
           │   CLI Dashboard        │
           │   python -m mcp_server │
           │   .budget.cli          │
           └────────────────────────┘
```

## Quick Start

### 1. Check Budget Status

```bash
# View budget dashboard
python -m mcp_server.budget dashboard
```

Expected output:
```
================================================================================
  Budget Monitoring Dashboard
================================================================================

Budget Status
-------------
Current Cost (MTD)          €3.45
Projected Monthly Cost      €8.67
Monthly Budget Limit        €10.00
Alert Threshold             €8.00
Budget Utilization          86.7%

⚠️  BUDGET ALERT - Monitor usage closely

Month Progress
--------------
Days Elapsed     12 / 30
Days Remaining   18
Average Daily Cost  €0.2875
```

### 2. View Cost Breakdown

```bash
# Detailed breakdown by API
python -m mcp_server.budget breakdown
```

### 3. Get Optimization Recommendations

```bash
# Cost optimization insights
python -m mcp_server.budget optimize
```

### 4. Check and Send Alerts

```bash
# Check alerts (no send)
python -m mcp_server.budget alerts

# Check and send alerts if threshold exceeded
python -m mcp_server.budget alerts --send
```

## CLI Dashboard

### Commands

#### dashboard
Display budget overview with current cost, projection, and status.

```bash
python -m mcp_server.budget dashboard
```

**Output Sections:**
- Budget Status (current, projected, limit, utilization)
- Month Progress (days elapsed, remaining, average daily cost)
- Cost Breakdown by API
- Quick Insights (most expensive API, transition readiness)

#### breakdown
Detailed cost breakdown by API with percentages and cost-per-call metrics.

```bash
# Current month breakdown
python -m mcp_server.budget breakdown

# Last 7 days daily breakdown
python -m mcp_server.budget breakdown --days 7
```

**Output:**
- Monthly cost by API (total, %, calls, tokens, cost/call)
- Daily costs for specified number of days

#### optimize
Cost optimization recommendations with estimated savings.

```bash
python -m mcp_server.budget optimize
```

**Output:**
- Savings potential summary
- Detailed recommendations (Query Expansion, Dual Judge, Evaluation, etc.)
- Staged Dual Judge transition status
- Trade-off analysis for each recommendation

#### alerts
Check budget alerts and optionally send notifications.

```bash
# Check without sending
python -m mcp_server.budget alerts

# Check and send notifications
python -m mcp_server.budget alerts --send
```

**Output:**
- Alert status (sent/not sent)
- Budget status summary
- Notification methods used

#### daily
Daily cost summary for last N days.

```bash
# Last 30 days (default)
python -m mcp_server.budget daily

# Last 7 days
python -m mcp_server.budget daily --days 7
```

**Output:**
- Daily costs table (date, cost, calls, tokens)
- Summary (total cost, calls, tokens, average daily cost)

## Configuration

Budget configuration in `config/config.yaml`:

```yaml
budget:
  # Monthly budget limit (NFR003: €5-10/mo target)
  monthly_limit_eur: 10.0

  # Alert threshold (80% of monthly limit = €8.00)
  alert_threshold_pct: 80

  # Optional: Email address for budget alerts
  alert_email: ""

  # Optional: Slack webhook URL for budget alerts
  alert_slack_webhook: ""
```

### API Cost Rates

Cost rates are hard-coded in `config.yaml` (Story 3.10 AC-5: Manual updates):

```yaml
api_cost_rates:
  # OpenAI API Pricing
  openai_embeddings: 0.00000002  # €0.02 per 1M tokens
  gpt4o_input: 0.0000025         # €2.50 per 1M input tokens
  gpt4o_output: 0.00001          # €10.00 per 1M output tokens

  # Anthropic API Pricing (USD to EUR conversion: 0.92)
  haiku_input: 0.00000092        # $1.00/1M → €0.92/1M tokens
  haiku_output: 0.0000046        # $5.00/1M → €4.60/1M tokens
```

**Update Procedure:**
1. Check API provider pricing pages
2. Convert USD to EUR if needed (current rate: 0.92)
3. Update rates in `config.yaml`
4. No code changes required (centralized calculation)

## Cost Tracking

### Automatic Logging

All API calls are automatically logged with actual token counts:

```python
# Example from OpenAI embeddings client
response = await client.embeddings.create(...)

# Extract actual token count
token_count = response.usage.total_tokens

# Calculate cost from config
estimated_cost = calculate_api_cost('openai_embeddings', token_count)

# Log to database
insert_cost_log(
    api_name='openai_embeddings',
    num_calls=1,
    token_count=token_count,
    estimated_cost=estimated_cost
)
```

### Logged APIs

| API Name | Description | Cost Model |
|----------|-------------|------------|
| `openai_embeddings` | OpenAI text-embedding-3-small | Per token |
| `gpt4o_judge` | GPT-4o dual judge evaluations | Input + output tokens |
| `haiku_judge` | Haiku dual judge evaluations | Input + output tokens |
| `haiku_eval` | Haiku self-evaluations | Input + output tokens |
| `haiku_reflexion` | Haiku reflexion/verbal RL | Input + output tokens |

### Database Schema

```sql
CREATE TABLE api_cost_log (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    api_name VARCHAR(50) NOT NULL,
    num_calls INTEGER NOT NULL DEFAULT 1,
    token_count INTEGER,
    estimated_cost FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Budget Alerts

### Alert Types

1. **Threshold Alert** (default: 80% of budget)
   - Triggered when projected monthly cost exceeds alert threshold (€8.00)
   - Warning to monitor usage closely

2. **Exceeded Alert**
   - Triggered when projected monthly cost exceeds monthly limit (€10.00)
   - Urgent action required

### Notification Methods

#### Email Alerts

Configure SMTP settings in environment variables:

```bash
# .env or .env.production
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=budget-alerts@example.com
```

Add recipient in `config.yaml`:

```yaml
budget:
  alert_email: "team@example.com"
```

#### Slack Alerts

Create Slack webhook and configure in `config.yaml`:

```yaml
budget:
  alert_slack_webhook: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### Deduplication

Alerts are deduplicated to prevent spam:
- Only one alert of each type per day
- Tracked in `budget_alerts` table
- Manual trigger: `python -m mcp_server.budget alerts --send`

## Cost Optimization

### Optimization Categories

#### 1. Query Expansion (Story 2.2)

**Current Cost Impact:** Embedding costs (4× queries: original + 3 variants)

**Optimization:**
```yaml
# config.yaml
memory:
  query_expansion:
    num_variants: 2  # Reduce from 3 to 2
```

**Trade-off:**
- Savings: ~25% of embedding costs (4→3 queries)
- Impact: ~5% recall reduction (15% → 10% recall uplift)

#### 2. Staged Dual Judge (Story 3.9)

**Current Cost Impact:** Haiku judge costs (50% of dual judge cost)

**Optimization:**
```yaml
# config.yaml
staged_dual_judge:
  dual_judge_enabled: false  # Transition to Single Judge Mode
```

**Requirements:**
- Cohen's Kappa ≥ 0.85 ("Almost Perfect Agreement")
- Minimum 10 ground truth evaluations
- Check readiness: `python -m mcp_server.budget optimize`

**Trade-off:**
- Savings: ~95% of Haiku judge costs (only 5% spot checks)
- Expected: €7.50/mo → €2.50/mo (-40% total budget)
- Impact: Maintains quality via spot checks

#### 3. Evaluation/Reflexion Frequency

**Current Cost Impact:** Haiku eval/reflexion costs

**Optimization:**
```yaml
# config.yaml
memory:
  evaluation:
    reward_threshold: 0.2  # Reduce from 0.3
```

**Trade-off:**
- Savings: ~30% of eval/reflexion costs
- Impact: Fewer reflexions = less verbalized learning

#### 4. Semantic Weight Adjustment

**Current Cost Impact:** Marginal (embedding frequency)

**Optimization:**
```yaml
# config.yaml
memory:
  semantic_weight: 0.5  # Reduce from 0.7 (balanced hybrid)
```

**Trade-off:**
- Savings: ~10% of embedding costs
- Impact: May reduce semantic recall, requires grid search recalibration

### Validation Tools

```bash
# Check Staged Dual Judge transition readiness
python -m mcp_server.budget optimize

# View all recommendations with estimated savings
python -m mcp_server.budget optimize
```

## Integration Guide

### Python API

```python
from mcp_server.budget import (
    get_monthly_cost,
    check_budget_threshold,
    get_optimization_recommendations,
    check_and_send_alerts,
)

# Get current month cost
cost = get_monthly_cost()
print(f"Current month: €{cost:.2f}")

# Check budget status
status = check_budget_threshold()
if status['budget_exceeded']:
    print("❌ Budget exceeded!")
elif status['alert_triggered']:
    print("⚠️  Budget alert!")

# Get optimization recommendations
recommendations = get_optimization_recommendations()
for rec in recommendations:
    print(f"{rec['category']}: €{rec['estimated_savings_eur']:.2f} savings")

# Trigger alerts (respects deduplication)
result = check_and_send_alerts()
if result['alert_sent']:
    print(f"Alert sent via: {result['notification_methods']}")
```

### SQL Integration

Direct SQL queries for Claude Code integration (see `budget-monitoring-sql-queries.md`):

```sql
-- Quick budget check
SELECT
    SUM(estimated_cost) as current_cost,
    SUM(estimated_cost) * 30.0 / EXTRACT(DAY FROM CURRENT_DATE) as projected_cost
FROM api_cost_log
WHERE date >= DATE_TRUNC('month', CURRENT_DATE);
```

### MCP Tool Integration

Future integration with MCP tools (suggested):

```json
{
  "tool": "budget_status",
  "description": "Check current budget status and cost projection",
  "returns": {
    "current_cost": "€3.45",
    "projected_cost": "€8.67",
    "utilization": "86.7%",
    "status": "alert"
  }
}
```

## Troubleshooting

### No cost data showing

**Symptoms:**
- CLI dashboard shows €0.00 costs
- Empty cost breakdown

**Diagnosis:**
```bash
# Check if database has cost entries
psql -U mcp_user -d cognitive_memory -c "SELECT COUNT(*) FROM api_cost_log;"
```

**Solutions:**
1. Ensure migrations are applied: Migration 004 (api_cost_log table)
2. Verify API clients are calling `insert_cost_log()`
3. Check database connection in `mcp_server/db/connection.py`

### Budget alerts not sending

**Symptoms:**
- Budget exceeded but no email/Slack notification
- `alerts --send` returns "alert_sent: false"

**Diagnosis:**
```bash
# Check budget configuration
grep -A 5 "budget:" config/config.yaml

# Test SMTP manually
python -c "import smtplib; smtplib.SMTP('smtp.gmail.com', 587).starttls()"
```

**Solutions:**
1. Configure SMTP environment variables (see [Email Alerts](#email-alerts))
2. Configure Slack webhook in `config.yaml`
3. Check alert deduplication: `SELECT * FROM budget_alerts WHERE alert_date = CURRENT_DATE;`

### Projected cost seems wrong

**Symptoms:**
- Projected cost much higher/lower than expected
- Utilization percentage doesn't match spending rate

**Diagnosis:**
```bash
# Check month progress
python -m mcp_server.budget dashboard
```

**Explanation:**
- Projection uses linear extrapolation: `projected = current + (avg_daily * days_remaining)`
- Early in month (days 1-5): High variance, unreliable projections
- Mid-month (days 10-20): Accurate projections
- End of month (days 25-30): Low variance, accurate but less actionable

**Solutions:**
1. Wait until mid-month for reliable projections
2. Check for anomalous days with `python -m mcp_server.budget daily --days 7`
3. Compare with actual monthly limit: `python -m mcp_server.budget breakdown`

### Cost rates outdated

**Symptoms:**
- Costs don't match API provider invoices
- Exchange rates changed

**Diagnosis:**
```bash
# Check current cost rates
grep -A 10 "api_cost_rates:" config/config.yaml
```

**Solutions:**
1. Check OpenAI pricing: https://openai.com/pricing
2. Check Anthropic pricing: https://www.anthropic.com/pricing
3. Update USD to EUR exchange rate (current: 0.92)
4. Update `config.yaml` rates (Story 3.10 AC-5: Manual updates)

### Optimization recommendations not showing

**Symptoms:**
- `optimize` command shows "No optimization recommendations"
- Expected recommendations missing

**Diagnosis:**
```python
# Check cost breakdown
python -m mcp_server.budget breakdown
```

**Explanation:**
Recommendations only appear when:
- Query Expansion: `num_variants > 2` and embedding costs exist
- Dual Judge: `dual_judge_enabled = true` and Haiku judge costs exist
- Evaluation: Eval/reflexion costs exceed 20% of total
- Semantic Weight: `semantic_weight > 0.5` and embedding costs exist

**Solutions:**
1. Ensure API costs are being logged (check `breakdown`)
2. Verify configuration in `config.yaml`
3. Wait for more data if in early stages of deployment

## Related Documentation

- **Story 3.10**: `bmad-docs/stories/3-10-budget-monitoring-cost-optimization-dashboard.md`
- **PRD**: `bmad-docs/PRD.md` (NFR003: Budget €5-10/mo)
- **SQL Queries**: `budget-monitoring-sql-queries.md`
- **Architecture**: `bmad-docs/architecture.md`
- **Tech Spec**: `bmad-docs/specs/tech-spec-epic-3.md`

## Support

For issues or questions:
1. Check this documentation
2. Review Story 3.10 acceptance criteria
3. Check database migrations (004, 010)
4. Review cost_logger.py and budget/ modules
