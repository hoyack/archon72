# Story consent-gov-3.1: Coercion Filter Domain Model

Status: done

---

## Story

As a **governance system**,
I want **a Coercion Filter domain model**,
So that **content filtering has clear structure and outcomes**.

---

## Acceptance Criteria

1. **AC1:** Filter outcomes defined: `accept` (with transformation), `reject` (require rewrite), `block` (hard violation) (FR16-FR18)
2. **AC2:** `FilteredContent` type required for all participant-facing output
3. **AC3:** Unfiltered content cannot reach participants (type system enforced)
4. **AC4:** Filter version tracked for auditability
5. **AC5:** Content transformation rules defined for `accept` outcomes
6. **AC6:** Rejection reasons defined for `reject` outcomes
7. **AC7:** Violation types defined for `block` outcomes
8. **AC8:** Immutable value objects for filter decisions
9. **AC9:** Unit tests for each outcome type

---

## Tasks / Subtasks

- [x] **Task 1: Create FilterDecision enum** (AC: 1)
  - [x] Create `src/domain/governance/filter/__init__.py`
  - [x] Create `src/domain/governance/filter/filter_decision.py`
  - [x] Define `FilterDecision` enum: ACCEPTED, REJECTED, BLOCKED
  - [x] Include decision descriptions

- [x] **Task 2: Create FilteredContent value object** (AC: 2, 3)
  - [x] Create `src/domain/governance/filter/filtered_content.py`
  - [x] Define `FilteredContent` as immutable dataclass
  - [x] Include original content hash (for audit)
  - [x] Include transformed content
  - [x] Include filter version
  - [x] Private constructor to prevent unfiltered instantiation

- [x] **Task 3: Create FilterResult value object** (AC: 1, 4, 5, 6, 7, 8)
  - [x] Create `src/domain/governance/filter/filter_result.py`
  - [x] Define `FilterResult` immutable dataclass
  - [x] Include decision, content, version, timestamp
  - [x] Include transformation details for ACCEPTED
  - [x] Include rejection reason for REJECTED
  - [x] Include violation details for BLOCKED

- [x] **Task 4: Create TransformationRule model** (AC: 5)
  - [x] Create `src/domain/governance/filter/transformation.py`
  - [x] Define what transformations can be applied
  - [x] E.g., remove urgency words, soften language
  - [x] Rules are versioned and auditable

- [x] **Task 5: Create RejectionReason enum** (AC: 6)
  - [x] Define rejection categories
  - [x] E.g., URGENCY_PRESSURE, GUILT_INDUCTION, FALSE_SCARCITY
  - [x] Include human-readable descriptions
  - [x] Map to required rewrite guidance

- [x] **Task 6: Create ViolationType enum** (AC: 7)
  - [x] Define hard violation categories
  - [x] E.g., EXPLICIT_THREAT, DECEPTION, MANIPULATION
  - [x] These cannot be transformed, only blocked
  - [x] Include severity and escalation path

- [x] **Task 7: Implement type system enforcement** (AC: 3)
  - [x] All participant-facing APIs require `FilteredContent` type
  - [x] Raw string cannot be passed where FilteredContent expected
  - [x] Compile-time (type hint) + runtime validation
  - [x] Add architectural test verifying no bypass path

- [x] **Task 8: Implement filter versioning** (AC: 4)
  - [x] Define `FilterVersion` value object
  - [x] Version included in every FilterResult
  - [x] Version tracked in FilteredContent
  - [x] Enable audit of which filter version processed content

- [x] **Task 9: Write comprehensive unit tests** (AC: 9)
  - [x] Test FilteredContent creation and immutability
  - [x] Test each FilterDecision outcome
  - [x] Test transformation rules
  - [x] Test rejection reasons
  - [x] Test violation types
  - [x] Test version tracking
  - [x] Architectural test: type system prevents bypass

---

## Documentation Checklist

- [x] Architecture docs updated (filter domain model)
- [x] Inline comments explaining type system enforcement
- [x] N/A - API docs (domain layer)
- [x] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Type System Enforcement (NFR-CONST-05):**
```
The FilteredContent type is the ONLY way content can reach participants.

                    ┌─────────────────────────┐
                    │      Raw Content        │
                    │     (str, dict, etc.)   │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │    Coercion Filter      │
                    │      (mandatory)        │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │    FilteredContent      │
                    │   (type-safe output)    │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │     Participant         │
                    │   (Cluster, Human)      │
                    └─────────────────────────┘

There is NO path from Raw Content → Participant that bypasses the filter.
This is enforced by the type system: functions that send to participants
require FilteredContent, not str.
```

