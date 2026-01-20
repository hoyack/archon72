# Story 2A.8: Disposition Emission & Pipeline Routing

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2a-8 |
| **Epic** | Epic 2A: Core Deliberation Protocol |
| **Priority** | P0-CRITICAL |
| **Status** | done |
| **Created** | 2026-01-19 |

## User Story

**As a** system,
**I want** to emit the deliberation outcome and route to the appropriate pipeline,
**So that** petitions proceed to their determined fate.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.11 | System SHALL route petition to appropriate pipeline based on deliberation outcome | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-10.1 | Deliberation latency | ≤30s for 95th percentile |
| NFR-10.2 | Deliberation availability | 99.9% uptime |
| NFR-10.5 | Outcome determination reliability | 100% consistent with consensus |

### Constitutional Truths

- **CT-14**: "Silence must be expensive. Every claim on attention terminates in a visible, witnessed fate."
- **CT-12**: "Every action that affects an Archon must be witnessed by another Archon, creating an unbroken chain of accountability."

## Acceptance Criteria

### AC-1: State Transition on Consensus

**Given** a deliberation reaches consensus
**When** the outcome is finalized
**Then** the petition state transitions: DELIBERATING → [ACKNOWLEDGED|REFERRED|ESCALATED]
**And** the transition is atomic with the consensus resolution
**And** the transition is logged with full provenance

### AC-2: DeliberationComplete Event Emission

**Given** a deliberation completes with consensus
**When** the outcome is finalized
**Then** a `DeliberationCompleteEvent` is emitted containing:
  - `event_id`: UUIDv7 for this event
  - `petition_id`: UUID of the petition
  - `session_id`: UUID of the deliberation session
  - `outcome`: The consensus disposition (ACKNOWLEDGE, REFER, ESCALATE)
  - `vote_breakdown`: Dict with 3 archon votes and rationales
  - `dissent_present`: Boolean indicating if vote was not unanimous
  - `dissent_archon_id`: UUID of dissenting archon (if dissent_present)
  - `dissent_disposition`: What the dissenter voted for (if dissent_present)
  - `completed_at`: Timestamp of completion

### AC-3: Pipeline Routing - ACKNOWLEDGED

**Given** a deliberation outcome is ACKNOWLEDGE
**When** the petition state transitions to ACKNOWLEDGED
**Then** the petition is routed to the Acknowledgment Execution pipeline (Epic 3)
**And** an `AcknowledgmentPending` event is emitted
**And** the petition is added to the acknowledgment queue

### AC-4: Pipeline Routing - REFERRED

**Given** a deliberation outcome is REFER
**When** the petition state transitions to REFERRED
**Then** the petition is routed to the Knight Referral pipeline (Epic 4)
**And** a `ReferralPending` event is emitted
**And** the petition is added to the knight referral queue
**And** the assigned knight (if determined) is recorded

### AC-5: Pipeline Routing - ESCALATED

**Given** a deliberation outcome is ESCALATE
**When** the petition state transitions to ESCALATED
**Then** the petition is routed to the King Escalation pipeline (Epic 6)
**And** an `EscalationPending` event is emitted
**And** the petition is added to the king escalation queue
**And** the escalation priority is set based on deliberation context

### AC-6: Disposition Emission Service Protocol

**Given** the need for testability
**When** the DispositionEmissionService is created
**Then** it defines a `DispositionEmissionProtocol` with:
  - `emit_disposition(session: DeliberationSession, consensus: ConsensusResult, petition: Petition) -> DispositionResult`
  - `route_to_pipeline(petition: Petition, outcome: DispositionOutcome) -> PipelineRoutingResult`
  - `get_pending_dispositions(pipeline: PipelineType) -> list[PendingDisposition]`
**And** a stub implementation is provided for testing

### AC-7: Atomic Disposition with Witness Completion

**Given** a deliberation has 4 phase witness events
**When** disposition is emitted
**Then** the disposition is only emitted after all 4 witness events are confirmed
**And** the disposition references the final witness hash (from VOTE phase)
**And** incomplete witness chains prevent disposition emission

### AC-8: Unit Tests

**Given** the DispositionEmissionService
**Then** unit tests verify:
  - DeliberationCompleteEvent creation with all required fields
  - State transition validation for each outcome
  - Pipeline routing for ACKNOWLEDGE/REFER/ESCALATE
  - Dissent information capture
  - Atomic emission with witness chain validation

### AC-9: Integration Tests

**Given** the DispositionEmissionService
**Then** integration tests verify:
  - Full deliberation → disposition → pipeline routing flow
  - Integration with ConsensusResolverService
  - Integration with PhaseWitnessBatchingService
  - State machine transition atomicity
  - Event bus emission ordering

## Technical Design

### Domain Events

