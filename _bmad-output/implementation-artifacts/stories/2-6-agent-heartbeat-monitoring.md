# Story 2.6: Agent Heartbeat Monitoring (FR14, FR90-FR93)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **system operator**,
I want agents to emit heartbeats during deliberation,
So that I can detect stalled or crashed agents.

## Acceptance Criteria

### AC1: Heartbeat Emission During Deliberation
**Given** an agent is actively deliberating
**When** it is healthy
**Then** it emits a heartbeat every 30 seconds
**And** heartbeat includes: `agent_id`, `session_id`, `status`, `memory_usage`

### AC2: Agent Unresponsive Detection
**Given** an agent misses 3 consecutive heartbeats (90 seconds)
**When** the watchdog detects this
**Then** an `AgentUnresponsiveEvent` is created
**And** the agent is flagged for recovery

### AC3: Missing Heartbeat Logging
**Given** a missing heartbeat
**When** logged
**Then** it includes last known state and timestamp
**And** failure detection time is recorded

### AC4: Heartbeat Spoofing Defense (FR90)
**Given** agent heartbeat spoofing defense
**When** a heartbeat is received
**Then** it is verified against agent's session token
**And** spoofed heartbeats are rejected and logged

## Tasks / Subtasks

- [x] Task 1: Create Heartbeat Domain Model (AC: 1) - ~6 tests
  - [x] 1.1 Create `src/domain/models/heartbeat.py`
  - [x] 1.2 Define `Heartbeat` frozen dataclass with:
    - `heartbeat_id: UUID`
    - `agent_id: str`
    - `session_id: UUID`
    - `status: AgentStatus` (reuse from agent_orchestrator.py)
    - `memory_usage_mb: int`
    - `timestamp: datetime`
    - `signature: Optional[str]`
  - [x] 1.3 Add validation: agent_id format, memory_usage >= 0
  - [x] 1.4 Add to `src/domain/models/__init__.py` exports
  - [x] 1.5 Add unit tests

- [x] Task 2: Create HeartbeatEmitter Port Interface (AC: 1, 4) - ~6 tests
  - [x] 2.1 Create `src/application/ports/heartbeat_emitter.py`
  - [x] 2.2 Define `HeartbeatEmitterPort(Protocol)` with:
    - `async def emit_heartbeat(agent_id: str, session_id: UUID, status: AgentStatus, memory_usage_mb: int) -> Heartbeat`
    - `async def sign_heartbeat(heartbeat: Heartbeat, agent_key: AgentKey) -> Heartbeat`
  - [x] 2.3 Define constants: `HEARTBEAT_INTERVAL_SECONDS = 30`, `MISSED_HEARTBEAT_THRESHOLD = 3`
  - [x] 2.4 Add to `src/application/ports/__init__.py` exports
  - [x] 2.5 Add unit tests for protocol definition

- [x] Task 3: Create HeartbeatMonitorPort Interface (AC: 2, 3) - ~6 tests
  - [x] 3.1 Create `src/application/ports/heartbeat_monitor.py`
  - [x] 3.2 Define `HeartbeatMonitorPort(Protocol)` with:
    - `async def register_heartbeat(heartbeat: Heartbeat) -> None`
    - `async def get_last_heartbeat(agent_id: str) -> Optional[Heartbeat]`
    - `async def get_unresponsive_agents(threshold_seconds: int = 90) -> list[str]`
    - `async def is_agent_responsive(agent_id: str) -> bool`
  - [x] 3.3 Add to `src/application/ports/__init__.py` exports
  - [x] 3.4 Add unit tests

- [x] Task 4: Create AgentUnresponsiveError Domain Error (AC: 2) - ~4 tests
  - [x] 4.1 Create `src/domain/errors/heartbeat.py`
  - [x] 4.2 Define `AgentUnresponsiveError(ConclaveError)` with:
    - `agent_id: str`
    - `last_heartbeat_timestamp: Optional[datetime]`
    - `missed_count: int`
  - [x] 4.3 Define `HeartbeatSpoofingError(ConstitutionalViolationError)` for FR90
  - [x] 4.4 Add to `src/domain/errors/__init__.py` exports
  - [x] 4.5 Add unit tests

