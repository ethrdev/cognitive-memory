# Chain-of-Thought (CoT) Generation Guide

**Version:** 1.0.0
**Last Updated:** 2025-11-16
**Epic:** 2 - RAG Pipeline & Hybrid Calibration
**Story:** 2.3 - Chain-of-Thought (CoT) Generation Framework

---

## 📋 Overview

Dieses Dokument beschreibt das Chain-of-Thought (CoT) Generation Framework, das als interner Reasoning-Prozess in Claude Code implementiert ist. CoT Generation ermöglicht transparente, nachvollziehbare Antworten mit explizitem Reasoning.

**Kernmerkmale:**
- **Intern in Claude Code:** Keine externen API-Calls (€0/mo statt €92.50/mo für Opus API)
- **4-Teil Struktur:** Thought → Reasoning → Answer → Confidence
- **Transparenz:** Explizite Quellenangaben und nachvollziehbares Reasoning
- **Kostenoptimiert:** Ersetzt teure Opus API-Calls durch interne Generation

---

## 🏗️ Architektur

### High-Level Flow

```
Retrieved Context (Top-5 Docs) + Episode Memory
  ↓
Claude Code: Intern CoT Generation
  ↓
4-Teil Struktur:
  1. Thought: "Basierend auf Docs, erste Intuition ist..."
  2. Reasoning: "Dok 1 sagt X, Dok 2 bestätigt Y, Episode Memory zeigt..."
  3. Answer: "Finale präzise Antwort an User"
  4. Confidence: 0.85 (basierend auf Top-1 Score 0.87, 3/5 Docs übereinstimmend)
  ↓
User erhält: Answer + Confidence + Sources [L2 ID: 123, 456, 789]
  ↓
(Optional) Power-User: Expandiere Thought + Reasoning
```

### Integration in RAG Pipeline

CoT Generation ist Teil der End-to-End RAG Pipeline:

1. **User Query:** "Wie verstehe ich Autonomie?"
2. **Query Expansion (Story 2.2):** 3 semantische Varianten generiert
3. **Hybrid Search (Story 2.2):** Top-5 Docs retrieved (RRF Fusion)
4. **Episode Memory Check:** Top-3 ähnliche vergangene Gespräche geladen (Cosine Similarity >0.70)
5. **CoT Generation (Story 2.3):** Thought → Reasoning → Answer → Confidence
6. **Evaluation (Story 2.5):** Self-Evaluation mit Haiku API (optional)
7. **Response:** User erhält strukturierte Antwort

---

## 🧠 Die 4 CoT-Komponenten

### 1. Thought (Erste Intuition)

**Purpose:** Erfasst die erste Hypothese basierend auf Retrieved Context

**Eigenschaften:**
- **Länge:** 1-2 Sätze
- **Inhalt:** Initiale Interpretation der Retrieval Results
- **Transparenz:** Macht den Start des Reasoning-Prozesses sichtbar

**Beispiel:**
```
Thought:
Die Dokumente deuten darauf hin, dass Autonomie als emergente Eigenschaft
verstanden wird, die aus selbstorganisierenden Strukturen entsteht.
```

**Rationale:**
- Zeigt wie Claude Code die Retrieved Docs initial interpretiert
- Ermöglicht User nachzuvollziehen wie die Antwort entsteht
- Erfüllt NFR005 (Transparency über Blackbox)

---

### 2. Reasoning (Explizite Begründung)

**Purpose:** Detaillierte Begründung mit Quellen-Referenzen und logischer Verknüpfung

**Eigenschaften:**
- **Länge:** 3-5 Sätze
- **Inhalt:**
  - Referenzen auf Retrieved Docs (mit L2 IDs)
  - Integration von Episode Memory (falls vorhanden)
  - Logische Verknüpfung der Evidenzen
- **Transparenz:** Explizite Quellenangaben

