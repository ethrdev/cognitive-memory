"""
Exception hierarchy for cognitive_memory library.

All exceptions inherit from CognitiveMemoryError for consistent error handling.
"""

from __future__ import annotations


class CognitiveMemoryError(Exception):
    """
    Base exception for all cognitive memory library errors.

    All exceptions raised by the cognitive_memory library inherit from this class,
    allowing for catch-all error handling:

        try:
            store.search("query")
        except CognitiveMemoryError as e:
            logger.error(f"Memory operation failed: {e}")
    """

    pass


class ConnectionError(CognitiveMemoryError):
    """
    Raised when database connection fails.

    This includes:
    - Connection pool exhaustion
    - Database unreachable
    - Authentication failures
    - Connection timeout
    """

    pass


class SearchError(CognitiveMemoryError):
    """
    Raised when search operations fail.

    This includes:
    - Embedding generation failures
    - Invalid search parameters
    - Query execution errors
    """

    pass


class StorageError(CognitiveMemoryError):
    """
    Raised when storage operations fail.

    This includes:
    - Insert/update failures
    - Constraint violations
    - Disk space issues
    """

    pass


class ValidationError(CognitiveMemoryError):
    """
    Raised when input validation fails.

    This includes:
    - Invalid content format
    - Missing required fields
    - Parameter out of range
    """

    pass


class EmbeddingError(CognitiveMemoryError):
    """
    Raised when embedding operations fail.

    This includes:
    - OpenAI API errors
    - Rate limiting
    - Model unavailable
    """

    pass
