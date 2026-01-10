"""Constitutional threshold model (Story 6.4, FR33-FR34).

This module provides the ConstitutionalThreshold model for representing
thresholds that cannot be lowered below their constitutional floors.

Constitutional Constraints:
- FR33: Threshold definitions SHALL be constitutional, not operational
- FR34: Threshold changes SHALL NOT reset active counters
- NFR39: No configuration SHALL allow thresholds below constitutional floors
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.domain.errors.threshold import ConstitutionalFloorViolationError


@dataclass(frozen=True)
class ConstitutionalThreshold:
    """A constitutional threshold that cannot be lowered below its floor.

    Constitutional Constraint (FR33):
    Threshold definitions SHALL be constitutional, not operational.
    This means they have a floor that cannot be breached.

    Attributes:
        threshold_name: Unique identifier for this threshold.
        constitutional_floor: Minimum allowed value (cannot go below this).
        current_value: Active value (must be >= floor).
        is_constitutional: Always True for constitutional thresholds.
        description: Human-readable description of the threshold.
        fr_reference: FR/NFR reference (e.g., "FR32", "NFR39").

    Example:
        >>> threshold = ConstitutionalThreshold(
        ...     threshold_name="cessation_breach_count",
        ...     constitutional_floor=10,
        ...     current_value=10,
        ...     is_constitutional=True,
        ...     description="Maximum unacknowledged breaches before cessation",
        ...     fr_reference="FR32",
        ... )
        >>> threshold.is_valid
        True
    """

    threshold_name: str
    constitutional_floor: int | float
    current_value: int | float
    is_constitutional: bool
    description: str
    fr_reference: str

    def __post_init__(self) -> None:
        """Validate threshold on creation.

        Raises:
            ConstitutionalFloorViolationError: If current_value < constitutional_floor.
        """
        if self.current_value < self.constitutional_floor:
            raise ConstitutionalFloorViolationError(
                threshold_name=self.threshold_name,
                attempted_value=self.current_value,
                constitutional_floor=self.constitutional_floor,
                fr_reference=self.fr_reference,
            )

    @property
    def is_valid(self) -> bool:
        """Check if current value is at or above floor.

        Returns:
            True if current_value >= constitutional_floor.
        """
        return self.current_value >= self.constitutional_floor

    def validate(self) -> None:
        """Validate threshold, raise error if invalid (FR33).

        Raises:
            ConstitutionalFloorViolationError: If current_value < constitutional_floor.
        """
        if not self.is_valid:
            raise ConstitutionalFloorViolationError(
                threshold_name=self.threshold_name,
                attempted_value=self.current_value,
                constitutional_floor=self.constitutional_floor,
                fr_reference=self.fr_reference,
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization.

        Returns:
            Dictionary with all threshold fields.
        """
        return {
            "threshold_name": self.threshold_name,
            "constitutional_floor": self.constitutional_floor,
            "current_value": self.current_value,
            "is_constitutional": self.is_constitutional,
            "description": self.description,
            "fr_reference": self.fr_reference,
        }


@dataclass(frozen=True)
class ConstitutionalThresholdRegistry:
    """Registry of all defined constitutional thresholds.

    Provides lookup and validation for constitutional thresholds.
    This registry is immutable and contains all system thresholds.

    Attributes:
        thresholds: Tuple of all constitutional thresholds.
    """

    thresholds: tuple[ConstitutionalThreshold, ...]

    def get_all_thresholds(self) -> tuple[ConstitutionalThreshold, ...]:
        """Return all defined constitutional thresholds.

        Returns:
            Tuple of all ConstitutionalThreshold instances.
        """
        return self.thresholds

    def get_threshold(self, name: str) -> ConstitutionalThreshold:
        """Look up a threshold by name.

        Args:
            name: The threshold_name to look up.

        Returns:
            The ConstitutionalThreshold with the given name.

        Raises:
            KeyError: If no threshold with that name exists.
        """
        for threshold in self.thresholds:
            if threshold.threshold_name == name:
                return threshold
        raise KeyError(f"Threshold not found: {name}")

    def validate_all(self) -> None:
        """Validate all thresholds in the registry.

        Raises:
            ConstitutionalFloorViolationError: If any threshold is invalid.
        """
        for threshold in self.thresholds:
            threshold.validate()

    def __len__(self) -> int:
        """Return the number of thresholds in the registry."""
        return len(self.thresholds)

    def __iter__(self):
        """Iterate over thresholds."""
        return iter(self.thresholds)
