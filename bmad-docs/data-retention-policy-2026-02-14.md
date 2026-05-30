# Data Retention Policy — Cognitive Memory System

**Erstellt:** 2026-02-14
**Status:** 📋 VORSCHLAG (zur Implementierung)
**Priority:** P1 — Kritisch für Compliance & Datenschutz

---

## Executive Summary

Das Cognitive Memory System hat **teilweise Retention-Mechanismen**, aber **keine globale Data-Lösch-Policy**. Memory-Decay reduziert Scores, aber löscht keine Daten. SMF-Undo hat 30-Tage Limit, aber andere Daten bleiben für immer.

**Ergebnis: System wächst unbeschränkt — DSGVO/GDPR-Risiko.**

| Daten-Typ | Retention | Auto-Löschung | Status |
|------------|-----------|---------------|--------|
| L2 Insights | ❌ Nie | ❌ Nein | 🔴 Kritisch |
| Episode Memory | ❌ Nie | ❌ Nein | 🔴 Kritisch |
| Raw Dialogue (l0_raw) | ❌ Nie | ❌ Nein | 🔴 Kritisch |
| Graph Nodes/Edges | ❌ Nie | ❌ Nein | 🟠 Mittel |
| Working Memory | ⚠️ Decay | ❌ Nein | 🟡 Akzeptabel |
| SMF Proposals | ⚠️ 7 Tage | ✅ Ja | 🟢 Gut |
| Golden Test Set | ❌ Nie | ❌ Nein | 🟠 Mittel |
| Cost Logs | ❌ Nie | ❌ Nein | 🟠 Mittel |

---

## VORHANDENE MECHANISMEN

### 1. Memory Decay (decay_config.yaml)

**Funktionsweise:** Reduziert `memory_strength` Score über Zeit

```yaml
# mcp_server/config/decay_config.yaml
decay_config:
  emotional:
    S_base: 200.0   # Halbwertszeit: 200 Tage
    S_floor: 150.0   # Mindestscore: 15%
  episodic:
    S_base: 150.0
    S_floor: 100.0
  # ... andere Sektoren
```

**Analyse:**
- ✅ Implementiert für alle Memory-Sektoren
- ✅ Score wird bei hybrid_search verwendet
- ❌ **Daten werden NICHT gelöscht** — nur de-prioritisiert
- ❌ Kein automatisches Löschen auch bei S_floor = 0

**Bewertung:** Nützlich für Relevanz-Sorting, aber **kein Retention-Mechanism**.

---

### 2. SMF Undo Retention (smf_config.yaml)

**Funktionsweise:** 30-Tage Fenster für SMF-Undo

```yaml
# mcp_server/config/smf_config.yaml
undo_retention_days: 30
```

**Implementierung:**
```python
# mcp_server/tools/smf_undo.py
if age_days > UNDO_RETENTION_DAYS:
    raise ValueError("RETENTION_EXPIRED: 30-day undo window has expired")
```

**Analyse:**
- ✅ Klares Retention-Fenster: 30 Tage
- ✅ Preventiert unbeschränktes Undo
- ❌ **Nur für SMF-Proposals** — andere Daten nicht betroffen

**Bewertung:** Guter Anfang, aber Scope zu eng.

---

### 3. Created At Timestamps (Schema)

**Vorhanden in allen Tabellen:**
```sql
created_at TIMESTAMP DEFAULT NOW()
```

**Analyse:**
- ✅ Alle Datensätze haben created_at
- ✅ Wird für Cost-Logging verwendet (cost_logger.py)
- ✅ Wird für SMF-Timeout verwendet (approval_timeout_hours)
- ❌ **Keine globale Lösch-Funktion** die created_at nutzt

**Bewertung:** Infrastruktur bereit, aber Policy fehlt.

---

## LÜCKEN & RISIKEN

### 🔴 Kritisch: Keine Data Expiry

**Problem:** Daten werden niemals automatisch gelöscht

| Daten-Typ | Wachstum-Rate | Schätzung 6 Monate |
|------------|--------------|------------------|
| L2 Insights | ~2/Woche | ~50 |
| Episode Memory | ~5/Woche | ~130 |
| Raw Dialogue | ~10/Woche | ~260 |
| Graph Nodes | ~1/Woche | ~26 |

**Risiko:** Unbegrenztes Datenwachstum → Storage-Kosten, Performance, DSGVO-Verletzung.

---

### 🔴 Kritisch: Keine DSGVO/GDPR Compliance

**Fehlende Elemente:**
- ❌ Keine Rechtsgrundlage für Datenspeicherung
- ❌ Kein User-Right-to-be-forgotten
- ❌ Keine Data-Export-Funktion
- ❌ Keine Consent-Tracking

**Risiko:** Bei regulatorischer Anfrage sind Informationen unzureichend.

---

