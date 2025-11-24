# Systemd Deployment Guide

**Cognitive Memory MCP Server v3.1.0-Hybrid**

Dieser Guide beschreibt die Installation und Verwaltung des MCP Servers als systemd Service für automatischen Start beim Boot und Auto-Restart bei Crashes.

## Überblick

Der MCP Server wird als systemd Service konfiguriert, um:
- Automatisch beim System-Boot zu starten
- Bei Crashes automatisch neu zu starten (Restart=always)
- Health Monitoring via systemd Watchdog zu ermöglichen
- Zentrale Logging über systemd Journal bereitzustellen

## Voraussetzungen

- Linux System mit systemd (getestet auf Arch Linux)
- Python 3.11+ Installation
- PostgreSQL Server installiert und laufend
- Production Environment konfiguriert (siehe `docs/production-checklist.md`)
- Sudo-Berechtigung für Service Installation

## Service Installation

### Automatische Installation (Empfohlen)

Die automatische Installation verwendet das mitgelieferte Script:

```bash
# Installation ausführen (requires sudo)
sudo bash scripts/install_service.sh
```

Das Script führt folgende Schritte aus:
1. Validiert Service File Syntax
2. Kopiert Service File nach `/etc/systemd/system/`
3. Führt `systemctl daemon-reload` aus
4. Aktiviert Service für Auto-Start (`systemctl enable`)

### Manuelle Installation

Falls manuelle Installation bevorzugt wird:

```bash
# 1. Service File kopieren
sudo cp systemd/cognitive-memory-mcp.service /etc/systemd/system/

# 2. Service File Syntax validieren
sudo systemd-analyze verify cognitive-memory-mcp.service

# 3. Systemd Daemon reload
sudo systemctl daemon-reload

# 4. Service für Auto-Start aktivieren
sudo systemctl enable cognitive-memory-mcp.service
```

## Service Management

### Service Starten/Stoppen

```bash
# Service starten
sudo systemctl start cognitive-memory-mcp

# Service stoppen
sudo systemctl stop cognitive-memory-mcp

# Service neu starten
sudo systemctl restart cognitive-memory-mcp
```

### Service Status Prüfen

```bash
# Aktuellen Status anzeigen
systemctl status cognitive-memory-mcp

# Aktiv-Status prüfen
systemctl is-active cognitive-memory-mcp

# Auto-Start Status prüfen
systemctl is-enabled cognitive-memory-mcp
```

### Log-Zugriff

Der Service schreibt alle Logs in das systemd Journal:

```bash
# Alle Logs anzeigen
journalctl -u cognitive-memory-mcp

# Logs live verfolgen (tail -f)
journalctl -u cognitive-memory-mcp -f

# Logs seit bestimmter Zeit
journalctl -u cognitive-memory-mcp --since "10 minutes ago"
journalctl -u cognitive-memory-mcp --since "2025-01-01"

# Nur Fehler anzeigen
journalctl -u cognitive-memory-mcp -p err

# Logs mit Timestamps
journalctl -u cognitive-memory-mcp -o short-precise
```

## Service Konfiguration

### Service File Struktur

Der Service ist konfiguriert unter `/etc/systemd/system/cognitive-memory-mcp.service`:

```ini
[Unit]
Description=Cognitive Memory MCP Server - Persistent Memory System
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=notify
User=ethr
WorkingDirectory=/home/user/i-o
ExecStart=/home/user/i-o/venv/bin/python /home/user/i-o/mcp_server/__main__.py
Restart=always
RestartSec=10
Environment="ENVIRONMENT=production"

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cognitive-memory-mcp

# Health Monitoring
WatchdogSec=60
NotifyAccess=main

[Install]
WantedBy=multi-user.target
```

### Wichtige Konfigurationsparameter

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| `Type` | `notify` | Service benachrichtigt systemd bei Bereitschaft (watchdog support) |
| `User` | `ethr` | Service läuft als non-root user (Security) |
| `Restart` | `always` | Auto-restart bei allen Exit-Codes (inkl. Crashes) |
| `RestartSec` | `10` | 10 Sekunden Wartezeit vor Neustart |
| `Environment` | `ENVIRONMENT=production` | Lädt Production Config (.env.production) |
| `WatchdogSec` | `60` | Watchdog Timeout 60 Sekunden |

### Environment Loading

Der Service setzt `ENVIRONMENT=production`, wodurch:
- `config/.env.production` geladen wird (API Keys, DB Credentials)
- Production Database `cognitive_memory` verwendet wird
- Production-spezifische Konfiguration aktiviert wird

Siehe `docs/production-checklist.md` für Environment Setup Details.

## Auto-Start Konfiguration

### Auto-Start Aktivieren

```bash
# Service für Auto-Start aktivieren
sudo systemctl enable cognitive-memory-mcp

# Verifikation
systemctl is-enabled cognitive-memory-mcp
# Expected output: "enabled"
```

### Auto-Start Deaktivieren

```bash
# Auto-Start deaktivieren
sudo systemctl disable cognitive-memory-mcp

# Verifikation
systemctl is-enabled cognitive-memory-mcp
# Expected output: "disabled"
```

### Boot-Verifikation

Nach System-Reboot:

