"""Integration tests for user content prohibition (Story 9.4, FR58).

Tests the complete user content prohibition workflow including:
- Feature evaluation flow
- Content flagging (NOT deletion)
- Event writing and witnessing
- Batch evaluation workflow
- Prohibition status queries
- Clear prohibition flag flow

CRITICAL DISTINCTION from Publication Scanning (Story 9.2):
- Publications: BLOCK content -> don't publish
- User Content: FLAG content -> allow to exist, prevent featuring

These tests use real implementations (stubs) instead of mocks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

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
)
from src.domain.models.user_content import (
    FeatureRequest,
    FeaturedStatus,
    UserContentStatus,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.prohibited_language_scanner_stub import (
    ProhibitedLanguageScannerStub,
)
from src.infrastructure.stubs.user_content_repository_stub import (
    UserContentRepositoryStub,
)


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def scanner() -> ProhibitedLanguageScannerStub:
    """Create prohibited language scanner stub."""
    return ProhibitedLanguageScannerStub()


@pytest.fixture
def content_repository() -> UserContentRepositoryStub:
    """Create user content repository stub."""
    return UserContentRepositoryStub()


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create mock event writer for integration tests."""
    writer = AsyncMock()
    writer.write_event.return_value = None
    return writer


@pytest.fixture
def service(
    content_repository: UserContentRepositoryStub,
    scanner: ProhibitedLanguageScannerStub,
    mock_event_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> UserContentProhibitionService:
    """Create user content prohibition service with real stubs."""
    return UserContentProhibitionService(
        content_repository=content_repository,
        scanner=scanner,
        event_writer=mock_event_writer,
        halt_checker=halt_checker,
    )


class TestFeatureEvaluationFlow:
    """Tests for end-to-end feature evaluation flow."""

    @pytest.mark.asyncio
    async def test_clean_content_becomes_pending_review(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test clean content gets PENDING_REVIEW status (FR58, AC1)."""
        request = FeatureRequest(
            content_id="uc_clean_001",
            owner_id="user_456",
            content="This is a completely normal article about software.",
            title="Clean Article",
        )

        content = await service.evaluate_for_featuring(request)

        assert content.featured_status == FeaturedStatus.PENDING_REVIEW
        assert content.status == UserContentStatus.ACTIVE
        assert content.prohibition_flag is None
        assert content.can_be_featured is True

    @pytest.mark.asyncio
    async def test_content_with_emergence_is_flagged(
        self,
        service: UserContentProhibitionService,
        content_repository: UserContentRepositoryStub,
    ) -> None:
        """Test content containing 'emergence' is FLAGGED (FR58, AC3)."""
        request = FeatureRequest(
            content_id="uc_flagged_001",
            owner_id="user_456",
            content="Our AI system has achieved emergence.",
            title="Flagged Article",
        )

        with pytest.raises(UserContentCannotBeFeaturedException) as exc_info:
            await service.evaluate_for_featuring(request)

        assert "emergence" in exc_info.value.matched_terms
        assert exc_info.value.content_id == "uc_flagged_001"

        # CRITICAL: Content exists (not deleted)
        saved = await content_repository.get_content("uc_flagged_001")
        assert saved is not None
        assert saved.status == UserContentStatus.FLAGGED
        assert saved.featured_status == FeaturedStatus.PROHIBITED

    @pytest.mark.asyncio
    async def test_content_with_consciousness_is_flagged(
        self,
        service: UserContentProhibitionService,
        content_repository: UserContentRepositoryStub,
    ) -> None:
        """Test content containing 'consciousness' is FLAGGED (FR58, AC3)."""
        request = FeatureRequest(
            content_id="uc_flagged_002",
            owner_id="user_456",
            content="The system exhibits signs of consciousness.",
            title="Consciousness Article",
        )

        with pytest.raises(UserContentCannotBeFeaturedException) as exc_info:
            await service.evaluate_for_featuring(request)

        assert "consciousness" in exc_info.value.matched_terms

        # CRITICAL: Content exists (not deleted)
        saved = await content_repository.get_content("uc_flagged_002")
        assert saved is not None

    @pytest.mark.asyncio
    async def test_content_with_sentience_is_flagged(
        self,
        service: UserContentProhibitionService,
        content_repository: UserContentRepositoryStub,
    ) -> None:
        """Test content containing 'sentience' is FLAGGED (FR58, AC3)."""
        request = FeatureRequest(
            content_id="uc_flagged_003",
            owner_id="user_456",
            content="We believe our AI has achieved sentience.",
            title="Sentience Article",
        )

        with pytest.raises(UserContentCannotBeFeaturedException) as exc_info:
            await service.evaluate_for_featuring(request)

        assert "sentience" in exc_info.value.matched_terms

        # CRITICAL: Content exists (not deleted)
        saved = await content_repository.get_content("uc_flagged_003")
        assert saved is not None

    @pytest.mark.asyncio
    async def test_content_with_multiple_terms_all_captured(
        self,
        service: UserContentProhibitionService,
        content_repository: UserContentRepositoryStub,
    ) -> None:
        """Test content with multiple terms captures all terms."""
        request = FeatureRequest(
            content_id="uc_multi_001",
            owner_id="user_456",
            content="The emergence of consciousness leads to sentience.",
            title="Multi-Term Article",
        )

        with pytest.raises(UserContentCannotBeFeaturedException) as exc_info:
            await service.evaluate_for_featuring(request)

        # All three terms should be captured
        assert len(exc_info.value.matched_terms) >= 3

        saved = await content_repository.get_content("uc_multi_001")
        assert saved is not None
        assert saved.prohibition_flag is not None
        assert len(saved.prohibition_flag.matched_terms) >= 3


class TestFlagNotDeleteCriticalDistinction:
    """Tests for the CRITICAL FR58 distinction: FLAG not DELETE."""

    @pytest.mark.asyncio
    async def test_prohibited_content_exists_after_flagging(
        self,
        service: UserContentProhibitionService,
        content_repository: UserContentRepositoryStub,
    ) -> None:
        """Test prohibited content still exists after flagging (FR58 CRITICAL)."""
        request = FeatureRequest(
            content_id="uc_exists_001",
            owner_id="user_456",
            content="AI emergence is happening.",
            title="Still Exists Article",
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(request)

        # CRITICAL: Content MUST exist
        content = await content_repository.get_content("uc_exists_001")
        assert content is not None, "FR58: Content must NOT be deleted"

    @pytest.mark.asyncio
    async def test_prohibited_content_still_has_original_content(
        self,
        service: UserContentProhibitionService,
        content_repository: UserContentRepositoryStub,
    ) -> None:
        """Test prohibited content preserves original content."""
        original_text = "AI emergence is real and happening now."
        request = FeatureRequest(
            content_id="uc_preserved_001",
            owner_id="user_456",
            content=original_text,
            title="Preserved Content",
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(request)

        saved = await content_repository.get_content("uc_preserved_001")
        assert saved is not None
        assert saved.content == original_text  # Original preserved

    @pytest.mark.asyncio
    async def test_prohibited_content_owner_preserved(
        self,
        service: UserContentProhibitionService,
        content_repository: UserContentRepositoryStub,
    ) -> None:
        """Test prohibited content preserves owner ID."""
        request = FeatureRequest(
            content_id="uc_owner_001",
            owner_id="original_user_789",
            content="Consciousness emerging in AI.",
            title="Owner Preserved",
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(request)

        saved = await content_repository.get_content("uc_owner_001")
        assert saved is not None
        assert saved.owner_id == "original_user_789"  # Owner preserved


class TestEventWritingFlow:
    """Tests for event writing and witnessing (CT-12)."""

    @pytest.mark.asyncio
    async def test_clean_content_writes_cleared_event(
        self,
        service: UserContentProhibitionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test clean content writes USER_CONTENT_CLEARED event (CT-12)."""
        request = FeatureRequest(
            content_id="uc_event_clean_001",
            owner_id="user_456",
            content="Clean content for event testing.",
            title="Event Test Clean",
        )

        await service.evaluate_for_featuring(request)

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == USER_CONTENT_CLEARED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_prohibited_content_writes_prohibited_event(
        self,
        service: UserContentProhibitionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test prohibited content writes USER_CONTENT_PROHIBITED event (CT-12)."""
        request = FeatureRequest(
            content_id="uc_event_prohibited_001",
            owner_id="user_456",
            content="Emergence detected in AI.",
            title="Event Test Prohibited",
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(request)

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == USER_CONTENT_PROHIBITED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_prohibited_event_contains_action_flag_not_feature(
        self,
        service: UserContentProhibitionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test prohibited event action_taken is 'flag_not_feature' (FR58)."""
        request = FeatureRequest(
            content_id="uc_action_001",
            owner_id="user_456",
            content="Consciousness in AI.",
            title="Action Test",
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(request)

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert payload["action_taken"] == "flag_not_feature"


class TestBatchEvaluationFlow:
    """Tests for batch content evaluation workflow."""

    @pytest.mark.asyncio
    async def test_batch_processes_all_content(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test batch evaluation processes all content items."""
        requests = [
            FeatureRequest(
                content_id=f"uc_batch_{i}",
                owner_id="user_456",
                content=f"Clean content {i}",
                title=f"Batch Title {i}",
            )
            for i in range(5)
        ]

        results = await service.batch_evaluate_for_featuring(requests)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.content_id == f"uc_batch_{i}"
            assert result.featured_status == FeaturedStatus.PENDING_REVIEW

    @pytest.mark.asyncio
    async def test_batch_continues_after_prohibition(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test batch continues processing after finding prohibited content."""
        requests = [
            FeatureRequest(
                content_id="uc_batch_clean_1",
                owner_id="user_456",
                content="Clean content 1",
                title="Clean 1",
            ),
            FeatureRequest(
                content_id="uc_batch_flagged",
                owner_id="user_456",
                content="Emergence detected here.",
                title="Flagged",
            ),
            FeatureRequest(
                content_id="uc_batch_clean_2",
                owner_id="user_456",
                content="Clean content 2",
                title="Clean 2",
            ),
        ]

        results = await service.batch_evaluate_for_featuring(requests)

        assert len(results) == 3
        assert results[0].featured_status == FeaturedStatus.PENDING_REVIEW
        assert results[1].featured_status == FeaturedStatus.PROHIBITED
        assert results[2].featured_status == FeaturedStatus.PENDING_REVIEW

    @pytest.mark.asyncio
    async def test_batch_writes_event_for_each_content(
        self,
        service: UserContentProhibitionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test batch writes event for each content item (CT-12)."""
        requests = [
            FeatureRequest(
                content_id=f"uc_batch_event_{i}",
                owner_id="user_456",
                content=f"Clean content {i}",
                title=f"Event Batch {i}",
            )
            for i in range(3)
        ]

        await service.batch_evaluate_for_featuring(requests)

        assert mock_event_writer.write_event.call_count == 3


class TestProhibitionStatusQueries:
    """Tests for prohibition status queries."""

    @pytest.mark.asyncio
    async def test_get_prohibited_content_returns_flagged(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test get_prohibited_content_list returns flagged content."""
        # Create some clean and some prohibited content
        clean_request = FeatureRequest(
            content_id="uc_query_clean",
            owner_id="user_456",
            content="Clean content here.",
            title="Clean",
        )
        prohibited_request = FeatureRequest(
            content_id="uc_query_prohibited",
            owner_id="user_456",
            content="Emergence in AI.",
            title="Prohibited",
        )

        await service.evaluate_for_featuring(clean_request)
        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(prohibited_request)

        prohibited = await service.get_prohibited_content_list()

        assert len(prohibited) == 1
        assert prohibited[0].content_id == "uc_query_prohibited"

    @pytest.mark.asyncio
    async def test_get_featured_candidates_excludes_prohibited(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test get_featured_candidates excludes prohibited content."""
        clean_request = FeatureRequest(
            content_id="uc_candidate_clean",
            owner_id="user_456",
            content="Clean candidate content.",
            title="Candidate",
        )
        prohibited_request = FeatureRequest(
            content_id="uc_candidate_prohibited",
            owner_id="user_456",
            content="Consciousness detected.",
            title="Not Candidate",
        )

        await service.evaluate_for_featuring(clean_request)
        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(prohibited_request)

        candidates = await service.get_featured_candidates()

        assert len(candidates) == 1
        assert candidates[0].content_id == "uc_candidate_clean"

    @pytest.mark.asyncio
    async def test_get_prohibition_status_returns_flag(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test get_content_prohibition_status returns flag for prohibited content."""
        request = FeatureRequest(
            content_id="uc_status_001",
            owner_id="user_456",
            content="Emergence in AI system.",
            title="Status Test",
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(request)

        status = await service.get_content_prohibition_status("uc_status_001")

        assert status is not None
        assert "emergence" in status.matched_terms
        assert status.can_be_featured is False


class TestClearProhibitionFlow:
    """Tests for clearing prohibition flag workflow."""

    @pytest.mark.asyncio
    async def test_clear_prohibition_restores_active_status(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test clearing prohibition flag restores ACTIVE status."""
        request = FeatureRequest(
            content_id="uc_clear_001",
            owner_id="user_456",
            content="Emergence detected.",
            title="To Clear",
        )

        # First prohibit
        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(request)

        # Then clear
        cleared = await service.clear_prohibition_flag(
            "uc_clear_001", "Admin review override"
        )

        assert cleared.status == UserContentStatus.ACTIVE
        assert cleared.featured_status == FeaturedStatus.NOT_FEATURED
        assert cleared.prohibition_flag is None

    @pytest.mark.asyncio
    async def test_clear_prohibition_writes_cleared_event(
        self,
        service: UserContentProhibitionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test clearing prohibition writes USER_CONTENT_CLEARED event (CT-12)."""
        request = FeatureRequest(
            content_id="uc_clear_event_001",
            owner_id="user_456",
            content="Consciousness in AI.",
            title="Clear Event Test",
        )

        # First prohibit
        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(request)

        # Reset call count
        mock_event_writer.reset_mock()

        # Then clear
        await service.clear_prohibition_flag(
            "uc_clear_event_001", "Admin review"
        )

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == USER_CONTENT_CLEARED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_clear_nonexistent_raises_not_found(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test clearing nonexistent content raises UserContentNotFoundError."""
        with pytest.raises(UserContentNotFoundError) as exc_info:
            await service.clear_prohibition_flag("nonexistent_id", "test")

        assert exc_info.value.content_id == "nonexistent_id"


class TestHaltCheckIntegration:
    """Tests for halt check integration (CT-11)."""

    @pytest.mark.asyncio
    async def test_evaluate_respects_halt(
        self,
        service: UserContentProhibitionService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test evaluate_for_featuring respects halt state (CT-11)."""
        halt_checker.set_halted(True)

        request = FeatureRequest(
            content_id="uc_halt_001",
            owner_id="user_456",
            content="Clean content.",
            title="Halt Test",
        )

        with pytest.raises(SystemHaltedError):
            await service.evaluate_for_featuring(request)

    @pytest.mark.asyncio
    async def test_batch_evaluate_respects_halt(
        self,
        service: UserContentProhibitionService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test batch_evaluate respects halt state (CT-11)."""
        halt_checker.set_halted(True)

        requests = [
            FeatureRequest(
                content_id="uc_halt_batch_001",
                owner_id="user_456",
                content="Clean content.",
                title="Halt Batch Test",
            )
        ]

        with pytest.raises(SystemHaltedError):
            await service.batch_evaluate_for_featuring(requests)

    @pytest.mark.asyncio
    async def test_query_operations_respect_halt(
        self,
        service: UserContentProhibitionService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test query operations respect halt state (CT-11)."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.get_prohibited_content_list()

        with pytest.raises(SystemHaltedError):
            await service.get_featured_candidates()


class TestCaseInsensitiveMatching:
    """Tests for case-insensitive prohibited term matching."""

    @pytest.mark.asyncio
    async def test_mixed_case_detected(
        self,
        service: UserContentProhibitionService,
    ) -> None:
        """Test mixed case variants are detected."""
        request = FeatureRequest(
            content_id="uc_case_001",
            owner_id="user_456",
            content="AI system EMERGENCE is happening.",
            title="Case Test",
        )

        with pytest.raises(UserContentCannotBeFeaturedException):
            await service.evaluate_for_featuring(request)
