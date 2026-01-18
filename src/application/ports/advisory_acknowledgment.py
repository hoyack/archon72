"""Advisory Acknowledgment Tracking Port (FR-GOV-18).

This module defines domain models and abstract protocol for advisory acknowledgment
tracking. Advisories must be acknowledged but not obeyed.

Per Government PRD FR-GOV-18: Advisories must be acknowledged but not obeyed;
Marquis cannot judge domains where advisory was given.

Constitutional Truths honored:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-12: Witnessing creates accountability → All acknowledgments witnessed

HARDENING-1: All timestamps must be provided via TimeAuthorityProtocol injection.
Factory methods require explicit timestamp parameters - no datetime.now() calls.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

# =============================================================================
# DOMAIN MODELS
# =============================================================================


@dataclass(frozen=True)
class AdvisoryAcknowledgment:
    """Acknowledgment of an advisory receipt.

    Per FR-GOV-18: Acknowledgment is receipt confirmation, not agreement.
    The `approved` field is ALWAYS False - acknowledgment != approval.
    """

    acknowledgment_id: UUID
    advisory_id: UUID
    acknowledged_by: str  # Archon ID
    acknowledged_at: datetime
    understanding: str  # Brief statement of understanding
    approved: bool = False  # ALWAYS False - acknowledgment != approval

    @classmethod
    def create(
        cls,
        advisory_id: UUID,
        acknowledged_by: str,
        understanding: str,
        timestamp: datetime,
    ) -> "AdvisoryAcknowledgment":
        """Create a new acknowledgment.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            advisory_id: UUID of the advisory being acknowledged
            acknowledged_by: Archon ID acknowledging
            understanding: Brief statement of understanding
            timestamp: Current time from TimeAuthorityProtocol

        Returns:
            New immutable AdvisoryAcknowledgment with approved=False
        """
        return cls(
            acknowledgment_id=uuid4(),
            advisory_id=advisory_id,
            acknowledged_by=acknowledged_by,
            acknowledged_at=timestamp,
            understanding=understanding,
            approved=False,  # ALWAYS False per FR-GOV-18
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "acknowledgment_id": str(self.acknowledgment_id),
            "advisory_id": str(self.advisory_id),
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat(),
            "understanding": self.understanding,
            "approved": self.approved,  # Always False
        }


@dataclass(frozen=True)
class ContraryDecision:
    """A decision made contrary to an advisory.

    Per FR-GOV-18: Contrary decisions must document reasoning.
    Knight witnesses all contrary decisions per CT-12.
    """

    decision_id: UUID
    advisory_id: UUID  # Advisory being contradicted
    decided_by: str  # Archon ID who made contrary decision
    reasoning: str  # Why the advisory was not followed
    decision_summary: str  # What was decided instead
    decided_at: datetime
    witnessed_by: str  # Knight who witnessed (always "furcas")

    @classmethod
    def create(
        cls,
        advisory_id: UUID,
        decided_by: str,
        reasoning: str,
        decision_summary: str,
        timestamp: datetime,
        witnessed_by: str = "furcas",
    ) -> "ContraryDecision":
        """Create a new contrary decision record.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            advisory_id: UUID of the advisory being contradicted
            decided_by: Archon ID who made the contrary decision
            reasoning: Why the advisory was not followed
            decision_summary: What was decided instead
            timestamp: Current time from TimeAuthorityProtocol
            witnessed_by: Knight who witnessed (default: furcas)

        Returns:
            New immutable ContraryDecision
        """
        return cls(
            decision_id=uuid4(),
            advisory_id=advisory_id,
            decided_by=decided_by,
            reasoning=reasoning,
            decision_summary=decision_summary,
            decided_at=timestamp,
            witnessed_by=witnessed_by,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "decision_id": str(self.decision_id),
            "advisory_id": str(self.advisory_id),
            "decided_by": self.decided_by,
            "reasoning": self.reasoning,
            "decision_summary": self.decision_summary,
            "decided_at": self.decided_at.isoformat(),
            "witnessed_by": self.witnessed_by,
        }


@dataclass(frozen=True)
class AdvisoryWindow:
    """Window during which a Marquis cannot judge on advised topic.

    Per FR-GOV-18: Marquis cannot judge domains where advisory was given.
    This creates a conflict-of-interest window.
    """

    window_id: UUID
    marquis_id: str  # Marquis who issued advisory
    advisory_id: UUID
    topic: str
    opened_at: datetime
    closed_at: datetime | None = None  # None = still open

    @classmethod
    def create(
        cls,
        marquis_id: str,
        advisory_id: UUID,
        topic: str,
        timestamp: datetime,
    ) -> "AdvisoryWindow":
        """Create a new advisory window.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            marquis_id: Marquis who issued the advisory
            advisory_id: UUID of the advisory
            topic: Topic of the advisory
            timestamp: Current time from TimeAuthorityProtocol

        Returns:
            New immutable AdvisoryWindow (open)
        """
        return cls(
            window_id=uuid4(),
            marquis_id=marquis_id,
            advisory_id=advisory_id,
            topic=topic,
            opened_at=timestamp,
            closed_at=None,  # Open by default
        )

    def with_closed(self, timestamp: datetime) -> "AdvisoryWindow":
        """Create a new window with closed timestamp.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            timestamp: When the window closed from TimeAuthorityProtocol

        Returns:
            New AdvisoryWindow with closed_at set
        """
        return AdvisoryWindow(
            window_id=self.window_id,
            marquis_id=self.marquis_id,
            advisory_id=self.advisory_id,
            topic=self.topic,
            opened_at=self.opened_at,
            closed_at=timestamp,
        )

    @property
    def is_open(self) -> bool:
        """Check if the window is still open."""
        return self.closed_at is None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "window_id": str(self.window_id),
            "marquis_id": self.marquis_id,
            "advisory_id": str(self.advisory_id),
            "topic": self.topic,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "is_open": self.is_open,
        }


class AcknowledgmentDeadlineStatus(Enum):
    """Status of acknowledgment deadline."""

    PENDING = "pending"  # Deadline not yet reached
    WARNING = "warning"  # Deadline passed, warning generated
    ESCALATED = "escalated"  # Pattern continued, escalated to Conclave


@dataclass(frozen=True)
class DeadlineViolation:
    """Record of a missed acknowledgment deadline.

    Generated when an archon fails to acknowledge an advisory in time.
    """

    violation_id: UUID
    advisory_id: UUID
    archon_id: str  # Archon who missed deadline
    deadline: datetime
    detected_at: datetime
    status: AcknowledgmentDeadlineStatus
    consecutive_misses: int  # For pattern detection

    @classmethod
    def create(
        cls,
        advisory_id: UUID,
        archon_id: str,
        deadline: datetime,
        timestamp: datetime,
        consecutive_misses: int = 1,
        status: AcknowledgmentDeadlineStatus = AcknowledgmentDeadlineStatus.WARNING,
    ) -> "DeadlineViolation":
        """Create a new deadline violation.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            advisory_id: UUID of the advisory
            archon_id: Archon who missed deadline
            deadline: When acknowledgment was due
            timestamp: Current time from TimeAuthorityProtocol
            consecutive_misses: Count of consecutive misses
            status: Violation status

        Returns:
            New immutable DeadlineViolation
        """
        return cls(
            violation_id=uuid4(),
            advisory_id=advisory_id,
            archon_id=archon_id,
            deadline=deadline,
            detected_at=timestamp,
            status=status,
            consecutive_misses=consecutive_misses,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "violation_id": str(self.violation_id),
            "advisory_id": str(self.advisory_id),
            "archon_id": self.archon_id,
            "deadline": self.deadline.isoformat(),
            "detected_at": self.detected_at.isoformat(),
            "status": self.status.value,
            "consecutive_misses": self.consecutive_misses,
        }


# =============================================================================
# REQUEST/RESULT MODELS
# =============================================================================


@dataclass
class AcknowledgmentRequest:
    """Request to acknowledge an advisory."""

    advisory_id: UUID
    archon_id: str
    understanding: str


@dataclass
class AcknowledgmentResult:
    """Result of acknowledgment attempt."""

    success: bool
    acknowledgment: AdvisoryAcknowledgment | None = None
    error: str | None = None


@dataclass
class ContraryDecisionRequest:
    """Request to record a contrary decision."""

    advisory_id: UUID
    decided_by: str
    reasoning: str
    decision_summary: str


@dataclass
class ContraryDecisionResult:
    """Result of contrary decision recording."""

    success: bool
    decision: ContraryDecision | None = None
    error: str | None = None


@dataclass
class JudgmentEligibilityResult:
    """Result of checking if Marquis can judge a topic."""

    can_judge: bool
    conflicting_window: AdvisoryWindow | None = None
    reason: str | None = None


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class AdvisoryTrackingConfig:
    """Configuration for advisory acknowledgment tracking.

    Default values per story specification.
    """

    acknowledgment_deadline_hours: int = 48
    window_close_on_motion_complete: bool = True
    warning_on_missed_deadline: bool = True
    escalate_pattern_threshold: int = 3  # Escalate after 3 missed deadlines

    @property
    def acknowledgment_deadline(self) -> timedelta:
        """Get the acknowledgment deadline as a timedelta."""
        return timedelta(hours=self.acknowledgment_deadline_hours)


# Default configuration
DEFAULT_CONFIG = AdvisoryTrackingConfig()


# =============================================================================
# PROTOCOL
# =============================================================================


class AdvisoryAcknowledgmentProtocol(ABC):
    """Abstract protocol for advisory acknowledgment tracking.

    Per Government PRD FR-GOV-18: Advisories must be acknowledged but not obeyed;
    Marquis cannot judge domains where advisory was given.

    This protocol handles:
    - Recording acknowledgments (receipt, not approval)
    - Tracking contrary decisions (with reasoning)
    - Deadline enforcement
    - Advisory window tracking (Marquis-Judge conflict prevention)

    All operations are witnessed by Knight per CT-12.
    """

    # =========================================================================
    # ACKNOWLEDGMENT OPERATIONS (AC1, AC5)
    # =========================================================================

    @abstractmethod
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
        ...

    # =========================================================================
    # CONTRARY DECISION OPERATIONS (AC2)
    # =========================================================================

    @abstractmethod
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
        ...

    # =========================================================================
    # REPOSITORY QUERIES (AC3)
    # =========================================================================

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    # =========================================================================
    # DEADLINE OPERATIONS (AC4)
    # =========================================================================

    @abstractmethod
    async def check_deadline_violations(self) -> list[DeadlineViolation]:
        """Check for acknowledgment deadline violations.

        Per AC4: Generate warning on missed deadline, escalate if pattern.

        Returns:
            List of deadline violations detected
        """
        ...

    @abstractmethod
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
        ...

    # =========================================================================
    # ADVISORY WINDOW OPERATIONS (AC6)
    # =========================================================================

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    # =========================================================================
    # STATISTICS
    # =========================================================================

    @abstractmethod
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
        ...
