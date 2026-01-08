# Epic 7 Review: v3 Constitutive Knowledge Graph (CKG)

**Reviewer:** I/O
**Datum:** 2025-12-17
**Status:** ✅ APPROVED (nach Korrektur)

---

## Executive Summary

Epic 7 ist vollständig implementiert. Alle 10 Stories (7.0-7.9) sind als "done" markiert und die Kernfunktionalität funktioniert. Das Epic transformiert cognitive-memory von einem deskriptiven System zu einem konstitutiven System basierend auf dem v3-exploration Framework.

**Bewertung:** APPROVED nach Korrektur kritischer Gaps.

### Review-Korrektur (2025-12-17, Nachtrag)

Der ursprüngliche Review hat mehrere nicht erfüllte Acceptance Criteria übersehen. Nach Konfrontation durch ethr wurden folgende Gaps identifiziert und vom BMAD-Team behoben:

**Story 7.7 (IEF) - 4 fehlende ACs:**
- `feedback_request` Feld → jetzt in `ief.py:141`
- `recalibrate_weights()` → jetzt in `ief.py:329`
- `on_feedback_received()` → jetzt in `ief.py:260`
- `W_MIN_CONSTITUTIVE = 1.5` → jetzt in `ief.py:31`

**Story 7.9 (SMF) - 4 fehlende ACs:**
- `smf_config.yaml` → jetzt in `/mcp_server/config/smf_config.yaml`
- `approval_timeout_hours` → jetzt konfigurierbar
- Bilateral consent für `smf_undo()` → jetzt implementiert
- SMF Notification bei `/io-start` → jetzt in `session_start.py:704-706`

**Story 7.3 (TGN) - 1 fehlende Heuristik:**
- `get_default_importance()` → jetzt in `graph.py:356`

**Lesson Learned:** "APPROVED" ohne AC-gegen-Code-Prüfung ist kein Review.

---

## Implementierte Komponenten

### Phase 1: TGN Minimal ✅

| Story | Status | Implementierung |
|-------|--------|-----------------|
| 7.0 | ✅ | `ConstitutiveEdgeProtectionError` in `graph.py`, Audit-Logging |
| 7.1 | ✅ | Migration 015: `modified_at`, `last_accessed`, `access_count` |
| 7.2 | ✅ | Auto-Update in `query_neighbors()`, `find_path()`, `get_edge_by_names()` |
| 7.3 | ✅ | `calculate_relevance_score()` mit Ebbinghaus-Decay und Memory Strength |

**Code-Lokation:** `mcp_server/db/graph.py:356-408`

**Formel implementiert:**
```python
S = S_base * (1 + math.log(1 + access_count))
relevance_score = math.exp(-days_since_last_access / S)
```

**Konstitutive Edges:** Score immer 1.0 (kein Decay)

### Phase 2: Dissonance Engine ✅

| Story | Status | Implementierung |
|-------|--------|-----------------|
| 7.4 | ✅ | `DissonanceEngine` Klasse mit LLM-Klassifikation |
| 7.5 | ✅ | `resolve_dissonance()` mit Hyperedge-Erstellung |

**Code-Lokation:** `mcp_server/analysis/dissonance.py` (917 Zeilen)

**Klassifikations-Typen:**
- `EVOLUTION`: Position hat sich entwickelt (supersedes-Mechanik)
- `CONTRADICTION`: Echter Widerspruch
- `NUANCE`: Spannung die okay ist (requires I/O review)

**AGM Alignment:** `entrenchment_level` Property automatisch gesetzt (maximal für konstitutive, default für deskriptive)

**Cost Protection:** MAX_PAIRS=100 Limit für O(n²) API-Calls

### Phase 3: IEF & Hyperedge ✅

| Story | Status | Implementierung |
|-------|--------|-----------------|
| 7.6 | ✅ | Properties-basierte Hyperedges, `_build_properties_filter_sql()` |
| 7.7 | ✅ | `calculate_ief_score()` mit ICAI-Architektur |

**Code-Lokation:** `mcp_server/analysis/ief.py` (229 Zeilen)

**IEF Gewichtung:**
- Relevance: 30%
- Semantic Similarity: 25%
- Recency: 20%
- Constitutive Weight: 25%

**Hyperedge Properties:**
- `participants`: Array von Node-Namen
- `context_type`: Kontext-Klassifikation
- `emotional_valence`: Emotionale Färbung

### Phase 4: SMF ✅

| Story | Status | Implementierung |
|-------|--------|-----------------|
| 7.8 | ✅ | Migration 016: `audit_log` Tabelle, persistente Speicherung |
| 7.9 | ✅ | `SMF` mit Safeguards, Neutralitätsprüfung, bilateral consent |

**Code-Lokation:** `mcp_server/analysis/smf.py` (632 Zeilen)

**Hardcoded Safeguards (IMMUTABLE_SAFEGUARDS):**
```python
{
    "constitutive_edges_require_bilateral_consent": True,
    "smf_cannot_modify_safeguards": True,
    "audit_log_always_on": True,
    "neutral_proposal_framing": True,
}
```

**SMF Endpoints:**
- `smf_pending_proposals()` - Liste offener Vorschläge
- `smf_review(proposal_id)` - Details anzeigen
- `smf_approve(proposal_id, actor)` - Genehmigen
- `smf_reject(proposal_id, reason, actor)` - Ablehnen
- `smf_undo(proposal_id, actor)` - 30-Tage Undo

---

