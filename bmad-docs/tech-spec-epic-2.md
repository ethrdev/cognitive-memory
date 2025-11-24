# Epic Technical Specification: RAG Pipeline & Hybrid Calibration

Date: 2025-11-14
Author: ethr
Epic ID: 2
Status: Draft

---

## Overview

Epic 2 implementiert die vollständige RAG-Pipeline mit Claude Code als primärem LLM für Bulk-Operationen (Query Expansion, CoT Generation) und externen APIs für kritische Evaluationen (Haiku für Reflexion/Evaluation). Das Epic etabliert Claude Code Integration als MCP Client, führt Query Expansion mit 3 semantischen Varianten ein, implementiert Chain-of-Thought Generation Framework, und kalibriert Hybrid Search Gewichte via Grid Search auf dem Ground Truth Set aus Epic 1. Ziel ist Precision@5 >0.75 und End-to-End Latency <5s bei einem Budget von €1-2/mo für Entwicklung und Testing.

## Objectives and Scope

### In-Scope:
- Claude Code MCP Client Setup & Integration Testing (Story 2.1)
- Query Expansion Logik intern in Claude Code mit 3 semantischen Varianten (Story 2.2)
- Chain-of-Thought (CoT) Generation Framework mit strukturierter Ausgabe (Story 2.3)
- Externe API Setup für Haiku Evaluation und Reflexion (Story 2.4)
- Self-Evaluation mit Haiku API (Reward -1.0 bis +1.0) (Story 2.5)
- Reflexion-Framework mit Verbal Reinforcement Learning (Story 2.6)
- End-to-End RAG Pipeline Testing über alle Komponenten (Story 2.7)
- Hybrid Weight Calibration via Grid Search auf Ground Truth Set (Story 2.8)
- Precision@5 Validierung auf Ground Truth Set (Story 2.9)

### Out-of-Scope:
- Neue MCP Tools oder Resources (werden in Epic 1 implementiert)
- Production Monitoring und Model Drift Detection (Epic 3)
- Budget Dashboard und Cost Optimization (Epic 3)
- PostgreSQL Backup und Recovery (Epic 3)
- Golden Test Set Creation (Epic 3)

## System Architecture Alignment

Die Epic 2 Implementierung nutzt die bestehende MCP Server Infrastruktur aus Epic 1 und fügt Claude Code als primären MCP Client hinzu. Die RAG-Pipeline verläuft primär in Claude Code (Query Expansion, CoT Generation) mit strategischen externen API Calls für Evaluation (Haiku) und Embeddings (OpenAI). Das Hybrid Search System aus Epic 1 wird durch Grid Search Kalibrierung für domänenspezifische Optimierung erweitert. Die Architektur etabliert klare Verantwortlichkeiten: Claude Code für generative Tasks (€0/mo), MCP Server für Persistence und API-Koordination, externe APIs für deterministische Evaluation.

## Detailed Design

### Services and Modules

| Module | Verantwortlichkeiten | Inputs | Outputs | Owner |
|--------|---------------------|---------|---------|-------|
| **Claude Code MCP Client** | MCP Protocol Kommunikation, Tool Calls, Resource Reads | User Queries, MCP Server Responses | Tool Invocations, Resource Data | Claude Code |
| **Query Expansion Engine** | Generiert 3 semantische Varianten pro Query | Original User Query | 4 Queries (Original + 3 Varianten) | Claude Code |
| **CoT Generator** | Chain-of-Thought Reasoning (Thought → Reasoning → Answer → Confidence) | Retrieved Context, Episode Memory | Strukturierte Antwort mit Metadaten | Claude Code |
| **Haiku Evaluation Client** | Self-Evaluation mit Reward Scores (-1.0 bis +1.0) | Query, Context, Generated Answer | Reward Score, Reasoning | MCP Server |
| **Reflexion Engine** | Verbalisierte Lektionen bei schlechten Bewertungen | Poor Answer + Evaluation Reasoning | Verbal Reflexion (Problem + Lesson) | MCP Server |
| **Hybrid Weight Calibrator** | Grid Search für optimale semantic/keyword Gewichte | Ground Truth Set, Gewicht-Grid | Kalibrierte Gewichte (config.yaml) | MCP Server |

