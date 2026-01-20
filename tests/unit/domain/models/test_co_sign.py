"""Unit tests for CoSign domain model (Story 5.1).

Tests cover:
- Valid CoSign creation with all fields
- Field validation (UUID formats, timezone-aware datetime, content_hash length)
- signable_content() determinism
- compute_content_hash() correctness
- verify_content_hash() with valid/invalid hashes
- to_dict() / from_dict() round-trip
- Frozen instance immutability

Constitutional Constraints Verified:
- FR-6.2: Unique constraint (tested at integration level)
- NFR-3.5: 0 duplicate signatures (tested at integration level)
- NFR-6.4: Full signer list queryable (model supports querying)
- CT-12: Content hash for witness integrity
"""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import blake3
import pytest

from src.domain.models.co_sign import CoSign


class TestCoSignCreation:
    """Tests for CoSign instantiation and field validation."""

    def test_valid_co_sign_creation_with_all_fields(self) -> None:
        """Test creating a CoSign with all fields specified."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)
        witness_event_id = uuid4()

        co_sign = CoSign(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
            identity_verified=True,
            witness_event_id=witness_event_id,
        )

        assert co_sign.cosign_id == cosign_id
        assert co_sign.petition_id == petition_id
        assert co_sign.signer_id == signer_id
        assert co_sign.signed_at == signed_at
        assert co_sign.content_hash == content_hash
        assert co_sign.identity_verified is True
        assert co_sign.witness_event_id == witness_event_id

    def test_valid_co_sign_creation_with_minimal_fields(self) -> None:
        """Test creating a CoSign with only required fields (defaults for optional)."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        assert co_sign.cosign_id == cosign_id
        assert co_sign.petition_id == petition_id
        assert co_sign.signer_id == signer_id
        assert co_sign.signed_at == signed_at
        assert co_sign.content_hash == content_hash
        # Verify defaults
        assert co_sign.identity_verified is False
        assert co_sign.witness_event_id is None

    def test_invalid_signed_at_not_timezone_aware(self) -> None:
        """Test that signed_at must be timezone-aware."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now()  # Not timezone-aware
        content_hash = b"x" * 32

        with pytest.raises(ValueError, match="signed_at must be timezone-aware"):
            CoSign(
                cosign_id=cosign_id,
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=signed_at,
                content_hash=content_hash,
            )

    def test_invalid_content_hash_too_short(self) -> None:
        """Test that content_hash must be exactly 32 bytes."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = b"x" * 16  # Only 16 bytes

        with pytest.raises(ValueError, match="content_hash must be 32 bytes"):
            CoSign(
                cosign_id=cosign_id,
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=signed_at,
                content_hash=content_hash,
            )

    def test_invalid_content_hash_too_long(self) -> None:
        """Test that content_hash must be exactly 32 bytes."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = b"x" * 64  # 64 bytes

        with pytest.raises(ValueError, match="content_hash must be 32 bytes"):
            CoSign(
                cosign_id=cosign_id,
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=signed_at,
                content_hash=content_hash,
            )

    def test_invalid_content_hash_empty(self) -> None:
        """Test that content_hash cannot be empty."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = b""  # Empty

        with pytest.raises(ValueError, match="content_hash must be 32 bytes"):
            CoSign(
                cosign_id=cosign_id,
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=signed_at,
                content_hash=content_hash,
            )


