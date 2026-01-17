"""CoercionPattern domain model for pattern detection.

Story: consent-gov-3.4: Coercion Pattern Detection

Defines the domain models for coercion pattern detection:
- PatternSeverity: How severely to treat pattern matches
- PatternCategory: Categories of coercive patterns
- CoercionPattern: A pattern for detecting coercive language

References:
- AC1: Detection of urgency pressure
- AC2: Detection of guilt induction
- AC3: Detection of false scarcity
- AC4: Detection of engagement-optimization
- AC6: Patterns categorized by severity
- AC7: Pattern matching is deterministic
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class PatternSeverity(Enum):
    """How severely to treat pattern matches.

    TRANSFORM: Auto-fix, content can be sent after transformation
    REJECT: Requires rewrite by Earl, cannot be auto-fixed
    BLOCK: Hard violation, cannot be sent under any circumstances
    """

    TRANSFORM = "transform"
    REJECT = "reject"
    BLOCK = "block"

    @property
    def is_sendable_after_action(self) -> bool:
        """Whether content can be sent after this severity's action."""
        return self == PatternSeverity.TRANSFORM

    @property
    def requires_human_action(self) -> bool:
        """Whether this severity requires human intervention."""
        return self in (PatternSeverity.REJECT, PatternSeverity.BLOCK)


class PatternCategory(Enum):
    """Categories of coercive patterns per AC1-4.

    Each category groups related patterns for:
    - Reporting and analytics
    - Configurable severity per category
    - Pattern library organization
    """

    URGENCY_PRESSURE = "urgency_pressure"  # AC1
    GUILT_INDUCTION = "guilt_induction"  # AC2
    FALSE_SCARCITY = "false_scarcity"  # AC3
    ENGAGEMENT_OPTIMIZATION = "engagement_optimization"  # AC4
    HARD_VIOLATION = "hard_violation"  # Hard violations (BLOCK)

    @property
    def description(self) -> str:
        """Human-readable description of this category."""
        descriptions = {
            PatternCategory.URGENCY_PRESSURE: "Creates artificial time pressure",
            PatternCategory.GUILT_INDUCTION: "Induces guilt or shame",
            PatternCategory.FALSE_SCARCITY: "Creates artificial scarcity",
            PatternCategory.ENGAGEMENT_OPTIMIZATION: "Optimizes for engagement over value",
            PatternCategory.HARD_VIOLATION: "Cannot be transformed or allowed",
        }
        return descriptions[self]

    @property
    def default_severity(self) -> PatternSeverity:
        """Default severity for patterns in this category."""
        severity_map = {
            PatternCategory.URGENCY_PRESSURE: PatternSeverity.TRANSFORM,
            PatternCategory.GUILT_INDUCTION: PatternSeverity.REJECT,
            PatternCategory.FALSE_SCARCITY: PatternSeverity.REJECT,
            PatternCategory.ENGAGEMENT_OPTIMIZATION: PatternSeverity.TRANSFORM,
            PatternCategory.HARD_VIOLATION: PatternSeverity.BLOCK,
        }
        return severity_map[self]


