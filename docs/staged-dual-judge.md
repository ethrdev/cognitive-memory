# Staged Dual Judge: Budget-Optimierung durch schrittweise Transition

Story 3.9 | Enhancement E8 | Budget-Reduktion -40%

## Überblick

**Staged Dual Judge** ist eine schrittweise Transition von Full Dual Judge (GPT-4o + Haiku für alle Queries) zu Single Judge + 5% Spot Checks, um API-Kosten um 40% zu reduzieren bei maintained Quality.

### Kosteneinsparung

| Phase | Modus | Kosten/Monat | Beschreibung |
|-------|-------|--------------|--------------|
| **Phase 1** | Full Dual Judge | €5-10/mo | Beide Judges evaluieren ALLE Ground Truth Queries |
| **Phase 2** | Single Judge + Spot Checks | €2-3/mo | GPT-4o evaluiert alle, Haiku nur 5% (random sampling) |
| **Savings** | - | **-40%** | **-€2.5-5/mo Einsparung** nach 3 Monaten |

### Transition-Kriterien

**Kappa ≥0.85** ("Almost Perfect Agreement" per Landis & Koch)

- Transition erfolgt **nur**, wenn Judges über letzten 100 Ground Truth Queries "Almost Perfect Agreement" erreichen
- Data-Driven Decision: Kein hart-codierter Timeline, sondern IRR-basiert
- Safety Net: Automatic Revert falls Spot Check Kappa <0.70

### Warum Staged Dual Judge?

1. **Cost Reduction**: Dual Judge ist teuerste API-Komponente (€4-6/mo von €5-10/mo total)
2. **Methodisch Valide**: Transition nur bei erwiesener IRR-Stabilität
3. **Spot Checks**: 5% Sampling erhält Drift Detection mit minimalem Cost Overhead
4. **Automatic Revert**: Falls Judges divergieren → Auto-Revert zu Full Dual Judge

## Transition Process

### Phase 1: Full Dual Judge (Erste 3 Monate)

**Konfiguration:**
```yaml
staged_dual_judge:
  dual_judge_enabled: true  # Full Dual Judge Mode
```

**Evaluation-Strategie:**
- Beide Judges (GPT-4o + Haiku) evaluieren **ALLE** Ground Truth Queries
- Kappa wird für jede Query berechnet
- IRR-Stabilität über Zeit aufgebaut

**Monatliche Evaluation:**
```bash
python scripts/staged_dual_judge_cli.py --evaluate
```

Beispiel-Output:
```
🔍 Staged Dual Judge Evaluation

+-------------------------+--------------------------------------------------+
| Key                     | Value                                            |
+=========================+==================================================+
| Current Kappa           | 0.872                                            |
| Queries Evaluated       | 100                                              |
| Agreement Level         | Almost Perfect                                   |
| Transition Status       | ✅ READY                                         |
| Kappa Threshold         | ≥ 0.85                                           |
| Current Cost            | €7.50/mo (Full Dual Judge)                       |
| Projected Cost          | €2.50/mo (Single Judge + Spot Checks)           |
| Savings                 | -40% (-€5.00/mo)                                |
| Recommendation          | Run 'python ... --transition' to proceed         |
+-------------------------+--------------------------------------------------+

✅ System is ready for transition!
   Run: python scripts/staged_dual_judge_cli.py --transition
```

### Transition Execution

**Manuell (mit Confirmation):**
```bash
python scripts/staged_dual_judge_cli.py --transition
```

CLI fragt nach Bestätigung:
```
⚠️ Confirm Transition to Single Judge Mode
   Current Kappa: 0.872 ≥ 0.85
   This will update config.yaml:
     - dual_judge_enabled: true → false
     - primary_judge: gpt-4o
     - spot_check_rate: 0.05 (5%)

   Cost reduction: €5-10/mo → €2-3/mo (-40%)

   Proceed with transition? (y/n):
```

**Automatisch (ohne Confirmation, z.B. für Scripts):**
```bash
python scripts/staged_dual_judge_cli.py --transition --yes
```

