"""Unit tests for BreachRepositoryStub (Story 6.1, FR30).

Tests for in-memory breach repository stub implementation.

Constitutional Constraints:
- FR30: Breach history shall be filterable by type and date
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from uuid import uuid4

import pytest

from src.domain.events.breach import (
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)
from src.infrastructure.stubs.breach_repository_stub import BreachRepositoryStub


@pytest.fixture
def stub() -> BreachRepositoryStub:
    """Create a fresh BreachRepositoryStub."""
    return BreachRepositoryStub()


@pytest.fixture
def sample_breach() -> BreachEventPayload:
    """Create a sample breach payload."""
    return BreachEventPayload(
        breach_id=uuid4(),
        breach_type=BreachType.HASH_MISMATCH,
        violated_requirement="FR82",
        severity=BreachSeverity.CRITICAL,
        detection_timestamp=datetime.now(timezone.utc),
        details=MappingProxyType({"expected": "abc", "actual": "def"}),
    )


class TestSave:
    """Tests for save() method."""

    @pytest.mark.asyncio
    async def test_save_stores_breach(
        self,
        stub: BreachRepositoryStub,
        sample_breach: BreachEventPayload,
    ) -> None:
        """save() stores the breach in the repository."""
        await stub.save(sample_breach)

        result = await stub.get_by_id(sample_breach.breach_id)
        assert result == sample_breach

    @pytest.mark.asyncio
    async def test_save_multiple_breaches(
        self,
        stub: BreachRepositoryStub,
    ) -> None:
        """save() can store multiple breaches."""
        breach1 = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=datetime.now(timezone.utc),
            details=MappingProxyType({}),
        )
        breach2 = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=datetime.now(timezone.utc),
            details=MappingProxyType({}),
        )

        await stub.save(breach1)
        await stub.save(breach2)

        assert stub.get_breach_count() == 2


class TestGetById:
    """Tests for get_by_id() method."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_breach(
        self,
        stub: BreachRepositoryStub,
        sample_breach: BreachEventPayload,
    ) -> None:
        """get_by_id() returns the breach when found."""
        await stub.save(sample_breach)

        result = await stub.get_by_id(sample_breach.breach_id)

        assert result == sample_breach

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(
        self,
        stub: BreachRepositoryStub,
    ) -> None:
        """get_by_id() returns None when breach not found."""
        result = await stub.get_by_id(uuid4())

        assert result is None


class TestListAll:
    """Tests for list_all() method."""

    @pytest.mark.asyncio
    async def test_list_all_returns_all_breaches(
        self,
        stub: BreachRepositoryStub,
    ) -> None:
        """list_all() returns all stored breaches."""
        breaches = [
            BreachEventPayload(
                breach_id=uuid4(),
                breach_type=BreachType.HASH_MISMATCH,
                violated_requirement="FR82",
                severity=BreachSeverity.CRITICAL,
                detection_timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
                details=MappingProxyType({}),
            ),
            BreachEventPayload(
                breach_id=uuid4(),
                breach_type=BreachType.SIGNATURE_INVALID,
                violated_requirement="FR104",
                severity=BreachSeverity.CRITICAL,
                detection_timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
                details=MappingProxyType({}),
            ),
        ]
        for breach in breaches:
            await stub.save(breach)

        result = await stub.list_all()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_all_returns_ordered_by_timestamp(
        self,
        stub: BreachRepositoryStub,
    ) -> None:
        """list_all() returns breaches ordered by detection_timestamp."""
        now = datetime.now(timezone.utc)
        breach1 = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(hours=2),
            details=MappingProxyType({}),
        )
        breach2 = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(hours=1),
            details=MappingProxyType({}),
        )
        # Save in reverse order
        await stub.save(breach2)
        await stub.save(breach1)

        result = await stub.list_all()

        assert result[0].breach_id == breach1.breach_id
        assert result[1].breach_id == breach2.breach_id

    @pytest.mark.asyncio
    async def test_list_all_empty_returns_empty_list(
        self,
        stub: BreachRepositoryStub,
    ) -> None:
        """list_all() returns empty list when no breaches stored."""
        result = await stub.list_all()

        assert result == []


class TestFilterByType:
    """Tests for filter_by_type() method (FR30)."""

    @pytest.mark.asyncio
    async def test_filter_by_type_returns_matching_breaches(
        self,
        stub: BreachRepositoryStub,
    ) -> None:
        """filter_by_type() returns only breaches of the specified type."""
        hash_breach = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=datetime.now(timezone.utc),
            details=MappingProxyType({}),
        )
        sig_breach = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=datetime.now(timezone.utc),
            details=MappingProxyType({}),
        )
        await stub.save(hash_breach)
        await stub.save(sig_breach)

        result = await stub.filter_by_type(BreachType.HASH_MISMATCH)

        assert len(result) == 1
        assert result[0].breach_type == BreachType.HASH_MISMATCH

    @pytest.mark.asyncio
    async def test_filter_by_type_returns_empty_when_no_matches(
        self,
        stub: BreachRepositoryStub,
        sample_breach: BreachEventPayload,
    ) -> None:
        """filter_by_type() returns empty list when no breaches match."""
        await stub.save(sample_breach)  # HASH_MISMATCH

        result = await stub.filter_by_type(BreachType.QUORUM_VIOLATION)

        assert result == []


