# Story 2B.4: Archon Substitution on Failure

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2b-4 |
| **Epic** | Epic 2B: Deliberation Edge Cases & Guarantees |
| **Priority** | P0 |
| **Status** | done |
| **Completed** | 2026-01-19 |
| **Created** | 2026-01-19 |

## User Story

**As a** system,
**I want** to substitute an Archon that fails mid-deliberation,
**So that** deliberation can complete even if one agent becomes unavailable.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.4 | System SHALL follow structured protocol: Assess -> Position -> Cross-Examine -> Vote | P0 |
| FR-11.5 | System SHALL require supermajority consensus (2-of-3 Archons) for disposition decision | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-10.6 | Archon substitution latency | < 10 seconds on failure |
| NFR-10.2 | Individual Archon response time | p95 < 30 seconds |
| NFR-10.5 | Concurrent deliberations | 100+ simultaneous sessions |
| NFR-3.6 | System availability | 99.9% uptime |

### PRD Section Reference

- **Section 13A.5**: "Archon unavailable: Response timeout > 30 sec -> Substitute from pool"

### Constitutional Truths

- **AT-1**: Every petition terminates in exactly one of Three Fates
- **AT-6**: Deliberation is collective judgment, not unilateral decision
- **CT-11**: Silent failure destroys legitimacy - must handle failures gracefully
- **CT-14**: Silence must be expensive - every petition terminates in witnessed fate

## Acceptance Criteria

### AC-1: Individual Archon Timeout Detection

**Given** a deliberation is in progress
**When** an Archon fails to respond within 30 seconds (individual timeout, NFR-10.2)
**Then** the Archon is marked as `FAILED` status in the session
**And** the failure is logged with:
- `archon_id`
- `phase_at_failure`
- `timeout_seconds`
- `response_received` (partial or none)
**And** the substitution process is triggered immediately

### AC-2: Substitute Archon Selection

**Given** an Archon has failed mid-deliberation
**When** a substitute is required
**Then** a substitute Archon is selected from the pool:
- Selection excludes all already-assigned Archons (original 3)
- Selection excludes any previously failed Archons in this session
- Selection is deterministic given (session_id + failure_sequence_number)
**And** the selection completes within 1 second
**And** the substitute Archon is recorded in `substitute_archons` array on session

### AC-3: Substitute Context Handoff

**Given** a substitute Archon is selected
**When** the substitute is initialized
**Then** the substitute receives:
- Full context package (same as original Archons)
- Complete transcript of all phases completed so far
- Current phase state (if substitution mid-phase)
- Summary of failed Archon's partial contribution (if any)
**And** the context handoff completes within 2 seconds

### AC-4: Substitution Latency SLA

**Given** an Archon failure is detected
**When** the full substitution process completes
**Then** total substitution latency is < 10 seconds (NFR-10.6):
- Failure detection: immediate (30s timeout triggers)
- Substitute selection: < 1 second
- Context handoff: < 2 seconds
- Substitute ready to participate: < 7 seconds
**And** latency is measured and recorded in `ArchonSubstitutedEvent`

### AC-5: Substitution During VOTE Phase

**Given** an Archon fails during the VOTE phase
**When** substitution occurs
**Then** the substitute casts a new vote
**And** the failed Archon's partial vote (if any) is discarded
**And** the vote round continues with the substitute
**And** if the failed Archon had already submitted a valid vote, that vote is preserved (no substitution needed for completed votes)

### AC-6: ArchonSubstitutedEvent Emission

**Given** a successful Archon substitution
**When** the substitute is ready to participate
**Then** an `ArchonSubstitutedEvent` is emitted with:
- `session_id`
- `petition_id`
- `failed_archon_id`
- `substitute_archon_id`
- `phase_at_failure`
- `failure_reason`: "RESPONSE_TIMEOUT" | "API_ERROR" | "INVALID_RESPONSE"
- `substitution_latency_ms`
- `transcript_pages_provided` (count of transcript pages given to substitute)
- `timestamp`
**And** the event is witnessed per CT-12

### AC-7: Multi-Archon Failure Handling

**Given** 2+ Archons fail simultaneously or sequentially within a session
**When** the second failure is detected
**Then** the deliberation is terminated with outcome = ESCALATE
**And** the petition state transitions: DELIBERATING -> ESCALATED
**And** a `DeliberationAborted` event is emitted with:
- `session_id`
- `petition_id`
- `reason`: "INSUFFICIENT_ARCHONS"
- `failed_archons`: array of failed archon details
- `surviving_archon_id`: the one Archon that didn't fail (if any)
**And** constitutional requirement AT-1 is satisfied (petition reaches fate)

### AC-8: Pool Exhaustion Handling

**Given** all available Archons in the pool have either been assigned or failed
**When** another substitution is needed
**Then** the deliberation is terminated with outcome = ESCALATE
**And** a `DeliberationAborted` event is emitted with:
- `reason`: "ARCHON_POOL_EXHAUSTED"
**And** an alert is raised for operator attention

