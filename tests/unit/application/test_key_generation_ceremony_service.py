"""Unit tests for KeyGenerationCeremonyService (FR69, ADR-4).

Tests service orchestration of witnessed key generation ceremonies.

Constitutional Constraints:
- FR69: Keeper keys SHALL be generated through witnessed ceremony
- CT-11: HALT CHECK FIRST at every operation
- CT-12: Witnessing creates accountability
- VAL-2: Ceremony timeout enforcement (1 hour max)
- CM-5: Single ceremony at a time per Keeper
- ADR-4: Key rotation includes 30-day transition period
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.key_generation_ceremony_service import (
    KeyGenerationCeremonyService,
)
from src.domain.errors.key_generation_ceremony import (
    CeremonyConflictError,
    CeremonyNotFoundError,
    DuplicateWitnessError,
    InvalidCeremonyStateError,
)
from src.domain.models.key_generation_ceremony import (
    CEREMONY_TIMEOUT_SECONDS,
    REQUIRED_WITNESSES,
    TRANSITION_PERIOD_DAYS,
    CeremonyState,
    CeremonyType,
    KeyGenerationCeremony,
)
from src.infrastructure.stubs.keeper_key_registry_stub import KeeperKeyRegistryStub
from src.infrastructure.stubs.key_generation_ceremony_stub import (
    KeyGenerationCeremonyStub,
)


@pytest.fixture
def hsm_mock() -> MagicMock:
    """Create mock HSM with async methods."""
    from src.application.ports.hsm import HSMMode

    hsm = MagicMock()
    hsm.get_primary_key_id = MagicMock(return_value="test-key-id")
    # Async methods required by service
    hsm.generate_key_pair = AsyncMock(return_value="hsm-generated-key-id")
    hsm.get_public_key_bytes = AsyncMock(return_value=b"\x00" * 32)
    hsm.get_mode = AsyncMock(return_value=HSMMode.DEVELOPMENT)
    return hsm


@pytest.fixture
def key_registry() -> KeeperKeyRegistryStub:
    """Create key registry stub without dev key for testing."""
    return KeeperKeyRegistryStub(with_dev_key=False)


@pytest.fixture
def ceremony_repo() -> KeyGenerationCeremonyStub:
    """Create ceremony repository stub."""
    return KeyGenerationCeremonyStub()


@pytest.fixture
def halt_guard_mock() -> AsyncMock:
    """Create mock halt guard (not halted)."""
    guard = AsyncMock()
    guard.check_write_allowed = AsyncMock(return_value=None)
    return guard


@pytest.fixture
def halted_guard_mock() -> AsyncMock:
    """Create mock halt guard (halted)."""
    from src.domain.errors.read_only import WriteBlockedDuringHaltError

    guard = AsyncMock()
    guard.check_write_allowed = AsyncMock(
        side_effect=WriteBlockedDuringHaltError("System is halted")
    )
    return guard


@pytest.fixture
def event_writer_mock() -> AsyncMock:
    """Create mock event writer."""
    writer = AsyncMock()
    writer.write_event = AsyncMock(return_value=None)
    return writer


@pytest.fixture
def service(
    hsm_mock: MagicMock,
    key_registry: KeeperKeyRegistryStub,
    ceremony_repo: KeyGenerationCeremonyStub,
) -> KeyGenerationCeremonyService:
    """Create service with stubs (no halt guard or event writer)."""
    return KeyGenerationCeremonyService(
        hsm=hsm_mock,
        key_registry=key_registry,
        ceremony_repo=ceremony_repo,
    )


@pytest.fixture
def service_with_halt_guard(
    hsm_mock: MagicMock,
    key_registry: KeeperKeyRegistryStub,
    ceremony_repo: KeyGenerationCeremonyStub,
    halt_guard_mock: AsyncMock,
) -> KeyGenerationCeremonyService:
    """Create service with halt guard."""
    return KeyGenerationCeremonyService(
        hsm=hsm_mock,
        key_registry=key_registry,
        ceremony_repo=ceremony_repo,
        halt_guard=halt_guard_mock,
    )


@pytest.fixture
def service_with_halted_guard(
    hsm_mock: MagicMock,
    key_registry: KeeperKeyRegistryStub,
    ceremony_repo: KeyGenerationCeremonyStub,
    halted_guard_mock: AsyncMock,
) -> KeyGenerationCeremonyService:
    """Create service with halted guard."""
    return KeyGenerationCeremonyService(
        hsm=hsm_mock,
        key_registry=key_registry,
        ceremony_repo=ceremony_repo,
        halt_guard=halted_guard_mock,
    )


@pytest.fixture
def service_with_event_writer(
    hsm_mock: MagicMock,
    key_registry: KeeperKeyRegistryStub,
    ceremony_repo: KeyGenerationCeremonyStub,
    event_writer_mock: AsyncMock,
) -> KeyGenerationCeremonyService:
    """Create service with event writer."""
    return KeyGenerationCeremonyService(
        hsm=hsm_mock,
        key_registry=key_registry,
        ceremony_repo=ceremony_repo,
        event_writer=event_writer_mock,
    )


class TestStartCeremony:
    """Tests for start_ceremony method."""

    @pytest.mark.asyncio
    async def test_start_ceremony_creates_pending_ceremony(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Start ceremony creates PENDING ceremony (FR69)."""
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        assert ceremony.keeper_id == "KEEPER:alice"
        assert ceremony.ceremony_type == CeremonyType.NEW_KEEPER_KEY
        assert ceremony.state == CeremonyState.PENDING
        assert len(ceremony.witnesses) == 0

    @pytest.mark.asyncio
    async def test_start_ceremony_with_old_key_for_rotation(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Start rotation ceremony stores old_key_id."""
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:bob",
            ceremony_type=CeremonyType.KEY_ROTATION,
            initiator_id="KEEPER:admin",
            old_key_id="old-key-123",
        )

        assert ceremony.ceremony_type == CeremonyType.KEY_ROTATION
        assert ceremony.old_key_id == "old-key-123"

    @pytest.mark.asyncio
    async def test_start_ceremony_rejects_conflict_cm5(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Start ceremony rejects conflicting active ceremony (CM-5)."""
        # Create first ceremony
        await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        # Try to create another for same Keeper
        with pytest.raises(CeremonyConflictError) as exc_info:
            await service.start_ceremony(
                keeper_id="KEEPER:alice",
                ceremony_type=CeremonyType.NEW_KEEPER_KEY,
                initiator_id="KEEPER:admin",
            )

        assert "CM-5" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_start_ceremony_halt_check_first_ct11(
        self,
        service_with_halt_guard: KeyGenerationCeremonyService,
        halt_guard_mock: AsyncMock,
    ) -> None:
        """Start ceremony calls halt check first (CT-11)."""
        await service_with_halt_guard.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        halt_guard_mock.check_write_allowed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_ceremony_blocked_when_halted(
        self,
        service_with_halted_guard: KeyGenerationCeremonyService,
    ) -> None:
        """Start ceremony blocked when system halted (CT-11)."""
        from src.domain.errors.read_only import WriteBlockedDuringHaltError

        with pytest.raises(WriteBlockedDuringHaltError):
            await service_with_halted_guard.start_ceremony(
                keeper_id="KEEPER:alice",
                ceremony_type=CeremonyType.NEW_KEEPER_KEY,
                initiator_id="KEEPER:admin",
            )

    @pytest.mark.asyncio
    async def test_start_ceremony_writes_started_event(
        self,
        service_with_event_writer: KeyGenerationCeremonyService,
        event_writer_mock: AsyncMock,
    ) -> None:
        """Start ceremony writes started event."""
        await service_with_event_writer.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        event_writer_mock.write_event.assert_awaited_once()
        call_args = event_writer_mock.write_event.call_args
        assert call_args.kwargs["event_type"] == "ceremony.key_generation.started"


class TestAddWitness:
    """Tests for add_witness method."""

    @pytest.mark.asyncio
    async def test_add_witness_accumulates_signatures(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Add witness accumulates signatures (CT-12)."""
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        updated = await service.add_witness(
            ceremony_id=str(ceremony.id),
            witness_id="KEEPER:witness1",
            signature=b"sig1",
        )

        assert len(updated.witnesses) == 1
        assert updated.witnesses[0].witness_id == "KEEPER:witness1"

    @pytest.mark.asyncio
    async def test_add_witness_auto_transitions_to_approved(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Add witness auto-transitions to APPROVED when threshold met."""
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        # Add witnesses up to threshold
        for i in range(REQUIRED_WITNESSES):
            updated = await service.add_witness(
                ceremony_id=str(ceremony.id),
                witness_id=f"KEEPER:witness{i}",
                signature=f"sig{i}".encode(),
            )

        assert updated.state == CeremonyState.APPROVED
        assert len(updated.witnesses) == REQUIRED_WITNESSES

    @pytest.mark.asyncio
    async def test_add_witness_rejects_duplicate(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Add witness rejects duplicate witness."""
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        await service.add_witness(
            ceremony_id=str(ceremony.id),
            witness_id="KEEPER:witness1",
            signature=b"sig1",
        )

        with pytest.raises(DuplicateWitnessError) as exc_info:
            await service.add_witness(
                ceremony_id=str(ceremony.id),
                witness_id="KEEPER:witness1",  # Same witness
                signature=b"sig1-again",
            )

        assert "CT-12" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_witness_not_found_ceremony(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Add witness raises not found for missing ceremony."""
        with pytest.raises(CeremonyNotFoundError) as exc_info:
            await service.add_witness(
                ceremony_id=str(uuid4()),
                witness_id="KEEPER:witness1",
                signature=b"sig1",
            )

        assert "FR69" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_witness_rejects_invalid_state(
        self,
        service: KeyGenerationCeremonyService,
        ceremony_repo: KeyGenerationCeremonyStub,
    ) -> None:
        """Add witness rejects non-PENDING state."""
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        # Manually transition to APPROVED (bypassing witness check for test)
        await ceremony_repo.update_state(str(ceremony.id), CeremonyState.APPROVED)

        with pytest.raises(InvalidCeremonyStateError) as exc_info:
            await service.add_witness(
                ceremony_id=str(ceremony.id),
                witness_id="KEEPER:new_witness",
                signature=b"sig",
            )

        assert "FP-4" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_witness_halt_check_first(
        self,
        service_with_halt_guard: KeyGenerationCeremonyService,
        halt_guard_mock: AsyncMock,
    ) -> None:
        """Add witness checks halt state first (CT-11)."""
        ceremony = await service_with_halt_guard.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        # Reset mock to check add_witness call
        halt_guard_mock.check_write_allowed.reset_mock()

        await service_with_halt_guard.add_witness(
            ceremony_id=str(ceremony.id),
            witness_id="KEEPER:witness1",
            signature=b"sig1",
        )

        halt_guard_mock.check_write_allowed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_witness_writes_witnessed_event(
        self,
        service_with_event_writer: KeyGenerationCeremonyService,
        event_writer_mock: AsyncMock,
    ) -> None:
        """Add witness writes witnessed event."""
        ceremony = await service_with_event_writer.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        # Reset mock to check add_witness event
        event_writer_mock.write_event.reset_mock()

        await service_with_event_writer.add_witness(
            ceremony_id=str(ceremony.id),
            witness_id="KEEPER:witness1",
            signature=b"sig1",
        )

        event_writer_mock.write_event.assert_awaited()
        call_args = event_writer_mock.write_event.call_args
        assert call_args.kwargs["event_type"] == "ceremony.key_generation.witnessed"


class TestExecuteCeremony:
    """Tests for execute_ceremony method."""

    async def _setup_approved_ceremony(
        self,
        service: KeyGenerationCeremonyService,
        keeper_id: str = "KEEPER:alice",
        ceremony_type: CeremonyType = CeremonyType.NEW_KEEPER_KEY,
        old_key_id: str | None = None,
    ) -> KeyGenerationCeremony:
        """Helper to create an APPROVED ceremony."""
        ceremony = await service.start_ceremony(
            keeper_id=keeper_id,
            ceremony_type=ceremony_type,
            initiator_id="KEEPER:admin",
            old_key_id=old_key_id,
        )

        # Add required witnesses
        for i in range(REQUIRED_WITNESSES):
            ceremony = await service.add_witness(
                ceremony_id=str(ceremony.id),
                witness_id=f"KEEPER:witness{i}",
                signature=f"sig{i}".encode(),
            )

        return ceremony

    @pytest.mark.asyncio
    async def test_execute_ceremony_generates_and_registers_key(
        self,
        service: KeyGenerationCeremonyService,
        key_registry: KeeperKeyRegistryStub,
    ) -> None:
        """Execute ceremony generates and registers new key."""
        ceremony = await self._setup_approved_ceremony(service)

        completed = await service.execute_ceremony(str(ceremony.id))

        assert completed.state == CeremonyState.COMPLETED
        assert completed.new_key_id is not None
        assert completed.completed_at is not None

        # Verify key registered
        assert key_registry.get_key_count() == 1

    @pytest.mark.asyncio
    async def test_execute_ceremony_sets_transition_for_rotation(
        self,
        service: KeyGenerationCeremonyService,
        key_registry: KeeperKeyRegistryStub,
    ) -> None:
        """Execute rotation ceremony sets 30-day transition period (ADR-4)."""
        # Pre-register old key
        from src.domain.models.keeper_key import KeeperKey

        old_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:bob",
            key_id="old-key-123",
            public_key=b"\x00" * 32,
            active_from=datetime.now(timezone.utc) - timedelta(days=365),
            active_until=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=365),
        )
        key_registry.add_keeper_key(old_key)

        ceremony = await self._setup_approved_ceremony(
            service,
            keeper_id="KEEPER:bob",
            ceremony_type=CeremonyType.KEY_ROTATION,
            old_key_id="old-key-123",
        )

        completed = await service.execute_ceremony(str(ceremony.id))

        assert completed.transition_end_at is not None
        # Check transition is ~30 days from now
        expected_transition_end = datetime.now(timezone.utc) + timedelta(
            days=TRANSITION_PERIOD_DAYS
        )
        delta = abs(
            (completed.transition_end_at - expected_transition_end).total_seconds()
        )
        assert delta < 5  # Within 5 seconds tolerance

    @pytest.mark.asyncio
    async def test_execute_ceremony_rejects_non_approved_state(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Execute ceremony rejects non-APPROVED state."""
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        with pytest.raises(InvalidCeremonyStateError) as exc_info:
            await service.execute_ceremony(str(ceremony.id))

        assert "FP-4" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_ceremony_not_found(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Execute ceremony raises not found for missing ceremony."""
        with pytest.raises(CeremonyNotFoundError) as exc_info:
            await service.execute_ceremony(str(uuid4()))

        assert "FR69" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_ceremony_halt_check_first(
        self,
        service_with_halt_guard: KeyGenerationCeremonyService,
        halt_guard_mock: AsyncMock,
    ) -> None:
        """Execute ceremony checks halt state first (CT-11)."""
        ceremony = await self._setup_approved_ceremony(service_with_halt_guard)

        # Reset mock to isolate execute call
        halt_guard_mock.check_write_allowed.reset_mock()

        await service_with_halt_guard.execute_ceremony(str(ceremony.id))

        halt_guard_mock.check_write_allowed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_ceremony_writes_completed_event(
        self,
        service_with_event_writer: KeyGenerationCeremonyService,
        event_writer_mock: AsyncMock,
    ) -> None:
        """Execute ceremony writes completed event."""
        ceremony = await self._setup_approved_ceremony(service_with_event_writer)

        # Reset mock to isolate execute event
        event_writer_mock.write_event.reset_mock()

        await service_with_event_writer.execute_ceremony(str(ceremony.id))

        event_writer_mock.write_event.assert_awaited()
        call_args = event_writer_mock.write_event.call_args
        assert call_args.kwargs["event_type"] == "ceremony.key_generation.completed"


class TestCheckCeremonyTimeout:
    """Tests for check_ceremony_timeout method."""

    @pytest.mark.asyncio
    async def test_check_timeout_expires_timed_out_ceremonies(
        self,
        service: KeyGenerationCeremonyService,
        ceremony_repo: KeyGenerationCeremonyStub,
    ) -> None:
        """Check timeout expires timed out ceremonies (VAL-2).

        Uses EXPIRED state (distinct from FAILED) to indicate timeout
        vs. error conditions per LOW-1 fix.
        """
        # Create ceremony with old created_at
        old_time = datetime.now(timezone.utc) - timedelta(
            seconds=CEREMONY_TIMEOUT_SECONDS + 60
        )
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.PENDING,
            witnesses=[],
            created_at=old_time,
        )
        ceremony_repo.add_ceremony(ceremony)

        expired = await service.check_ceremony_timeout()

        assert len(expired) == 1
        assert expired[0].state == CeremonyState.EXPIRED
        assert "VAL-2" in (expired[0].failure_reason or "")

    @pytest.mark.asyncio
    async def test_check_timeout_ignores_recent_ceremonies(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Check timeout ignores recent ceremonies."""
        # Create recent ceremony
        await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        failed = await service.check_ceremony_timeout()

        assert len(failed) == 0

    @pytest.mark.asyncio
    async def test_check_timeout_ignores_completed_ceremonies(
        self,
        service: KeyGenerationCeremonyService,
        ceremony_repo: KeyGenerationCeremonyStub,
    ) -> None:
        """Check timeout ignores completed ceremonies."""
        # Create old but completed ceremony
        old_time = datetime.now(timezone.utc) - timedelta(
            seconds=CEREMONY_TIMEOUT_SECONDS + 60
        )
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.COMPLETED,  # Terminal state
            witnesses=[],
            created_at=old_time,
        )
        ceremony_repo.add_ceremony(ceremony)

        failed = await service.check_ceremony_timeout()

        assert len(failed) == 0

    @pytest.mark.asyncio
    async def test_check_timeout_writes_failed_events(
        self,
        service_with_event_writer: KeyGenerationCeremonyService,
        ceremony_repo: KeyGenerationCeremonyStub,
        event_writer_mock: AsyncMock,
    ) -> None:
        """Check timeout writes failed event for each timeout."""
        # Create old ceremony
        old_time = datetime.now(timezone.utc) - timedelta(
            seconds=CEREMONY_TIMEOUT_SECONDS + 60
        )
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.PENDING,
            witnesses=[],
            created_at=old_time,
        )
        ceremony_repo.add_ceremony(ceremony)

        # Inject ceremony_repo into service
        service_with_event_writer._ceremony_repo = ceremony_repo

        await service_with_event_writer.check_ceremony_timeout()

        event_writer_mock.write_event.assert_awaited()
        call_args = event_writer_mock.write_event.call_args
        assert call_args.kwargs["event_type"] == "ceremony.key_generation.failed"


class TestGetCeremony:
    """Tests for get_ceremony method."""

    @pytest.mark.asyncio
    async def test_get_ceremony_returns_ceremony(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Get ceremony returns existing ceremony."""
        created = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        retrieved = await service.get_ceremony(str(created.id))

        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_get_ceremony_returns_none_for_missing(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Get ceremony returns None for missing ceremony."""
        result = await service.get_ceremony(str(uuid4()))

        assert result is None


class TestGetActiveCeremonies:
    """Tests for get_active_ceremonies method."""

    @pytest.mark.asyncio
    async def test_get_active_ceremonies_returns_active(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Get active ceremonies returns non-terminal ceremonies."""
        await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        active = await service.get_active_ceremonies()

        assert len(active) == 1

    @pytest.mark.asyncio
    async def test_get_active_ceremonies_excludes_completed(
        self,
        service: KeyGenerationCeremonyService,
        ceremony_repo: KeyGenerationCeremonyStub,
    ) -> None:
        """Get active ceremonies excludes completed ceremonies."""
        ceremony = KeyGenerationCeremony(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            state=CeremonyState.COMPLETED,
            witnesses=[],
        )
        ceremony_repo.add_ceremony(ceremony)

        active = await service.get_active_ceremonies()

        assert len(active) == 0
