"""Unit tests for IndependenceAttestationService (Story 5.10, AC1-AC4).

Tests the core service functionality:
- submit_independence_attestation: Annual attestation submission (FR133)
- check_attestation_deadlines: Missed deadline detection and suspension (FR133)
- get_keeper_independence_history: History with change tracking (AC3)
- validate_keeper_can_override: Pre-override validation (FR133)

Constitutional Constraints:
- FR133: Annual independence attestation requirement
- FR98: Anomalous signature patterns flagged for manual review
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All events witnessed
- CT-9: Patient attacker detection via declaration change tracking
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.independence_attestation_service import (
    DeclarationDiff,
    IndependenceAttestationService,
    IndependenceHistoryResponse,
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
    ATTESTATION_DEADLINE_DAYS,
    DEADLINE_GRACE_PERIOD_DAYS,
    ConflictDeclaration,
    DeclarationType,
    IndependenceAttestation,
    calculate_deadline,
    get_current_attestation_year,
)
from src.infrastructure.stubs.independence_attestation_stub import (
    IndependenceAttestationStub,
)


@pytest.fixture
def attestation_stub() -> IndependenceAttestationStub:
    """Create attestation stub for testing."""
    return IndependenceAttestationStub()


@pytest.fixture
def mock_signature_service() -> MagicMock:
    """Create mock signature service."""
    mock = MagicMock()
    mock.verify_signature = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create mock event writer."""
    mock = AsyncMock()
    mock.write_event = AsyncMock()
    return mock


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create mock halt checker."""
    mock = AsyncMock()
    mock.is_halted = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_anomaly_detector() -> AsyncMock:
    """Create mock anomaly detector."""
    mock = AsyncMock()
    mock.report_anomaly = AsyncMock()
    return mock


@pytest.fixture
def service(
    attestation_stub: IndependenceAttestationStub,
    mock_signature_service: MagicMock,
    mock_event_writer: AsyncMock,
    mock_halt_checker: AsyncMock,
    mock_anomaly_detector: AsyncMock,
) -> IndependenceAttestationService:
    """Create service with stubs/mocks."""
    return IndependenceAttestationService(
        repository=attestation_stub,
        signature_service=mock_signature_service,
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker,
        anomaly_detector=mock_anomaly_detector,
    )


@pytest.fixture
def service_no_anomaly_detector(
    attestation_stub: IndependenceAttestationStub,
    mock_signature_service: MagicMock,
    mock_event_writer: AsyncMock,
    mock_halt_checker: AsyncMock,
) -> IndependenceAttestationService:
    """Create service without anomaly detector."""
    return IndependenceAttestationService(
        repository=attestation_stub,
        signature_service=mock_signature_service,
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker,
        anomaly_detector=None,
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


class TestSubmitIndependenceAttestation:
    """Test submit_independence_attestation method (AC1, AC2)."""

    @pytest.mark.asyncio
    async def test_submit_attestation_success(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test successful attestation submission (AC1)."""
        keeper_id = "KEEPER:alice"
        signature = b"x" * 64
        conflicts = [create_conflict()]
        organizations = ["Org A", "Org B"]

        attestation_stub.add_keeper(keeper_id)

        attestation = await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=conflicts,
            organizations=organizations,
            signature=signature,
        )

        assert attestation.keeper_id == keeper_id
        assert attestation.attestation_year == get_current_attestation_year()
        assert len(attestation.conflict_declarations) == 1
        assert len(attestation.affiliated_organizations) == 2
        assert attestation.signature == signature

        # Verify event written (CT-12)
        mock_event_writer.write_event.assert_called_once()
        call_args = mock_event_writer.write_event.call_args
        assert call_args.kwargs["event_type"] == INDEPENDENCE_ATTESTATION_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_submit_attestation_blocked_during_halt_ct11(
        self,
        service: IndependenceAttestationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test attestation blocked during system halt (CT-11)."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.submit_independence_attestation(
                keeper_id="KEEPER:alice",
                conflicts=[],
                organizations=[],
                signature=b"x" * 64,
            )

        assert "halt" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_submit_attestation_invalid_signature(
        self,
        service: IndependenceAttestationService,
        mock_signature_service: MagicMock,
    ) -> None:
        """Test attestation rejected with invalid signature."""
        mock_signature_service.verify_signature.return_value = False

        with pytest.raises(InvalidIndependenceSignatureError) as exc_info:
            await service.submit_independence_attestation(
                keeper_id="KEEPER:alice",
                conflicts=[],
                organizations=[],
                signature=b"x" * 64,
            )

        assert "FR133" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_attestation_duplicate_rejected(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
    ) -> None:
        """Test duplicate attestation for same year is rejected."""
        keeper_id = "KEEPER:alice"
        signature = b"x" * 64

        attestation_stub.add_keeper(keeper_id)

        # First submission should succeed
        await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[],
            organizations=[],
            signature=signature,
        )

        # Second submission should fail
        with pytest.raises(DuplicateIndependenceAttestationError) as exc_info:
            await service.submit_independence_attestation(
                keeper_id=keeper_id,
                conflicts=[],
                organizations=[],
                signature=signature,
            )

        assert "FR133" in str(exc_info.value)
        assert keeper_id in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_attestation_clears_suspension(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
    ) -> None:
        """Test attestation clears prior suspension."""
        keeper_id = "KEEPER:alice"
        signature = b"x" * 64

        attestation_stub.add_keeper(keeper_id)
        await attestation_stub.mark_keeper_suspended(keeper_id, "Overdue")

        assert await attestation_stub.is_keeper_suspended(keeper_id)

        await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[],
            organizations=[],
            signature=signature,
        )

        assert not await attestation_stub.is_keeper_suspended(keeper_id)


