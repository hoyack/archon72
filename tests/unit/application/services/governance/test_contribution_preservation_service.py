"""Unit tests for ContributionPreservationService.

Story: consent-gov-7.3: Contribution Preservation

Tests for:
- Contribution preservation on exit
- Event emission
- PII-free attribution
- No scrubbing enforcement
- Historical query support

Constitutional Truths Tested:
- FR45: Contribution history preserved on exit
- NFR-INT-02: Public data only, no PII
- AC1: Contribution history preserved
- AC2: History remains in ledger (immutable)
- AC5: Event `custodial.contributions.preserved` emitted
- AC6: Historical queries show preserved contributions
- AC7: No scrubbing of historical events
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.contribution_preservation_service import (
    CONTRIBUTIONS_PRESERVED_EVENT,
    ContributionPreservationService,
)
from src.domain.governance.exit.contribution_record import ContributionRecord
from src.domain.governance.exit.contribution_type import ContributionType
from src.domain.governance.exit.preservation_result import PreservationResult

# =============================================================================
# Test Doubles
# =============================================================================


class FakeTimeAuthority:
    """Fake time authority for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        """Initialize with optional fixed time."""
        self._time = fixed_time or datetime.now(timezone.utc)

    def now(self) -> datetime:
        """Get current timestamp."""
        return self._time

    def advance(self, seconds: int) -> None:
        """Advance time by seconds."""
        self._time = self._time + timedelta(seconds=seconds)


class FakeEventEmitter:
    """Fake event emitter for testing."""

    def __init__(self) -> None:
        """Initialize with empty event list."""
        self.events: list[dict] = []

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        """Emit an event."""
        self.events.append(
            {
                "event_type": event_type,
                "actor": actor,
                "payload": payload,
            }
        )

    def get_last(self, event_type: str) -> dict | None:
        """Get most recent event of type."""
        for event in reversed(self.events):
            if event["event_type"] == event_type:
                return event
        return None

    def count(self, event_type: str) -> int:
        """Count events of type."""
        return sum(1 for e in self.events if e["event_type"] == event_type)


class FakeContributionPort:
    """Fake contribution port for testing."""

    def __init__(self) -> None:
        """Initialize with empty contribution store."""
        self._contributions: dict[UUID, ContributionRecord] = {}

    async def get_for_cluster(
        self,
        cluster_id: UUID,
    ) -> list[ContributionRecord]:
        """Get all contributions for a Cluster."""
        return [c for c in self._contributions.values() if c.cluster_id == cluster_id]

    async def get_preserved(
        self,
        cluster_id: UUID,
    ) -> list[ContributionRecord]:
        """Get preserved contributions for a Cluster."""
        return [
            c
            for c in self._contributions.values()
            if c.cluster_id == cluster_id and c.preserved_at is not None
        ]

    async def mark_preserved(
        self,
        record_id: UUID,
        preserved_at: datetime,
    ) -> None:
        """Mark contribution as preserved."""
        if record_id in self._contributions:
            old = self._contributions[record_id]
            # Create new immutable record with preserved_at set
            self._contributions[record_id] = ContributionRecord(
                record_id=old.record_id,
                cluster_id=old.cluster_id,
                task_id=old.task_id,
                contribution_type=old.contribution_type,
                contributed_at=old.contributed_at,
                preserved_at=preserved_at,
                result_hash=old.result_hash,
            )

    async def record(
        self,
        contribution: ContributionRecord,
    ) -> None:
        """Record a new contribution."""
        self._contributions[contribution.record_id] = contribution

    async def get_by_id(
        self,
        record_id: UUID,
    ) -> ContributionRecord | None:
        """Get a contribution by its record ID."""
        return self._contributions.get(record_id)

    async def count_for_cluster(
        self,
        cluster_id: UUID,
    ) -> int:
        """Count contributions for a Cluster."""
        return len(await self.get_for_cluster(cluster_id))

    def add_contribution(
        self,
        cluster_id: UUID,
        task_id: UUID | None = None,
        contribution_type: ContributionType = ContributionType.TASK_COMPLETED,
        preserved: bool = False,
    ) -> ContributionRecord:
        """Helper to add a contribution."""
        now = datetime.now(timezone.utc)
        record = ContributionRecord(
            record_id=uuid4(),
            cluster_id=cluster_id,
            task_id=task_id or uuid4(),
            contribution_type=contribution_type,
            contributed_at=now,
            preserved_at=now if preserved else None,
            result_hash=f"hash_{uuid4().hex[:8]}",
        )
        self._contributions[record.record_id] = record
        return record


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Create fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    """Create fake event emitter."""
    return FakeEventEmitter()


