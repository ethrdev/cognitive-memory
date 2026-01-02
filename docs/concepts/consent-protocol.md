# Consent Protocol for AI Memory Systems

**Version:** 1.0
**Status:** Reference Architecture
**Origin:** Extracted from [i-o-system](https://github.com/ethrdev/i-o-system) for general use

---

## Executive Summary

The Consent Protocol is a **4-level governance framework** for AI memory operations. It provides a philosophically grounded, GDPR-compliant approach to the fundamental question:

> **Who decides what an AI system stores about you - and how?**

This document describes the **concept and architecture**. cognitive-memory provides the storage layer; consent enforcement is implemented in the application layer (like i-o-system).

---

## The Problem

Traditional AI memory systems have a critical flaw: **users have no control over what gets stored**.

| Aspect | Traditional Approach | Consent Protocol |
|--------|---------------------|------------------|
| **Storage Decision** | AI decides | User decides (or consents) |
| **Transparency** | Opaque | Full visibility via ConsentRequest |
| **Deletion** | Often impossible | GDPR-compliant revocation |
| **Granularity** | All-or-nothing | 4 graduated levels |
| **Fatigue** | Constant prompts | Batching + intelligent defaults |

---

## The 4 Consent Levels

The protocol defines four hierarchical consent levels, each mapped to a specific memory type and user interaction pattern:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONSENT LEVEL HIERARCHY                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LEVEL 3: PROTECTED                                                         │
│  ══════════════════                                                         │
│  Trigger:        Multi-factor authentication required                       │
│  Use Case:       Sensitive data (health, finances, secrets)                 │
│  Revocation:     Immediate hard-delete, no recovery window                  │
│  Example:        "User mentioned a medical condition"                       │
│                                                                             │
│  LEVEL 2: EXPLICIT                                                          │
│  ═════════════════                                                          │
│  Trigger:        User must actively approve via callback                    │
│  Use Case:       Long-term storage (Semantic Memory)                        │
│  Revocation:     Soft-delete with 30-day recovery option                    │
│  Example:        "User prefers concise explanations"                        │
│                                                                             │
│  LEVEL 1: IMPLICIT                                                          │
│  ═════════════════                                                          │
│  Trigger:        Opt-out model (user can object, but default is store)      │
│  Use Case:       Medium-term storage (Episodic Memory, 30-day TTL)          │
│  Revocation:     Standard deletion                                          │
│  Example:        "Last session discussed Python optimization"               │
│                                                                             │
│  LEVEL 0: AUTO                                                              │
│  ═══════════════                                                            │
│  Trigger:        No user interaction                                        │
│  Use Case:       Ephemeral session context (Working Memory)                 │
│  Revocation:     Automatic at session end                                   │
│  Example:        "User just asked about variable naming"                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Level Comparison

| Level | User Interaction | Default TTL | Revocation | Audit |
|-------|------------------|-------------|------------|-------|
| **AUTO** | None | Session | Automatic | Minimal |
| **IMPLICIT** | Opt-out available | 30 days | On request | Basic |
| **EXPLICIT** | Must approve | Unlimited | On request + recovery | Full |
| **PROTECTED** | Multi-factor | Unlimited | Immediate hard-delete | Full + alerts |

---

## Memory Layer Mapping

Each consent level maps naturally to a memory architecture layer:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Memory Layer          Default Consent     Rationale                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  Working Memory        AUTO                Ephemeral, session-scoped        │
│  Episodic Memory       IMPLICIT            Medium-term, user can opt-out    │
│  Semantic Memory       EXPLICIT            Permanent, user must opt-in      │
│  Protected Memory      PROTECTED           Sensitive, multi-factor          │
└─────────────────────────────────────────────────────────────────────────────┘
```

In cognitive-memory terms:

| cognitive-memory Component | Suggested Consent Level |
|---------------------------|------------------------|
| `update_working_memory` | AUTO |
| `store_episode` | IMPLICIT |
| `compress_to_l2_insight` | EXPLICIT |
| Sensitive L2 insights | PROTECTED |

---

## Core Components

### ConsentLevel Enum

```python
from enum import StrEnum

class ConsentLevel(StrEnum):
    AUTO = "auto"           # Level 0: No interaction
    IMPLICIT = "implicit"   # Level 1: Opt-out available
    EXPLICIT = "explicit"   # Level 2: Must approve
    PROTECTED = "protected" # Level 3: Multi-factor
```

### ConsentRequest

When EXPLICIT or PROTECTED consent is required, the system generates a `ConsentRequest`:

```python
@dataclass
class ConsentRequest:
    content_preview: str      # Sanitized preview (PII removed)
    layer: MemoryLayer        # Target memory layer
    consent_level: ConsentLevel
    purpose: str | None       # Why this is being stored
    ttl: int | None           # Time-to-live in seconds
    is_relational: bool       # Relates to user-AI relationship

    def approve(self) -> ConsentResponse: ...
    def deny(self, reason: str = None) -> ConsentResponse: ...
    def approve_for_session(self) -> ConsentResponse: ...
    def approve_for_category(self, category: str) -> ConsentResponse: ...
```

### ConsentResponse

```python
@dataclass
class ConsentResponse:
    request: ConsentRequest
    approved: bool
    scope: ConsentScope       # SINGLE, SESSION, or CATEGORY
    ttl_override: int | None  # Override default TTL
    denial_reason: str | None
```

### ConsentScope

Controls how long a consent decision is cached:

```python
class ConsentScope(Enum):
    SINGLE = "single"       # One-time, not cached
    SESSION = "session"     # Valid for current session
    CATEGORY = "category"   # Valid for content category
```

---

## Consent Flow

### Basic Flow

```
User Action
    │
    ▼
┌─────────────────────────────┐
│ Determine Required          │
│ Consent Level               │
│ (based on memory layer)     │
└─────────────┬───────────────┘
              │
              ▼
         ┌────────────┐
         │ AUTO?      │──Yes──► Store immediately
         └─────┬──────┘
               │ No
               ▼
         ┌────────────┐
         │ IMPLICIT?  │──Yes──► Store + offer opt-out
         └─────┬──────┘
               │ No
               ▼
         ┌────────────┐
         │ Check      │
         │ Cache      │──Hit──► Use cached decision
         └─────┬──────┘
               │ Miss
               ▼
         ┌────────────┐
         │ Invoke     │
         │ Callback   │
         └─────┬──────┘
               │
               ▼
         ┌────────────┐
         │ User       │
         │ Decision   │
         └─────┬──────┘
               │
        ┌──────┴──────┐
        ▼             ▼
    Approved       Denied
        │             │
        ▼             ▼
    Store         Don't store
    + Cache       + Log reason
```

### Callback Registration

```python
def my_consent_handler(request: ConsentRequest) -> ConsentResponse:
    """Custom consent handler for your application."""
    # Show UI dialog, check user preferences, etc.
    print(f"Store '{request.content_preview}' in {request.layer}?")
    print(f"Purpose: {request.purpose}")

    user_input = input("(y)es / (n)o / (s)ession / (c)ategory: ")

    if user_input == 'y':
        return request.approve()
    elif user_input == 's':
        return request.approve_for_session()
    elif user_input == 'c':
        return request.approve_for_category(request.layer.value)
    else:
        return request.deny("User declined")

# Register with your system
memory_system = MemorySystem(consent_callback=my_consent_handler)
```

---

## Consent Fatigue Mitigation

A critical design consideration: **users should not be overwhelmed with consent prompts**.

### Strategies

1. **Session Caching:** `approve_for_session()` caches consent for similar requests within a session.

2. **Category Caching:** `approve_for_category("preferences")` approves all preference-related storage.

3. **Prompt Limits:** Maximum N prompts per session (configurable, default: 2). Additional requests are queued.

4. **Batch Approval:** Group similar requests for single approval.

```python
# Instead of 5 individual prompts:
pending = middleware.pending_consent_requests()
# Returns: {"semantic_preferences": [3 items], "semantic_facts": [2 items]}

# One approval for all preferences:
await middleware.approve_batch("semantic_preferences", scope=ConsentScope.SESSION)
```

### Configuration

```python
ConsentMiddleware(
    max_consent_prompts_per_session=2,  # Max prompts before queueing
    consent_cache_ttl_hours=24,         # How long to cache decisions
    batch_similarity_threshold=0.8,      # Grouping threshold
    enable_smart_defaults=True           # Use intelligent defaults
)
```

---

## GDPR Compliance: Right to be Forgotten

The Consent Protocol provides full GDPR "Right to be Forgotten" support.

### Revocation Options

```python
# Revoke specific entries
result = await middleware.revoke_consent(entry_ids=["abc", "def"])

# Revoke all entries in a layer
result = await middleware.revoke_consent(layer=MemoryLayer.SEMANTIC)

# Revoke ALL consent (with safety check)
result = await middleware.revoke_all_consent(force=False)
```

### Utility Guarantee

When a revocation would delete more than 50% of memory, the system issues a warning:

```python
try:
    result = await middleware.revoke_all_consent()
except UtilityWarning as w:
    print(f"Warning: This would delete {w.percentage}% of memory")
    print(f"Affected entries: {w.affected_count}")

    if user_confirms():
        result = await middleware.revoke_all_consent(force=True)
```

This protects against "over-unlearning" while preserving user autonomy - it's a **warning, not a block**.

### Soft Delete with Recovery

```python
# Soft delete with 30-day recovery window
result = await middleware.revoke_consent(
    entry_ids=["abc"],
    soft_delete=True,
    recovery_days=30
)

# Recover within window
recovered = await middleware.recover_revoked(entry_ids=["abc"])

# Permanently purge expired soft-deletes
purged_count = await middleware.purge_soft_deleted()
```

---

## Relational Content Protection

Content that relates to the **user-AI relationship** receives special protection.

### Automatic Elevation

When `is_relational=True`, consent is automatically elevated to at least EXPLICIT:

```python
# Even if you request IMPLICIT:
store(
    content="User's communication style: direct, prefers brevity",
    consent_level=ConsentLevel.IMPLICIT,
    is_relational=True  # → Elevated to EXPLICIT
)
```

### No Auto-Decay

Relational content never auto-decays. TTL is ignored for relational entries.

### Special Revocation Warning

```
This memory relates to your relationship dynamics.
Deleting may affect how the system understands your preferences.
Are you sure you want to proceed?
```

---

## Content Sanitization

Consent previews are automatically sanitized to protect PII:

```python
DEFAULT_SANITIZATION_PATTERNS = [
    # API Keys
    (r"sk-[a-zA-Z0-9]{12,}", "sk-***"),

    # Passwords
    (r"password[=:]\s*['\"]?([^\s'\"]+)", r"password=***"),

    # Emails (partial masking)
    (r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
     lambda m: f"{m.group(1)[0]}***@{m.group(2)}"),

    # Phone numbers
    (r"\+(\d{1,3})(\d{4,})(\d{3})", r"+\1***\3"),

    # Credit cards
    (r"\b(\d{4})\d{8,12}(\d{4})\b", r"\1********\2"),
]
```

Custom patterns can be provided:

```python
ConsentMiddleware(
    sanitization_patterns=[
        (r"SSN:\s*\d{3}-\d{2}-\d{4}", "SSN: ***-**-****"),
        # ... additional patterns
    ]
)
```

---

## Integration with cognitive-memory

cognitive-memory is a **storage layer** - it stores and retrieves data. The Consent Protocol is an **application layer** concern - it decides *whether* to store.

### Recommended Pattern

```python
class ConsentAwareMemory:
    """Wrapper that adds consent to cognitive-memory operations."""

    def __init__(self, mcp_client, consent_middleware):
        self.mcp = mcp_client
        self.consent = consent_middleware

    async def store_insight(
        self,
        content: str,
        source_ids: list[int],
        consent_level: ConsentLevel = ConsentLevel.EXPLICIT
    ):
        # Check consent first
        result = await self.consent.check(
            content=content,
            layer=MemoryLayer.SEMANTIC,
            requested_level=consent_level
        )

        if not result.approved:
            raise ConsentDeniedError(result.denial_reason)

        # Store with consent metadata
        return await self.mcp.call_tool("compress_to_l2_insight", {
            "content": content,
            "source_ids": source_ids,
            "metadata": {
                "consent_level": consent_level.value,
                "consented_at": datetime.now(timezone.utc).isoformat(),
                "consent_scope": result.scope.value if hasattr(result, 'scope') else "single"
            }
        })
```

### Metadata Convention

When storing with cognitive-memory, include consent metadata:

```json
{
    "consent_level": "explicit",
    "consented_at": "2025-01-02T10:30:00Z",
    "consent_scope": "session",
    "purpose": "Long-term preference storage",
    "is_relational": false
}
```

This enables:
- Audit trails
- Consent-based filtering
- GDPR compliance reporting

---

## Audit Trail

All consent decisions should be logged:

```python
@dataclass
class ConsentAuditEntry:
    timestamp: datetime
    action: str              # "granted", "denied", "revoked", "recovered"
    consent_level: ConsentLevel
    layer: MemoryLayer
    content_preview: str     # Sanitized
    scope: ConsentScope
    reason: str | None       # For denials/revocations
    session_id: str
```

---

## Philosophical Foundation

The Consent Protocol is grounded in two principles:

### 1. User Autonomy

The user has final authority over their data. The `force=True` parameter exists because:

> Even if deletion would break the system, the user's right to delete their data supersedes system functionality.

### 2. Transparency over Convenience

Every storage decision is visible and challengeable. This creates friction - but **informed friction** is preferable to silent data collection.

---

## Reference Implementation

For a complete, production-ready implementation, see:

- **Repository:** [i-o-system](https://github.com/ethrdev/i-o-system)
- **File:** `src/io_system/core/consent.py` (~1460 LOC)
- **Tests:** `tests/unit/test_consent*.py`, `tests/integration/test_consent*.py`

The i-o-system implementation includes:
- Full ConsentMiddleware class
- Callback and batch callback protocols
- Session and category caching
- RevocationService with soft-delete
- Comprehensive test coverage

---

## See Also

- [Implementing Consent in Your Application](../guides/implementing-consent.md)
- [API Reference - Memory Tools](../reference/api-reference.md)
- [Ecosystem Architecture](../ecosystem/architecture.md)

---

**Document Version:** 1.0
**Last Updated:** 2025-01-02
**Authors:** Extracted from i-o-system by the cognitive-memory team
