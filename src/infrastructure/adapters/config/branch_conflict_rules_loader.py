"""Branch Conflict Rules Loader.

This loader is the ONLY way to load BranchConflictRule instances.
Rules are defined in config/permissions/rank-matrix.yaml.

Per HARDENING-2: Configuration lives in YAML, code loads it - no dual-source patterns.
Per PRD §2.1: No entity may define intent, execute it, AND judge it.
Per FR-GOV-23: No role may be collapsed.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml
from structlog import get_logger

logger = get_logger(__name__)


# =============================================================================
# Domain Models (moved here to avoid circular imports)
# =============================================================================


class BranchConflictSeverity:
    """Severity levels for branch conflicts.

    Per PRD §2.1 and FR-GOV-23:
    - CRITICAL: Constitutional violation requiring immediate halt
    - MAJOR: Significant violation requiring Conclave review
    - INFO: Informational (e.g., witness exclusion note)
    """

    CRITICAL = "critical"
    MAJOR = "major"
    INFO = "info"

    @classmethod
    def validate(cls, value: str) -> bool:
        """Check if severity value is valid."""
        return value in (cls.CRITICAL, cls.MAJOR, cls.INFO)


@dataclass(frozen=True)
class BranchConflictRule:
    """A rule defining conflicting branches.

    Per HARDENING-2 AC1: Loaded ONLY from config/permissions/rank-matrix.yaml.
    """

    id: str
    branches: frozenset[str]
    rule: str
    prd_ref: str
    severity: str
    description: str

    def applies_to(self, branch1: str, branch2: str) -> bool:
        """Check if this rule applies to two branches.

        Args:
            branch1: First branch name
            branch2: Second branch name

        Returns:
            True if both branches are in this conflict rule
        """
        return branch1 in self.branches and branch2 in self.branches

    def is_critical(self) -> bool:
        """Check if this is a critical severity rule."""
        return self.severity == BranchConflictSeverity.CRITICAL

    def is_major(self) -> bool:
        """Check if this is a major severity rule."""
        return self.severity == BranchConflictSeverity.MAJOR


# =============================================================================
# Loader Protocol and Errors
# =============================================================================


class ConfigurationError(Exception):
    """Raised when configuration loading fails.

    Per HARDENING-2 AC5: Validates schema on load.
    """

    def __init__(self, source: str, reason: str) -> None:
        self.source = source
        self.reason = reason
        super().__init__(f"Configuration error in {source}: {reason}")


class BranchConflictRulesLoaderProtocol(Protocol):
    """Protocol for loading branch conflict rules.

    Per HARDENING-2 AC4: Services inject this protocol.
    """

    def load_rules(self) -> list[BranchConflictRule]:
        """Load branch conflict rules from configuration.

        Returns:
            List of BranchConflictRule instances

        Raises:
            ConfigurationError: If configuration is invalid
        """
        ...

    def get_rule_by_id(self, rule_id: str) -> BranchConflictRule | None:
        """Get a specific rule by ID.

        Args:
            rule_id: The rule identifier

        Returns:
            The rule, or None if not found
        """
        ...


# =============================================================================
# YAML Loader Implementation
# =============================================================================


class YamlBranchConflictRulesLoader:
    """Loads branch conflict rules from rank-matrix.yaml.

    Per HARDENING-2:
    - AC1: Single source of truth from YAML
    - AC4: Runtime loading (not compile-time constants)
    - AC5: Schema validation with specific error messages

    Example YAML structure:
    ```yaml
    branch_conflicts:
      - id: "legislative_executive"
        branches: ["legislative", "executive"]
        rule: "Same Archon cannot define WHAT and HOW for same motion"
        severity: "critical"
        prd_ref: "PRD §2.1"
        description: |
          Kings introduce motions (WHAT), Presidents translate into execution plans (HOW).
    ```
    """

    REQUIRED_FIELDS = {"id", "branches", "rule", "severity", "prd_ref"}

    def __init__(self, yaml_path: Path | str | None = None) -> None:
        """Initialize the loader with YAML path.

        Args:
            yaml_path: Path to rank-matrix.yaml. Defaults to project config.

        Raises:
            ConfigurationError: If file not found
        """
        if yaml_path is None:
            # Default to project root config
            project_root = Path(__file__).parent.parent.parent.parent.parent
            yaml_path = project_root / "config" / "permissions" / "rank-matrix.yaml"

        self._yaml_path = Path(yaml_path)
        self._rules: list[BranchConflictRule] | None = None
        self._rules_by_id: dict[str, BranchConflictRule] = {}

        logger.info(
            "branch_conflict_rules_loader_initialized",
            yaml_path=str(self._yaml_path),
        )

    def load_rules(self) -> list[BranchConflictRule]:
        """Load and validate branch conflict rules from YAML.

        Per HARDENING-2 AC1, AC4, AC5.

        Returns:
            List of validated BranchConflictRule instances

        Raises:
            ConfigurationError: If file not found, YAML invalid, or schema invalid
        """
        if self._rules is not None:
            return self._rules

        if not self._yaml_path.exists():
            raise ConfigurationError(
                source=str(self._yaml_path),
                reason="File not found",
            )

        try:
            with open(self._yaml_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(
                source=str(self._yaml_path),
                reason=f"YAML parse error: {e}",
            ) from e

        if not config:
            raise ConfigurationError(
                source=str(self._yaml_path),
                reason="Empty configuration file",
            )

        branch_conflicts = config.get("branch_conflicts")
        if not branch_conflicts:
            raise ConfigurationError(
                source=str(self._yaml_path),
                reason="Missing 'branch_conflicts' section",
            )

        if not isinstance(branch_conflicts, list):
            raise ConfigurationError(
                source=str(self._yaml_path),
                reason="'branch_conflicts' must be a list",
            )

        rules: list[BranchConflictRule] = []
        for i, entry in enumerate(branch_conflicts):
            rule = self._validate_and_create_rule(entry, index=i)
            rules.append(rule)
            self._rules_by_id[rule.id] = rule

        self._rules = rules

        logger.info(
            "branch_conflict_rules_loaded",
            rule_count=len(rules),
            critical_count=sum(1 for r in rules if r.is_critical()),
            major_count=sum(1 for r in rules if r.is_major()),
            yaml_path=str(self._yaml_path),
        )

        return rules

    def get_rule_by_id(self, rule_id: str) -> BranchConflictRule | None:
        """Get a specific rule by ID.

        Args:
            rule_id: The rule identifier

        Returns:
            The rule, or None if not found
        """
        if self._rules is None:
            self.load_rules()
        return self._rules_by_id.get(rule_id)

    def _validate_and_create_rule(
        self,
        entry: dict[str, Any],
        index: int,
    ) -> BranchConflictRule:
        """Validate YAML entry and create BranchConflictRule.

        Per HARDENING-2 AC5: Schema validation with specific messages.

        Args:
            entry: YAML dictionary entry
            index: Index in list for error messages

        Returns:
            Validated BranchConflictRule

        Raises:
            ConfigurationError: If validation fails
        """
        if not isinstance(entry, dict):
            raise ConfigurationError(
                source=str(self._yaml_path),
                reason=f"branch_conflicts[{index}]: Expected dict, got {type(entry).__name__}",
            )

        # Check required fields
        missing = self.REQUIRED_FIELDS - set(entry.keys())
        if missing:
            raise ConfigurationError(
                source=str(self._yaml_path),
                reason=f"branch_conflicts[{index}]: Missing required fields: {missing}",
            )

        # Validate branches
        branches = entry.get("branches")
        if not isinstance(branches, list) or len(branches) < 1:
            raise ConfigurationError(
                source=str(self._yaml_path),
                reason=f"branch_conflicts[{index}]: 'branches' must be a non-empty list",
            )

        # Validate severity
        severity = entry.get("severity", "")
        if not BranchConflictSeverity.validate(severity):
            raise ConfigurationError(
                source=str(self._yaml_path),
                reason=f"branch_conflicts[{index}]: Invalid severity '{severity}'. "
                f"Must be one of: critical, major, info",
            )

        # Validate id is unique
        rule_id = entry.get("id", "")
        if rule_id in self._rules_by_id:
            raise ConfigurationError(
                source=str(self._yaml_path),
                reason=f"branch_conflicts[{index}]: Duplicate id '{rule_id}'",
            )

        return BranchConflictRule(
            id=rule_id,
            branches=frozenset(branches),
            rule=entry.get("rule", ""),
            prd_ref=entry.get("prd_ref", ""),
            severity=severity,
            description=entry.get("description", ""),
        )


# =============================================================================
# Factory Function
# =============================================================================


def create_branch_conflict_rules_loader(
    yaml_path: Path | str | None = None,
) -> YamlBranchConflictRulesLoader:
    """Factory function to create a BranchConflictRulesLoader.

    Uses default path if not specified: config/permissions/rank-matrix.yaml

    Args:
        yaml_path: Optional path to YAML file

    Returns:
        Configured loader instance
    """
    return YamlBranchConflictRulesLoader(yaml_path=yaml_path)
