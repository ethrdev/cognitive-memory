# Budget Monitoring Testing & Validation

Comprehensive testing plan for Story 3.10: Budget Monitoring & Cost Optimization Dashboard

## Acceptance Criteria Mapping

### AC-1: API Cost Tracking Infrastructure ✓

**Requirements:**
- Daily cost logging to api_cost_log table
- Actual token counts from API responses
- Configuration-based cost rates

**Implementation:**
- ✓ Migration 010: Composite index on api_cost_log (date DESC, api_name)
- ✓ cost_logger.py: CRUD operations for cost tracking
- ✓ config.yaml: Centralized cost rates for all APIs
- ✓ calculate_api_cost(): Centralized cost calculation

**Testing Checklist:**
- [ ] Apply migration 010 to database
- [ ] Insert test cost log entry
- [ ] Query cost logs by date range
- [ ] Verify token counts are non-null
- [ ] Verify costs match config rates

**Test Commands:**
```bash
# Apply migration
psql -U mcp_user -d cognitive_memory_dev -f mcp_server/db/migrations/010_api_cost_log_index.sql

# Test cost logger
python -c "
from mcp_server.db.cost_logger import insert_cost_log, get_costs_by_date_range
from datetime import date, timedelta

# Insert test entry
insert_cost_log('test_api', 1, 1000, 0.02)

# Query last 7 days
end = date.today()
start = end - timedelta(days=7)
costs = get_costs_by_date_range(start, end)
print(f'Found {len(costs)} cost entries')
"
```

### AC-2: Monthly Aggregation & Budget Projection ✓

**Requirements:**
- get_monthly_cost(): Current month total
- get_monthly_cost_by_api(): Breakdown by API
- project_monthly_cost(): Linear projection
- check_budget_threshold(): Compare with limits

**Implementation:**
- ✓ budget_monitor.py: All aggregation functions
- ✓ Linear projection: current + (avg_daily × days_remaining)
- ✓ Threshold checks: alert (80%) and exceeded (100%)

**Testing Checklist:**
- [ ] Test get_monthly_cost() with sample data
- [ ] Test get_monthly_cost_by_api() grouping
- [ ] Verify projection calculation accuracy
- [ ] Test threshold detection (80%, 100%)
- [ ] Verify utilization percentage calculation

**Test Commands:**
```bash
# Test monthly aggregation
python -c "
from mcp_server.budget import get_monthly_cost, project_monthly_cost, check_budget_threshold

# Get current month cost
cost = get_monthly_cost()
print(f'Current month: €{cost:.2f}')

# Get projection
projection = project_monthly_cost()
print(f'Projected: €{projection[\"projected_cost\"]:.2f}')

# Check thresholds
status = check_budget_threshold()
print(f'Utilization: {status[\"utilization_pct\"]:.1f}%')
print(f'Alert triggered: {status[\"alert_triggered\"]}')
"
```

### AC-3: Budget Alert System ✓

**Requirements:**
- Email alerts via SMTP
- Slack alerts via webhook
- Deduplication (one alert per type per day)
- Threshold and exceeded alerts

**Implementation:**
- ✓ budget_alerts.py: Email and Slack notification functions
- ✓ budget_alerts table: Alert history and deduplication
- ✓ check_and_send_alerts(): Main alert trigger function

**Testing Checklist:**
- [ ] Configure SMTP settings (.env)
- [ ] Configure Slack webhook (config.yaml)
- [ ] Trigger threshold alert (80% budget)
- [ ] Trigger exceeded alert (100% budget)
- [ ] Verify deduplication (second alert same day fails)
- [ ] Verify alert logging to budget_alerts table

**Test Commands:**
```bash
# Set environment variables
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=test@example.com
export SMTP_PASSWORD=your-app-password

# Update config.yaml with test email/Slack webhook

# Trigger alert check (will send if threshold exceeded)
python -c "
from mcp_server.budget import check_and_send_alerts

result = check_and_send_alerts()
print(f'Alert sent: {result[\"alert_sent\"]}')
if result['alert_sent']:
    print(f'Type: {result[\"alert_type\"]}')
    print(f'Methods: {result[\"notification_methods\"]}')
"

# Verify deduplication (run again immediately)
python -m mcp_server.budget alerts --send
```

