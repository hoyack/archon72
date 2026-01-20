"""Unit tests for CrewAI Deliberation Adapter (Story 2A.5, FR-11.4).

Tests the CrewAIDeliberationAdapter implementation of PhaseExecutorProtocol.
Uses mocked CrewAI components to ensure deterministic test behavior.

Test Coverage:
- AC1: Implements PhaseExecutorProtocol
- AC2: ASSESS phase with concurrent archon invocations
- AC3: POSITION phase with sequential archon invocations
- AC4: CROSS_EXAMINE phase with max 3 rounds
- AC5: VOTE phase with simultaneous vote collection
- AC6: Blake3 transcript hashing for integrity
- NFR-10.2: 30-second timeout enforcement
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.domain.errors.deliberation import PhaseExecutionError
from src.domain.models.deliberation_context_package import (
    DeliberationContextPackage,
)
from src.domain.models.deliberation_result import PhaseResult
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.adapters.external.crewai_deliberation_adapter import (
    DEFAULT_ARCHON_TIMEOUT_SECONDS,
    MAX_CROSS_EXAMINE_ROUNDS,
    CrewAIDeliberationAdapter,
    _compute_blake3_hash,
    create_crewai_deliberation_adapter,
)

if TYPE_CHECKING:
    pass


# Test fixtures
@pytest.fixture
def archon_ids() -> tuple[UUID, UUID, UUID]:
    """Create 3 archon UUIDs for testing."""
    return (uuid4(), uuid4(), uuid4())


@pytest.fixture
def session_id() -> UUID:
    """Create session UUID for testing."""
    return uuid4()


@pytest.fixture
def petition_id() -> UUID:
    """Create petition UUID for testing."""
    return uuid4()


@pytest.fixture
def mock_profile_repository(archon_ids: tuple[UUID, UUID, UUID]) -> MagicMock:
    """Create mock profile repository with 3 archon profiles."""
    repo = MagicMock()

    def get_by_id(archon_id: UUID) -> MagicMock | None:
        if archon_id not in archon_ids:
            return None

        idx = archon_ids.index(archon_id)
        names = ["Archon Alpha", "Archon Beta", "Archon Gamma"]

        profile = MagicMock()
        profile.id = archon_id
        profile.name = names[idx]
        profile.role = f"Role {idx + 1}"
        profile.goal = f"Goal {idx + 1}"
        profile.backstory = f"Backstory for {names[idx]}"
        profile.llm_config = MagicMock()
        profile.llm_config.provider = "anthropic"
        profile.llm_config.model = "claude-3-sonnet"
        profile.llm_config.temperature = 0.7
        profile.llm_config.max_tokens = 4096
        return profile

    repo.get_by_id = MagicMock(side_effect=get_by_id)
    return repo


@pytest.fixture
def deliberation_session(
    session_id: UUID,
    petition_id: UUID,
    archon_ids: tuple[UUID, UUID, UUID],
) -> DeliberationSession:
    """Create a deliberation session for testing."""
    return DeliberationSession.create(
        session_id=session_id,
        petition_id=petition_id,
        assigned_archons=archon_ids,
    )


@pytest.fixture
def context_package(
    petition_id: UUID,
    session_id: UUID,
    archon_ids: tuple[UUID, UUID, UUID],
) -> DeliberationContextPackage:
    """Create a context package for testing."""
    return DeliberationContextPackage(
        petition_id=petition_id,
        petition_text="This is a test petition requesting action.",
        petition_type="GENERAL",
        co_signer_count=5,
        submitter_id=uuid4(),
        realm="technology",
        submitted_at=datetime.now(timezone.utc),
        session_id=session_id,
        assigned_archons=archon_ids,
    )


@pytest.fixture
def adapter(mock_profile_repository: MagicMock) -> CrewAIDeliberationAdapter:
    """Create adapter with mock profile repository."""
    return CrewAIDeliberationAdapter(
        profile_repository=mock_profile_repository,
        timeout_seconds=30,
        verbose=False,
    )


class TestBlake3Hash:
    """Test Blake3 hashing function."""

    def test_compute_blake3_hash_returns_32_bytes(self) -> None:
        """AC6: Blake3 hash produces 32-byte digest."""
        content = "Test content for hashing"
        result = _compute_blake3_hash(content)
        assert len(result) == 32

    def test_compute_blake3_hash_deterministic(self) -> None:
        """AC6: Same content produces same hash."""
        content = "Deterministic test content"
        hash1 = _compute_blake3_hash(content)
        hash2 = _compute_blake3_hash(content)
        assert hash1 == hash2

    def test_compute_blake3_hash_different_content(self) -> None:
        """AC6: Different content produces different hash."""
        hash1 = _compute_blake3_hash("Content A")
        hash2 = _compute_blake3_hash("Content B")
        assert hash1 != hash2


class TestCrewAIDeliberationAdapterInit:
    """Test adapter initialization."""

    def test_init_with_default_timeout(
        self,
        mock_profile_repository: MagicMock,
    ) -> None:
        """Adapter initializes with default 30s timeout (NFR-10.2)."""
        adapter = CrewAIDeliberationAdapter(
            profile_repository=mock_profile_repository,
        )
        assert adapter._timeout_seconds == DEFAULT_ARCHON_TIMEOUT_SECONDS
        assert adapter._timeout_seconds == 30

    def test_init_with_custom_timeout(
        self,
        mock_profile_repository: MagicMock,
    ) -> None:
        """Adapter accepts custom timeout."""
        adapter = CrewAIDeliberationAdapter(
            profile_repository=mock_profile_repository,
            timeout_seconds=60,
        )
        assert adapter._timeout_seconds == 60

    def test_init_with_verbose(
        self,
        mock_profile_repository: MagicMock,
    ) -> None:
        """Adapter accepts verbose flag."""
        adapter = CrewAIDeliberationAdapter(
            profile_repository=mock_profile_repository,
            verbose=True,
        )
        assert adapter._verbose is True


class TestAssessPhase:
    """Test ASSESS phase execution (AC-2)."""

    @pytest.mark.asyncio
    async def test_execute_assess_returns_phase_result(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
    ) -> None:
        """AC2: ASSESS phase returns valid PhaseResult."""
        with patch.object(
            adapter,
            "_invoke_archon",
            new_callable=AsyncMock,
            return_value="Assessment response from archon",
        ):
            result = adapter.execute_assess(deliberation_session, context_package)

            assert isinstance(result, PhaseResult)
            assert result.phase == DeliberationPhase.ASSESS
            assert len(result.transcript_hash) == 32  # Blake3
            assert len(result.participants) == 3

    @pytest.mark.asyncio
    async def test_execute_assess_concurrent_invocations(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
        archon_ids: tuple[UUID, UUID, UUID],
    ) -> None:
        """AC2: All archons are invoked during ASSESS."""
        invoked_archons: list[UUID] = []

        async def track_invocation(archon_id: UUID, prompt: str, phase: DeliberationPhase) -> str:
            invoked_archons.append(archon_id)
            return f"Assessment from {archon_id}"

        with patch.object(
            adapter,
            "_invoke_archon",
            side_effect=track_invocation,
        ):
            adapter.execute_assess(deliberation_session, context_package)

            # All 3 archons should be invoked
            assert len(invoked_archons) == 3
            for archon_id in archon_ids:
                assert archon_id in invoked_archons

    @pytest.mark.asyncio
    async def test_execute_assess_transcript_contains_assessments(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
    ) -> None:
        """AC2: Transcript includes all archon assessments."""
        with patch.object(
            adapter,
            "_invoke_archon",
            new_callable=AsyncMock,
            return_value="This is my assessment of the petition.",
        ):
            result = adapter.execute_assess(deliberation_session, context_package)

            assert "ASSESS PHASE" in result.transcript
            assert "This is my assessment of the petition." in result.transcript

    @pytest.mark.asyncio
    async def test_execute_assess_metadata_includes_count(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
    ) -> None:
        """AC2: Phase metadata includes assessments count."""
        with patch.object(
            adapter,
            "_invoke_archon",
            new_callable=AsyncMock,
            return_value="Assessment",
        ):
            result = adapter.execute_assess(deliberation_session, context_package)

            assert result.get_metadata("assessments_completed") == 3
            assert result.get_metadata("petition_type") == "GENERAL"


class TestPositionPhase:
    """Test POSITION phase execution (AC-3)."""

    @pytest.mark.asyncio
    async def test_execute_position_returns_phase_result(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
    ) -> None:
        """AC3: POSITION phase returns valid PhaseResult."""
        assess_result = MagicMock(spec=PhaseResult)
        assess_result.phase = DeliberationPhase.ASSESS
        assess_result.transcript = "ASSESS transcript"

        with patch.object(
            adapter,
            "_invoke_archon",
            new_callable=AsyncMock,
            return_value="VOTE: ACKNOWLEDGE\nRationale here.",
        ):
            result = adapter.execute_position(
                deliberation_session, context_package, assess_result
            )

            assert isinstance(result, PhaseResult)
            assert result.phase == DeliberationPhase.POSITION
            assert len(result.transcript_hash) == 32

    @pytest.mark.asyncio
    async def test_execute_position_sequential_invocations(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
        archon_ids: tuple[UUID, UUID, UUID],
    ) -> None:
        """AC3: Archons are invoked sequentially."""
        invocation_order: list[UUID] = []

        async def track_invocation(archon_id: UUID, prompt: str, phase: DeliberationPhase) -> str:
            invocation_order.append(archon_id)
            return f"Position from {archon_id}"

        assess_result = MagicMock(spec=PhaseResult)
        assess_result.phase = DeliberationPhase.ASSESS

        with patch.object(
            adapter,
            "_invoke_archon",
            side_effect=track_invocation,
        ):
            adapter.execute_position(
                deliberation_session, context_package, assess_result
            )

            # Order should match assigned_archons order
            assert invocation_order == list(archon_ids)


class TestCrossExaminePhase:
    """Test CROSS_EXAMINE phase execution (AC-4)."""

    @pytest.mark.asyncio
    async def test_execute_cross_examine_returns_phase_result(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
    ) -> None:
        """AC4: CROSS_EXAMINE phase returns valid PhaseResult."""
        position_result = MagicMock(spec=PhaseResult)
        position_result.phase = DeliberationPhase.POSITION
        position_result.get_metadata = MagicMock(return_value=[])

        with patch.object(
            adapter,
            "_invoke_archon",
            new_callable=AsyncMock,
            return_value="NO CHALLENGE",
        ):
            result = adapter.execute_cross_examine(
                deliberation_session, context_package, position_result
            )

            assert isinstance(result, PhaseResult)
            assert result.phase == DeliberationPhase.CROSS_EXAMINE
            assert len(result.transcript_hash) == 32

    @pytest.mark.asyncio
    async def test_execute_cross_examine_max_rounds(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
    ) -> None:
        """AC4: Cross-examination limited to 3 rounds max."""
        position_result = MagicMock(spec=PhaseResult)
        position_result.phase = DeliberationPhase.POSITION
        position_result.get_metadata = MagicMock(return_value=[])

        invocation_count = 0

        async def count_invocations(archon_id: UUID, prompt: str, phase: DeliberationPhase) -> str:
            nonlocal invocation_count
            invocation_count += 1
            # Always challenge to force max rounds
            return "I challenge this position."

        with patch.object(
            adapter,
            "_invoke_archon",
            side_effect=count_invocations,
        ):
            result = adapter.execute_cross_examine(
                deliberation_session, context_package, position_result
            )

            # 3 archons * 3 rounds = 9 invocations max
            assert invocation_count <= 3 * MAX_CROSS_EXAMINE_ROUNDS
            assert result.get_metadata("max_rounds") == MAX_CROSS_EXAMINE_ROUNDS

    @pytest.mark.asyncio
    async def test_execute_cross_examine_stops_on_no_challenge(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
    ) -> None:
        """AC4: Phase ends when no challenges raised."""
        position_result = MagicMock(spec=PhaseResult)
        position_result.phase = DeliberationPhase.POSITION
        position_result.get_metadata = MagicMock(return_value=[])

        with patch.object(
            adapter,
            "_invoke_archon",
            new_callable=AsyncMock,
            return_value="NO CHALLENGE - I accept the positions.",
        ):
            result = adapter.execute_cross_examine(
                deliberation_session, context_package, position_result
            )

            assert result.get_metadata("rounds_completed") == 1
            assert result.get_metadata("challenges_raised") == 0


class TestVotePhase:
    """Test VOTE phase execution (AC-5)."""

    @pytest.mark.asyncio
    async def test_execute_vote_returns_phase_result(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
    ) -> None:
        """AC5: VOTE phase returns valid PhaseResult."""
        cross_examine_result = MagicMock(spec=PhaseResult)
        cross_examine_result.phase = DeliberationPhase.CROSS_EXAMINE
        cross_examine_result.transcript = "Cross-examine transcript"

        with patch.object(
            adapter,
            "_invoke_archon",
            new_callable=AsyncMock,
            return_value="VOTE: ACKNOWLEDGE\nFinal reasoning here.",
        ):
            result = adapter.execute_vote(
                deliberation_session, context_package, cross_examine_result
            )

            assert isinstance(result, PhaseResult)
            assert result.phase == DeliberationPhase.VOTE
            assert len(result.transcript_hash) == 32

    @pytest.mark.asyncio
    async def test_execute_vote_extracts_votes(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
        archon_ids: tuple[UUID, UUID, UUID],
    ) -> None:
        """AC5: Votes are extracted from archon responses."""
        cross_examine_result = MagicMock(spec=PhaseResult)
        cross_examine_result.phase = DeliberationPhase.CROSS_EXAMINE
        cross_examine_result.transcript = "Cross-examine transcript"

        responses = [
            "VOTE: ACKNOWLEDGE\nI believe acknowledgment is appropriate.",
            "VOTE: ACKNOWLEDGE\nConcur with acknowledgment.",
            "VOTE: REFER\nI recommend referral to Knight.",
        ]
        response_idx = 0

        async def return_votes(archon_id: UUID, prompt: str, phase: DeliberationPhase) -> str:
            nonlocal response_idx
            response = responses[response_idx]
            response_idx += 1
            return response

        with patch.object(
            adapter,
            "_invoke_archon",
            side_effect=return_votes,
        ):
            result = adapter.execute_vote(
                deliberation_session, context_package, cross_examine_result
            )

            votes = result.get_metadata("votes")
            assert len(votes) == 3
            assert votes[archon_ids[0]] == DeliberationOutcome.ACKNOWLEDGE
            assert votes[archon_ids[1]] == DeliberationOutcome.ACKNOWLEDGE
            assert votes[archon_ids[2]] == DeliberationOutcome.REFER

    @pytest.mark.asyncio
    async def test_execute_vote_includes_vote_counts(
        self,
        adapter: CrewAIDeliberationAdapter,
        deliberation_session: DeliberationSession,
        context_package: DeliberationContextPackage,
    ) -> None:
        """AC5: Vote counts are included in metadata."""
        cross_examine_result = MagicMock(spec=PhaseResult)
        cross_examine_result.phase = DeliberationPhase.CROSS_EXAMINE
        cross_examine_result.transcript = "Cross-examine transcript"

        with patch.object(
            adapter,
            "_invoke_archon",
            new_callable=AsyncMock,
            return_value="VOTE: ESCALATE\nEscalation needed.",
        ):
            result = adapter.execute_vote(
                deliberation_session, context_package, cross_examine_result
            )

            vote_counts = result.get_metadata("vote_counts")
            assert vote_counts["ESCALATE"] == 3


class TestVoteParsing:
    """Test vote parsing from archon responses."""

    def test_parse_vote_acknowledge(self, adapter: CrewAIDeliberationAdapter) -> None:
        """Parse ACKNOWLEDGE vote."""
        response = "VOTE: ACKNOWLEDGE\nReasoning..."
        assert adapter._parse_vote(response) == DeliberationOutcome.ACKNOWLEDGE

    def test_parse_vote_refer(self, adapter: CrewAIDeliberationAdapter) -> None:
        """Parse REFER vote."""
        response = "VOTE: REFER\nShould be referred."
        assert adapter._parse_vote(response) == DeliberationOutcome.REFER

    def test_parse_vote_escalate(self, adapter: CrewAIDeliberationAdapter) -> None:
        """Parse ESCALATE vote."""
        response = "VOTE: ESCALATE\nNeeds escalation."
        assert adapter._parse_vote(response) == DeliberationOutcome.ESCALATE

    def test_parse_vote_flexible_format(self, adapter: CrewAIDeliberationAdapter) -> None:
        """Parse vote with flexible formatting."""
        assert adapter._parse_vote("VOTE:ACKNOWLEDGE") == DeliberationOutcome.ACKNOWLEDGE
        assert adapter._parse_vote("vote: refer") == DeliberationOutcome.REFER
        assert adapter._parse_vote("My VOTE is to ESCALATE") == DeliberationOutcome.ESCALATE

    def test_parse_vote_invalid_returns_none(self, adapter: CrewAIDeliberationAdapter) -> None:
        """Invalid vote format returns None."""
        assert adapter._parse_vote("I think we should do something") is None
        assert adapter._parse_vote("") is None


class TestTimeoutHandling:
    """Test timeout enforcement (NFR-10.2)."""

    @pytest.mark.asyncio
    async def test_invoke_archon_timeout_raises_error(
        self,
        adapter: CrewAIDeliberationAdapter,
        archon_ids: tuple[UUID, UUID, UUID],
    ) -> None:
        """NFR-10.2: Timeout raises PhaseExecutionError."""
        with patch("asyncio.wait_for", side_effect=TimeoutError):
            with pytest.raises(PhaseExecutionError) as exc_info:
                await adapter._invoke_archon(
                    archon_ids[0],
                    "Test prompt",
                    DeliberationPhase.ASSESS,
                )

            assert "timed out" in str(exc_info.value).lower()
            assert exc_info.value.archon_id == archon_ids[0]


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_archon_not_found_raises_error(
        self,
        adapter: CrewAIDeliberationAdapter,
    ) -> None:
        """PhaseExecutionError when archon not found."""
        unknown_id = uuid4()
        with pytest.raises(PhaseExecutionError) as exc_info:
            adapter._get_archon_profile(unknown_id)

        assert "not found" in str(exc_info.value).lower()
        assert exc_info.value.archon_id == unknown_id


class TestFactoryFunction:
    """Test factory function."""

    def test_create_crewai_deliberation_adapter_default(self) -> None:
        """Factory creates adapter with defaults."""
        with patch(
            "src.infrastructure.adapters.external.crewai_deliberation_adapter.create_archon_profile_repository"
        ) as mock_create:
            mock_repo = MagicMock()
            mock_create.return_value = mock_repo

            adapter = create_crewai_deliberation_adapter()

            assert isinstance(adapter, CrewAIDeliberationAdapter)
            assert adapter._timeout_seconds == DEFAULT_ARCHON_TIMEOUT_SECONDS

    def test_create_crewai_deliberation_adapter_custom_repo(
        self,
        mock_profile_repository: MagicMock,
    ) -> None:
        """Factory accepts custom repository."""
        adapter = create_crewai_deliberation_adapter(
            profile_repository=mock_profile_repository,
            timeout_seconds=60,
            verbose=True,
        )

        assert adapter._profile_repo == mock_profile_repository
        assert adapter._timeout_seconds == 60
        assert adapter._verbose is True