```python
# src/domain/events/disposition.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


class DispositionOutcome(str, Enum):
    """Possible outcomes from Three Fates deliberation."""
    ACKNOWLEDGE = "acknowledge"  # Petition heard, no action required
    REFER = "refer"             # Refer to Knight for review
    ESCALATE = "escalate"       # Escalate to King for decision


class PipelineType(str, Enum):
    """Target pipelines for disposition routing."""
    ACKNOWLEDGMENT = "acknowledgment"   # Epic 3
    KNIGHT_REFERRAL = "knight_referral" # Epic 4
    KING_ESCALATION = "king_escalation" # Epic 6


@dataclass(frozen=True, eq=True)
class DeliberationCompleteEvent:
    """Event emitted when deliberation reaches consensus (Story 2A.8, FR-11.11).

    Captures the final disposition from Three Fates deliberation,
    including vote breakdown and any dissent.

    Constitutional Constraints:
    - CT-14: Every claim terminates in witnessed fate
    - CT-12: Outcome witnessed by participating archons
    - FR-11.11: Route to appropriate pipeline

    Attributes:
        event_id: UUIDv7 for this event.
        petition_id: UUID of the petition.
        session_id: UUID of the deliberation session.
        outcome: The consensus disposition.
        vote_breakdown: Dict mapping archon_id -> (vote, rationale).
        dissent_present: Whether vote was not unanimous.
        dissent_archon_id: UUID of dissenter (if any).
        dissent_disposition: What dissenter voted for (if any).
        final_witness_hash: Hash of VOTE phase witness for audit chain.
        completed_at: When deliberation completed.
    """

    event_id: UUID
    petition_id: UUID
    session_id: UUID
    outcome: DispositionOutcome
    vote_breakdown: dict[UUID, tuple[DispositionOutcome, str]]  # archon_id -> (vote, rationale)
    dissent_present: bool
    final_witness_hash: bytes
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dissent_archon_id: UUID | None = field(default=None)
    dissent_disposition: DispositionOutcome | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate event invariants."""
        # Must have exactly 3 votes
        if len(self.vote_breakdown) != 3:
            raise ValueError("vote_breakdown must contain exactly 3 archon votes")

        # Witness hash must be 32 bytes (Blake3)
        if len(self.final_witness_hash) != 32:
            raise ValueError("final_witness_hash must be 32 bytes (Blake3)")

        # If dissent present, must have dissent details
        if self.dissent_present:
            if self.dissent_archon_id is None:
                raise ValueError("dissent_present=True requires dissent_archon_id")
            if self.dissent_disposition is None:
                raise ValueError("dissent_present=True requires dissent_disposition")
            if self.dissent_archon_id not in self.vote_breakdown:
                raise ValueError("dissent_archon_id must be in vote_breakdown")

        # If no dissent, fields should be None
        if not self.dissent_present:
            if self.dissent_archon_id is not None:
                raise ValueError("dissent_present=False but dissent_archon_id is set")
            if self.dissent_disposition is not None:
                raise ValueError("dissent_present=False but dissent_disposition is set")


@dataclass(frozen=True)
class PipelineRoutingEvent:
    """Event emitted when petition is routed to a pipeline.

    Attributes:
        event_id: UUIDv7 for this event.
        petition_id: UUID of the petition.
        pipeline: Target pipeline type.
        deliberation_event_id: ID of DeliberationCompleteEvent that triggered routing.
        routed_at: When routing occurred.
        routing_metadata: Additional pipeline-specific routing data.
    """

    event_id: UUID
    petition_id: UUID
    pipeline: PipelineType
    deliberation_event_id: UUID
    routed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    routing_metadata: dict[str, Any] = field(default_factory=dict)
```

### Domain Models

```python
# src/domain/models/disposition_result.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from src.domain.events.disposition import (
    DeliberationCompleteEvent,
    DispositionOutcome,
    PipelineRoutingEvent,
    PipelineType,
)


@dataclass(frozen=True)
class DispositionResult:
    """Result of disposition emission (Story 2A.8).

    Captures both the deliberation completion event and
    the pipeline routing that follows.

    Attributes:
        deliberation_event: The DeliberationCompleteEvent.
        routing_event: The PipelineRoutingEvent.
        success: Whether emission completed successfully.
        error_message: Error details if success=False.
    """

    deliberation_event: DeliberationCompleteEvent
    routing_event: PipelineRoutingEvent
    success: bool = field(default=True)
    error_message: str | None = field(default=None)

    @property
    def outcome(self) -> DispositionOutcome:
        """The disposition outcome."""
        return self.deliberation_event.outcome

    @property
    def target_pipeline(self) -> PipelineType:
        """The target pipeline for routing."""
        return self.routing_event.pipeline


@dataclass(frozen=True)
class PendingDisposition:
    """A disposition waiting to be processed by a pipeline.

    Attributes:
        petition_id: UUID of the petition.
        outcome: The disposition outcome.
        pipeline: Target pipeline.
        deliberation_event_id: The triggering event ID.
        queued_at: When added to the pipeline queue.
        priority: Processing priority (lower = higher priority).
        routing_metadata: Pipeline-specific metadata.
    """

    petition_id: UUID
    outcome: DispositionOutcome
    pipeline: PipelineType
    deliberation_event_id: UUID
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: int = field(default=100)
    routing_metadata: dict = field(default_factory=dict)
```