### Phase 2: Single Judge + Spot Checks

**Konfiguration (nach Transition):**
```yaml
staged_dual_judge:
  dual_judge_enabled: false  # Single Judge Mode
  primary_judge: "gpt-4o"
  spot_check_rate: 0.05      # 5% random sampling
```

**Evaluation-Strategie:**
- **95% der Queries**: Nur GPT-4o evaluiert (Primary Judge)
- **5% der Queries**: Beide Judges evaluieren (Spot Check)
  - Random Sampling: `if random.random() < 0.05`
  - Spot Check Flag: `metadata->>'spot_check' = 'true'` in ground_truth table

**Monatliche Spot Check Validation:**

Automatisch via Cron Job (1st of month, midnight):
```bash
0 0 1 * * /path/to/i-o/scripts/validate_spot_checks.sh >> /var/log/mcp-server/spot-check-validation.log 2>&1
```

Oder manuell:
```bash
python scripts/staged_dual_judge_cli.py --validate-spot-checks
```

## Spot Check Mechanism

### Random Sampling

**Für jede neue Ground Truth Query:**

1. **Check Config**: `dual_judge_enabled == false`?
2. **Random Sample**: `if random.random() < spot_check_rate` (0.05 = 5%)
   - **TRUE**: **Spot Check** → Call both judges (GPT-4o + Haiku)
     - Store both scores
     - Mark: `metadata->>'spot_check' = 'true'`
   - **FALSE**: **Primary Judge Only** → Call GPT-4o
     - Store single score
     - Mark: `metadata->>'spot_check' = 'false'`

### Monatliche Kappa Validation

**Am 1. des Monats (Cron Job):**

1. Query all spot checks from last 30 days
2. Calculate Kappa on spot check sample
3. **If Kappa <0.70**:
   - **REVERT to Full Dual Judge**
   - Update config: `dual_judge_enabled: true`
   - Log: "Spot Check Kappa below threshold (X.XX < 0.70), reverting"
   - PostgreSQL log + optional Email/Slack alert
4. **If Kappa ≥0.70**:
   - **CONTINUE Single Judge Mode**
   - Log: "Spot Check Kappa healthy (X.XX ≥ 0.70)"

### Kappa Threshold Rationale

| Threshold | Usage | Rationale |
|-----------|-------|-----------|
| **Kappa ≥0.85** | **Initial Transition** | "Almost Perfect Agreement" - Safe to reduce to Single Judge |
| **Kappa ≥0.70** | **Spot Check Validation** | "Substantial Agreement" - Minimum acceptable, provides buffer gegen Flip-Flopping |

## CLI Usage

### 1. Evaluate Transition Eligibility

```bash
python scripts/staged_dual_judge_cli.py --evaluate
```

**Zeigt:**
- Current Kappa (last 100 queries)
- Transition recommendation (Ready/Not Ready)
- Cost projection (€5-10/mo → €2-3/mo)

**JSON Output (für Automation):**
```bash
python scripts/staged_dual_judge_cli.py --evaluate --format json
```

### 2. Execute Transition

```bash
# Mit Confirmation Prompt
python scripts/staged_dual_judge_cli.py --transition

# Ohne Confirmation (für Scripts)
python scripts/staged_dual_judge_cli.py --transition --yes
```

### 3. View Current Status

```bash
python scripts/staged_dual_judge_cli.py --status
```

**Zeigt:**
- Current mode (Dual Judge or Single Judge + Spot Checks)
- Primary judge
- Spot check rate (if Single Judge Mode)
- Spot check Kappa (last 30 days)
- Health status (HEALTHY or LOW)

**Beispiel Output (Single Judge Mode):**
```
📊 Staged Dual Judge Status

+--------------------------------+-----------------------------------------------+
| Key                            | Value                                         |
+================================+===============================================+
| Current Mode                   | Single Judge + Spot Checks                    |
| Primary Judge                  | gpt-4o                                        |
| Spot Check Rate                | 5%                                            |
| Spot Check Kappa (30 Days)     | 0.823 (15 spot checks)                        |
| Kappa Threshold                | ≥ 0.70                                        |
| Status                         | ✅ HEALTHY                                    |
| Cost                           | €2-3/mo (down from €5-10/mo)                  |
+--------------------------------+-----------------------------------------------+

💡 Tip: Monitor spot check Kappa monthly to ensure quality
```

