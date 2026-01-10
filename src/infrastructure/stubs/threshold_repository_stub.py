"""Threshold repository stub (Story 6.4, FR33-FR34).

This module provides an in-memory stub implementation of the
ThresholdRepositoryProtocol for development and testing.

DEV MODE WARNING:
This stub stores threshold overrides in memory only. All data
is lost when the process restarts. Use only for development
and testing, not production.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.application.ports.threshold_configuration import ThresholdRepositoryProtocol


logger = logging.getLogger(__name__)


class ThresholdRepositoryStub(ThresholdRepositoryProtocol):
    """In-memory stub implementation of ThresholdRepositoryProtocol.

    Provides storage for threshold value overrides during development
    and testing. Uses a simple dictionary for storage.

    DEV MODE WARNING:
    This stub stores data in memory only. All data is lost when
    the process restarts. Use only for development and testing.

    Note: This stub does NOT enforce constitutional floors. Floor
    enforcement is the responsibility of ThresholdConfigurationService.
    """

    def __init__(self) -> None:
        """Initialize the threshold repository stub.

        Logs a DEV MODE watermark warning on initialization.
        """
        self._overrides: dict[str, int | float] = {}
        logger.warning(
            "threshold_repository_stub_initialized",
            extra={
                "mode": "DEV",
                "warning": "In-memory storage - data lost on restart",
            },
        )

    async def save_threshold_override(
        self, name: str, value: int | float
    ) -> None:
        """Save a threshold override.

        Args:
            name: The threshold name.
            value: The override value.

        Note: This method does NOT validate against constitutional floors.
        Floor validation is the responsibility of ThresholdConfigurationService.
        """
        self._overrides[name] = value
        logger.debug(
            "threshold_override_saved",
            extra={
                "threshold_name": name,
                "value": value,
            },
        )

    async def get_threshold_override(
        self, name: str
    ) -> Optional[int | float]:
        """Get a threshold override if one exists.

        Args:
            name: The threshold name.

        Returns:
            The override value if set, None otherwise.
        """
        value = self._overrides.get(name)
        if value is not None:
            logger.debug(
                "threshold_override_retrieved",
                extra={
                    "threshold_name": name,
                    "value": value,
                },
            )
        return value

    async def clear_threshold_override(self, name: str) -> None:
        """Clear a threshold override (revert to default).

        Args:
            name: The threshold name.
        """
        if name in self._overrides:
            del self._overrides[name]
            logger.debug(
                "threshold_override_cleared",
                extra={
                    "threshold_name": name,
                },
            )

    def clear(self) -> None:
        """Clear all overrides (for test cleanup).

        This method is synchronous for easy test fixture cleanup.
        """
        self._overrides.clear()
        logger.debug("threshold_repository_cleared")

    @property
    def override_count(self) -> int:
        """Get the number of stored overrides.

        Returns:
            Number of threshold overrides currently stored.
        """
        return len(self._overrides)

    def has_override(self, name: str) -> bool:
        """Check if an override exists for a threshold.

        Args:
            name: The threshold name.

        Returns:
            True if an override exists, False otherwise.
        """
        return name in self._overrides
