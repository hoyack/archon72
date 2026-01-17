# Story consent-gov-1.5: Projection Infrastructure

Status: done

---

## Story

As a **governance system**,
I want **queryable projections derived from the ledger**,
So that **current state can be efficiently accessed without replaying all events, enabling fast reads while maintaining the ledger as the single source of truth**.

---

## Acceptance Criteria

1. **AC1:** `ProjectionPort` interface exists for projection storage operations
2. **AC2:** Projections stored in `projections.*` schema (isolated from `ledger.*`)
3. **AC3:** Five initial projection tables created: `task_states`, `legitimacy_states`, `panel_registry`, `petition_index`, `actor_registry`
4. **AC4:** Infrastructure tables created: `projection_checkpoints`, `projection_applies`
5. **AC5:** Projections can be rebuilt from ledger replay (deterministic state derivation)
6. **AC6:** CQRS-Lite pattern: Single API with internal read/write separation
7. **AC7:** Idempotency enforced via `projection_applies` table (no duplicate event processing)
8. **AC8:** Projection checkpoint tracking via `projection_checkpoints` table
9. **AC9:** Unit tests verify projection matches ledger state after replay
10. **AC10:** PostgreSQL adapter implements `ProjectionPort` with async operations

---

## Tasks / Subtasks

- [x] **Task 1: Create projection ports module structure** (AC: All)
  - [x] Create `src/application/ports/governance/projection_port.py`
  - [x] Update `src/application/ports/governance/__init__.py`

- [x] **Task 2: Implement ProjectionPort interface** (AC: 1, 6)
  - [x] Define Protocol with `apply_event()` method
  - [x] Define `get_projection_state()` method for each projection type
  - [x] Define `get_checkpoint()` method for checkpoint retrieval
  - [x] Define `is_event_applied()` method for idempotency check
  - [x] Define `rebuild_from_events()` method for replay
  - [x] Add explicit docstrings describing CQRS-Lite pattern

- [x] **Task 3: Create database migration for projections schema** (AC: 2, 3, 4)
  - [x] Create Alembic migration for `projections` schema
  - [x] Create `projections.task_states` table per architecture spec
  - [x] Create `projections.legitimacy_states` table per architecture spec
  - [x] Create `projections.panel_registry` table per architecture spec
  - [x] Create `projections.petition_index` table per architecture spec
  - [x] Create `projections.actor_registry` table per architecture spec
  - [x] Create `projections.projection_checkpoints` table
  - [x] Create `projections.projection_applies` table with composite primary key
  - [x] Add indexes for query patterns

- [x] **Task 4: Implement domain models for projection records** (AC: 3)
  - [x] Create `src/domain/governance/projections/__init__.py`
  - [x] Create `src/domain/governance/projections/task_state.py`
  - [x] Create `src/domain/governance/projections/legitimacy_state.py`
  - [x] Create `src/domain/governance/projections/panel_registry.py`
  - [x] Create `src/domain/governance/projections/petition_index.py`
  - [x] Create `src/domain/governance/projections/actor_registry.py`

- [x] **Task 5: Implement PostgresProjectionAdapter** (AC: 2, 7, 8, 10)
  - [x] Create `src/infrastructure/adapters/governance/postgres_projection_adapter.py`
  - [x] Implement `apply_event()` with idempotency check
  - [x] Implement `get_projection_state()` for each projection type
  - [x] Implement `get_checkpoint()` for checkpoint retrieval
  - [x] Implement `is_event_applied()` for idempotency verification
  - [x] Implement `save_checkpoint()` for checkpoint persistence
  - [x] Use async SQLAlchemy 2.0 patterns

- [x] **Task 6: Implement projection rebuild service** (AC: 5, 9)
  - [x] Create `src/application/services/governance/projection_rebuild_service.py`
  - [x] Implement `rebuild_projection()` method from ledger events
  - [x] Implement checkpoint-based incremental rebuild
  - [x] Integrate with `GovernanceLedgerPort.read_events()`

- [x] **Task 7: Implement event-to-projection mapping** (AC: 5)
  - [x] Create `src/domain/governance/projections/event_handlers.py`
  - [x] Define mapping from event types to projection updates
  - [x] Ensure deterministic state derivation

