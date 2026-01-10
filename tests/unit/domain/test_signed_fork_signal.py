"""Unit tests for SignedForkSignal domain model (Story 3.8, FR84).

Tests the SignedForkSignal dataclass for signed fork detection signals.
This enables external observers to verify fork detection authenticity.

Constitutional Constraints:
- FR84: Fork detection signals MUST be signed by the detecting service
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timezone
from uuid import UUID

import pytest

from src.domain.events.fork_detected import ForkDetectedPayload
from src.domain.models.signed_fork_signal import SignedForkSignal


class TestSignedForkSignal:
    """Tests for SignedForkSignal dataclass."""

    @pytest.fixture
    def fork_payload(self) -> ForkDetectedPayload:
        """Fixture providing a valid fork detected payload."""
        return ForkDetectedPayload(
            conflicting_event_ids=[
                UUID("11111111-1111-1111-1111-111111111111"),
                UUID("22222222-2222-2222-2222-222222222222"),
            ],
            prev_hash="a" * 64,
            content_hashes=["b" * 64, "c" * 64],
            detection_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            detecting_service_id="fork-monitor-001",
        )

    @pytest.fixture
    def valid_signature(self) -> str:
        """Fixture providing a valid base64-encoded signature."""
        return "c2lnbmF0dXJlX2RhdGFfaGVyZQ=="  # Base64 encoded

    @pytest.fixture
    def signed_signal(
        self, fork_payload: ForkDetectedPayload, valid_signature: str
    ) -> SignedForkSignal:
        """Fixture providing a valid signed fork signal."""
        return SignedForkSignal(
            fork_payload=fork_payload,
            signature=valid_signature,
            signing_key_id="key-001",
            sig_alg_version=1,
        )

    def test_create_signed_fork_signal(
        self, fork_payload: ForkDetectedPayload, valid_signature: str
    ) -> None:
        """Should create SignedForkSignal with valid data."""
        signal = SignedForkSignal(
            fork_payload=fork_payload,
            signature=valid_signature,
            signing_key_id="key-001",
            sig_alg_version=1,
        )

        assert signal.fork_payload == fork_payload
        assert signal.signature == valid_signature
        assert signal.signing_key_id == "key-001"
        assert signal.sig_alg_version == 1

    def test_signed_signal_is_frozen(self, signed_signal: SignedForkSignal) -> None:
        """SignedForkSignal should be immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            signed_signal.signature = "new_signature"  # type: ignore[misc]

    def test_fork_payload_is_fork_detected_payload(
        self, signed_signal: SignedForkSignal
    ) -> None:
        """fork_payload should be a ForkDetectedPayload."""
        assert isinstance(signed_signal.fork_payload, ForkDetectedPayload)

    def test_signature_is_string(self, signed_signal: SignedForkSignal) -> None:
        """signature should be a string (Base64 encoded)."""
        assert isinstance(signed_signal.signature, str)

    def test_signing_key_id_is_string(self, signed_signal: SignedForkSignal) -> None:
        """signing_key_id should be a string."""
        assert isinstance(signed_signal.signing_key_id, str)

    def test_sig_alg_version_is_int(self, signed_signal: SignedForkSignal) -> None:
        """sig_alg_version should be an integer."""
        assert isinstance(signed_signal.sig_alg_version, int)

    def test_get_signable_content_returns_bytes(
        self, signed_signal: SignedForkSignal
    ) -> None:
        """get_signable_content() should return bytes from fork_payload."""
        result = signed_signal.get_signable_content()
        assert isinstance(result, bytes)

    def test_get_signable_content_matches_payload(
        self, signed_signal: SignedForkSignal
    ) -> None:
        """get_signable_content() should match fork_payload.signable_content()."""
        result = signed_signal.get_signable_content()
        expected = signed_signal.fork_payload.signable_content()
        assert result == expected

    def test_equality_same_data(
        self, fork_payload: ForkDetectedPayload, valid_signature: str
    ) -> None:
        """Two SignedForkSignals with same data should be equal."""
        signal1 = SignedForkSignal(
            fork_payload=fork_payload,
            signature=valid_signature,
            signing_key_id="key-001",
            sig_alg_version=1,
        )
        signal2 = SignedForkSignal(
            fork_payload=fork_payload,
            signature=valid_signature,
            signing_key_id="key-001",
            sig_alg_version=1,
        )

        assert signal1 == signal2

    def test_inequality_different_signature(
        self, fork_payload: ForkDetectedPayload
    ) -> None:
        """Two SignedForkSignals with different signatures should not be equal."""
        signal1 = SignedForkSignal(
            fork_payload=fork_payload,
            signature="signature_1",
            signing_key_id="key-001",
            sig_alg_version=1,
        )
        signal2 = SignedForkSignal(
            fork_payload=fork_payload,
            signature="signature_2",
            signing_key_id="key-001",
            sig_alg_version=1,
        )

        assert signal1 != signal2

    def test_inequality_different_key_id(
        self, fork_payload: ForkDetectedPayload, valid_signature: str
    ) -> None:
        """Two SignedForkSignals with different key IDs should not be equal."""
        signal1 = SignedForkSignal(
            fork_payload=fork_payload,
            signature=valid_signature,
            signing_key_id="key-001",
            sig_alg_version=1,
        )
        signal2 = SignedForkSignal(
            fork_payload=fork_payload,
            signature=valid_signature,
            signing_key_id="key-002",
            sig_alg_version=1,
        )

        assert signal1 != signal2

    def test_inequality_different_alg_version(
        self, fork_payload: ForkDetectedPayload, valid_signature: str
    ) -> None:
        """Two SignedForkSignals with different alg versions should not be equal."""
        signal1 = SignedForkSignal(
            fork_payload=fork_payload,
            signature=valid_signature,
            signing_key_id="key-001",
            sig_alg_version=1,
        )
        signal2 = SignedForkSignal(
            fork_payload=fork_payload,
            signature=valid_signature,
            signing_key_id="key-001",
            sig_alg_version=2,
        )

        assert signal1 != signal2

    def test_has_all_required_fields(self, signed_signal: SignedForkSignal) -> None:
        """SignedForkSignal should have all required fields."""
        assert hasattr(signed_signal, "fork_payload")
        assert hasattr(signed_signal, "signature")
        assert hasattr(signed_signal, "signing_key_id")
        assert hasattr(signed_signal, "sig_alg_version")
        assert hasattr(signed_signal, "get_signable_content")
