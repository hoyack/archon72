"""Errors for Knight witness domain.

Story: consent-gov-6-1: Knight Witness Domain Model

This module defines error types specific to witness statement
creation and validation.

References:
    - AC3: Witness statements are observation only, no judgment
    - AC4: Statements cannot be suppressed by any role
    - AC8: No interpretation or recommendation in statement
"""

from __future__ import annotations


class JudgmentLanguageError(ValueError):
    """Raised when witness statement contains judgment language.

    Knight statements must be observation-only (FR34). This error
    is raised when the WitnessStatementFactory detects language
    that implies judgment rather than observation.

    Examples of judgment language:
        - "should", "must" (recommendation)
        - "violated", "guilty", "innocent" (determination)
        - "severe", "minor", "critical" (severity)
        - "recommend", "suggests" (advice)
        - "remedy", "punishment" (prescription)

    Example:
        >>> factory.create_statement(
        ...     what="This should not have happened",  # "should" = judgment
        ...     ...
        ... )
        JudgmentLanguageError: Statement contains judgment indicator 'should'.
        Knight statements must be observation-only.
    """

    pass
