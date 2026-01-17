"""Unit tests for TwoPhaseEventEmitter service.

Story: consent-gov-1.6: Two-Phase Event Emission

Tests the TwoPhaseEventEmitter service that encapsulates the two-phase
emission pattern for Knight observability.

Constitutional Reference:
- AD-3: Two-phase event emission
- NFR-CONST-07: Witness statements cannot be suppressed
- NFR-OBS-01: Events observable within ≤1 second
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.two_phase_emitter_port import TwoPhaseEmitError
from src.application.services.governance.two_phase_event_emitter import (
    TwoPhaseEventEmitter,
)


@pytest.fixture
def mock_ledger() -> AsyncMock:
    """Create a mock governance ledger."""
    ledger = AsyncMock()
    # Configure append_event to return a persisted event with event_id
    def make_persisted_event(event):
        persisted = MagicMock()
        persisted.event_id = event.event_id
        persisted.event = event
        return persisted
    ledger.append_event = AsyncMock(side_effect=make_persisted_event)
    return ledger


@pytest.fixture
def mock_time_authority() -> MagicMock:
    """Create a mock time authority."""
    time_authority = MagicMock()
    time_authority.now.return_value = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
    return time_authority


@pytest.fixture
def emitter(mock_ledger: AsyncMock, mock_time_authority: MagicMock) -> TwoPhaseEventEmitter:
    """Create a TwoPhaseEventEmitter with mocked dependencies."""
    return TwoPhaseEventEmitter(mock_ledger, mock_time_authority)


class TestEmitIntent:
    """Tests for emit_intent method (AC1)."""

    @pytest.mark.asyncio
    async def test_emit_intent_returns_correlation_id(
        self, emitter: TwoPhaseEventEmitter
    ) -> None:
        """emit_intent should return a correlation_id UUID."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={"earl_id": "earl-1"},
        )

        assert isinstance(correlation_id, UUID)

    @pytest.mark.asyncio
    async def test_emit_intent_persists_to_ledger(
        self, emitter: TwoPhaseEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """emit_intent should persist an event to the ledger."""
        await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        mock_ledger.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_intent_creates_correct_event_type(
        self, emitter: TwoPhaseEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """emit_intent should create event with {branch}.intent.emitted type."""
        await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        # Get the event that was passed to append_event
        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        assert event.event_type == "executive.intent.emitted"

    @pytest.mark.asyncio
    async def test_emit_intent_tracks_pending(
        self, emitter: TwoPhaseEventEmitter
    ) -> None:
        """emit_intent should track the intent as pending."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={"key": "value"},
        )

        pending = await emitter.get_pending_intent(correlation_id)
        assert pending is not None
        assert pending["correlation_id"] == str(correlation_id)
        assert pending["operation_type"] == "executive.task.accept"
        assert pending["actor_id"] == "archon-42"

    @pytest.mark.asyncio
    async def test_emit_intent_uses_time_authority(
        self, emitter: TwoPhaseEventEmitter, mock_time_authority: MagicMock
    ) -> None:
        """emit_intent should use time authority for timestamp."""
        await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        mock_time_authority.now.assert_called_once()


class TestEmitCommit:
    """Tests for emit_commit method (AC2)."""

    @pytest.mark.asyncio
    async def test_emit_commit_on_success(
        self, emitter: TwoPhaseEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """emit_commit should persist a commit event to the ledger."""
        # First emit intent
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        # Then emit commit
        await emitter.emit_commit(
            correlation_id=correlation_id,
            result_payload={"new_state": "accepted"},
        )

        # Should have 2 calls: intent + commit
        assert mock_ledger.append_event.call_count == 2

    @pytest.mark.asyncio
    async def test_emit_commit_creates_correct_event_type(
        self, emitter: TwoPhaseEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """emit_commit should create event with {branch}.commit.confirmed type."""
        correlation_id = await emitter.emit_intent(
            operation_type="judicial.panel.convene",
            actor_id="archon-42",
            target_entity_id="panel-001",
            intent_payload={},
        )

        await emitter.emit_commit(
            correlation_id=correlation_id,
            result_payload={},
        )

        # Get the second event (commit)
        call_args = mock_ledger.append_event.call_args_list[1]
        event = call_args[0][0]
        assert event.event_type == "judicial.commit.confirmed"

    @pytest.mark.asyncio
    async def test_emit_commit_removes_from_pending(
        self, emitter: TwoPhaseEventEmitter
    ) -> None:
        """emit_commit should remove intent from pending tracking."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        # Verify pending before commit
        assert await emitter.get_pending_intent(correlation_id) is not None

        await emitter.emit_commit(
            correlation_id=correlation_id,
            result_payload={},
        )

        # Verify removed after commit
        assert await emitter.get_pending_intent(correlation_id) is None

    @pytest.mark.asyncio
    async def test_emit_commit_raises_for_unknown_correlation_id(
        self, emitter: TwoPhaseEventEmitter
    ) -> None:
        """emit_commit should raise TwoPhaseEmitError for unknown correlation_id."""
        unknown_id = uuid4()

        with pytest.raises(TwoPhaseEmitError) as exc_info:
            await emitter.emit_commit(
                correlation_id=unknown_id,
                result_payload={},
            )

        assert "No pending intent found" in str(exc_info.value)


class TestEmitFailure:
    """Tests for emit_failure method (AC3)."""

    @pytest.mark.asyncio
    async def test_emit_failure_on_error(
        self, emitter: TwoPhaseEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """emit_failure should persist a failure event to the ledger."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        await emitter.emit_failure(
            correlation_id=correlation_id,
            failure_reason="VALIDATION_FAILED",
            failure_details={"error": "Invalid state"},
        )

        assert mock_ledger.append_event.call_count == 2

    @pytest.mark.asyncio
    async def test_emit_failure_creates_correct_event_type(
        self, emitter: TwoPhaseEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """emit_failure should create event with {branch}.failure.recorded type."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        await emitter.emit_failure(
            correlation_id=correlation_id,
            failure_reason="ERROR",
            failure_details={},
        )

        call_args = mock_ledger.append_event.call_args_list[1]
        event = call_args[0][0]
        assert event.event_type == "executive.failure.recorded"

    @pytest.mark.asyncio
    async def test_emit_failure_removes_from_pending(
        self, emitter: TwoPhaseEventEmitter
    ) -> None:
        """emit_failure should remove intent from pending tracking."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        assert await emitter.get_pending_intent(correlation_id) is not None

        await emitter.emit_failure(
            correlation_id=correlation_id,
            failure_reason="ERROR",
            failure_details={},
        )

        assert await emitter.get_pending_intent(correlation_id) is None

    @pytest.mark.asyncio
    async def test_emit_failure_raises_for_unknown_correlation_id(
        self, emitter: TwoPhaseEventEmitter
    ) -> None:
        """emit_failure should raise TwoPhaseEmitError for unknown correlation_id."""
        unknown_id = uuid4()

        with pytest.raises(TwoPhaseEmitError) as exc_info:
            await emitter.emit_failure(
                correlation_id=unknown_id,
                failure_reason="ERROR",
                failure_details={},
            )

        assert "No pending intent found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_emit_failure_marks_orphan(
        self, emitter: TwoPhaseEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """emit_failure with ORPHAN_TIMEOUT should set was_orphan flag."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        await emitter.emit_failure(
            correlation_id=correlation_id,
            failure_reason="ORPHAN_TIMEOUT",
            failure_details={"timeout_seconds": 300},
        )

        call_args = mock_ledger.append_event.call_args_list[1]
        event = call_args[0][0]
        assert event.payload["was_orphan"] is True


class TestPendingIntentTracking:
    """Tests for pending intent tracking methods."""

    @pytest.mark.asyncio
    async def test_get_pending_correlation_ids(
        self, emitter: TwoPhaseEventEmitter
    ) -> None:
        """get_pending_correlation_ids should return all pending IDs."""
        id1 = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )
        id2 = await emitter.emit_intent(
            operation_type="judicial.panel.convene",
            actor_id="archon-42",
            target_entity_id="panel-001",
            intent_payload={},
        )

        pending_ids = emitter.get_pending_correlation_ids()
        assert len(pending_ids) == 2
        assert id1 in pending_ids
        assert id2 in pending_ids

    @pytest.mark.asyncio
    async def test_get_pending_intents_with_age(
        self, emitter: TwoPhaseEventEmitter, mock_time_authority: MagicMock
    ) -> None:
        """get_pending_intents_with_age should return IDs with timestamps."""
        fixed_time = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = fixed_time

        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        pending = emitter.get_pending_intents_with_age()
        assert len(pending) == 1
        assert pending[0][0] == correlation_id
        assert pending[0][1] == fixed_time


