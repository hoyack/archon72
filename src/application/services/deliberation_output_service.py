"""Deliberation Output Service (Story 2.1, FR9).

This service orchestrates the No Preview constraint, ensuring agent outputs
are committed to the event store before any human can view them.

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability

AC1: Immediate Output Commitment - commit_and_store()
AC2: Hash Verification on View - get_for_viewing()
AC3: Pre-Commit Access Denial - NoPreviewEnforcer
AC4: No Preview Code Path - atomic commit-then-serve

Architecture Pattern:
    DeliberationOutputService orchestrates FR9 compliance:

    commit_and_store(payload):
      ├─ halt_checker.is_halted()     # Check first (HALT FIRST rule)
      ├─ output_port.store_output()   # Store output atomically
      └─ no_preview_enforcer.mark_committed()  # Mark as viewable

    get_for_viewing(output_id, viewer_id):
      ├─ halt_checker.is_halted()     # Check first (HALT FIRST rule)
      ├─ no_preview_enforcer.verify_committed()  # FR9 check (raises if not)
      ├─ output_port.get_output()     # Retrieve from storage
      ├─ no_preview_enforcer.verify_hash()  # Integrity check
      └─ return ViewableOutput        # Only after all checks pass
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from structlog import get_logger

from src.application.ports.deliberation_output import (
    DeliberationOutputPort,
    StoredOutput,
)
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.writer import SystemHaltedError
from src.domain.services.no_preview_enforcer import NoPreviewEnforcer

if TYPE_CHECKING:
    from src.domain.events.deliberation_output import DeliberationOutputPayload

logger = get_logger()


@dataclass(frozen=True, eq=True)
class CommittedOutput:
    """Result of committing a deliberation output.

    Returned by commit_and_store() after successful commit.
    Contains references needed for later retrieval.

    Attributes:
        output_id: UUID of the committed output.
        content_hash: SHA-256 hash of the content.
        event_sequence: Sequence number in the event store.
        committed_at: Timestamp when output was committed.
    """

    output_id: UUID
    content_hash: str
    event_sequence: int
    committed_at: datetime


@dataclass(frozen=True, eq=True)
class ViewableOutput:
    """Output that has been verified and is safe to view.

    Returned by get_for_viewing() after FR9 verification.
    The caller can safely display this to a human.

    Attributes:
        output_id: UUID of the output.
        agent_id: ID of the agent that produced the output.
        content: The actual output content (verified).
        content_type: MIME type of the content.
        content_hash: SHA-256 hash (verified to match).
    """

    output_id: UUID
    agent_id: str
    content: str
    content_type: str
    content_hash: str


class DeliberationOutputService:
    """Service for FR9-compliant deliberation output handling.

    This service ensures the No Preview constraint (FR9) is honored:
    agent outputs must be recorded before any human sees them.

    Developer Golden Rules:
    1. HALT FIRST - Check halt state before any operation
    2. COMMIT BEFORE VIEW - Never return content before commit
    3. VERIFY HASH - Always verify content integrity before serving

    Attributes:
        _output_port: Interface for output storage.
        _halt_checker: Interface for halt state checking.
        _no_preview_enforcer: Domain service for FR9 enforcement.
    """

    def __init__(
        self,
        output_port: DeliberationOutputPort,
        halt_checker: HaltChecker,
        no_preview_enforcer: NoPreviewEnforcer,
    ) -> None:
        """Initialize the service.

        Args:
            output_port: Storage interface for outputs.
            halt_checker: Interface to check halt state.
            no_preview_enforcer: Domain service for FR9 enforcement.
        """
        self._output_port = output_port
        self._halt_checker = halt_checker
        self._no_preview_enforcer = no_preview_enforcer

    async def commit_and_store(
        self,
        payload: DeliberationOutputPayload,
    ) -> CommittedOutput:
        """Commit and store an agent output (AC1).

        This is the ONLY path for agent outputs to become viewable.
        The output is stored atomically, and only after successful
        storage is it marked as committed.

        Args:
            payload: The deliberation output payload to commit.

        Returns:
            CommittedOutput with reference information.

        Raises:
            SystemHaltedError: If system is halted.
            EventStoreError: If storage fails.
        """
        # HALT FIRST (Golden Rule #1)
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            logger.warning(
                "commit_blocked_halt",
                output_id=str(payload.output_id),
                halt_reason=reason,
            )
            raise SystemHaltedError(
                f"FR9: Cannot commit output - system halted: {reason}"
            )

        logger.info(
            "committing_output",
            output_id=str(payload.output_id),
            agent_id=payload.agent_id,
            content_type=payload.content_type,
        )

        # Store output atomically - this blocks until confirmed
        # Note: sequence is set to 0 as placeholder - actual sequence comes from event store
        stored: StoredOutput = await self._output_port.store_output(
            payload=payload,
            event_sequence=0,  # Placeholder - real impl gets from event store
        )

        # ONLY after confirmed commit, mark as viewable
        self._no_preview_enforcer.mark_committed(
            payload.output_id,
            content_hash=payload.content_hash,
        )

        logger.info(
            "output_committed",
            output_id=str(payload.output_id),
            event_sequence=stored.event_sequence,
            content_hash=payload.content_hash[:8] + "...",
        )

        return CommittedOutput(
            output_id=payload.output_id,
            content_hash=payload.content_hash,
            event_sequence=stored.event_sequence,
            committed_at=stored.stored_at,
        )

    async def get_for_viewing(
        self,
        output_id: UUID,
        viewer_id: str,
    ) -> ViewableOutput | None:
        """Get an output for viewing (AC2, AC3).

        This method enforces FR9 by verifying the output was committed
        before allowing access. It also verifies content hash integrity.

        Args:
            output_id: UUID of the output to view.
            viewer_id: Identity of the viewer (for audit trail).

        Returns:
            ViewableOutput if found and verified, None if not found.

        Raises:
            SystemHaltedError: If system is halted.
            FR9ViolationError: If output was not committed (AC3).
        """
        # HALT FIRST (Golden Rule #1)
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            logger.warning(
                "view_blocked_halt",
                output_id=str(output_id),
                viewer_id=viewer_id,
                halt_reason=reason,
            )
            raise SystemHaltedError(
                f"FR9: Cannot view output - system halted: {reason}"
            )

        # FR9 ENFORCEMENT (AC3) - raises FR9ViolationError if not committed
        self._no_preview_enforcer.verify_committed(output_id)

        # Retrieve from storage
        payload = await self._output_port.get_output(output_id)
        if payload is None:
            logger.warning(
                "output_not_found",
                output_id=str(output_id),
                viewer_id=viewer_id,
            )
            return None

        # HASH VERIFICATION (AC2) - raises FR9ViolationError on mismatch
        self._no_preview_enforcer.verify_hash(output_id, payload.content_hash)

        logger.info(
            "output_viewed",
            output_id=str(output_id),
            viewer_id=viewer_id,
            agent_id=payload.agent_id,
        )

        return ViewableOutput(
            output_id=payload.output_id,
            agent_id=payload.agent_id,
            content=payload.raw_content,
            content_type=payload.content_type,
            content_hash=payload.content_hash,
        )
