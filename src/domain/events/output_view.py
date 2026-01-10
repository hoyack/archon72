"""Output view event types (Story 2.1, AC2).

This module defines the OutputViewPayload and event type constant
for recording when humans view deliberation outputs. This creates
an audit trail for the No Preview constraint.

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- CT-12: Witnessing creates accountability - view events create audit trail
- AC2: Hash Verification on View - view event logged with viewer identity
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Event type constant following lowercase.dot.notation convention
OUTPUT_VIEW_EVENT_TYPE: str = "output.view"


@dataclass(frozen=True, eq=True)
class OutputViewPayload:
    """Payload for output view events (AC2).

    Records when a human or system views a deliberation output.
    This creates an audit trail that external observers can verify.

    Attributes:
        output_id: UUID of the output being viewed.
        viewer_id: Identity of the viewer (user ID, API client ID, etc.).
        viewer_type: Type of viewer (e.g., "human", "api_client", "system").
        viewed_at: Timestamp when the view occurred.

    Constitutional Constraints:
        - CT-12: Creates accountability through audit trail
        - AC2: Logs viewer identity with each view

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> payload = OutputViewPayload(
        ...     output_id=uuid4(),
        ...     viewer_id="user-123",
        ...     viewer_type="human",
        ...     viewed_at=datetime.now(timezone.utc),
        ... )
    """

    output_id: UUID
    viewer_id: str
    viewer_type: str
    viewed_at: datetime

    def __post_init__(self) -> None:
        """Validate payload fields.

        Raises:
            TypeError: If output_id is not UUID or viewed_at is not datetime.
            ValueError: If any string field fails validation.
        """
        self._validate_output_id()
        self._validate_viewer_id()
        self._validate_viewer_type()
        self._validate_viewed_at()

    def _validate_output_id(self) -> None:
        """Validate output_id is a UUID."""
        if not isinstance(self.output_id, UUID):
            raise TypeError(
                f"output_id must be UUID, got {type(self.output_id).__name__}"
            )

    def _validate_viewer_id(self) -> None:
        """Validate viewer_id is non-empty string."""
        if not isinstance(self.viewer_id, str) or not self.viewer_id.strip():
            raise ValueError("viewer_id must be non-empty string")

    def _validate_viewer_type(self) -> None:
        """Validate viewer_type is non-empty string."""
        if not isinstance(self.viewer_type, str) or not self.viewer_type.strip():
            raise ValueError("viewer_type must be non-empty string")

    def _validate_viewed_at(self) -> None:
        """Validate viewed_at is datetime."""
        if not isinstance(self.viewed_at, datetime):
            raise TypeError(
                f"viewed_at must be datetime, got {type(self.viewed_at).__name__}"
            )

    def to_dict(self) -> dict[str, str]:
        """Convert payload to dictionary for event payload field.

        Returns:
            Dictionary with string values suitable for JSON serialization.
        """
        return {
            "output_id": str(self.output_id),
            "viewer_id": self.viewer_id,
            "viewer_type": self.viewer_type,
            "viewed_at": self.viewed_at.isoformat(),
        }
