"""Extension request protocol (Story 4.5, FR-4.4).

This module defines the protocol for processing Knight deadline extension requests.

Constitutional Constraints:
- FR-4.4: Knight SHALL be able to request extension (max 2) [P1]
- NFR-4.4: Referral deadline persistence: Survives scheduler restart
- CT-12: Every action that affects an Archon must be witnessed
- NFR-5.2: Authorization: Only assigned Knight can request extension
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ExtensionRequest:
    """Request to extend a referral deadline.

    Attributes:
        referral_id: The referral to extend.
        knight_id: The Knight requesting the extension (must be assigned).
        reason: Explanation for why extension is needed.
    """

    referral_id: UUID
    knight_id: UUID
    reason: str


@dataclass(frozen=True)
class ExtensionResult:
    """Result of a successful extension request.

    Attributes:
        referral_id: The extended referral.
        petition_id: The petition being reviewed.
        knight_id: The Knight who requested extension.
        previous_deadline: The deadline before extension.
        new_deadline: The deadline after extension.
        extensions_granted: Total extensions granted (1 or 2).
        reason: The reason provided for extension.
        witness_hash: BLAKE3 hash for witnessing (CT-12).
        extended_at: When the extension was processed.
    """

    referral_id: UUID
    petition_id: UUID
    knight_id: UUID
    previous_deadline: datetime
    new_deadline: datetime
    extensions_granted: int
    reason: str
    witness_hash: str
    extended_at: datetime


class ExtensionRequestProtocol(Protocol):
    """Protocol for processing Knight deadline extension requests.

    This protocol defines the contract for extending referral deadlines.
    Implementations must:
    - Verify the requester is the assigned Knight (NFR-5.2)
    - Check that max extensions (2) haven't been reached (FR-4.4)
    - Verify the referral is in a valid state (ASSIGNED or IN_REVIEW)
    - Update the deadline and emit ReferralExtendedEvent (CT-12)
    - Reschedule the deadline job (NFR-4.4)

    Raises:
        MaxExtensionsReachedError: If 2 extensions already granted.
        NotAssignedKnightError: If requester is not the assigned Knight.
        InvalidReferralStateError: If referral is not in valid state.
        ExtensionReasonRequiredError: If reason is missing or too short.
        ReferralNotFoundError: If referral doesn't exist.
    """

    async def request_extension(
        self,
        request: ExtensionRequest,
    ) -> ExtensionResult:
        """Process a deadline extension request.

        Args:
            request: The extension request details.

        Returns:
            ExtensionResult with new deadline and witness hash.

        Raises:
            MaxExtensionsReachedError: If 2 extensions already granted.
            NotAssignedKnightError: If requester is not the assigned Knight.
            InvalidReferralStateError: If referral is not in valid state.
            ExtensionReasonRequiredError: If reason is missing or too short.
            ReferralNotFoundError: If referral doesn't exist.
        """
        ...

    async def get_extension_count(self, referral_id: UUID) -> int:
        """Get the number of extensions granted for a referral.

        Args:
            referral_id: The referral to check.

        Returns:
            Number of extensions granted (0, 1, or 2).

        Raises:
            ReferralNotFoundError: If referral doesn't exist.
        """
        ...

    async def can_extend(self, referral_id: UUID) -> bool:
        """Check if a referral can be extended.

        Args:
            referral_id: The referral to check.

        Returns:
            True if extension is possible, False otherwise.

        Raises:
            ReferralNotFoundError: If referral doesn't exist.
        """
        ...
