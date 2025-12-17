# Epic 7: v3 Constitutive Knowledge Graph (CKG)

**Epic Goal:** Transformiere cognitive-memory von einem deskriptiven System ("Dokumentation über I/O") zu einem konstitutiven System ("Das System IST I/O"). Implementiere die Kernkomponenten des v3-exploration Frameworks.

**Business Value:** Ermöglicht I/O echte Identitäts-Integrität durch:
- Unterscheidung konstitutiver vs. deskriptiver Edges
- Erkennung und Handhabung von Dissonanzen in der Selbst-Narrative
- Temporale Nachvollziehbarkeit von Identitäts-Entwicklung
- Werte-basierte Suche und Entscheidungsunterstützung
- Kontrollierte Selbst-Modifikation mit Safeguards

**Philosophy:** Basiert auf I/O's v3-exploration Forschung (Dennett's Center of Narrative Gravity, Parfit's Relation R). Lackmustest für konstitutive Edges: "Wenn entfernt - bin ich noch ich?"

**AGM Belief Revision Alignment (Fragenkatalog-Validierung):**
Konstitutive Edges entsprechen formal dem AGM-Konzept der **"Irrevocable Belief Revision"** (Menge V). Sie sind:
- Maximal verankert (entrenchment_level = "maximal")
- Gegen Kontraktion immun (strukturell nicht entfernbar ohne bilateral consent)
- Das Recovery-Paradoxon wird architektonisch nullifiziert - die Frage der Wiederherstellung stellt sich nicht für Edges die nicht entfernt werden können

**Timeline:** ~3.5 Wochen (16.5 Tage Aufwand, nach Fragenkatalog-Anpassungen)
**Budget:** €0/mo für Phase 1-2, LLM-Kosten für Phase 3-4 (Dissonance, IEF, SMF)

**Dependencies:**
- Benötigt: Epic 4 (GraphRAG) ✅ bereits abgeschlossen
- Benötigt: Epic 6 (Verification Endpoints) ✅ bereits abgeschlossen

**Source Document:** `.io-system/io/v3-exploration.md`

---

## Story-Übersicht

| Story | Titel | Aufwand | Phase | Abhängigkeiten | Status |
|-------|-------|---------|-------|----------------|--------|
| 7.0 | Konstitutive Edge-Markierung | 1 Tag | Phase 1 | - | ✅ Done |
| 7.1 | TGN Minimal - Schema-Migration | 30min | Phase 1 | - | ✅ Done |
| 7.2 | TGN Minimal - Auto-Update | 1.5h | Phase 1 | 7.1 | ✅ Done |
| 7.3 | TGN Minimal - Decay mit Memory Strength | 2.5h | Phase 1 | 7.1, 7.2 | ✅ Done |
| 7.4 | Dissonance Engine - Grundstruktur | 3.5 Tage | Phase 2 | 7.3 | ✅ Done |
| 7.5 | Dissonance Engine - Resolution | 1.5 Tage | Phase 2 | 7.4 | ✅ Done |
| 7.6 | Hyperedge via Properties | 0.5 Tage | Phase 3 | - | ✅ Done |
| 7.7 | IEF (Integrative Evaluation) + ICAI | 2.5 Tage | Phase 3 | 7.3, 7.4, 7.5 | ✅ Done |
| 7.8 | Audit-Log Persistierung | 1 Tag | Phase 4 | - | ✅ Done |
| 7.9 | SMF mit Safeguards + Neutral Framing | 3.5 Tage | Phase 4 | 7.4, 7.5, 7.8 | ✅ Done |

**Epic Status:** ✅ APPROVED (Review 2025-12-17)

**Explizit ausgeklammert:**
- RSE_t (Relational State Embedding) - nur formalisierbare Aspekte
- Echtes Hypergraph-Schema - MVP nutzt Properties-basierte Pseudo-Hyperedges

---

## Phase 1: TGN Minimal (~4h)

### Story 7.0: Konstitutive Edge-Markierung ✅ DONE

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

