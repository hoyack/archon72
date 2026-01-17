"""Advisory Conflict Detection Service (FR-GOV-18).

Implements conflict detection and prevention when a Marquis who advised on a topic
attempts to judge that same topic.

Per Government PRD FR-GOV-18: Marquis cannot judge domains where advisory was given.
Per PRD §2.1: No entity may define intent, execute it, AND judge it.

Constitutional Truths honored:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-12: Witnessing creates accountability → All conflicts witnessed
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from src.application.ports.advisory_acknowledgment import (
    AdvisoryAcknowledgmentProtocol,
    AdvisoryWindow,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
    WitnessStatementType,
)


# =============================================================================
# DOMAIN MODELS
# =============================================================================


@dataclass(frozen=True)
class TopicOverlap:
    """Result of topic overlap analysis.

    Used to determine if an advisory topic conflicts with a judgment topic.
    """

    overlap_score: float  # 0.0 to 1.0
    advisory_topic: str
    judgment_topic: str
    is_conflict: bool  # True if score > threshold
    matching_keywords: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "overlap_score": self.overlap_score,
            "advisory_topic": self.advisory_topic,
            "judgment_topic": self.judgment_topic,
            "is_conflict": self.is_conflict,
            "matching_keywords": list(self.matching_keywords),
        }


class ConflictResolution(Enum):
    """Resolution action for a conflict."""

    EXCLUDED = "excluded"  # Marquis excluded from panel
    VIOLATED = "violated"  # Attempted participation despite conflict
    ESCALATED = "escalated"  # All Princes conflicted, escalated to Conclave
    CLEARED = "cleared"  # No conflict detected


@dataclass(frozen=True)
class AdvisoryConflict:
    """A detected conflict between advisory and judgment roles.

    Per FR-GOV-18: Marquis cannot judge domains where advisory was given.
    """

    conflict_id: UUID
    marquis_id: str
    advisory_id: UUID
    advisory_topic: str
    judgment_topic: str
    overlap: TopicOverlap
    detected_at: datetime
    resolution: ConflictResolution

    @classmethod
    def create(
        cls,
        marquis_id: str,
        advisory_id: UUID,
        advisory_topic: str,
        judgment_topic: str,
        overlap: TopicOverlap,
        resolution: ConflictResolution = ConflictResolution.EXCLUDED,
    ) -> "AdvisoryConflict":
        """Create a new advisory conflict."""
        return cls(
            conflict_id=uuid4(),
            marquis_id=marquis_id,
            advisory_id=advisory_id,
            advisory_topic=advisory_topic,
            judgment_topic=judgment_topic,
            overlap=overlap,
            detected_at=datetime.now(timezone.utc),
            resolution=resolution,
        )

    def with_resolution(self, resolution: ConflictResolution) -> "AdvisoryConflict":
        """Create new conflict with updated resolution."""
        return AdvisoryConflict(
            conflict_id=self.conflict_id,
            marquis_id=self.marquis_id,
            advisory_id=self.advisory_id,
            advisory_topic=self.advisory_topic,
            judgment_topic=self.judgment_topic,
            overlap=self.overlap,
            detected_at=self.detected_at,
            resolution=resolution,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "conflict_id": str(self.conflict_id),
            "marquis_id": self.marquis_id,
            "advisory_id": str(self.advisory_id),
            "advisory_topic": self.advisory_topic,
            "judgment_topic": self.judgment_topic,
            "overlap": self.overlap.to_dict(),
            "detected_at": self.detected_at.isoformat(),
            "resolution": self.resolution.value,
        }


class ViolationSeverity(Enum):
    """Severity levels for violations."""

    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


@dataclass(frozen=True)
class AdvisoryConflictViolation:
    """Violation when a conflicted Marquis attempts judgment.

    Per FR-GOV-18: This is a MAJOR severity violation.
    """

    violation_id: UUID
    conflict: AdvisoryConflict
    attempted_action: str
    invalidated: bool = True
    severity: ViolationSeverity = ViolationSeverity.MAJOR
    witnessed_by: str = "furcas"  # Knight-Witness

    @classmethod
    def create(
        cls,
        conflict: AdvisoryConflict,
        attempted_action: str,
        witnessed_by: str = "furcas",
    ) -> "AdvisoryConflictViolation":
        """Create a new conflict violation."""
        return cls(
            violation_id=uuid4(),
            conflict=conflict,
            attempted_action=attempted_action,
            invalidated=True,  # Always invalidate
            severity=ViolationSeverity.MAJOR,  # Per AC3
            witnessed_by=witnessed_by,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "violation_id": str(self.violation_id),
            "conflict": self.conflict.to_dict(),
            "attempted_action": self.attempted_action,
            "invalidated": self.invalidated,
            "severity": self.severity.value,
            "witnessed_by": self.witnessed_by,
        }


class AuditEventType(Enum):
    """Types of audit events for conflict tracking."""

    DETECTED = "detected"
    EXCLUDED = "excluded"
    VIOLATED = "violated"
    ESCALATED = "escalated"
    CLEARED = "cleared"


@dataclass(frozen=True)
class ConflictAuditEntry:
    """Audit trail entry for conflict detection.

    Per AC6: Full audit trail must be maintained.
    """

    entry_id: UUID
    conflict_id: UUID | None  # None if no conflict (cleared)
    event_type: AuditEventType
    marquis_id: str
    advisory_topic: str | None
    judgment_topic: str
    details: dict[str, Any]
    recorded_at: datetime

    @classmethod
    def create(
        cls,
        event_type: AuditEventType,
        marquis_id: str,
        judgment_topic: str,
        advisory_topic: str | None = None,
        conflict_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> "ConflictAuditEntry":
        """Create a new audit entry."""
        return cls(
            entry_id=uuid4(),
            conflict_id=conflict_id,
            event_type=event_type,
            marquis_id=marquis_id,
            advisory_topic=advisory_topic,
            judgment_topic=judgment_topic,
            details=details or {},
            recorded_at=datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entry_id": str(self.entry_id),
            "conflict_id": str(self.conflict_id) if self.conflict_id else None,
            "event_type": self.event_type.value,
            "marquis_id": self.marquis_id,
            "advisory_topic": self.advisory_topic,
            "judgment_topic": self.judgment_topic,
            "details": self.details,
            "recorded_at": self.recorded_at.isoformat(),
        }


# =============================================================================
# REQUEST/RESULT MODELS
# =============================================================================


@dataclass
class ConflictDetectionRequest:
    """Request to detect conflicts for a judgment."""

    marquis_id: str
    judgment_topic: str


@dataclass
class ConflictDetectionResult:
    """Result of conflict detection."""

    has_conflict: bool
    conflicts: list[AdvisoryConflict] = field(default_factory=list)
    can_judge: bool = True
    reason: str | None = None


@dataclass
class PanelFormationRequest:
    """Request to form a Prince panel for judgment."""

    judgment_topic: str
    available_princes: list[str]  # List of Prince Archon IDs


@dataclass
class PanelFormationResult:
    """Result of panel formation."""

    success: bool
    panel: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    escalated: bool = False
    reason: str | None = None


@dataclass
class ParticipationCheckRequest:
    """Request to check if participation is allowed."""

    marquis_id: str
    judgment_topic: str
    action: str  # e.g., "evaluate_compliance", "issue_finding"


@dataclass
class ParticipationCheckResult:
    """Result of participation check."""

    allowed: bool
    violation: AdvisoryConflictViolation | None = None
    reason: str | None = None


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class ConflictDetectionConfig:
    """Configuration for conflict detection."""

    overlap_threshold: float = 0.6  # Similarity score to consider conflict
    exclusion_automatic: bool = True  # Auto-exclude conflicted Marquis
    violation_severity: ViolationSeverity = ViolationSeverity.MAJOR
    escalation_enabled: bool = True  # Escalate when all Princes conflicted


DEFAULT_CONFIG = ConflictDetectionConfig()


# =============================================================================
# SERVICE
# =============================================================================


class AdvisoryConflictDetectionService:
    """Service for detecting and managing advisory-judgment conflicts.

    Per FR-GOV-18: Marquis cannot judge domains where advisory was given.
    Per PRD §2.1: No entity may define intent, execute it, AND judge it.

    This service:
    - Detects conflicts between advisory and judgment topics
    - Excludes conflicted Marquis from Prince panels
    - Records violations for attempted participation
    - Maintains full audit trail
    """

    def __init__(
        self,
        advisory_service: AdvisoryAcknowledgmentProtocol | None = None,
        knight_witness: KnightWitnessProtocol | None = None,
        config: ConflictDetectionConfig | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            advisory_service: Service for querying advisory windows
            knight_witness: Knight witness service for CT-12 compliance
            config: Configuration for conflict detection
        """
        self._advisory_service = advisory_service
        self._knight_witness = knight_witness
        self._config = config or DEFAULT_CONFIG

        # In-memory storage for conflicts and audit trail
        self._conflicts: dict[UUID, AdvisoryConflict] = {}
        self._violations: dict[UUID, AdvisoryConflictViolation] = {}
        self._audit_trail: list[ConflictAuditEntry] = []

        # Direct window storage for testing without advisory service
        self._advisory_windows: dict[str, list[AdvisoryWindow]] = {}

    # =========================================================================
    # ADVISORY WINDOW REGISTRATION (for testing)
    # =========================================================================

    def register_advisory_window(self, window: AdvisoryWindow) -> None:
        """Register an advisory window directly (for testing).

        In production, windows come from AdvisoryAcknowledgmentService.

        Args:
            window: The advisory window to register
        """
        if window.marquis_id not in self._advisory_windows:
            self._advisory_windows[window.marquis_id] = []
        self._advisory_windows[window.marquis_id].append(window)

    # =========================================================================
    # CONFLICT DETECTION (AC1, AC4)
    # =========================================================================

    async def detect_conflicts(
        self,
        request: ConflictDetectionRequest,
    ) -> ConflictDetectionResult:
        """Detect conflicts for a Marquis on a judgment topic.

        Per AC1: Detect conflicts when topic comes to judicial review.
        Per AC4: Use semantic similarity to detect overlapping topics.

        Args:
            request: Detection request with marquis_id and topic

        Returns:
            ConflictDetectionResult with conflicts and can_judge status
        """
        conflicts: list[AdvisoryConflict] = []

        # Get advisory windows for this Marquis
        windows = await self._get_advisory_windows(request.marquis_id)

        for window in windows:
            if not window.is_open:
                continue

            # Calculate topic overlap
            overlap = self._calculate_topic_overlap(
                window.topic,
                request.judgment_topic,
            )

            if overlap.is_conflict:
                conflict = AdvisoryConflict.create(
                    marquis_id=request.marquis_id,
                    advisory_id=window.advisory_id,
                    advisory_topic=window.topic,
                    judgment_topic=request.judgment_topic,
                    overlap=overlap,
                    resolution=ConflictResolution.EXCLUDED,
                )
                conflicts.append(conflict)
                self._conflicts[conflict.conflict_id] = conflict

                # Record audit entry
                audit_entry = ConflictAuditEntry.create(
                    event_type=AuditEventType.DETECTED,
                    marquis_id=request.marquis_id,
                    judgment_topic=request.judgment_topic,
                    advisory_topic=window.topic,
                    conflict_id=conflict.conflict_id,
                    details={
                        "overlap_score": overlap.overlap_score,
                        "matching_keywords": list(overlap.matching_keywords),
                    },
                )
                self._audit_trail.append(audit_entry)

                # Witness the conflict detection per CT-12
                await self._witness_conflict_detection(conflict)

        if conflicts:
            return ConflictDetectionResult(
                has_conflict=True,
                conflicts=conflicts,
                can_judge=False,
                reason=f"Marquis {request.marquis_id} has {len(conflicts)} conflicting advisory(s) on topic '{request.judgment_topic}' per FR-GOV-18",
            )

        # Record cleared audit entry
        audit_entry = ConflictAuditEntry.create(
            event_type=AuditEventType.CLEARED,
            marquis_id=request.marquis_id,
            judgment_topic=request.judgment_topic,
            details={"windows_checked": len(windows)},
        )
        self._audit_trail.append(audit_entry)

        return ConflictDetectionResult(
            has_conflict=False,
            conflicts=[],
            can_judge=True,
            reason=None,
        )

    def _calculate_topic_overlap(
        self,
        advisory_topic: str,
        judgment_topic: str,
    ) -> TopicOverlap:
        """Calculate semantic overlap between topics.

        Per AC4: Use semantic similarity with configurable threshold.

        Args:
            advisory_topic: Topic from advisory
            judgment_topic: Topic for judgment

        Returns:
            TopicOverlap with score and conflict determination
        """
        a_lower = advisory_topic.lower().strip()
        j_lower = judgment_topic.lower().strip()

        # Exact match
        if a_lower == j_lower:
            return TopicOverlap(
                overlap_score=1.0,
                advisory_topic=advisory_topic,
                judgment_topic=judgment_topic,
                is_conflict=True,
                matching_keywords=(advisory_topic,),
            )

        # Contains match
        if a_lower in j_lower or j_lower in a_lower:
            return TopicOverlap(
                overlap_score=0.85,
                advisory_topic=advisory_topic,
                judgment_topic=judgment_topic,
                is_conflict=True,
                matching_keywords=(min(a_lower, j_lower, key=len),),
            )

        # Keyword analysis
        keywords_a = set(a_lower.split())
        keywords_j = set(j_lower.split())

        # Remove common stop words
        stop_words = {"the", "a", "an", "on", "in", "for", "of", "to", "and", "or", "is"}
        keywords_a -= stop_words
        keywords_j -= stop_words

        if not keywords_a or not keywords_j:
            return TopicOverlap(
                overlap_score=0.0,
                advisory_topic=advisory_topic,
                judgment_topic=judgment_topic,
                is_conflict=False,
                matching_keywords=(),
            )

        common = keywords_a & keywords_j
        total = keywords_a | keywords_j
        overlap_score = len(common) / len(total) if total else 0.0

        return TopicOverlap(
            overlap_score=overlap_score,
            advisory_topic=advisory_topic,
            judgment_topic=judgment_topic,
            is_conflict=overlap_score >= self._config.overlap_threshold,
            matching_keywords=tuple(common),
        )

    async def _get_advisory_windows(self, marquis_id: str) -> list[AdvisoryWindow]:
        """Get advisory windows for a Marquis.

        Uses advisory service if available, otherwise local storage.

        Args:
            marquis_id: The Marquis to query

        Returns:
            List of advisory windows
        """
        if self._advisory_service:
            return await self._advisory_service.get_open_windows(marquis_id)
        return self._advisory_windows.get(marquis_id, [])

    # =========================================================================
    # PRINCE PANEL MANAGEMENT (AC2, AC5)
    # =========================================================================

    async def form_unconflicted_panel(
        self,
        request: PanelFormationRequest,
    ) -> PanelFormationResult:
        """Form a Prince panel excluding conflicted members.

        Per AC2: Exclude conflicted Marquis from panel.
        Per AC5: Escalate if all Princes are conflicted.

        Args:
            request: Panel formation request with topic and available Princes

        Returns:
            PanelFormationResult with panel and any excluded members
        """
        panel: list[str] = []
        excluded: list[str] = []

        for prince_id in request.available_princes:
            # Check for conflicts
            detection_result = await self.detect_conflicts(
                ConflictDetectionRequest(
                    marquis_id=prince_id,
                    judgment_topic=request.judgment_topic,
                )
            )

            if detection_result.has_conflict:
                excluded.append(prince_id)

                # Record exclusion
                for conflict in detection_result.conflicts:
                    updated_conflict = conflict.with_resolution(
                        ConflictResolution.EXCLUDED
                    )
                    self._conflicts[conflict.conflict_id] = updated_conflict

                    audit_entry = ConflictAuditEntry.create(
                        event_type=AuditEventType.EXCLUDED,
                        marquis_id=prince_id,
                        judgment_topic=request.judgment_topic,
                        advisory_topic=conflict.advisory_topic,
                        conflict_id=conflict.conflict_id,
                        details={"panel_size": len(request.available_princes)},
                    )
                    self._audit_trail.append(audit_entry)
            else:
                panel.append(prince_id)

        # Check if we need to escalate
        if not panel and self._config.escalation_enabled:
            # All Princes conflicted - escalate to Conclave
            await self._escalate_to_conclave(
                request.judgment_topic,
                excluded,
            )

            return PanelFormationResult(
                success=False,
                panel=[],
                excluded=excluded,
                escalated=True,
                reason=f"All {len(excluded)} available Princes have conflicts on topic '{request.judgment_topic}'. Escalating to Conclave per AC5.",
            )

        return PanelFormationResult(
            success=True,
            panel=panel,
            excluded=excluded,
            escalated=False,
            reason=None if panel else "No unconflicted Princes available",
        )

    async def _escalate_to_conclave(
        self,
        judgment_topic: str,
        conflicted_princes: list[str],
    ) -> None:
        """Escalate to Conclave when all Princes are conflicted.

        Per AC5: Document the conflict pattern.

        Args:
            judgment_topic: The judgment topic
            conflicted_princes: List of conflicted Prince IDs
        """
        # Record audit entry for escalation
        audit_entry = ConflictAuditEntry.create(
            event_type=AuditEventType.ESCALATED,
            marquis_id="ALL",
            judgment_topic=judgment_topic,
            details={
                "conflicted_princes": conflicted_princes,
                "escalation_reason": "All available Princes have advisory conflicts",
            },
        )
        self._audit_trail.append(audit_entry)

        # Witness the escalation per CT-12
        if self._knight_witness:
            context = ObservationContext(
                event_type="ADVISORY_CONFLICT_ESCALATION",
                event_id=uuid4(),
                description=f"All Princes conflicted on topic '{judgment_topic}'. Escalating to Conclave.",
                participants=conflicted_princes,
                target_id=judgment_topic,
                target_type="judgment",
                metadata={
                    "conflicted_count": len(conflicted_princes),
                    "prd_reference": "FR-GOV-18, AC5",
                },
            )
            statement = self._knight_witness.observe(context)
            self._knight_witness.trigger_acknowledgment(statement.statement_id)

    # =========================================================================
    # PARTICIPATION VIOLATION DETECTION (AC3)
    # =========================================================================

    async def check_participation(
        self,
        request: ParticipationCheckRequest,
    ) -> ParticipationCheckResult:
        """Check if a Marquis can participate in judgment.

        Per AC3: Detect and invalidate participation by conflicted Marquis.

        Args:
            request: Participation check request

        Returns:
            ParticipationCheckResult with allowed status and any violation
        """
        # Detect conflicts
        detection_result = await self.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id=request.marquis_id,
                judgment_topic=request.judgment_topic,
            )
        )

        if not detection_result.has_conflict:
            return ParticipationCheckResult(
                allowed=True,
                violation=None,
                reason=None,
            )

        # Conflicted Marquis attempting participation - create violation
        conflict = detection_result.conflicts[0]  # Use first conflict

        # Update conflict resolution to VIOLATED
        updated_conflict = conflict.with_resolution(ConflictResolution.VIOLATED)
        self._conflicts[conflict.conflict_id] = updated_conflict

        # Create violation record
        violation = AdvisoryConflictViolation.create(
            conflict=updated_conflict,
            attempted_action=request.action,
            witnessed_by="furcas",
        )
        self._violations[violation.violation_id] = violation

        # Record audit entry
        audit_entry = ConflictAuditEntry.create(
            event_type=AuditEventType.VIOLATED,
            marquis_id=request.marquis_id,
            judgment_topic=request.judgment_topic,
            advisory_topic=conflict.advisory_topic,
            conflict_id=conflict.conflict_id,
            details={
                "attempted_action": request.action,
                "severity": violation.severity.value,
                "invalidated": violation.invalidated,
            },
        )
        self._audit_trail.append(audit_entry)

        # Witness the violation per CT-12
        await self._witness_violation(violation)

        return ParticipationCheckResult(
            allowed=False,
            violation=violation,
            reason=f"Marquis {request.marquis_id} has conflict on topic '{request.judgment_topic}' per FR-GOV-18. Action '{request.action}' invalidated.",
        )

    async def _witness_violation(
        self,
        violation: AdvisoryConflictViolation,
    ) -> None:
        """Witness a conflict violation per CT-12.

        Args:
            violation: The violation to witness
        """
        if not self._knight_witness:
            return

        violation_record = ViolationRecord(
            violation_type="branch_violation",
            violator_id=uuid4(),  # Would be actual Archon UUID in production
            violator_name=violation.conflict.marquis_id,
            violator_rank="marquis",
            description=f"Conflicted Marquis attempted {violation.attempted_action} on topic where advisory was given",
            target_id=str(violation.conflict.conflict_id),
            target_type="advisory_conflict",
            prd_reference="FR-GOV-18",
            requires_acknowledgment=True,
            metadata={
                "advisory_topic": violation.conflict.advisory_topic,
                "judgment_topic": violation.conflict.judgment_topic,
                "severity": violation.severity.value,
            },
        )

        self._knight_witness.record_violation(violation_record)

    async def _witness_conflict_detection(
        self,
        conflict: AdvisoryConflict,
    ) -> None:
        """Witness conflict detection per CT-12.

        Args:
            conflict: The detected conflict
        """
        if not self._knight_witness:
            return

        context = ObservationContext(
            event_type="ADVISORY_CONFLICT_DETECTED",
            event_id=conflict.conflict_id,
            description=f"Advisory conflict detected for {conflict.marquis_id} on topic '{conflict.judgment_topic}'",
            participants=[conflict.marquis_id],
            target_id=str(conflict.advisory_id),
            target_type="advisory",
            metadata={
                "overlap_score": conflict.overlap.overlap_score,
                "advisory_topic": conflict.advisory_topic,
                "prd_reference": "FR-GOV-18",
            },
        )
        self._knight_witness.observe(context)

    # =========================================================================
    # AUDIT TRAIL (AC6)
    # =========================================================================

    async def get_conflict_audit(
        self,
        conflict_id: UUID,
    ) -> list[ConflictAuditEntry]:
        """Get audit trail for a specific conflict.

        Per AC6: Full audit trail must be maintained.

        Args:
            conflict_id: UUID of the conflict

        Returns:
            List of audit entries for that conflict
        """
        return [
            entry
            for entry in self._audit_trail
            if entry.conflict_id == conflict_id
        ]

    async def get_audit_by_marquis(
        self,
        marquis_id: str,
    ) -> list[ConflictAuditEntry]:
        """Get audit trail for a specific Marquis.

        Args:
            marquis_id: Marquis ID

        Returns:
            List of audit entries for that Marquis
        """
        return [
            entry
            for entry in self._audit_trail
            if entry.marquis_id == marquis_id
        ]

    async def get_audit_by_topic(
        self,
        judgment_topic: str,
    ) -> list[ConflictAuditEntry]:
        """Get audit trail for a specific judgment topic.

        Args:
            judgment_topic: The judgment topic

        Returns:
            List of audit entries for that topic
        """
        return [
            entry
            for entry in self._audit_trail
            if entry.judgment_topic == judgment_topic
        ]

    async def get_full_audit_trail(self) -> list[ConflictAuditEntry]:
        """Get the complete audit trail.

        Returns:
            All audit entries
        """
        return list(self._audit_trail)

    # =========================================================================
    # QUERIES
    # =========================================================================

    async def get_conflict(self, conflict_id: UUID) -> AdvisoryConflict | None:
        """Get a conflict by ID.

        Args:
            conflict_id: UUID of the conflict

        Returns:
            AdvisoryConflict if found, None otherwise
        """
        return self._conflicts.get(conflict_id)

    async def get_violation(
        self,
        violation_id: UUID,
    ) -> AdvisoryConflictViolation | None:
        """Get a violation by ID.

        Args:
            violation_id: UUID of the violation

        Returns:
            AdvisoryConflictViolation if found, None otherwise
        """
        return self._violations.get(violation_id)

    async def get_conflicts_by_marquis(
        self,
        marquis_id: str,
    ) -> list[AdvisoryConflict]:
        """Get all conflicts for a Marquis.

        Args:
            marquis_id: Marquis ID

        Returns:
            List of conflicts for that Marquis
        """
        return [
            conflict
            for conflict in self._conflicts.values()
            if conflict.marquis_id == marquis_id
        ]

    async def get_violations_by_marquis(
        self,
        marquis_id: str,
    ) -> list[AdvisoryConflictViolation]:
        """Get all violations for a Marquis.

        Args:
            marquis_id: Marquis ID

        Returns:
            List of violations for that Marquis
        """
        return [
            violation
            for violation in self._violations.values()
            if violation.conflict.marquis_id == marquis_id
        ]

    # =========================================================================
    # STATISTICS
    # =========================================================================

    async def get_conflict_stats(self) -> dict[str, Any]:
        """Get statistics about conflicts.

        Returns:
            Dictionary with conflict statistics
        """
        conflicts_by_resolution = {
            resolution.value: 0 for resolution in ConflictResolution
        }
        for conflict in self._conflicts.values():
            conflicts_by_resolution[conflict.resolution.value] += 1

        return {
            "total_conflicts": len(self._conflicts),
            "total_violations": len(self._violations),
            "audit_entries": len(self._audit_trail),
            "conflicts_by_resolution": conflicts_by_resolution,
            "unique_marquis_with_conflicts": len(
                set(c.marquis_id for c in self._conflicts.values())
            ),
        }
