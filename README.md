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

**Note**: The Library API is included in the same package as the MCP server - no additional installation required for direct Python integration.

### Database Setup (Neon Cloud)

This project uses [Neon Cloud](https://neon.tech) for serverless PostgreSQL with pgvector.

**Multi-Project Architecture:** All ai-experiments projects (agentic-business, cognitive-memory, semantic-memory, i-o-system) share a single Neon DB instance with **namespace isolation via PROJECT_ID**. This provides cost efficiency and unified data management while maintaining strict project boundaries.

1. **Create a Neon account** at [console.neon.tech](https://console.neon.tech)

2. **Use the shared Neon database** (already provisioned):
   ```
   postgresql://neondb_owner:PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```

3. **Set your PROJECT_ID** for namespace isolation:
   - `cognitive` - for cognitive-memory project
   - `agentic-business` - for agentic-business project
   - `semantic` - for semantic-memory project
   - `io` - for i-o-system project

4. **Update `.env`** with your configuration:
   ```bash
   DATABASE_URL=postgresql://neondb_owner:PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require
   PROJECT_ID=cognitive
   ```

<details>
<summary>Setting up a new Neon database (if needed)</summary>

1. **Create a new project** and note your connection string:
   ```
   postgresql://neondb-user:PASSWORD@ep-xxx.REGION.aws.neon.tech/neondb?sslmode=require
   ```

2. **Enable pgvector extension** (in Neon SQL Editor):
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

3. **Run migrations**:
   ```bash
   # Set your Neon connection string
   export DATABASE_URL="postgresql://neondb-user:PASSWORD@ep-xxx.neon.tech/neondb?sslmode=require"
   export PROJECT_ID="cognitive"

   # Run all migrations
   for f in mcp_server/db/migrations/*.sql; do psql "$DATABASE_URL" -f "$f"; done
   ```

4. **Update `.env`** with your Neon DATABASE_URL and PROJECT_ID
</details>

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

The MCP server integrates with Claude Code via `.mcp.json` configuration.

**Option 1: Project-specific configuration** (agentic-business/.mcp.json):

```json
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "/home/ethr/01-projects/ai-experiments/cognitive-memory/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "/home/ethr/01-projects/ai-experiments/cognitive-memory",
      "env": {
        "DATABASE_URL": "postgresql://neondb_owner:PASSWORD@ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require",
        "PROJECT_ID": "cognitive",
        "PYTHONPATH": "/home/ethr/01-projects/ai-experiments/cognitive-memory"
      }
    }
  }
}
```

**Option 2: Global configuration** (`~/.config/claude-code/mcp-settings.json`):

```json
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "/path/to/cognitive-memory/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/cognitive-memory",
      "env": {
        "DATABASE_URL": "postgresql://...@ep-little-glitter-ag9uxp2a-pooler...neon.tech/neondb?sslmode=require",
        "PROJECT_ID": "cognitive",
        "PYTHONPATH": "/path/to/cognitive-memory"
      }
    }
  }
}
```

**Key Configuration:**
- `PROJECT_ID` - Namespace isolation for multi-project environments
- `PYTHONPATH` - Required for mcp_server module resolution
- `DATABASE_URL` - Neon DB connection with SSL enforced

## Library API

The Cognitive Memory Library provides direct Python API access to all memory operations without MCP protocol overhead. **No additional installation required** - the library is included in the same package as the MCP server.

### Quick Start

```python
from cognitive_memory import MemoryStore

# Environment-based initialization
with MemoryStore.from_env() as store:
    # Hybrid search
    results = store.search("künstliche intelligenz", top_k=5)

    # Store insight with metadata
    result = store.store_insight(
        "Kognitive Architekturen benötigen modulare Designprinzipien",
        source_ids=[1, 2, 3],
        metadata={"category": "architecture"}
    )

    # Working memory operations
    store.working.add("User prefers German explanations", importance=0.8)

    # Graph operations
    store.graph.add_node("Concept", "Machine Learning")
    store.graph.add_edge("AI", "Machine Learning", "INCLUDES", weight=0.9)
```

### Key Features

- **Direct Database Access**: ~25% faster than MCP tools (no protocol overhead)
- **Type Safety**: Full type hints with static analysis support
- **Connection Management**: Built-in connection pooling and context manager support
- **Exception Handling**: Structured exception hierarchy for robust error handling
- **Ecosystem Integration**: Designed for integration in i-o-system and other Python projects

### When to Use Library API vs MCP Tools

| Use Case | Recommended Approach |
|----------|----------------------|
| **Claude Code Integration** | MCP Tools |
| **Python Applications** | Library API |
| **Unit Testing** | Library API (better mocking) |
| **Performance-Critical** | Library API |
| **Cross-Language** | MCP Tools |
| **Rapid Prototyping** | MCP Tools |

### Installation

The Library API is included in the main package. Just import:

```python
from cognitive_memory import MemoryStore
```

For detailed API documentation, see: [Library API Reference](docs/api/library.md)

### Migration from MCP Tools

For guidance on migrating from MCP tools to the Library API, see: [Migration Guide](docs/migration-guide.md)

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
    type VARCHAR(100),                     -- Optional categorization
    properties JSONB DEFAULT '{}',        -- Flexible metadata
    embedding VECTOR(1536),                -- Optional embedding for semantic search
    project_id VARCHAR(100) DEFAULT 'cognitive',  -- Namespace isolation
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uniq_node_name UNIQUE (name)
);

-- Edges table: Stores relationships between entities
CREATE TABLE edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL,               -- From node
    target_id UUID NOT NULL,               -- To node
    relation VARCHAR(255) NOT NULL,        -- Relationship type ('knows', 'contains', 'cites')
    weight FLOAT DEFAULT 1.0,             -- Relationship strength (0.0-1.0)
    properties JSONB DEFAULT '{}',        -- Flexible metadata
    project_id VARCHAR(100) DEFAULT 'cognitive',  -- Namespace isolation
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT fk_edges_source_id FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE,
    CONSTRAINT fk_edges_target_id FOREIGN KEY (target_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- L2 Insights table: Compressed semantic insights
CREATE TABLE l2_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,                 -- Compressed insight text
    embedding VECTOR(1536),                -- Semantic embedding for search
    created_at TIMESTAMPTZ DEFAULT NOW(),
    source_ids INTEGER[],                  -- Related L0 memory IDs
    metadata JSONB DEFAULT '{}',          -- Additional metadata
    io_category VARCHAR(100),              -- I-O system category
    memory_strength FLOAT DEFAULT 1.0,     -- Forgetting curve strength
    is_identity BOOLEAN DEFAULT FALSE,    -- Whether this is identity info
    source_file VARCHAR(255),              -- Origin file
    is_deleted BOOLEAN DEFAULT FALSE,      -- Soft delete support
    deleted_at TIMESTAMPTZ,                -- Deletion timestamp
    deleted_by VARCHAR(100),               -- Deletion source
    deleted_reason TEXT,                   -- Deletion reason
    project_id VARCHAR(100) DEFAULT 'cognitive',  -- Namespace isolation
    CONSTRAINT uniq_insight_content UNIQUE (content)
);

-- Episode memory: Verbal reflexions from evaluations
CREATE TABLE episode_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,                   -- Original query
    response TEXT NOT NULL,                -- System response
    ground_truth TEXT,                     -- Expected answer
    haiku_reflection TEXT,                 -- Verbal reflexion
    haiku_rating NUMERIC(1,5),             -- Haiku quality score
    created_at TIMESTAMPTZ DEFAULT NOW(),
    project_id VARCHAR(100) DEFAULT 'cognitive'  -- Namespace isolation
);

