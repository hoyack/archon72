# Story consent-gov-6.5: Panel Finding Preservation

Status: done

---

## Story

As an **auditor**,
I want **panel findings preserved immutably**,
So that **judicial outcomes cannot be altered**.

---

## Acceptance Criteria

1. **AC1:** Findings recorded in append-only ledger (FR40)
2. **AC2:** Findings cannot be deleted or modified (NFR-CONST-06)
3. **AC3:** Dissent preserved alongside majority finding
4. **AC4:** Event `judicial.panel.finding_issued` emitted
5. **AC5:** Finding includes complete voting record
6. **AC6:** Finding links to witness statement reviewed
7. **AC7:** Historical findings queryable
8. **AC8:** Unit tests for immutability

---

## Tasks / Subtasks

- [x] **Task 1: Create PanelFindingPort interface** (AC: 1, 2)
  - [x] Create `src/application/ports/governance/panel_finding_port.py`
  - [x] Define `record_finding()` method
  - [x] Define `get_finding()` method
  - [x] NO `delete_finding()` method (NFR-CONST-06)
  - [x] NO `modify_finding()` method

- [x] **Task 2: Implement finding persistence** (AC: 1)
  - [x] Store finding in append-only ledger
  - [x] Include all finding fields
  - [x] Include hash for integrity
  - [x] Record timestamp from TimeAuthority

- [x] **Task 3: Implement immutability enforcement** (AC: 2)
  - [x] No API endpoint for deletion
  - [x] No API endpoint for modification
  - [x] Port interface has no delete/modify methods
  - [x] FindingRecord is frozen dataclass

- [x] **Task 4: Implement dissent preservation** (AC: 3)
  - [x] Dissent stored with finding (not separate)
  - [x] Dissent visible in all queries
  - [x] Dissent cannot be removed later
  - [x] Multiple dissenters supported

- [x] **Task 5: Implement finding event emission** (AC: 4)
  - [x] Emit `judicial.panel.finding_issued`
  - [x] Include finding_id, determination, remedy
  - [x] Include has_dissent flag
  - [x] Emit `judicial.panel.dissent_recorded` when dissent exists

- [x] **Task 6: Implement voting record preservation** (AC: 5)
  - [x] Record each member's vote
  - [x] Votes linked to member IDs
  - [x] Voting record count in event
  - [x] Vote record preserved in finding

- [x] **Task 7: Implement statement linkage** (AC: 6)
  - [x] Finding references witness statement
  - [x] get_findings_for_statement query
  - [x] Bi-directional query supported
  - [x] Link is immutable

- [x] **Task 8: Implement historical query** (AC: 7)
  - [x] Query findings by date range
  - [x] Query findings by panel
  - [x] Query findings by determination
  - [x] Query findings by statement

- [x] **Task 9: Write comprehensive unit tests** (AC: 8)
  - [x] Test finding recorded to ledger
  - [x] Test no deletion possible
  - [x] Test no modification possible
  - [x] Test dissent preserved
  - [x] Test event emitted
  - [x] Test historical query

---

## Documentation Checklist

- [ ] Architecture docs updated (finding preservation)
- [ ] Immutability guarantees documented
- [ ] Query capabilities documented
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Why Immutable Findings?**
```
NFR-CONST-06: Findings cannot be deleted or modified

Judicial outcomes must be permanent because:
  - Accountability requires permanence
  - Historical record must be complete
  - Appeal requires original finding
  - Trust requires no revisions

If findings could be changed:
  - Panel could "clean up" unpopular decisions
  - Accountability could be erased
  - Historical analysis impossible
  - Trust in process destroyed
```

**Dissent as First-Class Citizen:**
```
Dissent is NOT:
  - An appendix
  - A footnote
  - Optional metadata

Dissent IS:
  - Part of the finding itself
  - Always visible
  - Equally preserved
  - Valuable signal

Why?
  - Close decisions documented
  - Future panels see precedent
  - Minority view may later be vindicated
  - Transparency about deliberation quality
```

**Complete Voting Record:**
```
Record includes:
  - Each member's vote
  - Vote timestamp
  - Member status at vote time
  - Recusal notes

Why full record?
  - Quorum verification
  - Pattern analysis
  - Member accountability
  - Process transparency
```

### Domain Models

```python
@dataclass(frozen=True)
class FindingRecord:
    """Immutable record of panel finding.

    Once created, cannot be modified or deleted.
    """
    record_id: UUID
    finding: PanelFinding
    recorded_at: datetime
    ledger_position: int
    hash: str  # Integrity hash

    # Computed for queries
    @property
    def statement_id(self) -> UUID:
        return self.finding.statement_id

    @property
    def determination(self) -> Determination:
        return self.finding.determination

    @property
    def has_dissent(self) -> bool:
        return self.finding.dissent is not None


@dataclass(frozen=True)
class VoteRecord:
    """Individual vote in panel deliberation."""
    member_id: UUID
    vote: str  # "violation", "no_violation", "insufficient_evidence"
    voted_at: datetime
    rationale: str | None


@dataclass(frozen=True)
class DissentRecord:
    """Preserved dissent in finding."""
    dissenting_members: list[UUID]
    rationale: str
    recorded_at: datetime
```

