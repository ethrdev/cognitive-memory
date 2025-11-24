# Cognitive Memory v3.1.0-Hybrid

Ein hybrides kognitives Speichersystem, das MCP (Model Context Protocol) Server mit PostgreSQL + pgvector für effiziente Vektor- und Keyword-Suche kombiniert.

## Überblick

Das Cognitive Memory System ist eine fortschrittliche Speicherarchitektur, die:

- **Hybride Suche**: Kombiniert semantische Ähnlichkeit (Vektoren) mit keyword-basierter Suche
- **Drei Ebenen**: L0 Raw Memory, L1 Working Memory, L2 Insights
- **MCP Integration**: Vollständige Unterstützung für Model Context Protocol Tools und Resources
- **Ground Truth**: Integriertes Dual-Judge-System für Qualitätsvalidierung
- **Skalierbarkeit**: PostgreSQL + pgvector für hohe Performance

## System Requirements

### Minimum Requirements
- **Python**: 3.11+ (getestet mit 3.13)
- **PostgreSQL**: 15+ (wird in Story 1.2 installiert)
- **pgvector**: Extension (wird in Story 1.2 installiert)
- **RAM**: Minimum 4GB, empfohlen 8GB+
- **Speicher**: Minimum 10GB freier Speicherplatz

### API Keys erforderlich
- OpenAI API Key (für Embeddings und GPT-4o)
- Anthropic API Key (für Claude/Haiku)

## Installation

### 1. Repository klonen
```bash
git clone <repository-url>
cd i-o
```

### 2. Python Environment einrichten
```bash
# Python 3.11+ verifizieren
python3 --version

# Virtual Environment erstellen
python3 -m venv venv

# Virtual Environment aktivieren
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate     # Windows
```

### 3. Dependencies installieren
```bash
# Mit pip (empfohlen für dieses Projekt)
pip install --upgrade pip
pip install -r requirements.txt

# Alternativ mit Poetry (falls installiert)
poetry install
```

## Environment Setup

### 1. Environment Datei erstellen
```bash
# Template kopieren
cp .env.template .env.development

# Permissions setzen (Linux/Mac)
chmod 600 .env.development
```

### 2. API Keys konfigurieren
Editiere `.env.development` und füge deine API Keys ein:

```bash
# OpenAI API Key (für Embeddings und GPT-4o)
OPENAI_API_KEY=sk-your-echter-openai-api-key-hier

# Anthropic API Key (für Claude/Haiku)
ANTHROPIC_API_KEY=sk-ant-your-echter-anthropic-api-key-hier

# Semantic Fidelity Threshold (Optional, Default: 0.5)
FIDELITY_THRESHOLD=0.5

# PostgreSQL Credentials (Placeholder für Story 1.2)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=cognitive_memory
POSTGRES_USER=mcp_user
POSTGRES_PASSWORD=changeme
```

**Wichtig:**
- `OPENAI_API_KEY` ist erforderlich für das `compress_to_l2_insight` Tool
- `FIDELITY_THRESHOLD` steuert die Qualitätsschwelle für semantische Kompression (0.0-1.0)

### 3. Konfiguration anpassen
Die `config/config.yaml` enthält environment-spezifische Einstellungen:
- `base`: Gemeinsame Konfiguration
- `development`: Entwicklungseinstellungen
- `production`: Produktionseinstellungen

## Quick Start

### 1. Development Umgebung starten
```bash
# Virtual Environment aktivieren
source venv/bin/activate

# Environment laden
export $(cat .env.development | xargs)
```

### 2. Pre-commit Hooks installieren
```bash
# Hooks installieren (einmalig)
pre-commit install

# Testen
pre-commit run --all-files
```

### 4. PostgreSQL + pgvector Setup (Story 1.2)
```bash
# PostgreSQL Server installieren (Arch Linux)
sudo pacman -S postgresql

# PostgreSQL initialisieren (falls nicht bereits vorhanden)
sudo -u postgres initdb -D /var/lib/postgres/data

# PostgreSQL Service starten und enablen
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Service Status prüfen
systemctl status postgresql  # sollte "active (running)" anzeigen
```

