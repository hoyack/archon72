"""Unit tests for UserContentProhibitionService (Story 9.4, FR58).

Tests:
- HALT CHECK FIRST pattern (CT-11)
- Clean content can be featured
- Prohibited content is flagged not deleted (FR58 critical distinction)
- Prohibition flag prevents featuring
- Event creation and witnessing (CT-12)
- Batch evaluation
- Prohibition status query
- Clear prohibition flag
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.ports.prohibited_language_scanner import ScanResult
from src.application.services.user_content_prohibition_service import (
    UserContentProhibitionService,
)
from src.domain.errors.user_content import (
    UserContentCannotBeFeaturedException,
    UserContentNotFoundError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.user_content_prohibition import (
    USER_CONTENT_CLEARED_EVENT_TYPE,
    USER_CONTENT_PROHIBITED_EVENT_TYPE,
    USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
)
from src.domain.models.user_content import (
    FeaturedStatus,
    FeatureRequest,
    UserContent,
    UserContentProhibitionFlag,
    UserContentStatus,
)
from src.infrastructure.stubs.user_content_repository_stub import (
    UserContentRepositoryStub,
)


@pytest.fixture
def mock_scanner() -> AsyncMock:
    """Create mock scanner port."""
    scanner = AsyncMock()
    scanner.scan_content.return_value = ScanResult.no_violations()
    return scanner


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create mock event writer."""
    writer = AsyncMock()
    writer.write_event.return_value = None
    return writer


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create mock halt checker."""
    checker = AsyncMock()
    checker.is_halted.return_value = False
    return checker


@pytest.fixture
def content_repository() -> UserContentRepositoryStub:
    """Create content repository stub."""
    return UserContentRepositoryStub()


@pytest.fixture
def service(
    content_repository: UserContentRepositoryStub,
    mock_scanner: AsyncMock,
    mock_event_writer: AsyncMock,
    mock_halt_checker: AsyncMock,
) -> UserContentProhibitionService:
    """Create service with mock dependencies."""
    return UserContentProhibitionService(
        content_repository=content_repository,
        scanner=mock_scanner,
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker,
    )


@pytest.fixture
def sample_request() -> FeatureRequest:
    """Create sample feature request."""
    return FeatureRequest(
        content_id="uc_123",
        owner_id="user_456",
        content="Clean article content here",
        title="My Article",
    )


class TestHaltCheckFirst:
    """Tests for HALT CHECK FIRST pattern (CT-11)."""

    @pytest.mark.asyncio
    async def test_evaluate_checks_halt_state_first(
        self,
        service: UserContentProhibitionService,
        mock_halt_checker: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test evaluate_for_featuring checks halt state first."""
        await service.evaluate_for_featuring(sample_request)

        mock_halt_checker.is_halted.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_raises_when_halted(
        self,
        service: UserContentProhibitionService,
        mock_halt_checker: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test evaluate raises SystemHaltedError when halted."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError):
            await service.evaluate_for_featuring(sample_request)

    @pytest.mark.asyncio
    async def test_batch_evaluate_checks_halt_first(
        self,
        service: UserContentProhibitionService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test batch_evaluate checks halt state first."""
        mock_halt_checker.is_halted.return_value = True
        requests = [
            FeatureRequest(
                content_id=f"uc_{i}",
                owner_id="user_456",
                content=f"Content {i}",
                title=f"Title {i}",
            )
            for i in range(3)
        ]

        with pytest.raises(SystemHaltedError):
            await service.batch_evaluate_for_featuring(requests)

    @pytest.mark.asyncio
    async def test_get_prohibition_status_checks_halt_first(
        self,
        service: UserContentProhibitionService,
        mock_halt_checker: AsyncMock,
        content_repository: UserContentRepositoryStub,
    ) -> None:
        """Test get_content_prohibition_status checks halt state first."""
        mock_halt_checker.is_halted.return_value = True

        # Add some content
        now = datetime.now(timezone.utc)
        content = UserContent(
            content_id="uc_123",
            owner_id="user_456",
            content="Content",
            title="Title",
            status=UserContentStatus.ACTIVE,
            featured_status=FeaturedStatus.NOT_FEATURED,
            created_at=now,
        )
        content_repository.add_content(content)

        with pytest.raises(SystemHaltedError):
            await service.get_content_prohibition_status("uc_123")

    @pytest.mark.asyncio
    async def test_clear_prohibition_flag_checks_halt_first(
        self,
        service: UserContentProhibitionService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test clear_prohibition_flag checks halt state first."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError):
            await service.clear_prohibition_flag("uc_123", "admin override")


class TestCleanContentFeaturing:
    """Tests for clean content that can be featured."""

    @pytest.mark.asyncio
    async def test_clean_content_returns_pending_review_status(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test clean content returns PENDING_REVIEW featured status."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()

        content = await service.evaluate_for_featuring(sample_request)

        assert content.featured_status == FeaturedStatus.PENDING_REVIEW
        assert content.status == UserContentStatus.ACTIVE
        assert content.prohibition_flag is None
        assert content.is_flagged is False

    @pytest.mark.asyncio
    async def test_clean_content_is_saved_to_repository(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        content_repository: UserContentRepositoryStub,
        sample_request: FeatureRequest,
    ) -> None:
        """Test clean content is saved to repository."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()

        await service.evaluate_for_featuring(sample_request)

        saved = await content_repository.get_content(sample_request.content_id)
        assert saved is not None
        assert saved.content_id == sample_request.content_id
        assert saved.featured_status == FeaturedStatus.PENDING_REVIEW

    @pytest.mark.asyncio
    async def test_clean_content_writes_cleared_event(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test clean content writes USER_CONTENT_CLEARED event (CT-12)."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()

        await service.evaluate_for_featuring(sample_request)

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == USER_CONTENT_CLEARED_EVENT_TYPE
        assert call_kwargs["agent_id"] == USER_CONTENT_SCANNER_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_clean_content_event_payload_is_correct(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test clean content event payload contains correct data."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()

        await service.evaluate_for_featuring(sample_request)

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert payload["content_id"] == sample_request.content_id
        assert payload["owner_id"] == sample_request.owner_id
        assert payload["title"] == sample_request.title


class TestProhibitedContentFlagging:
    """Tests for prohibited content being flagged not deleted (FR58)."""

    @pytest.mark.asyncio
    async def test_prohibited_content_raises_cannot_be_featured_error(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test prohibited content raises UserContentCannotBeFeaturedException."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )

        with pytest.raises(UserContentCannotBeFeaturedException) as exc_info:
            await service.evaluate_for_featuring(sample_request)

        assert exc_info.value.content_id == sample_request.content_id
        assert exc_info.value.owner_id == sample_request.owner_id
        assert "emergence" in exc_info.value.matched_terms

    @pytest.mark.asyncio
    async def test_prohibited_content_is_flagged_not_deleted(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        content_repository: UserContentRepositoryStub,
        sample_request: FeatureRequest,
    ) -> None:
        """Test prohibited content is saved with FLAGGED status (not deleted)."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence", "consciousness")
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(sample_request)

        # Content should still exist (NOT deleted)
        saved = await content_repository.get_content(sample_request.content_id)
        assert saved is not None  # Not deleted
        assert saved.status == UserContentStatus.FLAGGED
        assert saved.featured_status == FeaturedStatus.PROHIBITED
        assert saved.prohibition_flag is not None

    @pytest.mark.asyncio
    async def test_prohibited_content_has_prohibition_flag(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        content_repository: UserContentRepositoryStub,
        sample_request: FeatureRequest,
    ) -> None:
        """Test prohibited content has prohibition flag with matched terms."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence", "consciousness")
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(sample_request)

        saved = await content_repository.get_content(sample_request.content_id)
        assert saved is not None
        assert saved.prohibition_flag is not None
        assert "emergence" in saved.prohibition_flag.matched_terms
        assert "consciousness" in saved.prohibition_flag.matched_terms
        assert saved.prohibition_flag.can_be_featured is False

    @pytest.mark.asyncio
    async def test_prohibited_content_writes_prohibited_event(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test prohibited content writes USER_CONTENT_PROHIBITED event (CT-12)."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(sample_request)

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == USER_CONTENT_PROHIBITED_EVENT_TYPE
        assert call_kwargs["agent_id"] == USER_CONTENT_SCANNER_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_prohibited_event_contains_matched_terms(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test prohibited event contains matched terms in payload."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence", "consciousness")
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(sample_request)

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert "emergence" in payload["matched_terms"]
        assert "consciousness" in payload["matched_terms"]
        assert payload["action_taken"] == "flag_not_feature"

    @pytest.mark.asyncio
    async def test_error_message_includes_fr58(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test error message references FR58."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )

        with pytest.raises(UserContentCannotBeFeaturedException) as exc_info:
            await service.evaluate_for_featuring(sample_request)

        assert "FR58" in str(exc_info.value)


class TestProhibitionFlagPreventsFeturing:
    """Tests for prohibition flag preventing featuring."""

    @pytest.mark.asyncio
    async def test_can_be_featured_is_false_for_prohibited_content(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        content_repository: UserContentRepositoryStub,
        sample_request: FeatureRequest,
    ) -> None:
        """Test can_be_featured property is False for prohibited content."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(sample_request)

        saved = await content_repository.get_content(sample_request.content_id)
        assert saved is not None
        assert saved.can_be_featured is False

    @pytest.mark.asyncio
    async def test_featured_status_is_prohibited(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        content_repository: UserContentRepositoryStub,
        sample_request: FeatureRequest,
    ) -> None:
        """Test featured_status is PROHIBITED for prohibited content."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(sample_request)

        saved = await content_repository.get_content(sample_request.content_id)
        assert saved is not None
        assert saved.featured_status == FeaturedStatus.PROHIBITED

    @pytest.mark.asyncio
    async def test_prohibited_content_appears_in_prohibited_list(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        content_repository: UserContentRepositoryStub,
        sample_request: FeatureRequest,
    ) -> None:
        """Test prohibited content appears in get_prohibited_content_list."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(sample_request)

        prohibited = await service.get_prohibited_content_list()
        assert len(prohibited) == 1
        assert prohibited[0].content_id == sample_request.content_id


class TestBatchEvaluation:
    """Tests for batch content evaluation."""

    @pytest.mark.asyncio
    async def test_batch_evaluate_returns_all_results(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test batch_evaluate returns results for all content."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()
        requests = [
            FeatureRequest(
                content_id=f"uc_{i}",
                owner_id="user_456",
                content=f"Content {i}",
                title=f"Title {i}",
            )
            for i in range(5)
        ]

        results = await service.batch_evaluate_for_featuring(requests)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.content_id == f"uc_{i}"

    @pytest.mark.asyncio
    async def test_batch_evaluate_continues_on_prohibition(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test batch_evaluate continues processing after a prohibition."""
        # First and third clean, second prohibited
        mock_scanner.scan_content.side_effect = [
            ScanResult.no_violations(),
            ScanResult.with_violations(matched_terms=("emergence",)),
            ScanResult.no_violations(),
        ]
        requests = [
            FeatureRequest(
                content_id=f"uc_{i}",
                owner_id="user_456",
                content=f"Content {i}",
                title=f"Title {i}",
            )
            for i in range(3)
        ]

        results = await service.batch_evaluate_for_featuring(requests)

        assert len(results) == 3
        assert results[0].featured_status == FeaturedStatus.PENDING_REVIEW
        assert results[1].featured_status == FeaturedStatus.PROHIBITED
        assert results[2].featured_status == FeaturedStatus.PENDING_REVIEW

    @pytest.mark.asyncio
    async def test_batch_evaluate_empty_list_returns_empty(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test batch_evaluate with empty list returns empty."""
        results = await service.batch_evaluate_for_featuring([])

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_evaluate_writes_event_per_content(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test batch_evaluate writes an event for each content."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()
        requests = [
            FeatureRequest(
                content_id=f"uc_{i}",
                owner_id="user_456",
                content=f"Content {i}",
                title=f"Title {i}",
            )
            for i in range(3)
        ]

        await service.batch_evaluate_for_featuring(requests)

        assert mock_event_writer.write_event.call_count == 3


class TestProhibitionStatusQuery:
    """Tests for prohibition status query."""

    @pytest.mark.asyncio
    async def test_get_status_returns_none_for_clean_content(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test get_content_prohibition_status returns None for clean content."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()

        await service.evaluate_for_featuring(sample_request)
        status = await service.get_content_prohibition_status(sample_request.content_id)

        assert status is None

    @pytest.mark.asyncio
    async def test_get_status_returns_flag_for_prohibited_content(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test get_content_prohibition_status returns flag for prohibited content."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(sample_request)

        status = await service.get_content_prohibition_status(sample_request.content_id)

        assert status is not None
        assert isinstance(status, UserContentProhibitionFlag)
        assert "emergence" in status.matched_terms

    @pytest.mark.asyncio
    async def test_get_status_raises_for_unknown_content(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test get_content_prohibition_status raises for unknown content."""
        with pytest.raises(UserContentNotFoundError) as exc_info:
            await service.get_content_prohibition_status("unknown_id")

        assert exc_info.value.content_id == "unknown_id"
        assert "FR58" in str(exc_info.value)


class TestClearProhibitionFlag:
    """Tests for clearing prohibition flag."""

    @pytest.mark.asyncio
    async def test_clear_flag_returns_updated_content(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test clear_prohibition_flag returns updated content."""
        # First prohibit content
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )
        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(sample_request)

        # Then clear flag
        cleared = await service.clear_prohibition_flag(
            sample_request.content_id, "admin override"
        )

        assert cleared is not None
        assert cleared.status == UserContentStatus.ACTIVE
        assert cleared.featured_status == FeaturedStatus.NOT_FEATURED
        assert cleared.prohibition_flag is None

    @pytest.mark.asyncio
    async def test_clear_flag_writes_cleared_event(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        sample_request: FeatureRequest,
    ) -> None:
        """Test clear_prohibition_flag writes cleared event (CT-12)."""
        # First prohibit content
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )
        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(sample_request)

        # Reset call count
        mock_event_writer.reset_mock()

        # Clear flag
        await service.clear_prohibition_flag(
            sample_request.content_id, "admin override"
        )

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == USER_CONTENT_CLEARED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_clear_flag_raises_for_unknown_content(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test clear_prohibition_flag raises for unknown content."""
        with pytest.raises(UserContentNotFoundError) as exc_info:
            await service.clear_prohibition_flag("unknown_id", "reason")

        assert exc_info.value.content_id == "unknown_id"


class TestFeaturedCandidates:
    """Tests for getting featured candidates."""

    @pytest.mark.asyncio
    async def test_get_featured_candidates_returns_pending_review(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test get_featured_candidates returns PENDING_REVIEW content."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()
        requests = [
            FeatureRequest(
                content_id=f"uc_{i}",
                owner_id="user_456",
                content=f"Content {i}",
                title=f"Title {i}",
            )
            for i in range(3)
        ]

        for req in requests:
            await service.evaluate_for_featuring(req)

        candidates = await service.get_featured_candidates()

        assert len(candidates) == 3
        for candidate in candidates:
            assert candidate.featured_status == FeaturedStatus.PENDING_REVIEW

    @pytest.mark.asyncio
    async def test_get_featured_candidates_excludes_prohibited(
        self,
        service: UserContentProhibitionService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test get_featured_candidates excludes prohibited content."""
        # First clean, second prohibited, third clean
        mock_scanner.scan_content.side_effect = [
            ScanResult.no_violations(),
            ScanResult.with_violations(matched_terms=("emergence",)),
            ScanResult.no_violations(),
        ]
        requests = [
            FeatureRequest(
                content_id=f"uc_{i}",
                owner_id="user_456",
                content=f"Content {i}",
                title=f"Title {i}",
            )
            for i in range(3)
        ]

        for req in requests:
            with contextlib.suppress(UserContentCannotBeFeaturedException):
                await service.evaluate_for_featuring(req)

        candidates = await service.get_featured_candidates()

        assert len(candidates) == 2
        assert all(
            c.featured_status == FeaturedStatus.PENDING_REVIEW for c in candidates
        )

    @pytest.mark.asyncio
    async def test_get_featured_candidates_checks_halt_first(
        self,
        service: UserContentProhibitionService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test get_featured_candidates checks halt state first."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError):
            await service.get_featured_candidates()
