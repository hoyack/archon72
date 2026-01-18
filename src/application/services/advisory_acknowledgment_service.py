"""Advisory Acknowledgment Service Implementation.

Implements advisory acknowledgment tracking per FR-GOV-18:
- Advisories must be acknowledged but not obeyed
- Marquis cannot judge domains where advisory was given

Constitutional Truths honored:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-12: Witnessing creates accountability → All acknowledgments witnessed
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from src.application.ports.advisory_acknowledgment import (
    AcknowledgmentDeadlineStatus,
    AcknowledgmentRequest,
    AcknowledgmentResult,
    AdvisoryAcknowledgment,
    AdvisoryAcknowledgmentProtocol,
    AdvisoryTrackingConfig,
    AdvisoryWindow,
    ContraryDecision,
    ContraryDecisionRequest,
    ContraryDecisionResult,
    DeadlineViolation,
    JudgmentEligibilityResult,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
)
from src.application.ports.marquis_service import Advisory


class AdvisoryNotFoundError(Exception):
    """Raised when an advisory is not found."""

    pass


class DuplicateAcknowledgmentError(Exception):
    """Raised when an archon tries to acknowledge the same advisory twice."""

    pass


class AdvisoryWindowConflictError(Exception):
    """Raised when a Marquis tries to judge on a conflicting topic."""

    pass


class AdvisoryAcknowledgmentService(AdvisoryAcknowledgmentProtocol):
    """Service for tracking advisory acknowledgments.

    Per FR-GOV-18: Advisories must be acknowledged but not obeyed;
    Marquis cannot judge domains where advisory was given.

    This service:
    - Records acknowledgments (receipt, not approval)
    - Tracks contrary decisions with reasoning
    - Monitors acknowledgment deadlines
    - Prevents Marquis from judging advised domains
    """

    def __init__(
        self,
        config: AdvisoryTrackingConfig | None = None,
        knight_witness: KnightWitnessProtocol | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            config: Configuration for tracking (uses defaults if None)
            knight_witness: Knight witness service for CT-12 compliance
        """
        self._config = config or AdvisoryTrackingConfig()
        self._knight_witness = knight_witness

        # In-memory storage (would be replaced by repository in production)
        self._advisories: dict[UUID, Advisory] = {}
        self._acknowledgments: dict[UUID, list[AdvisoryAcknowledgment]] = {}
        self._contrary_decisions: dict[UUID, list[ContraryDecision]] = {}
        self._advisory_windows: dict[UUID, AdvisoryWindow] = {}
        self._deadline_violations: dict[str, int] = {}  # archon_id -> count
        self._advisory_recipients: dict[UUID, set[str]] = {}  # advisory_id -> archons

    # =========================================================================
    # ADVISORY REGISTRATION (for testing and integration)
    # =========================================================================

    async def register_advisory(
        self,
        advisory: Advisory,
        recipients: list[str],
    ) -> None:
        """Register an advisory for tracking.

        This is called when MarquisService issues an advisory.

        Args:
            advisory: The advisory to track
            recipients: List of archon IDs who should acknowledge
        """
        self._advisories[advisory.advisory_id] = advisory
        self._acknowledgments[advisory.advisory_id] = []
        self._contrary_decisions[advisory.advisory_id] = []
        self._advisory_recipients[advisory.advisory_id] = set(recipients)

        # Open advisory window per AC6
        window = await self.open_advisory_window(
            marquis_id=advisory.issued_by,
            advisory_id=advisory.advisory_id,
            topic=advisory.topic,
        )

        # Witness the advisory issuance per CT-12
        if self._knight_witness:
            context = ObservationContext(
                event_type="ADVISORY_ISSUED",
                event_id=advisory.advisory_id,
                description=f"Advisory issued by {advisory.issued_by} on topic: {advisory.topic}",
                participants=[advisory.issued_by] + recipients,
                target_id=str(advisory.advisory_id),
                target_type="advisory",
                metadata={
                    "domain": advisory.domain.value,
                    "recommendation": advisory.recommendation,
                    "window_id": str(window.window_id),
                },
            )
            self._knight_witness.observe(context)

    # =========================================================================
    # ACKNOWLEDGMENT OPERATIONS (AC1, AC5)
    # =========================================================================

    async def record_acknowledgment(
        self,
        request: AcknowledgmentRequest,
    ) -> AcknowledgmentResult:
        """Record acknowledgment of an advisory.

        Per AC1: Record acknowledgment with archon_id, timestamp, understanding.
        Per AC5: Acknowledgment explicitly states approved=False.

        Args:
            request: Acknowledgment request

        Returns:
            AcknowledgmentResult with acknowledgment (approved=False) or error
        """
        # Validate advisory exists
        if request.advisory_id not in self._advisories:
            return AcknowledgmentResult(
                success=False,
                error=f"Advisory {request.advisory_id} not found",
            )

        # Check for duplicate acknowledgment
        existing = self._acknowledgments.get(request.advisory_id, [])
        for ack in existing:
            if ack.acknowledged_by == request.archon_id:
                return AcknowledgmentResult(
                    success=False,
                    error=f"Archon {request.archon_id} has already acknowledged advisory {request.advisory_id}",
                )

        # Create acknowledgment with approved=False per AC5
        acknowledgment = AdvisoryAcknowledgment.create(
            advisory_id=request.advisory_id,
            acknowledged_by=request.archon_id,
            understanding=request.understanding,
        )

        # Store acknowledgment
        if request.advisory_id not in self._acknowledgments:
            self._acknowledgments[request.advisory_id] = []
        self._acknowledgments[request.advisory_id].append(acknowledgment)

        # Clear any deadline violation count for this archon
        if request.archon_id in self._deadline_violations:
            self._deadline_violations[request.archon_id] = 0

        # Witness the acknowledgment per CT-12
        if self._knight_witness:
            advisory = self._advisories[request.advisory_id]
            context = ObservationContext(
                event_type="ADVISORY_ACKNOWLEDGED",
                event_id=acknowledgment.acknowledgment_id,
                description=f"Advisory acknowledged by {request.archon_id}: {request.understanding}",
                participants=[request.archon_id, advisory.issued_by],
                target_id=str(request.advisory_id),
                target_type="advisory",
                metadata={
                    "acknowledgment_id": str(acknowledgment.acknowledgment_id),
                    "approved": False,  # Always False per AC5
                },
            )
            self._knight_witness.observe(context)

        return AcknowledgmentResult(
            success=True,
            acknowledgment=acknowledgment,
        )

    # =========================================================================
    # CONTRARY DECISION OPERATIONS (AC2)
    # =========================================================================

    async def record_contrary_decision(
        self,
        request: ContraryDecisionRequest,
    ) -> ContraryDecisionResult:
        """Record a decision made contrary to an advisory.

        Per AC2: Document reference, reasoning, who made decision.
        Knight witnesses the contrary decision per CT-12.

        Args:
            request: Contrary decision request

        Returns:
            ContraryDecisionResult with decision or error
        """
        # Validate advisory exists
        if request.advisory_id not in self._advisories:
            return ContraryDecisionResult(
                success=False,
                error=f"Advisory {request.advisory_id} not found",
            )

        # Create contrary decision (witnessed by Knight)
        decision = ContraryDecision.create(
            advisory_id=request.advisory_id,
            decided_by=request.decided_by,
            reasoning=request.reasoning,
            decision_summary=request.decision_summary,
            witnessed_by="furcas",  # Knight-Witness per CT-12
        )

        # Store the decision
        if request.advisory_id not in self._contrary_decisions:
            self._contrary_decisions[request.advisory_id] = []
        self._contrary_decisions[request.advisory_id].append(decision)

        # Witness the contrary decision per CT-12
        if self._knight_witness:
            advisory = self._advisories[request.advisory_id]
            context = ObservationContext(
                event_type="CONTRARY_DECISION",
                event_id=decision.decision_id,
                description=f"Contrary decision by {request.decided_by}: {request.decision_summary}",
                participants=[request.decided_by, advisory.issued_by],
                target_id=str(request.advisory_id),
                target_type="advisory",
                metadata={
                    "decision_id": str(decision.decision_id),
                    "reasoning": request.reasoning,
                    "advisory_topic": advisory.topic,
                },
            )
            statement = self._knight_witness.observe(context)
            # Contrary decisions require Conclave acknowledgment
            self._knight_witness.trigger_acknowledgment(statement.statement_id)

        return ContraryDecisionResult(
            success=True,
            decision=decision,
        )

    # =========================================================================
    # REPOSITORY QUERIES (AC3)
    # =========================================================================

    async def get_unacknowledged_advisories(
        self,
        archon_id: str,
    ) -> list[UUID]:
        """Get advisories pending acknowledgment by an archon.

        Per AC3: Provide list of unacknowledged advisories.

        Args:
            archon_id: Archon to check

        Returns:
            List of advisory UUIDs pending acknowledgment
        """
        unacknowledged = []

        for advisory_id, recipients in self._advisory_recipients.items():
            if archon_id not in recipients:
                continue

            # Check if already acknowledged
            acknowledgments = self._acknowledgments.get(advisory_id, [])
            acknowledged_by = {ack.acknowledged_by for ack in acknowledgments}

            if archon_id not in acknowledged_by:
                unacknowledged.append(advisory_id)

        return unacknowledged

    async def get_advisory_acknowledgments(
        self,
        advisory_id: UUID,
    ) -> list[AdvisoryAcknowledgment]:
        """Get all acknowledgments for an advisory.

        Per AC3: Provide all acknowledgments for an advisory.

        Args:
            advisory_id: UUID of the advisory

        Returns:
            List of acknowledgments
        """
        return list(self._acknowledgments.get(advisory_id, []))

    async def get_contrary_decisions(
        self,
        advisory_id: UUID,
    ) -> list[ContraryDecision]:
        """Get decisions that contradicted an advisory.

        Per AC3: Provide decisions that contradicted the advisory.

        Args:
            advisory_id: UUID of the advisory

        Returns:
            List of contrary decisions
        """
        return list(self._contrary_decisions.get(advisory_id, []))

    # =========================================================================
    # DEADLINE OPERATIONS (AC4)
    # =========================================================================

    async def check_deadline_violations(self) -> list[DeadlineViolation]:
        """Check for acknowledgment deadline violations.

        Per AC4: Generate warning on missed deadline, escalate if pattern.

        Returns:
            List of deadline violations detected
        """
        violations = []
        now = datetime.now(timezone.utc)

        for advisory_id, recipients in self._advisory_recipients.items():
            advisory = self._advisories.get(advisory_id)
            if not advisory:
                continue

            deadline = advisory.issued_at + self._config.acknowledgment_deadline
            if now < deadline:
                continue  # Not yet past deadline

            # Check each recipient
            acknowledgments = self._acknowledgments.get(advisory_id, [])
            acknowledged_by = {ack.acknowledged_by for ack in acknowledgments}

            for archon_id in recipients:
                if archon_id in acknowledged_by:
                    continue  # Already acknowledged

                # Increment violation count
                if archon_id not in self._deadline_violations:
                    self._deadline_violations[archon_id] = 0
                self._deadline_violations[archon_id] += 1
                consecutive = self._deadline_violations[archon_id]

                # Determine status based on pattern
                if consecutive >= self._config.escalate_pattern_threshold:
                    status = AcknowledgmentDeadlineStatus.ESCALATED
                else:
                    status = AcknowledgmentDeadlineStatus.WARNING

                violation = DeadlineViolation.create(
                    advisory_id=advisory_id,
                    archon_id=archon_id,
                    deadline=deadline,
                    consecutive_misses=consecutive,
                    status=status,
                )
                violations.append(violation)

                # Witness the violation per CT-12
                if self._knight_witness and self._config.warning_on_missed_deadline:
                    context = ObservationContext(
                        event_type="ACKNOWLEDGMENT_DEADLINE_MISSED",
                        event_id=violation.violation_id,
                        description=f"Acknowledgment deadline missed by {archon_id} for advisory {advisory_id}",
                        participants=[archon_id, advisory.issued_by],
                        target_id=str(advisory_id),
                        target_type="advisory",
                        metadata={
                            "deadline": deadline.isoformat(),
                            "consecutive_misses": consecutive,
                            "status": status.value,
                        },
                    )
                    statement = self._knight_witness.observe(context)

                    # Escalated violations require Conclave acknowledgment
                    if status == AcknowledgmentDeadlineStatus.ESCALATED:
                        self._knight_witness.trigger_acknowledgment(
                            statement.statement_id
                        )

        return violations

    async def get_deadline_for_advisory(
        self,
        advisory_id: UUID,
    ) -> datetime | None:
        """Get the acknowledgment deadline for an advisory.

        Args:
            advisory_id: UUID of the advisory

        Returns:
            Deadline datetime or None if advisory not found
        """
        advisory = self._advisories.get(advisory_id)
        if not advisory:
            return None
        return advisory.issued_at + self._config.acknowledgment_deadline

    # =========================================================================
    # ADVISORY WINDOW OPERATIONS (AC6)
    # =========================================================================

    async def open_advisory_window(
        self,
        marquis_id: str,
        advisory_id: UUID,
        topic: str,
    ) -> AdvisoryWindow:
        """Open an advisory window when advisory is issued.

        Per AC6: Track window where Marquis cannot judge on topic.

        Args:
            marquis_id: Marquis who issued advisory
            advisory_id: UUID of the advisory
            topic: Topic of the advisory

        Returns:
            Opened AdvisoryWindow
        """
        window = AdvisoryWindow.create(
            marquis_id=marquis_id,
            advisory_id=advisory_id,
            topic=topic,
        )
        self._advisory_windows[window.window_id] = window

        # Witness window opening per CT-12
        if self._knight_witness:
            context = ObservationContext(
                event_type="ADVISORY_WINDOW_OPENED",
                event_id=window.window_id,
                description=f"Advisory window opened for {marquis_id} on topic: {topic}",
                participants=[marquis_id],
                target_id=str(advisory_id),
                target_type="advisory",
                metadata={
                    "window_id": str(window.window_id),
                    "topic": topic,
                },
            )
            self._knight_witness.observe(context)

        return window

    async def close_advisory_window(
        self,
        window_id: UUID,
    ) -> AdvisoryWindow | None:
        """Close an advisory window.

        Args:
            window_id: UUID of the window to close

        Returns:
            Closed AdvisoryWindow or None if not found
        """
        window = self._advisory_windows.get(window_id)
        if not window:
            return None

        closed_window = window.with_closed()
        self._advisory_windows[window_id] = closed_window

        # Witness window closing per CT-12
        if self._knight_witness:
            context = ObservationContext(
                event_type="ADVISORY_WINDOW_CLOSED",
                event_id=window_id,
                description=f"Advisory window closed for {window.marquis_id} on topic: {window.topic}",
                participants=[window.marquis_id],
                target_id=str(window.advisory_id),
                target_type="advisory",
                metadata={
                    "window_id": str(window_id),
                    "topic": window.topic,
                    "duration_seconds": (
                        closed_window.closed_at - window.opened_at
                    ).total_seconds()
                    if closed_window.closed_at
                    else None,
                },
            )
            self._knight_witness.observe(context)

        return closed_window

    async def check_can_judge(
        self,
        marquis_id: str,
        topic: str,
    ) -> JudgmentEligibilityResult:
        """Check if a Marquis can judge on a topic.

        Per FR-GOV-18: Cannot judge domains where advisory was given.

        Args:
            marquis_id: Marquis ID to check
            topic: Topic to judge

        Returns:
            JudgmentEligibilityResult with can_judge and any conflicting window
        """
        open_windows = await self.get_open_windows(marquis_id)

        for window in open_windows:
            if self._topics_overlap(window.topic, topic):
                return JudgmentEligibilityResult(
                    can_judge=False,
                    conflicting_window=window,
                    reason=f"Marquis {marquis_id} has open advisory window on topic '{window.topic}' "
                    f"which conflicts with judgment topic '{topic}' per FR-GOV-18",
                )

        return JudgmentEligibilityResult(
            can_judge=True,
            conflicting_window=None,
            reason=None,
        )

    async def get_open_windows(
        self,
        marquis_id: str,
    ) -> list[AdvisoryWindow]:
        """Get all open advisory windows for a Marquis.

        Args:
            marquis_id: Marquis ID

        Returns:
            List of open AdvisoryWindows
        """
        return [
            window
            for window in self._advisory_windows.values()
            if window.marquis_id == marquis_id and window.is_open
        ]

    def _topics_overlap(self, topic1: str, topic2: str) -> bool:
        """Check if two topics overlap.

        Simple implementation using substring matching.
        Could be enhanced with semantic similarity in production.

        Args:
            topic1: First topic
            topic2: Second topic

        Returns:
            True if topics overlap
        """
        t1 = topic1.lower().strip()
        t2 = topic2.lower().strip()

        # Exact match
        if t1 == t2:
            return True

        # Substring match
        if t1 in t2 or t2 in t1:
            return True

        # Word overlap
        words1 = set(t1.split())
        words2 = set(t2.split())
        common = words1 & words2
        if len(common) >= 2:  # At least 2 words in common
            return True

        return False

    # =========================================================================
    # STATISTICS
    # =========================================================================

    async def get_acknowledgment_stats(
        self,
        hours: int = 24,
    ) -> dict[str, Any]:
        """Get acknowledgment statistics for the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with statistics
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        total_advisories = len(self._advisories)
        total_acknowledgments = sum(
            len([a for a in acks if a.acknowledged_at >= cutoff])
            for acks in self._acknowledgments.values()
        )
        total_contrary = sum(
            len([d for d in decisions if d.decided_at >= cutoff])
            for decisions in self._contrary_decisions.values()
        )
        open_windows = sum(1 for w in self._advisory_windows.values() if w.is_open)

        # Count pending acknowledgments
        pending = 0
        for advisory_id, recipients in self._advisory_recipients.items():
            acks = self._acknowledgments.get(advisory_id, [])
            acknowledged = {a.acknowledged_by for a in acks}
            pending += len(recipients - acknowledged)

        return {
            "period_hours": hours,
            "total_advisories": total_advisories,
            "acknowledgments_in_period": total_acknowledgments,
            "contrary_decisions_in_period": total_contrary,
            "pending_acknowledgments": pending,
            "open_advisory_windows": open_windows,
            "archons_with_deadline_violations": len(
                [c for c in self._deadline_violations.values() if c > 0]
            ),
        }