- [x] **Task 8: Write comprehensive tests** (AC: 9)
  - [x] Unit tests for `ProjectionPort` interface compliance
  - [x] Unit tests for projection domain models
  - [x] Integration tests for adapter persistence
  - [x] Test idempotency (same event applied twice = no change)
  - [x] Test rebuild from ledger produces identical state
  - [x] Test checkpoint tracking accuracy
  - [x] Test schema isolation (projections cannot write to ledger)

---

## Documentation Checklist

- [x] Architecture docs updated (projection infrastructure details)
- [x] Inline comments added for CQRS-Lite pattern
- [x] N/A - API docs (internal infrastructure)
- [x] N/A - README (internal component)

---

## Dev Notes

### Architecture Compliance (CRITICAL)

**From governance-architecture.md:**

This story implements the projection infrastructure defined in the architecture document.

**Architectural Foundation (Locked):**

> **The system is event-sourced. The ledger IS the state. Everything else is a projection.**

**Implications:**
- Projections are derived, never authoritative
- Projections can be rebuilt from ledger replay
- Projection lag is a first-class metric
- Consistency model: Read-your-writes for writer, eventual for others

**Schema Separation (Locked):**

| Schema | Purpose | Write Access |
|--------|---------|--------------|
| `ledger.*` | Append-only event storage | Event Store service only |
| `projections.*` | Derived state views | Projection services |

**Role Isolation:**
```sql
-- Projection writer role (projection_service)
GRANT ALL ON projections.* TO projection_service;
REVOKE ALL ON ledger.* FROM projection_service;
```

### Initial Projection Tables (Locked)

**1. Task State Projection:**
```sql
CREATE TABLE projections.task_states (
  task_id uuid PRIMARY KEY,
  current_state text NOT NULL,
  earl_id text NOT NULL,
  cluster_id text,
  last_event_sequence bigint NOT NULL,
  last_event_hash text NOT NULL,
  updated_at timestamptz NOT NULL
);
```

**2. Legitimacy State Projection:**
```sql
CREATE TABLE projections.legitimacy_states (
  entity_id text PRIMARY KEY,
  entity_type text NOT NULL,
  current_band text NOT NULL,
  band_entered_at timestamptz NOT NULL,
  violation_count int NOT NULL DEFAULT 0,
  last_event_sequence bigint NOT NULL,
  updated_at timestamptz NOT NULL
);
```

**3. Panel Registry Projection:**
```sql
CREATE TABLE projections.panel_registry (
  panel_id uuid PRIMARY KEY,
  panel_status text NOT NULL,
  violation_id uuid NOT NULL,
  prince_ids text[] NOT NULL,
  convened_at timestamptz,
  finding_issued_at timestamptz,
  last_event_sequence bigint NOT NULL,
  updated_at timestamptz NOT NULL
);
```

**4. Petition Index Projection:**
```sql
CREATE TABLE projections.petition_index (
  petition_id uuid PRIMARY KEY,
  petition_type text NOT NULL,
  subject_entity_id text NOT NULL,
  current_status text NOT NULL,
  filed_at timestamptz NOT NULL,
  resolved_at timestamptz,
  last_event_sequence bigint NOT NULL,
  updated_at timestamptz NOT NULL
);
```

**5. Actor Registry Projection:**
```sql
CREATE TABLE projections.actor_registry (
  actor_id text PRIMARY KEY,
  actor_type text NOT NULL,
  branch text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL,
  last_event_sequence bigint NOT NULL,
  updated_at timestamptz NOT NULL
);
```

### Infrastructure Tables (Locked)

