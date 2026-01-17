"""Halt status domain model for emergency safety circuit.

This module defines the core value objects for the halt circuit:
- HaltReason: Why the system was halted
- HaltStatus: Current halt state with full context
- HaltedException: Raised when operations attempted during halt

Constitutional Context:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-13: Integrity outranks availability → Halt preserves integrity
- Foundation 2: Halt correctness > observability > durability

Story: consent-gov-4.1 (Halt Circuit Port & Adapter)
Requirements: FR22-FR27, NFR-PERF-01, NFR-REL-01
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class HaltReason(Enum):
    """Reason for system halt.

    Each reason indicates why the system was halted, enabling
    appropriate response procedures and audit trails.
    """

    OPERATOR = "operator"
    """Human operator triggered halt (e.g., maintenance, emergency)."""

    SYSTEM_FAULT = "system_fault"
    """Detected system fault requiring halt (e.g., resource exhaustion)."""

    INTEGRITY_VIOLATION = "integrity_violation"
    """Integrity violation detected (e.g., hash chain break, fork detection)."""

    CONSENSUS_FAILURE = "consensus_failure"
    """Consensus failure requiring halt (e.g., quorum loss)."""

    CONSTITUTIONAL_BREACH = "constitutional_breach"
    """Constitutional breach detected (e.g., CT violation)."""


@dataclass(frozen=True)
class HaltStatus:
    """Current halt status with full context.

    Immutable value object representing the system's halt state.
    Used throughout the system to check and communicate halt status.

    Attributes:
        is_halted: Whether the system is currently halted.
        halted_at: When the halt was triggered (None if not halted).
        reason: Why the system was halted (None if not halted).
        operator_id: ID of operator who triggered halt (None if system-triggered).
        message: Human-readable description of the halt.
        trace_id: Trace ID for audit correlation.

    Examples:
        >>> status = HaltStatus.not_halted()
        >>> assert not status.is_halted

        >>> status = HaltStatus.halted(
        ...     reason=HaltReason.OPERATOR,
        ...     operator_id=UUID("..."),
        ...     message="Maintenance window",
        ...     halted_at=datetime.now(timezone.utc),
        ...     trace_id="abc-123",
        ... )
        >>> assert status.is_halted
    """

    is_halted: bool
    halted_at: Optional[datetime]
    reason: Optional[HaltReason]
    operator_id: Optional[UUID]
    message: Optional[str]
    trace_id: Optional[str] = None

    @classmethod
    def not_halted(cls) -> "HaltStatus":
        """Create a status indicating system is not halted.

        Returns:
            HaltStatus with is_halted=False and all fields None.
        """
        return cls(
            is_halted=False,
            halted_at=None,
            reason=None,
            operator_id=None,
            message=None,
            trace_id=None,
        )

    @classmethod
    def halted(
        cls,
        reason: HaltReason,
        message: str,
        halted_at: datetime,
        operator_id: Optional[UUID] = None,
        trace_id: Optional[str] = None,
    ) -> "HaltStatus":
        """Create a status indicating system is halted.

        Args:
            reason: Why the system was halted.
            message: Human-readable description.
            halted_at: When the halt was triggered.
            operator_id: ID of operator who triggered halt (None if system).
            trace_id: Trace ID for audit correlation.

        Returns:
            HaltStatus with is_halted=True and full context.
        """
        return cls(
            is_halted=True,
            halted_at=halted_at,
            reason=reason,
            operator_id=operator_id,
            message=message,
            trace_id=trace_id,
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary for Redis/JSON transport.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "is_halted": self.is_halted,
            "halted_at": self.halted_at.isoformat() if self.halted_at else None,
            "reason": self.reason.value if self.reason else None,
            "operator_id": str(self.operator_id) if self.operator_id else None,
            "message": self.message,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HaltStatus":
        """Deserialize from dictionary (Redis/JSON transport).

        Args:
            data: Dictionary from to_dict() or JSON.

        Returns:
            Reconstructed HaltStatus.
        """
        if not data.get("is_halted"):
            return cls.not_halted()

        return cls(
            is_halted=True,
            halted_at=datetime.fromisoformat(data["halted_at"])
            if data.get("halted_at")
            else None,
            reason=HaltReason(data["reason"]) if data.get("reason") else None,
            operator_id=UUID(data["operator_id"]) if data.get("operator_id") else None,
            message=data.get("message"),
            trace_id=data.get("trace_id"),
        )


class HaltedException(Exception):
    """Raised when operation attempted during system halt.

    This exception is raised by HaltChecker when an operation
    is attempted while the system is halted. Services should
    NOT catch and suppress this exception.

    Attributes:
        status: The current HaltStatus with full context.

    Constitutional Context:
        CT-11: Silent failure destroys legitimacy
        Suppressing HaltedException violates CT-11.
    """

    def __init__(self, status: HaltStatus) -> None:
        """Initialize HaltedException with halt status.

        Args:
            status: Current halt status with full context.
        """
        self.status = status
        reason = status.reason.value if status.reason else "unknown"
        message = status.message or "No message provided"
        super().__init__(f"System halted ({reason}): {message}")

    def __repr__(self) -> str:
        """Return detailed representation for debugging."""
        return (
            f"HaltedException(reason={self.status.reason}, "
            f"halted_at={self.status.halted_at}, "
            f"message={self.status.message!r})"
        )
