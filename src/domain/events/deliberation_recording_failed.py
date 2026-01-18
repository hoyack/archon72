"""Deliberation recording failed event payload (Story 7.8, FR135).

This module defines the DeliberationRecordingFailedEventPayload for capturing
recording failures as the final event when deliberation recording fails.

Constitutional Constraints:
- FR135: If recording fails, that failure is the final event
- CT-11: Silent failure destroys legitimacy -> Failure MUST be logged
- CT-12: Witnessing creates accountability -> Failure must be witnessed

Developer Golden Rules:
1. FAIL LOUD - This is the final event when deliberation recording fails
2. WITNESS EVERYTHING - CT-12 requires failure to be witnessed
3. INTEGRITY FIRST - This event proves the system tried and failed honestly
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

# Event type constant following lowercase.dot.notation convention
DELIBERATION_RECORDING_FAILED_EVENT_TYPE: str = (
    "cessation.deliberation_recording_failed"
)

# Maximum Archon count for validation
MAX_ARCHON_COUNT: int = 72


@dataclass(frozen=True, eq=True)
class DeliberationRecordingFailedEventPayload:
    """Payload for deliberation recording failure events (FR135).

    This event captures the failure when cessation deliberation recording
    fails. Per FR135, if recording fails, that failure IS the final event.

    This ensures the system cannot silently fail to record deliberation.
    The failure itself becomes the permanent record of what happened.

    Constitutional Constraints:
    - FR135: Recording failure SHALL be the final event
    - CT-11: Silent failure destroys legitimacy -> All failure details logged
    - CT-12: Witnessing creates accountability -> Failure must be witnessed

    Attributes:
        deliberation_id: ID of the deliberation that failed to record.
        attempted_at: When recording was first attempted (UTC).
        failed_at: When the failure was determined final (UTC).
        error_code: Machine-readable error code.
        error_message: Human-readable error description.
        retry_count: Number of retry attempts before giving up.
        partial_archon_count: Number of Archon deliberations collected before failure.
    """

    deliberation_id: UUID
    attempted_at: datetime
    failed_at: datetime
    error_code: str
    error_message: str
    retry_count: int
    partial_archon_count: int

    def __post_init__(self) -> None:
        """Validate payload fields for FR135 compliance.

        Raises:
            ValueError: If any field fails validation.
        """
        self._validate_retry_count()
        self._validate_partial_archon_count()
        self._validate_error_code()

    def _validate_retry_count(self) -> None:
        """Validate retry_count is non-negative."""
        if self.retry_count < 0:
            raise ValueError(
                f"retry_count must be non-negative, got {self.retry_count}"
            )

    def _validate_partial_archon_count(self) -> None:
        """Validate partial_archon_count is between 0 and 72."""
        if self.partial_archon_count < 0:
            raise ValueError(
                f"partial_archon_count must be non-negative, got {self.partial_archon_count}"
            )
        if self.partial_archon_count > MAX_ARCHON_COUNT:
            raise ValueError(
                f"partial_archon_count cannot exceed 72, got {self.partial_archon_count}"
            )

    def _validate_error_code(self) -> None:
        """Validate error_code is not empty."""
        if not self.error_code:
            raise ValueError("error_code cannot be empty")

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "attempted_at": self.attempted_at.isoformat(),
            "deliberation_id": str(self.deliberation_id),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "failed_at": self.failed_at.isoformat(),
            "partial_archon_count": self.partial_archon_count,
            "retry_count": self.retry_count,
        }

        return json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "deliberation_id": str(self.deliberation_id),
            "attempted_at": self.attempted_at.isoformat(),
            "failed_at": self.failed_at.isoformat(),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "partial_archon_count": self.partial_archon_count,
        }
