"""Integration tests for two-phase event emission lifecycle.

Story: consent-gov-1.6: Two-Phase Event Emission

Tests the full two-phase lifecycle end-to-end with real service instances.

Constitutional Reference:
- AD-3: Two-phase event emission
- AC8: Knight can observe intent immediately
- AC10: Integration tests for full lifecycle
"""

from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.orphan_intent_detector import (
    OrphanIntentDetector,
)
from src.application.services.governance.two_phase_event_emitter import (
    TwoPhaseEventEmitter,
)
from src.application.services.governance.two_phase_execution import TwoPhaseExecution
from src.application.services.governance.two_phase_gap_detector import (
    TwoPhaseGapDetector,
)
from src.domain.governance.events.event_envelope import EventMetadata, GovernanceEvent


class FakeTimeAuthority:
    """Fake time authority for deterministic testing."""

    def __init__(self, initial_time: datetime | None = None) -> None:
        self._current_time = initial_time or datetime(
            2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc
        )

    def now(self) -> datetime:
        return self._current_time

    def utcnow(self) -> datetime:
        return self._current_time

    def monotonic(self) -> float:
        return 0.0

    def advance(self, delta: timedelta) -> None:
        self._current_time += delta


class FakeLedger:
    """Fake ledger that stores events in memory."""

    def __init__(self) -> None:
        self._events: list[GovernanceEvent] = []

    async def append_event(self, event: GovernanceEvent) -> GovernanceEvent:
        """Append event to ledger."""
        self._events.append(event)
        return event

    async def read_events(
        self, event_type_pattern: str | None = None
    ) -> list[GovernanceEvent]:
        """Read events matching pattern."""
        if not event_type_pattern:
            return self._events.copy()

        # Simple pattern matching for tests
        patterns = event_type_pattern.split("|")
        result = []
        for event in self._events:
            for pattern in patterns:
                if pattern.startswith("*"):
                    # Wildcard prefix match
                    suffix = pattern[1:]
                    if event.event_type.endswith(suffix):
                        result.append(event)
                        break
                elif event.event_type == pattern:
                    result.append(event)
                    break
        return result

    def get_events(self) -> list[GovernanceEvent]:
        """Get all events."""
        return self._events.copy()

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Create a fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def ledger() -> FakeLedger:
    """Create a fake ledger."""
    return FakeLedger()


@pytest.fixture
def emitter(ledger: FakeLedger, time_authority: FakeTimeAuthority) -> TwoPhaseEventEmitter:
    """Create a TwoPhaseEventEmitter with fake dependencies."""
    return TwoPhaseEventEmitter(ledger, time_authority)


@pytest.fixture
def orphan_detector(
    emitter: TwoPhaseEventEmitter, time_authority: FakeTimeAuthority
) -> OrphanIntentDetector:
    """Create an OrphanIntentDetector with fake dependencies."""
    return OrphanIntentDetector(
        emitter=emitter,
        time_authority=time_authority,
        orphan_timeout=timedelta(minutes=5),
    )


@pytest.fixture
def gap_detector(
    ledger: FakeLedger, time_authority: FakeTimeAuthority
) -> TwoPhaseGapDetector:
    """Create a TwoPhaseGapDetector with fake dependencies."""
    return TwoPhaseGapDetector(
        ledger=ledger,
        time_authority=time_authority,
        orphan_timeout=timedelta(minutes=5),
    )


class TestFullTwoPhaseLifecycle:
    """Tests for full two-phase lifecycle end-to-end."""

    @pytest.mark.asyncio
    async def test_success_lifecycle(
        self,
        emitter: TwoPhaseEventEmitter,
        ledger: FakeLedger,
    ) -> None:
        """Full success lifecycle: intent → operation → commit."""
        # Emit intent
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={"earl_id": "earl-1"},
        )

        # Verify intent in ledger
        events = ledger.get_events()
        assert len(events) == 1
        assert events[0].event_type == "executive.intent.emitted"
        assert events[0].payload["correlation_id"] == str(correlation_id)

        # Emit commit
        await emitter.emit_commit(
            correlation_id=correlation_id,
            result_payload={"new_state": "accepted"},
        )

        # Verify commit in ledger
        events = ledger.get_events()
        assert len(events) == 2
        assert events[1].event_type == "executive.commit.confirmed"
        assert events[1].payload["correlation_id"] == str(correlation_id)

    @pytest.mark.asyncio
    async def test_failure_lifecycle(
        self,
        emitter: TwoPhaseEventEmitter,
        ledger: FakeLedger,
    ) -> None:
        """Full failure lifecycle: intent → operation failure → failure recorded."""
        correlation_id = await emitter.emit_intent(
            operation_type="judicial.panel.convene",
            actor_id="archon-42",
            target_entity_id="panel-001",
            intent_payload={},
        )

        await emitter.emit_failure(
            correlation_id=correlation_id,
            failure_reason="QUORUM_NOT_MET",
            failure_details={"required": 5, "present": 3},
        )

        events = ledger.get_events()
        assert len(events) == 2
        assert events[0].event_type == "judicial.intent.emitted"
        assert events[1].event_type == "judicial.failure.recorded"
        assert events[1].payload["failure_reason"] == "QUORUM_NOT_MET"