#### pgvector Extension Installation

**Option A: AUR Package (empfohlen)**
```bash
# AUR Helper yay verwenden
yay -S pgvector
```

**Option B: From Source**
```bash
# Build-Dependencies installieren
sudo pacman -S base-devel git

# pgvector kompilieren
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

#### Datenbank und User erstellen
```bash
# PostgreSQL Shell als postgres User öffnen
sudo -u postgres psql

# In der PostgreSQL Shell ausführen:
CREATE DATABASE cognitive_memory;
CREATE USER mcp_user WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE cognitive_memory TO mcp_user;
\c cognitive_memory
CREATE EXTENSION vector;
\q  # Shell verlassen
```

#### Database Schema erstellen
```bash
# Migration ausführen (ersetze PASSWORD mit deinem echten Passwort)
PGPASSWORD=secure_password_here psql -U mcp_user -d cognitive_memory -f mcp_server/db/migrations/001_initial_schema.sql

# Schema validieren
PGPASSWORD=secure_password_here psql -U mcp_user -d cognitive_memory -c "\dt"  # sollte 6 Tabellen zeigen
```

### 5. Dependencies verifizieren
```bash
# Teste Import aller Haupt-Dependencies
python -c "
import mcp, psycopg2, openai, anthropic, numpy, streamlit, scipy
print('✅ Alle Dependencies erfolgreich importiert')
"

# Teste PostgreSQL Connection (ersetze .env.development Passwort)
python tests/test_database.py
```

### 3. Environment Configuration für PostgreSQL
```bash
# .env.development mit echtem PostgreSQL Passwort aktualisieren
POSTGRES_PASSWORD=secure_password_here  # ersetze mit deinem Passwort aus der User-Erstellung
```

**Wichtig**: PostgreSQL Setup ist jetzt Teil von Story 1.2. Siehe "PostgreSQL + pgvector Setup" oben.

## Projektstruktur

```
i-o/
├── mcp_server/              # MCP Server Implementation
│   ├── __main__.py         # Server Entry Point (stdio transport)
│   ├── tools/              # MCP Tool Implementierungen (7 Tools)
│   ├── resources/          # MCP Resource Implementierungen (5 Resources)
│   ├── db/                 # Database Layer
│   │   ├── connection.py   # PostgreSQL Connection Pool
│   │   ├── migrations/     # Schema Migrations
│   │   └── models.py       # Data Models
│   ├── external/           # External API Clients
│   │   ├── openai_client.py
│   │   └── anthropic_client.py
│   ├── utils/              # Utilities
│   └── config.py           # Configuration Management
├── .env.template           # Environment Template (PROJECT ROOT)
├── .env.development        # Development Environment (PROJECT ROOT, git-ignored)
├── tests/                  # Tests (Unit & Integration)
├── docs/                   # Dokumentation
├── config/                 # Konfigurationsdateien
│   └── config.yaml         # Configuration Settings
├── scripts/                # Automation Scripts
├── streamlit_apps/         # Streamlit UIs (Ground Truth Labeling)
├── memory/                 # L2 Insights Git Backup
├── backups/                # PostgreSQL Backups
├── systemd/                # Systemd Service Files
├── pyproject.toml          # Poetry Dependencies & Configuration
├── requirements.txt        # pip Dependencies (Fallback)
└── README.md              # Diese Datei
```

## MCP Tools & Resources

### Tools (7)
1. **l0_raw_storage** - Speichert rohe Dialoge
2. **l2_insights_compression** - Komprimiert zu L2 Insights
3. **hybrid_search** - Hybrid-Suche (semantisch + keyword)
4. **working_memory_management** - Working Memory Verwaltung
5. **episode_storage** - Episoden-Speicherung
6. **dual_judge_scoring** - Dual-Judge Bewertung
7. **golden_test_results** - Golden Test Ergebnisse

### Resources (5)

Alle MCP Resources sind Read-Only und verwenden das `memory://` URI-Schema. Sie ermöglichen Claude Code, Memory-State vor Aktionen zu laden.

#### 1. memory://l2-insights
L2 Insights mit semantischer Suche.

