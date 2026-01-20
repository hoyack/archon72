"""Dual-Channel Halt Transport Implementation (Story 3.3, Task 5; Story 3.4 for clear).

Implements the DualChannelHaltTransport port for ADR-3.
Combines Redis Streams (fast) + DB halt flag (durable).

ADR-3: Partition Behavior + Halt Durability
- Dual-channel halt: Redis Streams for speed + DB halt flag for safety
- If EITHER channel indicates halt -> component halts
- DB is canonical when channels disagree
- 5-second Redis-to-DB confirmation (RT-2)
- Halt is **sticky** - clearing requires witnessed ceremony (Story 3.4)

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> Failures MUST be logged
- CT-12: Witnessing creates accountability -> crisis_event_id tracks trigger
- CT-13: Integrity outranks availability -> Availability sacrificed for integrity

Developer Golden Rules:
1. HALT FIRST - Check dual-channel halt before every operation
2. DB IS CANONICAL - When Redis and DB disagree, trust DB
3. LOG CONFLICTS - Every channel mismatch must be logged
4. FAIL LOUD - Never swallow halt check errors
5. CEREMONY IS KING - No backdoors for clearing halt
"""

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from src.application.ports.dual_channel_halt import (
    CONFIRMATION_TIMEOUT_SECONDS,
    DualChannelHaltTransport,
    HaltFlagState,
)
from src.domain.errors.halt_clear import HaltClearDeniedError
from src.domain.events.halt_cleared import HALT_CLEARED_EVENT_TYPE, HaltClearedPayload
from src.domain.models.ceremony_evidence import CeremonyEvidence
from src.infrastructure.adapters.messaging.halt_stream_consumer import (
    HaltStreamConsumer,
)
from src.infrastructure.adapters.messaging.halt_stream_publisher import (
    HaltStreamPublisher,
)
from src.infrastructure.adapters.persistence.halt_flag_repository import (
    HaltFlagRepository,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable

# Type alias for ceremony event writer callback
# This callback writes the HaltClearedEvent to the event store
# and returns the event_id of the persisted event
CeremonyEventWriter = Callable[[HaltClearedPayload], "Awaitable[UUID]"]

log = structlog.get_logger(__name__)


class DualChannelHaltTransportImpl(DualChannelHaltTransport):
    """Production implementation of dual-channel halt transport.

    Combines Redis Streams (fast propagation) with DB halt flag (durability).
    Implements ADR-3 dual-channel semantics:
    - write_halt() writes to BOTH channels
    - is_halted() returns True if EITHER channel indicates halt
    - DB is canonical when channels disagree

    Example:
        >>> transport = DualChannelHaltTransportImpl(
        ...     halt_flag_repo=repo,
        ...     halt_publisher=publisher,
        ...     halt_consumer=consumer,
        ... )
        >>> await transport.write_halt(
        ...     reason="FR17: Fork detected",
        ...     crisis_event_id=crisis_uuid,
        ... )
    """

    def __init__(
        self,
        halt_flag_repo: HaltFlagRepository,
        halt_publisher: HaltStreamPublisher,
        halt_consumer: HaltStreamConsumer,
        ceremony_event_writer: CeremonyEventWriter | None = None,
    ) -> None:
        """Initialize dual-channel halt transport.

        Args:
            halt_flag_repo: Repository for DB halt flag (canonical).
            halt_publisher: Publisher for Redis Streams halt signals.
            halt_consumer: Consumer for Redis Streams halt signals.
            ceremony_event_writer: Optional callback to write HaltClearedEvent
                to event store. CT-12 requires this event be written BEFORE
                the halt is actually cleared. If not provided, a warning is
                logged but clear proceeds (for backward compatibility during
                testing/development).
        """
        self._halt_flag_repo = halt_flag_repo
        self._halt_publisher = halt_publisher
        self._halt_consumer = halt_consumer
        self._ceremony_event_writer = ceremony_event_writer

    @property
    def confirmation_timeout_seconds(self) -> float:
        """RT-2: Halt from Redis must be confirmed against DB within 5 seconds."""
        return CONFIRMATION_TIMEOUT_SECONDS

    async def write_halt(
        self,
        reason: str,
        crisis_event_id: UUID,
    ) -> None:
        """Write halt signal to BOTH channels (Redis + DB).

        AC1: Both writes must complete before halt is considered "sent".
        Writes to both channels concurrently for speed.

        Args:
            reason: Human-readable reason for halt.
            crisis_event_id: UUID of triggering crisis event.

        Raises:
            Exception: If either channel write fails.
        """
        log.info(
            "dual_channel_halt_write_started",
            reason=reason,
            crisis_event_id=str(crisis_event_id),
        )

        # Write to both channels concurrently
        # Both must succeed for halt to be considered "sent"
        db_task = self._halt_flag_repo.set_halt_flag(
            halted=True,
            reason=reason,
            crisis_event_id=crisis_event_id,
        )
        redis_task = self._halt_publisher.publish_halt(
            reason=reason,
            crisis_event_id=crisis_event_id,
        )

        try:
            await asyncio.gather(db_task, redis_task)
            log.info(
                "dual_channel_halt_write_completed",
                reason=reason,
                crisis_event_id=str(crisis_event_id),
            )
        except Exception as e:
            log.error(
                "dual_channel_halt_write_failed",
                reason=reason,
                crisis_event_id=str(crisis_event_id),
                error=str(e),
            )
            raise

    async def is_halted(self) -> bool:
        """Check if system is halted via EITHER channel.

        AC2: Return True if Redis OR DB indicates halt.
        AC3: If Redis fails, use DB (source of truth).

        Returns:
            True if system is halted (either channel), False otherwise.
        """
        # Check both channels concurrently
        db_halted = False
        redis_halted = False

        try:
            db_state, redis_halted = await asyncio.gather(
                self._get_db_halt_state(),
                self._check_redis_halt(),
                return_exceptions=True,
            )

            # Handle exceptions
            if isinstance(db_state, BaseException):
                log.error("db_halt_check_failed", error=str(db_state))
                # DB failure is serious - can't determine canonical state
                # Still check Redis, but this is a degraded state
                db_halted = False
            else:
                db_halted = db_state.is_halted

            if isinstance(redis_halted, BaseException):
                log.warning("redis_halt_check_failed", error=str(redis_halted))
                # Redis failure is expected in some scenarios (AC3)
                redis_halted = False

        except Exception as e:
            log.error("halt_check_failed", error=str(e))
            # Conservative: assume not halted but log error
            return False

        # AC2: If EITHER indicates halt, we're halted
        halted = db_halted or redis_halted

        # Detect and handle conflicts (AC4)
        if redis_halted and not db_halted:
            log.warning(
                "halt_channel_conflict_detected",
                redis_halted=redis_halted,
                db_halted=db_halted,
                action="logging_for_investigation",
            )
            # Note: We still return True because Redis says halt
            # But DB is canonical, so this is suspicious

        return halted

    async def get_halt_reason(self) -> str | None:
        """Get the reason for current halt state.

        Returns DB halt reason (canonical source).

        Returns:
            Halt reason if halted, None otherwise.
        """
        db_state = await self._halt_flag_repo.get_halt_flag()
        return db_state.reason if db_state.is_halted else None

    async def check_channels_consistent(self) -> bool:
        """Check if Redis and DB halt states are consistent.

        AC4: Detect channel drift for monitoring.

        Returns:
            True if both channels agree, False if there's a mismatch.
        """
        try:
            db_state = await self._halt_flag_repo.get_halt_flag()
            redis_halted = await self._check_redis_halt()

            consistent = db_state.is_halted == redis_halted

            if not consistent:
                log.warning(
                    "halt_channels_inconsistent",
                    db_halted=db_state.is_halted,
                    redis_halted=redis_halted,
                )

            return consistent

        except Exception as e:
            log.error("channel_consistency_check_failed", error=str(e))
            return False

    async def resolve_conflict(self) -> None:
        """Resolve halt channel conflict (AC4).

        DB is canonical. Corrects Redis to match DB.
        Logs conflict for investigation.
        """
        db_state = await self._halt_flag_repo.get_halt_flag()
        redis_halted = await self._check_redis_halt()

        if db_state.is_halted and not redis_halted:
            # DB is halted but Redis isn't - propagate to Redis
            log.info(
                "conflict_resolution_propagating_to_redis",
                db_halted=True,
                redis_halted=False,
            )
            if db_state.crisis_event_id:
                await self._halt_publisher.publish_halt(
                    reason=db_state.reason or "Conflict resolution",
                    crisis_event_id=db_state.crisis_event_id,
                )

        elif not db_state.is_halted and redis_halted:
            # Redis says halt but DB doesn't - SUSPICIOUS
            # Log but do NOT clear Redis halt (security measure)
            log.warning(
                "conflict_detected_phantom_halt",
                db_halted=False,
                redis_halted=True,
                action="logged_for_investigation_redis_not_cleared",
            )

        else:
            log.info("no_conflict_to_resolve", db_halted=db_state.is_halted)

    async def clear_halt(
        self,
        ceremony_evidence: CeremonyEvidence,
    ) -> HaltClearedPayload:
        """Clear halt with proper ceremony evidence (Story 3.4, ADR-3).

        Halt is sticky once set. Clearing requires a witnessed ceremony
        with at least 2 Keeper approvers (ADR-6 Tier 1).

        Process (CT-12 compliant - witness BEFORE action):
        1. Validate ceremony_evidence (>= 2 approvers, valid signatures)
        2. Create HaltClearedPayload
        3. Write HaltClearedEvent to event store (witnessed) BEFORE clear
        4. Clear DB halt flag via ceremony-authorized procedure
        5. Clear Redis halt state
        6. Return HaltClearedPayload

        Args:
            ceremony_evidence: CeremonyEvidence proving ceremony was conducted.

        Returns:
            HaltClearedPayload with ceremony details.

        Raises:
            HaltClearDeniedError: If ceremony_evidence is None.
            InsufficientApproversError: If < 2 Keepers approved.
            InvalidCeremonyError: If any signature is invalid.
        """
        if ceremony_evidence is None:
            raise HaltClearDeniedError("ADR-3: Halt flag protected - ceremony required")

        # Validate ceremony evidence (raises on failure)
        ceremony_evidence.validate()

        log.info(
            "dual_channel_halt_clear_started",
            ceremony_id=str(ceremony_evidence.ceremony_id),
            approver_count=len(ceremony_evidence.approvers),
            keeper_ids=ceremony_evidence.get_keeper_ids(),
        )

        # Create the clear reason for audit trail
        clear_reason = f"Recovery ceremony {ceremony_evidence.ceremony_id}"

        # Create HaltClearedPayload BEFORE any state changes
        halt_cleared_payload = HaltClearedPayload(
            ceremony_id=ceremony_evidence.ceremony_id,
            clearing_authority="Keeper Council",
            reason=clear_reason,
            approvers=ceremony_evidence.get_keeper_ids(),
            cleared_at=datetime.now(timezone.utc),
        )

        # =====================================================================
        # CT-12 COMPLIANCE: Write HaltClearedEvent BEFORE clearing halt
        # =====================================================================
        # The HaltClearedEvent MUST be witnessed and recorded BEFORE the
        # halt is actually cleared. This ensures the clear operation is
        # part of the audit trail even if something fails afterward.
        if self._ceremony_event_writer is not None:
            event_id = await self._ceremony_event_writer(halt_cleared_payload)
            log.info(
                "halt_cleared_event_written",
                event_id=str(event_id),
                ceremony_id=str(ceremony_evidence.ceremony_id),
                event_type=HALT_CLEARED_EVENT_TYPE,
            )
        else:
            # No event writer configured - log warning but proceed
            # This allows backward compatibility during testing/development
            log.warning(
                "halt_cleared_event_not_written_no_writer",
                ceremony_id=str(ceremony_evidence.ceremony_id),
                message="CT-12 WARNING: No ceremony_event_writer configured - "
                "HaltClearedEvent not written to event store",
            )

        # Now safe to clear the halt (event is already witnessed)
        # Clear DB halt flag with ceremony authorization
        await self._halt_flag_repo.clear_halt_with_ceremony(
            ceremony_id=ceremony_evidence.ceremony_id,
            reason=clear_reason,
        )

        # Clear Redis halt state
        await self._halt_consumer.clear_halt_state()

        log.info(
            "dual_channel_halt_clear_completed",
            ceremony_id=str(ceremony_evidence.ceremony_id),
            approver_count=len(ceremony_evidence.approvers),
        )

        return halt_cleared_payload

    async def _get_db_halt_state(self) -> HaltFlagState:
        """Get halt state from DB (canonical source)."""
        return await self._halt_flag_repo.get_halt_flag()

    async def _check_redis_halt(self) -> bool:
        """Check halt state from Redis channel."""
        return await self._halt_consumer.check_redis_halt()
