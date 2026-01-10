"""Witness domain model for event attestation (FR4, FR5).

This module defines the Witness entity for the constitutional event store.
Witnesses attest to event creation, providing accountability and verification.

Constitutional Constraints:
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist
- CT-12: Witnessing creates accountability

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Witness attribution creates verifiable attestation

Note: Witnesses are NOT agents. Witnesses attest to events, agents create events.
This distinction is constitutional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.errors.constitutional import ConstitutionalViolationError

# Witness ID prefix
WITNESS_PREFIX: str = "WITNESS:"


@dataclass(frozen=True, eq=True)
class Witness:
    """Witness entity for event attestation - immutable.

    Witnesses are the foundation of accountability in the constitutional
    event store. They attest to event creation, providing an independent
    verification that an event occurred.

    Constitutional Constraints:
    - FR4: Events must have atomic witness attribution
    - FR5: No unwitnessed events can exist
    - CT-12: Witnessing creates accountability

    Attributes:
        witness_id: Unique identifier (format: "WITNESS:{uuid}")
        public_key: Ed25519 public key bytes (32 bytes)
        active_from: When this witness became active
        active_until: When this witness was deactivated (None = currently active)

    Note:
        Witnesses attest, agents create. Different roles, different signing contexts.
    """

    # Witness identifier (format: "WITNESS:{uuid}")
    witness_id: str

    # Ed25519 public key bytes (32 bytes)
    public_key: bytes

    # Temporal validity
    active_from: datetime

    # Expiry (None = currently active)
    active_until: datetime | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ConstitutionalViolationError: If any field fails validation.
        """
        self._validate_witness_id()
        self._validate_public_key()

    def _validate_witness_id(self) -> None:
        """Validate witness_id has correct format."""
        if not isinstance(self.witness_id, str) or not self.witness_id.strip():
            raise ConstitutionalViolationError(
                "FR4: Witness validation failed - witness_id must be non-empty string"
            )
        if not self.witness_id.startswith(WITNESS_PREFIX):
            raise ConstitutionalViolationError(
                f"FR4: Witness validation failed - witness_id must start with '{WITNESS_PREFIX}', got {self.witness_id}"
            )

    def _validate_public_key(self) -> None:
        """Validate public_key is Ed25519 public key (32 bytes)."""
        if not isinstance(self.public_key, bytes):
            raise ConstitutionalViolationError(
                "FR4: Witness validation failed - public_key must be bytes"
            )
        # Ed25519 public keys are exactly 32 bytes
        if len(self.public_key) != 32:
            raise ConstitutionalViolationError(
                f"FR4: Witness validation failed - public_key must be 32 bytes (Ed25519), got {len(self.public_key)}"
            )

    def is_active(self, at: datetime | None = None) -> bool:
        """Check if witness is active at given time.

        Used for witness selection - only active witnesses can attest events.

        Args:
            at: The time to check against. Defaults to current time.

        Returns:
            True if witness was active at the given time, False otherwise.
        """
        check_time = at or datetime.now(timezone.utc)

        # Must be after active_from
        if check_time < self.active_from:
            return False

        # If no expiry, witness is still active
        if self.active_until is None:
            return True

        # Must be before active_until
        return check_time < self.active_until

    def is_currently_active(self) -> bool:
        """Check if this witness is currently active.

        Convenience method that calls is_active with current time.

        Returns:
            True if witness is currently active, False otherwise.
        """
        return self.is_active()

    def __hash__(self) -> int:
        """Hash based on witness_id.

        Note: public_key is excluded from hash since bytes are included
        in the dataclass comparison but we want set membership to be
        based on witness_id alone.
        """
        return hash(self.witness_id)
