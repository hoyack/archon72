# Story consent-gov-1.2: Append-Only Ledger Port & Adapter

Status: done

---

## Story

As a **governance system**,
I want **an append-only ledger interface**,
so that **events can be persisted without modification or deletion, ensuring constitutional integrity and enabling deterministic replay**.

---

## Acceptance Criteria

1. **AC1:** `GovernanceLedgerPort` interface exists with `append_event()` and `read_events()` methods
2. **AC2:** No `update`, `delete`, or `modify` methods exist on the interface (by design, not omission)
3. **AC3:** PostgreSQL adapter implements append with global monotonic sequence number
4. **AC4:** Global monotonic sequence via `ledger.governance_events.sequence` (bigint GENERATED ALWAYS AS IDENTITY)
5. **AC5:** Schema isolation: `ledger.*` tables separate from existing `public.*` and future `projections.*`
6. **AC6:** Ledger survives service restart without data loss (PostgreSQL ACID guarantees)
7. **AC7:** Unit tests verify no mutation paths exist and adapter correctly persists events
8. **AC8:** Adapter accepts only `GovernanceEvent` from story 1-1 (type enforcement)

---

## Tasks / Subtasks

- [x] **Task 1: Create governance ports module structure** (AC: All)
  - [x] Create `src/application/ports/governance/__init__.py`
  - [x] Create `src/application/ports/governance/ledger_port.py`

- [x] **Task 2: Implement GovernanceLedgerPort interface** (AC: 1, 2, 8)
  - [x] Define Protocol with `append_event()` accepting `GovernanceEvent`
  - [x] Define `read_events()` method with filtering options
  - [x] Define `get_latest_event()` method
  - [x] Define `get_max_sequence()` method
  - [x] Add explicit docstrings stating NO update/delete methods by design
  - [x] Add type hints requiring `GovernanceEvent` (not generic Event)

- [x] **Task 3: Create database migration for ledger schema** (AC: 4, 5)
  - [x] Create SQL migration for `ledger` schema (migrations/009_create_ledger_schema.sql)
  - [x] Create `ledger.governance_events` table with sequence IDENTITY
  - [x] Add indexes: `idx_governance_events_event_id`, `idx_governance_events_event_type`, `idx_governance_events_branch_sequence`
  - [x] Verify schema isolation from `public.*`

- [x] **Task 4: Implement PostgresGovernanceLedgerAdapter** (AC: 3, 6, 8)
  - [x] Create `src/infrastructure/adapters/governance/__init__.py`
  - [x] Create `src/infrastructure/adapters/governance/postgres_ledger_adapter.py`
  - [x] Implement `append_event()` with sequence assignment
  - [x] Implement `read_events()` with filtering
  - [x] Implement `get_latest_event()`
  - [x] Implement `get_max_sequence()`
  - [x] Use async SQLAlchemy 2.0 patterns

- [x] **Task 5: Write comprehensive tests** (AC: 7)
  - [x] Unit tests for port interface compliance (25 tests)
  - [x] Unit tests for adapter logic with mocked DB (23 tests)
  - [x] Test that no mutation paths exist (no update/delete methods callable)
  - [x] Test type enforcement (only GovernanceEvent accepted)

---

## Documentation Checklist

- [x] Architecture docs updated (new governance ports/adapters structure) - Module docstrings document structure
- [x] Inline comments added for constitutional constraints - All methods documented
- [x] N/A - API docs (internal infrastructure)
- [x] N/A - README (internal component)

---

## Dev Notes

### Architecture Compliance (CRITICAL)

**From governance-architecture.md:**

This story implements the append-only ledger port defined in the architecture document.

**Ledger Table Schema (Locked):**
```sql
CREATE SCHEMA IF NOT EXISTS ledger;

CREATE TABLE ledger.governance_events (
  sequence    bigint GENERATED ALWAYS AS IDENTITY,
  event_id    uuid NOT NULL,
  event_type  text NOT NULL,
  branch      text NOT NULL,  -- derived from event_type.split('.')[0]
  schema_version text NOT NULL,
  timestamp   timestamptz NOT NULL,
  actor_id    text NOT NULL,
  trace_id    text NOT NULL,
  payload     jsonb NOT NULL,

  PRIMARY KEY (sequence)
);

CREATE INDEX idx_governance_events_event_id ON ledger.governance_events (event_id);
CREATE INDEX idx_governance_events_branch_sequence ON ledger.governance_events (branch, sequence);
CREATE INDEX idx_governance_events_event_type ON ledger.governance_events (event_type);
```

**Schema Isolation:**
| Schema | Purpose | Write Access |
|--------|---------|--------------|
| `ledger.*` | Append-only governance events | GovernanceLedgerAdapter only |
| `projections.*` | Derived state (future story) | Projection services |
| `public.*` | Existing system tables | Existing services |

