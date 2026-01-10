"""Unit tests for SigningService application service (FR74, FP-5).

Tests the centralized signing service that orchestrates event signing
using the HSM protocol.

Constitutional Constraints:
- FR74: Invalid agent signatures must be rejected
- FP-5: Centralized signing service pattern
- MA-2: Signature must cover prev_hash (chain binding)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.application.ports.hsm import HSMMode, SignatureResult


class MockHSM:
    """Mock HSM for testing."""

    def __init__(self) -> None:
        self.sign = AsyncMock()
        self.verify = AsyncMock(return_value=True)
        self.verify_with_key = AsyncMock(return_value=True)
        self.get_current_key_id = AsyncMock(return_value="dev-test123")
        self.get_mode = AsyncMock(return_value=HSMMode.DEVELOPMENT)


class MockKeyRegistry:
    """Mock key registry for testing."""

    def __init__(self) -> None:
        self.get_key_by_id = AsyncMock(return_value=None)
        self.key_exists = AsyncMock(return_value=True)


@pytest.fixture
def mock_hsm() -> MockHSM:
    """Create a mock HSM."""
    hsm = MockHSM()
    hsm.sign.return_value = SignatureResult(
        content=b"[DEV MODE]test content",
        signature=b"x" * 64,  # Ed25519 signature
        mode=HSMMode.DEVELOPMENT,
        key_id="dev-test123",
    )
    return hsm


@pytest.fixture
def mock_key_registry() -> MockKeyRegistry:
    """Create a mock key registry."""
    return MockKeyRegistry()


class TestSigningServiceCreation:
    """Tests for SigningService instantiation."""

    def test_creates_with_hsm_and_registry(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """SigningService should accept HSM and key registry."""
        from src.application.services.signing_service import SigningService

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        assert service is not None


class TestSignEventMethod:
    """Tests for sign_event method."""

    @pytest.mark.asyncio
    async def test_sign_event_returns_tuple(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """sign_event should return (signature, key_id, sig_alg_version)."""
        from src.application.services.signing_service import SigningService

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        result = await service.sign_event(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
        )

        assert isinstance(result, tuple)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_sign_event_returns_base64_signature(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """Signature should be base64 encoded."""
        import base64

        from src.application.services.signing_service import SigningService

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        signature_b64, _, _ = await service.sign_event(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
        )

        # Should not raise - valid base64
        base64.b64decode(signature_b64)

    @pytest.mark.asyncio
    async def test_sign_event_returns_key_id(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """sign_event should return the signing key ID."""
        from src.application.services.signing_service import SigningService

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        _, key_id, _ = await service.sign_event(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
        )

        assert key_id == "dev-test123"

    @pytest.mark.asyncio
    async def test_sign_event_returns_sig_alg_version(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """sign_event should return signature algorithm version."""
        from src.application.services.signing_service import SigningService

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        _, _, sig_alg_version = await service.sign_event(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
        )

        assert sig_alg_version == 1  # Ed25519

    @pytest.mark.asyncio
    async def test_sign_event_calls_hsm_sign(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """sign_event should call HSM sign method."""
        from src.application.services.signing_service import SigningService

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        await service.sign_event(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
        )

        mock_hsm.sign.assert_called_once()

    @pytest.mark.asyncio
    async def test_sign_event_signable_content_includes_prev_hash(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """MA-2: Signable content must include prev_hash for chain binding."""
        from src.application.services.signing_service import SigningService

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        await service.sign_event(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
        )

        # Get the bytes that were signed
        call_args = mock_hsm.sign.call_args
        signed_content = call_args[0][0]

        # prev_hash should be in the signed content
        assert b"prev456" in signed_content

    @pytest.mark.asyncio
    async def test_sign_event_signable_content_includes_agent_id(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """Signable content should include agent_id."""
        from src.application.services.signing_service import SigningService

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        await service.sign_event(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
        )

        call_args = mock_hsm.sign.call_args
        signed_content = call_args[0][0]

        assert b"agent-001" in signed_content

    @pytest.mark.asyncio
    async def test_sign_event_handles_system_agent(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """sign_event should handle system agent ID format."""
        from src.application.services.signing_service import SigningService

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        await service.sign_event(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="SYSTEM:WATCHDOG",
        )

        call_args = mock_hsm.sign.call_args
        signed_content = call_args[0][0]

        assert b"SYSTEM:WATCHDOG" in signed_content


class TestVerifyEventSignatureMethod:
    """Tests for verify_event_signature method."""

    @pytest.mark.asyncio
    async def test_verify_returns_bool(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """verify_event_signature should return a boolean."""
        from src.application.services.signing_service import SigningService

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        result = await service.verify_event_signature(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
            signature_b64="eA==" * 21 + "eA==",  # ~88 chars base64
            signing_key_id="dev-test123",
        )

        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_verify_calls_hsm_verify_with_key(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """verify_event_signature should call HSM verify_with_key."""
        from src.application.services.signing_service import SigningService

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        await service.verify_event_signature(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
            signature_b64="eA==" * 21 + "eA==",
            signing_key_id="dev-test123",
        )

        mock_hsm.verify_with_key.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_returns_false_for_invalid_signature(
        self, mock_hsm: MockHSM, mock_key_registry: MockKeyRegistry
    ) -> None:
        """verify_event_signature should return False for invalid signatures."""
        from src.application.services.signing_service import SigningService

        mock_hsm.verify_with_key.return_value = False

        service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)

        result = await service.verify_event_signature(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-001",
            signature_b64="eA==" * 21 + "eA==",
            signing_key_id="dev-test123",
        )

        assert result is False
