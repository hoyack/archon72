# Story 3.3: Dual-Channel Halt Transport (ADR-3)

Status: done

## Story

As a **system operator**,
I want halt signals to propagate via dual channels (Redis + DB),
so that halt cannot be missed even if one channel fails.

## Acceptance Criteria

1. **AC1: Dual-Channel Halt Signal Writing**
   - **Given** a halt is triggered (via `HaltTriggerService`)
   - **When** the halt signal is sent
   - **Then** it is written to Redis Streams for fast propagation
   - **And** it is written to DB halt flag for durability
   - **And** both writes complete before halt is considered "sent"

2. **AC2: Dual-Channel Halt State Reading**
   - **Given** a component checking halt state
   - **When** it queries halt status
   - **Then** it checks both Redis stream consumer state AND DB halt flag
   - **And** if EITHER indicates halt, the component halts

3. **AC3: DB as Source of Truth During Redis Failure**
   - **Given** Redis is down but DB is available
   - **When** halt state is checked
   - **Then** DB halt flag is the source of truth
   - **And** component halts if DB flag is set

4. **AC4: Halt Channel Conflict Resolution (SR-5)**
   - **Given** halt channel conflict (Redis says halt, DB says not halted)
   - **When** conflict is detected
   - **Then** explicit resolution logic runs
   - **And** DB is canonical; Redis state is corrected
   - **And** conflict event is logged

5. **AC5: Redis Confirmation Against DB (RT-2)**
   - **Given** a halt is triggered via Redis
   - **When** halt from Redis is detected
   - **Then** halt must be confirmed against DB within 5 seconds
   - **And** if DB does not confirm within 5 seconds, conflict resolution triggers

## Tasks / Subtasks

