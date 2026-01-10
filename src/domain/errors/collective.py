"""Collective output constraint errors (Story 2.3, FR11).

This module defines error types for FR11 (Collective Output Irreducibility) violations.
FR11 requires collective outputs to be attributed to the Conclave, not individuals.

Constitutional Constraints:
- FR11: Collective outputs attributed to Conclave, not individuals
- CT-11: Silent failure destroys legitimacy → Violations HALT system
- CT-13: Integrity outranks availability → Better to reject than accept invalid output
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class FR11ViolationError(ConstitutionalViolationError):
    """Raised when Collective Output Irreducibility (FR11) is violated.

    FR11 violations indicate an attempt to create a collective output
    that does not meet the requirements for collective attribution.

    This is a CRITICAL constitutional violation that must NEVER be
    silently ignored.

    Examples:
        - Single-agent "collective" output (requires at least 2)
        - Zero-agent collective output
        - Invalid author_type for collective output

    Usage:
        raise FR11ViolationError(
            "FR11: Collective output requires multiple participants"
        )
    """

    pass
