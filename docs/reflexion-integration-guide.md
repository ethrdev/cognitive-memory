# Reflexion-Framework Integration Guide

**Version:** 1.0
**Date:** 2025-11-16
**Story:** 2.6 - Reflexion-Framework mit Verbal Reinforcement Learning
**Audience:** Claude Code (Primary LLM), Developers

---

## Overview

This guide documents how to integrate the Reflexion-Framework (Verbal Reinforcement Learning) into the RAG Pipeline within Claude Code. The reflexion system enables the MCP Server to learn from poor-quality answers by generating verbalized lessons that are stored in Episode Memory and retrieved for similar future queries.

**Key Components:**
- **MCP Server:** Provides `generate_reflection()` method via HaikuClient
- **Trigger Logic:** `should_trigger_reflection()` utility (reward < 0.3 threshold)
- **Storage:** `store_episode()` MCP Tool for persistent lesson storage
- **Retrieval:** `memory://episode-memory` MCP Resource for lesson retrieval

---

## Pipeline Integration (Task 2)

### Full RAG Pipeline with Reflexion

```
1. User Query (in Claude Code)
   ↓
2. Query Expansion → 3 Varianten (Story 2.2)
   ↓
3. Hybrid Search → Top-5 L2 Insights (Story 1.6)
   ↓
4. Episode Memory Load → ähnliche vergangene Queries (Story 1.8)
   ↓ [NEW: Lessons Learned Integration - see Task 3]
   - Falls ähnliche Episode (Similarity >0.70): Lade Lesson
   - Füge zu CoT Context: "Past experience: {lesson}"
   ↓
5. CoT Generation → Thought + Reasoning + Answer + Confidence (Story 2.3)
   ↓
6. Self-Evaluation (Story 2.5) → Reward Score (-1.0 bis +1.0)
   ↓
7. ** CONDITIONAL REFLEXION (Story 2.6 - This Integration) **
   ↓
   ┌─ Check Trigger Condition:
   │  should_trigger_reflection(evaluation_result["reward_score"])
   │
   ├─ IF False (Reward ≥0.3):
   │  └─ Skip Reflexion → Continue to Step 8
   │
   └─ IF True (Reward <0.3):
      └─ Trigger Reflexion Flow:
         1. Call haiku_client.generate_reflection()
         2. Parse Response (Problem + Lesson)
         3. Call store_episode() MCP Tool
         4. Log to Episode Memory
   ↓
8. Working Memory Update (Story 1.7)
   ↓
9. User Response: Answer + Confidence + Sources + (optional Lesson Learned)
```

---

### Integration Point: After Self-Evaluation (Step 6 → 7)

**Location:** Claude Code (after evaluate_answer() call in RAG Pipeline)

**Pseudo-Code:**
```python
# Step 6: Self-Evaluation
evaluation_result = await haiku_client.evaluate_answer(
    query=user_query,
    context=top_5_docs,
    answer=generated_answer
)

reward_score = evaluation_result["reward_score"]
evaluation_reasoning = evaluation_result["reasoning"]

# Step 7: Conditional Reflexion (NEW)
if should_trigger_reflection(reward_score):
    # Trigger Reflexion
    reflexion_result = await haiku_client.generate_reflection(
        query=user_query,
        context=top_5_docs,
        answer=generated_answer,
        evaluation_result=evaluation_result
    )

    # Extract Problem + Lesson
    problem = reflexion_result["problem"]
    lesson = reflexion_result["lesson"]
    full_reflection = reflexion_result["full_reflection"]

    # Store in Episode Memory via MCP Tool
    await store_episode(
        query=user_query,
        reward=reward_score,
        reflection=full_reflection  # or f"Problem: {problem} | Lesson: {lesson}"
    )

    # Optional: Display lesson to user (transparency)
    logger.info(f"System learned: {lesson}")
else:
    # No reflexion needed - answer quality acceptable
    logger.debug(f"Reward {reward_score:.2f} ≥ 0.3, skipping reflexion")

# Continue to Step 8: Working Memory Update...
```

---

### Trigger Logic Details

**Function:** `should_trigger_reflection(reward_score: float) -> bool`
**Location:** `mcp_server/utils/reflexion_utils.py` (from Story 2.5)
**Threshold:** reward_score < 0.3 (configurable in config.yaml)

**Expected Trigger Rate:**
- **Bootstrapping (first 2-4 weeks):** 20-30% (many low-quality answers)
- **After Calibration (month 2):** 10-15% (system learns over time)
- **Long-Term (month 4+):** 5-10% (stable system)

**Rationale for 0.3 Threshold:**
- Reward ≥0.3: Answer is "minimally acceptable" → No reflexion needed
- Reward <0.3: Answer is unacceptable → Reflexion required to learn

---

### Reflexion-to-Episode-Memory Flow (Subtask 2.2)

**Step 1:** Generate Reflexion
```python
reflexion_result = await haiku_client.generate_reflection(
    query=user_query,
    context=top_5_docs,
    answer=generated_answer,
    evaluation_result=evaluation_result
)
```

