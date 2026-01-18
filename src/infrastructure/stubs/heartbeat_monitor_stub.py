"""Stub HeartbeatMonitor for development/testing (Story 2.6, FR91).

This stub implements HeartbeatMonitorPort for local development and testing.
It tracks heartbeats in-memory and detects unresponsive agents.

RT-1 Pattern (ADR-4): Dev mode logging distinguishes from production.

WARNING: This stub is for development/testing only.
Production must use a real implementation with persistent storage.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog

from src.application.ports.heartbeat_emitter import UNRESPONSIVE_TIMEOUT_SECONDS
from src.application.ports.heartbeat_monitor import HeartbeatMonitorPort

if TYPE_CHECKING:
    from src.domain.models.heartbeat import Heartbeat

logger = structlog.get_logger()


class HeartbeatMonitorStub(HeartbeatMonitorPort):
    """Stub implementation of HeartbeatMonitorPort for development/testing.

    WARNING: NOT FOR PRODUCTION USE.

    This implementation:
    - Stores heartbeats in-memory (not persistent)
    - Detects unresponsive agents based on timestamp comparison
    - Provides test helpers for assertion verification

    Attributes:
        _heartbeats: Dict mapping agent_id to last known Heartbeat.
        _threshold_seconds: Default threshold for unresponsive detection.
    """

    def __init__(
        self,
        threshold_seconds: int = UNRESPONSIVE_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the stub with empty heartbeat tracking.

        Args:
            threshold_seconds: Default threshold for unresponsive detection.
                Defaults to 90 seconds (3 missed heartbeats).
        """
        self._heartbeats: dict[str, Heartbeat] = {}
        self._threshold_seconds = threshold_seconds
        logger.warning(
            "heartbeat_monitor_stub_initialized",
            message="Using DEV MODE heartbeat monitor - NOT FOR PRODUCTION",
            threshold_seconds=threshold_seconds,
        )

    async def register_heartbeat(self, heartbeat: Heartbeat) -> None:
        """Register a heartbeat for an agent (stub implementation).

        Stores the heartbeat in memory, overwriting any previous heartbeat.

        Args:
            heartbeat: The heartbeat to register.
        """
        self._heartbeats[heartbeat.agent_id] = heartbeat
        logger.debug(
            "heartbeat_registered_stub",
            agent_id=heartbeat.agent_id,
            heartbeat_id=str(heartbeat.heartbeat_id),
            timestamp=str(heartbeat.timestamp),
        )

    async def get_last_heartbeat(self, agent_id: str) -> Heartbeat | None:
        """Get the last registered heartbeat for an agent (stub implementation).

        Args:
            agent_id: The ID of the agent.

        Returns:
            The last Heartbeat, or None if agent is unknown.
        """
        return self._heartbeats.get(agent_id)

    async def get_unresponsive_agents(
        self,
        threshold_seconds: int = 90,
    ) -> list[str]:
        """Get agents whose heartbeats exceed the threshold (stub implementation).

        Args:
            threshold_seconds: Maximum seconds since last heartbeat.

        Returns:
            List of unresponsive agent IDs.
        """
        now = datetime.now(timezone.utc)
        threshold_time = now - timedelta(seconds=threshold_seconds)

        unresponsive: list[str] = []
        for agent_id, heartbeat in self._heartbeats.items():
            if heartbeat.timestamp < threshold_time:
                unresponsive.append(agent_id)
                logger.debug(
                    "agent_unresponsive_detected_stub",
                    agent_id=agent_id,
                    last_heartbeat=str(heartbeat.timestamp),
                    threshold_seconds=threshold_seconds,
                )

        return unresponsive

    async def is_agent_responsive(self, agent_id: str) -> bool:
        """Check if an agent is responsive (stub implementation).

        Args:
            agent_id: The ID of the agent.

        Returns:
            True if agent has recent heartbeat, False otherwise.
        """
        heartbeat = self._heartbeats.get(agent_id)
        if heartbeat is None:
            return False

        now = datetime.now(timezone.utc)
        threshold_time = now - timedelta(seconds=self._threshold_seconds)
        return heartbeat.timestamp >= threshold_time

    # Test helper methods

    def get_all_heartbeats(self) -> dict[str, Heartbeat]:
        """Get all stored heartbeats for test verification.

        Returns:
            Copy of the heartbeat dictionary.
        """
        return dict(self._heartbeats)

    def clear_heartbeats(self) -> None:
        """Clear all stored heartbeats (for test reset)."""
        self._heartbeats.clear()