- [x] Task 1: Create DualChannelHaltTransport port interface (AC: #1, #2)
  - [x] 1.1: Create `src/application/ports/dual_channel_halt.py` with `DualChannelHaltTransport` ABC
  - [x] 1.2: Define abstract methods: `async def write_halt(reason: str, crisis_event_id: UUID) -> None`
  - [x] 1.3: Define abstract methods: `async def is_halted() -> bool`, `async def get_halt_reason() -> Optional[str]`
  - [x] 1.4: Define abstract methods: `async def check_channels_consistent() -> bool`, `async def resolve_conflict() -> None`
  - [x] 1.5: Define abstract property: `confirmation_timeout_seconds: float` (default 5.0)
  - [x] 1.6: Export from `src/application/ports/__init__.py`

- [x] Task 2: Create halt flag database schema and repository (AC: #1, #3)
  - [x] 2.1: Create migration `migrations/006_halt_state_table.sql`
  - [x] 2.2: Table: `halt_state` with columns: `id`, `is_halted`, `reason`, `crisis_event_id`, `halted_at`, `updated_at`
  - [x] 2.3: Create `src/infrastructure/adapters/persistence/halt_flag_repository.py`
  - [x] 2.4: Implement `set_halt_flag(halted: bool, reason: str, crisis_event_id: UUID)` method
  - [x] 2.5: Implement `get_halt_flag() -> HaltFlagState` method
  - [x] 2.6: Write unit tests in `tests/unit/infrastructure/test_halt_flag_repository.py`

- [x] Task 3: Create Redis Streams halt publisher (AC: #1)
  - [x] 3.1: Create `src/infrastructure/adapters/messaging/halt_stream_publisher.py`
  - [x] 3.2: Use Redis Streams with `XADD` to publish halt signals
  - [x] 3.3: Stream name: `halt:signals` (configurable)
  - [x] 3.4: Message fields: `reason`, `crisis_event_id`, `timestamp`, `source_service`
  - [x] 3.5: Implement `publish_halt(reason: str, crisis_event_id: UUID) -> str` (returns message ID)
  - [x] 3.6: Write unit tests in `tests/unit/infrastructure/test_halt_stream_publisher.py`

- [x] Task 4: Create Redis Streams halt consumer (AC: #2)
  - [x] 4.1: Create `src/infrastructure/adapters/messaging/halt_stream_consumer.py`
  - [x] 4.2: Use consumer group for reliable delivery: `halt:consumers`
  - [x] 4.3: Implement `async def check_redis_halt() -> bool` (check stream for halt messages)
  - [x] 4.4: Implement `async def start_listening() -> None` (background stream listener)
  - [x] 4.5: Implement `async def stop_listening() -> None` (graceful shutdown)
  - [x] 4.6: Use `XREADGROUP` with blocking read and `XACK` for acknowledgment
  - [x] 4.7: Write unit tests in `tests/unit/infrastructure/test_halt_stream_consumer.py`

- [x] Task 5: Create DualChannelHaltTransportImpl adapter (AC: #1, #2, #3, #4, #5)
  - [x] 5.1: Create `src/infrastructure/adapters/messaging/dual_channel_halt_impl.py`
  - [x] 5.2: Inject `HaltFlagRepository` for DB channel
  - [x] 5.3: Inject `HaltStreamPublisher` and `HaltStreamConsumer` for Redis channel
  - [x] 5.4: Implement `write_halt()`: write to BOTH channels, fail if either fails
  - [x] 5.5: Implement `is_halted()`: return `True` if EITHER channel indicates halt
  - [x] 5.6: Implement `check_channels_consistent()`: compare Redis and DB states
  - [x] 5.7: Implement `resolve_conflict()`: DB is canonical, correct Redis
  - [x] 5.8: Add 5-second timeout for Redis-to-DB confirmation (RT-2)
  - [x] 5.9: Log all conflict events with structured logging
  - [x] 5.10: Write unit tests in `tests/unit/infrastructure/test_dual_channel_halt.py`

- [x] Task 6: Create DualChannelHaltTransportStub for testing (AC: #1, #2)
  - [x] 6.1: Create `src/infrastructure/stubs/dual_channel_halt_stub.py`
  - [x] 6.2: Implement in-memory dual-channel simulation
  - [x] 6.3: Add `set_redis_halt()` and `set_db_halt()` for testing conflicts
  - [x] 6.4: Add `set_redis_failure()` for testing fallback to DB
  - [x] 6.5: Add `get_trigger_count()` and `get_crisis_event_id()` for test verification
  - [x] 6.6: Write unit tests in `tests/unit/infrastructure/test_dual_channel_halt_stub.py`

- [x] Task 7: Update HaltTriggerService to use DualChannelHaltTransport (AC: #1)
  - [x] 7.1: Modify `src/application/services/halt_trigger_service.py`
  - [x] 7.2: Add `DualChannelHaltTransport` as optional dependency (preferred over HaltTrigger)
  - [x] 7.3: Add `_write_halt()` method to dispatch to appropriate transport
  - [x] 7.4: Write unit tests in `tests/unit/application/test_halt_trigger_service.py`

- [x] Task 8: Update HaltChecker implementations to use DualChannelHaltTransport (AC: #2, #3)
  - [x] 8.1: Modify existing `HaltCheckerStub` to delegate to `DualChannelHaltTransport` when available
  - [x] 8.2: Add three-mode priority: DualChannel > SharedState > ForceHalted
  - [x] 8.3: Ensure backward compatibility with existing tests (21 tests pass)

- [x] Task 9: Integration tests (AC: #1, #2, #3, #4, #5)
  - [x] 9.1: Create `tests/integration/test_dual_channel_halt_integration.py`
  - [x] 9.2: Test: Halt written to both Redis and DB (TestFullHaltFlow)
  - [x] 9.3: Test: Either channel halt triggers component halt (TestEitherChannelHalt)
  - [x] 9.4: Test: DB fallback when Redis unavailable (TestRedisFallback)
  - [x] 9.5: Test: Conflict detection and resolution (TestChannelConflict)
  - [x] 9.6: Test: 5-second confirmation timeout constant (TestConfirmationTimeout)
  - [x] 9.7: Test: End-to-end flow with multiple services (TestEndToEndFlow)

## Dev Notes

### Constitutional Requirements

**ADR-3 Coverage:**
- Dual-channel halt: Redis Streams for speed + DB halt flag for safety
- Halt is **sticky** once set (clearing requires witnessed ceremony - Story 3.4)
- Every operation boundary MUST check halt
- If EITHER channel indicates halt → component halts
- DB is canonical when channels disagree

**FR-related:**
- FR17: Single fork triggers halt (Story 3.2 dependency)
- FR18-FR22: Halt propagation and recovery (this story + 3.4-3.6)

**Constitutional Truths to Honor:**
- **CT-11 (Silent failure destroys legitimacy):** Halt channel failures MUST be logged
- **CT-12 (Witnessing creates accountability):** Halt writes must include crisis_event_id for attribution
- **CT-13 (Integrity outranks availability):** Dual-channel ensures halt cannot be missed

**Red Team Hardening (RT-2):**
- Halt from Redis must be confirmed against DB within 5 seconds
- Phantom halts detectable via channel mismatch analysis
- Conflict resolution is logged as an event

**Debate-Driven Constraint (DEB-002):**
- Halt state MUST include user-facing notification with human escalation contact

**Developer Golden Rules:**
1. **HALT FIRST** - Check dual-channel halt before every operation
2. **DB IS CANONICAL** - When Redis and DB disagree, trust DB
3. **LOG CONFLICTS** - Every channel mismatch must be logged
4. **FAIL LOUD** - Never swallow halt check errors

### Architecture Compliance

**ADR-3 (Partition Behavior + Halt Durability):**
- This story implements the TRANSPORT mechanism
- Story 3.2 (Single-Conflict Halt Trigger) provides the trigger
- Story 3.4 (Sticky Halt Semantics) will prevent accidental clearing
- Story 3.5 (Read-Only Access During Halt) will enforce halt behavior

**Hexagonal Architecture:**
- `src/application/ports/dual_channel_halt.py` - Port interface
- `src/infrastructure/adapters/persistence/halt_flag_repository.py` - DB adapter
- `src/infrastructure/adapters/messaging/halt_stream_publisher.py` - Redis publisher
- `src/infrastructure/adapters/messaging/halt_stream_consumer.py` - Redis consumer
- `src/infrastructure/adapters/messaging/dual_channel_halt.py` - Combined adapter
- `src/infrastructure/stubs/dual_channel_halt_stub.py` - Stub for testing

**Import Rules:**
- Domain layer: NO infrastructure imports
- Application layer: Import from domain only (ports are in application)
- Infrastructure: Implements application ports

**File Paths from ADR-003:**
- Primary: `src/infrastructure/adapters/messaging/halt_transport.py` (or `dual_channel_halt.py`)
- Domain errors: `src/domain/errors/halt.py` (already exists as `src/domain/errors/writer.py`)

### Technical Implementation Notes

**Redis Streams Pattern:**
```python
# Publisher (halt_stream_publisher.py)
async def publish_halt(self, reason: str, crisis_event_id: UUID) -> str:
    """Publish halt signal to Redis Stream."""
    message_id = await self._redis.xadd(
        self._stream_name,
        {
            "reason": reason,
            "crisis_event_id": str(crisis_event_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_service": self._service_id,
        },
    )
    log.info("halt_signal_published", message_id=message_id, stream=self._stream_name)
    return message_id
```

**Consumer Group Pattern:**
```python
# Consumer (halt_stream_consumer.py)
async def start_listening(self) -> None:
    """Start listening for halt signals with consumer group."""
    # Create consumer group if not exists
    try:
        await self._redis.xgroup_create(
            self._stream_name,
            self._consumer_group,
            id="0",
            mkstream=True,
        )
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

    while self._running:
        messages = await self._redis.xreadgroup(
            self._consumer_group,
            self._consumer_name,
            {self._stream_name: ">"},  # Read new messages only
            count=1,
            block=1000,  # 1 second block
        )
        for stream, stream_messages in messages:
            for message_id, fields in stream_messages:
                await self._process_halt_message(fields)
                await self._redis.xack(self._stream_name, self._consumer_group, message_id)
```

**Dual-Channel Check Pattern:**
```python
# dual_channel_halt.py
async def is_halted(self) -> bool:
    """Check if system is halted via either channel."""
    # Check both channels concurrently
    redis_halted, db_halted = await asyncio.gather(
        self._check_redis_halt(),
        self._check_db_halt(),
        return_exceptions=True,
    )

    # Handle Redis failure gracefully
    if isinstance(redis_halted, Exception):
        log.warning("redis_halt_check_failed", error=str(redis_halted))
        redis_halted = False  # Fall back to DB only

    # If EITHER indicates halt, we're halted (AC2)
    halted = redis_halted or db_halted

    # Detect and resolve conflicts (AC4, AC5)
    if redis_halted and not db_halted:
        await self._handle_conflict("redis_halt_db_not_halted")

    return halted
```

**Conflict Resolution Pattern:**
```python
async def resolve_conflict(self) -> None:
    """Resolve channel conflict - DB is canonical."""
    db_state = await self._halt_flag_repo.get_halt_flag()

    if db_state.is_halted:
        # DB says halt - ensure Redis matches
        await self._publisher.publish_halt(
            reason=db_state.reason,
            crisis_event_id=db_state.crisis_event_id,
        )
        log.info("conflict_resolved_halt_propagated", source="db", target="redis")
    else:
        # DB says not halted - this is SUSPICIOUS
        # Redis had a halt but DB doesn't - possible phantom halt or race
        log.warning(
            "conflict_detected_phantom_halt",
            redis_halted=True,
            db_halted=False,
            action="logged_for_investigation",
        )
        # Do NOT clear Redis halt - log for human investigation
        # This prevents attackers from clearing halts via DB manipulation
```

### Library/Framework Requirements

**Required Libraries (already in project):**
- `redis.asyncio` - Async Redis client with Streams support
- `asyncio` - Async coordination
- `structlog` - Structured logging
- `dataclasses` - Data structures
- `datetime` with `timezone.utc` (Python 3.10+ compatible)
- `uuid` - Event and message IDs
- `sqlalchemy` 2.0+ - Async DB operations

**Redis Streams Best Practices (2025):**
- Use consumer groups for reliable delivery
- Implement `XACK` for explicit acknowledgment
- Use `XCLAIM` for handling stuck messages (future enhancement)
- Wrap in Docker with health checks
- Add exponential back-off on transient failures

**Patterns to Follow:**
- Use `@dataclass(frozen=True)` for state objects
- Use `Optional[T]` for nullable fields
- Use `UUID` from uuid module
- Use `timezone.utc` not `datetime.UTC` (Python 3.10 compat)

### File Structure

```
src/
├── application/
│   └── ports/
│       ├── dual_channel_halt.py      # NEW: DualChannelHaltTransport ABC
│       └── __init__.py               # UPDATE: export new port
├── infrastructure/
│   ├── adapters/
│   │   ├── persistence/
│   │   │   └── halt_flag_repository.py  # NEW: DB halt flag repo
│   │   └── messaging/
│   │       ├── halt_stream_publisher.py # NEW: Redis Streams publisher
│   │       ├── halt_stream_consumer.py  # NEW: Redis Streams consumer
│   │       └── dual_channel_halt.py     # NEW: Combined transport
│   └── stubs/
│       └── dual_channel_halt_stub.py    # NEW: Testing stub

migrations/
└── versions/
    └── XXX_create_halt_flag_table.py    # NEW: DB migration

tests/
├── unit/
│   └── infrastructure/
│       ├── test_halt_flag_repository.py      # NEW
│       ├── test_halt_stream_publisher.py     # NEW
│       ├── test_halt_stream_consumer.py      # NEW
│       ├── test_dual_channel_halt.py         # NEW
│       └── test_dual_channel_halt_stub.py    # NEW
└── integration/
    └── test_dual_channel_halt_integration.py # NEW
```

### Testing Standards

**Unit Tests:**
- Test Redis Streams publish with mock redis client
- Test consumer group creation and message acknowledgment
- Test DB halt flag CRUD operations
- Test dual-channel logic: either channel halt → halted
- Test conflict detection and resolution
- Test graceful degradation when Redis fails
- Use `pytest.mark.asyncio` for async tests
- Use `AsyncMock` for async dependencies

**Integration Tests:**
- Test with real Redis (via testcontainers or local)
- Test with real PostgreSQL (via testcontainers or Supabase local)
- Test full halt flow: trigger → dual-channel write → check
- Test conflict scenarios with injected inconsistencies
- Test 5-second timeout behavior

**Coverage Target:** 80% minimum, 100% for conflict resolution logic

### Previous Story Learnings (Story 3.1, 3.2)

**From Story 3-1 (Fork Monitoring):**
- Use `timezone.utc` not `datetime.UTC` for Python 3.10 compatibility
- Use `tuple[T, ...]` for immutable collections in dataclass fields
- Use `contextlib.suppress(asyncio.CancelledError)` for graceful shutdown
- Export all new types from `__init__.py` files immediately

**From Story 3-2 (Halt Trigger):**
- Callback pattern used for decoupling trigger from transport
- `HaltState` singleton for stub coordination
- Crisis event ID must be included in halt signal for attribution
- Shared state module pattern for stub coordination

**From Code Review Issues:**
- Missing exports in `__init__.py` files are HIGH priority
- Move inline imports to module level
- Use consistent error message prefixes (e.g., "FR17: ...")

### Dependencies

**Story Dependencies:**
- **Story 3.2 (Single-Conflict Halt Trigger):** Provides `HaltTriggerService` that will use this transport
- **Story 1.6 (Event Writer Service):** May need to check halt before writes
- **Story 3.4 (Sticky Halt Semantics):** Will build on this to prevent clearing

**Implementation Order:**
1. Create port interface (no dependencies)
2. Create DB halt flag repository (uses SQLAlchemy)
3. Create Redis publisher (uses redis.asyncio)
4. Create Redis consumer (uses redis.asyncio)
5. Create dual-channel transport adapter (combines all above)
6. Create testing stub (simulates all above)
7. Update HaltTriggerService to use new transport
8. Update HaltChecker to use new transport
9. Integration tests (depends on all above)

### Database Schema

**halt_state table:**
```sql
CREATE TABLE IF NOT EXISTS halt_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    is_halted BOOLEAN NOT NULL DEFAULT FALSE,
    reason TEXT,
    crisis_event_id UUID REFERENCES events(event_id),
    halted_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT single_halt_row CHECK (id = '00000000-0000-0000-0000-000000000001')
);

-- Ensure only one row exists (singleton pattern for halt state)
INSERT INTO halt_state (id, is_halted, reason, crisis_event_id)
VALUES ('00000000-0000-0000-0000-000000000001', FALSE, NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_halt_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER halt_state_updated
    BEFORE UPDATE ON halt_state
    FOR EACH ROW
    EXECUTE FUNCTION update_halt_state_timestamp();
```

### Redis Stream Schema

**Stream: `halt:signals`**
```
Message fields:
- reason: str - Human-readable halt reason
- crisis_event_id: str - UUID of triggering crisis event
- timestamp: str - ISO 8601 timestamp
- source_service: str - Service ID that triggered halt
```

**Consumer Group: `halt:consumers`**
- Each service instance has unique consumer name
- Messages acknowledged after processing
- Pending messages tracked for recovery

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.3]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-003]
- [Source: _bmad-output/planning-artifacts/architecture.md#DEB-002]
- [Source: _bmad-output/planning-artifacts/architecture.md#RT-2]
- [Source: _bmad-output/project-context.md#ADR-3]
- [Source: src/application/services/halt_trigger_service.py] - Will be updated
- [Source: src/infrastructure/stubs/halt_state.py] - Existing shared state pattern
- [Source: src/domain/events/constitutional_crisis.py] - Crisis event for attribution
- [Web: Redis Streams Python async patterns](https://dev.to/streamersuite/async-job-queues-made-simple-with-redis-streams-and-python-asyncio-4410)
- [Web: Redis Streams consumer groups](https://redis.io/docs/latest/commands/xreadgroup/)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
