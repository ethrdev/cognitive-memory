# Implementing Consent in Your Application

This guide shows how to integrate the Consent Protocol with cognitive-memory in your own AI application.

---

## Prerequisites

- cognitive-memory MCP server running
- Understanding of [Consent Protocol concepts](../concepts/consent-protocol.md)
- Python 3.11+ (for type hints)

---

## Quick Start

### 1. Define the Consent Levels

```python
from enum import StrEnum

class ConsentLevel(StrEnum):
    AUTO = "auto"
    IMPLICIT = "implicit"
    EXPLICIT = "explicit"
    PROTECTED = "protected"

class MemoryLayer(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
```

### 2. Create a Simple Consent Handler

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ConsentRequest:
    content_preview: str
    layer: MemoryLayer
    consent_level: ConsentLevel
    purpose: Optional[str] = None

    def approve(self) -> dict:
        return {"approved": True, "scope": "single"}

    def deny(self, reason: str = None) -> dict:
        return {"approved": False, "reason": reason}

def simple_consent_handler(request: ConsentRequest) -> dict:
    """Basic CLI consent handler."""
    print(f"\n{'='*60}")
    print(f"CONSENT REQUEST")
    print(f"{'='*60}")
    print(f"Content: {request.content_preview}")
    print(f"Layer:   {request.layer}")
    print(f"Level:   {request.consent_level}")
    if request.purpose:
        print(f"Purpose: {request.purpose}")
    print(f"{'='*60}")

    choice = input("Store this? (y/n): ").lower().strip()
    if choice == 'y':
        return request.approve()
    else:
        return request.deny("User declined")
```

### 3. Wrap cognitive-memory with Consent

```python
class ConsentAwareMemory:
    """Adds consent layer to cognitive-memory MCP tools."""

    # Map memory layers to default consent levels
    LAYER_CONSENT_MAP = {
        MemoryLayer.WORKING: ConsentLevel.AUTO,
        MemoryLayer.EPISODIC: ConsentLevel.IMPLICIT,
        MemoryLayer.SEMANTIC: ConsentLevel.EXPLICIT,
    }

    def __init__(self, mcp_client, consent_handler=None):
        self.mcp = mcp_client
        self.consent_handler = consent_handler or simple_consent_handler
        self._consent_cache = {}  # session cache

    async def store_insight(
        self,
        content: str,
        source_ids: list[int],
        purpose: str = None
    ) -> dict:
        """Store L2 insight with consent check."""

        # Create consent request
        request = ConsentRequest(
            content_preview=self._sanitize(content[:100]),
            layer=MemoryLayer.SEMANTIC,
            consent_level=ConsentLevel.EXPLICIT,
            purpose=purpose or "Long-term insight storage"
        )

        # Check cache first
        cache_key = hash(content)
        if cache_key in self._consent_cache:
            if not self._consent_cache[cache_key]:
                raise ConsentDeniedError("Previously denied")
        else:
            # Ask for consent
            response = self.consent_handler(request)
            self._consent_cache[cache_key] = response["approved"]

            if not response["approved"]:
                raise ConsentDeniedError(response.get("reason", "Denied"))

        # Store with consent metadata
        return await self.mcp.call_tool("compress_to_l2_insight", {
            "content": content,
            "source_ids": source_ids,
            "metadata": {
                "consent_level": "explicit",
                "consented_at": datetime.now().isoformat()
            }
        })

    async def update_working_memory(self, content: str, importance: float = 0.5):
        """Working memory - AUTO consent, no prompt needed."""
        return await self.mcp.call_tool("update_working_memory", {
            "content": content,
            "importance": importance
        })

    def _sanitize(self, text: str) -> str:
        """Remove potential PII from preview."""
        import re
        # API keys
        text = re.sub(r"sk-[a-zA-Z0-9]{12,}", "sk-***", text)
        # Emails
        text = re.sub(
            r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            r"\1[0]***@\2",
            text
        )
        return text

class ConsentDeniedError(Exception):
    pass
