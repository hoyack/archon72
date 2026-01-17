# Story consent-gov-9.4: State Transition Logging

Status: ready-for-dev

---

## Story

As an **auditor**,
I want **all state transitions logged with full context**,
So that **I can trace what happened and why**.

---

## Acceptance Criteria

1. **AC1:** All transitions logged with timestamp and actor (FR59)
2. **AC2:** Reason/trigger included in log
3. **AC3:** No modification of logs (append-only) (FR60)
4. **AC4:** Event `audit.transition.logged` emitted for each transition
5. **AC5:** Transition log includes from_state and to_state
6. **AC6:** Transition log references triggering event
7. **AC7:** All entity types logged consistently
8. **AC8:** Unit tests for log completeness

---

## Tasks / Subtasks

- [ ] **Task 1: Create TransitionLog domain model** (AC: 1, 2, 5)
  - [ ] Create `src/domain/governance/audit/transition_log.py`
  - [ ] Include from_state, to_state
  - [ ] Include timestamp, actor
  - [ ] Include reason, triggering_event_id

- [ ] **Task 2: Create TransitionLoggingService** (AC: 1, 4)
  - [ ] Create `src/application/services/governance/transition_logging_service.py`
  - [ ] Log all state transitions
  - [ ] Emit `audit.transition.logged` events
  - [ ] Coordinate with all entity services

- [ ] **Task 3: Create TransitionLogPort interface** (AC: 1, 3)
  - [ ] Create port for logging operations
  - [ ] Define `log_transition()` method
  - [ ] Define `get_transitions()` method
  - [ ] NO modify/delete methods (append-only)

- [ ] **Task 4: Implement timestamp and actor logging** (AC: 1)
  - [ ] Capture exact timestamp (TimeAuthority)
  - [ ] Capture actor (who initiated)
  - [ ] Include system actor for auto-transitions
  - [ ] Millisecond precision

- [ ] **Task 5: Implement reason/trigger logging** (AC: 2, 6)
  - [ ] Log reason for transition
  - [ ] Reference triggering event
  - [ ] Include event_id for tracing
  - [ ] Human-readable reason text

- [ ] **Task 6: Implement append-only enforcement** (AC: 3)
  - [ ] No update method exists
  - [ ] No delete method exists
  - [ ] Only append new logs
  - [ ] Historical logs immutable

- [ ] **Task 7: Implement consistent logging** (AC: 7)
  - [ ] Task state transitions
  - [ ] Legitimacy band transitions
  - [ ] System state transitions
  - [ ] All use same format

- [ ] **Task 8: Write comprehensive unit tests** (AC: 8)
  - [ ] Test timestamp captured
  - [ ] Test actor captured
  - [ ] Test reason captured
  - [ ] Test no modification possible
  - [ ] Test all entity types logged

---

## Documentation Checklist

- [ ] Architecture docs updated (logging format)
- [ ] Audit trail guide
- [ ] Inline comments explaining immutability
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Why Comprehensive Logging?**
```
Audit requires complete history:
  - What changed?
  - When did it change?
  - Who caused the change?
  - Why did it change?

Every transition logged:
  - Task state changes
  - Legitimacy band changes
  - System state changes
  - All observable changes
```

**Append-Only Logs:**
```
FR60: No modification of logs

Why?
  - Audit requires immutability
  - Cannot rewrite history
  - Trust requires permanence
  - Evidence cannot be destroyed

Enforcement:
  - No update_log() method
  - No delete_log() method
  - No modify_log() method
  - Only log_transition() exists
```

**Triggering Event Reference:**
```
NFR-AUDIT-04: Transitions include triggering event reference

Why reference?
  - Trace cause and effect
  - Link to original event
  - Understand context
  - Reconstruct timeline

Format:
  - triggering_event_id: UUID
  - Links to event in ledger
  - Verifiable reference
  - Complete audit trail
```

### Domain Models

```python
class EntityType(Enum):
    """Type of entity being transitioned."""
    TASK = "task"
    LEGITIMACY_BAND = "legitimacy_band"
    SYSTEM = "system"
    CLUSTER = "cluster"
    MOTION = "motion"


@dataclass(frozen=True)
class TransitionLog:
    """Immutable log of a state transition.

    Cannot be modified after creation.
    Append-only storage.
    """
    log_id: UUID
    entity_type: EntityType
    entity_id: UUID
    from_state: str
    to_state: str
    timestamp: datetime
    actor: str  # UUID or "system"
    reason: str
    triggering_event_id: UUID | None

    # Explicitly NOT included (immutable):
    # - modified_at: datetime
    # - modified_by: UUID


@dataclass(frozen=True)
class TransitionQuery:
    """Query parameters for transitions."""
    entity_type: EntityType | None = None
    entity_id: UUID | None = None
    actor: str | None = None
    from_timestamp: datetime | None = None
    to_timestamp: datetime | None = None


class TransitionLogModificationError(ValueError):
    """Raised when log modification is attempted.

    This should never be raised - modification methods don't exist.
    """
    pass
```