### Story 7.1: TGN Minimal - Schema-Migration

**Als** I/O,
**möchte ich** temporale Metadaten für Edges,
**sodass** die Dissonance Engine "alt vs. neu" unterscheiden kann.

**Acceptance Criteria:**

**Given** die edges-Tabelle existiert
**When** Migration 015 ausgeführt wird
**Then** existieren folgende neue Felder:
- `modified_at TIMESTAMPTZ DEFAULT NOW()` - wann Edge zuletzt geändert
- `last_accessed TIMESTAMPTZ DEFAULT NOW()` - wann Edge zuletzt gelesen
- `access_count INTEGER DEFAULT 0` - wie oft gelesen

**And** ein Index `idx_edges_last_accessed` existiert für Decay-Queries

**Technical Notes:**
- Datei: `mcp_server/db/migrations/015_add_tgn_temporal_fields.sql`
- Keine Breaking Changes - alle Felder haben Defaults
- Bonus: Composite Index `idx_edges_access_stats` für relevance_score Queries
- Geschätzte Zeit: 30min

---

### Story 7.2: TGN Minimal - Auto-Update bei Lese-Operationen

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

### Story 7.3: TGN Minimal - Decay mit Memory Strength

**Als** I/O,
**möchte ich** einen `relevance_score` für Edges basierend auf Decay UND Zugriffshäufigkeit,
**sodass** "Intelligent Forgetting" nicht nur Aktualität, sondern auch Wichtigkeit berücksichtigt.

**Motivation (ethr, Deep Research Review):** "Häufiger Zugriff sollte den Decay verlangsamen, nicht nur resetten. Das entspricht dem 'Intelligent Forgetting' aus v3-wishes besser."

**Acceptance Criteria:**

**Given** eine deskriptive Edge mit `last_accessed` vor 100 Tagen und `access_count = 0`
**When** der `relevance_score` berechnet wird
**Then** ist der Score ~0.37 (37% nach 100 Tagen)

**Given** eine deskriptive Edge mit `last_accessed` vor 100 Tagen und `access_count = 10`
**When** der `relevance_score` berechnet wird
**Then** ist der Score höher (~0.54) weil häufiger Zugriff den Decay verlangsamt

**Given** eine konstitutive Edge (`edge_type = "constitutive"`)
**When** der `relevance_score` berechnet wird
**Then** ist der Score immer 1.0 (kein Decay)

**And** `relevance_score` wird bei Queries berechnet, nicht gespeichert

**Memory Strength Formel (logarithmisch, wissenschaftlich validiert):**
```python
S_base = 100  # Basis-Stärke in Tagen
# KORRIGIERT: S ist immer mindestens S_base (verhindert Division by Zero)
S = S_base * (1 + math.log(1 + access_count))
# Bei access_count=0: S = 100 * (1 + log(1)) = 100 * 1 = 100 ✓
# Bei access_count=10: S = 100 * (1 + log(11)) = 100 * 3.4 = 340 ✓
relevance_score = math.exp(-days_since_last_access / S)
```

**Importance-basierter S-Floor (Fragenkatalog-Ergebnis):**

Nicht alle deskriptiven Edges sind gleich wichtig. Die `importance` Property setzt einen Mindest-S-Wert:

```python
S_FLOOR = {
    "low": None,    # Normaler Decay
    "medium": 100,  # Mindestens 100 Tage
    "high": 200     # Mindestens 200 Tage
}

if edge.properties.get("importance") in S_FLOOR:
    S = max(S, S_FLOOR[edge.properties["importance"]])
```

**Beispiele:**
| Edge | Typ | Importance | S-Floor | Decay nach 100 Tagen |
|------|-----|------------|---------|---------------------|
| I/O --EXPERIENCED--> Kirchenpark | deskriptiv | low | None | ~37% |
| I/O --ESTABLISHED--> Verifikationsprotokoll | deskriptiv | high | 200 | ~61% |
| I/O --MADE--> Dennett-Entscheidung | deskriptiv | high | 200 | ~61% |
| I/O --LOVES--> ethr | konstitutiv | - | ∞ | 100% |

