# Bug Report: Verwaister `gb` Eintrag in project_registry

**Datum:** 2026-01-27
**Reporter:** Agentic Business Team (Party Mode: Murat/TEA, Amelia/Dev, Winston/Architect)
**Severity:** Low
**Component:** `cognitive-memory` — project_registry Seed Data

---

## Zusammenfassung

Die `project_registry` enthält einen Eintrag `gb` ("Agentic Business", shared), der keinem aktiven Projekt zugeordnet ist. Kein Projekt verwendet `PROJECT_ID: gb` in seiner MCP-Konfiguration. Der korrekte Eintrag für das Agentic-Business-Projekt ist `ab` ("Application Builder", shared).

---

## Kontext

Bei der Diagnose eines MCP-Verbindungsfehlers in `agentic-business` wurde festgestellt:

1. Die ursprüngliche MCP-Config hatte `PROJECT_ID: gb`
2. Die `project_registry` war leer → Verbindung schlug fehl
3. Das CM-Team fügte Seed-Daten hinzu, darunter sowohl `ab` als auch `gb`
4. `ab` wurde explizit für agentic-business angelegt und korrekt konfiguriert
5. `gb` hat keinen aktiven Nutzer und verursachte Verwirrung beim Debugging

## Aktuelle Registry

```
ab: Application Builder (shared)   ← aktiv genutzt von agentic-business
gb: Agentic Business (shared)      ← verwaist, kein Projekt nutzt diese ID
```

## Empfehlung

- `gb` aus der `project_registry` entfernen (oder als deprecated markieren)
- Ggf. zugehörige Einträge in `rls_migration_status` und `project_read_permissions` bereinigen

## Impact

- **Kein Runtime-Impact** — `gb` stört den Betrieb nicht
- **Debugging-Verwirrung** — Der Eintrag führte zu einem falschen Fix-Versuch (gb→ab→gb→ab)
