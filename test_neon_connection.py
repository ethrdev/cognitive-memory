#!/usr/bin/env python3
"""Test Neon database connection and setup pgvector extension."""

import os
import sys

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Neon connection string
DATABASE_URL = "postgresql://neondb_owner:YOUR_PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require"

try:
    print("🔗 Connecting to Neon database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    # Test 1: Check PostgreSQL version
    print("\n✅ Test 1: PostgreSQL Version")
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    print(f"   Version: {version[:80]}...")

    # Test 2: Enable pgvector extension
    print("\n✅ Test 2: Enable pgvector Extension")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    print("   pgvector extension enabled")

    # Test 3: Verify pgvector is available
    print("\n✅ Test 3: Verify pgvector Extension")
    cursor.execute("SELECT * FROM pg_extension WHERE extname='vector';")
    result = cursor.fetchone()
    if result:
        print(f"   pgvector extension active: {result}")
    else:
        print("   ❌ pgvector extension NOT found!")
        sys.exit(1)

    # Test 4: Check existing tables
    print("\n✅ Test 4: Check Existing Tables")
    cursor.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname='public'
        ORDER BY tablename;
    """)
    tables = cursor.fetchall()
    if tables:
        print(f"   Found {len(tables)} tables:")
        for table in tables:
            print(f"     - {table[0]}")
    else:
        print("   No tables found (schema migration needed)")

    cursor.close()
    conn.close()

    print("\n🎉 Neon connection successful! Database is ready for schema migration.")
    sys.exit(0)

except Exception as e:
    print(f"\n❌ Connection failed: {e}")
    sys.exit(1)
