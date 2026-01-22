"""Orphan petition detection domain model (Story 8.3, FR-8.5).

This module defines the domain model for orphan petition detection -
tracking petitions stuck in RECEIVED state beyond acceptable thresholds.

Constitutional Constraints:
- FR-8.5: System SHALL identify petitions stuck in RECEIVED state
- NFR-7.1: 100% of orphans must be detected
- CT-11: Silent failure destroys legitimacy -> Track all orphans
- CT-12: Witnessing creates accountability -> Frozen dataclass
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID


@dataclass(frozen=True)
class OrphanPetitionInfo:
    """Information about an orphaned petition (Story 8.3, FR-8.5).

    Represents a single petition stuck in RECEIVED state beyond the
    acceptable threshold.

    Attributes:
        petition_id: UUID of the orphaned petition
        created_at: When the petition was created/entered RECEIVED state (UTC)
        age_hours: How long the petition has been in RECEIVED (hours)
        petition_type: Type of petition (GENERAL, CESSATION, etc.)
        co_signer_count: Number of co-signers (for context)
    """

    petition_id: UUID
    created_at: datetime
    age_hours: float
    petition_type: str
    co_signer_count: int


@dataclass(frozen=True)
class OrphanPetitionDetectionResult:
    """Result of orphan petition detection scan (Story 8.3, FR-8.5).

    Constitutional Requirements:
    - FR-8.5: Must identify all petitions stuck >24 hours
    - NFR-7.1: 100% detection rate required
    - CT-12: Frozen dataclass for immutability

    Attributes:
        detection_id: Unique identifier for this detection run
        detected_at: When the detection scan ran (UTC)
        threshold_hours: Threshold used for orphan detection (default: 24)
        orphan_petitions: List of detected orphaned petitions
        total_orphans: Count of orphaned petitions found
        oldest_orphan_age_hours: Age of the oldest orphan (hours), None if no orphans
    """

    detection_id: UUID
    detected_at: datetime
    threshold_hours: float
    orphan_petitions: tuple[OrphanPetitionInfo, ...]
    total_orphans: int
    oldest_orphan_age_hours: float | None

    @classmethod
    def create(
        cls,
        detection_id: UUID,
        threshold_hours: float,
        orphan_petitions: list[OrphanPetitionInfo],
    ) -> OrphanPetitionDetectionResult:
        """Create detection result from orphan list (FR-8.5).

        Args:
            detection_id: Unique identifier for this detection run
            threshold_hours: Threshold used for detection
            orphan_petitions: List of detected orphaned petitions

        Returns:
            OrphanPetitionDetectionResult instance.
        """
        # Compute oldest orphan age
        oldest_age = None
        if orphan_petitions:
            oldest_age = max(orphan.age_hours for orphan in orphan_petitions)

        return cls(
            detection_id=detection_id,
            detected_at=datetime.now(timezone.utc),
            threshold_hours=threshold_hours,
            orphan_petitions=tuple(orphan_petitions),
            total_orphans=len(orphan_petitions),
            oldest_orphan_age_hours=oldest_age,
        )

    def has_orphans(self) -> bool:
        """Check if any orphans were detected.

        Returns:
            True if orphans were found, False otherwise.
        """
        return self.total_orphans > 0

    def get_petition_ids(self) -> list[UUID]:
        """Get list of orphaned petition IDs.

        Returns:
            List of petition UUIDs.
        """
        return [orphan.petition_id for orphan in self.orphan_petitions]
