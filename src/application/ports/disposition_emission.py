"""Disposition emission protocol (Story 2A.8, FR-11.11).

This module defines the protocol for disposition emission and
pipeline routing after Three Fates deliberation completes.

Constitutional Constraints:
- CT-14: Every claim terminates in witnessed fate
- CT-12: Outcome witnessed by participating archons
- FR-11.11: Route to appropriate pipeline

Pipeline Routing:
- ACKNOWLEDGE → Acknowledgment Execution (Epic 3)
- REFER → Knight Referral Workflow (Epic 4)
- ESCALATE → King Escalation Queue (Epic 6)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.events.disposition import (
        DispositionOutcome,
        PipelineRoutingEvent,
        PipelineType,
    )
    from src.domain.models.consensus_result import ConsensusResult
    from src.domain.models.deliberation_session import DeliberationSession
    from src.domain.models.disposition_result import (
        DispositionResult,
        PendingDisposition,
    )
    from src.domain.models.petition_submission import PetitionSubmission


class DispositionEmissionProtocol(Protocol):
    """Protocol for disposition emission and pipeline routing (Story 2A.8, FR-11.11).

    Implementations emit the deliberation outcome as an event and route
    the petition to the appropriate downstream pipeline based on the
    Three Fates disposition.

    Constitutional Constraints:
    - CT-14: Every claim terminates in witnessed fate
    - CT-12: Outcome witnessed by participating archons
    - FR-11.11: Route to appropriate pipeline

    Pipeline Routing:
    - ACKNOWLEDGE → Acknowledgment Execution (Epic 3)
    - REFER → Knight Referral Workflow (Epic 4)
    - ESCALATE → King Escalation Queue (Epic 6)
    """

    async def emit_disposition(
        self,
        session: DeliberationSession,
        consensus: ConsensusResult,
        petition: PetitionSubmission,
    ) -> DispositionResult:
        """Emit disposition event and route to appropriate pipeline.

        This is the main entry point for completing a deliberation.
        It performs the following atomically:
        1. Validates witness chain is complete (4 phases)
        2. Creates DeliberationCompleteEvent
        3. Transitions petition state
        4. Routes to appropriate pipeline
        5. Creates PipelineRoutingEvent

        Args:
            session: The completed deliberation session.
            consensus: The consensus result from ConsensusResolverService.
            petition: The petition being deliberated.

        Returns:
            DispositionResult with both events and routing details.

        Raises:
            IncompleteWitnessChainError: If witness chain has < 4 phases.
            InvalidPetitionStateError: If petition not in DELIBERATING state.
            PipelineRoutingError: If routing fails.
        """
        ...

    async def route_to_pipeline(
        self,
        petition: PetitionSubmission,
        outcome: DispositionOutcome,
        deliberation_event_id: UUID,
    ) -> PipelineRoutingEvent:
        """Route a petition to its target pipeline.

        Called internally by emit_disposition, but also available
        for re-routing scenarios.

        Args:
            petition: The petition to route.
            outcome: The disposition outcome.
            deliberation_event_id: ID of the triggering event.

        Returns:
            PipelineRoutingEvent with routing details.
        """
        ...

    async def get_pending_dispositions(
        self,
        pipeline: PipelineType,
        limit: int = 100,
    ) -> list[PendingDisposition]:
        """Get pending dispositions for a pipeline.

        Used by downstream pipelines to retrieve their queued work.

        Args:
            pipeline: The pipeline type to query.
            limit: Maximum number to return.

        Returns:
            List of PendingDisposition in priority order.
        """
        ...

    async def acknowledge_routing(
        self,
        petition_id: UUID,
        pipeline: PipelineType,
    ) -> bool:
        """Acknowledge that a pipeline has picked up a petition.

        Removes the petition from pending queue.

        Args:
            petition_id: The petition ID.
            pipeline: The pipeline acknowledging.

        Returns:
            True if acknowledged, False if not found.
        """
        ...
