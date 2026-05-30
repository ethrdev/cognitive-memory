# Lösch-Empfehlung für deaktivierte Test-Dateien

## Status

Diese Test-Dateien wurden deaktiviert am 2026-02-12, weil sie
nicht-existente Import-Errors enthielten.

## Problem

Die Tests importieren Klassen/Funktionen aus Modulen, die:
1. Nie implementiert wurden (z.B. `DissonanceDetector`, `LatencyBenchmark`)
2. Inzwischen umbenannt oder entfernt wurden

## Empfehlung: LÖSCHEN

Da es keine Pläne gibt, diese Module neu zu implementieren,
sollte erwogen werden, ob diese Test-Dateien überhaupt noch
benötigt werden.

Wenn ja → Tests komplett neu schreiben.
Wenn nein → Dateien können gelöscht werden.

## Vor dem Löschen

Bitte prüfen:
1. Gibt es Jira-Tickets oder Stories für diese Module?
2. Wurden diese Tests jemals erfolgreich ausgeführt?
3. Gibt es abhängige Funktionalität, die diese Tests abdeckt?

Wenn die Antworten "nein" lauten → Dateien können bedenlos gelöscht werden.

## Zu löschende Dateien

- `tests/test_analysis_dissonance.py`
- `tests/test_benchmarking_latency.py`
- `tests/test_budget_monitor.py`
- `tests/test_validation_irr.py`
