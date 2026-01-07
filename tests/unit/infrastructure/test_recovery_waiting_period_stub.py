"""Unit tests for RecoveryWaitingPeriodStub (Story 3.6, Task 7).

Tests that the stub:
- Implements the RecoveryWaitingPeriodPort interface
- Supports all test scenarios for 48-hour waiting period
- Provides helper methods for test setup
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.ports.recovery_waiting_period import RecoveryWaitingPeriodPort
from src.domain.errors.recovery import (
    RecoveryAlreadyInProgressError,
    RecoveryWaitingPeriodNotElapsedError,
    RecoveryWaitingPeriodNotStartedError,
)
from src.domain.models.ceremony_evidence import ApproverSignature, CeremonyEvidence
from src.infrastructure.stubs.recovery_waiting_period_stub import (
    RecoveryWaitingPeriodStub,
)


def create_ceremony_evidence():
    """Create valid ceremony evidence for testing."""
    return CeremonyEvidence(
        ceremony_id=uuid4(),
        ceremony_type="recovery_complete",
        approvers=(
            ApproverSignature(
                keeper_id="keeper-001",
                signature=b"valid_sig_1",
                signed_at=datetime.now(timezone.utc),
            ),
            ApproverSignature(
                keeper_id="keeper-002",
                signature=b"valid_sig_2",
                signed_at=datetime.now(timezone.utc),
            ),
        ),
        created_at=datetime.now(timezone.utc),
    )


class TestRecoveryWaitingPeriodStubImplementation:
    """Tests that stub implements the port interface."""

    def test_implements_port_interface(self) -> None:
        """Stub implements RecoveryWaitingPeriodPort."""
        stub = RecoveryWaitingPeriodStub()
        assert isinstance(stub, RecoveryWaitingPeriodPort)


class TestStartWaitingPeriod:
    """Tests for start_waiting_period method."""

    @pytest.mark.asyncio
    async def test_start_creates_waiting_period(self) -> None:
        """Starting a waiting period creates and stores it."""
        stub = RecoveryWaitingPeriodStub()
        crisis_id = uuid4()
        keepers = ("keeper-001", "keeper-002")

        period = await stub.start_waiting_period(
            crisis_event_id=crisis_id,
            initiated_by=keepers,
        )

        assert period.crisis_event_id == crisis_id
        assert period.initiated_by == keepers

    @pytest.mark.asyncio
    async def test_start_rejects_if_already_active(self) -> None:
        """Cannot start new period if one is active."""
        stub = RecoveryWaitingPeriodStub()
        await stub.start_waiting_period(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        with pytest.raises(RecoveryAlreadyInProgressError):
            await stub.start_waiting_period(
                crisis_event_id=uuid4(),
                initiated_by=("keeper-002",),
            )


class TestGetActiveWaitingPeriod:
    """Tests for get_active_waiting_period method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_active(self) -> None:
        """Returns None when no active period."""
        stub = RecoveryWaitingPeriodStub()
        period = await stub.get_active_waiting_period()
        assert period is None

    @pytest.mark.asyncio
    async def test_returns_active_period(self) -> None:
        """Returns active period when one exists."""
        stub = RecoveryWaitingPeriodStub()
        await stub.start_waiting_period(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        period = await stub.get_active_waiting_period()
        assert period is not None


class TestIsWaitingPeriodElapsed:
    """Tests for is_waiting_period_elapsed method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_no_active(self) -> None:
        """Returns False when no active period."""
        stub = RecoveryWaitingPeriodStub()
        elapsed = await stub.is_waiting_period_elapsed()
        assert elapsed is False

    @pytest.mark.asyncio
    async def test_returns_false_when_not_elapsed(self) -> None:
        """Returns False when period not elapsed."""
        stub = RecoveryWaitingPeriodStub()
        await stub.start_waiting_period(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        elapsed = await stub.is_waiting_period_elapsed()
        assert elapsed is False

    @pytest.mark.asyncio
    async def test_returns_true_when_elapsed(self) -> None:
        """Returns True when period has elapsed."""
        stub = RecoveryWaitingPeriodStub()
        stub.set_elapsed(True)
        await stub.start_waiting_period(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        elapsed = await stub.is_waiting_period_elapsed()
        assert elapsed is True


class TestGetRemainingTime:
    """Tests for get_remaining_time method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_active(self) -> None:
        """Returns None when no active period."""
        stub = RecoveryWaitingPeriodStub()
        remaining = await stub.get_remaining_time()
        assert remaining is None

    @pytest.mark.asyncio
    async def test_returns_remaining_time(self) -> None:
        """Returns remaining time when active period exists."""
        stub = RecoveryWaitingPeriodStub()
        await stub.start_waiting_period(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        remaining = await stub.get_remaining_time()
        assert remaining is not None
        # Should be close to 48 hours (minus a few ms of test execution)
        assert remaining > timedelta(hours=47)

    @pytest.mark.asyncio
    async def test_returns_zero_when_elapsed(self) -> None:
        """Returns zero when period has elapsed."""
        stub = RecoveryWaitingPeriodStub()
        stub.set_elapsed(True)
        await stub.start_waiting_period(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        remaining = await stub.get_remaining_time()
        assert remaining == timedelta(0)


class TestCompleteWaitingPeriod:
    """Tests for complete_waiting_period method."""

    @pytest.mark.asyncio
    async def test_complete_requires_active_period(self) -> None:
        """Cannot complete without active period."""
        stub = RecoveryWaitingPeriodStub()
        ceremony = create_ceremony_evidence()

        with pytest.raises(RecoveryWaitingPeriodNotStartedError):
            await stub.complete_waiting_period(ceremony_evidence=ceremony)

    @pytest.mark.asyncio
    async def test_complete_requires_elapsed(self) -> None:
        """Cannot complete before period elapsed."""
        stub = RecoveryWaitingPeriodStub()
        await stub.start_waiting_period(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )
        ceremony = create_ceremony_evidence()

        with pytest.raises(RecoveryWaitingPeriodNotElapsedError) as exc_info:
            await stub.complete_waiting_period(ceremony_evidence=ceremony)

        assert "FR21" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_succeeds_when_elapsed(self) -> None:
        """Complete succeeds when period has elapsed."""
        stub = RecoveryWaitingPeriodStub()
        stub.set_elapsed(True)
        await stub.start_waiting_period(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )
        ceremony = create_ceremony_evidence()

        payload = await stub.complete_waiting_period(ceremony_evidence=ceremony)

        assert payload.keeper_ceremony_id == ceremony.ceremony_id


class TestHelperMethods:
    """Tests for stub helper methods."""

    def test_set_elapsed_helper(self) -> None:
        """set_elapsed helper controls elapsed state."""
        stub = RecoveryWaitingPeriodStub()

        stub.set_elapsed(True)
        assert stub._force_elapsed is True

        stub.set_elapsed(False)
        assert stub._force_elapsed is False

    def test_reset_clears_state(self) -> None:
        """reset clears all state."""
        stub = RecoveryWaitingPeriodStub()
        stub.set_elapsed(True)

        stub.reset()

        assert stub._active_period is None
        assert stub._force_elapsed is False