### 4. Validate Spot Checks (Cron Job)

```bash
python scripts/staged_dual_judge_cli.py --validate-spot-checks
```

**Exit Codes:**
- `0`: Validation passed, continuing Single Judge Mode
- `1`: Validation failed, reverted to Dual Judge Mode
- `2`: Error during validation

## Troubleshooting

### Issue: Kappa Calculation Fails

**Symptom:**
```
❌ Error during evaluation: No Ground Truth data available
```

**Diagnose:**
```bash
# Check Ground Truth table
psql -U mcp_user -d cognitive_memory -c "SELECT COUNT(*) FROM ground_truth WHERE judge1_score IS NOT NULL AND judge2_score IS NOT NULL;"
```

**Lösung:**
- Minimum 100 Ground Truth queries mit beiden Judge scores required
- Run Ground Truth collection (Story 1.11) wenn <100 queries

### Issue: Transition Not Recommended

**Symptom:**
```
⚠️ Not ready for transition
   Reason: Kappa (0.782) < threshold (0.850). Gap: 0.068.
```

**Diagnose:**
```bash
python scripts/staged_dual_judge_cli.py --evaluate
```

**Mögliche Ursachen:**
1. **Insufficient Data**: <100 queries → Collect more Ground Truth data
2. **Judge Disagreement**: Judges disagree zu oft
   - Review judge prompts (mcp_server/tools/dual_judge.py)
   - Check Ground Truth quality (sind Expected Docs korrekt?)
3. **Transition zu früh**: Wait another month, then re-evaluate

**Lösung:**
- **Option A**: Continue collecting Ground Truth data
- **Option B**: Improve judge prompts für better agreement
- **Option C**: Wait for more data, monthly re-evaluation

### Issue: Spot Check Kappa <0.70 (Automatic Revert)

**Symptom:**
```bash
⚠️ Spot Check Kappa below threshold: 0.652 < 0.70 (12 spot checks)
⚠️ Reverted to Full Dual Judge Mode
```

**Diagnose:**
```bash
# Check recent spot checks
psql -U mcp_user -d cognitive_memory -c "
  SELECT created_at, judge1_score, judge2_score, kappa
  FROM ground_truth
  WHERE metadata->>'spot_check' = 'true'
    AND created_at >= NOW() - INTERVAL '30 days'
  ORDER BY created_at DESC;
"
```

**Mögliche Ursachen:**
1. **Judges Diverging**: GPT-4o and Haiku entwickeln unterschiedliche Scoring-Strategien
2. **Data Drift**: Query-Typen ändern sich → Judges disagree mehr
3. **Prompt Drift**: Judge prompts wurden geändert → Inconsistency

**Lösung:**
1. **Investigate Divergence**: Why disagree Judges now?
   - Review recent Ground Truth queries
   - Check for query distribution changes
2. **Stay in Dual Judge**: System auto-reverted → Safe
3. **Re-evaluate after 1 month**: Collect more data, check if divergence temporary

### Issue: Config Update Fails

**Symptom:**
```
❌ Error during transition: Failed to update config: Permission denied
```

**Diagnose:**
```bash
ls -la config/config.yaml
```

**Lösung:**
```bash
# Fix file permissions
chmod 644 config/config.yaml

# Verify YAML syntax
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
```

### Issue: Insufficient Spot Checks (<5 in 30 Days)

**Symptom:**
```
⚠️ Insufficient spot checks for Kappa validation: 3 found, minimum 5 required
```

**Diagnose:**
```bash
# Count spot checks
psql -U mcp_user -d cognitive_memory -c "
  SELECT COUNT(*)
  FROM ground_truth
  WHERE metadata->>'spot_check' = 'true'
    AND created_at >= NOW() - INTERVAL '30 days';
"
```

