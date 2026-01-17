"""Tests for LedgerValidationService orchestrator.

Story: consent-gov-1.4: Write-Time Validation
AC1: Illegal state transitions rejected before append
AC2: Hash chain breaks rejected before append
AC3: Unknown event types rejected before append
AC4: Unknown actors rejected before append
AC5: Specific error types with context
AC7: Validation happens before transaction, not inside
"""

import pytest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

from src.application.services.governance.ledger_validation_service import (
    EventValidator,
    LedgerValidationService,
    NoOpValidationService,
    ValidationResult,
)
from src.application.services.governance.validators.event_type_validator import (
    EventTypeValidator,
)
from src.application.services.governance.validators.actor_validator import (
    ActorValidator,
    InMemoryActorRegistry,
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
    HashChainBreakError,
    IllegalStateTransitionError,
    UnknownActorError,
    UnknownEventTypeError,
    WriteTimeValidationError,
)
from src.domain.governance.events.event_envelope import GovernanceEvent


@pytest.fixture
def sample_event() -> GovernanceEvent:
    """Create a sample governance event for testing."""
    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type="consent.task.requested",
        timestamp=datetime.now(timezone.utc),
        actor_id="test-actor",
        trace_id=str(uuid4()),
        payload={"task_id": "task-123"},
    )


class MockLedgerPort:
    """Mock ledger port for hash chain validator."""

    async def get_latest_event(self) -> GovernanceEvent | None:
        return None


@pytest.fixture
def event_type_validator() -> EventTypeValidator:
    """Create a real event type validator."""
    return EventTypeValidator()


@pytest.fixture
def actor_registry() -> InMemoryActorRegistry:
    """Create an actor registry with the test actor."""
    return InMemoryActorRegistry(frozenset({"test-actor"}))


@pytest.fixture
def actor_validator(actor_registry: InMemoryActorRegistry) -> ActorValidator:
    """Create a real actor validator."""
    return ActorValidator(actor_registry)


@pytest.fixture
def mock_ledger() -> MockLedgerPort:
    """Create a mock ledger port."""
    return MockLedgerPort()


@pytest.fixture
def hash_chain_validator(mock_ledger: MockLedgerPort) -> HashChainValidator:
    """Create a hash chain validator with mock ledger."""
    return HashChainValidator(mock_ledger, skip_validation=True)  # type: ignore


@pytest.fixture
def state_projection() -> InMemoryStateProjection:
    """Create a state projection."""
    return InMemoryStateProjection()


@pytest.fixture
def state_transition_validator(
    state_projection: InMemoryStateProjection,
) -> StateTransitionValidator:
    """Create a state transition validator."""
    return StateTransitionValidator(state_projection)


@pytest.fixture
def validation_service(
    event_type_validator: EventTypeValidator,
    actor_validator: ActorValidator,
    hash_chain_validator: HashChainValidator,
    state_transition_validator: StateTransitionValidator,
) -> LedgerValidationService:
    """Create a validation service with all validators."""
    return LedgerValidationService(
        event_type_validator=event_type_validator,
        actor_validator=actor_validator,
        hash_chain_validator=hash_chain_validator,
        state_transition_validator=state_transition_validator,
    )


class TestLedgerValidationServiceConstruction:
    """Tests for LedgerValidationService construction."""

    def test_create_with_all_validators(
        self,
        event_type_validator: EventTypeValidator,
        actor_validator: ActorValidator,
        hash_chain_validator: HashChainValidator,
        state_transition_validator: StateTransitionValidator,
    ) -> None:
        """Service can be created with all validators."""
        service = LedgerValidationService(
            event_type_validator=event_type_validator,
            actor_validator=actor_validator,
            hash_chain_validator=hash_chain_validator,
            state_transition_validator=state_transition_validator,
        )
        assert len(service._validators) == 4

    def test_validators_stored_in_performance_order(
        self,
        event_type_validator: EventTypeValidator,
        actor_validator: ActorValidator,
        hash_chain_validator: HashChainValidator,
        state_transition_validator: StateTransitionValidator,
    ) -> None:
        """Validators are stored in performance order (fastest first)."""
        service = LedgerValidationService(
            event_type_validator=event_type_validator,
            actor_validator=actor_validator,
            hash_chain_validator=hash_chain_validator,
            state_transition_validator=state_transition_validator,
        )
        validator_order = [name for name, _ in service._validators]
        # Event type is fastest (≤1ms), hash chain is slowest (≤50ms)
        assert validator_order[0] == "event_type"
        assert validator_order[-1] == "hash_chain"


