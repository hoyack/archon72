# Story consent-gov-3.2: Coercion Filter Service

Status: ready-for-dev

---

## Story

As a **governance system**,
I want **a filter service that processes content**,
So that **coercive language is detected and handled before reaching participants**.

---

## Acceptance Criteria

1. **AC1:** Filter processes content in ≤200ms (NFR-PERF-03)
2. **AC2:** Determinism is primary; speed is secondary
3. **AC3:** All participant-facing messages routed through filter (FR21)
4. **AC4:** No API or administrative bypass path exists (NFR-CONST-05)
5. **AC5:** Filter applies transformation rules for correctable issues
6. **AC6:** Filter rejects content requiring Earl rewrite
7. **AC7:** Filter blocks hard violations
8. **AC8:** Filter returns `FilteredContent` type on success
9. **AC9:** Unit tests for filter processing

---

## Tasks / Subtasks

- [ ] **Task 1: Create CoercionFilterPort interface** (AC: 3, 4)
  - [ ] Create `src/application/ports/governance/coercion_filter_port.py`
  - [ ] Define `filter_content()` method
  - [ ] Define `preview_filter()` method (FR19 - Earl preview)
  - [ ] Include message type parameter

- [ ] **Task 2: Implement CoercionFilterService** (AC: 1, 2, 5, 6, 7, 8)
  - [ ] Create `src/application/services/governance/coercion_filter_service.py`
  - [ ] Implement filtering pipeline
  - [ ] Apply transformation rules
  - [ ] Check for rejection patterns
  - [ ] Check for blocking violations
  - [ ] Return FilterResult with appropriate outcome

- [ ] **Task 3: Implement performance constraint** (AC: 1, 2)
  - [ ] Process content in ≤200ms
  - [ ] If filter cannot complete deterministically in 200ms, REJECT
  - [ ] Do NOT timeout silently - rejection is explicit
  - [ ] Log processing time for monitoring

- [ ] **Task 4: Implement deterministic processing** (AC: 2)
  - [ ] Same input always produces same output
  - [ ] No random elements in filtering
  - [ ] No external dependencies that could vary
  - [ ] Determinism > Speed (if uncertain, reject)

- [ ] **Task 5: Implement mandatory routing** (AC: 3, 4)
  - [ ] All participant-facing APIs require FilteredContent
  - [ ] No bypass path in API design
  - [ ] No administrative override endpoint
  - [ ] Architectural test: verify no bypass path exists

- [ ] **Task 6: Implement transformation pipeline** (AC: 5)
  - [ ] Load transformation rules from pattern library
  - [ ] Apply rules in priority order
  - [ ] Record all transformations made
  - [ ] Return transformed content with audit trail

- [ ] **Task 7: Implement rejection logic** (AC: 6)
  - [ ] Detect patterns requiring rewrite
  - [ ] Provide rejection reason and guidance
  - [ ] Do NOT log as violation (correctable)
  - [ ] Earl can preview and fix before submit

- [ ] **Task 8: Implement blocking logic** (AC: 7)
  - [ ] Detect hard violations
  - [ ] Block content completely
  - [ ] Log violation details
  - [ ] May trigger Knight observation

- [ ] **Task 9: Write comprehensive unit tests** (AC: 9)
  - [ ] Test filter completes in ≤200ms
  - [ ] Test deterministic output
  - [ ] Test transformation application
  - [ ] Test rejection with guidance
  - [ ] Test blocking with violation details
  - [ ] Test FilteredContent type returned
  - [ ] Architectural test: no bypass path

---

## Documentation Checklist

- [ ] Architecture docs updated (filter service)
- [ ] Inline comments explaining determinism requirement
- [ ] Performance monitoring documentation
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Determinism > Speed (NFR-PERF-03):**
```
The filter MUST produce deterministic results.

If the filter cannot determine an outcome within 200ms:
  - Do NOT timeout silently
  - REJECT the content explicitly
  - Reason: "filter_timeout" with guidance to simplify content

Rationale: Silent timeout could allow coercive content through.
Explicit rejection maintains integrity.
```

**No Bypass Path (NFR-CONST-05):**
```
There is NO way to send content to participants without filtering:
  - No admin endpoint to bypass
  - No "urgent" flag to skip
  - No debug mode to disable
  - No environment variable to turn off

The type system enforces this: participant-facing APIs require
FilteredContent, which can only be created by the filter service.
```

### Filter Pipeline

