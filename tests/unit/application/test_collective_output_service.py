"""Unit tests for CollectiveOutputService (Story 2.3, FR11).

Tests the application service for creating and retrieving collective outputs.

Constitutional Constraints:
- FR9: No Preview - outputs committed before viewing
- FR11: Collective outputs attributed to Conclave, not individuals
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Mock halt checker that reports not halted."""
    checker = AsyncMock()
    checker.is_halted.return_value = False
    checker.get_halt_reason.return_value = None
    return checker


@pytest.fixture
def mock_halted_checker() -> AsyncMock:
    """Mock halt checker that reports halted."""
    checker = AsyncMock()
    checker.is_halted.return_value = True
    checker.get_halt_reason.return_value = "Test halt"
    return checker


@pytest.fixture
def mock_collective_output_port() -> AsyncMock:
    """Mock collective output port."""
    from src.application.ports.collective_output import StoredCollectiveOutput

    port = AsyncMock()
    port.store_collective_output.return_value = StoredCollectiveOutput(
        output_id=uuid4(),
        event_sequence=1,
        content_hash="a" * 64,
        stored_at=datetime.now(timezone.utc),
    )
    port.get_collective_output.return_value = None
    port.get_linked_vote_events.return_value = []
    return port


@pytest.fixture
def mock_no_preview_enforcer() -> MagicMock:
    """Mock NoPreviewEnforcer."""
    enforcer = MagicMock()
    enforcer.mark_committed.return_value = None
    enforcer.is_committed.return_value = True
    enforcer.verify_committed.return_value = True  # Does not raise
    return enforcer


class TestCommittedCollectiveOutput:
    """Tests for CommittedCollectiveOutput result type."""

    def test_dataclass_exists(self) -> None:
        """CommittedCollectiveOutput should be importable."""
        from src.application.services.collective_output_service import (
            CommittedCollectiveOutput,
        )

        assert CommittedCollectiveOutput is not None

    def test_create_committed_output(self) -> None:
        """CommittedCollectiveOutput should accept valid fields."""
        from src.application.services.collective_output_service import (
            CommittedCollectiveOutput,
        )

        committed = CommittedCollectiveOutput(
            output_id=uuid4(),
            event_sequence=42,
            content_hash="a" * 64,
            committed_at=datetime.now(timezone.utc),
        )
        assert committed.event_sequence == 42


class TestCollectiveOutputService:
    """Tests for CollectiveOutputService."""

    def test_service_exists(self) -> None:
        """CollectiveOutputService should be importable."""
        from src.application.services.collective_output_service import (
            CollectiveOutputService,
        )

        assert CollectiveOutputService is not None

    @pytest.mark.asyncio
    async def test_create_collective_output_checks_halt_first(
        self,
        mock_halted_checker: AsyncMock,
        mock_collective_output_port: AsyncMock,
        mock_no_preview_enforcer: MagicMock,
    ) -> None:
        """Should check halt state FIRST (Golden Rule #1)."""
        from src.application.services.collective_output_service import (
            CollectiveOutputService,
        )
        from src.domain.errors import SystemHaltedError
        from src.domain.events.collective_output import VoteCounts

        service = CollectiveOutputService(
            halt_checker=mock_halted_checker,
            collective_output_port=mock_collective_output_port,
            no_preview_enforcer=mock_no_preview_enforcer,
        )

        with pytest.raises(SystemHaltedError):
            await service.create_collective_output(
                contributing_agents=["archon-1", "archon-2"],
                vote_counts=VoteCounts(yes_count=70, no_count=2, abstain_count=0),
                content="Test content",
                linked_vote_ids=[uuid4(), uuid4()],
            )

        # Halt should be checked first
        mock_halted_checker.is_halted.assert_called_once()
        # Port should NOT be called if halted
        mock_collective_output_port.store_collective_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_collective_output_success(
        self,
        mock_halt_checker: AsyncMock,
        mock_collective_output_port: AsyncMock,
        mock_no_preview_enforcer: MagicMock,
    ) -> None:
        """Should create and store collective output successfully."""
        from src.application.services.collective_output_service import (
            CollectiveOutputService,
            CommittedCollectiveOutput,
        )
        from src.domain.events.collective_output import VoteCounts

        service = CollectiveOutputService(
            halt_checker=mock_halt_checker,
            collective_output_port=mock_collective_output_port,
            no_preview_enforcer=mock_no_preview_enforcer,
        )

        result = await service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=VoteCounts(yes_count=70, no_count=2, abstain_count=0),
            content="Test content",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        assert isinstance(result, CommittedCollectiveOutput)
        mock_collective_output_port.store_collective_output.assert_called_once()
        mock_no_preview_enforcer.mark_committed.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_collective_output_rejects_single_agent(
        self,
        mock_halt_checker: AsyncMock,
        mock_collective_output_port: AsyncMock,
        mock_no_preview_enforcer: MagicMock,
    ) -> None:
        """Should reject single-agent collective output (FR11)."""
        from src.application.services.collective_output_service import (
            CollectiveOutputService,
        )
        from src.domain.events.collective_output import VoteCounts

        service = CollectiveOutputService(
            halt_checker=mock_halt_checker,
            collective_output_port=mock_collective_output_port,
            no_preview_enforcer=mock_no_preview_enforcer,
        )

        with pytest.raises(ValueError, match="FR11"):
            await service.create_collective_output(
                contributing_agents=["archon-1"],  # Only 1 agent!
                vote_counts=VoteCounts(yes_count=1, no_count=0, abstain_count=0),
                content="Test content",
                linked_vote_ids=[uuid4()],
            )

    @pytest.mark.asyncio
    async def test_create_collective_output_calculates_dissent(
        self,
        mock_halt_checker: AsyncMock,
        mock_collective_output_port: AsyncMock,
        mock_no_preview_enforcer: MagicMock,
    ) -> None:
        """Should calculate dissent percentage correctly."""
        from src.application.services.collective_output_service import (
            CollectiveOutputService,
        )
        from src.domain.events.collective_output import VoteCounts

        service = CollectiveOutputService(
            halt_checker=mock_halt_checker,
            collective_output_port=mock_collective_output_port,
            no_preview_enforcer=mock_no_preview_enforcer,
        )

        await service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=VoteCounts(
                yes_count=36, no_count=36, abstain_count=0
            ),  # 50% dissent
            content="Test content",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        # Check that the payload passed to port has correct dissent
        call_args = mock_collective_output_port.store_collective_output.call_args
        payload = call_args[0][0]  # First positional arg
        assert payload.dissent_percentage == 50.0

    @pytest.mark.asyncio
    async def test_create_collective_output_calculates_unanimous(
        self,
        mock_halt_checker: AsyncMock,
        mock_collective_output_port: AsyncMock,
        mock_no_preview_enforcer: MagicMock,
    ) -> None:
        """Should set unanimous flag correctly."""
        from src.application.services.collective_output_service import (
            CollectiveOutputService,
        )
        from src.domain.events.collective_output import VoteCounts

        service = CollectiveOutputService(
            halt_checker=mock_halt_checker,
            collective_output_port=mock_collective_output_port,
            no_preview_enforcer=mock_no_preview_enforcer,
        )

        await service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=VoteCounts(
                yes_count=72, no_count=0, abstain_count=0
            ),  # Unanimous
            content="Test content",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        call_args = mock_collective_output_port.store_collective_output.call_args
        payload = call_args[0][0]
        assert payload.unanimous is True


