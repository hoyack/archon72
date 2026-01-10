"""Override reason enumeration for Keeper override actions (Story 5.2, FR28; Story 5.4, FR26).

This module defines the enumerated reasons for override actions.
All override actions MUST specify a reason from this list (FR28).
Also defines forbidden override scopes that cannot be targeted (FR26).

Constitutional Constraints:
- FR26: Overrides cannot suppress witnessing (Constitution Supremacy)
- FR28: Override reasons must be from enumerated list
- FR24: Override events SHALL include reason attribution
- CT-12: Witnessing creates accountability -> Reason is part of witnessed content

Override Reason Categories:
- Technical: System failures requiring intervention
- Operational: Ceremony and configuration issues
- Security: Incident response and emergency actions

Forbidden Override Scopes (FR26):
- witness, witnessing, attestation: Cannot suppress witnessing
- witness_service, witness_pool: Cannot disable witness infrastructure
"""

from __future__ import annotations

from enum import Enum


class OverrideReason(Enum):
    """Enumerated override reasons (FR28).

    Each reason must be documented and auditable.
    Override actions MUST specify exactly one reason from this list.

    Constitutional Constraint (FR28):
    Override reasons are constrained to prevent arbitrary justifications.
    Each reason represents a specific, auditable category of intervention.

    Attributes:
        value: The string value used for serialization.
        description: Human-readable explanation of when to use this reason.
    """

    TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
    """Technical failure preventing normal operation."""

    CEREMONY_HEALTH = "CEREMONY_HEALTH"
    """Ceremony health check override (Tier 1)."""

    EMERGENCY_HALT_CLEAR = "EMERGENCY_HALT_CLEAR"
    """Emergency halt clearing."""

    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    """Configuration error correction."""

    WATCHDOG_INTERVENTION = "WATCHDOG_INTERVENTION"
    """Watchdog intervention required."""

    SECURITY_INCIDENT = "SECURITY_INCIDENT"
    """Security incident response."""

    @property
    def description(self) -> str:
        """Return human-readable description of the override reason.

        Returns:
            A descriptive string explaining when this reason applies.
        """
        descriptions: dict[OverrideReason, str] = {
            OverrideReason.TECHNICAL_FAILURE: (
                "Technical failure preventing normal operation - "
                "system bugs, crashes, or infrastructure issues"
            ),
            OverrideReason.CEREMONY_HEALTH: (
                "Ceremony health check override (Tier 1) - "
                "issues with ceremony execution or quorum"
            ),
            OverrideReason.EMERGENCY_HALT_CLEAR: (
                "Emergency halt clearing - "
                "critical system recovery from halted state"
            ),
            OverrideReason.CONFIGURATION_ERROR: (
                "Configuration error correction - "
                "misconfigurations requiring immediate fix"
            ),
            OverrideReason.WATCHDOG_INTERVENTION: (
                "Watchdog intervention required - "
                "watchdog-detected issues requiring override"
            ),
            OverrideReason.SECURITY_INCIDENT: (
                "Security incident response - "
                "active security threats requiring immediate action"
            ),
        }
        return descriptions[self]


# =============================================================================
# Forbidden Override Scopes (FR26, Story 5.4)
# =============================================================================

FORBIDDEN_OVERRIDE_SCOPES: frozenset[str] = frozenset([
    "witness",
    "witnessing",
    "attestation",
    "witness_service",
    "witness_pool",
])
"""Exact scope names that are forbidden (FR26).

These scopes directly target witnessing infrastructure and cannot be overridden.
Any override attempt targeting these scopes will be rejected with a
WitnessSuppressionAttemptError.
"""

FORBIDDEN_OVERRIDE_SCOPE_PATTERNS: tuple[str, ...] = (
    "witness.",
    "attestation.",
)
"""Prefix patterns for forbidden scopes (FR26).

Any scope starting with these patterns targets witnessing subsystems
and will be rejected. For example:
- "witness.pool" matches "witness."
- "attestation.disable" matches "attestation."
"""


def is_witness_suppression_scope(scope: str) -> bool:
    """Check if scope attempts to suppress witnessing (FR26).

    Constitutional Constraint (FR26):
    Overrides that attempt to suppress witnessing are invalid by definition.
    This function detects override scopes that would disable or suppress
    the witnessing mechanism.

    Cross-Epic Requirement (PM-4):
    This validation is invoked by Epic 5 (Override layer) to protect
    the witnessing guarantees established by Epic 1 (Event Store layer).

    Args:
        scope: Override scope to validate.

    Returns:
        True if scope attempts witness suppression (FORBIDDEN),
        False if scope is allowed.

    Examples:
        >>> is_witness_suppression_scope("witness")
        True
        >>> is_witness_suppression_scope("witness_pool")
        True
        >>> is_witness_suppression_scope("witness.disable")
        True
        >>> is_witness_suppression_scope("attestation")
        True
        >>> is_witness_suppression_scope("voting.extension")
        False
    """
    scope_lower = scope.lower()

    # Check exact matches
    if scope_lower in FORBIDDEN_OVERRIDE_SCOPES:
        return True

    # Check prefix patterns
    for pattern in FORBIDDEN_OVERRIDE_SCOPE_PATTERNS:
        if scope_lower.startswith(pattern):
            return True

    return False
