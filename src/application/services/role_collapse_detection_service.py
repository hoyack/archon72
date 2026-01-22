"""Role Collapse Detection Service (Epic 8, Story 8.4).

This service detects and prevents role collapse violations where an Archon
attempts to perform multiple branch functions on the same motion.

Per Government PRD FR-GOV-23: No role may be collapsed.
Per PRD §2.1: No entity may define intent, execute it, AND judge it.

Per CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
Per CT-12: Witnessing creates accountability → All collapse attempts witnessed

Per HARDENING-2: Branch conflict rules loaded from YAML - no inline definitions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.branch_action_tracker import (
    BranchActionTrackerProtocol,
    GovernanceAction,
    GovernanceBranch,
    RecordActionRequest,
    get_branch_for_action,
)
from src.application.ports.branch_conflict_rules_loader import (
    BranchConflictRule,
    BranchConflictRulesLoaderProtocol,
    BranchConflictSeverity,
)

logger = get_logger(__name__)


# =============================================================================
# Domain Models for Role Collapse Detection (AC2, AC6)
# =============================================================================


class RoleCollapseSeverity(Enum):
    """Severity levels for role collapse violations.

    Per AC6:
    - CRITICAL for legislative↔executive or executive↔judicial collapse
    - MAJOR for advisory↔judicial collapse
    """

    CRITICAL = "critical"  # Constitutional violation requiring Conclave review
    MAJOR = "major"  # Significant violation requiring Conclave review

    @classmethod
    def from_string(cls, value: str) -> "RoleCollapseSeverity":
        """Convert string severity to enum.

        Args:
            value: String severity value ('critical', 'major')

        Returns:
            RoleCollapseSeverity enum value
        """
        if value == BranchConflictSeverity.CRITICAL:
            return cls.CRITICAL
        elif value == BranchConflictSeverity.MAJOR:
            return cls.MAJOR
        # Default to MAJOR for unknown severities (e.g., 'info')
        return cls.MAJOR


@dataclass(frozen=True)
class CollapsedRoles:
    """Tuple of roles that were collapsed.

    Per AC1: Identifies the roles being collapsed.
    """

    existing_branch: GovernanceBranch
    attempted_branch: GovernanceBranch
    existing_action: GovernanceAction | None = None
    attempted_action: GovernanceAction | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "existing_branch": self.existing_branch.value,
            "attempted_branch": self.attempted_branch.value,
            "existing_action": self.existing_action.value
            if self.existing_action
            else None,
            "attempted_action": self.attempted_action.value
            if self.attempted_action
            else None,
        }


@dataclass(frozen=True)
class RoleCollapseViolation:
    """A violation where an Archon attempted to perform multiple branch functions.

    Per PRD §2.1: No entity may define intent, execute it, AND judge it.
    Per AC1: Includes identification of Archon, roles, and motion.
    Per AC6: All role collapse violations require Conclave review.

    Note: Per HARDENING-2, violations are created by the service's _create_violation()
    method which has access to the YAML-loaded rules. Direct instantiation is supported
    for testing and serialization.
    """

    violation_id: UUID
    archon_id: str
    motion_id: UUID
    existing_branches: tuple[GovernanceBranch, ...]
    attempted_branch: GovernanceBranch
    collapsed_roles: tuple[CollapsedRoles, ...]
    conflict_rule: str
    prd_reference: str
    severity: RoleCollapseSeverity
    detected_at: datetime
    rejected: bool = True
    escalated_to_conclave: bool = True  # Per AC6: All require Conclave review

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization and audit logging."""
        return {
            "violation_id": str(self.violation_id),
            "violation_type": "ROLE_COLLAPSE_VIOLATION",
            "archon_id": self.archon_id,
            "motion_id": str(self.motion_id),
            "existing_branches": [b.value for b in self.existing_branches],
            "attempted_branch": self.attempted_branch.value,
            "collapsed_roles": [cr.to_dict() for cr in self.collapsed_roles],
            "conflict_rule": self.conflict_rule,
            "prd_reference": self.prd_reference,
            "severity": self.severity.value,
            "detected_at": self.detected_at.isoformat(),
            "rejected": self.rejected,
            "escalated_to_conclave": self.escalated_to_conclave,
        }