```bash
# Service Status prüfen (should be active)
systemctl status cognitive-memory-mcp

# Logs seit Boot anzeigen
journalctl -u cognitive-memory-mcp -b
```

## Health Monitoring (Watchdog)

### Watchdog-Funktionsweise

Der Service implementiert systemd Watchdog Health Monitoring:
- **Watchdog Timeout**: 60 Sekunden
- **Heartbeat Intervall**: 30-45 Sekunden (vor Timeout)
- **Bei Timeout**: systemd führt Auto-Restart durch

### Watchdog Monitoring

```bash
# Watchdog Status in systemd anzeigen
systemctl show cognitive-memory-mcp | grep -i watchdog

# Service Status anzeigt Watchdog-Informationen
systemctl status cognitive-memory-mcp
```

### Watchdog-Implementierung

Der MCP Server sendet periodische Heartbeats via `daemon.notify("WATCHDOG=1")`:
- Startup Notification: `daemon.notify("READY=1")` nach Initialisierung
- Periodic Heartbeat: `daemon.notify("WATCHDOG=1")` alle 30s
- Shutdown Notification: `daemon.notify("STOPPING=1")` bei SIGTERM

Siehe `mcp_server/__main__.py` für Implementierungsdetails.

## Troubleshooting

### Service startet nicht

**Symptom**: `systemctl start` schlägt fehl

**Debug-Schritte**:
```bash
# 1. Status prüfen
systemctl status cognitive-memory-mcp

# 2. Detaillierte Logs anzeigen
journalctl -u cognitive-memory-mcp -n 50

# 3. Service File Syntax prüfen
sudo systemd-analyze verify cognitive-memory-mcp.service
```

**Häufige Ursachen**:
- Python venv nicht gefunden: Prüfe ExecStart Path
- Environment nicht geladen: Prüfe .env.production exists
- PostgreSQL nicht verfügbar: `systemctl status postgresql`
- Permission Denied: Prüfe User=ethr und File Permissions

### Watchdog Timeout

**Symptom**: Service wird von systemd alle 60s neu gestartet

**Debug-Schritte**:
```bash
# Logs auf Watchdog Timeout prüfen
journalctl -u cognitive-memory-mcp | grep -i watchdog

# Heartbeat-Implementierung prüfen
journalctl -u cognitive-memory-mcp | grep -i "heartbeat\|notify"
```

**Lösungen**:
- Heartbeat Thread nicht gestartet: Prüfe `mcp_server/__main__.py` Watchdog Implementation
- Thread blockiert: Debug mit zusätzlichem Logging
- Temporary: WatchdogSec erhöhen (z.B. auf 120) für Debugging

### Environment Loading Fehler

**Symptom**: Service startet, aber lädt Development Environment

**Debug-Schritte**:
```bash
# Logs auf Environment Loading prüfen
journalctl -u cognitive-memory-mcp | grep -i environment

# Expected: "Production environment loaded from /home/user/i-o/config/.env.production"
# If "Development environment loaded": Environment variable nicht gesetzt
```

**Lösung**:
- Service File prüfen: `Environment="ENVIRONMENT=production"` muss gesetzt sein
- Nach Änderung: `sudo systemctl daemon-reload && sudo systemctl restart cognitive-memory-mcp`

### Auto-Restart funktioniert nicht

**Symptom**: Service crashed aber startet nicht automatisch neu

**Debug-Schritte**:
```bash
# Restart Policy prüfen
systemctl show cognitive-memory-mcp | grep Restart

# Should show: Restart=always, RestartSec=10
```

**Lösung**:
- Service File prüfen: `Restart=always` und `RestartSec=10` gesetzt
- Manueller Restart Test: `sudo kill -9 $(systemctl show -p MainPID cognitive-memory-mcp | cut -d= -f2)`
- Wait 10s, then check: `systemctl status cognitive-memory-mcp`

### Logs nicht sichtbar

**Symptom**: `journalctl -u cognitive-memory-mcp` zeigt keine Logs

**Debug-Schritte**:
```bash
# SyslogIdentifier prüfen
systemctl show cognitive-memory-mcp | grep SyslogIdentifier

# Logs mit anderem Identifier suchen
journalctl SYSLOG_IDENTIFIER=cognitive-memory-mcp

# Alle systemd Unit Logs prüfen
journalctl -u cognitive-memory-mcp --no-pager
```

**Lösung**:
- Service File prüfen: `SyslogIdentifier=cognitive-memory-mcp` gesetzt
- `StandardOutput=journal` und `StandardError=journal` gesetzt

## Deinstallation

Falls Service entfernt werden soll:

```bash
# 1. Service stoppen
sudo systemctl stop cognitive-memory-mcp

# 2. Auto-Start deaktivieren
sudo systemctl disable cognitive-memory-mcp

# 3. Service File entfernen
sudo rm /etc/systemd/system/cognitive-memory-mcp.service

# 4. Systemd Daemon reload
sudo systemctl daemon-reload
```

## Referenzen

- **Architecture**: `bmad-docs/architecture.md` - Service Management mit systemd
- **Production Setup**: `docs/production-checklist.md` - Environment Configuration
- **Story 3.8**: `bmad-docs/stories/3-8-mcp-server-daemonization-auto-start.md` - Acceptance Criteria
- **systemd Manual**: `man systemd.service`, `man systemd-analyze`
