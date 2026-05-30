# Deaktivierte Tests

Diese Tests wurden deaktiviert, weil die importierten Klassen/Funktionen
nicht mehr existieren oder nie implementiert wurden.

## Deaktivierte Test-Dateien

- `test_analysis_dissonance.py` - DissonanceDetector nicht gefunden
- `test_benchmarking_latency.py` - LatencyBenchmark nicht gefunden
- `test_budget_monitor.py` - BudgetMonitor nicht gefunden
- `test_validation_irr.py` - ContingencyPlanner nicht gefunden

## Grund

Die Tests importieren Klassen/Funktionen aus Modulen, die entweder:
- Nie implementiert wurden
- Inzwischen umbenannt oder entfernt wurden

## Lösung

Diese Tests sollten neu implementiert oder gelöscht werden, wenn die
entsprechende Funktionalität wieder verfügbar ist.

## Wann zu reaktivieren?

1. Modul implementieren: Die fehlenden Klassen (`DissonanceDetector`, etc.)
   werden mit neuer Funktionalität implementiert
2. Tests löschen: Wenn die Funktionalität nicht mehr benötigt wird

## Status

- Deaktivierungsdatum: 2026-02-12
- Grund: Import-Errors blockieren Test-Collection
