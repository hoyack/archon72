"""Unit tests for ObserverService cessation methods (Story 7.5, Task 3).

Tests the cessation status retrieval methods added to ObserverService.

Constitutional Constraints:
- FR42: Read-only access indefinitely after cessation
- CT-11: Silent failure destroys legitimacy -> status must be visible
- CT-13: Reads always succeed, even after cessation
"""

from datetime import datetime, timezone

import pytest

from src.application.services.observer_service import ObserverService
from src.infrastructure.stubs.event_store_stub import EventStoreStub
from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


@pytest.fixture
def event_store() -> EventStoreStub:
    """Create event store stub."""
    return EventStoreStub()


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def freeze_checker() -> FreezeCheckerStub:
    """Create freeze checker stub."""
    return FreezeCheckerStub()


@pytest.fixture
def observer_service(
    event_store: EventStoreStub,
    halt_checker: HaltCheckerStub,
    freeze_checker: FreezeCheckerStub,
) -> ObserverService:
    """Create observer service with all dependencies."""
    return ObserverService(
        event_store=event_store,
        halt_checker=halt_checker,
        freeze_checker=freeze_checker,
    )


class TestIsSystemCeased:
    """Tests for is_system_ceased method."""

    async def test_returns_false_when_not_ceased(
        self, observer_service: ObserverService, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Returns False when system is operational."""
        freeze_checker.clear_frozen()
        result = await observer_service.is_system_ceased()
        assert result is False

    async def test_returns_true_when_ceased(
        self, observer_service: ObserverService, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Returns True when system is ceased."""
        freeze_checker.set_frozen_simple()
        result = await observer_service.is_system_ceased()
        assert result is True

    async def test_returns_false_when_no_freeze_checker(
        self, event_store: EventStoreStub, halt_checker: HaltCheckerStub
    ) -> None:
        """Returns False when freeze_checker is not provided."""
        service = ObserverService(
            event_store=event_store,
            halt_checker=halt_checker,
            freeze_checker=None,  # No freeze checker
        )
        result = await service.is_system_ceased()
        assert result is False


class TestGetCessationDetails:
    """Tests for get_cessation_details method."""

    async def test_returns_none_when_not_ceased(
        self, observer_service: ObserverService, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Returns None when system is not ceased."""
        freeze_checker.clear_frozen()
        result = await observer_service.get_cessation_details()
        assert result is None

    async def test_returns_details_when_ceased(
        self, observer_service: ObserverService, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Returns CessationDetails when system is ceased."""
        ceased_at = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
        freeze_checker.set_frozen(
            ceased_at=ceased_at,
            final_sequence=12345,
            reason="Test cessation reason",
        )
        result = await observer_service.get_cessation_details()
        assert result is not None
        assert result.ceased_at == ceased_at
        assert result.final_sequence_number == 12345
        assert result.reason == "Test cessation reason"

    async def test_returns_none_when_no_freeze_checker(
        self, event_store: EventStoreStub, halt_checker: HaltCheckerStub
    ) -> None:
        """Returns None when freeze_checker is not provided."""
        service = ObserverService(
            event_store=event_store,
            halt_checker=halt_checker,
            freeze_checker=None,
        )
        result = await service.get_cessation_details()
        assert result is None


class TestGetCessationStatusForResponse:
    """Tests for get_cessation_status_for_response method."""

    async def test_returns_none_when_not_ceased(
        self, observer_service: ObserverService, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Returns None when system is not ceased."""
        freeze_checker.clear_frozen()
        result = await observer_service.get_cessation_status_for_response()
        assert result is None

    async def test_returns_dict_when_ceased(
        self, observer_service: ObserverService, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Returns properly formatted dict when system is ceased (AC5)."""
        ceased_at = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
        freeze_checker.set_frozen(
            ceased_at=ceased_at,
            final_sequence=12345,
            reason="Unanimous vote for cessation",
        )
        result = await observer_service.get_cessation_status_for_response()
        assert result is not None
        assert result["system_status"] == "CEASED"
        assert result["final_sequence_number"] == 12345
        assert result["cessation_reason"] == "Unanimous vote for cessation"
        assert "2024-06-15" in result["ceased_at"]

    async def test_dict_format_matches_spec(
        self, observer_service: ObserverService, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Returned dict has all required fields per AC5."""
        freeze_checker.set_frozen_simple()
        result = await observer_service.get_cessation_status_for_response()
        assert result is not None
        # Check all required fields exist
        assert "system_status" in result
        assert "ceased_at" in result
        assert "final_sequence_number" in result
        assert "cessation_reason" in result


class TestCessationDoesNotBlockReads:
    """Tests ensuring reads continue working after cessation (CT-13, FR42)."""

    async def test_get_events_works_when_ceased(
        self, observer_service: ObserverService, freeze_checker: FreezeCheckerStub
    ) -> None:
        """get_events continues to work after cessation."""
        freeze_checker.set_frozen_simple()
        # Should not raise
        events, total = await observer_service.get_events()
        assert isinstance(events, list)
        assert isinstance(total, int)

    async def test_verify_chain_works_when_ceased(
        self, observer_service: ObserverService, freeze_checker: FreezeCheckerStub
    ) -> None:
        """verify_chain continues to work after cessation."""
        freeze_checker.set_frozen_simple()
        # Should not raise
        result = await observer_service.verify_chain(1, 10)
        assert result is not None
