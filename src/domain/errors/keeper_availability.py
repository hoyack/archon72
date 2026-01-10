"""Keeper availability errors for Archon 72 (FR77-FR79).

This module provides exception classes for Keeper availability-related
failures. All errors inherit from ConclaveError and include FR references.

Constitutional Constraints:
- FR78: Keepers SHALL attest availability weekly
- FR79: If registered Keeper count falls below 3, system SHALL halt
- CT-11: Silent failure destroys legitimacy -> Errors MUST be explicit

Error Types:
- KeeperAvailabilityError: Base class for all availability errors
- KeeperAttestationExpiredError: Attestation period has passed
- DuplicateAttestationError: Already attested for this period
- KeeperQuorumViolationError: FR79 - Quorum below minimum (3)
- KeeperReplacementRequiredError: FR78 - 2 missed attestations
- InvalidAttestationSignatureError: Signature verification failed
"""

from src.domain.exceptions import ConclaveError


class KeeperAvailabilityError(ConclaveError):
    """Base exception for Keeper availability errors.

    All Keeper availability-specific exceptions inherit from this class.
    This enables consistent error handling for availability operations.

    Constitutional Constraints:
    - FR78: Weekly attestation requirement
    - FR79: Minimum Keeper quorum (3)
    - CT-11: Silent failure destroys legitimacy
    """

    pass


class KeeperAttestationExpiredError(KeeperAvailabilityError):
    """Raised when attestation submission is after period deadline.

    Constitutional Constraint (FR78):
    Keepers SHALL attest availability weekly. Attestations submitted
    after the period deadline are rejected.

    Usage:
        raise KeeperAttestationExpiredError(
            "FR78: Attestation period ended at 2025-01-06T00:00:00Z"
        )
    """

    pass


class DuplicateAttestationError(KeeperAvailabilityError):
    """Raised when Keeper has already attested for current period.

    A Keeper can only submit one attestation per weekly period.
    Duplicate submissions are rejected.

    Usage:
        raise DuplicateAttestationError(
            "FR78: Keeper KEEPER:alice already attested for period "
            "2025-01-06 to 2025-01-13"
        )
    """

    pass


class KeeperQuorumViolationError(KeeperAvailabilityError):
    """Raised when Keeper count falls below minimum (3).

    Constitutional Constraint (FR79):
    If registered Keeper count falls below 3, system SHALL halt
    until complement restored.

    This error triggers a system halt (CT-11).

    Usage:
        raise KeeperQuorumViolationError(
            "FR79: Keeper quorum below minimum - only 2 active Keepers"
        )
    """

    pass


class KeeperReplacementRequiredError(KeeperAvailabilityError):
    """Raised when Keeper has missed 2 consecutive attestations.

    Constitutional Constraint (FR78):
    2 missed attestations trigger replacement process.
    This error indicates the Keeper should be replaced.

    Usage:
        raise KeeperReplacementRequiredError(
            "FR78: Keeper KEEPER:bob missed 2 consecutive attestations - "
            "replacement required"
        )
    """

    pass


class InvalidAttestationSignatureError(KeeperAvailabilityError):
    """Raised when attestation signature verification fails.

    All attestations must be cryptographically signed by the Keeper's
    registered key. Invalid signatures indicate tampering or
    unauthorized access.

    Constitutional Constraints:
    - CT-6: Cryptography depends on key custody
    - CT-12: Witnessing creates accountability

    Usage:
        raise InvalidAttestationSignatureError(
            "FR78: Attestation signature verification failed for KEEPER:alice"
        )
    """

    pass