**No Hash Fields in This Story:**
- `prev_hash` and `hash` fields are added in story consent-gov-1-3
- This story focuses on the append-only persistence mechanism
- Hash chain verification is a separate concern

### Existing Patterns to Follow

**Reference:** `src/application/ports/event_store.py`

The existing `EventStorePort` demonstrates the pattern:
- ABC with `@abstractmethod` decorators
- Clear docstrings with Constitutional Constraints
- No delete methods defined (by design)
- Type hints on all methods

**Key Difference:**
- Existing `EventStorePort` uses `Event` class
- New `GovernanceLedgerPort` uses `GovernanceEvent` class (from story 1-1)
- New port is in `src/application/ports/governance/` (separate namespace)

**Reference:** `src/infrastructure/adapters/` for adapter patterns

### Dependency on Story 1-1

This story depends on `consent-gov-1-1-event-envelope-domain-model` for:
- `GovernanceEvent` domain model
- `EventMetadata` structure
- Event type validation

**Import:**
```python
from src.domain.governance.events.event_envelope import GovernanceEvent, EventMetadata
```

### Source Tree Components

**New Files:**
```
src/application/ports/governance/
├── __init__.py
└── ledger_port.py                    # GovernanceLedgerPort protocol

src/infrastructure/adapters/governance/
├── __init__.py
└── postgres_ledger_adapter.py        # PostgresGovernanceLedgerAdapter

alembic/versions/
└── YYYYMMDD_HHMMSS_create_ledger_schema.py
```

**Test Files:**
```
tests/unit/application/ports/governance/
├── __init__.py
└── test_ledger_port.py

tests/integration/governance/
├── __init__.py
└── test_ledger_adapter.py
```

### Technical Requirements

**Port Interface Design:**
```python
from typing import Protocol
from src.domain.governance.events.event_envelope import GovernanceEvent

class GovernanceLedgerPort(Protocol):
    """Append-only ledger for governance events.

    Constitutional Constraints:
    - NO update methods - events are immutable
    - NO delete methods - events are permanent
    - Append is the ONLY write operation

    This interface deliberately omits mutation methods.
    The absence is intentional, not an oversight.
    """

    async def append_event(self, event: GovernanceEvent) -> GovernanceEvent:
        """Append event to ledger. Returns event with sequence assigned."""
        ...

    async def get_latest_event(self) -> GovernanceEvent | None:
        """Get most recent event for chaining."""
        ...

    async def get_max_sequence(self) -> int:
        """Get highest sequence number."""
        ...

    async def read_events(
        self,
        start_sequence: int | None = None,
        end_sequence: int | None = None,
        branch: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[GovernanceEvent]:
        """Read events with optional filters."""
        ...
```

**Adapter Implementation Pattern:**
```python
class PostgresGovernanceLedgerAdapter:
    """PostgreSQL implementation of GovernanceLedgerPort.

    Uses ledger.governance_events table with:
    - sequence: bigint GENERATED ALWAYS AS IDENTITY
    - ACID guarantees for persistence
    - No UPDATE/DELETE capabilities (table design)
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def append_event(self, event: GovernanceEvent) -> GovernanceEvent:
        async with self._session_factory() as session:
            # Insert event, get assigned sequence
            ...
```

**Python Patterns (CRITICAL):**
- Use `Protocol` from `typing` for port definition
- Use `async_sessionmaker` from SQLAlchemy 2.0
- All I/O operations MUST be async
- Type hints on ALL functions
- Import `GovernanceEvent` from story 1-1 location

### Testing Standards

**Port Compliance Test:**
```python
def test_port_has_no_update_method():
    """Verify no update method exists on GovernanceLedgerPort."""
    assert not hasattr(GovernanceLedgerPort, 'update_event')

def test_port_has_no_delete_method():
    """Verify no delete method exists on GovernanceLedgerPort."""
    assert not hasattr(GovernanceLedgerPort, 'delete_event')
```