**Step 2:** Parse Response
```python
problem = reflexion_result["problem"]        # What went wrong (1-2 sentences)
lesson = reflexion_result["lesson"]          # What to do differently (1-2 sentences)
full_reflection = reflexion_result["full_reflection"]  # Complete text
```

**Step 3:** Store in Episode Memory
```python
await store_episode(
    query=user_query,                # Original query (will be embedded)
    reward=reward_score,             # Reward score from evaluation
    reflection=full_reflection       # Verbalized lesson
)
```

**Database Storage:**
- **Table:** `episode_memory`
- **Columns:** id, query, reward, reflection, created_at, embedding (1536-dim)
- **Embedding:** Query is embedded via OpenAI API for similarity search
- **Retrieval:** Later queries with Similarity >0.70 will retrieve this lesson (see Task 3)

---

### Logging and Cost Tracking (Subtask 2.3)

**Automatic Logging:** `generate_reflection()` automatically logs to `api_cost_log`

**Log Entry Example:**
```sql
INSERT INTO api_cost_log (date, api_name, num_calls, token_count, estimated_cost)
VALUES ('2025-11-16', 'haiku_reflexion', 1, 875, 0.0015);
```

**Cost Breakdown:**
- Input Tokens: ~500-700 (Query + Context + Answer + Evaluation + Prompt)
- Output Tokens: ~150-200 (Problem + Lesson)
- Total: ~650-900 tokens per reflexion
- Cost: ~€0.0015 per reflexion
- Monthly: ~€0.45 for 300 reflexions (30% trigger rate @ 1000 queries/mo)

**Budget Monitoring:**
- Query monthly costs: `SELECT SUM(estimated_cost) FROM api_cost_log WHERE api_name='haiku_reflexion' AND date >= NOW() - INTERVAL '30 days'`
- Target: Within NFR003 Budget (€5-10/mo total for all Haiku API calls)

---

## Episode Memory Retrieval for CoT (Task 3)

### Integration Point: Before CoT Generation (Step 4)

**Location:** Claude Code (before CoT generation in RAG Pipeline)

**Pseudo-Code:**
```python
# Step 4: Load Episode Memory (existing step, enhance with lessons)
episode_resource_url = f"memory://episode-memory?query={current_query}&min_similarity=0.70"
episodes = await load_resource(episode_resource_url)

# Extract Lessons Learned from similar past episodes
lessons_learned = []
if episodes:
    for episode in episodes[:3]:  # Top-3 most similar episodes
        similarity = episode["similarity"]
        if similarity > 0.70:
            lesson = extract_lesson_from_reflection(episode["reflection"])
            lessons_learned.append({
                "similarity": similarity,
                "lesson": lesson,
                "past_query": episode["query"]
            })

# Step 5: CoT Generation with Lessons Context
cot_context = {
    "retrieved_docs": top_5_docs,
    "lessons_learned": lessons_learned  # NEW: Add lessons to CoT context
}

generated_answer = await generate_cot(
    query=user_query,
    context=cot_context
)
```

---

### Episode Memory Resource Details

**Resource URI:** `memory://episode-memory`
**Query Parameters:**
- `query`: Current user query (will be embedded and compared)
- `min_similarity`: Minimum cosine similarity threshold (default: 0.70)
- `top_k`: Number of episodes to return (default: 3)

**Response Format:**
```json
[
  {
    "id": 42,
    "query": "What is consciousness?",
    "reward": 0.25,
    "reflection": "Problem: Retrieved context was too technical...\nLesson: For philosophical questions, provide accessible explanations...",
    "similarity": 0.85
  },
  {
    "id": 17,
    "query": "Explain the nature of consciousness",
    "reward": 0.15,
    "reflection": "Problem: Answer lacked concrete examples...\nLesson: Use metaphors and examples for abstract concepts...",
    "similarity": 0.72
  }
]
```

**Similarity Threshold Rationale:**
- **>0.70:** High similarity - lesson is likely relevant to current query
- **0.50-0.70:** Medium similarity - may or may not be relevant
- **<0.50:** Low similarity - lesson unlikely to be relevant

---

### Lessons Learned Integration in CoT (Subtask 3.2)

**Format:** Lessons appear as separate section in CoT Input

**Example CoT Prompt Enhancement:**
```
You are answering a user query with retrieved context.

**Query:** {user_query}

**Retrieved Context:**
{top_5_docs}

**Lessons from Similar Past Queries:**
- Past Query (Similarity: 0.85): "What is consciousness?"
  Lesson: For philosophical questions, provide accessible explanations rather than dense technical terminology.

- Past Query (Similarity: 0.72): "Explain the nature of consciousness"
  Lesson: Use metaphors and examples for abstract concepts to aid understanding.

**Task:** Generate a thoughtful answer incorporating these lessons learned.

**Output Format:**
- Thought: [Initial intuition]
- Reasoning: [Explicit reasoning based on context and lessons]
- Answer: [Final answer to user]
- Confidence: [0.0-1.0]
```

