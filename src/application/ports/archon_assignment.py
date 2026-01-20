"""ArchonAssignmentService protocol for Three Fates deliberation (Story 2A.2, FR-11.1).

This module defines the protocol for assigning Fate Archons to petitions
and creating deliberation sessions. The service handles:
- Deterministic archon selection from the Three Fates pool
- DeliberationSession creation with UUIDv7
- Idempotent assignment (returns existing session if already assigned)
- Event emission for archon assignment

Constitutional Constraints:
- FR-11.1: System assigns exactly 3 Marquis-rank Archons per petition
- FR-11.2: Initiate mini-Conclave when petition enters RECEIVED state
- NFR-10.3: Consensus determinism (100% reproducible)
- NFR-10.5: Support 100+ concurrent deliberations
- NFR-10.6: Archon substitution < 10 seconds on failure

Developer Golden Rules:
1. DETERMINISM - Same (petition_id + seed) always produces same selection
2. IDEMPOTENT - Repeated assignment returns existing session
3. EXACTLY_THREE - Never more, never fewer Archons assigned
4. EVENT_EMISSION - Always emit ArchonsAssignedEvent on new assignment
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.models.deliberation_session import DeliberationSession
    from src.domain.models.fate_archon import FateArchon


# Event type constant for archon assignment
ARCHONS_ASSIGNED_EVENT_TYPE: str = "deliberation.archons_assigned"

# Schema version for D2 compliance
ARCHONS_ASSIGNED_SCHEMA_VERSION: int = 1


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class AssignmentResult:
    """Result of archon assignment operation (Story 2A.2, AC-4).

    Represents the outcome of assigning archons to a petition for deliberation.
    The result indicates whether this was a new assignment or an existing one
    was returned (idempotency).

    Attributes:
        session: The DeliberationSession created or retrieved.
        assigned_archons: Tuple of exactly 3 FateArchon instances.
        is_new_assignment: True if this was a new assignment, False if existing.
        assigned_at: When the assignment was made (UTC).
    """

    session: DeliberationSession
    assigned_archons: tuple[FateArchon, FateArchon, FateArchon]
    is_new_assignment: bool
    assigned_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, eq=True)
class ArchonsAssignedEventPayload:
    """Payload for archon assignment events (Story 2A.2, AC-5).

    An ArchonsAssignedEventPayload is created when archons are assigned
    to a petition for Three Fates deliberation.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - AC-5: Event includes schema_version for D2 compliance
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - FR-11.1: Exactly 3 archon IDs included

    Attributes:
        session_id: ID of the created DeliberationSession.
        petition_id: ID of the petition being deliberated.
        archon_ids: Tuple of exactly 3 assigned archon UUIDs.
        archon_names: Tuple of assigned archon names (for readability).
        assigned_at: When the assignment was made (UTC).
        schema_version: Version for D2 compliance.
    """

    session_id: UUID
    petition_id: UUID
    archon_ids: tuple[UUID, UUID, UUID]
    archon_names: tuple[str, str, str]
    assigned_at: datetime
    schema_version: int = ARCHONS_ASSIGNED_SCHEMA_VERSION

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "archon_ids": [str(aid) for aid in self.archon_ids],
            "archon_names": list(self.archon_names),
            "assigned_at": self.assigned_at.isoformat(),
            "petition_id": str(self.petition_id),
            "schema_version": self.schema_version,
            "session_id": str(self.session_id),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        D2 Compliance: Includes schema_version for deterministic replay.

        Returns:
            Dict representation suitable for GovernanceLedger.append_event().
        """
        return {
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "archon_ids": [str(aid) for aid in self.archon_ids],
            "archon_names": list(self.archon_names),
            "assigned_at": self.assigned_at.isoformat(),
            "schema_version": self.schema_version,
        }


class ArchonAssignmentServiceProtocol(Protocol):
    """Protocol for assigning Archons to petitions for deliberation.

    Implementations must guarantee:
    1. Exactly 3 Archons are assigned per petition (FR-11.1)
    2. Selection is deterministic given (petition_id + seed) (NFR-10.3)
    3. Assignment is idempotent (same petition_id returns existing session) (AC-3)
    4. ArchonsAssignedEvent is emitted on new assignment (AC-5)
    5. Session state transitions to DELIBERATING (AC-4)

    Constitutional Constraints:
    - FR-11.1: Exactly 3 Marquis-rank Archons per petition
    - FR-11.2: Initiate mini-Conclave when petition enters RECEIVED state
    - NFR-10.3: Consensus determinism (100% reproducible)
    """

    async def assign_archons(
        self,
        petition_id: UUID,
        seed: int | None = None,
    ) -> AssignmentResult:
        """Assign archons to a petition for deliberation.

        This operation is idempotent: if archons have already been assigned
        to this petition, the existing session is returned.

        Selection is deterministic: given the same (petition_id, seed),
        the same 3 Archons will always be assigned.

        Args:
            petition_id: UUID of the petition requiring deliberation.
            seed: Optional seed for deterministic selection. If None,
                  uses petition_id bytes as seed.

        Returns:
            AssignmentResult containing the session and assigned archons.

        Raises:
            PetitionNotFoundError: If petition does not exist.
            InvalidPetitionStateError: If petition is not in RECEIVED state.
            ArchonPoolExhaustedError: If pool has fewer than 3 Archons.
        """
        ...

    async def get_session_by_petition(
        self,
        petition_id: UUID,
    ) -> DeliberationSession | None:
        """Get existing deliberation session for a petition.

        Args:
            petition_id: UUID of the petition.

        Returns:
            DeliberationSession if exists, None otherwise.
        """
        ...

    async def get_assigned_archons(
        self,
        petition_id: UUID,
    ) -> tuple[FateArchon, FateArchon, FateArchon] | None:
        """Get assigned archons for a petition.

        Args:
            petition_id: UUID of the petition.

        Returns:
            Tuple of 3 FateArchons if assigned, None otherwise.
        """
        ...
