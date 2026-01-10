"""Witness pool monitoring service (Story 6.6, FR117).

Provides monitoring of witness pool health and degraded mode surfacing.

Constitutional Constraints:
- FR117: If witness pool <12, continue only for low-stakes events;
         high-stakes events pause until restored. Degraded mode publicly surfaced.
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> Degraded events must be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - Degraded events must be witnessed
3. FAIL LOUD - Failed event write = monitoring failure
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.witness_anomaly_detector import WitnessAnomalyDetectorProtocol
from src.application.ports.witness_pool import WitnessPoolProtocol
from src.application.ports.witness_pool_monitor import (
    MINIMUM_WITNESSES_HIGH_STAKES,
    MINIMUM_WITNESSES_STANDARD,
    WitnessPoolMonitorProtocol,
    WitnessPoolStatus,
)
from src.domain.errors.witness_anomaly import WitnessPoolDegradedError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.witness_anomaly import (
    WITNESS_POOL_DEGRADED_EVENT_TYPE,
    WitnessPoolDegradedEventPayload,
)


class WitnessPoolMonitoringService:
    """Service for witness pool monitoring (FR117).

    Monitors witness pool health, accounting for excluded witnesses,
    and surfaces degraded mode when pool falls below operational minimums.

    Constitutional Pattern:
    1. HALT CHECK FIRST at every public operation (CT-11)
    2. Calculate effective pool size (available - excluded)
    3. Determine degraded state (effective < 12)
    4. Create degraded events for witnessing (CT-12)
    5. Block/allow operations based on pool state

    Example:
        service = WitnessPoolMonitoringService(
            halt_checker=halt_checker,
            witness_pool=pool,
            anomaly_detector=detector,
        )

        # Check pool health
        status = await service.check_pool_health()
        if status.is_degraded:
            # Handle degraded mode
            payload = await service.handle_pool_degraded(status)

        # Check if high-stakes operation can proceed
        can_proceed, reason = await service.can_proceed_with_operation(high_stakes=True)
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        witness_pool: WitnessPoolProtocol,
        anomaly_detector: Optional[WitnessAnomalyDetectorProtocol] = None,
    ) -> None:
        """Initialize the witness pool monitoring service.

        Args:
            halt_checker: For CT-11 halt check before operations.
            witness_pool: For getting available witnesses.
            anomaly_detector: For getting excluded witnesses (optional).
        """
        self._halt_checker = halt_checker
        self._witness_pool = witness_pool
        self._anomaly_detector = anomaly_detector
        self._degraded_since: Optional[datetime] = None

    async def check_pool_health(self) -> WitnessPoolStatus:
        """Check current witness pool health (FR117).

        Gets the current pool size, accounts for excluded witnesses,
        and determines if degraded mode should be surfaced.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Get available witnesses from pool
        3. Get excluded witnesses from anomaly detector
        4. Calculate effective count
        5. Determine degraded state

        Returns:
            WitnessPoolStatus with current pool state.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - pool health check blocked")

        # Get available witnesses
        available_witnesses = await self._witness_pool.get_ordered_active_witnesses()
        available_count = len(available_witnesses)

        # Get excluded witnesses if anomaly detector available
        excluded_witnesses: tuple[str, ...] = ()
        if self._anomaly_detector:
            excluded_pairs = await self._anomaly_detector.get_excluded_pairs()
            # Extract unique witness IDs from excluded pairs
            # Pair format: "ID1:ID2" where IDs may contain colons
            excluded_set: set[str] = set()
            for pair_key in excluded_pairs:
                # Smart split for pair keys
                if pair_key.count(":") == 1:
                    parts = pair_key.split(":")
                else:
                    # Find the middle split point for complex IDs
                    mid_point = len(pair_key) // 2
                    left_colon = pair_key.rfind(":", 0, mid_point + 1)
                    right_colon = pair_key.find(":", mid_point)
                    if left_colon != -1 and right_colon != -1:
                        split_pos = left_colon if (mid_point - left_colon) <= (right_colon - mid_point) else right_colon
                        parts = [pair_key[:split_pos], pair_key[split_pos + 1:]]
                    else:
                        parts = [pair_key]
                excluded_set.update(parts)
            excluded_witnesses = tuple(sorted(excluded_set))

        # Calculate effective count
        effective_count = available_count - len(excluded_witnesses)

        # Determine if degraded
        is_degraded = effective_count < MINIMUM_WITNESSES_HIGH_STAKES

        # Track degraded start time
        if is_degraded and self._degraded_since is None:
            self._degraded_since = datetime.now(timezone.utc)
        elif not is_degraded:
            self._degraded_since = None

        return WitnessPoolStatus(
            available_count=available_count,
            excluded_witnesses=excluded_witnesses,
            is_degraded=is_degraded,
            degraded_since=self._degraded_since,
            minimum_for_standard=MINIMUM_WITNESSES_STANDARD,
            minimum_for_high_stakes=MINIMUM_WITNESSES_HIGH_STAKES,
        )

    async def handle_pool_degraded(
        self,
        status: WitnessPoolStatus,
        operation_type: str = "high_stakes",
    ) -> WitnessPoolDegradedEventPayload:
        """Handle degraded pool state by creating event payload (FR117, CT-12).

        Creates a WitnessPoolDegradedEventPayload for witnessing when
        pool falls below minimum.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Determine if blocking (high-stakes) or continuing (low-stakes)
        3. Create event payload for witnessing (CT-12)

        Args:
            status: Current pool status from check_pool_health().
            operation_type: Type of operation affected ("high_stakes" or "standard").

        Returns:
            WitnessPoolDegradedEventPayload for the degraded event.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - degraded handling blocked")

        # Determine if blocking based on operation type
        is_high_stakes = operation_type == "high_stakes"
        minimum_required = (
            MINIMUM_WITNESSES_HIGH_STAKES if is_high_stakes else MINIMUM_WITNESSES_STANDARD
        )
        is_blocking = is_high_stakes and status.effective_count < minimum_required

        # Build reason
        if status.excluded_witnesses:
            reason = (
                f"Pool degraded: {status.effective_count} effective witnesses "
                f"({status.available_count} available, {len(status.excluded_witnesses)} excluded)"
            )
        else:
            reason = f"Pool degraded: {status.effective_count} witnesses available"

        now = datetime.now(timezone.utc)

        return WitnessPoolDegradedEventPayload(
            available_witnesses=status.available_count,
            minimum_required=minimum_required,
            operation_type=operation_type,
            is_blocking=is_blocking,
            degraded_at=status.degraded_since or now,
            excluded_witnesses=status.excluded_witnesses,
            reason=reason,
        )

    async def can_proceed_with_operation(
        self,
        high_stakes: bool,
    ) -> tuple[bool, str]:
        """Check if an operation can proceed given pool state (FR117).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Check pool health
        3. Return (can_proceed, reason)

        Args:
            high_stakes: True for high-stakes operations (require 12 witnesses).

        Returns:
            Tuple of (can_proceed, reason).

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - operation check blocked")

        status = await self.check_pool_health()
        return status.can_perform(high_stakes)

    async def is_degraded(self) -> bool:
        """Check if pool is currently in degraded mode (FR117).

        Returns:
            True if pool is below high-stakes minimum (12).

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - degraded check blocked")

        status = await self.check_pool_health()
        return status.is_degraded

    async def get_degraded_since(self) -> Optional[datetime]:
        """Get when degraded mode started.

        Returns:
            Datetime when degraded mode started, or None if not degraded.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - degraded since check blocked")

        return self._degraded_since

    async def require_healthy_pool_for_high_stakes(self) -> None:
        """Require healthy pool for high-stakes operations (FR117).

        Convenience method that raises WitnessPoolDegradedError if
        pool cannot support high-stakes operations.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            WitnessPoolDegradedError: If pool cannot support high-stakes.
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - pool requirement check blocked")

        status = await self.check_pool_health()
        can_proceed, reason = status.can_perform(high_stakes=True)

        if not can_proceed:
            raise WitnessPoolDegradedError(
                available=status.effective_count,
                minimum_required=MINIMUM_WITNESSES_HIGH_STAKES,
                excluded_count=len(status.excluded_witnesses),
                operation_type="high_stakes",
            )
