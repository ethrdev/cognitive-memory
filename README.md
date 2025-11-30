# Cognitive Memory

> MCP-based persistent memory system for Claude Code with hybrid RAG, verbal reinforcement learning, and dual-judge evaluation.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 15+](https://img.shields.io/badge/postgresql-15+-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Cognitive Memory is a multi-layer memory architecture that provides Claude Code with persistent, context-rich retrieval capabilities. The system uses the Model Context Protocol (MCP) to integrate seamlessly with Claude Code while maintaining all conversation history, insights, and learned lessons.

### Key Features

- **Hybrid Search**: Combines semantic similarity (60%), keyword matching (20%), and graph relationships (20%) using RRF fusion
- **GraphRAG Integration**: Graph-based entity and relationship storage for structured knowledge discovery
- **Multi-Layer Memory**: L0 Raw Memory, Working Memory, L2 Insights, Episode Memory
- **Verbal Reinforcement Learning**: Learns from mistakes through Haiku API-powered reflexion
- **Dual-Judge Evaluation**: GPT-4o + Haiku for methodologically valid ground truth (Cohen's Kappa >0.70)
- **Model Drift Detection**: Daily Golden Test Set execution with automatic alerting
- **Cost Efficient**: 90-95% cost reduction vs. full API approach (~$5-10/month)

### Architecture

```
Claude Code (MAX Subscription)
├── Generation, Planning, CoT ($0/mo, internal)
├── MCP Protocol ↕
└── MCP Server (Python, local)
    ├── PostgreSQL + pgvector (Persistence)
    ├── L0 Raw Memory (complete transcripts)
    ├── L2 Insights (semantic compression)
    ├── Working Memory (8-10 items, LRU)
    └── Episode Memory (verbal reflexions)
        ↓
    External APIs ($5-10/mo)
    ├── OpenAI Embeddings ($0.06/mo)
    ├── GPT-4o Dual Judge ($1-1.5/mo)
    ├── Haiku Dual Judge ($1-1.5/mo)
    └── Haiku Evaluation/Reflexion ($1-2/mo)
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- OpenAI API key (for embeddings)
- Anthropic API key (for Haiku evaluation)

### Installation

```bash
# Clone the repository
git clone https://github.com/ethrdev/cognitive-memory.git
cd cognitive-memory

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.template .env.development
chmod 600 .env.development

# Edit .env.development with your API keys
```

### Database Setup (Neon Cloud)

This project uses [Neon Cloud](https://neon.tech) for serverless PostgreSQL with pgvector.

1. **Create a Neon account** at [console.neon.tech](https://console.neon.tech)

2. **Create a new project** and note your connection string:
   ```
   postgresql://neondb-user:PASSWORD@ep-xxx.REGION.aws.neon.tech/neondb?sslmode=require
   ```

3. **Enable pgvector extension** (in Neon SQL Editor):
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

4. **Run migrations**:
   ```bash
   # Set your Neon connection string
   export DATABASE_URL="postgresql://neondb-user:PASSWORD@ep-xxx.neon.tech/neondb?sslmode=require"

   # Run all migrations
   for f in mcp_server/db/migrations/*.sql; do psql "$DATABASE_URL" -f "$f"; done
   ```

5. **Update `.env.development`** with your Neon DATABASE_URL

<details>
<summary>Alternative: Local PostgreSQL Setup</summary>

```bash
# Install PostgreSQL and pgvector (Arch Linux)
sudo pacman -S postgresql
yay -S pgvector

# Initialize and start PostgreSQL
sudo -u postgres initdb -D /var/lib/postgres/data
sudo systemctl enable --now postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE cognitive_memory;
CREATE USER mcp_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE cognitive_memory TO mcp_user;
\c cognitive_memory
CREATE EXTENSION vector;
EOF

# Run migrations
PGPASSWORD=your_secure_password psql -U mcp_user -d cognitive_memory \
  -f mcp_server/db/migrations/001_initial_schema.sql
```
</details>

### Running the MCP Server

```bash
# Activate virtual environment and load environment variables
source venv/bin/activate
set -a && source .env.development && set +a

# Start MCP Server
python -m mcp_server
```

### Claude Code Integration

1. Copy the MCP configuration template:

```bash
cp .mcp.json.template .mcp.json
```

2. Edit `.mcp.json` and replace `${PROJECT_ROOT}` with your actual path:

```json
{
  "mcpServers": {
    "cognitive-memory": {
      "type": "stdio",
      "command": "/your/path/to/cognitive-memory/start_mcp_server.sh"
    }
  }
}
```

3. For **global availability** (all projects), add to `~/.config/claude-code/mcp-settings.json`:

```json
{
  "mcpServers": {
    "cognitive-memory": {
      "type": "stdio",
      "command": "/path/to/cognitive-memory/start_mcp_server.sh"
    }
  }
}
```

The start script automatically loads environment variables from `.env.development`.

## MCP Tools

| Tool | Description |
|------|-------------|
| **Memory Tools** ||
| `store_raw_dialogue` | Store complete dialogue transcripts (L0) |
| `compress_to_l2_insight` | Compress dialogues to semantic insights with embeddings |
| `hybrid_search` | Semantic + keyword + graph search with RRF fusion |
| `update_working_memory` | Manage session context with LRU eviction |
| `store_episode` | Store verbal reflexions from Haiku evaluation |
| **Evaluation Tools** ||
| `store_dual_judge_scores` | IRR validation with GPT-4o + Haiku |
| `get_golden_test_results` | Daily model drift detection |
| `ping` | Health check for connectivity testing |
| **Graph Tools** ||
| `graph_add_node` | Create or find graph nodes with optional vector linking |
| `graph_add_edge` | Create relationships between entities with auto-upsert |
| `graph_query_neighbors` | Find neighbor nodes with depth-limited traversal |
| `graph_find_path` | Find shortest path between entities using BFS |

## MCP Resources

| Resource | Description |
|----------|-------------|
| `memory://l2-insights?query={q}&top_k={k}` | Semantic search over L2 insights |
| `memory://working-memory` | Current session context |
| `memory://episode-memory?query={q}` | Similar past episodes with lessons |
| `memory://l0-raw?session_id={id}` | Raw dialogue transcripts |
| `memory://stale-memory` | Archived memory items |

## Graph Schema (GraphRAG Integration)

The system includes a graph database layer for storing entities and relationships, enabling GraphRAG (Graph Retrieval-Augmented Generation) capabilities. This extends the hybrid search to combine semantic, keyword, and graph-based retrieval.

### Schema Overview

```sql
-- Nodes table: Stores entities (people, concepts, documents, etc.)
CREATE TABLE nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label VARCHAR(255) NOT NULL,           -- Entity type ('Person', 'Concept', 'Document')
    name VARCHAR(255) NOT NULL,            -- Unique entity name
    properties JSONB DEFAULT '{}',        -- Flexible metadata
    vector_id INTEGER,                     -- Optional FK to l2_insights.id
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Edges table: Stores relationships between entities
CREATE TABLE edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL,               -- From node
    target_id UUID NOT NULL,               -- To node
    relation VARCHAR(255) NOT NULL,        -- Relationship type ('knows', 'contains', 'cites')
    weight FLOAT DEFAULT 1.0,             -- Relationship strength (0.0-1.0)
    properties JSONB DEFAULT '{}',        -- Flexible metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Key Features

- **UUID Primary Keys**: Distributed system compatibility and graph traversal performance
- **Idempotent Operations**: UNIQUE constraints prevent duplicate entities and relationships
- **Flexible Metadata**: JSONB properties with GIN indexes for complex queries
- **Optional Vector Integration**: Link entities to L2 insights via `vector_id` foreign key
- **CASCADE Deletes**: Automatic cleanup of relationships when entities are removed
- **Performance Optimized**: Comprehensive indexing for fast graph traversals

### Indexes and Performance

| Index | Purpose | Type |
|-------|---------|------|
| `idx_nodes_unique` | Prevent duplicate entities | B-tree |
| `idx_nodes_label` | Filter by entity type | B-tree |
| `idx_nodes_name` | Fast entity lookup | B-tree |
| `idx_edges_unique` | Prevent duplicate relationships | B-tree |
| `idx_edges_source_id` | Outbound traversals | B-tree |
| `idx_edges_target_id` | Inbound traversals | B-tree |
| `idx_edges_relation` | Filter by relationship type | B-tree |
| `idx_nodes_properties` | JSONB metadata queries | GIN |
| `idx_edges_properties` | JSONB metadata queries | GIN |

### Usage Examples

```sql
-- Create entities
INSERT INTO nodes (label, name, properties) VALUES
  ('Person', 'Alice', '{"role": "developer", "team": "AI"}'),
  ('Concept', 'Machine Learning', '{"domain": "AI", "complexity": "advanced"}'),
  ('Document', 'Research Paper', '{"type": "academic", "year": 2024}');

-- Create relationships
INSERT INTO edges (source_id, target_id, relation, weight) VALUES
  ((SELECT id FROM nodes WHERE name = 'Alice'),
   (SELECT id FROM nodes WHERE name = 'Machine Learning'),
   'knows', 0.9),
  ((SELECT id FROM nodes WHERE name = 'Machine Learning'),
   (SELECT id FROM nodes WHERE name = 'Research Paper'),
   'applies_to', 0.8);

-- Query Alice's connections
SELECT n.name, e.relation, e.weight
FROM edges e
JOIN nodes n ON e.target_id = n.id
JOIN nodes alice ON e.source_id = alice.id
WHERE alice.name = 'Alice';

-- JSONB property queries
SELECT name FROM nodes WHERE properties @> '{"role": "developer"}';
```

### Integration with Cognitive Memory

The graph schema extends the existing cognitive memory system:

- **Entity Extraction**: Automatically extract and store entities from conversations
- **Relationship Mapping**: Track relationships between concepts, people, and documents
- **Graph-Enhanced Search**: Combine with hybrid search for contextual retrieval
- **Knowledge Evolution**: Track how relationships change over time

### Migration

Apply the graph schema with migration `012_add_graph_tables.sql`:

```bash
psql "$DATABASE_URL" -f mcp_server/db/migrations/012_add_graph_tables.sql
```

## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](docs/guides/installation-guide.md) | Detailed setup instructions |
| [Operations Manual](docs/operations/operations-manual.md) | Daily operations and maintenance |
| [API Reference](docs/reference/api-reference.md) | Complete MCP tools and resources reference |
| [GraphRAG Guide](docs/guides/graphrag-guide.md) | Graph-based entity and relationship management |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |
| [Backup & Recovery](docs/operations/backup-recovery.md) | Disaster recovery procedures |

## Project Structure

```
cognitive-memory/
├── mcp_server/           # MCP Server implementation
│   ├── tools/            # 11 MCP tool implementations
│   ├── resources/        # 5 MCP resource implementations
│   ├── db/               # Database layer and migrations
│   └── external/         # OpenAI and Anthropic API clients
├── docs/                 # Documentation
├── tests/                # Test suite
├── scripts/              # Automation scripts
├── streamlit_apps/       # Ground truth labeling UI
├── systemd/              # Service configuration
```

## Performance Metrics

| Metric | Target | Achieved |
|--------|--------|----------|
| Precision@5 | ≥0.75 | 0.72 (Partial Success) |
| End-to-End Latency | <5s (p95) | ✓ |
| Cohen's Kappa (IRR) | >0.70 | ✓ |
| Monthly Budget | $5-10 | ✓ |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run pre-commit hooks
pre-commit install
pre-commit run --all-files

# Run tests
pytest tests/ -v

# Type checking
mypy mcp_server/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Model Context Protocol](https://modelcontextprotocol.io/)
- Uses [pgvector](https://github.com/pgvector/pgvector) for vector similarity search
- Inspired by cognitive science research on memory systems
