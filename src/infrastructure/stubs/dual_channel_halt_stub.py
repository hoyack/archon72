"""Dual-Channel Halt Transport Stub for testing/development (Story 3.3, Task 6; Story 3.4 for clear).

Implements the DualChannelHaltTransport port for testing scenarios.
Simulates dual-channel behavior without actual Redis/DB connections.

ADR-3: Partition Behavior + Halt Durability
- Simulates dual-channel halt for testing
- Allows independent control of DB/Redis channel states
- Supports failure simulation for edge case testing
- Halt is **sticky** - clearing requires ceremony (Story 3.4)

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> Failures MUST be logged
- CT-12: Witnessing creates accountability -> crisis_event_id tracks trigger
- CT-13: Integrity outranks availability -> Availability sacrificed for integrity

Usage:
    # Basic usage
    stub = DualChannelHaltTransportStub()
    await stub.write_halt(
        reason="FR17: Fork detected",
        crisis_event_id=crisis_uuid,
    )
    assert await stub.is_halted() is True

    # Simulate channel inconsistency
    stub = DualChannelHaltTransportStub()
    stub.set_db_halted(True, "DB halt only")
    stub.set_redis_halted(False)
    assert await stub.check_channels_consistent() is False

    # Simulate failures
    stub.set_db_failure(True)
    stub.set_redis_failure(True)

    # Clear halt with ceremony (Story 3.4)
    evidence = CeremonyEvidence(...)
    payload = await stub.clear_halt(evidence)
"""

from datetime import datetime, timezone
from uuid import UUID

import structlog

from src.application.ports.dual_channel_halt import (
    CONFIRMATION_TIMEOUT_SECONDS,
    DualChannelHaltTransport,
)
from src.domain.errors.halt_clear import HaltClearDeniedError
from src.domain.events.halt_cleared import HaltClearedPayload
from src.domain.models.ceremony_evidence import CeremonyEvidence

log = structlog.get_logger(__name__)


