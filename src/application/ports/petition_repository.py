"""Petition repository port (Story 7.2, FR39).

This module defines the abstract interface for petition storage operations.
Implementations provide persistence for petitions and co-signatures.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All operations must be logged
- CT-12: Witnessing creates accountability → All writes are witnessed
- FR39: External observers can petition with 100+ co-signers

Developer Golden Rules:
1. HALT CHECK FIRST - Service layer checks halt, not repository
2. WITNESS EVERYTHING - Repository stores, service witnesses
3. FAIL LOUD - Repository raises on errors
4. READS DURING HALT - Repository reads work during halt (CT-13)
"""

from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from src.domain.events.petition import PetitionStatus
from src.domain.models.petition import CoSigner, Petition


class PetitionRepositoryProtocol(Protocol):
    """Protocol for petition storage operations (FR39).

    Defines the contract for petition persistence. Implementations
    may use Supabase, in-memory storage, or other backends.

    Constitutional Constraints:
    - AC1: Store petitions with submitter signature
    - AC2: Store co-signatures with duplicate detection
    - AC5: Support idempotent status updates
    - AC8: Support public listing without authentication
    """

    async def save_petition(self, petition: Petition) -> None:
        """Save a new petition to storage.

        Args:
            petition: The petition to save.

        Raises:
            PetitionAlreadyExistsError: If petition_id already exists.
        """
        ...

    async def get_petition(self, petition_id: UUID) -> Optional[Petition]:
        """Retrieve a petition by ID.

        Args:
            petition_id: The unique petition identifier.

        Returns:
            The petition if found, None otherwise.
        """
        ...

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
        ...

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
        ...

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
        ...

    async def update_status(
        self,
        petition_id: UUID,
        status: PetitionStatus,
        threshold_met_at: Optional[str] = None,
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
        ...

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
        ...
