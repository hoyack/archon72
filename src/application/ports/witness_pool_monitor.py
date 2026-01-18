"""Witness pool monitor port (Story 6.6, FR117).

Defines the protocol for monitoring witness pool health and surfacing
degraded mode when pool falls below operational minimums.

Constitutional Constraints:
- FR117: If witness pool <12, continue only for low-stakes events;
         high-stakes events pause until restored. Degraded mode publicly surfaced.
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

# Constitutional thresholds (FR117)
MINIMUM_WITNESSES_STANDARD: int = 6
MINIMUM_WITNESSES_HIGH_STAKES: int = 12


@dataclass(frozen=True)
class WitnessPoolStatus:
    """Current witness pool status (FR117).

    Constitutional Constraint (FR117):
    If witness pool <12, continue only for low-stakes events;
    high-stakes events pause until restored.
    Degraded mode publicly surfaced.

    Attributes:
        available_count: Total number of witnesses in the pool.
        excluded_witnesses: Witnesses currently excluded due to anomalies.
        is_degraded: True if pool is below high-stakes minimum.
        degraded_since: When degraded mode started (None if not degraded).
        minimum_for_standard: Minimum witnesses for standard operations (6).
        minimum_for_high_stakes: Minimum witnesses for high-stakes operations (12).
    """

    available_count: int
    excluded_witnesses: tuple[str, ...] = ()
    is_degraded: bool = False
    degraded_since: datetime | None = None
    minimum_for_standard: int = MINIMUM_WITNESSES_STANDARD
    minimum_for_high_stakes: int = MINIMUM_WITNESSES_HIGH_STAKES

    @property
    def effective_count(self) -> int:
        """Get effective count (available minus excluded).

        Returns:
            Number of witnesses actually available for selection.
        """
        return max(0, self.available_count - len(self.excluded_witnesses))

    def can_perform(self, high_stakes: bool) -> tuple[bool, str]:
        """Check if an operation can proceed (FR117).

        Args:
            high_stakes: True for high-stakes operations requiring 12 witnesses.

        Returns:
            Tuple of (can_proceed, reason).
        """
        required = (
            self.minimum_for_high_stakes if high_stakes else self.minimum_for_standard
        )
        effective = self.effective_count

        if effective >= required:
            return (True, f"Pool adequate: {effective} >= {required} witnesses")

        if high_stakes:
            return (
                False,
                f"FR117: High-stakes blocked - {effective} < {required} witnesses available",
            )

        return (False, f"Pool insufficient: {effective} < {required} witnesses")


@runtime_checkable
class WitnessPoolMonitorProtocol(Protocol):
    """Protocol for witness pool monitoring (FR117).

    Constitutional Constraint (FR117):
    If witness pool <12, continue only for low-stakes events;
    high-stakes events pause until restored. Degraded mode publicly surfaced.

    Implementations must:
    1. Track available witness count
    2. Account for excluded witnesses
    3. Surface degraded mode when pool < 12
    4. Allow/block operations based on pool state

    Example:
        monitor: WitnessPoolMonitorProtocol = ...

        # Check pool health
        status = await monitor.get_pool_status()
        if status.is_degraded:
            # Handle degraded mode
            ...

        # Check if operation can proceed
        can_proceed, reason = status.can_perform(high_stakes=True)
        if not can_proceed:
            raise WitnessPoolDegradedError(...)
    """

    @abstractmethod
    async def get_pool_status(self) -> WitnessPoolStatus:
        """Get current witness pool status.

        Returns:
            Current pool status including degraded state.
        """
        ...

    @abstractmethod
    async def is_degraded(self) -> bool:
        """Check if pool is in degraded mode.

        Returns:
            True if pool is below high-stakes minimum (12).
        """
        ...

    @abstractmethod
    async def can_perform_operation(self, high_stakes: bool) -> bool:
        """Check if an operation type can be performed.

        Args:
            high_stakes: True for high-stakes operations.

        Returns:
            True if the operation can proceed.
        """
        ...

    @abstractmethod
    async def get_degraded_since(self) -> datetime | None:
        """Get when degraded mode started.

        Returns:
            Datetime when degraded mode started, or None if not degraded.
        """
        ...

    @abstractmethod
    async def get_available_witnesses(self) -> tuple[str, ...]:
        """Get list of available witness IDs.

        Returns:
            Tuple of witness IDs currently available for selection.
        """
        ...

    @abstractmethod
    async def get_excluded_witnesses(self) -> tuple[str, ...]:
        """Get list of excluded witness IDs.

        Returns:
            Tuple of witness IDs currently excluded due to anomalies.
        """
        ...
