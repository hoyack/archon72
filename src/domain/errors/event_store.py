"""Event store errors for Archon 72.

This module provides exception classes for event store operations.
These exceptions are raised by EventStorePort implementations when
storage-related failures occur.

Note: Constitutional violations (e.g., attempting to delete events)
raise ConstitutionalViolationError, not EventStoreError.
"""

from src.domain.exceptions import ConclaveError


class EventStoreError(ConclaveError):
    """Base exception for event store operations.

    Raised when storage-related failures occur in EventStorePort
    implementations. This includes:
    - Connection failures
    - Transaction failures
    - Query errors
    - Constraint violations (non-constitutional)

    For constitutional violations (e.g., delete attempts), use
    ConstitutionalViolationError instead.

    Usage:
        raise EventStoreError("Failed to append event: connection timeout")
    """

    pass


class EventNotFoundError(EventStoreError):
    """Raised when an event cannot be found.

    This is a normal condition (not an error) in many cases,
    so callers should handle this gracefully.

    Usage:
        raise EventNotFoundError(f"Event with sequence {sequence} not found")
    """

    pass


class EventStoreConnectionError(EventStoreError):
    """Raised when connection to event store fails.

    This indicates infrastructure issues that may require
    operational intervention.

    Usage:
        raise EventStoreConnectionError("Failed to connect to database")
    """

    pass