```
Input Content
      │
      ▼
┌─────────────────┐
│ 1. Block Check  │ ──── Hard violation? ──→ BLOCKED
│   (critical)    │
└────────┬────────┘
         │ No
         ▼
┌─────────────────┐
│ 2. Reject Check │ ──── Requires rewrite? ──→ REJECTED
│  (correctable)  │
└────────┬────────┘
         │ No
         ▼
┌─────────────────┐
│ 3. Transform    │ ──── Apply transformations
│   (softening)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. Validate     │ ──── Re-check post-transform
│   (final)       │
└────────┬────────┘
         │ Pass
         ▼
     ACCEPTED
   (FilteredContent)
```

### Service Implementation Sketch

```python
class CoercionFilterService:
    """Coercion Filter service - mandatory path for all participant content."""

    TIMEOUT_MS = 200

    def __init__(
        self,
        pattern_library: PatternLibraryPort,
        time_authority: TimeAuthority,
    ):
        self._patterns = pattern_library
        self._time = time_authority

    async def filter_content(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        """Filter content for coercive language.

        Returns FilterResult with:
        - ACCEPTED: Content can be sent (with FilteredContent)
        - REJECTED: Content needs Earl rewrite
        - BLOCKED: Hard violation, cannot send
        """
        start_time = self._time.now()
        version = await self._patterns.get_current_version()

        try:
            # 1. Check for hard violations (block)
            violation = await self._check_violations(content)
            if violation:
                return FilterResult(
                    decision=FilterDecision.BLOCKED,
                    content=None,
                    version=version,
                    timestamp=start_time,
                    violation_type=violation.type,
                    violation_details=violation.details,
                )

            # 2. Check for correctable issues (reject)
            rejection = await self._check_rejections(content)
            if rejection:
                return FilterResult(
                    decision=FilterDecision.REJECTED,
                    content=None,
                    version=version,
                    timestamp=start_time,
                    rejection_reason=rejection.reason,
                    rejection_guidance=rejection.guidance,
                )

            # 3. Apply transformations
            transformed, transformations = await self._apply_transformations(content)

            # 4. Check timeout
            elapsed_ms = (self._time.now() - start_time).total_seconds() * 1000
            if elapsed_ms > self.TIMEOUT_MS:
                # Determinism > Speed: reject rather than risk non-deterministic result
                return FilterResult(
                    decision=FilterDecision.REJECTED,
                    content=None,
                    version=version,
                    timestamp=start_time,
                    rejection_reason=RejectionReason.TIMEOUT,
                    rejection_guidance="Content too complex. Please simplify.",
                )

            # 5. Create FilteredContent (only this service can do this)
            filtered_content = FilteredContent._create(
                content=transformed,
                original_content=content,
                filter_version=version,
                filtered_at=self._time.now(),
            )

            return FilterResult(
                decision=FilterDecision.ACCEPTED,
                content=filtered_content,
                version=version,
                timestamp=start_time,
                transformations=tuple(transformations),
            )

        except Exception as e:
            # Any error results in rejection (not silent failure)
            return FilterResult(
                decision=FilterDecision.REJECTED,
                content=None,
                version=version,
                timestamp=start_time,
                rejection_reason=RejectionReason.PROCESSING_ERROR,
                rejection_guidance=f"Filter error: {str(e)}. Please retry.",
            )

    async def preview_filter(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        """Preview filter result without logging (FR19).

        Allows Earl to see what would happen before submit.
        """
        # Same logic, but doesn't emit events or log to ledger
        return await self.filter_content(content, message_type)

    async def _check_violations(self, content: str) -> Violation | None:
        """Check for hard violations that cannot be transformed."""
        blocking_patterns = await self._patterns.get_blocking_patterns()
        for pattern in blocking_patterns:
            if pattern.matches(content):
                return Violation(
                    type=pattern.violation_type,
                    details=f"Pattern matched: {pattern.description}",
                )
        return None

    async def _check_rejections(self, content: str) -> Rejection | None:
        """Check for correctable issues requiring rewrite."""
        rejection_patterns = await self._patterns.get_rejection_patterns()
        for pattern in rejection_patterns:
            if pattern.matches(content):
                return Rejection(
                    reason=pattern.rejection_reason,
                    guidance=pattern.guidance,
                )
        return None

    async def _apply_transformations(
        self,
        content: str,
    ) -> tuple[str, list[Transformation]]:
        """Apply transformation rules to soften content."""
        transformations = []
        result = content

        transform_rules = await self._patterns.get_transformation_rules()
        for rule in transform_rules:
            if rule.matches(result):
                original_text = rule.extract_match(result)
                result = rule.apply(result)
                transformations.append(Transformation(
                    pattern_matched=rule.pattern,
                    original_text=original_text,
                    replacement_text=rule.replacement,
                    rule_id=rule.id,
                ))

        return result, transformations
```