@dataclass(frozen=True)
class RoleCollapseAuditEntry:
    """Audit trail entry for role collapse attempts.

    Per CT-12: All collapse attempts must be witnessed.
    """

    audit_id: UUID
    violation: RoleCollapseViolation
    recorded_at: datetime
    witness_statement_id: UUID | None = None

    @classmethod
    def create(
        cls,
        violation: RoleCollapseViolation,
        witness_statement_id: UUID | None = None,
    ) -> "RoleCollapseAuditEntry":
        """Create a new audit entry.

        Args:
            violation: The role collapse violation
            witness_statement_id: Optional Knight witness reference

        Returns:
            New immutable audit entry
        """
        return cls(
            audit_id=uuid4(),
            violation=violation,
            recorded_at=datetime.now(timezone.utc),
            witness_statement_id=witness_statement_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "audit_id": str(self.audit_id),
            "violation": self.violation.to_dict(),
            "recorded_at": self.recorded_at.isoformat(),
            "witness_statement_id": str(self.witness_statement_id)
            if self.witness_statement_id
            else None,
        }


class RoleCollapseError(Exception):
    """Raised when role collapse is attempted.

    Per FR-GOV-23: No role may be collapsed.
    Per CT-11: Silent failure destroys legitimacy → explicit error.
    """

    def __init__(self, violation: RoleCollapseViolation) -> None:
        self.violation = violation
        self.error_code = "ROLE_COLLAPSE_VIOLATION"
        super().__init__(
            f"Role collapse violation: Archon {violation.archon_id} attempted "
            f"{violation.attempted_branch.value} branch on motion {violation.motion_id} "
            f"after acting in {', '.join(b.value for b in violation.existing_branches)}. "
            f"Rule: {violation.conflict_rule}"
        )

    def to_error_response(self) -> dict[str, Any]:
        """Generate HTTP error response format."""
        return {
            "error_code": self.error_code,
            "prd_reference": self.violation.prd_reference,
            "message": str(self),
            "archon_id": self.violation.archon_id,
            "motion_id": str(self.violation.motion_id),
            "existing_branches": [b.value for b in self.violation.existing_branches],
            "attempted_branch": self.violation.attempted_branch.value,
            "conflict_rule": self.violation.conflict_rule,
            "severity": self.violation.severity.value,
            "requires_conclave_review": self.violation.escalated_to_conclave,
        }


# =============================================================================
# Detection Results
# =============================================================================


@dataclass(frozen=True)
class CollapseCheckResult:
    """Result of checking for role collapse.

    Per AC1: Detection includes Archon, roles, and motion.
    """

    has_collapse: bool
    archon_id: str
    motion_id: UUID
    proposed_branch: GovernanceBranch
    violation: RoleCollapseViolation | None = None
    existing_branches: tuple[GovernanceBranch, ...] = field(default_factory=tuple)
    message: str | None = None

    @classmethod
    def no_collapse(
        cls,
        archon_id: str,
        motion_id: UUID,
        proposed_branch: GovernanceBranch,
        existing_branches: list[GovernanceBranch] | None = None,
    ) -> "CollapseCheckResult":
        """Create a result indicating no collapse detected.

        Args:
            archon_id: The Archon
            motion_id: The motion
            proposed_branch: The proposed branch
            existing_branches: Existing branches (if any)

        Returns:
            CollapseCheckResult with no violation
        """
        return cls(
            has_collapse=False,
            archon_id=archon_id,
            motion_id=motion_id,
            proposed_branch=proposed_branch,
            existing_branches=tuple(existing_branches or []),
            message="No role collapse detected",
        )

    @classmethod
    def collapse_detected(
        cls,
        archon_id: str,
        motion_id: UUID,
        proposed_branch: GovernanceBranch,
        violation: RoleCollapseViolation,
    ) -> "CollapseCheckResult":
        """Create a result indicating collapse was detected.

        Args:
            archon_id: The Archon
            motion_id: The motion
            proposed_branch: The proposed branch
            violation: The violation details

        Returns:
            CollapseCheckResult with violation
        """
        return cls(
            has_collapse=True,
            archon_id=archon_id,
            motion_id=motion_id,
            proposed_branch=proposed_branch,
            violation=violation,
            existing_branches=violation.existing_branches,
            message=f"Role collapse: {violation.conflict_rule}",
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "has_collapse": self.has_collapse,
            "archon_id": self.archon_id,
            "motion_id": str(self.motion_id),
            "proposed_branch": self.proposed_branch.value,
            "existing_branches": [b.value for b in self.existing_branches],
            "message": self.message,
        }
        if self.violation:
            result["violation"] = self.violation.to_dict()
        return result


