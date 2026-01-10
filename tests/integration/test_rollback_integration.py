"""Integration tests for rollback flow (Story 3.10, Task 10).

End-to-end tests for the complete rollback flow using stubs.

Constitutional Constraints:
- FR143: Rollback to checkpoint for infrastructure recovery
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
from src.domain.errors.rollback import (
    CheckpointNotFoundError,
    InvalidRollbackTargetError,
    RollbackNotPermittedError,
)
from src.domain.events.rollback_completed import ROLLBACK_COMPLETED_EVENT_TYPE
from src.domain.events.rollback_target_selected import ROLLBACK_TARGET_SELECTED_EVENT_TYPE
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
    stub = HaltCheckerStub()
    stub.set_halted(True)  # Default to halted for rollback tests
    return stub


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
def sample_checkpoints() -> list[Checkpoint]:
    """Create sample checkpoints for tests."""
    return [
        Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            anchor_hash="a" * 64,
            anchor_type="genesis",
            creator_id="system",
        ),
        Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=500,
            timestamp=datetime(2025, 1, 8, 0, 0, 0, tzinfo=timezone.utc),
            anchor_hash="b" * 64,
            anchor_type="periodic",
            creator_id="checkpoint-service",
        ),
        Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=1000,
            timestamp=datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            anchor_hash="c" * 64,
            anchor_type="periodic",
            creator_id="checkpoint-service",
        ),
    ]


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
    """Integration tests for checkpoint query (AC1)."""

    @pytest.mark.asyncio
    async def test_query_checkpoints_returns_all_anchors(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoints: list[Checkpoint],
    ) -> None:
        """Query should return all available checkpoint anchors (AC1)."""
        checkpoint_repo.seed_checkpoints(sample_checkpoints)

        result = await service.query_checkpoints()

        assert len(result) == 3
        # Should be sorted by sequence
        assert result[0].event_sequence == 100
        assert result[1].event_sequence == 500
        assert result[2].event_sequence == 1000
        # Should have all required fields
        for cp in result:
            assert cp.checkpoint_id is not None
            assert cp.event_sequence >= 0
            assert cp.timestamp is not None
            assert len(cp.anchor_hash) == 64


class TestSelectTarget:
    """Integration tests for target selection (AC2)."""

    @pytest.mark.asyncio
    async def test_select_target_creates_witnessed_event(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoints: list[Checkpoint],
    ) -> None:
        """Select target should create RollbackTargetSelectedEvent payload (AC2)."""
        checkpoint_repo.seed_checkpoints(sample_checkpoints)
        target = sample_checkpoints[1]  # Sequence 500

        payload = await service.select_rollback_target(
            checkpoint_id=target.checkpoint_id,
            selecting_keepers=("keeper-001", "keeper-002"),
            reason="Fork detected at sequence 1200",
        )

        # Should create valid payload for witnessed event
        assert payload.target_checkpoint_id == target.checkpoint_id
        assert payload.target_event_sequence == 500
        assert payload.target_anchor_hash == target.anchor_hash
        assert payload.selecting_keepers == ("keeper-001", "keeper-002")
        assert "Fork detected" in payload.selection_reason

    @pytest.mark.asyncio
    async def test_rollback_requires_halt_state(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoints: list[Checkpoint],
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Rollback should require system to be halted (CT-13)."""
        checkpoint_repo.seed_checkpoints(sample_checkpoints)
        halt_checker.set_halted(False)  # Not halted

        with pytest.raises(RollbackNotPermittedError) as exc:
            await service.select_rollback_target(
                checkpoint_id=sample_checkpoints[0].checkpoint_id,
                selecting_keepers=("keeper-001",),
                reason="Test",
            )

        assert "halted" in str(exc.value).lower()


