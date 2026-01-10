"""Unit tests for WitnessSuppressionAttemptError (Story 5.4, FR26).

Tests that the error class correctly enforces FR26 (Constitution Supremacy)
by providing appropriate error messages and attributes.

Constitutional Constraints:
- FR26: Overrides that attempt to suppress witnessing are invalid by definition
- CT-12: Witnessing creates accountability - no unwitnessed actions
"""

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.override import WitnessSuppressionAttemptError


class TestWitnessSuppressionAttemptError:
    """Tests for WitnessSuppressionAttemptError (FR26)."""

    def test_error_message_contains_fr26_reference(self) -> None:
        """FR26: Error message must reference FR26 for traceability."""
        error = WitnessSuppressionAttemptError(scope="witness")

        assert "FR26" in str(error)

    def test_error_message_contains_constitution_supremacy(self) -> None:
        """FR26: Error message must mention constitution supremacy."""
        error = WitnessSuppressionAttemptError(scope="witness")

        assert "Constitution supremacy" in str(error) or "witnessing cannot be suppressed" in str(error)

    def test_error_message_contains_scope(self) -> None:
        """Error message should include the offending scope for debugging."""
        error = WitnessSuppressionAttemptError(scope="witness_pool")

        assert "witness_pool" in str(error)

    def test_error_inherits_from_constitutional_violation(self) -> None:
        """FR26: Error must be a ConstitutionalViolationError."""
        error = WitnessSuppressionAttemptError(scope="witness")

        assert isinstance(error, ConstitutionalViolationError)

    def test_error_stores_scope_attribute(self) -> None:
        """Error should expose scope attribute for programmatic access."""
        error = WitnessSuppressionAttemptError(scope="attestation")

        assert error.scope == "attestation"

    def test_error_with_custom_message(self) -> None:
        """Error should support custom message while preserving scope."""
        custom_msg = "Custom FR26 violation message"
        error = WitnessSuppressionAttemptError(scope="witness", message=custom_msg)

        assert str(error) == custom_msg
        assert error.scope == "witness"

    def test_error_default_message_format(self) -> None:
        """Error default message should follow consistent format."""
        error = WitnessSuppressionAttemptError(scope="witnessing")

        # Default message format: "FR26: Constitution supremacy - witnessing cannot be suppressed (scope: {scope})"
        assert "FR26" in str(error)
        assert "witnessing" in str(error)

    @pytest.mark.parametrize(
        "scope",
        [
            "witness",
            "witnessing",
            "attestation",
            "witness_service",
            "witness_pool",
            "witness.disable",
            "attestation.override",
        ],
    )
    def test_error_works_with_various_forbidden_scopes(self, scope: str) -> None:
        """Error should work consistently with various forbidden scopes."""
        error = WitnessSuppressionAttemptError(scope=scope)

        assert error.scope == scope
        assert "FR26" in str(error)
        assert isinstance(error, ConstitutionalViolationError)