- [x] Task 5: Create HeartbeatVerifier Domain Service (AC: 4) - ~10 tests
  - [x] 5.1 Create `src/domain/services/heartbeat_verifier.py`
  - [x] 5.2 Define `HeartbeatVerifier` class with:
    - `verify_heartbeat_signature(heartbeat: Heartbeat, expected_key: AgentKey) -> bool`
    - `detect_spoofing(heartbeat: Heartbeat, session_registry: dict) -> bool`
    - `reject_spoofed_heartbeat(heartbeat: Heartbeat) -> None` raises HeartbeatSpoofingError
  - [x] 5.3 Reuse `verify_signature()` from `src/domain/events/signing.py`
  - [x] 5.4 Add unit tests

- [x] Task 6: Create HeartbeatEmitterStub Infrastructure (AC: 1) - ~8 tests
  - [x] 6.1 Create `src/infrastructure/stubs/heartbeat_emitter_stub.py`
  - [x] 6.2 Implement `HeartbeatEmitterStub` with in-memory emission tracking
  - [x] 6.3 Follow DEV_MODE_WATERMARK pattern (RT-1/ADR-4)
  - [x] 6.4 Add unit tests

- [x] Task 7: Create HeartbeatMonitorStub Infrastructure (AC: 2, 3) - ~8 tests
  - [x] 7.1 Create `src/infrastructure/stubs/heartbeat_monitor_stub.py`
  - [x] 7.2 Implement `HeartbeatMonitorStub` with:
    - In-memory heartbeat storage by agent_id
    - Unresponsive detection based on timestamp comparison
    - Configurable threshold (default 90 seconds)
  - [x] 7.3 Follow DEV_MODE_WATERMARK pattern
  - [x] 7.4 Add unit tests

- [x] Task 8: Create HeartbeatService Application Service (AC: 1, 2, 3, 4) - ~12 tests
  - [x] 8.1 Create `src/application/services/heartbeat_service.py`
  - [x] 8.2 Inject: `HaltChecker`, `HeartbeatEmitterPort`, `HeartbeatMonitorPort`, `HeartbeatVerifier`
  - [x] 8.3 Implement `async def emit_agent_heartbeat(agent_id, session_id, status, memory_usage)`:
    - Check HALT FIRST
    - Create heartbeat
    - Sign with agent's key
    - Register with monitor
  - [x] 8.4 Implement `async def check_agent_liveness(agent_id)`:
    - Get last heartbeat
    - Check threshold (90s = 3 missed heartbeats)
    - Log missing heartbeats with last known state
  - [x] 8.5 Implement `async def detect_unresponsive_agents()`:
    - Return list of agents that missed threshold
    - For each, create `AgentUnresponsiveEvent` (domain event)
    - Flag for recovery
  - [x] 8.6 Implement `async def verify_and_register_heartbeat(heartbeat)`:
    - Verify signature against session token
    - Reject and log spoofed heartbeats (FR90)
    - Register valid heartbeats
  - [x] 8.7 Add unit tests

- [x] Task 9: Create AgentUnresponsiveEvent Domain Event (AC: 2) - ~6 tests
  - [x] 9.1 Create `src/domain/events/agent_unresponsive.py`
  - [x] 9.2 Define `AgentUnresponsivePayload` (frozen dataclass) with:
    - `agent_id: str`
    - `session_id: UUID`
    - `last_heartbeat: Optional[datetime]`
    - `missed_heartbeat_count: int`
    - `detection_timestamp: datetime`
    - `flagged_for_recovery: bool`
  - [x] 9.3 Add to `src/domain/events/__init__.py` exports
  - [x] 9.4 Add unit tests (9 tests)