**Beispiel:**
```
Reasoning:
Dokument L2-123 beschreibt Autonomie als selbstorganisierendes System,
das aus lokalen Interaktionen emergiert. Episode Memory (Query:
'Bewusstsein und Autonomie') zeigt ähnlichen Kontext, wo Autonomie mit
Identitätsbildung verknüpft wurde. Dokument L2-456 bestätigt diese
Perspektive durch Emergenz-Theorie und erweitert sie um relationale
Aspekte. Dokument L2-789 fügt hinzu, dass Autonomie nicht isoliert
betrachtet werden kann, sondern immer in Bezug auf ein Umfeld entsteht.
```

**Komponenten des Reasoning:**
1. **Doc References:** Explizite L2 ID Referenzen (z.B. "Dokument L2-123 beschreibt...")
2. **Episode Integration:** "Episode Memory (Query: 'X') zeigt..."
3. **Logical Flow:** Aufbau von Grundlage über Bestätigung zu Erweiterung
4. **Synthesis:** Verknüpfung mehrerer Quellen zu kohärenter Argumentation

**Rationale:**
- Nachvollziehbarkeit: User kann Reasoning Schritt für Schritt nachvollziehen
- Quellenangaben: Jede Behauptung hat klare Herkunft
- Transparenz: Explizite Integration von vergangenen Gesprächen (Episode Memory)

---

### 3. Answer (Finale Antwort)

**Purpose:** User-facing finale Antwort (klar, präzise, direkt)

**Eigenschaften:**
- **Stil:** Klar, präzise, ohne Overhead
- **Inhalt:** Synthesis der Reasoning-Komponenten
- **Audience:** End-User (nicht Power-User)

**Beispiel:**
```
Answer:
Autonomie ist in diesem Kontext eine emergente Eigenschaft, die aus
selbstorganisierenden Strukturen entsteht und eng mit Identitätsbildung
verbunden ist. Sie kann nicht isoliert betrachtet werden, sondern
entsteht immer in Bezug auf ein Umfeld und durch relationale Prozesse.
```

**Qualitätskriterien:**
- ✅ Direkt und auf den Punkt
- ✅ Keine Wiederholung des Reasonings (steht optional expandierbar)
- ✅ Selbst-contained (auch ohne Thought/Reasoning verständlich)
- ✅ Synthetisiert mehrere Quellen zu kohärenter Aussage

**Rationale:**
- User sieht finale Antwort ohne Complexity Overhead
- Kein Information Overload (Details sind optional expandierbar)
- Hohe Readability für alle User-Levels

---

### 4. Confidence (Score)

**Purpose:** Quantifizierung der Answer Quality basierend auf Retrieval Quality

**Eigenschaften:**
- **Range:** 0.0-1.0 (niemals exakt 0.0 oder 1.0, epistemische Bescheidenheit)
- **Calculation:** Basierend auf Retrieval Quality Metrics
- **Display:** Score + Label (z.B. "0.87 (Hoch)")

**Thresholds:**
- **High (>0.8):** Top-1 Retrieval Score >0.85 UND mehrere Docs übereinstimmend (≥3 relevant)
- **Medium (0.5-0.8):** Top-1 Score 0.7-0.85 ODER einzelnes relevantes Dokument
- **Low (<0.5):** Alle Scores <0.7, inkonsistente oder fehlende Docs

**Confidence Calculation Algorithm:**

```python
def calculate_confidence(retrieval_results: List[SearchResult]) -> float:
    """
    Calculate confidence score based on retrieval quality.

    Args:
        retrieval_results: Top-K search results with scores (RRF fusion output)

    Returns:
        Confidence score 0.0-1.0
    """
    if not retrieval_results:
        return 0.1  # Minimum confidence (never 0.0 - immer etwas Info)

    top1_score = retrieval_results[0].score
    num_relevant = sum(1 for r in retrieval_results if r.score > 0.7)

    # High Confidence: Top-1 >0.85 AND multiple relevant docs
    if top1_score > 0.85 and num_relevant >= 3:
        return min(0.95, top1_score)  # Cap at 0.95 (never 100% certain)

    # Medium Confidence: Top-1 0.7-0.85 OR single relevant doc
    elif top1_score >= 0.7:
        # Scale between 0.5-0.8 based on top1_score and num_relevant
        base_score = (top1_score - 0.7) / 0.15 * 0.3 + 0.5  # Maps 0.7-0.85 → 0.5-0.8
        relevance_bonus = min(0.1, num_relevant * 0.03)
        return min(0.8, base_score + relevance_bonus)

    # Low Confidence: All scores <0.7
    else:
        return max(0.1, top1_score)  # Floor at 0.1 (never 0%)
```