**Adapter Integration Test:**
```python
@pytest.mark.asyncio
async def test_append_event_assigns_sequence(adapter, governance_event):
    """Appended event gets monotonic sequence assigned."""
    result = await adapter.append_event(governance_event)
    assert result.sequence > 0

@pytest.mark.asyncio
async def test_append_events_have_increasing_sequence(adapter):
    """Multiple appends produce strictly increasing sequences."""
    event1 = await adapter.append_event(make_event())
    event2 = await adapter.append_event(make_event())
    assert event2.sequence > event1.sequence
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

**Alignment:** Creates new `src/application/ports/governance/` and `src/infrastructure/adapters/governance/` per architecture (Step 6).

**Import Rules (Hexagonal):**
- Port imports domain models (`GovernanceEvent`)
- Adapter imports port and domain models
- No circular dependencies

### Migration Notes

**Alembic Migration Template:**
```python
"""Create ledger schema for governance events.

Revision ID: {revision_id}
Create Date: {date}
"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # Create ledger schema
    op.execute("CREATE SCHEMA IF NOT EXISTS ledger")

    # Create governance_events table
    op.create_table(
        'governance_events',
        sa.Column('sequence', sa.BigInteger, primary_key=True,
                  server_default=sa.text("nextval('ledger.governance_events_sequence_seq')")),
        sa.Column('event_id', sa.UUID, nullable=False),
        sa.Column('event_type', sa.Text, nullable=False),
        sa.Column('branch', sa.Text, nullable=False),
        sa.Column('schema_version', sa.Text, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor_id', sa.Text, nullable=False),
        sa.Column('trace_id', sa.Text, nullable=False),
        sa.Column('payload', sa.dialects.postgresql.JSONB, nullable=False),
        schema='ledger'
    )

    # Create indexes
    op.create_index('idx_governance_events_event_id', 'governance_events',
                    ['event_id'], schema='ledger')
    op.create_index('idx_governance_events_branch_sequence', 'governance_events',
                    ['branch', 'sequence'], schema='ledger')

def downgrade() -> None:
    op.drop_table('governance_events', schema='ledger')
    op.execute("DROP SCHEMA IF EXISTS ledger")
```

### References

- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Storage Strategy (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Ledger Table Schema (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Port Definitions Required]
- [Source: _bmad-output/planning-artifacts/government-epics.md#GOV-1-2]
- [Source: src/application/ports/event_store.py] - Reference port pattern
- [Source: _bmad-output/project-context.md#Framework-Specific Rules]
- [Source: consent-gov-1-1-event-envelope-domain-model.md] - Dependency

### FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| AD-1 | Event sourcing as canonical model | Append-only ledger |
| AD-8 | Same DB, schema isolation | `ledger.*` schema |
| AD-11 | Global monotonic sequence | sequence IDENTITY column |
| NFR-CONST-01 | Append-only enforcement | No update/delete methods |
| NFR-REL-02 | Persistence survives restart | PostgreSQL ACID |
| NFR-ATOMIC-01 | Atomic operations | Single INSERT per append |

### Story Dependencies

| Story | Dependency Type | What We Need |
|-------|-----------------|--------------|
| consent-gov-1-1 | Hard dependency | `GovernanceEvent`, `EventMetadata` types |

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - clean implementation with all tests passing on first run.

### Completion Notes List

- Created new `src/application/ports/governance/` module for governance ledger port
- Implemented `GovernanceLedgerPort` protocol with append_event(), read_events(), get_latest_event(), get_max_sequence(), get_event_by_sequence(), get_event_by_id(), count_events() methods
- Created `LedgerReadOptions` frozen dataclass for filtering with start_sequence, end_sequence, branch, event_type, limit, offset
- Created `PersistedGovernanceEvent` wrapper to add ledger-assigned sequence to GovernanceEvent
- Created SQL migration `migrations/009_create_ledger_schema.sql` with:
  - `ledger` schema for isolation from `public.*`
  - `ledger.governance_events` table with GENERATED ALWAYS AS IDENTITY sequence
  - Append-only triggers preventing UPDATE/DELETE (NFR-CONST-01)
  - Branch derivation trigger ensuring branch is derived at write-time (AD-15)
  - Indexes for event_id, branch+sequence, event_type, timestamp, actor_id
- Implemented `PostgresGovernanceLedgerAdapter` with async SQLAlchemy 2.0 patterns
- Type enforcement: append_event() raises TypeError for non-GovernanceEvent (AC8)
- **48 unit tests passing** (25 port + 23 adapter) covering all acceptance criteria
- NO update/delete methods exist on port or adapter (by design per NFR-CONST-01)

### File List

**Created:**
- `src/application/ports/governance/__init__.py`
- `src/application/ports/governance/ledger_port.py` (GovernanceLedgerPort, LedgerReadOptions, PersistedGovernanceEvent)
- `src/infrastructure/adapters/governance/__init__.py`
- `src/infrastructure/adapters/governance/postgres_ledger_adapter.py` (PostgresGovernanceLedgerAdapter)
- `migrations/009_create_ledger_schema.sql` (ledger schema, governance_events table, triggers)
- `tests/unit/application/ports/governance/__init__.py`
- `tests/unit/application/ports/governance/test_ledger_port.py` (25 tests)
- `tests/unit/infrastructure/adapters/governance/__init__.py`
- `tests/unit/infrastructure/adapters/governance/test_postgres_ledger_adapter.py` (23 tests)

