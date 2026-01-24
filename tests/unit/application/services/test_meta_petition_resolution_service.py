"""Unit tests for MetaPetitionResolutionService (Story 8.5, AC4).

These tests verify:
1. Resolution with ACKNOWLEDGE disposition
2. Resolution with CREATE_ACTION disposition
3. Resolution with FORWARD disposition and target
4. Rationale validation
5. Forward target validation
6. Event emission
7. Error handling
"""

# Direct imports to avoid services __init__ chain issues
import importlib.util
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.meta_petition_queue_repository import (
    MetaPetitionAlreadyResolvedError,
    MetaPetitionNotFoundError,
)

_spec_res = importlib.util.spec_from_file_location(
    "meta_petition_resolution_service",
    "src/application/services/meta_petition_resolution_service.py",
)
_resolution_module = importlib.util.module_from_spec(_spec_res)
_spec_res.loader.exec_module(_resolution_module)
MetaPetitionResolutionService = _resolution_module.MetaPetitionResolutionService
MIN_RATIONALE_LENGTH = _resolution_module.MIN_RATIONALE_LENGTH

from src.application.ports.meta_petition_event_emitter import (
    MetaPetitionEventEmitterProtocol,
)
from src.domain.events.meta_petition import MetaPetitionResolvedEventPayload
from src.domain.models.meta_petition import (
    MetaDisposition,
    MetaPetitionQueueItem,
    MetaPetitionStatus,
)


@pytest.fixture
def mock_queue_repo() -> AsyncMock:
    """Create mock queue repository."""
    mock = AsyncMock()
    mock.mark_resolved.return_value = MetaPetitionQueueItem(
        petition_id=uuid4(),
        submitter_id=uuid4(),
        petition_text="Test",
        received_at=datetime.now(timezone.utc),
        status=MetaPetitionStatus.RESOLVED,
    )
    mock.get_pending.return_value = ([], 0)
    mock.get_by_petition_id.return_value = None
    return mock


@pytest.fixture
def mock_event_emitter() -> AsyncMock:
    """Create mock event emitter."""
    return AsyncMock(spec=MetaPetitionEventEmitterProtocol)


