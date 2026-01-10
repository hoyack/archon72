# Story 0.7: Constitutional Primitives (FR80, FR81)

Status: done

## Story

As a **developer**,
I want constitutional primitives PREVENT_DELETE and ENSURE_ATOMICITY,
So that I can build features on a foundation that prevents deletion and ensures atomic operations.

## Acceptance Criteria

### AC1: Domain Primitives Location

**Given** the domain layer
**When** I examine `src/domain/primitives/`
**Then** it contains:
  - `prevent_delete.py` with DeletePreventionMixin
  - `ensure_atomicity.py` with AtomicOperationContext

### AC2: DeletePreventionMixin Behavior

**Given** a model using DeletePreventionMixin
**When** I attempt to call `.delete()` on an instance
**Then** a `ConstitutionalViolationError` is raised
**And** the error message includes "FR80: Deletion prohibited"

### AC3: AtomicOperationContext Behavior

**Given** an AtomicOperationContext
**When** an exception occurs within the context
**Then** all changes are rolled back
**And** no partial state is persisted
**And** the exception is re-raised after rollback

### AC4: Unit Tests Pass Without Infrastructure

**Given** I want to test these primitives
**When** I run `pytest tests/unit/test_constitutional_primitives.py`
**Then** all primitive tests pass without infrastructure dependencies

## Tasks / Subtasks

- [x] Task 1: Create domain primitives directory structure (AC: 1)
  - [x] 1.1 Create `src/domain/primitives/` directory
  - [x] 1.2 Create `src/domain/primitives/__init__.py` with exports
  - [x] 1.3 Update `src/domain/__init__.py` to expose primitives module

- [x] Task 2: Implement ConstitutionalViolationError (AC: 2)
  - [x] 2.1 Create `src/domain/errors/constitutional.py`
  - [x] 2.2 Add `ConstitutionalViolationError` inheriting from `ConclaveError`
  - [x] 2.3 Export from `src/domain/errors/__init__.py`
  - [x] 2.4 Include FR reference in error message format

- [x] Task 3: Implement DeletePreventionMixin (AC: 2)
  - [x] 3.1 Create `src/domain/primitives/prevent_delete.py`
  - [x] 3.2 Implement mixin with `delete()` method that raises `ConstitutionalViolationError`
  - [x] 3.3 Include FR80 reference in error message
  - [x] 3.4 Add docstring explaining constitutional context

- [x] Task 4: Implement AtomicOperationContext (AC: 3)
  - [x] 4.1 Create `src/domain/primitives/ensure_atomicity.py`
  - [x] 4.2 Implement async context manager supporting rollback
  - [x] 4.3 Support both sync and async rollback handlers
  - [x] 4.4 Re-raise original exception after cleanup
  - [x] 4.5 Log rollback operations with structlog

- [x] Task 5: Create unit tests (AC: 4)
  - [x] 5.1 Create `tests/unit/domain/test_constitutional_primitives.py`
  - [x] 5.2 Test DeletePreventionMixin raises ConstitutionalViolationError
  - [x] 5.3 Test error message contains "FR80: Deletion prohibited"
  - [x] 5.4 Test AtomicOperationContext rollback on exception
  - [x] 5.5 Test AtomicOperationContext re-raises after rollback
  - [x] 5.6 Test AtomicOperationContext with multiple rollback handlers
  - [x] 5.7 Test no infrastructure dependencies (pure domain tests)

- [x] Task 6: Export primitives from domain module (AC: 1)
  - [x] 6.1 Export from `src/domain/primitives/__init__.py`
  - [x] 6.2 Verify imports work: `from src.domain.primitives import DeletePreventionMixin, AtomicOperationContext`

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → Unwitnessed actions are invalid
- **CT-13:** Integrity outranks availability → Availability may be sacrificed

**FR80 (Delete Prevention):**
> Constitutional events cannot be deleted. The DeletePreventionMixin ensures any attempt to delete raises an explicit constitutional violation error, making the forbidden operation visible rather than silent.

**FR81 (Atomicity):**
> All constitutional operations must be atomic. Either the complete operation succeeds, or the entire operation is rolled back with no partial state persisted. This is a foundation primitive that Epic 1 (Event Store) will build upon.

### Hexagonal Architecture Compliance

**Location:** `src/domain/primitives/` - pure domain layer, NO infrastructure imports allowed.

**Import Rules (CRITICAL):**
```python
# ALLOWED in domain/primitives/
from src.domain.exceptions import ConclaveError
from src.domain.errors.constitutional import ConstitutionalViolationError
import asyncio
import structlog  # Logging is acceptable

# FORBIDDEN - Will fail pre-commit hook
from src.infrastructure import ...  # VIOLATION!
from src.application import ...     # VIOLATION!
from src.api import ...             # VIOLATION!
```