@dataclass(frozen=True)
class CoercionPattern:
    """A pattern for detecting coercive language.

    Patterns are immutable value objects that define:
    - What to match (regex pattern)
    - How severe it is (severity)
    - What category it belongs to
    - Optional replacement for TRANSFORM severity

    Constitutional Guarantee:
    - Patterns are deterministic (same input = same result) per AC7
    - All patterns are versioned for auditability per AC5

    Usage:
        pattern = CoercionPattern(
            id="urgency_caps_urgent",
            category=PatternCategory.URGENCY_PRESSURE,
            severity=PatternSeverity.TRANSFORM,
            pattern=r"\\bURGENT\\b",
            description="Caps-lock URGENT creates artificial pressure",
            replacement="",
        )

        if pattern.matches("URGENT task"):
            result = pattern.apply("URGENT task")  # Returns " task"
    """

    id: str
    category: PatternCategory
    severity: PatternSeverity
    pattern: str  # Regex pattern
    description: str
    replacement: Optional[str] = None  # For TRANSFORM severity
    rejection_reason: Optional[str] = None  # For REJECT severity
    violation_type: Optional[str] = None  # For BLOCK severity
    case_sensitive: bool = False  # Default: case-insensitive matching

    def __post_init__(self) -> None:
        """Validate pattern fields."""
        if not self.id:
            raise ValueError("Pattern ID is required")
        if not self.pattern:
            raise ValueError("Pattern regex is required")
        if not self.description:
            raise ValueError("Pattern description is required")

        # Validate regex syntax
        try:
            re.compile(self.pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{self.pattern}': {e}")

        # Validate severity-specific fields
        if self.severity == PatternSeverity.TRANSFORM and self.replacement is None:
            # Allow empty string replacement (removal), but None means default ""
            object.__setattr__(self, "replacement", "")

    def matches(self, content: str) -> bool:
        """Check if pattern matches content.

        Args:
            content: Content to check

        Returns:
            True if pattern matches, False otherwise.

        Note:
            Matching is case-insensitive by default unless case_sensitive=True.
            This is deterministic per AC7.
        """
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return bool(re.search(self.pattern, content, flags))

    def _get_flags(self) -> int:
        """Get regex flags based on case_sensitive setting."""
        return 0 if self.case_sensitive else re.IGNORECASE

    def extract_match(self, content: str) -> Optional[str]:
        """Extract the matched text from content.

        Args:
            content: Content to search

        Returns:
            The matched text, or None if no match.
        """
        match = re.search(self.pattern, content, self._get_flags())
        return match.group(0) if match else None

    def find_all_matches(self, content: str) -> list[str]:
        """Find all matches in content.

        Args:
            content: Content to search

        Returns:
            List of all matched strings.
        """
        return re.findall(self.pattern, content, self._get_flags())

    def find_match_positions(self, content: str) -> list[tuple[int, int]]:
        """Find positions of all matches.

        Args:
            content: Content to search

        Returns:
            List of (start, end) tuples for each match.
        """
        return [(m.start(), m.end()) for m in re.finditer(self.pattern, content, self._get_flags())]

    def apply(self, content: str) -> str:
        """Apply transformation (for TRANSFORM severity only).

        Args:
            content: Content to transform

        Returns:
            Transformed content with pattern replaced.

        Raises:
            ValueError: If severity is not TRANSFORM.
        """
        if self.severity != PatternSeverity.TRANSFORM:
            raise ValueError(
                f"Can only apply TRANSFORM patterns, got {self.severity.value}"
            )
        replacement = self.replacement if self.replacement is not None else ""
        return re.sub(self.pattern, replacement, content, flags=self._get_flags())

    def count_matches(self, content: str) -> int:
        """Count number of matches in content.

        Args:
            content: Content to search

        Returns:
            Number of matches found.
        """
        return len(re.findall(self.pattern, content, self._get_flags()))


@dataclass(frozen=True)
class PatternLibraryVersion:
    """Version information for pattern library.

    Per AC5, all pattern libraries are versioned and auditable.
    The hash ensures integrity of the pattern set.
    """

    version: str  # semver format: X.Y.Z
    patterns_hash: str  # blake3 or sha256 hash of all patterns
    pattern_count: int
    loaded_at: datetime  # When this version was loaded

    def __post_init__(self) -> None:
        """Validate version format."""
        if not self.version:
            raise ValueError("Version is required")
        if not self.patterns_hash:
            raise ValueError("Patterns hash is required")

        # Validate semver format
        if not re.match(r"^\d+\.\d+\.\d+$", self.version):
            raise ValueError(
                f"Version must be in semver format (X.Y.Z), got: {self.version}"
            )

    @property
    def major(self) -> int:
        """Major version number."""
        return int(self.version.split(".")[0])

    @property
    def minor(self) -> int:
        """Minor version number."""
        return int(self.version.split(".")[1])

    @property
    def patch(self) -> int:
        """Patch version number."""
        return int(self.version.split(".")[2])