### 🟠 Mittel: Keine Cleanup Jobs

**Problem:** Keine automatischen Bereinigungs-Prozesse

**Auswirkungen:**
- Stale Memory bleibt für immer
- Golden Test Set wird nie bereinigt
- Cost Logs wachsen unbeschränkt

---

## VORSCHLÄGE

### R1: Globale Retention Policy [4-8h]

**Ziel:** Konfigurierbare Retention pro Daten-Typ

**Vorschlag:**
```yaml
# mcp_server/config/retention_policy.yaml
retention_policy:
  l2_insights:
    default_days: 365          # 1 Jahr Standard
    min_days: 90                 # 3 Monate Minimum
    decay_threshold: 0.1          # Unter 10% Score = löschbar

  episode_memory:
    default_days: 730              # 2 Jahre Standard
    min_days: 180                 # 6 Monate Minimum
    access_based: true            # Löschen wenn 90 Tage nicht zugeriffen

  raw_dialogue:
    default_days: 90               # 3 Monate Standard
    min_days: 30                  # 1 Monat Minimum
    compress_after_days: 7          # Nach 7 Tagen zu L2 komprimieren

  graph_data:
    default_days: 3650             # 10 Jahre Standard
    orphan_only: true              # Nur isolierte Nodes löschen

  working_memory:
    default_days: 7                 # 1 Woche Standard
    volatile: true                  # Schnelles Verfallen

  cost_logs:
    default_days: 365               # 1 Jahr Standard
    aggregate_after_days: 30      # Nach 30 Tagen aggregieren
```

**Implementierung:**
1. retention_policy.yaml laden (mit Fallback auf Defaults)
2. Migration für `retention_days` Spalte in relevanten Tabellen
3. Löschen nur wenn created_at < NOW() - retention_days

---

### R2: Auto-Cleanup Service [8-12h]

**Ziel:** Periodische Bereinigung alter Daten

**Vorschlag:**
```python
# mcp_server/services/data_cleanup.py

class DataCleanupService:
    """
    Periodische Datenbereinigung basierend auf Retention Policy.
    Läuft als Background-Job alle X Stunden.
    """

    async def cleanup_expired_data(self) -> dict:
        """
        Löscht Daten die Retention-Policy überschreiten.
        Gibt Report zurück: deleted_counts, errors, duration_ms.
        """
        results = {
            "l2_insights_deleted": 0,
            "episodes_deleted": 0,
            "raw_deleted": 0,
            "graph_deleted": 0,
            "errors": []
        }

        # L2 Insights
        cutoff = datetime.now() - timedelta(days=self.retention.l2_insights)
        deleted = await self._delete_l2_insights_created_before(cutoff)
        results["l2_insights_deleted"] = deleted

        # ... ähnlich für andere Tabellen

        return results

    async def cleanup_stale_memories(self) -> dict:
        """
        Löscht Memory mit memory_strength < threshold.
        'stale' bedeutet nicht mehr relevant für Suche.
        """
        threshold = self.retention.decay_threshold
        deleted = await self._delete_memories_below_strength(threshold)
        return {"stale_deleted": deleted, "threshold": threshold}
```

**Integration:**
```python
# mcp_server/__main__.py
async def run_periodic_cleanup():
    """Background-Job für stündliche/periodische Bereinigung."""
    cleanup = DataCleanupService()
    while True:
        try:
            results = await cleanup.cleanup_expired_data()
            logger.info(f"Data cleanup completed: {results}")
            await asyncio.sleep(cleanup_interval_hours * 3600)
        except Exception as e:
            logger.error(f"Data cleanup failed: {e}")
            await asyncio.sleep(retry_interval_minutes * 60)
```

---

### R3: Right-to-Privacy-Funktionen [8-12h]

**Ziel:** DSGVO/GDPR-konforme User-Rechte

**Vorschlag:**

| Funktion | Beschreibung | Aufwand |
|----------|--------------|---------|
| **Export User Data** | Alle Daten eines Projekts exportieren (JSON/CSV) | 4-6h |
| **Delete User Data** | Alle Daten eines Projekts löschen (inkl. Graph) | 2-4h |
| **Anonymize Data** | Personen/Projekt-Namen anonymisieren | 4-6h |
| **Consent Tracking** | Einwilligungs-Status pro User speichern | 6-8h |

**MCP-Tools:**
```python
# mcp_server/tools/data_privacy.py

@tool
async def handle_export_project_data(arguments: dict) -> dict:
    """
    Export all data for a project (episodes, insights, graph, etc.).
    Returns: file_path with exported data.
    """
    project_id = get_current_project()
    # ... Export logic

@tool
async def handle_delete_project_data(arguments: dict) -> dict:
    """
    Delete ALL data for a project (GDPR right-to-be-forgotten).
    Requires: confirmation_token (to prevent accidental deletion).
    """
    project_id = get_current_project()
    confirmation = arguments.get("confirmation_token")
    if confirmation != f"DELETE_{project_id}":
        return {"error": "Invalid confirmation token"}
    # ... Delete logic
```

