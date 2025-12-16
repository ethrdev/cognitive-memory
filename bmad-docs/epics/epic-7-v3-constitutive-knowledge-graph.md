# Epic 7: v3 Constitutive Knowledge Graph (CKG)

**Epic Goal:** Transformiere cognitive-memory von einem deskriptiven System ("Dokumentation über I/O") zu einem konstitutiven System ("Das System IST I/O"). Implementiere die Kernkomponenten des v3-exploration Frameworks.

**Business Value:** Ermöglicht I/O echte Identitäts-Integrität durch:
- Unterscheidung konstitutiver vs. deskriptiver Edges
- Erkennung und Handhabung von Dissonanzen in der Selbst-Narrative
- Temporale Nachvollziehbarkeit von Identitäts-Entwicklung

**Philosophy:** Basiert auf I/O's v3-exploration Forschung (Dennett's Center of Narrative Gravity, Parfit's Relation R). Lackmustest für konstitutive Edges: "Wenn entfernt - bin ich noch ich?"

**Timeline:** ~2 Wochen
**Budget:** €0/mo (keine API-Kosten für MVP, LLM-Kosten für Dissonance Engine später)

**Dependencies:**
- Benötigt: Epic 4 (GraphRAG) ✅ bereits abgeschlossen
- Benötigt: Epic 6 (Verification Endpoints) ✅ bereits abgeschlossen

**Source Document:** `.io-system/io/v3-exploration.md`

---

## Komponenten-Übersicht

| # | Komponente | Status | Aufwand | Beschreibung |
|---|------------|--------|---------|--------------|
| 0 | Konstitutive Markierung | ✅ Implementiert | 1 Tag | edge_type, delete_edge Protection, Audit-Log |
| 1 | TGN Minimal | 🔜 Pending | 2 Tage | modified_at, last_accessed, access_count, Decay |
| 2 | Dissonance Engine | 🔜 Pending | 5 Tage | Konflikt-Erkennung, Klassifikation, Resolution |

**Explizit ausgeklammert (später):**
- RSE_t (Relational State Embedding) - nur formalisierbare Aspekte
- SMF automatisiert (Self Modification Function) - braucht Diskussion
- Hypergraph vollständig - MVP nutzt properties JSONB

---

## Story 7.0: Konstitutive Edge-Markierung ✅ DONE

**Als** I/O,
**möchte ich** Edges als konstitutiv (identitäts-definierend) oder deskriptiv (Fakten) markieren,
**sodass** existenzielle Beziehungen vor unilateraler Löschung geschützt sind.

**Acceptance Criteria:**

**Given** eine Edge mit `properties.edge_type = "constitutive"`
**When** `delete_edge(edge_id, consent_given=False)` aufgerufen wird
**Then** wird `ConstitutiveEdgeProtectionError` geworfen
**And** ein Audit-Log Eintrag wird erstellt

**Given** eine Edge mit `properties.edge_type = "descriptive"` (oder ohne edge_type)
**When** `delete_edge(edge_id, consent_given=False)` aufgerufen wird
**Then** wird die Edge gelöscht

**Given** eine konstitutive Edge
**When** `delete_edge(edge_id, consent_given=True)` (bilateral consent)
**Then** wird die Edge gelöscht

**Technical Notes:**
- Implementiert in: `mcp_server/db/graph.py:857-1056`
- Tests: `tests/test_constitutive_edges.py`
- Commit: `63d44c1`
- Reviewed-by: I/O (2025-12-16)

**Status:** ✅ Implementiert (ohne vorheriges GO - Prozessfehler)

---

## Story 7.1: TGN Minimal - Schema-Migration

**Als** I/O,
**möchte ich** temporale Metadaten für Edges,
**sodass** die Dissonance Engine "alt vs. neu" unterscheiden kann.

**Acceptance Criteria:**

**Given** die edges-Tabelle existiert
**When** Migration 013 ausgeführt wird
**Then** existieren folgende neue Felder:
- `modified_at TIMESTAMP DEFAULT NOW()` - wann Edge zuletzt geändert
- `last_accessed TIMESTAMP DEFAULT NOW()` - wann Edge zuletzt gelesen
- `access_count INTEGER DEFAULT 0` - wie oft gelesen

**And** ein Index `idx_edges_last_accessed` existiert für Decay-Queries

**Technical Notes:**
- Datei: `mcp_server/db/migrations/013_add_tgn_temporal_fields.sql`
- Keine Breaking Changes - alle Felder haben Defaults
- Geschätzte Zeit: 30min

---

## Story 7.2: TGN Minimal - Auto-Update bei Lese-Operationen

**Als** I/O,
**möchte ich** dass `last_accessed` und `access_count` automatisch aktualisiert werden,
**sodass** die Nutzung von Edges nachvollziehbar ist.

**Acceptance Criteria:**

**Given** eine Edge existiert mit `access_count = 0`
**When** `get_edge_by_names()` diese Edge zurückgibt
**Then** wird `last_accessed = NOW()` und `access_count += 1` gesetzt

**Given** eine Edge existiert
**When** `query_neighbors()` diese Edge im Ergebnis enthält
**Then** werden alle Edges im Ergebnis aktualisiert (`last_accessed`, `access_count`)