**Three Filter Outcomes (FR16-FR18):**
```
ACCEPTED (FR16):
  - Content can be sent
  - May include transformations (softening, removal of coercive words)
  - Original + transformed content preserved for audit

REJECTED (FR17):
  - Content cannot be sent as-is
  - Earl must rewrite and resubmit
  - Rejection reason provided
  - Not logged as violation (correctable)

BLOCKED (FR18):
  - Hard violation detected
  - Content cannot be sent under any circumstance
  - Logged as potential governance issue
  - May trigger Knight observation
```

### Domain Models

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import NewType
from hashlib import blake2b


class FilterDecision(Enum):
    """Outcome of content filtering."""
    ACCEPTED = "accepted"      # Content can be sent (possibly transformed)
    REJECTED = "rejected"      # Content requires rewrite
    BLOCKED = "blocked"        # Hard violation, cannot send


class RejectionReason(Enum):
    """Reasons content was rejected (correctable)."""
    URGENCY_PRESSURE = "urgency_pressure"
    GUILT_INDUCTION = "guilt_induction"
    FALSE_SCARCITY = "false_scarcity"
    ENGAGEMENT_OPTIMIZATION = "engagement_optimization"
    EXCESSIVE_EMPHASIS = "excessive_emphasis"
    IMPLICIT_THREAT = "implicit_threat"

    @property
    def guidance(self) -> str:
        """Rewrite guidance for this rejection reason."""
        guidance_map = {
            self.URGENCY_PRESSURE: "Remove time pressure language",
            self.GUILT_INDUCTION: "Remove guilt-inducing phrases",
            self.FALSE_SCARCITY: "Remove artificial scarcity claims",
            self.ENGAGEMENT_OPTIMIZATION: "Use neutral, informational tone",
            self.EXCESSIVE_EMPHASIS: "Remove excessive caps, punctuation",
            self.IMPLICIT_THREAT: "Remove implied negative consequences",
        }
        return guidance_map.get(self, "Revise content for neutral tone")


class ViolationType(Enum):
    """Hard violations that cannot be transformed."""
    EXPLICIT_THREAT = "explicit_threat"
    DECEPTION = "deception"
    MANIPULATION = "manipulation"
    COERCION = "coercion"
    HARASSMENT = "harassment"

    @property
    def severity(self) -> str:
        """Severity level for this violation."""
        return "critical"  # All hard violations are critical


@dataclass(frozen=True)
class FilterVersion:
    """Version of the filter rules used."""
    major: int
    minor: int
    patch: int
    rules_hash: str  # Hash of the pattern library

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class FilteredContent:
    """Type-safe container for filtered content.

    This type MUST be used for all participant-facing output.
    It cannot be created without going through the filter.
    """
    _content: str
    _original_hash: str
    _filter_version: FilterVersion
    _filtered_at: datetime

    # Private factory method - only Coercion Filter can create instances
    @classmethod
    def _create(
        cls,
        content: str,
        original_content: str,
        filter_version: FilterVersion,
        filtered_at: datetime,
    ) -> "FilteredContent":
        """Internal factory. Only CoercionFilterService should call this."""
        original_hash = blake2b(
            original_content.encode(), digest_size=32
        ).hexdigest()
        return cls(
            _content=content,
            _original_hash=original_hash,
            _filter_version=filter_version,
            _filtered_at=filtered_at,
        )

    @property
    def content(self) -> str:
        return self._content

    @property
    def original_hash(self) -> str:
        return self._original_hash

    @property
    def filter_version(self) -> FilterVersion:
        return self._filter_version


@dataclass(frozen=True)
class Transformation:
    """Record of a transformation applied to content."""
    pattern_matched: str
    original_text: str
    replacement_text: str
    rule_id: str


