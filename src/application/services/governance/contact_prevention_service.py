"""Contact prevention service for dignified exit.

Story: consent-gov-7.4: Follow-Up Contact Prevention

Service that enforces the constitutional prohibition on contacting
exited Clusters. This service implements structural prohibition -
the methods for follow-up contact do not exist.

NFR-EXIT-02: No follow-up contact mechanism may exist.
FR46: System can prohibit follow-up contact after exit.

Structural Prohibition Enforced:
- No unblock() method
- No send_to_exited() method
- No winback_message() method
- No reengagement_campaign() method
- No come_back_notification() method

These methods structurally do not exist. You cannot call what
does not exist. This is architecture-level enforcement.
"""

from typing import Protocol
from uuid import UUID, uuid4

from src.application.ports.governance.contact_block_port import ContactBlockPort
from src.domain.governance.exit.contact_block import ContactBlock
from src.domain.governance.exit.contact_block_status import ContactBlockStatus
from src.domain.governance.exit.contact_violation import ContactViolation


class EventEmitter(Protocol):
    """Protocol for event emission."""

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        """Emit an event."""
        ...


class TimeAuthority(Protocol):
    """Protocol for time operations."""

    def now(self):
        """Get current time."""
        ...


class ContactPreventionService:
    """Service for preventing follow-up contact with exited Clusters.

    This service implements NFR-EXIT-02's structural prohibition.
    Methods for contacting exited Clusters DO NOT EXIST.

    Key Design Principles:
    1. Blocks are permanent (no unblock method)
    2. All contact attempts are blocked (structural)
    3. All violations are recorded (accountability)
    4. Knight observes all violations (observability)

    Intentionally Missing Methods (Structural Prohibition):
    - unblock(): Cannot unblock
    - send_to_exited(): Cannot contact exited Clusters
    - winback_message(): No win-back capability
    - reengagement_campaign(): No re-engagement
    - come_back_notification(): No "come back" messages

    Example:
        # Block contact on exit
        block = await prevention_service.block_on_exit(cluster_id)

        # Check if blocked
        is_blocked = await prevention_service.is_blocked(cluster_id)

        # Record violation (called by infrastructure)
        await prevention_service.record_contact_attempt(
            cluster_id=cluster_id,
            attempted_by="MessageRouter",
        )

        # NOTE: No way to unblock or contact exited Cluster
    """

    def __init__(
        self,
        contact_block_port: ContactBlockPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ) -> None:
        """Initialize the contact prevention service.

        Args:
            contact_block_port: Port for contact block operations.
            event_emitter: Port for emitting events.
            time_authority: Authority for time operations.
        """
        self._blocks = contact_block_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def block_on_exit(self, cluster_id: UUID) -> ContactBlock:
        """Block all contact to a Cluster on exit.

        This creates a permanent contact block. Once called,
        the Cluster can never be contacted by the system again.

        There is NO unblock method. This is final.

        Args:
            cluster_id: The Cluster that is exiting.

        Returns:
            The created ContactBlock.

        Emits:
            custodial.contact.blocked: When block is created.
        """
        now = self._time.now()

        block = ContactBlock(
            block_id=uuid4(),
            cluster_id=cluster_id,
            blocked_at=now,
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        await self._blocks.add_block(block)

        await self._event_emitter.emit(
            event_type="custodial.contact.blocked",
            actor="system",
            payload={
                "block_id": str(block.block_id),
                "cluster_id": str(cluster_id),
                "blocked_at": now.isoformat(),
                "reason": "exit",
                "permanent": True,
            },
        )

        return block

    async def is_blocked(self, cluster_id: UUID) -> bool:
        """Check if contact is blocked for a Cluster.

        Args:
            cluster_id: The Cluster to check.

        Returns:
            True if contact is blocked, False otherwise.
        """
        return await self._blocks.is_blocked(cluster_id)

    async def get_block(self, cluster_id: UUID) -> ContactBlock | None:
        """Get the block record for a Cluster.

        Args:
            cluster_id: The Cluster to look up.

        Returns:
            The ContactBlock if blocked, None otherwise.
        """
        return await self._blocks.get_block(cluster_id)

    async def record_contact_attempt(
        self,
        cluster_id: UUID,
        attempted_by: str,
    ) -> ContactViolation:
        """Record a blocked contact attempt.

        This is called by infrastructure (routers, APIs) when
        contact is attempted to a blocked Cluster. The contact
        is ALWAYS blocked. This method records the violation.

        Args:
            cluster_id: The Cluster contact was attempted to.
            attempted_by: Component that attempted contact.

        Returns:
            The ContactViolation record.

        Emits:
            constitutional.violation.contact_attempt: Violation event.
        """
        now = self._time.now()

        violation = ContactViolation(
            violation_id=uuid4(),
            cluster_id=cluster_id,
            attempted_by=attempted_by,
            attempted_at=now,
            blocked=True,  # Always blocked
        )

        await self._event_emitter.emit(
            event_type="constitutional.violation.contact_attempt",
            actor=attempted_by,
            payload={
                "violation_id": str(violation.violation_id),
                "cluster_id": str(cluster_id),
                "attempted_by": attempted_by,
                "attempted_at": now.isoformat(),
                "blocked": True,
                "violation_type": "nfr_exit_02_contact_after_exit",
            },
        )

        return violation

    async def get_all_blocked_clusters(self) -> list[UUID]:
        """Get all blocked Cluster IDs.

        Returns:
            List of all Cluster IDs that are blocked.
        """
        return await self._blocks.get_all_blocked()

    # ═══════════════════════════════════════════════════════════════════════════
    # STRUCTURAL PROHIBITION - These methods DO NOT EXIST
    # ═══════════════════════════════════════════════════════════════════════════
    #
    # NFR-EXIT-02: No follow-up contact mechanism may exist.
    #
    # The following methods are NOT defined and MUST NOT be added:
    #
    # async def unblock(self, cluster_id: UUID) -> None:
    #     """THIS METHOD DOES NOT EXIST - blocks are permanent."""
    #
    # async def remove_block(self, cluster_id: UUID) -> None:
    #     """THIS METHOD DOES NOT EXIST - blocks cannot be removed."""
    #
    # async def send_to_exited(self, cluster_id: UUID, message: str) -> None:
    #     """THIS METHOD DOES NOT EXIST - cannot contact exited."""
    #
    # async def winback_message(self, cluster_id: UUID) -> None:
    #     """THIS METHOD DOES NOT EXIST - no win-back capability."""
    #
    # async def reengagement_campaign(self, cluster_ids: list[UUID]) -> None:
    #     """THIS METHOD DOES NOT EXIST - no re-engagement."""
    #
    # async def come_back_notification(self, cluster_id: UUID) -> None:
    #     """THIS METHOD DOES NOT EXIST - no "come back" messages."""
    #
    # async def we_miss_you_email(self, cluster_id: UUID) -> None:
    #     """THIS METHOD DOES NOT EXIST - no "we miss you" messages."""
    #
    # async def tasks_waiting_reminder(self, cluster_id: UUID) -> None:
    #     """THIS METHOD DOES NOT EXIST - no task reminders to exited."""
    #
    # Why structural absence?
    # - Policy can be violated
    # - Settings can be changed
    # - Methods that don't exist cannot be called
    # - Architecture IS the enforcement
    # ═══════════════════════════════════════════════════════════════════════════
