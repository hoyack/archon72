"""Unit tests for hash_algorithms module.

Story: consent-gov-1.3: Hash Chain Implementation

Tests hash algorithm implementations (BLAKE3 and SHA-256) per AC1, AC2, AC3, AC10.
"""

import pytest

from src.domain.governance.events.hash_algorithms import (
    DEFAULT_ALGORITHM,
    GENESIS_PREV_HASH,
    SUPPORTED_ALGORITHMS,
    Blake3Hasher,
    Sha256Hasher,
    compute_hash,
    extract_algorithm_from_hash,
    extract_hex_digest,
    get_hasher,
    is_genesis_hash,
    make_genesis_hash,
    validate_hash_format,
    verify_hash,
)


class TestBlake3Hasher:
    """Tests for Blake3Hasher (AC1)."""

    def test_blake3_hasher_name(self) -> None:
        """Blake3Hasher.name returns 'blake3'."""
        hasher = Blake3Hasher()
        assert hasher.name == "blake3"

    def test_blake3_hash_returns_32_bytes(self) -> None:
        """Blake3Hasher.hash returns 32-byte digest."""
        hasher = Blake3Hasher()
        digest = hasher.hash(b"test data")
        assert len(digest) == 32

    def test_blake3_hash_is_deterministic(self) -> None:
        """Same input produces same hash."""
        hasher = Blake3Hasher()
        digest1 = hasher.hash(b"test data")
        digest2 = hasher.hash(b"test data")
        assert digest1 == digest2

    def test_blake3_different_input_different_hash(self) -> None:
        """Different input produces different hash."""
        hasher = Blake3Hasher()
        digest1 = hasher.hash(b"test data 1")
        digest2 = hasher.hash(b"test data 2")
        assert digest1 != digest2


class TestSha256Hasher:
    """Tests for Sha256Hasher (AC2)."""

    def test_sha256_hasher_name(self) -> None:
        """Sha256Hasher.name returns 'sha256'."""
        hasher = Sha256Hasher()
        assert hasher.name == "sha256"

    def test_sha256_hash_returns_32_bytes(self) -> None:
        """Sha256Hasher.hash returns 32-byte digest."""
        hasher = Sha256Hasher()
        digest = hasher.hash(b"test data")
        assert len(digest) == 32

    def test_sha256_hash_is_deterministic(self) -> None:
        """Same input produces same hash."""
        hasher = Sha256Hasher()
        digest1 = hasher.hash(b"test data")
        digest2 = hasher.hash(b"test data")
        assert digest1 == digest2

    def test_sha256_different_input_different_hash(self) -> None:
        """Different input produces different hash."""
        hasher = Sha256Hasher()
        digest1 = hasher.hash(b"test data 1")
        digest2 = hasher.hash(b"test data 2")
        assert digest1 != digest2


class TestAlgorithmPrefixFormat:
    """Tests for algorithm-prefixed hash format (AC3)."""

    def test_compute_hash_blake3_prefix(self) -> None:
        """compute_hash with blake3 returns 'blake3:...' format."""
        result = compute_hash(b"test", "blake3")
        assert result.startswith("blake3:")
        assert len(result) == 7 + 64  # prefix + colon + 64 hex chars

    def test_compute_hash_sha256_prefix(self) -> None:
        """compute_hash with sha256 returns 'sha256:...' format."""
        result = compute_hash(b"test", "sha256")
        assert result.startswith("sha256:")
        assert len(result) == 7 + 64  # prefix + colon + 64 hex chars

    def test_extract_algorithm_blake3(self) -> None:
        """extract_algorithm_from_hash extracts 'blake3' from prefix."""
        hash_str = f"blake3:{'a' * 64}"
        assert extract_algorithm_from_hash(hash_str) == "blake3"

    def test_extract_algorithm_sha256(self) -> None:
        """extract_algorithm_from_hash extracts 'sha256' from prefix."""
        hash_str = f"sha256:{'b' * 64}"
        assert extract_algorithm_from_hash(hash_str) == "sha256"

    def test_extract_algorithm_invalid_no_colon(self) -> None:
        """extract_algorithm_from_hash raises for hash without colon."""
        with pytest.raises(ValueError, match="Invalid hash format"):
            extract_algorithm_from_hash("abc123")

    def test_extract_algorithm_unsupported(self) -> None:
        """extract_algorithm_from_hash raises for unsupported algorithm."""
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            extract_algorithm_from_hash(f"md5:{'c' * 32}")

    def test_extract_hex_digest(self) -> None:
        """extract_hex_digest returns hex part without prefix."""
        hex_part = "a" * 64
        hash_str = f"blake3:{hex_part}"
        assert extract_hex_digest(hash_str) == hex_part


