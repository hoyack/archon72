"""Integration tests for Key Generation Ceremony (FR69, ADR-4).

End-to-end tests for witnessed key generation ceremonies including
full workflow validation and constitutional constraint enforcement.

Constitutional Constraints:
- FR69: Keeper keys SHALL be generated through witnessed ceremony
- CT-11: HALT CHECK FIRST - silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- VAL-2: Ceremony timeout enforcement (1 hour max)
- CM-5: Single ceremony at a time per Keeper
- ADR-4: Key rotation includes 30-day transition period
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.services.key_generation_ceremony_service import (
    KeyGenerationCeremonyService,
)
from src.domain.errors.key_generation_ceremony import (
    CeremonyConflictError,
    DuplicateWitnessError,
    InvalidCeremonyStateError,
)
from src.domain.models.ceremony_witness import WitnessType
from src.domain.models.keeper_key import KeeperKey
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


class TestCeremonyWorkflow:
    """Integration tests for complete ceremony workflow."""

    @pytest.fixture
    def ceremony_repo(self) -> KeyGenerationCeremonyStub:
        """Create ceremony repository stub."""
        return KeyGenerationCeremonyStub()

    @pytest.fixture
    def key_registry(self) -> KeeperKeyRegistryStub:
        """Create key registry stub."""
        return KeeperKeyRegistryStub(with_dev_key=False)

    @pytest.fixture
    def service(
        self,
        ceremony_repo: KeyGenerationCeremonyStub,
        key_registry: KeeperKeyRegistryStub,
    ) -> KeyGenerationCeremonyService:
        """Create service with stubs."""
        from unittest.mock import AsyncMock, MagicMock

        from src.application.ports.hsm import HSMMode

        hsm = MagicMock()
        hsm.get_primary_key_id = MagicMock(return_value="test-key")
        hsm.generate_key_pair = AsyncMock(return_value="hsm-generated-key-id")
        hsm.get_public_key_bytes = AsyncMock(return_value=b"\x00" * 32)
        hsm.get_mode = AsyncMock(return_value=HSMMode.DEVELOPMENT)
        return KeyGenerationCeremonyService(
            hsm=hsm,
            key_registry=key_registry,
            ceremony_repo=ceremony_repo,
        )

    @pytest.mark.asyncio
    async def test_complete_new_key_ceremony_workflow(
        self,
        service: KeyGenerationCeremonyService,
        key_registry: KeeperKeyRegistryStub,
    ) -> None:
        """FR69: Complete workflow for new Keeper key generation.

        Tests:
        1. Start ceremony -> PENDING
        2. Add required witnesses -> auto-transitions to APPROVED
        3. Execute ceremony -> COMPLETED with new key registered
        """
        # Step 1: Start ceremony
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )
        assert ceremony.state == CeremonyState.PENDING
        assert len(ceremony.witnesses) == 0

        # Step 2: Add witnesses (3 required per CT-12)
        for i in range(REQUIRED_WITNESSES):
            ceremony = await service.add_witness(
                ceremony_id=str(ceremony.id),
                witness_id=f"KEEPER:witness{i}",
                signature=f"ed25519-sig-{i}".encode(),
                witness_type=WitnessType.KEEPER,
            )

        # Auto-transitions to APPROVED when threshold met
        assert ceremony.state == CeremonyState.APPROVED
        assert len(ceremony.witnesses) == REQUIRED_WITNESSES

        # Step 3: Execute ceremony
        completed = await service.execute_ceremony(str(ceremony.id))

        assert completed.state == CeremonyState.COMPLETED
        assert completed.new_key_id is not None
        assert completed.completed_at is not None

        # Verify key registered in registry
        assert key_registry.get_key_count() == 1

    @pytest.mark.asyncio
    async def test_complete_key_rotation_ceremony_workflow(
        self,
        service: KeyGenerationCeremonyService,
        key_registry: KeeperKeyRegistryStub,
    ) -> None:
        """ADR-4: Complete workflow for key rotation with transition period.

        Tests:
        1. Pre-existing key in registry
        2. Start rotation ceremony with old_key_id
        3. Execute ceremony -> 30-day transition period set
        4. Both keys valid during transition
        """
        # Pre-register existing key
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

        # Start rotation ceremony
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:bob",
            ceremony_type=CeremonyType.KEY_ROTATION,
            initiator_id="KEEPER:admin",
            old_key_id="old-key-123",
        )
        assert ceremony.old_key_id == "old-key-123"

        # Add required witnesses
        for i in range(REQUIRED_WITNESSES):
            ceremony = await service.add_witness(
                ceremony_id=str(ceremony.id),
                witness_id=f"KEEPER:witness{i}",
                signature=f"ed25519-sig-{i}".encode(),
            )

        # Execute ceremony
        completed = await service.execute_ceremony(str(ceremony.id))

        # Verify transition period (ADR-4: 30 days)
        assert completed.transition_end_at is not None
        expected_end = datetime.now(timezone.utc) + timedelta(
            days=TRANSITION_PERIOD_DAYS
        )
        delta = abs((completed.transition_end_at - expected_end).total_seconds())
        assert delta < 5  # Within 5 seconds

        # Verify both keys exist
        assert key_registry.get_key_count() == 2


class TestConstitutionalConstraints:
    """Integration tests for constitutional constraint enforcement."""

    @pytest.fixture
    def ceremony_repo(self) -> KeyGenerationCeremonyStub:
        """Create ceremony repository stub."""
        return KeyGenerationCeremonyStub()

    @pytest.fixture
    def key_registry(self) -> KeeperKeyRegistryStub:
        """Create key registry stub."""
        return KeeperKeyRegistryStub(with_dev_key=False)

    @pytest.fixture
    def service(
        self,
        ceremony_repo: KeyGenerationCeremonyStub,
        key_registry: KeeperKeyRegistryStub,
    ) -> KeyGenerationCeremonyService:
        """Create service with stubs."""
        from unittest.mock import AsyncMock, MagicMock

        from src.application.ports.hsm import HSMMode

        hsm = MagicMock()
        hsm.generate_key_pair = AsyncMock(return_value="hsm-generated-key-id")
        hsm.get_public_key_bytes = AsyncMock(return_value=b"\x00" * 32)
        hsm.get_mode = AsyncMock(return_value=HSMMode.DEVELOPMENT)
        return KeyGenerationCeremonyService(
            hsm=hsm,
            key_registry=key_registry,
            ceremony_repo=ceremony_repo,
        )

    @pytest.mark.asyncio
    async def test_cm5_single_ceremony_per_keeper(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """CM-5: Single active ceremony per Keeper enforced."""
        # Create first ceremony
        await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        # Second ceremony for same Keeper rejected
        with pytest.raises(CeremonyConflictError) as exc_info:
            await service.start_ceremony(
                keeper_id="KEEPER:alice",
                ceremony_type=CeremonyType.NEW_KEEPER_KEY,
                initiator_id="KEEPER:admin",
            )

        assert "CM-5" in str(exc_info.value)

        # Different Keeper is allowed
        ceremony2 = await service.start_ceremony(
            keeper_id="KEEPER:bob",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )
        assert ceremony2.keeper_id == "KEEPER:bob"

    @pytest.mark.asyncio
    async def test_ct12_witness_threshold_enforced(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """CT-12: Required witness threshold enforced before execution."""
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        # Add only 2 witnesses (less than required 3)
        for i in range(REQUIRED_WITNESSES - 1):
            await service.add_witness(
                ceremony_id=str(ceremony.id),
                witness_id=f"KEEPER:witness{i}",
                signature=f"sig{i}".encode(),
            )

        # Should still be PENDING (not APPROVED)
        ceremony = await service.get_ceremony(str(ceremony.id))
        assert ceremony is not None
        assert ceremony.state == CeremonyState.PENDING

    @pytest.mark.asyncio
    async def test_ct12_duplicate_witness_rejected(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """CT-12: Duplicate witness signatures rejected."""
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        # First witness accepted
        await service.add_witness(
            ceremony_id=str(ceremony.id),
            witness_id="KEEPER:witness1",
            signature=b"sig1",
        )

        # Same witness rejected
        with pytest.raises(DuplicateWitnessError) as exc_info:
            await service.add_witness(
                ceremony_id=str(ceremony.id),
                witness_id="KEEPER:witness1",
                signature=b"sig1-again",
            )

        assert "CT-12" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_val2_ceremony_timeout(
        self,
        service: KeyGenerationCeremonyService,
        ceremony_repo: KeyGenerationCeremonyStub,
    ) -> None:
        """VAL-2: Ceremony timeout enforcement (1 hour max).

        Uses EXPIRED state (distinct from FAILED) to indicate timeout
        vs. error conditions per LOW-1 fix.
        """
        # Create ceremony with old timestamp
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

        # Run timeout check
        expired = await service.check_ceremony_timeout()

        # Ceremony should be expired (not failed - timeout is distinct from error)
        assert len(expired) == 1
        assert expired[0].state == CeremonyState.EXPIRED
        assert "VAL-2" in (expired[0].failure_reason or "")

    @pytest.mark.asyncio
    async def test_fp4_state_machine_enforced(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """FP-4: State machine transitions enforced."""
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        # Cannot execute from PENDING state
        with pytest.raises(InvalidCeremonyStateError) as exc_info:
            await service.execute_ceremony(str(ceremony.id))

        assert "FP-4" in str(exc_info.value)


class TestWitnessTypes:
    """Integration tests for different witness types."""

    @pytest.fixture
    def ceremony_repo(self) -> KeyGenerationCeremonyStub:
        """Create ceremony repository stub."""
        return KeyGenerationCeremonyStub()

    @pytest.fixture
    def key_registry(self) -> KeeperKeyRegistryStub:
        """Create key registry stub."""
        return KeeperKeyRegistryStub(with_dev_key=False)

    @pytest.fixture
    def service(
        self,
        ceremony_repo: KeyGenerationCeremonyStub,
        key_registry: KeeperKeyRegistryStub,
    ) -> KeyGenerationCeremonyService:
        """Create service with stubs."""
        from unittest.mock import AsyncMock, MagicMock

        from src.application.ports.hsm import HSMMode

        hsm = MagicMock()
        hsm.generate_key_pair = AsyncMock(return_value="hsm-generated-key-id")
        hsm.get_public_key_bytes = AsyncMock(return_value=b"\x00" * 32)
        hsm.get_mode = AsyncMock(return_value=HSMMode.DEVELOPMENT)
        return KeyGenerationCeremonyService(
            hsm=hsm,
            key_registry=key_registry,
            ceremony_repo=ceremony_repo,
        )

    @pytest.mark.asyncio
    async def test_mixed_witness_types_accepted(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Different witness types can be mixed in ceremony."""
        ceremony = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
            initiator_id="KEEPER:admin",
        )

        # Add KEEPER witness
        await service.add_witness(
            ceremony_id=str(ceremony.id),
            witness_id="KEEPER:witness1",
            signature=b"sig1",
            witness_type=WitnessType.KEEPER,
        )

        # Add SYSTEM witness
        await service.add_witness(
            ceremony_id=str(ceremony.id),
            witness_id="SYSTEM:hsm",
            signature=b"sig2",
            witness_type=WitnessType.SYSTEM,
        )

        # Add EXTERNAL witness
        ceremony = await service.add_witness(
            ceremony_id=str(ceremony.id),
            witness_id="EXTERNAL:auditor",
            signature=b"sig3",
            witness_type=WitnessType.EXTERNAL,
        )

        assert ceremony.state == CeremonyState.APPROVED
        assert len(ceremony.witnesses) == 3

        witness_types = {w.witness_type for w in ceremony.witnesses}
        assert WitnessType.KEEPER in witness_types
        assert WitnessType.SYSTEM in witness_types
        assert WitnessType.EXTERNAL in witness_types


