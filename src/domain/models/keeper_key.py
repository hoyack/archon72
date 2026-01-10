"""Keeper key domain model for cryptographic signing (FR68, FR76).

This module defines the KeeperKey entity for the Keeper key registry.
Keeper keys are used to sign override commands and verify Keeper identity.

Constitutional Constraints:
- FR68: Override commands require cryptographic signature from registered Keeper key
- FR76: Historical keys must be preserved (no deletion)

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Keeper attribution creates verifiable authorship

Note: DeletePreventionMixin ensures `.delete()` raises
ConstitutionalViolationError before any DB interaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.primitives import DeletePreventionMixin

# Keeper ID prefix for identification
KEEPER_ID_PREFIX: str = "KEEPER:"


@dataclass(frozen=True, eq=True)
class KeeperKey(DeletePreventionMixin):
    """Keeper signing key entity - immutable, deletion prohibited.

    Keeper keys are the foundation of cryptographic attribution for
    human Keepers in the constitutional system. Each key is associated
    with a Keeper and has a temporal validity period.

    Constitutional Constraints:
    - FR68: Override commands require cryptographic signature from Keeper key
    - FR76: Historical keys must be preserved (no deletion)

    Attributes:
        id: Unique identifier for this key record (UUID)
        keeper_id: ID of Keeper that owns this key
            Format: "KEEPER:{name}" (e.g., "KEEPER:alice")
        key_id: HSM key identifier (unique across all keys)
        public_key: Ed25519 public key bytes (32 bytes)
        active_from: When this key became active
        active_until: When this key was rotated out (None = currently active)
        created_at: When this record was created

    Note:
        DeletePreventionMixin ensures `.delete()` raises
        ConstitutionalViolationError before any DB interaction.
    """

    # Primary identifier
    id: UUID

    # Keeper identifier (FR68)
    keeper_id: str

    # HSM key identifier (unique)
    key_id: str

    # Ed25519 public key bytes (32 bytes)
    public_key: bytes

    # Temporal validity
    active_from: datetime

    # Expiry (None = currently active)
    active_until: datetime | None = field(default=None)

    # Audit timestamp
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ConstitutionalViolationError: If any field fails validation.
        """
        self._validate_id()
        self._validate_keeper_id()
        self._validate_key_id()
        self._validate_public_key()

    def _validate_id(self) -> None:
        """Validate id is UUID."""
        if not isinstance(self.id, UUID):
            raise ConstitutionalViolationError(
                f"FR68: KeeperKey validation failed - id must be UUID, got {type(self.id).__name__}"
            )

    def _validate_keeper_id(self) -> None:
        """Validate keeper_id is non-empty string."""
        if not isinstance(self.keeper_id, str) or not self.keeper_id.strip():
            raise ConstitutionalViolationError(
                "FR68: KeeperKey validation failed - keeper_id must be non-empty string"
            )

    def _validate_key_id(self) -> None:
        """Validate key_id is non-empty string."""
        if not isinstance(self.key_id, str) or not self.key_id.strip():
            raise ConstitutionalViolationError(
                "FR68: KeeperKey validation failed - key_id must be non-empty string"
            )

    def _validate_public_key(self) -> None:
        """Validate public_key is Ed25519 public key (32 bytes)."""
        if not isinstance(self.public_key, bytes):
            raise ConstitutionalViolationError(
                "FR68: KeeperKey validation failed - public_key must be bytes"
            )
        # Ed25519 public keys are exactly 32 bytes
        if len(self.public_key) != 32:
            raise ConstitutionalViolationError(
                f"FR68: KeeperKey validation failed - public_key must be 32 bytes (Ed25519), got {len(self.public_key)}"
            )

    def __hash__(self) -> int:
        """Hash based on id (unique identifier).

        Note: public_key is excluded from hash since bytes are included
        in the dataclass comparison but we want set membership to be
        based on id alone.
        """
        return hash(self.id)

    def is_active_at(self, timestamp: datetime) -> bool:
        """Check if this key was active at a specific time.

        Used for historical verification - when verifying old overrides,
        we need to find the key that was active when the override was created.

        Args:
            timestamp: The time to check against.

        Returns:
            True if key was active at the given time, False otherwise.
        """
        # Must be after active_from
        if timestamp < self.active_from:
            return False

        # If no expiry, key is still active
        if self.active_until is None:
            return True

        # Must be before active_until
        return timestamp < self.active_until

    def is_currently_active(self) -> bool:
        """Check if this key is currently active.

        Convenience method that calls is_active_at with current time.

        Returns:
            True if key is currently active, False otherwise.
        """
        return self.is_active_at(datetime.now(timezone.utc))