**Expected Impact:**
- Improved Answer Quality: +10-15% Reward Score for similar queries
- Consistency: Same mistakes not repeated across sessions
- Transparency: User sees "Lesson from past experience" in CoT (optional)

---

### Integration Pattern Documentation (Subtask 3.3)

**Pattern Summary:**
1. **Before CoT:** Load Episode Memory Resource
2. **If Similar Episodes Found (Similarity >0.70):** Extract Lessons
3. **Add to CoT Context:** Lessons as separate section "Past experience suggests..."
4. **Else (No Similar Episodes):** Proceed with CoT without Episode Memory Lessons

**Code Location:** Claude Code (CoT Generation Module)

**Dependencies:**
- MCP Resource: `memory://episode-memory` (already implemented in Story 1.9)
- Episode Storage: `store_episode()` Tool (already implemented in Story 1.8)
- Query Embedding: OpenAI API (already integrated)

**No Code Changes Required:** Episode Memory MCP Resource is already fully functional. Claude Code just needs to call it before CoT generation and parse the response.

---

## Error Handling and Fallback

### API Failure Scenarios

**Scenario 1: Haiku API Unavailable (Rate Limit / 503)**
- **Retry Logic:** 4 retries with Exponential Backoff (1s, 2s, 4s, 8s)
- **Total Wait:** ~15s max
- **Implemented:** `@retry_with_backoff` decorator on `generate_reflection()`

**Scenario 2: 4 Retries Failed**
- **Fallback:** Skip Reflexion (degraded mode)
- **Impact:** No lesson learned stored, system continues normally
- **Rationale:** Reflexion is not critical for system functionality
- **Log:** Warning message: "Reflexion skipped due to API failure"

**Scenario 3: Parsing Failure (Problem/Lesson not found)**
- **Fallback:** Use full reflection text as lesson
- **Log:** Warning: "Failed to parse Problem/Lesson sections. Using full response as lesson."
- **Impact:** Lesson still stored, slightly less structured

### Robustness Principles

1. **Non-Blocking:** Reflexion failure never blocks answer generation
2. **Graceful Degradation:** System works without reflexion, just no learning
3. **Logging:** All failures logged for debugging and monitoring
4. **Retry Logic:** Transient errors handled automatically
5. **Cost Safety:** API budget monitoring prevents runaway costs

---

## Testing Validation

### Manual Test Cases (Task 4)

**Test 1: Low-Quality Answer (Trigger Reflexion)**
- Query: Ask question without matching context (simulate poor retrieval)
- Expected: Reward <0.3, Reflexion triggered
- Validate: Problem + Lesson correctly parsed, Episode Memory contains new entry

**Test 2: Medium-Quality Answer (No Reflexion)**
- Query: Ambiguous question with partially relevant context
- Expected: Reward 0.3-0.7, NO reflexion triggered
- Validate: Only evaluation logged, no store_episode call

**Test 3: Similar Query After Reflexion**
- First Query: Trigger reflexion (Reward <0.3)
- Second Query: Similar query (Similarity >0.70)
- Expected: Episode Memory Resource returns lesson
- Validate: Lesson integrated in CoT ("Past experience suggests...")

**Test 4: Episode Memory Validation**
- After 3-5 reflexions, query episode_memory table
- Validate: Reflexions stored, query embeddings present, similarity search works

---

## Implementation Checklist

- [x] Task 1.1: generate_reflection() implemented in anthropic_client.py
- [x] Task 1.2: Structured Reflexion Prompt (Problem + Lesson format)
- [x] Task 1.3: Parsing for Problem/Lesson with fallback
- [x] Task 1.4: @retry_with_backoff Decorator applied
- [x] Task 1.5: Token Count and Cost Tracking
- [x] Task 2.1: Documented Reflexion Trigger Logic (this guide)
- [x] Task 2.2: Documented Reflexion-to-Episode-Memory Flow (this guide)
- [x] Task 2.3: Cost Tracking Logging integrated (api_name='haiku_reflexion')
- [x] Task 3.1: Documented Episode Memory Retrieval before CoT (this guide)
- [x] Task 3.2: Documented Lessons Learned Integration in CoT (this guide)
- [x] Task 3.3: Integration Pattern documented (this guide)
- [ ] Task 4.1-4.5: Manual Testing (to be completed during testing phase)

---

## References

- **Story:** 2.6 - Reflexion-Framework mit Verbal Reinforcement Learning
- **Tech-Spec:** bmad-docs/tech-spec-epic-2.md (AC-2.6.1 to AC-2.6.4)
- **Architecture:** bmad-docs/architecture.md (Haiku API Reflexion, Verbal RL)
- **Code:** mcp_server/external/anthropic_client.py (generate_reflection method)
- **Utils:** mcp_server/utils/reflexion_utils.py (should_trigger_reflection)
- **Tools:** mcp_server/tools/store_episode.py (Episode Memory Storage)
- **Resources:** mcp_server/resources/episode_memory.py (Episode Memory Retrieval)

---

**End of Guide**
