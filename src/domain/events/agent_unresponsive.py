"""AgentUnresponsiveEvent domain event (Story 2.6, FR91).

This module defines the AgentUnresponsivePayload for recording agent
liveness failures detected by the heartbeat monitoring system.

Constitutional Constraints:
- FR91: System detects unresponsive agents (3 missed heartbeats)
- FR92: Missed heartbeats logged without derailing process
- CT-11: Silent failure destroys legitimacy -> Log all failures
- CT-12: Witnessing creates accountability -> Record detection events
- CT-13: Integrity outranks availability -> Flag for recovery

An AgentUnresponsiveEvent is created when an agent is detected as
unresponsive (missed 3+ heartbeats or 90+ seconds since last heartbeat).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Event type constant following lowercase.dot.notation convention
AGENT_UNRESPONSIVE_EVENT_TYPE: str = "agent.unresponsive"


@dataclass(frozen=True, eq=True)
class AgentUnresponsivePayload:
    """Payload for agent unresponsive events (FR91).

    Records when an agent is detected as unresponsive due to missed
    heartbeats. This event is used to track agent liveness failures
    and trigger recovery procedures.

    Attributes:
        agent_id: ID of the unresponsive agent.
        session_id: UUID of the agent's session when it became unresponsive.
        last_heartbeat: Timestamp of the last received heartbeat, or None
            if no heartbeat was ever received from this agent.
        missed_heartbeat_count: Number of missed heartbeats at detection time.
        detection_timestamp: UTC timestamp when unresponsiveness was detected.
        flagged_for_recovery: Whether the agent was flagged for recovery action.

    Constitutional Constraints:
        - agent_id must be non-empty
        - session_id must be a valid UUID
        - missed_heartbeat_count must be non-negative
        - detection_timestamp required

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> payload = AgentUnresponsivePayload(
        ...     agent_id="archon-1",
        ...     session_id=uuid4(),
        ...     last_heartbeat=datetime.now(timezone.utc),
        ...     missed_heartbeat_count=3,
        ...     detection_timestamp=datetime.now(timezone.utc),
        ...     flagged_for_recovery=True,
        ... )
    """

    agent_id: str
    session_id: UUID
    last_heartbeat: datetime | None
    missed_heartbeat_count: int
    detection_timestamp: datetime
    flagged_for_recovery: bool

    def __post_init__(self) -> None:
        """Validate payload fields for FR91 compliance.

        Raises:
            ValueError: If agent_id is empty or missed_heartbeat_count is negative.
            TypeError: If session_id is not a UUID.
        """
        self._validate_agent_id()
        self._validate_session_id()
        self._validate_missed_heartbeat_count()

    def _validate_agent_id(self) -> None:
        """Validate agent_id is non-empty string."""
        if not isinstance(self.agent_id, str) or not self.agent_id.strip():
            raise ValueError("agent_id must be non-empty string")

    def _validate_session_id(self) -> None:
        """Validate session_id is a UUID."""
        if not isinstance(self.session_id, UUID):
            raise TypeError(
                f"session_id must be UUID, got {type(self.session_id).__name__}"
            )

    def _validate_missed_heartbeat_count(self) -> None:
        """Validate missed_heartbeat_count is non-negative."""
        if (
            not isinstance(self.missed_heartbeat_count, int)
            or self.missed_heartbeat_count < 0
        ):
            raise ValueError(
                f"missed_heartbeat_count must be non-negative integer, got {self.missed_heartbeat_count}"
            )

    def to_dict(self) -> dict[str, object]:
        """Convert payload to dictionary for event serialization.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "agent_id": self.agent_id,
            "session_id": str(self.session_id),
            "last_heartbeat": self.last_heartbeat.isoformat()
            if self.last_heartbeat
            else None,
            "missed_heartbeat_count": self.missed_heartbeat_count,
            "detection_timestamp": self.detection_timestamp.isoformat(),
            "flagged_for_recovery": self.flagged_for_recovery,
        }
