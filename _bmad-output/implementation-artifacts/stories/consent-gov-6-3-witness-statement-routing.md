# Story consent-gov-6.3: Witness Statement Routing

Status: done

---

## Story

As a **governance system**,
I want **witness statements routed to Prince Panel queue**,
So that **violations are queued for review**.

---

## Acceptance Criteria

1. **AC1:** Statements routed to Prince Panel queue (FR35)
2. **AC2:** Queue is append-only (no deletion)
3. **AC3:** Statements with POTENTIAL_VIOLATION type routed
4. **AC4:** Normal BRANCH_ACTION statements not queued for panel
5. **AC5:** Event `judicial.witness.statement_queued` emitted
6. **AC6:** Queue includes priority based on observation type
7. **AC7:** Human Operator can view queue
8. **AC8:** Unit tests for routing mechanics

---

## Tasks / Subtasks

- [x] **Task 1: Create WitnessRoutingService** (AC: 1, 3, 4)
  - [x] Create `src/application/services/governance/witness_routing_service.py`
  - [x] Route POTENTIAL_VIOLATION statements to panel queue
  - [x] Skip BRANCH_ACTION statements (normal operations)
  - [x] Route TIMING_ANOMALY for review
  - [x] Route HASH_CHAIN_GAP as critical

- [x] **Task 2: Create PanelQueuePort interface** (AC: 2)
  - [x] Create `src/application/ports/governance/panel_queue_port.py`
  - [x] Define `enqueue_statement()` method
  - [x] Define `get_pending_statements()` method
  - [x] NO `delete_statement()` method (append-only)
  - [x] NO `modify_statement()` method (immutable)

- [x] **Task 3: Implement append-only queue** (AC: 2)
  - [x] Queue stored in append-only ledger
  - [x] Status transitions: PENDING → ACKNOWLEDGED → IN_REVIEW → RESOLVED
  - [x] Resolved statements remain (for audit)
  - [x] No physical deletion

- [x] **Task 4: Implement routing rules** (AC: 3, 4)
  - [x] POTENTIAL_VIOLATION → queue (review needed)
  - [x] TIMING_ANOMALY → queue (investigation needed)
  - [x] HASH_CHAIN_GAP → queue with CRITICAL priority
  - [x] BRANCH_ACTION → no queue (normal operation)

- [x] **Task 5: Implement priority assignment** (AC: 6)
  - [x] CRITICAL: hash chain gaps, integrity issues
  - [x] HIGH: consent violations, coercion blocked
  - [x] MEDIUM: timing anomalies
  - [x] LOW: other potential violations
  - [x] Priority affects queue ordering

- [x] **Task 6: Implement queue event emission** (AC: 5)
  - [x] Emit `judicial.witness.statement_queued`
  - [x] Include statement_id, priority, queued_at
  - [x] Knight observes all queuing events
  - [x] Panel notified of new items

- [x] **Task 7: Implement queue viewing** (AC: 7)
  - [x] Human Operator can view pending queue
  - [x] Filter by priority, date range
  - [x] No modification via view endpoint
  - [x] Read-only access to queue

- [x] **Task 8: Write comprehensive unit tests** (AC: 8)
  - [x] Test violation statements queued
  - [x] Test branch actions not queued
  - [x] Test queue is append-only
  - [x] Test priority assignment
  - [x] Test queued event emitted
  - [x] Test queue viewing

---

## Documentation Checklist

- [x] Architecture docs updated (routing rules)
- [x] Routing decision tree documented
- [x] Inline comments explaining queue semantics
- [x] N/A - README (internal component)

---

## Dev Agent Record

### Implementation Plan
Implemented witness statement routing to Prince Panel queue with:
1. Domain models for queue (QueuePriority, QueueItemStatus, QueuedStatement)
2. PanelQueuePort interface with append-only semantics (no delete/modify)
3. WitnessRoutingService with routing rules and priority assignment
4. Two-phase event emission for Knight observability
5. Comprehensive unit tests covering all acceptance criteria

### Debug Log
- No blocking issues encountered
- All 51 unit tests pass (48 original + 3 added in code review)
- All witness/queue related tests pass (including existing witness domain tests)
- Code review fixes applied: tuple type for `who` field, date range filtering test, get_item_by_id tests

### Completion Notes
- Created domain models in `src/domain/governance/queue/`
- Created PanelQueuePort in `src/application/ports/governance/`
- Created WitnessRoutingService in `src/application/services/governance/`
- 48 new unit tests covering routing rules, priority, events, queue viewing
- Follows hexagonal architecture patterns
- Uses TimeAuthorityProtocol for testable timestamps
- Uses TwoPhaseEventEmitterPort for Knight observability

---

## File List