### AC-9: Session Model Substitution Tracking

**Given** the DeliberationSession model
**Then** it tracks substitution state:
- `substitute_archons`: list of (failed_id, substitute_id, phase, timestamp)
- `archon_statuses`: map of archon_id -> status (ACTIVE, FAILED, SUBSTITUTED)
- `current_active_archons`: derived list of 3 currently active archon IDs
**And** the model ensures exactly 3 active Archons at all times (or ESCALATE)

### AC-10: Idempotent Substitution

**Given** a substitution request for an already-substituted Archon
**When** the request is processed
**Then** the existing substitution is returned (idempotent)
**And** no duplicate events are emitted
**And** no errors are raised

### AC-11: Unit Tests

**Given** the Archon substitution components
**Then** unit tests verify:
- Individual Archon timeout detection
- Substitute selection excludes assigned/failed Archons
- Context handoff includes full transcript
- Substitution latency < 10 seconds
- Vote phase substitution discards partial vote
- Event emission with correct payload
- Multi-Archon failure triggers ESCALATE
- Pool exhaustion triggers ESCALATE
- Idempotent substitution handling

### AC-12: Integration Tests

**Given** the full substitution flow
**Then** integration tests verify:
- End-to-end substitution with real ArchonPool
- Database state persistence
- Event witnessing
- Deliberation continues with substitute
- Multi-failure scenario handling

## Technical Design

### Domain Events

```python
# src/domain/events/archon_substitution.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from src.domain.models.deliberation_session import DeliberationPhase


@dataclass(frozen=True, eq=True)
class ArchonSubstitutedEvent:
    """Event emitted when an Archon is substituted (NFR-10.6).

    This event is witnessed in the hash chain. Substitution ensures
    deliberation can continue despite individual agent failure.

    Attributes:
        event_type: Always "ArchonSubstituted".
        session_id: Deliberation session ID.
        petition_id: Petition ID.
        failed_archon_id: ID of the Archon that failed.
        substitute_archon_id: ID of the replacement Archon.
        phase_at_failure: Which phase the failure occurred in.
        failure_reason: Why the Archon failed.
        substitution_latency_ms: Time from failure to substitute ready.
        transcript_pages_provided: Pages of transcript given to substitute.
        emitted_at: Timestamp of event emission.
    """

    event_type: str = field(default="ArchonSubstituted", init=False)
    session_id: UUID
    petition_id: UUID
    failed_archon_id: UUID
    substitute_archon_id: UUID
    phase_at_failure: str  # Serialized DeliberationPhase
    failure_reason: str  # "RESPONSE_TIMEOUT" | "API_ERROR" | "INVALID_RESPONSE"
    substitution_latency_ms: int
    transcript_pages_provided: int
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Serialize for event emission and witnessing."""
        return {
            "event_type": self.event_type,
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "failed_archon_id": str(self.failed_archon_id),
            "substitute_archon_id": str(self.substitute_archon_id),
            "phase_at_failure": self.phase_at_failure,
            "failure_reason": self.failure_reason,
            "substitution_latency_ms": self.substitution_latency_ms,
            "transcript_pages_provided": self.transcript_pages_provided,
            "emitted_at": self.emitted_at.isoformat(),
            "schema_version": 1,
        }


@dataclass(frozen=True, eq=True)
class DeliberationAbortedEvent:
    """Event emitted when deliberation is aborted due to failures (AC-7, AC-8).

    This is a terminal event - the petition will be ESCALATED.

    Attributes:
        event_type: Always "DeliberationAborted".
        session_id: Deliberation session ID.
        petition_id: Petition ID.
        reason: "INSUFFICIENT_ARCHONS" | "ARCHON_POOL_EXHAUSTED".
        failed_archons: Details of Archons that failed.
        surviving_archon_id: ID of any Archon that didn't fail (optional).
        emitted_at: Timestamp of event emission.
    """

    event_type: str = field(default="DeliberationAborted", init=False)
    session_id: UUID
    petition_id: UUID
    reason: str  # "INSUFFICIENT_ARCHONS" | "ARCHON_POOL_EXHAUSTED"
    failed_archons: tuple[dict, ...]  # List of {archon_id, failure_reason, phase}
    surviving_archon_id: UUID | None
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Serialize for event emission and witnessing."""
        return {
            "event_type": self.event_type,
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "reason": self.reason,
            "failed_archons": list(self.failed_archons),
            "surviving_archon_id": str(self.surviving_archon_id) if self.surviving_archon_id else None,
            "emitted_at": self.emitted_at.isoformat(),
            "schema_version": 1,
        }
```

### Archon Status Enum