# =============================================================================
# Service Implementation
# =============================================================================


class RoleCollapseDetectionService:
    """Service for detecting role collapse violations.

    Per FR-GOV-23: No role may be collapsed.
    Per PRD §2.1: No entity may define intent, execute it, AND judge it.

    This service:
    1. Detects when an Archon attempts multiple branch functions on same motion
    2. Creates detailed violation records
    3. Provides audit trail for witnessed violations
    4. Integrates with branch action tracker for state management

    Per HARDENING-2: Rules loaded from YAML via BranchConflictRulesLoaderProtocol.
    """

    def __init__(
        self,
        tracker: BranchActionTrackerProtocol,
        rules_loader: BranchConflictRulesLoaderProtocol,
    ) -> None:
        """Initialize the role collapse detection service.

        Per HARDENING-2 AC4: Rules loaded from YAML at runtime via loader.

        Args:
            tracker: Branch action tracker for querying/recording actions
            rules_loader: Loader for branch conflict rules
        """
        self._tracker = tracker
        self._violations: list[RoleCollapseViolation] = []
        self._audit_entries: list[RoleCollapseAuditEntry] = []

        # Per HARDENING-2 AC4: Load rules at runtime from injected loader
        self._rules_loader = rules_loader
        self._rules = rules_loader.load_rules()

        logger.info(
            "role_collapse_detection_service_initialized",
            conflict_rules=len(self._rules),
        )

    def _find_conflict_rule(
        self,
        existing_branch: GovernanceBranch,
        proposed_branch: GovernanceBranch,
    ) -> BranchConflictRule | None:
        """Find the conflict rule that applies to two branches.

        Args:
            existing_branch: Branch already acted in
            proposed_branch: Branch being proposed

        Returns:
            The applicable conflict rule, or None if no conflict
        """
        for rule in self._rules:
            if rule.applies_to(existing_branch.value, proposed_branch.value):
                return rule
        return None

    def _create_violation(
        self,
        archon_id: str,
        motion_id: UUID,
        existing_branches: list[GovernanceBranch],
        attempted_branch: GovernanceBranch,
        conflict_rule: BranchConflictRule,
        attempted_action: GovernanceAction | None = None,
    ) -> RoleCollapseViolation:
        """Create a RoleCollapseViolation from the new BranchConflictRule format.

        Per HARDENING-2: Adapts YAML-loaded rules to violation domain model.

        Args:
            archon_id: The Archon attempting collapse
            motion_id: The motion affected
            existing_branches: Branches already acted in
            attempted_branch: Branch being attempted
            conflict_rule: The YAML-loaded rule being violated
            attempted_action: The action being attempted

        Returns:
            New immutable RoleCollapseViolation
        """
        # Build collapsed roles for each conflicting existing branch
        collapsed = []
        for existing in existing_branches:
            if self._find_conflict_rule(existing, attempted_branch):
                collapsed.append(
                    CollapsedRoles(
                        existing_branch=existing,
                        attempted_branch=attempted_branch,
                        attempted_action=attempted_action,
                    )
                )

        # Convert string severity to enum
        severity = RoleCollapseSeverity.from_string(conflict_rule.severity)

        return RoleCollapseViolation(
            violation_id=uuid4(),
            archon_id=archon_id,
            motion_id=motion_id,
            existing_branches=tuple(existing_branches),
            attempted_branch=attempted_branch,
            collapsed_roles=tuple(collapsed),
            conflict_rule=conflict_rule.rule,
            prd_reference=conflict_rule.prd_ref,
            severity=severity,
            detected_at=datetime.now(timezone.utc),
        )

    async def detect_collapse(
        self,
        archon_id: str,
        motion_id: UUID,
        proposed_branch: GovernanceBranch,
        proposed_action: GovernanceAction | None = None,
    ) -> CollapseCheckResult:
        """Detect if an Archon would collapse roles.

        Per AC1: Detection of role collapse
        Per AC4: PRD §2.1 enforcement
        Per AC5: Branch conflict matrix integration

        Args:
            archon_id: The Archon attempting the action
            motion_id: The motion being acted upon
            proposed_branch: The branch of the proposed action
            proposed_action: Optional specific action being proposed

        Returns:
            CollapseCheckResult with detection result
        """
        # Get branches this Archon has already acted in for this motion
        existing_branches = await self._tracker.get_archon_branches(
            archon_id, motion_id
        )

        if not existing_branches:
            logger.debug(
                "no_existing_branches",
                archon_id=archon_id,
                motion_id=str(motion_id),
                proposed_branch=proposed_branch.value,
            )
            return CollapseCheckResult.no_collapse(
                archon_id=archon_id,
                motion_id=motion_id,
                proposed_branch=proposed_branch,
            )

        # Check each conflict rule
        for existing in existing_branches:
            # Skip if same branch (repeated actions in same branch are OK)
            if existing == proposed_branch:
                continue

            # Check if there's a conflict rule (using instance method)
            conflict_rule = self._find_conflict_rule(existing, proposed_branch)
            if conflict_rule:
                # Collapse detected!
                violation = self._create_violation(
                    archon_id=archon_id,
                    motion_id=motion_id,
                    existing_branches=existing_branches,
                    attempted_branch=proposed_branch,
                    conflict_rule=conflict_rule,
                    attempted_action=proposed_action,
                )

                # Store the violation
                self._violations.append(violation)

                logger.warning(
                    "role_collapse_detected",
                    archon_id=archon_id,
                    motion_id=str(motion_id),
                    existing_branch=existing.value,
                    proposed_branch=proposed_branch.value,
                    rule=conflict_rule.rule,
                    severity=conflict_rule.severity,
                )

                return CollapseCheckResult.collapse_detected(
                    archon_id=archon_id,
                    motion_id=motion_id,
                    proposed_branch=proposed_branch,
                    violation=violation,
                )

        # No collapse detected
        logger.debug(
            "no_collapse_detected",
            archon_id=archon_id,
            motion_id=str(motion_id),
            proposed_branch=proposed_branch.value,
            existing_branches=[b.value for b in existing_branches],
        )
        return CollapseCheckResult.no_collapse(
            archon_id=archon_id,
            motion_id=motion_id,
            proposed_branch=proposed_branch,
            existing_branches=existing_branches,
        )

    async def detect_collapse_for_action(
        self,
        archon_id: str,
        motion_id: UUID,
        proposed_action: GovernanceAction,
    ) -> CollapseCheckResult:
        """Detect if an action would cause role collapse.

        Convenience method that derives branch from action.

        Args:
            archon_id: The Archon attempting the action
            motion_id: The motion being acted upon
            proposed_action: The action being proposed

        Returns:
            CollapseCheckResult with detection result
        """
        proposed_branch = get_branch_for_action(proposed_action)
        return await self.detect_collapse(
            archon_id=archon_id,
            motion_id=motion_id,
            proposed_branch=proposed_branch,
            proposed_action=proposed_action,
        )

    async def enforce_no_collapse(
        self,
        archon_id: str,
        motion_id: UUID,
        proposed_branch: GovernanceBranch,
        proposed_action: GovernanceAction | None = None,
    ) -> CollapseCheckResult:
        """Check for collapse and raise if detected.

        Per CT-11: Silent failure destroys legitimacy → raise on violation.

        Args:
            archon_id: The Archon attempting the action
            motion_id: The motion being acted upon
            proposed_branch: The branch of the proposed action
            proposed_action: Optional specific action being proposed

        Returns:
            CollapseCheckResult if no collapse

        Raises:
            RoleCollapseError: If role collapse is detected
        """
        result = await self.detect_collapse(
            archon_id=archon_id,
            motion_id=motion_id,
            proposed_branch=proposed_branch,
            proposed_action=proposed_action,
        )

        if result.has_collapse and result.violation:
            raise RoleCollapseError(result.violation)

        return result

    async def record_action_if_allowed(
        self,
        archon_id: str,
        motion_id: UUID,
        action: GovernanceAction,
    ) -> CollapseCheckResult:
        """Check for collapse and record action if allowed.

        This is the primary method for use in the flow - it:
        1. Checks for role collapse
        2. If no collapse, records the action
        3. Returns the result

        Args:
            archon_id: The Archon attempting the action
            motion_id: The motion being acted upon
            action: The action being attempted

        Returns:
            CollapseCheckResult with result

        Raises:
            RoleCollapseError: If role collapse is detected
        """
        branch = get_branch_for_action(action)

        # First check for collapse
        result = await self.enforce_no_collapse(
            archon_id=archon_id,
            motion_id=motion_id,
            proposed_branch=branch,
            proposed_action=action,
        )

        # If we get here, no collapse - record the action
        await self._tracker.record_branch_action(
            RecordActionRequest(
                archon_id=archon_id,
                motion_id=motion_id,
                action_type=action,
                branch=branch,
            )
        )

        logger.info(
            "action_recorded_after_collapse_check",
            archon_id=archon_id,
            motion_id=str(motion_id),
            action=action.value,
            branch=branch.value,
        )

        return result

    def record_audit_entry(
        self,
        violation: RoleCollapseViolation,
        witness_statement_id: UUID | None = None,
    ) -> RoleCollapseAuditEntry:
        """Record an audit entry for a violation.

        Per CT-12: All collapse attempts must be witnessed.

        Args:
            violation: The violation to audit
            witness_statement_id: Optional Knight witness reference

        Returns:
            The audit entry
        """
        entry = RoleCollapseAuditEntry.create(
            violation=violation,
            witness_statement_id=witness_statement_id,
        )
        self._audit_entries.append(entry)

        logger.info(
            "role_collapse_audit_recorded",
            audit_id=str(entry.audit_id),
            violation_id=str(violation.violation_id),
            archon_id=violation.archon_id,
            motion_id=str(violation.motion_id),
            witnessed=witness_statement_id is not None,
        )

        return entry

    def get_violations(
        self,
        motion_id: UUID | None = None,
        archon_id: str | None = None,
    ) -> list[RoleCollapseViolation]:
        """Get recorded violations with optional filtering.

        Args:
            motion_id: Optional filter by motion
            archon_id: Optional filter by Archon

        Returns:
            List of matching violations
        """
        violations = self._violations

        if motion_id:
            violations = [v for v in violations if v.motion_id == motion_id]

        if archon_id:
            violations = [v for v in violations if v.archon_id == archon_id]

        return violations

    def get_audit_entries(
        self,
        motion_id: UUID | None = None,
    ) -> list[RoleCollapseAuditEntry]:
        """Get audit entries with optional filtering.

        Args:
            motion_id: Optional filter by motion

        Returns:
            List of matching audit entries
        """
        if motion_id:
            return [
                e for e in self._audit_entries if e.violation.motion_id == motion_id
            ]
        return list(self._audit_entries)

    def clear_violations(self) -> None:
        """Clear all recorded violations and audit entries.

        For testing purposes.
        """
        self._violations.clear()
        self._audit_entries.clear()