### Data Models and Contracts

#### Evaluation Results Model
```python
@dataclass
class EvaluationResult:
    query: str
    retrieved_context: List[L2Insight]
    generated_answer: str
    reward_score: float  # -1.0 bis +1.0
    evaluation_reasoning: str
    confidence_score: float  # 0.0 bis 1.0
    timestamp: datetime

class Reflexion:
    problem_description: str
    lesson_learned: str
    trigger_query: str
    reward_score: float
    created_at: datetime
```

#### Query Expansion Model
```python
@dataclass
class ExpandedQuery:
    original_query: str
    variants: List[str]  # 3 semantische Varianten
    expansion_strategy: str  # "paraphrase", "perspective_shift", "keyword_focus"

class CoTResponse:
    thought: str  # Erste Intuition
    reasoning: str  # Explizite Begründung
    answer: str  # Finale Antwort
    confidence: float  # 0.0-1.0
    sources: List[int]  # L2 Insight IDs
```

#### Calibration Results Model
```python
@dataclass
class CalibrationResult:
    semantic_weight: float
    keyword_weight: float
    precision_at_5: float
    grid_search_results: List[WeightCombination]
    calibration_date: datetime
    ground_truth_queries: int
```

### APIs and Interfaces

#### Haiku Evaluation API
```python
async def evaluate_answer(
    query: str,
    context: List[L2Insight],
    answer: str,
    model: str = "claude-3-5-haiku-20241022"
) -> EvaluationResult:
    """
    Evaluiert Antwortqualität mit externer Haiku API

    Returns:
        EvaluationResult mit Reward Score (-1.0 bis +1.0)
    """
```

#### Reflexion Generation API
```python
async def generate_reflection(
    query: str,
    context: List[L2Insight],
    answer: str,
    evaluation_result: EvaluationResult
) -> Reflexion:
    """
    Generiert verbalisierte Reflexion bei schlechter Bewertung

    Trigger: Reward Score < 0.3
    """
```

#### Query Expansion Interface (intern in Claude Code)
```python
def expand_query(query: str, num_variants: int = 3) -> ExpandedQuery:
    """
    Generiert semantische Varianten für robuste Retrieval
    Intern in Claude Code, keine externen API Calls
    """
```

#### Hybrid Search Interface (existierend MCP Tool)
```python
@tool
def hybrid_search(
    query_embedding: List[float],
    query_text: str,
    top_k: int = 5,
    weights: HybridWeights = None
) -> List[SearchResult]:
    """
    Führt Hybrid Search durch mit kalibrierten Gewichten
    """
```

### Workflows and Sequencing

#### End-to-End RAG Pipeline Sequence
```
1. User Query → Claude Code
2. Query Expansion (intern):
   - Original Query
   - Paraphrase Variant
   - Perspective Shift Variant
   - Keyword Focus Variant
3. OpenAI Embeddings API (parallel, 4 Queries)
4. MCP Tool: hybrid_search (4× parallel, RRF Fusion)
5. MCP Resource: memory://episode-memory (ähnliche Episodes laden)
6. CoT Generation (intern):
   - Thought: Erste Intuition
   - Reasoning: Begründung mit Context + Episodes
   - Answer: Finale Antwort
   - Confidence: Score basierend auf Retrieval Quality
7. Haiku API Evaluation:
   - Input: Query + Context + Answer
   - Output: Reward Score + Reasoning
8. Conditional Reflexion (Reward < 0.3):
   - Haiku API: Reflexion generieren
   - MCP Tool: store_episode
9. MCP Tool: update_working_memory (LRU Eviction)
10. User Response: Answer + Confidence + Sources
```

#### Grid Search Calibration Sequence
```
1. Load Ground Truth Set (50-100 Queries aus Epic 1)
2. Define Weight Grid:
   - semantic: [0.5, 0.6, 0.7, 0.8, 0.9]
   - keyword: [0.5, 0.4, 0.3, 0.2, 0.1]
3. For Each Weight Combination:
   - Run hybrid_search für alle Ground Truth Queries
   - Calculate Precision@5 für jede Query
   - Average Precision@5 über alle Queries
4. Select Best Weight Combination:
   - Highest Precision@5
   - Expected: semantic=0.8, keyword=0.2
5. Update config.yaml mit kalibrierten Gewichten
6. Document Results in /docs/calibration-results.md
```

