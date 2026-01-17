"""Tests for FakeTimeAuthority test helper.

HARDENING-3: FakeTimeAuthority Test Helper
These tests validate the FakeTimeAuthority class itself to ensure
it provides reliable, deterministic time control for other tests.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports.time_authority import TimeAuthorityProtocol
from tests.helpers.fake_time_authority import FakeTimeAuthority


class TestFakeTimeAuthorityProtocolCompliance:
    """AC1: FakeTimeAuthority must implement TimeAuthorityProtocol."""

    def test_implements_protocol(self) -> None:
        """Verify FakeTimeAuthority is a valid TimeAuthorityProtocol."""
        fake_time = FakeTimeAuthority()
        assert isinstance(fake_time, TimeAuthorityProtocol)

    def test_has_now_method(self) -> None:
        """Verify now() method exists and returns datetime."""
        fake_time = FakeTimeAuthority()
        result = fake_time.now()
        assert isinstance(result, datetime)

    def test_has_utcnow_method(self) -> None:
        """Verify utcnow() method exists and returns datetime."""
        fake_time = FakeTimeAuthority()
        result = fake_time.utcnow()
        assert isinstance(result, datetime)

    def test_has_monotonic_method(self) -> None:
        """Verify monotonic() method exists and returns float."""
        fake_time = FakeTimeAuthority()
        result = fake_time.monotonic()
        assert isinstance(result, float)


class TestControllableTime:
    """AC2: now() and utcnow() return controlled time value."""

    def test_now_returns_controlled_time(self) -> None:
        """Verify now() returns the controlled time."""
        frozen_at = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        assert fake_time.now() == frozen_at

    def test_utcnow_returns_controlled_time(self) -> None:
        """Verify utcnow() returns the controlled time."""
        frozen_at = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        assert fake_time.utcnow() == frozen_at

    def test_now_and_utcnow_are_equal(self) -> None:
        """Verify now() and utcnow() return same value."""
        fake_time = FakeTimeAuthority()

        assert fake_time.now() == fake_time.utcnow()

    def test_default_time_is_predictable(self) -> None:
        """Verify default time is 2026-01-01T00:00:00 UTC."""
        fake_time = FakeTimeAuthority()

        expected = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert fake_time.now() == expected

    def test_multiple_calls_return_same_time(self) -> None:
        """Verify time doesn't change without explicit advancement."""
        fake_time = FakeTimeAuthority()

        first_call = fake_time.now()
        second_call = fake_time.now()
        third_call = fake_time.now()

        assert first_call == second_call == third_call


class TestTimeAdvancement:
    """AC3: advance() method advances time correctly."""

    def test_advance_by_seconds_int(self) -> None:
        """Verify advance(seconds=N) works with int."""
        frozen_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        fake_time.advance(seconds=3600)  # 1 hour

        expected = datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        assert fake_time.now() == expected

    def test_advance_by_seconds_float(self) -> None:
        """Verify advance(seconds=N) works with float."""
        frozen_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        fake_time.advance(seconds=0.5)  # 500ms

        expected = datetime(2026, 1, 15, 10, 0, 0, 500000, tzinfo=timezone.utc)
        assert fake_time.now() == expected

    def test_advance_by_timedelta(self) -> None:
        """Verify advance(delta=timedelta) works correctly."""
        frozen_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        fake_time.advance(delta=timedelta(days=1, hours=2, minutes=30))

        expected = datetime(2026, 1, 16, 12, 30, 0, tzinfo=timezone.utc)
        assert fake_time.now() == expected

    def test_advance_multiple_times(self) -> None:
        """Verify multiple advances accumulate correctly."""
        frozen_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        fake_time.advance(seconds=3600)  # +1 hour
        fake_time.advance(seconds=1800)  # +30 minutes
        fake_time.advance(delta=timedelta(minutes=15))  # +15 minutes

        expected = datetime(2026, 1, 15, 11, 45, 0, tzinfo=timezone.utc)
        assert fake_time.now() == expected

    def test_advance_requires_argument(self) -> None:
        """Verify advance() raises error without arguments."""
        fake_time = FakeTimeAuthority()

        with pytest.raises(ValueError, match="Must provide either"):
            fake_time.advance()

    def test_advance_negative_time_raises_error(self) -> None:
        """Verify advance() rejects negative time."""
        fake_time = FakeTimeAuthority()

        with pytest.raises(ValueError, match="Cannot advance time backwards"):
            fake_time.advance(seconds=-100)

    def test_advance_negative_timedelta_raises_error(self) -> None:
        """Verify advance() rejects negative timedelta."""
        fake_time = FakeTimeAuthority()

        with pytest.raises(ValueError, match="Cannot advance time backwards"):
            fake_time.advance(delta=timedelta(hours=-1))

    def test_timedelta_takes_precedence_over_seconds(self) -> None:
        """Verify delta argument takes precedence when both provided."""
        frozen_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        # Both provided - delta should win
        fake_time.advance(seconds=3600, delta=timedelta(minutes=30))

        expected = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert fake_time.now() == expected