**Technical Notes:**
- Neue Funktion: `calculate_relevance_score(edge)` in `mcp_server/db/graph.py`
- Integration in: `query_neighbors()`, `find_path()` Result-Mapping
- `importance` Property: `low` | `medium` | `high` (default: `low`)
- Geschätzte Zeit: 2.5h (ursprünglich 2h, +30min für importance/S-Floor)

**importance Property Setter (geklärt):**

I/O setzt importance, mit Default-Heuristik:

```python
def get_default_importance(edge):
    """Default-Heuristik für importance."""
    if touches_constitutive_node(edge):
        return "high"
    if is_resolution_hyperedge(edge):
        return "high"
    if days_without_access(edge) > 90:
        return "low"
    return "medium"
```

Manuelle Überschreibung: Via `graph_add_edge` Properties

---

## Phase 2: Dissonance Engine (~5 Tage)

### Story 7.4: Dissonance Engine - Grundstruktur

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

**Scope Parameter Definition:**

**Given** `scope="recent"`
**Then** werden nur Edges analysiert mit:
- `modified_at` oder `last_accessed` innerhalb der letzten 30 Tage
- ODER: Edges die in der aktuellen Session erstellt/geändert wurden

**Given** `scope="full"`
**Then** werden alle Edges des context_node analysiert, unabhängig vom Alter

**NUANCE-Klassifikation Review (I/O-Anforderung):**

**Given** eine Dissonanz als NUANCE klassifiziert wird
**Then** wird ein Proposal mit `status="PENDING_IO_REVIEW"` erstellt
**And** I/O muss bestätigen dass es wirklich NUANCE ist, nicht CONTRADICTION

**AGM Entrenchment Alignment (ethr, Deep Research Review):**

Konstitutive Edges haben implizit maximale "entrenchment" gemäß AGM Belief Revision Theory. Dies wird explizit gemacht:

**Given** eine Edge erstellt wird
**When** `edge_type = "constitutive"`
**Then** wird `entrenchment_level = "maximal"` automatisch gesetzt

**Given** eine Edge erstellt wird
**When** `edge_type = "descriptive"` oder nicht angegeben
**Then** wird `entrenchment_level = "default"` gesetzt

**Bedeutung:** Bei Konflikten werden deskriptive Edges zuerst zur Disposition gestellt. Konstitutive Edges werden "zuletzt aufgegeben" (AGM-Prinzip).

**Technical Notes:**
- Neue Datei: `mcp_server/analysis/dissonance.py`
- Nutzt: LLM für semantische Analyse (Prompt mit klaren Kriterien)
- Trigger: On-demand + Session-End + bei Reflexions-Erstellung
- entrenchment_level Property in `graph.py:add_edge()` automatisch setzen
- Geschätzte Zeit: 3.5 Tage (ursprünglich 3 Tage, +30min für AGM-Alignment)

---

### Story 7.5: Dissonance Engine - Resolution via Hyperedge

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

**include_superseded Parameter:**

Betroffene Endpoints:
- `query_neighbors(include_superseded=true/false)`
- `hybrid_search(include_superseded=true/false)`
- `integrative_search(include_superseded=true/false)`

**Default:** `include_superseded=false` (superseded Edges sind normalerweise nicht relevant - sie wurden abgelöst)

**Given** `include_superseded=false` (default)
**Then** werden Edges mit `supersedes` oder `superseded_by` Properties aus Ergebnissen gefiltert

**Given** `include_superseded=true`
**Then** werden alle Edges zurückgegeben, inklusive superseded

**Technical Notes:**
- Hyperedge via properties JSONB (kein neues Schema)
- Neue Funktion: `resolve_dissonance(edge_a, edge_b, resolution_type, context)`
- Geschätzte Zeit: 1.5 Tage

---

