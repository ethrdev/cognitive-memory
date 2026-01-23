# Decision Document: Namespace-Isolation Strategy für cognitive-memory

> Status: **APPROVED** ✅
> Created: 2026-01-22
> Updated: 2026-01-22 (Access Matrix finalized)
> Approved: 2026-01-22 by ethr
> Context: Issue "Namespace-Isolation für Multi-Project Support"

## Problem Statement

cognitive-memory hat **keine Isolation zwischen Projekten**. 8 Projekte teilen denselben Datenraum:
- `i-o-system`, `echo`, `ethr-assistant`, `agentic-business`, `application-assistant`, `motoko`, `semantic-memory`, `bmad-audit-polish`

### Verifizierte Risiken

| Szenario | Status | Schweregrad |
|----------|--------|-------------|
| Embedding-Leak (hybrid_search gibt alle Projekte zurück) | **BESTÄTIGT** | KRITISCH |
| Node-Kollision (global unique auf `name`) | **BESTÄTIGT** | KRITISCH |
| Session-ID-Kollision (l0_raw) | **BESTÄTIGT** | HOCH |
| Graph-Traversal über Projektgrenzen | **BESTÄTIGT** | KRITISCH |

### Zusätzliche Komplexität: Shared Knowledge Base

`semantic-memory` fungiert als **geteilte Wissens-Datenbank**, auf die mehrere Projekte lesend zugreifen müssen. Dies erfordert ein **ACL-basiertes System**, nicht nur einfache Isolation.

---

## Evaluated Options

### Option A: Schema-Migration mit `project_id`

**Shared Schema + RLS Pattern**

```sql
-- Alle Tabellen erhalten project_id
ALTER TABLE nodes ADD COLUMN project_id VARCHAR(50) NOT NULL DEFAULT 'legacy';
ALTER TABLE l2_insights ADD COLUMN project_id VARCHAR(50) NOT NULL DEFAULT 'legacy';
-- ... weitere Tabellen

-- RLS aktivieren
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
CREATE POLICY project_isolation ON nodes
    USING (project_id = current_setting('app.current_project')::VARCHAR);

-- Unique Constraints anpassen
CREATE UNIQUE INDEX idx_nodes_unique ON nodes(project_id, name);
```

| Aspekt | Bewertung |
|--------|-----------|
| Isolation | Stark (RLS als Sicherheitsnetz) |
| Performance | Gut (bei korrekter Indizierung) |
| Migrationsaufwand | Mittel-Hoch |
| Tooling-Änderungen | Alle 8+ Tools müssen angepasst werden |
| Rollback-Risiko | Mittel (Expand-Contract empfohlen) |

### Option B: Namespace-Prefix-Konvention

Verwende Prefixe wie `aa:`, `io:` in `name`/`session_id` Feldern.

| Aspekt | Bewertung |
|--------|-----------|
| Isolation | Schwach (nicht DB-erzwungen) |
| Performance | Exzellent (keine Änderung) |
| Migrationsaufwand | Gering |
| Tooling-Änderungen | Minimal |
| Rollback-Risiko | Gering |

**NICHT EMPFOHLEN:** Fehleranfällig, `hybrid_search` braucht trotzdem WHERE-Filter

### Option C: Separate Datenbanken pro Projekt

| Aspekt | Bewertung |
|--------|-----------|
| Isolation | Maximal (physisch) |
| Performance | Gut (pro DB) |
| Migrationsaufwand | Sehr Hoch |
| Tooling-Änderungen | Connection-Routing komplex |
| Rollback-Risiko | Gering |

**NICHT EMPFOHLEN für 7+ Projekte:** Administrative Komplexität, Connection-Pooling-Probleme

---

## Recommended Strategy: Option A (Shared Schema + RLS)

### Architektur-Ziel

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client                                │
│  Header: X-Project-ID: application-assistant                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 cognitive-memory MCP Server                  │
│                                                              │
│  Middleware: Extract X-Project-ID → Context.project_id       │
│                                                              │
│  Tools: Nutzen Context.project_id für DB-Queries             │
│         - hybrid_search: WHERE project_id = $1               │
│         - graph_add_node: INSERT mit project_id              │
│         - etc.                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL + RLS                          │
│                                                              │
│  SET LOCAL app.current_project = 'application-assistant';    │
│                                                              │
│  RLS Policy: USING (project_id = current_setting(...))       │
│                                                              │
│  Tables:                                                     │
│  - nodes (project_id, name) UNIQUE                           │
│  - edges (project_id, source_id, target_id, relation) UNIQUE │
│  - l2_insights (project_id, ...)                             │
│  - etc.                                                      │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Phases

