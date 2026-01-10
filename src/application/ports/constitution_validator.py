"""Constitution Validator Port - Abstract interface for constitutional validation (Story 5.4, FR26).

This port defines the contract for validating override commands against
constitutional constraints, specifically FR26 (Constitution Supremacy).

Constitutional Constraints:
- FR26: Overrides that attempt to suppress witnessing are invalid by definition
- CT-12: Witnessing creates accountability - no unwitnessed actions
- PM-4: Cross-epic FR ownership - Epic 1 enforces witnessing, Epic 5 validates

This port enables:
- Dependency inversion for constitution validation
- Testability with mock implementations
- Clear separation between validation logic and override orchestration
"""

from __future__ import annotations

from typing import Protocol


class ConstitutionValidatorProtocol(Protocol):
    """Protocol for constitutional constraint validation (FR26).

    Constitutional Constraint (FR26):
    Overrides that attempt to suppress witnessing are invalid by definition.
    This protocol defines the interface for validating override scopes.

    Implementations MUST:
    - Reject any scope that would suppress witnessing
    - Raise WitnessSuppressionAttemptError for invalid scopes
    - Allow valid scopes to pass without error

    Cross-Epic Requirement (PM-4):
    This validation protects the witnessing guarantees established by
    Epic 1 (AtomicEventWriter) from being bypassed by Epic 5 (Overrides).
    """

    async def validate_override_scope(self, scope: str) -> None:
        """Validate that override scope does not suppress witnessing.

        Constitutional Constraint (FR26):
        This method enforces constitution supremacy by rejecting any
        override scope that would disable or suppress the witnessing
        mechanism.

        Args:
            scope: Override scope to validate. Examples:
                - "voting.extension" - allowed (normal override)
                - "witness" - forbidden (suppresses witnessing)
                - "attestation.disable" - forbidden (suppresses witnessing)

        Raises:
            WitnessSuppressionAttemptError: If scope attempts to suppress
                witnessing. Error message includes "FR26" reference.

        Returns:
            None if scope is valid (does not suppress witnessing).

        Example:
            >>> validator = ConstitutionSupremacyValidator()
            >>> await validator.validate_override_scope("voting.extension")  # OK
            >>> await validator.validate_override_scope("witness")  # Raises!
        """
        ...
