"""Constitution Validator Stub for testing and development (Story 5.4, FR26).

This stub provides a configurable implementation of ConstitutionValidatorProtocol
for use in testing and development environments.

WARNING: This stub is NOT for production use.
Production should use ConstitutionSupremacyValidator from
src/application/services/constitution_supremacy_service.py.

Usage:
    # Default behavior: uses real validation logic
    validator = ConstitutionValidatorStub()

    # Disable validation for specific tests
    validator = ConstitutionValidatorStub(validate_enabled=False)

    # Force all validations to fail
    validator = ConstitutionValidatorStub(force_reject=True)
"""

from __future__ import annotations

from src.application.ports.constitution_validator import ConstitutionValidatorProtocol
from src.domain.errors.override import WitnessSuppressionAttemptError
from src.domain.models.override_reason import is_witness_suppression_scope


class ConstitutionValidatorStub(ConstitutionValidatorProtocol):
    """Stub implementation of ConstitutionValidatorProtocol for testing (FR26).

    This stub provides configurable behavior for testing:
    - Default: uses real validation logic (same as production)
    - validate_enabled=False: allows all scopes (for testing non-FR26 scenarios)
    - force_reject=True: rejects all scopes (for testing rejection handling)

    Thread Safety:
        This stub is stateless and thread-safe.

    Attributes:
        validate_enabled: Whether to perform real validation.
        force_reject: Whether to reject all scopes regardless of content.
        validation_calls: List of scopes that were validated (for test assertions).
    """

    def __init__(
        self,
        validate_enabled: bool = True,
        force_reject: bool = False,
    ) -> None:
        """Initialize the Constitution Validator Stub.

        Args:
            validate_enabled: If True (default), uses real validation logic.
                If False, allows all scopes to pass.
            force_reject: If True, rejects all scopes regardless of content.
                Takes precedence over validate_enabled.
        """
        self._validate_enabled = validate_enabled
        self._force_reject = force_reject
        self._validation_calls: list[str] = []

    async def validate_override_scope(self, scope: str) -> None:
        """Validate that override scope does not suppress witnessing.

        Stub behavior:
        1. If force_reject=True, always raises WitnessSuppressionAttemptError
        2. If validate_enabled=False, always passes (no validation)
        3. Otherwise, uses real validation logic

        Args:
            scope: Override scope to validate.

        Raises:
            WitnessSuppressionAttemptError: If scope is forbidden
                (when validate_enabled=True or force_reject=True).
        """
        # Track all validation calls for test assertions
        self._validation_calls.append(scope)

        # Force reject all scopes (for testing rejection handling)
        if self._force_reject:
            raise WitnessSuppressionAttemptError(
                scope=scope,
                message="FR26: Constitution supremacy - witnessing cannot be suppressed",
            )

        # Skip validation if disabled (for testing non-FR26 scenarios)
        if not self._validate_enabled:
            return

        # Use real validation logic (default behavior)
        if is_witness_suppression_scope(scope):
            raise WitnessSuppressionAttemptError(
                scope=scope,
                message="FR26: Constitution supremacy - witnessing cannot be suppressed",
            )

    @property
    def validation_calls(self) -> list[str]:
        """Get list of scopes that were validated.

        Useful for test assertions to verify validation was called.

        Returns:
            List of scope strings that were passed to validate_override_scope.
        """
        return self._validation_calls.copy()

    def reset(self) -> None:
        """Reset stub state for test isolation.

        Clears the validation_calls list.
        """
        self._validation_calls.clear()
