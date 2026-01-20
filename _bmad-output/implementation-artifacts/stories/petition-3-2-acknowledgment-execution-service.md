# Story 3.2: Acknowledgment Execution Service

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-3-2 |
| **Epic** | Epic 3: Acknowledgment Execution |
| **Priority** | P1 |
| **Status** | done |
| **Completed** | 2026-01-19 |
| **Created** | 2026-01-19 |
| **Dependencies** | Story 3.1 (AcknowledgmentReasonCode enum) |

## User Story

**As a** system,
**I want** to execute acknowledgment when deliberation determines ACKNOWLEDGE fate,
**So that** petitions receive formal closure with proper documentation.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-3.1 | Marquis SHALL be able to ACKNOWLEDGE petition with reason code | P0 |
| FR-3.3 | System SHALL require rationale text for REFUSED and NO_ACTION_WARRANTED | P0 |
| FR-3.4 | System SHALL require reference_petition_id for DUPLICATE | P1 |

### Non-Functional Requirements

| NFR ID | Requirement | Target | Measurement |
|--------|-------------|--------|-------------|
| NFR-6.1 | All fate transitions witnessed | Event with actor, timestamp, reason | CT-12 compliance |
| NFR-6.3 | Rationale preservation | REFUSED/NO_ACTION rationale stored | Audit queryable |
| NFR-3.2 | Fate assignment atomicity | 100% single-fate | No double acknowledgment |

### Constitutional Truths

- **CT-12**: "Every action that affects an Archon must be witnessed" - Acknowledgment event witnessed
- **CT-14**: "Every claim terminates in visible, witnessed fate" - ACKNOWLEDGED is terminal fate

## Acceptance Criteria

### AC-1: Acknowledgment Record Creation

**Given** a petition with deliberation outcome = ACKNOWLEDGE
**When** the acknowledgment is executed
**Then** an `Acknowledgment` record is created with:
- `id`: UUID for the acknowledgment
- `petition_id`: Reference to the petition
- `reason_code`: From AcknowledgmentReasonCode enum
- `rationale`: Text explaining the decision (required for REFUSED/NO_ACTION_WARRANTED)
- `reference_petition_id`: For DUPLICATE reason code (optional otherwise)
- `acknowledging_archon_ids`: List of 2+ archons who voted ACKNOWLEDGE
- `acknowledged_at`: UTC timestamp
- `witness_hash`: Blake3 hash of the acknowledgment for witnessing
**And** validation from Story 3.1 is enforced (rationale/reference requirements)

### AC-2: State Transition Execution

**Given** a petition in DELIBERATING state
**When** acknowledgment execution is triggered
**Then** the petition state transitions: DELIBERATING → ACKNOWLEDGED
**And** the transition is atomic (no intermediate states visible)
**And** the petition's `fate_reason` is set to the reason code

**Given** a petition NOT in DELIBERATING state
**When** acknowledgment execution is attempted
**Then** `InvalidStateTransitionError` is raised
**And** no state change occurs
**And** the error is logged with petition details

### AC-3: Event Emission

**Given** successful acknowledgment execution
**When** the state transition completes
**Then** a `PetitionAcknowledged` event is emitted containing:
- `petition_id`
- `reason_code`
- `rationale` (if provided)
- `acknowledging_archon_ids`
- `acknowledged_at`
- `witness_hash`
**And** the event is persisted via EventWriterService
**And** CT-12 witnessing requirement is satisfied

### AC-4: Protocol Interface

**Given** the need for testability and separation of concerns
**When** designing the service
**Then** `AcknowledgmentExecutionProtocol` defines the interface
**And** `AcknowledgmentExecutionService` implements the protocol
**And** a stub implementation exists for testing

### AC-5: Idempotency

**Given** an acknowledgment that was already executed for a petition
**When** execution is attempted again
**Then** the operation is idempotent (no error, returns existing acknowledgment)
**Or** raises `AlreadyAcknowledgedError` if strict mode is enabled

## Technical Design

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/domain/models/acknowledgment.py` | Create | Acknowledgment aggregate root |
| `src/domain/events/acknowledgment.py` | Create | PetitionAcknowledged event |
| `src/domain/errors/acknowledgment.py` | Create | Domain errors |
| `src/application/ports/acknowledgment_execution.py` | Create | Protocol definition |
| `src/application/services/acknowledgment_execution_service.py` | Create | Service implementation |
| `src/infrastructure/stubs/acknowledgment_execution_stub.py` | Create | Test stub |
| `migrations/022_create_acknowledgments_table.sql` | Create | Database table |
| `tests/unit/domain/models/test_acknowledgment.py` | Create | Domain model tests |
| `tests/unit/application/services/test_acknowledgment_execution_service.py` | Create | Service tests |
| `tests/integration/test_acknowledgment_execution_integration.py` | Create | Integration tests |

### Domain Model Design

```python
@dataclass(frozen=True)
class Acknowledgment:
    """Acknowledgment record for a petition (FR-3.1).

    Represents the formal closure of a petition with ACKNOWLEDGED fate.
    Created when deliberation reaches consensus on ACKNOWLEDGE disposition.
    """
    id: UUID
    petition_id: UUID
    reason_code: AcknowledgmentReasonCode
    rationale: str | None  # Required for REFUSED, NO_ACTION_WARRANTED
    reference_petition_id: UUID | None  # Required for DUPLICATE
    acknowledging_archon_ids: tuple[int, ...]  # 2+ archons who voted ACKNOWLEDGE
    acknowledged_at: datetime
    witness_hash: str  # Blake3 hash for CT-12 compliance

    def __post_init__(self) -> None:
        validate_acknowledgment_requirements(
            self.reason_code,
            self.rationale,
            self.reference_petition_id,
        )
        if len(self.acknowledging_archon_ids) < 2:
            raise ValueError("At least 2 acknowledging archons required")
