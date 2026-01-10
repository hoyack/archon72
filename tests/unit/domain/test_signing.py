"""Unit tests for event signing utilities (FR3, FR74).

Tests the signable content computation and signature format conversion
for the constitutional event store.

Constitutional Constraints:
- FR3: Events must have agent attribution
- FR74: Invalid agent signatures must be rejected
- MA-2: Signature must cover prev_hash (chain binding)
"""

from __future__ import annotations

import base64

import pytest


class TestComputeSignableContent:
    """Tests for compute_signable_content function."""

    def test_returns_bytes(self) -> None:
        """Signable content should return bytes."""
        from src.domain.events.signing import compute_signable_content

        result = compute_signable_content(
            content_hash="abc123" * 10 + "abcd",  # 64 chars
            prev_hash="0" * 64,
            agent_id="agent-001",
        )

        assert isinstance(result, bytes)

    def test_deterministic_output(self) -> None:
        """Same inputs should produce same output (canonical)."""
        from src.domain.events.signing import compute_signable_content

        result1 = compute_signable_content(
            content_hash="abc123" * 10 + "abcd",
            prev_hash="0" * 64,
            agent_id="agent-001",
        )
        result2 = compute_signable_content(
            content_hash="abc123" * 10 + "abcd",
            prev_hash="0" * 64,
            agent_id="agent-001",
        )

        assert result1 == result2

    def test_includes_all_fields(self) -> None:
        """Output should include all three fields."""
        from src.domain.events.signing import compute_signable_content

        result = compute_signable_content(
            content_hash="hash123",
            prev_hash="prev456",
            agent_id="agent-789",
        )

        # Decode and verify all fields present
        content_str = result.decode("utf-8")
        assert "hash123" in content_str
        assert "prev456" in content_str
        assert "agent-789" in content_str

    def test_canonical_json_sorted_keys(self) -> None:
        """Output should be canonical JSON with sorted keys."""
        from src.domain.events.signing import compute_signable_content

        result = compute_signable_content(
            content_hash="c_hash",
            prev_hash="p_hash",
            agent_id="a_id",
        )

        content_str = result.decode("utf-8")
        # Keys should appear in alphabetical order: agent_id, content_hash, prev_hash
        agent_pos = content_str.find("agent_id")
        content_pos = content_str.find("content_hash")
        prev_pos = content_str.find("prev_hash")

        assert agent_pos < content_pos < prev_pos, "Keys should be sorted alphabetically"

    def test_no_whitespace(self) -> None:
        """Canonical JSON should have no extra whitespace."""
        from src.domain.events.signing import compute_signable_content

        result = compute_signable_content(
            content_hash="hash",
            prev_hash="prev",
            agent_id="agent",
        )

        content_str = result.decode("utf-8")
        # Should not have ": " or ", " - only ":" and ","
        assert ": " not in content_str
        assert ", " not in content_str

    def test_different_inputs_different_outputs(self) -> None:
        """Different inputs should produce different outputs."""
        from src.domain.events.signing import compute_signable_content

        result1 = compute_signable_content(
            content_hash="hash1",
            prev_hash="prev1",
            agent_id="agent1",
        )
        result2 = compute_signable_content(
            content_hash="hash2",
            prev_hash="prev1",
            agent_id="agent1",
        )

        assert result1 != result2

    def test_chain_binding_different_prev_hash(self) -> None:
        """MA-2: Different prev_hash should produce different signable content."""
        from src.domain.events.signing import compute_signable_content

        result1 = compute_signable_content(
            content_hash="same_hash",
            prev_hash="prev_A",
            agent_id="same_agent",
        )
        result2 = compute_signable_content(
            content_hash="same_hash",
            prev_hash="prev_B",
            agent_id="same_agent",
        )

        assert result1 != result2, "MA-2: Signature must depend on prev_hash"

    def test_system_agent_format(self) -> None:
        """System agents use SYSTEM:{service_name} format."""
        from src.domain.events.signing import compute_signable_content

        result = compute_signable_content(
            content_hash="hash",
            prev_hash="prev",
            agent_id="SYSTEM:WATCHDOG",
        )

        content_str = result.decode("utf-8")
        assert "SYSTEM:WATCHDOG" in content_str


class TestSignatureToBase64:
    """Tests for signature_to_base64 function."""

    def test_converts_bytes_to_string(self) -> None:
        """Should convert bytes to base64 string."""
        from src.domain.events.signing import signature_to_base64

        raw_sig = b"\x00\x01\x02\x03\x04\x05"
        result = signature_to_base64(raw_sig)

        assert isinstance(result, str)

    def test_valid_base64(self) -> None:
        """Output should be valid base64."""
        from src.domain.events.signing import signature_to_base64

        raw_sig = b"test signature bytes"
        result = signature_to_base64(raw_sig)

        # Should not raise
        decoded = base64.b64decode(result)
        assert decoded == raw_sig

    def test_ed25519_signature_length(self) -> None:
        """Ed25519 64-byte signature should produce ~88 char base64."""
        from src.domain.events.signing import signature_to_base64

        # Ed25519 signatures are exactly 64 bytes
        raw_sig = b"x" * 64
        result = signature_to_base64(raw_sig)

        # 64 bytes = 88 base64 chars (with padding)
        assert 80 <= len(result) <= 100


class TestSignatureFromBase64:
    """Tests for signature_from_base64 function."""

    def test_converts_string_to_bytes(self) -> None:
        """Should convert base64 string to bytes."""
        from src.domain.events.signing import signature_from_base64

        b64_sig = base64.b64encode(b"test").decode("ascii")
        result = signature_from_base64(b64_sig)

        assert isinstance(result, bytes)
        assert result == b"test"

    def test_roundtrip(self) -> None:
        """to_base64 and from_base64 should roundtrip."""
        from src.domain.events.signing import signature_from_base64, signature_to_base64

        original = b"this is a test signature of exactly 64 bytes for ed25519 test!!"
        encoded = signature_to_base64(original)
        decoded = signature_from_base64(encoded)

        assert decoded == original

    def test_invalid_base64_raises(self) -> None:
        """Invalid base64 should raise ValueError."""
        from src.domain.events.signing import signature_from_base64

        with pytest.raises(Exception):  # binascii.Error or ValueError
            signature_from_base64("not valid base64!!!")


class TestSigningConstants:
    """Tests for signing module constants."""

    def test_sig_alg_version(self) -> None:
        """SIG_ALG_VERSION should be 1 for Ed25519."""
        from src.domain.events.signing import SIG_ALG_VERSION

        assert SIG_ALG_VERSION == 1

    def test_sig_alg_name(self) -> None:
        """SIG_ALG_NAME should be Ed25519."""
        from src.domain.events.signing import SIG_ALG_NAME

        assert SIG_ALG_NAME == "Ed25519"
