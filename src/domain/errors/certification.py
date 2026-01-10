"""Certification domain errors (Story 2.8, FR99-FR101).

This module defines error classes for certification-related failures.
These errors are raised when certification operations fail, including
signature verification and hash mismatches.

Constitutional Constraints:
- FR99: Deliberation results SHALL have certified result events
- FR100: Certification SHALL include result_hash, participant_count, certification_timestamp
- FR101: Certification signature SHALL be verifiable
- CT-11: Silent failure destroys legitimacy -> Certification failures must be explicit
"""

from __future__ import annotations

from uuid import UUID

from src.domain.exceptions import ConclaveError


class CertificationError(ConclaveError):
    """Base exception for all certification-related errors.

    All certification-specific exceptions inherit from this class,
    enabling consistent error handling for certification operations.

    Example:
        >>> raise CertificationError("Certification operation failed")
        Traceback (most recent call last):
            ...
        CertificationError: Certification operation failed
    """

    pass


class CertificationSignatureError(CertificationError):
    """Error raised when certification signature verification fails.

    This error indicates that the certification signature could not be
    verified, either because the key ID doesn't match or the signature
    itself is invalid.

    Attributes:
        result_id: The UUID of the result that failed verification.
        expected_key_id: The key ID that was expected.
        actual_key_id: The key ID that was found (or None if missing).

    Constitutional Constraints:
        - FR101: Certification signature SHALL be verifiable
        - CT-11: Explicit failure when signature verification fails

    Example:
        >>> from uuid import uuid4
        >>> error = CertificationSignatureError(
        ...     result_id=uuid4(),
        ...     expected_key_id="CERT:key-001",
        ...     actual_key_id="CERT:key-002",
        ... )
    """

    def __init__(
        self,
        result_id: UUID,
        expected_key_id: str,
        actual_key_id: str | None,
    ) -> None:
        """Initialize CertificationSignatureError.

        Args:
            result_id: The UUID of the result that failed verification.
            expected_key_id: The key ID that was expected.
            actual_key_id: The key ID that was found (or None if missing).
        """
        self.result_id = result_id
        self.expected_key_id = expected_key_id
        self.actual_key_id = actual_key_id

        actual_key_display = actual_key_id if actual_key_id else "no key found"
        message = (
            f"FR101: Certification signature verification failed for result {result_id}. "
            f"Expected key: {expected_key_id}, actual: {actual_key_display}"
        )
        super().__init__(message)


class ResultHashMismatchError(CertificationError):
    """Error raised when result content hash doesn't match stored hash.

    This error indicates tampering or corruption - the content of a
    certified result no longer matches its recorded hash.

    Attributes:
        result_id: The UUID of the result with hash mismatch.
        stored_hash: The hash that was stored during certification.
        computed_hash: The hash computed from current content.

    Constitutional Constraints:
        - FR99: Result must match its certified hash
        - CT-11: Explicit failure when hash verification fails
        - CT-13: Integrity outranks availability

    Example:
        >>> from uuid import uuid4
        >>> error = ResultHashMismatchError(
        ...     result_id=uuid4(),
        ...     stored_hash="a" * 64,
        ...     computed_hash="b" * 64,
        ... )
    """

    def __init__(
        self,
        result_id: UUID,
        stored_hash: str,
        computed_hash: str,
    ) -> None:
        """Initialize ResultHashMismatchError.

        Args:
            result_id: The UUID of the result with hash mismatch.
            stored_hash: The hash that was stored during certification.
            computed_hash: The hash computed from current content.
        """
        self.result_id = result_id
        self.stored_hash = stored_hash
        self.computed_hash = computed_hash

        message = (
            f"FR99: Result hash mismatch for result {result_id}. "
            f"Stored hash: {stored_hash[:16]}..., "
            f"computed hash: {computed_hash[:16]}... - possible tampering detected"
        )
        super().__init__(message)
