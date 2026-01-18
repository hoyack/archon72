"""Integration tests for Collective Output (Story 2.3, FR11).

Tests the full integration of collective output components:
- CollectiveOutputPayload validation
- CollectiveOutputService with all dependencies
- FR11 compliance verification

Constitutional Constraints:
- FR9: No Preview - outputs committed before viewing
- FR11: Collective outputs attributed to Conclave, not individuals
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def halt_checker_not_halted() -> AsyncMock:
    """Halt checker that reports not halted."""
    checker = AsyncMock()
    checker.is_halted.return_value = False
    checker.get_halt_reason.return_value = None
    return checker


@pytest.fixture
def halt_checker_halted() -> AsyncMock:
    """Halt checker that reports halted."""
    checker = AsyncMock()
    checker.is_halted.return_value = True
    checker.get_halt_reason.return_value = "Test halt"
    return checker


@pytest.fixture
def no_preview_enforcer() -> MagicMock:
    """NoPreviewEnforcer mock."""
    enforcer = MagicMock()
    enforcer.mark_committed.return_value = None
    enforcer.is_committed.return_value = True
    return enforcer


@pytest.fixture
def collective_output_stub():
    """CollectiveOutputStub instance."""
    from src.infrastructure.stubs.collective_output_stub import CollectiveOutputStub

    return CollectiveOutputStub()


@pytest.fixture
def collective_output_service(
    halt_checker_not_halted: AsyncMock,
    collective_output_stub,
    no_preview_enforcer: MagicMock,
):
    """CollectiveOutputService with stub dependencies."""
    from src.application.services.collective_output_service import (
        CollectiveOutputService,
    )

    return CollectiveOutputService(
        halt_checker=halt_checker_not_halted,
        collective_output_port=collective_output_stub,
        no_preview_enforcer=no_preview_enforcer,
    )


class TestCollectiveOutputWith72Agents:
    """Tests for collective output with full Conclave (72 agents)."""

    @pytest.mark.asyncio
    async def test_72_agents_accepted(self, collective_output_service) -> None:
        """FR11: Collective output should accept 72 agents (full Conclave)."""
        from src.domain.events.collective_output import VoteCounts

        result = await collective_output_service.create_collective_output(
            contributing_agents=[f"archon-{i}" for i in range(72)],
            vote_counts=VoteCounts(yes_count=70, no_count=2, abstain_count=0),
            content="Collective decision by full Conclave",
            linked_vote_ids=[uuid4() for _ in range(72)],
        )

        assert result is not None
        assert result.event_sequence is not None
        assert len(result.content_hash) == 64


class TestCollectiveOutputMinimumAgents:
    """Tests for minimum agent requirement (FR11)."""

    @pytest.mark.asyncio
    async def test_2_agents_accepted(self, collective_output_service) -> None:
        """FR11: Collective output should accept minimum 2 agents."""
        from src.domain.events.collective_output import VoteCounts

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=VoteCounts(yes_count=2, no_count=0, abstain_count=0),
            content="Collective decision by 2 agents",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        assert result is not None


class TestSingleAgentRejection:
    """Tests for single-agent rejection (FR11)."""

    @pytest.mark.asyncio
    async def test_single_agent_rejected(self, collective_output_service) -> None:
        """FR11: Single-agent collective output should be rejected."""
        from src.domain.events.collective_output import VoteCounts

        with pytest.raises(ValueError, match="FR11"):
            await collective_output_service.create_collective_output(
                contributing_agents=["archon-1"],  # Only 1 agent!
                vote_counts=VoteCounts(yes_count=1, no_count=0, abstain_count=0),
                content="Invalid single-agent output",
                linked_vote_ids=[uuid4()],
            )


class TestZeroAgentRejection:
    """Tests for zero-agent rejection (FR11)."""

    @pytest.mark.asyncio
    async def test_zero_agents_rejected(self, collective_output_service) -> None:
        """FR11: Zero-agent collective output should be rejected."""
        from src.domain.events.collective_output import VoteCounts

        with pytest.raises(ValueError, match="FR11"):
            await collective_output_service.create_collective_output(
                contributing_agents=[],  # No agents!
                vote_counts=VoteCounts(yes_count=0, no_count=0, abstain_count=0),
                content="Invalid zero-agent output",
                linked_vote_ids=[],
            )


class TestDissentPercentageCalculation:
    """Tests for dissent percentage calculation."""

    @pytest.mark.asyncio
    async def test_even_split_50_percent_dissent(
        self, collective_output_service, collective_output_stub
    ) -> None:
        """Dissent should be 50% for even split."""
        from src.domain.events.collective_output import VoteCounts

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=VoteCounts(yes_count=36, no_count=36, abstain_count=0),
            content="Even split decision",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        # Retrieve and verify dissent
        payload = await collective_output_stub.get_collective_output(result.output_id)
        assert payload is not None
        assert payload.dissent_percentage == 50.0

    @pytest.mark.asyncio
    async def test_unanimous_zero_dissent(
        self, collective_output_service, collective_output_stub
    ) -> None:
        """Dissent should be 0% for unanimous vote."""
        from src.domain.events.collective_output import VoteCounts

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            content="Unanimous decision",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        payload = await collective_output_stub.get_collective_output(result.output_id)
        assert payload is not None
        assert payload.dissent_percentage == 0.0


class TestUnanimousFlag:
    """Tests for unanimous flag calculation."""

    @pytest.mark.asyncio
    async def test_unanimous_true_for_100_percent(
        self, collective_output_service, collective_output_stub
    ) -> None:
        """Unanimous should be True for 100% agreement."""
        from src.domain.events.collective_output import VoteCounts

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            content="Unanimous yes",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        payload = await collective_output_stub.get_collective_output(result.output_id)
        assert payload is not None
        assert payload.unanimous is True

    @pytest.mark.asyncio
    async def test_unanimous_false_for_dissent(
        self, collective_output_service, collective_output_stub
    ) -> None:
        """Unanimous should be False when there's any dissent."""
        from src.domain.events.collective_output import VoteCounts

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=VoteCounts(yes_count=71, no_count=1, abstain_count=0),
            content="One dissenter",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        payload = await collective_output_stub.get_collective_output(result.output_id)
        assert payload is not None
        assert payload.unanimous is False


