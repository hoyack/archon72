"""Knight Observer Service - Passive observation of governance events.

Story: consent-gov-6.2: Passive Knight Observation

This service implements passive observation via ledger polling. The Knight
observes all governance events without active intervention - services publish
to the ledger, and Knight reads from it. This loose coupling ensures that
services cannot suppress observations by choosing not to call the Knight.

Architectural Decision: Ledger-Based Observation (not event bus)
----------------------------------------------------------------
The architecture uses an append-only ledger (not pub/sub event bus) for
governance events. This means Knight observes via ledger polling rather
than event subscriptions:

  Active (REJECTED):
    - Services call Knight explicitly
    - Tight coupling
    - Service can choose not to call → suppression

  Passive (ACCEPTED - via ledger polling):
    - Services write to ledger
    - Knight reads from ledger
    - Loose coupling
    - Cannot suppress what you don't control

Dual-Path Resilience:
---------------------
Since the architecture already provides ledger-based persistence, the "dual
path" concept becomes ledger-primary with position tracking:

  Primary: Ledger polling (fast, configurable interval)
  Fallback: Position tracking ensures no events missed on restart

Constitutional Guarantees:
- NFR-OBS-01: Knight observes all branch actions within ≤1 second
- NFR-AUDIT-01: All branch actions logged with sufficient detail
- FR33: Knight can observe and record across all branches
- FR41: Knight can observe Prince Panel conduct

References:
    - AD-16: Knight Observation Pattern (passive subscription)
    - NFR-OBS-01: Observation latency ≤1 second
    - NFR-AUDIT-01: Sufficient detail logging
    - FR33: Cross-branch observation
    - FR41: Panel observation
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable, Awaitable
from uuid import UUID

from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.witness_statement import WitnessStatement

if TYPE_CHECKING:
    from src.application.ports.governance.ledger_port import (
        GovernanceLedgerPort,
        LedgerReadOptions,
        PersistedGovernanceEvent,
    )
    from src.application.ports.governance.witness_port import WitnessPort
    from src.application.ports.time_authority import TimeAuthorityProtocol
    from src.domain.governance.witness.witness_statement_factory import (
        WitnessStatementFactory,
    )

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ObservationMetrics:
    """Metrics from an observation cycle.

    Attributes:
        events_observed: Number of events observed this cycle.
        gaps_detected: Number of sequence gaps detected.
        max_latency_ms: Maximum observation latency in milliseconds.
        avg_latency_ms: Average observation latency in milliseconds.
        cycle_duration_ms: Total time for this observation cycle.
    """

    events_observed: int
    gaps_detected: int
    max_latency_ms: float
    avg_latency_ms: float
    cycle_duration_ms: float


@dataclass(frozen=True)
class GapDetection:
    """Record of a detected sequence gap.

    Attributes:
        expected_sequence: The sequence number that was expected.
        actual_sequence: The sequence number that was observed.
        missing_count: Number of events missing in the gap.
        detected_at: When the gap was detected.
    """

    expected_sequence: int
    actual_sequence: int
    missing_count: int
    detected_at: datetime


class KnightObserverService:
    """Passive observation service for Knight witness.

    Polls the governance ledger to observe all governance events. Creates
    witness statements for each observed event without judgment. Detects
    gaps in the sequence chain that could indicate suppression or tampering.

    Key Design Principles:
    1. PASSIVE: Knight reads from ledger, doesn't receive callbacks
    2. LOOSE COUPLING: Services don't know Knight is watching
    3. COMPLETE: All events in ledger are eventually observed
    4. GAP DETECTION: Missing sequence numbers are detected and recorded

    Example:
        >>> observer = KnightObserverService(
        ...     ledger=governance_ledger,
        ...     witness_port=witness_port,
        ...     statement_factory=statement_factory,
        ...     time_authority=time_authority,
        ... )
        >>> await observer.start()  # Begin observation loop
        >>> # ... later ...
        >>> await observer.stop()   # Stop observation loop
    """

    # Event type prefixes for different branches
    BRANCH_PREFIXES = frozenset({
        "executive",
        "judicial",
        "constitutional",
        "witness",
        "filter",
        "consent",
        "legitimacy",
        "exit",
        "safety",
        "system",
        "ledger",
        "administrative",
    })

    # Panel event types for FR41 (Knight observes Prince Panel conduct)
    PANEL_EVENT_TYPES = frozenset({
        "judicial.panel.convened",
        "judicial.panel.deliberation_started",
        "judicial.panel.member_recused",
        "judicial.panel.finding_proposed",
        "judicial.panel.vote_recorded",
        "judicial.panel.finding_issued",
        "judicial.panel.dissent_recorded",
    })

    # Default poll interval (configurable)
    DEFAULT_POLL_INTERVAL_SECONDS = 0.5  # 500ms for sub-second observation

    # Latency warning threshold (NFR-OBS-01)
    LATENCY_THRESHOLD_MS = 1000.0  # 1 second

    def __init__(
        self,
        ledger: GovernanceLedgerPort,
        witness_port: WitnessPort,
        statement_factory: WitnessStatementFactory,
        time_authority: TimeAuthorityProtocol,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        batch_size: int = 100,
    ) -> None:
        """Initialize the Knight Observer Service.

        Args:
            ledger: The governance ledger to observe.
            witness_port: Port for recording witness statements.
            statement_factory: Factory for creating valid statements.
            time_authority: Time authority for timestamps.
            poll_interval_seconds: Interval between ledger polls.
            batch_size: Maximum events to fetch per poll cycle.
        """
        self._ledger = ledger
        self._witness_port = witness_port
        self._statement_factory = statement_factory
        self._time_authority = time_authority
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size

        # State tracking
        self._last_observed_sequence: int = 0
        self._running: bool = False
        self._poll_task: asyncio.Task | None = None
        self._observed_event_ids: set[UUID] = set()

        # Metrics
        self._total_events_observed: int = 0
        self._total_gaps_detected: int = 0
        self._latency_violations: int = 0

        # Callbacks for gap detection (optional)
        self._gap_callback: Callable[[GapDetection], Awaitable[None]] | None = None

    async def start(self, starting_sequence: int = 0) -> None:
        """Start the observation loop.

        Args:
            starting_sequence: Sequence number to start observing from.
                              0 means start from beginning.
        """
        if self._running:
            logger.warning("Observer already running")
            return

        self._last_observed_sequence = starting_sequence
        self._running = True

        logger.info(
            f"Knight Observer starting from sequence {starting_sequence}, "
            f"poll interval {self._poll_interval}s"
        )

        self._poll_task = asyncio.create_task(self._observation_loop())

    async def stop(self) -> None:
        """Stop the observation loop."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        logger.info(
            f"Knight Observer stopped. "
            f"Total observed: {self._total_events_observed}, "
            f"Gaps detected: {self._total_gaps_detected}"
        )

    async def observe_once(self) -> ObservationMetrics:
        """Run a single observation cycle (for testing/manual use).

        Returns:
            Metrics from this observation cycle.
        """
        return await self._poll_and_observe()

    async def _observation_loop(self) -> None:
        """Main observation loop - polls ledger continuously."""
        while self._running:
            try:
                await self._poll_and_observe()
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Observer error: {e}", exc_info=True)
                await asyncio.sleep(self._poll_interval)

    async def _poll_and_observe(self) -> ObservationMetrics:
        """Poll ledger and observe new events.

        Returns:
            Metrics from this observation cycle.
        """
        cycle_start = self._time_authority.monotonic()

        # Import here to avoid circular import
        from src.application.ports.governance.ledger_port import LedgerReadOptions

        # Fetch events since last observed sequence
        options = LedgerReadOptions(
            start_sequence=self._last_observed_sequence + 1,
            limit=self._batch_size,
        )

        events = await self._ledger.read_events(options)

        if not events:
            cycle_duration = (self._time_authority.monotonic() - cycle_start) * 1000
            return ObservationMetrics(
                events_observed=0,
                gaps_detected=0,
                max_latency_ms=0.0,
                avg_latency_ms=0.0,
                cycle_duration_ms=cycle_duration,
            )

        # Process events
        events_observed = 0
        gaps_detected = 0
        latencies: list[float] = []

        for event in events:
            # Skip already observed (idempotency)
            if event.event_id in self._observed_event_ids:
                continue

            # Check for gap
            gap = self._check_for_gap(event.sequence)
            if gap:
                gaps_detected += 1
                await self._handle_gap_detected(gap)

            # Observe and record
            latency_ms = await self._observe_event(event)
            latencies.append(latency_ms)
            events_observed += 1

            # Update tracking
            self._last_observed_sequence = event.sequence
            self._observed_event_ids.add(event.event_id)

            # Limit observed_event_ids set size (rolling window)
            if len(self._observed_event_ids) > 10000:
                # Remove oldest (this is approximate but sufficient)
                self._observed_event_ids = set(
                    list(self._observed_event_ids)[-5000:]
                )

        # Calculate metrics
        cycle_duration = (self._time_authority.monotonic() - cycle_start) * 1000
        max_latency = max(latencies) if latencies else 0.0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        # Update totals
        self._total_events_observed += events_observed
        self._total_gaps_detected += gaps_detected

        return ObservationMetrics(
            events_observed=events_observed,
            gaps_detected=gaps_detected,
            max_latency_ms=max_latency,
            avg_latency_ms=avg_latency,
            cycle_duration_ms=cycle_duration,
        )

    def _check_for_gap(self, current_sequence: int) -> GapDetection | None:
        """Check if there's a gap in the sequence.

        Args:
            current_sequence: The sequence number of the current event.

        Returns:
            GapDetection if gap found, None otherwise.
        """
        expected = self._last_observed_sequence + 1

        if current_sequence > expected:
            missing_count = current_sequence - expected

            logger.warning(
                f"Gap detected: expected sequence {expected}, "
                f"got {current_sequence}, missing {missing_count} events"
            )

            return GapDetection(
                expected_sequence=expected,
                actual_sequence=current_sequence,
                missing_count=missing_count,
                detected_at=self._time_authority.now(),
            )

        return None

    async def _handle_gap_detected(self, gap: GapDetection) -> None:
        """Handle a detected sequence gap.

        Creates a witness statement recording the gap, and optionally
        invokes the gap callback.

        Args:
            gap: The detected gap information.
        """
        # Create a pseudo-event for the gap observation
        @dataclass
        class GapPseudoEvent:
            event_id: UUID
            event_type: str
            timestamp: datetime
            actor: str

        from uuid import uuid4
        pseudo_event = GapPseudoEvent(
            event_id=uuid4(),
            event_type="witness.gap.detected",
            timestamp=gap.detected_at,
            actor="knight.observer",
        )

        # Create witness statement for the gap
        statement = self._statement_factory.create_statement(
            observation_type=ObservationType.HASH_CHAIN_GAP,
            observed_event=pseudo_event,
            what=(
                f"Sequence gap detected: expected {gap.expected_sequence}, "
                f"received {gap.actual_sequence}, "
                f"missing {gap.missing_count} event(s)"
            ),
            where="witness.observation",
        )

        await self._witness_port.record_statement(statement)

        # Invoke callback if registered
        if self._gap_callback:
            await self._gap_callback(gap)

    async def _observe_event(
        self, event: PersistedGovernanceEvent
    ) -> float:
        """Observe a single event and create witness statement.

        Args:
            event: The persisted governance event to observe.

        Returns:
            Observation latency in milliseconds.
        """
        now = self._time_authority.now()
        event_timestamp = event.timestamp

        # Calculate latency
        latency_delta = now - event_timestamp
        latency_ms = latency_delta.total_seconds() * 1000

        # Log latency warning (NFR-OBS-01)
        if latency_ms > self.LATENCY_THRESHOLD_MS:
            logger.warning(
                f"Observation latency {latency_ms:.1f}ms exceeds "
                f"{self.LATENCY_THRESHOLD_MS}ms threshold for event "
                f"{event.event_id} (type: {event.event_type})"
            )
            self._latency_violations += 1

        # Determine observation type
        observation_type = self._classify_event(event)

        # Create factual description
        what = self._describe_event(event)

        # Determine branch
        where = self._determine_branch(event)

        # Create an event-like object for the factory
        @dataclass
        class EventForFactory:
            event_id: UUID
            event_type: str
            timestamp: datetime
            actor: str

        event_for_factory = EventForFactory(
            event_id=event.event_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            actor=event.actor_id,
        )

        # Create witness statement
        statement = self._statement_factory.create_statement(
            observation_type=observation_type,
            observed_event=event_for_factory,
            what=what,
            where=where,
        )

        # Record to witness ledger
        await self._witness_port.record_statement(statement)

        return latency_ms

    def _classify_event(
        self, event: PersistedGovernanceEvent
    ) -> ObservationType:
        """Classify event for observation type.

        Args:
            event: The event to classify.

        Returns:
            The appropriate ObservationType.
        """
        event_type_lower = event.event_type.lower()

        # Check for potential violation indicators
        if "violation" in event_type_lower:
            return ObservationType.POTENTIAL_VIOLATION

        # Check for timing-related events
        if "timeout" in event_type_lower or "expired" in event_type_lower:
            return ObservationType.TIMING_ANOMALY

        # Check for integrity-related events
        if "gap" in event_type_lower or "orphan" in event_type_lower:
            return ObservationType.HASH_CHAIN_GAP

        # Default: normal branch action
        return ObservationType.BRANCH_ACTION

    def _describe_event(self, event: PersistedGovernanceEvent) -> str:
        """Create factual description of event.

        Args:
            event: The event to describe.

        Returns:
            Factual description string (no judgment).
        """
        # Panel events get special descriptions (FR41)
        if event.event_type in self.PANEL_EVENT_TYPES:
            return self._describe_panel_event(event)

        # Standard event description
        return (
            f"Event {event.event_type} at sequence {event.sequence} "
            f"by actor {event.actor_id}"
        )

    def _describe_panel_event(self, event: PersistedGovernanceEvent) -> str:
        """Create factual description of panel event (FR41).

        Args:
            event: The panel event to describe.

        Returns:
            Factual description of panel activity.
        """
        descriptions = {
            "judicial.panel.convened": "Panel convened",
            "judicial.panel.deliberation_started": "Deliberation began",
            "judicial.panel.member_recused": "Member recused from panel",
            "judicial.panel.finding_proposed": "Finding proposed for vote",
            "judicial.panel.vote_recorded": "Vote recorded by member",
            "judicial.panel.finding_issued": "Formal finding issued",
            "judicial.panel.dissent_recorded": "Dissent recorded in finding",
        }

        base_desc = descriptions.get(
            event.event_type,
            f"Panel event: {event.event_type}"
        )

        return f"{base_desc} at sequence {event.sequence}"

    def _determine_branch(self, event: PersistedGovernanceEvent) -> str:
        """Determine which branch the event belongs to.

        Args:
            event: The event to classify.

        Returns:
            Branch identifier (e.g., "executive", "judicial").
        """
        # Extract branch from event type (first segment)
        parts = event.event_type.split(".")
        if parts and parts[0] in self.BRANCH_PREFIXES:
            return parts[0]

        # Fallback
        return "governance"

    def register_gap_callback(
        self,
        callback: Callable[[GapDetection], Awaitable[None]],
    ) -> None:
        """Register a callback for gap detection events.

        Args:
            callback: Async function to call when a gap is detected.
        """
        self._gap_callback = callback

    @property
    def last_observed_sequence(self) -> int:
        """Get the last observed sequence number."""
        return self._last_observed_sequence

    @property
    def is_running(self) -> bool:
        """Check if the observer is currently running."""
        return self._running

    @property
    def total_events_observed(self) -> int:
        """Get total number of events observed."""
        return self._total_events_observed

    @property
    def total_gaps_detected(self) -> int:
        """Get total number of gaps detected."""
        return self._total_gaps_detected

    @property
    def latency_violations(self) -> int:
        """Get count of latency threshold violations."""
        return self._latency_violations

    async def get_observation_status(self) -> dict:
        """Get current observation status for monitoring.

        Returns:
            Dict with current status information.
        """
        return {
            "running": self._running,
            "last_observed_sequence": self._last_observed_sequence,
            "total_events_observed": self._total_events_observed,
            "total_gaps_detected": self._total_gaps_detected,
            "latency_violations": self._latency_violations,
            "poll_interval_seconds": self._poll_interval,
            "batch_size": self._batch_size,
        }
