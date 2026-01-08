# Story 7.7: IEF (Integrative Evaluation Function) + ICAI

Status: Done

## Story

Als I/O,
Ich will bei Entscheidungen automatisch alle relevanten Wissenskomponenten gewichtet kombinieren,
sodass meine Antworten sowohl aktuelle Erkenntnisse als auch konstitutive Überzeugungen berücksichtigen.

## Acceptance Criteria

1. **Given** ein Retrieval-Query für einen Node
   **When** `calculate_ief_score()` aufgerufen wird
   **Then** werden vier Komponenten kombiniert:
   - `relevance_score` (aus Story 7.3)
   - `semantic_similarity` (aus HybridSearch, falls L2-Insight verlinkt)
   - `recency_boost` (logarithmisches Decay für kürzliche Updates)
   - `constitutive_weight` (höhere Gewichtung für konstitutive Edges)

2. **Given** eine konstitutive Edge (edge_type = "constitutive")
   **When** `calculate_ief_score()` berechnet wird
   **Then** ist der `constitutive_weight` = 1.5 (50% Boost)
   **And** die finale Score-Formel: IEF = (relevance × 0.3) + (similarity × 0.25) + (recency × 0.2) + (constitutive × 0.25)

3. **Given** eine deskriptive Edge mit verlinktem L2-Insight (vector_id)
   **When** `calculate_ief_score()` aufgerufen wird mit query_embedding
   **Then** wird `semantic_similarity` via Cosine-Similarity zu L2-Insight berechnet
   **And** ein leerer vector_id führt zu similarity = 0.5 (neutral)

4. **Given** eine Edge mit `modified_at` vor 7 Tagen oder weniger
   **When** `recency_boost` berechnet wird mit Formel `exp(-days / 30)`
   **Then** ist der Boost ~0.79 (7 Tage: `exp(-7/30) ≈ 0.79`)
   **And** nach 30 Tagen ist der Boost ~0.37 (`exp(-1) ≈ 0.368`)
   **And** nach 1 Tag ist der Boost ~0.97 (sehr frisch)

5. **Given** `query_neighbors()` oder `find_path()` Aufruf
   **When** ICAI (Integrative Context Assembly Interface) aktiviert ist
   **Then** werden Ergebnisse nach `ief_score` statt nur `relevance_score` sortiert
   **And** ein `use_ief=True` Parameter steuert die Aktivierung (default: False für Rückwärtskompatibilität)

6. **Given** ein `dissonance_check` findet NUANCE-Konflikte
   **When** `calculate_ief_score()` für betroffene Edges aufgerufen wird
   **Then** wird ein `nuance_penalty` von 0.1 abgezogen
   **And** der Penalty ist nur temporär bis zur Resolution

## Task-zu-AC Mapping

| Task | AC Coverage | Beschreibung |
|------|-------------|--------------|
| Task 1 | AC #1, #2, #4 | calculate_ief_score() Core-Funktion |
| Task 2 | AC #3 | L2-Insight Semantic Similarity Integration |
| Task 3 | AC #5 | ICAI Parameter in query_neighbors/find_path |
| Task 4 | AC #6 | Nuance Penalty Integration |
| Task 5 | Test Coverage | Unit + Integration Tests |

## Tasks / Subtasks

