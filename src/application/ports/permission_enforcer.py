"""Port interface for permission enforcement.

This module defines the abstract interface for checking rank-based permissions,
ensuring no entity exceeds their jurisdictional authority per the Government PRD.

Per Government PRD §2.2: "Rank Implies Jurisdiction: Authority derives from rank,
not personality or capability."

Per Government PRD §10: "Machine-enforceable permissions based on rank."
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


class GovernanceAction(Enum):
    """Actions that can be performed in the governance system.

    Per Government PRD §4:
    - Legislative: introduce_motion
    - Deliberative: deliberate, ratify
    - Executive: define_execution
    - Administrative: execute
    - Judicial: judge
    - Advisory: advise
    - Witness: witness
    """

    INTRODUCE_MOTION = "introduce_motion"
    DELIBERATE = "deliberate"
    RATIFY = "ratify"
    DEFINE_EXECUTION = "define_execution"
    EXECUTE = "execute"
    JUDGE = "judge"
    ADVISE = "advise"
    WITNESS = "witness"


class GovernanceBranch(Enum):
    """Branches of governance per Government PRD §3."""

    LEGISLATIVE = "legislative"
    EXECUTIVE = "executive"
    ADMINISTRATIVE = "administrative"
    JUDICIAL = "judicial"
    ADVISORY = "advisory"
    WITNESS = "witness"


class ViolationSeverity(Enum):
    """Severity levels for permission violations."""

    CRITICAL = "critical"  # Constitutional violation requiring immediate halt
    MAJOR = "major"  # Significant violation requiring Conclave review
    MINOR = "minor"  # Procedural violation requiring acknowledgment


@dataclass(frozen=True)
class PermissionContext:
    """Context for permission check requests.

    Contains all information needed to evaluate whether an action is permitted.
    """

    archon_id: UUID
    archon_name: str
    aegis_rank: str
    original_rank: str
    branch: str
    action: GovernanceAction
    target_id: str | None = None  # Motion ID, task ID, etc.
    target_type: str | None = None  # "motion", "task", "finding", etc.
    additional_context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ViolationDetail:
    """Details about a permission violation."""

    violated_constraint: str
    severity: ViolationSeverity
    prd_reference: str  # e.g., "FR-GOV-6", "PRD §4.1"
    requires_witnessing: bool = True
    requires_conclave_review: bool = False


@dataclass(frozen=True)
class RoleCollapseDetail:
    """Details about a role collapse violation.

    Per PRD §2.1: No entity may define intent, execute it, AND judge it.
    Per FR-GOV-23: No role may be collapsed.
    """

    existing_branches: tuple[str, ...]
    attempted_branch: str
    conflict_rule: str
    prd_reference: str
    severity: ViolationSeverity
    requires_conclave_review: bool = True  # Per AC6: All require Conclave review


@dataclass(frozen=True)
class PermissionResult:
    """Result of a permission check.

    Per Government PRD NFR-GOV-1: "Violations must be visible."
    All permission checks must return clear results with reasons.
    """

    allowed: bool
    archon_id: UUID
    archon_name: str
    action: GovernanceAction
    violation_reason: str | None = None
    violation_details: list[ViolationDetail] = field(default_factory=list)
    matched_constraints: list[str] = field(default_factory=list)
    role_collapse_detail: RoleCollapseDetail | None = None  # Per Story 8.4
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_critical_violation(self) -> bool:
        """Check if any violation is critical severity."""
        if any(v.severity == ViolationSeverity.CRITICAL for v in self.violation_details):
            return True
        if self.role_collapse_detail and self.role_collapse_detail.severity == ViolationSeverity.CRITICAL:
            return True
        return False

    @property
    def requires_conclave_review(self) -> bool:
        """Check if any violation requires Conclave review."""
        if any(v.requires_conclave_review for v in self.violation_details):
            return True
        if self.role_collapse_detail and self.role_collapse_detail.requires_conclave_review:
            return True
        return False

    @property
    def is_role_collapse(self) -> bool:
        """Check if this is a role collapse violation."""
        return self.role_collapse_detail is not None


class RankViolationError(Exception):
    """Exception raised when an Archon attempts an action outside their jurisdiction.

    Per Government PRD §2.2: Authority derives from rank.
    This exception ensures violations cannot be silently ignored.
    """

    def __init__(
        self,
        archon_id: UUID,
        archon_name: str,
        action: GovernanceAction,
        reason: str,
        details: list[ViolationDetail] | None = None,
    ) -> None:
        self.archon_id = archon_id
        self.archon_name = archon_name
        self.action = action
        self.reason = reason
        self.details = details or []

        super().__init__(
            f"Rank violation: {archon_name} (ID: {archon_id}) attempted "
            f"'{action.value}' - {reason}"
        )


class BranchConflictError(Exception):
    """Exception raised when separation of powers is violated.

    Per Government PRD §2.1: "No entity may define intent, execute it, AND judge it."
    """

    def __init__(
        self,
        archon_id: UUID,
        archon_name: str,
        branches_involved: list[GovernanceBranch],
        target_id: str,
        reason: str,
    ) -> None:
        self.archon_id = archon_id
        self.archon_name = archon_name
        self.branches_involved = branches_involved
        self.target_id = target_id
        self.reason = reason

        branches_str = ", ".join(b.value for b in branches_involved)
        super().__init__(
            f"Branch conflict: {archon_name} violated separation of powers "
            f"by acting in branches [{branches_str}] on {target_id} - {reason}"
        )


class PermissionEnforcerProtocol(ABC):
    """Abstract protocol for permission enforcement.

    This port defines the interface for checking whether an Archon is permitted
    to perform a governance action based on their rank.

    Per Government PRD §10: Permissions must be machine-enforceable.

    Implementations should:
    1. Load rank permissions from configuration
    2. Validate actions against allowed actions for the rank
    3. Check for branch conflicts (separation of powers)
    4. Return clear PermissionResult with violation details
    5. Trigger witness events for violations

    Example usage:
        enforcer = PermissionEnforcerAdapter(...)
        context = PermissionContext(
            archon_id=king_id,
            archon_name="Paimon",
            aegis_rank="executive_director",
            original_rank="King",
            branch="legislative",
            action=GovernanceAction.DEFINE_EXECUTION,  # Prohibited for Kings
        )
        result = enforcer.check_permission(context)
        if not result.allowed:
            raise RankViolationError(...)
    """

    @abstractmethod
    def check_permission(self, context: PermissionContext) -> PermissionResult:
        """Check if an Archon is permitted to perform an action.

        Args:
            context: Full context for the permission check

        Returns:
            PermissionResult with allowed status and violation details

        Note:
            This method should NOT raise exceptions for violations.
            It returns the result and lets the caller decide how to handle it.
        """
        ...

    @abstractmethod
    def enforce_permission(self, context: PermissionContext) -> PermissionResult:
        """Check permission and raise if not allowed.

        Args:
            context: Full context for the permission check

        Returns:
            PermissionResult if allowed

        Raises:
            RankViolationError: If the action is not permitted
        """
        ...

    @abstractmethod
    def check_branch_conflict(
        self,
        archon_id: UUID,
        target_id: str,
        proposed_branch: GovernanceBranch,
    ) -> tuple[bool, str | None]:
        """Check if an Archon would violate separation of powers.

        Per PRD §2.1: No entity may define intent, execute it, AND judge it.

        Args:
            archon_id: The Archon attempting the action
            target_id: The motion/task being acted upon
            proposed_branch: The branch of the proposed action

        Returns:
            Tuple of (has_conflict: bool, conflict_reason: str | None)
        """
        ...

    @abstractmethod
    def get_allowed_actions(self, aegis_rank: str) -> list[GovernanceAction]:
        """Get the list of allowed actions for a rank.

        Args:
            aegis_rank: The Aegis rank to check (e.g., "executive_director")

        Returns:
            List of allowed GovernanceAction values
        """
        ...

    @abstractmethod
    def get_prohibited_actions(self, aegis_rank: str) -> list[GovernanceAction]:
        """Get the list of prohibited actions for a rank.

        Args:
            aegis_rank: The Aegis rank to check

        Returns:
            List of prohibited GovernanceAction values
        """
        ...

    @abstractmethod
    def get_constraints(self, aegis_rank: str) -> list[str]:
        """Get the constraints for a rank.

        Args:
            aegis_rank: The Aegis rank to check

        Returns:
            List of constraint descriptions
        """
        ...

    @abstractmethod
    def get_branch_for_rank(self, aegis_rank: str) -> GovernanceBranch | None:
        """Get the governance branch for a rank.

        Args:
            aegis_rank: The Aegis rank to check

        Returns:
            The GovernanceBranch for the rank, or None if not found
        """
        ...

    @abstractmethod
    def register_action(
        self,
        archon_id: UUID,
        target_id: str,
        branch: GovernanceBranch,
    ) -> None:
        """Register that an Archon has acted on a target in a branch.

        This is used to track actions for branch conflict detection.

        Args:
            archon_id: The Archon who performed the action
            target_id: The motion/task acted upon
            branch: The branch of the action
        """
        ...
