"""Unit tests for amendment repository stub (Story 6.7, FR126-FR128)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports.amendment_repository import AmendmentProposal
from src.domain.errors.amendment import AmendmentNotFoundError
from src.domain.events.amendment import AmendmentStatus, AmendmentType
from src.infrastructure.stubs.amendment_repository_stub import AmendmentRepositoryStub


@pytest.fixture
def repository() -> AmendmentRepositoryStub:
    """Provide a fresh repository stub."""
    return AmendmentRepositoryStub()


@pytest.fixture
def sample_amendment() -> AmendmentProposal:
    """Provide a sample amendment proposal."""
    now = datetime.now(timezone.utc)
    return AmendmentProposal(
        amendment_id="AMD-001",
        amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
        title="Test Amendment",
        summary="Test summary",
        proposed_at=now,
        visible_from=now,
        votable_from=now + timedelta(days=14),
        proposer_id="proposer-001",
        is_core_guarantee=False,
        affected_guarantees=(),
        status=AmendmentStatus.VISIBILITY_PERIOD,
    )


class TestSaveAmendment:
    """Tests for save_amendment method."""

    @pytest.mark.asyncio
    async def test_save_amendment(
        self, repository: AmendmentRepositoryStub, sample_amendment: AmendmentProposal
    ) -> None:
        """Test saving an amendment."""
        await repository.save_amendment(sample_amendment)

        saved = await repository.get_amendment("AMD-001")
        assert saved is not None
        assert saved.amendment_id == "AMD-001"

    @pytest.mark.asyncio
    async def test_save_overwrites_existing(
        self, repository: AmendmentRepositoryStub, sample_amendment: AmendmentProposal
    ) -> None:
        """Test saving overwrites existing amendment with same ID."""
        await repository.save_amendment(sample_amendment)

        # Save again with different title
        updated = AmendmentProposal(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Updated Title",
            summary="Test summary",
            proposed_at=sample_amendment.proposed_at,
            visible_from=sample_amendment.visible_from,
            votable_from=sample_amendment.votable_from,
            proposer_id="proposer-001",
            is_core_guarantee=False,
            affected_guarantees=(),
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )
        await repository.save_amendment(updated)

        saved = await repository.get_amendment("AMD-001")
        assert saved is not None
        assert saved.title == "Updated Title"


class TestGetAmendment:
    """Tests for get_amendment method."""

    @pytest.mark.asyncio
    async def test_get_existing_amendment(
        self, repository: AmendmentRepositoryStub, sample_amendment: AmendmentProposal
    ) -> None:
        """Test getting existing amendment."""
        await repository.save_amendment(sample_amendment)

        result = await repository.get_amendment("AMD-001")

        assert result is not None
        assert result.amendment_id == "AMD-001"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(
        self, repository: AmendmentRepositoryStub
    ) -> None:
        """Test getting non-existent amendment returns None."""
        result = await repository.get_amendment("AMD-NONEXISTENT")

        assert result is None


class TestListPendingAmendments:
    """Tests for list_pending_amendments method."""

    @pytest.mark.asyncio
    async def test_list_pending_includes_visibility_period(
        self, repository: AmendmentRepositoryStub
    ) -> None:
        """Test pending includes amendments in visibility period."""
        now = datetime.now(timezone.utc)

        for i in range(3):
            amendment = AmendmentProposal(
                amendment_id=f"AMD-00{i + 1}",
                amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
                title=f"Test {i + 1}",
                summary="Test",
                proposed_at=now + timedelta(hours=i),
                visible_from=now + timedelta(hours=i),
                votable_from=now + timedelta(days=14),
                proposer_id="proposer-001",
                is_core_guarantee=False,
                affected_guarantees=(),
                status=AmendmentStatus.VISIBILITY_PERIOD,
            )
            await repository.save_amendment(amendment)

        result = await repository.list_pending_amendments()

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_pending_excludes_approved(
        self, repository: AmendmentRepositoryStub, sample_amendment: AmendmentProposal
    ) -> None:
        """Test pending excludes approved amendments."""
        approved = AmendmentProposal(
            amendment_id="AMD-001",
            amendment_type=sample_amendment.amendment_type,
            title=sample_amendment.title,
            summary=sample_amendment.summary,
            proposed_at=sample_amendment.proposed_at,
            visible_from=sample_amendment.visible_from,
            votable_from=sample_amendment.votable_from,
            proposer_id=sample_amendment.proposer_id,
            is_core_guarantee=sample_amendment.is_core_guarantee,
            affected_guarantees=sample_amendment.affected_guarantees,
            status=AmendmentStatus.APPROVED,
        )
        await repository.save_amendment(approved)

        result = await repository.list_pending_amendments()

        assert len(result) == 0


class TestListVotableAmendments:
    """Tests for list_votable_amendments method (FR126)."""

    @pytest.mark.asyncio
    async def test_list_votable_includes_past_14_days(
        self, repository: AmendmentRepositoryStub
    ) -> None:
        """Test FR126: Votable includes amendments past 14-day visibility."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=15)

        amendment = AmendmentProposal(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Test",
            proposed_at=past,
            visible_from=past,
            votable_from=past + timedelta(days=14),  # Already past
            proposer_id="proposer-001",
            is_core_guarantee=False,
            affected_guarantees=(),
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )
        await repository.save_amendment(amendment)

        result = await repository.list_votable_amendments()

        assert len(result) == 1
        assert result[0].amendment_id == "AMD-001"

    @pytest.mark.asyncio
    async def test_list_votable_excludes_before_14_days(
        self, repository: AmendmentRepositoryStub, sample_amendment: AmendmentProposal
    ) -> None:
        """Test FR126: Votable excludes amendments before 14-day visibility."""
        await repository.save_amendment(sample_amendment)

        result = await repository.list_votable_amendments()

        assert len(result) == 0


