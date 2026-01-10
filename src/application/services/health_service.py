"""Health check service (Story 8.1, Task 4).

Application service for liveness and readiness checks.

NFR28 Requirements:
- Liveness: Is the process running?
- Readiness: Are dependencies connected?

Architecture Note:
This service uses application-layer DTOs (DependencyCheckDTO, HealthResponseDTO,
ReadyResponseDTO) to avoid importing from the API layer. The API routes are
responsible for mapping these DTOs to Pydantic response models.

The metrics collector is injected via constructor to avoid importing from
infrastructure layer directly.
"""

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Optional

from src.application.dtos.health import (
    DependencyCheckDTO,
    HealthResponseDTO,
    ReadyResponseDTO,
)

if TYPE_CHECKING:
    from src.application.ports.metrics_collector import MetricsCollectorProtocol


class DependencyChecker(ABC):
    """Abstract base class for dependency health checkers."""

    @abstractmethod
    async def check(self) -> DependencyCheckDTO:
        """Check dependency health.

        Returns:
            DependencyCheckDTO with health status.
        """
        pass


class DatabaseChecker(DependencyChecker):
    """Database connectivity checker.

    Uses injected query function for actual connectivity testing.
    """

    def __init__(
        self, query_fn: Optional[Callable[[], bool]] = None, name: str = "database"
    ) -> None:
        """Initialize database checker.

        Args:
            query_fn: Async function that returns True if db is healthy.
                     If None, uses stub that always returns healthy.
            name: Name for the dependency check.
        """
        self._query_fn = query_fn
        self._name = name

    async def check(self) -> DependencyCheckDTO:
        """Check database connectivity.

        Returns:
            DependencyCheckDTO for database.
        """
        start_time = time.perf_counter()
        try:
            if self._query_fn is not None:
                # Use injected query function for real connectivity test
                healthy = await self._query_fn()
            else:
                # Stub mode: assume healthy (for testing/development)
                healthy = True

            latency_ms = (time.perf_counter() - start_time) * 1000
            return DependencyCheckDTO(
                name=self._name,
                healthy=healthy,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return DependencyCheckDTO(
                name=self._name,
                healthy=False,
                latency_ms=latency_ms,
                error=str(e),
            )


class RedisChecker(DependencyChecker):
    """Redis connectivity checker.

    Uses injected ping function for actual connectivity testing.
    """

    def __init__(
        self, ping_fn: Optional[Callable[[], bool]] = None, name: str = "redis"
    ) -> None:
        """Initialize Redis checker.

        Args:
            ping_fn: Async function that returns True if Redis is healthy.
                    If None, uses stub that always returns healthy.
            name: Name for the dependency check.
        """
        self._ping_fn = ping_fn
        self._name = name

    async def check(self) -> DependencyCheckDTO:
        """Check Redis connectivity.

        Returns:
            DependencyCheckDTO for Redis.
        """
        start_time = time.perf_counter()
        try:
            if self._ping_fn is not None:
                # Use injected ping function for real connectivity test
                healthy = await self._ping_fn()
            else:
                # Stub mode: assume healthy (for testing/development)
                healthy = True

            latency_ms = (time.perf_counter() - start_time) * 1000
            return DependencyCheckDTO(
                name=self._name,
                healthy=healthy,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return DependencyCheckDTO(
                name=self._name,
                healthy=False,
                latency_ms=latency_ms,
                error=str(e),
            )


class EventStoreChecker(DependencyChecker):
    """Event store connectivity checker.

    Uses injected check function for actual connectivity testing.
    """

    def __init__(
        self, check_fn: Optional[Callable[[], bool]] = None, name: str = "event_store"
    ) -> None:
        """Initialize event store checker.

        Args:
            check_fn: Async function that returns True if event store is healthy.
                     If None, uses stub that always returns healthy.
            name: Name for the dependency check.
        """
        self._check_fn = check_fn
        self._name = name

    async def check(self) -> DependencyCheckDTO:
        """Check event store connectivity.

        Returns:
            DependencyCheckDTO for event store.
        """
        start_time = time.perf_counter()
        try:
            if self._check_fn is not None:
                # Use injected check function for real connectivity test
                healthy = await self._check_fn()
            else:
                # Stub mode: assume healthy (for testing/development)
                healthy = True

            latency_ms = (time.perf_counter() - start_time) * 1000
            return DependencyCheckDTO(
                name=self._name,
                healthy=healthy,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return DependencyCheckDTO(
                name=self._name,
                healthy=False,
                latency_ms=latency_ms,
                error=str(e),
            )


class HealthService:
    """Service for health and readiness checks.

    Provides liveness and readiness checks for Kubernetes probes
    and operational monitoring.

    Supports dependency injection for real connectivity testing (AC5).
    """

    def __init__(
        self,
        service_name: str = "api",
        metrics_collector: Optional["MetricsCollectorProtocol"] = None,
        database_checker: Optional[DependencyChecker] = None,
        redis_checker: Optional[DependencyChecker] = None,
        event_store_checker: Optional[DependencyChecker] = None,
    ) -> None:
        """Initialize health service with optional dependency checkers.

        Args:
            service_name: Name of the service for uptime tracking.
            metrics_collector: Metrics collector for uptime tracking.
                If None, uptime will be reported as 0.0.
            database_checker: Checker for database connectivity.
            redis_checker: Checker for Redis connectivity.
            event_store_checker: Checker for event store connectivity.
        """
        self._service_name = service_name
        self._metrics_collector = metrics_collector
        self._database_checker = database_checker or DatabaseChecker()
        self._redis_checker = redis_checker or RedisChecker()
        self._event_store_checker = event_store_checker or EventStoreChecker()

    async def check_liveness(self) -> HealthResponseDTO:
        """Check service liveness.

        Returns:
            HealthResponseDTO with status and uptime.
        """
        uptime = 0.0
        if self._metrics_collector is not None:
            uptime = self._metrics_collector.get_uptime_seconds(self._service_name)

        return HealthResponseDTO(status="healthy", uptime_seconds=uptime)

    async def check_readiness(self) -> ReadyResponseDTO:
        """Check service readiness with dependency checks (AC5).

        Checks connectivity to:
        - Database
        - Redis
        - Event store

        Returns:
            ReadyResponseDTO with status and dependency checks.
        """
        checks: dict[str, DependencyCheckDTO] = {}

        # Check database using injected checker
        db_check = await self._database_checker.check()
        checks["database"] = db_check

        # Check Redis using injected checker
        redis_check = await self._redis_checker.check()
        checks["redis"] = redis_check

        # Check event store using injected checker
        event_store_check = await self._event_store_checker.check()
        checks["event_store"] = event_store_check

        # Determine overall status
        all_healthy = all(check.healthy for check in checks.values())
        status = "ready" if all_healthy else "not-ready"

        return ReadyResponseDTO(status=status, checks=checks)

    # Legacy methods for backward compatibility with existing tests
    async def _check_database(self) -> DependencyCheckDTO:
        """Check database connectivity (legacy, uses injected checker)."""
        return await self._database_checker.check()

    async def _check_redis(self) -> DependencyCheckDTO:
        """Check Redis connectivity (legacy, uses injected checker)."""
        return await self._redis_checker.check()

    async def _check_event_store(self) -> DependencyCheckDTO:
        """Check event store connectivity (legacy, uses injected checker)."""
        return await self._event_store_checker.check()


# Default service instance
_health_service: Optional[HealthService] = None


def get_health_service() -> HealthService:
    """Get or create the health service instance.

    Returns:
        The HealthService instance.
    """
    global _health_service
    if _health_service is None:
        _health_service = HealthService()
    return _health_service


def configure_health_service(
    metrics_collector: Optional["MetricsCollectorProtocol"] = None,
    database_checker: Optional[DependencyChecker] = None,
    redis_checker: Optional[DependencyChecker] = None,
    event_store_checker: Optional[DependencyChecker] = None,
) -> HealthService:
    """Configure the global health service with real dependency checkers.

    Call this at application startup to inject real connectivity tests.

    Args:
        metrics_collector: Metrics collector for uptime tracking.
        database_checker: Real database connectivity checker.
        redis_checker: Real Redis connectivity checker.
        event_store_checker: Real event store connectivity checker.

    Returns:
        Configured HealthService instance.
    """
    global _health_service
    _health_service = HealthService(
        metrics_collector=metrics_collector,
        database_checker=database_checker,
        redis_checker=redis_checker,
        event_store_checker=event_store_checker,
    )
    return _health_service


def reset_health_service() -> None:
    """Reset the health service singleton (for testing only)."""
    global _health_service
    _health_service = None
