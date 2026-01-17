"""Tests for TimeAuthorityProtocol port (HARDENING-1, AC4).

This module tests the TimeAuthorityProtocol interface that defines
how services obtain timestamps consistently.

Constitutional Constraint (CT-3):
Ordering via sequence numbers only (time is unreliable) - but when we do
use time, it must come from a single authority for consistency and auditability.
"""

import time
from datetime import datetime, timezone

import pytest

from src.application.ports.time_authority import TimeAuthorityProtocol


class TestTimeAuthorityProtocol:
    """Tests for TimeAuthorityProtocol interface (AC4)."""

    def test_protocol_defines_now_method(self) -> None:
        """AC4: Protocol must define now() -> datetime method."""
        # Verify the method exists in the protocol
        assert hasattr(TimeAuthorityProtocol, "now")
        # Check it's an abstract method by verifying __abstractmethods__
        assert "now" in TimeAuthorityProtocol.__abstractmethods__

    def test_protocol_defines_utcnow_method(self) -> None:
        """AC4: Protocol must define utcnow() -> datetime method."""
        assert hasattr(TimeAuthorityProtocol, "utcnow")
        assert "utcnow" in TimeAuthorityProtocol.__abstractmethods__

    def test_protocol_defines_monotonic_method(self) -> None:
        """AC4: Protocol must define monotonic() -> float method."""
        assert hasattr(TimeAuthorityProtocol, "monotonic")
        assert "monotonic" in TimeAuthorityProtocol.__abstractmethods__

    def test_protocol_cannot_be_instantiated(self) -> None:
        """Protocol is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            TimeAuthorityProtocol()  # type: ignore[abstract]


class ConcreteTimeAuthority(TimeAuthorityProtocol):
    """Concrete implementation for testing interface compliance."""

    def now(self) -> datetime:
        """Return current local time."""
        return datetime.now(timezone.utc)

    def utcnow(self) -> datetime:
        """Return current UTC time."""
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        """Return monotonic clock value."""
        return time.monotonic()


class TestConcreteImplementation:
    """Tests that a concrete implementation satisfies the protocol."""

    def test_concrete_implementation_satisfies_protocol(self) -> None:
        """A proper implementation can be instantiated."""
        impl = ConcreteTimeAuthority()
        assert isinstance(impl, TimeAuthorityProtocol)

    def test_now_returns_datetime(self) -> None:
        """now() returns a datetime object."""
        impl = ConcreteTimeAuthority()
        result = impl.now()
        assert isinstance(result, datetime)

    def test_utcnow_returns_datetime(self) -> None:
        """utcnow() returns a datetime object."""
        impl = ConcreteTimeAuthority()
        result = impl.utcnow()
        assert isinstance(result, datetime)

    def test_monotonic_returns_float(self) -> None:
        """monotonic() returns a float."""
        impl = ConcreteTimeAuthority()
        result = impl.monotonic()
        assert isinstance(result, float)

    def test_monotonic_is_monotonically_increasing(self) -> None:
        """monotonic() values never decrease."""
        impl = ConcreteTimeAuthority()
        values = [impl.monotonic() for _ in range(100)]
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1], "monotonic() must never decrease"
