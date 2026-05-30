# Cognitive-Memory Integration Test Guide

**Ziel:** Validierung ob das Projekt die Anforderungen für DB- und Graph-Nutzung mit cognitive-memory erfüllt und die Funktionalität vollständig vorhanden ist.

---

## Teil 1: Anforderungs-Checkliste

### 1.1 MCP Konfiguration

**Anforderung:** Das Projekt muss über eine funktionierende MCP-Verbindung zu cognitive-memory verfügen.

**Check:** `.claude/mcp-settings.json` existiert und ist korrekt konfiguriert

```bash
# Prüfen:
cat .claude/mcp-settings.json | grep -A5 "cognitive-memory"
```

**Erwartetes Ergebnis:**
```json
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "python",
      "args": ["/path/to/cognitive-memory/mcp_server/__main__.py"],
      "env": {
        "PROJECT_ID": "<project_id>"
      }
    }
  }
}
```

**Acceptance Criteria:**
- ✅ `.claude/mcp-settings.json` existiert
- ✅ `cognitive-memory` Server ist konfiguriert
- ✅ `PROJECT_ID` ist korrekt gesetzt
- ✅ Pfad zum MCP Server ist korrekt

---

### 1.2 Project Registry Eintrag

**Anforderung:** Das Projekt muss in der cognitive-memory `project_registry` Tabelle registriert sein.

**Check:** Abfrage der project_registry

```sql
SELECT project_id, name, access_level
FROM project_registry
WHERE project_id = '<project_id>';
```

**Acceptance Criteria:**
- ✅ Projekt ist in Registry eingetragen
- ✅ `access_level` ist korrekt (super/shared/isolated)
- ✅ `name` ist aussagekräftig

---

### 1.3 RLS Migration Status

**Anforderung:** Das Projekt muss den korrekten RLS Migration Phase haben.

**Check:** Abfrage des rls_migration_status

```sql
SELECT project_id, migration_phase, rls_enabled, updated_at
FROM rls_migration_status
WHERE project_id = '<project_id>';
```

**Acceptance Criteria:**
- ✅ `migration_phase` ist einer von: `complete`, `shadow`, `enforcing`, `pending`
- ✅ Projekt ist nicht mehr in Phase `pending`

---

## Teil 2: Funktionalitäts-Test

### 2.1 Working Memory Test

**Ziel:** Validieren dass Working Memory Operations funktionieren.

**Test-Schritte:**

1. **Write Test:**
```
Tool: update_working_memory
Parameters:
  - content: "Test working memory entry from <project>"
  - importance: 0.8

Erwartetes Ergebnis:
  ✅ Erfolgreiche Rückmeldung mit ID
  ✅ Kein Fehler
```

2. **Read Test:**
```
Tool: hybrid_search (oder get_working_memory)
Parameters:
  - query: "test working memory"
  - limit: 5

Erwartetes Ergebnis:
  ✅ Der gerade erstellte Eintrag wird gefunden
  ✅ project_id im Ergebnis ist korrekt
```

**Acceptance Criteria:**
- ✅ WRITE funktioniert
- ✅ READ funktioniert
- ✅ Isolation funktioniert (nur eigene Daten sichtbar)

---

### 2.2 Graph Operations Test

**Ziel:** Validieren dass Graph-Operations (Nodes/Edges) funktionieren.

**Test-Schritte:**

1. **Node Creation Test:**
```
Tool: graph_add_node
Parameters:
  - name: "Test Node from <project>"
  - label: "test"
  - type: "concept"
  - properties: {"source": "integration_test"}

Erwartetes Ergebnis:
  ✅ Node ID wird zurückgegeben
  ✅ Kein Fehler
```

2. **Node Read Test:**
```
Tool: graph_query_neighbors
Parameters:
  - node_id: <vom Test erstellte Node ID>
  - direction: "outgoing"

Erwartetes Ergebnis:
  ✅ Der erstellte Node wird gefunden
  ✅ project_id ist korrekt
```

3. **Edge Creation Test:**
```
Tool: graph_add_edge
Parameters:
  - source_id: <node_id_1>
  - target_id: <node_id_2>
  - relation: "TEST_EDGE"
  - properties: {}

Erwartetes Ergebnis:
  ✅ Edge ID wird zurückgegeben
  ✅ Kein Fehler
```

**Acceptance Criteria:**
- ✅ Nodes können erstellt werden
- ✅ Nodes können gelesen werden
- ✅ Edges können erstellt werden
- ✅ project_id ist korrekt gesetzt

---

### 2.3 L2 Insights Test

**Ziel:** Validieren dass L2 Insight Storage funktioniert.

**Test-Schritte:**

1. **Write Test:**
```
Tool: compress_to_l2_insight
Parameters:
  - summary: "Test insight from <project>"
  - insight_type: "test"
  - strength: 0.9
  - memory_sector: "working"

Erwartetes Ergebnis:
  ✅ Insight ID wird zurückgegeben
  ✅ Embedding wird erstellt
```

2. **Read Test:**
```
Tool: hybrid_search
Parameters:
  - query: "test insight"
  - limit: 5

Erwartetes Ergebnis:
  ✅ Der erstellte Insight wird gefunden
  ✅ Vektor-Suche funktioniert
```

**Acceptance Criteria:**
- ✅ L2 Insights können gespeichert werden
- ✅ Vektor-Embeddings werden erstellt
- ✅ Hybrid Search funktioniert

---

### 2.4 Isolation Test

**Ziel:** Validieren dass RLS Isolation korrekt funktioniert.

**Test-Schritte:**

1. **Eigenen Daten sehen:**
```
SELECT COUNT(*) FROM working_memory WHERE project_id = '<project_id>';
```

