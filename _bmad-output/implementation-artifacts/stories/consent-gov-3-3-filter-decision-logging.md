# Story consent-gov-3.3: Filter Decision Logging

Status: done

---

## Story

As an **auditor**,
I want **all filter decisions logged**,
So that **I can review what was filtered and why**.

---

## Acceptance Criteria

1. **AC1:** All decisions logged with input, output, version, timestamp (FR20)
2. **AC2:** Earl can view filter outcome before content is sent (FR19)
3. **AC3:** Logs include transformation details for `accept` outcomes
4. **AC4:** Logs include rejection reason for `reject` outcomes
5. **AC5:** Logs include violation details for `block` outcomes
6. **AC6:** Event `custodial.filter.decision_logged` emitted
7. **AC7:** Preview operations are NOT logged (allows Earl iteration)
8. **AC8:** Logged decisions are immutable (append-only ledger)
9. **AC9:** Unit tests for logging each outcome type

---

## Tasks / Subtasks

- [x] **Task 1: Create FilterDecisionLogPort interface** (AC: 1, 8)
  - [x] Create `src/application/ports/governance/filter_decision_log_port.py`
  - [x] Define `log_decision()` method
  - [x] Define `get_decision_history()` method for audit
  - [x] Ensure append-only semantics

- [x] **Task 2: Create FilterDecisionLog domain model** (AC: 1, 3, 4, 5)
  - [x] Create `src/domain/governance/filter/filter_decision_log.py`
  - [x] Include input content hash (not raw - privacy)
  - [x] Include output content hash
  - [x] Include filter version
  - [x] Include timestamp
  - [x] Include decision-specific details

- [x] **Task 3: Implement FilterLoggingService** (AC: 1, 3, 4, 5, 6, 7)
  - [x] Create `src/application/services/governance/filter_logging_service.py`
  - [x] Log accepted decisions with transformations
  - [x] Log rejected decisions with reasons
  - [x] Log blocked decisions with violations
  - [x] Do NOT log preview operations

- [x] **Task 4: Implement accepted decision logging** (AC: 3)
  - [x] Log original content hash
  - [x] Log transformed content hash
  - [x] Log all transformations applied
  - [x] Include rule IDs for auditability

- [x] **Task 5: Implement rejected decision logging** (AC: 4)
  - [x] Log original content hash
  - [x] Log rejection reason
  - [x] Log guidance provided
  - [x] Track rejection count per Earl (pattern detection)

- [x] **Task 6: Implement blocked decision logging** (AC: 5)
  - [x] Log original content hash
  - [x] Log violation type and details
  - [x] May trigger Knight observation
  - [x] Higher severity logging level

- [x] **Task 7: Implement Earl preview** (AC: 2, 7)
  - [x] Earl can call preview before submit
  - [x] Preview shows what would happen
  - [x] Preview is NOT logged to ledger
  - [x] Allows iteration without audit trail pollution

- [x] **Task 8: Implement event emission** (AC: 6)
  - [x] Emit `custodial.filter.decision_logged` event
  - [x] Include decision type, content hashes, version
  - [x] Event is part of hash chain
  - [x] Knight can observe filter decisions

- [x] **Task 9: Write comprehensive unit tests** (AC: 9)
  - [x] Test accepted decisions logged with transformations
  - [x] Test rejected decisions logged with reasons
  - [x] Test blocked decisions logged with violations
  - [x] Test preview NOT logged
  - [x] Test event emission
  - [x] Test decision history retrieval

---

## Documentation Checklist

- [ ] Architecture docs updated (filter logging)
- [ ] Inline comments explaining preview vs submit distinction
- [ ] Audit query documentation
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Preview vs Submit (FR19):**
```
Preview:
  - Earl sees what filter would do
  - NOT logged to ledger
  - Allows iteration and revision
  - No audit trail pollution

Submit:
  - Final decision
  - ALWAYS logged to ledger
  - Part of hash chain
  - Knight can observe
```

