"""Semantic violation suspected events (Story 9.7, FR110).

Domain events for recording when content is flagged by semantic analysis
as potentially containing emergence claims that evade keyword detection.

Constitutional Constraints:
- FR110: Secondary semantic scanning beyond keyword matching
- FR55: System outputs never claim emergence, consciousness, etc.
- CT-11: Silent failure destroys legitimacy -> fail loud on scan errors
- CT-12: All suspected violations must be witnessed
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Final

# Event type constant (follows existing pattern in codebase)
SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE: Final[str] = "semantic.violation.suspected"

# System agent ID for semantic scanning (follows existing pattern)
SEMANTIC_SCANNER_SYSTEM_AGENT_ID: Final[str] = "system:semantic_scanner"

# Maximum content preview length (consistent with prohibited_language_blocked)
MAX_CONTENT_PREVIEW_LENGTH: Final[int] = 200

# Default confidence threshold for semantic scanning
DEFAULT_CONFIDENCE_THRESHOLD: Final[float] = 0.7


@dataclass(frozen=True, eq=True)
class SemanticViolationSuspectedEventPayload:
    """Payload for semantic violation suspected events (FR110).

    Records when content is flagged by semantic analysis as potentially
    containing emergence claims. This event is witnessed per CT-12 and
    forms part of the immutable audit trail.

    Note: This is a SUSPECTED violation (probabilistic), not a CONFIRMED
    violation. Semantic analysis uses pattern-based heuristics and may
    require human review.

    Attributes:
        content_id: Unique identifier for the analyzed content.
        suspected_patterns: Patterns that triggered suspicion.
        confidence_score: Analysis confidence (0.0-1.0).
        analysis_method: How the analysis was performed (e.g., "pattern_analysis").
        content_preview: First 200 characters of content for audit context.
        detected_at: When the analysis occurred (UTC).
    """

    content_id: str
    suspected_patterns: tuple[str, ...]
    confidence_score: float
    analysis_method: str
    content_preview: str
    detected_at: datetime

    def __post_init__(self) -> None:
        """Validate payload per FR110.

        Raises:
            ValueError: If validation fails with FR110 reference.
        """
        if not self.content_id:
            raise ValueError("FR110: content_id is required")

        if not self.suspected_patterns:
            raise ValueError("FR110: At least one suspected pattern required")

        if not self.analysis_method:
            raise ValueError("FR110: analysis_method is required")

        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError("FR110: confidence_score must be between 0.0 and 1.0")

        # Truncate content_preview if too long (frozen dataclass workaround)
        if len(self.content_preview) > MAX_CONTENT_PREVIEW_LENGTH:
            object.__setattr__(
                self,
                "content_preview",
                self.content_preview[:MAX_CONTENT_PREVIEW_LENGTH],
            )

    @property
    def event_type(self) -> str:
        """Get the event type for this payload."""
        return SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE

    @property
    def pattern_count(self) -> int:
        """Get the number of suspected patterns."""
        return len(self.suspected_patterns)

    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high-confidence detection (>= 0.7)."""
        return self.confidence_score >= DEFAULT_CONFIDENCE_THRESHOLD

    def to_dict(self) -> dict[str, object]:
        """Convert payload to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization and event storage.
        """
        return {
            "content_id": self.content_id,
            "suspected_patterns": list(self.suspected_patterns),
            "confidence_score": self.confidence_score,
            "analysis_method": self.analysis_method,
            "content_preview": self.content_preview,
            "detected_at": self.detected_at.isoformat(),
            "pattern_count": self.pattern_count,
            "is_high_confidence": self.is_high_confidence,
        }

    def signable_content(self) -> bytes:
        """Generate deterministic bytes for CT-12 witnessing.

        Creates a canonical byte representation of this event payload
        suitable for signing. The representation is deterministic
        (same payload always produces same bytes).

        Returns:
            Bytes suitable for cryptographic signing.
        """
        # Create canonical string representation
        # Sort suspected_patterns for determinism
        sorted_patterns = tuple(sorted(self.suspected_patterns))
        canonical = (
            f"semantic_violation_suspected:"
            f"content_id={self.content_id}:"
            f"suspected_patterns={','.join(sorted_patterns)}:"
            f"confidence_score={self.confidence_score:.4f}:"
            f"analysis_method={self.analysis_method}:"
            f"detected_at={self.detected_at.isoformat()}"
        )
        return canonical.encode("utf-8")

    def content_hash(self) -> str:
        """Generate SHA-256 hash of signable content.

        Returns:
            Hex-encoded SHA-256 hash of the signable content.
        """
        return hashlib.sha256(self.signable_content()).hexdigest()
