# Story consent-gov-2.6: Task Reminders

Status: done

---

## Story

As a **governance system**,
I want **to send neutral reminders at TTL milestones**,
So that **participants are informed without coercion**.

---

## Acceptance Criteria

1. **AC1:** Reminder sent at 50% of TTL (FR11)
2. **AC2:** Reminder sent at 90% of TTL (FR11)
3. **AC3:** Reminders MUST pass through Coercion Filter (mandatory path)
4. **AC4:** Reminder content is informational, NOT pressuring
5. **AC5:** Event `executive.task.reminder_sent` emitted for each reminder
6. **AC6:** Reminder includes TTL milestone and time remaining
7. **AC7:** No reminder sent if task already responded to
8. **AC8:** Reminder uses FilteredContent type (type system prevents bypass)
9. **AC9:** Duplicate reminders prevented for same milestone
10. **AC10:** Unit tests for reminder timing and content

---

## Tasks / Subtasks

- [x] **Task 1: Create TaskReminderPort interface** (AC: 1, 2, 5)
  - [x] Create `src/application/ports/governance/task_reminder_port.py`
  - [x] Define `send_milestone_reminder()` method
  - [x] Define `get_pending_reminders()` method
  - [x] Include milestone tracking (50%, 90%)

- [x] **Task 2: Create ReminderTemplate domain model** (AC: 4)
  - [x] Create `src/domain/governance/task/reminder_template.py`
  - [x] Define neutral reminder text templates
  - [x] No pressuring language (no "urgent", "hurry", "deadline", etc.)
  - [x] Template variables: task_id, ttl_remaining, milestone_pct

- [x] **Task 3: Implement TaskReminderService** (AC: 1, 2, 3, 5, 7, 9)
  - [x] Create `src/application/services/governance/task_reminder_service.py`
  - [x] Implement 50% TTL reminder logic
  - [x] Implement 90% TTL reminder logic
  - [x] Skip if task already actioned (accepted/declined)
  - [x] Track sent reminders to prevent duplicates

- [x] **Task 4: Integrate with Coercion Filter** (AC: 3, 8)
  - [x] All reminder content passes through Coercion Filter
  - [x] Use FilteredContent type for reminder body
  - [x] If filter rejects, log but do not send (constitutional)
  - [x] Filter decision logged to ledger

- [x] **Task 5: Implement 50% TTL reminder** (AC: 1, 4, 6)
  - [x] Calculate 50% of TTL (36h for 72h TTL)
  - [x] Query tasks at or past 50% milestone
  - [x] Generate neutral reminder content
  - [x] Pass through Coercion Filter
  - [x] Send to Cluster if filter accepts
  - [x] Emit `executive.task.reminder_sent` event

- [x] **Task 6: Implement 90% TTL reminder** (AC: 2, 4, 6)
  - [x] Calculate 90% of TTL (64.8h for 72h TTL)
  - [x] Query tasks at or past 90% milestone
  - [x] Generate neutral reminder content
  - [x] Include "final reminder" indicator (still neutral tone)
  - [x] Pass through Coercion Filter
  - [x] Send to Cluster if filter accepts
  - [x] Emit `executive.task.reminder_sent` event

- [x] **Task 7: Implement duplicate prevention** (AC: 9)
  - [x] Track which milestones sent for each task
  - [x] Store in reminder_tracking table or projection
  - [x] Skip if milestone already sent
  - [x] Handle race conditions in batch processing

- [x] **Task 8: Write comprehensive unit tests** (AC: 10)
  - [x] Test reminder sent at 50% TTL
  - [x] Test reminder sent at 90% TTL
  - [x] Test reminder content is neutral
  - [x] Test Coercion Filter integration
  - [x] Test no reminder if task already actioned
  - [x] Test duplicate prevention
  - [x] Test FilteredContent type enforcement

---

## Documentation Checklist

- [x] Architecture docs updated (reminder workflow)
- [x] Inline comments explaining neutral tone requirement
- [x] Reminder template documentation
- [x] N/A - README (internal component)

---

## Implementation Summary

### Files Created

1. **`src/application/ports/governance/task_reminder_port.py`**
   - `ReminderMilestone` enum (HALFWAY=50%, FINAL=90%)
   - `ReminderRecord` - immutable tracking of sent milestones
   - `ReminderSendResult` - result of individual reminder sends
   - `ReminderProcessingResult` - batch processing results
   - `ReminderTrackingPort` - protocol for milestone tracking
   - `TaskReminderPort` - main protocol for reminder operations

2. **`src/domain/governance/task/reminder_template.py`**
   - `BANNED_PHRASES` - frozenset of coercive language patterns
   - `ReminderTemplate` - immutable template with banned word validation
   - `HALFWAY_TEMPLATE` - pre-defined neutral 50% template
   - `FINAL_TEMPLATE` - pre-defined neutral 90% template
   - `get_template_for_milestone()` - template selector
   - `validate_custom_template()` - utility for custom template validation