#### Reflexion Trigger Logic
```
IF evaluation_result.reward_score < 0.3:
    trigger_reflection()
ELSE:
    log_successful_evaluation()

Reflexion Process:
1. Call Haiku API with structured prompt
2. Parse "Problem" and "Lesson" sections
3. Store via MCP Tool: store_episode
4. Update episode memory for future retrieval
```

## Non-Functional Requirements

### Performance

**NFR001: Latency Targets**
- **End-to-End Latency:** <5s (p95) für vollständige RAG-Pipeline
- **Query Expansion:** <0.5s (intern in Claude Code)
- **Hybrid Search:** <1s (p95) für 4× parallele `hybrid_search` Calls
- **CoT Generation:** 2-3s (längster Step, aber intern €0/mo)
- **Haiku Evaluation:** <0.5s (externe API)
- **Reflexion (conditional):** <1s (nur bei Reward <0.3)

**Performance Monitoring:**
- Latency Tracking für jeden Pipeline-Schritt
- p50, p95, p99 Percentiles für End-to-End Pipeline
- API Latency Monitoring für OpenAI und Anthropic

### Security

**API Key Management:**
- ANTHROPIC_API_KEY für Haiku Evaluation/Reflexion
- OpenAI API Key für Embeddings (bestehend aus Epic 1)
- Environment-specific .env Files (.env.development vs .env.production)
- API Keys niemals in Git committen (.gitignore konfiguriert)

**Data Security:**
- Alle sensitiven Daten lokal in PostgreSQL
- Keine Cloud-Dependencies für Datenpersistenz
- API Calls nur für Compute, nicht für Datenspeicherung

### Reliability/Availability

**API Reliability:**
- Retry-Logic mit Exponential Backoff für Haiku API
- 4 Retries mit Delays: 1s, 2s, 4s, 8s (+/- 20% Jitter)
- Fallback zu Claude Code Evaluation bei totalem Haiku Ausfall (Degraded Mode)
- Rate Limit Handling mit automatischer Recovery

**System Reliability:**
- MCP Server Auto-Restart via systemd (Epic 3)
- Graceful Degradation bei API-Ausfällen
- Error Logging für Post-Mortem Analysis
- Health Check Endpoints für Monitoring

### Observability

**Logging Requirements:**
- Strukturiertes JSON Logging für alle Pipeline-Schritte
- API Call Logs mit Token Counts und Latency
- Evaluation Results mit Reward Scores und Reasoning
- Reflexion Logs mit Trigger Conditions

**Metrics Collection:**
- Query Success Rate (>99% Ziel)
- Average Reward Scores über Zeit
- Reflexion Trigger Rate (erwartet 20-30% bei Bootstrapping)
- Cost Tracking pro API (Haiku, OpenAI Embeddings)

**Debugging Support:**
- Complete Pipeline Trace für jede Query
- Error Context mit Stack Traces
- Performance Profiles bei Latency-Issues

## Dependencies and Integrations

### Externe API Dependencies

| API | Purpose | Rate Limits | Cost Model | Fallback Strategy |
|-----|---------|-------------|------------|-------------------|
| **Anthropic Haiku API** | Self-Evaluation & Reflexion | 1000 requests/minute | €0.001 per 1K tokens (Evaluation), €0.0015 per 1K tokens (Reflexion) | Claude Code Evaluation (Degraded Mode) |
| **OpenAI Embeddings API** | Query Embeddings (4× pro Query) | 3500 requests/minute | €0.02 per 1M tokens (text-embedding-3-small) | Kein Fallback (kritisch für Retrieval) |

### Internal Dependencies

| Component | Version | Purpose | Integration Point |
|-----------|---------|---------|-------------------|
| **MCP Server** | Python 3.11+ | Persistence & API-Koordination | MCP Protocol (stdio transport) |
| **PostgreSQL + pgvector** | 15+ | Vektor-Suche & Datenspeicherung | Hybrid Search Tool Calls |
| **Ground Truth Set** | Epic 1 Output | Grid Search Kalibrierung | Story 2.8 Calibration |
| **Episode Memory** | Epic 1 Feature | Kontext für CoT Generation | memory://episode-memory Resource |

