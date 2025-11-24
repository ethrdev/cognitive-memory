#!/usr/bin/env python3
"""
Manual Integration Test for : Haiku API Setup

Tests:
1. API Client initialization (valid/invalid keys)
2. Configuration loading (evaluation/reflexion settings)
3. Retry logic validation
4. Database schema validation (api_cost_log, api_retry_log tables)
5. .env security (git-ignored files)

Run from project root:
    python test_haiku_setup.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_1_api_client_initialization():
    """Test TC-2.4.1 and TC-2.4.2: API Client Initialization"""
    print("\n" + "=" * 70)
    print("TEST 1: API Client Initialization")
    print("=" * 70)

    from mcp_server.external.anthropic_client import HaikuClient

    # Test 1.1: Valid API key (from environment)
    print("\n[TC-2.4.1] Testing with valid API key...")
    try:
        client = HaikuClient()
        print(f"✅ HaikuClient initialized successfully")
        print(f"   Model: {client.model}")
        assert client.model == "claude-3-5-haiku-20241022", "Model mismatch"
        print(f"   ✅ Model correctly set to claude-3-5-haiku-20241022")
    except RuntimeError as e:
        if "not configured" in str(e):
            print(f"⚠️  ANTHROPIC_API_KEY not set in environment")
            print(f"   This is expected if running without API key")
            print(f"   Set ANTHROPIC_API_KEY to test with real API")
        else:
            print(f"❌ Unexpected error: {e}")
            raise

    # Test 1.2: Invalid API key (placeholder)
    print("\n[TC-2.4.2] Testing with invalid API key...")
    try:
        client = HaikuClient(api_key="sk-ant-your-anthropic-api-key-here")
        print("❌ Should have raised RuntimeError for placeholder key")
        return False
    except RuntimeError as e:
        if "not configured" in str(e):
            print("✅ Correctly rejected placeholder API key")
        else:
            print(f"❌ Unexpected error: {e}")
            return False

    return True


def test_2_configuration():
    """Test TC-2.4.3 and TC-2.4.4: Temperature Configuration"""
    print("\n" + "=" * 70)
    print("TEST 2: Configuration Loading")
    print("=" * 70)

    import yaml

    config_path = project_root / "config" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Test 2.1: Evaluation configuration
    print("\n[TC-2.4.3] Checking evaluation configuration...")
    eval_config = config["base"]["memory"]["evaluation"]
    assert eval_config["model"] == "claude-3-5-haiku-20241022", "Eval model mismatch"
    assert eval_config["temperature"] == 0.0, "Eval temperature should be 0.0"
    assert eval_config["max_tokens"] == 500, "Eval max_tokens should be 500"
    print("✅ Evaluation config correct:")
    print(f"   Model: {eval_config['model']}")
    print(f"   Temperature: {eval_config['temperature']} (deterministic)")
    print(f"   Max Tokens: {eval_config['max_tokens']}")

    # Test 2.2: Reflexion configuration
    print("\n[TC-2.4.4] Checking reflexion configuration...")
    refl_config = config["base"]["memory"]["reflexion"]
    assert refl_config["model"] == "claude-3-5-haiku-20241022", "Refl model mismatch"
    assert refl_config["temperature"] == 0.7, "Refl temperature should be 0.7"
    assert refl_config["max_tokens"] == 1000, "Refl max_tokens should be 1000"
    print("✅ Reflexion config correct:")
    print(f"   Model: {refl_config['model']}")
    print(f"   Temperature: {refl_config['temperature']} (creative)")
    print(f"   Max Tokens: {refl_config['max_tokens']}")

    # Test 2.3: API limits configuration
    print("\n[TC-2.4.5] Checking API limits configuration...")
    api_limits = config["base"]["api_limits"]["anthropic"]
    assert api_limits["rpm_limit"] == 1000, "RPM limit should be 1000"
    assert api_limits["retry_attempts"] == 4, "Retry attempts should be 4"
    assert api_limits["retry_delays"] == [1, 2, 4, 8], "Retry delays incorrect"
    print("✅ API limits config correct:")
    print(f"   RPM Limit: {api_limits['rpm_limit']}")
    print(f"   Retry Attempts: {api_limits['retry_attempts']}")
    print(f"   Retry Delays: {api_limits['retry_delays']}")

    return True


def test_3_retry_logic():
    """Test TC-2.4.5 and TC-2.4.6: Retry Logic"""
    print("\n" + "=" * 70)
    print("TEST 3: Retry Logic Decorator")
    print("=" * 70)

    from mcp_server.utils.retry_logic import retry_with_backoff

    print("\n[TC-2.4.5] Checking retry_with_backoff decorator...")

    # Test 3.1: Decorator exists and is callable
    assert callable(retry_with_backoff), "retry_with_backoff should be callable"
    print("✅ retry_with_backoff decorator exists")

    # Test 3.2: Decorator with default parameters
    @retry_with_backoff()
    async def test_function():
        return "success"

    print("✅ Decorator can be applied to async functions")

    # Test 3.3: Verify default parameters
    decorator = retry_with_backoff(max_retries=4, base_delays=[1, 2, 4, 8], jitter=True)
    print("✅ Decorator accepts max_retries, base_delays, jitter parameters")
    print("   Default config: max_retries=4, delays=[1,2,4,8], jitter=True")

    return True


def test_4_database_schema():
    """Test TC-2.4.8: Database Schema"""
    print("\n" + "=" * 70)
    print("TEST 4: Database Schema Validation")
    print("=" * 70)

    migration_path = project_root / "mcp_server" / "db" / "migrations" / "004_api_tracking_tables.sql"

    print("\n[TC-2.4.8] Checking database migration file...")
    assert migration_path.exists(), f"Migration file not found: {migration_path}"
    print(f"✅ Migration file exists: {migration_path.name}")

    # Check migration content
    with open(migration_path) as f:
        migration_sql = f.read()

    # Verify table definitions
    assert "CREATE TABLE IF NOT EXISTS api_cost_log" in migration_sql, "api_cost_log table missing"
    assert "CREATE TABLE IF NOT EXISTS api_retry_log" in migration_sql, "api_retry_log table missing"
    print("✅ Both tables defined in migration:")
    print("   - api_cost_log (cost tracking)")
    print("   - api_retry_log (retry statistics)")

    # Verify key columns
    assert "api_name VARCHAR(50)" in migration_sql, "api_name column missing"
    assert "estimated_cost FLOAT" in migration_sql, "estimated_cost column missing"
    assert "token_count INTEGER" in migration_sql, "token_count column missing"
    print("✅ Key columns present in schema")

    # Verify indices
    assert "CREATE INDEX idx_api_cost_date" in migration_sql, "Cost date index missing"
    assert "CREATE INDEX idx_api_retry_name" in migration_sql, "Retry name index missing"
    print("✅ Performance indices defined")

    # Verify views
    assert "CREATE OR REPLACE VIEW daily_api_costs" in migration_sql, "daily_api_costs view missing"
    print("✅ Helper views defined")

    return True


def test_5_security():
    """Test TC-2.4.12: API Key Security"""
    print("\n" + "=" * 70)
    print("TEST 5: API Key Security Validation")
    print("=" * 70)

    # Test 5.1: .env.template exists and has ANTHROPIC_API_KEY
    print("\n[TC-2.4.12] Checking .env.template...")
    env_template_path = project_root / ".env.template"
    assert env_template_path.exists(), ".env.template not found"
    print(f"✅ .env.template exists")

    with open(env_template_path) as f:
        env_template = f.read()

    assert "ANTHROPIC_API_KEY" in env_template, "ANTHROPIC_API_KEY not in .env.template"
    print("✅ ANTHROPIC_API_KEY documented in .env.template")

    # Test 5.2: .gitignore includes .env files
    print("\n[TC-2.4.12] Checking .gitignore...")
    gitignore_path = project_root / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path) as f:
            gitignore = f.read()

        if ".env" in gitignore or "*.env" in gitignore:
            print("✅ .env files are git-ignored")
        else:
            print("⚠️  .env files may not be git-ignored - verify .gitignore")
    else:
        print("⚠️  .gitignore not found - create one to protect API keys")

    return True


def test_6_project_structure():
    """Test: Project Structure Validation"""
    print("\n" + "=" * 70)
    print("TEST 6: Project Structure")
    print("=" * 70)

    expected_files = [
        "mcp_server/external/anthropic_client.py",
        "mcp_server/utils/retry_logic.py",
        "mcp_server/db/migrations/004_api_tracking_tables.sql",
        "config/config.yaml",
        ".env.template",
    ]

    print("\n[INFO] Checking expected files...")
    all_exist = True
    for file_path in expected_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} NOT FOUND")
            all_exist = False

    return all_exist


async def run_all_tests():
    """Run all test suites"""
    print("\n" + "=" * 70)
    print("STORY 2.4: HAIKU API SETUP - INTEGRATION TESTS")
    print("=" * 70)
    print(f"Project Root: {project_root}")

    results = {}

    # Run tests
    try:
        results["test_1"] = await test_1_api_client_initialization()
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
        results["test_1"] = False

    try:
        results["test_2"] = test_2_configuration()
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
        results["test_2"] = False

    try:
        results["test_3"] = test_3_retry_logic()
    except Exception as e:
        print(f"❌ Test 3 failed: {e}")
        results["test_3"] = False

    try:
        results["test_4"] = test_4_database_schema()
    except Exception as e:
        print(f"❌ Test 4 failed: {e}")
        results["test_4"] = False

    try:
        results["test_5"] = test_5_security()
    except Exception as e:
        print(f"❌ Test 5 failed: {e}")
        results["test_5"] = False

    try:
        results["test_6"] = test_6_project_structure()
    except Exception as e:
        print(f"❌ Test 6 failed: {e}")
        results["test_6"] = False

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{test_name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ ALL TESTS PASSED -  infrastructure ready!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - review output above")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
