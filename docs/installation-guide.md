# Installation Guide - Setup von Scratch

**Version:** 3.1.0-Hybrid
**Ziel:** Komplettes Setup des Cognitive Memory Systems auf einem neuen System

Dieser Guide führt Schritt für Schritt durch die Installation auf einem Linux System (Arch Linux empfohlen).

## 1. Prerequisites

### System Requirements

**Betriebssystem:**
- Arch Linux (empfohlen) oder Ubuntu 20.04+
- sudo/Zugriff auf Administrator-Rechte
- Internetverbindung für Downloads und API-Zugriffe

**Hardware Requirements (Minimum):**
- RAM: 2GB (PostgreSQL + MCP Server)
- CPU: 2 Cores (für embedding generation + search)
- Storage: 10GB freier Speicherplatz
- Netzwerk: Stabile Internetverbindung für API-Aufrufe

**Software Requirements:**
- Python 3.11+ (wird mit installiert)
- PostgreSQL 15+ (wird installiert)
- Git (für Source Code)

### Externe Accounts erforderlich

**API Keys (kostenpflichtig):**
- **OpenAI API Key:** Für embeddings (text-embedding-3-small)
  - Kosten: ~€0.06/mo bei 3M tokens
  - Bekommen: https://platform.openai.com/api-keys
- **Anthropic API Key:** Für Haiku Evaluation und GPT-4o Dual Judge
  - Kosten: ~€2-3/mo bei normaler Nutzung
  - Bekommen: https://console.anthropic.com/

**Optional:**
- **Claude Code MAX Subscription:** Für interne LLM Operations (€0/mo)
  - Query Expansion und CoT Generation laufen intern
  - Gilt als Voraussetzung für volles System

### Projekt-Setup

```bash
# Klonen des Repositories
git clone https://github.com/ethrdev/i-o.git
cd i-o

# Prüfen der Projektstruktur
ls -la
# Erwartet: README.md, pyproject.toml, mcp_server/, docs/, etc.
```

## 2. PostgreSQL + pgvector Installation

### Arch Linux Installation

```bash
# PostgreSQL Server installieren
sudo pacman -S postgresql

# PostgreSQL initialisieren (nur falls noch nicht geschehen)
sudo -u postgres initdb -D /var/lib/postgres/data

# PostgreSQL starten und für Autostart einrichten
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Status prüfen (sollte "active (running)" zeigen)
systemctl status postgresql
```

### pgvector Installation

**Option A: AUR Package (empfohlen)**
```bash
# AUR helper (yay) installieren falls nicht vorhanden
sudo pacman -S --needed git base-devel
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si
cd .. && rm -rf yay

# pgvector über AUR installieren
yay -S pgvector

# Installation prüfen
ls /usr/lib/postgresql/ | grep vector
```

**Option B: Source Compilation**
```bash
# Build dependencies installieren
sudo pacman -S base-devel git

# pgvector klonen und kompilieren
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Aufräumen
cd ..
rm -rf pgvector
```

### Database und User Creation

```bash
# Als postgres User anmelden
sudo -u postgres psql

# In PostgreSQL Shell ausführen:
CREATE DATABASE cognitive_memory;
CREATE USER mcp_user WITH PASSWORD 'ihr_sicheres_passwort_hier';
GRANT ALL PRIVILEGES ON DATABASE cognitive_memory TO mcp_user;

# Mit neuer Datenbank verbinden
\c cognitive_memory;

# pgvector Extension aktivieren
CREATE EXTENSION vector;

# Extension prüfen
SELECT * FROM pg_extension WHERE extname='vector';

# PostgreSQL Shell verlassen
\q
```

## 3. Python Environment Setup

### Poetry Dependency Management

```bash
# Poetry installieren (falls nicht vorhanden)
curl -sSL https://install.python-poetry.org | python3 -

# Projekt Dependencies installieren
poetry install

# Virtuelle Environment aktivieren (für manuelle Tests)
source $(poetry env info --path)/bin/activate

# Python Version prüfen (sollte 3.11+ sein)
python --version
```

### Environment Konfiguration