class TestDeclarationChangeDetection:
    """Test declaration change detection (FP-3, ADR-7, CT-9)."""

    @pytest.mark.asyncio
    async def test_declaration_change_writes_event(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test declaration changes write witnessed event (CT-12)."""
        keeper_id = "KEEPER:alice"
        signature = b"x" * 64

        attestation_stub.add_keeper(keeper_id)

        # Create previous year's attestation manually
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
        attestation_stub._attestations[keeper_id] = {prev_year: prev_attestation}

        # Submit with new conflict
        await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[create_conflict()],
            organizations=[],
            signature=signature,
        )

        # Should write attestation event + change detection event
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
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
        mock_anomaly_detector: AsyncMock,
    ) -> None:
        """Test declaration changes notify anomaly detector (ADR-7)."""
        keeper_id = "KEEPER:alice"
        signature = b"x" * 64

        attestation_stub.add_keeper(keeper_id)

        # Create previous year's attestation
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
        attestation_stub._attestations[keeper_id] = {prev_year: prev_attestation}

        # Submit with different conflicts (change)
        await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[
                create_conflict(
                    declaration_type=DeclarationType.ORGANIZATIONAL,
                    description="New conflict",
                    related_party="Different Corp",
                )
            ],
            organizations=["New Org"],
            signature=signature,
        )

        # Anomaly detector should be notified
        mock_anomaly_detector.report_anomaly.assert_called_once()
        call_args = mock_anomaly_detector.report_anomaly.call_args
        assert call_args.kwargs["anomaly_type"] == AnomalyType.PATTERN_CORRELATION
        assert keeper_id in call_args.kwargs["keeper_ids"]

    @pytest.mark.asyncio
    async def test_no_change_no_anomaly_notification(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
        mock_event_writer: AsyncMock,
        mock_anomaly_detector: AsyncMock,
    ) -> None:
        """Test no change doesn't notify anomaly detector."""
        keeper_id = "KEEPER:alice"
        signature = b"x" * 64
        conflicts = [create_conflict()]
        organizations = ["Org A"]

        attestation_stub.add_keeper(keeper_id)

        # Create previous year's attestation with same data
        prev_year = get_current_attestation_year() - 1
        prev_attestation = IndependenceAttestation(
            id=uuid4(),
            keeper_id=keeper_id,
            attested_at=datetime.now(timezone.utc) - timedelta(days=365),
            attestation_year=prev_year,
            conflict_declarations=conflicts,
            affiliated_organizations=organizations,
            signature=signature,
        )
        attestation_stub._attestations[keeper_id] = {prev_year: prev_attestation}

        # Submit with same conflicts (no change)
        await service.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=conflicts,
            organizations=organizations,
            signature=signature,
        )

        # Only attestation event should be written, no change event
        assert mock_event_writer.write_event.call_count == 1
        mock_anomaly_detector.report_anomaly.assert_not_called()


