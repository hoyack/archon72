# Story consent-gov-6.4: Prince Panel Domain Model

Status: ready-for-dev

---

## Story

As a **governance system**,
I want **a Prince Panel domain model**,
So that **panels can review and issue findings**.

---

## Acceptance Criteria

1. **AC1:** Panel requires ≥3 members (FR36)
2. **AC2:** Human Operator convenes panel
3. **AC3:** Panel can review witness artifacts (FR37)
4. **AC4:** Panel can issue formal finding with remedy (FR38)
5. **AC5:** Panel can record dissent in finding (FR39)
6. **AC6:** Panel composition validated before accepting finding
7. **AC7:** Recusal mechanism for conflict of interest
8. **AC8:** Unit tests for panel mechanics

---

## Tasks / Subtasks

- [ ] **Task 1: Create panel domain package** (AC: 1, 2)
  - [ ] Create `src/domain/governance/panel/__init__.py`
  - [ ] Create `src/domain/governance/panel/prince_panel.py`
  - [ ] Define panel composition rules
  - [ ] Document convening requirements

- [ ] **Task 2: Create PrincePanel domain model** (AC: 1, 2, 7)
  - [ ] Define immutable value object for panel state
  - [ ] Include panel_id, convened_by, members
  - [ ] Include convened_at, status
  - [ ] Validate ≥3 members on creation

- [ ] **Task 3: Create PanelMember model** (AC: 1, 7)
  - [ ] Include member_id, role, joined_at
  - [ ] Track recusal status
  - [ ] Track participation status
  - [ ] No rank/influence weight (all equal)

- [ ] **Task 4: Create PanelFinding domain model** (AC: 4, 5)
  - [ ] Include finding_id, panel_id, statement_id
  - [ ] Include determination (violation/no_violation)
  - [ ] Include remedy (if violation found)
  - [ ] Include dissent (minority opinion)

- [ ] **Task 5: Create RemedyType enum** (AC: 4)
  - [ ] WARNING: Formal notice
  - [ ] CORRECTION: Require action change
  - [ ] ESCALATION: Route to higher authority
  - [ ] HALT_RECOMMENDATION: Recommend system halt
  - [ ] No punitive remedies (dignity preservation)

- [ ] **Task 6: Implement composition validation** (AC: 1, 6)
  - [ ] Minimum 3 members required
  - [ ] All members must be active (not recused)
  - [ ] Quorum for finding: majority of active members
  - [ ] Reject finding if composition invalid

- [ ] **Task 7: Implement recusal mechanism** (AC: 7)
  - [ ] Member can recuse from specific case
  - [ ] Recusal recorded with reason
  - [ ] Panel still valid if ≥3 active remain
  - [ ] Panel invalid if <3 active members

- [ ] **Task 8: Implement artifact review** (AC: 3)
  - [ ] Panel receives witness statements
  - [ ] Panel can access related events
  - [ ] Review session recorded
  - [ ] All evidence preserved

- [ ] **Task 9: Create PanelPort interface** (AC: 2, 4)
  - [ ] Create `src/application/ports/governance/panel_port.py`
  - [ ] Define `convene_panel()` method
  - [ ] Define `record_finding()` method
  - [ ] Define `record_recusal()` method

- [ ] **Task 10: Write comprehensive unit tests** (AC: 8)
  - [ ] Test panel requires ≥3 members
  - [ ] Test panel convening
  - [ ] Test finding with remedy
  - [ ] Test dissent recording
  - [ ] Test recusal mechanics
  - [ ] Test composition validation

---

## Documentation Checklist

- [ ] Architecture docs updated (panel mechanics)
- [ ] Panel composition rules documented
- [ ] Remedy types documented
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Why ≥3 Members?**
```
Single person decisions are problematic:
  - No check on individual bias
  - No deliberation required
  - No dissent possible
  - Single point of failure

Two person panels:
  - Deadlock possible
  - Still limited perspective

Three or more:
  - Deliberation required
  - Majority can decide
  - Dissent can be recorded
  - Multiple perspectives included
```

