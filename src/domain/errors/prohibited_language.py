"""Prohibited language errors (Story 9.1, FR55).

Domain errors for prohibited language constraint violations.

Constitutional Constraints:
- FR55: System outputs never claim emergence, consciousness, etc.
- CT-11: Silent failure destroys legitimacy - fail loud on violations
- CT-12: All blocking must be witnessed
"""

from __future__ import annotations

from src.domain.errors.constitutional import ConstitutionalViolationError


class ProhibitedLanguageError(ConstitutionalViolationError):
    """Base error for prohibited language violations.

    All prohibited language errors inherit from this class
    and from ConstitutionalViolationError to indicate they
    represent constitutional (not just operational) failures.
    """

    pass


class ProhibitedLanguageBlockedError(ProhibitedLanguageError):
    """Raised when content is blocked due to prohibited language (FR55, AC2).

    This error indicates that content was blocked because it contained
    one or more prohibited terms (emergence, consciousness, etc.).

    Attributes:
        content_id: Identifier for the blocked content.
        matched_terms: Tuple of prohibited terms that were detected.
    """

    def __init__(
        self,
        content_id: str,
        matched_terms: tuple[str, ...],
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            content_id: Identifier for the blocked content.
            matched_terms: Tuple of prohibited terms that were detected.
            message: Optional custom message (auto-generated if not provided).
        """
        self.content_id = content_id
        self.matched_terms = matched_terms

        if message is None:
            terms_str = ", ".join(matched_terms)
            message = (
                f"FR55: Content blocked due to prohibited language. "
                f"Content ID: {content_id}. "
                f"Matched terms: {terms_str}. "
                f"System outputs must not claim emergence, consciousness, "
                f"sentience, or self-awareness."
            )

        super().__init__(message)

    @property
    def terms_count(self) -> int:
        """Get the number of matched terms."""
        return len(self.matched_terms)


class ProhibitedTermsConfigurationError(ProhibitedLanguageError):
    """Raised when the prohibited terms list is invalid (AC1).

    This error indicates a configuration problem with the
    prohibited terms list that must be fixed before the
    system can operate correctly.

    Attributes:
        reason: Reason the configuration is invalid.
    """

    def __init__(
        self,
        reason: str,
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            reason: Why the configuration is invalid.
            message: Optional custom message.
        """
        self.reason = reason

        if message is None:
            message = (
                f"FR55: Prohibited terms list configuration error: {reason}. "
                f"The prohibited language list is required for FR55 compliance."
            )

        super().__init__(message)


class ProhibitedLanguageScanError(ProhibitedLanguageError):
    """Raised when the prohibited language scan itself fails.

    This indicates an infrastructure failure in scanning content,
    not a content violation. Per CT-11, the system should fail
    loudly rather than allow potentially violating content through.

    Attributes:
        source_error: The underlying error that caused the failure.
        content_id: Identifier for the content being scanned (if known).
    """

    def __init__(
        self,
        source_error: Exception,
        content_id: str | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            source_error: The underlying error.
            content_id: Optional identifier for the content being scanned.
            message: Optional custom message.
        """
        self.source_error = source_error
        self.content_id = content_id

        if message is None:
            content_part = f" for content {content_id}" if content_id else ""
            message = (
                f"FR55: Prohibited language scan failed{content_part}: {source_error}. "
                f"Per CT-11, content cannot be allowed through without verification."
            )

        super().__init__(message)