### AC-4: Cost Optimization Insights ✓

**Requirements:**
- Cost breakdown analysis
- Optimization recommendations (Query Expansion, Dual Judge, etc.)
- Potential savings calculations
- Staged Dual Judge transition validation

**Implementation:**
- ✓ cost_optimization.py: All insight functions
- ✓ 4 optimization categories with trade-off analysis
- ✓ validate_staged_dual_judge_transition(): Kappa-based validation

**Testing Checklist:**
- [ ] Test get_cost_breakdown_insights() with sample data
- [ ] Verify most expensive API detection
- [ ] Test get_optimization_recommendations()
- [ ] Verify savings calculations
- [ ] Test validate_staged_dual_judge_transition() with ground truth data

**Test Commands:**
```bash
# Test cost optimization insights
python -c "
from mcp_server.budget import (
    get_cost_breakdown_insights,
    get_optimization_recommendations,
    calculate_potential_savings,
    validate_staged_dual_judge_transition,
)

# Get insights
insights = get_cost_breakdown_insights()
print(f'Most expensive: {insights[\"most_expensive\"]}')

# Get recommendations
recommendations = get_optimization_recommendations()
print(f'Found {len(recommendations)} recommendations')
for rec in recommendations:
    print(f'- {rec[\"category\"]}: €{rec[\"estimated_savings_eur\"]:.2f}')

# Check dual judge transition
dj_status = validate_staged_dual_judge_transition()
print(f'Transition ready: {dj_status[\"transition_ready\"]}')
print(f'Kappa: {dj_status[\"current_kappa\"]:.3f}')
"
```

### AC-5: CLI Dashboard Tool ✓

**Requirements:**
- dashboard: Overview
- breakdown: Detailed costs
- optimize: Recommendations
- alerts: Alert management
- daily: Daily summary

**Implementation:**
- ✓ cli.py: All 5 commands with argparse
- ✓ Tabulate formatting for tables
- ✓ Colored status indicators (✓, ⚠️, ❌)

**Testing Checklist:**
- [ ] Test dashboard command
- [ ] Test breakdown command (with --days flag)
- [ ] Test optimize command
- [ ] Test alerts command (with --send flag)
- [ ] Test daily command (with --days flag)
- [ ] Verify table formatting
- [ ] Verify status indicators

**Test Commands:**
```bash
# Test all CLI commands
python -m mcp_server.budget dashboard
python -m mcp_server.budget breakdown --days 7
python -m mcp_server.budget optimize
python -m mcp_server.budget alerts
python -m mcp_server.budget alerts --send
python -m mcp_server.budget daily --days 30

# Verify help messages
python -m mcp_server.budget --help
python -m mcp_server.budget dashboard --help
```

## Integration Testing

### End-to-End Flow

**Scenario: Normal Usage Flow**

1. **API Call** → Cost logged
   ```python
   # Simulate API call logging
   from mcp_server.external.openai_client import OpenAIClient
   from mcp_server.config import calculate_api_cost
   from mcp_server.db.cost_logger import insert_cost_log

   # After API call
   insert_cost_log('openai_embeddings', 1, 1536, 0.00003)
   ```

2. **Daily Monitoring** → View costs
   ```bash
   python -m mcp_server.budget dashboard
   ```

3. **Budget Check** → Alert if needed
   ```bash
   python -m mcp_server.budget alerts --send
   ```

4. **Optimization** → Review recommendations
   ```bash
   python -m mcp_server.budget optimize
   ```

**Scenario: Budget Exceeded Flow**

1. **Insert high-cost entries** to simulate budget exceeded
   ```python
   from mcp_server.db.cost_logger import insert_cost_log
   from datetime import date

   # Simulate €5/day for 30 days = €150/month projected
   for i in range(5):
       insert_cost_log('gpt4o_judge', 100, 100000, 5.0, log_date=date.today())
   ```

2. **Check budget status**
   ```bash
   python -m mcp_server.budget dashboard
   # Should show "❌ BUDGET EXCEEDED"
   ```

3. **Trigger alert**
   ```bash
   python -m mcp_server.budget alerts --send
   # Should send email/Slack notification
   ```