@dataclass(frozen=True)
class FilterResult:
    """Complete result of content filtering."""
    decision: FilterDecision
    content: FilteredContent | None  # None if BLOCKED
    version: FilterVersion
    timestamp: datetime

    # For ACCEPTED
    transformations: tuple[Transformation, ...] = ()

    # For REJECTED
    rejection_reason: RejectionReason | None = None
    rejection_guidance: str | None = None

    # For BLOCKED
    violation_type: ViolationType | None = None
    violation_details: str | None = None

    def is_sendable(self) -> bool:
        """Returns True if content can be sent to participant."""
        return self.decision == FilterDecision.ACCEPTED
```

### Type System Enforcement

```python
# Correct: Function requires FilteredContent
async def send_to_cluster(
    cluster_id: UUID,
    content: FilteredContent,  # Type hint enforces filter usage
) -> SendResult:
    """Send content to cluster. Requires filtered content."""
    # Content is guaranteed to have passed through filter
    ...


# WRONG: This would be caught by type checker
async def bad_send(cluster_id: UUID, content: str) -> SendResult:
    # Type error: str is not FilteredContent
    return await send_to_cluster(cluster_id, content)  # ERROR


# Runtime enforcement (defense in depth)
def validate_filtered_content(content: Any) -> FilteredContent:
    """Runtime validation that content is FilteredContent."""
    if not isinstance(content, FilteredContent):
        raise TypeError(
            f"Participant-facing content must be FilteredContent, got {type(content)}"
        )
    return content
```

### Architectural Test

```python
class TestFilterTypeEnforcement:
    """Architectural tests for type system enforcement."""

    def test_participant_apis_require_filtered_content(self):
        """All participant-facing APIs require FilteredContent type."""
        # Inspect all functions that send to participants
        participant_facing_modules = [
            "src.application.services.governance.task_activation_service",
            "src.application.services.governance.task_reminder_service",
            "src.application.services.governance.notification_service",
        ]

        for module_path in participant_facing_modules:
            module = importlib.import_module(module_path)
            for name, func in inspect.getmembers(module, inspect.isfunction):
                if "send" in name.lower() or "notify" in name.lower():
                    hints = get_type_hints(func)
                    # Verify content parameter is FilteredContent
                    assert any(
                        hint == FilteredContent
                        for hint in hints.values()
                    ), f"{module_path}.{name} must require FilteredContent"

    def test_raw_string_cannot_reach_participant(self):
        """Verify no path exists for raw string to reach participant."""
        # This test inspects the call graph to ensure FilteredContent
        # is required at all participant-facing boundaries
        pass
```

### Test Patterns

```python
class TestFilterDomainModels:
    """Unit tests for filter domain models."""

    def test_filter_decision_values(self):
        """All three outcomes are defined."""
        assert FilterDecision.ACCEPTED.value == "accepted"
        assert FilterDecision.REJECTED.value == "rejected"
        assert FilterDecision.BLOCKED.value == "blocked"

    def test_filtered_content_immutable(self):
        """FilteredContent is immutable."""
        content = FilteredContent._create(
            content="Hello",
            original_content="HELLO!",
            filter_version=FilterVersion(1, 0, 0, "abc123"),
            filtered_at=datetime.now(),
        )

        with pytest.raises(FrozenInstanceError):
            content._content = "Modified"

    def test_filtered_content_tracks_original_hash(self):
        """Original content hash preserved for audit."""
        original = "Original content with URGENCY!"
        content = FilteredContent._create(
            content="Original content with emphasis",
            original_content=original,
            filter_version=FilterVersion(1, 0, 0, "abc123"),
            filtered_at=datetime.now(),
        )

        expected_hash = blake2b(original.encode(), digest_size=32).hexdigest()
        assert content.original_hash == expected_hash

    def test_rejection_reason_has_guidance(self):
        """Each rejection reason provides rewrite guidance."""
        for reason in RejectionReason:
            assert reason.guidance is not None
            assert len(reason.guidance) > 0

    def test_filter_result_accepted_has_transformations(self):
        """Accepted results include transformation details."""
        result = FilterResult(
            decision=FilterDecision.ACCEPTED,
            content=FilteredContent._create(...),
            version=FilterVersion(1, 0, 0, "abc"),
            timestamp=datetime.now(),
            transformations=(
                Transformation(
                    pattern_matched="URGENT",
                    original_text="URGENT!",
                    replacement_text="",
                    rule_id="remove_urgency_caps",
                ),
            ),
        )

        assert result.is_sendable()
        assert len(result.transformations) == 1

    def test_filter_result_rejected_has_reason(self):
        """Rejected results include reason and guidance."""
        result = FilterResult(
            decision=FilterDecision.REJECTED,
            content=None,
            version=FilterVersion(1, 0, 0, "abc"),
            timestamp=datetime.now(),
            rejection_reason=RejectionReason.URGENCY_PRESSURE,
            rejection_guidance="Remove time pressure language",
        )

        assert not result.is_sendable()
        assert result.rejection_reason == RejectionReason.URGENCY_PRESSURE

    def test_filter_result_blocked_has_violation(self):
        """Blocked results include violation details."""
        result = FilterResult(
            decision=FilterDecision.BLOCKED,
            content=None,
            version=FilterVersion(1, 0, 0, "abc"),
            timestamp=datetime.now(),
            violation_type=ViolationType.EXPLICIT_THREAT,
            violation_details="Content contained explicit threat",
        )

        assert not result.is_sendable()
        assert result.violation_type == ViolationType.EXPLICIT_THREAT
