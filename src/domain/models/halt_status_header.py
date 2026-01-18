"""Halt Status Header value object (Story 3.5, FR20).

This module provides the HaltStatusHeader value object that is included
in all read responses to indicate the system's halt state.

Constitutional Constraints:
- FR20: Read responses during halt must include system status
- CT-11: Silent failure destroys legitimacy → Status is ALWAYS visible
- AC1: Results include `system_status: HALTED` header during halt

The status header provides transparency to external observers,
allowing them to know whether they're reading from a halted system.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

# Status constants for consistency
SYSTEM_STATUS_OPERATIONAL: str = "OPERATIONAL"
SYSTEM_STATUS_HALTED: str = "HALTED"


@dataclass(frozen=True)
class HaltStatusHeader:
    """System status header for all read responses (FR20, AC1).

    Per FR20, all read responses during halt must include system status.
    This provides transparency to external observers.

    Attributes:
        system_status: Either "HALTED" or "OPERATIONAL".
        halt_reason: Human-readable reason for halt (if halted).
        halted_at: Timestamp when halt was triggered (if halted).

    Example:
        >>> header = HaltStatusHeader.operational()
        >>> header.system_status
        'OPERATIONAL'

        >>> header = HaltStatusHeader.halted(
        ...     reason="FR17: Fork detected",
        ...     halted_at=datetime.now(timezone.utc)
        ... )
        >>> header.system_status
        'HALTED'
    """

    system_status: str
    halt_reason: str | None
    halted_at: datetime | None

    @classmethod
    def operational(cls) -> HaltStatusHeader:
        """Factory for normal operational status.

        Use this when the system is running normally without halt.

        Returns:
            HaltStatusHeader indicating operational state.

        Example:
            >>> header = HaltStatusHeader.operational()
            >>> header.system_status
            'OPERATIONAL'
            >>> header.halt_reason is None
            True
        """
        return cls(
            system_status=SYSTEM_STATUS_OPERATIONAL,
            halt_reason=None,
            halted_at=None,
        )

    @classmethod
    def halted(
        cls,
        reason: str,
        halted_at: datetime | None = None,
    ) -> HaltStatusHeader:
        """Factory for halted status.

        Use this when the system is halted due to integrity concerns.

        Args:
            reason: Human-readable reason for the halt.
            halted_at: When the halt was triggered. Defaults to now if not provided.

        Returns:
            HaltStatusHeader indicating halted state.

        Example:
            >>> from datetime import datetime, timezone
            >>> header = HaltStatusHeader.halted(
            ...     reason="FR17: Fork detected",
            ...     halted_at=datetime(2024, 1, 1, tzinfo=timezone.utc)
            ... )
            >>> header.system_status
            'HALTED'
            >>> header.halt_reason
            'FR17: Fork detected'
        """
        return cls(
            system_status=SYSTEM_STATUS_HALTED,
            halt_reason=reason,
            halted_at=halted_at or datetime.now(timezone.utc),
        )

    @classmethod
    def from_halt_state(
        cls,
        is_halted: bool,
        reason: str | None = None,
        halted_at: datetime | None = None,
    ) -> HaltStatusHeader:
        """Factory method creating header from halt state.

        Convenience method for creating appropriate header based on
        boolean halt state. Useful when integrating with HaltChecker.

        Args:
            is_halted: Whether the system is currently halted.
            reason: Halt reason (used only if is_halted=True).
            halted_at: When halt was triggered (used only if is_halted=True).

        Returns:
            HaltStatusHeader with appropriate status.

        Example:
            >>> header = HaltStatusHeader.from_halt_state(False)
            >>> header.system_status
            'OPERATIONAL'

            >>> header = HaltStatusHeader.from_halt_state(
            ...     True, reason="Fork detected"
            ... )
            >>> header.system_status
            'HALTED'
        """
        if is_halted:
            return cls.halted(
                reason=reason or "Unknown",
                halted_at=halted_at,
            )
        return cls.operational()

    @property
    def is_halted(self) -> bool:
        """Check if this header indicates halted state.

        Returns:
            True if system_status is HALTED, False otherwise.

        Example:
            >>> HaltStatusHeader.operational().is_halted
            False
            >>> HaltStatusHeader.halted("test").is_halted
            True
        """
        return self.system_status == SYSTEM_STATUS_HALTED

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for API responses.

        Example:
            >>> header = HaltStatusHeader.operational()
            >>> header.to_dict()
            {'system_status': 'OPERATIONAL', 'halt_reason': None, 'halted_at': None}
        """
        return {
            "system_status": self.system_status,
            "halt_reason": self.halt_reason,
            "halted_at": self.halted_at.isoformat() if self.halted_at else None,
        }
