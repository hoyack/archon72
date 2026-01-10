"""Cessation trigger condition models (Story 7.7, FR134).

This module defines the domain model for public cessation trigger conditions.
All trigger conditions are sourced from CONSTITUTIONAL_THRESHOLD_REGISTRY.

Constitutional Constraints:
- FR134: Public documentation of cessation trigger conditions
- FR33: Threshold definitions SHALL be constitutional, not operational
- FR37: 3 consecutive integrity failures in 30 days triggers cessation
- FR38: Anti-success alert sustained 90 days triggers cessation
- FR39: External observer petition with 100+ co-signers triggers cessation
- FR32: >10 unacknowledged breaches in 90-day window triggers cessation
- RT-4: 5 non-consecutive failures in any 90-day rolling window triggers cessation
- CT-11: Silent failure destroys legitimacy -> All conditions must be visible
- CT-12: Witnessing creates accountability -> Changes must be witnessed

Developer Golden Rules:
1. REGISTRY SOURCE OF TRUTH - All thresholds from CONSTITUTIONAL_THRESHOLD_REGISTRY
2. PUBLIC READ - No authentication required for trigger conditions
3. WITNESS CHANGES - Any threshold change must create witnessed event
4. VERSION TRACKING - Include schema and constitution versions
5. READ-ONLY SURVIVES - Endpoint must work after cessation

Usage:
    from src.domain.models.cessation_trigger_condition import (
        CessationTriggerCondition,
        CessationTriggerConditionSet,
    )

    # Create a single trigger condition
    condition = CessationTriggerCondition(
        trigger_type="consecutive_failures",
        threshold=3,
        window_days=30,
        description="3 consecutive integrity failures in 30 days",
        fr_reference="FR37",
        constitutional_floor=3,
    )

    # Create a full set of trigger conditions
    condition_set = CessationTriggerConditionSet.from_registry()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True, eq=True)
class CessationTriggerCondition:
    """A single cessation trigger condition (FR134).

    Represents one type of condition that can trigger cessation
    agenda placement. All threshold values are sourced from the
    constitutional threshold registry.

    Constitutional Constraint (FR134):
    Public documentation of cessation trigger conditions SHALL include
    all automatic trigger types with their thresholds and descriptions.

    Attributes:
        trigger_type: Unique identifier for this trigger type.
        threshold: Numeric threshold value that triggers cessation.
        window_days: Rolling window in days (optional, None if not applicable).
        description: Human-readable description of the trigger.
        fr_reference: Functional requirement reference (e.g., "FR37").
        constitutional_floor: Minimum allowed value for this threshold.

    Example:
        >>> condition = CessationTriggerCondition(
        ...     trigger_type="consecutive_failures",
        ...     threshold=3,
        ...     window_days=30,
        ...     description="3 consecutive failures in 30 days",
        ...     fr_reference="FR37",
        ...     constitutional_floor=3,
        ... )
        >>> condition.trigger_type
        'consecutive_failures'
    """

    trigger_type: str
    threshold: int | float
    window_days: Optional[int]
    description: str
    fr_reference: str
    constitutional_floor: int | float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict with all trigger condition fields formatted for API response.
        """
        result: dict[str, Any] = {
            "trigger_type": self.trigger_type,
            "threshold": self.threshold,
            "description": self.description,
            "fr_reference": self.fr_reference,
            "constitutional_floor": self.constitutional_floor,
        }
        # Only include window_days if applicable
        if self.window_days is not None:
            result["window_days"] = self.window_days
        return result

    def to_json_ld(self) -> dict[str, Any]:
        """Convert to JSON-LD format for semantic interoperability (FR134 AC5).

        Returns:
            Dict with JSON-LD context and trigger condition fields.
        """
        result = self.to_dict()
        result["@type"] = "cessation:TriggerCondition"
        return result


# JSON-LD context for semantic interoperability (FR134 AC5)
CESSATION_TRIGGER_JSON_LD_CONTEXT: dict[str, Any] = {
    "@context": {
        "cessation": "https://archon72.org/schema/cessation#",
        "trigger_type": "cessation:triggerType",
        "threshold": "cessation:threshold",
        "window_days": "cessation:windowDays",
        "description": "cessation:description",
        "fr_reference": "cessation:functionalRequirement",
        "constitutional_floor": "cessation:constitutionalFloor",
        "TriggerCondition": "cessation:TriggerCondition",
        "TriggerConditionSet": "cessation:TriggerConditionSet",
    }
}


