# Cognitive Memory Library API Reference

Dieses Dokument beschreibt die vollständige Python API des Cognitive Memory Library Package.

## Inhaltsverzeichnis

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [MemoryStore Klasse](#memorystore-klasse)
4. [Sub-Module](#sub-module)
5. [Data Models](#data-models)
6. [Exception Hierarchy](#exception-hierarchy)
7. [Error Handling Patterns](#error-handling-patterns)
8. [Ecosystem Integration](#ecosystem-integration)

## Installation

Die Library API ist im selben Package wie der MCP Server enthalten. Keine zusätzliche Installation nötig.

```python
from cognitive_memory import MemoryStore
```

## Quick Start

```python
from cognitive_memory import MemoryStore

# Mit Environment Variable
with MemoryStore.from_env() as store:
    results = store.search("Autonomie und Bewusstsein", top_k=3)
    for r in results:
        print(f"[{r.score:.2f}] {r.content[:50]}...")

# Insight speichern
result = store.store_insight(
    content="Kognitive Architekturen erfordern modulare Designprinzipien",
    source_ids=[1, 2, 3],
    metadata={"category": "architecture"}
)
```

## MemoryStore Klasse

Die `MemoryStore` Klasse ist der Haupteinstiegspunkt für alle Memory-Operationen.

### Konstruktor

```python
def __init__(
    self,
    connection_string: str | None = None,
    auto_initialize: bool = True
) -> None
```

**Parameter:**
- `connection_string`: PostgreSQL Connection String (optional, Default: aus `DATABASE_URL` Environment Variable)
- `auto_initialize`: Ob Datenbanktabellen automatisch erstellt werden sollen (Default: `True`)

**Beispiel:**
```python
# Mit explizitem Connection String
store = MemoryStore("postgresql://user:pass@localhost/memory")

# Mit Environment Variable
store = MemoryStore.from_env()

# Als Context Manager
with MemoryStore() as store:
    # Connection wird automatisch verwaltet
    results = store.search("query")
```

### Context Manager Support

```python
def __enter__(self) -> MemoryStore
def __exit__(self, exc_type, exc_val, exc_tb) -> None
```

Der MemoryStore unterstützt Python Context Manager Protocol:

```python
with MemoryStore() as store:
    # Database Connection automatisch geöffnet
    results = store.search("query")
    store.store_insight("content", [1, 2])
# Connection automatisch geschlossen
```

### search()

```python
def search(
    self,
    query: str,
    top_k: int = 5,
    weights: dict[str, float] | None = None
) -> list[SearchResult]
```

Führt Hybrid Search über L2 Insights und L0 Raw Memory aus.

**Parameter:**
- `query`: Suchanfrage (wird automatisch embedded)
- `top_k`: Maximale Anzahl Ergebnisse (default: 5)
- `weights`: Gewichtung für Semantic/Keyword/Graph
  - Default: `{"semantic": 0.6, "keyword": 0.2, "graph": 0.2}`

**Returns:** Liste von `SearchResult` Objekten

**Raises:**
- `SearchError`: Bei Embedding- oder Datenbankfehlern
- `ConnectionError`: Wenn nicht verbunden
- `ValidationError`: Bei ungültigen Parametern

**Beispiel:**
```python
results = store.search(
    "Autonomie und Bewusstsein",
    top_k=3,
    weights={"semantic": 0.8, "keyword": 0.1, "graph": 0.1}
)

for result in results:
    print(f"[{result.score:.2f}] {result.content}")
    print(f"Source: {result.source}")
```

### store_insight()

```python
def store_insight(
    self,
    content: str,
    source_ids: list[int],
    metadata: dict | None = None
) -> InsightResult
```

Speichert komprimierte Erkenntnis mit Embedding und semantischer Fidelity-Validierung.

**Parameter:**
- `content`: Inhalt der Erkenntnis (wird für L2 Speicherung komprimiert)
- `source_ids`: IDs von L0 Raw Dialogue Einträgen, die komprimiert wurden
- `metadata`: Optionale Metadaten (Tags, Kategorie, etc.)

**Returns:** `InsightResult` mit ID und Embedding-Status

**Raises:**
- `StorageError`: Bei Speicherfehlern
- `EmbeddingError`: Bei Embedding-Generierungsfehlern
- `ValidationError`: Bei ungültigen Input-Daten

**Beispiel:**
```python
result = store.store_insight(
    content="Kognitive Architekturen erfordern modulare Designprinzipien",
    source_ids=[42, 43, 44],
    metadata={"category": "architecture", "priority": "high"}
)

print(f"Insight gespeichert mit ID: {result.id}")
print(f"Fidelity Score: {result.fidelity_score:.2f}")
```

## Sub-Module

### Working Memory (`store.working`)

Working Memory mit LRU Eviction und Importance Scoring.

#### add()

```python
def add(
    self,
    content: str,
    importance: float = 0.5
) -> WorkingMemoryResult
```

**Parameter:**
- `content`: Zu speichernder Inhalt
- `importance`: Wichtigkeit (0.0-1.0, Default: 0.5)

**Returns:** `WorkingMemoryResult` mit add/evict/archived IDs

#### list()

```python
def list(self) -> list[WorkingMemoryItem]
```

**Returns:** Liste aller Working Memory Items sortiert nach Wichtigkeit

#### clear()

```python
def clear(self) -> int
```

**Returns:** Anzahl der gelöschten Items

**Beispiel:**
```python
# Item hinzufügen
result = store.working.add(
    "User prefers verbose explanations",
    importance=0.8
)

# Alle Items auflisten
items = store.working.list()
for item in items:
    print(f"[{item.importance:.1f}] {item.content}")

# Memory leeren
cleared = store.working.clear()
print(f"{cleared} Items gelöscht")
```

### Episode Memory (`store.episode`)

Episode Memory für verbal reinforcement learning.

#### store()

```python
def store(
    self,
    query: str,
    reward: float,
    reflection: str
) -> EpisodeResult
```

**Parameter:**
- `query`: User Query die Episode ausgelöst hat
- `reward`: Reward Score (-1.0 bis +1.0)
- `reflection`: Verbalisierte Lektion

#### search()

```python
def search(
    self,
    query: str,
    min_similarity: float = 0.7,
    limit: int = 3
) -> list[Episode]
```

**Beispiel:**
```python
# Episode speichern
result = store.episode.store(
    query="Wie funktioniert KI-Lernen?",
    reward=0.8,
    reflection="Erkläre mit konkreten Beispielen statt abstrakter Theorie"
)

# Ähnliche Episoden finden
episodes = store.episode.search(
    "Wie lerne ich am besten?",
    min_similarity=0.6
)
```

### Graph Store (`store.graph`)

Graph Operations für GraphRAG Funktionalität.

#### add_node()

```python
def add_node(
    self,
    label: str,
    name: str,
    properties: dict | None = None,
    vector_id: int | None = None
) -> NodeResult
```

**Parameter:**
- `label`: Node Typ/Kategorie
- `name`: Eindeutiger Name
- `properties`: Metadaten
- `vector_id`: Optional Link zu L2 Insight

#### add_edge()

```python
def add_edge(
    self,
    source: str,
    target: str,
    relation: str,
    weight: float = 1.0,
    properties: dict | None = None
) -> EdgeResult
```

#### query_neighbors()

```python
def query_neighbors(
    self,
    node_name: str,
    relation_type: str | None = None,
    depth: int = 1
) -> list[GraphNode]
```

#### find_path()

```python
def find_path(
    self,
    start: str,
    end: str,
    max_depth: int = 5
) -> PathResult
```

**Beispiel:**
```python
# Graph Nodes hinzufügen
ai_node = store.graph.add_node("Concept", "Künstliche Intelligenz")
ml_node = store.graph.add_node("Concept", "Maschinelles Lernen")

# Edge hinzufügen
store.graph.add_edge(
    source="Künstliche Intelligenz",
    target="Maschinelles Lernen",
    relation="INCLUDES",
    weight=0.9
)

# Nachbarn finden
neighbors = store.graph.query_neighbors("Künstliche Intelligenz")

# Pfad finden
path = store.graph.find_path("Künstliche Intelligenz", "Neuronale Netze")
```

## Data Models

### SearchResult

```python
@dataclass
class SearchResult:
    id: int
    content: str
    score: float  # 0.0-1.0
    source: str  # 'l2_insight', 'working_memory', 'episode', 'graph'
    metadata: dict[str, Any]
    semantic_score: float | None = None
    keyword_score: float | None = None
```

### InsightResult

```python
@dataclass
class InsightResult:
    id: int
    embedding_status: str  # 'success', 'failed', 'retried'
    fidelity_score: float  # 0.0-1.0
    created_at: datetime
```

### WorkingMemoryResult

```python
@dataclass
class WorkingMemoryResult:
    added_id: int | None = None
    evicted_id: int | None = None
    archived_id: int | None = None
    current_count: int = 0
```

### WorkingMemoryItem

```python
@dataclass
class WorkingMemoryItem:
    id: int
    content: str
    importance: float  # 0.0-1.0
    last_accessed: datetime
    created_at: datetime
```

### EpisodeResult

```python
@dataclass
class EpisodeResult:
    id: int
    query: str
    reward: float  # -1.0 bis +1.0
    reflection: str
    created_at: datetime | None = None
```

### GraphNode

```python
@dataclass
class GraphNode:
    id: int
    name: str
    label: str
    properties: dict[str, Any]
    vector_id: int | None = None
```

### GraphEdge

```python
@dataclass
class GraphEdge:
    id: int
    source_id: int
    target_id: int
    relation: str
    weight: float  # 0.0-1.0
    properties: dict[str, Any]
```

### PathResult

```python
@dataclass
class PathResult:
    path: list[str]
    length: int
    found: bool
    nodes: list[GraphNode]
    edges: list[GraphEdge]
```

## Exception Hierarchy

Alle Exceptions erben von `CognitiveMemoryError`.

### CognitiveMemoryError

Base Exception für alle Library-Fehler.

```python
try:
    store.search("query")
except CognitiveMemoryError as e:
    logger.error(f"Memory operation failed: {e}")
```

### ConnectionError

Datenbank-Connection Fehler.

```python
try:
    store = MemoryStore("invalid://connection")
except ConnectionError as e:
    print(f"Database connection failed: {e}")
```

### SearchError

Search Operation Fehler.

```python
try:
    store.search("", top_k=0)  # Invalid parameters
except SearchError as e:
    print(f"Search failed: {e}")
```

### StorageError

Storage Operation Fehler.

```python
try:
    store.store_insight("", [])  # Invalid content
except StorageError as e:
    print(f"Storage failed: {e}")
```

### ValidationError

Input Validation Fehler.

```python
try:
    store.working.add("content", importance=2.0)  # Out of range
except ValidationError as e:
    print(f"Validation failed: {e}")
```

### EmbeddingError

Embedding Operation Fehler.

```python
try:
    store.search("very long query" * 1000)  # Too long
except EmbeddingError as e:
    print(f"Embedding failed: {e}")
```

## Error Handling Patterns

### Retry-Strategien

Bei transienten Fehlern (Rate Limits, Network Issues):

```python
import time
from cognitive_memory import ConnectionError, EmbeddingError

def store_with_retry(store, content, max_retries=3):
    for attempt in range(max_retries):
        try:
            return store.store_insight(content, [1, 2, 3])
        except EmbeddingError as e:
            if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
        except ConnectionError as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            raise

# Verwendung
try:
    result = store_with_retry(store, "Important insight")
except (EmbeddingError, ConnectionError) as e:
    print(f"Failed after retries: {e}")
```

### Graceful Degradation

```python
def robust_search(store, query, fallback_weights=None):
    try:
        # Primary: Full hybrid search
        return store.search(query, weights={"semantic": 0.6, "keyword": 0.2, "graph": 0.2})
    except EmbeddingError:
        # Fallback 1: Keyword-only search
        try:
            return store.search(query, weights={"semantic": 0.0, "keyword": 1.0, "graph": 0.0})
        except SearchError:
            # Fallback 2: Return empty results
            return []
    except SearchError as e:
        # Log error but don't crash
        print(f"Search failed: {e}")
        return []

# Verwendung
results = robust_search(store, "complex query")
if not results:
    print("Search failed, using fallback strategy")
```

### Connection Management

```python
from contextlib import contextmanager
from cognitive_memory import MemoryStore, ConnectionError

@contextmanager
def safe_store(connection_string=None):
    store = None
    try:
        store = MemoryStore(connection_string) if connection_string else MemoryStore.from_env()
        yield store
    except ConnectionError as e:
        print(f"Connection failed: {e}")
        raise
    finally:
        if store:
            store.disconnect()

# Verwendung
try:
    with safe_store() as store:
        results = store.search("query")
        # Connection wird automatisch geschlossen
except ConnectionError:
    print("Could not connect to database")
```

## Ecosystem Integration

### CognitiveMemoryAdapter Pattern

Für Integration in i-o-system oder andere Ecosystem-Projekte:

```python
from cognitive_memory import MemoryStore
from io_system.storage.base import StorageBackend  # Beispiel Interface

class CognitiveMemoryAdapter(StorageBackend):
    """Adapter für StorageBackend Protocol Compliance."""

    def __init__(self):
        self._store = MemoryStore.from_env()

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Suche nach relevanten Inhalten."""
        try:
            results = self._store.search(query, top_k=limit)
            return [self._to_io_format(r) for r in results]
        except CognitiveMemoryError as e:
            logger.error(f"Memory search failed: {e}")
            return []

    def store(self, content: str, metadata: dict = None) -> str:
            """Speichere neuen Inhalt."""
            try:
                result = self._store.store_insight(content, [], metadata or {})
                return str(result.id)
            except CognitiveMemoryError as e:
                logger.error(f"Memory storage failed: {e}")
                raise

    def _to_io_format(self, result) -> dict:
        """Konvertiere SearchResult zu i-o-system Format."""
        return {
            "id": str(result.id),
            "content": result.content,
            "score": result.score,
            "source": result.source,
            "metadata": result.metadata
        }
```

### Import-Pfade und Dependencies

```python
# Core Imports
from cognitive_memory import (
    MemoryStore,
    WorkingMemory,
    EpisodeMemory,
    GraphStore
)

# Result Types
from cognitive_memory.types import (
    SearchResult,
    InsightResult,
    WorkingMemoryResult,
    EpisodeResult,
    GraphNode,
    PathResult
)

# Exceptions
from cognitive_memory.exceptions import (
    CognitiveMemoryError,
    ConnectionError,
    SearchError,
    StorageError,
    ValidationError,
    EmbeddingError
)

# Connection Management
from cognitive_memory.connection import ConnectionManager
```

### Dependencies für Ecosystem Integration

Die Library API hat folgende Dependencies:

**Core Dependencies:**
- `psycopg2-binary` >= 2.9.0 (PostgreSQL driver)
- `pgvector` >= 0.2.0 (Vector extension support)
- `openai` >= 1.0.0 (Embedding generation)
- `numpy` >= 1.24.0 (Numerical operations)
- `scipy` >= 1.11.0 (RRF fusion)
- `scikit-learn` >= 1.3.0 (ML algorithms)
- `python-dotenv` >= 1.0.0 (Environment variables)

**Optional Dependencies:**
- `anthropic` >= 0.25.0 (Für dual judge features)

**Keine zusätzlichen Installationen nötig** - die Library API nutzt dieselben Dependencies wie der MCP Server.