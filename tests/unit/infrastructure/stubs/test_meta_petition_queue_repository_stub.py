"""Unit tests for MetaPetitionQueueRepositoryStub (Story 8.5, FR-10.4).

These tests verify the in-memory stub implementation of the META petition
queue repository.

Tests:
1. Enqueue operations
2. Get pending (FIFO ordering)
3. Get by petition ID
4. Mark resolved operations
5. Get resolved (most recent first)
6. Error handling
"""

import sys
from uuid import uuid4

import pytest

# Workaround for import chain issues in test environment
if "src.infrastructure" in sys.modules:
    del sys.modules["src.infrastructure"]

# Direct import to avoid infrastructure __init__ chain
import importlib.util

from src.application.ports.meta_petition_queue_repository import (
    MetaPetitionAlreadyResolvedError,
    MetaPetitionNotFoundError,
    PetitionAlreadyInQueueError,
)
from src.domain.models.meta_petition import MetaDisposition, MetaPetitionStatus

spec = importlib.util.spec_from_file_location(
    "meta_petition_queue_repository_stub",
    "src/infrastructure/stubs/meta_petition_queue_repository_stub.py",
)
stub_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stub_module)
MetaPetitionQueueRepositoryStub = stub_module.MetaPetitionQueueRepositoryStub


