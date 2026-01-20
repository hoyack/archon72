# Story 3.3: Rationale Requirement Enforcement

## Story Details
- **Story ID:** petition-3-3-rationale-requirement-enforcement
- **Epic:** 3 - Acknowledgment Execution
- **Priority:** P1
- **Status:** DONE (implemented as part of Stories 3.1 and 3.2)
- **Completed:** 2026-01-19

## User Story
As a **system**,
I want to enforce mandatory rationale for certain reason codes,
So that REFUSED and NO_ACTION_WARRANTED decisions are properly justified.

## Acceptance Criteria

### AC-1: REFUSED Requires Rationale ✅
**Given** a REFUSED acknowledgment request
**When** the acknowledgment is created
**Then** the system SHALL require non-empty `rationale` text

**Implementation:**
- `AcknowledgmentReasonCode.requires_rationale()` returns `True` for REFUSED
- `validate_acknowledgment_requirements()` raises `RationaleRequiredError` if missing
- Domain model `__post_init__` enforces validation
- Service layer validates before execution

### AC-2: NO_ACTION_WARRANTED Requires Rationale ✅
**Given** a NO_ACTION_WARRANTED acknowledgment request
**When** the acknowledgment is created
**Then** the system SHALL require non-empty `rationale` text

**Implementation:**
- `AcknowledgmentReasonCode.requires_rationale()` returns `True` for NO_ACTION_WARRANTED
- Same validation flow as REFUSED

### AC-3: Other Codes Do Not Require Rationale ✅
**Given** an acknowledgment with reason code NOTED, ADDRESSED, OUT_OF_SCOPE, WITHDRAWN, EXPIRED, or DUPLICATE
**When** the acknowledgment is created
**Then** `rationale` is optional (may be empty)

**Implementation:**
- `requires_rationale()` returns `False` for all other codes
- Validation allows None or empty rationale for these codes

### AC-4: Rationale Preserved in Acknowledgment Record ✅
**Given** an acknowledgment with rationale
**When** the acknowledgment is persisted
**Then** the rationale is stored in the acknowledgment record

**Implementation:**
- `Acknowledgment` dataclass has `rationale: str | None` field
- `to_dict()` includes rationale for serialization
- Database migration 022 includes `rationale` column

### AC-5: Rationale Included in Witness Event ✅
**Given** an acknowledgment with rationale
**When** the PetitionAcknowledgedEvent is emitted
**Then** the rationale is included in the event payload

**Implementation:**
- `PetitionAcknowledgedEvent.rationale` field at line 69
- `to_dict()` includes rationale at line 156
- Event validates rationale for required codes at lines 109-116
- Service includes rationale in witness hash at lines 302-303

## Functional Requirements Coverage

| FR | Description | Status |
|----|-------------|--------|
| FR-3.3 | System SHALL require rationale text for REFUSED and NO_ACTION_WARRANTED | ✅ |
| NFR-6.3 | Rationale preservation | ✅ |

## Implementation Files

### Already Implemented (Stories 3.1 & 3.2)

| File | Purpose |
|------|---------|
| `src/domain/models/acknowledgment_reason.py` | `requires_rationale()`, `RationaleRequiredError`, `validate_acknowledgment_requirements()` |
| `src/domain/models/acknowledgment.py` | Domain model with rationale field and validation |
| `src/domain/events/acknowledgment.py` | Event with rationale field and validation |
| `src/application/services/acknowledgment_execution_service.py` | Service validates and preserves rationale |
| `migrations/022_create_acknowledgments_table.sql` | Database schema with rationale column |

### Test Coverage

| Test File | Tests |
|-----------|-------|
| `tests/unit/domain/models/test_acknowledgment_reason.py` | 15+ rationale-specific tests |
| `tests/unit/domain/models/test_acknowledgment.py` | 8+ rationale enforcement tests |
| `tests/unit/application/services/test_acknowledgment_execution_service.py` | Service-level rationale tests |

## Key Implementation Details

### 1. Validation Logic (`acknowledgment_reason.py`)

