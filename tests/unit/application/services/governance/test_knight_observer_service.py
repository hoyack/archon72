"""Unit tests for Knight Observer Service.

Story: consent-gov-6.2: Passive Knight Observation

Tests for the KnightObserverService which provides passive observation of
governance events via ledger polling.

Acceptance Criteria Tested:
- AC1: Event bus subscription for real-time observation (ledger polling)
- AC2: Ledger replay as verification backstop
- AC3: Events observable within ≤1 second (NFR-OBS-01)
- AC4: All branch actions logged with sufficient detail (NFR-AUDIT-01)
- AC5: Knight can observe Prince Panel conduct (FR41)
- AC6: No active notification from services (loose coupling)
- AC7: Gap detection via hash chain continuity
- AC8: Dual-path observation: bus (fast) + ledger (resilient)
- AC9: Unit tests for observation mechanics

References:
    - FR33: Knight can observe and record violations across all branches
    - FR41: Knight can observe Prince Panel conduct
    - NFR-OBS-01: Knight observes all branch actions within ≤1 second
    - NFR-AUDIT-01: All branch actions logged with sufficient detail
    - AD-16: Knight Observation Pattern (passive subscription)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.knight_observer_service import (
    GapDetection,
    KnightObserverService,
)
from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.witness_statement import WitnessStatement
from src.domain.governance.witness.witness_statement_factory import (
    WitnessStatementFactory,
)

# =============================================================================
# Test Doubles
# =============================================================================


class FakeTimeAuthority:
    """Fake time authority for deterministic testing."""

    def __init__(
        self,
        fixed_time: datetime | None = None,
        monotonic_start: float = 0.0,
    ) -> None:
        self._fixed_time = fixed_time or datetime(
            2026, 1, 17, 10, 30, 0, tzinfo=timezone.utc
        )
        self._monotonic_value = monotonic_start
        self._auto_advance = timedelta(seconds=0)

    def now(self) -> datetime:
        result = self._fixed_time
        if self._auto_advance:
            self._fixed_time = self._fixed_time + self._auto_advance
        return result

    def utcnow(self) -> datetime:
        return self.now()

    def monotonic(self) -> float:
        result = self._monotonic_value
        self._monotonic_value += 0.001  # Advance 1ms each call
        return result

    def advance(self, delta: timedelta) -> None:
        """Advance the clock by delta."""
        self._fixed_time = self._fixed_time + delta

    def set_time(self, new_time: datetime) -> None:
        """Set a specific time."""
        self._fixed_time = new_time

    def enable_auto_advance(self, delta: timedelta) -> None:
        """Enable automatic time advancement on each call."""
        self._auto_advance = delta


@dataclass(frozen=True)
class FakePersistedGovernanceEvent:
    """Fake persisted governance event for testing."""

    event_id: UUID
    event_type: str
    timestamp: datetime
    actor_id: str
    sequence: int
    payload: dict[str, Any] | None = None

    @property
    def branch(self) -> str:
        parts = self.event_type.split(".")
        return parts[0] if parts else "governance"


class FakeGovernanceLedgerPort:
    """Fake ledger port for testing."""

    def __init__(self) -> None:
        self._events: list[FakePersistedGovernanceEvent] = []
        self._max_sequence: int = 0

    def add_event(
        self,
        event_type: str,
        actor_id: str = "test-actor",
        timestamp: datetime | None = None,
        payload: dict[str, Any] | None = None,
    ) -> FakePersistedGovernanceEvent:
        """Add an event to the fake ledger."""
        self._max_sequence += 1
        event = FakePersistedGovernanceEvent(
            event_id=uuid4(),
            event_type=event_type,
            timestamp=timestamp
            or datetime(2026, 1, 17, 10, 30, 0, tzinfo=timezone.utc),
            actor_id=actor_id,
            sequence=self._max_sequence,
            payload=payload or {},
        )
        self._events.append(event)
        return event

    def add_event_at_sequence(
        self,
        sequence: int,
        event_type: str,
        actor_id: str = "test-actor",
        timestamp: datetime | None = None,
    ) -> FakePersistedGovernanceEvent:
        """Add an event at a specific sequence number (for gap testing)."""
        event = FakePersistedGovernanceEvent(
            event_id=uuid4(),
            event_type=event_type,
            timestamp=timestamp
            or datetime(2026, 1, 17, 10, 30, 0, tzinfo=timezone.utc),
            actor_id=actor_id,
            sequence=sequence,
        )
        self._events.append(event)
        self._events.sort(key=lambda e: e.sequence)
        self._max_sequence = max(self._max_sequence, sequence)
        return event

    async def read_events(
        self,
        options: Any = None,
    ) -> list[FakePersistedGovernanceEvent]:
        """Read events from fake ledger."""
        if options is None:
            return self._events[:100]

        start_seq = getattr(options, "start_sequence", None) or 0
        limit = getattr(options, "limit", 100)

        filtered = [e for e in self._events if e.sequence >= start_seq]
        return filtered[:limit]

    async def get_max_sequence(self) -> int:
        """Get max sequence number."""
        return self._max_sequence

    async def get_latest_event(self) -> FakePersistedGovernanceEvent | None:
        """Get latest event."""
        if not self._events:
            return None
        return max(self._events, key=lambda e: e.sequence)


class FakeWitnessPort:
    """Fake witness port for testing."""

    def __init__(self) -> None:
        self._statements: list[WitnessStatement] = []

    async def record_statement(self, statement: WitnessStatement) -> None:
        """Record a witness statement."""
        self._statements.append(statement)

    async def get_statements_for_event(self, event_id: UUID) -> list[WitnessStatement]:
        """Get statements for an event."""
        return [s for s in self._statements if s.content.event_id == event_id]

    async def get_statements_by_type(
        self,
        observation_type: ObservationType,
        since: datetime | None = None,
    ) -> list[WitnessStatement]:
        """Get statements by type."""
        result = [s for s in self._statements if s.observation_type == observation_type]
        if since:
            result = [s for s in result if s.observed_at >= since]
        return result

    async def get_statement_chain(
        self,
        start_position: int,
        end_position: int,
    ) -> list[WitnessStatement]:
        """Get statements by chain position."""
        return [
            s
            for s in self._statements
            if start_position <= s.hash_chain_position <= end_position
        ]

    def get_all_statements(self) -> list[WitnessStatement]:
        """Get all recorded statements (test helper)."""
        return list(self._statements)

    def clear(self) -> None:
        """Clear all statements (test helper)."""
        self._statements.clear()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Create fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def ledger() -> FakeGovernanceLedgerPort:
    """Create fake ledger port."""
    return FakeGovernanceLedgerPort()


@pytest.fixture
def witness_port() -> FakeWitnessPort:
    """Create fake witness port."""
    return FakeWitnessPort()


@pytest.fixture
def statement_factory(time_authority: FakeTimeAuthority) -> WitnessStatementFactory:
    """Create statement factory with fake time authority."""
    return WitnessStatementFactory(time_authority=time_authority)


@pytest.fixture
def observer(
    ledger: FakeGovernanceLedgerPort,
    witness_port: FakeWitnessPort,
    statement_factory: WitnessStatementFactory,
    time_authority: FakeTimeAuthority,
) -> KnightObserverService:
    """Create Knight Observer Service for testing."""
    return KnightObserverService(
        ledger=ledger,
        witness_port=witness_port,
        statement_factory=statement_factory,
        time_authority=time_authority,
        poll_interval_seconds=0.1,  # Fast for testing
    )


# =============================================================================
# Test Classes
# =============================================================================


class TestKnightObserverServiceBasics:
    """Basic functionality tests for Knight Observer Service."""

    @pytest.mark.asyncio
    async def test_observer_starts_and_stops(
        self,
        observer: KnightObserverService,
    ) -> None:
        """Observer can start and stop cleanly."""
        await observer.start()
        assert observer.is_running is True

        await observer.stop()
        assert observer.is_running is False

    @pytest.mark.asyncio
    async def test_observer_tracks_last_sequence(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
    ) -> None:
        """Observer tracks last observed sequence number (AC2)."""
        ledger.add_event("executive.task.activated")
        ledger.add_event("executive.task.accepted")

        await observer.observe_once()

        assert observer.last_observed_sequence == 2

    @pytest.mark.asyncio
    async def test_observer_starts_from_specified_sequence(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer can start from a specific sequence number."""
        # Add events at sequences 1-3
        ledger.add_event("executive.task.activated")
        ledger.add_event("executive.task.accepted")
        ledger.add_event("executive.task.completed")

        # Start from sequence 2 (should only observe sequence 3)
        observer2 = KnightObserverService(
            ledger=ledger,
            witness_port=witness_port,
            statement_factory=observer._statement_factory,
            time_authority=observer._time_authority,
        )

        await observer2.start(starting_sequence=2)
        await observer2.observe_once()
        await observer2.stop()

        # Should have observed only 1 event (sequence 3)
        witness_port.get_all_statements()
        # Due to the factory counter being shared, we may have more
        # But the observer should only have processed events from seq 3
        assert observer2.total_events_observed == 1


