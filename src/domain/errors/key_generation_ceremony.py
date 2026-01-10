"""Key generation ceremony errors (FR69, ADR-4).

This module provides exception classes for key generation ceremony failures.
These are constitutional violations that enforce witnessed ceremony requirements.

Constitutional Truths Honored:
- FR69: Keeper keys SHALL be generated through witnessed ceremony
- CT-11: Silent failure destroys legitimacy -> FAIL LOUD
- CT-12: Witnessing creates accountability
- VAL-2: Ceremony timeout enforcement
- CM-5: Ceremony mutex / conflict detection
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class CeremonyError(ConstitutionalViolationError):
    """Base class for key generation ceremony errors (FR69).

    Constitutional Constraint:
    All ceremony errors indicate constitutional violations and MUST
    be handled explicitly - never silently ignored.
    """

    pass


class CeremonyNotFoundError(CeremonyError):
    """Raised when ceremony ID is not found.

    Constitutional Constraint (FR69):
    Ceremony operations require valid ceremony records.
    Missing ceremonies MUST fail loudly.

    Usage:
        raise CeremonyNotFoundError(
            f"FR69: Ceremony not found: {ceremony_id}"
        )
    """

    pass


class InvalidCeremonyStateError(CeremonyError):
    """Raised when ceremony state transition is invalid (FP-4).

    Constitutional Constraint (FP-4):
    Ceremony state transitions must follow the valid transition map.
    Invalid transitions MUST be rejected immediately.

    Usage:
        raise InvalidCeremonyStateError(
            f"FP-4: Invalid state transition {current} -> {target}"
        )
    """

    pass


class InsufficientWitnessesError(CeremonyError):
    """Raised when ceremony has fewer than required witnesses (CT-12).

    Constitutional Constraint (CT-12):
    Witnessing creates accountability. Key generation ceremonies
    require at least 3 witnesses.

    Usage:
        raise InsufficientWitnessesError(
            f"CT-12: Ceremony requires 3 witnesses, got {count}"
        )
    """

    pass


class CeremonyTimeoutError(CeremonyError):
    """Raised when ceremony exceeds time limit (VAL-2).

    Constitutional Constraint (VAL-2):
    Ceremonies MUST have timeout enforcement to prevent
    indefinite pending states.

    Usage:
        raise CeremonyTimeoutError(
            f"VAL-2: Ceremony timeout after {elapsed}s"
        )
    """

    pass


class CeremonyConflictError(CeremonyError):
    """Raised when conflicting ceremony is in progress (CM-5).

    Constitutional Constraint (CM-5):
    Only one key generation ceremony can be active at a time
    for a given Keeper to prevent conflicts.

    Usage:
        raise CeremonyConflictError(
            f"CM-5: Conflicting ceremony already active: {active_id}"
        )
    """

    pass


class DuplicateWitnessError(CeremonyError):
    """Raised when witness has already signed the ceremony.

    Constitutional Constraint (CT-12):
    Each witness can only attest once per ceremony to ensure
    proper quorum counting.

    Usage:
        raise DuplicateWitnessError(
            f"CT-12: Witness {witness_id} has already signed"
        )
    """

    pass


class InvalidWitnessSignatureError(CeremonyError):
    """Raised when a witness signature fails cryptographic verification.

    Constitutional Constraint (CT-12):
    Witnessing creates accountability. Invalid signatures MUST be
    rejected to prevent attestation fraud.

    Usage:
        raise InvalidWitnessSignatureError(
            f"CT-12: Invalid signature from witness {witness_id}"
        )
    """

    pass
