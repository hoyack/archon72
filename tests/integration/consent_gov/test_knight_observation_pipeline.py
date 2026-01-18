"""Knight observation pipeline tests using real Conclave event data.

These tests validate the Knight Observer service using governance events
created from real Conclave session data.

Tests:
- Observing speech events
- Classifying event types
- Gap detection
- Observation metrics
- Latency tracking

Constitutional References:
- NFR-OBS-01: Knight observes all branch actions within ≤1 second
- NFR-AUDIT-01: All branch actions logged with sufficient detail
- FR33: Knight can observe and record across all branches
- FR41: Knight can observe Prince Panel conduct
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.witness_statement import WitnessStatement

# =============================================================================
# Mock Fixtures for Knight Observer Dependencies
# =============================================================================


@pytest.fixture
def mock_witness_port():
    """Mock witness port for recording statements."""
    mock = AsyncMock()
    mock.record_statement = AsyncMock()
    return mock


@pytest.fixture
def mock_witness_statement_factory():
    """Mock factory for creating witness statements."""
    from src.domain.governance.witness.observation_content import ObservationContent

    def _create_statement(
        observation_type: ObservationType,
        observed_event,
        what: str,
        where: str,
    ) -> WitnessStatement:
        return WitnessStatement(
            statement_id=uuid4(),
            observation_type=observation_type,
            content=ObservationContent(
                what=what,
                when=observed_event.timestamp,
                who=(observed_event.actor_id,),
                where=where,
                event_type=observed_event.event_type,
                event_id=observed_event.event_id,
            ),
            observed_at=datetime.now(timezone.utc),
            hash_chain_position=0,
        )

    mock = MagicMock()
    mock.create_statement = _create_statement
    return mock


@pytest.fixture
def mock_ledger_port(debate_entries: list, make_governance_event):
    """Mock ledger port with events from debate entries."""
    from dataclasses import dataclass as dc

    # Create persisted events from debate entries
    events_to_serve = []
    for i, entry in enumerate(debate_entries[:5]):
        event = make_governance_event(entry)

        @dc
        class PersistedEvent:
            event_id: UUID
            event_type: str
            timestamp: datetime
            actor_id: str
            sequence: int

        events_to_serve.append(
            PersistedEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                actor_id=event.actor_id,
                sequence=i + 1,
            )
        )

    mock = AsyncMock()
    mock.read_events = AsyncMock(return_value=events_to_serve)
    return mock


# =============================================================================
# Test Classes
# =============================================================================


class TestKnightObserverEventClassification:
    """Tests for Knight observer event classification."""

    @pytest.mark.asyncio
    async def test_classify_executive_branch_event(
        self,
        fake_time_authority,
    ) -> None:
        """Executive branch events are correctly classified."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        # Create minimal service to test classification method
        service = KnightObserverService(
            ledger=AsyncMock(),
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
        )

        @dataclass
        class MockEvent:
            event_type: str

        event = MockEvent(event_type="executive.speech.delivered")
        observation_type = service._classify_event(event)

        assert observation_type == ObservationType.BRANCH_ACTION

    @pytest.mark.asyncio
    async def test_classify_violation_event(
        self,
        fake_time_authority,
    ) -> None:
        """Violation events are classified as potential violations."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        service = KnightObserverService(
            ledger=AsyncMock(),
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
        )

        @dataclass
        class MockEvent:
            event_type: str

        event = MockEvent(event_type="constitutional.violation.detected")
        observation_type = service._classify_event(event)

        assert observation_type == ObservationType.POTENTIAL_VIOLATION

    @pytest.mark.asyncio
    async def test_classify_timing_event(
        self,
        fake_time_authority,
    ) -> None:
        """Timeout events are classified as timing anomalies."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        service = KnightObserverService(
            ledger=AsyncMock(),
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
        )

        @dataclass
        class MockEvent:
            event_type: str

        event = MockEvent(event_type="consent.task.timeout")
        observation_type = service._classify_event(event)

        assert observation_type == ObservationType.TIMING_ANOMALY


