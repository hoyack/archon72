"""Collective output application service (Story 2.3, FR11, Story 2.4, FR12).

This module provides the application layer service for creating and
retrieving collective outputs. It orchestrates domain services and ports.

Constitutional Constraints:
- FR9: No Preview - outputs committed before viewing
- FR11: Collective outputs attributed to Conclave, not individuals
- FR12: Dissent tracking in vote tallies (Story 2.4)
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability - unanimous votes get special events
- CT-13: Integrity outranks availability

Golden Rules:
1. HALT FIRST - Check halt state before every operation
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.collective_output import (
    CollectiveOutputPort,
)
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.unanimous_vote import UnanimousVotePort
from src.application.services.dissent_health_service import DissentHealthService
from src.domain.errors import SystemHaltedError
from src.domain.events.collective_output import (
    AuthorType,
    CollectiveOutputPayload,
    VoteCounts,
)
from src.domain.events.unanimous_vote import UnanimousVotePayload, VoteOutcome
from src.domain.services.collective_output_enforcer import (
    calculate_dissent_percentage,
    is_unanimous,
    validate_collective_output,
)
from src.domain.services.no_preview_enforcer import NoPreviewEnforcer


def _compute_raw_content_hash(content: str) -> str:
    """Compute SHA-256 hash of raw content string.

    Args:
        content: The raw content string to hash.

    Returns:
        64-character hex string (SHA-256).
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

logger = get_logger()


@dataclass(frozen=True, eq=True)
class CommittedCollectiveOutput:
    """Result of successfully committing a collective output.

    Returned after a collective output has been committed to storage.

    Attributes:
        output_id: UUID of the committed output.
        event_sequence: Sequence number in the event store.
        content_hash: SHA-256 hash of the content.
        committed_at: UTC timestamp when committed.
    """

    output_id: UUID
    event_sequence: int
    content_hash: str
    committed_at: datetime


@dataclass(frozen=True, eq=True)
class ViewableCollectiveOutput:
    """A collective output ready for viewing.

    Contains aggregate information about the collective output.
    Individual vote details are NOT included (see linked events).

    Attributes:
        output_id: UUID of the output.
        author_type: Always COLLECTIVE for FR11 compliance.
        contributing_agents_count: Number of agents that contributed.
        vote_counts: Aggregate vote breakdown.
        dissent_percentage: Minority vote percentage.
        unanimous: True if 100% agreement.
        content_hash: SHA-256 hash for verification.
    """

    output_id: UUID
    author_type: AuthorType
    contributing_agents_count: int
    vote_counts: VoteCounts
    dissent_percentage: float
    unanimous: bool
    content_hash: str