```python
@classmethod
def requires_rationale(cls, code: "AcknowledgmentReasonCode") -> bool:
    """Per FR-3.3, REFUSED and NO_ACTION_WARRANTED require rationale."""
    return code in {cls.REFUSED, cls.NO_ACTION_WARRANTED}

class RationaleRequiredError(ValueError):
    """Raised when rationale is required but not provided."""
    def __init__(self, reason_code: AcknowledgmentReasonCode):
        super().__init__(
            f"Rationale is required for reason code '{reason_code.value}'. "
            f"Per FR-3.3, acknowledgments with REFUSED or NO_ACTION_WARRANTED "
            f"must include a non-empty rationale explaining the decision."
        )

def validate_acknowledgment_requirements(
    reason_code: AcknowledgmentReasonCode,
    rationale: Optional[str] = None,
    reference_petition_id: Optional[UUID] = None,
) -> None:
    """Validate rationale and reference requirements."""
    if AcknowledgmentReasonCode.requires_rationale(reason_code):
        if not rationale or not rationale.strip():
            raise RationaleRequiredError(reason_code)
```

### 2. Domain Model Enforcement (`acknowledgment.py`)

```python
def __post_init__(self) -> None:
    """Validate all invariants after initialization."""
    # Validate rationale and reference requirements (from Story 3.1)
    validate_acknowledgment_requirements(
        self.reason_code,
        self.rationale,
        self.reference_petition_id,
    )
```

### 3. Event Validation (`acknowledgment.py`)

```python
def _validate_rationale_for_reason(self) -> None:
    """Validate rationale present for codes that require it (FR-3.3)."""
    if AcknowledgmentReasonCode.requires_rationale(self.reason_code):
        if not self.rationale or not self.rationale.strip():
            raise ValueError(
                f"rationale is required for reason code {self.reason_code.value} "
                f"per FR-3.3"
            )
```

### 4. Witness Hash Includes Rationale (`acknowledgment_execution_service.py`)

```python
def _build_witness_content(self, ...):
    parts = [...]
    if rationale:
        parts.append(f"rationale:{rationale}")
    return "|".join(parts)
```

## Test Summary

### Unit Tests: `test_acknowledgment_reason.py`
- `test_requires_rationale_for_refused` ✅
- `test_requires_rationale_for_no_action_warranted` ✅
- `test_other_codes_do_not_require_rationale` (parametrized) ✅
- `test_refused_with_rationale_passes` ✅
- `test_refused_without_rationale_raises` ✅
- `test_refused_with_empty_rationale_raises` ✅
- `test_refused_with_whitespace_only_rationale_raises` ✅
- `test_no_action_warranted_with_rationale_passes` ✅
- `test_no_action_warranted_without_rationale_raises` ✅
- `test_codes_without_requirements_accept_optional_rationale` (parametrized) ✅
- `test_rationale_required_error_message` ✅
- `test_rationale_required_error_inheritance` ✅

### Unit Tests: `test_acknowledgment.py`
- `test_create_valid_acknowledgment_with_rationale` ✅
- `test_create_refused_requires_rationale` ✅
- `test_create_refused_with_rationale_succeeds` ✅
- `test_create_no_action_warranted_requires_rationale` ✅
- `test_create_no_action_warranted_with_rationale_succeeds` ✅
- `test_has_rationale_true` ✅
- `test_has_rationale_false` ✅
- `test_to_dict_with_rationale_and_reference` ✅

## Notes

This story was effectively implemented as part of Stories 3.1 (Acknowledgment Reason Code Enumeration) and 3.2 (Acknowledgment Execution Service). The FR-3.3 requirement for rationale enforcement was addressed proactively during the reason code implementation, ensuring the validation logic was in place from the start.

**No additional code changes required** - the story acceptance criteria are fully satisfied by the existing implementation.

## References
- FR-3.3: System SHALL require rationale text for REFUSED and NO_ACTION_WARRANTED
- NFR-6.3: Rationale preservation
- Story 3.1: Acknowledgment Reason Code Enumeration
- Story 3.2: Acknowledgment Execution Service
