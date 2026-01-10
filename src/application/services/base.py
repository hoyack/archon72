"""Base service logging mixin (Story 8.7, AC4, WR-1).

This module provides the LoggingMixin class for standardized structured
logging across all application services, following the WR-1 architecture
pattern from architecture.md.

Constitutional Constraints:
- WR-1: Structured logging convention for all services
- AC4: Service logger base pattern with _log_operation()

Usage:
    from src.application.services.base import LoggingMixin

    class MyService(LoggingMixin):
        def __init__(self, dependency: SomePort) -> None:
            self._dependency = dependency
            self._init_logger()  # Initialize structured logger

        async def do_something(self) -> None:
            log = self._log_operation("do_something", item_id="123")
            log.info("operation_started")
            # ... do work ...
            log.info("operation_completed")
"""

import structlog

from src.infrastructure.observability.correlation import get_correlation_id


class LoggingMixin:
    """Mixin providing structured logging for services (WR-1).

    This mixin provides the _log_operation() pattern defined in architecture.md
    for consistent, correlated logging across all constitutional services.

    The logger is bound with:
    - service: The class name of the service
    - component: The component type (default: "constitutional")

    Each operation gets:
    - operation: The name of the operation being performed
    - correlation_id: From context for distributed tracing
    - Any additional context passed to _log_operation()

    Attributes:
        _log: The structlog BoundLogger for this service instance.
    """

    _log: structlog.BoundLogger

    def _init_logger(self, component: str = "constitutional") -> None:
        """Initialize the logger with service name binding.

        Should be called in __init__ after setting up dependencies.

        Args:
            component: The component type for log categorization.
                      Defaults to "constitutional" for constitutional services.
        """
        self._log = structlog.get_logger().bind(
            service=self.__class__.__name__,
            component=component,
        )

    def _log_operation(
        self,
        operation: str,
        **context: object,
    ) -> structlog.BoundLogger:
        """Create operation-scoped logger with correlation ID.

        Returns a bound logger with operation name and correlation ID
        from context. Additional context can be passed as keyword arguments.

        Args:
            operation: Name of the operation being performed.
            **context: Additional context to bind to the logger.

        Returns:
            BoundLogger with operation and correlation context.

        Example:
            log = self._log_operation("create_bundle", meeting_id=str(meeting_id))
            log.info("bundle_creation_started")
            # ... do work ...
            log.info("bundle_creation_completed", bundle_id=bundle.id)
        """
        return self._log.bind(
            operation=operation,
            correlation_id=get_correlation_id(),
            **context,
        )