class TestTwoPhaseExecutionIntegration:
    """Integration tests for TwoPhaseExecution context manager."""

    @pytest.mark.asyncio
    async def test_execution_success_lifecycle(
        self,
        emitter: TwoPhaseEventEmitter,
        ledger: FakeLedger,
    ) -> None:
        """TwoPhaseExecution should emit intent and commit."""
        async with TwoPhaseExecution(
            emitter=emitter,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={"earl_id": "earl-1"},
        ) as execution:
            # Verify intent emitted before operation
            events = ledger.get_events()
            assert len(events) == 1
            assert events[0].event_type == "executive.intent.emitted"

            execution.set_result({"new_state": "accepted"})

        # Verify commit after exit
        events = ledger.get_events()
        assert len(events) == 2
        assert events[1].event_type == "executive.commit.confirmed"

    @pytest.mark.asyncio
    async def test_execution_failure_lifecycle(
        self,
        emitter: TwoPhaseEventEmitter,
        ledger: FakeLedger,
    ) -> None:
        """TwoPhaseExecution should emit intent and failure on exception."""
        with pytest.raises(ValueError):
            async with TwoPhaseExecution(
                emitter=emitter,
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            ):
                raise ValueError("Operation failed")

        events = ledger.get_events()
        assert len(events) == 2
        assert events[0].event_type == "executive.intent.emitted"
        assert events[1].event_type == "executive.failure.recorded"


class TestConcurrentTwoPhaseOperations:
    """Tests for concurrent two-phase operations."""

    @pytest.mark.asyncio
    async def test_concurrent_intents_tracked_independently(
        self,
        emitter: TwoPhaseEventEmitter,
        ledger: FakeLedger,
    ) -> None:
        """Multiple concurrent intents should be tracked independently."""
        id1 = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-1",
            target_entity_id="task-001",
            intent_payload={},
        )
        id2 = await emitter.emit_intent(
            operation_type="judicial.panel.convene",
            actor_id="archon-2",
            target_entity_id="panel-001",
            intent_payload={},
        )

        # Both pending
        assert await emitter.get_pending_intent(id1) is not None
        assert await emitter.get_pending_intent(id2) is not None

        # Commit first
        await emitter.emit_commit(id1, {"result": "accepted"})

        # First resolved, second still pending
        assert await emitter.get_pending_intent(id1) is None
        assert await emitter.get_pending_intent(id2) is not None

        # Fail second
        await emitter.emit_failure(id2, "ERROR", {})

        # Both resolved
        assert await emitter.get_pending_intent(id1) is None
        assert await emitter.get_pending_intent(id2) is None

        # Verify all events in ledger
        events = ledger.get_events()
        assert len(events) == 4

    @pytest.mark.asyncio
    async def test_nested_executions_independent_outcomes(
        self,
        emitter: TwoPhaseEventEmitter,
        ledger: FakeLedger,
    ) -> None:
        """Nested executions should have independent outcomes."""
        async with TwoPhaseExecution(
            emitter=emitter,
            operation_type="executive.workflow.start",
            actor_id="archon-42",
            target_entity_id="workflow-001",
            intent_payload={},
        ) as outer:
            # Outer intent emitted
            outer_events = ledger.get_events()
            assert len(outer_events) == 1

            async with TwoPhaseExecution(
                emitter=emitter,
                operation_type="executive.task.execute",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            ) as inner:
                inner.set_result({"done": True})

            # Inner commit emitted
            inner_events = ledger.get_events()
            assert len(inner_events) == 3  # outer intent + inner intent + inner commit

            outer.set_result({"completed": True})

        # Outer commit emitted
        final_events = ledger.get_events()
        assert len(final_events) == 4


