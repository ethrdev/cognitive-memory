# Session Report: Agentic-Business MCP Connection Diagnosis

**Datum:** 2026-01-27
**Reporter:** Party Mode (Murat/TEA, Amelia/Dev, Winston/Architect)
**Severity:** High → Resolved
**Projekte:** agentic-business ↔ cognitive-memory

---

## Zusammenfassung

Die MCP-Verbindung von `agentic-business` zu `cognitive-memory` schlug fehl. Diagnose ergab zwei zusammenhängende Ursachen: eine leere `project_registry` (vom CM-Team behoben) und eine falsche `PROJECT_ID` in der MCP-Konfiguration.

---

## Chronologie

### 1. Ausgangslage

```
.claude/mcp-settings.json (agentic-business)
→ PROJECT_ID: "gb"
→ Status: ❌ "Failed to reconnect to cognitive-memory"
```

### 2. Erste Diagnose

- **Neon DB** (nicht lokales PostgreSQL) als Datenbank identifiziert
- MCP Server startet manuell erfolgreich (32 Tools, 5 Resources, Pool OK)
- Connection Pool zur Neon DB: ✅ Healthy
- PostgreSQL 17.7 erreichbar: ✅

### 3. CM-Team Parallel-Fix

Das cognitive-memory Team hatte unabhängig das Problem diagnostiziert:

**Root Cause (CM-Team):** Die `project_registry`-Tabelle in der Neon-Produktions-DB war leer.

**Lösung (CM-Team):** Seed-Daten hinzugefügt:

| project_id | name | access_level |
|---|---|---|
| aa | Application Assistant | shared |
| **ab** | **Application Builder** | **shared** |
| bp | BMAD Audit Polish | shared |
| ea | ETHR Assistant | super |
| ec | Echo | super |
| **gb** | **Agentic Business** | **shared** |
| io | I/O System | super |
| mo | Motoko | isolated |
| sm | Semantic Memory | isolated |

Zusätzlich für `ab`:
```sql
INSERT INTO project_read_permissions (reader_project_id, target_project_id)
VALUES ('ab', 'sm');

INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
VALUES ('ab', 'pending', FALSE);
```

### 4. PROJECT_ID Klärung

**Verwirrung:** Sowohl `ab` als auch `gb` existieren in der Registry:
- `ab` = "Application Builder" → vom CM-Team **explizit** für agentic-business angelegt, mit Read-Permissions und RLS-Status
- `gb` = "Agentic Business" → verwaister Eintrag, kein Projekt nutzt diese ID aktiv

**Entscheidung:** `PROJECT_ID: ab` ist korrekt für agentic-business.

### 5. Verbleibender Status

Die MCP-Verbindung konnte in dieser Session nicht validiert werden, da Claude Code die Config nur beim Session-Start liest. Ein Neustart ist erforderlich.

---

## Durchgeführte Änderungen

### Änderung 1: MCP Config (agentic-business)

**Datei:** `agentic-business/.claude/mcp-settings.json`

```json
{
  "mcpServers": {
    "cognitive-memory": {
      "type": "stdio",
      "command": "/home/ethr/01-projects/ai-experiments/cognitive-memory/start_mcp_server.sh",
      "env": {
        "PROJECT_ID": "ab"
      }
    }
  }
}
```

| Feld | Vorher | Nachher | Grund |
|---|---|---|---|
| PROJECT_ID | `gb` | `ab` | CM-Team hat `ab` für agentic-business konfiguriert |

### Änderung 2: Bug Report (cognitive-memory)

**Datei:** `cognitive-memory/docs/bug-reports/2026-01-27-orphaned-gb-registry-entry.md`

Dokumentiert den verwaisten `gb`-Eintrag in der `project_registry` mit Empfehlung zur Bereinigung.

---

## Aktueller Stand

### MCP-Verbindung

| Check | Status | Details |
|---|---|---|
| `.claude/mcp-settings.json` | ✅ Korrekt | `PROJECT_ID: ab`, Pfad zum Start-Script OK |
| `start_mcp_server.sh` | ✅ Executable | Lädt `.env.development`, startet Python MCP Server |
| Neon DB Connection | ✅ Erreichbar | PostgreSQL 17.7, Connection Pool healthy |
| `project_registry` | ✅ `ab` vorhanden | "Application Builder", access_level: shared |
| Read Permissions | ✅ `ab → sm` | Kann Semantic Memory lesen |
| RLS Migration | ⚠️ Pending | Phase: pending, rls_enabled: false |
| MCP Server Start | ✅ Manuell OK | 32 Tools, 5 Resources registriert |
| **Claude Code Session** | ❓ **Neustart nötig** | Config geändert, Session noch nicht neu gestartet |

### Integration Test Guide Status

| Teil | Status | Anmerkung |
|---|---|---|
| Teil 1: Konfiguration | ✅ Geprüft | MCP Config, Registry, Start Script – alles OK |
| Teil 2: Funktionalität | ❓ Ausstehend | Working Memory, Graph, L2 Insights – nach Reconnect |
| Teil 3: Integration | ❓ Ausstehend | Tool-Verfügbarkeit, Performance – nach Reconnect |
| Teil 4: Troubleshooting | ✅ Dokumentiert | Dieser Report |
| Teil 5: Sign-Off | ❓ Ausstehend | Nach Abschluss aller Tests |

### Offene Punkte

1. **Session-Neustart** — Claude Code muss neu gestartet werden, damit `PROJECT_ID: ab` wirksam wird
2. **Integration Tests** — Teil 2-3 des Integration Test Guide nach erfolgreichem Reconnect durchführen
3. **`gb` Bereinigung** — Verwaister Registry-Eintrag sollte entfernt werden (Low Priority)
4. **RLS Migration** — `ab` ist noch in Phase `pending` (ggf. CM-Team informieren)

---

## Server-Technische Details

| Komponente | Version/Detail |
|---|---|
| FastMCP | 3.0.0b1 (Beta) |
| MCP SDK | 1.26.0 |
| Python | System Python via `.venv` |
| PostgreSQL | 17.7 (Neon Cloud) |
| Transport | stdio |
| Region | eu-central-1 (AWS) |

---

## Lessons Learned

1. **Registry vor Config prüfen** — Bei MCP-Verbindungsfehlern immer zuerst `project_registry` abfragen
2. **PROJECT_ID ≠ Projektname** — Abbreviation und Display-Name können unterschiedlich sein
3. **Seed-Daten auditieren** — Verwaiste Einträge (`gb`) verursachen Debugging-Verwirrung
4. **Session-Restart bei Config-Änderungen** — Claude Code cached MCP Config beim Start; `/mcp` Reconnect reicht bei fundamentalen Änderungen nicht

---

*Report erstellt: 2026-01-27 | Party Mode Session*
