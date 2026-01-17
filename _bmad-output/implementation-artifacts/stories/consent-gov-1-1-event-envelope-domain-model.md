# Story consent-gov-1.1: Event Envelope Domain Model

Status: done

---

## Story

As a **governance system operator**,
I want **a canonical event envelope structure**,
so that **all governance events have consistent metadata and can be validated, enabling deterministic replay and external verification**.

---

## Acceptance Criteria

1. **AC1:** `GovernanceEvent` domain model exists with `metadata` and `payload` fields, both immutable
2. **AC2:** Metadata includes all required fields: `event_id` (UUID), `event_type` (str), `timestamp` (datetime), `actor_id` (str), `schema_version` (str), `trace_id` (str)
3. **AC3:** Event type follows `branch.noun.verb` naming convention with validation (e.g., `executive.task.accepted`)
4. **AC4:** Branch is derived from `event_type` at write-time using `event_type.split('.')[0]`, not trusted from caller
5. **AC5:** Schema version field present on all events (format: `"1.0.0"` semver)
6. **AC6:** Unit tests for event envelope validation covering all acceptance criteria
7. **AC7:** Validation errors raise `ConstitutionalViolationError` with descriptive messages

---

## Tasks / Subtasks

- [x] **Task 1: Create governance events module structure** (AC: All)
  - [x] Create `src/domain/governance/__init__.py`
  - [x] Create `src/domain/governance/events/__init__.py`
  - [x] Create `src/domain/governance/events/event_envelope.py`
  - [x] Create `src/domain/governance/events/event_types.py` (registry)
  - [x] Create `src/domain/governance/events/schema_versions.py`

- [x] **Task 2: Implement EventMetadata dataclass** (AC: 2, 5)
  - [x] Define frozen dataclass with all metadata fields
  - [x] Add validation in `__post_init__` for all fields
  - [x] Implement `schema_version` semver validation

- [x] **Task 3: Implement GovernanceEvent dataclass** (AC: 1, 3, 4)
  - [x] Define frozen dataclass with `metadata` and `payload` fields
  - [x] Implement `branch.noun.verb` event_type validation regex
  - [x] Implement `_derive_branch()` function that splits event_type
  - [x] Freeze payload dict to MappingProxyType (existing pattern)

- [x] **Task 4: Implement event type registry** (AC: 3)
  - [x] Create `GOVERNANCE_EVENT_TYPES` enum/frozenset
  - [x] Add validation against known event types
  - [x] Add extensibility mechanism for future event types

- [x] **Task 5: Write comprehensive unit tests** (AC: 6, 7)
  - [x] Test valid event creation
  - [x] Test invalid event_type format rejection
  - [x] Test branch derivation correctness
  - [x] Test metadata field validation
  - [x] Test payload immutability
  - [x] Test schema_version validation
  - [x] Test ConstitutionalViolationError messages

---

## Documentation Checklist

- [x] Architecture docs updated (new governance module structure) - Module docstrings document structure
- [x] Inline comments added for validation logic - All validation methods documented
- [x] N/A - API docs (no endpoints in this story)
- [x] N/A - README (internal domain model)

---

## Dev Notes

### Architecture Compliance (CRITICAL)

**From governance-architecture.md:**

This story implements the foundational event envelope pattern defined in the architecture document.

**Event Envelope Pattern (Locked):**
```json
{
  "metadata": {
    "event_id": "uuid",
    "event_type": "executive.task.accepted",
    "schema_version": "1.0.0",
    "timestamp": "2026-01-16T00:00:00Z",
    "actor_id": "archon-or-officer-id",
    "prev_hash": "sha256:...",
    "hash": "blake3:..."
  },
  "payload": {
    // Domain-specific event data
  }
}
```

**Event Naming Convention:**
- Pattern: `{branch}.{noun}.{verb}`
- Branch: `executive`, `judicial`, `witness`, `filter`, etc.
- Noun: Aggregate or entity (`task`, `panel`, `observation`)
- Verb: Past-tense action (`accepted`, `convened`, `recorded`)

**Branch Derivation (MANDATORY):**
```python
def _derive_branch(event_type: str) -> str:
    """Branch is derived at write-time, NEVER trusted from caller."""
    return event_type.split('.')[0]
```

**NOTE:** This story creates the envelope structure WITHOUT hash fields (prev_hash, hash). Those are added in story consent-gov-1-3 (Hash Chain Implementation). This story focuses on the metadata/payload separation and event type validation.

### Existing Patterns to Follow

**Reference:** `src/domain/events/event.py`

The existing `Event` class demonstrates patterns to follow:
- Frozen dataclass with `frozen=True`
- `MappingProxyType` for immutable payload
- Validation in `__post_init__`
- `ConstitutionalViolationError` for validation failures
- Factory method pattern (`create_with_hash`)

