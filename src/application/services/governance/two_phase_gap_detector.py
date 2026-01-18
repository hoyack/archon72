"""TwoPhaseGapDetector service implementation.

Story: consent-gov-1.6: Two-Phase Event Emission

This service verifies two-phase completeness by detecting intents without
corresponding outcome events (commit or failure) in the governance ledger.

It integrates with the hash chain verification (story 1-3) to provide
complete integrity monitoring of the two-phase event emission pattern.

Constitutional Guarantees:
- Hash chain gap detection triggers constitutional violation event
- Knight can observe intent_emitted immediately upon action initiation
- All orphaned intents are detected and reported

References:
- AD-3: Two-phase event emission
- AC7: Hash chain gap detection triggers constitutional violation event
- AC8: Knight can observe intent_emitted immediately
- NFR-CONST-07: Witness statements cannot be suppressed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.event_types import GovernanceEventType
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION

if TYPE_CHECKING:
    from src.application.ports.governance.ledger_port import GovernanceLedgerPort
    from src.application.ports.time_authority import TimeAuthorityProtocol


class TwoPhaseViolationType(str, Enum):
    """Types of two-phase emission violations."""

    ORPHANED_INTENT = "orphaned_intent"
    OUTCOME_WITHOUT_INTENT = "outcome_without_intent"


@dataclass(frozen=True)
class TwoPhaseViolation:
    """Record of a two-phase emission violation.

    Attributes:
        event_id: The event ID of the problematic event.
        correlation_id: The correlation ID linking intent to outcome.
        violation_type: Type of violation detected.
        event_type: The event type of the problematic event.
        age: How long since the intent was emitted (for orphans).
    """

    event_id: UUID
    correlation_id: str
    violation_type: TwoPhaseViolationType
    event_type: str
    age: timedelta


class TwoPhaseGapDetector:
    """Detects gaps in two-phase event emission.

    This service scans the governance ledger for intents that have
    not received corresponding outcome events (commit or failure)
    within the configured timeout period.

    It integrates with hash chain verification to provide complete
    integrity monitoring of the governance event stream.

    Constitutional Guarantees:
    - All orphaned intents are detected and reported
    - Violation events are emitted to the ledger for audit
    - Knight can query intent-outcome pairs

    Example:
        detector = TwoPhaseGapDetector(
            ledger=ledger,
            time_authority=time_authority,
            orphan_timeout=timedelta(minutes=5),
        )

        # Periodic scan (e.g., every hour)
        violations = await detector.scan_and_emit_violations()
        for v in violations:
            logger.error(f"Two-phase violation: {v.correlation_id}")
    """

    def __init__(
        self,
        ledger: GovernanceLedgerPort,
        time_authority: TimeAuthorityProtocol,
        orphan_timeout: timedelta = timedelta(minutes=5),
    ) -> None:
        """Initialize the TwoPhaseGapDetector.

        Args:
            ledger: The governance ledger for reading/writing events.
            time_authority: Time authority for current time.
            orphan_timeout: Threshold after which unresolved intents
                           are considered orphaned. Default 5 minutes.
        """
        self._ledger = ledger
        self._time_authority = time_authority
        self._orphan_timeout = orphan_timeout

    async def verify_two_phase_completeness(self) -> list[TwoPhaseViolation]:
        """Verify all intents have corresponding outcomes.

        Scans the ledger for intent events and checks that each has
        a corresponding commit or failure event. Intents without
        outcomes that exceed the timeout threshold are reported.

        Returns:
            List of TwoPhaseViolation records for detected violations.
        """
        now = self._time_authority.now()

        # Get all intent events
        intents = await self._ledger.read_events(event_type_pattern="*.intent.emitted")

        if not intents:
            return []

        # Get all outcome events
        outcomes = await self._ledger.read_events(
            event_type_pattern="*.commit.confirmed|*.failure.recorded"
        )

        # Index outcomes by correlation_id
        outcome_by_correlation: dict[str, GovernanceEvent] = {}
        for outcome in outcomes:
            corr_id = outcome.payload.get("correlation_id")
            if corr_id:
                outcome_by_correlation[corr_id] = outcome

        violations: list[TwoPhaseViolation] = []

        for intent in intents:
            correlation_id = intent.payload.get("correlation_id")
            if not correlation_id:
                continue

            # Check if outcome exists
            if correlation_id in outcome_by_correlation:
                continue

            # Check if past timeout threshold
            age = now - intent.timestamp
            if age >= self._orphan_timeout:
                violations.append(
                    TwoPhaseViolation(
                        event_id=intent.event_id,
                        correlation_id=correlation_id,
                        violation_type=TwoPhaseViolationType.ORPHANED_INTENT,
                        event_type=intent.event_type,
                        age=age,
                    )
                )

        return violations

    async def emit_orphan_violation_event(self, violation: TwoPhaseViolation) -> None:
        """Emit a constitutional violation event for an orphaned intent.

        Creates a ledger.integrity.orphaned_intent_detected event
        to record the violation in the audit trail.

        Args:
            violation: The violation to emit.
        """
        now = self._time_authority.now()

        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type=GovernanceEventType.LEDGER_INTEGRITY_ORPHANED_INTENT_DETECTED.value,
            timestamp=now,
            actor_id="system.gap_detector",
            trace_id=violation.correlation_id,
            payload={
                "intent_event_id": str(violation.event_id),
                "correlation_id": violation.correlation_id,
                "violation_type": violation.violation_type.value,
                "original_event_type": violation.event_type,
                "orphan_age_seconds": violation.age.total_seconds(),
                "detected_at": now.isoformat(),
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        await self._ledger.append_event(event)

    async def scan_and_emit_violations(self) -> list[TwoPhaseViolation]:
        """Scan for violations and emit events for each.

        Convenience method that runs verify_two_phase_completeness and
        emits ledger events for all detected violations.

        Returns:
            List of violations that were detected and emitted.
        """
        violations = await self.verify_two_phase_completeness()

        for violation in violations:
            await self.emit_orphan_violation_event(violation)

        return violations

    async def get_intent_outcome_pair(
        self, correlation_id: str
    ) -> dict[str, Any] | None:
        """Get intent-outcome pair by correlation ID.

        Used by Knight to query two-phase event pairs for observability.

        Args:
            correlation_id: The correlation ID to look up.

        Returns:
            Dict with intent, outcome, and status. None if no intent found.
        """
        # Get intent event
        intents = await self._ledger.read_events(event_type_pattern="*.intent.emitted")

        intent = None
        for event in intents:
            if event.payload.get("correlation_id") == correlation_id:
                intent = event
                break

        if intent is None:
            return None

        # Get outcome event
        outcomes = await self._ledger.read_events(
            event_type_pattern="*.commit.confirmed|*.failure.recorded"
        )

        outcome = None
        for event in outcomes:
            if event.payload.get("correlation_id") == correlation_id:
                outcome = event
                break

        now = self._time_authority.now()
        is_pending = outcome is None and (now - intent.timestamp) < self._orphan_timeout

        return {
            "correlation_id": correlation_id,
            "intent": intent,
            "outcome": outcome,
            "is_pending": is_pending,
            "age_seconds": (now - intent.timestamp).total_seconds(),
        }

    @property
    def orphan_timeout(self) -> timedelta:
        """Get the configured orphan timeout threshold."""
        return self._orphan_timeout
