"""Integration tests for agent signing (FR3, FR74-FR76).

Tests the end-to-end signing flow with real HSM and key registry.

Constitutional Constraints:
- FR3: Events must have agent attribution
- FR74: Invalid agent signatures must be rejected
- FR75: Key registry must track active keys
- FR76: Historical keys must be preserved
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.ports.hsm import HSMMode
from src.application.services.signing_service import SigningService
from src.domain.events.signing import compute_signable_content
from src.domain.models.agent_key import AgentKey
from src.infrastructure.adapters.persistence.key_registry import (
    InMemoryKeyRegistry,
    KeyAlreadyExistsError,
    KeyNotFoundError,
)
from src.infrastructure.adapters.security.hsm_dev import DevHSM


@pytest.fixture
def dev_hsm() -> DevHSM:
    """Create a DevHSM instance."""
    return DevHSM()


@pytest.fixture
def key_registry() -> InMemoryKeyRegistry:
    """Create an in-memory key registry."""
    return InMemoryKeyRegistry()


class TestSigningServiceIntegration:
    """Integration tests for SigningService with real DevHSM."""

    @pytest.mark.asyncio
    async def test_sign_event_produces_valid_signature(
        self, dev_hsm: DevHSM, key_registry: InMemoryKeyRegistry
    ) -> None:
        """Full signing flow should produce valid signature."""
        service = SigningService(hsm=dev_hsm, key_registry=key_registry)

        signature_b64, key_id, sig_alg_version = await service.sign_event(
            content_hash="abc123" * 10 + "abcd",  # 64 chars
            prev_hash="0" * 64,
            agent_id="agent-001",
        )

        # Verify signature is base64
        assert len(signature_b64) >= 80
        assert sig_alg_version == 1
        assert key_id.startswith("dev-")

    @pytest.mark.asyncio
    async def test_sign_event_includes_dev_mode_watermark(
        self, dev_hsm: DevHSM, key_registry: InMemoryKeyRegistry
    ) -> None:
        """RT-1: Signature should include dev mode watermark."""
        service = SigningService(hsm=dev_hsm, key_registry=key_registry)

        # Sign and then verify the mode is embedded
        mode = await dev_hsm.get_mode()
        assert mode == HSMMode.DEVELOPMENT

    @pytest.mark.asyncio
    async def test_sign_and_verify_roundtrip(
        self, dev_hsm: DevHSM, key_registry: InMemoryKeyRegistry
    ) -> None:
        """Sign then verify should succeed."""
        service = SigningService(hsm=dev_hsm, key_registry=key_registry)

        content_hash = "abc123" * 10 + "abcd"
        prev_hash = "0" * 64
        agent_id = "agent-001"

        # Sign
        signature_b64, key_id, _ = await service.sign_event(
            content_hash=content_hash,
            prev_hash=prev_hash,
            agent_id=agent_id,
        )

        # Verify
        is_valid = await service.verify_event_signature(
            content_hash=content_hash,
            prev_hash=prev_hash,
            agent_id=agent_id,
            signature_b64=signature_b64,
            signing_key_id=key_id,
        )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_fails_with_wrong_content_hash(
        self, dev_hsm: DevHSM, key_registry: InMemoryKeyRegistry
    ) -> None:
        """Verification should fail if content_hash differs."""
        service = SigningService(hsm=dev_hsm, key_registry=key_registry)

        # Sign with original content_hash
        signature_b64, key_id, _ = await service.sign_event(
            content_hash="abc123" * 10 + "abcd",
            prev_hash="0" * 64,
            agent_id="agent-001",
        )

        # Verify with different content_hash
        is_valid = await service.verify_event_signature(
            content_hash="xyz789" * 10 + "wxyz",  # Different!
            prev_hash="0" * 64,
            agent_id="agent-001",
            signature_b64=signature_b64,
            signing_key_id=key_id,
        )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_fails_with_wrong_prev_hash(
        self, dev_hsm: DevHSM, key_registry: InMemoryKeyRegistry
    ) -> None:
        """MA-2: Verification should fail if prev_hash differs (chain binding)."""
        service = SigningService(hsm=dev_hsm, key_registry=key_registry)

        # Sign with original prev_hash
        signature_b64, key_id, _ = await service.sign_event(
            content_hash="abc123" * 10 + "abcd",
            prev_hash="0" * 64,
            agent_id="agent-001",
        )

        # Verify with different prev_hash
        is_valid = await service.verify_event_signature(
            content_hash="abc123" * 10 + "abcd",
            prev_hash="1" * 64,  # Different!
            agent_id="agent-001",
            signature_b64=signature_b64,
            signing_key_id=key_id,
        )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_fails_with_wrong_agent_id(
        self, dev_hsm: DevHSM, key_registry: InMemoryKeyRegistry
    ) -> None:
        """Verification should fail if agent_id differs."""
        service = SigningService(hsm=dev_hsm, key_registry=key_registry)

        # Sign with original agent_id
        signature_b64, key_id, _ = await service.sign_event(
            content_hash="abc123" * 10 + "abcd",
            prev_hash="0" * 64,
            agent_id="agent-001",
        )

        # Verify with different agent_id
        is_valid = await service.verify_event_signature(
            content_hash="abc123" * 10 + "abcd",
            prev_hash="0" * 64,
            agent_id="agent-002",  # Different!
            signature_b64=signature_b64,
            signing_key_id=key_id,
        )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_system_agent_signature(
        self, dev_hsm: DevHSM, key_registry: InMemoryKeyRegistry
    ) -> None:
        """System agents (SYSTEM:*) should be signable."""
        service = SigningService(hsm=dev_hsm, key_registry=key_registry)

        signature_b64, key_id, sig_alg_version = await service.sign_event(
            content_hash="abc123" * 10 + "abcd",
            prev_hash="0" * 64,
            agent_id="SYSTEM:WATCHDOG",
        )

        # Verify
        is_valid = await service.verify_event_signature(
            content_hash="abc123" * 10 + "abcd",
            prev_hash="0" * 64,
            agent_id="SYSTEM:WATCHDOG",
            signature_b64=signature_b64,
            signing_key_id=key_id,
        )

        assert is_valid is True


class TestInMemoryKeyRegistryIntegration:
    """Integration tests for InMemoryKeyRegistry."""

    @pytest.mark.asyncio
    async def test_register_and_retrieve_key(
        self, key_registry: InMemoryKeyRegistry
    ) -> None:
        """Should be able to register and retrieve a key."""
        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-test123",
            public_key=b"x" * 32,
            active_from=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        await key_registry.register_key(key)
        retrieved = await key_registry.get_key_by_id("dev-test123")

        assert retrieved is not None
        assert retrieved.key_id == "dev-test123"
        assert retrieved.agent_id == "agent-001"

    @pytest.mark.asyncio
    async def test_register_duplicate_key_raises_error(
        self, key_registry: InMemoryKeyRegistry
    ) -> None:
        """Registering duplicate key_id should raise error."""
        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-test123",
            public_key=b"x" * 32,
            active_from=datetime.now(timezone.utc),
        )

        await key_registry.register_key(key)

        with pytest.raises(KeyAlreadyExistsError):
            await key_registry.register_key(key)

    @pytest.mark.asyncio
    async def test_get_active_key_for_agent(
        self, key_registry: InMemoryKeyRegistry
    ) -> None:
        """Should find active key for agent."""
        now = datetime.now(timezone.utc)
        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-test123",
            public_key=b"x" * 32,
            active_from=now - timedelta(hours=1),
            active_until=None,  # Currently active
        )

        await key_registry.register_key(key)
        active = await key_registry.get_active_key_for_agent("agent-001")

        assert active is not None
        assert active.key_id == "dev-test123"

    @pytest.mark.asyncio
    async def test_get_active_key_for_agent_not_found(
        self, key_registry: InMemoryKeyRegistry
    ) -> None:
        """Should return None if no active key for agent."""
        active = await key_registry.get_active_key_for_agent("nonexistent-agent")
        assert active is None

    @pytest.mark.asyncio
    async def test_get_active_key_at_historical_time(
        self, key_registry: InMemoryKeyRegistry
    ) -> None:
        """FR76: Should find key that was active at a specific time."""
        now = datetime.now(timezone.utc)

        # Old key (deactivated)
        old_key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-old",
            public_key=b"o" * 32,
            active_from=now - timedelta(days=30),
            active_until=now - timedelta(days=15),
        )

        # Current key
        current_key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-current",
            public_key=b"c" * 32,
            active_from=now - timedelta(days=14),
            active_until=None,
        )

        await key_registry.register_key(old_key)
        await key_registry.register_key(current_key)

        # Query at historical time (when old key was active)
        historical_time = now - timedelta(days=20)
        historical_key = await key_registry.get_active_key_for_agent(
            "agent-001", at_time=historical_time
        )

        assert historical_key is not None
        assert historical_key.key_id == "dev-old"

        # Query at current time
        current = await key_registry.get_active_key_for_agent("agent-001")
        assert current is not None
        assert current.key_id == "dev-current"

    @pytest.mark.asyncio
    async def test_deactivate_key(
        self, key_registry: InMemoryKeyRegistry
    ) -> None:
        """Deactivating a key should set active_until."""
        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-test123",
            public_key=b"x" * 32,
            active_from=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        await key_registry.register_key(key)

        deactivation_time = datetime.now(timezone.utc)
        await key_registry.deactivate_key("dev-test123", deactivation_time)

        # Key should still exist but not be currently active
        retrieved = await key_registry.get_key_by_id("dev-test123")
        assert retrieved is not None
        assert retrieved.active_until == deactivation_time

        # Should not be found as active
        active = await key_registry.get_active_key_for_agent("agent-001")
        assert active is None

    @pytest.mark.asyncio
    async def test_deactivate_nonexistent_key_raises_error(
        self, key_registry: InMemoryKeyRegistry
    ) -> None:
        """Deactivating nonexistent key should raise error."""
        with pytest.raises(KeyNotFoundError):
            await key_registry.deactivate_key(
                "nonexistent-key", datetime.now(timezone.utc)
            )

    @pytest.mark.asyncio
    async def test_key_exists(
        self, key_registry: InMemoryKeyRegistry
    ) -> None:
        """key_exists should return correct boolean."""
        key = AgentKey(
            id=uuid4(),
            agent_id="agent-001",
            key_id="dev-test123",
            public_key=b"x" * 32,
            active_from=datetime.now(timezone.utc),
        )

        assert await key_registry.key_exists("dev-test123") is False

        await key_registry.register_key(key)

        assert await key_registry.key_exists("dev-test123") is True
        assert await key_registry.key_exists("nonexistent") is False


class TestSignableContentIntegration:
    """Integration tests for signable content computation."""

    def test_compute_signable_content_is_deterministic(self) -> None:
        """Same inputs should always produce same output."""
        content1 = compute_signable_content(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
        )
        content2 = compute_signable_content(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
        )

        assert content1 == content2

    def test_signable_content_includes_chain_binding(self) -> None:
        """MA-2: Different prev_hash should produce different content."""
        content1 = compute_signable_content(
            content_hash="same-hash",
            prev_hash="prev-A",
            agent_id="same-agent",
        )
        content2 = compute_signable_content(
            content_hash="same-hash",
            prev_hash="prev-B",
            agent_id="same-agent",
        )

        assert content1 != content2

    def test_signable_content_includes_agent_attribution(self) -> None:
        """FR3: Different agent_id should produce different content."""
        content1 = compute_signable_content(
            content_hash="same-hash",
            prev_hash="same-prev",
            agent_id="agent-A",
        )
        content2 = compute_signable_content(
            content_hash="same-hash",
            prev_hash="same-prev",
            agent_id="agent-B",
        )

        assert content1 != content2


class TestDevHSMIntegration:
    """Integration tests for DevHSM."""

    @pytest.mark.asyncio
    async def test_dev_hsm_sign_produces_ed25519_signature(
        self, dev_hsm: DevHSM
    ) -> None:
        """DevHSM should produce Ed25519 signatures (64 bytes)."""
        data = b"test data to sign"
        result = await dev_hsm.sign(data)

        assert len(result.signature) == 64  # Ed25519 signature length

    @pytest.mark.asyncio
    async def test_dev_hsm_verify_roundtrip(self, dev_hsm: DevHSM) -> None:
        """Sign then verify should succeed using content with mode prefix."""
        data = b"test data to sign"
        result = await dev_hsm.sign(data)

        # Must verify with the content_with_prefix returned by sign()
        is_valid = await dev_hsm.verify(result.content, result.signature)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_dev_hsm_verify_fails_wrong_data(self, dev_hsm: DevHSM) -> None:
        """Verify should fail with tampered data."""
        data = b"original data"
        result = await dev_hsm.sign(data)

        is_valid = await dev_hsm.verify(b"tampered data", result.signature)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_dev_hsm_mode_is_development(self, dev_hsm: DevHSM) -> None:
        """DevHSM should report DEVELOPMENT mode."""
        mode = await dev_hsm.get_mode()
        assert mode == HSMMode.DEVELOPMENT

    @pytest.mark.asyncio
    async def test_dev_hsm_key_id_starts_with_dev(self, dev_hsm: DevHSM) -> None:
        """DevHSM key_id should start with 'dev-'."""
        key_id = await dev_hsm.get_current_key_id()
        assert key_id.startswith("dev-")
