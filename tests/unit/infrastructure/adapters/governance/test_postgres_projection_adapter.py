"""Unit tests for PostgresProjectionAdapter.

Tests cover acceptance criteria for story consent-gov-1.5:
- AC1: ProjectionPort protocol defined in application layer
- AC2: Schema isolation (projections.* tables)
- AC5: Idempotent event application
- AC6: Full rebuild capability
- AC8: Comprehensive unit tests for projection behavior
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import uuid4

import pytest

from src.application.ports.governance.projection_port import (
    ProjectionCheckpoint,
)
from src.infrastructure.adapters.governance.postgres_projection_adapter import (
    KNOWN_PROJECTIONS,
    PostgresProjectionAdapter,
)


@pytest.fixture
def mock_time_authority() -> MagicMock:
    """Create a mock time authority."""
    authority = MagicMock()
    authority.now.return_value = datetime.now(timezone.utc)
    return authority


class TestPostgresProjectionAdapterCreation:
    """Tests for adapter creation and configuration."""

    def test_adapter_creation(self, mock_time_authority: MagicMock) -> None:
        """PostgresProjectionAdapter can be created with session factory and time authority."""
        mock_factory = MagicMock()
        adapter = PostgresProjectionAdapter(
            session_factory=mock_factory,
            time_authority=mock_time_authority,
        )

        assert adapter is not None

    def test_known_projections_constant(self) -> None:
        """KNOWN_PROJECTIONS contains all expected projection names."""
        expected = {
            "task_states",
            "legitimacy_states",
            "panel_registry",
            "petition_index",
            "actor_registry",
        }
        assert KNOWN_PROJECTIONS == frozenset(expected)


class TestPostgresProjectionAdapterGetCheckpoint:
    """Tests for get_checkpoint method."""

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
    def adapter(self, mock_session_factory: MagicMock, mock_time_authority: MagicMock) -> PostgresProjectionAdapter:
        """Create adapter with mocked session factory."""
        return PostgresProjectionAdapter(
            session_factory=mock_session_factory,
            time_authority=mock_time_authority,
        )

    @pytest.mark.asyncio
    async def test_get_checkpoint_returns_none_when_not_found(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """get_checkpoint returns None when no checkpoint exists."""
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = None
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute.return_value = mock_result

        result = await adapter.get_checkpoint("task_states")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_checkpoint_returns_checkpoint_when_found(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """get_checkpoint returns ProjectionCheckpoint when found."""
        event_id = uuid4()
        timestamp = datetime.now(timezone.utc)
        # Use mappings().first() return format as per actual implementation
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = {
            "projection_name": "task_states",
            "last_event_id": event_id,
            "last_hash": "abc123",
            "last_sequence": 42,
            "updated_at": timestamp,
        }
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute.return_value = mock_result

        result = await adapter.get_checkpoint("task_states")

        assert result is not None
        assert isinstance(result, ProjectionCheckpoint)
        assert result.projection_name == "task_states"
        assert result.last_event_id == event_id
        assert result.last_hash == "abc123"
        assert result.last_sequence == 42


class TestPostgresProjectionAdapterSaveCheckpoint:
    """Tests for save_checkpoint method."""

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
    def adapter(self, mock_session_factory: MagicMock, mock_time_authority: MagicMock) -> PostgresProjectionAdapter:
        """Create adapter with mocked session factory."""
        return PostgresProjectionAdapter(
            session_factory=mock_session_factory,
            time_authority=mock_time_authority,
        )

    @pytest.mark.asyncio
    async def test_save_checkpoint_returns_checkpoint(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """save_checkpoint returns the saved ProjectionCheckpoint."""
        event_id = uuid4()

        result = await adapter.save_checkpoint(
            projection_name="task_states",
            event_id=event_id,
            event_hash="abc123",
            sequence=42,
        )

        assert isinstance(result, ProjectionCheckpoint)
        assert result.projection_name == "task_states"
        assert result.last_event_id == event_id
        assert result.last_hash == "abc123"
        assert result.last_sequence == 42

    @pytest.mark.asyncio
    async def test_save_checkpoint_calls_commit(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """save_checkpoint commits the transaction."""
        event_id = uuid4()

        await adapter.save_checkpoint(
            projection_name="task_states",
            event_id=event_id,
            event_hash="abc123",
            sequence=42,
        )

        mock_session.commit.assert_called_once()


class TestPostgresProjectionAdapterIsEventApplied:
    """Tests for is_event_applied method (idempotency check)."""

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
    def adapter(self, mock_session_factory: MagicMock, mock_time_authority: MagicMock) -> PostgresProjectionAdapter:
        """Create adapter with mocked session factory."""
        return PostgresProjectionAdapter(
            session_factory=mock_session_factory,
            time_authority=mock_time_authority,
        )

    @pytest.mark.asyncio
    async def test_is_event_applied_returns_false_when_not_found(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """is_event_applied returns False when event not in projection_applies."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        result = await adapter.is_event_applied("task_states", uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_is_event_applied_returns_true_when_found(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """is_event_applied returns True when event in projection_applies."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result

        result = await adapter.is_event_applied("task_states", uuid4())

        assert result is True


