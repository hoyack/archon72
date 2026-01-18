"""Unit tests for PostgresGovernanceLedgerAdapter.

Tests cover acceptance criteria for story consent-gov-1.2:
- AC3: PostgreSQL adapter implements append with global monotonic sequence
- AC6: Ledger survives service restart (PostgreSQL ACID guarantees)
- AC7: Unit tests verify adapter correctly persists events
- AC8: Adapter accepts only GovernanceEvent (type enforcement)

These tests use mocked database sessions to test the adapter logic
without requiring a real PostgreSQL database. Integration tests
with a real database are in tests/integration/governance/.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.governance.ledger_port import (
    LedgerReadOptions,
    PersistedGovernanceEvent,
)
from src.domain.governance.events.event_envelope import (
    GovernanceEvent,
)
from src.infrastructure.adapters.governance.postgres_ledger_adapter import (
    PostgresGovernanceLedgerAdapter,
)


class TestPostgresGovernanceLedgerAdapterTypeEnforcement:
    """Tests for type enforcement (AC8)."""

    @pytest.fixture
    def mock_session_factory(self) -> MagicMock:
        """Create a mock session factory."""
        session = AsyncMock()
        session_factory = MagicMock()
        session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        return session_factory

    @pytest.fixture
    def adapter(
        self, mock_session_factory: MagicMock
    ) -> PostgresGovernanceLedgerAdapter:
        """Create adapter with mocked session factory."""
        return PostgresGovernanceLedgerAdapter(
            session_factory=mock_session_factory,
            verbose=True,
        )

    @pytest.fixture
    def sample_event(self) -> GovernanceEvent:
        """Create a sample GovernanceEvent for testing."""
        return GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="archon-42",
            trace_id="req-12345",
            payload={"task_id": "task-001"},
        )

    @pytest.mark.asyncio
    async def test_append_event_rejects_non_governance_event(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
    ) -> None:
        """append_event raises TypeError for non-GovernanceEvent (AC8)."""
        # Try to append a dict instead of GovernanceEvent
        with pytest.raises(TypeError) as exc_info:
            await adapter.append_event({"not": "a governance event"})  # type: ignore[arg-type]

        assert "GovernanceEvent" in str(exc_info.value)
        assert "AC8" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_append_event_rejects_string(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
    ) -> None:
        """append_event raises TypeError for string input."""
        with pytest.raises(TypeError) as exc_info:
            await adapter.append_event("not an event")  # type: ignore[arg-type]

        assert "GovernanceEvent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_append_event_rejects_none(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
    ) -> None:
        """append_event raises TypeError for None input."""
        with pytest.raises(TypeError) as exc_info:
            await adapter.append_event(None)  # type: ignore[arg-type]

        assert "GovernanceEvent" in str(exc_info.value)


class TestPostgresGovernanceLedgerAdapterNoMutationMethods:
    """Tests verifying no update/delete methods exist (AC2)."""

    def test_adapter_has_no_update_method(self) -> None:
        """PostgresGovernanceLedgerAdapter has NO update method."""
        assert not hasattr(PostgresGovernanceLedgerAdapter, "update_event")
        assert not hasattr(PostgresGovernanceLedgerAdapter, "update")
        assert not hasattr(PostgresGovernanceLedgerAdapter, "modify_event")
        assert not hasattr(PostgresGovernanceLedgerAdapter, "modify")

    def test_adapter_has_no_delete_method(self) -> None:
        """PostgresGovernanceLedgerAdapter has NO delete method."""
        assert not hasattr(PostgresGovernanceLedgerAdapter, "delete_event")
        assert not hasattr(PostgresGovernanceLedgerAdapter, "delete")
        assert not hasattr(PostgresGovernanceLedgerAdapter, "remove_event")
        assert not hasattr(PostgresGovernanceLedgerAdapter, "remove")

    def test_adapter_has_no_clear_method(self) -> None:
        """PostgresGovernanceLedgerAdapter has NO clear/truncate method."""
        assert not hasattr(PostgresGovernanceLedgerAdapter, "clear")
        assert not hasattr(PostgresGovernanceLedgerAdapter, "truncate")
        assert not hasattr(PostgresGovernanceLedgerAdapter, "purge")


class TestPostgresGovernanceLedgerAdapterAppend:
    """Tests for append_event method (AC3, AC7)."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session: AsyncMock) -> MagicMock:
        """Create a mock session factory that returns the mock session."""
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        factory.return_value.__aexit__ = AsyncMock(return_value=None)
        return factory

    @pytest.fixture
    def adapter(
        self, mock_session_factory: MagicMock
    ) -> PostgresGovernanceLedgerAdapter:
        """Create adapter with mocked session factory."""
        return PostgresGovernanceLedgerAdapter(
            session_factory=mock_session_factory,
            verbose=True,
        )

    @pytest.fixture
    def sample_event(self) -> GovernanceEvent:
        """Create a sample GovernanceEvent for testing."""
        return GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="archon-42",
            trace_id="req-12345",
            payload={"task_id": "task-001"},
        )

    @pytest.mark.asyncio
    async def test_append_event_returns_persisted_event(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
        sample_event: GovernanceEvent,
    ) -> None:
        """append_event returns PersistedGovernanceEvent with sequence (AC3)."""
        # Mock the database response
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (42, "executive")  # sequence, branch
        mock_session.execute.return_value = mock_result

        result = await adapter.append_event(sample_event)

        assert isinstance(result, PersistedGovernanceEvent)
        assert result.sequence == 42
        assert result.event == sample_event
        assert result.event_id == sample_event.event_id

    @pytest.mark.asyncio
    async def test_append_event_calls_commit(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
        sample_event: GovernanceEvent,
    ) -> None:
        """append_event commits the transaction (AC6 - ACID guarantees)."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1, "executive")
        mock_session.execute.return_value = mock_result

        await adapter.append_event(sample_event)

        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_append_event_uses_correct_sql_parameters(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
        sample_event: GovernanceEvent,
    ) -> None:
        """append_event passes correct parameters to SQL (AC7)."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1, "executive")
        mock_session.execute.return_value = mock_result

        await adapter.append_event(sample_event)

        # Verify execute was called
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args

        # Check parameters
        params = call_args[0][1]  # Second positional arg is params dict
        assert params["event_id"] == sample_event.event_id
        assert params["event_type"] == sample_event.event_type
        assert params["branch"] == sample_event.branch
        assert params["schema_version"] == sample_event.schema_version
        assert params["actor_id"] == sample_event.actor_id
        assert params["trace_id"] == sample_event.trace_id


