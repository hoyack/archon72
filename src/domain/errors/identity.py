"""Identity verification domain errors (Story 5.3, NFR-5.2).

This module defines errors related to identity verification:
- IdentityNotFoundError: Unknown signer identity
- IdentitySuspendedError: Suspended/blocked identity
- IdentityServiceUnavailableError: Identity service unavailable

Constitutional Constraints:
- NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
- LEGIT-1: Manufactured consent via bot co-signers -> verification required
- D7: RFC 7807 error responses with governance extensions

Developer Golden Rules:
1. VERIFY BEFORE WRITE - Check identity before any state changes
2. FAIL LOUD - Reject invalid identities, don't auto-create
3. GRACEFUL DEGRADATION - Service down returns 503, not silent failure
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID


class IdentityVerificationError(Exception):
    """Base class for identity verification errors.

    All identity verification errors inherit from this base,
    enabling catch-all handling while preserving specific types.

    Attributes:
        signer_id: The signer identity that caused the error.
        message: Human-readable error description.
        nfr_reference: NFR requirement this error relates to.
        hardening_control: Red team control this error enforces.
    """

    def __init__(
        self,
        signer_id: UUID,
        message: str,
        nfr_reference: str = "NFR-5.2",
        hardening_control: str = "LEGIT-1",
    ) -> None:
        """Initialize identity verification error.

        Args:
            signer_id: The identity that triggered the error.
            message: Human-readable error message.
            nfr_reference: NFR requirement reference.
            hardening_control: Hardening control reference.
        """
        self.signer_id = signer_id
        self.message = message
        self.nfr_reference = nfr_reference
        self.hardening_control = hardening_control
        super().__init__(message)

    def to_dict(self) -> dict:
        """Convert to RFC 7807 compatible dictionary.

        Returns:
            Dictionary with error details for API response.
        """
        return {
            "signer_id": str(self.signer_id),
            "message": self.message,
            "nfr_reference": self.nfr_reference,
            "hardening_control": self.hardening_control,
        }


class IdentityNotFoundError(IdentityVerificationError):
    """Raised when signer identity is not found in identity store.

    HTTP Status: 403 Forbidden (not 401 - request is authenticated
    but identity is unknown to the petition system).

    Constitutional Constraints:
    - NFR-5.2: Only verified identities can co-sign
    - LEGIT-1: Prevents bot co-signers with fabricated IDs

    Example:
        >>> raise IdentityNotFoundError(
        ...     signer_id=UUID("00000000-0000-0000-0000-000000000001")
        ... )
    """

    ERROR_CODE = "IDENTITY_NOT_FOUND"
    HTTP_STATUS = 403

    def __init__(
        self,
        signer_id: UUID,
        message: Optional[str] = None,
    ) -> None:
        """Initialize identity not found error.

        Args:
            signer_id: The unknown signer identity.
            message: Optional custom message.
        """
        if message is None:
            message = f"Signer identity {signer_id} not found in identity store"
        super().__init__(
            signer_id=signer_id,
            message=message,
            nfr_reference="NFR-5.2",
            hardening_control="LEGIT-1",
        )
        self.error_code = self.ERROR_CODE

    def to_rfc7807(self, instance: str) -> dict:
        """Convert to RFC 7807 problem details format.

        Args:
            instance: The request instance URI (e.g., /api/v1/petitions/{id}/co-sign)

        Returns:
            RFC 7807 compliant error response.
        """
        return {
            "type": "urn:archon72:identity:not-found",
            "title": "Identity Not Found",
            "status": self.HTTP_STATUS,
            "detail": self.message,
            "instance": instance,
            "error_code": self.error_code,
            "nfr_reference": self.nfr_reference,
            "hardening_control": self.hardening_control,
        }


class IdentitySuspendedError(IdentityVerificationError):
    """Raised when signer identity is suspended/blocked.

    HTTP Status: 403 Forbidden

    A suspended identity exists in the system but has been blocked
    from performing actions, typically due to abuse detection or
    manual governance action.

    Constitutional Constraints:
    - NFR-5.2: Only active identities can co-sign
    - LEGIT-1: Suspended identities cannot manufacture consent

    Example:
        >>> raise IdentitySuspendedError(
        ...     signer_id=UUID("00000000-0000-0000-0000-000000000001"),
        ...     reason="Abuse pattern detected"
        ... )
    """

    ERROR_CODE = "IDENTITY_SUSPENDED"
    HTTP_STATUS = 403

    def __init__(
        self,
        signer_id: UUID,
        reason: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        """Initialize identity suspended error.

        Args:
            signer_id: The suspended signer identity.
            reason: Why the identity was suspended (optional).
            message: Optional custom message.
        """
        self.reason = reason
        if message is None:
            if reason:
                message = f"Signer identity {signer_id} is suspended: {reason}"
            else:
                message = f"Signer identity {signer_id} is suspended"
        super().__init__(
            signer_id=signer_id,
            message=message,
            nfr_reference="NFR-5.2",
            hardening_control="LEGIT-1",
        )
        self.error_code = self.ERROR_CODE

    def to_rfc7807(self, instance: str) -> dict:
        """Convert to RFC 7807 problem details format.

        Args:
            instance: The request instance URI.

        Returns:
            RFC 7807 compliant error response.
        """
        result = {
            "type": "urn:archon72:identity:suspended",
            "title": "Identity Suspended",
            "status": self.HTTP_STATUS,
            "detail": self.message,
            "instance": instance,
            "error_code": self.error_code,
            "nfr_reference": self.nfr_reference,
            "hardening_control": self.hardening_control,
        }
        if self.reason:
            result["suspension_reason"] = self.reason
        return result


class IdentityServiceUnavailableError(IdentityVerificationError):
    """Raised when identity verification service is unavailable.

    HTTP Status: 503 Service Unavailable

    This is a transient error - the client should retry after
    the Retry-After period. The co-sign is NOT rejected permanently,
    just temporarily unavailable.

    Constitutional Constraints:
    - NFR-5.2: Cannot verify identity if service is down
    - Graceful degradation: Return 503 with Retry-After

    Example:
        >>> raise IdentityServiceUnavailableError(
        ...     signer_id=UUID("00000000-0000-0000-0000-000000000001"),
        ...     retry_after=30
        ... )
    """

    ERROR_CODE = "IDENTITY_SERVICE_UNAVAILABLE"
    HTTP_STATUS = 503

    def __init__(
        self,
        signer_id: UUID,
        retry_after: int = 30,
        message: Optional[str] = None,
    ) -> None:
        """Initialize identity service unavailable error.

        Args:
            signer_id: The signer identity that couldn't be verified.
            retry_after: Seconds to wait before retrying.
            message: Optional custom message.
        """
        self.retry_after = retry_after
        if message is None:
            message = "Identity verification service is temporarily unavailable"
        super().__init__(
            signer_id=signer_id,
            message=message,
            nfr_reference="NFR-5.2",
            hardening_control="LEGIT-1",
        )
        self.error_code = self.ERROR_CODE

    def to_rfc7807(self, instance: str) -> dict:
        """Convert to RFC 7807 problem details format.

        Args:
            instance: The request instance URI.

        Returns:
            RFC 7807 compliant error response with retry_after.
        """
        return {
            "type": "urn:archon72:identity:service-unavailable",
            "title": "Identity Service Unavailable",
            "status": self.HTTP_STATUS,
            "detail": self.message,
            "instance": instance,
            "error_code": self.error_code,
            "retry_after": self.retry_after,
            "nfr_reference": self.nfr_reference,
            "hardening_control": self.hardening_control,
        }
