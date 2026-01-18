"""Petition repository stub implementation (Story 7.2, FR39).

This module provides an in-memory stub implementation of PetitionRepositoryProtocol
for development and testing purposes.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All operations logged
- FR39: External observers can petition with 100+ co-signers
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.application.ports.petition_repository import PetitionRepositoryProtocol
from src.domain.errors.petition import (
    DuplicateCosignatureError,
    PetitionAlreadyExistsError,
    PetitionClosedError,
    PetitionNotFoundError,
)
from src.domain.events.petition import PetitionStatus
from src.domain.models.petition import CoSigner, Petition


class PetitionRepositoryStub(PetitionRepositoryProtocol):
    """In-memory stub implementation of PetitionRepositoryProtocol.

    This stub stores petitions in memory for development and testing.
    It is NOT suitable for production use.

    Attributes:
        petitions: Dictionary mapping petition_id to Petition.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._petitions: dict[UUID, Petition] = {}

    async def save_petition(self, petition: Petition) -> None:
        """Save a new petition to storage.

        Args:
            petition: The petition to save.

        Raises:
            PetitionAlreadyExistsError: If petition_id already exists.
        """
        if petition.petition_id in self._petitions:
            raise PetitionAlreadyExistsError(str(petition.petition_id))
        self._petitions[petition.petition_id] = petition

    async def get_petition(self, petition_id: UUID) -> Petition | None:
        """Retrieve a petition by ID.

        Args:
            petition_id: The unique petition identifier.

        Returns:
            The petition if found, None otherwise.
        """
        return self._petitions.get(petition_id)

    async def list_open_petitions(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Petition], int]:
        """List all open petitions with pagination.

        Returns petitions with status=OPEN, ordered by created_timestamp desc.

        Args:
            limit: Maximum number of petitions to return.
            offset: Number of petitions to skip.

        Returns:
            Tuple of (list of petitions, total count of open petitions).
        """
        open_petitions = [
            p for p in self._petitions.values() if p.status == PetitionStatus.OPEN
        ]
        # Sort by created_timestamp descending
        open_petitions.sort(key=lambda p: p.created_timestamp, reverse=True)
        total = len(open_petitions)
        return open_petitions[offset : offset + limit], total

    async def add_cosigner(
        self,
        petition_id: UUID,
        cosigner: CoSigner,
    ) -> Petition:
        """Add a co-signer to a petition.

        Args:
            petition_id: The petition to add co-signer to.
            cosigner: The co-signer to add.

        Returns:
            Updated petition with new co-signer.

        Raises:
            PetitionNotFoundError: If petition doesn't exist.
            DuplicateCosignatureError: If public_key already co-signed.
            PetitionClosedError: If petition is not open.
        """
        petition = self._petitions.get(petition_id)
        if petition is None:
            raise PetitionNotFoundError(str(petition_id))

        if petition.status == PetitionStatus.CLOSED:
            raise PetitionClosedError(str(petition_id), petition.status.value)

        if petition.has_cosigned(cosigner.public_key):
            raise DuplicateCosignatureError(str(petition_id), cosigner.public_key)

        updated = petition.add_cosigner(cosigner)
        self._petitions[petition_id] = updated
        return updated

    async def has_cosigned(self, petition_id: UUID, public_key: str) -> bool:
        """Check if a public key has already co-signed a petition.

        This includes checking the original submitter as well as co-signers.

        Args:
            petition_id: The petition to check.
            public_key: The hex-encoded public key to check.

        Returns:
            True if the key has already signed this petition.

        Raises:
            PetitionNotFoundError: If petition doesn't exist.
        """
        petition = self._petitions.get(petition_id)
        if petition is None:
            raise PetitionNotFoundError(str(petition_id))
        return petition.has_cosigned(public_key)

    async def update_status(
        self,
        petition_id: UUID,
        status: PetitionStatus,
        threshold_met_at: str | None = None,
    ) -> None:
        """Update a petition's status.

        Used to mark petitions as threshold_met or closed.

        Args:
            petition_id: The petition to update.
            status: The new status.
            threshold_met_at: ISO timestamp when threshold was met (optional).

        Raises:
            PetitionNotFoundError: If petition doesn't exist.
        """
        petition = self._petitions.get(petition_id)
        if petition is None:
            raise PetitionNotFoundError(str(petition_id))

        if status == PetitionStatus.THRESHOLD_MET and threshold_met_at:
            met_at = datetime.fromisoformat(threshold_met_at.replace("Z", "+00:00"))
            updated = petition.with_threshold_met(met_at)
        else:
            updated = petition.with_status(status)

        self._petitions[petition_id] = updated

    async def get_cosigner_count(self, petition_id: UUID) -> int:
        """Get the number of co-signers for a petition.

        Optimized method for checking threshold without loading all co-signers.

        Args:
            petition_id: The petition to check.

        Returns:
            Number of co-signers (not including submitter).

        Raises:
            PetitionNotFoundError: If petition doesn't exist.
        """
        petition = self._petitions.get(petition_id)
        if petition is None:
            raise PetitionNotFoundError(str(petition_id))
        return petition.cosigner_count

    def clear(self) -> None:
        """Clear all petitions (for testing)."""
        self._petitions.clear()
