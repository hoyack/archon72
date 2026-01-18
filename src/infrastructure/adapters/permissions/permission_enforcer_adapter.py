"""Permission Enforcer Adapter implementation.

This adapter loads the rank permission matrix from YAML configuration and
provides runtime enforcement of rank-based permissions.

Per Government PRD §10: Machine-enforceable permissions based on rank.
Per Government PRD §2.2: Authority derives from rank, not personality or capability.
"""

from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from structlog import get_logger

from src.application.ports.permission_enforcer import (
    GovernanceAction,
    GovernanceBranch,
    PermissionContext,
    PermissionEnforcerProtocol,
    PermissionResult,
    RankViolationError,
    ViolationDetail,
    ViolationSeverity,
)

logger = get_logger(__name__)


class PermissionEnforcerAdapter(PermissionEnforcerProtocol):
    """Adapter that enforces rank-based permissions from YAML configuration.

    This implementation:
    1. Loads rank permissions from config/permissions/rank-matrix.yaml
    2. Validates actions against allowed/prohibited actions per rank
    3. Tracks actions for branch conflict detection (separation of powers)
    4. Returns detailed PermissionResult with violation information
    5. Logs all permission checks for auditability

    Per Government PRD NFR-GOV-1: Violations must be visible.
    Per Government PRD NFR-GOV-3: All decisions must have record.
    """

    def __init__(
        self,
        config_path: Path | str | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the permission enforcer.

        Args:
            config_path: Path to rank-matrix.yaml. If None, uses default location.
            verbose: Enable verbose logging.
        """
        self._verbose = verbose
        self._config_path = Path(config_path) if config_path else self._default_path()
        self._config: dict[str, Any] = {}
        self._ranks: dict[str, dict[str, Any]] = {}
        self._actions: dict[str, dict[str, Any]] = {}
        self._branch_conflicts: list[dict[str, Any]] = []

        # Track Archon actions on targets for branch conflict detection
        # Structure: {target_id: {archon_id: [branches_acted_in]}}
        self._action_history: dict[str, dict[UUID, list[GovernanceBranch]]] = (
            defaultdict(lambda: defaultdict(list))
        )

        self._load_config()

        logger.info(
            "permission_enforcer_initialized",
            config_path=str(self._config_path),
            ranks_loaded=len(self._ranks),
            actions_defined=len(self._actions),
        )

    def _default_path(self) -> Path:
        """Get the default configuration path."""
        # Assumes running from project root
        return Path("config/permissions/rank-matrix.yaml")

    def _load_config(self) -> None:
        """Load the rank permission matrix from YAML."""
        if not self._config_path.exists():
            raise FileNotFoundError(f"Permission matrix not found: {self._config_path}")

        with open(self._config_path, encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        self._ranks = self._config.get("ranks", {})
        self._actions = self._config.get("actions", {})
        self._branch_conflicts = self._config.get("branch_conflicts", [])

        if self._verbose:
            logger.debug(
                "permission_config_loaded",
                ranks=list(self._ranks.keys()),
                branch_conflicts=len(self._branch_conflicts),
            )

    def check_permission(self, context: PermissionContext) -> PermissionResult:
        """Check if an Archon is permitted to perform an action.

        Per Government PRD §10: Validate action against rank permissions.
        Per rank-matrix.yaml v2.0: Permissions keyed on original_rank (constitutional role),
        NOT aegis_rank (organizational hierarchy) to enable proper separation of powers.

        Args:
            context: Full context for the permission check

        Returns:
            PermissionResult with allowed status and any violation details
        """
        # Key change v2.0: Use original_rank (constitutional role) for lookup
        # This enables proper separation of powers since Prince/Earl/Knight
        # share the same aegis_rank but have different constitutional permissions
        rank_config = self._ranks.get(context.original_rank)

        if not rank_config:
            # Unknown rank - deny by default with critical violation
            return PermissionResult(
                allowed=False,
                archon_id=context.archon_id,
                archon_name=context.archon_name,
                action=context.action,
                violation_reason=f"Unknown constitutional rank: {context.original_rank}",
                violation_details=[
                    ViolationDetail(
                        violated_constraint="Constitutional rank must be defined in permission matrix",
                        severity=ViolationSeverity.CRITICAL,
                        prd_reference="PRD §10",
                        requires_witnessing=True,
                        requires_conclave_review=True,
                    )
                ],
            )

        allowed_actions = self._parse_actions(rank_config.get("allowed_actions", []))
        prohibited_actions = self._parse_actions(
            rank_config.get("prohibited_actions", [])
        )
        constraints = rank_config.get("constraints", [])

        # Check if action is allowed
        if context.action in prohibited_actions:
            # Explicitly prohibited
            violation_details = [
                ViolationDetail(
                    violated_constraint=f"Action '{context.action.value}' is prohibited for {context.original_rank} rank",
                    severity=ViolationSeverity.MAJOR,
                    prd_reference=self._get_prd_reference(
                        context.original_rank, context.action
                    ),
                    requires_witnessing=True,
                    requires_conclave_review=self._action_requires_review(
                        context.action
                    ),
                )
            ]

            logger.warning(
                "permission_denied_prohibited",
                archon_id=str(context.archon_id),
                archon_name=context.archon_name,
                rank=context.aegis_rank,
                action=context.action.value,
            )

            return PermissionResult(
                allowed=False,
                archon_id=context.archon_id,
                archon_name=context.archon_name,
                action=context.action,
                violation_reason=f"{context.original_rank} rank is prohibited from '{context.action.value}'",
                violation_details=violation_details,
                matched_constraints=constraints,
            )

        if context.action not in allowed_actions:
            # Not explicitly allowed (implicit denial)
            violation_details = [
                ViolationDetail(
                    violated_constraint=f"Action '{context.action.value}' is not allowed for {context.original_rank} rank",
                    severity=ViolationSeverity.MAJOR,
                    prd_reference=self._get_prd_reference(
                        context.original_rank, context.action
                    ),
                    requires_witnessing=True,
                    requires_conclave_review=False,
                )
            ]

            logger.warning(
                "permission_denied_not_allowed",
                archon_id=str(context.archon_id),
                archon_name=context.archon_name,
                rank=context.aegis_rank,
                action=context.action.value,
            )

            return PermissionResult(
                allowed=False,
                archon_id=context.archon_id,
                archon_name=context.archon_name,
                action=context.action,
                violation_reason=f"{context.original_rank} rank does not have permission for '{context.action.value}'",
                violation_details=violation_details,
                matched_constraints=constraints,
            )

        # Check for branch conflicts if target_id is provided
        if context.target_id:
            branch = self.get_branch_for_rank(context.original_rank)
            if branch:
                has_conflict, conflict_reason = self.check_branch_conflict(
                    context.archon_id,
                    context.target_id,
                    branch,
                )
                if has_conflict:
                    return PermissionResult(
                        allowed=False,
                        archon_id=context.archon_id,
                        archon_name=context.archon_name,
                        action=context.action,
                        violation_reason=conflict_reason,
                        violation_details=[
                            ViolationDetail(
                                violated_constraint="Separation of powers violation",
                                severity=ViolationSeverity.CRITICAL,
                                prd_reference="PRD §2.1",
                                requires_witnessing=True,
                                requires_conclave_review=True,
                            )
                        ],
                    )

        # Permission granted
        if self._verbose:
            logger.debug(
                "permission_granted",
                archon_id=str(context.archon_id),
                archon_name=context.archon_name,
                rank=context.aegis_rank,
                action=context.action.value,
            )

        return PermissionResult(
            allowed=True,
            archon_id=context.archon_id,
            archon_name=context.archon_name,
            action=context.action,
            matched_constraints=constraints,
        )

    def enforce_permission(self, context: PermissionContext) -> PermissionResult:
        """Check permission and raise if not allowed.

        Args:
            context: Full context for the permission check

        Returns:
            PermissionResult if allowed

        Raises:
            RankViolationError: If the action is not permitted
        """
        result = self.check_permission(context)

        if not result.allowed:
            raise RankViolationError(
                archon_id=context.archon_id,
                archon_name=context.archon_name,
                action=context.action,
                reason=result.violation_reason or "Permission denied",
                details=result.violation_details,
            )

        return result

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
        # Get existing branches this Archon has acted in for this target
        existing_branches = self._action_history[target_id].get(archon_id, [])

        if not existing_branches:
            return False, None

        # Check each branch conflict rule
        for conflict_rule in self._branch_conflicts:
            rule_branches = conflict_rule.get("branches", [])
            if proposed_branch.value in rule_branches:
                # Check if Archon has acted in other branches of this conflict set
                for branch in existing_branches:
                    if branch.value in rule_branches and branch != proposed_branch:
                        return True, conflict_rule.get(
                            "rule", "Branch conflict detected"
                        )

        return False, None

    def get_allowed_actions(self, original_rank: str) -> list[GovernanceAction]:
        """Get the list of allowed actions for a constitutional rank.

        Args:
            original_rank: Constitutional rank (King, President, Duke, etc.)
        """
        rank_config = self._ranks.get(original_rank, {})
        return self._parse_actions(rank_config.get("allowed_actions", []))

    def get_prohibited_actions(self, original_rank: str) -> list[GovernanceAction]:
        """Get the list of prohibited actions for a constitutional rank.

        Args:
            original_rank: Constitutional rank (King, President, Duke, etc.)
        """
        rank_config = self._ranks.get(original_rank, {})
        return self._parse_actions(rank_config.get("prohibited_actions", []))

    def get_constraints(self, original_rank: str) -> list[str]:
        """Get the constraints for a constitutional rank.

        Args:
            original_rank: Constitutional rank (King, President, Duke, etc.)
        """
        rank_config = self._ranks.get(original_rank, {})
        return rank_config.get("constraints", [])

    def get_branch_for_rank(self, original_rank: str) -> GovernanceBranch | None:
        """Get the governance branch for a constitutional rank.

        Args:
            original_rank: Constitutional rank (King, President, Duke, etc.)
        """
        rank_config = self._ranks.get(original_rank, {})
        branch_str = rank_config.get("branch")
        if branch_str:
            try:
                return GovernanceBranch(branch_str)
            except ValueError:
                return None
        return None

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
        if branch not in self._action_history[target_id][archon_id]:
            self._action_history[target_id][archon_id].append(branch)

            logger.info(
                "action_registered",
                archon_id=str(archon_id),
                target_id=target_id,
                branch=branch.value,
            )

    def _parse_actions(self, action_strings: list[str]) -> list[GovernanceAction]:
        """Parse action strings into GovernanceAction enums."""
        actions = []
        for action_str in action_strings:
            try:
                actions.append(GovernanceAction(action_str))
            except ValueError:
                logger.warning("unknown_action_in_config", action=action_str)
        return actions

    def _get_prd_reference(self, original_rank: str, action: GovernanceAction) -> str:
        """Get the PRD reference for a rank/action combination.

        Args:
            original_rank: Constitutional rank (King, President, Duke, etc.)
            action: The governance action attempted
        """
        # Map specific violations to PRD references using original_rank
        references = {
            # Kings (Legislative) - FR-GOV-6: Cannot define HOW
            ("King", GovernanceAction.DEFINE_EXECUTION): "FR-GOV-6",
            ("King", GovernanceAction.EXECUTE): "FR-GOV-6",
            ("King", GovernanceAction.JUDGE): "FR-GOV-6",
            # Dukes/Earls (Administrative) - FR-GOV-9/12: Execute only
            ("Duke", GovernanceAction.INTRODUCE_MOTION): "FR-GOV-9",
            ("Earl", GovernanceAction.INTRODUCE_MOTION): "FR-GOV-12",
            # Princes (Judicial) - FR-GOV-16: Judge only
            ("Prince", GovernanceAction.INTRODUCE_MOTION): "FR-GOV-16",
            ("Prince", GovernanceAction.DEFINE_EXECUTION): "FR-GOV-16",
            # Knights (Witness) - FR-GOV-21: Cannot participate
            ("Knight", GovernanceAction.INTRODUCE_MOTION): "FR-GOV-21",
            ("Knight", GovernanceAction.DELIBERATE): "FR-GOV-21",
            ("Knight", GovernanceAction.JUDGE): "FR-GOV-21",
        }
        return references.get((original_rank, action), "PRD §10")

    def _action_requires_review(self, action: GovernanceAction) -> bool:
        """Check if a violation of this action requires Conclave review."""
        # Critical actions that require review if violated
        critical_actions = {
            GovernanceAction.INTRODUCE_MOTION,
            GovernanceAction.DEFINE_EXECUTION,
            GovernanceAction.JUDGE,
        }
        return action in critical_actions


def create_permission_enforcer(
    config_path: Path | str | None = None,
    verbose: bool = False,
) -> PermissionEnforcerProtocol:
    """Factory function to create a PermissionEnforcerProtocol instance.

    Args:
        config_path: Optional path to rank-matrix.yaml
        verbose: Enable verbose logging

    Returns:
        Configured PermissionEnforcerProtocol instance
    """
    return PermissionEnforcerAdapter(config_path=config_path, verbose=verbose)
