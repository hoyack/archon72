# Story consent-gov-7.3: Contribution Preservation

Status: done

---

## Story

As a **Cluster**,
I want **my contribution history preserved on exit**,
So that **my work remains attributed even after I leave**.

---

## Acceptance Criteria

1. **AC1:** Contribution history preserved (FR45) ✅
2. **AC2:** History remains in ledger (immutable) ✅
3. **AC3:** Attribution maintained without PII ✅
4. **AC4:** Completed work attributed to Cluster ID ✅
5. **AC5:** Event `custodial.contributions.preserved` emitted ✅
6. **AC6:** Historical queries show preserved contributions ✅
7. **AC7:** No scrubbing of historical events ✅
8. **AC8:** Unit tests for preservation ✅

---

## Tasks / Subtasks

- [x] **Task 1: Create ContributionPreservationService** (AC: 1, 2)
  - [x] Create `src/application/services/governance/contribution_preservation_service.py`
  - [x] Preserve contribution records on exit
  - [x] Link to immutable ledger events
  - [x] No deletion or modification

- [x] **Task 2: Implement preservation logic** (AC: 1, 7)
  - [x] Mark contributions as preserved (flag only)
  - [x] Do NOT delete any events
  - [x] Do NOT modify any events
  - [x] Historical integrity maintained

- [x] **Task 3: Implement PII-free attribution** (AC: 3, 4)
  - [x] Attribution uses Cluster ID (UUID)
  - [x] No personal names stored
  - [x] No email addresses stored
  - [x] No contact information stored

- [x] **Task 4: Implement preservation event** (AC: 5)
  - [x] Emit `custodial.contributions.preserved`
  - [x] Include contribution count
  - [x] Include task IDs preserved
  - [x] Knight observes preservation

- [x] **Task 5: Implement historical query support** (AC: 6)
  - [x] Contributions queryable by Cluster ID
  - [x] Query returns preserved contributions
  - [x] Works same as before exit
  - [x] No access restriction after exit

- [x] **Task 6: Ensure no scrubbing** (AC: 7)
  - [x] No "delete my data" for contributions
  - [x] Ledger immutability enforced
  - [x] Constitutional constraint
  - [x] Audit trail preserved

- [x] **Task 7: Create ContributionRecord model** (AC: 1, 4)
  - [x] Include cluster_id, task_id, contribution_type
  - [x] Include contributed_at, preserved_at
  - [x] Include result_hash (for verification)
  - [x] Immutable value object

- [x] **Task 8: Write comprehensive unit tests** (AC: 8)
  - [x] Test contributions preserved on exit
  - [x] Test ledger immutability
  - [x] Test PII-free attribution
  - [x] Test historical queries work
  - [x] Test no scrubbing possible

---

## Documentation Checklist

- [x] Architecture docs updated (preservation) - In code docstrings
- [x] PII constraints documented - In ContributionRecord structural absence comments
- [x] Immutability guarantees documented - In PreservationResult and ContributionPort structural absence comments
- [x] N/A - README (internal component)

---

## Implementation Summary

### Files Created

**Domain Models:**
- `src/domain/governance/exit/contribution_type.py` - ContributionType enum
- `src/domain/governance/exit/contribution_record.py` - ContributionRecord frozen dataclass
- `src/domain/governance/exit/preservation_result.py` - PreservationResult frozen dataclass

**Ports:**
- `src/application/ports/governance/contribution_port.py` - ContributionPort protocol

**Services:**
- `src/application/services/governance/contribution_preservation_service.py` - ContributionPreservationService

**Tests:**
- `tests/unit/domain/governance/exit/test_contribution_preservation.py` - 39 domain model tests
- `tests/unit/application/ports/governance/test_contribution_port.py` - 16 port tests
- `tests/unit/application/services/governance/test_contribution_preservation_service.py` - 33 service tests

### Test Results

**88 unit tests passing:**
- ContributionType enum tests (5)
- ContributionRecord validation tests (14)
- ContributionRecord PII-free tests (6)
- PreservationResult validation tests (11)
- PreservationResult no-scrubbing tests (3)
- ContributionPort protocol tests (16)
- ContributionPreservationService tests (33)

### Key Features

1. **Immutable Domain Models:** All models are frozen dataclasses with validation
2. **PII-Free Attribution:** Uses UUIDs only - no cluster_name, cluster_email, etc.
3. **No Scrubbing:** ContributionPort and ContributionPreservationService have no delete/scrub/modify methods (structural absence)
4. **Event Emission:** `custodial.contributions.preserved` event emitted with cluster_id, contribution count, task_ids
5. **Historical Queries:** get_for_cluster() and get_preserved() work same before and after exit

