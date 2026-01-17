# Story consent-gov-2.6: Task Reminders

Status: ready-for-dev

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

- [ ] **Task 1: Create TaskReminderPort interface** (AC: 1, 2, 5)
  - [ ] Create `src/application/ports/governance/task_reminder_port.py`
  - [ ] Define `send_milestone_reminder()` method
  - [ ] Define `get_pending_reminders()` method
  - [ ] Include milestone tracking (50%, 90%)

- [ ] **Task 2: Create ReminderTemplate domain model** (AC: 4)
  - [ ] Create `src/domain/governance/reminder_template.py`
  - [ ] Define neutral reminder text templates
  - [ ] No pressuring language (no "urgent", "hurry", "deadline", etc.)
  - [ ] Template variables: task_id, ttl_remaining, milestone_pct

- [ ] **Task 3: Implement TaskReminderService** (AC: 1, 2, 3, 5, 7, 9)
  - [ ] Create `src/application/services/governance/task_reminder_service.py`
  - [ ] Implement 50% TTL reminder logic
  - [ ] Implement 90% TTL reminder logic
  - [ ] Skip if task already actioned (accepted/declined)
  - [ ] Track sent reminders to prevent duplicates

- [ ] **Task 4: Integrate with Coercion Filter** (AC: 3, 8)
  - [ ] All reminder content passes through Coercion Filter
  - [ ] Use FilteredContent type for reminder body
  - [ ] If filter rejects, log but do not send (constitutional)
  - [ ] Filter decision logged to ledger

- [ ] **Task 5: Implement 50% TTL reminder** (AC: 1, 4, 6)
  - [ ] Calculate 50% of TTL (36h for 72h TTL)
  - [ ] Query tasks at or past 50% milestone
  - [ ] Generate neutral reminder content
  - [ ] Pass through Coercion Filter
  - [ ] Send to Cluster if filter accepts
  - [ ] Emit `executive.task.reminder_sent` event

- [ ] **Task 6: Implement 90% TTL reminder** (AC: 2, 4, 6)
  - [ ] Calculate 90% of TTL (64.8h for 72h TTL)
  - [ ] Query tasks at or past 90% milestone
  - [ ] Generate neutral reminder content
  - [ ] Include "final reminder" indicator (still neutral tone)
  - [ ] Pass through Coercion Filter
  - [ ] Send to Cluster if filter accepts
  - [ ] Emit `executive.task.reminder_sent` event

- [ ] **Task 7: Implement duplicate prevention** (AC: 9)
  - [ ] Track which milestones sent for each task
  - [ ] Store in reminder_tracking table or projection
  - [ ] Skip if milestone already sent
  - [ ] Handle race conditions in batch processing

- [ ] **Task 8: Write comprehensive unit tests** (AC: 10)
  - [ ] Test reminder sent at 50% TTL
  - [ ] Test reminder sent at 90% TTL
  - [ ] Test reminder content is neutral
  - [ ] Test Coercion Filter integration
  - [ ] Test no reminder if task already actioned
  - [ ] Test duplicate prevention
  - [ ] Test FilteredContent type enforcement

---

## Documentation Checklist

- [ ] Architecture docs updated (reminder workflow)
- [ ] Inline comments explaining neutral tone requirement
- [ ] Reminder template documentation
- [ ] N/A - README (internal component)

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