```python
# src/domain/models/archon_status.py

from enum import Enum


class ArchonStatus(str, Enum):
    """Status of an Archon within a deliberation session.

    Values:
        ACTIVE: Archon is actively participating.
        FAILED: Archon failed and needs substitution.
        SUBSTITUTED: Archon was substituted (original is no longer active).
    """

    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    SUBSTITUTED = "SUBSTITUTED"


class ArchonFailureReason(str, Enum):
    """Reasons an Archon may fail during deliberation.

    Values:
        RESPONSE_TIMEOUT: Archon didn't respond within 30 seconds.
        API_ERROR: CrewAI or LLM API returned an error.
        INVALID_RESPONSE: Response couldn't be parsed or was malformed.
    """

    RESPONSE_TIMEOUT = "RESPONSE_TIMEOUT"
    API_ERROR = "API_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
```

### Session Model Extension

```python
# Additions to src/domain/models/deliberation_session.py

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from src.domain.models.archon_status import ArchonStatus, ArchonFailureReason


@dataclass(frozen=True, eq=True)
class ArchonSubstitution:
    """Record of an Archon substitution within a session.

    Attributes:
        failed_archon_id: Original Archon that failed.
        substitute_archon_id: Replacement Archon.
        phase_at_failure: Phase when failure occurred.
        failure_reason: Why the original failed.
        substituted_at: When substitution occurred.
    """

    failed_archon_id: UUID
    substitute_archon_id: UUID
    phase_at_failure: str
    failure_reason: str
    substituted_at: datetime


@dataclass(frozen=True, eq=True)
class DeliberationSession:
    # ... existing fields ...

    # Substitution tracking (AC-9)
    substitute_archons: tuple[ArchonSubstitution, ...] = field(default_factory=tuple)
    archon_statuses: dict[UUID, ArchonStatus] = field(default_factory=dict)

    @property
    def current_active_archons(self) -> tuple[UUID, UUID, UUID]:
        """Get the 3 currently active Archon IDs.

        Returns the original Archons minus any that failed,
        plus their substitutes.
        """
        active = []
        for archon_id in self.assigned_archons:
            status = self.archon_statuses.get(archon_id, ArchonStatus.ACTIVE)
            if status == ArchonStatus.ACTIVE:
                active.append(archon_id)
            elif status == ArchonStatus.SUBSTITUTED:
                # Find the substitute
                for sub in self.substitute_archons:
                    if sub.failed_archon_id == archon_id:
                        active.append(sub.substitute_archon_id)
                        break
        return tuple(active)  # type: ignore

    @property
    def failed_archon_count(self) -> int:
        """Count of Archons that have failed."""
        return sum(
            1 for status in self.archon_statuses.values()
            if status == ArchonStatus.FAILED
        )

    def with_archon_failure(
        self,
        archon_id: UUID,
        reason: ArchonFailureReason,
    ) -> "DeliberationSession":
        """Mark an Archon as failed.

        Args:
            archon_id: The Archon that failed.
            reason: Why they failed.

        Returns:
            Updated session with Archon marked FAILED.
        """
        new_statuses = dict(self.archon_statuses)
        new_statuses[archon_id] = ArchonStatus.FAILED
        return DeliberationSession(
            # ... copy all fields ...
            archon_statuses=new_statuses,
        )

    def with_archon_substitution(
        self,
        failed_archon_id: UUID,
        substitute_archon_id: UUID,
        failure_reason: str,
        substituted_at: datetime,
    ) -> "DeliberationSession":
        """Record an Archon substitution.

        Args:
            failed_archon_id: Original Archon that failed.
            substitute_archon_id: Replacement Archon.
            failure_reason: Why original failed.
            substituted_at: When substitution occurred.

        Returns:
            Updated session with substitution recorded.
        """
        substitution = ArchonSubstitution(
            failed_archon_id=failed_archon_id,
            substitute_archon_id=substitute_archon_id,
            phase_at_failure=self.current_phase.value,
            failure_reason=failure_reason,
            substituted_at=substituted_at,
        )

        new_statuses = dict(self.archon_statuses)
        new_statuses[failed_archon_id] = ArchonStatus.SUBSTITUTED
        new_statuses[substitute_archon_id] = ArchonStatus.ACTIVE

        return DeliberationSession(
            # ... copy all fields ...
            substitute_archons=(*self.substitute_archons, substitution),
            archon_statuses=new_statuses,
        )
```

### Substitution Service Protocol

