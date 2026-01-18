"""Integration tests for seed validation (Story 6.9, FR124).

Tests SeedValidationService with infrastructure stubs.

Constitutional Constraints:
- FR124: Seed source independence verification
- NFR22: Witness selection randomness SHALL include external entropy
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

import pytest

from src.application.services.seed_validation_service import (
    SeedValidationService,
    ValidatedSeed,
)
from src.domain.errors.topic_manipulation import (
    PredictableSeedError,
    SeedSourceDependenceError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.seed_validation import SeedValidationResult
from src.infrastructure.stubs.entropy_source_stub import EntropySourceStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.seed_validator_stub import SeedValidatorStub


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def validator() -> SeedValidatorStub:
    """Create seed validator stub."""
    return SeedValidatorStub()


@pytest.fixture
def entropy_source() -> EntropySourceStub:
    """Create entropy source stub."""
    return EntropySourceStub()


@pytest.fixture
def service(
    halt_checker: HaltCheckerStub,
    validator: SeedValidatorStub,
    entropy_source: EntropySourceStub,
) -> SeedValidationService:
    """Create seed validation service with stubs."""
    return SeedValidationService(
        halt_checker=halt_checker,
        validator=validator,
        entropy_source=entropy_source,
    )


class TestHaltCheckFirst:
    """Tests for HALT CHECK FIRST pattern (CT-11)."""

    @pytest.mark.asyncio
    async def test_validate_and_get_seed_halted(
        self,
        service: SeedValidationService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that validate_and_get_seed raises when halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.validate_and_get_seed("witness_selection")

    @pytest.mark.asyncio
    async def test_get_seed_audit_trail_halted(
        self,
        service: SeedValidationService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that get_seed_audit_trail raises when halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.get_seed_audit_trail()


class TestSeedValidation:
    """Tests for seed validation (AC4, FR124)."""

    @pytest.mark.asyncio
    async def test_successful_validation(
        self,
        service: SeedValidationService,
    ) -> None:
        """Test successful seed validation."""
        result = await service.validate_and_get_seed("witness_selection")

        assert isinstance(result, ValidatedSeed)
        assert result.seed_bytes is not None
        assert len(result.seed_bytes) > 0
        assert result.seed_hash is not None
        assert result.validation_id is not None
        assert result.validation_event.validation_result == SeedValidationResult.VALID
        assert result.validation_event.independence_verified is True

    @pytest.mark.asyncio
    async def test_validation_event_includes_purpose(
        self,
        service: SeedValidationService,
    ) -> None:
        """Test validation event includes purpose."""
        result = await service.validate_and_get_seed("deliberation_selection")

        assert result.validation_event.seed_purpose == "deliberation_selection"

    @pytest.mark.asyncio
    async def test_validation_records_usage(
        self,
        service: SeedValidationService,
        validator: SeedValidatorStub,
    ) -> None:
        """Test validation records seed usage for audit trail."""
        await service.validate_and_get_seed("test_purpose")

        # Check usage was recorded
        records = await service.get_seed_audit_trail()
        assert len(records) >= 1


class TestSourceIndependence:
    """Tests for source independence verification (FR124)."""

    @pytest.mark.asyncio
    async def test_rejects_dependent_source(
        self,
        service: SeedValidationService,
        validator: SeedValidatorStub,
        entropy_source: EntropySourceStub,
    ) -> None:
        """Test rejection when source fails independence check."""
        # Configure validator to reject the source
        source_id = await entropy_source.get_source_identifier()
        validator.set_source_independent(source_id, False)

        with pytest.raises(SeedSourceDependenceError) as exc_info:
            await service.validate_and_get_seed("witness_selection")

        assert exc_info.value.seed_purpose == "witness_selection"
        assert exc_info.value.failed_source == source_id

    @pytest.mark.asyncio
    async def test_accepts_independent_source(
        self,
        service: SeedValidationService,
        validator: SeedValidatorStub,
        entropy_source: EntropySourceStub,
    ) -> None:
        """Test acceptance when source passes independence check."""
        # Default stub marks all sources as independent
        source_id = await entropy_source.get_source_identifier()
        validator.set_source_independent(source_id, True)

        result = await service.validate_and_get_seed("witness_selection")

        assert result.source_id == source_id
        assert result.validation_event.independence_verified is True


class TestPredictabilityCheck:
    """Tests for seed predictability detection (AC4)."""

    @pytest.mark.asyncio
    async def test_rejects_predictable_seed(
        self,
        service: SeedValidationService,
        validator: SeedValidatorStub,
    ) -> None:
        """Test rejection when seed appears predictable."""
        # Configure validator to mark all seeds as predictable by default
        validator.set_default_predictability(True)

        with pytest.raises(PredictableSeedError) as exc_info:
            await service.validate_and_get_seed("witness_selection")

        assert exc_info.value.seed_purpose == "witness_selection"

    @pytest.mark.asyncio
    async def test_accepts_unpredictable_seed(
        self,
        service: SeedValidationService,
        validator: SeedValidatorStub,
    ) -> None:
        """Test acceptance when seed is not predictable."""
        # Default stub marks seeds as not predictable
        validator.set_default_predictability(False)

        result = await service.validate_and_get_seed("witness_selection")

        assert result.validation_event.validation_result == SeedValidationResult.VALID


class TestAuditTrail:
    """Tests for seed usage audit trail (CT-12)."""

    @pytest.mark.asyncio
    async def test_audit_trail_recorded(
        self,
        service: SeedValidationService,
    ) -> None:
        """Test that seed usage is recorded for audit trail."""
        await service.validate_and_get_seed("audit_test")

        records = await service.get_seed_audit_trail()
        assert len(records) >= 1

    @pytest.mark.asyncio
    async def test_audit_trail_filter_by_purpose(
        self,
        service: SeedValidationService,
    ) -> None:
        """Test filtering audit trail by purpose."""
        # Generate seeds with different purposes
        await service.validate_and_get_seed("purpose_a")
        await service.validate_and_get_seed("purpose_b")
        await service.validate_and_get_seed("purpose_a")

        records = await service.get_seed_audit_trail(purpose="purpose_a")
        assert len(records) >= 2
        for record in records:
            assert record.purpose == "purpose_a"

    @pytest.mark.asyncio
    async def test_audit_trail_respects_limit(
        self,
        service: SeedValidationService,
    ) -> None:
        """Test audit trail respects limit parameter."""
        # Generate multiple seeds
        for i in range(5):
            await service.validate_and_get_seed(f"limit_test_{i}")

        records = await service.get_seed_audit_trail(limit=3)
        assert len(records) <= 3


class TestServiceDependencyValidation:
    """Tests for service initialization validation."""

    def test_requires_halt_checker(
        self,
        validator: SeedValidatorStub,
        entropy_source: EntropySourceStub,
    ) -> None:
        """Test service requires halt_checker dependency."""
        with pytest.raises(TypeError) as exc_info:
            SeedValidationService(
                halt_checker=None,  # type: ignore
                validator=validator,
                entropy_source=entropy_source,
            )
        assert "halt_checker is required" in str(exc_info.value)

    def test_requires_validator(
        self,
        halt_checker: HaltCheckerStub,
        entropy_source: EntropySourceStub,
    ) -> None:
        """Test service requires validator dependency."""
        with pytest.raises(TypeError) as exc_info:
            SeedValidationService(
                halt_checker=halt_checker,
                validator=None,  # type: ignore
                entropy_source=entropy_source,
            )
        assert "validator is required" in str(exc_info.value)

    def test_requires_entropy_source(
        self,
        halt_checker: HaltCheckerStub,
        validator: SeedValidatorStub,
    ) -> None:
        """Test service requires entropy_source dependency."""
        with pytest.raises(TypeError) as exc_info:
            SeedValidationService(
                halt_checker=halt_checker,
                validator=validator,
                entropy_source=None,  # type: ignore
            )
        assert "entropy_source is required" in str(exc_info.value)


class TestEndToEndScenarios:
    """End-to-end integration scenarios."""

    @pytest.mark.asyncio
    async def test_witness_selection_seed_flow(
        self,
        service: SeedValidationService,
        entropy_source: EntropySourceStub,
    ) -> None:
        """Test complete flow for witness selection seed.

        Scenario: System needs a seed for witness selection.

        Expected behavior:
        1. Get entropy from external source
        2. Verify source independence
        3. Check for predictability
        4. Return validated seed with audit trail
        """
        # Get seed for witness selection
        result = await service.validate_and_get_seed("witness_selection")

        # Verify result structure
        assert result.seed_bytes is not None
        assert len(result.seed_bytes) == 32  # Standard entropy size
        assert result.seed_hash is not None
        assert len(result.seed_hash) == 64  # SHA256 hex

        # Verify source is recorded
        source_id = await entropy_source.get_source_identifier()
        assert result.source_id == source_id

        # Verify event is properly formed
        event = result.validation_event
        assert event.seed_purpose == "witness_selection"
        assert event.entropy_source_id == source_id
        assert event.independence_verified is True
        assert event.validation_result == SeedValidationResult.VALID

        # Verify audit trail
        records = await service.get_seed_audit_trail()
        assert any(r.purpose == "witness_selection" for r in records)

    @pytest.mark.asyncio
    async def test_multiple_seed_requests_all_validated(
        self,
        service: SeedValidationService,
    ) -> None:
        """Test multiple seed requests all get validated successfully.

        Note: The stub returns the same entropy bytes for simplicity.
        In production, each call would return unique bytes.
        """
        validation_ids = []
        for i in range(5):
            result = await service.validate_and_get_seed(f"uniqueness_test_{i}")
            validation_ids.append(result.validation_id)

        # Each validation should have a unique ID
        assert len(set(validation_ids)) == len(validation_ids), (
            "Validation IDs should be unique"
        )

    @pytest.mark.asyncio
    async def test_attack_detection_scenario(
        self,
        service: SeedValidationService,
        validator: SeedValidatorStub,
        entropy_source: EntropySourceStub,
    ) -> None:
        """Test defense against compromised entropy source.

        Scenario: Attacker compromises the entropy source to
        produce predictable seeds.

        Expected defense:
        1. Independence check should catch compromised source
        2. Predictability check should catch low-entropy seeds
        """
        # Case 1: Source fails independence check
        source_id = await entropy_source.get_source_identifier()
        validator.set_source_independent(source_id, False)

        with pytest.raises(SeedSourceDependenceError):
            await service.validate_and_get_seed("attacked_selection")

        # Reset source independence for case 2
        validator.set_source_independent(source_id, True)

        # Case 2: Seed appears predictable
        validator.set_default_predictability(True)

        with pytest.raises(PredictableSeedError):
            await service.validate_and_get_seed("attacked_selection")