### Integration Points

#### Claude Code ↔ MCP Server Integration
```yaml
mcp_settings:
  servers:
    cognitive-memory:
      command: python
      args: ["/path/to/mcp_server/main.py"]
      env:
        ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY}"
        ENVIRONMENT: "production"
```

#### Haiku API Client Integration
```python
# mcp_server/external/anthropic_client.py
import anthropic
from typing import List, Dict, Any

class HaikuClient:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    async def evaluate_answer(
        self,
        query: str,
        context: List[str],
        answer: str
    ) -> Dict[str, Any]:
        """Self-Evaluation mit Reward Score"""

    async def generate_reflection(
        self,
        query: str,
        poor_answer: str,
        evaluation_reasoning: str
    ) -> Dict[str, Any]:
        """Verbalisierte Reflexion bei schlechter Bewertung"""
```

#### Query Expansion Integration (Claude Code intern)
```
Query Expansion Process:
1. Original Query: "Wie denke ich über Bewusstsein?"
2. Paraphrase: "Was ist meine Perspektive auf das Bewusstseinskonzept?"
3. Perspective Shift: "Meine Meinung zum Thema Bewusstsein wäre..."
4. Keyword Focus: "Bewusstsein Konzept Gedanken Meinung"
```

### Configuration Dependencies

```yaml
# config.yaml ( Epic 2 Erweiterungen )
hybrid_search_weights:
  semantic: 0.8  # Nach Grid Search Kalibrierung
  keyword: 0.2   # Nach Grid Search Kalibrierung

query_expansion:
  enabled: true
  num_variants: 3
  strategies: ["paraphrase", "perspective_shift", "keyword_focus"]

evaluation:
  model: "claude-3-5-haiku-20241022"
  temperature: 0.0  # Deterministisch für konsistente Scores
  max_tokens: 500
  reward_threshold: 0.3  # Trigger für Reflexion

reflexion:
  model: "claude-3-5-haiku-20241022"
  temperature: 0.7  # Kreativ für Reflexion
  max_tokens: 1000

api_limits:
  anthropic:
    rpm_limit: 1000
    retry_attempts: 4
    retry_delays: [1, 2, 4, 8]  # seconds
```

### Version Constraints

- **Anthropic SDK:** `anthropic>=0.30.0` (stabile Haiku API Unterstützung)
- **Python MCP SDK:** Latest (via pip install mcp)
- **PostgreSQL:** >=15 mit pgvector Extension
- **Claude Code:** Sonnet 4.5 mit MAX Subscription (für €0/mo Bulk Operations)

## Acceptance Criteria (Authoritative)

### Story 2.1: Claude Code MCP Client Setup & Integration Testing
1. **Given** MCP Server läuft lokal (Epic 1 abgeschlossen), **When** Claude Code MCP Settings konfiguriert, **Then** sind alle 7 MCP Tools und 5 Resources aufrufbar
2. **Given** Tool-Liste ist sichtbar, **Then** zeigt Claude Code `ping`, `store_raw_dialogue`, `compress_to_l2_insight`, `hybrid_search`, `update_working_memory`, `store_episode`, `store_dual_judge_scores` Tools
3. **Given** Resource-Liste ist sichtbar, **Then** zeigt Claude Code `memory://l2-insights`, `memory://working-memory`, `memory://episode-memory`, `memory://l0-raw`, `memory://stale-memory` Resources
4. **Given** Test-Tool-Call wird ausgeführt, **Then** antwortet `ping` Tool mit "pong"

### Story 2.2: Query Expansion Logik (intern in Claude Code)
1. **Given** eine User-Query wird gestellt, **When** Query Expansion durchgeführt wird, **Then** werden 3 Varianten generiert (Paraphrase, Perspektiv-Shift, Keyword-Fokus)
2. **Given** 4 Queries existieren (Original + 3 Varianten), **When** Retrieval durchgeführt wird, **Then** werden alle 4 Queries embedded und an `hybrid_search` gesendet
3. **Given** Ergebnisse von 4 Queries zurückkommen, **Then** werden Ergebnisse dedupliziert (nach L2 ID) und via RRF fusioniert
4. **Given** Expansion läuft, **Then** entstehen keine externen API-Kosten (intern in Claude Code)

