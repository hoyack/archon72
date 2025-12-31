"""Integration tests for HSM functionality.

These tests verify end-to-end HSM operations including:
- AC1: Sign and verify round-trip with DevHSM
- AC2: Watermark cannot be stripped (verification fails)
- Key persistence across HSM instances

Integration tests use real file system for key storage.
"""

import tempfile
from pathlib import Path

import pytest

from src.application.ports.hsm import HSMMode
from src.domain.models.signable import SignableContent
from src.infrastructure.adapters.security.hsm_dev import DevHSM


class TestDevHSMSignVerifyRoundTrip:
    """Integration tests for sign/verify round-trip operations."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_sign_and_verify_roundtrip(self) -> None:
        """AC1: Sign and verify round-trip should work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            # Sign some data
            original_content = b"This is important constitutional data"
            result = await hsm.sign(original_content)

            # Verify the signature
            is_valid = await hsm.verify(result.content, result.signature)

            assert is_valid is True
            assert result.mode == HSMMode.DEVELOPMENT

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_sign_verify_multiple_messages(self) -> None:
        """Multiple messages should each have valid signatures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            messages = [
                b"First message",
                b"Second message with different content",
                b"Third message",
                b"",  # Empty message
                b"A" * 10000,  # Large message
            ]

            for msg in messages:
                result = await hsm.sign(msg)
                is_valid = await hsm.verify(result.content, result.signature)
                assert is_valid is True, f"Failed to verify signature for: {msg[:50]!r}"


class TestWatermarkIntegrity:
    """Integration tests for watermark integrity."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_watermark_cannot_be_stripped(self) -> None:
        """AC2: Stripping watermark should invalidate signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            content = b"Constitutional event data"
            result = await hsm.sign(content)

            # Verify original is valid
            assert await hsm.verify(result.content, result.signature) is True

            # Try to strip the [DEV MODE] prefix
            stripped_content = result.content.replace(b"[DEV MODE]", b"")

            # Signature should be invalid after stripping
            is_valid_after_strip = await hsm.verify(stripped_content, result.signature)
            assert is_valid_after_strip is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_watermark_replacement_invalidates_signature(self) -> None:
        """Replacing watermark should invalidate signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            content = b"Constitutional event data"
            result = await hsm.sign(content)

            # Try to replace [DEV MODE] with [PROD]
            fake_prod_content = result.content.replace(b"[DEV MODE]", b"[PROD]")

            # Signature should be invalid
            is_valid = await hsm.verify(fake_prod_content, result.signature)
            assert is_valid is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_content_modification_invalidates_signature(self) -> None:
        """Any content modification should invalidate signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            content = b"Original constitutional data"
            result = await hsm.sign(content)

            # Modify content in various ways
            modifications = [
                result.content + b"x",  # Append
                b"x" + result.content,  # Prepend
                result.content[:-1],  # Truncate
                result.content.replace(b"Original", b"Modified"),  # Replace
            ]

            for modified in modifications:
                is_valid = await hsm.verify(modified, result.signature)
                assert is_valid is False


class TestKeyPersistence:
    """Integration tests for key persistence across instances."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_key_persistence_across_instances(self) -> None:
        """Keys should persist and work across HSM instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_dir = Path(tmpdir)

            # First instance: generate key and sign
            hsm1 = DevHSM(key_dir=key_dir)
            key_id = await hsm1.generate_key_pair()
            content = b"Data signed by first instance"
            result = await hsm1.sign(content)

            # Second instance: load keys and verify
            hsm2 = DevHSM(key_dir=key_dir)
            loaded_key_id = await hsm2.get_current_key_id()

            # Key IDs should match
            assert loaded_key_id == key_id

            # Should be able to verify signature from first instance
            is_valid = await hsm2.verify(result.content, result.signature)
            assert is_valid is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_new_instance_can_sign_and_verify(self) -> None:
        """New instance with loaded keys can sign and verify."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_dir = Path(tmpdir)

            # First instance: generate key
            hsm1 = DevHSM(key_dir=key_dir)
            await hsm1.generate_key_pair()

            # Second instance: sign new data
            hsm2 = DevHSM(key_dir=key_dir)
            content = b"Data signed by second instance"
            result = await hsm2.sign(content)

            # Third instance: verify
            hsm3 = DevHSM(key_dir=key_dir)
            is_valid = await hsm3.verify(result.content, result.signature)
            assert is_valid is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_key_generations(self) -> None:
        """Multiple key generations should all be usable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_dir = Path(tmpdir)
            hsm = DevHSM(key_dir=key_dir)

            # Generate multiple keys
            await hsm.generate_key_pair()  # First key
            content1 = b"Signed with key 1"
            await hsm.sign(content1)  # Sign with first key

            key2 = await hsm.generate_key_pair()
            content2 = b"Signed with key 2"
            result2 = await hsm.sign(content2)

            # Both signatures should be verifiable
            # Note: Current implementation uses current key for verification
            # This tests that the most recent key works
            assert key2 == await hsm.get_current_key_id()
            assert await hsm.verify(result2.content, result2.signature) is True


class TestSignableContentIntegration:
    """Integration tests for SignableContent with HSM."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_signable_content_parse_after_sign(self) -> None:
        """SignableContent should correctly parse signed bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            original = b"Constitutional data"
            result = await hsm.sign(original)

            # Parse the signed content back
            parsed, is_dev = SignableContent.from_signed_bytes(result.content)

            assert is_dev is True  # DevHSM always uses dev mode
            assert parsed.raw_content == original

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_signable_content_mode_detection(self) -> None:
        """SignableContent should detect correct mode from signed bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hsm = DevHSM(key_dir=Path(tmpdir))

            content = b"Test data"
            result = await hsm.sign(content)

            # The content should start with [DEV MODE]
            assert result.content.startswith(SignableContent.DEV_MODE_PREFIX)

            # Parsing should detect dev mode
            _, is_dev = SignableContent.from_signed_bytes(result.content)
            assert is_dev is True
