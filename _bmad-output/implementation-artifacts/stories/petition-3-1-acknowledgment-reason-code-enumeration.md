# Story 3.1: Acknowledgment Reason Code Enumeration

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-3-1 |
| **Epic** | Epic 3: Acknowledgment Execution |
| **Priority** | P1 |
| **Status** | done |
| **Completed** | 2026-01-19 |
| **Created** | 2026-01-19 |

## User Story

**As a** developer,
**I want** an enumerated list of acknowledgment reason codes,
**So that** all acknowledgments use standardized, auditable reasons.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-3.2 | System SHALL require reason_code from: OUT_OF_SCOPE, DUPLICATE, MALFORMED, NO_ACTION_WARRANTED, REFUSED, WITHDRAWN, EXPIRED | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target | Measurement |
|--------|-------------|--------|-------------|
| NFR-6.1 | All fate transitions witnessed | Event with actor, timestamp, reason | CT-12 compliance |
| NFR-6.3 | Rationale preservation | REFUSED/NO_ACTION rationale stored | Audit queryable |

### Constitutional Truths

- **CT-12**: "Every action that affects an Archon must be witnessed" - Reason codes enable witnessing
- **CT-14**: "Every claim terminates in visible, witnessed fate" - ACKNOWLEDGED is a terminal fate

## Acceptance Criteria

### AC-1: Reason Code Enumeration Definition

**Given** the acknowledgment domain model
**When** I define reason codes
**Then** the following enum values exist:
- `ADDRESSED`: Concern has been or will be addressed by existing governance action
- `NOTED`: Input has been recorded for future consideration
- `DUPLICATE`: Petition duplicates an existing or resolved petition (requires reference)
- `OUT_OF_SCOPE`: Matter falls outside governance jurisdiction
- `REFUSED`: Petition violates policy or norms (requires rationale)
- `NO_ACTION_WARRANTED`: After review, no action is appropriate (requires rationale)
- `WITHDRAWN`: Petitioner withdrew the petition
- `EXPIRED`: Referral timeout with no Knight response
**And** the enum is named `AcknowledgmentReasonCode`
**And** the enum values are strings for database compatibility

### AC-2: Rationale Requirement Enforcement

**Given** an acknowledgment with a reason code
**When** the reason code is `REFUSED` or `NO_ACTION_WARRANTED`
**Then** a non-empty `rationale` field is required
**And** attempting to create an acknowledgment without rationale raises `RationaleRequiredError`

**Given** an acknowledgment with a reason code
**When** the reason code is `DUPLICATE`
**Then** a valid `reference_petition_id` field is required
**And** attempting to create an acknowledgment without reference raises `ReferenceRequiredError`

**Given** an acknowledgment with any other reason code
**When** creating the acknowledgment
**Then** rationale is optional (but recommended)

### AC-3: Enum Validation

**Given** an acknowledgment reason code string
**When** converting to `AcknowledgmentReasonCode`
**Then** valid values are accepted
**And** invalid values raise `InvalidReasonCodeError`
**And** case-insensitive matching is supported (e.g., "refused" → REFUSED)

### AC-4: Database Enum Type

**Given** the PostgreSQL database schema
**When** creating the acknowledgment table
**Then** a database enum type `acknowledgment_reason_enum` is created
**And** the enum contains all 8 reason codes
**And** the migration is reversible (supports rollback)

### AC-5: Domain Model Integration

**Given** the `AcknowledgmentReasonCode` enum
**When** used in the domain model
**Then** it integrates with the existing petition domain models
**And** it follows the established pattern from `PetitionState` enum
**And** it is exported from `src/domain/models/__init__.py`

## Technical Design

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/domain/models/acknowledgment_reason.py` | Create | Domain model with enum and validation |
| `src/domain/models/__init__.py` | Modify | Export `AcknowledgmentReasonCode` |
| `migrations/021_create_acknowledgment_reason_enum.sql` | Create | Database enum type |
| `tests/unit/domain/models/test_acknowledgment_reason.py` | Create | Unit tests |
| `tests/integration/test_acknowledgment_reason_persistence.py` | Create | Integration tests |

### Domain Model Design

```python
from enum import StrEnum
from dataclasses import dataclass
from uuid import UUID