- [x] Task 10: FR14/FR90-FR93 Compliance Integration Tests (AC: 1, 2, 3, 4) - 19 tests
  - [x] 10.1 Create `tests/integration/test_heartbeat_monitoring_integration.py`
  - [x] 10.2 Test: Agent emits heartbeat every 30s during deliberation
  - [x] 10.3 Test: Heartbeat includes all required fields (agent_id, session_id, status, memory_usage)
  - [x] 10.4 Test: 3 missed heartbeats (90s) triggers AgentUnresponsiveEvent
  - [x] 10.5 Test: Unresponsive agent is flagged for recovery
  - [x] 10.6 Test: Missing heartbeat log includes last known state and timestamp
  - [x] 10.7 Test: Failure detection time is recorded
  - [x] 10.8 Test: Valid heartbeats pass signature verification
  - [x] 10.9 Test: Spoofed heartbeats are rejected (FR90)
  - [x] 10.10 Test: Spoofed heartbeats are logged with rejection reason
  - [x] 10.11 Test: HALT state blocks heartbeat operations
  - [x] 10.12 Test: End-to-end heartbeat monitoring flow

## Dev Notes

### Critical Architecture Context

**FR14, FR90-FR93: Agent Liveness Primitives**
From the PRD:
- FR90: Each agent SHALL emit heartbeat event at minimum every 5 minutes during active operation (story uses 30s interval for faster detection)
- FR91: Missing heartbeat beyond 2x expected interval SHALL trigger agent unavailability alert
- FR92: System SHALL maintain minimum 6 available witnesses at all times (not in scope for this story)
- FR93: Witnesses not responding within 30 seconds SHALL be temporarily removed from selection pool with recorded event (not in scope for this story)

**Note:** This story focuses on agent heartbeats (FR90-FR91). Witness heartbeats (FR92-FR93) are handled separately in Epic 6.

**Constitutional Truths Honored:**
- **CT-11:** Silent failure destroys legitimacy -> Missing heartbeats MUST be detected and logged
- **CT-12:** Witnessing creates accountability -> All heartbeat operations are traceable
- **CT-13:** Integrity outranks availability -> Unresponsive agents flagged, not silently dropped

### Previous Story Intelligence (Story 2.5)

**Key Learnings from Story 2.5:**
- HALT FIRST pattern enforced throughout (check halt before operations)
- DEV_MODE_WATERMARK pattern for all stubs
- Hexagonal architecture strictly maintained (domain has no infrastructure imports)
- Structured logging with structlog (no print statements or f-strings in logs)
- Total ~50 tests created for comprehensive coverage
- Application services use dependency injection for ports

**Existing Code to Reuse:**
- `AgentStatus` enum from `src/application/ports/agent_orchestrator.py` - agent statuses
- `AgentKey` model from `src/domain/models/agent_key.py` - agent cryptographic keys
- `verify_signature()` from `src/domain/events/signing.py` - signature verification
- `HaltChecker` pattern from `src/application/ports/halt_checker.py` - HALT checking
- `ConclaveError` from `src/domain/exceptions.py` - base exception class
- `ConstitutionalViolationError` from `src/domain/errors/constitutional.py` - FR errors

### Heartbeat Flow

```
1. Agent starts deliberation
2. HeartbeatService.emit_agent_heartbeat() called every 30s:
   a. HALT CHECK (fail fast if halted)
   b. Create Heartbeat with agent_id, session_id, status, memory_usage
   c. Sign heartbeat with agent's key
   d. Register with HeartbeatMonitor
3. Watchdog periodically calls HeartbeatService.detect_unresponsive_agents():
   a. Get all agents with last heartbeat > 90s ago
   b. For each unresponsive agent:
      - Create AgentUnresponsiveEvent
      - Log with last known state and timestamp
      - Flag for recovery
4. Incoming heartbeats verified:
   a. Verify signature against session token
   b. If mismatch -> reject, log, raise HeartbeatSpoofingError
   c. If valid -> register heartbeat
```

### Heartbeat Model Design