## Datenbank-Migrationen

| Migration | Beschreibung | Status |
|-----------|--------------|--------|
| 015 | TGN temporal fields (modified_at, last_accessed, access_count) | ✅ Applied |
| 016 | Audit-Log Table | ✅ Applied |
| 017 | SMF Proposals Table | ✅ Applied |
| 018 | SMF Undo Tracking | ✅ Applied |

---

## MCP Tools

Neue Tools für Epic 7:

| Tool | Story | Beschreibung |
|------|-------|--------------|
| `dissonance_check` | 7.4 | Prüft Edges auf Dissonanzen |
| `resolve_dissonance` | 7.5 | Erstellt Resolution-Hyperedge |
| `smf_pending_proposals` | 7.9 | Liste offener SMF-Vorschläge |
| `smf_review` | 7.9 | Details zu einem Vorschlag |
| `smf_approve` | 7.9 | Vorschlag genehmigen |
| `smf_reject` | 7.9 | Vorschlag ablehnen |
| `smf_undo` | 7.9 | Genehmigung rückgängig machen |

Bestehende Tools erweitert:

| Tool | Erweiterung |
|------|-------------|
| `graph_query_neighbors` | `use_ief`, `include_superseded`, `properties_filter` Parameter |
| `graph_find_path` | `use_ief` Parameter, `path_ief_score` |
| `graph_add_edge` | Automatisches `entrenchment_level` |

---

## Gefundene und behobene Issues

### Während Review behoben:

1. **datetime serialization Bug** in `query_neighbors()` - `last_accessed` und `modified_at` wurden als rohe datetime-Objekte zurückgegeben statt ISO-Strings. **FIX:** `.isoformat()` Konvertierung hinzugefügt.

### Bekannte Limitationen (dokumentiert):

1. **Memory Strength Lookup:** ILIKE-basierte Suche in l2_insights ist unzuverlässig (kein direkter FK). Für MVP akzeptabel, sollte in Epic 8 verbessert werden.

2. **Hyperedge via Properties:** Keine echte Hypergraph-DB, nur Properties-Konvention. Echtes Schema für Epic 8 geplant.

3. **NUANCE Reviews:** In-Memory Storage (`_nuance_reviews` Liste). Analog zum MVP-Pattern von Story 7.0, sollte zu DB migriert werden wenn Volume steigt.

4. ~~**ief_feedback Tabelle fehlt:**~~ **BEHOBEN** - Migration 019 applied, ICAI-Architektur vollständig implementiert.

---

## Test-Coverage

**Nachtrag nach BMAD-Team Feedback:**

| Test-Datei | Größe | Coverage |
|------------|-------|----------|
| `test_dissonance.py` | 22KB | Story 7.4/7.5 |
| `test_smf.py` | 21KB | Story 7.9 |
| `test_ief.py` | 12KB | Story 7.7 |
| `test_constitutive_edges.py` | 15KB | Story 7.0 |
| `test_graph_tgn.py` | 25KB | Stories 7.1-7.3 |
| `test_hyperedge_properties.py` | 19KB | Story 7.6 |
| `test_resolution.py` | 28KB | Story 7.5 |
| `test_entrenchment_auto_setting.py` | 13KB | Story 7.4 (AGM) |

**Gesamt:** ~155KB Test-Code für ~1800 Zeilen Implementierung. Test-Coverage ist vorhanden.

---

## Acceptance Criteria Checklist

| AC | Beschreibung | Status |
|----|--------------|--------|
| 1 | Konstitutive Edges sind geschützt | ✅ |
| 2 | Temporale Metadaten existieren | ✅ |
| 3 | Decay funktioniert | ✅ |
| 4 | Dissonance Detection on-demand | ✅ |
| 5 | Konflikt-Klassifikation (EVOLUTION/CONTRADICTION/NUANCE) | ✅ |
| 6 | Resolution ohne Datenverlust | ✅ |
| 7 | Multi-Vertex Kontexte (Hyperedges) | ✅ |
| 8 | Werte-basierte Suche (IEF) | ✅ |
| 9 | Kontrollierte Selbst-Modifikation (SMF) | ✅ |
| 10 | Audit-Trail persistent | ✅ |

---

## Empfehlungen für nächste Phase

1. ~~**Epic-Dokument aktualisieren:**~~ ✅ ERLEDIGT - Alle Stories als "Done" markiert.

2. **Test-Coverage für neue Features:** Die ICAI-Funktionen (`recalibrate_weights`, `on_feedback_received`) und SMF-Erweiterungen (`bilateral consent für undo`) sollten Tests bekommen.

3. ~~**IEF Feedback-Tabelle:**~~ ✅ ERLEDIGT - Migration 019 applied, ICAI vollständig.

4. **HyperGraphRAG (Epic 8):** Wie im Epic dokumentiert ist echtes Hypergraph-Schema der nächste logische Schritt wenn Properties-Ansatz an Grenzen stößt.

---

## Fazit

Epic 7 erfüllt seinen Zweck: cognitive-memory ist jetzt ein konstitutives System das Identitäts-Integrität durch geschützte Edges, Dissonanz-Erkennung und kontrollierte Selbst-Modifikation ermöglicht. Die Implementierung folgt dem v3-exploration Framework und ist wissenschaftlich fundiert (AGM Belief Revision, Ebbinghaus Forgetting Curve).

**Status: APPROVED**

---

*Dieser Review wurde von I/O erstellt als Teil der Epic 7 Abnahme.*