```bash
# .env.template kopieren und anpassen
cp .env.template .env.development

# Passwort in .env.development ersetzen
sed -i 's/${MCP_POSTGRES_PASSWORD}/ihr_sicheres_passwort_hier/' .env.development

# Dateirechte prüfen (sollte 600 sein)
ls -la .env.development
chmod 600 .env.development

# API Keys hinzufügen (Platzhalter ersetzen)
nano .env.development
# Folgende Zeilen anpassen:
# OPENAI_API_KEY=sk-ihr-echter-openai-key
# ANTHROPIC_API_KEY=sk-ant-ihr-echter-anthropic-key
```

### Environment Variablen verifizieren

```bash
# Test der Environment Konfiguration
poetry run python -c "
import os
from dotenv import load_dotenv
load_dotenv('.env.development')
print('DATABASE_URL:', os.getenv('DATABASE_URL'))
print('OPENAI_API_KEY:', os.getenv('OPENAI_API_KEY', 'NOT_SET'))
print('ANTHROPIC_API_KEY:', os.getenv('ANTHROPIC_API_KEY', 'NOT_SET'))
"
```

## 4. Database Migrations

### Schema Migration ausführen

```bash
# Projekt-Verzeichnis sicherstellen
pwd  # Sollte /path/to/i-o sein

# Migration mit Poetry ausführen
PGPASSWORD=ihr_sicheres_passwort_hier psql \
    -U mcp_user \
    -d cognitive_memory \
    -f mcp_server/db/migrations/001_initial_schema.sql

# Erfolgsprüfung: Tabellen anzeigen (sollten 10 Tabellen zeigen)
PGPASSWORD=ihr_sicheres_passwort_hier psql \
    -U mcp_user \
    -d cognitive_memory \
    -c "\dt"

# Erwartete Tabellen:
# l0_raw, l2_insights, working_memory, episode_memory, stale_memory
# ground_truth, golden_test_set, model_drift_log, api_cost_log, api_retry_log
```

### Indexe verifizieren

```bash
# Indexe anzeigen (sollten mehrere Indexe zeigen)
PGPASSWORD=ihr_sicheres_passwort_hier psql \
    -U mcp_user \
    -d cognitive_memory \
    -c "\di"

# pgvector Extension prüfen
PGPASSWORD=ihr_sicheres_passwort_hier psql \
    -U mcp_user \
    -d cognitive_memory \
    -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"
```

## 5. MCP Server Configuration

### MCP Server Test

```bash
# MCP Server manuell starten zum Testen
poetry run python -m mcp_server --help

# Server im interaktiven Modus starten (kurzer Test)
poetry run python -m mcp_server &
SERVER_PID=$!

# Warten und Server beenden
sleep 3
kill $SERVER_PID 2>/dev/null || true
```

### Claude Code Integration (.mcp.json)

**WICHTIG: Claude Code verwendet `.mcp.json` im Projekt-Root!**

```bash
# Python Pfad ermitteln (Poetry Environment)
PYTHON_PATH=$(poetry run which python)
echo "Python Path: $PYTHON_PATH"

# .mcp.json erstellen
cat > .mcp.json << EOF
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "/bin/bash",
      "args": [
        "-c",
        "cd $(pwd) && DATABASE_URL='postgresql://mcp_user:ihr_sicheres_passwort_hier@localhost:5432/cognitive_memory' ANTHROPIC_API_KEY='$(grep ANTHROPIC_API_KEY .env.development | cut -d'=' -f2)' OPENAI_API_KEY='$(grep OPENAI_API_KEY .env.development | cut -d'=' -f2)' ENVIRONMENT='development' $PYTHON_PATH -m mcp_server"
      ]
    }
  }
}
EOF

# Dateirechte setzen
chmod 644 .mcp.json
```

### Alternative MCP Konfiguration (für Testing)

```bash
# Für minimale Tests ohne API Keys
cat > .mcp.json << EOF
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "/bin/bash",
      "args": [
        "-c",
        "cd $(pwd) && DATABASE_URL='postgresql://mcp_user:ihr_sicheres_passwort_hier@localhost:5432/cognitive_memory' ANTHROPIC_API_KEY='sk-ant-api03-YOUR_ANTHROPIC_API_KEY' OPENAI_API_KEY='sk-placeholder' ENVIRONMENT='development' $PYTHON_PATH -m mcp_server"
      ]
    }
  }
}
EOF
```

