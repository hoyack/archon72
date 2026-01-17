"""Unit tests for CessationTriggerService.

Story: consent-gov-8.1: System Cessation Trigger
AC1: Human Operator can trigger cessation (FR47)
AC2: Cessation blocks new motions (FR49)
AC3: Cessation halts execution (FR50)
AC4: Cessation requires Human Operator authentication
AC5: Event `constitutional.cessation.triggered` emitted
AC6: Cessation trigger is irreversible (no "undo")
AC7: All in-flight operations complete or interrupted
AC8: Unit tests for cessation trigger
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.cessation_trigger_service import (
    CessationTriggerService,
    DEFAULT_GRACE_PERIOD_SECONDS,
)
from src.domain.governance.cessation import (
    CessationAlreadyTriggeredError,
    CessationState,
    CessationStatus,
    CessationTrigger,
)


# =============================================================================
# Fake Implementations for Testing
# =============================================================================


class FakeCessationPort:
    """Fake CessationPort for testing."""

    def __init__(self, initial_state: CessationState | None = None) -> None:
        self._state = initial_state or CessationState.active()
        self._trigger: CessationTrigger | None = None

    async def get_state(self) -> CessationState:
        return self._state

    async def record_trigger(self, trigger: CessationTrigger) -> None:
        if self._state.status != CessationStatus.ACTIVE:
            raise CessationAlreadyTriggeredError(
                original_trigger_id=self._trigger.trigger_id if self._trigger else uuid4(),
                original_triggered_at=self._trigger.triggered_at if self._trigger else datetime.now(timezone.utc),
            )
        self._trigger = trigger
        self._state = CessationState.triggered(trigger)

    async def mark_ceased(self) -> None:
        if self._trigger:
            self._state = CessationState.ceased(self._trigger)

    async def update_in_flight_count(self, count: int) -> None:
        if self._state.status == CessationStatus.CESSATION_TRIGGERED:
            self._state = self._state.with_in_flight_count(count)


class FakeMotionBlocker:
    """Fake MotionBlockerPort for testing."""

    def __init__(self) -> None:
        self._blocked = False
        self._reason: str | None = None
        self.block_calls: list[str] = []

    async def block_new_motions(self, reason: str) -> None:
        self._blocked = True
        self._reason = reason
        self.block_calls.append(reason)

    async def is_blocked(self) -> bool:
        return self._blocked

    async def get_block_reason(self) -> str | None:
        return self._reason


class FakeExecutionHalter:
    """Fake ExecutionHalterPort for testing."""

    def __init__(self, in_flight_count: int = 0) -> None:
        self._in_flight_count = in_flight_count
        self._halt_begun = False
        self._halt_complete = False
        self._force_stopped = 0
        self.halt_calls: list[dict[str, Any]] = []

    async def begin_halt(
        self,
        trigger_id: str,
        grace_period_seconds: int,
    ) -> None:
        self._halt_begun = True
        self.halt_calls.append({
            "trigger_id": trigger_id,
            "grace_period_seconds": grace_period_seconds,
        })

    async def get_in_flight_count(self) -> int:
        return self._in_flight_count

    async def is_halt_complete(self) -> bool:
        return self._halt_complete

    async def force_halt(self) -> int:
        stopped = self._in_flight_count
        self._in_flight_count = 0
        self._halt_complete = True
        self._force_stopped = stopped
        return stopped

    def simulate_operations_complete(self) -> None:
        """Simulate all operations completing."""
        self._in_flight_count = 0
        self._halt_complete = True


class FakeTwoPhaseEventEmitter:
    """Fake TwoPhaseEventEmitterPort for testing."""

    def __init__(self) -> None:
        self.intents: list[dict[str, Any]] = []
        self.commits: list[dict[str, Any]] = []
        self.failures: list[dict[str, Any]] = []
        self._correlation_counter = 0

    async def emit_intent(
        self,
        operation_type: str,
        actor_id: str,
        target_entity_id: str,
        intent_payload: dict[str, Any],
    ) -> UUID:
        self._correlation_counter += 1
        correlation_id = uuid4()
        self.intents.append({
            "correlation_id": correlation_id,
            "operation_type": operation_type,
            "actor_id": actor_id,
            "target_entity_id": target_entity_id,
            "intent_payload": intent_payload,
        })
        return correlation_id

    async def emit_commit(
        self,
        correlation_id: UUID,
        outcome_payload: dict[str, Any],
    ) -> None:
        self.commits.append({
            "correlation_id": correlation_id,
            "outcome_payload": outcome_payload,
        })

    async def emit_failure(
        self,
        correlation_id: UUID,
        failure_reason: str,
        failure_details: dict[str, Any],
    ) -> None:
        self.failures.append({
            "correlation_id": correlation_id,
            "failure_reason": failure_reason,
            "failure_details": failure_details,
        })


class FakeTimeAuthority:
    """Fake TimeAuthorityProtocol for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._time = fixed_time or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._time

    def utcnow(self) -> datetime:
        return self._time

    def monotonic(self) -> float:
        return 0.0

    def advance(self, seconds: float) -> None:
        """Advance time for testing."""
        from datetime import timedelta
        self._time = self._time + timedelta(seconds=seconds)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def cessation_port() -> FakeCessationPort:
    return FakeCessationPort()


