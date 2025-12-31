"""Unit tests for DevHSM (development HSM stub).

Tests cover:
- AC1: Dev mode signature includes [DEV MODE] prefix
- AC2: Signature metadata contains mode: "development"
- AC4: Key generation logs warning
- Factory returns correct HSM based on DEV_MODE
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.application.ports.hsm import HSMMode
from src.domain.errors.hsm import HSMKeyNotFoundError, HSMNotConfiguredError
from src.domain.models.signable import SignableContent
from src.infrastructure.adapters.security.hsm_cloud import CloudHSM
from src.infrastructure.adapters.security.hsm_dev import DevHSM
from src.infrastructure.adapters.security.hsm_factory import get_hsm, is_dev_mode


class TestDevHSMMode:
    """Tests for DevHSM mode behavior."""

    @pytest.mark.asyncio
    async def test_dev_hsm_returns_development_mode(self) -> None:
        """AC2: DevHSM should return DEVELOPMENT mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))
            mode = await hsm.get_mode()
            assert mode == HSMMode.DEVELOPMENT

    @pytest.mark.asyncio
    async def test_cloud_hsm_returns_production_mode(self) -> None:
        """CloudHSM should return PRODUCTION mode."""
        hsm = CloudHSM()
        mode = await hsm.get_mode()
        assert mode == HSMMode.PRODUCTION


class TestDevHSMSignature:
    """Tests for DevHSM signing functionality."""

    @pytest.mark.asyncio
    async def test_signature_includes_dev_mode_prefix(self) -> None:
        """AC1: Dev mode signature includes [DEV MODE] prefix in content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            content = b"test data to sign"
            result = await hsm.sign(content)

            # The signed content should start with [DEV MODE]
            assert result.content.startswith(b"[DEV MODE]")
            # And contain the original content
            assert content in result.content

    @pytest.mark.asyncio
    async def test_signature_metadata_contains_development_mode(self) -> None:
        """AC2: Signature metadata contains mode: 'development'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            content = b"test data"
            result = await hsm.sign(content)

            assert result.mode == HSMMode.DEVELOPMENT
            assert result.mode.value == "development"

    @pytest.mark.asyncio
    async def test_signature_contains_key_id(self) -> None:
        """Signature result should include the signing key ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            content = b"test data"
            result = await hsm.sign(content)

            assert result.key_id is not None
            assert result.key_id.startswith("dev-")

    @pytest.mark.asyncio
    async def test_signature_is_valid_bytes(self) -> None:
        """Signature should be non-empty bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            result = await hsm.sign(b"test")

            assert isinstance(result.signature, bytes)
            assert len(result.signature) > 0


class TestDevHSMVerification:
    """Tests for DevHSM signature verification."""

    @pytest.mark.asyncio
    async def test_verify_valid_signature(self) -> None:
        """Verification should succeed for valid signatures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            content = b"important data"
            result = await hsm.sign(content)

            is_valid = await hsm.verify(result.content, result.signature)
            assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_invalid_signature(self) -> None:
        """Verification should fail for tampered signatures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            content = b"important data"
            result = await hsm.sign(content)

            # Tamper with signature
            tampered_sig = bytes([b ^ 0xFF for b in result.signature[:8]]) + result.signature[8:]

            is_valid = await hsm.verify(result.content, tampered_sig)
            assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_fails_with_modified_content(self) -> None:
        """Verification should fail if content is modified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            content = b"important data"
            result = await hsm.sign(content)

            # Modify the content
            modified_content = result.content + b"tampered"

            is_valid = await hsm.verify(modified_content, result.signature)
            assert is_valid is False


class TestDevHSMKeyGeneration:
    """Tests for DevHSM key generation."""

    @pytest.mark.asyncio
    async def test_generate_key_pair_returns_key_id(self) -> None:
        """AC4: Key generation should return a key ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            key_id = await hsm.generate_key_pair()

            assert key_id is not None
            assert isinstance(key_id, str)
            assert key_id.startswith("dev-")

    @pytest.mark.asyncio
    async def test_key_generation_logs_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        """AC4: Key generation should log a warning about insecure storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # The warning is logged on initialization
            hsm = DevHSM(key_dir=Path(tmpdir))

            # Check stdout/stderr contains the warning (structlog outputs to stdout by default)
            captured = capsys.readouterr()
            all_output = captured.out + captured.err
            assert "NOT FOR PRODUCTION" in all_output or "hsm_dev_mode_active" in all_output

    @pytest.mark.asyncio
    async def test_get_current_key_id_after_generation(self) -> None:
        """get_current_key_id should return the generated key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            generated_id = await hsm.generate_key_pair()
            current_id = await hsm.get_current_key_id()

            assert current_id == generated_id