3. **`src/application/services/governance/task_reminder_service.py`**
   - `TaskReminderService` - main service implementing TaskReminderPort
   - `TaskReminderScheduler` - background scheduler for periodic processing
   - Full Coercion Filter integration (mandatory path, no bypass)
   - Golden Rule compliance: events emitted regardless of filter outcome

### Test Coverage (60 tests)

- `tests/unit/application/ports/governance/test_task_reminder_port.py` (19 tests)
- `tests/unit/domain/governance/task/test_reminder_template.py` (25 tests)
- `tests/unit/application/services/governance/test_task_reminder_service.py` (16 tests)

### Key Architectural Decisions

1. **BANNED_PHRASES vs BANNED_WORDS**: Changed from simple word matching to phrase matching to allow neutral phrases like "no penalty" while blocking coercive phrases like "you must".

2. **Mandatory Coercion Filter**: All reminder content passes through the Coercion Filter. If rejected, the reminder is NOT sent but an event is still emitted (Golden Rule).

3. **Immutable Data Structures**: `ReminderRecord`, `ReminderTemplate`, `ReminderSendResult`, and `ReminderProcessingResult` are all frozen dataclasses.

4. **FilteredContent Type Enforcement**: The service uses the type system to ensure only filtered content can be sent to participants.

---

## Dev Notes

### Key Architectural Decisions

**Coercion Filter is MANDATORY:**
```
Reminder Content → Coercion Filter → Send (if accepted)
                                  → Block (if rejected/blocked)

There is NO path that bypasses the Coercion Filter.
If filter rejects, the reminder is NOT sent.
Constitutional guarantee: NFR-CONST-05
```

**Neutral Tone Templates:**
```
BANNED words/phrases in reminders:
- "urgent", "immediately", "hurry"
- "deadline", "expires", "running out"
- "consequences", "failure", "penalties"
- "must", "required", "mandatory"
- "last chance", "final warning"

ALLOWED tone:
- "This is a status update"
- "Time remaining: X hours"
- "You may respond at your convenience"
- "No response required"
```

### Reminder Milestones

```
Task Created (0h)
    ↓
50% TTL (36h for 72h TTL) → First Reminder
    ↓
90% TTL (64.8h for 72h TTL) → Final Reminder
    ↓
100% TTL (72h) → Auto-decline (story 2-5)
```

### Event Pattern

```python
# Reminder sent event
{
    "event_type": "executive.task.reminder_sent",
    "actor": "system",
    "payload": {
        "task_id": "uuid",
        "cluster_id": "uuid",
        "milestone_pct": 50,  # or 90
        "ttl_remaining_hours": 36,
        "filter_decision": "accepted",
        "sent_at": "timestamp"
    }
}
```

### Domain Models

```python
class ReminderMilestone(Enum):
    """TTL milestone percentages for reminders."""
    HALFWAY = 50
    FINAL = 90


@dataclass(frozen=True)
class ReminderTemplate:
    """Neutral reminder text template."""
    milestone: ReminderMilestone
    template: str  # Must pass Coercion Filter validation

    # Neutral templates only
    HALFWAY_TEMPLATE = """
Task Status Update

Task ID: {task_id}
Status: Awaiting your response
Time remaining: approximately {ttl_remaining_hours} hours

You may respond at your convenience. No action is required.
"""

    FINAL_TEMPLATE = """
Task Status Update

Task ID: {task_id}
Status: Awaiting your response
Time remaining: approximately {ttl_remaining_hours} hours

This is an informational update. The task will auto-transition
after the time period expires. No action is required on your part.
"""


@dataclass
class ReminderRecord:
    """Tracks which reminders have been sent."""
    task_id: UUID
    milestones_sent: set[ReminderMilestone]
    last_sent_at: datetime
```

### Service Implementation Sketch