### New Files Created
- `src/domain/governance/queue/__init__.py`
- `src/domain/governance/queue/priority.py`
- `src/domain/governance/queue/status.py`
- `src/domain/governance/queue/queued_statement.py`
- `src/application/ports/governance/panel_queue_port.py`
- `src/application/services/governance/witness_routing_service.py`
- `tests/unit/domain/governance/queue/__init__.py`
- `tests/unit/domain/governance/queue/test_queue_models.py`
- `tests/unit/application/services/governance/test_witness_routing_service.py`

### Modified Files
- `src/application/ports/governance/__init__.py` (added PanelQueuePort export)
- `src/application/services/governance/__init__.py` (added WitnessRoutingService exports)

---

## Change Log

- 2026-01-17: Story implementation complete - all 8 tasks completed, 48 unit tests passing
- 2026-01-17: Code review fixes - 51 tests passing, HARDENING-1 compliance (tuple for who field)

---

## Dev Notes

### Key Architectural Decisions

**Routing Rules:**
```
Observation Type       │ Route to Panel │ Priority
───────────────────────┼────────────────┼──────────
POTENTIAL_VIOLATION    │ Yes            │ Based on content
TIMING_ANOMALY         │ Yes            │ MEDIUM
HASH_CHAIN_GAP         │ Yes            │ CRITICAL
BRANCH_ACTION          │ No             │ N/A

Why not all statements?
  - BRANCH_ACTION is normal operation
  - Panel would be overwhelmed with noise
  - Panel reviews violations, not normal activity
  - Normal activity still in ledger (auditable)
```

**Append-Only Queue:**
```
Why can't we delete from queue?
  - Evidence must be preserved
  - Deletion could suppress violations
  - Audit trail must be complete
  - Resolution is a status change, not deletion

Queue Item Lifecycle:
  PENDING → ACKNOWLEDGED → IN_REVIEW → RESOLVED
            (Operator)     (Panel)     (Finding issued)

Resolved items remain in queue (historical record)
```

### Domain Models

```python
class QueuePriority(Enum):
    """Priority for panel queue items."""
    CRITICAL = "critical"  # Integrity issues
    HIGH = "high"          # Consent/coercion violations
    MEDIUM = "medium"      # Timing anomalies
    LOW = "low"            # Other observations


class QueueItemStatus(Enum):
    """Status of queued statement."""
    PENDING = "pending"            # Waiting for acknowledgment
    ACKNOWLEDGED = "acknowledged"  # Operator saw it
    IN_REVIEW = "in_review"        # Panel reviewing
    RESOLVED = "resolved"          # Finding issued


@dataclass(frozen=True)
class QueuedStatement:
    """Statement queued for panel review."""
    queue_item_id: UUID
    statement_id: UUID
    statement: WitnessStatement
    priority: QueuePriority
    status: QueueItemStatus
    queued_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    finding_id: UUID | None  # Link to panel finding


# Routing rules
ROUTING_RULES: dict[ObservationType, bool] = {
    ObservationType.POTENTIAL_VIOLATION: True,   # Route
    ObservationType.TIMING_ANOMALY: True,        # Route
    ObservationType.HASH_CHAIN_GAP: True,        # Route (critical)
    ObservationType.BRANCH_ACTION: False,        # Don't route
}


def determine_priority(
    statement: WitnessStatement,
) -> QueuePriority:
    """Determine queue priority for statement."""

    if statement.observation_type == ObservationType.HASH_CHAIN_GAP:
        return QueuePriority.CRITICAL

    # Check content for severity indicators
    content = statement.content.what.lower()

    if any(word in content for word in ["consent", "coercion", "blocked"]):
        return QueuePriority.HIGH

    if statement.observation_type == ObservationType.TIMING_ANOMALY:
        return QueuePriority.MEDIUM

    return QueuePriority.LOW
```

### Service Implementation Sketch

