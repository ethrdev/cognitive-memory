# ADR-001: Test-Layer-Architektur

**Status:** Accepted
**Datum:** 2026-02-12
**Autoren:** BMAD Party Mode Team (Murat/TEA, Winston/Architect, Amelia/Dev, Bob/SM)
**Kontext:** Audit-Session zur Test-Infrastruktur nach Epic 9/11 Abschluss

---

## Context

Die bestehende Test-Suite zeigt fundamentale Architektur-Probleme:

1. **API-Signatur-Mismatch:** Tests rufen Handler mit 3 Parametern statt 1 arguments-dict
2. **Keine Test-Tiers:** Unit, Integration und E2E Tests sind gemischt
3. **Mock-Injection:** Tests sind fest an DB-Implementation Details gekoppelt
4. **Keine Stories:** Pre-BMAD Tests ohne Acceptance Criteria

Diese Probleme führten zum FAILED Test-Coverage-Audit am 2026-02-12 (35 Collection Errors).

---

## Decision

Die Cognitive Memory Test-Suite verwendet eine **drei-Layer Architektur**:

| Layer | Scope | Database | Target Coverage | Mock-Strategy |
|-------|--------|-----------|----------------|---------------|
| **Unit Tests** | Handler-Logik ohne DB | Mocked | 80%+ Code-Coverage | Ja, full mocking |
| **Integration Tests** | Handler + echte DB | Real (Test-DB) | 60%+ Pfad-Coverage | Nein, echte DB |
| **E2E Tests** | Komplette MCP-Sitzung | Real (Test-DB) | Happy Path + Edge Cases | Nein, Full Stack |

### Unit Tests

Testen isolierte Funktionen ohne Datenbank-Abhängigkeit:

```python
@pytest.mark.asyncio
async def test_smf_approve_returns_approved_status():
    # Arrange
    arguments = {"proposal_id": 1, "actor": "I/O"}

    # Act
    result = await handle_smf_approve(arguments)

    # Assert
    assert result["status"] == "approved"
```

### Integration Tests

Testen Handler mit echter Datenbank (requires `asyncpg`):

```python
@pytest.mark.asyncio
async def test_smf_approve_updates_database(test_db_connection):
    # Arrange
    proposal = await create_test_proposal(test_db_connection)
    arguments = {"proposal_id": proposal["id"], "actor": "I/O"}

    # Act
    result = await handle_smf_approve(arguments)

    # Assert
    db_row = await test_db_connection.fetchrow(
        "SELECT status FROM smf_proposals WHERE id = $1",
        proposal["id"]
    )
    assert db_row["status"] == "approved"
```

### E2E Tests

Testen komplette MCP-Server-Sitzungen:

```python
@pytest.mark.e2e
async def test_smf_approval_flow_full_session():
    # Start MCP-Server, sende approve request, validiere Response
    # ...
```

---

## Consequences

### Positive

- ✅ **Lose Kopplung:** Unit Tests sind unabhängig von DB-Änderungen
- ✅ **Klare Trennung:** Jede Test-Art hat klare Verantwortung
- ✅ **Schnelle Unit-Tests:** Kein DB-Setup, keine Latenz
- ✅ **Wartbarkeit:** API-First Design statt Implementation Details

### Negative

- ⚠️ **Initialer Aufwand:** Bestehende Tests müssen refactort werden (~14.5h für 8 SMF-Tests)
- ⚠️ **Komplexität:** Drei Test-Kategorien müssen koordiniert werden
- ⚠️ **Dependency:** Integration und E2E Tests benötigen `asyncpg`

---

## Implementation Roadmap

| Phase | Task | Aufwand | Status |
|--------|-------|---------|--------|
| P0 | `asyncpg` Dependency installieren | 5 min | Pending |
| P0 | Unit-Test Base in `tests/conftest.py` erstellen | 2h | Pending |
| P1 | 8 SMF-Tests zu Unit-Tests refactoren | 14.5h | Pending |
| P2 | Integration-Test Base erstellen | 4h | Pending |
| P2 | Tote Tests (35 Import-Errors) aufräumen | 4h | Pending |

---

## Referenzen

- Audit-Bericht: `bmad-docs/audit-test-coverage-2026-02-12.md`
- System-Audit: `bmad-docs/audit-2026-02-12.md`
- Party-Mode Session: `bmad-docs/party-mode-session-2026-02-12.md`

---

**Next Review:** Nach Epic TD-1 Abschluss