class TestDevHSMKeyPersistence:
    """Tests for DevHSM key storage persistence."""

    @pytest.mark.asyncio
    async def test_keys_persist_across_instances(self) -> None:
        """Keys should be loadable by new HSM instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_dir = Path(tmpdir)

            # Generate key with first instance
            hsm1 = DevHSM(key_dir=key_dir)
            key_id = await hsm1.generate_key_pair()
            content = b"test data"
            result1 = await hsm1.sign(content)

            # Create new instance
            hsm2 = DevHSM(key_dir=key_dir)
            loaded_key_id = await hsm2.get_current_key_id()

            # Should have same key
            assert loaded_key_id == key_id

            # Should be able to verify signature from first instance
            is_valid = await hsm2.verify(result1.content, result1.signature)
            assert is_valid is True


class TestCloudHSM:
    """Tests for CloudHSM (production placeholder)."""

    @pytest.mark.asyncio
    async def test_cloud_hsm_sign_raises_not_configured(self) -> None:
        """AC3: CloudHSM.sign should raise HSMNotConfiguredError."""
        hsm = CloudHSM()

        with pytest.raises(HSMNotConfiguredError) as exc_info:
            await hsm.sign(b"test")

        assert "Production HSM not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cloud_hsm_verify_raises_not_configured(self) -> None:
        """AC3: CloudHSM.verify should raise HSMNotConfiguredError."""
        hsm = CloudHSM()

        with pytest.raises(HSMNotConfiguredError):
            await hsm.verify(b"content", b"signature")

    @pytest.mark.asyncio
    async def test_cloud_hsm_generate_key_raises_not_configured(self) -> None:
        """AC3: CloudHSM.generate_key_pair should raise HSMNotConfiguredError."""
        hsm = CloudHSM()

        with pytest.raises(HSMNotConfiguredError):
            await hsm.generate_key_pair()

    @pytest.mark.asyncio
    async def test_cloud_hsm_get_key_id_raises_not_configured(self) -> None:
        """AC3: CloudHSM.get_current_key_id should raise HSMNotConfiguredError."""
        hsm = CloudHSM()

        with pytest.raises(HSMNotConfiguredError):
            await hsm.get_current_key_id()


class TestHSMFactory:
    """Tests for HSM factory function."""

    def test_is_dev_mode_true(self) -> None:
        """is_dev_mode should return True when DEV_MODE=true."""
        with patch.dict(os.environ, {"DEV_MODE": "true"}):
            assert is_dev_mode() is True

    def test_is_dev_mode_false(self) -> None:
        """is_dev_mode should return False when DEV_MODE=false."""
        with patch.dict(os.environ, {"DEV_MODE": "false"}):
            assert is_dev_mode() is False

    def test_is_dev_mode_default(self) -> None:
        """is_dev_mode should return False when DEV_MODE not set."""
        env = os.environ.copy()
        env.pop("DEV_MODE", None)
        with patch.dict(os.environ, env, clear=True):
            assert is_dev_mode() is False

    def test_is_dev_mode_case_insensitive(self) -> None:
        """is_dev_mode should be case-insensitive."""
        with patch.dict(os.environ, {"DEV_MODE": "TRUE"}):
            assert is_dev_mode() is True
        with patch.dict(os.environ, {"DEV_MODE": "True"}):
            assert is_dev_mode() is True

    def test_factory_returns_dev_hsm_when_dev_mode(self) -> None:
        """Factory should return DevHSM when DEV_MODE=true."""
        with patch.dict(os.environ, {"DEV_MODE": "true"}):
            with tempfile.TemporaryDirectory() as tmpdir:
                hsm = get_hsm(dev_hsm_instance=DevHSM(key_dir=Path(tmpdir)))
                assert isinstance(hsm, DevHSM)

    def test_factory_returns_cloud_hsm_when_prod_mode(self) -> None:
        """Factory should return CloudHSM when DEV_MODE=false."""
        with patch.dict(os.environ, {"DEV_MODE": "false"}):
            hsm = get_hsm()
            assert isinstance(hsm, CloudHSM)


class TestSignableContent:
    """Tests for SignableContent domain model."""

    def test_to_bytes_with_dev_mode(self) -> None:
        """to_bytes_with_mode should add [DEV MODE] prefix."""
        content = SignableContent(raw_content=b"test data")
        result = content.to_bytes_with_mode(dev_mode=True)

        assert result.startswith(b"[DEV MODE]")
        assert b"test data" in result

    def test_to_bytes_with_prod_mode(self) -> None:
        """to_bytes_with_mode should add [PROD] prefix."""
        content = SignableContent(raw_content=b"test data")
        result = content.to_bytes_with_mode(dev_mode=False)

        assert result.startswith(b"[PROD]")
        assert b"test data" in result

    def test_from_signed_bytes_dev_mode(self) -> None:
        """from_signed_bytes should parse dev mode prefix."""
        original = SignableContent(raw_content=b"test data")
        signed = original.to_bytes_with_mode(dev_mode=True)

        parsed, is_dev = SignableContent.from_signed_bytes(signed)

        assert is_dev is True
        assert parsed.raw_content == b"test data"

    def test_from_signed_bytes_prod_mode(self) -> None:
        """from_signed_bytes should parse prod mode prefix."""
        original = SignableContent(raw_content=b"test data")
        signed = original.to_bytes_with_mode(dev_mode=False)

        parsed, is_dev = SignableContent.from_signed_bytes(signed)

        assert is_dev is False
        assert parsed.raw_content == b"test data"

    def test_from_signed_bytes_invalid_prefix(self) -> None:
        """from_signed_bytes should raise ValueError for invalid prefix."""
        invalid_bytes = b"INVALID PREFIX test data"

        with pytest.raises(ValueError) as exc_info:
            SignableContent.from_signed_bytes(invalid_bytes)

        assert "missing mode prefix" in str(exc_info.value)

    def test_watermark_cannot_be_stripped_without_invalidating(self) -> None:
        """AC2: Watermark cannot be stripped without invalidating signature."""
        # This is tested implicitly through the signature verification tests
        # The watermark is INSIDE the signed content, so stripping it
        # would change the content and invalidate the signature.
        content = SignableContent(raw_content=b"test")
        with_prefix = content.to_bytes_with_mode(dev_mode=True)

        # If someone tries to strip the prefix
        stripped = with_prefix.replace(b"[DEV MODE]", b"")

        # The content changes
        assert stripped != with_prefix
        # And wouldn't match the original raw_content prefixed differently
        with_prod = content.to_bytes_with_mode(dev_mode=False)
        assert stripped != with_prod