```

---

## Full Implementation

For a production system, implement these additional components:

### Consent Middleware

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional, Dict, List
from enum import Enum

class ConsentScope(Enum):
    SINGLE = "single"      # One-time approval
    SESSION = "session"    # Valid for session
    CATEGORY = "category"  # Valid for content category

@dataclass
class ConsentResponse:
    approved: bool
    scope: ConsentScope = ConsentScope.SINGLE
    ttl_override: Optional[int] = None
    denial_reason: Optional[str] = None

@dataclass
class ConsentRequest:
    content: str
    layer: MemoryLayer
    consent_level: ConsentLevel
    purpose: Optional[str] = None
    category: Optional[str] = None
    is_relational: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def content_preview(self) -> str:
        """Sanitized preview for display."""
        preview = self.content[:50]
        if len(self.content) > 50:
            preview += "..."
        return preview

    def approve(self, scope: ConsentScope = ConsentScope.SINGLE) -> ConsentResponse:
        return ConsentResponse(approved=True, scope=scope)

    def deny(self, reason: str = None) -> ConsentResponse:
        return ConsentResponse(approved=False, denial_reason=reason)

    def approve_for_session(self) -> ConsentResponse:
        return self.approve(ConsentScope.SESSION)

    def approve_for_category(self) -> ConsentResponse:
        return self.approve(ConsentScope.CATEGORY)


class ConsentMiddleware:
    """Production-ready consent middleware."""

    def __init__(
        self,
        callback: Callable[[ConsentRequest], ConsentResponse] = None,
        max_prompts_per_session: int = 2,
        cache_ttl_hours: int = 24
    ):
        self.callback = callback
        self.max_prompts = max_prompts_per_session
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

        self._prompts_this_session = 0
        self._consent_cache: Dict[str, tuple[ConsentResponse, datetime]] = {}
        self._pending_batch: List[ConsentRequest] = []

    def check(
        self,
        content: str,
        layer: MemoryLayer,
        consent_level: ConsentLevel = None,
        is_relational: bool = False
    ) -> ConsentResponse:
        """Check if consent is granted for this operation."""

        # Determine required level
        if consent_level is None:
            consent_level = self._get_default_level(layer)

        # Relational content requires at least EXPLICIT
        if is_relational and consent_level.value < ConsentLevel.EXPLICIT.value:
            consent_level = ConsentLevel.EXPLICIT

        # AUTO: always approved
        if consent_level == ConsentLevel.AUTO:
            return ConsentResponse(approved=True)

        # IMPLICIT: approved with opt-out
        if consent_level == ConsentLevel.IMPLICIT:
            return ConsentResponse(approved=True)

        # EXPLICIT/PROTECTED: need actual consent
        request = ConsentRequest(
            content=content,
            layer=layer,
            consent_level=consent_level,
            is_relational=is_relational
        )

        # Check cache
        cache_key = self._cache_key(request)
        cached = self._check_cache(cache_key)
        if cached:
            return cached

        # Check prompt limit
        if self._prompts_this_session >= self.max_prompts:
            self._pending_batch.append(request)
            return ConsentResponse(approved=False, denial_reason="Queued for batch")

        # Invoke callback
        if self.callback is None:
            raise RuntimeError("No consent callback registered")

        self._prompts_this_session += 1
        response = self.callback(request)

        # Cache response
        if response.scope != ConsentScope.SINGLE:
            self._cache_response(cache_key, response)

        return response

    def reset_session(self):
        """Reset session state (call at session start)."""
        self._prompts_this_session = 0
        self._pending_batch.clear()

    def pending_requests(self) -> Dict[str, List[ConsentRequest]]:
        """Get pending requests grouped by category."""
        grouped: Dict[str, List[ConsentRequest]] = {}
        for req in self._pending_batch:
            key = f"{req.layer.value}_{req.category or 'general'}"
            grouped.setdefault(key, []).append(req)
        return grouped

    def approve_batch(self, category: str, scope: ConsentScope = ConsentScope.SESSION):
        """Approve all pending requests in a category."""
        pending = self.pending_requests()
        if category not in pending:
            raise KeyError(f"No pending requests for category: {category}")

        for request in pending[category]:
            cache_key = self._cache_key(request)
            response = ConsentResponse(approved=True, scope=scope)
            self._cache_response(cache_key, response)
            self._pending_batch.remove(request)

    def _get_default_level(self, layer: MemoryLayer) -> ConsentLevel:
        return {
            MemoryLayer.WORKING: ConsentLevel.AUTO,
            MemoryLayer.EPISODIC: ConsentLevel.IMPLICIT,
            MemoryLayer.SEMANTIC: ConsentLevel.EXPLICIT,
        }.get(layer, ConsentLevel.EXPLICIT)

    def _cache_key(self, request: ConsentRequest) -> str:
        return f"{hash(request.content)}:{request.layer.value}"

    def _check_cache(self, key: str) -> Optional[ConsentResponse]:
        if key not in self._consent_cache:
            return None
        response, timestamp = self._consent_cache[key]
        if datetime.now(timezone.utc) - timestamp > self.cache_ttl:
            del self._consent_cache[key]
            return None
        return response

    def _cache_response(self, key: str, response: ConsentResponse):
        self._consent_cache[key] = (response, datetime.now(timezone.utc))
```

