"""Configuration floor violation event payloads (Story 6.10, NFR39).

This module defines event payloads for configuration floor violations:
- ConfigurationFloorViolationEventPayload: When a floor violation is detected
- ConfigurationSource: Where the violation originated (startup, runtime, etc.)

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Violation events MUST be witnessed
- CT-13: Integrity outranks availability -> Startup failure over running below floor

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before runtime operations
2. WITNESS EVERYTHING - All violation events must be witnessed
3. FAIL LOUD - Never silently allow floor violations
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

# Event type constant for configuration floor violation
CONFIGURATION_FLOOR_VIOLATION_EVENT_TYPE: str = "configuration.floor_violation"


class ConfigurationSource(Enum):
    """Source of configuration change that violated a floor (NFR39).

    This enum identifies where the violation originated for audit purposes.
    """

    STARTUP = "STARTUP"
    """Configuration provided at application startup."""

    RUNTIME_API = "RUNTIME_API"
    """Configuration change attempted via API call."""

    RUNTIME_ENV = "RUNTIME_ENV"
    """Configuration change from environment variable reload."""

    RUNTIME_FILE = "RUNTIME_FILE"
    """Configuration change from config file reload."""


@dataclass(frozen=True, eq=True)
class ConfigurationFloorViolationEventPayload:
    """Payload for configuration floor violation events (NFR39).

    A ConfigurationFloorViolationEventPayload is created when a configuration
    value is attempted below its constitutional floor. This event MUST be
    witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - NFR39: No configuration SHALL allow thresholds below constitutional floors
    - CT-11: Silent failure destroys legitimacy -> Must halt on runtime violations
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - CT-13: Integrity outranks availability -> Startup fails over running below floor

    Attributes:
        violation_id: Unique identifier for this violation event.
        threshold_name: Name of the threshold being violated.
        attempted_value: The value that was attempted.
        constitutional_floor: The minimum allowed value.
        fr_reference: FR reference for the threshold (e.g., "FR32", "NFR39").
        source: Where the violation originated.
        detected_at: When the violation was detected (UTC).
    """

    violation_id: str
    threshold_name: str
    attempted_value: int | float
    constitutional_floor: int | float
    fr_reference: str
    source: ConfigurationSource
    detected_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for event serialization.

        Returns:
            Dictionary with all payload fields, enum serialized to string.
        """
        return {
            "violation_id": self.violation_id,
            "threshold_name": self.threshold_name,
            "attempted_value": self.attempted_value,
            "constitutional_floor": self.constitutional_floor,
            "fr_reference": self.fr_reference,
            "source": self.source.value,
            "detected_at": self.detected_at.isoformat(),
        }

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
            "violation_id": self.violation_id,
            "threshold_name": self.threshold_name,
            "attempted_value": self.attempted_value,
            "constitutional_floor": self.constitutional_floor,
            "fr_reference": self.fr_reference,
            "source": self.source.value,
            "detected_at": self.detected_at.isoformat(),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")
