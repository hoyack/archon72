"""Unit tests for RecoveryWaitingPeriodPort abstract interface (Story 3.6, FR21).

Tests that the port interface:
- Defines all required methods from story tasks
- Is an abstract base class
- Uses proper type hints
"""

from abc import ABC
from datetime import timedelta
from typing import Optional
from uuid import UUID, uuid4

import pytest

from src.application.ports.recovery_waiting_period import RecoveryWaitingPeriodPort
from src.domain.events.recovery_completed import RecoveryCompletedPayload
from src.domain.models.ceremony_evidence import CeremonyEvidence
from src.domain.models.recovery_waiting_period import RecoveryWaitingPeriod


class TestRecoveryWaitingPeriodPortInterface:
    """Tests for RecoveryWaitingPeriodPort abstract interface."""

    def test_is_abstract_base_class(self) -> None:
        """Port is an abstract base class."""
        assert issubclass(RecoveryWaitingPeriodPort, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """Cannot instantiate abstract port directly."""
        with pytest.raises(TypeError):
            RecoveryWaitingPeriodPort()  # type: ignore

    def test_has_start_waiting_period_method(self) -> None:
        """Port defines start_waiting_period method."""
        assert hasattr(RecoveryWaitingPeriodPort, "start_waiting_period")
        method = getattr(RecoveryWaitingPeriodPort, "start_waiting_period")
        assert callable(method)

    def test_has_get_active_waiting_period_method(self) -> None:
        """Port defines get_active_waiting_period method."""
        assert hasattr(RecoveryWaitingPeriodPort, "get_active_waiting_period")
        method = getattr(RecoveryWaitingPeriodPort, "get_active_waiting_period")
        assert callable(method)

    def test_has_is_waiting_period_elapsed_method(self) -> None:
        """Port defines is_waiting_period_elapsed method."""
        assert hasattr(RecoveryWaitingPeriodPort, "is_waiting_period_elapsed")
        method = getattr(RecoveryWaitingPeriodPort, "is_waiting_period_elapsed")
        assert callable(method)

    def test_has_get_remaining_time_method(self) -> None:
        """Port defines get_remaining_time method."""
        assert hasattr(RecoveryWaitingPeriodPort, "get_remaining_time")
        method = getattr(RecoveryWaitingPeriodPort, "get_remaining_time")
        assert callable(method)

    def test_has_complete_waiting_period_method(self) -> None:
        """Port defines complete_waiting_period method."""
        assert hasattr(RecoveryWaitingPeriodPort, "complete_waiting_period")
        method = getattr(RecoveryWaitingPeriodPort, "complete_waiting_period")
        assert callable(method)


class TestConcreteImplementationContract:
    """Tests verifying a concrete implementation can satisfy the port contract."""

    def test_concrete_implementation_is_valid(self) -> None:
        """A concrete implementation must implement all methods."""
        # This test verifies the contract by creating a minimal stub
        from datetime import datetime, timezone

        class MockRecoveryWaitingPeriodPort(RecoveryWaitingPeriodPort):
            """Minimal implementation to verify contract."""

            async def start_waiting_period(
                self,
                crisis_event_id: UUID,
                initiated_by: tuple[str, ...],
            ) -> RecoveryWaitingPeriod:
                return RecoveryWaitingPeriod.start(
                    crisis_event_id=crisis_event_id,
                    initiated_by=initiated_by,
                )

            async def get_active_waiting_period(self) -> Optional[RecoveryWaitingPeriod]:
                return None

            async def is_waiting_period_elapsed(self) -> bool:
                return False

            async def get_remaining_time(self) -> Optional[timedelta]:
                return None

            async def complete_waiting_period(
                self,
                ceremony_evidence: CeremonyEvidence,
            ) -> RecoveryCompletedPayload:
                return RecoveryCompletedPayload(
                    crisis_event_id=uuid4(),
                    waiting_period_started_at=datetime.now(timezone.utc),
                    recovery_completed_at=datetime.now(timezone.utc),
                    keeper_ceremony_id=ceremony_evidence.ceremony_id,
                    approving_keepers=ceremony_evidence.get_keeper_ids(),
                )

        # If this doesn't raise, the implementation is valid
        port = MockRecoveryWaitingPeriodPort()
        assert isinstance(port, RecoveryWaitingPeriodPort)


class TestPortDocstringExample:
    """Tests that validate the port docstring example flow.

    The port docstring (lines 43-52) shows this usage pattern:
        >>> period = await port.start_waiting_period(crisis_id, keepers)
        >>> if await port.is_waiting_period_elapsed():
        ...     # Proceed with recovery
        ...     pass

    This test validates that flow using the stub implementation.
    """

    @pytest.mark.asyncio
    async def test_docstring_example_start_and_check_elapsed(self) -> None:
        """Docstring example: Start period, then check if elapsed."""
        from src.infrastructure.stubs.recovery_waiting_period_stub import (
            RecoveryWaitingPeriodStub,
        )

        port = RecoveryWaitingPeriodStub()
        crisis_id = uuid4()

        # Start waiting period (as shown in docstring example)
        period = await port.start_waiting_period(
            crisis_event_id=crisis_id,
            initiated_by=("keeper-001", "keeper-002"),
        )

        assert period is not None
        assert period.crisis_event_id == crisis_id
        assert period.initiated_by == ("keeper-001", "keeper-002")

        # Check if elapsed (as shown in docstring example) - should be False initially
        is_elapsed = await port.is_waiting_period_elapsed()
        assert is_elapsed is False  # 48 hours haven't passed

    @pytest.mark.asyncio
    async def test_docstring_example_elapsed_after_time_passes(self) -> None:
        """Docstring example extension: elapsed returns True after 48 hours."""
        from src.infrastructure.stubs.recovery_waiting_period_stub import (
            RecoveryWaitingPeriodStub,
        )

        port = RecoveryWaitingPeriodStub()
        crisis_id = uuid4()

        # Start waiting period
        await port.start_waiting_period(
            crisis_event_id=crisis_id,
            initiated_by=("keeper-001", "keeper-002"),
        )

        # Simulate time passing using stub helper
        port.set_elapsed(True)

        # Now elapsed should return True
        is_elapsed = await port.is_waiting_period_elapsed()
        assert is_elapsed is True  # Can proceed with recovery
