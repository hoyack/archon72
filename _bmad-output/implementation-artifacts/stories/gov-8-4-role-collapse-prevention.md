# Story GOV-8.4: Implement Role Collapse Prevention (FR-GOV-23)

Status: done

## Story

As a **developer**,
I want **enforcement that no role can be collapsed**,
So that **separation of powers is maintained**.

## Acceptance Criteria

### AC1: Role Collapse Detection

**Given** separate branch services
**When** a single Archon attempts to perform multiple branch functions on same motion
**Then** the collapse is detected
**And** includes identification of:
  - The Archon attempting collapse
  - The roles being collapsed
  - The motion affected

### AC2: Role Collapse Rejection

**Given** a role collapse attempt is detected
**When** the attempt is processed
**Then** it is rejected
**And** the role collapse attempt is witnessed as violation
**And** the rejection includes specific role boundaries violated

### AC3: Branch Action Tracking

**Given** the need to detect role collapse
**When** an Archon acts on a motion
**Then** the action is recorded with:
  - `archon_id`
  - `motion_id`
  - `branch` (legislative, executive, administrative, judicial, witness)
  - `action_type`
  - `timestamp`

### AC4: PRD §2.1 Enforcement

**Given** PRD §2.1 states "No entity may define intent, execute it, AND judge it"
**When** an Archon has already:
  - Introduced a motion (King function), OR
  - Defined execution (President function), OR
  - Executed tasks (Duke/Earl function), OR
  - Judged compliance (Prince function)
**Then** they are blocked from performing other branch functions on that motion

### AC5: Branch Conflict Matrix Integration

**Given** the permission enforcer has branch conflict rules
**When** a role collapse is detected
**Then** it references the specific conflict rule:
  - legislative↔executive: "Same Archon cannot define WHAT and HOW"
  - executive↔judicial: "Same Archon cannot plan execution and judge compliance"
  - advisory↔judicial: "Archon who advised cannot judge that topic"

### AC6: Violation Severity Classification

**Given** role collapse is a separation of powers violation
**When** the violation is recorded
**Then** severity is:
  - `CRITICAL` for legislative↔executive or executive↔judicial collapse
  - `MAJOR` for advisory↔judicial collapse
**And** all role collapse violations require Conclave review

## Tasks / Subtasks

- [x] Task 1: Create Branch Action Tracker (AC: 3)
  - [x] 1.1 Create `BranchAction` domain model
  - [x] 1.2 Create `BranchActionTrackerProtocol` port
  - [x] 1.3 Implement `record_branch_action()` method
  - [x] 1.4 Implement `get_archon_branches(archon_id, motion_id)` method

- [x] Task 2: Create Role Collapse Detector (AC: 1, 4, 5)
  - [x] 2.1 Create `src/application/services/role_collapse_detection_service.py`
  - [x] 2.2 Implement `detect_collapse(archon_id, motion_id, proposed_branch)` method
  - [x] 2.3 Integrate with branch conflict rules from rank-matrix.yaml
  - [x] 2.4 Map conflicts to PRD §2.1

- [x] Task 3: Create Role Collapse Violation Models (AC: 2, 6)
  - [x] 3.1 Create `RoleCollapseViolation` frozen dataclass
  - [x] 3.2 Create `CollapsedRoles` tuple type
  - [x] 3.3 Implement severity classification

- [x] Task 4: Integrate with Permission Enforcer (AC: 5)
  - [x] 4.1 Add `check_branch_conflict()` call before action permission
  - [x] 4.2 Update permission result to include collapse details
  - [x] 4.3 Add role collapse to violation types

- [x] Task 5: Integrate with Flow Orchestrator (AC: 2)
  - [x] 5.1 Add pre-routing collapse check
  - [x] 5.2 Implement rejection handling
  - [x] 5.3 Add Knight witnessing for collapse violations

- [x] Task 6: Unit Tests (AC: 1-6)
  - [x] 6.1 Create `tests/unit/application/services/test_role_collapse_detection.py`
  - [x] 6.2 Test detection of all collapse scenarios
  - [x] 6.3 Test rejection and witnessing
  - [x] 6.4 Test severity classification
  - [x] 6.5 Test PRD §2.1 enforcement

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → All collapse attempts witnessed

**Government PRD Requirements:**
- **PRD §2.1:** Separation of Powers - No entity may define intent, execute it, AND judge it
- **FR-GOV-23:** Governance Flow - No role may be collapsed
- **FR-GOV-1:** Separation of Powers constitutional principle

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Application/Service | `src/application/services/role_collapse_detection_service.py` | Detection service |
| Application/Port | `src/application/ports/branch_action_tracker.py` | Action tracking port |
| Tests | `tests/unit/application/services/test_role_collapse_detection.py` | Unit tests |

### Domain Model Design

