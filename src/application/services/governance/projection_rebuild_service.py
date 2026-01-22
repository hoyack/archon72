"""Projection Rebuild Service - Rebuild projections from ledger events.

Story: consent-gov-1.5: Projection Infrastructure

This service rebuilds projections from the governance ledger events,
enabling recovery from corruption or migration to new projection schemas.

CQRS-Lite Pattern (AD-9):
- Ledger is the single source of truth
- Projections are derived views that can be rebuilt at any time
- Rebuild produces identical state to incremental application

Rebuild Strategies:
- Full rebuild: Clear projection and replay all events
- Incremental rebuild: Resume from checkpoint
- Verification rebuild: Compare incremental vs full

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Rebuild Strategies (Locked)]
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from src.application.ports.governance import (
    GovernanceLedgerPort,
    LedgerReadOptions,
    ProjectionPort,
)
from src.domain.governance.events.event_envelope import GovernanceEvent

if TYPE_CHECKING:
    from src.domain.ports.time_authority import TimeAuthority


@dataclass(frozen=True)
class RebuildResult:
    """Result of a projection rebuild operation.

    Attributes:
        projection_name: Name of the rebuilt projection.
        events_processed: Number of events processed.
        start_sequence: First sequence processed (0 for full rebuild).
        end_sequence: Last sequence processed.
        started_at: When the rebuild started.
        completed_at: When the rebuild completed.
        is_full_rebuild: True if this was a full rebuild (not incremental).
    """

    projection_name: str
    events_processed: int
    start_sequence: int
    end_sequence: int
    started_at: datetime
    completed_at: datetime
    is_full_rebuild: bool

    @property
    def duration_seconds(self) -> float:
        """Get rebuild duration in seconds."""
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def events_per_second(self) -> float:
        """Get processing rate in events per second."""
        if self.duration_seconds == 0:
            return 0.0
        return self.events_processed / self.duration_seconds


@dataclass(frozen=True)
class VerificationResult:
    """Result of a projection verification operation.

    Attributes:
        projection_name: Name of the verified projection.
        is_consistent: True if incremental and full rebuild match.
        events_checked: Number of events verified.
        discrepancies: List of discrepancy descriptions (empty if consistent).
    """

    projection_name: str
    is_consistent: bool
    events_checked: int
    discrepancies: tuple[str, ...]


# Type alias for event handlers
EventHandler = Callable[[GovernanceEvent, int], Awaitable[None]]


class ProjectionRebuildService:
    """Service for rebuilding projections from ledger events.

    This service enables:
    - Full rebuild: Clear and replay all events
    - Incremental rebuild: Resume from last checkpoint
    - Verification: Compare incremental vs full

    ┌────────────────────────────────────────────────────────────────────┐
    │                    REBUILD GUARANTEES                               │
    │                                                                      │
    │  ✅ Deterministic: Same events produce same projection state        │
    │  ✅ Idempotent: Re-applying events is safe (via projection_applies) │
    │  ✅ Resumable: Can continue from checkpoint after failure           │
    │                                                                      │
    │  Ref: AD-1, NFR-AUDIT-06, governance-architecture.md                │
    └────────────────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        ledger_port: GovernanceLedgerPort,
        projection_port: ProjectionPort,
        time_authority: TimeAuthority,
        batch_size: int = 100,
    ) -> None:
        """Initialize the rebuild service.

        Args:
            ledger_port: Port for reading events from ledger.
            projection_port: Port for updating projections.
            time_authority: Time authority for timestamps.
            batch_size: Number of events to process per batch.
        """
        self._ledger_port = ledger_port
        self._projection_port = projection_port
        self._time_authority = time_authority
        self._batch_size = batch_size

        # Event handlers registered by projection name
        self._event_handlers: dict[str, EventHandler] = {}

    def register_handler(
        self,
        projection_name: str,
        handler: EventHandler,
    ) -> None:
        """Register an event handler for a projection.

        Args:
            projection_name: Name of the projection.
            handler: Async function that processes events for this projection.
        """
        self._event_handlers[projection_name] = handler

    async def rebuild_full(
        self,
        projection_name: str,
    ) -> RebuildResult:
        """Perform a full rebuild of a projection.

        Clears all projection data and replays all events from the ledger.

        Args:
            projection_name: Name of the projection to rebuild.

        Returns:
            RebuildResult with statistics.

        Raises:
            ValueError: If projection_name has no registered handler.
        """
        if projection_name not in self._event_handlers:
            raise ValueError(
                f"No handler registered for projection '{projection_name}'"
            )

        started_at = self._time_authority.now()

        # Clear the projection
        await self._projection_port.clear_projection(projection_name)

        # Get all events from ledger
        events_processed = 0
        start_sequence = 0
        end_sequence = 0

        # Process events in batches
        offset = 0
        handler = self._event_handlers[projection_name]

        while True:
            options = LedgerReadOptions(
                limit=self._batch_size,
                offset=offset,
            )
            batch = await self._ledger_port.read_events(options)

            if not batch:
                break

            for persisted_event in batch:
                # Apply event through projection port (records apply for idempotency)
                applied = await self._projection_port.apply_event(
                    projection_name,
                    persisted_event.event,
                    persisted_event.sequence,
                )

                if applied:
                    # Call the handler to actually update projection state
                    await handler(persisted_event.event, persisted_event.sequence)

                events_processed += 1
                end_sequence = persisted_event.sequence

                if events_processed == 1:
                    start_sequence = persisted_event.sequence

            # Save checkpoint after each batch
            if batch:
                last_event = batch[-1]
                await self._projection_port.save_checkpoint(
                    projection_name,
                    last_event.event_id,
                    last_event.event.hash or "",
                    last_event.sequence,
                )

            offset += len(batch)

        completed_at = self._time_authority.now()

        return RebuildResult(
            projection_name=projection_name,
            events_processed=events_processed,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            started_at=started_at,
            completed_at=completed_at,
            is_full_rebuild=True,
        )

    async def rebuild_incremental(
        self,
        projection_name: str,
    ) -> RebuildResult:
        """Perform an incremental rebuild from the last checkpoint.

        Resumes from the last processed event and applies new events.

        Args:
            projection_name: Name of the projection to rebuild.

        Returns:
            RebuildResult with statistics.

        Raises:
            ValueError: If projection_name has no registered handler.
        """
        if projection_name not in self._event_handlers:
            raise ValueError(
                f"No handler registered for projection '{projection_name}'"
            )

        started_at = self._time_authority.now()

        # Get current checkpoint
        checkpoint = await self._projection_port.get_checkpoint(projection_name)
        start_sequence = checkpoint.last_sequence + 1 if checkpoint else 0

        # Get events from checkpoint
        events_processed = 0
        end_sequence = start_sequence - 1

        handler = self._event_handlers[projection_name]

        while True:
            options = LedgerReadOptions(
                start_sequence=start_sequence + events_processed,
                limit=self._batch_size,
            )
            batch = await self._ledger_port.read_events(options)

            if not batch:
                break

            for persisted_event in batch:
                # Apply event through projection port
                applied = await self._projection_port.apply_event(
                    projection_name,
                    persisted_event.event,
                    persisted_event.sequence,
                )

                if applied:
                    await handler(persisted_event.event, persisted_event.sequence)

                events_processed += 1
                end_sequence = persisted_event.sequence

            # Save checkpoint after each batch
            if batch:
                last_event = batch[-1]
                await self._projection_port.save_checkpoint(
                    projection_name,
                    last_event.event_id,
                    last_event.event.hash or "",
                    last_event.sequence,
                )

        completed_at = self._time_authority.now()

        return RebuildResult(
            projection_name=projection_name,
            events_processed=events_processed,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            started_at=started_at,
            completed_at=completed_at,
            is_full_rebuild=False,
        )

    async def get_rebuild_status(
        self,
        projection_name: str,
    ) -> dict[str, int | str | None]:
        """Get the current rebuild status for a projection.

        Args:
            projection_name: Name of the projection.

        Returns:
            Dict with checkpoint and ledger max sequence info.
        """
        checkpoint = await self._projection_port.get_checkpoint(projection_name)
        max_sequence = await self._ledger_port.get_max_sequence()

        return {
            "projection_name": projection_name,
            "checkpoint_sequence": checkpoint.last_sequence if checkpoint else None,
            "checkpoint_event_id": str(checkpoint.last_event_id)
            if checkpoint
            else None,
            "ledger_max_sequence": max_sequence,
            "events_behind": (
                max_sequence - checkpoint.last_sequence if checkpoint else max_sequence
            ),
        }

    async def rebuild_all(self) -> list[RebuildResult]:
        """Rebuild all registered projections.

        Performs a full rebuild of every registered projection.

        Returns:
            List of RebuildResult for each projection.
        """
        results = []
        for projection_name in self._event_handlers:
            result = await self.rebuild_full(projection_name)
            results.append(result)
        return results
