"""Unit tests for KeeperKeyRegistryProtocol port (FR68, FR76).

Tests the abstract protocol for Keeper key registry operations.
Validates that implementations provide all required methods.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.models.keeper_key import KeeperKey


class TestKeeperKeyRegistryProtocolCompliance:
    """Test that implementations comply with the protocol."""

    @pytest.mark.asyncio
    async def test_get_key_by_id_returns_key_when_exists(self) -> None:
        """get_key_by_id returns KeeperKey when key exists."""
        from src.infrastructure.stubs.keeper_key_registry_stub import (
            KeeperKeyRegistryStub,
        )

        stub = KeeperKeyRegistryStub(with_dev_key=False)

        key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            key_id="keeper-key-001",
            public_key=b"a" * 32,
            active_from=datetime.now(timezone.utc),
        )
        await stub.register_key(key)

        result = await stub.get_key_by_id("keeper-key-001")
        assert result is not None
        assert result.key_id == "keeper-key-001"
        assert result.keeper_id == "KEEPER:alice"

    @pytest.mark.asyncio
    async def test_get_key_by_id_returns_none_when_not_found(self) -> None:
        """get_key_by_id returns None when key doesn't exist."""
        from src.infrastructure.stubs.keeper_key_registry_stub import (
            KeeperKeyRegistryStub,
        )

        stub = KeeperKeyRegistryStub(with_dev_key=False)
        result = await stub.get_key_by_id("nonexistent-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_key_for_keeper_returns_active_key(self) -> None:
        """get_active_key_for_keeper returns currently active key."""
        from src.infrastructure.stubs.keeper_key_registry_stub import (
            KeeperKeyRegistryStub,
        )

        stub = KeeperKeyRegistryStub(with_dev_key=False)

        key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:bob",
            key_id="keeper-key-002",
            public_key=b"b" * 32,
            active_from=datetime.now(timezone.utc) - timedelta(days=1),
            active_until=None,  # Currently active
        )
        await stub.register_key(key)

        result = await stub.get_active_key_for_keeper("KEEPER:bob")
        assert result is not None
        assert result.keeper_id == "KEEPER:bob"
        assert result.is_currently_active()

    @pytest.mark.asyncio
    async def test_get_active_key_for_keeper_returns_none_when_no_active(self) -> None:
        """get_active_key_for_keeper returns None when no active key."""
        from src.infrastructure.stubs.keeper_key_registry_stub import (
            KeeperKeyRegistryStub,
        )

        stub = KeeperKeyRegistryStub(with_dev_key=False)

        # Add expired key
        key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:charlie",
            key_id="keeper-key-003",
            public_key=b"c" * 32,
            active_from=datetime.now(timezone.utc) - timedelta(days=30),
            active_until=datetime.now(timezone.utc) - timedelta(days=1),  # Expired
        )
        await stub.register_key(key)

        result = await stub.get_active_key_for_keeper("KEEPER:charlie")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_key_for_keeper_at_specific_time(self) -> None:
        """get_active_key_for_keeper returns key active at specified time."""
        from src.infrastructure.stubs.keeper_key_registry_stub import (
            KeeperKeyRegistryStub,
        )

        stub = KeeperKeyRegistryStub(with_dev_key=False)

        # Old key (was active in January)
        old_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:dave",
            key_id="keeper-key-old",
            public_key=b"d" * 32,
            active_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            active_until=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )

        # New key (active from June)
        new_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:dave",
            key_id="keeper-key-new",
            public_key=b"e" * 32,
            active_from=datetime(2025, 6, 1, tzinfo=timezone.utc),
            active_until=None,
        )

        await stub.register_key(old_key)
        await stub.register_key(new_key)

        # Query for January - should get old key
        jan_time = datetime(2025, 3, 15, tzinfo=timezone.utc)
        result = await stub.get_active_key_for_keeper("KEEPER:dave", at_time=jan_time)
        assert result is not None
        assert result.key_id == "keeper-key-old"

        # Query for July - should get new key
        july_time = datetime(2025, 7, 15, tzinfo=timezone.utc)
        result = await stub.get_active_key_for_keeper("KEEPER:dave", at_time=july_time)
        assert result is not None
        assert result.key_id == "keeper-key-new"

    @pytest.mark.asyncio
    async def test_register_key_adds_key_to_registry(self) -> None:
        """register_key adds key to the registry."""
        from src.infrastructure.stubs.keeper_key_registry_stub import (
            KeeperKeyRegistryStub,
        )

        stub = KeeperKeyRegistryStub(with_dev_key=False)

        key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:eve",
            key_id="keeper-key-004",
            public_key=b"f" * 32,
            active_from=datetime.now(timezone.utc),
        )

        await stub.register_key(key)

        assert await stub.key_exists("keeper-key-004")

    @pytest.mark.asyncio
    async def test_deactivate_key_sets_active_until(self) -> None:
        """deactivate_key sets active_until on the key."""
        from src.infrastructure.stubs.keeper_key_registry_stub import (
            KeeperKeyRegistryStub,
        )

        stub = KeeperKeyRegistryStub(with_dev_key=False)

        key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:frank",
            key_id="keeper-key-005",
            public_key=b"g" * 32,
            active_from=datetime.now(timezone.utc) - timedelta(days=10),
        )
        await stub.register_key(key)

        deactivation_time = datetime.now(timezone.utc)
        await stub.deactivate_key("keeper-key-005", deactivation_time)

        result = await stub.get_key_by_id("keeper-key-005")
        assert result is not None
        assert result.active_until == deactivation_time
        assert not result.is_currently_active()

    @pytest.mark.asyncio
    async def test_key_exists_returns_true_for_existing_key(self) -> None:
        """key_exists returns True when key exists."""
        from src.infrastructure.stubs.keeper_key_registry_stub import (
            KeeperKeyRegistryStub,
        )

        stub = KeeperKeyRegistryStub(with_dev_key=False)

        key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:grace",
            key_id="keeper-key-006",
            public_key=b"h" * 32,
            active_from=datetime.now(timezone.utc),
        )
        await stub.register_key(key)

        assert await stub.key_exists("keeper-key-006") is True

    @pytest.mark.asyncio
    async def test_key_exists_returns_false_for_nonexistent_key(self) -> None:
        """key_exists returns False when key doesn't exist."""
        from src.infrastructure.stubs.keeper_key_registry_stub import (
            KeeperKeyRegistryStub,
        )

        stub = KeeperKeyRegistryStub(with_dev_key=False)

        assert await stub.key_exists("nonexistent-key") is False

    @pytest.mark.asyncio
    async def test_get_all_keys_for_keeper_returns_historical_keys(self) -> None:
        """get_all_keys_for_keeper returns all keys including historical (FR76)."""
        from src.infrastructure.stubs.keeper_key_registry_stub import (
            KeeperKeyRegistryStub,
        )

        stub = KeeperKeyRegistryStub(with_dev_key=False)

        # Old key
        old_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:henry",
            key_id="keeper-key-old-henry",
            public_key=b"i" * 32,
            active_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            active_until=datetime(2024, 12, 31, tzinfo=timezone.utc),
        )

        # Current key
        current_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:henry",
            key_id="keeper-key-new-henry",
            public_key=b"j" * 32,
            active_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            active_until=None,
        )

        await stub.register_key(old_key)
        await stub.register_key(current_key)

        all_keys = await stub.get_all_keys_for_keeper("KEEPER:henry")
        assert len(all_keys) == 2

        key_ids = {k.key_id for k in all_keys}
        assert "keeper-key-old-henry" in key_ids
        assert "keeper-key-new-henry" in key_ids


class TestKeeperKeyRegistryProtocolDefinition:
    """Test that the protocol is properly defined."""

    def test_protocol_is_importable(self) -> None:
        """KeeperKeyRegistryProtocol can be imported."""
        from src.application.ports.keeper_key_registry import (
            KeeperKeyRegistryProtocol,
        )

        assert KeeperKeyRegistryProtocol is not None

    def test_protocol_has_required_methods(self) -> None:
        """Protocol defines all required methods."""
        from src.application.ports.keeper_key_registry import (
            KeeperKeyRegistryProtocol,
        )

        # Check method names are defined
        assert hasattr(KeeperKeyRegistryProtocol, "get_key_by_id")
        assert hasattr(KeeperKeyRegistryProtocol, "get_active_key_for_keeper")
        assert hasattr(KeeperKeyRegistryProtocol, "register_key")
        assert hasattr(KeeperKeyRegistryProtocol, "deactivate_key")
        assert hasattr(KeeperKeyRegistryProtocol, "key_exists")
        assert hasattr(KeeperKeyRegistryProtocol, "get_all_keys_for_keeper")
