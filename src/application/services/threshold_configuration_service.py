"""Threshold configuration service (Story 6.4, FR33-FR34).

This service manages constitutional threshold configuration, enforcing
floors and ensuring counter preservation.

Constitutional Constraints:
- FR33: Threshold definitions SHALL be constitutional, not operational
- FR34: Threshold changes SHALL NOT reset active counters
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy → HALT CHECK FIRST
- CT-12: Witnessing creates accountability → Threshold changes must be witnessed
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.threshold_configuration import ThresholdRepositoryProtocol
from src.domain.errors.threshold import (
    ConstitutionalFloorViolationError,
    ThresholdNotFoundError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.threshold import (
    THRESHOLD_UPDATED_EVENT_TYPE,
    ThresholdUpdatedEventPayload,
)
from src.domain.models.constitutional_threshold import ConstitutionalThreshold
from src.domain.primitives.constitutional_thresholds import (
    CONSTITUTIONAL_THRESHOLD_REGISTRY,
)


logger = logging.getLogger(__name__)


class ThresholdConfigurationService:
    """Service for managing constitutional threshold configuration.

    This service provides operations to:
    - Get threshold definitions with current values
    - Validate proposed threshold changes against constitutional floors
    - Update thresholds while preserving counter state (FR34)
    - Write witnessed events for threshold changes (CT-12)

    Constitutional Constraints:
    - FR33: Enforces constitutional floors on all threshold changes
    - FR34: NEVER resets counters - this service has NO access to counter state
    - NFR39: Rejects all below-floor values
    - CT-11: Checks halt state before every operation

    CRITICAL FR34 Note:
    Counter preservation is enforced architecturally. This service
    has NO dependency on BreachRepository, EscalationRepository, or
    any other repository that maintains counters. There is no code
    path from threshold update to counter reset.
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        repository: Optional[ThresholdRepositoryProtocol] = None,
        event_writer = None,  # Optional EventWriterService
    ) -> None:
        """Initialize the threshold configuration service.

        Args:
            halt_checker: Halt state checker (CT-11 compliance).
            repository: Optional repository for threshold overrides.
                       If None, uses registry defaults only.
            event_writer: Optional EventWriterService for witnessed events.
        """
        self._halt_checker = halt_checker
        self._repository = repository
        self._event_writer = event_writer
        self._registry = CONSTITUTIONAL_THRESHOLD_REGISTRY

    async def get_threshold(self, name: str) -> ConstitutionalThreshold:
        """Get a threshold by name with current value.

        HALT CHECK FIRST (CT-11)

        Args:
            name: The threshold name to look up.

        Returns:
            The ConstitutionalThreshold with current value.
            If a repository override exists, returns threshold with
            the overridden current_value.

        Raises:
            SystemHaltedError: If system is halted.
            ThresholdNotFoundError: If threshold not found.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - threshold access blocked")

        # Get from registry
        try:
            threshold = self._registry.get_threshold(name)
        except KeyError as exc:
            raise ThresholdNotFoundError(name) from exc

        # Check for override
        if self._repository:
            override = await self._repository.get_threshold_override(name)
            if override is not None:
                # Create new threshold with overridden value
                threshold = ConstitutionalThreshold(
                    threshold_name=threshold.threshold_name,
                    constitutional_floor=threshold.constitutional_floor,
                    current_value=override,
                    is_constitutional=threshold.is_constitutional,
                    description=threshold.description,
                    fr_reference=threshold.fr_reference,
                )

        return threshold

    async def get_all_thresholds(self) -> list[ConstitutionalThreshold]:
        """Get all constitutional thresholds with current values.

        HALT CHECK FIRST (CT-11)

        Returns:
            List of all ConstitutionalThreshold instances.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - threshold access blocked")

        thresholds = []
        for threshold in self._registry.thresholds:
            # Get with any overrides applied
            thresholds.append(await self.get_threshold(threshold.threshold_name))

        return thresholds

    async def validate_threshold_value(
        self, name: str, proposed_value: int | float
    ) -> bool:
        """Validate a proposed threshold value against its floor.

        HALT CHECK FIRST (CT-11)

        Args:
            name: The threshold name.
            proposed_value: The value to validate.

        Returns:
            True if the value is valid (>= floor).

        Raises:
            SystemHaltedError: If system is halted.
            ConstitutionalFloorViolationError: If below floor (FR33).
            ThresholdNotFoundError: If threshold not found.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - threshold validation blocked")

        # Get threshold definition
        try:
            threshold = self._registry.get_threshold(name)
        except KeyError as exc:
            raise ThresholdNotFoundError(name) from exc

        # Validate against floor (FR33, NFR39)
        if proposed_value < threshold.constitutional_floor:
            logger.warning(
                "threshold_floor_violation",
                extra={
                    "threshold_name": name,
                    "attempted_value": proposed_value,
                    "constitutional_floor": threshold.constitutional_floor,
                    "fr_reference": threshold.fr_reference,
                },
            )
            raise ConstitutionalFloorViolationError(
                threshold_name=name,
                attempted_value=proposed_value,
                constitutional_floor=threshold.constitutional_floor,
                fr_reference=threshold.fr_reference,
            )

        logger.info(
            "threshold_validation_passed",
            extra={
                "threshold_name": name,
                "proposed_value": proposed_value,
                "floor": threshold.constitutional_floor,
            },
        )
        return True

    async def update_threshold(
        self, name: str, new_value: int | float, updated_by: str
    ) -> ConstitutionalThreshold:
        """Update a threshold value without resetting counters (FR33, FR34).

        HALT CHECK FIRST (CT-11)
        WRITES WITNESSED EVENT (CT-12)

        CRITICAL FR34 CONSTRAINT:
        Threshold changes SHALL NOT reset active counters.
        This method ONLY updates the threshold value. It has NO access
        to breach repositories, escalation repositories, or any counter state.

        Counter preservation is enforced architecturally:
        - This service has no dependency on repositories with counters
        - Counter state lives in separate repositories (BreachRepository, etc.)
        - There is no code path from threshold update to counter reset

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
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - threshold update blocked")

        # Get current threshold
        threshold = await self.get_threshold(name)

        # Validate against floor (FR33, NFR39)
        if new_value < threshold.constitutional_floor:
            logger.warning(
                "threshold_update_rejected",
                extra={
                    "threshold_name": name,
                    "attempted_value": new_value,
                    "constitutional_floor": threshold.constitutional_floor,
                    "fr_reference": threshold.fr_reference,
                    "updated_by": updated_by,
                },
            )
            raise ConstitutionalFloorViolationError(
                threshold_name=name,
                attempted_value=new_value,
                constitutional_floor=threshold.constitutional_floor,
                fr_reference=threshold.fr_reference,
            )

        previous_value = threshold.current_value

        # Create updated threshold (does NOT touch any counters - FR34)
        updated = ConstitutionalThreshold(
            threshold_name=threshold.threshold_name,
            constitutional_floor=threshold.constitutional_floor,
            current_value=new_value,
            is_constitutional=True,
            description=threshold.description,
            fr_reference=threshold.fr_reference,
        )

        # Save override if repository is available
        if self._repository:
            await self._repository.save_threshold_override(name, new_value)

        # Write witnessed event if EventWriter provided (CT-12)
        if self._event_writer:
            now = datetime.now(timezone.utc)
            payload = ThresholdUpdatedEventPayload(
                threshold_name=name,
                previous_value=previous_value,
                new_value=new_value,
                constitutional_floor=threshold.constitutional_floor,
                fr_reference=threshold.fr_reference,
                updated_at=now,
                updated_by=updated_by,
            )
            await self._event_writer.write_event(
                event_type=THRESHOLD_UPDATED_EVENT_TYPE,
                payload=payload.to_dict(),
                agent_id=updated_by,
                local_timestamp=now,
            )

        logger.info(
            "threshold_updated",
            extra={
                "threshold_name": name,
                "previous_value": previous_value,
                "new_value": new_value,
                "floor": threshold.constitutional_floor,
                "updated_by": updated_by,
            },
        )

        return updated