```bash
# Basic usage
memory://l2-insights?query=machine%20learning&top_k=5

# Parameters:
# - query (required): Suchtext für semantische Suche
# - top_k (optional): Anzahl der Ergebnisse (default: 5, max: 100)
```

**Response Format:**
```json
[
  {
    "id": 1,
    "content": "Machine learning requires careful feature engineering...",
    "score": 0.95,
    "source_ids": [1, 2, 3]
  }
]
```

#### 2. memory://working-memory
Current Working Memory Items, sortiert nach last_accessed.

```bash
# Usage (keine Parameter)
memory://working-memory
```

**Response Format:**
```json
[
  {
    "id": 1,
    "content": "Current task: Implement MCP resources",
    "importance": 0.8,
    "last_accessed": "2025-11-12T14:30:00Z",
    "created_at": "2025-11-12T13:00:00Z"
  }
]
```

#### 3. memory://episode-memory
Ähnliche vergangene Episoden mit Similarity-Filtering (Top-3).

```bash
# Basic usage
memory://episode-memory?query=how%20to%20implement%20mcp&min_similarity=0.70

# Parameters:
# - query (required): Suchtext für semantische Suche
# - min_similarity (optional): Mindest-Similarity (default: 0.70, range: 0.0-1.0)
```

**Response Format:**
```json
[
  {
    "id": 1,
    "query": "How to implement MCP server resources?",
    "reward": 0.8,
    "reflection": "Use @server.read_resource() decorator and register resource handlers",
    "similarity": 0.85
  }
]
```

#### 4. memory://l0-raw
Raw Dialogtranskripte mit Session- und Datum-Filtering.

```bash
# Basic usage (limitiert zu 100 Einträgen)
memory://l0-raw?limit=50

# Mit Session-Filter
memory://l0-raw?session_id=123e4567-e89b-12d3-a456-426614174000

# Mit Datum-Range
memory://l0-raw?date_range=2025-11-01:2025-11-12&limit=100

# Parameters:
# - session_id (optional): UUID für Session-Filtering
# - date_range (optional): YYYY-MM-DD:YYYY-MM-DD Format
# - limit (optional): Anzahl der Ergebnisse (default: 100, max: 1000)
```

**Response Format:**
```json
[
  {
    "id": 1,
    "session_id": "123e4567-e89b-12d3-a456-426614174000",
    "timestamp": "2025-11-12T13:00:00Z",
    "speaker": "user",
    "content": "I need help implementing MCP resources",
    "metadata": {"type": "question"}
  }
]
```

#### 5. memory://stale-memory
Archivierte Memory Items mit Importance-Filtering.

```bash
# Alle archivierten Items
memory://stale-memory

# Mit Importance-Filter
memory://stale-memory?importance_min=0.8

# Parameters:
# - importance_min (optional): Mindest-Importance (range: 0.0-1.0)
```

**Response Format:**
```json
[
  {
    "id": 1,
    "original_content": "Old todo: Set up development environment",
    "archived_at": "2025-11-05T10:00:00Z",
    "importance": 0.3,
    "reason": "LRU_EVICTION"
  }
]
```

### Error Handling

Alle Resources verwenden konsistentes Error Handling:

- **400 Bad Request**: Invalid Parameter (z.B. empty query, invalid date format)
- **Empty Array `[]`**: Keine Ergebnisse (nicht 404)
- **404 Not Found**: Nur bei invalid Resource URIs (z.B. `memory://invalid-resource`)

### Claude Code Usage Examples

```bash
# Lade Kontext vor Answer Generation
read_resource("memory://episode-memory?query=user%20query&min_similarity=0.7")
read_resource("memory://l2-insights?query=user%20query&top_k=5")

# Prüfe aktuellen Working Memory State
read_resource("memory://working-memory")

# Lade historische Kontexte
read_resource("memory://l0-raw?session_id=current-session")
read_resource("memory://stale-memory?importance_min=0.8")
```

## Production Deployment

### Environment Setup

Für den produktiven Einsatz müssen Sie die Datenbank-Konfiguration über Environment Variables setzen:

