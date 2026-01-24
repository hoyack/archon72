"""Co-sign domain errors (Story 5.2, FR-6.1, FR-6.3, NFR-3.5).

This module provides exception classes for co-sign submission failures.
These errors represent issues when creating or validating co-signatures.

Constitutional Constraints:
- FR-6.1: Seeker SHALL be able to co-sign active petition
- FR-6.2: System SHALL enforce unique constraint (petition_id, signer_id)
- FR-6.3: System SHALL reject co-sign after fate assignment
- NFR-3.5: 0 duplicate signatures ever exist
- CT-11: Silent failure destroys legitimacy -> All errors must be logged
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError


class CoSignError(ConstitutionalViolationError):
    """Base error for co-sign related operations.

    Constitutional Constraint:
    All co-sign errors inherit from ConstitutionalViolationError and
    represent failures in the co-sign submission system.

    All subclasses include FR-6.x reference for traceability.
    """

    pass


class AlreadySignedError(CoSignError):
    """Raised when a signer tries to co-sign the same petition twice (FR-6.2, NFR-3.5).

    Constitutional Constraint (FR-6.2, NFR-3.5):
    System SHALL enforce unique constraint (petition_id, signer_id).
    0 duplicate signatures ever exist - this is a hard invariant.

    HTTP Status: 409 Conflict

    Story 5.7 Enhancement: Includes existing signature details for better error UX.

    Attributes:
        petition_id: The petition that was already signed.
        signer_id: The signer UUID attempting duplicate signature.
        existing_cosign_id: UUID of the existing co-signature (if available).
        signed_at: When the existing signature was recorded (if available).
    """

    def __init__(
        self,
        petition_id: UUID,
        signer_id: UUID,
        existing_cosign_id: UUID | None = None,
        signed_at: datetime | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            petition_id: The petition that was already signed.
            signer_id: The signer UUID attempting duplicate signature.
            existing_cosign_id: UUID of the existing co-signature (if available).
            signed_at: When the existing signature was recorded (if available).
        """
        self.petition_id = petition_id
        self.signer_id = signer_id
        self.existing_cosign_id = existing_cosign_id
        self.signed_at = signed_at
        super().__init__(
            f"FR-6.2/NFR-3.5: Signer {signer_id} already co-signed "
            f"petition {petition_id}"
        )

    def to_rfc7807_dict(self) -> dict:
        """Serialize to RFC 7807 + governance extensions format (D7).

        Returns:
            Dictionary conforming to RFC 7807 problem details with governance extensions.
        """
        result: dict = {
            "type": "urn:archon72:co-sign:already-signed",
            "title": "Already Signed",
            "status": 409,
            "detail": f"Signer {self.signer_id} has already co-signed petition {self.petition_id}",
            "petition_id": str(self.petition_id),
            "signer_id": str(self.signer_id),
        }

        # Include existing signature details if available (Story 5.7)
        if self.existing_cosign_id is not None:
            result["existing_cosign_id"] = str(self.existing_cosign_id)

        if self.signed_at is not None:
            result["signed_at"] = self.signed_at.isoformat()

        return result


class CoSignPetitionNotFoundError(CoSignError):
    """Raised when attempting to co-sign a non-existent petition (FR-6.1).

    Constitutional Constraint (FR-6.1):
    Co-signing requires a valid, existing petition.
    This error indicates the petition_id does not exist.

    HTTP Status: 404 Not Found

    Attributes:
        petition_id: The petition ID that was not found.
    """

    def __init__(self, petition_id: UUID) -> None:
        """Initialize the error.

        Args:
            petition_id: The petition ID that was not found.
        """
        self.petition_id = petition_id
        super().__init__(f"FR-6.1: Petition not found: {petition_id}")


class CoSignPetitionFatedError(CoSignError):
    """Raised when attempting to co-sign a petition in terminal state (FR-6.3).

    Constitutional Constraint (FR-6.3):
    System SHALL reject co-sign after fate assignment.
    Once a petition has been assigned a fate (ACKNOWLEDGED, REFERRED, or
    ESCALATED), no co-signatures are permitted.

    HTTP Status: 400 Bad Request

    Attributes:
        petition_id: UUID of the petition.
        terminal_state: The terminal fate state the petition is in.
    """

    def __init__(
        self,
        petition_id: UUID,
        terminal_state: str,
    ) -> None:
        """Initialize petition already fated error.

        Args:
            petition_id: UUID of the petition.
            terminal_state: The terminal state name (ACKNOWLEDGED/REFERRED/ESCALATED).
        """
        self.petition_id = petition_id
        self.terminal_state = terminal_state
        super().__init__(
            f"FR-6.3: Petition {petition_id} already has fate: {terminal_state}. "
            "Co-signing is not permitted after fate assignment."
        )
