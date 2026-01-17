# Story GOV-6.2: Implement Advisory Acknowledgment Tracking (FR-GOV-18)

Status: done

## Story

As a **developer**,
I want **tracking that advisories are acknowledged but not binding**,
So that **the advisory relationship is clear**.

## Acceptance Criteria

### AC1: Acknowledgment Recording

**Given** a Marquis issues an advisory
**When** other branches receive it
**Then** they must record acknowledgment (not approval)
**And** the acknowledgment includes:
  - `acknowledged_by`: Archon ID
  - `acknowledged_at`: Timestamp
  - `understanding`: Brief statement of understanding

### AC2: Contrary Decision Documentation

**Given** a decision is made contrary to an advisory
**When** the decision is recorded
**Then** it must document:
  - Reference to the advisory being contradicted
  - Reasoning for the contrary decision
  - Who made the contrary decision
**And** Knight witnesses the contrary decision

### AC3: Acknowledgment Tracking Repository

**Given** advisories require acknowledgment tracking
**When** the repository is queried
**Then** it provides:
  - `get_unacknowledged_advisories(archon_id)` - Advisories pending acknowledgment
  - `get_advisory_acknowledgments(advisory_id)` - All acknowledgments for an advisory
  - `get_contrary_decisions(advisory_id)` - Decisions that contradicted the advisory

### AC4: Acknowledgment Deadline Enforcement

**Given** advisories must be acknowledged within a deadline
**When** the deadline passes without acknowledgment
**Then** the system generates a warning event
**And** escalates to Conclave if pattern continues

### AC5: Non-Approval Distinction

**Given** acknowledgment is distinct from approval
**When** an acknowledgment is recorded
**Then** it explicitly states `approved: false`
**And** documentation clarifies this is acknowledgment of receipt, not agreement

### AC6: Advisory Window Tracking

**Given** advisories create a "window" where Marquis cannot judge
**When** an advisory is issued on topic X
**Then** the system tracks this window
**And** prevents that Marquis from judging topic X (per FR-GOV-18)

## Tasks / Subtasks

- [ ] Task 1: Create Acknowledgment Domain Models (AC: 1, 2, 5)
  - [ ] 1.1 Create `AdvisoryAcknowledgment` frozen dataclass
  - [ ] 1.2 Create `ContraryDecision` frozen dataclass
  - [ ] 1.3 Add `approved: bool = False` field to acknowledgment
  - [ ] 1.4 Add `to_dict()` serialization methods

- [ ] Task 2: Create Advisory Repository Port (AC: 3)
  - [ ] 2.1 Create `src/application/ports/advisory_repository.py`
  - [ ] 2.2 Define `AdvisoryRepositoryProtocol` abstract class
  - [ ] 2.3 Add `save_advisory()` method
  - [ ] 2.4 Add `get_unacknowledged_advisories()` method
  - [ ] 2.5 Add `get_advisory_acknowledgments()` method
  - [ ] 2.6 Add `get_contrary_decisions()` method
  - [ ] 2.7 Add `record_acknowledgment()` method
  - [ ] 2.8 Add `record_contrary_decision()` method

- [ ] Task 3: Create Advisory Acknowledgment Service (AC: 1, 4, 6)
  - [ ] 3.1 Create `src/application/services/advisory_acknowledgment_service.py`
  - [ ] 3.2 Implement acknowledgment recording
  - [ ] 3.3 Implement deadline monitoring
  - [ ] 3.4 Implement advisory window tracking
  - [ ] 3.5 Integrate with Knight witness service

- [ ] Task 4: Create Advisory Window Tracking (AC: 6)
  - [ ] 4.1 Create `AdvisoryWindow` domain model
  - [ ] 4.2 Implement window opening on advisory issuance
  - [ ] 4.3 Implement Marquis-Judge conflict detection
  - [ ] 4.4 Add `check_can_judge(marquis_id, topic)` method