class TestLedgerValidationServiceValidate:
    """Tests for LedgerValidationService.validate() method."""

    @pytest.mark.asyncio
    async def test_valid_event_passes(
        self,
        validation_service: LedgerValidationService,
        sample_event: GovernanceEvent,
    ) -> None:
        """Validation passes for valid events."""
        await validation_service.validate(sample_event)  # Should not raise

    @pytest.mark.asyncio
    async def test_invalid_event_type_rejected(
        self,
        validation_service: LedgerValidationService,
    ) -> None:
        """Invalid event type is rejected."""
        # Use syntactically valid but unregistered event type
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="unknown.event.type",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={},
        )

        with pytest.raises(UnknownEventTypeError):
            await validation_service.validate(event)

    @pytest.mark.asyncio
    async def test_invalid_actor_rejected(
        self,
        validation_service: LedgerValidationService,
    ) -> None:
        """Invalid actor is rejected."""
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="consent.task.requested",
            timestamp=datetime.now(timezone.utc),
            actor_id="unknown-actor-not-registered",
            trace_id=str(uuid4()),
            payload={},
        )

        with pytest.raises(UnknownActorError):
            await validation_service.validate(event)

    @pytest.mark.asyncio
    async def test_invalid_state_transition_rejected(
        self,
        validation_service: LedgerValidationService,
        state_projection: InMemoryStateProjection,
    ) -> None:
        """Invalid state transition is rejected."""
        # Set up task in terminal state
        state_projection.set_state("task", "task-123", TaskState.COMPLETED.value)

        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.activated",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={"task_id": "task-123"},
        )

        with pytest.raises(IllegalStateTransitionError):
            await validation_service.validate(event)

    @pytest.mark.asyncio
    async def test_fail_fast_stops_on_first_error(
        self,
        event_type_validator: EventTypeValidator,
        actor_validator: ActorValidator,
        hash_chain_validator: HashChainValidator,
        state_transition_validator: StateTransitionValidator,
    ) -> None:
        """Validation stops on first error (fail-fast)."""
        # Create service with tracked validators
        call_order: list[str] = []

        original_et_validate = event_type_validator.validate

        async def tracked_et_validate(event: GovernanceEvent) -> None:
            call_order.append("event_type")
            await original_et_validate(event)

        event_type_validator.validate = tracked_et_validate  # type: ignore

        original_actor_validate = actor_validator.validate

        async def tracked_actor_validate(event: GovernanceEvent) -> None:
            call_order.append("actor")
            await original_actor_validate(event)

        actor_validator.validate = tracked_actor_validate  # type: ignore

        service = LedgerValidationService(
            event_type_validator=event_type_validator,
            actor_validator=actor_validator,
            hash_chain_validator=hash_chain_validator,
            state_transition_validator=state_transition_validator,
        )

        # Invalid event type should fail fast before actor check
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="invalid.event.type",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={},
        )

        with pytest.raises(UnknownEventTypeError):
            await service.validate(event)

        # Only event_type validator should have been called
        assert call_order == ["event_type"]

    @pytest.mark.asyncio
    async def test_preserves_specific_error_types(
        self,
        validation_service: LedgerValidationService,
        state_projection: InMemoryStateProjection,
    ) -> None:
        """Specific error types are preserved (AC5)."""
        # Test UnknownEventTypeError (syntactically valid but unregistered)
        event1 = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="unknown.event.type",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={},
        )
        with pytest.raises(UnknownEventTypeError):
            await validation_service.validate(event1)

        # Test UnknownActorError
        event2 = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="consent.task.requested",
            timestamp=datetime.now(timezone.utc),
            actor_id="unknown",
            trace_id=str(uuid4()),
            payload={},
        )
        with pytest.raises(UnknownActorError):
            await validation_service.validate(event2)

        # Test IllegalStateTransitionError
        state_projection.set_state("task", "task-123", TaskState.COMPLETED.value)
        event3 = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.activated",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={"task_id": "task-123"},
        )
        with pytest.raises(IllegalStateTransitionError):
            await validation_service.validate(event3)