```python
@dataclass(frozen=True)
class Heartbeat:
    """Agent heartbeat for liveness monitoring (FR90).

    Attributes:
        heartbeat_id: Unique identifier for this heartbeat.
        agent_id: The ID of the agent (e.g., "archon-42").
        session_id: The current deliberation session ID.
        status: Current agent status (IDLE, BUSY, FAILED, UNKNOWN).
        memory_usage_mb: Current memory usage in megabytes.
        timestamp: When the heartbeat was emitted.
        signature: Cryptographic signature for spoofing defense (FR90).
    """
    heartbeat_id: UUID
    agent_id: str
    session_id: UUID
    status: AgentStatus
    memory_usage_mb: int
    timestamp: datetime
    signature: Optional[str] = None
```

### AgentUnresponsiveEvent Design

```python
@dataclass(frozen=True)
class AgentUnresponsiveEvent:
    """Event created when an agent misses heartbeat threshold (FR91).

    Attributes:
        event_id: Unique identifier for this event.
        agent_id: The ID of the unresponsive agent.
        session_id: The session during which unresponsiveness occurred.
        last_heartbeat: Timestamp of last known heartbeat (if any).
        missed_heartbeat_count: Number of consecutive missed heartbeats.
        detection_timestamp: When unresponsiveness was detected.
        flagged_for_recovery: Whether agent has been flagged for recovery.
    """
    event_id: UUID
    agent_id: str
    session_id: UUID
    last_heartbeat: Optional[datetime]
    missed_heartbeat_count: int
    detection_timestamp: datetime
    flagged_for_recovery: bool = True
```

### Project Structure Notes

**Files to Create:**
```
src/
├── domain/
│   ├── models/
│   │   └── heartbeat.py              # Heartbeat dataclass
│   ├── errors/
│   │   └── heartbeat.py              # AgentUnresponsiveError, HeartbeatSpoofingError
│   ├── events/
│   │   └── agent_unresponsive.py     # AgentUnresponsiveEvent
│   └── services/
│       └── heartbeat_verifier.py     # HeartbeatVerifier
├── application/
│   ├── ports/
│   │   ├── heartbeat_emitter.py      # HeartbeatEmitterPort
│   │   └── heartbeat_monitor.py      # HeartbeatMonitorPort
│   └── services/
│       └── heartbeat_service.py      # HeartbeatService
└── infrastructure/
    └── stubs/
        ├── heartbeat_emitter_stub.py # HeartbeatEmitterStub
        └── heartbeat_monitor_stub.py # HeartbeatMonitorStub

tests/
├── unit/
│   ├── domain/
│   │   ├── test_heartbeat.py                  # 6 tests
│   │   ├── test_heartbeat_errors.py           # 4 tests
│   │   ├── test_agent_unresponsive_event.py   # 6 tests
│   │   └── test_heartbeat_verifier.py         # 10 tests
│   ├── application/
│   │   ├── test_heartbeat_emitter_port.py     # 6 tests
│   │   ├── test_heartbeat_monitor_port.py     # 6 tests
│   │   └── test_heartbeat_service.py          # 12 tests
│   └── infrastructure/
│       ├── test_heartbeat_emitter_stub.py     # 8 tests
│       └── test_heartbeat_monitor_stub.py     # 8 tests
└── integration/
    └── test_heartbeat_monitoring_integration.py  # 12 tests
```

**Files to Modify:**
```
src/domain/models/__init__.py         # Add Heartbeat export
src/domain/errors/__init__.py         # Add AgentUnresponsiveError, HeartbeatSpoofingError exports
src/domain/events/__init__.py         # Add AgentUnresponsiveEvent export
src/application/ports/__init__.py     # Add HeartbeatEmitterPort, HeartbeatMonitorPort exports
```

**Alignment with Hexagonal Architecture:**
- Domain layer (`domain/`) has NO infrastructure imports
- Application layer (`application/`) orchestrates domain and uses ports
- Infrastructure layer (`infrastructure/`) implements adapters for ports
- Import boundary enforcement from Story 0-6 MUST be respected

### Testing Standards

Per `project-context.md`:
- ALL test files use `pytest.mark.asyncio`
- Use `async def test_*` for async tests
- Use `AsyncMock` not `Mock` for async functions
- Unit tests in `tests/unit/{module}/test_{name}.py`
- Integration tests in `tests/integration/test_{feature}_integration.py`
- 80% minimum coverage