**Remedy Philosophy:**
```
Remedies are CORRECTIVE, not PUNITIVE:
  - WARNING: "This happened, don't repeat"
  - CORRECTION: "Change this specific thing"
  - ESCALATION: "This needs higher authority"
  - HALT_RECOMMENDATION: "System should stop"

Explicitly NOT available:
  - Reputation penalties
  - Access restrictions
  - Punitive measures
  - Permanent marks

Why?
  - Consent-based system respects dignity
  - Refusal is penalty-free (Golden Rule)
  - Correction addresses problem
  - Punishment creates fear → coercion
```

**Dissent Preservation:**
```
FR39: Panel can record dissent in finding

Dissent is NOT:
  - Overruled
  - Suppressed
  - Hidden

Dissent IS:
  - Recorded alongside finding
  - Visible to observers
  - Part of official record
  - Valuable for appeals/review

Example Finding:
{
  "determination": "violation",
  "remedy": "correction",
  "majority_rationale": "...",
  "dissent": {
    "member_ids": ["uuid1"],
    "rationale": "I disagree because..."
  }
}
```

### Domain Models

```python
class PanelStatus(Enum):
    """Status of a Prince Panel."""
    CONVENED = "convened"           # Panel formed
    REVIEWING = "reviewing"         # Reviewing artifacts
    DELIBERATING = "deliberating"   # Members deliberating
    FINDING_ISSUED = "finding_issued"  # Finding complete
    DISBANDED = "disbanded"         # Panel ended


class MemberStatus(Enum):
    """Status of panel member."""
    ACTIVE = "active"
    RECUSED = "recused"


@dataclass(frozen=True)
class PanelMember:
    """Member of a Prince Panel."""
    member_id: UUID
    joined_at: datetime
    status: MemberStatus
    recusal_reason: str | None  # If recused


class RemedyType(Enum):
    """Type of remedy panel can issue."""
    WARNING = "warning"                    # Formal notice
    CORRECTION = "correction"              # Require action change
    ESCALATION = "escalation"              # Route to higher authority
    HALT_RECOMMENDATION = "halt_recommendation"  # Recommend halt

    # Explicitly NOT available (dignity preservation):
    # - REPUTATION_PENALTY
    # - ACCESS_RESTRICTION
    # - PUNITIVE_FINE


@dataclass(frozen=True)
class Determination(Enum):
    """Panel determination."""
    VIOLATION_FOUND = "violation_found"
    NO_VIOLATION = "no_violation"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class Dissent:
    """Minority dissent in finding."""
    dissenting_member_ids: list[UUID]
    rationale: str


@dataclass(frozen=True)
class PanelFinding:
    """Formal finding from Prince Panel."""
    finding_id: UUID
    panel_id: UUID
    statement_id: UUID  # Witness statement being reviewed
    determination: Determination
    remedy: RemedyType | None  # None if no violation
    majority_rationale: str
    dissent: Dissent | None  # None if unanimous
    issued_at: datetime
    voting_record: dict[UUID, str]  # member_id → vote


@dataclass(frozen=True)
class PrincePanel:
    """Prince Panel for judicial review.

    Requires ≥3 active members to issue findings.
    """
    panel_id: UUID
    convened_by: UUID  # Human Operator
    members: tuple[PanelMember, ...]  # Immutable tuple
    statement_under_review: UUID
    status: PanelStatus
    convened_at: datetime
    finding: PanelFinding | None

    def __post_init__(self):
        """Validate panel composition."""
        active_count = sum(
            1 for m in self.members
            if m.status == MemberStatus.ACTIVE
        )
        if active_count < 3:
            raise InvalidPanelComposition(
                f"Panel requires ≥3 active members, has {active_count}"
            )

    @property
    def active_members(self) -> list[PanelMember]:
        """Get active (non-recused) members."""
        return [m for m in self.members if m.status == MemberStatus.ACTIVE]

    @property
    def quorum(self) -> int:
        """Quorum is majority of active members."""
        return (len(self.active_members) // 2) + 1

    def can_issue_finding(self) -> bool:
        """Check if panel can issue finding."""
        return (
            len(self.active_members) >= 3 and
            self.status in [PanelStatus.REVIEWING, PanelStatus.DELIBERATING]
        )


class InvalidPanelComposition(ValueError):
    """Raised when panel composition is invalid."""
    pass
```

