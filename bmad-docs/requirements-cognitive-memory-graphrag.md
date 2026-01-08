# Anforderungsliste: Erweiterung 'cognitive-memory' um GraphRAG

**Datum:** 2025-11-26
**Ziel:** Befähigung des `cognitive-memory` Systems, komplexe Beziehungen zwischen Entitäten zu speichern und abzufragen, um BMAD-BMM Agenten mit strukturiertem Kontext zu versorgen.

---

## 1. High-Level Zielsetzung

Das bestehende `cognitive-memory` (MCP Server + PostgreSQL + pgvector) soll um eine **Graphen-Schicht** erweitert werden.

* **Vektorsuche** (Status Quo) findet *ähnliche* Inhalte.
* **Graphensuche** (Neu) findet *verknüpfte* Inhalte (Kausalitäten, Abhängigkeiten, Hierarchien).

Dies ist essenziell für den **Hybrid-Ansatz** (BMAD-BMM), damit der "BMM Architect" weiß, welche Lösungen in der Vergangenheit funktioniert haben.

---

## 2. Technische Anforderungen

### 2.1 Datenmodell (PostgreSQL)

Wir nutzen PostgreSQL als Graph-Datenbank (Adjacency List Pattern), um keinen neuen Tech-Stack (wie Neo4j) einzuführen.

* **Tabelle `nodes`**
  * `id` (UUID, PK)
  * `label` (VARCHAR) - z.B. "Project", "Technology", "Client", "Error"
  * `name` (VARCHAR) - z.B. "Agentic Business", "Next.js", "Acme Corp"
  * `properties` (JSONB) - Metadaten
  * `vector_id` (UUID, FK) - Link zum Vektor-Embedding (optional)

* **Tabelle `edges`**
  * `id` (UUID, PK)
  * `source_id` (UUID, FK -> nodes)
  * `target_id` (UUID, FK -> nodes)
  * `relation` (VARCHAR) - z.B. "USES", "CREATED_BY", "SOLVES", "RELATED_TO"
  * `weight` (FLOAT) - Relevanz (0.0 - 1.0)
  * `properties` (JSONB) - Metadaten (z.B. Timestamp)

### 2.2 MCP Tools (Erweiterung)

Der MCP Server (`cognitive-memory/mcp_server`) muss um folgende Tools erweitert werden:

#### A. `graph_add_node`

* **Input:** `label` (string), `name` (string), `properties` (json, optional)
* **Logik:** Erstellt Node, wenn nicht vorhanden (Idempotenz basierend auf name+label).
* **Output:** `node_id`

#### B. `graph_add_edge`

* **Input:** `source_name` (string), `target_name` (string), `relation` (string), `source_label` (string), `target_label` (string)
* **Logik:**
    1. Sucht/Erstellt Source & Target Nodes.
    2. Erstellt Edge zwischen ihnen.
* **Output:** Success Message.

#### C. `graph_query_neighbors`

* **Input:** `node_name` (string), `relation_type` (string, optional), `depth` (int, default=1)
* **Zweck:** "Welche Technologien nutzt 'Project A'?" oder "Welche Projekte nutzen 'Next.js'?"
* **Output:** JSON Liste der verbundenen Nodes.

#### D. `graph_find_path`

* **Input:** `start_node` (string), `end_node` (string)
* **Zweck:** "Gibt es eine Verbindung zwischen 'Kunde X' und 'Problem Y'?"
* **Output:** Pfad (Node -> Edge -> Node).

### 2.3 Integration in Existing Tools

* **`store_memory` (Update):** Wenn ein Memory gespeichert wird, soll der Agent optional Graph-Relationen extrahieren und mitspeichern können.

---

## 3. Use Cases für BMAD-BMM

### Use Case 1: Architecture Check

* **Agent:** `@bmad/bmm/architect`
* **Query:** "Welche Datenbank haben wir für Projekte mit 'High Volume' benutzt?"
* **Graph Op:** `graph_query_neighbors(node="High Volume Requirement", relation="SOLVED_BY")`

### Use Case 2: Risk Analysis

* **Agent:** `@bmad/bmm/pm`
* **Query:** "Haben wir Erfahrung mit 'Stripe API'?"
* **Graph Op:** `graph_find_path(start="Me", end="Stripe API")` -> Findet Projekte, Code-Snippets und Errors.

### Use Case 3: Automated Knowledge Harvesting

* **Agent:** `@bmad/bmm/tech-writer`
* **Action:** Nach Projektabschluss.
* **Graph Op:** Erstellt Edges: `Project X` --USES--> `Tech Y`, `Project X` --DELIVERED_TO--> `Client Z`.

---

## 4. Implementierungs-Schritte

1. **DB-Migration:** SQL-Script für `nodes` und `edges` Tabellen.
2. **Python-Logik:** CRUD-Klassen für Graph-Operationen in `mcp_server/db/`.
3. **MCP-Registrierung:** Hinzufügen der neuen Tools in `server.py`.
4. **Testing:** Unit-Tests für Zyklen-Erkennung und Performance.

---
*Erstellt für den Lead Developer von cognitive-memory*
