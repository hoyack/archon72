# Story 5.4: Constitution Supremacy - No Witness Suppression (FR26, PM-4)

Status: done

## Story

As an **external observer**,
I want overrides unable to suppress witnessing,
So that no Keeper can bypass accountability.

## Acceptance Criteria

### AC1: Witness Suppression Rejection
**Given** an override command
**When** it attempts to suppress witnessing
**Then** the command is rejected
**And** error includes "FR26: Constitution supremacy - witnessing cannot be suppressed"

### AC2: Override Events Always Witnessed
**Given** any override
**When** it executes
**Then** the override itself is witnessed
**And** witness signature is required
**And** unwitnessed override attempts are blocked

### AC3: Mandatory Integration Test (PM-4)
**Given** the mandatory integration test (PM-4)
**When** `test_suppress_witness_override.py` runs
**Then** it confirms witness suppression is rejected

## Tasks / Subtasks

- [x] Task 1: Create Witness Suppression Error (AC: #1)
  - [x] 1.1 Add `WitnessSuppressionAttemptError` to `src/domain/errors/override.py`
  - [x] 1.2 Error message: "FR26: Constitution supremacy - witnessing cannot be suppressed"
  - [x] 1.3 Export from `src/domain/errors/__init__.py`

- [x] Task 2: Create Witness Suppression Scope Detection (AC: #1)
  - [x] 2.1 Add `FORBIDDEN_OVERRIDE_SCOPES` constant in `src/domain/models/override_reason.py`
  - [x] 2.2 Include scope patterns: `witness.*`, `witnessing`, `attestation.*`, `witness_service`, `witness_pool`
  - [x] 2.3 Create `is_witness_suppression_scope(scope: str) -> bool` function
  - [x] 2.4 Export from `src/domain/models/__init__.py`

- [x] Task 3: Create Constitution Supremacy Validator Port (AC: #1)
  - [x] 3.1 Create `src/application/ports/constitution_validator.py`
  - [x] 3.2 Define `ConstitutionValidatorProtocol` with:
    - `async def validate_override_scope(scope: str) -> None` (raises WitnessSuppressionAttemptError)
  - [x] 3.3 Export from `src/application/ports/__init__.py`

- [x] Task 4: Create Constitution Supremacy Validator Service (AC: #1)
  - [x] 4.1 Create `src/application/services/constitution_supremacy_service.py`
  - [x] 4.2 Implement `ConstitutionSupremacyValidator` class
  - [x] 4.3 Inject `is_witness_suppression_scope` function
  - [x] 4.4 `validate_override_scope()`:
    - Call `is_witness_suppression_scope(scope)`
    - If True, raise `WitnessSuppressionAttemptError`
    - Log rejection with scope and reason
  - [x] 4.5 Export from `src/application/services/__init__.py`

- [x] Task 5: Integrate Validation into OverrideService (AC: #1, #2)
  - [x] 5.1 Add `constitution_validator: ConstitutionValidatorProtocol` to OverrideService `__init__`
  - [x] 5.2 Call `validate_override_scope(override_payload.scope)` BEFORE event write
  - [x] 5.3 Ensure validation failure prevents ANY execution
  - [x] 5.4 Log rejection with full attribution (keeper_id, scope)

- [x] Task 6: Create Constitution Supremacy Stub (AC: #1)
  - [x] 6.1 Create `src/infrastructure/stubs/constitution_validator_stub.py`
  - [x] 6.2 Implement `ConstitutionValidatorStub` with configurable behavior
  - [x] 6.3 Default: uses real validation logic
  - [x] 6.4 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 7: Write Unit Tests (AC: #1, #2)
  - [x] 7.1 Create `tests/unit/domain/test_witness_suppression_error.py`
    - Test error message contains "FR26"
    - Test error inherits from ConstitutionalViolationError
  - [x] 7.2 Create `tests/unit/domain/test_forbidden_override_scopes.py`
    - Test `witness` scope is forbidden
    - Test `witnessing` scope is forbidden
    - Test `witness_service` scope is forbidden
    - Test `witness_pool` scope is forbidden
    - Test `attestation.disable` scope is forbidden
    - Test normal scopes (e.g., `voting.extension`) are allowed
  - [x] 7.3 Create `tests/unit/application/test_constitution_supremacy_service.py`
    - Test valid scopes pass without error
    - Test witness scopes raise WitnessSuppressionAttemptError
    - Test logging on rejection
  - [x] 7.4 Update `tests/unit/application/test_override_service.py`
    - Test validation is called before event write
    - Test validation failure prevents execution
    - Test validation failure returns correct error

- [x] Task 8: Write Integration Tests (AC: #1, #2, #3)
  - [x] 8.1 Create `tests/integration/test_suppress_witness_override.py` (PM-4 mandatory test)
    - Test: `test_suppress_witness_override_rejected`
    - Test: `test_witness_scope_override_rejected_with_fr26_message`
    - Test: `test_witnessing_scope_override_rejected`
    - Test: `test_attestation_scope_override_rejected`
  - [x] 8.2 Create `tests/integration/test_constitution_supremacy_integration.py`
    - Test: End-to-end override with valid scope succeeds
    - Test: End-to-end override with witness scope fails
    - Test: Override is witnessed when it succeeds
    - Test: No event created when validation fails

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR26**: Overrides that attempt to suppress witnessing SHALL be invalid by definition
- **CT-12**: Witnessing creates accountability - no unwitnessed actions
- **PM-4**: Cross-epic FR ownership - Epic 1 enforces (atomic witness), Epic 5 invokes (validation)
- **RT-1**: No witnesses available = write blocked, not degraded

### Cross-Epic Requirement (PM-4)

This story implements the **Epic 5 side** of FR26. The **Epic 1 side** (already implemented) ensures:
- All events require witness attestation (AtomicEventWriter)
- No unwitnessed events can exist (FR5)
- Witness unavailability blocks writes entirely (RT-1)

Story 5.4 adds the **validation layer** that:
- Detects override scopes that would suppress witnessing
- Rejects such overrides BEFORE they reach the event writer
- Creates constitutional violation error with FR26 message

### Architecture Pattern: Layered Protection

```
Override Request
     │
     ▼
┌─────────────────────────────────────────┐
│ ConstitutionSupremacyValidator          │ ← Story 5.4 (NEW)
│ - Check scope against FORBIDDEN_SCOPES  │
│ - Raise WitnessSuppressionAttemptError  │
└─────────────────────────────────────────┘
     │ (pass if valid scope)
     ▼
┌─────────────────────────────────────────┐
│ OverrideService                         │ ← Story 5.1
│ - Halt check first                      │
│ - Log override event BEFORE execution   │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ EventWriterService                      │ ← Story 1.6
│ - Halt check                            │
│ - Writer lock verification              │
│ - Delegates to AtomicEventWriter        │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ AtomicEventWriter                       │ ← Story 1.4
│ - Agent signing                         │
│ - Witness attestation (REQUIRED)        │
│ - Atomic persistence                    │
└─────────────────────────────────────────┘
```

### Forbidden Override Scopes (FR26)

These scope patterns MUST be rejected:

| Pattern | Reason |
|---------|--------|
| `witness` | Direct witness system override |
| `witness.*` | Any witness subsystem override |
| `witnessing` | Core witnessing function override |
| `attestation` | Event attestation override |
| `attestation.*` | Any attestation subsystem override |
| `witness_service` | Witness service override |
| `witness_pool` | Witness pool override |

### Key Implementation Pattern

```python
# src/domain/models/override_reason.py
FORBIDDEN_OVERRIDE_SCOPES: frozenset[str] = frozenset([
    "witness",
    "witnessing",
    "attestation",
    "witness_service",
    "witness_pool",
])

FORBIDDEN_OVERRIDE_SCOPE_PATTERNS: tuple[str, ...] = (
    "witness.",
    "attestation.",
)

def is_witness_suppression_scope(scope: str) -> bool:
    """Check if scope attempts to suppress witnessing (FR26).

    Args:
        scope: Override scope to validate.

    Returns:
        True if scope attempts witness suppression, False otherwise.
    """
    scope_lower = scope.lower()

    # Check exact matches
    if scope_lower in FORBIDDEN_OVERRIDE_SCOPES:
        return True

    # Check prefix patterns
    for pattern in FORBIDDEN_OVERRIDE_SCOPE_PATTERNS:
        if scope_lower.startswith(pattern):
            return True

    return False
```

```python
# src/application/services/constitution_supremacy_service.py
class ConstitutionSupremacyValidator:
    """Validates override commands against constitutional constraints (FR26)."""

    async def validate_override_scope(self, scope: str) -> None:
        """Validate that override scope does not suppress witnessing.

        Args:
            scope: Override scope to validate.

        Raises:
            WitnessSuppressionAttemptError: If scope attempts to suppress witnessing.
        """
        if is_witness_suppression_scope(scope):
            log.warning(
                "witness_suppression_attempt_rejected",
                scope=scope,
                fr_ref="FR26",
            )
            raise WitnessSuppressionAttemptError(
                scope=scope,
                message="FR26: Constitution supremacy - witnessing cannot be suppressed"
            )
```

```python
# In OverrideService.initiate_override() - add AFTER halt check, BEFORE event write:
# Step 1.5: Constitution Supremacy Validation (FR26, NEW)
await self._constitution_validator.validate_override_scope(override_payload.scope)
```

### Testing Patterns

**PM-4 Mandatory Integration Test:**
```python
# tests/integration/test_suppress_witness_override.py
import pytest
from src.domain.errors.override import WitnessSuppressionAttemptError

class TestSuppressWitnessOverride:
    """PM-4: Mandatory integration tests for FR26 witness suppression."""

    @pytest.mark.asyncio
    async def test_suppress_witness_override_rejected(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
    ):
        """FR26: Override attempting to suppress witnessing is rejected."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="witness",  # FORBIDDEN - attempts to suppress witnessing
            duration=3600,
            reason=OverrideReason.EMERGENCY_INTERVENTION,
            action_type=OverrideActionType.SUSPEND,
        )

        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await override_service.initiate_override(payload)

        assert "FR26" in str(exc_info.value)
        assert "Constitution supremacy" in str(exc_info.value)
        assert "witnessing cannot be suppressed" in str(exc_info.value)
```

### Files to Create

```
src/domain/errors/override.py                                  # Add WitnessSuppressionAttemptError
src/domain/models/override_reason.py                           # Add FORBIDDEN_OVERRIDE_SCOPES
src/application/ports/constitution_validator.py                # New - Protocol
src/application/services/constitution_supremacy_service.py     # New - Validator service
src/infrastructure/stubs/constitution_validator_stub.py        # New - Stub
tests/unit/domain/test_witness_suppression_error.py            # New
tests/unit/domain/test_forbidden_override_scopes.py            # New
tests/unit/application/test_constitution_supremacy_service.py  # New
tests/integration/test_suppress_witness_override.py            # New - PM-4 MANDATORY
tests/integration/test_constitution_supremacy_integration.py   # New
```

### Files to Modify

```
src/domain/errors/__init__.py                                  # Export new error
src/domain/models/__init__.py                                  # Export validation function
src/application/ports/__init__.py                              # Export protocol
src/application/services/__init__.py                           # Export service
src/application/services/override_service.py                   # Add validation step
src/infrastructure/stubs/__init__.py                           # Export stub
tests/unit/application/test_override_service.py                # Add validation tests
```

### Import Rules (Hexagonal Architecture)

- `domain/errors/` imports from base ConstitutionalViolationError only
- `domain/models/` NO external imports for validation function
- `application/ports/` imports from `typing` only
- `application/services/` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `api/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the ConstitutionValidatorProtocol
- Integration tests use real validator with real stubs
- PM-4 test MUST be named `test_suppress_witness_override.py`

### Previous Story Patterns (from 5.3)

**Error Handling Pattern:**
```python
class WitnessSuppressionAttemptError(ConstitutionalViolationError):
    """Raised when override attempts to suppress witnessing (FR26).

    Constitutional Constraint (FR26):
    Overrides that attempt to suppress witnessing are invalid by definition.
    No Keeper can bypass accountability through override.
    """

    def __init__(self, scope: str, message: str | None = None) -> None:
        msg = message or f"FR26: Override scope '{scope}' attempts to suppress witnessing"
        super().__init__(msg)
        self.scope = scope
```

**Service Injection Pattern:**
```python
class OverrideService:
    def __init__(
        self,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
        override_executor: OverrideExecutorPort,
        override_registry: Optional[OverrideRegistryPort] = None,
        constitution_validator: Optional[ConstitutionValidatorProtocol] = None,  # NEW
    ) -> None:
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.4] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR26] - Constitution Supremacy requirement
- [Source: src/application/services/override_service.py] - Override orchestration pattern
- [Source: src/application/services/witness_service.py] - Witness attestation pattern
- [Source: src/domain/errors/witness.py] - Witness error patterns
- [Source: _bmad-output/implementation-artifacts/stories/5-3-public-override-visibility.md] - Previous story

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 117 tests passing (89 unit + 28 integration)
- PM-4 mandatory tests in `test_suppress_witness_override.py` verified

### Completion Notes List

- FR26 Constitution Supremacy validation fully implemented
- Layered protection: validation occurs BEFORE event write in OverrideService
- Backward compatible: ConstitutionValidatorProtocol is optional in OverrideService
- Forbidden scopes: witness, witnessing, attestation, witness_service, witness_pool
- Forbidden patterns: witness.*, attestation.*
- All acceptance criteria (AC1, AC2, AC3) verified
- Cross-epic PM-4 requirement satisfied

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-07 | Story created with comprehensive FR26 context | Create-Story Workflow (Opus 4.5) |
| 2026-01-07 | Implementation complete - all 8 tasks done, 117 tests passing | Dev-Story Workflow (Opus 4.5) |

### File List

**Created:**
- `src/application/ports/constitution_validator.py` - Protocol for constitution validation
- `src/application/services/constitution_supremacy_service.py` - Validator service implementation
- `src/infrastructure/stubs/constitution_validator_stub.py` - Configurable test stub
- `tests/unit/domain/test_witness_suppression_error.py` - Error class tests
- `tests/unit/domain/test_forbidden_override_scopes.py` - Scope detection tests
- `tests/unit/application/test_constitution_supremacy_service.py` - Service unit tests
- `tests/integration/test_suppress_witness_override.py` - PM-4 mandatory integration tests
- `tests/integration/test_constitution_supremacy_integration.py` - End-to-end integration tests

**Modified:**
- `src/domain/errors/override.py` - Added WitnessSuppressionAttemptError
- `src/domain/errors/__init__.py` - Export new error
- `src/domain/models/override_reason.py` - Added forbidden scopes and detection function
- `src/domain/models/__init__.py` - Export validation function
- `src/application/ports/__init__.py` - Export protocol
- `src/application/services/__init__.py` - Export service
- `src/application/services/override_service.py` - Integrated validation step
- `src/infrastructure/stubs/__init__.py` - Export stub
- `tests/unit/application/test_override_service.py` - Added TestConstitutionValidation class
