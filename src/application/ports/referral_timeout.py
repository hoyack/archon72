"""Referral timeout port for auto-acknowledge (Story 4.6, FR-4.5).

This module defines the abstract interface for referral timeout processing
in the Knight referral workflow.

Constitutional Constraints:
- FR-4.5: System SHALL auto-ACKNOWLEDGE on referral timeout (reason: EXPIRED)
- NFR-3.4: Referral timeout reliability: 100% timeouts fire
- NFR-4.4: Referral deadline persistence: Survives scheduler restart
- CT-12: Every action that affects an Archon must be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before modifying referrals (writes)
2. WITNESS EVERYTHING - All timeout events require attribution
3. FAIL LOUD - Never silently swallow timeout errors
4. READS DURING HALT - Referral queries work during halt (CT-13)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID


class ReferralTimeoutAction(str, Enum):
    """Result actions from timeout processing.

    Describes what happened when processing a referral timeout.
    """

    EXPIRED = "expired"
    """Referral was expired and petition auto-acknowledged."""

    ALREADY_COMPLETED = "already_completed"
    """Referral was already completed (no-op)."""

    ALREADY_EXPIRED = "already_expired"
    """Referral was already expired (idempotent no-op)."""

    NOT_FOUND = "not_found"
    """Referral was not found."""


@dataclass(frozen=True)
class ReferralTimeoutResult:
    """Result of referral timeout processing (Story 4.6, FR-4.5).

    Encapsulates the outcome of processing a referral timeout job,
    including the action taken and any generated identifiers.

    Attributes:
        referral_id: The referral that was processed.
        petition_id: The associated petition.
        action: What action was taken.
        acknowledgment_id: ID of created acknowledgment (if EXPIRED).
        expired_at: When expiration was processed (if EXPIRED).
        witness_hash: BLAKE3 witness hash (if EXPIRED).
        rationale: Auto-generated rationale (if EXPIRED).
        message: Human-readable description of result.
    """

    referral_id: UUID
    petition_id: UUID
    action: ReferralTimeoutAction
    acknowledgment_id: UUID | None = field(default=None)
    expired_at: datetime | None = field(default=None)
    witness_hash: str | None = field(default=None)
    rationale: str | None = field(default=None)
    message: str = field(default="")

    @property
    def was_processed(self) -> bool:
        """Check if the timeout resulted in actual processing.

        Returns:
            True if referral was expired, False for no-op cases.
        """
        return self.action == ReferralTimeoutAction.EXPIRED

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dict for logging/storage.

        Returns:
            Dict representation of the result.
        """
        result: dict[str, Any] = {
            "referral_id": str(self.referral_id),
            "petition_id": str(self.petition_id),
            "action": self.action.value,
            "was_processed": self.was_processed,
            "message": self.message,
        }

        if self.acknowledgment_id:
            result["acknowledgment_id"] = str(self.acknowledgment_id)
        if self.expired_at:
            result["expired_at"] = self.expired_at.isoformat()
        if self.witness_hash:
            result["witness_hash"] = self.witness_hash
        if self.rationale:
            result["rationale"] = self.rationale

        return result


class ReferralTimeoutProtocol(Protocol):
    """Protocol for referral timeout processing (Story 4.6, FR-4.5).

    Defines the contract for handling referral timeout jobs when
    Knights fail to submit recommendations before the deadline.

    Constitutional Constraints:
    - FR-4.5: Auto-ACKNOWLEDGE on timeout with EXPIRED reason
    - NFR-3.4: 100% timeout reliability
    - CT-12: All timeout actions must be witnessed

    Example:
        >>> handler = ReferralTimeoutService(...)
        >>> result = await handler.process_timeout(
        ...     referral_id=referral.referral_id,
        ...     petition_id=referral.petition_id,
        ...     realm_id=referral.realm_id,
        ... )
        >>> if result.was_processed:
        ...     print(f"Expired referral {result.referral_id}")
    """

    async def process_timeout(
        self,
        referral_id: UUID,
        petition_id: UUID,
        realm_id: UUID,
    ) -> ReferralTimeoutResult:
        """Process a referral timeout.

        Called when a referral deadline job fires. Handles the full
        timeout flow including:
        1. Checking if referral is still eligible for timeout
        2. Expiring the referral (if not terminal)
        3. Auto-acknowledging the petition with EXPIRED reason
        4. Emitting witnessed events

        Idempotency: Safe to call multiple times for the same referral.
        If already COMPLETED or EXPIRED, returns appropriate no-op result.

        Args:
            referral_id: UUID of the referral to timeout.
            petition_id: UUID of the associated petition.
            realm_id: UUID of the realm for rationale generation.

        Returns:
            ReferralTimeoutResult describing the outcome.

        Raises:
            ReferralTimeoutError: If timeout processing fails unrecoverably.
        """
        ...

    async def handle_expired_referral(
        self,
        referral_id: UUID,
    ) -> bool:
        """Check if a referral has been handled for timeout.

        Used by job handlers to verify idempotency before processing.

        Args:
            referral_id: UUID of the referral to check.

        Returns:
            True if referral is in terminal state (COMPLETED or EXPIRED).
            False if referral still needs timeout processing.
        """
        ...


class ReferralTimeoutError(Exception):
    """Base exception for referral timeout errors.

    Raised when timeout processing encounters an unrecoverable error
    that should result in job failure/retry.
    """

    def __init__(
        self,
        referral_id: UUID,
        reason: str,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral that failed timeout processing.
            reason: Description of what went wrong.
        """
        self.referral_id = referral_id
        self.reason = reason
        super().__init__(
            f"Referral timeout processing failed for {referral_id}: {reason}"
        )


class ReferralTimeoutWitnessError(ReferralTimeoutError):
    """Raised when witness hash generation fails during timeout.

    Per CT-12, timeout actions must be witnessed. If hash generation
    fails, the timeout cannot be processed.
    """

    def __init__(
        self,
        referral_id: UUID,
        petition_id: UUID,
        reason: str,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID.
            petition_id: The petition UUID.
            reason: Why hash generation failed.
        """
        self.petition_id = petition_id
        super().__init__(
            referral_id=referral_id,
            reason=f"Witness hash generation failed for petition {petition_id}: {reason}",
        )


class ReferralTimeoutAcknowledgeError(ReferralTimeoutError):
    """Raised when auto-acknowledge fails during timeout.

    If the acknowledgment service fails, the timeout cannot complete.
    The job should be retried.
    """

    def __init__(
        self,
        referral_id: UUID,
        petition_id: UUID,
        reason: str,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID.
            petition_id: The petition UUID.
            reason: Why acknowledgment failed.
        """
        self.petition_id = petition_id
        super().__init__(
            referral_id=referral_id,
            reason=f"Auto-acknowledge failed for petition {petition_id}: {reason}",
        )