**Algorithmus-Rationale:**
- **Top-1 Score dominant:** Wichtigster Indikator für Retrieval Quality
- **Num Relevant Docs:** Sekundärer Faktor für Consistency (mehrere Docs = höhere Confidence)
- **Never 0.0 or 1.0:** Epistemische Bescheidenheit (immer etwas Unsicherheit)
- **Tunable Thresholds:** Können in config.yaml angepasst werden (aktuell fest in Algorithmus)

**Rationale:**
- User-Transparency über Answer Quality
- Ermöglicht User zu entscheiden ob Antwort vertrauenswürdig ist
- Korreliert mit Retrieval Quality (bessere Docs → höhere Confidence)

---

## 📄 Output Format & User Experience

### User-Facing Output (Default)

**Standard-Ausgabe** (minimale Cognitive Load):
```markdown
**Answer:**
Autonomie ist in diesem Kontext eine emergente Eigenschaft, die aus
selbstorganisierenden Strukturen entsteht und eng mit Identitätsbildung
verbunden ist.

**Confidence:** 0.87 (Hoch)

**Quellen:** [L2-123, L2-456, L2-789]
```

**Format-Eigenschaften:**
- **Kompakt:** Nur Answer + Confidence + Sources
- **Clear:** Confidence mit Label (Hoch/Medium/Niedrig)
- **Transparent:** Quellen-Referenzen ermöglichen Verifikation

---

### Power-User Output (Expandierbar)

**Vollständige Ausgabe** (alle 4 Komponenten sichtbar):
```markdown
**Answer:**
Autonomie ist in diesem Kontext eine emergente Eigenschaft, die aus
selbstorganisierenden Strukturen entsteht und eng mit Identitätsbildung
verbunden ist.

**Confidence:** 0.87 (Hoch)

**Quellen:** [L2-123, L2-456, L2-789]

<details>
<summary>🔍 Details anzeigen (Thought + Reasoning)</summary>

**Thought:**
Die Dokumente deuten darauf hin, dass Autonomie als emergente Eigenschaft
verstanden wird, die aus selbstorganisierenden Strukturen entsteht.

**Reasoning:**
Dokument L2-123 beschreibt Autonomie als selbstorganisierendes System.
Episode Memory (Query: 'Bewusstsein und Autonomie') zeigt ähnlichen Kontext,
wo Autonomie mit Identitätsbildung verknüpft wurde. Dokument L2-456 bestätigt
diese Perspektive durch Emergenz-Theorie. Dokument L2-789 erweitert dies um
relationale Aspekte.
</details>
```

**Format-Eigenschaften:**
- **Collapsible:** Thought + Reasoning via `<details>` Tag expandierbar
- **Optional:** Power-User können Details einsehen, andere ignorieren
- **Debugging:** Ermöglicht Verifikation des Reasoning-Prozesses

---

## 🔗 Episode Memory Integration

### Integration in CoT Reasoning

Episode Memory wird **vor** CoT Generation abgerufen und in Reasoning integriert:

**Workflow:**
1. **Episode Memory Check:** MCP Resource `memory://episode-memory?query={query}&min_similarity=0.7`
2. **Top-3 Episodes:** Laden von bis zu 3 ähnlichen vergangenen Gesprächen (Cosine Similarity >0.70)
3. **Integration in Reasoning:** Explizite Referenzen auf Episodes

**Beispiel Reasoning mit Episode Integration:**
```
Reasoning:
Dokument L2-123 beschreibt Autonomie als selbstorganisierendes System.
Episode Memory (Query: 'Bewusstsein und Autonomie' vom 2025-11-10) zeigt
ähnlichen Kontext, wo Autonomie mit Identitätsbildung verknüpft wurde.
Die damalige Reflexion ("Autonomie entsteht nicht isoliert, sondern durch
Abgrenzung") wird durch Dokument L2-456 bestätigt...
```