class AcknowledgmentReasonCode(StrEnum):
    """Enumeration of valid acknowledgment reason codes per FR-3.2."""
    ADDRESSED = "ADDRESSED"
    NOTED = "NOTED"
    DUPLICATE = "DUPLICATE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    REFUSED = "REFUSED"
    NO_ACTION_WARRANTED = "NO_ACTION_WARRANTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"

    @classmethod
    def requires_rationale(cls, code: "AcknowledgmentReasonCode") -> bool:
        """Returns True if this reason code requires mandatory rationale."""
        return code in {cls.REFUSED, cls.NO_ACTION_WARRANTED}

    @classmethod
    def requires_reference(cls, code: "AcknowledgmentReasonCode") -> bool:
        """Returns True if this reason code requires reference_petition_id."""
        return code == cls.DUPLICATE


class RationaleRequiredError(ValueError):
    """Raised when rationale is required but not provided."""
    pass


class ReferenceRequiredError(ValueError):
    """Raised when reference_petition_id is required but not provided."""
    pass


class InvalidReasonCodeError(ValueError):
    """Raised when an invalid reason code string is provided."""
    pass
```

### Database Migration Design

```sql
-- Migration: 021_create_acknowledgment_reason_enum
-- FR-3.2: Acknowledgment reason codes enumeration

BEGIN;

-- Create the enum type for acknowledgment reasons
CREATE TYPE acknowledgment_reason_enum AS ENUM (
    'ADDRESSED',
    'NOTED',
    'DUPLICATE',
    'OUT_OF_SCOPE',
    'REFUSED',
    'NO_ACTION_WARRANTED',
    'WITHDRAWN',
    'EXPIRED'
);

-- Add comment for documentation
COMMENT ON TYPE acknowledgment_reason_enum IS
    'Acknowledgment reason codes per FR-3.2. REFUSED and NO_ACTION_WARRANTED require rationale. DUPLICATE requires reference_petition_id.';

COMMIT;

-- Rollback:
-- DROP TYPE IF EXISTS acknowledgment_reason_enum;
```

## Definition of Done

- [x] `AcknowledgmentReasonCode` enum created with all 8 values
- [x] `requires_rationale()` class method implemented
- [x] `requires_reference()` class method implemented
- [x] Custom exception classes created
- [x] Case-insensitive parsing supported
- [x] Database migration created and tested
- [x] Unit tests with >90% coverage
- [x] Integration test for enum persistence
- [x] Exported from domain models `__init__.py`
- [ ] Code review completed

## Test Plan

### Unit Tests

1. **test_all_reason_codes_exist**: Verify all 8 codes are defined
2. **test_requires_rationale_for_refused**: Verify REFUSED requires rationale
3. **test_requires_rationale_for_no_action_warranted**: Verify NO_ACTION_WARRANTED requires rationale
4. **test_other_codes_do_not_require_rationale**: Verify other codes don't require rationale
5. **test_requires_reference_for_duplicate**: Verify DUPLICATE requires reference
6. **test_other_codes_do_not_require_reference**: Verify other codes don't require reference
7. **test_case_insensitive_parsing**: Verify "refused" → REFUSED works
8. **test_invalid_code_raises_error**: Verify invalid codes raise InvalidReasonCodeError
9. **test_enum_string_values**: Verify enum values match expected strings
10. **test_enum_is_strenum**: Verify enum extends StrEnum for database compatibility

### Integration Tests

1. **test_enum_type_exists_in_database**: Verify acknowledgment_reason_enum type exists
2. **test_all_enum_values_in_database**: Verify all 8 values exist in DB enum
3. **test_migration_rollback**: Verify migration can be rolled back cleanly

## Dependencies

- Epic 2A/2B deliberation infrastructure (for disposition → acknowledgment flow)
- Existing petition domain models
- PostgreSQL database

## Notes

- This story establishes the vocabulary for acknowledgment - the actual execution service is Story 3.2
- Reason codes align with PRD Section 13 "Acknowledgment Reason Codes"
- Updated codes from PRD to match epic spec (added ADDRESSED, NOTED; both align with formal acknowledgment semantics)
- StrEnum requires Python 3.11+ (consistent with existing codebase pattern)
