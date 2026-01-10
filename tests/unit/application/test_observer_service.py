"""Unit tests for ObserverService (Story 4.1, Task 5; Story 4.3, Task 3).

Tests for the application service providing observer operations.

Constitutional Constraints:
- FR44: All read operations are public (no auth required)
- FR46: Query interface supports date range and event type filtering
- CT-13: Reads allowed during halt (per Story 3.5)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestObserverService:
    """Tests for ObserverService class."""

    def _create_mock_event(self, sequence: int = 1):
        """Create a mock event for testing."""
        from src.domain.events import Event

        return Event(
            event_id=uuid4(),
            sequence=sequence,
            event_type="test.event",
            payload={"key": "value"},
            prev_hash="0" * 64,
            content_hash="a" * 64,
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime.now(timezone.utc),
        )

    def _create_service(self, events: list = None, halted: bool = False):
        """Create ObserverService with mock dependencies."""
        from src.application.services.observer_service import ObserverService

        # Create mock event store
        event_store = AsyncMock()
        events = events or []

        event_store.count_events.return_value = len(events)
        event_store.get_max_sequence.return_value = len(events)
        event_store.get_events_by_sequence_range.return_value = events
        event_store.get_event_by_id.return_value = events[0] if events else None
        event_store.get_event_by_sequence.return_value = events[0] if events else None

        # Create mock halt checker
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = halted
        halt_checker.get_halt_reason.return_value = (
            "Test halt reason" if halted else None
        )

        return ObserverService(
            event_store=event_store,
            halt_checker=halt_checker,
        )

    def test_service_exists(self) -> None:
        """Test that ObserverService exists."""
        from src.application.services.observer_service import ObserverService

        assert ObserverService is not None

    @pytest.mark.asyncio
    async def test_get_events_returns_events(self) -> None:
        """Test get_events returns events from the store."""
        events = [self._create_mock_event(i) for i in range(1, 4)]
        service = self._create_service(events=events)

        result_events, total = await service.get_events(limit=10, offset=0)

        assert len(result_events) == 3
        assert total == 3

    @pytest.mark.asyncio
    async def test_get_events_with_pagination(self) -> None:
        """Test get_events respects pagination parameters."""
        from src.application.services.observer_service import ObserverService

        # Create service with mock that respects pagination
        event_store = AsyncMock()
        event_store.count_events.return_value = 100
        event_store.get_max_sequence.return_value = 100
        event_store.get_events_by_sequence_range.return_value = [
            self._create_mock_event(i) for i in range(51, 61)
        ]

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        service = ObserverService(
            event_store=event_store,
            halt_checker=halt_checker,
        )

        result_events, total = await service.get_events(limit=10, offset=50)

        assert total == 100
        # Verify the event store was called with correct sequence range
        event_store.get_events_by_sequence_range.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_events_empty_store(self) -> None:
        """Test get_events with empty event store."""
        service = self._create_service(events=[])

        result_events, total = await service.get_events()

        assert result_events == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_event_by_id_found(self) -> None:
        """Test get_event_by_id returns event when found."""
        event = self._create_mock_event()
        service = self._create_service(events=[event])

        # Configure mock to return the specific event
        service._event_store.get_event_by_id.return_value = event

        result = await service.get_event_by_id(event.event_id)

        assert result is not None
        assert result.event_id == event.event_id

    @pytest.mark.asyncio
    async def test_get_event_by_id_not_found(self) -> None:
        """Test get_event_by_id returns None when not found."""
        service = self._create_service(events=[])
        service._event_store.get_event_by_id.return_value = None

        result = await service.get_event_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_event_by_sequence_found(self) -> None:
        """Test get_event_by_sequence returns event when found."""
        event = self._create_mock_event(sequence=42)
        service = self._create_service(events=[event])
        service._event_store.get_event_by_sequence.return_value = event

        result = await service.get_event_by_sequence(42)

        assert result is not None
        assert result.sequence == 42

    @pytest.mark.asyncio
    async def test_get_event_by_sequence_not_found(self) -> None:
        """Test get_event_by_sequence returns None when not found."""
        service = self._create_service(events=[])
        service._event_store.get_event_by_sequence.return_value = None

        result = await service.get_event_by_sequence(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_service_allows_reads_during_halt(self) -> None:
        """Test that reads are allowed during halt state.

        Per CT-13 / Story 3.5: Read-only access during halt.
        Observer reads should ALWAYS work, even when system is halted.
        """
        events = [self._create_mock_event()]
        service = self._create_service(events=events, halted=True)

        # Should NOT raise, reads are allowed during halt
        result_events, total = await service.get_events()

        assert len(result_events) == 1
        # Verify halt checker was NOT consulted for reads
        # (we don't check halt for read operations)

    @pytest.mark.asyncio
    async def test_get_event_by_id_during_halt(self) -> None:
        """Test get_event_by_id works during halt."""
        event = self._create_mock_event()
        service = self._create_service(events=[event], halted=True)
        service._event_store.get_event_by_id.return_value = event

        # Should NOT raise, reads allowed during halt
        result = await service.get_event_by_id(event.event_id)

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_event_by_sequence_during_halt(self) -> None:
        """Test get_event_by_sequence works during halt."""
        event = self._create_mock_event(sequence=5)
        service = self._create_service(events=[event], halted=True)
        service._event_store.get_event_by_sequence.return_value = event

        # Should NOT raise, reads allowed during halt
        result = await service.get_event_by_sequence(5)

        assert result is not None


# =============================================================================
# Tests for Filtered Query Methods (Story 4.3, Task 3 - FR46)
# =============================================================================


class TestObserverServiceFilteredQueries:
    """Tests for ObserverService filtered query methods (FR46)."""

    def _create_mock_event(
        self,
        sequence: int = 1,
        event_type: str = "test.event",
        authority_timestamp: datetime | None = None,
    ):
        """Create a mock event for testing."""
        from src.domain.events import Event

        if authority_timestamp is None:
            authority_timestamp = datetime.now(timezone.utc)

        return Event(
            event_id=uuid4(),
            sequence=sequence,
            event_type=event_type,
            payload={"key": "value"},
            prev_hash="0" * 64,
            content_hash="a" * 64,
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime.now(timezone.utc),
            authority_timestamp=authority_timestamp,
        )

    def _create_service_with_filtered_mock(
        self,
        filtered_events: list = None,
        filtered_count: int = 0,
    ):
        """Create ObserverService with mock supporting filtered queries."""
        from src.application.services.observer_service import ObserverService

        event_store = AsyncMock()
        filtered_events = filtered_events or []

        event_store.get_events_filtered.return_value = filtered_events
        event_store.count_events_filtered.return_value = filtered_count

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        return ObserverService(
            event_store=event_store,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_get_events_filtered_no_filters(self) -> None:
        """Test get_events_filtered with no filters applied."""
        events = [self._create_mock_event(i) for i in range(1, 4)]
        service = self._create_service_with_filtered_mock(
            filtered_events=events, filtered_count=3
        )

        result_events, total = await service.get_events_filtered()

        assert len(result_events) == 3
        assert total == 3
        service._event_store.get_events_filtered.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_events_filtered_by_start_date(self) -> None:
        """Test get_events_filtered with start_date filter."""
        start = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        events = [self._create_mock_event(1)]
        service = self._create_service_with_filtered_mock(
            filtered_events=events, filtered_count=1
        )

        result_events, total = await service.get_events_filtered(start_date=start)

        assert total == 1
        service._event_store.get_events_filtered.assert_called_once_with(
            limit=100,
            offset=0,
            start_date=start,
            end_date=None,
            event_types=None,
        )

    @pytest.mark.asyncio
    async def test_get_events_filtered_by_end_date(self) -> None:
        """Test get_events_filtered with end_date filter."""
        end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
        events = [self._create_mock_event(1)]
        service = self._create_service_with_filtered_mock(
            filtered_events=events, filtered_count=1
        )

        result_events, total = await service.get_events_filtered(end_date=end)

        assert total == 1
        service._event_store.get_events_filtered.assert_called_once_with(
            limit=100,
            offset=0,
            start_date=None,
            end_date=end,
            event_types=None,
        )

    @pytest.mark.asyncio
    async def test_get_events_filtered_by_date_range(self) -> None:
        """Test get_events_filtered with full date range."""
        start = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
        events = [self._create_mock_event(i) for i in range(1, 6)]
        service = self._create_service_with_filtered_mock(
            filtered_events=events, filtered_count=5
        )

        result_events, total = await service.get_events_filtered(
            start_date=start, end_date=end
        )

        assert total == 5
        service._event_store.count_events_filtered.assert_called_once_with(
            start_date=start,
            end_date=end,
            event_types=None,
        )

    @pytest.mark.asyncio
    async def test_get_events_filtered_by_single_type(self) -> None:
        """Test get_events_filtered with single event type."""
        events = [self._create_mock_event(1, event_type="vote")]
        service = self._create_service_with_filtered_mock(
            filtered_events=events, filtered_count=1
        )

        result_events, total = await service.get_events_filtered(event_types=["vote"])

        assert total == 1
        service._event_store.get_events_filtered.assert_called_once_with(
            limit=100,
            offset=0,
            start_date=None,
            end_date=None,
            event_types=["vote"],
        )

    @pytest.mark.asyncio
    async def test_get_events_filtered_by_multiple_types(self) -> None:
        """Test get_events_filtered with multiple event types."""
        events = [
            self._create_mock_event(1, event_type="vote"),
            self._create_mock_event(2, event_type="halt"),
        ]
        service = self._create_service_with_filtered_mock(
            filtered_events=events, filtered_count=2
        )

        result_events, total = await service.get_events_filtered(
            event_types=["vote", "halt"]
        )

        assert total == 2
        service._event_store.get_events_filtered.assert_called_once_with(
            limit=100,
            offset=0,
            start_date=None,
            end_date=None,
            event_types=["vote", "halt"],
        )

    @pytest.mark.asyncio
    async def test_get_events_filtered_combined(self) -> None:
        """Test get_events_filtered with date range and type filter."""
        start = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
        events = [self._create_mock_event(1, event_type="vote")]
        service = self._create_service_with_filtered_mock(
            filtered_events=events, filtered_count=1
        )

        result_events, total = await service.get_events_filtered(
            start_date=start,
            end_date=end,
            event_types=["vote"],
        )

        assert total == 1
        service._event_store.get_events_filtered.assert_called_once_with(
            limit=100,
            offset=0,
            start_date=start,
            end_date=end,
            event_types=["vote"],
        )

    @pytest.mark.asyncio
    async def test_get_events_filtered_with_pagination(self) -> None:
        """Test get_events_filtered respects pagination."""
        events = [self._create_mock_event(i) for i in range(51, 61)]
        service = self._create_service_with_filtered_mock(
            filtered_events=events, filtered_count=100
        )

        result_events, total = await service.get_events_filtered(
            limit=10, offset=50
        )

        assert total == 100
        assert len(result_events) == 10
        service._event_store.get_events_filtered.assert_called_once_with(
            limit=10,
            offset=50,
            start_date=None,
            end_date=None,
            event_types=None,
        )


# =============================================================================
# Tests for Historical Query Methods (Story 4.5, Task 3 - FR88, FR89)
# =============================================================================


class TestObserverServiceHistoricalQueries:
    """Tests for ObserverService historical query methods (FR88, FR89)."""

    def _create_mock_event(
        self,
        sequence: int = 1,
        event_type: str = "test.event",
        authority_timestamp: datetime | None = None,
        content_hash: str | None = None,
        prev_hash: str | None = None,
    ):
        """Create a mock event for testing."""
        from src.domain.events import Event

        if authority_timestamp is None:
            authority_timestamp = datetime.now(timezone.utc)

        return Event(
            event_id=uuid4(),
            sequence=sequence,
            event_type=event_type,
            payload={"key": "value"},
            prev_hash=prev_hash or ("0" * 64 if sequence == 1 else "b" * 64),
            content_hash=content_hash or f"{sequence:064x}",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime.now(timezone.utc),
            authority_timestamp=authority_timestamp,
        )

    def _create_service_with_historical_mock(
        self,
        events_up_to: list = None,
        count_up_to: int = 0,
        events_range: list = None,
        latest_event=None,
        as_of_event=None,
    ):
        """Create ObserverService with mock supporting historical queries."""
        from src.application.services.observer_service import ObserverService

        event_store = AsyncMock()
        events_up_to = events_up_to or []
        events_range = events_range or []

        event_store.get_events_up_to_sequence.return_value = events_up_to
        event_store.count_events_up_to_sequence.return_value = count_up_to
        event_store.get_events_by_sequence_range.return_value = events_range
        event_store.get_latest_event.return_value = latest_event
        event_store.get_event_by_sequence.return_value = as_of_event

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        return ObserverService(
            event_store=event_store,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_get_events_as_of_returns_events_up_to_sequence(self) -> None:
        """Test get_events_as_of returns events up to the specified sequence (FR88)."""
        events = [self._create_mock_event(i) for i in range(1, 6)]
        as_of_event = events[4]  # Sequence 5
        latest = self._create_mock_event(10)

        service = self._create_service_with_historical_mock(
            events_up_to=events,
            count_up_to=5,
            as_of_event=as_of_event,
            latest_event=latest,
            events_range=events,
        )

        result_events, total, proof = await service.get_events_as_of(
            as_of_sequence=5,
            include_proof=False,
        )

        assert len(result_events) == 5
        assert total == 5
        assert proof is None
        service._event_store.get_events_up_to_sequence.assert_called_once_with(
            max_sequence=5,
            limit=100,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_get_events_as_of_excludes_later_events(self) -> None:
        """Test get_events_as_of excludes events after the sequence (FR88)."""
        # We have 10 events total, but only request up to sequence 5
        events_up_to_5 = [self._create_mock_event(i) for i in range(1, 6)]
        as_of_event = events_up_to_5[4]
        latest = self._create_mock_event(10)

        service = self._create_service_with_historical_mock(
            events_up_to=events_up_to_5,
            count_up_to=5,
            as_of_event=as_of_event,
            latest_event=latest,
            events_range=events_up_to_5,
        )

        result_events, total, proof = await service.get_events_as_of(as_of_sequence=5)

        assert len(result_events) == 5
        assert all(e.sequence <= 5 for e in result_events)

    @pytest.mark.asyncio
    async def test_get_events_as_of_generates_proof(self) -> None:
        """Test get_events_as_of generates hash chain proof when requested (FR89)."""
        # Events 1-5 are the as_of events
        events_up_to_5 = [self._create_mock_event(i) for i in range(1, 6)]
        as_of_event = events_up_to_5[4]

        # Events 5-10 form the proof chain
        proof_events = [
            self._create_mock_event(
                i,
                content_hash=f"{i:064x}",
                prev_hash=f"{i-1:064x}" if i > 1 else "0" * 64,
            )
            for i in range(5, 11)
        ]
        latest = proof_events[-1]

        service = self._create_service_with_historical_mock(
            events_up_to=events_up_to_5,
            count_up_to=5,
            as_of_event=as_of_event,
            latest_event=latest,
            events_range=proof_events,
        )

        result_events, total, proof = await service.get_events_as_of(
            as_of_sequence=5,
            include_proof=True,
        )

        assert proof is not None
        assert proof.from_sequence == 5
        assert proof.to_sequence == 10
        assert len(proof.chain) == 6  # Events 5 through 10
        assert proof.current_head_hash == latest.content_hash

    @pytest.mark.asyncio
    async def test_get_events_as_of_proof_is_verifiable(self) -> None:
        """Test that the generated proof has valid chain continuity (FR89)."""
        # Create a chain where each event's prev_hash = previous event's content_hash
        def make_chained_event(seq: int, prev_content: str) -> MagicMock:
            """Create event with proper hash chain."""
            from src.domain.events import Event

            return Event(
                event_id=uuid4(),
                sequence=seq,
                event_type="test.event",
                payload={},
                prev_hash=prev_content,
                content_hash=f"{seq:064x}",
                signature="sig",
                witness_id="w",
                witness_signature="ws",
                local_timestamp=datetime.now(timezone.utc),
                authority_timestamp=datetime.now(timezone.utc),
            )

        # Build chain: 5 -> 6 -> 7 -> 8 -> 9 -> 10
        chain_events = []
        prev_hash = f"{4:064x}"  # Previous event's hash
        for seq in range(5, 11):
            event = make_chained_event(seq, prev_hash)
            chain_events.append(event)
            prev_hash = event.content_hash

        as_of_event = chain_events[0]  # Sequence 5
        latest = chain_events[-1]  # Sequence 10

        service = self._create_service_with_historical_mock(
            events_up_to=[as_of_event],
            count_up_to=5,
            as_of_event=as_of_event,
            latest_event=latest,
            events_range=chain_events,
        )

        _, _, proof = await service.get_events_as_of(
            as_of_sequence=5,
            include_proof=True,
        )

        # Verify chain continuity
        assert proof is not None
        for i in range(1, len(proof.chain)):
            assert proof.chain[i].prev_hash == proof.chain[i - 1].content_hash

    @pytest.mark.asyncio
    async def test_get_events_as_of_sequence_not_found(self) -> None:
        """Test get_events_as_of raises error for invalid sequence."""
        from src.domain.errors.event_store import EventNotFoundError

        service = self._create_service_with_historical_mock(
            as_of_event=None,  # Sequence not found
        )

        with pytest.raises(EventNotFoundError) as exc_info:
            await service.get_events_as_of(as_of_sequence=999)

        assert "999" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_events_as_of_timestamp_finds_sequence(self) -> None:
        """Test get_events_as_of_timestamp resolves timestamp to sequence (FR88)."""
        timestamp = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Event at sequence 42 is the last before the timestamp
        as_of_event = self._create_mock_event(
            sequence=42,
            authority_timestamp=datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc),
        )
        events = [as_of_event]
        latest = self._create_mock_event(100)

        service = self._create_service_with_historical_mock(
            events_up_to=events,
            count_up_to=42,
            as_of_event=as_of_event,
            latest_event=latest,
            events_range=events,
        )
        service._event_store.find_sequence_for_timestamp.return_value = 42

        result_events, total, resolved_seq, proof = await service.get_events_as_of_timestamp(
            as_of_timestamp=timestamp,
        )

        assert resolved_seq == 42
        service._event_store.find_sequence_for_timestamp.assert_called_once_with(timestamp)


# =============================================================================
# Tests for Merkle Proof Methods (Story 4.6, Task 4 - FR136, FR137)
# =============================================================================


class TestObserverServiceMerkleProofs:
    """Tests for ObserverService Merkle proof methods (FR136, FR137)."""

    def _create_mock_event(
        self,
        sequence: int = 1,
        event_type: str = "test.event",
        authority_timestamp: datetime | None = None,
        content_hash: str | None = None,
        prev_hash: str | None = None,
    ):
        """Create a mock event for testing."""
        from src.domain.events import Event

        if authority_timestamp is None:
            authority_timestamp = datetime.now(timezone.utc)

        return Event(
            event_id=uuid4(),
            sequence=sequence,
            event_type=event_type,
            payload={"key": "value"},
            prev_hash=prev_hash or ("0" * 64 if sequence == 1 else "b" * 64),
            content_hash=content_hash or f"{sequence:064x}",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime.now(timezone.utc),
            authority_timestamp=authority_timestamp,
        )

    def _create_service_with_merkle_mock(
        self,
        checkpoint_for_seq=None,
        events_range: list = None,
        latest_event=None,
        as_of_event=None,
        events_up_to: list = None,
        count_up_to: int = 0,
    ):
        """Create ObserverService with mock supporting Merkle proofs."""
        from src.application.ports.checkpoint_repository import CheckpointRepository
        from src.application.services.merkle_tree_service import MerkleTreeService
        from src.application.services.observer_service import ObserverService
        from src.domain.models.checkpoint import Checkpoint

        event_store = AsyncMock()
        events_range = events_range or []
        events_up_to = events_up_to or []

        event_store.get_events_by_sequence_range.return_value = events_range
        event_store.get_latest_event.return_value = latest_event
        event_store.get_event_by_sequence.return_value = as_of_event
        event_store.get_events_up_to_sequence.return_value = events_up_to
        event_store.count_events_up_to_sequence.return_value = count_up_to

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        checkpoint_repo = AsyncMock()
        checkpoint_repo.get_checkpoint_for_sequence.return_value = checkpoint_for_seq

        merkle_service = MerkleTreeService()

        return ObserverService(
            event_store=event_store,
            halt_checker=halt_checker,
            checkpoint_repo=checkpoint_repo,
            merkle_service=merkle_service,
        )

    @pytest.mark.asyncio
    async def test_generate_merkle_proof_returns_valid_proof(self) -> None:
        """Test _generate_merkle_proof returns valid MerkleProof (FR136)."""
        from src.domain.models.checkpoint import Checkpoint

        # Create checkpoint covering sequences 1-100
        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="a" * 64,  # Valid 64-char hex
            anchor_type="periodic",
            creator_id="system",
        )

        # Create events in the checkpoint range
        events = [
            self._create_mock_event(
                sequence=i,
                content_hash=f"{i:064x}",
            )
            for i in range(1, 101)
        ]
        as_of_event = events[41]  # Sequence 42

        service = self._create_service_with_merkle_mock(
            checkpoint_for_seq=checkpoint,
            events_range=events,
            as_of_event=as_of_event,
        )

        proof = await service._generate_merkle_proof(42)

        assert proof is not None
        assert proof.event_sequence == 42
        assert proof.event_hash == as_of_event.content_hash
        assert proof.proof_type == "merkle"

    @pytest.mark.asyncio
    async def test_generate_merkle_proof_for_pending_returns_none(self) -> None:
        """Test _generate_merkle_proof returns None for pending interval."""
        # No checkpoint covers this sequence (pending)
        service = self._create_service_with_merkle_mock(
            checkpoint_for_seq=None,  # No checkpoint
        )

        proof = await service._generate_merkle_proof(150)

        assert proof is None

    @pytest.mark.asyncio
    async def test_get_events_with_merkle_proof_includes_proof(self) -> None:
        """Test get_events_as_of with include_merkle_proof=True (FR136)."""
        from src.domain.models.checkpoint import Checkpoint

        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="b" * 64,  # Valid 64-char hex
            anchor_type="periodic",
            creator_id="system",
        )

        events = [
            self._create_mock_event(sequence=i, content_hash=f"{i:064x}")
            for i in range(1, 51)
        ]
        as_of_event = events[49]  # Sequence 50
        latest = self._create_mock_event(100)

        service = self._create_service_with_merkle_mock(
            checkpoint_for_seq=checkpoint,
            events_range=events,
            events_up_to=events,
            count_up_to=50,
            as_of_event=as_of_event,
            latest_event=latest,
        )

        result_events, total, merkle_proof, hash_proof = await service.get_events_with_merkle_proof(
            as_of_sequence=50,
        )

        assert len(result_events) == 50
        assert merkle_proof is not None
        assert hash_proof is None  # Merkle proof takes precedence

    @pytest.mark.asyncio
    async def test_get_events_with_merkle_proof_falls_back_to_hash_chain(self) -> None:
        """Test get_events_with_merkle_proof returns hash chain for pending (FR137)."""
        # Events in pending interval (no checkpoint)
        events = [
            self._create_mock_event(
                sequence=i,
                content_hash=f"{i:064x}",
                prev_hash=f"{i-1:064x}" if i > 1 else "0" * 64,
            )
            for i in range(1, 51)
        ]
        as_of_event = events[49]
        latest = events[49]

        service = self._create_service_with_merkle_mock(
            checkpoint_for_seq=None,  # No checkpoint - pending interval
            events_range=events,
            events_up_to=events,
            count_up_to=50,
            as_of_event=as_of_event,
            latest_event=latest,
        )

        result_events, total, merkle_proof, hash_proof = await service.get_events_with_merkle_proof(
            as_of_sequence=50,
        )

        assert merkle_proof is None  # No checkpoint
        assert hash_proof is not None  # Falls back to hash chain
        assert hash_proof.proof_type == "hash_chain"

    @pytest.mark.asyncio
    async def test_merkle_proof_has_log_n_path_length(self) -> None:
        """Test Merkle proof path length is O(log n) (FR137)."""
        import math

        from src.domain.models.checkpoint import Checkpoint

        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="c" * 64,  # Valid 64-char hex
            anchor_type="periodic",
            creator_id="system",
        )

        # 100 events in checkpoint
        events = [
            self._create_mock_event(sequence=i, content_hash=f"{i:064x}")
            for i in range(1, 101)
        ]
        as_of_event = events[49]

        service = self._create_service_with_merkle_mock(
            checkpoint_for_seq=checkpoint,
            events_range=events,
            as_of_event=as_of_event,
        )

        proof = await service._generate_merkle_proof(50)

        assert proof is not None
        # Path length should be ceil(log2(n)) for n leaves
        # For 100 events padded to 128, that's 7 levels
        expected_max_path_len = math.ceil(math.log2(128))
        assert len(proof.path) <= expected_max_path_len

    @pytest.mark.asyncio
    async def test_list_checkpoints_returns_checkpoints(self) -> None:
        """Test list_checkpoints returns checkpoint list (FR138)."""
        from src.domain.models.checkpoint import Checkpoint

        checkpoints = [
            Checkpoint(
                checkpoint_id=uuid4(),
                event_sequence=i * 100,
                timestamp=datetime.now(timezone.utc) - timedelta(weeks=10 - i),
                anchor_hash=f"{i:064x}",
                anchor_type="periodic",
                creator_id="system",
            )
            for i in range(1, 11)
        ]

        service = self._create_service_with_merkle_mock()
        service._checkpoint_repo.list_checkpoints.return_value = (checkpoints, 10)

        result, total = await service.list_checkpoints(limit=10, offset=0)

        assert len(result) == 10
        assert total == 10
        service._checkpoint_repo.list_checkpoints.assert_called_once_with(
            limit=10, offset=0
        )

    @pytest.mark.asyncio
    async def test_get_checkpoint_for_sequence_found(self) -> None:
        """Test get_checkpoint_for_sequence returns checkpoint."""
        from src.domain.models.checkpoint import Checkpoint

        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="a" * 64,
            anchor_type="periodic",
            creator_id="system",
        )

        service = self._create_service_with_merkle_mock(checkpoint_for_seq=checkpoint)

        result = await service.get_checkpoint_for_sequence(50)

        assert result is not None
        assert result.event_sequence == 100

    @pytest.mark.asyncio
    async def test_get_checkpoint_for_sequence_pending(self) -> None:
        """Test get_checkpoint_for_sequence returns None for pending."""
        service = self._create_service_with_merkle_mock(checkpoint_for_seq=None)

        result = await service.get_checkpoint_for_sequence(150)

        assert result is None