@dataclass(frozen=True)
class CessationTriggerConditionSet:
    """Complete set of cessation trigger conditions (FR134).

    Contains all automatic trigger conditions that can cause cessation
    agenda placement. Includes version tracking for API compatibility.

    Constitutional Constraint (FR134):
    All cessation trigger conditions SHALL be publicly documented.
    Threshold values SHALL be sourced from CONSTITUTIONAL_THRESHOLD_REGISTRY.

    Attributes:
        conditions: Tuple of all trigger conditions.
        schema_version: Version of the API schema.
        constitution_version: Version of the constitutional rules.
        effective_date: When the current rules took effect.
        last_updated: When these conditions were last updated.

    Example:
        >>> condition_set = CessationTriggerConditionSet.from_registry()
        >>> len(condition_set.conditions)
        5
    """

    conditions: tuple[CessationTriggerCondition, ...]
    schema_version: str = field(default="1.0.0")
    constitution_version: str = field(default="1.0.0")
    effective_date: datetime = field(
        default_factory=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    last_updated: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def from_registry(cls) -> CessationTriggerConditionSet:
        """Create trigger conditions from constitutional threshold registry.

        Sources all threshold values from CONSTITUTIONAL_THRESHOLD_REGISTRY
        per FR33 (thresholds are constitutional, not operational).

        Returns:
            CessationTriggerConditionSet with all trigger conditions.
        """
        # Import here to avoid circular dependencies
        from src.domain.primitives.constitutional_thresholds import (
            CESSATION_BREACH_THRESHOLD,
            CESSATION_WINDOW_DAYS_THRESHOLD,
        )

        # FR37: 3 consecutive integrity failures in 30 days
        consecutive_failures = CessationTriggerCondition(
            trigger_type="consecutive_failures",
            threshold=3,  # Fixed by FR37, not in registry
            window_days=30,  # Fixed by FR37, not in registry
            description=(
                "3 consecutive integrity failures in 30 days SHALL trigger "
                "automatic cessation agenda placement"
            ),
            fr_reference="FR37",
            constitutional_floor=3,  # FR37 specifies exactly 3
        )

        # RT-4: 5 non-consecutive failures in any 90-day rolling window
        rolling_window = CessationTriggerCondition(
            trigger_type="rolling_window",
            threshold=5,  # Fixed by RT-4, not in registry
            window_days=CESSATION_WINDOW_DAYS_THRESHOLD.current_value,
            description=(
                "5 non-consecutive integrity failures in any 90-day rolling "
                "window SHALL trigger cessation agenda placement (timing attack prevention)"
            ),
            fr_reference="RT-4",
            constitutional_floor=5,  # RT-4 specifies exactly 5
        )

        # FR38: Anti-success alert sustained 90 days
        anti_success_sustained = CessationTriggerCondition(
            trigger_type="anti_success_sustained",
            threshold=90,  # 90 days sustained
            window_days=None,  # N/A - this is the duration itself
            description=(
                "Anti-success alert sustained for 90 days SHALL trigger "
                "automatic cessation agenda placement"
            ),
            fr_reference="FR38",
            constitutional_floor=90,  # FR38 specifies exactly 90 days
        )

        # FR39: External observer petition with 100+ co-signers
        petition_threshold = CessationTriggerCondition(
            trigger_type="petition_threshold",
            threshold=100,  # 100 co-signers
            window_days=None,  # N/A - this is a count, not a rolling window
            description=(
                "External observer petition with 100 or more co-signers "
                "SHALL trigger cessation agenda placement"
            ),
            fr_reference="FR39",
            constitutional_floor=100,  # FR39 specifies exactly 100
        )

        # FR32: >10 unacknowledged breaches in 90-day window
        breach_threshold = CessationTriggerCondition(
            trigger_type="breach_threshold",
            threshold=CESSATION_BREACH_THRESHOLD.current_value,
            window_days=CESSATION_WINDOW_DAYS_THRESHOLD.current_value,
            description=(
                f"More than {CESSATION_BREACH_THRESHOLD.current_value} "
                f"unacknowledged breaches in "
                f"{CESSATION_WINDOW_DAYS_THRESHOLD.current_value}-day "
                "window SHALL trigger cessation agenda placement"
            ),
            fr_reference="FR32",
            constitutional_floor=CESSATION_BREACH_THRESHOLD.constitutional_floor,
        )

        return cls(
            conditions=(
                consecutive_failures,
                rolling_window,
                anti_success_sustained,
                petition_threshold,
                breach_threshold,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization (FR134 AC5).

        Returns:
            Dict with version metadata and all trigger conditions.
        """
        return {
            "schema_version": self.schema_version,
            "constitution_version": self.constitution_version,
            "effective_date": self.effective_date.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "trigger_conditions": [c.to_dict() for c in self.conditions],
        }

    def to_json_ld(self) -> dict[str, Any]:
        """Convert to JSON-LD format for semantic interoperability (FR134 AC5).

        Returns:
            Dict with JSON-LD context and all trigger conditions.
        """
        result = self.to_dict()
        result["@context"] = CESSATION_TRIGGER_JSON_LD_CONTEXT["@context"]
        result["@type"] = "cessation:TriggerConditionSet"
        result["trigger_conditions"] = [
            c.to_json_ld() for c in self.conditions
        ]
        return result

    def get_condition(self, trigger_type: str) -> Optional[CessationTriggerCondition]:
        """Get a specific trigger condition by type.

        Args:
            trigger_type: The trigger_type to look up.

        Returns:
            The CessationTriggerCondition if found, None otherwise.
        """
        for condition in self.conditions:
            if condition.trigger_type == trigger_type:
                return condition
        return None

    def __len__(self) -> int:
        """Return number of trigger conditions."""
        return len(self.conditions)

    def __iter__(self):
        """Iterate over trigger conditions."""
        return iter(self.conditions)
