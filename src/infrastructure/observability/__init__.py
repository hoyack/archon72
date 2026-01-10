"""Observability infrastructure for structured logging and correlation (Story 8.7, WR-1).

This module provides cross-cutting observability concerns:
- Structured JSON logging with structlog
- Correlation ID management for distributed tracing
- Log processors for consistent output format

Constitutional Constraints:
- NFR27: Operational monitoring with structured logging
- WR-1: Structured logging convention for all services

Usage:
    from src.infrastructure.observability import (
        configure_structlog,
        get_correlation_id,
        set_correlation_id,
    )

    # At startup
    configure_structlog(environment="production")

    # In request handling
    set_correlation_id(request_correlation_id)
    logger = structlog.get_logger().bind(correlation_id=get_correlation_id())
"""

from src.infrastructure.observability.correlation import (
    correlation_id_processor,
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
)
from src.infrastructure.observability.logging import configure_structlog

__all__: list[str] = [
    "configure_structlog",
    "correlation_id_processor",
    "generate_correlation_id",
    "get_correlation_id",
    "set_correlation_id",
]
