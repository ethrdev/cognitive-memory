# PostgreSQL + pgvector Setup Guide

**Story 1.2 - PostgreSQL + pgvector Setup**

This guide documents the complete setup process for PostgreSQL and pgvector on Arch Linux.

## Prerequisites

- Arch Linux system
- sudo access
- Internet connection
- Git

## Manual Setup Required

Some steps in Story 1.2 require manual execution with sudo privileges. This document provides the complete commands needed.

### Step 1: PostgreSQL Server Installation

```bash
# Install PostgreSQL server package
sudo pacman -S postgresql

# Initialize PostgreSQL database (only if not already initialized)
sudo -u postgres initdb -D /var/lib/postgres/data

# Start and enable PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Verify service is running
systemctl status postgresql
# Expected output: "active (running)"
```

### Step 2: pgvector Extension Installation

#### Option A: AUR Package (Recommended)

```bash
# Install pgvector using AUR helper
yay -S pgvector

# Verify installation (should show vector files)
ls /usr/lib/postgresql/
```

#### Option B: Build from Source

```bash
# Install build dependencies
sudo pacman -S base-devel git

# Clone and compile pgvector
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Cleanup
cd ..
rm -rf pgvector
```

### Step 3: Database and User Creation

```bash
# Open PostgreSQL shell as postgres user
sudo -u postgres psql

# Execute these commands in the PostgreSQL shell:
CREATE DATABASE cognitive_memory;
CREATE USER mcp_user WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE cognitive_memory TO mcp_user;

# Connect to the new database
\c cognitive_memory

# Enable pgvector extension
CREATE EXTENSION vector;

# Verify extension is installed
SELECT * FROM pg_extension WHERE extname='vector';

# Exit PostgreSQL shell
\q
```

### Step 4: Environment Configuration

```bash
# Update .env.development with your password
# Replace 'secure_password_here' with the password you set above
sed -i 's/your-secure-password-here/secure_password_here/' .env.development

# Verify file permissions (should be 600)
ls -la .env.development
```

### Step 5: Run Database Migration

```bash
# Run the schema migration
PGPASSWORD=secure_password_here psql -U mcp_user -d cognitive_memory -f mcp_server/db/migrations/001_initial_schema.sql

# Verify tables were created (should show 6 tables)
PGPASSWORD=secure_password_here psql -U mcp_user -d cognitive_memory -c "\dt"

# Verify indexes were created (should show 3 indexes - IVFFlat not built yet)
PGPASSWORD=secure_password_here psql -U mcp_user -d cognitive_memory -c "\di"
```

### Step 6: Test Python Connection

```bash
# Make sure you're in a Python virtual environment
source venv/bin/activate

# Run the comprehensive database test
python tests/test_database.py

# Expected output: "🎉 Alle PostgreSQL + pgvector Tests erfolgreich!"
```

## Verification Checklist

After completing the setup, verify:

- [ ] PostgreSQL service is running: `systemctl status postgresql`
- [ ] PostgreSQL version is 15+: `psql --version`
- [ ] pgvector extension is installed: `SELECT * FROM pg_extension WHERE extname='vector';`
- [ ] Database `cognitive_memory` exists: `\l` in psql
- [ ] User `mcp_user` has permissions: `\du` in psql
- [ ] All 6 tables exist: `\dt` shows l0_raw, l2_insights, working_memory, episode_memory, stale_memory, ground_truth
- [ ] 3 indexes exist: `\di` shows idx_l0_session, idx_l2_fts, idx_wm_lru
- [ ] Python connection test passes: `python tests/test_database.py`

## Important Notes

### IVFFlat Index Strategy

- **IVFFlat indexes are NOT built during Story 1.2**
- They require at least 100 vectors for training
- Index creation will happen in Story 1.5 after initial data is inserted
- The SQL commands are included as comments in the migration file

### Configuration Files

- **PostgreSQL config**: `/var/lib/postgres/data/postgresql.conf`
- **Authentication config**: `/var/lib/postgres/data/pg_hba.conf`
- **Environment file**: `.env.development` (project root, not in config/)

### Security

- PostgreSQL password is stored in `.env.development` (git-ignored)
- File permissions are set to 600 (owner read only)
- Consider using `md5` authentication in production instead of `trust`

## Troubleshooting

### Connection Refused
```bash
# Check if PostgreSQL is running
systemctl status postgresql

# Check if PostgreSQL is listening on localhost
sudo -u postgres psql -c "SELECT setting FROM pg_settings WHERE name = 'listen_addresses';"
```

### Authentication Failed
```bash
# Check pg_hba.conf for auth method
sudo cat /var/lib/postgres/data/pg_hba.conf

# Common fix: Change 'peer' to 'md5' for local connections
# Then restart PostgreSQL: sudo systemctl restart postgresql
```

### pgvector Not Found
```bash
# Check if extension files exist
ls /usr/lib/postgresql/vector*

# Check if extension is enabled in database
psql -U mcp_user -d cognitive_memory -c "\dx"
```

### Migration Fails
```bash
# Check SQL syntax manually
psql --set ON_ERROR_STOP=1 -U mcp_user -d cognitive_memory -f mcp_server/db/migrations/001_initial_schema.sql

# Check PostgreSQL version compatibility
psql --version  # Should be 15+
```

## Next Steps

After completing this setup:

1. Story 1.2 is complete and ready for review
2. Story 1.3 will create the MCP server framework and database connection module
3. Story 1.5 will build the IVFFlat indexes after initial data is available

## References

- [PostgreSQL Arch Wiki](https://wiki.archlinux.org/title/PostgreSQL)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Story 1.2 Context](../bmad-docs/stories/1-2-postgresql-pgvector-setup.context.xml)
- [Architecture Documentation](../bmad-docs/architecture.md)