class DualChannelHaltTransportStub(DualChannelHaltTransport):
    """Stub implementation of dual-channel halt transport for testing.

    Simulates dual-channel behavior (Redis + DB) for testing without
    actual infrastructure dependencies.

    Features:
    - Independent control of DB/Redis channel states
    - Failure simulation for edge case testing
    - Trigger count tracking for verification
    - Reset capability for test isolation

    Example:
        >>> stub = DualChannelHaltTransportStub()
        >>> await stub.write_halt("Test", uuid4())
        >>> await stub.is_halted()
        True
    """

    def __init__(self) -> None:
        """Initialize the stub with clean state."""
        self._db_halted: bool = False
        self._redis_halted: bool = False
        self._halt_reason: str | None = None
        self._crisis_event_id: UUID | None = None
        self._trigger_count: int = 0
        self._db_failure: bool = False
        self._redis_failure: bool = False

    @property
    def confirmation_timeout_seconds(self) -> float:
        """RT-2: Halt from Redis must be confirmed against DB within 5 seconds."""
        return CONFIRMATION_TIMEOUT_SECONDS

    async def write_halt(
        self,
        reason: str,
        crisis_event_id: UUID,
    ) -> None:
        """Write halt signal to BOTH channels (simulated).

        Args:
            reason: Human-readable reason for halt.
            crisis_event_id: UUID of triggering crisis event.
        """
        log.info(
            "stub_dual_channel_halt_write",
            reason=reason,
            crisis_event_id=str(crisis_event_id),
        )

        self._db_halted = True
        self._redis_halted = True
        self._halt_reason = reason
        self._crisis_event_id = crisis_event_id
        self._trigger_count += 1

    async def is_halted(self) -> bool:
        """Check if system is halted via EITHER channel.

        Returns True if Redis OR DB indicates halt.
        Falls back to DB if Redis fails, uses Redis if DB fails.

        Returns:
            True if system is halted (either channel), False otherwise.
        """
        db_halted = False
        redis_halted = False

        if not self._db_failure:
            db_halted = self._db_halted
        else:
            log.warning("stub_db_failure_simulated")

        if not self._redis_failure:
            redis_halted = self._redis_halted
        else:
            log.warning("stub_redis_failure_simulated")

        return db_halted or redis_halted

    async def get_halt_reason(self) -> str | None:
        """Get the reason for current halt state.

        Returns DB halt reason (canonical source).

        Returns:
            Halt reason if halted, None otherwise.
        """
        if self._db_halted:
            return self._halt_reason
        return None

    async def check_channels_consistent(self) -> bool:
        """Check if Redis and DB halt states are consistent.

        Returns:
            True if both channels agree, False if there's a mismatch.
        """
        consistent = self._db_halted == self._redis_halted

        if not consistent:
            log.warning(
                "stub_halt_channels_inconsistent",
                db_halted=self._db_halted,
                redis_halted=self._redis_halted,
            )

        return consistent

    async def resolve_conflict(self) -> None:
        """Resolve halt channel conflict.

        DB is canonical. Corrects Redis to match DB.
        Logs phantom halt (Redis halted, DB not) for investigation.
        """
        if self._db_halted and not self._redis_halted:
            # DB is halted but Redis isn't - propagate to Redis
            log.info(
                "stub_conflict_resolution_propagating_to_redis",
                db_halted=True,
                redis_halted=False,
            )
            self._redis_halted = True

        elif not self._db_halted and self._redis_halted:
            # Redis says halt but DB doesn't - SUSPICIOUS
            # Log but do NOT clear Redis halt (security measure)
            log.warning(
                "stub_conflict_detected_phantom_halt",
                db_halted=False,
                redis_halted=True,
                action="logged_for_investigation_redis_not_cleared",
            )
            # Note: Redis NOT cleared - phantom halts are suspicious

        else:
            log.info("stub_no_conflict_to_resolve", db_halted=self._db_halted)

    async def clear_halt(
        self,
        ceremony_evidence: CeremonyEvidence,
    ) -> HaltClearedPayload:
        """Clear halt with proper ceremony evidence (Story 3.4, ADR-3).

        Halt is sticky once set. Clearing requires a witnessed ceremony
        with at least 2 Keeper approvers (ADR-6 Tier 1).

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
            "stub_dual_channel_halt_clear",
            ceremony_id=str(ceremony_evidence.ceremony_id),
            approver_count=len(ceremony_evidence.approvers),
            keeper_ids=ceremony_evidence.get_keeper_ids(),
        )

        # Clear both channels
        self._db_halted = False
        self._redis_halted = False
        clear_reason = f"Recovery ceremony {ceremony_evidence.ceremony_id}"

        # Create and return HaltClearedPayload
        return HaltClearedPayload(
            ceremony_id=ceremony_evidence.ceremony_id,
            clearing_authority="Keeper Council",
            reason=clear_reason,
            approvers=ceremony_evidence.get_keeper_ids(),
            cleared_at=datetime.now(timezone.utc),
        )

    # Test helper methods

    def set_db_halted(
        self,
        halted: bool,
        reason: str | None = None,
        crisis_event_id: UUID | None = None,
    ) -> None:
        """Set DB halt state directly for testing.

        Args:
            halted: Whether DB channel shows halted.
            reason: Halt reason (optional).
            crisis_event_id: Crisis event ID (optional).
        """
        self._db_halted = halted
        if reason is not None:
            self._halt_reason = reason
        if crisis_event_id is not None:
            self._crisis_event_id = crisis_event_id

    def set_redis_halted(self, halted: bool) -> None:
        """Set Redis halt state directly for testing.

        Args:
            halted: Whether Redis channel shows halted.
        """
        self._redis_halted = halted

    def set_db_failure(self, failing: bool) -> None:
        """Simulate DB failure for testing.

        Args:
            failing: True to simulate DB failure.
        """
        self._db_failure = failing

    def set_redis_failure(self, failing: bool) -> None:
        """Simulate Redis failure for testing.

        Args:
            failing: True to simulate Redis failure.
        """
        self._redis_failure = failing

    def get_trigger_count(self) -> int:
        """Get number of write_halt calls (for testing).

        Returns:
            Number of times write_halt was called.
        """
        return self._trigger_count

    def get_crisis_event_id(self) -> UUID | None:
        """Get last crisis event ID (for testing).

        Returns:
            Last crisis event ID, or None if never halted.
        """
        return self._crisis_event_id

    def reset(self) -> None:
        """Reset all state for test isolation."""
        self._db_halted = False
        self._redis_halted = False
        self._halt_reason = None
        self._crisis_event_id = None
        self._trigger_count = 0
        self._db_failure = False
        self._redis_failure = False
