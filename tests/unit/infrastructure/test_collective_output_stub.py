"""Unit tests for CollectiveOutputStub (Story 2.3, FR11).

Tests the infrastructure stub for collective output storage.

RT-1/ADR-4: Dev Mode Watermark
- Stub must include DEV_MODE_WATERMARK for dev mode indication
"""

from uuid import uuid4

import pytest


class TestCollectiveOutputStub:
    """Tests for CollectiveOutputStub infrastructure adapter."""

    def test_stub_exists(self) -> None:
        """CollectiveOutputStub should be importable."""
        from src.infrastructure.stubs.collective_output_stub import (
            CollectiveOutputStub,
        )

        assert CollectiveOutputStub is not None

    def test_stub_has_dev_mode_watermark(self) -> None:
        """Stub should have DEV_MODE_WATERMARK constant (RT-1/ADR-4)."""
        from src.infrastructure.stubs.collective_output_stub import DEV_MODE_WATERMARK

        assert DEV_MODE_WATERMARK is not None
        assert "DEV" in DEV_MODE_WATERMARK or "dev" in DEV_MODE_WATERMARK.lower()

    def test_stub_implements_protocol(self) -> None:
        """CollectiveOutputStub should implement CollectiveOutputPort."""
        from src.application.ports.collective_output import CollectiveOutputPort
        from src.infrastructure.stubs.collective_output_stub import (
            CollectiveOutputStub,
        )

        stub = CollectiveOutputStub()
        assert isinstance(stub, CollectiveOutputPort)

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self) -> None:
        """Stub should store and retrieve collective outputs."""
        from src.domain.events.collective_output import (
            AuthorType,
            CollectiveOutputPayload,
            VoteCounts,
        )
        from src.infrastructure.stubs.collective_output_stub import (
            CollectiveOutputStub,
        )

        stub = CollectiveOutputStub()
        output_id = uuid4()

        payload = CollectiveOutputPayload(
            output_id=output_id,
            author_type=AuthorType.COLLECTIVE,
            contributing_agents=("archon-1", "archon-2"),
            content_hash="a" * 64,
            vote_counts=VoteCounts(yes_count=70, no_count=2, abstain_count=0),
            dissent_percentage=2.78,
            unanimous=False,
            linked_vote_event_ids=(uuid4(), uuid4()),
        )

        stored = await stub.store_collective_output(payload, event_sequence=42)
        assert stored.output_id == output_id
        assert stored.event_sequence == 42

        retrieved = await stub.get_collective_output(output_id)
        assert retrieved is not None
        assert retrieved.output_id == output_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self) -> None:
        """Stub should return None for nonexistent output."""
        from src.infrastructure.stubs.collective_output_stub import (
            CollectiveOutputStub,
        )

        stub = CollectiveOutputStub()
        result = await stub.get_collective_output(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_linked_vote_events(self) -> None:
        """Stub should return linked vote event IDs."""
        from src.domain.events.collective_output import (
            AuthorType,
            CollectiveOutputPayload,
            VoteCounts,
        )
        from src.infrastructure.stubs.collective_output_stub import (
            CollectiveOutputStub,
        )

        stub = CollectiveOutputStub()
        output_id = uuid4()
        vote_id_1 = uuid4()
        vote_id_2 = uuid4()

        payload = CollectiveOutputPayload(
            output_id=output_id,
            author_type=AuthorType.COLLECTIVE,
            contributing_agents=("archon-1", "archon-2"),
            content_hash="a" * 64,
            vote_counts=VoteCounts(yes_count=70, no_count=2, abstain_count=0),
            dissent_percentage=2.78,
            unanimous=False,
            linked_vote_event_ids=(vote_id_1, vote_id_2),
        )

        await stub.store_collective_output(payload, event_sequence=1)

        linked = await stub.get_linked_vote_events(output_id)
        assert len(linked) == 2
        assert vote_id_1 in linked
        assert vote_id_2 in linked

    @pytest.mark.asyncio
    async def test_get_linked_vote_events_nonexistent(self) -> None:
        """Stub should return empty list for nonexistent output."""
        from src.infrastructure.stubs.collective_output_stub import (
            CollectiveOutputStub,
        )

        stub = CollectiveOutputStub()
        linked = await stub.get_linked_vote_events(uuid4())
        assert linked == []

    def test_stub_in_memory_storage(self) -> None:
        """Stub should use in-memory storage (no persistence)."""
        from src.infrastructure.stubs.collective_output_stub import (
            CollectiveOutputStub,
        )

        stub1 = CollectiveOutputStub()
        stub2 = CollectiveOutputStub()
        # Each instance should have its own storage
        assert stub1._storage is not stub2._storage