**Ursache:**
- **Low Query Volume**: Not enough Ground Truth queries in last 30 days
- **Low Spot Check Rate**: 5% of low volume = very few spot checks

**Lösung:**
- **Wait for more data**: Continue collecting, validation will succeed when ≥5 spot checks
- **Increase spot check rate** (temporary): `spot_check_rate: 0.10` (10%) für mehr samples
  - Not recommended: Increases cost

## Integration mit Production Checklist

**Monatliche Tasks (nach Transition):**

1. **Evaluate Transition Eligibility** (während Phase 1):
   ```bash
   python scripts/staged_dual_judge_cli.py --evaluate
   ```
   - Check Kappa progress
   - Execute transition wenn ready

2. **Monitor Spot Check Kappa** (während Phase 2):
   ```bash
   python scripts/staged_dual_judge_cli.py --status
   ```
   - Verify spot check Kappa ≥0.70
   - Check health status

3. **Verify Cost Reduction** (nach Transition):
   ```bash
   # Compare api_cost_log Month N (Dual) vs Month N+1 (Single)
   psql -U mcp_user -d cognitive_memory -c "
     SELECT DATE_TRUNC('month', date) AS month, SUM(estimated_cost) AS total_cost
     FROM api_cost_log
     WHERE date >= NOW() - INTERVAL '2 months'
     GROUP BY month
     ORDER BY month;
   "
   ```
   - Expected: ~40% cost reduction
   - Month N: €5-10/mo (Dual Judge)
   - Month N+1: €2-3/mo (Single Judge)

## Technische Details

### Config.yaml Structure

```yaml
staged_dual_judge:
  # Current Mode
  dual_judge_enabled: true  # false nach Transition

  # Transition Configuration
  kappa_threshold: 0.85

  # Single Judge Mode Settings
  primary_judge: "gpt-4o"
  spot_check_rate: 0.05

  # Spot Check Validation
  spot_check_kappa_threshold: 0.70
  spot_check_validation_interval_days: 30

  # Cost Projections (für CLI display)
  cost_dual_judge_eur_per_month: 7.5
  cost_single_judge_eur_per_month: 2.5
  cost_savings_percentage: 40
```

### Ground Truth Table Schema

```sql
-- Existing columns (Story 1.11)
CREATE TABLE ground_truth (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    expected_docs TEXT[] NOT NULL,
    judge1_score FLOAT[],
    judge2_score FLOAT[],
    judge1_model TEXT,
    judge2_model TEXT,
    kappa FLOAT,
    metadata JSONB,  -- Story 3.9: Spot check flag stored here
    created_at TIMESTAMP DEFAULT NOW()
);

-- Story 3.9: Spot check flag in metadata JSONB
-- metadata->>'spot_check' = 'true'  → Spot check performed
-- metadata->>'spot_check' = 'false' → Primary judge only
```

### Cron Job Setup

```bash
# Edit crontab
crontab -e

# Add monthly validation (1st of month, midnight)
0 0 1 * * /home/user/i-o/scripts/validate_spot_checks.sh >> /var/log/mcp-server/spot-check-validation.log 2>&1
```

**Logging:**
```bash
# View validation logs
tail -f /var/log/mcp-server/spot-check-validation.log
```

## Referenzen

- **Story 3.9**: Staged Dual Judge Implementation (Enhancement E8)
- **Enhancement E8**: Budget optimization via staged approach
- **NFR003**: Budget target €5-10/mo → €2-3/mo
- **Story 1.11**: Dual Judge Implementation (prerequisite)
- **Story 1.12**: IRR Validation & Contingency Plan (prerequisite)
- **Tech Spec**: `bmad-docs/tech-spec-epic-3.md#Story-3.9`
- **Architecture**: `bmad-docs/architecture.md#NFR003-Budget`

---

**Version**: 1.0
**Last Updated**: 2025-11-20
**Author**: BMad Dev-Story Workflow (Story 3.9)