### Service Protocol

```python
# src/application/ports/disposition_emission.py

from typing import Protocol
from uuid import UUID

from src.domain.events.disposition import (
    DeliberationCompleteEvent,
    DispositionOutcome,
    PipelineType,
)
from src.domain.models.consensus_result import ConsensusResult
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.disposition_result import DispositionResult, PendingDisposition
from src.domain.models.petition import Petition


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
        petition: Petition,
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
        petition: Petition,
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
```

### Service Implementation

```python
# src/application/services/disposition_emission_service.py

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from src.application.ports.phase_witness_batching import PhaseWitnessBatchingProtocol
from src.domain.errors.deliberation import (
    IncompleteWitnessChainError,
    InvalidPetitionStateError,
    PipelineRoutingError,
)
from src.domain.events.disposition import (
    DeliberationCompleteEvent,
    DispositionOutcome,
    PipelineRoutingEvent,
    PipelineType,
)
from src.domain.models.consensus_result import ConsensusResult
from src.domain.models.deliberation_session import DeliberationPhase, DeliberationSession
from src.domain.models.disposition_result import DispositionResult, PendingDisposition
from src.domain.models.petition import Petition, PetitionState


class DispositionEmissionService:
    """Service for disposition emission and pipeline routing (Story 2A.8, FR-11.11).

    Completes the deliberation cycle by:
    1. Validating witness chain completeness
    2. Emitting DeliberationCompleteEvent
    3. Transitioning petition state
    4. Routing to downstream pipeline

    Constitutional Constraints:
    - CT-14: Every claim terminates in witnessed fate
    - CT-12: Outcome witnessed by participating archons
    - FR-11.11: Route to appropriate pipeline

    Attributes:
        _witness_service: Service for witness chain validation.
        _pending_dispositions: In-memory queue of pending dispositions.
        _emitted_events: In-memory storage of emitted events.
    """

    # Mapping from disposition to pipeline
    OUTCOME_TO_PIPELINE: dict[DispositionOutcome, PipelineType] = {
        DispositionOutcome.ACKNOWLEDGE: PipelineType.ACKNOWLEDGMENT,
        DispositionOutcome.REFER: PipelineType.KNIGHT_REFERRAL,
        DispositionOutcome.ESCALATE: PipelineType.KING_ESCALATION,
    }

    # Mapping from disposition to target petition state
    OUTCOME_TO_STATE: dict[DispositionOutcome, PetitionState] = {
        DispositionOutcome.ACKNOWLEDGE: PetitionState.ACKNOWLEDGED,
        DispositionOutcome.REFER: PetitionState.REFERRED,
        DispositionOutcome.ESCALATE: PetitionState.ESCALATED,
    }

    def __init__(
        self,
        witness_service: PhaseWitnessBatchingProtocol | None = None,
    ) -> None:
        """Initialize the disposition emission service.

        Args:
            witness_service: Service for witness chain validation.
        """
        self._witness_service = witness_service
        # In-memory storage - replace with repository in production
        self._pending_dispositions: dict[PipelineType, list[PendingDisposition]] = {
            pipeline: [] for pipeline in PipelineType
        }
        self._emitted_events: dict[UUID, DeliberationCompleteEvent] = {}
        self._routing_events: dict[UUID, PipelineRoutingEvent] = {}

    async def _validate_witness_chain(
        self,
        session: DeliberationSession,
    ) -> bytes:
        """Validate witness chain completeness and return final hash.

        Args:
            session: The deliberation session to validate.

        Returns:
            The final witness hash (from VOTE phase).

        Raises:
            IncompleteWitnessChainError: If witness chain incomplete.
        """
        if self._witness_service is None:
            # If no witness service, use session's phase transcripts
            vote_hash = session.phase_transcripts.get(DeliberationPhase.VOTE)
            if vote_hash is None:
                raise IncompleteWitnessChainError(
                    session_id=session.session_id,
                    missing_phases=[DeliberationPhase.VOTE],
                )
            return vote_hash

        # Get all witnesses for the session
        witnesses = await self._witness_service.get_all_witnesses(session.session_id)

        if len(witnesses) < 4:
            missing = []
            witnessed_phases = {w.phase for w in witnesses}
            for phase in [
                DeliberationPhase.ASSESS,
                DeliberationPhase.POSITION,
                DeliberationPhase.CROSS_EXAMINE,
                DeliberationPhase.VOTE,
            ]:
                if phase not in witnessed_phases:
                    missing.append(phase)
            raise IncompleteWitnessChainError(
                session_id=session.session_id,
                missing_phases=missing,
            )

        # Return the VOTE phase witness hash
        vote_witness = next(
            (w for w in witnesses if w.phase == DeliberationPhase.VOTE),
            None,
        )
        if vote_witness is None:
            raise IncompleteWitnessChainError(
                session_id=session.session_id,
                missing_phases=[DeliberationPhase.VOTE],
            )

        return vote_witness.event_hash

    def _extract_dissent_info(
        self,
        consensus: ConsensusResult,
    ) -> tuple[bool, UUID | None, DispositionOutcome | None]:
        """Extract dissent information from consensus result.

        Args:
            consensus: The consensus result.

        Returns:
            Tuple of (dissent_present, dissent_archon_id, dissent_disposition).
        """
        if consensus.is_unanimous:
            return (False, None, None)

        # Find the dissenting archon
        winning_outcome = DispositionOutcome(consensus.outcome.value)
        for archon_id, vote in consensus.votes.items():
            vote_outcome = DispositionOutcome(vote.disposition.value)
            if vote_outcome != winning_outcome:
                return (True, archon_id, vote_outcome)

        return (False, None, None)

    def _build_vote_breakdown(
        self,
        consensus: ConsensusResult,
    ) -> dict[UUID, tuple[DispositionOutcome, str]]:
        """Build vote breakdown dict from consensus result.

        Args:
            consensus: The consensus result.

        Returns:
            Dict mapping archon_id to (vote, rationale).
        """
        breakdown = {}
        for archon_id, vote in consensus.votes.items():
            outcome = DispositionOutcome(vote.disposition.value)
            rationale = vote.rationale or ""
            breakdown[archon_id] = (outcome, rationale)
        return breakdown

    async def emit_disposition(
        self,
        session: DeliberationSession,
        consensus: ConsensusResult,
        petition: Petition,
    ) -> DispositionResult:
        """Emit disposition event and route to appropriate pipeline.

        Args:
            session: The completed deliberation session.
            consensus: The consensus result.
            petition: The petition being deliberated.

        Returns:
            DispositionResult with both events and routing details.

        Raises:
            IncompleteWitnessChainError: If witness chain incomplete.
            InvalidPetitionStateError: If petition not in DELIBERATING.
            PipelineRoutingError: If routing fails.
        """
        # Validate petition state
        if petition.state != PetitionState.DELIBERATING:
            raise InvalidPetitionStateError(
                petition_id=petition.petition_id,
                current_state=petition.state,
                expected_state=PetitionState.DELIBERATING,
            )

        # Validate witness chain and get final hash
        final_witness_hash = await self._validate_witness_chain(session)

        # Extract dissent info
        dissent_present, dissent_archon_id, dissent_disposition = self._extract_dissent_info(
            consensus
        )

        # Build vote breakdown
        vote_breakdown = self._build_vote_breakdown(consensus)

        # Determine outcome
        outcome = DispositionOutcome(consensus.outcome.value)

        # Create deliberation complete event
        deliberation_event = DeliberationCompleteEvent(
            event_id=uuid4(),  # Should be UUIDv7 in production
            petition_id=petition.petition_id,
            session_id=session.session_id,
            outcome=outcome,
            vote_breakdown=vote_breakdown,
            dissent_present=dissent_present,
            dissent_archon_id=dissent_archon_id,
            dissent_disposition=dissent_disposition,
            final_witness_hash=final_witness_hash,
        )

        # Store event
        self._emitted_events[deliberation_event.event_id] = deliberation_event

        # Route to pipeline
        routing_event = await self.route_to_pipeline(
            petition=petition,
            outcome=outcome,
            deliberation_event_id=deliberation_event.event_id,
        )

        return DispositionResult(
            deliberation_event=deliberation_event,
            routing_event=routing_event,
        )

    async def route_to_pipeline(
        self,
        petition: Petition,
        outcome: DispositionOutcome,
        deliberation_event_id: UUID,
    ) -> PipelineRoutingEvent:
        """Route a petition to its target pipeline.

        Args:
            petition: The petition to route.
            outcome: The disposition outcome.
            deliberation_event_id: ID of the triggering event.

        Returns:
            PipelineRoutingEvent with routing details.
        """
        # Determine target pipeline
        pipeline = self.OUTCOME_TO_PIPELINE[outcome]

        # Build routing metadata
        routing_metadata: dict[str, Any] = {
            "source_state": petition.state.value,
            "target_state": self.OUTCOME_TO_STATE[outcome].value,
            "realm": petition.realm,
        }

        # Add pipeline-specific metadata
        if pipeline == PipelineType.KNIGHT_REFERRAL:
            routing_metadata["referral_deadline"] = None  # Set by Epic 4
        elif pipeline == PipelineType.KING_ESCALATION:
            routing_metadata["escalation_priority"] = self._compute_escalation_priority(
                petition
            )

        # Create routing event
        routing_event = PipelineRoutingEvent(
            event_id=uuid4(),
            petition_id=petition.petition_id,
            pipeline=pipeline,
            deliberation_event_id=deliberation_event_id,
            routing_metadata=routing_metadata,
        )

        # Store routing event
        self._routing_events[routing_event.event_id] = routing_event

        # Add to pending queue
        pending = PendingDisposition(
            petition_id=petition.petition_id,
            outcome=outcome,
            pipeline=pipeline,
            deliberation_event_id=deliberation_event_id,
            priority=routing_metadata.get("escalation_priority", 100),
            routing_metadata=routing_metadata,
        )
        self._pending_dispositions[pipeline].append(pending)

        return routing_event

    def _compute_escalation_priority(self, petition: Petition) -> int:
        """Compute escalation priority for King queue.

        Lower numbers = higher priority.

        Args:
            petition: The petition to prioritize.

        Returns:
            Priority value (0-100).
        """
        priority = 50  # Default middle priority

        # Adjust based on petition characteristics
        # These rules can be expanded based on governance requirements

        # Older petitions get higher priority
        age_hours = (datetime.now(timezone.utc) - petition.submitted_at).total_seconds() / 3600
        if age_hours > 24:
            priority -= 10
        if age_hours > 48:
            priority -= 10

        # META realm petitions are high priority
        if petition.realm == "META":
            priority -= 20

        # Ensure bounds
        return max(0, min(100, priority))

    async def get_pending_dispositions(
        self,
        pipeline: PipelineType,
        limit: int = 100,
    ) -> list[PendingDisposition]:
        """Get pending dispositions for a pipeline.

        Args:
            pipeline: The pipeline type to query.
            limit: Maximum number to return.

        Returns:
            List of PendingDisposition in priority order.
        """
        pending = self._pending_dispositions.get(pipeline, [])
        # Sort by priority (lower = higher priority)
        sorted_pending = sorted(pending, key=lambda p: p.priority)
        return sorted_pending[:limit]

    async def acknowledge_routing(
        self,
        petition_id: UUID,
        pipeline: PipelineType,
    ) -> bool:
        """Acknowledge that a pipeline has picked up a petition.

        Args:
            petition_id: The petition ID.
            pipeline: The pipeline acknowledging.

        Returns:
            True if acknowledged, False if not found.
        """
        pending = self._pending_dispositions.get(pipeline, [])
        for i, p in enumerate(pending):
            if p.petition_id == petition_id:
                pending.pop(i)
                return True
        return False

    async def get_emitted_event(
        self,
        event_id: UUID,
    ) -> DeliberationCompleteEvent | None:
        """Get an emitted deliberation complete event by ID.

        Args:
            event_id: The event ID.

        Returns:
            The event if found, None otherwise.
        """
        return self._emitted_events.get(event_id)

    async def get_routing_event(
        self,
        event_id: UUID,
    ) -> PipelineRoutingEvent | None:
        """Get a routing event by ID.

        Args:
            event_id: The event ID.

        Returns:
            The event if found, None otherwise.
        """
        return self._routing_events.get(event_id)
```