---

## Usage Examples

### Basic Usage

```python
# Initialize
middleware = ConsentMiddleware(callback=simple_consent_handler)

# Check consent before storing
response = middleware.check(
    content="User prefers dark mode interfaces",
    layer=MemoryLayer.SEMANTIC
)

if response.approved:
    await mcp.call_tool("compress_to_l2_insight", {...})
else:
    print(f"Not stored: {response.denial_reason}")
```

### With Session Caching

```python
def session_aware_handler(request: ConsentRequest) -> ConsentResponse:
    """Handler that offers session-wide approval."""
    print(f"Store: {request.content_preview}?")
    choice = input("(y)es / (n)o / (a)ll similar: ").lower()

    if choice == 'y':
        return request.approve()
    elif choice == 'a':
        return request.approve_for_session()
    else:
        return request.deny()

middleware = ConsentMiddleware(callback=session_aware_handler)

# First request: user chooses 'all similar'
middleware.check("Preference 1", MemoryLayer.SEMANTIC)  # Prompts user

# Subsequent requests: auto-approved from cache
middleware.check("Preference 2", MemoryLayer.SEMANTIC)  # No prompt
middleware.check("Preference 3", MemoryLayer.SEMANTIC)  # No prompt
```

### Batch Approval

```python
# After prompt limit reached, requests are queued
for i in range(5):
    middleware.check(f"Item {i}", MemoryLayer.SEMANTIC)

# View pending requests
print(middleware.pending_requests())
# {"semantic_general": [Item 2, Item 3, Item 4]}

# Approve all at once
middleware.approve_batch("semantic_general", ConsentScope.SESSION)
```

### Relational Content

```python
# Relational content auto-elevates to EXPLICIT
response = middleware.check(
    content="User communicates directly, prefers brevity",
    layer=MemoryLayer.EPISODIC,  # Would normally be IMPLICIT
    is_relational=True           # Elevated to EXPLICIT
)
# User will be prompted even though layer default is IMPLICIT
```

---

## Integration Patterns

### Pattern 1: Decorator

```python
def require_consent(level: ConsentLevel = None, is_relational: bool = False):
    """Decorator to add consent to any storage function."""
    def decorator(func):
        async def wrapper(self, content: str, *args, **kwargs):
            response = self.consent.check(
                content=content,
                layer=kwargs.get('layer', MemoryLayer.SEMANTIC),
                consent_level=level,
                is_relational=is_relational
            )
            if not response.approved:
                raise ConsentDeniedError(response.denial_reason)
            return await func(self, content, *args, **kwargs)
        return wrapper
    return decorator

class MyMemorySystem:
    @require_consent(level=ConsentLevel.EXPLICIT)
    async def store_preference(self, content: str):
        await self.mcp.call_tool("compress_to_l2_insight", {...})
```

### Pattern 2: Context Manager

