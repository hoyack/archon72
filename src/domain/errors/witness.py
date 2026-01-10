"""Witness-specific domain errors (FR4, FR5).

This module defines exception classes for witness-related failures.

Constitutional Constraints:
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist
- CT-12: Witnessing creates accountability
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class NoWitnessAvailableError(ConstitutionalViolationError):
    """Raised when no witnesses are available for attestation.

    Constitutional Constraint (RT-1):
    No witnesses available = write blocked, not degraded.

    This error MUST cause the event write to be rejected entirely.
    No unwitnessed events are allowed (FR5).
    """

    def __init__(self) -> None:
        """Initialize with standard RT-1 message."""
        super().__init__("RT-1: No witnesses available - write blocked")


class WitnessSigningError(ConstitutionalViolationError):
    """Raised when witness signing fails.

    Constitutional Constraint (FR4):
    Events must have atomic witness attribution.

    If witness signing fails, the entire event write must be rolled back.
    """

    def __init__(self, witness_id: str, reason: str) -> None:
        """Initialize with witness ID and failure reason.

        Args:
            witness_id: The ID of the witness that failed to sign.
            reason: Description of why signing failed.
        """
        super().__init__(f"FR4: Witness signing failed for {witness_id}: {reason}")
        self.witness_id = witness_id
        self.reason = reason


class WitnessNotFoundError(ConstitutionalViolationError):
    """Raised when a witness cannot be found by ID.

    Used during signature verification when looking up witness public key.
    """

    def __init__(self, witness_id: str) -> None:
        """Initialize with the witness ID that was not found.

        Args:
            witness_id: The ID of the witness that could not be found.
        """
        super().__init__(f"FR4: Witness not found: {witness_id}")
        self.witness_id = witness_id