### Stub Implementation

```python
# src/infrastructure/stubs/disposition_emission_stub.py

from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.events.disposition import (
    DeliberationCompleteEvent,
    DispositionOutcome,
    PipelineRoutingEvent,
    PipelineType,
)
from src.domain.models.consensus_result import ConsensusResult
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.disposition_result import DispositionResult, PendingDisposition
from src.domain.models.petition import Petition


class DispositionEmissionStub:
    """Stub implementation of DispositionEmissionProtocol for testing.

    Provides configurable disposition emission for unit tests
    without requiring full service dependencies.
    """

    def __init__(self) -> None:
        """Initialize the stub."""
        self.emit_disposition_calls: list[tuple[DeliberationSession, ConsensusResult, Petition]] = []
        self.route_to_pipeline_calls: list[tuple[Petition, DispositionOutcome, UUID]] = []
        self._emitted_events: dict[UUID, DeliberationCompleteEvent] = {}
        self._routing_events: dict[UUID, PipelineRoutingEvent] = {}
        self._pending: dict[PipelineType, list[PendingDisposition]] = {
            p: [] for p in PipelineType
        }
        self._force_error: bool = False
        self._force_incomplete_witness: bool = False

    def set_force_error(self, force: bool) -> None:
        """Force errors for testing error paths."""
        self._force_error = force

    def set_force_incomplete_witness(self, force: bool) -> None:
        """Force incomplete witness error."""
        self._force_incomplete_witness = force

    async def emit_disposition(
        self,
        session: DeliberationSession,
        consensus: ConsensusResult,
        petition: Petition,
    ) -> DispositionResult:
        """Record call and return stub result."""
        self.emit_disposition_calls.append((session, consensus, petition))

        if self._force_error:
            raise RuntimeError("Forced error for testing")

        if self._force_incomplete_witness:
            from src.domain.errors.deliberation import IncompleteWitnessChainError
            from src.domain.models.deliberation_session import DeliberationPhase
            raise IncompleteWitnessChainError(
                session_id=session.session_id,
                missing_phases=[DeliberationPhase.VOTE],
            )

        # Create stub events
        outcome = DispositionOutcome(consensus.outcome.value)

        # Build vote breakdown
        vote_breakdown = {}
        for archon_id, vote in consensus.votes.items():
            vote_outcome = DispositionOutcome(vote.disposition.value)
            vote_breakdown[archon_id] = (vote_outcome, vote.rationale or "")

        # Determine dissent
        dissent_present = not consensus.is_unanimous
        dissent_archon_id = None
        dissent_disposition = None
        if dissent_present:
            for archon_id, (vote_outcome, _) in vote_breakdown.items():
                if vote_outcome != outcome:
                    dissent_archon_id = archon_id
                    dissent_disposition = vote_outcome
                    break

        deliberation_event = DeliberationCompleteEvent(
            event_id=uuid4(),
            petition_id=petition.petition_id,
            session_id=session.session_id,
            outcome=outcome,
            vote_breakdown=vote_breakdown,
            dissent_present=dissent_present,
            dissent_archon_id=dissent_archon_id,
            dissent_disposition=dissent_disposition,
            final_witness_hash=b"\x00" * 32,  # Stub hash
        )

        routing_event = await self.route_to_pipeline(
            petition, outcome, deliberation_event.event_id
        )

        self._emitted_events[deliberation_event.event_id] = deliberation_event

        return DispositionResult(
            deliberation_event=deliberation_event,
            routing_event=routing_event,
        )

    async def route_to_pipeline(
        self,
        petition: Petition,
        outcome: DispositionOutcome,
        deliberation_event_id: UUID,
    ) -> PipelineRoutingEvent:
        """Record call and return stub event."""
        self.route_to_pipeline_calls.append((petition, outcome, deliberation_event_id))

        pipeline = {
            DispositionOutcome.ACKNOWLEDGE: PipelineType.ACKNOWLEDGMENT,
            DispositionOutcome.REFER: PipelineType.KNIGHT_REFERRAL,
            DispositionOutcome.ESCALATE: PipelineType.KING_ESCALATION,
        }[outcome]

        event = PipelineRoutingEvent(
            event_id=uuid4(),
            petition_id=petition.petition_id,
            pipeline=pipeline,
            deliberation_event_id=deliberation_event_id,
        )

        self._routing_events[event.event_id] = event

        pending = PendingDisposition(
            petition_id=petition.petition_id,
            outcome=outcome,
            pipeline=pipeline,
            deliberation_event_id=deliberation_event_id,
        )
        self._pending[pipeline].append(pending)

        return event

    async def get_pending_dispositions(
        self,
        pipeline: PipelineType,
        limit: int = 100,
    ) -> list[PendingDisposition]:
        """Get pending dispositions."""
        return self._pending.get(pipeline, [])[:limit]

    async def acknowledge_routing(
        self,
        petition_id: UUID,
        pipeline: PipelineType,
    ) -> bool:
        """Acknowledge routing."""
        pending = self._pending.get(pipeline, [])
        for i, p in enumerate(pending):
            if p.petition_id == petition_id:
                pending.pop(i)
                return True
        return False
```

