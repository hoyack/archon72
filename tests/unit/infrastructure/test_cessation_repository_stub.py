"""Unit tests for CessationRepositoryStub (Story 6.3, FR32).

Tests cover:
- save_consideration() persistence
- save_decision() persistence
- get_active_consideration() query
- get_consideration_by_id() query
- get_decision_for_consideration() query
- list_considerations() query
- clear() reset behavior
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.cessation import (
    CessationConsiderationEventPayload,
    CessationDecision,
    CessationDecisionEventPayload,
)
from src.infrastructure.stubs.cessation_repository_stub import CessationRepositoryStub


@pytest.fixture
def stub() -> CessationRepositoryStub:
    """Create a fresh stub for each test."""
    return CessationRepositoryStub()


@pytest.fixture
def sample_consideration() -> CessationConsiderationEventPayload:
    """Create a sample consideration payload."""
    return CessationConsiderationEventPayload(
        consideration_id=uuid4(),
        trigger_timestamp=datetime.now(timezone.utc),
        breach_count=11,
        window_days=90,
        unacknowledged_breach_ids=(uuid4(), uuid4(), uuid4()),
        agenda_placement_reason="FR32: >10 unacknowledged breaches in 90 days",
    )


@pytest.fixture
def sample_decision(
    sample_consideration: CessationConsiderationEventPayload,
) -> CessationDecisionEventPayload:
    """Create a sample decision payload."""
    return CessationDecisionEventPayload(
        decision_id=uuid4(),
        consideration_id=sample_consideration.consideration_id,
        decision=CessationDecision.DISMISS_CONSIDERATION,
        decision_timestamp=datetime.now(timezone.utc),
        decided_by="Conclave Session 42",
        rationale="Breaches were addressed through remediation",
    )


class TestSaveConsideration:
    """Tests for save_consideration method."""

    @pytest.mark.asyncio
    async def test_saves_consideration(
        self,
        stub: CessationRepositoryStub,
        sample_consideration: CessationConsiderationEventPayload,
    ) -> None:
        """Test consideration is saved."""
        await stub.save_consideration(sample_consideration)

        result = await stub.get_consideration_by_id(
            sample_consideration.consideration_id
        )
        assert result is not None
        assert result.consideration_id == sample_consideration.consideration_id

    @pytest.mark.asyncio
    async def test_save_multiple_considerations(
        self,
        stub: CessationRepositoryStub,
    ) -> None:
        """Test multiple considerations can be saved."""
        c1 = CessationConsiderationEventPayload(
            consideration_id=uuid4(),
            trigger_timestamp=datetime.now(timezone.utc),
            breach_count=11,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="First",
        )
        c2 = CessationConsiderationEventPayload(
            consideration_id=uuid4(),
            trigger_timestamp=datetime.now(timezone.utc),
            breach_count=12,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="Second",
        )

        await stub.save_consideration(c1)
        await stub.save_consideration(c2)

        all_considerations = await stub.list_considerations()
        assert len(all_considerations) == 2


class TestSaveDecision:
    """Tests for save_decision method."""

    @pytest.mark.asyncio
    async def test_saves_decision(
        self,
        stub: CessationRepositoryStub,
        sample_consideration: CessationConsiderationEventPayload,
        sample_decision: CessationDecisionEventPayload,
    ) -> None:
        """Test decision is saved."""
        await stub.save_consideration(sample_consideration)
        await stub.save_decision(sample_decision)

        result = await stub.get_decision_for_consideration(
            sample_consideration.consideration_id
        )
        assert result is not None
        assert result.decision == CessationDecision.DISMISS_CONSIDERATION


class TestGetActiveConsideration:
    """Tests for get_active_consideration method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_empty(
        self,
        stub: CessationRepositoryStub,
    ) -> None:
        """Test returns None when no considerations exist."""
        result = await stub.get_active_consideration()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_consideration_without_decision(
        self,
        stub: CessationRepositoryStub,
        sample_consideration: CessationConsiderationEventPayload,
    ) -> None:
        """Test returns consideration that has no decision."""
        await stub.save_consideration(sample_consideration)

        result = await stub.get_active_consideration()

        assert result is not None
        assert result.consideration_id == sample_consideration.consideration_id

    @pytest.mark.asyncio
    async def test_returns_none_when_decision_exists(
        self,
        stub: CessationRepositoryStub,
        sample_consideration: CessationConsiderationEventPayload,
        sample_decision: CessationDecisionEventPayload,
    ) -> None:
        """Test returns None when consideration has a decision."""
        await stub.save_consideration(sample_consideration)
        await stub.save_decision(sample_decision)

        result = await stub.get_active_consideration()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_latest_active_consideration(
        self,
        stub: CessationRepositoryStub,
    ) -> None:
        """Test returns the most recent active consideration."""
        older = CessationConsiderationEventPayload(
            consideration_id=uuid4(),
            trigger_timestamp=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            breach_count=11,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="Older",
        )
        newer = CessationConsiderationEventPayload(
            consideration_id=uuid4(),
            trigger_timestamp=datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
            breach_count=12,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="Newer",
        )

        await stub.save_consideration(older)
        await stub.save_consideration(newer)

        result = await stub.get_active_consideration()

        # Should return the newer one
        assert result is not None
        assert result.consideration_id == newer.consideration_id