- [x] Task 1: `calculate_ief_score()` Core-Funktion (AC: #1, #2, #4)
  - [x] Subtask 1.1: Funktion in `mcp_server/analysis/ief.py` (NEUE DATEI)
  - [x] Subtask 1.2: Import `calculate_relevance_score()` aus graph.py
  - [x] Subtask 1.3: `recency_boost` mit exponential decay (base 30 Tage)
  - [x] Subtask 1.4: `constitutive_weight` (1.5 für konstitutive, 1.0 sonst)
  - [x] Subtask 1.5: Gewichtete Formel implementieren (0.3, 0.25, 0.2, 0.25)
  - [x] Subtask 1.6: Return-Dict mit allen Komponenten für Transparenz

- [x] Task 2: L2-Insight Semantic Similarity (AC: #3)
  - [x] Subtask 2.1: `get_insight_embedding()` Helper aus l2_insights Tabelle
  - [x] Subtask 2.2: Cosine-Similarity Berechnung (numpy-frei, pure Python)
  - [x] Subtask 2.3: Fallback similarity = 0.5 wenn kein vector_id
  - [x] Subtask 2.4: Optional query_embedding Parameter für IEF

- [x] Task 3: ICAI Parameter Integration (AC: #5)
  - [x] Subtask 3.1: `use_ief` Parameter zu `query_neighbors()` in graph.py hinzufügen
  - [x] Subtask 3.2: `use_ief` Parameter zu `find_path()` in graph.py hinzufügen
  - [x] Subtask 3.3: Sortierung nach ief_score wenn use_ief=True
  - [x] Subtask 3.4: MCP Tools erweitern (graph_query_neighbors, graph_find_path)

- [x] Task 4: Nuance Penalty Integration (AC: #6) - **IMPLEMENTIERE** neue Funktion
  - [x] Subtask 4.1: **ERSTELLE** `get_pending_nuance_edge_ids()` in `mcp_server/analysis/dissonance.py`
    - Funktion existiert noch NICHT - muss neu implementiert werden
    - Nutzt `_nuance_reviews` In-Memory Storage (Zeile 85 in dissonance.py)
    - Filtert nach `status == "PENDING"`
  - [x] Subtask 4.2: Penalty-Lookup in calculate_ief_score()
  - [x] Subtask 4.3: Penalty nur wenn Edge in ungelösten NUANCE-Reviews

- [x] Task 5: Test Suite
  - [x] Subtask 5.1: `tests/test_ief.py` (NEUE DATEI)
  - [x] Subtask 5.2: Unit-Tests für IEF-Komponenten (exemplarisch unten)
  - [x] Subtask 5.3: **Integration-Test für Full Pipeline** (AC #5 + AC #6):
    - Edge mit NUANCE-Status erstellen
    - `query_neighbors(use_ief=True)` aufrufen
    - Verifizieren: ief_score hat nuance_penalty
    - Verifizieren: Sortierung nach ief_score
  - [x] Subtask 5.4: Integration-Test für `find_path(use_ief=True)`
  - [x] Subtask 5.5: Mock-Test für `_get_insight_embedding()` DB-Query

## Dev Notes

### Architecture Compliance

**Neue Dateien:**
- `mcp_server/analysis/ief.py` - IEF Core Logic
- `tests/test_ief.py` - Test Suite

**Modifikationen:**
- `mcp_server/db/graph.py` - `use_ief` Parameter zu query_neighbors/find_path
- `mcp_server/tools/graph_query_neighbors.py` - `use_ief` im inputSchema
- `mcp_server/tools/graph_find_path.py` - `use_ief` im inputSchema
- `mcp_server/analysis/dissonance.py` - `get_pending_nuance_edge_ids()` Helper

---

### IEF Komponenten-Übersicht

| Komponente | Range | Beschreibung | Quelle |
|------------|-------|--------------|--------|
| `relevance_score` | 0.0-1.0 | Ebbinghaus Decay × Memory Strength | Story 7.3 |
| `semantic_sim` | 0.0-1.0 | Cosine-Similarity zu L2-Insight | L2-Insights Tabelle |
| `recency_boost` | 0.0-1.0 | `exp(-days/30)` - belohnt kürzliche Updates | Berechnet |
| `constitutive_w` | 1.0-1.5 | 1.5 für konstitutive, 1.0 für deskriptive | Edge properties |
| `nuance_penalty` | 0.0-0.1 | Abzug für ungelöste NUANCE-Reviews | Dissonance Engine |

**Score-Range:** 0.0 bis ~1.25 (mit constitutive boost, vor penalty)

---

### `calculate_ief_score()` Implementation

```python
# mcp_server/analysis/ief.py (NEUE DATEI)

import math
from datetime import datetime, timezone
from typing import Any

from mcp_server.db.graph import calculate_relevance_score
from mcp_server.db.connection import get_connection

# IEF Gewichte (summe = 1.0)
IEF_WEIGHT_RELEVANCE = 0.30
IEF_WEIGHT_SIMILARITY = 0.25
IEF_WEIGHT_RECENCY = 0.20
IEF_WEIGHT_CONSTITUTIVE = 0.25

# Konstanten
RECENCY_DECAY_DAYS = 30  # Halbwertszeit für recency_boost
CONSTITUTIVE_BOOST = 1.5  # 50% Boost für konstitutive Edges
NUANCE_PENALTY = 0.1  # Temporärer Abzug für ungelöste NUANCE-Konflikte


def calculate_ief_score(
    edge_data: dict[str, Any],
    query_embedding: list[float] | None = None,
    pending_nuance_edge_ids: set[str] | None = None
) -> dict[str, Any]:
    """
    Berechnet den Integrativen Evaluations-Score für eine Edge.

    Kombiniert vier Komponenten:
    - relevance_score: Memory Strength × Ebbinghaus Decay
    - semantic_similarity: Cosine-Similarity zu Query (via L2-Insight)
    - recency_boost: Exponentieller Boost für kürzliche Updates
    - constitutive_weight: Erhöhte Gewichtung für konstitutive Edges

    Args:
        edge_data: Dict mit edge_properties, last_accessed, access_count,
                   modified_at, vector_id (optional)
        query_embedding: Optional 1536-dim Query-Embedding für Semantic Similarity
        pending_nuance_edge_ids: Optional Set von Edge-IDs mit ungelösten NUANCE-Reviews

    Returns:
        Dict mit ief_score und allen Komponenten für Transparenz:
        {
            "ief_score": float,
            "components": {
                "relevance_score": float,
                "semantic_similarity": float,
                "recency_boost": float,
                "constitutive_weight": float,
                "nuance_penalty": float
            },
            "weights": {
                "relevance": 0.30,
                "similarity": 0.25,
                "recency": 0.20,
                "constitutive": 0.25
            }
        }
    """
    edge_id = edge_data.get("edge_id") or edge_data.get("id")
    properties = edge_data.get("edge_properties") or edge_data.get("properties") or {}

    # Komponente 1: Relevance Score (aus Story 7.3)
    relevance_score = calculate_relevance_score(edge_data)

    # Komponente 2: Semantic Similarity
    vector_id = properties.get("vector_id") or edge_data.get("vector_id")
    semantic_similarity = _calculate_semantic_similarity(
        vector_id=vector_id,
        query_embedding=query_embedding
    )

    # Komponente 3: Recency Boost
    modified_at = edge_data.get("modified_at")
    recency_boost = _calculate_recency_boost(modified_at)

    # Komponente 4: Constitutive Weight
    is_constitutive = properties.get("edge_type") == "constitutive"
    constitutive_weight = CONSTITUTIVE_BOOST if is_constitutive else 1.0

    # Nuance Penalty (temporär für ungelöste Konflikte)
    nuance_penalty = 0.0
    if pending_nuance_edge_ids and edge_id and str(edge_id) in pending_nuance_edge_ids:
        nuance_penalty = NUANCE_PENALTY

    # IEF Score berechnen
    ief_score = (
        (relevance_score * IEF_WEIGHT_RELEVANCE) +
        (semantic_similarity * IEF_WEIGHT_SIMILARITY) +
        (recency_boost * IEF_WEIGHT_RECENCY) +
        (constitutive_weight * IEF_WEIGHT_CONSTITUTIVE)
    ) - nuance_penalty

    # Clamp auf [0.0, 1.5] (theoretisches Maximum mit constitutive boost)
    ief_score = max(0.0, min(1.5, ief_score))

    return {
        "ief_score": ief_score,
        "components": {
            "relevance_score": relevance_score,
            "semantic_similarity": semantic_similarity,
            "recency_boost": recency_boost,
            "constitutive_weight": constitutive_weight,
            "nuance_penalty": nuance_penalty
        },
        "weights": {
            "relevance": IEF_WEIGHT_RELEVANCE,
            "similarity": IEF_WEIGHT_SIMILARITY,
            "recency": IEF_WEIGHT_RECENCY,
            "constitutive": IEF_WEIGHT_CONSTITUTIVE
        }
    }


def _calculate_recency_boost(modified_at: datetime | str | None) -> float:
    """
    Berechnet den Recency Boost basierend auf modified_at Timestamp.

    Formel: recency = exp(-days_since_modified / RECENCY_DECAY_DAYS)

    Args:
        modified_at: Timestamp der letzten Modifikation

    Returns:
        Float zwischen 0.0 und 1.0
    """
    if not modified_at:
        return 0.5  # Neutral wenn kein Timestamp

    if isinstance(modified_at, str):
        modified_at = datetime.fromisoformat(modified_at.replace('Z', '+00:00'))

    # Timezone-aware handling (aus Story 7.3 Review-Fix)
    if modified_at.tzinfo is None:
        modified_at = modified_at.replace(tzinfo=timezone.utc)

    days_since = (datetime.now(timezone.utc) - modified_at).total_seconds() / 86400

    # Exponentieller Decay
    return max(0.0, min(1.0, math.exp(-days_since / RECENCY_DECAY_DAYS)))


def _calculate_semantic_similarity(
    vector_id: int | None,
    query_embedding: list[float] | None
) -> float:
    """
    Berechnet Cosine-Similarity zwischen Query-Embedding und L2-Insight Embedding.

    Args:
        vector_id: Foreign Key zu l2_insights.id
        query_embedding: 1536-dim Query-Embedding

    Returns:
        Float zwischen 0.0 und 1.0, oder 0.5 wenn nicht berechenbar
    """
    if not vector_id or not query_embedding:
        return 0.5  # Neutral wenn keine Daten

    insight_embedding = _get_insight_embedding(vector_id)
    if not insight_embedding:
        return 0.5

    return _cosine_similarity(query_embedding, insight_embedding)


def _get_insight_embedding(vector_id: int) -> list[float] | None:
    """
    Holt Embedding aus l2_insights Tabelle.

    Args:
        vector_id: Foreign Key zu l2_insights.id

    Returns:
        1536-dim Embedding oder None
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT embedding
            FROM l2_insights
            WHERE id = %s;
            """,
            (vector_id,)
        )
        result = cursor.fetchone()
        if result and result["embedding"]:
            # pgvector speichert als list
            return list(result["embedding"])
    return None


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Berechnet Cosine-Similarity zwischen zwei Vektoren (numpy-frei).

    Args:
        vec_a: Erster Vektor
        vec_b: Zweiter Vektor (muss gleiche Länge haben)

    Returns:
        Float zwischen -1.0 und 1.0 (normalisiert auf 0.0-1.0)
    """
    if len(vec_a) != len(vec_b):
        return 0.5  # Fallback bei Dimension-Mismatch

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.5  # Fallback bei Zero-Vector

    # Cosine similarity range: [-1, 1] → normalize to [0, 1]
    cos_sim = dot_product / (norm_a * norm_b)
    return (cos_sim + 1) / 2  # Map [-1,1] to [0,1]
```

---

### `get_pending_nuance_edge_ids()` Helper (dissonance.py)

```python
# mcp_server/analysis/dissonance.py - HINZUFÜGEN

def get_pending_nuance_edge_ids() -> set[str]:
    """
    Gibt alle Edge-IDs zurück die in ungelösten NUANCE-Reviews beteiligt sind.

    Wird von IEF verwendet um temporären Penalty anzuwenden.

    Returns:
        Set von Edge-ID Strings
    """
    edge_ids: set[str] = set()

    for review in _nuance_reviews:
        if review.get("status") == "PENDING":
            dissonance = review.get("dissonance", {})
            edge_a = dissonance.get("edge_a_id")
            edge_b = dissonance.get("edge_b_id")
            if edge_a:
                edge_ids.add(str(edge_a))
            if edge_b:
                edge_ids.add(str(edge_b))

    return edge_ids
```

---

### ICAI Integration in `query_neighbors()` (graph.py)

**Schritt 1:** Signatur erweitern (graph.py, nach include_superseded Parameter):

```python
def query_neighbors(
    node_id: str,
    relation_type: str | None = None,
    max_depth: int = 1,
    direction: str = "both",
    include_superseded: bool = False,
    use_ief: bool = False,  # NEU: ICAI Aktivierung
    query_embedding: list[float] | None = None  # NEU: Für IEF semantic similarity
) -> list[dict[str, Any]]:
```

**Schritt 2:** IEF Score Berechnung (nach relevance_score, vor Sortierung):

```python
# NEU: IEF Score Berechnung wenn ICAI aktiviert
if use_ief:
    from mcp_server.analysis.ief import calculate_ief_score
    from mcp_server.analysis.dissonance import get_pending_nuance_edge_ids

    pending_nuance_ids = get_pending_nuance_edge_ids()

    for neighbor in neighbors:
        ief_result = calculate_ief_score(
            edge_data=neighbor,
            query_embedding=query_embedding,
            pending_nuance_edge_ids=pending_nuance_ids
        )
        neighbor["ief_score"] = ief_result["ief_score"]
        neighbor["ief_components"] = ief_result["components"]

# Sortierung: IEF wenn aktiviert, sonst relevance_score
if use_ief:
    neighbors.sort(key=lambda n: n.get("ief_score", 0), reverse=True)
else:
    neighbors.sort(key=lambda n: n["relevance_score"], reverse=True)
```

---

### ICAI Integration in `find_path()` (graph.py)

**Schritt 1:** Signatur erweitern (graph.py:1046, nach max_depth Parameter):

```python
def find_path(
    start_node_name: str,
    end_node_name: str,
    max_depth: int = 5,
    use_ief: bool = False,  # NEU: ICAI Aktivierung
    query_embedding: list[float] | None = None  # NEU: Für IEF semantic similarity
) -> dict[str, Any]:
```

**Schritt 2:** IEF Score Berechnung (nach `path_relevance` Berechnung, ~Zeile 1230):

```python
# NEU: IEF Score für jeden Pfad wenn ICAI aktiviert
if use_ief:
    from mcp_server.analysis.ief import calculate_ief_score
    from mcp_server.analysis.dissonance import get_pending_nuance_edge_ids

    pending_nuance_ids = get_pending_nuance_edge_ids()

    for path in paths:
        path_ief_scores = []
        for edge in path["edges"]:
            edge_detail = get_edge_by_id(edge["edge_id"])
            if edge_detail:
                ief_result = calculate_ief_score(
                    edge_data=edge_detail,
                    query_embedding=query_embedding,
                    pending_nuance_edge_ids=pending_nuance_ids
                )
                edge["ief_score"] = ief_result["ief_score"]
                edge["ief_components"] = ief_result["components"]
                path_ief_scores.append(ief_result["ief_score"])

        # Pfad-IEF als Produkt (analog zu path_relevance)
        path["path_ief_score"] = math.prod(path_ief_scores) if path_ief_scores else 1.0

    # Sortierung nach path_ief_score wenn ICAI aktiviert
    paths.sort(key=lambda p: p.get("path_ief_score", 0), reverse=True)
```

---

### MCP Tool Erweiterung: `graph_find_path.py`

```python
# mcp_server/tools/graph_find_path.py - inputSchema erweitern

GRAPH_FIND_PATH_TOOL = Tool(
    name="graph_find_path",
    description="Find shortest path between nodes with optional IEF scoring.",
    inputSchema={
        "type": "object",
        "properties": {
            # ... existing properties (start_node, end_node, max_depth) ...
            "use_ief": {  # NEU
                "type": "boolean",
                "default": False,
                "description": "If true, calculates IEF scores for path edges and sorts paths by path_ief_score."
            },
            "query_embedding": {  # NEU
                "type": "array",
                "items": {"type": "number"},
                "minItems": 1536,
                "maxItems": 1536,
                "description": "Optional 1536-dimensional query embedding for semantic similarity in IEF."
            }
        },
        "required": ["start_node", "end_node"]
    }
)

# Handler erweitern:
async def handle_graph_find_path(arguments: dict) -> list[TextContent]:
    # ... existing code ...
    use_ief = arguments.get("use_ief", False)  # NEU
    query_embedding = arguments.get("query_embedding")  # NEU

    result = find_path(
        start_node_name=start_node,
        end_node_name=end_node,
        max_depth=max_depth,
        use_ief=use_ief,  # NEU
        query_embedding=query_embedding  # NEU
    )
    # ...
```

---

### MCP Tool Erweiterung: `graph_query_neighbors.py`

```python
# mcp_server/tools/graph_query_neighbors.py - inputSchema erweitern

GRAPH_QUERY_NEIGHBORS_TOOL = Tool(
    name="graph_query_neighbors",
    description="Find neighbor nodes with optional IEF scoring for integrative context assembly.",
    inputSchema={
        "type": "object",
        "properties": {
            # ... existing properties ...
            "use_ief": {  # NEU
                "type": "boolean",
                "default": False,
                "description": "If true, calculates IEF (Integrative Evaluation Function) scores and sorts by ief_score instead of relevance_score. Enables ICAI (Integrative Context Assembly Interface)."
            },
            "query_embedding": {  # NEU
                "type": "array",
                "items": {"type": "number"},
                "minItems": 1536,
                "maxItems": 1536,
                "description": "Optional 1536-dimensional query embedding for semantic similarity calculation in IEF."
            }
        },
        "required": ["node_name"]
    }
)

# Handler erweitern:
async def handle_graph_query_neighbors(arguments: dict) -> list[TextContent]:
    # ... existing code ...
    use_ief = arguments.get("use_ief", False)  # NEU
    query_embedding = arguments.get("query_embedding")  # NEU

    neighbors = query_neighbors(
        node_id=node_id,
        relation_type=relation_type,
        max_depth=depth,
        direction=direction,
        include_superseded=include_superseded,
        use_ief=use_ief,  # NEU
        query_embedding=query_embedding  # NEU
    )
    # ...
```

---

### Testing Strategy (Exemplarisch)

**Test-Datei:** `tests/test_ief.py` (NEU)

```python
# tests/test_ief.py - Exemplarische Kern-Tests (vollständige Suite analog implementieren)

import pytest
from datetime import datetime, timezone, timedelta
from mcp_server.analysis.ief import (
    calculate_ief_score, _calculate_recency_boost, _cosine_similarity,
    CONSTITUTIVE_BOOST, NUANCE_PENALTY
)

class TestIEFCore:
    """Kritische Tests für IEF Core-Funktion."""

    def test_ief_score_constitutive_boost(self):
        """AC #2: Konstitutive Edge bekommt 50% Boost."""
        edge_data = {
            "edge_id": "test-edge",
            "edge_properties": {"edge_type": "constitutive"},
            "modified_at": datetime.now(timezone.utc),
        }
        result = calculate_ief_score(edge_data)
        assert result["components"]["constitutive_weight"] == 1.5

    def test_ief_score_with_nuance_penalty(self):
        """AC #6: Nuance Penalty wird abgezogen."""
        edge_data = {"edge_id": "nuance-edge", "edge_properties": {}}
        result = calculate_ief_score(edge_data, pending_nuance_edge_ids={"nuance-edge"})
        assert result["components"]["nuance_penalty"] == 0.1

    def test_recency_boost_values(self):
        """AC #4: Recency Boost mit exp(-days/30)."""
        # 1 Tag: ~0.97, 7 Tage: ~0.79, 30 Tage: ~0.37
        assert _calculate_recency_boost(datetime.now(timezone.utc) - timedelta(days=1)) > 0.95
        assert 0.75 <= _calculate_recency_boost(datetime.now(timezone.utc) - timedelta(days=7)) <= 0.82
        assert 0.35 <= _calculate_recency_boost(datetime.now(timezone.utc) - timedelta(days=30)) <= 0.40

    def test_cosine_similarity_edge_cases(self):
        """Cosine Similarity Fallbacks."""
        assert _cosine_similarity([1, 2], [1, 2, 3]) == 0.5  # Dimension mismatch
        assert _cosine_similarity([0, 0], [1, 2]) == 0.5      # Zero vector

class TestICAIIntegration:
    """Integration-Tests für ICAI (AC #5 + #6)."""

    def test_query_neighbors_with_ief_sorting(self):
        """AC #5: query_neighbors sortiert nach ief_score wenn use_ief=True."""
        # Implementiere mit Mocks für graph.py Integration
        pass  # Analog zu test_graph_query_neighbors.py Muster

    def test_find_path_with_ief_scoring(self):
        """AC #5: find_path berechnet path_ief_score wenn use_ief=True."""
        pass  # Analog implementieren

    def test_full_pipeline_with_nuance_penalty(self):
        """AC #5 + #6 Integration: Edge mit NUANCE-Status in query_neighbors."""
        # 1. Edge mit NUANCE-Review Status erstellen
        # 2. query_neighbors(use_ief=True) aufrufen
        # 3. Verifizieren: ief_score enthält nuance_penalty
        pass
```

**Weitere Tests analog implementieren für:**
- `_calculate_semantic_similarity()` mit DB-Mock
- `_get_insight_embedding()` mit Connection-Mock
- Edge-Cases: kein vector_id, kein modified_at, etc.

---

## Previous Story Intelligence (Story 7.6, 7.5, 7.3)

**Direkt wiederverwendbar:**
- `calculate_relevance_score()` aus graph.py (Story 7.3) - Core-Komponente für IEF
- `_nuance_reviews` In-Memory Storage (Story 7.4/7.5) - Für Nuance Penalty Lookup
- `include_superseded` Pattern (Story 7.5) - Analoges Parameter-Pattern für use_ief
- **`properties_filter` aus Story 7.6** - Kann genutzt werden für effiziente konstitutive Edge Queries:
  ```python
  # Beispiel: Nur konstitutive Edges für IEF-Priorisierung
  query_neighbors(node_id, properties_filter={"edge_type": "constitutive"})
  ```
- Connection Pattern, Logging Pattern (alle Stories)

**Relevante Code-Stellen:**
- `graph.py:289-339` - `calculate_relevance_score()` Funktion
- `graph.py:650-870` - `query_neighbors()` für ICAI Integration
- `graph.py:872-975` - `find_path()` für ICAI Integration
- `dissonance.py:84` - `_nuance_reviews` Storage
- `dissonance.py:452-454` - `get_pending_reviews()` als Vorlage

**Review-Fixes aus vorherigen Stories (beachten):**
- Timezone-aware datetime handling (`datetime.now(timezone.utc)`)
- Type Safety für conn Parameter
- Silent-fail für nicht-kritische Ops

---

## Technical Dependencies

**Upstream (vorausgesetzt):**
- ✅ Story 7.3: Decay mit Memory Strength (`calculate_relevance_score()`)
- ✅ Story 7.4/7.5: Dissonance Engine (`_nuance_reviews`, `NuanceReviewProposal`)
- ✅ Epic 2: L2-Insights mit Embeddings (`l2_insights` Tabelle mit `embedding` Column)
- ✅ Epic 4: GraphRAG (`query_neighbors`, `find_path`)

**Downstream (blockiert von dieser Story):**
- Story 7.8: Semantic Memory Fields (nutzt IEF für Memory-Organization)
- Story 7.9: SMF Integration (nutzt ICAI für holistische Antworten)

---

## Latest Tech Information

**Integrative Evaluation (2024 Research):**
- Multi-Signal Fusion ist Standard für moderne RAG-Systeme
- Gewichtete Kombination outperformt Single-Signal Ranking
- Recency Boost verbessert Faktizität bei sich ändernden Domains

**Cosine Similarity (Best Practices):**
- Pure Python Implementation für kleine Batches ausreichend
- Numpy nur bei >1000 Vektoren/Sekunde notwendig
- Normalisierung [-1,1] → [0,1] für konsistente Scores

**ICAI Pattern:**
- "Integrative Context Assembly" ist ein etabliertes Pattern
- Separate Aktivierung (use_ief=False default) für Rückwärtskompatibilität
- Transparenz durch Komponenten-Rückgabe ermöglicht Debugging

---

## Estimated Effort

**Epic-Definition:** 2 Tage

**Breakdown:**
- Task 1: 0.5 Tage (IEF Core-Funktion)
- Task 2: 0.5 Tage (L2-Insight Semantic Similarity)
- Task 3: 0.5 Tage (ICAI Integration in graph.py + MCP Tools)
- Task 4: 0.25 Tage (Nuance Penalty Integration)
- Task 5: 0.25 Tage (Test Suite)

---

## References

- [Source: bmad-docs/epics/epic-7-v3-constitutive-knowledge-graph.md#Story 7.7]
- [Source: mcp_server/db/graph.py - calculate_relevance_score(), query_neighbors()]
- [Source: mcp_server/analysis/dissonance.py - _nuance_reviews, NuanceReviewProposal]
- [Source: bmad-docs/stories/7-3-tgn-minimal-decay-mit-memory-strength.md - Memory Strength Formel]
- [Source: bmad-docs/stories/7-5-dissonance-engine-resolution.md - include_superseded Pattern]

---

### Completion Notes List

**Date:** 2025-12-17

**Story 7.7 Implementation Summary:**
✅ Fully implemented IEF (Integrative Evaluation Function) with all 6 Acceptance Criteria
✅ Created `mcp_server/analysis/ief.py` with weighted scoring system
✅ Added `get_pending_nuance_edge_ids()` to dissonance.py for nuance penalty
✅ Integrated IEF into `query_neighbors()` and `find_path()` with `use_ief` parameter
✅ Updated MCP tools with IEF parameters and validation
✅ Created comprehensive test suite with 21 passing tests

**Key Components Implemented:**
- Core IEF scoring with weights: relevance (0.3), similarity (0.25), recency (0.2), constitutive (0.25)
- Constitutive boost (1.5x) for constitutive edges
- Recency boost with exp(-days/30) formula
- Semantic similarity via L2-insight embeddings
- Nuance penalty (0.1) for unresolved conflicts
- ICAI (Integrative Context Assembly Interface) activation via use_ief=True

**Files Modified/Created:**
- NEW: `mcp_server/analysis/ief.py` - IEF core implementation
- NEW: `tests/test_ief.py` - Comprehensive test suite
- MODIFIED: `mcp_server/db/graph.py` - Added IEF parameters and scoring
- MODIFIED: `mcp_server/analysis/dissonance.py` - Added get_pending_nuance_edge_ids()
- MODIFIED: `mcp_server/tools/graph_query_neighbors.py` - Added IEF parameters
- MODIFIED: `mcp_server/tools/graph_find_path.py` - Added IEF parameters
- MODIFIED: `mcp_server/tools/__init__.py` - Updated tool schemas

### File List

**Neue Dateien:**
- `mcp_server/analysis/ief.py` - IEF Core Logic
- `tests/test_ief.py` - Comprehensive Test Suite

**Modifizierte Dateien:**
- `mcp_server/db/graph.py` - use_ief + query_embedding Parameter für query_neighbors() und find_path()
- `mcp_server/tools/graph_query_neighbors.py` - MCP Tool Erweiterung mit use_ief, query_embedding
- `mcp_server/tools/graph_find_path.py` - MCP Tool Erweiterung mit use_ief, query_embedding
- `mcp_server/analysis/dissonance.py` - **NEUE** Funktion `get_pending_nuance_edge_ids()`

---

## Validation Report (2025-12-17)

**Reviewer:** Claude Opus 4.5 (Scrum Master Validation Mode)
**Status:** ✅ Story verbessert, ready-for-dev

### Issues Fixed

| # | Severity | Issue | Fix Applied |
|---|----------|-------|-------------|
| 1 | 🔴 KRITISCH | `get_pending_nuance_edge_ids()` Funktion existiert nicht | Task 4 expliziter gemacht: "ERSTELLE" statt nur Code zeigen |
| 2 | 🔴 KRITISCH | AC #4 Recency Werte falsch (> 0.9 für 7 Tage unmöglich mit exp(-7/30)) | AC korrigiert auf realistische Werte (~0.79 für 7 Tage) |
| 3 | 🔴 KRITISCH | `find_path()` use_ief Implementation fehlte | Vollständige Implementation Section hinzugefügt |
| 4 | 🟡 ENHANCEMENT | Integration Test fehlte | Task 5 erweitert um Pipeline-Tests |
| 5 | 🟡 ENHANCEMENT | MCP Tool graph_find_path Details fehlten | Schema/Handler Section hinzugefügt |
| 6 | 🟡 ENHANCEMENT | L2-Insight DB-Query Test fehlte | Task 5.5 hinzugefügt |
| 7 | 🟡 ENHANCEMENT | Story 7.6 properties_filter nicht erwähnt | Nutzungshinweis in Previous Story Intelligence |
| 8 | 🟢 LLM-OPT | Dev Notes Code zu lang (~400 Zeilen) | Tests auf exemplarische reduziert |
| 9 | 🟢 LLM-OPT | Doppelte Formel-Dokumentation (3x gleiche Info) | Konsolidiert zu Komponenten-Tabelle |
| 10 | 🟢 LLM-OPT | Test-Code zu ausführlich (~220 Zeilen) | Gekürzt auf kritische Tests + Hinweis |

### Verification Checklist

- ✅ AC #1-6 vollständig abgedeckt
- ✅ Alle Tasks haben klare Implementation-Details
- ✅ `find_path()` jetzt gleichwertig zu `query_neighbors()` dokumentiert
- ✅ Test-Strategie enthält Integration-Tests
- ✅ Story 7.6 Kontext integriert
- ✅ Recency-Werte mathematisch korrekt

### Recommendations for Dev Agent

1. **Beginne mit Task 4.1** - `get_pending_nuance_edge_ids()` muss ZUERST implementiert werden, da IEF davon abhängt
2. **Nutze Story 7.6 Pattern** - `properties_filter={"edge_type": "constitutive"}` für effiziente Queries
3. **Verifiziere Imports** - `from mcp_server.analysis.ief import calculate_ief_score` muss nach Task 1 funktionieren
4. **Test-First für AC #4** - Recency-Werte sind jetzt korrekt definiert, Tests sollten sofort passen
