#!/usr/bin/env python3
"""
Manual Test Script for SSL Timeout Fix

This script tests the SSL timeout fix by:
1. Verifying TCP keep-alive settings are configured
2. Testing pool validator thread functionality
3. Running an idle connection test (>30 seconds)

Usage:
    python tests/manual/test_ssl_fix_manual.py

Requirements:
    - DATABASE_URL environment variable set
    - 40+ seconds of runtime for idle test
"""

import os
import sys
import time


def test_tcp_keepalive_settings():
    """Test 1: Verify TCP keep-alive settings are passed to pool."""
    print("\n" + "=" * 60)
    print("TEST 1: TCP Keep-Alive Settings")
    print("=" * 60)

    from unittest.mock import MagicMock, patch

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
        with patch("mcp_server.db.connection.pool.SimpleConnectionPool") as mock_pool:
            mock_pool_instance = MagicMock()
            mock_pool_instance.minconn = 1
            mock_pool_instance.maxconn = 10
            mock_pool_instance._pool = []
            mock_pool_instance._used = []
            mock_pool_instance.closed = False
            mock_pool.return_value = mock_pool_instance

            # Mock get_connection to avoid real DB call during init
            with patch("mcp_server.db.connection.get_connection"):
                from mcp_server.db.connection import initialize_pool_sync

                initialize_pool_sync()

                # Check TCP keep-alive settings
                call_kwargs = mock_pool.call_args[1]
                print(f"✓ keepalives_idle: {call_kwargs.get('keepalives_idle')}")
                print(f"✓ keepalives_interval: {call_kwargs.get('keepalives_interval')}")
                print(f"✓ keepalives_count: {call_kwargs.get('keepalives_count')}")

                assert call_kwargs["keepalives_idle"] == 10
                assert call_kwargs["keepalives_interval"] == 10
                assert call_kwargs["keepalives_count"] == 3

                print("\n✅ TCP Keep-Alive Settings: PASSED")
                return True


def test_pool_validator_thread():
    """Test 2: Verify pool validator thread is started."""
    print("\n" + "=" * 60)
    print("TEST 2: Pool Validator Thread")
    print("=" * 60)

    from unittest.mock import MagicMock, patch

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
        with patch("mcp_server.db.connection.pool.SimpleConnectionPool") as mock_pool:
            mock_pool_instance = MagicMock()
            mock_pool_instance.minconn = 1
            mock_pool_instance.maxconn = 10
            mock_pool_instance._pool = []
            mock_pool_instance._used = []
            mock_pool_instance.closed = False
            mock_pool.return_value = mock_pool_instance

            with patch("mcp_server.db.connection.get_connection"):
                with patch("mcp_server.db.connection.threading.Thread") as mock_thread:
                    from mcp_server.db.connection import _pool_validator_thread, initialize_pool_sync

                    mock_thread_instance = MagicMock()
                    mock_thread_instance.is_alive.return_value = False
                    mock_thread.return_value = mock_thread_instance

                    initialize_pool_sync()

                    # Check thread was created
                    assert _pool_validator_thread is not None
                    print(f"✓ Thread created: {_pool_validator_thread}")

                    # Check thread arguments
                    thread_args = mock_thread.call_args
                    print(f"✓ Thread target: {thread_args[1]['target'].__name__}")
                    print(f"✓ Thread daemon: {thread_args[1]['daemon']}")
                    print(f"✓ Thread name: {thread_args[1]['name']}")

                    # Check thread was started
                    mock_thread_instance.start.assert_called_once()
                    print("✓ Thread started")

                    print("\n✅ Pool Validator Thread: PASSED")
                    return True


def test_retry_logic():
    """Test 3: Verify SSL error is classified as transient."""
    print("\n" + "=" * 60)
    print("TEST 3: Retry Logic for SSL Errors")
    print("=" * 60)

    from mcp_server.db.connection import _is_transient_error

    test_cases = [
        ("SSL connection has been closed unexpectedly", True),
        ("connection reset by peer", True),
        ("connection timed out", True),
        ("server closed the connection unexpectedly", True),
        ("could not connect to server", True),
        ("the connection is closed", True),
        ("syntax error at or near SELECT", False),
        ("relation does not exist", False),
    ]

    all_passed = True
    for error_msg, expected in test_cases:
        result = _is_transient_error(Exception(error_msg))
        status = "✓" if result == expected else "✗"
        print(f"{status} '{error_msg[:50]}...' -> transient={result} (expected={expected})")
        if result != expected:
            all_passed = False

    if all_passed:
        print("\n✅ Retry Logic: PASSED")
    else:
        print("\n❌ Retry Logic: FAILED")

    return all_passed