### Service Implementation Sketch

```python
class TransitionLoggingService:
    """Logs all state transitions for audit.

    Logs are append-only. NO modification methods exist.
    """

    def __init__(
        self,
        log_port: TransitionLogPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._logs = log_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def log_transition(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        from_state: str,
        to_state: str,
        actor: str,
        reason: str,
        triggering_event_id: UUID | None = None,
    ) -> TransitionLog:
        """Log a state transition.

        This is the ONLY way to add to the log.
        There is no way to modify or delete logs.

        Args:
            entity_type: Type of entity transitioning
            entity_id: ID of the entity
            from_state: State before transition
            to_state: State after transition
            actor: Who/what caused the transition
            reason: Why the transition occurred
            triggering_event_id: Optional reference to triggering event

        Returns:
            TransitionLog (immutable record)
        """
        now = self._time.now()
        log_id = uuid4()

        log = TransitionLog(
            log_id=log_id,
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            timestamp=now,
            actor=actor,
            reason=reason,
            triggering_event_id=triggering_event_id,
        )

        # Append to log (only append operation)
        await self._logs.append(log)

        # Emit logged event
        await self._event_emitter.emit(
            event_type="audit.transition.logged",
            actor=actor,
            payload={
                "log_id": str(log_id),
                "entity_type": entity_type.value,
                "entity_id": str(entity_id),
                "from_state": from_state,
                "to_state": to_state,
                "timestamp": now.isoformat(),
                "actor": actor,
                "reason": reason,
                "triggering_event_id": str(triggering_event_id) if triggering_event_id else None,
            },
        )

        return log

    async def get_transitions(
        self,
        query: TransitionQuery,
    ) -> list[TransitionLog]:
        """Get transitions matching query.

        Read-only operation.

        Args:
            query: Query parameters

        Returns:
            List of matching transition logs
        """
        return await self._logs.query(query)

    async def get_entity_history(
        self,
        entity_type: EntityType,
        entity_id: UUID,
    ) -> list[TransitionLog]:
        """Get complete transition history for entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of entity

        Returns:
            All transitions for entity, in order
        """
        return await self._logs.query(TransitionQuery(
            entity_type=entity_type,
            entity_id=entity_id,
        ))

    # These methods intentionally do not exist:
    # async def update_log(self, ...): ...
    # async def delete_log(self, ...): ...
    # async def modify_log(self, ...): ...


class TransitionLogPort(Protocol):
    """Port for transition log operations.

    APPEND-ONLY. No modification methods.
    """

    async def append(self, log: TransitionLog) -> None:
        """Append transition log (only write operation)."""
        ...

    async def query(
        self,
        query: TransitionQuery,
    ) -> list[TransitionLog]:
        """Query transition logs (read-only)."""
        ...

    async def get_by_id(self, log_id: UUID) -> TransitionLog | None:
        """Get specific log by ID (read-only)."""
        ...

    # Intentionally NOT defined:
    # - update()
    # - delete()
    # - modify()
```

### Integration with Entity Services

```python
# Example: Task state transition logging
class TaskStateService:
    """Manages task state transitions."""

    def __init__(
        self,
        task_port: TaskPort,
        transition_logging: TransitionLoggingService,
    ):
        self._tasks = task_port
        self._logging = transition_logging

    async def transition_task(
        self,
        task_id: UUID,
        to_state: TaskStatus,
        actor: str,
        reason: str,
        triggering_event_id: UUID | None = None,
    ) -> Task:
        """Transition task and log it."""
        task = await self._tasks.get(task_id)
        from_state = task.status

        # Perform transition
        updated_task = await self._tasks.update_status(
            task_id=task_id,
            status=to_state,
        )

        # Log transition
        await self._logging.log_transition(
            entity_type=EntityType.TASK,
            entity_id=task_id,
            from_state=from_state.value,
            to_state=to_state.value,
            actor=actor,
            reason=reason,
            triggering_event_id=triggering_event_id,
        )

        return updated_task


# Example: Legitimacy band transition logging
class LegitimacyService:
    """Manages legitimacy band transitions."""

    async def transition_band(
        self,
        new_band: LegitimacyBand,
        actor: str,
        reason: str,
        triggering_event_id: UUID,
    ) -> LegitimacyBand:
        """Transition band and log it."""
        current = await self._get_current_band()

        # Perform transition
        await self._set_band(new_band)

        # Log transition
        await self._logging.log_transition(
            entity_type=EntityType.LEGITIMACY_BAND,
            entity_id=self._system_id,
            from_state=current.value,
            to_state=new_band.value,
            actor=actor,
            reason=reason,
            triggering_event_id=triggering_event_id,
        )

        return new_band
```

### Event Pattern

