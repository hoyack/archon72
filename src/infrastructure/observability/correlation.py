"""Correlation ID management for distributed tracing (Story 8.7, AC2).

This module provides correlation ID management using contextvars,
ensuring correlation IDs are consistently available across async
boundaries within a single request context.

Constitutional Constraints:
- NFR27: Operational monitoring with distributed tracing support
- AC2: Correlation ID consistency across all services

Usage:
    # In middleware (request start)
    correlation_id = request.headers.get("X-Correlation-ID") or generate_correlation_id()
    set_correlation_id(correlation_id)

    # In services
    log = structlog.get_logger().bind(correlation_id=get_correlation_id())

    # In structlog configuration
    processors = [..., correlation_id_processor, ...]
"""

from contextvars import ContextVar
from typing import Any
from uuid import uuid4

# Context variable for correlation ID
# Default is empty string to avoid None type issues
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def generate_correlation_id() -> str:
    """Generate a new correlation ID (UUID4).

    Returns:
        A new UUID4 string suitable for correlation tracking.
    """
    return str(uuid4())


def get_correlation_id() -> str:
    """Get the current correlation ID from context.

    If no correlation ID has been set in the current context,
    returns an empty string. Callers should handle this case
    appropriately (e.g., generating a new ID if needed).

    Returns:
        The current correlation ID or empty string if not set.
    """
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID in the current context.

    This should be called at the start of each request to establish
    the correlation context for all downstream operations.

    Args:
        correlation_id: The correlation ID to set.
    """
    _correlation_id.set(correlation_id)


def correlation_id_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor to add correlation_id to every log entry.

    This processor automatically adds the current correlation ID from
    context to every log entry, ensuring consistent tracing.

    Args:
        logger: The logger instance (unused, required by structlog).
        method_name: The logging method name (unused, required by structlog).
        event_dict: The event dictionary to modify.

    Returns:
        The event dictionary with correlation_id added.
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict
