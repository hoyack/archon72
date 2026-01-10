"""HeartbeatService application service (Story 2.6, FR14/FR90-FR93).

This service orchestrates heartbeat operations: emission, monitoring,
liveness checking, and spoofing detection.

Constitutional Constraints:
- FR90: Each agent SHALL emit heartbeat during active operation
- FR91: Missing heartbeat beyond 2x expected interval triggers alert
- FR93: Spoofed heartbeats must be rejected and logged

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> All operations traceable
- CT-13: Integrity outranks availability -> Reject invalid heartbeats

Architecture Pattern:
    HeartbeatService orchestrates FR90-FR93 compliance:

    emit_agent_heartbeat(agent_id, session_id, status, memory):
      ├─ halt_checker.is_halted()       # HALT FIRST rule
      ├─ emitter.emit_heartbeat()       # Create heartbeat
      ├─ emitter.sign_heartbeat()       # Sign for spoofing defense
      └─ monitor.register_heartbeat()   # Register with monitor

    verify_and_register_heartbeat(heartbeat, session_registry):
      ├─ halt_checker.is_halted()       # HALT FIRST rule
      ├─ verifier.detect_spoofing()     # FR90 check
      ├─ verifier.reject_spoofed_heartbeat()  # Raise if spoofed
      └─ monitor.register_heartbeat()   # Register valid heartbeat
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.heartbeat_emitter import HeartbeatEmitterPort
from src.application.ports.heartbeat_monitor import HeartbeatMonitorPort
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.heartbeat import Heartbeat
from src.domain.services.heartbeat_verifier import HeartbeatVerifier

if TYPE_CHECKING:
    from src.application.ports.agent_orchestrator import AgentStatus

logger = structlog.get_logger()


class HeartbeatService:
    """Application service for agent heartbeat monitoring (FR14/FR90-FR93).

    This service provides the primary interface for:
    - Emitting heartbeats during agent deliberation
    - Checking agent liveness
    - Detecting unresponsive agents
    - Verifying and registering received heartbeats

    HALT FIRST Rule:
        Every operation checks halt state before proceeding.
        Never retry after SystemHaltedError.

    Attributes:
        _halt_checker: Interface for checking halt state.
        _emitter: Interface for emitting heartbeats.
        _monitor: Interface for monitoring heartbeats.
        _verifier: Domain service for spoofing detection.
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        emitter: HeartbeatEmitterPort,
        monitor: HeartbeatMonitorPort,
        verifier: HeartbeatVerifier | None = None,
    ) -> None:
        """Initialize the service with required dependencies.

        Args:
            halt_checker: Interface for checking halt state.
            emitter: Interface for emitting heartbeats.
            monitor: Interface for monitoring heartbeats.
            verifier: Domain service for spoofing detection.
                Defaults to new HeartbeatVerifier() if not provided.
        """
        self._halt_checker = halt_checker
        self._emitter = emitter
        self._monitor = monitor
        self._verifier = verifier or HeartbeatVerifier()

    async def emit_agent_heartbeat(
        self,
        agent_id: str,
        session_id: UUID,
        status: AgentStatus,
        memory_usage_mb: int,
    ) -> Heartbeat:
        """Emit a heartbeat for an agent during deliberation.

        This is the primary method for FR90 compliance. Agents should
        call this every HEARTBEAT_INTERVAL_SECONDS (30s) during operation.

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Create heartbeat with agent info
            3. Sign heartbeat with agent's key (spoofing defense)
            4. Register with monitor for liveness tracking

        Args:
            agent_id: The ID of the agent (e.g., "archon-42").
            session_id: The current deliberation session ID.
            status: Current agent status.
            memory_usage_mb: Current memory usage.

        Returns:
            Signed Heartbeat object.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning(
                "heartbeat_emission_blocked_halted",
                agent_id=agent_id,
            )
            raise SystemHaltedError("System halted - cannot emit heartbeat")

        # Create heartbeat
        heartbeat = await self._emitter.emit_heartbeat(
            agent_id=agent_id,
            session_id=session_id,
            status=status,
            memory_usage_mb=memory_usage_mb,
        )

        # Sign heartbeat for spoofing defense (FR93)
        signed_heartbeat = await self._emitter.sign_heartbeat(
            heartbeat=heartbeat,
            agent_key=None,  # Stub doesn't need real key
        )

        # Register with monitor for liveness tracking
        await self._monitor.register_heartbeat(signed_heartbeat)

        logger.info(
            "heartbeat_emitted",
            agent_id=agent_id,
            heartbeat_id=str(signed_heartbeat.heartbeat_id),
            status=status.value if hasattr(status, "value") else str(status),
            memory_usage_mb=memory_usage_mb,
        )

        return signed_heartbeat

    async def check_agent_liveness(self, agent_id: str) -> bool:
        """Check if an agent is currently responsive.

        This method checks if the agent has sent a recent heartbeat
        (within the unresponsive timeout threshold).

        Args:
            agent_id: The ID of the agent to check.

        Returns:
            True if agent is responsive, False otherwise.
        """
        is_responsive = await self._monitor.is_agent_responsive(agent_id)

        if not is_responsive:
            # Get last heartbeat for logging
            last_hb = await self._monitor.get_last_heartbeat(agent_id)
            last_hb_time = str(last_hb.timestamp) if last_hb else "never"
            logger.warning(
                "agent_not_responsive",
                agent_id=agent_id,
                last_heartbeat=last_hb_time,
            )

        return is_responsive

    async def detect_unresponsive_agents(
        self,
        threshold_seconds: int = 90,
    ) -> list[str]:
        """Detect all agents that have missed heartbeats.

        This method is called periodically (e.g., by a watchdog) to
        find agents that need recovery attention.

        Args:
            threshold_seconds: Maximum seconds since last heartbeat.
                Defaults to 90 (3 missed heartbeats at 30s interval).

        Returns:
            List of agent IDs that are unresponsive.
        """
        unresponsive = await self._monitor.get_unresponsive_agents(
            threshold_seconds=threshold_seconds,
        )

        for agent_id in unresponsive:
            last_hb = await self._monitor.get_last_heartbeat(agent_id)
            logger.warning(
                "unresponsive_agent_detected",
                agent_id=agent_id,
                last_heartbeat=str(last_hb.timestamp) if last_hb else "never",
                threshold_seconds=threshold_seconds,
            )

        return unresponsive

    async def verify_and_register_heartbeat(
        self,
        heartbeat: Heartbeat,
        session_registry: dict[str, UUID],
    ) -> None:
        """Verify and register an incoming heartbeat.

        This method verifies the heartbeat against spoofing and
        registers valid heartbeats with the monitor.

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Verify signature and session (FR90)
            3. Reject spoofed heartbeats with logged error
            4. Register valid heartbeats

        Args:
            heartbeat: The heartbeat to verify and register.
            session_registry: Map of agent_id to expected session_id.

        Raises:
            SystemHaltedError: If system is halted.
            HeartbeatSpoofingError: If heartbeat is spoofed (FR90).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning(
                "heartbeat_verification_blocked_halted",
                agent_id=heartbeat.agent_id,
            )
            raise SystemHaltedError("System halted - cannot verify heartbeat")

        # Detect spoofing (FR90)
        is_spoofed = self._verifier.detect_spoofing(heartbeat, session_registry)

        if is_spoofed:
            # Determine reason for rejection
            if heartbeat.signature is None or heartbeat.signature == "":
                reason = "unsigned_heartbeat"
            elif heartbeat.agent_id not in session_registry:
                reason = "unknown_agent"
            else:
                reason = "session_mismatch"

            # Reject and log (FR90)
            self._verifier.reject_spoofed_heartbeat(heartbeat, reason)
            # Note: reject_spoofed_heartbeat always raises

        # Register valid heartbeat
        await self._monitor.register_heartbeat(heartbeat)

        logger.info(
            "heartbeat_verified_and_registered",
            agent_id=heartbeat.agent_id,
            heartbeat_id=str(heartbeat.heartbeat_id),
        )