**Key Difference:** This new `GovernanceEvent` is for the consent-based governance system, separate from the existing deliberation events.

### Source Tree Components

**New Files:**
```
src/domain/governance/
├── __init__.py
└── events/
    ├── __init__.py
    ├── event_envelope.py      # GovernanceEvent, EventMetadata
    ├── event_types.py         # Event type registry and validation
    └── schema_versions.py     # Schema version constants
```

**Test Files:**
```
tests/unit/domain/governance/
├── __init__.py
└── events/
    ├── __init__.py
    └── test_event_envelope.py
```

### Technical Requirements

**Python Patterns (CRITICAL):**
- ALL dataclasses must use `frozen=True` for immutability
- Use `MappingProxyType` from `types` module for payload
- Use `object.__setattr__` pattern for frozen dataclass initialization
- Type hints on ALL functions (mypy --strict must pass)
- Import from `src.domain.errors.constitutional import ConstitutionalViolationError`

**Validation Requirements:**
- Event type regex: `^[a-z]+\.[a-z]+\.[a-z_]+$` (branch.noun.verb)
- Schema version regex: `^\d+\.\d+\.\d+$` (semver)
- UUID validation for event_id
- Datetime validation for timestamp
- Non-empty string validation for actor_id, trace_id

### Testing Standards

**Test File Location:** `tests/unit/domain/governance/events/test_event_envelope.py`

**Test Patterns:**
```python
import pytest
from uuid import uuid4
from datetime import datetime, timezone

class TestGovernanceEvent:
    def test_valid_event_creation(self):
        """GovernanceEvent with valid data creates successfully."""

    def test_invalid_event_type_format_raises(self):
        """Event type not matching branch.noun.verb raises ConstitutionalViolationError."""

    def test_branch_derived_from_event_type(self):
        """Branch is derived from event_type.split('.')[0], not from input."""

    def test_payload_is_immutable(self):
        """Payload dict is converted to MappingProxyType."""
```

**Coverage Requirement:** 100% for domain models

### Library/Framework Requirements

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Dataclasses, type hints |
| pytest | latest | Unit testing |
| types.MappingProxyType | stdlib | Immutable dict wrapper |

No external dependencies needed - pure domain model.

### Project Structure Notes

**Alignment:** This story creates the new `src/domain/governance/` module per architecture specification (Step 6).

**Import Rules (Hexagonal):**
- Domain layer imports NOTHING from other layers
- Domain errors imported from `src/domain/errors/`
- No infrastructure imports allowed

### References

- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Event Envelope Pattern (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Event Naming Convention (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Core Architectural Decisions - Category 1]
- [Source: _bmad-output/planning-artifacts/government-epics.md#GOV-1-1]
- [Source: src/domain/events/event.py] - Reference implementation pattern
- [Source: _bmad-output/project-context.md#Critical Implementation Rules]

### FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| FR1-FR2 | Events must be hash-chained and witnessed | Hash fields deferred to story 1-3; envelope structure prepared |
| AD-4 | Event envelope pattern | Metadata + payload separation |
| AD-5 | Event naming convention | `branch.noun.verb` validation |
| AD-15 | Branch derivation at write-time | `_derive_branch()` function |
| AD-17 | Schema versioning | `schema_version` field |
| NFR-AUDIT-06 | Deterministic replay | Immutable, version-tagged events |
| NFR-CONST-02 | Event integrity | Validation before creation |

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - clean implementation with all tests passing on first run.

### Completion Notes List

- Created new `src/domain/governance/` module for consent-based governance system
- Implemented `EventMetadata` frozen dataclass with all required fields per AD-4
- Implemented `GovernanceEvent` frozen dataclass with metadata + payload separation
- Event type validation uses regex `^[a-z]+\.[a-z]+\.[a-z_]+$` for branch.noun.verb pattern
- Branch derivation implemented at property access time via `event_type.split('.')[0]`
- Schema version validation enforces semver format (X.Y.Z)
- Created `GovernanceEventType` enum with 30 known event types across 9 branches
- All validation errors raise `ConstitutionalViolationError` with AD-* reference codes
- Payload automatically frozen to `MappingProxyType` for immutability
- Factory method `GovernanceEvent.create()` for convenient event creation
- **34 unit tests passing** covering all acceptance criteria

### File List

**Created:**
- `src/domain/governance/__init__.py`
- `src/domain/governance/events/__init__.py`
- `src/domain/governance/events/event_envelope.py` (EventMetadata, GovernanceEvent)
- `src/domain/governance/events/event_types.py` (GovernanceEventType enum, validation, derive_branch)
- `src/domain/governance/events/schema_versions.py` (CURRENT_SCHEMA_VERSION, validation)
- `tests/unit/domain/governance/__init__.py`
- `tests/unit/domain/governance/events/__init__.py`
- `tests/unit/domain/governance/events/test_event_envelope.py` (34 tests)