class TestKeyRegistryIntegration:
    """Integration tests for key registry interaction."""

    @pytest.fixture
    def ceremony_repo(self) -> KeyGenerationCeremonyStub:
        """Create ceremony repository stub."""
        return KeyGenerationCeremonyStub()

    @pytest.fixture
    def key_registry(self) -> KeeperKeyRegistryStub:
        """Create key registry stub."""
        return KeeperKeyRegistryStub(with_dev_key=False)

    @pytest.fixture
    def service(
        self,
        ceremony_repo: KeyGenerationCeremonyStub,
        key_registry: KeeperKeyRegistryStub,
    ) -> KeyGenerationCeremonyService:
        """Create service with stubs."""
        from unittest.mock import AsyncMock, MagicMock

        from src.application.ports.hsm import HSMMode

        hsm = MagicMock()
        hsm.generate_key_pair = AsyncMock(return_value="hsm-generated-key-id")
        hsm.get_public_key_bytes = AsyncMock(return_value=b"\x00" * 32)
        hsm.get_mode = AsyncMock(return_value=HSMMode.DEVELOPMENT)
        return KeyGenerationCeremonyService(
            hsm=hsm,
            key_registry=key_registry,
            ceremony_repo=ceremony_repo,
        )

    async def _complete_ceremony(
        self,
        service: KeyGenerationCeremonyService,
        keeper_id: str,
        ceremony_type: CeremonyType,
        old_key_id: str | None = None,
    ) -> KeyGenerationCeremony:
        """Helper to complete a ceremony."""
        ceremony = await service.start_ceremony(
            keeper_id=keeper_id,
            ceremony_type=ceremony_type,
            initiator_id="KEEPER:admin",
            old_key_id=old_key_id,
        )
        for i in range(REQUIRED_WITNESSES):
            ceremony = await service.add_witness(
                ceremony_id=str(ceremony.id),
                witness_id=f"KEEPER:w{i}",
                signature=f"s{i}".encode(),
            )
        return await service.execute_ceremony(str(ceremony.id))

    @pytest.mark.asyncio
    async def test_new_key_registered_after_completion(
        self,
        service: KeyGenerationCeremonyService,
        key_registry: KeeperKeyRegistryStub,
    ) -> None:
        """New key is registered in key registry after ceremony completion."""
        completed = await self._complete_ceremony(
            service,
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        # Key should be in registry
        key = await key_registry.get_key_by_id(completed.new_key_id)
        assert key is not None
        assert key.keeper_id == "KEEPER:alice"

    @pytest.mark.asyncio
    async def test_old_key_deactivated_after_rotation(
        self,
        service: KeyGenerationCeremonyService,
        key_registry: KeeperKeyRegistryStub,
    ) -> None:
        """Old key has active_until set after rotation (ADR-4)."""
        # Pre-register old key
        old_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:bob",
            key_id="old-key-456",
            public_key=b"\x00" * 32,
            active_from=datetime.now(timezone.utc) - timedelta(days=365),
            active_until=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=365),
        )
        key_registry.add_keeper_key(old_key)

        # Complete rotation
        await self._complete_ceremony(
            service,
            keeper_id="KEEPER:bob",
            ceremony_type=CeremonyType.KEY_ROTATION,
            old_key_id="old-key-456",
        )

        # Old key should have active_until set
        deactivated_key = await key_registry.get_key_by_id("old-key-456")
        assert deactivated_key is not None
        assert deactivated_key.active_until is not None

    @pytest.mark.asyncio
    async def test_can_start_new_ceremony_after_completion(
        self,
        service: KeyGenerationCeremonyService,
    ) -> None:
        """Can start new ceremony for same Keeper after previous completes."""
        # Complete first ceremony
        await self._complete_ceremony(
            service,
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.NEW_KEEPER_KEY,
        )

        # Can start another (previous is not active anymore)
        ceremony2 = await service.start_ceremony(
            keeper_id="KEEPER:alice",
            ceremony_type=CeremonyType.KEY_ROTATION,
            initiator_id="KEEPER:admin",
            old_key_id="some-key",
        )

        assert ceremony2.keeper_id == "KEEPER:alice"
        assert ceremony2.state == CeremonyState.PENDING
