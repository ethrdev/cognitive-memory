# MCP Tools → Library API Migration Guide

Dieser Guide hilft bei der Migration von MCP Tools zur Library API und zeigt wann welche Approach am besten geeignet ist.

## Inhaltsverzeichnis

1. [Wann MCP vs. Library nutzen?](#wann-mcp-vs-library-nutzen)
2. [Performance-Vergleich](#performance-vergleich)
3. [MCP Tool → Library Method Mapping](#mcp-tool--library-method-mapping)
4. [Code-Migrationsbeispiele](#code-migrationsbeispiele)
5. [Parameter-Mapping](#parameter-mapping)
6. [Return Type Mapping](#return-type-mapping)
7. [Migration-Checklist](#migration-checklist)

## Wann MCP vs. Library nutzen?

### MCP Tools nutzen wenn:

- **Claude Code Integration**: Direkte Integration in Claude Code mit MCP Protocol
- **Externe MCP Clients**: Andere Tools die MCP Protocol unterstützen
- **Rapid Prototyping**: Schnelle Tests ohne Python Setup
- **Cross-Language Integration**: Aufruf aus verschiedenen Programmiersprachen
- **Server-based Architecture**: Centralisierte Server-Lösung

**Beispiel MCP Usage:**
```json
{
  "tool": "hybrid_search",
  "arguments": {
    "query_text": "künstliche intelligenz",
    "top_k": 5,
    "weights": {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}
  }
}
```

### Library API nutzen wenn:

- **Python-Projekte**: Direkte Integration in Python Anwendungen
- **Unit Tests**: Einfache Mocking und Testing Integration
- **Ecosystem-Integration**: Integration in i-o-system, tethr, etc.
- **Performance-Kritisch**: Direkte DB-Calls ohne MCP Overhead
- **Type Safety**: Statische Typ-Prüfung mit Type Hints
- **Connection Pooling**: Optimiertes Connection Management

**Beispiel Library Usage:**
```python
from cognitive_memory import MemoryStore

with MemoryStore() as store:
    results = store.search(
        "künstliche intelligenz",
        top_k=5,
        weights={"semantic": 0.6, "keyword": 0.2, "graph": 0.2}
    )
```

## Performance-Vergleich

### Library API

**Vorteile:**
- **~10-20ms faster**: Kein MCP Protocol Overhead
- **Direct DB Calls**: Bessere Connection Pooling
- **Batch Operations**: Möglich für multi-item operations
- **Memory Efficiency**: Kein JSON serialization/deserialization
- **Type Safety**: Compile-time error detection

**Benchmark (typische Operation):**
- Library API: ~45ms average
- MCP Tools: ~60ms average
- **Speedup: ~25% faster**

### MCP Tools

**Vorteile:**
- **Protocol Flexibility**: Language-agnostic
- **Claude Code Integration**: Nahtlose Integration
- **Server Management**: Centralized deployment
- **Monitoring**: Built-in MCP server monitoring

**Benchmark Overhead Breakdown:**
- JSON Serialization: ~5ms
- MCP Protocol: ~8ms
- Network Transport: ~2ms
- **Total MCP Overhead: ~15ms**

## MCP Tool → Library Method Mapping

### Core Search & Storage

| MCP Tool | Library Method | Return Type | Notes |
|----------|----------------|-------------|-------|
| `hybrid_search` | `store.search()` | `list[SearchResult]` | Direct mapping |
| `compress_to_l2_insight` | `store.store_insight()` | `InsightResult` | Same parameters |
| `store_raw_dialogue` | `store.working.add()` | `WorkingMemoryResult` | Working memory pattern |
| `update_working_memory` | `store.working.add()` | `WorkingMemoryResult` | Same operation |
| `get_working_memory` | `store.working.list()` | `list[WorkingMemoryItem]` | Direct mapping |
| `store_episode` | `store.episode.store()` | `EpisodeResult` | Direct mapping |
| `search_episodes` | `store.episode.search()` | `list[Episode]` | Direct mapping |

### Graph Operations

| MCP Tool | Library Method | Return Type | Notes |
|----------|----------------|-------------|-------|
| `graph_add_node` | `store.graph.add_node()` | `NodeResult` | Auto-UPSERT |
| `graph_add_edge` | `store.graph.add_edge()` | `EdgeResult` | Auto-UPSERT |
| `graph_query_neighbors` | `store.graph.query_neighbors()` | `list[GraphNode]` | Same interface |
| `graph_find_path` | `store.graph.find_path()` | `PathResult` | Same interface |

### Resources

| MCP Resource | Library Equivalent | Usage |
|--------------|-------------------|-------|
| `ping` | Direct imports | Check library availability |
| `list_commits` | Git operations | Use gitpython or subprocess |

## Code-Migrationsbeispiele

### 1. Hybrid Search Migration

**Vorher (MCP):**
```python
# MCP Client Code
import mcp

client = mcp.Client("localhost:8080")
response = client.call_tool("hybrid_search", {
    "query_text": "künstliche intelligenz",
    "top_k": 5,
    "weights": {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}
})

results = response.get("results", [])
for result in results:
    print(f"[{result['score']:.3f}] {result['content']}")
```

**Nachher (Library):**
```python
# Library Code
from cognitive_memory import MemoryStore

with MemoryStore() as store:
    results = store.search(
        "künstliche intelligenz",
        top_k=5,
        weights={"semantic": 0.6, "keyword": 0.2, "graph": 0.2}
    )

    for result in results:
        print(f"[{result.score:.3f}] {result.content}")
```

### 2. L2 Insight Storage Migration

**Vorher (MCP):**
```python
# MCP Client Code
response = client.call_tool("compress_to_l2_insight", {
    "content": "Kognitive Architekturen benötigen modulare Designprinzipien",
    "source_ids": [1, 2, 3],
    "metadata": {"category": "architecture", "priority": "high"}
})

result = response.get("result", {})
print(f"Stored insight with ID: {result.get('id')}")
```

**Nachher (Library):**
```python
# Library Code
from cognitive_memory import MemoryStore

with MemoryStore() as store:
    result = store.store_insight(
        "Kognitive Architekturen benötigen modulare Designprinzipien",
        source_ids=[1, 2, 3],
        metadata={"category": "architecture", "priority": "high"}
    )

    print(f"Stored insight with ID: {result.id}")
```

### 3. Working Memory Migration

**Vorher (MCP):**
```python
# MCP Client Code
# Add to working memory
response = client.call_tool("update_working_memory", {
    "content": "User prefers German explanations",
    "importance": 0.8
})

# Get working memory contents
response = client.call_tool("get_working_memory")
items = response.get("items", [])
```

**Nachher (Library):**
```python
# Library Code
from cognitive_memory import MemoryStore

with MemoryStore() as store:
    # Add to working memory
    result = store.working.add(
        "User prefers German explanations",
        importance=0.8
    )

    # Get working memory contents
    items = store.working.list()
```

### 4. Graph Operations Migration

**Vorher (MCP):**
```python
# MCP Client Code
# Add nodes
client.call_tool("graph_add_node", {
    "label": "Concept",
    "name": "Künstliche Intelligenz",
    "properties": {"domain": "cs"}
})

# Add edge
client.call_tool("graph_add_edge", {
    "source_name": "Künstliche Intelligenz",
    "target_name": "Maschinelles Lernen",
    "relation": "INCLUDES",
    "weight": 0.9
})

# Query neighbors
response = client.call_tool("graph_query_neighbors", {
    "node_name": "Künstliche Intelligenz"
})
neighbors = response.get("neighbors", [])
```

**Nachher (Library):**
```python
# Library Code
from cognitive_memory import MemoryStore

with MemoryStore() as store:
    # Add nodes
    store.graph.add_node(
        "Concept",
        "Künstliche Intelligenz",
        properties={"domain": "cs"}
    )

    # Add edge
    store.graph.add_edge(
        "Künstliche Intelligenz",
        "Maschinelles Lernen",
        "INCLUDES",
        weight=0.9
    )

    # Query neighbors
    neighbors = store.graph.query_neighbors("Künstliche Intelligenz")
```

### 5. Error Handling Migration

**Vorher (MCP):**
```python
# MCP Client Code
try:
    response = client.call_tool("hybrid_search", {
        "query_text": "",
        "top_k": 0
    })
    results = response.get("results", [])
except mcp.MCPError as e:
    print(f"MCP Error: {e}")
except json.JSONDecodeError as e:
    print(f"JSON Error: {e}")
```

**Nachher (Library):**
```python
# Library Code
from cognitive_memory import MemoryStore, SearchError, ValidationError

with MemoryStore() as store:
    try:
        results = store.search("", top_k=0)
    except ValidationError as e:
        print(f"Validation Error: {e}")
    except SearchError as e:
        print(f"Search Error: {e}")
```

## Parameter-Mapping

### Hybrid Search

| MCP Parameter | Library Parameter | Type | Notes |
|---------------|------------------|------|-------|
| `query_text` | `query` | `str` | Same value |
| `top_k` | `top_k` | `int` | Same value |
| `weights` | `weights` | `dict[str, float]` | Same structure |

### L2 Insight Storage

| MCP Parameter | Library Parameter | Type | Notes |
|---------------|------------------|------|-------|
| `content` | `content` | `str` | Same value |
| `source_ids` | `source_ids` | `list[int]` | Same value |
| `metadata` | `metadata` | `dict` | Same value |

### Working Memory

| MCP Parameter | Library Parameter | Type | Notes |
|---------------|------------------|------|-------|
| `content` | `content` | `str` | Same value |
| `importance` | `importance` | `float` | Same value (0.0-1.0) |

### Graph Operations

| MCP Parameter | Library Parameter | Type | Notes |
|---------------|------------------|------|-------|
| `label` | `label` | `str` | Same value |
| `name` | `name` | `str` | Same value |
| `source_name` | `source` | `str` | Renamed parameter |
| `target_name` | `target` | `str` | Renamed parameter |

## Return Type Mapping

### Search Results

**MCP Response:**
```json
{
  "results": [
    {
      "id": 1,
      "content": "...",
      "score": 0.85,
      "source": "l2_insight",
      "metadata": {...},
      "semantic_score": 0.90,
      "keyword_score": 0.75
    }
  ]
}
```

**Library Return:**
```python
[
    SearchResult(
        id=1,
        content="...",
        score=0.85,
        source="l2_insight",
        metadata={...},
        semantic_score=0.90,
        keyword_score=0.75
    )
]
```

### Storage Results

**MCP Response:**
```json
{
  "result": {
    "id": 42,
    "embedding_status": "success",
    "fidelity_score": 0.92,
    "created_at": "2025-11-30T10:00:00Z"
  }
}
```

**Library Return:**
```python
InsightResult(
    id=42,
    embedding_status="success",
    fidelity_score=0.92,
    created_at=datetime(2025, 11, 30, 10, 0, 0)
)
```

## Migration-Checklist

### Phase 1: Vorbereitung

- [ ] **Dependencies prüfen**: `pip install psycopg2-binary pgvector openai numpy scipy scikit-learn python-dotenv`
- [ ] **Environment Variables**: `DATABASE_URL`, `OPENAI_API_KEY` konfigurieren
- [ ] **Code Analysis**: Identifiziere alle MCP Tool Calls im Code
- [ ] **Test Coverage**: Stelle sicher dass Tests für MCP Calls existieren

### Phase 2: Library Integration

- [ ] **Import Statements**: `from cognitive_memory import MemoryStore`
- [ ] **Connection Setup**: `MemoryStore.from_env()` oder `MemoryStore(connection_string)`
- [ ] **Context Manager**: Nutze `with MemoryStore() as store:` Pattern
- [ ] **Error Handling**: Implementiere `try/except` mit spezifischen Exceptions

### Phase 3: Code Migration

- [ ] **Tool Calls ersetzen**: MCP `call_tool()` → Library Method Calls
- [ ] **Parameter Mapping**: Passe Parameter-Namen an (z.B. `source_name` → `source`)
- [ ] **Return Processing**: Direkter Zugriff auf Objekte statt JSON Parsing
- [ ] **Type Annotations**: Füge Type Hints für bessere IDE Unterstützung hinzu

### Phase 4: Testing & Validation

- [ ] **Unit Tests**: Schreibe Tests mit Mocking für externe Dependencies
- [ ] **Integration Tests**: Teste mit echter Datenbank Connection
- [ ] **Performance Testing**: Vergleiche Latency vor/nach Migration
- [ ] **Error Scenarios**: Teste Exception Handling mit Network Issues

### Phase 5: Deployment

- [ ] **Production Environment**: Konfiguriere Production Database Connection
- [ ] **Monitoring**: Implementiere Logging für Performance Monitoring
- [ ] **Rollback Plan**: Behalte MCP Code als Fallback
- [ ] **Documentation**: Update interne API-Dokumentation

### Phase 6: Optimization

- [ ] **Connection Pooling**: Nutze Connection Pooling für bessere Performance
- [ ] **Batch Operations**: Implementiere Batch Processing wo möglich
- [ ] **Caching**: Nutze Application-level Caching für häufige Queries
- [ ] **Async Support**: Nutze Async Patterns bei hoher Concurrency

## Migration Examples für verschiedene Use Cases

### Web Application Integration

**MCP Approach:**
```python
# Flask route with MCP
@app.route('/search')
def search():
    query = request.args.get('q')
    response = mcp_client.call_tool("hybrid_search", {
        "query_text": query,
        "top_k": 10
    })
    return jsonify(response)
```

**Library Approach:**
```python
# Flask route with Library
@app.route('/search')
def search():
    query = request.args.get('q')
    with MemoryStore() as store:
        results = store.search(query, top_k=10)
        return jsonify([{
            'id': r.id,
            'content': r.content,
            'score': r.score
        } for r in results])
```

### Data Science Pipeline

**MCP Approach:**
```python
# Data processing with MCP
import pandas as pd

def process_texts(texts):
    results = []
    for text in texts:
        response = mcp_client.call_tool("hybrid_search", {
            "query_text": text,
            "top_k": 3
        })
        results.append(response['results'])
    return pd.DataFrame(results)
```

**Library Approach:**
```python
# Data processing with Library
import pandas as pd
from cognitive_memory import MemoryStore

def process_texts(texts):
    with MemoryStore() as store:
        results = []
        for text in texts:
            search_results = store.search(text, top_k=3)
            results.append([{
                'content': r.content,
                'score': r.score,
                'source': r.source
            } for r in search_results])
        return pd.DataFrame(results)
```

## Troubleshooting

### Häufige Migration Issues

1. **Connection Errors**:
   - **Problem**: `ConnectionError: could not connect to database`
   - **Lösung**: Prüfe `DATABASE_URL` Environment Variable und Network Connectivity

2. **Import Errors**:
   - **Problem**: `ModuleNotFoundError: No module named 'cognitive_memory'`
   - **Lösung**: Stelle sicher dass Package im PYTHONPATH ist

3. **Type Errors**:
   - **Problem**: `TypeError: 'str' object is not callable`
   - **Lösung**: Prüfe Method Names und Parameter Mapping

4. **Performance Issues**:
   - **Problem**: Library ist langsamer als MCP
   - **Lösung**: Nutze Connection Pooling, überprüfe Database Connection

### Debugging Tips

1. **Enable Logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **Test Connection separat**:
```python
from cognitive_memory import MemoryStore, ConnectionError

try:
    with MemoryStore() as store:
        print("Connection successful")
except ConnectionError as e:
    print(f"Connection failed: {e}")
```

3. **Validate Parameters**:
```python
from cognitive_memory import ValidationError

try:
    store.working.add("content", importance=0.5)  # Valid range 0.0-1.0
except ValidationError as e:
    print(f"Invalid parameters: {e}")
```

## Next Steps

Nach erfolgreicher Migration:

1. **Performance Optimization**: Nutze Library-spezifische Features
2. **Advanced Patterns**: Implementiere Caching und Batch Processing
3. **Monitoring**: Integriere Application Monitoring
4. **Scaling**: Plane für horizontale Skalierbarkeit
5. **Documentation**: Halte API-Dokumentation aktuell

Für weitere Fragen und Support:
- [API Reference](/docs/api/library.md)
- [Usage Examples](/examples/library_usage.py)
- [Project README](/README.md)