"""Trend analysis domain errors (Story 5.5, FR27, RT-3).

This module defines exceptions related to override trend analysis.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> Errors must be surfaced
- FR27: Override trend analysis with anti-success alerts
- RT-3: >20 overrides in 365-day window triggers governance review
"""

from src.domain.exceptions import ConclaveError


class TrendAnalysisError(ConclaveError):
    """Base exception for trend analysis failures.

    All trend analysis exceptions inherit from this class.
    This enables specific handling of analysis-related errors.

    Constitutional Reference: FR27 - Override trend analysis
    """

    pass


class InsufficientDataError(TrendAnalysisError):
    """Raised when there is not enough historical data for analysis.

    This error indicates that the analysis cannot be performed due to
    insufficient override history. The system should surface this clearly
    rather than silently degrading (CT-11).

    Example cases:
    - System just started, no overrides yet
    - Requested analysis window exceeds available data
    - Data corruption detected

    Constitutional Reference: CT-11 - Silent failure destroys legitimacy
    """

    pass
