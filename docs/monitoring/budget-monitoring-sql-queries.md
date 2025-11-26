# Budget Monitoring SQL Queries

SQL query templates for Claude Code to access budget and cost data directly.

## Table of Contents
- [Core Tables](#core-tables)
- [Monthly Aggregation Queries](#monthly-aggregation-queries)
- [Cost Breakdown Queries](#cost-breakdown-queries)
- [Budget Status Queries](#budget-status-queries)
- [Daily Cost Queries](#daily-cost-queries)
- [Optimization Analysis Queries](#optimization-analysis-queries)

## Core Tables

### api_cost_log

Main table for tracking API costs (created in migration 004).

```sql
-- Table structure
CREATE TABLE api_cost_log (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    api_name VARCHAR(50) NOT NULL,
    num_calls INTEGER NOT NULL DEFAULT 1,
    token_count INTEGER,
    estimated_cost FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_api_cost_date ON api_cost_log(date DESC);
CREATE INDEX idx_api_cost_name ON api_cost_log(api_name, date DESC);
CREATE INDEX idx_cost_date_api ON api_cost_log(date DESC, api_name);  -- Story 3.10
```

**API Name Values:**
- `openai_embeddings` - OpenAI text-embedding-3-small
- `gpt4o_judge` - GPT-4o dual judge evaluations
- `haiku_judge` - Claude Haiku dual judge evaluations
- `haiku_eval` - Claude Haiku self-evaluations
- `haiku_reflexion` - Claude Haiku reflexion/verbal RL

## Monthly Aggregation Queries

### Get Total Monthly Cost

Get total API cost for current month:

```sql
SELECT COALESCE(SUM(estimated_cost), 0.0) as total_cost
FROM api_cost_log
WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE);
```

Get total cost for specific month:

```sql
SELECT COALESCE(SUM(estimated_cost), 0.0) as total_cost
FROM api_cost_log
WHERE EXTRACT(YEAR FROM date) = 2025
  AND EXTRACT(MONTH FROM date) = 11;
```

### Get Monthly Cost by API

Monthly cost breakdown by API (current month):

```sql
SELECT
    api_name,
    SUM(estimated_cost) as total_cost,
    SUM(num_calls) as num_calls,
    SUM(token_count) as total_tokens,
    ROUND((SUM(estimated_cost) / SUM(SUM(estimated_cost)) OVER () * 100)::numeric, 1) as cost_pct
FROM api_cost_log
WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
GROUP BY api_name
ORDER BY total_cost DESC;
```

## Cost Breakdown Queries

### Most Expensive API

Identify most expensive API for current month:

```sql
SELECT
    api_name,
    SUM(estimated_cost) as total_cost
FROM api_cost_log
WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
GROUP BY api_name
ORDER BY total_cost DESC
LIMIT 1;
```

### Cost per API Call

Average cost per API call by API type:

```sql
SELECT
    api_name,
    SUM(estimated_cost) as total_cost,
    SUM(num_calls) as total_calls,
    ROUND((SUM(estimated_cost) / NULLIF(SUM(num_calls), 0))::numeric, 6) as cost_per_call
FROM api_cost_log
WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
GROUP BY api_name
ORDER BY cost_per_call DESC;
```

## Budget Status Queries

### Current Month Progress

Calculate month-to-date cost and projection:

```sql
WITH month_stats AS (
    SELECT
        DATE_TRUNC('month', CURRENT_DATE) as month_start,
        DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day' as month_end,
        CURRENT_DATE - DATE_TRUNC('month', CURRENT_DATE)::date + 1 as days_elapsed
),
current_cost AS (
    SELECT COALESCE(SUM(estimated_cost), 0.0) as mtd_cost
    FROM api_cost_log
    WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
      AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
)
SELECT
    ms.month_start,
    ms.month_end,
    ms.days_elapsed,
    EXTRACT(DAY FROM ms.month_end) as days_in_month,
    EXTRACT(DAY FROM ms.month_end) - ms.days_elapsed as days_remaining,
    cc.mtd_cost as current_cost,
    ROUND((cc.mtd_cost / NULLIF(ms.days_elapsed, 0))::numeric, 4) as avg_daily_cost,
    ROUND((cc.mtd_cost + (cc.mtd_cost / NULLIF(ms.days_elapsed, 0) * (EXTRACT(DAY FROM ms.month_end) - ms.days_elapsed)))::numeric, 2) as projected_cost
FROM month_stats ms, current_cost cc;
```

### Budget Threshold Check

Check if projected cost exceeds budget (assumes €10.00 limit, 80% alert threshold):

```sql
WITH month_stats AS (
    SELECT
        CURRENT_DATE - DATE_TRUNC('month', CURRENT_DATE)::date + 1 as days_elapsed,
        EXTRACT(DAY FROM DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day') as days_in_month
),
current_cost AS (
    SELECT COALESCE(SUM(estimated_cost), 0.0) as mtd_cost
    FROM api_cost_log
    WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
      AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
),
projection AS (
    SELECT
        ms.days_elapsed,
        ms.days_in_month,
        cc.mtd_cost,
        cc.mtd_cost / NULLIF(ms.days_elapsed, 0) as avg_daily_cost
    FROM month_stats ms, current_cost cc
)
SELECT
    mtd_cost as current_cost,
    mtd_cost + (avg_daily_cost * (days_in_month - days_elapsed)) as projected_cost,
    10.0 as budget_limit,
    8.0 as alert_threshold,
    ROUND(((mtd_cost + (avg_daily_cost * (days_in_month - days_elapsed))) / 10.0 * 100)::numeric, 1) as utilization_pct,
    CASE
        WHEN (mtd_cost + (avg_daily_cost * (days_in_month - days_elapsed))) > 10.0 THEN 'EXCEEDED'
        WHEN (mtd_cost + (avg_daily_cost * (days_in_month - days_elapsed))) > 8.0 THEN 'ALERT'
        ELSE 'OK'
    END as status
FROM projection;
```

## Daily Cost Queries

### Daily Cost Totals

Get daily cost totals for last 30 days:

```sql
SELECT
    date,
    SUM(estimated_cost) as total_cost,
    SUM(num_calls) as num_calls,
    SUM(token_count) as total_tokens
FROM api_cost_log
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date
ORDER BY date DESC;
```

### Daily Cost by API

Daily breakdown by API for last 7 days:

```sql
SELECT
    date,
    api_name,
    SUM(estimated_cost) as daily_cost,
    SUM(num_calls) as calls,
    SUM(token_count) as tokens
FROM api_cost_log
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY date, api_name
ORDER BY date DESC, daily_cost DESC;
```

## Optimization Analysis Queries

### Embeddings Cost Analysis

Analyze OpenAI embeddings cost for query expansion optimization:

```sql
-- Get monthly embeddings cost
SELECT
    SUM(estimated_cost) as embeddings_cost,
    SUM(num_calls) as embedding_calls,
    SUM(token_count) as total_tokens,
    ROUND((SUM(estimated_cost) / NULLIF(SUM(num_calls), 0))::numeric, 6) as cost_per_embedding
FROM api_cost_log
WHERE api_name = 'openai_embeddings'
  AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE);
```

### Dual Judge Cost Analysis

Analyze Dual Judge costs for Story 3.9 transition evaluation:

```sql
SELECT
    api_name,
    SUM(estimated_cost) as total_cost,
    SUM(num_calls) as num_evaluations,
    ROUND((SUM(estimated_cost) / NULLIF(SUM(num_calls), 0))::numeric, 6) as cost_per_eval
FROM api_cost_log
WHERE api_name IN ('gpt4o_judge', 'haiku_judge')
  AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
GROUP BY api_name
ORDER BY total_cost DESC;
```

**Interpretation:**
- If `haiku_judge` cost is high and you're in Full Dual Judge Mode, transitioning to Single Judge Mode (Story 3.9) can save ~95% of Haiku judge costs
- Check Cohen's Kappa in ground_truth table to validate readiness for transition

### Evaluation/Reflexion Cost Analysis

Analyze Haiku evaluation and reflexion costs:

```sql
SELECT
    api_name,
    SUM(estimated_cost) as total_cost,
    SUM(num_calls) as num_calls,
    ROUND((SUM(estimated_cost) / (
        SELECT SUM(estimated_cost)
        FROM api_cost_log
        WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
          AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
    ) * 100)::numeric, 1) as pct_of_total
FROM api_cost_log
WHERE api_name IN ('haiku_eval', 'haiku_reflexion')
  AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
GROUP BY api_name;
```

**Optimization Opportunity:**
- If evaluation/reflexion costs exceed 20% of total, consider increasing `evaluation.reward_threshold` from 0.3 to 0.2 to reduce reflexion frequency

## Historical Analysis Queries

### Monthly Cost Trend

Compare current month with previous months:

```sql
SELECT
    TO_CHAR(DATE_TRUNC('month', date), 'YYYY-MM') as month,
    SUM(estimated_cost) as monthly_cost,
    SUM(num_calls) as total_calls,
    SUM(token_count) as total_tokens
FROM api_cost_log
WHERE date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '6 months'
GROUP BY DATE_TRUNC('month', date)
ORDER BY month DESC;
```

### Cost Growth Rate

Calculate month-over-month cost growth:

```sql
WITH monthly_costs AS (
    SELECT
        DATE_TRUNC('month', date) as month,
        SUM(estimated_cost) as cost
    FROM api_cost_log
    GROUP BY DATE_TRUNC('month', date)
    ORDER BY month DESC
    LIMIT 2
),
ranked AS (
    SELECT
        month,
        cost,
        LAG(cost) OVER (ORDER BY month) as prev_cost
    FROM monthly_costs
)
SELECT
    month,
    cost as current_month_cost,
    prev_cost as previous_month_cost,
    ROUND(((cost - prev_cost) / NULLIF(prev_cost, 0) * 100)::numeric, 1) as growth_pct
FROM ranked
WHERE prev_cost IS NOT NULL;
```

## Alert History Queries

### Recent Budget Alerts

Query recent budget alerts (requires budget_alerts table from Task 4):

```sql
SELECT
    alert_date,
    alert_type,
    projected_cost,
    budget_limit,
    utilization_pct,
    alert_sent,
    notification_methods,
    created_at
FROM budget_alerts
ORDER BY alert_date DESC, created_at DESC
LIMIT 10;
```

### Alert Frequency

Count alerts by type in last 30 days:

```sql
SELECT
    alert_type,
    COUNT(*) as alert_count,
    AVG(utilization_pct) as avg_utilization,
    MAX(projected_cost) as max_projected_cost
FROM budget_alerts
WHERE alert_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY alert_type
ORDER BY alert_count DESC;
```

## Usage Examples for Claude Code

### Quick Budget Check

```sql
-- One-liner to check current budget status
WITH cost AS (
    SELECT SUM(estimated_cost) as mtd
    FROM api_cost_log
    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
)
SELECT
    mtd as current_cost,
    mtd * 30.0 / EXTRACT(DAY FROM CURRENT_DATE) as projected_cost,
    CASE
        WHEN mtd * 30.0 / EXTRACT(DAY FROM CURRENT_DATE) > 10.0 THEN '❌ EXCEEDED'
        WHEN mtd * 30.0 / EXTRACT(DAY FROM CURRENT_DATE) > 8.0 THEN '⚠️  ALERT'
        ELSE '✓ OK'
    END as status
FROM cost;
```

### Cost Summary for User Query

```sql
-- Formatted cost summary for display
SELECT
    '💰 Budget Status' as section,
    CONCAT('€', ROUND(SUM(estimated_cost)::numeric, 2)) as current_cost,
    CONCAT('€', ROUND((SUM(estimated_cost) * 30.0 / EXTRACT(DAY FROM CURRENT_DATE))::numeric, 2)) as projected,
    CONCAT(ROUND((SUM(estimated_cost) * 30.0 / EXTRACT(DAY FROM CURRENT_DATE) / 10.0 * 100)::numeric, 0), '%') as utilization
FROM api_cost_log
WHERE date >= DATE_TRUNC('month', CURRENT_DATE);
```

## Configuration References

These queries assume default budget configuration from `config/config.yaml`:

```yaml
budget:
  monthly_limit_eur: 10.0      # Monthly budget limit
  alert_threshold_pct: 80      # Alert at 80% = €8.00
```

To use different budget values, replace `10.0` and `8.0` in queries with actual configured values.

## Performance Notes

- All queries use indexes from migrations 004 and 010
- `idx_cost_date_api` composite index optimizes date + API filtering
- Month-to-date queries scan current month only (typically <30 rows per API)
- Historical trend queries may scan multiple months (consider adding LIMIT)

## Related Documentation

- **PRD**: `bmad-docs/PRD.md` - NFR003 Budget requirements
- **Story 3.10**: `bmad-docs/stories/3-10-budget-monitoring-cost-optimization-dashboard.md`
- **Migration 004**: `mcp_server/db/migrations/004_api_tracking_tables.sql`
- **Migration 010**: `mcp_server/db/migrations/010_api_cost_log_index.sql`
- **Python API**: `mcp_server/budget/` - Budget monitoring modules
