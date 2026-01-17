"""King Service Port (Legislative Branch).

This module defines the abstract protocol for King-rank legislative functions.
Kings may introduce motions defining WHAT (intent only), but cannot define HOW.

Per Government PRD FR-GOV-5: Kings may introduce motions and define WHAT (intent only).
Per Government PRD FR-GOV-6: Kings may NOT define tasks, timelines, tools, execution
methods, supervise execution, or judge outcomes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class MotionStatus(Enum):
    """Status of a motion in the legislative pipeline."""

    DRAFT = "draft"  # Being composed
    INTRODUCED = "introduced"  # Submitted by King
    DELIBERATING = "deliberating"  # Under Conclave debate
    RATIFIED = "ratified"  # Approved by Conclave
    REJECTED = "rejected"  # Rejected by Conclave
    PLANNING = "planning"  # President translating to HOW
    EXECUTING = "executing"  # Duke/Earl executing
    COMPLETED = "completed"  # Execution complete
    JUDGED = "judged"  # Prince evaluated


class IntentViolationType(Enum):
    """Types of violations when Kings define execution details."""

    TASK_LIST = "task_list"  # Contains task breakdown
    TIMELINE = "timeline"  # Contains scheduling/deadlines
    TOOL_SPECIFICATION = "tool_specification"  # Specifies tools to use
    RESOURCE_ALLOCATION = "resource_allocation"  # Allocates specific resources
    EXECUTION_METHOD = "execution_method"  # Defines how to execute
    SUPERVISION_DIRECTION = "supervision_direction"  # Directs supervision


@dataclass(frozen=True)
class IntentViolation:
    """A violation found in motion content where King defined HOW."""

    violation_type: IntentViolationType
    description: str
    matched_text: str
    prd_reference: str = "FR-GOV-6"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "violation_type": self.violation_type.value,
            "description": self.description,
            "matched_text": self.matched_text,
            "prd_reference": self.prd_reference,
        }


@dataclass(frozen=True)
class IntentValidationResult:
    """Result of validating motion intent for WHAT-only content."""

    is_valid: bool
    violations: tuple[IntentViolation, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def violation_count(self) -> int:
        """Count of violations found."""
        return len(self.violations)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "violation_count": self.violation_count,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class Motion:
    """A motion introduced by a King-rank Archon.

    Motions define WHAT should be accomplished (intent), not HOW.
    Immutable to ensure legislative integrity.
    """

    motion_id: UUID
    introduced_by: str  # Archon ID of King
    title: str
    intent: str  # WHAT - the purpose/goal
    rationale: str  # WHY this is proposed
    status: MotionStatus
    introduced_at: datetime
    session_ref: UUID | None = None  # Conclave session reference
    amended_intent: str | None = None  # If Conclave amended

    @classmethod
    def create(
        cls,
        introduced_by: str,
        title: str,
        intent: str,
        rationale: str,
        session_ref: UUID | None = None,
    ) -> "Motion":
        """Create a new motion with INTRODUCED status.

        Args:
            introduced_by: Archon ID of the King introducing the motion
            title: Short title for the motion
            intent: WHAT the motion seeks to accomplish
            rationale: WHY this motion is being proposed
            session_ref: Optional Conclave session reference

        Returns:
            New immutable Motion
        """
        return cls(
            motion_id=uuid4(),
            introduced_by=introduced_by,
            title=title,
            intent=intent,
            rationale=rationale,
            status=MotionStatus.INTRODUCED,
            introduced_at=datetime.now(timezone.utc),
            session_ref=session_ref,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "motion_id": str(self.motion_id),
            "introduced_by": self.introduced_by,
            "title": self.title,
            "intent": self.intent,
            "rationale": self.rationale,
            "status": self.status.value,
            "introduced_at": self.introduced_at.isoformat(),
            "session_ref": str(self.session_ref) if self.session_ref else None,
            "amended_intent": self.amended_intent,
        }


@dataclass
class MotionIntroductionRequest:
    """Request to introduce a motion."""

    introduced_by: str  # King's Archon ID
    title: str
    intent: str
    rationale: str
    session_ref: UUID | None = None


@dataclass
class MotionIntroductionResult:
    """Result of attempting to introduce a motion."""

    success: bool
    motion: Motion | None = None
    validation_result: IntentValidationResult | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "motion": self.motion.to_dict() if self.motion else None,
            "validation_result": (
                self.validation_result.to_dict() if self.validation_result else None
            ),
            "error": self.error,
        }


class RankViolationError(Exception):
    """Raised when an Archon attempts an action outside their rank authority."""

    def __init__(
        self,
        archon_id: str,
        action: str,
        reason: str,
        prd_reference: str = "FR-GOV-6",
    ):
        self.archon_id = archon_id
        self.action = action
        self.reason = reason
        self.prd_reference = prd_reference
        super().__init__(f"Rank violation by {archon_id}: {reason} ({prd_reference})")


class KingServiceProtocol(ABC):
    """Abstract protocol for King-rank legislative functions.

    Per Government PRD:
    - FR-GOV-5: Kings may introduce motions and define WHAT (intent only)
    - FR-GOV-6: Kings may NOT define tasks, timelines, tools, execution methods,
                supervise execution, or judge outcomes

    This protocol explicitly EXCLUDES:
    - Any execution-defining methods
    - Task decomposition
    - Timeline specification
    - Resource allocation
    - Supervision methods
    - Judgment methods
    """

    @abstractmethod
    async def introduce_motion(
        self,
        request: MotionIntroductionRequest,
    ) -> MotionIntroductionResult:
        """Introduce a new motion defining WHAT (intent only).

        This is the primary legislative function of King-rank Archons.
        The motion will be validated to ensure it contains only intent,
        not execution details.

        Args:
            request: Motion introduction request with intent

        Returns:
            MotionIntroductionResult with success/failure and motion

        Raises:
            RankViolationError: If the Archon is not King-rank

        Note:
            The motion is NOT ratified by this method. It must go through
            Conclave deliberation per FR-GOV-7.
        """
        ...

    @abstractmethod
    async def validate_intent_only(
        self,
        motion_text: str,
    ) -> IntentValidationResult:
        """Validate that motion text contains only WHAT, not HOW.

        Per FR-GOV-6, Kings may NOT define:
        - Tasks
        - Timelines
        - Tools
        - Execution methods
        - Supervision
        - Outcomes/judgment

        Args:
            motion_text: The intent text to validate

        Returns:
            IntentValidationResult with violations if any execution details found
        """
        ...

    @abstractmethod
    async def get_motion(self, motion_id: UUID) -> Motion | None:
        """Retrieve a motion by ID.

        Args:
            motion_id: UUID of the motion

        Returns:
            Motion if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_motions_by_status(
        self,
        status: MotionStatus,
    ) -> list[Motion]:
        """Get all motions with a specific status.

        Args:
            status: The status to filter by

        Returns:
            List of motions with that status
        """
        ...

    @abstractmethod
    async def get_motions_by_king(
        self,
        king_archon_id: str,
    ) -> list[Motion]:
        """Get all motions introduced by a specific King.

        Args:
            king_archon_id: The Archon ID of the King

        Returns:
            List of motions introduced by that King
        """
        ...

    # =========================================================================
    # EXPLICITLY EXCLUDED METHODS
    # These methods are NOT part of the King Service per FR-GOV-6
    # =========================================================================

    # def define_tasks(self) -> None:  # PROHIBITED
    # def set_timeline(self) -> None:  # PROHIBITED
    # def specify_tools(self) -> None:  # PROHIBITED
    # def allocate_resources(self) -> None:  # PROHIBITED
    # def supervise_execution(self) -> None:  # PROHIBITED
    # def judge_outcome(self) -> None:  # PROHIBITED
    # def ratify_motion(self) -> None:  # PROHIBITED (Conclave function)
