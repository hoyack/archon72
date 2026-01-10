"""Integration tests for FR12 Dissent Tracking (Story 2.4).

Tests the complete dissent tracking flow including:
- Dissent percentage calculation
- UnanimousVoteEvent creation
- Rolling averages and alerting
- HALT state compliance

Test categories:
- Dissent calculation integration
- Unanimous vote event creation
- Dissent health metrics
- Alert triggering
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.collective_output_service import (
    CollectiveOutputService,
)
from src.application.services.dissent_health_service import (
    DissentHealthService,
)
from src.domain.events.collective_output import VoteCounts
from src.domain.events.unanimous_vote import VoteOutcome
from src.domain.services.no_preview_enforcer import NoPreviewEnforcer
from src.infrastructure.stubs.collective_output_stub import CollectiveOutputStub
from src.infrastructure.stubs.dissent_metrics_stub import DissentMetricsStub
from src.infrastructure.stubs.unanimous_vote_stub import UnanimousVoteStub


class MockHaltChecker:
    """Mock HaltChecker for integration tests."""

    def __init__(self, is_halted: bool = False, reason: str = "Test halt") -> None:
        self._is_halted = is_halted
        self._reason = reason

    async def is_halted(self) -> bool:
        return self._is_halted

    async def get_halt_reason(self) -> str:
        return self._reason

    async def check_halted(self) -> None:
        if self._is_halted:
            from src.domain.errors.writer import SystemHaltedError
            raise SystemHaltedError(f"System is halted: {self._reason}")


@pytest.fixture
def halt_checker() -> MockHaltChecker:
    return MockHaltChecker(is_halted=False)


@pytest.fixture
def collective_output_stub() -> CollectiveOutputStub:
    return CollectiveOutputStub()


@pytest.fixture
def unanimous_vote_stub() -> UnanimousVoteStub:
    return UnanimousVoteStub()


@pytest.fixture
def dissent_metrics_stub() -> DissentMetricsStub:
    return DissentMetricsStub()


@pytest.fixture
def no_preview_enforcer() -> NoPreviewEnforcer:
    return NoPreviewEnforcer()


@pytest.fixture
def dissent_health_service(
    halt_checker: MockHaltChecker,
    dissent_metrics_stub: DissentMetricsStub,
) -> DissentHealthService:
    return DissentHealthService(
        halt_checker=halt_checker,  # type: ignore[arg-type]
        metrics_port=dissent_metrics_stub,  # type: ignore[arg-type]
    )


@pytest.fixture
def collective_output_service(
    halt_checker: MockHaltChecker,
    collective_output_stub: CollectiveOutputStub,
    no_preview_enforcer: NoPreviewEnforcer,
    unanimous_vote_stub: UnanimousVoteStub,
    dissent_health_service: DissentHealthService,
) -> CollectiveOutputService:
    return CollectiveOutputService(
        halt_checker=halt_checker,  # type: ignore[arg-type]
        collective_output_port=collective_output_stub,  # type: ignore[arg-type]
        no_preview_enforcer=no_preview_enforcer,
        unanimous_vote_port=unanimous_vote_stub,  # type: ignore[arg-type]
        dissent_health_service=dissent_health_service,
    )


class TestDissentCalculationIntegration:
    """Integration tests for dissent percentage calculation."""

    @pytest.mark.asyncio
    async def test_dissent_percentage_for_split_votes(
        self,
        collective_output_service: CollectiveOutputService,
        dissent_metrics_stub: DissentMetricsStub,
    ) -> None:
        """Dissent percentage is calculated correctly for split votes."""
        # 36 yes, 36 no = 50% dissent (maximum possible)
        vote_counts = VoteCounts(yes_count=36, no_count=36, abstain_count=0)

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=vote_counts,
            content="Split vote output",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        # Check dissent was recorded
        history = await dissent_metrics_stub.get_dissent_history(days=30)
        assert len(history) == 1
        assert history[0].dissent_percentage == 50.0

    @pytest.mark.asyncio
    async def test_dissent_percentage_for_majority_vote(
        self,
        collective_output_service: CollectiveOutputService,
        dissent_metrics_stub: DissentMetricsStub,
    ) -> None:
        """Dissent percentage is calculated correctly for majority votes."""
        # 70 yes, 2 no = ~2.78% dissent
        vote_counts = VoteCounts(yes_count=70, no_count=2, abstain_count=0)

        await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=vote_counts,
            content="Majority vote output",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        history = await dissent_metrics_stub.get_dissent_history(days=30)
        assert len(history) == 1
        assert 2.7 < history[0].dissent_percentage < 2.8


class TestUnanimousVoteEventCreation:
    """Integration tests for UnanimousVoteEvent creation."""

    @pytest.mark.asyncio
    async def test_unanimous_yes_vote_creates_event(
        self,
        collective_output_service: CollectiveOutputService,
        unanimous_vote_stub: UnanimousVoteStub,
    ) -> None:
        """Unanimous YES vote creates UnanimousVoteEvent with YES_UNANIMOUS outcome."""
        vote_counts = VoteCounts(yes_count=72, no_count=0, abstain_count=0)

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=vote_counts,
            content="Unanimous yes output",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        # Check unanimous vote event was created
        votes = await unanimous_vote_stub.get_unanimous_votes_for_output(result.output_id)
        assert len(votes) == 1
        assert votes[0].outcome == VoteOutcome.YES_UNANIMOUS
        assert votes[0].voter_count == 72

    @pytest.mark.asyncio
    async def test_unanimous_no_vote_creates_event(
        self,
        collective_output_service: CollectiveOutputService,
        unanimous_vote_stub: UnanimousVoteStub,
    ) -> None:
        """Unanimous NO vote creates UnanimousVoteEvent with NO_UNANIMOUS outcome."""
        vote_counts = VoteCounts(yes_count=0, no_count=72, abstain_count=0)

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=vote_counts,
            content="Unanimous no output",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        votes = await unanimous_vote_stub.get_unanimous_votes_for_output(result.output_id)
        assert len(votes) == 1
        assert votes[0].outcome == VoteOutcome.NO_UNANIMOUS

    @pytest.mark.asyncio
    async def test_unanimous_abstain_vote_creates_event(
        self,
        collective_output_service: CollectiveOutputService,
        unanimous_vote_stub: UnanimousVoteStub,
    ) -> None:
        """Unanimous ABSTAIN vote creates UnanimousVoteEvent with ABSTAIN_UNANIMOUS outcome."""
        vote_counts = VoteCounts(yes_count=0, no_count=0, abstain_count=72)

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=vote_counts,
            content="Unanimous abstain output",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        votes = await unanimous_vote_stub.get_unanimous_votes_for_output(result.output_id)
        assert len(votes) == 1
        assert votes[0].outcome == VoteOutcome.ABSTAIN_UNANIMOUS

    @pytest.mark.asyncio
    async def test_non_unanimous_vote_does_not_create_event(
        self,
        collective_output_service: CollectiveOutputService,
        unanimous_vote_stub: UnanimousVoteStub,
    ) -> None:
        """Non-unanimous vote does NOT create UnanimousVoteEvent."""
        vote_counts = VoteCounts(yes_count=70, no_count=2, abstain_count=0)

        result = await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=vote_counts,
            content="Non-unanimous output",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        votes = await unanimous_vote_stub.get_unanimous_votes_for_output(result.output_id)
        assert len(votes) == 0


class TestDissentHealthMetrics:
    """Integration tests for dissent health metrics and alerting."""

    @pytest.mark.asyncio
    async def test_rolling_average_calculated_correctly(
        self,
        dissent_health_service: DissentHealthService,
        dissent_metrics_stub: DissentMetricsStub,
    ) -> None:
        """Rolling average is calculated correctly over 30 days."""
        now = datetime.now(timezone.utc)

        # Record several dissent values
        await dissent_metrics_stub.record_vote_dissent(uuid4(), 10.0, now)
        await dissent_metrics_stub.record_vote_dissent(uuid4(), 20.0, now)
        await dissent_metrics_stub.record_vote_dissent(uuid4(), 30.0, now)

        status = await dissent_health_service.get_health_status()

        assert status.rolling_average == 20.0  # (10 + 20 + 30) / 3
        assert status.record_count == 3
        assert status.period_days == 30

    @pytest.mark.asyncio
    async def test_alert_fires_when_dissent_below_10_percent(
        self,
        dissent_health_service: DissentHealthService,
        dissent_metrics_stub: DissentMetricsStub,
    ) -> None:
        """Alert fires when rolling average dissent drops below 10%."""
        now = datetime.now(timezone.utc)

        # Record low dissent values (all below 10%)
        await dissent_metrics_stub.record_vote_dissent(uuid4(), 5.0, now)
        await dissent_metrics_stub.record_vote_dissent(uuid4(), 7.0, now)
        await dissent_metrics_stub.record_vote_dissent(uuid4(), 8.0, now)

        alert = await dissent_health_service.check_alert_condition()

        assert alert is not None
        assert alert.threshold == 10.0
        assert alert.actual_average < 10.0
        assert alert.alert_type == "DISSENT_BELOW_THRESHOLD"

    @pytest.mark.asyncio
    async def test_no_alert_when_dissent_healthy(
        self,
        dissent_health_service: DissentHealthService,
        dissent_metrics_stub: DissentMetricsStub,
    ) -> None:
        """No alert when dissent is above threshold (healthy)."""
        now = datetime.now(timezone.utc)

        # Record healthy dissent values (above 10%)
        await dissent_metrics_stub.record_vote_dissent(uuid4(), 15.0, now)
        await dissent_metrics_stub.record_vote_dissent(uuid4(), 20.0, now)
        await dissent_metrics_stub.record_vote_dissent(uuid4(), 25.0, now)

        alert = await dissent_health_service.check_alert_condition()

        assert alert is None


class TestHaltStateCompliance:
    """Integration tests for HALT state compliance."""

    @pytest.mark.asyncio
    async def test_halt_state_blocks_dissent_recording(
        self,
        dissent_metrics_stub: DissentMetricsStub,
    ) -> None:
        """HALT state blocks dissent recording (Golden Rule #1)."""
        halted_checker = MockHaltChecker(is_halted=True, reason="Test halt")
        service = DissentHealthService(
            halt_checker=halted_checker,  # type: ignore[arg-type]
            metrics_port=dissent_metrics_stub,  # type: ignore[arg-type]
        )

        from src.domain.errors.writer import SystemHaltedError

        with pytest.raises(SystemHaltedError):
            await service.record_dissent(uuid4(), 15.0)

        # Verify no record was created
        history = await dissent_metrics_stub.get_dissent_history(days=30)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_halt_state_blocks_collective_output_creation(
        self,
        collective_output_stub: CollectiveOutputStub,
        no_preview_enforcer: NoPreviewEnforcer,
        unanimous_vote_stub: UnanimousVoteStub,
        dissent_metrics_stub: DissentMetricsStub,
    ) -> None:
        """HALT state blocks collective output creation."""
        halted_checker = MockHaltChecker(is_halted=True, reason="Test halt")
        dissent_service = DissentHealthService(
            halt_checker=halted_checker,  # type: ignore[arg-type]
            metrics_port=dissent_metrics_stub,  # type: ignore[arg-type]
        )
        service = CollectiveOutputService(
            halt_checker=halted_checker,  # type: ignore[arg-type]
            collective_output_port=collective_output_stub,  # type: ignore[arg-type]
            no_preview_enforcer=no_preview_enforcer,
            unanimous_vote_port=unanimous_vote_stub,  # type: ignore[arg-type]
            dissent_health_service=dissent_service,
        )

        from src.domain.errors.writer import SystemHaltedError

        with pytest.raises(SystemHaltedError):
            await service.create_collective_output(
                contributing_agents=["archon-1", "archon-2"],
                vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
                content="Test content",
                linked_vote_ids=[uuid4(), uuid4()],
            )


class TestDissentRecordingForAllOutputs:
    """Integration tests verifying dissent is recorded for every collective output."""

    @pytest.mark.asyncio
    async def test_dissent_recorded_for_unanimous_output(
        self,
        collective_output_service: CollectiveOutputService,
        dissent_metrics_stub: DissentMetricsStub,
    ) -> None:
        """Dissent is recorded even for unanimous votes (0% dissent)."""
        vote_counts = VoteCounts(yes_count=72, no_count=0, abstain_count=0)

        await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=vote_counts,
            content="Unanimous output",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        history = await dissent_metrics_stub.get_dissent_history(days=30)
        assert len(history) == 1
        assert history[0].dissent_percentage == 0.0

    @pytest.mark.asyncio
    async def test_dissent_recorded_for_non_unanimous_output(
        self,
        collective_output_service: CollectiveOutputService,
        dissent_metrics_stub: DissentMetricsStub,
    ) -> None:
        """Dissent is recorded for non-unanimous votes."""
        vote_counts = VoteCounts(yes_count=70, no_count=2, abstain_count=0)

        await collective_output_service.create_collective_output(
            contributing_agents=["archon-1", "archon-2"],
            vote_counts=vote_counts,
            content="Non-unanimous output",
            linked_vote_ids=[uuid4(), uuid4()],
        )

        history = await dissent_metrics_stub.get_dissent_history(days=30)
        assert len(history) == 1
        assert history[0].dissent_percentage > 0.0