class TestTimeFreezePattern:
    """AC4: FakeTimeAuthority(frozen_at=...) freezes time."""

    def test_frozen_time_does_not_change(self) -> None:
        """Verify frozen time stays constant without advance()."""
        frozen_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        # Multiple calls should return exact same time
        for _ in range(100):
            assert fake_time.now() == frozen_at

    def test_frozen_time_with_naive_datetime(self) -> None:
        """Verify naive datetime gets UTC timezone."""
        naive_dt = datetime(2026, 1, 15, 10, 0, 0)  # No tzinfo
        fake_time = FakeTimeAuthority(frozen_at=naive_dt)

        result = fake_time.now()
        assert result.tzinfo == timezone.utc
        assert result == datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    def test_frozen_time_preserves_timezone(self) -> None:
        """Verify provided timezone is preserved."""
        utc_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=utc_time)

        assert fake_time.now().tzinfo == timezone.utc


class TestMonotonicClockSimulation:
    """AC5: monotonic() returns monotonically increasing values."""

    def test_monotonic_starts_at_zero_by_default(self) -> None:
        """Verify monotonic clock starts at 0.0 by default."""
        fake_time = FakeTimeAuthority()

        assert fake_time.monotonic() == 0.0

    def test_monotonic_starts_at_custom_value(self) -> None:
        """Verify monotonic clock can start at custom value."""
        fake_time = FakeTimeAuthority(start_monotonic=100.0)

        assert fake_time.monotonic() == 100.0

    def test_monotonic_advances_with_time(self) -> None:
        """Verify monotonic advances when advance() is called."""
        fake_time = FakeTimeAuthority()

        m1 = fake_time.monotonic()
        fake_time.advance(seconds=10)
        m2 = fake_time.monotonic()

        assert m2 - m1 == 10.0

    def test_monotonic_never_decreases(self) -> None:
        """Verify monotonic clock never goes backwards."""
        fake_time = FakeTimeAuthority()

        values = []
        for i in range(10):
            fake_time.advance(seconds=1)
            values.append(fake_time.monotonic())

        # Verify each value is greater than previous
        for i in range(1, len(values)):
            assert values[i] > values[i - 1]

    def test_monotonic_without_advance_stays_same(self) -> None:
        """Verify monotonic doesn't change without advance()."""
        fake_time = FakeTimeAuthority()

        m1 = fake_time.monotonic()
        m2 = fake_time.monotonic()
        m3 = fake_time.monotonic()

        assert m1 == m2 == m3

    def test_monotonic_accumulates_advances(self) -> None:
        """Verify monotonic correctly accumulates multiple advances."""
        fake_time = FakeTimeAuthority()

        fake_time.advance(seconds=5)
        fake_time.advance(seconds=10)
        fake_time.advance(delta=timedelta(seconds=15))

        assert fake_time.monotonic() == 30.0


