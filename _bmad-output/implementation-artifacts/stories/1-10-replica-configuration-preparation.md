# Story 1.10: Replica Configuration Preparation (FR8, FR94-FR95)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **system operator**,
I want the schema ready for 3 geographic replicas,
So that replica distribution can be enabled in deployment.

## Acceptance Criteria

### AC1: Schema Replication Compatibility
**Given** the events table schema
**When** I examine it
**Then** it contains no features that prevent logical replication
**And** primary key and sequence are suitable for replica synchronization

### AC2: Read/Write Path Separation
**Given** the application architecture
**When** I examine read vs write paths
**Then** writes go to the primary (single writer)
**And** reads can be routed to replicas (eventual consistency acceptable for reads)

### AC3: Event Replicator Port Interface
**Given** the event propagation interface
**When** I examine `src/application/ports/event_replicator.py`
**Then** it defines: `propagate_event(event_id) -> ReplicationReceipt`
**And** it defines: `verify_replicas() -> VerificationResult`
**And** verification checks: head hash match, signature validity, schema version

## Tasks / Subtasks

- [x] Task 1: Schema Replication Compatibility Audit (AC: 1)
  - [x] 1.1 Review events table schema from `migrations/001_create_events_table.sql`
  - [x] 1.2 Document that UUID primary key is replication-safe
  - [x] 1.3 Document that BIGSERIAL sequence works with logical replication
  - [x] 1.4 Verify no features that prevent replication (no UNLOGGED, no IDENTITY issues)
  - [x] 1.5 Create `docs/spikes/1-10-replica-readiness-report.md` with schema assessment

- [x] Task 2: Create EventReplicatorPort Interface (AC: 3)
  - [x] 2.1 Create `src/application/ports/event_replicator.py`
  - [x] 2.2 Define `ReplicationReceipt` dataclass with: `event_id`, `replica_ids`, `status`, `timestamp`
  - [x] 2.3 Define `VerificationResult` dataclass with: `head_hash_match`, `signature_valid`, `schema_version_match`, `errors`
  - [x] 2.4 Define `EventReplicatorPort` protocol with `propagate_event()` and `verify_replicas()` methods
  - [x] 2.5 Add async abstract method signatures following `HaltChecker` pattern

- [x] Task 3: Create EventReplicatorStub Implementation (AC: 3)
  - [x] 3.1 Create `src/infrastructure/stubs/event_replicator_stub.py`
  - [x] 3.2 Implement `EventReplicatorStub` that always returns success (no replicas configured)
  - [x] 3.3 Add structlog logging for traceability
  - [x] 3.4 Follow watermark pattern from `DevHSM` for dev mode indication

- [x] Task 4: Update Ports Module Exports (AC: 3)
  - [x] 4.1 Update `src/application/ports/__init__.py` to export new types
  - [x] 4.2 Add docstring entry for EventReplicatorPort

- [x] Task 5: Document Read/Write Path Separation (AC: 2)
  - [x] 5.1 Add section to spike report documenting single-writer architecture
  - [x] 5.2 Document that Writer goes to primary, Observers can read from replicas
  - [x] 5.3 Document eventual consistency is acceptable for Observer reads (Epic 4)

- [x] Task 6: Unit Tests for Port and Stub (AC: 3)
  - [x] 6.1 Create `tests/unit/application/test_event_replicator_port.py`
  - [x] 6.2 Test ReplicationReceipt and VerificationResult dataclass creation
  - [x] 6.3 Create `tests/unit/infrastructure/test_event_replicator_stub.py`
  - [x] 6.4 Test stub returns success receipts
  - [x] 6.5 Test stub verify_replicas returns positive result

## Dev Notes

### Critical Architecture Context

