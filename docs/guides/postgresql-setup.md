# PostgreSQL + pgvector Setup Guide

**Story 1.2 - PostgreSQL + pgvector Setup**

This guide documents the complete setup process for PostgreSQL with pgvector extension.

## Prerequisites

- Python 3.11+
- Internet connection
- API keys (OpenAI, Anthropic)

## Option A: Neon Cloud (Recommended)

[Neon](https://neon.tech) provides serverless PostgreSQL with pgvector pre-installed. This is the recommended setup for development and production.

### Step 1: Create Neon Account and Project

1. Go to [console.neon.tech](https://console.neon.tech)
2. Sign up or log in
3. Click **"New Project"**
4. Choose a region close to you (e.g., `eu-central-1`)
5. Note your connection string:
   ```
   postgresql://neondb-user:PASSWORD@ep-xxx-xxx-123456.REGION.aws.neon.tech/neondb?sslmode=require
   ```

### Step 2: Enable pgvector Extension

In the Neon SQL Editor (or via psql):

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Step 3: Environment Configuration

```bash
# Copy template
cp .env.template .env.development
chmod 600 .env.development

# Edit .env.development and set:
# DATABASE_URL=postgresql://neondb-user:PASSWORD@ep-xxx.neon.tech/neondb?sslmode=require
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

### Step 4: Run Database Migrations

The database schema is split across multiple migration files. Run all in order:

```bash
# Set your Neon connection string
export DATABASE_URL="postgresql://neondb-user:PASSWORD@ep-xxx.neon.tech/neondb?sslmode=require"

# Run all migrations
for f in mcp_server/db/migrations/*.sql; do
  echo "Running: $f"
  psql "$DATABASE_URL" -f "$f"
done

# Verify tables were created (should show 10 tables)
psql "$DATABASE_URL" -c "\dt"

# Verify indexes
psql "$DATABASE_URL" -c "\di"
```

### Step 5: Test Python Connection

```bash
# Activate virtual environment
source venv/bin/activate

# Load environment
set -a && source .env.development && set +a

# Run database test
python tests/test_database.py

# Expected output: "🎉 Alle PostgreSQL + pgvector Tests erfolgreich!"
```

### Neon-Specific Notes

- **SSL Required**: Always use `?sslmode=require` in connection strings
- **Connection Pooling**: Neon uses PgBouncer; use `-pooler` endpoint for high-concurrency apps
- **Branching**: Create database branches for testing without affecting production
- **Auto-suspend**: Free tier suspends after 5 min inactivity (first query takes ~1s to wake)

---

## Option B: Local PostgreSQL (Alternative)

For offline development or if you prefer local infrastructure.

### Step 1: PostgreSQL Server Installation (Arch Linux)

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
# Copy template
cp .env.template .env.development
chmod 600 .env.development

# Edit .env.development:
# DATABASE_URL=postgresql://mcp_user:secure_password_here@localhost:5432/cognitive_memory
```

### Step 5: Run Database Migrations

```bash
# Run all migrations in order
for f in mcp_server/db/migrations/*.sql; do
  echo "Running: $f"
  PGPASSWORD=secure_password_here psql -U mcp_user -d cognitive_memory -f "$f"
done

# Verify tables were created (should show 10 tables)
PGPASSWORD=secure_password_here psql -U mcp_user -d cognitive_memory -c "\dt"

# Verify indexes were created
PGPASSWORD=secure_password_here psql -U mcp_user -d cognitive_memory -c "\di"
```

### Step 6: Test Python Connection

```bash
# Make sure you're in a Python virtual environment
source venv/bin/activate

# Load environment
set -a && source .env.development && set +a

# Run the comprehensive database test
python tests/test_database.py

# Expected output: "🎉 Alle PostgreSQL + pgvector Tests erfolgreich!"
```

---

## Verification Checklist

After completing the setup, verify:

### For Neon Cloud:
- [ ] Neon project created and connection string noted
- [ ] pgvector extension enabled: `SELECT * FROM pg_extension WHERE extname='vector';`
- [ ] All 6 tables exist: `\dt` shows l0_raw, l2_insights, working_memory, episode_memory, stale_memory, ground_truth
- [ ] Indexes exist: `\di`
- [ ] Python connection test passes: `python tests/test_database.py`

### For Local PostgreSQL:
- [ ] PostgreSQL service is running: `systemctl status postgresql`
- [ ] PostgreSQL version is 15+: `psql --version`
- [ ] pgvector extension is installed: `SELECT * FROM pg_extension WHERE extname='vector';`
- [ ] Database `cognitive_memory` exists: `\l` in psql
- [ ] User `mcp_user` has permissions: `\du` in psql
- [ ] All 6 tables exist: `\dt`
- [ ] Python connection test passes

## Important Notes

### IVFFlat Index Strategy

- **IVFFlat indexes are NOT built during Story 1.2**
- They require at least 100 vectors for training
- Index creation will happen in Story 1.5 after initial data is inserted
- The SQL commands are included as comments in the migration file

### Configuration Files

**Neon Cloud:**
- All configuration via Neon Console
- Connection string in `.env.development`

**Local PostgreSQL:**
- PostgreSQL config: `/var/lib/postgres/data/postgresql.conf`
- Authentication config: `/var/lib/postgres/data/pg_hba.conf`
- Environment file: `.env.development` (project root)

### Security

- Database credentials stored in `.env.development` (git-ignored)
- File permissions set to 600 (owner read only)
- Neon: SSL enforced automatically
- Local: Consider using `md5` authentication in production

## Troubleshooting

### Connection Refused (Neon)

```bash
# Verify connection string format
echo $DATABASE_URL
# Should include: ?sslmode=require

# Test connection
psql "$DATABASE_URL" -c "SELECT 1;"

# Check if project is suspended (free tier)
# First query may take ~1s to wake up
```

### Connection Refused (Local)

```bash
# Check if PostgreSQL is running
systemctl status postgresql

# Check if PostgreSQL is listening on localhost
sudo -u postgres psql -c "SELECT setting FROM pg_settings WHERE name = 'listen_addresses';"
```

### Authentication Failed (Local)

```bash
# Check pg_hba.conf for auth method
sudo cat /var/lib/postgres/data/pg_hba.conf

# Common fix: Change 'peer' to 'md5' for local connections
# Then restart PostgreSQL: sudo systemctl restart postgresql
```

### pgvector Not Found

```bash
# Neon: Run in SQL Editor
CREATE EXTENSION IF NOT EXISTS vector;

# Local: Check if extension files exist
ls /usr/lib/postgresql/vector*

# Check if extension is enabled in database
psql -c "\dx"
```

### Migration Fails

```bash
# Check SQL syntax manually (run each migration with error stop)
for f in mcp_server/db/migrations/*.sql; do
  psql "$DATABASE_URL" --set ON_ERROR_STOP=1 -f "$f" || break
done

# Check PostgreSQL version compatibility (should be 15+)
psql "$DATABASE_URL" -c "SELECT version();"
```

## References

- [Neon Documentation](https://neon.tech/docs)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [PostgreSQL Arch Wiki](https://wiki.archlinux.org/title/PostgreSQL)
- [Architecture Documentation](../bmad-docs/architecture.md)
