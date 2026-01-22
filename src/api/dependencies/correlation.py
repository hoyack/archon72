"""Correlation ID FastAPI dependency (Story 8.7, AC2).

This module provides FastAPI dependencies for correlation ID management.
While the LoggingMiddleware handles correlation ID for all requests,
this dependency can be used to explicitly access the correlation ID
in route handlers when needed.

Usage:
    from fastapi import Depends
    from src.api.dependencies.correlation import get_correlation_id_header

    @router.get("/example")
    async def example_endpoint(
        correlation_id: str = Depends(get_correlation_id_header)
    ) -> dict:
        return {"correlation_id": correlation_id}
"""

from fastapi import Header

from src.bootstrap.correlation import (
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
)

# Header name for correlation ID (matching middleware)
CORRELATION_HEADER = "X-Correlation-ID"


async def get_correlation_id_header(
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
) -> str:
    """FastAPI dependency to get or create correlation ID.

    This dependency extracts the correlation ID from the X-Correlation-ID
    header if present, otherwise generates a new one. It also ensures
    the correlation ID is set in the context for downstream use.

    Note: If LoggingMiddleware is in use (recommended), the correlation
    ID will already be set in context. This dependency can still be used
    to explicitly access it in route handlers.

    Args:
        x_correlation_id: The correlation ID from request header (optional).

    Returns:
        The correlation ID (either from header, context, or newly generated).
    """
    # Check if already set in context (by middleware)
    existing = get_correlation_id()
    if existing:
        return existing

    # Use header value or generate new
    correlation_id = x_correlation_id or generate_correlation_id()

    # Set in context for downstream
    set_correlation_id(correlation_id)

    return correlation_id
