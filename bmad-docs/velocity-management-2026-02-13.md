# Velocity-Management: Prevention over Cure

**Datum:** 2026-02-13
**Erstellt von:** Party-Mode Session (Mary, Murat, Winston)
**Status:** PROPOSED
**Ziel:** Technical Debt durch schnelle Entwicklung verhindern

---

## Executive Summary

Das Cognitive Memory System hat ein wiederkehrendes Muster: **Hohe Velocity erzeugt Technical Debt**. Das Party-Mode-Problem vom 12. Februar 2026 (35 Test-Errors nach schnellen API-Änderungen) ist exemplarisch.

Dieses Dokument etabliert **Protokolle für Velocity-Management**, die Balance zwischen Geschwindigkeit und Qualität ermöglichen.

---

## The Problem Pattern (Historische Daten)

### Timeline des Debt-Anstiegs

| Datum | Event | Konsequenz | Debt-Stunde |
|-------|--------|------------|-------------|
| 2026-02-12 | Party-Mode-Session | 35 Test-Errors | 8-12h Reparatur |
| 2026-02-12 | 7 Fixes in 1 Tag | Unbekannte Regression-Risiken | ? |
| 2026-02-12 | API-Signatur-Änderungen | 8 SMF-Tests kaputt | 4-6h Reparatur |

**Gesamtschätzung:** 12-18 Stunden Technical Debt durch **einen Tag** schneller Entwicklung.

---

## Root Cause Analysis

### Warum entsteht der Debt?

| Root Cause | Beschreibung | Vorkommen |
|------------|-------------|-----------|
| **Code ohne Test-Updates** | Änderungen ohne parallele Test-Anpassung | Sehr häufig |
| **Hotfixes bypass Tests** | Schnelle Fixes ohne Test-Verification | Häufig |
| **Missing Definition of Done** | Kein klarer Abschluss für schnelle Sessions | Immer |
| **Kein Documentation-Mandat** | API-Änderungen nicht dokumentiert | Häufig |

### Das "Party Mode" Anti-Pattern

```
Schnelle Entwicklung
    ↓
Änderungen im Code
    ↓
Tests NICHT angepasst
    ↓
Technical Debt
    ↓
Reparatur-Zeit (8-18h)
    ↓
Velocity verloren
```

---

## Prevention Protocols

### Phase 1: VOR schnellen Änderungen

**Trigger:** Geplante schnelle Entwicklungssitzung (z.B. Party Mode, Hotfix-Sprint)

**Checkliste:**
- [ ] **Test Impact Assessment** - Welche Tests sind betroffen?
- [ ] **Draft Test Updates** - Test-Änderungen IN DER SESSION mitdraften
- [ ] **Critical Path Identification** - Welche Tests MÜSSEN funktionieren?
- [ ] **Ticket-Erstellung** - Test-Reparatur-Ticket VORher erstellen

**Dauer:** 15-30 Minuten
**ROI:** Verhindert 8-18h Reparatur

---

### Phase 2: WÄHREND schneller Sessions

**Protokoll für Party-Mode, Hotfix-Sprints, etc.:**

1. **Alle API-Änderungen dokumentieren**
   ```markdown
   ## API Changes [Date]
   - tool_name: signature change X → Y
   - reason: ...
   - tests_affected: list
   ```

2. **Tests als "temporarily broken" markieren**
   ```python
   # TODO: Test broken after API change (2026-02-13)
   # Fix in: ticket-XXX
   # Temporary workaround: ...
   ```

3. **Reparatur-Ticket SOFORT erstellen**
   - Titel: "Test-Reparatur nach [Session Name]"
   - Priority: P0
   - Deadline: 1 Woche

---

### Phase 3: NACH schnellen Sessions

**Verpflichtender Follow-up innerhalb 1 Woche:**

- [ ] **Test Verification Sprint** - Alle Tests wieder grün
- [ ] **Regression Test** - Modifizierte Module verifizieren
- [ ] **Documentation Update** - API-Changes in docs/ integrieren
- [ ] **Retro-Session** - Was lief gut? Was kann verbessert werden?

**Go/No-Go Kriterium:**
- ✅ Go: 0 Test-Errors, Docs updated
- ❌ No-Go: Session gilt als NICHT abgeschlossen

---

## Velocity vs. Quality Matrix

| Szenario | Velocity | Qualität | Akzeptabel? | Protokoll |
|----------|----------|----------|--------------|-----------|
| **Normal Development** | Mittel | Hoch | ✅ Ja | Standard-Workflow |
| **Hotfix (Produktion)** | Hoch | Mittel | ⚠️ Mit Ticket | Hotfix-Protokoll + 1-week follow-up |
| **Party Mode Session** | Hoch | Niedrig | ❌ Nein | Nicht erlaubt ohne Protokoll |
| **Planned Feature Sprint** | Mittel | Hoch | ✅ Ja | Mit Test-Planung |
| **Emergency Fix** | Sehr Hoch | Gering | ⚠️ 24h Fix | Nur bei Produktion-Down |

---

## Definition of Done (für schnelle Sessions)

Eine schnelle Entwicklungssession gilt nur als **DONE**, wenn:

### Must-Have (P0)
- [ ] Code funktioniert
- [ ] Kritische Tests passieren
- [ ] API-Änderungen dokumentiert
- [ ] Reparatur-Ticket erstellt