class TestGetConsiderationById:
    """Tests for get_consideration_by_id method."""

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_id(
        self,
        stub: CessationRepositoryStub,
    ) -> None:
        """Test returns None for unknown consideration ID."""
        result = await stub.get_consideration_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_correct_consideration(
        self,
        stub: CessationRepositoryStub,
        sample_consideration: CessationConsiderationEventPayload,
    ) -> None:
        """Test returns correct consideration by ID."""
        await stub.save_consideration(sample_consideration)

        result = await stub.get_consideration_by_id(
            sample_consideration.consideration_id
        )

        assert result is not None
        assert result.breach_count == sample_consideration.breach_count


class TestGetDecisionForConsideration:
    """Tests for get_decision_for_consideration method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_decision(
        self,
        stub: CessationRepositoryStub,
        sample_consideration: CessationConsiderationEventPayload,
    ) -> None:
        """Test returns None when no decision exists."""
        await stub.save_consideration(sample_consideration)

        result = await stub.get_decision_for_consideration(
            sample_consideration.consideration_id
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_decision(
        self,
        stub: CessationRepositoryStub,
        sample_consideration: CessationConsiderationEventPayload,
        sample_decision: CessationDecisionEventPayload,
    ) -> None:
        """Test returns decision when exists."""
        await stub.save_consideration(sample_consideration)
        await stub.save_decision(sample_decision)

        result = await stub.get_decision_for_consideration(
            sample_consideration.consideration_id
        )

        assert result is not None
        assert result.decided_by == "Conclave Session 42"


class TestListConsiderations:
    """Tests for list_considerations method."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_empty(
        self,
        stub: CessationRepositoryStub,
    ) -> None:
        """Test returns empty list when no considerations exist."""
        result = await stub.list_considerations()
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_all_considerations(
        self,
        stub: CessationRepositoryStub,
        sample_consideration: CessationConsiderationEventPayload,
    ) -> None:
        """Test returns all considerations."""
        c2 = CessationConsiderationEventPayload(
            consideration_id=uuid4(),
            trigger_timestamp=datetime.now(timezone.utc),
            breach_count=15,
            window_days=90,
            unacknowledged_breach_ids=(),
            agenda_placement_reason="Second",
        )

        await stub.save_consideration(sample_consideration)
        await stub.save_consideration(c2)

        result = await stub.list_considerations()

        assert len(result) == 2
        ids = {c.consideration_id for c in result}
        assert sample_consideration.consideration_id in ids
        assert c2.consideration_id in ids


class TestClear:
    """Tests for clear method."""

    @pytest.mark.asyncio
    async def test_clear_removes_all_data(
        self,
        stub: CessationRepositoryStub,
        sample_consideration: CessationConsiderationEventPayload,
        sample_decision: CessationDecisionEventPayload,
    ) -> None:
        """Test clear removes all considerations and decisions."""
        await stub.save_consideration(sample_consideration)
        await stub.save_decision(sample_decision)

        stub.clear()

        assert await stub.list_considerations() == []
        assert await stub.get_active_consideration() is None
        assert (
            await stub.get_consideration_by_id(sample_consideration.consideration_id)
            is None
        )
        assert (
            await stub.get_decision_for_consideration(
                sample_consideration.consideration_id
            )
            is None
        )