def test_idle_connection_with_real_db():
    """Test 4: Real database test - connection survives >30s idle period."""
    print("\n" + "=" * 60)
    print("TEST 4: Idle Connection Test (Real Database)")
    print("=" * 60)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("⚠️  DATABASE_URL not set - skipping real database test")
        print("   To run this test, set DATABASE_URL environment variable")
        return None  # Skip, not fail

    from mcp_server.db.connection import (
        close_all_connections,
        get_connection_sync,
        initialize_pool_sync,
    )

    print(f"Database URL: {database_url[:30]}...")

    try:
        # Initialize pool with TCP keep-alive
        print("Initializing connection pool...")
        initialize_pool_sync()
        print("✓ Pool initialized with TCP keep-alive")

        # First connection
        print("\nFirst connection test...")
        with get_connection_sync() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as test, NOW() as timestamp")
            result = cursor.fetchone()
            print(f"✓ First query successful: {result}")

        # Wait for >30 seconds (idle period)
        print("\n⏳ Waiting 35 seconds to test idle connection handling...")
        print("   (This simulates the SSL timeout scenario)")
        for i in range(35, 0, -5):
            print(f"   {i} seconds remaining...")
            time.sleep(5)

        # Second connection after idle - should succeed without retry
        print("\nSecond connection test after 35s idle...")
        with get_connection_sync() as conn2:
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT 2 as test, NOW() as timestamp")
            result2 = cursor2.fetchone()
            print(f"✓ Second query successful: {result2}")

            # Check connection info
            cursor2.execute("SELECT pg_backend_pid() as pid")
            pid_info = cursor2.fetchone()
            print(f"✓ Connection PID: {pid_info['pid']}")

            print("\n✅ Idle Connection Test: PASSED")
            print("   Connection survived >30s idle period - SSL timeout fix working!")
            return True

    except Exception as e:
        print(f"\n❌ Idle Connection Test: FAILED")
        print(f"   Error: {e}")
        return False
    finally:
        print("\nCleaning up...")
        close_all_connections()
        print("✓ Connections closed")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SSL Timeout Fix - Manual Test Suite")
    print("=" * 60)
    print("\nThis test suite verifies the SSL timeout fix implementation:")
    print("1. TCP Keep-Alive Settings")
    print("2. Pool Validator Thread")
    print("3. Retry Logic for SSL Errors")
    print("4. Idle Connection Test (Real Database)")

    results = {}

    # Test 1: TCP Keep-Alive Settings
    try:
        results["tcp_keepalive"] = test_tcp_keepalive_settings()
    except Exception as e:
        print(f"\n❌ Test 1 failed with error: {e}")
        results["tcp_keepalive"] = False

    # Test 2: Pool Validator Thread
    try:
        results["pool_validator"] = test_pool_validator_thread()
    except Exception as e:
        print(f"\n❌ Test 2 failed with error: {e}")
        results["pool_validator"] = False

    # Test 3: Retry Logic
    try:
        results["retry_logic"] = test_retry_logic()
    except Exception as e:
        print(f"\n❌ Test 3 failed with error: {e}")
        results["retry_logic"] = False

    # Test 4: Idle Connection (optional, requires DATABASE_URL)
    try:
        results["idle_connection"] = test_idle_connection_with_real_db()
    except Exception as e:
        print(f"\n❌ Test 4 failed with error: {e}")
        results["idle_connection"] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    for test_name, result in results.items():
        if result is True:
            print(f"✅ {test_name}: PASSED")
        elif result is False:
            print(f"❌ {test_name}: FAILED")
        else:
            print(f"⏭️  {test_name}: SKIPPED")

    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
