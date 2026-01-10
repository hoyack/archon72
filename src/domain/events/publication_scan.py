"""Publication scan events (Story 9.2, FR56, AC5).

Domain events for recording publication scan results in the
pre-publish workflow. Both clean and blocked publications
generate witnessed events for audit trail.

Constitutional Constraints:
- FR56: Automated keyword scanning on all publications
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All scan events must be witnessed
- ADR-11: Emergence governance under complexity control
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

# Event type constants (FR56)
PUBLICATION_SCANNED_EVENT_TYPE: Final[str] = "publication.scanned"
PUBLICATION_BLOCKED_EVENT_TYPE: Final[str] = "publication.blocked"

# System agent ID for publication scanning (follows existing pattern)
PUBLICATION_SCANNER_SYSTEM_AGENT_ID: Final[str] = "system:publication_scanner"

# Scan result literal type
ScanResultStatus = Literal["clean", "blocked"]


@dataclass(frozen=True, eq=True)
class PublicationScannedEventPayload:
    """Payload for publication scan events (FR56, AC5).

    Records when a publication is scanned during pre-publish workflow.
    Both clean and blocked publications generate events for audit trail.

    Attributes:
        publication_id: Unique identifier of the scanned publication.
        title: Publication title for audit context.
        scan_result: Result status ("clean" or "blocked").
        matched_terms: Tuple of prohibited terms detected (empty if clean).
        scanned_at: When the scan occurred (UTC).
        detection_method: Method used for scanning (e.g., "nfkc_scan").
    """

    publication_id: str
    title: str
    scan_result: ScanResultStatus
    matched_terms: tuple[str, ...]
    scanned_at: datetime
    detection_method: str

    def __post_init__(self) -> None:
        """Validate payload per FR56.

        Raises:
            ValueError: If validation fails with FR56 reference.
        """
        if not self.publication_id:
            raise ValueError("FR56: publication_id is required")

        if not self.title:
            raise ValueError("FR56: title is required")

        if self.scan_result not in ("clean", "blocked"):
            raise ValueError(
                f"FR56: scan_result must be 'clean' or 'blocked', got '{self.scan_result}'"
            )

        if not self.detection_method:
            raise ValueError("FR56: detection_method is required")

        # Blocked scans must have matched terms
        if self.scan_result == "blocked" and not self.matched_terms:
            raise ValueError("FR56: blocked scan must have at least one matched term")

        # Clean scans should not have matched terms
        if self.scan_result == "clean" and self.matched_terms:
            raise ValueError("FR56: clean scan should not have matched terms")

    @property
    def event_type(self) -> str:
        """Get the event type based on scan result."""
        if self.scan_result == "blocked":
            return PUBLICATION_BLOCKED_EVENT_TYPE
        return PUBLICATION_SCANNED_EVENT_TYPE

    @property
    def is_blocked(self) -> bool:
        """Check if the publication was blocked."""
        return self.scan_result == "blocked"

    @property
    def is_clean(self) -> bool:
        """Check if the publication passed scanning."""
        return self.scan_result == "clean"

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
            "publication_id": self.publication_id,
            "title": self.title,
            "scan_result": self.scan_result,
            "matched_terms": list(self.matched_terms),
            "scanned_at": self.scanned_at.isoformat(),
            "detection_method": self.detection_method,
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
            f"publication_scanned:"
            f"publication_id={self.publication_id}:"
            f"title={self.title}:"
            f"scan_result={self.scan_result}:"
            f"matched_terms={','.join(sorted_terms)}:"
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
    def clean_scan(
        cls,
        publication_id: str,
        title: str,
        scanned_at: datetime,
        detection_method: str = "nfkc_scan",
    ) -> PublicationScannedEventPayload:
        """Create a payload for a clean scan result.

        Args:
            publication_id: ID of the scanned publication.
            title: Publication title.
            scanned_at: When the scan occurred.
            detection_method: Detection method used.

        Returns:
            PublicationScannedEventPayload for a clean scan.
        """
        return cls(
            publication_id=publication_id,
            title=title,
            scan_result="clean",
            matched_terms=(),
            scanned_at=scanned_at,
            detection_method=detection_method,
        )

    @classmethod
    def blocked_scan(
        cls,
        publication_id: str,
        title: str,
        matched_terms: tuple[str, ...],
        scanned_at: datetime,
        detection_method: str = "nfkc_scan",
    ) -> PublicationScannedEventPayload:
        """Create a payload for a blocked scan result.

        Args:
            publication_id: ID of the scanned publication.
            title: Publication title.
            matched_terms: Prohibited terms that were detected.
            scanned_at: When the scan occurred.
            detection_method: Detection method used.

        Returns:
            PublicationScannedEventPayload for a blocked scan.
        """
        return cls(
            publication_id=publication_id,
            title=title,
            scan_result="blocked",
            matched_terms=matched_terms,
            scanned_at=scanned_at,
            detection_method=detection_method,
        )