class TestFilterByDateRange:
    """Tests for filter_by_date_range() method (FR30)."""

    @pytest.mark.asyncio
    async def test_filter_by_date_range_returns_breaches_in_range(
        self,
        stub: BreachRepositoryStub,
    ) -> None:
        """filter_by_date_range() returns breaches within the date range."""
        now = datetime.now(timezone.utc)
        in_range = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=5),
            details=MappingProxyType({}),
        )
        out_of_range = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=30),
            details=MappingProxyType({}),
        )
        await stub.save(in_range)
        await stub.save(out_of_range)

        start = now - timedelta(days=10)
        end = now

        result = await stub.filter_by_date_range(start=start, end=end)

        assert len(result) == 1
        assert result[0].breach_id == in_range.breach_id

    @pytest.mark.asyncio
    async def test_filter_by_date_range_inclusive_boundaries(
        self,
        stub: BreachRepositoryStub,
    ) -> None:
        """filter_by_date_range() includes breaches on boundaries."""
        boundary_time = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        breach = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=boundary_time,
            details=MappingProxyType({}),
        )
        await stub.save(breach)

        result = await stub.filter_by_date_range(
            start=boundary_time,
            end=boundary_time,
        )

        assert len(result) == 1


class TestFilterByTypeAndDate:
    """Tests for filter_by_type_and_date() method (FR30)."""

    @pytest.mark.asyncio
    async def test_filter_by_type_and_date_combines_filters(
        self,
        stub: BreachRepositoryStub,
    ) -> None:
        """filter_by_type_and_date() applies both type and date filters."""
        now = datetime.now(timezone.utc)

        # Matching type and date
        match = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=5),
            details=MappingProxyType({}),
        )
        # Wrong type, right date
        wrong_type = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=5),
            details=MappingProxyType({}),
        )
        # Right type, wrong date
        wrong_date = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=30),
            details=MappingProxyType({}),
        )

        await stub.save(match)
        await stub.save(wrong_type)
        await stub.save(wrong_date)

        start = now - timedelta(days=10)
        end = now

        result = await stub.filter_by_type_and_date(
            breach_type=BreachType.HASH_MISMATCH,
            start=start,
            end=end,
        )

        assert len(result) == 1
        assert result[0].breach_id == match.breach_id


class TestCountUnacknowledgedInWindow:
    """Tests for count_unacknowledged_in_window() method."""

    @pytest.mark.asyncio
    async def test_count_unacknowledged_in_window_counts_recent_breaches(
        self,
        stub: BreachRepositoryStub,
    ) -> None:
        """count_unacknowledged_in_window() counts breaches in window."""
        now = datetime.now(timezone.utc)

        recent = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=30),
            details=MappingProxyType({}),
        )
        old = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=100),
            details=MappingProxyType({}),
        )

        await stub.save(recent)
        await stub.save(old)

        count = await stub.count_unacknowledged_in_window(window_days=90)

        assert count == 1

    @pytest.mark.asyncio
    async def test_count_unacknowledged_excludes_acknowledged(
        self,
        stub: BreachRepositoryStub,
    ) -> None:
        """count_unacknowledged_in_window() excludes acknowledged breaches."""
        now = datetime.now(timezone.utc)

        breach1 = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=30),
            details=MappingProxyType({}),
        )
        breach2 = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=30),
            details=MappingProxyType({}),
        )

        await stub.save(breach1)
        await stub.save(breach2)
        stub.acknowledge_breach(breach1.breach_id)

        count = await stub.count_unacknowledged_in_window(window_days=90)

        assert count == 1


class TestClear:
    """Tests for clear() method."""

    @pytest.mark.asyncio
    async def test_clear_removes_all_breaches(
        self,
        stub: BreachRepositoryStub,
        sample_breach: BreachEventPayload,
    ) -> None:
        """clear() removes all stored breaches."""
        await stub.save(sample_breach)
        stub.acknowledge_breach(sample_breach.breach_id)

        stub.clear()

        assert stub.get_breach_count() == 0
        assert stub.get_acknowledged_count() == 0


class TestHelperMethods:
    """Tests for test helper methods."""

    @pytest.mark.asyncio
    async def test_get_breach_count(
        self,
        stub: BreachRepositoryStub,
        sample_breach: BreachEventPayload,
    ) -> None:
        """get_breach_count() returns number of stored breaches."""
        assert stub.get_breach_count() == 0

        await stub.save(sample_breach)

        assert stub.get_breach_count() == 1

    @pytest.mark.asyncio
    async def test_get_acknowledged_count(
        self,
        stub: BreachRepositoryStub,
        sample_breach: BreachEventPayload,
    ) -> None:
        """get_acknowledged_count() returns number of acknowledged breaches."""
        await stub.save(sample_breach)

        assert stub.get_acknowledged_count() == 0

        stub.acknowledge_breach(sample_breach.breach_id)

        assert stub.get_acknowledged_count() == 1
