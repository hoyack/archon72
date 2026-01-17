"""Anti-Metrics Domain Module.

Story: consent-gov-10.1: Anti-Metrics Data Layer Enforcement

This module implements the anti-metrics constitutional constraint (NFR-CONST-08):
Anti-metrics are enforced at data layer; collection endpoints do not exist.

Design Philosophy - Structural Absence:
    Traditional: "Don't track metrics" (policy)
        - Can be ignored
        - Can be "accidentally" implemented
        - Requires ongoing vigilance

    Structural: No metrics infrastructure exists
        - No metric tables in schema
        - No metric endpoints in router
        - No metric fields in models
        - Cannot use what doesn't exist

Constitutional Guarantees:
- FR61: System can coordinate tasks without storing participant-level performance metrics
- FR62: System can complete task workflows without calculating completion rates per participant
- FR63: System can operate without engagement or retention tracking
- NFR-CONST-08: Anti-metrics are enforced at data layer; collection endpoints do not exist

Why Anti-Metrics?
    The system exists to serve, not to surveil:
    - No engagement optimization
    - No retention tracking
    - No performance scoring
    - No participant surveillance
"""

from src.domain.governance.antimetrics.prohibited_pattern import (
    PROHIBITED_COLUMN_PATTERNS,
    PROHIBITED_TABLE_PATTERNS,
    ProhibitedPattern,
)
from src.domain.governance.antimetrics.violation import (
    AntiMetricsViolation,
    AntiMetricsViolationError,
)

__all__ = [
    "ProhibitedPattern",
    "PROHIBITED_TABLE_PATTERNS",
    "PROHIBITED_COLUMN_PATTERNS",
    "AntiMetricsViolation",
    "AntiMetricsViolationError",
]
