"""User content repository stub (Story 9.4, FR58).

In-memory implementation of UserContentRepositoryProtocol for testing.
Provides test control methods for setting up test scenarios.

This stub is NOT production-ready. Replace with a real implementation
(e.g., PostgreSQL adapter) for production use.
"""

from __future__ import annotations

from src.application.ports.user_content_repository import (
    UserContentRepositoryProtocol,
)
from src.domain.models.user_content import (
    FeaturedStatus,
    UserContent,
    UserContentProhibitionFlag,
    UserContentStatus,
)


class UserContentRepositoryStub(UserContentRepositoryProtocol):
    """In-memory stub implementation for testing (FR58).

    Provides an in-memory storage for user content that can be
    configured for different test scenarios.

    Test Control Methods:
        - add_content: Add content to storage
        - clear: Clear all stored content
        - set_content_prohibited: Apply prohibition flag to content
        - configure_content_list: Set up multiple content items

    Example:
        stub = UserContentRepositoryStub()

        # Add test content
        stub.add_content(UserContent(...))

        # Set up prohibition
        stub.set_content_prohibited("uc_123", flag)

        # Clear for next test
        stub.clear()
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._content: dict[str, UserContent] = {}

    # =========================================================================
    # Protocol Implementation
    # =========================================================================

    async def get_content(self, content_id: str) -> UserContent | None:
        """Retrieve user content by ID.

        Args:
            content_id: The unique identifier of the content.

        Returns:
            The UserContent if found, None otherwise.
        """
        return self._content.get(content_id)

    async def save_content(self, content: UserContent) -> None:
        """Save user content.

        Creates new content or updates existing content.

        Args:
            content: The UserContent to save.
        """
        self._content[content.content_id] = content

    async def update_prohibition_flag(
        self,
        content_id: str,
        flag: UserContentProhibitionFlag,
    ) -> None:
        """Update the prohibition flag on user content.

        Args:
            content_id: The ID of the content to update.
            flag: The prohibition flag to apply.

        Note:
            Creates a new UserContent with the flag applied
            since UserContent is immutable.
        """
        existing = self._content.get(content_id)
        if existing is None:
            return  # No-op if not found

        # Create new content with flag applied
        updated = existing.with_prohibition_flag(flag)
        self._content[content_id] = updated

    async def update_featured_status(
        self,
        content_id: str,
        status: FeaturedStatus,
    ) -> None:
        """Update the featured status of user content.

        Args:
            content_id: The ID of the content to update.
            status: The new featured status.
        """
        existing = self._content.get(content_id)
        if existing is None:
            return  # No-op if not found

        # Create new content with updated status
        updated = UserContent(
            content_id=existing.content_id,
            owner_id=existing.owner_id,
            content=existing.content,
            title=existing.title,
            status=existing.status,
            featured_status=status,
            created_at=existing.created_at,
            prohibition_flag=existing.prohibition_flag,
        )
        self._content[content_id] = updated

    async def get_featured_candidates(self) -> list[UserContent]:
        """Get all content that is a candidate for featuring.

        Returns content with FeaturedStatus.PENDING_REVIEW.

        Returns:
            List of UserContent that can be featured.
        """
        return [
            content
            for content in self._content.values()
            if content.featured_status == FeaturedStatus.PENDING_REVIEW
        ]

    async def get_prohibited_content(self) -> list[UserContent]:
        """Get all content that has been flagged as prohibited.

        Returns content with FeaturedStatus.PROHIBITED.

        Returns:
            List of prohibited UserContent.
        """
        return [
            content
            for content in self._content.values()
            if content.featured_status == FeaturedStatus.PROHIBITED
        ]

    async def clear_prohibition_flag(self, content_id: str) -> UserContent | None:
        """Clear the prohibition flag from user content.

        Args:
            content_id: The ID of the content to clear.

        Returns:
            The updated UserContent if found, None otherwise.
        """
        existing = self._content.get(content_id)
        if existing is None:
            return None

        # Create new content with cleared flag
        cleared = UserContent(
            content_id=existing.content_id,
            owner_id=existing.owner_id,
            content=existing.content,
            title=existing.title,
            status=UserContentStatus.ACTIVE,
            featured_status=FeaturedStatus.NOT_FEATURED,
            created_at=existing.created_at,
            prohibition_flag=None,
        )
        self._content[content_id] = cleared
        return cleared

    async def get_content_by_owner(self, owner_id: str) -> list[UserContent]:
        """Get all content owned by a specific user.

        Args:
            owner_id: The user who owns the content.

        Returns:
            List of UserContent owned by the user.
        """
        return [
            content
            for content in self._content.values()
            if content.owner_id == owner_id
        ]

    # =========================================================================
    # Test Control Methods
    # =========================================================================

    def add_content(self, content: UserContent) -> None:
        """Add content to storage (synchronous for test setup).

        Args:
            content: The UserContent to add.
        """
        self._content[content.content_id] = content

    def clear(self) -> None:
        """Clear all stored content."""
        self._content.clear()

    def set_content_prohibited(
        self,
        content_id: str,
        flag: UserContentProhibitionFlag,
    ) -> None:
        """Apply prohibition flag to content (synchronous for test setup).

        Args:
            content_id: The ID of the content to prohibit.
            flag: The prohibition flag to apply.
        """
        existing = self._content.get(content_id)
        if existing is not None:
            updated = existing.with_prohibition_flag(flag)
            self._content[content_id] = updated

    def configure_content_list(self, contents: list[UserContent]) -> None:
        """Set up multiple content items at once.

        Args:
            contents: List of UserContent to add.
        """
        for content in contents:
            self._content[content.content_id] = content

    def get_all_content(self) -> list[UserContent]:
        """Get all content in storage (for test assertions).

        Returns:
            List of all UserContent in storage.
        """
        return list(self._content.values())

    def content_count(self) -> int:
        """Get the count of content items in storage.

        Returns:
            Number of content items.
        """
        return len(self._content)