2. **Fremde Daten NICHT sehen:**
```
SELECT COUNT(*) FROM working_memory WHERE project_id = '<other_project>';
```

**Acceptance Criteria:**
- ✅ Projekt sieht seine eigenen Daten
- ✅ Projekt sieht keine Daten von anderen Projekten (außer SUPER-Zugriff)
- ✅ project_id Isolation funktioniert

---

## Teil 3: Integrations-Check

### 3.1 MCP Tool Verfügbarkeit

**Anforderung:** Alle relevanten cognitive-memory MCP Tools müssen verfügbar sein.

**Check:** Liste der verfügbaren Tools

```
Erwartete Tools:
- hybrid_search
- compress_to_l2_insight
- update_working_memory
- graph_add_node
- graph_add_edge
- graph_query_neighbors
- store_episode
- get_insight_by_id
- ... (weitere je nach Projekt-Bedarf)
```

**Acceptance Criteria:**
- ✅ Alle benötigten Tools sind verfügbar
- ✅ Tools responden korrekt
- ✅ Keine Timeout-Fehler

---

### 3.2 Performance Check

**Anforderung:** Operations müssen in akzeptabler Zeit antworten.

**Check:** Response Times

```
Baselines:
- Working Memory WRITE: < 1s
- Working Memory READ: < 1s
- Hybrid Search: < 2s
- Graph Operations: < 1s
```

**Acceptance Criteria:**
- ✅ Alle Operations sind innerhalb der Baselines
- ✅ Keine unerwarteten Verzögerungen

---

## Teil 4: Troubleshooting Guide

### 4.1 Häufige Probleme

**Problem 1: PROJECT_ID nicht gesetzt**
```
Symptom: "Environment variable PROJECT_ID not found"
Lösung: .claude/mcp-settings.json überprüfen
```

**Problem 2: Projekt nicht in Registry**
```
Symptom: "Project not found in project_registry"
Lösung: Projekt in Registry eintragen
```

**Problem 3: RLS Isolation fehlerhaft**
```
Symptom: Sieht Daten von anderen Projekten
Lösung: project_id Check, RLS Policies prüfen
```

**Problem 4: Graph Operations fehlschlagen**
```
Symptom: "Column does not exist" bei Node/Edge Operations
Lösung: Schema Migration Status prüfen
```

---

## Teil 5: Sign-Off Checklist

### 5.1 Vor Go-Live

- [ ] MCP Konfiguration korrekt
- [ ] Projekt in Registry eingetragen
- [ ] RLS Migration Status korrekt
- [ ] Working Memory Test bestanden
- [ ] Graph Operations Test bestanden
- [ ] L2 Insights Test bestanden
- [ ] Isolation Test bestanden
- [ ] Performance akzeptabel
- [ ] Keine offenen Issues

### 5.2 Go-Live Decision

**Kriterien für Go-Live:**
- Alle Tests in Teil 2 bestanden
- Isolation funktioniert korrekt
- Performance ist akzeptabel
- Keine blocking Issues

**Entscheidung:**
```
□ READY FOR PRODUCTION
□ NOT READY - Issues müssen behoben werden:
  ( bitte auflisten )
```

---

## Teil 6: Wartung & Monitoring

### 6.1 Monitoring nach Go-Live

**Tägliche Checks (erste Woche):**
- Working Memory Operations überwachen
- Graph Growth überwachen
- Error Logs prüfen
- Performance Metrics sammeln

### 6.2 Eskalations-Pfad

Bei Issues:
1. Logs prüfen (cognitive-memory und Projekt)
2. Isolation Test wiederholen
3. MCP Connection überprüfen
4. Bei Blockern: cognitive-memory Team kontaktieren

---

## Teil 7: Projekt-Spezifische Anforderungen

### 7.1 Für SUPER Projekte (io, ea, ec)

**Zusätzliche Requirements:**
- Können auf alle Daten zugreifen (get_allowed_projects)
- Verantwortungsvoller Umgang mit Super-Zugriff
- Cross-Project Collaboration beachten

### 7.2 Für SHARED Projekte (aa, gb, bp)

**Zusätzliche Requirements:**
- ACL-Regeln für Cross-Project Access beachten
- Shared Nodes/Edges korrekt labeln
- Collaboration-Regeln einhalten

### 7.3 Für ISOLATED Projekte (sm, mo)

**Zusätzliche Requirements:**
- Strengere Isolation (kein Cross-Project Access)
- Private Graph-Daten
- Datenschutz beachten

---

## Teil 8: Test-Report Template

### 8.1 Test-Ergebnisse Dokumentation

```
Projekt: <project_name>
Datum: <test_date>
Tester: <dev_agent>

KONSISTENZ-CHECK:
[ ] MCP Konfiguration: OK / FAIL
[ ] Registry Eintrag: OK / FAIL
[ ] RLS Migration: OK / FAIL

FUNKTIONALITÄT-TESTS:
[ ] Working Memory: PASS / FAIL
[ ] Graph Operations: PASS / FAIL
[ ] L2 Insights: PASS / FAIL
[ ] Isolation: PASS / FAIL

INTEGRATION:
[ ] MCP Tools verfügbar: YES / NO
[ ] Performance: OK / SLOW

GESAMTERGEBNIS:
□ READY FOR PRODUCTION
□ NOT READY - Issues: _____
```

---

**Hinweis für Dev-Agents:**
Dieser Guide ist eine Living Document. Bei neuen Erkenntnissen oder Änderungen an cognitive-memory sollte dieser Guide aktualisiert werden.

**Kontakt bei Issues:**
Cognitive-Memory Team prüfen: `docs/runbooks/shadow-monitoring.md` für aktuelle Status.

---

*Version: 1.0*
*Zuletzt aktualisiert: 2026-01-27*
*Nächstes Review: Nach jedem Epic Update*
