"""Contribution preservation service for consent-based governance.

Story: consent-gov-7.3: Contribution Preservation

This module implements the ContributionPreservationService for preserving
a Cluster's contribution history when they exit the system.

Constitutional Truths Honored:
- FR45: Contribution history preserved on exit
- NFR-INT-02: Public data only, no PII
- Ledger immutability: No deletion or modification
- CT-12: Witnessing creates accountability → Knight observes preservation

Key Design Principles:
1. Mark-only preservation (set flag, no data change)
2. NO delete methods exist
3. NO scrub methods exist
4. NO modify methods exist
5. Attribution uses UUIDs only (no PII)
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.governance.exit.preservation_result import PreservationResult


# Event type constant
CONTRIBUTIONS_PRESERVED_EVENT = "custodial.contributions.preserved"


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


class ContributionPortProtocol(Protocol):
    """Protocol for contribution port (injected dependency)."""

    async def get_for_cluster(self, cluster_id: UUID) -> list:
        """Get all contributions for a Cluster."""
        ...

    async def mark_preserved(self, record_id: UUID, preserved_at) -> None:
        """Mark contribution as preserved."""
        ...


class ContributionPreservationService:
    """Preserves contributions on Cluster exit.

    Per FR45: System can preserve Cluster's contribution history on exit.
    Per AC1: Contribution history preserved.
    Per AC2: History remains in ledger (immutable).

    This service:
    1. Gets all contributions for the exiting Cluster
    2. Marks each contribution as preserved (timestamp only)
    3. Emits `custodial.contributions.preserved` event
    4. Returns preservation result

    Does NOT delete or modify any records.
    Attribution is PII-free (UUIDs only).

    STRUCTURAL ABSENCE (immutability enforcement):
        The following methods DO NOT EXIST:
        - delete_contributions()
        - remove_contributions()
        - scrub_history()
        - scrub_contributions()
        - modify_contributions()

        If these methods are ever added, it is a CONSTITUTIONAL VIOLATION.
    """

    def __init__(
        self,
        contribution_port: ContributionPortProtocol,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ) -> None:
        """Initialize ContributionPreservationService.

        Args:
            contribution_port: Port for contribution operations.
            event_emitter: For emitting governance events.
            time_authority: For timestamp generation.
        """
        self._contributions = contribution_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def preserve(
        self,
        cluster_id: UUID,
    ) -> PreservationResult:
        """Preserve contributions for an exiting Cluster.

        Per FR45: System can preserve Cluster's contribution history on exit.
        Per AC1: Contribution history preserved.
        Per AC2: History remains in ledger (immutable).
        Per AC5: Event `custodial.contributions.preserved` emitted.

        This method:
        1. Gets all contributions for the Cluster
        2. Marks each as preserved (sets preserved_at timestamp)
        3. Emits preservation event
        4. Returns result

        Does NOT delete anything.
        Does NOT modify contribution content.
        Only sets preservation timestamp flag.

        Args:
            cluster_id: ID of the Cluster whose contributions to preserve.

        Returns:
            PreservationResult with preservation details.
        """
        now = self._time.now()

        # Get all contributions for Cluster
        contributions = await self._contributions.get_for_cluster(cluster_id)

        # Mark each as preserved (flag only - no deletion)
        preserved_task_ids: list[UUID] = []
        for contribution in contributions:
            # Skip already preserved contributions
            if self._is_preserved(contribution):
                continue

            record_id = self._get_record_id(contribution)
            task_id = self._get_task_id(contribution)

            await self._contributions.mark_preserved(
                record_id=record_id,
                preserved_at=now,
            )
            preserved_task_ids.append(task_id)

        # Emit preservation event (AC5)
        await self._event_emitter.emit(
            event_type=CONTRIBUTIONS_PRESERVED_EVENT,
            actor="system",
            payload={
                "cluster_id": str(cluster_id),
                "contributions_preserved": len(preserved_task_ids),
                "task_ids": [str(t) for t in preserved_task_ids],
                "preserved_at": now.isoformat(),
            },
        )

        return PreservationResult(
            cluster_id=cluster_id,
            contributions_preserved=len(preserved_task_ids),
            task_ids=tuple(preserved_task_ids),
            preserved_at=now,
        )

    def _is_preserved(self, contribution) -> bool:
        """Check if contribution is already preserved."""
        if hasattr(contribution, "is_preserved"):
            return contribution.is_preserved
        if hasattr(contribution, "preserved_at"):
            return contribution.preserved_at is not None
        return False

    def _get_record_id(self, contribution) -> UUID:
        """Extract record ID from contribution object."""
        if hasattr(contribution, "record_id"):
            return contribution.record_id
        if hasattr(contribution, "id"):
            return contribution.id
        raise ValueError(f"Cannot determine record ID for contribution: {contribution}")

    def _get_task_id(self, contribution) -> UUID:
        """Extract task ID from contribution object."""
        if hasattr(contribution, "task_id"):
            return contribution.task_id
        raise ValueError(f"Cannot determine task ID for contribution: {contribution}")

    # ========================================================================
    # SCRUBBING METHODS - INTENTIONALLY DO NOT EXIST
    # ========================================================================
    #
    # The following methods DO NOT EXIST by design (ledger immutability):
    #
    # async def delete_contributions(self, cluster_id: UUID) -> None:
    #     '''Would delete contributions - NO DELETION ALLOWED'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def remove_contributions(self, cluster_id: UUID) -> None:
    #     '''Would remove contributions - NO REMOVAL ALLOWED'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def scrub_history(self, cluster_id: UUID) -> None:
    #     '''Would scrub history - NO SCRUBBING ALLOWED'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def scrub_contributions(self, cluster_id: UUID) -> None:
    #     '''Would scrub contributions - NO SCRUBBING ALLOWED'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def modify_contributions(self, ...) -> None:
    #     '''Would modify contributions - NO MODIFICATION ALLOWED'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def handle_delete_request(self, ...) -> None:
    #     '''Would handle GDPR-style deletion - NOT APPLICABLE'''
    #     # Contributions use pseudonymous attribution (UUIDs)
    #     # No PII is stored, so GDPR right-to-be-forgotten does not apply
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # If these methods are ever added, Knight should observe and record
    # as a CONSTITUTIONAL VIOLATION.
    # ========================================================================
