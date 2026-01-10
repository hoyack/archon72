"""Ceased Status Header value object (Story 7.4, FR41).

This module provides the CeasedStatusHeader value object that is included
in all read responses to indicate the system has permanently ceased.

Constitutional Constraints:
- FR41: Freeze on new actions except record preservation
- CT-11: Silent failure destroys legitimacy → Status is ALWAYS visible
- AC6: Results include `system_status: CEASED` header after cessation

The status header provides transparency to external observers,
allowing them to know they are reading from a permanently ceased system.

Key Differences from HaltStatusHeader:
- HaltStatusHeader indicates temporary halt (can be cleared)
- CeasedStatusHeader indicates permanent cessation (irreversible, NFR40)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    pass


# Status constant for consistency
SYSTEM_STATUS_CEASED: str = "CEASED"


@dataclass(frozen=True)
class CessationDetails:
    """Details about a cessation event (FR41).

    Contains all information needed to understand when and why
    the system was permanently ceased.

    Attributes:
        ceased_at: When the cessation occurred (UTC).
        final_sequence_number: The last valid sequence number in the event store.
        reason: Human-readable reason for cessation.
        cessation_event_id: UUID of the CESSATION_EXECUTED event.
    """

    ceased_at: datetime
    final_sequence_number: int
    reason: str
    cessation_event_id: UUID


@dataclass(frozen=True)
class CeasedStatusHeader:
    """System status header for all read responses after cessation (FR41, AC6).

    Per FR41, all read responses after cessation must include system status.
    This provides transparency to external observers that the system has
    permanently ceased operations.

    Unlike HaltStatusHeader (temporary), this indicates permanent cessation
    per NFR40 (schema irreversibility).

    Attributes:
        system_status: Always "CEASED" for this header type.
        ceased_at: Timestamp when cessation occurred (UTC).
        final_sequence_number: The last valid sequence number (cessation event).
        cessation_reason: Human-readable reason for cessation.

    Example:
        >>> header = CeasedStatusHeader.ceased(
        ...     ceased_at=datetime(2024, 6, 15, tzinfo=timezone.utc),
        ...     final_sequence_number=12345,
        ...     reason="Unanimous vote for cessation"
        ... )
        >>> header.system_status
        'CEASED'
        >>> header.is_permanent
        True
    """

    system_status: str
    ceased_at: datetime
    final_sequence_number: int
    cessation_reason: str

    @classmethod
    def ceased(
        cls,
        *,
        final_sequence_number: int,
        reason: str,
        ceased_at: datetime | None = None,
    ) -> CeasedStatusHeader:
        """Factory for creating a ceased status header.

        Use this when the system has permanently ceased operations.

        Args:
            final_sequence_number: The last valid sequence number.
            reason: Human-readable reason for cessation.
            ceased_at: When cessation occurred. Defaults to now if not provided.

        Returns:
            CeasedStatusHeader indicating ceased state.

        Example:
            >>> header = CeasedStatusHeader.ceased(
            ...     final_sequence_number=500,
            ...     reason="Integrity failure",
            ... )
            >>> header.system_status
            'CEASED'
        """
        return cls(
            system_status=SYSTEM_STATUS_CEASED,
            ceased_at=ceased_at or datetime.now(timezone.utc),
            final_sequence_number=final_sequence_number,
            cessation_reason=reason,
        )

    @classmethod
    def from_cessation_details(
        cls,
        details: CessationDetails,
    ) -> CeasedStatusHeader:
        """Factory method creating header from CessationDetails.

        Convenience method for creating header from a CessationDetails
        object returned by the freeze checker or flag repository.

        Args:
            details: CessationDetails containing all cessation information.

        Returns:
            CeasedStatusHeader with fields populated from details.

        Example:
            >>> details = CessationDetails(
            ...     ceased_at=datetime.now(timezone.utc),
            ...     final_sequence_number=999,
            ...     reason="Breach threshold exceeded",
            ...     cessation_event_id=uuid4()
            ... )
            >>> header = CeasedStatusHeader.from_cessation_details(details)
            >>> header.final_sequence_number
            999
        """
        return cls(
            system_status=SYSTEM_STATUS_CEASED,
            ceased_at=details.ceased_at,
            final_sequence_number=details.final_sequence_number,
            cessation_reason=details.reason,
        )

    @property
    def is_ceased(self) -> bool:
        """Check if this header indicates ceased state.

        Returns:
            Always True for CeasedStatusHeader (by definition).

        Example:
            >>> CeasedStatusHeader.ceased(
            ...     final_sequence_number=100, reason="test"
            ... ).is_ceased
            True
        """
        return self.system_status == SYSTEM_STATUS_CEASED

    @property
    def is_permanent(self) -> bool:
        """Check if this state is permanent (irreversible).

        Returns:
            Always True - cessation is permanent per NFR40.

        Example:
            >>> CeasedStatusHeader.ceased(
            ...     final_sequence_number=100, reason="test"
            ... ).is_permanent
            True
        """
        return True

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for API responses.

        Example:
            >>> header = CeasedStatusHeader.ceased(
            ...     final_sequence_number=100,
            ...     reason="Test",
            ...     ceased_at=datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
            ... )
            >>> header.to_dict()
            {'system_status': 'CEASED', 'ceased_at': '2024-06-15T12:30:00+00:00', ...}
        """
        return {
            "system_status": self.system_status,
            "ceased_at": self.ceased_at.isoformat(),
            "final_sequence_number": self.final_sequence_number,
            "cessation_reason": self.cessation_reason,
        }