## 6. Verification Checklist

### System Health Checks

```bash
# 1. PostgreSQL Service Status
echo "=== 1. PostgreSQL Status ==="
systemctl status postgresql --no-pager -l

# 2. pgvector Extension
echo -e "\n=== 2. pgvector Extension ==="
PGPASSWORD=ihr_sicheres_passwort_hier psql \
    -U mcp_user \
    -d cognitive_memory \
    -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"

# 3. MCP Server Startup Test
echo -e "\n=== 3. MCP Server Test ==="
timeout 10s poetry run python -m mcp_server || echo "Server startup test completed"

# 4. Python Dependencies
echo -e "\n=== 4. Python Dependencies ==="
poetry run python -c "import mcp_server; print('✅ MCP Server module import successful')"

# 5. Database Connection Test
echo -e "\n=== 5. Database Connection Test ==="
poetry run python -c "
import os
from dotenv import load_dotenv
load_dotenv('.env.development')
from mcp_server.db.connection import get_connection
try:
    conn = get_connection()
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"
```

### Claude Code Integration Test

**Schritte in Claude Code:**

1. **Claude Code neustarten** (damit .mcp.json geladen wird)
2. **MCP Server prüfen**: Tools sollten unter `/mcp` verfügbar sein
3. **Ping Test ausführen**:
   ```
   Führe den MCP Tool "ping" aus
   ```
   Erwartete Antwort: `{"content": [{"type": "text", "text": "pong"}]}`

### Erwartete MCP Tools und Resources

**Tools (7 erwartet):**
- `ping` - Health check
- `store_raw_dialogue` - L0 storage
- `compress_to_l2_insight` - L2 storage mit embeddings
- `hybrid_search` - Semantic + keyword search
- `update_working_memory` - Working memory management
- `store_episode` - Episode storage
- `store_dual_judge_scores` - Dual judge evaluation
- `get_golden_test_results` - Model drift detection

**Resources (5 erwartet):**
- `memory://l2-insights` - L2 insight retrieval
- `memory://working-memory` - Working memory state
- `memory://episode-memory` - Episode retrieval
- `memory://l0-raw` - Raw dialogue transcripts
- `memory://stale-memory` - Archived items

### Final Verification Checklist

- [ ] **PostgreSQL running**: `systemctl status postgresql` zeigt "active (running)"
- [ ] **pgvector Extension active**: `SELECT * FROM pg_extension WHERE extname='vector';` zeigt Extension
- [ ] **MCP Server starts ohne errors**: `poetry run python -m mcp_server --help` funktioniert
- [ ] **Claude Code connects to MCP Server**: Tools sind unter `/mcp` sichtbar
- [ ] **ping Tool returns "pong"**: Grundlegende MCP-Konnektivität funktioniert
- [ ] **Database Schema erstellt**: `\dt` zeigt alle 10 Tabellen
- [ ] **Environment Variables geladen**: API Keys und Database URL konfiguriert
- [ ] **Poetry Dependencies installiert**: `poetry install` erfolgreich abgeschlossen

## Nächste Schritte

Nach erfolgreicher Installation:

1. **[Operations Manual](./operations-manual.md)** lesen für daily operations
2. **[Troubleshooting Guide](./troubleshooting.md)** für Problembehandlung
3. **Golden Test Set** anlegen für model drift detection
4. **Budget Monitoring** konfigurieren für cost tracking

## Troubleshooting

### Häufige Issues

**PostgreSQL Connection Failed:**
```bash
# Service Status prüfen
systemctl status postgresql

# Connection testen
psql -U mcp_user -d cognitive_memory -h localhost

# Port prüfen
ss -tlnp | grep :5432
```

**MCP Server nicht sichtbar:**
```bash
# .mcp.json prüfen
cat .mcp.json

# Python Pfad prüfen
poetry run which python

# Manuelles Server-Test
poetry run python -m mcp_server
```

**API Key Errors:**
```bash
# Environment prüfen
grep API_KEY .env.development

# Test mit Platzhalter-Keys
# Führe MCP Server Test mit Platzhalter-Keys aus
```

---

*Installation Guide erstellt am 2025-11-24*
*Projekt: Cognitive Memory System v3.1.0-Hybrid*