### Story 2.3: Chain-of-Thought (CoT) Generation Framework
1. **Given** Retrieved Context und Episode Memory vorhanden, **When** Answer Generation durchgeführt wird, **Then** wird CoT-Struktur generiert (Thought → Reasoning → Answer → Confidence)
2. **Given** CoT generiert wird, **Then** enthält Thought erste Intuition (1-2 Sätze), Reasoning explizite Begründung (3-5 Sätze), Answer klare finale Antwort, Confidence Score 0.0-1.0
3. **Given** Confidence berechnet wird, **Then** basiert Score auf Retrieval Quality (High >0.8, Medium 0.5-0.8, Low <0.5)
4. **Given** Antwort generiert wird, **Then** sieht User Answer + Confidence + Quellen (L2 IDs), optional Thought + Reasoning expandierbar

### Story 2.4: External API Setup für Haiku (Evaluation + Reflexion)
1. **Given** Anthropic API-Key konfiguriert, **When** MCP Server Haiku API aufruft, **Then** ist Integration mit `claude-3-5-haiku-20241022` funktional
2. **Given** API-Aufruf erfolgt, **Then** ist Temperature 0.7 (Reflexion) oder 0.0 (Evaluation) konfiguriert
3. **Given** Rate Limit erreicht wird, **Then** wird Retry-Logic mit Exponential Backoff (1s, 2s, 4s, 8s) ausgeführt
4. **Given** API-Aufruf erfolgreich, **Then** wird Cost-Tracking mit Token Count in PostgreSQL geloggt

### Story 2.5: Self-Evaluation mit Haiku API
1. **Given** Antwort via CoT generiert, **When** Self-Evaluation durchgeführt wird, **Then** ruft MCP Server Haiku API auf mit Query + Context + Answer
2. **Given** Evaluation erfolgt, **Then** werden Relevance, Accuracy, Completeness Kriterien geprüft und Reward Score -1.0 bis +1.0 zurückgegeben
3. **Given** Evaluation Score berechnet, **Then** wird Response mit Reward + Reasoning zurückgegeben und in PostgreSQL geloggt
4. **Given** Reward <0.3, **Then** wird Reflexion getriggert (Story 2.6)

### Story 2.6: Reflexion-Framework mit Verbal Reinforcement Learning
1. **Given** Reward <0.3 (schlechte Antwort), **When** Reflexion getriggert wird, **Then** ruft MCP Server Haiku API mit strukturiertem Prompt auf
2. **Given** Reflexion generiert wird, **Then** folgt Format "Problem: Was lief schief?" + "Lesson: Was tun in Zukunft?" (2-3 Sätze)
3. **Given** Reflexion erstellt, **Then** wird via MCP Tool `store_episode` gespeichert mit Query Embedding für Similarity-Suche
4. **Given** ähnliche Query in Zukunft, **Then** wird Lesson Learned aus Episode Memory geladen und in CoT integriert

### Story 2.7: End-to-End RAG Pipeline Testing
1. **Given** MCP Server läuft und Claude Code konfiguriert, **When** Test-Query gestellt wird, **Then** durchläuft System alle 9 Pipeline-Schritte (Expansion → Embedding → Hybrid Search → Episode Memory → CoT → Evaluation → Reflexion → Working Memory → Response)
2. **Given** Pipeline läuft, **Then** wird End-to-End Latency <5s (p95) gemessen
3. **Given** verschiedene Query-Typen getestet, **Then** decken Tests High/Medium/Low Confidence Szenarien ab
4. **Given** Pipeline-Test erfolgreich, **Then** sind alle Pipeline-Schritte in PostgreSQL für Post-Mortem Analysis geloggt

