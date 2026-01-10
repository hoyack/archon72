"""Petition domain models (Story 7.2, FR39).

This module defines the domain models for external observer petitions:
- Petition: Main petition entity with submitter and co-signers
- CoSigner: Individual co-signer with signature

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All petitions must be tracked
- CT-12: Witnessing creates accountability → All signatures must be verifiable
- FR39: External observers can petition with 100+ co-signers

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before modifying petitions (writes)
2. WITNESS EVERYTHING - All petition events require attribution
3. FAIL LOUD - Never silently swallow signature errors
4. READS DURING HALT - Petition queries work during halt (CT-13)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.domain.events.petition import PetitionStatus


@dataclass(frozen=True, eq=True)
class CoSigner:
    """A co-signer on a petition (FR39, AC2).

    Represents an external observer who has co-signed a petition
    with their Ed25519 signature.

    Constitutional Constraint (CT-12):
    All signatures must be cryptographically verifiable.

    Attributes:
        public_key: Hex-encoded Ed25519 public key.
        signature: Hex-encoded Ed25519 signature over petition content.
        signed_at: When the co-signature was added (UTC).
        sequence: Order of this co-signer (1-based).
    """

    public_key: str
    signature: str
    signed_at: datetime
    sequence: int


@dataclass(frozen=True, eq=True)
class Petition:
    """An external observer petition for cessation consideration (FR39).

    A petition allows external observers to raise cessation concerns.
    When 100+ observers co-sign, cessation is automatically placed on
    the Conclave agenda.

    Constitutional Constraints:
    - FR39: 100+ co-signers triggers cessation agenda placement
    - CT-11: Silent failure destroys legitimacy -> Must track all petitions
    - CT-12: Witnessing creates accountability -> All signatures verifiable
    - AC2: Duplicate co-signatures from same public key are rejected

    Attributes:
        petition_id: Unique identifier for this petition.
        submitter_public_key: Hex-encoded Ed25519 public key of submitter.
        submitter_signature: Hex-encoded Ed25519 signature over petition content.
        petition_content: Reason for cessation concern.
        created_timestamp: When the petition was submitted (UTC).
        status: Current status (open, threshold_met, closed).
        cosigners: Tuple of co-signers (immutable).
        threshold_met_at: When 100 co-signers was reached (UTC), or None.
    """

    petition_id: UUID
    submitter_public_key: str
    submitter_signature: str
    petition_content: str
    created_timestamp: datetime
    status: PetitionStatus = field(default=PetitionStatus.OPEN)
    cosigners: tuple[CoSigner, ...] = field(default_factory=tuple)
    threshold_met_at: Optional[datetime] = field(default=None)

    @property
    def cosigner_count(self) -> int:
        """Return the number of co-signers.

        Returns:
            Number of co-signers (not including original submitter).
        """
        return len(self.cosigners)

    @property
    def all_public_keys(self) -> tuple[str, ...]:
        """Return all public keys (submitter + co-signers).

        Returns:
            Tuple of all public keys associated with this petition.
        """
        return (self.submitter_public_key,) + tuple(c.public_key for c in self.cosigners)

    def has_cosigned(self, public_key: str) -> bool:
        """Check if a public key has already co-signed this petition.

        Args:
            public_key: Hex-encoded public key to check.

        Returns:
            True if the key has already co-signed, False otherwise.
        """
        # Check submitter
        if self.submitter_public_key == public_key:
            return True

        # Check co-signers
        return any(c.public_key == public_key for c in self.cosigners)

    def add_cosigner(self, cosigner: CoSigner) -> "Petition":
        """Create a new petition with an additional co-signer.

        Since Petition is frozen, this returns a new Petition instance
        with the co-signer added.

        Args:
            cosigner: The co-signer to add.

        Returns:
            New Petition instance with the co-signer added.
        """
        return Petition(
            petition_id=self.petition_id,
            submitter_public_key=self.submitter_public_key,
            submitter_signature=self.submitter_signature,
            petition_content=self.petition_content,
            created_timestamp=self.created_timestamp,
            status=self.status,
            cosigners=self.cosigners + (cosigner,),
            threshold_met_at=self.threshold_met_at,
        )

    def with_status(self, status: PetitionStatus) -> "Petition":
        """Create a new petition with updated status.

        Since Petition is frozen, this returns a new Petition instance
        with the updated status.

        Args:
            status: The new status.

        Returns:
            New Petition instance with the updated status.
        """
        return Petition(
            petition_id=self.petition_id,
            submitter_public_key=self.submitter_public_key,
            submitter_signature=self.submitter_signature,
            petition_content=self.petition_content,
            created_timestamp=self.created_timestamp,
            status=status,
            cosigners=self.cosigners,
            threshold_met_at=self.threshold_met_at,
        )

    def with_threshold_met(self, met_at: datetime) -> "Petition":
        """Create a new petition marked as threshold met.

        Since Petition is frozen, this returns a new Petition instance
        with threshold_met status and timestamp.

        Args:
            met_at: When the threshold was met (UTC).

        Returns:
            New Petition instance with threshold_met status.
        """
        return Petition(
            petition_id=self.petition_id,
            submitter_public_key=self.submitter_public_key,
            submitter_signature=self.submitter_signature,
            petition_content=self.petition_content,
            created_timestamp=self.created_timestamp,
            status=PetitionStatus.THRESHOLD_MET,
            cosigners=self.cosigners,
            threshold_met_at=met_at,
        )

    def canonical_content_bytes(self) -> bytes:
        """Return canonical bytes of petition content for signature verification.

        This is what signers sign: the petition content encoded as UTF-8.

        Returns:
            UTF-8 encoded bytes of petition content.
        """
        return self.petition_content.encode("utf-8")
