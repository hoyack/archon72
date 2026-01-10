"""Petition domain errors (Story 7.2, FR39).

This module provides exception classes for petition-related failures.
These errors represent issues when creating, co-signing, or querying petitions.

Constitutional Constraints:
- FR39: External observers can petition with 100+ co-signers
- CT-11: Silent failure destroys legitimacy -> All errors must be logged
- AC2: Duplicate co-signatures from same public key are rejected
- AC4: Invalid signatures must be rejected at submission time
"""

from __future__ import annotations

from src.domain.errors.constitutional import ConstitutionalViolationError


class PetitionError(ConstitutionalViolationError):
    """Base error for petition-related operations.

    Constitutional Constraint:
    All petition errors inherit from ConstitutionalViolationError and
    represent failures in the petition system.

    All subclasses include FR39 reference for traceability.
    """

    pass


class InvalidSignatureError(PetitionError):
    """Raised when signature verification fails (FR39, AC4).

    Constitutional Constraint (AC4):
    Invalid signatures must be rejected at submission time.
    All signatures use Ed25519 algorithm.

    Attributes:
        public_key: The public key that failed verification.
        message: Detailed error message.
    """

    def __init__(self, public_key: str, message: str = "Signature verification failed") -> None:
        """Initialize the error.

        Args:
            public_key: The public key that failed verification.
            message: Detailed error message.
        """
        self.public_key = public_key
        super().__init__(f"FR39/AC4: {message} for public_key={public_key[:16]}...")


class DuplicateCosignatureError(PetitionError):
    """Raised when a public key tries to co-sign twice (FR39, AC2).

    Constitutional Constraint (AC2):
    Duplicate co-signatures from same public key are rejected.
    A key can only sign a petition once (as submitter or co-signer).

    Attributes:
        petition_id: The petition that was already signed.
        public_key: The public key attempting duplicate signature.
    """

    def __init__(self, petition_id: str, public_key: str) -> None:
        """Initialize the error.

        Args:
            petition_id: The petition that was already signed.
            public_key: The public key attempting duplicate signature.
        """
        self.petition_id = petition_id
        self.public_key = public_key
        super().__init__(
            f"FR39/AC2: Public key {public_key[:16]}... already signed "
            f"petition {petition_id}"
        )


class PetitionNotFoundError(PetitionError):
    """Raised when a petition cannot be found (FR39).

    Constitutional Constraint (FR39):
    Petition queries must return accurate results.
    This error indicates a requested petition does not exist.

    Attributes:
        petition_id: The petition ID that was not found.
    """

    def __init__(self, petition_id: str) -> None:
        """Initialize the error.

        Args:
            petition_id: The petition ID that was not found.
        """
        self.petition_id = petition_id
        super().__init__(f"FR39: Petition not found: {petition_id}")


class PetitionClosedError(PetitionError):
    """Raised when trying to co-sign a closed petition (FR39).

    Constitutional Constraint (FR39):
    Petitions have lifecycle states. Once a petition is closed
    or has reached threshold, it may no longer accept co-signatures
    (depending on configuration).

    Attributes:
        petition_id: The petition that is closed.
        status: The current status of the petition.
    """

    def __init__(self, petition_id: str, status: str) -> None:
        """Initialize the error.

        Args:
            petition_id: The petition that is closed.
            status: The current status of the petition.
        """
        self.petition_id = petition_id
        self.status = status
        super().__init__(
            f"FR39: Petition {petition_id} is not accepting co-signatures "
            f"(status={status})"
        )


class PetitionAlreadyExistsError(PetitionError):
    """Raised when trying to create a petition with existing ID (FR39).

    Constitutional Constraint (FR39):
    Each petition must have a unique identifier.

    Attributes:
        petition_id: The petition ID that already exists.
    """

    def __init__(self, petition_id: str) -> None:
        """Initialize the error.

        Args:
            petition_id: The petition ID that already exists.
        """
        self.petition_id = petition_id
        super().__init__(f"FR39: Petition already exists: {petition_id}")