```python
# src/application/ports/archon_substitution.py

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.events.archon_substitution import (
    ArchonSubstitutedEvent,
    DeliberationAbortedEvent,
)
from src.domain.models.archon_status import ArchonFailureReason
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.fate_archon import FateArchon


@dataclass(frozen=True)
class SubstitutionResult:
    """Result of an Archon substitution operation."""

    session: DeliberationSession
    substitute_archon: FateArchon
    event: ArchonSubstitutedEvent
    latency_ms: int


@dataclass(frozen=True)
class AbortResult:
    """Result of a deliberation abort due to multiple failures."""

    session: DeliberationSession
    event: DeliberationAbortedEvent


class ArchonSubstitutionServiceProtocol(Protocol):
    """Protocol for handling Archon failures and substitutions (NFR-10.6).

    Implementations detect Archon failures and coordinate substitution
    to ensure deliberation can continue with minimal disruption.
    """

    async def handle_archon_failure(
        self,
        session_id: UUID,
        failed_archon_id: UUID,
        failure_reason: ArchonFailureReason,
    ) -> SubstitutionResult | AbortResult:
        """Handle an Archon failure by substituting or aborting.

        If this is the first failure, substitutes the Archon.
        If this is the second+ failure, aborts the deliberation.

        Args:
            session_id: The deliberation session ID.
            failed_archon_id: ID of the Archon that failed.
            failure_reason: Why the Archon failed.

        Returns:
            SubstitutionResult if substitution succeeded,
            AbortResult if deliberation was aborted.

        Raises:
            SessionNotFoundError: If session doesn't exist.
            ArchonNotInSessionError: If failed_archon_id not in session.
        """
        ...

    async def get_substitute_context(
        self,
        session_id: UUID,
        substitute_archon_id: UUID,
    ) -> dict:
        """Build the context package for a substitute Archon.

        Includes full original context plus transcript so far.

        Args:
            session_id: The deliberation session ID.
            substitute_archon_id: ID of the substitute Archon.

        Returns:
            Context dictionary with original context + transcript.
        """
        ...
```

### Substitution Service Implementation