class TestGetAmendmentHistory:
    """Tests for get_amendment_history method (FR128)."""

    @pytest.mark.asyncio
    async def test_history_includes_all_statuses(
        self, repository: AmendmentRepositoryStub
    ) -> None:
        """Test FR128: History includes all amendments regardless of status."""
        now = datetime.now(timezone.utc)

        statuses = [
            AmendmentStatus.VISIBILITY_PERIOD,
            AmendmentStatus.APPROVED,
            AmendmentStatus.REJECTED,
        ]

        for i, status in enumerate(statuses):
            amendment = AmendmentProposal(
                amendment_id=f"AMD-00{i + 1}",
                amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
                title=f"Test {i + 1}",
                summary="Test",
                proposed_at=now + timedelta(hours=i),
                visible_from=now + timedelta(hours=i),
                votable_from=now + timedelta(days=14),
                proposer_id="proposer-001",
                is_core_guarantee=False,
                affected_guarantees=(),
                status=status,
            )
            await repository.save_amendment(amendment)

        result = await repository.get_amendment_history()

        assert len(result) == 3


class TestIsAmendmentVotable:
    """Tests for is_amendment_votable method (FR126)."""

    @pytest.mark.asyncio
    async def test_is_votable_after_14_days(
        self, repository: AmendmentRepositoryStub
    ) -> None:
        """Test FR126: Amendment is votable after 14 days."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=15)

        amendment = AmendmentProposal(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Test",
            proposed_at=past,
            visible_from=past,
            votable_from=past + timedelta(days=14),
            proposer_id="proposer-001",
            is_core_guarantee=False,
            affected_guarantees=(),
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )
        await repository.save_amendment(amendment)

        is_votable, days_remaining = await repository.is_amendment_votable("AMD-001")

        assert is_votable is True
        assert days_remaining == 0

    @pytest.mark.asyncio
    async def test_is_not_votable_before_14_days(
        self, repository: AmendmentRepositoryStub, sample_amendment: AmendmentProposal
    ) -> None:
        """Test FR126: Amendment is not votable before 14 days."""
        await repository.save_amendment(sample_amendment)

        is_votable, days_remaining = await repository.is_amendment_votable("AMD-001")

        assert is_votable is False
        assert days_remaining > 0

    @pytest.mark.asyncio
    async def test_is_votable_not_found_raises_error(
        self, repository: AmendmentRepositoryStub
    ) -> None:
        """Test error raised for non-existent amendment."""
        with pytest.raises(AmendmentNotFoundError):
            await repository.is_amendment_votable("AMD-NONEXISTENT")


class TestUpdateStatus:
    """Tests for update_status method."""

    @pytest.mark.asyncio
    async def test_update_status(
        self, repository: AmendmentRepositoryStub, sample_amendment: AmendmentProposal
    ) -> None:
        """Test status update."""
        await repository.save_amendment(sample_amendment)

        await repository.update_status("AMD-001", AmendmentStatus.REJECTED)

        saved = await repository.get_amendment("AMD-001")
        assert saved is not None
        assert saved.status == AmendmentStatus.REJECTED

    @pytest.mark.asyncio
    async def test_update_status_not_found_raises_error(
        self, repository: AmendmentRepositoryStub
    ) -> None:
        """Test error raised for non-existent amendment."""
        with pytest.raises(AmendmentNotFoundError):
            await repository.update_status("AMD-NONEXISTENT", AmendmentStatus.REJECTED)


class TestHelperMethods:
    """Tests for test helper methods."""

    @pytest.mark.asyncio
    async def test_clear(
        self, repository: AmendmentRepositoryStub, sample_amendment: AmendmentProposal
    ) -> None:
        """Test clear removes all amendments."""
        await repository.save_amendment(sample_amendment)
        assert repository.get_amendment_count() == 1

        repository.clear()

        assert repository.get_amendment_count() == 0

    @pytest.mark.asyncio
    async def test_get_amendment_count(
        self, repository: AmendmentRepositoryStub, sample_amendment: AmendmentProposal
    ) -> None:
        """Test get_amendment_count returns correct count."""
        assert repository.get_amendment_count() == 0

        await repository.save_amendment(sample_amendment)

        assert repository.get_amendment_count() == 1

    @pytest.mark.asyncio
    async def test_get_amendments_by_status(
        self, repository: AmendmentRepositoryStub
    ) -> None:
        """Test get_amendments_by_status filters correctly."""
        now = datetime.now(timezone.utc)

        for i, status in enumerate(
            [AmendmentStatus.VISIBILITY_PERIOD, AmendmentStatus.APPROVED]
        ):
            amendment = AmendmentProposal(
                amendment_id=f"AMD-00{i + 1}",
                amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
                title=f"Test {i + 1}",
                summary="Test",
                proposed_at=now,
                visible_from=now,
                votable_from=now + timedelta(days=14),
                proposer_id="proposer-001",
                is_core_guarantee=False,
                affected_guarantees=(),
                status=status,
            )
            await repository.save_amendment(amendment)

        pending = repository.get_amendments_by_status(AmendmentStatus.VISIBILITY_PERIOD)
        approved = repository.get_amendments_by_status(AmendmentStatus.APPROVED)

        assert len(pending) == 1
        assert len(approved) == 1