class TestEventObservation:
    """Tests for event observation mechanics."""

    @pytest.mark.asyncio
    async def test_observes_events_from_ledger(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer creates witness statements for ledger events (AC1, AC4)."""
        ledger.add_event("executive.task.activated", actor_id="archon-42")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert len(statements) == 1
        assert statements[0].observation_type == ObservationType.BRANCH_ACTION

    @pytest.mark.asyncio
    async def test_observes_multiple_events(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer handles multiple events in single poll cycle."""
        ledger.add_event("executive.task.activated")
        ledger.add_event("judicial.panel.convened")
        ledger.add_event("constitutional.amendment.proposed")

        metrics = await observer.observe_once()

        assert metrics.events_observed == 3
        assert len(witness_port.get_all_statements()) == 3

    @pytest.mark.asyncio
    async def test_idempotent_observation(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer doesn't re-observe already-observed events."""
        ledger.add_event("executive.task.activated")

        # Observe twice
        await observer.observe_once()
        await observer.observe_once()

        # Should only have 1 statement, not 2
        statements = witness_port.get_all_statements()
        assert len(statements) == 1

    @pytest.mark.asyncio
    async def test_observes_new_events_after_previous_batch(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer picks up new events in subsequent poll cycles."""
        ledger.add_event("executive.task.activated")
        await observer.observe_once()

        # Add more events
        ledger.add_event("executive.task.accepted")
        ledger.add_event("executive.task.completed")
        await observer.observe_once()

        assert observer.total_events_observed == 3
        assert len(witness_port.get_all_statements()) == 3


class TestGapDetection:
    """Tests for sequence gap detection (AC7)."""

    @pytest.mark.asyncio
    async def test_detects_sequence_gap(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer detects gaps in sequence numbers (AC7)."""
        # Add event at sequence 1
        ledger.add_event_at_sequence(1, "executive.task.activated")
        await observer.observe_once()

        # Skip sequence 2, add at sequence 3
        ledger.add_event_at_sequence(3, "executive.task.completed")
        metrics = await observer.observe_once()

        assert metrics.gaps_detected == 1
        assert observer.total_gaps_detected == 1

        # Check that a gap detection statement was recorded
        gap_statements = await witness_port.get_statements_by_type(
            ObservationType.HASH_CHAIN_GAP
        )
        assert len(gap_statements) == 1
        assert "gap" in gap_statements[0].content.what.lower()

    @pytest.mark.asyncio
    async def test_gap_detection_records_missing_count(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Gap detection includes count of missing events."""
        ledger.add_event_at_sequence(1, "executive.task.activated")
        await observer.observe_once()

        # Skip 3 events (2, 3, 4), add at 5
        ledger.add_event_at_sequence(5, "executive.task.completed")
        await observer.observe_once()

        gap_statements = await witness_port.get_statements_by_type(
            ObservationType.HASH_CHAIN_GAP
        )
        assert len(gap_statements) == 1
        assert "3" in gap_statements[0].content.what  # 3 missing events

    @pytest.mark.asyncio
    async def test_no_false_gap_for_sequential_events(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
    ) -> None:
        """No gap detection for properly sequential events."""
        ledger.add_event("executive.task.activated")  # seq 1
        ledger.add_event("executive.task.accepted")  # seq 2
        ledger.add_event("executive.task.completed")  # seq 3

        metrics = await observer.observe_once()

        assert metrics.gaps_detected == 0
        assert observer.total_gaps_detected == 0

    @pytest.mark.asyncio
    async def test_gap_callback_invoked(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
    ) -> None:
        """Gap callback is invoked when gap detected."""
        gap_detections: list[GapDetection] = []

        async def gap_callback(gap: GapDetection) -> None:
            gap_detections.append(gap)

        observer.register_gap_callback(gap_callback)

        ledger.add_event_at_sequence(1, "executive.task.activated")
        await observer.observe_once()

        ledger.add_event_at_sequence(5, "executive.task.completed")
        await observer.observe_once()

        assert len(gap_detections) == 1
        assert gap_detections[0].expected_sequence == 2
        assert gap_detections[0].actual_sequence == 5
        assert gap_detections[0].missing_count == 3


class TestLatencyMonitoring:
    """Tests for latency monitoring (AC3, NFR-OBS-01)."""

    @pytest.mark.asyncio
    async def test_tracks_observation_latency(
        self,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
        statement_factory: WitnessStatementFactory,
    ) -> None:
        """Observer tracks latency from event timestamp to observation (AC3)."""
        # Event happened 500ms ago
        time_authority = FakeTimeAuthority(
            fixed_time=datetime(2026, 1, 17, 10, 30, 0, 500000, tzinfo=timezone.utc)
        )

        event_time = datetime(2026, 1, 17, 10, 30, 0, 0, tzinfo=timezone.utc)
        ledger.add_event(
            "executive.task.activated",
            timestamp=event_time,
        )

        observer = KnightObserverService(
            ledger=ledger,
            witness_port=witness_port,
            statement_factory=statement_factory,
            time_authority=time_authority,
        )

        metrics = await observer.observe_once()

        # Latency should be around 500ms
        assert metrics.max_latency_ms >= 400  # Allow some tolerance
        assert metrics.max_latency_ms <= 600

    @pytest.mark.asyncio
    async def test_counts_latency_violations(
        self,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
        statement_factory: WitnessStatementFactory,
    ) -> None:
        """Observer counts events exceeding latency threshold (NFR-OBS-01)."""
        # Event happened 2 seconds ago (exceeds 1s threshold)
        time_authority = FakeTimeAuthority(
            fixed_time=datetime(2026, 1, 17, 10, 30, 2, tzinfo=timezone.utc)
        )

        event_time = datetime(2026, 1, 17, 10, 30, 0, tzinfo=timezone.utc)
        ledger.add_event(
            "executive.task.activated",
            timestamp=event_time,
        )

        observer = KnightObserverService(
            ledger=ledger,
            witness_port=witness_port,
            statement_factory=statement_factory,
            time_authority=time_authority,
        )

        await observer.observe_once()

        assert observer.latency_violations == 1

    @pytest.mark.asyncio
    async def test_latency_within_threshold_no_violation(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
    ) -> None:
        """Events within latency threshold don't count as violations."""
        # Event and observation at same time (0 latency)
        ledger.add_event(
            "executive.task.activated",
            timestamp=datetime(2026, 1, 17, 10, 30, 0, tzinfo=timezone.utc),
        )

        await observer.observe_once()

        assert observer.latency_violations == 0


class TestEventClassification:
    """Tests for event type classification."""

    @pytest.mark.asyncio
    async def test_classifies_violation_events(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer classifies violation events correctly."""
        ledger.add_event("consent.violation.detected")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert statements[0].observation_type == ObservationType.POTENTIAL_VIOLATION

    @pytest.mark.asyncio
    async def test_classifies_timing_events(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer classifies timeout/timing events correctly."""
        ledger.add_event("executive.task.timeout")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert statements[0].observation_type == ObservationType.TIMING_ANOMALY

    @pytest.mark.asyncio
    async def test_classifies_gap_events(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer classifies gap-related events correctly."""
        ledger.add_event("ledger.integrity.gap_detected")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert statements[0].observation_type == ObservationType.HASH_CHAIN_GAP

    @pytest.mark.asyncio
    async def test_classifies_normal_events_as_branch_action(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer classifies normal events as BRANCH_ACTION."""
        ledger.add_event("executive.task.activated")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert statements[0].observation_type == ObservationType.BRANCH_ACTION


class TestBranchClassification:
    """Tests for branch determination from event types."""

    @pytest.mark.asyncio
    async def test_determines_executive_branch(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer determines executive branch from event type."""
        ledger.add_event("executive.task.activated")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert statements[0].content.where == "executive"

    @pytest.mark.asyncio
    async def test_determines_judicial_branch(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer determines judicial branch from event type."""
        ledger.add_event("judicial.panel.convened")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert statements[0].content.where == "judicial"

    @pytest.mark.asyncio
    async def test_determines_constitutional_branch(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer determines constitutional branch from event type."""
        ledger.add_event("constitutional.amendment.proposed")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert statements[0].content.where == "constitutional"


class TestPanelObservation:
    """Tests for Prince Panel observation (AC5, FR41)."""

    @pytest.mark.asyncio
    async def test_observes_panel_convened(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer observes panel convening (FR41)."""
        ledger.add_event("judicial.panel.convened")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert len(statements) == 1
        assert "Panel convened" in statements[0].content.what

    @pytest.mark.asyncio
    async def test_observes_panel_deliberation(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer observes panel deliberation (FR41)."""
        ledger.add_event("judicial.panel.deliberation_started")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert "Deliberation began" in statements[0].content.what

    @pytest.mark.asyncio
    async def test_observes_panel_finding_issued(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer observes panel findings (FR41)."""
        ledger.add_event("judicial.panel.finding_issued")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert "Formal finding issued" in statements[0].content.what

    @pytest.mark.asyncio
    async def test_observes_panel_recusal(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer observes panel member recusal (FR41)."""
        ledger.add_event("judicial.panel.member_recused")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert "recused" in statements[0].content.what.lower()

    @pytest.mark.asyncio
    async def test_observes_panel_dissent(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer observes panel dissent (FR41)."""
        ledger.add_event("judicial.panel.dissent_recorded")

        await observer.observe_once()

        statements = witness_port.get_all_statements()
        assert "Dissent" in statements[0].content.what


class TestLooseCoupling:
    """Tests for loose coupling design (AC6)."""

    @pytest.mark.asyncio
    async def test_observer_pulls_from_ledger(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
    ) -> None:
        """Observer pulls events from ledger (not pushed to) (AC6)."""
        # Add events without notifying observer
        ledger.add_event("executive.task.activated")
        ledger.add_event("executive.task.accepted")

        # Observer must actively pull
        assert observer.total_events_observed == 0

        # Now pull
        await observer.observe_once()

        assert observer.total_events_observed == 2

    @pytest.mark.asyncio
    async def test_services_dont_call_observer(
        self,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
        statement_factory: WitnessStatementFactory,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Observer is not called by services - it polls (AC6).

        This test demonstrates that the ledger doesn't have a reference
        to the observer and cannot call it. The observer must poll.
        """
        # Create ledger and observer separately
        observer = KnightObserverService(
            ledger=ledger,
            witness_port=witness_port,
            statement_factory=statement_factory,
            time_authority=time_authority,
        )

        # Services write to ledger (simulated)
        ledger.add_event("executive.task.activated")

        # Ledger has no way to notify observer
        # Observer must poll to discover events
        assert observer.total_events_observed == 0

        # Only after polling does observer see events
        await observer.observe_once()
        assert observer.total_events_observed == 1


class TestObservationMetrics:
    """Tests for observation metrics."""

    @pytest.mark.asyncio
    async def test_metrics_include_event_count(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
    ) -> None:
        """Metrics include count of events observed."""
        ledger.add_event("executive.task.activated")
        ledger.add_event("executive.task.accepted")

        metrics = await observer.observe_once()

        assert metrics.events_observed == 2

    @pytest.mark.asyncio
    async def test_metrics_include_gap_count(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
    ) -> None:
        """Metrics include count of gaps detected."""
        ledger.add_event_at_sequence(1, "executive.task.activated")
        await observer.observe_once()

        ledger.add_event_at_sequence(3, "executive.task.completed")
        metrics = await observer.observe_once()

        assert metrics.gaps_detected == 1

    @pytest.mark.asyncio
    async def test_metrics_include_cycle_duration(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
    ) -> None:
        """Metrics include observation cycle duration."""
        ledger.add_event("executive.task.activated")

        metrics = await observer.observe_once()

        assert metrics.cycle_duration_ms >= 0

    @pytest.mark.asyncio
    async def test_empty_cycle_returns_zero_metrics(
        self,
        observer: KnightObserverService,
    ) -> None:
        """Empty observation cycle returns zero metrics."""
        metrics = await observer.observe_once()

        assert metrics.events_observed == 0
        assert metrics.gaps_detected == 0
        assert metrics.max_latency_ms == 0.0
        assert metrics.avg_latency_ms == 0.0


class TestObservationStatus:
    """Tests for observation status reporting."""

    @pytest.mark.asyncio
    async def test_get_observation_status(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
    ) -> None:
        """Observer provides status for monitoring."""
        ledger.add_event("executive.task.activated")
        await observer.observe_once()

        status = await observer.get_observation_status()

        assert status["running"] is False
        assert status["last_observed_sequence"] == 1
        assert status["total_events_observed"] == 1
        assert status["total_gaps_detected"] == 0
        assert "poll_interval_seconds" in status
        assert "batch_size" in status

    @pytest.mark.asyncio
    async def test_status_reflects_running_state(
        self,
        observer: KnightObserverService,
    ) -> None:
        """Status correctly reflects running state."""
        assert (await observer.get_observation_status())["running"] is False

        await observer.start()
        assert (await observer.get_observation_status())["running"] is True

        await observer.stop()
        assert (await observer.get_observation_status())["running"] is False


class TestAllBranchObservation:
    """Tests for observing events across all branches (FR33)."""

    @pytest.mark.asyncio
    async def test_observes_all_branch_types(
        self,
        observer: KnightObserverService,
        ledger: FakeGovernanceLedgerPort,
        witness_port: FakeWitnessPort,
    ) -> None:
        """Observer handles events from all governance branches (FR33)."""
        branches = [
            "executive.task.activated",
            "judicial.panel.convened",
            "constitutional.amendment.proposed",
            "witness.observation.recorded",
            "filter.message.blocked",
            "consent.granted",
            "legitimacy.band.transitioned",
            "safety.halt.triggered",
            "system.lifecycle.started",
            "ledger.integrity.verified",
        ]

        for event_type in branches:
            ledger.add_event(event_type)

        await observer.observe_once()

        assert observer.total_events_observed == len(branches)
        statements = witness_port.get_all_statements()
        assert len(statements) == len(branches)