class TestConcurrentEmits:
    """Tests for concurrent two-phase emissions."""

    @pytest.mark.asyncio
    async def test_multiple_intents_tracked_separately(
        self, emitter: TwoPhaseEventEmitter
    ) -> None:
        """Multiple intents should be tracked independently."""
        id1 = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={"key": "value1"},
        )
        id2 = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-43",
            target_entity_id="task-002",
            intent_payload={"key": "value2"},
        )

        # Both should be pending
        pending1 = await emitter.get_pending_intent(id1)
        pending2 = await emitter.get_pending_intent(id2)

        assert pending1 is not None
        assert pending2 is not None
        assert pending1["actor_id"] == "archon-42"
        assert pending2["actor_id"] == "archon-43"

    @pytest.mark.asyncio
    async def test_committing_one_does_not_affect_other(
        self, emitter: TwoPhaseEventEmitter
    ) -> None:
        """Committing one intent should not affect other pending intents."""
        id1 = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )
        id2 = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-43",
            target_entity_id="task-002",
            intent_payload={},
        )

        # Commit first intent
        await emitter.emit_commit(id1, {})

        # First should be resolved, second still pending
        assert await emitter.get_pending_intent(id1) is None
        assert await emitter.get_pending_intent(id2) is not None

    @pytest.mark.asyncio
    async def test_cannot_double_commit(
        self, emitter: TwoPhaseEventEmitter
    ) -> None:
        """Cannot commit the same intent twice."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        await emitter.emit_commit(correlation_id, {})

        with pytest.raises(TwoPhaseEmitError):
            await emitter.emit_commit(correlation_id, {})

    @pytest.mark.asyncio
    async def test_cannot_commit_after_failure(
        self, emitter: TwoPhaseEventEmitter
    ) -> None:
        """Cannot commit an intent that has already failed."""
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        await emitter.emit_failure(correlation_id, "ERROR", {})

        with pytest.raises(TwoPhaseEmitError):
            await emitter.emit_commit(correlation_id, {})
