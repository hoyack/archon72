"""Branch conflict rules loader port (HARDENING-2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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
        """Check if this rule applies to two branches."""
        return branch1 in self.branches and branch2 in self.branches

    def is_critical(self) -> bool:
        """Check if this is a critical severity rule."""
        return self.severity == BranchConflictSeverity.CRITICAL

    def is_major(self) -> bool:
        """Check if this is a major severity rule."""
        return self.severity == BranchConflictSeverity.MAJOR


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
        """Load branch conflict rules from configuration."""
        ...

    def get_rule_by_id(self, rule_id: str) -> BranchConflictRule | None:
        """Get a specific rule by ID."""
        ...


__all__ = [
    "BranchConflictRule",
    "BranchConflictRulesLoaderProtocol",
    "BranchConflictSeverity",
    "ConfigurationError",
]