---

## Dev Notes

### Key Architectural Decisions

**Why Preserve Contributions?**
```
Cluster's work has value:
  - Results may be used by system
  - Attribution respects effort
  - Audit requires history
  - Completeness is constitutional

Without preservation:
  - Work could "disappear"
  - Attribution lost
  - Audit trail broken
  - Dignity violated
```

**PII-Free Attribution:**
```
NFR-INT-02: Public data only, no PII

Attribution uses:
  ✓ Cluster ID (UUID)
  ✓ Task ID (UUID)
  ✓ Timestamps
  ✓ Result hashes

Attribution does NOT use:
  ✗ Personal names
  ✗ Email addresses
  ✗ Phone numbers
  ✗ Any identifying information

Why?
  - Public ledger requirement
  - Privacy by design
  - No "right to be forgotten" conflict
  - Pseudonymous attribution
```

**No Scrubbing:**
```
Constitutional constraint:
  - Ledger is append-only
  - Events cannot be deleted
  - Contributions are events
  - Therefore: no scrubbing

"Delete my data" applies to:
  ✗ Contribution records (immutable)
  ✓ Contact information (blocked on exit)
  ✓ Credentials (revoked on exit)

This is by design:
  - Audit requires completeness
  - History cannot be rewritten
  - Trust requires immutability
```

### Domain Models

```python
class ContributionType(Enum):
    """Type of contribution."""
    TASK_COMPLETED = "task_completed"
    TASK_REPORTED = "task_reported"
    DELIBERATION_PARTICIPATED = "deliberation_participated"


@dataclass(frozen=True)
class ContributionRecord:
    """Record of Cluster contribution.

    Attribution is PII-free (UUIDs only).
    Cannot be deleted or modified (immutable ledger).
    """
    record_id: UUID
    cluster_id: UUID  # Pseudonymous attribution
    task_id: UUID
    contribution_type: ContributionType
    contributed_at: datetime
    preserved_at: datetime | None  # Set on exit
    result_hash: str  # For verification

    # Explicitly NOT included (PII):
    # - cluster_name: str
    # - cluster_email: str
    # - cluster_contact: str


@dataclass(frozen=True)
class PreservationResult:
    """Result of contribution preservation."""
    cluster_id: UUID
    contributions_preserved: int
    task_ids: list[UUID]
    preserved_at: datetime
```

### Service Implementation Sketch

```python
class ContributionPreservationService:
    """Preserves contributions on Cluster exit.

    Does NOT delete or modify any records.
    Attribution is PII-free.
    """

    def __init__(
        self,
        contribution_port: ContributionPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._contributions = contribution_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def preserve(
        self,
        cluster_id: UUID,
    ) -> PreservationResult:
        """Preserve contributions for exiting Cluster.

        Marks contributions as preserved (flag only).
        Does NOT delete anything.
        """
        now = self._time.now()

        # Get all contributions for Cluster
        contributions = await self._contributions.get_for_cluster(cluster_id)

        # Mark as preserved (add preservation timestamp)
        preserved_ids = []
        for contribution in contributions:
            await self._contributions.mark_preserved(
                record_id=contribution.record_id,
                preserved_at=now,
            )
            preserved_ids.append(contribution.task_id)

        # Emit preservation event
        await self._event_emitter.emit(
            event_type="custodial.contributions.preserved",
            actor="system",
            payload={
                "cluster_id": str(cluster_id),
                "contributions_preserved": len(contributions),
                "task_ids": [str(t) for t in preserved_ids],
                "preserved_at": now.isoformat(),
            },
        )

        return PreservationResult(
            cluster_id=cluster_id,
            contributions_preserved=len(contributions),
            task_ids=preserved_ids,
            preserved_at=now,
        )

    # These methods intentionally do not exist:
    # async def delete_contributions(self, ...): ...
    # async def scrub_history(self, ...): ...
    # async def remove_attribution(self, ...): ...


class ContributionPort(Protocol):
    """Port for contribution operations.

    NO delete methods (immutability).
    """

    async def get_for_cluster(
        self,
        cluster_id: UUID,
    ) -> list[ContributionRecord]:
        """Get all contributions for a Cluster."""
        ...

    async def mark_preserved(
        self,
        record_id: UUID,
        preserved_at: datetime,
    ) -> None:
        """Mark contribution as preserved (flag only, no deletion)."""
        ...

    async def get_preserved(
        self,
        cluster_id: UUID,
    ) -> list[ContributionRecord]:
        """Get preserved contributions (historical query)."""
        ...

    # Intentionally NOT defined:
    # - delete_contribution()
    # - scrub_contribution()
    # - remove_contribution()
```