### Service Implementation Sketch

```python
class PrincePanelService:
    """Orchestrates Prince Panel workflow."""

    def __init__(
        self,
        panel_port: PanelPort,
        witness_port: WitnessPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._panels = panel_port
        self._witness = witness_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def convene_panel(
        self,
        convener_id: UUID,
        statement_id: UUID,
        member_ids: list[UUID],
    ) -> PrincePanel:
        """Convene a new panel for statement review.

        Requires ≥3 members.
        """
        now = self._time.now()

        members = tuple(
            PanelMember(
                member_id=mid,
                joined_at=now,
                status=MemberStatus.ACTIVE,
                recusal_reason=None,
            )
            for mid in member_ids
        )

        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=convener_id,
            members=members,
            statement_under_review=statement_id,
            status=PanelStatus.CONVENED,
            convened_at=now,
            finding=None,
        )

        await self._panels.save_panel(panel)

        await self._event_emitter.emit(
            event_type="judicial.panel.convened",
            actor=str(convener_id),
            payload={
                "panel_id": str(panel.panel_id),
                "statement_id": str(statement_id),
                "member_count": len(members),
                "convened_at": now.isoformat(),
            },
        )

        return panel

    async def record_recusal(
        self,
        panel_id: UUID,
        member_id: UUID,
        reason: str,
    ) -> PrincePanel:
        """Record member recusal from panel."""
        panel = await self._panels.get_panel(panel_id)

        # Update member status
        new_members = []
        for member in panel.members:
            if member.member_id == member_id:
                new_members.append(
                    PanelMember(
                        member_id=member.member_id,
                        joined_at=member.joined_at,
                        status=MemberStatus.RECUSED,
                        recusal_reason=reason,
                    )
                )
            else:
                new_members.append(member)

        # Validate still has quorum
        active_count = sum(
            1 for m in new_members
            if m.status == MemberStatus.ACTIVE
        )

        if active_count < 3:
            raise InvalidPanelComposition(
                f"Recusal would leave {active_count} active members (<3)"
            )

        updated_panel = PrincePanel(
            panel_id=panel.panel_id,
            convened_by=panel.convened_by,
            members=tuple(new_members),
            statement_under_review=panel.statement_under_review,
            status=panel.status,
            convened_at=panel.convened_at,
            finding=panel.finding,
        )

        await self._panels.save_panel(updated_panel)

        await self._event_emitter.emit(
            event_type="judicial.panel.member_recused",
            actor=str(member_id),
            payload={
                "panel_id": str(panel_id),
                "member_id": str(member_id),
                "reason": reason,
                "remaining_active": active_count,
            },
        )

        return updated_panel

    async def issue_finding(
        self,
        panel_id: UUID,
        determination: Determination,
        remedy: RemedyType | None,
        majority_rationale: str,
        voting_record: dict[UUID, str],
        dissent: Dissent | None = None,
    ) -> PanelFinding:
        """Issue formal finding from panel."""
        panel = await self._panels.get_panel(panel_id)

        if not panel.can_issue_finding():
            raise InvalidPanelComposition(
                "Panel cannot issue finding in current state"
            )

        now = self._time.now()

        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=panel_id,
            statement_id=panel.statement_under_review,
            determination=determination,
            remedy=remedy,
            majority_rationale=majority_rationale,
            dissent=dissent,
            issued_at=now,
            voting_record=voting_record,
        )

        # Update panel with finding
        updated_panel = PrincePanel(
            panel_id=panel.panel_id,
            convened_by=panel.convened_by,
            members=panel.members,
            statement_under_review=panel.statement_under_review,
            status=PanelStatus.FINDING_ISSUED,
            convened_at=panel.convened_at,
            finding=finding,
        )

        await self._panels.save_panel(updated_panel)

        await self._event_emitter.emit(
            event_type="judicial.panel.finding_issued",
            actor="panel",
            payload={
                "finding_id": str(finding.finding_id),
                "panel_id": str(panel_id),
                "determination": determination.value,
                "remedy": remedy.value if remedy else None,
                "has_dissent": dissent is not None,
                "issued_at": now.isoformat(),
            },
        )

        return finding
```