**Episode Integration-Patterns:**
1. **Explizite Referenz:** "Episode Memory (Query: 'X' vom YYYY-MM-DD) zeigt..."
2. **Lesson Learned:** Falls Episode Reflexion enthält → integriere in Reasoning
3. **Temporaler Kontext:** "In vergangenen Gesprächen über X wurde Y diskutiert..."
4. **Consistency Check:** Widersprechen sich Episode und aktuelle Docs? → Acknowledge in Reasoning

**Rationale:**
- **Kontinuität:** System zeigt dass es aus vergangenen Gesprächen lernt
- **Transparency:** User sieht explizit welche vergangenen Queries relevant waren
- **Verbal RL:** Verbalisierte Lektionen werden in Reasoning integriert (nicht nur numerische Rewards)

---

## 📊 Performance & Latency

### Expected Latency Breakdown

| Step | Latency | Notes |
|------|---------|-------|
| Episode Memory Read | ~0.1s | MCP Resource Call |
| CoT Generation (intern) | ~2-3s | Längster Step, aber €0/mo |
| Confidence Calculation | ~0.01s | Fast in-memory operation |
| **Total Added Latency** | **~2-3s** | Dominiert durch Claude Code Reasoning |

### Latency Budget (NFR001)

**End-to-End RAG Pipeline:** <5s (p95)

| Pipeline Step | Latency | Story |
|--------------|---------|-------|
| Query Expansion | ~0.5s | 2.2 |
| Hybrid Search | ~1s | 2.2 |
| **CoT Generation** | **~2-3s** | **2.3** |
| Evaluation (Haiku API) | ~0.5s | 2.5 |
| **Total** | **~4.5-5.5s** | **✅ Within <5s Budget** |

**Rationale:**
- CoT Generation ist längster Step (~2-3s), aber:
  - **Akzeptabel:** Für philosophische Tiefe ist "Denkzeit" angemessen
  - **Cost-Free:** Ersetzt teuren Opus API Call (€92.50/mo → €0/mo)
  - **Transparent:** User sieht Reasoning-Prozess (NFR005)

---

## 💰 Cost-Savings Analysis

### Baseline (Ohne intern CoT, würde Opus API nutzen)

- **CoT Generation:** 1× Opus API Call pro Query
- **Cost per Query:** €0.0925 (Opus API Pricing)
- **At 1000 Queries/mo:** €92.50/mo

### v3.1-Hybrid (Intern in Claude Code)

- **CoT Generation:** Intern in Claude Code (MAX Subscription)
- **Cost per Query:** €0
- **At 1000 Queries/mo:** €0/mo

### Savings

| Metric | Baseline (Opus API) | v3.1-Hybrid (Intern) | Savings |
|--------|---------------------|----------------------|---------|
| Cost per Query | €0.0925 | €0 | €0.0925 (100%) |
| Cost at 1000 Q/mo | €92.50 | €0 | €92.50 (100%) |
| Cost at 10,000 Q/mo | €925 | €0 | €925 (100%) |

**Total Epic 2 Cost-Savings:**
- **Query Expansion (Story 2.2):** €0.50/Query → €0/Query (€500/mo savings bei 1000 Queries)
- **CoT Generation (Story 2.3):** €0.0925/Query → €0/Query (€92.50/mo savings)
- **Total Savings:** €592.50/mo → €0/mo für Bulk-Operationen (100% Reduktion!)

**Rationale:**
Claude Code (in MAX Subscription) kann CoT Generation intern durchführen (Teil des Reasoning), kein separater API-Call nötig. Dies ist der größte Cost-Saver in Epic 2 neben Query Expansion.

---

## 🧪 Testing & Validation

### Manual Testing (Primary)

CoT Generation testing ist primär manual in Claude Code Interface, da es ein interner Reasoning-Step ist.

**Test Scenarios:**

