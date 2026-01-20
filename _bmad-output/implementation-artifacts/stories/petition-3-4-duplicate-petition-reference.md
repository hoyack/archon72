# Story 3.4: Duplicate Petition Reference

## Story Details
- **Story ID:** petition-3-4-duplicate-petition-reference
- **Epic:** 3 - Acknowledgment Execution
- **Priority:** P1
- **Status:** DONE (implemented as part of Stories 3.1 and 3.2)
- **Completed:** 2026-01-19

## User Story
As a **system**,
I want DUPLICATE acknowledgments to reference the original petition,
So that petitioners can track the canonical petition.

## Acceptance Criteria

### AC-1: DUPLICATE Requires reference_petition_id ✅
**Given** an acknowledgment with reason_code = DUPLICATE
**When** the acknowledgment is validated
**Then** `reference_petition_id` must be provided

**Implementation:**
- `AcknowledgmentReasonCode.requires_reference()` returns `True` for DUPLICATE
- `validate_acknowledgment_requirements()` raises `ReferenceRequiredError` if missing
- Domain model `__post_init__` enforces validation

### AC-2: Referenced Petition Must Exist ✅
**Given** a DUPLICATE acknowledgment with reference_petition_id
**When** the service executes the acknowledgment
**Then** the referenced petition must exist in the database
**And** validation fails if reference petition doesn't exist

**Implementation:**
- `AcknowledgmentExecutionService.execute()` at lines 177-183 validates reference exists
- `InvalidReferencePetitionError` raised when reference petition not found

### AC-3: Validation Fails for Missing/Invalid Reference ✅
**Given** a DUPLICATE acknowledgment
**When** reference_petition_id is missing or invalid
**Then** the appropriate error is raised

**Implementation:**
- Missing: `ReferenceRequiredError` from domain validation
- Invalid (non-existent): `InvalidReferencePetitionError` from service layer

### AC-4: Reference Persisted in Acknowledgment Record ✅
**Given** a valid DUPLICATE acknowledgment
**When** the acknowledgment is persisted
**Then** the `reference_petition_id` is stored

**Implementation:**
- `Acknowledgment.reference_petition_id: UUID | None` field
- `to_dict()` includes reference_petition_id for serialization
- Database migration 022 includes `reference_petition_id` column

### AC-5: Reference Included in Witness Event ✅
**Given** a DUPLICATE acknowledgment with reference
**When** the PetitionAcknowledgedEvent is emitted
**Then** the reference_petition_id is included in the event payload

**Implementation:**
- `PetitionAcknowledgedEvent.reference_petition_id` field
- `to_dict()` includes reference_petition_id
- Event validates reference for DUPLICATE codes

## Functional Requirements Coverage

| FR | Description | Status |
|----|-------------|--------|
| FR-3.4 | System SHALL require reference_petition_id for DUPLICATE | ✅ |

## Implementation Files

### Already Implemented (Stories 3.1 & 3.2)

| File | Purpose |
|------|---------|
| `src/domain/models/acknowledgment_reason.py` | `requires_reference()`, `ReferenceRequiredError`, `validate_acknowledgment_requirements()` |
| `src/domain/models/acknowledgment.py` | Domain model with reference_petition_id field and validation |
| `src/domain/events/acknowledgment.py` | Event with reference_petition_id field and validation |
| `src/domain/errors/acknowledgment.py` | `InvalidReferencePetitionError` for non-existent references |
| `src/application/services/acknowledgment_execution_service.py` | Service validates reference exists (lines 177-183) |
| `migrations/022_create_acknowledgments_table.sql` | Database schema with reference_petition_id column |

### Test Coverage

| Test File | Tests |
|-----------|-------|
| `tests/unit/domain/models/test_acknowledgment_reason.py` | 8+ reference-specific tests |
| `tests/unit/domain/models/test_acknowledgment.py` | 6+ DUPLICATE reference tests |
| `tests/unit/application/services/test_acknowledgment_execution_service.py` | 3+ service-level reference tests |

## Key Implementation Details

