"""Identity verification port (Story 5.3, NFR-5.2).

This module defines the port for identity verification:
- IdentityStatus: Enum for verification result states
- IdentityVerificationResult: Dataclass for verification outcome
- IdentityStoreProtocol: Protocol for identity store adapters

Constitutional Constraints:
- NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
- LEGIT-1: Manufactured consent via bot co-signers -> verification required
- D7: RFC 7807 error responses with governance extensions

Developer Golden Rules:
1. VERIFY BEFORE WRITE - Check identity before any state changes
2. FAIL LOUD - Reject invalid identities, don't auto-create
3. GRACEFUL DEGRADATION - Service down returns specific error
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import UUID


class IdentityStatus(Enum):
    """Result of identity verification (NFR-5.2).

    Values:
        VALID: Identity exists and is active
        NOT_FOUND: Identity does not exist in the store
        SUSPENDED: Identity exists but is suspended/blocked
        SERVICE_UNAVAILABLE: Cannot verify due to service issues

    Constitutional Constraints:
    - NFR-5.2: Only VALID status allows co-sign
    - LEGIT-1: All other statuses must reject co-sign
    """

    VALID = "valid"
    NOT_FOUND = "not_found"
    SUSPENDED = "suspended"
    SERVICE_UNAVAILABLE = "service_unavailable"


@dataclass(frozen=True)
class IdentityVerificationResult:
    """Result of identity verification (NFR-5.2).

    Encapsulates the outcome of verifying a signer's identity.
    Used by CoSignSubmissionService to determine if co-sign should proceed.

    Constitutional Constraints:
    - NFR-5.2: Only VALID status allows co-sign
    - LEGIT-1: Result includes details for audit trail

    Attributes:
        identity_id: The identity that was verified (same as request).
        status: Result of verification (VALID, NOT_FOUND, SUSPENDED, etc.).
        verified_at: When verification was performed (UTC).
        suspension_reason: Why identity is suspended (if status is SUSPENDED).
        details: Additional details for debugging/audit.
    """

    identity_id: UUID
    status: IdentityStatus
    verified_at: datetime = field(default_factory=lambda: datetime.now(tz=None))
    suspension_reason: str | None = field(default=None)
    details: str | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate result fields after initialization."""
        # Ensure verified_at is timezone-aware if provided
        if self.verified_at.tzinfo is None:
            # Convert to UTC-aware
            from datetime import timezone

            object.__setattr__(
                self, "verified_at", self.verified_at.replace(tzinfo=timezone.utc)
            )

    @property
    def is_valid(self) -> bool:
        """Check if identity verification passed.

        Returns:
            True if identity is valid and active, False otherwise.
        """
        return self.status == IdentityStatus.VALID

    @property
    def should_retry(self) -> bool:
        """Check if verification should be retried.

        Returns:
            True if verification failed due to transient error.
        """
        return self.status == IdentityStatus.SERVICE_UNAVAILABLE

    def to_dict(self) -> dict:
        """Serialize to dictionary for events/logging.

        Returns:
            Dictionary representation suitable for audit trail.
        """
        result = {
            "identity_id": str(self.identity_id),
            "status": self.status.value,
            "verified_at": self.verified_at.isoformat(),
        }
        if self.suspension_reason:
            result["suspension_reason"] = self.suspension_reason
        if self.details:
            result["details"] = self.details
        return result


class IdentityStoreProtocol(Protocol):
    """Protocol for identity store adapters (NFR-5.2).

    Defines the interface for verifying signer identities.
    Implementations may use external identity providers, databases,
    or in-memory stubs for testing.

    Constitutional Constraints:
    - NFR-5.2: Must verify identity before allowing co-sign
    - LEGIT-1: Must detect bot/fake identities

    Methods:
        verify: Check if identity exists and is active
        is_available: Check if the identity service is available

    Example:
        class PostgresIdentityStore(IdentityStoreProtocol):
            def verify(self, identity_id: UUID) -> IdentityVerificationResult:
                # Check PostgreSQL for identity
                ...
    """

    def verify(self, identity_id: UUID) -> IdentityVerificationResult:
        """Verify an identity exists and is active.

        Args:
            identity_id: The UUID of the identity to verify.

        Returns:
            IdentityVerificationResult with status and details.

        Note:
            This method should NOT raise exceptions for invalid/suspended
            identities. Instead, return appropriate status in result.
            Only raise for truly exceptional conditions (connectivity, etc.).
        """
        ...

    def is_available(self) -> bool:
        """Check if identity service is available.

        Returns:
            True if service can process verification requests.

        Note:
            Used for health checks and circuit breaker patterns.
        """
        ...
