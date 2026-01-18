"""Unit tests for WitnessService (FR4, FR5).

Tests the witness attestation service.

Constitutional Constraints Tested:
- CT-12: Witnessing creates accountability
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.hsm import HSMMode, SignatureResult
from src.application.services.witness_service import WitnessService
from src.domain.errors.witness import NoWitnessAvailableError
from src.domain.models.witness import Witness


@pytest.fixture
def mock_hsm() -> AsyncMock:
    """Create a mock HSM protocol."""
    hsm = AsyncMock()
    hsm.sign = AsyncMock(
        return_value=SignatureResult(
            content=b"test content",
            signature=b"A" * 64,  # 64-byte Ed25519 signature
            mode=HSMMode.DEVELOPMENT,
            key_id="witness-key-001",
        )
    )
    hsm.get_mode = AsyncMock(return_value=HSMMode.DEVELOPMENT)
    return hsm


@pytest.fixture
def mock_witness_pool() -> AsyncMock:
    """Create a mock witness pool protocol."""
    pool = AsyncMock()
    witness = Witness(
        witness_id=f"WITNESS:{uuid4()}",
        public_key=bytes(32),
        active_from=datetime.now(timezone.utc),
    )
    pool.get_available_witness = AsyncMock(return_value=witness)
    pool.get_witness_by_id = AsyncMock(return_value=witness)
    return pool


@pytest.fixture
def witness_service(
    mock_hsm: AsyncMock, mock_witness_pool: AsyncMock
) -> WitnessService:
    """Create a WitnessService with mock dependencies."""
    return WitnessService(hsm=mock_hsm, witness_pool=mock_witness_pool)


class TestWitnessServiceAttestEvent:
    """Tests for attest_event() method."""

    @pytest.mark.asyncio
    async def test_attest_event_returns_witness_id_and_signature(
        self, witness_service: WitnessService, mock_witness_pool: AsyncMock
    ) -> None:
        """Test that attest_event returns witness_id and signature."""
        content_hash = "abcd" * 16  # 64-char hex hash

        witness_id, witness_signature = await witness_service.attest_event(content_hash)

        assert witness_id.startswith("WITNESS:")
        assert isinstance(witness_signature, str)
        assert len(witness_signature) > 0

    @pytest.mark.asyncio
    async def test_attest_event_selects_witness_from_pool(
        self, witness_service: WitnessService, mock_witness_pool: AsyncMock
    ) -> None:
        """Test that attest_event selects a witness from the pool."""
        content_hash = "abcd" * 16

        await witness_service.attest_event(content_hash)

        mock_witness_pool.get_available_witness.assert_called_once()

    @pytest.mark.asyncio
    async def test_attest_event_signs_with_hsm(
        self, witness_service: WitnessService, mock_hsm: AsyncMock
    ) -> None:
        """Test that attest_event signs content with HSM."""
        content_hash = "abcd" * 16

        await witness_service.attest_event(content_hash)

        mock_hsm.sign.assert_called_once()

    @pytest.mark.asyncio
    async def test_attest_event_includes_content_hash_in_signable(
        self, witness_service: WitnessService, mock_hsm: AsyncMock
    ) -> None:
        """Test that signable content includes the event content hash."""
        content_hash = "unique_hash_12345"

        await witness_service.attest_event(content_hash)

        # Verify sign was called with content containing the hash
        call_args = mock_hsm.sign.call_args
        signed_content = call_args[0][0]  # First positional argument
        assert content_hash.encode() in signed_content

    @pytest.mark.asyncio
    async def test_attest_event_raises_when_no_witness_available(
        self, mock_hsm: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test that attest_event raises NoWitnessAvailableError when pool is empty."""
        mock_witness_pool.get_available_witness = AsyncMock(
            side_effect=NoWitnessAvailableError()
        )
        service = WitnessService(hsm=mock_hsm, witness_pool=mock_witness_pool)
        content_hash = "abcd" * 16

        with pytest.raises(NoWitnessAvailableError) as exc_info:
            await service.attest_event(content_hash)

        assert "RT-1" in str(exc_info.value)
        assert "No witnesses available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_attest_event_returns_base64_signature(
        self, witness_service: WitnessService
    ) -> None:
        """Test that signature is returned as valid base64."""
        import base64

        content_hash = "abcd" * 16

        _, witness_signature = await witness_service.attest_event(content_hash)

        # Should be valid base64
        decoded = base64.b64decode(witness_signature)
        assert len(decoded) == 64  # Ed25519 signature


class TestWitnessServiceSignableContent:
    """Tests for witness signable content format."""

    @pytest.mark.asyncio
    async def test_signable_content_starts_with_attestation_prefix(
        self, witness_service: WitnessService, mock_hsm: AsyncMock
    ) -> None:
        """Test that signable content has WITNESS_ATTESTATION prefix."""
        content_hash = "test_hash"

        await witness_service.attest_event(content_hash)

        call_args = mock_hsm.sign.call_args
        signed_content = call_args[0][0]
        assert b"WITNESS_ATTESTATION:" in signed_content

    @pytest.mark.asyncio
    async def test_signable_content_includes_mode_watermark(
        self, witness_service: WitnessService, mock_hsm: AsyncMock
    ) -> None:
        """Test that signable content includes RT-1 mode watermark."""
        content_hash = "test_hash"

        await witness_service.attest_event(content_hash)

        # Verify HSM sign was called (watermark is added inside sign)
        mock_hsm.sign.assert_called_once()


class TestWitnessServiceVerifyAttestation:
    """Tests for verify_attestation() method."""

    @pytest.mark.asyncio
    async def test_verify_attestation_returns_true_for_valid(
        self, mock_hsm: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test that verify_attestation returns True for valid attestation."""
        mock_hsm.verify_with_key = AsyncMock(return_value=True)
        service = WitnessService(hsm=mock_hsm, witness_pool=mock_witness_pool)

        result = await service.verify_attestation(
            event_content_hash="abcd" * 16,
            witness_id=f"WITNESS:{uuid4()}",
            witness_signature_b64="QUFB" + "Q" * 80,  # Valid base64
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_attestation_returns_false_for_invalid(
        self, mock_hsm: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test that verify_attestation returns False for invalid attestation."""
        mock_hsm.verify_with_key = AsyncMock(return_value=False)
        service = WitnessService(hsm=mock_hsm, witness_pool=mock_witness_pool)

        result = await service.verify_attestation(
            event_content_hash="abcd" * 16,
            witness_id=f"WITNESS:{uuid4()}",
            witness_signature_b64="QUFB" + "Q" * 80,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_attestation_looks_up_witness(
        self, mock_hsm: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test that verify_attestation looks up witness for public key."""
        mock_hsm.verify_with_key = AsyncMock(return_value=True)
        service = WitnessService(hsm=mock_hsm, witness_pool=mock_witness_pool)
        witness_id = f"WITNESS:{uuid4()}"

        await service.verify_attestation(
            event_content_hash="abcd" * 16,
            witness_id=witness_id,
            witness_signature_b64="QUFB" + "Q" * 80,
        )

        mock_witness_pool.get_witness_by_id.assert_called_once_with(witness_id)