```bash
# Datenbank-Passwort setzen (erforderlich)
export MCP_POSTGRES_PASSWORD="<your-secure-database-password>"

# Optionale API Keys
export OPENAI_API_KEY="<your-openai-api-key>"
export ANTHROPIC_API_KEY="<your-anthropic-api-key>"
```

### Secrets Management

**Empfohlene Production-Setup mit Secrets Management:**

#### AWS Secrets Manager
```bash
export MCP_POSTGRES_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id mcp/postgres/password \
  --query SecretString \
  --output text)
```

#### HashiCorp Vault
```bash
export MCP_POSTGRES_PASSWORD=$(vault kv get -field=password secret/mcp/postgres)
```

#### Kubernetes Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-secrets
type: Opaque
data:
  postgres-password: <base64-encoded-password>
  openai-api-key: <base64-encoded-key>
  anthropic-api-key: <base64-encoded-key>
```

### Deployment Verification

```bash
# Überprüfen, ob die Environment Variable gesetzt ist
echo $MCP_POSTGRES_PASSWORD  # Sollte das Passwort ausgeben

# MCP Server starten
python -m mcp_server

# Test-Query ausführen
echo '{"tool": "ping"}' | python -m mcp_server
```

### Production-Konfiguration

1. **Kopieren Sie `.env.template` nach `.env.production`**
2. **Passen Sie die Konfiguration an Ihre Produktionsumgebung an**
3. **Setzen Sie alle erforderlichen Environment Variables**
4. **Stellen Sie sicher, dass PostgreSQL mit pgvector läuft**

#### Beispiel .env.production
```bash
ENVIRONMENT=production
POSTGRES_HOST=your-production-db-host
POSTGRES_PORT=5432
POSTGRES_DB=cognitive_memory
POSTGRES_USER=mcp_user
# Wird über MCP_POSTGRES_PASSWORD environment variable gesetzt
POSTGRES_PASSWORD=${MCP_POSTGRES_PASSWORD}
```

### Docker Deployment (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install poetry && poetry install --only=main

# Environment variables werden über docker-compose oder kubernetes gesetzt
CMD ["python", "-m", "mcp_server"]
```

## Development Guidelines

### Code Quality
- **Black**: Code Formatting (PEP 8)
- **Ruff**: Linting und Import-Sorting
- **MyPy**: Type Checking
- **Pre-commit Hooks**: Automatische Qualitätssicherung

### Naming Conventions
- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`

### Testing Strategy
- **Manual Testing**: Epic 1-2 (Claude Code Interface)
- **Integration Testing**: Epic 2 (End-to-End RAG Pipeline)
- **Validation Testing**: Epic 3 (Golden Test Set, 7-Day Stability)

## Usage Example

### store_raw_dialogue Tool

Store raw dialogue data from Claude Code conversations:

```python
# Claude Code MCP Aufruf
{
  "tool": "store_raw_dialogue",
  "arguments": {
    "session_id": "session-abc-123",
    "speaker": "user",
    "content": "Wie funktioniert das RAG System?",
    "metadata": {
      "model": "claude-sonnet-4",
      "temperature": 0.7,
      "tags": ["frage", "system"]
    }
  }
}

# Success Response
{
  "id": 12345,
  "timestamp": "2025-11-12T14:30:00Z",
  "session_id": "session-abc-123",
  "status": "success"
}
```

### update_working_memory Tool

Manage working memory with LRU eviction and importance-based protection:

```python
# Claude Code MCP Aufruf - Normal Priority Item
{
  "tool": "update_working_memory",
  "arguments": {
    "content": "User asked about RAG system implementation details",
    "importance": 0.6
  }
}

# Success Response (No Eviction)
{
  "added_id": 456,
  "evicted_id": null,
  "archived_id": null,
  "status": "success"
}

# Claude Code MCP Aufruf - Critical Priority Item
{
  "tool": "update_working_memory",
  "arguments": {
    "content": "Critical: User authentication system is failing",
    "importance": 0.9
  }
}

# Success Response (No Eviction - item is protected)
{
  "added_id": 457,
  "evicted_id": null,
  "archived_id": null,
  "status": "success"
}

