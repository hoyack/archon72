"""Time Authority Protocol - interface for consistent timestamp provisioning.

This port defines the contract for obtaining timestamps throughout the system.
All services that need timestamps MUST inject a TimeAuthorityProtocol implementation
instead of calling datetime.now() or datetime.utcnow() directly.

HARDENING-1: TimeAuthorityService Mandatory Injection
Source: Gov Epic 8 Retrospective Action Item #1 (2026-01-15)

Constitutional Context:
- CT-3: Ordering via sequence numbers only (time is unreliable)
- CT-12: Witnessing creates accountability - timestamps must be auditable

Benefits:
1. **Consistency**: All services get time from single authority
2. **Testability**: Tests can inject FakeTimeAuthority for deterministic behavior
3. **Auditability**: Timestamps provably from single source
4. **Reliability**: No flaky tests from time-dependent logic

Team Agreement (Gov Epic 8 Retrospective):
> No `datetime.now()` calls in production code - always inject time authority
"""

from abc import ABC, abstractmethod
from datetime import datetime


class TimeAuthorityProtocol(ABC):
    """Abstract interface for time authority.

    All services requiring timestamps MUST inject this protocol
    instead of calling datetime.now() or datetime.utcnow() directly.

    Example usage:
        class MyService:
            def __init__(self, time_authority: TimeAuthorityProtocol) -> None:
                self._time = time_authority

            def process(self) -> None:
                now = self._time.now()  # NOT datetime.now()
                ...

    For production:
        Use TimeAuthorityService from src/application/services/

    For testing:
        Use FakeTimeAuthority from tests/helpers/fake_time_authority.py
    """

    @abstractmethod
    def now(self) -> datetime:
        """Return current local time with timezone awareness.

        Returns:
            Current datetime with timezone information (UTC recommended).

        Note:
            Implementations should return timezone-aware datetimes.
            UTC is strongly recommended for consistency.
        """
        ...

    @abstractmethod
    def utcnow(self) -> datetime:
        """Return current UTC time.

        Returns:
            Current datetime in UTC timezone.

        Note:
            This should always return a timezone-aware datetime in UTC.
        """
        ...

    @abstractmethod
    def monotonic(self) -> float:
        """Return monotonic clock value for measuring elapsed time.

        Returns:
            Monotonically increasing float value (in seconds).

        Note:
            Use this for measuring elapsed time, not for timestamps.
            Values are guaranteed to never decrease (unlike wall clock).
            The reference point is arbitrary - only differences are meaningful.
        """
        ...