class TestPostgresGovernanceLedgerAdapterRead:
    """Tests for read methods (AC7)."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session: AsyncMock) -> MagicMock:
        """Create a mock session factory."""
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        factory.return_value.__aexit__ = AsyncMock(return_value=None)
        return factory

    @pytest.fixture
    def adapter(
        self, mock_session_factory: MagicMock
    ) -> PostgresGovernanceLedgerAdapter:
        """Create adapter with mocked session factory."""
        return PostgresGovernanceLedgerAdapter(
            session_factory=mock_session_factory,
            verbose=False,
        )

    @pytest.mark.asyncio
    async def test_get_max_sequence_returns_zero_for_empty_ledger(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """get_max_sequence returns 0 for empty ledger."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (0,)
        mock_session.execute.return_value = mock_result

        result = await adapter.get_max_sequence()

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_max_sequence_returns_highest_sequence(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """get_max_sequence returns the highest sequence number."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (42,)
        mock_session.execute.return_value = mock_result

        result = await adapter.get_max_sequence()

        assert result == 42

    @pytest.mark.asyncio
    async def test_get_latest_event_returns_none_for_empty_ledger(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """get_latest_event returns None when ledger is empty."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        result = await adapter.get_latest_event()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_event_by_sequence_returns_none_for_missing(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """get_event_by_sequence returns None for non-existent sequence."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        result = await adapter.get_event_by_sequence(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_event_by_id_returns_none_for_missing(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """get_event_by_id returns None for non-existent event ID."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        result = await adapter.get_event_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_read_events_returns_empty_list_for_no_matches(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """read_events returns empty list when no events match."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        result = await adapter.read_events()

        assert result == []

    @pytest.mark.asyncio
    async def test_count_events_returns_zero_for_empty_ledger(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """count_events returns 0 for empty ledger."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (0,)
        mock_session.execute.return_value = mock_result

        result = await adapter.count_events()

        assert result == 0


class TestPostgresGovernanceLedgerAdapterFiltering:
    """Tests for read_events filtering with LedgerReadOptions."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session: AsyncMock) -> MagicMock:
        """Create a mock session factory."""
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        factory.return_value.__aexit__ = AsyncMock(return_value=None)
        return factory

    @pytest.fixture
    def adapter(
        self, mock_session_factory: MagicMock
    ) -> PostgresGovernanceLedgerAdapter:
        """Create adapter with mocked session factory."""
        return PostgresGovernanceLedgerAdapter(
            session_factory=mock_session_factory,
            verbose=False,
        )

    @pytest.mark.asyncio
    async def test_read_events_applies_sequence_range_filter(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """read_events applies start_sequence and end_sequence filters."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        options = LedgerReadOptions(start_sequence=10, end_sequence=100)
        await adapter.read_events(options)

        # Verify the query includes sequence range conditions
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["start_sequence"] == 10
        assert params["end_sequence"] == 100

    @pytest.mark.asyncio
    async def test_read_events_applies_branch_filter(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """read_events applies branch filter."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        options = LedgerReadOptions(branch="executive")
        await adapter.read_events(options)

        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["branch"] == "executive"

    @pytest.mark.asyncio
    async def test_read_events_applies_event_type_filter(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """read_events applies event_type filter."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        options = LedgerReadOptions(event_type="executive.task.accepted")
        await adapter.read_events(options)

        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["event_type"] == "executive.task.accepted"

    @pytest.mark.asyncio
    async def test_read_events_applies_limit_and_offset(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """read_events applies limit and offset for pagination."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        options = LedgerReadOptions(limit=50, offset=25)
        await adapter.read_events(options)

        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 50
        assert params["offset"] == 25


class TestRowToPersistedEvent:
    """Tests for _row_to_persisted_event helper method."""

    @pytest.fixture
    def adapter(self) -> PostgresGovernanceLedgerAdapter:
        """Create adapter with mocked session factory."""
        mock_factory = MagicMock()
        return PostgresGovernanceLedgerAdapter(
            session_factory=mock_factory,
            verbose=False,
        )

    def test_converts_row_to_persisted_event(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
    ) -> None:
        """_row_to_persisted_event correctly converts database row."""
        event_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        row = (
            42,  # sequence
            event_id,  # event_id
            "executive.task.accepted",  # event_type
            "executive",  # branch
            "1.0.0",  # schema_version
            timestamp,  # timestamp
            "archon-42",  # actor_id
            "req-12345",  # trace_id
            {"task_id": "task-001"},  # payload
        )

        result = adapter._row_to_persisted_event(row)

        assert isinstance(result, PersistedGovernanceEvent)
        assert result.sequence == 42
        assert result.event_id == event_id
        assert result.event_type == "executive.task.accepted"
        assert result.branch == "executive"
        assert result.actor_id == "archon-42"
        assert result.event.payload["task_id"] == "task-001"

    def test_handles_timezone_naive_timestamp(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
    ) -> None:
        """_row_to_persisted_event handles timezone-naive timestamps."""
        event_id = uuid4()
        naive_timestamp = datetime(2026, 1, 16, 12, 0, 0)  # No timezone

        row = (
            1,
            event_id,
            "executive.task.accepted",
            "executive",
            "1.0.0",
            naive_timestamp,
            "archon-42",
            "req-12345",
            {},
        )

        result = adapter._row_to_persisted_event(row)

        # Timestamp should be converted to UTC
        assert result.timestamp.tzinfo is not None

    def test_handles_string_uuid(
        self,
        adapter: PostgresGovernanceLedgerAdapter,
    ) -> None:
        """_row_to_persisted_event handles string UUID from database."""
        event_id_str = "12345678-1234-5678-1234-567812345678"
        timestamp = datetime.now(timezone.utc)

        row = (
            1,
            event_id_str,  # String UUID instead of UUID object
            "executive.task.accepted",
            "executive",
            "1.0.0",
            timestamp,
            "archon-42",
            "req-12345",
            {},
        )

        result = adapter._row_to_persisted_event(row)

        assert isinstance(result.event_id, uuid4().__class__)
        assert str(result.event_id) == event_id_str
