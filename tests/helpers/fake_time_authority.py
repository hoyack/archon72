"""FakeTimeAuthority - Controllable time authority for deterministic tests.

HARDENING-3: FakeTimeAuthority Test Helper
Source: Gov Epic 8 Retrospective Action Item #3 (2026-01-15)

This module provides a fake implementation of TimeAuthorityProtocol that allows
tests to control time, making time-dependent tests deterministic and reliable.

Team Agreement (Gov Epic 8 Retrospective):
> Time-dependent tests must use `FakeTimeAuthority` or `freezegun`

Usage Patterns:
--------------

1. Frozen Time Pattern:
    Tests that need a specific point in time.

    >>> fake_time = FakeTimeAuthority(frozen_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
    >>> service = MyService(time_authority=fake_time)
    >>> assert fake_time.now() == datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    >>> # Time never changes unless you advance it
    >>> assert fake_time.now() == datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

2. Time Advancement Pattern:
    Tests that need to simulate time passing.

    >>> fake_time = FakeTimeAuthority(frozen_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
    >>> fake_time.advance(seconds=3600)  # 1 hour later
    >>> assert fake_time.now() == datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc)

3. Timedelta Advancement:
    Using timedelta for more readable time manipulation.

    >>> from datetime import timedelta
    >>> fake_time = FakeTimeAuthority()
    >>> fake_time.advance(timedelta(days=1, hours=2))
    >>> # Time advanced by 1 day and 2 hours

4. Pytest Fixture Pattern:
    Use the `fake_time_authority` fixture from conftest.py.

    def test_timeout_detection(fake_time_authority):
        fake_time_authority.set_time(datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        service = SuppressionDetectionService(time_authority=fake_time_authority)

        fake_time_authority.advance(seconds=3600)  # 1 hour later

        result = service.check_timeout(acknowledgment)
        assert result.is_timed_out

5. Monotonic Clock Testing:
    The monotonic clock is tied to time advancement.

    >>> fake_time = FakeTimeAuthority()
    >>> m1 = fake_time.monotonic()
    >>> fake_time.advance(seconds=10)
    >>> m2 = fake_time.monotonic()
    >>> assert m2 - m1 == 10.0  # Monotonic advanced by 10 seconds
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.application.ports.time_authority import TimeAuthorityProtocol


class FakeTimeAuthority(TimeAuthorityProtocol):
    """Controllable time authority for deterministic tests.

    This implementation allows tests to:
    - Freeze time at a specific point
    - Advance time by a specified amount
    - Set time to an arbitrary value
    - Get deterministic monotonic clock values

    Attributes:
        _current_time: The controlled current time.
        _monotonic_offset: Base offset for monotonic clock.
        _monotonic_advances: Accumulated advances for monotonic clock.

    Example:
        >>> # Frozen time test
        >>> fake_time = FakeTimeAuthority(
        ...     frozen_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        ... )
        >>> assert fake_time.now().hour == 10
        >>>
        >>> # Advance time
        >>> fake_time.advance(seconds=3600)  # 1 hour
        >>> assert fake_time.now().hour == 11
    """

    def __init__(
        self,
        frozen_at: datetime | None = None,
        *,
        start_monotonic: float = 0.0,
    ) -> None:
        """Initialize the fake time authority.

        Args:
            frozen_at: Optional datetime to freeze time at. If not provided,
                defaults to 2026-01-01T00:00:00 UTC for predictable tests.
            start_monotonic: Starting value for monotonic clock. Defaults to 0.0.

        Note:
            If frozen_at is timezone-naive, UTC is assumed.
        """
        if frozen_at is None:
            # Default to a predictable time for tests
            frozen_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Ensure timezone awareness
        if frozen_at.tzinfo is None:
            frozen_at = frozen_at.replace(tzinfo=timezone.utc)

        self._current_time: datetime = frozen_at
        self._monotonic_base: float = start_monotonic
        self._monotonic_advances: float = 0.0

    # =========================================================================
    # TimeAuthorityProtocol Implementation
    # =========================================================================

    def now(self) -> datetime:
        """Return the controlled current time.

        Returns:
            The frozen/controlled datetime with timezone (UTC).

        Note:
            Time does not advance automatically. Use advance() or set_time()
            to change the returned value.
        """
        return self._current_time

    def utcnow(self) -> datetime:
        """Return the controlled current UTC time.

        Returns:
            Same as now() - the frozen/controlled datetime in UTC.

        Note:
            Equivalent to now() since both return UTC time.
        """
        return self._current_time

    def monotonic(self) -> float:
        """Return the controlled monotonic clock value.

        Returns:
            A float representing elapsed seconds since start.

        Note:
            The monotonic clock advances when you call advance().
            It never goes backward, ensuring monotonicity.
        """
        return self._monotonic_base + self._monotonic_advances

    # =========================================================================
    # Test Control Methods
    # =========================================================================

    def advance(
        self,
        seconds: float | int | None = None,
        delta: timedelta | None = None,
    ) -> None:
        """Advance time by the specified amount.

        Args:
            seconds: Number of seconds to advance (int or float).
            delta: A timedelta to advance by. Takes precedence over seconds.

        Raises:
            ValueError: If neither seconds nor delta is provided.
            ValueError: If attempting to advance by negative time.

        Example:
            >>> fake_time = FakeTimeAuthority()
            >>> fake_time.advance(seconds=3600)  # Advance 1 hour
            >>> fake_time.advance(delta=timedelta(days=1))  # Advance 1 day
        """
        if delta is not None:
            advance_seconds = delta.total_seconds()
        elif seconds is not None:
            advance_seconds = float(seconds)
        else:
            raise ValueError("Must provide either 'seconds' or 'delta' argument")

        if advance_seconds < 0:
            raise ValueError(
                f"Cannot advance time backwards. Got {advance_seconds} seconds. "
                "Use set_time() for explicit time changes."
            )

        self._current_time += timedelta(seconds=advance_seconds)
        self._monotonic_advances += advance_seconds

    def set_time(self, dt: datetime) -> None:
        """Set the current time to an explicit value.

        Args:
            dt: The datetime to set as current time.

        Note:
            This does NOT affect the monotonic clock. Use this for tests
            that need to jump to a specific time without advancing monotonic.
            If dt is timezone-naive, UTC is assumed.

        Warning:
            Setting time backwards may cause issues in tests that rely on
            monotonically increasing wall clock. Prefer advance() when possible.

        Example:
            >>> fake_time = FakeTimeAuthority()
            >>> fake_time.set_time(datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc))
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        self._current_time = dt

    def reset(
        self,
        to: datetime | None = None,
        *,
        reset_monotonic: bool = True,
    ) -> None:
        """Reset time to a specific point or default.

        Args:
            to: Optional datetime to reset to. If not provided, resets to
                the default (2026-01-01T00:00:00 UTC).
            reset_monotonic: If True (default), also reset monotonic clock to 0.

        Example:
            >>> fake_time = FakeTimeAuthority()
            >>> fake_time.advance(seconds=3600)
            >>> fake_time.reset()  # Back to default time and monotonic=0
        """
        if to is None:
            to = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        if to.tzinfo is None:
            to = to.replace(tzinfo=timezone.utc)

        self._current_time = to

        if reset_monotonic:
            self._monotonic_advances = 0.0

    # =========================================================================
    # Inspection Methods (for test assertions)
    # =========================================================================

    @property
    def current_time(self) -> datetime:
        """Get the current controlled time (readonly property).

        Returns:
            The current frozen/controlled datetime.

        Example:
            >>> fake_time = FakeTimeAuthority(frozen_at=datetime(2026, 1, 15, tzinfo=timezone.utc))
            >>> assert fake_time.current_time.day == 15
        """
        return self._current_time

    @property
    def elapsed_monotonic(self) -> float:
        """Get total elapsed time on monotonic clock since creation.

        Returns:
            Accumulated advances in seconds.

        Example:
            >>> fake_time = FakeTimeAuthority()
            >>> fake_time.advance(seconds=100)
            >>> assert fake_time.elapsed_monotonic == 100.0
        """
        return self._monotonic_advances

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return (
            f"FakeTimeAuthority("
            f"current_time={self._current_time.isoformat()}, "
            f"monotonic={self.monotonic():.3f})"
        )