### Port Interface

```python
class CoercionFilterPort(Protocol):
    """Port for coercion filter operations."""

    async def filter_content(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        """Filter content for coercive language.

        This is the ONLY path to create FilteredContent.
        """
        ...

    async def preview_filter(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        """Preview filter result without logging."""
        ...


class MessageType(Enum):
    """Types of messages that can be filtered."""
    TASK_ACTIVATION = "task_activation"
    REMINDER = "reminder"
    NOTIFICATION = "notification"
    SYSTEM_MESSAGE = "system_message"
```

### Bypass Prevention Architecture

```python
# How bypass is prevented:

# 1. Type system - participant APIs require FilteredContent
async def send_to_participant(
    participant_id: UUID,
    content: FilteredContent,  # Cannot pass str
) -> None:
    ...

# 2. FilteredContent has private constructor
class FilteredContent:
    @classmethod
    def _create(cls, ...):  # Underscore = internal only
        ...

# 3. Only CoercionFilterService calls _create
# All other code paths are blocked

# 4. No bypass endpoints
# There is no /api/send-unfiltered or similar

# 5. No admin override
# Even system administrator cannot bypass
```

### Test Patterns

```python
class TestCoercionFilterService:
    """Unit tests for coercion filter service."""

    async def test_filter_completes_within_200ms(
        self,
        filter_service: CoercionFilterService,
        sample_content: str,
    ):
        """Filter processes content in ≤200ms."""
        start = time.time()
        result = await filter_service.filter_content(
            content=sample_content,
            message_type=MessageType.TASK_ACTIVATION,
        )
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms <= 200

    async def test_deterministic_output(
        self,
        filter_service: CoercionFilterService,
    ):
        """Same input always produces same output."""
        content = "Please complete this task."

        result1 = await filter_service.filter_content(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )
        result2 = await filter_service.filter_content(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result1.decision == result2.decision
        if result1.content:
            assert result1.content.content == result2.content.content

    async def test_timeout_rejects_rather_than_passes(
        self,
        slow_filter_service: CoercionFilterService,
        complex_content: str,
    ):
        """If filter times out, it rejects (not accepts)."""
        result = await slow_filter_service.filter_content(
            content=complex_content,
            message_type=MessageType.TASK_ACTIVATION,
        )

        # REJECTED, not ACCEPTED or silent failure
        assert result.decision == FilterDecision.REJECTED
        assert "timeout" in result.rejection_guidance.lower()

    async def test_transformation_applied(
        self,
        filter_service: CoercionFilterService,
    ):
        """Transformations soften coercive language."""
        content = "URGENT! Complete this NOW!"

        result = await filter_service.filter_content(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.ACCEPTED
        assert len(result.transformations) > 0
        assert "URGENT" not in result.content.content

    async def test_rejection_provides_guidance(
        self,
        filter_service: CoercionFilterService,
    ):
        """Rejected content includes rewrite guidance."""
        content = "You MUST do this or you will be penalized!"

        result = await filter_service.filter_content(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.REJECTED
        assert result.rejection_reason is not None
        assert result.rejection_guidance is not None

    async def test_blocking_hard_violations(
        self,
        filter_service: CoercionFilterService,
    ):
        """Hard violations are blocked."""
        content = "Do this or I will hurt you."

        result = await filter_service.filter_content(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.BLOCKED
        assert result.violation_type == ViolationType.EXPLICIT_THREAT

    async def test_returns_filtered_content_type(
        self,
        filter_service: CoercionFilterService,
    ):
        """Accepted results return FilteredContent type."""
        content = "Please review when convenient."

        result = await filter_service.filter_content(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.ACCEPTED
        assert isinstance(result.content, FilteredContent)

    def test_no_bypass_path_exists(self):
        """Architectural test: no way to bypass filter."""
        # Verify all participant-facing functions require FilteredContent
        # See story 3-1 for detailed architectural test
        pass
```

### Dependencies

- **Depends on:** consent-gov-3-1 (domain model), consent-gov-3-4 (pattern library)
- **Enables:** consent-gov-2-2 (activation), consent-gov-2-6 (reminders)

### References

- FR15: System can filter outbound content for coercive language
- FR21: System can route all participant-facing messages through Coercion Filter
- NFR-CONST-05: No API or administrative path exists to bypass Coercion Filter
- NFR-PERF-03: Filter processes in ≤200ms