class CollectiveOutputService:
    """Application service for collective output operations.

    Orchestrates the creation and retrieval of collective outputs.
    Enforces FR9 (No Preview), FR11 (Collective Attribution), and
    FR12 (Dissent Tracking).

    Dependencies injected:
    - halt_checker: For HALT FIRST rule
    - collective_output_port: For persistence
    - no_preview_enforcer: For FR9 compliance
    - unanimous_vote_port: Optional, for FR12 unanimous vote tracking
    - dissent_health_service: Optional, for FR12 dissent metrics
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        collective_output_port: CollectiveOutputPort,
        no_preview_enforcer: NoPreviewEnforcer,
        unanimous_vote_port: UnanimousVotePort | None = None,
        dissent_health_service: DissentHealthService | None = None,
    ) -> None:
        """Initialize the service with dependencies.

        Args:
            halt_checker: For checking halt state.
            collective_output_port: For persistence operations.
            no_preview_enforcer: For FR9 tracking.
            unanimous_vote_port: Optional, for storing unanimous votes (FR12).
            dissent_health_service: Optional, for tracking dissent metrics (FR12).
        """
        self._halt_checker = halt_checker
        self._port = collective_output_port
        self._no_preview_enforcer = no_preview_enforcer
        self._unanimous_vote_port = unanimous_vote_port
        self._dissent_health_service = dissent_health_service

    async def create_collective_output(
        self,
        contributing_agents: list[str],
        vote_counts: VoteCounts,
        content: str,
        linked_vote_ids: list[UUID],
    ) -> CommittedCollectiveOutput:
        """Create and commit a collective output.

        Implements FR11 (Collective Attribution) and integrates with
        FR9 (No Preview) pipeline.

        Args:
            contributing_agents: List of agent IDs that contributed.
            vote_counts: The vote breakdown.
            content: The output content to store.
            linked_vote_ids: UUIDs of linked individual vote events.

        Returns:
            CommittedCollectiveOutput with commit metadata.

        Raises:
            SystemHaltedError: If system is halted.
            FR11ViolationError: If FR11 constraints violated.
            ValueError: If payload validation fails.
        """
        # HALT FIRST (Golden Rule #1)
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            raise SystemHaltedError(f"Cannot create collective output - system halted: {reason}")

        # Generate output ID
        output_id = uuid4()

        # Compute content hash (FR9 pattern)
        content_hash = _compute_raw_content_hash(content)

        # Calculate dissent percentage and unanimity
        dissent_pct = calculate_dissent_percentage(vote_counts)
        unanimous_flag = is_unanimous(vote_counts)

        # Build payload (validates FR11 constraints in __post_init__)
        payload = CollectiveOutputPayload(
            output_id=output_id,
            author_type=AuthorType.COLLECTIVE,
            contributing_agents=tuple(contributing_agents),
            content_hash=content_hash,
            vote_counts=vote_counts,
            dissent_percentage=dissent_pct,
            unanimous=unanimous_flag,
            linked_vote_event_ids=tuple(linked_vote_ids),
        )

        # Defense in depth: validate via enforcer
        validate_collective_output(payload)

        # Sequence placeholder - actual sequence assigned by storage layer
        # Production implementation: event store assigns monotonic sequence
        # Dev stub: auto-increments internally for test isolation
        event_sequence = 0

        # Store via port
        stored = await self._port.store_collective_output(payload, event_sequence)

        # Mark committed for FR9 (No Preview)
        self._no_preview_enforcer.mark_committed(output_id, content_hash=content_hash)

        # FR12: Record dissent metric for every collective output
        if self._dissent_health_service is not None:
            await self._dissent_health_service.record_dissent(output_id, dissent_pct)

        # FR12: Create UnanimousVoteEvent if vote was unanimous
        if unanimous_flag and self._unanimous_vote_port is not None:
            await self._create_unanimous_vote_event(
                output_id=output_id,
                vote_counts=vote_counts,
            )

        logger.info(
            "collective_output_created",
            output_id=str(output_id),
            contributing_agents_count=len(contributing_agents),
            dissent_percentage=dissent_pct,
            unanimous=unanimous_flag,
            event_sequence=stored.event_sequence,
        )

        return CommittedCollectiveOutput(
            output_id=stored.output_id,
            event_sequence=stored.event_sequence,
            content_hash=stored.content_hash,
            committed_at=stored.stored_at,
        )

    async def _create_unanimous_vote_event(
        self,
        output_id: UUID,
        vote_counts: VoteCounts,
    ) -> None:
        """Create and store a UnanimousVoteEvent (FR12).

        Called when a collective output has a unanimous vote.
        Determines the outcome direction and creates the event.

        Args:
            output_id: UUID of the collective output.
            vote_counts: The vote counts to determine outcome.
        """
        if self._unanimous_vote_port is None:
            return

        # Determine outcome based on which vote type is unanimous
        outcome = self._determine_unanimous_outcome(vote_counts)

        vote_payload = UnanimousVotePayload(
            vote_id=uuid4(),
            output_id=output_id,
            vote_counts=vote_counts,
            outcome=outcome,
            voter_count=vote_counts.total,
            recorded_at=datetime.now(timezone.utc),
        )

        stored = await self._unanimous_vote_port.store_unanimous_vote(vote_payload)

        logger.info(
            "unanimous_vote_event_created",
            vote_id=str(vote_payload.vote_id),
            output_id=str(output_id),
            outcome=outcome.value,
            voter_count=vote_counts.total,
            event_sequence=stored.event_sequence,
        )

    def _determine_unanimous_outcome(self, vote_counts: VoteCounts) -> VoteOutcome:
        """Determine the outcome direction for a unanimous vote.

        Args:
            vote_counts: The vote counts.

        Returns:
            The appropriate VoteOutcome enum value.
        """
        if vote_counts.yes_count == vote_counts.total:
            return VoteOutcome.YES_UNANIMOUS
        elif vote_counts.no_count == vote_counts.total:
            return VoteOutcome.NO_UNANIMOUS
        else:
            return VoteOutcome.ABSTAIN_UNANIMOUS

    async def get_collective_output_for_viewing(
        self,
        output_id: UUID,
        viewer_id: str,
    ) -> ViewableCollectiveOutput | None:
        """Retrieve a collective output for viewing.

        Enforces FR9 (must be committed) and returns aggregate view.

        Args:
            output_id: UUID of the output to retrieve.
            viewer_id: ID of the viewer for audit trail.

        Returns:
            ViewableCollectiveOutput if found and committed, None if not found.

        Raises:
            SystemHaltedError: If system is halted.
            FR9ViolationError: If attempting to view uncommitted output (CT-11).
        """
        # HALT FIRST (Golden Rule #1)
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            raise SystemHaltedError(f"Cannot view collective output - system halted: {reason}")

        # FR9 ENFORCEMENT (CT-11: Silent failure destroys legitimacy)
        # Raises FR9ViolationError if not committed - never silently return None
        self._no_preview_enforcer.verify_committed(output_id)

        # Retrieve from storage
        payload = await self._port.get_collective_output(output_id)
        if payload is None:
            return None

        logger.info(
            "collective_output_viewed",
            output_id=str(output_id),
            viewer_id=viewer_id,
        )

        return ViewableCollectiveOutput(
            output_id=payload.output_id,
            author_type=payload.author_type,
            contributing_agents_count=len(payload.contributing_agents),
            vote_counts=payload.vote_counts,
            dissent_percentage=payload.dissent_percentage,
            unanimous=payload.unanimous,
            content_hash=payload.content_hash,
        )
