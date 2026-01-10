"""Event Writer Service - single canonical writer (Story 1.6, ADR-1; Story 4.8, SR-9; Story 7.3; Story 7.4).

This service ensures the single-writer invariant required by ADR-1.
Only one Writer instance may be active at any time.
Failover requires a witnessed ceremony (not automatic).

Constitutional Constraints:
- ADR-1: Single canonical writer, DB enforces chain integrity
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-13: Integrity outranks availability -> Availability may be sacrificed
- GAP-CHAOS-001: Writer self-verification before accepting writes
- SR-9: Observer push notifications - breach events trigger notifications
- RT-5: Breach events pushed to multiple channels (webhook + SSE)
- FR40/NFR40: No cessation reversal - terminal check BEFORE halt check (Story 7.3)
- FR41: Freeze on new actions after cessation - freeze check AFTER terminal check (Story 7.4)

Responsibilities:
1. Terminal check before every write (TERMINAL FIRST rule - Story 7.3)
2. Freeze check before every write (FREEZE SECOND rule - Story 7.4)
3. Halt check before every write (HALT THIRD rule)
4. Writer lock verification (single-writer constraint)
5. Startup self-verification (head hash consistency)
6. Delegation to AtomicEventWriter for actual writes
7. Structured logging for success/failure (AC2, AC3)
8. Push notification publishing for notifiable events (SR-9)

Architecture Pattern:
    EventWriterService wraps AtomicEventWriter and adds constitutional checks:

    EventWriterService
      ├─ terminal_detector.is_system_terminated()  # Check first (TERMINAL FIRST - Story 7.3)
      ├─ freeze_checker.is_frozen()               # Check second (FREEZE SECOND - Story 7.4)
      ├─ halt_checker.is_halted()                 # Check third (HALT THIRD rule)
      ├─ writer_lock.is_held()                    # Verify we hold writer lock
      ├─ verify_head_consistency()                # Self-verification
      └─ atomic_writer.write_event()              # Delegates actual write

Trust Boundary (ADR-1 Critical):
    The Writer Service MUST NOT:
    - Compute content_hash locally (DB trigger computes)
    - Verify hash chain locally (DB trigger verifies)
    - Trust any hash that didn't come from DB response

    Hash computation, chain verification, and append-only enforcement
    are delegated to the database (Supabase Postgres).

Story 7.3 - Schema Irreversibility (FR40, NFR40):
    The terminal check MUST be performed BEFORE the halt check because:
    1. Cessation is permanent; halt is temporary
    2. A halted system can be unhalted; a ceased system cannot
    3. Terminal state supersedes all other states
    4. This ordering prevents any edge case where halt could mask cessation

Story 7.4 - Freeze Mechanics (FR41):
    The freeze check complements the terminal check:
    - Terminal check verifies cessation event EXISTS (Story 7.3)
    - Freeze check verifies operational FREEZE is in effect (Story 7.4)
    Both should raise appropriate errors, but freeze check happens AFTER terminal.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from structlog import get_logger

from src.application.ports.event_store import EventStorePort
from src.application.ports.freeze_checker import FreezeCheckerProtocol
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.notification_publisher import NotificationPublisherPort
from src.application.ports.terminal_event_detector import TerminalEventDetectorProtocol
from src.application.ports.writer_lock import WriterLockProtocol
from src.domain.errors.ceased import SystemCeasedError
from src.domain.errors.schema_irreversibility import SchemaIrreversibilityError
from src.domain.errors.writer import (
    SystemHaltedError,
    WriterInconsistencyError,
    WriterLockNotHeldError,
    WriterNotVerifiedError,
)

if TYPE_CHECKING:
    from src.application.services.atomic_event_writer import AtomicEventWriter
    from src.domain.events.event import Event

logger = get_logger()


class EventWriterService:
    """Single canonical event writer (ADR-1, Story 7.3, Story 7.4).

    Constitutional Constraint:
    This service ensures the single-writer invariant required by ADR-1.
    Only one Writer instance may be active at any time.
    Failover requires a witnessed ceremony.

    Developer Golden Rules:
    1. TERMINAL FIRST - Check termination state before any other check (Story 7.3)
    2. FREEZE SECOND - Check freeze state after terminal check (Story 7.4)
    3. HALT THIRD - Check halt state after freeze check
    4. FAIL LOUD - Never catch SystemHaltedError, SchemaIrreversibilityError, or SystemCeasedError
    5. Delegate to DB - Do not compute hashes locally

    Attributes:
        _atomic_writer: Underlying writer for actual event persistence.
        _terminal_detector: Interface to check system termination state (Story 7.3).
        _freeze_checker: Interface to check system freeze state (Story 7.4).
        _halt_checker: Interface to check system halt state.
        _writer_lock: Interface to verify single-writer constraint.
        _event_store: Direct event store access for verification.
        _notification_publisher: Optional publisher for push notifications.
        _verified: Whether startup verification has passed.
        _last_known_head_hash: Cached head hash from last verification.
    """

    def __init__(
        self,
        atomic_writer: AtomicEventWriter,
        halt_checker: HaltChecker,
        writer_lock: WriterLockProtocol,
        event_store: EventStorePort,
        notification_publisher: NotificationPublisherPort | None = None,
        terminal_detector: TerminalEventDetectorProtocol | None = None,
        freeze_checker: FreezeCheckerProtocol | None = None,
    ) -> None:
        """Initialize the Event Writer Service.

        Args:
            atomic_writer: Service for atomic event writes with witness.
            halt_checker: Interface to check halt state (stub in Epic 1).
            writer_lock: Interface for single-writer lock management.
            event_store: Direct event store access for head verification.
            notification_publisher: Optional publisher for push notifications (SR-9).
                If provided, notifiable events (breach, halt, fork) will trigger
                push notifications to SSE streams and webhooks.
            terminal_detector: Interface to check system termination state (Story 7.3).
                If provided, terminal check is performed BEFORE halt check.
                If None, terminal check is skipped (backwards compatible).
            freeze_checker: Interface to check system freeze state (Story 7.4).
                If provided, freeze check is performed AFTER terminal check.
                If None, freeze check is skipped (backwards compatible).
        """
        self._atomic_writer = atomic_writer
        self._halt_checker = halt_checker
        self._writer_lock = writer_lock
        self._event_store = event_store
        self._notification_publisher = notification_publisher
        self._terminal_detector = terminal_detector
        self._freeze_checker = freeze_checker
        self._verified = False
        self._last_known_head_hash: str | None = None

    async def verify_startup(self, expected_head_hash: str | None = None) -> None:
        """Verify head hash consistency on startup (GAP-CHAOS-001, AC5).

        MUST be called before accepting any writes.
        This verification ensures the Writer's view of the event store
        matches the database state.

        Constitutional Constraint:
        Writer self-verification prevents split-brain scenarios where
        the Writer has stale state. If mismatch is detected, the system
        must halt for human investigation.

        Args:
            expected_head_hash: If provided, verify the DB head hash matches
                this value. Used when Writer has cached state from previous
                execution. If None, just loads current head (cold start).

        Raises:
            SystemHaltedError: If system is halted during verification.
            WriterLockNotHeldError: If writer lock cannot be acquired.
            WriterInconsistencyError: If head hash mismatch detected (AC5).
                This error should NEVER be caught - it requires human intervention.
        """
        log = logger.bind(operation="verify_startup")

        # Step 1: Check halt state first (even during startup)
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.warning(
                "startup_verification_skipped_system_halted",
                halt_reason=reason,
            )
            # Still mark as not verified - no writes should proceed
            self._verified = False
            raise SystemHaltedError(f"GAP-CHAOS-001: Cannot verify - system halted: {reason}")

        # Step 2: Acquire writer lock before verification
        if not await self._writer_lock.is_held():
            # Try to acquire the lock
            acquired = await self._writer_lock.acquire()
            if not acquired:
                log.error("startup_verification_failed_lock_not_acquired")
                raise WriterLockNotHeldError(
                    "ADR-1: Cannot acquire writer lock - another instance is active"
                )

        # Step 3: Fetch latest event from DB
        latest = await self._event_store.get_latest_event()

        if latest is None:
            # Empty store case
            if expected_head_hash is not None:
                # We expected data but store is empty - mismatch!
                log.critical(
                    "writer_verification_failed_head_hash_mismatch",
                    expected_hash=expected_head_hash[:16] + "...",
                    db_hash="<empty_store>",
                    message="GAP-CHAOS-001: Expected events but DB is empty",
                )
                raise WriterInconsistencyError(
                    f"GAP-CHAOS-001: Head hash mismatch - "
                    f"expected={expected_head_hash}, db=<empty_store>"
                )
            # Cold start with empty store - OK
            log.info(
                "writer_verification_passed",
                state="empty_store",
                message="Empty store - no verification needed",
            )
            self._verified = True
            self._last_known_head_hash = None
            return

        # Step 4: Verify head hash if expected value provided (AC5)
        db_head_hash = latest.content_hash

        if expected_head_hash is not None and db_head_hash != expected_head_hash:
            # CRITICAL: Head hash mismatch detected (GAP-CHAOS-001)
            # Log CRITICAL with both hash values before raising (Task 3.5)
            log.critical(
                "writer_verification_failed_head_hash_mismatch",
                expected_hash=expected_head_hash[:16] + "...",
                db_hash=db_head_hash[:16] + "...",
                expected_hash_full=expected_head_hash,
                db_hash_full=db_head_hash,
                db_sequence=latest.sequence,
                message="GAP-CHAOS-001: Head hash mismatch - possible split-brain or corruption",
            )
            raise WriterInconsistencyError(
                f"GAP-CHAOS-001: Head hash mismatch - "
                f"expected={expected_head_hash}, db={db_head_hash}"
            )

        # Step 5: Store the verified head hash
        self._last_known_head_hash = db_head_hash

        log.info(
            "writer_verification_passed",
            head_sequence=latest.sequence,
            head_hash=db_head_hash[:16] + "...",
            verified_against_expected=expected_head_hash is not None,
            message="Head hash verified with DB",
        )
        self._verified = True

    async def write_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        agent_id: str,
        local_timestamp: datetime,
    ) -> Event:
        """Write event with all constitutional checks (AC1, AC2, AC3, Story 7.3, Story 7.4).

        This is the main entry point for writing events. It performs
        all constitutional checks before delegating to AtomicEventWriter.

        Check Order (CRITICAL - Story 7.3, Story 7.4):
        1. TERMINAL CHECK (NFR40 - cessation is permanent, Story 7.3)
        2. FREEZE CHECK (FR41 - operational freeze, Story 7.4)
        3. HALT CHECK (CT-11 - halt over degrade)
        4. Writer lock verification (ADR-1 - single writer)
        5. Startup verification check (GAP-CHAOS-001)
        6. Delegate to AtomicEventWriter
        7. Log success/failure with event_id and sequence
        8. Push notification for notifiable events (SR-9, RT-5)

        Args:
            event_type: Event type classification.
            payload: Event payload data.
            agent_id: Agent creating the event.
            local_timestamp: Timestamp from event source.

        Returns:
            The persisted Event with sequence assigned by DB.

        Raises:
            SchemaIrreversibilityError: If system is terminated (NFR40, never retry!).
            SystemCeasedError: If system is frozen/ceased (FR41, never retry!).
            SystemHaltedError: If system is halted (never retry!).
            WriterLockNotHeldError: If writer lock not held.
            WriterNotVerifiedError: If startup verification not done.
            NoWitnessAvailableError: If no witnesses available.
            EventStoreError: If persistence fails.
        """
        log = logger.bind(
            operation="write_event",
            event_type=event_type,
            agent_id=agent_id,
        )

        # =====================================================================
        # Step 1: TERMINAL FIRST (Developer Golden Rule, NFR40, Story 7.3)
        # Terminal check BEFORE halt check because:
        # - Cessation is permanent; halt is temporary
        # - A halted system can be unhalted; a ceased system cannot
        # - Terminal state supersedes all other states
        # =====================================================================
        if self._terminal_detector is not None:
            if await self._terminal_detector.is_system_terminated():
                terminal_event = await self._terminal_detector.get_terminal_event()
                terminal_timestamp = await self._terminal_detector.get_termination_timestamp()
                log.critical(
                    "post_cessation_write_rejected",
                    terminal_event_id=str(terminal_event.event_id) if terminal_event else None,
                    terminal_sequence=terminal_event.sequence if terminal_event else None,
                    termination_timestamp=terminal_timestamp.isoformat() if terminal_timestamp else None,
                    message="NFR40: Cannot write events after cessation",
                )
                seq_info = f" at seq {terminal_event.sequence}" if terminal_event else ""
                raise SchemaIrreversibilityError(
                    f"NFR40: Cannot write events after cessation. System terminated{seq_info}"
                )

        # =====================================================================
        # Step 2: FREEZE SECOND (Developer Golden Rule, FR41, Story 7.4)
        # Freeze check AFTER terminal check because:
        # - Terminal = cessation event exists (schema-level)
        # - Freeze = operational freeze in effect (operational-level)
        # - Both complement each other for full cessation handling
        # =====================================================================
        if self._freeze_checker is not None:
            if await self._freeze_checker.is_frozen():
                details = await self._freeze_checker.get_freeze_details()
                if details:
                    log.critical(
                        "write_rejected_system_frozen",
                        ceased_at=details.ceased_at.isoformat(),
                        final_sequence=details.final_sequence_number,
                        reason=details.reason,
                        message="FR41: System ceased - writes frozen",
                    )
                    raise SystemCeasedError.from_details(details)
                else:
                    # Frozen but no details (defensive handling)
                    ceased_at = await self._freeze_checker.get_ceased_at()
                    final_seq = await self._freeze_checker.get_final_sequence()
                    log.critical(
                        "write_rejected_system_frozen",
                        ceased_at=ceased_at.isoformat() if ceased_at else "unknown",
                        final_sequence=final_seq,
                        message="FR41: System ceased - writes frozen",
                    )
                    raise SystemCeasedError(
                        message="FR41: System ceased - writes frozen",
                        ceased_at=ceased_at,
                        final_sequence_number=final_seq,
                    )

        # =====================================================================
        # Step 3: HALT THIRD (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "write_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Step 4: Writer lock verification (ADR-1)
        # =====================================================================
        if not await self._writer_lock.is_held():
            log.error(
                "write_rejected_no_lock",
                message="ADR-1: Single-writer constraint violated",
            )
            raise WriterLockNotHeldError("ADR-1: Writer lock not held - cannot write")

        # =====================================================================
        # Step 5: Startup verification check (GAP-CHAOS-001)
        # =====================================================================
        if not self._verified:
            log.error(
                "write_rejected_not_verified",
                message="GAP-CHAOS-001: Startup verification not performed",
            )
            raise WriterNotVerifiedError(
                "GAP-CHAOS-001: Writer not verified - call verify_startup() first"
            )

        # =====================================================================
        # Step 6: Delegate to AtomicEventWriter
        # =====================================================================
        try:
            event = await self._atomic_writer.write_event(
                event_type=event_type,
                payload=payload,
                agent_id=agent_id,
                local_timestamp=local_timestamp,
            )

            # =====================================================================
            # Step 7: Log success (AC2)
            # =====================================================================
            log.info(
                "event_written_successfully",
                event_id=str(event.event_id),
                sequence=event.sequence,
                content_hash=event.content_hash[:16] + "...",  # Truncate for logging
            )

            # Update cached head hash
            self._last_known_head_hash = event.content_hash

            # =====================================================================
            # Step 8: Push notification (SR-9, RT-5)
            # =====================================================================
            if self._notification_publisher is not None:
                try:
                    await self._notification_publisher.notify_event(event)
                except Exception as notify_err:
                    # Log but don't fail the write - notification is best-effort
                    # Per CT-11: Log delivery failure for accountability
                    log.warning(
                        "notification_publish_failed",
                        event_id=str(event.event_id),
                        sequence=event.sequence,
                        error=str(notify_err),
                    )

            return event

        except Exception as e:
            # =====================================================================
            # Log failure (AC3)
            # =====================================================================
            log.error(
                "event_write_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    @property
    def is_verified(self) -> bool:
        """Check if startup verification has passed.

        Returns:
            True if verify_startup() succeeded, False otherwise.
        """
        return self._verified

    @property
    def last_known_head_hash(self) -> str | None:
        """Get the last known head hash.

        Returns:
            The content hash of the last verified/written event,
            or None if store is empty or not verified.
        """
        return self._last_known_head_hash
