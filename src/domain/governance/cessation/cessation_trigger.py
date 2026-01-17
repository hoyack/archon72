"""Cessation trigger domain model for system lifecycle management.

Story: consent-gov-8.1: System Cessation Trigger

This module defines the CessationTrigger - the immutable record of when,
why, and by whom cessation was triggered.

Key Design:
- Immutable (frozen dataclass)
- Requires operator_id (Human Operator authentication)
- Requires reason (documentation is mandatory)
- No cancelled_at field (irreversible)
- No revoked_by field (irreversible)

Constitutional Context:
- FR47: Human Operator can trigger cessation
- AC4: Cessation requires Human Operator authentication
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CessationTrigger:
    """Record of cessation trigger.

    Created when Human Operator initiates cessation.
    Immutable - cannot be cancelled or reversed.

    Attributes:
        trigger_id: Unique identifier for this trigger event.
        operator_id: The Human Operator who triggered cessation.
        triggered_at: Timestamp when cessation was triggered.
        reason: Required documentation of why cessation was triggered.

    Note: There is intentionally NO cancelled_at, revoked_by, or similar
    field. Cessation is irreversible by design.

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> trigger = CessationTrigger(
        ...     trigger_id=uuid4(),
        ...     operator_id=uuid4(),
        ...     triggered_at=datetime.now(timezone.utc),
        ...     reason="Planned system retirement",
        ... )
        >>> assert trigger.reason == "Planned system retirement"
    """

    trigger_id: UUID
    """Unique identifier for this trigger event."""

    operator_id: UUID
    """The Human Operator who triggered cessation.

    This MUST be a Human Operator - system cannot trigger cessation.
    Required for authentication and audit purposes (AC4, FR47).
    """

    triggered_at: datetime
    """Timestamp when cessation was triggered.

    Set by TimeAuthority for consistency.
    """

    reason: str
    """Required documentation of why cessation was triggered.

    This field is mandatory - operators must document their reasoning.
    Examples:
    - "Planned system retirement"
    - "Constitutional crisis - quorum permanently lost"
    - "End of operational mandate"
    """

    def __post_init__(self) -> None:
        """Validate trigger fields."""
        if not self.reason or not self.reason.strip():
            raise ValueError("Cessation reason is required and cannot be empty")

    def to_dict(self) -> dict:
        """Serialize to dictionary for event payload.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "trigger_id": str(self.trigger_id),
            "operator_id": str(self.operator_id),
            "triggered_at": self.triggered_at.isoformat(),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CessationTrigger":
        """Deserialize from dictionary.

        Args:
            data: Dictionary from to_dict() or event payload.

        Returns:
            Reconstructed CessationTrigger.
        """
        return cls(
            trigger_id=UUID(data["trigger_id"]),
            operator_id=UUID(data["operator_id"]),
            triggered_at=datetime.fromisoformat(data["triggered_at"]),
            reason=data["reason"],
        )