class TestLedgerValidationServiceValidateWithResult:
    """Tests for LedgerValidationService.validate_with_result() method."""

    @pytest.mark.asyncio
    async def test_returns_valid_on_success(
        self,
        validation_service: LedgerValidationService,
        sample_event: GovernanceEvent,
    ) -> None:
        """Returns valid result when validation passes."""
        result = await validation_service.validate_with_result(sample_event)

        assert result.is_valid is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_returns_invalid_with_error(
        self,
        validation_service: LedgerValidationService,
    ) -> None:
        """Returns invalid result with error when validation fails."""
        # Use syntactically valid but unregistered event type
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="unknown.event.type",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={},
        )

        result = await validation_service.validate_with_result(event)

        assert result.is_valid is False
        assert result.error is not None
        assert isinstance(result.error, UnknownEventTypeError)
        assert result.validator_name == "event_type"

    @pytest.mark.asyncio
    async def test_includes_failing_validator_name(
        self,
        validation_service: LedgerValidationService,
    ) -> None:
        """Result includes the name of the failing validator."""
        # Valid event type but invalid actor
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="consent.task.requested",
            timestamp=datetime.now(timezone.utc),
            actor_id="unknown-actor",
            trace_id=str(uuid4()),
            payload={},
        )

        result = await validation_service.validate_with_result(event)

        assert result.is_valid is False
        assert result.validator_name == "actor"

    @pytest.mark.asyncio
    async def test_validation_result_immutable(
        self,
        validation_service: LedgerValidationService,
        sample_event: GovernanceEvent,
    ) -> None:
        """ValidationResult is a frozen dataclass."""
        result = await validation_service.validate_with_result(sample_event)

        # Should be frozen (immutable)
        with pytest.raises(AttributeError):
            result.is_valid = False  # type: ignore