```python
# src/application/services/archon_substitution_service.py

import time
from datetime import datetime, timezone
from uuid import UUID

import structlog

from src.application.ports.archon_pool import ArchonPoolProtocol
from src.application.ports.archon_substitution import (
    AbortResult,
    ArchonSubstitutionServiceProtocol,
    SubstitutionResult,
)
from src.domain.events.archon_substitution import (
    ArchonSubstitutedEvent,
    DeliberationAbortedEvent,
)
from src.domain.models.archon_status import ArchonFailureReason, ArchonStatus
from src.domain.models.deliberation_session import DeliberationOutcome, DeliberationPhase

logger = structlog.get_logger(__name__)

# Constants
INDIVIDUAL_ARCHON_TIMEOUT_SECONDS = 30  # NFR-10.2
SUBSTITUTION_SLA_MS = 10_000  # NFR-10.6


class ArchonSubstitutionService(ArchonSubstitutionServiceProtocol):
    """Service for handling Archon failures and substitutions (NFR-10.6).

    Constitutional Constraints:
    - AT-1: Every petition terminates in exactly one of Three Fates
    - AT-6: Deliberation is collective judgment (need 3 Archons)
    - CT-11: Silent failure destroys legitimacy - handle failures gracefully
    """

    def __init__(
        self,
        archon_pool: ArchonPoolProtocol,
        session_repository: SessionRepositoryProtocol,
        petition_repository: PetitionRepositoryProtocol,
        context_builder: ContextPackageBuilderProtocol,
        event_emitter: EventEmitterProtocol,
    ) -> None:
        """Initialize the substitution service."""
        self._archon_pool = archon_pool
        self._session_repository = session_repository
        self._petition_repository = petition_repository
        self._context_builder = context_builder
        self._event_emitter = event_emitter
        self._log = logger.bind(component="archon_substitution_service")

    async def handle_archon_failure(
        self,
        session_id: UUID,
        failed_archon_id: UUID,
        failure_reason: ArchonFailureReason,
    ) -> SubstitutionResult | AbortResult:
        """Handle an Archon failure (AC-1, AC-7)."""
        start_time = time.monotonic()
        log = self._log.bind(
            session_id=str(session_id),
            failed_archon_id=str(failed_archon_id),
            failure_reason=failure_reason.value,
        )

        # Load session
        session = await self._session_repository.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)

        # Validate Archon is in session
        if failed_archon_id not in session.assigned_archons:
            if failed_archon_id not in [s.substitute_archon_id for s in session.substitute_archons]:
                raise ArchonNotInSessionError(session_id, failed_archon_id)

        # Check idempotency (AC-10)
        current_status = session.archon_statuses.get(failed_archon_id)
        if current_status in (ArchonStatus.FAILED, ArchonStatus.SUBSTITUTED):
            log.info("archon_already_handled", current_status=current_status.value)
            # Return existing result
            for sub in session.substitute_archons:
                if sub.failed_archon_id == failed_archon_id:
                    substitute = self._archon_pool.get_archon(sub.substitute_archon_id)
                    # Reconstruct event for idempotent return
                    event = ArchonSubstitutedEvent(
                        session_id=session_id,
                        petition_id=session.petition_id,
                        failed_archon_id=failed_archon_id,
                        substitute_archon_id=sub.substitute_archon_id,
                        phase_at_failure=sub.phase_at_failure,
                        failure_reason=sub.failure_reason,
                        substitution_latency_ms=0,  # Already done
                        transcript_pages_provided=0,
                    )
                    return SubstitutionResult(
                        session=session,
                        substitute_archon=substitute,
                        event=event,
                        latency_ms=0,
                    )

        # Mark Archon as failed
        session = session.with_archon_failure(failed_archon_id, failure_reason)
        log.info(
            "archon_marked_failed",
            phase=session.current_phase.value,
            failed_count=session.failed_archon_count,
        )

        # Check if this is the second+ failure (AC-7)
        if session.failed_archon_count >= 2:
            log.warning("multi_archon_failure_aborting")
            return await self._abort_deliberation(session, log)

        # Select substitute (AC-2)
        excluded_ids = set(session.assigned_archons)
        excluded_ids.update(s.substitute_archon_id for s in session.substitute_archons)
        excluded_ids.update(
            archon_id for archon_id, status in session.archon_statuses.items()
            if status == ArchonStatus.FAILED
        )

        try:
            substitute = self._archon_pool.select_substitute(
                session_id=session_id,
                sequence=len(session.substitute_archons),
                exclude_ids=excluded_ids,
            )
        except ArchonPoolExhaustedError:
            log.error("archon_pool_exhausted")
            return await self._abort_deliberation(
                session,
                log,
                reason="ARCHON_POOL_EXHAUSTED",
            )

        log.info("substitute_selected", substitute_id=str(substitute.id))

        # Record substitution (AC-9)
        now = datetime.now(timezone.utc)
        session = session.with_archon_substitution(
            failed_archon_id=failed_archon_id,
            substitute_archon_id=substitute.id,
            failure_reason=failure_reason.value,
            substituted_at=now,
        )

        # Persist updated session
        await self._session_repository.update(session)

        # Calculate latency
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Build context for substitute (AC-3)
        transcript_pages = await self._get_transcript_page_count(session)

        # Emit event (AC-6)
        event = ArchonSubstitutedEvent(
            session_id=session_id,
            petition_id=session.petition_id,
            failed_archon_id=failed_archon_id,
            substitute_archon_id=substitute.id,
            phase_at_failure=session.current_phase.value,
            failure_reason=failure_reason.value,
            substitution_latency_ms=latency_ms,
            transcript_pages_provided=transcript_pages,
        )
        await self._event_emitter.emit(event)

        log.info(
            "archon_substitution_complete",
            latency_ms=latency_ms,
            substitute_id=str(substitute.id),
        )

        return SubstitutionResult(
            session=session,
            substitute_archon=substitute,
            event=event,
            latency_ms=latency_ms,
        )

    async def get_substitute_context(
        self,
        session_id: UUID,
        substitute_archon_id: UUID,
    ) -> dict:
        """Build context for substitute Archon (AC-3)."""
        session = await self._session_repository.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)

        # Get original context
        original_context = await self._context_builder.build_context(
            session.petition_id
        )

        # Get transcript so far
        transcript = await self._get_transcript_so_far(session)

        return {
            **original_context,
            "is_substitute": True,
            "substituted_for_phase": session.current_phase.value,
            "transcript_so_far": transcript,
            "completed_phases": [
                phase.value for phase in session.completed_phases
            ],
        }

    async def _abort_deliberation(
        self,
        session: DeliberationSession,
        log: structlog.stdlib.BoundLogger,
        reason: str = "INSUFFICIENT_ARCHONS",
    ) -> AbortResult:
        """Abort deliberation due to multiple failures (AC-7, AC-8)."""
        # Update session to COMPLETE with ESCALATE
        session = session.with_abort_outcome(
            outcome=DeliberationOutcome.ESCALATE,
            reason=reason,
        )
        await self._session_repository.update(session)

        # Update petition state
        await self._petition_repository.transition_to_escalated(
            session.petition_id,
            reason=f"DELIBERATION_ABORTED_{reason}",
        )

        # Build failed archons list
        failed_archons = tuple(
            {
                "archon_id": str(archon_id),
                "failure_reason": session.archon_statuses.get(archon_id, ArchonStatus.FAILED).value,
                "phase": session.current_phase.value,
            }
            for archon_id, status in session.archon_statuses.items()
            if status == ArchonStatus.FAILED
        )

        # Find surviving archon
        surviving = None
        for archon_id, status in session.archon_statuses.items():
            if status == ArchonStatus.ACTIVE:
                surviving = archon_id
                break

        # Emit abort event
        event = DeliberationAbortedEvent(
            session_id=session.session_id,
            petition_id=session.petition_id,
            reason=reason,
            failed_archons=failed_archons,
            surviving_archon_id=surviving,
        )
        await self._event_emitter.emit(event)

        log.warning(
            "deliberation_aborted",
            reason=reason,
            failed_count=len(failed_archons),
        )

        return AbortResult(session=session, event=event)

    async def _get_transcript_so_far(
        self,
        session: DeliberationSession,
    ) -> list[dict]:
        """Get transcript of all completed phases."""
        transcripts = []
        for phase in session.completed_phases:
            phase_result = session.phase_results.get(phase)
            if phase_result:
                transcripts.append({
                    "phase": phase.value,
                    "transcript": phase_result.transcript,
                    "transcript_hash": phase_result.transcript_hash,
                })
        return transcripts

    async def _get_transcript_page_count(
        self,
        session: DeliberationSession,
    ) -> int:
        """Count transcript pages provided to substitute."""
        return len(session.completed_phases)
```