class TestViewableCollectiveOutput:
    """Tests for ViewableCollectiveOutput result type."""

    def test_dataclass_exists(self) -> None:
        """ViewableCollectiveOutput should be importable."""
        from src.application.services.collective_output_service import (
            ViewableCollectiveOutput,
        )

        assert ViewableCollectiveOutput is not None


class TestGetCollectiveOutputForViewing:
    """Tests for get_collective_output_for_viewing method."""

    @pytest.mark.asyncio
    async def test_checks_halt_first(
        self,
        mock_halted_checker: AsyncMock,
        mock_collective_output_port: AsyncMock,
        mock_no_preview_enforcer: MagicMock,
    ) -> None:
        """Should check halt state FIRST."""
        from src.application.services.collective_output_service import (
            CollectiveOutputService,
        )
        from src.domain.errors import SystemHaltedError

        service = CollectiveOutputService(
            halt_checker=mock_halted_checker,
            collective_output_port=mock_collective_output_port,
            no_preview_enforcer=mock_no_preview_enforcer,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_collective_output_for_viewing(
                output_id=uuid4(),
                viewer_id="observer-1",
            )

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(
        self,
        mock_halt_checker: AsyncMock,
        mock_collective_output_port: AsyncMock,
        mock_no_preview_enforcer: MagicMock,
    ) -> None:
        """Should return None if output not found (but was committed)."""
        from src.application.services.collective_output_service import (
            CollectiveOutputService,
        )

        mock_collective_output_port.get_collective_output.return_value = None

        service = CollectiveOutputService(
            halt_checker=mock_halt_checker,
            collective_output_port=mock_collective_output_port,
            no_preview_enforcer=mock_no_preview_enforcer,
        )

        result = await service.get_collective_output_for_viewing(
            output_id=uuid4(),
            viewer_id="observer-1",
        )

        assert result is None
        mock_no_preview_enforcer.verify_committed.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_fr9_for_uncommitted_output(
        self,
        mock_halt_checker: AsyncMock,
        mock_collective_output_port: AsyncMock,
    ) -> None:
        """Should raise FR9ViolationError for uncommitted output (CT-11)."""
        from src.application.services.collective_output_service import (
            CollectiveOutputService,
        )
        from src.domain.errors.no_preview import FR9ViolationError

        # Mock enforcer that raises FR9ViolationError
        mock_enforcer = MagicMock()
        mock_enforcer.verify_committed.side_effect = FR9ViolationError(
            "FR9: Output must be recorded before viewing"
        )

        service = CollectiveOutputService(
            halt_checker=mock_halt_checker,
            collective_output_port=mock_collective_output_port,
            no_preview_enforcer=mock_enforcer,
        )

        with pytest.raises(FR9ViolationError):
            await service.get_collective_output_for_viewing(
                output_id=uuid4(),
                viewer_id="observer-1",
            )

        # Port should NOT be called if FR9 check fails
        mock_collective_output_port.get_collective_output.assert_not_called()
