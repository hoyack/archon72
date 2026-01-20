"""Extension request stub implementation (Story 4.5, FR-4.4).

This module provides an in-memory implementation of ExtensionRequestProtocol
for testing and development purposes.

Constitutional Constraints:
- FR-4.4: Knight SHALL be able to request extension (max 2) [P1]
- NFR-4.4: Referral deadline persistence: Survives scheduler restart
- CT-12: Every action that affects an Archon must be witnessed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.application.ports.extension_request import (
    ExtensionRequest,
    ExtensionResult,
)
from src.domain.errors.referral import (
    ExtensionReasonRequiredError,
    InvalidReferralStateError,
    MaxExtensionsReachedError,
    NotAssignedKnightError,
    ReferralNotFoundError,
)
from src.domain.models.referral import (
    REFERRAL_DEFAULT_CYCLE_DURATION,
    REFERRAL_MAX_EXTENSIONS,
    Referral,
    ReferralStatus,
)

if TYPE_CHECKING:
    pass


# Configuration constants
MIN_REASON_LENGTH: int = 10
EXTENSION_DURATION_CYCLES: int = 1


@dataclass
class ExtensionRecord:
    """Record of a processed extension for tracking.

    Attributes:
        referral_id: The referral that was extended.
        knight_id: The Knight who requested extension.
        previous_deadline: Deadline before extension.
        new_deadline: Deadline after extension.
        extensions_granted: Total extensions after this one.
        reason: Reason for extension.
        witness_hash: Witness hash for the extension.
        extended_at: When the extension was processed.
    """

    referral_id: UUID
    knight_id: UUID
    previous_deadline: datetime
    new_deadline: datetime
    extensions_granted: int
    reason: str
    witness_hash: str
    extended_at: datetime


class ExtensionRequestStub:
    """In-memory implementation of ExtensionRequestProtocol.

    This stub maintains referral state and tracks extensions for testing.
    It simulates all validation and business logic without external dependencies.

    Example:
        >>> stub = ExtensionRequestStub()
        >>> stub.add_referral(referral)  # Add a test referral
        >>> result = await stub.request_extension(
        ...     ExtensionRequest(
        ...         referral_id=referral.referral_id,
        ...         knight_id=knight_id,
        ...         reason="Need more time to review",
        ...     )
        ... )
    """

    def __init__(
        self,
        extension_duration: timedelta | None = None,
        max_extensions: int = REFERRAL_MAX_EXTENSIONS,
        min_reason_length: int = MIN_REASON_LENGTH,
    ) -> None:
        """Initialize the extension request stub.

        Args:
            extension_duration: Duration to extend per request (default: 1 week).
            max_extensions: Maximum number of extensions allowed (default: 2).
            min_reason_length: Minimum length for extension reason (default: 10).
        """
        self._referrals: dict[UUID, Referral] = {}
        self._extensions: list[ExtensionRecord] = []
        self._extension_duration = extension_duration or (
            EXTENSION_DURATION_CYCLES * REFERRAL_DEFAULT_CYCLE_DURATION
        )
        self._max_extensions = max_extensions
        self._min_reason_length = min_reason_length
        self._witness_counter = 0

    def add_referral(self, referral: Referral) -> None:
        """Add a referral for testing.

        Args:
            referral: The referral to add.
        """
        self._referrals[referral.referral_id] = referral

    def get_referral(self, referral_id: UUID) -> Referral | None:
        """Get a referral by ID.

        Args:
            referral_id: The referral UUID.

        Returns:
            The referral if found, None otherwise.
        """
        return self._referrals.get(referral_id)

    def get_extensions(self) -> list[ExtensionRecord]:
        """Get all recorded extensions.

        Returns:
            List of all extension records.
        """
        return list(self._extensions)

    def get_extensions_for_referral(self, referral_id: UUID) -> list[ExtensionRecord]:
        """Get extensions for a specific referral.

        Args:
            referral_id: The referral UUID.

        Returns:
            List of extension records for this referral.
        """
        return [e for e in self._extensions if e.referral_id == referral_id]

    def clear(self) -> None:
        """Clear all stored data."""
        self._referrals.clear()
        self._extensions.clear()
        self._witness_counter = 0

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
            ReferralNotFoundError: Referral doesn't exist.
            NotAssignedKnightError: Requester is not the assigned Knight.
            InvalidReferralStateError: Referral is not in valid state.
            MaxExtensionsReachedError: Maximum extensions already granted.
            ExtensionReasonRequiredError: Reason is missing or too short.
        """
        # Step 1: Validate reason
        trimmed_reason = request.reason.strip() if request.reason else ""
        if len(trimmed_reason) < self._min_reason_length:
            raise ExtensionReasonRequiredError(
                referral_id=request.referral_id,
                provided_length=len(trimmed_reason),
                min_length=self._min_reason_length,
            )

        # Step 2: Retrieve the referral
        referral = self._referrals.get(request.referral_id)
        if referral is None:
            raise ReferralNotFoundError(referral_id=request.referral_id)

        # Step 3: Check for maximum extensions
        if referral.extensions_granted >= self._max_extensions:
            raise MaxExtensionsReachedError(
                referral_id=request.referral_id,
                extensions_granted=referral.extensions_granted,
            )

        # Step 4: Validate referral state
        valid_states = [ReferralStatus.ASSIGNED, ReferralStatus.IN_REVIEW]
        if referral.status not in valid_states:
            raise InvalidReferralStateError(
                referral_id=request.referral_id,
                current_status=referral.status.value,
                required_statuses=[s.value for s in valid_states],
                operation="extension request",
            )

        # Step 5: Authorization check
        if referral.assigned_knight_id is None:
            raise NotAssignedKnightError(
                referral_id=request.referral_id,
                requester_id=request.knight_id,
            )

        if request.knight_id != referral.assigned_knight_id:
            raise NotAssignedKnightError(
                referral_id=request.referral_id,
                requester_id=request.knight_id,
                assigned_knight_id=referral.assigned_knight_id,
            )

        # Step 6: Calculate new deadline
        previous_deadline = referral.deadline
        new_deadline = previous_deadline + self._extension_duration
        extended_at = datetime.now(timezone.utc)

        # Step 7: Update referral with extension
        updated_referral = referral.with_extension(new_deadline)
        extensions_granted = updated_referral.extensions_granted
        self._referrals[request.referral_id] = updated_referral

        # Step 8: Generate witness hash (stub - just increment counter)
        self._witness_counter += 1
        witness_hash = f"ext-witness-{self._witness_counter:06d}"

        # Step 9: Record the extension
        record = ExtensionRecord(
            referral_id=request.referral_id,
            knight_id=request.knight_id,
            previous_deadline=previous_deadline,
            new_deadline=new_deadline,
            extensions_granted=extensions_granted,
            reason=trimmed_reason,
            witness_hash=witness_hash,
            extended_at=extended_at,
        )
        self._extensions.append(record)

        return ExtensionResult(
            referral_id=request.referral_id,
            petition_id=referral.petition_id,
            knight_id=request.knight_id,
            previous_deadline=previous_deadline,
            new_deadline=new_deadline,
            extensions_granted=extensions_granted,
            reason=trimmed_reason,
            witness_hash=witness_hash,
            extended_at=extended_at,
        )

    async def get_extension_count(self, referral_id: UUID) -> int:
        """Get the number of extensions granted for a referral.

        Args:
            referral_id: The referral to check.

        Returns:
            Number of extensions granted (0, 1, or 2).

        Raises:
            ReferralNotFoundError: If referral doesn't exist.
        """
        referral = self._referrals.get(referral_id)
        if referral is None:
            raise ReferralNotFoundError(referral_id=referral_id)
        return referral.extensions_granted

    async def can_extend(self, referral_id: UUID) -> bool:
        """Check if a referral can be extended.

        Args:
            referral_id: The referral to check.

        Returns:
            True if extension is possible, False otherwise.

        Raises:
            ReferralNotFoundError: If referral doesn't exist.
        """
        referral = self._referrals.get(referral_id)
        if referral is None:
            raise ReferralNotFoundError(referral_id=referral_id)
        return referral.can_extend()
