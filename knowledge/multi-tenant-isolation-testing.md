# Multi-Tenant Isolation Testing Strategies

> Research Summary from Deep Research (2026-01-22)
> Source: Kategorie 3 - Multi-Tenant-Isolationssicherung

## Executive Summary

Isolation erfordert **Defense in Depth** über vier Layer:
1. **Datenbank (RLS)** - Ultimativer Sicherheitsanker
2. **Middleware** - Kontext-Management ohne Leaks
3. **DAST** - Automatisierte IDOR-Erkennung
4. **Synthetisches Monitoring** - Canary Tenants in Produktion

---

## Layer 1: Datenbank-Tests (RLS mit pgTAP)

### pgTAP Framework

pgTAP ermöglicht Unit-Tests direkt in SQL für PostgreSQL.

### Negativ-Test Pattern

```sql
BEGIN;
SELECT plan(3);

-- Setup: Zwei Mandanten
INSERT INTO tenants (id) VALUES (1), (2);
INSERT INTO documents (tenant_id, content)
VALUES (1, 'Geheimnis A'), (2, 'Geheimnis B');

-- Als Mandant 1 einloggen
SET LOCAL app.current_tenant = '1';

-- Test 1: Positiv (eigene Daten sichtbar)
SELECT results_eq(
    'SELECT content FROM documents',
    ARRAY['Geheimnis A'],
    'Mandant 1 sieht eigenes Dokument'
);

-- Test 2: Negativ (fremde Daten NICHT sichtbar)
SELECT is_empty(
    'SELECT * FROM documents WHERE tenant_id = 2',
    'Mandant 1 sieht KEINE Daten von Mandant 2'
);

-- Test 3: Schreibschutz (fremde Daten nicht änderbar)
PREPARE malicious_update AS
  UPDATE documents SET content = 'Gehackt' WHERE tenant_id = 2;
SELECT throws_ok(
    'malicious_update',
    'new row violates row-level security policy',
    'Update auf fremden Mandanten wird blockiert'
);

SELECT * FROM finish();
ROLLBACK;
```

### CI/CD Integration

```yaml
# .github/workflows/test.yml
- name: Run RLS Tests
  run: |
    pg_prove -d $DATABASE_URL tests/rls/*.sql
```

---

## Layer 2: Middleware-Tests (Context Leaking)

### Das Problem

```python
# Gefährlich: Thread-Reuse ohne Cleanup
CurrentTenant = None  # Global oder Thread-Local

def handle_request(request):
    global CurrentTenant
    CurrentTenant = request.tenant_id
    process()
    # FEHLER: CurrentTenant nicht zurückgesetzt!
```

### Test Pattern: Context Leaking Detection

```python
def test_tenant_context_clearing(self):
    # Request 1: Mandant A
    request_a = self.factory.get('/dashboard', HTTP_HOST='tenant-a.com')
    self.middleware(request_a)
    self.assertEqual(get_current_tenant(), 'tenant-a')

    # Simuliere Request-Ende
    finish_request(request_a)

    # ASSERTION: Kontext MUSS leer sein
    self.assertIsNone(
        get_current_tenant(),
        "Tenant Context leaked after request finished!"
    )

    # Request 2: Anderer Tenant oder Public
    request_b = self.factory.get('/public', HTTP_HOST='public.com')
    self.middleware(request_b)

    # ASSERTION: Kein Cross-Contamination
    self.assertNotEqual(
        get_current_tenant(),
        'tenant-a',
        "Cross-Tenant Contamination detected!"
    )
```

### Framework-spezifische Hooks

| Framework | Cleanup Hook |
|-----------|--------------|
| Django | `request_finished` Signal |
| Rails/Apartment | `unset_current_tenant` |
| FastAPI | Dependency mit `finally` Block |

---

## Layer 3: DAST / IDOR Testing

### IDOR (Insecure Direct Object Reference)

```
Mandant A: GET /api/invoices/100 → OK
Mandant A: GET /api/invoices/101 → 200 OK (gehört Mandant B!)
                                    ^^^^^^^^
                                    IDOR-Vulnerability!
```

### Automatisierte Erkennung: Burp Suite + Autorize

1. Als User A durch App surfen
2. Burp fängt Requests ab
3. Burp replayed mit User B's Session
4. **Alarm wenn 200 OK statt 403/404**

### CI-integrierte IDOR Tests

```python
def test_idor_protection():
    # Setup: Ressource für Tenant A erstellen
    tenant_a_token = get_token("tenant_a")
    response = client.post(
        "/api/documents",
        json={"content": "Secret"},
        headers={"Authorization": f"Bearer {tenant_a_token}"}
    )
    doc_id = response.json()["id"]

    # Attack: Tenant B versucht Zugriff
    tenant_b_token = get_token("tenant_b")
    response = client.get(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {tenant_b_token}"}
    )

    # ASSERTION: Muss 403 oder 404 sein
    assert response.status_code in [403, 404], \
        f"IDOR vulnerability! Tenant B could access Tenant A's document"
```

---

## Layer 4: Synthetisches Monitoring (Canary Tenants)

