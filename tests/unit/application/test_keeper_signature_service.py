"""Unit tests for KeeperSignatureService (FR68-FR70).

Tests the Keeper signature service for signing and verification operations.
Validates constitutional constraint compliance.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.hsm import HSMMode, SignatureResult
from src.application.services.keeper_signature_service import (
    KeeperSignatureService,
    KeeperSignedOverride,
)
from src.domain.errors.keeper_signature import (
    InvalidKeeperSignatureError,
    KeeperKeyNotFoundError,
)
from src.domain.events.override_event import ActionType, OverrideEventPayload
from src.domain.models.keeper_key import KeeperKey


@pytest.fixture
def mock_hsm() -> AsyncMock:
    """Create mock HSM protocol."""
    hsm = AsyncMock()
    hsm.sign = AsyncMock(
        return_value=SignatureResult(
            content=b"signed_content",
            signature=b"mock_signature_32_bytes_long!!!!",
            mode=HSMMode.DEVELOPMENT,
            key_id="mock-key-id",
        )
    )
    hsm.verify_with_key = AsyncMock(return_value=True)
    hsm.get_mode = AsyncMock(return_value=HSMMode.DEVELOPMENT)
    return hsm


@pytest.fixture
def mock_key_registry() -> AsyncMock:
    """Create mock key registry."""
    return AsyncMock()


@pytest.fixture
def sample_override_payload() -> OverrideEventPayload:
    """Create sample override payload."""
    return OverrideEventPayload(
        keeper_id="KEEPER:alice",
        scope="system.monitoring",
        duration=86400,  # 24 hours in seconds
        reason="Scheduled maintenance",
        action_type=ActionType.CONFIG_CHANGE,
        initiated_at=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_keeper_key() -> KeeperKey:
    """Create sample keeper key."""
    return KeeperKey(
        id=uuid4(),
        keeper_id="KEEPER:alice",
        key_id="keeper-key-001",
        public_key=b"x" * 32,
        active_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
        active_until=None,
    )


class TestKeeperSignatureServiceSignOverride:
    """Tests for sign_override method."""

    @pytest.mark.asyncio
    async def test_sign_override_creates_valid_signature(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
        sample_override_payload: OverrideEventPayload,
        sample_keeper_key: KeeperKey,
    ) -> None:
        """sign_override creates a valid KeeperSignedOverride."""
        mock_key_registry.get_active_key_for_keeper = AsyncMock(
            return_value=sample_keeper_key
        )

        service = KeeperSignatureService(
            hsm=mock_hsm,
            key_registry=mock_key_registry,
        )

        result = await service.sign_override(
            override_payload=sample_override_payload,
            keeper_id="KEEPER:alice",
        )

        assert isinstance(result, KeeperSignedOverride)
        assert result.override_payload == sample_override_payload
        assert result.signing_key_id == "mock-key-id"
        assert result.signature is not None
        assert result.signed_at is not None

    @pytest.mark.asyncio
    async def test_sign_override_calls_hsm_sign(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
        sample_override_payload: OverrideEventPayload,
        sample_keeper_key: KeeperKey,
    ) -> None:
        """sign_override calls HSM.sign with signable content."""
        mock_key_registry.get_active_key_for_keeper = AsyncMock(
            return_value=sample_keeper_key
        )

        service = KeeperSignatureService(
            hsm=mock_hsm,
            key_registry=mock_key_registry,
        )

        await service.sign_override(
            override_payload=sample_override_payload,
            keeper_id="KEEPER:alice",
        )

        mock_hsm.sign.assert_called_once()
        # Verify signable content is bytes
        call_args = mock_hsm.sign.call_args[0][0]
        assert isinstance(call_args, bytes)

    @pytest.mark.asyncio
    async def test_sign_override_fails_if_no_active_key(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
        sample_override_payload: OverrideEventPayload,
    ) -> None:
        """sign_override raises KeeperKeyNotFoundError if no active key."""
        mock_key_registry.get_active_key_for_keeper = AsyncMock(return_value=None)

        service = KeeperSignatureService(
            hsm=mock_hsm,
            key_registry=mock_key_registry,
        )

        with pytest.raises(
            KeeperKeyNotFoundError,
            match="FR68.*No active key found",
        ):
            await service.sign_override(
                override_payload=sample_override_payload,
                keeper_id="KEEPER:unknown",
            )

    @pytest.mark.asyncio
    async def test_sign_override_encodes_signature_as_base64(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
        sample_override_payload: OverrideEventPayload,
        sample_keeper_key: KeeperKey,
    ) -> None:
        """sign_override returns base64-encoded signature."""
        mock_key_registry.get_active_key_for_keeper = AsyncMock(
            return_value=sample_keeper_key
        )

        service = KeeperSignatureService(
            hsm=mock_hsm,
            key_registry=mock_key_registry,
        )

        result = await service.sign_override(
            override_payload=sample_override_payload,
            keeper_id="KEEPER:alice",
        )

        # Verify signature is valid base64
        decoded = base64.b64decode(result.signature)
        assert decoded == b"mock_signature_32_bytes_long!!!!"


class TestKeeperSignatureServiceVerifySignature:
    """Tests for verify_override_signature method."""

    @pytest.mark.asyncio
    async def test_verify_override_signature_validates_correct_signature(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
        sample_override_payload: OverrideEventPayload,
        sample_keeper_key: KeeperKey,
    ) -> None:
        """verify_override_signature returns True for valid signature."""
        mock_key_registry.get_key_by_id = AsyncMock(return_value=sample_keeper_key)
        mock_hsm.verify_with_key = AsyncMock(return_value=True)

        service = KeeperSignatureService(
            hsm=mock_hsm,
            key_registry=mock_key_registry,
        )

        signed_override = KeeperSignedOverride(
            override_payload=sample_override_payload,
            signature=base64.b64encode(b"valid_signature").decode(),
            signing_key_id="keeper-key-001",
            signed_at=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        )

        result = await service.verify_override_signature(signed_override)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_override_signature_rejects_invalid_signature(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
        sample_override_payload: OverrideEventPayload,
        sample_keeper_key: KeeperKey,
    ) -> None:
        """verify_override_signature returns False for invalid signature."""
        mock_key_registry.get_key_by_id = AsyncMock(return_value=sample_keeper_key)
        mock_hsm.verify_with_key = AsyncMock(return_value=False)

        service = KeeperSignatureService(
            hsm=mock_hsm,
            key_registry=mock_key_registry,
        )

        signed_override = KeeperSignedOverride(
            override_payload=sample_override_payload,
            signature=base64.b64encode(b"invalid_signature").decode(),
            signing_key_id="keeper-key-001",
            signed_at=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        )

        result = await service.verify_override_signature(signed_override)
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_override_signature_fails_if_key_not_found(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
        sample_override_payload: OverrideEventPayload,
    ) -> None:
        """verify_override_signature raises InvalidKeeperSignatureError if key not found."""
        mock_key_registry.get_key_by_id = AsyncMock(return_value=None)

        service = KeeperSignatureService(
            hsm=mock_hsm,
            key_registry=mock_key_registry,
        )

        signed_override = KeeperSignedOverride(
            override_payload=sample_override_payload,
            signature=base64.b64encode(b"signature").decode(),
            signing_key_id="nonexistent-key",
            signed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(
            InvalidKeeperSignatureError,
            match="FR68.*signing key not found",
        ):
            await service.verify_override_signature(signed_override)

    @pytest.mark.asyncio
    async def test_verify_override_signature_fails_if_key_not_active_at_signing_time(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
        sample_override_payload: OverrideEventPayload,
    ) -> None:
        """verify_override_signature fails if key was not active when signed."""
        # Key that was active only in 2024
        expired_key = KeeperKey(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            key_id="old-key",
            public_key=b"y" * 32,
            active_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            active_until=datetime(2024, 12, 31, tzinfo=timezone.utc),
        )
        mock_key_registry.get_key_by_id = AsyncMock(return_value=expired_key)

        service = KeeperSignatureService(
            hsm=mock_hsm,
            key_registry=mock_key_registry,
        )

        signed_override = KeeperSignedOverride(
            override_payload=sample_override_payload,
            signature=base64.b64encode(b"signature").decode(),
            signing_key_id="old-key",
            signed_at=datetime(2025, 6, 15, tzinfo=timezone.utc),  # After key expired
        )

        with pytest.raises(
            InvalidKeeperSignatureError,
            match="FR68.*key was not active at signing time",
        ):
            await service.verify_override_signature(signed_override)

    @pytest.mark.asyncio
    async def test_verify_override_signature_calls_hsm_verify_with_key(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
        sample_override_payload: OverrideEventPayload,
        sample_keeper_key: KeeperKey,
    ) -> None:
        """verify_override_signature calls HSM.verify_with_key correctly."""
        mock_key_registry.get_key_by_id = AsyncMock(return_value=sample_keeper_key)
        mock_hsm.verify_with_key = AsyncMock(return_value=True)

        service = KeeperSignatureService(
            hsm=mock_hsm,
            key_registry=mock_key_registry,
        )

        signed_override = KeeperSignedOverride(
            override_payload=sample_override_payload,
            signature=base64.b64encode(b"signature").decode(),
            signing_key_id="keeper-key-001",
            signed_at=datetime(2025, 6, 15, tzinfo=timezone.utc),
        )

        await service.verify_override_signature(signed_override)

        mock_hsm.verify_with_key.assert_called_once()
        call_args = mock_hsm.verify_with_key.call_args
        # Verify it was called with (signable_content, signature, key_id)
        assert call_args[0][2] == "keeper-key-001"


class TestKeeperSignatureServiceSignableContent:
    """Tests for signable content creation."""

    @pytest.mark.asyncio
    async def test_signable_content_is_deterministic(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
        sample_keeper_key: KeeperKey,
    ) -> None:
        """Signable content is deterministic for same payload."""
        mock_key_registry.get_active_key_for_keeper = AsyncMock(
            return_value=sample_keeper_key
        )

        service = KeeperSignatureService(
            hsm=mock_hsm,
            key_registry=mock_key_registry,
        )

        payload1 = OverrideEventPayload(
            keeper_id="KEEPER:test",
            scope="test.scope",
            duration=3600,  # 1 hour in seconds
            reason="Test reason",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        payload2 = OverrideEventPayload(
            keeper_id="KEEPER:test",
            scope="test.scope",
            duration=3600,  # 1 hour in seconds
            reason="Test reason",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        content1 = service._create_signable_content(payload1)
        content2 = service._create_signable_content(payload2)

        assert content1 == content2

    @pytest.mark.asyncio
    async def test_signable_content_differs_for_different_payloads(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
        sample_keeper_key: KeeperKey,
    ) -> None:
        """Signable content differs for different payloads."""
        mock_key_registry.get_active_key_for_keeper = AsyncMock(
            return_value=sample_keeper_key
        )

        service = KeeperSignatureService(
            hsm=mock_hsm,
            key_registry=mock_key_registry,
        )

        payload1 = OverrideEventPayload(
            keeper_id="KEEPER:alice",
            scope="scope.a",
            duration=3600,  # 1 hour in seconds
            reason="Reason A",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        payload2 = OverrideEventPayload(
            keeper_id="KEEPER:bob",  # Different keeper
            scope="scope.a",
            duration=3600,  # 1 hour in seconds
            reason="Reason A",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        content1 = service._create_signable_content(payload1)
        content2 = service._create_signable_content(payload2)

        assert content1 != content2


class TestKeeperSignedOverrideDataclass:
    """Tests for KeeperSignedOverride dataclass."""

    def test_keeper_signed_override_is_frozen(
        self,
        sample_override_payload: OverrideEventPayload,
    ) -> None:
        """KeeperSignedOverride is immutable."""
        signed = KeeperSignedOverride(
            override_payload=sample_override_payload,
            signature="sig",
            signing_key_id="key-001",
            signed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            signed.signature = "new_sig"  # type: ignore[misc]

    def test_keeper_signed_override_fields(
        self,
        sample_override_payload: OverrideEventPayload,
    ) -> None:
        """KeeperSignedOverride has all expected fields."""
        now = datetime.now(timezone.utc)
        signed = KeeperSignedOverride(
            override_payload=sample_override_payload,
            signature="sig",
            signing_key_id="key-001",
            signed_at=now,
        )

        assert signed.override_payload == sample_override_payload
        assert signed.signature == "sig"
        assert signed.signing_key_id == "key-001"
        assert signed.signed_at == now
