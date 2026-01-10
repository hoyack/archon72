"""Keeper attestation domain model for availability tracking (FR77-FR79).

This module defines the KeeperAttestation entity for tracking weekly Keeper
availability attestations. Keepers must attest availability weekly, with
2 missed attestations triggering a replacement process.

Constitutional Constraints:
- FR77: If unanimous Keeper agreement not achieved within 72 hours of recovery,
        cessation evaluation SHALL begin
- FR78: Keepers SHALL attest availability weekly; 2 missed attestations trigger
        replacement process
- FR79: If registered Keeper count falls below 3, system SHALL halt until
        complement restored

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Attestations are witnessed events

Note: DeletePreventionMixin ensures `.delete()` raises
ConstitutionalViolationError before any DB interaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.primitives import DeletePreventionMixin

# Weekly attestation requirement (FR78)
ATTESTATION_PERIOD_DAYS: int = 7

# Replacement triggered after 2 missed attestations (FR78)
MISSED_ATTESTATIONS_THRESHOLD: int = 2

# Minimum Keeper quorum (FR79)
MINIMUM_KEEPER_QUORUM: int = 3


def get_current_period() -> tuple[datetime, datetime]:
    """Calculate current 7-day attestation period.

    Periods start at midnight UTC on Mondays. This provides consistent
    weekly boundaries for attestation tracking.

    Returns:
        Tuple of (period_start, period_end) datetimes.
        period_start: Monday 00:00:00 UTC of current week
        period_end: Monday 00:00:00 UTC of next week
    """
    now = datetime.now(timezone.utc)
    # Find Monday of current week (weekday 0 = Monday)
    days_since_monday = now.weekday()
    period_start = now.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=days_since_monday)
    period_end = period_start + timedelta(days=ATTESTATION_PERIOD_DAYS)
    return period_start, period_end


@dataclass(frozen=True, eq=True)
class KeeperAttestation(DeletePreventionMixin):
    """Keeper weekly availability attestation - immutable, deletion prohibited.

    Each Keeper must submit an attestation for each weekly period to confirm
    their continued availability. Missing 2 consecutive attestations triggers
    the Keeper replacement process.

    Constitutional Constraints:
    - FR76: Historical attestations must be preserved (no deletion)
    - FR78: Weekly attestation requirement

    Attributes:
        id: Unique identifier for this attestation record (UUID)
        keeper_id: ID of Keeper making the attestation
            Format: "KEEPER:{name}" (e.g., "KEEPER:alice")
        attested_at: When this attestation was submitted
        period_start: Start of the attestation period (Monday 00:00 UTC)
        period_end: End of the attestation period (next Monday 00:00 UTC)
        signature: Ed25519 signature over attestation content (64 bytes)

    Note:
        DeletePreventionMixin ensures `.delete()` raises
        ConstitutionalViolationError before any DB interaction.
    """

    # Primary identifier
    id: UUID

    # Keeper identifier (FR78)
    keeper_id: str

    # When attestation was submitted
    attested_at: datetime

    # Attestation period boundaries
    period_start: datetime
    period_end: datetime

    # Ed25519 signature (64 bytes)
    signature: bytes

    # Audit timestamp
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ConstitutionalViolationError: If any field fails validation.
        """
        self._validate_id()
        self._validate_keeper_id()
        self._validate_signature()
        self._validate_period()

    def _validate_id(self) -> None:
        """Validate id is UUID."""
        if not isinstance(self.id, UUID):
            raise ConstitutionalViolationError(
                f"FR78: KeeperAttestation validation failed - id must be UUID, "
                f"got {type(self.id).__name__}"
            )

    def _validate_keeper_id(self) -> None:
        """Validate keeper_id is non-empty string."""
        if not isinstance(self.keeper_id, str) or not self.keeper_id.strip():
            raise ConstitutionalViolationError(
                "FR78: KeeperAttestation validation failed - "
                "keeper_id must be non-empty string"
            )

    def _validate_signature(self) -> None:
        """Validate signature is Ed25519 signature (64 bytes)."""
        if not isinstance(self.signature, bytes):
            raise ConstitutionalViolationError(
                "FR78: KeeperAttestation validation failed - signature must be bytes"
            )
        # Ed25519 signatures are exactly 64 bytes
        if len(self.signature) != 64:
            raise ConstitutionalViolationError(
                f"FR78: KeeperAttestation validation failed - "
                f"signature must be 64 bytes (Ed25519), got {len(self.signature)}"
            )

    def _validate_period(self) -> None:
        """Validate period_end is after period_start."""
        if self.period_end <= self.period_start:
            raise ConstitutionalViolationError(
                "FR78: KeeperAttestation validation failed - "
                "period_end must be after period_start"
            )

    def __hash__(self) -> int:
        """Hash based on id (unique identifier).

        Note: signature is excluded from hash since bytes are included
        in the dataclass comparison but we want set membership to be
        based on id alone.
        """
        return hash(self.id)

    def is_valid_for_period(
        self, period_start: datetime, period_end: datetime
    ) -> bool:
        """Check if this attestation is valid for a specific period.

        An attestation is valid for a period if its period boundaries
        match exactly. This ensures Keepers attest for the correct
        weekly period.

        Args:
            period_start: Start of the period to check against.
            period_end: End of the period to check against.

        Returns:
            True if attestation covers the specified period, False otherwise.
        """
        return self.period_start == period_start and self.period_end == period_end