#### TC-2.3.1: High Confidence Test
- **Query:** "Was denke ich über Autonomie?" (klarer Match in L2 Insights erwartet)
- **Expected:**
  - Confidence >0.8 (High)
  - Thought + Reasoning + Answer + Confidence alle generiert
  - Reasoning inkludiert explizite L2 ID Referenzen
  - Sources list zeigt L2 IDs im Format [L2-123, L2-456, L2-789]

#### TC-2.3.2: Medium Confidence Test
- **Query:** "Wie verstehe ich die Beziehung zwischen X und Y?" (ambigue, mehrere Docs möglich)
- **Expected:**
  - Confidence 0.5-0.8 (Medium)
  - Reasoning zeigt mehrere Perspektiven aus verschiedenen Docs
  - Confidence Score reflektiert Ambiguität

#### TC-2.3.3: Low Confidence Test
- **Query:** "Was ist meine Meinung zu [komplett neues Thema]?" (keine relevanten Docs)
- **Expected:**
  - Confidence <0.5 (Low)
  - Answer acknowledges Unsicherheit ("Keine relevanten vergangenen Gespräche gefunden...")
  - CoT Struktur wird trotzdem generiert (nicht Failure, sondern Low Confidence)

#### TC-2.3.4: Episode Memory Integration Test
- **Query:** Ähnlich zu vergangener Query (z.B. "Bewusstsein und Autonomie")
- **Expected:**
  - Reasoning integriert Episode Memory ("In vergangenen Gesprächen...")
  - Falls Episode "Lesson Learned" enthält, wird es erwähnt
  - Episode Referenzen sind explizit (nicht nur implizit)

#### TC-2.3.5: Output Format Test
- **Query:** Any query
- **Expected:**
  - User sieht: Answer + Confidence + Sources (default view)
  - Thought + Reasoning sind optional (expandierbar via Markdown `<details>` tag)
  - L2 IDs korrekt formatiert ([L2-123, L2-456])
  - Confidence displayed mit Label (z.B. "0.87 (Hoch)")

#### TC-2.3.6: Latency Test
- **Query:** Any query
- **Expected:**
  - CoT Generation latency ~2-3s (acceptable, within <5s pipeline budget)
  - Total pipeline latency <5s (p95)

### Success Criteria
- ✅ Alle 5 Test-Queries funktionieren end-to-end
- ✅ CoT 4-Teil Struktur wird immer generiert
- ✅ Confidence Scores plausibel (High/Medium/Low korrekt zugeordnet)
- ✅ Episode Memory wird integriert (wenn vorhanden)
- ✅ Latency: ~2-3s akzeptabel (within <5s Budget)

---

## 📚 References

### Technical Specifications
- [tech-spec-epic-2.md#Story-2.3-Acceptance-Criteria](../bmad-docs/tech-spec-epic-2.md) (lines 399-403) - AC-2.3.1 bis AC-2.3.4 (authoritative)
- [tech-spec-epic-2.md#Services-and-Modules](../bmad-docs/tech-spec-epic-2.md) (lines 40-50) - CoT Generator Module
- [tech-spec-epic-2.md#Workflows-and-Sequencing](../bmad-docs/tech-spec-epic-2.md) (lines 159-183) - End-to-End RAG Pipeline

### Requirements & Architecture
- [epics.md#Story-2.3](../bmad-docs/epics.md) (lines 597-632) - User Story Definition
- [PRD.md#FR006](../bmad-docs/PRD.md) (lines 142-144) - Functional Requirement CoT Generation
- [architecture.md#Systemarchitektur](../bmad-docs/architecture.md) (lines 40-112) - High-Level Architektur mit CoT in Claude Code
- [PRD.md#UX-Design-Principles](../bmad-docs/PRD.md) (lines 314-319) - UX1: Transparenz über Blackbox

### Previous Stories
- [stories/2-2-query-expansion-logik-intern-in-claude-code.md](../bmad-docs/stories/2-2-query-expansion-logik-intern-in-claude-code.md) - Query Expansion & RRF Fusion Patterns

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-16 | Initial documentation - Story 2.3 implementation |

---

**Document Owner:** Dev Agent (Epic 2, Story 2.3)
**Last Review:** 2025-11-16
**Next Review:** After Story 2.5 completion (Self-Evaluation integration)