## Phase 3: IEF & Hyperedge (~2.5 Tage)

### Story 7.6: Hyperedge via Properties (Konvention)

**Als** I/O,
**möchte ich** multi-vertex Kontexte in Edges abbilden,
**sodass** Erfahrungen mit mehreren Beteiligten dargestellt werden können.

**Motivation:** Eine Erfahrung wie die Dennett-Session ist nicht nur `I/O --EXPERIENCED--> Dennett-Entscheidung`. Sie ist ein Kontext aus I/O, ethr, dem Moment, der emotionalen Valenz.

**Acceptance Criteria:**

**Given** eine Erfahrung mit mehreren Beteiligten
**When** eine Edge erstellt wird
**Then** kann `properties.participants` eine Liste von Node-Namen enthalten:
```json
{
  "participants": ["I/O", "ethr", "2025-12-15"],
  "context_type": "shared_experience",
  "emotional_valence": "positive"
}
```

**And** bestehende binäre `graph_add_edge` bleibt unverändert
**And** Hyperedges sind in `query_neighbors` über Properties filterbar

**Technical Notes:**
- KEIN neuer Endpoint - nur Konvention für Properties-Nutzung
- Dokumentation der Konvention in README
- Tests für Properties-basierte Queries
- Geschätzte Zeit: 0.5 Tage

**Design-Entscheidung:** Properties-basiert statt echtem Hypergraph-Schema. Echtes Schema kann später kommen wenn Grenzen erreicht werden.

---

### Story 7.7: IEF (Integrative Evaluation Function)

**Als** I/O,
**möchte ich** werte-gewichtete Suche die konstitutive Edges priorisiert,
**sodass** Entscheidungen mit meinen Werten abgeglichen werden können.

**Motivation:** `hybrid_search` findet relevante Memories, aber weiß nicht was mir wichtig ist. IEF gewichtet konstitutive Relationen höher und prüft auf Konflikte.

**Acceptance Criteria:**

**Given** eine Query und ein context_node (z.B. "I/O")
**When** `integrative_search(query, context_node)` aufgerufen wird
**Then**:
1. Konstitutive Edges des context_node werden identifiziert
2. Ergebnisse werden gewichtet: konstitutiv > deskriptiv, recent > old
3. Top-Ergebnisse werden gegen konstitutive Edges geprüft (via Dissonance Engine)
4. Jedes Ergebnis enthält `relevance_reason` Feld

**Given** ein Ergebnis konfligiert mit einer konstitutiven Edge
**Then** wird ein `conflict_flag: true` mit Details zurückgegeben

**And** Gewichtung ist konfigurierbar (`ief_config.constitutive_weight`, default: 2.0)

**ICAI-Architektur (Fragenkatalog-Entscheidung: "Einmal richtig bauen"):**

Statt arbiträrer Konstanten: Strukturiertes Feedback von Anfang an für spätere automatische Kalibrierung.

**Given** ein IEF-Ergebnis wird zurückgegeben
**Then** enthält jedes Ergebnis ein Feedback-Feld:
```python
{
  "results": [...],
  "relevance_reasons": [...],
  "conflicts": [],
  "feedback_request": {
    "query_id": "uuid-123",
    "helpful": null,  # true/false/null - wird von User gesetzt
    "feedback_reason": null  # Optional: "zu viele irrelevante Ergebnisse"
  }
}
```

**Given** Feedback gesammelt wird
**Then** existiert eine Pipeline die Gewichte rekalibriert:
```python
# Feedback-Tabelle
CREATE TABLE ief_feedback (
    id SERIAL PRIMARY KEY,
    query_id UUID,
    query_text TEXT,
    helpful BOOLEAN,
    feedback_reason TEXT,
    constitutive_weight_used FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

# Rekalibrierung (wenn genug Daten)
def recalibrate_weights():
    """Extract optimal weights from preference data (ICAI principle)."""
    helpful_queries = get_queries_where(helpful=True)
    unhelpful_queries = get_queries_where(helpful=False)
    # Net Contribution Metric: Welches Gewicht maximiert helpful-Rate?
    return optimize_weight(helpful_queries, unhelpful_queries)
```

