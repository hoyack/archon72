"""Heartbeat-related domain errors (Story 2.6, FR90-FR91).

This module provides exception classes for heartbeat monitoring failures.

Constitutional Constraints:
- FR90: Spoofed heartbeats must be rejected
- FR91: Missing heartbeats trigger alerts

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Detect unresponsive agents
- CT-12: Witnessing creates accountability -> All detections are traceable
"""

from __future__ import annotations

from datetime import datetime

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.exceptions import ConclaveError


class AgentUnresponsiveError(ConclaveError):
    """Raised when an agent is detected as unresponsive (FR91).

    This error is raised when an agent has missed the threshold number
    of heartbeats and is flagged for recovery.

    Attributes:
        agent_id: The ID of the unresponsive agent.
        last_heartbeat_timestamp: When the last heartbeat was received.
        missed_count: Number of consecutive missed heartbeats.
    """

    def __init__(
        self,
        agent_id: str,
        last_heartbeat_timestamp: datetime | None,
        missed_count: int,
    ) -> None:
        """Initialize the error.

        Args:
            agent_id: The ID of the unresponsive agent.
            last_heartbeat_timestamp: When the last heartbeat was received.
                None if agent never sent a heartbeat.
            missed_count: Number of consecutive missed heartbeats.
        """
        self.agent_id = agent_id
        self.last_heartbeat_timestamp = last_heartbeat_timestamp
        self.missed_count = missed_count

        last_hb_str = (
            str(last_heartbeat_timestamp)
            if last_heartbeat_timestamp
            else "never"
        )
        message = (
            f"FR91: Agent {agent_id} is unresponsive - "
            f"missed {missed_count} heartbeats, "
            f"last heartbeat: {last_hb_str}"
        )
        super().__init__(message)


class HeartbeatSpoofingError(ConstitutionalViolationError):
    """Raised when a spoofed heartbeat is detected (FR90).

    This is a constitutional violation because spoofed heartbeats
    could mask agent failures and undermine system integrity.

    Attributes:
        agent_id: The agent_id claimed in the spoofed heartbeat.
        reason: Why the heartbeat was determined to be spoofed.
    """

    def __init__(
        self,
        agent_id: str,
        reason: str,
    ) -> None:
        """Initialize the error.

        Args:
            agent_id: The agent_id claimed in the spoofed heartbeat.
            reason: Why the heartbeat was determined to be spoofed
                (e.g., "signature_mismatch", "session_invalid").
        """
        self.agent_id = agent_id
        self.reason = reason

        message = (
            f"FR90: Heartbeat spoofing detected for agent {agent_id} - "
            f"reason: {reason}"
        )
        super().__init__(message)
