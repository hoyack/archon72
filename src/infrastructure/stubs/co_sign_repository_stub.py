"""In-memory stub for CoSignRepositoryProtocol (Story 5.2, Story 5.3).

This stub provides an in-memory implementation for testing.
It simulates the database behavior including:
- Unique constraint enforcement (petition_id, signer_id)
- Atomic count increment
- Signer list queries
- Identity verification status tracking

Constitutional Constraints:
- FR-6.2: System SHALL enforce unique constraint (petition_id, signer_id)
- FR-6.4: System SHALL increment co-signer count atomically
- NFR-3.5: 0 duplicate signatures ever exist
- NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
- NFR-6.4: Full signer list queryable
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.errors import AlreadySignedError, CoSignPetitionNotFoundError

if TYPE_CHECKING:
    pass


@dataclass
class StoredCoSign:
    """In-memory representation of a co-sign record."""

    cosign_id: UUID
    petition_id: UUID
    signer_id: UUID
    signed_at: datetime
    content_hash: bytes
    identity_verified: bool = False


class CoSignRepositoryStub:
    """In-memory stub implementation of CoSignRepositoryProtocol.

    This stub maintains:
    - A dictionary of co-sign records keyed by (petition_id, signer_id)
    - A dictionary of co-signer counts keyed by petition_id

    Thread-safety note: This stub is NOT thread-safe. For concurrent
    tests, use proper synchronization or separate instances.
    """

    def __init__(self) -> None:
        """Initialize empty stub."""
        # Key: (petition_id, signer_id), Value: StoredCoSign
        self._co_signs: dict[tuple[UUID, UUID], StoredCoSign] = {}
        # Key: petition_id, Value: count
        self._counts: dict[UUID, int] = {}
        # Set of valid petition IDs (simulates petition_submissions table)
        self._valid_petitions: set[UUID] = set()

    def add_valid_petition(self, petition_id: UUID) -> None:
        """Add a petition ID to the valid petitions set.

        Call this in tests before attempting to co-sign a petition.

        Args:
            petition_id: The petition ID to add.
        """
        self._valid_petitions.add(petition_id)
        if petition_id not in self._counts:
            self._counts[petition_id] = 0

    async def create(
        self,
        cosign_id: UUID,
        petition_id: UUID,
        signer_id: UUID,
        signed_at: datetime,
        content_hash: bytes,
        identity_verified: bool = False,
    ) -> int:
        """Create a co-sign record and increment petition co_signer_count.

        Args:
            cosign_id: Unique identifier for this co-signature.
            petition_id: The petition being co-signed.
            signer_id: The Seeker adding their support.
            signed_at: When the co-signature is recorded (UTC).
            content_hash: BLAKE3 hash for witness integrity.
            identity_verified: Whether signer identity was verified (NFR-5.2).

        Returns:
            The new co_signer_count after increment.

        Raises:
            AlreadySignedError: Unique constraint violation.
            CoSignPetitionNotFoundError: Petition doesn't exist.
        """
        # Validate petition exists
        if petition_id not in self._valid_petitions:
            raise CoSignPetitionNotFoundError(petition_id)

        # Check unique constraint (FR-6.2, NFR-3.5)
        key = (petition_id, signer_id)
        if key in self._co_signs:
            # Story 5.7: Include existing signature details in error
            existing = self._co_signs[key]
            raise AlreadySignedError(
                petition_id=petition_id,
                signer_id=signer_id,
                existing_cosign_id=existing.cosign_id,
                signed_at=existing.signed_at,
            )

        # Store co-sign record
        self._co_signs[key] = StoredCoSign(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
            identity_verified=identity_verified,
        )

        # Atomic count increment (FR-6.4)
        self._counts[petition_id] = self._counts.get(petition_id, 0) + 1

        return self._counts[petition_id]

    async def exists(
        self,
        petition_id: UUID,
        signer_id: UUID,
    ) -> bool:
        """Check if a signer has already co-signed a petition.

        Args:
            petition_id: The petition to check.
            signer_id: The signer to check.

        Returns:
            True if the signer has already co-signed, False otherwise.
        """
        return (petition_id, signer_id) in self._co_signs

    async def get_count(
        self,
        petition_id: UUID,
    ) -> int:
        """Get the current co-signer count for a petition.

        Args:
            petition_id: The petition to query.

        Returns:
            Current co_signer_count (0 if no co-signers).
        """
        return self._counts.get(petition_id, 0)

    async def get_signers(
        self,
        petition_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UUID]:
        """Get signer IDs for a petition (NFR-6.4).

        Args:
            petition_id: The petition to query.
            limit: Maximum signers to return.
            offset: Starting offset for pagination.

        Returns:
            List of signer UUIDs ordered by signed_at.
        """
        # Get all co-signs for this petition
        co_signs = [
            cs for cs in self._co_signs.values() if cs.petition_id == petition_id
        ]

        # Sort by signed_at
        co_signs.sort(key=lambda cs: cs.signed_at)

        # Apply pagination
        paginated = co_signs[offset : offset + limit]

        return [cs.signer_id for cs in paginated]

    # Test helper methods

    def reset(self) -> None:
        """Reset all stored data. Useful between tests."""
        self._co_signs.clear()
        self._counts.clear()
        self._valid_petitions.clear()

    def get_stored_co_sign(
        self, petition_id: UUID, signer_id: UUID
    ) -> StoredCoSign | None:
        """Get stored co-sign for inspection in tests."""
        return self._co_signs.get((petition_id, signer_id))

    async def get_existing(
        self, petition_id: UUID, signer_id: UUID
    ) -> tuple[UUID, datetime] | None:
        """Get existing co-sign details if exists (Story 5.7).

        Used by service layer to provide enhanced error messages.

        Args:
            petition_id: The petition to check.
            signer_id: The signer to check.

        Returns:
            Tuple of (cosign_id, signed_at) if exists, None otherwise.
        """
        key = (petition_id, signer_id)
        if key in self._co_signs:
            existing = self._co_signs[key]
            return (existing.cosign_id, existing.signed_at)
        return None

    @property
    def co_sign_count(self) -> int:
        """Total number of stored co-signs."""
        return len(self._co_signs)