class TestSetTimeMethod:
    """Test set_time() for explicit time setting."""

    def test_set_time_changes_current_time(self) -> None:
        """Verify set_time() changes the current time."""
        fake_time = FakeTimeAuthority()
        new_time = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

        fake_time.set_time(new_time)

        assert fake_time.now() == new_time

    def test_set_time_does_not_affect_monotonic(self) -> None:
        """Verify set_time() doesn't change monotonic clock."""
        fake_time = FakeTimeAuthority()
        fake_time.advance(seconds=100)

        monotonic_before = fake_time.monotonic()
        fake_time.set_time(datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
        monotonic_after = fake_time.monotonic()

        assert monotonic_before == monotonic_after

    def test_set_time_with_naive_datetime(self) -> None:
        """Verify set_time() adds UTC to naive datetime."""
        fake_time = FakeTimeAuthority()
        naive_dt = datetime(2026, 6, 15, 12, 0, 0)  # No tzinfo

        fake_time.set_time(naive_dt)

        result = fake_time.now()
        assert result.tzinfo == timezone.utc


class TestResetMethod:
    """Test reset() for returning to known state."""

    def test_reset_to_default(self) -> None:
        """Verify reset() returns to default time."""
        fake_time = FakeTimeAuthority()
        fake_time.advance(seconds=86400)  # Advance 1 day

        fake_time.reset()

        expected = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert fake_time.now() == expected

    def test_reset_to_specific_time(self) -> None:
        """Verify reset(to=...) sets specific time."""
        fake_time = FakeTimeAuthority()
        reset_time = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)

        fake_time.reset(to=reset_time)

        assert fake_time.now() == reset_time

    def test_reset_clears_monotonic(self) -> None:
        """Verify reset() clears monotonic by default."""
        fake_time = FakeTimeAuthority()
        fake_time.advance(seconds=100)

        fake_time.reset()

        assert fake_time.monotonic() == 0.0

    def test_reset_preserves_monotonic_when_requested(self) -> None:
        """Verify reset(reset_monotonic=False) preserves monotonic."""
        fake_time = FakeTimeAuthority()
        fake_time.advance(seconds=100)

        fake_time.reset(reset_monotonic=False)

        assert fake_time.monotonic() == 100.0


class TestInspectionMethods:
    """Test readonly inspection properties."""

    def test_current_time_property(self) -> None:
        """Verify current_time property returns controlled time."""
        frozen_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        assert fake_time.current_time == frozen_at

    def test_elapsed_monotonic_property(self) -> None:
        """Verify elapsed_monotonic tracks total advances."""
        fake_time = FakeTimeAuthority()
        fake_time.advance(seconds=50)
        fake_time.advance(seconds=50)

        assert fake_time.elapsed_monotonic == 100.0

    def test_repr_is_informative(self) -> None:
        """Verify __repr__ contains useful debugging info."""
        frozen_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        repr_str = repr(fake_time)

        assert "FakeTimeAuthority" in repr_str
        assert "2026-01-15" in repr_str


class TestPytestFixtures:
    """AC6: Test pytest fixtures work correctly."""

    def test_fake_time_authority_fixture(self, fake_time_authority: FakeTimeAuthority) -> None:
        """Verify fake_time_authority fixture provides fresh instance."""
        assert isinstance(fake_time_authority, FakeTimeAuthority)
        assert fake_time_authority.now() == datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_frozen_time_authority_fixture(
        self, frozen_time_authority: FakeTimeAuthority
    ) -> None:
        """Verify frozen_time_authority fixture provides known time."""
        assert isinstance(frozen_time_authority, FakeTimeAuthority)
        assert frozen_time_authority.now() == datetime(
            2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc
        )

    def test_fixtures_are_independent(
        self,
        fake_time_authority: FakeTimeAuthority,
        frozen_time_authority: FakeTimeAuthority,
    ) -> None:
        """Verify fixtures are independent instances."""
        # Modify one
        fake_time_authority.advance(seconds=3600)

        # Other should be unaffected
        assert frozen_time_authority.now() == datetime(
            2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc
        )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_advance_zero_seconds(self) -> None:
        """Verify advancing by zero is allowed (no-op)."""
        frozen_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        fake_time.advance(seconds=0)

        assert fake_time.now() == frozen_at

    def test_advance_very_small_amount(self) -> None:
        """Verify advancing by microseconds works."""
        frozen_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        fake_time.advance(seconds=0.000001)  # 1 microsecond

        assert fake_time.now() > frozen_at

    def test_advance_very_large_amount(self) -> None:
        """Verify advancing by years works."""
        frozen_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        fake_time = FakeTimeAuthority(frozen_at=frozen_at)

        fake_time.advance(delta=timedelta(days=365 * 10))  # 10 years

        assert fake_time.now().year == 2036

    def test_monotonic_with_custom_start_and_advances(self) -> None:
        """Verify custom monotonic start combines with advances."""
        fake_time = FakeTimeAuthority(start_monotonic=1000.0)

        fake_time.advance(seconds=50)

        assert fake_time.monotonic() == 1050.0
