"""Review session domain model.

Story: consent-gov-6-4: Prince Panel Domain Model

Defines the ReviewSession model for tracking panel review of artifacts (AC3/FR37).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import UUID


@dataclass(frozen=True, eq=True)
class ReviewedArtifact:
    """Record of an artifact reviewed by the panel.

    Attributes:
        artifact_id: UUID of the artifact (witness statement, event, etc.)
        artifact_type: Type of artifact (witness_statement, event, etc.)
        reviewed_at: When the panel reviewed this artifact
    """

    artifact_id: UUID
    """UUID of the artifact."""

    artifact_type: str
    """Type of artifact (witness_statement, event, etc.)."""

    reviewed_at: datetime
    """When the panel reviewed this artifact."""

    def __hash__(self) -> int:
        """Hash based on artifact_id."""
        return hash(self.artifact_id)


@dataclass(frozen=True, eq=True)
class ReviewSession:
    """Record of a panel review session (FR37/AC3).

    Tracks the panel's review of witness artifacts, ensuring:
    - Panel receives witness statements
    - Panel can access related events
    - Review session recorded
    - All evidence preserved

    This is immutable to ensure review records cannot be altered.

    Attributes:
        session_id: Unique identifier for this review session
        panel_id: UUID of the panel conducting review
        statement_id: Primary witness statement being reviewed
        started_at: When the review session started
        ended_at: When the review session ended (None if ongoing)
        reviewed_artifacts: List of all artifacts reviewed
        notes: Panel notes during review (optional)

    Example:
        >>> session = ReviewSession(
        ...     session_id=uuid4(),
        ...     panel_id=uuid4(),
        ...     statement_id=uuid4(),
        ...     started_at=datetime.now(timezone.utc),
        ...     ended_at=None,
        ...     reviewed_artifacts=[
        ...         ReviewedArtifact(
        ...             artifact_id=statement_id,
        ...             artifact_type="witness_statement",
        ...             reviewed_at=datetime.now(timezone.utc),
        ...         ),
        ...     ],
        ...     notes=None,
        ... )
    """

    session_id: UUID
    """Unique identifier for this review session."""

    panel_id: UUID
    """UUID of the panel conducting review."""

    statement_id: UUID
    """Primary witness statement being reviewed."""

    started_at: datetime
    """When the review session started."""

    ended_at: Optional[datetime]
    """When the review session ended (None if ongoing)."""

    reviewed_artifacts: List[ReviewedArtifact]
    """List of all artifacts reviewed.

    Includes the primary witness statement and any related events
    or evidence the panel accessed during review.
    """

    notes: Optional[str]
    """Panel notes during review (optional).

    May include observations, questions, or points for deliberation.
    """

    @property
    def is_active(self) -> bool:
        """Check if review session is still active.

        Returns:
            True if session has not ended, False otherwise
        """
        return self.ended_at is None

    @property
    def artifact_count(self) -> int:
        """Get count of reviewed artifacts.

        Returns:
            Number of artifacts reviewed in this session
        """
        return len(self.reviewed_artifacts)

    def __hash__(self) -> int:
        """Hash based on session_id (unique identifier)."""
        return hash(self.session_id)