**FR8: 3 Geographic Replicas Ready**
From the PRD, the system must be deployable with 3 geographic replicas for resilience. This story prepares the schema and interfaces but does NOT implement actual replication (that's deployment-phase work).

**FR94-FR95: Propagation Primitives**
- FR94: Event propagation interface (`propagate_event`)
- FR95: Replica verification interface (`verify_replicas`)

**Single-Writer Architecture (ADR-1)**
From `architecture.md`:
> "Single canonical Writer (constitutionally required). Read-only replicas via managed Postgres replication (Supabase/underlying PG). Failover is ceremony-based: watchdog detection + human approval + witnessed promotion."

**Key Points:**
- This is a PREPARATION story - no actual replication is implemented
- The port interface and stub allow Epic 1 code to work without replica infrastructure
- Actual replication will use Supabase's built-in Postgres logical replication
- The stub enables testing and development without replica infrastructure

### Previous Story Intelligence (Story 1-9)

From the Observer Query Schema Design Spike (Story 1-9):
1. **Schema is replication-ready** - GO decision confirmed no blocking features
2. **Indexes work with replication** - All indexes are standard B-tree, no issues
3. **UUID + BIGSERIAL combination** - Works well with logical replication
4. **No schema changes needed** - The events table is already optimized

**Key Learning:** The schema audit in 1-9 already validated that the events table has no replication-blocking features. This story focuses on creating the interface layer.

### Port Pattern to Follow

Use the `HaltChecker` port pattern from `src/application/ports/halt_checker.py`:
- Abstract base class with `@abstractmethod` decorators
- Async methods for consistency with the codebase
- Clear docstrings explaining Epic 1 stub vs future implementation
- Constitutional context in module docstring

### Stub Pattern to Follow

Reference `src/infrastructure/adapters/security/hsm_dev.py` for the stub pattern:
- Use `structlog` for logging
- Include dev mode watermark if applicable
- Return success values appropriate for development
- Clear comments about production implementation

### Schema Compatibility Checklist

The events table from `migrations/001_create_events_table.sql` should be verified:
- [x] Uses UUID primary key (replication-safe)
- [x] Uses BIGSERIAL for sequence (works with logical replication)
- [x] No UNLOGGED tables
- [x] No GENERATED columns with issues
- [x] Standard indexes (B-tree)
- [x] No exclusive locks in triggers
- [x] REVOKE TRUNCATE doesn't affect replication

### Read/Write Separation Notes

**Write Path (Primary only):**
- EventWriterService → PostgreSQL primary
- Single Writer per ADR-1
- All mutations go through primary

**Read Path (Can use replicas):**
- Observer queries (Epic 4) → Any replica
- Eventual consistency acceptable for reads
- Supabase handles routing via connection pooling

### Project Structure Notes

**Files to Create:**
```
src/
└── application/
    └── ports/
        └── event_replicator.py      # Port interface
src/
└── infrastructure/
    └── stubs/
        └── event_replicator_stub.py # Stub implementation
docs/
└── spikes/
    └── 1-10-replica-readiness-report.md  # Assessment report
tests/
└── unit/
    ├── application/
    │   └── test_event_replicator_port.py
    └── infrastructure/
        └── test_event_replicator_stub.py
```

**Alignment with Project Structure:**
- Ports in `src/application/ports/` (hexagonal architecture)
- Stubs in `src/infrastructure/stubs/` (development-only adapters)
- Spikes in `docs/spikes/` (existing pattern from 1-7, 1-9)

### Testing Standards

Per `project-context.md`:
- ALL test files use `pytest.mark.asyncio`
- Use `async def test_*` for async tests
- Unit tests in `tests/unit/{module}/test_{name}.py`
- 80% minimum coverage (100% for security module)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.10: Replica Configuration Preparation]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-1: Supabase]
- [Source: migrations/001_create_events_table.sql]
- [Source: src/application/ports/halt_checker.py] - Port pattern reference
- [Source: docs/spikes/1-9-observer-query-schema-spike-report.md] - Schema GO decision
- [Supabase Replication Docs](https://supabase.com/docs/guides/platform/read-replicas)
- [PostgreSQL Logical Replication](https://www.postgresql.org/docs/current/logical-replication.html)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - All tests passed on first run

### Completion Notes List

1. **Schema Replication Audit Complete:** Created comprehensive spike report documenting events table compatibility with PostgreSQL logical replication. UUID primary key and BIGSERIAL sequence are ideal for replica synchronization.

2. **EventReplicatorPort Interface Created:** Defined abstract port with `propagate_event()` and `verify_replicas()` methods following HaltChecker pattern. Includes `ReplicationReceipt`, `VerificationResult` dataclasses and `ReplicationStatus` enum.

3. **EventReplicatorStub Implemented:** Stub returns NOT_CONFIGURED status (no replicas) or CONFIRMED (with simulated replicas). Includes test helpers for failure mode and replica ID configuration.

4. **Ports and Stubs Exports Updated:** Added all new types to `src/application/ports/__init__.py` and `src/infrastructure/stubs/__init__.py`.

5. **Read/Write Path Documentation:** Section 2 of spike report comprehensively documents single-writer architecture (ADR-1) and read path separation for Observer API (Epic 4).

6. **Unit Tests Complete:** 26 tests covering all dataclass creation, is_valid property, stub behaviors (no replicas, with replicas, failure mode), and test helpers. All tests pass.

### File List

**Created:**
- `docs/spikes/1-10-replica-readiness-report.md` - Comprehensive schema assessment report
- `src/application/ports/event_replicator.py` - Port interface with dataclasses and enum
- `src/infrastructure/stubs/event_replicator_stub.py` - Stub implementation
- `tests/unit/application/__init__.py` - Test package init
- `tests/unit/application/test_event_replicator_port.py` - 13 tests for port types
- `tests/unit/infrastructure/test_event_replicator_stub.py` - 13 tests for stub

**Modified:**
- `src/application/ports/__init__.py` - Added EventReplicatorPort exports
- `src/infrastructure/stubs/__init__.py` - Added EventReplicatorStub export

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-06 | Story created with comprehensive context from Epic 1 analysis | SM Agent (Claude Opus 4.5) |
| 2026-01-06 | All tasks completed: schema audit, port interface, stub, docs, tests (26 passed) | Dev Agent (Claude Opus 4.5) |
| 2026-01-06 | Code review complete: Fixed mutable list issue (list→tuple) for true immutability in frozen dataclasses | Code Review (Claude Opus 4.5) |
