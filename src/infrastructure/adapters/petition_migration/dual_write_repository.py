"""Dual-write petition repository (Story 0.3, AC2, FR-9.3).

This module provides a dual-write adapter for the Story 7.2 migration period.
Writes go to BOTH legacy and new repositories; reads come from legacy.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → Log all dual-write operations
- CT-12: Witnessing creates accountability → Audit all writes
- FR-9.3: System SHALL support dual-write during migration period
- FR-9.4: System SHALL preserve existing petition_id references

Configuration:
- PETITION_DUAL_WRITE_ENABLED environment variable controls behavior
- Default: True (dual-write enabled during migration)
- Set to False after migration complete

Read Strategy:
- All reads come from legacy repository (source of truth during migration)
- After migration, switch to new repository

Write Strategy:
- save_petition: Write to legacy first, then convert and write to new
- update_status: Update legacy, map status to state, update new
- add_cosigner: Legacy only (co-signers remain in Story 7.2 model)
"""

from __future__ import annotations

import os
from typing import Final
from uuid import UUID

from src.application.ports.petition_repository import PetitionRepositoryProtocol
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.domain.events.petition import PetitionStatus
from src.domain.models.petition import CoSigner, Petition
from src.infrastructure.adapters.petition_migration.cessation_adapter import (
    STATUS_TO_STATE_MAP,
    CessationPetitionAdapter,
)

# Default value for dual-write during migration period
PETITION_DUAL_WRITE_ENABLED_DEFAULT: Final[bool] = True


def is_dual_write_enabled() -> bool:
    """Check if dual-write is enabled via environment variable.

    Returns:
        True if PETITION_DUAL_WRITE_ENABLED is 'true' or '1',
        False if 'false' or '0',
        Default value if not set.
    """
    value = os.environ.get("PETITION_DUAL_WRITE_ENABLED", "").lower()
    if value in ("true", "1"):
        return True
    elif value in ("false", "0"):
        return False
    return PETITION_DUAL_WRITE_ENABLED_DEFAULT


class DualWritePetitionRepository:
    """Dual-write adapter for petition migration (FR-9.3).

    This adapter wraps both the legacy PetitionRepositoryProtocol and the
    new PetitionSubmissionRepositoryProtocol, providing dual-write capability
    during the migration period.

    Constitutional Compliance:
    - FR-9.3: Supports dual-write during migration
    - FR-9.4: Preserves petition IDs via CessationPetitionAdapter

    Implements PetitionRepositoryProtocol interface so it can be used as
    a drop-in replacement for existing code.

    Usage:
        dual_repo = DualWritePetitionRepository(
            legacy_repo=legacy_petition_repo,
            new_repo=petition_submission_repo,
        )
        # Use as normal PetitionRepositoryProtocol
        await dual_repo.save_petition(petition)
    """

    def __init__(
        self,
        legacy_repo: PetitionRepositoryProtocol,
        new_repo: PetitionSubmissionRepositoryProtocol,
    ) -> None:
        """Initialize dual-write repository.

        Args:
            legacy_repo: Story 7.2 petition repository (source of truth).
            new_repo: Story 0.2 petition submission repository (new schema).
        """
        self._legacy_repo = legacy_repo
        self._new_repo = new_repo

    async def save_petition(self, petition: Petition) -> None:
        """Save petition to both repositories (dual-write).

        FR-9.3: Writes to legacy first (source of truth), then to new schema.
        FR-9.4: Petition ID is preserved via CessationPetitionAdapter.

        Args:
            petition: The petition to save.

        Raises:
            PetitionAlreadyExistsError: If petition_id already exists (from legacy).
        """
        # Always write to legacy (source of truth)
        await self._legacy_repo.save_petition(petition)

        # Write to new schema if dual-write enabled
        if is_dual_write_enabled():
            submission = CessationPetitionAdapter.to_submission(petition)
            await self._new_repo.save(submission)

    async def get_petition(self, petition_id: UUID) -> Petition | None:
        """Get petition from legacy repository (source of truth).

        Args:
            petition_id: The unique petition identifier.

        Returns:
            The petition if found, None otherwise.
        """
        return await self._legacy_repo.get_petition(petition_id)

    async def list_open_petitions(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Petition], int]:
        """List open petitions from legacy repository (source of truth).

        Args:
            limit: Maximum number of petitions to return.
            offset: Number of petitions to skip.

        Returns:
            Tuple of (list of petitions, total count of open petitions).
        """
        return await self._legacy_repo.list_open_petitions(limit=limit, offset=offset)

    async def add_cosigner(
        self,
        petition_id: UUID,
        cosigner: CoSigner,
    ) -> Petition:
        """Add co-signer to legacy repository only.

        Co-signers remain in the Story 7.2 model. The new PetitionSubmission
        model does not track co-signers; they're handled differently in the
        Three Fates system (Epic 5).

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
        # Co-signers only go to legacy repository
        return await self._legacy_repo.add_cosigner(petition_id, cosigner)

    async def has_cosigned(self, petition_id: UUID, public_key: str) -> bool:
        """Check if public key has co-signed (from legacy repository).

        Args:
            petition_id: The petition to check.
            public_key: The hex-encoded public key to check.

        Returns:
            True if the key has already signed this petition.

        Raises:
            PetitionNotFoundError: If petition doesn't exist.
        """
        return await self._legacy_repo.has_cosigned(petition_id, public_key)

    async def update_status(
        self,
        petition_id: UUID,
        status: PetitionStatus,
        threshold_met_at: str | None = None,
    ) -> None:
        """Update petition status in both repositories (dual-write).

        FR-9.3: Updates legacy first (source of truth), then new schema.
        Status is mapped to PetitionState via STATUS_TO_STATE_MAP.

        Args:
            petition_id: The petition to update.
            status: The new status.
            threshold_met_at: ISO timestamp when threshold was met (optional).

        Raises:
            PetitionNotFoundError: If petition doesn't exist.
        """
        # Always update legacy (source of truth)
        await self._legacy_repo.update_status(
            petition_id, status, threshold_met_at=threshold_met_at
        )

        # Update new schema if dual-write enabled
        if is_dual_write_enabled():
            new_state = STATUS_TO_STATE_MAP[status]
            await self._new_repo.update_state(petition_id, new_state)

    async def get_cosigner_count(self, petition_id: UUID) -> int:
        """Get co-signer count from legacy repository.

        Args:
            petition_id: The petition to check.

        Returns:
            Number of co-signers (not including submitter).

        Raises:
            PetitionNotFoundError: If petition doesn't exist.
        """
        return await self._legacy_repo.get_cosigner_count(petition_id)
