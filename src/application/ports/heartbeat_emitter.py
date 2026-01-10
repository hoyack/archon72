"""HeartbeatEmitter port - interface for agent heartbeat emission (Story 2.6, FR90).

This port defines the abstract interface for emitting heartbeats during
agent deliberation. Heartbeats are used to detect unresponsive agents.

Constitutional Constraints:
- FR90: Each agent SHALL emit heartbeat at minimum every 5 minutes
  (story uses 30s for faster detection)
- FR91: Missing heartbeat beyond 2x expected interval triggers alert

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Detect missing heartbeats
- CT-12: Witnessing creates accountability -> All heartbeats are traceable
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from src.application.ports.agent_orchestrator import AgentStatus
    from src.domain.models.agent_key import AgentKey
    from src.domain.models.heartbeat import Heartbeat


# Heartbeat timing constants (per Story 2.6 spec)
HEARTBEAT_INTERVAL_SECONDS: int = 30
"""Interval between heartbeats in seconds (FR90: faster than PRD minimum)."""

MISSED_HEARTBEAT_THRESHOLD: int = 3
"""Number of missed heartbeats before agent is considered unresponsive."""

UNRESPONSIVE_TIMEOUT_SECONDS: int = HEARTBEAT_INTERVAL_SECONDS * MISSED_HEARTBEAT_THRESHOLD
"""Total seconds before agent is flagged as unresponsive (90 seconds)."""


@runtime_checkable
class HeartbeatEmitterPort(Protocol):
    """Abstract interface for heartbeat emission.

    All heartbeat emitter implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific heartbeat emission mechanisms.

    Constitutional Constraints:
    - FR90: Emit heartbeats during agent operation
    - FR93: Sign heartbeats to prevent spoofing

    Note:
        This port defines the abstract interface. Infrastructure adapters
        (e.g., HeartbeatEmitterStub) implement this protocol with specific
        emission logic.
    """

    async def emit_heartbeat(
        self,
        agent_id: str,
        session_id: UUID,
        status: AgentStatus,
        memory_usage_mb: int,
    ) -> Heartbeat:
        """Emit a heartbeat for an agent.

        Creates a new heartbeat with the current timestamp and provided
        agent information. The heartbeat is NOT automatically signed;
        use sign_heartbeat() for spoofing defense.

        Args:
            agent_id: The ID of the agent (e.g., "archon-42").
            session_id: The current deliberation session ID.
            status: Current agent status (IDLE, BUSY, FAILED, UNKNOWN).
            memory_usage_mb: Current memory usage in megabytes.

        Returns:
            Heartbeat object with unsigned signature.

        Raises:
            ValueError: If agent_id is empty or memory_usage_mb is negative.
        """
        ...

    async def sign_heartbeat(
        self,
        heartbeat: Heartbeat,
        agent_key: AgentKey | None,
    ) -> Heartbeat:
        """Sign a heartbeat for spoofing defense (FR93).

        Creates a new Heartbeat with the cryptographic signature set.
        The original heartbeat is not modified (immutable).

        Args:
            heartbeat: The unsigned heartbeat to sign.
            agent_key: The agent's signing key.

        Returns:
            New Heartbeat object with signature field set.

        Raises:
            HSMError: If signing fails.
        """
        ...
