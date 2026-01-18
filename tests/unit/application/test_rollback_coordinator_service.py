"""Unit tests for RollbackCoordinatorService (Story 3.10, Task 8).

Tests the application service implementing rollback coordination.

Constitutional Constraints:
- FR143: Rollback for infrastructure recovery, logged, no event deletion
- CT-11: Rollback must be witnessed
- CT-13: Halt required before rollback
- PREVENT_DELETE: Events marked orphaned, never deleted
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.rollback_coordinator_service import (
    RollbackCoordinatorService,
)
from src.domain.errors.halt_clear import InsufficientApproversError
from src.domain.errors.rollback import (
    CheckpointNotFoundError,
    InvalidRollbackTargetError,
    RollbackNotPermittedError,
)
from src.domain.models.ceremony_evidence import (
    ApproverSignature,
    CeremonyEvidence,
)
from src.domain.models.checkpoint import Checkpoint
from src.infrastructure.stubs.checkpoint_repository_stub import CheckpointRepositoryStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def checkpoint_repo() -> CheckpointRepositoryStub:
    """Create checkpoint repository stub."""
    return CheckpointRepositoryStub()


@pytest.fixture
def service(
    halt_checker: HaltCheckerStub,
    checkpoint_repo: CheckpointRepositoryStub,
) -> RollbackCoordinatorService:
    """Create rollback coordinator service."""
    return RollbackCoordinatorService(
        halt_checker=halt_checker,
        checkpoint_repository=checkpoint_repo,
    )


@pytest.fixture
def sample_checkpoint() -> Checkpoint:
    """Create sample checkpoint for tests."""
    return Checkpoint(
        checkpoint_id=uuid4(),
        event_sequence=500,
        timestamp=datetime.now(timezone.utc),
        anchor_hash="a" * 64,
        anchor_type="periodic",
        creator_id="checkpoint-service",
    )


@pytest.fixture
def valid_ceremony_evidence() -> CeremonyEvidence:
    """Create valid ceremony evidence with 2 keepers."""
    return CeremonyEvidence(
        ceremony_id=uuid4(),
        ceremony_type="rollback",
        approvers=(
            ApproverSignature(
                keeper_id="keeper-001",
                signature=b"signature1",
                signed_at=datetime.now(timezone.utc),
            ),
            ApproverSignature(
                keeper_id="keeper-002",
                signature=b"signature2",
                signed_at=datetime.now(timezone.utc),
            ),
        ),
        created_at=datetime.now(timezone.utc),
    )


class TestQueryCheckpoints:
    """Tests for query_checkpoints method."""

    @pytest.mark.asyncio
    async def test_query_checkpoints_returns_all_available(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoint: Checkpoint,
    ) -> None:
        """query_checkpoints should return all available checkpoints."""
        cp2 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=1000,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="b" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        checkpoint_repo.seed_checkpoints([sample_checkpoint, cp2])

        result = await service.query_checkpoints()

        assert len(result) == 2
        assert sample_checkpoint in result
        assert cp2 in result

    @pytest.mark.asyncio
    async def test_query_checkpoints_empty_when_none(
        self,
        service: RollbackCoordinatorService,
    ) -> None:
        """query_checkpoints should return empty list when no checkpoints."""
        result = await service.query_checkpoints()

        assert result == []


class TestSelectRollbackTarget:
    """Tests for select_rollback_target method."""

    @pytest.mark.asyncio
    async def test_select_target_requires_halt(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoint: Checkpoint,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """select_rollback_target should require system to be halted."""
        checkpoint_repo.seed_checkpoints([sample_checkpoint])
        halt_checker.set_halted(False)

        with pytest.raises(RollbackNotPermittedError) as exc:
            await service.select_rollback_target(
                checkpoint_id=sample_checkpoint.checkpoint_id,
                selecting_keepers=("keeper-001",),
                reason="Test",
            )

        assert "halted" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_select_target_creates_event_payload(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoint: Checkpoint,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """select_rollback_target should create event payload."""
        checkpoint_repo.seed_checkpoints([sample_checkpoint])
        halt_checker.set_halted(True)

        payload = await service.select_rollback_target(
            checkpoint_id=sample_checkpoint.checkpoint_id,
            selecting_keepers=("keeper-001", "keeper-002"),
            reason="Fork detected",
        )

        assert payload.target_checkpoint_id == sample_checkpoint.checkpoint_id
        assert payload.target_event_sequence == sample_checkpoint.event_sequence
        assert payload.selecting_keepers == ("keeper-001", "keeper-002")
        assert payload.selection_reason == "Fork detected"

    @pytest.mark.asyncio
    async def test_select_target_validates_checkpoint_exists(
        self,
        service: RollbackCoordinatorService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """select_rollback_target should validate checkpoint exists."""
        halt_checker.set_halted(True)
        nonexistent_id = uuid4()

        with pytest.raises(CheckpointNotFoundError) as exc:
            await service.select_rollback_target(
                checkpoint_id=nonexistent_id,
                selecting_keepers=("keeper-001",),
                reason="Test",
            )

        assert str(nonexistent_id) in str(exc.value)

    @pytest.mark.asyncio
    async def test_select_target_rejects_invalid_checkpoint(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """select_rollback_target should reject nonexistent checkpoint."""
        halt_checker.set_halted(True)

        with pytest.raises(CheckpointNotFoundError):
            await service.select_rollback_target(
                checkpoint_id=uuid4(),
                selecting_keepers=("keeper-001",),
                reason="Test",
            )


class TestExecuteRollback:
    """Tests for execute_rollback method."""

    @pytest.mark.asyncio
    async def test_execute_rollback_requires_halt(
        self,
        service: RollbackCoordinatorService,
        halt_checker: HaltCheckerStub,
        valid_ceremony_evidence: CeremonyEvidence,
    ) -> None:
        """execute_rollback should require system to be halted."""
        halt_checker.set_halted(False)

        with pytest.raises(RollbackNotPermittedError) as exc:
            await service.execute_rollback(ceremony_evidence=valid_ceremony_evidence)

        assert "halted" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_execute_rollback_requires_target_selected(
        self,
        service: RollbackCoordinatorService,
        halt_checker: HaltCheckerStub,
        valid_ceremony_evidence: CeremonyEvidence,
    ) -> None:
        """execute_rollback should require target to be selected first."""
        halt_checker.set_halted(True)

        with pytest.raises(InvalidRollbackTargetError) as exc:
            await service.execute_rollback(ceremony_evidence=valid_ceremony_evidence)

        assert "select" in str(exc.value).lower() or "target" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_execute_rollback_creates_event_payload(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoint: Checkpoint,
        halt_checker: HaltCheckerStub,
        valid_ceremony_evidence: CeremonyEvidence,
    ) -> None:
        """execute_rollback should create event payload."""
        checkpoint_repo.seed_checkpoints([sample_checkpoint])
        halt_checker.set_halted(True)

        # First select target
        await service.select_rollback_target(
            checkpoint_id=sample_checkpoint.checkpoint_id,
            selecting_keepers=("keeper-001", "keeper-002"),
            reason="Fork detected",
        )

        # Then execute
        payload = await service.execute_rollback(
            ceremony_evidence=valid_ceremony_evidence
        )

        assert payload.target_checkpoint_id == sample_checkpoint.checkpoint_id
        assert payload.new_head_sequence == sample_checkpoint.event_sequence
        assert payload.ceremony_id == valid_ceremony_evidence.ceremony_id

    @pytest.mark.asyncio
    async def test_execute_rollback_validates_ceremony(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoint: Checkpoint,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """execute_rollback should validate ceremony evidence."""
        checkpoint_repo.seed_checkpoints([sample_checkpoint])
        halt_checker.set_halted(True)

        # Select target
        await service.select_rollback_target(
            checkpoint_id=sample_checkpoint.checkpoint_id,
            selecting_keepers=("keeper-001",),
            reason="Test",
        )

        # Invalid ceremony with only 1 approver
        invalid_ceremony = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type="rollback",
            approvers=(
                ApproverSignature(
                    keeper_id="keeper-001",
                    signature=b"signature1",
                    signed_at=datetime.now(timezone.utc),
                ),
            ),
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(InsufficientApproversError):
            await service.execute_rollback(ceremony_evidence=invalid_ceremony)


class TestGetStatus:
    """Tests for get_rollback_status method."""

    @pytest.mark.asyncio
    async def test_get_status_returns_state(
        self,
        service: RollbackCoordinatorService,
    ) -> None:
        """get_rollback_status should return current state."""
        status = await service.get_rollback_status()

        assert "in_progress" in status
        assert status["in_progress"] is False
        assert status["selected_checkpoint_id"] is None

    @pytest.mark.asyncio
    async def test_get_status_after_selection(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoint: Checkpoint,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """get_rollback_status should reflect target selection."""
        checkpoint_repo.seed_checkpoints([sample_checkpoint])
        halt_checker.set_halted(True)

        await service.select_rollback_target(
            checkpoint_id=sample_checkpoint.checkpoint_id,
            selecting_keepers=("keeper-001",),
            reason="Test",
        )

        status = await service.get_rollback_status()

        assert status["in_progress"] is True
        assert status["selected_checkpoint_id"] == str(sample_checkpoint.checkpoint_id)
        assert (
            status["selected_checkpoint_sequence"] == sample_checkpoint.event_sequence
        )