### Story 2.8: Hybrid Weight Calibration via Grid Search
1. **Given** Ground Truth Set (50-100 Queries) existiert, **When** Grid Search durchgeführt wird, **Then** werden Gewicht-Kombinationen semantic={0.5-0.9}, keyword={0.5-0.1} getestet
2. **Given** Grid Search läuft, **Then** wird Precision@5 für jede Kombination auf allen Ground Truth Queries berechnet
3. **Given** beste Gewichte gefunden, **Then** werden diese in config.yaml gespeichert (erwartet: semantic=0.8, keyword=0.2)
4. **Given** Kalibrierung abgeschlossen, **Then** ist Precision@5 Uplift von +5-10% über MEDRAG-Default (0.7/0.3) erreicht

### Story 2.9: Precision@5 Validation auf Ground Truth Set
1. **Given** Hybrid Gewichte kalibriert, **When** Precision@5 gemessen wird, **Then** wird finale Metrik auf komplettem Ground Truth Set berechnet
2. **Given** Precision@5 ≥0.75, **Then** ist System ready for production (Full Success)
3. **Given** Precision@5 0.70-0.74, **Then** wird System mit Monitoring deployed (Partial Success)
4. **Given** Precision@5 <0.70, **Then** wird Architecture Review oder zusätzliche Ground Truth Collection erforderlich (Failure)

## Traceability Mapping

| AC ID | Acceptance Criterion | Spec Section | Component/API | Test Idea |
|-------|---------------------|--------------|---------------|-----------|
| AC-2.1.1 | Claude Code zeigt 7 MCP Tools | APIs and Interfaces | MCP Tool Registry | Manuelles Test in Claude Code Interface |
| AC-2.1.2 | Claude Code zeigt 5 Resources | APIs and Interfaces | MCP Resource Registry | Resource-Aufruf Test |
| AC-2.2.1 | 3 Query Varianten generiert | Workflows and Sequencing | Query Expansion Engine | Varianten-Output validieren |
| AC-2.2.2 | 4 Queries für Retrieval genutzt | Workflows and Sequencing | Hybrid Search Tool | Parallel-Call Testing |
| AC-2.3.1 | CoT 4-Teil Struktur | Workflows and Sequencing | CoT Generator | CoT-Output Parsing |
| AC-2.3.2 | Confidence Score Berechnung | Services and Modules | CoT Generator | Score-Berechnung validieren |
| AC-2.4.1 | Haiku API Integration | Dependencies and Integrations | HaikuClient | API-Call Test |
| AC-2.4.2 | Retry-Logic Exponential Backoff | Reliability/Availability | API Retry Logic | Rate Limit Simulation |
| AC-2.5.1 | Self-Evaluation Reward Score | Services and Modules | HaikuClient | Evaluation-Output validieren |
| AC-2.5.2 | Evaluation Logging | Observability | PostgreSQL Logging | Log-Entry Prüfung |
| AC-2.6.1 | Reflexion bei Reward <0.3 | Workflows and Sequencing | Reflexion Engine | Trigger-Test |
| AC-2.6.2 | Episode Memory Speicherung | APIs and Interfaces | store_episode Tool | Episode Retrieval Test |
| AC-2.7.1 | 9 Pipeline-Schritte komplett | Workflows and Sequencing | Complete Pipeline | End-to-End Flow Test |
| AC-2.7.2 | Latency <5s (p95) | Performance | Latency Monitoring | Performance Benchmark |
| AC-2.8.1 | Grid Search Gewicht-Test | Services and Modules | Weight Calibrator | Grid Search Result Validierung |
| AC-2.8.2 | Precision@5 Berechnung | Services and Modules | Calibration Engine | Precision Formula Test |
| AC-2.9.1 | Finale Precision@5 Validierung | Services and Modules | Validation Engine | Ground Truth Comparison |

## Risks, Assumptions, Open Questions

### Risks

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|-------------------|
| **Haiku API Rate Limits** | Medium (Degraded Mode) | Low (1000 RPM Limit) | Retry-Logic mit Exponential Backoff, Claude Code Fallback |
| **Claude Code MCP Integration Complexity** | High (Blocker) | Medium | MCP Inspector für Debugging, Step-by-Step Integration Guide |
| **Query Expansion Quality** | Medium (Recall Uplift nicht erreicht) | Low | Manuelle Review von Expansion Outputs, Strategie-Anpassung |
| **Grid Search Calibration Runtime** | Low (Performance Issue) | Medium | Parallelisierung, Caching von Embeddings, Optimierung |
| **Cost Overrun Haiku API** | Medium (Budget €1-2/mo überschritten) | Low | Cost Monitoring, Reflexion Threshold Anpassung, Daily Limits |