### Stub Implementation

```python
# src/infrastructure/stubs/archon_substitution_stub.py

from datetime import datetime, timezone
from uuid import UUID, uuid7

from src.application.ports.archon_substitution import (
    AbortResult,
    ArchonSubstitutionServiceProtocol,
    SubstitutionResult,
)
from src.domain.events.archon_substitution import (
    ArchonSubstitutedEvent,
    DeliberationAbortedEvent,
)
from src.domain.models.archon_status import ArchonFailureReason, ArchonStatus
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationSession,
)
from src.domain.models.fate_archon import FateArchon


class ArchonSubstitutionServiceStub(ArchonSubstitutionServiceProtocol):
    """In-memory stub for testing Archon substitution (Story 2B.4)."""

    def __init__(
        self,
        archon_pool: list[FateArchon],
    ) -> None:
        """Initialize stub with available Archons."""
        self._archon_pool = {a.id: a for a in archon_pool}
        self._sessions: dict[UUID, DeliberationSession] = {}
        self._emitted_events: list = []
        self._failure_count: dict[UUID, int] = {}  # session_id -> failure count

    def set_session(self, session: DeliberationSession) -> None:
        """Set a session for testing."""
        self._sessions[session.session_id] = session

    async def handle_archon_failure(
        self,
        session_id: UUID,
        failed_archon_id: UUID,
        failure_reason: ArchonFailureReason,
    ) -> SubstitutionResult | AbortResult:
        """Handle Archon failure in test stub."""
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        # Track failures
        self._failure_count[session_id] = self._failure_count.get(session_id, 0) + 1

        # If 2+ failures, abort
        if self._failure_count[session_id] >= 2:
            event = DeliberationAbortedEvent(
                session_id=session_id,
                petition_id=session.petition_id,
                reason="INSUFFICIENT_ARCHONS",
                failed_archons=(),
                surviving_archon_id=None,
            )
            self._emitted_events.append(event)
            return AbortResult(session=session, event=event)

        # Select substitute (first available not in session)
        excluded = set(session.assigned_archons)
        substitute = None
        for archon in self._archon_pool.values():
            if archon.id not in excluded:
                substitute = archon
                break

        if substitute is None:
            event = DeliberationAbortedEvent(
                session_id=session_id,
                petition_id=session.petition_id,
                reason="ARCHON_POOL_EXHAUSTED",
                failed_archons=(),
                surviving_archon_id=None,
            )
            self._emitted_events.append(event)
            return AbortResult(session=session, event=event)

        # Create substitution event
        event = ArchonSubstitutedEvent(
            session_id=session_id,
            petition_id=session.petition_id,
            failed_archon_id=failed_archon_id,
            substitute_archon_id=substitute.id,
            phase_at_failure=session.current_phase.value,
            failure_reason=failure_reason.value,
            substitution_latency_ms=50,  # Simulated fast
            transcript_pages_provided=1,
        )
        self._emitted_events.append(event)

        return SubstitutionResult(
            session=session,
            substitute_archon=substitute,
            event=event,
            latency_ms=50,
        )

    async def get_substitute_context(
        self,
        session_id: UUID,
        substitute_archon_id: UUID,
    ) -> dict:
        """Build context for substitute in test stub."""
        session = self._sessions.get(session_id)
        return {
            "petition_id": str(session.petition_id) if session else None,
            "is_substitute": True,
            "transcript_so_far": [],
        }

    @property
    def emitted_events(self) -> list:
        """Get emitted events for assertions."""
        return self._emitted_events
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status | Why Needed |
|----------|------|--------|------------|
| petition-2a-1 | Deliberation Session Domain Model | DONE | Session model to extend |
| petition-2a-2 | Archon Assignment Service | DONE | ArchonPoolProtocol for selection |
| petition-2a-3 | Context Package Builder | DONE | Context for substitute |
| petition-2a-4 | Deliberation Protocol Orchestrator | DONE | Integration point |
| petition-2a-5 | CrewAI Deliberation Adapter | DONE | Detects Archon timeouts |
| petition-2a-6 | Supermajority Consensus Resolution | DONE | Vote handling |

### Downstream Dependencies (Blocked By This Story)

| Story ID | Name | Why Blocked |
|----------|------|-------------|
| petition-2b-6 | Audit Trail Reconstruction | Needs substitution events |
| petition-2b-8 | Deliberation Chaos Testing | Tests substitution scenarios |

## Implementation Tasks

### Task 1: Create Archon Status Enums
- [x] Create `src/domain/models/archon_status.py`
- [x] Define `ArchonStatus` enum (ACTIVE, FAILED, SUBSTITUTED)
- [x] Define `ArchonFailureReason` enum
- [x] Export from `src/domain/models/__init__.py`

### Task 2: Create Domain Events
- [x] Create `src/domain/events/archon_substitution.py`
- [x] Define `ArchonSubstitutedEvent` frozen dataclass
- [x] Define `DeliberationAbortedEvent` frozen dataclass
- [x] Implement `to_dict()` for both events
- [x] Export from `src/domain/events/__init__.py`

### Task 3: Extend DeliberationSession Model
- [x] Add `ArchonSubstitution` dataclass
- [x] Add `substitute_archons` field
- [x] Add `archon_statuses` field
- [x] Add `current_active_archons` property
- [x] Add `failed_archon_count` property
- [x] Add `with_archon_failure()` method
- [x] Add `with_archon_substitution()` method

### Task 4: Create Substitution Service Protocol
- [x] Create `src/application/ports/archon_substitution.py`
- [x] Define `SubstitutionResult` dataclass
- [x] Define `AbortResult` dataclass
- [x] Define `ArchonSubstitutionServiceProtocol`
- [x] Export from `src/application/ports/__init__.py`

### Task 5: Implement Substitution Service
- [x] Create `src/application/services/archon_substitution_service.py`
- [x] Implement `handle_archon_failure()` method
- [x] Implement `get_substitute_context()` method
- [x] Implement `_abort_deliberation()` helper
- [x] Add structured logging
- [x] Export from `src/application/services/__init__.py`

### Task 6: Extend ArchonPool for Substitute Selection
- [x] Add `select_substitute()` method to ArchonPoolProtocol
- [x] Implement deterministic substitute selection
- [x] Handle pool exhaustion
- [x] Update stub implementation

### Task 7: Create Stub Implementation
- [x] Create `src/infrastructure/stubs/archon_substitution_stub.py`
- [x] Implement in-memory substitution tracking
- [x] Record emitted events for test assertions
- [x] Export from `src/infrastructure/stubs/__init__.py`

### Task 8: Integrate with Orchestrator
- [x] Add timeout detection in orchestrator
- [x] Trigger `handle_archon_failure()` on timeout
- [x] Handle substitution result in orchestrator

### Task 9: Create Error Types
- [x] Add `SessionNotFoundError`
- [x] Add `ArchonNotInSessionError`
- [x] Add `ArchonPoolExhaustedError` (may exist from 2A.2)
- [x] Export from `src/domain/errors/__init__.py`

### Task 10: Write Unit Tests
- [x] Create `tests/unit/domain/models/test_archon_status.py`
- [x] Create `tests/unit/domain/events/test_archon_substitution_events.py`
- [x] Create `tests/unit/application/services/test_archon_substitution_service.py`
- [x] Test failure detection and marking
- [x] Test substitute selection excludes correct IDs
- [x] Test multi-failure triggers abort
- [x] Test pool exhaustion triggers abort
- [x] Test idempotent handling
- [x] Test event emission

### Task 11: Write Integration Tests
- [x] Create `tests/integration/test_archon_substitution_integration.py`
- [x] Test end-to-end substitution flow
- [x] Test database state persistence
- [x] Test event witnessing
- [x] Test deliberation continues after substitution

## Definition of Done

- [x] `ArchonStatus` and `ArchonFailureReason` enums defined
- [x] `ArchonSubstitutedEvent` and `DeliberationAbortedEvent` events defined
- [x] `DeliberationSession` extended with substitution tracking
- [x] `ArchonSubstitutionServiceProtocol` defined
- [x] `ArchonSubstitutionService` implements all methods
- [x] ArchonPool extended with substitute selection
- [x] Stub implementation for testing
- [x] Orchestrator integration complete
- [x] Unit tests pass (>90% coverage)
- [x] Integration tests verify end-to-end flow
- [x] NFR-10.6 satisfied: Substitution latency < 10 seconds
- [x] AC-7 satisfied: 2+ failures triggers ESCALATE

## Test Scenarios

### Scenario 1: Single Archon Timeout - Successful Substitution
```python
# Setup: Session in POSITION phase, Archon times out
session = create_session_in_phase(DeliberationPhase.POSITION)
archon_to_fail = session.assigned_archons[1]

