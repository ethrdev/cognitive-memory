# Quality Gate Pipeline

## Overview

The Quality Gate Pipeline ensures code quality through automated testing and coverage requirements. It operates on a **priority-based test execution model** with progressive gates.

---

## Test Priorities

### P0 - Critical Path Tests
**Must Pass** - Required for every commit and PR

- ✅ Constitutive edge protection
- ✅ SMF bilateral consent approval
- ✅ Memory sector reclassification (core functionality)

**Execution:** `pytest tests/ -k "test_p0" -v`

### P1 - High Priority Tests
**Must Pass** - Required for PR to main

- ✅ Dissonance detection and resolution
- ✅ SMF workflow (approve, reject, review, bulk operations)
- ✅ Golden test results and drift detection
- ✅ Memory sector classification accuracy

**Execution:** `pytest tests/ -k "test_p1" -v`

### P2 - Medium Priority Tests
**Should Pass** - Run in CI, can fail without blocking PR

- ✅ Edge suggestions and lateral connections
- ✅ Performance optimizations
- ✅ Edge cases and error handling

**Execution:** `pytest tests/ -k "test_p2" -v`

### P3 - Low Priority Tests
**Optional** - Run on-demand or nightly

- ✅ Experimental features
- ✅ Rare edge cases
- ✅ Documentation and examples

---

## Running Quality Gates

### Locally

```bash
# Run the complete quality gate pipeline
./scripts/run-quality-gate.sh

# Or run individual priorities
pytest tests/ -k "test_p0" -v      # Critical paths only
pytest tests/ -k "test_p1" -v      # P0 + P1 tests
pytest tests/ -k "test_p2" -v      # All tests
```

### In CI (GitHub Actions)

The pipeline automatically runs on:

1. **Pull Request** - Runs P0, P1, P2 tests
2. **Push to Main** - Runs all tests including performance
3. **Nightly** - Can be scheduled for full regression

---

## Coverage Requirements

### Minimum Coverage Thresholds

- **Overall Coverage:** 80% (minimum)
- **Critical Paths (P0):** 100% (must)
- **High Priority (P1):** 90% (should)

### Coverage Commands

```bash
# Generate coverage report
coverage run -m pytest tests/
coverage report --show-missing
coverage html

# Check specific file coverage
coverage run -m pytest tests/test_reclassify_memory_sector.py
coverage report --include="mcp_server/tools/reclassify_memory_sector"
```

---

## MCP Tools Coverage

### Current Status

- **Total MCP Tools:** 22
- **Tested Tools:** 18 (82%)
- **Untested Tools:** 4 (18%)

### Coverage by Category

✅ **Tested (18 tools):**
- Core graph operations (4 tools)
- Memory storage and retrieval (5 tools)
- SMF workflow (6 tools)
- Dissonance engine (2 tools)
- Validation and verification (1 tool)

⚠️ **Untested (4 tools):**
- get_golden_test_results
- resolve_dissonance
- dissonance_check
- suggest_lateral_edges

### Coverage Commands

```bash
# Count total tools
find mcp_server/tools -name "*.py" ! -name "__init__.py" | wc -l

# Count tested tools
grep -l "test_" tests/test_*.py | wc -l

# List untested tools
for tool in mcp_server/tools/*.py; do
  name=$(basename "$tool" .py)
  if [ ! -f "tests/test_${name}.py" ]; then
    echo "⚠ $name"
  fi
done
```

---

## Quality Gate Rules

### Pre-Merge Requirements

A PR can only be merged if:

1. ✅ All P0 tests pass (100%)
2. ✅ All P1 tests pass (100%)
3. ✅ Overall coverage ≥ 80%
4. ✅ No new critical vulnerabilities

### Pre-Commit Hooks (Optional)

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

---

## Interpreting Results

### Success Indicators

```
✓ QUALITY GATE PASSED

All P0 and P1 tests passed.
Coverage: 85% (min: 80%)
Bonus: All P2 tests passed
Coverage requirement met
```

### Failure Indicators

```
✗ QUALITY GATE FAILED

Critical tests failed:
  ✗ P0 tests failed
  ✗ P1 tests failed

Please fix failing tests before merging.
```

---

## Troubleshooting

### Common Issues

**Issue:** P0 tests failing
```bash
# Check what's failing
pytest tests/ -k "test_p0" -v

# Common causes:
# - Missing database fixtures
# - Incorrect mocking
# - Environment not set up
```

**Issue:** Coverage below minimum
```bash
# Find uncovered lines
coverage report --show-missing

# Generate HTML report for visual inspection
coverage html
open htmlcov/index.html
```

**Issue:** MCP tool tests not running
```bash
# Verify test file naming convention
ls tests/test_*.py | grep -E "(golden|dissonance|resolve|smf|suggest)"

# Check test discovery
pytest --collect-only tests/ | grep -E "(golden|dissonance|resolve|smf|suggest)"
```

---

## Adding New Tests

### Test File Naming

```
tests/test_{tool_name}.py
```

Example:
- `mcp_server/tools/reclassify_memory_sector.py`
- → `tests/test_reclassify_memory_sector.py`

### Test Structure

```python
import pytest

class TestToolName:
    """Test cases for tool_name tool"""

    @pytest.mark.p0  # or p1, p2, p3
    def test_critical_functionality(self, mock_db):
        """
        [P0] Should perform critical action
        """
        # GIVEN: Setup
        # WHEN: Action
        # THEN: Assertion
        pass
```

### Priority Guidelines

- **P0:** Critical paths, security, data integrity
- **P1:** Important features, error handling
- **P2:** Edge cases, performance, rare conditions
- **P3:** Nice-to-have, experimental

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/quality-gate.yml

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Run Quality Gate
        run: ./scripts/run-quality-gate.sh
      
      - name: Upload Coverage
        uses: codecov/codecov-action@v3
```

### Customization

Edit `.github/workflows/quality-gate.yml` to:
- Change Python version
- Adjust coverage thresholds
- Add/remove test categories
- Configure artifacts retention

---

## Best Practices

### Writing Tests

1. ✅ Use Given-When-Then structure
2. ✅ One assertion per test (atomic)
3. ✅ Use descriptive test names with priority tags
4. ✅ Mock external dependencies
5. ✅ Ensure auto-cleanup

### Avoiding Flaky Tests

1. ❌ No hard waits (`time.sleep()`)
2. ❌ No conditional logic in tests
3. ❌ No shared state between tests
4. ❌ No hardcoded values (use factories)

### Test Data

Use factories for consistent test data:

```python
from tests.factories import EdgeFactory

# Create test edge
edge = EdgeFactory().create(conn, source="A", target="B")
```

---

## Metrics and Monitoring

### Key Metrics

- **Test Pass Rate:** P0: 100%, P1: 100%, P2: >90%
- **Coverage:** Overall >80%, P0 >100%, P1 >90%
- **MCP Tools Coverage:** Target 90%+
- **Performance:** <5s per test (average)

### Dashboard

View metrics in:
- GitHub Actions summary
- Codecov dashboard
- Quality report artifact

---

## Support

### Getting Help

1. Check this documentation
2. Review test examples in `tests/`
3. Ask in project channels
4. Create issue with quality-gate tag

### Reporting Issues

Include:
- Test output (`pytest -v`)
- Coverage report
- System information (OS, Python version)
- Steps to reproduce

---

## Changelog

### 2026-01-14 - Initial Quality Gate
- Added P0/P1/P2/P3 priority system
- Created quality gate script
- Set up GitHub Actions workflow
- Established 80% coverage minimum
- MCP tools coverage tracking