class TestOrphanDetectionIntegration:
    """Integration tests for orphan detection."""

    @pytest.mark.asyncio
    async def test_detects_and_resolves_orphan(
        self,
        emitter: TwoPhaseEventEmitter,
        orphan_detector: OrphanIntentDetector,
        time_authority: FakeTimeAuthority,
        ledger: FakeLedger,
    ) -> None:
        """OrphanIntentDetector should detect and resolve orphaned intents."""
        # Emit intent
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        # No orphans yet (within timeout)
        orphans = await orphan_detector.scan_and_resolve_orphans()
        assert orphans == []

        # Advance time past timeout
        time_authority.advance(timedelta(minutes=10))

        # Now should detect orphan
        orphans = await orphan_detector.scan_and_resolve_orphans()
        assert len(orphans) == 1
        assert orphans[0].correlation_id == correlation_id

        # Verify failure emitted to ledger
        events = ledger.get_events()
        assert len(events) == 2  # intent + failure
        assert events[1].event_type == "executive.failure.recorded"
        assert events[1].payload["failure_reason"] == "ORPHAN_TIMEOUT"


class TestGapDetectionIntegration:
    """Integration tests for gap detection."""

    @pytest.mark.asyncio
    async def test_detects_orphan_via_gap_detector(
        self,
        emitter: TwoPhaseEventEmitter,
        gap_detector: TwoPhaseGapDetector,
        time_authority: FakeTimeAuthority,
        ledger: FakeLedger,
    ) -> None:
        """TwoPhaseGapDetector should detect orphaned intents in ledger."""
        # Emit intent
        await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        # No violations yet (within timeout)
        violations = await gap_detector.verify_two_phase_completeness()
        assert violations == []

        # Advance time past timeout
        time_authority.advance(timedelta(minutes=10))

        # Now should detect violation
        violations = await gap_detector.verify_two_phase_completeness()
        assert len(violations) == 1

    @pytest.mark.asyncio
    async def test_no_violation_for_committed_intent(
        self,
        emitter: TwoPhaseEventEmitter,
        gap_detector: TwoPhaseGapDetector,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """No violation when intent has corresponding commit."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        await emitter.emit_commit(correlation_id, {"done": True})

        # Advance time past timeout
        time_authority.advance(timedelta(minutes=10))

        # No violations - intent was committed
        violations = await gap_detector.verify_two_phase_completeness()
        assert violations == []


class TestKnightObservabilityIntegration:
    """Integration tests for Knight observability."""

    @pytest.mark.asyncio
    async def test_knight_can_observe_intent_immediately(
        self,
        emitter: TwoPhaseEventEmitter,
        ledger: FakeLedger,
    ) -> None:
        """Knight should be able to observe intent event immediately."""
        async with TwoPhaseExecution(
            emitter=emitter,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={"earl_id": "earl-1"},
        ):
            # Knight observes: intent is in ledger BEFORE operation body
            events = ledger.get_events()
            assert len(events) == 1
            intent = events[0]
            assert intent.event_type == "executive.intent.emitted"
            assert intent.actor_id == "archon-42"
            assert intent.payload["target_entity_id"] == "task-001"

    @pytest.mark.asyncio
    async def test_knight_can_query_intent_outcome_pair(
        self,
        emitter: TwoPhaseEventEmitter,
        gap_detector: TwoPhaseGapDetector,
        ledger: FakeLedger,
    ) -> None:
        """Knight should be able to query intent-outcome pairs."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        await emitter.emit_commit(correlation_id, {"new_state": "accepted"})

        # Knight queries the pair
        pair = await gap_detector.get_intent_outcome_pair(str(correlation_id))

        assert pair is not None
        assert pair["intent"] is not None
        assert pair["outcome"] is not None
        assert pair["is_pending"] is False

    @pytest.mark.asyncio
    async def test_knight_sees_pending_intent(
        self,
        emitter: TwoPhaseEventEmitter,
        gap_detector: TwoPhaseGapDetector,
    ) -> None:
        """Knight should see intent as pending before outcome."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        # Query before commit
        pair = await gap_detector.get_intent_outcome_pair(str(correlation_id))

        assert pair is not None
        assert pair["intent"] is not None
        assert pair["outcome"] is None
        assert pair["is_pending"] is True
