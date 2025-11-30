# API Reference - MCP Tools & Resources

Complete API documentation for MCP Tools and Resources.

The Cognitive Memory System provides MCP (Model Context Protocol) integration with 11 Tools and 5 Resources for comprehensive memory management including GraphRAG capabilities.

## Table of Contents

1. [MCP Tools (11 available)](#mcp-tools)
   - [store_raw_dialogue](#store_raw_dialogue)
   - [compress_to_l2_insight](#compress_to_l2_insight)
   - [hybrid_search](#hybrid_search)
   - [update_working_memory](#update_working_memory)
   - [store_episode](#store_episode)
   - [store_dual_judge_scores](#store_dual_judge_scores)
   - [get_golden_test_results](#get_golden_test_results)
   - [ping](#ping)
   - [Graph Tools](#graph-tools)
     - [graph_add_node](#graph_add_node)
     - [graph_add_edge](#graph_add_edge)
     - [graph_query_neighbors](#graph_query_neighbors)
     - [graph_find_path](#graph_find_path)
2. [MCP Resources (5 available)](#mcp-resources)
   - [memory://l2-insights](#memoryl2-insights)
   - [memory://working-memory](#memoryworking-memory)
   - [memory://episode-memory](#memoryepisode-memory)
   - [memory://l0-raw](#memoryl0-raw)
   - [memory://stale-memory](#memorystale-memory)

---

## MCP Tools

### store_raw_dialogue

**Purpose:** Store raw dialogue data to L0 memory (unprocessed transcripts)

**Signature:**
```json
{
  "name": "store_raw_dialogue",
  "description": "Store raw dialogue data to L0 memory",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {
        "type": "string",
        "description": "Unique identifier for the dialogue session"
      },
      "speaker": {
        "type": "string",
        "description": "Speaker identifier (user, assistant, etc.)"
      },
      "content": {
        "type": "string",
        "description": "Dialogue content text"
      },
      "metadata": {
        "type": "object",
        "description": "Additional metadata for the dialogue (optional)"
      }
    },
    "required": ["session_id", "speaker", "content"]
  }
}
```

**Parameters:**
- `session_id` (string, required): Unique session identifier
- `speaker` (string, required): Speaker name or identifier
- `content` (string, required): Dialogue content
- `metadata` (object, optional): Additional metadata as JSON

**Returns:**
```json
{
  "id": 12345,
  "timestamp": "2025-01-15T10:30:00Z",
  "session_id": "session-001",
  "status": "success"
}
```

**Example Usage:**
```python
result = await mcp_server.call_tool("store_raw_dialogue", {
    "session_id": "conversation-2025-01-15",
    "speaker": "user",
    "content": "What is consciousness and how does it relate to memory?",
    "metadata": {"context": "philosophical discussion"}
})
```

---

### compress_to_l2_insight

**Purpose:** Compress dialogue data to L2 insight with OpenAI embedding and semantic fidelity check

**Signature:**
```json
{
  "name": "compress_to_l2_insight",
  "description": "Compress dialogue data to L2 insight with OpenAI embedding and semantic fidelity check",
  "inputSchema": {
    "type": "object",
    "properties": {
      "content": {
        "type": "string",
        "description": "Compressed insight content to store with embedding"
      },
      "source_ids": {
        "type": "array",
        "items": {"type": "integer"},
        "description": "Array of L0 raw memory IDs that were compressed into this insight"
      }
    },
    "required": ["content", "source_ids"]
  }
}
```

**Parameters:**
- `content` (string, required): Compressed insight content
- `source_ids` (array[int], required): Source L0 dialogue IDs

**Returns:**
```json
{
  "id": 67890,
  "embedding_status": "success",
  "fidelity_score": 0.73,
  "timestamp": "2025-01-15T10:35:00Z"
}
```

**Semantic Fidelity:**
- Automatically calculates information density (0.0-1.0)
- Warnings for low fidelity (<0.5 by default)
- Uses OpenAI text-embedding-3-small (1536 dimensions)

---

### hybrid_search

**Purpose:** Perform hybrid semantic + keyword search with RRF fusion

**Signature:**
```json
{
  "name": "hybrid_search",
  "description": "Perform hybrid semantic + keyword search with RRF fusion. Embedding is generated automatically from query_text if not provided.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query_text": {
        "type": "string",
        "minLength": 1,
        "description": "Query text for search (embedding generated automatically)"
      },
      "query_embedding": {
        "type": "array",
        "items": {"type": "number"},
        "minItems": 1536,
        "maxItems": 1536,
        "description": "Optional: 1536-dimensional query embedding (auto-generated from query_text if omitted)"
      },
      "top_k": {
        "type": "integer",
        "minimum": 1,
        "maximum": 100,
        "default": 5,
        "description": "Maximum number of results to return"
      },
      "weights": {
        "type": "object",
        "properties": {
          "semantic": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "default": 0.7,
            "description": "Weight for semantic search results"
          },
          "keyword": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "default": 0.3,
            "description": "Weight for keyword search results"
          }
        },
        "default": {"semantic": 0.7, "keyword": 0.3},
        "description": "Weights for fusing semantic and keyword results (must sum to 1.0)"
      }
    },
    "required": ["query_text"]
  }
}
```

**Parameters:**
- `query_text` (string, required): Search query
- `query_embedding` (array[float], optional): 1536-dimensional embedding
- `top_k` (integer, optional, default: 5): Number of results
- `weights` (object, optional, default: {"semantic": 0.7, "keyword": 0.3}): Fusion weights

**Returns:**
```json
{
  "results": [
    {
      "id": 123,
      "content": "Insight about consciousness and memory...",
      "source_ids": [1, 2, 3],
      "score": 0.847
    }
  ],
  "query_embedding_dimension": 1536,
  "semantic_results_count": 15,
  "keyword_results_count": 8,
  "final_results_count": 5,
  "weights": {"semantic": 0.7, "keyword": 0.3},
  "status": "success"
}
```

**RRF Fusion:**
- Reciprocal Rank Fusion with k=60 constant
- Automatic embedding generation from query_text
- Parallel semantic and keyword search execution

---

### update_working_memory

**Purpose:** Add item to Working Memory with atomic eviction handling (LRU + importance)

**Signature:**
```json
{
  "name": "update_working_memory",
  "description": "Add item to Working Memory with atomic eviction handling. Returns {added_id: int, evicted_id: Optional[int], archived_id: Optional[int]}",
  "inputSchema": {
    "type": "object",
    "properties": {
      "content": {
        "type": "string",
        "description": "Content to store in working memory"
      },
      "importance": {
        "type": "number",
        "minimum": 0.0,
        "maximum": 1.0,
        "default": 0.5,
        "description": "Importance score (0.0-1.0, default: 0.5)"
      }
    },
    "required": ["content"]
  }
}
```

**Parameters:**
- `content` (string, required): Working memory content
- `importance` (float, optional, default: 0.5): Importance score (0.0-1.0)

**Returns:**
```json
{
  "added_id": 456,
  "evicted_id": 789,
  "archived_id": 101112,
  "status": "success"
}
```

**Eviction Strategy:**
- Capacity limit: 10 items
- Critical items (importance > 0.8) protected from LRU eviction
- Archived items moved to stale_memory before deletion
- Atomic transaction handling to prevent race conditions

---

### store_episode

**Purpose:** Store episode memory with query, reward, and reflection for verbal reinforcement learning

**Signature:**
```json
{
  "name": "store_episode",
  "description": "Store episode memory with query, reward, and reflection for verbal reinforcement learning",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "minLength": 1,
        "description": "User query that triggered the episode"
      },
      "reward": {
        "type": "number",
        "minimum": -1.0,
        "maximum": 1.0,
        "description": "Reward score from evaluation (-1.0=poor, +1.0=excellent)"
      },
      "reflection": {
        "type": "string",
        "minLength": 1,
        "description": "Verbalized lesson learned (format: 'Problem: ... Lesson: ...')"
      }
    },
    "required": ["query", "reward", "reflection"]
  }
}
```

**Parameters:**
- `query` (string, required): Original user query
- `reward` (float, required): Reward score (-1.0 to 1.0)
- `reflection` (string, required): Lesson learned text

**Returns:**
```json
{
  "id": 345,
  "embedding_status": "success",
  "query": "How does working memory relate to consciousness?",
  "reward": 0.8,
  "created_at": "2025-01-15T10:40:00Z"
}
```

**Embedding Strategy:**
- Embedding generated from query (not reflection)
- Used for similarity-based episode retrieval
- Supports learning from past experiences

---

### store_dual_judge_scores

**Purpose:** Store dual judge evaluation scores using GPT-4o and Haiku for IRR validation

**Signature:**
```json
{
  "name": "store_dual_judge_scores",
  "description": "Store dual judge evaluation scores using GPT-4o and Haiku for IRR validation. Evaluates documents with two independent judges and calculates Cohen's Kappa for methodologically valid ground truth creation.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query_id": {
        "type": "integer",
        "minimum": 1,
        "description": "Ground truth query ID (must exist in ground_truth table)"
      },
      "query": {
        "type": "string",
        "minLength": 1,
        "description": "User query string for relevance evaluation"
      },
      "docs": {
        "type": "array",
        "minItems": 1,
        "maxItems": 50,
        "items": {
          "type": "object",
          "properties": {
            "id": {
              "type": "integer",
              "description": "Document identifier"
            },
            "content": {
              "type": "string",
              "minLength": 1,
              "description": "Document content to evaluate for relevance"
            }
          },
          "required": ["id", "content"]
        },
        "description": "Array of documents to evaluate with both judges"
      }
    },
    "required": ["query_id", "query", "docs"]
  }
}
```

**Parameters:**
- `query_id` (int, required): Ground truth query ID
- `query` (string, required): Query for evaluation
- `docs` (array[object], required): Documents to evaluate (1-50 items)

**Document Format:**
```json
{
  "id": 123,
  "content": "Document content text..."
}
```

**Returns:**
```json
{
  "query_id": 42,
  "judge1_score": 0.7,
  "judge2_score": 0.8,
  "kappa": 0.75,
  "agreement": "substantial",
  "evaluated_documents": 10,
  "status": "success"
}
```

**IRR (Inter-Rater Reliability):**
- Judge 1: GPT-4o for consistency
- Judge 2: Claude Haiku for determinism
- Cohen's Kappa calculation for agreement validation
- Methodologically valid ground truth creation

---

### get_golden_test_results

**Purpose:** Execute Golden Test Set for daily Precision@5 tracking and model drift detection

**Signature:**
```json
{
  "name": "get_golden_test_results",
  "description": "Execute Golden Test Set for daily Precision@5 tracking and model drift detection. Returns daily metrics and drift detection status.",
  "inputSchema": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

**Parameters:** None

**Returns:**
```json
{
  "date": "2025-01-15",
  "precision_at_5": 0.78,
  "baseline_precision": 0.82,
  "drift_detected": false,
  "queries_tested": 75,
  "details": "All metrics within normal range",
  "query_breakdown": {
    "short": {"count": 25, "precision_at_5": 0.72},
    "medium": {"count": 50, "precision_at_5": 0.80},
    "long": {"count": 0, "precision_at_5": null}
  }
}
```

**Drift Detection:**
- Daily execution recommended
- Drift alert: Precision@5 drop >5% from baseline
- Query type breakdown for detailed analysis
- Model performance trend tracking

---

### ping

**Purpose:** Simple ping tool for testing MCP connectivity

**Signature:**
```json
{
  "name": "ping",
  "description": "Simple ping tool for testing connectivity",
  "inputSchema": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

**Parameters:** None

**Returns:**
```json
{
  "response": "pong",
  "timestamp": "2025-01-15T10:45:00Z",
  "tool": "ping",
  "status": "ok"
}
```

**Usage:** Basic MCP server connectivity test

---

## Graph Tools

### graph_add_node

**Purpose:** Create or find a graph node with idempotent operation. Supports flexible metadata and optional vector linking to L2 insights.

**Signature:**
```json
{
  "name": "graph_add_node",
  "description": "Create or find a graph node with idempotent operation. Supports flexible metadata and optional vector linking to L2 insights.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "label": {
        "type": "string",
        "description": "Node type/category (e.g., 'Project', 'Technology', 'Client', 'Error', 'Solution')"
      },
      "name": {
        "type": "string",
        "description": "Unique name identifier for the node"
      },
      "properties": {
        "type": "object",
        "description": "Flexible metadata as key-value pairs"
      },
      "vector_id": {
        "type": "integer",
        "minimum": 1,
        "description": "Optional foreign key to l2_insights.id for vector embedding linkage"
      }
    },
    "required": ["label", "name"]
  }
}
```

**Parameters:**
- `label` (string, required): Node type or category
- `name` (string, required): Unique name identifier for the node
- `properties` (object, optional, default: {}): Flexible metadata as key-value pairs
- `vector_id` (int, optional): Foreign key to l2_insights.id for vector embedding linkage

**Returns:**
```json
{
  "node_id": 123,
  "label": "Project",
  "name": "Cognitive Memory System",
  "created": false,
  "vector_id": 456,
  "status": "success"
}
```

**Use Cases:**
- **Entity Creation:** Create structured entities (projects, technologies, clients)
- **Vector Linking:** Connect graph nodes to L2 insight embeddings for hybrid search
- **Metadata Storage:** Store flexible properties with each node

**Example Usage:**
```python
result = await mcp_server.call_tool("graph_add_node", {
    "label": "Project",
    "name": "Cognitive Memory System",
    "properties": {
        "status": "active",
        "priority": "high",
        "start_date": "2025-01-15"
    },
    "vector_id": 456
})
```

---

### graph_add_edge

**Purpose:** Create or update a relationship edge between graph nodes with auto-upsert of nodes. Supports standardized relations and optional weight scoring.

**Signature:**
```json
{
  "name": "graph_add_edge",
  "description": "Create or update a relationship edge between graph nodes with auto-upsert of nodes. Supports standardized relations and optional weight scoring.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "source_name": {
        "type": "string",
        "description": "Name of source node (will be created if not exists)"
      },
      "target_name": {
        "type": "string",
        "description": "Name of target node (will be created if not exists)"
      },
      "relation": {
        "type": "string",
        "description": "Relationship type (e.g., 'USES', 'SOLVES', 'CREATED_BY', 'RELATED_TO', 'DEPENDS_ON')"
      },
      "source_label": {
        "type": "string",
        "description": "Label for source node if auto-created (default: 'Entity')"
      },
      "target_label": {
        "type": "string",
        "description": "Label for target node if auto-created (default: 'Entity')"
      },
      "weight": {
        "type": "number",
        "minimum": 0.0,
        "maximum": 1.0,
        "description": "Edge weight for relevance scoring (0.0-1.0, default: 1.0)"
      },
      "properties": {
        "type": "object",
        "description": "Flexible metadata as key-value pairs"
      }
    },
    "required": ["source_name", "target_name", "relation"]
  }
}
```

**Parameters:**
- `source_name` (string, required): Name of source node
- `target_name` (string, required): Name of target node
- `relation` (string, required): Relationship type
- `source_label` (string, optional): Label for source node if auto-created (default: 'Entity')
- `target_label` (string, optional): Label for target node if auto-created (default: 'Entity')
- `weight` (float, optional, default: 1.0): Edge weight for relevance scoring (0.0-1.0)
- `properties` (object, optional): Flexible metadata as key-value pairs

**Standardized Relation Types:**
- `USES`: Project → Technology (usage dependencies)
- `SOLVES`: Solution → Problem (problem-solution mapping)
- `CREATED_BY`: Entity → Agent/User (attribution)
- `RELATED_TO`: General relationship between entities
- `DEPENDS_ON`: Dependency relationships

**Returns:**
```json
{
  "edge_id": 789,
  "source_node_id": 123,
  "target_node_id": 124,
  "relation": "USES",
  "weight": 0.8,
  "source_created": true,
  "target_created": false,
  "status": "success"
}
```

**Auto-Upsert Behavior:**
- Source or target nodes are automatically created if they don't exist
- Existing edges are updated with new weight/properties
- Idempotent operations prevent duplicate creation

**Example Usage:**
```python
result = await mcp_server.call_tool("graph_add_edge", {
    "source_name": "Cognitive Memory System",
    "target_name": "PostgreSQL",
    "relation": "USES",
    "source_label": "Project",
    "target_label": "Technology",
    "weight": 0.9,
    "properties": {
        "critical": true,
        "version": "15+"
    }
})
```

---

### graph_query_neighbors

**Purpose:** Find neighbor nodes of a given node with single-hop and multi-hop traversal. Supports filtering by relation type, depth-limited traversal, and cycle detection.

**Signature:**
```json
{
  "name": "graph_query_neighbors",
  "description": "Find neighbor nodes of a given node with single-hop and multi-hop traversal. Supports filtering by relation type, depth-limited traversal, and cycle detection.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "node_name": {
        "type": "string",
        "description": "Name of the starting node to find neighbors for"
      },
      "relation_type": {
        "type": "string",
        "description": "Optional filter for specific relation types (e.g., 'USES', 'SOLVES', 'RELATED_TO')"
      },
      "depth": {
        "type": "integer",
        "minimum": 1,
        "maximum": 5,
        "description": "Maximum traversal depth (1-5, default: 1)"
      }
    },
    "required": ["node_name"]
  }
}
```

**Parameters:**
- `node_name` (string, required): Name of the starting node
- `relation_type` (string, optional): Filter for specific relation types
- `depth` (int, optional, default: 1): Maximum traversal depth (1-5)

**Returns:**
```json
{
  "neighbors": [
    {
      "node_id": 124,
      "label": "Technology",
      "name": "PostgreSQL",
      "properties": {
        "type": "database",
        "version": "15+"
      },
      "relation": "USES",
      "distance": 1,
      "weight": 0.9
    },
    {
      "node_id": 125,
      "label": "Technology",
      "name": "Python",
      "properties": {
        "type": "language",
        "version": "3.11+"
      },
      "relation": "USES",
      "distance": 1,
      "weight": 0.8
    }
  ],
  "start_node": "Cognitive Memory System",
  "depth": 1,
  "total_neighbors": 2,
  "status": "success"
}
```

**Performance Characteristics:**
- **Depth 1:** <50ms typical, <100ms max acceptable
- **Depth 2-3:** <100ms typical, <200ms max acceptable
- **Depth 4-5:** Use sparingly, may require index optimization

**WITH RECURSIVE CTE:**
Uses PostgreSQL's recursive Common Table Expression for efficient graph traversal with built-in cycle detection.

**Example Usage:**
```python
# Direct neighbors only
result = await mcp_server.call_tool("graph_query_neighbors", {
    "node_name": "Cognitive Memory System",
    "depth": 1
})

# Multi-hop traversal with filter
result = await mcp_server.call_tool("graph_query_neighbors", {
    "node_name": "Cognitive Memory System",
    "relation_type": "USES",
    "depth": 3
})
```

---

### graph_find_path

**Purpose:** Find the shortest path between two nodes using BFS-based pathfinding with bidirectional traversal, cycle detection, and performance protection.

**Signature:**
```json
{
  "name": "graph_find_path",
  "description": "Find the shortest path between two nodes using BFS-based pathfinding with bidirectional traversal, cycle detection, and performance protection.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "start_node": {
        "type": "string",
        "description": "Name of the starting node for pathfinding"
      },
      "end_node": {
        "type": "string",
        "description": "Name of the target node to find path to"
      },
      "max_depth": {
        "type": "integer",
        "minimum": 1,
        "maximum": 10,
        "default": 5,
        "description": "Maximum traversal depth (1-10, default: 5)"
      }
    },
    "required": ["start_node", "end_node"]
  }
}
```

**Parameters:**
- `start_node` (string, required): Name of the starting node
- `end_node` (string, required): Name of the target node
- `max_depth` (int, optional, default: 5): Maximum traversal depth (1-10)

**Returns:**
```json
{
  "path_found": true,
  "path_length": 3,
  "path": [
    {
      "node_id": 123,
      "label": "Project",
      "name": "Cognitive Memory System",
      "relation_to_next": "USES"
    },
    {
      "node_id": 124,
      "label": "Technology",
      "name": "PostgreSQL",
      "relation_to_next": "SOLVES"
    },
    {
      "node_id": 125,
      "label": "Solution",
      "name": "Vector Storage",
      "relation_to_next": null
    }
  ],
  "start_node": "Cognitive Memory System",
  "end_node": "Vector Storage",
  "search_depth": 3,
  "status": "success"
}
```

**Algorithm Details:**
- **BFS-based:** Breadth-First Search guarantees shortest path
- **Bidirectional:** Searches from both ends simultaneously for efficiency
- **Cycle Detection:** Prevents infinite loops in cyclic graphs
- **Performance Protection:** 10-second timeout, max 10 paths returned

**Performance Targets:**
- **5 Hops:** <200ms typical, <400ms max acceptable
- **Complex paths:** Timeout protection prevents system overload

**Example Usage:**
```python
# Find connection between project and solution
result = await mcp_server.call_tool("graph_find_path", {
    "start_node": "High Volume Requirement",
    "end_node": "PostgreSQL",
    "max_depth": 5
})

# Check if two entities are related
if result["path_found"]:
    print(f"Path found with {result['path_length']} hops")
    for step in result["path"]:
        print(f"  {step['name']} -> {step.get('relation_to_next', 'END')}")
```

---

## MCP Resources

### memory://l2-insights

**Purpose:** Query L2 Insights database with search and filtering capabilities

**URI Format:** `memory://l2-insights?query={text}&top_k={number}&fidelity_min={float}`

**Query Parameters:**
- `query` (string, optional): Text search query
- `top_k` (integer, optional, default: 50): Maximum results to return
- `fidelity_min` (float, optional): Minimum fidelity score filter (0.0-1.0)
- `created_after` (string, optional): ISO date filter (YYYY-MM-DD)
- `created_before` (string, optional): ISO date filter (YYYY-MM-DD)

**Response Format:**
```json
{
  "resource": "memory://l2-insights",
  "uri": "memory://l2-insights?query=consciousness&top_k=10",
  "mimeType": "application/json",
  "contents": [
    {
      "id": 123,
      "content": "Insight about consciousness patterns...",
      "fidelity_score": 0.85,
      "created_at": "2025-01-15T10:30:00Z",
      "source_ids": [1, 2, 3],
      "metadata": {"fidelity_warning": false}
    }
  ]
}
```

**Example Calls:**
- `memory://l2-insights` - All insights (default: top 50)
- `memory://l2-insights?query=memory&top_k=10` - Search for "memory"
- `memory://l2-insights?fidelity_min=0.8` - High-quality insights only

---

### memory://working-memory

**Purpose:** Access current Working Memory state (10 items max, LRU + importance)

**URI Format:** `memory://working-memory`

**Query Parameters:** None (returns full state)

**Response Format:**
```json
{
  "resource": "memory://working-memory",
  "uri": "memory://working-memory",
  "mimeType": "application/json",
  "contents": [
    {
      "id": 1,
      "content": "Current context item...",
      "importance": 0.7,
      "last_accessed": "2025-01-15T10:45:00Z",
      "created_at": "2025-01-15T09:30:00Z"
    }
  ]
}
```

**Sorting:** Ordered by last_accessed (most recent first)

---

### memory://episode-memory

**Purpose:** Retrieve Episode Memory with similarity-based search for related past experiences

**URI Format:** `memory://episode-memory?query={text}&top_k={number}&min_similarity={float}&reward_min={float}`

**Query Parameters:**
- `query` (string, required): Search query for similarity matching
- `top_k` (integer, optional, default: 5): Maximum episodes to return
- `min_similarity` (float, optional, default: 0.5): Minimum similarity threshold (0.0-1.0)
- `reward_min` (float, optional): Minimum reward filter (-1.0-1.0)
- `days_back` (integer, optional): Limit to recent episodes (default: 30)

**Response Format:**
```json
{
  "resource": "memory://episode-memory",
  "uri": "memory://episode-memory?query=memory+consistency&top_k=3",
  "mimeType": "application/json",
  "contents": [
    {
      "id": 45,
      "query": "How does memory consistency work?",
      "reward": 0.8,
      "reflection": "Problem: User asked about memory consistency. Lesson: Memory consistency requires both temporal coherence and semantic alignment across retrieved memories.",
      "similarity": 0.82,
      "created_at": "2025-01-14T15:20:00Z"
    }
  ]
}
```

**Similarity Search:** Uses OpenAI embeddings for semantic similarity

---

### memory://l0-raw

**Purpose:** Access raw dialogue transcripts by session or date range

**URI Format:** `memory://l0-raw?session_id={string}&date_range={start,end}&speaker={string}&limit={number}`

**Query Parameters:**
- `session_id` (string, optional): Filter by specific session
- `date_range` (string, optional): Date range "YYYY-MM-DD,YYYY-MM-DD"
- `speaker` (string, optional): Filter by speaker name
- `limit` (integer, optional, default: 100): Maximum transcripts to return
- `order` (string, optional, default: "desc"): Sort order ("asc" or "desc")

**Response Format:**
```json
{
  "resource": "memory://l0-raw",
  "uri": "memory://l0-raw?session_id=conv-001&limit=50",
  "mimeType": "application/json",
  "contents": [
    {
      "id": 789,
      "session_id": "conv-001",
      "speaker": "user",
      "content": "What's the relationship between working memory and consciousness?",
      "timestamp": "2025-01-15T10:15:00Z",
      "metadata": {"context": "philosophical discussion"}
    }
  ]
}
```

**Date Range Format:** "2025-01-10,2025-01-15" (start,end inclusive)

---

### memory://stale-memory

**Purpose:** Access archived Working Memory items (evicted items preserved for audit)

**URI Format:** `memory://stale-memory?reason={string}&days_back={number}&importance_min={float}`

**Query Parameters:**
- `reason` (string, optional): Filter by archive reason ("LRU_EVICTION", "MANUAL_ARCHIVE")
- `days_back` (integer, optional, default: 30): Days to look back (default: 30)
- `importance_min` (float, optional): Minimum importance filter (0.0-1.0)
- `limit` (integer, optional, default: 50): Maximum items to return

**Response Format:**
```json
{
  "resource": "memory://stale-memory",
  "uri": "memory://stale-memory?reason=LRU_EVICTION&days_back=7",
  "mimeType": "application/json",
  "contents": [
    {
      "id": 234,
      "original_content": "Evicted working memory item...",
      "importance": 0.6,
      "reason": "LRU_EVICTION",
      "archived_at": "2025-01-15T08:30:00Z"
    }
  ]
}
```

**Archive Reasons:**
- `LRU_EVICTION`: Automatically evicted when capacity exceeded
- `MANUAL_ARCHIVE`: Manually archived by user/admin

---

## Error Handling

All tools and resources follow consistent error handling:

### Standard Error Response
```json
{
  "error": "Error type description",
  "details": "Detailed error message",
  "tool": "tool_name"
}
```

### Common Error Types
- **Parameter validation failed**: Invalid parameters or missing required fields
- **Database operation failed**: PostgreSQL connection or query errors
- **API key not configured**: Missing OpenAI or Anthropic API keys
- **Tool execution failed**: Unexpected runtime errors
- **Resource not found**: Invalid resource URI or query parameters

### Success Status
Successful operations return:
- `status: "success"` (tools)
- No explicit status field (resources - success indicated by 200 response)

---

## Rate Limits and Quotas

### API Rate Limits
- **OpenAI Embeddings:** 3 requests/second (handled with automatic retry)
- **Anthropic Haiku:** 1 request/second (handled with automatic retry)
- **OpenAI GPT-4o:** 1 request/second (handled with automatic retry)

### Database Limits
- **Connection Pool:** 20 concurrent connections maximum
- **Query Timeout:** 30 seconds default
- **Transaction Size:** No explicit limit (PostgreSQL manages)

### Resource Quotas
- **L2 Insights:** Unlimited (storage limited by disk space)
- **Working Memory:** 10 items (with automatic eviction)
- **Episode Memory:** Unlimited (with search optimization)
- **L0 Raw:** Unlimited (raw transcript storage)