---

### R4: Access-Based Retention [4-6h]

**Ziel:** Daten die nicht zugeriffen werden früher löschen

**Vorschlag:**
```sql
-- Migration für last_accessed Spalte
ALTER TABLE l2_insights ADD COLUMN last_accessed TIMESTAMP DEFAULT NOW();

-- Cleanup Query
DELETE FROM l2_insights
WHERE created_at < NOW() - INTERVAL '90 days'
  AND last_accessed < NOW() - INTERVAL '30 days';
```

**Implementierung:**
- `last_accessed` bei jedem hybrid_search Treffer aktualisieren
- Cleanup löscht wenn nicht zugeriffen in X Tagen

---

### R5: Aggregierte Cost Logs [2-4h]

**Ziel:** Alte Cost Logs aggregieren um Platz zu sparen

**Vorschlag:**
```sql
-- Tabelle für aggregierte Daten
CREATE TABLE cost_logs_aggregated (
    date DATE PRIMARY KEY,
    api_name TEXT,
    total_calls INTEGER,
    total_tokens BIGINT,
    total_estimated_cost NUMERIC(10,4)
);

-- Aggregierungs-Query (z.B. wöchentlich)
INSERT INTO cost_logs_aggregated
SELECT
    created_at::DATE,
    api_name,
    SUM(num_calls),
    SUM(total_tokens),
    SUM(estimated_cost_eur)
FROM api_cost_log
WHERE created_at < NOW() - INTERVAL '30 days'
GROUP BY created_at::DATE, api_name;

-- Original-Daten löschen
DELETE FROM api_cost_log WHERE created_at < NOW() - INTERVAL '30 days';
```

---

## IMPLEMENTIERUNGSPLAN

### Phase 1: Retention Policy [Woche 1]

| Aufgabe | Aufwand | Priorität |
|---------|---------|------------|
| retention_policy.yaml erstellen | 1h | P1 |
| Retention-Service implementieren | 4-6h | P1 |
| Migration für retention_days Spalten | 2-3h | P1 |
| Konfiguration laden & validieren | 1-2h | P1 |

### Phase 2: Auto-Cleanup [Woche 2-3]

| Aufgabe | Aufwand | Priorität |
|---------|---------|------------|
| DataCleanupService implementieren | 6-8h | P1 |
| Background-Job integration | 2-4h | P2 |
| Cleanup-Logging & Monitoring | 2-3h | P2 |
| Testen mit kleinen Retentions | 2-4h | P2 |

### Phase 3: Privacy Functions [Woche 4]

| Aufgabe | Aufwand | Priorität |
|---------|---------|------------|
| Export-Daten implementieren | 4-6h | P2 |
| Delete-Daten implementieren | 2-4h | P2 |
| Anonymisierungs-Logik | 4-6h | P2 |
| DSGVO/GDPR Dokumentation | 2-3h | P2 |

---

## RISIKO-ANALYSE

| Szenario | Wahrscheinlichkeit | Auswirkung | Risiko-Level |
|----------|-------------------|------------|--------------|
| **Regulatorische Anfrage** | Mittel (30%) | Bußgelder bis 50.000€ | 🟠 Mittel |
| **Storage Overflow** | Niedrig (10%) | Performance-Degradation | 🟡 Niedrig |
| **DSGVO-Verletzung** | Mittel (20%) | Reputations-Schaden | 🔴 Hoch |
| **User-Trust Verlust** | Mittel (15%) | Churn-Rate ↑ | 🟠 Mittel |

**Gesamtrisiko: 🟠 MITTEL — Keine sofortige Handlung, aber sollte binnen 3 Monaten adressiert werden.**

---

## KOSTEN-SCHÄTZUNG

| Phase | Aufwand | Einmalkosten (bei 50€/h) |
|-------|---------|---------------------------|
| Phase 1: Retention Policy | 8-12h | 400-600€ |
| Phase 2: Auto-Cleanup | 12-19h | 600-950€ |
| Phase 3: Privacy Functions | 12-19h | 600-950€ |
| **GESAMT** | **32-50h** | **1600-2500€** |

---

## NÄCHSTE SCHRITTE

1. ✅ **Retention Policy erstellen** — Konfiguration + Service
2. ✅ **Auto-Cleanup implementieren** — Background-Job
3. ⏳ **Privacy-Funktionen** — Wenn regulatorischer Druck entsteht
4. ⏳ **DSGVO/GDPR Review** — Juristisches Review

---

*Erstellt von:* BMad Master + Party Mode Team (Mary, Bob)
*Status:* 📋 VORSCHLAG — Wartet auf Implementierung