class TestCoSignSignableContent:
    """Tests for signable_content() method."""

    def test_signable_content_returns_bytes(self) -> None:
        """Test that signable_content() returns bytes."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        result = co_sign.signable_content()
        assert isinstance(result, bytes)

    def test_signable_content_deterministic(self) -> None:
        """Test that signable_content() produces deterministic output."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        result1 = co_sign.signable_content()
        result2 = co_sign.signable_content()
        assert result1 == result2

    def test_signable_content_includes_key_fields(self) -> None:
        """Test that signable_content() includes petition_id, signer_id, and signed_at."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        result = co_sign.signable_content().decode("utf-8")
        assert str(petition_id) in result
        assert str(signer_id) in result
        assert signed_at.isoformat() in result

    def test_signable_content_different_for_different_co_signs(self) -> None:
        """Test that different co-signs produce different signable_content."""
        signed_at = datetime.now(timezone.utc)

        # Co-sign 1
        petition_id_1 = uuid4()
        signer_id_1 = uuid4()
        content_hash_1 = CoSign.compute_content_hash(
            petition_id_1, signer_id_1, signed_at
        )
        co_sign_1 = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id_1,
            signer_id=signer_id_1,
            signed_at=signed_at,
            content_hash=content_hash_1,
        )

        # Co-sign 2 (different signer)
        petition_id_2 = petition_id_1
        signer_id_2 = uuid4()
        content_hash_2 = CoSign.compute_content_hash(
            petition_id_2, signer_id_2, signed_at
        )
        co_sign_2 = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id_2,
            signer_id=signer_id_2,
            signed_at=signed_at,
            content_hash=content_hash_2,
        )

        assert co_sign_1.signable_content() != co_sign_2.signable_content()


class TestCoSignComputeContentHash:
    """Tests for compute_content_hash() static method."""

    def test_compute_content_hash_returns_32_bytes(self) -> None:
        """Test that compute_content_hash() returns exactly 32 bytes (BLAKE3)."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        result = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        assert isinstance(result, bytes)
        assert len(result) == 32

    def test_compute_content_hash_deterministic(self) -> None:
        """Test that compute_content_hash() is deterministic."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        result1 = CoSign.compute_content_hash(petition_id, signer_id, signed_at)
        result2 = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        assert result1 == result2

    def test_compute_content_hash_uses_blake3(self) -> None:
        """Test that compute_content_hash() uses BLAKE3 algorithm."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        # Compute using the method
        result = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        # Compute manually using BLAKE3
        content = f"{petition_id}|{signer_id}|{signed_at.isoformat()}".encode()
        expected = blake3.blake3(content).digest()

        assert result == expected

    def test_compute_content_hash_different_inputs_produce_different_hashes(
        self,
    ) -> None:
        """Test that different inputs produce different hashes."""
        signed_at = datetime.now(timezone.utc)

        hash1 = CoSign.compute_content_hash(uuid4(), uuid4(), signed_at)
        hash2 = CoSign.compute_content_hash(uuid4(), uuid4(), signed_at)

        assert hash1 != hash2