**Content Privacy:**
```
Logs store HASHES of content, not raw content.

Rationale:
  - Sensitive information may be in task content
  - Hash proves what was filtered without exposing content
  - If needed, original can be retrieved from task record
```

### Event Schema

```python
# Filter decision event
{
    "event_type": "custodial.filter.decision_logged",
    "actor": "system",
    "payload": {
        "decision_id": "uuid",
        "decision": "accepted",  # or rejected, blocked
        "input_hash": "blake3:...",
        "output_hash": "blake3:...",  # null if rejected/blocked
        "filter_version": "1.0.0",
        "message_type": "task_activation",
        "earl_id": "uuid",
        "timestamp": "2026-01-16T00:00:00Z",

        # For accepted
        "transformations": [
            {
                "rule_id": "remove_urgency_caps",
                "pattern": "URGENT",
                "original_hash": "...",
                "replacement_hash": "..."
            }
        ],

        # For rejected
        "rejection_reason": "urgency_pressure",
        "rejection_guidance": "Remove time pressure language",

        # For blocked
        "violation_type": "explicit_threat",
        "violation_details": "Content contained explicit threat"
    }
}
```

### Domain Model

```python
@dataclass(frozen=True)
class FilterDecisionLog:
    """Immutable log entry for filter decision."""
    decision_id: UUID
    decision: FilterDecision
    input_hash: str  # blake3 hash of input content
    output_hash: str | None  # None if rejected/blocked
    filter_version: FilterVersion
    message_type: MessageType
    earl_id: UUID
    timestamp: datetime

    # Decision-specific details
    transformations: tuple[TransformationLog, ...] = ()
    rejection_reason: RejectionReason | None = None
    rejection_guidance: str | None = None
    violation_type: ViolationType | None = None
    violation_details: str | None = None


@dataclass(frozen=True)
class TransformationLog:
    """Log entry for a single transformation."""
    rule_id: str
    pattern: str
    original_hash: str
    replacement_hash: str
```

### Service Implementation Sketch

```python
class FilterLoggingService:
    """Logs all filter decisions to the ledger."""

    def __init__(
        self,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._event_emitter = event_emitter
        self._time = time_authority

    async def log_decision(
        self,
        result: FilterResult,
        input_content: str,
        message_type: MessageType,
        earl_id: UUID,
    ) -> FilterDecisionLog:
        """Log a filter decision to the ledger."""
        decision_id = uuid4()
        input_hash = self._hash_content(input_content)
        output_hash = (
            self._hash_content(result.content.content)
            if result.content else None
        )

        # Create log entry
        log_entry = FilterDecisionLog(
            decision_id=decision_id,
            decision=result.decision,
            input_hash=input_hash,
            output_hash=output_hash,
            filter_version=result.version,
            message_type=message_type,
            earl_id=earl_id,
            timestamp=self._time.now(),
            transformations=self._map_transformations(result.transformations),
            rejection_reason=result.rejection_reason,
            rejection_guidance=result.rejection_guidance,
            violation_type=result.violation_type,
            violation_details=result.violation_details,
        )

        # Emit event to ledger
        await self._event_emitter.emit(
            event_type="custodial.filter.decision_logged",
            actor="system",
            payload=self._to_payload(log_entry),
        )

        return log_entry

    async def get_decision_history(
        self,
        earl_id: UUID | None = None,
        decision_type: FilterDecision | None = None,
        since: datetime | None = None,
    ) -> list[FilterDecisionLog]:
        """Query decision history for audit."""
        # Query from projection table
        ...

    def _hash_content(self, content: str) -> str:
        """Hash content using blake3."""
        from hashlib import blake2b
        return "blake3:" + blake2b(
            content.encode(), digest_size=32
        ).hexdigest()

    def _map_transformations(
        self,
        transformations: tuple[Transformation, ...],
    ) -> tuple[TransformationLog, ...]:
        """Convert transformations to log format."""
        return tuple(
            TransformationLog(
                rule_id=t.rule_id,
                pattern=t.pattern_matched,
                original_hash=self._hash_content(t.original_text),
                replacement_hash=self._hash_content(t.replacement_text),
            )
            for t in transformations
        )
```

