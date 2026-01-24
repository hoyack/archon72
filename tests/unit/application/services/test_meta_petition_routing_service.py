"""Unit tests for MetaPetitionRoutingService (Story 8.5, FR-10.4).

These tests verify:
1. META type detection (should_route_to_high_archon)
2. Routing to High Archon queue
3. Event emission
4. Error handling for non-META petitions
"""

# Direct imports to avoid services __init__ chain issues
import importlib.util
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

_spec = importlib.util.spec_from_file_location(
    "meta_petition_routing_service",
    "src/application/services/meta_petition_routing_service.py"
)
_routing_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_routing_module)
MetaPetitionRoutingService = _routing_module.MetaPetitionRoutingService
META_PETITION_TEXT_PREVIEW_LENGTH = _routing_module.META_PETITION_TEXT_PREVIEW_LENGTH

from src.application.ports.meta_petition_event_emitter import (
    MetaPetitionEventEmitterProtocol,
)
from src.domain.events.meta_petition import MetaPetitionReceivedEventPayload
from src.domain.models.meta_petition import MetaPetitionQueueItem, MetaPetitionStatus
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)


def create_petition(
    petition_type: PetitionType = PetitionType.META,
    text: str = "Test META petition about the system",
) -> PetitionSubmission:
    """Helper to create test petition."""
    return PetitionSubmission(
        id=uuid4(),
        type=petition_type,
        text=text,
        submitter_id=uuid4(),
        state=PetitionState.RECEIVED,
    )


class TestShouldRouteToHighArchon:
    """Tests for should_route_to_high_archon method."""

    @pytest.fixture
    def service(self) -> MetaPetitionRoutingService:
        """Create service with mock repository."""
        mock_repo = MagicMock()
        return MetaPetitionRoutingService(queue_repository=mock_repo)

    def test_meta_type_returns_true(self, service: MetaPetitionRoutingService) -> None:
        """Test that META type petitions return True."""
        petition = create_petition(petition_type=PetitionType.META)
        assert service.should_route_to_high_archon(petition) is True

    def test_general_type_returns_false(
        self, service: MetaPetitionRoutingService
    ) -> None:
        """Test that GENERAL type petitions return False."""
        petition = create_petition(petition_type=PetitionType.GENERAL)
        assert service.should_route_to_high_archon(petition) is False

    def test_cessation_type_returns_false(
        self, service: MetaPetitionRoutingService
    ) -> None:
        """Test that CESSATION type petitions return False."""
        petition = create_petition(petition_type=PetitionType.CESSATION)
        assert service.should_route_to_high_archon(petition) is False

    def test_grievance_type_returns_false(
        self, service: MetaPetitionRoutingService
    ) -> None:
        """Test that GRIEVANCE type petitions return False."""
        petition = create_petition(petition_type=PetitionType.GRIEVANCE)
        assert service.should_route_to_high_archon(petition) is False

    def test_collaboration_type_returns_false(
        self, service: MetaPetitionRoutingService
    ) -> None:
        """Test that COLLABORATION type petitions return False."""
        petition = create_petition(petition_type=PetitionType.COLLABORATION)
        assert service.should_route_to_high_archon(petition) is False


class TestRouteMetaPetition:
    """Tests for route_meta_petition method."""

    @pytest.fixture
    def mock_queue_repo(self) -> AsyncMock:
        """Create mock queue repository."""
        mock = AsyncMock()
        mock.enqueue.return_value = MetaPetitionQueueItem(
            petition_id=uuid4(),
            submitter_id=uuid4(),
            petition_text="Test",
            received_at=datetime.now(timezone.utc),
            status=MetaPetitionStatus.PENDING,
        )
        return mock

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        return AsyncMock(spec=MetaPetitionEventEmitterProtocol)

    @pytest.mark.asyncio
    async def test_route_meta_petition_enqueues(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that META petition is enqueued to High Archon queue."""
        service = MetaPetitionRoutingService(queue_repository=mock_queue_repo)
        petition = create_petition()

        await service.route_meta_petition(petition)

        mock_queue_repo.enqueue.assert_called_once_with(
            petition_id=petition.id,
            submitter_id=petition.submitter_id,
            petition_text=petition.text,
        )

    @pytest.mark.asyncio
    async def test_route_meta_petition_returns_event(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that routing returns MetaPetitionReceivedEventPayload."""
        service = MetaPetitionRoutingService(queue_repository=mock_queue_repo)
        petition = create_petition()

        event = await service.route_meta_petition(petition)

        assert isinstance(event, MetaPetitionReceivedEventPayload)
        assert event.petition_id == petition.id
        assert event.routing_reason == "EXPLICIT_META_TYPE"

    @pytest.mark.asyncio
    async def test_route_meta_petition_truncates_preview(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that long petition text is truncated in preview."""
        service = MetaPetitionRoutingService(queue_repository=mock_queue_repo)
        long_text = "A" * 1000  # Longer than preview limit
        petition = create_petition(text=long_text)

        event = await service.route_meta_petition(petition)

        assert len(event.petition_text_preview) == META_PETITION_TEXT_PREVIEW_LENGTH
        assert event.petition_text_preview == "A" * META_PETITION_TEXT_PREVIEW_LENGTH

    @pytest.mark.asyncio
    async def test_route_meta_petition_emits_event(
        self, mock_queue_repo: AsyncMock, mock_event_emitter: AsyncMock
    ) -> None:
        """Test that event is emitted when emitter is configured."""
        service = MetaPetitionRoutingService(
            queue_repository=mock_queue_repo,
            event_emitter=mock_event_emitter,
        )
        petition = create_petition()

        await service.route_meta_petition(petition)

        mock_event_emitter.emit_meta_petition_received.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_meta_petition_no_emitter_no_error(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that routing works without event emitter."""
        service = MetaPetitionRoutingService(
            queue_repository=mock_queue_repo,
            event_emitter=None,
        )
        petition = create_petition()

        # Should not raise
        event = await service.route_meta_petition(petition)
        assert event is not None

    @pytest.mark.asyncio
    async def test_route_non_meta_raises_error(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test that routing non-META petition raises ValueError."""
        service = MetaPetitionRoutingService(queue_repository=mock_queue_repo)
        petition = create_petition(petition_type=PetitionType.GENERAL)

        with pytest.raises(ValueError, match="Cannot route non-META petition"):
            await service.route_meta_petition(petition)

        mock_queue_repo.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_route_meta_petition_with_no_submitter(
        self, mock_queue_repo: AsyncMock
    ) -> None:
        """Test routing petition with no submitter_id."""
        service = MetaPetitionRoutingService(queue_repository=mock_queue_repo)
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.META,
            text="Anonymous META petition",
            submitter_id=None,
            state=PetitionState.RECEIVED,
        )

        event = await service.route_meta_petition(petition)

        # Should have zero UUID for anonymous
        assert event.submitter_id is not None
