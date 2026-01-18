"""Integration tests for Separation Enforcement (Story 8.2, FR52).

Tests the full separation flow between operational and constitutional data.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.separation_enforcement_service import (
    SeparationEnforcementService,
    WriteTarget,
)
from src.domain.errors.separation import OperationalToEventStoreError
from src.domain.models.event_type_registry import EventTypeRegistry
from src.infrastructure.stubs.event_store_stub import EventStoreStub
from src.infrastructure.stubs.separation_validator_stub import SeparationValidatorStub


class MockEvent:
    """Mock event for testing event store validation."""

    def __init__(self, event_type: str, sequence: int = 1) -> None:
        """Create a mock event with given type."""
        self.event_id = uuid4()
        self.event_type = event_type
        self.sequence = sequence
        self.authority_timestamp = datetime.now(timezone.utc)


class TestEventStoreRejectsOperationalTypes:
    """Test that event store rejects operational metric types (AC1, AC3)."""

    @pytest.fixture
    def event_store(self) -> EventStoreStub:
        """Create event store stub."""
        return EventStoreStub()

    @pytest.mark.asyncio
    async def test_rejects_uptime_recorded(self, event_store: EventStoreStub) -> None:
        """Test event store rejects uptime_recorded operational type."""
        event = MockEvent(event_type="uptime_recorded")
        with pytest.raises(OperationalToEventStoreError) as exc_info:
            await event_store.append_event(event)  # type: ignore
        assert exc_info.value.data_type == "uptime_recorded"

    @pytest.mark.asyncio
    async def test_rejects_latency_measured(self, event_store: EventStoreStub) -> None:
        """Test event store rejects latency_measured operational type."""
        event = MockEvent(event_type="latency_measured")
        with pytest.raises(OperationalToEventStoreError):
            await event_store.append_event(event)  # type: ignore

    @pytest.mark.asyncio
    async def test_rejects_error_logged(self, event_store: EventStoreStub) -> None:
        """Test event store rejects error_logged operational type."""
        event = MockEvent(event_type="error_logged")
        with pytest.raises(OperationalToEventStoreError):
            await event_store.append_event(event)  # type: ignore

    @pytest.mark.asyncio
    async def test_rejects_health_check(self, event_store: EventStoreStub) -> None:
        """Test event store rejects health_check operational type."""
        event = MockEvent(event_type="health_check")
        with pytest.raises(OperationalToEventStoreError):
            await event_store.append_event(event)  # type: ignore


class TestConstitutionalEventsWriteSuccessfully:
    """Test that constitutional events write successfully (AC1, AC3)."""

    @pytest.fixture
    def event_store(self) -> EventStoreStub:
        """Create event store stub."""
        return EventStoreStub()

    @pytest.mark.asyncio
    async def test_accepts_deliberation_output(
        self, event_store: EventStoreStub
    ) -> None:
        """Test event store accepts deliberation_output constitutional type."""
        event = MockEvent(event_type="deliberation_output")
        result = await event_store.append_event(event)  # type: ignore
        assert result.event_type == "deliberation_output"

    @pytest.mark.asyncio
    async def test_accepts_vote_cast(self, event_store: EventStoreStub) -> None:
        """Test event store accepts vote_cast constitutional type."""
        event = MockEvent(event_type="vote_cast", sequence=2)
        result = await event_store.append_event(event)  # type: ignore
        assert result.event_type == "vote_cast"

    @pytest.mark.asyncio
    async def test_accepts_halt_triggered(self, event_store: EventStoreStub) -> None:
        """Test event store accepts halt_triggered constitutional type."""
        event = MockEvent(event_type="halt_triggered", sequence=3)
        result = await event_store.append_event(event)  # type: ignore
        assert result.event_type == "halt_triggered"

    @pytest.mark.asyncio
    async def test_accepts_cessation_executed(
        self, event_store: EventStoreStub
    ) -> None:
        """Test event store accepts cessation_executed constitutional type."""
        event = MockEvent(event_type="cessation_executed", sequence=4)
        result = await event_store.append_event(event)  # type: ignore
        assert result.event_type == "cessation_executed"


class TestSeparationEnforcementFlow:
    """Test full separation enforcement flow (AC4)."""

    @pytest.fixture
    def service(self) -> SeparationEnforcementService:
        """Create separation enforcement service."""
        validator = SeparationValidatorStub()
        return SeparationEnforcementService(validator)

    @pytest.fixture
    def event_store(self) -> EventStoreStub:
        """Create event store stub."""
        return EventStoreStub()

    @pytest.mark.asyncio
    async def test_validate_before_write_constitutional(
        self,
        service: SeparationEnforcementService,
        event_store: EventStoreStub,
    ) -> None:
        """Test validation + write flow for constitutional event."""
        # Step 1: Validate
        result = service.validate_write_target(
            "deliberation_output", WriteTarget.EVENT_STORE
        )
        assert result.valid is True

        # Step 2: Write
        event = MockEvent(event_type="deliberation_output")
        written = await event_store.append_event(event)  # type: ignore
        assert written is not None

    @pytest.mark.asyncio
    async def test_validate_before_write_operational_blocked(
        self,
        service: SeparationEnforcementService,
        event_store: EventStoreStub,
    ) -> None:
        """Test validation + attempted write flow for operational data."""
        # Step 1: Validate should fail
        result = service.validate_write_target(
            "uptime_recorded", WriteTarget.EVENT_STORE
        )
        assert result.valid is False

        # Step 2: Attempt write should also fail
        event = MockEvent(event_type="uptime_recorded")
        with pytest.raises(OperationalToEventStoreError):
            await event_store.append_event(event)  # type: ignore

    @pytest.mark.asyncio
    async def test_assert_not_event_store_integration(
        self,
        service: SeparationEnforcementService,
        event_store: EventStoreStub,
    ) -> None:
        """Test assert_not_event_store guards write operations."""
        # Constitutional type should pass assertion
        service.assert_not_event_store("deliberation_output")
        event = MockEvent(event_type="deliberation_output")
        await event_store.append_event(event)  # type: ignore

        # Operational type should fail assertion
        with pytest.raises(OperationalToEventStoreError):
            service.assert_not_event_store("uptime_recorded")


class TestNoOperationalTypesInEventStore:
    """Test that event store never contains operational types (AC3)."""

    @pytest.fixture
    def event_store(self) -> EventStoreStub:
        """Create event store with constitutional events."""
        store = EventStoreStub()
        return store

    @pytest.mark.asyncio
    async def test_query_returns_only_constitutional_types(
        self, event_store: EventStoreStub
    ) -> None:
        """Test querying event store returns only constitutional types."""
        # Add constitutional events
        events = [
            MockEvent("deliberation_output", sequence=1),
            MockEvent("vote_cast", sequence=2),
            MockEvent("halt_triggered", sequence=3),
        ]
        for event in events:
            await event_store.append_event(event)  # type: ignore

        # Query all events
        count = await event_store.count_events()
        assert count == 3

        # Verify all types are constitutional
        for event_type in ["deliberation_output", "vote_cast", "halt_triggered"]:
            assert EventTypeRegistry.is_valid_constitutional_type(event_type)

    @pytest.mark.asyncio
    async def test_filtered_query_excludes_operational(
        self, event_store: EventStoreStub
    ) -> None:
        """Test filtered queries never return operational types."""
        # Add constitutional events
        event = MockEvent("deliberation_output")
        await event_store.append_event(event)  # type: ignore

        # Attempt to filter by operational type returns empty
        results = await event_store.get_events_by_type("uptime_recorded")
        assert len(results) == 0


class TestRegistryConsistency:
    """Test consistency between registry and stub."""

    def test_stub_and_registry_constitutional_types_match(self) -> None:
        """Test stub and registry have same constitutional types."""
        stub = SeparationValidatorStub()
        stub_types = stub.get_allowed_event_types()
        registry_types = set(EventTypeRegistry.CONSTITUTIONAL_TYPES)

        # They should be equal
        assert stub_types == registry_types

    def test_stub_and_registry_operational_types_match(self) -> None:
        """Test stub and registry have same operational types."""
        stub = SeparationValidatorStub()
        registry_types = set(EventTypeRegistry.OPERATIONAL_TYPES)

        # Check all registry operational types are recognized by stub
        for op_type in registry_types:
            assert stub.is_operational(op_type)


class TestConstitutionalIntegrityIndependence:
    """Test constitutional integrity is independent of operational data (AC2)."""

    def test_operational_types_excluded_from_constitutional_types(self) -> None:
        """Test operational types are not in constitutional types set."""
        for op_type in EventTypeRegistry.OPERATIONAL_TYPES:
            assert not EventTypeRegistry.is_valid_constitutional_type(op_type)

    def test_constitutional_types_excluded_from_operational_types(self) -> None:
        """Test constitutional types are not in operational types set."""
        for const_type in EventTypeRegistry.CONSTITUTIONAL_TYPES:
            assert not EventTypeRegistry.is_operational_type(const_type)

    def test_no_cross_contamination(self) -> None:
        """Test there's no overlap between type sets."""
        intersection = (
            EventTypeRegistry.CONSTITUTIONAL_TYPES & EventTypeRegistry.OPERATIONAL_TYPES
        )
        assert len(intersection) == 0, f"Cross-contamination found: {intersection}"
