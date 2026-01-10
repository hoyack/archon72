"""Waiver repository port for constitutional waiver persistence (Story 9.8, SC-4, SR-10).

This module defines the interface for storing and retrieving constitutional waivers.
Waivers document scope limitations and deferred requirements.

Constitutional Constraints:
- SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
- SR-10: CT-15 waiver documentation -> Must be explicit and tracked
- CT-12: Witnessing creates accountability -> Waiver changes witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before repository operations
2. WITNESS EVERYTHING - Waiver changes create witnessed events
3. FAIL LOUD - Never silently swallow repository errors
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

from src.domain.events.waiver import WaiverStatus


@dataclass(frozen=True)
class WaiverRecord:
    """Record of a constitutional waiver (SC-4, SR-10).

    Attributes:
        waiver_id: Unique identifier for this waiver (e.g., "CT-15-MVP-WAIVER").
        constitutional_truth_id: The CT being waived (e.g., "CT-15").
        constitutional_truth_statement: Full text of the CT being waived.
        what_is_waived: Description of what specific requirement is waived.
        rationale: Detailed reason for the waiver.
        target_phase: When the waived requirement will be addressed.
        status: Current status of the waiver (active, implemented, cancelled).
        documented_at: When the waiver was created (UTC).
        documented_by: Agent/system that documented the waiver.
    """

    waiver_id: str
    constitutional_truth_id: str
    constitutional_truth_statement: str
    what_is_waived: str
    rationale: str
    target_phase: str
    status: WaiverStatus
    documented_at: datetime
    documented_by: str

    def to_dict(self) -> dict[str, str | None]:
        """Convert record to dictionary for API responses.

        Returns:
            Dictionary representation of the waiver record.
        """
        return {
            "waiver_id": self.waiver_id,
            "constitutional_truth_id": self.constitutional_truth_id,
            "constitutional_truth_statement": self.constitutional_truth_statement,
            "what_is_waived": self.what_is_waived,
            "rationale": self.rationale,
            "target_phase": self.target_phase,
            "status": self.status.value,
            "documented_at": self.documented_at.isoformat(),
            "documented_by": self.documented_by,
        }


class WaiverRepositoryProtocol(Protocol):
    """Repository protocol for constitutional waivers (SC-4, SR-10).

    This protocol defines operations for persisting and retrieving waivers.
    Implementations should ensure transactional integrity and thread safety.

    Constitutional Constraints:
    - SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
    - SR-10: CT-15 waiver documentation -> Must be explicit
    """

    async def get_waiver(self, waiver_id: str) -> Optional[WaiverRecord]:
        """Retrieve a waiver by its ID.

        Args:
            waiver_id: Unique waiver identifier.

        Returns:
            WaiverRecord if found, None otherwise.
        """
        ...

    async def get_all_waivers(self) -> tuple[WaiverRecord, ...]:
        """Retrieve all documented waivers.

        Returns:
            Tuple of all WaiverRecords (empty tuple if none exist).
        """
        ...

    async def get_active_waivers(self) -> tuple[WaiverRecord, ...]:
        """Retrieve only active waivers.

        Active waivers are those with status == WaiverStatus.ACTIVE.

        Returns:
            Tuple of active WaiverRecords (empty tuple if none exist).
        """
        ...

    async def save_waiver(self, waiver: WaiverRecord) -> None:
        """Save a waiver record.

        If a waiver with the same ID exists, it will be updated.
        Otherwise, a new waiver will be created.

        Args:
            waiver: The waiver record to save.

        Raises:
            RepositoryError: If the save operation fails.
        """
        ...

    async def exists(self, waiver_id: str) -> bool:
        """Check if a waiver exists.

        Args:
            waiver_id: Unique waiver identifier.

        Returns:
            True if the waiver exists, False otherwise.
        """
        ...
