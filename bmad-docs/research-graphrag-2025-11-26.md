# Technical Research: GraphRAG-Erweiterung für cognitive-memory

**Datum:** 2025-11-26  
**Workflow:** BMAD BMM Research (Technical)  
**Status:** ✅ Abgeschlossen  
**Autor:** BMAD Research Agent  

---

## Executive Summary

Diese Recherche evaluiert Optionen zur Erweiterung des `cognitive-memory` Systems um eine **Graphen-Schicht (GraphRAG)**, die strukturierte Beziehungen zwischen Entitäten speichert und abfragt. Dies ist erforderlich für das Projekt `agentic-business`, damit BMAD-BMM Agenten kontextreichere Abfragen durchführen können.

**Empfehlung:** PostgreSQL Adjacency List Pattern (kein Apache AGE), da es die bestehende Architektur optimal ergänzt ohne neue Dependencies einzuführen.

---

## Forschungsfragen & Ergebnisse

### 1. PostgreSQL als Graph-Datenbank: Adjacency List vs. Apache AGE

#### Adjacency List Pattern (Empfohlen ✅)

**Beschreibung:** Graphen werden in relationalen Tabellen gespeichert (nodes + edges), wobei `WITH RECURSIVE` CTEs für Graph-Traversal verwendet werden.

**Vorteile:**
- ✅ **Keine neue Dependency** - Nutzt natives PostgreSQL
- ✅ **Konsistent mit bestehendem Stack** - Selbe Technologie wie pgvector
- ✅ **Einfache Migration** - Standard SQL, keine neue Abfragesprache
- ✅ **Bewährt** - Millionen von Production-Systemen nutzen dieses Pattern
- ✅ **pgvector-Integration** - Embeddings können direkt auf Nodes referenziert werden

**Nachteile:**
- ⚠️ Performance bei sehr tiefen Traversals (>5 Hops)
- ⚠️ Komplexere Queries für Pfadsuche

**Performance:** 
- Für Use Cases mit 1-3 Hop Queries: **<50ms** (typisch für BMAD-BMM)
- Für Pathfinding bis 5 Hops: **<200ms**

#### Apache AGE Extension

**Beschreibung:** PostgreSQL-Extension mit nativer openCypher-Unterstützung.

**Vorteile:**
- Deklarative Graph-Queries (Cypher-Syntax)
- Optimiert für tiefe Traversals

**Nachteile:**
- ❌ **Neue Dependency** - Installation und Wartung
- ❌ **Lernkurve** - openCypher-Syntax
- ❌ **Deployment-Komplexität** - Extension muss auf Server installiert werden
- ❌ **Weniger verbreitet** - Kleinere Community als Neo4j

**Entscheidung:** 
> **Adjacency List Pattern** bevorzugt, da cognitive-memory ein **"No New Dependencies"** Prinzip verfolgt und die Use Cases (1-3 Hops) optimal damit abgedeckt werden.

---

### 2. Hybrid Search: Vektor + Graph kombinieren

#### Best Practices

**2.1 Architektur-Pattern:**

```
User Query
    ↓
┌─────────────────────────────────────────────────────────┐
│                    HYBRID RETRIEVAL                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   (1) Vector Search          (2) Graph Search            │
│   ─────────────────          ───────────────             │
│   • pgvector cosine          • Neighbors by relation     │
│   • L2 Insights              • Pathfinding               │
│   • Semantic similarity      • Structural relationships  │
│                                                          │
│                     ↓                                    │
│              (3) RRF Fusion                              │
│   ─────────────────────────────────────────────          │
│   • Reciprocal Rank Fusion                               │
│   • score = Σ (weight_i / (k + rank_i))                  │
│   • Weights: semantic=0.6, keyword=0.2, graph=0.2        │
│                                                          │
└─────────────────────────────────────────────────────────┘
    ↓
Ranked Results
```

**2.2 Score Fusion (RRF erweitert):**

Aktuell: `80% Semantic + 20% Keyword`

Neu (mit Graph): `60% Semantic + 20% Keyword + 20% Graph`

**2.3 Wann Graph vs. Vector?**

| Query-Typ | Primäre Methode | Beispiel |
|-----------|-----------------|----------|
| **Semantisch** | Vector (80%) | "Was denke ich über Autonomie?" |
| **Relational** | Graph (80%) | "Welche Tech nutzen wir für High-Volume?" |
| **Hybrid** | Beide (50/50) | "Probleme mit Stripe API in Projekten?" |

**2.4 Query-Routing:**

```python
# Pseudo-Code für Query-Routing
if has_relation_keywords(query, ["nutzt", "verbunden mit", "abhängig von"]):
    weight_graph = 0.6
    weight_vector = 0.3
else:
    weight_graph = 0.2
    weight_vector = 0.6
```

---

### 3. GraphRAG Libraries: Evaluation 2025

#### 3.1 Microsoft GraphRAG