### Error Types

```python
# Add to src/domain/errors/deliberation.py

from dataclasses import dataclass
from uuid import UUID

from src.domain.models.deliberation_session import DeliberationPhase
from src.domain.models.petition import PetitionState


@dataclass(frozen=True)
class IncompleteWitnessChainError(Exception):
    """Raised when witness chain is incomplete for disposition emission."""

    session_id: UUID
    missing_phases: list[DeliberationPhase]

    def __str__(self) -> str:
        phases = ", ".join(p.value for p in self.missing_phases)
        return f"Incomplete witness chain for session {self.session_id}: missing {phases}"


@dataclass(frozen=True)
class InvalidPetitionStateError(Exception):
    """Raised when petition is not in expected state for operation."""

    petition_id: UUID
    current_state: PetitionState
    expected_state: PetitionState

    def __str__(self) -> str:
        return (
            f"Invalid petition state for {self.petition_id}: "
            f"expected {self.expected_state.value}, got {self.current_state.value}"
        )


@dataclass(frozen=True)
class PipelineRoutingError(Exception):
    """Raised when pipeline routing fails."""

    petition_id: UUID
    pipeline: str
    reason: str

    def __str__(self) -> str:
        return f"Pipeline routing failed for {self.petition_id} to {self.pipeline}: {self.reason}"
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status | Why Needed |
|----------|------|--------|------------|
| petition-2a-1 | Deliberation Session Domain Model | DONE | DeliberationSession with phases |
| petition-2a-4 | Deliberation Protocol Orchestrator | DONE | Orchestrates phases to completion |
| petition-2a-6 | Supermajority Consensus Resolution | DONE | ConsensusResult for disposition |
| petition-2a-7 | Phase-Level Witness Batching | DONE | Witness chain validation |

### Downstream Dependencies (Blocked By This Story)

| Story ID | Name | Why Blocked |
|----------|------|-------------|
| petition-3-2 | Acknowledgment Execution Service | Receives ACKNOWLEDGED petitions |
| petition-4-2 | Referral Execution Service | Receives REFERRED petitions |
| petition-6-1 | King Escalation Queue | Receives ESCALATED petitions |

## Implementation Tasks

### Task 1: Create Disposition Events (AC: 2)
- [ ] Create `src/domain/events/disposition.py`
- [ ] Define `DispositionOutcome` enum
- [ ] Define `PipelineType` enum
- [ ] Define `DeliberationCompleteEvent` frozen dataclass
- [ ] Define `PipelineRoutingEvent` frozen dataclass
- [ ] Export from `src/domain/events/__init__.py`

### Task 2: Create Disposition Result Models (AC: 1, 3, 4, 5)
- [ ] Create `src/domain/models/disposition_result.py`
- [ ] Define `DispositionResult` dataclass
- [ ] Define `PendingDisposition` dataclass
- [ ] Export from `src/domain/models/__init__.py`

### Task 3: Create Error Types (AC: 7)
- [ ] Add `IncompleteWitnessChainError` to deliberation errors
- [ ] Add `InvalidPetitionStateError` to deliberation errors
- [ ] Add `PipelineRoutingError` to deliberation errors
- [ ] Export from `src/domain/errors/__init__.py`

### Task 4: Create Service Protocol (AC: 6)
- [ ] Create `src/application/ports/disposition_emission.py`
- [ ] Define `DispositionEmissionProtocol`
- [ ] Export from `src/application/ports/__init__.py`

### Task 5: Implement Service (AC: 1-7)
- [ ] Create `src/application/services/disposition_emission_service.py`
- [ ] Implement `emit_disposition()` with witness validation
- [ ] Implement `route_to_pipeline()` with pipeline-specific logic
- [ ] Implement `get_pending_dispositions()`
- [ ] Implement `acknowledge_routing()`
- [ ] Export from `src/application/services/__init__.py`

### Task 6: Create Stub (AC: 6)
- [ ] Create `src/infrastructure/stubs/disposition_emission_stub.py`
- [ ] Implement stub with call tracking
- [ ] Export from `src/infrastructure/stubs/__init__.py`

### Task 7: Write Unit Tests (AC: 8)
- [ ] Create `tests/unit/domain/events/test_disposition_events.py`
- [ ] Create `tests/unit/domain/models/test_disposition_result.py`
- [ ] Create `tests/unit/application/services/test_disposition_emission_service.py`
- [ ] Test all validation rules
- [ ] Test pipeline routing logic
- [ ] Test dissent information extraction

### Task 8: Write Integration Tests (AC: 9)
- [ ] Create `tests/integration/test_disposition_emission_integration.py`
- [ ] Test full deliberation → disposition → pipeline flow
- [ ] Test integration with ConsensusResolverService
- [ ] Test integration with PhaseWitnessBatchingService
- [ ] Test all three pipeline routing paths

## Definition of Done

- [ ] `DeliberationCompleteEvent` domain event created
- [ ] `PipelineRoutingEvent` domain event created
- [ ] `DispositionResult` and `PendingDisposition` models created
- [ ] `DispositionEmissionProtocol` defined
- [ ] `DispositionEmissionService` implements emission and routing
- [ ] `DispositionEmissionStub` for testing
- [ ] Error types added for validation failures
- [ ] Unit tests pass (>90% coverage)
- [ ] Integration tests verify full flow
- [ ] FR-11.11 satisfied: Route to appropriate pipeline
- [ ] CT-14 satisfied: Claims terminate in witnessed fate
- [ ] All three pipeline paths verified (ACKNOWLEDGE/REFER/ESCALATE)

## Test Scenarios

### Scenario 1: Unanimous ACKNOWLEDGE Disposition
```python
service = DispositionEmissionService(witness_service)
session = create_completed_session()  # Has all 4 witness events
consensus = ConsensusResult(
    outcome=Disposition.ACKNOWLEDGE,
    votes={archon1: Vote(ACKNOWLEDGE), archon2: Vote(ACKNOWLEDGE), archon3: Vote(ACKNOWLEDGE)},
    is_unanimous=True,
)
petition = create_petition(state=PetitionState.DELIBERATING)