# Execute
result = await substitution_service.handle_archon_failure(
    session_id=session.session_id,
    failed_archon_id=archon_to_fail,
    failure_reason=ArchonFailureReason.RESPONSE_TIMEOUT,
)

# Verify substitution occurred
assert isinstance(result, SubstitutionResult)
assert result.substitute_archon.id != archon_to_fail
assert result.event.failure_reason == "RESPONSE_TIMEOUT"
assert result.latency_ms < 10_000  # NFR-10.6
```

### Scenario 2: Multi-Archon Failure - Deliberation Aborted
```python
# Setup: Session with one Archon already failed
session = create_session_with_one_failed_archon()
second_to_fail = session.assigned_archons[2]

# Execute second failure
result = await substitution_service.handle_archon_failure(
    session_id=session.session_id,
    failed_archon_id=second_to_fail,
    failure_reason=ArchonFailureReason.API_ERROR,
)

# Verify abort
assert isinstance(result, AbortResult)
assert result.event.reason == "INSUFFICIENT_ARCHONS"

# Verify petition ESCALATED
petition = await petition_repo.get(session.petition_id)
assert petition.state == PetitionState.ESCALATED
```

### Scenario 3: Substitution During VOTE Phase
```python
# Setup: Session in VOTE phase, one vote already cast
session = create_session_in_vote_phase(votes_cast=1)
voting_archon = session.assigned_archons[1]