class TestCoSignVerifyContentHash:
    """Tests for verify_content_hash() method."""

    def test_verify_content_hash_returns_true_for_valid_hash(self) -> None:
        """Test that verify_content_hash() returns True for valid hash."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        assert co_sign.verify_content_hash() is True

    def test_verify_content_hash_returns_false_for_invalid_hash(self) -> None:
        """Test that verify_content_hash() returns False for tampered hash."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        # Create a fake hash (wrong content)
        fake_hash = b"x" * 32

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=fake_hash,
        )

        assert co_sign.verify_content_hash() is False

    def test_verify_content_hash_detects_petition_id_tampering(self) -> None:
        """Test that verify_content_hash() detects petition_id changes."""
        petition_id_original = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        # Hash computed with original petition_id
        content_hash = CoSign.compute_content_hash(
            petition_id_original, signer_id, signed_at
        )

        # Create co-sign with different petition_id but same hash
        petition_id_tampered = uuid4()
        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id_tampered,  # Tampered!
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        assert co_sign.verify_content_hash() is False

    def test_verify_content_hash_detects_signed_at_tampering(self) -> None:
        """Test that verify_content_hash() detects signed_at changes."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at_original = datetime.now(timezone.utc)
        # Hash computed with original time
        content_hash = CoSign.compute_content_hash(
            petition_id, signer_id, signed_at_original
        )

        # Create co-sign with different signed_at but same hash
        signed_at_tampered = signed_at_original + timedelta(seconds=1)
        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at_tampered,  # Tampered!
            content_hash=content_hash,
        )

        assert co_sign.verify_content_hash() is False


class TestCoSignSerialization:
    """Tests for to_dict() and from_dict() serialization methods."""

    def test_to_dict_returns_dict(self) -> None:
        """Test that to_dict() returns a dictionary."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        result = co_sign.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_includes_all_fields(self) -> None:
        """Test that to_dict() includes all fields."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)
        witness_event_id = uuid4()

        co_sign = CoSign(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
            identity_verified=True,
            witness_event_id=witness_event_id,
        )

        result = co_sign.to_dict()

        assert result["cosign_id"] == str(cosign_id)
        assert result["petition_id"] == str(petition_id)
        assert result["signer_id"] == str(signer_id)
        assert result["signed_at"] == signed_at.isoformat()
        assert result["content_hash"] == content_hash.hex()
        assert result["identity_verified"] is True
        assert result["witness_event_id"] == str(witness_event_id)

    def test_to_dict_includes_schema_version(self) -> None:
        """Test that to_dict() includes schema_version (D2 compliance)."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        result = co_sign.to_dict()
        assert "schema_version" in result
        assert result["schema_version"] == 1

    def test_to_dict_handles_none_witness_event_id(self) -> None:
        """Test that to_dict() handles None witness_event_id."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
            witness_event_id=None,
        )

        result = co_sign.to_dict()
        assert result["witness_event_id"] is None

    def test_from_dict_creates_valid_co_sign(self) -> None:
        """Test that from_dict() creates a valid CoSign."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)
        witness_event_id = uuid4()

        data = {
            "cosign_id": str(cosign_id),
            "petition_id": str(petition_id),
            "signer_id": str(signer_id),
            "signed_at": signed_at.isoformat(),
            "content_hash": content_hash.hex(),
            "identity_verified": True,
            "witness_event_id": str(witness_event_id),
        }

        co_sign = CoSign.from_dict(data)

        assert co_sign.cosign_id == cosign_id
        assert co_sign.petition_id == petition_id
        assert co_sign.signer_id == signer_id
        assert co_sign.signed_at == signed_at
        assert co_sign.content_hash == content_hash
        assert co_sign.identity_verified is True
        assert co_sign.witness_event_id == witness_event_id

    def test_from_dict_handles_none_witness_event_id(self) -> None:
        """Test that from_dict() handles None witness_event_id."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        data = {
            "cosign_id": str(cosign_id),
            "petition_id": str(petition_id),
            "signer_id": str(signer_id),
            "signed_at": signed_at.isoformat(),
            "content_hash": content_hash.hex(),
            "identity_verified": False,
            "witness_event_id": None,
        }

        co_sign = CoSign.from_dict(data)
        assert co_sign.witness_event_id is None

    def test_from_dict_handles_missing_optional_fields(self) -> None:
        """Test that from_dict() handles missing optional fields."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        data = {
            "cosign_id": str(cosign_id),
            "petition_id": str(petition_id),
            "signer_id": str(signer_id),
            "signed_at": signed_at.isoformat(),
            "content_hash": content_hash.hex(),
            # identity_verified and witness_event_id not provided
        }

        co_sign = CoSign.from_dict(data)
        assert co_sign.identity_verified is False
        assert co_sign.witness_event_id is None

    def test_to_dict_from_dict_round_trip(self) -> None:
        """Test that to_dict() -> from_dict() round-trip preserves data."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)
        witness_event_id = uuid4()

        original = CoSign(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
            identity_verified=True,
            witness_event_id=witness_event_id,
        )

        data = original.to_dict()
        restored = CoSign.from_dict(data)

        assert restored == original

    def test_to_dict_from_dict_round_trip_with_defaults(self) -> None:
        """Test round-trip with default optional values."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        original = CoSign(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        data = original.to_dict()
        restored = CoSign.from_dict(data)

        assert restored == original


class TestCoSignImmutability:
    """Tests for frozen dataclass immutability."""

    def test_cannot_modify_cosign_id(self) -> None:
        """Test that cosign_id cannot be modified after creation."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        with pytest.raises(FrozenInstanceError):
            co_sign.cosign_id = uuid4()  # type: ignore[misc]

    def test_cannot_modify_petition_id(self) -> None:
        """Test that petition_id cannot be modified after creation."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        with pytest.raises(FrozenInstanceError):
            co_sign.petition_id = uuid4()  # type: ignore[misc]

    def test_cannot_modify_identity_verified(self) -> None:
        """Test that identity_verified cannot be modified after creation."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
            identity_verified=False,
        )

        with pytest.raises(FrozenInstanceError):
            co_sign.identity_verified = True  # type: ignore[misc]


class TestCoSignEquality:
    """Tests for equality comparison."""

    def test_equal_co_signs_are_equal(self) -> None:
        """Test that two CoSigns with same values are equal."""
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign_1 = CoSign(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        co_sign_2 = CoSign(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        assert co_sign_1 == co_sign_2

    def test_different_co_signs_are_not_equal(self) -> None:
        """Test that two CoSigns with different IDs are not equal."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign_1 = CoSign(
            cosign_id=uuid4(),  # Different
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        co_sign_2 = CoSign(
            cosign_id=uuid4(),  # Different
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        assert co_sign_1 != co_sign_2

    def test_co_sign_is_hashable(self) -> None:
        """Test that CoSign can be used in sets/dicts (hashable)."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)
        content_hash = CoSign.compute_content_hash(petition_id, signer_id, signed_at)

        co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        # Should be hashable
        hash_value = hash(co_sign)
        assert isinstance(hash_value, int)

        # Should work in sets
        co_sign_set = {co_sign}
        assert co_sign in co_sign_set
