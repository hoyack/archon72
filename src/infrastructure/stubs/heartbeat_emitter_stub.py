"""Stub HeartbeatEmitter for development/testing (Story 2.6, FR90).

This stub implements HeartbeatEmitterPort for local development and testing.
It tracks emitted heartbeats in-memory for test assertions.

RT-1 Pattern (ADR-4): All signatures include [DEV MODE] prefix to prevent
confusion with production signatures.

WARNING: This stub is for development/testing only.
Production must use a real implementation with HSM signing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from src.application.ports.heartbeat_emitter import HeartbeatEmitterPort
from src.domain.models.heartbeat import Heartbeat

if TYPE_CHECKING:
    from uuid import UUID

    from src.application.ports.agent_orchestrator import AgentStatus
    from src.domain.models.agent_key import AgentKey

logger = structlog.get_logger()


# RT-1/ADR-4: Dev mode signatures include this prefix
DEV_MODE_SIGNATURE_PREFIX: str = "[DEV_MODE]"


class HeartbeatEmitterStub(HeartbeatEmitterPort):
    """Stub implementation of HeartbeatEmitterPort for development/testing.

    WARNING: NOT FOR PRODUCTION USE.

    This implementation:
    - Creates heartbeats with timestamps and UUIDs
    - Signs heartbeats with [DEV_MODE] prefix (RT-1/ADR-4)
    - Tracks all emitted heartbeats for test assertions
    - Does NOT perform real cryptographic signing

    Attributes:
        _emissions: List of emitted heartbeats for test verification.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty emission tracking."""
        self._emissions: list[Heartbeat] = []
        logger.warning(
            "heartbeat_emitter_stub_initialized",
            message="Using DEV MODE heartbeat emitter - NOT FOR PRODUCTION",
        )

    async def emit_heartbeat(
        self,
        agent_id: str,
        session_id: UUID,
        status: AgentStatus,
        memory_usage_mb: int,
    ) -> Heartbeat:
        """Emit a heartbeat for an agent (stub implementation).

        Creates a new Heartbeat with generated UUID and current timestamp.
        The heartbeat is NOT signed - use sign_heartbeat() for that.

        Args:
            agent_id: The ID of the agent.
            session_id: The current session ID.
            status: Current agent status.
            memory_usage_mb: Current memory usage.

        Returns:
            Unsigned Heartbeat object.
        """
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id=agent_id,
            session_id=session_id,
            status=status,
            memory_usage_mb=memory_usage_mb,
            timestamp=datetime.now(timezone.utc),
            signature=None,
        )

        self._emissions.append(heartbeat)

        logger.debug(
            "heartbeat_emitted_stub",
            agent_id=agent_id,
            heartbeat_id=str(heartbeat.heartbeat_id),
            status=status.value if hasattr(status, "value") else str(status),
        )

        return heartbeat

    async def sign_heartbeat(
        self,
        heartbeat: Heartbeat,
        agent_key: AgentKey | None,
    ) -> Heartbeat:
        """Sign a heartbeat with dev mode watermark (stub implementation).

        Creates a new Heartbeat with a dev mode signature. The signature
        includes [DEV_MODE] prefix per RT-1/ADR-4 to prevent confusion
        with production signatures.

        Args:
            heartbeat: The heartbeat to sign.
            agent_key: The agent's key (ignored in stub - no real crypto).

        Returns:
            New Heartbeat with signature field set.
        """
        # Create dev mode signature (not cryptographically valid)
        dev_signature = f"{DEV_MODE_SIGNATURE_PREFIX}:{heartbeat.agent_id}:{heartbeat.heartbeat_id}"

        signed = Heartbeat(
            heartbeat_id=heartbeat.heartbeat_id,
            agent_id=heartbeat.agent_id,
            session_id=heartbeat.session_id,
            status=heartbeat.status,
            memory_usage_mb=heartbeat.memory_usage_mb,
            timestamp=heartbeat.timestamp,
            signature=dev_signature,
        )

        logger.debug(
            "heartbeat_signed_stub",
            agent_id=heartbeat.agent_id,
            heartbeat_id=str(heartbeat.heartbeat_id),
            signature_prefix=DEV_MODE_SIGNATURE_PREFIX,
        )

        return signed

    # Test helper methods

    def get_emissions(self) -> list[Heartbeat]:
        """Get all emitted heartbeats for test verification.

        Returns:
            List of all heartbeats emitted through this stub.
        """
        return list(self._emissions)

    def clear_emissions(self) -> None:
        """Clear the emission tracking (for test reset)."""
        self._emissions.clear()