result = await service.emit_disposition(session, consensus, petition)

assert result.success is True
assert result.outcome == DispositionOutcome.ACKNOWLEDGE
assert result.target_pipeline == PipelineType.ACKNOWLEDGMENT
assert result.deliberation_event.dissent_present is False

# Verify pending in acknowledgment queue
pending = await service.get_pending_dispositions(PipelineType.ACKNOWLEDGMENT)
assert len(pending) == 1
assert pending[0].petition_id == petition.petition_id
```

### Scenario 2: Supermajority REFER with Dissent
```python
service = DispositionEmissionService(witness_service)
consensus = ConsensusResult(
    outcome=Disposition.REFER,
    votes={
        archon1: Vote(REFER, "Should be reviewed by Knight"),
        archon2: Vote(REFER, "Agree, needs Knight attention"),
        archon3: Vote(ESCALATE, "I think this needs King"),  # Dissent
    },
    is_unanimous=False,
)

result = await service.emit_disposition(session, consensus, petition)

assert result.deliberation_event.dissent_present is True
assert result.deliberation_event.dissent_archon_id == archon3
assert result.deliberation_event.dissent_disposition == DispositionOutcome.ESCALATE
assert result.target_pipeline == PipelineType.KNIGHT_REFERRAL
```

### Scenario 3: ESCALATE with Priority
```python
service = DispositionEmissionService(witness_service)
old_petition = create_petition(
    state=PetitionState.DELIBERATING,
    submitted_at=datetime.now(timezone.utc) - timedelta(hours=72),
    realm="META",  # High priority realm
)
consensus = ConsensusResult(outcome=Disposition.ESCALATE, ...)