class TestLinkedVoteEvents:
    """Tests for linked vote event storage and retrieval."""

    @pytest.mark.asyncio
    async def test_linked_vote_ids_stored(
        self, collective_output_service, collective_output_stub
    ) -> None:
        """Linked vote event IDs should be stored and retrievable."""
        from src.domain.events.collective_output import VoteCounts

        vote_id_1 = uuid4()
        vote_id_2 = uuid4()

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=VoteCounts(yes_count=70, no_count=2, abstain_count=0),
            content="Decision with linked votes",
            linked_vote_ids=[vote_id_1, vote_id_2],
        )

        linked = await collective_output_stub.get_linked_vote_events(result.output_id)
        assert vote_id_1 in linked
        assert vote_id_2 in linked


class TestHaltStateBlocks:
    """Tests for halt state blocking collective output creation."""

    @pytest.mark.asyncio
    async def test_halt_blocks_creation(
        self,
        halt_checker_halted: AsyncMock,
        collective_output_stub,
        no_preview_enforcer: MagicMock,
    ) -> None:
        """Halted system should block collective output creation."""
        from src.application.services.collective_output_service import (
            CollectiveOutputService,
        )
        from src.domain.errors import SystemHaltedError
        from src.domain.events.collective_output import VoteCounts

        service = CollectiveOutputService(
            halt_checker=halt_checker_halted,
            collective_output_port=collective_output_stub,
            no_preview_enforcer=no_preview_enforcer,
        )

        with pytest.raises(SystemHaltedError):
            await service.create_collective_output(
                contributing_agents=["archon-1", "archon-2"],
                vote_counts=VoteCounts(yes_count=70, no_count=2, abstain_count=0),
                content="Should not be created",
                linked_vote_ids=[uuid4(), uuid4()],
            )


class TestAuthorTypeCollective:
    """Tests for author_type being COLLECTIVE."""

    @pytest.mark.asyncio
    async def test_author_type_is_collective(
        self, collective_output_service, collective_output_stub
    ) -> None:
        """Created outputs should have author_type COLLECTIVE."""
        from src.domain.events.collective_output import AuthorType, VoteCounts

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=VoteCounts(yes_count=70, no_count=2, abstain_count=0),
            content="Collective decision",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        payload = await collective_output_stub.get_collective_output(result.output_id)
        assert payload is not None
        assert payload.author_type == AuthorType.COLLECTIVE
