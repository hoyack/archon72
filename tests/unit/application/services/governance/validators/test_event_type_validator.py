"""Tests for event type validator.

Story: consent-gov-1.4: Write-Time Validation
AC3: Unknown event types rejected before append (with specific error)
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.application.services.governance.validators.event_type_validator import (
    EventTypeValidator,
)
from src.domain.governance.errors.validation_errors import UnknownEventTypeError
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.event_types import GOVERNANCE_EVENT_TYPES


@pytest.fixture
def validator() -> EventTypeValidator:
    """Create a validator in strict mode."""
    return EventTypeValidator(strict_mode=True, suggest_corrections=True)


@pytest.fixture
def non_strict_validator() -> EventTypeValidator:
    """Create a validator in non-strict mode."""
    return EventTypeValidator(strict_mode=False)


def make_event(event_type: str) -> GovernanceEvent:
    """Create a test event with the given event type."""
    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        actor_id="test-actor",
        trace_id=str(uuid4()),
        payload={"test": "data"},
    )


class TestEventTypeValidator:
    """Tests for EventTypeValidator."""

    @pytest.mark.asyncio
    async def test_valid_event_type_passes(self, validator: EventTypeValidator) -> None:
        """Valid registered event type passes validation."""
        event = make_event("executive.task.accepted")
        await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_all_governance_event_types_valid(self, validator: EventTypeValidator) -> None:
        """All registered governance event types are valid."""
        for event_type in GOVERNANCE_EVENT_TYPES:
            event = make_event(event_type)
            await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_unknown_event_type_rejected(self, validator: EventTypeValidator) -> None:
        """Unknown event type raises UnknownEventTypeError."""
        event = make_event("fake.branch.action")

        with pytest.raises(UnknownEventTypeError) as exc_info:
            await validator.validate(event)

        assert exc_info.value.event_type == "fake.branch.action"
        assert exc_info.value.event_id == event.event_id

    @pytest.mark.asyncio
    async def test_suggestion_provided_for_typo(self, validator: EventTypeValidator) -> None:
        """Suggestion provided for similar event types."""
        # Typo: "executive.task.acceptd" instead of "executive.task.accepted"
        event = make_event("executive.task.acceptd")

        with pytest.raises(UnknownEventTypeError) as exc_info:
            await validator.validate(event)

        # Should suggest the correct type
        assert exc_info.value.suggestion == "executive.task.accepted"

    @pytest.mark.asyncio
    async def test_no_suggestion_for_unrelated_type(self, validator: EventTypeValidator) -> None:
        """No suggestion for completely unrelated event types."""
        event = make_event("xyz.abc.def")

        with pytest.raises(UnknownEventTypeError) as exc_info:
            await validator.validate(event)

        # No good match, so no suggestion
        assert exc_info.value.suggestion == ""

    @pytest.mark.asyncio
    async def test_non_strict_mode_allows_any_type(
        self, non_strict_validator: EventTypeValidator
    ) -> None:
        """Non-strict mode allows any well-formed event type."""
        event = make_event("custom.branch.action")
        await non_strict_validator.validate(event)  # Should not raise

    def test_allowed_types_includes_standard_types(self, validator: EventTypeValidator) -> None:
        """allowed_types includes all standard governance event types."""
        assert validator.allowed_types == GOVERNANCE_EVENT_TYPES

    def test_additional_event_types_merged(self) -> None:
        """Additional event types are merged with standard types."""
        additional = frozenset({"custom.branch.action"})
        validator = EventTypeValidator(additional_event_types=additional)

        assert "custom.branch.action" in validator.allowed_types
        assert "executive.task.accepted" in validator.allowed_types

    @pytest.mark.asyncio
    async def test_is_valid_type_true_for_registered(self, validator: EventTypeValidator) -> None:
        """is_valid_type returns True for registered types."""
        assert validator.is_valid_type("executive.task.accepted") is True

    @pytest.mark.asyncio
    async def test_is_valid_type_false_for_unknown(self, validator: EventTypeValidator) -> None:
        """is_valid_type returns False for unknown types."""
        assert validator.is_valid_type("fake.branch.action") is False

    @pytest.mark.asyncio
    async def test_suggest_corrections_disabled(self) -> None:
        """Suggestions not provided when disabled."""
        validator = EventTypeValidator(strict_mode=True, suggest_corrections=False)
        event = make_event("executive.task.acceptd")

        with pytest.raises(UnknownEventTypeError) as exc_info:
            await validator.validate(event)

        assert exc_info.value.suggestion == ""


class TestEventTypeValidatorPerformance:
    """Performance tests for EventTypeValidator."""

    @pytest.mark.asyncio
    async def test_validation_performance(self, validator: EventTypeValidator) -> None:
        """Event type lookup completes quickly (in-memory frozenset)."""
        import time

        event = make_event("executive.task.accepted")

        start = time.perf_counter()
        for _ in range(1000):
            await validator.validate(event)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 1000 validations should complete in well under 100ms
        # Each validation should be << 1ms
        assert elapsed_ms < 100, f"1000 validations took {elapsed_ms}ms"