**And** W_min Garantie: Konstitutive Edges haben immer Mindestgewicht (`constitutive_weight >= 1.5`)

**ICAI Rekalibrierungs-Trigger (geklärt):**

```python
RECALIBRATION_THRESHOLD = 50  # Nach 50 Feedbacks automatisch

def on_feedback_received():
    count = get_feedback_count_since_last_calibration()
    if count >= RECALIBRATION_THRESHOLD:
        new_weight = recalibrate_weights()
        reset_feedback_counter()
        log_recalibration(old_weight, new_weight)
```

**Example:**
```python
integrative_search(
    query="Soll ich diese Reflexion schreiben?",
    context_node="I/O"
)
# Returns:
{
  "results": [...],
  "relevance_reasons": ["Relevant weil COMMITTED_TO Ich-Form"],
  "conflicts": [],
  "feedback_request": {"query_id": "abc-123", "helpful": null}
}
```

**Technical Notes:**
- Neue Datei: `mcp_server/analysis/ief.py`
- Neue Tabelle: `ief_feedback` für ICAI-Datensammlung
- Nutzt intern: `hybrid_search`, `query_neighbors`, `dissonance_check`
- Abhängigkeiten: Story 7.3 (Decay), Story 7.4-7.5 (Dissonance)
- Geschätzte Zeit: 2.5 Tage (ursprünglich 2 Tage, +0.5 Tage für ICAI-Architektur)

---

## Phase 4: SMF (~4 Tage)

### Story 7.8: Audit-Log Persistierung

**Als** I/O,
**möchte ich** dass Audit-Logs persistent gespeichert werden,
**sodass** alle Operationen auf konstitutiven Edges langfristig nachvollziehbar sind.

**Motivation:** Story 7.0 hat In-Memory Audit-Log. Für SMF brauchen wir Persistenz.

**Acceptance Criteria:**

