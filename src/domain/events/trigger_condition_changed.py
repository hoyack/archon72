"""Trigger condition changed event payload (Story 7.7, FR134 AC4).

This module defines the event payload for trigger condition changes.
When a cessation trigger threshold is modified through constitutional
process, this event is created to record the change.

Constitutional Constraints:
- FR134: Public documentation of cessation trigger conditions
- CT-12: Witnessing creates accountability -> All changes must be witnessed
- FR33: Threshold definitions SHALL be constitutional, not operational
- CT-11: Silent failure destroys legitimacy -> Changes must be logged

Developer Golden Rules:
1. WITNESS CHANGES - Every threshold change MUST be witnessed
2. NO HARDCODED VALUES - Thresholds come from constitutional registry
3. IMMUTABLE RECORD - Once created, event cannot be modified
4. FAIL LOUD - Invalid changes must raise, not silently fail

Usage:
    from src.domain.events.trigger_condition_changed import (
        TRIGGER_CONDITION_CHANGED_EVENT_TYPE,
        TriggerConditionChangedEventPayload,
    )

    # Create a change event
    payload = TriggerConditionChangedEventPayload(
        change_id=uuid4(),
        trigger_type="breach_threshold",
        old_value=10,
        new_value=12,
        changed_by="keeper-001",
        change_reason="Constitutional amendment approved",
        change_timestamp=datetime.now(timezone.utc),
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID


# Event type constant for trigger condition changes
TRIGGER_CONDITION_CHANGED_EVENT_TYPE: str = "cessation.trigger_condition_changed"
"""Event type for trigger condition changes (FR134 AC4)."""


@dataclass(frozen=True, eq=True)
class TriggerConditionChangedEventPayload:
    """Payload for trigger condition change events (FR134 AC4).

    A TriggerConditionChangedEventPayload is created when a cessation
    trigger threshold is modified through constitutional process.
    This ensures all changes are witnessed and publicly visible.

    Constitutional Constraint (CT-12):
    Witnessing creates accountability. This event MUST be witnessed
    when written to the event store.

    Constitutional Constraint (FR134 AC4):
    When a cessation trigger condition changes, a TriggerConditionChangedEvent
    SHALL be created with old_value, new_value, changed_by, and change_reason.

    Attributes:
        change_id: Unique identifier for this change event.
        trigger_type: Type of trigger that changed (e.g., "breach_threshold").
        old_value: Previous threshold value.
        new_value: New threshold value.
        changed_by: ID of Keeper or process that made the change.
        change_reason: Human-readable reason for the change.
        change_timestamp: When the change occurred (UTC).
        fr_reference: Functional requirement reference for the trigger.
        constitutional_floor: Minimum allowed value (change cannot go below this).

    Example:
        >>> payload = TriggerConditionChangedEventPayload(
        ...     change_id=uuid4(),
        ...     trigger_type="breach_threshold",
        ...     old_value=10,
        ...     new_value=12,
        ...     changed_by="keeper-001",
        ...     change_reason="Constitutional amendment",
        ...     change_timestamp=datetime.now(timezone.utc),
        ... )
        >>> payload.trigger_type
        'breach_threshold'
    """

    change_id: UUID
    trigger_type: str
    old_value: int | float
    new_value: int | float
    changed_by: str
    change_reason: str
    change_timestamp: datetime

    # Optional fields for additional context
    fr_reference: Optional[str] = field(default=None)
    constitutional_floor: Optional[int | float] = field(default=None)

    def __post_init__(self) -> None:
        """Validate the change event on creation.

        Raises:
            ValueError: If new_value is below constitutional_floor.
        """
        if (
            self.constitutional_floor is not None
            and self.new_value < self.constitutional_floor
        ):
            raise ValueError(
                f"new_value {self.new_value} cannot be below constitutional_floor "
                f"{self.constitutional_floor} for trigger {self.trigger_type}"
            )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "change_id": str(self.change_id),
            "trigger_type": self.trigger_type,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_by": self.changed_by,
            "change_reason": self.change_reason,
            "change_timestamp": self.change_timestamp.isoformat(),
        }

        # Include optional fields if present
        if self.fr_reference is not None:
            content["fr_reference"] = self.fr_reference
        if self.constitutional_floor is not None:
            content["constitutional_floor"] = self.constitutional_floor

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        result: dict[str, Any] = {
            "change_id": str(self.change_id),
            "trigger_type": self.trigger_type,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_by": self.changed_by,
            "change_reason": self.change_reason,
            "change_timestamp": self.change_timestamp.isoformat(),
        }

        # Include optional fields if present
        if self.fr_reference is not None:
            result["fr_reference"] = self.fr_reference
        if self.constitutional_floor is not None:
            result["constitutional_floor"] = self.constitutional_floor

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TriggerConditionChangedEventPayload:
        """Create payload from dictionary.

        Args:
            data: Dictionary with payload fields.

        Returns:
            TriggerConditionChangedEventPayload instance.
        """
        change_timestamp = data["change_timestamp"]
        if isinstance(change_timestamp, str):
            change_timestamp = datetime.fromisoformat(
                change_timestamp.replace("Z", "+00:00")
            )

        return cls(
            change_id=UUID(data["change_id"]) if isinstance(data["change_id"], str) else data["change_id"],
            trigger_type=data["trigger_type"],
            old_value=data["old_value"],
            new_value=data["new_value"],
            changed_by=data["changed_by"],
            change_reason=data["change_reason"],
            change_timestamp=change_timestamp,
            fr_reference=data.get("fr_reference"),
            constitutional_floor=data.get("constitutional_floor"),
        )
