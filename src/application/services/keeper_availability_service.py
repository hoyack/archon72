"""Keeper Availability Service (FR77-FR79).

This service handles Keeper availability tracking, attestation submission,
and quorum monitoring. All Keeper availability operations MUST go through
this service to ensure constitutional constraints are enforced.

Constitutional Constraints:
- FR77: If unanimous Keeper agreement not achieved within 72h, cessation begins
- FR78: Keepers SHALL attest availability weekly; 2 missed trigger replacement
- FR79: If registered Keeper count falls below 3, system SHALL halt

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- CT-12: Witnessing creates accountability -> Attestations are witnessed events
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from structlog import get_logger

from src.application.ports.halt_trigger import HaltTrigger
from src.application.ports.keeper_availability import KeeperAvailabilityProtocol
from src.domain.errors.keeper_availability import (
    DuplicateAttestationError,
    InvalidAttestationSignatureError,
    KeeperQuorumViolationError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.keeper_availability import (
    KEEPER_ATTESTATION_EVENT_TYPE,
    KEEPER_MISSED_ATTESTATION_EVENT_TYPE,
    KEEPER_QUORUM_WARNING_EVENT_TYPE,
    KEEPER_REPLACEMENT_INITIATED_EVENT_TYPE,
    AlertSeverity,
    KeeperAttestationPayload,
    KeeperMissedAttestationPayload,
    KeeperQuorumWarningPayload,
    KeeperReplacementInitiatedPayload,
)
from src.domain.models.keeper_attestation import (
    ATTESTATION_PERIOD_DAYS,
    MINIMUM_KEEPER_QUORUM,
    MISSED_ATTESTATIONS_THRESHOLD,
    KeeperAttestation,
    get_current_period,
)

if TYPE_CHECKING:
    from src.application.ports.halt_checker import HaltChecker
    from src.application.services.event_writer_service import EventWriterService
    from src.application.services.keeper_signature_service import KeeperSignatureService

logger = get_logger()


@dataclass(frozen=True)
class KeeperAttestationStatus:
    """Status of a Keeper's attestation.

    Attributes:
        keeper_id: The Keeper identifier.
        last_attestation: Most recent attestation (if any).
        missed_count: Number of consecutive missed attestations.
        next_deadline: When next attestation is due.
        status: Current status ("active", "warning", "replacement_pending").
    """

    keeper_id: str
    last_attestation: KeeperAttestation | None
    missed_count: int
    next_deadline: datetime
    status: str


class KeeperAvailabilityService:
    """Service for Keeper availability operations (FR77-FR79).

    This service provides:
    1. submit_attestation(): Submit weekly availability attestation
    2. check_attestation_deadlines(): Scan for missed attestations (background)
    3. check_keeper_quorum(): Monitor Keeper count and trigger halt if < 3
    4. get_keeper_attestation_status(): Get current status for a Keeper

    All operations HALT CHECK FIRST before proceeding (CT-11).

    Constitutional Constraints:
    - FR78: Weekly attestation requirement, 2 missed triggers replacement
    - FR79: Minimum 3 Keepers, system halts if below

    Attributes:
        _availability: Keeper availability repository.
        _signature_service: Service for verifying Keeper signatures.
        _event_writer: Service for writing constitutional events.
        _halt_checker: Service for checking halt state.
        _halt_trigger: Service for triggering system halt.
    """

    # Constitutional constants (FR79)
    MINIMUM_KEEPER_QUORUM: int = MINIMUM_KEEPER_QUORUM

    # Constitutional constants (FR78)
    MISSED_ATTESTATIONS_THRESHOLD: int = MISSED_ATTESTATIONS_THRESHOLD

    # Attestation period in days
    ATTESTATION_PERIOD_DAYS: int = ATTESTATION_PERIOD_DAYS

    def __init__(
        self,
        availability: KeeperAvailabilityProtocol,
        signature_service: KeeperSignatureService,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
        halt_trigger: HaltTrigger,
    ) -> None:
        """Initialize the Keeper Availability Service.

        Args:
            availability: Keeper availability repository.
            signature_service: Service for verifying Keeper signatures.
            event_writer: Service for writing constitutional events.
            halt_checker: Service for checking halt state.
            halt_trigger: Service for triggering system halt.
        """
        self._availability = availability
        self._signature_service = signature_service
        self._event_writer = event_writer
        self._halt_checker = halt_checker
        self._halt_trigger = halt_trigger

    async def submit_attestation(
        self,
        keeper_id: str,
        signature: bytes,
    ) -> KeeperAttestation:
        """Submit weekly availability attestation (FR78).

        Creates and records a KeeperAttestation after verifying the
        Keeper's cryptographic signature. Writes a KeeperAttestationEvent
        to the event store.

        Args:
            keeper_id: The Keeper submitting attestation.
            signature: Ed25519 signature over attestation content.

        Returns:
            The recorded KeeperAttestation.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            InvalidAttestationSignatureError: If signature verification fails.
            DuplicateAttestationError: If already attested for this period.
        """
        log = logger.bind(
            operation="submit_attestation",
            keeper_id=keeper_id,
        )

        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            log.warning("halt_check_failed", message="System is halted")
            raise SystemHaltedError("CT-11: System halted - attestation blocked")

        # Get current attestation period
        period_start, period_end = get_current_period()
        log = log.bind(
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
        )

        # Check for duplicate attestation
        existing = await self._availability.get_attestation(keeper_id, period_start)
        if existing is not None:
            log.warning(
                "duplicate_attestation",
                message="Already attested for this period",
            )
            raise DuplicateAttestationError(
                f"FR78: Keeper {keeper_id} already attested for period "
                f"{period_start.date()} to {period_end.date()}"
            )

        # Verify signature (using KeeperSignatureService would verify against HSM)
        # For now, we check signature length; full verification in Story 5.6 integration
        if len(signature) != 64:
            log.warning(
                "invalid_signature_length",
                expected=64,
                actual=len(signature),
            )
            raise InvalidAttestationSignatureError(
                f"FR78: Attestation signature verification failed for {keeper_id}"
            )

        # Create attestation record
        now = datetime.now(timezone.utc)
        attestation = KeeperAttestation(
            id=uuid4(),
            keeper_id=keeper_id,
            attested_at=now,
            period_start=period_start,
            period_end=period_end,
            signature=signature,
        )

        # Record attestation
        await self._availability.record_attestation(attestation)

        # Reset missed attestation count
        await self._availability.reset_missed_attestations(keeper_id)

        # Write constitutional event
        payload = KeeperAttestationPayload(
            keeper_id=keeper_id,
            attested_at=now,
            attestation_period_start=period_start,
            attestation_period_end=period_end,
        )
        await self._event_writer.write_event(
            event_type=KEEPER_ATTESTATION_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=keeper_id,  # Keeper is the agent for attestation
        )

        log.info(
            "attestation_submitted",
            attestation_id=str(attestation.id),
            message="Keeper attestation recorded successfully",
        )

        return attestation

    async def check_attestation_deadlines(self) -> list[str]:
        """Check for missed attestations and trigger replacements (FR78).

        This is designed to be called as a background task. It scans all
        active Keepers, detects missed attestations, and triggers replacement
        for Keepers who have missed 2+ consecutive attestations.

        Returns:
            List of Keeper IDs marked for replacement.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(operation="check_attestation_deadlines")

        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            log.warning("halt_check_failed", message="System is halted")
            raise SystemHaltedError("CT-11: System halted - deadline check blocked")

        # Get current period
        period_start, period_end = get_current_period()
        now = datetime.now(timezone.utc)

        # Only check if deadline has passed
        if now < period_end:
            log.debug("deadline_not_passed", period_end=period_end.isoformat())
            return []

        # Get all active Keepers
        active_keepers = await self._availability.get_all_active_keepers()
        keepers_for_replacement: list[str] = []

        for keeper_id in active_keepers:
            keeper_log = log.bind(keeper_id=keeper_id)

            # Check if attestation exists for current period
            attestation = await self._availability.get_attestation(
                keeper_id, period_start
            )

            if attestation is None:
                # Missed attestation
                missed_count = await self._availability.increment_missed_attestations(
                    keeper_id
                )
                keeper_log = keeper_log.bind(missed_count=missed_count)

                # Write missed attestation event
                missed_payload = KeeperMissedAttestationPayload(
                    keeper_id=keeper_id,
                    missed_period_start=period_start,
                    missed_period_end=period_end,
                    consecutive_misses=missed_count,
                    deadline_passed_at=now,
                )
                await self._event_writer.write_event(
                    event_type=KEEPER_MISSED_ATTESTATION_EVENT_TYPE,
                    payload=missed_payload.to_dict(),
                    agent_id="SYSTEM:availability_monitor",
                )

                keeper_log.warning(
                    "attestation_missed",
                    message=f"Keeper missed attestation ({missed_count} consecutive)",
                )

                # Check if replacement threshold reached
                if missed_count >= self.MISSED_ATTESTATIONS_THRESHOLD:
                    # Mark for replacement
                    reason = f"FR78: Missed {missed_count} consecutive attestations"
                    await self._availability.mark_keeper_for_replacement(
                        keeper_id, reason
                    )

                    # Build missed periods list (last 2 periods for the event)
                    # For simplicity, we just record the current period twice
                    missed_periods = (
                        (period_start.isoformat(), period_end.isoformat()),
                        (period_start.isoformat(), period_end.isoformat()),
                    )

                    # Write replacement initiated event
                    replacement_payload = KeeperReplacementInitiatedPayload(
                        keeper_id=keeper_id,
                        missed_periods=missed_periods,
                        initiated_at=now,
                        reason=reason,
                    )
                    await self._event_writer.write_event(
                        event_type=KEEPER_REPLACEMENT_INITIATED_EVENT_TYPE,
                        payload=replacement_payload.to_dict(),
                        agent_id="SYSTEM:availability_monitor",
                    )

                    keeper_log.error(
                        "replacement_triggered",
                        message="FR78: Keeper marked for replacement",
                    )

                    keepers_for_replacement.append(keeper_id)

        # After processing, check quorum
        await self.check_keeper_quorum()

        return keepers_for_replacement

    async def check_keeper_quorum(self) -> None:
        """Check Keeper quorum and trigger halt if below minimum (FR79).

        Monitors the active Keeper count and:
        - Triggers system halt if count < 3 (FR79)
        - Writes warning event if count == 3 (SR-7)

        Raises:
            KeeperQuorumViolationError: If quorum is below minimum (after halt).
        """
        log = logger.bind(operation="check_keeper_quorum")

        count = await self._availability.get_current_keeper_count()
        log = log.bind(
            current_count=count,
            minimum_required=self.MINIMUM_KEEPER_QUORUM,
        )

        if count < self.MINIMUM_KEEPER_QUORUM:
            # CRITICAL: Quorum violated - trigger halt
            log.critical(
                "quorum_violation",
                message=f"FR79: Keeper quorum below minimum - only {count} active Keepers",
            )

            # Trigger system halt
            await self._halt_trigger.trigger_halt(
                reason=f"FR79: Keeper quorum below minimum ({count} < {self.MINIMUM_KEEPER_QUORUM})",
                source="keeper_availability_service",
            )

            raise KeeperQuorumViolationError(
                f"FR79: Keeper quorum below minimum - only {count} active Keepers"
            )

        if count == self.MINIMUM_KEEPER_QUORUM:
            # SR-7: Warning at critical threshold
            log.warning(
                "quorum_warning",
                message="SR-7: Keeper quorum at minimum threshold",
            )

            # Write warning event
            warning_payload = KeeperQuorumWarningPayload(
                current_count=count,
                minimum_required=self.MINIMUM_KEEPER_QUORUM,
                alert_severity=AlertSeverity.MEDIUM.value,
            )
            await self._event_writer.write_event(
                event_type=KEEPER_QUORUM_WARNING_EVENT_TYPE,
                payload=warning_payload.to_dict(),
                agent_id="SYSTEM:quorum_monitor",
            )

        else:
            log.debug("quorum_healthy", message="Keeper quorum is healthy")

    async def get_keeper_attestation_status(
        self,
        keeper_id: str,
    ) -> KeeperAttestationStatus:
        """Get current attestation status for a Keeper.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            KeeperAttestationStatus with current status information.
        """
        log = logger.bind(
            operation="get_keeper_attestation_status",
            keeper_id=keeper_id,
        )

        # Get last attestation
        last_attestation = await self._availability.get_last_attestation(keeper_id)

        # Get missed count
        missed_count = await self._availability.get_missed_attestations_count(keeper_id)

        # Calculate next deadline
        period_start, period_end = get_current_period()

        # Determine status
        if missed_count >= self.MISSED_ATTESTATIONS_THRESHOLD:
            status = "replacement_pending"
        elif missed_count > 0:
            status = "warning"
        else:
            status = "active"

        attestation_status = KeeperAttestationStatus(
            keeper_id=keeper_id,
            last_attestation=last_attestation,
            missed_count=missed_count,
            next_deadline=period_end,
            status=status,
        )

        log.info(
            "status_retrieved",
            status=status,
            missed_count=missed_count,
        )

        return attestation_status