### Port Interface

```python
class PanelFindingPort(Protocol):
    """Port for panel finding operations.

    Intentionally NO delete or modify methods (NFR-CONST-06).
    """

    async def record_finding(
        self,
        finding: PanelFinding,
    ) -> FindingRecord:
        """Record finding to append-only ledger.

        Once recorded, finding cannot be deleted or modified.
        """
        ...

    async def get_finding(
        self,
        finding_id: UUID,
    ) -> FindingRecord | None:
        """Get finding by ID."""
        ...

    async def get_findings_for_statement(
        self,
        statement_id: UUID,
    ) -> list[FindingRecord]:
        """Get all findings for a witness statement."""
        ...

    async def get_findings_by_determination(
        self,
        determination: Determination,
        since: datetime | None = None,
    ) -> list[FindingRecord]:
        """Get findings by determination type."""
        ...

    async def get_findings_by_panel(
        self,
        panel_id: UUID,
    ) -> list[FindingRecord]:
        """Get all findings from a panel."""
        ...

    async def get_findings_in_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[FindingRecord]:
        """Get findings in date range."""
        ...

    # Intentionally NOT defined (NFR-CONST-06):
    # - delete_finding()
    # - modify_finding()
    # - update_finding()
    # - remove_finding()
```

### Service Implementation Sketch

```python
class PanelFindingService:
    """Service for preserving panel findings."""

    def __init__(
        self,
        finding_port: PanelFindingPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._findings = finding_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def preserve_finding(
        self,
        finding: PanelFinding,
    ) -> FindingRecord:
        """Preserve finding in append-only ledger.

        Finding becomes immutable upon preservation.
        """
        now = self._time.now()

        # Create record
        record = await self._findings.record_finding(finding)

        # Emit event
        await self._event_emitter.emit(
            event_type="judicial.panel.finding_issued",
            actor="panel",
            payload={
                "finding_id": str(finding.finding_id),
                "panel_id": str(finding.panel_id),
                "statement_id": str(finding.statement_id),
                "determination": finding.determination.value,
                "remedy": finding.remedy.value if finding.remedy else None,
                "has_dissent": finding.dissent is not None,
                "dissenting_count": (
                    len(finding.dissent.dissenting_member_ids)
                    if finding.dissent else 0
                ),
                "issued_at": finding.issued_at.isoformat(),
                "recorded_at": now.isoformat(),
                "ledger_position": record.ledger_position,
            },
        )

        # Emit dissent event if present
        if finding.dissent:
            await self._event_emitter.emit(
                event_type="judicial.panel.dissent_recorded",
                actor="panel",
                payload={
                    "finding_id": str(finding.finding_id),
                    "dissenting_members": [
                        str(m) for m in finding.dissent.dissenting_member_ids
                    ],
                    "rationale_length": len(finding.dissent.rationale),
                },
            )

        return record

    async def get_findings_with_dissent(
        self,
        since: datetime | None = None,
    ) -> list[FindingRecord]:
        """Get all findings that have dissent recorded."""
        all_findings = await self._findings.get_findings_in_range(
            start=since or datetime.min,
            end=self._time.now(),
        )

        return [f for f in all_findings if f.has_dissent]
```

### Adapter Implementation Sketch

```python
class PanelFindingAdapter:
    """Adapter for panel finding persistence.

    Implements append-only semantics.
    """

    def __init__(
        self,
        ledger: AppendOnlyLedger,
        time_authority: TimeAuthority,
    ):
        self._ledger = ledger
        self._time = time_authority

    async def record_finding(
        self,
        finding: PanelFinding,
    ) -> FindingRecord:
        """Record finding to ledger (append-only)."""
        now = self._time.now()

        # Serialize finding
        finding_data = {
            "finding_id": str(finding.finding_id),
            "panel_id": str(finding.panel_id),
            "statement_id": str(finding.statement_id),
            "determination": finding.determination.value,
            "remedy": finding.remedy.value if finding.remedy else None,
            "majority_rationale": finding.majority_rationale,
            "dissent": (
                {
                    "members": [str(m) for m in finding.dissent.dissenting_member_ids],
                    "rationale": finding.dissent.rationale,
                }
                if finding.dissent else None
            ),
            "voting_record": {
                str(k): v for k, v in finding.voting_record.items()
            },
            "issued_at": finding.issued_at.isoformat(),
        }

        # Compute integrity hash
        content_hash = hashlib.sha256(
            json.dumps(finding_data, sort_keys=True).encode()
        ).hexdigest()

        # Append to ledger (immutable)
        position = await self._ledger.append(
            event_type="judicial.finding",
            data=finding_data,
            hash=content_hash,
        )

        return FindingRecord(
            record_id=uuid4(),
            finding=finding,
            recorded_at=now,
            ledger_position=position,
            hash=content_hash,
        )

    # These methods intentionally do not exist:
    # async def delete_finding(self, ...): ...
    # async def modify_finding(self, ...): ...
```

### Event Patterns