class TestResolveMetaPetition:
    """Tests for resolve_meta_petition method."""

    @pytest.mark.asyncio
    async def test_resolve_acknowledge_success(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test successful resolution with ACKNOWLEDGE disposition."""
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)
        petition_id = uuid4()
        high_archon_id = uuid4()

        event = await service.resolve_meta_petition(
            petition_id=petition_id,
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Acknowledged the system feedback concern",
            high_archon_id=high_archon_id,
        )

        assert isinstance(event, MetaPetitionResolvedEventPayload)
        assert event.petition_id == petition_id
        assert event.disposition == MetaDisposition.ACKNOWLEDGE
        assert event.high_archon_id == high_archon_id
        assert event.forward_target is None

    @pytest.mark.asyncio
    async def test_resolve_create_action_success(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test successful resolution with CREATE_ACTION disposition."""
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        event = await service.resolve_meta_petition(
            petition_id=uuid4(),
            disposition=MetaDisposition.CREATE_ACTION,
            rationale="Creating governance action item for review",
            high_archon_id=uuid4(),
        )

        assert event.disposition == MetaDisposition.CREATE_ACTION

    @pytest.mark.asyncio
    async def test_resolve_forward_with_target_success(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test successful resolution with FORWARD disposition and target."""
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        event = await service.resolve_meta_petition(
            petition_id=uuid4(),
            disposition=MetaDisposition.FORWARD,
            rationale="Forwarding to governance council for review",
            high_archon_id=uuid4(),
            forward_target="governance_council",
        )

        assert event.disposition == MetaDisposition.FORWARD
        assert event.forward_target == "governance_council"

    @pytest.mark.asyncio
    async def test_resolve_calls_mark_resolved(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that resolution calls mark_resolved on repository."""
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)
        petition_id = uuid4()
        high_archon_id = uuid4()

        await service.resolve_meta_petition(
            petition_id=petition_id,
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Test rationale",
            high_archon_id=high_archon_id,
        )

        mock_queue_repo.mark_resolved.assert_called_once_with(
            petition_id=petition_id,
            high_archon_id=high_archon_id,
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Test rationale",
            forward_target=None,
        )

    @pytest.mark.asyncio
    async def test_resolve_emits_event(
        self, mock_queue_repo: AsyncMock, mock_event_emitter: AsyncMock
    ) -> None:
        """Test that resolution emits MetaPetitionResolved event."""
        service = MetaPetitionResolutionService(
            queue_repository=mock_queue_repo,
            event_emitter=mock_event_emitter,
        )

        await service.resolve_meta_petition(
            petition_id=uuid4(),
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Test rationale",
            high_archon_id=uuid4(),
        )

        mock_event_emitter.emit_meta_petition_resolved.assert_called_once()


class TestResolveValidation:
    """Tests for resolution validation."""

    @pytest.mark.asyncio
    async def test_rationale_too_short_raises_error(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that short rationale raises ValueError."""
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        with pytest.raises(ValueError, match="Rationale must be at least"):
            await service.resolve_meta_petition(
                petition_id=uuid4(),
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale="short",  # Less than MIN_RATIONALE_LENGTH
                high_archon_id=uuid4(),
            )

        mock_queue_repo.mark_resolved.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_rationale_raises_error(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that empty rationale raises ValueError."""
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        with pytest.raises(ValueError, match="Rationale must be at least"):
            await service.resolve_meta_petition(
                petition_id=uuid4(),
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale="",
                high_archon_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_whitespace_only_rationale_raises_error(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that whitespace-only rationale raises ValueError."""
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        with pytest.raises(ValueError, match="Rationale must be at least"):
            await service.resolve_meta_petition(
                petition_id=uuid4(),
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale="     ",  # Only whitespace
                high_archon_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_forward_without_target_raises_error(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that FORWARD without target raises ValueError."""
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        with pytest.raises(ValueError, match="forward_target required"):
            await service.resolve_meta_petition(
                petition_id=uuid4(),
                disposition=MetaDisposition.FORWARD,
                rationale="Forwarding to council",
                high_archon_id=uuid4(),
                forward_target=None,
            )

        mock_queue_repo.mark_resolved.assert_not_called()

    @pytest.mark.asyncio
    async def test_rationale_at_min_length_succeeds(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that rationale at exactly min length succeeds."""
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)
        min_rationale = "A" * MIN_RATIONALE_LENGTH

        # Should not raise
        event = await service.resolve_meta_petition(
            petition_id=uuid4(),
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale=min_rationale,
            high_archon_id=uuid4(),
        )

        assert event.rationale == min_rationale


class TestResolveErrorHandling:
    """Tests for resolution error handling."""

    @pytest.mark.asyncio
    async def test_petition_not_found_propagates(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that MetaPetitionNotFoundError is propagated."""
        petition_id = uuid4()
        mock_queue_repo.mark_resolved.side_effect = MetaPetitionNotFoundError(
            petition_id
        )
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        with pytest.raises(MetaPetitionNotFoundError):
            await service.resolve_meta_petition(
                petition_id=petition_id,
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale="Test rationale",
                high_archon_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_already_resolved_propagates(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that MetaPetitionAlreadyResolvedError is propagated."""
        petition_id = uuid4()
        mock_queue_repo.mark_resolved.side_effect = MetaPetitionAlreadyResolvedError(
            petition_id
        )
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        with pytest.raises(MetaPetitionAlreadyResolvedError):
            await service.resolve_meta_petition(
                petition_id=petition_id,
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale="Test rationale",
                high_archon_id=uuid4(),
            )


class TestGetPendingQueue:
    """Tests for get_pending_queue method."""

    @pytest.mark.asyncio
    async def test_get_pending_queue_returns_items(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that get_pending_queue returns items from repository."""
        mock_items = [
            MetaPetitionQueueItem(
                petition_id=uuid4(),
                submitter_id=uuid4(),
                petition_text="Test",
                received_at=datetime.now(timezone.utc),
                status=MetaPetitionStatus.PENDING,
            )
        ]
        mock_queue_repo.get_pending.return_value = (mock_items, 1)
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        items, total = await service.get_pending_queue()

        assert len(items) == 1
        assert total == 1
        mock_queue_repo.get_pending.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pending_queue_clamps_limit(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that limit is clamped to 100."""
        mock_queue_repo.get_pending.return_value = ([], 0)
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        await service.get_pending_queue(limit=500)

        mock_queue_repo.get_pending.assert_called_once_with(limit=100, offset=0)

    @pytest.mark.asyncio
    async def test_get_pending_queue_pagination(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that pagination parameters are passed."""
        mock_queue_repo.get_pending.return_value = ([], 0)
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        await service.get_pending_queue(limit=25, offset=50)

        mock_queue_repo.get_pending.assert_called_once_with(limit=25, offset=50)


class TestGetQueueItem:
    """Tests for get_queue_item method."""

    @pytest.mark.asyncio
    async def test_get_queue_item_found(self, mock_queue_repo: AsyncMock) -> None:
        """Test retrieving existing queue item."""
        petition_id = uuid4()
        mock_item = MetaPetitionQueueItem(
            petition_id=petition_id,
            submitter_id=uuid4(),
            petition_text="Test",
            received_at=datetime.now(timezone.utc),
            status=MetaPetitionStatus.PENDING,
        )
        mock_queue_repo.get_by_petition_id.return_value = mock_item
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        item = await service.get_queue_item(petition_id)

        assert item is not None
        assert item.petition_id == petition_id

    @pytest.mark.asyncio
    async def test_get_queue_item_not_found(self, mock_queue_repo: AsyncMock) -> None:
        """Test retrieving non-existent queue item."""
        mock_queue_repo.get_by_petition_id.return_value = None
        service = MetaPetitionResolutionService(queue_repository=mock_queue_repo)

        item = await service.get_queue_item(uuid4())

        assert item is None
