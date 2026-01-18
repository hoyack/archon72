"""Threshold configuration port (Story 6.4, FR33-FR34).

This module defines the protocol for threshold configuration operations.

Constitutional Constraints:
- FR33: Threshold definitions SHALL be constitutional, not operational
- FR34: Threshold changes SHALL NOT reset active counters
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy → HALT CHECK FIRST
"""

from __future__ import annotations

from typing import Protocol

from src.domain.models.constitutional_threshold import ConstitutionalThreshold


class ThresholdConfigurationProtocol(Protocol):
    """Protocol for threshold configuration operations.

    All implementations MUST:
    - Check halt state before every operation (CT-11)
    - Enforce constitutional floors (FR33)
    - Never reset counters on threshold changes (FR34)

    Constitutional Constraints:
    - FR33: Thresholds are constitutional, not operational
    - FR34: Changes SHALL NOT reset counters
    - NFR39: No value below constitutional floors
    """

    async def get_threshold(self, name: str) -> ConstitutionalThreshold:
        """Get a threshold by name.

        HALT CHECK FIRST (CT-11)

        Args:
            name: The threshold name to look up.

        Returns:
            The ConstitutionalThreshold with current value.

        Raises:
            SystemHaltedError: If system is halted.
            ThresholdNotFoundError: If threshold not found.
        """
        ...

    async def get_all_thresholds(self) -> list[ConstitutionalThreshold]:
        """Get all constitutional thresholds.

        HALT CHECK FIRST (CT-11)

        Returns:
            List of all ConstitutionalThreshold instances.

        Raises:
            SystemHaltedError: If system is halted.
        """
        ...

    async def validate_threshold_value(
        self, name: str, proposed_value: int | float
    ) -> bool:
        """Validate a proposed threshold value.

        HALT CHECK FIRST (CT-11)

        Args:
            name: The threshold name.
            proposed_value: The value to validate.

        Returns:
            True if the value is valid (>= floor).

        Raises:
            SystemHaltedError: If system is halted.
            ConstitutionalFloorViolationError: If below floor.
            ThresholdNotFoundError: If threshold not found.
        """
        ...

    async def update_threshold(
        self, name: str, new_value: int | float, updated_by: str
    ) -> ConstitutionalThreshold:
        """Update a threshold value.

        HALT CHECK FIRST (CT-11)
        CRITICAL FR34: Does NOT reset any counters.

        Args:
            name: The threshold name.
            new_value: The new value to set.
            updated_by: Agent/Keeper ID making the update.

        Returns:
            The updated ConstitutionalThreshold.

        Raises:
            SystemHaltedError: If system is halted.
            ConstitutionalFloorViolationError: If below floor (FR33).
            ThresholdNotFoundError: If threshold not found.
        """
        ...


class ThresholdRepositoryProtocol(Protocol):
    """Protocol for threshold persistence (optional stub).

    Provides storage for threshold value overrides.
    Default values come from the constitutional registry.

    Note: This is an optional component. The ThresholdConfigurationService
    can operate without persistence by using registry defaults.
    """

    async def save_threshold_override(self, name: str, value: int | float) -> None:
        """Save a threshold override.

        Args:
            name: The threshold name.
            value: The override value (must be >= floor).
        """
        ...

    async def get_threshold_override(self, name: str) -> int | float | None:
        """Get a threshold override if one exists.

        Args:
            name: The threshold name.

        Returns:
            The override value if set, None otherwise.
        """
        ...

    async def clear_threshold_override(self, name: str) -> None:
        """Clear a threshold override (revert to default).

        Args:
            name: The threshold name.
        """
        ...
