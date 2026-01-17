"""Tests for state transition validator.

Story: consent-gov-1.4: Write-Time Validation
AC1: Illegal state transitions rejected before append (with specific error)
AC6: State machine resolution completes in ≤10ms (NFR-PERF-05)
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.application.services.governance.validators.state_transition_validator import (
    InMemoryStateProjection,
    StateTransitionValidator,
    TaskState,
    LegitimacyBand,
)
from src.domain.governance.errors.validation_errors import IllegalStateTransitionError
from src.domain.governance.events.event_envelope import GovernanceEvent


@pytest.fixture
def state_projection() -> InMemoryStateProjection:
    """Create a test state projection."""
    return InMemoryStateProjection()


@pytest.fixture
def validator(state_projection: InMemoryStateProjection) -> StateTransitionValidator:
    """Create a validator with the test projection."""
    return StateTransitionValidator(state_projection)


@pytest.fixture
def bypass_validator(state_projection: InMemoryStateProjection) -> StateTransitionValidator:
    """Create a validator with validation bypassed."""
    return StateTransitionValidator(state_projection, skip_validation=True)


def make_task_event(event_type: str, task_id: str = "task-123") -> GovernanceEvent:
    """Create a test task event."""
    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        actor_id="test-actor",
        trace_id=str(uuid4()),
        payload={"task_id": task_id},
    )


def make_legitimacy_event(
    event_type: str, entity_id: str = "archon-42", new_band: str = "provisional"
) -> GovernanceEvent:
    """Create a test legitimacy event."""
    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        actor_id="test-actor",
        trace_id=str(uuid4()),
        payload={"entity_id": entity_id, "new_band": new_band},
    )


class TestStateTransitionValidatorTask:
    """Tests for task state machine validation."""

    @pytest.mark.asyncio
    async def test_new_task_must_start_pending(
        self, validator: StateTransitionValidator
    ) -> None:
        """New task must start in pending state."""
        event = make_task_event("consent.task.requested")
        await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_new_task_cannot_start_activated(
        self, validator: StateTransitionValidator
    ) -> None:
        """New task cannot skip to activated state."""
        event = make_task_event("executive.task.activated")

        with pytest.raises(IllegalStateTransitionError) as exc_info:
            await validator.validate(event)

        assert exc_info.value.current_state == "(new)"
        assert exc_info.value.attempted_state == TaskState.ACTIVATED.value
        assert TaskState.PENDING.value in exc_info.value.allowed_states

    @pytest.mark.asyncio
    async def test_pending_to_authorized_valid(
        self, validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """Pending task can transition to authorized."""
        state_projection.set_state("task", "task-123", TaskState.PENDING.value)
        event = make_task_event("consent.task.granted")
        await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_authorized_to_activated_valid(
        self, validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """Authorized task can transition to activated."""
        state_projection.set_state("task", "task-123", TaskState.AUTHORIZED.value)
        event = make_task_event("executive.task.activated")
        await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_authorized_to_completed_invalid(
        self, validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """Authorized task cannot skip to completed."""
        state_projection.set_state("task", "task-123", TaskState.AUTHORIZED.value)
        event = make_task_event("executive.task.completed")

        with pytest.raises(IllegalStateTransitionError) as exc_info:
            await validator.validate(event)

        assert exc_info.value.current_state == TaskState.AUTHORIZED.value
        assert exc_info.value.attempted_state == TaskState.COMPLETED.value
        assert TaskState.ACTIVATED.value in exc_info.value.allowed_states

    @pytest.mark.asyncio
    async def test_activated_to_accepted_valid(
        self, validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """Activated task can transition to accepted."""
        state_projection.set_state("task", "task-123", TaskState.ACTIVATED.value)
        event = make_task_event("executive.task.accepted")
        await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_accepted_to_completed_valid(
        self, validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """Accepted task can transition to completed."""
        state_projection.set_state("task", "task-123", TaskState.ACCEPTED.value)
        event = make_task_event("executive.task.completed")
        await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_completed_is_terminal(
        self, validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """Completed task cannot transition to any other state."""
        state_projection.set_state("task", "task-123", TaskState.COMPLETED.value)
        event = make_task_event("executive.task.activated")

        with pytest.raises(IllegalStateTransitionError) as exc_info:
            await validator.validate(event)

        assert exc_info.value.allowed_states == []

    @pytest.mark.asyncio
    async def test_error_includes_aggregate_info(
        self, validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """Error includes aggregate type and ID."""
        state_projection.set_state("task", "task-123", TaskState.COMPLETED.value)
        event = make_task_event("executive.task.activated")

        with pytest.raises(IllegalStateTransitionError) as exc_info:
            await validator.validate(event)

        assert exc_info.value.aggregate_type == "task"
        assert exc_info.value.aggregate_id == "task-123"


class TestStateTransitionValidatorLegitimacy:
    """Tests for legitimacy band state machine validation."""

    @pytest.mark.asyncio
    async def test_new_legitimacy_must_start_full(
        self, validator: StateTransitionValidator
    ) -> None:
        """New legitimacy assessment must start at full band."""
        event = make_legitimacy_event(
            "legitimacy.band.assessed", entity_id="archon-42", new_band=LegitimacyBand.FULL.value
        )
        await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_new_legitimacy_cannot_start_provisional(
        self, validator: StateTransitionValidator
    ) -> None:
        """New entity cannot start at provisional band."""
        event = make_legitimacy_event(
            "legitimacy.band.assessed", entity_id="archon-42", new_band=LegitimacyBand.PROVISIONAL.value
        )

        with pytest.raises(IllegalStateTransitionError) as exc_info:
            await validator.validate(event)

        assert exc_info.value.current_state == "(new)"
        assert exc_info.value.attempted_state == LegitimacyBand.PROVISIONAL.value

    @pytest.mark.asyncio
    async def test_full_to_provisional_valid(
        self, validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """Full legitimacy can decay to provisional."""
        state_projection.set_state("legitimacy", "archon-42", LegitimacyBand.FULL.value)
        event = make_legitimacy_event(
            "legitimacy.band.decayed", entity_id="archon-42", new_band=LegitimacyBand.PROVISIONAL.value
        )
        await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_provisional_to_full_valid(
        self, validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """Provisional legitimacy can be restored to full."""
        state_projection.set_state("legitimacy", "archon-42", LegitimacyBand.PROVISIONAL.value)
        event = make_legitimacy_event(
            "legitimacy.band.restored", entity_id="archon-42", new_band=LegitimacyBand.FULL.value
        )
        await validator.validate(event)  # Should not raise


class TestStateTransitionValidatorNonStateMachineEvents:
    """Tests for events that don't affect state machines."""

    @pytest.mark.asyncio
    async def test_non_state_event_passes(
        self, validator: StateTransitionValidator
    ) -> None:
        """Events not mapped to state machines pass validation."""
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="witness.observation.recorded",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={"observation": "test"},
        )
        await validator.validate(event)  # Should not raise