4. **Review recommendations**
   ```bash
   python -m mcp_server.budget optimize
   # Should show recommendations to reduce costs
   ```

## Component Testing

### Budget Monitor Module

```python
import pytest
from datetime import date
from mcp_server.budget.budget_monitor import (
    get_monthly_cost,
    get_monthly_cost_by_api,
    project_monthly_cost,
    check_budget_threshold,
    get_daily_costs,
)

def test_get_monthly_cost():
    """Test monthly cost retrieval."""
    cost = get_monthly_cost()
    assert isinstance(cost, float)
    assert cost >= 0.0

def test_get_monthly_cost_by_api():
    """Test cost breakdown by API."""
    breakdown = get_monthly_cost_by_api()
    assert isinstance(breakdown, list)
    for api in breakdown:
        assert 'api_name' in api
        assert 'total_cost' in api
        assert api['total_cost'] >= 0.0

def test_project_monthly_cost():
    """Test cost projection."""
    projection = project_monthly_cost()
    assert 'current_cost' in projection
    assert 'projected_cost' in projection
    assert 'days_elapsed' in projection
    assert projection['projected_cost'] >= projection['current_cost']

def test_check_budget_threshold():
    """Test budget threshold check."""
    status = check_budget_threshold()
    assert 'projected_cost' in status
    assert 'budget_limit' in status
    assert 'utilization_pct' in status
    assert 'budget_exceeded' in status
    assert 'alert_triggered' in status
    assert status['budget_limit'] == 10.0  # From config

def test_get_daily_costs():
    """Test daily cost retrieval."""
    daily = get_daily_costs(days=7)
    assert isinstance(daily, list)
    for entry in daily:
        assert 'date' in entry
        assert 'total_cost' in entry
```

### Cost Optimization Module

```python
import pytest
from mcp_server.budget.cost_optimization import (
    get_cost_breakdown_insights,
    get_optimization_recommendations,
    calculate_potential_savings,
    validate_staged_dual_judge_transition,
)

def test_get_cost_breakdown_insights():
    """Test cost breakdown insights."""
    insights = get_cost_breakdown_insights()
    assert 'breakdown' in insights
    assert 'most_expensive' in insights
    assert 'cost_distribution' in insights
    assert 'total_cost' in insights

def test_get_optimization_recommendations():
    """Test optimization recommendations."""
    recommendations = get_optimization_recommendations()
    assert isinstance(recommendations, list)
    for rec in recommendations:
        assert 'category' in rec
        assert 'recommendation' in rec
        assert 'estimated_savings_eur' in rec
        assert 'trade_off' in rec

def test_calculate_potential_savings():
    """Test savings calculation."""
    savings = calculate_potential_savings()
    assert 'current_monthly_cost' in savings
    assert 'total_potential_savings' in savings
    assert 'optimized_monthly_cost' in savings
    assert savings['optimized_monthly_cost'] <= savings['current_monthly_cost']

def test_validate_staged_dual_judge_transition():
    """Test Staged Dual Judge transition validation."""
    validation = validate_staged_dual_judge_transition()
    assert 'transition_ready' in validation
    assert 'current_kappa' in validation
    assert 'kappa_threshold' in validation
    assert 'ground_truth_count' in validation
```

### Budget Alerts Module

```python
import pytest
from mcp_server.budget.budget_alerts import check_and_send_alerts

def test_check_and_send_alerts():
    """Test alert checking and sending."""
    result = check_and_send_alerts()
    assert 'budget_status' in result
    assert 'alert_sent' in result
    assert 'alert_type' in result
    assert 'notification_methods' in result

def test_alert_deduplication():
    """Test alert deduplication (one per type per day)."""
    # First call
    result1 = check_and_send_alerts()

    # Second call (should be deduplicated if alert sent)
    result2 = check_and_send_alerts()

    if result1['alert_sent']:
        assert result2.get('reason') == 'duplicate_prevention'
```

## SQL Query Testing

Test SQL queries from `../monitoring/budget-monitoring-sql-queries.md`:

