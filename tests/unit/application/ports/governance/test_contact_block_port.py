"""Unit tests for ContactBlockPort interface.

Story: consent-gov-7.4: Follow-Up Contact Prevention

Tests:
- Port interface has required methods
- Port interface has NO unblock methods (structural prohibition)
- Fake implementation for testing
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.contact_block_port import ContactBlockPort
from src.domain.governance.exit.contact_block import ContactBlock
from src.domain.governance.exit.contact_block_status import ContactBlockStatus


class FakeContactBlockAdapter:
    """Fake adapter for testing ContactBlockPort."""

    def __init__(self) -> None:
        self._blocks: dict[UUID, ContactBlock] = {}

    async def add_block(self, block: ContactBlock) -> None:
        """Add a contact block."""
        if block.cluster_id in self._blocks:
            raise ValueError(f"Block already exists for cluster: {block.cluster_id}")
        self._blocks[block.cluster_id] = block

    async def is_blocked(self, cluster_id: UUID) -> bool:
        """Check if cluster is blocked."""
        return cluster_id in self._blocks

    async def get_block(self, cluster_id: UUID) -> ContactBlock | None:
        """Get block for cluster."""
        return self._blocks.get(cluster_id)

    async def get_all_blocked(self) -> list[UUID]:
        """Get all blocked cluster IDs."""
        return list(self._blocks.keys())


class TestContactBlockPortInterface:
    """Tests for ContactBlockPort interface definition."""

    def test_port_has_add_block_method(self):
        """Port defines add_block method."""
        assert hasattr(ContactBlockPort, "add_block")

    def test_port_has_is_blocked_method(self):
        """Port defines is_blocked method."""
        assert hasattr(ContactBlockPort, "is_blocked")

    def test_port_has_get_block_method(self):
        """Port defines get_block method."""
        assert hasattr(ContactBlockPort, "get_block")

    def test_port_has_get_all_blocked_method(self):
        """Port defines get_all_blocked method."""
        assert hasattr(ContactBlockPort, "get_all_blocked")


class TestContactBlockPortStructuralProhibition:
    """Tests verifying structural prohibition - no unblock methods."""

    def test_no_remove_block_method(self):
        """Port has no remove_block method (NFR-EXIT-02)."""
        assert not hasattr(ContactBlockPort, "remove_block")

    def test_no_unblock_method(self):
        """Port has no unblock method (NFR-EXIT-02)."""
        assert not hasattr(ContactBlockPort, "unblock")

    def test_no_allow_contact_method(self):
        """Port has no allow_contact method (NFR-EXIT-02)."""
        assert not hasattr(ContactBlockPort, "allow_contact")

    def test_no_delete_block_method(self):
        """Port has no delete_block method (NFR-EXIT-02)."""
        assert not hasattr(ContactBlockPort, "delete_block")

    def test_no_enable_contact_method(self):
        """Port has no enable_contact method (NFR-EXIT-02)."""
        assert not hasattr(ContactBlockPort, "enable_contact")

    def test_no_reactivate_contact_method(self):
        """Port has no reactivate_contact method (NFR-EXIT-02)."""
        assert not hasattr(ContactBlockPort, "reactivate_contact")

    def test_no_lift_block_method(self):
        """Port has no lift_block method (NFR-EXIT-02)."""
        assert not hasattr(ContactBlockPort, "lift_block")

    def test_no_temporary_allow_method(self):
        """Port has no temporary_allow method (NFR-EXIT-02)."""
        assert not hasattr(ContactBlockPort, "temporary_allow")


class TestFakeContactBlockAdapter:
    """Tests for fake adapter implementation."""

    @pytest.fixture
    def adapter(self) -> FakeContactBlockAdapter:
        """Create fresh adapter for each test."""
        return FakeContactBlockAdapter()

    @pytest.mark.asyncio
    async def test_add_block(self, adapter: FakeContactBlockAdapter):
        """Can add a block."""
        cluster_id = uuid4()
        block = ContactBlock(
            block_id=uuid4(),
            cluster_id=cluster_id,
            blocked_at=datetime.now(timezone.utc),
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        await adapter.add_block(block)

        assert await adapter.is_blocked(cluster_id)

    @pytest.mark.asyncio
    async def test_add_block_duplicate_raises(self, adapter: FakeContactBlockAdapter):
        """Cannot add duplicate block."""
        cluster_id = uuid4()
        block = ContactBlock(
            block_id=uuid4(),
            cluster_id=cluster_id,
            blocked_at=datetime.now(timezone.utc),
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        await adapter.add_block(block)

        with pytest.raises(ValueError):
            await adapter.add_block(block)

    @pytest.mark.asyncio
    async def test_is_blocked_returns_false_for_unknown(
        self, adapter: FakeContactBlockAdapter
    ):
        """is_blocked returns False for unknown cluster."""
        assert not await adapter.is_blocked(uuid4())

    @pytest.mark.asyncio
    async def test_get_block_returns_none_for_unknown(
        self, adapter: FakeContactBlockAdapter
    ):
        """get_block returns None for unknown cluster."""
        assert await adapter.get_block(uuid4()) is None

    @pytest.mark.asyncio
    async def test_get_block_returns_block(self, adapter: FakeContactBlockAdapter):
        """get_block returns the block."""
        cluster_id = uuid4()
        block = ContactBlock(
            block_id=uuid4(),
            cluster_id=cluster_id,
            blocked_at=datetime.now(timezone.utc),
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        await adapter.add_block(block)

        retrieved = await adapter.get_block(cluster_id)
        assert retrieved == block

    @pytest.mark.asyncio
    async def test_get_all_blocked_empty(self, adapter: FakeContactBlockAdapter):
        """get_all_blocked returns empty list initially."""
        assert await adapter.get_all_blocked() == []

    @pytest.mark.asyncio
    async def test_get_all_blocked_returns_ids(self, adapter: FakeContactBlockAdapter):
        """get_all_blocked returns all blocked IDs."""
        cluster_ids = [uuid4() for _ in range(3)]

        for cluster_id in cluster_ids:
            block = ContactBlock(
                block_id=uuid4(),
                cluster_id=cluster_id,
                blocked_at=datetime.now(timezone.utc),
                reason="exit",
                status=ContactBlockStatus.PERMANENTLY_BLOCKED,
            )
            await adapter.add_block(block)

        blocked = await adapter.get_all_blocked()
        assert len(blocked) == 3
        assert set(blocked) == set(cluster_ids)

    @pytest.mark.asyncio
    async def test_fake_adapter_has_no_remove_method(
        self, adapter: FakeContactBlockAdapter
    ):
        """Fake adapter also has no remove method."""
        assert not hasattr(adapter, "remove_block")
        assert not hasattr(adapter, "unblock")
