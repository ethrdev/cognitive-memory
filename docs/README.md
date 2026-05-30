# cognitive-memory - Documentation

Diese Dokumentation enthält alle **Betriebs- und Entwickler-Dokumente** für das Cognitive Memory System. Für Projekt-Planung (PRD, Architecture, Epics) siehe `/bmad-docs/`.

## Quick Links

| Aufgabe | Dokument |
|---------|----------|
| **Erstinstallation** | [Installation Guide](./guides/installation-guide.md) |
| **Täglicher Betrieb** | [Operations Manual](./operations/operations-manual.md) |
| **Fehlersuche** | [Troubleshooting](./troubleshooting.md) |
| **API-Referenz** | [API Reference](./reference/api-reference.md) |
| **Backup/Recovery** | [Backup & Recovery](./operations/backup-recovery.md) |
| **Ecosystem-Übersicht** | [Ecosystem Architecture](./ecosystem/architecture.md) |
| **Consent Protocol** | [Konzept](./concepts/consent-protocol.md) · [Implementation](./guides/implementing-consent.md) |

## Dokumenten-Struktur

```
docs/
├── README.md                 # Diese Datei
├── troubleshooting.md        # Fehlerbehebung
│
├── concepts/                 # Konzeptuelle Dokumentation
│   └── consent-protocol.md   # 4-Level Consent Protocol für AI Memory
│
├── ecosystem/                # Ecosystem-Integration
│   └── architecture.md       # Position im 4-Schichten-Ecosystem
│
├── guides/                   # Anleitungen
│   ├── installation-guide.md
│   ├── postgresql-setup.md
│   ├── mcp-configuration.md
│   ├── how-to-activate-io.md
│   ├── query-expansion-guide.md
│   ├── cot-generation-guide.md
│   ├── fallback-strategy.md
│   ├── staged-dual-judge.md
│   └── implementing-consent.md  # Consent Protocol Integration
│
├── operations/               # Betrieb
│   ├── operations-manual.md
│   ├── systemd-deployment.md
│   ├── production-checklist.md
│   └── backup-recovery.md
│
├── testing/                  # Testing & Evaluation
│   ├── query-expansion-testing-guide.md
│   ├── query-expansion-evaluation.md
│   ├── cot-evaluation.md
│   ├── budget-monitoring-testing.md
│   ├── 7-day-stability-test-guide.md
│   └── 7-day-stability-report-template.md
│
├── monitoring/               # Monitoring
│   ├── budget-monitoring.md
│   └── budget-monitoring-sql-queries.md
│
├── reference/                # API-Dokumentation
│   └── api-reference.md
│
├── integration/              # Integration Guides
│   ├── evaluation-integration-guide.md
│   └── reflexion-integration-guide.md
│
└── use-cases/                # Anwendungsfälle
    ├── portfolio-use-cases.md
    └── golden-test-set.md
```

## Ecosystem-Position

cognitive-memory ist **Layer 2 (Storage Layer)** im 4-Schichten-Ecosystem:

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: Applications                                           │
│   • tethr (AI Personal Assistant)                               │
│   • agentic-business (Business Hub)                             │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: Ethical Framework                                      │
│   • i-o-system (Consent Protocol, Memory Governance)            │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: Storage Layer  ★ COGNITIVE-MEMORY ★                   │
│   • MCP Server (Python)                                         │
│   • PostgreSQL + pgvector                                       │
│   • Hybrid Search, Verbal RL, Dual Judge                        │
└─────────────────────────────────────────────────────────────────┘
```

Für Details siehe [ecosystem/architecture.md](./ecosystem/architecture.md).

## Verbindung zu anderen Projekten

| Projekt | Rolle | Status |
|---------|-------|--------|
| **cognitive-memory** | Storage Layer (MCP Server) | ✅ ~95% fertig |
| **i-o-system** | Ethical Framework (nutzt cognitive-memory) | 🚧 ~40% |
| **tethr** | AI Personal Assistant | 📋 Geplant |
| **agentic-business** | Business Hub | 📋 Geplant |

## Dokumentations-Aufteilung

| Ordner | Zweck | Zielgruppe |
|--------|-------|------------|
| `/docs/` | Betriebs-Docs (Wie benutze ich es?) | Anwender, Ops |
| `/bmad-docs/` | Projekt-Docs (Was wurde geplant?) | Entwickler, Architekten |

---

**Version:** 3.1.0-Hybrid
**Letzte Aktualisierung:** 2026-01-02
