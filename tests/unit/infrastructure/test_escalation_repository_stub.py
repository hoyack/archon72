"""Unit tests for EscalationRepositoryStub (Story 6.2, FR31).

Tests:
- Save and retrieve escalation events
- Save and retrieve acknowledgment events
- List operations
- Clear method for test cleanup

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.breach import BreachType
from src.domain.events.escalation import (
    BreachAcknowledgedEventPayload,
    EscalationEventPayload,
    ResponseChoice,
)
from src.infrastructure.stubs.escalation_repository_stub import EscalationRepositoryStub


class TestEscalationRepositoryStubInit:
    """Tests for EscalationRepositoryStub initialization."""

    def test_init_creates_empty_storage(self) -> None:
        """Test that repository initializes with empty storage."""
        repo = EscalationRepositoryStub()

        assert repo._escalations == {}
        assert repo._acknowledgments == {}

    def test_clear_empties_storage(self) -> None:
        """Test that clear removes all stored data."""
        repo = EscalationRepositoryStub()
        repo._escalations[uuid4()] = object()  # type: ignore
        repo._acknowledgments[uuid4()] = object()  # type: ignore

        repo.clear()

        assert repo._escalations == {}
        assert repo._acknowledgments == {}


class TestSaveEscalation:
    """Tests for save_escalation method."""

    @pytest.fixture
    def repo(self) -> EscalationRepositoryStub:
        """Create a fresh repository for each test."""
        return EscalationRepositoryStub()

    @pytest.fixture
    def sample_escalation(self) -> EscalationEventPayload:
        """Create a sample escalation payload."""
        return EscalationEventPayload(
            escalation_id=uuid4(),
            breach_id=uuid4(),
            breach_type=BreachType.THRESHOLD_VIOLATION,
            escalation_timestamp=datetime.now(timezone.utc),
            days_since_breach=8,
            agenda_placement_reason="FR31: Unacknowledged breach exceeded 7-day threshold",
        )

    @pytest.mark.asyncio
    async def test_save_escalation_stores_by_breach_id(
        self,
        repo: EscalationRepositoryStub,
        sample_escalation: EscalationEventPayload,
    ) -> None:
        """Test that escalation is stored by breach_id."""
        await repo.save_escalation(sample_escalation)

        assert sample_escalation.breach_id in repo._escalations
        assert repo._escalations[sample_escalation.breach_id] == sample_escalation

    @pytest.mark.asyncio
    async def test_save_escalation_raises_on_duplicate(
        self,
        repo: EscalationRepositoryStub,
    ) -> None:
        """Test that saving escalation for same breach_id raises error."""
        from src.domain.errors.escalation import BreachAlreadyEscalatedError

        breach_id = uuid4()
        escalation1 = EscalationEventPayload(
            escalation_id=uuid4(),
            breach_id=breach_id,
            breach_type=BreachType.THRESHOLD_VIOLATION,
            escalation_timestamp=datetime.now(timezone.utc),
            days_since_breach=7,
            agenda_placement_reason="First escalation",
        )
        escalation2 = EscalationEventPayload(
            escalation_id=uuid4(),
            breach_id=breach_id,
            breach_type=BreachType.THRESHOLD_VIOLATION,
            escalation_timestamp=datetime.now(timezone.utc),
            days_since_breach=8,
            agenda_placement_reason="Second escalation",
        )

        await repo.save_escalation(escalation1)

        with pytest.raises(BreachAlreadyEscalatedError):
            await repo.save_escalation(escalation2)


class TestSaveAcknowledgment:
    """Tests for save_acknowledgment method."""

    @pytest.fixture
    def repo(self) -> EscalationRepositoryStub:
        """Create a fresh repository for each test."""
        return EscalationRepositoryStub()

    @pytest.fixture
    def sample_acknowledgment(self) -> BreachAcknowledgedEventPayload:
        """Create a sample acknowledgment payload."""
        return BreachAcknowledgedEventPayload(
            acknowledgment_id=uuid4(),
            breach_id=uuid4(),
            acknowledged_by="keeper_001",
            acknowledgment_timestamp=datetime.now(timezone.utc),
            response_choice=ResponseChoice.CORRECTIVE,
        )

    @pytest.mark.asyncio
    async def test_save_acknowledgment_stores_by_breach_id(
        self,
        repo: EscalationRepositoryStub,
        sample_acknowledgment: BreachAcknowledgedEventPayload,
    ) -> None:
        """Test that acknowledgment is stored by breach_id."""
        await repo.save_acknowledgment(sample_acknowledgment)

        assert sample_acknowledgment.breach_id in repo._acknowledgments
        assert (
            repo._acknowledgments[sample_acknowledgment.breach_id]
            == sample_acknowledgment
        )

    @pytest.mark.asyncio
    async def test_save_acknowledgment_raises_on_duplicate(
        self,
        repo: EscalationRepositoryStub,
    ) -> None:
        """Test that saving acknowledgment for same breach_id raises error."""
        from src.domain.errors.escalation import BreachAlreadyAcknowledgedError

        breach_id = uuid4()
        ack1 = BreachAcknowledgedEventPayload(
            acknowledgment_id=uuid4(),
            breach_id=breach_id,
            acknowledged_by="keeper_001",
            acknowledgment_timestamp=datetime.now(timezone.utc),
            response_choice=ResponseChoice.DISMISS,
        )
        ack2 = BreachAcknowledgedEventPayload(
            acknowledgment_id=uuid4(),
            breach_id=breach_id,
            acknowledged_by="keeper_002",
            acknowledgment_timestamp=datetime.now(timezone.utc),
            response_choice=ResponseChoice.CORRECTIVE,
        )

        await repo.save_acknowledgment(ack1)

        with pytest.raises(BreachAlreadyAcknowledgedError):
            await repo.save_acknowledgment(ack2)


class TestGetAcknowledgmentForBreach:
    """Tests for get_acknowledgment_for_breach method."""

    @pytest.fixture
    def repo(self) -> EscalationRepositoryStub:
        """Create a fresh repository for each test."""
        return EscalationRepositoryStub()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self,
        repo: EscalationRepositoryStub,
    ) -> None:
        """Test that None is returned for unknown breach_id."""
        result = await repo.get_acknowledgment_for_breach(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_acknowledgment_when_found(
        self,
        repo: EscalationRepositoryStub,
    ) -> None:
        """Test that acknowledgment is returned when it exists."""
        breach_id = uuid4()
        ack = BreachAcknowledgedEventPayload(
            acknowledgment_id=uuid4(),
            breach_id=breach_id,
            acknowledged_by="keeper_001",
            acknowledgment_timestamp=datetime.now(timezone.utc),
            response_choice=ResponseChoice.ACCEPT,
        )
        await repo.save_acknowledgment(ack)

        result = await repo.get_acknowledgment_for_breach(breach_id)

        assert result == ack


class TestGetEscalationForBreach:
    """Tests for get_escalation_for_breach method."""

    @pytest.fixture
    def repo(self) -> EscalationRepositoryStub:
        """Create a fresh repository for each test."""
        return EscalationRepositoryStub()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self,
        repo: EscalationRepositoryStub,
    ) -> None:
        """Test that None is returned for unknown breach_id."""
        result = await repo.get_escalation_for_breach(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_escalation_when_found(
        self,
        repo: EscalationRepositoryStub,
    ) -> None:
        """Test that escalation is returned when it exists."""
        breach_id = uuid4()
        escalation = EscalationEventPayload(
            escalation_id=uuid4(),
            breach_id=breach_id,
            breach_type=BreachType.WITNESS_COLLUSION,
            escalation_timestamp=datetime.now(timezone.utc),
            days_since_breach=10,
            agenda_placement_reason="FR31 violation",
        )
        await repo.save_escalation(escalation)

        result = await repo.get_escalation_for_breach(breach_id)

        assert result == escalation


class TestListEscalations:
    """Tests for list_escalations method."""

    @pytest.fixture
    def repo(self) -> EscalationRepositoryStub:
        """Create a fresh repository for each test."""
        return EscalationRepositoryStub()

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_empty(
        self,
        repo: EscalationRepositoryStub,
    ) -> None:
        """Test that empty list is returned when no escalations."""
        result = await repo.list_escalations()

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_all_escalations(
        self,
        repo: EscalationRepositoryStub,
    ) -> None:
        """Test that all escalations are returned."""
        escalation1 = EscalationEventPayload(
            escalation_id=uuid4(),
            breach_id=uuid4(),
            breach_type=BreachType.THRESHOLD_VIOLATION,
            escalation_timestamp=datetime.now(timezone.utc),
            days_since_breach=7,
            agenda_placement_reason="First",
        )
        escalation2 = EscalationEventPayload(
            escalation_id=uuid4(),
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            escalation_timestamp=datetime.now(timezone.utc),
            days_since_breach=8,
            agenda_placement_reason="Second",
        )
        await repo.save_escalation(escalation1)
        await repo.save_escalation(escalation2)

        result = await repo.list_escalations()

        assert len(result) == 2
        assert escalation1 in result
        assert escalation2 in result


class TestListAcknowledgments:
    """Tests for list_acknowledgments method."""

    @pytest.fixture
    def repo(self) -> EscalationRepositoryStub:
        """Create a fresh repository for each test."""
        return EscalationRepositoryStub()

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_empty(
        self,
        repo: EscalationRepositoryStub,
    ) -> None:
        """Test that empty list is returned when no acknowledgments."""
        result = await repo.list_acknowledgments()

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_all_acknowledgments(
        self,
        repo: EscalationRepositoryStub,
    ) -> None:
        """Test that all acknowledgments are returned."""
        ack1 = BreachAcknowledgedEventPayload(
            acknowledgment_id=uuid4(),
            breach_id=uuid4(),
            acknowledged_by="keeper_001",
            acknowledgment_timestamp=datetime.now(timezone.utc),
            response_choice=ResponseChoice.CORRECTIVE,
        )
        ack2 = BreachAcknowledgedEventPayload(
            acknowledgment_id=uuid4(),
            breach_id=uuid4(),
            acknowledged_by="keeper_002",
            acknowledgment_timestamp=datetime.now(timezone.utc),
            response_choice=ResponseChoice.DISMISS,
        )
        await repo.save_acknowledgment(ack1)
        await repo.save_acknowledgment(ack2)

        result = await repo.list_acknowledgments()

        assert len(result) == 2
        assert ack1 in result
        assert ack2 in result


class TestProtocolCompliance:
    """Tests to verify protocol compliance."""

    def test_implements_protocol(self) -> None:
        """Test that stub implements the protocol interface."""
        from src.application.ports.escalation_repository import (
            EscalationRepositoryProtocol,
        )

        repo = EscalationRepositoryStub()

        # Check all required methods exist
        assert hasattr(repo, "save_escalation")
        assert hasattr(repo, "save_acknowledgment")
        assert hasattr(repo, "get_acknowledgment_for_breach")
        assert hasattr(repo, "get_escalation_for_breach")
        assert hasattr(repo, "list_escalations")
        assert hasattr(repo, "list_acknowledgments")

        # Verify it can be used as the protocol type
        _: EscalationRepositoryProtocol = repo