```python
class TaskReminderService:
    """Sends neutral reminders at TTL milestones."""

    def __init__(
        self,
        task_state_port: TaskStatePort,
        coercion_filter: CoercionFilterPort,
        reminder_tracking: ReminderTrackingPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
        timeout_config: TaskTimeoutConfig,
    ):
        self._task_state = task_state_port
        self._filter = coercion_filter
        self._tracking = reminder_tracking
        self._event_emitter = event_emitter
        self._time = time_authority
        self._config = timeout_config

    async def process_reminders(self) -> ReminderProcessingResult:
        """Process all pending reminders. Called periodically."""
        result = ReminderProcessingResult()

        # Process 50% reminders
        result.halfway = await self._process_milestone(
            milestone=ReminderMilestone.HALFWAY,
            threshold_pct=0.5,
        )

        # Process 90% reminders
        result.final = await self._process_milestone(
            milestone=ReminderMilestone.FINAL,
            threshold_pct=0.9,
        )

        return result

    async def _process_milestone(
        self,
        milestone: ReminderMilestone,
        threshold_pct: float,
    ) -> list[UUID]:
        """Process reminders for a specific milestone."""
        now = self._time.now()
        threshold_time = self._config.activation_ttl * threshold_pct

        # Find tasks past threshold but not yet actioned
        tasks = await self._task_state.find_tasks(
            status=TaskStatus.ROUTED,
            age_at_least=threshold_time,
        )

        sent_ids = []
        for task in tasks:
            # Skip if milestone already sent
            if await self._tracking.has_milestone_sent(task.id, milestone):
                continue

            # Generate and filter content
            success = await self._send_reminder(task, milestone, now)
            if success:
                sent_ids.append(task.id)

        return sent_ids

    async def _send_reminder(
        self,
        task: Task,
        milestone: ReminderMilestone,
        now: datetime,
    ) -> bool:
        """Send reminder through Coercion Filter."""
        # Calculate remaining time
        ttl_remaining = (
            task.created_at + self._config.activation_ttl - now
        )

        # Generate content from template
        content = ReminderTemplate.for_milestone(milestone).format(
            task_id=task.id,
            ttl_remaining_hours=int(ttl_remaining.total_seconds() / 3600),
        )

        # MANDATORY: Pass through Coercion Filter
        filter_result = await self._filter.filter_content(
            content=content,
            message_type=MessageType.REMINDER,
        )

        # Log event regardless of filter outcome
        await self._event_emitter.emit(
            event_type="executive.task.reminder_sent",
            actor="system",
            payload={
                "task_id": str(task.id),
                "cluster_id": str(task.target_cluster_id),
                "milestone_pct": milestone.value,
                "filter_decision": filter_result.decision.value,
            },
        )

        # Only send if filter accepted
        if filter_result.decision == FilterDecision.ACCEPTED:
            await self._send_to_cluster(
                task.target_cluster_id,
                filter_result.content,  # FilteredContent type!
            )
            await self._tracking.mark_milestone_sent(task.id, milestone)
            return True

        return False
```

### Test Patterns

```python
class TestTaskReminderService:
    """Unit tests for task reminder service."""

    async def test_reminder_at_50pct_ttl(
        self,
        reminder_service: TaskReminderService,
        routed_task_at_36h: Task,
    ):
        """Reminder sent when task reaches 50% TTL."""
        result = await reminder_service.process_reminders()

        assert routed_task_at_36h.id in result.halfway

    async def test_reminder_passes_through_filter(
        self,
        reminder_service: TaskReminderService,
        routed_task_at_36h: Task,
        mock_filter: MockCoercionFilter,
    ):
        """All reminders pass through Coercion Filter."""
        await reminder_service.process_reminders()

        assert mock_filter.filter_content.called
        assert mock_filter.last_message_type == MessageType.REMINDER

    async def test_reminder_uses_filtered_content_type(
        self,
        reminder_service: TaskReminderService,
        routed_task_at_36h: Task,
        mock_sender: MockSender,
    ):
        """Sent content is FilteredContent, not raw string."""
        await reminder_service.process_reminders()

        sent_content = mock_sender.last_content
        assert isinstance(sent_content, FilteredContent)

    async def test_reminder_content_is_neutral(
        self,
        reminder_service: TaskReminderService,
        routed_task_at_36h: Task,
        mock_filter: MockCoercionFilter,
    ):
        """Reminder content contains no coercive language."""
        await reminder_service.process_reminders()

        content = mock_filter.last_content
        banned_words = ["urgent", "deadline", "hurry", "must", "required"]
        for word in banned_words:
            assert word.lower() not in content.lower()

    async def test_no_reminder_if_task_actioned(
        self,
        reminder_service: TaskReminderService,
        accepted_task_at_36h: Task,  # Already accepted
    ):
        """No reminder if task already accepted/declined."""
        result = await reminder_service.process_reminders()

        assert accepted_task_at_36h.id not in result.halfway

    async def test_no_duplicate_reminders(
        self,
        reminder_service: TaskReminderService,
        routed_task_at_36h: Task,
    ):
        """Same milestone not sent twice."""
        # First call sends reminder
        await reminder_service.process_reminders()
        # Second call should skip
        result = await reminder_service.process_reminders()

        assert routed_task_at_36h.id not in result.halfway
```

### Dependencies

- **Depends on:** consent-gov-2-5 (TTL config), consent-gov-3-2 (Coercion Filter service)
- **Note:** If Coercion Filter (Epic 3) not yet implemented, use mock/stub

### References

- FR11: Neutral reminders at TTL milestones
- NFR-CONST-05: No path bypasses Coercion Filter
- NFR-UX-01: Anti-engagement (neutral tone)