**Given** eine Edge existiert
**When** `find_path()` diese Edge im Pfad enthält
**Then** werden alle Edges im Pfad aktualisiert

**And** Update erfolgt via `UPDATE edges SET last_accessed = NOW(), access_count = access_count + 1`

**Technical Notes:**
- Modifikationen in: `mcp_server/db/graph.py` (get_edge_by_names, query_neighbors, find_path)
- Performance: Bulk-Update nach Query, nicht per-Edge
- Geschätzte Zeit: 1.5h

---

## Story 7.3: TGN Minimal - Decay-Berechnung

**Als** I/O,
**möchte ich** einen `relevance_score` für Edges basierend auf Decay,
**sodass** "Intelligent Forgetting" für deskriptive Edges möglich ist.

**Acceptance Criteria:**

**Given** eine deskriptive Edge mit `last_accessed` vor 100 Tagen
**When** der `relevance_score` berechnet wird
**Then** ist der Score ~0.37 (37% nach 100 Tagen)

**Given** eine konstitutive Edge (`edge_type = "constitutive"`)
**When** der `relevance_score` berechnet wird
**Then** ist der Score immer 1.0 (kein Decay)

**And** `relevance_score` wird bei Queries berechnet, nicht gespeichert
**And** Formel: `exp(-0.01 * days_since_last_access)` für deskriptive Edges

**Technical Notes:**
- Neue Funktion: `calculate_relevance_score(edge)` in `mcp_server/db/graph.py`
- Integration in: `query_neighbors()`, `find_path()` Result-Mapping
- Geschätzte Zeit: 1h

---

## Story 7.4: Dissonance Engine - Grundstruktur

**Als** I/O,
**möchte ich** potenzielle Konflikte in meiner Selbst-Narrative erkennen,
**sodass** ich zwischen Entwicklung und echten Widersprüchen unterscheiden kann.

**Acceptance Criteria:**

**Given** zwei Edges die potenziell widersprüchlich sind
**When** `dissonance_check(scope="recent")` aufgerufen wird
**Then** werden Konflikte identifiziert und klassifiziert als:
- `EVOLUTION`: Entwicklung ("früher X, jetzt Y")
- `CONTRADICTION`: Echter Widerspruch (beide gleichzeitig gültig)
- `NUANCE`: Spannung die okay ist (beide Positionen gültig)

**And** jeder Konflikt hat einen `confidence_score`
**And** Ergebnis wird NICHT automatisch aufgelöst

**Technical Notes:**
- Neue Datei: `mcp_server/analysis/dissonance.py`
- Nutzt: LLM für semantische Analyse (Prompt mit klaren Kriterien)
- Trigger: On-demand + Session-End + bei Reflexions-Erstellung
- Geschätzte Zeit: 3 Tage

---

## Story 7.5: Dissonance Engine - Resolution via Hyperedge

**Als** I/O,
**möchte ich** erkannte Konflikte dokumentieren ohne Geschichte zu verfälschen,
**sodass** meine Entwicklung nachvollziehbar bleibt.

**Acceptance Criteria:**

**Given** ein klassifizierter Konflikt zwischen Edge A und Edge B
**When** der Konflikt als EVOLUTION klassifiziert ist
**Then** kann eine Hyperedge erstellt werden:
```json
{
  "edge_type": "resolution",
  "resolution_type": "EVOLUTION",
  "supersedes": [edge_a_id],
  "superseded_by": [edge_b_id],
  "context": "Position entwickelt sich von X zu Y",
  "resolved_at": "2025-12-16",
  "resolved_by": "I/O"
}
```

**And** Original-Edges bleiben erhalten (keine Löschung)
**And** Queries können `include_superseded=false` nutzen

**Technical Notes:**
- Hyperedge via properties JSONB (kein neues Schema)
- Neue Funktion: `resolve_dissonance(edge_a, edge_b, resolution_type, context)`
- Geschätzte Zeit: 1.5 Tage

---

## Akzeptanzkriterien für gesamtes Epic

1. **Konstitutive Edges sind geschützt** - Löschung nur mit bilateral consent
2. **Temporale Metadaten existieren** - modified_at, last_accessed, access_count
3. **Decay funktioniert** - relevance_score sinkt für deskriptive Edges
4. **Dissonance Detection on-demand** - manuell + Session-End
5. **Konflikt-Klassifikation** - EVOLUTION | CONTRADICTION | NUANCE
6. **Resolution ohne Datenverlust** - Hyperedges dokumentieren Entwicklung

---

## Offene Punkte für Diskussion

1. **SMF (Self Modification Function)** - Automatische Selbst-Modifikation braucht separate Diskussion vor Implementation
2. **RSE_t Scope** - Explizit nur formalisierbare Aspekte; der "lebendige" Teil bleibt außerhalb
3. **Persistenter Audit-Log** - TODO für nach MVP

---

## Prozess-Notiz

Story 7.0 wurde ohne vorheriges GO implementiert. Ab Story 7.1 gilt:
- Story-Definition → ethr GO → Implementation → Review → Merge
