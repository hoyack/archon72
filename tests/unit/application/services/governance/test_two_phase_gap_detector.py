"""Unit tests for TwoPhaseGapDetector service.

Story: consent-gov-1.6: Two-Phase Event Emission

Tests the TwoPhaseGapDetector service that verifies two-phase completeness
by detecting intents without corresponding outcome events.

Constitutional Reference:
- AD-3: Two-phase event emission
- AC7: Hash chain gap detection triggers constitutional violation event
- AC8: Knight can observe intent_emitted immediately upon action initiation
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.governance.two_phase_gap_detector import (
    TwoPhaseGapDetector,
    TwoPhaseViolation,
    TwoPhaseViolationType,
)
from src.domain.governance.events.event_envelope import EventMetadata, GovernanceEvent


def make_event(
    event_type: str,
    correlation_id: str,
    timestamp: datetime,
    actor_id: str = "archon-42",
) -> GovernanceEvent:
    """Helper to create test events."""
    metadata = EventMetadata(
        event_id=uuid4(),
        event_type=event_type,
        timestamp=timestamp,
        actor_id=actor_id,
        schema_version="1.0.0",
        trace_id=correlation_id,
    )
    return GovernanceEvent(
        metadata=metadata,
        payload={"correlation_id": correlation_id},
    )


@pytest.fixture
def mock_ledger() -> AsyncMock:
    """Create a mock governance ledger."""
    ledger = AsyncMock()
    ledger.read_events.return_value = []
    return ledger


@pytest.fixture
def mock_time_authority() -> MagicMock:
    """Create a mock time authority."""
    time_authority = MagicMock()
    time_authority.now.return_value = datetime(
        2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc
    )
    return time_authority


@pytest.fixture
def detector(
    mock_ledger: AsyncMock, mock_time_authority: MagicMock
) -> TwoPhaseGapDetector:
    """Create a TwoPhaseGapDetector with mocked dependencies."""
    return TwoPhaseGapDetector(
        ledger=mock_ledger,
        time_authority=mock_time_authority,
        orphan_timeout=timedelta(minutes=5),
    )


class TestTwoPhaseViolationType:
    """Tests for TwoPhaseViolationType enum."""

    def test_orphaned_intent_type(self) -> None:
        """Should have ORPHANED_INTENT type."""
        assert TwoPhaseViolationType.ORPHANED_INTENT.value == "orphaned_intent"

    def test_outcome_without_intent_type(self) -> None:
        """Should have OUTCOME_WITHOUT_INTENT type."""
        assert (
            TwoPhaseViolationType.OUTCOME_WITHOUT_INTENT.value
            == "outcome_without_intent"
        )


class TestTwoPhaseViolation:
    """Tests for TwoPhaseViolation model."""

    def test_create_orphan_violation(self) -> None:
        """Should create an orphaned intent violation."""
        event_id = uuid4()
        correlation_id = str(uuid4())
        violation = TwoPhaseViolation(
            event_id=event_id,
            correlation_id=correlation_id,
            violation_type=TwoPhaseViolationType.ORPHANED_INTENT,
            event_type="executive.intent.emitted",
            age=timedelta(minutes=10),
        )

        assert violation.event_id == event_id
        assert violation.correlation_id == correlation_id
        assert violation.violation_type == TwoPhaseViolationType.ORPHANED_INTENT
        assert violation.age == timedelta(minutes=10)

    def test_violation_is_frozen(self) -> None:
        """TwoPhaseViolation should be immutable."""
        violation = TwoPhaseViolation(
            event_id=uuid4(),
            correlation_id=str(uuid4()),
            violation_type=TwoPhaseViolationType.ORPHANED_INTENT,
            event_type="executive.intent.emitted",
            age=timedelta(minutes=10),
        )

        with pytest.raises(AttributeError):
            violation.age = timedelta(minutes=5)  # type: ignore


class TestVerifyTwoPhaseCompleteness:
    """Tests for verify_two_phase_completeness method (AC7)."""

    @pytest.mark.asyncio
    async def test_no_violations_when_no_intents(
        self, detector: TwoPhaseGapDetector, mock_ledger: AsyncMock
    ) -> None:
        """No violations when there are no intent events."""
        mock_ledger.read_events.return_value = []

        violations = await detector.verify_two_phase_completeness()

        assert violations == []

    @pytest.mark.asyncio
    async def test_no_violation_for_committed_intent(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """No violation when intent has matching commit."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        correlation_id = str(uuid4())
        intent_time = now - timedelta(minutes=2)
        commit_time = now - timedelta(minutes=1)

        intent = make_event("executive.intent.emitted", correlation_id, intent_time)
        commit = make_event("executive.commit.confirmed", correlation_id, commit_time)

        # First call returns intents, second returns outcomes
        mock_ledger.read_events.side_effect = [[intent], [commit]]

        violations = await detector.verify_two_phase_completeness()

        assert violations == []

    @pytest.mark.asyncio
    async def test_no_violation_for_failed_intent(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """No violation when intent has matching failure."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        correlation_id = str(uuid4())
        intent_time = now - timedelta(minutes=2)
        failure_time = now - timedelta(minutes=1)

        intent = make_event("executive.intent.emitted", correlation_id, intent_time)
        failure = make_event("executive.failure.recorded", correlation_id, failure_time)

        mock_ledger.read_events.side_effect = [[intent], [failure]]

        violations = await detector.verify_two_phase_completeness()

        assert violations == []

    @pytest.mark.asyncio
    async def test_violation_for_orphaned_intent(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Violation when intent has no outcome and exceeds timeout."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        correlation_id = str(uuid4())
        intent_time = now - timedelta(minutes=10)  # Older than 5 min timeout

        intent = make_event("executive.intent.emitted", correlation_id, intent_time)

        # No outcomes found
        mock_ledger.read_events.side_effect = [[intent], []]

        violations = await detector.verify_two_phase_completeness()

        assert len(violations) == 1
        assert violations[0].correlation_id == correlation_id
        assert violations[0].violation_type == TwoPhaseViolationType.ORPHANED_INTENT

    @pytest.mark.asyncio
    async def test_no_violation_for_recent_unresolved_intent(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """No violation for intent within timeout (may still resolve)."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        correlation_id = str(uuid4())
        intent_time = now - timedelta(minutes=2)  # Within 5 min timeout

        intent = make_event("executive.intent.emitted", correlation_id, intent_time)

        mock_ledger.read_events.side_effect = [[intent], []]

        violations = await detector.verify_two_phase_completeness()

        assert violations == []

    @pytest.mark.asyncio
    async def test_multiple_orphans_detected(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """All orphaned intents are detected."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        old_time = now - timedelta(minutes=10)
        id1, id2 = str(uuid4()), str(uuid4())

        intent1 = make_event("executive.intent.emitted", id1, old_time)
        intent2 = make_event("judicial.intent.emitted", id2, old_time)

        mock_ledger.read_events.side_effect = [[intent1, intent2], []]

        violations = await detector.verify_two_phase_completeness()

        assert len(violations) == 2
        assert {v.correlation_id for v in violations} == {id1, id2}


class TestEmitOrphanViolationEvent:
    """Tests for emit_orphan_violation_event method."""

    @pytest.mark.asyncio
    async def test_emits_violation_event_to_ledger(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Should emit ledger.integrity.orphaned_intent_detected event."""
        violation = TwoPhaseViolation(
            event_id=uuid4(),
            correlation_id=str(uuid4()),
            violation_type=TwoPhaseViolationType.ORPHANED_INTENT,
            event_type="executive.intent.emitted",
            age=timedelta(minutes=10),
        )

        await detector.emit_orphan_violation_event(violation)

        mock_ledger.append_event.assert_called_once()
        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        assert event.event_type == "ledger.integrity.orphaned_intent_detected"

    @pytest.mark.asyncio
    async def test_violation_event_includes_details(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Violation event should include full violation details."""
        event_id = uuid4()
        correlation_id = str(uuid4())
        violation = TwoPhaseViolation(
            event_id=event_id,
            correlation_id=correlation_id,
            violation_type=TwoPhaseViolationType.ORPHANED_INTENT,
            event_type="executive.intent.emitted",
            age=timedelta(minutes=10),
        )

        await detector.emit_orphan_violation_event(violation)

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        assert event.payload["intent_event_id"] == str(event_id)
        assert event.payload["correlation_id"] == correlation_id
        assert event.payload["violation_type"] == "orphaned_intent"
        assert event.payload["orphan_age_seconds"] == 600


class TestScanAndEmitViolations:
    """Tests for scan_and_emit_violations convenience method."""

    @pytest.mark.asyncio
    async def test_scans_and_emits_all_violations(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Should scan for violations and emit events for each."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        old_time = now - timedelta(minutes=10)
        id1, id2 = str(uuid4()), str(uuid4())

        intent1 = make_event("executive.intent.emitted", id1, old_time)
        intent2 = make_event("judicial.intent.emitted", id2, old_time)

        # Configure ledger for scan
        mock_ledger.read_events.side_effect = [[intent1, intent2], []]

        violations = await detector.scan_and_emit_violations()

        assert len(violations) == 2
        # One call per violation event + 2 calls for read_events
        assert mock_ledger.append_event.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_violations(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
    ) -> None:
        """Should return empty list when no violations found."""
        mock_ledger.read_events.return_value = []

        violations = await detector.scan_and_emit_violations()

        assert violations == []
        mock_ledger.append_event.assert_not_called()


class TestKnightObservability:
    """Tests for Knight observability (AC8)."""

    @pytest.mark.asyncio
    async def test_can_query_intent_outcome_pairs(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Knight can query for intent-outcome pairs by correlation ID."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        correlation_id = str(uuid4())
        intent_time = now - timedelta(minutes=5)
        commit_time = now - timedelta(minutes=3)

        intent = make_event("executive.intent.emitted", correlation_id, intent_time)
        commit = make_event("executive.commit.confirmed", correlation_id, commit_time)

        mock_ledger.read_events.side_effect = [[intent], [commit]]

        pair = await detector.get_intent_outcome_pair(correlation_id)

        assert pair is not None
        assert pair["intent"] is not None
        assert pair["outcome"] is not None
        assert pair["correlation_id"] == correlation_id

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_correlation_id(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
    ) -> None:
        """Should return None for unknown correlation ID."""
        mock_ledger.read_events.return_value = []

        pair = await detector.get_intent_outcome_pair(str(uuid4()))

        assert pair is None

    @pytest.mark.asyncio
    async def test_returns_pair_with_intent_only(
        self,
        detector: TwoPhaseGapDetector,
        mock_ledger: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Should return pair with intent and None outcome for pending."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        correlation_id = str(uuid4())
        intent_time = now - timedelta(minutes=2)

        intent = make_event("executive.intent.emitted", correlation_id, intent_time)

        mock_ledger.read_events.side_effect = [[intent], []]

        pair = await detector.get_intent_outcome_pair(correlation_id)

        assert pair is not None
        assert pair["intent"] is not None
        assert pair["outcome"] is None
        assert pair["is_pending"] is True