**Repository:** [microsoft/graphrag](https://github.com/microsoft/graphrag)  
**Benchmark Score:** 73.9  
**Code Snippets:** 219  

**Beschreibung:** Hierarchischer Ansatz mit Community Detection und Multi-Level Summarization.

**Features:**
- Global Search (Community-Level Summaries)
- Local Search (Entity-focused Traversal)
- Parquet-basierte Index-Speicherung

**Bewertung:**
- ✅ Hervorragend für große, unstrukturierte Dokumente
- ❌ Overkill für cognitive-memory (bereits strukturierte Daten)
- ❌ Eigene Indexing-Pipeline erforderlich

#### 3.2 LlamaIndex PropertyGraphIndex

**Repository:** [run-llama/llama_index](https://github.com/run-llama/llama_index)  
**Benchmark Score:** 87.6  
**Code Snippets:** 13,615  

**Features:**
- `PropertyGraphIndex.from_documents()` - Automatische Entity Extraction
- Neo4j + Qdrant Integration
- `SimpleLLMPathExtractor`, `DynamicLLMPathExtractor`

**Beispiel-Code:**
```python
from llama_index.core import PropertyGraphIndex
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

index = PropertyGraphIndex.from_documents(
    documents,
    property_graph_store=graph_store,
    kg_extractors=[SimpleLLMPathExtractor(llm=llm)],
)
```

**Bewertung:**
- ✅ Sehr mächtig für automatische Graph-Erstellung
- ⚠️ Benötigt Neo4j (nicht PostgreSQL)
- ❌ Nicht direkt kompatibel mit unserem Stack

#### 3.3 Neo4j GraphRAG Python

**Repository:** [neo4j/neo4j-graphrag-python](https://github.com/neo4j/neo4j-graphrag-python)  
**Benchmark Score:** 78.3  
**Code Snippets:** 154  

**Features:**
- `SimpleKGPipeline` für Graph-Erstellung
- `VectorRetriever` + `GraphRAG` für Retrieval
- Schema-gesteuertes Entity Extraction

**Beispiel-Code:**
```python
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline

kg_builder = SimpleKGPipeline(
    llm=llm,
    driver=neo4j_driver,
    embedder=embedder,
    schema={"node_types": ["Project", "Tech"], "relationship_types": ["USES"]},
)
```

**Bewertung:**
- ✅ Production-ready mit gutem Schema-Support
- ❌ Setzt Neo4j voraus
- ❌ Zusätzliche Infrastruktur

#### 3.4 Custom Implementation (Empfohlen ✅)

**Beschreibung:** Eigene Graph-Logik in cognitive-memory mit PostgreSQL Adjacency List.

**Vorteile:**
- ✅ Perfekt integriert in bestehenden MCP Server
- ✅ Keine neuen Dependencies
- ✅ Volle Kontrolle über Datenmodell
- ✅ Direkte pgvector-Integration

**Architektur:**
```
cognitive-memory/
├── mcp_server/
│   ├── db/
│   │   ├── graph.py        # NEW: Graph CRUD
│   │   └── migrations/
│   │       └── 012_graph_schema.sql  # NEW
│   └── tools/
│       └── graph.py        # NEW: 4 Graph Tools
```

---

## Empfehlungen

### Primäre Empfehlung

| Aspekt | Empfehlung | Begründung |
|--------|------------|------------|
| **Graph Storage** | PostgreSQL Adjacency List | Keine neue Dependency, bewährt |
| **Query Language** | SQL + WITH RECURSIVE | Konsistent mit Stack |
| **Graph Library** | Custom Implementation | Perfekte Integration |
| **Hybrid Search** | RRF Fusion (60/20/20) | Erweiterung bestehender Logik |

### Datenmodell

```sql
-- Tabelle: nodes (Knoten)
CREATE TABLE nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label VARCHAR(100) NOT NULL,        -- "Project", "Technology", "Client", "Error"
    name VARCHAR(255) NOT NULL,         -- "Agentic Business", "Next.js", "Acme Corp"
    properties JSONB DEFAULT '{}',      -- Flexible Metadaten
    vector_id UUID REFERENCES l2_insights(id),  -- Link zu Embedding
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(label, name)                 -- Idempotenz
);

CREATE INDEX idx_nodes_label ON nodes(label);
CREATE INDEX idx_nodes_name ON nodes(name);

-- Tabelle: edges (Kanten)
CREATE TABLE edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    relation VARCHAR(100) NOT NULL,      -- "USES", "SOLVES", "CREATED_BY", "RELATED_TO"
    weight FLOAT DEFAULT 1.0 CHECK (weight >= 0 AND weight <= 1),
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_id, target_id, relation)  -- Keine doppelten Kanten
);

CREATE INDEX idx_edges_source ON edges(source_id);
CREATE INDEX idx_edges_target ON edges(target_id);
CREATE INDEX idx_edges_relation ON edges(relation);
```

### MCP Tools (4 neue)

| Tool | Beschreibung | Priority |
|------|--------------|----------|
| `graph_add_node` | Node erstellen (idempotent) | P0 |
| `graph_add_edge` | Kante zwischen Nodes erstellen | P0 |
| `graph_query_neighbors` | Nachbarn finden (mit Tiefe) | P0 |
| `graph_find_path` | Pfad zwischen zwei Nodes | P1 |

### Risiken & Mitigationen

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| Performance bei tiefen Traversals | Low | Medium | Depth-Limit (max 5), Index-Optimierung |
| Komplexe Queries | Medium | Low | Abstraktion in Python, gute Dokumentation |
| Dateninkonsistenz | Low | High | Foreign Key Constraints, Transaktionen |

---

## Nächste Schritte

1. **Correct Course Workflow** - Impact-Analyse auf bestehendes PRD
2. **PRD Update** - Neue FRs (FR013-FR016) für Graph-Tools
3. **Migration erstellen** - `012_graph_schema.sql`
4. **Implementation** - Graph-Modul in MCP Server

---

## Quellen

1. Apache AGE Documentation - https://age.apache.org/overview
2. Microsoft GraphRAG - https://github.com/microsoft/graphrag
3. LlamaIndex PropertyGraph - https://docs.llamaindex.ai/
4. Neo4j GraphRAG Python - https://github.com/neo4j/neo4j-graphrag-python
5. PostgreSQL WITH RECURSIVE - https://www.postgresql.org/docs/current/queries-with.html
6. Reciprocal Rank Fusion - Google Vertex AI Hybrid Search Documentation

---

*Research durchgeführt gemäß BMAD BMM Technical Research Workflow*

