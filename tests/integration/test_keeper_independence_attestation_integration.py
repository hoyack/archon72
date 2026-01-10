"""Integration tests for Keeper independence attestation (Story 5.10).

Tests end-to-end flows for:
- AC1: IndependenceAttestationEvent logged with Keeper attribution (FR133)
- AC2: Suspension if attestation deadline missed (FR133)
- AC3: History queries with declaration change tracking (FP-3, CT-9)
- AC4: Suspended Keepers blocked from override operations (FR133)

Constitutional Constraints:
- FR133: Annual independence attestation requirement
- FR98: Anomalous signature patterns flagged for manual review
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All events witnessed
- CT-9: Patient attacker detection via declaration change tracking
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.independence_attestation_service import (
    IndependenceAttestationService,
    SUSPENDED_CAPABILITIES,
)
from src.domain.errors.independence_attestation import (
    CapabilitySuspendedError,
    DuplicateIndependenceAttestationError,
    InvalidIndependenceSignatureError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.independence_attestation import (
    DECLARATION_CHANGE_DETECTED_EVENT_TYPE,
    INDEPENDENCE_ATTESTATION_EVENT_TYPE,
    KEEPER_INDEPENDENCE_SUSPENDED_EVENT_TYPE,
)
from src.domain.events.override_abuse import AnomalyType
from src.domain.models.independence_attestation import (
    ConflictDeclaration,
    DeclarationType,
    IndependenceAttestation,
    get_current_attestation_year,
)
from src.infrastructure.stubs.independence_attestation_stub import (
    IndependenceAttestationStub,
)


def create_conflict(
    declaration_type: DeclarationType = DeclarationType.FINANCIAL,
    description: str = "Test conflict",
    related_party: str = "Acme Corp",
) -> ConflictDeclaration:
    """Helper to create conflict declarations."""
    return ConflictDeclaration(
        declaration_type=declaration_type,
        description=description,
        related_party=related_party,
        disclosed_at=datetime.now(timezone.utc),
    )


class TestAC1IndependenceAttestationEvents:
    """AC1: IndependenceAttestationEvent logged with Keeper attribution (FR133)."""

    @pytest.fixture
    def service_with_mocks(self) -> tuple[
        IndependenceAttestationService,
        IndependenceAttestationStub,
        AsyncMock,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        repository = IndependenceAttestationStub()
        mock_signature_service = MagicMock()
        mock_signature_service.verify_signature = AsyncMock(return_value=True)
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)
        mock_anomaly_detector = AsyncMock()
        mock_anomaly_detector.report_anomaly = AsyncMock()

        service = IndependenceAttestationService(
            repository=repository,
            signature_service=mock_signature_service,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        return service, repository, mock_event_writer, mock_anomaly_detector

    @pytest.mark.asyncio
    async def test_attestation_event_logged_with_keeper_id(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test that attestation creates event with Keeper ID (FR133)."""
        service, repository, mock_event_writer, _ = service_with_mocks

        keeper_id = "KEEPER:alice"
        signature = b"x" * 64
        conflicts = [create_conflict()]
        organizations = ["Org A"]

        repository.add_keeper(keeper_id)

        attestation = await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=conflicts,
            organizations=organizations,
            signature=signature,
        )

        # Verify event was written
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs

        assert call_kwargs["event_type"] == INDEPENDENCE_ATTESTATION_EVENT_TYPE

        # Verify payload is bytes (signable_content) and contains correct data
        payload_bytes = call_kwargs["payload"]
        payload = json.loads(payload_bytes.decode("utf-8"))
        assert payload["keeper_id"] == keeper_id
        assert payload["attestation_year"] == get_current_attestation_year()
        assert payload["conflict_count"] == 1
        assert payload["organization_count"] == 1

    @pytest.mark.asyncio
    async def test_attestation_event_includes_attestation_year(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test that attestation event includes attestation year (FR133)."""
        service, repository, mock_event_writer, _ = service_with_mocks

        keeper_id = "KEEPER:bob"
        repository.add_keeper(keeper_id)

        await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[],
            organizations=[],
            signature=b"x" * 64,
        )

        payload_bytes = mock_event_writer.write_event.call_args.kwargs["payload"]
        payload = json.loads(payload_bytes.decode("utf-8"))

        assert payload["attestation_year"] == get_current_attestation_year()

    @pytest.mark.asyncio
    async def test_duplicate_attestation_rejected_with_fr133(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test duplicate attestation rejected with FR133 reference."""
        service, repository, _, _ = service_with_mocks

        keeper_id = "KEEPER:charlie"
        repository.add_keeper(keeper_id)

        # First attestation succeeds
        await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[],
            organizations=[],
            signature=b"x" * 64,
        )

        # Second attestation fails
        with pytest.raises(DuplicateIndependenceAttestationError) as exc_info:
            await service.submit_independence_attestation(
                keeper_id=keeper_id,
                conflicts=[],
                organizations=[],
                signature=b"x" * 64,
            )

        assert "FR133" in str(exc_info.value)
        assert keeper_id in str(exc_info.value)


