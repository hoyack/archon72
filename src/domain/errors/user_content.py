"""User content prohibition errors (Story 9.4, FR58).

Error classes for user content prohibition workflow.
These errors are raised when:
- User content contains prohibited language (cannot be featured)
- User content is not found
- Other prohibition-related failures

Constitutional Constraints:
- FR58: User content subject to same prohibition for featuring
- CRITICAL: User content is FLAGGED, not deleted
"""

from __future__ import annotations

from src.domain.errors.constitutional import ConstitutionalViolationError


class UserContentProhibitionError(ConstitutionalViolationError):
    """Base error for user content prohibition failures (FR58).

    This is the base class for all user content prohibition errors.
    """

    pass


class UserContentCannotBeFeaturedException(UserContentProhibitionError):
    """Error raised when user content cannot be featured (FR58).

    This error is raised when user content contains prohibited language
    and therefore cannot be featured or curated.

    CRITICAL: The content is NOT deleted - only flagged.

    Attributes:
        content_id: The ID of the content that was flagged.
        owner_id: The user who owns the content.
        matched_terms: The prohibited terms that were detected.
    """

    def __init__(
        self,
        content_id: str,
        owner_id: str,
        matched_terms: tuple[str, ...],
    ) -> None:
        """Initialize the error.

        Args:
            content_id: The ID of the content that was flagged.
            owner_id: The user who owns the content.
            matched_terms: The prohibited terms that were detected.
        """
        self.content_id = content_id
        self.owner_id = owner_id
        self.matched_terms = matched_terms

        terms_str = ", ".join(matched_terms[:3])
        if len(matched_terms) > 3:
            terms_str += f" (+{len(matched_terms) - 3} more)"

        super().__init__(
            f"FR58: User content '{content_id}' cannot be featured due to "
            f"prohibited language: {terms_str}"
        )


class UserContentNotFoundError(UserContentProhibitionError):
    """Error raised when user content is not found (FR58).

    This error is raised when attempting to operate on
    user content that does not exist.

    Attributes:
        content_id: The ID of the content that was not found.
    """

    def __init__(self, content_id: str) -> None:
        """Initialize the error.

        Args:
            content_id: The ID of the content that was not found.
        """
        self.content_id = content_id
        super().__init__(f"FR58: User content not found: {content_id}")


class UserContentFlagClearError(UserContentProhibitionError):
    """Error raised when prohibition flag cannot be cleared (FR58).

    This error is raised when attempting to clear a prohibition flag
    fails (e.g., insufficient permissions or invalid state).

    Attributes:
        content_id: The ID of the content.
        reason: The reason the flag could not be cleared.
    """

    def __init__(self, content_id: str, reason: str) -> None:
        """Initialize the error.

        Args:
            content_id: The ID of the content.
            reason: The reason the flag could not be cleared.
        """
        self.content_id = content_id
        self.reason = reason
        super().__init__(
            f"FR58: Cannot clear prohibition flag for content '{content_id}': {reason}"
        )
