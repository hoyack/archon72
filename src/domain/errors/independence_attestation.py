"""Independence attestation error classes (FR98, FR133).

This module defines domain errors for annual Keeper independence attestation:
- IndependenceAttestationError: Base class for attestation errors
- AttestationDeadlineMissedError: When deadline passes, capabilities suspended
- DuplicateIndependenceAttestationError: Already attested for year
- InvalidIndependenceSignatureError: Signature verification failed
- CapabilitySuspendedError: Override attempted while suspended

Constitutional Constraints:
- FR133: Keepers SHALL annually attest independence
- CT-11: Silent failure destroys legitimacy -> Fail loud with clear messages
"""

from __future__ import annotations


class IndependenceAttestationError(Exception):
    """Base error for independence attestation operations (FR133).

    All independence attestation errors inherit from this class.
    """


class AttestationDeadlineMissedError(IndependenceAttestationError):
    """Attestation deadline passed, capabilities suspended (FR133).

    Raised when a Keeper's independence attestation deadline has passed
    and their override capability is suspended until attestation.
    """

    def __init__(self, keeper_id: str, deadline: str) -> None:
        """Initialize error with Keeper ID and missed deadline.

        Args:
            keeper_id: ID of the Keeper who missed the deadline.
            deadline: The deadline that was missed (ISO format string).
        """
        self.keeper_id = keeper_id
        self.deadline = deadline
        super().__init__(
            f"FR133: Independence attestation deadline missed - "
            f"Keeper {keeper_id} deadline was {deadline}, capabilities suspended"
        )


class DuplicateIndependenceAttestationError(IndependenceAttestationError):
    """Already attested for this year (FR133).

    Raised when a Keeper attempts to submit an independence attestation
    for a year they have already attested for.
    """

    def __init__(self, keeper_id: str, year: int) -> None:
        """Initialize error with Keeper ID and year.

        Args:
            keeper_id: ID of the Keeper who already attested.
            year: The year that already has an attestation.
        """
        self.keeper_id = keeper_id
        self.year = year
        super().__init__(
            f"FR133: Duplicate independence attestation - "
            f"Keeper {keeper_id} already attested for year {year}"
        )


class InvalidIndependenceSignatureError(IndependenceAttestationError):
    """Signature verification failed (FR133, NFR22).

    Raised when an independence attestation has an invalid cryptographic
    signature. All Keeper actions must be signed (NFR22).
    """

    def __init__(self, keeper_id: str, reason: str = "verification failed") -> None:
        """Initialize error with Keeper ID and reason.

        Args:
            keeper_id: ID of the Keeper whose signature failed.
            reason: Additional context about the failure.
        """
        self.keeper_id = keeper_id
        self.reason = reason
        super().__init__(
            f"FR133: Invalid independence attestation signature - "
            f"Keeper {keeper_id} signature {reason}"
        )


class CapabilitySuspendedError(IndependenceAttestationError):
    """Override capability is suspended until attestation (FR133).

    Raised when a Keeper attempts to perform an override while their
    independence attestation is overdue and capability is suspended.
    """

    def __init__(self, keeper_id: str, capability: str = "override") -> None:
        """Initialize error with Keeper ID and suspended capability.

        Args:
            keeper_id: ID of the Keeper whose capability is suspended.
            capability: The capability that is suspended (default: "override").
        """
        self.keeper_id = keeper_id
        self.capability = capability
        super().__init__(
            f"FR133: Capability suspended - "
            f"Keeper {keeper_id} {capability} capability suspended until "
            f"independence attestation submitted"
        )
