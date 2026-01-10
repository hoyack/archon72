"""Unit tests for WaiverRepository port (Story 9.8, SC-4, SR-10).

Tests for the WaiverRecord dataclass and WaiverRepositoryStub.

Constitutional Constraints:
- SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
- SR-10: CT-15 waiver documentation -> Must be explicit and tracked
"""

from datetime import datetime, timezone

import pytest

from src.application.ports.waiver_repository import WaiverRecord
from src.domain.events.waiver import WaiverStatus
from src.infrastructure.stubs.waiver_repository_stub import WaiverRepositoryStub


class TestWaiverRecord:
    """Tests for WaiverRecord dataclass."""

    @pytest.fixture
    def valid_record(self) -> WaiverRecord:
        """Create a valid waiver record for testing."""
        return WaiverRecord(
            waiver_id="CT-15-MVP-WAIVER",
            constitutional_truth_id="CT-15",
            constitutional_truth_statement="Legitimacy requires consent",
            what_is_waived="Full consent mechanism implementation",
            rationale="MVP focuses on constitutional infrastructure",
            target_phase="Phase 2 - Seeker Journey",
            status=WaiverStatus.ACTIVE,
            documented_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            documented_by="system:waiver-documentation",
        )

    def test_record_creation_success(self, valid_record: WaiverRecord) -> None:
        """Test successful record creation with all fields."""
        assert valid_record.waiver_id == "CT-15-MVP-WAIVER"
        assert valid_record.constitutional_truth_id == "CT-15"
        assert valid_record.status == WaiverStatus.ACTIVE

    def test_record_is_immutable(self, valid_record: WaiverRecord) -> None:
        """Test record is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            valid_record.waiver_id = "different-id"  # type: ignore

    def test_record_to_dict(self, valid_record: WaiverRecord) -> None:
        """Test to_dict includes all fields."""
        result = valid_record.to_dict()
        assert result["waiver_id"] == "CT-15-MVP-WAIVER"
        assert result["constitutional_truth_id"] == "CT-15"
        assert result["status"] == "ACTIVE"
        assert result["target_phase"] == "Phase 2 - Seeker Journey"


class TestWaiverRecordStatus:
    """Tests for WaiverRecord with different statuses."""

    def test_active_status(self) -> None:
        """Test record with ACTIVE status."""
        record = WaiverRecord(
            waiver_id="TEST",
            constitutional_truth_id="CT-1",
            constitutional_truth_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 1",
            status=WaiverStatus.ACTIVE,
            documented_at=datetime.now(timezone.utc),
            documented_by="test",
        )
        assert record.status == WaiverStatus.ACTIVE

    def test_implemented_status(self) -> None:
        """Test record with IMPLEMENTED status."""
        record = WaiverRecord(
            waiver_id="TEST",
            constitutional_truth_id="CT-1",
            constitutional_truth_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 1",
            status=WaiverStatus.IMPLEMENTED,
            documented_at=datetime.now(timezone.utc),
            documented_by="test",
        )
        assert record.status == WaiverStatus.IMPLEMENTED

    def test_cancelled_status(self) -> None:
        """Test record with CANCELLED status."""
        record = WaiverRecord(
            waiver_id="TEST",
            constitutional_truth_id="CT-1",
            constitutional_truth_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 1",
            status=WaiverStatus.CANCELLED,
            documented_at=datetime.now(timezone.utc),
            documented_by="test",
        )
        assert record.status == WaiverStatus.CANCELLED


@pytest.mark.asyncio
class TestWaiverRepositoryStub:
    """Tests for WaiverRepositoryStub."""

    @pytest.fixture
    def stub(self) -> WaiverRepositoryStub:
        """Create a fresh stub for each test."""
        return WaiverRepositoryStub()

    @pytest.fixture
    def sample_waiver(self) -> WaiverRecord:
        """Create a sample waiver for testing."""
        return WaiverRecord(
            waiver_id="CT-15-MVP-WAIVER",
            constitutional_truth_id="CT-15",
            constitutional_truth_statement="Legitimacy requires consent",
            what_is_waived="Consent implementation",
            rationale="MVP scope",
            target_phase="Phase 2",
            status=WaiverStatus.ACTIVE,
            documented_at=datetime.now(timezone.utc),
            documented_by="test",
        )

    async def test_save_and_get_waiver(
        self, stub: WaiverRepositoryStub, sample_waiver: WaiverRecord
    ) -> None:
        """Test saving and retrieving a waiver."""
        await stub.save_waiver(sample_waiver)
        result = await stub.get_waiver(sample_waiver.waiver_id)
        assert result is not None
        assert result.waiver_id == sample_waiver.waiver_id

    async def test_get_nonexistent_waiver(self, stub: WaiverRepositoryStub) -> None:
        """Test getting a nonexistent waiver returns None."""
        result = await stub.get_waiver("nonexistent")
        assert result is None

    async def test_get_all_waivers_empty(self, stub: WaiverRepositoryStub) -> None:
        """Test get_all_waivers returns empty tuple when no waivers."""
        result = await stub.get_all_waivers()
        assert result == ()

    async def test_get_all_waivers_with_data(
        self, stub: WaiverRepositoryStub, sample_waiver: WaiverRecord
    ) -> None:
        """Test get_all_waivers returns all waivers."""
        await stub.save_waiver(sample_waiver)
        result = await stub.get_all_waivers()
        assert len(result) == 1
        assert result[0].waiver_id == sample_waiver.waiver_id

    async def test_get_active_waivers_filters_correctly(
        self, stub: WaiverRepositoryStub
    ) -> None:
        """Test get_active_waivers only returns active waivers."""
        active_waiver = WaiverRecord(
            waiver_id="ACTIVE-WAIVER",
            constitutional_truth_id="CT-1",
            constitutional_truth_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 1",
            status=WaiverStatus.ACTIVE,
            documented_at=datetime.now(timezone.utc),
            documented_by="test",
        )
        implemented_waiver = WaiverRecord(
            waiver_id="IMPLEMENTED-WAIVER",
            constitutional_truth_id="CT-2",
            constitutional_truth_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 1",
            status=WaiverStatus.IMPLEMENTED,
            documented_at=datetime.now(timezone.utc),
            documented_by="test",
        )

        await stub.save_waiver(active_waiver)
        await stub.save_waiver(implemented_waiver)

        all_waivers = await stub.get_all_waivers()
        active_waivers = await stub.get_active_waivers()

        assert len(all_waivers) == 2
        assert len(active_waivers) == 1
        assert active_waivers[0].waiver_id == "ACTIVE-WAIVER"

    async def test_exists_returns_true_for_existing(
        self, stub: WaiverRepositoryStub, sample_waiver: WaiverRecord
    ) -> None:
        """Test exists returns True for existing waiver."""
        await stub.save_waiver(sample_waiver)
        assert await stub.exists(sample_waiver.waiver_id) is True

    async def test_exists_returns_false_for_nonexistent(
        self, stub: WaiverRepositoryStub
    ) -> None:
        """Test exists returns False for nonexistent waiver."""
        assert await stub.exists("nonexistent") is False

    async def test_clear_removes_all_waivers(
        self, stub: WaiverRepositoryStub, sample_waiver: WaiverRecord
    ) -> None:
        """Test clear removes all waivers."""
        await stub.save_waiver(sample_waiver)
        assert await stub.exists(sample_waiver.waiver_id) is True

        stub.clear()

        assert await stub.exists(sample_waiver.waiver_id) is False
        assert stub.get_waiver_count() == 0

    async def test_save_updates_existing_waiver(
        self, stub: WaiverRepositoryStub
    ) -> None:
        """Test saving a waiver with same ID updates it."""
        original = WaiverRecord(
            waiver_id="TEST",
            constitutional_truth_id="CT-1",
            constitutional_truth_statement="Original",
            what_is_waived="Original",
            rationale="Original",
            target_phase="Phase 1",
            status=WaiverStatus.ACTIVE,
            documented_at=datetime.now(timezone.utc),
            documented_by="test",
        )
        updated = WaiverRecord(
            waiver_id="TEST",  # Same ID
            constitutional_truth_id="CT-1",
            constitutional_truth_statement="Updated",  # Changed
            what_is_waived="Updated",
            rationale="Updated",
            target_phase="Phase 1",
            status=WaiverStatus.IMPLEMENTED,  # Changed
            documented_at=datetime.now(timezone.utc),
            documented_by="test",
        )

        await stub.save_waiver(original)
        await stub.save_waiver(updated)

        result = await stub.get_waiver("TEST")
        assert result is not None
        assert result.constitutional_truth_statement == "Updated"
        assert result.status == WaiverStatus.IMPLEMENTED
        assert stub.get_waiver_count() == 1
