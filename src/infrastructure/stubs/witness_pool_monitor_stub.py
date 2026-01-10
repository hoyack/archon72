"""Witness pool monitor stub (Story 6.6, FR117).

Provides an in-memory stub implementation of WitnessPoolMonitorProtocol
for development and testing.

WARNING: DEV MODE ONLY
This stub is for development/testing only and should never be used
in production. The DEV MODE watermark is included in all operations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.application.ports.witness_pool_monitor import (
    MINIMUM_WITNESSES_HIGH_STAKES,
    MINIMUM_WITNESSES_STANDARD,
    WitnessPoolMonitorProtocol,
    WitnessPoolStatus,
)


logger = logging.getLogger(__name__)


# DEV MODE warning
DEV_MODE_WARNING = """
╔══════════════════════════════════════════════════════════════╗
║  [DEV MODE] WitnessPoolMonitorStub Active                    ║
║  This stub is for DEVELOPMENT/TESTING only.                  ║
║  DO NOT use in production environments.                      ║
╚══════════════════════════════════════════════════════════════╝
"""


class WitnessPoolMonitorStub(WitnessPoolMonitorProtocol):
    """In-memory stub for witness pool monitoring (FR117).

    Provides a simple implementation for development and testing.
    Supports configurable pool size and degraded state.

    WARNING: This stub is for development/testing only and should
    never be used in production.

    Example:
        stub = WitnessPoolMonitorStub()

        # Configure for test
        stub.set_pool_size(8)  # Below high-stakes minimum

        # Check status
        status = await stub.get_pool_status()
        assert status.is_degraded
    """

    def __init__(
        self,
        initial_pool_size: int = 15,
    ) -> None:
        """Initialize the stub with configurable pool size.

        Args:
            initial_pool_size: Initial number of available witnesses.
        """
        logger.warning(DEV_MODE_WARNING)

        self._available_witnesses: list[str] = [
            f"WITNESS:{i:03d}" for i in range(initial_pool_size)
        ]
        self._excluded_witnesses: list[str] = []
        self._degraded_since: Optional[datetime] = None
        self._force_degraded: Optional[bool] = None

    async def get_pool_status(self) -> WitnessPoolStatus:
        """Get current pool status.

        Returns:
            WitnessPoolStatus with current state.
        """
        available_count = len(self._available_witnesses)
        excluded = tuple(self._excluded_witnesses)
        effective_count = available_count - len(excluded)

        # Determine degraded state
        if self._force_degraded is not None:
            is_degraded = self._force_degraded
        else:
            is_degraded = effective_count < MINIMUM_WITNESSES_HIGH_STAKES

        # Track degraded start
        if is_degraded and self._degraded_since is None:
            self._degraded_since = datetime.now(timezone.utc)
        elif not is_degraded:
            self._degraded_since = None

        return WitnessPoolStatus(
            available_count=available_count,
            excluded_witnesses=excluded,
            is_degraded=is_degraded,
            degraded_since=self._degraded_since,
            minimum_for_standard=MINIMUM_WITNESSES_STANDARD,
            minimum_for_high_stakes=MINIMUM_WITNESSES_HIGH_STAKES,
        )

    async def is_degraded(self) -> bool:
        """Check if pool is in degraded mode.

        Returns:
            True if pool is below high-stakes minimum.
        """
        status = await self.get_pool_status()
        return status.is_degraded

    async def can_perform_operation(self, high_stakes: bool) -> bool:
        """Check if an operation can be performed.

        Args:
            high_stakes: True for high-stakes operations.

        Returns:
            True if the operation can proceed.
        """
        status = await self.get_pool_status()
        can_proceed, _ = status.can_perform(high_stakes)
        return can_proceed

    async def get_degraded_since(self) -> Optional[datetime]:
        """Get when degraded mode started.

        Returns:
            Datetime when degraded mode started, or None if not degraded.
        """
        return self._degraded_since

    async def get_available_witnesses(self) -> tuple[str, ...]:
        """Get list of available witness IDs.

        Returns:
            Tuple of available witness IDs.
        """
        return tuple(self._available_witnesses)

    async def get_ordered_active_witnesses(self) -> list[str]:
        """Get ordered list of active witnesses.

        Alias for get_available_witnesses, compatible with WitnessPoolProtocol.

        Returns:
            List of available witness IDs.
        """
        return list(self._available_witnesses)

    async def get_excluded_witnesses(self) -> tuple[str, ...]:
        """Get list of excluded witness IDs.

        Returns:
            Tuple of excluded witness IDs.
        """
        return tuple(self._excluded_witnesses)

    # ========== Test helpers ==========

    def set_pool_size(self, size: int) -> None:
        """Set the pool size for testing.

        Args:
            size: Number of witnesses in the pool.
        """
        self._available_witnesses = [
            f"WITNESS:{i:03d}" for i in range(size)
        ]
        self._force_degraded = None  # Re-calculate based on size
        logger.info(
            "[DEV MODE] Pool size set",
            extra={"size": size},
        )

    def set_available_witnesses(self, witnesses: list[str]) -> None:
        """Set specific witness IDs for testing.

        Args:
            witnesses: List of witness IDs.
        """
        self._available_witnesses = list(witnesses)
        self._force_degraded = None
        logger.info(
            "[DEV MODE] Available witnesses set",
            extra={"count": len(witnesses)},
        )

    def set_excluded_witnesses(self, excluded: list[str]) -> None:
        """Set excluded witnesses for testing.

        Args:
            excluded: List of excluded witness IDs.
        """
        self._excluded_witnesses = list(excluded)
        self._force_degraded = None
        logger.info(
            "[DEV MODE] Excluded witnesses set",
            extra={"count": len(excluded)},
        )

    def set_degraded(self, degraded: bool) -> None:
        """Force degraded state for testing.

        Args:
            degraded: True to force degraded mode, False to force healthy.
        """
        self._force_degraded = degraded
        if degraded and self._degraded_since is None:
            self._degraded_since = datetime.now(timezone.utc)
        elif not degraded:
            self._degraded_since = None
        logger.info(
            "[DEV MODE] Degraded state forced",
            extra={"degraded": degraded},
        )

    def clear(self) -> None:
        """Clear all state for test isolation."""
        self._available_witnesses = [
            f"WITNESS:{i:03d}" for i in range(15)
        ]
        self._excluded_witnesses = []
        self._degraded_since = None
        self._force_degraded = None
        logger.info("[DEV MODE] Stub state cleared")
