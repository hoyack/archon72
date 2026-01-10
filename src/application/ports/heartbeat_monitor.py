"""HeartbeatMonitor port - interface for agent heartbeat monitoring (Story 2.6, FR91).

This port defines the abstract interface for monitoring heartbeats and
detecting unresponsive agents.

Constitutional Constraints:
- FR91: Missing heartbeat beyond 2x expected interval triggers alert

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Detect unresponsive agents
- CT-12: Witnessing creates accountability -> All detections are traceable
- CT-13: Integrity outranks availability -> Flag unresponsive agents
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.domain.models.heartbeat import Heartbeat


@runtime_checkable
class HeartbeatMonitorPort(Protocol):
    """Abstract interface for heartbeat monitoring.

    All heartbeat monitor implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific monitoring mechanisms.

    Constitutional Constraints:
    - FR91: Detect missing heartbeats and trigger alerts
    - CT-11: Never silently drop unresponsive agents

    Note:
        This port defines the abstract interface. Infrastructure adapters
        (e.g., HeartbeatMonitorStub) implement this protocol with specific
        monitoring logic.
    """

    async def register_heartbeat(self, heartbeat: Heartbeat) -> None:
        """Register a received heartbeat for an agent.

        Stores the heartbeat for later liveness checking. This should be
        called after verifying the heartbeat signature.

        Args:
            heartbeat: The verified heartbeat to register.

        Note:
            This does NOT verify the heartbeat signature. Use
            HeartbeatVerifier for signature verification before calling.
        """
        ...

    async def get_last_heartbeat(self, agent_id: str) -> Heartbeat | None:
        """Get the last registered heartbeat for an agent.

        Args:
            agent_id: The ID of the agent to query.

        Returns:
            The last registered Heartbeat, or None if no heartbeat exists.
        """
        ...

    async def get_unresponsive_agents(
        self,
        threshold_seconds: int = 90,
    ) -> list[str]:
        """Get all agents whose last heartbeat exceeds the threshold.

        Agents are considered unresponsive if their last heartbeat
        timestamp is older than (now - threshold_seconds).

        Args:
            threshold_seconds: Maximum seconds since last heartbeat.
                Defaults to 90 (3 missed heartbeats at 30s interval).

        Returns:
            List of agent IDs that are unresponsive.
        """
        ...

    async def is_agent_responsive(self, agent_id: str) -> bool:
        """Check if an agent is currently responsive.

        An agent is responsive if their last heartbeat was within
        the default threshold (90 seconds).

        Args:
            agent_id: The ID of the agent to check.

        Returns:
            True if agent is responsive, False otherwise.
            Returns False if agent has never sent a heartbeat.
        """
        ...
