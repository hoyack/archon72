"""Heartbeat domain model for agent liveness monitoring (FR90).

This module defines the Heartbeat frozen dataclass used for tracking
agent health and liveness during deliberations.

Constitutional Constraints:
- FR90: Each agent SHALL emit heartbeat at minimum every 5 minutes
  (story uses 30s for faster detection)
- FR91: Missing heartbeat beyond 2x expected interval triggers alert

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Missing heartbeats MUST be detected
- CT-12: Witnessing creates accountability -> All heartbeat ops are traceable
- CT-13: Integrity outranks availability -> Unresponsive agents flagged, not dropped
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.models.agent_status import AgentStatus


@dataclass(frozen=True, eq=True)
class Heartbeat:
    """Agent heartbeat for liveness monitoring (FR90).

    Heartbeats are emitted periodically by agents during deliberation to
    indicate they are healthy and responsive. Each heartbeat is immutable
    and may be signed for spoofing defense.

    Attributes:
        heartbeat_id: Unique identifier for this heartbeat.
        agent_id: The ID of the agent (e.g., "archon-42").
        session_id: The current deliberation session ID.
        status: Current agent status (IDLE, BUSY, FAILED, UNKNOWN).
        memory_usage_mb: Current memory usage in megabytes.
        timestamp: When the heartbeat was emitted.
        signature: Cryptographic signature for spoofing defense (FR90).

    Raises:
        ValueError: If agent_id is empty or memory_usage_mb is negative.
    """

    heartbeat_id: UUID
    agent_id: str
    session_id: UUID
    status: AgentStatus
    memory_usage_mb: int
    timestamp: datetime
    signature: str | None = None

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ValueError: If validation fails.
        """
        self._validate_agent_id()
        self._validate_memory_usage()

    def _validate_agent_id(self) -> None:
        """Validate agent_id is non-empty string."""
        if not isinstance(self.agent_id, str) or not self.agent_id.strip():
            raise ValueError(
                "FR90: Heartbeat validation failed - agent_id must be non-empty string"
            )

    def _validate_memory_usage(self) -> None:
        """Validate memory_usage_mb is non-negative."""
        if self.memory_usage_mb < 0:
            raise ValueError(
                "FR90: Heartbeat validation failed - memory_usage_mb must be >= 0"
            )