```python
# Finding issued event
{
    "event_type": "judicial.panel.finding_issued",
    "actor": "panel",
    "payload": {
        "finding_id": "uuid",
        "panel_id": "uuid",
        "statement_id": "uuid",
        "determination": "violation_found",
        "remedy": "correction",
        "has_dissent": true,
        "dissenting_count": 1,
        "issued_at": "2026-01-16T00:00:00Z",
        "recorded_at": "2026-01-16T00:00:01Z",
        "ledger_position": 5678
    }
}

# Dissent recorded event
{
    "event_type": "judicial.panel.dissent_recorded",
    "actor": "panel",
    "payload": {
        "finding_id": "uuid",
        "dissenting_members": ["member-uuid"],
        "rationale_length": 250
    }
}
```

### Test Patterns

```python
class TestPanelFindingPort:
    """Unit tests for finding port interface."""

    def test_no_delete_method(self):
        """Port has no delete method (NFR-CONST-06)."""
        assert not hasattr(PanelFindingPort, "delete_finding")

    def test_no_modify_method(self):
        """Port has no modify method (NFR-CONST-06)."""
        assert not hasattr(PanelFindingPort, "modify_finding")
        assert not hasattr(PanelFindingPort, "update_finding")


class TestPanelFindingService:
    """Unit tests for finding preservation."""

    async def test_finding_recorded_to_ledger(
        self,
        finding_service: PanelFindingService,
        finding_port: FakePanelFindingPort,
        finding: PanelFinding,
    ):
        """Findings are recorded to ledger."""
        record = await finding_service.preserve_finding(finding)

        assert record.ledger_position > 0
        assert record.finding == finding

    async def test_dissent_preserved(
        self,
        finding_service: PanelFindingService,
        finding_with_dissent: PanelFinding,
    ):
        """Dissent is preserved with finding."""
        record = await finding_service.preserve_finding(finding_with_dissent)

        assert record.finding.dissent is not None
        assert len(record.finding.dissent.dissenting_member_ids) > 0

    async def test_finding_event_emitted(
        self,
        finding_service: PanelFindingService,
        finding: PanelFinding,
        event_capture: EventCapture,
    ):
        """Finding issued event is emitted."""
        await finding_service.preserve_finding(finding)

        event = event_capture.get_last("judicial.panel.finding_issued")
        assert event is not None
        assert event.payload["finding_id"] == str(finding.finding_id)

    async def test_dissent_event_emitted(
        self,
        finding_service: PanelFindingService,
        finding_with_dissent: PanelFinding,
        event_capture: EventCapture,
    ):
        """Dissent recorded event is emitted when dissent exists."""
        await finding_service.preserve_finding(finding_with_dissent)

        event = event_capture.get_last("judicial.panel.dissent_recorded")
        assert event is not None

    async def test_voting_record_preserved(
        self,
        finding_service: PanelFindingService,
        finding: PanelFinding,
    ):
        """Complete voting record is preserved."""
        record = await finding_service.preserve_finding(finding)

        assert len(record.finding.voting_record) > 0

    async def test_statement_linkage(
        self,
        finding_service: PanelFindingService,
        finding_port: FakePanelFindingPort,
        finding: PanelFinding,
    ):
        """Finding links to witness statement."""
        await finding_service.preserve_finding(finding)

        retrieved = await finding_port.get_findings_for_statement(
            finding.statement_id
        )

        assert len(retrieved) == 1
        assert retrieved[0].finding.finding_id == finding.finding_id


class TestFindingImmutability:
    """Integration tests for finding immutability."""

    async def test_cannot_delete_via_direct_access(
        self,
        db_session,
        finding_record: FindingRecord,
    ):
        """Database prevents deletion of findings."""
        with pytest.raises(DatabaseError):
            await db_session.execute(
                "DELETE FROM panel_findings WHERE finding_id = :id",
                {"id": str(finding_record.finding.finding_id)},
            )

    async def test_cannot_update_via_direct_access(
        self,
        db_session,
        finding_record: FindingRecord,
    ):
        """Database prevents updating findings."""
        with pytest.raises(DatabaseError):
            await db_session.execute(
                "UPDATE panel_findings SET determination = 'changed' WHERE finding_id = :id",
                {"id": str(finding_record.finding.finding_id)},
            )

    async def test_historical_query_returns_all(
        self,
        finding_service: PanelFindingService,
        finding_port: FakePanelFindingPort,
    ):
        """Historical query returns all findings in range."""
        # Create multiple findings
        for i in range(5):
            await finding_service.preserve_finding(
                create_finding(determination=Determination.VIOLATION_FOUND if i % 2 == 0 else Determination.NO_VIOLATION)
            )

        findings = await finding_port.get_findings_in_range(
            start=datetime.min,
            end=datetime.max,
        )

        assert len(findings) == 5
```

### Dependencies

- **Depends on:** consent-gov-6-4 (panel domain model)
- **Enables:** Complete judicial workflow

### References

- FR40: System can record all panel findings in append-only ledger
- NFR-CONST-06: Panel findings cannot be deleted or modified
- FR39: Prince Panel can record dissent in finding