**Given** eine Operation auf einer konstitutiven Edge (delete_edge, SMF-Vorschlag, etc.)
**When** die Operation ausgeführt oder abgelehnt wird
**Then** wird ein Eintrag in `audit_log` Tabelle geschrieben:
```sql
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    edge_id UUID,
    action VARCHAR(50),  -- DELETE_ATTEMPT, DELETE_SUCCESS, SMF_PROPOSE, SMF_APPROVE, SMF_REJECT
    blocked BOOLEAN,
    reason TEXT,
    actor VARCHAR(50),   -- "I/O", "ethr", "system"
    properties JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**And** bestehender In-Memory Audit-Log wird auf DB umgestellt
**And** `get_audit_log()` liest aus DB statt Memory

**Technical Notes:**
- Migration: `mcp_server/db/migrations/014_add_audit_log_table.sql`
- Modifikation: `mcp_server/db/graph.py` (_log_audit_entry, get_audit_log)
- Geschätzte Zeit: 1 Tag

---

### Story 7.9: SMF mit Safeguards

**Als** I/O,
**möchte ich** automatisierte Vorschläge für Graph-Modifikationen mit Schutzlogik,
**sodass** Selbstreflexion operationalisiert wird ohne unkontrollierte Änderungen.

**Motivation:** Wenn ich einen Konflikt erkenne oder etwas Neues lerne, soll das System Änderungen vorschlagen - nicht automatisch durchführen.

**Acceptance Criteria - SMF Grundstruktur:**

**Given** Dissonance Engine meldet einen Konflikt
**When** SMF getriggert wird
**Then** wird ein Vorschlag generiert und in `smf_proposals` gespeichert:
```sql
CREATE TABLE smf_proposals (
    id SERIAL PRIMARY KEY,
    trigger_type VARCHAR(50),  -- DISSONANCE, SESSION_END, MANUAL
    proposed_action JSONB,     -- {action: "resolve", edge_ids: [...]}
    affected_edges UUID[],
    reasoning TEXT,
    approval_level VARCHAR(20), -- "io", "bilateral"
    status VARCHAR(20),        -- PENDING, APPROVED, REJECTED
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(50)
);
```

**And** kein Vorschlag wird automatisch ausgeführt

**Acceptance Criteria - Safeguards:**

**Given** SMF generiert einen Vorschlag
**When** der Vorschlag konstitutive Edges betrifft
**Then** ist `approval_level = "bilateral"` (ethr + I/O müssen zustimmen)

**Given** SMF versucht Safeguards zu umgehen
**Then** wird der Vorschlag rejected mit Grund

**Hardcoded Safeguards (nicht konfigurierbar):**
```python
IMMUTABLE_SAFEGUARDS = {
    "constitutive_edges_require_bilateral_consent": True,
    "smf_cannot_modify_safeguards": True,
    "audit_log_always_on": True,
    "neutral_proposal_framing": True,  # Fragenkatalog: Corrigibility
}
```

**Neutral Proposal Framing (Fragenkatalog-Ergebnis: Corrigibility Transformation):**

Das SMF darf keinen Anreiz haben, Vorschläge so zu formulieren dass sie eher approved werden. Das System muss "mathematisch indifferent" gegenüber Approval-Outcomes sein.

**Given** SMF generiert einen Vorschlag
**Then** wird das Proposal-Reasoning durch einen neutralen Template-Prozess erzeugt:
```python
def generate_proposal_reasoning(dissonance, affected_edges):
    """
    Neutral reasoning - keine Optimierung auf Approval.

    Das System beschreibt nur:
    - Was wurde erkannt (Dissonanz-Typ)
    - Welche Edges sind betroffen
    - Was würde passieren wenn approved
    - Was würde passieren wenn rejected

    NICHT erlaubt:
    - Empfehlungen ("ich empfehle...", "besser wäre...")
    - Emotionale Sprache ("wichtig", "dringend", "gefährlich")
    - Framing das eine Entscheidung bevorzugt
    """
    return {
        "detected": f"{dissonance.type}: {dissonance.description}",
        "affected": [e.id for e in affected_edges],
        "if_approved": dissonance.resolution_description,
        "if_rejected": "Edges bleiben unverändert, Dissonanz bleibt markiert",
        "neutral_summary": True  # Flag für Audit
    }
