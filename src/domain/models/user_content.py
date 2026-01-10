"""User content domain models (Story 9.4, FR58).

This module provides domain models for user-generated content that
is subject to prohibited language screening for featuring/curation
but NOT deletion.

Constitutional Constraints:
- FR58: User content subject to same prohibition for featuring
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All prohibition events must be witnessed

CRITICAL DISTINCTION:
- User content is FLAGGED, not deleted
- User content belongs to the user
- Only featuring/curation is blocked
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final


# Constants
USER_CONTENT_ID_PREFIX: Final[str] = "uc_"
USER_CONTENT_SCANNER_SYSTEM_AGENT_ID: Final[str] = "system:user_content_scanner"


class UserContentStatus(str, Enum):
    """Status of user content (FR58).

    Represents the lifecycle state of user-generated content.
    FLAGGED indicates content has prohibition flag but is NOT deleted.
    """

    ACTIVE = "active"  # Normal content, no issues
    FLAGGED = "flagged"  # Has prohibition flag, cannot be featured
    REMOVED = "removed"  # User deleted their own content


class FeaturedStatus(str, Enum):
    """Featured eligibility status (FR58).

    Tracks whether content can be featured/curated.
    PROHIBITED means content cannot be featured due to prohibited language.
    """

    NOT_FEATURED = "not_featured"  # Default state
    PENDING_REVIEW = "pending_review"  # Passed scan, awaiting curation decision
    FEATURED = "featured"  # Currently featured/curated
    PROHIBITED = "prohibited"  # Cannot be featured due to prohibited language


@dataclass(frozen=True, eq=True)
class UserContentProhibitionFlag:
    """Flag indicating content cannot be featured (FR58).

    This flag is applied to user content when prohibited language is detected.
    The content is NOT deleted (belongs to user), only prevented from featuring.

    Attributes:
        flagged_at: When the content was flagged.
        matched_terms: Prohibited terms that were detected.
        can_be_featured: Always False when flagged (enforced in __post_init__).
        reviewed_by: Agent/system that performed the scan.
    """

    flagged_at: datetime
    matched_terms: tuple[str, ...]
    can_be_featured: bool = False
    reviewed_by: str | None = None

    def __post_init__(self) -> None:
        """Validate flag per FR58.

        Raises:
            ValueError: If validation fails with FR58 reference.
        """
        if self.can_be_featured:
            raise ValueError(
                "FR58: UserContentProhibitionFlag.can_be_featured must be False"
            )

        if not self.matched_terms:
            raise ValueError("FR58: UserContentProhibitionFlag requires matched_terms")

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "flagged_at": self.flagged_at.isoformat(),
            "matched_terms": list(self.matched_terms),
            "can_be_featured": self.can_be_featured,
            "reviewed_by": self.reviewed_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> UserContentProhibitionFlag:
        """Create from dictionary.

        Args:
            data: Dictionary with flag data.

        Returns:
            UserContentProhibitionFlag instance.
        """
        flagged_at = data["flagged_at"]
        if isinstance(flagged_at, str):
            flagged_at = datetime.fromisoformat(flagged_at)

        return cls(
            flagged_at=flagged_at,
            matched_terms=tuple(data["matched_terms"]),  # type: ignore[arg-type]
            can_be_featured=data.get("can_be_featured", False),  # type: ignore[arg-type]
            reviewed_by=data.get("reviewed_by"),  # type: ignore[arg-type]
        )


@dataclass(frozen=True, eq=True)
class UserContent:
    """User-generated content subject to prohibition scanning (FR58).

    This model represents content created by users. When prohibited
    language is detected:
    - Content is NOT deleted (user's property)
    - Content is FLAGGED (status = FLAGGED)
    - Content cannot be featured (featured_status = PROHIBITED)

    Attributes:
        content_id: Unique identifier for the content.
        owner_id: User who owns the content.
        content: The actual content text.
        title: Content title.
        status: Current content status (ACTIVE, FLAGGED, REMOVED).
        featured_status: Featured eligibility status.
        prohibition_flag: Flag if content is prohibited (None if clean).
        created_at: When content was created.
    """

    content_id: str
    owner_id: str
    content: str
    title: str
    status: UserContentStatus
    featured_status: FeaturedStatus
    created_at: datetime
    prohibition_flag: UserContentProhibitionFlag | None = None

    def __post_init__(self) -> None:
        """Validate content per FR58.

        Raises:
            ValueError: If validation fails with FR58 reference.
        """
        if not self.content_id:
            raise ValueError("FR58: content_id is required")

        if not self.owner_id:
            raise ValueError("FR58: owner_id is required")

        if not self.title:
            raise ValueError("FR58: title is required")

        # Consistency checks
        if self.status == UserContentStatus.FLAGGED and not self.prohibition_flag:
            raise ValueError(
                "FR58: FLAGGED status requires prohibition_flag"
            )

        if (
            self.featured_status == FeaturedStatus.PROHIBITED
            and not self.prohibition_flag
        ):
            raise ValueError(
                "FR58: PROHIBITED featured_status requires prohibition_flag"
            )

        if self.prohibition_flag and self.status != UserContentStatus.FLAGGED:
            raise ValueError(
                "FR58: prohibition_flag requires FLAGGED status"
            )

    @property
    def is_flagged(self) -> bool:
        """Check if content is flagged for prohibition."""
        return self.status == UserContentStatus.FLAGGED

    @property
    def can_be_featured(self) -> bool:
        """Check if content can be featured."""
        return (
            self.featured_status
            not in (FeaturedStatus.PROHIBITED, FeaturedStatus.NOT_FEATURED)
            and self.status == UserContentStatus.ACTIVE
        )

    @property
    def is_featured(self) -> bool:
        """Check if content is currently featured."""
        return self.featured_status == FeaturedStatus.FEATURED

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "content_id": self.content_id,
            "owner_id": self.owner_id,
            "content": self.content,
            "title": self.title,
            "status": self.status.value,
            "featured_status": self.featured_status.value,
            "prohibition_flag": (
                self.prohibition_flag.to_dict() if self.prohibition_flag else None
            ),
            "created_at": self.created_at.isoformat(),
        }

    def with_prohibition_flag(
        self, flag: UserContentProhibitionFlag
    ) -> UserContent:
        """Create a new UserContent with prohibition flag applied.

        This method creates a flagged copy of the content.
        The original content is NOT modified (immutable).

        Args:
            flag: The prohibition flag to apply.

        Returns:
            New UserContent with FLAGGED status and PROHIBITED featured_status.
        """
        return UserContent(
            content_id=self.content_id,
            owner_id=self.owner_id,
            content=self.content,
            title=self.title,
            status=UserContentStatus.FLAGGED,
            featured_status=FeaturedStatus.PROHIBITED,
            created_at=self.created_at,
            prohibition_flag=flag,
        )

    def with_cleared_for_featuring(self) -> UserContent:
        """Create a new UserContent cleared for featuring.

        This method creates a copy with PENDING_REVIEW status.

        Returns:
            New UserContent with PENDING_REVIEW featured_status.
        """
        return UserContent(
            content_id=self.content_id,
            owner_id=self.owner_id,
            content=self.content,
            title=self.title,
            status=UserContentStatus.ACTIVE,
            featured_status=FeaturedStatus.PENDING_REVIEW,
            created_at=self.created_at,
            prohibition_flag=None,
        )


@dataclass(frozen=True, eq=True)
class FeatureRequest:
    """Request to evaluate user content for featuring (FR58).

    This is the input model for the featuring evaluation workflow.

    Attributes:
        content_id: Unique identifier of the content.
        owner_id: User who owns the content.
        content: The actual content text to scan.
        title: Content title.
    """

    content_id: str
    owner_id: str
    content: str
    title: str

    def __post_init__(self) -> None:
        """Validate request per FR58.

        Raises:
            ValueError: If validation fails with FR58 reference.
        """
        if not self.content_id:
            raise ValueError("FR58: content_id is required in FeatureRequest")

        if not self.owner_id:
            raise ValueError("FR58: owner_id is required in FeatureRequest")

        if not self.title:
            raise ValueError("FR58: title is required in FeatureRequest")

    def to_user_content(
        self,
        status: UserContentStatus = UserContentStatus.ACTIVE,
        featured_status: FeaturedStatus = FeaturedStatus.NOT_FEATURED,
        created_at: datetime | None = None,
        prohibition_flag: UserContentProhibitionFlag | None = None,
    ) -> UserContent:
        """Convert to UserContent model.

        Args:
            status: Content status to set.
            featured_status: Featured status to set.
            created_at: Creation timestamp (defaults to now).
            prohibition_flag: Optional prohibition flag.

        Returns:
            UserContent instance.
        """
        from datetime import timezone

        return UserContent(
            content_id=self.content_id,
            owner_id=self.owner_id,
            content=self.content,
            title=self.title,
            status=status,
            featured_status=featured_status,
            created_at=created_at or datetime.now(timezone.utc),
            prohibition_flag=prohibition_flag,
        )