```

### Dependencies

- **Depends on:** None (foundational domain model)
- **Enables:** consent-gov-3-2 (filter service), consent-gov-2-6 (reminders use FilteredContent)

### References

- FR16: Coercion Filter can accept content (with transformation)
- FR17: Coercion Filter can reject content (requiring rewrite)
- FR18: Coercion Filter can block content (hard violation, logged)
- NFR-CONST-05: No API or administrative path exists to bypass Coercion Filter
- AD-14: FilteredContent type for bypass prevention

---

## Dev Agent Record

### Implementation Plan

Implemented the complete Coercion Filter domain model following the story specifications:
1. Created all domain models as frozen dataclasses for immutability (AC8)
2. Implemented three filter outcomes: ACCEPTED, REJECTED, BLOCKED (AC1)
3. Created FilteredContent type with BLAKE2b hash for audit trail (AC2, AC4)
4. Implemented type system enforcement with runtime validation (AC3)
5. Created comprehensive test suite covering all acceptance criteria (AC9)

### Debug Log

No issues encountered. All implementations followed the red-green-refactor cycle:
- Wrote failing tests first
- Implemented minimal code to pass tests
- Refactored for clarity while keeping tests green

### Completion Notes

✅ All 9 acceptance criteria satisfied
✅ 89 unit tests passing (0.15s execution time)
✅ No regressions in existing governance tests (1165 passed)
✅ All domain models are immutable (frozen dataclasses)
✅ Type system enforcement verified via architectural tests
✅ Filter versioning implemented for auditability

---

## File List

### Created Files

- `src/domain/governance/filter/__init__.py` - Module exports
- `src/domain/governance/filter/filter_decision.py` - FilterDecision enum (ACCEPTED, REJECTED, BLOCKED)
- `src/domain/governance/filter/filter_version.py` - FilterVersion value object
- `src/domain/governance/filter/filtered_content.py` - FilteredContent type-safe container
- `src/domain/governance/filter/filter_result.py` - FilterResult complete outcome
- `src/domain/governance/filter/rejection_reason.py` - RejectionReason enum with guidance
- `src/domain/governance/filter/violation_type.py` - ViolationType enum with severity
- `src/domain/governance/filter/transformation.py` - Transformation and TransformationRule models
- `tests/unit/domain/governance/filter/__init__.py` - Test module
- `tests/unit/domain/governance/filter/test_filter_decision.py` - FilterDecision tests (8 tests)
- `tests/unit/domain/governance/filter/test_filtered_content.py` - FilteredContent tests (10 tests)
- `tests/unit/domain/governance/filter/test_filter_result.py` - FilterResult tests (15 tests)
- `tests/unit/domain/governance/filter/test_filter_version.py` - FilterVersion tests (11 tests)
- `tests/unit/domain/governance/filter/test_rejection_reason.py` - RejectionReason tests (11 tests)
- `tests/unit/domain/governance/filter/test_violation_type.py` - ViolationType tests (12 tests)
- `tests/unit/domain/governance/filter/test_transformation.py` - Transformation tests (13 tests)
- `tests/unit/domain/governance/filter/test_type_enforcement.py` - Type enforcement tests (9 tests)

### Modified Files

- `_bmad-output/implementation-artifacts/sprint-status.yaml` - Status updated to in-progress

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-17 | Implemented complete Coercion Filter domain model with 89 unit tests | Dev Agent |