class TestAC2SuspensionOnMissedDeadline:
    """AC2: Suspension if attestation deadline missed (FR133)."""

    @pytest.fixture
    def service_with_mocks(self) -> tuple[
        IndependenceAttestationService,
        IndependenceAttestationStub,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        repository = IndependenceAttestationStub()
        mock_signature_service = MagicMock()
        mock_signature_service.verify_signature = AsyncMock(return_value=True)
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)

        service = IndependenceAttestationService(
            repository=repository,
            signature_service=mock_signature_service,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
        )

        return service, repository, mock_event_writer

    @pytest.mark.asyncio
    async def test_suspension_blocks_override_capability(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
        ],
    ) -> None:
        """Test that suspended Keeper cannot perform overrides (FR133)."""
        service, repository, _ = service_with_mocks

        keeper_id = "KEEPER:alice"
        repository.add_keeper(keeper_id)
        await repository.mark_keeper_suspended(keeper_id, "Deadline missed")

        with pytest.raises(CapabilitySuspendedError) as exc_info:
            await service.validate_keeper_can_override(keeper_id)

        assert "FR133" in str(exc_info.value)
        assert keeper_id in str(exc_info.value)
        assert "override" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_attestation_clears_suspension(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
        ],
    ) -> None:
        """Test that successful attestation clears prior suspension."""
        service, repository, _ = service_with_mocks

        keeper_id = "KEEPER:bob"
        repository.add_keeper(keeper_id)
        await repository.mark_keeper_suspended(keeper_id, "Deadline missed")

        assert await repository.is_keeper_suspended(keeper_id)

        # Submit attestation
        await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[],
            organizations=[],
            signature=b"x" * 64,
        )

        # Suspension should be cleared
        assert not await repository.is_keeper_suspended(keeper_id)

        # Override should now be allowed
        result = await service.validate_keeper_can_override(keeper_id)
        assert result is True


