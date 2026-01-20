"""Co-sign submission protocol (Story 5.2, Story 5.4, Story 5.5, Story 5.6, FR-6.1, FR-6.4, FR-6.5, FR-6.6, FR-5.1, FR-5.3).

This module defines the protocol for submitting co-signatures on petitions.
Follows hexagonal architecture with port/adapter pattern.

Constitutional Constraints:
- FR-6.1: Seeker SHALL be able to co-sign active petition
- FR-6.2: System SHALL enforce unique constraint (petition_id, signer_id)
- FR-6.3: System SHALL reject co-sign after fate assignment
- FR-6.4: System SHALL increment co-signer count atomically
- FR-6.5: System SHALL check escalation threshold on each co-sign
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.3: System SHALL emit EscalationTriggered event with co_signer_count [P0]
- CT-12: Every action that affects a petition must be witnessed
- CT-13: Halt rejects writes, allows reads
- CT-14: Silence must be expensive - auto-escalation ensures King attention
- NFR-3.5: 0 duplicate signatures ever exist
- NFR-5.1: Rate limiting per identity: Configurable per type
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID


@dataclass(frozen=True)
class CoSignSubmissionResult:
    """Result of a successful co-sign submission.

    Attributes:
        cosign_id: Unique identifier for the created co-signature.
        petition_id: The petition that was co-signed.
        signer_id: The Seeker who co-signed.
        signed_at: When the co-signature was recorded (UTC).
        content_hash: BLAKE3 hash for witness integrity.
        co_signer_count: Updated total co-signer count after this signature.
        identity_verified: Whether signer identity was verified (NFR-5.2, LEGIT-1).
        rate_limit_remaining: Number of co-signs remaining before rate limit (Story 5.4, FR-6.6).
        rate_limit_reset_at: UTC datetime when rate limit window resets (Story 5.4, FR-6.6).
        threshold_reached: Whether escalation threshold was reached (Story 5.5, FR-6.5).
        threshold_value: The escalation threshold for this petition type (Story 5.5, FR-5.2).
        petition_type: The type of petition (CESSATION, GRIEVANCE, etc.).
        escalation_triggered: Whether auto-escalation was triggered (Story 5.6, FR-5.1).
        escalation_id: UUID of the escalation event if triggered (Story 5.6, FR-5.3).
    """

    cosign_id: UUID
    petition_id: UUID
    signer_id: UUID
    signed_at: datetime
    content_hash: str
    co_signer_count: int
    identity_verified: bool = False
    rate_limit_remaining: int | None = None
    rate_limit_reset_at: datetime | None = None
    threshold_reached: bool = False
    threshold_value: int | None = None
    petition_type: str | None = None
    escalation_triggered: bool = False
    escalation_id: UUID | None = None


class CoSignSubmissionProtocol(Protocol):
    """Protocol for submitting co-signatures on petitions (FR-6.1).

    This protocol defines the contract for co-sign submission.
    Implementations must handle:

    1. Halt state check (CT-13: reject writes during halt)
    2. Petition existence validation
    3. Petition state validation (not in terminal state)
    4. Duplicate co-sign detection (FR-6.2, NFR-3.5)
    5. Atomic co-signer count increment (FR-6.4)
    6. Event emission and witnessing (CT-12)

    Constitutional Constraints:
    - FR-6.1: Seeker SHALL be able to co-sign active petition
    - FR-6.2: Unique (petition_id, signer_id)
    - FR-6.3: Reject after fate assignment
    - FR-6.4: Atomic count increment
    - CT-12: Witnessing creates accountability
    - CT-13: Halt rejects writes
    - NFR-3.5: 0 duplicate signatures
    """

    @abstractmethod
    async def submit_co_sign(
        self,
        petition_id: UUID,
        signer_id: UUID,
    ) -> CoSignSubmissionResult:
        """Submit a co-signature on a petition.

        This is the main entry point for co-signing a petition.
        The method must be atomic - either the co-sign completes
        fully (record + count increment + event) or not at all.

        Args:
            petition_id: The petition to co-sign.
            signer_id: The Seeker adding their support.

        Returns:
            CoSignSubmissionResult with the created co-sign details
            and updated co_signer_count.

        Raises:
            SystemHaltedError: System is in halt state (CT-13)
            CoSignPetitionNotFoundError: Petition doesn't exist
            CoSignPetitionFatedError: Petition in terminal state (FR-6.3)
            AlreadySignedError: Signer already co-signed (FR-6.2, NFR-3.5)
        """
        ...


class CoSignRepositoryProtocol(Protocol):
    """Repository protocol for co-sign persistence.

    Separates persistence concerns from submission logic.
    Implementations must ensure atomic operations for count
    increment to satisfy FR-6.4.

    Constitutional Constraints:
    - FR-6.2: Unique (petition_id, signer_id) - database enforced
    - FR-6.4: Atomic count increment
    - NFR-3.5: 0 duplicate signatures
    - NFR-6.4: Full signer list queryable
    """

    @abstractmethod
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

        This operation MUST be atomic:
        1. Insert co_sign record
        2. Increment petition_submissions.co_signer_count
        3. Return new count

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
            AlreadySignedError: Unique constraint violation (petition_id, signer_id).
            CoSignPetitionNotFoundError: Petition doesn't exist.
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    async def get_signers(
        self,
        petition_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UUID]:
        """Get signer IDs for a petition (NFR-6.4: full signer list queryable).

        Args:
            petition_id: The petition to query.
            limit: Maximum signers to return (default 100).
            offset: Starting offset for pagination.

        Returns:
            List of signer UUIDs ordered by signed_at.
        """
        ...