class TestPostgresProjectionAdapterClearProjection:
    """Tests for clear_projection method."""

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
    def adapter(self, mock_session_factory: MagicMock, mock_time_authority: MagicMock) -> PostgresProjectionAdapter:
        """Create adapter with mocked session factory."""
        return PostgresProjectionAdapter(
            session_factory=mock_session_factory,
            time_authority=mock_time_authority,
        )

    @pytest.mark.asyncio
    async def test_clear_projection_returns_deleted_count(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """clear_projection returns count of deleted rows."""
        # Mock responses for DELETE statements
        delete_result = MagicMock()
        delete_result.rowcount = 10
        mock_session.execute.return_value = delete_result

        result = await adapter.clear_projection("task_states")

        assert result == 10

    @pytest.mark.asyncio
    async def test_clear_projection_calls_commit(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """clear_projection commits the transaction."""
        delete_result = MagicMock()
        delete_result.rowcount = 0
        mock_session.execute.return_value = delete_result

        await adapter.clear_projection("task_states")

        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_clear_unknown_projection_raises_error(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """clear_projection raises ValueError for unknown projection names."""
        with pytest.raises(ValueError) as exc_info:
            await adapter.clear_projection("unknown_projection")

        assert "Unknown projection" in str(exc_info.value)


class TestPostgresProjectionAdapterGetProjectionNames:
    """Tests for get_projection_names method."""

    @pytest.fixture
    def mock_session_factory(self) -> MagicMock:
        """Create a mock session factory."""
        factory = MagicMock()
        return factory

    @pytest.fixture
    def adapter(self, mock_session_factory: MagicMock, mock_time_authority: MagicMock) -> PostgresProjectionAdapter:
        """Create adapter with mocked session factory."""
        return PostgresProjectionAdapter(
            session_factory=mock_session_factory,
            time_authority=mock_time_authority,
        )

    @pytest.mark.asyncio
    async def test_get_projection_names_returns_known_projections(
        self,
        adapter: PostgresProjectionAdapter,
    ) -> None:
        """get_projection_names returns list of known projection names."""
        result = await adapter.get_projection_names()

        assert isinstance(result, list)
        assert set(result) == KNOWN_PROJECTIONS


class TestPostgresProjectionAdapterQueryMethods:
    """Tests for query methods (task states, legitimacy, actor registry)."""

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
    def adapter(self, mock_session_factory: MagicMock, mock_time_authority: MagicMock) -> PostgresProjectionAdapter:
        """Create adapter with mocked session factory."""
        return PostgresProjectionAdapter(
            session_factory=mock_session_factory,
            time_authority=mock_time_authority,
        )

    @pytest.mark.asyncio
    async def test_get_task_state_returns_none_when_not_found(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """get_task_state returns None when task not found."""
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = None
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute.return_value = mock_result

        result = await adapter.get_task_state(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_legitimacy_state_returns_none_when_not_found(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """get_legitimacy_state returns None when entity not found."""
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = None
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute.return_value = mock_result

        result = await adapter.get_legitimacy_state("unknown-entity")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_actor_returns_none_when_not_found(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """get_actor returns None when actor not found."""
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = None
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute.return_value = mock_result

        result = await adapter.get_actor("unknown-actor")

        assert result is None

    @pytest.mark.asyncio
    async def test_actor_exists_returns_false_when_not_found(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """actor_exists returns False when actor not found."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        result = await adapter.actor_exists("unknown-actor")

        assert result is False

    @pytest.mark.asyncio
    async def test_actor_exists_returns_true_when_found(
        self,
        adapter: PostgresProjectionAdapter,
        mock_session: AsyncMock,
    ) -> None:
        """actor_exists returns True when actor found."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result

        result = await adapter.actor_exists("archon-42")

        assert result is True


class TestPostgresProjectionAdapterNoMutationMethods:
    """Tests verifying no direct update/delete methods on projections.

    Projections should only be modified through event application,
    not through direct mutation methods.
    """

    def test_adapter_has_no_direct_update_method(self) -> None:
        """PostgresProjectionAdapter has no direct update_task_state method."""
        # These methods should NOT exist - projections are updated via events only
        assert not hasattr(PostgresProjectionAdapter, "update_task_state")
        assert not hasattr(PostgresProjectionAdapter, "update_legitimacy_state")
        assert not hasattr(PostgresProjectionAdapter, "update_actor")

    def test_adapter_has_no_direct_delete_method(self) -> None:
        """PostgresProjectionAdapter has no direct delete methods for individual records."""
        # Individual record deletion should not be available
        # (clear_projection is for full rebuild, not individual deletes)
        assert not hasattr(PostgresProjectionAdapter, "delete_task_state")
        assert not hasattr(PostgresProjectionAdapter, "delete_legitimacy_state")
        assert not hasattr(PostgresProjectionAdapter, "delete_actor")
