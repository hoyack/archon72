"""Semantic violation errors (Story 9.7, FR110).

Domain errors for semantic analysis and violation detection.

Constitutional Constraints:
- FR110: Secondary semantic scanning beyond keyword matching
- FR55: System outputs never claim emergence, consciousness, etc.
- CT-11: Silent failure destroys legitimacy - fail loud on scan failures
"""

from __future__ import annotations

from src.domain.errors.constitutional import ConstitutionalViolationError


class SemanticViolationError(ConstitutionalViolationError):
    """Base error for semantic violation detection.

    All semantic violation errors inherit from this class
    and from ConstitutionalViolationError to indicate they
    represent constitutional (not just operational) failures.
    """

    pass


class SemanticScanError(SemanticViolationError):
    """Raised when semantic analysis itself fails.

    This indicates an infrastructure failure in analyzing content,
    not a content violation. Per CT-11, the system should fail
    loudly rather than allow potentially violating content through.

    Attributes:
        source_error: The underlying error that caused the failure.
        content_id: Identifier for the content being analyzed (if known).
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
            content_id: Optional identifier for the content being analyzed.
            message: Optional custom message.
        """
        self.source_error = source_error
        self.content_id = content_id

        if message is None:
            content_part = f" for content {content_id}" if content_id else ""
            message = (
                f"FR110: Semantic analysis failed{content_part}: {source_error}. "
                f"Per CT-11, content cannot be allowed through without verification."
            )

        super().__init__(message)


class SemanticViolationSuspectedError(SemanticViolationError):
    """Raised when high-confidence semantic violation is detected (FR110).

    This error indicates that semantic analysis has detected patterns
    suggesting emergence claims with high confidence.

    Note: This is used when orchestrating semantic scanning to create
    breaches for high-confidence suspicions. It is NOT raised by the
    SemanticScanningService itself, which only creates events.

    Attributes:
        content_id: Identifier for the analyzed content.
        suspected_patterns: Patterns that triggered suspicion.
        confidence_score: Analysis confidence (0.0-1.0).
    """

    def __init__(
        self,
        content_id: str,
        suspected_patterns: tuple[str, ...],
        confidence_score: float,
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            content_id: Identifier for the analyzed content.
            suspected_patterns: Patterns that triggered suspicion.
            confidence_score: Analysis confidence (0.0-1.0).
            message: Optional custom message (auto-generated if not provided).
        """
        self.content_id = content_id
        self.suspected_patterns = suspected_patterns
        self.confidence_score = confidence_score

        if message is None:
            patterns_str = ", ".join(suspected_patterns)
            message = (
                f"FR110: Semantic violation suspected. "
                f"Content ID: {content_id}. "
                f"Suspected patterns: {patterns_str}. "
                f"Confidence: {confidence_score:.2%}. "
                f"Content may contain emergence claims evading keyword detection."
            )

        super().__init__(message)

    @property
    def pattern_count(self) -> int:
        """Get the number of suspected patterns."""
        return len(self.suspected_patterns)