class TestExecuteRollback:
    """Integration tests for rollback execution (AC3)."""

    @pytest.mark.asyncio
    async def test_execute_rollback_creates_witnessed_event(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoints: list[Checkpoint],
        valid_ceremony_evidence: CeremonyEvidence,
    ) -> None:
        """Execute should create RollbackCompletedEvent payload (AC3)."""
        checkpoint_repo.seed_checkpoints(sample_checkpoints)
        target = sample_checkpoints[1]  # Sequence 500

        # First select target
        await service.select_rollback_target(
            checkpoint_id=target.checkpoint_id,
            selecting_keepers=("keeper-001", "keeper-002"),
            reason="Fork detected",
        )

        # Then execute
        payload = await service.execute_rollback(
            ceremony_evidence=valid_ceremony_evidence
        )

        # Should create valid payload for witnessed event
        assert payload.target_checkpoint_id == target.checkpoint_id
        assert payload.new_head_sequence == target.event_sequence
        assert payload.ceremony_id == valid_ceremony_evidence.ceremony_id
        assert payload.approving_keepers == ("keeper-001", "keeper-002")

    @pytest.mark.asyncio
    async def test_rollback_requires_ceremony_evidence(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoints: list[Checkpoint],
    ) -> None:
        """Rollback should require valid ceremony evidence."""
        checkpoint_repo.seed_checkpoints(sample_checkpoints)

        # Select target
        await service.select_rollback_target(
            checkpoint_id=sample_checkpoints[0].checkpoint_id,
            selecting_keepers=("keeper-001",),
            reason="Test",
        )

        # Invalid ceremony with empty signature
        invalid_ceremony = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type="rollback",
            approvers=(
                ApproverSignature(
                    keeper_id="keeper-001",
                    signature=b"",  # Empty - invalid!
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

        with pytest.raises(Exception):  # InvalidCeremonyError
            await service.execute_rollback(ceremony_evidence=invalid_ceremony)


class TestConstitutionalCompliance:
    """Tests for constitutional compliance."""

    @pytest.mark.asyncio
    async def test_constitutional_compliance_fr143(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoints: list[Checkpoint],
        valid_ceremony_evidence: CeremonyEvidence,
    ) -> None:
        """FR143: Rollback for infrastructure recovery, logged."""
        checkpoint_repo.seed_checkpoints(sample_checkpoints)
        target = sample_checkpoints[0]

        # Select target
        select_payload = await service.select_rollback_target(
            checkpoint_id=target.checkpoint_id,
            selecting_keepers=("keeper-001", "keeper-002"),
            reason="Infrastructure recovery",
        )

        # Execute rollback
        complete_payload = await service.execute_rollback(
            ceremony_evidence=valid_ceremony_evidence
        )

        # Both operations create event payloads for logging
        assert select_payload.signable_content() is not None
        assert complete_payload.signable_content() is not None

    @pytest.mark.asyncio
    async def test_orphaned_events_recorded_not_deleted(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoints: list[Checkpoint],
        valid_ceremony_evidence: CeremonyEvidence,
    ) -> None:
        """PREVENT_DELETE: Events marked orphaned, not deleted."""
        checkpoint_repo.seed_checkpoints(sample_checkpoints)
        target = sample_checkpoints[1]  # Sequence 500

        # Select and execute
        await service.select_rollback_target(
            checkpoint_id=target.checkpoint_id,
            selecting_keepers=("keeper-001",),
            reason="Test",
        )

        payload = await service.execute_rollback(
            ceremony_evidence=valid_ceremony_evidence
        )

        # The payload records orphaned event information
        # This allows the event store to mark (not delete) events
        assert payload.orphaned_event_count >= 0
        assert payload.orphaned_sequence_range is not None
        # The actual orphaning happens in the event store when
        # the RollbackCompletedEvent is processed


class TestFullRollbackFlow:
    """End-to-end rollback flow tests."""

    @pytest.mark.asyncio
    async def test_complete_rollback_flow(
        self,
        service: RollbackCoordinatorService,
        checkpoint_repo: CheckpointRepositoryStub,
        sample_checkpoints: list[Checkpoint],
        valid_ceremony_evidence: CeremonyEvidence,
    ) -> None:
        """Complete rollback flow: query -> select -> execute."""
        checkpoint_repo.seed_checkpoints(sample_checkpoints)

        # Step 1: Query checkpoints (AC1)
        checkpoints = await service.query_checkpoints()
        assert len(checkpoints) == 3

        # Step 2: Check status (should be idle)
        status = await service.get_rollback_status()
        assert status["in_progress"] is False

        # Step 3: Select target (AC2)
        target = checkpoints[1]  # Sequence 500
        select_payload = await service.select_rollback_target(
            checkpoint_id=target.checkpoint_id,
            selecting_keepers=("keeper-001", "keeper-002"),
            reason="Fork detected - reverting to checkpoint",
        )

        # Step 4: Check status (should be in progress)
        status = await service.get_rollback_status()
        assert status["in_progress"] is True
        assert status["selected_checkpoint_id"] == str(target.checkpoint_id)

        # Step 5: Execute rollback (AC3)
        complete_payload = await service.execute_rollback(
            ceremony_evidence=valid_ceremony_evidence
        )

        # Verify final state
        assert complete_payload.target_checkpoint_id == target.checkpoint_id
        assert complete_payload.new_head_sequence == target.event_sequence
        assert len(complete_payload.approving_keepers) == 2
