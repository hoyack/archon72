"""Constitutional threshold definitions (Story 6.4, FR33-FR34).

This module defines all constitutional thresholds with their floors.
These thresholds cannot be lowered below their defined minimums.

Constitutional Constraints:
- FR33: Threshold definitions SHALL be constitutional, not operational
- FR34: Threshold changes SHALL NOT reset active counters
- NFR39: No configuration SHALL allow thresholds below constitutional floors

Usage:
    from src.domain.primitives.constitutional_thresholds import (
        CONSTITUTIONAL_THRESHOLD_REGISTRY,
        get_threshold,
    )

    # Get a specific threshold
    cessation = get_threshold("cessation_breach_count")

    # Check the floor
    print(f"Floor: {cessation.constitutional_floor}")
"""

from src.domain.models.constitutional_threshold import (
    ConstitutionalThreshold,
    ConstitutionalThresholdRegistry,
)

# =============================================================================
# FR32: Cessation Thresholds
# =============================================================================

CESSATION_BREACH_THRESHOLD = ConstitutionalThreshold(
    threshold_name="cessation_breach_count",
    constitutional_floor=10,
    current_value=10,
    is_constitutional=True,
    description="Maximum unacknowledged breaches before cessation consideration (>10 triggers)",
    fr_reference="FR32",
)
"""FR32: Cessation triggers at >10 unacknowledged breaches in 90-day window."""

CESSATION_WINDOW_DAYS_THRESHOLD = ConstitutionalThreshold(
    threshold_name="cessation_window_days",
    constitutional_floor=90,
    current_value=90,
    is_constitutional=True,
    description="Rolling window for breach counting in cessation consideration",
    fr_reference="FR32",
)
"""FR32: 90-day rolling window for cessation breach counting."""


# =============================================================================
# FR21/NFR41: Recovery Waiting Period
# =============================================================================

RECOVERY_WAITING_HOURS_THRESHOLD = ConstitutionalThreshold(
    threshold_name="recovery_waiting_hours",
    constitutional_floor=48,
    current_value=48,
    is_constitutional=True,
    description="Minimum hours for recovery waiting period (constitutional floor)",
    fr_reference="NFR41",
)
"""NFR41: 48-hour minimum recovery waiting period."""


# =============================================================================
# FR79: Keeper Quorum
# =============================================================================

MINIMUM_KEEPER_QUORUM_THRESHOLD = ConstitutionalThreshold(
    threshold_name="minimum_keeper_quorum",
    constitutional_floor=3,
    current_value=3,
    is_constitutional=True,
    description="Minimum registered Keepers before system halt",
    fr_reference="FR79",
)
"""FR79: Minimum of 3 Keepers required at all times."""


# =============================================================================
# FR31: Escalation Threshold
# =============================================================================

ESCALATION_DAYS_THRESHOLD = ConstitutionalThreshold(
    threshold_name="escalation_days",
    constitutional_floor=7,
    current_value=7,
    is_constitutional=True,
    description="Days before unacknowledged breach escalates to Conclave agenda",
    fr_reference="FR31",
)
"""FR31: 7-day escalation to Conclave agenda."""


# =============================================================================
# FR78: Keeper Attestation
# =============================================================================

ATTESTATION_PERIOD_THRESHOLD = ConstitutionalThreshold(
    threshold_name="attestation_period_days",
    constitutional_floor=7,
    current_value=7,
    is_constitutional=True,
    description="Days between required Keeper attestations",
    fr_reference="FR78",
)
"""FR78: Weekly Keeper attestation requirement."""

MISSED_ATTESTATIONS_THRESHOLD_DEF = ConstitutionalThreshold(
    threshold_name="missed_attestations_threshold",
    constitutional_floor=2,
    current_value=2,
    is_constitutional=True,
    description="Consecutive missed attestations before replacement trigger",
    fr_reference="FR78",
)
"""FR78: 2 missed attestations triggers replacement process."""


# =============================================================================
# FR27: Override Thresholds
# =============================================================================

OVERRIDE_WARNING_30_DAY_THRESHOLD = ConstitutionalThreshold(
    threshold_name="override_warning_30_day",
    constitutional_floor=5,
    current_value=5,
    is_constitutional=True,
    description="Maximum overrides in 30 days before anti-success alert",
    fr_reference="FR27",
)
"""FR27: Anti-success alert at 5 overrides in 30 days."""