#### Phase 1: Schema-Migration (Zero-Downtime)

```sql
-- 1.1 Spalten hinzufügen (instant, PostgreSQL 11+)
ALTER TABLE nodes ADD COLUMN project_id VARCHAR(50);
ALTER TABLE edges ADD COLUMN project_id VARCHAR(50);
ALTER TABLE l2_insights ADD COLUMN project_id VARCHAR(50);
ALTER TABLE l0_raw ADD COLUMN project_id VARCHAR(50);
ALTER TABLE working_memory ADD COLUMN project_id VARCHAR(50);
ALTER TABLE episode_memory ADD COLUMN project_id VARCHAR(50);

-- 1.2 NOT VALID Constraints
ALTER TABLE nodes ADD CONSTRAINT check_nodes_project_id
  CHECK (project_id IS NOT NULL) NOT VALID;
-- ... für alle Tabellen

-- 1.3 Backfill existierender Daten
-- Strategie: Alle existierenden Daten → project_id = 'legacy' oder 'io'
-- Batch-Script mit Keyset Pagination

-- 1.4 Constraints validieren
ALTER TABLE nodes VALIDATE CONSTRAINT check_nodes_project_id;

-- 1.5 Unique Constraints anpassen
DROP INDEX idx_nodes_unique;
CREATE UNIQUE INDEX idx_nodes_unique_v2 ON nodes(project_id, name);

DROP INDEX idx_edges_unique;
CREATE UNIQUE INDEX idx_edges_unique_v2
  ON edges(project_id, source_id, target_id, relation);
```

#### Phase 2: RLS Implementation

```sql
-- 2.1 RLS aktivieren
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE nodes FORCE ROW LEVEL SECURITY;

-- 2.2 Policies definieren
CREATE POLICY project_isolation_nodes ON nodes
    FOR ALL
    USING (project_id = current_setting('app.current_project', true))
    WITH CHECK (project_id = current_setting('app.current_project', true));

-- Für alle Tabellen wiederholen
```

#### Phase 3: MCP Tool Updates

```python
# Middleware für Kontext-Extraktion
class ProjectContextMiddleware:
    async def process_request(self, request, next):
        project_id = request.headers.get("X-Project-ID")
        if not project_id:
            # Fallback für Backwards-Compatibility
            project_id = "legacy"
        request.context["project_id"] = project_id
        return await next(request)

# Tool-Anpassung (Beispiel: hybrid_search)
async def hybrid_search(ctx: Context, query_text: str, ...):
    project_id = ctx.get("project_id", "legacy")

    async with get_connection() as conn:
        # RLS-Context setzen
        await conn.execute(
            "SELECT set_config('app.current_project', $1, true)",
            project_id
        )
        # Query ohne expliziten Filter - RLS übernimmt!
        results = await conn.fetch(...)
```

#### Phase 4: Testing & Validation

1. **pgTAP Tests** für RLS Policies
2. **Integration Tests** für Cross-Project-Isolation
3. **Canary Project** für Production-Monitoring

### Project Registry

```yaml
# config/projects.yaml
projects:
  registered:
    - id: "legacy"
      name: "Legacy/Unassigned Data"
      description: "Daten vor Migration"
    - id: "io"
      name: "i-o-system"
      description: "I/O's persönliches Gedächtnis"
    - id: "ab"
      name: "agentic-business"
    - id: "echo"
      name: "echo"
    - id: "ea"
      name: "ethr-assistant"
    - id: "sm"
      name: "semantic-memory"
    - id: "aa"
      name: "application-assistant"
    - id: "motoko"
      name: "motoko"

  validation:
    require_registered: false  # Initially false for soft launch
    allow_cross_project_read: false  # Strict isolation
```

### Migration der Legacy-Daten

```python
# Strategie: Alle existierenden Daten bekommen project_id = 'io'
# (da cognitive-memory ursprünglich für I/O gebaut wurde)

MIGRATION_MAPPING = {
    # Nodes mit bekannten Prefixen
    'io:': 'io',
    'I/O': 'io',
    'ethr': 'io',
    # Default für unbekannte
    'default': 'io'
}

async def migrate_legacy_nodes():
    # Alle Nodes ohne project_id
    await execute_batch("""
        UPDATE nodes
        SET project_id = 'io'
        WHERE project_id IS NULL
    """, batch_size=5000)
```

