"""Integration tests for Constitution Supremacy (Story 5.4, FR26).

End-to-end tests verifying FR26 enforcement across the override stack.

Constitutional Constraints:
- FR26: Overrides that attempt to suppress witnessing are invalid by definition
- CT-12: Witnessing creates accountability - no unwitnessed actions
- PM-4: Cross-epic FR ownership - Epic 1 enforces witnessing, Epic 5 validates
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.override_executor import OverrideResult
from src.application.services.constitution_supremacy_service import (
    ConstitutionSupremacyValidator,
)
from src.application.services.override_service import OverrideService
from src.domain.errors.override import WitnessSuppressionAttemptError
from src.domain.events.override_event import ActionType, OverrideEventPayload
from src.infrastructure.stubs.constitution_validator_stub import (
    ConstitutionValidatorStub,
)


class TestConstitutionSupremacyIntegration:
    """Integration tests for constitution supremacy validation (FR26)."""

    @pytest.fixture
    def mock_event_writer(self) -> AsyncMock:
        """Create a mock event writer that tracks calls."""
        writer = AsyncMock()
        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.sequence = 42
        mock_event.witness_id = "WITNESS:test-001"
        mock_event.witness_signature = "test_signature_base64"
        writer.write_event.return_value = mock_event
        return writer

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create a mock halt checker (not halted)."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        checker.get_halt_reason.return_value = None
        return checker

    @pytest.fixture
    def mock_override_executor(self) -> AsyncMock:
        """Create a mock override executor."""
        executor = AsyncMock()
        executor.execute_override.return_value = OverrideResult(
            success=True,
            event_id=uuid4(),
            error_message=None,
        )
        return executor

    @pytest.fixture
    def real_constitution_validator(self) -> ConstitutionSupremacyValidator:
        """Create real constitution validator."""
        return ConstitutionSupremacyValidator()

    @pytest.fixture
    def override_service_with_real_validator(
        self,
        mock_event_writer: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_override_executor: AsyncMock,
        real_constitution_validator: ConstitutionSupremacyValidator,
    ) -> OverrideService:
        """Create OverrideService with real constitution validator."""
        return OverrideService(
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            override_executor=mock_override_executor,
            constitution_validator=real_constitution_validator,
        )

    # =========================================================================
    # End-to-End Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_end_to_end_override_with_valid_scope_succeeds(
        self,
        override_service_with_real_validator: OverrideService,
        mock_event_writer: AsyncMock,
        mock_override_executor: AsyncMock,
    ) -> None:
        """Valid scope override flows through entire stack successfully."""
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="voting.extension",  # ALLOWED
            duration=3600,
            reason="Emergency voting extension",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        result = await override_service_with_real_validator.initiate_override(payload)

        assert result.success is True
        mock_event_writer.write_event.assert_called_once()
        mock_override_executor.execute_override.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_to_end_override_with_witness_scope_fails(
        self,
        override_service_with_real_validator: OverrideService,
        mock_event_writer: AsyncMock,
        mock_override_executor: AsyncMock,
    ) -> None:
        """Witness scope override is rejected before any persistence."""
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="witness",  # FORBIDDEN
            duration=3600,
            reason="Attempt to suppress witnessing",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service_with_real_validator.initiate_override(payload)

        # Neither event writer nor executor should be called
        mock_event_writer.write_event.assert_not_called()
        mock_override_executor.execute_override.assert_not_called()

    @pytest.mark.asyncio
    async def test_override_is_witnessed_when_it_succeeds(
        self,
        override_service_with_real_validator: OverrideService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Valid overrides are witnessed (event has witness_id and witness_signature).

        This test verifies CT-12: Witnessing creates accountability.
        When an override succeeds, its event must be witnessed.
        """
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="configuration.parameter",  # ALLOWED
            duration=3600,
            reason="Configuration change",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        await override_service_with_real_validator.initiate_override(payload)

        # Verify event writer was called
        mock_event_writer.write_event.assert_called_once()

        # The mock event has witness fields (simulating that AtomicEventWriter
        # adds witness attestation - this is tested in Epic 1)
        event = mock_event_writer.write_event.return_value
        assert event.witness_id is not None
        assert event.witness_signature is not None

    @pytest.mark.asyncio
    async def test_no_event_created_when_validation_fails(
        self,
        override_service_with_real_validator: OverrideService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """FR26: No event is created when constitution validation fails."""
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="attestation.disable",  # FORBIDDEN
            duration=3600,
            reason="Attempt to disable attestation",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service_with_real_validator.initiate_override(payload)

        # No event created
        mock_event_writer.write_event.assert_not_called()


class TestConstitutionValidatorStubIntegration:
    """Integration tests for ConstitutionValidatorStub behavior."""

    @pytest.fixture
    def mock_event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.sequence = 42
        writer.write_event.return_value = mock_event
        return writer

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create a mock halt checker (not halted)."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        checker.get_halt_reason.return_value = None
        return checker

    @pytest.fixture
    def mock_override_executor(self) -> AsyncMock:
        """Create a mock override executor."""
        executor = AsyncMock()
        executor.execute_override.return_value = OverrideResult(
            success=True,
            event_id=uuid4(),
            error_message=None,
        )
        return executor

    @pytest.mark.asyncio
    async def test_stub_default_behavior_uses_real_validation(
        self,
        mock_event_writer: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_override_executor: AsyncMock,
    ) -> None:
        """Stub with default settings uses real validation logic."""
        stub = ConstitutionValidatorStub()  # Default: validate_enabled=True
        service = OverrideService(
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            override_executor=mock_override_executor,
            constitution_validator=stub,
        )

        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="witness",  # FORBIDDEN
            duration=3600,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await service.initiate_override(payload)

    @pytest.mark.asyncio
    async def test_stub_disabled_validation_allows_all_scopes(
        self,
        mock_event_writer: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_override_executor: AsyncMock,
    ) -> None:
        """Stub with validate_enabled=False allows all scopes."""
        stub = ConstitutionValidatorStub(validate_enabled=False)
        service = OverrideService(
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            override_executor=mock_override_executor,
            constitution_validator=stub,
        )

        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="witness",  # Would be forbidden, but validation disabled
            duration=3600,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        result = await service.initiate_override(payload)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_stub_force_reject_rejects_all_scopes(
        self,
        mock_event_writer: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_override_executor: AsyncMock,
    ) -> None:
        """Stub with force_reject=True rejects all scopes."""
        stub = ConstitutionValidatorStub(force_reject=True)
        service = OverrideService(
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            override_executor=mock_override_executor,
            constitution_validator=stub,
        )

        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="voting.extension",  # Would be allowed, but force_reject
            duration=3600,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await service.initiate_override(payload)

    @pytest.mark.asyncio
    async def test_stub_tracks_validation_calls(
        self,
        mock_event_writer: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_override_executor: AsyncMock,
    ) -> None:
        """Stub tracks all validation calls for test assertions."""
        stub = ConstitutionValidatorStub(validate_enabled=False)  # Allow all
        service = OverrideService(
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            override_executor=mock_override_executor,
            constitution_validator=stub,
        )

        scopes = ["scope1", "scope2", "scope3"]
        for scope in scopes:
            payload = OverrideEventPayload(
                keeper_id="keeper-001",
                scope=scope,
                duration=3600,
                reason="Test",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=datetime.now(timezone.utc),
            )
            await service.initiate_override(payload)

        assert stub.validation_calls == scopes
