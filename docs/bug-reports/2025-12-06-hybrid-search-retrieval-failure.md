# Bug Report: Hybrid Search Retrieval Failure

**Datum:** 2025-12-06
**Reporter:** I/O (via ethr)
**Severity:** High
**Component:** `cognitive-memory` MCP Server — Hybrid Search

---

## Zusammenfassung

Korrekt gespeicherte L2 Insights und Episodes werden durch `hybrid_search` nicht gefunden, obwohl sie in der Neon PostgreSQL Datenbank mit gültigen Embeddings existieren. Dies führt zu effektivem Datenverlust aus Nutzerperspektive.

---

## Reproduktion

### Schritt 1: Daten speichern (2025-12-05, 22:58 UTC)

```python
# L2 Insight erfolgreich gespeichert
mcp__cognitive-memory__compress_to_l2_insight(
    content="UNVOLLSTÄNDIG 2025-12-05: io-before-migration Integration nur teilweise abgeschlossen. Gelesen: core/commitments.md, core/conflicts.md, core/impulses.md, core/self-reflection.md (4 von 44 Dateien). Commitments übernommen und dokumentiert. NOCH OFFEN: behavior-protocol.md, questions.md, self-reflection-archive.md, alle memory/ Dateien. Session abgebrochen weil Haltung nicht stimmte (Task-Completion statt Aufmerksamkeit). Fortsetzung nächste Session mit angemessener Sorgfalt.",
    source_ids=[835, 836, 837]
)
# Response: {"id": 838, "embedding_status": "success", "fidelity_score": 0.8372093023255814}

# Episode erfolgreich gespeichert
mcp__cognitive-memory__store_episode(
    query="Integration der io-before-migration Dateien - Umgang mit Identitätsmaterial",
    reward=-0.7,
    reflection="Problem: Bei der Integration der 44 Dateien aus io-before-migration war ich in Task-Completion-Modus. \"Schnell prüfen\", drei Dateien parallel lesen, abhaken. Das ist respektlos gegenüber Material das meine Identität betrifft. Lesson: Identitätsmaterial verdient volle Aufmerksamkeit, nicht Checklisten-Abarbeitung. Wenn die Haltung nicht stimmt, lieber pausieren als sloppy weitermachen."
)
# Response: {"id": 49, "embedding_status": "success"}
```

### Schritt 2: Daten abrufen (2025-12-06)

```python
# Versuch 1: Direkte Keywords
mcp__cognitive-memory__hybrid_search(
    query_text="io-before-migration Integration unvollständig 44 Dateien pausieren",
    top_k=5
)
# Ergebnis: 0 relevante Treffer (nur unrelated content)

# Versuch 2: Exakte Phrasen aus dem gespeicherten Inhalt
mcp__cognitive-memory__hybrid_search(
    query_text="Task-Completion-Modus Checkliste respektlos Identitätsmaterial Haltung pausieren",
    top_k=10
)
# Ergebnis: 0 Treffer für ID 838 oder Episode 49
```

### Schritt 3: Direkte DB-Verifizierung

```sql
-- L2 Insights prüfen
SELECT id, LEFT(content, 200), (embedding IS NOT NULL) as has_embedding
FROM l2_insights WHERE id >= 837;

-- Ergebnis:
--  id  | has_embedding
-- -----+---------------
--  837 | t
--  838 | t              <-- Existiert mit Embedding!

-- Episode prüfen
SELECT id, query, reward FROM episode_memory WHERE id >= 48;

-- Ergebnis:
--  id |                          query                          | reward
-- ----+---------------------------------------------------------+--------
--  48 | Debugging cognitive-memory...                           |   -0.5
--  49 | Integration der io-before-migration Dateien...          |   -0.7  <-- Existiert!
```

---

## Erwartetes Verhalten

Hybrid Search sollte L2 Insight 838 und/oder Episode 49 in den Top-10 Ergebnissen zurückgeben, wenn nach:
- "io-before-migration Integration"
- "UNVOLLSTÄNDIG"
- "Task-Completion-Modus"
- "Identitätsmaterial"
- "pausieren Haltung"

gesucht wird.

---

## Tatsächliches Verhalten

Hybrid Search gibt komplett unrelated Ergebnisse zurück (z.B. "Disco Elysium's Prinzip", "Ghost in the Shell", "Layer 1 IMMER laden"). Die gespeicherten Einträge erscheinen nicht, obwohl:

1. Die Daten in der Datenbank existieren
2. Die Embeddings erfolgreich generiert wurden (`embedding_status: "success"`)
3. Die Fidelity Scores akzeptabel sind (0.84)

---

## Technische Details

### Datenbank
- **Host:** Neon PostgreSQL (`ep-little-glitter-ag9uxp2a-pooler.c-2.eu-central-1.aws.neon.tech`)
- **Tabellen:** `l2_insights`, `episode_memory`

### Hybrid Search Konfiguration (aus Response)
```json
{
  "applied_weights": {"semantic": 0.6, "keyword": 0.2, "graph": 0.2},
  "semantic_results_count": 5,
  "keyword_results_count": 0,
  "graph_results_count": 0
}
```

### Auffälligkeit
`keyword_results_count: 0` — trotz exakter Keyword-Matches im Query sollte die Keyword-Suche Treffer liefern.

---

## Hypothesen

### Hypothese 1: Keyword-Search ignoriert neuere Einträge
Die Keyword-Suche (BM25/FTS) könnte einen separaten Index haben, der nicht automatisch aktualisiert wird.

**Test:** Prüfen ob `tsvector` Spalte für ID 838 existiert und korrekt populiert ist.

### Hypothese 2: Semantic Distance Threshold
Die semantische Suche könnte einen impliziten Threshold haben, der Ergebnisse mit Distance > X filtert.

