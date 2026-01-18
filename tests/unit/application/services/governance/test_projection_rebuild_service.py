"""Unit tests for ProjectionRebuildService.

Tests cover acceptance criteria for story consent-gov-1.5:
- AC6: Full rebuild capability from ledger replay
- AC7: Projection checkpoints for incremental updates
- AC8: Comprehensive unit tests for projection behavior
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.governance.projection_port import (
    ProjectionCheckpoint,
)
from src.application.services.governance.projection_rebuild_service import (
    ProjectionRebuildService,
    RebuildResult,
    VerificationResult,
)


class TestRebuildResultDataclass:
    """Tests for RebuildResult dataclass."""

    def test_rebuild_result_creation(self) -> None:
        """RebuildResult with valid data creates successfully."""
        result = RebuildResult(
            projection_name="task_states",
            events_processed=100,
            start_sequence=1,
            end_sequence=100,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            is_full_rebuild=True,
        )

        assert result.projection_name == "task_states"
        assert result.events_processed == 100
        assert result.is_full_rebuild is True

    def test_rebuild_result_with_incremental(self) -> None:
        """RebuildResult can capture incremental rebuild."""
        result = RebuildResult(
            projection_name="task_states",
            events_processed=50,
            start_sequence=51,
            end_sequence=100,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            is_full_rebuild=False,
        )

        assert result.is_full_rebuild is False
        assert result.start_sequence == 51


class TestVerificationResultDataclass:
    """Tests for VerificationResult dataclass."""

    def test_verification_result_creation(self) -> None:
        """VerificationResult with valid data creates successfully."""
        result = VerificationResult(
            projection_name="task_states",
            is_consistent=True,
            events_checked=100,
            discrepancies=(),
        )

        assert result.projection_name == "task_states"
        assert result.is_consistent is True
        assert result.events_checked == 100

    def test_verification_result_with_discrepancies(self) -> None:
        """VerificationResult can capture discrepancies."""
        result = VerificationResult(
            projection_name="task_states",
            is_consistent=False,
            events_checked=100,
            discrepancies=("Event 50 hash mismatch", "Event 75 missing"),
        )

        assert result.is_consistent is False
        assert len(result.discrepancies) == 2


class TestProjectionRebuildServiceCreation:
    """Tests for service creation."""

    def test_service_creation(self) -> None:
        """ProjectionRebuildService can be created with dependencies."""
        mock_ledger = MagicMock()
        mock_projection = MagicMock()
        mock_time_authority = MagicMock()

        service = ProjectionRebuildService(
            ledger_port=mock_ledger,
            projection_port=mock_projection,
            time_authority=mock_time_authority,
        )

        assert service is not None


class TestProjectionRebuildServiceRebuildFull:
    """Tests for rebuild_full method."""

    @pytest.fixture
    def mock_ledger(self) -> AsyncMock:
        """Create mock ledger port."""
        ledger = AsyncMock()
        ledger.get_max_sequence.return_value = 0
        ledger.read_events.return_value = []
        return ledger

    @pytest.fixture
    def mock_projection(self) -> AsyncMock:
        """Create mock projection port."""
        projection = AsyncMock()
        projection.clear_projection.return_value = 0
        projection.is_event_applied.return_value = False
        projection.apply_event.return_value = True
        return projection

    @pytest.fixture
    def mock_time_authority(self) -> MagicMock:
        """Create mock time authority."""
        time_authority = MagicMock()
        time_authority.now.return_value = datetime.now(timezone.utc)
        return time_authority

    @pytest.fixture
    def service(
        self,
        mock_ledger: AsyncMock,
        mock_projection: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> ProjectionRebuildService:
        """Create service with mocked dependencies."""
        return ProjectionRebuildService(
            ledger_port=mock_ledger,
            projection_port=mock_projection,
            time_authority=mock_time_authority,
        )

    @pytest.mark.asyncio
    async def test_rebuild_full_requires_handler(
        self,
        service: ProjectionRebuildService,
    ) -> None:
        """rebuild_full raises ValueError without registered handler."""
        with pytest.raises(ValueError, match="No handler registered"):
            await service.rebuild_full("task_states")

    @pytest.mark.asyncio
    async def test_rebuild_full_with_registered_handler(
        self,
        service: ProjectionRebuildService,
        mock_projection: AsyncMock,
    ) -> None:
        """rebuild_full succeeds with registered handler."""
        # Register a handler for the projection
        async def handler(event, seq):
            pass

        service.register_handler("task_states", handler)

        result = await service.rebuild_full("task_states")

        mock_projection.clear_projection.assert_called_once_with("task_states")
        assert isinstance(result, RebuildResult)
        assert result.projection_name == "task_states"
        assert result.is_full_rebuild is True


class TestProjectionRebuildServiceRebuildIncremental:
    """Tests for rebuild_incremental method."""

    @pytest.fixture
    def mock_ledger(self) -> AsyncMock:
        """Create mock ledger port."""
        ledger = AsyncMock()
        ledger.get_max_sequence.return_value = 100
        ledger.read_events.return_value = []
        return ledger

    @pytest.fixture
    def mock_projection(self) -> AsyncMock:
        """Create mock projection port."""
        projection = AsyncMock()
        projection.get_checkpoint.return_value = None
        projection.is_event_applied.return_value = False
        projection.apply_event.return_value = True
        return projection

    @pytest.fixture
    def mock_time_authority(self) -> MagicMock:
        """Create mock time authority."""
        time_authority = MagicMock()
        time_authority.now.return_value = datetime.now(timezone.utc)
        return time_authority

    @pytest.fixture
    def service(
        self,
        mock_ledger: AsyncMock,
        mock_projection: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> ProjectionRebuildService:
        """Create service with mocked dependencies."""
        return ProjectionRebuildService(
            ledger_port=mock_ledger,
            projection_port=mock_projection,
            time_authority=mock_time_authority,
        )

    @pytest.mark.asyncio
    async def test_rebuild_incremental_requires_handler(
        self,
        service: ProjectionRebuildService,
    ) -> None:
        """rebuild_incremental raises ValueError without registered handler."""
        with pytest.raises(ValueError, match="No handler registered"):
            await service.rebuild_incremental("task_states")

    @pytest.mark.asyncio
    async def test_rebuild_incremental_with_registered_handler(
        self,
        service: ProjectionRebuildService,
        mock_projection: AsyncMock,
    ) -> None:
        """rebuild_incremental succeeds with registered handler."""
        event_id = uuid4()
        checkpoint = ProjectionCheckpoint(
            projection_name="task_states",
            last_event_id=event_id,
            last_hash="abc123",
            last_sequence=50,
            updated_at=datetime.now(timezone.utc),
        )
        mock_projection.get_checkpoint.return_value = checkpoint

        async def handler(event, seq):
            pass

        service.register_handler("task_states", handler)
        result = await service.rebuild_incremental("task_states")

        assert isinstance(result, RebuildResult)
        assert result.start_sequence == 51  # Starts after checkpoint


class TestProjectionRebuildServiceGetRebuildStatus:
    """Tests for get_rebuild_status method."""

    @pytest.fixture
    def mock_ledger(self) -> AsyncMock:
        """Create mock ledger port."""
        ledger = AsyncMock()
        ledger.get_max_sequence.return_value = 100
        return ledger

    @pytest.fixture
    def mock_projection(self) -> AsyncMock:
        """Create mock projection port."""
        projection = AsyncMock()
        return projection

    @pytest.fixture
    def mock_time_authority(self) -> MagicMock:
        """Create mock time authority."""
        time_authority = MagicMock()
        time_authority.now.return_value = datetime.now(timezone.utc)
        return time_authority

    @pytest.fixture
    def service(
        self,
        mock_ledger: AsyncMock,
        mock_projection: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> ProjectionRebuildService:
        """Create service with mocked dependencies."""
        return ProjectionRebuildService(
            ledger_port=mock_ledger,
            projection_port=mock_projection,
            time_authority=mock_time_authority,
        )

    @pytest.mark.asyncio
    async def test_get_rebuild_status_synchronized(
        self,
        service: ProjectionRebuildService,
        mock_ledger: AsyncMock,
        mock_projection: AsyncMock,
    ) -> None:
        """get_rebuild_status returns synchronized when up to date."""
        mock_ledger.get_max_sequence.return_value = 100
        checkpoint = ProjectionCheckpoint(
            projection_name="task_states",
            last_event_id=uuid4(),
            last_hash="abc123",
            last_sequence=100,
            updated_at=datetime.now(timezone.utc),
        )
        mock_projection.get_checkpoint.return_value = checkpoint

        result = await service.get_rebuild_status("task_states")

        assert isinstance(result, dict)
        assert result["projection_name"] == "task_states"
        assert result["checkpoint_sequence"] == 100
        assert result["ledger_max_sequence"] == 100
        assert result["events_behind"] == 0

    @pytest.mark.asyncio
    async def test_get_rebuild_status_out_of_sync(
        self,
        service: ProjectionRebuildService,
        mock_ledger: AsyncMock,
        mock_projection: AsyncMock,
    ) -> None:
        """get_rebuild_status returns out of sync when behind."""
        mock_ledger.get_max_sequence.return_value = 100
        checkpoint = ProjectionCheckpoint(
            projection_name="task_states",
            last_event_id=uuid4(),
            last_hash="abc123",
            last_sequence=90,
            updated_at=datetime.now(timezone.utc),
        )
        mock_projection.get_checkpoint.return_value = checkpoint

        result = await service.get_rebuild_status("task_states")

        assert isinstance(result, dict)
        assert result["checkpoint_sequence"] == 90
        assert result["ledger_max_sequence"] == 100
        assert result["events_behind"] == 10

    @pytest.mark.asyncio
    async def test_get_rebuild_status_no_checkpoint(
        self,
        service: ProjectionRebuildService,
        mock_ledger: AsyncMock,
        mock_projection: AsyncMock,
    ) -> None:
        """get_rebuild_status handles missing checkpoint."""
        mock_ledger.get_max_sequence.return_value = 100
        mock_projection.get_checkpoint.return_value = None

        result = await service.get_rebuild_status("task_states")

        assert isinstance(result, dict)
        assert result["checkpoint_sequence"] is None
        assert result["ledger_max_sequence"] == 100
        assert result["events_behind"] == 100


class TestProjectionRebuildServiceRebuildAll:
    """Tests for rebuild_all method."""

    @pytest.fixture
    def mock_ledger(self) -> AsyncMock:
        """Create mock ledger port."""
        ledger = AsyncMock()
        ledger.get_max_sequence.return_value = 0
        ledger.read_events.return_value = []
        return ledger

    @pytest.fixture
    def mock_projection(self) -> AsyncMock:
        """Create mock projection port."""
        projection = AsyncMock()
        projection.get_projection_names.return_value = [
            "task_states",
            "legitimacy_states",
        ]
        projection.clear_projection.return_value = 0
        return projection

    @pytest.fixture
    def mock_time_authority(self) -> MagicMock:
        """Create mock time authority."""
        time_authority = MagicMock()
        time_authority.now.return_value = datetime.now(timezone.utc)
        return time_authority

    @pytest.fixture
    def service(
        self,
        mock_ledger: AsyncMock,
        mock_projection: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> ProjectionRebuildService:
        """Create service with mocked dependencies."""
        return ProjectionRebuildService(
            ledger_port=mock_ledger,
            projection_port=mock_projection,
            time_authority=mock_time_authority,
        )

    @pytest.mark.asyncio
    async def test_rebuild_all_rebuilds_registered_handlers(
        self,
        service: ProjectionRebuildService,
        mock_projection: AsyncMock,
    ) -> None:
        """rebuild_all rebuilds all registered handler projections."""
        # Register handlers for projections
        async def handler(event, seq):
            pass

        service.register_handler("task_states", handler)
        service.register_handler("legitimacy_states", handler)

        results = await service.rebuild_all()

        assert len(results) == 2
        assert all(isinstance(r, RebuildResult) for r in results)
        projection_names = {r.projection_name for r in results}
        assert projection_names == {"task_states", "legitimacy_states"}

    @pytest.mark.asyncio
    async def test_rebuild_all_returns_empty_without_handlers(
        self,
        service: ProjectionRebuildService,
    ) -> None:
        """rebuild_all returns empty list without registered handlers."""
        results = await service.rebuild_all()

        assert isinstance(results, list)
        assert len(results) == 0
