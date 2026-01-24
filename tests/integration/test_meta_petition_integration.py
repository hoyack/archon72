"""Integration tests for META Petition Routing (Story 8.5, FR-10.4).

Tests the complete META petition flow:
1. META petition detection and routing to High Archon queue
2. Queue listing with FIFO ordering (AC3)
3. Resolution with disposition (AC4)
4. Event emission for witnessing (AC6, CT-12)

Constitutional Constraints:
- FR-10.4: META petitions (about petition system) SHALL route to High Archon [P2]
- META-1: Prevents deliberation deadlock from system-about-system petitions
- CT-11: Silent failure destroys legitimacy -> All operations logged
- CT-12: Witnessing creates accountability -> Events for all operations
"""

from __future__ import annotations

# Direct imports to avoid infrastructure __init__ chain issues
import importlib.util
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

# Load routing service
_routing_spec = importlib.util.spec_from_file_location(
    "meta_petition_routing_service",
    "src/application/services/meta_petition_routing_service.py",
)
_routing_module = importlib.util.module_from_spec(_routing_spec)
_routing_spec.loader.exec_module(_routing_module)
MetaPetitionRoutingService = _routing_module.MetaPetitionRoutingService

# Load resolution service
_resolution_spec = importlib.util.spec_from_file_location(
    "meta_petition_resolution_service",
    "src/application/services/meta_petition_resolution_service.py",
)
_resolution_module = importlib.util.module_from_spec(_resolution_spec)
_resolution_spec.loader.exec_module(_resolution_module)
MetaPetitionResolutionService = _resolution_module.MetaPetitionResolutionService

# Load repository stub
_stub_spec = importlib.util.spec_from_file_location(
    "meta_petition_queue_repository_stub",
    "src/infrastructure/stubs/meta_petition_queue_repository_stub.py",
)
_stub_module = importlib.util.module_from_spec(_stub_spec)
_stub_spec.loader.exec_module(_stub_module)
MetaPetitionQueueRepositoryStub = _stub_module.MetaPetitionQueueRepositoryStub

from src.application.ports.meta_petition_event_emitter import (
    MetaPetitionEventEmitterProtocol,
)
from src.application.ports.meta_petition_queue_repository import (
    MetaPetitionAlreadyResolvedError,
)
from src.domain.events.meta_petition import (
    MetaPetitionReceivedEventPayload,
    MetaPetitionResolvedEventPayload,
)
from src.domain.models.meta_petition import MetaDisposition, MetaPetitionStatus
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)


def create_meta_petition(
    text: str = "The petition system timeout of 72 hours is too restrictive",
) -> PetitionSubmission:
    """Create a META type petition for testing."""
    return PetitionSubmission(
        id=uuid4(),
        type=PetitionType.META,
        text=text,
        submitter_id=uuid4(),
        state=PetitionState.RECEIVED,
    )


def create_general_petition(text: str = "General petition") -> PetitionSubmission:
    """Create a GENERAL type petition for testing."""
    return PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text=text,
        submitter_id=uuid4(),
        state=PetitionState.RECEIVED,
    )


@pytest.fixture
def queue_repository() -> MetaPetitionQueueRepositoryStub:
    """Create fresh queue repository stub."""
    return MetaPetitionQueueRepositoryStub()


@pytest.fixture
def mock_event_emitter() -> AsyncMock:
    """Create mock event emitter."""
    return AsyncMock(spec=MetaPetitionEventEmitterProtocol)


@pytest.fixture
def routing_service(
    queue_repository: MetaPetitionQueueRepositoryStub,
    mock_event_emitter: AsyncMock,
) -> MetaPetitionRoutingService:
    """Create routing service with dependencies."""
    return MetaPetitionRoutingService(
        queue_repository=queue_repository,
        event_emitter=mock_event_emitter,
    )