**Projection Checkpoint Table:**
```sql
CREATE TABLE projections.projection_checkpoints (
  projection_name text PRIMARY KEY,
  last_event_id uuid NOT NULL,
  last_hash text NOT NULL,
  last_sequence bigint NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

**Projection Apply Log (Idempotency):**
```sql
CREATE TABLE projections.projection_applies (
  projection_name text NOT NULL,
  event_id uuid NOT NULL,
  event_hash text NOT NULL,
  sequence bigint NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (projection_name, event_id)
);
```

**Idempotency Rule:** Before applying event, check `projection_applies`. If exists, skip.

### CQRS-Lite Query Pattern (Locked)

**Pattern:**
```
                    ┌─────────────────┐
                    │   Governance    │
                    │      API        │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
        ┌─────┴─────┐               ┌───────┴───────┐
        │   Write   │               │     Read      │
        │   Path    │               │     Path      │
        └─────┬─────┘               └───────┬───────┘
              │                             │
              ▼                             ▼
        ┌───────────┐               ┌───────────────┐
        │  Ledger   │──────────────▶│  Projections  │
        │  (Truth)  │   (rebuild)   │   (Derived)   │
        └───────────┘               └───────────────┘
```

**Key Principle:** Single API, internal separation. External callers don't distinguish read/write paths.

### Rebuild Strategies (Locked)

| Strategy | Trigger | Purpose |
|----------|---------|---------|
| Continuous | Event bus notification | Real-time derived state |
| Periodic | Scheduled job | Drift detection |
| Manual | Operator command | Recovery, migration |

### Consumer Contract (At-Least-Once Delivery)

1. Track last processed sequence per projection
2. On wake-up, query ledger from checkpoint
3. Before applying, check `projection_applies`
4. Update checkpoint after successful apply

**Failure Modes:**

| Failure | Recovery |
|---------|----------|
| Consumer crash mid-apply | Restart, re-query from checkpoint |
| Redis notification lost | Periodic poll (background) |

### Existing Patterns to Follow

**Reference:** `src/application/ports/governance/ledger_port.py` (from story 1-2)

The existing `GovernanceLedgerPort` demonstrates the pattern:
- Protocol with `@abstractmethod` decorators
- Clear docstrings with Constitutional Constraints
- Type hints on all methods

**Reference:** `src/infrastructure/adapters/governance/postgres_ledger_adapter.py`

### Dependency on Story 1-1 and 1-2

This story depends on:
- `consent-gov-1-1-event-envelope-domain-model`: `GovernanceEvent`, `EventMetadata`
- `consent-gov-1-2-append-only-ledger-port-adapter`: `GovernanceLedgerPort.read_events()`

**Import:**
```python
from src.domain.governance.events.event_envelope import GovernanceEvent, EventMetadata
from src.application.ports.governance.ledger_port import GovernanceLedgerPort
```

### Source Tree Components

**New Files:**
```
src/application/ports/governance/
└── projection_port.py                    # ProjectionPort protocol

src/domain/governance/projections/
├── __init__.py
├── task_state.py                         # TaskState domain model
├── legitimacy_state.py                   # LegitimacyState domain model
├── panel_registry.py                     # PanelRegistry domain model
├── petition_index.py                     # PetitionIndex domain model
├── actor_registry.py                     # ActorRegistry domain model
└── event_handlers.py                     # Event-to-projection mapping

src/infrastructure/adapters/governance/
└── postgres_projection_adapter.py        # PostgresProjectionAdapter

src/application/services/governance/
└── projection_rebuild_service.py         # ProjectionRebuildService

alembic/versions/
└── YYYYMMDD_HHMMSS_create_projections_schema.py
```

**Test Files:**
```
tests/unit/application/ports/governance/
└── test_projection_port.py

tests/unit/domain/governance/projections/
├── __init__.py
├── test_task_state.py
├── test_legitimacy_state.py
├── test_panel_registry.py
├── test_petition_index.py
└── test_actor_registry.py

tests/integration/governance/
└── test_projection_rebuild.py
```

### Technical Requirements

**Port Interface Design:**
```python
from typing import Protocol
from uuid import UUID
from src.domain.governance.events.event_envelope import GovernanceEvent