### Test Patterns

```python
class TestPrincePanel:
    """Unit tests for Prince Panel domain model."""

    def test_panel_requires_minimum_three_members(self):
        """Panel must have ≥3 members."""
        with pytest.raises(InvalidPanelComposition):
            PrincePanel(
                panel_id=uuid4(),
                convened_by=uuid4(),
                members=(create_member(), create_member()),  # Only 2
                statement_under_review=uuid4(),
                status=PanelStatus.CONVENED,
                convened_at=datetime.now(UTC),
                finding=None,
            )

    def test_panel_allows_three_or_more_members(self):
        """Panel accepts ≥3 members."""
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=(create_member(), create_member(), create_member()),
            statement_under_review=uuid4(),
            status=PanelStatus.CONVENED,
            convened_at=datetime.now(UTC),
            finding=None,
        )

        assert len(panel.members) == 3

    def test_quorum_is_majority(self):
        """Quorum is majority of active members."""
        members = tuple(create_member() for _ in range(5))
        panel = create_panel(members=members)

        assert panel.quorum == 3  # Majority of 5


class TestPanelFinding:
    """Unit tests for panel finding."""

    def test_finding_can_include_dissent(self):
        """Findings can include dissent."""
        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            determination=Determination.VIOLATION_FOUND,
            remedy=RemedyType.CORRECTION,
            majority_rationale="Majority believes...",
            dissent=Dissent(
                dissenting_member_ids=[uuid4()],
                rationale="I disagree because...",
            ),
            issued_at=datetime.now(UTC),
            voting_record={uuid4(): "violation", uuid4(): "violation", uuid4(): "no_violation"},
        )

        assert finding.dissent is not None
        assert len(finding.dissent.dissenting_member_ids) == 1

    def test_finding_remedy_only_if_violation(self):
        """Remedy is only set if violation found."""
        # No violation = no remedy
        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            determination=Determination.NO_VIOLATION,
            remedy=None,  # No remedy needed
            majority_rationale="No violation found",
            dissent=None,
            issued_at=datetime.now(UTC),
            voting_record={},
        )

        assert finding.remedy is None


class TestRecusal:
    """Unit tests for recusal mechanics."""

    async def test_recusal_updates_member_status(
        self,
        panel_service: PrincePanelService,
        panel: PrincePanel,
    ):
        """Recusal changes member status."""
        member_id = panel.members[0].member_id

        updated = await panel_service.record_recusal(
            panel_id=panel.panel_id,
            member_id=member_id,
            reason="Conflict of interest",
        )

        recused_member = next(
            m for m in updated.members
            if m.member_id == member_id
        )
        assert recused_member.status == MemberStatus.RECUSED

    async def test_recusal_fails_if_below_quorum(
        self,
        panel_service: PrincePanelService,
    ):
        """Recusal fails if it would leave <3 active members."""
        panel = await panel_service.convene_panel(
            convener_id=uuid4(),
            statement_id=uuid4(),
            member_ids=[uuid4(), uuid4(), uuid4()],  # Exactly 3
        )

        with pytest.raises(InvalidPanelComposition):
            await panel_service.record_recusal(
                panel_id=panel.panel_id,
                member_id=panel.members[0].member_id,
                reason="Would break quorum",
            )
```

### Dependencies

- **Depends on:** consent-gov-6-3 (statement routing)
- **Enables:** consent-gov-6-5 (finding preservation)

### References

- FR36: Human Operator can convene panel (≥3 members)
- FR37: Prince Panel can review witness artifacts
- FR38: Prince Panel can issue formal finding with remedy
- FR39: Prince Panel can record dissent in finding