class TestLedgerValidationServiceIsValid:
    """Tests for LedgerValidationService.is_valid() method."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(
        self,
        validation_service: LedgerValidationService,
        sample_event: GovernanceEvent,
    ) -> None:
        """Returns True when validation passes."""
        is_valid = await validation_service.is_valid(sample_event)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(
        self,
        validation_service: LedgerValidationService,
    ) -> None:
        """Returns False when validation fails."""
        # Use syntactically valid but unregistered event type
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="unknown.event.type",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={},
        )

        is_valid = await validation_service.is_valid(event)

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_does_not_raise(
        self,
        validation_service: LedgerValidationService,
    ) -> None:
        """is_valid never raises, only returns False."""
        # Use syntactically valid but unregistered event type
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="unknown.event.type",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={},
        )

        # Should not raise
        result = await validation_service.is_valid(event)
        assert result is False


class TestNoOpValidationService:
    """Tests for NoOpValidationService (testing bypass)."""

    @pytest.fixture
    def noop_service(self) -> NoOpValidationService:
        return NoOpValidationService()

    @pytest.mark.asyncio
    async def test_validate_always_passes(
        self, noop_service: NoOpValidationService, sample_event: GovernanceEvent
    ) -> None:
        """NoOpValidationService.validate() never raises."""
        await noop_service.validate(sample_event)  # Should not raise

    @pytest.mark.asyncio
    async def test_validate_with_result_always_valid(
        self, noop_service: NoOpValidationService, sample_event: GovernanceEvent
    ) -> None:
        """NoOpValidationService always returns valid result."""
        result = await noop_service.validate_with_result(sample_event)

        assert result.is_valid is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_is_valid_always_true(
        self, noop_service: NoOpValidationService, sample_event: GovernanceEvent
    ) -> None:
        """NoOpValidationService.is_valid() always returns True."""
        is_valid = await noop_service.is_valid(sample_event)

        assert is_valid is True


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self) -> None:
        """Valid result has is_valid=True and no error."""
        result = ValidationResult(is_valid=True, error=None)

        assert result.is_valid is True
        assert result.error is None

    def test_invalid_result(self) -> None:
        """Invalid result has is_valid=False and an error."""
        error = UnknownEventTypeError(
            event_id=uuid4(),
            event_type="bad.event",
        )
        result = ValidationResult(is_valid=False, error=error)

        assert result.is_valid is False
        assert result.error is error

    def test_frozen(self) -> None:
        """ValidationResult is immutable."""
        result = ValidationResult(is_valid=True, error=None)

        with pytest.raises(AttributeError):
            result.is_valid = False  # type: ignore


class TestLedgerValidationServiceValidatorOrder:
    """Tests for validator execution order (performance optimization)."""

    @pytest.mark.asyncio
    async def test_validators_called_in_performance_order(
        self,
        event_type_validator: EventTypeValidator,
        actor_validator: ActorValidator,
        hash_chain_validator: HashChainValidator,
        state_transition_validator: StateTransitionValidator,
        sample_event: GovernanceEvent,
    ) -> None:
        """Validators are called in the order they were provided."""
        call_order: list[str] = []

        # Track event type validator
        original_et = event_type_validator.validate
        async def track_et(event: GovernanceEvent) -> None:
            call_order.append("event_type")
            await original_et(event)
        event_type_validator.validate = track_et  # type: ignore

        # Track actor validator
        original_actor = actor_validator.validate
        async def track_actor(event: GovernanceEvent) -> None:
            call_order.append("actor")
            await original_actor(event)
        actor_validator.validate = track_actor  # type: ignore

        # Track state transition validator
        original_state = state_transition_validator.validate
        async def track_state(event: GovernanceEvent) -> None:
            call_order.append("state_transition")
            await original_state(event)
        state_transition_validator.validate = track_state  # type: ignore

        # Track hash chain validator
        original_hash = hash_chain_validator.validate
        async def track_hash(event: GovernanceEvent) -> None:
            call_order.append("hash_chain")
            await original_hash(event)
        hash_chain_validator.validate = track_hash  # type: ignore

        service = LedgerValidationService(
            event_type_validator=event_type_validator,
            actor_validator=actor_validator,
            hash_chain_validator=hash_chain_validator,
            state_transition_validator=state_transition_validator,
        )
        await service.validate(sample_event)

        # Performance order: event_type, actor, state_transition, hash_chain
        assert call_order == ["event_type", "actor", "state_transition", "hash_chain"]

    def test_recommended_performance_order(self) -> None:
        """Document recommended validator order for performance.

        Per AC6 performance requirements:
        1. Event type: ≤1ms (O(1) lookup)
        2. Actor: ≤3ms (cached projection)
        3. State machine: ≤10ms (projection lookup + graph traversal)
        4. Hash chain: ≤50ms (crypto + DB lookup)
        """
        # This test documents the recommended order
        validator_order = [
            "event_type",       # ≤1ms
            "actor",            # ≤3ms
            "state_transition", # ≤10ms
            "hash_chain",       # ≤50ms
        ]

        # Fail-fast means we want cheapest validators first
        # This maximizes early rejection with minimal resource usage
        assert validator_order[0] == "event_type"
        assert validator_order[-1] == "hash_chain"
