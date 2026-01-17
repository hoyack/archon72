"""Transformation models for content filtering.

Defines the transformation rules and records for the ACCEPTED outcome.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TransformationRule:
    """A rule for transforming content.

    Transformation rules are versioned and auditable.
    They define what patterns to match and how to transform them.
    """

    rule_id: str
    pattern: str  # Regex or pattern to match
    replacement: str  # What to replace with (can be empty for removal)
    description: str  # Human-readable description
    category: str  # E.g., "urgency", "emphasis", "pressure"
    version: str  # Version of this rule (semver format: X.Y.Z)

    def __post_init__(self) -> None:
        """Validate rule fields."""
        if not self.rule_id:
            raise ValueError("Rule ID is required")
        if not self.pattern:
            raise ValueError("Pattern is required")
        if not self.category:
            raise ValueError("Category is required")
        if not self.version:
            raise ValueError("Version is required")
        # Validate semver format (relaxed: X.Y.Z where X, Y, Z are digits)
        if not re.match(r"^\d+\.\d+\.\d+$", self.version):
            raise ValueError(
                f"Version must be in semver format (X.Y.Z), got: {self.version}"
            )


@dataclass(frozen=True)
class Transformation:
    """Record of a transformation applied to content.

    This is an audit record showing exactly what was changed.
    """

    pattern_matched: str  # The pattern that matched
    original_text: str  # The original text that was matched
    replacement_text: str  # What it was replaced with
    rule_id: str  # Which rule was applied
    position: int | None = None  # Character position where match occurred

    def __post_init__(self) -> None:
        """Validate transformation fields."""
        if not self.rule_id:
            raise ValueError("Rule ID is required for audit trail")

    @property
    def was_removed(self) -> bool:
        """Whether the transformation removed content entirely."""
        return self.replacement_text == ""

    @property
    def change_description(self) -> str:
        """Human-readable description of this transformation."""
        if self.was_removed:
            return f"Removed '{self.original_text}' (rule: {self.rule_id})"
        return f"Changed '{self.original_text}' to '{self.replacement_text}' (rule: {self.rule_id})"
