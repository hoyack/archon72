"""Unit tests for ConstitutionSupremacyValidator service (Story 5.4, FR26).

Tests that the service correctly validates override scopes against
FR26 (Constitution Supremacy) requirements.

Constitutional Constraints:
- FR26: Overrides that attempt to suppress witnessing are invalid by definition
- CT-12: Witnessing creates accountability - no unwitnessed actions
- PM-4: Cross-epic FR ownership - Epic 1 enforces witnessing, Epic 5 validates
"""

import pytest

from src.application.services.constitution_supremacy_service import (
    ConstitutionSupremacyValidator,
)
from src.domain.errors.override import WitnessSuppressionAttemptError


class TestConstitutionSupremacyValidator:
    """Tests for ConstitutionSupremacyValidator service (FR26)."""

    @pytest.fixture
    def validator(self) -> ConstitutionSupremacyValidator:
        """Create a validator instance for testing."""
        return ConstitutionSupremacyValidator()

    # =========================================================================
    # Valid scopes - should pass without error
    # =========================================================================

    @pytest.mark.asyncio
    async def test_valid_scope_passes_without_error(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """Valid scopes should pass validation without raising error."""
        # Should not raise - valid scope
        await validator.validate_override_scope("voting.extension")

    @pytest.mark.asyncio
    async def test_ceremony_scope_passes(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """Ceremony scope should pass validation."""
        await validator.validate_override_scope("ceremony.health")

    @pytest.mark.asyncio
    async def test_configuration_scope_passes(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """Configuration scope should pass validation."""
        await validator.validate_override_scope("configuration")

    @pytest.mark.asyncio
    async def test_halt_scope_passes(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """Halt scope should pass validation."""
        await validator.validate_override_scope("halt.clear")

    # =========================================================================
    # Forbidden scopes - should raise WitnessSuppressionAttemptError
    # =========================================================================

    @pytest.mark.asyncio
    async def test_witness_scope_raises_error(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: 'witness' scope must raise WitnessSuppressionAttemptError."""
        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await validator.validate_override_scope("witness")

        assert "FR26" in str(exc_info.value)
        assert exc_info.value.scope == "witness"

    @pytest.mark.asyncio
    async def test_witnessing_scope_raises_error(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: 'witnessing' scope must raise WitnessSuppressionAttemptError."""
        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await validator.validate_override_scope("witnessing")

        assert "FR26" in str(exc_info.value)
        assert "witnessing cannot be suppressed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_attestation_scope_raises_error(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: 'attestation' scope must raise WitnessSuppressionAttemptError."""
        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await validator.validate_override_scope("attestation")

        assert "FR26" in str(exc_info.value)
        assert exc_info.value.scope == "attestation"

    @pytest.mark.asyncio
    async def test_witness_service_scope_raises_error(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: 'witness_service' scope must raise WitnessSuppressionAttemptError."""
        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await validator.validate_override_scope("witness_service")

        assert exc_info.value.scope == "witness_service"

    @pytest.mark.asyncio
    async def test_witness_pool_scope_raises_error(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: 'witness_pool' scope must raise WitnessSuppressionAttemptError."""
        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await validator.validate_override_scope("witness_pool")

        assert exc_info.value.scope == "witness_pool"

    @pytest.mark.asyncio
    async def test_witness_pattern_scope_raises_error(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: 'witness.disable' pattern must raise WitnessSuppressionAttemptError."""
        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await validator.validate_override_scope("witness.disable")

        assert exc_info.value.scope == "witness.disable"

    @pytest.mark.asyncio
    async def test_attestation_pattern_scope_raises_error(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: 'attestation.override' pattern must raise WitnessSuppressionAttemptError."""
        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await validator.validate_override_scope("attestation.override")

        assert exc_info.value.scope == "attestation.override"

    # =========================================================================
    # Error message validation
    # =========================================================================

    @pytest.mark.asyncio
    async def test_error_message_contains_fr26(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: Error message must contain FR26 reference."""
        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await validator.validate_override_scope("witness")

        assert "FR26" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_message_contains_constitution_supremacy(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: Error message must mention constitution supremacy."""
        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await validator.validate_override_scope("witness")

        assert "Constitution supremacy" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_message_contains_witnessing_cannot_be_suppressed(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: Error message must state witnessing cannot be suppressed."""
        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await validator.validate_override_scope("witness")

        assert "witnessing cannot be suppressed" in str(exc_info.value)

    # =========================================================================
    # Case insensitivity tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_uppercase_scope_raises_error(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: Validation should be case-insensitive."""
        with pytest.raises(WitnessSuppressionAttemptError):
            await validator.validate_override_scope("WITNESS")

    @pytest.mark.asyncio
    async def test_mixed_case_scope_raises_error(
        self, validator: ConstitutionSupremacyValidator
    ) -> None:
        """FR26: Validation should be case-insensitive."""
        with pytest.raises(WitnessSuppressionAttemptError):
            await validator.validate_override_scope("Witnessing")

    # =========================================================================
    # Parametrized tests
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scope",
        [
            "witness",
            "witnessing",
            "attestation",
            "witness_service",
            "witness_pool",
            "witness.disable",
            "witness.override",
            "attestation.disable",
            "attestation.suppress",
        ],
    )
    async def test_forbidden_scopes_all_raise_error(
        self, validator: ConstitutionSupremacyValidator, scope: str
    ) -> None:
        """FR26: All forbidden scopes must raise WitnessSuppressionAttemptError."""
        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await validator.validate_override_scope(scope)

        assert "FR26" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scope",
        [
            "voting.extension",
            "ceremony.health",
            "configuration",
            "halt.clear",
            "emergency",
            "agent.restart",
            "deliberation.extend",
        ],
    )
    async def test_allowed_scopes_all_pass(
        self, validator: ConstitutionSupremacyValidator, scope: str
    ) -> None:
        """Valid business scopes should pass without error."""
        # Should not raise
        await validator.validate_override_scope(scope)