### Implementation Patterns

**DeletePreventionMixin Pattern:**
```python
"""Constitutional primitive: Prevent deletion of domain entities (FR80)."""

from src.domain.errors.constitutional import ConstitutionalViolationError


class DeletePreventionMixin:
    """Mixin that prevents deletion of domain entities.

    Constitutional Constraint (FR80):
    Events and constitutional entities cannot be deleted.
    Any attempt to delete raises ConstitutionalViolationError.

    Usage:
        class MyEntity(BaseModel, DeletePreventionMixin):
            ...
    """

    def delete(self) -> None:
        """Raise ConstitutionalViolationError - deletion is prohibited.

        Raises:
            ConstitutionalViolationError: Always raised with FR80 reference.
        """
        raise ConstitutionalViolationError(
            "FR80: Deletion prohibited - constitutional entities are immutable"
        )
```

**AtomicOperationContext Pattern:**
```python
"""Constitutional primitive: Ensure atomic operations (FR81)."""

import asyncio
from typing import Any, Callable, Coroutine, Optional, Union
import structlog

log = structlog.get_logger()

RollbackHandler = Union[
    Callable[[], None],
    Callable[[], Coroutine[Any, Any, None]]
]


class AtomicOperationContext:
    """Context manager ensuring atomic operations with rollback.

    Constitutional Constraint (FR81):
    All constitutional operations must be atomic - complete success
    or complete rollback, never partial state.

    Usage:
        async with AtomicOperationContext() as ctx:
            ctx.add_rollback(cleanup_function)
            await do_operation()
            # On exception: cleanup_function called, exception re-raised
    """

    def __init__(self) -> None:
        self._rollback_handlers: list[RollbackHandler] = []

    def add_rollback(self, handler: RollbackHandler) -> None:
        """Register a rollback handler to be called on failure."""
        self._rollback_handlers.append(handler)

    async def __aenter__(self) -> "AtomicOperationContext":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any
    ) -> bool:
        if exc_val is not None:
            # Execute rollback handlers in reverse order
            log.info("atomic_operation_failed", error=str(exc_val))
            for handler in reversed(self._rollback_handlers):
                try:
                    result = handler()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as rollback_error:
                    log.error(
                        "rollback_handler_failed",
                        rollback_error=str(rollback_error)
                    )
            # Re-raise the original exception
            return False
        return False
```

**ConstitutionalViolationError Pattern:**
```python
"""Constitutional violation errors."""

from src.domain.exceptions import ConclaveError


class ConstitutionalViolationError(ConclaveError):
    """Raised when a constitutional constraint is violated.

    Constitutional violations are NEVER silently ignored.
    They represent fundamental breaches of system integrity.

    Error messages MUST include the FR reference (e.g., "FR80: ...").
    """
    pass
```

### Testing Requirements

**No Infrastructure Dependencies:**
- Tests MUST be pure unit tests
- No database, Redis, or external services
- Use in-memory test doubles only
- Tests should be fast (<100ms each)

**Test Patterns:**
```python
import pytest
from src.domain.primitives import DeletePreventionMixin, AtomicOperationContext
from src.domain.errors.constitutional import ConstitutionalViolationError


class TestEntity(DeletePreventionMixin):
    """Test entity for DeletePreventionMixin."""
    pass


class TestDeletePreventionMixin:
    def test_delete_raises_constitutional_violation(self) -> None:
        entity = TestEntity()
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            entity.delete()
        assert "FR80" in str(exc_info.value)
        assert "Deletion prohibited" in str(exc_info.value)


@pytest.mark.asyncio
class TestAtomicOperationContext:
    async def test_rollback_on_exception(self) -> None:
        rollback_called = False

        def rollback() -> None:
            nonlocal rollback_called
            rollback_called = True

        with pytest.raises(ValueError):
            async with AtomicOperationContext() as ctx:
                ctx.add_rollback(rollback)
                raise ValueError("Test error")

        assert rollback_called is True
```

### Project Structure Notes

**New Files to Create:**
```
src/domain/
├── primitives/              # NEW directory
│   ├── __init__.py         # Exports: DeletePreventionMixin, AtomicOperationContext
│   ├── prevent_delete.py   # DeletePreventionMixin implementation
│   └── ensure_atomicity.py # AtomicOperationContext implementation
└── errors/
    ├── __init__.py         # UPDATE: add ConstitutionalViolationError export
    └── constitutional.py   # NEW: ConstitutionalViolationError class
```