# Archon fails during vote
result = await substitution_service.handle_archon_failure(
    session_id=session.session_id,
    failed_archon_id=voting_archon,
    failure_reason=ArchonFailureReason.RESPONSE_TIMEOUT,
)

# Verify substitute
assert isinstance(result, SubstitutionResult)
# Vote phase continues with substitute
assert session.current_phase == DeliberationPhase.VOTE
```

### Scenario 4: Pool Exhaustion
```python
# Setup: All 7 Archons either assigned or previously failed
session = create_session_with_exhausted_pool()

# Try to substitute
result = await substitution_service.handle_archon_failure(
    session_id=session.session_id,
    failed_archon_id=session.assigned_archons[0],
    failure_reason=ArchonFailureReason.RESPONSE_TIMEOUT,
)

# Verify abort
assert isinstance(result, AbortResult)
assert result.event.reason == "ARCHON_POOL_EXHAUSTED"
```

### Scenario 5: Idempotent Substitution
```python
# Setup: Already substituted Archon
session = create_session_with_substitution()
already_failed = session.substitute_archons[0].failed_archon_id

# Attempt duplicate substitution
result1 = await substitution_service.handle_archon_failure(...)
result2 = await substitution_service.handle_archon_failure(
    session_id=session.session_id,
    failed_archon_id=already_failed,
    failure_reason=ArchonFailureReason.RESPONSE_TIMEOUT,
)

# Verify idempotent
assert isinstance(result2, SubstitutionResult)
assert result2.latency_ms == 0  # Already done
```

## Dev Notes

### Relevant Architecture Patterns

1. **Failure handling pattern**:
   - Detect failure (timeout, error, invalid response)
   - Mark Archon status in session
   - Decide: substitute or abort
   - Emit appropriate event

2. **Substitute selection pattern**:
   - Exclude all assigned Archons
   - Exclude all previously failed Archons
   - Deterministic based on (session_id, sequence)
   - Handle pool exhaustion gracefully

3. **Event pattern**:
   - Follow `ArchonSubstitutedEvent` / `DeliberationAbortedEvent`
   - Events witnessed in hash chain
   - Frozen dataclass with `to_dict()`

4. **Latency tracking pattern**:
   - Measure from failure detection to substitute ready
   - Record in event for observability
   - SLA: < 10 seconds (NFR-10.6)

### Key Files to Reference

| File | Why |
|------|-----|
| `src/domain/models/deliberation_session.py` | Session model to extend |
| `src/application/ports/archon_pool.py` | ArchonPoolProtocol |
| `src/application/services/archon_pool.py` | Pool implementation |
| `src/infrastructure/adapters/external/crewai_deliberation_adapter.py` | Integration point |
| `src/domain/events/phase_witness.py` | Event pattern reference |

### Integration Points

1. **CrewAI adapter integration**:
   ```python
   # In CrewAI adapter, on Archon timeout
   if archon_response_timeout:
       await substitution_service.handle_archon_failure(
           session_id=session_id,
           failed_archon_id=archon_id,
           failure_reason=ArchonFailureReason.RESPONSE_TIMEOUT,
       )
   ```

2. **Orchestrator integration**:
   ```python
   # In orchestrator, handle substitution result
   result = await substitution_service.handle_archon_failure(...)
   if isinstance(result, SubstitutionResult):
       # Continue deliberation with substitute
       await continue_with_substitute(result.substitute_archon, result.session)
   else:
       # Deliberation aborted, petition ESCALATED
       return AbortedDeliberationResult(...)
   ```

### Project Structure Notes

- **Location**: Follow existing patterns:
  - Enums: `src/domain/models/archon_status.py`
  - Events: `src/domain/events/archon_substitution.py`
  - Protocol: `src/application/ports/archon_substitution.py`
  - Service: `src/application/services/archon_substitution_service.py`
  - Stub: `src/infrastructure/stubs/archon_substitution_stub.py`
- **Naming**: `archon_substitution_*` prefix
- **Imports**: Absolute imports from `src.`

### References

- [Source: `_bmad-output/planning-artifacts/petition-system-prd.md#NFR-10.6`] - Latency requirement
- [Source: `_bmad-output/planning-artifacts/petition-system-prd.md#Section-13A.5`] - Archon unavailable handling
- [Source: `_bmad-output/planning-artifacts/petition-system-epics.md#Story-2B.4`] - Original story
- [Source: `src/application/services/archon_pool.py`] - Pool implementation reference
- [Source: `_bmad-output/implementation-artifacts/stories/petition-2a-2-archon-assignment-service.md`] - Related story

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for complex logic
- [x] N/A - Internal service, builds on existing deliberation infrastructure

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-01-19 | Claude | Initial story creation |