```python
class ConsentContext:
    """Context manager for consent-protected operations."""

    def __init__(self, middleware: ConsentMiddleware, content: str, layer: MemoryLayer):
        self.middleware = middleware
        self.content = content
        self.layer = layer
        self.approved = False

    def __enter__(self):
        response = self.middleware.check(self.content, self.layer)
        self.approved = response.approved
        if not self.approved:
            raise ConsentDeniedError(response.denial_reason)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

# Usage
with ConsentContext(middleware, "Store this", MemoryLayer.SEMANTIC):
    await mcp.call_tool("compress_to_l2_insight", {...})
```

### Pattern 3: Event-Driven

```python
class ConsentEventMiddleware(ConsentMiddleware):
    """Middleware with event hooks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_consent_granted = []
        self.on_consent_denied = []

    def check(self, *args, **kwargs) -> ConsentResponse:
        response = super().check(*args, **kwargs)

        if response.approved:
            for handler in self.on_consent_granted:
                handler(args[0], response)  # content, response
        else:
            for handler in self.on_consent_denied:
                handler(args[0], response)

        return response

# Register event handlers
middleware = ConsentEventMiddleware(callback=my_handler)
middleware.on_consent_denied.append(lambda c, r: log_denial(c, r.denial_reason))
```

---

## GDPR Revocation

### Basic Revocation

```python
class RevocationService:
    """Handle consent revocation and data deletion."""

    def __init__(self, mcp_client, consent_middleware):
        self.mcp = mcp_client
        self.consent = consent_middleware

    async def revoke_entries(self, entry_ids: list[str]) -> dict:
        """Delete specific entries."""
        # Implementation depends on your storage
        # For cognitive-memory, you might need custom SQL
        deleted = 0
        for entry_id in entry_ids:
            # Delete from L2 insights, graph nodes, etc.
            deleted += 1

        # Clear consent cache for these entries
        self.consent._consent_cache.clear()

        return {"deleted": deleted, "entry_ids": entry_ids}

    async def revoke_by_layer(self, layer: MemoryLayer) -> dict:
        """Delete all entries in a layer."""
        # Query all entries in layer, then delete
        pass

    async def revoke_all(self, force: bool = False) -> dict:
        """Delete everything (with safety check)."""
        if not force:
            # Count entries
            total = await self._count_entries()
            raise UtilityWarning(
                f"This would delete {total} entries. "
                f"Use force=True to proceed."
            )
        # Proceed with deletion
        pass

class UtilityWarning(Exception):
    def __init__(self, message: str, affected_count: int = 0, percentage: float = 0):
        super().__init__(message)
        self.affected_count = affected_count
        self.percentage = percentage
```

---

## Testing

### Unit Test Example

```python
import pytest

def test_auto_consent_always_approved():
    middleware = ConsentMiddleware()
    response = middleware.check("test", MemoryLayer.WORKING)
    assert response.approved is True

def test_explicit_requires_callback():
    middleware = ConsentMiddleware()  # No callback
    with pytest.raises(RuntimeError, match="No consent callback"):
        middleware.check("test", MemoryLayer.SEMANTIC)

def test_relational_elevates_to_explicit():
    approvals = []

    def tracking_handler(req):
        approvals.append(req.consent_level)
        return req.approve()

    middleware = ConsentMiddleware(callback=tracking_handler)
    middleware.check(
        "relationship info",
        MemoryLayer.EPISODIC,  # Normally IMPLICIT
        is_relational=True
    )

    assert approvals[0] == ConsentLevel.EXPLICIT

def test_session_caching():
    call_count = [0]

    def counting_handler(req):
        call_count[0] += 1
        return req.approve_for_session()

    middleware = ConsentMiddleware(callback=counting_handler)

    # First call: handler invoked
    middleware.check("content", MemoryLayer.SEMANTIC)
    assert call_count[0] == 1

    # Second call: cached
    middleware.check("content", MemoryLayer.SEMANTIC)
    assert call_count[0] == 1  # Still 1, not 2
```

---

## See Also

- [Consent Protocol Concepts](../concepts/consent-protocol.md)
- [API Reference](../reference/api-reference.md)
- [i-o-system Reference Implementation](https://github.com/ethrdev/i-o-system)

---

**Document Version:** 1.0
**Last Updated:** 2025-01-02
