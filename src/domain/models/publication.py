"""Publication domain models (Story 9.2, FR56).

This module provides domain models for publications subject to
automated keyword scanning in the pre-publish workflow.

Constitutional Constraints:
- FR56: Automated keyword scanning on all publications
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All scan events must be witnessed

Usage:
    request = PublicationScanRequest(
        publication_id="pub-123",
        content="Article content here...",
        title="Article Title",
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final

# Publication ID prefix (FR56)
PUBLICATION_ID_PREFIX: Final[str] = "pub-"


class PublicationStatus(str, Enum):
    """Status of a publication in the pre-publish workflow (FR56).

    State transitions:
    - DRAFT -> PENDING_REVIEW (submitted for publication)
    - PENDING_REVIEW -> APPROVED (scan passed, ready for publish)
    - PENDING_REVIEW -> BLOCKED (scan found prohibited content)
    - APPROVED -> PUBLISHED (successfully published)
    - BLOCKED -> PENDING_REVIEW (after content revision)
    """

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    BLOCKED = "blocked"  # Prohibited language detected
    PUBLISHED = "published"


@dataclass(frozen=True)
class Publication:
    """A publication subject to pre-publish keyword scanning (FR56).

    Publications represent content that must be scanned for prohibited
    language before being made public. The status tracks progression
    through the pre-publish workflow.

    Attributes:
        id: Unique publication identifier (prefix: pub-).
        content: The publication content to be scanned.
        title: Publication title.
        author_agent_id: ID of the agent that authored the publication.
        status: Current status in the pre-publish workflow.
        created_at: When the publication was created.
        scanned_at: When the publication was last scanned (None if never).
    """

    id: str
    content: str
    title: str
    author_agent_id: str
    status: PublicationStatus
    created_at: datetime
    scanned_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate publication fields on creation."""
        if not self.id:
            raise ValueError("FR56: Publication ID cannot be empty")
        if not self.content:
            raise ValueError("FR56: Publication content cannot be empty")
        if not self.title:
            raise ValueError("FR56: Publication title cannot be empty")
        if not self.author_agent_id:
            raise ValueError("FR56: Author agent ID cannot be empty")

    def with_status(self, new_status: PublicationStatus) -> Publication:
        """Create a new Publication with updated status.

        Args:
            new_status: The new status to set.

        Returns:
            New Publication instance with updated status.
        """
        return Publication(
            id=self.id,
            content=self.content,
            title=self.title,
            author_agent_id=self.author_agent_id,
            status=new_status,
            created_at=self.created_at,
            scanned_at=self.scanned_at,
        )

    def with_scan_timestamp(self, scanned_at: datetime) -> Publication:
        """Create a new Publication with updated scan timestamp.

        Args:
            scanned_at: When the scan occurred.

        Returns:
            New Publication instance with updated scan timestamp.
        """
        return Publication(
            id=self.id,
            content=self.content,
            title=self.title,
            author_agent_id=self.author_agent_id,
            status=self.status,
            created_at=self.created_at,
            scanned_at=scanned_at,
        )


@dataclass(frozen=True)
class PublicationScanRequest:
    """Request for scanning a publication (FR56).

    This represents a request to scan publication content
    for prohibited language before publication.

    Attributes:
        publication_id: Unique identifier of the publication.
        content: The content to scan.
        title: Publication title (for logging/events).
    """

    publication_id: str
    content: str
    title: str

    def __post_init__(self) -> None:
        """Validate scan request fields on creation."""
        if not self.publication_id:
            raise ValueError("FR56: Publication ID cannot be empty")
        if not self.content:
            raise ValueError("FR56: Content to scan cannot be empty")
        if not self.title:
            raise ValueError("FR56: Publication title cannot be empty")

    @classmethod
    def from_publication(cls, publication: Publication) -> PublicationScanRequest:
        """Create a scan request from an existing publication.

        Args:
            publication: The publication to scan.

        Returns:
            PublicationScanRequest for the publication.
        """
        return cls(
            publication_id=publication.id,
            content=publication.content,
            title=publication.title,
        )