# Claude Code MCP Aufruf - Adding 11th Item (Triggers Eviction)
{
  "tool": "update_working_memory",
  "arguments": {
    "content": "New context item that exceeds capacity",
    "importance": 0.5
  }
}

# Success Response (LRU Eviction Triggered)
{
  "added_id": 458,
  "evicted_id": 448,
  "archived_id": 123,
  "status": "success"
}
```

#### LRU Eviction mit Importance Override

Das Working Memory implementiert ein intelligentes Eviction-System:

- **Kapazität**: Maximum 10 Items (konfigurierbar)
- **LRU Sortierung**: Items werden nach `last_accessed` sortiert (älteste zuerst)
- **Importance Protection**: Items mit `importance > 0.8` werden nicht evictet
- **Force Eviction**: Wenn alle Items critical sind, wird das älteste critical Item evictet
- **Stale Memory Archive**: Evictete Items werden in `stale_memory` archiviert

#### Parameter

- **content** (required, string): Der zu speichernde Inhalt
- **importance** (optional, number, default 0.5): Wichtigkeitsscore (0.0-1.0)
  - `0.0-0.8`: Normal Priority (kann evictet werden)
  - `0.8-1.0`: Critical Priority (geschützt vor LRU Eviction)

#### Response Format

- **added_id**: ID des neu hinzugefügten Items
- **evicted_id**: ID des evicteten Items (null wenn keine Eviction)
- **archived_id**: ID des archivierten Items in stale_memory (null wenn keine Eviction)
- **status**: "success" bei Erfolg, oder "error" bei Fehlern

## Nächste Schritte

### Story 1.2: PostgreSQL + pgvector Setup
- PostgreSQL 15+ Installation
- pgvector Extension Setup
- Database Schema Creation
- Connection Testing

### Story 1.3: MCP Server Grundstruktur
- MCP Server Framework Setup
- Tool/Resource Framework
- Basic Connection Handling

## MCP Server Setup

### Voraussetzungen
- PostgreSQL läuft mit pgvector Extension (Story 1.2)
- Environment konfiguriert (.env.development)
- Python Dependencies installiert

### 1. MCP Server starten
```bash
# Virtual Environment aktivieren
source venv/bin/activate

# Environment Variablen laden
export $(cat .env.development | xargs)

