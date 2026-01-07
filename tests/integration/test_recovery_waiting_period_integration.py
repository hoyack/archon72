"""Integration tests for 48-hour recovery waiting period (Story 3.6, FR21).

These tests verify the complete recovery flow:
- AC1: Timer starts when Keepers initiate recovery
- AC2: Recovery allowed only after 48 hours
- AC3: Early rejection includes remaining time
- AC4: Successful completion creates audit trail
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
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
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


class TestRecoveryWaitingPeriodIntegration:
    """Integration tests for complete recovery flow."""

    @pytest.fixture
    def halted_system(self):
        """Fixture for a system in halted state."""
        halt_checker = HaltCheckerStub(force_halted=True, halt_reason="Fork detected")
        return halt_checker

    @pytest.fixture
    def operational_system(self):
        """Fixture for a system in operational state."""
        return HaltCheckerStub()  # Not halted by default

    @pytest.fixture
    def recovery_port(self):
        """Fixture for recovery waiting period port."""
        return RecoveryWaitingPeriodStub()

    @pytest.fixture
    def coordinator(self, halted_system, recovery_port):
        """Fixture for RecoveryCoordinator with halted system."""
        return RecoveryCoordinator(
            halt_checker=halted_system,
            recovery_port=recovery_port,
        )


class TestAC1TimerStartsOnInitiation(TestRecoveryWaitingPeriodIntegration):
    """AC1: Timer starts when Keepers initiate recovery process."""

    @pytest.mark.asyncio
    async def test_initiation_starts_48_hour_timer(
        self, halted_system, recovery_port
    ) -> None:
        """Initiating recovery starts the 48-hour countdown."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)
        crisis_id = uuid4()
        keepers = ("keeper-001", "keeper-002")

        payload = await coordinator.initiate_recovery(
            crisis_event_id=crisis_id,
            initiated_by=keepers,
        )

        # Verify event payload
        assert isinstance(payload, RecoveryWaitingPeriodStartedPayload)
        assert payload.crisis_event_id == crisis_id
        assert payload.initiated_by_keepers == keepers
        assert payload.public_notification_sent is True

        # Verify timing (ends_at is 48 hours after started_at)
        duration = payload.ends_at - payload.started_at
        assert duration == timedelta(hours=48)

    @pytest.mark.asyncio
    async def test_initiation_requires_halted_state(
        self, operational_system, recovery_port
    ) -> None:
        """Cannot initiate recovery if system is not halted."""
        coordinator = RecoveryCoordinator(operational_system, recovery_port)

        with pytest.raises(RecoveryNotPermittedError) as exc_info:
            await coordinator.initiate_recovery(
                crisis_event_id=uuid4(),
                initiated_by=("keeper-001",),
            )

        assert "not halted" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_only_one_active_recovery_at_a_time(
        self, halted_system, recovery_port
    ) -> None:
        """Cannot start new recovery if one is already in progress."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)

        # Start first recovery
        await coordinator.initiate_recovery(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        # Try to start second - should fail
        with pytest.raises(RecoveryAlreadyInProgressError):
            await coordinator.initiate_recovery(
                crisis_event_id=uuid4(),
                initiated_by=("keeper-002",),
            )


class TestAC2RecoveryAfter48Hours(TestRecoveryWaitingPeriodIntegration):
    """AC2: Recovery can only proceed after 48 hours have elapsed."""

    @pytest.mark.asyncio
    async def test_recovery_allowed_after_48_hours(
        self, halted_system, recovery_port
    ) -> None:
        """Recovery succeeds when 48 hours have elapsed."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)

        # Start recovery
        await coordinator.initiate_recovery(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        # Force elapsed for testing
        recovery_port.set_elapsed(True)

        # Complete recovery
        ceremony = create_ceremony_evidence()
        payload = await coordinator.complete_recovery(ceremony_evidence=ceremony)

        assert isinstance(payload, RecoveryCompletedPayload)
        assert payload.keeper_ceremony_id == ceremony.ceremony_id

    @pytest.mark.asyncio
    async def test_48_hours_is_constitutional_floor(
        self, halted_system, recovery_port
    ) -> None:
        """Verify 48 hours is the minimum (NFR41 constitutional floor)."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)

        # Start recovery
        payload = await coordinator.initiate_recovery(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        # Verify the window is exactly 48 hours
        duration = payload.ends_at - payload.started_at
        assert duration.total_seconds() == 48 * 3600  # Exactly 48 hours in seconds


class TestAC3EarlyRejectionWithRemainingTime(TestRecoveryWaitingPeriodIntegration):
    """AC3: Early recovery attempts rejected with remaining time displayed."""

    @pytest.mark.asyncio
    async def test_early_recovery_rejected(
        self, halted_system, recovery_port
    ) -> None:
        """Recovery rejected before 48 hours elapsed."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)

        # Start recovery
        await coordinator.initiate_recovery(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        # Try to complete immediately (not elapsed)
        ceremony = create_ceremony_evidence()
        with pytest.raises(RecoveryWaitingPeriodNotElapsedError):
            await coordinator.complete_recovery(ceremony_evidence=ceremony)

    @pytest.mark.asyncio
    async def test_error_includes_remaining_time(
        self, halted_system, recovery_port
    ) -> None:
        """Rejection error message includes remaining time."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)

        # Start recovery
        await coordinator.initiate_recovery(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        # Try to complete immediately
        ceremony = create_ceremony_evidence()
        with pytest.raises(RecoveryWaitingPeriodNotElapsedError) as exc_info:
            await coordinator.complete_recovery(ceremony_evidence=ceremony)

        # Verify error message
        error_msg = str(exc_info.value)
        assert "FR21" in error_msg
        assert "Remaining" in error_msg

    @pytest.mark.asyncio
    async def test_status_shows_remaining_time(
        self, halted_system, recovery_port
    ) -> None:
        """Status endpoint shows remaining time during waiting period."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)

        # Start recovery
        await coordinator.initiate_recovery(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        # Check status
        status = await coordinator.get_recovery_status()

        assert status["active"] is True
        assert status["remaining_time"] is not None


class TestAC4AuditTrailCreation(TestRecoveryWaitingPeriodIntegration):
    """AC4: Successful recovery creates proper audit trail."""

    @pytest.mark.asyncio
    async def test_completion_returns_payload_for_event(
        self, halted_system, recovery_port
    ) -> None:
        """Completion returns payload suitable for RecoveryCompletedEvent."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)
        crisis_id = uuid4()

        # Start recovery
        await coordinator.initiate_recovery(
            crisis_event_id=crisis_id,
            initiated_by=("keeper-001",),
        )

        # Force elapsed and complete
        recovery_port.set_elapsed(True)
        ceremony = create_ceremony_evidence()
        payload = await coordinator.complete_recovery(ceremony_evidence=ceremony)

        # Verify payload has all fields for audit trail
        assert payload.crisis_event_id == crisis_id
        assert payload.waiting_period_started_at is not None
        assert payload.recovery_completed_at is not None
        assert payload.keeper_ceremony_id == ceremony.ceremony_id
        assert payload.approving_keepers == ceremony.get_keeper_ids()

    @pytest.mark.asyncio
    async def test_completion_includes_ceremony_reference(
        self, halted_system, recovery_port
    ) -> None:
        """Completion payload references the Keeper ceremony (FR22)."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)

        # Start recovery
        await coordinator.initiate_recovery(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        # Complete
        recovery_port.set_elapsed(True)
        ceremony = create_ceremony_evidence()
        payload = await coordinator.complete_recovery(ceremony_evidence=ceremony)

        # Verify ceremony linkage
        assert payload.keeper_ceremony_id == ceremony.ceremony_id
        assert len(payload.approving_keepers) >= 2  # FR22: 2+ Keepers


class TestEdgeCases(TestRecoveryWaitingPeriodIntegration):
    """Edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_complete_without_initiation_fails(
        self, halted_system, recovery_port
    ) -> None:
        """Cannot complete recovery that was never initiated."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)
        ceremony = create_ceremony_evidence()

        with pytest.raises(RecoveryWaitingPeriodNotStartedError):
            await coordinator.complete_recovery(ceremony_evidence=ceremony)

    @pytest.mark.asyncio
    async def test_status_when_no_active_recovery(
        self, halted_system, recovery_port
    ) -> None:
        """Status correctly indicates no active recovery."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)

        status = await coordinator.get_recovery_status()

        assert status["active"] is False
        assert status["remaining_time"] is None
        assert status["crisis_event_id"] is None

    @pytest.mark.asyncio
    async def test_can_complete_recovery_helper(
        self, halted_system, recovery_port
    ) -> None:
        """can_complete_recovery correctly indicates completion readiness."""
        coordinator = RecoveryCoordinator(halted_system, recovery_port)

        # No active recovery
        assert await coordinator.can_complete_recovery() is False

        # Start recovery
        await coordinator.initiate_recovery(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        # Not elapsed yet
        assert await coordinator.can_complete_recovery() is False

        # Force elapsed
        recovery_port.set_elapsed(True)
        assert await coordinator.can_complete_recovery() is True