@pytest.fixture
def contribution_port() -> FakeContributionPort:
    """Create fake contribution port."""
    return FakeContributionPort()


@pytest.fixture
def service(
    contribution_port: FakeContributionPort,
    event_emitter: FakeEventEmitter,
    time_authority: FakeTimeAuthority,
) -> ContributionPreservationService:
    """Create contribution preservation service."""
    return ContributionPreservationService(
        contribution_port=contribution_port,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


# =============================================================================
# Contribution Preservation Tests (AC1, AC2)
# =============================================================================


class TestContributionPreservation:
    """Tests for contribution preservation functionality."""

    @pytest.mark.asyncio
    async def test_preserves_contributions_on_exit(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Contributions are preserved on exit (AC1)."""
        cluster_id = uuid4()

        # Add contributions
        contribution_port.add_contribution(cluster_id)
        contribution_port.add_contribution(cluster_id)
        contribution_port.add_contribution(cluster_id)

        result = await service.preserve(cluster_id)

        assert result.contributions_preserved == 3
        assert isinstance(result, PreservationResult)

    @pytest.mark.asyncio
    async def test_preserved_contributions_remain_in_ledger(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Preserved contributions remain in ledger (AC2)."""
        cluster_id = uuid4()

        # Add contributions
        contribution_port.add_contribution(cluster_id)
        contribution_port.add_contribution(cluster_id)

        # Get count before
        count_before = await contribution_port.count_for_cluster(cluster_id)

        await service.preserve(cluster_id)

        # Get count after
        count_after = await contribution_port.count_for_cluster(cluster_id)

        # Same count (nothing deleted)
        assert count_after == count_before

    @pytest.mark.asyncio
    async def test_marks_contributions_as_preserved(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Preservation sets preserved_at timestamp."""
        cluster_id = uuid4()

        # Add contribution
        c = contribution_port.add_contribution(cluster_id)
        assert c.preserved_at is None

        await service.preserve(cluster_id)

        # Check preserved_at is set
        updated = await contribution_port.get_by_id(c.record_id)
        assert updated is not None
        assert updated.preserved_at == time_authority.now()

    @pytest.mark.asyncio
    async def test_skips_already_preserved_contributions(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Already preserved contributions are skipped."""
        cluster_id = uuid4()

        # Add one preserved and one not preserved
        contribution_port.add_contribution(cluster_id, preserved=True)
        contribution_port.add_contribution(cluster_id, preserved=False)

        result = await service.preserve(cluster_id)

        # Only 1 newly preserved
        assert result.contributions_preserved == 1

    @pytest.mark.asyncio
    async def test_preserve_no_contributions(
        self,
        service: ContributionPreservationService,
    ) -> None:
        """Preserve handles Cluster with no contributions."""
        cluster_id = uuid4()

        result = await service.preserve(cluster_id)

        assert result.contributions_preserved == 0
        assert result.task_ids == ()
        assert result.has_contributions is False


# =============================================================================
# Event Emission Tests (AC5)
# =============================================================================


class TestPreservationEventEmission:
    """Tests for event emission on preservation (AC5)."""

    @pytest.mark.asyncio
    async def test_emits_preservation_event(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Emits custodial.contributions.preserved event (AC5)."""
        cluster_id = uuid4()

        contribution_port.add_contribution(cluster_id)

        await service.preserve(cluster_id)

        event = event_emitter.get_last(CONTRIBUTIONS_PRESERVED_EVENT)
        assert event is not None
        assert event["event_type"] == "custodial.contributions.preserved"

    @pytest.mark.asyncio
    async def test_event_contains_cluster_id(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Preservation event contains cluster_id."""
        cluster_id = uuid4()

        contribution_port.add_contribution(cluster_id)

        await service.preserve(cluster_id)

        event = event_emitter.get_last(CONTRIBUTIONS_PRESERVED_EVENT)
        assert event is not None
        assert event["payload"]["cluster_id"] == str(cluster_id)

    @pytest.mark.asyncio
    async def test_event_contains_contribution_count(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Preservation event contains contribution count."""
        cluster_id = uuid4()

        contribution_port.add_contribution(cluster_id)
        contribution_port.add_contribution(cluster_id)
        contribution_port.add_contribution(cluster_id)

        await service.preserve(cluster_id)

        event = event_emitter.get_last(CONTRIBUTIONS_PRESERVED_EVENT)
        assert event is not None
        assert event["payload"]["contributions_preserved"] == 3

    @pytest.mark.asyncio
    async def test_event_contains_task_ids(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Preservation event contains task_ids."""
        cluster_id = uuid4()
        task_id_1 = uuid4()
        task_id_2 = uuid4()

        contribution_port.add_contribution(cluster_id, task_id=task_id_1)
        contribution_port.add_contribution(cluster_id, task_id=task_id_2)

        await service.preserve(cluster_id)

        event = event_emitter.get_last(CONTRIBUTIONS_PRESERVED_EVENT)
        assert event is not None
        task_ids = event["payload"]["task_ids"]
        assert str(task_id_1) in task_ids
        assert str(task_id_2) in task_ids

    @pytest.mark.asyncio
    async def test_event_contains_preserved_at(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Preservation event contains preserved_at timestamp."""
        cluster_id = uuid4()

        contribution_port.add_contribution(cluster_id)

        await service.preserve(cluster_id)

        event = event_emitter.get_last(CONTRIBUTIONS_PRESERVED_EVENT)
        assert event is not None
        assert event["payload"]["preserved_at"] == time_authority.now().isoformat()

    @pytest.mark.asyncio
    async def test_event_actor_is_system(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Preservation event actor is 'system'."""
        cluster_id = uuid4()

        contribution_port.add_contribution(cluster_id)

        await service.preserve(cluster_id)

        event = event_emitter.get_last(CONTRIBUTIONS_PRESERVED_EVENT)
        assert event is not None
        assert event["actor"] == "system"

    @pytest.mark.asyncio
    async def test_event_emitted_even_for_no_contributions(
        self,
        service: ContributionPreservationService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Event is emitted even when no contributions exist."""
        cluster_id = uuid4()

        await service.preserve(cluster_id)

        event = event_emitter.get_last(CONTRIBUTIONS_PRESERVED_EVENT)
        assert event is not None
        assert event["payload"]["contributions_preserved"] == 0


# =============================================================================
# Historical Query Tests (AC6)
# =============================================================================


class TestHistoricalQueries:
    """Tests for historical query support (AC6)."""

    @pytest.mark.asyncio
    async def test_contributions_queryable_after_preservation(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Contributions remain queryable after preservation (AC6)."""
        cluster_id = uuid4()

        # Add contributions
        contribution_port.add_contribution(cluster_id)
        contribution_port.add_contribution(cluster_id)

        await service.preserve(cluster_id)

        # Query still works
        contributions = await contribution_port.get_for_cluster(cluster_id)
        assert len(contributions) == 2

    @pytest.mark.asyncio
    async def test_preserved_contributions_in_preserved_query(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Preserved contributions appear in get_preserved query."""
        cluster_id = uuid4()

        contribution_port.add_contribution(cluster_id)
        contribution_port.add_contribution(cluster_id)

        await service.preserve(cluster_id)

        preserved = await contribution_port.get_preserved(cluster_id)
        assert len(preserved) == 2

    @pytest.mark.asyncio
    async def test_query_works_same_before_and_after(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Historical queries work the same before and after exit (AC6)."""
        cluster_id = uuid4()

        # Add contributions
        contribution_port.add_contribution(cluster_id)
        contribution_port.add_contribution(cluster_id)

        # Query before
        before = await contribution_port.get_for_cluster(cluster_id)
        before_ids = {c.record_id for c in before}

        await service.preserve(cluster_id)

        # Query after
        after = await contribution_port.get_for_cluster(cluster_id)
        after_ids = {c.record_id for c in after}

        # Same records (only difference is preserved_at timestamp)
        assert after_ids == before_ids


# =============================================================================
# No Scrubbing Tests (AC7)
# =============================================================================


class TestNoScrubbing:
    """Tests ensuring no scrubbing mechanisms exist (AC7)."""

    def test_no_delete_contributions_method(
        self,
        service: ContributionPreservationService,
    ) -> None:
        """No delete_contributions method exists."""
        assert not hasattr(service, "delete_contributions")

    def test_no_remove_contributions_method(
        self,
        service: ContributionPreservationService,
    ) -> None:
        """No remove_contributions method exists."""
        assert not hasattr(service, "remove_contributions")

    def test_no_scrub_history_method(
        self,
        service: ContributionPreservationService,
    ) -> None:
        """No scrub_history method exists."""
        assert not hasattr(service, "scrub_history")

    def test_no_scrub_contributions_method(
        self,
        service: ContributionPreservationService,
    ) -> None:
        """No scrub_contributions method exists."""
        assert not hasattr(service, "scrub_contributions")

    def test_no_modify_contributions_method(
        self,
        service: ContributionPreservationService,
    ) -> None:
        """No modify_contributions method exists."""
        assert not hasattr(service, "modify_contributions")

    def test_no_handle_delete_request_method(
        self,
        service: ContributionPreservationService,
    ) -> None:
        """No handle_delete_request method exists."""
        assert not hasattr(service, "handle_delete_request")

    @pytest.mark.asyncio
    async def test_preserve_does_not_delete(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """preserve() does not delete any records."""
        cluster_id = uuid4()

        # Add 5 contributions
        for _ in range(5):
            contribution_port.add_contribution(cluster_id)

        count_before = await contribution_port.count_for_cluster(cluster_id)

        await service.preserve(cluster_id)

        count_after = await contribution_port.count_for_cluster(cluster_id)

        # Exactly same count
        assert count_after == count_before


# =============================================================================
# PII-Free Attribution Tests (AC3, AC4)
# =============================================================================


class TestPIIFreeAttribution:
    """Tests ensuring attribution is PII-free (AC3, AC4)."""

    @pytest.mark.asyncio
    async def test_result_uses_cluster_id_uuid(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Preservation result uses UUID for cluster_id (AC4)."""
        cluster_id = uuid4()

        contribution_port.add_contribution(cluster_id)

        result = await service.preserve(cluster_id)

        assert isinstance(result.cluster_id, UUID)

    @pytest.mark.asyncio
    async def test_event_uses_uuid_strings(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Event uses UUID strings for attribution."""
        cluster_id = uuid4()
        task_id = uuid4()

        contribution_port.add_contribution(cluster_id, task_id=task_id)

        await service.preserve(cluster_id)

        event = event_emitter.get_last(CONTRIBUTIONS_PRESERVED_EVENT)
        assert event is not None

        # cluster_id is UUID string
        assert event["payload"]["cluster_id"] == str(cluster_id)

        # task_ids are UUID strings
        assert str(task_id) in event["payload"]["task_ids"]

    def test_result_has_no_pii_fields(
        self,
        service: ContributionPreservationService,
    ) -> None:
        """PreservationResult has no PII fields (AC3)."""
        # Check PreservationResult class
        from src.domain.governance.exit.preservation_result import PreservationResult

        assert not hasattr(PreservationResult, "cluster_name")
        assert not hasattr(PreservationResult, "cluster_email")
        assert not hasattr(PreservationResult, "cluster_phone")
        assert not hasattr(PreservationResult, "cluster_contact")


# =============================================================================
# Result Object Tests
# =============================================================================


class TestPreservationResultObject:
    """Tests for PreservationResult returned by service."""

    @pytest.mark.asyncio
    async def test_result_is_preservation_result(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """preserve() returns PreservationResult."""
        cluster_id = uuid4()
        contribution_port.add_contribution(cluster_id)

        result = await service.preserve(cluster_id)

        assert isinstance(result, PreservationResult)

    @pytest.mark.asyncio
    async def test_result_contains_correct_cluster_id(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Result contains correct cluster_id."""
        cluster_id = uuid4()
        contribution_port.add_contribution(cluster_id)

        result = await service.preserve(cluster_id)

        assert result.cluster_id == cluster_id

    @pytest.mark.asyncio
    async def test_result_contains_correct_count(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Result contains correct contribution count."""
        cluster_id = uuid4()
        contribution_port.add_contribution(cluster_id)
        contribution_port.add_contribution(cluster_id)
        contribution_port.add_contribution(cluster_id)

        result = await service.preserve(cluster_id)

        assert result.contributions_preserved == 3

    @pytest.mark.asyncio
    async def test_result_contains_task_ids(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Result contains task_ids as tuple."""
        cluster_id = uuid4()
        task_id_1 = uuid4()
        task_id_2 = uuid4()

        contribution_port.add_contribution(cluster_id, task_id=task_id_1)
        contribution_port.add_contribution(cluster_id, task_id=task_id_2)

        result = await service.preserve(cluster_id)

        assert isinstance(result.task_ids, tuple)
        assert task_id_1 in result.task_ids
        assert task_id_2 in result.task_ids

    @pytest.mark.asyncio
    async def test_result_contains_preserved_at(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Result contains preserved_at timestamp."""
        cluster_id = uuid4()
        contribution_port.add_contribution(cluster_id)

        result = await service.preserve(cluster_id)

        assert result.preserved_at == time_authority.now()


# =============================================================================
# Contribution Type Tests
# =============================================================================


class TestContributionTypes:
    """Tests for different contribution types."""

    @pytest.mark.asyncio
    async def test_preserves_task_completed(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Preserves TASK_COMPLETED contributions."""
        cluster_id = uuid4()
        contribution_port.add_contribution(
            cluster_id,
            contribution_type=ContributionType.TASK_COMPLETED,
        )

        result = await service.preserve(cluster_id)

        assert result.contributions_preserved == 1

    @pytest.mark.asyncio
    async def test_preserves_task_reported(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Preserves TASK_REPORTED contributions."""
        cluster_id = uuid4()
        contribution_port.add_contribution(
            cluster_id,
            contribution_type=ContributionType.TASK_REPORTED,
        )

        result = await service.preserve(cluster_id)

        assert result.contributions_preserved == 1

    @pytest.mark.asyncio
    async def test_preserves_deliberation_participated(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Preserves DELIBERATION_PARTICIPATED contributions."""
        cluster_id = uuid4()
        contribution_port.add_contribution(
            cluster_id,
            contribution_type=ContributionType.DELIBERATION_PARTICIPATED,
        )

        result = await service.preserve(cluster_id)

        assert result.contributions_preserved == 1

    @pytest.mark.asyncio
    async def test_preserves_mixed_contribution_types(
        self,
        service: ContributionPreservationService,
        contribution_port: FakeContributionPort,
    ) -> None:
        """Preserves all contribution types together."""
        cluster_id = uuid4()

        contribution_port.add_contribution(
            cluster_id,
            contribution_type=ContributionType.TASK_COMPLETED,
        )
        contribution_port.add_contribution(
            cluster_id,
            contribution_type=ContributionType.TASK_REPORTED,
        )
        contribution_port.add_contribution(
            cluster_id,
            contribution_type=ContributionType.DELIBERATION_PARTICIPATED,
        )

        result = await service.preserve(cluster_id)

        assert result.contributions_preserved == 3
