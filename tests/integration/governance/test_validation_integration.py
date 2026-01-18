"""Integration tests for write-time validation.

Story: consent-gov-1.4: Write-Time Validation
AC10: Verify ledger unchanged after any rejection

This integration test verifies that when an event is rejected by
write-time validation, the ledger state remains completely unchanged.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.ledger_port import (
    LedgerReadOptions,
    PersistedGovernanceEvent,
)
from src.application.services.governance.ledger_validation_service import (
    LedgerValidationService,
)
from src.application.services.governance.validators.actor_validator import (
    ActorValidator,
    InMemoryActorRegistry,
)
from src.application.services.governance.validators.event_type_validator import (
    EventTypeValidator,
)
from src.application.services.governance.validators.hash_chain_validator import (
    HashChainValidator,
)
from src.application.services.governance.validators.state_transition_validator import (
    InMemoryStateProjection,
    StateTransitionValidator,
    TaskState,
)
from src.domain.governance.errors.validation_errors import (
    IllegalStateTransitionError,
    UnknownActorError,
    UnknownEventTypeError,
)
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.infrastructure.adapters.governance.validated_ledger_adapter import (
    ValidatedGovernanceLedgerAdapter,
)


class MockGovernanceLedgerPort:
    """Mock ledger port that tracks all operations.

    Tracks appended events and provides inspection methods
    for verifying ledger state.
    """

    def __init__(self) -> None:
        """Initialize empty mock ledger."""
        self._events: list[PersistedGovernanceEvent] = []
        self._append_calls: list[GovernanceEvent] = []
        self._latest_sequence: int = 0

    @property
    def event_count(self) -> int:
        """Get number of events in ledger."""
        return len(self._events)

    @property
    def append_call_count(self) -> int:
        """Get number of times append was called."""
        return len(self._append_calls)

    def get_events(self) -> list[PersistedGovernanceEvent]:
        """Get all events in ledger."""
        return list(self._events)

    async def append_event(self, event: GovernanceEvent) -> PersistedGovernanceEvent:
        """Append an event to the ledger."""
        self._append_calls.append(event)
        self._latest_sequence += 1
        persisted = PersistedGovernanceEvent(
            event=event, sequence=self._latest_sequence
        )
        self._events.append(persisted)
        return persisted

    async def get_latest_event(self) -> PersistedGovernanceEvent | None:
        """Get the latest event from the ledger."""
        if not self._events:
            return None
        return self._events[-1]

    async def get_max_sequence(self) -> int:
        """Get max sequence number."""
        return self._latest_sequence

    async def get_event_by_sequence(
        self, sequence: int
    ) -> PersistedGovernanceEvent | None:
        """Get event by sequence number."""
        for e in self._events:
            if e.sequence == sequence:
                return e
        return None

    async def get_event_by_id(self, event_id: UUID) -> PersistedGovernanceEvent | None:
        """Get event by ID."""
        for e in self._events:
            if e.event_id == event_id:
                return e
        return None

    async def read_events(
        self, options: LedgerReadOptions | None = None
    ) -> list[PersistedGovernanceEvent]:
        """Read events with optional filters."""
        return self._events

    async def count_events(self, options: LedgerReadOptions | None = None) -> int:
        """Count events in ledger."""
        return len(self._events)


def make_valid_event(
    event_type: str = "consent.task.requested",
    actor_id: str = "registered-actor",
    task_id: str = "task-123",
) -> GovernanceEvent:
    """Create a valid governance event for testing."""
    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        actor_id=actor_id,
        trace_id=str(uuid4()),
        payload={"task_id": task_id},
    )


def make_invalid_event_type_event() -> GovernanceEvent:
    """Create an event with a syntactically valid but unregistered event type."""
    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type="unknown.event.type",
        timestamp=datetime.now(timezone.utc),
        actor_id="registered-actor",
        trace_id=str(uuid4()),
        payload={"task_id": "task-123"},
    )


def make_invalid_actor_event() -> GovernanceEvent:
    """Create an event with an unregistered actor."""
    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type="consent.task.requested",
        timestamp=datetime.now(timezone.utc),
        actor_id="unknown-actor-not-registered",
        trace_id=str(uuid4()),
        payload={"task_id": "task-123"},
    )


def make_invalid_state_transition_event(
    state_projection: InMemoryStateProjection,
) -> GovernanceEvent:
    """Create an event that would cause an invalid state transition.

    Sets up a task in COMPLETED state, then tries to activate it.
    """
    state_projection.set_state("task", "task-123", TaskState.COMPLETED.value)
    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type="executive.task.activated",
        timestamp=datetime.now(timezone.utc),
        actor_id="registered-actor",
        trace_id=str(uuid4()),
        payload={"task_id": "task-123"},
    )


@pytest.fixture
def mock_ledger() -> MockGovernanceLedgerPort:
    """Create a mock ledger port."""
    return MockGovernanceLedgerPort()


@pytest.fixture
def actor_registry() -> InMemoryActorRegistry:
    """Create an actor registry with a registered actor."""
    registry = InMemoryActorRegistry(frozenset({"registered-actor"}))
    return registry


@pytest.fixture
def state_projection() -> InMemoryStateProjection:
    """Create an empty state projection."""
    return InMemoryStateProjection()


@pytest.fixture
def validation_service(
    mock_ledger: MockGovernanceLedgerPort,
    actor_registry: InMemoryActorRegistry,
    state_projection: InMemoryStateProjection,
) -> LedgerValidationService:
    """Create a validation service with all validators."""
    return LedgerValidationService(
        event_type_validator=EventTypeValidator(),
        actor_validator=ActorValidator(actor_registry),
        hash_chain_validator=HashChainValidator(mock_ledger, skip_validation=True),  # type: ignore
        state_transition_validator=StateTransitionValidator(state_projection),
    )


@pytest.fixture
def validated_adapter(
    mock_ledger: MockGovernanceLedgerPort,
    validation_service: LedgerValidationService,
) -> ValidatedGovernanceLedgerAdapter:
    """Create a validated ledger adapter."""
    return ValidatedGovernanceLedgerAdapter(
        base_adapter=mock_ledger,  # type: ignore
        validation_service=validation_service,
    )


class TestLedgerUnchangedAfterRejection:
    """AC10: Verify ledger unchanged after any rejection."""

    @pytest.mark.asyncio
    async def test_ledger_unchanged_after_invalid_event_type(
        self,
        validated_adapter: ValidatedGovernanceLedgerAdapter,
        mock_ledger: MockGovernanceLedgerPort,
    ) -> None:
        """Ledger is unchanged when event type validation fails."""
        initial_count = mock_ledger.event_count
        initial_append_calls = mock_ledger.append_call_count

        invalid_event = make_invalid_event_type_event()

        with pytest.raises(UnknownEventTypeError):
            await validated_adapter.append_event(invalid_event)

        # Verify ledger state is completely unchanged
        assert mock_ledger.event_count == initial_count
        assert mock_ledger.append_call_count == initial_append_calls

    @pytest.mark.asyncio
    async def test_ledger_unchanged_after_invalid_actor(
        self,
        validated_adapter: ValidatedGovernanceLedgerAdapter,
        mock_ledger: MockGovernanceLedgerPort,
    ) -> None:
        """Ledger is unchanged when actor validation fails."""
        initial_count = mock_ledger.event_count
        initial_append_calls = mock_ledger.append_call_count

        invalid_event = make_invalid_actor_event()

        with pytest.raises(UnknownActorError):
            await validated_adapter.append_event(invalid_event)

        # Verify ledger state is completely unchanged
        assert mock_ledger.event_count == initial_count
        assert mock_ledger.append_call_count == initial_append_calls

    @pytest.mark.asyncio
    async def test_ledger_unchanged_after_invalid_state_transition(
        self,
        validated_adapter: ValidatedGovernanceLedgerAdapter,
        mock_ledger: MockGovernanceLedgerPort,
        state_projection: InMemoryStateProjection,
    ) -> None:
        """Ledger is unchanged when state transition validation fails."""
        initial_count = mock_ledger.event_count
        initial_append_calls = mock_ledger.append_call_count

        invalid_event = make_invalid_state_transition_event(state_projection)

        with pytest.raises(IllegalStateTransitionError):
            await validated_adapter.append_event(invalid_event)

        # Verify ledger state is completely unchanged
        assert mock_ledger.event_count == initial_count
        assert mock_ledger.append_call_count == initial_append_calls

    @pytest.mark.asyncio
    async def test_valid_event_still_appends(
        self,
        validated_adapter: ValidatedGovernanceLedgerAdapter,
        mock_ledger: MockGovernanceLedgerPort,
    ) -> None:
        """Valid events are still appended successfully."""
        initial_count = mock_ledger.event_count

        valid_event = make_valid_event()
        persisted = await validated_adapter.append_event(valid_event)

        # Verify event was appended
        assert mock_ledger.event_count == initial_count + 1
        assert persisted.sequence == initial_count + 1
        assert mock_ledger.get_events()[-1].event == valid_event


class TestValidationBeforeTransaction:
    """AC7: Validation happens before transaction, not inside."""

    @pytest.mark.asyncio
    async def test_validation_runs_before_any_db_call(
        self,
        validation_service: LedgerValidationService,
        mock_ledger: MockGovernanceLedgerPort,
    ) -> None:
        """Validation runs entirely before append is called."""
        # Track call order
        call_order: list[str] = []

        original_append = mock_ledger.append_event

        async def tracked_append(event: GovernanceEvent) -> PersistedGovernanceEvent:
            call_order.append("append")
            return await original_append(event)

        mock_ledger.append_event = tracked_append  # type: ignore

        # Create adapter with tracked validation
        original_validate = validation_service.validate

        async def tracked_validate(event: GovernanceEvent) -> None:
            call_order.append("validate")
            await original_validate(event)

        validation_service.validate = tracked_validate  # type: ignore

        adapter = ValidatedGovernanceLedgerAdapter(
            base_adapter=mock_ledger,  # type: ignore
            validation_service=validation_service,
        )

        # Execute valid event
        valid_event = make_valid_event()
        await adapter.append_event(valid_event)

        # Verify validation happened before append
        assert call_order == ["validate", "append"]

    @pytest.mark.asyncio
    async def test_validation_failure_prevents_any_db_call(
        self,
        validation_service: LedgerValidationService,
        mock_ledger: MockGovernanceLedgerPort,
    ) -> None:
        """When validation fails, append is never called."""
        append_called = False
        original_append = mock_ledger.append_event

        async def tracked_append(event: GovernanceEvent) -> PersistedGovernanceEvent:
            nonlocal append_called
            append_called = True
            return await original_append(event)

        mock_ledger.append_event = tracked_append  # type: ignore

        adapter = ValidatedGovernanceLedgerAdapter(
            base_adapter=mock_ledger,  # type: ignore
            validation_service=validation_service,
        )

        # Execute invalid event
        invalid_event = make_invalid_event_type_event()

        with pytest.raises(UnknownEventTypeError):
            await adapter.append_event(invalid_event)

        # Verify append was never called
        assert append_called is False


class TestMultipleValidationFailures:
    """Test behavior with multiple invalid events."""

    @pytest.mark.asyncio
    async def test_multiple_rejections_no_cumulative_effect(
        self,
        validated_adapter: ValidatedGovernanceLedgerAdapter,
        mock_ledger: MockGovernanceLedgerPort,
    ) -> None:
        """Multiple rejected events don't have cumulative effect on ledger."""
        initial_count = mock_ledger.event_count

        # Try to append many invalid events
        for _ in range(10):
            with pytest.raises(UnknownEventTypeError):
                await validated_adapter.append_event(make_invalid_event_type_event())

        # Ledger should still be unchanged
        assert mock_ledger.event_count == initial_count

    @pytest.mark.asyncio
    async def test_rejection_doesnt_affect_subsequent_valid_events(
        self,
        validated_adapter: ValidatedGovernanceLedgerAdapter,
        mock_ledger: MockGovernanceLedgerPort,
    ) -> None:
        """Rejected events don't affect subsequent valid events."""
        # First, append a valid event
        valid1 = make_valid_event(task_id="task-1")
        await validated_adapter.append_event(valid1)
        count_after_first = mock_ledger.event_count

        # Try to append invalid event
        with pytest.raises(UnknownEventTypeError):
            await validated_adapter.append_event(make_invalid_event_type_event())

        # Verify count unchanged after rejection
        assert mock_ledger.event_count == count_after_first

        # Append another valid event
        valid2 = make_valid_event(task_id="task-2")
        await validated_adapter.append_event(valid2)

        # Verify second valid event was appended
        assert mock_ledger.event_count == count_after_first + 1
        assert mock_ledger.get_events()[-1].event == valid2


class TestReadOperationsPassThrough:
    """Test that read operations pass through without validation."""

    @pytest.mark.asyncio
    async def test_get_latest_event_no_validation(
        self,
        validated_adapter: ValidatedGovernanceLedgerAdapter,
        mock_ledger: MockGovernanceLedgerPort,
    ) -> None:
        """get_latest_event passes through without validation."""
        # Add an event directly to mock
        event = make_valid_event()
        await mock_ledger.append_event(event)

        # Read through validated adapter
        latest = await validated_adapter.get_latest_event()

        assert latest is not None
        assert latest.event == event

    @pytest.mark.asyncio
    async def test_count_events_no_validation(
        self,
        validated_adapter: ValidatedGovernanceLedgerAdapter,
        mock_ledger: MockGovernanceLedgerPort,
    ) -> None:
        """count_events passes through without validation."""
        # Add events directly
        for _ in range(5):
            await mock_ledger.append_event(make_valid_event())

        count = await validated_adapter.count_events()

        assert count == 5