class TestCheckAttestationDeadlines:
    """Test check_attestation_deadlines method (AC2)."""

    @pytest.mark.asyncio
    async def test_check_deadlines_blocked_during_halt_ct11(
        self,
        service: IndependenceAttestationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test deadline check blocked during system halt (CT-11)."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.check_attestation_deadlines()

        assert "halt" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_check_deadlines_skips_already_suspended(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test deadline check skips already suspended Keepers."""
        keeper_id = "KEEPER:alice"

        attestation_stub.add_keeper(keeper_id)
        await attestation_stub.mark_keeper_suspended(keeper_id, "Already suspended")

        suspended = await service.check_attestation_deadlines()

        # Should not re-suspend
        assert keeper_id not in suspended
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_deadlines_skips_attested_keepers(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test deadline check skips Keepers with current year attestation."""
        keeper_id = "KEEPER:alice"
        current_year = get_current_attestation_year()
        signature = b"x" * 64

        attestation_stub.add_keeper(keeper_id)

        # Add current year attestation
        attestation = IndependenceAttestation(
            id=uuid4(),
            keeper_id=keeper_id,
            attested_at=datetime.now(timezone.utc),
            attestation_year=current_year,
            conflict_declarations=[],
            affiliated_organizations=[],
            signature=signature,
        )
        attestation_stub._attestations[keeper_id] = {current_year: attestation}

        suspended = await service.check_attestation_deadlines()

        assert keeper_id not in suspended
        mock_event_writer.write_event.assert_not_called()


class TestValidateKeeperCanOverride:
    """Test validate_keeper_can_override method (AC2)."""

    @pytest.mark.asyncio
    async def test_validate_non_suspended_keeper_can_override(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
    ) -> None:
        """Test non-suspended Keeper can override."""
        keeper_id = "KEEPER:alice"
        attestation_stub.add_keeper(keeper_id)

        result = await service.validate_keeper_can_override(keeper_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_suspended_keeper_cannot_override(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
    ) -> None:
        """Test suspended Keeper cannot override (FR133)."""
        keeper_id = "KEEPER:alice"

        attestation_stub.add_keeper(keeper_id)
        await attestation_stub.mark_keeper_suspended(keeper_id, "Overdue")

        with pytest.raises(CapabilitySuspendedError) as exc_info:
            await service.validate_keeper_can_override(keeper_id)

        assert "FR133" in str(exc_info.value)
        assert keeper_id in str(exc_info.value)


class TestGetKeeperIndependenceHistory:
    """Test get_keeper_independence_history method (AC3)."""

    @pytest.mark.asyncio
    async def test_get_history_empty(
        self,
        service: IndependenceAttestationService,
    ) -> None:
        """Test history query for Keeper with no attestations."""
        result = await service.get_keeper_independence_history("KEEPER:alice")

        assert result.attestations == []
        assert result.declaration_changes == []
        assert result.is_suspended is False
        assert result.current_year_attested is False

    @pytest.mark.asyncio
    async def test_get_history_with_attestations(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
    ) -> None:
        """Test history query returns attestations ordered by year."""
        keeper_id = "KEEPER:alice"
        signature = b"x" * 64

        attestation_stub.add_keeper(keeper_id)

        # Create attestations for multiple years
        current_year = get_current_attestation_year()
        for year_offset in [2, 1, 0]:
            year = current_year - year_offset
            attestation = IndependenceAttestation(
                id=uuid4(),
                keeper_id=keeper_id,
                attested_at=datetime.now(timezone.utc) - timedelta(days=365 * year_offset),
                attestation_year=year,
                conflict_declarations=[],
                affiliated_organizations=[],
                signature=signature,
            )
            if keeper_id not in attestation_stub._attestations:
                attestation_stub._attestations[keeper_id] = {}
            attestation_stub._attestations[keeper_id][year] = attestation

        result = await service.get_keeper_independence_history(keeper_id)

        assert len(result.attestations) == 3
        # Should be ordered by year ascending
        years = [a.attestation_year for a in result.attestations]
        assert years == sorted(years)
        assert result.current_year_attested is True

    @pytest.mark.asyncio
    async def test_get_history_includes_declaration_changes(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
    ) -> None:
        """Test history includes declaration changes between years."""
        keeper_id = "KEEPER:alice"
        signature = b"x" * 64

        attestation_stub.add_keeper(keeper_id)

        current_year = get_current_attestation_year()

        # Year 1: No conflicts
        attestation1 = IndependenceAttestation(
            id=uuid4(),
            keeper_id=keeper_id,
            attested_at=datetime.now(timezone.utc) - timedelta(days=365),
            attestation_year=current_year - 1,
            conflict_declarations=[],
            affiliated_organizations=[],
            signature=signature,
        )

        # Year 2: Added conflict
        attestation2 = IndependenceAttestation(
            id=uuid4(),
            keeper_id=keeper_id,
            attested_at=datetime.now(timezone.utc),
            attestation_year=current_year,
            conflict_declarations=[create_conflict()],
            affiliated_organizations=["New Org"],
            signature=signature,
        )

        attestation_stub._attestations[keeper_id] = {
            current_year - 1: attestation1,
            current_year: attestation2,
        }

        result = await service.get_keeper_independence_history(keeper_id)

        assert len(result.declaration_changes) == 1
        diff = result.declaration_changes[0]
        assert diff.has_changes is True
        assert len(diff.added_conflicts) == 1
        assert len(diff.added_organizations) == 1

    @pytest.mark.asyncio
    async def test_get_history_shows_suspension_status(
        self,
        service: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
    ) -> None:
        """Test history shows current suspension status."""
        keeper_id = "KEEPER:alice"

        attestation_stub.add_keeper(keeper_id)
        await attestation_stub.mark_keeper_suspended(keeper_id, "Overdue")

        result = await service.get_keeper_independence_history(keeper_id)

        assert result.is_suspended is True


class TestDeclarationDiff:
    """Test DeclarationDiff computation."""

    def test_diff_no_previous_with_declarations(
        self,
        service: IndependenceAttestationService,
    ) -> None:
        """Test diff when no previous attestation exists but current has data."""
        current = IndependenceAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=datetime.now(timezone.utc),
            attestation_year=get_current_attestation_year(),
            conflict_declarations=[create_conflict()],
            affiliated_organizations=["Org A"],
            signature=b"x" * 64,
        )

        diff = service._get_declaration_diff(None, current)

        assert diff.has_changes is True
        assert len(diff.added_conflicts) == 1
        assert len(diff.added_organizations) == 1
        assert diff.removed_conflicts == []
        assert diff.removed_organizations == []

    def test_diff_no_previous_empty_declarations(
        self,
        service: IndependenceAttestationService,
    ) -> None:
        """Test diff when no previous and current has no declarations."""
        current = IndependenceAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=datetime.now(timezone.utc),
            attestation_year=get_current_attestation_year(),
            conflict_declarations=[],
            affiliated_organizations=[],
            signature=b"x" * 64,
        )

        diff = service._get_declaration_diff(None, current)

        # Empty declarations = no changes (first attestation with nothing declared)
        assert diff.has_changes is False

    def test_diff_no_changes(
        self,
        service: IndependenceAttestationService,
    ) -> None:
        """Test diff when declarations are identical."""
        conflicts = [create_conflict()]
        organizations = ["Org A"]
        signature = b"x" * 64

        prev = IndependenceAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=datetime.now(timezone.utc) - timedelta(days=365),
            attestation_year=get_current_attestation_year() - 1,
            conflict_declarations=conflicts,
            affiliated_organizations=organizations,
            signature=signature,
        )

        current = IndependenceAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=datetime.now(timezone.utc),
            attestation_year=get_current_attestation_year(),
            conflict_declarations=conflicts,
            affiliated_organizations=organizations,
            signature=signature,
        )

        diff = service._get_declaration_diff(prev, current)

        assert diff.has_changes is False
        assert diff.added_conflicts == []
        assert diff.removed_conflicts == []
        assert diff.added_organizations == []
        assert diff.removed_organizations == []

    def test_diff_added_and_removed(
        self,
        service: IndependenceAttestationService,
    ) -> None:
        """Test diff with both additions and removals."""
        old_conflict = create_conflict(description="Old", related_party="Old Corp")
        new_conflict = create_conflict(description="New", related_party="New Corp")
        signature = b"x" * 64

        prev = IndependenceAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=datetime.now(timezone.utc) - timedelta(days=365),
            attestation_year=get_current_attestation_year() - 1,
            conflict_declarations=[old_conflict],
            affiliated_organizations=["Old Org"],
            signature=signature,
        )

        current = IndependenceAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=datetime.now(timezone.utc),
            attestation_year=get_current_attestation_year(),
            conflict_declarations=[new_conflict],
            affiliated_organizations=["New Org"],
            signature=signature,
        )

        diff = service._get_declaration_diff(prev, current)

        assert diff.has_changes is True
        assert len(diff.added_conflicts) == 1
        assert len(diff.removed_conflicts) == 1
        assert "New Org" in diff.added_organizations
        assert "Old Org" in diff.removed_organizations


