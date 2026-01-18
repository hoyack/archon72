"""Publication errors (Story 9.2, FR56).

Domain errors for publication scanning constraint violations.

Constitutional Constraints:
- FR56: Automated keyword scanning on all publications
- CT-11: Silent failure destroys legitimacy - fail loud on violations
- CT-12: All blocking must be witnessed
"""

from __future__ import annotations

from src.domain.errors.constitutional import ConstitutionalViolationError


class PublicationError(ConstitutionalViolationError):
    """Base error for publication-related violations.

    All publication errors inherit from this class and from
    ConstitutionalViolationError to indicate they represent
    constitutional (not just operational) failures.
    """

    pass


class PublicationBlockedError(PublicationError):
    """Raised when a publication is blocked due to prohibited language (FR56).

    This error indicates that a publication was blocked during
    pre-publish scanning because it contained prohibited terms.

    Attributes:
        publication_id: Identifier for the blocked publication.
        title: Title of the blocked publication.
        matched_terms: Tuple of prohibited terms that were detected.
    """

    def __init__(
        self,
        publication_id: str,
        title: str,
        matched_terms: tuple[str, ...],
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            publication_id: Identifier for the blocked publication.
            title: Title of the blocked publication.
            matched_terms: Tuple of prohibited terms that were detected.
            message: Optional custom message (auto-generated if not provided).
        """
        self.publication_id = publication_id
        self.title = title
        self.matched_terms = matched_terms

        if message is None:
            terms_str = ", ".join(matched_terms)
            message = (
                f"FR56: Publication blocked due to prohibited language. "
                f"Publication: '{title}' (ID: {publication_id}). "
                f"Matched terms: {terms_str}. "
                f"Publication is pending review."
            )

        super().__init__(message)

    @property
    def terms_count(self) -> int:
        """Get the number of matched terms."""
        return len(self.matched_terms)


class PublicationScanError(PublicationError):
    """Raised when the publication scan itself fails (FR56, CT-11).

    This indicates an infrastructure failure in scanning a publication,
    not a content violation. Per CT-11, the system should fail
    loudly rather than allow potentially violating content through.

    Attributes:
        source_error: The underlying error that caused the failure.
        publication_id: Identifier for the publication being scanned.
    """

    def __init__(
        self,
        source_error: Exception,
        publication_id: str,
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            source_error: The underlying error.
            publication_id: Identifier for the publication being scanned.
            message: Optional custom message.
        """
        self.source_error = source_error
        self.publication_id = publication_id

        if message is None:
            message = (
                f"FR56: Publication scan failed for publication {publication_id}: "
                f"{source_error}. "
                f"Per CT-11, publication cannot proceed without verification."
            )

        super().__init__(message)


class PublicationNotFoundError(PublicationError):
    """Raised when a publication is not found (FR56).

    This error indicates that a requested publication does not
    exist in the system.

    Attributes:
        publication_id: Identifier for the missing publication.
    """

    def __init__(
        self,
        publication_id: str,
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            publication_id: Identifier for the missing publication.
            message: Optional custom message.
        """
        self.publication_id = publication_id

        if message is None:
            message = f"FR56: Publication not found: {publication_id}"

        super().__init__(message)


class PublicationValidationError(PublicationError):
    """Raised when publication validation fails (FR56).

    This error indicates that a publication request is invalid
    (e.g., empty content, missing title).

    Attributes:
        field: The field that failed validation.
        reason: Why the validation failed.
    """

    def __init__(
        self,
        field: str,
        reason: str,
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            field: The field that failed validation.
            reason: Why the validation failed.
            message: Optional custom message.
        """
        self.field = field
        self.reason = reason

        if message is None:
            message = (
                f"FR56: Publication validation failed. Field: {field}. Reason: {reason}"
            )

        super().__init__(message)
