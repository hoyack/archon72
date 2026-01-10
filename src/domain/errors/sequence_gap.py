"""Sequence gap domain errors (FR18-FR19, Story 3.7).

This module provides exception classes for sequence gap detection scenarios.
Sequence gaps indicate potential integrity violations that require investigation.

Constitutional Constraints:
- FR18: Gap detection within 1 minute
- FR19: Gap triggers investigation, not auto-fill
- CT-3: Time is unreliable - sequence is authoritative ordering
- CT-11: Silent failure destroys legitimacy - gaps MUST be reported

Note:
    Sequence gaps may indicate:
    - Event suppression by attacker
    - Data loss or corruption
    - Replication failure
    - System failure during write

    Gaps are NEVER auto-filled. Manual investigation required.
"""

from src.domain.exceptions import ConclaveError


class SequenceGapDetectedError(ConclaveError):
    """Raised when sequence gap is detected (FR18-FR19).

    A sequence gap indicates a potential integrity violation.
    The error message includes gap details for investigation.

    Attributes:
        expected: The sequence number that was expected.
        actual: The sequence number that was found.
        missing: Tuple of missing sequence numbers.

    Example:
        >>> raise SequenceGapDetectedError(
        ...     expected=5,
        ...     actual=10,
        ...     missing=(5, 6, 7, 8, 9),
        ... )
    """

    def __init__(
        self,
        expected: int,
        actual: int,
        missing: tuple[int, ...],
    ) -> None:
        """Initialize the sequence gap error.

        Args:
            expected: The sequence number that was expected.
            actual: The sequence number that was found.
            missing: Tuple of missing sequence numbers.
        """
        self.expected = expected
        self.actual = actual
        self.missing = missing
        super().__init__(
            f"FR18: Sequence gap detected. "
            f"Expected {expected}, found {actual}. "
            f"Missing: {missing}"
        )


class SequenceGapResolutionRequiredError(ConclaveError):
    """Raised when attempting to auto-fill sequence gaps (FR19).

    Sequence gaps require manual investigation and resolution.
    Auto-fill is constitutionally prohibited as it could mask
    tampering or data loss.

    Constitutional Constraint (FR19):
        Gap detection SHALL trigger further investigation.
        Gaps are NOT auto-filled - manual resolution required.

    Example:
        >>> raise SequenceGapResolutionRequiredError(
        ...     "FR19: Auto-fill prohibited - manual investigation required"
        ... )
    """

    pass