@pytest.fixture
def motion_blocker() -> FakeMotionBlocker:
    return FakeMotionBlocker()


@pytest.fixture
def execution_halter() -> FakeExecutionHalter:
    return FakeExecutionHalter()


@pytest.fixture
def event_emitter() -> FakeTwoPhaseEventEmitter:
    return FakeTwoPhaseEventEmitter()


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    return FakeTimeAuthority()


@pytest.fixture
def cessation_service(
    cessation_port: FakeCessationPort,
    motion_blocker: FakeMotionBlocker,
    execution_halter: FakeExecutionHalter,
    event_emitter: FakeTwoPhaseEventEmitter,
    time_authority: FakeTimeAuthority,
) -> CessationTriggerService:
    return CessationTriggerService(
        cessation_port=cessation_port,
        motion_blocker=motion_blocker,
        execution_halter=execution_halter,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


# =============================================================================
# Tests for AC1: Human Operator can trigger cessation (FR47)
# =============================================================================


class TestOperatorCanTriggerCessation:
    """Tests for AC1: Human Operator can trigger cessation."""

    @pytest.mark.asyncio
    async def test_operator_can_trigger_cessation(
        self,
        cessation_service: CessationTriggerService,
    ) -> None:
        """Human Operator can trigger cessation (AC1, FR47)."""
        operator_id = uuid4()

        trigger = await cessation_service.trigger_cessation(
            operator_id=operator_id,
            reason="Planned shutdown",
        )

        assert trigger.operator_id == operator_id
        assert trigger.reason == "Planned shutdown"

    @pytest.mark.asyncio
    async def test_trigger_has_operator_id(
        self,
        cessation_service: CessationTriggerService,
    ) -> None:
        """Trigger record includes operator ID (AC4)."""
        operator_id = uuid4()

        trigger = await cessation_service.trigger_cessation(
            operator_id=operator_id,
            reason="Test",
        )

        assert trigger.operator_id == operator_id

    @pytest.mark.asyncio
    async def test_trigger_has_timestamp(
        self,
        cessation_service: CessationTriggerService,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Trigger record includes timestamp."""
        expected_time = time_authority.utcnow()

        trigger = await cessation_service.trigger_cessation(
            operator_id=uuid4(),
            reason="Test",
        )

        assert trigger.triggered_at == expected_time


# =============================================================================
# Tests for AC2: Cessation blocks new motions (FR49)
# =============================================================================


class TestCessationBlocksNewMotions:
    """Tests for AC2: Cessation blocks new motions."""

    @pytest.mark.asyncio
    async def test_cessation_blocks_new_motions(
        self,
        cessation_service: CessationTriggerService,
        motion_blocker: FakeMotionBlocker,
    ) -> None:
        """New motions are blocked after cessation triggered (AC2, FR49)."""
        await cessation_service.trigger_cessation(
            operator_id=uuid4(),
            reason="Test",
        )

        assert await motion_blocker.is_blocked()

    @pytest.mark.asyncio
    async def test_block_reason_is_cessation(
        self,
        cessation_service: CessationTriggerService,
        motion_blocker: FakeMotionBlocker,
    ) -> None:
        """Block reason indicates cessation."""
        await cessation_service.trigger_cessation(
            operator_id=uuid4(),
            reason="Test",
        )

        reason = await motion_blocker.get_block_reason()
        assert reason == "cessation_triggered"


# =============================================================================
# Tests for AC3: Cessation halts execution (FR50)
# =============================================================================


class TestCessationHaltsExecution:
    """Tests for AC3: Cessation halts execution."""

    @pytest.mark.asyncio
    async def test_cessation_begins_halt(
        self,
        cessation_service: CessationTriggerService,
        execution_halter: FakeExecutionHalter,
    ) -> None:
        """Execution halt is begun after cessation triggered (AC3, FR50)."""
        trigger = await cessation_service.trigger_cessation(
            operator_id=uuid4(),
            reason="Test",
        )

        assert len(execution_halter.halt_calls) == 1
        assert execution_halter.halt_calls[0]["trigger_id"] == str(trigger.trigger_id)

    @pytest.mark.asyncio
    async def test_halt_uses_grace_period(
        self,
        cessation_service: CessationTriggerService,
        execution_halter: FakeExecutionHalter,
    ) -> None:
        """Halt uses configured grace period."""
        await cessation_service.trigger_cessation(
            operator_id=uuid4(),
            reason="Test",
        )

        assert (
            execution_halter.halt_calls[0]["grace_period_seconds"]
            == DEFAULT_GRACE_PERIOD_SECONDS
        )


# =============================================================================
# Tests for AC5: Event `constitutional.cessation.triggered` emitted
# =============================================================================


class TestCessationEventEmitted:
    """Tests for AC5: Event emitted."""

    @pytest.mark.asyncio
    async def test_triggered_event_emitted(
        self,
        cessation_service: CessationTriggerService,
        event_emitter: FakeTwoPhaseEventEmitter,
    ) -> None:
        """Triggered event is emitted (AC5)."""
        await cessation_service.trigger_cessation(
            operator_id=uuid4(),
            reason="Test",
        )

        assert len(event_emitter.intents) == 1
        assert (
            event_emitter.intents[0]["operation_type"]
            == "constitutional.cessation.triggered"
        )

    @pytest.mark.asyncio
    async def test_event_includes_reason(
        self,
        cessation_service: CessationTriggerService,
        event_emitter: FakeTwoPhaseEventEmitter,
    ) -> None:
        """Event includes cessation reason."""
        await cessation_service.trigger_cessation(
            operator_id=uuid4(),
            reason="Planned retirement",
        )

        assert event_emitter.intents[0]["intent_payload"]["reason"] == "Planned retirement"

    @pytest.mark.asyncio
    async def test_commit_event_on_success(
        self,
        cessation_service: CessationTriggerService,
        event_emitter: FakeTwoPhaseEventEmitter,
    ) -> None:
        """Commit event emitted on successful trigger."""
        await cessation_service.trigger_cessation(
            operator_id=uuid4(),
            reason="Test",
        )

        assert len(event_emitter.commits) == 1
        assert event_emitter.commits[0]["outcome_payload"]["motions_blocked"] is True


# =============================================================================
# Tests for AC6: Cessation trigger is irreversible (no "undo")
# =============================================================================


class TestCessationIrreversibility:
    """Tests for AC6: Cessation is irreversible."""

    @pytest.mark.asyncio
    async def test_cannot_trigger_cessation_twice(
        self,
        cessation_service: CessationTriggerService,
    ) -> None:
        """Cessation cannot be triggered twice (AC6)."""
        await cessation_service.trigger_cessation(
            operator_id=uuid4(),
            reason="First",
        )

        with pytest.raises(CessationAlreadyTriggeredError):
            await cessation_service.trigger_cessation(
                operator_id=uuid4(),
                reason="Second",
            )

    def test_no_cancel_method(
        self,
        cessation_service: CessationTriggerService,
    ) -> None:
        """No cancel method exists (AC6)."""
        assert not hasattr(cessation_service, "cancel_cessation")
        assert not hasattr(cessation_service, "abort_cessation")

    def test_no_undo_method(
        self,
        cessation_service: CessationTriggerService,
    ) -> None:
        """No undo method exists (AC6)."""
        assert not hasattr(cessation_service, "undo_cessation")
        assert not hasattr(cessation_service, "revert_cessation")

    def test_no_rollback_method(
        self,
        cessation_service: CessationTriggerService,
    ) -> None:
        """No rollback method exists (AC6)."""
        assert not hasattr(cessation_service, "rollback_cessation")
        assert not hasattr(cessation_service, "resume_operations")


# =============================================================================
# Tests for AC7: All in-flight operations complete or interrupted
# =============================================================================


class TestInFlightOperations:
    """Tests for AC7: In-flight operation handling."""

    @pytest.mark.asyncio
    async def test_in_flight_count_tracked(
        self,
        cessation_port: FakeCessationPort,
        motion_blocker: FakeMotionBlocker,
        event_emitter: FakeTwoPhaseEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """In-flight operation count is tracked (AC7)."""
        execution_halter = FakeExecutionHalter(in_flight_count=5)
        service = CessationTriggerService(
            cessation_port=cessation_port,
            motion_blocker=motion_blocker,
            execution_halter=execution_halter,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        await service.trigger_cessation(
            operator_id=uuid4(),
            reason="Test",
        )

        state = await service.get_state()
        assert state.in_flight_count == 5

    @pytest.mark.asyncio
    async def test_check_and_finalize_when_complete(
        self,
        cessation_port: FakeCessationPort,
        motion_blocker: FakeMotionBlocker,
        event_emitter: FakeTwoPhaseEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """check_and_finalize marks CEASED when operations complete."""
        execution_halter = FakeExecutionHalter(in_flight_count=3)
        service = CessationTriggerService(
            cessation_port=cessation_port,
            motion_blocker=motion_blocker,
            execution_halter=execution_halter,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        await service.trigger_cessation(
            operator_id=uuid4(),
            reason="Test",
        )

        # Simulate operations completing
        execution_halter.simulate_operations_complete()

        result = await service.check_and_finalize()

        assert result is True
        state = await service.get_state()
        assert state.status == CessationStatus.CEASED

    @pytest.mark.asyncio
    async def test_force_finalize_stops_remaining(
        self,
        cessation_port: FakeCessationPort,
        motion_blocker: FakeMotionBlocker,
        event_emitter: FakeTwoPhaseEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """force_finalize stops remaining operations (AC7)."""
        execution_halter = FakeExecutionHalter(in_flight_count=3)
        service = CessationTriggerService(
            cessation_port=cessation_port,
            motion_blocker=motion_blocker,
            execution_halter=execution_halter,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        await service.trigger_cessation(
            operator_id=uuid4(),
            reason="Test",
        )

        stopped = await service.force_finalize()

        assert stopped == 3
        state = await service.get_state()
        assert state.status == CessationStatus.CEASED


# =============================================================================
# Tests for Input Validation
# =============================================================================


class TestInputValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_empty_reason_rejected(
        self,
        cessation_service: CessationTriggerService,
    ) -> None:
        """Empty reason is rejected."""
        with pytest.raises(ValueError, match="reason is required"):
            await cessation_service.trigger_cessation(
                operator_id=uuid4(),
                reason="",
            )

    @pytest.mark.asyncio
    async def test_whitespace_reason_rejected(
        self,
        cessation_service: CessationTriggerService,
    ) -> None:
        """Whitespace-only reason is rejected."""
        with pytest.raises(ValueError, match="reason is required"):
            await cessation_service.trigger_cessation(
                operator_id=uuid4(),
                reason="   ",
            )


# =============================================================================
# Tests for State Retrieval
# =============================================================================


class TestStateRetrieval:
    """Tests for get_state method."""

    @pytest.mark.asyncio
    async def test_get_state_before_trigger(
        self,
        cessation_service: CessationTriggerService,
    ) -> None:
        """Can get state before trigger."""
        state = await cessation_service.get_state()

        assert state.status == CessationStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_state_after_trigger(
        self,
        cessation_service: CessationTriggerService,
    ) -> None:
        """Can get state after trigger."""
        await cessation_service.trigger_cessation(
            operator_id=uuid4(),
            reason="Test",
        )

        state = await cessation_service.get_state()

        assert state.status == CessationStatus.CESSATION_TRIGGERED
        assert state.trigger is not None
