"""Ceremony witness domain model (FR69, CT-12).

This module defines the CeremonyWitness value object for tracking
witness attestations during key generation ceremonies.

Constitutional Constraints:
- FR69: Keeper keys SHALL be generated through witnessed ceremony
- CT-12: Witnessing creates accountability -> Witness signatures required

Note: CeremonyWitness is immutable (frozen dataclass) to ensure
witness attestations cannot be tampered with after creation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.domain.errors.constitutional import ConstitutionalViolationError


class WitnessType(Enum):
    """Type of witness for a ceremony.

    KEEPER: Human Keeper witness
    SYSTEM: System-level witness (automated verification)
    EXTERNAL: External third-party witness
    """

    KEEPER = "keeper"
    SYSTEM = "system"
    EXTERNAL = "external"


@dataclass(frozen=True, eq=True)
class CeremonyWitness:
    """Witness attestation for a key generation ceremony.

    Represents a single witness's attestation that they observed
    the ceremony being conducted properly. The signature proves
    the witness authorized the ceremony.

    Constitutional Constraints:
    - FR69: Keeper keys require witnessed ceremony
    - CT-12: Witnessing creates accountability

    Attributes:
        witness_id: ID of the witness (e.g., "KEEPER:alice", "SYSTEM:hsm")
        witnessed_at: When the witness signed (UTC)
        signature: Ed25519 signature bytes proving witness attestation
        witness_type: Type of witness (KEEPER, SYSTEM, EXTERNAL)

    Note:
        Frozen dataclass ensures immutability - witness attestations
        cannot be modified after creation.
    """

    # Witness identifier
    witness_id: str

    # Signature proving attestation (Ed25519)
    signature: bytes

    # Type of witness
    witness_type: WitnessType

    # When witness signed
    witnessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ConstitutionalViolationError: If any field fails validation.
        """
        self._validate_witness_id()
        self._validate_signature()
        self._validate_witness_type()

    def _validate_witness_id(self) -> None:
        """Validate witness_id is non-empty string."""
        if not isinstance(self.witness_id, str) or not self.witness_id.strip():
            raise ConstitutionalViolationError(
                "CT-12: Witness validation failed - witness_id must be non-empty string"
            )

    def _validate_signature(self) -> None:
        """Validate signature is non-empty bytes."""
        if not isinstance(self.signature, bytes):
            raise ConstitutionalViolationError(
                "CT-12: Witness validation failed - signature must be bytes"
            )
        if len(self.signature) == 0:
            raise ConstitutionalViolationError(
                "CT-12: Witness validation failed - signature cannot be empty"
            )

    def _validate_witness_type(self) -> None:
        """Validate witness_type is WitnessType enum."""
        if not isinstance(self.witness_type, WitnessType):
            raise ConstitutionalViolationError(
                f"CT-12: Witness validation failed - witness_type must be WitnessType, got {type(self.witness_type).__name__}"
            )

    def __hash__(self) -> int:
        """Hash based on witness_id for set membership."""
        return hash(self.witness_id)