### Should-Have (P1)
- [ ] Alle Tests passieren
- [ ] Regression-Test durchgeführt
- [ ] Dokumentation aktualisiert

### Nice-to-Have (P2)
- [ ] Performance-Test durchgeführt
- [ ] Code Review durchgeführt

---

## Test-First Protokoll für API-Änderungen

Wenn API-Signaturen sich ändern:

### 1. Vor der Änderung
```python
# OLD SIGNATURE (documented)
async def handle_smf_approve(
    mock_db_connection,
    proposal_id: int,
    actor: str
) -> dict:
    ...
```

### 2. Die Änderung
```python
# NEW SIGNATURE (documented in code comment)
async def handle_smf_approve(
    arguments: dict[str, Any]
) -> dict[str, Any]:
    """
    MCP tool handler for SMF approve.

    Args:
        arguments: Tool arguments containing:
            - proposal_id: ID of proposal to approve
            - actor: Who is approving

    Returns:
        Dict with approval status and execution results
    """
    proposal_id = arguments.get("proposal_id")
    actor = arguments.get("actor")
```

### 3. Test-Anpassung (IMMEDIATEL)
```python
# NEW TEST SIGNATURE (adapted)
async def test_smf_approve_happy_path():
    result = await handle_smf_approve({
        "proposal_id": 123,
        "actor": "I/O"
    })
    assert result["status"] == "approved"
```

---

## Dashboard & Metrics

### Zu trackende Metriken

| Metrik | Ziel | Aktuell | Action wenn unterschritten |
|--------|-------|---------|--------------------------|
| Test-Errors | 0 | 35 | ❌ Blockiert Deploy |
| Test-Collection-Errors | 0 | 35 | ❌ Blockiert Deploy |
| Velocity-Sessions mit Follow-up | 100% | 0% | ⚠️ Protokoll nicht etabliert |
| API-Änderungen dokumentiert | 100% | ~50% | ⚠️ Documentation-Debt |

---

## Verantwortlichkeiten

| Rolle | Verantwortung bei schnellen Sessions |
|-------|-------------------------------------|
| **Developer** | Code schreiben, Tests anpassen, Änderungen dokumentieren |
| **QA/Murat** | Test-Impact-Assessment, Verification |
| **Architect/Winston** | Review, Regression-Check |
| **PM/Mary** | Ticket-Erstellung, Deadline-Tracking |

---

## Communication Channels

### Bei Velocity-Sessions:

1. **VORHER:** Ankündigung mit Test-Impact-Assessment
2. **WÄHREND:** Status-Updates bei API-Änderungen
3. **NACHHER:** Follow-up-Ticket mit 1-week Deadline

---

## Lessons Learned (aus Party-Mode-Session)

### Was lief schief?
- Tests wurden nicht parallel zu Code-Änderungen angepasst
- API-Changes wurden nicht dokumentiert
- Kein Follow-up-Ticket erstellt
- Keine Test-Impact-Analyse VORHER

### Was lief gut?
- Schnelle Problem-Identifikation
- 7 kritische Fixes in kurzer Zeit
- Transparente Dokumentation nachträglich

### Takeaways für Zukunft:
1. **Test-First Mindset** - Änderungen IMMER mit Tests denken
2. **Documentation Mandate** - API-Änderungen IMMER dokumentieren
3. **Follow-up Tickets** - Reparatur IMMER ticketen

---

## Templates

### Template: Test-Reparatur-Ticket

```markdown
## Test-Reparatur nach [Session Name]

**Erstellt:** [Date]
**Session:** [Session Name, z.B. Party Mode 2026-02-12]
**Priority:** P0
**Deadline:** [Date + 1 week]

### Scope
- [ ] Affected Tests: [List]
- [ ] Estimated Hours: [Number]

### Root Cause
- API-Signature changed: [Details]
- Module deprecated: [Details]

### Fix Plan
1. [ ] Delete obsolete tests
2. [ ] Update API signatures
3. [ ] Verify test collection
4. [ ] Run full test suite

### Go/No-Go Criteria
- ✅ Go: 0 errors, >90% tests passing
- ❌ No-Go: Reassess approach
```

### Template: Velocity-Session Checklist

```markdown
## Velocity Session Checklist

**Session:** [Name]
**Date:** [Date]

### BEFORE
- [ ] Test Impact Assessment done?
- [ ] Critical tests identified?
- [ ] Repair ticket created?

### DURING
- [ ] All API changes documented?
- [ ] Tests marked as temporarily broken (if needed)?
- [ ] Code review completed?

### AFTER (within 1 week)
- [ ] All tests passing?
- [ ] Regression test done?
- [ ] Documentation updated?
- [ ] Retro session completed?
```

---

## Next Steps

1. ✅ Dokument erstellt (2026-02-13)
2. ⏳ Team-Review und Feedback einholen
3. ⏳ Protokolle in next Party-Mode-Session anwenden
4. ⏳ Nach 1 Monat: Effectiveness-Review

---

## References

- bmad-docs/party-mode-session-2026-02-12.md
- bmad-docs/technical-debt-audit-2026-02-13.md
- bmad-docs/audit-test-coverage-2026-02-12.md

---

**Erstellt von:** Mary (Analyst), Murat (TEA), Winston (Architect)
**Document Version:** 1.0
**Next Review:** 2026-03-13
