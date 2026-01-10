"""Integration tests for Keeper Key Cryptographic Signature (FR68-FR70).

These tests validate the end-to-end signature verification workflow
for Keeper overrides. They use stub implementations to simulate
the full flow without requiring actual HSM infrastructure.

Constitutional Constraints Being Verified:
- FR68: Override commands require cryptographic signature from registered Keeper key
- FR69: Keeper keys generated through witnessed ceremony (mocked)
- FR70: Full authorization chain from Keeper identity through execution

Acceptance Criteria:
- AC1: Override includes cryptographic signature, verified against registry
- AC2: Invalid signature rejected, logged with "FR68: Invalid Keeper signature"
- AC3: Registry shows keeper_id, public_key, active_from, active_until; historical preserved
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.services.keeper_signature_service import (
    KeeperSignatureService,
    KeeperSignedOverride,
)
from src.domain.errors.keeper_signature import (
    InvalidKeeperSignatureError,
    KeeperKeyNotFoundError,
)
from src.domain.events.override_event import ActionType, OverrideEventPayload
from src.domain.models.keeper_key import KEEPER_ID_PREFIX, KeeperKey
from src.infrastructure.adapters.security.hsm_dev import DevHSM
from src.infrastructure.stubs.keeper_key_registry_stub import KeeperKeyRegistryStub


@pytest.fixture
def keeper_key_registry() -> KeeperKeyRegistryStub:
    """Create Keeper key registry stub."""
    return KeeperKeyRegistryStub(with_dev_key=False)


@pytest.fixture
def dev_hsm() -> DevHSM:
    """Create development HSM for signing."""
    return DevHSM()


@pytest.fixture
def sample_override_payload() -> OverrideEventPayload:
    """Create sample override payload for testing."""
    return OverrideEventPayload(
        keeper_id="KEEPER:alice",
        scope="system.monitoring",
        duration=86400,  # 24 hours
        reason="Scheduled maintenance window",
        action_type=ActionType.CONFIG_CHANGE,
        initiated_at=datetime.now(timezone.utc),
    )


class TestOverrideWithValidKeeperSignatureSucceeds:
    """AC1: Override includes cryptographic signature verified against registry."""

    @pytest.mark.asyncio
    async def test_override_with_valid_keeper_signature_succeeds(
        self,
        keeper_key_registry: KeeperKeyRegistryStub,
        dev_hsm: DevHSM,
        sample_override_payload: OverrideEventPayload,
    ) -> None:
        """Override with valid Keeper signature is accepted."""
        # Setup: Register a Keeper key
        key_id = await dev_hsm.generate_key_pair()
        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            key_id=key_id,
            public_key=b"x" * 32,  # Placeholder - DevHSM handles keys internally
            active_from=datetime.now(timezone.utc) - timedelta(days=1),
            active_until=None,
        )
        await keeper_key_registry.register_key(keeper_key)

        # Create signature service
        signature_service = KeeperSignatureService(
            hsm=dev_hsm,
            key_registry=keeper_key_registry,
        )

        # Sign the override
        signed_override = await signature_service.sign_override(
            override_payload=sample_override_payload,
            keeper_id="KEEPER:alice",
        )

        # Verify signature is present
        assert signed_override.signature is not None
        assert signed_override.signing_key_id == key_id
        assert signed_override.signed_at is not None

        # Verify signature is valid
        is_valid = await signature_service.verify_override_signature(signed_override)
        assert is_valid is True


class TestOverrideWithInvalidSignatureRejected:
    """AC2: Invalid signature rejected, logged with FR68 error."""

    @pytest.mark.asyncio
    async def test_override_with_invalid_signature_rejected(
        self,
        keeper_key_registry: KeeperKeyRegistryStub,
        dev_hsm: DevHSM,
        sample_override_payload: OverrideEventPayload,
    ) -> None:
        """Override with tampered signature is rejected."""
        # Setup: Register a Keeper key
        key_id = await dev_hsm.generate_key_pair()
        keeper_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            key_id=key_id,
            public_key=b"x" * 32,
            active_from=datetime.now(timezone.utc) - timedelta(days=1),
            active_until=None,
        )
        await keeper_key_registry.register_key(keeper_key)

        # Create signature service
        signature_service = KeeperSignatureService(
            hsm=dev_hsm,
            key_registry=keeper_key_registry,
        )

        # Create signed override with tampered signature
        signed_override = KeeperSignedOverride(
            override_payload=sample_override_payload,
            signature=base64.b64encode(b"tampered_invalid_signature").decode(),
            signing_key_id=key_id,
            signed_at=datetime.now(timezone.utc),
        )

        # Verify signature returns False
        is_valid = await signature_service.verify_override_signature(signed_override)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_override_rejection_logged_with_fr68_error(
        self,
        keeper_key_registry: KeeperKeyRegistryStub,
        dev_hsm: DevHSM,
        sample_override_payload: OverrideEventPayload,
    ) -> None:
        """Invalid signature raises error with FR68 message."""
        # Create signature service
        signature_service = KeeperSignatureService(
            hsm=dev_hsm,
            key_registry=keeper_key_registry,
        )

        # Try to verify with nonexistent key - should raise FR68 error
        signed_override = KeeperSignedOverride(
            override_payload=sample_override_payload,
            signature=base64.b64encode(b"signature").decode(),
            signing_key_id="nonexistent-key-id",
            signed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(
            InvalidKeeperSignatureError,
            match="FR68.*Invalid Keeper signature",
        ):
            await signature_service.verify_override_signature(signed_override)


class TestKeeperKeyRegistryReturnsActiveKey:
    """AC3: Registry returns active key for Keeper."""

    @pytest.mark.asyncio
    async def test_keeper_key_registry_returns_active_key(
        self,
        keeper_key_registry: KeeperKeyRegistryStub,
    ) -> None:
        """Registry returns currently active key for Keeper."""
        # Register an active key
        active_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:bob",
            key_id="bob-key-active",
            public_key=b"a" * 32,
            active_from=datetime.now(timezone.utc) - timedelta(days=10),
            active_until=None,  # No expiry
        )
        await keeper_key_registry.register_key(active_key)

        # Query active key
        result = await keeper_key_registry.get_active_key_for_keeper("KEEPER:bob")

        assert result is not None
        assert result.keeper_id == "KEEPER:bob"
        assert result.key_id == "bob-key-active"
        assert result.is_currently_active()


class TestKeeperKeyRegistryPreservesHistoricalKeys:
    """AC3: Historical keys preserved (FR76)."""

    @pytest.mark.asyncio
    async def test_keeper_key_registry_preserves_historical_keys(
        self,
        keeper_key_registry: KeeperKeyRegistryStub,
    ) -> None:
        """Registry preserves old keys after rotation (FR76)."""
        # Register old key (now expired)
        old_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:charlie",
            key_id="charlie-key-old",
            public_key=b"b" * 32,
            active_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            active_until=datetime(2024, 12, 31, tzinfo=timezone.utc),
        )
        await keeper_key_registry.register_key(old_key)

        # Register new key (currently active)
        new_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:charlie",
            key_id="charlie-key-new",
            public_key=b"c" * 32,
            active_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            active_until=None,
        )
        await keeper_key_registry.register_key(new_key)

        # Query all keys
        all_keys = await keeper_key_registry.get_all_keys_for_keeper("KEEPER:charlie")

        # Both keys should be preserved
        assert len(all_keys) == 2
        key_ids = {k.key_id for k in all_keys}
        assert "charlie-key-old" in key_ids
        assert "charlie-key-new" in key_ids


class TestSignatureVerificationUsesCorrectKeyAtTime:
    """Test temporal key lookup for signature verification."""

    @pytest.mark.asyncio
    async def test_signature_verification_uses_correct_key_at_time(
        self,
        keeper_key_registry: KeeperKeyRegistryStub,
    ) -> None:
        """Verification uses key that was active at signing time."""
        # Register key active only in a specific period
        jan_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:dave",
            key_id="dave-key-jan",
            public_key=b"d" * 32,
            active_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            active_until=datetime(2025, 6, 30, tzinfo=timezone.utc),
        )
        await keeper_key_registry.register_key(jan_key)

        # Query for time within validity period
        march_time = datetime(2025, 3, 15, tzinfo=timezone.utc)
        result = await keeper_key_registry.get_active_key_for_keeper(
            "KEEPER:dave", at_time=march_time
        )

        assert result is not None
        assert result.key_id == "dave-key-jan"

        # Query for time after expiry
        aug_time = datetime(2025, 8, 15, tzinfo=timezone.utc)
        result = await keeper_key_registry.get_active_key_for_keeper(
            "KEEPER:dave", at_time=aug_time
        )

        assert result is None


class TestExpiredKeyCannotSignNewOverrides:
    """Test that expired keys cannot be used for new signatures."""

    @pytest.mark.asyncio
    async def test_expired_key_cannot_sign_new_overrides(
        self,
        keeper_key_registry: KeeperKeyRegistryStub,
        dev_hsm: DevHSM,
        sample_override_payload: OverrideEventPayload,
    ) -> None:
        """Keeper with only expired key cannot sign new overrides."""
        # Register only an expired key
        expired_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:expired-keeper",
            key_id="expired-key-001",
            public_key=b"e" * 32,
            active_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            active_until=datetime(2024, 12, 31, tzinfo=timezone.utc),  # Expired
        )
        await keeper_key_registry.register_key(expired_key)

        # Create signature service
        signature_service = KeeperSignatureService(
            hsm=dev_hsm,
            key_registry=keeper_key_registry,
        )

        # Update payload with the expired keeper
        payload = OverrideEventPayload(
            keeper_id="KEEPER:expired-keeper",
            scope="test.scope",
            duration=3600,
            reason="Test reason",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        # Attempt to sign should fail
        with pytest.raises(
            KeeperKeyNotFoundError,
            match="FR68.*No active key found",
        ):
            await signature_service.sign_override(
                override_payload=payload,
                keeper_id="KEEPER:expired-keeper",
            )


class TestKeeperKeyRegistryFieldsExposed:
    """AC3: Registry shows keeper_id, public_key, active_from, active_until."""

    @pytest.mark.asyncio
    async def test_keeper_key_registry_exposes_required_fields(
        self,
        keeper_key_registry: KeeperKeyRegistryStub,
    ) -> None:
        """Registered keys expose all required fields (AC3)."""
        now = datetime.now(timezone.utc)
        active_from = now - timedelta(days=7)
        active_until = now + timedelta(days=7)

        key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:frank",
            key_id="frank-key-001",
            public_key=b"f" * 32,
            active_from=active_from,
            active_until=active_until,
        )
        await keeper_key_registry.register_key(key)

        result = await keeper_key_registry.get_key_by_id("frank-key-001")

        assert result is not None
        # AC3: Must show keeper_id
        assert result.keeper_id == "KEEPER:frank"
        # AC3: Must show public_key
        assert result.public_key == b"f" * 32
        # AC3: Must show active_from
        assert result.active_from == active_from
        # AC3: Must show active_until
        assert result.active_until == active_until


class TestKeeperIdPrefixConstant:
    """Test KEEPER_ID_PREFIX constant."""

    def test_keeper_id_prefix_is_correct(self) -> None:
        """KEEPER_ID_PREFIX is 'KEEPER:'."""
        assert KEEPER_ID_PREFIX == "KEEPER:"