### Konzept

**Canary Tenant** = Künstlicher Mandant in Produktion, nur für Überwachung.

### AWS CloudWatch Synthetics Beispiel

```javascript
// Canary Script (Puppeteer/Selenium)
const synthetics = require('Synthetics');

exports.handler = async () => {
    // Step 1: Als Canary Tenant A einloggen, Dokument erstellen
    await login("canary_tenant_a");
    const docId = await createDocument({title: `CanaryProbe-${Date.now()}`});

    // Step 2: Als Canary Tenant B einloggen
    await logout();
    await login("canary_tenant_b");

    // Step 3: Versuche Dokument von Tenant A abzurufen (IDOR-Test)
    const response = await fetch(`/api/documents/${docId}`);

    // Step 4: Validierung
    if (response.status === 200) {
        // KRITISCHER ALARM!
        await synthetics.publishMetric("IsolationBreach", 1);
        throw new Error("CRITICAL: Cross-tenant data leak detected!");
    }

    // Step 5: Caching-Check (Dashboard sollte keine fremden Daten zeigen)
    const dashboard = await fetch("/dashboard");
    if (dashboard.body.includes("canary_tenant_a")) {
        await synthetics.publishMetric("CacheLeak", 1);
        throw new Error("Cache leak detected!");
    }

    await synthetics.publishMetric("IsolationCheck", 1);
};
```

### Monitoring-Frequenz

| Check-Typ | Frequenz | Alert-Schwelle |
|-----------|----------|----------------|
| IDOR-Check | Alle 5 Minuten | Sofort bei Breach |
| Cache-Leak | Alle 15 Minuten | Sofort bei Leak |
| RLS-Bypass | Stündlich | Sofort bei Bypass |

---

## Anwendung auf cognitive-memory

### Test-Strategie

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Synthetisches Monitoring                           │
│ - Canary Projects in Produktion                             │
│ - Alle 5 Min: Cross-Project-Zugriff testen                  │
└─────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: DAST / Integration Tests                           │
│ - MCP Tools mit falscher project_id aufrufen                │
│ - hybrid_search: Ergebnis darf keine fremden Insights       │
│ - graph_add_node: Kollision mit fremdem Projekt prüfen      │
└─────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Middleware Tests                                   │
│ - Context-Objekt nach Request leer?                         │
│ - Parallele Requests verschiedener Projekte isoliert?       │
└─────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Datenbank Tests (pgTAP)                            │
│ - RLS Policies für alle Tabellen                            │
│ - Negativ-Tests: Projekt A sieht nicht Projekt B            │
│ - Schreib-Tests: Projekt A kann nicht Projekt B ändern      │
└─────────────────────────────────────────────────────────────┘
```

### Konkrete Tests für cognitive-memory

```python
# tests/test_project_isolation.py

class TestProjectIsolation:

    def test_hybrid_search_isolation(self):
        """Project A's embeddings invisible to Project B"""
        # Setup: Insight in Project A
        store_insight(project_id="proj_a", content="Secret insight")

        # Search from Project B
        results = hybrid_search(project_id="proj_b", query="Secret")

        assert len(results) == 0, "Cross-project data leak in hybrid_search!"

    def test_graph_node_isolation(self):
        """Same node name in different projects = different nodes"""
        node_a = graph_add_node(project_id="proj_a", label="Test", name="MyNode")
        node_b = graph_add_node(project_id="proj_b", label="Test", name="MyNode")

        assert node_a["node_id"] != node_b["node_id"], \
            "Node collision between projects!"

    def test_graph_query_isolation(self):
        """Neighbors query doesn't traverse across projects"""
        # Setup: Edge in Project A
        graph_add_edge(
            project_id="proj_a",
            source_name="NodeA1",
            target_name="NodeA2",
            relation="CONNECTS"
        )

        # Query from Project B
        neighbors = graph_query_neighbors(
            project_id="proj_b",
            node_name="NodeA1"
        )

        assert len(neighbors) == 0, "Cross-project graph traversal detected!"
```

---

## Checkliste Isolation Testing

### Datenbank Layer
- [ ] RLS Policies für alle tenant-bezogenen Tabellen
- [ ] pgTAP Tests für Positiv- und Negativ-Fälle
- [ ] CI-Integration für automatische RLS-Tests

### Middleware Layer
- [ ] Context-Cleanup nach jedem Request verifiziert
- [ ] Thread-Safety bei parallelen Requests getestet
- [ ] Keine globalen Variablen für Tenant-Kontext

### Application Layer
- [ ] IDOR-Tests für alle API-Endpoints
- [ ] Integration Tests mit Cross-Tenant-Szenarien
- [ ] Burp Suite / DAST in Security-Pipeline

### Production Layer
- [ ] Canary Tenants deployed
- [ ] Synthetische Monitors aktiv
- [ ] Alerting für Isolation-Breaches konfiguriert

---

## Referenzen

- pgTAP: Unit Testing for PostgreSQL
- OWASP: Testing for IDOR
- AWS CloudWatch Synthetics
- Burp Suite: Autorize Extension