```python
class WitnessRoutingService:
    """Routes witness statements to appropriate queues."""

    def __init__(
        self,
        panel_queue: PanelQueuePort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._queue = panel_queue
        self._event_emitter = event_emitter
        self._time = time_authority

    async def route_statement(
        self,
        statement: WitnessStatement,
    ) -> bool:
        """Route statement to panel queue if needed.

        Returns True if queued, False if not applicable.
        """
        # Check routing rules
        should_route = ROUTING_RULES.get(
            statement.observation_type,
            False,
        )

        if not should_route:
            return False

        # Determine priority
        priority = determine_priority(statement)

        # Create queue item
        now = self._time.now()
        queued_statement = QueuedStatement(
            queue_item_id=uuid4(),
            statement_id=statement.statement_id,
            statement=statement,
            priority=priority,
            status=QueueItemStatus.PENDING,
            queued_at=now,
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )

        # Enqueue
        await self._queue.enqueue_statement(queued_statement)

        # Emit event
        await self._event_emitter.emit(
            event_type="judicial.witness.statement_queued",
            actor="witness_router",
            payload={
                "queue_item_id": str(queued_statement.queue_item_id),
                "statement_id": str(statement.statement_id),
                "observation_type": statement.observation_type.value,
                "priority": priority.value,
                "queued_at": now.isoformat(),
            },
        )

        return True


class PanelQueuePort(Protocol):
    """Port for panel queue operations.

    Append-only by design: no delete/modify methods.
    """

    async def enqueue_statement(
        self,
        item: QueuedStatement,
    ) -> None:
        """Add statement to queue."""
        ...

    async def get_pending_statements(
        self,
        priority: QueuePriority | None = None,
    ) -> list[QueuedStatement]:
        """Get pending statements, optionally filtered by priority."""
        ...

    async def acknowledge_statement(
        self,
        queue_item_id: UUID,
        operator_id: UUID,
    ) -> QueuedStatement:
        """Mark statement as acknowledged (status change, not deletion)."""
        ...

    async def mark_in_review(
        self,
        queue_item_id: UUID,
        panel_id: UUID,
    ) -> QueuedStatement:
        """Mark statement as under panel review."""
        ...

    async def mark_resolved(
        self,
        queue_item_id: UUID,
        finding_id: UUID,
    ) -> QueuedStatement:
        """Mark statement as resolved with finding."""
        ...

    # Intentionally NOT defined:
    # - delete_statement()
    # - modify_statement()
```

### Event Pattern

```python
# Statement queued event
{
    "event_type": "judicial.witness.statement_queued",
    "actor": "witness_router",
    "payload": {
        "queue_item_id": "uuid",
        "statement_id": "uuid",
        "observation_type": "potential_violation",
        "priority": "high",
        "queued_at": "2026-01-16T00:00:00Z"
    }
}

# Statement acknowledged event
{
    "event_type": "judicial.queue.statement_acknowledged",
    "actor": "operator-uuid",
    "payload": {
        "queue_item_id": "uuid",
        "acknowledged_at": "2026-01-16T00:00:00Z"
    }
}
```

### Test Patterns

```python
class TestWitnessRoutingService:
    """Unit tests for witness statement routing."""

    async def test_violation_statements_queued(
        self,
        routing_service: WitnessRoutingService,
        panel_queue: FakePanelQueue,
    ):
        """Potential violation statements are queued."""
        statement = create_statement(
            observation_type=ObservationType.POTENTIAL_VIOLATION,
        )

        result = await routing_service.route_statement(statement)

        assert result is True
        queued = await panel_queue.get_pending_statements()
        assert len(queued) == 1

    async def test_branch_actions_not_queued(
        self,
        routing_service: WitnessRoutingService,
        panel_queue: FakePanelQueue,
    ):
        """Normal branch actions are not queued."""
        statement = create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
        )

        result = await routing_service.route_statement(statement)

        assert result is False
        queued = await panel_queue.get_pending_statements()
        assert len(queued) == 0

    async def test_hash_chain_gap_is_critical(
        self,
        routing_service: WitnessRoutingService,
        panel_queue: FakePanelQueue,
    ):
        """Hash chain gaps get CRITICAL priority."""
        statement = create_statement(
            observation_type=ObservationType.HASH_CHAIN_GAP,
        )

        await routing_service.route_statement(statement)

        queued = await panel_queue.get_pending_statements()
        assert queued[0].priority == QueuePriority.CRITICAL

    async def test_queued_event_emitted(
        self,
        routing_service: WitnessRoutingService,
        event_capture: EventCapture,
    ):
        """Queue event is emitted when statement queued."""
        statement = create_statement(
            observation_type=ObservationType.POTENTIAL_VIOLATION,
        )

        await routing_service.route_statement(statement)

        event = event_capture.get_last("judicial.witness.statement_queued")
        assert event is not None


class TestPanelQueuePort:
    """Unit tests for panel queue port."""

    def test_no_delete_method(self):
        """Queue port has no delete method."""
        assert not hasattr(PanelQueuePort, "delete_statement")

    async def test_resolved_items_remain(
        self,
        panel_queue: FakePanelQueue,
        queued_statement: QueuedStatement,
    ):
        """Resolved items remain in queue (not deleted)."""
        await panel_queue.enqueue_statement(queued_statement)

        await panel_queue.mark_resolved(
            queue_item_id=queued_statement.queue_item_id,
            finding_id=uuid4(),
        )

        # Item still exists, just with resolved status
        all_items = await panel_queue.get_all_items()
        assert any(
            item.queue_item_id == queued_statement.queue_item_id
            for item in all_items
        )
```

### Dependencies

- **Depends on:** consent-gov-6-1 (witness domain), consent-gov-6-2 (observation)
- **Enables:** consent-gov-6-4 (prince panel), consent-gov-6-5 (panel findings)

### References

- FR35: System can route witness statements to Prince Panel queue