### Event Pattern

```python
# Contributions preserved
{
    "event_type": "custodial.contributions.preserved",
    "actor": "system",
    "payload": {
        "cluster_id": "uuid",
        "contributions_preserved": 5,
        "task_ids": ["uuid1", "uuid2", "uuid3", "uuid4", "uuid5"],
        "preserved_at": "2026-01-16T00:00:00Z"
    }
}
```

### Test Patterns

```python
class TestContributionPreservationService:
    """Unit tests for contribution preservation."""

    async def test_contributions_preserved_on_exit(
        self,
        preservation_service: ContributionPreservationService,
        cluster_with_contributions: Cluster,
        contribution_port: FakeContributionPort,
    ):
        """Contributions are preserved on exit."""
        result = await preservation_service.preserve(
            cluster_id=cluster_with_contributions.id,
        )

        assert result.contributions_preserved > 0

        # Verify preserved flag set
        contributions = await contribution_port.get_preserved(
            cluster_with_contributions.id
        )
        for c in contributions:
            assert c.preserved_at is not None

    async def test_ledger_immutability(
        self,
        preservation_service: ContributionPreservationService,
        cluster_with_contributions: Cluster,
        contribution_port: FakeContributionPort,
    ):
        """Contributions remain in ledger after preservation."""
        # Get count before
        before = await contribution_port.get_for_cluster(
            cluster_with_contributions.id
        )

        await preservation_service.preserve(
            cluster_id=cluster_with_contributions.id,
        )

        # Get count after
        after = await contribution_port.get_for_cluster(
            cluster_with_contributions.id
        )

        # Same count (nothing deleted)
        assert len(after) == len(before)

    async def test_pii_free_attribution(
        self,
        contribution_record: ContributionRecord,
    ):
        """Attribution uses UUIDs only, no PII."""
        # Check UUIDs are used
        assert isinstance(contribution_record.cluster_id, UUID)
        assert isinstance(contribution_record.task_id, UUID)

        # Check PII fields don't exist
        assert not hasattr(contribution_record, "cluster_name")
        assert not hasattr(contribution_record, "cluster_email")
        assert not hasattr(contribution_record, "cluster_contact")

    async def test_historical_query_works(
        self,
        preservation_service: ContributionPreservationService,
        cluster_with_contributions: Cluster,
        contribution_port: FakeContributionPort,
    ):
        """Historical queries return preserved contributions."""
        await preservation_service.preserve(
            cluster_id=cluster_with_contributions.id,
        )

        # Query by Cluster ID still works
        contributions = await contribution_port.get_for_cluster(
            cluster_with_contributions.id
        )

        assert len(contributions) > 0

    async def test_preservation_event_emitted(
        self,
        preservation_service: ContributionPreservationService,
        cluster_with_contributions: Cluster,
        event_capture: EventCapture,
    ):
        """Preservation event is emitted."""
        await preservation_service.preserve(
            cluster_id=cluster_with_contributions.id,
        )

        event = event_capture.get_last("custodial.contributions.preserved")
        assert event is not None


class TestNoScrubbing:
    """Tests ensuring no scrubbing mechanisms exist."""

    def test_no_delete_method(
        self,
        preservation_service: ContributionPreservationService,
    ):
        """No delete method exists."""
        assert not hasattr(preservation_service, "delete_contributions")
        assert not hasattr(preservation_service, "remove_contributions")

    def test_no_scrub_method(
        self,
        preservation_service: ContributionPreservationService,
    ):
        """No scrub method exists."""
        assert not hasattr(preservation_service, "scrub_history")
        assert not hasattr(preservation_service, "scrub_contributions")

    def test_port_has_no_delete(self):
        """Contribution port has no delete method."""
        assert not hasattr(ContributionPort, "delete_contribution")
        assert not hasattr(ContributionPort, "scrub_contribution")
```

### Dependencies

- **Depends on:** consent-gov-7-2 (obligation release)
- **Enables:** consent-gov-7-4 (contact prevention)

### References

- FR45: System can preserve Cluster's contribution history on exit
- NFR-INT-02: Public data only, no PII