class TestMetaPetitionQueueEnqueue:
    """Tests for enqueue operation."""

    @pytest.fixture
    def repo(self) -> MetaPetitionQueueRepositoryStub:
        """Create fresh repository for each test."""
        return MetaPetitionQueueRepositoryStub()

    @pytest.mark.asyncio
    async def test_enqueue_creates_pending_item(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test that enqueue creates item with PENDING status."""
        petition_id = uuid4()
        submitter_id = uuid4()

        item = await repo.enqueue(
            petition_id=petition_id,
            submitter_id=submitter_id,
            petition_text="Test META petition",
        )

        assert item.petition_id == petition_id
        assert item.submitter_id == submitter_id
        assert item.petition_text == "Test META petition"
        assert item.status == MetaPetitionStatus.PENDING
        assert item.received_at is not None

    @pytest.mark.asyncio
    async def test_enqueue_duplicate_raises_error(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test that enqueueing same petition twice raises error."""
        petition_id = uuid4()

        await repo.enqueue(
            petition_id=petition_id,
            submitter_id=uuid4(),
            petition_text="First",
        )

        with pytest.raises(PetitionAlreadyInQueueError) as exc_info:
            await repo.enqueue(
                petition_id=petition_id,
                submitter_id=uuid4(),
                petition_text="Second",
            )

        assert exc_info.value.petition_id == petition_id

    @pytest.mark.asyncio
    async def test_enqueue_without_submitter_id(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test enqueue with None submitter_id."""
        petition_id = uuid4()

        item = await repo.enqueue(
            petition_id=petition_id,
            submitter_id=None,
            petition_text="Anonymous petition",
        )

        assert item.petition_id == petition_id
        assert item.status == MetaPetitionStatus.PENDING


class TestMetaPetitionQueueGetPending:
    """Tests for get_pending operation (AC3 FIFO ordering)."""

    @pytest.fixture
    def repo(self) -> MetaPetitionQueueRepositoryStub:
        """Create fresh repository for each test."""
        return MetaPetitionQueueRepositoryStub()

    @pytest.mark.asyncio
    async def test_get_pending_returns_fifo_order(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test that pending items are returned oldest first (FIFO)."""
        ids = [uuid4() for _ in range(3)]

        # Enqueue in order
        for i, pid in enumerate(ids):
            await repo.enqueue(
                petition_id=pid,
                submitter_id=uuid4(),
                petition_text=f"Petition {i}",
            )

        items, total = await repo.get_pending()

        assert total == 3
        assert len(items) == 3
        # FIFO: oldest first
        assert items[0].petition_id == ids[0]
        assert items[1].petition_id == ids[1]
        assert items[2].petition_id == ids[2]

    @pytest.mark.asyncio
    async def test_get_pending_excludes_resolved(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test that resolved items are not returned in pending list."""
        pending_id = uuid4()
        resolved_id = uuid4()

        await repo.enqueue(
            petition_id=pending_id,
            submitter_id=uuid4(),
            petition_text="Pending",
        )
        await repo.enqueue(
            petition_id=resolved_id,
            submitter_id=uuid4(),
            petition_text="To be resolved",
        )

        # Resolve one
        await repo.mark_resolved(
            petition_id=resolved_id,
            high_archon_id=uuid4(),
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Test rationale",
        )

        items, total = await repo.get_pending()

        assert total == 1
        assert items[0].petition_id == pending_id

    @pytest.mark.asyncio
    async def test_get_pending_pagination(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test pagination of pending items."""
        ids = [uuid4() for _ in range(5)]

        for pid in ids:
            await repo.enqueue(
                petition_id=pid,
                submitter_id=uuid4(),
                petition_text="Test",
            )

        # Get first page
        items, total = await repo.get_pending(limit=2, offset=0)
        assert total == 5
        assert len(items) == 2
        assert items[0].petition_id == ids[0]

        # Get second page
        items, total = await repo.get_pending(limit=2, offset=2)
        assert total == 5
        assert len(items) == 2
        assert items[0].petition_id == ids[2]

    @pytest.mark.asyncio
    async def test_get_pending_empty_queue(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test get_pending on empty queue."""
        items, total = await repo.get_pending()

        assert total == 0
        assert len(items) == 0


class TestMetaPetitionQueueGetByPetitionId:
    """Tests for get_by_petition_id operation."""

    @pytest.fixture
    def repo(self) -> MetaPetitionQueueRepositoryStub:
        """Create fresh repository for each test."""
        return MetaPetitionQueueRepositoryStub()

    @pytest.mark.asyncio
    async def test_get_by_petition_id_found(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test retrieving existing queue item."""
        petition_id = uuid4()

        await repo.enqueue(
            petition_id=petition_id,
            submitter_id=uuid4(),
            petition_text="Test",
        )

        item = await repo.get_by_petition_id(petition_id)

        assert item is not None
        assert item.petition_id == petition_id

    @pytest.mark.asyncio
    async def test_get_by_petition_id_not_found(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test retrieving non-existent queue item."""
        item = await repo.get_by_petition_id(uuid4())

        assert item is None


class TestMetaPetitionQueueMarkResolved:
    """Tests for mark_resolved operation (AC4)."""

    @pytest.fixture
    def repo(self) -> MetaPetitionQueueRepositoryStub:
        """Create fresh repository for each test."""
        return MetaPetitionQueueRepositoryStub()

    @pytest.mark.asyncio
    async def test_mark_resolved_acknowledge(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test resolving with ACKNOWLEDGE disposition."""
        petition_id = uuid4()
        high_archon_id = uuid4()

        await repo.enqueue(
            petition_id=petition_id,
            submitter_id=uuid4(),
            petition_text="Test",
        )

        item = await repo.mark_resolved(
            petition_id=petition_id,
            high_archon_id=high_archon_id,
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Acknowledged the concern",
        )

        assert item.status == MetaPetitionStatus.RESOLVED

        # Verify resolution details
        details = repo.get_resolution_details(petition_id)
        assert details is not None
        assert details["resolved_by"] == high_archon_id
        assert details["disposition"] == MetaDisposition.ACKNOWLEDGE
        assert details["rationale"] == "Acknowledged the concern"

    @pytest.mark.asyncio
    async def test_mark_resolved_create_action(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test resolving with CREATE_ACTION disposition."""
        petition_id = uuid4()

        await repo.enqueue(
            petition_id=petition_id,
            submitter_id=uuid4(),
            petition_text="Test",
        )

        item = await repo.mark_resolved(
            petition_id=petition_id,
            high_archon_id=uuid4(),
            disposition=MetaDisposition.CREATE_ACTION,
            rationale="Creating governance action",
        )

        assert item.status == MetaPetitionStatus.RESOLVED
        details = repo.get_resolution_details(petition_id)
        assert details["disposition"] == MetaDisposition.CREATE_ACTION

    @pytest.mark.asyncio
    async def test_mark_resolved_forward_with_target(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test resolving with FORWARD disposition and target."""
        petition_id = uuid4()

        await repo.enqueue(
            petition_id=petition_id,
            submitter_id=uuid4(),
            petition_text="Test",
        )

        item = await repo.mark_resolved(
            petition_id=petition_id,
            high_archon_id=uuid4(),
            disposition=MetaDisposition.FORWARD,
            rationale="Forwarding to council",
            forward_target="governance_council",
        )

        assert item.status == MetaPetitionStatus.RESOLVED
        details = repo.get_resolution_details(petition_id)
        assert details["disposition"] == MetaDisposition.FORWARD
        assert details["forward_target"] == "governance_council"

    @pytest.mark.asyncio
    async def test_mark_resolved_forward_without_target_raises(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test FORWARD without target raises error."""
        petition_id = uuid4()

        await repo.enqueue(
            petition_id=petition_id,
            submitter_id=uuid4(),
            petition_text="Test",
        )

        with pytest.raises(ValueError, match="forward_target required"):
            await repo.mark_resolved(
                petition_id=petition_id,
                high_archon_id=uuid4(),
                disposition=MetaDisposition.FORWARD,
                rationale="Forwarding",
                forward_target=None,
            )

    @pytest.mark.asyncio
    async def test_mark_resolved_not_found(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test resolving non-existent petition raises error."""
        with pytest.raises(MetaPetitionNotFoundError):
            await repo.mark_resolved(
                petition_id=uuid4(),
                high_archon_id=uuid4(),
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale="Test",
            )

    @pytest.mark.asyncio
    async def test_mark_resolved_already_resolved(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test resolving already-resolved petition raises error."""
        petition_id = uuid4()

        await repo.enqueue(
            petition_id=petition_id,
            submitter_id=uuid4(),
            petition_text="Test",
        )

        await repo.mark_resolved(
            petition_id=petition_id,
            high_archon_id=uuid4(),
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="First resolution",
        )

        with pytest.raises(MetaPetitionAlreadyResolvedError):
            await repo.mark_resolved(
                petition_id=petition_id,
                high_archon_id=uuid4(),
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale="Second resolution",
            )


class TestMetaPetitionQueueGetResolved:
    """Tests for get_resolved operation."""

    @pytest.fixture
    def repo(self) -> MetaPetitionQueueRepositoryStub:
        """Create fresh repository for each test."""
        return MetaPetitionQueueRepositoryStub()

    @pytest.mark.asyncio
    async def test_get_resolved_most_recent_first(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test that resolved items are returned most recent first."""
        ids = [uuid4() for _ in range(3)]

        # Enqueue all
        for pid in ids:
            await repo.enqueue(
                petition_id=pid,
                submitter_id=uuid4(),
                petition_text="Test",
            )

        # Resolve in order
        for pid in ids:
            await repo.mark_resolved(
                petition_id=pid,
                high_archon_id=uuid4(),
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale="Test",
            )

        items, total = await repo.get_resolved()

        assert total == 3
        # Most recent first (last resolved = first in list)
        assert items[0].petition_id == ids[2]

    @pytest.mark.asyncio
    async def test_get_resolved_excludes_pending(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test that pending items are not returned in resolved list."""
        pending_id = uuid4()
        resolved_id = uuid4()

        await repo.enqueue(
            petition_id=pending_id,
            submitter_id=uuid4(),
            petition_text="Pending",
        )
        await repo.enqueue(
            petition_id=resolved_id,
            submitter_id=uuid4(),
            petition_text="Resolved",
        )

        await repo.mark_resolved(
            petition_id=resolved_id,
            high_archon_id=uuid4(),
            disposition=MetaDisposition.ACKNOWLEDGE,
            rationale="Test",
        )

        items, total = await repo.get_resolved()

        assert total == 1
        assert items[0].petition_id == resolved_id


class TestMetaPetitionQueueCountPending:
    """Tests for count_pending operation."""

    @pytest.fixture
    def repo(self) -> MetaPetitionQueueRepositoryStub:
        """Create fresh repository for each test."""
        return MetaPetitionQueueRepositoryStub()

    @pytest.mark.asyncio
    async def test_count_pending_empty(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test count on empty queue."""
        count = await repo.count_pending()
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_pending_with_items(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test count with pending items."""
        for _ in range(5):
            await repo.enqueue(
                petition_id=uuid4(),
                submitter_id=uuid4(),
                petition_text="Test",
            )

        count = await repo.count_pending()
        assert count == 5

    @pytest.mark.asyncio
    async def test_count_pending_excludes_resolved(
        self, repo: MetaPetitionQueueRepositoryStub
    ) -> None:
        """Test count excludes resolved items."""
        ids = [uuid4() for _ in range(5)]

        for pid in ids:
            await repo.enqueue(
                petition_id=pid,
                submitter_id=uuid4(),
                petition_text="Test",
            )

        # Resolve 2
        for pid in ids[:2]:
            await repo.mark_resolved(
                petition_id=pid,
                high_archon_id=uuid4(),
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale="Test",
            )

        count = await repo.count_pending()
        assert count == 3