OVERRIDE_GOVERNANCE_365_DAY_THRESHOLD = ConstitutionalThreshold(
    threshold_name="override_governance_365_day",
    constitutional_floor=20,
    current_value=20,
    is_constitutional=True,
    description="Maximum overrides in 365 days before governance review required",
    fr_reference="RT-3",
)
"""RT-3: Governance review required at 20 overrides in 365 days."""


# =============================================================================
# FR73: Topic Diversity
# =============================================================================

TOPIC_DIVERSITY_THRESHOLD_DEF = ConstitutionalThreshold(
    threshold_name="topic_diversity_threshold",
    constitutional_floor=0.30,
    current_value=0.30,
    is_constitutional=True,
    description="Maximum percentage from single origin type over 30 days",
    fr_reference="FR73",
)
"""FR73: No single origin type can exceed 30% of topics."""


# =============================================================================
# FR85: Fork Signal Rate Limit
# =============================================================================

FORK_SIGNAL_RATE_LIMIT_THRESHOLD = ConstitutionalThreshold(
    threshold_name="fork_signal_rate_limit",
    constitutional_floor=3,
    current_value=3,
    is_constitutional=True,
    description="Maximum fork signals per hour per source",
    fr_reference="FR85",
)
"""FR85: Rate limit of 3 fork signals per hour per source."""


# =============================================================================
# ADR-3: Halt Confirmation
# =============================================================================

HALT_CONFIRMATION_SECONDS_THRESHOLD = ConstitutionalThreshold(
    threshold_name="halt_confirmation_seconds",
    constitutional_floor=5,
    current_value=5,
    is_constitutional=True,
    description="Maximum seconds for Redis-DB halt confirmation",
    fr_reference="ADR-3",
)
"""ADR-3: 5-second maximum for dual-channel halt confirmation."""


# =============================================================================
# FR59-61: Witness Pool
# =============================================================================

WITNESS_POOL_MINIMUM_THRESHOLD = ConstitutionalThreshold(
    threshold_name="witness_pool_minimum_high_stakes",
    constitutional_floor=12,
    current_value=12,
    is_constitutional=True,
    description="Minimum witnesses for high-stakes operations",
    fr_reference="FR59",
)
"""FR59-61: Minimum witness pool for high-stakes operations."""


# =============================================================================
# Registry of All Constitutional Thresholds
# =============================================================================

CONSTITUTIONAL_THRESHOLD_REGISTRY = ConstitutionalThresholdRegistry(
    thresholds=(
        CESSATION_BREACH_THRESHOLD,
        CESSATION_WINDOW_DAYS_THRESHOLD,
        RECOVERY_WAITING_HOURS_THRESHOLD,
        MINIMUM_KEEPER_QUORUM_THRESHOLD,
        ESCALATION_DAYS_THRESHOLD,
        ATTESTATION_PERIOD_THRESHOLD,
        MISSED_ATTESTATIONS_THRESHOLD_DEF,
        OVERRIDE_WARNING_30_DAY_THRESHOLD,
        OVERRIDE_GOVERNANCE_365_DAY_THRESHOLD,
        TOPIC_DIVERSITY_THRESHOLD_DEF,
        FORK_SIGNAL_RATE_LIMIT_THRESHOLD,
        HALT_CONFIRMATION_SECONDS_THRESHOLD,
        WITNESS_POOL_MINIMUM_THRESHOLD,
    )
)
"""Registry of all constitutional thresholds with their floors."""


def get_threshold(name: str) -> ConstitutionalThreshold:
    """Get a constitutional threshold by name.

    Args:
        name: The threshold_name to look up.

    Returns:
        The ConstitutionalThreshold with the given name.

    Raises:
        KeyError: If no threshold with that name exists.

    Example:
        >>> threshold = get_threshold("cessation_breach_count")
        >>> threshold.constitutional_floor
        10
    """
    return CONSTITUTIONAL_THRESHOLD_REGISTRY.get_threshold(name)


def validate_all_thresholds() -> None:
    """Validate all constitutional thresholds.

    Raises:
        ConstitutionalFloorViolationError: If any threshold is invalid.
    """
    CONSTITUTIONAL_THRESHOLD_REGISTRY.validate_all()


# All threshold names for easy reference
THRESHOLD_NAMES: tuple[str, ...] = tuple(
    t.threshold_name for t in CONSTITUTIONAL_THRESHOLD_REGISTRY.thresholds
)
"""All threshold names in the registry."""
