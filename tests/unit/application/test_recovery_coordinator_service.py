"""Unit tests for RecoveryCoordinator application service (Story 3.6, FR21).

Tests that the service:
- Coordinates 48-hour waiting period initiation (AC1)
- Rejects early recovery with remaining time (AC3)
- Allows recovery after 48 hours (AC2)
- Creates proper events for audit trail (AC4)
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.services.recovery_coordinator import RecoveryCoordinator
from src.domain.errors.recovery import (
    RecoveryAlreadyInProgressError,
    RecoveryNotPermittedError,
    RecoveryWaitingPeriodNotElapsedError,
    RecoveryWaitingPeriodNotStartedError,
)
from src.domain.events.recovery_completed import RecoveryCompletedPayload
from src.domain.events.recovery_waiting_period_started import (
    RecoveryWaitingPeriodStartedPayload,
)
from src.domain.models.ceremony_evidence import ApproverSignature, CeremonyEvidence
from src.domain.models.recovery_waiting_period import RecoveryWaitingPeriod


# Test fixtures
def create_mock_halt_checker(is_halted: bool = True):
    """Create a mock halt checker."""

    class MockHaltChecker:
        async def is_halted(self) -> bool:
            return is_halted

    return MockHaltChecker()


def create_mock_recovery_port(
    active_period: RecoveryWaitingPeriod = None, elapsed: bool = False
):
    """Create a mock recovery waiting period port."""
    from datetime import timedelta

    from src.domain.events.recovery_completed import RecoveryCompletedPayload
    from src.domain.models.ceremony_evidence import CeremonyEvidence
    from src.domain.models.recovery_waiting_period import RecoveryWaitingPeriod

    class MockRecoveryWaitingPeriodPort:
        def __init__(self):
            self._active = active_period
            self._elapsed = elapsed

        async def start_waiting_period(
            self, crisis_event_id, initiated_by
        ) -> RecoveryWaitingPeriod:
            if self._active:
                raise RecoveryAlreadyInProgressError("Recovery already in progress")
            self._active = RecoveryWaitingPeriod.start(
                crisis_event_id=crisis_event_id,
                initiated_by=initiated_by,
            )
            return self._active

        async def get_active_waiting_period(self) -> RecoveryWaitingPeriod | None:
            return self._active

        async def is_waiting_period_elapsed(self) -> bool:
            return self._elapsed and self._active is not None

        async def get_remaining_time(self) -> timedelta | None:
            if not self._active:
                return None
            if self._elapsed:
                return timedelta(0)
            return self._active.remaining_time()

        async def complete_waiting_period(
            self, ceremony_evidence: CeremonyEvidence
        ) -> RecoveryCompletedPayload:
            if not self._active:
                raise RecoveryWaitingPeriodNotStartedError("No active period")
            if not self._elapsed:
                remaining = await self.get_remaining_time()
                raise RecoveryWaitingPeriodNotElapsedError(
                    f"FR21: 48-hour waiting period not elapsed. Remaining: {remaining}"
                )
            return RecoveryCompletedPayload(
                crisis_event_id=self._active.crisis_event_id,
                waiting_period_started_at=self._active.started_at,
                recovery_completed_at=datetime.now(timezone.utc),
                keeper_ceremony_id=ceremony_evidence.ceremony_id,
                approving_keepers=ceremony_evidence.get_keeper_ids(),
            )

    return MockRecoveryWaitingPeriodPort()


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


class TestInitiateRecovery:
    """Tests for initiate_recovery method (AC1)."""

    @pytest.mark.asyncio
    async def test_initiate_recovery_starts_waiting_period(self) -> None:
        """Initiating recovery starts the 48-hour waiting period."""
        halt_checker = create_mock_halt_checker(is_halted=True)
        recovery_port = create_mock_recovery_port()
        coordinator = RecoveryCoordinator(
            halt_checker=halt_checker,
            recovery_port=recovery_port,
        )

        crisis_id = uuid4()
        keepers = ("keeper-001", "keeper-002")

        payload = await coordinator.initiate_recovery(
            crisis_event_id=crisis_id,
            initiated_by=keepers,
        )

        assert isinstance(payload, RecoveryWaitingPeriodStartedPayload)
        assert payload.crisis_event_id == crisis_id
        assert payload.initiated_by_keepers == keepers

    @pytest.mark.asyncio
    async def test_initiate_recovery_requires_halted_state(self) -> None:
        """Cannot initiate recovery if system is not halted."""
        halt_checker = create_mock_halt_checker(is_halted=False)
        recovery_port = create_mock_recovery_port()
        coordinator = RecoveryCoordinator(
            halt_checker=halt_checker,
            recovery_port=recovery_port,
        )

        with pytest.raises(RecoveryNotPermittedError):
            await coordinator.initiate_recovery(
                crisis_event_id=uuid4(),
                initiated_by=("keeper-001",),
            )

    @pytest.mark.asyncio
    async def test_initiate_recovery_rejects_if_already_in_progress(self) -> None:
        """Cannot start new recovery if one is already in progress."""
        existing = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )
        halt_checker = create_mock_halt_checker(is_halted=True)
        recovery_port = create_mock_recovery_port(active_period=existing)
        coordinator = RecoveryCoordinator(
            halt_checker=halt_checker,
            recovery_port=recovery_port,
        )

        with pytest.raises(RecoveryAlreadyInProgressError):
            await coordinator.initiate_recovery(
                crisis_event_id=uuid4(),
                initiated_by=("keeper-002",),
            )


class TestCompleteRecovery:
    """Tests for complete_recovery method (AC2, AC3)."""

    @pytest.mark.asyncio
    async def test_complete_recovery_requires_halted_state(self) -> None:
        """Cannot complete recovery if system is not halted (M1 safety check)."""
        start = datetime.now(timezone.utc) - timedelta(hours=48)
        existing = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=start,
        )
        halt_checker = create_mock_halt_checker(is_halted=False)  # Not halted
        recovery_port = create_mock_recovery_port(active_period=existing, elapsed=True)
        coordinator = RecoveryCoordinator(
            halt_checker=halt_checker,
            recovery_port=recovery_port,
        )

        ceremony = create_ceremony_evidence()
        with pytest.raises(RecoveryNotPermittedError) as exc_info:
            await coordinator.complete_recovery(ceremony_evidence=ceremony)

        assert "system not halted" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_recovery_after_48_hours(self) -> None:
        """Recovery can be completed after 48 hours elapsed."""
        start = datetime.now(timezone.utc) - timedelta(hours=48)
        existing = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=start,
        )
        halt_checker = create_mock_halt_checker(is_halted=True)
        recovery_port = create_mock_recovery_port(active_period=existing, elapsed=True)
        coordinator = RecoveryCoordinator(
            halt_checker=halt_checker,
            recovery_port=recovery_port,
        )

        ceremony = create_ceremony_evidence()
        payload = await coordinator.complete_recovery(ceremony_evidence=ceremony)

        assert isinstance(payload, RecoveryCompletedPayload)
        assert payload.keeper_ceremony_id == ceremony.ceremony_id

    @pytest.mark.asyncio
    async def test_complete_recovery_rejects_before_48_hours(self) -> None:
        """Recovery cannot be completed before 48 hours elapsed (AC3)."""
        existing = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )
        halt_checker = create_mock_halt_checker(is_halted=True)
        recovery_port = create_mock_recovery_port(active_period=existing, elapsed=False)
        coordinator = RecoveryCoordinator(
            halt_checker=halt_checker,
            recovery_port=recovery_port,
        )

        ceremony = create_ceremony_evidence()
        with pytest.raises(RecoveryWaitingPeriodNotElapsedError) as exc_info:
            await coordinator.complete_recovery(ceremony_evidence=ceremony)

        assert "FR21" in str(exc_info.value)
        assert "Remaining" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_recovery_requires_active_period(self) -> None:
        """Cannot complete recovery without active waiting period."""
        halt_checker = create_mock_halt_checker(is_halted=True)
        recovery_port = create_mock_recovery_port()  # No active period
        coordinator = RecoveryCoordinator(
            halt_checker=halt_checker,
            recovery_port=recovery_port,
        )

        ceremony = create_ceremony_evidence()
        with pytest.raises(RecoveryWaitingPeriodNotStartedError):
            await coordinator.complete_recovery(ceremony_evidence=ceremony)


class TestGetRecoveryStatus:
    """Tests for get_recovery_status method."""

    @pytest.mark.asyncio
    async def test_get_status_when_no_active_period(self) -> None:
        """Status indicates no active period."""
        halt_checker = create_mock_halt_checker(is_halted=True)
        recovery_port = create_mock_recovery_port()
        coordinator = RecoveryCoordinator(
            halt_checker=halt_checker,
            recovery_port=recovery_port,
        )

        status = await coordinator.get_recovery_status()

        assert status["active"] is False
        assert status["remaining_time"] is None

    @pytest.mark.asyncio
    async def test_get_status_with_active_period(self) -> None:
        """Status includes period details and remaining time."""
        existing = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )
        halt_checker = create_mock_halt_checker(is_halted=True)
        recovery_port = create_mock_recovery_port(active_period=existing)
        coordinator = RecoveryCoordinator(
            halt_checker=halt_checker,
            recovery_port=recovery_port,
        )

        status = await coordinator.get_recovery_status()

        assert status["active"] is True
        assert status["remaining_time"] is not None
        assert status["crisis_event_id"] == str(existing.crisis_event_id)