### Assumptions

1. **Epic 1 Completion:** Ground Truth Set mit 50-100 Queries ist verfügbar und hat Cohen's Kappa >0.70
2. **Claude Code MAX Subscription:** Verfügbar für €0/mo Bulk Operations (Query Expansion, CoT Generation)
3. **API Pricing Stability:** OpenAI Embeddings (€0.02/1M tokens) und Haiku (€0.001-0.0015/1K tokens) bleiben stabil
4. **PostgreSQL Performance:** Hybrid Search mit IVFFlat Index erreicht <1s Latency bei <100k Vektoren
5. **Network Reliability:** Stable Internet Connection für externe API Calls (Haiku, OpenAI)

### Open Questions

1. **Query Expansion Strategy:** Sind 3 Varianten optimal oder sollte Anzahl konfigurierbar sein (2-5)?
2. **Confidence Score Calculation:** Wie genau soll Retrieval Quality in Confidence Score umgerechnet werden?
3. **Reflexion Threshold:** Ist Reward <0.3 der optimale Trigger oder sollte Schwellenwert dynamisch sein?
4. **Grid Search Granularity:** Reichen 5 Gewicht-Kombinationen oder ist feineres Grid notwendig?
5. **CoT Output Format:** Sollte vollständiger CoT immer sichtbar sein oder nur auf Anfrage?

## Test Strategy Summary

### Test Levels

**1. Unit Tests (MCP Server Components)**
- Haiku API Client Integration Tests
- Evaluation Result Parsing Tests
- Reflexion Generation Tests
- Grid Search Calibration Logic Tests
- Retry-Logic Tests mit Mock APIs

**2. Integration Tests (Epic 2 Focus)**
- Claude Code ↔ MCP Server Communication Tests
- End-to-End Pipeline Flow Tests
- Query Expansion + Hybrid Search Integration Tests
- Evaluation + Reflexion Trigger Chain Tests
- Configuration Loading Tests (Hybrid Weights)

**3. System Tests (Ground Truth Validation)**
- Precision@5 Validation auf komplettem Ground Truth Set
- Latency Benchmarks (p95 <5s Target)
- Cost Validation (€1-2/mo Budget)
- API Reliability Tests (Rate Limit Handling)
- Fallback Mode Tests (Haiku API Ausfall Simulation)

### Test Data Strategy

**Ground Truth Set (Epic 1 Output):**
- 50-100 gelabelte Queries mit Cohen's Kappa >0.70
- Stratified Sampling: 40% Short, 40% Medium, 20% Long Queries
- Temporal Diversity über verschiedene Sessions

**Test Queries (Epic 2 Generation):**
- High Confidence expected: Queries mit klarem Match in L2 Insights
- Medium Confidence expected: Ambigue Queries mit mehreren möglichen Docs
- Low Confidence expected: Queries ohne passende Dokumente

**Performance Test Data:**
- 100 Test-Queries für Latency Benchmarks
- Load Testing mit 10+ parallel Queries
- API Rate Limit Simulation Tests

### Success Criteria

**Functional Success:**
- Alle 9 Stories erfolgreich implementiert
- End-to-End Pipeline funktioniert für alle Query-Typen
- Claude Code Integration stabil (99%+ Success Rate)

**Performance Success:**
- End-to-End Latency <5s (p95)
- Precision@5 ≥0.75 auf Ground Truth Set
- Cost innerhalb Budget (€1-2/mo Development)

**Quality Success:**
- Evaluation Rewards konsistent über Sessions
- Reflexion Quality hilfreich für Lernen
- Query Expansion Recall Uplift +10-15% erreicht

### Test Automation

**Manual Testing Required:**
- Claude Code MCP Integration (UI-basiert)
- End-to-End User Experience Tests
- Ground Truth Label Quality Verification

**Automated Testing:**
- API Client Unit Tests
- Grid Search Calibration Scripts
- Performance Benchmarking Tools
- Cost Tracking Validation Scripts