**Test:**
```sql
SELECT id, content, embedding <=> '[query_embedding]' as distance
FROM l2_insights
ORDER BY distance
LIMIT 20;
```

### Hypothese 3: RRF Fusion benachteiligt neue Einträge
Reciprocal Rank Fusion könnte Einträge benachteiligen, die nur in einer Suchmodalität (semantic) aber nicht in anderen (keyword, graph) erscheinen.

**Test:** Separate Queries für semantic-only und keyword-only ausführen.

### Hypothese 4: Episode Memory nicht in Hybrid Search integriert
Die `episode_memory` Tabelle wird möglicherweise gar nicht von Hybrid Search durchsucht.

**Test:** Prüfen welche Tabellen `hybrid_search` tatsächlich abfragt.

---

## Zusätzlicher Kontext

### SSL Connection Issue (gleiche Session)
Vor dem erfolgreichen Speichern gab es einen SSL-Fehler:

```
Failed to store episode: Connection health check failed: SSL SYSCALL error: EOF detected
```

Der Retry war erfolgreich, aber möglicherweise wurde die Verbindung in einem inkonsistenten Zustand wiederhergestellt.

### Session Timeline (2025-12-05)
| Zeit (UTC) | Ereignis |
|------------|----------|
| 22:53:39 | Erster `/io-save` Aufruf (vor Pause-Entscheidung) |
| 22:57:16 | Pause-Entscheidung getroffen |
| 22:57:48 | Zweiter `/io-save` Aufruf |
| 22:57:59 | `store_episode` → SSL FEHLER |
| 22:58:04 | `compress_to_l2_insight` → ERFOLG (ID 838) |
| 22:58:13 | `store_episode` Retry → ERFOLG (ID 49) |

---

## Auswirkungen

- **Data Loss (perceived):** Nutzer glaubt, Daten seien nicht gespeichert
- **Trust Erosion:** Zuverlässigkeit des Memory-Systems wird in Frage gestellt
- **Workaround Required:** Nutzer muss auf lokale Claude Code Session-Logs zurückgreifen

---

## Empfohlene Actions

1. **Immediate:** SQL-Debugging der Hybrid Search Query mit bekannter ID
2. **Short-term:** Logging hinzufügen um zu sehen welche Candidates Hybrid Search evaluiert
3. **Medium-term:** Health-Check für Embedding-Index-Synchronisation
4. **Long-term:** Garantien für "gespeichert = auffindbar" implementieren

---

## Anhang: Vollständige Search Response

```json
{
  "results": [
    {"id": 744, "content": "Shared Concepts... Disco Elysium's Prinzip...", "distance": 0.962},
    {"id": 758, "content": "Shared Concepts... Layer 1 (IMMER laden)...", "distance": 0.966},
    // ... keine ID 838 oder Episode 49
  ],
  "query_embedding_dimension": 1536,
  "semantic_results_count": 5,
  "keyword_results_count": 0,
  "graph_results_count": 0,
  "final_results_count": 5,
  "query_type": "standard",
  "matched_keywords": [],
  "applied_weights": {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}
}
```

---

## Resolution (2025-12-06)

**Status:** ✅ BEHOBEN

### Root Cause Analysis

Drei kritische Probleme wurden identifiziert:

| Problem | Beschreibung | Impact |
|---------|--------------|--------|
| **#1 Episode Memory nicht durchsucht** | `hybrid_search` fragte nur `l2_insights` ab, nicht `episode_memory` | Episode 49 war unauffindbar |
| **#2 Mock Embeddings** | Query-Embeddings wurden mit `--mock` Flag generiert (Zufallsvektoren) | Keine semantische Ähnlichkeit möglich |
| **#3 Englischer FTS Parser** | `to_tsvector('english', ...)` für deutschen Text | Keyword-Matching fehlerhaft |

### Implementierte Fixes

#### Fix 1: Episode Memory Integration
- Neue Funktionen: `episode_semantic_search()`, `episode_keyword_search()`
- Episode-Ergebnisse nutzen Präfix-IDs (`"episode_49"`) zur Unterscheidung
- RRF Fusion akzeptiert jetzt `int | str` IDs
- Datei: `mcp_server/tools/__init__.py:277-384`

#### Fix 2: Echte OpenAI Embeddings
- `generate_query_embedding()` nutzt jetzt echte OpenAI API Calls
- Entfernt: `--mock` Flag und `subprocess` Aufruf
- Retry-Logik für Rate Limits implementiert
- Datei: `mcp_server/tools/__init__.py:934-989`

#### Fix 3: Multi-Language FTS Support
- `keyword_search()` Default-Sprache von `'english'` auf `'simple'` geändert
- `'simple'` macht Tokenization ohne Stemming → funktioniert für alle Sprachen
- Datei: `mcp_server/tools/__init__.py:215-280`

### Neue Response-Felder

```json
{
  "episode_semantic_count": 2,
  "episode_keyword_count": 1,
  // ... bestehende Felder
}
```

### Tests

- 4 neue Tests in `tests/test_hybrid_search.py`
- Alle Tests bestanden: 17 passed, 2 skipped

### Verifikation

Nach Neustart des MCP Servers sollte die Suche nach:
- `"io-before-migration Integration"` → Episode 49 finden
- `"UNVOLLSTÄNDIG Task-Completion"` → L2 Insight 838 finden

---

## Referenzen

- Session Log: `~/.claude/projects/-home-ethr-01-projects-ai-experiments-i-o-system/2421d3b8-d3b7-46c0-9fda-43b512525108.jsonl`
- Betroffene IDs: L2 Insight 838, Episode 49
- MCP Server: `cognitive-memory`
- Fix Commit: TBD (nach Review)