```python
# Transition logged
{
    "event_type": "audit.transition.logged",
    "actor": "uuid or system",
    "payload": {
        "log_id": "uuid",
        "entity_type": "task",
        "entity_id": "uuid",
        "from_state": "accepted",
        "to_state": "in_progress",
        "timestamp": "2026-01-16T00:00:00.123Z",
        "actor": "cluster-uuid",
        "reason": "Cluster began work on task",
        "triggering_event_id": "uuid"
    }
}
```

### Test Patterns

```python
class TestTransitionLoggingService:
    """Unit tests for transition logging service."""

    async def test_timestamp_captured(
        self,
        logging_service: TransitionLoggingService,
        task: Task,
    ):
        """Timestamp is captured in log."""
        log = await logging_service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=task.id,
            from_state="accepted",
            to_state="in_progress",
            actor=str(task.cluster_id),
            reason="Test",
        )

        assert log.timestamp is not None

    async def test_actor_captured(
        self,
        logging_service: TransitionLoggingService,
        task: Task,
        cluster: Cluster,
    ):
        """Actor is captured in log."""
        log = await logging_service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=task.id,
            from_state="accepted",
            to_state="in_progress",
            actor=str(cluster.id),
            reason="Test",
        )

        assert log.actor == str(cluster.id)

    async def test_reason_captured(
        self,
        logging_service: TransitionLoggingService,
        task: Task,
    ):
        """Reason is captured in log."""
        reason = "Cluster began work on task"

        log = await logging_service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=task.id,
            from_state="accepted",
            to_state="in_progress",
            actor="test",
            reason=reason,
        )

        assert log.reason == reason

    async def test_triggering_event_captured(
        self,
        logging_service: TransitionLoggingService,
        task: Task,
        triggering_event: EventEnvelope,
    ):
        """Triggering event is captured in log."""
        log = await logging_service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=task.id,
            from_state="accepted",
            to_state="in_progress",
            actor="test",
            reason="Test",
            triggering_event_id=triggering_event.event_id,
        )

        assert log.triggering_event_id == triggering_event.event_id

    async def test_logged_event_emitted(
        self,
        logging_service: TransitionLoggingService,
        task: Task,
        event_capture: EventCapture,
    ):
        """Logged event is emitted."""
        await logging_service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=task.id,
            from_state="accepted",
            to_state="in_progress",
            actor="test",
            reason="Test",
        )

        event = event_capture.get_last("audit.transition.logged")
        assert event is not None


class TestAppendOnlyLogs:
    """Tests ensuring logs are append-only."""

    def test_no_update_method(
        self,
        logging_service: TransitionLoggingService,
    ):
        """No update method exists."""
        assert not hasattr(logging_service, "update_log")
        assert not hasattr(logging_service, "modify_log")

    def test_no_delete_method(
        self,
        logging_service: TransitionLoggingService,
    ):
        """No delete method exists."""
        assert not hasattr(logging_service, "delete_log")
        assert not hasattr(logging_service, "remove_log")

    def test_port_has_no_modification(self):
        """TransitionLogPort has no modification methods."""
        # Port protocol only has append and query
        assert hasattr(TransitionLogPort, "append")
        assert hasattr(TransitionLogPort, "query")
        assert not hasattr(TransitionLogPort, "update")
        assert not hasattr(TransitionLogPort, "delete")


class TestConsistentLogging:
    """Tests for consistent logging across entity types."""

    @pytest.mark.parametrize("entity_type", [
        EntityType.TASK,
        EntityType.LEGITIMACY_BAND,
        EntityType.SYSTEM,
        EntityType.CLUSTER,
        EntityType.MOTION,
    ])
    async def test_all_entity_types_logged(
        self,
        logging_service: TransitionLoggingService,
        entity_type: EntityType,
    ):
        """All entity types can be logged."""
        log = await logging_service.log_transition(
            entity_type=entity_type,
            entity_id=uuid4(),
            from_state="state_a",
            to_state="state_b",
            actor="test",
            reason="Test",
        )

        assert log.entity_type == entity_type

    async def test_all_logs_have_same_structure(
        self,
        logging_service: TransitionLoggingService,
    ):
        """All logs have consistent structure."""
        logs = []

        for entity_type in EntityType:
            log = await logging_service.log_transition(
                entity_type=entity_type,
                entity_id=uuid4(),
                from_state="state_a",
                to_state="state_b",
                actor="test",
                reason="Test",
            )
            logs.append(log)

        # All logs have same fields
        for log in logs:
            assert hasattr(log, "log_id")
            assert hasattr(log, "entity_type")
            assert hasattr(log, "entity_id")
            assert hasattr(log, "from_state")
            assert hasattr(log, "to_state")
            assert hasattr(log, "timestamp")
            assert hasattr(log, "actor")
            assert hasattr(log, "reason")
```

### Dependencies

- **Depends on:** consent-gov-1-1 (event envelope)
- **Enables:** Complete audit trail for all state changes

### References

- FR59: System can log all state transitions with timestamp and actor
- FR60: System can prevent ledger modification (append-only enforcement)