class TestAC3DeclarationChangeTracking:
    """AC3: History queries with declaration change tracking (FP-3, CT-9)."""

    @pytest.fixture
    def service_with_mocks(self) -> tuple[
        IndependenceAttestationService,
        IndependenceAttestationStub,
        AsyncMock,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        repository = IndependenceAttestationStub()
        mock_signature_service = MagicMock()
        mock_signature_service.verify_signature = AsyncMock(return_value=True)
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)
        mock_anomaly_detector = AsyncMock()
        mock_anomaly_detector.report_anomaly = AsyncMock()

        service = IndependenceAttestationService(
            repository=repository,
            signature_service=mock_signature_service,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        return service, repository, mock_event_writer, mock_anomaly_detector

    @pytest.mark.asyncio
    async def test_declaration_change_triggers_event(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test that declaration changes trigger witnessed event (CT-12)."""
        service, repository, mock_event_writer, _ = service_with_mocks

        keeper_id = "KEEPER:alice"
        signature = b"x" * 64

        repository.add_keeper(keeper_id)

        # Create previous year attestation with no conflicts
        prev_year = get_current_attestation_year() - 1
        prev_attestation = IndependenceAttestation(
            id=uuid4(),
            keeper_id=keeper_id,
            attested_at=datetime.now(timezone.utc) - timedelta(days=365),
            attestation_year=prev_year,
            conflict_declarations=[],
            affiliated_organizations=[],
            signature=signature,
        )
        repository._attestations[keeper_id] = {prev_year: prev_attestation}

        # Submit new attestation with conflicts
        await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[create_conflict()],
            organizations=["New Org"],
            signature=signature,
        )

        # Should write both attestation and change detection events
        assert mock_event_writer.write_event.call_count == 2

        event_types = [
            call.kwargs["event_type"]
            for call in mock_event_writer.write_event.call_args_list
        ]
        assert INDEPENDENCE_ATTESTATION_EVENT_TYPE in event_types
        assert DECLARATION_CHANGE_DETECTED_EVENT_TYPE in event_types

    @pytest.mark.asyncio
    async def test_declaration_change_notifies_anomaly_detector(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test that declaration changes notify anomaly detector (ADR-7, CT-9)."""
        service, repository, _, mock_anomaly_detector = service_with_mocks

        keeper_id = "KEEPER:alice"
        signature = b"x" * 64

        repository.add_keeper(keeper_id)

        # Create previous year attestation
        prev_year = get_current_attestation_year() - 1
        prev_attestation = IndependenceAttestation(
            id=uuid4(),
            keeper_id=keeper_id,
            attested_at=datetime.now(timezone.utc) - timedelta(days=365),
            attestation_year=prev_year,
            conflict_declarations=[create_conflict()],
            affiliated_organizations=["Old Org"],
            signature=signature,
        )
        repository._attestations[keeper_id] = {prev_year: prev_attestation}

        # Submit with changed declarations
        await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[
                create_conflict(
                    declaration_type=DeclarationType.ORGANIZATIONAL,
                    description="Different conflict",
                    related_party="Different Corp",
                )
            ],
            organizations=["New Org"],
            signature=signature,
        )

        # Anomaly detector should be notified
        mock_anomaly_detector.report_anomaly.assert_called_once()
        call_kwargs = mock_anomaly_detector.report_anomaly.call_args.kwargs

        assert call_kwargs["anomaly_type"] == AnomalyType.PATTERN_CORRELATION
        assert keeper_id in call_kwargs["keeper_ids"]
        assert "change" in call_kwargs["details"].lower()

    @pytest.mark.asyncio
    async def test_history_includes_declaration_changes(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test history query returns declaration changes between years (FP-3)."""
        service, repository, _, _ = service_with_mocks

        keeper_id = "KEEPER:bob"
        signature = b"x" * 64

        repository.add_keeper(keeper_id)

        current_year = get_current_attestation_year()

        # Year 1: No conflicts
        attestation1 = IndependenceAttestation(
            id=uuid4(),
            keeper_id=keeper_id,
            attested_at=datetime.now(timezone.utc) - timedelta(days=730),
            attestation_year=current_year - 2,
            conflict_declarations=[],
            affiliated_organizations=[],
            signature=signature,
        )

        # Year 2: Added conflict
        attestation2 = IndependenceAttestation(
            id=uuid4(),
            keeper_id=keeper_id,
            attested_at=datetime.now(timezone.utc) - timedelta(days=365),
            attestation_year=current_year - 1,
            conflict_declarations=[create_conflict()],
            affiliated_organizations=["New Org"],
            signature=signature,
        )

        repository._attestations[keeper_id] = {
            current_year - 2: attestation1,
            current_year - 1: attestation2,
        }

        # Query history
        history = await service.get_keeper_independence_history(keeper_id)

        assert len(history.attestations) == 2
        assert len(history.declaration_changes) == 1

        # Verify change was detected
        change = history.declaration_changes[0]
        assert change.has_changes is True
        assert len(change.added_conflicts) == 1
        assert "New Org" in change.added_organizations


class TestAC4SuspendedKeeperOverrideBlocking:
    """AC4: Suspended Keepers blocked from override operations (FR133)."""

    @pytest.fixture
    def service_with_mocks(self) -> tuple[
        IndependenceAttestationService,
        IndependenceAttestationStub,
    ]:
        """Create service with stubs and mocks."""
        repository = IndependenceAttestationStub()
        mock_signature_service = MagicMock()
        mock_signature_service.verify_signature = AsyncMock(return_value=True)
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)

        service = IndependenceAttestationService(
            repository=repository,
            signature_service=mock_signature_service,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
        )

        return service, repository

    @pytest.mark.asyncio
    async def test_suspended_keeper_blocked_with_fr133(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
        ],
    ) -> None:
        """Test suspended Keeper is blocked with FR133 error."""
        service, repository = service_with_mocks

        keeper_id = "KEEPER:alice"
        repository.add_keeper(keeper_id)
        await repository.mark_keeper_suspended(keeper_id, "Independence attestation overdue")

        with pytest.raises(CapabilitySuspendedError) as exc_info:
            await service.validate_keeper_can_override(keeper_id)

        assert "FR133" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_non_suspended_keeper_allowed(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
        ],
    ) -> None:
        """Test non-suspended Keeper is allowed to override."""
        service, repository = service_with_mocks

        keeper_id = "KEEPER:bob"
        repository.add_keeper(keeper_id)

        result = await service.validate_keeper_can_override(keeper_id)

        assert result is True


class TestEndToEndScenarios:
    """End-to-end scenario tests."""

    @pytest.fixture
    def service_with_mocks(self) -> tuple[
        IndependenceAttestationService,
        IndependenceAttestationStub,
        AsyncMock,
        AsyncMock,
    ]:
        """Create service with stubs and mocks."""
        repository = IndependenceAttestationStub()
        mock_signature_service = MagicMock()
        mock_signature_service.verify_signature = AsyncMock(return_value=True)
        mock_event_writer = AsyncMock()
        mock_event_writer.write_event = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)
        mock_anomaly_detector = AsyncMock()
        mock_anomaly_detector.report_anomaly = AsyncMock()

        service = IndependenceAttestationService(
            repository=repository,
            signature_service=mock_signature_service,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        return service, repository, mock_event_writer, mock_anomaly_detector

    @pytest.mark.asyncio
    async def test_full_attestation_lifecycle(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test complete attestation lifecycle from submission to history."""
        service, repository, mock_event_writer, _ = service_with_mocks

        keeper_id = "KEEPER:alice"
        repository.add_keeper(keeper_id)

        # Step 1: Submit first attestation
        attestation = await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[create_conflict()],
            organizations=["Org A"],
            signature=b"x" * 64,
        )

        assert attestation.keeper_id == keeper_id
        assert attestation.attestation_year == get_current_attestation_year()
        mock_event_writer.write_event.assert_called_once()

        # Step 2: Query history
        history = await service.get_keeper_independence_history(keeper_id)

        assert len(history.attestations) == 1
        assert history.current_year_attested is True
        assert history.is_suspended is False

        # Step 3: Verify override is allowed
        result = await service.validate_keeper_can_override(keeper_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_suspension_and_recovery_cycle(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test complete suspension and recovery cycle."""
        service, repository, _, _ = service_with_mocks

        keeper_id = "KEEPER:bob"
        repository.add_keeper(keeper_id)

        # Step 1: Suspend Keeper
        await repository.mark_keeper_suspended(keeper_id, "Deadline missed")

        # Step 2: Verify suspension blocks override
        with pytest.raises(CapabilitySuspendedError):
            await service.validate_keeper_can_override(keeper_id)

        # Step 3: Verify history shows suspension
        history = await service.get_keeper_independence_history(keeper_id)
        assert history.is_suspended is True

        # Step 4: Submit attestation to clear suspension
        await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[],
            organizations=[],
            signature=b"x" * 64,
        )

        # Step 5: Verify suspension cleared
        assert not await repository.is_keeper_suspended(keeper_id)

        # Step 6: Verify override now allowed
        result = await service.validate_keeper_can_override(keeper_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_operations_blocked_during_halt(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test that operations are blocked during system halt (CT-11)."""
        service, repository, _, _ = service_with_mocks

        # Set system to halted state
        service._halt_checker.is_halted.return_value = True

        keeper_id = "KEEPER:charlie"
        repository.add_keeper(keeper_id)

        # Attestation submission should be blocked
        with pytest.raises(SystemHaltedError) as exc_info:
            await service.submit_independence_attestation(
                keeper_id=keeper_id,
                conflicts=[],
                organizations=[],
                signature=b"x" * 64,
            )
        assert "halt" in str(exc_info.value).lower()

        # Deadline check should be blocked
        with pytest.raises(SystemHaltedError) as exc_info:
            await service.check_attestation_deadlines()
        assert "halt" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(
        self,
        service_with_mocks: tuple[
            IndependenceAttestationService,
            IndependenceAttestationStub,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test that invalid signature is rejected with FR133 reference."""
        service, repository, _, _ = service_with_mocks

        keeper_id = "KEEPER:dave"
        repository.add_keeper(keeper_id)

        # Configure signature service to reject
        service._signature_service.verify_signature.return_value = False

        with pytest.raises(InvalidIndependenceSignatureError) as exc_info:
            await service.submit_independence_attestation(
                keeper_id=keeper_id,
                conflicts=[],
                organizations=[],
                signature=b"x" * 64,
            )

        assert "FR133" in str(exc_info.value)
