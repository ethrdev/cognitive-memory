# Epic 9: Structured Retrieval - Tags & Filter System

**Status:** Geplant
**Erstellt:** 2026-02-11
**Kontext:** I/O kann Wissen speichern aber nicht gezielt abrufen. hybrid_search ist probabilistisch - es gibt keinen deterministischen Zugang zu gespeichertem Wissen. Dieses Epic fügt Tags und Filter hinzu.

**Hintergrund:** ethrs Frage: "Was bringt es, wenn sie alles merken aber nichts abrufen kann?" Die externe Research bestätigt: Pre-Filtering vor Vektorsuche ist Industriestandard. cognitive-memory hat die Architektur (JSONB, RRF, Sector-Filter) - es fehlen spezifische Features.

---

## Überblick

| Story | Titel | Prio | Abhängigkeit |
|-------|-------|------|-------------|
| 9.1 | Tags-Infrastruktur (Schema + Parameter) | P1 | Keine |
| 9.2 | Filter-Endpoints (list_episodes, list_insights) | P2 | 9.1 |
| 9.3 | Pre-Filtering in hybrid_search | P2 | 9.1 |
| 9.4 | Retroaktives Tagging des Bestands | P3 | 9.1 |

---

## Story 9.1: Tags-Infrastruktur

**Ziel:** Tags als First-Class-Citizen auf Episodes und Insights.

### Schema-Migration

```sql
-- Migration: 033_add_tags.sql

-- Tags auf episode_memory
ALTER TABLE episode_memory ADD COLUMN tags TEXT[] DEFAULT '{}';
CREATE INDEX idx_episode_tags ON episode_memory USING gin(tags);

-- Tags auf l2_insights (eigene Spalte statt nur JSONB)
ALTER TABLE l2_insights ADD COLUMN tags TEXT[] DEFAULT '{}';
CREATE INDEX idx_l2_tags ON l2_insights USING gin(tags);

-- Metadata auf episode_memory (für Erweiterbarkeit)
ALTER TABLE episode_memory ADD COLUMN metadata JSONB DEFAULT '{}';
```

### Parameter-Erweiterung

**store_episode:**
```python
# Neuer optionaler Parameter: tags (TEXT[])
# Beispiel: store_episode(query="...", reward=0.5, reflection="...", tags=["dark-romance", "stil"])
```

**compress_to_l2_insight:**
```python
# Neuer optionaler Parameter: tags (TEXT[])
# Beispiel: compress_to_l2_insight(content="...", source_ids=[], tags=["relationship", "ethr"])
```

### Tag-Taxonomie

**Closed (feste Werte als Empfehlung, nicht erzwungen):**
- source_type: `self`, `ethr`, `shared`, `relationship`

**Open (Freitext):**
- Projekte: `dark-romance`, `drift`, `cognitive-memory`, `i-o-system`
- Themen: `stil`, `pattern`, `architektur`, `beziehung`
- Frei erweiterbar

### Acceptance Criteria

- [ ] Migration läuft ohne Datenverlust
- [ ] store_episode akzeptiert optionalen tags-Parameter
- [ ] compress_to_l2_insight akzeptiert optionalen tags-Parameter
- [ ] Tags werden als TEXT[] gespeichert mit GIN-Index
- [ ] Bestehende Aufrufe ohne tags funktionieren unverändert (Backward-Compatible)
- [ ] Tests: Unit + Integration

---

## Story 9.2: Filter-Endpoints

**Ziel:** Deterministischer Zugang zu Episodes und Insights.

### list_episodes erweitern

```python
# Neue Parameter:
# - tags: TEXT[] (optional) - Array-Contains: WHERE tags @> ARRAY['dark-romance']
# - category: VARCHAR (optional) - Prefix-Match: WHERE query LIKE '[ethr]%'
# - date_from: TIMESTAMPTZ (optional)
# - date_to: TIMESTAMPTZ (optional)
# Bestehend: limit, offset, since (since bleibt für Backward-Compatibility)
```

### list_insights (NEUER Endpoint)

```python
@mcp.tool()
async def list_insights(
    tags: list[str] | None = None,      # Array-Contains Filter
    date_from: str | None = None,        # ISO 8601
    date_to: str | None = None,          # ISO 8601
    io_category: str | None = None,      # Exakter Match
    is_identity: bool | None = None,     # Boolean Filter
    memory_sector: str | None = None,    # Sector Filter
    limit: int = 50,                     # 1-100
    offset: int = 0
) -> dict:
    """Browse L2 Insights mit strukturierten Filtern."""
    # SELECT id, content, tags, memory_strength, memory_sector, created_at
    # FROM l2_insights
    # WHERE is_deleted = FALSE
    # AND (tags @> ARRAY[...] IF tags provided)
    # AND (created_at >= date_from IF provided)
    # AND (created_at <= date_to IF provided)
    # ORDER BY created_at DESC
    # LIMIT limit OFFSET offset
    #
    # Returns: insights[], total_count, limit, offset
```