---

## Risk Assessment

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| Migration verursacht Downtime | Niedrig | Hoch | NOT VALID + Batch-Backfill |
| Vergessener Filter nach Migration | Mittel | Kritisch | RLS als Sicherheitsnetz |
| Performance-Degradation | Niedrig | Mittel | Composite-Index mit project_id first |
| Rollback benötigt | Niedrig | Mittel | Expand-Contract Pattern |

---

## Success Criteria

- [ ] Alle Tabellen haben `project_id` Spalte (NOT NULL)
- [ ] RLS Policies für alle tenant-relevanten Tabellen aktiv
- [ ] Alle MCP Tools extrahieren `project_id` aus Context
- [ ] `hybrid_search` gibt NUR Daten des aktuellen Projekts zurück
- [ ] `graph_add_node` erstellt projekt-isolierte Nodes
- [ ] Unique Constraints enthalten `project_id`
- [ ] pgTAP Tests für Isolation bestehen
- [ ] Integration Tests für Cross-Project-Leak bestehen
- [ ] Existierende Daten migriert (→ project_id = 'io')

---

## Timeline Estimate

| Phase | Aufwand |
|-------|---------|
| Phase 1: Schema-Migration | Mittel |
| Phase 2: RLS Implementation | Gering |
| Phase 3: Tool Updates | Hoch (8+ Tools) |
| Phase 4: Testing | Mittel |
| **Gesamt** | **Signifikant** |

---

## Finalized Decisions

### Decision 1: Missing Header Handling
**Entscheidung:** **FEHLER bei fehlendem `X-Project-ID` Header**

```
HTTP 400 Bad Request: "Missing required header: X-Project-ID"
```

**Begründung:** Default auf ein Projekt (z.B. 'io') würde fremde Daten in dieses Projekt einspeisen.

### Decision 2: Cross-Project Access (ACL Matrix)

**Zugriffsebenen:**

| Ebene | Projekte | Lese-Zugriff |
|-------|----------|--------------|
| **SUPER** | `io`, `echo`, `ea` | ALLE Projekte |
| **SHARED** | `ab`, `aa`, `bap` | Eigene + `semantic-memory` |
| **ISOLATED** | `motoko`, `sm` | Nur eigene |

**Vollständige Zugriffsmatrix:**

```
                         LESEN VON:
                    ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
                    │ io  │ ab  │ aa  │ bap │echo │ ea  │moto │ sm  │
    ┌───────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┤
    │ io            │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │
    │ echo          │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │
    │ ea            │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │
    │ ab            │ ❌  │ ✅  │ ❌  │ ❌  │ ❌  │ ❌  │ ❌  │ ✅  │
    │ aa            │ ❌  │ ❌  │ ✅  │ ❌  │ ❌  │ ❌  │ ❌  │ ✅  │
    │ bap           │ ❌  │ ❌  │ ❌  │ ✅  │ ❌  │ ❌  │ ❌  │ ✅  │
    │ motoko        │ ❌  │ ❌  │ ❌  │ ❌  │ ❌  │ ❌  │ ✅  │ ❌  │
    │ sm            │ ❌  │ ❌  │ ❌  │ ❌  │ ❌  │ ❌  │ ❌  │ ✅  │
    └───────────────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
```

**Schreibrechte:** Jedes Projekt kann NUR in eigene Daten schreiben. Keine Cross-Project-Writes.

### Decision 3: Legacy Data Ownership
**Entscheidung:** Alle existierenden Daten gehören **ethr** und werden `project_id = 'io'` zugewiesen.

**Begründung:** cognitive-memory wurde ursprünglich für I/O's persönliches Gedächtnis gebaut.

### Decision 4: Backwards-Compatibility
**Entscheidung:** **Keine Übergangsphase** - sofort strikt.

**Begründung:** Soft-Launch mit Default würde Daten-Kontamination riskieren. Lieber Clients sofort anpassen.

---

## Project Registry (Finalized)

