"""Integration tests for Keeper availability attestation (Story 5.8).

Tests end-to-end flows for:
- AC1: Weekly attestation events logged with Keeper attribution (FR77, FR78)
- AC2: KeeperQuorumWarningEvent if quorum = 3 (SR-7)
- AC3: System halt if quorum < 3 (FR79)
- AC4: 2 missed attestations triggers replacement process (FR78)

Constitutional Constraints:
- FR77: Unanimous agreement within 72h or cessation begins
- FR78: Weekly attestation, 2 missed triggers replacement
- FR79: Minimum 3 Keepers, system halts if below
- SR-7: Alert when quorum drops to exactly 3
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.keeper_availability_service import (
    KeeperAvailabilityService,
)
from src.domain.errors.keeper_availability import (
    KeeperQuorumViolationError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.keeper_availability import (
    KEEPER_ATTESTATION_EVENT_TYPE,
    KEEPER_QUORUM_WARNING_EVENT_TYPE,
)
from src.domain.models.keeper_attestation import (
    MINIMUM_KEEPER_QUORUM,
    MISSED_ATTESTATIONS_THRESHOLD,
    get_current_period,
)
from src.infrastructure.stubs.keeper_availability_stub import KeeperAvailabilityStub


class TestAC1WeeklyAttestationEvents:
    """AC1: KeeperAttestationEvent logged with Keeper attribution (FR77, FR78)."""

    @pytest.fixture
    def service_with_mocks(
        self,
    ) -> tuple[
        KeeperAvailabilityService,
        KeeperAvailabilityStub,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        availability = KeeperAvailabilityStub()
        mock_signature_service = MagicMock()
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)
        mock_halt_trigger = AsyncMock()

        service = KeeperAvailabilityService(
            availability=availability,
            signature_service=mock_signature_service,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            halt_trigger=mock_halt_trigger,
        )

        return service, availability, mock_event_writer

    @pytest.mark.asyncio
    async def test_attestation_event_logged_with_keeper_attribution(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
        ],
    ) -> None:
        """Test that attestation creates event with Keeper as agent_id (FR77)."""
        service, availability, mock_event_writer = service_with_mocks

        keeper_id = "KEEPER:alice"
        signature = b"x" * 64

        await availability.add_keeper(keeper_id)

        # Submit attestation
        await service.submit_attestation(keeper_id, signature)

        # Verify event was written with correct attribution
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs

        assert call_kwargs["event_type"] == KEEPER_ATTESTATION_EVENT_TYPE
        assert call_kwargs["agent_id"] == keeper_id  # Keeper attribution (FR77)

        # Verify payload contains correct data
        payload = call_kwargs["payload"]
        assert payload["keeper_id"] == keeper_id

    @pytest.mark.asyncio
    async def test_attestation_event_includes_period_boundaries(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
        ],
    ) -> None:
        """Test that attestation event includes period start/end (FR78)."""
        service, availability, mock_event_writer = service_with_mocks

        keeper_id = "KEEPER:bob"
        await availability.add_keeper(keeper_id)

        period_start, period_end = get_current_period()

        await service.submit_attestation(keeper_id, b"x" * 64)

        payload = mock_event_writer.write_event.call_args.kwargs["payload"]

        # Period boundaries should match current period
        assert payload["attestation_period_start"] == period_start.isoformat()
        assert payload["attestation_period_end"] == period_end.isoformat()


class TestAC2QuorumWarningEvent:
    """AC2: KeeperQuorumWarningEvent if quorum = 3 (SR-7)."""

    @pytest.fixture
    def service_with_mocks(
        self,
    ) -> tuple[
        KeeperAvailabilityService,
        KeeperAvailabilityStub,
        AsyncMock,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        availability = KeeperAvailabilityStub()
        mock_signature_service = MagicMock()
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)
        mock_halt_trigger = AsyncMock()
        mock_halt_trigger.trigger_halt = AsyncMock()

        service = KeeperAvailabilityService(
            availability=availability,
            signature_service=mock_signature_service,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            halt_trigger=mock_halt_trigger,
        )

        return service, availability, mock_event_writer, mock_halt_trigger

    @pytest.mark.asyncio
    async def test_quorum_warning_event_at_minimum_threshold(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test warning event when quorum drops to exactly 3 (SR-7)."""
        service, availability, mock_event_writer, _ = service_with_mocks

        # Add exactly 3 Keepers (minimum threshold)
        for name in ["alice", "bob", "charlie"]:
            await availability.add_keeper(f"KEEPER:{name}")

        # Check quorum should trigger warning
        await service.check_keeper_quorum()

        # Should write warning event
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs

        assert call_kwargs["event_type"] == KEEPER_QUORUM_WARNING_EVENT_TYPE
        assert call_kwargs["payload"]["current_count"] == 3
        assert call_kwargs["payload"]["minimum_required"] == MINIMUM_KEEPER_QUORUM

    @pytest.mark.asyncio
    async def test_no_warning_when_quorum_healthy(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test no warning event when quorum is above minimum (SR-7)."""
        service, availability, mock_event_writer, _ = service_with_mocks

        # Add 4 Keepers (above minimum)
        for name in ["alice", "bob", "charlie", "dave"]:
            await availability.add_keeper(f"KEEPER:{name}")

        await service.check_keeper_quorum()

        # Should NOT write any event
        mock_event_writer.write_event.assert_not_called()


class TestAC3SystemHaltOnQuorumViolation:
    """AC3: System halt if quorum < 3 (FR79)."""

    @pytest.fixture
    def service_with_mocks(
        self,
    ) -> tuple[
        KeeperAvailabilityService,
        KeeperAvailabilityStub,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        availability = KeeperAvailabilityStub()
        mock_signature_service = MagicMock()
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)
        mock_halt_trigger = AsyncMock()
        mock_halt_trigger.trigger_halt = AsyncMock()

        service = KeeperAvailabilityService(
            availability=availability,
            signature_service=mock_signature_service,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            halt_trigger=mock_halt_trigger,
        )

        return service, availability, mock_halt_trigger

    @pytest.mark.asyncio
    async def test_halt_triggered_when_quorum_below_minimum(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
        ],
    ) -> None:
        """Test system halt triggered when quorum < 3 (FR79)."""
        service, availability, mock_halt_trigger = service_with_mocks

        # Add only 2 Keepers (below minimum of 3)
        await availability.add_keeper("KEEPER:alice")
        await availability.add_keeper("KEEPER:bob")

        # Check quorum should trigger halt
        with pytest.raises(KeeperQuorumViolationError) as exc_info:
            await service.check_keeper_quorum()

        # Verify halt was triggered
        mock_halt_trigger.trigger_halt.assert_called_once()
        call_kwargs = mock_halt_trigger.trigger_halt.call_args.kwargs

        assert "FR79" in call_kwargs["reason"]
        assert "Keeper quorum below minimum" in call_kwargs["reason"]
        assert "FR79" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_halt_triggered_when_no_keepers(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
        ],
    ) -> None:
        """Test system halt triggered when no Keepers registered (FR79)."""
        service, _, mock_halt_trigger = service_with_mocks

        # No Keepers added
        with pytest.raises(KeeperQuorumViolationError):
            await service.check_keeper_quorum()

        mock_halt_trigger.trigger_halt.assert_called_once()


class TestAC4ReplacementProcessOnMissedAttestations:
    """AC4: 2 missed attestations triggers replacement process (FR78)."""

    @pytest.fixture
    def service_with_mocks(
        self,
    ) -> tuple[
        KeeperAvailabilityService,
        KeeperAvailabilityStub,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        availability = KeeperAvailabilityStub()
        mock_signature_service = MagicMock()
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)
        mock_halt_trigger = AsyncMock()
        mock_halt_trigger.trigger_halt = AsyncMock()

        service = KeeperAvailabilityService(
            availability=availability,
            signature_service=mock_signature_service,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            halt_trigger=mock_halt_trigger,
        )

        return service, availability, mock_event_writer

    @pytest.mark.asyncio
    async def test_missed_attestation_increments_count(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
        ],
    ) -> None:
        """Test that missed attestation increments consecutive count (FR78)."""
        _, availability, _ = service_with_mocks

        keeper_id = "KEEPER:bob"
        await availability.add_keeper(keeper_id)

        # Simulate missing an attestation
        new_count = await availability.increment_missed_attestations(keeper_id)
        assert new_count == 1

        new_count = await availability.increment_missed_attestations(keeper_id)
        assert new_count == 2

    @pytest.mark.asyncio
    async def test_replacement_triggered_after_threshold_misses(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
        ],
    ) -> None:
        """Test replacement process triggered after 2 missed attestations (FR78)."""
        _, availability, _ = service_with_mocks

        keeper_id = "KEEPER:charlie"
        await availability.add_keeper(keeper_id)

        # Miss 2 consecutive attestations (threshold)
        await availability.increment_missed_attestations(keeper_id)
        await availability.increment_missed_attestations(keeper_id)

        count = await availability.get_missed_attestations_count(keeper_id)
        assert count == MISSED_ATTESTATIONS_THRESHOLD

        # Mark for replacement
        await availability.mark_keeper_for_replacement(
            keeper_id, "FR78: Missed 2 consecutive attestations"
        )

        pending = await availability.get_keepers_pending_replacement()
        assert keeper_id in pending

    @pytest.mark.asyncio
    async def test_successful_attestation_resets_missed_count(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
        ],
    ) -> None:
        """Test that successful attestation resets missed count to 0 (FR78)."""
        service, availability, _ = service_with_mocks

        keeper_id = "KEEPER:dave"
        await availability.add_keeper(keeper_id)

        # Miss 1 attestation
        await availability.increment_missed_attestations(keeper_id)
        assert await availability.get_missed_attestations_count(keeper_id) == 1

        # Submit successful attestation
        await service.submit_attestation(keeper_id, b"x" * 64)

        # Missed count should be reset
        assert await availability.get_missed_attestations_count(keeper_id) == 0


class TestEndToEndScenarios:
    """End-to-end scenario tests."""

    @pytest.fixture
    def service_with_mocks(
        self,
    ) -> tuple[
        KeeperAvailabilityService,
        KeeperAvailabilityStub,
        AsyncMock,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        availability = KeeperAvailabilityStub()
        mock_signature_service = MagicMock()
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)
        mock_halt_trigger = AsyncMock()
        mock_halt_trigger.trigger_halt = AsyncMock()

        service = KeeperAvailabilityService(
            availability=availability,
            signature_service=mock_signature_service,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            halt_trigger=mock_halt_trigger,
        )

        return service, availability, mock_event_writer, mock_halt_trigger

    @pytest.mark.asyncio
    async def test_full_attestation_lifecycle(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test complete attestation lifecycle from registration to attestation."""
        service, availability, mock_event_writer, _ = service_with_mocks

        # Setup: 4 active Keepers
        keepers = ["KEEPER:alice", "KEEPER:bob", "KEEPER:charlie", "KEEPER:dave"]
        for keeper_id in keepers:
            await availability.add_keeper(keeper_id)

        # Step 1: Check initial quorum (healthy)
        await service.check_keeper_quorum()
        mock_event_writer.write_event.assert_not_called()  # No warning

        # Step 2: All Keepers submit attestations
        for keeper_id in keepers:
            await service.submit_attestation(keeper_id, b"x" * 64)

        assert mock_event_writer.write_event.call_count == 4  # 4 attestation events

        # Step 3: Verify all Keepers have active status
        for keeper_id in keepers:
            status = await service.get_keeper_attestation_status(keeper_id)
            assert status.status == "active"
            assert status.missed_count == 0

    @pytest.mark.asyncio
    async def test_quorum_degradation_scenario(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test scenario where quorum degrades from healthy to warning to halt."""
        service, availability, mock_event_writer, mock_halt_trigger = service_with_mocks

        # Start with 4 Keepers
        keepers = ["KEEPER:alice", "KEEPER:bob", "KEEPER:charlie", "KEEPER:dave"]
        for keeper_id in keepers:
            await availability.add_keeper(keeper_id)

        # Phase 1: Healthy quorum (4 Keepers)
        await service.check_keeper_quorum()
        mock_event_writer.write_event.assert_not_called()

        # Phase 2: One Keeper marked for replacement (3 active - warning threshold)
        await availability.mark_keeper_for_replacement("KEEPER:dave", "test")
        mock_event_writer.reset_mock()

        await service.check_keeper_quorum()

        # Should write warning event (SR-7)
        mock_event_writer.write_event.assert_called_once()
        assert (
            mock_event_writer.write_event.call_args.kwargs["event_type"]
            == KEEPER_QUORUM_WARNING_EVENT_TYPE
        )

        # Phase 3: Another Keeper removed (2 active - below minimum)
        await availability.mark_keeper_for_replacement("KEEPER:charlie", "test")

        # Should trigger halt (FR79)
        with pytest.raises(KeeperQuorumViolationError):
            await service.check_keeper_quorum()

        mock_halt_trigger.trigger_halt.assert_called_once()

    @pytest.mark.asyncio
    async def test_operations_blocked_during_halt(
        self,
        service_with_mocks: tuple[
            KeeperAvailabilityService,
            KeeperAvailabilityStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test that operations are blocked during system halt (CT-11)."""
        service, availability, _, _ = service_with_mocks

        # Get halt checker mock and set to halted
        service._halt_checker.is_halted.return_value = True

        # Attestation submission should be blocked
        with pytest.raises(SystemHaltedError) as exc_info:
            await service.submit_attestation("KEEPER:alice", b"x" * 64)
        assert "CT-11" in str(exc_info.value)

        # Deadline check should be blocked
        with pytest.raises(SystemHaltedError) as exc_info:
            await service.check_attestation_deadlines()
        assert "CT-11" in str(exc_info.value)
