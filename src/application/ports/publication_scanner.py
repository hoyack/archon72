"""Publication scanner port interface (Story 9.2, FR56).

Defines the protocol for scanning publications for prohibited language
in the pre-publish workflow.

Constitutional Constraints:
- FR56: Automated keyword scanning on all publications
- CT-11: Silent failure destroys legitimacy -> fail loud on scan errors
- CT-12: All scan events must be witnessed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from src.domain.models.publication import PublicationScanRequest


class PublicationScanResultStatus(str, Enum):
    """Status of a publication scan result (FR56).

    Values:
        CLEAN: No prohibited content found, publication can proceed.
        BLOCKED: Prohibited content found, publication blocked.
        ERROR: Scan failed due to an error.
    """

    CLEAN = "clean"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass(frozen=True)
class PublicationScanResult:
    """Result of scanning a publication (FR56).

    This immutable result object contains information about
    the publication scan outcome.

    Attributes:
        status: Scan result status (CLEAN, BLOCKED, or ERROR).
        publication_id: ID of the scanned publication.
        matched_terms: Tuple of prohibited terms detected (empty if clean).
        detection_method: How detection was performed (e.g., "nfkc_scan").
        scanned_at: When the scan was performed.
        blocked_reason: Reason for blocking (if blocked).
    """

    status: PublicationScanResultStatus
    publication_id: str
    matched_terms: tuple[str, ...]
    detection_method: str
    scanned_at: datetime
    blocked_reason: str | None = None

    @property
    def is_clean(self) -> bool:
        """Check if the publication passed scanning."""
        return self.status == PublicationScanResultStatus.CLEAN

    @property
    def is_blocked(self) -> bool:
        """Check if the publication was blocked."""
        return self.status == PublicationScanResultStatus.BLOCKED

    @property
    def is_error(self) -> bool:
        """Check if the scan failed with an error."""
        return self.status == PublicationScanResultStatus.ERROR

    @property
    def terms_count(self) -> int:
        """Get the number of matched terms."""
        return len(self.matched_terms)

    @classmethod
    def clean(
        cls,
        publication_id: str,
        scanned_at: datetime,
        detection_method: str = "nfkc_scan",
    ) -> PublicationScanResult:
        """Create a clean scan result.

        Args:
            publication_id: ID of the scanned publication.
            scanned_at: When the scan was performed.
            detection_method: Detection method used.

        Returns:
            PublicationScanResult indicating clean publication.
        """
        return cls(
            status=PublicationScanResultStatus.CLEAN,
            publication_id=publication_id,
            matched_terms=(),
            detection_method=detection_method,
            scanned_at=scanned_at,
            blocked_reason=None,
        )

    @classmethod
    def blocked(
        cls,
        publication_id: str,
        matched_terms: tuple[str, ...],
        scanned_at: datetime,
        detection_method: str = "nfkc_scan",
    ) -> PublicationScanResult:
        """Create a blocked scan result.

        Args:
            publication_id: ID of the scanned publication.
            matched_terms: Prohibited terms that were detected.
            scanned_at: When the scan was performed.
            detection_method: Detection method used.

        Returns:
            PublicationScanResult indicating blocked publication.

        Raises:
            ValueError: If matched_terms is empty.
        """
        if not matched_terms:
            raise ValueError("FR56: matched_terms cannot be empty for blocked result")

        terms_str = ", ".join(matched_terms)
        return cls(
            status=PublicationScanResultStatus.BLOCKED,
            publication_id=publication_id,
            matched_terms=matched_terms,
            detection_method=detection_method,
            scanned_at=scanned_at,
            blocked_reason=f"Prohibited language detected: {terms_str}",
        )

    @classmethod
    def error(
        cls,
        publication_id: str,
        scanned_at: datetime,
        error_message: str,
        detection_method: str = "nfkc_scan",
    ) -> PublicationScanResult:
        """Create an error scan result.

        Args:
            publication_id: ID of the publication.
            scanned_at: When the scan was attempted.
            error_message: Description of the error.
            detection_method: Detection method used.

        Returns:
            PublicationScanResult indicating scan error.
        """
        return cls(
            status=PublicationScanResultStatus.ERROR,
            publication_id=publication_id,
            matched_terms=(),
            detection_method=detection_method,
            scanned_at=scanned_at,
            blocked_reason=f"Scan error: {error_message}",
        )


class PublicationScannerProtocol(Protocol):
    """Protocol for publication scanning (FR56).

    This port enables dependency inversion for publication scanning.
    Implementations orchestrate the pre-publish workflow including:
    - Scanning publication content for prohibited language
    - Recording scan history
    - Creating witnessed events

    Constitutional Constraints:
    - FR56: Automated keyword scanning on all publications
    - CT-11: HALT CHECK FIRST on all operations
    - CT-12: All scan events must be witnessed

    Methods:
        scan_publication: Scan a single publication.
        get_scan_history: Get scan history for a publication.
    """

    async def scan_publication(
        self, request: PublicationScanRequest
    ) -> PublicationScanResult:
        """Scan a publication for prohibited language (FR56).

        Performs the pre-publish scan to detect prohibited terms.
        If violations are found, the publication is blocked.

        Args:
            request: The publication scan request.

        Returns:
            PublicationScanResult with status and any matched terms.

        Raises:
            PublicationBlockedError: If prohibited content is found.
            PublicationScanError: If the scan fails.
            SystemHaltedError: If system is in halted state.
        """
        ...

    async def get_scan_history(
        self, publication_id: str
    ) -> list[PublicationScanResult]:
        """Get scan history for a publication (FR56).

        Returns all previous scan results for a publication,
        ordered by scan time (most recent first).

        Args:
            publication_id: ID of the publication.

        Returns:
            List of PublicationScanResult for the publication.
        """
        ...