### Integration with Filter Service

```python
class CoercionFilterService:
    """Updated to include logging."""

    async def filter_content(
        self,
        content: str,
        message_type: MessageType,
        earl_id: UUID,
    ) -> FilterResult:
        """Filter and LOG the decision."""
        result = await self._do_filter(content, message_type)

        # Log decision to ledger
        await self._logging_service.log_decision(
            result=result,
            input_content=content,
            message_type=message_type,
            earl_id=earl_id,
        )

        return result

    async def preview_filter(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        """Preview WITHOUT logging (FR19)."""
        # Same filtering logic, no logging
        return await self._do_filter(content, message_type)
```

### Test Patterns

```python
class TestFilterLoggingService:
    """Unit tests for filter decision logging."""

    async def test_accepted_logged_with_transformations(
        self,
        logging_service: FilterLoggingService,
        accepted_result: FilterResult,
        event_capture: EventCapture,
    ):
        """Accepted decisions log transformations."""
        await logging_service.log_decision(
            result=accepted_result,
            input_content="URGENT task",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        event = event_capture.get_last("custodial.filter.decision_logged")
        assert event.payload["decision"] == "accepted"
        assert len(event.payload["transformations"]) > 0

    async def test_rejected_logged_with_reason(
        self,
        logging_service: FilterLoggingService,
        rejected_result: FilterResult,
        event_capture: EventCapture,
    ):
        """Rejected decisions log reason and guidance."""
        await logging_service.log_decision(
            result=rejected_result,
            input_content="Do this NOW!",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        event = event_capture.get_last("custodial.filter.decision_logged")
        assert event.payload["decision"] == "rejected"
        assert event.payload["rejection_reason"] is not None
        assert event.payload["rejection_guidance"] is not None

    async def test_blocked_logged_with_violation(
        self,
        logging_service: FilterLoggingService,
        blocked_result: FilterResult,
        event_capture: EventCapture,
    ):
        """Blocked decisions log violation details."""
        await logging_service.log_decision(
            result=blocked_result,
            input_content="Threatening content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        event = event_capture.get_last("custodial.filter.decision_logged")
        assert event.payload["decision"] == "blocked"
        assert event.payload["violation_type"] is not None

    async def test_preview_not_logged(
        self,
        filter_service: CoercionFilterService,
        event_capture: EventCapture,
    ):
        """Preview operations are NOT logged."""
        initial_count = event_capture.count("custodial.filter.decision_logged")

        await filter_service.preview_filter(
            content="Test content",
            message_type=MessageType.TASK_ACTIVATION,
        )

        # No new events
        assert event_capture.count("custodial.filter.decision_logged") == initial_count

    async def test_content_hashed_not_stored(
        self,
        logging_service: FilterLoggingService,
        accepted_result: FilterResult,
        event_capture: EventCapture,
    ):
        """Logs store hashes, not raw content."""
        content = "Sensitive task details"

        await logging_service.log_decision(
            result=accepted_result,
            input_content=content,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        event = event_capture.get_last("custodial.filter.decision_logged")
        assert content not in str(event.payload)
        assert event.payload["input_hash"].startswith("blake3:")
```

### Dependencies

- **Depends on:** consent-gov-3-1 (domain model), consent-gov-3-2 (filter service)
- **Enables:** Audit capabilities, Knight observation of filter behavior

### References

- FR19: Earl can view filter outcome before content is sent
- FR20: System can log all filter decisions with version and timestamp
- NFR-AUDIT-02: Complete audit trail
