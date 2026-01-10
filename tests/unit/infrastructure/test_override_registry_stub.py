"""Unit tests for OverrideRegistryStub (Story 5.2, AC2).

Tests verify the in-memory override registry stub correctly:
- Registers active overrides
- Detects expired overrides
- Marks overrides as reverted
- Reports active/inactive state correctly
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.infrastructure.stubs.override_registry_stub import OverrideRegistryStub


class TestOverrideRegistryStubRegistration:
    """Tests for override registration."""

    @pytest.fixture
    def registry(self) -> OverrideRegistryStub:
        """Create a fresh registry for each test."""
        return OverrideRegistryStub()

    @pytest.mark.asyncio
    async def test_register_active_override(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test registering an active override."""
        override_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        await registry.register_active_override(
            override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expires_at=expires_at,
        )

        # Should be active
        assert await registry.is_override_active(override_id)

    @pytest.mark.asyncio
    async def test_register_multiple_overrides(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test registering multiple active overrides."""
        override_ids = [uuid4() for _ in range(3)]
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        for i, oid in enumerate(override_ids):
            await registry.register_active_override(
                override_id=oid,
                keeper_id=f"keeper-{i:03d}",
                scope=f"scope.{i}",
                expires_at=expires_at,
            )

        # All should be active
        for oid in override_ids:
            assert await registry.is_override_active(oid)


class TestOverrideRegistryStubExpiration:
    """Tests for expired override detection."""

    @pytest.fixture
    def registry(self) -> OverrideRegistryStub:
        """Create a fresh registry for each test."""
        return OverrideRegistryStub()

    @pytest.mark.asyncio
    async def test_get_expired_overrides_none(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test getting expired overrides when none have expired."""
        override_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        await registry.register_active_override(
            override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expires_at=expires_at,
        )

        expired = await registry.get_expired_overrides()
        assert len(expired) == 0

    @pytest.mark.asyncio
    async def test_get_expired_overrides_one_expired(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test getting expired overrides when one has expired."""
        override_id = uuid4()
        # Already expired
        expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        await registry.register_active_override(
            override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expires_at=expires_at,
        )

        expired = await registry.get_expired_overrides()
        assert len(expired) == 1
        assert expired[0].override_id == override_id
        assert expired[0].keeper_id == "keeper-001"
        assert expired[0].scope == "config.parameter"

    @pytest.mark.asyncio
    async def test_get_expired_overrides_mixed(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test getting expired overrides with mix of expired/active."""
        expired_id = uuid4()
        active_id = uuid4()

        # Expired
        await registry.register_active_override(
            override_id=expired_id,
            keeper_id="keeper-001",
            scope="scope.expired",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )

        # Still active
        await registry.register_active_override(
            override_id=active_id,
            keeper_id="keeper-002",
            scope="scope.active",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        expired = await registry.get_expired_overrides()
        assert len(expired) == 1
        assert expired[0].override_id == expired_id


class TestOverrideRegistryStubReversion:
    """Tests for marking overrides as reverted."""

    @pytest.fixture
    def registry(self) -> OverrideRegistryStub:
        """Create a fresh registry for each test."""
        return OverrideRegistryStub()

    @pytest.mark.asyncio
    async def test_mark_override_reverted(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test marking an override as reverted."""
        override_id = uuid4()
        # Already expired
        expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        await registry.register_active_override(
            override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expires_at=expires_at,
        )

        # Should show as expired
        expired = await registry.get_expired_overrides()
        assert len(expired) == 1

        # Mark as reverted
        await registry.mark_override_reverted(override_id)

        # Should no longer show as expired
        expired = await registry.get_expired_overrides()
        assert len(expired) == 0

    @pytest.mark.asyncio
    async def test_reverted_override_not_active(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test that reverted override is not active."""
        override_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        await registry.register_active_override(
            override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expires_at=expires_at,
        )

        # Should be active
        assert await registry.is_override_active(override_id)

        # Mark as reverted
        await registry.mark_override_reverted(override_id)

        # Should no longer be active
        assert not await registry.is_override_active(override_id)

    @pytest.mark.asyncio
    async def test_mark_nonexistent_override_no_error(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test that marking nonexistent override doesn't raise."""
        # Should not raise
        await registry.mark_override_reverted(uuid4())


class TestOverrideRegistryStubActiveState:
    """Tests for active state checking."""

    @pytest.fixture
    def registry(self) -> OverrideRegistryStub:
        """Create a fresh registry for each test."""
        return OverrideRegistryStub()

    @pytest.mark.asyncio
    async def test_nonexistent_override_not_active(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test that nonexistent override is not active."""
        assert not await registry.is_override_active(uuid4())

    @pytest.mark.asyncio
    async def test_expired_override_not_active(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test that expired override is not active."""
        override_id = uuid4()
        # Already expired
        expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        await registry.register_active_override(
            override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expires_at=expires_at,
        )

        # Should not be active (expired)
        assert not await registry.is_override_active(override_id)

    @pytest.mark.asyncio
    async def test_active_override_is_active(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test that non-expired override is active."""
        override_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        await registry.register_active_override(
            override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expires_at=expires_at,
        )

        # Should be active
        assert await registry.is_override_active(override_id)
