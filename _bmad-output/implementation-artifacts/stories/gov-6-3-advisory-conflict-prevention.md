# Story GOV-6.3: Implement Advisory Conflict Prevention (FR-GOV-18)

Status: done

## Story

As a **developer**,
I want **enforcement that Marquis cannot judge domains they advised on**,
So that **conflict of interest is prevented**.

## Acceptance Criteria

### AC1: Conflict Detection

**Given** a Marquis advised on topic X
**When** that topic comes to judicial review
**Then** that Marquis is automatically detected as having a conflict
**And** the conflict is logged with advisory reference

### AC2: Prince Panel Exclusion

**Given** a Marquis is detected with conflict
**When** a judicial panel is formed for that topic
**Then** the conflicted Marquis is excluded from the panel
**And** alternative Princes are selected

### AC3: Participation Violation Witnessing

**Given** a conflicted Marquis attempts to participate in judgment
**When** the participation is detected
**Then** it triggers a violation witness event
**And** the attempted judgment is invalidated
**And** the violation is recorded with severity: MAJOR

### AC4: Topic Overlap Detection

**Given** advisory topics may not exactly match judgment topics
**When** conflict detection runs
**Then** it uses semantic similarity to detect overlapping topics
**And** configurable threshold determines "same topic"

### AC5: Conflict Resolution Path

**Given** all available Princes have conflicts on a topic
**When** no unconflicted panel can be formed
**Then** the system escalates to Conclave
**And** documents the conflict pattern

### AC6: Conflict Audit Trail

**Given** conflicts must be auditable
**When** a conflict is detected
**Then** a full audit trail is maintained:
  - Original advisory with topic and date
  - Judgment request with topic
  - Conflict detection result
  - Action taken (exclusion, violation, escalation)

## Tasks / Subtasks

- [ ] Task 1: Create Conflict Detection Service (AC: 1, 4)
  - [ ] 1.1 Create `src/application/services/advisory_conflict_detection_service.py`
  - [ ] 1.2 Implement `detect_conflicts(marquis_id, topic)` method
  - [ ] 1.3 Implement semantic topic overlap detection
  - [ ] 1.4 Configure overlap threshold

- [ ] Task 2: Create Prince Panel Management (AC: 2, 5)
  - [ ] 2.1 Add `exclude_conflicted_from_panel()` method
  - [ ] 2.2 Implement alternative Prince selection
  - [ ] 2.3 Implement escalation path when all Princes conflicted

- [ ] Task 3: Create Violation Detection (AC: 3)
  - [ ] 3.1 Integrate with permission enforcer
  - [ ] 3.2 Implement participation interception
  - [ ] 3.3 Create `AdvisoryConflictViolation` domain model
  - [ ] 3.4 Integrate with Knight witness service

- [ ] Task 4: Create Audit Trail (AC: 6)
  - [ ] 4.1 Create `ConflictAuditEntry` domain model
  - [ ] 4.2 Implement audit trail logging
  - [ ] 4.3 Create `get_conflict_audit(advisory_id)` method

- [ ] Task 5: Integration with Prince Service (AC: 2, 3)
  - [ ] 5.1 Add conflict check to `PrinceServiceProtocol`
  - [ ] 5.2 Implement `can_judge(prince_id, topic)` method
  - [ ] 5.3 Add pre-judgment conflict validation

- [ ] Task 6: Unit Tests (AC: 1-6)
  - [ ] 6.1 Create `tests/unit/application/services/test_advisory_conflict_detection.py`
  - [ ] 6.2 Test conflict detection
  - [ ] 6.3 Test topic overlap detection
  - [ ] 6.4 Test panel exclusion
  - [ ] 6.5 Test violation witnessing
  - [ ] 6.6 Test audit trail

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → All conflicts must be witnessed

**Government PRD Requirements:**
- **FR-GOV-18:** Marquis cannot judge domains where advisory was given
- **PRD §2.1:** Separation of Powers - No entity may define intent, execute it, AND judge it

