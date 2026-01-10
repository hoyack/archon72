"""System ceased errors for Archon 72 (Story 7.4, FR41).

This module provides exception classes for write rejections after system
cessation. These errors indicate that write operations were attempted
after the system has permanently ceased.

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → Errors include FR41 reference
- CT-13: Integrity outranks availability → Writes blocked after cessation
- FR41: Freeze on new actions except record preservation

Key Differences from Read-Only Errors (Story 3.5):
- Read-only errors are for temporary halt (can be cleared)
- Ceased errors are for permanent cessation (irreversible, NFR40)

Usage:
    raise SystemCeasedError.from_details_values(
        ceased_at=datetime.now(timezone.utc),
        final_sequence_number=12345,
        reason="Unanimous vote for cessation",
    )
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from src.domain.errors.constitutional import ConstitutionalViolationError

if TYPE_CHECKING:
    from src.domain.models.ceased_status_header import CessationDetails


class SystemCeasedError(ConstitutionalViolationError):
    """Raised when write attempted after system cessation (FR41).

    This error is PERMANENT. Do NOT retry - the system has ceased.
    There is no recovery mechanism per NFR40 (schema irreversibility).

    The error message must include "FR41: System ceased - writes frozen"
    per acceptance criteria AC2 and AC3.

    Attributes:
        ceased_at: When the system was ceased (if known).
        final_sequence_number: The last valid sequence number (if known).

    Usage:
        raise SystemCeasedError.from_details_values(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=12345,
            reason="Unanimous vote",
        )
    """

    def __init__(
        self,
        message: str = "FR41: System ceased - writes frozen",
        *,
        ceased_at: datetime | None = None,
        final_sequence_number: int | None = None,
    ) -> None:
        """Initialize SystemCeasedError.

        Args:
            message: Error message (should include FR41 reference).
            ceased_at: When cessation occurred.
            final_sequence_number: Last valid sequence number.
        """
        super().__init__(message)
        self.ceased_at = ceased_at
        self.final_sequence_number = final_sequence_number

    @classmethod
    def from_details(cls, details: CessationDetails) -> SystemCeasedError:
        """Create error from CessationDetails object.

        Args:
            details: CessationDetails containing cessation information.

        Returns:
            SystemCeasedError with all details populated.
        """
        return cls.from_details_values(
            ceased_at=details.ceased_at,
            final_sequence_number=details.final_sequence_number,
            reason=details.reason,
        )

    @classmethod
    def from_details_values(
        cls,
        *,
        ceased_at: datetime,
        final_sequence_number: int,
        reason: str,
    ) -> SystemCeasedError:
        """Create error with all cessation details.

        This is the preferred factory method for creating SystemCeasedError
        with full context for debugging and logging.

        Args:
            ceased_at: When cessation occurred.
            final_sequence_number: Last valid sequence number.
            reason: Reason for cessation.

        Returns:
            SystemCeasedError with detailed message.
        """
        message = (
            f"FR41: System ceased - writes frozen. "
            f"Ceased at {ceased_at.isoformat()} "
            f"(final sequence: {final_sequence_number}). "
            f"Reason: {reason}"
        )
        return cls(
            message=message,
            ceased_at=ceased_at,
            final_sequence_number=final_sequence_number,
        )


class CeasedWriteAttemptError(SystemCeasedError):
    """Raised when a specific write operation is attempted after cessation.

    This error provides additional context about which operation was
    attempted, useful for debugging and logging.

    Attributes:
        operation: The operation that was attempted.
        ceased_at: When the system was ceased.
        final_sequence_number: The last valid sequence number.

    Usage:
        raise CeasedWriteAttemptError.for_operation(
            operation="write_event",
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=12345,
        )
    """

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        ceased_at: datetime | None = None,
        final_sequence_number: int | None = None,
    ) -> None:
        """Initialize CeasedWriteAttemptError.

        Args:
            message: Error message (should include FR41 reference).
            operation: The operation that was attempted.
            ceased_at: When cessation occurred.
            final_sequence_number: Last valid sequence number.
        """
        super().__init__(
            message,
            ceased_at=ceased_at,
            final_sequence_number=final_sequence_number,
        )
        self.operation = operation

    @classmethod
    def for_operation(
        cls,
        *,
        operation: str,
        ceased_at: datetime,
        final_sequence_number: int,
    ) -> CeasedWriteAttemptError:
        """Create error for a specific write operation attempt.

        Args:
            operation: Name of the operation that was attempted.
            ceased_at: When cessation occurred.
            final_sequence_number: Last valid sequence number.

        Returns:
            CeasedWriteAttemptError with operation context.
        """
        message = (
            f"FR41: System ceased - writes frozen. "
            f"Operation '{operation}' rejected. "
            f"Ceased at {ceased_at.isoformat()} "
            f"(final sequence: {final_sequence_number})"
        )
        return cls(
            message=message,
            operation=operation,
            ceased_at=ceased_at,
            final_sequence_number=final_sequence_number,
        )