@pytest.fixture
def resolution_service(
    queue_repository: MetaPetitionQueueRepositoryStub,
    mock_event_emitter: AsyncMock,
) -> MetaPetitionResolutionService:
    """Create resolution service with dependencies."""
    return MetaPetitionResolutionService(
        queue_repository=queue_repository,
        event_emitter=mock_event_emitter,
    )


class TestMetaPetitionDetection:
    """Tests for META petition detection (FR-10.4)."""

    def test_meta_type_detected(
        self, routing_service: MetaPetitionRoutingService
    ) -> None:
        """Test that META type petitions are detected for routing."""
        petition = create_meta_petition()

        result = routing_service.should_route_to_high_archon(petition)

        assert result is True

    def test_general_type_not_routed(
        self, routing_service: MetaPetitionRoutingService
    ) -> None:
        """Test that GENERAL type petitions are not routed to High Archon."""
        petition = create_general_petition()

        result = routing_service.should_route_to_high_archon(petition)

        assert result is False

    def test_all_other_types_not_routed(
        self, routing_service: MetaPetitionRoutingService
    ) -> None:
        """Test that non-META types are not routed."""
        other_types = [
            PetitionType.CESSATION,
            PetitionType.GRIEVANCE,
            PetitionType.COLLABORATION,
        ]

        for petition_type in other_types:
            petition = PetitionSubmission(
                id=uuid4(),
                type=petition_type,
                text="Test petition",
                submitter_id=uuid4(),
                state=PetitionState.RECEIVED,
            )

            result = routing_service.should_route_to_high_archon(petition)
            assert result is False, f"{petition_type} should not route to High Archon"


class TestMetaPetitionRouting:
    """Tests for META petition routing to High Archon queue (AC2)."""

    @pytest.mark.asyncio
    async def test_route_meta_petition_creates_queue_entry(
        self,
        routing_service: MetaPetitionRoutingService,
        queue_repository: MetaPetitionQueueRepositoryStub,
    ) -> None:
        """Test that routing creates pending queue entry (AC2)."""
        petition = create_meta_petition()

        _ = await routing_service.route_meta_petition(petition)

        # Verify queue entry was created
        items, total = await queue_repository.get_pending()
        assert total == 1
        assert items[0].petition_id == petition.id
        assert items[0].status == MetaPetitionStatus.PENDING

    @pytest.mark.asyncio
    async def test_route_meta_petition_emits_event(
        self,
        routing_service: MetaPetitionRoutingService,
        mock_event_emitter: AsyncMock,
    ) -> None:
        """Test that routing emits MetaPetitionReceived event (AC6)."""
        petition = create_meta_petition()

        await routing_service.route_meta_petition(petition)

        mock_event_emitter.emit_meta_petition_received.assert_called_once()
        call_args = mock_event_emitter.emit_meta_petition_received.call_args
        event_payload = call_args[0][0]
        assert isinstance(event_payload, MetaPetitionReceivedEventPayload)
        assert event_payload.petition_id == petition.id

    @pytest.mark.asyncio
    async def test_route_non_meta_raises_error(
        self,
        routing_service: MetaPetitionRoutingService,
        queue_repository: MetaPetitionQueueRepositoryStub,
    ) -> None:
        """Test that routing non-META petition raises ValueError."""
        petition = create_general_petition()

        with pytest.raises(ValueError, match="Cannot route non-META"):
            await routing_service.route_meta_petition(petition)

        # Verify nothing was enqueued
        items, total = await queue_repository.get_pending()
        assert total == 0


class TestMetaPetitionQueueOrdering:
    """Tests for queue FIFO ordering (AC3)."""

    @pytest.mark.asyncio
    async def test_queue_returns_fifo_order(
        self,
        routing_service: MetaPetitionRoutingService,
        resolution_service: MetaPetitionResolutionService,
    ) -> None:
        """Test that queue returns oldest petitions first (AC3)."""
        # Route multiple petitions
        petitions = [
            create_meta_petition(f"META petition {i}")
            for i in range(3)
        ]

        for petition in petitions:
            await routing_service.route_meta_petition(petition)

        # Get queue
        items, total = await resolution_service.get_pending_queue()

        # Verify FIFO order (oldest first)
        assert total == 3
        assert items[0].petition_id == petitions[0].id
        assert items[1].petition_id == petitions[1].id
        assert items[2].petition_id == petitions[2].id