```bash
# Test monthly cost query
psql -U mcp_user -d cognitive_memory_dev -c "
SELECT COALESCE(SUM(estimated_cost), 0.0) as total_cost
FROM api_cost_log
WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE);
"

# Test cost breakdown query
psql -U mcp_user -d cognitive_memory_dev -c "
SELECT
    api_name,
    SUM(estimated_cost) as total_cost,
    SUM(num_calls) as num_calls,
    SUM(token_count) as total_tokens
FROM api_cost_log
WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
GROUP BY api_name
ORDER BY total_cost DESC;
"

# Test budget threshold query
psql -U mcp_user -d cognitive_memory_dev -f - <<'SQL'
-- (Paste budget threshold query from SQL docs)
SQL
```

## Performance Testing

### Query Performance

Test query performance with realistic data volumes:

```sql
-- Insert 1000 cost entries (simulate 1 month of usage)
INSERT INTO api_cost_log (date, api_name, num_calls, token_count, estimated_cost)
SELECT
    CURRENT_DATE - (random() * 30)::int,
    (ARRAY['openai_embeddings', 'gpt4o_judge', 'haiku_judge', 'haiku_eval', 'haiku_reflexion'])[1 + floor(random() * 5)],
    1,
    (random() * 10000)::int,
    random() * 0.1
FROM generate_series(1, 1000);

-- Test monthly aggregation performance
EXPLAIN ANALYZE
SELECT SUM(estimated_cost)
FROM api_cost_log
WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE);

-- Verify index usage
EXPLAIN ANALYZE
SELECT api_name, SUM(estimated_cost)
FROM api_cost_log
WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY api_name;
```

**Expected Performance:**
- Monthly aggregation: <10ms (with index)
- Cost breakdown: <20ms (with index)
- Projection calculation: <30ms (includes multiple queries)

## Production Checklist

Before deploying to production:

- [ ] Apply migration 010 to production database
- [ ] Verify config.yaml has correct API cost rates
- [ ] Set budget.monthly_limit_eur and alert_threshold_pct
- [ ] Configure SMTP settings in production .env
- [ ] Configure Slack webhook in config.yaml
- [ ] Test email alerts with production SMTP
- [ ] Test Slack alerts with production webhook
- [ ] Verify API clients are logging costs
- [ ] Test CLI dashboard with production data
- [ ] Set up cron job for daily budget checks (optional)
- [ ] Document budget monitoring procedures for team

## Monitoring & Observability

### Daily Monitoring Script

Create cron job for daily budget checks:

```bash
# Add to crontab
0 9 * * * cd /path/to/i-o && python -m mcp_server.budget alerts --send >> /var/log/budget-alerts.log 2>&1
```

### Logging

Check logs for cost tracking:

```bash
# Search for cost logging events
grep "API cost logged" logs/cognitive_memory_dev.log

# Check alert sends
grep "Budget alert" logs/cognitive_memory_dev.log
```

### Database Monitoring

Monitor api_cost_log table growth:

```sql
-- Check table size
SELECT
    pg_size_pretty(pg_total_relation_size('api_cost_log')) as table_size,
    (SELECT COUNT(*) FROM api_cost_log) as row_count;

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as scans,
    idx_tup_read as tuples_read
FROM pg_stat_user_indexes
WHERE tablename = 'api_cost_log';
```

## Known Issues & Limitations

1. **Early Month Projections**: Projections in days 1-5 have high variance
   - **Mitigation**: Wait until mid-month for reliable projections

2. **Manual Cost Rate Updates**: Rates must be manually updated in config.yaml
   - **Mitigation**: Set calendar reminder to check API pricing quarterly

3. **Alert Deduplication**: Only one alert per type per day
   - **Mitigation**: Run `alerts --send` multiple times manually if needed

4. **No Real-time Alerts**: Alerts require manual trigger or cron job
   - **Future**: Implement background worker for continuous monitoring

## Next Steps

After validation:

1. **Mark Story 3.10 as DONE** in sprint-status.yaml
2. **Create Story 3.11** (if needed) for additional features:
   - Real-time alert monitoring
   - Historical trend analysis
   - Cost forecast models
3. **Document findings** in retrospective
4. **Share budget dashboard** with team

## Support

For testing issues:
- Review `../monitoring/budget-monitoring.md` troubleshooting section
- Check database connection and migrations
- Verify config.yaml configuration
- Review logs for error messages
