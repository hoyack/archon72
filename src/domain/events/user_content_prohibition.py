"""User content prohibition events (Story 9.4, FR58).

Domain events for recording user content prohibition outcomes.
These events track when user content is evaluated for featuring
and whether it was cleared or flagged for prohibited language.

Constitutional Constraints:
- FR58: User content subject to same prohibition for featuring
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All prohibition events must be witnessed

CRITICAL: User content is FLAGGED, not deleted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Final

# Event type constants (FR58)
USER_CONTENT_PROHIBITED_EVENT_TYPE: Final[str] = "user_content.prohibited"
USER_CONTENT_CLEARED_EVENT_TYPE: Final[str] = "user_content.cleared"

# System agent ID for user content scanning
USER_CONTENT_SCANNER_SYSTEM_AGENT_ID: Final[str] = "system:user_content_scanner"


@dataclass(frozen=True, eq=True)
class UserContentProhibitionEventPayload:
    """Payload for user content prohibition events (FR58, AC4).

    Records when user content is flagged for prohibited language.
    The content is NOT deleted - only flagged to prevent featuring.

    Attributes:
        content_id: Unique identifier of the content.
        owner_id: User who owns the content.
        title: Content title for audit context.
        matched_terms: Tuple of prohibited terms detected.
        action_taken: Action taken (always "flag_not_feature" per FR58).
        flagged_at: When the content was flagged (UTC).
    """

    content_id: str
    owner_id: str
    title: str
    matched_terms: tuple[str, ...]
    action_taken: str
    flagged_at: datetime

    def __post_init__(self) -> None:
        """Validate payload per FR58.

        Raises:
            ValueError: If validation fails with FR58 reference.
        """
        if not self.content_id:
            raise ValueError("FR58: content_id is required")

        if not self.owner_id:
            raise ValueError("FR58: owner_id is required")

        if not self.title:
            raise ValueError("FR58: title is required")

        if not self.matched_terms:
            raise ValueError("FR58: prohibition event must have matched_terms")

        if self.action_taken != "flag_not_feature":
            raise ValueError(
                f"FR58: action_taken must be 'flag_not_feature', got '{self.action_taken}'"
            )

    @property
    def event_type(self) -> str:
        """Get the event type."""
        return USER_CONTENT_PROHIBITED_EVENT_TYPE

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
            "owner_id": self.owner_id,
            "title": self.title,
            "matched_terms": list(self.matched_terms),
            "action_taken": self.action_taken,
            "flagged_at": self.flagged_at.isoformat(),
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
        # Sort matched_terms for determinism
        sorted_terms = tuple(sorted(self.matched_terms))
        canonical = (
            f"user_content_prohibited:"
            f"content_id={self.content_id}:"
            f"owner_id={self.owner_id}:"
            f"title={self.title}:"
            f"matched_terms={','.join(sorted_terms)}:"
            f"action_taken={self.action_taken}:"
            f"flagged_at={self.flagged_at.isoformat()}"
        )
        return canonical.encode("utf-8")

    def content_hash(self) -> str:
        """Generate SHA-256 hash of signable content.

        Returns:
            Hex-encoded SHA-256 hash of the signable content.
        """
        return hashlib.sha256(self.signable_content()).hexdigest()

    @classmethod
    def create(
        cls,
        content_id: str,
        owner_id: str,
        title: str,
        matched_terms: tuple[str, ...],
        flagged_at: datetime,
    ) -> UserContentProhibitionEventPayload:
        """Create a prohibition event payload.

        Args:
            content_id: ID of the content being flagged.
            owner_id: User who owns the content.
            title: Content title.
            matched_terms: Prohibited terms that were detected.
            flagged_at: When the flagging occurred.

        Returns:
            UserContentProhibitionEventPayload instance.
        """
        return cls(
            content_id=content_id,
            owner_id=owner_id,
            title=title,
            matched_terms=matched_terms,
            action_taken="flag_not_feature",
            flagged_at=flagged_at,
        )


@dataclass(frozen=True, eq=True)
class UserContentClearedEventPayload:
    """Payload for user content cleared events (FR58, AC4).

    Records when user content passes scanning and is cleared
    for consideration in featuring/curation.

    Attributes:
        content_id: Unique identifier of the content.
        owner_id: User who owns the content.
        title: Content title for audit context.
        scanned_at: When the scan occurred (UTC).
        detection_method: Method used for scanning.
    """

    content_id: str
    owner_id: str
    title: str
    scanned_at: datetime
    detection_method: str

    def __post_init__(self) -> None:
        """Validate payload per FR58.

        Raises:
            ValueError: If validation fails with FR58 reference.
        """
        if not self.content_id:
            raise ValueError("FR58: content_id is required")

        if not self.owner_id:
            raise ValueError("FR58: owner_id is required")

        if not self.title:
            raise ValueError("FR58: title is required")

        if not self.detection_method:
            raise ValueError("FR58: detection_method is required")

    @property
    def event_type(self) -> str:
        """Get the event type."""
        return USER_CONTENT_CLEARED_EVENT_TYPE

    def to_dict(self) -> dict[str, object]:
        """Convert payload to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization and event storage.
        """
        return {
            "content_id": self.content_id,
            "owner_id": self.owner_id,
            "title": self.title,
            "scanned_at": self.scanned_at.isoformat(),
            "detection_method": self.detection_method,
        }

    def signable_content(self) -> bytes:
        """Generate deterministic bytes for CT-12 witnessing.

        Creates a canonical byte representation of this event payload
        suitable for signing. The representation is deterministic
        (same payload always produces same bytes).

        Returns:
            Bytes suitable for cryptographic signing.
        """
        canonical = (
            f"user_content_cleared:"
            f"content_id={self.content_id}:"
            f"owner_id={self.owner_id}:"
            f"title={self.title}:"
            f"scanned_at={self.scanned_at.isoformat()}:"
            f"detection_method={self.detection_method}"
        )
        return canonical.encode("utf-8")

    def content_hash(self) -> str:
        """Generate SHA-256 hash of signable content.

        Returns:
            Hex-encoded SHA-256 hash of the signable content.
        """
        return hashlib.sha256(self.signable_content()).hexdigest()

    @classmethod
    def create(
        cls,
        content_id: str,
        owner_id: str,
        title: str,
        scanned_at: datetime,
        detection_method: str = "nfkc_scan",
    ) -> UserContentClearedEventPayload:
        """Create a cleared event payload.

        Args:
            content_id: ID of the content that was scanned.
            owner_id: User who owns the content.
            title: Content title.
            scanned_at: When the scan occurred.
            detection_method: Detection method used.

        Returns:
            UserContentClearedEventPayload instance.
        """
        return cls(
            content_id=content_id,
            owner_id=owner_id,
            title=title,
            scanned_at=scanned_at,
            detection_method=detection_method,
        )