class TestMetaPetitionResolution:
    """Tests for High Archon resolution of META petitions (AC4)."""

    @pytest.mark.asyncio
    async def test_resolve_acknowledge(
        self,
        routing_service: MetaPetitionRoutingService,
        resolution_service: MetaPetitionResolutionService,
        queue_repository: MetaPetitionQueueRepositoryStub,
    ) -> None:
        """Test resolving with ACKNOWLEDGE disposition (AC4)."""
        petition = create_meta_petition()
        high_archon_id = uuid4()

        await routing_service.route_meta_petition(petition)

        event = await resolution_service.resolve_meta_petition(
            petition_id=petition.id,
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Acknowledged the system feedback concern",
            high_archon_id=high_archon_id,
        )

        # Verify resolution
        assert event.disposition == MetaDisposition.ACKNOWLEDGE
        assert event.high_archon_id == high_archon_id

        # Verify no longer in pending queue
        items, total = await resolution_service.get_pending_queue()
        assert total == 0

    @pytest.mark.asyncio
    async def test_resolve_create_action(
        self,
        routing_service: MetaPetitionRoutingService,
        resolution_service: MetaPetitionResolutionService,
    ) -> None:
        """Test resolving with CREATE_ACTION disposition (AC4)."""
        petition = create_meta_petition()

        await routing_service.route_meta_petition(petition)

        event = await resolution_service.resolve_meta_petition(
            petition_id=petition.id,
            disposition=MetaDisposition.CREATE_ACTION,
            rationale="Creating governance action item for review",
            high_archon_id=uuid4(),
        )

        assert event.disposition == MetaDisposition.CREATE_ACTION

    @pytest.mark.asyncio
    async def test_resolve_forward_with_target(
        self,
        routing_service: MetaPetitionRoutingService,
        resolution_service: MetaPetitionResolutionService,
    ) -> None:
        """Test resolving with FORWARD disposition (AC4)."""
        petition = create_meta_petition()

        await routing_service.route_meta_petition(petition)

        event = await resolution_service.resolve_meta_petition(
            petition_id=petition.id,
            disposition=MetaDisposition.FORWARD,
            rationale="Forwarding to governance council for review",
            high_archon_id=uuid4(),
            forward_target="governance_council",
        )

        assert event.disposition == MetaDisposition.FORWARD
        assert event.forward_target == "governance_council"

    @pytest.mark.asyncio
    async def test_resolve_emits_event(
        self,
        routing_service: MetaPetitionRoutingService,
        resolution_service: MetaPetitionResolutionService,
        mock_event_emitter: AsyncMock,
    ) -> None:
        """Test that resolution emits MetaPetitionResolved event (AC6)."""
        petition = create_meta_petition()

        await routing_service.route_meta_petition(petition)
        mock_event_emitter.reset_mock()

        await resolution_service.resolve_meta_petition(
            petition_id=petition.id,
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Acknowledged the concern",
            high_archon_id=uuid4(),
        )

        mock_event_emitter.emit_meta_petition_resolved.assert_called_once()
        call_args = mock_event_emitter.emit_meta_petition_resolved.call_args
        event_payload = call_args[0][0]
        assert isinstance(event_payload, MetaPetitionResolvedEventPayload)

    @pytest.mark.asyncio
    async def test_resolve_twice_raises_error(
        self,
        routing_service: MetaPetitionRoutingService,
        resolution_service: MetaPetitionResolutionService,
    ) -> None:
        """Test that resolving twice raises MetaPetitionAlreadyResolvedError."""
        petition = create_meta_petition()

        await routing_service.route_meta_petition(petition)

        # First resolution succeeds
        await resolution_service.resolve_meta_petition(
            petition_id=petition.id,
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="First resolution",
            high_archon_id=uuid4(),
        )

        # Second resolution fails
        with pytest.raises(MetaPetitionAlreadyResolvedError):
            await resolution_service.resolve_meta_petition(
                petition_id=petition.id,
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale="Second resolution",
                high_archon_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_resolve_forward_without_target_raises(
        self,
        routing_service: MetaPetitionRoutingService,
        resolution_service: MetaPetitionResolutionService,
    ) -> None:
        """Test that FORWARD without target raises ValueError."""
        petition = create_meta_petition()

        await routing_service.route_meta_petition(petition)

        with pytest.raises(ValueError, match="forward_target required"):
            await resolution_service.resolve_meta_petition(
                petition_id=petition.id,
                disposition=MetaDisposition.FORWARD,
                rationale="Forwarding without target",
                high_archon_id=uuid4(),
                forward_target=None,
            )


class TestEndToEndMetaPetitionFlow:
    """End-to-end tests for complete META petition lifecycle."""

    @pytest.mark.asyncio
    async def test_complete_meta_petition_lifecycle(
        self,
        routing_service: MetaPetitionRoutingService,
        resolution_service: MetaPetitionResolutionService,
        queue_repository: MetaPetitionQueueRepositoryStub,
        mock_event_emitter: AsyncMock,
    ) -> None:
        """Test complete lifecycle: submit -> queue -> review -> resolve."""
        # Step 1: Create and route META petition
        petition = create_meta_petition(
            "The petition deliberation timeout should be extended"
        )
        high_archon_id = uuid4()

        # Step 2: Route to High Archon queue (AC2)
        _ = await routing_service.route_meta_petition(petition)
        assert received_event.petition_id == petition.id
        assert received_event.routing_reason == "EXPLICIT_META_TYPE"

        # Step 3: Verify in queue (AC3)
        items, total = await resolution_service.get_pending_queue()
        assert total == 1
        assert items[0].petition_id == petition.id
        assert items[0].status == MetaPetitionStatus.PENDING

        # Step 4: High Archon reviews and resolves (AC4)
        resolved_event = await resolution_service.resolve_meta_petition(
            petition_id=petition.id,
            disposition=MetaDisposition.CREATE_ACTION,
            rationale="Valid concern - creating action item for governance review",
            high_archon_id=high_archon_id,
        )

        # Step 5: Verify resolution
        assert resolved_event.disposition == MetaDisposition.CREATE_ACTION
        assert resolved_event.high_archon_id == high_archon_id

        # Step 6: Verify removed from pending queue
        items, total = await resolution_service.get_pending_queue()
        assert total == 0

        # Step 7: Verify events were emitted (AC6, CT-12)
        assert mock_event_emitter.emit_meta_petition_received.call_count == 1
        assert mock_event_emitter.emit_meta_petition_resolved.call_count == 1

    @pytest.mark.asyncio
    async def test_multiple_petitions_fifo_processing(
        self,
        routing_service: MetaPetitionRoutingService,
        resolution_service: MetaPetitionResolutionService,
    ) -> None:
        """Test that multiple petitions are processed in FIFO order."""
        # Route 5 META petitions
        petitions = []
        for i in range(5):
            petition = create_meta_petition(f"META concern {i}")
            petitions.append(petition)
            await routing_service.route_meta_petition(petition)

        # Resolve in order (should be oldest first)
        for i in range(5):
            items, total = await resolution_service.get_pending_queue(limit=1)
            assert items[0].petition_id == petitions[i].id, f"Expected petition {i} first"

            await resolution_service.resolve_meta_petition(
                petition_id=petitions[i].id,
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale=f"Acknowledged concern {i}",
                high_archon_id=uuid4(),
            )

        # Verify all processed
        _, total = await resolution_service.get_pending_queue()
        assert total == 0