### 1. Validation Logic (`acknowledgment_reason.py`)

```python
@classmethod
def requires_reference(cls, code: "AcknowledgmentReasonCode") -> bool:
    """Per FR-3.4, DUPLICATE requires a reference_petition_id."""
    return code == cls.DUPLICATE

class ReferenceRequiredError(ValueError):
    """Raised when reference_petition_id is required but not provided."""
    def __init__(self):
        super().__init__(
            "Reference petition ID is required for DUPLICATE acknowledgments. "
            "Per FR-3.4, DUPLICATE reason code must include the petition_id "
            "of the original or already-resolved petition."
        )

def validate_acknowledgment_requirements(...):
    if AcknowledgmentReasonCode.requires_reference(reason_code):
        if reference_petition_id is None:
            raise ReferenceRequiredError()
```

### 2. Service Layer Validation (`acknowledgment_execution_service.py`)

```python
# Step 5: Validate reference petition exists for DUPLICATE
if reference_petition_id is not None:
    ref_petition = await self._petition_repo.get_by_id(reference_petition_id)
    if ref_petition is None:
        raise InvalidReferencePetitionError(
            petition_id=petition_id,
            reference_petition_id=reference_petition_id,
        )
```

### 3. Error Class (`acknowledgment.py`)

```python
class InvalidReferencePetitionError(AcknowledgmentExecutionError):
    """Raised when DUPLICATE references a non-existent petition."""
    def __init__(self, petition_id: UUID, reference_petition_id: UUID) -> None:
        self.petition_id = petition_id
        self.reference_petition_id = reference_petition_id
        super().__init__(
            f"DUPLICATE acknowledgment for petition {petition_id} references "
            f"non-existent petition {reference_petition_id}. "
            f"Per FR-3.4, reference_petition_id must point to an existing petition."
        )
```

### 4. Domain Model Property (`acknowledgment.py`)

```python
@property
def is_duplicate_reference(self) -> bool:
    """Return True if this acknowledges a duplicate petition."""
    return self.reason_code == AcknowledgmentReasonCode.DUPLICATE
```

### 5. Witness Hash Includes Reference (`acknowledgment_execution_service.py`)

```python
def _build_witness_content(self, ...):
    parts = [...]
    if reference_petition_id:
        parts.append(f"reference_petition_id:{reference_petition_id}")
    return "|".join(parts)
```

## Test Summary

### Unit Tests: `test_acknowledgment_reason.py`
- `test_requires_reference_for_duplicate` ✅
- `test_other_codes_do_not_require_reference` (parametrized) ✅
- `test_duplicate_with_reference_passes` ✅
- `test_duplicate_without_reference_raises` ✅
- `test_reference_required_error_message` ✅
- `test_reference_required_error_inheritance` ✅

### Unit Tests: `test_acknowledgment.py`
- `test_create_duplicate_requires_reference` ✅
- `test_create_duplicate_with_reference_succeeds` ✅
- `test_is_duplicate_reference_true` ✅
- `test_is_duplicate_reference_false` ✅

### Unit Tests: `test_acknowledgment_execution_service.py`
- `test_execute_duplicate_with_reference` ✅
- `test_duplicate_without_reference` ✅
- `test_duplicate_with_invalid_reference` ✅

## Notes

This story was effectively implemented as part of Stories 3.1 (Acknowledgment Reason Code Enumeration) and 3.2 (Acknowledgment Execution Service). The FR-3.4 requirement for reference_petition_id validation was addressed proactively during implementation.

The implementation provides two layers of validation:
1. **Domain Layer**: `ReferenceRequiredError` - Ensures reference_petition_id is provided for DUPLICATE
2. **Service Layer**: `InvalidReferencePetitionError` - Ensures the referenced petition actually exists

**No additional code changes required** - the story acceptance criteria are fully satisfied by the existing implementation.

## References
- FR-3.4: System SHALL require reference_petition_id for DUPLICATE
- Story 3.1: Acknowledgment Reason Code Enumeration
- Story 3.2: Acknowledgment Execution Service