# MCP Server starten (stdio transport)
python -m mcp_server
```

### 2. Claude Code MCP Konfiguration
Erstelle oder aktualisiere `~/.config/claude-code/mcp-settings.json`:

```json
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/pfad/zu/i-o",
      "env": {
        "LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

**Wichtig**: Ersetze `/pfad/zu/i-o` mit dem absoluten Pfad zu deinem Projektverzeichnis.

### 3. Claude Code neustarten
```bash
# Claude Code beenden und neu starten
# Der MCP Server sollte automatisch verbunden werden
```

### 4. Validierung
```bash
# MCP Server mit MCP Inspector testen
npx @modelcontextprotocol/inspector python -m mcp_server

# Oder Integration Tests ausführen
pytest tests/test_mcp_server.py -v
```

### MCP Tools (7 implementiert)
1. **store_raw_dialogue** - L0 Raw Storage (Story 1.4)
2. **compress_to_l2_insight** - L2 Insights Storage (Story 1.5)
3. **hybrid_search** - Hybrid Search (Story 1.6)
4. **update_working_memory** - Working Memory Management (Story 1.7)
5. **store_episode** - Episode Memory Storage (Story 1.8)
6. **store_dual_judge_scores** - Dual Judge Scoring (Story 1.11)
7. **ping** - Connectivity Test Tool ✅

### MCP Resources (5 implementiert)
1. **memory://l2-insights** - L2 Insights Read (Story 1.9)
2. **memory://working-memory** - Working Memory State (Story 1.9)
3. **memory://episode-memory** - Episode Memory Read (Story 1.9)
4. **memory://l0-raw** - L0 Raw Data Read (Story 1.9)
5. **memory://status** - Server Status ✅

## Usage Examples

### compress_to_l2_insight Tool
Komprimiert Dialoge zu semantischen Insights mit OpenAI Embeddings:

```python
# MCP Tool Call
{
    "tool": "compress_to_l2_insight",
    "arguments": {
        "content": "Discussion about machine learning algorithms and their applications in natural language processing",
        "source_ids": [1, 2, 3]  # L0 raw dialogue IDs
    }
}

# Response
{
    "id": 123,
    "embedding_status": "success",
    "fidelity_score": 0.73,
    "timestamp": "2025-11-12T14:30:00Z"
}
```

**Response Fields:**
- `id`: Generierte ID des gespeicherten L2 Insights
- `embedding_status`: "success" oder "retried" (bei Rate-Limits)
- `fidelity_score`: Information Density (0.0-1.0, höher ist besser)
- `timestamp`: ISO 8601 Timestamp der Erstellung

### store_episode Tool
Speichert verbalisierte Reflexionen mit Query Embeddings für Episode Memory (Verbal Reinforcement Learning):

```python
# MCP Tool Call
{
    "tool": "store_episode",
    "arguments": {
        "query": "How to handle errors in async code?",
        "reward": -0.3,
        "reflection": "Problem: Missed edge case in exception handling. Lesson: Always check boundary conditions and use proper error propagation."
    }
}

# Success Response
{
    "id": 456,
    "embedding_status": "success",
    "query": "How to handle errors in async code?",
    "reward": -0.3,
    "created_at": "2025-11-12T15:45:00Z"
}

# Error Response (invalid reward)
{
    "error": "Reward out of range",
    "details": "Reward 1.5 is outside valid range [-1.0, 1.0]",
    "tool": "store_episode",
    "embedding_status": "failed"
}
```

**Episode Memory Purpose:**
- **Verbal Reinforcement Learning**: Speichert Lektionen aus der Haiku API Self-Evaluation
- **Similarity Retrieval**: Top-3 Episoden mit Cosine Similarity >0.70 (FR009)
- **Query Embedding**: Nur die Query wird embedded (nicht die Reflection) für Similarity-Suche
- **Reward Scale**: -1.0 (schlechte Antwort) bis +1.0 (exzellent), Trigger-Threshold <0.3

### MCP Protocol Basics
- **Transport**: stdio (Standard für lokale MCP Server)
- **Handshake**: Server sendet protocol version und capabilities
- **Tool Discovery**: `tools/list` → alle registrierten Tools
- **Resource Discovery**: `resources/list` → alle registrierten URIs
- **Error Handling**: MCP Error Responses gemäß Spec

## Troubleshooting

### Common Issues

**1. Python Version zu alt**
```bash
# Python 3.11+ erforderlich
python3 --version  # sollte >= 3.11 sein
```

**2. Dependencies nicht gefunden**
```bash
# Virtual Environment aktivieren
source venv/bin/activate

# Dependencies reinstallieren
pip install -r requirements.txt
```

**3. Pre-commit Hooks fehlerhaft**
```bash
# Hooks reinstallieren
pre-commit uninstall
pre-commit install

# Manuelles Testen
pre-commit run --all-files
```

**4. Permissions Problem mit .env Dateien**
```bash
# Korrekte Permissions setzen
chmod 600 .env.development
```

**5. PostgreSQL Connection Issues**
```bash
# Service Status prüfen
systemctl status postgresql

# PostgreSQL Config Files prüfen
sudo -u postgres psql -c "SELECT version();"  # Verbindungstest

# Firewall prüfen (falls Connection refused)
sudo ufw status

# pgvector Extension prüfen
psql -U mcp_user -d cognitive_memory -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

**6. pgvector Installation Probleme**
```bash
# PostgreSQL Headers prüfen
ls /usr/include/postgresql/

# Manuelles pgvector Build (falls AUR fehlschlägt)
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make clean && make
sudo make install
```

## Lizenz

[License Information hier einfügen]

## Contributing

[Contributing Guidelines hier einfügen]

---

**Wichtiger Hinweis**: Dieses Projekt folgt einem strukturierten Entwicklungsprozess mit 33 Stories über 3 Epics. Story 1.1 stellt die Foundation bereit. PostgreSQL Setup folgt in Story 1.2.