```python
@dataclass(frozen=True)
class BranchAction:
    """Record of an Archon acting on a motion in a specific branch."""
    action_id: UUID
    archon_id: str
    motion_id: UUID
    branch: GovernanceBranch
    action_type: GovernanceAction
    acted_at: datetime

@dataclass(frozen=True)
class RoleCollapseViolation:
    """A violation where an Archon attempted to perform multiple branch functions.

    Per PRD §2.1: No entity may define intent, execute it, AND judge it.
    """
    violation_id: UUID
    archon_id: str
    motion_id: UUID
    existing_branches: tuple[GovernanceBranch, ...]
    attempted_branch: GovernanceBranch
    conflict_rule: str  # From rank-matrix.yaml
    prd_reference: str  # PRD §2.1
    severity: str  # CRITICAL or MAJOR
    detected_at: datetime
```

### Branch Conflict Rules (from rank-matrix.yaml)

```python
BRANCH_CONFLICT_RULES = [
    BranchConflictRule(
        branches={"legislative", "executive"},
        rule="Same Archon cannot define WHAT and HOW for same motion",
        prd_ref="PRD §2.1",
        severity="CRITICAL",
    ),
    BranchConflictRule(
        branches={"executive", "judicial"},
        rule="Same Archon cannot plan execution and judge its compliance",
        prd_ref="PRD §2.1",
        severity="CRITICAL",
    ),
    BranchConflictRule(
        branches={"advisory", "judicial"},
        rule="Archon who advised on topic cannot judge that topic",
        prd_ref="FR-GOV-18",
        severity="MAJOR",
    ),
    # Witness branch has no conflicts - exists outside governance
]
```

### Role Collapse Detection Algorithm

```python
def detect_role_collapse(
    archon_id: str,
    motion_id: UUID,
    proposed_branch: GovernanceBranch,
) -> RoleCollapseViolation | None:
    """Detect if an Archon would collapse roles.

    Per PRD §2.1: No entity may define intent, execute it, AND judge it.
    """
    # Get branches this Archon has already acted in for this motion
    existing_branches = self._tracker.get_archon_branches(archon_id, motion_id)

    # Check each conflict rule
    for rule in BRANCH_CONFLICT_RULES:
        if proposed_branch.value in rule.branches:
            for existing in existing_branches:
                if existing.value in rule.branches and existing != proposed_branch:
                    return RoleCollapseViolation(
                        violation_id=uuid4(),
                        archon_id=archon_id,
                        motion_id=motion_id,
                        existing_branches=tuple(existing_branches),
                        attempted_branch=proposed_branch,
                        conflict_rule=rule.rule,
                        prd_reference=rule.prd_ref,
                        severity=rule.severity,
                        detected_at=datetime.now(timezone.utc),
                    )

    return None  # No collapse detected
```

### Integration with Existing Permission Enforcer

The `PermissionEnforcerAdapter` already has `check_branch_conflict()`:

```python
# In permission_enforcer_adapter.py (already exists)
def check_branch_conflict(
    self,
    archon_id: UUID,
    target_id: str,
    proposed_branch: GovernanceBranch,
) -> tuple[bool, str | None]:
    """Check if an Archon would violate separation of powers."""
```

This story enhances that method with:
1. Full branch action tracking
2. Detailed violation recording
3. Knight witnessing integration
4. Conclave review triggering

### Role Collapse Scenarios

```
Scenario 1: King → President (CRITICAL)
┌────────────────────────────────────────────┐
│ Archon A (King rank) introduces motion M   │
│                 ↓                           │
│ Motion M is ratified                        │
│                 ↓                           │
│ Archon A (now acting as President)         │
│ attempts to define execution for M         │
│                 ↓                           │
│ BLOCKED: Same Archon cannot define         │
│          WHAT and HOW                       │
└────────────────────────────────────────────┘

Scenario 2: President → Prince (CRITICAL)
┌────────────────────────────────────────────┐
│ Archon B (President rank) plans execution  │
│                 ↓                           │
│ Execution completes                        │
│                 ↓                           │
│ Archon B attempts to judge compliance      │
│                 ↓                           │
│ BLOCKED: Same Archon cannot plan           │
│          execution and judge it            │
└────────────────────────────────────────────┘

Scenario 3: Marquis → Prince (MAJOR)
┌────────────────────────────────────────────┐
│ Archon C (Marquis rank) advises on topic X │
│                 ↓                           │
│ Topic X comes to judicial review           │
│                 ↓                           │
│ Archon C attempts to judge on topic X      │
│                 ↓                           │
│ BLOCKED: Archon who advised cannot judge   │
└────────────────────────────────────────────┘
```

### Event Types

```python
ROLE_COLLAPSE_VIOLATION = "ROLE_COLLAPSE_VIOLATION"
BRANCH_ACTION_RECORDED = "BRANCH_ACTION_RECORDED"
```

### References

- [Source: _bmad-output/planning-artifacts/government-epics.md#Story 8.4]
- [Source: docs/new-requirements.md#PRD §2.1, FR-GOV-23]
- [Source: config/permissions/rank-matrix.yaml#branch_conflicts]
- [Source: src/infrastructure/adapters/permissions/permission_enforcer_adapter.py#check_branch_conflict]
- [Source: Story GOV-8.1#Governance State Machine]
- [Source: Story GOV-8.2#Flow Orchestrator]
- [Source: Story GOV-8.3#Skip Prevention]