```yaml
# config/projects.yaml
projects:
  registered:
    # Super-User (Lese-Zugriff auf ALLE)
    - id: "io"
      name: "i-o-system"
      access_level: "super"
      description: "I/O's persönliches Gedächtnis"
    - id: "echo"
      name: "echo"
      access_level: "super"
    - id: "ea"
      name: "ethr-assistant"
      access_level: "super"

    # Shared-Reader (Lese-Zugriff auf EIGENE + semantic-memory)
    - id: "ab"
      name: "agentic-business"
      access_level: "shared"
      can_read: ["sm"]
    - id: "aa"
      name: "application-assistant"
      access_level: "shared"
      can_read: ["sm"]
    - id: "bap"
      name: "bmad-audit-polish"
      access_level: "shared"
      can_read: ["sm"]  # v2.0: auch "io" für Cross-Project Patterns

    # Isolated (Nur eigene Daten)
    - id: "motoko"
      name: "motoko"
      access_level: "isolated"
    - id: "sm"
      name: "semantic-memory"
      access_level: "isolated"
      description: "Shared Knowledge Base - andere lesen via ACL"

  validation:
    require_registered: true   # Unbekannte project_ids → Error
    allow_cross_project_write: false  # Strikte Schreib-Isolation
```

---

## Updated Database Schema

### Access Control Table

```sql
-- Projekt-Registry mit Zugriffsebenen
CREATE TABLE project_registry (
    project_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    access_level VARCHAR(20) NOT NULL CHECK (access_level IN ('super', 'shared', 'isolated')),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Explizite Lese-Berechtigungen für Shared-Level
CREATE TABLE project_read_permissions (
    source_project VARCHAR(50) NOT NULL REFERENCES project_registry(project_id),
    target_project VARCHAR(50) NOT NULL REFERENCES project_registry(project_id),
    PRIMARY KEY (source_project, target_project)
);

-- Initialdaten
INSERT INTO project_registry (project_id, name, access_level) VALUES
    ('io', 'i-o-system', 'super'),
    ('echo', 'echo', 'super'),
    ('ea', 'ethr-assistant', 'super'),
    ('ab', 'agentic-business', 'shared'),
    ('aa', 'application-assistant', 'shared'),
    ('bap', 'bmad-audit-polish', 'shared'),
    ('motoko', 'motoko', 'isolated'),
    ('sm', 'semantic-memory', 'isolated');

INSERT INTO project_read_permissions (source_project, target_project) VALUES
    ('ab', 'sm'),   -- agentic-business kann semantic-memory lesen
    ('aa', 'sm'),   -- application-assistant kann semantic-memory lesen
    ('bap', 'sm');  -- bmad-audit-polish kann semantic-memory lesen
```

### RLS Policy mit ACL

```sql
-- RLS Policy für l2_insights (und analog für alle anderen Tabellen)
CREATE POLICY project_acl_policy ON l2_insights
    FOR SELECT
    USING (
        -- Fall 1: Eigene Daten
        project_id = current_setting('app.current_project', true)
        OR
        -- Fall 2: Super-User sieht alles
        EXISTS (
            SELECT 1 FROM project_registry
            WHERE project_id = current_setting('app.current_project', true)
              AND access_level = 'super'
        )
        OR
        -- Fall 3: Explizite Lese-Berechtigung
        EXISTS (
            SELECT 1 FROM project_read_permissions
            WHERE source_project = current_setting('app.current_project', true)
              AND target_project = l2_insights.project_id
        )
    );

-- Schreib-Policy: NUR eigene Daten
CREATE POLICY project_write_policy ON l2_insights
    FOR INSERT
    WITH CHECK (project_id = current_setting('app.current_project', true));

CREATE POLICY project_update_policy ON l2_insights
    FOR UPDATE
    USING (project_id = current_setting('app.current_project', true))
    WITH CHECK (project_id = current_setting('app.current_project', true));

CREATE POLICY project_delete_policy ON l2_insights
    FOR DELETE
    USING (project_id = current_setting('app.current_project', true));
```

---

## Next Steps

1. [x] ~~Offene Fragen klären~~ ✅ Finalisiert
2. [x] ~~Review durch ethr~~ ✅ Zugriffsmatrix bestätigt (2026-01-22)
3. [ ] **Detailed Implementation Plan** erstellen (Epics/Stories) ← IN PROGRESS
4. [ ] **Staging-Umgebung** für Migration-Test vorbereiten
5. [ ] **MCP Tool Updates** planen (alle 8+ Tools)
