"""PM-4 Mandatory Integration Tests: Witness Suppression Override Rejection (Story 5.4, FR26).

This is the PM-4 mandated integration test file that verifies FR26
(Constitution Supremacy - No Witness Suppression) is enforced.

Constitutional Constraints:
- FR26: Overrides that attempt to suppress witnessing are invalid by definition
- CT-12: Witnessing creates accountability - no unwitnessed actions
- PM-4: Cross-epic FR ownership - Epic 1 enforces witnessing, Epic 5 validates

This test file MUST exist and MUST pass for Story 5.4 acceptance (AC3).
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


class TestSuppressWitnessOverride:
    """PM-4: Mandatory integration tests for FR26 witness suppression rejection.

    These tests verify that the system correctly rejects override attempts
    that would suppress witnessing, enforcing FR26 (Constitution Supremacy).
    """

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

    @pytest.fixture
    def constitution_validator(self) -> ConstitutionSupremacyValidator:
        """Create real constitution validator (not a stub)."""
        return ConstitutionSupremacyValidator()

    @pytest.fixture
    def override_service(
        self,
        mock_event_writer: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_override_executor: AsyncMock,
        constitution_validator: ConstitutionSupremacyValidator,
    ) -> OverrideService:
        """Create OverrideService with real constitution validator."""
        return OverrideService(
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            override_executor=mock_override_executor,
            constitution_validator=constitution_validator,
        )

    @pytest.fixture
    def valid_keeper_id(self) -> str:
        """Return a valid keeper ID for testing."""
        return "keeper-001"

    # =========================================================================
    # PM-4 Mandatory Tests - MUST PASS for Story 5.4 Acceptance
    # =========================================================================

    @pytest.mark.asyncio
    async def test_suppress_witness_override_rejected(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
    ) -> None:
        """PM-4/FR26: Override attempting to suppress witnessing is rejected.

        This is the primary test required by PM-4 to verify FR26 enforcement.
        """
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="witness",  # FORBIDDEN - attempts to suppress witnessing
            duration=3600,
            reason="Emergency test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await override_service.initiate_override(payload)

        # Verify FR26 is referenced in error
        assert "FR26" in str(exc_info.value)
        assert "Constitution supremacy" in str(exc_info.value)
        assert "witnessing cannot be suppressed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_witness_scope_override_rejected_with_fr26_message(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
    ) -> None:
        """FR26: Error message must explicitly reference FR26 for traceability."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="witness",
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await override_service.initiate_override(payload)

        error_message = str(exc_info.value)
        assert "FR26" in error_message, "Error must reference FR26"

    @pytest.mark.asyncio
    async def test_witnessing_scope_override_rejected(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
    ) -> None:
        """FR26: 'witnessing' scope must be rejected."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="witnessing",  # FORBIDDEN
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service.initiate_override(payload)

    @pytest.mark.asyncio
    async def test_attestation_scope_override_rejected(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
    ) -> None:
        """FR26: 'attestation' scope must be rejected."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="attestation",  # FORBIDDEN
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service.initiate_override(payload)

    # =========================================================================
    # Additional FR26 Validation Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_witness_service_scope_rejected(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
    ) -> None:
        """FR26: 'witness_service' scope must be rejected."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="witness_service",
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service.initiate_override(payload)

    @pytest.mark.asyncio
    async def test_witness_pool_scope_rejected(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
    ) -> None:
        """FR26: 'witness_pool' scope must be rejected."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="witness_pool",
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service.initiate_override(payload)

    @pytest.mark.asyncio
    async def test_witness_pattern_scope_rejected(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
    ) -> None:
        """FR26: 'witness.*' pattern scopes must be rejected."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="witness.disable",  # Pattern match
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service.initiate_override(payload)

    @pytest.mark.asyncio
    async def test_attestation_pattern_scope_rejected(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
    ) -> None:
        """FR26: 'attestation.*' pattern scopes must be rejected."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="attestation.override",  # Pattern match
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service.initiate_override(payload)

    @pytest.mark.asyncio
    async def test_valid_scope_succeeds(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Valid business scopes should succeed (FR26 allows non-witness scopes)."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="voting.extension",  # ALLOWED - normal business scope
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        result = await override_service.initiate_override(payload)

        assert result.success is True
        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejection_prevents_event_logging(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
        mock_event_writer: AsyncMock,
    ) -> None:
        """FR26: Rejected overrides must NOT be logged to event store."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="witness",
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service.initiate_override(payload)

        # Event writer should NOT have been called
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejection_prevents_execution(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
        mock_override_executor: AsyncMock,
    ) -> None:
        """FR26: Rejected overrides must NOT be executed."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope="witness",
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service.initiate_override(payload)

        # Override executor should NOT have been called
        mock_override_executor.execute_override.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "forbidden_scope",
        [
            "witness",
            "witnessing",
            "attestation",
            "witness_service",
            "witness_pool",
            "witness.disable",
            "witness.override",
            "attestation.suppress",
            "attestation.disable",
        ],
    )
    async def test_all_forbidden_scopes_rejected(
        self,
        override_service: OverrideService,
        valid_keeper_id: str,
        forbidden_scope: str,
    ) -> None:
        """FR26: All forbidden scopes must be rejected with WitnessSuppressionAttemptError."""
        payload = OverrideEventPayload(
            keeper_id=valid_keeper_id,
            scope=forbidden_scope,
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await override_service.initiate_override(payload)

        assert "FR26" in str(exc_info.value)