class TestKnightObserverBranchDetermination:
    """Tests for branch determination from event types."""

    @pytest.mark.asyncio
    async def test_determine_executive_branch(
        self,
        fake_time_authority,
    ) -> None:
        """Executive branch events correctly identified."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        service = KnightObserverService(
            ledger=AsyncMock(),
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
        )

        @dataclass
        class MockEvent:
            event_type: str

        event = MockEvent(event_type="executive.motion.passed")
        branch = service._determine_branch(event)

        assert branch == "executive"

    @pytest.mark.asyncio
    async def test_determine_judicial_branch(
        self,
        fake_time_authority,
    ) -> None:
        """Judicial branch events correctly identified."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        service = KnightObserverService(
            ledger=AsyncMock(),
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
        )

        @dataclass
        class MockEvent:
            event_type: str

        event = MockEvent(event_type="judicial.panel.convened")
        branch = service._determine_branch(event)

        assert branch == "judicial"

    @pytest.mark.asyncio
    async def test_determine_witness_branch(
        self,
        fake_time_authority,
    ) -> None:
        """Witness branch events correctly identified."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        service = KnightObserverService(
            ledger=AsyncMock(),
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
        )

        @dataclass
        class MockEvent:
            event_type: str

        event = MockEvent(event_type="witness.statement.recorded")
        branch = service._determine_branch(event)

        assert branch == "witness"


class TestKnightObserverGapDetection:
    """Tests for sequence gap detection."""

    @pytest.mark.asyncio
    async def test_detect_gap_in_sequence(
        self,
        fake_time_authority,
    ) -> None:
        """Gap in sequence numbers is detected."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        service = KnightObserverService(
            ledger=AsyncMock(),
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
        )

        # Set last observed sequence
        service._last_observed_sequence = 5

        # Check for gap (sequence 10 when expecting 6)
        gap = service._check_for_gap(10)

        assert gap is not None
        assert gap.expected_sequence == 6
        assert gap.actual_sequence == 10
        assert gap.missing_count == 4

    @pytest.mark.asyncio
    async def test_no_gap_for_consecutive_sequence(
        self,
        fake_time_authority,
    ) -> None:
        """No gap detected for consecutive sequence numbers."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        service = KnightObserverService(
            ledger=AsyncMock(),
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
        )

        service._last_observed_sequence = 5

        # Check next expected sequence (6)
        gap = service._check_for_gap(6)

        assert gap is None


class TestKnightObserverEventDescription:
    """Tests for event description generation."""

    @pytest.mark.asyncio
    async def test_describe_speech_event(
        self,
        debate_entries: list,
        make_governance_event,
        fake_time_authority,
    ) -> None:
        """Speech events are described factually."""
        if not debate_entries:
            pytest.skip("No debate entries")

        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        service = KnightObserverService(
            ledger=AsyncMock(),
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
        )

        entry = debate_entries[0]
        event = make_governance_event(entry)

        @dataclass
        class MockPersistedEvent:
            event_type: str
            sequence: int
            actor_id: str

        persisted = MockPersistedEvent(
            event_type=event.event_type,
            sequence=1,
            actor_id=event.actor_id,
        )

        description = service._describe_event(persisted)

        assert "executive.speech.delivered" in description
        assert "sequence 1" in description

    @pytest.mark.asyncio
    async def test_describe_panel_event(
        self,
        fake_time_authority,
    ) -> None:
        """Panel events get special descriptions (FR41)."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        service = KnightObserverService(
            ledger=AsyncMock(),
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
        )

        @dataclass
        class MockPersistedEvent:
            event_type: str
            sequence: int
            actor_id: str

        persisted = MockPersistedEvent(
            event_type="judicial.panel.convened",
            sequence=42,
            actor_id="prince-123",
        )

        description = service._describe_panel_event(persisted)

        assert "Panel convened" in description
        assert "sequence 42" in description


class TestKnightObserverStatus:
    """Tests for observer status reporting."""

    @pytest.mark.asyncio
    async def test_get_observation_status(
        self,
        fake_time_authority,
    ) -> None:
        """Observer status is correctly reported."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        service = KnightObserverService(
            ledger=AsyncMock(),
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
            poll_interval_seconds=0.5,
            batch_size=100,
        )

        status = await service.get_observation_status()

        assert status["running"] is False
        assert status["last_observed_sequence"] == 0
        assert status["total_events_observed"] == 0
        assert status["poll_interval_seconds"] == 0.5
        assert status["batch_size"] == 100

    @pytest.mark.asyncio
    async def test_status_updates_after_observation(
        self,
        fake_time_authority,
    ) -> None:
        """Status reflects observations."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        # Create ledger mock that returns empty (no events)
        mock_ledger = AsyncMock()
        mock_ledger.read_events = AsyncMock(return_value=[])

        service = KnightObserverService(
            ledger=mock_ledger,
            witness_port=AsyncMock(),
            statement_factory=MagicMock(),
            time_authority=fake_time_authority,
        )

        # Run one observation cycle
        metrics = await service.observe_once()

        assert metrics.events_observed == 0
        assert metrics.cycle_duration_ms >= 0


class TestKnightObserverPanelEventTypes:
    """Tests for panel event type recognition (FR41)."""

    @pytest.mark.asyncio
    async def test_panel_event_types_recognized(
        self,
    ) -> None:
        """All panel event types are recognized."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        expected_panel_types = {
            "judicial.panel.convened",
            "judicial.panel.deliberation_started",
            "judicial.panel.member_recused",
            "judicial.panel.finding_proposed",
            "judicial.panel.vote_recorded",
            "judicial.panel.finding_issued",
            "judicial.panel.dissent_recorded",
        }

        assert expected_panel_types == KnightObserverService.PANEL_EVENT_TYPES

    @pytest.mark.asyncio
    async def test_branch_prefixes_complete(
        self,
    ) -> None:
        """All expected branch prefixes are configured."""
        from src.application.services.governance.knight_observer_service import (
            KnightObserverService,
        )

        required_branches = {"executive", "judicial", "witness", "consent"}

        for branch in required_branches:
            assert branch in KnightObserverService.BRANCH_PREFIXES
