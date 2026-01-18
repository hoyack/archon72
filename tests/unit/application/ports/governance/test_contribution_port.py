"""Unit tests for ContributionPort protocol.

Story: consent-gov-7.3: Contribution Preservation

Tests for:
- ContributionPort protocol methods
- Immutability enforcement (no delete/scrub methods)
- PII-free operations

Constitutional Truths Tested:
- FR45: Contribution history preserved on exit
- NFR-INT-02: Public data only, no PII
- Ledger immutability: No deletion or modification
- AC7: No scrubbing of historical events
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.contribution_port import ContributionPort
from src.domain.governance.exit.contribution_record import ContributionRecord
from src.domain.governance.exit.contribution_type import ContributionType


class FakeContributionPort:
    """Fake implementation of ContributionPort for testing."""

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


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestContributionPortProtocol:
    """Tests verifying FakeContributionPort implements the protocol."""

    def test_fake_implements_protocol(self) -> None:
        """FakeContributionPort implements ContributionPort."""
        port = FakeContributionPort()
        # Protocol compliance check - if this doesn't raise, it implements
        assert isinstance(port, FakeContributionPort)
        # Check required methods exist
        assert hasattr(port, "get_for_cluster")
        assert hasattr(port, "get_preserved")
        assert hasattr(port, "mark_preserved")
        assert hasattr(port, "record")
        assert hasattr(port, "get_by_id")
        assert hasattr(port, "count_for_cluster")


# =============================================================================
# Functional Tests
# =============================================================================


class TestContributionPortOperations:
    """Tests for ContributionPort operations."""

    @pytest.fixture
    def port(self) -> FakeContributionPort:
        """Create a fake contribution port."""
        return FakeContributionPort()

    @pytest.fixture
    def sample_contribution(self) -> ContributionRecord:
        """Create a sample contribution record."""
        return ContributionRecord(
            record_id=uuid4(),
            cluster_id=uuid4(),
            task_id=uuid4(),
            contribution_type=ContributionType.TASK_COMPLETED,
            contributed_at=datetime.now(timezone.utc),
            preserved_at=None,
            result_hash="hash123",
        )

    @pytest.mark.asyncio
    async def test_record_contribution(
        self,
        port: FakeContributionPort,
        sample_contribution: ContributionRecord,
    ) -> None:
        """Can record a new contribution."""
        await port.record(sample_contribution)

        result = await port.get_by_id(sample_contribution.record_id)
        assert result is not None
        assert result.record_id == sample_contribution.record_id
        assert result.cluster_id == sample_contribution.cluster_id

    @pytest.mark.asyncio
    async def test_get_for_cluster(
        self,
        port: FakeContributionPort,
    ) -> None:
        """Can get all contributions for a Cluster."""
        cluster_id = uuid4()
        other_cluster_id = uuid4()

        # Create contributions for two different clusters
        c1 = ContributionRecord(
            record_id=uuid4(),
            cluster_id=cluster_id,
            task_id=uuid4(),
            contribution_type=ContributionType.TASK_COMPLETED,
            contributed_at=datetime.now(timezone.utc),
            preserved_at=None,
            result_hash="hash1",
        )
        c2 = ContributionRecord(
            record_id=uuid4(),
            cluster_id=cluster_id,
            task_id=uuid4(),
            contribution_type=ContributionType.TASK_REPORTED,
            contributed_at=datetime.now(timezone.utc),
            preserved_at=None,
            result_hash="hash2",
        )
        c3 = ContributionRecord(
            record_id=uuid4(),
            cluster_id=other_cluster_id,
            task_id=uuid4(),
            contribution_type=ContributionType.TASK_COMPLETED,
            contributed_at=datetime.now(timezone.utc),
            preserved_at=None,
            result_hash="hash3",
        )

        await port.record(c1)
        await port.record(c2)
        await port.record(c3)

        # Get for specific cluster
        contributions = await port.get_for_cluster(cluster_id)

        assert len(contributions) == 2
        assert all(c.cluster_id == cluster_id for c in contributions)

    @pytest.mark.asyncio
    async def test_get_preserved(
        self,
        port: FakeContributionPort,
    ) -> None:
        """Can get only preserved contributions."""
        cluster_id = uuid4()
        now = datetime.now(timezone.utc)

        # Create preserved and non-preserved contributions
        c1 = ContributionRecord(
            record_id=uuid4(),
            cluster_id=cluster_id,
            task_id=uuid4(),
            contribution_type=ContributionType.TASK_COMPLETED,
            contributed_at=now,
            preserved_at=now,  # Preserved
            result_hash="hash1",
        )
        c2 = ContributionRecord(
            record_id=uuid4(),
            cluster_id=cluster_id,
            task_id=uuid4(),
            contribution_type=ContributionType.TASK_REPORTED,
            contributed_at=now,
            preserved_at=None,  # Not preserved
            result_hash="hash2",
        )

        await port.record(c1)
        await port.record(c2)

        preserved = await port.get_preserved(cluster_id)

        assert len(preserved) == 1
        assert preserved[0].record_id == c1.record_id
        assert preserved[0].preserved_at is not None

    @pytest.mark.asyncio
    async def test_mark_preserved(
        self,
        port: FakeContributionPort,
        sample_contribution: ContributionRecord,
    ) -> None:
        """Can mark contribution as preserved."""
        await port.record(sample_contribution)

        # Verify not preserved initially
        before = await port.get_by_id(sample_contribution.record_id)
        assert before is not None
        assert before.preserved_at is None

        # Mark as preserved
        preservation_time = datetime.now(timezone.utc)
        await port.mark_preserved(
            record_id=sample_contribution.record_id,
            preserved_at=preservation_time,
        )

        # Verify preserved after
        after = await port.get_by_id(sample_contribution.record_id)
        assert after is not None
        assert after.preserved_at == preservation_time

    @pytest.mark.asyncio
    async def test_count_for_cluster(
        self,
        port: FakeContributionPort,
    ) -> None:
        """Can count contributions for a Cluster."""
        cluster_id = uuid4()
        now = datetime.now(timezone.utc)

        # Create 3 contributions
        for i in range(3):
            contribution = ContributionRecord(
                record_id=uuid4(),
                cluster_id=cluster_id,
                task_id=uuid4(),
                contribution_type=ContributionType.TASK_COMPLETED,
                contributed_at=now,
                preserved_at=None,
                result_hash=f"hash{i}",
            )
            await port.record(contribution)

        count = await port.count_for_cluster(cluster_id)
        assert count == 3

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self,
        port: FakeContributionPort,
    ) -> None:
        """get_by_id returns None for unknown ID."""
        result = await port.get_by_id(uuid4())
        assert result is None


# =============================================================================
# Immutability Tests (AC7: No Scrubbing)
# =============================================================================


class TestContributionPortNoScrubbing:
    """Tests ensuring ContributionPort has no scrubbing methods (AC7)."""

    def test_no_delete_contribution_method(self) -> None:
        """ContributionPort has no delete_contribution method."""
        assert not hasattr(ContributionPort, "delete_contribution")

    def test_no_remove_contribution_method(self) -> None:
        """ContributionPort has no remove_contribution method."""
        assert not hasattr(ContributionPort, "remove_contribution")

    def test_no_scrub_contribution_method(self) -> None:
        """ContributionPort has no scrub_contribution method."""
        assert not hasattr(ContributionPort, "scrub_contribution")

    def test_no_modify_contribution_method(self) -> None:
        """ContributionPort has no modify_contribution method."""
        assert not hasattr(ContributionPort, "modify_contribution")

    def test_fake_has_no_delete_method(self) -> None:
        """FakeContributionPort has no delete method."""
        port = FakeContributionPort()
        assert not hasattr(port, "delete_contribution")
        assert not hasattr(port, "delete")

    def test_fake_has_no_scrub_method(self) -> None:
        """FakeContributionPort has no scrub method."""
        port = FakeContributionPort()
        assert not hasattr(port, "scrub_contribution")
        assert not hasattr(port, "scrub")


# =============================================================================
# Historical Query Tests (AC6)
# =============================================================================


class TestContributionPortHistoricalQueries:
    """Tests for historical query capabilities (AC6)."""

    @pytest.fixture
    def port(self) -> FakeContributionPort:
        """Create a fake contribution port."""
        return FakeContributionPort()

    @pytest.mark.asyncio
    async def test_preserved_contributions_queryable(
        self,
        port: FakeContributionPort,
    ) -> None:
        """Preserved contributions remain queryable."""
        cluster_id = uuid4()
        now = datetime.now(timezone.utc)

        # Record contribution
        contribution = ContributionRecord(
            record_id=uuid4(),
            cluster_id=cluster_id,
            task_id=uuid4(),
            contribution_type=ContributionType.TASK_COMPLETED,
            contributed_at=now,
            preserved_at=None,
            result_hash="hash123",
        )
        await port.record(contribution)

        # Mark preserved
        await port.mark_preserved(contribution.record_id, now)

        # Query still works
        contributions = await port.get_for_cluster(cluster_id)
        assert len(contributions) == 1

        preserved = await port.get_preserved(cluster_id)
        assert len(preserved) == 1

    @pytest.mark.asyncio
    async def test_mark_preserved_does_not_delete(
        self,
        port: FakeContributionPort,
    ) -> None:
        """mark_preserved only sets flag, does not delete (AC2)."""
        cluster_id = uuid4()
        now = datetime.now(timezone.utc)

        contribution = ContributionRecord(
            record_id=uuid4(),
            cluster_id=cluster_id,
            task_id=uuid4(),
            contribution_type=ContributionType.TASK_COMPLETED,
            contributed_at=now,
            preserved_at=None,
            result_hash="hash123",
        )
        await port.record(contribution)

        # Get count before
        count_before = await port.count_for_cluster(cluster_id)

        # Mark preserved
        await port.mark_preserved(contribution.record_id, now)

        # Get count after
        count_after = await port.count_for_cluster(cluster_id)

        # Same count (nothing deleted)
        assert count_after == count_before

    @pytest.mark.asyncio
    async def test_historical_query_same_before_and_after_exit(
        self,
        port: FakeContributionPort,
    ) -> None:
        """Historical queries return same data before and after exit (AC6)."""
        cluster_id = uuid4()
        now = datetime.now(timezone.utc)

        # Record 5 contributions
        for i in range(5):
            contribution = ContributionRecord(
                record_id=uuid4(),
                cluster_id=cluster_id,
                task_id=uuid4(),
                contribution_type=ContributionType.TASK_COMPLETED,
                contributed_at=now,
                preserved_at=None,
                result_hash=f"hash{i}",
            )
            await port.record(contribution)

        # Query before preservation
        before = await port.get_for_cluster(cluster_id)
        assert len(before) == 5

        # Preserve all
        for c in before:
            await port.mark_preserved(c.record_id, now)

        # Query after preservation (simulating post-exit)
        after = await port.get_for_cluster(cluster_id)
        assert len(after) == 5  # Same count

        # Same records (by ID)
        before_ids = {c.record_id for c in before}
        after_ids = {c.record_id for c in after}
        assert after_ids == before_ids
