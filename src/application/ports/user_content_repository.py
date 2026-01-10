"""User content repository port (Story 9.4, FR58).

Protocol definition for user content storage and retrieval.
This port is used by the UserContentProhibitionService for
content prohibition workflow.

Constitutional Constraints:
- FR58: User content subject to same prohibition for featuring
- CRITICAL: User content is FLAGGED, not deleted
"""

from __future__ import annotations

from typing import Protocol

from src.domain.models.user_content import (
    FeaturedStatus,
    UserContent,
    UserContentProhibitionFlag,
)


class UserContentRepositoryProtocol(Protocol):
    """Protocol for user content persistence (FR58).

    This port defines the interface for storing and retrieving
    user content. Implementations must ensure content is never
    deleted when prohibited - only flagged.

    All methods are async for non-blocking I/O.
    """

    async def get_content(self, content_id: str) -> UserContent | None:
        """Retrieve user content by ID.

        Args:
            content_id: The unique identifier of the content.

        Returns:
            The UserContent if found, None otherwise.
        """
        ...

    async def save_content(self, content: UserContent) -> None:
        """Save user content.

        Creates new content or updates existing content.
        This should be used for all content operations including
        flagging (prohibited content is saved, not deleted).

        Args:
            content: The UserContent to save.
        """
        ...

    async def update_prohibition_flag(
        self,
        content_id: str,
        flag: UserContentProhibitionFlag,
    ) -> None:
        """Update the prohibition flag on user content.

        This method is used to add or update a prohibition flag
        on existing content. The content itself is NOT deleted.

        Args:
            content_id: The ID of the content to update.
            flag: The prohibition flag to apply.

        Raises:
            UserContentNotFoundError: If content_id does not exist.
        """
        ...

    async def update_featured_status(
        self,
        content_id: str,
        status: FeaturedStatus,
    ) -> None:
        """Update the featured status of user content.

        Args:
            content_id: The ID of the content to update.
            status: The new featured status.

        Raises:
            UserContentNotFoundError: If content_id does not exist.
        """
        ...

    async def get_featured_candidates(self) -> list[UserContent]:
        """Get all content that is a candidate for featuring.

        Returns content with FeaturedStatus.PENDING_REVIEW,
        which have passed scanning and await curation.

        Returns:
            List of UserContent that can be featured.
        """
        ...

    async def get_prohibited_content(self) -> list[UserContent]:
        """Get all content that has been flagged as prohibited.

        Returns content with FeaturedStatus.PROHIBITED.
        This content cannot be featured but is NOT deleted.

        Returns:
            List of prohibited UserContent.
        """
        ...

    async def clear_prohibition_flag(self, content_id: str) -> UserContent | None:
        """Clear the prohibition flag from user content.

        This method is used for admin/manual review override.
        It removes the prohibition flag and sets the content
        back to a clean state.

        Args:
            content_id: The ID of the content to clear.

        Returns:
            The updated UserContent if found, None otherwise.
        """
        ...

    async def get_content_by_owner(self, owner_id: str) -> list[UserContent]:
        """Get all content owned by a specific user.

        Args:
            owner_id: The user who owns the content.

        Returns:
            List of UserContent owned by the user.
        """
        ...