-- Chunks table: Text chunks with embeddings
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    document_id INTEGER NOT NULL,
    level INTEGER NOT NULL,                -- Chunk hierarchy level
    content TEXT NOT NULL,                 -- Chunk content
    embedding VECTOR(1536),                -- Semantic embedding
    position INTEGER NOT NULL,             -- Position in document
    section_title TEXT,                    -- Section heading
    metadata JSONB DEFAULT '{}',          -- Additional metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    project_id VARCHAR(100) DEFAULT 'cognitive'  -- Namespace isolation
);
```

### Key Features

- **UUID Primary Keys**: Distributed system compatibility and graph traversal performance
- **Global Node Uniqueness**: Nodes are unique by `name` only - labels are mutable attributes (updated on conflict)
- **Namespace Isolation**: PROJECT_ID column enables multi-project environments sharing one database
- **Idempotent Operations**: UNIQUE constraints prevent duplicate entities and relationships
- **Flexible Metadata**: JSONB properties with GIN indexes for complex queries
- **Vector Embeddings**: pgvector integration for semantic search on nodes, insights, and chunks
- **CASCADE Deletes**: Automatic cleanup of relationships when entities are removed
- **Performance Optimized**: Comprehensive indexing for fast graph traversals and vector search

### Indexes and Performance

| Index | Purpose | Type |
|-------|---------|------|
| `idx_nodes_unique` | Prevent duplicate entities (by name only) | B-tree UNIQUE |
| `idx_nodes_label` | Filter by entity type | B-tree |
| `idx_nodes_project_id` | Namespace isolation | B-tree |
| `idx_edges_unique` | Prevent duplicate relationships | B-tree |
| `idx_edges_source_id` | Outbound traversals | B-tree |
| `idx_edges_target_id` | Inbound traversals | B-tree |
| `idx_edges_relation` | Filter by relationship type | B-tree |
| `idx_edges_project_id` | Namespace isolation | B-tree |
| `idx_nodes_properties` | JSONB metadata queries | GIN |
| `idx_edges_properties` | JSONB metadata queries | GIN |
| `idx_nodes_embedding` | Vector similarity search on nodes | ivfflat |
| `idx_l2_insights_embedding` | Vector similarity search on insights | ivfflat |
| `idx_chunks_embedding` | Vector similarity search on chunks | ivfflat |
| `idx_l2_insights_project_id` | Namespace isolation | B-tree |

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
