"""Tests for actor validator.

Story: consent-gov-1.4: Write-Time Validation
AC4: Unknown actors rejected before append (with specific error)
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.application.services.governance.validators.actor_validator import (
    ActorValidator,
    InMemoryActorRegistry,
)
from src.domain.governance.errors.validation_errors import UnknownActorError
from src.domain.governance.events.event_envelope import GovernanceEvent


@pytest.fixture
def actor_registry() -> InMemoryActorRegistry:
    """Create a test actor registry with some actors."""
    return InMemoryActorRegistry(
        actors=frozenset({
            "archon-01",
            "archon-02",
            "archon-42",
            "officer-king-01",
            "officer-president-01",
            "system",
        })
    )


@pytest.fixture
def validator(actor_registry: InMemoryActorRegistry) -> ActorValidator:
    """Create a validator with the test registry."""
    return ActorValidator(actor_registry)


@pytest.fixture
def bypass_validator(actor_registry: InMemoryActorRegistry) -> ActorValidator:
    """Create a validator with validation bypassed."""
    return ActorValidator(actor_registry, skip_validation=True)


def make_event(actor_id: str) -> GovernanceEvent:
    """Create a test event with the given actor ID."""
    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type="executive.task.accepted",
        timestamp=datetime.now(timezone.utc),
        actor_id=actor_id,
        trace_id=str(uuid4()),
        payload={"test": "data"},
    )


class TestActorValidator:
    """Tests for ActorValidator."""

    @pytest.mark.asyncio
    async def test_valid_actor_passes(self, validator: ActorValidator) -> None:
        """Registered actor passes validation."""
        event = make_event("archon-42")
        await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_all_registered_actors_pass(
        self, validator: ActorValidator, actor_registry: InMemoryActorRegistry
    ) -> None:
        """All registered actors pass validation."""
        for actor_id in ["archon-01", "archon-02", "officer-king-01", "system"]:
            event = make_event(actor_id)
            await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_unknown_actor_rejected(self, validator: ActorValidator) -> None:
        """Unknown actor raises UnknownActorError."""
        event = make_event("unknown-archon-99")

        with pytest.raises(UnknownActorError) as exc_info:
            await validator.validate(event)

        assert exc_info.value.actor_id == "unknown-archon-99"
        assert exc_info.value.event_id == event.event_id

    @pytest.mark.asyncio
    async def test_error_message_includes_actor_id(self, validator: ActorValidator) -> None:
        """Error message includes the unknown actor ID."""
        event = make_event("unknown-archon-99")

        with pytest.raises(UnknownActorError) as exc_info:
            await validator.validate(event)

        msg = str(exc_info.value)
        assert "unknown-archon-99" in msg

    @pytest.mark.asyncio
    async def test_skip_validation_allows_any_actor(
        self, bypass_validator: ActorValidator
    ) -> None:
        """Skip validation mode allows any actor."""
        event = make_event("unknown-archon-99")
        await bypass_validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_is_valid_actor_true_for_registered(
        self, validator: ActorValidator
    ) -> None:
        """is_valid_actor returns True for registered actors."""
        assert await validator.is_valid_actor("archon-42") is True

    @pytest.mark.asyncio
    async def test_is_valid_actor_false_for_unknown(
        self, validator: ActorValidator
    ) -> None:
        """is_valid_actor returns False for unknown actors."""
        assert await validator.is_valid_actor("unknown-actor") is False

    @pytest.mark.asyncio
    async def test_is_valid_actor_true_when_skipped(
        self, bypass_validator: ActorValidator
    ) -> None:
        """is_valid_actor returns True for any actor when validation skipped."""
        assert await bypass_validator.is_valid_actor("unknown-actor") is True


class TestInMemoryActorRegistry:
    """Tests for InMemoryActorRegistry."""

    @pytest.mark.asyncio
    async def test_actor_exists_true_for_registered(
        self, actor_registry: InMemoryActorRegistry
    ) -> None:
        """actor_exists returns True for registered actors."""
        assert await actor_registry.actor_exists("archon-01") is True

    @pytest.mark.asyncio
    async def test_actor_exists_false_for_unknown(
        self, actor_registry: InMemoryActorRegistry
    ) -> None:
        """actor_exists returns False for unknown actors."""
        assert await actor_registry.actor_exists("unknown") is False

    @pytest.mark.asyncio
    async def test_get_all_actor_ids(
        self, actor_registry: InMemoryActorRegistry
    ) -> None:
        """get_all_actor_ids returns all registered actors."""
        actors = await actor_registry.get_all_actor_ids()
        assert "archon-01" in actors
        assert "system" in actors

    def test_add_actor(self, actor_registry: InMemoryActorRegistry) -> None:
        """add_actor adds a new actor."""
        actor_registry.add_actor("new-archon")
        assert "new-archon" in actor_registry._actors

    def test_remove_actor(self, actor_registry: InMemoryActorRegistry) -> None:
        """remove_actor removes an existing actor."""
        actor_registry.remove_actor("archon-01")
        assert "archon-01" not in actor_registry._actors

    @pytest.mark.asyncio
    async def test_empty_registry(self) -> None:
        """Empty registry returns False for all actors."""
        registry = InMemoryActorRegistry()
        assert await registry.actor_exists("any-actor") is False


class TestActorValidatorPerformance:
    """Performance tests for ActorValidator."""

    @pytest.mark.asyncio
    async def test_validation_performance(self, validator: ActorValidator) -> None:
        """Actor lookup completes quickly (cached projection)."""
        import time

        event = make_event("archon-42")

        start = time.perf_counter()
        for _ in range(1000):
            await validator.validate(event)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 1000 validations should complete in well under 100ms
        # Each validation should be ≤3ms per AC
        assert elapsed_ms < 100, f"1000 validations took {elapsed_ms}ms"