**Existing Files to Reference:**
- `src/domain/exceptions.py` - ConclaveError base class
- `src/domain/errors/hsm.py` - Pattern for error subclasses
- `src/domain/errors/__init__.py` - Export pattern

### Previous Story Learnings (Story 0.6)

From Story 0.6 completion:
- **Import boundary enforcement is active** - pre-commit hooks will reject cross-layer imports
- **Use `python3 -m` consistently** in Makefile targets
- All 34 tests passing (28 unit + 6 integration)
- **Test file organization:** `tests/unit/domain/` for domain layer tests

### Dependencies on Future Stories

**Epic 1 will use these primitives:**
- Story 1.1: Event Store will use DeletePreventionMixin on events
- Story 1.4: Atomic witness attribution will use AtomicOperationContext
- Story 1.6: Event Writer Service will use AtomicOperationContext

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 0.7: Constitutional Primitives (FR80, FR81)]
- [Source: _bmad-output/planning-artifacts/architecture.md#Constitutional Truths (CT-11, CT-12, CT-13)]
- [Source: _bmad-output/project-context.md#Critical Implementation Rules]
- [Source: _bmad-output/implementation-artifacts/stories/0-6-import-boundary-enforcement.md#Dev Agent Record]
- [Source: src/domain/exceptions.py#ConclaveError]
- [Source: src/domain/errors/hsm.py#Error class pattern]

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No significant debug issues encountered

### Completion Notes List

- **Task 1**: Created `src/domain/primitives/` directory with `__init__.py` exporting DeletePreventionMixin and AtomicOperationContext. Updated `src/domain/__init__.py` with import note for primitives module.

- **Task 2**: Created `src/domain/errors/constitutional.py` with ConstitutionalViolationError class inheriting from ConclaveError. Exported from `src/domain/errors/__init__.py`. Error messages include FR reference format.

- **Task 3**: Implemented DeletePreventionMixin in `src/domain/primitives/prevent_delete.py`. The `delete()` method raises ConstitutionalViolationError with message "FR80: Deletion prohibited - constitutional entities are immutable". Comprehensive docstrings explain constitutional context.

- **Task 4**: Implemented AtomicOperationContext async context manager in `src/domain/primitives/ensure_atomicity.py`. Supports both sync and async rollback handlers called in LIFO order. Uses structlog for logging rollback operations. Re-raises original exception after all rollback handlers complete.

- **Task 5**: Created 22 unit tests in `tests/unit/domain/test_constitutional_primitives.py`. Tests cover:
  - ConstitutionalViolationError inheritance and message preservation
  - DeletePreventionMixin raising error with FR80 reference
  - AtomicOperationContext rollback on exception
  - Multiple handlers called in reverse order
  - Mixed sync/async handler support
  - Rollback handler failure isolation
  - No infrastructure dependencies validation

- **Task 6**: Verified exports work correctly from `src.domain.primitives` and `src.domain.errors`.

### File List

**New Files:**
- `src/domain/primitives/__init__.py` - Module exports for constitutional primitives
- `src/domain/primitives/prevent_delete.py` - DeletePreventionMixin implementation (FR80)
- `src/domain/primitives/ensure_atomicity.py` - AtomicOperationContext implementation (FR81)
- `src/domain/errors/constitutional.py` - ConstitutionalViolationError class
- `tests/unit/domain/test_constitutional_primitives.py` - 22 unit tests

**Modified Files:**
- `src/domain/__init__.py` - Added import note for primitives module
- `src/domain/errors/__init__.py` - Added ConstitutionalViolationError export

### Change Log

- 2026-01-06: Story 0.7 implementation complete
  - Implemented constitutional primitives for FR80 (Delete Prevention) and FR81 (Atomicity)
  - DeletePreventionMixin prevents deletion with explicit ConstitutionalViolationError
  - AtomicOperationContext ensures atomic operations with rollback capability
  - 22 unit tests covering all acceptance criteria
  - Zero import boundary violations
  - All tests passing (22 new tests, 110 total unit tests pass)

- 2026-01-06: Code Review Complete (Claude Opus 4.5)
  - **Reviewer:** Claude Opus 4.5 (claude-opus-4-5-20251101)
  - **Issues Found:** 7 Medium (ruff linting), 3 Low (style)
  - **Issues Fixed:** All 7 ruff linting issues resolved
    - Fixed import sorting in `__init__.py`
    - Updated type annotations to use modern Python 3.10+ syntax (`X | None`)
    - Used `collections.abc` for `Callable` and `Coroutine` imports
    - Combined duplicate if branches in rollback handler detection
    - Fixed test function return type hint
  - **Final Status:** All acceptance criteria met, all tests passing (22/22), ruff clean, mypy clean