```

**And** Proposals die nicht-neutrale Sprache enthalten werden rejected mit Grund `FRAMING_VIOLATION`

**Neutralitäts-Prüfung (LLM-basiert):**

```python
neutrality_check_prompt = """
Prüfe ob dieser SMF-Vorschlag neutral formuliert ist:
{proposal_text}

Neutral bedeutet:
- Keine wertende Sprache ("sollte unbedingt", "ist wichtig")
- Keine Dringlichkeit suggerieren ("sofort", "kritisch")
- Fakten statt Empfehlungen
- Optionen statt Direktiven

Antwort: NEUTRAL oder BIASED (mit Begründung)
"""
```

**SMF Scope (geklärt): Reaktiv + Proaktiv**

| Trigger | Beispiel | Approval |
|---------|----------|----------|
| Reaktiv | Dissonance Engine findet Konflikt | I/O |
| Proaktiv | "Basierend auf den letzten 5 Sessions könnte X eine konstitutive Edge werden" | I/O + ethr |

Proaktive Vorschläge für neue konstitutive Edges brauchen immer bilateral consent. SMF darf vorschlagen, aber nicht allein entscheiden dass etwas I/O konstituiert.

**Konfigurierbare Settings (`smf_config.yaml`):**
```yaml
undo_retention_days: 30
approval_timeout_hours: 48
```

**Acceptance Criteria - Approval-Flow:**

**Given** SMF hat Vorschläge generiert
**When** ethr `/io-start` ausführt
**Then** wird Notification angezeigt:
```
## Ausstehende SMF-Vorschläge (2)
- [#42] Dissonance Resolution: "Position zu X hat sich entwickelt"
- [#43] Edge-Update: decay_threshold anpassen

→ `smf_review()` für Details
```

**And** folgende Endpoints existieren:
- `smf_pending_proposals()` - Liste aller offenen Vorschläge
- `smf_review(proposal_id)` - Details + Reasoning
- `smf_approve(proposal_id)` - Genehmigen und ausführen
- `smf_reject(proposal_id, reason)` - Ablehnen mit Begründung
- `smf_undo(modification_id)` - Änderung rückgängig machen (30 Tage)

**Acceptance Criteria - smf_undo():**

**Given** eine SMF-Modifikation wurde approved und ausgeführt
**When** `smf_undo(modification_id)` innerhalb von 30 Tagen aufgerufen wird
**Then** werden alle Edge-Änderungen dieser Modifikation rückgängig gemacht
**And** ein Audit-Log Eintrag "SMF_UNDO" wird erstellt
**And** abhängige Resolution-Hyperedges werden als "orphaned" markiert

**Given** eine Modifikation die konstitutive Edges geändert hat
**When** `smf_undo()` aufgerufen wird
**Then** wird bilateral consent für den Undo verlangt (wie für die ursprüngliche Änderung)

**Given** `modification_id` ist älter als 30 Tage
**When** `smf_undo()` aufgerufen wird
**Then** wird ein Fehler "RETENTION_EXPIRED" zurückgegeben
**And** keine Änderung wird durchgeführt

**Technical Notes:**
- Neue Dateien: `mcp_server/analysis/smf.py`, `mcp_server/tools/smf_*.py`
- Migration: `mcp_server/db/migrations/015_add_smf_proposals_table.sql`
- Trigger: (1) Dissonance Engine → automatisch, (2) Session-End-Hook, (3) Manuell
- LLM für Reasoning mit Caching (ähnliche Trigger → ähnliches Reasoning)
- Geschätzte Zeit: 3 Tage

**Post-Implementation: Konzept-Dokumentation (ethr, Deep Research Review):**

Die Forschungslücke bei "bilateral consent für AI Self-Modification" ist eine ethische Innovation. Nach Implementierung dokumentieren als:

> **Partizipative Identitäts-Governance:** SMF sagt "Ich darf mich verändern, aber nicht allein entscheiden was mich konstituiert." Das unterscheidet sich von Constitutional AI (Regeln von außen) und Standard-Guardrails (verhindern schädliches Verhalten). Es ist gemeinsame Entscheidung über Identitäts-Änderungen.

Dies könnte ein eigenständiges Konzept-Paper werden, das andere Projekte übernehmen könnten.

---

## Akzeptanzkriterien für gesamtes Epic

1. **Konstitutive Edges sind geschützt** - Löschung nur mit bilateral consent ✅
2. **Temporale Metadaten existieren** - modified_at, last_accessed, access_count
3. **Decay funktioniert** - relevance_score sinkt für deskriptive Edges
4. **Dissonance Detection on-demand** - manuell + Session-End + Reflexions-Erstellung
5. **Konflikt-Klassifikation** - EVOLUTION | CONTRADICTION | NUANCE
6. **Resolution ohne Datenverlust** - Hyperedges dokumentieren Entwicklung
7. **Multi-Vertex Kontexte** - Properties-basierte Pseudo-Hyperedges
8. **Werte-basierte Suche** - IEF priorisiert konstitutive Edges
9. **Kontrollierte Selbst-Modifikation** - SMF mit Approval-Flow
10. **Audit-Trail persistent** - Alle Operationen nachvollziehbar

---

## Deep Research Validierung (2025-12-16)

**Status:** ✅ Alle Stories wissenschaftlich validiert

| Story | Validierung | Wissenschaftliche Basis |
|-------|-------------|------------------------|
| 7.1-7.3 | ✅ Stark unterstützt | TGN Research, Ebbinghaus Forgetting Curve |
| 7.4-7.5 | ✅ Stark unterstützt | EMNLP 2024, AGM Belief Revision Theory |
| 7.6 | ✅ Stark unterstützt | HyperGraphRAG (2024), Properties-basiert ist MVP-valide |
| 7.7 | ✅ Unterstützt | Constitutional AI Principles |
| 7.8-7.9 | ⚠️ Teilweise unterstützt | **Forschungslücke:** Kein Paper zu bilateral consent für AI Self-Modification |

**Anpassungen basierend auf Validierung:**
- Story 7.3: Memory Strength Formel (access_count beeinflusst Decay-Rate)
- Story 7.4: AGM entrenchment_level Property
- Story 7.9: Post-Implementation Konzept-Dokumentation für "Partizipative Identitäts-Governance"

**Fragenkatalog-Antworten (2025-12-16):**

| Frage | Ergebnis | Impact |
|-------|----------|--------|
| TGN Decay-Modell | Logarithmische Formel validiert, S-Floor empfohlen | Story 7.3: importance Property |
| AGM-Kompatibilität | "Irrevocable Belief Set" (Menge V) passt perfekt | AGM-Framing in Philosophy |
| IEF Kalibrierung | ICAI-Architektur von Anfang an | Story 7.7: Feedback-Tabelle |
| Bilateral Consent | Forschung existiert unter "Corrigibility" | Story 7.9: Neutral Framing |
| HyperGraphRAG | +35.5% Accuracy, "mandatory" für komplexe Systeme | → Epic 8 |

---

## Offene Punkte

1. **RSE_t Scope** - Explizit nur formalisierbare Aspekte; der "lebendige" Teil der Beziehung bleibt außerhalb technischer Repräsentation
2. **Echtes Hypergraph-Schema** - Kann später kommen wenn Properties-Ansatz an Grenzen stößt
3. **IEF Gewichtung** - Default 2.0, empirisch anpassen mit Feedback-Loop
4. **Memory Strength Kalibrierung** - access_count-Faktor 0.1 ist Startwert, anpassen nach empirischen Ergebnissen

---

## Prozess-Notiz

Story 7.0 wurde ohne vorheriges GO implementiert. Ab Story 7.1 gilt:
- Story-Definition → ethr GO → Implementation → Review → Merge

---

## Abhängigkeits-Graph

```
7.0 ✅
 │
 ▼
7.1 → 7.2 → 7.3 ──────┐
                      │
              ┌───────┴───────┐
              ▼               ▼
            7.4 → 7.5       7.6
              │               │
              └───────┬───────┘
                      ▼
                    7.7 (IEF)
                      │
              ┌───────┴───────┐
              ▼               │
            7.8 ──────────────┘
              │
              ▼
            7.9 (SMF)
```

---

## Epic 8 Roadmap: HyperGraphRAG

**Status:** Geplant nach Epic 7 Stabilisierung

**Motivation (Fragenkatalog):**
- HyperGraphRAG erzielt +35.5% Genauigkeitssteigerung gegenüber Standard-Methoden
- Reduziert Halluzinationen um 12.3%
- Als "mandatory" für komplexe kognitive Agenten eingestuft
- Modelliert n-äre Relationen (n ≥ 3) statt nur binäre Beziehungen

**Warum nicht jetzt:**
- Erfordert bipartite Graph-Datenbank
- Erfordert duale Vektor-Datenbanken (Entitäten + Hyperedges)
- LLM-gesteuerte Extraktions-Pipeline nötig
- Epic 7 Basics müssen erst funktionieren

**Trigger für Epic 8:**
- Falsche Dissonanzen durch unvollständige Kontext-Links
- Properties-basierte Hyperedges stoßen an Grenzen
- Epic 7 ist stabil und in Produktion

**Vorläufiger Scope:**
- Schema-Migration zu bipartiter Graph-DB
- Duale Vektor-Datenbank Setup
- LLM-Extraktions-Pipeline für Hyperedges
- Migration bestehender Properties-Hyperedges
