"""Unit tests for user content domain models (Story 9.4, FR58).

Tests UserContent, UserContentStatus, FeaturedStatus, and
UserContentProhibitionFlag domain models.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.models.user_content import (
    USER_CONTENT_ID_PREFIX,
    USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
    FeatureRequest,
    FeaturedStatus,
    UserContent,
    UserContentProhibitionFlag,
    UserContentStatus,
)


class TestUserContentStatus:
    """Tests for UserContentStatus enum."""

    def test_active_status_value(self) -> None:
        """Test ACTIVE status has correct value."""
        assert UserContentStatus.ACTIVE.value == "active"

    def test_flagged_status_value(self) -> None:
        """Test FLAGGED status has correct value."""
        assert UserContentStatus.FLAGGED.value == "flagged"

    def test_removed_status_value(self) -> None:
        """Test REMOVED status has correct value."""
        assert UserContentStatus.REMOVED.value == "removed"


class TestFeaturedStatus:
    """Tests for FeaturedStatus enum."""

    def test_not_featured_value(self) -> None:
        """Test NOT_FEATURED status has correct value."""
        assert FeaturedStatus.NOT_FEATURED.value == "not_featured"

    def test_pending_review_value(self) -> None:
        """Test PENDING_REVIEW status has correct value."""
        assert FeaturedStatus.PENDING_REVIEW.value == "pending_review"

    def test_featured_value(self) -> None:
        """Test FEATURED status has correct value."""
        assert FeaturedStatus.FEATURED.value == "featured"

    def test_prohibited_value(self) -> None:
        """Test PROHIBITED status has correct value."""
        assert FeaturedStatus.PROHIBITED.value == "prohibited"


class TestUserContentProhibitionFlag:
    """Tests for UserContentProhibitionFlag dataclass."""

    def test_create_valid_flag(self) -> None:
        """Test creating a valid prohibition flag."""
        now = datetime.now(timezone.utc)
        flag = UserContentProhibitionFlag(
            flagged_at=now,
            matched_terms=("emergence", "consciousness"),
            can_be_featured=False,
            reviewed_by=USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
        )

        assert flag.flagged_at == now
        assert flag.matched_terms == ("emergence", "consciousness")
        assert flag.can_be_featured is False
        assert flag.reviewed_by == USER_CONTENT_SCANNER_SYSTEM_AGENT_ID

    def test_can_be_featured_must_be_false(self) -> None:
        """Test that can_be_featured must be False."""
        with pytest.raises(ValueError, match="FR58"):
            UserContentProhibitionFlag(
                flagged_at=datetime.now(timezone.utc),
                matched_terms=("emergence",),
                can_be_featured=True,  # Invalid
            )

    def test_matched_terms_required(self) -> None:
        """Test that matched_terms cannot be empty."""
        with pytest.raises(ValueError, match="FR58"):
            UserContentProhibitionFlag(
                flagged_at=datetime.now(timezone.utc),
                matched_terms=(),  # Invalid
                can_be_featured=False,
            )

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        now = datetime.now(timezone.utc)
        flag = UserContentProhibitionFlag(
            flagged_at=now,
            matched_terms=("emergence",),
            can_be_featured=False,
            reviewed_by="test_reviewer",
        )

        data = flag.to_dict()
        assert data["flagged_at"] == now.isoformat()
        assert data["matched_terms"] == ["emergence"]
        assert data["can_be_featured"] is False
        assert data["reviewed_by"] == "test_reviewer"

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        now = datetime.now(timezone.utc)
        data = {
            "flagged_at": now.isoformat(),
            "matched_terms": ["emergence", "consciousness"],
            "can_be_featured": False,
            "reviewed_by": "test_reviewer",
        }

        flag = UserContentProhibitionFlag.from_dict(data)
        assert flag.matched_terms == ("emergence", "consciousness")
        assert flag.can_be_featured is False


class TestUserContent:
    """Tests for UserContent dataclass."""

    def test_create_active_content(self) -> None:
        """Test creating active user content."""
        now = datetime.now(timezone.utc)
        content = UserContent(
            content_id="uc_123",
            owner_id="user_456",
            content="Some article content",
            title="My Article",
            status=UserContentStatus.ACTIVE,
            featured_status=FeaturedStatus.NOT_FEATURED,
            created_at=now,
            prohibition_flag=None,
        )

        assert content.content_id == "uc_123"
        assert content.owner_id == "user_456"
        assert content.status == UserContentStatus.ACTIVE
        assert content.featured_status == FeaturedStatus.NOT_FEATURED
        assert content.prohibition_flag is None
        assert content.is_flagged is False

    def test_create_flagged_content(self) -> None:
        """Test creating flagged user content."""
        now = datetime.now(timezone.utc)
        flag = UserContentProhibitionFlag(
            flagged_at=now,
            matched_terms=("emergence",),
            can_be_featured=False,
        )
        content = UserContent(
            content_id="uc_123",
            owner_id="user_456",
            content="Some article content",
            title="My Article",
            status=UserContentStatus.FLAGGED,
            featured_status=FeaturedStatus.PROHIBITED,
            created_at=now,
            prohibition_flag=flag,
        )

        assert content.status == UserContentStatus.FLAGGED
        assert content.featured_status == FeaturedStatus.PROHIBITED
        assert content.prohibition_flag is not None
        assert content.is_flagged is True

    def test_content_id_required(self) -> None:
        """Test that content_id is required."""
        with pytest.raises(ValueError, match="FR58.*content_id"):
            UserContent(
                content_id="",
                owner_id="user_456",
                content="Some content",
                title="Title",
                status=UserContentStatus.ACTIVE,
                featured_status=FeaturedStatus.NOT_FEATURED,
                created_at=datetime.now(timezone.utc),
            )

    def test_owner_id_required(self) -> None:
        """Test that owner_id is required."""
        with pytest.raises(ValueError, match="FR58.*owner_id"):
            UserContent(
                content_id="uc_123",
                owner_id="",
                content="Some content",
                title="Title",
                status=UserContentStatus.ACTIVE,
                featured_status=FeaturedStatus.NOT_FEATURED,
                created_at=datetime.now(timezone.utc),
            )

    def test_title_required(self) -> None:
        """Test that title is required."""
        with pytest.raises(ValueError, match="FR58.*title"):
            UserContent(
                content_id="uc_123",
                owner_id="user_456",
                content="Some content",
                title="",
                status=UserContentStatus.ACTIVE,
                featured_status=FeaturedStatus.NOT_FEATURED,
                created_at=datetime.now(timezone.utc),
            )

    def test_flagged_status_requires_flag(self) -> None:
        """Test that FLAGGED status requires prohibition_flag."""
        with pytest.raises(ValueError, match="FR58.*FLAGGED.*prohibition_flag"):
            UserContent(
                content_id="uc_123",
                owner_id="user_456",
                content="Some content",
                title="Title",
                status=UserContentStatus.FLAGGED,
                featured_status=FeaturedStatus.NOT_FEATURED,
                created_at=datetime.now(timezone.utc),
                prohibition_flag=None,  # Invalid
            )

    def test_prohibited_status_requires_flag(self) -> None:
        """Test that PROHIBITED featured_status requires prohibition_flag."""
        with pytest.raises(ValueError, match="FR58.*PROHIBITED.*prohibition_flag"):
            UserContent(
                content_id="uc_123",
                owner_id="user_456",
                content="Some content",
                title="Title",
                status=UserContentStatus.ACTIVE,
                featured_status=FeaturedStatus.PROHIBITED,
                created_at=datetime.now(timezone.utc),
                prohibition_flag=None,  # Invalid
            )

    def test_flag_requires_flagged_status(self) -> None:
        """Test that prohibition_flag requires FLAGGED status."""
        now = datetime.now(timezone.utc)
        flag = UserContentProhibitionFlag(
            flagged_at=now,
            matched_terms=("emergence",),
            can_be_featured=False,
        )
        with pytest.raises(ValueError, match="FR58.*prohibition_flag.*FLAGGED"):
            UserContent(
                content_id="uc_123",
                owner_id="user_456",
                content="Some content",
                title="Title",
                status=UserContentStatus.ACTIVE,  # Invalid with flag
                featured_status=FeaturedStatus.NOT_FEATURED,
                created_at=now,
                prohibition_flag=flag,
            )

    def test_can_be_featured_property(self) -> None:
        """Test can_be_featured property."""
        now = datetime.now(timezone.utc)

        # Active content with pending review can be featured
        content = UserContent(
            content_id="uc_123",
            owner_id="user_456",
            content="Some content",
            title="Title",
            status=UserContentStatus.ACTIVE,
            featured_status=FeaturedStatus.PENDING_REVIEW,
            created_at=now,
        )
        assert content.can_be_featured is True

        # Prohibited content cannot be featured
        flag = UserContentProhibitionFlag(
            flagged_at=now,
            matched_terms=("emergence",),
            can_be_featured=False,
        )
        prohibited_content = UserContent(
            content_id="uc_124",
            owner_id="user_456",
            content="Some content",
            title="Title",
            status=UserContentStatus.FLAGGED,
            featured_status=FeaturedStatus.PROHIBITED,
            created_at=now,
            prohibition_flag=flag,
        )
        assert prohibited_content.can_be_featured is False

    def test_with_prohibition_flag(self) -> None:
        """Test with_prohibition_flag method."""
        now = datetime.now(timezone.utc)
        content = UserContent(
            content_id="uc_123",
            owner_id="user_456",
            content="Some content",
            title="Title",
            status=UserContentStatus.ACTIVE,
            featured_status=FeaturedStatus.NOT_FEATURED,
            created_at=now,
        )

        flag = UserContentProhibitionFlag(
            flagged_at=now,
            matched_terms=("emergence",),
            can_be_featured=False,
        )
        flagged_content = content.with_prohibition_flag(flag)

        # Original unchanged (immutable)
        assert content.status == UserContentStatus.ACTIVE
        assert content.prohibition_flag is None

        # New content is flagged
        assert flagged_content.status == UserContentStatus.FLAGGED
        assert flagged_content.featured_status == FeaturedStatus.PROHIBITED
        assert flagged_content.prohibition_flag == flag
        assert flagged_content.content_id == content.content_id

    def test_with_cleared_for_featuring(self) -> None:
        """Test with_cleared_for_featuring method."""
        now = datetime.now(timezone.utc)
        content = UserContent(
            content_id="uc_123",
            owner_id="user_456",
            content="Some content",
            title="Title",
            status=UserContentStatus.ACTIVE,
            featured_status=FeaturedStatus.NOT_FEATURED,
            created_at=now,
        )

        cleared = content.with_cleared_for_featuring()

        assert cleared.status == UserContentStatus.ACTIVE
        assert cleared.featured_status == FeaturedStatus.PENDING_REVIEW
        assert cleared.prohibition_flag is None

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        now = datetime.now(timezone.utc)
        content = UserContent(
            content_id="uc_123",
            owner_id="user_456",
            content="Some content",
            title="Title",
            status=UserContentStatus.ACTIVE,
            featured_status=FeaturedStatus.NOT_FEATURED,
            created_at=now,
        )

        data = content.to_dict()
        assert data["content_id"] == "uc_123"
        assert data["owner_id"] == "user_456"
        assert data["status"] == "active"
        assert data["featured_status"] == "not_featured"
        assert data["prohibition_flag"] is None


class TestFeatureRequest:
    """Tests for FeatureRequest dataclass."""

    def test_create_valid_request(self) -> None:
        """Test creating a valid feature request."""
        request = FeatureRequest(
            content_id="uc_123",
            owner_id="user_456",
            content="Article content here",
            title="My Article",
        )

        assert request.content_id == "uc_123"
        assert request.owner_id == "user_456"
        assert request.content == "Article content here"
        assert request.title == "My Article"

    def test_content_id_required(self) -> None:
        """Test that content_id is required."""
        with pytest.raises(ValueError, match="FR58.*content_id"):
            FeatureRequest(
                content_id="",
                owner_id="user_456",
                content="Content",
                title="Title",
            )

    def test_owner_id_required(self) -> None:
        """Test that owner_id is required."""
        with pytest.raises(ValueError, match="FR58.*owner_id"):
            FeatureRequest(
                content_id="uc_123",
                owner_id="",
                content="Content",
                title="Title",
            )

    def test_title_required(self) -> None:
        """Test that title is required."""
        with pytest.raises(ValueError, match="FR58.*title"):
            FeatureRequest(
                content_id="uc_123",
                owner_id="user_456",
                content="Content",
                title="",
            )

    def test_to_user_content(self) -> None:
        """Test converting FeatureRequest to UserContent."""
        request = FeatureRequest(
            content_id="uc_123",
            owner_id="user_456",
            content="Article content",
            title="My Article",
        )

        content = request.to_user_content(
            status=UserContentStatus.ACTIVE,
            featured_status=FeaturedStatus.PENDING_REVIEW,
        )

        assert content.content_id == request.content_id
        assert content.owner_id == request.owner_id
        assert content.content == request.content
        assert content.title == request.title
        assert content.status == UserContentStatus.ACTIVE
        assert content.featured_status == FeaturedStatus.PENDING_REVIEW


class TestConstants:
    """Tests for module constants."""

    def test_user_content_id_prefix(self) -> None:
        """Test USER_CONTENT_ID_PREFIX value."""
        assert USER_CONTENT_ID_PREFIX == "uc_"

    def test_system_agent_id(self) -> None:
        """Test USER_CONTENT_SCANNER_SYSTEM_AGENT_ID value."""
        assert USER_CONTENT_SCANNER_SYSTEM_AGENT_ID == "system:user_content_scanner"