### Acceptance Criteria

- [ ] list_episodes akzeptiert tags, category, date_from, date_to
- [ ] list_insights Endpoint existiert und funktioniert
- [ ] Alle Filter sind optional und kombinierbar
- [ ] Pagination funktioniert korrekt mit total_count
- [ ] Backward-Compatible: Bestehende list_episodes Aufrufe unverändert
- [ ] Tests: Unit + Integration für alle Filter-Kombinationen

---

## Story 9.3: Pre-Filtering in hybrid_search

**Ziel:** hybrid_search schränkt den Suchraum VOR der Vektorsuche ein.

### Parameter-Erweiterung

```python
# Neue Parameter auf hybrid_search:
# - tags_filter: TEXT[] (optional) - Pre-Filter vor Vektorsuche
# - date_from: TIMESTAMPTZ (optional)
# - date_to: TIMESTAMPTZ (optional)
# - source_type_filter: TEXT[] (optional) - nur "l2_insight", "episode_memory", etc.
```

### Implementierung

```python
# Pre-Filtering (NICHT Post-Filtering!)
#
# Semantic Search wird eingeschränkt:
# SELECT ... FROM l2_insights
# WHERE is_deleted = FALSE
# AND (tags @> ARRAY[...] IF tags_filter)
# AND (created_at >= date_from IF provided)
# ORDER BY embedding <=> query_embedding
# LIMIT top_k
#
# Episode Search wird ebenfalls eingeschränkt:
# SELECT ... FROM episode_memory
# WHERE (tags @> ARRAY[...] IF tags_filter)
# AND (created_at >= date_from IF provided)
# ORDER BY embedding <=> query_embedding
# LIMIT top_k
```

### Acceptance Criteria

- [ ] hybrid_search akzeptiert tags_filter, date_from, date_to, source_type_filter
- [ ] Filter werden VOR der Vektorsuche angewendet (Pre-Filtering)
- [ ] Ergebnisse enthalten nur Einträge die den Filtern entsprechen
- [ ] Performance: Kein signifikanter Overhead durch zusätzliche WHERE-Clauses
- [ ] Backward-Compatible: hybrid_search ohne neue Parameter funktioniert wie bisher
- [ ] Tests: Unit + Integration

---

## Story 9.4: Retroaktives Tagging des Bestands

**Ziel:** Bestehende Episodes und Insights bekommen Tags.

### Regelbasiertes Script

```python
# Migration-Script (einmalig ausführen)

TAG_RULES = {
    # Episode Query-Prefix → Tags
    r'^\[self\]': ['self'],
    r'^\[ethr\]': ['ethr'],
    r'^\[shared\]': ['shared'],
    r'^\[relationship\]': ['relationship'],

    # Keyword-basiert → Projekt-Tags
    r'Dark Romance|Szene|Kira|Jan': ['dark-romance'],
    r'Drift|Layer': ['drift'],
    r'Stil|Anti-Pattern|aus-nicht-ueber|aesthetisieren': ['stil'],
    r'Validation|Soll ich|nachgefragt': ['pattern'],
    r'cognitive-memory|MCP|hybrid_search': ['cognitive-memory'],
}

# Für jede Episode:
# 1. Query-Text gegen Regeln matchen
# 2. Alle matchenden Tags sammeln
# 3. UPDATE episode_memory SET tags = ARRAY[...] WHERE id = X

# Für jeden L2 Insight:
# 1. Content gegen Regeln matchen
# 2. UPDATE l2_insights SET tags = ARRAY[...] WHERE id = X
```

### Acceptance Criteria

- [ ] Script verarbeitet alle bestehenden Episodes (aktuell ~120)
- [ ] Script verarbeitet alle bestehenden Insights
- [ ] Regelbasiert, kein LLM nötig (Kosten = 0)
- [ ] ~80% Trefferquote erwartet, Rest bleibt ungetaggt
- [ ] Dry-Run Modus verfügbar (zeigt was getaggt würde ohne zu schreiben)
- [ ] Idempotent: Kann mehrfach ausgeführt werden ohne Duplikate
- [ ] Logging: Zeigt wie viele Einträge getaggt wurden pro Regel

---

## Nicht in diesem Epic

- **Background Consolidator** - Tag-Volumen zu klein für automatische Bereinigung
- **LLM-basiertes Tagging** - Regelbasiert reicht bei aktuellem Volumen
- **Alpha-Parameter auf hybrid_search** - Bestehende Gewichtung mit Query-Routing reicht
- **Cursor-basierte Pagination** - OFFSET reicht bei aktuellem Volumen (<1000 Einträge)

---

## Referenzen

- I/O Memory Guide: `.io-system/io/memory-guide.md` (i-o-system Projekt)
- Research: Pre-Filtering Best Practices, Hybride Taxonomien, Retroaktives Tagging (ethr, 2026-02-11)
- Codebase-Analyse: Schema, Endpoints, Hybrid Search Internals (I/O, 2026-02-11)
