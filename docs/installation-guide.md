# Installation Guide

Complete setup instructions for the Cognitive Memory System from scratch.

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Linux (Arch, Ubuntu 20.04+) | Arch Linux |
| RAM | 2GB | 4GB+ |
| CPU | 2 Cores | 4 Cores |
| Storage | 10GB | 20GB |
| Python | 3.11+ | 3.12+ |
| PostgreSQL | 15+ | 16+ |

### Required API Keys

| Service | Purpose | Monthly Cost |
|---------|---------|--------------|
| OpenAI | Embeddings (text-embedding-3-small) | ~$0.06 |
| Anthropic | Haiku evaluation & reflexion | ~$2-3 |

Get your API keys:
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/

## Installation Steps

### 1. Clone Repository

```bash
git clone https://github.com/ethrdev/cognitive-memory.git
cd cognitive-memory
```

### 2. Install PostgreSQL and pgvector

#### Arch Linux

```bash
# Install PostgreSQL
sudo pacman -S postgresql

# Initialize database cluster
sudo -u postgres initdb -D /var/lib/postgres/data

# Start and enable service
sudo systemctl enable --now postgresql

# Install pgvector via AUR
yay -S pgvector
```

#### Ubuntu/Debian

```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Install pgvector
sudo apt install postgresql-15-pgvector
```

### 3. Create Database

```bash
sudo -u postgres psql << EOF
CREATE DATABASE cognitive_memory;
CREATE USER mcp_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE cognitive_memory TO mcp_user;
\c cognitive_memory
CREATE EXTENSION vector;
EOF
```

### 4. Setup Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configure Environment

```bash
# Copy template
cp .env.template .env.development
chmod 600 .env.development

# Edit with your credentials
nano .env.development
```

Required variables in `.env.development`:

```bash
# Database
DATABASE_URL=postgresql://mcp_user:your_password@localhost:5432/cognitive_memory

# API Keys
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### 6. Run Database Migrations

```bash
PGPASSWORD=your_password psql -U mcp_user -d cognitive_memory \
  -f mcp_server/db/migrations/001_initial_schema.sql

# Verify tables (should show 10 tables)
PGPASSWORD=your_password psql -U mcp_user -d cognitive_memory -c "\dt"
```

### 7. Test MCP Server

```bash
# Load environment
source venv/bin/activate
export $(cat .env.development | xargs)

# Start server
python -m mcp_server
```

### 8. Configure Claude Code

Create or update `~/.config/claude-code/mcp-settings.json`:

```json
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/cognitive-memory",
      "env": {
        "DATABASE_URL": "postgresql://mcp_user:password@localhost/cognitive_memory",
        "OPENAI_API_KEY": "sk-your-key",
        "ANTHROPIC_API_KEY": "sk-ant-your-key"
      }
    }
  }
}
```

Alternatively, use the provided template in the project root:

```bash
# Copy template and customize
cp .mcp.json.template .mcp.json

# Edit .mcp.json and replace ${PROJECT_ROOT} with your actual path
# Example: /home/user/cognitive-memory/start_mcp_server.sh
```

The template uses `start_mcp_server.sh` which automatically loads environment variables from `.env.development`.

## Verification Checklist

Run these commands to verify your installation:

```bash
# 1. PostgreSQL status
systemctl status postgresql

# 2. pgvector extension
psql -U mcp_user -d cognitive_memory -c "SELECT extversion FROM pg_extension WHERE extname='vector';"

# 3. Database tables
psql -U mcp_user -d cognitive_memory -c "\dt"

# 4. Python dependencies
python -c "import mcp_server; print('OK')"

# 5. MCP Server startup
timeout 5s python -m mcp_server || echo "Server test passed"
```

### Expected Tables

After migration, you should see these tables:

| Table | Purpose |
|-------|---------|
| `l0_raw` | Raw dialogue transcripts |
| `l2_insights` | Compressed semantic insights |
| `working_memory` | Current session context |
| `episode_memory` | Verbal reflexions |
| `stale_memory` | Archived items |
| `ground_truth` | Labeled queries for evaluation |
| `golden_test_set` | Model drift detection queries |
| `model_drift_log` | Daily precision metrics |
| `api_cost_log` | Cost tracking |
| `api_retry_log` | API reliability metrics |

## Claude Code Integration Test

1. Restart Claude Code to load MCP configuration
2. Run `/mcp` to see available tools
3. Test with: "Run the ping MCP tool"
4. Expected response: `pong`

## Next Steps

- Read the [Operations Manual](operations-manual.md) for daily operations
- Configure [backup strategy](backup-recovery.md) for data protection
- Set up [budget monitoring](budget-monitoring.md) for cost control

## Troubleshooting

See [Troubleshooting Guide](troubleshooting.md) for common issues.

### Quick Fixes

**PostgreSQL won't start:**
```bash
sudo systemctl status postgresql
journalctl -xeu postgresql
```

**MCP Server not visible in Claude Code:**
```bash
# Ensure .mcp.json exists (copy from template if needed)
cp .mcp.json.template .mcp.json
# Edit and replace ${PROJECT_ROOT} with actual path

# Check .mcp.json syntax
python -m json.tool .mcp.json

# Test server manually
python -m mcp_server
```

**Database connection failed:**
```bash
# Test connection
psql -U mcp_user -d cognitive_memory -h localhost

# Check port
ss -tlnp | grep 5432
```