class TestHasherRegistry:
    """Tests for hasher registry functions."""

    def test_get_hasher_blake3(self) -> None:
        """get_hasher returns Blake3Hasher for 'blake3'."""
        hasher = get_hasher("blake3")
        assert hasher.name == "blake3"

    def test_get_hasher_sha256(self) -> None:
        """get_hasher returns Sha256Hasher for 'sha256'."""
        hasher = get_hasher("sha256")
        assert hasher.name == "sha256"

    def test_get_hasher_unsupported(self) -> None:
        """get_hasher raises for unsupported algorithm."""
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            get_hasher("md5")

    def test_supported_algorithms_contains_blake3(self) -> None:
        """SUPPORTED_ALGORITHMS contains 'blake3'."""
        assert "blake3" in SUPPORTED_ALGORITHMS

    def test_supported_algorithms_contains_sha256(self) -> None:
        """SUPPORTED_ALGORITHMS contains 'sha256'."""
        assert "sha256" in SUPPORTED_ALGORITHMS

    def test_default_algorithm_is_blake3(self) -> None:
        """DEFAULT_ALGORITHM is 'blake3' (preferred per AD-6)."""
        assert DEFAULT_ALGORITHM == "blake3"


class TestHashVerification:
    """Tests for hash verification functions (AC10)."""

    def test_verify_hash_blake3_valid(self) -> None:
        """verify_hash returns True for valid BLAKE3 hash."""
        data = b"test data"
        hash_str = compute_hash(data, "blake3")
        assert verify_hash(data, hash_str) is True

    def test_verify_hash_sha256_valid(self) -> None:
        """verify_hash returns True for valid SHA-256 hash."""
        data = b"test data"
        hash_str = compute_hash(data, "sha256")
        assert verify_hash(data, hash_str) is True

    def test_verify_hash_invalid_data(self) -> None:
        """verify_hash returns False for modified data."""
        hash_str = compute_hash(b"original data", "blake3")
        assert verify_hash(b"modified data", hash_str) is False

    def test_verify_hash_selects_algorithm_from_prefix(self) -> None:
        """verify_hash automatically selects algorithm from hash prefix."""
        data = b"test data"

        # Create SHA-256 hash
        sha256_hash = compute_hash(data, "sha256")

        # Verification should select sha256 from prefix
        assert verify_hash(data, sha256_hash) is True


class TestGenesisHash:
    """Tests for genesis hash handling (AC5)."""

    def test_genesis_prev_hash_is_blake3_zeros(self) -> None:
        """GENESIS_PREV_HASH is blake3 prefix with 64 zeros."""
        assert GENESIS_PREV_HASH == f"blake3:{'0' * 64}"

    def test_is_genesis_hash_true_for_zeros(self) -> None:
        """is_genesis_hash returns True for all-zeros hash."""
        assert is_genesis_hash(GENESIS_PREV_HASH) is True
        assert is_genesis_hash(f"sha256:{'0' * 64}") is True

    def test_is_genesis_hash_false_for_nonzeros(self) -> None:
        """is_genesis_hash returns False for non-zero hash."""
        assert is_genesis_hash(f"blake3:{'a' * 64}") is False

    def test_is_genesis_hash_false_for_invalid_format(self) -> None:
        """is_genesis_hash returns False for invalid format."""
        assert is_genesis_hash("invalid") is False

    def test_make_genesis_hash_blake3(self) -> None:
        """make_genesis_hash creates blake3 zero hash."""
        result = make_genesis_hash("blake3")
        assert result == f"blake3:{'0' * 64}"
        assert is_genesis_hash(result) is True

    def test_make_genesis_hash_sha256(self) -> None:
        """make_genesis_hash creates sha256 zero hash."""
        result = make_genesis_hash("sha256")
        assert result == f"sha256:{'0' * 64}"
        assert is_genesis_hash(result) is True

    def test_make_genesis_hash_unsupported(self) -> None:
        """make_genesis_hash raises for unsupported algorithm."""
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            make_genesis_hash("md5")


class TestHashFormatValidation:
    """Tests for hash format validation."""

    def test_validate_hash_format_valid_blake3(self) -> None:
        """validate_hash_format returns True for valid blake3 hash."""
        assert validate_hash_format(f"blake3:{'a' * 64}") is True

    def test_validate_hash_format_valid_sha256(self) -> None:
        """validate_hash_format returns True for valid sha256 hash."""
        assert validate_hash_format(f"sha256:{'b' * 64}") is True

    def test_validate_hash_format_invalid_no_colon(self) -> None:
        """validate_hash_format returns False for hash without colon."""
        assert validate_hash_format("abc123") is False

    def test_validate_hash_format_invalid_algorithm(self) -> None:
        """validate_hash_format returns False for unsupported algorithm."""
        assert validate_hash_format(f"md5:{'c' * 32}") is False

    def test_validate_hash_format_invalid_length(self) -> None:
        """validate_hash_format returns False for wrong hex length."""
        assert validate_hash_format("blake3:abc") is False

    def test_validate_hash_format_invalid_uppercase(self) -> None:
        """validate_hash_format returns False for uppercase hex."""
        assert validate_hash_format(f"blake3:{'A' * 64}") is False

    def test_validate_hash_format_invalid_nonhex(self) -> None:
        """validate_hash_format returns False for non-hex characters."""
        assert validate_hash_format(f"blake3:{'z' * 64}") is False