**Permission Matrix Integration:**
Per `config/permissions/rank-matrix.yaml`:
```yaml
branch_conflicts:
  - branches: ["advisory", "judicial"]
    rule: "Archon who advised on topic cannot judge that topic"
```

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Application/Service | `src/application/services/advisory_conflict_detection_service.py` | Conflict detection |
| Tests | `tests/unit/application/services/test_advisory_conflict_detection.py` | Unit tests |

### Domain Model Design

```python
@dataclass(frozen=True)
class TopicOverlap:
    """Result of topic overlap analysis."""
    overlap_score: float  # 0.0 to 1.0
    advisory_topic: str
    judgment_topic: str
    is_conflict: bool  # True if score > threshold

@dataclass(frozen=True)
class AdvisoryConflict:
    """A detected conflict between advisory and judgment roles."""
    conflict_id: UUID
    marquis_id: str
    advisory_id: UUID
    advisory_topic: str
    judgment_topic: str
    overlap: TopicOverlap
    detected_at: datetime
    resolution: str  # "excluded", "violated", "escalated"

@dataclass(frozen=True)
class AdvisoryConflictViolation:
    """Violation when a conflicted Marquis attempts judgment."""
    violation_id: UUID
    conflict: AdvisoryConflict
    attempted_action: str
    invalidated: bool = True
    severity: str = "MAJOR"
    witnessed_by: str | None = None

@dataclass(frozen=True)
class ConflictAuditEntry:
    """Audit trail entry for conflict detection."""
    entry_id: UUID
    conflict_id: UUID
    event_type: str  # "detected", "excluded", "violated", "escalated"
    details: dict[str, Any]
    recorded_at: datetime
```

### Conflict Detection Flow

```
Judgment Request on Topic
        │
        ▼
┌───────────────────┐
│ Query Advisory    │
│ Windows for Topic │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Topic Overlap     │
│ Analysis          │
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    │           │
 Overlap     No Overlap
 > threshold  < threshold
    │           │
    ▼           ▼
Conflict     Clear to
Detected     Judge
    │
    ▼
┌───────────────────┐
│ Exclude from      │
│ Prince Panel      │
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    │           │
Panel OK    All Princes
            Conflicted
    │           │
    ▼           ▼
Proceed     Escalate to
            Conclave
```

### Topic Overlap Algorithm

```python
def calculate_topic_overlap(
    advisory_topic: str,
    judgment_topic: str,
) -> TopicOverlap:
    """Calculate semantic overlap between topics.

    Uses simple heuristics for now:
    1. Exact match → 1.0
    2. Contains match → 0.8
    3. Keyword overlap → proportional
    4. No match → 0.0

    Configurable threshold (default 0.6) determines conflict.
    """
    if advisory_topic.lower() == judgment_topic.lower():
        return TopicOverlap(
            overlap_score=1.0,
            advisory_topic=advisory_topic,
            judgment_topic=judgment_topic,
            is_conflict=True,
        )

    # Keyword analysis...
    keywords_a = set(advisory_topic.lower().split())
    keywords_j = set(judgment_topic.lower().split())
    overlap = len(keywords_a & keywords_j) / max(len(keywords_a | keywords_j), 1)

    return TopicOverlap(
        overlap_score=overlap,
        advisory_topic=advisory_topic,
        judgment_topic=judgment_topic,
        is_conflict=overlap >= CONFLICT_THRESHOLD,
    )
```

### Configuration

```yaml
# config/advisory-conflict.yaml
advisory_conflict:
  overlap_threshold: 0.6  # Similarity score to consider conflict
  exclusion_automatic: true
  violation_severity: "MAJOR"
  escalation_enabled: true
```

### Integration Points

1. **Prince Service** - Pre-judgment conflict check
2. **Permission Enforcer** - Branch conflict validation (advisory↔judicial)
3. **Knight Witness** - Violation witnessing
4. **Advisory Repository** - Window queries

### References

- [Source: _bmad-output/planning-artifacts/government-epics.md#Story 6.3]
- [Source: docs/new-requirements.md#FR-GOV-18]
- [Source: config/permissions/rank-matrix.yaml#branch_conflicts]
- [Source: Story GOV-6.1#Marquis Service Port]
- [Source: Story GOV-6.2#Advisory Acknowledgment Tracking]
- [Source: src/application/ports/prince_service.py#PrinceServiceProtocol]