**Expected Test Count:** ~78 tests total (6+6+6+4+10+8+8+12+6+12)

### Library/Framework Requirements

**Required Dependencies (already installed in Epic 0):**
- `structlog` for logging (NO print statements, NO f-strings in logs)
- `pytest-asyncio` for async testing
- Python 3.10+ compatible (use `Optional[T]` not `T | None`)
- `hashlib` from stdlib for signature verification

**Do NOT add new dependencies without explicit approval.**

### Logging Pattern

Per `project-context.md`, use structured logging:
```python
import structlog

logger = structlog.get_logger()

# CORRECT
logger.info(
    "heartbeat_emitted",
    agent_id=agent_id,
    session_id=str(session_id),
    status=status.value,
    memory_usage_mb=memory_usage,
)

logger.warning(
    "agent_unresponsive",
    agent_id=agent_id,
    last_heartbeat=str(last_heartbeat) if last_heartbeat else "never",
    missed_count=missed_count,
    detection_time=str(datetime.utcnow()),
)

logger.error(
    "heartbeat_spoofing_detected",
    agent_id=heartbeat.agent_id,
    session_id=str(heartbeat.session_id),
    rejection_reason="signature_mismatch",
)

# WRONG - Never do these
print(f"Heartbeat from {agent_id}")  # No print
logger.info(f"Agent {agent_id} unresponsive")  # No f-strings in logs
```

### Integration with Previous Stories

**Story 2.2 (FR10 - 72 Concurrent Agents):**
- AgentPool and AgentOrchestratorProtocol already exist
- HeartbeatService will work with these to monitor agent liveness
- Each of 72 agents needs heartbeat monitoring

**Story 2.3 (FR11 - Collective Output):**
- Collective outputs require all participating agents to be responsive
- HeartbeatService provides liveness checks for collective operations

**Story 2.4 (FR12 - Dissent Tracking):**
- Dissent metrics require agent availability
- Missing heartbeats may indicate agent failure during voting

**Story 2.5 (FR13 - No Silent Edits):**
- HALT FIRST pattern applies to heartbeat operations
- Hash verification patterns can be reused for heartbeat signatures

### Security Considerations

**Spoofing Defense (FR90):**
- All heartbeats must be signed with agent's key
- Session token verification prevents impersonation
- Spoofed heartbeats are logged and rejected
- HeartbeatSpoofingError is a constitutional violation

**Agent Recovery:**
- Unresponsive agents are flagged, not silently dropped
- Recovery mechanism tracked via AgentUnresponsiveEvent
- All recovery attempts logged with full context

**Audit Trail:**
- Every heartbeat emission logged
- Missing heartbeats logged with last known state
- Spoofing attempts logged with rejection reason
- All events are traceable for forensics

### Timing Configuration

| Constant | Value | Rationale |
|----------|-------|-----------|
| `HEARTBEAT_INTERVAL_SECONDS` | 30 | Faster than PRD minimum (5 min) for quicker detection |
| `MISSED_HEARTBEAT_THRESHOLD` | 3 | 3 missed = 90 seconds = unresponsive |
| `UNRESPONSIVE_TIMEOUT_SECONDS` | 90 | 3 * 30 seconds |

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.6: Agent Heartbeat Monitoring]
- [Source: _bmad-output/project-context.md]
- [Source: _bmad-output/implementation-artifacts/stories/2-5-no-silent-edits.md] - Previous story patterns
- [Source: _bmad-output/planning-artifacts/prd.md#Liveness Primitives FR90-FR93]
- [Source: src/application/ports/agent_orchestrator.py] - AgentStatus enum
- [Source: src/domain/models/agent_key.py] - AgentKey model
- [Source: src/domain/events/signing.py] - verify_signature pattern
- [Source: src/application/ports/halt_checker.py] - HALT checking pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-5] - Watchdog Independence
- [Source: _bmad-output/planning-artifacts/architecture.md#CH-6] - Heartbeat timeout: 30s default

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

