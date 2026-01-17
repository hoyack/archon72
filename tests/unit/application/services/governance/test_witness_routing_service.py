"""Unit tests for WitnessRoutingService.

Story: consent-gov-6-3: Witness Statement Routing

Tests:
- Violation statements queued (AC1, AC3)
- Branch actions NOT queued (AC4)
- Queue is append-only (AC2)
- Priority assignment (AC6)
- Queued event emitted (AC5)
- Routing rules correctness
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.panel_queue_port import PanelQueuePort
from src.application.ports.governance.two_phase_emitter_port import (
    TwoPhaseEventEmitterPort,
)
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.application.services.governance.witness_routing_service import (
    HIGH_PRIORITY_KEYWORDS,
    ROUTING_RULES,
    WitnessRoutingService,
    determine_priority,
)
from src.domain.governance.queue.priority import QueuePriority
from src.domain.governance.queue.status import QueueItemStatus
from src.domain.governance.queue.queued_statement import QueuedStatement
from src.domain.governance.witness.observation_content import ObservationContent
from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.witness_statement import WitnessStatement


class FakeTimeAuthority(TimeAuthorityProtocol):
    """Fake time authority for testing."""

    def __init__(self, fixed_time: Optional[datetime] = None) -> None:
        self._fixed_time = fixed_time or datetime(
            2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc
        )

    def now(self) -> datetime:
        return self._fixed_time

    def utcnow(self) -> datetime:
        return self._fixed_time

    def monotonic(self) -> float:
        return 0.0


class FakePanelQueue(PanelQueuePort):
    """Fake panel queue for testing."""

    def __init__(self) -> None:
        self._items: list[QueuedStatement] = []
        self._enqueue_error: Optional[Exception] = None

    def set_enqueue_error(self, error: Exception) -> None:
        """Configure queue to raise error on enqueue."""
        self._enqueue_error = error

    async def enqueue_statement(self, item: QueuedStatement) -> None:
        if self._enqueue_error:
            raise self._enqueue_error
        self._items.append(item)

    async def get_pending_statements(
        self,
        priority: Optional[QueuePriority] = None,
    ) -> list[QueuedStatement]:
        items = [i for i in self._items if i.status == QueueItemStatus.PENDING]
        if priority:
            items = [i for i in items if i.priority == priority]
        return items

    async def get_statements_by_status(
        self,
        status: QueueItemStatus,
        since: Optional[datetime] = None,
    ) -> list[QueuedStatement]:
        items = [i for i in self._items if i.status == status]
        if since:
            items = [i for i in items if i.queued_at >= since]
        return items

    async def get_all_items(
        self,
        since: Optional[datetime] = None,
    ) -> list[QueuedStatement]:
        items = self._items
        if since:
            items = [i for i in items if i.queued_at >= since]
        return items

    async def get_item_by_id(
        self,
        queue_item_id: UUID,
    ) -> Optional[QueuedStatement]:
        for item in self._items:
            if item.queue_item_id == queue_item_id:
                return item
        return None

    async def acknowledge_statement(
        self,
        queue_item_id: UUID,
        operator_id: UUID,
        acknowledged_at: datetime,
    ) -> QueuedStatement:
        for i, item in enumerate(self._items):
            if item.queue_item_id == queue_item_id:
                updated = item.with_status(
                    new_status=QueueItemStatus.ACKNOWLEDGED,
                    acknowledged_at=acknowledged_at,
                )
                self._items[i] = updated
                return updated
        raise ValueError(f"Item not found: {queue_item_id}")

    async def mark_in_review(
        self,
        queue_item_id: UUID,
        panel_id: UUID,
    ) -> QueuedStatement:
        for i, item in enumerate(self._items):
            if item.queue_item_id == queue_item_id:
                updated = item.with_status(new_status=QueueItemStatus.IN_REVIEW)
                self._items[i] = updated
                return updated
        raise ValueError(f"Item not found: {queue_item_id}")

    async def mark_resolved(
        self,
        queue_item_id: UUID,
        finding_id: UUID,
        resolved_at: datetime,
    ) -> QueuedStatement:
        for i, item in enumerate(self._items):
            if item.queue_item_id == queue_item_id:
                updated = item.with_status(
                    new_status=QueueItemStatus.RESOLVED,
                    resolved_at=resolved_at,
                    finding_id=finding_id,
                )
                self._items[i] = updated
                return updated
        raise ValueError(f"Item not found: {queue_item_id}")


class FakeEventEmitter(TwoPhaseEventEmitterPort):
    """Fake event emitter for testing."""

    def __init__(self) -> None:
        self._intents: dict[UUID, dict[str, Any]] = {}
        self._commits: list[dict[str, Any]] = []
        self._failures: list[dict[str, Any]] = []

    async def emit_intent(
        self,
        operation_type: str,
        actor_id: str,
        target_entity_id: str,
        intent_payload: dict[str, Any],
    ) -> UUID:
        correlation_id = uuid4()
        self._intents[correlation_id] = {
            "operation_type": operation_type,
            "actor_id": actor_id,
            "target_entity_id": target_entity_id,
            "intent_payload": intent_payload,
        }
        return correlation_id

    async def emit_commit(
        self,
        correlation_id: UUID,
        result_payload: dict[str, Any],
    ) -> None:
        self._commits.append(
            {
                "correlation_id": correlation_id,
                "result_payload": result_payload,
            }
        )
        if correlation_id in self._intents:
            del self._intents[correlation_id]

    async def emit_failure(
        self,
        correlation_id: UUID,
        failure_reason: str,
        failure_details: dict[str, Any],
    ) -> None:
        self._failures.append(
            {
                "correlation_id": correlation_id,
                "failure_reason": failure_reason,
                "failure_details": failure_details,
            }
        )
        if correlation_id in self._intents:
            del self._intents[correlation_id]

    async def get_pending_intent(
        self,
        correlation_id: UUID,
    ) -> dict[str, Any] | None:
        return self._intents.get(correlation_id)

    def get_last_commit(self) -> dict[str, Any] | None:
        """Get the last commit event."""
        return self._commits[-1] if self._commits else None

    def get_commits_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """Get all commits with a specific event type in payload."""
        return [
            c
            for c in self._commits
            if c["result_payload"].get("event_type") == event_type
        ]


def create_statement(
    observation_type: ObservationType = ObservationType.POTENTIAL_VIOLATION,
    what: str = "Task activated without explicit consent",
) -> WitnessStatement:
    """Create a test witness statement."""
    return WitnessStatement(
        statement_id=uuid4(),
        observation_type=observation_type,
        content=ObservationContent(
            what=what,
            when=datetime(2026, 1, 17, 10, 30, tzinfo=timezone.utc),
            who=("actor-uuid-1",),  # Tuple per HARDENING-1 compliance
            where="executive.task_coordination",
            event_type="executive.task.activated",
            event_id=uuid4(),
        ),
        observed_at=datetime(2026, 1, 17, 10, 30, 1, tzinfo=timezone.utc),
        hash_chain_position=42,
    )


class TestRoutingRules:
    """Test routing rules configuration."""

    def test_potential_violation_should_route(self) -> None:
        """POTENTIAL_VIOLATION observations should be routed."""
        assert ROUTING_RULES[ObservationType.POTENTIAL_VIOLATION] is True

    def test_timing_anomaly_should_route(self) -> None:
        """TIMING_ANOMALY observations should be routed."""
        assert ROUTING_RULES[ObservationType.TIMING_ANOMALY] is True

    def test_hash_chain_gap_should_route(self) -> None:
        """HASH_CHAIN_GAP observations should be routed."""
        assert ROUTING_RULES[ObservationType.HASH_CHAIN_GAP] is True

    def test_branch_action_should_not_route(self) -> None:
        """BRANCH_ACTION observations should NOT be routed."""
        assert ROUTING_RULES[ObservationType.BRANCH_ACTION] is False

    def test_all_observation_types_have_rules(self) -> None:
        """All observation types have routing rules defined."""
        for obs_type in ObservationType:
            assert obs_type in ROUTING_RULES


class TestDeterminePriority:
    """Test priority determination function."""

    def test_hash_chain_gap_is_critical(self) -> None:
        """Hash chain gaps get CRITICAL priority."""
        statement = create_statement(
            observation_type=ObservationType.HASH_CHAIN_GAP,
        )
        priority = determine_priority(statement)
        assert priority == QueuePriority.CRITICAL

    def test_consent_keyword_is_high(self) -> None:
        """Content with consent keyword gets HIGH priority."""
        statement = create_statement(
            what="Task activated without explicit consent from Cluster",
        )
        priority = determine_priority(statement)
        assert priority == QueuePriority.HIGH

    def test_coercion_keyword_is_high(self) -> None:
        """Content with coercion keyword gets HIGH priority."""
        statement = create_statement(
            what="Message blocked due to coercion pattern detected",
        )
        priority = determine_priority(statement)
        assert priority == QueuePriority.HIGH

    def test_blocked_keyword_is_high(self) -> None:
        """Content with blocked keyword gets HIGH priority."""
        statement = create_statement(
            what="Action blocked by filter",
        )
        priority = determine_priority(statement)
        assert priority == QueuePriority.HIGH

    def test_timing_anomaly_is_medium(self) -> None:
        """Timing anomalies get MEDIUM priority."""
        statement = create_statement(
            observation_type=ObservationType.TIMING_ANOMALY,
            what="Unexpected timing deviation detected",
        )
        priority = determine_priority(statement)
        assert priority == QueuePriority.MEDIUM

    def test_generic_violation_is_low(self) -> None:
        """Generic violations without keywords get LOW priority."""
        statement = create_statement(
            what="Some pattern matched in observation",
        )
        priority = determine_priority(statement)
        assert priority == QueuePriority.LOW

    def test_high_priority_keywords_exist(self) -> None:
        """High priority keywords set is populated."""
        assert len(HIGH_PRIORITY_KEYWORDS) > 0
        assert "consent" in HIGH_PRIORITY_KEYWORDS
        assert "coercion" in HIGH_PRIORITY_KEYWORDS
        assert "blocked" in HIGH_PRIORITY_KEYWORDS


class TestWitnessRoutingService:
    """Test WitnessRoutingService."""

    @pytest.fixture
    def panel_queue(self) -> FakePanelQueue:
        """Create a fake panel queue."""
        return FakePanelQueue()

    @pytest.fixture
    def event_emitter(self) -> FakeEventEmitter:
        """Create a fake event emitter."""
        return FakeEventEmitter()

    @pytest.fixture
    def time_authority(self) -> FakeTimeAuthority:
        """Create a fake time authority."""
        return FakeTimeAuthority()

    @pytest.fixture
    def routing_service(
        self,
        panel_queue: FakePanelQueue,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> WitnessRoutingService:
        """Create a routing service with fakes."""
        return WitnessRoutingService(
            panel_queue=panel_queue,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

    @pytest.mark.asyncio
    async def test_violation_statements_queued(
        self,
        routing_service: WitnessRoutingService,
        panel_queue: FakePanelQueue,
    ) -> None:
        """Potential violation statements are queued (AC1, AC3)."""
        statement = create_statement(
            observation_type=ObservationType.POTENTIAL_VIOLATION,
        )

        result = await routing_service.route_statement(statement)

        assert result is True
        queued = await panel_queue.get_pending_statements()
        assert len(queued) == 1
        assert queued[0].statement_id == statement.statement_id

    @pytest.mark.asyncio
    async def test_branch_actions_not_queued(
        self,
        routing_service: WitnessRoutingService,
        panel_queue: FakePanelQueue,
    ) -> None:
        """Normal branch actions are NOT queued (AC4)."""
        statement = create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
        )

        result = await routing_service.route_statement(statement)

        assert result is False
        queued = await panel_queue.get_pending_statements()
        assert len(queued) == 0

    @pytest.mark.asyncio
    async def test_timing_anomaly_queued(
        self,
        routing_service: WitnessRoutingService,
        panel_queue: FakePanelQueue,
    ) -> None:
        """Timing anomalies are queued."""
        statement = create_statement(
            observation_type=ObservationType.TIMING_ANOMALY,
        )

        result = await routing_service.route_statement(statement)

        assert result is True
        queued = await panel_queue.get_pending_statements()
        assert len(queued) == 1

    @pytest.mark.asyncio
    async def test_hash_chain_gap_queued(
        self,
        routing_service: WitnessRoutingService,
        panel_queue: FakePanelQueue,
    ) -> None:
        """Hash chain gaps are queued."""
        statement = create_statement(
            observation_type=ObservationType.HASH_CHAIN_GAP,
        )

        result = await routing_service.route_statement(statement)

        assert result is True
        queued = await panel_queue.get_pending_statements()
        assert len(queued) == 1

    @pytest.mark.asyncio
    async def test_hash_chain_gap_is_critical_priority(
        self,
        routing_service: WitnessRoutingService,
        panel_queue: FakePanelQueue,
    ) -> None:
        """Hash chain gaps get CRITICAL priority (AC6)."""
        statement = create_statement(
            observation_type=ObservationType.HASH_CHAIN_GAP,
        )

        await routing_service.route_statement(statement)

        queued = await panel_queue.get_pending_statements()
        assert queued[0].priority == QueuePriority.CRITICAL

    @pytest.mark.asyncio
    async def test_queued_event_emitted(
        self,
        routing_service: WitnessRoutingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Queue event is emitted when statement queued (AC5)."""
        statement = create_statement(
            observation_type=ObservationType.POTENTIAL_VIOLATION,
        )

        await routing_service.route_statement(statement)

        commits = event_emitter.get_commits_by_type(
            "judicial.witness.statement_queued"
        )
        assert len(commits) == 1
        payload = commits[0]["result_payload"]
        assert payload["event_type"] == "judicial.witness.statement_queued"
        assert payload["statement_id"] == str(statement.statement_id)
        assert "priority" in payload
        assert "queued_at" in payload

    @pytest.mark.asyncio
    async def test_no_event_for_branch_action(
        self,
        routing_service: WitnessRoutingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """No event emitted for branch actions (not queued)."""
        statement = create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
        )

        await routing_service.route_statement(statement)

        # No intents, no commits (not routed at all)
        assert len(event_emitter._commits) == 0

    @pytest.mark.asyncio
    async def test_queued_statement_has_pending_status(
        self,
        routing_service: WitnessRoutingService,
        panel_queue: FakePanelQueue,
    ) -> None:
        """Queued statements start with PENDING status."""
        statement = create_statement(
            observation_type=ObservationType.POTENTIAL_VIOLATION,
        )

        await routing_service.route_statement(statement)

        queued = await panel_queue.get_pending_statements()
        assert queued[0].status == QueueItemStatus.PENDING

    @pytest.mark.asyncio
    async def test_failure_emitted_on_queue_error(
        self,
        panel_queue: FakePanelQueue,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Failure event emitted if queue operation fails."""
        panel_queue.set_enqueue_error(Exception("Queue unavailable"))
        routing_service = WitnessRoutingService(
            panel_queue=panel_queue,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        statement = create_statement(
            observation_type=ObservationType.POTENTIAL_VIOLATION,
        )

        with pytest.raises(Exception, match="Queue unavailable"):
            await routing_service.route_statement(statement)

        # Failure event was emitted
        assert len(event_emitter._failures) == 1
        assert event_emitter._failures[0]["failure_reason"] == "QUEUE_FAILED"

    def test_should_route_helper_method(
        self,
        routing_service: WitnessRoutingService,
    ) -> None:
        """should_route helper returns correct values."""
        assert routing_service.should_route(ObservationType.POTENTIAL_VIOLATION) is True
        assert routing_service.should_route(ObservationType.TIMING_ANOMALY) is True
        assert routing_service.should_route(ObservationType.HASH_CHAIN_GAP) is True
        assert routing_service.should_route(ObservationType.BRANCH_ACTION) is False

    def test_get_priority_for_type_helper(
        self,
        routing_service: WitnessRoutingService,
    ) -> None:
        """get_priority_for_type returns base priorities."""
        assert (
            routing_service.get_priority_for_type(ObservationType.HASH_CHAIN_GAP)
            == QueuePriority.CRITICAL
        )
        assert (
            routing_service.get_priority_for_type(ObservationType.TIMING_ANOMALY)
            == QueuePriority.MEDIUM
        )
        assert (
            routing_service.get_priority_for_type(ObservationType.POTENTIAL_VIOLATION)
            == QueuePriority.LOW
        )
        assert (
            routing_service.get_priority_for_type(ObservationType.BRANCH_ACTION) is None
        )


class TestPanelQueuePort:
    """Test panel queue port interface properties."""

    def test_no_delete_method(self) -> None:
        """Queue port has no delete method (AC2)."""
        assert not hasattr(PanelQueuePort, "delete_statement")

    def test_no_modify_method(self) -> None:
        """Queue port has no modify method."""
        assert not hasattr(PanelQueuePort, "modify_statement")

    def test_no_remove_method(self) -> None:
        """Queue port has no remove method."""
        assert not hasattr(PanelQueuePort, "remove_statement")

    @pytest.mark.asyncio
    async def test_resolved_items_remain_in_queue(self) -> None:
        """Resolved items remain in queue (not deleted) (AC2)."""
        queue = FakePanelQueue()
        statement = create_statement()
        finding_id = uuid4()
        resolved_at = datetime.now(timezone.utc)

        # Create and enqueue
        queued = QueuedStatement(
            queue_item_id=uuid4(),
            statement_id=statement.statement_id,
            statement=statement,
            priority=QueuePriority.HIGH,
            status=QueueItemStatus.PENDING,
            queued_at=datetime.now(timezone.utc),
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )
        await queue.enqueue_statement(queued)

        # Resolve
        await queue.mark_resolved(
            queue_item_id=queued.queue_item_id,
            finding_id=finding_id,
            resolved_at=resolved_at,
        )

        # Item still exists with RESOLVED status
        all_items = await queue.get_all_items()
        assert len(all_items) == 1
        assert all_items[0].status == QueueItemStatus.RESOLVED
        assert all_items[0].finding_id == finding_id


class TestQueueViewing:
    """Test queue viewing capabilities (AC7)."""

    @pytest.fixture
    def populated_queue(self) -> FakePanelQueue:
        """Create a queue with multiple items."""
        return FakePanelQueue()

    @pytest.mark.asyncio
    async def test_get_pending_statements(
        self,
        populated_queue: FakePanelQueue,
    ) -> None:
        """Can view pending statements."""
        statement = create_statement()
        queued = QueuedStatement(
            queue_item_id=uuid4(),
            statement_id=statement.statement_id,
            statement=statement,
            priority=QueuePriority.HIGH,
            status=QueueItemStatus.PENDING,
            queued_at=datetime.now(timezone.utc),
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )
        await populated_queue.enqueue_statement(queued)

        pending = await populated_queue.get_pending_statements()

        assert len(pending) == 1
        assert pending[0].queue_item_id == queued.queue_item_id

    @pytest.mark.asyncio
    async def test_filter_by_priority(
        self,
        populated_queue: FakePanelQueue,
    ) -> None:
        """Can filter by priority."""
        # Add HIGH priority item
        high_statement = create_statement()
        high_queued = QueuedStatement(
            queue_item_id=uuid4(),
            statement_id=high_statement.statement_id,
            statement=high_statement,
            priority=QueuePriority.HIGH,
            status=QueueItemStatus.PENDING,
            queued_at=datetime.now(timezone.utc),
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )
        await populated_queue.enqueue_statement(high_queued)

        # Add LOW priority item
        low_statement = create_statement()
        low_queued = QueuedStatement(
            queue_item_id=uuid4(),
            statement_id=low_statement.statement_id,
            statement=low_statement,
            priority=QueuePriority.LOW,
            status=QueueItemStatus.PENDING,
            queued_at=datetime.now(timezone.utc),
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )
        await populated_queue.enqueue_statement(low_queued)

        # Filter by HIGH only
        high_items = await populated_queue.get_pending_statements(
            priority=QueuePriority.HIGH
        )

        assert len(high_items) == 1
        assert high_items[0].priority == QueuePriority.HIGH

    @pytest.mark.asyncio
    async def test_get_all_items_for_audit(
        self,
        populated_queue: FakePanelQueue,
    ) -> None:
        """Can get all items including resolved for audit."""
        statement = create_statement()
        queued = QueuedStatement(
            queue_item_id=uuid4(),
            statement_id=statement.statement_id,
            statement=statement,
            priority=QueuePriority.HIGH,
            status=QueueItemStatus.PENDING,
            queued_at=datetime.now(timezone.utc),
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )
        await populated_queue.enqueue_statement(queued)

        # Resolve the item
        await populated_queue.mark_resolved(
            queue_item_id=queued.queue_item_id,
            finding_id=uuid4(),
            resolved_at=datetime.now(timezone.utc),
        )

        # All items still available
        all_items = await populated_queue.get_all_items()
        assert len(all_items) == 1

    @pytest.mark.asyncio
    async def test_filter_by_date_range(
        self,
        populated_queue: FakePanelQueue,
    ) -> None:
        """Can filter items by date range (AC7)."""
        # Create items at different times
        old_time = datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc)
        new_time = datetime(2026, 1, 17, 10, 0, 0, tzinfo=timezone.utc)

        # Add old item
        old_statement = create_statement()
        old_queued = QueuedStatement(
            queue_item_id=uuid4(),
            statement_id=old_statement.statement_id,
            statement=old_statement,
            priority=QueuePriority.LOW,
            status=QueueItemStatus.PENDING,
            queued_at=old_time,
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )
        await populated_queue.enqueue_statement(old_queued)

        # Add new item
        new_statement = create_statement()
        new_queued = QueuedStatement(
            queue_item_id=uuid4(),
            statement_id=new_statement.statement_id,
            statement=new_statement,
            priority=QueuePriority.HIGH,
            status=QueueItemStatus.PENDING,
            queued_at=new_time,
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )
        await populated_queue.enqueue_statement(new_queued)

        # Filter by date - only items since Jan 15
        since = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        filtered = await populated_queue.get_all_items(since=since)

        assert len(filtered) == 1
        assert filtered[0].queue_item_id == new_queued.queue_item_id

    @pytest.mark.asyncio
    async def test_get_item_by_id(
        self,
        populated_queue: FakePanelQueue,
    ) -> None:
        """Can retrieve specific item by ID."""
        statement = create_statement()
        queued = QueuedStatement(
            queue_item_id=uuid4(),
            statement_id=statement.statement_id,
            statement=statement,
            priority=QueuePriority.HIGH,
            status=QueueItemStatus.PENDING,
            queued_at=datetime.now(timezone.utc),
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )
        await populated_queue.enqueue_statement(queued)

        # Retrieve by ID
        found = await populated_queue.get_item_by_id(queued.queue_item_id)

        assert found is not None
        assert found.queue_item_id == queued.queue_item_id
        assert found.statement_id == statement.statement_id

    @pytest.mark.asyncio
    async def test_get_item_by_id_not_found(
        self,
        populated_queue: FakePanelQueue,
    ) -> None:
        """Returns None when item ID not found."""
        nonexistent_id = uuid4()

        found = await populated_queue.get_item_by_id(nonexistent_id)

        assert found is None