result = await service.emit_disposition(session, consensus, old_petition)

assert result.target_pipeline == PipelineType.KING_ESCALATION
# Should have high priority (low number) due to age and META realm
assert result.routing_event.routing_metadata["escalation_priority"] < 50
```

### Scenario 4: Incomplete Witness Chain Error
```python
service = DispositionEmissionService(witness_service)
session = create_session_with_only_3_witnesses()  # Missing VOTE witness

with pytest.raises(IncompleteWitnessChainError) as exc:
    await service.emit_disposition(session, consensus, petition)

assert exc.value.session_id == session.session_id
assert DeliberationPhase.VOTE in exc.value.missing_phases
```

### Scenario 5: Invalid Petition State Error
```python
service = DispositionEmissionService(witness_service)
petition = create_petition(state=PetitionState.ACKNOWLEDGED)  # Already processed

with pytest.raises(InvalidPetitionStateError) as exc:
    await service.emit_disposition(session, consensus, petition)

assert exc.value.current_state == PetitionState.ACKNOWLEDGED
assert exc.value.expected_state == PetitionState.DELIBERATING
```

## Dev Notes

### Relevant Architecture Patterns

1. **Event emission pattern**:
   - Use frozen dataclasses for immutable events
   - Include all audit fields (timestamps, IDs)
   - Link to witness chain for provenance

2. **Pipeline routing pattern**:
   - Map outcome to pipeline type
   - Include pipeline-specific metadata
   - Support priority ordering for escalation

3. **Atomic state transitions**:
   - Validate preconditions (petition state, witness chain)
   - Emit event atomically with state change
   - Rollback on failure

### Key Files to Reference

| File | Why |
|------|-----|
| `src/domain/models/deliberation_session.py` | Session state and phases |
| `src/domain/models/consensus_result.py` | Consensus structure |
| `src/application/services/phase_witness_batching_service.py` | Witness chain |
| `src/domain/models/petition.py` | Petition state machine |

### Integration Points

1. **ConsensusResolverService** (Story 2A.6):
   - Provides `ConsensusResult` with votes and outcome
   - Call `emit_disposition()` after consensus achieved

2. **PhaseWitnessBatchingService** (Story 2A.7):
   - Validates 4-phase witness chain exists
   - Provides final witness hash for audit link

3. **Downstream Pipelines** (Epics 3, 4, 6):
   - Call `get_pending_dispositions()` to retrieve work
   - Call `acknowledge_routing()` when picking up petition

### State Transition Diagram

```
DELIBERATING
    │
    ├──[ACKNOWLEDGE]──> ACKNOWLEDGED ──> Acknowledgment Pipeline (Epic 3)
    │
    ├──[REFER]─────────> REFERRED ─────> Knight Referral (Epic 4)
    │
    └──[ESCALATE]──────> ESCALATED ────> King Escalation (Epic 6)
