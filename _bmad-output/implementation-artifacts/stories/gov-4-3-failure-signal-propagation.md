# Story GOV-4.3: Implement Failure Signal Propagation (FR-GOV-13)

Status: done

## Story

As a **developer**,
I want **automatic propagation of execution failures**,
So that **failure signals are never suppressed**.

## Acceptance Criteria

### AC1: Immediate Failure Propagation

**Given** a task execution fails
**When** Duke/Earl detects the failure
**Then** it immediately propagates to Prince for evaluation
**And** the failure is witnessed by Knight before propagation

### AC2: Suppression Detection

**Given** an attempt to suppress a failure signal
**When** the suppression is detected
**Then** it triggers a violation witness event
**And** the suppression attempt is logged with archon_id and details

### AC3: Failure Signal Types

**Given** various failure modes
**When** a failure signal is created
**Then** it includes:
  - `signal_type`: TASK_FAILED, CONSTRAINT_VIOLATED, RESOURCE_EXHAUSTED, TIMEOUT, BLOCKED
  - `source_archon_id`: Duke/Earl who detected the failure
  - `task_id`: Reference to failed task
  - `evidence`: Details supporting the failure
  - `severity`: CRITICAL, HIGH, MEDIUM, LOW
  - `detected_at`: Timestamp of detection

### AC4: Prince Notification

**Given** a failure signal is propagated
**When** the Prince receives it
**Then** they receive full context for evaluation:
  - Original task specification (AegisTaskSpec)
  - Execution result with failure details
  - Evidence collected during execution
  - Timeline of events leading to failure

### AC5: Failure Chain Integrity

**Given** failure signals are critical governance events
**When** a failure signal is emitted
**Then** it is stored in the append-only event store
**And** hash-chained for tamper evidence
**And** witnessed by Knight

### AC6: Anti-Suppression Enforcement

**Given** FR-GOV-13 prohibits failure suppression
**When** a failure occurs but is not propagated within timeout
**Then** the system auto-generates a suppression violation
**And** escalates to Conclave review

## Tasks / Subtasks

- [x] Task 1: Create Failure Signal Domain Models (AC: 3)
  - [x] 1.1 Create `FailureSignalType` Enum
  - [x] 1.2 Create `FailureSeverity` Enum
  - [x] 1.3 Create `FailureSignal` frozen dataclass
  - [x] 1.4 Create `SuppressionViolation` frozen dataclass
  - [x] 1.5 Add `to_dict()` serialization methods

- [x] Task 2: Create Failure Propagation Port (AC: 1, 4)
  - [x] 2.1 Create `src/application/ports/failure_propagation.py`
  - [x] 2.2 Define `FailurePropagationProtocol` abstract class
  - [x] 2.3 Add `emit_failure(signal: FailureSignal)` method
  - [x] 2.4 Add `notify_prince(signal: FailureSignal)` method
  - [x] 2.5 Add `get_pending_failures(task_id: UUID)` method

- [x] Task 3: Create Suppression Detection Service (AC: 2, 6)
  - [x] 3.1 Create `src/application/services/suppression_detection_service.py`
  - [x] 3.2 Implement failure timeout monitoring
  - [x] 3.3 Implement suppression violation generation
  - [x] 3.4 Integrate with Knight witness service

- [x] Task 4: Integrate with Event Store (AC: 5)
  - [x] 4.1 Define `FAILURE_SIGNAL` event type
  - [x] 4.2 Define `SUPPRESSION_VIOLATION` event type
  - [x] 4.3 Add failure signal to hash chain
  - [x] 4.4 Ensure Knight witnessing before storage

- [x] Task 5: Unit Tests (AC: 1-6)
  - [x] 5.1 Create `tests/unit/application/services/test_failure_propagation.py`
  - [x] 5.2 Test failure signal creation and propagation
  - [x] 5.3 Test suppression detection
  - [x] 5.4 Test Prince notification

- [x] Task 6: Integration Tests (AC: 5)
  - [x] 6.1 Create `tests/integration/test_failure_propagation_integration.py`
  - [x] 6.2 Test failure signal storage in event store
  - [x] 6.3 Test hash chain integrity for failure signals

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → All failures must be witnessed
- **CT-13:** Integrity outranks availability → Never suppress failure signals

**Government PRD Requirements:**
- **FR-GOV-13:** Duke/Earl Constraints - No suppression of failure signals
- **NFR-GOV-5:** System may fail to enforce but must not conceal

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Application/Port | `src/application/ports/failure_propagation.py` | Failure propagation protocol |
| Application/Service | `src/application/services/suppression_detection_service.py` | Suppression detection |
| Tests | `tests/unit/application/services/test_failure_propagation.py` | Unit tests |
| Tests | `tests/integration/test_failure_propagation_integration.py` | Integration tests |

### Domain Model Design

```python
class FailureSignalType(Enum):
    """Types of failure signals from Duke/Earl execution."""
    TASK_FAILED = "task_failed"
    CONSTRAINT_VIOLATED = "constraint_violated"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    INTENT_AMBIGUITY = "intent_ambiguity"

class FailureSeverity(Enum):
    """Severity levels for failure signals."""
    CRITICAL = "critical"  # Halt execution, immediate Prince review
    HIGH = "high"          # Prince review in next cycle
    MEDIUM = "medium"      # Logged, advisory Prince notification
    LOW = "low"            # Logged only

@dataclass(frozen=True)
class FailureSignal:
    """A failure signal emitted by Duke/Earl.

    Per FR-GOV-13: Failure signals MUST be propagated, never suppressed.
    """
    signal_id: UUID
    signal_type: FailureSignalType
    source_archon_id: str  # Duke or Earl who detected
    task_id: UUID
    severity: FailureSeverity
    evidence: dict[str, Any]
    detected_at: datetime
    propagated_at: datetime | None = None
    prince_notified: bool = False

@dataclass(frozen=True)
class SuppressionViolation:
    """A violation where failure was suppressed.

    This is a CRITICAL governance violation per FR-GOV-13.
    """
    violation_id: UUID
    signal_id: UUID  # Original failure signal
    suppressing_archon_id: str
    detection_method: str  # e.g., "timeout", "manual_override"
    detected_at: datetime
```

### Suppression Detection Flow

```
Task Failure Detected
        │
        ▼
┌───────────────────┐
│ Create FailureSignal │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Knight Witnesses  │  ← FR-GOV-20: Observe and record
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Start Propagation │
│    Timeout       │  ← Default: 30 seconds
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
Propagated   Timeout
    │           │
    ▼           ▼
Prince      SuppressionViolation
Notified    ├── Knight Witnesses
            ├── Escalate to Conclave
            └── CRITICAL severity
```

### Configuration

```yaml
# config/failure-propagation.yaml
failure_propagation:
  timeout_seconds: 30  # Max time before suppression violation
  retry_attempts: 3    # Retries before declaring failure
  prince_notification:
    critical: immediate
    high: next_cycle
    medium: advisory
    low: log_only
```

### Event Types

```python
# New event types for failure propagation
FAILURE_SIGNAL = "FAILURE_SIGNAL"
SUPPRESSION_VIOLATION = "SUPPRESSION_VIOLATION"
```

### References

- [Source: _bmad-output/planning-artifacts/government-epics.md#Story 4.3]
- [Source: docs/new-requirements.md#FR-GOV-13]
- [Source: config/permissions/rank-matrix.yaml#Duke and Earl constraints]
- [Source: src/application/ports/knight_witness.py#Witness protocol]
- [Source: Story GOV-4.1#Duke Service Port]
- [Source: Story GOV-4.2#Earl Service Port]