```

### Protocol Design

```python
class AcknowledgmentExecutionProtocol(Protocol):
    """Protocol for executing petition acknowledgments (FR-3.1)."""

    async def execute(
        self,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        acknowledging_archon_ids: Sequence[int],
        rationale: str | None = None,
        reference_petition_id: UUID | None = None,
    ) -> Acknowledgment:
        """Execute acknowledgment for a petition.

        Args:
            petition_id: The petition to acknowledge
            reason_code: Reason for acknowledgment
            acknowledging_archon_ids: Archons who voted ACKNOWLEDGE (min 2)
            rationale: Required for REFUSED/NO_ACTION_WARRANTED
            reference_petition_id: Required for DUPLICATE

        Returns:
            The created Acknowledgment record

        Raises:
            InvalidStateTransitionError: Petition not in DELIBERATING state
            RationaleRequiredError: Rationale missing for REFUSED/NO_ACTION_WARRANTED
            ReferenceRequiredError: Reference missing for DUPLICATE
            PetitionNotFoundError: Petition doesn't exist
        """
        ...
```

### Database Migration Design

```sql
-- Migration: 022_create_acknowledgments_table
CREATE TABLE acknowledgments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    petition_id UUID NOT NULL REFERENCES petition_submissions(id) ON DELETE RESTRICT,
    reason_code acknowledgment_reason_enum NOT NULL,
    rationale TEXT,
    reference_petition_id UUID REFERENCES petition_submissions(id),
    acknowledging_archon_ids INTEGER[] NOT NULL,
    acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    witness_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT ck_min_archons CHECK (array_length(acknowledging_archon_ids, 1) >= 2),
    CONSTRAINT ck_rationale_for_refused CHECK (
        (reason_code NOT IN ('REFUSED', 'NO_ACTION_WARRANTED'))
        OR (rationale IS NOT NULL AND length(rationale) > 0)
    ),
    CONSTRAINT ck_reference_for_duplicate CHECK (
        (reason_code != 'DUPLICATE')
        OR (reference_petition_id IS NOT NULL)
    ),

    -- One acknowledgment per petition
    CONSTRAINT uq_petition_acknowledgment UNIQUE (petition_id)
);

CREATE INDEX idx_acknowledgments_reason ON acknowledgments(reason_code);
CREATE INDEX idx_acknowledgments_acknowledged_at ON acknowledgments(acknowledged_at);
```

## Definition of Done

- [ ] `Acknowledgment` domain model created with validation
- [ ] `PetitionAcknowledged` event created
- [ ] `AcknowledgmentExecutionProtocol` defined
- [ ] `AcknowledgmentExecutionService` implemented
- [ ] Stub implementation created
- [ ] Database migration with constraints
- [ ] State transition DELIBERATING → ACKNOWLEDGED works
- [ ] Event emission via EventWriterService
- [ ] Idempotency handled
- [ ] Unit tests with >90% coverage
- [ ] Integration tests
- [ ] Code review completed

## Test Plan

### Unit Tests

1. **test_acknowledgment_creation_valid**: Valid acknowledgment creates successfully
2. **test_acknowledgment_requires_min_two_archons**: Less than 2 archons fails
3. **test_acknowledgment_validates_rationale_requirement**: REFUSED without rationale fails
4. **test_acknowledgment_validates_reference_requirement**: DUPLICATE without reference fails
5. **test_service_execute_happy_path**: Successful acknowledgment execution
6. **test_service_rejects_non_deliberating_petition**: InvalidStateTransitionError raised
7. **test_service_emits_acknowledged_event**: Event emitted and witnessed
8. **test_service_idempotent_execution**: Re-execution returns existing acknowledgment

### Integration Tests

1. **test_acknowledgment_persisted_to_database**: Acknowledgment record saved
2. **test_petition_state_updated_atomically**: State transition is atomic
3. **test_event_witnessed_in_database**: Event persisted with witness hash
4. **test_database_constraints_enforced**: Invalid data rejected at DB level

## Notes

- This story implements the execution path when deliberation reaches ACKNOWLEDGE consensus
- Builds on Story 3.1's AcknowledgmentReasonCode enum and validation
- The service will be called by the disposition routing from Story 2A.8
- CT-12 witnessing is critical - every acknowledgment must be witnessed