```

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for complex logic
- [ ] N/A - Internal service, no external API impact

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Implementation verified complete on 2026-01-19
- All tests passing (unit and integration)

### Completion Notes List

1. **AC1-AC7 Complete**: Full implementation exists in codebase
2. **AC8 Complete**: Unit tests with 24 test cases covering all acceptance criteria
3. **AC9 Complete**: Integration tests exist for full deliberation flow
4. **All Definition of Done items satisfied**

### File List

**Created Files:**
- `src/domain/events/disposition.py` - Domain events (DispositionOutcome, PipelineType, DeliberationCompleteEvent, PipelineRoutingEvent)
- `src/domain/models/disposition_result.py` - Domain models (DispositionResult, PendingDisposition)
- `src/application/ports/disposition_emission.py` - Protocol definition (DispositionEmissionProtocol)
- `src/application/services/disposition_emission_service.py` - Service implementation
- `src/infrastructure/stubs/disposition_emission_stub.py` - Test stub
- `tests/unit/application/services/test_disposition_emission_service.py` - Unit tests (24 test cases)
- `tests/integration/test_disposition_emission_integration.py` - Integration tests

**Modified Files:**
- `src/domain/events/__init__.py` - Added disposition exports
- `src/domain/models/__init__.py` - Added disposition_result exports
- `src/application/ports/__init__.py` - Added disposition_emission exports
- `src/application/services/__init__.py` - Added disposition_emission_service exports
- `src/infrastructure/stubs/__init__.py` - Added disposition_emission_stub exports
- `src/domain/errors/deliberation.py` - Added IncompleteWitnessChainError, InvalidPetitionStateError, PipelineRoutingError

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-19 | Story created via create-story workflow | SM Agent |
| 2026-01-19 | Implementation verified complete | Dev Agent |