- [ ] Task 5: Unit Tests (AC: 1-6)
  - [ ] 5.1 Create `tests/unit/application/services/test_advisory_acknowledgment.py`
  - [ ] 5.2 Test acknowledgment recording
  - [ ] 5.3 Test contrary decision documentation
  - [ ] 5.4 Test deadline enforcement
  - [ ] 5.5 Test advisory window tracking

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → All acknowledgments must be witnessed

**Government PRD Requirements:**
- **FR-GOV-18:** Marquis Constraints - Advisories must be acknowledged but not obeyed; cannot judge domains where advisory was given

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Application/Port | `src/application/ports/advisory_repository.py` | Advisory repository protocol |
| Application/Service | `src/application/services/advisory_acknowledgment_service.py` | Acknowledgment service |
| Tests | `tests/unit/application/services/test_advisory_acknowledgment.py` | Unit tests |

### Domain Model Design

```python
@dataclass(frozen=True)
class AdvisoryAcknowledgment:
    """Acknowledgment of an advisory receipt.

    Per FR-GOV-18: Acknowledgment is receipt confirmation, not agreement.
    """
    acknowledgment_id: UUID
    advisory_id: UUID
    acknowledged_by: str  # Archon ID
    acknowledged_at: datetime
    understanding: str  # Brief statement of understanding
    approved: bool = False  # ALWAYS False - acknowledgment != approval

@dataclass(frozen=True)
class ContraryDecision:
    """A decision made contrary to an advisory.

    Per FR-GOV-18: Contrary decisions must document reasoning.
    """
    decision_id: UUID
    advisory_id: UUID  # Advisory being contradicted
    decided_by: str  # Archon ID who made contrary decision
    reasoning: str  # Why the advisory was not followed
    decision_summary: str  # What was decided instead
    decided_at: datetime
    witnessed_by: str  # Knight who witnessed

@dataclass(frozen=True)
class AdvisoryWindow:
    """Window during which a Marquis cannot judge on advised topic.

    Per FR-GOV-18: Marquis cannot judge domains where advisory was given.
    """
    window_id: UUID
    marquis_id: str  # Marquis who issued advisory
    advisory_id: UUID
    topic: str
    opened_at: datetime
    closed_at: datetime | None = None  # None = still open
```

### Advisory Acknowledgment Flow

```
Marquis Issues Advisory
        │
        ▼
┌───────────────────┐
│ Knight Witnesses  │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Recipients Notified│
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Start Ack Deadline│  ← Default: 48 hours
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
Acknowledged  Deadline
    │          Missed
    │           │
    ▼           ▼
If Contrary  Warning
Decision:    Generated
└── Document
    Reasoning
```

### Advisory Window Logic

```python
def check_can_judge(self, marquis_id: str, topic: str) -> bool:
    """Check if a Marquis can judge on a topic.

    Per FR-GOV-18: Cannot judge domains where advisory was given.
    """
    windows = self._get_open_windows(marquis_id)
    for window in windows:
        if self._topics_overlap(window.topic, topic):
            return False  # Conflict - cannot judge
    return True  # No conflict
```

### Configuration

```yaml
# config/advisory-tracking.yaml
advisory_tracking:
  acknowledgment_deadline_hours: 48
  window_close_on_motion_complete: true
  warning_on_missed_deadline: true
  escalate_pattern_threshold: 3  # Escalate after 3 missed deadlines
```

### Event Types

```python
# New event types for advisory tracking
ADVISORY_ISSUED = "ADVISORY_ISSUED"
ADVISORY_ACKNOWLEDGED = "ADVISORY_ACKNOWLEDGED"
CONTRARY_DECISION = "CONTRARY_DECISION"
ADVISORY_WINDOW_OPENED = "ADVISORY_WINDOW_OPENED"
ADVISORY_WINDOW_CLOSED = "ADVISORY_WINDOW_CLOSED"
```

### References

- [Source: _bmad-output/planning-artifacts/government-epics.md#Story 6.2]
- [Source: docs/new-requirements.md#FR-GOV-18]
- [Source: config/permissions/rank-matrix.yaml#Marquis constraints]
- [Source: Story GOV-6.1#Marquis Service Port]
- [Source: src/application/ports/knight_witness.py#Witness protocol]
