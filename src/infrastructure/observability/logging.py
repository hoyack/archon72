"""Structured logging configuration with structlog (Story 8.7, AC1, AC3).

This module provides centralized structlog configuration for the application,
supporting both production (JSON) and development (console) output modes.

Constitutional Constraints:
- NFR27: Operational monitoring with structured logging
- AC1: JSON formatted log entries with required fields
- AC3: Configurable log levels per environment

Log Entry Format (AC1):
    {
        "timestamp": "2024-01-01T00:00:00.000000Z",
        "level": "info",
        "event": "message",
        "correlation_id": "uuid",
        "service": "service_name",
        ...additional context
    }

Usage:
    # At application startup
    from src.infrastructure.observability import configure_structlog

    configure_structlog(environment="production")  # JSON output
    configure_structlog(environment="development")  # Console output

    # Then use structlog normally
    import structlog
    log = structlog.get_logger()
    log.info("event_name", key="value")
"""

import logging
import os
from typing import cast

import structlog
from structlog.typing import Processor

from src.infrastructure.observability.correlation import correlation_id_processor

# Environment variable for log level (default: INFO)
LOG_LEVEL_ENV = "LOG_LEVEL"
DEFAULT_LOG_LEVEL = "INFO"


def _get_log_level() -> int:
    """Get the configured log level from environment.

    Returns:
        The logging level integer (e.g., logging.INFO).
    """
    level_name = os.getenv(LOG_LEVEL_ENV, DEFAULT_LOG_LEVEL).upper()
    return getattr(logging, level_name, logging.INFO)


def configure_structlog(environment: str = "production") -> None:
    """Configure structlog for the application.

    This function configures structlog with appropriate processors
    for the given environment. Should be called once at application startup.

    Args:
        environment: 'production' for JSON output, 'development' for console.
                    Defaults to 'production'.

    Configuration:
        Production:
            - JSON output for machine parsing
            - ISO 8601 timestamps
            - All context fields preserved

        Development:
            - Colored console output for readability
            - ISO 8601 timestamps
            - All context fields preserved
    """
    # Shared processors for all environments
    shared_processors: list[Processor] = [
        # Merge context from contextvars (async support)
        structlog.contextvars.merge_contextvars,
        # Add log level
        structlog.processors.add_log_level,
        # Add ISO 8601 timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add correlation ID from context
        cast(Processor, correlation_id_processor),
        # Handle stack traces nicely
        structlog.processors.StackInfoRenderer(),
        # Handle Unicode properly
        structlog.processors.UnicodeDecoder(),
    ]

    # Environment-specific final processor
    if environment == "production":
        # JSON output for log aggregation
        final_processor: Processor = structlog.processors.JSONRenderer()
    else:
        # Pretty console output for development
        final_processor = structlog.dev.ConsoleRenderer(colors=True)

    # Combine processors
    processors = shared_processors + [final_processor]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(_get_log_level()),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger_for_service(
    service_name: str, component: str = "constitutional"
) -> structlog.BoundLogger:
    """Get a pre-bound logger for a service.

    Creates a logger with service name and component already bound,
    following the WR-1 structured logging convention.

    Args:
        service_name: The name of the service (typically class name).
        component: The component type (default: "constitutional").

    Returns:
        A BoundLogger with service and component bound.
    """
    return structlog.get_logger().bind(
        service=service_name,
        component=component,
    )