class TestStateTransitionValidatorBypass:
    """Tests for validation bypass."""

    @pytest.mark.asyncio
    async def test_skip_validation_allows_any_transition(
        self, bypass_validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """Skip validation mode allows any transition."""
        state_projection.set_state("task", "task-123", TaskState.COMPLETED.value)
        event = make_task_event("executive.task.activated")  # Invalid normally
        await bypass_validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_is_valid_transition_true_when_skipped(
        self, bypass_validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """is_valid_transition returns True when validation skipped."""
        state_projection.set_state("task", "task-123", TaskState.COMPLETED.value)
        event = make_task_event("executive.task.activated")
        assert await bypass_validator.is_valid_transition(event) is True


class TestInMemoryStateProjection:
    """Tests for InMemoryStateProjection."""

    @pytest.mark.asyncio
    async def test_get_current_state_none_for_unknown(
        self, state_projection: InMemoryStateProjection
    ) -> None:
        """get_current_state returns None for unknown aggregates."""
        state = await state_projection.get_current_state("task", "unknown")
        assert state is None

    @pytest.mark.asyncio
    async def test_set_and_get_state(
        self, state_projection: InMemoryStateProjection
    ) -> None:
        """set_state followed by get_current_state works."""
        state_projection.set_state("task", "task-1", "pending")
        state = await state_projection.get_current_state("task", "task-1")
        assert state is not None
        assert state.current_state == "pending"

    def test_clear(self, state_projection: InMemoryStateProjection) -> None:
        """clear removes all states."""
        state_projection.set_state("task", "task-1", "pending")
        state_projection.clear()
        assert len(state_projection._states) == 0


class TestStateTransitionValidatorPerformance:
    """Performance tests for StateTransitionValidator."""

    @pytest.mark.asyncio
    async def test_validation_performance(
        self, validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """State machine resolution completes in ≤10ms (AC6)."""
        import time

        state_projection.set_state("task", "task-123", TaskState.ACTIVATED.value)
        event = make_task_event("executive.task.accepted")

        # Single validation should be fast
        start = time.perf_counter()
        await validator.validate(event)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms <= 10, f"State machine resolution took {elapsed_ms}ms, limit is 10ms"

    @pytest.mark.asyncio
    async def test_bulk_validation_performance(
        self, validator: StateTransitionValidator, state_projection: InMemoryStateProjection
    ) -> None:
        """Multiple state machine resolutions are performant."""
        import time

        # Set up 100 tasks
        for i in range(100):
            state_projection.set_state("task", f"task-{i}", TaskState.ACTIVATED.value)

        events = [
            make_task_event("executive.task.accepted", f"task-{i}")
            for i in range(100)
        ]

        start = time.perf_counter()
        for event in events:
            await validator.validate(event)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 100 validations should complete in reasonable time
        # Each should be ≤10ms, so 100 should be ≤1000ms
        assert elapsed_ms < 1000, f"100 validations took {elapsed_ms}ms"
