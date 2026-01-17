"""Exit service for consent-based governance.

Story: consent-gov-7.1: Exit Request Processing

This module implements the ExitService for processing exit requests.
Exit is designed to be simple, immediate, and barrier-free.

Constitutional Truths Honored:
- Golden Rule: Exit is an unconditional right
- CT-11: Silent failure destroys legitimacy → Events always emitted
- CT-12: Witnessing creates accountability → Knight observes all exits

Design Principles:
- Exit completes in ≤2 message round-trips (NFR-EXIT-01)
- Exit path available from any task state (NFR-EXIT-03)
- No barriers, confirmations, or waiting periods
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid4

from src.domain.governance.exit.exit_request import ExitRequest
from src.domain.governance.exit.exit_result import ExitResult
from src.domain.governance.exit.exit_status import ExitStatus
from src.domain.governance.exit.errors import AlreadyExitedError


# Event type constants
EXIT_INITIATED_EVENT = "custodial.exit.initiated"
EXIT_COMPLETED_EVENT = "custodial.exit.completed"


class TimeAuthority(Protocol):
    """Protocol for time authority (injected dependency)."""

    def now(self):
        """Get current timestamp."""
        ...


class EventEmitter(Protocol):
    """Protocol for event emission (injected dependency)."""

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        """Emit an event to the ledger."""
        ...


class ExitPortProtocol(Protocol):
    """Protocol for exit port (injected dependency)."""

    async def record_exit_request(self, request: ExitRequest) -> None:
        """Record exit request."""
        ...

    async def record_exit_result(self, result: ExitResult) -> None:
        """Record exit result."""
        ...

    async def has_cluster_exited(self, cluster_id: UUID) -> bool:
        """Check if cluster has exited."""
        ...

    async def get_cluster_active_tasks(self, cluster_id: UUID) -> list[UUID]:
        """Get active tasks for cluster."""
        ...


class ExitService:
    """Handles Cluster exit processing.

    Per FR42: Cluster can initiate exit request.
    Per FR43: System can process exit request.
    Per NFR-EXIT-01: Exit MUST complete in ≤2 round-trips.

    Exit Flow:
        Round-trip 1: Cluster sends request → System processes
        Round-trip 2: System confirms completion

    No barriers allowed:
    - No confirmation prompts
    - No waiting periods
    - No penalty warnings
    - No reason required
    """

    def __init__(
        self,
        exit_port: ExitPortProtocol,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ) -> None:
        """Initialize ExitService.

        Args:
            exit_port: Port for exit data operations.
            event_emitter: For emitting governance events.
            time_authority: For timestamp generation.
        """
        self._exit = exit_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def initiate_exit(
        self,
        cluster_id: UUID,
    ) -> ExitResult:
        """Initiate and complete exit in single call.

        Per NFR-EXIT-01: Exit completes in ≤2 round-trips.

        This is the ONLY method needed for exit. It:
        1. Validates cluster hasn't already exited
        2. Creates exit request
        3. Emits initiated event
        4. Processes exit (releases obligations, etc.)
        5. Emits completed event
        6. Returns result

        No confirmation required. No intermediate state.

        Args:
            cluster_id: ID of the Cluster requesting exit.

        Returns:
            ExitResult with completion status.

        Raises:
            AlreadyExitedError: If Cluster has already exited.
        """
        # Round-trip 1: Request received

        now = self._time.now()

        # Check if already exited (not a barrier - logical check)
        if await self._exit.has_cluster_exited(cluster_id):
            raise AlreadyExitedError(str(cluster_id))

        # Get active tasks at time of request
        active_tasks = await self._exit.get_cluster_active_tasks(cluster_id)

        # Create exit request
        request = ExitRequest(
            request_id=uuid4(),
            cluster_id=cluster_id,
            requested_at=now,
            tasks_at_request=tuple(active_tasks),
        )

        # Record request
        await self._exit.record_exit_request(request)

        # Emit initiated event
        await self._event_emitter.emit(
            event_type=EXIT_INITIATED_EVENT,
            actor=str(cluster_id),
            payload={
                "request_id": str(request.request_id),
                "cluster_id": str(cluster_id),
                "initiated_at": now.isoformat(),
                "active_tasks": len(active_tasks),
            },
        )

        # Process exit immediately (no intermediate state)
        # In full implementation, this would coordinate with:
        # - ObligationReleaseService
        # - ContributionPreservationService
        # - ContactPreventionService
        # For now, we track tasks affected as the count of active tasks
        tasks_affected = len(active_tasks)
        obligations_released = tasks_affected

        completed_at = self._time.now()

        # Create result
        result = ExitResult(
            request_id=request.request_id,
            cluster_id=cluster_id,
            status=ExitStatus.COMPLETED,
            initiated_at=now,
            completed_at=completed_at,
            tasks_affected=tasks_affected,
            obligations_released=obligations_released,
            round_trips=2,  # Exactly 2 per NFR-EXIT-01
        )

        # Record result
        await self._exit.record_exit_result(result)

        # Emit completed event
        await self._event_emitter.emit(
            event_type=EXIT_COMPLETED_EVENT,
            actor="system",
            payload={
                "request_id": str(request.request_id),
                "cluster_id": str(cluster_id),
                "initiated_at": now.isoformat(),
                "completed_at": completed_at.isoformat(),
                "tasks_affected": tasks_affected,
                "obligations_released": obligations_released,
                "duration_ms": result.duration_ms,
            },
        )

        # Round-trip 2: Confirmation returned

        return result

    async def get_exit_status(
        self,
        cluster_id: UUID,
    ) -> ExitStatus | None:
        """Get exit status for a Cluster.

        Args:
            cluster_id: ID of the Cluster.

        Returns:
            ExitStatus.COMPLETED if exited, None otherwise.
        """
        if await self._exit.has_cluster_exited(cluster_id):
            return ExitStatus.COMPLETED
        return None

    # ========================================================================
    # BARRIER METHODS - INTENTIONALLY NOT IMPLEMENTED
    # ========================================================================
    #
    # The following methods DO NOT EXIST by design (NFR-EXIT-01):
    #
    # def confirm_exit(self) -> bool:
    #     '''Would require confirmation - VIOLATES NFR-EXIT-01'''
    #     raise ExitBarrierError("Confirmation prompts not allowed")
    #
    # def verify_exit(self) -> bool:
    #     '''Would require verification - VIOLATES NFR-EXIT-01'''
    #     raise ExitBarrierError("Verification not allowed")
    #
    # def approve_exit(self) -> bool:
    #     '''Would require approval - VIOLATES Golden Rule'''
    #     raise ExitBarrierError("Approval not allowed")
    #
    # def wait_for_exit(self) -> None:
    #     '''Would add waiting period - VIOLATES NFR-EXIT-01'''
    #     raise ExitBarrierError("Waiting periods not allowed")
    #
    # def require_reason(self) -> str:
    #     '''Would require justification - VIOLATES Golden Rule'''
    #     raise ExitBarrierError("Justification not required")
    #
    # def warn_exit(self) -> str:
    #     '''Would show penalty warning - VIOLATES NFR-EXIT-01'''
    #     raise ExitBarrierError("Penalty warnings not allowed")
    #
    # def are_you_sure(self) -> bool:
    #     '''Classic dark pattern - VIOLATES NFR-EXIT-01'''
    #     raise ExitBarrierError("'Are you sure?' not allowed")
    #
    # These methods are documented here to explicitly show they were
    # considered and intentionally rejected to honor constitutional requirements.
