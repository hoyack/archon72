"""FilterVersion value object for tracking filter rule versions.

Tracks which version of the filter rules processed content for auditability.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FilterVersion:
    """Version of the filter rules used.

    This enables audit trails to track which filter version
    processed each piece of content.
    """

    major: int
    minor: int
    patch: int
    rules_hash: str  # Hash of the pattern library

    def __str__(self) -> str:
        """Return semantic version string."""
        return f"{self.major}.{self.minor}.{self.patch}"

    def __post_init__(self) -> None:
        """Validate version components."""
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("Version components must be non-negative")
        if not self.rules_hash:
            raise ValueError("Rules hash is required")