class TestServiceConstants:
    """Test service constant values."""

    def test_suspended_capabilities(self) -> None:
        """Test suspended capabilities includes override."""
        assert "override" in SUSPENDED_CAPABILITIES

    def test_attestation_deadline_days(self) -> None:
        """Test attestation deadline matches domain constant."""
        assert ATTESTATION_DEADLINE_DAYS == 365

    def test_grace_period_days(self) -> None:
        """Test grace period matches domain constant."""
        assert DEADLINE_GRACE_PERIOD_DAYS == 30


class TestServiceWithoutAnomalyDetector:
    """Test service behavior when anomaly detector is not provided."""

    @pytest.mark.asyncio
    async def test_declaration_change_without_anomaly_detector(
        self,
        service_no_anomaly_detector: IndependenceAttestationService,
        attestation_stub: IndependenceAttestationStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test declaration change works without anomaly detector."""
        keeper_id = "KEEPER:alice"
        signature = b"x" * 64

        attestation_stub.add_keeper(keeper_id)

        # Create previous year's attestation
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
        attestation_stub._attestations[keeper_id] = {prev_year: prev_attestation}

        # Submit with new conflict - should not raise even without anomaly detector
        attestation = await service_no_anomaly_detector.submit_independence_attestation(
            keeper_id=keeper_id,
            conflicts=[create_conflict()],
            organizations=[],
            signature=signature,
        )

        assert attestation is not None
        # Should still write both events
        assert mock_event_writer.write_event.call_count == 2
