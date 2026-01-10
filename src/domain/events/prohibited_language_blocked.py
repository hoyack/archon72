"""Prohibited language blocking events (Story 9.1, FR55, AC2, AC4).

Domain events for recording when content is blocked due to
prohibited language (emergence, consciousness, etc.).

Constitutional Constraints:
- FR55: System outputs never claim emergence, consciousness, etc.
- CT-12: All blocking events must be witnessed
- ADR-11: Emergence governance under complexity control
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Final

# Event type constant (follows existing pattern in codebase)
PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE: Final[str] = "prohibited.language.blocked"

# System agent ID for prohibited language blocking (follows existing pattern)
PROHIBITED_LANGUAGE_SYSTEM_AGENT_ID: Final[str] = "system:prohibited_language_blocker"

# Maximum content preview length
MAX_CONTENT_PREVIEW_LENGTH: Final[int] = 200


@dataclass(frozen=True, eq=True)
class ProhibitedLanguageBlockedEventPayload:
    """Payload for prohibited language blocking events (FR55, AC2).

    Records when content is blocked due to containing prohibited
    language. This event is witnessed per CT-12 and forms part
    of the immutable audit trail.

    Attributes:
        content_id: Unique identifier for the blocked content.
        matched_terms: Tuple of prohibited terms that were detected.
        detection_method: How the terms were detected (e.g., "nfkc_scan").
        blocked_at: When the block occurred (UTC).
        content_preview: First 200 characters of content for audit context.
    """

    content_id: str
    matched_terms: tuple[str, ...]
    detection_method: str
    blocked_at: datetime
    content_preview: str

    def __post_init__(self) -> None:
        """Validate payload per FR55.

        Raises:
            ValueError: If validation fails with FR55 reference.
        """
        if not self.content_id:
            raise ValueError("FR55: content_id is required")

        if not self.matched_terms:
            raise ValueError("FR55: At least one matched term required")

        if not self.detection_method:
            raise ValueError("FR55: detection_method is required")

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
        return PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE

    @property
    def terms_count(self) -> int:
        """Get the number of matched terms."""
        return len(self.matched_terms)

    def to_dict(self) -> dict[str, object]:
        """Convert payload to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization and event storage.
        """
        return {
            "content_id": self.content_id,
            "matched_terms": list(self.matched_terms),
            "detection_method": self.detection_method,
            "blocked_at": self.blocked_at.isoformat(),
            "content_preview": self.content_preview,
            "terms_count": self.terms_count,
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
        # Sort matched_terms for determinism
        sorted_terms = tuple(sorted(self.matched_terms))
        canonical = (
            f"prohibited_language_blocked:"
            f"content_id={self.content_id}:"
            f"matched_terms={','.join(sorted_terms)}:"
            f"detection_method={self.detection_method}:"
            f"blocked_at={self.blocked_at.isoformat()}"
        )
        return canonical.encode("utf-8")

    def content_hash(self) -> str:
        """Generate SHA-256 hash of signable content.

        Returns:
            Hex-encoded SHA-256 hash of the signable content.
        """
        return hashlib.sha256(self.signable_content()).hexdigest()