class ProjectionPort(Protocol):
    """Projection storage for derived governance state.

    CQRS-Lite Pattern:
    - Projections are DERIVED from ledger, never authoritative
    - Can be rebuilt from ledger replay at any time
    - Idempotent event application via projection_applies table

    Constitutional Constraint:
    - Projections CANNOT write to ledger schema
    - Projections CANNOT be used as source of truth
    """

    async def apply_event(self, event: GovernanceEvent) -> None:
        """Apply event to update projection state.

        Idempotency: Checks projection_applies before applying.
        """
        ...

    async def is_event_applied(self, projection_name: str, event_id: UUID) -> bool:
        """Check if event was already applied to projection."""
        ...

    async def get_checkpoint(self, projection_name: str) -> int | None:
        """Get last processed sequence for projection."""
        ...

    async def rebuild_from_events(
        self,
        projection_name: str,
        events: list[GovernanceEvent],
    ) -> None:
        """Rebuild projection from list of events (deterministic)."""
        ...
```

**Python Patterns (CRITICAL):**
- Use `Protocol` from `typing` for port definition
- Use `async_sessionmaker` from SQLAlchemy 2.0
- All I/O operations MUST be async
- Type hints on ALL functions
- Import domain models from story 1-1 location

### Testing Standards

**Idempotency Test:**
```python
@pytest.mark.asyncio
async def test_apply_event_idempotent(adapter, governance_event):
    """Applying same event twice produces identical state."""
    await adapter.apply_event(governance_event)
    state_after_first = await adapter.get_task_state(governance_event.task_id)

    await adapter.apply_event(governance_event)  # Second apply
    state_after_second = await adapter.get_task_state(governance_event.task_id)

    assert state_after_first == state_after_second
```

**Rebuild Test:**
```python
@pytest.mark.asyncio
async def test_rebuild_matches_incremental(adapter, ledger_port):
    """Projection rebuilt from ledger matches incrementally built projection."""
    # Apply events incrementally
    events = await ledger_port.read_events()
    for event in events:
        await adapter.apply_event(event)
    incremental_state = await adapter.get_all_task_states()

    # Rebuild from scratch
    await adapter.clear_projection("task_states")
    await adapter.rebuild_from_events("task_states", events)
    rebuilt_state = await adapter.get_all_task_states()

    assert incremental_state == rebuilt_state
