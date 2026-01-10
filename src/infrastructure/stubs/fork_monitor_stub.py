"""Fork Monitor stub for testing/development (FR16, Story 3.1, Task 4).

This module provides a stub implementation of ForkMonitor for testing
and development. It allows injecting fork conditions for testing.

Constitutional Constraints:
- FR16: System SHALL continuously monitor for conflicting hashes
- CT-11: Silent failure destroys legitimacy

WARNING: This stub is for development/testing only.
Production must use a real ForkMonitor implementation.
"""

from __future__ import annotations

from src.application.ports.fork_monitor import ForkMonitor
from src.domain.events.fork_detected import ForkDetectedPayload


class ForkMonitorStub(ForkMonitor):
    """Stub implementation of ForkMonitor for testing.

    This stub allows testing fork detection logic without requiring
    a real event store or hash chain.

    Features:
    - Returns no forks by default
    - Supports fork injection via inject_fork()
    - Supports clearing injected forks via clear_fork()
    - Configurable monitoring interval
    - Tracks monitoring state (is_monitoring)

    WARNING: This stub is for development/testing only.
    Production must use a real ForkMonitor implementation.

    Example:
        >>> stub = ForkMonitorStub()
        >>> await stub.check_for_forks()  # Returns None
        >>> stub.inject_fork(fake_fork_payload)
        >>> await stub.check_for_forks()  # Returns fake_fork_payload
    """

    def __init__(
        self,
        *,
        monitoring_interval_seconds: int = 10,
        service_id: str = "fork-monitor-stub",
    ) -> None:
        """Initialize the stub.

        Args:
            monitoring_interval_seconds: Interval between fork checks (default 10s)
            service_id: Service identifier for attribution (default "fork-monitor-stub")
        """
        self._monitoring_interval_seconds = monitoring_interval_seconds
        self._service_id = service_id
        self._injected_fork: ForkDetectedPayload | None = None
        self._is_monitoring = False

    @property
    def monitoring_interval_seconds(self) -> int:
        """Get the monitoring interval in seconds."""
        return self._monitoring_interval_seconds

    @property
    def service_id(self) -> str:
        """Get the service ID."""
        return self._service_id

    @property
    def is_monitoring(self) -> bool:
        """Check if monitoring is currently active."""
        return self._is_monitoring

    async def check_for_forks(self) -> ForkDetectedPayload | None:
        """Stub: Return injected fork or None.

        Returns:
            The injected fork payload if one was set, None otherwise.
        """
        return self._injected_fork

    async def start_monitoring(self) -> None:
        """Stub: Mark monitoring as started.

        Does not actually start background monitoring - just sets state.
        """
        self._is_monitoring = True

    async def stop_monitoring(self) -> None:
        """Stub: Mark monitoring as stopped.

        Does not actually stop anything - just sets state.
        """
        self._is_monitoring = False

    def inject_fork(self, fork: ForkDetectedPayload) -> None:
        """Inject a fork condition for testing.

        After calling this, check_for_forks() will return the injected fork.

        Args:
            fork: The fork payload to return from check_for_forks()
        """
        self._injected_fork = fork

    def clear_fork(self) -> None:
        """Clear any injected fork condition.

        After calling this, check_for_forks() will return None.
        """
        self._injected_fork = None