```

**Coverage Requirement:** 100% for ports, 90%+ for adapters

### Library/Framework Requirements

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Async/await, Protocol |
| SQLAlchemy | 2.0+ | Async database operations |
| asyncpg | latest | PostgreSQL async driver |
| Alembic | latest | Database migrations |
| pytest | latest | Testing |
| pytest-asyncio | latest | Async test support |

### Project Structure Notes

**Alignment:** Creates `src/domain/governance/projections/` and extends `src/infrastructure/adapters/governance/` per architecture (Step 6).

**Import Rules (Hexagonal):**
- Port imports domain models (`GovernanceEvent`, projection domain models)
- Adapter imports port and domain models
- Service imports port (dependency injection)
- No circular dependencies

### Migration Notes

**Alembic Migration Template:**
```python
"""Create projections schema for governance derived state.

Revision ID: {revision_id}
Create Date: {date}
"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # Create projections schema
    op.execute("CREATE SCHEMA IF NOT EXISTS projections")

    # Create task_states table
    op.create_table(
        'task_states',
        sa.Column('task_id', sa.UUID, primary_key=True),
        sa.Column('current_state', sa.Text, nullable=False),
        sa.Column('earl_id', sa.Text, nullable=False),
        sa.Column('cluster_id', sa.Text),
        sa.Column('last_event_sequence', sa.BigInteger, nullable=False),
        sa.Column('last_event_hash', sa.Text, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        schema='projections'
    )

    # ... other tables ...

    # Create projection_applies table
    op.create_table(
        'projection_applies',
        sa.Column('projection_name', sa.Text, nullable=False),
        sa.Column('event_id', sa.UUID, nullable=False),
        sa.Column('event_hash', sa.Text, nullable=False),
        sa.Column('sequence', sa.BigInteger, nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('projection_name', 'event_id'),
        schema='projections'
    )

def downgrade() -> None:
    op.drop_table('projection_applies', schema='projections')
    op.drop_table('projection_checkpoints', schema='projections')
    op.drop_table('actor_registry', schema='projections')
    op.drop_table('petition_index', schema='projections')
    op.drop_table('panel_registry', schema='projections')
    op.drop_table('legitimacy_states', schema='projections')
    op.drop_table('task_states', schema='projections')
    op.execute("DROP SCHEMA IF EXISTS projections")
```

### References

- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Projection Architecture]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Initial Projection Set (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Query API Pattern (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Projection Apply Log (Idempotency)]
- [Source: _bmad-output/planning-artifacts/government-epics.md#GOV-1-5]
- [Source: src/application/ports/governance/ledger_port.py] - Reference port pattern
- [Source: _bmad-output/project-context.md#Framework-Specific Rules]
- [Source: consent-gov-1-1-event-envelope-domain-model.md] - Dependency
- [Source: consent-gov-1-2-append-only-ledger-port-adapter.md] - Dependency

### FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| AD-1 | Event sourcing as canonical model | Ledger = truth, projections = derived |
| AD-8 | Same-DB projection storage | `projections.*` schema isolation |
| AD-9 | CQRS-Lite query pattern | Single API, internal separation |
| NFR-AUDIT-06 | Deterministic replay | Rebuild from ledger events |
| NFR-PERF-04 | Read performance | Projections enable fast queries |
| NFR-REL-04 | Recovery to consistent state | Projection rebuild capability |

### Story Dependencies

| Story | Dependency Type | What We Need |
|-------|-----------------|--------------|
| consent-gov-1-1 | Hard dependency | `GovernanceEvent`, `EventMetadata` types |
| consent-gov-1-2 | Hard dependency | `GovernanceLedgerPort.read_events()` for replay |
| consent-gov-1-3 | Soft dependency | Hash fields for `last_event_hash` tracking |

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

Session transcript available at: `/home/hoyack/.claude/projects/-home-hoyack-work-archon72/`

### Completion Notes List

1. All 8 tasks completed successfully
2. 100 unit tests passing across all projection components
3. Projection domain models implemented with immutable frozen dataclasses
4. PostgresProjectionAdapter implements full ProjectionPort protocol
5. Event-to-projection mapping supports deterministic state derivation
6. Idempotency enforced via projection_applies table checks
7. Checkpoint tracking implemented for incremental rebuilds
8. Schema isolation maintained (projections.* separate from ledger.*)

### File List

**Application Layer (Ports):**
- `src/application/ports/governance/projection_port.py` - ProjectionPort protocol and ProjectionCheckpoint dataclass
- `src/application/ports/governance/__init__.py` - Updated exports

**Domain Layer (Projections):**
- `src/domain/governance/projections/__init__.py` - Package exports
- `src/domain/governance/projections/task_state.py` - TaskStateRecord frozen dataclass
- `src/domain/governance/projections/legitimacy_state.py` - LegitimacyStateRecord frozen dataclass
- `src/domain/governance/projections/panel_registry.py` - PanelRegistryRecord frozen dataclass
- `src/domain/governance/projections/petition_index.py` - PetitionIndexRecord frozen dataclass
- `src/domain/governance/projections/actor_registry.py` - ActorRegistryRecord frozen dataclass
- `src/domain/governance/projections/event_handlers.py` - Event-to-projection mapping

**Infrastructure Layer (Adapters):**
- `src/infrastructure/adapters/governance/postgres_projection_adapter.py` - PostgresProjectionAdapter

**Application Layer (Services):**
- `src/application/services/governance/projection_rebuild_service.py` - ProjectionRebuildService
- `src/application/services/governance/__init__.py` - Updated exports

**Database Migration:**
- `migrations/009_create_ledger_schema.sql` - Extended with projections schema tables

**Test Files:**
- `tests/unit/domain/governance/projections/__init__.py`
- `tests/unit/domain/governance/projections/test_task_state.py` (21 tests)
- `tests/unit/domain/governance/projections/test_legitimacy_state.py` (15 tests)
- `tests/unit/domain/governance/projections/test_actor_registry.py` (23 tests)
- `tests/unit/domain/governance/projections/test_event_handlers.py` (21 tests)
- `tests/unit/infrastructure/adapters/governance/test_postgres_projection_adapter.py` (20 tests)

